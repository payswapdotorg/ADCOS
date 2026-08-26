"""ADCOS Open RAN real interoperability gate (WORK-020: the frozen
SDR-based-lab acceptance criterion).

The frozen WORK-020 acceptance criterion -- "at least one SDR-based
lab topology works", required verification "end-to-end lab tests", DoD
"ADCOS can provision/use a standards-compliant 5G access path" --
cannot be closed by
:class:`adapters.ran.conformance.ReferenceRanConformanceServer` alone,
because the conformance peer is an in-repo ADCOS test implementation
(``ADCOS adapter <-> ADCOS reference peer``), not a real SDR-based RAN
lab (``ADCOS adapter <-> independent OpenAirInterface/O-RAN stack on
real SDR hardware``).

This module is the required gate, environment-gated by
``RAN_INTEROP=1``.  When the gate is enabled AND a real RAN stack is
reachable at ``RAN_CONTROL_URL`` AND the environment carries real SDR
device evidence, the gate exercises the full byte-path the frozen
acceptance requires::

    ADCOS
      -> OpenRanAdapter                    (production-shaped real-HTTP
                                            adapter implementing the
                                            frozen 14-op RanContract)
      -> REAL OpenAirInterface / O-RAN lab (O1/E2-style control
                                            endpoint; TS 38.413 NG
                                            setup analog; O-RAN.WG1 O1
                                            management style)
         |- [SDR]  real SDR hardware present (device node evidence,
         |         earned from the environment probe -- NEVER from the
         |         control plane alone)
         |- [CTRL] real control-plane interaction (capabilities +
         |         state from the real stack)
         |- [CELL] real cell activation on the real SDR (RF on air)
         |- [UE]   real UE attach through the radio (RRC connected)
         |- [DRB]  real data radio bearer bound to an ADCOS session_id
         |- [IP]   real end-to-end application bytes (byte-identical
                   echo + SHA-256)

When the gate is enabled but the environment cannot host a real
SDR-based lab, the gate returns ``UNREACHABLE`` -- it does NOT fall
back to the in-repo conformance peer.  The Architect's W019 B1
correction (applied family-internally) is explicit: a
verification-environment blocker is NOT architecture permission to
redefine "SDR-based lab topology" as "our own reference server."

This sandbox (user ``z``, no root, no Docker) cannot host a real
OpenAirInterface/SDR lab: no cmake/meson/ninja on PATH, no SDR device
nodes (no ``/dev/usrp*``/``/dev/soapy*``, not even ``/dev/bus/usb``),
no SCTP, no ``/dev/net/tun``, and no OAI binaries.  The gate therefore
reports ``UNREACHABLE`` in this sandbox -- a verification-environment
blocker transparently disclosed in the family README and in the gate's
own capability matrix.  The conformance suite (the
``ReferenceRanConformanceServer`` evidence, a sibling module) remains
the strongest honest evidence achievable in this sandbox; this gate
closes the SDR-lab criterion the moment the environment is expanded
to a real lab host.

The gate uses ONLY stdlib (``http.client`` through the adapter,
``socket`` through the probe, ``hashlib``, ``os``).  No vendor SDK, no
RAN state machine import, no radio.  The ``OpenRanAdapter`` this gate
constructs is the SAME adapter used by the conformance suite --
proving the adapter is not coupled to either peer (replaceability
across the same seam).

Environment variables consumed:

* ``RAN_INTEROP``           -- the gate switch (``1`` enables it).
* ``RAN_PEER_KIND``         -- the operator's independence assertion
                               (``real_oai``/``real_oran``/``real_sdr``/
                               ``real_other_ran``; the forbidden kinds
                               ``reference``/``inrepo``/
                               ``conformance_server``/``simulator``
                               fire FORBIDDEN before any network probe).
* ``RAN_CONTROL_URL``       -- the real lab's O1/E2-style control
                               endpoint (default
                               ``http://127.0.0.1:9091``).
* ``RAN_INTEROP_SESSION_ID``-- optional; the session_id the gate binds
                               (default ``adcos-w020-interop``).
* ``RAN_INTEROP_CELL_ID``   -- optional; the canonical lab cell id
                               (default ``c-lab-1``).

Usage (CI acceptance / local evidence; the selftest case numbering
lives in the WORK-020 RAN selftest, a sibling task)::

    RAN_INTEROP=1 \\
    RAN_PEER_KIND=real_oai \\
    RAN_CONTROL_URL=http://<lab-host>:9091 \\
    python3 tools/ran_selftest.py
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .contract import RanContext
from .errors import RanError
from .interop_env_probe import (
    RAN_PEER_KIND_ENV,
    RanCapabilityReport,
    RanCheck,
    RanEnvProbeConfig,
    probe_ran_interop_capability,
)
from .model import (
    CellSpec,
    CellState,
    CuElement,
    DuElement,
    DuplexMode,
    GnbProvisionRequest,
    HealthState,
    RanSplitOption,
    RanSplitTopology,
    RuElement,
)
from .openran import DEFAULT_RAN_CONTROL_URL, RAN_CONTROL_URL_ENV, OpenRanAdapter
from .sandbox import DEFAULT_STEP_BUDGET

__all__ = [
    "RAN_INTEROP_ENV",
    "RAN_INTEROP_SESSION_ID_ENV",
    "RAN_INTEROP_CELL_ID_ENV",
    "DEFAULT_RAN_INTEROP_SESSION_ID",
    "DEFAULT_RAN_INTEROP_CELL_ID",
    "DEFAULT_RAN_INTEROP_PAYLOAD",
    "RanInteropConfig",
    "RanInteropOutcome",
    "ran_interop_gate_enabled",
    "run_openran_interop",
]


#: The gate switch (``RAN_INTEROP=1`` enables the real-SDR-lab gate).
RAN_INTEROP_ENV = "RAN_INTEROP"

#: Optional env overrides for the canonical interop session/cell.
RAN_INTEROP_SESSION_ID_ENV = "RAN_INTEROP_SESSION_ID"
RAN_INTEROP_CELL_ID_ENV = "RAN_INTEROP_CELL_ID"

#: The session_id the gate binds on the real RAN (a WORK-012-shaped
#: opaque id; never derived from RAN identity -- LOCK-006/R1).
DEFAULT_RAN_INTEROP_SESSION_ID = "adcos-w020-interop"

#: The canonical lab cell id of the gate's provisioned gNB.
DEFAULT_RAN_INTEROP_CELL_ID = "c-lab-1"

#: A deterministic payload the interop gate carries over the real
#: radio bearer path (the fivegc gate's canonical payload discipline:
#: bytes are content-stable; no randomness).
DEFAULT_RAN_INTEROP_PAYLOAD = b"adcospktpath-real-ran-interop-v1"

#: The injected instant for every gate operation (WORK-003 grammar; no
#: wall clock anywhere in the gate).
_INTEROP_INSTANT = "2026-06-01T12:00:00Z"

#: The canonical gNB name the gate provisions (band 78 TDD, F1 CU/DU
#: topology + an O-RAN 7-2x RU element -- TS 38.401/38.473, O-RAN.WG4).
_INTEROP_GNB_NAME = "adcos-w020-interop-gnb"

#: The six frozen evidence lines, in the canonical order.  A PASS
#: record carries all six; a FAILED record carries only the lines
#: actually earned.  The [SDR] line is earned from the environment
#: probe (device-node/driver evidence), NEVER from the control plane
#: alone -- so a PASS record can never be mistaken for a generic
#: control-plane echo.
_EVIDENCE_SDR = "[SDR]  real SDR hardware present (device node / driver evidence)"
_EVIDENCE_CTRL = "[CTRL] real control-plane interaction (capabilities + state from the real stack)"
_EVIDENCE_CELL = "[CELL] real cell activation on the real SDR (RF on air)"
_EVIDENCE_UE = "[UE]   real UE attach through the radio (RRC connected)"
_EVIDENCE_DRB = "[DRB]  real data radio bearer bound to an ADCOS session_id"
_EVIDENCE_IP = "[IP]   real end-to-end application bytes (payload equality + SHA-256)"


def ran_interop_gate_enabled() -> bool:
    """Whether the real SDR-lab interop gate is enabled.

    The gate is OFF by default; set ``RAN_INTEROP=1`` to enable it.
    The conformance suite always runs against the deterministic
    reference peer; the real-SDR-lab interop gate runs only when
    explicitly enabled AND a real OpenAirInterface/O-RAN lab with SDR
    evidence is reachable.
    """
    return os.environ.get(RAN_INTEROP_ENV, "").strip() == "1"


@dataclass(frozen=True)
class RanInteropConfig:
    """Configuration for the real SDR-lab interop gate.

    All fields default from the environment (``RAN_CONTROL_URL``,
    ``RAN_PEER_KIND``, ``RAN_INTEROP_SESSION_ID``,
    ``RAN_INTEROP_CELL_ID``) or to deterministic module-level constants
    (no wall clock, no randomness -- the W018/W019 selftest
    discipline).  ``RAN_INTEROP`` itself is read by
    :func:`ran_interop_gate_enabled`, not stored here.
    """

    control_url: str = DEFAULT_RAN_CONTROL_URL
    peer_kind: str = ""
    session_id: str = DEFAULT_RAN_INTEROP_SESSION_ID
    cell_id: str = DEFAULT_RAN_INTEROP_CELL_ID
    payload: bytes = DEFAULT_RAN_INTEROP_PAYLOAD

    @classmethod
    def from_env(cls) -> "RanInteropConfig":
        return cls(
            control_url=os.environ.get(RAN_CONTROL_URL_ENV, "").strip()
            or DEFAULT_RAN_CONTROL_URL,
            peer_kind=os.environ.get(RAN_PEER_KIND_ENV, "").strip(),
            session_id=os.environ.get(RAN_INTEROP_SESSION_ID_ENV, "").strip()
            or DEFAULT_RAN_INTEROP_SESSION_ID,
            cell_id=os.environ.get(RAN_INTEROP_CELL_ID_ENV, "").strip()
            or DEFAULT_RAN_INTEROP_CELL_ID,
        )


@dataclass(frozen=True)
class RanInteropOutcome:
    """The outcome of a real SDR-lab interop gate run.

    ``status`` is one of:

    * ``"SKIP"`` -- ``RAN_INTEROP`` is not set to ``"1"``; the gate is
      not enabled (transparent gate-disabled disclosure; the
      conformance suite remains the strongest honest in-sandbox
      evidence, and the selftest case numbering lives in the WORK-020
      RAN selftest, a sibling task).
    * ``"FORBIDDEN"`` -- the operator explicitly tagged the peer as an
      in-repo reference/conformance peer or simulator
      (``RAN_PEER_KIND`` in ``reference|inrepo|conformance_server|
      simulator``); the anti-faking guard fired BEFORE any network
      probe.  This is a hard non-acceptance outcome; the gate does NOT
      fall back to the in-repo conformance peer (the in-repo peer can
      NEVER satisfy the frozen SDR-based lab topology criterion, not
      even as a fallback).
    * ``"UNREACHABLE"`` -- ``RAN_INTEROP=1`` was set but the
      environment cannot host a real SDR-based lab: the control
      endpoint is unreachable, or build_tools+oai_binaries+sdr_driver
      are all absent (no possibility of a real stack).  This is a
      verification-environment blocker, NOT a fake-pass; the gate does
      NOT fall back to the in-repo conformance peer.
    * ``"FAILED"`` -- the gate ran against a reachable control plane
      but a real phase failed (control-plane interaction, cell
      activation, UE/DRB evidence, SDR device evidence, or payload
      equality); the detail names the specific phase and reason.  Real
      failures are NEVER masked as SKIP.
    * ``"PASSED"`` -- real stack reachable at ``RAN_CONTROL_URL`` +
      real SDR device evidence + real cell ACTIVE + real UE/DRB bound
      to the ADCOS session_id + payload byte-identical end-to-end.
      This is the outcome that closes the frozen SDR-lab criterion.

    The provenance fields make a PASS record auditable: the control
    URL, the asserted peer kind, the opaque gNB/bearer references, the
    payload length/equality/SHA-256, and the evidence lines actually
    earned (in the canonical [SDR]/[CTRL]/[CELL]/[UE]/[DRB]/[IP]
    order).  RNTI/DRB internals are adapter-private and never appear
    here -- only opaque references.
    """

    status: str
    detail: str
    control_url: str = ""
    peer_kind: str = ""
    gnb_ref: Optional[str] = None
    cell_id: Optional[str] = None
    bearer_ref: Optional[str] = None
    payload_length: int = 0
    payload_equality: bool = False
    payload_sha256: Optional[str] = None
    evidence: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _canonical_gnb_request(cell_id: str) -> GnbProvisionRequest:
    """The fixed canonical gNB the gate provisions on the real stack:
    one TDD cell (band 78, TS 38.104 §5.2; 30 kHz SCS, TS 38.211
    §4.2.1; an n78 NR-ARFCN, TS 38.104 §5.4.2) under an F1 CU/DU
    topology (TS 38.401 §5 / TS 38.473) with an O-RAN 7-2x RU element
    (O-RAN.WG4 open fronthaul)."""
    return GnbProvisionRequest(
        gnb_name=_INTEROP_GNB_NAME,
        cells=(
            CellSpec(
                cell_id=cell_id,
                band=78,
                duplex=DuplexMode.TDD,
                numerology=1,
                arfcn=632628,
                prb_count=10,
            ),
        ),
        topology=RanSplitTopology(
            cu=CuElement(
                element_id="cu-lab-1",
                split=RanSplitOption.F1_CU_DU,
                state=HealthState.HEALTHY,
            ),
            dus=(
                DuElement(
                    element_id="du-lab-1",
                    split=RanSplitOption.F1_CU_DU,
                    state=HealthState.HEALTHY,
                    cell_ids=(cell_id,),
                ),
            ),
            rus=(
                RuElement(
                    element_id="ru-lab-1",
                    split=RanSplitOption.O_RAN_7_2X,
                    state=HealthState.HEALTHY,
                    band=78,
                ),
            ),
        ),
    )


def _find_check(report: RanCapabilityReport, name: str) -> Optional[RanCheck]:
    for check in report.checks:
        if check.name == name:
            return check
    return None


def _ordered_evidence(
    sdr: bool,
    ctrl: bool,
    cell: bool,
    ue: bool,
    drb: bool,
    ip: bool,
) -> Tuple[str, ...]:
    """Assemble the earned evidence lines in the canonical order."""
    lines: List[str] = []
    if sdr:
        lines.append(_EVIDENCE_SDR)
    if ctrl:
        lines.append(_EVIDENCE_CTRL)
    if cell:
        lines.append(_EVIDENCE_CELL)
    if ue:
        lines.append(_EVIDENCE_UE)
    if drb:
        lines.append(_EVIDENCE_DRB)
    if ip:
        lines.append(_EVIDENCE_IP)
    return tuple(lines)


def _phase_failure(
    cfg: RanInteropConfig,
    phase: str,
    reason: str,
    *,
    gnb_ref: Optional[str] = None,
    cell_id: Optional[str] = None,
    bearer_ref: Optional[str] = None,
    payload_length: int = 0,
    evidence: Tuple[str, ...] = (),
) -> RanInteropOutcome:
    """A real phase failure -> FAILED with the specific phase named.

    The gate does NOT mask real failures as SKIP (the fivegc gate
    discipline): a reachable-but-failing stack is an integration
    failure with a specific reason, not a verification-environment
    blocker.
    """
    return RanInteropOutcome(
        status="FAILED",
        detail="%s failed: %s" % (phase, reason),
        control_url=cfg.control_url,
        peer_kind=cfg.peer_kind,
        gnb_ref=gnb_ref,
        cell_id=cell_id,
        bearer_ref=bearer_ref,
        payload_length=payload_length,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# The real SDR-lab interop gate
# ---------------------------------------------------------------------------


def run_openran_interop(
    config: Optional[RanInteropConfig] = None,
) -> RanInteropOutcome:
    """Run the real SDR-lab interop gate.

    Returns a :class:`RanInteropOutcome`.  Does NOT fake success with
    an in-repo simulator; an environment that cannot host a real
    SDR-based lab is reported as ``UNREACHABLE`` (verification-
    environment blocker) and a failing real stack is reported as
    ``FAILED`` with the phase named.  There is NO new PASSED path: PASS
    requires every real phase to succeed on a real SDR-based lab.
    """
    cfg = config or RanInteropConfig.from_env()

    # Gate disabled -> SKIP with a transparent disclosure (the fivegc
    # gate-disabled disclosure mirrored; the SKIP lives INSIDE the gate
    # here so an ungated invocation can never fall through to the
    # real phases).
    if not ran_interop_gate_enabled():
        return RanInteropOutcome(
            status="SKIP",
            detail=(
                "RAN_INTEROP!=1: the real SDR-lab interop gate is not run; "
                "the conformance suite against the in-repo "
                "ReferenceRanConformanceServer remains the strongest "
                "honest in-sandbox evidence (case numbering will live in "
                "the WORK-020 RAN selftest, a sibling task). Set "
                "RAN_INTEROP=1 with RAN_PEER_KIND=real_oai and a "
                "reachable real OpenAirInterface/O-RAN lab control "
                "endpoint (RAN_CONTROL_URL) to run the acceptance gate."
            ),
            control_url=cfg.control_url,
            peer_kind=cfg.peer_kind,
        )

    # Phase 0 (BEFORE any network probe): anti-faking independence
    # guard + the explicit environment-capability matrix.  The guard
    # fires FORBIDDEN when the operator explicitly tags the peer as an
    # in-repo reference/conformance peer or simulator (Architect
    # anti-faking rule, enforced in code rather than prose); the probe
    # deliberately leaves the control endpoint UNPROBED in that case,
    # so the short-circuit opens no socket at all.  The matrix is
    # computed once here so the UNREACHABLE branches below carry the
    # explicit capability table instead of an opaque string.  This
    # phase adds no new PASSED path -- FORBIDDEN and UNREACHABLE are
    # non-acceptance outcomes.
    probe_report = probe_ran_interop_capability(
        RanEnvProbeConfig(control_url=cfg.control_url, peer_kind=cfg.peer_kind)
    )
    if probe_report.forbidden_substitution is not None:
        return RanInteropOutcome(
            status="FORBIDDEN",
            detail=(
                "%s -- the gate does NOT fall back to the in-repo "
                "conformance peer (the in-repo reference/conformance peer "
                "can NEVER satisfy the frozen SDR-based lab topology "
                "criterion, not even as a fallback); set "
                "RAN_PEER_KIND=real_oai|real_oran|real_sdr|real_other_ran "
                "against a real, independent SDR-based RAN lab to "
                "proceed. Probe report:\n%s"
            ) % (probe_report.forbidden_substitution, probe_report.summary()),
            control_url=cfg.control_url,
            peer_kind=cfg.peer_kind,
        )

    # Phase 1: environment capability.  UNREACHABLE when the control
    # endpoint is unreachable, and ALSO when build_tools + oai_binaries
    # + sdr_driver are ALL absent (no possibility of a real stack in
    # this environment -- a reachable endpoint cannot be a real
    # SDR-based lab here).  Both branches carry the full matrix; the
    # gate does NOT fall back to the in-repo conformance peer.
    control_check = _find_check(probe_report, "openran_control")
    if control_check is None or not control_check.available:
        return RanInteropOutcome(
            status="UNREACHABLE",
            detail=(
                "RAN control endpoint not reachable at %s (%s) -- "
                "verification-environment blocker (the gate does NOT fall "
                "back to the in-repo conformance peer; point "
                "RAN_CONTROL_URL at a real OpenAirInterface/O-RAN lab "
                "control endpoint). Environment-capability matrix:\n%s"
            )
            % (
                cfg.control_url,
                control_check.detail if control_check is not None else "not probed",
                probe_report.summary(),
            ),
            control_url=cfg.control_url,
            peer_kind=cfg.peer_kind,
        )
    stack_capability = any(
        check.available
        for check in probe_report.checks
        if check.name in ("build_tools", "oai_binaries", "sdr_driver")
    )
    if not stack_capability:
        return RanInteropOutcome(
            status="UNREACHABLE",
            detail=(
                "no possibility of a real RAN stack in this environment "
                "(build_tools + oai_binaries + sdr_driver all absent) -- "
                "verification-environment blocker: a reachable control "
                "endpoint cannot be a real SDR-based RAN lab here, and the "
                "gate does NOT fall back to the in-repo conformance peer. "
                "Environment-capability matrix:\n%s"
            )
            % (probe_report.summary(),),
            control_url=cfg.control_url,
            peer_kind=cfg.peer_kind,
        )

    sdr_check = _find_check(probe_report, "sdr_driver")
    sdr_available = sdr_check is not None and sdr_check.available
    sdr_detail = sdr_check.detail if sdr_check is not None else "not probed"

    # Phases 2-5 run against the reachable control endpoint through the
    # SAME production-shaped adapter the conformance suite uses.  Every
    # phase failure is a FAILED with the phase named -- never a SKIP,
    # never a fallback.
    adapter = OpenRanAdapter(control_url=cfg.control_url)
    context = RanContext(
        ran_integration_id="adcos:ran:openran-interop",
        instant=_INTEROP_INSTANT,
        step_budget=DEFAULT_STEP_BUDGET,
    )
    gnb_ref: Optional[str] = None
    bearer_ref: Optional[str] = None
    adapter_open = False
    ctrl_earned = False
    cell_earned = False
    try:
        # Phase 2 [CTRL]: real control-plane interaction -- open the
        # adapter, read capabilities (at least one
        # capability.access.ran.* reference must be served), and
        # observe real state (the RanObservation shape carries the
        # link metrics by construction).
        try:
            adapter.open(context)
            adapter_open = True
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 2 [CTRL] open", "%s: %s" % (exc.reason_code, exc)
            )
        try:
            capabilities = adapter.capabilities()
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 2 [CTRL] capabilities", "%s: %s" % (exc.reason_code, exc)
            )
        if not any(c.startswith("capability.access.ran.") for c in capabilities):
            return _phase_failure(
                cfg,
                "Phase 2 [CTRL] capabilities",
                "the control plane at %s answered but served no "
                "capability.access.ran.* reference (got %r)"
                % (cfg.control_url, list(capabilities)),
            )
        try:
            adapter.observe(context)
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 2 [CTRL] observe", "%s: %s" % (exc.reason_code, exc)
            )
        ctrl_earned = True

        # Phase 3 [CELL]: provision the canonical gNB (one TDD cell,
        # band 78, F1 CU/DU topology + an O-RAN 7-2x RU element) and
        # activate the cell; the observed state must show the cell
        # ACTIVE and the resources must reflect it.
        try:
            gnb_ref = adapter.provision_gnb(
                context, request=_canonical_gnb_request(cfg.cell_id)
            )
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 3 [CELL] provision_gnb", "%s: %s" % (exc.reason_code, exc),
                evidence=_ordered_evidence(sdr_available, ctrl_earned, False, False, False, False),
            )
        try:
            adapter.activate_cell(context, gnb_ref=gnb_ref, cell_id=cfg.cell_id)
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 3 [CELL] activate_cell", "%s: %s" % (exc.reason_code, exc),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, False, False, False, False),
            )
        try:
            after_activation = adapter.observe(context)
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 3 [CELL] observe", "%s: %s" % (exc.reason_code, exc),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, False, False, False, False),
            )
        if after_activation.health.cell_states.get(cfg.cell_id) != CellState.ACTIVE:
            return _phase_failure(
                cfg,
                "Phase 3 [CELL]",
                "the stack did not report cell %r ACTIVE (observed %r)"
                % (cfg.cell_id, after_activation.health.cell_states.get(cfg.cell_id)),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, False, False, False, False),
            )
        if after_activation.resources.prb_total <= 0:
            return _phase_failure(
                cfg,
                "Phase 3 [CELL]",
                "resources do not reflect the active cell (prb_total=%d)"
                % after_activation.resources.prb_total,
                gnb_ref=gnb_ref, cell_id=cfg.cell_id,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, False, False, False, False),
            )
        cell_earned = True

        # SDR evidence rule (the anti-faking heart of the gate): the
        # [CELL] line above is CONTROL-PLANE evidence of cell
        # activation on the stack at RAN_CONTROL_URL; the [SDR] line is
        # earned from the environment probe (device-node/driver
        # evidence), NEVER from the control plane alone.  If the
        # sdr_driver check missed, [SDR] is NOT claimed and the status
        # is FAILED: the frozen criterion is an SDR-based topology, so
        # control-plane-only activation can never close it (this is
        # exactly why a control-plane-only peer -- e.g. the in-repo
        # conformance peer -- can never satisfy the criterion even
        # when pointed at with a real_* peer kind).
        if not sdr_available:
            return RanInteropOutcome(
                status="FAILED",
                detail=(
                    "Phase 3 [SDR]: control-plane evidence of cell "
                    "activation on the stack at %s was earned, but the SDR "
                    "device evidence line [SDR] is NOT claimed: the "
                    "sdr_driver probe found no SDR device evidence (%s). "
                    "The frozen WORK-020 criterion is an SDR-based lab "
                    "topology, so this is a FAILED gate -- a "
                    "control-plane-only peer can never close the criterion "
                    "(the [CELL] line above is control-plane evidence; the "
                    "[SDR] line must come from the environment)."
                )
                % (cfg.control_url, sdr_detail),
                control_url=cfg.control_url,
                peer_kind=cfg.peer_kind,
                gnb_ref=gnb_ref,
                cell_id=cfg.cell_id,
                evidence=_ordered_evidence(False, ctrl_earned, cell_earned, False, False, False),
            )

        # Phase 4 [UE]+[DRB]: bind the ADCOS session to a real data
        # radio bearer; the real stack's state observation must report
        # the UE context (the RRC-connected analog: a connected-UE
        # count and an active-DRB count).  Only the opaque bearer
        # reference is recorded -- RNTI/DRB internals are
        # adapter-private and never appear in the outcome.
        try:
            bearer_ref = adapter.bind_session(context, session_id=cfg.session_id)
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 4 [DRB] bind_session", "%s: %s" % (exc.reason_code, exc),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, False, False, False),
            )
        try:
            bound = adapter.observe(context)
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 4 [UE] observe", "%s: %s" % (exc.reason_code, exc),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id, bearer_ref=bearer_ref,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, False, False, False),
            )
        if bound.resources.rrc_connected_ue_count < 1:
            return _phase_failure(
                cfg,
                "Phase 4 [UE]",
                "the stack does not report an RRC-connected UE after "
                "binding session %r (rrc_connected_ue_count=%d)"
                % (cfg.session_id, bound.resources.rrc_connected_ue_count),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id, bearer_ref=bearer_ref,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, False, False, False),
            )
        if bound.resources.active_drb_count < 1:
            return _phase_failure(
                cfg,
                "Phase 4 [DRB]",
                "the stack does not report an active data radio bearer "
                "after binding session %r (active_drb_count=%d)"
                % (cfg.session_id, bound.resources.active_drb_count),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id, bearer_ref=bearer_ref,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, True, False, False),
            )

        # Phase 5 [IP]: the payload round-trip over the real bearer
        # path -- byte-identical equality + SHA-256 (the fivegc
        # payload-equality discipline).
        try:
            echoed = adapter.egress_data(
                context, bearer_ref=bearer_ref, payload=cfg.payload
            )
        except RanError as exc:
            return _phase_failure(
                cfg, "Phase 5 [IP] egress_data", "%s: %s" % (exc.reason_code, exc),
                gnb_ref=gnb_ref, cell_id=cfg.cell_id, bearer_ref=bearer_ref,
                payload_length=len(cfg.payload),
                evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, True, True, False),
            )
        digest = hashlib.sha256(cfg.payload).hexdigest()
        equal = echoed == cfg.payload
        if not equal:
            return RanInteropOutcome(
                status="FAILED",
                detail=(
                    "Phase 5 [IP] failed: echo mismatch over the real "
                    "bearer path: %r != %r"
                )
                % (echoed, cfg.payload),
                control_url=cfg.control_url,
                peer_kind=cfg.peer_kind,
                gnb_ref=gnb_ref,
                cell_id=cfg.cell_id,
                bearer_ref=bearer_ref,
                payload_length=len(cfg.payload),
                payload_equality=False,
                payload_sha256=digest,
                evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, True, True, False),
            )

        # PASSED -- the only PASSED path in the gate: every real phase
        # succeeded on a real SDR-based lab.  Provenance fields are
        # populated so the record cannot be mistaken for a generic
        # echo.
        return RanInteropOutcome(
            status="PASSED",
            detail=(
                "real SDR-lab RAN interop PASSED: capabilities + state "
                "from the real stack at %s -> canonical gNB provisioned "
                "(band 78 TDD, F1 CU/DU + O-RAN 7-2x RU) with cell %r "
                "ACTIVE on the real SDR -> session %r bound to a real "
                "data radio bearer -> payload byte-identical over the "
                "real radio path (%d bytes, sha256 %s)"
            )
            % (cfg.control_url, cfg.cell_id, cfg.session_id, len(cfg.payload), digest),
            control_url=cfg.control_url,
            peer_kind=cfg.peer_kind,
            gnb_ref=gnb_ref,
            cell_id=cfg.cell_id,
            bearer_ref=bearer_ref,
            payload_length=len(cfg.payload),
            payload_equality=True,
            payload_sha256=digest,
            evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, True, True, True),
        )
    except Exception as exc:  # noqa: BLE001 -- the gate never propagates
        # Defensive outer net (the adapter already maps transport
        # failures to RanError): an unexpected exception is a FAILED
        # gate carrying the exception CLASS NAME only (LOCK-023
        # discipline -- exception message text is never captured).
        return RanInteropOutcome(
            status="FAILED",
            detail=(
                "unexpected implementation exception (%s; class name only "
                "-- the gate never captures exception text)"
                % exc.__class__.__name__
            ),
            control_url=cfg.control_url,
            peer_kind=cfg.peer_kind,
            gnb_ref=gnb_ref,
            cell_id=cfg.cell_id,
            bearer_ref=bearer_ref,
            evidence=_ordered_evidence(sdr_available, ctrl_earned, cell_earned, False, False, False),
        )
    finally:
        # Teardown (best-effort, the fivegc gate discipline): unbind
        # the gate's bearer, decommission the gate's own canonical
        # gNB, and close the adapter.  A teardown failure never
        # manufactures or masks the outcome -- the outcome above is
        # already recorded.
        if adapter_open:
            if bearer_ref is not None:
                try:
                    adapter.unbind_session(context, bearer_ref=bearer_ref)
                except Exception:  # noqa: BLE001
                    pass
            if gnb_ref is not None:
                try:
                    adapter.decommission_gnb(context, gnb_ref=gnb_ref)
                except Exception:  # noqa: BLE001
                    pass
            try:
                adapter.close(context)
            except Exception:  # noqa: BLE001
                pass
