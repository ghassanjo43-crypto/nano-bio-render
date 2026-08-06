"""The login limiter's counter store, and the startup gate over it.

What was wrong before
---------------------
The limiter counted in a per-process dictionary and said so in a docstring.
That is a control whose weakness is invisible at runtime: four workers means
four counters, so "five attempts then lockout" becomes twenty, the application
reports itself healthy, and the only evidence is a brute force nobody
attributes to the limiter.

These tests pin two things. The policy is unchanged whichever store is used —
so swapping to Redis cannot quietly change the threshold — and a deployment
that declares more instances than its store can serve **fails to start**.

The Redis tests run against a fake that implements the handful of commands used
(``incr``, ``expire``, ``setex``, ``ttl``, ``delete``, ``scan``, ``pipeline``,
``ping``) with the semantics that matter, including expiry. A real Redis in the
normal test suite would make the suite depend on a service being up, which the
brief rules out; the fake makes the *logic* testable, and the startup gate
below is what catches a real instance being unreachable.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "nanobio_studio_backend"
for _p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from nanobio_studio.app.core.rate_limit import (  # noqa: E402
    MemoryRateLimitBackend, RateLimitMisconfigured, RedisRateLimitBackend,
    build_backend, verify_rate_limit_configuration,
)
from nanobio_studio.app.services.auth_service import (  # noqa: E402
    LOCKOUT_WINDOW, MAX_FAILED_ATTEMPTS, AuthError, LoginRateLimiter,
)


# ===========================================================================
# A fake Redis, honest about the commands the backend actually uses
# ===========================================================================

class FakeRedis:
    """Enough Redis to test the backend, with a controllable clock.

    Expiry is evaluated on read against an injectable clock rather than by
    sleeping — the brief requires time-based tests to use a clock, and a test
    that sleeps for a fifteen-minute lockout is a test nobody runs.
    """

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expiry: dict[str, float] = {}
        self.now = 1000.0
        self.reachable = True

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def _sweep(self) -> None:
        for key in [k for k, at in self.expiry.items() if at <= self.now]:
            self.values.pop(key, None)
            self.expiry.pop(key, None)

    def ping(self):
        if not self.reachable:
            raise ConnectionError("fake redis is down")
        return True

    def incr(self, key):
        self._sweep()
        self.values[key] = str(int(self.values.get(key, "0")) + 1)
        return int(self.values[key])

    def expire(self, key, seconds, nx=False):
        self._sweep()
        if nx and key in self.expiry:
            return False
        self.expiry[key] = self.now + seconds
        return True

    def setex(self, key, seconds, value):
        self.values[key] = value
        self.expiry[key] = self.now + seconds

    def ttl(self, key):
        self._sweep()
        if key not in self.values:
            return -2
        if key not in self.expiry:
            return -1
        return int(self.expiry[key] - self.now)

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.expiry.pop(key, None)

    def scan(self, cursor, match="*", count=100):
        self._sweep()
        prefix = match.rstrip("*")
        return 0, [k for k in list(self.values) if k.startswith(prefix)]

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis):
        self._redis = redis
        self._queued = []

    def incr(self, key):
        self._queued.append(("incr", (key,), {}))
        return self

    def expire(self, key, seconds, nx=False):
        self._queued.append(("expire", (key, seconds), {"nx": nx}))
        return self

    def execute(self):
        results = []
        for name, args, kwargs in self._queued:
            results.append(getattr(self._redis, name)(*args, **kwargs))
        self._queued.clear()
        return results


@pytest.fixture
def fake_redis():
    return FakeRedis()


# ===========================================================================
# 1. Both stores implement the same policy
# ===========================================================================

class TestThePolicyIsIdenticalAcrossStores:
    """The threshold must come from the policy, never from the store.

    A Redis backend that locked out after three attempts, or after seven, would
    be a change to an authentication control disguised as an infrastructure
    change.
    """

    def _backends(self, fake_redis):
        return [("memory", MemoryRateLimitBackend()),
                ("redis", RedisRateLimitBackend(fake_redis))]

    def test_lockout_happens_on_exactly_the_configured_attempt(self, fake_redis):
        for name, backend in self._backends(fake_redis):
            limiter = LoginRateLimiter(backend)
            for attempt in range(1, MAX_FAILED_ATTEMPTS):
                assert limiter.record_failure("someone", "10.0.0.1") is False, (
                    f"{name} locked out early, on attempt {attempt}")
                limiter.check("someone", "10.0.0.1")  # must not raise
            assert limiter.record_failure("someone", "10.0.0.1") is True, (
                f"{name} did not lock out on attempt {MAX_FAILED_ATTEMPTS}")

            with pytest.raises(AuthError) as caught:
                limiter.check("someone", "10.0.0.1")
            assert caught.value.status_code == 429
            assert caught.value.retry_after > 0

    def test_a_successful_sign_in_clears_the_counter(self, fake_redis):
        """Positive control: the limiter forgets, so a user who mistypes twice
        and then succeeds is not four failures away from a lockout forever."""
        for name, backend in self._backends(fake_redis):
            limiter = LoginRateLimiter(backend)
            limiter.record_failure("someone", "10.0.0.1")
            limiter.record_failure("someone", "10.0.0.1")
            limiter.reset("someone", "10.0.0.1")

            for _ in range(MAX_FAILED_ATTEMPTS - 1):
                assert limiter.record_failure("someone", "10.0.0.1") is False, (
                    f"{name} did not clear the counter on success")

    def test_the_lock_expires_rather_than_being_permanent(self, fake_redis):
        """No permanent lockout — that is a denial-of-service tool aimed at a
        named person. Driven by the fake clock, not by sleeping."""
        backend = RedisRateLimitBackend(fake_redis)
        limiter = LoginRateLimiter(backend)
        for _ in range(MAX_FAILED_ATTEMPTS):
            limiter.record_failure("someone", "10.0.0.1")

        with pytest.raises(AuthError):
            limiter.check("someone", "10.0.0.1")

        fake_redis.advance(LOCKOUT_WINDOW.total_seconds() + 1)
        limiter.check("someone", "10.0.0.1")  # forgotten; must not raise

    def test_the_key_is_account_and_address_together(self, fake_redis):
        """Keying on the account alone would let anybody who knows a username
        lock its owner out from anywhere."""
        for name, backend in self._backends(fake_redis):
            limiter = LoginRateLimiter(backend)
            for _ in range(MAX_FAILED_ATTEMPTS):
                limiter.record_failure("victim", "203.0.113.9")

            with pytest.raises(AuthError):
                limiter.check("victim", "203.0.113.9")

            # The same account from its own address is unaffected.
            limiter.check("victim", "10.0.0.1")


# ===========================================================================
# 2. Redis-specific behaviour that memory cannot express
# ===========================================================================

class TestRedisBackendSpecifics:

    def test_the_failure_window_does_not_slide_forward_on_every_attempt(
            self, fake_redis):
        """``EXPIRE ... NX`` is the whole point.

        Refreshing the window on each failure would let a slow attacker hold it
        open indefinitely, never reaching the threshold and never being
        forgotten either.
        """
        backend = RedisRateLimitBackend(fake_redis)
        backend.record_failure("k", window_s=900, threshold=5, lockout_s=900)
        first = fake_redis.ttl("nanobio:ratelimit:fail:k")

        fake_redis.advance(100)
        backend.record_failure("k", window_s=900, threshold=5, lockout_s=900)
        second = fake_redis.ttl("nanobio:ratelimit:fail:k")

        assert second < first, (
            "the window was extended by the second failure; it must expire "
            "900s after the FIRST one")

    def test_clear_touches_only_this_limiters_keys(self, fake_redis):
        """A test helper that emptied a shared Redis would take the rest of the
        deployment's data with it."""
        fake_redis.values["someone-elses-key"] = "important"
        backend = RedisRateLimitBackend(fake_redis)
        backend.record_failure("k", window_s=900, threshold=5, lockout_s=900)

        backend.clear()

        assert fake_redis.values.get("someone-elses-key") == "important"
        assert not [k for k in fake_redis.values if k.startswith("nanobio:")]

    def test_health_never_leaks_the_connection_string(self, fake_redis):
        """A Redis connection error can carry the host, port and password."""
        fake_redis.reachable = False
        health = RedisRateLimitBackend(fake_redis).health()

        assert health["available"] is False
        assert health["error"] == "ConnectionError"
        assert "fake redis is down" not in str(health)

    def test_redis_reports_itself_as_shared(self, fake_redis):
        assert RedisRateLimitBackend(fake_redis).shared is True
        assert MemoryRateLimitBackend().shared is False


# ===========================================================================
# 3. The startup gate
# ===========================================================================

class TestStartupRefusesAMisconfiguredLimiter:

    def test_multiple_instances_with_per_process_counters_is_fatal(self):
        """The defect this whole file exists for.

        Four workers with a dictionary each is a limit of twenty, not five,
        while every log line and every test still says five.
        """
        with pytest.raises(RateLimitMisconfigured) as caught:
            verify_rate_limit_configuration(
                kind="memory", instance_count=4,
                backend=MemoryRateLimitBackend())

        message = str(caught.value)
        assert "multiplied by 4" in message
        assert "RATE_LIMIT_BACKEND=redis" in message, (
            "the error must name the fix, not merely the fault")

    def test_a_single_instance_with_memory_counters_is_allowed(self):
        """Positive control: this is the default and it must start."""
        description = verify_rate_limit_configuration(
            kind="memory", instance_count=1, backend=MemoryRateLimitBackend())

        assert description["shared"] is False
        assert description["instances"] == 1
        assert "limitation" in description, (
            "a single instance is allowed, but the limitation must still be "
            "reported in the startup log rather than passing silently")

    def test_multiple_instances_with_redis_is_allowed(self, fake_redis):
        description = verify_rate_limit_configuration(
            kind="redis", instance_count=4,
            backend=RedisRateLimitBackend(fake_redis))

        assert description["shared"] is True
        assert description["instances"] == 4

    def test_an_unreachable_redis_stops_startup(self, fake_redis):
        """Starting anyway would leave login attempts uncounted while the
        configuration claims they are shared."""
        fake_redis.reachable = False
        with pytest.raises(RateLimitMisconfigured, match="not reachable"):
            verify_rate_limit_configuration(
                kind="redis", instance_count=2,
                backend=RedisRateLimitBackend(fake_redis))

    def test_redis_without_a_url_names_the_missing_setting(self):
        with pytest.raises(RateLimitMisconfigured,
                           match="RATE_LIMIT_REDIS_URL"):
            build_backend(kind="redis", redis_url=None)

    def test_an_unknown_backend_is_refused(self):
        with pytest.raises(RateLimitMisconfigured, match="memcached"):
            build_backend(kind="memcached", redis_url=None)

    def test_the_default_configuration_builds_the_memory_backend(self):
        backend = build_backend(kind="memory", redis_url=None)
        assert isinstance(backend, MemoryRateLimitBackend)
        assert backend.health()["limitation"], (
            "the memory backend must always report its limitation, so an "
            "operator reading /health sees it without reading the source")


# ===========================================================================
# 4. Concurrency
# ===========================================================================

class TestConcurrentFailuresAreCountedOnce:

    def test_simultaneous_failures_do_not_share_a_slot(self):
        """FastAPI serves concurrently.

        Two requests for one account arriving together could otherwise both
        read four failures and both write five — spending two attempts on one
        slot, and in the other direction letting an attacker who parallelises
        get more attempts than the threshold allows.
        """
        import threading

        backend = MemoryRateLimitBackend()
        lockouts = []
        barrier = threading.Barrier(20)

        def attempt():
            barrier.wait()
            if backend.record_failure("k", window_s=900, threshold=5,
                                      lockout_s=900):
                lockouts.append(1)

        threads = [threading.Thread(target=attempt) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # 20 failures, threshold 5, counter cleared on each lockout: exactly 4.
        assert len(lockouts) == 4, (
            f"expected 4 lockouts from 20 concurrent failures, got "
            f"{len(lockouts)} — the counter is not atomic")
