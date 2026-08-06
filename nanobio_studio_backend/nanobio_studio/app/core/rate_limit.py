"""Where login-attempt counters live, and what happens when that is wrong.

The problem this file exists to stop being silent
-------------------------------------------------
The login limiter counted failures in a Python dictionary. On one process that
is a real control. Behind a load balancer with four workers it is four separate
counters, so five-attempts-then-lockout becomes twenty, and every restart wipes
the memory — an attacker who can cause or wait for a restart has no limit at
all.

The dangerous part was never the weakness. It was that the weakness was
*invisible*: the same code, the same passing tests, the same log lines, and a
control that quietly did a quarter of its job. Documentation does not fix that,
because the deployment that gets it wrong is the one where nobody read the
docstring.

So the backend is now explicit and the mismatch is fatal at startup:

* ``RATE_LIMIT_BACKEND=memory`` (default) — the dictionary, and
  ``APP_INSTANCE_COUNT`` must be 1. Declare more and the application refuses to
  start rather than serving with a limiter that cannot do what it claims.
* ``RATE_LIMIT_BACKEND=redis`` — counters shared across every instance, which
  is what a multi-instance deployment needs.

``verify_rate_limit_configuration()`` runs on startup. A deployment that would
have been quietly wrong is now loudly stopped.

Why fail closed on a *counter*
------------------------------
Refusing to start looks severe for a rate limiter. But the failure mode is an
authentication control that reports itself healthy while permitting several
times the attempts it promises, and the only signal is a successful brute force
nobody attributes to it. A refusal at startup is read by the person deploying;
a diluted lockout is read by nobody.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Protocol

__all__ = [
    "RateLimitBackend", "MemoryRateLimitBackend", "RedisRateLimitBackend",
    "RateLimitMisconfigured", "build_backend", "describe_backend",
    "verify_rate_limit_configuration",
]


class RateLimitMisconfigured(RuntimeError):
    """The configured backend cannot deliver the limit that is claimed."""


@dataclass
class _Attempts:
    failures: list[float] = field(default_factory=list)
    locked_until: float | None = None


class RateLimitBackend(Protocol):
    """What the limiter needs, small enough that Redis satisfies it honestly.

    Deliberately not a general-purpose cache interface. Every method here maps
    to one operation Redis performs atomically, so the Redis implementation is
    not the memory one with network calls bolted on — it is the same policy
    expressed in operations that are correct when several processes run them at
    once.
    """

    #: True when counters survive a restart and are shared between processes.
    shared: bool

    def locked_for(self, key: str) -> float: ...

    def record_failure(self, key: str, *, window_s: float, threshold: int,
                       lockout_s: float) -> bool: ...

    def reset(self, key: str) -> None: ...

    def clear(self) -> None: ...

    def health(self) -> dict: ...


class MemoryRateLimitBackend:
    """Per-process counters. Correct for exactly one instance.

    The lock matters even here: FastAPI serves concurrently, and two requests
    for the same account arriving together could otherwise both read four
    failures and both write five, spending two attempts on one slot.
    """

    shared = False

    def __init__(self) -> None:
        self._buckets: dict[str, _Attempts] = {}
        self._lock = threading.Lock()

    def locked_for(self, key: str) -> float:
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket or not bucket.locked_until:
                return 0.0
            return max(0.0, bucket.locked_until - time.monotonic())

    def record_failure(self, key: str, *, window_s: float, threshold: int,
                       lockout_s: float) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, _Attempts())
            bucket.failures = [t for t in bucket.failures
                               if now - t < window_s]
            bucket.failures.append(now)
            if len(bucket.failures) >= threshold:
                bucket.locked_until = now + lockout_s
                bucket.failures.clear()
                return True
            return False

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def health(self) -> dict:
        with self._lock:
            live = sum(1 for b in self._buckets.values()
                       if b.locked_until or b.failures)
        return {
            "backend": "memory",
            "shared": False,
            "available": True,
            "tracked_keys": live,
            "limitation": (
                "counters are per-process and are lost on restart; correct "
                "only for a single instance"),
        }


class RedisRateLimitBackend:
    """Counters shared across instances, in Redis.

    Two keys per bucket: a lock key whose TTL *is* the remaining lockout, and a
    failure counter whose TTL is the rolling window. Expiry does the forgetting,
    so there is nothing to sweep and no way for a stale entry to keep somebody
    locked out past the window.

    ``INCR`` then ``EXPIRE`` is a pipeline rather than two round trips, and the
    window is set only on the first failure — refreshing it on every attempt
    would let a slow, steady attacker hold the window open indefinitely.
    """

    shared = True

    def __init__(self, client, *, prefix: str = "nanobio:ratelimit:") -> None:
        self._redis = client
        self._prefix = prefix

    def _lock_key(self, key: str) -> str:
        return f"{self._prefix}lock:{key}"

    def _count_key(self, key: str) -> str:
        return f"{self._prefix}fail:{key}"

    def locked_for(self, key: str) -> float:
        ttl = self._redis.ttl(self._lock_key(key))
        return float(ttl) if ttl and ttl > 0 else 0.0

    def record_failure(self, key: str, *, window_s: float, threshold: int,
                       lockout_s: float) -> bool:
        count_key = self._count_key(key)
        pipe = self._redis.pipeline()
        pipe.incr(count_key)
        # NX: only when no expiry is set, i.e. only on the first failure of a
        # window. Without it the window slides forward on every attempt and
        # never closes.
        pipe.expire(count_key, int(window_s), nx=True)
        count = pipe.execute()[0]

        if int(count) >= threshold:
            self._redis.setex(self._lock_key(key), int(lockout_s), "1")
            self._redis.delete(count_key)
            return True
        return False

    def reset(self, key: str) -> None:
        self._redis.delete(self._count_key(key), self._lock_key(key))

    def clear(self) -> None:
        """Only this limiter's keys. Never ``FLUSHDB``.

        A test helper that emptied a shared Redis would take the rest of the
        deployment's data with it the first time somebody pointed it at
        something other than a scratch instance.
        """
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match=f"{self._prefix}*",
                                            count=500)
            if keys:
                self._redis.delete(*keys)
            if cursor == 0:
                break

    def health(self) -> dict:
        try:
            self._redis.ping()
            available = True
            error = None
        except Exception as exc:  # noqa: BLE001
            available = False
            # The class name, not the message: a connection error can carry the
            # host, port and sometimes the password from the URL.
            error = type(exc).__name__
        return {"backend": "redis", "shared": True, "available": available,
                "error": error}


def build_backend(*, kind: str, redis_url: str | None):
    """Construct the configured backend, or say precisely what is missing."""
    kind = (kind or "memory").strip().lower()

    if kind == "memory":
        return MemoryRateLimitBackend()

    if kind == "redis":
        if not redis_url:
            raise RateLimitMisconfigured(
                "RATE_LIMIT_BACKEND=redis needs RATE_LIMIT_REDIS_URL. Set it "
                "to the shared instance every application process can reach.")
        try:
            import redis  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RateLimitMisconfigured(
                "RATE_LIMIT_BACKEND=redis needs the 'redis' package "
                "(pip install redis).") from exc
        client = redis.Redis.from_url(redis_url, decode_responses=True,
                                      socket_connect_timeout=5)
        return RedisRateLimitBackend(client)

    raise RateLimitMisconfigured(
        f"unknown RATE_LIMIT_BACKEND {kind!r}; expected 'memory' or 'redis'")


def verify_rate_limit_configuration(*, kind: str, instance_count: int,
                                    backend) -> dict:
    """Startup gate. Raises when the backend cannot deliver the claimed limit.

    Returns a description for the startup log when the configuration is sound,
    so the operator sees which limiter is running without having to infer it.
    """
    kind = (kind or "memory").strip().lower()
    instance_count = max(1, int(instance_count or 1))

    if instance_count > 1 and not getattr(backend, "shared", False):
        raise RateLimitMisconfigured(
            f"APP_INSTANCE_COUNT={instance_count} with "
            f"RATE_LIMIT_BACKEND={kind}: login attempts would be counted "
            f"separately by each instance, so the configured limit would be "
            f"multiplied by {instance_count} in practice. Set "
            f"RATE_LIMIT_BACKEND=redis with RATE_LIMIT_REDIS_URL, or run a "
            f"single instance.")

    health = backend.health()
    if kind == "redis" and not health.get("available"):
        raise RateLimitMisconfigured(
            "RATE_LIMIT_BACKEND=redis is configured but the instance is not "
            f"reachable ({health.get('error')}). Starting would leave login "
            "attempts uncounted.")

    return {"backend": kind, "shared": bool(getattr(backend, "shared", False)),
            "instances": instance_count, **health}


def describe_backend(backend) -> dict:
    return backend.health()
