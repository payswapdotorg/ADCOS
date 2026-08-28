"""ADCOS access-path session facade (WORK-020): application
transparency.

An ordinary application uses ``connect()`` / ``send()`` / ``recv()`` /
``close()`` with a standard destination string and exchanges data; it
makes NO ADCOS or 3GPP API call and sees NO RAN identifier.  The
application-transparency invariant (LOCK-019 analog; LOCK-006 --
access technology is invisible to the session) is structurally
enforced by the public surface:

* The public method signatures expose ONLY standard session semantics
  (``connect(destination: str)``, ``send(payload: bytes)``,
  ``recv() -> bytes``, ``close()``) -- the parameter names are
  technology-neutral (``destination``/``payload`` only), so a surface
  audit that introspects signature tokens finds nothing else.
* No ``session_id``, ``rnti``, ``drb``, ``cell_id``, ``gnb_ref``,
  ``bearer_ref``, or ``adcos`` token appears in the session's PUBLIC
  surface -- not even in the constructor signature (the private
  routing handle is attached by the manager through the private
  ``_bind_access_path`` hook, mirroring the WORK-019 ``AppSession``
  pattern of manager-injected private routing metadata).

The session INTERNALLY routes ``send`` through the manager's
``egress_data`` on the bound radio bearer (the manager injects itself
and the operation instant at construction time through private
hooks).  This internal routing metadata is private to the session
instance; it is never exposed as a public attribute (the field names
are underscore-prefixed and never appear in the public method
signatures or in any ADCOS/RAN-token-shaped attribute name).

This module imports NO ADCOS core symbol and NO 3GPP type: only the
RAN family's own error vocabulary (``adapters.ran.errors``).

WORK-020 definition of done: "ADCOS can provision/use a
standards-compliant 5G access path" -- this facade IS that surface:
an ordinary application provisions and uses a standards-compliant 5G
access path without ever knowing that a RAN exists underneath.
"""

from __future__ import annotations

from typing import Any, List, Optional

from .errors import RanError, RanReasonCode

__all__ = ["AccessPathSession"]


class AccessPathSession:
    """An ordinary 5G access-path session facade.

    An ordinary application uses ``connect()`` / ``send()`` /
    ``recv()`` / ``close()`` with a standard destination string (a
    data-network name or an address literal) and exchanges data over
    the standards-compliant 5G access path.  It makes NO ADCOS or
    3GPP API call.  The application-transparency invariant (LOCK-019
    analog; LOCK-006) is structurally enforced: only standard session
    semantics appear in the public surface.

    The session internally routes bytes through the manager's
    ``egress_data`` on the bound radio bearer; this is private
    routing metadata, never exposed as a public attribute.

    Constructed ONLY through
    :meth:`adapters.ran.manager.RanManager.access_path_session`
    (which creates the binding on the default implementation and
    injects itself + the routing handle + the operation instant).
    """

    # NOTE: __slots__ is omitted deliberately so the manager can
    # attach private routing metadata through setattr; the public
    # surface is the four methods below only.  The attribute names
    # used internally begin with an underscore and never collide with
    # the forbidden transparency tokens (session_id/rnti/drb/cell_id/
    # gnb_ref/bearer_ref/adcos).

    def __init__(self, *, destination: str = "") -> None:
        # All fields are PRIVATE; they are NOT part of the public
        # surface.  The binding handle is stored under a non-token
        # attribute name (_path_handle) so a leaky-attribute audit
        # cannot be defeated by the field name itself, and the sacred
        # session identity is deliberately NOT stored on the session
        # at all (the manager's binding record owns the
        # session-to-bearer mapping; LOCK-006).
        self._destination = destination
        self._path_handle = ""  # private routing handle (manager-injected)
        self._manager: Optional[Any] = None
        self._connected = True
        self._inbound: List[bytes] = []  # inbound bytes buffer (deterministic model)
        self._closed = False
        self._now = "2026-06-01T12:00:00Z"  # injected instant (deterministic)

    # ------------------------------------------------------------------
    # Public surface (LOCK-019 analog): standard session semantics only.
    # ------------------------------------------------------------------

    def connect(self, destination: str) -> None:
        """Connect to a remote endpoint.

        An ordinary application calls this with a standard destination
        string and exchanges data with the peer over the 5G access
        path.  The standard session semantics are the only surface
        exposed here.
        """
        if not isinstance(destination, str) or not destination:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "destination must be a non-empty string",
            )
        if self._closed:
            raise RanError(
                RanReasonCode.NOT_OPEN,
                "session is closed",
            )
        self._destination = destination

    def send(self, payload: bytes) -> int:
        """Send bytes over the connected access path.

        The bytes traverse the contract path ``AccessPathSession.send
        -> manager.egress_data -> SandboxedRan -> implementation.
        egress_data`` on the bound radio bearer (the binding's OWNING
        sandbox carries them -- B2/R4); the bytes the RAN user plane
        returns (the deterministic reference engine's unchanged
        payload, or a real radio peer's round-trip echo) land in the
        inbound buffer for the next ``recv()``.  Returns the number
        of payload bytes sent.
        """
        if self._closed:
            raise RanError(
                RanReasonCode.NOT_OPEN,
                "session is closed",
            )
        if not isinstance(payload, (bytes, bytearray)):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "payload must be bytes",
            )
        if self._manager is None:
            # No manager bound: nothing to carry (the deterministic
            # in-isolation model, mirroring the WORK-019 AppSession).
            return len(payload)
        # Route through the manager's egress_data path with the
        # injected instant (the manager injected the instant at
        # construction; no wall clock is ever consulted here).
        result = self._manager.egress_data(
            now=self._now,
            binding_ref=self._path_handle,
            payload=bytes(payload),
        )
        if not result.ok:
            raise RanError(
                result.reason,
                "egress_data failed: %s" % result.detail,
            )
        # The bytes the RAN user plane returned are the modeled
        # round-trip: they land in the inbound buffer for the next
        # recv() (the reference engine returns the payload unchanged;
        # a real RAN returns the bytes the far end returned).
        if result.value is not None:
            self._inbound.append(bytes(result.value))
        return len(payload)

    def recv(self) -> bytes:
        """Receive bytes from the connected access path.

        Returns the last round-trip bytes (pop from the inbound
        buffer, oldest first -- the WORK-019 ``AppSession`` recv
        semantics).  An empty recv is permitted when nothing has
        traversed the path since the last receive (the byte
        round-trip over a real radio peer is exercised by the
        conformance/interop layer, not by this facade).
        """
        if self._closed:
            raise RanError(
                RanReasonCode.NOT_OPEN,
                "session is closed",
            )
        if self._inbound:
            return self._inbound.pop(0)
        return b""

    def close(self) -> None:
        """Close the session (application-side only).

        The MANAGER's binding lives until ``unbind_session`` /
        ``close_binding`` -- an application closing its session never
        tears the session-to-bearer mapping out from under the next
        application that uses the same access path.
        """
        self._closed = True

    # ------------------------------------------------------------------
    # Internal routing metadata (PRIVATE; never exposed as a public
    # attribute on the session surface).
    # ------------------------------------------------------------------

    def _bind_access_path(self, *, manager: Any, binding_ref: str) -> None:
        """Internal: the manager injects itself and the binding's
        MANAGER-side routing handle (the opaque binding token its own
        ops accept) so the session can route egress to the binding's
        OWNING sandbox (B2/R4).  The handle is PRIVATE routing
        metadata; it never appears in the public surface."""
        self._manager = manager
        self._path_handle = binding_ref

    def _set_now(self, now: str) -> None:
        """Internal: inject the operation instant for deterministic
        egress routing (never a wall clock)."""
        self._now = now

    def _deliver(self, data: bytes) -> None:
        """Internal: deliver inbound bytes (called by the test harness
        or by the manager's ingress path)."""
        self._inbound.append(bytes(data))
