"""Ordinary Python callables, scheduled by the native graph engine."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import traceback
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from . import _native
from .cache import Cache, ResumeDecisionError, fingerprint
from .history import History, RunActiveError


@dataclass(frozen=True)
class Node:
    """Reference to one graph's output; pass it as an argument to another node."""

    name: str
    _owner: object


@dataclass(frozen=True)
class Failure:
    exception_type: str
    message: str
    traceback: str


@dataclass(frozen=True)
class RunReport:
    graph: str
    run_id: str | None
    states: Mapping[str, str]
    outputs: Mapping[str, Any]
    failures: Mapping[str, Failure]
    reuse: Mapping[str, str]

    @property
    def succeeded(self) -> bool:
        return all(s in ("succeeded", "reused", "unselected") for s in self.states.values())

    def raise_for_status(self) -> RunReport:
        if not self.succeeded:
            raise RunError(self)
        return self


class _TaskException(Exception):
    def __init__(self, original):
        self.original = original
        super().__init__(str(original))


class RunError(RuntimeError):
    def __init__(self, report: RunReport):
        self.report = report
        super().__init__(f"Graph {report.graph!r} failed: {', '.join(report.failures)}")


def _map_value(value, node_fn):
    if isinstance(value, Node):
        return node_fn(value)
    if type(value) is list:
        return [_map_value(v, node_fn) for v in value]
    if type(value) is tuple:
        return tuple(_map_value(v, node_fn) for v in value)
    if type(value) is dict:
        if any(isinstance(k, Node) for k in value):
            raise TypeError("Node references are supported in dictionary values, not keys")
        return {k: _map_value(v, node_fn) for k, v in value.items()}
    return value


@dataclass(frozen=True)
class _Task:
    node: Node
    function: Callable
    args: tuple
    kwargs: dict
    after: tuple[Node, ...]
    cache: Cache | None


class Graph:
    """Build a static DAG; compilation freezes bindings and dependencies."""

    def __init__(self, name: str, *, version: str = "1", store=None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("graph name must be a nonempty string")
        if not isinstance(version, str) or not version:
            raise ValueError("graph version must be a nonempty string")
        self.store = store if isinstance(store, History) or store is None else History(store)
        self.name = name
        self.version = version
        self._owner = object()
        self._tasks: dict[str, _Task] = {}

    def _check_node(self, node: Node) -> Node:
        if (
            not isinstance(node, Node)
            or node._owner is not self._owner
            or node.name not in self._tasks
        ):
            raise ValueError("node does not belong to this graph")
        return node

    def add(self, name: str, function: Callable, *args, after=(), cache=None, **kwargs) -> Node:
        if not isinstance(name, str) or not name.strip() or name in self._tasks:
            raise ValueError("node name must be a nonempty unique string")
        if not callable(function):
            raise TypeError("node function must be callable")
        if cache is not None and not isinstance(cache, Cache):
            raise TypeError("cache must be Cache(key) or None")
        args = _map_value(args, self._check_node)
        kwargs = _map_value(kwargs, self._check_node)
        after = tuple(self._check_node(n) for n in after)
        node = Node(name, self._owner)
        self._tasks[name] = _Task(node, function, args, kwargs, after, cache)
        return node

    def depends_on(self, node: Node, *dependencies: Node) -> None:
        node = self._check_node(node)
        deps = tuple(self._check_node(n) for n in dependencies)
        old = self._tasks[node.name]
        self._tasks[node.name] = _Task(
            old.node, old.function, old.args, old.kwargs, old.after + deps, old.cache
        )

    def compile(self, *targets: Node | str) -> Plan:
        names = []
        for target in targets:
            if isinstance(target, Node):
                names.append(self._check_node(target).name)
            elif isinstance(target, str):
                names.append(target)
            else:
                raise TypeError("targets must be Node references or node names")
        return Plan(
            self.name,
            self.version,
            tuple(self._tasks.values()),
            tuple(dict.fromkeys(names)),
            self.store,
        )

    def run(self, *targets: Node | str, max_concurrency: int = 4) -> RunReport:
        return self.compile(*targets).run(max_concurrency=max_concurrency)


class Plan:
    def __init__(self, name, version, tasks, targets, store=None):
        self.store = store
        self.name, self.version, self.targets = name, version, targets
        # Rebuild binding containers so caller mutations cannot change plan structure.
        self._tasks = tuple(
            _Task(
                t.node,
                t.function,
                _map_value(t.args, lambda n: n),
                _map_value(t.kwargs, lambda n: n),
                t.after,
                t.cache,
            )
            for t in tasks
        )
        self._index = {t.node.name: i for i, t in enumerate(tasks)}
        dependencies = []
        for task in tasks:
            deps = set()

            def collect(n, deps=deps):
                deps.add(self._index[n.name])
                return n

            _map_value(task.args, collect)
            _map_value(task.kwargs, collect)
            for n in task.after:
                collect(n)
            dependencies.append(sorted(deps))
        self._dependencies = dependencies
        self._topology = _native.Topology(list(self._index), dependencies)
        self._selected = self._topology.select(list(targets))

    def describe(self) -> dict:
        return {
            "graph": self.name,
            "version": self.version,
            "targets": list(self.targets),
            "nodes": [
                {
                    "name": t.node.name,
                    "dependencies": [self._tasks[d].node.name for d in self._dependencies[i]],
                    "selected": self._selected[i],
                    "callable": getattr(t.function, "__qualname__", type(t.function).__name__),
                    "module": getattr(t.function, "__module__", None),
                    "repeat_safe": t.cache is not None,
                    "ordering_dependencies": [n.name for n in t.after],
                }
                for i, t in enumerate(self._tasks)
            ],
            "order": [
                self._tasks[i].node.name for i in self._topology.order() if self._selected[i]
            ],
        }

    def _fingerprints(self):
        keys = [None] * len(self._tasks)
        for i in self._topology.order():
            task = self._tasks[i]
            deps = self._dependencies[i]
            if task.cache is not None and all(keys[d] is not None for d in deps):
                keys[i] = fingerprint(
                    [
                        self.name,
                        self.version,
                        task.node.name,
                        task.cache.key,
                        [[self._tasks[d].node.name, keys[d]] for d in deps],
                    ]
                )
        return keys

    def explain_run(self, *, previous=None, rerun=()):
        force = set(rerun)
        if not force.issubset(self._index):
            raise ValueError("rerun contains unknown node names")
        prior = {}
        if previous is not None:
            if self.store is None:
                raise ValueError("resume requires a history store")
            record = self.store.get(previous)
            if record["graph"] != self.name:
                raise ValueError("previous run belongs to another graph")
            if record["status"] == "running":
                raise RunActiveError(
                    "recover the previous unfinished run explicitly before resuming"
                )
            prior = {n["name"]: n for n in record["nodes"]}
        keys = self._fingerprints()
        nodes = []
        for i, task in enumerate(self._tasks):
            name = task.node.name
            action, reason = "run", "no reusable result"
            if not self._selected[i]:
                action, reason = "unselected", "not needed for targets"
            elif name in force:
                reason = "explicit rerun"
            elif self.store is None:
                reason = "history store disabled"
            elif keys[i] is not None:
                found, _, reason = self.store._cached(keys[i], previous, name)
                action = "reuse" if found else "run"
            else:
                reason = "node or an ancestor has no explicit cache key"
            old = prior.get(name)
            if (
                self._selected[i]
                and action != "reuse"
                and name not in force
                and task.cache is None
                and old is not None
                and (
                    old["started_at"] is not None
                    or old["state"] in ("succeeded", "reused", "failed", "unknown")
                )
            ):
                action, reason = "decision", "previously started work is not declared repeat-safe"
            nodes.append({"name": name, "action": action, "reason": reason})
        return {"graph": self.name, "previous": previous, "nodes": nodes}

    def resume(self, previous, *, rerun=(), max_concurrency=4):
        return self.run(previous=previous, rerun=rerun, max_concurrency=max_concurrency)

    def run(self, *, max_concurrency: int = 4, previous=None, rerun=()) -> RunReport:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.arun(max_concurrency=max_concurrency, previous=previous, rerun=rerun)
            )
        raise RuntimeError("An event loop is running; use await plan.arun()")

    async def arun(self, *, max_concurrency: int = 4, previous=None, rerun=()) -> RunReport:
        if type(max_concurrency) is not int or max_concurrency < 1:
            raise ValueError("max_concurrency must be a positive integer")
        explanation = self.explain_run(previous=previous, rerun=rerun)
        decisions = [n["name"] for n in explanation["nodes"] if n["action"] == "decision"]
        if decisions:
            raise ResumeDecisionError(decisions)
        force = set(rerun)
        keys = self._fingerprints()
        reuse = {n["name"]: n["reason"] for n in explanation["nodes"]}
        state = self._topology.start(list(self.targets), max_concurrency)
        run_id, lease = (
            self.store._start(self.name, self.version, list(self._index), self._selected, previous)
            if self.store is not None
            else (None, None)
        )
        outputs, failures = {}, {}
        pending: dict[asyncio.Task, tuple[int, bool]] = {}
        pool = ThreadPoolExecutor(max_workers=max_concurrency, thread_name_prefix="traversal")
        loop = asyncio.get_running_loop()

        async def invoke(task, args, kwargs, is_async):
            try:
                if is_async:
                    return await task.function(*args, **kwargs)
                ctx = contextvars.copy_context()
                result = await asyncio.shield(
                    loop.run_in_executor(pool, lambda: ctx.run(task.function, *args, **kwargs))
                )
                if inspect.isawaitable(result):
                    if inspect.iscoroutine(result):
                        result.close()
                    raise TypeError(
                        "A blocking callable returned an awaitable; wrap it in an async function"
                    )
                return result
            except asyncio.CancelledError:
                raise
            except BaseException as exc:
                # SystemExit/KeyboardInterrupt in user tasks must not escape the event loop.
                raise _TaskException(exc) from exc

        def complete(future, index):
            name = self._tasks[index].node.name
            if future.cancelled():
                state.finish(index, "cancelled")
                if self.store is not None:
                    self.store._finished(run_id, name, "cancelled")
                return
            exc = future.exception()
            if isinstance(exc, _TaskException):
                exc = exc.original
            if exc is None:
                outputs[name] = future.result()
                if self.store is not None and keys[index] is not None:
                    reuse[name] = self.store._save_result(keys[index], outputs[name])
                state.finish(index, "succeeded")
            else:
                failures[name] = Failure(
                    type(exc).__name__, str(exc), "".join(traceback.format_exception(exc))
                )
                state.finish(index, "failed")
            if self.store is not None:
                self.store._reuse_note(run_id, name, keys[index], reuse[name])
                self.store._finished(
                    run_id, name, "failed" if exc else "succeeded", failures.get(name)
                )

        try:
            while not state.done():
                reused_any = False
                for index in state.admit():
                    task = self._tasks[index]
                    if (
                        self.store is not None
                        and keys[index] is not None
                        and task.node.name not in force
                    ):
                        found, value, reason = self.store._cached(
                            keys[index], previous, task.node.name
                        )
                        if found:
                            outputs[task.node.name] = value
                            reuse[task.node.name] = reason
                            self.store._reuse_note(run_id, task.node.name, keys[index], reason)
                            self.store._finished(run_id, task.node.name, "reused")
                            state.finish(index, "reused")
                            reused_any = True
                            continue
                    if self.store is not None:
                        self.store._running(run_id, task.node.name)
                    args = _map_value(task.args, lambda n: outputs[n.name])
                    kwargs = _map_value(task.kwargs, lambda n: outputs[n.name])
                    is_async = inspect.iscoroutinefunction(
                        task.function
                    ) or inspect.iscoroutinefunction(getattr(task.function, "__call__", None))  # noqa: B004
                    future = asyncio.create_task(invoke(task, args, kwargs, is_async))
                    pending[future] = (index, is_async)
                if not pending:
                    if reused_any:
                        continue
                    if state.done():
                        break
                    raise RuntimeError("scheduler has unfinished work but no runnable nodes")
                done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                # Stable processing when several completions arrive in one event-loop turn.
                for future in sorted(done, key=lambda f: pending[f][0]):
                    index, _ = pending.pop(future)
                    complete(future, index)
            if self.store is not None:
                self.store._end(
                    run_id,
                    dict(zip(self._index, state.states())),
                    "succeeded"
                    if all(s in ("succeeded", "reused", "unselected") for s in state.states())
                    else "failed",
                )
        except BaseException:
            state.cancel()
            for future, (_, is_async) in pending.items():
                if is_async:
                    future.cancel()
            # Blocking calls retain their concurrency slot until they actually finish.
            drain = asyncio.gather(*pending, return_exceptions=True)
            while not drain.done():
                try:
                    await asyncio.shield(drain)
                except asyncio.CancelledError:
                    # Repeated cancellation cannot release the lease before workers finish.
                    continue
            for future, (index, _) in pending.items():
                complete(future, index)
            if self.store is not None:
                self.store._end(
                    run_id,
                    {
                        n: "unknown" if s == "running" else s
                        for n, s in zip(self._index, state.states())
                    },
                    "interrupted",
                )
            raise
        finally:
            pool.shutdown(wait=True)
            if lease is not None:
                lease.close()
        return RunReport(
            self.name,
            run_id,
            MappingProxyType(dict(zip(self._index, state.states()))),
            MappingProxyType(outputs),
            MappingProxyType(failures),
            MappingProxyType(reuse),
        )
