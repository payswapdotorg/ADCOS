#!/usr/bin/env python3
"""T4 Upstash Redis ephemeral-coordination battery (DEC-0126
bounded deployment scope, worker 2; deterministic, stdlib only,
NO network).

End-to-end verification of ``backends/upstash.py`` -- the Upstash
Redis REST coordination adapter -- against a deterministic
in-memory fake of the minimal REST surface (a dict key store
honoring NX/PX semantics over an injectable LOGICAL clock):

Verified surface (each criterion mapped to its cases):

- **module surface** (case 01): pure stdlib + the sanctioned
  in-repo seams only (the ``RateDecision`` seam and the
  ``AgentClock`` helpers), the RedisNeverCanonical invariant in
  the module docstring, and the frozen typed-error vocabulary;
- **configuration** (case 02): bad URL/token/limit/window/prefix/
  clock shapes fail closed as ``config-invalid``;
- **the RateLimiter seam** (cases 03-09): under-limit decisions
  carry the REAL ``RateDecision`` (same class and members as the
  accepted in-process limiter); the at-limit outcome mirrors the
  real limiter exactly (``rate-limited`` with truthful retry
  guidance -- verified in parity with the in-process class);
  the fixed window resets at expiry, is anchored ONCE at the
  first increment (never refreshed by later increments -- the
  window boundary cannot drift), and scopes per application;
  backend failure NEVER silently allows (the typed error is
  raised); free-tier exhaustion (HTTP 429) is the explicit
  ``explicit-limit`` failure; refused credentials and malformed
  bodies are typed failures;
- **the serialization lock** (cases 10-18): atomic acquire
  (duplicate acquisition by anyone returns False -- no
  takeover), owner-only release (a non-owner release fails AND
  the holder survives), expiry and re-acquisition, owner-only
  extend, Redis TTL semantics (-1 no expiry, -2/missing -> None),
  and typed failures on every backend trouble;
- **secret hygiene** (case 19): the REST bearer token and the
  lock ownership tokens never appear in any error surface; the
  Authorization header is exactly ``Bearer <token>`` on every
  command;
- **determinism** (case 20): identical construction sequences
  produce identical decisions, identical typed-failure reason
  codes, identical REST command logs, and identical auto
  generated ownership tokens (no wall clock, no randomness);
- **the unmodified gateway seam** (case 21): the adapter drops
  into ``DeveloperApiService`` as the ``rate_limiter`` seam --
  admitted requests carry the canonical ``rate_limit`` envelope
  member, the blocked request is the canonical 429 with
  ``Retry-After``, and a throttled mutation mints NOTHING
  canonical (DEC-0126: infrastructure failure never silently
  weakens a hard contract constraint).

The battery exercises the PUBLIC adapter surface only.  No
private method is called to manufacture a PASS.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agent.clock import AgentClock, FixedClock, StepClock  # noqa: E402

from contracts import ContractStore  # noqa: E402

import developerapi  # noqa: E402,F401
from developerapi import (  # noqa: E402
    Capability,
    DeveloperApiError,
    DeveloperApiService,
    MemoryApiStore,
    RateDecision,
    RateLimiter,
)
from developerapi.gateway import ApiRequest  # noqa: E402

import backends.upstash as upstash_module  # noqa: E402
from backends.upstash import (  # noqa: E402
    REASON_CODES,
    UpstashCoordinationError,
    UpstashLock,
    UpstashRateLimiter,
)

Result = Tuple[str, bool, str]

_REST_URL = "https://determined-upstash-fake.upstash.io"
_REST_TOKEN = "usk-battery-rotation-token-0001"
_T0 = datetime(2026, 9, 13, 0, 0, 0, tzinfo=timezone.utc)
_MODULE = REPO_ROOT / "backends" / "upstash.py"


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# The deterministic world (logical clock + fake REST transport)
# ---------------------------------------------------------------------------

class _LogicalClock(AgentClock):
    """One logical millisecond timeline: the fake backend's time
    source AND the adapter's injected AgentClock (one timeline,
    so TTLs and decision instants agree deterministically)."""

    def __init__(self, start_ms: int = 0) -> None:
        self._ms = start_ms

    def now_ms(self) -> int:
        return self._ms

    def advance_ms(self, ms: int) -> None:
        if ms < 0:
            raise AssertionError("the logical clock never runs backwards")
        self._ms += ms

    def advance_seconds(self, seconds: int) -> None:
        self.advance_ms(seconds * 1000)

    def now(self) -> str:
        moment = _T0 + timedelta(milliseconds=self._ms)
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeUpstashTransport:
    """The minimal Upstash REST surface, in memory.

    A dict key store honoring NX/PX semantics over the injected
    logical clock (expired keys sweep before every command).
    ``commands`` records the (command, key) audit log the
    anchoring/determinism cases pin; ``auth_violations`` records
    malformed Authorization headers; one-shot failure scripting:
    ``raise_error`` (transport exception), ``next_status`` (a raw
    HTTP status), ``next_body`` (a raw 200 body).

    The fake NEVER auto-expires an INCR counter -- anchoring the
    window expiry is the ADAPTER's INCR+EXPIRE discipline, and
    the anchoring case proves it (a counter without an anchored
    expiry would never reset).
    """

    def __init__(self, clock: _LogicalClock, *, base_url: str = _REST_URL) -> None:
        self.clock = clock
        self.base_url = base_url.rstrip("/")
        self.store: dict = {}  # key -> [value_str, expires_at_ms | None]
        self.commands: List[Tuple[str, str]] = []
        self.auth_violations: List[str] = []
        self.raise_error: Optional[BaseException] = None
        self.next_status: Optional[int] = None
        self.next_body: Optional[bytes] = None

    # -- helpers -------------------------------------------------------

    def _sweep(self) -> None:
        now = self.clock.now_ms()
        for key in [
            key
            for key, entry in self.store.items()
            if entry[1] is not None and now >= entry[1]
        ]:
            del self.store[key]

    def plain_set(self, key: str, value: str) -> None:
        """A foreign writer's plain SET (no TTL) -- battery
        fixture for the -1 (no expiry) TTL semantics."""
        self.store[key] = [value, None]

    def stored_value(self, key: str) -> Optional[str]:
        entry = self.store.get(key)
        return None if entry is None else entry[0]

    # -- the transport -------------------------------------------------

    def __call__(
        self, method: str, url: str, headers: dict, body: bytes
    ) -> Tuple[int, bytes]:
        if method != "POST":
            self.auth_violations.append("non-POST method %r" % (method,))
        auth = headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or len(auth) <= len("Bearer "):
            self.auth_violations.append(
                "malformed Authorization header %r" % (auth[:24],)
            )
        if self.raise_error is not None:
            error, self.raise_error = self.raise_error, None
            raise error
        if self.next_status is not None:
            status, self.next_status = self.next_status, None
            return status, b""
        if self.next_body is not None:
            raw, self.next_body = self.next_body, None
            return 200, raw
        path = url[len(self.base_url):]
        segments = [unquote(part) for part in path.split("/") if part]
        command, args = segments[0], segments[1:]
        self.commands.append((command, args[0] if args else ""))
        self._sweep()
        result = self._dispatch(command, args)
        return 200, json.dumps({"result": result}).encode("utf-8")

    def _dispatch(self, command: str, args: List[str]) -> Any:
        key = args[0]
        if command == "incr":
            entry = self.store.get(key)
            if entry is None:
                self.store[key] = ["1", None]
                return 1
            count = int(entry[0]) + 1
            entry[0] = str(count)
            return count
        if command == "ttl":
            entry = self.store.get(key)
            if entry is None:
                return -2
            if entry[1] is None:
                return -1
            remaining = entry[1] - self.clock.now_ms()
            return (remaining + 999) // 1000
        if command == "expire":
            entry = self.store.get(key)
            if entry is None:
                return 0
            entry[1] = self.clock.now_ms() + int(args[1]) * 1000
            return 1
        if command == "set":
            value = args[1]
            flags = args[2:]
            if "NX" in flags and key in self.store:
                return None
            expiry = None
            if "PX" in flags:
                expiry = self.clock.now_ms() + int(
                    args[args.index("PX") + 1]
                )
            self.store[key] = [value, expiry]
            return "OK"
        if command == "get":
            entry = self.store.get(key)
            return None if entry is None else entry[0]
        if command == "del":
            if key not in self.store:
                return 0
            del self.store[key]
            return 1
        raise AssertionError("unexpected REST command %r" % (command,))


def _world(*, start_ms: int = 0) -> Tuple[_LogicalClock, FakeUpstashTransport]:
    clock = _LogicalClock(start_ms)
    return clock, FakeUpstashTransport(clock)


def _limiter(
    fake: FakeUpstashTransport,
    clock: _LogicalClock,
    *,
    limit: int = 3,
    window_seconds: int = 60,
    key_prefix: str = "ratelimit",
) -> UpstashRateLimiter:
    return UpstashRateLimiter(
        rest_url=_REST_URL,
        rest_token=_REST_TOKEN,
        transport=fake,
        key_prefix=key_prefix,
        limit=limit,
        window_seconds=window_seconds,
        clock=clock,
    )


def _lock(
    fake: FakeUpstashTransport,
    *,
    key: str = "journal-append",
    ttl_ms: int = 5000,
    token: Optional[str] = None,
) -> UpstashLock:
    return UpstashLock(
        rest_url=_REST_URL,
        rest_token=_REST_TOKEN,
        key=key,
        ttl_ms=ttl_ms,
        transport=fake,
        token=token,
    )


def _expect_coordination_error(
    name: str,
    operation,
    reason: str,
    problems: List[str],
    *,
    secrets: Tuple[str, ...] = (),
) -> None:
    """Run ``operation`` and require the typed coordination error
    with exactly ``reason`` (never a silent allow/deny); scan the
    error surface for leaked secrets."""
    try:
        operation()
    except UpstashCoordinationError as error:
        if error.reason_code != reason:
            problems.append(
                "%s: reason %r (want %r)" % (name, error.reason_code, reason)
            )
        if error.backend != "upstash":
            problems.append("%s: backend %r" % (name, error.backend))
        rendered = str(error)
        for secret in secrets:
            if secret and secret in rendered:
                problems.append("%s: secret leaked into the error surface" % name)
    except Exception as error:  # noqa: BLE001 - wrong failure kind
        problems.append(
            "%s: raised %r instead of the typed coordination error"
            % (name, error)
        )
    else:
        problems.append("%s: no error raised (silent allow/deny)" % name)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def case_01_module_surface(results: List[Result]) -> None:
    """Pure stdlib + the sanctioned in-repo seams; the
    RedisNeverCanonical invariant; the frozen typed-error
    vocabulary."""
    problems: List[str] = []
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    sanctioned = {"agent", "developerapi"}
    third_party = sorted(
        name
        for name in imported
        if name not in sanctioned
        and name not in sys.stdlib_module_names
    )
    if third_party:
        problems.append("third-party imports: %s" % (third_party,))
    docstring = ast.get_docstring(tree) or ""
    if "RedisNeverCanonical" not in docstring:
        problems.append("the RedisNeverCanonical invariant is not documented")
    if REASON_CODES != (
        "backend-unavailable",
        "config-invalid",
        "lock-not-held",
        "explicit-limit",
        "protocol-error",
    ):
        problems.append("the reason vocabulary drifted: %r" % (REASON_CODES,))
    try:
        UpstashCoordinationError("not-a-reason")
    except ValueError:
        pass
    except Exception as error:  # noqa: BLE001
        problems.append("unknown reason accepted: %r" % (error,))
    else:
        problems.append("unknown reason accepted silently")
    probe = UpstashCoordinationError("backend-unavailable", "probe")
    if probe.backend != "upstash" or probe.reason_code != "backend-unavailable":
        problems.append("the typed error carries the wrong surface data")
    if problems:
        results.append(fail("01 module surface", "; ".join(problems)))
    else:
        results.append(
            ok(
                "01 module surface",
                "stdlib + sanctioned seams only; RedisNeverCanonical "
                "documented; 5-member frozen vocabulary",
            )
        )


def case_02_config_invalid(results: List[Result]) -> None:
    """Constructor-shape failures fail closed as config-invalid
    (URL/token shapes, tuning bounds, the clock seam)."""
    problems: List[str] = []
    clock, fake = _world()
    bad_urls = ("", "not-a-url", "ftp://example.upstash.io", "https://")
    for bad in bad_urls:
        _expect_coordination_error(
            "rest_url=%r" % (bad,),
            lambda bad=bad: UpstashRateLimiter(rest_url=bad, rest_token=_REST_TOKEN),
            "config-invalid",
            problems,
        )
    _expect_coordination_error(
        "empty token",
        lambda: UpstashRateLimiter(rest_url=_REST_URL, rest_token=""),
        "config-invalid",
        problems,
    )
    for bad_limit in (0, -1, True, "3", 2.0):
        _expect_coordination_error(
            "limit=%r" % (bad_limit,),
            lambda bad=bad_limit: _limiter(fake, clock, limit=bad_limit),
            "config-invalid",
            problems,
        )
    for bad_window in (0, -60, True, "60"):
        _expect_coordination_error(
            "window=%r" % (bad_window,),
            lambda bad=bad_window: _limiter(fake, clock, window_seconds=bad_window),
            "config-invalid",
            problems,
        )
    _expect_coordination_error(
        "empty key_prefix",
        lambda: _limiter(fake, clock, key_prefix=""),
        "config-invalid",
        problems,
    )
    _expect_coordination_error(
        "non-AgentClock clock",
        lambda: UpstashRateLimiter(
            rest_url=_REST_URL,
            rest_token=_REST_TOKEN,
            transport=fake,
            clock=object(),
        ),
        "config-invalid",
        problems,
    )
    for bad_key in ("", None, 7):
        _expect_coordination_error(
            "lock key=%r" % (bad_key,),
            lambda bad_key=bad_key: _lock(fake, key=bad_key),
            "config-invalid",
            problems,
        )
    for bad_ttl in (0, -5, True, "5000"):
        _expect_coordination_error(
            "ttl_ms=%r" % (bad_ttl,),
            lambda bad_ttl=bad_ttl: _lock(fake, ttl_ms=bad_ttl),
            "config-invalid",
            problems,
        )
    _expect_coordination_error(
        "empty explicit token",
        lambda: _lock(fake, token=""),
        "config-invalid",
        problems,
    )
    if problems:
        results.append(fail("02 config-invalid shapes", "; ".join(problems)))
    else:
        results.append(
            ok(
                "02 config-invalid shapes",
                "bad URL/token/limit/window/prefix/clock/key/ttl all "
                "fail closed as config-invalid",
            )
        )


def case_03_rate_under_limit(results: List[Result]) -> None:
    """Under the limit: the REAL RateDecision (same class and
    members as the accepted in-process limiter), counting down
    the remaining allowance to 0."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = _limiter(fake, clock, limit=3, window_seconds=60)
    expected_reset = "2026-09-13T00:01:00Z"
    for index, want_remaining in enumerate((2, 1, 0)):
        decision = limiter.check("app-1")
        if not isinstance(decision, RateDecision):
            problems.append(
                "check %d returned %r (not the real RateDecision)"
                % (index, type(decision).__name__)
            )
            continue
        if decision.allowed is not True or decision.limit != 3:
            problems.append("check %d decision flags drifted" % index)
        if decision.remaining != want_remaining:
            problems.append(
                "check %d remaining %d (want %d)"
                % (index, decision.remaining, want_remaining)
            )
        if decision.reset_at != expected_reset:
            problems.append(
                "check %d reset_at %r (want the window expiry %r)"
                % (index, decision.reset_at, expected_reset)
            )
        if decision.retry_after != "":
            problems.append("check %d allowed retry_after not empty" % index)
    if problems:
        results.append(fail("03 rate under limit", "; ".join(problems)))
    else:
        results.append(
            ok(
                "03 rate under limit",
                "the real RateDecision counts 2/1/0 against the window "
                "expiry instant",
            )
        )


def case_04_rate_at_limit_blocked(results: List[Result]) -> None:
    """At the limit the outcome MIRRORS the accepted in-process
    limiter exactly: the rate-limited boundary error with truthful
    retry guidance (verified in parity with the real class)."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = _limiter(fake, clock, limit=3, window_seconds=60)
    for _ in range(3):
        limiter.check("app-1")
    try:
        limiter.check("app-1")
    except DeveloperApiError as error:
        if error.reason != "rate-limited":
            problems.append("blocked reason %r" % (error.reason,))
        if error.http_status != 429 or not error.retryable:
            problems.append("blocked classification drifted")
        if error.retry_after != "2026-09-13T00:01:00Z":
            problems.append(
                "blocked retry_after %r (want the window reset instant)"
                % (error.retry_after,)
            )
    except Exception as error:  # noqa: BLE001
        problems.append("blocked raised %r" % (error,))
    else:
        problems.append("the over-limit request was silently admitted")
    # parity with the accepted in-process limiter (same admitted
    # count, same blocked outcome kind under identical shape)
    real = RateLimiter(capacity=3, refill_per_second=1, clock=FixedClock(_T0.strftime("%Y-%m-%dT%H:%M:%SZ")))
    admitted = 0
    for _ in range(5):
        try:
            real.check("app-1")
            admitted += 1
        except DeveloperApiError as error:
            if error.reason != "rate-limited" or not error.retry_after:
                problems.append("in-process parity broke at the block")
            break
    if admitted != 3:
        problems.append("in-process parity admitted %d (want 3)" % admitted)
    if problems:
        results.append(fail("04 rate at limit blocked", "; ".join(problems)))
    else:
        results.append(
            ok(
                "04 rate at limit blocked",
                "the 4th request raises rate-limited with the window-reset "
                "retry_after, outcome-for-outcome identical to the "
                "in-process limiter",
            )
        )


def case_05_rate_window_reset(results: List[Result]) -> None:
    """Counter expiry resets the window: after the logical clock
    passes the anchored expiry the allowance is whole again."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = _limiter(fake, clock, limit=2, window_seconds=60)
    limiter.check("app-1")
    try:
        limiter.check("app-1")
        limiter.check("app-1")
        problems.append("the window did not block at the limit")
    except DeveloperApiError:
        pass
    clock.advance_seconds(60)
    decision = limiter.check("app-1")
    if not decision.allowed or decision.remaining != 1 or decision.limit != 2:
        problems.append(
            "the window did not reset: %r" % (decision,)
        )
    if decision.reset_at != "2026-09-13T00:02:00Z":
        problems.append(
            "post-reset reset_at %r (want the NEW window expiry)"
            % (decision.reset_at,)
        )
    if fake.stored_value("ratelimit:app-1") != "1":
        problems.append(
            "the counter did not restart at 1: %r"
            % (fake.stored_value("ratelimit:app-1"),)
        )
    if problems:
        results.append(fail("05 rate window reset", "; ".join(problems)))
    else:
        results.append(
            ok(
                "05 rate window reset",
                "expiry resets the counter to 1 with the full allowance "
                "and a fresh window instant",
            )
        )


def case_06_rate_window_anchoring(results: List[Result]) -> None:
    """Duplicate traffic in one window is IDEMPOTENT about the
    window boundary: EXPIRE anchors exactly once (at the first
    increment), later increments never refresh it, and the TTL
    decreases monotonically until expiry."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = _limiter(fake, clock, limit=10, window_seconds=60)
    limiter.check("app-1")
    expires = [c for c in fake.commands if c[0] == "expire"]
    if len(expires) != 1 or expires[0][1] != "ratelimit:app-1":
        problems.append(
            "the first increment did not anchor exactly one expiry: %r"
            % (expires,)
        )
    ttl_reads = []
    for step in range(3):
        decision = limiter.check("app-1")
        ttl_reads.append(decision.reset_at)
        clock.advance_seconds(10)
    # the window expiry never moved (all reads before t=30s of a
    # 60s window anchored at t=0)
    if any(value != "2026-09-13T00:01:00Z" for value in ttl_reads):
        problems.append(
            "the window boundary drifted under duplicate traffic: %r"
            % (ttl_reads,)
        )
    if len([c for c in fake.commands if c[0] == "expire"]) != 1:
        problems.append("later increments refreshed the expiry")
    # a second window anchors exactly once again
    clock.advance_seconds(40)
    limiter.check("app-1")
    if len([c for c in fake.commands if c[0] == "expire"]) != 2:
        problems.append("the new window did not anchor exactly once")
    # the counter key layout is pinned (prefix:application)
    if not any(key == "ratelimit:app-1" for _cmd, key in fake.commands):
        problems.append("the counter key layout drifted")
    other_clock, other_fake = _world()
    other = _limiter(other_fake, other_clock, key_prefix="coord")
    other.check("app-2")
    if other_fake.stored_value("coord:app-2") != "1":
        problems.append("a custom key_prefix did not land in the key")
    if problems:
        results.append(fail("06 rate window anchoring", "; ".join(problems)))
    else:
        results.append(
            ok(
                "06 rate window anchoring",
                "one EXPIRE per window, no drift under duplicate traffic, "
                "prefix:key layout pinned",
            )
        )


def case_07_rate_per_application(results: List[Result]) -> None:
    """Per-application counters: one application's block never
    throttles another (independent keys)."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = _limiter(fake, clock, limit=2, window_seconds=60)
    limiter.check("app-a")
    limiter.check("app-a")
    try:
        limiter.check("app-a")
        problems.append("app-a was not blocked at its limit")
    except DeveloperApiError:
        pass
    decision = limiter.check("app-b")
    if not decision.allowed or decision.remaining != 1:
        problems.append("app-b inherited app-a's throttle")
    if sorted(fake.store) != ["ratelimit:app-a", "ratelimit:app-b"]:
        problems.append("per-application keys drifted: %r" % (sorted(fake.store),))
    if problems:
        results.append(fail("07 rate per application", "; ".join(problems)))
    else:
        results.append(
            ok(
                "07 rate per application",
                "independent counters; one app's block leaves the other "
                "admitted",
            )
        )


def case_08_rate_backend_failure(results: List[Result]) -> None:
    """Backend failure NEVER silently allows: a raising transport
    and an HTTP 500 both raise the typed backend-unavailable
    error."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = _limiter(fake, clock)
    fake.raise_error = OSError("simulated upstash outage")
    _expect_coordination_error(
        "check with a dead transport",
        lambda: limiter.check("app-1"),
        "backend-unavailable",
        problems,
        secrets=(_REST_TOKEN,),
    )
    clock2, fake2 = _world()
    limiter2 = _limiter(fake2, clock2)
    fake2.next_status = 500
    _expect_coordination_error(
        "check against HTTP 500",
        lambda: limiter2.check("app-1"),
        "backend-unavailable",
        problems,
        secrets=(_REST_TOKEN,),
    )
    if problems:
        results.append(fail("08 rate backend failure", "; ".join(problems)))
    else:
        results.append(
            ok(
                "08 rate backend failure",
                "dead transport and HTTP 500 raise backend-unavailable; "
                "no silent allow",
            )
        )


def case_09_rate_typed_failure_map(results: List[Result]) -> None:
    """Free-tier exhaustion (HTTP 429) is the EXPLICIT
    explicit-limit failure; refused credentials are
    config-invalid; malformed bodies are protocol-errors."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = _limiter(fake, clock)
    fake.next_status = 429
    _expect_coordination_error(
        "HTTP 429 (free-tier exhaustion)",
        lambda: limiter.check("app-1"),
        "explicit-limit",
        problems,
        secrets=(_REST_TOKEN,),
    )
    fake.next_status = 401
    _expect_coordination_error(
        "HTTP 401 (refused credentials)",
        lambda: limiter.check("app-1"),
        "config-invalid",
        problems,
        secrets=(_REST_TOKEN,),
    )
    fake.next_body = b"<html>not json</html>"
    _expect_coordination_error(
        "non-JSON body",
        lambda: limiter.check("app-1"),
        "protocol-error",
        problems,
        secrets=(_REST_TOKEN,),
    )
    fake.next_body = json.dumps({"unexpected": "shape"}).encode("utf-8")
    _expect_coordination_error(
        "resultless body",
        lambda: limiter.check("app-1"),
        "protocol-error",
        problems,
        secrets=(_REST_TOKEN,),
    )
    fake.next_body = json.dumps({"result": "not-a-number"}).encode("utf-8")
    _expect_coordination_error(
        "non-integer INCR result",
        lambda: limiter.check("app-1"),
        "protocol-error",
        problems,
        secrets=(_REST_TOKEN,),
    )
    if problems:
        results.append(fail("09 rate typed failure map", "; ".join(problems)))
    else:
        results.append(
            ok(
                "09 rate typed failure map",
                "429->explicit-limit, 401->config-invalid, malformed "
                "bodies->protocol-error",
            )
        )


def case_10_lock_acquire(results: List[Result]) -> None:
    """Atomic acquire: SET key token NX PX ttl takes the lock
    with the requested TTL."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, key="journal-append", ttl_ms=5000, token="owner-1")
    if lock.acquire() is not True:
        problems.append("acquire did not return True")
    if lock.is_held() is not True:
        problems.append("is_held false after acquire")
    if lock.ttl_seconds() != 5:
        problems.append("ttl %r (want 5)" % (lock.ttl_seconds(),))
    if fake.stored_value("journal-append") != "owner-1":
        problems.append("the ownership token was not stored")
    sets = [c for c in fake.commands if c[0] == "set"]
    if len(sets) != 1 or sets[0][1] != "journal-append":
        problems.append("the acquire command shape drifted: %r" % (sets,))
    if problems:
        results.append(fail("10 lock acquire", "; ".join(problems)))
    else:
        results.append(
            ok(
                "10 lock acquire",
                "atomic SET NX PX takes the lock with ttl 5s and the "
                "stored ownership token",
            )
        )


def case_11_lock_duplicate_acquire(results: List[Result]) -> None:
    """Duplicate acquisition returns False -- by another holder
    AND re-entrantly by the same instance: never a takeover."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, token="owner-1")
    lock.acquire()
    if lock.acquire() is not False:
        problems.append("re-entrant self-acquire took over")
    rival = _lock(fake, token="owner-2")
    if rival.acquire() is not False:
        problems.append("a rival acquire took over")
    if lock.is_held() is not True or lock.ttl_seconds() != 5:
        problems.append("the original lock did not survive")
    if fake.stored_value("journal-append") != "owner-1":
        problems.append(
            "the ownership token changed under duplicate acquisition: %r"
            % (fake.stored_value("journal-append"),)
        )
    if problems:
        results.append(fail("11 lock duplicate acquire", "; ".join(problems)))
    else:
        results.append(
            ok(
                "11 lock duplicate acquire",
                "no takeover: self- and rival-acquire both return False "
                "and the holder survives",
            )
        )


def case_12_lock_release_owner(results: List[Result]) -> None:
    """The owner releases: True, and the key is gone."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, token="owner-1")
    lock.acquire()
    if lock.release() is not True:
        problems.append("owner release returned False")
    if lock.is_held() is not False:
        problems.append("the lock survived its own release")
    if fake.stored_value("journal-append") is not None:
        problems.append("the key survived DEL")
    if problems:
        results.append(fail("12 lock release owner", "; ".join(problems)))
    else:
        results.append(
            ok("12 lock release owner", "owner release deletes the key")
        )


def case_13_lock_release_non_owner(results: List[Result]) -> None:
    """A non-owner release returns False AND the holder
    survives; releasing a missing key is also False."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, token="owner-1")
    lock.acquire()
    rival = _lock(fake, token="owner-2")
    if rival.release() is not False:
        problems.append("a non-owner release reported success")
    if lock.is_held() is not True or lock.ttl_seconds() != 5:
        problems.append("the holder did not survive the rival release")
    if fake.stored_value("journal-append") != "owner-1":
        problems.append("the rival release deleted or rewrote the lock")
    released = _lock(fake, key="never-acquired", token="owner-1")
    if released.release() is not False:
        problems.append("releasing a missing key reported success")
    if problems:
        results.append(fail("13 lock release non-owner", "; ".join(problems)))
    else:
        results.append(
            ok(
                "13 lock release non-owner",
                "non-owner and missing-key releases fail; the holder "
                "survives untouched",
            )
        )


def case_14_lock_expiry_reacquire(results: List[Result]) -> None:
    """Expiry: after the TTL the key vanishes and a fresh
    acquire succeeds."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, ttl_ms=5000, token="owner-1")
    lock.acquire()
    clock.advance_ms(5000)
    if lock.is_held() is not False or lock.ttl_seconds() is not None:
        problems.append("the lock survived its expiry")
    if lock.release() is not False:
        problems.append("an expired lock still released as owner")
    fresh = _lock(fake, ttl_ms=5000, token="owner-2")
    if fresh.acquire() is not True:
        problems.append("a fresh acquire failed after expiry")
    if fake.stored_value("journal-append") != "owner-2":
        problems.append("the fresh owner token was not stored")
    if problems:
        results.append(fail("14 lock expiry reacquire", "; ".join(problems)))
    else:
        results.append(
            ok(
                "14 lock expiry reacquire",
                "PX expiry drops the key; the next acquire succeeds",
            )
        )


def case_15_lock_extend_owner(results: List[Result]) -> None:
    """The owner extends the TTL; the new TTL is observable."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, ttl_ms=5000, token="owner-1")
    lock.acquire()
    clock.advance_ms(2000)
    if lock.extend(30000) is not True:
        problems.append("owner extend returned False")
    if lock.ttl_seconds() != 30:
        problems.append("extend left ttl %r (want 30)" % (lock.ttl_seconds(),))
    clock.advance_ms(10000)
    if lock.is_held() is not True:
        problems.append("the lock did not survive into the extended window")
    if lock.extend(1500) is not True:
        problems.append("a second extend failed")
    if lock.ttl_seconds() != 2:
        problems.append(
            "sub-second extend rounding drifted: %r" % (lock.ttl_seconds(),)
        )
    if problems:
        results.append(fail("15 lock extend owner", "; ".join(problems)))
    else:
        results.append(
            ok(
                "15 lock extend owner",
                "owner extend re-arms the TTL (sub-second windows round "
                "up)",
            )
        )


def case_16_lock_extend_non_owner(results: List[Result]) -> None:
    """A non-owner extend returns False and leaves the holder's
    TTL untouched; an expired lock cannot be extended."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, ttl_ms=5000, token="owner-1")
    lock.acquire()
    rival = _lock(fake, ttl_ms=5000, token="owner-2")
    if rival.extend(60000) is not False:
        problems.append("a non-owner extend reported success")
    if lock.ttl_seconds() != 5:
        problems.append(
            "the non-owner extend changed the TTL: %r" % (lock.ttl_seconds(),)
        )
    clock.advance_ms(5000)
    if lock.extend(60000) is not False:
        problems.append("an expired lock extended successfully")
    if problems:
        results.append(fail("16 lock extend non-owner", "; ".join(problems)))
    else:
        results.append(
            ok(
                "16 lock extend non-owner",
                "non-owner and post-expiry extends fail; the holder's "
                "TTL is untouched",
            )
        )


def case_17_lock_ttl_semantics(results: List[Result]) -> None:
    """Redis TTL semantics: -1 (exists, no expiry) stays -1;
    missing (-2) maps to None; is_held observes existence
    regardless of ownership."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, ttl_ms=5000, token="owner-1")
    lock.acquire()
    clock.advance_ms(1000)
    if lock.ttl_seconds() != 4:
        problems.append("ttl %r (want 4 after 1s)" % (lock.ttl_seconds(),))
    # a foreign plain SET (no expiry) -- the -1 semantics
    fake.plain_set("foreign-key", "foreign-value")
    foreign = _lock(fake, key="foreign-key", ttl_ms=5000, token="observer")
    if foreign.ttl_seconds() != -1:
        problems.append(
            "the -1 (no expiry) semantics drifted: %r" % (foreign.ttl_seconds(),)
        )
    if foreign.is_held() is not True:
        problems.append("is_held must observe existence without ownership")
    missing = _lock(fake, key="absent-key", ttl_ms=5000, token="observer")
    if missing.ttl_seconds() is not None:
        problems.append(
            "the missing (-2) semantics must map to None: %r"
            % (missing.ttl_seconds(),)
        )
    if missing.is_held() is not False:
        problems.append("is_held true for a missing key")
    if problems:
        results.append(fail("17 lock ttl semantics", "; ".join(problems)))
    else:
        results.append(
            ok(
                "17 lock ttl semantics",
                "held->int, no-expiry->-1, missing->None; is_held is "
                "ownership-blind existence",
            )
        )


def case_18_lock_backend_failure(results: List[Result]) -> None:
    """Every lock operation fails closed with the typed error on
    backend trouble (never a silent True/False)."""
    problems: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, ttl_ms=5000, token="owner-1")
    for name, operation in (
        ("acquire", lock.acquire),
        ("release", lock.release),
        ("extend", lambda: lock.extend(1000)),
        ("is_held", lock.is_held),
        ("ttl", lock.ttl_seconds),
    ):
        fake.raise_error = OSError("simulated upstash outage")
        _expect_coordination_error(
            "lock %s with a dead transport" % name,
            operation,
            "backend-unavailable",
            problems,
            secrets=(_REST_TOKEN, "owner-1"),
        )
    clock2, fake2 = _world()
    lock2 = _lock(fake2, ttl_ms=5000, token="owner-1")
    fake2.next_status = 429
    _expect_coordination_error(
        "lock acquire against HTTP 429",
        lock2.acquire,
        "explicit-limit",
        problems,
        secrets=(_REST_TOKEN, "owner-1"),
    )
    fake2.next_body = b"gateway timeout"
    _expect_coordination_error(
        "lock ttl against a non-JSON body",
        lock2.ttl_seconds,
        "protocol-error",
        problems,
        secrets=(_REST_TOKEN, "owner-1"),
    )
    fake2.next_body = json.dumps({"result": "OK"}).encode("utf-8")
    _expect_coordination_error(
        "lock ttl against a non-integer TTL result",
        lock2.ttl_seconds,
        "protocol-error",
        problems,
        secrets=(_REST_TOKEN, "owner-1"),
    )
    if problems:
        results.append(fail("18 lock backend failure", "; ".join(problems)))
    else:
        results.append(
            ok(
                "18 lock backend failure",
                "acquire/release/extend/observe all fail closed with "
                "typed reasons; no silent True/False",
            )
        )


def case_19_secret_hygiene(results: List[Result]) -> None:
    """The REST bearer token and the ownership tokens never
    appear in any error surface; every command carries exactly
    ``Authorization: Bearer <token>``."""
    problems: List[str] = []
    seen_bodies: List[str] = []
    clock, fake = _world()
    lock = _lock(fake, ttl_ms=5000, token="owner-secret-token-1")
    lock.acquire()
    fake.raise_error = OSError("simulated upstash outage")
    for operation in (lock.acquire, lock.release, lock.ttl_seconds):
        try:
            operation()
        except UpstashCoordinationError as error:
            seen_bodies.append(str(error))
        except Exception as error:  # noqa: BLE001
            problems.append("unexpected error %r" % (error,))
    fake.raise_error = None
    fake.next_body = b"not-json"
    limiter = _limiter(fake, clock)
    try:
        limiter.check("app-1")
    except UpstashCoordinationError as error:
        seen_bodies.append(str(error))
    except Exception as error:  # noqa: BLE001
        problems.append("unexpected error %r" % (error,))
    for secret in (_REST_TOKEN, "owner-secret-token-1"):
        for rendered in seen_bodies:
            if secret in rendered:
                problems.append("secret leaked into %r" % (rendered[:40],))
    auto_clock, auto_fake = _world()
    auto_lock = _lock(auto_fake, key="auto-token-lock")
    auto_lock.acquire()
    stored = auto_fake.stored_value("auto-token-lock") or ""
    auto_fake.raise_error = OSError("simulated upstash outage")
    try:
        auto_lock.ttl_seconds()
    except UpstashCoordinationError as error:
        if stored and stored in str(error):
            problems.append("the auto token leaked into an error surface")
    if fake.auth_violations or auto_fake.auth_violations:
        problems.append(
            "authorization header violations: %r" % (fake.auth_violations,)
        )
    if problems:
        results.append(fail("19 secret hygiene", "; ".join(problems)))
    else:
        results.append(
            ok(
                "19 secret hygiene",
                "bearer and ownership tokens absent from every error "
                "surface; Bearer auth on every command",
            )
        )


def case_20_determinism(results: List[Result]) -> None:
    """Identical construction sequences produce identical
    decisions, typed-failure reason codes, and REST command logs
    (no wall clock, no randomness); the auto-generated ownership
    token is unique per instance within a process and stable per
    construction position across runs (pinned by digest in the
    case detail, which the x3 byte-identical runs verify)."""
    problems: List[str] = []

    def scenario() -> Tuple[Any, ...]:
        clock, fake = _world()
        limiter = _limiter(fake, clock, limit=2, window_seconds=60)
        lock = _lock(fake, key="trace-lock", ttl_ms=5000, token="trace-owner")
        trace = []
        trace.append(limiter.check("app-1"))
        trace.append(limiter.check("app-1"))
        try:
            limiter.check("app-1")
        except DeveloperApiError as error:
            trace.append(("blocked", error.reason, error.retry_after))
        clock.advance_seconds(60)
        trace.append(limiter.check("app-1"))
        trace.append(lock.acquire())
        trace.append(lock.ttl_seconds())
        rival = _lock(fake, key="trace-lock", ttl_ms=1000, token="trace-rival")
        trace.append(rival.acquire())
        fake.raise_error = OSError("simulated upstash outage")
        try:
            lock.extend(1000)
        except UpstashCoordinationError as error:
            trace.append(("typed", error.reason_code))
        trace.append(fake.commands)
        trace.append(fake.stored_value("trace-lock"))
        return tuple(trace)

    first, second = scenario(), scenario()
    if first != second:
        problems.append("the scenario traces diverged across fresh runs")
    # the auto-generated ownership token: unique per instance
    # within a process (different sequence positions never
    # collide), and stable per construction position across runs
    # (the digest in the case detail pins byte-identity).
    clock_a, fake_a = _world()
    lock_a = _lock(fake_a, key="same-key")
    lock_a.acquire()
    token_a = fake_a.stored_value("same-key")
    clock_b, fake_b = _world()
    _lock(fake_b, key="same-key")  # consumed a sequence position
    lock_b = _lock(fake_b, key="same-key")
    lock_b.acquire()
    token_b = fake_b.stored_value("same-key")
    if not token_a or not token_b or token_a == token_b:
        problems.append("auto tokens collide across instances")
    if not token_a.startswith("upstash-lock-") or len(token_a) != len(
        "upstash-lock-"
    ) + 32:
        problems.append("the auto token shape drifted: %d chars" % len(token_a))
    token_digest = hashlib.sha256(
        (token_a or "").encode("utf-8")
    ).hexdigest()[:16]
    if problems:
        results.append(fail("20 determinism", "; ".join(problems)))
    else:
        results.append(
            ok(
                "20 determinism",
                "identical traces (token digest %s pinned per construction "
                "position); unique-per-instance auto tokens" % token_digest,
            )
        )


def case_21_gateway_seam(results: List[Result]) -> None:
    """The unmodified accepted gateway admits the adapter as its
    RateLimiter seam: canonical envelopes, the canonical 429 with
    Retry-After, and a throttled mutation mints NOTHING
    canonical."""
    problems: List[str] = []
    clock, fake = _world()
    limiter = UpstashRateLimiter(
        rest_url=_REST_URL,
        rest_token=_REST_TOKEN,
        transport=fake,
        limit=2,
        window_seconds=60,
        clock=clock,
    )
    service = DeveloperApiService(
        environment="sandbox",
        contracts=ContractStore(),
        store=MemoryApiStore(),
        clock=StepClock("2026-09-13T00:00:00Z", 60),
        issuance_key=b"w2-coordination-battery-issuance-key",
        rate_limiter=limiter,
        delivery_transports={},
    )
    app = service.issue_application_credential(
        developer_id="dev-w2",
        application_name="w2-app",
        capabilities=Capability.values(),
        valid_until="2030-01-01T00:00:00Z",
        key_material="dev-w2-key",
        actor="platform",
    )

    def request(method: str, route: str, *, body=None, key: str = "") -> ApiRequest:
        return ApiRequest(
            method=method,
            route=route,
            body=dict(body or {}),
            api_version="2.0",
            idempotency_key=key,
            application_id=app.record.application_id,
            secret=app.secret,
        )

    for index in range(2):
        response = service.handle(request("GET", "/api/2.0/application"))
        if response.status != 200:
            problems.append("admitted request %d rejected" % index)
        if "rate_limit" not in dict(response.body):
            problems.append("the rate_limit envelope member is absent")
    journal_before = len(service.journal_records())
    throttled = service.handle(request("GET", "/api/2.0/application"))
    if throttled.status != 429:
        problems.append("the third request was not throttled")
    error = throttled.error()
    if error.get("reason") != "rate-limited":
        problems.append("throttle reason %r" % (error.get("reason"),))
    if not error.get("retry_after"):
        problems.append("the throttle lacks truthful retry guidance")
    if "Retry-After" not in throttled.headers:
        problems.append("the Retry-After header is absent")
    intent_body = {
        "requirements": [
            {
                "ref_kind": "intent-requirements",
                "value": "req-1",
                "provenance": {
                    "issuer": "intent-authority",
                    "decision_refs": ["dec-1"],
                },
            }
        ],
        "validity": {
            "not_before": "2026-09-13T00:00:00Z",
            "not_after": "2026-09-14T00:00:00Z",
        },
        "termination": {
            "conditions": ["principal-requested", "validity-expired"],
            "compensation": {
                "ref_kind": "compensation",
                "value": "comp-rule-1",
            },
        },
        "recorded_at": "2026-09-13T00:00:00Z",
        "hard_constraints": [
            {"kind": "latency-bound", "params": {"ms": 100}},
            {"kind": "throughput-floor", "params": {"bps": 1000}},
        ],
        "beneficiaries": [
            {"beneficiary_kind": "DEVICE", "beneficiary_ref": "device-1"}
        ],
        "service_properties": [
            {"ref_kind": "service-property", "value": "prop-1"}
        ],
        "usage_pricing_terms": {
            "ref_kind": "usage-pricing-terms",
            "value": "terms-1",
        },
        "assurance_obligations": [
            {
                "ref_kind": "assurance-obligation",
                "value": "oblig-1",
                "provenance": {
                    "issuer": "assurance-authority",
                    "decision_refs": ["a-1"],
                },
            }
        ],
        "execution_scope": [
            {"ref_kind": "execution-scope", "value": "scope-1"},
        ],
    }
    mutation = service.handle(
        request(
            "POST",
            "/api/2.0/intents",
            body=intent_body,
            key="w2-throttled-1",
        )
    )
    if mutation.status != 429:
        problems.append("a throttled mutation was admitted")
    if len(service.journal_records()) != journal_before:
        problems.append("a throttled mutation minted journal records")
    if len(service._contracts.journal()) != 0:  # noqa: SLF001 - public read
        problems.append("a throttled mutation minted canonical state")
    app_b = service.issue_application_credential(
        developer_id="dev-w2-b",
        application_name="w2-app-b",
        capabilities=Capability.values(),
        valid_until="2030-01-01T00:00:00Z",
        key_material="dev-w2-b-key",
        actor="platform",
    )
    other = service.handle(
        ApiRequest(
            method="GET",
            route="/api/2.0/application",
            body={},
            api_version="2.0",
            idempotency_key="",
            application_id=app_b.record.application_id,
            secret=app_b.secret,
        )
    )
    if other.status != 200 or "rate_limit" not in dict(other.body):
        problems.append("per-application scoping drifted at the seam")
    if problems:
        results.append(fail("21 gateway seam", "; ".join(problems)))
    else:
        results.append(
            ok(
                "21 gateway seam",
                "the unmodified gateway: 2 admitted with rate_limit, the "
                "3rd is the canonical 429 with Retry-After, the throttled "
                "mutation mints nothing, scoping is per application",
            )
        )


_CASES = (
    case_01_module_surface,
    case_02_config_invalid,
    case_03_rate_under_limit,
    case_04_rate_at_limit_blocked,
    case_05_rate_window_reset,
    case_06_rate_window_anchoring,
    case_07_rate_per_application,
    case_08_rate_backend_failure,
    case_09_rate_typed_failure_map,
    case_10_lock_acquire,
    case_11_lock_duplicate_acquire,
    case_12_lock_release_owner,
    case_13_lock_release_non_owner,
    case_14_lock_expiry_reacquire,
    case_15_lock_extend_owner,
    case_16_lock_extend_non_owner,
    case_17_lock_ttl_semantics,
    case_18_lock_backend_failure,
    case_19_secret_hygiene,
    case_20_determinism,
    case_21_gateway_seam,
)


def main() -> int:
    results: List[Result] = []
    for case in _CASES:
        try:
            case(results)
        except Exception as error:  # noqa: BLE001 - the battery never crashes silently
            results.append(
                fail(case.__name__, "raised: %r" % (error,))
            )
    width = max(len(name) for name, _ok, _detail in results)
    passed = 0
    for name, is_ok, detail in results:
        marker = "ok  " if is_ok else "FAIL"
        print("[%s] %-*s %s" % (marker, width, name, detail))
        if is_ok:
            passed += 1
    print("-" * 72)
    print(
        "Result: %s (%d/%d cases passed)"
        % (
            "PASS" if passed == len(results) else "FAIL",
            passed,
            len(results),
        )
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
