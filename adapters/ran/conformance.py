"""ADCOS 5G RAN integration conformance peer (WORK-020).

A REAL-socket HTTP control peer for the RAN seam, running as user
``z`` (no root, no Docker, no SDR).  It is the WORK-019
``Reference5GCoreConformanceServer`` analog: where WORK-019 used a
real HTTP socket speaking 3GPP TS 29.5xx SBi message-schema shapes
to prove the Open5GS adapter's real HTTP calls traverse a real 5G
Core interface, WORK-020 runs a real ``http.server`` thread speaking
the SAME REST control-surface SHAPE an O-RAN O1/E2-style or
OpenAirInterface-adjacent deployment would recognize (reference
SHAPES with citations: TS 38.413 NG setup as the gNB-to-core
association analog, O-RAN.WG1 O1-style REST resource management,
O-RAN.WG2 E2-style state reporting) -- so the OpenRanAdapter's real
``http.client`` requests and real JSON bodies literally traverse a
real socket to a genuinely separate RAN-side peer state machine.

TRANSPARENT DISCLOSURE (the fivegc B1 honesty, mirrored): this is an
ADCOS test implementation, NOT a real RAN stack.  It implements no
radio, no L1/L2 (TS 38.211/38.212/38.214), no RRC/F1/E1 state
machines (TS 38.331/38.473/38.463), no open fronthaul (O-RAN.WG4),
and no vendor or Open RAN API.  It therefore CANNOT satisfy the
frozen WORK-020 ``SDR-based lab topology`` acceptance criterion on
its own; that requires the environment-gated REAL interop gate
against a real OpenAirInterface/O-RAN lab (a sibling module, a later
task), exactly as the WORK-019 B1 real-Open5GS gate superseded the
fivegc conformance peer.  The peer lives in the ADAPTER package
(``adapters/ran/conformance.py``), NEVER in the ADCOS core
(LOCK-002/016/017); no RAN type, RNTI/DRB identifier, or state
machine is imported into the core.

The served REST surface (all JSON, all deterministic -- content-
derived references over the family's ``_mint_ref`` sha256 minting,
sequence counters, NO wall clock anywhere in a response body):

* ``GET  /capabilities`` -- the capability-id REFERENCE list
* ``GET  /state`` -- health + resources + CU/DU/RU topology
* ``POST /gnb`` -- provision a gNB (cells start INACTIVE) -> the
  opaque ``ran:gnb:<digest>`` reference (HTTP 400 on bad input)
* ``DELETE /gnb/{gnb_ref}`` -- decommission (404 unknown gNB, 409
  while live bearers are served -- the fail-closed mirror)
* ``POST /gnb/{gnb_ref}/cells/{cell_id}/activate`` /
  ``.../deactivate`` -- cell state transitions (404 unknown
  gNB/cell; strict same-state transitions are HTTP 400)
* ``POST /bearers`` -- bind a session (body: ``session_id`` +
  optional ``requirements``) -> the opaque
  ``ran:bearer:<digest>`` reference plus the mapped serving
  ``cell_id``.  The peer allocates its ADAPTER-PRIVATE UE context
  (RNTI per TS 38.321 §7.1, DRB per TS 38.331, QFI per TS 23.501
  §5.4) server-side, mirroring the engine's UE-context model; the
  response NEVER echoes RNTI/DRB/QFI material (LOCK-006/016 -- only
  opaque refs + mapped state cross the peer boundary).
* ``DELETE /bearers/{bearer_ref}`` -- unbind (404 unknown bearer)
* ``POST /bearers/{bearer_ref}/data`` -- carry a base64 payload over
  the bearer's user plane; the response echoes the payload
  BYTE-IDENTICAL (the DN/UE-application echo analog of the WORK-019
  conformance peer's TCP data plane).  A bearer whose serving cell
  is INACTIVE returns HTTP 503 ``{"reason": "ran-unavailable"}``
  (honest fail-closed, mirroring the engine's egress discipline).
* ``POST /allocations`` / ``DELETE /allocations/{ref}`` -- minimal
  radio-capacity reservation lifecycle (the ``allocate``/``release``
  contract ops; ``ran:alloc:<digest>`` references).

Server-internal state machine: a minimal deterministic RAN model
over the family's own model dataclasses (``CellDescriptor``/
``CellState``/``RanSplitTopology``/``RanUeContext``/``RanDrb``) with
a gnb/cell/bearer registry, bounded PRB accounting (1 PRB per
bearer, first-fit ACTIVE cell choice in gNB-then-cell insertion
order) -- mirroring :class:`adapters.ran.engine.ReferenceRanEngine`
semantics exactly, so the peer and the reference engine agree on
refs, PRB math, and health aggregation for the same operation
sequence.  The peer is a SEPARATE state machine on the far side of a
real socket, not the engine in disguise.
"""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote

from .engine import FIRST_RNTI, LAST_RNTI, RAN_ALLOCATION_KINDS, _mint_ref
from .model import (
    RAN_CAPABILITY_CELL_FDD,
    RAN_CAPABILITY_CELL_TDD,
    RAN_CAPABILITY_CU_DU_SPLIT_F1,
    RAN_CAPABILITY_DRB_QOS_FLOW,
    RAN_CAPABILITY_GNB_PROVISION,
    RAN_CAPABILITY_O_RU_FRONTHAUL,
    RAN_CAPABILITY_REFERENCES,
    CellDescriptor,
    CellSpec,
    CellState,
    CuElement,
    DuplexMode,
    DuElement,
    GnbProvisionRequest,
    HealthState,
    RanDrb,
    RanSplitOption,
    RanSplitTopology,
    RanUeContext,
    RuElement,
)
from .validation import (
    reject_credential_like_text,
    validate_gnb_provision_request,
    validate_session_id,
)

__all__ = ["ReferenceRanConformanceServer"]


def _json_response(status: int, payload: Dict[str, Any]) -> Tuple[int, bytes]:
    return status, json.dumps(payload).encode("utf-8")


def _error(status: int, reason: str) -> Tuple[int, bytes]:
    return status, json.dumps({"reason": reason}).encode("utf-8")


class _ConformanceHTTPServer(ThreadingHTTPServer):
    """A :class:`ThreadingHTTPServer` that delegates control-surface
    requests to the owning :class:`ReferenceRanConformanceServer`
    (so the request handler can reach ``server._handle_control``)."""

    def __init__(self, addr, handler, conformance: "ReferenceRanConformanceServer") -> None:
        super().__init__(addr, handler)
        self._conformance = conformance

    def _handle_control(self, method: str, path: str, body: bytes) -> Tuple[int, bytes]:
        return self._conformance._handle_control(method, path, body)


class _ControlHandler(BaseHTTPRequestHandler):
    """Minimal O1/E2-style REST handler (real HTTP, real JSON)."""

    # Silence the default stderr logging (deterministic output).
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        self._delegate("GET")

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        self._delegate("POST")

    def do_DELETE(self) -> None:  # noqa: N802 (stdlib naming)
        self._delegate("DELETE")

    def _delegate(self, method: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b""
        path = self.path
        server: "_ConformanceHTTPServer" = self.server  # type: ignore[assignment]
        try:
            response = server._handle_control(method, path, body)
        except Exception:  # noqa: BLE001 -- the peer must not crash
            response = _error(500, "internal")
        status, payload = response
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._send(payload)

    def _send(self, payload: bytes) -> None:
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _PeerGnbEntry:
    """Peer-private provisioned-gNB record (never core state)."""

    __slots__ = ("gnb_name", "cells", "topology")

    def __init__(
        self,
        gnb_name: str,
        cells: Dict[str, CellDescriptor],
        topology: RanSplitTopology,
    ) -> None:
        self.gnb_name = gnb_name
        self.cells = cells
        self.topology = topology


class _PeerBearerEntry:
    """Peer-private bound-bearer record.

    ``session_id`` is stored EXACTLY as provided (LOCK-006 read-only
    passthrough); the UE context (RNTI/DRB/QFI) is peer-private
    adapter-side state that NEVER crosses the wire -- responses carry
    only the opaque ``ran:bearer:<hex>`` ref and mapped state.
    """

    __slots__ = ("session_id", "gnb_ref", "cell_id", "ue_context")

    def __init__(
        self,
        session_id: str,
        gnb_ref: str,
        cell_id: str,
        ue_context: RanUeContext,
    ) -> None:
        self.session_id = session_id
        self.gnb_ref = gnb_ref
        self.cell_id = cell_id
        self.ue_context = ue_context


class ReferenceRanConformanceServer:
    """A real REST-over-HTTP RAN control-plane peer.

    Runs as user ``z`` (no root).  Starts a real
    :class:`ThreadingHTTPServer` on ``127.0.0.1:<ephemeral>`` serving
    the O1/E2-style control surface above, backed by a deterministic
    in-peer RAN model.  Use as a context manager or call
    :meth:`close` to shut the server down.
    """

    def __init__(self, *, host: str = "127.0.0.1") -> None:
        self._host = host
        # One mutation lock: the threading HTTP server may dispatch
        # concurrent requests, and the peer's registry mutations must
        # stay deterministic (the fivegc peer had the same exposure;
        # this peer closes it).
        self._lock = threading.Lock()
        # Deterministic counters (no wall clock, no randomness) --
        # mirrors of the reference engine's counters.
        self._sequence = 0
        self._rnti_next = FIRST_RNTI
        # gnb_ref -> provisioned gNB (insertion order = provision order).
        self._gnbs: Dict[str, _PeerGnbEntry] = {}
        # bearer_ref -> bound bearer (session_id stored EXACTLY as given).
        self._bearers: Dict[str, _PeerBearerEntry] = {}
        # alloc_ref -> purpose (radio-capacity reservations).
        self._allocations: Dict[str, str] = {}
        # Real HTTP server (the RAN control plane) -- delegates to self.
        self._http = _ConformanceHTTPServer((host, 0), _ControlHandler, self)
        self._http.timeout = 5
        self._http_thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._http_thread.start()

    # ------------------------------------------------------------------
    # Public surface (mirrors the fivegc conformance server lifecycle)
    # ------------------------------------------------------------------

    @property
    def port(self) -> int:
        """The ephemeral port the real HTTP server listens on."""
        return int(self._http.server_address[1])

    @property
    def base_url(self) -> str:
        return "http://%s:%d" % (self._host, self.port)

    def close(self) -> None:
        """Shut the HTTP server down and release the socket."""
        try:
            self._http.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._http.server_close()
        except Exception:  # noqa: BLE001
            pass
        self._http_thread.join(timeout=5)

    def __enter__(self) -> "ReferenceRanConformanceServer":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Request entry point
    # ------------------------------------------------------------------

    def _handle_control(self, method: str, path: str, body: bytes) -> Tuple[int, bytes]:
        with self._lock:
            return self._dispatch(method, path, body)

    def _dispatch(self, method: str, path: str, body: bytes) -> Tuple[int, bytes]:
        segments = [unquote(segment) for segment in path.split("/") if segment]
        if method == "GET" and segments == ["capabilities"]:
            return _json_response(200, {"capabilities": list(self._current_capabilities())})
        if method == "GET" and segments == ["state"]:
            return _json_response(200, self._state_view())
        if method == "POST" and segments == ["gnb"]:
            return self._handle_provision(body)
        if method == "DELETE" and len(segments) == 2 and segments[0] == "gnb":
            return self._handle_decommission(segments[1])
        if (
            method == "POST"
            and len(segments) == 5
            and segments[0] == "gnb"
            and segments[2] == "cells"
            and segments[4] in ("activate", "deactivate")
        ):
            return self._handle_cell_transition(segments[1], segments[3], segments[4])
        if method == "POST" and segments == ["bearers"]:
            return self._handle_bind(body)
        if method == "DELETE" and len(segments) == 2 and segments[0] == "bearers":
            return self._handle_unbind(segments[1])
        if method == "POST" and len(segments) == 3 and segments[0] == "bearers" and segments[2] == "data":
            return self._handle_data(segments[1], body)
        if method == "POST" and segments == ["allocations"]:
            return self._handle_allocate(body)
        if method == "DELETE" and len(segments) == 2 and segments[0] == "allocations":
            return self._handle_release(segments[1])
        return _error(404, "path-not-found")

    @staticmethod
    def _parse_body(body: bytes) -> Optional[Dict[str, Any]]:
        if not body:
            return None
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    # ------------------------------------------------------------------
    # Deterministic RAN model (mirrors ReferenceRanEngine semantics)
    # ------------------------------------------------------------------

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _current_capabilities(self) -> Tuple[str, ...]:
        """Capability-id REFERENCES currently served, in frozen catalog
        order (the peer is always up, so gnb-provision is always
        served -- the engine's open-state analog)."""
        served = {RAN_CAPABILITY_GNB_PROVISION}
        active = tuple(
            cell
            for entry in self._gnbs.values()
            for cell in entry.cells.values()
            if cell.state == CellState.ACTIVE
        )
        if any(cell.duplex == DuplexMode.TDD for cell in active):
            served.add(RAN_CAPABILITY_CELL_TDD)
        if any(cell.duplex == DuplexMode.FDD for cell in active):
            served.add(RAN_CAPABILITY_CELL_FDD)
        if self._bearers:
            served.add(RAN_CAPABILITY_DRB_QOS_FLOW)
        for entry in self._gnbs.values():
            elements = (entry.topology.cu, *entry.topology.dus, *entry.topology.rus)
            for element in elements:
                if element.split == RanSplitOption.F1_CU_DU:
                    served.add(RAN_CAPABILITY_CU_DU_SPLIT_F1)
                if element.split == RanSplitOption.O_RAN_7_2X:
                    served.add(RAN_CAPABILITY_O_RU_FRONTHAUL)
        return tuple(cap for cap in RAN_CAPABILITY_REFERENCES if cap in served)

    def _health_view(self) -> Dict[str, Any]:
        """The per-element health view (engine ``_health_snapshot``
        semantics; ``ngap_connected`` models the gNB-CU's NG
        association -- TS 38.413 NG Setup -- up once at least one gNB
        is provisioned)."""
        degraded_gnb_refs = set()
        for bearer in self._bearers.values():
            entry = self._gnbs.get(bearer.gnb_ref)
            cell = entry.cells.get(bearer.cell_id) if entry is not None else None
            if cell is None or cell.state != CellState.ACTIVE:
                degraded_gnb_refs.add(bearer.gnb_ref)
        gnb_states: list = []
        cu_states: list = []
        du_states: list = []
        ru_states: list = []
        cell_states: Dict[str, str] = {}
        for gnb_ref, entry in self._gnbs.items():
            elements = (entry.topology.cu, *entry.topology.dus, *entry.topology.rus)
            if any(element.state == HealthState.FAILED for element in elements):
                gnb_state = HealthState.FAILED
            elif (
                any(element.state == HealthState.DEGRADED for element in elements)
                or any(cell.state == CellState.INACTIVE for cell in entry.cells.values())
                or gnb_ref in degraded_gnb_refs
            ):
                gnb_state = HealthState.DEGRADED
            else:
                gnb_state = HealthState.HEALTHY
            gnb_states.append(gnb_state)
            cu_states.append(entry.topology.cu.state)
            du_states.extend(du.state for du in entry.topology.dus)
            ru_states.extend(ru.state for ru in entry.topology.rus)
            for cell_id, cell in entry.cells.items():
                cell_states[cell_id] = cell.state
        if any(state == HealthState.FAILED for state in gnb_states):
            overall_gnb = HealthState.FAILED
        elif any(state == HealthState.DEGRADED for state in gnb_states):
            overall_gnb = HealthState.DEGRADED
        else:
            overall_gnb = HealthState.HEALTHY
        if any(state == HealthState.FAILED for state in cu_states):
            overall_cu = HealthState.FAILED
        elif any(state == HealthState.DEGRADED for state in cu_states):
            overall_cu = HealthState.DEGRADED
        else:
            overall_cu = HealthState.HEALTHY
        return {
            "gnb_state": overall_gnb,
            "cu_state": overall_cu,
            "du_states": du_states,
            "ru_states": ru_states,
            "cell_states": dict(sorted(cell_states.items())),
            "ngap_connected": bool(self._gnbs),
        }

    def _resources_view(self) -> Dict[str, Any]:
        """Integer PRB/RRC/DRB accounting (1 PRB per bearer; INACTIVE
        cells carry no active capacity or reservation -- engine
        ``_resource_snapshot`` semantics)."""
        active = tuple(
            cell
            for entry in self._gnbs.values()
            for cell in entry.cells.values()
            if cell.state == CellState.ACTIVE
        )
        prb_used = 0
        for bearer in self._bearers.values():
            entry = self._gnbs.get(bearer.gnb_ref)
            cell = entry.cells.get(bearer.cell_id) if entry is not None else None
            if cell is not None and cell.state == CellState.ACTIVE:
                prb_used += 1
        return {
            "prb_total": sum(cell.prb_count for cell in active),
            "prb_used": prb_used,
            "rrc_connected_ue_count": len(self._bearers),
            "active_drb_count": len(self._bearers),
        }

    def _state_view(self) -> Dict[str, Any]:
        """The ``GET /state`` body: health + resources + the FIRST
        provisioned gNB's topology (the engine's single-split
        observation view)."""
        topology: Optional[Dict[str, Any]] = None
        for entry in self._gnbs.values():
            topology = entry.topology.to_dict()
            break
        return {
            "health": self._health_view(),
            "resources": self._resources_view(),
            "topology": topology,
        }

    def _first_active_cell_with_capacity(self) -> Optional[Tuple[str, str, CellDescriptor]]:
        """The deterministic bind choice: the FIRST active cell with a
        free PRB (gNB insertion order, then cell insertion order)."""
        for gnb_ref, entry in self._gnbs.items():
            for cell_id, cell in entry.cells.items():
                if cell.state != CellState.ACTIVE:
                    continue
                used = sum(
                    1
                    for bearer in self._bearers.values()
                    if bearer.gnb_ref == gnb_ref and bearer.cell_id == cell_id
                )
                if used < cell.prb_count:
                    return gnb_ref, cell_id, cell
        return None

    # ------------------------------------------------------------------
    # Endpoint handlers
    # ------------------------------------------------------------------

    def _handle_provision(self, body: bytes) -> Tuple[int, bytes]:
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        try:
            raw_cells = request.get("cells")
            if not isinstance(raw_cells, list) or not raw_cells:
                raise KeyError("cells")
            if any(not isinstance(raw, dict) for raw in raw_cells):
                raise KeyError("cells")
            cells = tuple(
                CellSpec(
                    cell_id=raw["cell_id"],
                    band=raw["band"],
                    duplex=raw["duplex"],
                    numerology=raw["numerology"],
                    arfcn=raw["arfcn"],
                    prb_count=raw["prb_count"],
                )
                for raw in raw_cells
            )
            provision = GnbProvisionRequest(
                gnb_name=request["name"],
                cells=cells,
                topology=self._parse_topology(request.get("topology")),
            )
            validate_gnb_provision_request(provision)
        except (KeyError, TypeError, ValueError):
            return _error(400, "invalid-input")
        sequence = self._next_sequence()
        gnb_ref = _mint_ref(
            "gnb",
            {
                "gnb_name": provision.gnb_name,
                "cells": [cell.to_dict() for cell in provision.cells],
                "topology": provision.topology.to_dict(),
                "sequence": sequence,
            },
        )
        if gnb_ref in self._gnbs:
            return _error(409, "binding-exists")
        self._gnbs[gnb_ref] = _PeerGnbEntry(
            gnb_name=provision.gnb_name,
            cells={
                cell.cell_id: CellDescriptor(
                    cell_id=cell.cell_id,
                    band=cell.band,
                    duplex=cell.duplex,
                    numerology=cell.numerology,
                    arfcn=cell.arfcn,
                    prb_count=cell.prb_count,
                    state=CellState.INACTIVE,
                )
                for cell in provision.cells
            },
            topology=provision.topology,
        )
        return _json_response(201, {"gnb_ref": gnb_ref})

    @staticmethod
    def _parse_topology(raw: Any) -> RanSplitTopology:
        if not isinstance(raw, dict):
            raise KeyError("topology")
        cu_raw = raw.get("cu")
        dus_raw = raw.get("dus")
        rus_raw = raw.get("rus")
        if not isinstance(cu_raw, dict) or not isinstance(dus_raw, list) or not isinstance(rus_raw, list):
            raise KeyError("topology")
        if any(not isinstance(item, dict) for item in dus_raw + rus_raw):
            raise KeyError("topology")
        if any(not isinstance(item.get("cell_ids"), list) for item in dus_raw):
            raise KeyError("topology")
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
            raise KeyError("topology") from None

    def _handle_decommission(self, gnb_ref: str) -> Tuple[int, bytes]:
        entry = self._gnbs.get(gnb_ref)
        if entry is None:
            return _error(404, "gnb-unknown")
        if any(bearer.gnb_ref == gnb_ref for bearer in self._bearers.values()):
            return _error(409, "binding-exists")
        del self._gnbs[gnb_ref]
        return _json_response(200, {"status": "decommissioned"})

    def _handle_cell_transition(self, gnb_ref: str, cell_id: str, action: str) -> Tuple[int, bytes]:
        entry = self._gnbs.get(gnb_ref)
        if entry is None:
            return _error(404, "gnb-unknown")
        cell = entry.cells.get(cell_id)
        if cell is None:
            return _error(404, "cell-unknown")
        target = CellState.ACTIVE if action == "activate" else CellState.INACTIVE
        if cell.state == target:
            return _error(400, "invalid-input")
        entry.cells[cell_id] = CellDescriptor(
            cell_id=cell.cell_id,
            band=cell.band,
            duplex=cell.duplex,
            numerology=cell.numerology,
            arfcn=cell.arfcn,
            prb_count=cell.prb_count,
            state=target,
        )
        return _json_response(
            200, {"status": "active" if target == CellState.ACTIVE else "inactive"}
        )

    def _handle_bind(self, body: bytes) -> Tuple[int, bytes]:
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        session_id = request.get("session_id")
        requirements = request.get("requirements")
        if requirements is not None and not isinstance(requirements, dict):
            return _error(400, "invalid-input")
        if not isinstance(session_id, str):
            return _error(400, "invalid-input")
        try:
            validate_session_id(session_id)
        except ValueError:
            return _error(400, "invalid-input")
        if not self._gnbs:
            return _error(404, "gnb-unknown")
        choice = self._first_active_cell_with_capacity()
        if choice is None:
            return _error(503, "ran-unavailable")
        gnb_ref, cell_id, _cell = choice
        rnti = self._rnti_next
        if rnti > LAST_RNTI:
            return _error(503, "ran-unavailable")
        self._rnti_next += 1
        sequence = self._next_sequence()
        ue_ref = _mint_ref("ue", {"session_id": session_id, "rnti": rnti, "sequence": sequence})
        ue_context = RanUeContext(
            ue_ref=ue_ref,
            rnti=rnti,
            drbs=(RanDrb(drb_id=1, qfi=5),),
        )
        bearer_ref = _mint_ref(
            "bearer",
            {
                "session_id": session_id,
                "gnb_ref": gnb_ref,
                "cell_id": cell_id,
                "rnti": rnti,
                "sequence": sequence,
            },
        )
        if bearer_ref in self._bearers:
            return _error(409, "binding-exists")
        self._bearers[bearer_ref] = _PeerBearerEntry(
            session_id=session_id,
            gnb_ref=gnb_ref,
            cell_id=cell_id,
            ue_context=ue_context,
        )
        # Only the opaque ref + the mapped serving cell cross the wire
        # -- the UE context (RNTI/DRB/QFI) is peer-private.
        return _json_response(201, {"bearer_ref": bearer_ref, "cell_id": cell_id})

    def _handle_unbind(self, bearer_ref: str) -> Tuple[int, bytes]:
        if bearer_ref not in self._bearers:
            return _error(404, "bearer-unknown")
        del self._bearers[bearer_ref]
        return _json_response(200, {"status": "released"})

    def _handle_data(self, bearer_ref: str, body: bytes) -> Tuple[int, bytes]:
        bearer = self._bearers.get(bearer_ref)
        if bearer is None:
            return _error(404, "bearer-unknown")
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        payload_b64 = request.get("payload_b64")
        if not isinstance(payload_b64, str) or not payload_b64:
            return _error(400, "invalid-input")
        try:
            payload = base64.b64decode(payload_b64, validate=True)
        except (TypeError, ValueError):
            return _error(400, "invalid-input")
        entry = self._gnbs.get(bearer.gnb_ref)
        cell = entry.cells.get(bearer.cell_id) if entry is not None else None
        if cell is None or cell.state != CellState.ACTIVE:
            return _error(503, "ran-unavailable")
        # Byte-identical user-plane echo (the DN/UE-application echo
        # analog of the WORK-019 conformance peer).
        echoed = base64.b64encode(payload).decode("ascii")
        return _json_response(200, {"payload_b64": echoed})

    def _handle_allocate(self, body: bytes) -> Tuple[int, bytes]:
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        kind = request.get("kind")
        quantity_base = request.get("quantity_base")
        purpose = request.get("purpose")
        if not isinstance(kind, str) or kind not in RAN_ALLOCATION_KINDS:
            return _error(400, "invalid-input")
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int) or quantity_base < 0:
            return _error(400, "invalid-input")
        if not isinstance(purpose, str) or not purpose:
            return _error(400, "invalid-input")
        try:
            reject_credential_like_text(purpose, what="purpose")
        except ValueError:
            return _error(400, "invalid-input")
        sequence = self._next_sequence()
        alloc_ref = _mint_ref(
            "alloc",
            {
                "kind": kind,
                "quantity_base": quantity_base,
                "purpose": purpose,
                "sequence": sequence,
            },
        )
        if alloc_ref in self._allocations:
            return _error(409, "binding-exists")
        self._allocations[alloc_ref] = purpose
        return _json_response(201, {"technology_ref": alloc_ref})

    def _handle_release(self, alloc_ref: str) -> Tuple[int, bytes]:
        if alloc_ref not in self._allocations:
            return _error(404, "allocation-unknown")
        del self._allocations[alloc_ref]
        return _json_response(200, {"status": "released"})
