"""Upstash Redis REST ephemeral-coordination adapter (DEC-0126
bounded deployment scope, worker 2).

RedisNeverCanonical (the design-mandated invariant, DEC-0126 /
docs/deployment/runtime-inventory.md): this module stores ONLY
ephemeral coordination state -- per-application rate-limit
counters and cross-instance serialization locks.  NO canonical
ADCOS state may live behind this adapter: the ConnectivityContract
journal (ContractStore over durable persistence) remains the sole
canonical authority, and a Redis/Upstash outage can never become
canonical state and never silently weakens a hard contract
constraint.  Every failure is explicit and observable: the typed
:class:`UpstashCoordinationError` (never a silent allow, never a
silent deny); the per-application rate-limit BLOCK mirrors the
accepted in-process limiter's own blocked outcome (the
``rate-limited`` boundary error with truthful retry guidance --
``developerapi/ratelimit.py`` is the seam contract this adapter
implements over REST).

Pure standard library only (``urllib`` + ``json`` + ``hashlib``)
plus the accepted in-repo seams composed BY REFERENCE (the
``RateDecision`` dataclass and the ``AgentClock`` instant helpers)
-- no provider SDK anywhere (the Upstash REST API is the provider
surface, kept behind this adapter boundary).

Transport contract (the tiny injectable seam the batteries ride):

    Transport = Callable[[method, url, headers, body],
                          -> (status, body)]

``method`` is always ``"POST"`` (Upstash accepts POST for every
REST command; a uniform verb keeps the command surface one
shape), ``headers`` always carries ``Authorization: Bearer
<token>``, ``body`` is always empty (commands ride the URL path,
each path segment URL-quoted).  The transport returns the HTTP
status and raw body bytes, and may RAISE on network trouble (the
adapter maps any transport exception to ``backend-unavailable``).
The default transport is ``urllib.request`` with a bounded
timeout.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import quote, urlsplit

from agent.clock import AgentClock, SystemClock, add_seconds
from developerapi.errors import DeveloperApiError, DeveloperApiReasonCode
from developerapi.ratelimit import RateDecision

#: The injectable transport: (method, url, headers, body) ->
#: (status, body).  May raise on network failure.
Transport = Callable[[str, str, Dict[str, str], bytes], Tuple[int, bytes]]

#: The frozen failure vocabulary (DEC-0126: explicit, observable,
#: backend-named failures -- free-tier exhaustion included).
REASON_CODES = (
    "backend-unavailable",
    "config-invalid",
    "lock-not-held",
    "explicit-limit",
    "protocol-error",
)

#: The bounded default REST timeout (seconds).
DEFAULT_TIMEOUT_SECONDS = 10.0

#: The default rate-limit key prefix (keys read
#: ``"<prefix>:<application_id>"``).
DEFAULT_KEY_PREFIX = "ratelimit"

#: The default fixed-window size (mirrors the in-process
#: ``RateLimiter`` default ``capacity`` of 100 requests; the
#: refill cadence maps to the window length -- see the class
#: docstring).
DEFAULT_LIMIT = 100
DEFAULT_WINDOW_SECONDS = 60


class UpstashCoordinationError(Exception):
    """One typed Upstash coordination failure (DATA).

    ``reason_code`` is drawn from the frozen :data:`REASON_CODES`
    vocabulary; ``backend`` always names the failing backend
    (``"upstash"``) so a free-tier outage is attributable and
    observable.  ``detail`` never carries the REST token, a lock
    ownership token, or a raw URL (secret hygiene: error surfaces
    carry the command name, the status, and the failure class
    only).
    """

    backend = "upstash"

    def __init__(self, reason_code: str, detail: str = "") -> None:
        if reason_code not in REASON_CODES:
            raise ValueError(
                "upstash coordination reason %r is not in the frozen "
                "vocabulary" % (reason_code,)
            )
        self.reason_code = reason_code
        self.detail = detail
        super().__init__("upstash %s: %s" % (reason_code, detail))


# ---------------------------------------------------------------------------
# The REST plumbing
# ---------------------------------------------------------------------------

def _urllib_transport(
    method: str, url: str, headers: Dict[str, str], body: bytes
) -> Tuple[int, bytes]:
    """The default transport: stdlib ``urllib`` with a bounded
    timeout.  Network failures raise (the caller maps them to the
    typed backend-unavailable error); HTTP error statuses are
    returned as (status, body) pairs."""
    request = urllib.request.Request(
        url, data=body if body else None, method=method
    )
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(
            request, timeout=DEFAULT_TIMEOUT_SECONDS
        ) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        try:
            payload = error.read()
        except Exception:  # noqa: BLE001 - best-effort error body
            payload = b""
        return int(error.code), payload


def _validated_rest_config(
    rest_url: object, rest_token: object
) -> Tuple[str, str]:
    """Constructor-shape validation (fail closed, config-invalid)."""
    if not isinstance(rest_url, str) or not rest_url.strip():
        raise UpstashCoordinationError(
            "config-invalid", "rest_url must be a non-empty string"
        )
    parts = urlsplit(rest_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise UpstashCoordinationError(
            "config-invalid",
            "rest_url must be an absolute http(s) URL "
            "(https://<host>)",
        )
    if not isinstance(rest_token, str) or not rest_token.strip():
        raise UpstashCoordinationError(
            "config-invalid", "rest_token must be a non-empty string"
        )
    return rest_url.rstrip("/"), rest_token


class _RestClient:
    """One Upstash REST connection (URL + bearer token + transport).

    Each command is ONE transport call:
    ``POST <rest_url>/<command>/<quoted args...>`` with an empty
    body; the JSON ``result`` member is the command outcome.
    Failure mapping (frozen, single site):

    - transport exception      -> ``backend-unavailable``
    - HTTP 429 (quota/limit)   -> ``explicit-limit`` (free-tier
      exhaustion fails explicitly, DEC-0126)
    - HTTP 401/403             -> ``config-invalid`` (credentials
      refused by the backend)
    - any other non-200        -> ``backend-unavailable``
    - non-JSON / resultless    -> ``protocol-error``

    Details carry the command name and status only -- never the
    bearer token, never a raw URL, never a lock token.
    """

    def __init__(
        self,
        *,
        rest_url: str,
        rest_token: str,
        transport: Optional[Transport] = None,
    ) -> None:
        self._url = rest_url
        self._token = rest_token
        self._transport = (
            transport if transport is not None else _urllib_transport
        )

    def command(self, name: str, *segments: object) -> Any:
        path = "/" + "/".join(
            [name] + [quote(str(segment), safe="") for segment in segments]
        )
        url = self._url + path
        headers = {"Authorization": "Bearer %s" % self._token}
        try:
            status, body = self._transport("POST", url, headers, b"")
        except Exception as error:  # noqa: BLE001 - fail closed, typed
            raise UpstashCoordinationError(
                "backend-unavailable",
                "REST %s: transport raised %s"
                % (name, type(error).__name__),
            ) from error
        if status == 429:
            raise UpstashCoordinationError(
                "explicit-limit",
                "REST %s rejected with HTTP 429 (upstash command or "
                "quota limit reached -- free-tier exhaustion fails "
                "explicitly, never silently)" % name,
            )
        if status in (401, 403):
            raise UpstashCoordinationError(
                "config-invalid",
                "REST %s rejected with HTTP %d (credentials refused)"
                % (name, status),
            )
        if status != 200:
            raise UpstashCoordinationError(
                "backend-unavailable",
                "REST %s returned HTTP %d" % (name, status),
            )
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise UpstashCoordinationError(
                "protocol-error",
                "REST %s returned a non-JSON body" % name,
            ) from error
        if parsed is None:
            # Upstash answers a failed conditional SET with a bare
            # null result (documented shape); treat it as None.
            return None
        if isinstance(parsed, dict) and "result" in parsed:
            return parsed["result"]
        raise UpstashCoordinationError(
            "protocol-error",
            "REST %s returned a body without a result member" % name,
        )


def _require_positive_int(value: object, label: str) -> int:
    """Positive-integer constructor validation (mirrors the
    in-process ``RateLimiter``'s own capacity/refill checks,
    typed as the adapter's config-invalid failure)."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise UpstashCoordinationError(
            "config-invalid", "%s must be a positive integer" % label
        )
    return value


def _require_nonempty_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise UpstashCoordinationError(
            "config-invalid", "%s must be a non-empty string" % label
        )
    return value


# ---------------------------------------------------------------------------
# The rate limiter (the RateLimiter seam over REST)
# ---------------------------------------------------------------------------

class UpstashRateLimiter:
    """The per-application FIXED-WINDOW counter over the Upstash
    REST API -- the ``developerapi.ratelimit.RateLimiter`` seam
    implemented for a shared, cross-instance backend.

    Seam mirroring (the accepted in-process limiter is the
    contract; ``developerapi/ratelimit.py``):

    - ``check(application_id)`` returns the REAL ``RateDecision``
      (same class, same members: ``allowed``/``limit``/
      ``remaining``/``reset_at``/``retry_after``) while the
      application is under its limit.  ``limit`` requests are
      admitted per window (``remaining`` reaches 0), exactly as
      ``capacity`` tokens are consumed by the in-process bucket.
    - The blocked outcome MIRRORS the real limiter exactly: the
      ``rate-limited`` ``DeveloperApiError`` with truthful
      ``retry_after`` guidance (the window's reset instant), so
      an unmodified ``DeveloperGateway`` translates it into the
      same 429 envelope with ``Retry-After``.  A blocked request
      never silently admits (DEC-0126).
    - Token-bucket refill has no REST-native equivalent; the
      fixed window (``window_seconds``) is the honest analogue:
      the allowance resets atomically when the counter's expiry
      fires.  ``capacity`` -> ``limit``; refill cadence ->
      ``window_seconds``.

    Window discipline (one counter key per application,
    ``"<key_prefix>:<application_id>"``): ``INCR`` then ``TTL``;
    a ``TTL`` of -1 (fresh or orphaned counter -- the only state
    in which no expiry is anchored) triggers ``EXPIRE
    window_seconds``.  The expiry is therefore anchored ONCE at
    the first increment of a window and is NEVER refreshed by
    later increments (the window boundary cannot drift under
    duplicate traffic).  The ``TTL`` read also feeds the decision
    instants, so a decision costs two REST commands (three on
    the anchoring call).

    Determinism: decisions depend only on the injected transport
    and clock (an ``AgentClock`` for absolute ``reset_at``/
    ``retry_after`` instants; the sanctioned ``SystemClock`` OS
    time site is the default -- batteries inject deterministic
    clocks).  REST failure raises the typed
    :class:`UpstashCoordinationError` -- NEVER a silent allow.
    """

    def __init__(
        self,
        *,
        rest_url: str,
        rest_token: str,
        transport: Optional[Transport] = None,
        key_prefix: str = DEFAULT_KEY_PREFIX,
        limit: int = DEFAULT_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        clock: Optional[AgentClock] = None,
    ) -> None:
        url, token = _validated_rest_config(rest_url, rest_token)
        prefix = _require_nonempty_str(key_prefix, "key_prefix")
        limit = _require_positive_int(limit, "limit")
        window = _require_positive_int(window_seconds, "window_seconds")
        if clock is not None and not isinstance(clock, AgentClock):
            raise UpstashCoordinationError(
                "config-invalid", "clock must be an AgentClock"
            )
        self._rest = _RestClient(
            rest_url=url, rest_token=token, transport=transport
        )
        self._key_prefix = prefix
        self._limit = limit
        self._window_seconds = window
        self._clock = clock if clock is not None else SystemClock()

    @property
    def limit(self) -> int:
        """The per-window request allowance (the seam's capacity)."""
        return self._limit

    @property
    def window_seconds(self) -> int:
        """The fixed window length (the refill-cadence analogue)."""
        return self._window_seconds

    def _counter_key(self, application_id: str) -> str:
        return "%s:%s" % (self._key_prefix, application_id)

    def _window_ttl(self, key: str) -> int:
        """The counter's remaining TTL in seconds, anchoring the
        window expiry when (and only when) none is anchored."""
        ttl = self._rest.command("ttl", key)
        if ttl == -2:
            # impossible just after INCR unless the window expired
            # between the two commands -- fail closed and observable
            # rather than miscount a request.
            raise UpstashCoordinationError(
                "protocol-error",
                "the rate-limit counter vanished between INCR and TTL",
            )
        if ttl == -1:
            anchored = self._rest.command("expire", key, self._window_seconds)
            if anchored != 1:
                raise UpstashCoordinationError(
                    "protocol-error",
                    "EXPIRE did not anchor the fresh rate-limit window",
                )
            return self._window_seconds
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl < 0:
            raise UpstashCoordinationError(
                "protocol-error", "TTL returned a non-integer value"
            )
        return ttl

    def check(self, application_id: str) -> RateDecision:
        """Evaluate (and account) one request against its
        application's shared fixed-window counter.

        Under the limit: the real ``RateDecision`` (allowed,
        limit, remaining, reset_at = the window's reset instant,
        empty retry_after).  At/over the limit: the blocked
        outcome IDENTICAL in kind to the in-process limiter's
        (``rate-limited`` with ``retry_after`` = the window's
        reset instant).  REST failure: the typed
        :class:`UpstashCoordinationError` (fail closed, never a
        silent allow)."""
        if not isinstance(application_id, str) or not application_id:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "application_id must be a non-empty string",
            )
        key = self._counter_key(application_id)
        count = self._rest.command("incr", key)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise UpstashCoordinationError(
                "protocol-error", "INCR returned a non-integer count"
            )
        ttl = self._window_ttl(key)
        now = self._clock.now()
        reset_at = add_seconds(now, ttl)
        remaining = self._limit - count
        if remaining >= 0:
            return RateDecision(
                allowed=True,
                limit=self._limit,
                remaining=remaining,
                reset_at=reset_at,
                retry_after="",
            )
        raise DeveloperApiError(
            DeveloperApiReasonCode.RATE_LIMITED,
            "rate limit exceeded for application %r (limit %d per "
            "%d-second window)"
            % (application_id, self._limit, self._window_seconds),
            retry_after=reset_at,
        )


# ---------------------------------------------------------------------------
# The serialization lock
# ---------------------------------------------------------------------------

#: The deterministic ownership-token sequence (no randomness, no
# wall clock: identical construction orders yield identical
# tokens; cross-INSTANCE uniqueness holds within a process, and
# cross-PROCESS callers supply their own ``token``).
_TOKEN_SEQUENCE = itertools.count(1)


class UpstashLock:
    """A cross-instance append-serialization lock over the Upstash
    REST API (``SET key token NX PX ttl``).

    Ownership discipline (fail-safe against takeover):

    - ``acquire`` is ATOMIC (one ``SET ... NX PX`` command): a
      lock held by ANYONE (including a re-entrant self-acquire)
      returns ``False`` -- never a takeover.
    - ``release`` deletes ONLY own property: GET must equal the
      instance's own token before DEL runs; a non-owner (or a
      missing key) returns ``False`` and the holder survives.
    - ``extend`` re-arms the TTL only while still the owner.
    - ``is_held`` / ``ttl_seconds`` are observations (Redis TTL
      semantics: -1 = exists with no expiry, -2/missing -> None).

    The auto-generated ownership token is deterministic (derived
    from the key and a process-local sequence -- see
    :data:`_TOKEN_SEQUENCE`); it never appears in any error
    surface.  REST failures raise the typed
    :class:`UpstashCoordinationError` (never a silent
    acquire/release).  This is EPHEMERAL coordination state only
    (RedisNeverCanonical): the lock guards append serialization;
    it never stores or decides canonical ADCOS state.
    """

    def __init__(
        self,
        *,
        rest_url: str,
        rest_token: str,
        key: str,
        ttl_ms: int,
        transport: Optional[Transport] = None,
        token: Optional[str] = None,
    ) -> None:
        url, rest_token_value = _validated_rest_config(rest_url, rest_token)
        key = _require_nonempty_str(key, "key")
        ttl_ms = _require_positive_int(ttl_ms, "ttl_ms")
        if token is None:
            token = "upstash-lock-%s" % hashlib.sha256(
                ("%s#%d" % (key, next(_TOKEN_SEQUENCE))).encode("utf-8")
            ).hexdigest()[:32]
        else:
            token = _require_nonempty_str(token, "token")
        self._rest = _RestClient(
            rest_url=url, rest_token=rest_token_value, transport=transport
        )
        self._key = key
        self._ttl_ms = ttl_ms
        self._token = token

    @property
    def key(self) -> str:
        """The lock's coordination key (public: coordination
        state is not secret; the ownership token is)."""
        return self._key

    def acquire(self) -> bool:
        """Atomically take the lock (``SET key token NX PX
        ttl``).  ``True`` when acquired; ``False`` when the lock
        is already held (by anyone -- no takeover); typed error
        on backend failure."""
        result = self._rest.command(
            "set", self._key, self._token, "NX", "PX", self._ttl_ms
        )
        if result == "OK":
            return True
        if result is None:
            return False
        raise UpstashCoordinationError(
            "protocol-error",
            "SET NX PX returned an unexpected result for lock %r" % self._key,
        )

    def release(self) -> bool:
        """Release OWN property only: GET must equal the
        instance's token before DEL runs.  ``True`` when the
        owner released; ``False`` for a non-owner or a missing
        key (the holder survives).  Typed error on backend
        failure."""
        value = self._rest.command("get", self._key)
        if value is None or value != self._token:
            return False
        deleted = self._rest.command("del", self._key)
        if isinstance(deleted, bool) or not isinstance(deleted, int):
            raise UpstashCoordinationError(
                "protocol-error", "DEL returned a non-integer count"
            )
        if deleted < 0:
            raise UpstashCoordinationError(
                "protocol-error", "DEL returned a negative count"
            )
        # ownership was confirmed by the GET; a zero count means
        # the lock expired inside the release race window (the
        # key is gone either way -- and DEL never touched another
        # owner's lock).
        return True

    def extend(self, ttl_ms: int) -> bool:
        """Re-arm the lock's TTL -- ONLY while still the owner
        (GET == own token, then ``EXPIRE``).  ``False`` when the
        lock is missing or held by another owner (their TTL is
        untouched); typed error on backend failure.  Sub-second
        windows round UP to whole seconds (``EXPIRE`` is the
        second-granularity command on the REST surface)."""
        ttl_ms = _require_positive_int(ttl_ms, "ttl_ms")
        value = self._rest.command("get", self._key)
        if value is None or value != self._token:
            return False
        seconds = (ttl_ms + 999) // 1000
        result = self._rest.command("expire", self._key, seconds)
        if result == 1:
            return True
        if result == 0:
            # the key vanished between GET and EXPIRE: not the
            # owner of anything anymore.
            return False
        raise UpstashCoordinationError(
            "protocol-error",
            "EXPIRE returned an unexpected result for lock %r" % self._key,
        )

    def is_held(self) -> bool:
        """EXISTS semantics derived from TTL (the lock key exists
        -- ownership is NOT checked): ``True`` while any holder
        keeps the key alive, ``False`` once expired/absent."""
        return self.ttl_seconds() is not None

    def ttl_seconds(self) -> Optional[int]:
        """The lock's remaining TTL in whole seconds (Redis TTL
        semantics): ``None`` when the key is missing (-2), ``-1``
        when it exists with no expiry, otherwise the remaining
        seconds.  Typed error on backend failure."""
        result = self._rest.command("ttl", self._key)
        if result == -2:
            return None
        if result == -1:
            return -1
        if (
            isinstance(result, bool)
            or not isinstance(result, int)
            or result < 0
        ):
            raise UpstashCoordinationError(
                "protocol-error", "TTL returned a non-integer value"
            )
        return result
