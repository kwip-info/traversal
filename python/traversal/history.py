"""Opt-in local run metadata. No task values or credentials are stored by default."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class RunActiveError(RuntimeError):
    """The run still owns its local execution lease."""


class _Lease:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a+b")
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RunActiveError("run has an active local owner") from exc

    def close(self):
        if self.file.closed:
            return
        if os.name == "nt":
            import msvcrt

            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()


class History:
    """Local SQLite history; explicit construction creates the store if needed.

    error_formatter receives an in-memory Failure and returns redacted text.
    The default persists only the exception type. Local filesystems only.
    """

    def __init__(self, path, *, error_formatter=None, max_cache_bytes=1_048_576):
        if type(max_cache_bytes) is not int or max_cache_bytes < 1:
            raise ValueError("max_cache_bytes must be positive")
        self.max_cache_bytes = max_cache_bytes
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._locks = self.path.with_name(self.path.name + ".locks")
        self.error_formatter = error_formatter
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise ValueError(f"unsupported Traversal history schema: {version}")
            if version == 0:
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                if tables:
                    raise ValueError("refusing to initialize an unrelated database")
                db.execute(
                    "CREATE TABLE runs (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, graph TEXT NOT NULL, graph_version TEXT NOT NULL, status TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL, source_run_id TEXT)"
                )
                db.execute("CREATE INDEX runs_lookup ON runs(graph, status, seq DESC)")
                db.execute(
                    "CREATE TABLE nodes (run_id TEXT NOT NULL REFERENCES runs(id), name TEXT NOT NULL, state TEXT NOT NULL, started_at REAL, finished_at REAL, error TEXT, PRIMARY KEY(run_id,name))"
                )
                db.execute("PRAGMA user_version=1")
            if version in (0, 1):
                db.execute("ALTER TABLE nodes ADD COLUMN cache_key TEXT")
                db.execute("ALTER TABLE nodes ADD COLUMN reuse_reason TEXT")
                db.execute(
                    "CREATE TABLE results (fingerprint TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)"
                )
                db.execute("PRAGMA user_version=2")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _lease(self, run_id):
        # IDs supplied to public methods must never escape the locks directory.
        if (
            not isinstance(run_id, str)
            or len(run_id) != 32
            or any(c not in "0123456789abcdef" for c in run_id)
        ):
            raise ValueError("invalid run ID")
        return _Lease(self._locks / (run_id + ".lock"))

    def _start(self, graph, version, names, selected, source_run_id=None):
        run_id = uuid.uuid4().hex
        lease = self._lease(run_id)
        try:
            with self._connect() as db:
                db.execute(
                    "INSERT INTO runs(id,graph,graph_version,status,started_at,source_run_id) VALUES(?,?,?,'running',?,?)",
                    (run_id, graph, version, time.time(), source_run_id),
                )
                db.executemany(
                    "INSERT INTO nodes(run_id,name,state) VALUES(?,?,?)",
                    [
                        (run_id, name, "pending" if selected[i] else "unselected")
                        for i, name in enumerate(names)
                    ],
                )
        except BaseException:
            lease.close()
            raise
        return run_id, lease

    def _running(self, run_id, name):
        with self._connect() as db:
            db.execute(
                "UPDATE nodes SET state='running',started_at=? WHERE run_id=? AND name=?",
                (time.time(), run_id, name),
            )

    def _finished(self, run_id, name, state, failure=None):
        error = None
        if failure is not None:
            error = failure.exception_type
            if self.error_formatter is not None:
                try:
                    error = str(self.error_formatter(failure))[:4096]
                except Exception:  # noqa: BLE001 — user formatter must not replace task outcome
                    error = failure.exception_type + " (error formatter failed)"
        with self._connect() as db:
            db.execute(
                "UPDATE nodes SET state=?,finished_at=?,error=? WHERE run_id=? AND name=?",
                (state, time.time(), error, run_id, name),
            )

    def _end(self, run_id, states, status):
        with self._connect() as db:
            db.executemany(
                "UPDATE nodes SET state=? WHERE run_id=? AND name=?",
                [(state, run_id, name) for name, state in states.items()],
            )
            db.execute(
                "UPDATE runs SET status=?,finished_at=? WHERE id=?", (status, time.time(), run_id)
            )

    def runs(self, *, graph=None, status=None, limit=20):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        where, params = [], []
        for field, value in (("graph", graph), ("status", status)):
            if value is not None:
                where.append(field + "=?")
                params.append(value)
        query = (
            "SELECT * FROM runs"
            + (" WHERE " + " AND ".join(where) if where else "")
            + " ORDER BY seq DESC LIMIT ?"
        )
        with self._connect() as db:
            return [dict(row) for row in db.execute(query, [*params, limit])]

    def latest(self, *, graph, status=None):
        rows = self.runs(graph=graph, status=status, limit=1)
        return rows[0] if rows else None

    def get(self, run_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            result = dict(row)
            result["nodes"] = [
                dict(n)
                for n in db.execute("SELECT * FROM nodes WHERE run_id=? ORDER BY rowid", (run_id,))
            ]
            return result

    def recover(self, run_id):
        """Explicitly recover an abandoned run. Never changes an active run."""
        record = self.get(run_id)
        if record["status"] != "running":
            return record
        lease = self._lease(run_id)
        try:
            with self._connect() as db:
                db.execute(
                    "UPDATE nodes SET state=CASE WHEN state='running' THEN 'unknown' ELSE 'cancelled' END WHERE run_id=? AND state IN ('running','pending','ready')",
                    (run_id,),
                )
                db.execute(
                    "UPDATE runs SET status='interrupted',finished_at=? WHERE id=? AND status='running'",
                    (time.time(), run_id),
                )
        finally:
            lease.close()
        return self.get(run_id)

    def _cached(self, key, previous=None, node=None):
        with self._connect() as db:
            if previous is not None:
                allowed = db.execute(
                    "SELECT 1 FROM nodes WHERE run_id=? AND name=? AND cache_key=? AND state IN ('succeeded','reused')",
                    (previous, node, key),
                ).fetchone()
                if allowed is None:
                    return False, None, "no compatible result in previous run"
            row = db.execute(
                "SELECT payload,digest FROM results WHERE fingerprint=? AND length(CAST(payload AS BLOB))<=?",
                (key, self.max_cache_bytes),
            ).fetchone()
            if row is None:
                return False, None, "result missing or exceeds byte limit"
            payload, digest = row
            if hashlib.sha256(payload.encode()).hexdigest() != digest:
                return False, None, "result integrity check failed"
            try:
                result = json.loads(payload)
                from .cache import encode

                encode(result, self.max_cache_bytes)
            except (ValueError, TypeError, RecursionError):
                return False, None, "invalid JSON result"
            return True, result, "compatible persisted result"

    def _save_result(self, key, value):
        from .cache import encode

        try:
            payload, digest = encode(value, self.max_cache_bytes)
        except (ValueError, TypeError, RecursionError) as exc:
            return "not persisted: " + str(exc)
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO results(fingerprint,payload,digest) VALUES(?,?,?)",
                (key, payload, digest),
            )
        return "result persisted"

    def _reuse_note(self, run_id, name, key, reason):
        with self._connect() as db:
            db.execute(
                "UPDATE nodes SET cache_key=?,reuse_reason=? WHERE run_id=? AND name=?",
                (key, reason, run_id, name),
            )
