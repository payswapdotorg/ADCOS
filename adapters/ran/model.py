"""ADCOS 5G RAN integration domain model (WORK-020).

Value types for the 5G RAN integration boundary (the new
``adapters/ran`` sub-package within the frozen ``/adapters`` module
boundary -- ``spec/architecture.md`` §29; LOCK-002 frozen,
non-negotiable: ``5G NR is implemented through an access adapter.
3GPP RAN/core functions remain outside the ADCOS core domain.`` and
the WORK-020 acceptance criteria themselves: ``ADCOS core imports no
vendor/Open RAN implementation types`` / ``RAN capability/health/
resource state is mapped through adapters``).

Standards leverage (LOCK-018, mirroring the W017/W018/W019
discipline): the model uses 3GPP TS 38.300 (NR overall description),
TS 38.401 (NG-RAN architecture: CU/DU), TS 38.473 (F1 application
protocol), TS 38.463 (E1 application protocol), O-RAN.WG4 (open
fronthaul, split 7-2x), TS 38.331 (RRC), TS 38.321 (MAC), TS 38.413
(NGAP), and TS 23.501 §5.4 (QoS flows to DRB mapping) reference
SHAPES as DATA with citations in docstrings -- no invented RAN
primitive, no vendor SDK, no radio, no 3GPP state machine exists in
this module.  The boundary never imports RAN types or identifiers
into the ADCOS core (LOCK-002/016; verified by the WORK-020
selftest's no-core-RAN-leakage audit).

Central boundary (WORK-020):

    RAN INTEGRATION
        != SESSION IDENTITY        (session_id sacred, from WORK-012;
                                    access-independent -- LOCK-006)
        != RAN ROUTE IDENTITY      (bearer/RNTI/DRB refs are RAN-side
                                    identity; never collapse onto
                                    session_id -- R1 invariant)
        != IDENTITY AUTHORITY      (WORK-004)
        != RESOURCE AUTHORITY      (WORK-008; PRB/DRB = mapped DATA)
        != POLICY AUTHORITY        (caller-supplied policy DATA)
        != TOPOLOGY AUTHORITY      (CU/DU/RU boundary mapping is
                                    adapter-owned DATA)
        != ACCESS/VENDOR AUTHORITY (LOCK-016/017; concrete RAN stacks
                                    = adapters, behind the seam)
        != RAN STATE AUTHORITY     (gNB/CU/DU/RU/cell/RRC state lives
                                    in the adapter/conformance peer,
                                    NEVER in ADCOS core)

Determinism rules (mirroring the accepted adapter families): no wall
clock (instants are injected, WORK-003 grammar), no randomness (no
``urandom``/``secrets``/``random`` anywhere in this module), and
integer-only accounting.  Identifiers carried here are opaque
adapter-side strings validated by SHAPE only -- this module never
mints ADCOS authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .validation import (
    reject_credential_like_text,
    validate_ran_capability_reference,
)


# --------------------------------------------------------------------------
# Health / state / duplex vocabularies (frozen)
# --------------------------------------------------------------------------


class HealthState:
    """RAN element health vocabulary (plain string constants, the
    tokens the WORK-016/018/19 families already report: ``HEALTHY``,
    ``DEGRADED``, ``FAILED``).

    Health is REPORTED by implementations and aggregated
    deterministically (see :meth:`RanHealthSnapshot.aggregate`); it is
    never authoritative by itself (LOCK-017: the manager computes the
    effective health from mediated outcomes).
    """

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.HEALTHY, cls.DEGRADED, cls.FAILED)


class CellState:
    """NR cell administrative/operational state (ACTIVE carries
    traffic; INACTIVE carries none -- TS 38.413 cell activation
    semantics as DATA, no RRC state machine here)."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ACTIVE, cls.INACTIVE)


class DuplexMode:
    """NR duplex vocabulary (3GPP TS 38.104 §4.1: TDD or FDD)."""

    TDD = "TDD"
    FDD = "FDD"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.TDD, cls.FDD)


class RanSplitOption:
    """CU/DU/RU split-option vocabulary (labels, DATA only).

    TS 38.401 §5 defines the NG-RAN architecture in which a gNB is a
    logical node assembled from a gNB-CU and one or more gNB-DUs; the
    F1 logical boundary between them is TS 38.473, and the E1
    boundary between gNB-CU-CP and gNB-CU-UP is TS 38.463.  O-RAN.WG4
    defines the open fronthaul between O-DU and O-RU, with split
    7-2x the deployed CUS-plane profile.  The boundary never enforces
    a split -- it maps elements across one (LOCK-016).
    """

    #: The F1 logical boundary between gNB-CU and gNB-DU (TS 38.473).
    F1_CU_DU = "f1-cu-du"
    #: The E1 logical boundary between gNB-CU-CP and gNB-CU-UP
    #: (TS 38.463).
    E1_CU_CU = "e1-cu-cu"
    #: The O-RAN open fronthaul, split 7-2x (O-RAN.WG4 CUS-plane).
    O_RAN_7_2X = "o-ran-7-2x"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.F1_CU_DU, cls.E1_CU_CU, cls.O_RAN_7_2X)


class LinkMetricName:
    """Generic link-metric names for the RAN observation.

    The constant VALUES mirror WORK-016 ``adapters.model.LinkMetricName``
    (``link-up``, ``rx-bytes-total``, ``tx-bytes-total``,
    ``rx-error-count``, ``tx-error-count``, ``retransmit-count``) so a
    RAN observation maps 1:1 into the generic adapter metric
    vocabulary.  The SDK symbols are deliberately NOT imported here --
    the ran family stays import-light in ``model.py`` and the WORK-016
    bridge performs the translation (radio/technology-specific
    counters stay inside implementations; semantics owned by WORK-026).
    """

    LINK_UP = "link-up"
    RX_BYTES_TOTAL = "rx-bytes-total"
    TX_BYTES_TOTAL = "tx-bytes-total"
    RX_ERROR_COUNT = "rx-error-count"
    TX_ERROR_COUNT = "tx-error-count"
    RETRANSMIT_COUNT = "retransmit-count"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.LINK_UP,
            cls.RX_BYTES_TOTAL,
            cls.TX_BYTES_TOTAL,
            cls.RX_ERROR_COUNT,
            cls.TX_ERROR_COUNT,
            cls.RETRANSMIT_COUNT,
        )


# --------------------------------------------------------------------------
# Capability-id reference catalog (EXPOSURE ONLY -- never minted here)
# --------------------------------------------------------------------------

#: A gNB can be provisioned/decommissioned through the boundary.
RAN_CAPABILITY_GNB_PROVISION = "capability.access.ran.gnb-provision"
#: A TDD cell (3GPP TS 38.104 §4.1) is (or can be) served.
RAN_CAPABILITY_CELL_TDD = "capability.access.ran.cell-tdd"
#: An FDD cell (3GPP TS 38.104 §4.1) is (or can be) served.
RAN_CAPABILITY_CELL_FDD = "capability.access.ran.cell-fdd"
#: Data radio bearers mapped to QoS flows (TS 23.501 §5.4).
RAN_CAPABILITY_DRB_QOS_FLOW = "capability.access.ran.drb-qos-flow"
#: CU/DU split with the F1 logical boundary (TS 38.401/38.473).
RAN_CAPABILITY_CU_DU_SPLIT_F1 = "capability.access.ran.cu-du-split-f1"
#: O-RU open fronthaul, split 7-2x (O-RAN.WG4).
RAN_CAPABILITY_O_RU_FRONTHAUL = "capability.access.ran.o-ru-fronthaul-7-2x"

#: The known RAN capability-id reference set.  These strings are
#: REFERENCES into WORK-005 capability-registry semantics (exposure by
#: reference): this module NEVER mints, registers, reinterprets, or
#: mutates capability entries -- the boundary only ever EXPOSES the
#: subset the RAN currently serves.  The ``capability.access.ran.*``
#: namespace is a reserved future extension of the frozen WORK-002
#: registry grammar (which today admits ``capability.core.*`` /
#: ``capability.profile.*``); admitting it is a WORK-005 vocabulary
#: change under ``spec/change-control.md`` -- never an adapter-family
#: action (fail-closed open world; LOCK-018).
RAN_CAPABILITY_REFERENCES: Tuple[str, ...] = (
    RAN_CAPABILITY_GNB_PROVISION,
    RAN_CAPABILITY_CELL_TDD,
    RAN_CAPABILITY_CELL_FDD,
    RAN_CAPABILITY_DRB_QOS_FLOW,
    RAN_CAPABILITY_CU_DU_SPLIT_F1,
    RAN_CAPABILITY_O_RU_FRONTHAUL,
)


# --------------------------------------------------------------------------
# Cell value types (3GPP reference shapes as DATA; no state machine)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CellSpec:
    """An NR cell specification -- the ``provision_gnb`` input shape
    (3GPP TS 38.300 §5.3 / TS 38.104 radio parameters as DATA).

    ``cell_id`` is an OPAQUE adapter-side identifier (non-empty
    string, never the WORK-012 session identity and never core state
    -- LOCK-006/016).  ``band`` is the NR operating band (TS 38.104
    §5.2, a positive integer index); ``duplex`` is TDD or FDD (TS
    38.104 §4.1); ``numerology`` is µ (TS 38.211 §4.2.1: SCS =
    15·2^µ kHz, µ in 0..5); ``arfcn`` is the NR-ARFCN (TS 38.104
    §5.4.2, non-negative); ``prb_count`` is the carrier's PRB
    capacity (TS 38.211 §4.4, 1..273).
    """

    cell_id: str
    band: int
    duplex: str
    numerology: int
    arfcn: int
    prb_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.cell_id, str) or not self.cell_id:
            raise ValueError("cell_id must be a non-empty opaque string")
        reject_credential_like_text(self.cell_id, what="cell_id")
        if isinstance(self.band, bool) or not isinstance(self.band, int):
            raise ValueError("band must be an integer")
        if self.band <= 0:
            raise ValueError("band must be > 0 (3GPP TS 38.104 §5.2 operating band)")
        if self.duplex not in DuplexMode.values():
            raise ValueError(
                "duplex must be one of %s (3GPP TS 38.104 §4.1)"
                % (list(DuplexMode.values()),)
            )
        if isinstance(self.numerology, bool) or not isinstance(self.numerology, int):
            raise ValueError("numerology must be an integer")
        if not (0 <= self.numerology <= 5):
            raise ValueError(
                "numerology (mu) must be in [0, 5] (3GPP TS 38.211 §4.2.1: "
                "SCS = 15*2^mu kHz)"
            )
        if isinstance(self.arfcn, bool) or not isinstance(self.arfcn, int):
            raise ValueError("arfcn must be an integer")
        if self.arfcn < 0:
            raise ValueError("arfcn must be >= 0 (3GPP TS 38.104 §5.4.2 NR-ARFCN)")
        if isinstance(self.prb_count, bool) or not isinstance(self.prb_count, int):
            raise ValueError("prb_count must be an integer")
        if not (1 <= self.prb_count <= 273):
            raise ValueError(
                "prb_count must be in [1, 273] (3GPP TS 38.211 §4.4 carrier PRBs)"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "band": self.band,
            "duplex": self.duplex,
            "numerology": self.numerology,
            "arfcn": self.arfcn,
            "prb_count": self.prb_count,
        }


@dataclass(frozen=True)
class CellDescriptor(CellSpec):
    """A served NR cell: the CellSpec fields plus the cell's state
    (ACTIVE carries traffic; INACTIVE carries none -- TS 38.413 cell
    activation semantics as adapter-side DATA, never an RRC state
    machine in core)."""

    state: str = CellState.INACTIVE

    def __post_init__(self) -> None:
        CellSpec.__post_init__(self)
        if self.state not in CellState.values():
            raise ValueError("cell state must be one of %s" % (list(CellState.values()),))

    def to_dict(self) -> Dict[str, Any]:
        payload = CellSpec.to_dict(self)
        payload["state"] = self.state
        return payload


# --------------------------------------------------------------------------
# CU/DU/RU topology elements (adapter-owned boundary mapping as DATA)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _TopologyElement:
    """Shared shape of a CU/DU/RU topology element.

    The CU/DU/RU boundary mapping (TS 38.401 §5; TS 38.473 F1; TS
    38.463 E1; O-RAN.WG4 fronthaul) is ADAPTER-OWNED DATA: each
    element carries an opaque element id, the split-option label of
    the boundary it terminates, and a health state.  None of it is
    core topology authority (WORK-007) and none of it is a 3GPP state
    machine -- the boundary maps elements, it never runs them
    (LOCK-016/017).
    """

    element_id: str
    split: str
    state: str

    def __post_init__(self) -> None:
        if not isinstance(self.element_id, str) or not self.element_id:
            raise ValueError("element_id must be a non-empty opaque string")
        reject_credential_like_text(self.element_id, what="element_id")
        if self.split not in RanSplitOption.values():
            raise ValueError(
                "split must be one of %s (TS 38.401 §5 / TS 38.473 / "
                "TS 38.463 / O-RAN.WG4)" % (list(RanSplitOption.values()),)
            )
        if self.state not in HealthState.values():
            raise ValueError(
                "element state must be one of %s" % (list(HealthState.values()),)
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "element_id": self.element_id,
            "split": self.split,
            "state": self.state,
        }

    @property
    def kind(self) -> str:
        raise NotImplementedError  # pragma: no cover - concrete classes set it


@dataclass(frozen=True)
class CuElement(_TopologyElement):
    """A central unit element (TS 38.401 §5.1 -- the gNB-CU terminates
    the NG and F1-C control-plane side of an F1 CU/DU split, and the
    E1 control side of a CU-CP/CU-UP split per TS 38.463)."""

    @property
    def kind(self) -> str:
        return "cu"


@dataclass(frozen=True)
class DuElement(_TopologyElement):
    """A distributed unit element (TS 38.401 §5.1 / TS 38.473 -- the
    gNB-DU terminates the F1-D/U user-plane side of the F1 split and
    serves one or more cells, by opaque cell id)."""

    cell_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _TopologyElement.__post_init__(self)
        if not isinstance(self.cell_ids, (tuple, list)):
            raise ValueError("cell_ids must be a sequence of cell id strings")
        seen: list = []
        for cell_id in self.cell_ids:
            if not isinstance(cell_id, str) or not cell_id:
                raise ValueError("each served cell id must be a non-empty string")
            if cell_id in seen:
                raise ValueError("duplicate served cell id %r in DU element" % cell_id)
            seen.append(cell_id)
        object.__setattr__(self, "cell_ids", tuple(self.cell_ids))

    def to_dict(self) -> Dict[str, Any]:
        payload = _TopologyElement.to_dict(self)
        payload["cell_ids"] = list(self.cell_ids)
        return payload

    @property
    def kind(self) -> str:
        return "du"


@dataclass(frozen=True)
class RuElement(_TopologyElement):
    """A radio unit element (O-RAN.WG4 -- the O-RU terminates the open
    fronthaul, split 7-2x the deployed profile; ``band`` is its NR
    operating band, TS 38.104 §5.2)."""

    band: int

    def __post_init__(self) -> None:
        _TopologyElement.__post_init__(self)
        if isinstance(self.band, bool) or not isinstance(self.band, int):
            raise ValueError("ru band must be an integer")
        if self.band <= 0:
            raise ValueError("ru band must be > 0 (3GPP TS 38.104 §5.2 operating band)")

    def to_dict(self) -> Dict[str, Any]:
        payload = _TopologyElement.to_dict(self)
        payload["band"] = self.band
        return payload

    @property
    def kind(self) -> str:
        return "ru"


@dataclass(frozen=True)
class RanSplitTopology:
    """The CU/DU/RU split topology of one gNB (adapter-owned DATA).

    TS 38.401 §5 defines the NG-RAN architecture in which a gNB is a
    logical node assembled from a gNB-CU, one or more gNB-DUs (the F1
    logical boundary, TS 38.473), and -- under the O-RAN open
    fronthaul -- one or more O-RUs (O-RAN.WG4, split 7-2x).  This
    record maps that assembly as DATA; it never instantiates or
    controls a RAN element (LOCK-016: external RAN implementations
    remain behind the adapter boundary).  All element ids are opaque
    adapter-side strings, never core state.
    """

    cu: CuElement
    dus: Tuple[DuElement, ...] = ()
    rus: Tuple[RuElement, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.cu, CuElement):
            raise ValueError("cu must be a CuElement")
        if not isinstance(self.dus, (tuple, list)):
            raise ValueError("dus must be a sequence of DuElement")
        if not isinstance(self.rus, (tuple, list)):
            raise ValueError("rus must be a sequence of RuElement")
        for du in self.dus:
            if not isinstance(du, DuElement):
                raise ValueError("dus must contain only DuElement instances")
        for ru in self.rus:
            if not isinstance(ru, RuElement):
                raise ValueError("rus must contain only RuElement instances")
        seen = [self.cu.element_id]
        for element in tuple(self.dus) + tuple(self.rus):
            if element.element_id in seen:
                raise ValueError(
                    "duplicate topology element id %r" % element.element_id
                )
            seen.append(element.element_id)
        object.__setattr__(self, "dus", tuple(self.dus))
        object.__setattr__(self, "rus", tuple(self.rus))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cu": self.cu.to_dict(),
            "dus": [du.to_dict() for du in self.dus],
            "rus": [ru.to_dict() for ru in self.rus],
        }


@dataclass(frozen=True)
class GnbProvisionRequest:
    """The ``provision_gnb`` input: bring a gNB (TS 38.300 §5 -- a
    logical node serving cells) into the RAN integration.

    ``gnb_name`` is a caller-chosen label; ``cells`` are the served
    cell specifications (at least one); ``topology`` is the CU/DU/RU
    split mapping (adapter-owned DATA).  The provision result is an
    OPAQUE ``ran:gnb:<digest>`` reference (never core state and never
    the sacred ``session_id`` -- LOCK-006/016).  Cross-field topology
    consistency (at least one DU, DU cell coverage) is enforced at
    the seam by
    :func:`adapters.ran.validation.validate_gnb_provision_request`.
    """

    gnb_name: str
    cells: Tuple[CellSpec, ...]
    topology: RanSplitTopology

    def __post_init__(self) -> None:
        if not isinstance(self.gnb_name, str) or not self.gnb_name:
            raise ValueError("gnb_name must be a non-empty string")
        reject_credential_like_text(self.gnb_name, what="gnb_name")
        if not isinstance(self.cells, (tuple, list)):
            raise ValueError("cells must be a sequence of CellSpec")
        if not self.cells:
            raise ValueError("cells must contain at least one cell")
        seen: list = []
        for cell in self.cells:
            if not isinstance(cell, CellSpec):
                raise ValueError("cells must contain only CellSpec instances")
            if cell.cell_id in seen:
                raise ValueError("duplicate cell id %r in provision request" % cell.cell_id)
            seen.append(cell.cell_id)
        object.__setattr__(self, "cells", tuple(self.cells))
        if not isinstance(self.topology, RanSplitTopology):
            raise ValueError("topology must be a RanSplitTopology")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gnb_name": self.gnb_name,
            "cells": [cell.to_dict() for cell in self.cells],
            "topology": self.topology.to_dict(),
        }


# --------------------------------------------------------------------------
# Observation snapshots (adapter-reported DATA, never core authority)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RanHealthSnapshot:
    """The per-element health of the mapped RAN (returned inside
    :class:`RanObservation`).

    ``gnb_state``/``cu_state`` carry the gNB/CU health tokens;
    ``du_states``/``ru_states`` carry one token per DU/RU element (in
    topology order); ``cell_states`` maps each served cell id to its
    ACTIVE/INACTIVE state; ``ngap_connected`` reports whether the NG
    Application Protocol association to the 5G Core (TS 38.413) is
    up.  All of it is DATA reported by the adapter, never core state
    (LOCK-016/017).  Defaults are fail-closed: FAILED elements, no
    cells, NGAP down -- an implementation must affirmatively report
    health.
    """

    gnb_state: str = HealthState.FAILED
    cu_state: str = HealthState.FAILED
    du_states: Tuple[str, ...] = ()
    ru_states: Tuple[str, ...] = ()
    cell_states: Mapping[str, str] = field(default_factory=dict)
    ngap_connected: bool = False

    def __post_init__(self) -> None:
        for name in ("gnb_state", "cu_state"):
            if getattr(self, name) not in HealthState.values():
                raise ValueError(
                    "%s must be one of %s" % (name, list(HealthState.values()))
                )
        for name in ("du_states", "ru_states"):
            states = getattr(self, name)
            if not isinstance(states, (tuple, list)):
                raise ValueError("%s must be a sequence of health tokens" % name)
            for state in states:
                if state not in HealthState.values():
                    raise ValueError(
                        "%s entries must be one of %s"
                        % (name, list(HealthState.values()))
                    )
            object.__setattr__(self, name, tuple(states))
        if not isinstance(self.cell_states, Mapping):
            raise ValueError("cell_states must be a mapping of cell id -> state")
        cells: Dict[str, str] = {}
        for cell_id, state in self.cell_states.items():
            if not isinstance(cell_id, str) or not cell_id:
                raise ValueError("cell_states keys must be non-empty cell id strings")
            if state not in CellState.values():
                raise ValueError(
                    "cell_states values must be one of %s" % (list(CellState.values()),)
                )
            cells[cell_id] = state
        object.__setattr__(self, "cell_states", cells)
        if not isinstance(self.ngap_connected, bool):
            raise ValueError("ngap_connected must be a bool")

    def aggregate(self) -> str:
        """Deterministic aggregate over all element states.

        Rule (frozen): any element FAILED -> FAILED; else any element
        DEGRADED or any cell INACTIVE -> DEGRADED; else HEALTHY.
        """
        states = [self.gnb_state, self.cu_state, *self.du_states, *self.ru_states]
        if HealthState.FAILED in states:
            return HealthState.FAILED
        if HealthState.DEGRADED in states:
            return HealthState.DEGRADED
        if CellState.INACTIVE in self.cell_states.values():
            return HealthState.DEGRADED
        return HealthState.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gnb_state": self.gnb_state,
            "cu_state": self.cu_state,
            "du_states": list(self.du_states),
            "ru_states": list(self.ru_states),
            "cell_states": dict(sorted(self.cell_states.items())),
            "ngap_connected": self.ngap_connected,
        }


@dataclass(frozen=True)
class RanResourceSnapshot:
    """The mapped RAN resource snapshot (integer accounting only).

    ``prb_total``/``prb_used``: physical resource block capacity and
    reservation across the ACTIVE cells (TS 38.211 §4.4 -- one PRB is
    the atomic scheduling unit; counted as integers, never floats).
    ``rrc_connected_ue_count``: UEs in RRC_CONNECTED (TS 38.331 state
    as a COUNT, never a state machine).  ``active_drb_count``: data
    radio bearers currently carrying QoS flows.  A MAPPING into
    generic resource semantics -- never WORK-008 fabric accounting
    authority.
    """

    prb_total: int = 0
    prb_used: int = 0
    rrc_connected_ue_count: int = 0
    active_drb_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "prb_total",
            "prb_used",
            "rrc_connected_ue_count",
            "active_drb_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("%s must be an integer" % name)
            if value < 0:
                raise ValueError("%s must be >= 0" % name)
        if self.prb_used > self.prb_total:
            raise ValueError("prb_used must be in [0, prb_total]")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prb_total": self.prb_total,
            "prb_used": self.prb_used,
            "rrc_connected_ue_count": self.rrc_connected_ue_count,
            "active_drb_count": self.active_drb_count,
        }


@dataclass(frozen=True)
class RanObservation:
    """The mapped state snapshot returned by ``observe()``.

    Carries the capability-id REFERENCES the RAN currently serves, the
    per-element health snapshot, the integer resource snapshot, the
    CU/DU/RU topology, and the generic link metrics (the WORK-016
    ``LinkMetricName`` names mirrored as plain strings so the WORK-016
    bridge can translate them into the generic adapter metric
    vocabulary).  All of it is adapter-reported DATA -- never core
    topology/resource/health authority (LOCK-016/017).
    """

    capabilities: Tuple[str, ...]
    health: RanHealthSnapshot
    resources: RanResourceSnapshot
    topology: RanSplitTopology
    link_metrics: Mapping[str, int]

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, (tuple, list)):
            raise ValueError("capabilities must be a sequence of reference strings")
        for capability in self.capabilities:
            validate_ran_capability_reference(capability)
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        if not isinstance(self.health, RanHealthSnapshot):
            raise ValueError("health must be a RanHealthSnapshot")
        if not isinstance(self.resources, RanResourceSnapshot):
            raise ValueError("resources must be a RanResourceSnapshot")
        if not isinstance(self.topology, RanSplitTopology):
            raise ValueError("topology must be a RanSplitTopology")
        if not isinstance(self.link_metrics, Mapping):
            raise ValueError("link_metrics must be a mapping of metric name -> int")
        metrics: Dict[str, int] = {}
        for metric, value in self.link_metrics.items():
            if metric not in LinkMetricName.values():
                raise ValueError(
                    "link metric %r is not in the six-name generic vocabulary "
                    "(values mirror WORK-016 adapters.model.LinkMetricName)"
                    % (metric,)
                )
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("link metric %r must have an integer value" % metric)
            if value < 0:
                raise ValueError("link metric %r must be >= 0" % metric)
            metrics[metric] = value
        object.__setattr__(self, "link_metrics", metrics)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capabilities": list(self.capabilities),
            "health": self.health.to_dict(),
            "resources": self.resources.to_dict(),
            "topology": self.topology.to_dict(),
            "link_metrics": dict(sorted(self.link_metrics.items())),
        }


# --------------------------------------------------------------------------
# Adapter-private UE/bearer context (typed model for conformance/interop)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RanDrb:
    """A data radio bearer record (3GPP TS 38.331 -- at most 29 DRBs
    per UE, so ``drb_id`` is 1..29; TS 23.501 §5.4 -- a DRB carries
    one or more QoS flows, each identified by a QFI in 0..63).

    DATA only: the boundary maps DRB ids and QFIs, it never schedules
    them (a production gNB's MAC/scheduler does, behind the seam --
    LOCK-016).
    """

    drb_id: int
    qfi: int

    def __post_init__(self) -> None:
        if isinstance(self.drb_id, bool) or not isinstance(self.drb_id, int):
            raise ValueError("drb_id must be an integer")
        if not (1 <= self.drb_id <= 29):
            raise ValueError(
                "drb_id must be in [1, 29] (3GPP TS 38.331 max DRB per UE)"
            )
        if isinstance(self.qfi, bool) or not isinstance(self.qfi, int):
            raise ValueError("qfi must be an integer")
        if not (0 <= self.qfi <= 63):
            raise ValueError("qfi must be in [0, 63] (3GPP TS 23.501 §5.7.3)")

    def to_dict(self) -> Dict[str, Any]:
        return {"drb_id": self.drb_id, "qfi": self.qfi}


@dataclass(frozen=True)
class RanUeContext:
    """An adapter-private UE context (opaque ue ref + RNTI + the UE's
    DRB records).

    RAN identifiers are adapter-private OPAQUE state: the RNTI (TS
    38.321 §7.1 -- a 16-bit radio-network temporary identifier;
    0x0000 and 0xFFFF are reserved, so valid values are 1..65534),
    the DRB ids, the cell id, and the gNB id NEVER cross into the
    ADCOS core as authority (LOCK-006: logical session identity is
    access independent; LOCK-016: the RAN stays behind the adapter).
    The core sees only the sacred ``session_id`` and the opaque
    ``ran:bearer:<digest>`` reference returned by ``bind_session``;
    the mapping between them lives in the MANAGER.  This dataclass
    exists so adapter-side conformance/interop code has a typed
    model, NOT so core can branch on it.
    """

    ue_ref: str
    rnti: int
    drbs: Tuple[RanDrb, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.ue_ref, str) or not self.ue_ref:
            raise ValueError("ue_ref must be a non-empty opaque string")
        reject_credential_like_text(self.ue_ref, what="ue_ref")
        if isinstance(self.rnti, bool) or not isinstance(self.rnti, int):
            raise ValueError("rnti must be an integer")
        if not (1 <= self.rnti <= 65534):
            raise ValueError(
                "rnti must be in [1, 65534] (3GPP TS 38.321 §7.1 -- "
                "16-bit RNTI; 0x0000 and 0xFFFF reserved)"
            )
        if not isinstance(self.drbs, (tuple, list)):
            raise ValueError("drbs must be a sequence of RanDrb")
        for drb in self.drbs:
            if not isinstance(drb, RanDrb):
                raise ValueError("drbs must contain only RanDrb instances")
        object.__setattr__(self, "drbs", tuple(self.drbs))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ue_ref": self.ue_ref,
            "rnti": self.rnti,
            "drbs": [drb.to_dict() for drb in self.drbs],
        }


__all__ = [
    "HealthState",
    "CellState",
    "DuplexMode",
    "RanSplitOption",
    "LinkMetricName",
    "RAN_CAPABILITY_GNB_PROVISION",
    "RAN_CAPABILITY_CELL_TDD",
    "RAN_CAPABILITY_CELL_FDD",
    "RAN_CAPABILITY_DRB_QOS_FLOW",
    "RAN_CAPABILITY_CU_DU_SPLIT_F1",
    "RAN_CAPABILITY_O_RU_FRONTHAUL",
    "RAN_CAPABILITY_REFERENCES",
    "CellSpec",
    "CellDescriptor",
    "CuElement",
    "DuElement",
    "RuElement",
    "RanSplitTopology",
    "GnbProvisionRequest",
    "RanHealthSnapshot",
    "RanResourceSnapshot",
    "RanObservation",
    "RanDrb",
    "RanUeContext",
]
