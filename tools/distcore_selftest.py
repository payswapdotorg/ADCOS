#!/usr/bin/env python3
"""ADCOS distributed-core adapter self-test (WORK-024).

Mirrors the WORK-018/019/021/022/023 selftest discipline and verifies
the frozen WORK-024 handoff's required verification matrix:

* local traffic can REMAIN LOCAL (case 12 -- egress through a LOCAL
  binding reports locality=local and the remote provider's delivery
  log stays EMPTY; case 14 -- deterministic latency/locality over
  real WORK-011 LinkMetrics fixtures);
* remote gateway FAILOVER works (cases 16, 17, 19 -- the explicit
  transition preserves the logical session identity, the supersedes
  chain, and flips locality/latency deterministically; a partitioned
  old provider never blocks the failover; recovery fails back);
* 5G UPF and generic IP gateway functions COEXIST behind adapters
  (cases 11, 36, 37, 38, 39 -- the reference engines coexist AND the
  REAL WORK-018 ``IPIntegrationManager`` and REAL WORK-019
  ``FiveGCoreManager`` are composed behind
  ``BreakoutProviderContract`` adapters at the composition root);
* POLICY determines local vs remote breakout (cases 7, 15 -- a REAL
  tamper-evident WORK-010 ``PolicyDecision`` with an ALLOW effect is
  consumed as DATA; tampered/denied/stale/cross-session decisions
  fail closed; the manager never evaluates policy);
* session identity is preserved across gateway changes (cases 16,
  20, 21, 39 -- the sacred session_id never changes; no retroactive
  rebinding: superseded breakouts never carry traffic; provider
  swaps keep live breakouts on their owning sandbox);
* adapter/provider state cannot become core authority (cases 23,
  24, 26, 27, 30, 31 -- sandbox isolation, contract-violation
  discard, secret isolation, ACCESS-STATE-OUT canonical shape,
  standards-boundary and no-core-leakage audits);
* failover and partition behavior are proven with honest
  degradation (cases 17, 18, 19, 35);
* full determinism across repeated runs and PYTHONHASHSEED
  variation (cases 32, 33); frozen ``spec/`` byte-identity (case
  34);
* validate/commit transactional discipline: the identity-derivation
  nonce advances ONLY in commit phases, so failed operations
  (validate- or commit-phase) leave canonical state AND derivation
  state untouched, and the next successful derived refs are
  byte-identical to a clean twin run (case 40 -- the PR #24
  architectural-review regression, applied from day one).
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

# Make the repository root importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from adapters.distcore import (  # noqa: E402
    CONTEXT_SURFACE,
    CONTRACT_OPERATIONS,
    DEFAULT_STEP_BUDGET,
    DISTCORE_PREFIX,
    MAX_EGRESS_BYTES,
    RATE_KINDS_BPS,
    DistCoreError,
    DistCoreFailure,
    DistCoreReasonCode,
    DistCoreTechnologyAdapter,
    DistributedCoreManager,
    FAILURE_THRESHOLD_DEGRADED,
    FAILURE_THRESHOLD_FAILED,
    ReferenceIPGatewayEngine,
    ReferenceUPFEngine,
    STEP_CHARGES,
    AllocationState,
    BreakoutAllocation,
    BreakoutBinding,
    BreakoutDecision,
    BreakoutEgress,
    BreakoutMode,
    BreakoutState,
    DistCoreEvent,
    DistCoreObservation,
    EgressOutcome,
    EvidenceSourceClass,
    GatewayCandidate,
    GatewayDescriptor,
    GatewayEvidence,
    GatewayRoleClass,
    GatewayState,
    LinkMetricName,
    SessionReader,
    SessionView,
    derive_allocation_ref,
    derive_binding_id,
    derive_breakout_ref,
    derive_decision_ref,
    derive_gateway_claim_digest,
    derive_gateway_ref,
    derive_integration_id,
)
from adapters.distcore.contract import (  # noqa: E402
    BreakoutContext,
    BreakoutProviderContract,
)
from policy.model import PolicyDecision  # noqa: E402
from routing.model import (  # noqa: E402
    LinkMetrics,
    Path,
    aggregate_link_metrics,
    derive_path_id,
)

Result = Tuple[str, bool, str]


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# --------------------------------------------------------------------------
# Deterministic fixtures
# --------------------------------------------------------------------------

_NOW = "2026-06-01T12:00:00Z"
_T1 = "2026-06-01T12:01:00Z"
_T2 = "2026-06-01T12:02:00Z"
_T3 = "2026-06-01T12:03:00Z"
_T4 = "2026-06-01T12:04:00Z"
_T5 = "2026-06-01T12:05:00Z"
_FRESH = "2026-12-31T23:59:59Z"

_NODE_UE = "adcos:node:test.profile.v1:" + "a" * 64
_NODE_LOCAL_GW = "adcos:node:test.profile.v1:" + "b" * 64
_NODE_REMOTE_GW = "adcos:node:test.profile.v1:" + "c" * 64
_NODE_TRANSIT = "adcos:node:test.profile.v1:" + "d" * 64

_SESSION_ID = "sha256:" + "1" * 64
_SESSION_ID_2 = "sha256:" + "2" * 64

_PAYLOAD = b"local-breakout-payload"
_PAYLOAD_2 = b"remote-breakout-payload"

_LOCALITY = "village-A"

_LOCAL_LATENCY_MS = 5
_REMOTE_LATENCY_MS = 50

_LOCAL_CAP_BPS = 10_000_000
_REMOTE_CAP_BPS = 50_000_000


class _TestSessionReader(SessionReader):
    """The WORK-012 test double (the import-lock rule for test
    doubles: implements the same interface)."""

    def __init__(self, *known: str, secureable: bool = True) -> None:
        self._known = set(known)
        self._secureable = secureable

    def lookup(self, session_id: str) -> Optional[SessionView]:
        if session_id not in self._known:
            return None
        return SessionView(
            session_id=session_id,
            secureable=self._secureable,
            initiator_node_id=_NODE_UE,
            responder_node_id=_NODE_LOCAL_GW,
        )


_READER = _TestSessionReader(_SESSION_ID, _SESSION_ID_2)


def _allow_decision(*, evaluation_instant: str = _NOW, matched=("locality-allow",)):
    """A REAL tamper-evident WORK-010 ``PolicyDecision`` (the probe
    trick: construct once to get the canonical bytes, then construct
    the genuine id-bound instance)."""
    probe = PolicyDecision(
        decision_id="0" * 64, effect="allow", code="allow",
        detail="w024", matched_rule_ids=tuple(matched),
        policy_set_id="ps-1", policy_set_version=1,
        evaluation_instant=evaluation_instant,
    )
    return PolicyDecision(
        decision_id=hashlib.sha256(probe.canonical_bytes()).hexdigest(),
        effect="allow", code="allow", detail="w024",
        matched_rule_ids=tuple(matched), policy_set_id="ps-1",
        policy_set_version=1, evaluation_instant=evaluation_instant,
    )


def _deny_decision(*, evaluation_instant: str = _NOW):
    probe = PolicyDecision(
        decision_id="0" * 64, effect="deny", code="deny",
        detail="w024", matched_rule_ids=("deny-all",),
        policy_set_id="ps-1", policy_set_version=1,
        evaluation_instant=evaluation_instant,
    )
    return PolicyDecision(
        decision_id=hashlib.sha256(probe.canonical_bytes()).hexdigest(),
        effect="deny", code="deny", detail="w024",
        matched_rule_ids=("deny-all",), policy_set_id="ps-1",
        policy_set_version=1, evaluation_instant=evaluation_instant,
    )


def _metrics(latency_ms: int, capacity_bps: int) -> LinkMetrics:
    return LinkMetrics(
        latency_ms=latency_ms, loss_basis_points=0,
        capacity_bps=capacity_bps, energy_cost_millijoules=10,
        confidence_basis_points=10_000, observed_at=_NOW,
        freshness_until=_FRESH,
    )


def _local_path() -> Path:
    """The LOCAL breakout path: UE -> the local gateway node (real
    WORK-011 Path over real LinkMetrics fixtures)."""
    hops = ("link:%s:%s" % (_NODE_UE, _NODE_LOCAL_GW),)
    nodes = (_NODE_UE, _NODE_LOCAL_GW)
    metrics = aggregate_link_metrics((_metrics(_LOCAL_LATENCY_MS, _LOCAL_CAP_BPS),))
    return Path(
        path_id=derive_path_id(_NODE_UE, _NODE_LOCAL_GW, hops, nodes),
        source_node_id=_NODE_UE, destination_node_id=_NODE_LOCAL_GW,
        hops=hops, nodes=nodes, metrics=metrics, feasible=True,
    )


def _remote_path() -> Path:
    """The REMOTE breakout path: UE -> transit -> the remote gateway
    node (real WORK-011 Path; the local-first fixture is strictly
    lower-latency)."""
    hops = (
        "link:%s:%s" % (_NODE_UE, _NODE_TRANSIT),
        "link:%s:%s" % (_NODE_TRANSIT, _NODE_REMOTE_GW),
    )
    nodes = (_NODE_UE, _NODE_TRANSIT, _NODE_REMOTE_GW)
    metrics = aggregate_link_metrics(
        (
            _metrics(_REMOTE_LATENCY_MS // 2, _REMOTE_CAP_BPS),
            _metrics(_REMOTE_LATENCY_MS - _REMOTE_LATENCY_MS // 2, _REMOTE_CAP_BPS),
        )
    )
    return Path(
        path_id=derive_path_id(_NODE_UE, _NODE_REMOTE_GW, hops, nodes),
        source_node_id=_NODE_UE, destination_node_id=_NODE_REMOTE_GW,
        hops=hops, nodes=nodes, metrics=metrics, feasible=True,
    )


_LOCAL_PATH = _local_path()
_REMOTE_PATH = _remote_path()

_LOCAL_DESCRIPTOR = GatewayDescriptor(
    name="village-gateway", gateway_id="gw-local-1",
    node_id=_NODE_LOCAL_GW, role_class=GatewayRoleClass.IP_GATEWAY,
    locality_label=_LOCALITY, capacity_bps=_LOCAL_CAP_BPS,
    external_gateway_id="edge-gw-element-42",
)
_LOCAL_EVIDENCE = GatewayEvidence(
    observer_node_id=_NODE_LOCAL_GW, reporter_node_id=_NODE_LOCAL_GW,
    source_class=EvidenceSourceClass.DIRECT_OBSERVATION,
    observed_at=_NOW,
    claim_digest=derive_gateway_claim_digest(_LOCAL_DESCRIPTOR),
)
_REMOTE_DESCRIPTOR = GatewayDescriptor(
    name="core-upf", gateway_id="gw-remote-1",
    node_id=_NODE_REMOTE_GW, role_class=GatewayRoleClass.UPF,
    locality_label="region-core", capacity_bps=_REMOTE_CAP_BPS,
    external_gateway_id="upf-instance-7",
)
_REMOTE_EVIDENCE = GatewayEvidence(
    observer_node_id=_NODE_REMOTE_GW, reporter_node_id=_NODE_UE,
    source_class=EvidenceSourceClass.REMOTE_CLAIM,
    observed_at=_NOW,
    claim_digest=derive_gateway_claim_digest(_REMOTE_DESCRIPTOR),
)


def _full_stack(
    *, session_reader: SessionReader = _READER
) -> Tuple[DistributedCoreManager, ReferenceIPGatewayEngine, ReferenceUPFEngine]:
    """The canonical two-mode stack: a LOCAL reference provider and a
    REMOTE reference (UPF-shaped) provider, both gateways admitted
    with evidence, both paths registered, both decisions applied."""
    local_engine = ReferenceIPGatewayEngine()
    remote_engine = ReferenceUPFEngine()
    mgr = DistributedCoreManager(session_reader=session_reader)
    mgr.register_provider(
        local_engine, label="local", breakout_mode=BreakoutMode.LOCAL, now=_NOW
    )
    mgr.register_provider(
        remote_engine, label="remote", breakout_mode=BreakoutMode.REMOTE, now=_NOW
    )
    mgr.register_gateway(
        now=_NOW, label="local",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    mgr.register_gateway(
        now=_NOW, label="remote",
        descriptor=_REMOTE_DESCRIPTOR, evidence=_REMOTE_EVIDENCE,
    )
    mgr.register_path(now=_NOW, path=_LOCAL_PATH)
    mgr.register_path(now=_NOW, path=_REMOTE_PATH)
    decision_local = mgr.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
        locality_labels=(_LOCALITY,),
    )
    decision_remote = mgr.apply_policy_decision(
        now=_T1, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T1),
        mode=BreakoutMode.REMOTE,
    )
    assert decision_local.ok and decision_remote.ok
    return mgr, local_engine, remote_engine


def _establish_local(mgr: DistributedCoreManager, session_id: str = _SESSION_ID):
    decision = mgr.apply_policy_decision(
        now=_T2, session_id=session_id,
        policy_decision=_allow_decision(evaluation_instant=_T2),
        mode=BreakoutMode.LOCAL,
        locality_labels=(_LOCALITY,),
    )
    assert decision.ok, decision.detail
    return mgr.establish_breakout(
        now=_T2, session_id=session_id,
        decision_ref=decision.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )


def _establish_remote(mgr: DistributedCoreManager, session_id: str = _SESSION_ID):
    decision = mgr.apply_policy_decision(
        now=_T3, session_id=session_id,
        policy_decision=_allow_decision(evaluation_instant=_T3),
        mode=BreakoutMode.REMOTE,
    )
    assert decision.ok, decision.detail
    return mgr.establish_breakout(
        now=_T3, session_id=session_id,
        decision_ref=decision.value.decision_ref,
        path_ref=_REMOTE_PATH.path_id,
    )


def _src(module: str) -> str:
    path = os.path.join(_ROOT, "adapters", "distcore", module)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


# --------------------------------------------------------------------------
# Real-seam composition adapters (composition-root code; the family
# imports no other family -- the accepted seam managers are wrapped
# HERE, behind BreakoutProviderContract)
# --------------------------------------------------------------------------


def _build_dual_reader():
    """Build a reader satisfying the distcore, WORK-018, and WORK-019
    SessionReader ABCs simultaneously (composition-root wiring)."""
    import adapters.ip.contract as _ip_contract
    import adapters.fivegc.contract as _fivegc_contract

    class _Reader(
        SessionReader,
        _ip_contract.SessionReader,
        _fivegc_contract.SessionReader,
    ):
        def __init__(self, known_sessions=None, secureable=True, store=None):
            self._known = set(known_sessions or (_SESSION_ID,))
            self._secureable = secureable
            self._store = store

        def lookup(self, session_id: str):
            if self._store is not None:
                session = self._store.get(session_id)
                if session is None:
                    return None
                from sessions import SessionState

                view = SessionView(
                    session_id=session.session_id,
                    secureable=session.state in (
                        SessionState.ESTABLISHED, SessionState.DEGRADED
                    ),
                    initiator_node_id=session.binding.source_node_id,
                    responder_node_id=session.binding.destination_node_id,
                )
                return view
            if session_id not in self._known:
                return None
            return SessionView(
                session_id=session_id,
                secureable=self._secureable,
                initiator_node_id=_NODE_UE,
                responder_node_id=_NODE_LOCAL_GW,
            )

    return _Reader


_DualReader = _build_dual_reader()


class _IPSeamLocalProvider(BreakoutProviderContract):
    """The REAL WORK-018 seam as a LOCAL breakout provider
    (composition-root adapter; the family boundary is never crossed
    by the seam types -- they stay inside this adapter).

    establish -> the real ``IPIntegrationManager.bind_session`` (a
    REAL mediated IP binding with a content-derived flow); egress ->
    the real ``app_socket().send()`` (the LOCK-019 app-transparent
    data path through the real egress mediation); release -> the real
    ``close_binding``.
    """

    label = "ip-seam-local-breakout"

    def __init__(self, ip_manager: Any) -> None:
        self._ip = ip_manager
        self._gateways: Dict[str, GatewayDescriptor] = {}
        self._breakouts: Dict[str, Tuple[str, str]] = {}
        self._seq = 0
        self._reserved = 0
        self._available = True
        self._open = False
        self._egress_count = 0
        self._egress_failures = 0
        self._egress_bytes = 0

    # -- reference-model partition control (composition-root test
    #    control; drives establish/egress to fail closed) ------------

    def partition(self) -> None:
        self._available = False

    def restore(self) -> None:
        self._available = True

    def delivered_total(self) -> int:
        return self._egress_count

    # -- contract -----------------------------------------------------

    def open(self, context: BreakoutContext) -> None:
        result = self._ip.open(now=context.now())
        if not result.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "ip seam open failed",
            )
        self._open = True

    def register_gateway(
        self, context: BreakoutContext, *, descriptor, evidence
    ) -> GatewayCandidate:
        if not self._available:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "ip seam partitioned",
            )
        ref = derive_gateway_ref(
            descriptor.name, descriptor.gateway_id,
            descriptor.node_id, descriptor.role_class,
        )
        self._gateways[ref] = descriptor
        return GatewayCandidate(
            gateway_ref=ref, name=descriptor.name,
            gateway_id=descriptor.gateway_id, node_id=descriptor.node_id,
            role_class=descriptor.role_class,
            locality_label=descriptor.locality_label,
            capacity_bps=descriptor.capacity_bps,
            state=GatewayState.AVAILABLE,
            evidence_source_class=evidence.source_class,
            external_gateway_id=descriptor.external_gateway_id,
        )

    def close_gateway(self, context: BreakoutContext, *, gateway_ref: str) -> None:
        if gateway_ref not in self._gateways:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNKNOWN, "unknown gateway"
            )
        self._gateways.pop(gateway_ref)

    def allocate(
        self, context: BreakoutContext, *, kind, quantity_base, purpose
    ) -> BreakoutAllocation:
        if kind not in RATE_KINDS_BPS:
            raise DistCoreError(DistCoreReasonCode.INVALID_INPUT, "kind")
        available = (
            sum(d.capacity_bps for d in self._gateways.values())
            if self._available else 0
        )
        if quantity_base > available - self._reserved:
            raise DistCoreError(
                DistCoreReasonCode.CAPACITY_EXHAUSTED, "exhausted"
            )
        self._seq += 1
        allocation = BreakoutAllocation(
            allocation_ref=derive_allocation_ref(
                kind, quantity_base, purpose, self._seq
            ),
            kind=kind, quantity_base=quantity_base, purpose=purpose,
            state=AllocationState.RESERVED,
        )
        self._reserved += quantity_base
        return allocation

    def release(self, context: BreakoutContext, *, allocation_ref: str) -> None:
        # The composition-root ledger releases by ref (kept simple:
        # the tests release the only outstanding admission).
        self._reserved = 0

    def establish_breakout(
        self, context: BreakoutContext, *, session_id, gateway_ref,
        path_ref, requirements=None,
    ) -> BreakoutBinding:
        if not self._available:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "ip seam partitioned (establish fails closed)",
            )
        result = self._ip.bind_session(
            session_id=session_id,
            transport_ref="distcore-ip-seam-transport",
            route_ref=path_ref, now=context.now(),
        )
        if not result.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "ip seam bind failed (%s)" % result.reason,
            )
        binding = result.value
        self._seq += 1
        breakout_ref = derive_breakout_ref(
            session_id, gateway_ref, path_ref, self._seq
        )
        self._breakouts[breakout_ref] = (session_id, gateway_ref)
        return BreakoutBinding(
            session_id=session_id, breakout_ref=breakout_ref,
            binding_id=derive_binding_id(session_id, breakout_ref),
            gateway_ref=gateway_ref, path_ref=path_ref,
            state=BreakoutState.ACTIVE,
            established_instant=context.now(),
        )

    def release_breakout(
        self, context: BreakoutContext, *, breakout_ref: str
    ) -> None:
        entry = self._breakouts.pop(breakout_ref, None)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN, "unknown breakout"
            )
        session_id, _ = entry
        binding = self._ip.binding_for_session(session_id)
        if binding is not None:
            result = self._ip.close_binding(
                ip_binding_ref=binding.binding_id, now=context.now()
            )
            if not result.ok:
                raise DistCoreError(
                    DistCoreReasonCode.DISTCORE_FAILURE,
                    "ip seam close failed (%s)" % result.reason,
                )

    def egress(
        self, context: BreakoutContext, *, breakout_ref, payload
    ) -> EgressOutcome:
        entry = self._breakouts.get(breakout_ref)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN, "unknown breakout"
            )
        session_id, gateway_ref = entry
        if not self._available:
            self._egress_failures += 1
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "ip seam partitioned (egress fails closed)",
            )
        socket = self._ip.app_socket(
            session_id=session_id, now=context.now()
        )
        if not socket.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "ip seam app socket failed (%s)" % socket.reason,
            )
        sent = socket.value.send(payload)
        self._egress_count += 1
        self._egress_bytes += sent
        return EgressOutcome(
            breakout_ref=breakout_ref, gateway_ref=gateway_ref,
            egress_instant=context.now(), payload_bytes=sent,
        )

    def observe(self, context: BreakoutContext) -> DistCoreObservation:
        available = len(self._gateways) if self._available else 0
        unavailable = 0 if self._available else len(self._gateways)
        return DistCoreObservation(
            samples=(
                (LinkMetricName.LINK_UP, available),
                (LinkMetricName.RX_BYTES_TOTAL, 0),
                (LinkMetricName.TX_BYTES_TOTAL, self._egress_bytes),
                (LinkMetricName.RX_ERROR_COUNT, 0),
                (LinkMetricName.TX_ERROR_COUNT, self._egress_failures),
                (LinkMetricName.RETRANSMIT_COUNT, 0),
            ),
            available_gateways=available,
            unavailable_gateways=unavailable,
            active_breakouts=len(self._breakouts),
            delivered_egress=self._egress_count,
            failed_egress=self._egress_failures,
        )

    def health(self) -> str:
        if not self._open:
            return "NOT_RUNNING"
        return "HEALTHY" if self._available else "DEGRADED"

    def close(self, context: BreakoutContext) -> None:
        if self._breakouts:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "ip seam has outstanding breakouts",
            )
        self._open = False


class _FiveGCSeamRemoteProvider(BreakoutProviderContract):
    """The REAL WORK-019 seam as a REMOTE breakout provider
    (composition-root adapter).

    establish -> the real ``FiveGCoreManager`` ladder
    (``bind_session`` -> ``authenticate`` -> ``establish_pdu_session``
    -- a REAL PDU-session anchor with a UE IPv6 address); egress ->
    the real ``egress_pdu`` (real bytes through the mediated
    contract path); release -> the real ``release_pdu_session``.
    """

    label = "fivegc-seam-remote-breakout"

    def __init__(
        self, fivegc_manager: Any, *, supi: str, snssai: Any, dnn: Any
    ) -> None:
        self._fivegc = fivegc_manager
        self._supi = supi
        self._snssai = snssai
        self._dnn = dnn
        self._gateways: Dict[str, GatewayDescriptor] = {}
        self._breakouts: Dict[str, Tuple[str, str, str]] = {}
        self._seq = 0
        self._available = True
        self._open = False
        self._egress_count = 0
        self._egress_failures = 0
        self._egress_bytes = 0
        self._anchors: Dict[str, str] = {}

    def partition(self) -> None:
        self._available = False

    def restore(self) -> None:
        self._available = True

    def delivered_total(self) -> int:
        return self._egress_count

    def open(self, context: BreakoutContext) -> None:
        result = self._fivegc.provision_subscriber(
            now=context.now(), supi=self._supi,
            credential_slot_name="fivegc-credentials",
            subscribed_snssai=self._snssai, subscribed_dnn=self._dnn,
        )
        if not result.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "fivegc seam subscriber provisioning failed",
            )
        self._open = True

    def register_gateway(
        self, context: BreakoutContext, *, descriptor, evidence
    ) -> GatewayCandidate:
        if not self._available:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "fivegc seam partitioned",
            )
        ref = derive_gateway_ref(
            descriptor.name, descriptor.gateway_id,
            descriptor.node_id, descriptor.role_class,
        )
        self._gateways[ref] = descriptor
        return GatewayCandidate(
            gateway_ref=ref, name=descriptor.name,
            gateway_id=descriptor.gateway_id, node_id=descriptor.node_id,
            role_class=descriptor.role_class,
            locality_label=descriptor.locality_label,
            capacity_bps=descriptor.capacity_bps,
            state=GatewayState.AVAILABLE,
            evidence_source_class=evidence.source_class,
            external_gateway_id=descriptor.external_gateway_id,
        )

    def close_gateway(self, context: BreakoutContext, *, gateway_ref: str) -> None:
        if gateway_ref not in self._gateways:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNKNOWN, "unknown anchor"
            )
        self._gateways.pop(gateway_ref)

    def allocate(
        self, context: BreakoutContext, *, kind, quantity_base, purpose
    ) -> BreakoutAllocation:
        if kind not in RATE_KINDS_BPS:
            raise DistCoreError(DistCoreReasonCode.INVALID_INPUT, "kind")
        available = (
            sum(d.capacity_bps for d in self._gateways.values())
            if self._available else 0
        )
        if quantity_base > available:
            raise DistCoreError(
                DistCoreReasonCode.CAPACITY_EXHAUSTED, "exhausted"
            )
        self._seq += 1
        return BreakoutAllocation(
            allocation_ref=derive_allocation_ref(
                kind, quantity_base, purpose, self._seq
            ),
            kind=kind, quantity_base=quantity_base, purpose=purpose,
            state=AllocationState.RESERVED,
        )

    def release(self, context: BreakoutContext, *, allocation_ref: str) -> None:
        return None

    def establish_breakout(
        self, context: BreakoutContext, *, session_id, gateway_ref,
        path_ref, requirements=None,
    ) -> BreakoutBinding:
        if not self._available:
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "fivegc seam partitioned (establish fails closed)",
            )
        bound = self._fivegc.bind_session(
            now=context.now(), session_id=session_id, supi=self._supi,
            snssai=self._snssai, dnn=self._dnn,
        )
        if not bound.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "fivegc seam bind failed (%s)" % bound.reason,
            )
        pdu_ref = bound.value.pdu_session_ref
        auth = self._fivegc.authenticate(now=context.now(), pdu_session_ref=pdu_ref)
        if not auth.ok or not auth.value.success:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "fivegc seam authentication failed",
            )
        established = self._fivegc.establish_pdu_session(
            now=context.now(), pdu_session_ref=pdu_ref
        )
        if not established.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "fivegc seam PDU session establishment failed",
            )
        self._seq += 1
        breakout_ref = derive_breakout_ref(
            session_id, gateway_ref, path_ref, self._seq
        )
        self._breakouts[breakout_ref] = (session_id, gateway_ref, pdu_ref)
        self._anchors[breakout_ref] = established.value.ue_ipv6
        return BreakoutBinding(
            session_id=session_id, breakout_ref=breakout_ref,
            binding_id=derive_binding_id(session_id, breakout_ref),
            gateway_ref=gateway_ref, path_ref=path_ref,
            state=BreakoutState.ACTIVE,
            established_instant=context.now(),
        )

    def release_breakout(
        self, context: BreakoutContext, *, breakout_ref: str
    ) -> None:
        entry = self._breakouts.pop(breakout_ref, None)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN, "unknown breakout"
            )
        _, _, pdu_ref = entry
        result = self._fivegc.release_pdu_session(
            now=context.now(), pdu_session_ref=pdu_ref
        )
        if not result.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "fivegc seam release failed (%s)" % result.reason,
            )

    def egress(
        self, context: BreakoutContext, *, breakout_ref, payload
    ) -> EgressOutcome:
        entry = self._breakouts.get(breakout_ref)
        if entry is None:
            raise DistCoreError(
                DistCoreReasonCode.BREAKOUT_UNKNOWN, "unknown breakout"
            )
        session_id, gateway_ref, pdu_ref = entry
        if not self._available:
            self._egress_failures += 1
            raise DistCoreError(
                DistCoreReasonCode.GATEWAY_UNAVAILABLE,
                "fivegc seam partitioned (egress fails closed)",
            )
        result = self._fivegc.egress_pdu(
            now=context.now(), pdu_session_ref=pdu_ref, payload=payload
        )
        if not result.ok:
            raise DistCoreError(
                DistCoreReasonCode.DISTCORE_FAILURE,
                "fivegc seam egress failed (%s)" % result.reason,
            )
        self._egress_count += 1
        self._egress_bytes += len(result.value)
        return EgressOutcome(
            breakout_ref=breakout_ref, gateway_ref=gateway_ref,
            egress_instant=context.now(), payload_bytes=len(result.value),
        )

    def ue_ipv6_for(self, breakout_ref: str) -> str:
        return self._anchors.get(breakout_ref, "")

    def observe(self, context: BreakoutContext) -> DistCoreObservation:
        available = len(self._gateways) if self._available else 0
        unavailable = 0 if self._available else len(self._gateways)
        return DistCoreObservation(
            samples=(
                (LinkMetricName.LINK_UP, available),
                (LinkMetricName.RX_BYTES_TOTAL, 0),
                (LinkMetricName.TX_BYTES_TOTAL, self._egress_bytes),
                (LinkMetricName.RX_ERROR_COUNT, 0),
                (LinkMetricName.TX_ERROR_COUNT, self._egress_failures),
                (LinkMetricName.RETRANSMIT_COUNT, 0),
            ),
            available_gateways=available,
            unavailable_gateways=unavailable,
            active_breakouts=len(self._breakouts),
            delivered_egress=self._egress_count,
            failed_egress=self._egress_failures,
        )

    def health(self) -> str:
        if not self._open:
            return "NOT_RUNNING"
        return "HEALTHY" if self._available else "DEGRADED"

    def close(self, context: BreakoutContext) -> None:
        if self._breakouts:
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "fivegc seam has outstanding breakouts",
            )
        self._open = False


def _compose_real_session(variant: str = "5"):
    """Compose a REAL WORK-012 ESTABLISHED session driven by a REAL
    routing decision over a REAL topology graph (the WORK-022/023
    composition recipe); returns (store, live_session_id, decision,
    selected_path)."""
    from resources import ResourceStore
    from routing import RoutingContext, RoutingEngine
    from sessions import SessionState, SessionStore
    from topology import (
        ClaimType,
        SourceClass,
        TopologyClaim,
        TopologyGraph,
        make_link_subject,
    )

    node_a = "adcos:node:test.profile.v1:" + variant * 64
    node_b = _NODE_LOCAL_GW
    decision = _allow_decision()
    graph = TopologyGraph()
    graph.merge(
        TopologyClaim(
            subject=make_link_subject(node_a, node_b), reporter=node_a,
            claim_type=ClaimType.LINK_STATE, value="up",
            source_class=SourceClass.SELF_ADVERTISEMENT,
            issued_at=_NOW, freshness_until=_FRESH, sequence=1,
        )
    )
    graph.merge(
        TopologyClaim(
            subject=node_b, reporter=node_a,
            claim_type=ClaimType.REACHABLE, value="true",
            source_class=SourceClass.DIRECT_OBSERVATION,
            issued_at=_NOW, freshness_until=_FRESH, sequence=1,
        )
    )
    evaluation = RoutingEngine().evaluate(
        RoutingContext(
            source_node_id=node_a, destination_node_id=node_b,
            topology=graph, resources=ResourceStore(),
            evaluation_instant=_NOW, policy_decision=decision,
            link_metrics={
                make_link_subject(node_a, node_b): _metrics(
                    _LOCAL_LATENCY_MS, _LOCAL_CAP_BPS
                )
            },
        )
    )
    if evaluation.decision is None or evaluation.decision.selected is None:
        raise AssertionError("routing composition failed")
    store = SessionStore()
    created = store.create(
        evaluation.decision, decision,
        source_node_id=node_a, destination_node_id=node_b,
        creation_instant=_NOW,
    )
    if not created.ok:
        raise AssertionError("session creation failed")
    sid = created.session.session_id
    store.transition(sid, SessionState.AUTHORIZED, event_instant=_NOW)
    store.transition(sid, SessionState.ESTABLISHED, event_instant=_NOW)
    return store, sid, decision, evaluation.decision.selected


# --------------------------------------------------------------------------
# A WORK-018 TopologyReader returning an EVIDENCED gateway claim for
# the local gateway node (the W018 gateway-role discipline consumed
# by the real IP seam).
# --------------------------------------------------------------------------


def _build_topology_reader():
    from adapters.ip.contract import GatewayClaim, TopologyReader
    from adapters.ip.model import IPv6Address, IPv6Prefix

    prefix = IPv6Prefix(
        address=IPv6Address(text="2001:db8:aa::"),
        prefix_len=64, delegation_source="manual",
    )

    class _Topo(TopologyReader):
        def gateway_for(self, destination):
            return GatewayClaim(
                node_id=_NODE_LOCAL_GW,
                destination_prefix=prefix,
                evidence_digest="e" * 64,
                claim_instant=_NOW,
            )

    return _Topo()


# --------------------------------------------------------------------------
# Family surface and least-authority context
# --------------------------------------------------------------------------


def case_01_family_surface_frozen() -> Result:
    name = "case_01_family_surface_frozen"
    if CONTRACT_OPERATIONS != (
        "open", "register_gateway", "close_gateway", "allocate",
        "release", "establish_breakout", "release_breakout", "egress",
        "observe", "health", "close",
    ):
        return fail(name, "CONTRACT_OPERATIONS changed: %s" % (CONTRACT_OPERATIONS,))
    if len(DistCoreReasonCode.values()) != 25:
        return fail(name, "reason-code count drift: %d" % len(DistCoreReasonCode.values()))
    if STEP_CHARGES != {
        "open": 4, "register_gateway": 8, "close_gateway": 4,
        "allocate": 6, "release": 3, "establish_breakout": 8,
        "release_breakout": 3, "egress": 4, "observe": 2,
        "health": 1, "close": 4,
    }:
        return fail(name, "STEP_CHARGES changed")
    if CONTEXT_SURFACE != frozenset(
        {"integration_id", "now", "charge", "steps_left", "session_reader"}
    ):
        return fail(name, "CONTEXT_SURFACE changed")
    if DEFAULT_STEP_BUDGET != 10000 or FAILURE_THRESHOLD_DEGRADED != 2 or FAILURE_THRESHOLD_FAILED != 5:
        return fail(name, "sandbox constants drifted")
    if DISTCORE_PREFIX != "distcore":
        return fail(name, "prefix drifted")
    # Prefix disjointness (structural): the family ref root namespace
    # is disjoint from every other family's.
    sample = derive_gateway_ref(
        "n", "g", _NODE_LOCAL_GW, GatewayRoleClass.IP_GATEWAY
    )
    if not sample.startswith("distcore:gateway:"):
        return fail(name, "gateway ref root drifted: %s" % sample[:20])
    for other in ("adcos:node:", "adcos:adapter:", "adcos:transport:",
                  "adcos:ipint:", "mesh:", "backhaul:", "wifi:",
                  "adcos:fivegc", "sha256:"):
        if sample.startswith(other):
            return fail(name, "gateway ref collides with %r" % other)
    # Distinct ref kinds are disjoint namespaces.
    ref_breakout = "distcore:breakout:" + "0" * 32
    ref_binding = "distcore:binding:" + "0" * 32
    ref_decision = "distcore:decision:" + "0" * 32
    ref_alloc = "distcore:alloc:" + "0" * 32
    for ref, kind in ((ref_breakout, "breakout"), (ref_binding, "binding"),
                      (ref_decision, "decision"), (ref_alloc, "alloc")):
        try:
            from adapters.distcore.validation import validate_opaque_ref
            validate_opaque_ref(ref, kind)
        except DistCoreError:
            return fail(name, "ref grammar rejected %s" % ref)
    return ok(name, "11-op contract, 25 reason codes, STEP_CHARGES, "
                    "CONTEXT_SURFACE, prefix disjointness all pinned")


def case_02_context_least_authority() -> Result:
    name = "case_02_context_least_authority"
    ctx = BreakoutContext("distcore:test", _NOW, 100, None)
    # Immutable facade: attribute injection is rejected.
    try:
        ctx.integration_id = "x"  # type: ignore[misc]
        return fail(name, "context attribute injection accepted")
    except TypeError:
        pass
    try:
        del ctx.now  # type: ignore[misc]
        return fail(name, "context attribute deletion accepted")
    except TypeError:
        pass
    if ctx.integration_id != "distcore:test" or ctx.now() != _NOW:
        return fail(name, "context surface values drifted")
    # Budget (hang model).
    ctx.charge(60)
    if ctx.steps_left() != 40:
        return fail(name, "charge accounting broken")
    try:
        ctx.charge(41)
        return fail(name, "budget overdraw accepted")
    except Exception as exc:
        if type(exc).__name__ != "_BudgetExhausted":
            return fail(name, "wrong sentinel: %s" % type(exc).__name__)
    # Absent authority fail-closed: the rejecting reader returns
    # None for every lookup.
    if ctx.session_reader().lookup(_SESSION_ID) is not None:
        return fail(name, "absent session authority fabricated bindability")
    # Surface: exactly the five least-authority members.
    surface = set()
    for attr in ("integration_id", "now", "charge", "steps_left", "session_reader"):
        if callable(getattr(ctx, attr, None)) or isinstance(
            getattr(ctx, attr, None), str
        ):
            surface.add(attr)
    if surface != set(CONTEXT_SURFACE):
        return fail(name, "context surface drifted: %s" % sorted(surface))
    return ok(name, "immutable least-authority facade; budget hang model; "
                    "absent authority fail-closed")


def case_03_model_invariants() -> Result:
    name = "case_03_model_invariants"
    # Deterministic derivation.
    g1 = derive_gateway_ref("n", "g", _NODE_LOCAL_GW, GatewayRoleClass.IP_GATEWAY)
    g2 = derive_gateway_ref("n", "g", _NODE_LOCAL_GW, GatewayRoleClass.IP_GATEWAY)
    if g1 != g2:
        return fail(name, "gateway ref derivation not deterministic")
    if g1 == derive_gateway_ref("n2", "g", _NODE_LOCAL_GW, GatewayRoleClass.IP_GATEWAY):
        return fail(name, "gateway identity ignores the name")
    if g1 == derive_gateway_ref("n", "g", _NODE_LOCAL_GW, GatewayRoleClass.UPF):
        return fail(name, "gateway identity ignores the role")
    # The EXTERNAL seam id / locality / capacity are identity-EXCLUDED.
    d1 = GatewayDescriptor(name="n", gateway_id="g", node_id=_NODE_LOCAL_GW,
                           role_class=GatewayRoleClass.IP_GATEWAY,
                           locality_label="L", capacity_bps=5,
                           external_gateway_id="elem-1")
    d2 = GatewayDescriptor(name="n", gateway_id="g", node_id=_NODE_LOCAL_GW,
                           role_class=GatewayRoleClass.IP_GATEWAY)
    if derive_gateway_ref(d1.name, d1.gateway_id, d1.node_id, d1.role_class) != \
            derive_gateway_ref(d2.name, d2.gateway_id, d2.node_id, d2.role_class):
        return fail(name, "identity content changed with DATA-only fields")
    if derive_gateway_claim_digest(d1) == derive_gateway_claim_digest(d2):
        return fail(name, "claim digest ignores the claim content")
    # Tamper-evident constructors: a tampered binding id is rejected.
    seq = 1
    ref = derive_breakout_ref(_SESSION_ID, g1, _LOCAL_PATH.path_id, seq)
    binding_id = derive_binding_id(_SESSION_ID, ref)
    try:
        BreakoutBinding(
            session_id=_SESSION_ID, breakout_ref=ref,
            binding_id="distcore:binding:" + "0" * 32,
            gateway_ref=g1, path_ref=_LOCAL_PATH.path_id,
            state=BreakoutState.ACTIVE, established_instant=_NOW,
        )
        return fail(name, "tampered binding_id accepted")
    except DistCoreError:
        pass
    # A tampered decision ref is rejected.
    decision = BreakoutDecision(
        decision_ref=derive_decision_ref(_SESSION_ID, "f" * 64, BreakoutMode.LOCAL, _NOW),
        session_id=_SESSION_ID, policy_decision_id="f" * 64,
        policy_effect="allow", mode=BreakoutMode.LOCAL,
        matched_rule_ids=("r1",), locality_labels=(_LOCALITY,),
        applied_instant=_NOW,
    )
    try:
        BreakoutDecision(
            decision_ref="distcore:decision:" + "0" * 32,
            session_id=_SESSION_ID, policy_decision_id="f" * 64,
            policy_effect="allow", mode=BreakoutMode.LOCAL,
            matched_rule_ids=("r1",), locality_labels=(_LOCALITY,),
            applied_instant=_NOW,
        )
        return fail(name, "tampered decision_ref accepted")
    except DistCoreError:
        pass
    # A DENIED effect never constructs a breakout decision.
    try:
        BreakoutDecision(
            decision_ref=derive_decision_ref(_SESSION_ID, "f" * 64, BreakoutMode.LOCAL, _NOW),
            session_id=_SESSION_ID, policy_decision_id="f" * 64,
            policy_effect="deny", mode=BreakoutMode.LOCAL,
            matched_rule_ids=(), locality_labels=(),
            applied_instant=_NOW,
        )
        return fail(name, "deny-effect decision accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.DECISION_DENIED:
            return fail(name, "deny-effect mistyped: %s" % exc.reason)
    # Vocabularies.
    if BreakoutMode.values() != ("local", "remote"):
        return fail(name, "mode vocabulary drifted")
    if GatewayRoleClass.values() != ("ip-gateway", "upf", "wifi-gateway", "backhaul-gateway"):
        return fail(name, "role vocabulary drifted")
    if EvidenceSourceClass.values() != ("direct-observation", "remote-claim"):
        return fail(name, "evidence vocabulary drifted")
    if len(LinkMetricName.values()) != 6:
        return fail(name, "metric vocabulary drifted")
    return ok(name, "deterministic derivations; identity-excluded DATA "
                    "fields; tamper-evident binding/decision constructors; "
                    "deny-effect rejected at construction")


def case_04_validation_vocabulary() -> Result:
    name = "case_04_validation_vocabulary"
    from adapters.distcore.validation import (
        assert_ref_session_separation,
        reject_credential_like_text,
        validate_external_gateway_id,
        validate_locality_label,
        validate_node_id,
        validate_opaque_ref,
        validate_path_ref,
        validate_session_ref,
    )
    # Ref grammar.
    for bad in ("", "distcore:gateway:", "mesh:link:" + "0" * 32,
                "distcore:gateway:" + "0" * 31, "distcore:gw:" + "0" * 32):
        try:
            validate_opaque_ref(bad)
            return fail(name, "malformed ref accepted: %r" % bad)
        except DistCoreError:
            pass
    # Kind enforcement.
    try:
        validate_opaque_ref("distcore:gateway:" + "0" * 32, "breakout")
        return fail(name, "kind mismatch accepted")
    except DistCoreError:
        pass
    # Path / session refs.
    if validate_path_ref(_LOCAL_PATH.path_id) != _LOCAL_PATH.path_id:
        return fail(name, "path ref rejected")
    try:
        validate_path_ref("distcore:gateway:" + "0" * 32)
        return fail(name, "family ref accepted as path ref")
    except DistCoreError:
        pass
    if validate_session_ref(_SESSION_ID) != _SESSION_ID:
        return fail(name, "session ref rejected")
    # Node id.
    if validate_node_id(_NODE_UE) != _NODE_UE:
        return fail(name, "node id rejected")
    try:
        validate_node_id("node-a")
        return fail(name, "malformed node id accepted")
    except DistCoreError:
        pass
    # External gateway ids are DATA and must not match ADCOS grammars.
    if validate_external_gateway_id("upf-instance-7") != "upf-instance-7":
        return fail(name, "external id rejected")
    for bad in ("adcos:node:x", "distcore:gateway:" + "0" * 32,
                "sha256:" + "0" * 64, "mesh:link:" + "0" * 32):
        try:
            validate_external_gateway_id(bad)
            return fail(name, "identity-colliding external id accepted: %r" % bad)
        except DistCoreError as exc:
            if exc.reason != DistCoreReasonCode.ACCESS_SESSION_COLLAPSE:
                return fail(name, "external id collision mistyped")
    # Locality labels.
    if validate_locality_label(_LOCALITY) != _LOCALITY:
        return fail(name, "locality label rejected")
    try:
        validate_locality_label("x" * 65)
        return fail(name, "overlong locality label accepted")
    except DistCoreError:
        pass
    # Identity separation.
    assert_ref_session_separation(
        "distcore:breakout:" + "a" * 32, _SESSION_ID
    )
    try:
        assert_ref_session_separation(_SESSION_ID[:15] + _SESSION_ID[15:], _SESSION_ID)
        # the session id trivially embeds itself; craft the real case:
        ref_with_fragment = "distcore:breakout:" + _SESSION_ID[7:23]
        assert_ref_session_separation(ref_with_fragment, _SESSION_ID)
        return fail(name, "session-embedding ref accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ACCESS_SESSION_COLLAPSE:
            return fail(name, "identity collapse mistyped: %s" % exc.reason)
    # Credential-like text.
    for secretish in ("gateway_password", "shared-secret", "psk", "UPF_KEY"):
        try:
            reject_credential_like_text(secretish, label="probe")
            return fail(name, "credential-like text accepted: %r" % secretish)
        except DistCoreError:
            pass
    return ok(name, "ref grammars, kind enforcement, external-id DATA "
                    "discipline, identity separation, credential-like "
                    "rejection")


def case_05_provider_registration() -> Result:
    name = "case_05_provider_registration"
    mgr = DistributedCoreManager(session_reader=_READER)
    if mgr.computed_health() != "NOT_RUNNING":
        return fail(name, "pre-registration health not NOT_RUNNING")
    if mgr.capabilities() != ():
        return fail(name, "pre-registration capabilities not empty")
    # Non-contract objects are rejected (isinstance, no duck typing).
    try:
        mgr.register_provider(object(), label="x", breakout_mode="local", now=_NOW)
        return fail(name, "non-contract implementation accepted")
    except DistCoreError:
        pass
    # Bad mode vocabulary.
    try:
        mgr.register_provider(
            ReferenceIPGatewayEngine(), label="x", breakout_mode="both", now=_NOW
        )
        return fail(name, "invalid breakout mode accepted")
    except DistCoreError:
        pass
    r1 = mgr.register_provider(
        ReferenceIPGatewayEngine(), label="local",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    if not r1.ok:
        return fail(name, "registration failed: %s" % r1.detail)
    # Duplicate label.
    try:
        mgr.register_provider(
            ReferenceIPGatewayEngine(), label="local",
            breakout_mode=BreakoutMode.LOCAL, now=_NOW,
        )
        return fail(name, "duplicate label accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.BINDING_EXISTS:
            return fail(name, "duplicate label mistyped")
    # Registration without a provider -> ILLEGAL_STATE on ops.
    mgr2 = DistributedCoreManager(session_reader=_READER)
    try:
        mgr2.allocate(now=_NOW, kind="bandwidth", quantity_base=1, purpose="p")
        return fail(name, "allocate without provider accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ILLEGAL_STATE:
            return fail(name, "no-provider mistyped: %s" % exc.reason)
    # The default provider becomes the first registration.
    mgr3 = DistributedCoreManager(session_reader=_READER)
    mgr3.register_provider(
        ReferenceUPFEngine(), label="upf",
        breakout_mode=BreakoutMode.REMOTE, now=_NOW,
    )
    if "capability.core.local-breakout" in mgr3.capabilities():
        return fail(name, "local-breakout capability without a LOCAL provider")
    if "capability.profile.distcore.remote-breakout" not in mgr3.capabilities():
        return fail(name, "remote capability missing")
    mgr3.register_provider(
        ReferenceIPGatewayEngine(), label="gw",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    caps = mgr3.capabilities()
    if "capability.core.local-breakout" not in caps:
        return fail(name, "frozen core capability id missing")
    # events: PROVIDER_REGISTERED carries no label/mode.
    events = [e["event_type"] for e in mgr.snapshot()["events"]] if False else \
        [e.event_type for e in mgr._events]  # noqa: SLF001
    if events.count("PROVIDER_REGISTERED") != 1:
        return fail(name, "registration event missing")
    return ok(name, "isinstance-enforced registration, mode vocabulary, "
                    "duplicate labels, capability ladder with the frozen "
                    "capability.core.local-breakout id")


def case_06_gateway_evidence_fail_closed() -> Result:
    name = "case_06_gateway_evidence_fail_closed"
    mgr = DistributedCoreManager(session_reader=_READER)
    mgr.register_provider(
        ReferenceIPGatewayEngine(), label="local",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    # Unevidenced registration (None / non-evidence) fails closed.
    for evidence in (None, "evidence", 42):
        try:
            mgr.register_gateway(
                now=_NOW, label="local",
                descriptor=_LOCAL_DESCRIPTOR, evidence=evidence,
            )
            return fail(name, "unevidenced registration accepted: %r" % (evidence,))
        except DistCoreError as exc:
            if exc.reason != DistCoreReasonCode.GATEWAY_UNEVIDENCED:
                return fail(name, "unevidenced mistyped: %s" % exc.reason)
    # Evidence that does not bind to the claim (digest mismatch).
    wrong = GatewayEvidence(
        observer_node_id=_NODE_LOCAL_GW, reporter_node_id=_NODE_LOCAL_GW,
        source_class=EvidenceSourceClass.DIRECT_OBSERVATION,
        observed_at=_NOW, claim_digest="0" * 64,
    )
    try:
        mgr.register_gateway(
            now=_NOW, label="local",
            descriptor=_LOCAL_DESCRIPTOR, evidence=wrong,
        )
        return fail(name, "mismatched claim digest accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.GATEWAY_UNEVIDENCED:
            return fail(name, "digest mismatch mistyped: %s" % exc.reason)
    # A well-evidenced registration succeeds and PRESERVES the
    # provenance class (a remote-claim gateway is recorded as such --
    # never upgraded).
    r = mgr.register_gateway(
        now=_NOW, label="local",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    if not r.ok:
        return fail(name, "evidenced registration failed: %s" % r.detail)
    if r.value.evidence_source_class != EvidenceSourceClass.DIRECT_OBSERVATION:
        return fail(name, "evidence class not preserved")
    remote = DistributedCoreManager(session_reader=_READER)
    remote.register_provider(
        ReferenceUPFEngine(), label="remote",
        breakout_mode=BreakoutMode.REMOTE, now=_NOW,
    )
    r2 = remote.register_gateway(
        now=_NOW, label="remote",
        descriptor=_REMOTE_DESCRIPTOR, evidence=_REMOTE_EVIDENCE,
    )
    if not r2.ok:
        return fail(name, "remote-claim registration failed: %s" % r2.detail)
    if r2.value.evidence_source_class != EvidenceSourceClass.REMOTE_CLAIM:
        return fail(name, "remote-claim class not preserved")
    # Duplicate gateway identity (the provider screens it; the
    # mediated failure VALUE surfaces).
    duplicate = mgr.register_gateway(
        now=_NOW, label="local",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    if duplicate.ok or duplicate.reason != DistCoreReasonCode.BINDING_EXISTS:
        return fail(name, "duplicate gateway identity: %s" % duplicate.reason)
    return ok(name, "unevidenced/mismatched registrations fail closed "
                    "GATEWAY_UNEVIDENCED; provenance classes preserved, "
                    "never upgraded")


def case_07_policy_decision_verification() -> Result:
    name = "case_07_policy_decision_verification"
    mgr = DistributedCoreManager(session_reader=_READER)
    mgr.register_provider(
        ReferenceIPGatewayEngine(), label="local",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    # A non-decision object is rejected.
    for not_a_decision in (None, "allow", {"effect": "allow"}):
        try:
            mgr.apply_policy_decision(
                now=_NOW, session_id=_SESSION_ID,
                policy_decision=not_a_decision, mode=BreakoutMode.LOCAL,
            )
            return fail(name, "non-decision accepted: %r" % (not_a_decision,))
        except DistCoreError:
            pass
    # A TAMPERED decision (id does not bind to canonical bytes).
    genuine = _allow_decision()
    tampered = PolicyDecision(
        decision_id="0" * 64, effect="allow", code="allow",
        detail="w024", matched_rule_ids=genuine.matched_rule_ids,
        policy_set_id=genuine.policy_set_id,
        policy_set_version=genuine.policy_set_version,
        evaluation_instant=genuine.evaluation_instant,
    )
    try:
        mgr.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=tampered, mode=BreakoutMode.LOCAL,
        )
        return fail(name, "tampered decision accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.INVALID_INPUT:
            return fail(name, "tampered decision mistyped: %s" % exc.reason)
    # A DENIED decision never authorizes a breakout.
    try:
        mgr.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=_deny_decision(), mode=BreakoutMode.LOCAL,
        )
        return fail(name, "denied decision accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.DECISION_DENIED:
            return fail(name, "denied decision mistyped: %s" % exc.reason)
    # A FUTURE-DATED decision is stale.
    try:
        mgr.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=_allow_decision(evaluation_instant=_T1),
            mode=BreakoutMode.LOCAL,
        )
        return fail(name, "future-dated decision accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.DECISION_STALE:
            return fail(name, "stale decision mistyped: %s" % exc.reason)
    # A genuine decision applies and is SESSION-SCOPED.
    r = mgr.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=genuine, mode=BreakoutMode.LOCAL,
        locality_labels=(_LOCALITY,),
    )
    if not r.ok:
        return fail(name, "genuine decision rejected: %s" % r.detail)
    decision = r.value
    if decision.mode != BreakoutMode.LOCAL or decision.policy_effect != "allow":
        return fail(name, "decision record drifted")
    if decision.matched_rule_ids != genuine.matched_rule_ids:
        return fail(name, "matched rule ids not preserved")
    if decision.locality_labels != (_LOCALITY,):
        return fail(name, "locality labels not preserved")
    # Cross-session authorization is rejected.
    try:
        mgr.establish_breakout(
            now=_NOW, session_id=_SESSION_ID_2,
            decision_ref=decision.decision_ref,
            path_ref=_LOCAL_PATH.path_id,
        )
        return fail(name, "cross-session decision accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ACCESS_SESSION_COLLAPSE:
            return fail(name, "cross-session mistyped: %s" % exc.reason)
    # Deterministic re-application at the same instant is rejected.
    try:
        mgr.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=genuine, mode=BreakoutMode.LOCAL,
        )
        return fail(name, "identical re-application accepted")
    except DistCoreError:
        pass
    return ok(name, "REAL tamper-evident WORK-010 decisions verified "
                    "(tampered/denied/stale fail closed); session-scoped "
                    "application; cross-session authorization rejected")


def case_08_path_registration() -> Result:
    name = "case_08_path_registration"
    mgr = DistributedCoreManager(session_reader=_READER)
    mgr.register_provider(
        ReferenceIPGatewayEngine(), label="local",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    # Non-Path objects are rejected.
    for not_a_path in (None, "sha256:" + "0" * 64, {"hops": ()}):
        try:
            mgr.register_path(now=_NOW, path=not_a_path)
            return fail(name, "non-Path accepted: %r" % (not_a_path,))
        except DistCoreError:
            pass
    # An infeasible path is rejected fail-closed.
    hops = _LOCAL_PATH.hops
    nodes = _LOCAL_PATH.nodes
    infeasible = Path(
        path_id=derive_path_id(_NODE_UE, _NODE_LOCAL_GW, hops, nodes),
        source_node_id=_NODE_UE, destination_node_id=_NODE_LOCAL_GW,
        hops=hops, nodes=nodes, metrics=_LOCAL_PATH.metrics,
        feasible=False,
        rejection_code="hard-constraint-unsatisfied",
        rejection_detail="fixture: infeasible path",
    )
    try:
        mgr.register_path(now=_NOW, path=infeasible)
        return fail(name, "infeasible path accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.PATH_INFEASIBLE:
            return fail(name, "infeasible mistyped: %s" % exc.reason)
    # A REAL ordinary Path registers verbatim (identity = fingerprint).
    r = mgr.register_path(now=_NOW, path=_LOCAL_PATH)
    if not r.ok or r.value != _LOCAL_PATH.path_id:
        return fail(name, "ordinary Path registration failed")
    # Duplicate registration.
    try:
        mgr.register_path(now=_NOW, path=_LOCAL_PATH)
        return fail(name, "duplicate path accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.BINDING_EXISTS:
            return fail(name, "duplicate path mistyped")
    # The PATH_REGISTERED event carries the deterministic latency.
    events = [e for e in mgr._events if e.event_type == "PATH_REGISTERED"]  # noqa: SLF001
    if not events or events[0].detail != "latency_ms=%d" % _LOCAL_LATENCY_MS:
        return fail(name, "path event latency detail missing")
    # Tampered paths cannot exist (the Path constructor binds the id).
    try:
        Path(
            path_id="sha256:" + "0" * 64,
            source_node_id=_NODE_UE, destination_node_id=_NODE_LOCAL_GW,
            hops=hops, nodes=nodes, metrics=_LOCAL_PATH.metrics, feasible=True,
        )
        return fail(name, "tampered Path constructed")
    except Exception:
        pass
    return ok(name, "ordinary WORK-011 Paths consumed as DATA (feasible "
                    "only; fingerprint identity; deterministic latency "
                    "surface)")


def case_09_local_breakout_establishment() -> Result:
    name = "case_09_local_breakout_establishment"
    mgr, local_engine, remote_engine = _full_stack()
    # Unknown decision / unknown path fail closed.
    try:
        mgr.establish_breakout(
            now=_NOW, session_id=_SESSION_ID,
            decision_ref="distcore:decision:" + "0" * 32,
            path_ref=_LOCAL_PATH.path_id,
        )
        return fail(name, "unknown decision accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.DECISION_UNKNOWN:
            return fail(name, "unknown decision mistyped")
    decision_local = mgr.apply_policy_decision(
        now=_T2, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T2),
        mode=BreakoutMode.LOCAL,
    )
    try:
        mgr.establish_breakout(
            now=_T2, session_id=_SESSION_ID,
            decision_ref=decision_local.value.decision_ref,
            path_ref="sha256:" + "9" * 64,
        )
        return fail(name, "unknown path accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.PATH_UNKNOWN:
            return fail(name, "unknown path mistyped")
    # MODE MISMATCH: a LOCAL decision over the REMOTE gateway's path.
    try:
        mgr.establish_breakout(
            now=_T2, session_id=_SESSION_ID,
            decision_ref=decision_local.value.decision_ref,
            path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "mode-mismatched path accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.PATH_GATEWAY_MISMATCH:
            return fail(name, "mode mismatch mistyped: %s" % exc.reason)
    # A non-secureable session fails closed BEFORE the provider.
    insecure = DistributedCoreManager(
        session_reader=_TestSessionReader(_SESSION_ID, secureable=False)
    )
    insecure.register_provider(
        ReferenceIPGatewayEngine(), label="local",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    insecure.register_gateway(
        now=_NOW, label="local",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    insecure.register_path(now=_NOW, path=_LOCAL_PATH)
    d = insecure.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
    )
    try:
        insecure.establish_breakout(
            now=_NOW, session_id=_SESSION_ID,
            decision_ref=d.value.decision_ref, path_ref=_LOCAL_PATH.path_id,
        )
        return fail(name, "non-secureable session bound")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.SESSION_NOT_SECUREABLE:
            return fail(name, "non-secureable mistyped: %s" % exc.reason)
    # The happy path: the LOCAL binding records mode + role + decision.
    r = mgr.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=mgr._decisions and next(  # noqa: SLF001
            ref for ref in sorted(mgr._decisions)
            if mgr._decisions[ref].mode == BreakoutMode.LOCAL  # noqa: SLF001
        ),
        path_ref=_LOCAL_PATH.path_id,
    )
    if not r.ok:
        return fail(name, "local establishment failed: %s" % r.detail)
    binding = r.value
    if binding.gateway_ref != derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    ):
        return fail(name, "binding on the wrong gateway")
    record = mgr.snapshot()["breakouts"][0]
    if record["mode"] != "local" or record["role_class"] != "ip-gateway":
        return fail(name, "binding provenance drifted: %s" % record)
    if record["state"] != "active" or record["path_latency_ms"] != _LOCAL_LATENCY_MS:
        return fail(name, "binding state/latency drifted")
    return ok(name, "LOCAL establishment over the local gateway with "
                    "mode/role/decision provenance; unknown refs, mode "
                    "mismatch, and non-secureable sessions fail closed")


def case_10_remote_breakout_establishment() -> Result:
    name = "case_10_remote_breakout_establishment"
    mgr, local_engine, remote_engine = _full_stack()
    remote_ref = next(
        ref for ref in sorted(mgr._decisions)  # noqa: SLF001
        if mgr._decisions[ref].mode == BreakoutMode.REMOTE  # noqa: SLF001
    )
    r = mgr.establish_breakout(
        now=_T1, session_id=_SESSION_ID,
        decision_ref=remote_ref, path_ref=_REMOTE_PATH.path_id,
    )
    if not r.ok:
        return fail(name, "remote establishment failed: %s" % r.detail)
    record = mgr.snapshot()["breakouts"][0]
    if record["mode"] != "remote" or record["role_class"] != "upf":
        return fail(name, "remote provenance drifted: %s" % record)
    if record["path_latency_ms"] != _REMOTE_LATENCY_MS:
        return fail(name, "remote latency drifted")
    # AMBIGUITY: two same-mode gateways on the remote node fail closed.
    mgr2, _, _ = _full_stack()
    extra = GatewayDescriptor(
        name="second-upf", gateway_id="gw-remote-2",
        node_id=_NODE_REMOTE_GW, role_class=GatewayRoleClass.UPF,
        capacity_bps=1000,
    )
    extra_evidence = GatewayEvidence(
        observer_node_id=_NODE_REMOTE_GW, reporter_node_id=_NODE_REMOTE_GW,
        source_class=EvidenceSourceClass.DIRECT_OBSERVATION,
        observed_at=_NOW,
        claim_digest=derive_gateway_claim_digest(extra),
    )
    mgr2.register_gateway(
        now=_NOW, label="remote", descriptor=extra, evidence=extra_evidence,
    )
    remote_ref2 = next(
        ref for ref in sorted(mgr2._decisions)  # noqa: SLF001
        if mgr2._decisions[ref].mode == BreakoutMode.REMOTE  # noqa: SLF001
    )
    try:
        mgr2.establish_breakout(
            now=_T1, session_id=_SESSION_ID,
            decision_ref=remote_ref2, path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "ambiguous gateway accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.GATEWAY_AMBIGUOUS:
            return fail(name, "ambiguity mistyped: %s" % exc.reason)
    return ok(name, "REMOTE (UPF-shaped) establishment with provenance; "
                    "ambiguous breakout points fail closed")


def case_11_upf_ip_gateway_coexistence() -> Result:
    name = "case_11_upf_ip_gateway_coexistence"
    mgr, local_engine, remote_engine = _full_stack()
    b_local = _establish_local(mgr)
    b_remote = _establish_remote(mgr)
    if not (b_local.ok and b_remote.ok):
        return fail(name, "coexisting establishments failed")
    # A 5G UPF function and a generic IP gateway function coexist
    # behind adapters SIMULTANEOUSLY (one session, two modes).
    snapshot = mgr.snapshot()
    if snapshot["breakout_count"] != 2:
        return fail(name, "active breakout count: %d" % snapshot["breakout_count"])
    modes = {b["mode"] for b in snapshot["breakouts"]}
    roles = {b["role_class"] for b in snapshot["breakouts"]}
    if modes != {"local", "remote"}:
        return fail(name, "modes: %s" % modes)
    if roles != {"ip-gateway", "upf"}:
        return fail(name, "roles: %s" % roles)
    # Different sessions may hold their own breakouts too.
    mgr2, _, _ = _full_stack()
    s_local = _establish_local(mgr2, _SESSION_ID)
    s_remote = _establish_remote(mgr2, _SESSION_ID_2)
    if not (s_local.ok and s_remote.ok):
        return fail(name, "cross-session coexistence failed")
    if mgr2.breakout_count != 2:
        return fail(name, "cross-session breakout count drifted")
    return ok(name, "5G UPF and generic IP gateway functions coexist "
                    "behind adapters (same session, both modes; and "
                    "across sessions)")


def case_12_local_traffic_stays_local() -> Result:
    name = "case_12_local_traffic_stays_local"
    mgr, local_engine, remote_engine = _full_stack()
    b_local = _establish_local(mgr)
    b_remote = _establish_remote(mgr)
    if not (b_local.ok and b_remote.ok):
        return fail(name, "establishments failed")
    # Egress through the LOCAL binding.
    e1 = mgr.egress(now=_NOW, breakout_ref=b_local.value.breakout_ref, payload=_PAYLOAD)
    if not e1.ok:
        return fail(name, "local egress failed: %s" % e1.detail)
    record = e1.value
    if record.locality != "local" or record.mode != "local":
        return fail(name, "local egress locality drifted: %s" % record.locality)
    if record.path_latency_ms != _LOCAL_LATENCY_MS:
        return fail(name, "local egress latency drifted")
    # THE isolation proof: the payload appears in the LOCAL gateway's
    # delivery log and NOWHERE in the remote (UPF) provider.
    local_gw_ref = derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    )
    remote_gw_ref = derive_gateway_ref(
        _REMOTE_DESCRIPTOR.name, _REMOTE_DESCRIPTOR.gateway_id,
        _REMOTE_DESCRIPTOR.node_id, _REMOTE_DESCRIPTOR.role_class,
    )
    if local_engine.delivered_payloads(local_gw_ref) != (_PAYLOAD,):
        return fail(name, "local delivery log missing the payload")
    if remote_engine.delivered_payloads(remote_gw_ref) != ():
        return fail(name, "LOCAL traffic leaked to the remote provider")
    # Egress through the REMOTE binding never touches the local one.
    e2 = mgr.egress(now=_T1, breakout_ref=b_remote.value.breakout_ref, payload=_PAYLOAD_2)
    if not e2.ok or e2.value.locality != "remote":
        return fail(name, "remote egress failed")
    if local_engine.delivered_payloads(local_gw_ref) != (_PAYLOAD,):
        return fail(name, "REMOTE traffic leaked to the local provider")
    if remote_engine.delivered_payloads(remote_gw_ref) != (_PAYLOAD_2,):
        return fail(name, "remote delivery log missing the payload")
    return ok(name, "local traffic stays local (the remote provider's "
                    "delivery log stays empty) and remote traffic never "
                    "touches the local gateway")


def case_13_egress_data_path_fail_closed() -> Result:
    name = "case_13_egress_data_path_fail_closed"
    mgr, _, _ = _full_stack()
    b = _establish_local(mgr)
    if not b.ok:
        return fail(name, "establishment failed")
    ref = b.value.breakout_ref
    # Unknown breakout.
    try:
        mgr.egress(now=_NOW, breakout_ref="distcore:breakout:" + "0" * 32, payload=b"x")
        return fail(name, "unknown breakout egress accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.BREAKOUT_UNKNOWN:
            return fail(name, "unknown breakout mistyped")
    # Payload bounds (engine-side fail-closed typed failures).
    for bad_payload in (b"", b"x" * (MAX_EGRESS_BYTES + 1), "text"):
        result = mgr.egress(now=_NOW, breakout_ref=ref, payload=bad_payload)
        if result.ok:
            return fail(name, "bad payload accepted: %r" % (bad_payload[:10],))
    # Size accounting on the happy path.
    e = mgr.egress(now=_NOW, breakout_ref=ref, payload=b"12345")
    if not e.ok or e.value.payload_bytes != 5:
        return fail(name, "payload accounting broken")
    # Release then egress -> BREAKOUT_STATE (never retroactively
    # rebound).
    rel = mgr.release_breakout(now=_NOW, breakout_ref=ref)
    if not rel.ok:
        return fail(name, "release failed: %s" % rel.detail)
    try:
        mgr.egress(now=_NOW, breakout_ref=ref, payload=b"x")
        return fail(name, "released breakout carried traffic")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.BREAKOUT_STATE:
            return fail(name, "released breakout mistyped: %s" % exc.reason)
    # Data-path operations append NO events.
    event_types = [e.event_type for e in mgr._events]  # noqa: SLF001
    for lifecycle in ("BREAKOUT_ESTABLISHED", "BREAKOUT_RELEASED"):
        if lifecycle not in event_types:
            return fail(name, "lifecycle event missing")
    if any(e["detail"].startswith("egress") for e in mgr.snapshot()["events"]):
        return fail(name, "data-path event leaked into canonical state")
    return ok(name, "payload bounds, unknown/released breakouts fail "
                    "closed; honest size accounting; data-path ops append "
                    "no events")


def case_14_latency_locality_determinism() -> Result:
    name = "case_14_latency_locality_determinism"

    def journey():
        mgr, _, _ = _full_stack()
        b_local = _establish_local(mgr)
        records = []
        records.append(
            mgr.egress(now=_NOW, breakout_ref=b_local.value.breakout_ref, payload=_PAYLOAD).value.to_dict()
        )
        # Failover flips the deterministic locality/latency pair.
        remote_decision = mgr.apply_policy_decision(
            now=_T4, session_id=_SESSION_ID,
            policy_decision=_allow_decision(evaluation_instant=_T4),
            mode=BreakoutMode.REMOTE,
        )
        f = mgr.failover_binding(
            now=_T4, breakout_ref=b_local.value.breakout_ref,
            target_decision_ref=remote_decision.value.decision_ref,
            target_path_ref=_REMOTE_PATH.path_id,
        )
        if not f.ok:
            raise AssertionError("failover failed: %s" % f.detail)
        records.append(
            mgr.egress(now=_T4, breakout_ref=f.value.breakout_ref, payload=_PAYLOAD).value.to_dict()
        )
        return records

    first = journey()
    second = journey()
    if first != second:
        return fail(name, "latency/locality journey diverged across runs")
    local_record, remote_record = first
    if local_record["locality"] != "local" or local_record["path_latency_ms"] != _LOCAL_LATENCY_MS:
        return fail(name, "local record drifted: %s" % local_record)
    if remote_record["locality"] != "remote" or remote_record["path_latency_ms"] != _REMOTE_LATENCY_MS:
        return fail(name, "remote record drifted: %s" % remote_record)
    if local_record["path_latency_ms"] >= remote_record["path_latency_ms"]:
        return fail(name, "local-first fixture is not lower-latency")
    if local_record["session_id"] != remote_record["session_id"]:
        return fail(name, "session identity drifted across the failover")
    return ok(name, "deterministic latency/locality fixtures: local "
                    "egress is strictly lower-latency, failover flips the "
                    "pair deterministically, session identity stable")


def case_15_policy_determines_breakout() -> Result:
    name = "case_15_policy_determines_breakout"
    mgr, _, _ = _full_stack()
    # The policy-determined mode selects which breakout is
    # establishable: a LOCAL decision cannot establish over the
    # remote gateway's path, and vice versa (already proven); here
    # the FULL determination chain is verified: the decision record
    # carries the policy provenance and the binding records it.
    local_decision = mgr.apply_policy_decision(
        now=_T2, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T2),
        mode=BreakoutMode.LOCAL, locality_labels=(_LOCALITY,),
    )
    if not local_decision.ok:
        return fail(name, "local decision application failed")
    b = mgr.establish_breakout(
        now=_T2, session_id=_SESSION_ID,
        decision_ref=local_decision.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if not b.ok:
        return fail(name, "local establishment failed")
    record = next(
        rec for rec in mgr.snapshot()["breakouts"]
        if rec["binding_id"] == b.value.binding_id
    )
    if record["decision_ref"] != local_decision.value.decision_ref:
        return fail(name, "binding does not carry the decision provenance")
    decision_dict = next(
        dec for dec in mgr.snapshot()["decisions"]
        if dec["decision_ref"] == local_decision.value.decision_ref
    )
    if decision_dict["mode"] != "local" or decision_dict["policy_effect"] != "allow":
        return fail(name, "decision record drifted: %s" % decision_dict)
    if decision_dict["locality_labels"] != [_LOCALITY]:
        return fail(name, "locality labels not recorded")
    # A DENIED policy cannot even construct a decision: nothing is
    # establishable (the distributed core never overrides policy).
    mgr2, _, _ = _full_stack()
    try:
        mgr2.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=_deny_decision(), mode=BreakoutMode.LOCAL,
        )
        return fail(name, "deny decision applied")
    except DistCoreError:
        pass
    if mgr2.breakout_count != 0:
        return fail(name, "breakout without an allow decision")
    # The policy decision id is preserved on the record (auditability).
    if decision_dict["policy_decision_id"] != _allow_decision(evaluation_instant=_T2).decision_id:
        return fail(name, "policy decision id not preserved")
    return ok(name, "the policy determination (mode + rule ids + "
                    "locality labels + decision id) is the recorded and "
                    "auditable source of the breakout; deny never "
                    "authorizes")


def case_16_session_identity_across_failover() -> Result:
    name = "case_16_session_identity_across_failover"
    mgr, local_engine, _ = _full_stack()
    b_local = _establish_local(mgr)
    old_binding = b_local.value
    remote_decision = mgr.apply_policy_decision(
        now=_T4, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T4),
        mode=BreakoutMode.REMOTE,
    )
    f = mgr.failover_binding(
        now=_T1, breakout_ref=old_binding.breakout_ref,
        target_decision_ref=remote_decision.value.decision_ref,
        target_path_ref=_REMOTE_PATH.path_id,
    )
    if not f.ok:
        return fail(name, "failover failed: %s" % f.detail)
    new_binding = f.value
    # THE identity invariant: same session, new breakout identity.
    if new_binding.session_id != old_binding.session_id:
        return fail(name, "session identity changed across failover")
    if new_binding.breakout_ref == old_binding.breakout_ref:
        return fail(name, "breakout identity did not change")
    if new_binding.binding_id == old_binding.binding_id:
        return fail(name, "binding key did not change")
    # The chain: old SUPERSEDED -> new; new supersedes old.
    snapshot = mgr.snapshot()
    records = {b["binding_id"]: b for b in snapshot["breakouts"]}
    old_record = records[old_binding.binding_id]
    new_record = records[new_binding.binding_id]
    if old_record["state"] != "superseded":
        return fail(name, "old binding not superseded: %s" % old_record["state"])
    if old_record["superseded_by"] != new_binding.binding_id:
        return fail(name, "superseded_by link broken")
    if new_record["supersedes"] != old_binding.binding_id:
        return fail(name, "supersedes link broken")
    if new_record["state"] != "active":
        return fail(name, "new binding not active")
    # The transition event carries old + new refs.
    events = [e for e in snapshot["events"] if e["event_type"] == "BREAKOUT_SUPERSEDED"]
    if not events or events[0]["breakout_ref"] != old_binding.breakout_ref:
        return fail(name, "transition event missing the old ref")
    if "new_breakout=%s" % new_binding.breakout_ref not in events[0]["detail"]:
        return fail(name, "transition event missing the new ref")
    # The old breakout NEVER carries traffic again.
    try:
        mgr.egress(now=_T1, breakout_ref=old_binding.breakout_ref, payload=b"x")
        return fail(name, "superseded breakout carried traffic")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.BREAKOUT_STATE:
            return fail(name, "superseded egress mistyped: %s" % exc.reason)
    # Only an ACTIVE breakout can fail over again.
    try:
        mgr.failover_binding(
            now=_T2, breakout_ref=old_binding.breakout_ref,
            target_decision_ref=remote_decision.value.decision_ref,
            target_path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "superseded breakout failed over")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.BREAKOUT_STATE:
            return fail(name, "superseded failover mistyped")
    # Egress through the new binding works and preserves the session.
    e = mgr.egress(now=_T1, breakout_ref=new_binding.breakout_ref, payload=b"x")
    if not e.ok or e.value.session_id != _SESSION_ID:
        return fail(name, "post-failover egress lost the session identity")
    return ok(name, "session identity preserved across the gateway change; "
                    "supersedes chain + transition event recorded; "
                    "superseded breakouts never carry traffic")


def case_17_remote_gateway_failover_partition() -> Result:
    name = "case_17_remote_gateway_failover_partition"
    mgr, local_engine, _ = _full_stack()
    b_local = _establish_local(mgr)
    ref = b_local.value.breakout_ref
    local_gw_ref = derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    )
    # THE partition: the local gateway goes down.
    local_engine.set_gateway_state(local_gw_ref, available=False)
    # Egress fails closed with the binding PRESERVED.
    e = mgr.egress(now=_NOW, breakout_ref=ref, payload=b"x")
    if e.ok or e.reason != DistCoreReasonCode.GATEWAY_UNAVAILABLE:
        return fail(name, "partitioned egress: %s" % e.reason)
    if mgr.breakout_count != 1:
        return fail(name, "partition dropped the binding")
    # Failover to the remote gateway WORKS while the local one is
    # partitioned (the old provider's release does not block).
    remote_decision = mgr.apply_policy_decision(
        now=_T4, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T4),
        mode=BreakoutMode.REMOTE,
    )
    f = mgr.failover_binding(
        now=_T1, breakout_ref=ref,
        target_decision_ref=remote_decision.value.decision_ref,
        target_path_ref=_REMOTE_PATH.path_id,
    )
    if not f.ok:
        return fail(name, "partition-time failover failed: %s" % f.detail)
    # Egress succeeds via the remote gateway with flipped locality.
    e2 = mgr.egress(now=_T1, breakout_ref=f.value.breakout_ref, payload=_PAYLOAD_2)
    if not e2.ok or e2.value.locality != "remote":
        return fail(name, "post-failover egress failed")
    if e2.value.path_latency_ms != _REMOTE_LATENCY_MS:
        return fail(name, "post-failover latency drifted")
    if e2.value.session_id != _SESSION_ID:
        return fail(name, "session identity lost")
    return ok(name, "remote gateway failover under partition: egress "
                    "fails closed with the binding preserved, the "
                    "explicit transition succeeds while the local "
                    "gateway is down, locality/latency flip "
                    "deterministically, session identity preserved")


def case_18_graceful_degradation_alternate_paths() -> Result:
    name = "case_18_graceful_degradation_alternate_paths"
    mgr, local_engine, _ = _full_stack()
    local_gw_ref = derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    )
    # Partition the local gateway BEFORE any local establishment.
    local_engine.set_gateway_state(local_gw_ref, available=False)
    # A LOCAL establishment fails closed...
    d_local = mgr.apply_policy_decision(
        now=_T4, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T4),
        mode=BreakoutMode.LOCAL,
        locality_labels=(_LOCALITY,),
    )
    r = mgr.establish_breakout(
        now=_T4, session_id=_SESSION_ID,
        decision_ref=d_local.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if r.ok or r.reason != DistCoreReasonCode.GATEWAY_UNAVAILABLE:
        return fail(name, "partitioned local establish: %s" % r.reason)
    # ...while the ALTERNATE REMOTE path stays establishable (the
    # degradation is graceful; remote paths are preserved).
    b_remote = _establish_remote(mgr)
    if not b_remote.ok:
        return fail(name, "alternate remote path not establishable")
    e = mgr.egress(now=_T1, breakout_ref=b_remote.value.breakout_ref, payload=b"x")
    if not e.ok:
        return fail(name, "remote egress under local degradation failed")
    # The engine health DEGRADES (an unavailable local gateway
    # degrades service rather than silently disappearing).  The
    # manager-level degradation surface is the honest observation
    # (below); the sandbox computed health accounts MEDIATED
    # failures (case 23 covers that accounting).
    if local_engine.health() != "DEGRADED":
        return fail(name, "partitioned local gateway not DEGRADED")
    # The observation honestly reports the unavailable gateway.
    obs = mgr.observe(now=_NOW, label="local")
    if not obs.ok or obs.value.unavailable_gateways != 1 or obs.value.available_gateways != 0:
        return fail(name, "observation not honest: %s" % obs.value.to_dict())
    # Capacity grounded in AVAILABLE gateways only: the partitioned
    # provider admits NOTHING (zero-capacity contribution).
    # (The default provider here is the LOCAL one; allocate fails.)
    alloc = mgr.allocate(
        now=_NOW, kind="bandwidth", quantity_base=1, purpose="p"
    )
    if alloc.ok:
        return fail(name, "partitioned provider admitted capacity")
    return ok(name, "local breakout degrades gracefully (fail closed) "
                    "while alternate remote paths remain establishable; "
                    "health and observation honest; capacity fails "
                    "closed")


def case_19_partition_recovery() -> Result:
    name = "case_19_partition_recovery"
    mgr, local_engine, _ = _full_stack()
    b_local = _establish_local(mgr)
    ref = b_local.value.breakout_ref
    local_gw_ref = derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    )
    # Partition, fail over to remote.
    local_engine.set_gateway_state(local_gw_ref, available=False)
    remote_decision = mgr.apply_policy_decision(
        now=_T4, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T4),
        mode=BreakoutMode.REMOTE,
    )
    f = mgr.failover_binding(
        now=_T1, breakout_ref=ref,
        target_decision_ref=remote_decision.value.decision_ref,
        target_path_ref=_REMOTE_PATH.path_id,
    )
    if not f.ok:
        return fail(name, "failover failed")
    # RECOVER the local gateway.
    local_engine.set_gateway_state(local_gw_ref, available=True)
    if local_engine.health() != "HEALTHY":
        return fail(name, "recovered local gateway not HEALTHY")
    # Fail BACK to the local breakout (the recovery transition):
    # same explicit semantics, chain grows, session preserved.
    recovery_decision = mgr.apply_policy_decision(
        now=_T5, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T5),
        mode=BreakoutMode.LOCAL, locality_labels=(_LOCALITY,),
    )
    back = mgr.failover_binding(
        now=_T2, breakout_ref=f.value.breakout_ref,
        target_decision_ref=recovery_decision.value.decision_ref,
        target_path_ref=_LOCAL_PATH.path_id,
    )
    if not back.ok:
        return fail(name, "recovery failover failed: %s" % back.detail)
    e = mgr.egress(now=_T2, breakout_ref=back.value.breakout_ref, payload=_PAYLOAD)
    if not e.ok or e.value.locality != "local":
        return fail(name, "recovered egress not local")
    if e.value.path_latency_ms != _LOCAL_LATENCY_MS:
        return fail(name, "recovered latency drifted")
    if e.value.session_id != _SESSION_ID:
        return fail(name, "session identity lost on recovery")
    # The three-link chain: local -> remote -> local.
    snapshot = mgr.snapshot()
    if len(snapshot["breakouts"]) != 3:
        return fail(name, "chain length: %d" % len(snapshot["breakouts"]))
    states = sorted(b["state"] for b in snapshot["breakouts"])
    if states != ["active", "superseded", "superseded"]:
        return fail(name, "chain states: %s" % states)
    # Strict toggling on the reference control.
    try:
        local_engine.set_gateway_state(local_gw_ref, available=True)
        return fail(name, "same-state partition toggle accepted")
    except DistCoreError:
        pass
    return ok(name, "partition recovery: fail back to the local breakout "
                    "with the same explicit transition semantics; the "
                    "chain grows local->remote->local with the session "
                    "identity preserved throughout")


def case_20_failover_validation_fail_closed() -> Result:
    name = "case_20_failover_validation_fail_closed"
    mgr, _, _ = _full_stack()
    b_local = _establish_local(mgr)
    ref = b_local.value.breakout_ref
    remote_decision = mgr.apply_policy_decision(
        now=_T4, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T4),
        mode=BreakoutMode.REMOTE,
    )
    # Cross-session target decision.
    other = mgr.apply_policy_decision(
        now=_T1, session_id=_SESSION_ID_2,
        policy_decision=_allow_decision(evaluation_instant=_T1),
        mode=BreakoutMode.REMOTE,
    )
    # Mode-mismatched target (LOCAL decision + remote path).
    local_only = mgr.apply_policy_decision(
        now=_T5, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T5),
        mode=BreakoutMode.LOCAL,
    )
    if not (remote_decision.ok and other.ok and local_only.ok):
        return fail(name, "decision applications failed")
    # All state that WILL exist is now applied: the frozen
    # before-bytes for the side-effect-free assertions.
    before_bytes = mgr.to_canonical_bytes()
    # Unknown decision.
    try:
        mgr.failover_binding(
            now=_T1, breakout_ref=ref,
            target_decision_ref="distcore:decision:" + "0" * 32,
            target_path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "unknown target decision accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.DECISION_UNKNOWN:
            return fail(name, "unknown decision mistyped")
    # Unknown path.
    try:
        mgr.failover_binding(
            now=_T1, breakout_ref=ref,
            target_decision_ref=remote_decision.value.decision_ref,
            target_path_ref="sha256:" + "9" * 64,
        )
        return fail(name, "unknown target path accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.PATH_UNKNOWN:
            return fail(name, "unknown path mistyped")
    try:
        mgr.failover_binding(
            now=_T1, breakout_ref=ref,
            target_decision_ref=other.value.decision_ref,
            target_path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "cross-session failover accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ACCESS_SESSION_COLLAPSE:
            return fail(name, "cross-session failover mistyped")
    try:
        mgr.failover_binding(
            now=_T2, breakout_ref=ref,
            target_decision_ref=local_only.value.decision_ref,
            target_path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "mode-mismatched failover accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.PATH_GATEWAY_MISMATCH:
            return fail(name, "mode-mismatched failover mistyped")
    # Non-secureable session blocks failover BEFORE the provider.
    insecure = _TestSessionReader(_SESSION_ID, secureable=False)
    mgr._session_reader = insecure  # noqa: SLF001 (test probe)
    try:
        mgr.failover_binding(
            now=_T1, breakout_ref=ref,
            target_decision_ref=remote_decision.value.decision_ref,
            target_path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "non-secureable failover accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.SESSION_NOT_SECUREABLE:
            return fail(name, "non-secureable failover mistyped")
    mgr._session_reader = _READER  # noqa: SLF001 (restore)
    # EVERY failed validation left the canonical state byte-identical.
    if mgr.to_canonical_bytes() != before_bytes:
        return fail(name, "failed failovers mutated canonical bytes")
    # A failed TARGET (provider-side) also leaves the old binding
    # intact: partition the remote gateway first.
    mgr2, _, remote_engine = _full_stack()
    b2 = _establish_local(mgr2)
    remote_gw_ref = derive_gateway_ref(
        _REMOTE_DESCRIPTOR.name, _REMOTE_DESCRIPTOR.gateway_id,
        _REMOTE_DESCRIPTOR.node_id, _REMOTE_DESCRIPTOR.role_class,
    )
    remote_engine.set_anchor_state(remote_gw_ref, up=False)
    rd = mgr2.apply_policy_decision(
        now=_T4, session_id=_SESSION_ID,
        policy_decision=_allow_decision(evaluation_instant=_T4),
        mode=BreakoutMode.REMOTE,
    )
    before2 = mgr2.to_canonical_bytes()
    failed = mgr2.failover_binding(
        now=_T1, breakout_ref=b2.value.breakout_ref,
        target_decision_ref=rd.value.decision_ref,
        target_path_ref=_REMOTE_PATH.path_id,
    )
    if failed.ok or failed.reason != DistCoreReasonCode.GATEWAY_UNAVAILABLE:
        return fail(name, "partitioned target failover: %s" % failed.reason)
    if mgr2.to_canonical_bytes() != before2:
        return fail(name, "failed target failover mutated state")
    if mgr2.breakout_count != 1:
        return fail(name, "failed target failover dropped the old binding")
    return ok(name, "failover validation is side-effect free (unknown "
                    "refs, cross-session, mode mismatch, non-secureable "
                    "session, partitioned target) -- the old binding is "
                    "byte-identically intact after every failure")


def case_21_no_retroactive_rebinding_provider_swap() -> Result:
    name = "case_21_no_retroactive_rebinding_provider_swap"
    mgr, local_engine, _ = _full_stack()
    b = _establish_local(mgr)
    ref = b.value.breakout_ref
    local_gw_ref = derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    )
    e1 = mgr.egress(now=_NOW, breakout_ref=ref, payload=_PAYLOAD)
    if not e1.ok:
        return fail(name, "pre-swap egress failed")
    # Swap in a SECOND local provider as the default.
    replacement = ReferenceIPGatewayEngine()
    r = mgr.register_provider(
        replacement, label="local-2",
        breakout_mode=BreakoutMode.LOCAL, make_default=True, now=_T1,
    )
    if not r.ok:
        return fail(name, "provider swap failed: %s" % r.detail)
    # The LIVE binding keeps its OWNING provider (B2): egress still
    # delivers through the ORIGINAL engine, never the replacement.
    e2 = mgr.egress(now=_T1, breakout_ref=ref, payload=_PAYLOAD_2)
    if not e2.ok:
        return fail(name, "post-swap egress failed")
    if local_engine.delivered_payloads(local_gw_ref) != (_PAYLOAD, _PAYLOAD_2):
        return fail(name, "live binding left its owning provider")
    # New gateways register on the NEW default provider (the swap
    # governs new admissions only) -- and NO traffic ever flows
    # through the replacement (its delivery log stays empty).
    extra = GatewayDescriptor(
        name="second-gw", gateway_id="gw-local-2",
        node_id=_NODE_TRANSIT, role_class=GatewayRoleClass.IP_GATEWAY,
        capacity_bps=1000,
    )
    extra_evidence = GatewayEvidence(
        observer_node_id=_NODE_TRANSIT, reporter_node_id=_NODE_TRANSIT,
        source_class=EvidenceSourceClass.DIRECT_OBSERVATION,
        observed_at=_NOW, claim_digest=derive_gateway_claim_digest(extra),
    )
    g = mgr.register_gateway(
        now=_T1, label="local-2", descriptor=extra, evidence=extra_evidence,
    )
    if not g.ok:
        return fail(name, "new gateway registration on swap failed")
    if replacement.delivered_payloads(g.value.gateway_ref) != ():
        return fail(name, "traffic leaked to the replacement provider")
    # The canonical state is unaffected by the swap (labels are
    # diagnostic; ACCESS-STATE-OUT).
    diag = mgr.diagnostic_state()
    labels = [reg["label"] for reg in diag["registrations"]]
    if labels != ["local", "remote", "local-2"]:
        return fail(name, "diagnostic registrations drifted: %s" % labels)
    return ok(name, "provider swap preserves live bindings on their "
                    "owning provider (B2); no retroactive rebinding; the "
                    "swap governs new admissions only")


def case_22_allocation_capacity_fail_closed() -> Result:
    name = "case_22_allocation_capacity_fail_closed"
    mgr, _, _ = _full_stack()
    # The default provider is the LOCAL one (registered first): its
    # allocatable pool is the local gateway's capacity.
    r = mgr.allocate(
        now=_NOW, kind="bandwidth",
        quantity_base=_LOCAL_CAP_BPS, purpose="full",
    )
    if not r.ok:
        return fail(name, "full-capacity allocation failed: %s" % r.detail)
    if not r.value.allocation_ref.startswith("distcore:alloc:"):
        return fail(name, "allocation ref drifted")
    # Over the pool -> CAPACITY_EXHAUSTED.
    over = mgr.allocate(
        now=_NOW, kind="bandwidth", quantity_base=1, purpose="over",
    )
    if over.ok or over.reason != DistCoreReasonCode.CAPACITY_EXHAUSTED:
        return fail(name, "over-capacity: %s" % over.reason)
    # Wrong kind.
    bad_kind = mgr.allocate(now=_NOW, kind="storage", quantity_base=1, purpose="p")
    if bad_kind.ok or bad_kind.reason != DistCoreReasonCode.INVALID_INPUT:
        return fail(name, "wrong kind: %s" % bad_kind.reason)
    # Release frees the pool.
    rel = mgr.release(now=_NOW, allocation_ref=r.value.allocation_ref)
    if not rel.ok:
        return fail(name, "release failed: %s" % rel.detail)
    again = mgr.allocate(
        now=_NOW, kind="bandwidth",
        quantity_base=_LOCAL_CAP_BPS, purpose="again",
    )
    if not again.ok:
        return fail(name, "post-release allocation failed")
    # Unknown allocation.
    try:
        mgr.release(now=_NOW, allocation_ref="distcore:alloc:" + "0" * 32)
        return fail(name, "unknown allocation released")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ALLOCATION_UNKNOWN:
            return fail(name, "unknown allocation mistyped")
    # ZERO-CAPACITY gateways contribute NOTHING (the W022 lesson).
    mgr2 = DistributedCoreManager(session_reader=_READER)
    mgr2.register_provider(
        ReferenceIPGatewayEngine(), label="local",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    zero = GatewayDescriptor(
        name="zero-gw", gateway_id="gw-zero",
        node_id=_NODE_LOCAL_GW, role_class=GatewayRoleClass.IP_GATEWAY,
        capacity_bps=0,
    )
    zero_evidence = GatewayEvidence(
        observer_node_id=_NODE_LOCAL_GW, reporter_node_id=_NODE_LOCAL_GW,
        source_class=EvidenceSourceClass.DIRECT_OBSERVATION,
        observed_at=_NOW, claim_digest=derive_gateway_claim_digest(zero),
    )
    mgr2.register_gateway(
        now=_NOW, label="local", descriptor=zero, evidence=zero_evidence,
    )
    r_zero = mgr2.allocate(
        now=_NOW, kind="bandwidth", quantity_base=1, purpose="p",
    )
    if r_zero.ok or r_zero.reason != DistCoreReasonCode.CAPACITY_EXHAUSTED:
        return fail(name, "zero-capacity gateway admitted capacity: %s" % r_zero.reason)
    return ok(name, "capacity grounded in AVAILABLE gateway capacity; "
                    "zero-capacity gateways contribute nothing (W022 "
                    "fail-closed lesson); release frees the pool")


def case_23_base_exception_isolation() -> Result:
    name = "case_23_base_exception_isolation"

    class _CrashingProvider(BreakoutProviderContract):
        label = "crashing"
        def __init__(self):
            self.bursts = 0
        def open(self, context):
            return None
        def register_gateway(self, context, *, descriptor, evidence):
            return GatewayCandidate(
                gateway_ref=derive_gateway_ref(
                    descriptor.name, descriptor.gateway_id,
                    descriptor.node_id, descriptor.role_class,
                ),
                name=descriptor.name, gateway_id=descriptor.gateway_id,
                node_id=descriptor.node_id,
                role_class=descriptor.role_class,
                locality_label=descriptor.locality_label,
                capacity_bps=descriptor.capacity_bps,
                state=GatewayState.AVAILABLE,
                evidence_source_class=evidence.source_class,
            )
        def close_gateway(self, context, *, gateway_ref):
            return None
        def allocate(self, context, *, kind, quantity_base, purpose):
            return BreakoutAllocation(
                allocation_ref=derive_allocation_ref(kind, quantity_base, purpose, 1),
                kind=kind, quantity_base=quantity_base, purpose=purpose,
                state=AllocationState.RESERVED,
            )
        def release(self, context, *, allocation_ref):
            return None
        def establish_breakout(self, context, *, session_id, gateway_ref, path_ref, requirements=None):
            self.bursts += 1
            if self.bursts == 1:
                raise SystemExit("vendor gateway daemon abort")  # BaseException
            return BreakoutBinding(
                session_id=session_id,
                breakout_ref=derive_breakout_ref(session_id, gateway_ref, path_ref, 1),
                binding_id=derive_binding_id(
                    session_id,
                    derive_breakout_ref(session_id, gateway_ref, path_ref, 1),
                ),
                gateway_ref=gateway_ref, path_ref=path_ref,
                state=BreakoutState.ACTIVE,
                established_instant=context.now(),
            )
        def release_breakout(self, context, *, breakout_ref):
            return None
        def egress(self, context, *, breakout_ref, payload):
            raise KeyboardInterrupt("interrupt")
        def observe(self, context):
            return DistCoreObservation()
        def health(self):
            return "HEALTHY"
        def close(self, context):
            return None

    mgr = DistributedCoreManager(session_reader=_READER)
    crashing = _CrashingProvider()
    mgr.register_provider(
        crashing, label="crash", breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    mgr.register_gateway(
        now=_NOW, label="crash",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    mgr.register_path(now=_NOW, path=_LOCAL_PATH)
    decision = mgr.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
    )
    before = mgr.to_canonical_bytes()
    # A BaseException from the implementation is converted into a
    # typed failure VALUE (never propagates; nothing committed).
    first = mgr.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=decision.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if first.ok or first.reason != DistCoreReasonCode.DISTCORE_FAILURE:
        return fail(name, "BaseException isolation: %s" % first.reason)
    if first.failure.exception_class_name != "SystemExit":
        return fail(name, "exception class name not captured")
    if first.failure.to_dict().get("reason_code") != "distcore-failure":
        return fail(name, "failure dict drifted")
    if mgr.to_canonical_bytes() != before:
        return fail(name, "crashed establish mutated canonical bytes")
    # The failure VALUE is secret-free: no message text anywhere.
    if "vendor gateway daemon" in repr(first) or "interrupt" in repr(first):
        return fail(name, "exception message text leaked")
    # A second (successful) establish commits normally.
    second = mgr.establish_breakout(
        now=_T1, session_id=_SESSION_ID,
        decision_ref=decision.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if not second.ok:
        return fail(name, "post-crash establish failed: %s" % second.detail)
    # KeyboardInterrupt during egress is isolated too (twice -- the
    # consecutive-failure threshold for DEGRADED is 2).
    e = mgr.egress(now=_NOW, breakout_ref=second.value.breakout_ref, payload=b"x")
    if e.ok or e.reason != DistCoreReasonCode.DISTCORE_FAILURE:
        return fail(name, "KeyboardInterrupt isolation: %s" % e.reason)
    e2 = mgr.egress(now=_T1, breakout_ref=second.value.breakout_ref, payload=b"y")
    if e2.ok or e2.reason != DistCoreReasonCode.DISTCORE_FAILURE:
        return fail(name, "second KeyboardInterrupt isolation: %s" % e2.reason)
    # Health accounting: consecutive failures degrade the sandbox.
    sandbox = mgr._registrations[0].sandbox  # noqa: SLF001
    if sandbox.computed_health() != "DEGRADED":
        return fail(name, "failures did not degrade health: %s" % sandbox.computed_health())
    return ok(name, "SystemExit/KeyboardInterrupt from a provider are "
                    "fully isolated typed failure values (secret-free; "
                    "no state committed; health degrades)")


def case_24_contract_violations_discarded() -> Result:
    name = "case_24_contract_violations_discarded"

    class _TamperingProvider(BreakoutProviderContract):
        """A hostile provider whose returns violate the frozen
        contract shape in selectable ways (one violation per flag)."""
        label = "tampering"

        def __init__(self, *, misbind_gateway=False, fake_binding_key=False,
                     foreign_egress_ref=False, bad_metric=False,
                     bad_health=False, bad_allocation=False):
            self.misbind_gateway = misbind_gateway
            self.fake_binding_key = fake_binding_key
            self.foreign_egress_ref = foreign_egress_ref
            self.bad_metric = bad_metric
            self.bad_health = bad_health
            self.bad_allocation = bad_allocation

        def open(self, context):
            return None

        def register_gateway(self, context, *, descriptor, evidence):
            ref = (
                "distcore:gateway:" + "0" * 32
                if self.misbind_gateway
                else derive_gateway_ref(
                    descriptor.name, descriptor.gateway_id,
                    descriptor.node_id, descriptor.role_class,
                )
            )
            return GatewayCandidate(
                gateway_ref=ref,
                name=descriptor.name, gateway_id=descriptor.gateway_id,
                node_id=descriptor.node_id,
                role_class=descriptor.role_class,
                locality_label=descriptor.locality_label,
                capacity_bps=descriptor.capacity_bps,
                state=GatewayState.AVAILABLE,
                evidence_source_class=evidence.source_class,
            )

        def close_gateway(self, context, *, gateway_ref):
            return None

        def allocate(self, context, *, kind, quantity_base, purpose):
            if self.bad_allocation:
                return "not-an-allocation"
            return BreakoutAllocation(
                allocation_ref=derive_allocation_ref(kind, quantity_base, purpose, 1),
                kind=kind, quantity_base=quantity_base, purpose=purpose,
                state=AllocationState.RESERVED,
            )

        def release(self, context, *, allocation_ref):
            return None

        def establish_breakout(self, context, *, session_id, gateway_ref,
                               path_ref, requirements=None):
            breakout_ref = derive_breakout_ref(session_id, gateway_ref, path_ref, 1)
            binding_id = (
                "distcore:binding:" + "0" * 32
                if self.fake_binding_key
                else derive_binding_id(session_id, breakout_ref)
            )
            return BreakoutBinding(
                session_id=session_id, breakout_ref=breakout_ref,
                binding_id=binding_id,
                gateway_ref=gateway_ref, path_ref=path_ref,
                state=BreakoutState.ACTIVE,
                established_instant=context.now(),
            )

        def release_breakout(self, context, *, breakout_ref):
            return None

        def egress(self, context, *, breakout_ref, payload):
            gateway_ref = (
                "mesh:link:" + "0" * 32
                if self.foreign_egress_ref
                else "distcore:gateway:" + "1" * 32
            )
            return EgressOutcome(
                breakout_ref=breakout_ref, gateway_ref=gateway_ref,
                egress_instant=context.now(), payload_bytes=len(payload),
            )

        def observe(self, context):
            samples = (
                (("n6-session-count", 3),)
                if self.bad_metric
                else ((LinkMetricName.LINK_UP, 1),)
            )
            return DistCoreObservation(samples=samples)

        def health(self):
            return "GREEN" if self.bad_health else "HEALTHY"

        def close(self, context):
            return None

    def build(provider):
        mgr = DistributedCoreManager(session_reader=_READER)
        mgr.register_provider(
            provider, label="tamper",
            breakout_mode=BreakoutMode.LOCAL, now=_NOW,
        )
        mgr.register_path(now=_NOW, path=_LOCAL_PATH)
        decision = mgr.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
        )
        return mgr, decision

    # Misbound gateway ref -> rejected fail-closed with the value
    # discarded (the MODEL's tamper-evident constructor catches it at
    # construction inside the provider; the sandbox surfaces the
    # typed failure -- either invalid-input here or
    # contract-violation if a subclass bypasses the constructor, and
    # the seam's own re-assert backstops both).
    mgr, decision = build(_TamperingProvider(misbind_gateway=True))
    g = mgr.register_gateway(
        now=_NOW, label="tamper",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    if g.ok or g.reason not in (
        DistCoreReasonCode.CONTRACT_VIOLATION,
        DistCoreReasonCode.INVALID_INPUT,
    ):
        return fail(name, "misbound gateway ref: %s" % g.reason)
    if mgr._gateways:  # noqa: SLF001
        return fail(name, "violating gateway value was stored")

    # Non-allocation return -> CONTRACT_VIOLATION.
    mgr, decision = build(_TamperingProvider(bad_allocation=True))
    a = mgr.allocate(now=_NOW, kind="bandwidth", quantity_base=1, purpose="p")
    if a.ok or a.reason != DistCoreReasonCode.CONTRACT_VIOLATION:
        return fail(name, "non-allocation: %s" % a.reason)

    # Fabricated binding key -> CONTRACT_VIOLATION (the establish
    # reaches the provider: a WELL-FORMED gateway is admitted first).
    mgr, decision = build(_TamperingProvider(fake_binding_key=True))
    gw = mgr.register_gateway(
        now=_NOW, label="tamper",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    if not gw.ok:
        return fail(name, "well-formed gateway on the tampering provider rejected")
    b = mgr.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=decision.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if b.ok or b.reason not in (
        DistCoreReasonCode.CONTRACT_VIOLATION,
        DistCoreReasonCode.INVALID_INPUT,
    ):
        return fail(name, "fabricated binding key: %s" % b.reason)
    if mgr._breakouts:  # noqa: SLF001
        return fail(name, "violating binding value was stored")

    # Foreign gateway-grammar on the egress outcome -> CONTRACT_VIOLATION.
    mgr, decision = build(_TamperingProvider(foreign_egress_ref=True))
    mgr.register_gateway(
        now=_NOW, label="tamper",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    b = mgr.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=decision.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if not b.ok:
        return fail(name, "well-formed establish on the tampering provider rejected")
    e = mgr.egress(now=_NOW, breakout_ref=b.value.breakout_ref, payload=b"x")
    if e.ok or e.reason not in (
        DistCoreReasonCode.CONTRACT_VIOLATION,
        DistCoreReasonCode.INVALID_INPUT,
    ):
        return fail(name, "foreign egress ref: %s" % e.reason)

    # Non-generic observation metric -> rejected fail-closed (the
    # MODEL's vocabulary check catches it inside the provider; the
    # sandbox validator re-asserts the same invariant at the seam).
    mgr, decision = build(_TamperingProvider(bad_metric=True))
    o = mgr.observe(now=_NOW)
    if o.ok or o.reason not in (
        DistCoreReasonCode.CONTRACT_VIOLATION,
        DistCoreReasonCode.INVALID_INPUT,
    ):
        return fail(name, "observation vocabulary: %s" % o.reason)

    # Out-of-vocabulary health -> the register_provider health probe
    # surfaces the CONTRACT_VIOLATION (registration fails).
    mgr, decision = build(_TamperingProvider(bad_health=True))
    r = mgr.register_provider(
        _TamperingProvider(bad_health=True), label="tamper-2",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    if r.ok or r.reason != DistCoreReasonCode.CONTRACT_VIOLATION:
        return fail(name, "health vocabulary: %s" % r.reason)
    return ok(name, "misbound refs, fabricated binding keys, foreign "
                    "grammars, non-generic metrics, non-allocations, and "
                    "vocabulary violations are rejected fail-closed "
                    "(model constructor or sandbox validator) with the "
                    "values discarded")

def case_25_budget_exhaustion() -> Result:
    name = "case_25_budget_exhaustion"

    class _StarvingProvider(BreakoutProviderContract):
        label = "starving"
        def open(self, context):
            return None
        def register_gateway(self, context, *, descriptor, evidence):
            context.charge(10 ** 9)  # starve the budget
            return GatewayCandidate(
                gateway_ref=derive_gateway_ref(
                    descriptor.name, descriptor.gateway_id,
                    descriptor.node_id, descriptor.role_class,
                ),
                name=descriptor.name, gateway_id=descriptor.gateway_id,
                node_id=descriptor.node_id,
                role_class=descriptor.role_class,
                locality_label=descriptor.locality_label,
                capacity_bps=descriptor.capacity_bps,
                state=GatewayState.AVAILABLE,
                evidence_source_class=evidence.source_class,
            )
        def close_gateway(self, context, *, gateway_ref):
            return None
        def allocate(self, context, *, kind, quantity_base, purpose):
            return BreakoutAllocation(
                allocation_ref=derive_allocation_ref(kind, quantity_base, purpose, 1),
                kind=kind, quantity_base=quantity_base, purpose=purpose,
                state=AllocationState.RESERVED,
            )
        def release(self, context, *, allocation_ref):
            return None
        def establish_breakout(self, context, *, session_id, gateway_ref, path_ref, requirements=None):
            return BreakoutBinding(
                session_id=session_id,
                breakout_ref=derive_breakout_ref(session_id, gateway_ref, path_ref, 1),
                binding_id=derive_binding_id(
                    session_id,
                    derive_breakout_ref(session_id, gateway_ref, path_ref, 1),
                ),
                gateway_ref=gateway_ref, path_ref=path_ref,
                state=BreakoutState.ACTIVE,
                established_instant=context.now(),
            )
        def release_breakout(self, context, *, breakout_ref):
            return None
        def egress(self, context, *, breakout_ref, payload):
            return EgressOutcome(
                breakout_ref=breakout_ref, gateway_ref="distcore:gateway:" + "1" * 32,
                egress_instant=context.now(), payload_bytes=len(payload),
            )
        def observe(self, context):
            return DistCoreObservation()
        def health(self):
            return "HEALTHY"
        def close(self, context):
            return None

    mgr = DistributedCoreManager(
        session_reader=_READER, step_budget=100,
    )
    mgr.register_provider(
        _StarvingProvider(), label="starve",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    result = mgr.register_gateway(
        now=_NOW, label="starve",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    if result.ok or result.reason != DistCoreReasonCode.BUDGET_EXHAUSTED:
        return fail(name, "budget exhaustion: %s" % result.reason)
    if "wall clock" not in result.detail and "budget" not in result.detail:
        return fail(name, "budget detail drifted: %s" % result.detail)
    # No state committed.
    if mgr._gateways:  # noqa: SLF001
        return fail(name, "starved gateway registration committed state")
    return ok(name, "a hung/overrunning provider exhausts the "
                    "deterministic budget and fails closed (hang model; "
                    "no wall clock)")


def case_26_secret_isolation() -> Result:
    name = "case_26_secret_isolation"
    mgr, _, _ = _full_stack()
    # Credential-like text is rejected across the caller surface.
    for secretish in ("gateway_password", "shared_secret", "psk"):
        try:
            GatewayDescriptor(
                name=secretish, gateway_id="g",
                node_id=_NODE_LOCAL_GW,
                role_class=GatewayRoleClass.IP_GATEWAY,
            )
            return fail(name, "credential-like gateway name accepted")
        except DistCoreError:
            pass
        try:
            GatewayEvidence(
                observer_node_id=_NODE_LOCAL_GW,
                reporter_node_id=_NODE_LOCAL_GW,
                source_class=EvidenceSourceClass.DIRECT_OBSERVATION,
                observed_at=_NOW, claim_digest="0" * 64,
                provenance=secretish,
            )
            return fail(name, "credential-like provenance accepted")
        except DistCoreError:
            pass
    # The canonical state carries no secret-shaped content.
    b = _establish_local(mgr)
    if not b.ok:
        return fail(name, "establishment failed")
    canonical = mgr.to_canonical_bytes().decode()
    for token in ("password", "secret", "psk", "api_key", "credential"):
        if token in canonical.lower():
            return fail(name, "canonical state carries %r" % token)
    # Credential slot NAMES only (never material) -- the validator
    # rejects credential-LIKE names.
    from adapters.distcore.validation import validate_credential_slot_name
    if validate_credential_slot_name("gateway-management") != "gateway-management":
        return fail(name, "honest slot name rejected")
    try:
        validate_credential_slot_name("gateway_password")
        return fail(name, "credential-like slot name accepted")
    except DistCoreError:
        pass
    return ok(name, "credential-like text rejected at every surface; "
                    "canonical state is secret-free; slot names only")


def case_27_canonical_state_shape() -> Result:
    name = "case_27_canonical_state_shape"
    mgr, _, _ = _full_stack()
    b_local = _establish_local(mgr)
    b_remote = _establish_remote(mgr)
    if not (b_local.ok and b_remote.ok):
        return fail(name, "establishments failed")
    snapshot = mgr.snapshot()
    if set(snapshot.keys()) != {
        "integration_id", "closed", "breakout_count", "breakouts",
        "decisions", "events",
    }:
        return fail(name, "snapshot keys drifted: %s" % sorted(snapshot.keys()))
    # ACCESS-STATE-OUT: no labels, no gateway tables, no path content,
    # no payloads, no diagnostic health.
    canonical = mgr.to_canonical_bytes().decode()
    for forbidden in (
        "reference-ip-gateway", "reference-upf", "implementation_label",
        "computed_health", "delivered", "village-gateway", "core-upf",
        "capacity_bps", "n6_frames", "local-breakout-payload",
    ):
        if forbidden in canonical:
            return fail(name, "canonical state carries %r" % forbidden)
    # The bindings carry the authoritative chain fields.
    for record in snapshot["breakouts"]:
        if set(record.keys()) != {
            "session_id", "breakout_ref", "binding_id", "gateway_ref",
            "path_ref", "mode", "role_class", "decision_ref", "state",
            "established_instant", "path_latency_ms", "supersedes",
            "superseded_by",
        }:
            return fail(name, "binding record keys drifted: %s" % sorted(record.keys()))
    # The decisions carry the policy provenance fields.
    for decision in snapshot["decisions"]:
        if set(decision.keys()) != {
            "decision_ref", "session_id", "policy_decision_id",
            "policy_effect", "mode", "matched_rule_ids",
            "locality_labels", "applied_instant",
        }:
            return fail(name, "decision record keys drifted: %s" % sorted(decision.keys()))
    # Sorted determinism.
    binding_ids = [b["binding_id"] for b in snapshot["breakouts"]]
    if binding_ids != sorted(binding_ids):
        return fail(name, "breakouts not sorted by binding_id")
    decision_refs = [d["decision_ref"] for d in snapshot["decisions"]]
    if decision_refs != sorted(decision_refs):
        return fail(name, "decisions not sorted by decision_ref")
    return ok(name, "canonical state = integration id + closed + active "
                    "count + bindings(chain) + decisions(policy DATA) + "
                    "events; everything else stays behind the seam")


def case_28_teardown_fail_closed() -> Result:
    name = "case_28_teardown_fail_closed"
    mgr, _, _ = _full_stack()
    b = _establish_local(mgr)
    if not b.ok:
        return fail(name, "establishment failed")
    local_gw_ref = derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    )
    # Gateway close with a live breakout fails closed.
    closed = mgr.close_gateway(now=_NOW, gateway_ref=local_gw_ref)
    if closed.ok:
        return fail(name, "gateway closed with a live breakout")
    # Release, then close succeeds.
    if not mgr.release_breakout(now=_NOW, breakout_ref=b.value.breakout_ref).ok:
        return fail(name, "release failed")
    closed2 = mgr.close_gateway(now=_NOW, gateway_ref=local_gw_ref)
    if not closed2.ok:
        return fail(name, "gateway close after release failed: %s" % closed2.detail)
    # Unknown gateway after close.
    try:
        mgr.close_gateway(now=_NOW, gateway_ref=local_gw_ref)
        return fail(name, "closed gateway re-closed")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.GATEWAY_UNKNOWN:
            return fail(name, "re-close mistyped")
    # Manager close: subsequent ops reject.
    mgr.close()
    if not mgr.closed:
        return fail(name, "close flag not set")
    try:
        mgr.register_path(now=_NOW, path=_LOCAL_PATH)
        return fail(name, "post-close op accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ILLEGAL_STATE:
            return fail(name, "post-close mistyped: %s" % exc.reason)
    if mgr.snapshot()["closed"] is not True:
        return fail(name, "closed flag not canonical")
    return ok(name, "gateway close fail-closed with live breakouts; "
                    "manager close rejects subsequent operations")


def case_29_work016_sdk_bridge() -> Result:
    name = "case_29_work016_sdk_bridge"
    from adapters import (
        AdapterDescriptor,
        AdapterRuntime,
        AdapterSecurityState,
    )
    from adapters.model import ResourceMappingEntry, derive_adapter_id

    # A REAL WORK-012 store backs BOTH the manager's and the SDK
    # runtime's read-only bindability verification.
    store, live_sid, decision, _selected = _compose_real_session("5")
    reader = _DualReader(store=store)
    mgr = DistributedCoreManager(session_reader=reader)
    mgr.register_provider(
        ReferenceIPGatewayEngine(), label="local",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    mgr.register_gateway(
        now=_NOW, label="local",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    mgr.register_path(now=_NOW, path=_LOCAL_PATH)
    applied = mgr.apply_policy_decision(
        now=_NOW, session_id=live_sid,
        policy_decision=decision, mode=BreakoutMode.LOCAL,
        locality_labels=(_LOCALITY,),
    )
    if not applied.ok:
        return fail(name, "decision application failed: %s" % applied.detail)
    bridge = DistCoreTechnologyAdapter(mgr)
    descriptor = AdapterDescriptor(
        adapter_id=derive_adapter_id(
            "access.generic.experimental", "distcore-sdk-bridge"
        ),
        access_technology_id="access.generic.experimental",
        supported_profile_versions=("v1-0-0",),
        capabilities=(
            "capability.core.local-breakout",
            "capability.profile.distcore.breakout",
            "capability.profile.distcore.failover",
            "capability.profile.distcore.remote-breakout",
        ),
        resource_mapping=(
            ResourceMappingEntry(
                technology_resource="breakout-capacity",
                kind="bandwidth",
                unit="bps",
                quantity=1024,
                availability="reservation-based",
            ),
        ),
        security_state=AdapterSecurityState(
            profile="baseline",
            credential_slots=("gateway-management",),
            attested=False,
        ),
    )
    runtime = AdapterRuntime(session_store=store)
    runtime.register(descriptor, bridge, now=_NOW)
    opened = runtime.open_adapter(descriptor.adapter_id, now=_NOW)
    if not opened.ok:
        return fail(name, "SDK open failed")
    caps = runtime.capabilities(descriptor.adapter_id, now=_NOW)
    if "capability.core.local-breakout" not in caps:
        return fail(name, "SDK capabilities missing the local-breakout id: %s" % caps)
    observed = runtime.observe(descriptor.adapter_id, now=_NOW)
    if not observed.ok:
        return fail(name, "SDK observe failed")
    observed_metrics = {sample.metric for sample in observed.value}
    for metric in ("link-up", "rx-bytes-total", "tx-bytes-total",
                   "rx-error-count", "tx-error-count", "retransmit-count"):
        if metric not in observed_metrics:
            return fail(name, "generic metric %r missing" % metric)
    # allocate -> a breakout-capacity admission (mapped kind/unit).
    alloc = runtime.allocate(
        descriptor.adapter_id, now=_NOW, kind="bandwidth",
        quantity=64, unit="bps", purpose="sdk-reservation",
    )
    if not alloc.ok:
        return fail(name, "SDK allocate failed: %s" % alloc.detail)
    # bind_session -> a breakout over the decision + path coordinates
    # (requirements carry the breakout coordinates as DATA).
    bound = runtime.bind_session(
        descriptor.adapter_id, now=_NOW, session_id=live_sid,
        requirements={
            "decision_ref": applied.value.decision_ref,
            "path_ref": _LOCAL_PATH.path_id,
        },
    )
    if not bound.ok:
        return fail(name, "SDK bind failed: %s" % bound.detail)
    if not bound.value.bearer_ref.startswith("distcore:breakout:"):
        return fail(name, "SDK bind returned %r" % bound.value.bearer_ref[:20])
    # The bridge routed through the MANAGER: the canonical event
    # history proves mediation (two-layer proof).
    events = [e["event_type"] for e in mgr.snapshot()["events"]]
    for needed in ("BREAKOUT_ESTABLISHED", "ALLOCATED", "OBSERVED"):
        if needed not in events:
            return fail(name, "bridge bypassed the manager (missing %s)" % needed)
    # unbind + release through the SDK surface.
    unbound = runtime.unbind_session(bound.value.binding_id, now=_NOW)
    if not unbound.ok:
        return fail(name, "SDK unbind failed: %s" % unbound.detail)
    released = runtime.release(alloc.value.allocation_id, now=_NOW)
    if not released.ok:
        return fail(name, "SDK release failed")
    health = runtime.health(descriptor.adapter_id, now=_NOW)
    if health.state not in ("HEALTHY", "DEGRADED"):
        return fail(name, "SDK health: %s" % health.state)
    # bind without the coordinates fails closed (the SDK sandbox
    # isolates the bridge's AdapterError into a failure VALUE).
    coordinateless = runtime.bind_session(
        descriptor.adapter_id, now=_NOW, session_id=live_sid,
        requirements={},
    )
    if coordinateless.ok:
        return fail(name, "coordinate-less bind accepted")
    # An unknown requirement key fails closed.
    smuggled = runtime.bind_session(
        descriptor.adapter_id, now=_NOW, session_id=live_sid,
        requirements={"decision_ref": applied.value.decision_ref,
                      "path_ref": _LOCAL_PATH.path_id, "session_id": live_sid},
    )
    if smuggled.ok:
        return fail(name, "identity-smuggling requirement key accepted")
    return ok(name, "the nine-op SDK bridge routes through the mediated "
                    "manager (allocate/bind/unbind/observe/health; "
                    "real WORK-012 store behind both layers); "
                    "missing/smuggling coordinates fail closed")


# --------------------------------------------------------------------------
# Standards-boundary and no-core-leakage audits
# --------------------------------------------------------------------------


def case_30_standards_boundary_audit() -> Result:
    name = "case_30_standards_boundary_audit"
    allowed_roots = (
        "protocol", "routing", "policy", "resources", "adapters",
        "__future__", "abc", "dataclasses", "datetime", "typing",
        "types", "re", "hashlib", "collections",
    )
    modules = (
        "errors.py", "validation.py", "model.py", "contract.py",
        "sandbox.py", "engine.py", "upf.py", "manager.py",
        "bridge.py", "serialization.py", "__init__.py",
    )
    for module in modules:
        source = _src(module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed_roots:
                        return fail(
                            name, "%s imports forbidden root %r"
                            % (module, alias.name)
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    # Intra-family relative import (adapters.distcore.*
                    # and the sanctioned ..contract SDK bridge):
                    # always sanctioned.
                    continue
                if node.module is None:
                    continue
                root = node.module.split(".")[0]
                if root not in allowed_roots:
                    return fail(
                        name, "%s imports from forbidden root %r"
                        % (module, node.module)
                    )
                # No ABSOLUTE adapters.* import: the family never
                # imports another family (cross-family composition
                # belongs to the composition root).
                if root == "adapters" and node.module != "adapters":
                    return fail(
                        name, "%s absolutely imports %r (cross-family "
                        "composition belongs to the composition root)"
                        % (module, node.module)
                    )
    # No second routing authority: the family references the routing
    # ENGINE never (only Path/derive_path_id/LinkMetrics data).
    for module in ("engine.py", "upf.py", "model.py", "manager.py"):
        source = _src(module)
        if "RoutingEngine" in source or "RoutingContext" in source:
            return fail(name, "%s references the routing ENGINE" % module)
        if "construct_candidates" in source or "rank_candidates" in source:
            return fail(name, "%s enumerates or scores paths" % module)
    # No second policy authority: the family references the policy
    # ENGINE/evaluator never (only the PolicyDecision data type).
    for module in ("manager.py", "model.py"):
        source = _src(module)
        if "PolicyEngine" in source:
            return fail(name, "%s references the policy ENGINE" % module)
        if "from policy import" in source or "import policy\n" in source:
            # only policy.model.PolicyDecision is consumed
            if "from policy.model import PolicyDecision" not in source:
                return fail(name, "%s imports policy beyond the decision DATA type" % module)
    # Standards citations as DATA.
    engine_src = _src("engine.py") + _src("upf.py") + _src("model.py")
    for citation in ("ts 23.501", "ts 23.548", "ts 29.244"):
        if citation not in engine_src.lower():
            return fail(name, "missing 3GPP citation %s" % citation)
    # No vendor/daemon vocabulary in CODE (docstrings/comments cite
    # the forbidden concepts only in negation -- stripped first).
    def _strip_prose(source: str) -> str:
        tree = ast.parse(source)
        chunks = [source]
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                       ast.ClassDef)
            ):
                body = getattr(node, "body", None)
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    chunks.append(body[0].value.value)
        stripped = chunks[0]
        for doc in chunks[1:]:
            stripped = stripped.replace(doc, "")
        lines = [
            line for line in stripped.splitlines()
            if not line.lstrip().startswith("#")
        ]
        return "\n".join(lines)

    for module in ("engine.py", "upf.py", "model.py", "manager.py",
                   "contract.py", "bridge.py"):
        source = _strip_prose(_src(module)).lower()
        for token in ("open5gs", "n3iwf", "pfcp", "vendor sdk",
                      "snmp community", "daemon api"):
            if token in source:
                return fail(
                    name, "%s carries vendor/daemon token %r in code"
                    % (module, token)
                )
    return ok(
        name,
        "imports confined to protocol/routing/policy/resources/adapters "
        "(relative only across adapters); no routing/policy ENGINE usage "
        "(Path/PolicyDecision data only); no absolute cross-family "
        "imports; 3GPP TS 23.501/23.548/29.244 cited as DATA; no "
        "vendor/daemon vocabulary",
    )


def case_31_no_core_leakage() -> Result:
    name = "case_31_no_core_leakage"
    core_roots = (
        "identity", "capability", "discovery", "topology", "resources",
        "intent", "policy", "routing", "sessions", "multipath",
        "mobility", "federation", "transport", "protocol",
    )
    for root in core_roots:
        base = os.path.join(_ROOT, root)
        if not os.path.isdir(base):
            continue
        for filename in os.listdir(base):
            if not filename.endswith(".py") or filename == "__init__.py":
                continue
            path = os.path.join(base, filename)
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()
            if "adapters.distcore" in source or "adapters import distcore" in source:
                return fail(name, "%s/%s imports the distcore family" % (root, filename))
            if "from adapters import" in source and "DistCore" in source:
                return fail(name, "%s/%s references distcore symbols" % (root, filename))
    # The adapters SDK itself must not import or reference the family.
    for filename in ("contract.py", "model.py", "sandbox.py", "runtime.py",
                     "errors.py", "validation.py", "serialization.py"):
        path = os.path.join(_ROOT, "adapters", filename)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        import re as _re

        if _re.search(r"\bdistcore\b", source):
            return fail(name, "adapters/%s references distcore" % filename)
    # No OTHER family imports the distcore family (family separation).
    for family in ("ip", "fivegc", "wifi", "backhaul", "mesh"):
        base = os.path.join(_ROOT, "adapters", family)
        if not os.path.isdir(base):
            continue
        for filename in os.listdir(base):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(base, filename)
            with open(path, "r", encoding="utf-8") as handle:
                if "distcore" in handle.read():
                    return fail(
                        name, "adapters/%s/%s references distcore"
                        % (family, filename)
                    )
    return ok(
        name,
        "no core module, SDK file, or sibling family imports or "
        "references the distcore family; the SDK stays family-agnostic",
    )


# --------------------------------------------------------------------------
# Determinism and frozen-spec identity
# --------------------------------------------------------------------------


def case_32_determinism_repeated_runs() -> Result:
    name = "case_32_determinism_repeated_runs"

    def sequence() -> str:
        mgr, local_engine, remote_engine = _full_stack()
        b_local = _establish_local(mgr)
        mgr.egress(now=_NOW, breakout_ref=b_local.value.breakout_ref, payload=_PAYLOAD)
        remote_decision = mgr.apply_policy_decision(
            now=_T4, session_id=_SESSION_ID,
            policy_decision=_allow_decision(evaluation_instant=_T4),
            mode=BreakoutMode.REMOTE,
        )
        f = mgr.failover_binding(
            now=_T4, breakout_ref=b_local.value.breakout_ref,
            target_decision_ref=remote_decision.value.decision_ref,
            target_path_ref=_REMOTE_PATH.path_id,
        )
        mgr.egress(now=_T4, breakout_ref=f.value.breakout_ref, payload=_PAYLOAD_2)
        # Partition, fail BACK, recover.
        local_gw_ref = derive_gateway_ref(
            _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
            _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
        )
        local_engine.set_gateway_state(local_gw_ref, available=False)
        mgr.observe(now=_T2, label="local")
        local_engine.set_gateway_state(local_gw_ref, available=True)
        recovery = mgr.apply_policy_decision(
            now=_T5, session_id=_SESSION_ID,
            policy_decision=_allow_decision(evaluation_instant=_T5),
            mode=BreakoutMode.LOCAL, locality_labels=(_LOCALITY,),
        )
        back = mgr.failover_binding(
            now=_T2, breakout_ref=f.value.breakout_ref,
            target_decision_ref=recovery.value.decision_ref,
            target_path_ref=_LOCAL_PATH.path_id,
        )
        mgr.egress(now=_T2, breakout_ref=back.value.breakout_ref, payload=_PAYLOAD)
        mgr.allocate(
            now=_T2, kind="bandwidth",
            quantity_base=1000, purpose="reserve",
        )
        mgr.health(now=_T3)
        return mgr.content_digest()

    if sequence() != sequence():
        return fail(name, "repeated runs diverged")
    return ok(name, "byte-identical canonical digest across repeated "
                    "runs (establish -> egress -> failover -> partition -> "
                    "recovery -> fail back -> allocate)")


def case_33_determinism_hash_seed() -> Result:
    name = "case_33_determinism_hash_seed"
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "import hashlib\n"
        "from adapters.distcore import (\n"
        "    DistributedCoreManager, ReferenceIPGatewayEngine,\n"
        "    ReferenceUPFEngine, GatewayDescriptor, GatewayEvidence,\n"
        "    GatewayRoleClass, EvidenceSourceClass, BreakoutMode,\n"
        "    SessionReader, SessionView, derive_gateway_claim_digest,\n"
        "    derive_breakout_ref, derive_binding_id, BreakoutBinding,\n"
        "    BreakoutState, EgressOutcome,\n"
        ")\n"
        "from policy.model import PolicyDecision\n"
        "from routing.model import (\n"
        "    LinkMetrics, Path, aggregate_link_metrics, derive_path_id,\n"
        ")\n"
        "NOW = '2026-06-01T12:00:00Z'\n"
        "FRESH = '2026-12-31T23:59:59Z'\n"
        "A = 'adcos:node:test.profile.v1:' + 'a' * 64\n"
        "B = 'adcos:node:test.profile.v1:' + 'b' * 64\n"
        "C = 'adcos:node:test.profile.v1:' + 'c' * 64\n"
        "SID = 'sha256:' + '1' * 64\n"
        "class R(SessionReader):\n"
        "    def lookup(self, sid):\n"
        "        return SessionView(session_id=sid, secureable=True,\n"
        "            initiator_node_id=A, responder_node_id=B)\n"
        "hops = ('link:%%s:%%s' %% (A, B),)\n"
        "nodes = (A, B)\n"
        "metrics = aggregate_link_metrics((LinkMetrics(latency_ms=5,\n"
        "    loss_basis_points=0, capacity_bps=10000000,\n"
        "    energy_cost_millijoules=10, confidence_basis_points=10000,\n"
        "    observed_at=NOW, freshness_until=FRESH),))\n"
        "path = Path(path_id=derive_path_id(A, B, hops, nodes),\n"
        "    source_node_id=A, destination_node_id=B, hops=hops,\n"
        "    nodes=nodes, metrics=metrics, feasible=True)\n"
        "hops_r = ('link:%%s:%%s' %% (A, C),)\n"
        "nodes_r = (A, C)\n"
        "metrics_r = aggregate_link_metrics((LinkMetrics(latency_ms=50,\n"
        "    loss_basis_points=0, capacity_bps=50000000,\n"
        "    energy_cost_millijoules=10, confidence_basis_points=10000,\n"
        "    observed_at=NOW, freshness_until=FRESH),))\n"
        "path_r = Path(path_id=derive_path_id(A, C, hops_r, nodes_r),\n"
        "    source_node_id=A, destination_node_id=C, hops=hops_r,\n"
        "    nodes=nodes_r, metrics=metrics_r, feasible=True)\n"
        "probe = PolicyDecision(decision_id='0' * 64, effect='allow',\n"
        "    code='allow', detail='w', matched_rule_ids=('r1',),\n"
        "    policy_set_id='ps', policy_set_version=1,\n"
        "    evaluation_instant=NOW)\n"
        "dec = PolicyDecision(decision_id=hashlib.sha256(\n"
        "    probe.canonical_bytes()).hexdigest(), effect='allow',\n"
        "    code='allow', detail='w', matched_rule_ids=('r1',),\n"
        "    policy_set_id='ps', policy_set_version=1,\n"
        "    evaluation_instant=NOW)\n"
        "dl = GatewayDescriptor(name='g', gateway_id='1', node_id=B,\n"
        "    role_class='ip-gateway', locality_label='L',\n"
        "    capacity_bps=10000000)\n"
        "el = GatewayEvidence(observer_node_id=B, reporter_node_id=B,\n"
        "    source_class='direct-observation', observed_at=NOW,\n"
        "    claim_digest=derive_gateway_claim_digest(dl))\n"
        "dr = GatewayDescriptor(name='u', gateway_id='2', node_id=C,\n"
        "    role_class='upf', capacity_bps=50000000)\n"
        "er = GatewayEvidence(observer_node_id=C, reporter_node_id=A,\n"
        "    source_class='remote-claim', observed_at=NOW,\n"
        "    claim_digest=derive_gateway_claim_digest(dr))\n"
        "mgr = DistributedCoreManager(session_reader=R())\n"
        "mgr.register_provider(ReferenceIPGatewayEngine(), label='local',\n"
        "    breakout_mode='local', now=NOW)\n"
        "mgr.register_provider(ReferenceUPFEngine(), label='remote',\n"
        "    breakout_mode='remote', now=NOW)\n"
        "gl = mgr.register_gateway(now=NOW, label='local',\n"
        "    descriptor=dl, evidence=el)\n"
        "gr = mgr.register_gateway(now=NOW, label='remote',\n"
        "    descriptor=dr, evidence=er)\n"
        "assert gl.ok and gr.ok\n"
        "assert mgr.register_path(now=NOW, path=path).ok\n"
        "assert mgr.register_path(now=NOW, path=path_r).ok\n"
        "d1 = mgr.apply_policy_decision(now=NOW, session_id=SID,\n"
        "    policy_decision=dec, mode='local',\n"
        "    locality_labels=('village-A',))\n"
        "assert d1.ok\n"
        "b = mgr.establish_breakout(now=NOW, session_id=SID,\n"
        "    decision_ref=d1.value.decision_ref,\n"
        "    path_ref=path.path_id)\n"
        "assert b.ok\n"
        "e = mgr.egress(now=NOW, breakout_ref=b.value.breakout_ref,\n"
        "    payload=b'seed')\n"
        "assert e.ok\n"
        "d2 = mgr.apply_policy_decision(\n"
        "    now='2026-06-01T12:01:00Z', session_id=SID,\n"
        "    policy_decision=dec, mode='remote')\n"
        "assert d2.ok\n"
        "f = mgr.failover_binding(now='2026-06-01T12:01:00Z',\n"
        "    breakout_ref=b.value.breakout_ref,\n"
        "    target_decision_ref=d2.value.decision_ref,\n"
        "    target_path_ref=path_r.path_id)\n"
        "assert f.ok\n"
        "e2 = mgr.egress(now='2026-06-01T12:01:00Z',\n"
        "    breakout_ref=f.value.breakout_ref, payload=b'seed2')\n"
        "assert e2.ok\n"
        "sys.stdout.write(mgr.content_digest())\n"
    ) % (_ROOT,)
    digests = []
    for seed in ("0", "1", "7919"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, env=env, cwd=_ROOT,
        )
        if proc.returncode != 0:
            return fail(
                name, "seed=%s run failed: %s" % (seed, proc.stderr[-300:])
            )
        digests.append(proc.stdout.strip())
    if len(set(digests)) != 1:
        return fail(name, "digests differ across PYTHONHASHSEED: %s" % digests)
    return ok(
        name,
        "byte-identical canonical digest across PYTHONHASHSEED "
        "variation (0/1/7919)",
    )


def case_34_frozen_spec_intact() -> Result:
    name = "case_34_frozen_spec_intact"
    diff = subprocess.run(
        ["git", "diff", "origin/main", "HEAD", "--", "spec/"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/"],
        capture_output=True, text=True, cwd=_ROOT,
    )
    if diff.stdout.strip() or status.stdout.strip():
        return fail(name, "spec/ not byte-identical to origin/main")
    return ok(name, "spec/ byte-identical to origin/main; working tree clean")


# --------------------------------------------------------------------------
# Observation honesty and cross-implementation identity
# --------------------------------------------------------------------------


def case_35_observation_honesty() -> Result:
    name = "case_35_observation_honesty"
    mgr, local_engine, remote_engine = _full_stack()
    b_local = _establish_local(mgr)
    b_remote = _establish_remote(mgr)
    mgr.egress(now=_NOW, breakout_ref=b_local.value.breakout_ref, payload=_PAYLOAD)
    mgr.egress(now=_T1, breakout_ref=b_remote.value.breakout_ref, payload=_PAYLOAD_2)
    local_gw_ref = derive_gateway_ref(
        _LOCAL_DESCRIPTOR.name, _LOCAL_DESCRIPTOR.gateway_id,
        _LOCAL_DESCRIPTOR.node_id, _LOCAL_DESCRIPTOR.role_class,
    )
    # Partition: the observation honestly reports the unavailable
    # gateway and the failed egress attempt.
    local_engine.set_gateway_state(local_gw_ref, available=False)
    failed = mgr.egress(now=_T2, breakout_ref=b_local.value.breakout_ref, payload=b"x")
    if failed.ok or failed.reason != DistCoreReasonCode.GATEWAY_UNAVAILABLE:
        return fail(name, "partitioned egress: %s" % failed.reason)
    obs = mgr.observe(now=_T2, label="local")
    if not obs.ok:
        return fail(name, "observe failed")
    observation = obs.value
    if observation.unavailable_gateways != 1 or observation.available_gateways != 0:
        return fail(name, "availability not honest: %s" % observation.to_dict())
    if observation.active_breakouts != 1:
        return fail(name, "active breakout count not honest")
    if observation.failed_egress != 1:
        return fail(name, "failed egress attempt not counted")
    if observation.delivered_egress != 1:
        return fail(name, "delivered egress not counted")
    # The sample vocabulary is exactly the six generic W016 names.
    from adapters.model import LinkMetricName as SdkMetricName

    if sorted(n for n, _ in observation.samples) != sorted(SdkMetricName.values()):
        return fail(name, "observation vocabulary is not the generic six")
    samples = dict(observation.samples)
    if samples["link-up"] != 0:
        return fail(name, "link-up does not carry availability")
    if samples["tx-error-count"] != 1:
        return fail(name, "tx-error-count does not carry the failure")
    if samples["tx-bytes-total"] != len(_PAYLOAD):
        return fail(name, "tx-bytes-total does not carry delivery bytes")
    # The engine health DEGRADES with the partition.
    if local_engine.health() != "DEGRADED":
        return fail(name, "partitioned engine not DEGRADED")
    # Recovery restores HEALTHY.
    local_engine.set_gateway_state(local_gw_ref, available=True)
    if local_engine.health() != "HEALTHY":
        return fail(name, "recovered engine not HEALTHY")
    return ok(name, "honest observation: availability, delivered/failed "
                    "egress, the generic six-metric vocabulary, DEGRADED "
                    "partition health, HEALTHY recovery")


def case_36_cross_implementation_byte_identity() -> Result:
    name = "case_36_cross_implementation_byte_identity"

    def journey(engine_factory):
        mgr = DistributedCoreManager(session_reader=_READER)
        mgr.register_provider(
            engine_factory(), label="provider",
            breakout_mode=BreakoutMode.LOCAL, now=_NOW,
        )
        mgr.register_gateway(
            now=_NOW, label="provider",
            descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
        )
        mgr.register_path(now=_NOW, path=_LOCAL_PATH)
        decision = mgr.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
            locality_labels=(_LOCALITY,),
        )
        b = mgr.establish_breakout(
            now=_NOW, session_id=_SESSION_ID,
            decision_ref=decision.value.decision_ref,
            path_ref=_LOCAL_PATH.path_id,
        )
        assert b.ok, b.detail
        mgr.egress(now=_NOW, breakout_ref=b.value.breakout_ref, payload=_PAYLOAD)
        mgr.egress(now=_T1, breakout_ref=b.value.breakout_ref, payload=_PAYLOAD_2)
        rel = mgr.release_breakout(now=_T2, breakout_ref=b.value.breakout_ref)
        assert rel.ok, rel.detail
        return mgr.content_digest()

    ip_digest = journey(ReferenceIPGatewayEngine)
    upf_digest = journey(ReferenceUPFEngine)
    if ip_digest != upf_digest:
        return fail(
            name,
            "cross-implementation divergence:\n  ip-gateway %s\n  upf %s"
            % (ip_digest, upf_digest),
        )
    return ok(name, "byte-identical canonical state over the SAME mediated "
                    "op sequence on the two independent implementations "
                    "(IP-gateway engine and UPF engine)")


# --------------------------------------------------------------------------
# REAL seam composition (WORK-018 IP seam + WORK-019 5GC seam)
# --------------------------------------------------------------------------


def _real_stack():
    """The REAL-seam composition root: a REAL WORK-012 session (real
    policy decision + real RoutingEngine path + real SessionStore),
    the REAL WORK-018 IPIntegrationManager as the LOCAL breakout
    provider, and the REAL WORK-019 FiveGCoreManager as the REMOTE
    breakout provider, both wrapped behind BreakoutProviderContract
    adapters."""
    from adapters.ip import IPIntegrationManager
    from adapters.fivegc import FiveGCoreManager, Reference5GCoreEngine
    from adapters.fivegc.model import Snssai, Dnn

    store, live_sid, decision, selected_path = _compose_real_session("7")
    reader = _DualReader(store=store)
    topo = _build_topology_reader()

    ip_manager = IPIntegrationManager(
        session_reader=reader, topology_reader=topo,
    )
    fivegc_manager = FiveGCoreManager(session_reader=reader)
    fivegc_manager.register_implementation(
        Reference5GCoreEngine(), now=_NOW,
    )
    local_provider = _IPSeamLocalProvider(ip_manager)
    remote_provider = _FiveGCSeamRemoteProvider(
        fivegc_manager,
        supi="imsi-001012345678901",
        snssai=Snssai(sst=1, sd="000001"),
        dnn=Dnn(value="internet"),
    )
    mgr = DistributedCoreManager(session_reader=reader)
    mgr.register_provider(
        local_provider, label="ip-seam",
        breakout_mode=BreakoutMode.LOCAL, now=_NOW,
    )
    mgr.register_provider(
        remote_provider, label="fivegc-seam",
        breakout_mode=BreakoutMode.REMOTE, now=_NOW,
    )
    mgr.register_gateway(
        now=_NOW, label="ip-seam",
        descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
    )
    mgr.register_gateway(
        now=_NOW, label="fivegc-seam",
        descriptor=_REMOTE_DESCRIPTOR, evidence=_REMOTE_EVIDENCE,
    )
    # The REAL RoutingEngine-selected path registers verbatim as the
    # local breakout path (destination = the local gateway node).
    mgr.register_path(now=_NOW, path=selected_path)
    mgr.register_path(now=_NOW, path=_REMOTE_PATH)
    return {
        "manager": mgr,
        "store": store,
        "session_id": live_sid,
        "decision": decision,
        "selected_path": selected_path,
        "ip_manager": ip_manager,
        "fivegc_manager": fivegc_manager,
        "local_provider": local_provider,
        "remote_provider": remote_provider,
        "reader": reader,
    }


def case_37_real_w018_ip_seam_local_breakout() -> Result:
    name = "case_37_real_w018_ip_seam_local_breakout"
    stack = _real_stack()
    mgr = stack["manager"]
    live_sid = stack["session_id"]
    decision = stack["decision"]
    selected_path = stack["selected_path"]
    ip_manager = stack["ip_manager"]

    # The policy determination for the REAL session.
    applied = mgr.apply_policy_decision(
        now=_NOW, session_id=live_sid,
        policy_decision=decision, mode=BreakoutMode.LOCAL,
        locality_labels=(_LOCALITY,),
    )
    if not applied.ok:
        return fail(name, "decision application failed: %s" % applied.detail)
    # Establish through the REAL WORK-018 seam.
    bound = mgr.establish_breakout(
        now=_NOW, session_id=live_sid,
        decision_ref=applied.value.decision_ref,
        path_ref=selected_path.path_id,
    )
    if not bound.ok:
        return fail(name, "ip-seam establish failed: %s" % bound.detail)
    # A REAL IP binding exists on the W018 manager (the real seam was
    # driven, and the sacred session id is the W012-minted one).
    ip_binding = ip_manager.binding_for_session(live_sid)
    if ip_binding is None:
        return fail(name, "no real IP binding on the W018 manager")
    if ip_binding.session_id != live_sid:
        return fail(name, "real IP binding lost the session identity")
    # Egress through the REAL app-transparent data path
    # (app_socket().send() -> the mediated W018 egress).
    egress = mgr.egress(
        now=_NOW, breakout_ref=bound.value.breakout_ref,
        payload=b"real-ip-seam-payload",
    )
    if not egress.ok:
        return fail(name, "ip-seam egress failed: %s" % egress.detail)
    if egress.value.locality != "local":
        return fail(name, "ip-seam egress not local")
    if egress.value.session_id != live_sid:
        return fail(name, "ip-seam egress lost the session identity")
    if egress.value.path_latency_ms != selected_path.metrics.latency_ms:
        return fail(name, "ip-seam latency drifted from the real Path")
    # Release through the real seam.
    released = mgr.release_breakout(
        now=_NOW, breakout_ref=bound.value.breakout_ref,
    )
    if not released.ok:
        return fail(name, "ip-seam release failed: %s" % released.detail)
    if ip_manager.binding_for_session(live_sid) is not None:
        return fail(name, "real IP binding not closed on release")
    return ok(name, "the REAL WORK-018 IPIntegrationManager serves local "
                    "breakout behind the contract (real bind/egress/close; "
                    "real W012 session; real RoutingEngine path)")


def case_38_real_w019_fivegc_remote_seam() -> Result:
    name = "case_38_real_w019_fivegc_remote_seam"
    stack = _real_stack()
    mgr = stack["manager"]
    live_sid = stack["session_id"]
    decision = stack["decision"]
    remote_provider = stack["remote_provider"]

    applied = mgr.apply_policy_decision(
        now=_T1, session_id=live_sid,
        policy_decision=_allow_decision(evaluation_instant=_T1),
        mode=BreakoutMode.REMOTE,
    )
    if not applied.ok:
        return fail(name, "decision application failed")
    # Establish through the REAL WORK-019 seam (bind -> authenticate
    # -> establish_pdu_session -- a REAL PDU-session anchor with a UE
    # IPv6 address).
    bound = mgr.establish_breakout(
        now=_T1, session_id=live_sid,
        decision_ref=applied.value.decision_ref,
        path_ref=_REMOTE_PATH.path_id,
    )
    if not bound.ok:
        return fail(name, "fivegc-seam establish failed: %s" % bound.detail)
    ue_ipv6 = remote_provider.ue_ipv6_for(bound.value.breakout_ref)
    if not ue_ipv6:
        return fail(name, "no UE IPv6 anchor from the real PDU session")
    # Egress through the real mediated N6 path (real bytes).
    egress = mgr.egress(
        now=_T1, breakout_ref=bound.value.breakout_ref,
        payload=b"real-fivegc-payload",
    )
    if not egress.ok:
        return fail(name, "fivegc-seam egress failed: %s" % egress.detail)
    if egress.value.locality != "remote":
        return fail(name, "fivegc-seam egress not remote")
    if egress.value.session_id != live_sid:
        return fail(name, "fivegc-seam egress lost the session identity")
    # Release through the real seam.
    released = mgr.release_breakout(
        now=_T2, breakout_ref=bound.value.breakout_ref,
    )
    if not released.ok:
        return fail(name, "fivegc-seam release failed: %s" % released.detail)
    return ok(name, "the REAL WORK-019 FiveGCoreManager serves remote "
                    "breakout behind the contract (real PDU-session anchor "
                    "with UE IPv6; real egress bytes; real release)")


def case_39_real_seam_failover_and_coexistence() -> Result:
    name = "case_39_real_seam_failover_and_coexistence"
    stack = _real_stack()
    mgr = stack["manager"]
    live_sid = stack["session_id"]
    decision = stack["decision"]
    selected_path = stack["selected_path"]
    local_provider = stack["local_provider"]
    remote_provider = stack["remote_provider"]
    ip_manager = stack["ip_manager"]

    # COEXISTENCE: a LOCAL breakout through the real IP seam.
    applied_local = mgr.apply_policy_decision(
        now=_NOW, session_id=live_sid,
        policy_decision=decision, mode=BreakoutMode.LOCAL,
        locality_labels=(_LOCALITY,),
    )
    local = mgr.establish_breakout(
        now=_NOW, session_id=live_sid,
        decision_ref=applied_local.value.decision_ref,
        path_ref=selected_path.path_id,
    )
    if not local.ok:
        return fail(name, "local (ip-seam) establish failed: %s" % local.detail)
    e_local = mgr.egress(
        now=_NOW, breakout_ref=local.value.breakout_ref,
        payload=b"coexist-local",
    )
    if not e_local.ok or e_local.value.locality != "local":
        return fail(name, "local (ip-seam) egress failed")
    if local_provider.delivered_total() != 1:
        return fail(name, "ip seam delivery accounting drifted")
    if remote_provider.delivered_total() != 0:
        return fail(name, "local traffic leaked to the 5GC seam")
    # A REMOTE breakout through the real 5GC seam SIMULTANEOUSLY
    # (5G UPF and generic IP gateway functions coexist behind
    # adapters).
    applied_remote = mgr.apply_policy_decision(
        now=_T1, session_id=live_sid,
        policy_decision=_allow_decision(evaluation_instant=_T1),
        mode=BreakoutMode.REMOTE,
    )
    remote = mgr.establish_breakout(
        now=_T1, session_id=live_sid,
        decision_ref=applied_remote.value.decision_ref,
        path_ref=_REMOTE_PATH.path_id,
    )
    if not remote.ok:
        return fail(name, "remote (fivegc-seam) establish failed: %s" % remote.detail)
    e_remote = mgr.egress(
        now=_T1, breakout_ref=remote.value.breakout_ref,
        payload=b"coexist-remote",
    )
    if not e_remote.ok or e_remote.value.locality != "remote":
        return fail(name, "remote (fivegc-seam) egress failed")
    if local_provider.delivered_total() != 1:
        return fail(name, "remote traffic leaked to the IP seam")

    # FAILOVER across the REAL seams: partition the IP seam, then
    # fail the local breakout over to the 5GC seam.  The session
    # identity (the W012-minted id) is preserved end-to-end.
    local_provider.partition()
    failed = mgr.egress(
        now=_T2, breakout_ref=local.value.breakout_ref, payload=b"x",
    )
    if failed.ok or failed.reason != DistCoreReasonCode.GATEWAY_UNAVAILABLE:
        return fail(name, "partitioned ip-seam egress: %s" % failed.reason)
    # Release the coexisting remote breakout first (the failover
    # targets IT after the local one is superseded).
    if not mgr.release_breakout(now=_T2, breakout_ref=remote.value.breakout_ref).ok:
        return fail(name, "coexisting remote release failed")
    failover = mgr.failover_binding(
        now=_T2, breakout_ref=local.value.breakout_ref,
        target_decision_ref=applied_remote.value.decision_ref,
        target_path_ref=_REMOTE_PATH.path_id,
    )
    if not failover.ok:
        return fail(name, "real-seam failover failed: %s" % failover.detail)
    new_binding = failover.value
    if new_binding.session_id != live_sid:
        return fail(name, "session identity changed across the real-seam failover")
    # Egress through the real 5GC seam with the SAME session.
    e_after = mgr.egress(
        now=_T2, breakout_ref=new_binding.breakout_ref,
        payload=b"post-failover-remote",
    )
    if not e_after.ok or e_after.value.locality != "remote":
        return fail(name, "post-failover egress failed")
    if e_after.value.session_id != live_sid:
        return fail(name, "post-failover egress lost the session identity")
    # The old ip-seam binding was closed by the failover's
    # post-commit cleanup (the real W018 manager holds no binding).
    if ip_manager.binding_for_session(live_sid) is not None:
        return fail(name, "the real IP binding was not closed by the failover")
    # The supersedes chain is recorded with both real seams.
    snapshot = mgr.snapshot()
    chain = {b["state"] for b in snapshot["breakouts"]}
    if chain != {"active", "superseded", "released"}:
        return fail(name, "chain states drifted: %s" % chain)
    # Recovery: restore the IP seam and fail BACK (both real seams
    # serve the same session across the whole journey).
    local_provider.restore()
    applied_back = mgr.apply_policy_decision(
        now=_T3, session_id=live_sid,
        policy_decision=_allow_decision(evaluation_instant=_T3),
        mode=BreakoutMode.LOCAL, locality_labels=(_LOCALITY,),
    )
    back = mgr.failover_binding(
        now=_T3, breakout_ref=new_binding.breakout_ref,
        target_decision_ref=applied_back.value.decision_ref,
        target_path_ref=selected_path.path_id,
    )
    if not back.ok:
        return fail(name, "real-seam recovery failover failed: %s" % back.detail)
    e_back = mgr.egress(
        now=_T3, breakout_ref=back.value.breakout_ref,
        payload=b"recovered-local",
    )
    if not e_back.ok or e_back.value.locality != "local":
        return fail(name, "recovered egress failed")
    if e_back.value.session_id != live_sid:
        return fail(name, "recovered egress lost the session identity")
    return ok(name, "REAL W018 + W019 seams coexist behind adapters; "
                    "failover across the real seams preserves the W012 "
                    "session identity end-to-end (partition -> remote -> "
                    "recovery -> local)")


# --------------------------------------------------------------------------
# Validate/commit sequence discipline (the PR #24 lesson, day one)
# --------------------------------------------------------------------------


class _OnceFailingCommitEngine(ReferenceIPGatewayEngine):
    """A probe whose COMMIT phase faults exactly once per faulting op
    (validation completed and derived a ref; the commit then faults)
    -- proving the nonce never advances on a commit-phase fault."""

    def __init__(self) -> None:
        super().__init__()
        self._fail_allocate_once = True
        self._fail_establish_once = True

    def _commit_allocate(self, allocation, candidate_sequence) -> None:
        if self._fail_allocate_once:
            self._fail_allocate_once = False
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "probe: commit-phase allocate fault",
            )
        super()._commit_allocate(allocation, candidate_sequence)

    def _commit_establish_breakout(self, binding, candidate_sequence) -> None:
        if self._fail_establish_once:
            self._fail_establish_once = False
            raise DistCoreError(
                DistCoreReasonCode.ILLEGAL_STATE,
                "probe: commit-phase establish fault",
            )
        super()._commit_establish_breakout(binding, candidate_sequence)


def case_40_validate_commit_sequence_discipline() -> Result:
    name = "case_40_validate_commit_sequence_discipline"

    def fresh_stack(engine_factory=None):
        engine = engine_factory() if engine_factory else ReferenceIPGatewayEngine()
        mgr = DistributedCoreManager(session_reader=_READER)
        mgr.register_provider(
            engine, label="provider",
            breakout_mode=BreakoutMode.LOCAL, now=_NOW,
        )
        mgr.register_gateway(
            now=_NOW, label="provider",
            descriptor=_LOCAL_DESCRIPTOR, evidence=_LOCAL_EVIDENCE,
        )
        mgr.register_path(now=_NOW, path=_LOCAL_PATH)
        return mgr, engine

    # -- leg 1: failed establish of several typed flavors leaves the
    #    canonical bytes AND the nonce untouched.
    mgr, engine = fresh_stack()
    decision = mgr.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
    )
    before_bytes = mgr.to_canonical_bytes()
    before_seq = engine._sequence  # noqa: SLF001
    # identity-smuggling requirements (caller-side guard).
    try:
        mgr.establish_breakout(
            now=_NOW, session_id=_SESSION_ID,
            decision_ref=decision.value.decision_ref,
            path_ref=_LOCAL_PATH.path_id,
            requirements={"session_id": _SESSION_ID},
        )
        return fail(name, "smuggled requirements accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ACCESS_SESSION_COLLAPSE:
            return fail(name, "smuggling mistyped")
    # unknown session (caller-side guard).
    try:
        mgr.establish_breakout(
            now=_NOW, session_id=_SESSION_ID_2,
            decision_ref=decision.value.decision_ref,
            path_ref=_LOCAL_PATH.path_id,
        )
        return fail(name, "unknown session accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.ACCESS_SESSION_COLLAPSE:
            return fail(name, "unknown session mistyped: %s" % exc.reason)
    # mode-mismatched path (caller-side guard: the remote path is NOT
    # registered on this stack -> PATH_UNKNOWN).
    try:
        mgr.establish_breakout(
            now=_NOW, session_id=_SESSION_ID,
            decision_ref=decision.value.decision_ref,
            path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "unregistered path accepted")
    except DistCoreError as exc:
        if exc.reason != DistCoreReasonCode.PATH_UNKNOWN:
            return fail(name, "unregistered path mistyped: %s" % exc.reason)
    # engine-side validate failure (bad payload on egress --
    # engine-side validate).
    b = mgr.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=decision.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if not b.ok:
        return fail(name, "clean establish failed: %s" % b.detail)
    if mgr.to_canonical_bytes() == before_bytes:
        return fail(name, "clean establish did not commit")
    before2 = mgr.to_canonical_bytes()
    bad = mgr.egress(now=_NOW, breakout_ref=b.value.breakout_ref, payload=b"")
    if bad.ok or bad.reason != DistCoreReasonCode.INVALID_INPUT:
        return fail(name, "empty payload not rejected")
    if mgr.to_canonical_bytes() != before2:
        return fail(name, "failed egress mutated canonical bytes")
    if engine._sequence != before_seq + 1:  # noqa: SLF001
        return fail(name, "unexpected nonce drift after clean establish")

    # -- leg 2: COMMIT-phase faults consume no derivation state.
    mgr_probe, probe = fresh_stack(_OnceFailingCommitEngine)
    decision_probe = mgr_probe.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
    )
    probe_before = mgr_probe.to_canonical_bytes()
    c1 = mgr_probe.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=decision_probe.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if c1.ok or c1.reason != DistCoreReasonCode.ILLEGAL_STATE:
        return fail(name, "commit-phase establish fault mistyped: %s" % c1.reason)
    a1 = mgr_probe.allocate(
        now=_NOW, kind="bandwidth", quantity_base=10, purpose="p",
    )
    if a1.ok or a1.reason != DistCoreReasonCode.ILLEGAL_STATE:
        return fail(name, "commit-phase allocate fault mistyped: %s" % a1.reason)
    if probe._sequence != 0:  # noqa: SLF001
        return fail(
            name,
            "commit-phase faults consumed derivation state: %r"
            % probe._sequence,  # noqa: SLF001
        )
    if mgr_probe.to_canonical_bytes() != probe_before:
        return fail(name, "commit-phase faults mutated canonical bytes")

    # -- leg 3: the counterfactual -- a failed operation never changes
    #    what the NEXT successful derived ref would have been (the
    #    snapshot-blind assertion: _sequence is NOT canonicalized).
    def clean_refs():
        mgr_c, engine_c = fresh_stack()
        d = mgr_c.apply_policy_decision(
            now=_NOW, session_id=_SESSION_ID,
            policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
        )
        refs = []
        refs.append(
            mgr_c.establish_breakout(
                now=_NOW, session_id=_SESSION_ID,
                decision_ref=d.value.decision_ref,
                path_ref=_LOCAL_PATH.path_id,
            ).value.breakout_ref
        )
        refs.append(
            mgr_c.allocate(
                now=_NOW, kind="bandwidth",
                quantity_base=100, purpose="reserve-a",
            ).value.allocation_ref
        )
        return mgr_c, engine_c, refs

    _, clean_engine, wanted = clean_refs()
    if clean_engine._sequence != 2:  # noqa: SLF001
        return fail(name, "clean-run sequence drift: %r" % clean_engine._sequence)  # noqa: SLF001

    mgr_p, probe_engine = fresh_stack(_OnceFailingCommitEngine)
    d_p = mgr_p.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=_allow_decision(), mode=BreakoutMode.LOCAL,
    )
    # validate-phase failure first (mode-mismatched path).
    try:
        mgr_p.establish_breakout(
            now=_NOW, session_id=_SESSION_ID,
            decision_ref=d_p.value.decision_ref,
            path_ref=_REMOTE_PATH.path_id,
        )
        return fail(name, "probe run: mismatched path accepted")
    except DistCoreError:
        pass
    # commit-phase failures (validation completed, commit faulted).
    cf1 = mgr_p.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=d_p.value.decision_ref,
        path_ref=_LOCAL_PATH.path_id,
    )
    if cf1.ok or cf1.reason != DistCoreReasonCode.ILLEGAL_STATE:
        return fail(name, "probe commit-phase establish mistyped: %s" % cf1.reason)
    ca1 = mgr_p.allocate(
        now=_NOW, kind="bandwidth", quantity_base=100,
        purpose="reserve-a",
    )
    if ca1.ok or ca1.reason != DistCoreReasonCode.ILLEGAL_STATE:
        return fail(name, "probe commit-phase allocate mistyped: %s" % ca1.reason)
    if probe_engine._sequence != 0:  # noqa: SLF001
        return fail(name, "probe faults consumed nonce: %r" % probe_engine._sequence)  # noqa: SLF001
    # The same successful sequence derives byte-identical refs.
    got = [
        mgr_p.establish_breakout(
            now=_NOW, session_id=_SESSION_ID,
            decision_ref=d_p.value.decision_ref,
            path_ref=_LOCAL_PATH.path_id,
        ).value.breakout_ref,
        mgr_p.allocate(
            now=_NOW, kind="bandwidth", quantity_base=100,
            purpose="reserve-a",
        ).value.allocation_ref,
    ]
    for i, (g, w) in enumerate(zip(got, wanted)):
        if g != w:
            return fail(
                name,
                "derived ref %d diverged after failed operations:\n  "
                "got    %s\n  wanted %s" % (i, g, w),
            )
    if probe_engine._sequence != 2:  # noqa: SLF001
        return fail(name, "probe-run sequence drift: %r" % probe_engine._sequence)  # noqa: SLF001
    # The UPF engine's monolithic nonce discipline: a failed
    # establish never consumes the nonce either.
    upf_mgr = DistributedCoreManager(session_reader=_READER)
    upf_engine = ReferenceUPFEngine()
    upf_mgr.register_provider(
        upf_engine, label="remote",
        breakout_mode=BreakoutMode.REMOTE, now=_NOW,
    )
    upf_mgr.register_gateway(
        now=_NOW, label="remote",
        descriptor=_REMOTE_DESCRIPTOR, evidence=_REMOTE_EVIDENCE,
    )
    upf_mgr.register_path(now=_NOW, path=_REMOTE_PATH)
    d_upf = upf_mgr.apply_policy_decision(
        now=_NOW, session_id=_SESSION_ID,
        policy_decision=_allow_decision(), mode=BreakoutMode.REMOTE,
    )
    # Partitioned anchor -> validate-phase failure, nonce untouched.
    upf_engine.set_anchor_state(
        derive_gateway_ref(
            _REMOTE_DESCRIPTOR.name, _REMOTE_DESCRIPTOR.gateway_id,
            _REMOTE_DESCRIPTOR.node_id, _REMOTE_DESCRIPTOR.role_class,
        ),
        up=False,
    )
    failed = upf_mgr.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=d_upf.value.decision_ref,
        path_ref=_REMOTE_PATH.path_id,
    )
    if failed.ok or failed.reason != DistCoreReasonCode.GATEWAY_UNAVAILABLE:
        return fail(name, "upf partitioned establish: %s" % failed.reason)
    if upf_engine._nonce != 0:  # noqa: SLF001
        return fail(name, "upf failed establish consumed the nonce")
    upf_engine.set_anchor_state(
        derive_gateway_ref(
            _REMOTE_DESCRIPTOR.name, _REMOTE_DESCRIPTOR.gateway_id,
            _REMOTE_DESCRIPTOR.node_id, _REMOTE_DESCRIPTOR.role_class,
        ),
        up=True,
    )
    good = upf_mgr.establish_breakout(
        now=_NOW, session_id=_SESSION_ID,
        decision_ref=d_upf.value.decision_ref,
        path_ref=_REMOTE_PATH.path_id,
    )
    if not good.ok:
        return fail(name, "upf post-failure establish failed")
    if upf_engine._nonce != 1:  # noqa: SLF001
        return fail(name, "upf nonce drift: %r" % upf_engine._nonce)  # noqa: SLF001
    return ok(
        name,
        "validate phases never mutate the derivation nonce: failed "
        "establishes/allocates (validate- and commit-phase failures "
        "alike) leave canonical bytes AND the nonce unchanged on BOTH "
        "engines, and the next successful derived refs are "
        "byte-identical to a clean twin run",
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    cases = [
        case_01_family_surface_frozen,
        case_02_context_least_authority,
        case_03_model_invariants,
        case_04_validation_vocabulary,
        case_05_provider_registration,
        case_06_gateway_evidence_fail_closed,
        case_07_policy_decision_verification,
        case_08_path_registration,
        case_09_local_breakout_establishment,
        case_10_remote_breakout_establishment,
        case_11_upf_ip_gateway_coexistence,
        case_12_local_traffic_stays_local,
        case_13_egress_data_path_fail_closed,
        case_14_latency_locality_determinism,
        case_15_policy_determines_breakout,
        case_16_session_identity_across_failover,
        case_17_remote_gateway_failover_partition,
        case_18_graceful_degradation_alternate_paths,
        case_19_partition_recovery,
        case_20_failover_validation_fail_closed,
        case_21_no_retroactive_rebinding_provider_swap,
        case_22_allocation_capacity_fail_closed,
        case_23_base_exception_isolation,
        case_24_contract_violations_discarded,
        case_25_budget_exhaustion,
        case_26_secret_isolation,
        case_27_canonical_state_shape,
        case_28_teardown_fail_closed,
        case_29_work016_sdk_bridge,
        case_30_standards_boundary_audit,
        case_31_no_core_leakage,
        case_32_determinism_repeated_runs,
        case_33_determinism_hash_seed,
        case_34_frozen_spec_intact,
        case_35_observation_honesty,
        case_36_cross_implementation_byte_identity,
        case_37_real_w018_ip_seam_local_breakout,
        case_38_real_w019_fivegc_remote_seam,
        case_39_real_seam_failover_and_coexistence,
        case_40_validate_commit_sequence_discipline,
    ]
    print("ADCOS distributed-core adapter self-test (WORK-024)")
    print("=" * 72)
    failures = 0
    for case in cases:
        try:
            name, passed, detail = case()
        except Exception as exc:  # noqa: BLE001
            name, passed, detail = case.__name__, False, "case raised %s: %s" % (
                type(exc).__name__, exc,
            )
        if not passed:
            failures += 1
        print("[%s] %-56s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 72)
    if failures:
        print("Result: FAIL (%d/%d cases)" % (len(cases) - failures, len(cases)))
        return 1
    print("Result: PASS (%d/%d cases)" % (len(cases), len(cases)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
