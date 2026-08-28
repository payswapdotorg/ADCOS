"""WORK-037 class-C gate: the real interoperability-lab profile gate.

The frozen WORK-037 acceptance -- "at least one real 5G lab works
end-to-end", required verification "interoperability lab" -- is
composed over the THREE accepted real interop gates (never
re-implemented, never bypassed):

- the WORK-019 real-Open5GS gate
  (:func:`adapters.fivegc.open5gs_interop.run_open5gs_interop`);
- the WORK-020 real SDR-based RAN lab gate
  (:func:`adapters.ran.openran_interop.run_openran_interop`);
- the WORK-021 real N3IWF gate
  (:func:`adapters.wifi.wifi_interop.run_wifi_interop`).

The profile gate adds EXACTLY one requirement on top of the three
legs: the SAME sacred, access-independent ``session_id`` must be
carried by every leg (the mixed-access demonstration on real
infrastructure -- config-level coherence is validated fail-closed
BEFORE any leg runs, and the PASSED outcome requires every leg's own
PASSED).

EVIDENCE RULE -- THE W020 LESSON, ENFORCED HERE
-----------------------------------------------
RF simulation, OAI RFsim, software emulation, in-repo conformance
peers, and synthetic interoperability provide architecture evidence
and automated verification (classes A/B) but can NEVER be promoted to
the real-lab acceptance criterion (class C).  The gate therefore:

- reports ``GATE_DISABLED`` when ``ORAN_INTEROP`` is unset (the
  honest disclosure; NEVER a PASS);
- reports ``LEG_DISABLED`` when the profile switch is set but a leg
  gate's own switch is unset (each leg keeps its independent operator
  switch -- the profile gate never bypasses one);
- propagates a leg's ``FORBIDDEN`` (the per-leg anti-faking guards
  fire inside the leg gates BEFORE any network probe);
- propagates a leg's ``UNREACHABLE`` (a verification-environment
  blocker; the profile gate NEVER falls back to an in-repo peer);
- reports ``PASSED`` ONLY when every leg gate passed on real
  infrastructure with the coherent session id.

No new PASSED path is introduced by composition: the profile PASSED
exists only as the conjunction of the three leg PASSED outcomes.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

from adapters.fivegc.open5gs_interop import (
    InteropConfig as FiveGcLegConfig,
    run_open5gs_interop,
)
from adapters.ran.openran_interop import (
    RanInteropConfig as RanLegConfig,
    run_openran_interop,
)
from adapters.wifi.wifi_interop import (
    InteropConfig as WifiLegConfig,
    run_wifi_interop,
)

from .errors import InteropError, InteropReasonCode
from .evidence import (
    PROFILE_EVIDENCE_STATUS,
    REAL_LAB_EVIDENCE_STATEMENT,
)

__all__ = [
    "ORAN_INTEROP_ENV",
    "ORAN_INTEROP_SESSION_ID_ENV",
    "DEFAULT_ORAN_INTEROP_SESSION_ID",
    "PROFILE_LEG_SWITCHES",
    "ProfileLabConfig",
    "LegGateStatus",
    "ProfileLabOutcome",
    "oran_interop_gate_enabled",
    "check_session_coherence",
    "aggregate_leg_outcomes",
    "run_profile_lab_gate",
    "profile_lab_runbook",
]

#: The profile gate switch (``ORAN_INTEROP=1`` enables the lab run).
ORAN_INTEROP_ENV = "ORAN_INTEROP"

#: The shared session id the three legs must carry coherently.
ORAN_INTEROP_SESSION_ID_ENV = "ORAN_INTEROP_SESSION_ID"

#: The canonical shared session id (deterministic; the runbook tells
#: the operator to override it with the REAL session under test).
DEFAULT_ORAN_INTEROP_SESSION_ID = "adcos-w037-interop"

#: Bounded leg-detail length (diagnostics never carry unbounded peer
#: output and never carry credential material).
_DETAIL_LIMIT = 200


def _bounded(detail: str) -> str:
    text = str(detail)
    if len(text) <= _DETAIL_LIMIT:
        return text
    return text[: _DETAIL_LIMIT - 3] + "..."


#: The frozen leg order + each leg's INDEPENDENT operator switch (the
#: profile gate never bypasses a leg switch -- it composes the leg
#: gates exactly as the accepted work items froze them).
PROFILE_LEG_SWITCHES: Tuple[Tuple[str, str], ...] = (
    ("five-g-core", "OPEN5GS_INTEROP"),
    ("ran", "RAN_INTEROP"),
    ("non-threegpp", "WIFI_INTEROP"),
)


def oran_interop_gate_enabled() -> bool:
    """True when the operator explicitly enabled the profile lab
    gate (``ORAN_INTEROP=1``)."""
    return os.environ.get(ORAN_INTEROP_ENV, "").strip() == "1"


@dataclass(frozen=True)
class ProfileLabConfig:
    """The profile lab-gate configuration (env-driven).

    Each leg's endpoint/peer configuration stays with the leg gate's
    OWN ``from_env()`` (the accepted surfaces); the profile layer
    only carries the leg switches and the shared session id.
    """

    session_id: str = DEFAULT_ORAN_INTEROP_SESSION_ID
    leg_switches: Dict[str, bool] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "ProfileLabConfig":
        session_id = (
            os.environ.get(ORAN_INTEROP_SESSION_ID_ENV, "").strip()
            or DEFAULT_ORAN_INTEROP_SESSION_ID
        )
        switches = {leg: False for leg, _switch in PROFILE_LEG_SWITCHES}
        for leg, switch in PROFILE_LEG_SWITCHES:
            switches[leg] = os.environ.get(switch, "").strip() == "1"
        return cls(session_id=session_id, leg_switches=switches)


@dataclass(frozen=True)
class LegGateStatus:
    """One leg gate's outcome inside a profile lab run."""

    leg: str
    family: str
    switch: str
    status: str
    detail: str = ""

    def __post_init__(self) -> None:
        known_legs = tuple(leg for leg, _ in PROFILE_LEG_SWITCHES)
        if self.leg not in known_legs:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "unknown lab leg: %r" % (self.leg,),
            )
        if not isinstance(self.status, str) or not self.status:
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "leg status must be a non-empty string",
            )
        if not isinstance(self.detail, str):
            raise InteropError(
                InteropReasonCode.INVALID_INPUT,
                "leg detail must be a string",
            )


@dataclass(frozen=True)
class ProfileLabOutcome:
    """The profile lab-gate outcome.

    ``status`` is one of:

    * ``GATE_DISABLED`` -- ``ORAN_INTEROP`` unset (never a PASS);
    * ``SESSION_DIVERGENCE`` -- the leg configs carry divergent
      session ids (fail-closed BEFORE any leg runs);
    * ``LEG_DISABLED`` -- a leg gate's own switch is unset;
    * ``FORBIDDEN`` -- a leg's anti-faking guard fired;
    * ``UNREACHABLE`` -- a leg's verification-environment blocker;
    * ``LEG_FAILED`` -- a leg reached a real peer and failed;
    * ``PASSED`` -- EVERY leg passed on real infrastructure with the
      coherent session id (the only class-C closure).
    """

    status: str
    detail: str
    legs: Tuple[LegGateStatus, ...] = ()
    session_id: str = ""
    session_coherent: bool = False


# ----------------------------------------------------------------------
# Pure checks (testable without any real lab)
# ----------------------------------------------------------------------


def check_session_coherence(session_ids: Mapping[str, str]) -> str:
    """Assert that every leg carries the SAME session id (pure).

    Takes a ``leg -> session_id`` mapping; returns the coherent id;
    raises ``SESSION_DIVERGENCE`` on ANY divergence.  The mixed-access
    criterion is a SESSION criterion: one access-independent identity
    across the 3GPP and non-3GPP legs.
    """
    if not isinstance(session_ids, Mapping):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "session_ids must be a mapping (leg -> session_id)",
        )
    values = tuple(session_ids.values())
    if not values:
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "session_ids must not be empty",
        )
    first = values[0]
    divergent = sorted(
        leg for leg, sid in session_ids.items() if sid != first
    )
    if divergent:
        raise InteropError(
            InteropReasonCode.SESSION_DIVERGENCE,
            "legs %s carry divergent session ids (mixed access requires "
            "ONE access-independent session id)" % (divergent,),
        )
    return first


#: The frozen aggregation precedence (most severe first): an
#: anti-faking violation outranks an environment blocker, which
#: outranks a real-peer failure, which outranks a disabled leg.
_SEVERITY_ORDER: Tuple[str, ...] = (
    "FORBIDDEN",
    "UNREACHABLE",
    "LEG_FAILED",
    "LEG_DISABLED",
)

#: The leg statuses mapped to each profile-level aggregation class.
_STATUS_TO_PROFILE = {
    "FORBIDDEN": "FORBIDDEN",
    "UNREACHABLE": "UNREACHABLE",
    "SKIP": "LEG_DISABLED",
    "GATE_DISABLED": "LEG_DISABLED",
    "PASSED": "PASSED",
}


def _profile_class_for_leg_status(leg_status: str) -> str:
    if leg_status in _STATUS_TO_PROFILE:
        return _STATUS_TO_PROFILE[leg_status]
    # Any other real-run failure shape (SBI_FAILED, PEER_FAILED,
    # BYTE_MISMATCH, DATA_PEER_UNREACHABLE, FAILED, ...): a real peer
    # was reached and the leg failed.
    return "LEG_FAILED"


def aggregate_leg_outcomes(
    legs: Tuple[LegGateStatus, ...],
    *,
    session_id: str,
) -> ProfileLabOutcome:
    """Aggregate the leg outcomes into the profile outcome (PURE).

    This function performs NO I/O; it is the frozen classification
    rule.  ``PASSED`` requires every leg PASSED AND the coherent
    session id -- nothing else ever produces a class-C closure.
    """
    if not isinstance(legs, tuple) or not legs:
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "legs must be a non-empty tuple of LegGateStatus",
        )
    statuses = tuple(_profile_class_for_leg_status(leg.status) for leg in legs)
    if all(status == "PASSED" for status in statuses):
        return ProfileLabOutcome(
            status="PASSED",
            detail=(
                "real 5G lab PASSED end-to-end: every leg gate passed on "
                "real infrastructure (%s) with ONE access-independent "
                "session id -- the frozen WORK-037 class-C closure "
                "(mixed access demonstrated on real infrastructure)"
                % (", ".join("%s=%s" % (leg.leg, leg.status) for leg in legs),)
            ),
            legs=legs,
            session_id=session_id,
            session_coherent=True,
        )
    for profile_class in _SEVERITY_ORDER:
        if any(status == profile_class for status in statuses):
            failed_legs = [
                (leg.leg, leg.status) for leg, status in zip(legs, statuses)
                if status == profile_class
            ]
            return ProfileLabOutcome(
                status=profile_class,
                detail=(
                    "%s: %s (per-leg statuses: %s) -- NOT a PASS; class C "
                    "remains %s"
                    % (
                        profile_class,
                        failed_legs,
                        ", ".join(
                            "%s=%s" % (leg.leg, leg.status) for leg in legs
                        ),
                        PROFILE_EVIDENCE_STATUS["real_interop_lab"],
                    )
                ),
                legs=legs,
                session_id=session_id,
                session_coherent=False,
            )
    raise InteropError(
        InteropReasonCode.INVALID_INPUT,
        "unclassifiable leg statuses: %s" % (statuses,),
    )


def profile_lab_runbook() -> Dict[str, object]:
    """The operator runbook for a REAL profile lab run (pure DATA).

    Documents what a real 5G interoperability lab must provide to
    close the frozen WORK-037 class-C criterion.  Deterministic; no
    environment reads.
    """
    return {
        "objective": (
            "Close the WORK-037 real-lab criterion: at least one real 5G "
            "lab works end-to-end with clean adapter boundaries and "
            "demonstrated mixed access (one session_id across 3GPP and "
            "non-3GPP legs)."
        ),
        "lab_requirements": (
            "A Linux lab host (or hosts) with: a real Open5GS 5G Core "
            "(SBI reachable; UPF data network with an echo peer); a real "
            "SDR-based RAN (OpenAirInterface gNB or an O-RAN O-DU/O-RU "
            "combination on real SDR hardware, with a UE attached through "
            "the radio); a real N3IFW/N3IWF non-3GPP access path (kernel "
            "IPsec/XFRM per the WORK-021 runbook); SCTP support for "
            "NGAP/F1 transport on the RAN host.",
        ),
        "environment": (
            "ORAN_INTEROP=1 plus every leg's own switch: OPEN5GS_INTEROP=1 "
            "with OPEN5GS_SBI_URL (and OPEN5GS_DATA_PEER for the user "
            "plane); RAN_INTEROP=1 with RAN_PEER_KIND=real_oai (or "
            "real_oran/real_sdr/real_other_ran) and RAN_CONTROL_URL; "
            "WIFI_INTEROP=1 with WIFI_PEER_KIND=real_n3iwf and "
            "WIFI_N3IWF_ENDPOINT (plus WIFI_DATA_PEER).  Set "
            "ORAN_INTEROP_SESSION_ID to the REAL session under test so "
            "the three legs carry ONE access-independent session id.",
        ),
        "anti_faking": (
            "reference/inrepo/conformance_server/simulator (and "
            "rf_simulation/rfsim on the RAN leg) are FORBIDDEN peer "
            "kinds: each leg gate fires FORBIDDEN before any network "
            "probe.  RF simulation and in-repo conformance peers are "
            "classes A/B evidence and can NEVER satisfy class C."
        ),
        "evidence_status": dict(PROFILE_EVIDENCE_STATUS),
        "statement": REAL_LAB_EVIDENCE_STATEMENT,
    }


# ----------------------------------------------------------------------
# The gate
# ----------------------------------------------------------------------


def run_profile_lab_gate(
    config: Optional[ProfileLabConfig] = None,
) -> ProfileLabOutcome:
    """Run the profile lab gate (composes the three leg gates).

    Returns a :class:`ProfileLabOutcome`.  NEVER fakes success: an
    unreachable leg is a verification-environment blocker, a disabled
    leg is an honest non-run, and ``PASSED`` exists only as the
    conjunction of the three real leg PASSED outcomes with the
    coherent session id.
    """
    cfg = config if config is not None else ProfileLabConfig.from_env()

    if not oran_interop_gate_enabled():
        return ProfileLabOutcome(
            status="GATE_DISABLED",
            detail=(
                "ORAN_INTEROP!=1: the real interoperability-lab profile "
                "gate is not run; the class-B scenario (the mixed-access "
                "demonstration over the in-repo conformance peers) plus "
                "the class-A architecture conformance checks remain the "
                "strongest honest in-sandbox evidence -- neither can "
                "satisfy the frozen real-lab criterion (class C).  %s"
                % REAL_LAB_EVIDENCE_STATEMENT
            ),
        )

    # Phase 0: config-level session coherence (fail-closed BEFORE any
    # leg runs; the mixed-access criterion is a session criterion).
    fivegc_cfg = dataclasses.replace(
        FiveGcLegConfig.from_env(), session_id=cfg.session_id
    )
    ran_cfg = dataclasses.replace(
        RanLegConfig.from_env(), session_id=cfg.session_id
    )
    wifi_cfg = dataclasses.replace(
        WifiLegConfig.from_env(), session_id=cfg.session_id
    )
    leg_session_ids = {
        "five-g-core": fivegc_cfg.session_id,
        "ran": ran_cfg.session_id,
        "non-threegpp": wifi_cfg.session_id,
    }
    try:
        coherent_session_id = check_session_coherence(leg_session_ids)
    except InteropError as exc:
        return ProfileLabOutcome(
            status="SESSION_DIVERGENCE",
            detail=(
                "the leg configurations carry divergent session ids; the "
                "profile gate refuses to run a lab demonstration whose "
                "legs do not share ONE access-independent session id "
                "(%s)"
            )
            % exc.detail,
        )

    # Phase 1: leg switches (each leg keeps its INDEPENDENT operator
    # switch; the profile gate never bypasses one).
    disabled = [
        (leg, switch)
        for leg, switch in PROFILE_LEG_SWITCHES
        if not cfg.leg_switches.get(leg, False)
    ]
    if disabled:
        return ProfileLabOutcome(
            status="LEG_DISABLED",
            detail=(
                "profile gate enabled but leg gate(s) unset: %s -- each "
                "leg gate keeps its independent operator switch (set "
                "OPEN5GS_INTEROP=1, RAN_INTEROP=1, and WIFI_INTEROP=1 "
                "on the real lab host); this is an honest non-run, NOT "
                "a PASS; class C remains %s"
                % (
                    ", ".join("%s (%s)" % (leg, switch) for leg, switch in disabled),
                    PROFILE_EVIDENCE_STATUS["real_interop_lab"],
                )
            ),
            session_id=coherent_session_id,
        )

    # Phase 2: run every enabled leg (frozen order), collecting each
    # leg's own outcome verbatim (statuses are never remapped; the
    # detail is bounded and secret-free).
    fivegc_outcome = run_open5gs_interop(fivegc_cfg)
    ran_outcome = run_openran_interop(ran_cfg)
    wifi_outcome = run_wifi_interop(wifi_cfg)
    leg_results: Tuple[LegGateStatus, ...] = (
        LegGateStatus(
            leg="five-g-core",
            family="adapters.fivegc",
            switch="OPEN5GS_INTEROP",
            status=fivegc_outcome.status,
            detail=_bounded(fivegc_outcome.detail),
        ),
        LegGateStatus(
            leg="ran",
            family="adapters.ran",
            switch="RAN_INTEROP",
            status=ran_outcome.status,
            detail=_bounded(ran_outcome.detail),
        ),
        LegGateStatus(
            leg="non-threegpp",
            family="adapters.wifi",
            switch="WIFI_INTEROP",
            status=wifi_outcome.status,
            detail=_bounded(wifi_outcome.detail),
        ),
    )

    # Phase 3: the frozen aggregation (pure).
    return aggregate_leg_outcomes(leg_results, session_id=coherent_session_id)
