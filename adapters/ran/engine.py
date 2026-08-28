"""ADCOS 5G RAN integration reference engine (WORK-020).

:class:`ReferenceRanEngine` is the ADCOS REFERENCE MODEL of the 5G RAN
integration contract -- NOT a real RAN stack.  It is HONESTLY
NON-CONFIDENTIAL: no radio, no SDR, no 3GPP RRC/NGAP/F1/E1 state
machine, and no vendor or Open RAN API is implemented or imported here
(LOCK-016: external RAN/modem/SDR implementations remain behind
adapter/provider interfaces; LOCK-017: vendor implementations are not
ADCOS authority).  It models the 3GPP TS 38.300 (NR overall), TS 38.401
(NG-RAN CU/DU architecture), TS 38.473 (F1), TS 38.463 (E1),
O-RAN.WG4 (open fronthaul 7-2x), TS 38.331 (RRC), TS 38.321 (MAC),
TS 38.413 (NGAP) and TS 23.501 §5.4 (QoS flow to DRB mapping)
reference SHAPES in-memory, so the manager, sandbox, bridge, and
conformance layers and the deterministic selftest battery have a
COMPLETE, BYTE-STABLE contract implementation to run against (the
WORK-019 ``Reference5GCoreEngine`` analog).  Concrete RAN stacks --
OpenAirInterface, O-CU/O-DU/O-RU-style open implementations, a future
RAN -- plug in behind the same :class:`RanContract` without modifying
the manager or any core semantics (LOCK-002/016/018).

The reference engine is RAN-STATE-OUT (LOCK-016/017): its in-memory
gNB/cell/bearer/UE-context state lives in the ADAPTER package, NEVER
in the ADCOS core.  The manager's snapshot carries only
integration-instance state (bindings, events) -- NEVER RAN state.

The reference engine is IDENTITY-SEPARATE (LOCK-006, R1): every
reference it mints is content-derived over
:func:`protocol.canonicalization.canonical_json_bytes` (sha256,
truncated to 32 hex chars) from operation CONTENT plus a deterministic
sequence counter -- never ``urandom``, never wall clock, and never the
sacred ``session_id`` itself (the session id only ever enters hashed
ref content, exactly as the WORK-019 engine derives PDU session ids;
the minted string can never equal or embed it).

Determinism: two runs of the same operation sequence against a fresh
engine produce byte-identical references and observations (dict
insertion order is deterministic; sorted keys wherever the model
exposes a mapping).  Documented reference-model choices:

* **Cell deactivation degrades, never kills.**  Deactivating a cell
  with live bearers moves health to DEGRADED and the bearers stay
  (mirroring how the WORK-019 reference engine models an NF failure:
  an honest DEGRADED state, not a silent teardown); ``egress_data``
  on such a bearer fails closed with ``RAN_UNAVAILABLE`` until the
  cell is active again.
* **One PRB per bearer.**  Each bearer reserves exactly 1 PRB on its
  serving cell (the minimal deterministic QoS model; a real gNB's
  scheduler enforces the requested QoS behind the seam -- TS 23.501
  §5.4).  ``prb_used`` counts only bearers whose cell is ACTIVE (an
  INACTIVE cell carries no active reservation, keeping the frozen
  ``prb_used <= prb_total`` invariant honest).
* **Single-split observation view.**  ``RanObservation.topology``
  carries ONE :class:`~adapters.ran.model.RanSplitTopology` (its
  single-CU shape models one split view), so the reference reports the
  FIRST provisioned gNB's topology in insertion order; multi-gNB
  inventories are carried by the per-gNB ``GnbView`` projections, not
  by the observation.
* **NGAP model.**  ``ngap_connected`` is up iff the integration is
  open (the reference models the gNB-CU's NG association; the real
  NGAP state lives behind the seam, TS 38.413).
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from .contract import RanContext, RanContract
from .errors import RanError, RanReasonCode
from .model import (
    CellDescriptor,
    CellState,
    DuplexMode,
    GnbProvisionRequest,
    HealthState,
    LinkMetricName,
    RAN_CAPABILITY_CELL_FDD,
    RAN_CAPABILITY_CELL_TDD,
    RAN_CAPABILITY_CU_DU_SPLIT_F1,
    RAN_CAPABILITY_DRB_QOS_FLOW,
    RAN_CAPABILITY_GNB_PROVISION,
    RAN_CAPABILITY_O_RU_FRONTHAUL,
    RAN_CAPABILITY_REFERENCES,
    RanDrb,
    RanHealthSnapshot,
    RanObservation,
    RanResourceSnapshot,
    RanSplitOption,
    RanSplitTopology,
    RanUeContext,
)
from .validation import (
    reject_credential_like_text,
    validate_gnb_provision_request,
    validate_opaque_ref,
    validate_session_id,
)

__all__ = [
    "ReferenceRanEngine",
    "RAN_ALLOCATION_KIND_PRB",
    "RAN_ALLOCATION_KIND_CELL",
    "RAN_ALLOCATION_KIND_RADIO_CAPACITY",
    "RAN_ALLOCATION_KINDS",
    "FIRST_RNTI",
    "LAST_RNTI",
]

#: Radio-capacity allocation kinds (the WORK-016 ``allocate`` kind
#: vocabulary for the RAN family): physical resource blocks, cells,
#: and aggregate radio capacity -- integer base units only.
RAN_ALLOCATION_KIND_PRB = "ran.prb"
RAN_ALLOCATION_KIND_CELL = "ran.cell"
RAN_ALLOCATION_KIND_RADIO_CAPACITY = "ran.radio-capacity"
RAN_ALLOCATION_KINDS: Tuple[str, ...] = (
    RAN_ALLOCATION_KIND_PRB,
    RAN_ALLOCATION_KIND_CELL,
    RAN_ALLOCATION_KIND_RADIO_CAPACITY,
)

#: First RNTI the deterministic counter allocates (TS 38.321 §7.1:
#: 16-bit RNTI space with 0x0000/0xFFFF reserved; the reference draws
#: from the C-RNTI-style range starting at 0x4601).
FIRST_RNTI = 0x4601

#: Last allocatable RNTI (the model's frozen 1..65534 range).
LAST_RNTI = 65534

#: Reference suffix length: the truncated sha256 hexdigest carried by
#: every minted ``ran:<kind>:<hex>`` reference.
_REF_DIGEST_LENGTH = 32


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mint_ref(kind: str, material: Mapping[str, Any]) -> str:
    """Content-derive an opaque RAN-side reference.

    Deterministic (sha256 over canonical JSON bytes of the operation
    content + the engine's sequence counter): never ``urandom``, never
    wall clock.  The minted reference is self-checked against the
    frozen seam grammar and the LOCK-023 credential scan before it
    leaves the engine (defense in depth; the sandbox re-checks).
    """
    digest = _sha256_hex(canonical_json_bytes(dict(material)))
    ref = "ran:%s:%s" % (kind, digest[:_REF_DIGEST_LENGTH])
    validate_opaque_ref(ref, prefix=kind)
    reject_credential_like_text(ref, what="%s reference" % kind)
    return ref


class _GnbEntry:
    """Adapter-private provisioned-gNB record (never core state)."""

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


class _BearerEntry:
    """Adapter-private bound-bearer record.

    ``session_id`` is stored EXACTLY as provided (LOCK-006: the sacred,
    access-independent session identity is a read-only passthrough;
    the engine never mutates, re-derives, or echoes it as a RAN
    handle).  The UE context (RNTI/DRB/QFI) is adapter-private opaque
    state; the core sees only the opaque ``ran:bearer:<hex>`` ref.
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


class ReferenceRanEngine(RanContract):
    """The deterministic in-memory 5G RAN reference model (WORK-020).

    Implements all 14 :class:`RanContract` operations in-memory.  No
    radio, no SDR, no 3GPP state machine, no vendor/Open RAN API (the
    conformance peer carries the real radio bytes; this engine is the
    deterministic model CI runs offline).  The engine charges NO steps
    itself: the sandbox mediating it charges the family's fixed
    ``STEP_CHARGES`` table per operation, so the total deterministic
    cost of an operation is fixed at the mediator (mirrors the WORK-016
    ``GenericAdapter`` budget discipline).
    """

    label = "reference-ran-engine"

    def __init__(self) -> None:
        self._open = False
        # Deterministic sequence counter for content-derived refs (no
        # randomness; reset on construction and on close; increments
        # predictably per minted reference, so byte-identical
        # snapshots across runs hold).
        self._sequence = 0
        # Deterministic RNTI counter (TS 38.321 §7.1).
        self._rnti_next = FIRST_RNTI
        # gnb_ref -> provisioned gNB (insertion order = provision order).
        self._gnbs: Dict[str, _GnbEntry] = {}
        # bearer_ref -> bound bearer (session_id stored EXACTLY as given).
        self._bearers: Dict[str, _BearerEntry] = {}
        # alloc_ref -> purpose (radio-capacity reservations).
        self._allocations: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Internal helpers (adapter-private RAN state)
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "engine not open")

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _gnb_entry(self, gnb_ref: str) -> _GnbEntry:
        entry = self._gnbs.get(gnb_ref)
        if entry is None:
            raise RanError(
                RanReasonCode.GNB_UNKNOWN,
                "gnb %s not found" % gnb_ref,
            )
        return entry

    def _cell_descriptor(self, gnb_ref: str, cell_id: str) -> CellDescriptor:
        entry = self._gnb_entry(gnb_ref)
        cell = entry.cells.get(cell_id)
        if cell is None:
            raise RanError(
                RanReasonCode.CELL_UNKNOWN,
                "cell %s not found on gnb" % cell_id,
            )
        return cell

    def _bearer_entry(self, bearer_ref: str) -> _BearerEntry:
        entry = self._bearers.get(bearer_ref)
        if entry is None:
            raise RanError(
                RanReasonCode.BEARER_UNKNOWN,
                "bearer %s not found" % bearer_ref,
            )
        return entry

    def _active_cells(self) -> Tuple[CellDescriptor, ...]:
        return tuple(
            cell
            for entry in self._gnbs.values()
            for cell in entry.cells.values()
            if cell.state == CellState.ACTIVE
        )

    def _prbs_used_on_cell(self, gnb_ref: str, cell_id: str) -> int:
        return sum(
            1
            for bearer in self._bearers.values()
            if bearer.gnb_ref == gnb_ref and bearer.cell_id == cell_id
        )

    def _bearer_cell_active(self, bearer: _BearerEntry) -> bool:
        entry = self._gnbs.get(bearer.gnb_ref)
        if entry is None:
            return False
        cell = entry.cells.get(bearer.cell_id)
        return cell is not None and cell.state == CellState.ACTIVE

    def _first_active_cell_with_capacity(self) -> Optional[Tuple[str, str, CellDescriptor]]:
        """The deterministic bind choice: the FIRST active cell with a
        free PRB, in gNB insertion order then cell insertion order."""
        for gnb_ref, entry in self._gnbs.items():
            for cell_id, cell in entry.cells.items():
                if cell.state != CellState.ACTIVE:
                    continue
                if self._prbs_used_on_cell(gnb_ref, cell_id) < cell.prb_count:
                    return gnb_ref, cell_id, cell
        return None

    # ------------------------------------------------------------------
    # Capability / health / resource / topology snapshots
    # ------------------------------------------------------------------

    def _current_capabilities(self) -> Tuple[str, ...]:
        """The capability-id REFERENCES the reference currently serves
        (exposure only; WORK-005 registry semantics -- never minted),
        in frozen catalog order for determinism."""
        if not self._open:
            return ()
        served = {RAN_CAPABILITY_GNB_PROVISION}
        active = self._active_cells()
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

    def _health_snapshot(self) -> RanHealthSnapshot:
        """The per-element health snapshot (adapter-reported DATA).

        Aggregate rule (frozen in the model): any element FAILED ->
        FAILED; else any element DEGRADED, any cell INACTIVE, or any
        live bearer on an INACTIVE/missing cell -> DEGRADED; else
        HEALTHY.  A live bearer referencing an unknown gNB is FAILED
        (defensive only -- decommission fails closed under live
        bearers, so the engine cannot reach that state).
        """
        bearer_on_unknown_gnb = False
        degraded_gnb_refs = set()
        for bearer in self._bearers.values():
            entry = self._gnbs.get(bearer.gnb_ref)
            if entry is None:
                bearer_on_unknown_gnb = True
                continue
            cell = entry.cells.get(bearer.cell_id)
            if cell is None or cell.state != CellState.ACTIVE:
                degraded_gnb_refs.add(bearer.gnb_ref)

        gnb_states: list = []
        cu_states: list = []
        du_states: list = []
        ru_states: list = []
        cell_states: Dict[str, str] = {}
        for gnb_ref, entry in self._gnbs.items():
            elements = (entry.topology.cu, *entry.topology.dus, *entry.topology.rus)
            element_failed = any(
                element.state == HealthState.FAILED for element in elements
            )
            element_degraded = any(
                element.state == HealthState.DEGRADED for element in elements
            )
            cells_inactive = any(
                cell.state == CellState.INACTIVE for cell in entry.cells.values()
            )
            if element_failed:
                gnb_state = HealthState.FAILED
            elif (
                element_degraded
                or cells_inactive
                or gnb_ref in degraded_gnb_refs
            ):
                gnb_state = HealthState.DEGRADED
            else:
                gnb_state = HealthState.HEALTHY
            gnb_states.append(gnb_state)
            cu_states.append(entry.topology.cu.state)
            du_states.extend(du.state for du in entry.topology.dus)
            ru_states.extend(ru.state for ru in entry.topology.rus)
            # Cell ids are unique within a gNB (enforced at provision);
            # across gNBs the reference merges into the flat snapshot
            # (deterministic insertion order).
            for cell_id, cell in entry.cells.items():
                cell_states[cell_id] = cell.state

        if bearer_on_unknown_gnb or any(
            state == HealthState.FAILED for state in gnb_states
        ):
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
        return RanHealthSnapshot(
            gnb_state=overall_gnb,
            cu_state=overall_cu,
            du_states=tuple(du_states),
            ru_states=tuple(ru_states),
            cell_states=cell_states,
            ngap_connected=self._open,
        )

    def _resource_snapshot(self) -> RanResourceSnapshot:
        """Integer PRB/UE/DRB accounting (mapped DATA, never WORK-008
        fabric authority).

        ``prb_total`` sums the PRB capacity of the ACTIVE cells; each
        live bearer reserves 1 PRB on its cell; a bearer whose cell is
        INACTIVE parks its reservation (the cell carries no active
        capacity), which keeps ``prb_used <= prb_total`` honest.
        """
        active = self._active_cells()
        prb_total = sum(cell.prb_count for cell in active)
        prb_used = sum(1 for bearer in self._bearers.values() if self._bearer_cell_active(bearer))
        return RanResourceSnapshot(
            prb_total=prb_total,
            prb_used=prb_used,
            rrc_connected_ue_count=len(self._bearers),
            active_drb_count=len(self._bearers),
        )

    def _link_metrics(self) -> Dict[str, int]:
        """Generic link metrics (the WORK-016 six-name vocabulary;
        deterministic counters mirroring ``GenericAdapter.observe``)."""
        link_up = 1 if (self._open and self._active_cells()) else 0
        return {
            LinkMetricName.LINK_UP: link_up,
            LinkMetricName.RX_BYTES_TOTAL: 1000 * self._sequence,
            LinkMetricName.TX_BYTES_TOTAL: 1000 * self._sequence,
            LinkMetricName.RX_ERROR_COUNT: 0,
            LinkMetricName.TX_ERROR_COUNT: 0,
            LinkMetricName.RETRANSMIT_COUNT: 0,
        }

    # ------------------------------------------------------------------
    # Contract operations
    # ------------------------------------------------------------------

    def open(self, context: RanContext) -> None:
        if self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "engine already open")
        self._open = True

    def close(self, context: RanContext) -> None:
        """Fails closed while live bearers exist, then clears state
        (mirror of the WORK-019 close discipline: the integration never
        tears a live session-to-bearer mapping out from under an
        application)."""
        if not self._open:
            raise RanError(RanReasonCode.NOT_OPEN, "engine not open")
        if self._bearers:
            raise RanError(
                RanReasonCode.BINDING_EXISTS,
                "cannot close the RAN integration while %d radio "
                "bearer(s) are live (fail closed)" % len(self._bearers),
            )
        self._open = False
        self._gnbs = {}
        self._bearers = {}
        self._allocations = {}
        # Reset the deterministic counters so a close/reopen replay of
        # the same operation sequence mints identical references.
        self._sequence = 0
        self._rnti_next = FIRST_RNTI

    def capabilities(self) -> Tuple[str, ...]:
        return self._current_capabilities()

    def observe(self, context: RanContext) -> RanObservation:
        self._require_open()
        if not self._gnbs:
            # The frozen observation shape requires at least one
            # reported cell (validate_ran_observation), so an empty
            # RAN fails closed instead of emitting a non-contract
            # snapshot.
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "no provisioned gnb to observe (the frozen observation "
                "shape requires at least one reported cell)",
            )
        # Single-split view: the FIRST provisioned gNB's topology (the
        # observation's single-CU shape models one split view; see the
        # module docstring).
        first_topology: RanSplitTopology = next(iter(self._gnbs.values())).topology
        return RanObservation(
            capabilities=self._current_capabilities(),
            health=self._health_snapshot(),
            resources=self._resource_snapshot(),
            topology=first_topology,
            link_metrics=self._link_metrics(),
        )

    def provision_gnb(self, context: RanContext, *, request: GnbProvisionRequest) -> str:
        """Provision a gNB: cells start INACTIVE (TS 38.413 activation
        is a separate, explicit step)."""
        self._require_open()
        validate_gnb_provision_request(request)
        sequence = self._next_sequence()
        gnb_ref = _mint_ref(
            "gnb",
            {
                "gnb_name": request.gnb_name,
                "cells": [cell.to_dict() for cell in request.cells],
                "topology": request.topology.to_dict(),
                "sequence": sequence,
            },
        )
        if gnb_ref in self._gnbs:
            raise RanError(
                RanReasonCode.BINDING_EXISTS,
                "gnb reference collision (identical provision already "
                "exists)",
            )
        cells: Dict[str, CellDescriptor] = {}
        for cell in request.cells:
            cells[cell.cell_id] = CellDescriptor(
                cell_id=cell.cell_id,
                band=cell.band,
                duplex=cell.duplex,
                numerology=cell.numerology,
                arfcn=cell.arfcn,
                prb_count=cell.prb_count,
                state=CellState.INACTIVE,
            )
        self._gnbs[gnb_ref] = _GnbEntry(
            gnb_name=request.gnb_name,
            cells=cells,
            topology=request.topology,
        )
        return gnb_ref

    def decommission_gnb(self, context: RanContext, *, gnb_ref: str) -> None:
        entry = self._gnb_entry(gnb_ref)
        if any(bearer.gnb_ref == gnb_ref for bearer in self._bearers.values()):
            raise RanError(
                RanReasonCode.BINDING_EXISTS,
                "gnb %s still serves live bearers (fail closed)" % entry.gnb_name,
            )
        del self._gnbs[gnb_ref]

    def activate_cell(self, context: RanContext, *, gnb_ref: str, cell_id: str) -> None:
        """Activate a served cell (strict: activating an ACTIVE cell
        is a caller state error -- mirrors the WORK-019 double-open
        discipline)."""
        self._require_open()
        cell = self._cell_descriptor(gnb_ref, cell_id)
        if cell.state == CellState.ACTIVE:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "cell %s is already active" % cell_id,
            )
        entry = self._gnbs[gnb_ref]
        entry.cells[cell_id] = CellDescriptor(
            cell_id=cell.cell_id,
            band=cell.band,
            duplex=cell.duplex,
            numerology=cell.numerology,
            arfcn=cell.arfcn,
            prb_count=cell.prb_count,
            state=CellState.ACTIVE,
        )

    def deactivate_cell(self, context: RanContext, *, gnb_ref: str, cell_id: str) -> None:
        """Deactivate a served cell.

        DOCUMENTED CHOICE (per the WORK-020 brief): deactivation
        DEGRADES, it never kills -- live bearers on the cell stay
        (honest DEGRADED health, mirroring the WORK-019 NF-failure
        model) and ``egress_data`` on them fails closed with
        ``RAN_UNAVAILABLE`` until the cell is active again.
        """
        self._require_open()
        cell = self._cell_descriptor(gnb_ref, cell_id)
        if cell.state == CellState.INACTIVE:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "cell %s is already inactive" % cell_id,
            )
        entry = self._gnbs[gnb_ref]
        entry.cells[cell_id] = CellDescriptor(
            cell_id=cell.cell_id,
            band=cell.band,
            duplex=cell.duplex,
            numerology=cell.numerology,
            arfcn=cell.arfcn,
            prb_count=cell.prb_count,
            state=CellState.INACTIVE,
        )

    def bind_session(
        self,
        context: RanContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> str:
        """Create a radio bearer for a WORK-012 session.

        The ``session_id`` is stored EXACTLY as provided (LOCK-006:
        read-only passthrough).  The deterministic cell choice is the
        FIRST active cell with a free PRB (gNB insertion order, then
        cell insertion order).  The UE context (RNTI from the
        deterministic counter, DRB id 1, QFI 5 -- TS 38.321/38.331/
        23.501 §5.4 shapes) is adapter-private; the caller sees only
        the opaque ``ran:bearer:<hex>`` reference.
        """
        self._require_open()
        validate_session_id(session_id)
        if requirements is not None and not isinstance(requirements, Mapping):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "requirements must be a mapping or None",
            )
        if not self._gnbs:
            raise RanError(
                RanReasonCode.GNB_UNKNOWN,
                "no gnb provisioned to serve on",
            )
        choice = self._first_active_cell_with_capacity()
        if choice is None:
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "no active cell with free PRB capacity",
            )
        gnb_ref, cell_id, _cell = choice
        rnti = self._rnti_next
        if rnti > LAST_RNTI:
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "RNTI space exhausted (TS 38.321 §7.1)",
            )
        self._rnti_next += 1
        sequence = self._next_sequence()
        ue_ref = _mint_ref(
            "ue",
            {"session_id": session_id, "rnti": rnti, "sequence": sequence},
        )
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
            raise RanError(
                RanReasonCode.BINDING_EXISTS,
                "bearer reference collision (binding already exists)",
            )
        self._bearers[bearer_ref] = _BearerEntry(
            session_id=session_id,
            gnb_ref=gnb_ref,
            cell_id=cell_id,
            ue_context=ue_context,
        )
        return bearer_ref

    def unbind_session(self, context: RanContext, *, bearer_ref: str) -> None:
        """Tear down a radio bearer: removes the adapter-private UE
        context; the 1-PRB reservation is derived from live bearers,
        so removal releases it."""
        self._bearer_entry(bearer_ref)
        del self._bearers[bearer_ref]

    def egress_data(
        self,
        context: RanContext,
        *,
        bearer_ref: str,
        payload: bytes,
    ) -> bytes:
        """Carry the payload over the bearer's user plane.

        Byte-stable in-memory model: the payload is returned unchanged
        (exactly the WORK-019 ``Reference5GCoreEngine.egress_pdu``
        behavior -- the conformance peer carries the real radio bytes;
        this engine models the contract shape only).  Fails closed
        with ``RAN_UNAVAILABLE`` when the bearer's serving cell is not
        active (honest DEGRADED-state behavior).
        """
        self._require_open()
        if not isinstance(payload, (bytes, bytearray)):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "payload must be bytes",
            )
        bearer = self._bearer_entry(bearer_ref)
        if not self._bearer_cell_active(bearer):
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "bearer's serving cell is not active (honest fail-closed)",
            )
        return bytes(payload)

    def allocate(
        self,
        context: RanContext,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
    ) -> str:
        """Reserve radio capacity (adapter-scoped, integer base units;
        a mapping into generic resource semantics -- never WORK-008
        fabric accounting)."""
        self._require_open()
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
        self._allocations[alloc_ref] = purpose
        return alloc_ref

    def release(self, context: RanContext, *, technology_ref: str) -> None:
        if technology_ref not in self._allocations:
            raise RanError(
                RanReasonCode.ALLOCATION_UNKNOWN,
                "radio capacity reservation %s not found (already released?)"
                % technology_ref,
            )
        del self._allocations[technology_ref]

    def health(self) -> str:
        """Implementation-local health (reported, never authoritative
        by itself -- LOCK-017): the aggregate rule over the current
        state; fail-closed FAILED when not open."""
        if not self._open:
            return HealthState.FAILED
        return self._health_snapshot().aggregate()
