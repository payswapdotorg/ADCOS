"""WORK-037 class-B scenario: the mixed-access profile demonstration.

The deterministic, in-repo orchestration of the COMPLETE Open
RAN/Core interoperability profile over the ACCEPTED adapter families
and their in-repo conformance peers (real loopback sockets; honest
engineering evidence):

    one sacred, access-independent WORK-012 ``session_id``
      -> leg 1  five-g-core-pdu       (W019 seam: FiveGCoreManager ->
                                       Open5GSAdapter -> 5G Core
                                       conformance peer; real HTTP
                                       SBi + real TCP data socket)
      -> leg 2  ran-access-path       (W020 seam: RanManager ->
                                       OpenRanAdapter -> RAN
                                       conformance peer; real HTTP
                                       control + access-path echo)
      -> leg 3  non-threegpp-tunnel   (W021 seam: WifiManager ->
                                       N3IWFAdapter -> N3IWF
                                       conformance peer; real UDP
                                       control + real TCP tunnel)
      -> leg 4  five-g-core-rebind    (access change BACK to 3GPP
                                       with the session identity
                                       never re-minted)

Every leg carries the SAME payload and must receive it back
byte-identical; the access changes (3GPP <-> non-3GPP) are journaled;
adapter-side refs stay adapter-side (cross-family opacity is checked
and only their SHA-256 digests are journaled).

EVIDENCE CLASS -- DISCLOSED, HONEST, FROZEN
--------------------------------------------
This scenario is evidence class B (automated verification) over
in-repo conformance peers.  It is NEVER real-lab evidence: class C
(real interoperability with an independent Open5GS/OpenAirInterface/
N3IWF lab) belongs to :mod:`interop.labgate` alone and stays OPEN
until the real gate passes.  No ``LegEvidence`` record may carry a
class other than "B" (enforced in the record constructor).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Sequence, Tuple

from adapters.fivegc import (
    Dnn,
    FiveGCoreManager,
    NfEndpoint,
    Open5GSAdapter,
    Reference5GCoreConformanceServer,
    Snssai,
    SessionReader as FiveGcSessionReader,
    SessionView as FiveGcSessionView,
    SubscriberProfileView,
    SubscriberReader,
)
from adapters.ran import (
    CellSpec,
    CuElement,
    DuplexMode,
    DuElement,
    GnbProvisionRequest,
    HealthState,
    OpenRanAdapter,
    RanManager,
    RanSplitOption,
    RanSplitTopology,
    ReferenceRanConformanceServer,
    RuElement,
)
from adapters.wifi import (
    ApDescriptor,
    ApProfileReader,
    ApProfileView,
    N3IWFAdapter,
    ReferenceWifiConformanceServer,
    SecurityPolicy,
    SsidProfile,
    WifiManager,
    SessionReader as WifiSessionReader,
    SessionView as WifiSessionView,
)

from .errors import InteropError, InteropReasonCode
from .model import (
    AccessLegKind,
    InteropEvent,
    InteropEventType,
    InteropRunResult,
    LegEvidence,
    ProfileDeclaration,
    ScenarioLegName,
)
from .profile import validate_profile

__all__ = [
    "DEFAULT_PROFILE_PAYLOAD",
    "DEFAULT_START_INSTANT",
    "SessionFacts",
    "check_ref_opacity",
    "run_profile_scenario",
    "verify_interop_replay",
]

#: The canonical profile payload (content-stable; no randomness).
DEFAULT_PROFILE_PAYLOAD = b"adcospktpath-oran-interop-profile-v1"

#: The canonical scenario start instant (injected; never a clock read).
DEFAULT_START_INSTANT = "2026-06-01T12:00:00Z"

#: The canonical profile subscriber facts (slot NAME only -- LOCK-023:
#: no 5G credential material ever appears in the profile layer).
_PROFILE_SUPI = "imsi-001010000000001"
_PROFILE_SNSSAI = Snssai(sst=1, sd="010203")
_PROFILE_DNN = Dnn(value="internet")
_PROFILE_CRED_SLOT = "subscriber-credentials"

#: The canonical profile Wi-Fi AP facts (slot NAME only -- LOCK-023).
_PROFILE_AP_NAME = "interop-ap"
_PROFILE_SSID = "interop"
_PROFILE_WIFI_SLOT = "wifi-technology-credentials"


# ----------------------------------------------------------------------
# Session projection (INPUT -- the profile never mints sessions)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class SessionFacts:
    """The least-authority session projection the scenario needs.

    The scenario accepts a read-only ``lookup`` callable supplying
    these facts for a REAL session (the battery wires it to a genuine
    WORK-012 ``SessionStore``).  The profile layer VALIDATES the
    session; it never creates, transitions, or re-mints one.
    """

    secureable: bool
    initiator_node_id: str
    responder_node_id: str


class _FiveGcReader(FiveGcSessionReader):
    """The fivegc-family session reader delegating to the scenario's
    read-only lookup (the composition-root wiring discipline)."""

    __slots__ = ("_lookup",)

    def __init__(self, lookup: Callable[[str], Optional[SessionFacts]]) -> None:
        self._lookup = lookup

    def lookup(self, session_id: str) -> Optional[FiveGcSessionView]:
        facts = self._lookup(session_id)
        if facts is None:
            return None
        return FiveGcSessionView(
            session_id=session_id,
            secureable=facts.secureable,
            initiator_node_id=facts.initiator_node_id,
            responder_node_id=facts.responder_node_id,
        )


class _WifiReader(WifiSessionReader):
    """The wifi-family session reader delegating to the scenario's
    read-only lookup."""

    __slots__ = ("_lookup",)

    def __init__(self, lookup: Callable[[str], Optional[SessionFacts]]) -> None:
        self._lookup = lookup

    def lookup(self, session_id: str) -> Optional[WifiSessionView]:
        facts = self._lookup(session_id)
        if facts is None:
            return None
        return WifiSessionView(
            session_id=session_id,
            secureable=facts.secureable,
            initiator_node_id=facts.initiator_node_id,
            responder_node_id=facts.responder_node_id,
        )


class _ProfileSubscriberReader(SubscriberReader):
    """The canonical subscriber-PROFILE projection (secret-free; the
    slot NAME only -- LOCK-023; mirrors the accepted gate's reader)."""

    __slots__ = ()

    def profile_for(self, supi: str) -> Optional[SubscriberProfileView]:
        return SubscriberProfileView(
            supi=supi,
            subscribed_sst=1,
            subscribed_sd="010203",
            subscribed_dnn="internet",
            credential_slot_name=_PROFILE_CRED_SLOT,
        )


class _ProfileApProfileReader(ApProfileReader):
    """The canonical AP-profile projection (slot NAME only)."""

    __slots__ = ()

    def profile_for(self, ap_name: str) -> Optional[ApProfileView]:
        return ApProfileView(
            ap_name=ap_name,
            ssid_names=(_PROFILE_SSID,),
            credential_slot_name=_PROFILE_WIFI_SLOT,
        )


# ----------------------------------------------------------------------
# Cross-family ref opacity (pure)
# ----------------------------------------------------------------------

#: Fragments of OTHER families that must never appear in a family's
#: opaque refs (the W021 case_33 identity-separation rule, frozen as
#: the profile's opacity map; hex digests cannot false-positive these
#: fragments -- none of them is a hex string).
_FAMILY_FORBIDDEN_FRAGMENTS = {
    "adapters.fivegc": ("wifi:", "n3iwf", "ran:"),
    "adapters.ran": ("adcos:fivegc", "wifi:", "tunnel:", "assoc:"),
    "adapters.wifi": ("adcos:fivegc", "ran:", "pdu:"),
}


def check_ref_opacity(
    *,
    fivegc_refs: Sequence[str] = (),
    ran_refs: Sequence[str] = (),
    wifi_refs: Sequence[str] = (),
) -> None:
    """Assert cross-family ref opacity (pure, fail-closed).

    Each family's adapter-side opaque refs must not carry any other
    family's ref fragments -- the families never share an identity
    namespace, and the sacred ``session_id`` is the ONLY identity
    crossing them.
    """
    groups = {
        "adapters.fivegc": tuple(fivegc_refs),
        "adapters.ran": tuple(ran_refs),
        "adapters.wifi": tuple(wifi_refs),
    }
    for family, forbidden in _FAMILY_FORBIDDEN_FRAGMENTS.items():
        for ref in groups[family]:
            if not isinstance(ref, str):
                raise InteropError(
                    InteropReasonCode.INVALID_INPUT,
                    "refs must be strings (got %s)" % (type(ref).__name__,),
                )
            for fragment in forbidden:
                if fragment in ref:
                    raise InteropError(
                        InteropReasonCode.REF_OPACITY_VIOLATION,
                        "%s ref carries another family's identity "
                        "fragment %r (cross-family opacity violated)"
                        % (family, fragment),
                    )


# ----------------------------------------------------------------------
# Deterministic injected-instant stepping (no clock reads)
# ----------------------------------------------------------------------


def _step_instant(base: str, minutes: int) -> str:
    """Pure instant arithmetic: base + N minutes (deterministic; the
    audit case forbids wall-clock reads, not stdlib date arithmetic
    over an injected base)."""
    parsed = datetime.strptime(base, "%Y-%m-%dT%H:%M:%SZ")
    stepped = parsed + timedelta(minutes=minutes)
    return stepped.strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------
# The canonical lab shape (DATA)
# ----------------------------------------------------------------------


def _canonical_lab_gnb_request() -> GnbProvisionRequest:
    """The profile's canonical gNB lab shape (the W020 reference lab
    topology: one band-78 TDD cell on an F1 CU/DU split with an
    O-RAN 7-2x open-fronthaul RU)."""
    return GnbProvisionRequest(
        gnb_name="interop-lab-gnb-1",
        cells=(
            CellSpec(
                cell_id="c1",
                band=78,
                duplex=DuplexMode.TDD,
                numerology=1,
                arfcn=632628,
                prb_count=10,
            ),
        ),
        topology=RanSplitTopology(
            cu=CuElement(
                element_id="cu-1",
                split=RanSplitOption.F1_CU_DU,
                state=HealthState.HEALTHY,
            ),
            dus=(
                DuElement(
                    element_id="du-1",
                    split=RanSplitOption.F1_CU_DU,
                    state=HealthState.HEALTHY,
                    cell_ids=("c1",),
                ),
            ),
            rus=(
                RuElement(
                    element_id="ru-1",
                    split=RanSplitOption.O_RAN_7_2X,
                    state=HealthState.HEALTHY,
                    band=78,
                ),
            ),
        ),
    )


def _profile_ap_descriptor() -> ApDescriptor:
    """The profile's canonical Wi-Fi AP descriptor."""
    return ApDescriptor(
        name=_PROFILE_AP_NAME,
        ssids=(
            SsidProfile(
                ssid=_PROFILE_SSID,
                band="5ghz",
                security_policy=SecurityPolicy.OPEN,
                max_stations=8,
            ),
        ),
        bands=("5ghz",),
        max_associations=8,
    )


# ----------------------------------------------------------------------
# The scenario
# ----------------------------------------------------------------------


class _Journal:
    """The append-only scenario journal (content-derived event ids;
    one injected-instant step per logical operation)."""

    def __init__(self, start_instant: str) -> None:
        self._base = start_instant
        self._events: List[InteropEvent] = []

    def step(self) -> str:
        return _step_instant(self._base, len(self._events))

    def append(self, kind: str, subject: str, detail: str = "") -> None:
        self._events.append(
            InteropEvent(
                sequence=len(self._events) + 1,
                instant=self.step(),
                kind=kind,
                subject=subject,
                detail=detail,
            )
        )

    def events(self) -> Tuple[InteropEvent, ...]:
        return tuple(self._events)


def _require_ok(name: str, result) -> object:
    if not getattr(result, "ok", False):
        raise InteropError(
            InteropReasonCode.LEG_UNAVAILABLE,
            "%s failed: %s" % (name, getattr(result, "detail", "")),
        )
    return result.value


def _echo_round_trip(send_recv, payload: bytes) -> bytes:
    """Send the payload and collect the echo (bounded attempts)."""
    sent = send_recv.send(payload)
    if sent != len(payload):
        raise InteropError(
            InteropReasonCode.LEG_BYTE_MISMATCH,
            "send returned %d, expected %d" % (sent, len(payload)),
        )
    echo = b""
    attempts = 0
    while len(echo) < len(payload) and attempts < 64:
        chunk = send_recv.recv()
        if not chunk:
            break
        echo += chunk
        attempts += 1
    return echo


def _run_fivegc_leg(
    server: Reference5GCoreConformanceServer,
    *,
    integration_id: str,
    session_id: str,
    payload: bytes,
    journal: _Journal,
    leg_name: str,
    lookup: Callable[[str], Optional[SessionFacts]],
) -> Tuple[LegEvidence, Tuple[str, ...]]:
    """One 5G Core PDU-session leg over the W019 seam."""
    mgr = FiveGCoreManager(
        integration_id=integration_id,
        session_reader=_FiveGcReader(lookup),
        subscriber_reader=_ProfileSubscriberReader(),
    )
    try:
        journal.append(InteropEventType.LEG_STARTED, leg_name)
        adapter = Open5GSAdapter(
            nf_endpoint=NfEndpoint(nf_type="SMF", url=server.base_url)
        )
        _require_ok(
            "register_implementation",
            mgr.register_implementation(adapter, now=journal.step()),
        )
        mgr.provision_subscriber(
            now=journal.step(),
            supi=_PROFILE_SUPI,
            credential_slot_name=_PROFILE_CRED_SLOT,
            subscribed_snssai=_PROFILE_SNSSAI,
            subscribed_dnn=_PROFILE_DNN,
        )
        bound = _require_ok(
            "bind_session",
            mgr.bind_session(
                now=journal.step(),
                session_id=session_id,
                supi=_PROFILE_SUPI,
                snssai=_PROFILE_SNSSAI,
                dnn=_PROFILE_DNN,
            ),
        )
        pdu_ref = bound.pdu_session_ref
        _require_ok(
            "authenticate",
            mgr.authenticate(now=journal.step(), pdu_session_ref=pdu_ref),
        )
        _require_ok(
            "establish_pdu_session",
            mgr.establish_pdu_session(now=journal.step(), pdu_session_ref=pdu_ref),
        )
        app = _require_ok(
            "app_session", mgr.app_session(now=journal.step(), session_id=session_id)
        )
        app.connect("internet")
        echo = _echo_round_trip(app, payload)
        app.close()
        payload_digest = hashlib.sha256(payload).hexdigest()
        echo_digest = hashlib.sha256(echo).hexdigest()
        if echo != payload:
            raise InteropError(
                InteropReasonCode.LEG_BYTE_MISMATCH,
                "leg %r echo digest %s != payload digest %s"
                % (leg_name, echo_digest, payload_digest),
            )
        evidence = LegEvidence(
            leg=leg_name,
            access_kind=AccessLegKind.THREE_GPP,
            session_id=session_id,
            payload_sha256=payload_digest,
            echo_sha256=echo_digest,
            bytes_equal=True,
            adapter_ref_digest=hashlib.sha256(pdu_ref.encode("utf-8")).hexdigest(),
        )
        journal.append(
            InteropEventType.LEG_BYTES_VERIFIED,
            leg_name,
            "echo digest %s byte-identical over the W019 seam" % echo_digest,
        )
        _require_ok(
            "close_binding",
            mgr.close_binding(now=journal.step(), pdu_session_ref=pdu_ref),
        )
        journal.append(InteropEventType.LEG_RELEASED, leg_name)
        return evidence, (pdu_ref,)
    finally:
        mgr.close()


def _run_ran_leg(
    server: ReferenceRanConformanceServer,
    *,
    session_id: str,
    payload: bytes,
    journal: _Journal,
) -> Tuple[LegEvidence, Tuple[str, ...]]:
    """One RAN access-path leg over the W020 seam."""
    mgr = RanManager(ran_integration_id="adcos:ran:interop-profile")
    try:
        journal.append(InteropEventType.LEG_STARTED, ScenarioLegName.RAN_ACCESS_PATH)
        r = mgr.register_implementation(
            OpenRanAdapter(control_url=server.base_url),
            label="openran-interop-profile",
            make_default=True,
            now=journal.step(),
        )
        if not r.ok:
            raise InteropError(
                InteropReasonCode.LEG_UNAVAILABLE,
                "ran register_implementation failed: %s" % r.detail,
            )
        gnb_ref = str(
            _require_ok(
                "provision_gnb",
                mgr.provision_gnb(
                    now=journal.step(), request=_canonical_lab_gnb_request()
                ),
            )
        )
        _require_ok(
            "activate_cell",
            mgr.activate_cell(now=journal.step(), gnb_ref=gnb_ref, cell_id="c1"),
        )
        session = _require_ok(
            "access_path_session",
            mgr.access_path_session(now=journal.step(), session_id=session_id),
        )
        session.connect("internet")
        echo = _echo_round_trip(session, payload)
        session.close()
        payload_digest = hashlib.sha256(payload).hexdigest()
        echo_digest = hashlib.sha256(echo).hexdigest()
        if echo != payload:
            raise InteropError(
                InteropReasonCode.LEG_BYTE_MISMATCH,
                "leg %r echo digest %s != payload digest %s"
                % (ScenarioLegName.RAN_ACCESS_PATH, echo_digest, payload_digest),
            )
        evidence = LegEvidence(
            leg=ScenarioLegName.RAN_ACCESS_PATH,
            access_kind=AccessLegKind.THREE_GPP,
            session_id=session_id,
            payload_sha256=payload_digest,
            echo_sha256=echo_digest,
            bytes_equal=True,
            adapter_ref_digest=hashlib.sha256(gnb_ref.encode("utf-8")).hexdigest(),
        )
        journal.append(
            InteropEventType.LEG_BYTES_VERIFIED,
            ScenarioLegName.RAN_ACCESS_PATH,
            "echo digest %s byte-identical over the W020 seam" % echo_digest,
        )
        journal.append(
            InteropEventType.LEG_RELEASED, ScenarioLegName.RAN_ACCESS_PATH
        )
        return evidence, (gnb_ref,)
    finally:
        mgr.close()


def _run_wifi_leg(
    server: ReferenceWifiConformanceServer,
    *,
    session_id: str,
    payload: bytes,
    journal: _Journal,
    lookup: Callable[[str], Optional[SessionFacts]],
) -> Tuple[LegEvidence, Tuple[str, ...]]:
    """One Wi-Fi/N3IWF tunnel leg over the W021 seam."""
    mgr = WifiManager(
        integration_id="adcos:wifi:interop-profile",
        session_reader=_WifiReader(lookup),
        ap_profile_reader=_ProfileApProfileReader(),
    )
    try:
        journal.append(
            InteropEventType.LEG_STARTED, ScenarioLegName.NON_THREEGPP_TUNNEL
        )
        wr = mgr.register_implementation(
            N3IWFAdapter(control_endpoint=server.control_endpoint),
            label="n3iwf-interop-profile",
            make_default=True,
            now=journal.step(),
        )
        if not wr.ok:
            raise InteropError(
                InteropReasonCode.LEG_UNAVAILABLE,
                "wifi register_implementation failed: %s" % wr.detail,
            )
        ap_ref = _require_ok(
            "provision_ap",
            mgr.provision_ap(
                now=journal.step(),
                descriptor=_profile_ap_descriptor(),
                credential_slot_name=_PROFILE_WIFI_SLOT,
            ),
        ).ap_ref
        binding = _require_ok(
            "bind_session",
            mgr.bind_session(
                now=journal.step(),
                session_id=session_id,
                ap_ref=ap_ref,
                ssid_name=_PROFILE_SSID,
                station_label="interop-station",
            ),
        )
        _require_ok(
            "authenticate",
            mgr.authenticate(now=journal.step(), binding_id=binding.binding_id),
        )
        tunnel = _require_ok(
            "establish_tunnel",
            mgr.establish_tunnel(now=journal.step(), binding_id=binding.binding_id),
        )
        tunnel_ref = tunnel.tunnel_ref
        wsession = _require_ok(
            "app_session", mgr.app_session(now=journal.step(), session_id=session_id)
        )
        wsession.connect("interop-service")
        echo = _echo_round_trip(wsession, payload)
        wsession.close()
        payload_digest = hashlib.sha256(payload).hexdigest()
        echo_digest = hashlib.sha256(echo).hexdigest()
        if echo != payload:
            raise InteropError(
                InteropReasonCode.LEG_BYTE_MISMATCH,
                "leg %r echo digest %s != payload digest %s"
                % (ScenarioLegName.NON_THREEGPP_TUNNEL, echo_digest, payload_digest),
            )
        evidence = LegEvidence(
            leg=ScenarioLegName.NON_THREEGPP_TUNNEL,
            access_kind=AccessLegKind.NON_THREE_GPP,
            session_id=session_id,
            payload_sha256=payload_digest,
            echo_sha256=echo_digest,
            bytes_equal=True,
            adapter_ref_digest=hashlib.sha256(
                tunnel_ref.encode("utf-8")
            ).hexdigest(),
        )
        journal.append(
            InteropEventType.LEG_BYTES_VERIFIED,
            ScenarioLegName.NON_THREEGPP_TUNNEL,
            "echo digest %s byte-identical over the W021 seam" % echo_digest,
        )
        mgr.release_tunnel(now=journal.step(), tunnel_ref=tunnel_ref)
        _require_ok(
            "close_binding",
            mgr.close_binding(now=journal.step(), binding_id=binding.binding_id),
        )
        journal.append(
            InteropEventType.LEG_RELEASED, ScenarioLegName.NON_THREEGPP_TUNNEL
        )
        return evidence, (ap_ref, binding.binding_id, tunnel_ref)
    finally:
        mgr.close()


def run_profile_scenario(
    profile: ProfileDeclaration,
    *,
    session_id: str,
    session_lookup: Callable[[str], Optional[SessionFacts]],
    payload: bytes = DEFAULT_PROFILE_PAYLOAD,
    start_instant: str = DEFAULT_START_INSTANT,
) -> InteropRunResult:
    """Run the complete mixed-access profile scenario (class B).

    Fail-closed sequence: validate the declaration -> validate the
    session (existence + secureability) BEFORE any peer is started ->
    run the four legs in the frozen order -> verify cross-family ref
    opacity -> verify session coherence -> journal the verification.
    Any failure raises a typed :class:`InteropError`; nothing partial
    is ever returned.
    """
    if not isinstance(session_id, str) or not session_id:
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "session_id must be a non-empty string",
        )
    if not isinstance(payload, (bytes, bytearray)):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "payload must be bytes",
        )
    payload = bytes(payload)

    # Phase 0: the profile (fail-closed, before anything is started).
    profile_digest = validate_profile(profile)

    # Phase 1: the session (INPUT; the profile never mints one).
    facts = session_lookup(session_id)
    if facts is None:
        raise InteropError(
            InteropReasonCode.SESSION_UNKNOWN,
            "session %r is not known to the session authority "
            "(read-only lookup returned nothing)" % (session_id[:24] + "...",),
        )
    if not isinstance(facts, SessionFacts):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "session_lookup must return SessionFacts or None",
        )
    if not facts.secureable:
        raise InteropError(
            InteropReasonCode.SESSION_UNSECUREABLE,
            "session %r is not secureable; the profile refuses to carry "
            "it across access legs" % (session_id[:24] + "...",),
        )

    journal = _Journal(start_instant)
    journal.append(
        InteropEventType.PROFILE_VALIDATED,
        profile.profile_id,
        "profile digest %s over %d components and %d reference points"
        % (
            profile_digest,
            len(profile.bindings),
            len(profile.required_reference_points),
        ),
    )

    fivegc_server = Reference5GCoreConformanceServer()
    ran_server = ReferenceRanConformanceServer()
    wifi_server = ReferenceWifiConformanceServer()
    legs: List[LegEvidence] = []
    fivegc_refs: List[str] = []
    ran_refs: List[str] = []
    wifi_refs: List[str] = []
    try:
        # Leg 1: the 3GPP core leg (W019).
        evidence, refs = _run_fivegc_leg(
            fivegc_server,
            integration_id="adcos:fivegc:interop-profile",
            session_id=session_id,
            payload=payload,
            journal=journal,
            leg_name=ScenarioLegName.FIVE_G_CORE_PDU,
            lookup=session_lookup,
        )
        legs.append(evidence)
        fivegc_refs.extend(refs)

        # Leg 2: the 3GPP radio leg (W020).  Same access family (no
        # access change); a different seam of the same 3GPP access.
        evidence, refs = _run_ran_leg(
            ran_server,
            session_id=session_id,
            payload=payload,
            journal=journal,
        )
        legs.append(evidence)
        ran_refs.extend(refs)

        # Leg 3: the non-3GPP leg (W021).  ACCESS CHANGE: 3GPP ->
        # non-3GPP with the SAME sacred session_id.
        journal.append(
            InteropEventType.ACCESS_CHANGED,
            ScenarioLegName.NON_THREEGPP_TUNNEL,
            "access change three-gpp -> non-three-gpp; session_id "
            "unchanged (never re-minted)",
        )
        evidence, refs = _run_wifi_leg(
            wifi_server,
            session_id=session_id,
            payload=payload,
            journal=journal,
            lookup=session_lookup,
        )
        legs.append(evidence)
        wifi_refs.extend(refs)

        # Leg 4: access change BACK to 3GPP (the W021 case_33
        # continuity pattern: release + re-bind, never a new session).
        journal.append(
            InteropEventType.ACCESS_CHANGED,
            ScenarioLegName.FIVE_G_CORE_REBIND,
            "access change non-three-gpp -> three-gpp; session_id "
            "unchanged (never re-minted)",
        )
        evidence, refs = _run_fivegc_leg(
            fivegc_server,
            integration_id="adcos:fivegc:interop-profile-rebind",
            session_id=session_id,
            payload=payload,
            journal=journal,
            leg_name=ScenarioLegName.FIVE_G_CORE_REBIND,
            lookup=session_lookup,
        )
        legs.append(evidence)
        fivegc_refs.extend(refs)
    finally:
        fivegc_server.close()
        ran_server.close()
        wifi_server.close()

    # Cross-family ref opacity (the identity-separation invariant).
    check_ref_opacity(
        fivegc_refs=tuple(fivegc_refs),
        ran_refs=tuple(ran_refs),
        wifi_refs=tuple(wifi_refs),
    )
    journal.append(
        InteropEventType.REF_OPACITY_VERIFIED,
        "profile",
        "cross-family ref opacity verified over %d refs (digests only; "
        "no raw adapter ref is journaled)"
        % (len(fivegc_refs) + len(ran_refs) + len(wifi_refs),),
    )

    # Session coherence: the SAME sacred session_id on every leg.
    divergent = [leg.leg for leg in legs if leg.session_id != session_id]
    if divergent:
        raise InteropError(
            InteropReasonCode.SESSION_DIVERGENCE,
            "legs carry divergent session ids: %s" % (divergent,),
        )
    journal.append(
        InteropEventType.SESSION_COHERENCE_VERIFIED,
        "profile",
        "one session_id identical across %d legs (%d three-gpp, %d "
        "non-three-gpp); never re-minted"
        % (
            len(legs),
            sum(1 for leg in legs if leg.access_kind == AccessLegKind.THREE_GPP),
            sum(1 for leg in legs if leg.access_kind == AccessLegKind.NON_THREE_GPP),
        ),
    )

    # The verified-state digest (legs + journal at verification time;
    # recorded BEFORE the terminal events so no circularity exists).
    verified_state = InteropRunResult(
        profile_digest=profile_digest,
        session_id=session_id,
        legs=tuple(legs),
        events=journal.events(),
    )
    journal.append(
        InteropEventType.PROFILE_VERIFIED,
        "profile",
        "verified-state digest %s over %d legs"
        % (verified_state.interop_digest(), len(legs)),
    )
    journal.append(
        InteropEventType.EVIDENCE_RECORDED,
        "profile",
        "evidence class B (automated verification) recorded over "
        "in-repo conformance peers; class C (real interoperability "
        "lab) remains OPEN and is NOT satisfied by this run",
    )
    return InteropRunResult(
        profile_digest=profile_digest,
        session_id=session_id,
        legs=tuple(legs),
        events=journal.events(),
    )


def verify_interop_replay(
    result: InteropRunResult,
    *,
    profile: ProfileDeclaration,
    session_id: str,
    session_lookup: Callable[[str], Optional[SessionFacts]],
    payload: bytes = DEFAULT_PROFILE_PAYLOAD,
    start_instant: str = DEFAULT_START_INSTANT,
) -> None:
    """Replay-verify a scenario result (the W036 discipline).

    Two independent checks:

    1. structural coherence of the GIVEN result (sequence contiguity,
       content-derived event ids, leg session coherence, verified
       byte-identical leg evidence);
    2. a FULL replay: the same inputs must reproduce the SAME run
       digest.  Any tampering with the recorded result (or any
       nondeterminism in the scenario) diverges and raises
       :class:`InteropError` with ``interop.replay-mismatch``.
    """
    if not isinstance(result, InteropRunResult):
        raise InteropError(
            InteropReasonCode.INVALID_INPUT,
            "result must be an InteropRunResult",
        )
    # 1. structural coherence.
    for index, event in enumerate(result.events):
        if event.sequence != index + 1:
            raise InteropError(
                InteropReasonCode.REPLAY_MISMATCH,
                "event sequence broken at %d (got %d)"
                % (index + 1, event.sequence),
            )
        recomputed = InteropEvent(
            sequence=event.sequence,
            instant=event.instant,
            kind=event.kind,
            subject=event.subject,
            detail=event.detail,
        )
        if recomputed.event_id() != event.event_id():
            raise InteropError(
                InteropReasonCode.REPLAY_MISMATCH,
                "event %d content does not match its id" % (event.sequence,),
            )
    for leg in result.legs:
        if leg.session_id != result.session_id:
            raise InteropError(
                InteropReasonCode.REPLAY_MISMATCH,
                "leg %r session_id diverges from the run session_id"
                % (leg.leg,),
            )
        if not leg.bytes_equal or leg.payload_sha256 != leg.echo_sha256:
            raise InteropError(
                InteropReasonCode.REPLAY_MISMATCH,
                "leg %r evidence is not a verified byte-identical "
                "round trip" % (leg.leg,),
            )
    # 2. the full replay (same inputs -> same digest).
    replayed = run_profile_scenario(
        profile,
        session_id=session_id,
        session_lookup=session_lookup,
        payload=payload,
        start_instant=start_instant,
    )
    if replayed.interop_digest() != result.interop_digest():
        raise InteropError(
            InteropReasonCode.REPLAY_MISMATCH,
            "replayed digest %s diverges from the recorded digest %s"
            % (replayed.interop_digest()[:16], result.interop_digest()[:16]),
        )
