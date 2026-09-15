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
    states: Mapping[str, str]
    outputs: Mapping[str, Any]
    failures: Mapping[str, Failure]

    @property
    def succeeded(self) -> bool:
        return all(s in ("succeeded", "unselected") for s in self.states.values())

    def raise_for_status(self) -> RunReport:
        if not self.succeeded:
            raise RunError(self)
        return self


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


class Graph:
    """Build a static DAG; compilation freezes bindings and dependencies."""

    def __init__(self, name: str, *, version: str = "1"):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("graph name must be a nonempty string")
        if not isinstance(version, str) or not version:
            raise ValueError("graph version must be a nonempty string")
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

    def add(self, name: str, function: Callable, *args, after=(), **kwargs) -> Node:
        if not isinstance(name, str) or not name.strip() or name in self._tasks:
            raise ValueError("node name must be a nonempty unique string")
        if not callable(function):
            raise TypeError("node function must be callable")
        args = _map_value(args, self._check_node)
        kwargs = _map_value(kwargs, self._check_node)
        after = tuple(self._check_node(n) for n in after)
        node = Node(name, self._owner)
        self._tasks[name] = _Task(node, function, args, kwargs, after)
        return node

    def depends_on(self, node: Node, *dependencies: Node) -> None:
        node = self._check_node(node)
        deps = tuple(self._check_node(n) for n in dependencies)
        old = self._tasks[node.name]
        self._tasks[node.name] = _Task(
            old.node, old.function, old.args, old.kwargs, old.after + deps
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
            self.name, self.version, tuple(self._tasks.values()), tuple(dict.fromkeys(names))
        )

    def run(self, *targets: Node | str, max_concurrency: int = 4) -> RunReport:
        return self.compile(*targets).run(max_concurrency=max_concurrency)


class Plan:
    def __init__(self, name, version, tasks, targets):
        self.name, self.version, self.targets = name, version, targets
        # Rebuild binding containers so caller mutations cannot change plan structure.
        self._tasks = tuple(
            _Task(
                t.node,
                t.function,
                _map_value(t.args, lambda n: n),
                _map_value(t.kwargs, lambda n: n),
                t.after,
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
                }
                for i, t in enumerate(self._tasks)
            ],
            "order": [
                self._tasks[i].node.name for i in self._topology.order() if self._selected[i]
            ],
        }

    def run(self, *, max_concurrency: int = 4) -> RunReport:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.arun(max_concurrency=max_concurrency))
        raise RuntimeError("An event loop is running; use await plan.arun()")

    async def arun(self, *, max_concurrency: int = 4) -> RunReport:
        if type(max_concurrency) is not int or max_concurrency < 1:
            raise ValueError("max_concurrency must be a positive integer")
        state = self._topology.start(list(self.targets), max_concurrency)
        outputs, failures = {}, {}
        pending: dict[asyncio.Task, tuple[int, bool]] = {}
        pool = ThreadPoolExecutor(max_workers=max_concurrency, thread_name_prefix="traversal")
        loop = asyncio.get_running_loop()

        async def invoke(task, args, kwargs, is_async):
            if is_async:
                return await task.function(*args, **kwargs)
            ctx = contextvars.copy_context()
            result = await asyncio.shield(
                loop.run_in_executor(pool, lambda: ctx.run(task.function, *args, **kwargs))
            )
            if inspect.isawaitable(result):
                return await result
            return result

        def complete(future, index):
            name = self._tasks[index].node.name
            if future.cancelled():
                state.finish(index, "cancelled")
                return
            exc = future.exception()
            if exc is None:
                outputs[name] = future.result()
                state.finish(index, "succeeded")
            else:
                failures[name] = Failure(
                    type(exc).__name__, str(exc), "".join(traceback.format_exception(exc))
                )
                state.finish(index, "failed")

        try:
            while not state.done():
                for index in state.admit():
                    task = self._tasks[index]
                    args = _map_value(task.args, lambda n: outputs[n.name])
                    kwargs = _map_value(task.kwargs, lambda n: outputs[n.name])
                    is_async = inspect.iscoroutinefunction(
                        task.function
                    ) or inspect.iscoroutinefunction(getattr(task.function, "__call__", None))  # noqa: B004
                    future = asyncio.create_task(invoke(task, args, kwargs, is_async))
                    pending[future] = (index, is_async)
                if not pending:
                    if state.done():
                        break
                    raise RuntimeError("scheduler has unfinished work but no runnable nodes")
                done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                # Stable processing when several completions arrive in one event-loop turn.
                for future in sorted(done, key=lambda f: pending[f][0]):
                    index, _ = pending.pop(future)
                    complete(future, index)
        except BaseException:
            state.cancel()
            for future, (_, is_async) in pending.items():
                if is_async:
                    future.cancel()
            # Blocking calls retain their concurrency slot until they actually finish.
            await asyncio.shield(asyncio.gather(*pending, return_exceptions=True))
            for future, (index, _) in pending.items():
                complete(future, index)
            raise
        finally:
            pool.shutdown(wait=True)
        return RunReport(
            self.name,
            MappingProxyType(dict(zip(self._index, state.states()))),
            MappingProxyType(outputs),
            MappingProxyType(failures),
        )
