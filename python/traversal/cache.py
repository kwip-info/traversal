"""Explicit repeat-safe computations and strict JSON result persistence."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Cache:
    """Declare a repeat-safe computation and its code/input/configuration key.

    The caller must change key when anything affecting the result changes.
    All dependencies must also have explicit cache keys for reuse eligibility.
    """

    key: str

    def __post_init__(self):
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("cache key must be a nonempty string")


class ResumeDecisionError(RuntimeError):
    def __init__(self, decisions):
        self.decisions = decisions
        super().__init__("Explicit rerun decisions required for: " + ", ".join(decisions))


def encode(value, max_bytes):
    def check(v, seen):
        if v is None or type(v) in (str, bool, int):
            return
        if type(v) is float and math.isfinite(v):
            return
        if type(v) in (list, dict):
            if id(v) in seen:
                raise ValueError("circular result")
            seen.add(id(v))
            if type(v) is dict:
                if any(type(k) is not str for k in v):
                    raise ValueError("JSON result keys must be strings")
                values = v.values()
            else:
                values = v
            for item in values:
                check(item, seen)
            seen.remove(id(v))
            return
        raise ValueError("result must contain only finite JSON-native values")

    check(value, set())
    payload = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
    if len(payload.encode()) > max_bytes:
        raise ValueError("result exceeds cache byte limit")
    return payload, hashlib.sha256(payload.encode()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
