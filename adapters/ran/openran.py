"""ADCOS Open RAN adapter (WORK-020): the production-shaped
real-HTTP adapter.

:class:`OpenRanAdapter` is the production-shaped 5G RAN integration
implementation.  It targets REAL OpenAirInterface / O-RAN-style lab
deployments through a configured HTTP control endpoint (the
O-RAN.WG1 O1-style REST resource-management surface: gNB/cell
lifecycle, bearer setup, state/capability reporting -- with TS
38.413 NG setup as the gNB-to-core association analog and
O-RAN.WG2 E2-style state reporting); pointing it at a running
OpenAirInterface/O-RAN lab is an endpoint config change, NOT a core
change (the WORK-020 acceptance criterion "ADCOS core imports no
vendor/Open RAN implementation types" -- the adapter is a package
module, the core never imports it).

It implements the frozen 14-operation :class:`RanContract` surface
DIRECTLY (unlike the WORK-019 ``Open5GSAdapter``, which subclasses
its reference engine): the RAN family's reference model lives behind
a REAL socket in the conformance peer, so the adapter proxies every
network-visible operation with REAL stdlib ``http.client`` requests
(JSON bodies, synchronous, bounded connect/read timeout) and keeps
only a registry of the opaque references the peer minted.  Every
response is mapped back into the family's value types
(:class:`~adapters.ran.model.RanObservation`,
:class:`~adapters.ran.model.RanSplitTopology`, ...); any response
shape outside the frozen contract fails closed with
``CONTRACT_VIOLATION``.

HONESTY DISCLOSURE (mirrors the fivegc ``Open5GSAdapter``): this
adapter is NOT itself a RAN stack -- it implements no radio, no
SDR, no L1/L2, no RRC/F1/E1 state machine, and no vendor or Open
RAN API (LOCK-016: external RAN/modem/SDR implementations remain
behind adapter/provider interfaces; LOCK-017: vendor
implementations are not ADCOS authority).  The in-sandbox evidence
path is the in-repo conformance peer
(:class:`adapters.ran.conformance.ReferenceRanConformanceServer`) --
the strongest honest evidence achievable in this sandbox (real
sockets, real JSON, byte-identical user-plane echo), NOT real radio
evidence.  The REAL acceptance path for the frozen WORK-020
"SDR-based lab topology" criterion is the environment-gated
OpenAirInterface/O-RAN-lab interop gate (a sibling module, a later
task -- the WORK-019 B1 real-Open5GS gate analog): when a real lab
control endpoint is reachable at ``RAN_CONTROL_URL``, the gate
exercises this adapter against it; until then the criterion remains
open, and no in-repo peer may be substituted for it in that gate.

Determinism: no randomness, no wall clock, no wall-clock-derived
state anywhere; the adapter is sequence-independent (it mints NO
references itself -- every ``ran:<kind>:<hex>`` reference is minted
by the peer and merely recorded here).  ``open``/``close`` are
local lifecycle gates (mirroring how the WORK-019 ``Open5GSAdapter``
inherited the reference engine's open/close discipline: open is
strict, close fails closed while live bearers exist and then clears
the local registries -- the peer is never torn down from close; a
real RAN deployment outlives any single integration session).  The
``observe`` link metrics are the adapter's OWN deterministic
counters over the real bearer data path (``tx`` bytes sent,
``rx`` bytes echoed back; link-up derived from the peer's NGAP flag
and active PRB capacity) -- the WORK-016 ``GenericAdapter.observe``
counter discipline, never wall-clock derived.
"""

from __future__ import annotations

import base64
import http.client
import json
import os
from typing import Any, Dict, Mapping, NoReturn, Optional, Tuple
from urllib.parse import quote, urlparse

from .contract import RanContext, RanContract
from .engine import RAN_ALLOCATION_KINDS
from .errors import RanError, RanReasonCode
from .model import (
    CuElement,
    DuElement,
    GnbProvisionRequest,
    HealthState,
    LinkMetricName,
    RanHealthSnapshot,
    RanObservation,
    RanResourceSnapshot,
    RanSplitTopology,
    RuElement,
)
from .validation import (
    assert_ref_session_separation,
    reject_credential_like_text,
    validate_gnb_provision_request,
    validate_opaque_ref,
    validate_session_id,
)

__all__ = ["OpenRanAdapter", "DEFAULT_RAN_CONTROL_URL", "RAN_CONTROL_URL_ENV"]

#: Default RAN control endpoint (an O-RAN O1-style HTTP control
#: surface; 9091 avoids the WORK-019 Open5GS SBI default 7777).
DEFAULT_RAN_CONTROL_URL = "http://127.0.0.1:9091"

#: The environment variable the EXPLICIT opt-in config load reads
#: (mirroring the WORK-019 ``OPEN5GS_SBI_URL`` discipline: the
#: adapter constructor NEVER reads the environment -- only the
#: explicit :meth:`OpenRanAdapter.from_env` opt-in does, so a test
#: or interop gate that wants environment configuration says so).
RAN_CONTROL_URL_ENV = "RAN_CONTROL_URL"

#: Bounded connect/read timeout for every control request (mirrors
#: the WORK-019 ``Open5GSAdapter`` HTTP timeout; an I/O bound, never
#: a source of wall-clock-derived state).
_HTTP_TIMEOUT_SECONDS = 10

#: HTTP 404 body reasons -> family reason codes (the peer reports
#: WHICH resource is unknown; an unrecognized 404 shape is a
#: non-contract response).
_NOT_FOUND_REASONS: Dict[str, str] = {
    "gnb-unknown": RanReasonCode.GNB_UNKNOWN,
    "cell-unknown": RanReasonCode.CELL_UNKNOWN,
    "bearer-unknown": RanReasonCode.BEARER_UNKNOWN,
    "allocation-unknown": RanReasonCode.ALLOCATION_UNKNOWN,
}


class OpenRanAdapter(RanContract):
    """The production-shaped Open RAN adapter (WORK-020).

    Constructed with an explicit HTTP control endpoint URL (a real
    OpenAirInterface/O-RAN-style lab deployment, or the WORK-020
    conformance peer).  ``open``/``close`` gate the adapter locally
    (strict open; close fails closed under live bearers); every
    network-visible contract operation issues a REAL synchronous
    ``http.client`` request with a JSON body against the peer's
    REST surface and maps the response into the family's frozen
    value shapes.
    """

    label = "openran-adapter"

    def __init__(
        self,
        *,
        control_url: str = DEFAULT_RAN_CONTROL_URL,
        timeout_seconds: int = _HTTP_TIMEOUT_SECONDS,
    ) -> None:
        if not isinstance(control_url, str) or not control_url:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "control_url must be a non-empty string",
            )
        if urlparse(control_url).hostname is None:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "control_url must have a host",
            )
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "timeout_seconds must be an integer",
            )
        if timeout_seconds <= 0:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "timeout_seconds must be > 0",
            )
        self._control_url = control_url
        self._timeout_seconds = timeout_seconds
        self._open = False
        # Registry of the opaque references the PEER minted (the
        # adapter mints nothing): gnb_ref -> gnb name, bearer_ref ->
        # session_id stored EXACTLY as provided (LOCK-006 read-only
        # passthrough bookkeeping), alloc_ref -> kind.
        self._gnb_refs: Dict[str, str] = {}
        self._bearer_refs: Dict[str, str] = {}
        self._allocation_refs: Dict[str, str] = {}
        # Deterministic link-metric counters over the real bearer
        # data path (adapter-side view; never wall-clock derived).
        self._tx_bytes_total = 0
        self._rx_bytes_total = 0

    # ------------------------------------------------------------------
    # Explicit opt-in environment config load
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls, **kwargs: Any) -> "OpenRanAdapter":
        """The EXPLICIT opt-in config load: read ``RAN_CONTROL_URL``
        from the environment (defaulting to
        :data:`DEFAULT_RAN_CONTROL_URL`) and construct the adapter.

        Mirroring the WORK-019 discipline (``OPEN5GS_SBI_URL`` is
        read only by the interop gate's ``InteropConfig.from_env``,
        never by the adapter constructor), the constructor itself
        NEVER touches the environment: a caller that wants
        environment-based endpoint configuration must explicitly
        call this classmethod.
        """
        url = os.environ.get(RAN_CONTROL_URL_ENV, "").strip() or DEFAULT_RAN_CONTROL_URL
        return cls(control_url=url, **kwargs)

    # ------------------------------------------------------------------
    # Local lifecycle gating (mirrors the reference engine discipline)
    # ------------------------------------------------------------------

    def open(self, context: RanContext) -> None:
        if self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter already open")
        self._open = True

    def close(self, context: RanContext) -> None:
        """Fails closed while live bearers exist, then clears the
        LOCAL registries (the peer deployment -- a real RAN lab or
        the conformance peer -- is never torn down from here;
        decommissioning peer resources is the caller's explicit
        per-resource operation, mirroring how the WORK-019
        ``Open5GSAdapter.close`` released only the adapter's own
        sockets)."""
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter not open")
        if self._bearer_refs:
            raise RanError(
                RanReasonCode.BINDING_EXISTS,
                "cannot close the RAN integration while %d radio "
                "bearer(s) are live (fail closed)" % len(self._bearer_refs),
            )
        self._open = False
        self._gnb_refs = {}
        self._bearer_refs = {}
        self._allocation_refs = {}

    # ------------------------------------------------------------------
    # Read-only reporting operations
    # ------------------------------------------------------------------

    def capabilities(self) -> Tuple[str, ...]:
        if not self._open:
            return ()
        response = self._request_json("GET", "/capabilities")
        return self._parse_capabilities(response)

    def observe(self, context: RanContext) -> RanObservation:
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter not open")
        state = self._request_json("GET", "/state")
        health = self._parse_health(state)
        if not health.cell_states:
            # Fail-closed mirror of the reference engine: the frozen
            # observation shape requires at least one reported cell.
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "no provisioned gnb to observe (the frozen observation "
                "shape requires at least one reported cell)",
            )
        resources = self._parse_resources(state)
        topology = self._parse_topology(state)
        capabilities = self._parse_capabilities(
            self._request_json("GET", "/capabilities")
        )
        link_up = 1 if (health.ngap_connected and resources.prb_total > 0) else 0
        link_metrics: Dict[str, int] = {
            LinkMetricName.LINK_UP: link_up,
            LinkMetricName.RX_BYTES_TOTAL: self._rx_bytes_total,
            LinkMetricName.TX_BYTES_TOTAL: self._tx_bytes_total,
            LinkMetricName.RX_ERROR_COUNT: 0,
            LinkMetricName.TX_ERROR_COUNT: 0,
            LinkMetricName.RETRANSMIT_COUNT: 0,
        }
        try:
            return RanObservation(
                capabilities=capabilities,
                health=health,
                resources=resources,
                topology=topology,
                link_metrics=link_metrics,
            )
        except (TypeError, ValueError) as exc:
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "peer /state did not satisfy the frozen observation "
                "shape: %s" % exc,
            ) from None

    def health(self) -> str:
        """Implementation-local health, derived from ``GET /state``
        (the peer's aggregate element health; fail-closed FAILED
        while the adapter is not open -- the reference engine's
        discipline)."""
        if not self._open:
            return HealthState.FAILED
        state = self._request_json("GET", "/state")
        return self._parse_health(state).aggregate()

    # ------------------------------------------------------------------
    # gNB / cell lifecycle operations
    # ------------------------------------------------------------------

    def provision_gnb(self, context: RanContext, *, request: GnbProvisionRequest) -> str:
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter not open")
        validate_gnb_provision_request(request)
        body: Dict[str, Any] = {
            "name": request.gnb_name,
            "cells": [cell.to_dict() for cell in request.cells],
            "topology": request.topology.to_dict(),
        }
        response = self._request_json("POST", "/gnb", body)
        gnb_ref = self._peer_ref(response, "gnb_ref", prefix="gnb", what="provision_gnb")
        self._gnb_refs[gnb_ref] = request.gnb_name
        return gnb_ref

    def decommission_gnb(self, context: RanContext, *, gnb_ref: str) -> None:
        validate_opaque_ref(gnb_ref, prefix="gnb")
        response = self._request_json("DELETE", "/gnb/%s" % gnb_ref)
        if response.get("status") != "decommissioned":
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "decommission response must carry status=decommissioned",
            )
        self._gnb_refs.pop(gnb_ref, None)

    def activate_cell(self, context: RanContext, *, gnb_ref: str, cell_id: str) -> None:
        self._cell_transition(gnb_ref, cell_id, "activate", "active")

    def deactivate_cell(self, context: RanContext, *, gnb_ref: str, cell_id: str) -> None:
        self._cell_transition(gnb_ref, cell_id, "deactivate", "inactive")

    def _cell_transition(
        self,
        gnb_ref: str,
        cell_id: str,
        action: str,
        expected_status: str,
    ) -> None:
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter not open")
        validate_opaque_ref(gnb_ref, prefix="gnb")
        if not isinstance(cell_id, str) or not cell_id:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "cell_id must be a non-empty string",
            )
        path = "/gnb/%s/cells/%s/%s" % (gnb_ref, quote(cell_id, safe=""), action)
        response = self._request_json("POST", path)
        if response.get("status") != expected_status:
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "cell %s response must carry status=%s" % (action, expected_status),
            )

    # ------------------------------------------------------------------
    # Bearer / data-plane operations
    # ------------------------------------------------------------------

    def bind_session(
        self,
        context: RanContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> str:
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter not open")
        validate_session_id(session_id)
        if requirements is not None and not isinstance(requirements, Mapping):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "requirements must be a mapping or None",
            )
        body: Dict[str, Any] = {
            "session_id": session_id,
            "requirements": dict(requirements) if requirements is not None else None,
        }
        response = self._request_json("POST", "/bearers", body)
        bearer_ref = self._peer_ref(
            response, "bearer_ref", prefix="bearer", what="bind_session"
        )
        cell_id = response.get("cell_id")
        if not isinstance(cell_id, str) or not cell_id:
            # The mapped serving cell is part of the response shape;
            # it is validated and then DISCARDED (mapped state, never
            # adapter bookkeeping and never core-visible).
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "bind response must carry the mapped cell_id",
            )
        # R1 defense at the seam: the PEER minted this reference, so
        # the mechanical separation check runs here as defense in
        # depth (the sandbox re-checks).
        assert_ref_session_separation(bearer_ref, session_id)
        self._bearer_refs[bearer_ref] = session_id
        return bearer_ref

    def unbind_session(self, context: RanContext, *, bearer_ref: str) -> None:
        validate_opaque_ref(bearer_ref, prefix="bearer")
        response = self._request_json("DELETE", "/bearers/%s" % bearer_ref)
        if response.get("status") != "released":
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "unbind response must carry status=released",
            )
        self._bearer_refs.pop(bearer_ref, None)

    def egress_data(
        self,
        context: RanContext,
        *,
        bearer_ref: str,
        payload: bytes,
    ) -> bytes:
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter not open")
        if not isinstance(payload, (bytes, bytearray)):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "payload must be bytes",
            )
        validate_opaque_ref(bearer_ref, prefix="bearer")
        encoded = base64.b64encode(bytes(payload)).decode("ascii")
        response = self._request_json(
            "POST", "/bearers/%s/data" % bearer_ref, {"payload_b64": encoded}
        )
        echoed = response.get("payload_b64")
        if not isinstance(echoed, str) or not echoed:
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "bearer data response must carry payload_b64",
            )
        try:
            decoded = base64.b64decode(echoed, validate=True)
        except (TypeError, ValueError) as exc:
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "bearer data response was not valid base64: %s" % exc,
            ) from None
        self._tx_bytes_total += len(payload)
        self._rx_bytes_total += len(decoded)
        # The bytes the far end returned (the conformance peer echoes
        # them byte-identically; a real RAN's far end returns what it
        # returned -- the adapter reports, never fabricates).
        return decoded

    # ------------------------------------------------------------------
    # Radio-capacity reservation operations
    # ------------------------------------------------------------------

    def allocate(
        self,
        context: RanContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "adapter not open")
        if not isinstance(kind, str) or kind not in RAN_ALLOCATION_KINDS:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "kind must be one of %s" % (list(RAN_ALLOCATION_KINDS),),
            )
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "quantity_base must be an integer",
            )
        if quantity_base < 0:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "quantity_base must be >= 0",
            )
        if not isinstance(purpose, str) or not purpose:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "purpose must be a non-empty string",
            )
        reject_credential_like_text(purpose, what="purpose")
        body: Dict[str, Any] = {
            "kind": kind,
            "quantity_base": quantity_base,
            "purpose": purpose,
        }
        response = self._request_json("POST", "/allocations", body)
        alloc_ref = self._peer_ref(
            response, "technology_ref", prefix="alloc", what="allocate"
        )
        self._allocation_refs[alloc_ref] = kind
        return alloc_ref

    def release(self, context: RanContext, *, technology_ref: str) -> None:
        validate_opaque_ref(technology_ref, prefix="alloc")
        response = self._request_json("DELETE", "/allocations/%s" % technology_ref)
        if response.get("status") != "released":
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "release response must carry status=released",
            )
        self._allocation_refs.pop(technology_ref, None)

    # ------------------------------------------------------------------
    # Response-shape parsing (peer JSON -> family value types)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_capabilities(response: Dict[str, Any]) -> Tuple[str, ...]:
        raw = response.get("capabilities")
        if not isinstance(raw, list) or any(
            not isinstance(item, str) for item in raw
        ):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "capabilities response must carry a list of reference strings",
            )
        return tuple(raw)

    @staticmethod
    def _parse_health(state: Dict[str, Any]) -> RanHealthSnapshot:
        raw = state.get("health")
        if not isinstance(raw, dict):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state must carry a health object",
            )
        try:
            return RanHealthSnapshot(
                gnb_state=raw["gnb_state"],
                cu_state=raw["cu_state"],
                du_states=tuple(raw["du_states"]),
                ru_states=tuple(raw["ru_states"]),
                cell_states=dict(raw["cell_states"]),
                ngap_connected=raw["ngap_connected"],
            )
        except (KeyError, TypeError, ValueError):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state health block does not match the frozen health "
                "snapshot shape",
            ) from None

    @staticmethod
    def _parse_resources(state: Dict[str, Any]) -> RanResourceSnapshot:
        raw = state.get("resources")
        if not isinstance(raw, dict):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state must carry a resources object",
            )
        values = [
            raw.get("prb_total"),
            raw.get("prb_used"),
            raw.get("rrc_connected_ue_count"),
            raw.get("active_drb_count"),
        ]
        for value in values:
            if isinstance(value, bool) or not isinstance(value, int):
                raise RanError(
                    RanReasonCode.CONTRACT_VIOLATION,
                    "/state resources must carry integer counters",
                )
        try:
            return RanResourceSnapshot(
                prb_total=raw["prb_total"],
                prb_used=raw["prb_used"],
                rrc_connected_ue_count=raw["rrc_connected_ue_count"],
                active_drb_count=raw["active_drb_count"],
            )
        except (KeyError, TypeError, ValueError):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state resources block does not match the frozen "
                "resource snapshot shape",
            ) from None

    @staticmethod
    def _parse_topology(state: Dict[str, Any]) -> RanSplitTopology:
        raw = state.get("topology")
        if not isinstance(raw, dict):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state must carry the mapped CU/DU/RU topology",
            )
        cu_raw = raw.get("cu")
        dus_raw = raw.get("dus")
        rus_raw = raw.get("rus")
        if not isinstance(cu_raw, dict) or not isinstance(dus_raw, list) or not isinstance(rus_raw, list):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state topology must carry cu/dus/rus blocks",
            )
        if any(not isinstance(du, dict) for du in dus_raw) or any(
            not isinstance(ru, dict) for ru in rus_raw
        ):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state topology elements must be objects",
            )
        try:
            cu = CuElement(
                element_id=cu_raw["element_id"],
                split=cu_raw["split"],
                state=cu_raw["state"],
            )
            dus = tuple(
                DuElement(
                    element_id=du["element_id"],
                    split=du["split"],
                    state=du["state"],
                    cell_ids=tuple(du["cell_ids"]),
                )
                for du in dus_raw
            )
            rus = tuple(
                RuElement(
                    element_id=ru["element_id"],
                    split=ru["split"],
                    state=ru["state"],
                    band=ru["band"],
                )
                for ru in rus_raw
            )
            return RanSplitTopology(cu=cu, dus=dus, rus=rus)
        except (KeyError, TypeError, ValueError):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "/state topology does not match the frozen split "
                "topology shape",
            ) from None

    @staticmethod
    def _peer_ref(
        response: Dict[str, Any],
        key: str,
        *,
        prefix: str,
        what: str,
    ) -> str:
        """Extract + grammar-check an opaque reference the PEER
        minted (a reference outside the frozen
        ``ran:<kind>:<hex>`` grammar is a non-contract response)."""
        value = response.get(key)
        if not isinstance(value, str) or not value:
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "%s response must carry %s" % (what, key),
            )
        try:
            validate_opaque_ref(value, prefix=prefix)
        except RanError:
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "%s response carried a reference outside the frozen "
                "ran:<kind>:<hexdigest> grammar" % what,
            ) from None
        return value

    # ------------------------------------------------------------------
    # Real HTTP transport (stdlib http.client; no vendor SDK)
    # ------------------------------------------------------------------

    def _http_request(self, method: str, path: str, body: Optional[Dict[str, Any]]) -> Tuple[int, bytes]:
        """Make a REAL HTTP request to the configured RAN control
        endpoint (synchronous, bounded connect/read timeout, JSON
        in/out).  Transport failures raise ``RAN_UNAVAILABLE`` --
        honest fail-closed, mirroring the WORK-019 ``NF_UNAVAILABLE``
        discipline."""
        parsed = urlparse(self._control_url)
        host = parsed.hostname
        port = parsed.port or 80
        if host is None:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "control_url must have a host",
            )
        payload: Optional[bytes] = None
        if body is not None:
            try:
                payload = json.dumps(body).encode("utf-8")
            except (TypeError, ValueError):
                raise RanError(
                    RanReasonCode.INVALID_INPUT,
                    "request body is not JSON-serializable",
                ) from None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            headers["Content-Length"] = str(len(payload))
        conn = http.client.HTTPConnection(host, port, timeout=self._timeout_seconds)
        try:
            conn.request(method, path, body=payload, headers=headers)
            response = conn.getresponse()
            data = response.read()
            return response.status, data
        except RanError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "RAN control endpoint unreachable: %s" % exc,
            )
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _request_json(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Issue the request and parse a JSON-object response body.

        Success statuses are 200/201 (REST create discipline).  Any
        other status maps to the family's reason codes (400 ->
        invalid-input; 404 with a recognized body reason -> the
        matching unknown-resource code; 409 -> binding-exists; 503 ->
        ran-unavailable; anything else, and any unparseable body, is
        a CONTRACT_VIOLATION -- non-contract response shape).
        """
        status, data = self._http_request(method, path, body)
        if status not in (200, 201):
            self._raise_status_error(status, data)
        if not data:
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "RAN control endpoint returned an empty body",
            )
        try:
            parsed = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "RAN control endpoint returned a non-JSON body",
            ) from None
        if not isinstance(parsed, dict):
            raise RanError(
                RanReasonCode.CONTRACT_VIOLATION,
                "RAN control endpoint returned a non-object JSON body",
            )
        return parsed

    @staticmethod
    def _raise_status_error(status: int, data: bytes) -> NoReturn:
        reason = ""
        if data:
            try:
                parsed = json.loads(data.decode("utf-8"))
                if isinstance(parsed, dict) and isinstance(parsed.get("reason"), str):
                    reason = parsed["reason"]
            except (UnicodeDecodeError, json.JSONDecodeError):
                reason = ""
        if status == 400:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "RAN control endpoint rejected the request (HTTP 400)",
            )
        if status == 404:
            reason_code = _NOT_FOUND_REASONS.get(reason)
            if reason_code is None:
                raise RanError(
                    RanReasonCode.CONTRACT_VIOLATION,
                    "RAN control endpoint returned HTTP 404 without a "
                    "recognized RAN reason (got %r)" % reason,
                )
            raise RanError(reason_code, "RAN control endpoint: %s" % reason)
        if status == 409:
            raise RanError(
                RanReasonCode.BINDING_EXISTS,
                "RAN control endpoint reported a live binding conflict "
                "(HTTP 409)",
            )
        if status == 503:
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "RAN control endpoint reported ran-unavailable (HTTP 503)",
            )
        raise RanError(
            RanReasonCode.CONTRACT_VIOLATION,
            "RAN control endpoint returned HTTP %d (non-contract "
            "status)" % status,
        )
