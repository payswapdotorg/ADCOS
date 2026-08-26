#!/usr/bin/env python3
"""ADCOS 5G RAN integration self-test (WORK-020).

Mirrors the WORK-018/019 selftest discipline: the frozen 14-op
contract surface, least-authority context, sandboxed boundary (budget
+ BaseException isolation + return-shape validation), gNB/cell
lifecycle with strict state transitions, radio-bearer binding with
manager-side opaque binding tokens, R1 session/bearer identity
separation, R2 credential/identifier isolation + RAN-unavailable
fail-closed, R3 AccessPathSession surface audit + leaky-session
rejection, R4 per-binding sandbox ownership across
register_implementation swaps, and honest health/resource/capability/
topology mapping as adapter DATA.

The full battery (32 cases) has two parts.  The deterministic
reference battery (cases 01-29) runs fully in-process against the
ReferenceRanEngine through the RanManager/SandboxedRan seam: no wall
clock, no randomness, no network -- every instant is injected, every
reference is content-derived, every assertion is honest (no faked
success).  Part 2 (W020-b2) extends it with the R5/R6
standards-boundary + frozen-spec-intact + no-core-RAN-leakage audits,
the WORK-016 SDK bridge (the sanctioned ``..contract`` import),
determinism (byte-identical snapshots + DIRECT cross-impl canonical
equality with implementation_label excluded), and failure isolation
(BaseException, contract violation, budget exhaustion, no secret leak
through diagnostics).

The B4 cases (30-32) are the real-peer and environment-gated legs:
case_30 proves bytes traverse the AccessPathSession -> RanManager ->
SandboxedRan -> OpenRanAdapter -> real REST-over-HTTP RAN
control-plane peer -> AccessPathSession.recv path over real loopback
sockets (two legs, the second through a register_implementation
swap); cases 31-32 are the environment-gated real-SDR-lab interop
gate: ``RAN_INTEROP=1`` with a real SDR-based lab
(OpenAirInterface/O-RAN style, ``RAN_PEER_KIND=real_oai`` +
``RAN_CONTROL_URL``) is the frozen WORK-020 acceptance path -- the
frozen SDR-lab criterion REQUIRES the external lab run (see the
RAN_INTEROP_RUNBOOK in adapters/ran/interop_env_probe.py).  When the
gate is disabled or the lab is unreachable those cases SKIP with a
transparent verification-environment disclosure and NEVER fake
success with the in-repo conformance peer.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import os
import re
import socket as _socket
import subprocess
import sys
from typing import Any, List, Mapping, Optional, Set, Tuple

# Make the repository root importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from adapters.ran import (  # noqa: E402
    RAN_CAPABILITY_CELL_TDD,
    RAN_CAPABILITY_CU_DU_SPLIT_F1,
    RAN_CAPABILITY_DRB_QOS_FLOW,
    RAN_CAPABILITY_GNB_PROVISION,
    RAN_CAPABILITY_O_RU_FRONTHAUL,
    RAN_CAPABILITY_REFERENCES,
    RAN_CONTRACT_OPERATIONS,
    RAN_CONTEXT_SURFACE,
    RAN_PREFIX,
    AccessPathSession,
    BearerView,
    CellSpec,
    CellState,
    CuElement,
    DuplexMode,
    DuElement,
    GnbProvisionRequest,
    GnbView,
    HealthState,
    LinkMetricName,
    OpenRanAdapter,
    RanContext,
    RanContract,
    RanEnvProbeConfig,
    RanError,
    RanInteropConfig,
    RanManager,
    RanObservation,
    RanReasonCode,
    RanSplitOption,
    RanSplitTopology,
    RanTechnologyAdapter,
    ReferenceRanConformanceServer,
    ReferenceRanEngine,
    RuElement,
    SandboxedRan,
    validate_opaque_ref,
    reject_credential_like_text,
    probe_ran_interop_capability,
    ran_interop_gate_enabled,
    run_openran_interop,
)
from adapters.ran.contract import _BudgetExhausted  # noqa: E402
from adapters.contract import (  # noqa: E402
    AdapterContext,
    AdapterContract,
    CONTRACT_OPERATIONS,
)

# --------------------------------------------------------------------------
# Deterministic module-level constants (no wall clock, no randomness)
# --------------------------------------------------------------------------

#: The canonical conformance payload (part 2 reuses it).
PAYLOAD = b"adcospktpath-ran-conformance-v1"

#: Fixed instants: ``_T(n)`` is the n-th minute after 12:00Z on the
#: fixed selftest date (every operation injects one; none reads a clock).
def _T(n: int) -> str:
    return "2026-06-01T%02d:%02d:00Z" % (12 + (n // 60), n % 60)


Result = Tuple[str, bool, str]


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# --------------------------------------------------------------------------
# Canonical fixtures (defined once; part 2 reuses them)
# --------------------------------------------------------------------------


def _canonical_gnb_request() -> GnbProvisionRequest:
    """The fixed canonical gNB provision request: one band-78 TDD cell
    (``c1``, numerology 1, NR-ARFCN 632628, 10 PRBs) carried on an F1
    CU/DU split (TS 38.401 section 5 / TS 38.473) with an O-RAN 7-2x open
    fronthaul RU (O-RAN.WG4) -- the WORK-020 reference lab shape."""
    return GnbProvisionRequest(
        gnb_name="lab-gnb-1",
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


def _alternate_gnb_request() -> GnbProvisionRequest:
    """A second, distinct canonical request (the R4 swap case provisions
    one gNB PER engine; identical content on two fresh engines would
    mint the same content-derived reference and collide in the
    manager's registry, so the second gNB honestly differs by name)."""
    request = _canonical_gnb_request()
    return GnbProvisionRequest(
        gnb_name="lab-gnb-2",
        cells=request.cells,
        topology=request.topology,
    )


def _new_manager(
    implementation: Optional[RanContract] = None,
    *,
    integration_id: str = "adcos:ran:test",
    label: str = "reference-ran-engine",
) -> RanManager:
    """A manager with the given implementation registered as DEFAULT
    (mirrors the fivegc ``_new_manager`` helper)."""
    mgr = RanManager(ran_integration_id=integration_id)
    if implementation is None:
        implementation = ReferenceRanEngine()
    r = mgr.register_implementation(implementation, label=label, make_default=True, now=_T(0))
    assert r.ok, "register_implementation failed: %s" % r.detail
    return mgr


def _fresh_manager(
    implementation: Optional[RanContract] = None,
    *,
    integration_id: str = "adcos:ran:test",
    label: str = "reference-ran-engine",
) -> Tuple[RanManager, str]:
    """A manager + registered DEFAULT ReferenceRanEngine with the
    canonical gNB provisioned and its cell ACTIVATED (the standard
    ready-to-bind state; returns ``(manager, gnb_ref)``)."""
    mgr = _new_manager(
        implementation, integration_id=integration_id, label=label
    )
    r = mgr.provision_gnb(now=_T(1), request=_canonical_gnb_request())
    assert r.ok, "provision_gnb failed: %s" % r.detail
    gnb_ref = str(r.value)
    r = mgr.activate_cell(now=_T(2), gnb_ref=gnb_ref, cell_id="c1")
    assert r.ok, "activate_cell failed: %s" % r.detail
    return mgr, gnb_ref


def _observe(mgr: RanManager, n: int) -> RanObservation:
    """The mediated observation through the DEFAULT sandbox (the
    manager has no observe convenience wrapper; the sandbox IS the
    mediated contract path -- the same seam every manager op uses)."""
    sandbox = mgr._default_sandbox
    assert sandbox is not None, "no default sandbox registered"
    r = sandbox.observe(_T(n))
    assert r.ok, "observe failed: %s" % r.detail
    return r.value  # type: ignore[no-any-return]


def _bind(mgr: RanManager, session_id: str, gnb_ref: str, n: int) -> str:
    """Bind a session and return the manager's opaque binding token."""
    r = mgr.bind_session(now=_T(n), session_id=session_id, gnb_ref=gnb_ref)
    assert r.ok, "bind_session failed: %s" % r.detail
    return str(r.value)


# --------------------------------------------------------------------------
# Test doubles (implement the same interfaces used by real adapters)
# --------------------------------------------------------------------------


class _CrossBindingImpl(ReferenceRanEngine):
    """A misbehaving implementation that returns the FIRST bearer
    reference for EVERY bind_session call (an implementation trying to
    collapse a second session onto another session's bearer -- the
    manager's cross-binding check must reject it; R1)."""

    label = "cross-binding-impl"

    def __init__(self) -> None:
        super().__init__()
        self._first_bearer_ref: Optional[str] = None

    def bind_session(
        self,
        context: RanContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> str:
        ref = super().bind_session(
            context, session_id=session_id, requirements=requirements
        )
        if self._first_bearer_ref is None:
            self._first_bearer_ref = ref
        # Every later session gets session-1's bearer reference back.
        return self._first_bearer_ref


class _LeakyAccessPathSession(AccessPathSession):
    """An AccessPathSession-shaped object that leaks RAN identifiers as
    public surface (a property returning the bearer ref and an added
    ``rnti()`` method -- the R3 leaky-session test double)."""

    @property
    def bearer_ref(self) -> str:
        return "ran:bearer:deadbeefdeadbeefdeadbeefdeadbeef"

    def rnti(self) -> int:
        return 0x4601


class _LeakySessionReturningImpl(ReferenceRanEngine):
    """An implementation that tries to smuggle a leaky session object
    through the bind_session seam (the sandbox must discard it --
    CONTRACT_VIOLATION, never stored, keyed, or echoed)."""

    label = "leaky-session-impl"

    def bind_session(
        self,
        context: RanContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> str:
        return _LeakyAccessPathSession()  # type: ignore[return-value]


# ==========================================================================
# Cases
# ==========================================================================


def case_01_contract_surface_frozen() -> Result:
    name = "case_01_contract_surface_frozen"
    ops = RAN_CONTRACT_OPERATIONS
    expected = (
        "open", "close", "capabilities", "observe", "provision_gnb",
        "decommission_gnb", "activate_cell", "deactivate_cell",
        "bind_session", "unbind_session", "egress_data", "allocate",
        "release", "health",
    )
    if ops != expected:
        return fail(name, "RAN_CONTRACT_OPERATIONS != frozen surface: %r" % (ops,))
    if RAN_CONTEXT_SURFACE != frozenset(
        {"ran_integration_id", "now", "charge", "steps_left"}
    ):
        return fail(name, "RAN_CONTEXT_SURFACE != 4-member facade")
    # Every frozen op is an abstractmethod on the contract ABC.
    abstract_ops = set(getattr(RanContract, "__abstractmethods__", frozenset()))
    if abstract_ops != set(expected):
        return fail(
            name,
            "contract abstractmethods != frozen surface: %r"
            % (sorted(abstract_ops),),
        )
    return ok(name, "14 engine ops; 4-member context surface")


def case_02_context_least_authority() -> Result:
    name = "case_02_context_least_authority"
    ctx = RanContext(
        ran_integration_id="adcos:ran:t", instant=_T(0), step_budget=10,
    )
    # Immutable.
    try:
        ctx.ran_integration_id = "x"  # type: ignore[misc]
        return fail(name, "context is mutable")
    except TypeError:
        pass
    # The 4-member surface; nothing else.
    surface = {a for a in dir(ctx) if not a.startswith("_")}
    if surface != set(RAN_CONTEXT_SURFACE):
        return fail(name, "context surface != RAN_CONTEXT_SURFACE: %r" % (sorted(surface),))
    # Structurally least-authority: only the three private slots exist.
    if getattr(RanContext, "__slots__", ()) != (
        "_ran_integration_id", "_instant", "_steps_left"
    ):
        return fail(name, "RanContext carries fields beyond the facade slots")
    # The context's module imports nothing from core domain modules
    # (no sessions/identity/policy/topology/... reachability).
    path = os.path.join(_ROOT, "adapters", "ran", "contract.py")
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    allowed_roots = {"__future__", "abc", "dataclasses", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in allowed_roots:
                    return fail(name, "contract.py imports %r (core reachability)" % root)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            root = (node.module or "").split(".")[0]
            if root not in allowed_roots:
                return fail(name, "contract.py imports %r (core reachability)" % root)
    return ok(name, "immutable 4-member facade; no core reachability")


def case_03_context_injected_instant_and_budget() -> Result:
    name = "case_03_context_injected_instant_and_budget"
    ctx = RanContext(
        ran_integration_id="adcos:ran:t", instant=_T(0), step_budget=2,
    )
    if ctx.now() != _T(0):
        return fail(name, "now() != injected instant")
    ctx.charge(1)
    if ctx.steps_left() != 1:
        return fail(name, "charge did not decrement budget")
    ctx.charge(1)
    if ctx.steps_left() != 0:
        return fail(name, "second charge did not decrement")
    # Budget exhaustion (hang model; no wall clock) raises the private
    # budget sentinel; so do negative/bool/non-int charges.
    for bad in (1, -1, True, "x", 1.5):
        try:
            ctx.charge(bad)  # type: ignore[arg-type]
            return fail(name, "charge(%r) did not raise _BudgetExhausted" % (bad,))
        except _BudgetExhausted:
            pass
    # The sandbox converts the sentinel into a BUDGET_EXHAUSTED failure
    # value (the hang model at the mediated seam).
    sandbox = SandboxedRan(
        ReferenceRanEngine(), ran_integration_id="adcos:ran:t"
    )
    r = sandbox.open(_T(0))
    if not r.ok:
        return fail(name, "sandbox open failed: %s" % r.detail)
    r = sandbox.bind_session(_T(1), session_id="sess-budget", step_budget=1)
    if r.ok:
        return fail(name, "tiny budget did not fail the bind")
    if r.reason != RanReasonCode.BUDGET_EXHAUSTED:
        return fail(name, "wrong reason: %s" % r.reason)
    if "hang" not in (r.detail or "").lower():
        return fail(name, "no hang model mentioned in failure detail")
    return ok(name, "injected instant + budget hang model; sentinel isolated as budget-exhausted")


def case_04_provision_gnb_happy() -> Result:
    name = "case_04_provision_gnb_happy"
    mgr = _new_manager()
    r = mgr.provision_gnb(now=_T(1), request=_canonical_gnb_request())
    if not r.ok:
        return fail(name, r.detail)
    gnb_ref = str(r.value)
    if not gnb_ref.startswith("ran:gnb:"):
        return fail(name, "gnb_ref not an opaque ran:gnb: reference")
    try:
        validate_opaque_ref(gnb_ref, prefix="gnb")
    except RanError as exc:
        return fail(name, "gnb_ref violates the frozen grammar: %s" % exc.reason_code)
    # Cells start INACTIVE (activation is a separate explicit step).
    obs = _observe(mgr, 2)
    if obs.health.cell_states != {"c1": CellState.INACTIVE}:
        return fail(name, "cells do not start INACTIVE: %r" % (obs.health.cell_states,))
    if obs.resources.prb_total != 0:
        return fail(name, "INACTIVE cell contributed PRB capacity")
    # The secret-free GnbView projection: the frozen field shape,
    # constructible purely from adapter DATA (no RNTI/DRB material).
    field_names = [f.name for f in dataclasses.fields(GnbView)]
    if field_names != [
        "gnb_ref", "gnb_name", "cell_count",
        "cu_element_id", "du_element_ids", "ru_element_ids",
    ]:
        return fail(name, "GnbView field shape changed: %r" % (field_names,))
    view = GnbView(
        gnb_ref=gnb_ref,
        gnb_name=_canonical_gnb_request().gnb_name,
        cell_count=len(obs.health.cell_states),
        cu_element_id=obs.topology.cu.element_id,
        du_element_ids=tuple(du.element_id for du in obs.topology.dus),
        ru_element_ids=tuple(ru.element_id for ru in obs.topology.rus),
    )
    if view.cell_count != 1 or view.cu_element_id != "cu-1":
        return fail(name, "GnbView projection not carried from adapter DATA")
    blob = repr(view).lower()
    for token in ("rnti", "drb", "qfi"):
        if token in blob:
            return fail(name, "RAN identifier material %r in GnbView" % token)
    return ok(name, "gNB provisioned; opaque ran:gnb: ref; cells INACTIVE; GnbView secret-free")


def case_05_cell_lifecycle_happy() -> Result:
    name = "case_05_cell_lifecycle_happy"
    mgr = _new_manager()
    r = mgr.provision_gnb(now=_T(1), request=_canonical_gnb_request())
    gnb_ref = str(r.value)
    # Activate -> ACTIVE, observable, carrying PRB capacity.
    r = mgr.activate_cell(now=_T(2), gnb_ref=gnb_ref, cell_id="c1")
    if not r.ok:
        return fail(name, r.detail)
    obs = _observe(mgr, 3)
    if obs.health.cell_states.get("c1") != CellState.ACTIVE:
        return fail(name, "cell not ACTIVE after activate")
    if obs.resources.prb_total != 10:
        return fail(name, "prb_total != 10 after activation: %d" % obs.resources.prb_total)
    # Double-activate is rejected (honest strictness, not idempotence).
    r = mgr.activate_cell(now=_T(4), gnb_ref=gnb_ref, cell_id="c1")
    if r.ok or r.reason != RanReasonCode.INVALID_INPUT:
        return fail(name, "double activate not rejected invalid-input: %s" % r.reason)
    # Deactivate -> INACTIVE; PRB totals track ACTIVE cells only.
    r = mgr.deactivate_cell(now=_T(5), gnb_ref=gnb_ref, cell_id="c1")
    if not r.ok:
        return fail(name, r.detail)
    obs = _observe(mgr, 6)
    if obs.health.cell_states.get("c1") != CellState.INACTIVE:
        return fail(name, "cell not INACTIVE after deactivate")
    if obs.resources.prb_total != 0:
        return fail(name, "prb_total != 0 after deactivation: %d" % obs.resources.prb_total)
    return ok(name, "activate/deactivate mirror; double-activate rejected invalid-input; prb_total tracks ACTIVE cells (10 -> 0)")


def case_06_bind_session_happy() -> Result:
    name = "case_06_bind_session_happy"
    mgr, gnb_ref = _fresh_manager()
    token = _bind(mgr, "sess-alpha", gnb_ref, 3)
    if not token.startswith("%s:binding:" % RAN_PREFIX):
        return fail(name, "binding token not in the adcos:ran:binding: space")
    record = mgr._bindings[token]
    bearer_ref = record.bearer_ref
    if not bearer_ref.startswith("ran:bearer:"):
        return fail(name, "bearer_ref not an opaque ran:bearer: reference")
    try:
        validate_opaque_ref(bearer_ref, prefix="bearer")
    except RanError as exc:
        return fail(name, "bearer_ref violates the frozen grammar: %s" % exc.reason_code)
    # The ref does NOT embed the session id (R1, green path).
    if "sess-alpha" in bearer_ref:
        return fail(name, "bearer_ref embeds the session id (R1)")
    # Manager indirection: the caller's token is NOT the raw bearer ref.
    if token == bearer_ref:
        return fail(name, "binding token collapsed onto the raw bearer ref")
    # The secret-free BearerView projection: the frozen field shape,
    # session_id stored EXACTLY as provided.
    field_names = [f.name for f in dataclasses.fields(BearerView)]
    if field_names != ["bearer_ref", "session_id"]:
        return fail(name, "BearerView field shape changed: %r" % (field_names,))
    view = BearerView(bearer_ref=bearer_ref, session_id="sess-alpha")
    if view.session_id != "sess-alpha":
        return fail(name, "BearerView session_id not carried exactly")
    return ok(name, "bearer ref ran:bearer:<hex> (no session material); manager token adcos:ran:binding:<hex> (indirection)")


def case_07_egress_data_happy() -> Result:
    name = "case_07_egress_data_happy"
    mgr, gnb_ref = _fresh_manager()
    token = _bind(mgr, "sess-alpha", gnb_ref, 3)
    r = mgr.egress_data(now=_T(4), binding_ref=token, payload=PAYLOAD)
    if not r.ok:
        return fail(name, r.detail)
    if r.value != PAYLOAD:
        return fail(name, "egress_data did not return the carried payload")
    # Determinism: a second call returns the same bytes.
    r2 = mgr.egress_data(now=_T(5), binding_ref=token, payload=PAYLOAD)
    if not r2.ok or r2.value != r.value:
        return fail(name, "egress_data not deterministic across calls")
    return ok(name, "egress returns bytes; payload carried byte-identical (deterministic)")


def case_08_access_path_facade_happy() -> Result:
    name = "case_08_access_path_facade_happy"
    mgr, gnb_ref = _fresh_manager()
    r = mgr.access_path_session(now=_T(3), session_id="sess-alpha")
    if not r.ok:
        return fail(name, r.detail)
    sess = r.value
    if not isinstance(sess, AccessPathSession):
        return fail(name, "not an AccessPathSession")
    sess.connect("internet")
    sent = sess.send(PAYLOAD)
    if sent != len(PAYLOAD):
        return fail(name, "send returned wrong length")
    echo = sess.recv()
    if echo != PAYLOAD:
        return fail(name, "recv() != payload byte-identical: %r" % (echo,))
    # Closed sessions fail closed.
    sess.close()
    try:
        sess.send(b"x")
        return fail(name, "closed session did not fail closed")
    except RanError:
        pass
    return ok(name, "AccessPathSession connect/send/recv/close; recv() byte-identical; closed session fails closed")


def case_09_topology_mapping() -> Result:
    name = "case_09_topology_mapping"
    mgr, gnb_ref = _fresh_manager()
    _bind(mgr, "sess-alpha", gnb_ref, 3)
    obs = _observe(mgr, 4)
    topology = obs.topology
    # The CU/DU/RU boundary mapping is adapter DATA on the observation.
    if topology.cu.split != RanSplitOption.F1_CU_DU:
        return fail(name, "cu split != f1-cu-du")
    if not topology.dus or topology.dus[0].cell_ids != ("c1",):
        return fail(name, "du does not cover the served cell")
    if not topology.rus or topology.rus[0].split != RanSplitOption.O_RAN_7_2X:
        return fail(name, "ru split != o-ran-7-2x")
    if topology.rus[0].band != 78:
        return fail(name, "ru band not carried")
    # Element identities are OPAQUE adapter-side strings: no session
    # material, no core NodeID shape.
    elements = (topology.cu, *topology.dus, *topology.rus)
    for element in elements:
        if not element.element_id or "sess-alpha" in element.element_id:
            return fail(name, "topology element id not opaque: %r" % element.element_id)
        if "adcos:node:" in element.element_id:
            return fail(name, "topology element id carries a core NodeID shape")
    # The canonical fixture shape round-trips as DATA.
    if topology.to_dict() != _canonical_gnb_request().topology.to_dict():
        return fail(name, "observed topology != canonical fixture topology")
    return ok(name, "CU/DU/RU carried as adapter DATA (f1-cu-du + o-ran-7-2x, DU serves c1); element ids opaque")


def case_10_capability_mapping() -> Result:
    name = "case_10_capability_mapping"
    # Not open -> no capabilities at all.
    if ReferenceRanEngine().capabilities() != ():
        return fail(name, "capabilities not empty before open")
    impl = ReferenceRanEngine()
    sandbox = SandboxedRan(impl, ran_integration_id="adcos:ran:cap")
    if not sandbox.open(_T(0)).ok:
        return fail(name, "sandbox open failed")
    caps_open = sandbox.capabilities().value
    if tuple(caps_open) != (RAN_CAPABILITY_GNB_PROVISION,):
        return fail(name, "capabilities after open != (gnb-provision,): %r" % (caps_open,))
    r = sandbox.provision_gnb(_T(1), request=_canonical_gnb_request())
    if not r.ok:
        return fail(name, r.detail)
    gnb_ref = str(r.value)
    caps_provisioned = tuple(sandbox.capabilities().value)
    for expected in (RAN_CAPABILITY_CU_DU_SPLIT_F1, RAN_CAPABILITY_O_RU_FRONTHAUL):
        if expected not in caps_provisioned:
            return fail(name, "split capability %r missing after provisioning" % expected)
    if not sandbox.activate_cell(_T(2), gnb_ref=gnb_ref, cell_id="c1").ok:
        return fail(name, "activate failed")
    caps_active = tuple(sandbox.capabilities().value)
    if RAN_CAPABILITY_CELL_TDD not in caps_active:
        return fail(name, "cell-tdd capability missing after ACTIVE TDD cell")
    if not sandbox.bind_session(_T(3), session_id="sess-cap").ok:
        return fail(name, "bind failed")
    caps_bound = tuple(sandbox.capabilities().value)
    if RAN_CAPABILITY_DRB_QOS_FLOW not in caps_bound:
        return fail(name, "drb-qos-flow capability missing after live bearer")
    # All references in the reserved namespace, all drawn from the
    # known catalog (exposure by reference -- never minted).
    catalog = set(RAN_CAPABILITY_REFERENCES)
    for caps in (caps_open, caps_provisioned, caps_active, caps_bound):
        for capability in caps:
            if not capability.startswith("capability.access.ran."):
                return fail(name, "capability outside the ran namespace: %r" % capability)
            if capability not in catalog:
                return fail(name, "capability minted outside the known catalog: %r" % capability)
    # observe() reports the same references.
    r = sandbox.observe(_T(4))
    if not r.ok or tuple(r.value.capabilities) != caps_bound:
        return fail(name, "observe capabilities != capabilities()")
    return ok(name, "capability ladder: () closed -> gnb-provision open -> +splits provisioned -> +cell-tdd active -> +drb-qos-flow bound; references only, subset of catalog")


def case_11_health_mapping() -> Result:
    name = "case_11_health_mapping"
    mgr, gnb_ref = _fresh_manager()
    token = _bind(mgr, "sess-h", gnb_ref, 3)
    # All up (ACTIVE cell, healthy elements, bearer served) -> HEALTHY.
    obs = _observe(mgr, 4)
    if obs.health.aggregate() != HealthState.HEALTHY:
        return fail(name, "aggregate != HEALTHY with everything up: %s" % obs.health.aggregate())
    if mgr.health(now=_T(5)).value != HealthState.HEALTHY:
        return fail(name, "health() does not mirror the aggregate")
    # Deactivating the cell under a live bearer DEGRADES (documented
    # engine choice): the bearer is degraded, NOT killed.
    if not mgr.deactivate_cell(now=_T(6), gnb_ref=gnb_ref, cell_id="c1").ok:
        return fail(name, "deactivate failed")
    obs = _observe(mgr, 7)
    if obs.health.aggregate() != HealthState.DEGRADED:
        return fail(name, "aggregate != DEGRADED under live bearer on INACTIVE cell")
    if obs.health.cell_states.get("c1") != CellState.INACTIVE:
        return fail(name, "cell not INACTIVE after deactivate")
    if obs.resources.rrc_connected_ue_count != 1:
        return fail(name, "bearer was killed by deactivation (not degraded)")
    if mgr.health(now=_T(8)).value != HealthState.DEGRADED:
        return fail(name, "health() does not mirror the DEGRADED aggregate")
    # Close -> FAILED/NOT_RUNNING per engine semantics.
    if not mgr.unbind_session(now=_T(9), binding_ref=token).ok:
        return fail(name, "unbind failed")
    sandbox = mgr._default_sandbox
    assert sandbox is not None
    if not sandbox.close(_T(10)).ok:
        return fail(name, "sandbox close failed")
    if mgr.health(now=_T(11)).value != HealthState.FAILED:
        return fail(name, "engine health != FAILED after close")
    if sandbox.computed_health() != "NOT_RUNNING":
        return fail(name, "sandbox computed_health != NOT_RUNNING after close")
    if ReferenceRanEngine().health() != HealthState.FAILED:
        return fail(name, "bare engine health != FAILED when not open")
    return ok(name, "HEALTHY all-up; deactivate under live bearer -> DEGRADED (bearer alive); health() mirrors; closed -> FAILED/NOT_RUNNING")


def case_12_resource_mapping() -> Result:
    name = "case_12_resource_mapping"
    mgr, gnb_ref = _fresh_manager()
    obs = _observe(mgr, 3)
    if obs.resources.prb_total != 10 or obs.resources.prb_used != 0:
        return fail(name, "baseline resources wrong: %r" % (obs.resources,))
    if obs.resources.rrc_connected_ue_count != 0 or obs.resources.active_drb_count != 0:
        return fail(name, "baseline UE/DRB counts nonzero")
    token_a = _bind(mgr, "sess-a", gnb_ref, 4)
    obs = _observe(mgr, 5)
    if obs.resources.prb_used != 1 or obs.resources.rrc_connected_ue_count != 1 or obs.resources.active_drb_count != 1:
        return fail(name, "one bearer did not map to 1 PRB / 1 UE / 1 DRB: %r" % (obs.resources,))
    token_b = _bind(mgr, "sess-b", gnb_ref, 6)
    obs = _observe(mgr, 7)
    if obs.resources.prb_used != 2 or obs.resources.rrc_connected_ue_count != 2 or obs.resources.active_drb_count != 2:
        return fail(name, "two bearers did not map to 2 PRB / 2 UE / 2 DRB: %r" % (obs.resources,))
    # Unbind releases (integer accounting only).
    if not mgr.unbind_session(now=_T(8), binding_ref=token_a).ok:
        return fail(name, "unbind failed")
    obs = _observe(mgr, 9)
    if obs.resources.prb_used != 1 or obs.resources.rrc_connected_ue_count != 1 or obs.resources.active_drb_count != 1:
        return fail(name, "unbind did not release the reservation: %r" % (obs.resources,))
    # Deactivating the cell parks the reservation (no active capacity).
    if not mgr.deactivate_cell(now=_T(10), gnb_ref=gnb_ref, cell_id="c1").ok:
        return fail(name, "deactivate failed")
    obs = _observe(mgr, 11)
    if obs.resources.prb_total != 0 or obs.resources.prb_used != 0:
        return fail(name, "INACTIVE cell did not park PRB accounting: %r" % (obs.resources,))
    if obs.resources.rrc_connected_ue_count != 1:
        return fail(name, "live bearer disappeared from UE accounting")
    if token_b not in mgr._bindings:
        return fail(name, "surviving binding lost from the registry")
    return ok(name, "prb_total=ACTIVE cells; prb_used/rrc/drb track live bearers (0->1->2->1); unbind releases; INACTIVE parks")


def case_13_r1_session_ran_identity_separation_green() -> Result:
    name = "case_13_r1_session_ran_identity_separation_green"
    mgr, gnb_ref = _fresh_manager()
    token = _bind(mgr, "sess-alpha", gnb_ref, 3)
    record = mgr._bindings[token]
    # session_id stored byte-identical (snapshot shows the exact string).
    if record.session_id != "sess-alpha":
        return fail(name, "session_id not stored exactly")
    canonical = mgr.to_canonical_bytes()
    if b'"sess-alpha"' not in canonical:
        return fail(name, "session_id not byte-identical in canonical snapshot")
    bearer_ref = record.bearer_ref
    # Distinct identity spaces: no substring either way, no digest
    # equality (the ref is not a trivial re-encoding of session_id).
    if "sess-alpha" in bearer_ref or bearer_ref in "sess-alpha":
        return fail(name, "bearer_ref and session_id embed each other (R1)")
    digest = hashlib.sha256(b"sess-alpha").hexdigest()
    if digest in bearer_ref:
        return fail(name, "bearer_ref carries the session_id digest (R1)")
    # Two sessions on the same gNB coexist with distinct refs/tokens.
    token_b = _bind(mgr, "sess-beta", gnb_ref, 4)
    record_b = mgr._bindings[token_b]
    if token_b == token or record_b.bearer_ref == bearer_ref:
        return fail(name, "two sessions share a ref/token")
    if mgr.binding_count != 2:
        return fail(name, "two bound sessions do not coexist")
    return ok(name, "session_id byte-identical; bearer/token distinct identity (no substring, no digest); two sessions coexist")


def case_14_r1_session_ran_collapse_rejected() -> Result:
    name = "case_14_r1_session_ran_collapse_rejected"
    mgr, gnb_ref = _fresh_manager()
    # Requirements-map smuggling of identity keys -> RAN_SESSION_COLLAPSE.
    for key in ("session_id", "session", "bearer_ref", "binding_ref"):
        try:
            mgr.bind_session(
                now=_T(3), session_id="sess-x", gnb_ref=gnb_ref,
                requirements={key: "smuggled"},
            )
            return fail(name, "requirements key %r was not rejected" % key)
        except RanError as exc:
            if exc.reason_code != RanReasonCode.RAN_SESSION_COLLAPSE:
                return fail(name, "requirements key %r wrong reason: %s" % (key, exc.reason_code))
    # An implementation returning a bearer ref already bound to a
    # DIFFERENT session -> RAN_SESSION_COLLAPSE (manager cross-check).
    mgr2, gnb2 = _fresh_manager(
        _CrossBindingImpl(), integration_id="adcos:ran:collapse", label="cross"
    )
    _bind(mgr2, "sess-a", gnb2, 3)
    try:
        mgr2.bind_session(now=_T(4), session_id="sess-b", gnb_ref=gnb2)
        return fail(name, "cross-bound bearer ref was not rejected")
    except RanError as exc:
        if exc.reason_code != RanReasonCode.RAN_SESSION_COLLAPSE:
            return fail(name, "cross-binding wrong reason: %s" % exc.reason_code)
    if mgr2.binding_count != 1:
        return fail(name, "bogus second binding was registered")
    return ok(name, "requirements-key smuggling -> ran-session-collapse (4 keys); cross-binding impl bearer reuse -> ran-session-collapse; not registered")


def case_15_r2_identifier_and_credential_isolation() -> Result:
    name = "case_15_r2_identifier_and_credential_isolation"
    mgr, gnb_ref = _fresh_manager()
    token = _bind(mgr, "sess-alpha", gnb_ref, 3)
    record = mgr._bindings[token]
    # Real refs carry no key-like tokens (the LOCK-023 scan passes).
    for ref in (record.bearer_ref, record.gnb_ref, token):
        try:
            reject_credential_like_text(ref, what="ref")
        except RanError as exc:
            return fail(name, "honest ref rejected by the LOCK-023 scan: %s" % exc.reason_code)
    # Secret-like refs ARE rejected by the validator (called directly).
    for evil in ("ran:bearer:0000secret_key00000000000000000000",
                 "ran:gnb:0000000000password0000000000000000",
                 "ran:bearer:0000000000000000000000000token0"):
        try:
            reject_credential_like_text(evil, what="ref")
            return fail(name, "secret-like ref %r not rejected" % evil)
        except RanError:
            pass
    # RanUeContext/RNTI/DRB data NEVER appears in the manager snapshot
    # or the binding records (recursive key walk + text scan).
    snap = mgr.snapshot()

    def _walk(value: Any, seen: Set[int]) -> List[str]:
        keys: List[str] = []
        if id(value) in seen:
            return keys
        seen.add(id(value))
        if isinstance(value, Mapping):
            for key in value.keys():
                keys.append(str(key))
                keys.extend(_walk(value[key], seen))
        elif isinstance(value, (list, tuple)):
            for item in value:
                keys.extend(_walk(item, seen))
        return keys

    forbidden_keys = {"rnti", "drb", "drbs", "drb_id", "qfi", "ue_ref", "ue_context"}
    for key in _walk(snap, set()):
        if key.lower() in forbidden_keys:
            return fail(name, "RAN identifier key %r in manager snapshot" % key)
    blob = repr(snap) + repr(record.to_public_dict())
    for token_text in ("rnti", "drb", "ue_ref", "ue_context"):
        if token_text in blob.lower():
            return fail(name, "RAN identifier material %r in public state" % token_text)
    return ok(name, "refs pass the LOCK-023 scan; secret-like refs rejected; no rnti/drb/ue keys in snapshot or binding records")


def case_16_r2_ran_unavailable_fail_closed() -> Result:
    name = "case_16_r2_ran_unavailable_fail_closed"
    # No implementation registered -> every op fails closed.
    mgr = RanManager(ran_integration_id="adcos:ran:none")
    try:
        mgr.provision_gnb(now=_T(0), request=_canonical_gnb_request())
        return fail(name, "provision did not fail closed with RAN_UNAVAILABLE")
    except RanError as exc:
        if exc.reason_code != RanReasonCode.RAN_UNAVAILABLE:
            return fail(name, "provision wrong reason: %s" % exc.reason_code)
    try:
        mgr.bind_session(
            now=_T(1), session_id="sess-x",
            gnb_ref="ran:gnb:00000000000000000000000000000000",
        )
        return fail(name, "bind did not fail closed with RAN_UNAVAILABLE")
    except RanError as exc:
        if exc.reason_code != RanReasonCode.RAN_UNAVAILABLE:
            return fail(name, "bind wrong reason: %s" % exc.reason_code)
    try:
        mgr.allocate(now=_T(2), kind="ran.prb", quantity_base=1, purpose="p")
        return fail(name, "allocate did not fail closed with RAN_UNAVAILABLE")
    except RanError as exc:
        if exc.reason_code != RanReasonCode.RAN_UNAVAILABLE:
            return fail(name, "allocate wrong reason: %s" % exc.reason_code)
    # Bind with no gNB: the honest reason is GNB_UNKNOWN (the manager's
    # provisioning records AND the engine's own state both say so).
    mgr2 = _new_manager()
    try:
        mgr2.bind_session(
            now=_T(3), session_id="sess-x",
            gnb_ref="ran:gnb:00000000000000000000000000000000",
        )
        return fail(name, "bind with unknown gNB did not fail closed")
    except RanError as exc:
        if exc.reason_code != RanReasonCode.GNB_UNKNOWN:
            return fail(name, "unknown-gnb bind wrong reason: %s" % exc.reason_code)
    sandbox = SandboxedRan(
        ReferenceRanEngine(), ran_integration_id="adcos:ran:nog"
    )
    if not sandbox.open(_T(0)).ok:
        return fail(name, "sandbox open failed")
    r = sandbox.bind_session(_T(1), session_id="sess-x")
    if r.ok or r.reason != RanReasonCode.GNB_UNKNOWN:
        return fail(name, "engine-side no-gNB bind wrong reason: %s" % r.reason)
    # Egress on a deactivated cell -> RAN_UNAVAILABLE (degrade, then
    # fail closed until reactivation).
    mgr3, gnb_ref = _fresh_manager()
    token = _bind(mgr3, "sess-x", gnb_ref, 3)
    if not mgr3.deactivate_cell(now=_T(4), gnb_ref=gnb_ref, cell_id="c1").ok:
        return fail(name, "deactivate failed")
    r = mgr3.egress_data(now=_T(5), binding_ref=token, payload=b"x")
    if r.ok or r.reason != RanReasonCode.RAN_UNAVAILABLE:
        return fail(name, "egress on deactivated cell wrong reason: %s" % r.reason)
    return ok(name, "no impl -> ran-unavailable; bind with no gNB -> gnb-unknown (manager + engine); egress on deactivated cell -> ran-unavailable")


def case_17_r3_facade_surface_audited() -> Result:
    name = "case_17_r3_facade_surface_audited"
    path = os.path.join(_ROOT, "adapters", "ran", "session.py")
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    public_methods: Set[str] = set()
    # Signature-level tokens (names/parameters/annotations): nothing
    # technology-shaped at all.
    signature_tokens = (
        "adcos", "3gpp", "ran", "5g", "rnti", "drb", "gnb", "bearer",
        "cell", "session_id",
    )
    # Docstring-level tokens: RAN IDENTIFIERS must never appear (prose
    # may honestly disclose the standards vocabulary, not identifiers).
    identifier_tokens = (
        "session_id", "rnti", "drb", "cell_id", "gnb_ref", "bearer_ref",
        "adcos",
    )
    neutral_params = {"self", "destination", "payload"}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "AccessPathSession"):
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = [a.arg for a in item.args.args]
            params = set(args) | {a.arg for a in item.args.kwonlyargs}
            if item.name.startswith("_"):
                # Private hooks/constructor: parameters stay neutral too.
                if not params <= (neutral_params | {"now", "manager", "binding_ref", "data"}):
                    return fail(name, "non-neutral private parameter in %s" % item.name)
                continue
            public_methods.add(item.name)
            if not params <= neutral_params:
                return fail(name, "non-neutral parameter in %s: %r" % (item.name, sorted(params)))
            signature_bits: List[str] = [item.name, " ".join(args)]
            for annotation in [a.annotation for a in item.args.args]:
                if annotation is not None:
                    signature_bits.append(ast.unparse(annotation))
            if item.returns is not None:
                signature_bits.append(ast.unparse(item.returns))
            signature = " ".join(signature_bits).lower()
            for tok in signature_tokens:
                if tok in signature:
                    return fail(name, "token %r in AccessPathSession.%s signature" % (tok, item.name))
            doc = (ast.get_docstring(item) or "").lower()
            for tok in identifier_tokens:
                if tok in doc:
                    return fail(name, "identifier token %r in AccessPathSession.%s docstring" % (tok, item.name))
    if public_methods != {"connect", "send", "recv", "close"}:
        return fail(name, "public surface != {connect,send,recv,close}: %r" % (sorted(public_methods),))
    # Live surface audit: a manager-minted session exposes exactly the
    # four methods (no public attribute at all).
    mgr, gnb_ref = _fresh_manager()
    sess = mgr.access_path_session(now=_T(3), session_id="sess-a").value
    live_surface = {m for m in dir(sess) if not m.startswith("_")}
    if live_surface != {"connect", "send", "recv", "close"}:
        return fail(name, "live public surface != 4 methods: %r" % (sorted(live_surface),))
    return ok(name, "public surface connect/send/recv/close; technology-neutral parameters; no ADCOS/RAN identifier tokens in signatures or docstrings")


def case_18_r3_leaky_session_rejected() -> Result:
    name = "case_18_r3_leaky_session_rejected"
    # The RAN facade is MINTED by the manager (the contract has no
    # session-returning op), so the fivegc app_session seam guard has
    # no direct analog; the equivalent guard that DOES exist is the
    # sandbox's contract-shape path: a leaky session object returned
    # through ANY seam op is a CONTRACT_VIOLATION and is discarded.
    leaky = _LeakyAccessPathSession()
    leaky_surface = {m for m in dir(leaky) if not m.startswith("_")}
    if not {"bearer_ref", "rnti"} <= leaky_surface:
        return fail(name, "test double is not actually leaky")
    sandbox = SandboxedRan(
        _LeakySessionReturningImpl(), ran_integration_id="adcos:ran:leak"
    )
    if not sandbox.open(_T(0)).ok:
        return fail(name, "sandbox open failed")
    r = sandbox.bind_session(_T(1), session_id="sess-leak")
    if r.ok:
        return fail(name, "leaky session object was NOT rejected at the seam")
    if r.reason != RanReasonCode.CONTRACT_VIOLATION:
        return fail(name, "wrong reason: %s" % r.reason)
    if r.value is not None:
        return fail(name, "non-contract value was returned (not discarded)")
    # Through the manager, the bogus binding is never registered.
    mgr, gnb_ref = _fresh_manager(
        _LeakySessionReturningImpl(),
        integration_id="adcos:ran:leak2", label="leaky",
    )
    r = mgr.bind_session(now=_T(3), session_id="sess-leak", gnb_ref=gnb_ref)
    if r.ok or mgr.binding_count != 0:
        return fail(name, "leaky-session binding was registered")
    return ok(name, "leaky session rejected at the sandbox contract-shape seam (contract-violation, value discarded); facade is manager-minted so no impl-supplied session can cross")


def case_19_r4_default_swap_preserves_live_binding() -> Result:
    name = "case_19_r4_default_swap_preserves_live_binding"
    mgr = RanManager(ran_integration_id="adcos:ran:r4")
    if not mgr.register_implementation(
        ReferenceRanEngine(), label="engine-one", make_default=True, now=_T(0)
    ).ok:
        return fail(name, "register engine-one failed")
    r = mgr.provision_gnb(now=_T(1), request=_canonical_gnb_request())
    if not r.ok:
        return fail(name, r.detail)
    gnb_one = str(r.value)
    if not mgr.activate_cell(now=_T(2), gnb_ref=gnb_one, cell_id="c1").ok:
        return fail(name, "activate on engine-one failed")
    token_a = _bind(mgr, "sess-r4-a", gnb_one, 3)
    # Swap the DEFAULT implementation.
    if not mgr.register_implementation(
        ReferenceRanEngine(), label="engine-two", make_default=True, now=_T(4)
    ).ok:
        return fail(name, "register engine-two failed")
    # The existing binding still egresses via engine-1, byte-identical.
    r = mgr.egress_data(now=_T(5), binding_ref=token_a, payload=PAYLOAD)
    if not r.ok or r.value != PAYLOAD:
        return fail(name, "live binding did not survive the default swap")
    record_a = mgr._bindings[token_a]
    if record_a.sandbox is mgr._default_sandbox:
        return fail(name, "binding A migrated to the new sandbox (R4 violation)")
    # New work goes to engine-2 (a new gNB provisioned on the new
    # default; its binding's owning sandbox IS the new default).
    r = mgr.provision_gnb(now=_T(6), request=_alternate_gnb_request())
    if not r.ok:
        return fail(name, r.detail)
    gnb_two = str(r.value)
    if gnb_two == gnb_one:
        return fail(name, "second provision collided with the first gNB ref")
    if not mgr.activate_cell(now=_T(7), gnb_ref=gnb_two, cell_id="c1").ok:
        return fail(name, "activate on engine-two failed")
    token_b = _bind(mgr, "sess-r4-b", gnb_two, 8)
    if token_b == token_a:
        return fail(name, "binding B shares A's token")
    record_b = mgr._bindings[token_b]
    if record_b.sandbox is not mgr._default_sandbox:
        return fail(name, "binding B did not go to the new default")
    # Decommissioning engine-1's gNB routes to the OWNING sandbox: it
    # fails closed with binding-exists while A's bearer is live (an
    # engine-2 routing would say gnb-unknown), then succeeds after the
    # unbind -- the honest documented behavior.
    r = mgr.decommission_gnb(now=_T(9), gnb_ref=gnb_one)
    if r.ok or r.reason != RanReasonCode.BINDING_EXISTS:
        return fail(name, "decommission under live bearer wrong reason: %s" % r.reason)
    if not mgr.unbind_session(now=_T(10), binding_ref=token_a).ok:
        return fail(name, "unbind A failed")
    if not mgr.decommission_gnb(now=_T(11), gnb_ref=gnb_one).ok:
        return fail(name, "decommission after unbind failed")
    return ok(name, "A keeps engine-1 (egress byte-identical after swap); B on engine-2; gNB-A decommission routes to owner (binding-exists under live bearer, ok after unbind)")


# ==========================================================================
# Part 2 (W020-b2): test doubles for the failure-isolation cases
# ==========================================================================


class _CrashingRanImpl(ReferenceRanEngine):
    """An implementation that raises SystemExit mid-op (failure
    isolation: BaseException never propagates out of the seam)."""

    label = "crashing-ran-impl"

    def provision_gnb(
        self, context: RanContext, *, request: GnbProvisionRequest
    ) -> str:
        raise SystemExit("vendor RAN SDK crashed")


class _ContractViolatingRanImpl(ReferenceRanEngine):
    """An implementation whose bind_session returns the session_id
    itself (a non-contract value: not an opaque ran:bearer: ref -- the
    sandbox must discard it)."""

    label = "contract-violating-ran-impl"

    def bind_session(
        self,
        context: RanContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> str:
        return session_id


class _SecretLeakingRanImpl(ReferenceRanEngine):
    """An implementation that raises RanError carrying fake secret
    material in the exception MESSAGE (the sandbox must not capture
    message text -- LOCK-023)."""

    label = "secret-leaking-ran-impl"

    def bind_session(
        self,
        context: RanContext,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> str:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "secret=K=0xdeadbeef0xcafebad0x1234567890abcdef",
        )


# ==========================================================================
# Cases 20-32 (W020-b2 part 2)
# ==========================================================================


def case_20_r5_standards_boundary_audit() -> Result:
    name = "case_20_r5_standards_boundary_audit"
    pkg_dir = os.path.join(_ROOT, "adapters", "ran")
    # (a) Forbidden-import scan.  Positive surface: every import is
    # STDLIB, family-internal (level-1 relative), the sanctioned
    # WORK-003 canonical-JSON core helper (``protocol.canonicalization``
    # -- the same sanctioned import the accepted WORK-019 fivegc family
    # carries in serialization/manager/engine), or the ONE sanctioned
    # SDK import: bridge.py's ``from ..contract import AdapterContext,
    # AdapterContract`` (allowlisted explicitly below, by module AND by
    # imported names).
    forbidden_import_roots = ("ssl", "cryptography", "crypto", "random", "secrets")
    stdlib_roots = {
        "__future__", "abc", "base64", "collections", "dataclasses",
        "hashlib", "http", "json", "os", "re", "shutil", "socket",
        "threading", "typing", "unicodedata", "urllib",
    }
    sanctioned_core_roots = {"protocol"}
    # (d) Real-network stdlib (http/socket/urllib/json) is allowed ONLY
    # in the env-aware gate surface: conformance.py (the real-socket
    # reference RAN control-plane peer), openran.py (the
    # production-shaped real-HTTP adapter), openran_interop.py (the B4
    # real-SDR-lab interop gate -- it legitimately drives a real HTTP
    # control peer, no in-repo simulator fallback), and
    # interop_env_probe.py (the Architect-approved NON-SEMANTIC gate
    # hardening: it probes environment capabilities and enforces the
    # anti-faking RAN_PEER_KIND guard -- gate SURFACE, a sibling of
    # openran_interop.py).  Mirrors the fivegc case_19 allowlist
    # mechanism.
    real_network_allowed = {
        "conformance.py", "openran.py", "openran_interop.py",
        "interop_env_probe.py",
    }
    # (e) os.environ is read ONLY in the env-aware gate surface:
    # interop_env_probe.py + openran_interop.py (RAN_INTEROP /
    # RAN_PEER_KIND / RAN_CONTROL_URL / RAN_INTEROP_SESSION_ID /
    # RAN_INTEROP_CELL_ID) and openran.py's explicit ``from_env``
    # opt-in (the only place the adapter itself reads RAN_CONTROL_URL;
    # the constructor never touches the environment -- verified by
    # grep before encoding).  The sub-scan below rejects
    # os.urandom/system/popen/fork/exec/spawn so the `os` import
    # cannot smuggle non-determinism or sandbox escape.
    env_aware_allowed = {"openran.py", "openran_interop.py", "interop_env_probe.py"}
    forbidden_os_calls = (
        "os.urandom", "os.system", "os.popen", "os.fork", "os.exec",
        "os.spawn",
    )
    real_network_modules = ("http", "socket", "urllib", "json")
    # (b) Secret-MATERIAL-looking tokens (not credential NAMES cited in
    # docstrings to explain LOCK-023 -- those are legitimate; the
    # validation module enforces slot names structurally).
    secret_tokens = (
        "private_key", "secret_key", "password", "api_key", "shared_secret",
        "ghp_", "akia",
    )
    for fname in sorted(os.listdir(pkg_dir)):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(pkg_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            source = f.read()
        # validation.py defines the LOCK-023 rejected-token vocabulary
        # (the enforcement); it LEGITIMATELY contains the
        # secret-resembling tokens as the rejected list, so it is
        # excluded from the TEXT scan here (its imports are still
        # audited below -- the fivegc case_19 precedent).
        if fname != "validation.py":
            lower = source.lower()
            for tok in secret_tokens:
                if tok in lower:
                    return fail(name, "%s: secret-looking token %r" % (fname, tok))
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in forbidden_import_roots:
                        return fail(name, "%s: forbidden import root %r" % (fname, root))
                    if root == "os" and fname not in env_aware_allowed:
                        return fail(
                            name,
                            "%s: imports os (only %s may, for env-var config)"
                            % (fname, sorted(env_aware_allowed)),
                        )
                    if (
                        root not in stdlib_roots
                        and root not in sanctioned_core_roots
                    ):
                        return fail(
                            name,
                            "%s: import %r outside stdlib+family+sanctioned SDK"
                            % (fname, root),
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    root = (node.module or "").split(".")[0]
                    if root in forbidden_import_roots:
                        return fail(name, "%s: forbidden import-from root %r" % (fname, root))
                    if root == "os" and fname not in env_aware_allowed:
                        return fail(
                            name,
                            "%s: imports os (only %s may, for env-var config)"
                            % (fname, sorted(env_aware_allowed)),
                        )
                    if (
                        root not in stdlib_roots
                        and root not in sanctioned_core_roots
                    ):
                        return fail(
                            name,
                            "%s: import-from %r outside stdlib+family+sanctioned SDK"
                            % (fname, root),
                        )
                elif node.level == 1:
                    # Family-internal relative import.
                    continue
                else:
                    # level >= 2: reaches OUTSIDE the family -- the ONE
                    # sanctioned SDK import (bridge.py only).
                    names = tuple(sorted(a.name for a in node.names))
                    if (
                        fname != "bridge.py"
                        or node.module != "contract"
                        or names != ("AdapterContext", "AdapterContract")
                    ):
                        return fail(
                            name,
                            "%s: non-sanctioned SDK import (only bridge.py's "
                            "'from ..contract import AdapterContext, "
                            "AdapterContract' is allowed)" % fname,
                        )
        # Non-real-network files must NOT use http/socket/urllib/json.
        if fname not in real_network_allowed:
            for node in ast.walk(tree):
                roots: Set[str] = set()
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    roots = {(node.module or "").split(".")[0]}
                for root in roots:
                    if root in real_network_modules:
                        return fail(
                            name,
                            "%s: real-network import %r forbidden outside the "
                            "env-aware gate surface + conformance peer"
                            % (fname, root),
                        )
        # Env-aware files use `os` for os.environ config ONLY; all
        # other files must not read os.environ at all.
        if fname in env_aware_allowed:
            for bad_call in forbidden_os_calls:
                if bad_call in source:
                    return fail(
                        name,
                        "%s: forbidden os call %r (env-aware files may use "
                        "os.environ only)" % (fname, bad_call),
                    )
        elif "os.environ" in source:
            return fail(
                name,
                "%s reads os.environ (only the env-aware gate surface may)"
                % fname,
            )
    # (c) 3GPP TS + O-RAN citations present (model.py at minimum).
    model_src = open(
        os.path.join(pkg_dir, "model.py"), encoding="utf-8"
    ).read().lower()
    for citation in (
        "ts 38.300", "ts 38.401", "ts 38.473", "ts 38.331", "ts 38.321",
        "ts 38.413", "ts 23.501", "o-ran.wg4",
    ):
        if citation not in model_src:
            return fail(name, "model.py missing %s citation" % citation)
    openran_src = open(
        os.path.join(pkg_dir, "openran.py"), encoding="utf-8"
    ).read().lower()
    if "ts 38.413" not in openran_src and "38.413" not in openran_src:
        return fail(name, "openran.py missing TS 38.413 citation")
    conf_src = open(
        os.path.join(pkg_dir, "conformance.py"), encoding="utf-8"
    ).read().lower()
    if "ts 38.331" not in conf_src:
        return fail(name, "conformance.py missing TS 38.331 citation")
    interop_src = open(
        os.path.join(pkg_dir, "openran_interop.py"), encoding="utf-8"
    ).read().lower()
    if "ts 38.413" not in interop_src or "o-ran.wg4" not in interop_src:
        return fail(name, "openran_interop.py missing TS 38.413/O-RAN.WG4 citations")
    return ok(
        name,
        "no forbidden imports (stdlib + family + sanctioned protocol.canonicalization "
        "+ bridge.py's ..contract pair only); no secret tokens; TS 38.300/38.401/38.473/"
        "38.331/38.321/38.413/23.501 + O-RAN.WG4 cited; real-network stdlib only in "
        "conformance/openran/openran_interop/interop_env_probe; os.environ only in the "
        "env-aware gate surface",
    )


def case_21_r5_frozen_spec_intact() -> Result:
    name = "case_21_r5_frozen_spec_intact"
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


def case_22_r5_no_core_ran_leakage() -> Result:
    name = "case_22_r5_no_core_ran_leakage"
    # DOMAIN modules (sessions/identity/protocol/...) must contain NO
    # RAN references at all (no RAN text tokens, no adapters.ran
    # import).  These are the ADCOS core; they must not know about RAN.
    core_dirs = [
        "sessions", "identity", "protocol", "capabilities", "discovery",
        "transport", "topology", "routing", "multipath", "mobility",
        "federation", "policy", "intent", "resources",
    ]
    # Word-boundary, case-insensitive tokens.  Bare "cu"/"du"/"ru" are
    # deliberately ABSENT (too dangerous as English substrings/words;
    # the CU/DU/RU boundary mapping is proven by case_09 instead).
    ran_tokens = (
        "oai", "openairinterface", "oran", "o-ran", "ocudu", "gnb", "enb",
        "rnti", "c-rnti", "drb", "srb", "prb", "rrc", "ngap", "f1ap",
        "e2ap", "sdr", "usrp", "b210", "cu-plane",
    )
    # Allowlist: the ONLY verified word-boundary occurrences are
    # "gnb"/"enb" as QUOTED members of the LOCK-002
    # access-technology-neutrality REJECTION vocabularies
    # (mobility/model.py and federation/model.py _FORBIDDEN_TOKENS --
    # the enforcement that keeps such tokens OUT of core state, i.e.
    # the very rule this case audits).  A hit is allowlisted ONLY when
    # (file, token) matches AND the occurrence is quote-wrapped (a
    # vocabulary member), so any real use in logic/docstrings still
    # fails the scan.
    negative_vocab_allowlist = {
        ("mobility", "model.py"): {"gnb", "enb"},
        ("federation", "model.py"): {"gnb", "enb"},
    }
    scanned = 0
    vocab_hits = 0
    for d in core_dirs:
        dp = os.path.join(_ROOT, d)
        if not os.path.isdir(dp):
            continue
        for fn in sorted(os.listdir(dp)):
            if not fn.endswith(".py"):
                continue
            fpath = os.path.join(dp, fn)
            with open(fpath, "r", encoding="utf-8") as f:
                src = f.read()
            scanned += 1
            # No core module imports adapters.ran (the real leak).
            if "adapters.ran" in src or "adapters/ran" in src:
                return fail(name, "%s/%s imports adapters.ran (LOCK-002/016 leak)" % (d, fn))
            for tok in ran_tokens:
                for match in re.finditer(r"\b%s\b" % re.escape(tok), src, re.IGNORECASE):
                    line = src[: match.start()].count("\n") + 1
                    before = src[match.start() - 1] if match.start() > 0 else ""
                    after = src[match.end()] if match.end() < len(src) else ""
                    quote_wrapped = before in "\"'" and after in "\"'"
                    if (
                        tok in negative_vocab_allowlist.get((d, fn), set())
                        and quote_wrapped
                    ):
                        vocab_hits += 1
                        continue
                    return fail(
                        name,
                        "%s/%s:%d: RAN token %r leaks into core domain"
                        % (d, fn, line, tok),
                    )
    # The W016 generic adapter SDK + W018 IP adapter are ACCESS-
    # TECHNOLOGY-NEUTRAL by design (LOCK-001/002/016) and may
    # legitimately cite "3GPP" in access-neutrality docstrings.  They
    # must NOT, however, IMPORT the WORK-020 RAN adapter (the real
    # leak).
    peer_files = [
        os.path.join("adapters", "__init__.py"),
        os.path.join("adapters", "contract.py"),
        os.path.join("adapters", "sandbox.py"),
        os.path.join("adapters", "runtime.py"),
        os.path.join("adapters", "model.py"),
        os.path.join("adapters", "validation.py"),
        os.path.join("adapters", "serialization.py"),
        os.path.join("adapters", "errors.py"),
    ]
    for cf in peer_files + [os.path.join("adapters", "README.md")]:
        fpath = os.path.join(_ROOT, cf)
        if not os.path.exists(fpath):
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            src = f.read()
        scanned += 1
        if "adapters.ran" in src or "adapters/ran" in src:
            return fail(name, "%s imports adapters.ran (LOCK-002/016 leak)" % cf)
    # adapters/ip/ is the W018 peer -- it must not import adapters.ran.
    ip_dir = os.path.join(_ROOT, "adapters", "ip")
    if os.path.isdir(ip_dir):
        for fn in sorted(os.listdir(ip_dir)):
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(ip_dir, fn), "r", encoding="utf-8") as f:
                src = f.read()
            scanned += 1
            if "adapters.ran" in src or "adapters/ran" in src:
                return fail(name, "adapters/ip/%s imports adapters.ran" % fn)
    return ok(
        name,
        "core domain modules carry no RAN tokens (word-boundary scan, %d files; "
        "%d allowlisted occurrences are quoted members of the LOCK-002 rejection "
        "vocabularies); no module imports adapters.ran (%d files scanned)"
        % (scanned, vocab_hits, scanned),
    )


def case_23_r5_w016_sdk_bridge() -> Result:
    name = "case_23_r5_w016_sdk_bridge"
    # (a) The bridge IS the WORK-016 SDK contract (isinstance-enforced).
    bridge = RanTechnologyAdapter(ReferenceRanEngine())
    if not isinstance(bridge, AdapterContract):
        return fail(name, "bridge is not an adapters.contract.AdapterContract")
    expected_ops = (
        "open", "capabilities", "observe", "allocate", "release",
        "bind_session", "unbind_session", "health", "close",
    )
    if CONTRACT_OPERATIONS != expected_ops:
        return fail(name, "SDK CONTRACT_OPERATIONS changed: %r" % (CONTRACT_OPERATIONS,))
    for op in CONTRACT_OPERATIONS:
        if not callable(getattr(bridge, op, None)):
            return fail(name, "bridge missing SDK op %r" % op)
    # (b) The empty-RAN observe translation: the honest link-down
    # mapping with the six kebab-case WORK-016 LinkMetricName VALUES.
    ctx = AdapterContext(
        adapter_id="adcos:adapter:ran-selftest",
        access_technology_id="access.ran.5g-nr",
        instant=_T(0),
        step_budget=100,
    )
    # SDK open -> impl.open (bring the RAN integration up; None return).
    bridge.open(ctx)
    down = dict(bridge.observe(ctx))
    expected_down = {
        "link-up": 0,
        "rx-bytes-total": 0,
        "tx-bytes-total": 0,
        "rx-error-count": 0,
        "tx-error-count": 0,
        "retransmit-count": 0,
    }
    if down != expected_down:
        return fail(name, "empty-RAN observe != link-down six-metric mapping: %r" % (down,))
    if sorted(down) != sorted(
        (
            LinkMetricName.LINK_UP, LinkMetricName.RX_BYTES_TOTAL,
            LinkMetricName.TX_BYTES_TOTAL, LinkMetricName.RX_ERROR_COUNT,
            LinkMetricName.TX_ERROR_COUNT, LinkMetricName.RETRANSMIT_COUNT,
        )
    ):
        return fail(name, "bridge keys != the WORK-016 LinkMetricName VALUES")
    # (c) bind returns an opaque ran:bearer: ref with no session
    # material; the populated-RAN observe is the 1:1 metric projection.
    engine = ReferenceRanEngine()
    ran_ctx = RanContext(
        ran_integration_id="adcos:ran:bridge", instant=_T(0), step_budget=100,
    )
    engine.open(ran_ctx)
    gnb_ref = engine.provision_gnb(ran_ctx, request=_canonical_gnb_request())
    engine.activate_cell(ran_ctx, gnb_ref=gnb_ref, cell_id="c1")
    bridged = RanTechnologyAdapter(engine)
    bearer_ref = bridged.bind_session(ctx, session_id="sess-bridge", requirements=None)
    if not isinstance(bearer_ref, str) or not bearer_ref.startswith("ran:bearer:"):
        return fail(name, "bridge bind did not return an opaque ran:bearer: ref: %r" % (bearer_ref,))
    if "sess-bridge" in bearer_ref:
        return fail(name, "bridge bearer ref carries session material (R1)")
    populated = dict(bridged.observe(ctx))
    if sorted(populated) != sorted(expected_down):
        return fail(name, "populated observe keys != the six generic metrics")
    if populated["link-up"] != 1:
        return fail(name, "populated observe did not translate link-up=1: %r" % (populated,))
    # (d) AST: the bridge imports ONLY the sanctioned SDK symbols from
    # ..contract (no absolute adapters import, no other level>=2 import).
    path = os.path.join(_ROOT, "adapters", "ran", "bridge.py")
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    sdk_imports: List[Tuple[Optional[str], Tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level >= 2:
            sdk_imports.append(
                (node.module, tuple(sorted(a.name for a in node.names)))
            )
        elif node.level == 0 and (node.module or "").split(".")[0] == "adapters":
            return fail(name, "bridge imports the SDK by absolute path (unsanctioned)")
    if sdk_imports != [("contract", ("AdapterContext", "AdapterContract"))]:
        return fail(name, "bridge SDK imports != the sanctioned pair: %r" % (sdk_imports,))
    return ok(
        name,
        "isinstance AdapterContract; all 9 SDK ops callable; empty-RAN observe -> honest "
        "link-down mapping (six kebab LinkMetricName values); bind -> opaque ran:bearer: "
        "ref (no session material); imports only the sanctioned ..contract pair",
    )


def case_24_determinism_byte_identical_snapshot() -> Result:
    name = "case_24_determinism_byte_identical_snapshot"

    def build() -> bytes:
        mgr, gnb_ref = _fresh_manager()
        token = _bind(mgr, "sess-det", gnb_ref, 3)
        r = mgr.egress_data(now=_T(4), binding_ref=token, payload=PAYLOAD)
        assert r.ok, "egress_data failed: %s" % r.detail
        return mgr.to_canonical_bytes()

    a = build()
    b = build()
    if a != b:
        return fail(name, "canonical state not byte-identical across identical runs")
    return ok(name, "byte-identical canonical state across identical operation histories")


def case_25_determinism_cross_impl_byte_identical() -> Result:
    name = "case_25_determinism_cross_impl_byte_identical"
    # DIRECT comparison, no normalization: the SAME operation history
    # through (a) ReferenceRanEngine and (b) an OpenRanAdapter pointed
    # at a live ReferenceRanConformanceServer (real HTTP over a real
    # loopback socket), each in its own manager.
    server = ReferenceRanConformanceServer()
    try:
        m1 = _new_manager(ReferenceRanEngine(), label="reference-ran-engine")
        r1 = m1.provision_gnb(now=_T(1), request=_canonical_gnb_request())
        if not r1.ok:
            return fail(name, "engine provision failed: %s" % r1.detail)
        gnb_one = str(r1.value)
        if not m1.activate_cell(now=_T(2), gnb_ref=gnb_one, cell_id="c1").ok:
            return fail(name, "engine activate failed")
        token_one = _bind(m1, "sess-cross", gnb_one, 3)
        r = m1.egress_data(now=_T(4), binding_ref=token_one, payload=PAYLOAD)
        if not r.ok or r.value != PAYLOAD:
            return fail(name, "engine egress not byte-identical")

        m2 = _new_manager(
            OpenRanAdapter(control_url=server.base_url), label="openran-adapter"
        )
        r2 = m2.provision_gnb(now=_T(1), request=_canonical_gnb_request())
        if not r2.ok:
            return fail(name, "adapter provision failed: %s" % r2.detail)
        gnb_two = str(r2.value)
        if not m2.activate_cell(now=_T(2), gnb_ref=gnb_two, cell_id="c1").ok:
            return fail(name, "adapter activate failed")
        token_two = _bind(m2, "sess-cross", gnb_two, 3)
        r = m2.egress_data(now=_T(4), binding_ref=token_two, payload=PAYLOAD)
        if not r.ok or r.value != PAYLOAD:
            return fail(name, "adapter egress not byte-identical")

        a = m1.to_canonical_bytes()
        b = m2.to_canonical_bytes()
        if a != b:
            return fail(name, "canonical state differs across implementations (DIRECT, no normalization)")
        # implementation_label is NOT in the snapshot (B2).
        snap = m1.snapshot()
        if "implementation_label" in snap:
            return fail(name, "implementation_label in canonical snapshot (B2 violation)")
        # But the two labels genuinely differ (diagnostic_state).
        d1 = m1.diagnostic_state().get("implementation_label", "")
        d2 = m2.diagnostic_state().get("implementation_label", "")
        if d1 == d2:
            return fail(name, "two impls have the same label (test invalid)")
        return ok(
            name,
            "DIRECT byte-identical canonical state: ReferenceRanEngine == OpenRanAdapter "
            "over a live real-HTTP conformance peer (same op history); implementation_label "
            "excluded (B2)",
        )
    finally:
        server.close()


def case_26_failure_isolation_base_exception() -> Result:
    name = "case_26_failure_isolation_base_exception"
    mgr = _new_manager(
        _CrashingRanImpl(), integration_id="adcos:ran:crash", label="crash"
    )
    r = mgr.provision_gnb(now=_T(1), request=_canonical_gnb_request())
    if r.ok:
        return fail(name, "crashing impl did not fail")
    if r.reason != RanReasonCode.RAN_FAILURE:
        return fail(name, "wrong reason: %s" % r.reason)
    if r.failure is None or r.failure.exception_class_name != "SystemExit":
        return fail(name, "exception class name not captured")
    if "crashed" in (r.detail or "").lower():
        return fail(name, "exception message text captured (LOCK-023 leak)")
    return ok(name, "SystemExit -> isolated RanFailure value; class name only; message text not captured")


def case_27_failure_isolation_contract_violation() -> Result:
    name = "case_27_failure_isolation_contract_violation"
    mgr, gnb_ref = _fresh_manager(
        _ContractViolatingRanImpl(),
        integration_id="adcos:ran:bogus", label="bogus",
    )
    r = mgr.bind_session(now=_T(3), session_id="sess-bogus", gnb_ref=gnb_ref)
    if r.ok:
        return fail(name, "contract-violating impl did not fail")
    if r.reason != RanReasonCode.CONTRACT_VIOLATION:
        return fail(name, "wrong reason: %s" % r.reason)
    # The non-contract value is discarded (never stored/keyed/echoed).
    if r.value is not None:
        return fail(name, "non-contract value was returned (not discarded)")
    if mgr.binding_count != 0:
        return fail(name, "bogus binding was registered")
    return ok(name, "bind returning the session_id itself -> contract-violation; value discarded; no binding registered")


def case_28_failure_isolation_budget_exhaustion() -> Result:
    name = "case_28_failure_isolation_budget_exhaustion"
    # A tiny budget: open charges 4 (fits), provision_gnb charges 10
    # (exceeds) -- the deterministic hang model fires.
    mgr = RanManager(ran_integration_id="adcos:ran:budget", default_step_budget=5)
    r = mgr.register_implementation(
        ReferenceRanEngine(), label="budget", make_default=True, now=_T(0)
    )
    if not r.ok:
        return fail(name, "register failed (open charge 4 must fit budget 5): %s" % r.detail)
    r = mgr.provision_gnb(now=_T(1), request=_canonical_gnb_request())
    if r.ok:
        return fail(name, "provision did not exhaust the budget")
    if r.reason != RanReasonCode.BUDGET_EXHAUSTED:
        return fail(name, "wrong reason: %s" % r.reason)
    detail = (r.detail or "").lower()
    if "hang" not in detail:
        return fail(name, "no hang model mentioned in failure detail")
    if "wall clock" not in detail:
        return fail(name, "failure detail must state no wall clock is consulted")
    return ok(name, "BUDGET_EXHAUSTED (step 10 > budget 5); hang model; no wall clock")


def case_29_failure_isolation_no_secret_leak() -> Result:
    name = "case_29_failure_isolation_no_secret_leak"
    mgr, gnb_ref = _fresh_manager(
        _SecretLeakingRanImpl(),
        integration_id="adcos:ran:leak", label="leaky",
    )
    r = mgr.bind_session(now=_T(3), session_id="sess-leak", gnb_ref=gnb_ref)
    if r.ok:
        return fail(name, "secret-leaking impl did not fail")
    blob = (
        repr(r.failure.to_payload() if r.failure is not None else None)
        + " "
        + repr(r.failure)
        + " "
        + (r.detail or "")
    )
    for fragment in ("0xdeadbeef", "cafebad", "1234567890abcdef", "secret=K"):
        if fragment in blob:
            return fail(name, "secret material %r leaked through failure diagnostics" % fragment)
    return ok(name, "exception message text never captured (LOCK-023); failure value carries reason + class name only")


def case_30_b4_real_ran_conformance() -> Result:
    name = "case_30_b4_real_ran_conformance"
    # Two legs over REAL sockets (ephemeral ports on 127.0.0.1); both
    # servers are this case's own instances, stopped in finally.
    server1 = ReferenceRanConformanceServer()
    server2 = ReferenceRanConformanceServer()
    try:
        # Leg 1: manager + OpenRanAdapter(endpoint=server1) as default.
        mgr = _new_manager(
            OpenRanAdapter(control_url=server1.base_url),
            integration_id="adcos:ran:b4", label="openran-one",
        )
        r = mgr.provision_gnb(now=_T(1), request=_canonical_gnb_request())
        if not r.ok:
            return fail(name, "leg1 provision failed: %s" % r.detail)
        gnb_one = str(r.value)
        if not mgr.activate_cell(now=_T(2), gnb_ref=gnb_one, cell_id="c1").ok:
            return fail(name, "leg1 activate failed")
        r = mgr.access_path_session(now=_T(3), session_id="sess-conf")
        if not r.ok:
            return fail(name, "leg1 access_path_session failed: %s" % r.detail)
        sess_a = r.value
        sess_a.connect("internet")
        if sess_a.send(PAYLOAD) != len(PAYLOAD):
            return fail(name, "leg1 send returned wrong length")
        echo_a = sess_a.recv()
        if echo_a != PAYLOAD:
            return fail(name, "leg1 recv != payload byte-identical: %r" % (echo_a,))

        # Leg 2: register_implementation swap to a SECOND OpenRanAdapter
        # on a SECOND server (make_default) -> new binding -> repeat.
        r = mgr.register_implementation(
            OpenRanAdapter(control_url=server2.base_url),
            label="openran-two", make_default=True, now=_T(5),
        )
        if not r.ok:
            return fail(name, "leg2 register swap failed: %s" % r.detail)
        r = mgr.provision_gnb(now=_T(6), request=_alternate_gnb_request())
        if not r.ok:
            return fail(name, "leg2 provision failed: %s" % r.detail)
        gnb_two = str(r.value)
        if not mgr.activate_cell(now=_T(7), gnb_ref=gnb_two, cell_id="c1").ok:
            return fail(name, "leg2 activate failed")
        r = mgr.access_path_session(now=_T(8), session_id="sess-conf-2")
        if not r.ok:
            return fail(name, "leg2 access_path_session failed: %s" % r.detail)
        sess_b = r.value
        sess_b.connect("internet")
        if sess_b.send(PAYLOAD) != len(PAYLOAD):
            return fail(name, "leg2 send returned wrong length")
        echo_b = sess_b.recv()
        if echo_b != PAYLOAD:
            return fail(name, "leg2 recv != payload byte-identical: %r" % (echo_b,))

        # Cleanup (mediated unbind per live binding, then manager close).
        for token in sorted(mgr._bindings):
            if not mgr.close_binding(now=_T(9), binding_ref=token).ok:
                return fail(name, "cleanup close_binding failed for %s" % token)
        mgr.close()
        return ok(
            name,
            "AccessPathSession->RanManager->SandboxedRan->OpenRanAdapter->real HTTP RAN "
            "conformance peer->AccessPathSession.recv (leg1 + leg2 register_implementation "
            "swap on a second real peer); payload=%r byte-identical both legs" % PAYLOAD,
        )
    finally:
        server1.close()
        server2.close()


def case_31_b4_real_sdr_lab_interop_gate() -> Result:
    """B4 real-SDR-lab interop gate (environment-gated).

    The frozen WORK-020 acceptance requires a real SDR-based lab
    topology (OpenAirInterface/O-RAN style) -- NOT the in-repo
    :class:`ReferenceRanConformanceServer`.  This case runs the gate
    with the environment CLEAN of ``RAN_INTEROP`` (save/restore in
    finally, mirroring the fivegc env discipline) so the run asserts
    the gate-disabled disclosure deterministically regardless of the
    caller's environment: SKIP, naming the conformance suite (case_30)
    as the strongest honest in-sandbox evidence; NO PASSED.  The gate
    closes the frozen SDR-lab criterion only on a real lab host (see
    the RAN_INTEROP_RUNBOOK); it NEVER fakes success with the in-repo
    conformance peer.
    """
    name = "case_31_b4_real_sdr_lab_interop_gate"
    env_keys = ("RAN_INTEROP", "RAN_PEER_KIND", "RAN_CONTROL_URL")
    saved = {k: os.environ.get(k) for k in env_keys}
    try:
        for key in env_keys:
            os.environ.pop(key, None)
        if ran_interop_gate_enabled():
            return fail(name, "gate still enabled after cleaning RAN_INTEROP")
        outcome = run_openran_interop(RanInteropConfig.from_env())
        if outcome.status != "SKIP":
            return fail(
                name,
                "gate-disabled run must SKIP; got %s: %s"
                % (outcome.status, outcome.detail),
            )
        detail = outcome.detail.lower()
        if "conformance" not in detail:
            return fail(name, "SKIP detail must name the conformance suite")
        if "referenceranconformanceserver" not in detail:
            return fail(name, "SKIP detail must name the in-repo ReferenceRanConformanceServer")
        return ok(
            name,
            "SKIP (environment-gated RAN_INTEROP!=1): the B4 real-SDR-lab interop "
            "gate is not run; the conformance suite (case_30) remains the strongest "
            "honest in-sandbox evidence. Set RAN_INTEROP=1 with RAN_PEER_KIND=real_oai "
            "and a reachable real OpenAirInterface/O-RAN SDR lab control endpoint "
            "(RAN_CONTROL_URL) to run the frozen acceptance gate; NO PASSED is "
            "possible from the disabled path",
        )
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def case_32_b4_gate_hardening_matrix_and_anti_faking() -> Result:
    """B4 gate-hardening regression (the W019 hardening mirrored).

    Five legs, all with env save/restore in finally:

    (1) probe matrix on the SKIP path: run with RAN_INTEROP unset ->
        SKIP; ``probe_ran_interop_capability()`` directly -> the
        summary carries the [SDR-LAB CAPABILITY MATRIX] header and one
        line per check (build_tools/sdr_driver/sctp/tun/
        oai_binaries/openran_control).
    (2) RAN_INTEROP=1 + RAN_PEER_KIND=reference -> FORBIDDEN with NO
        socket connection made (a connection-counting listener on a
        real port proves the guard fires BEFORE any network probe).
    (3) RAN_INTEROP=1 + real_oai + RAN_CONTROL_URL at an unreachable
        port -> UNREACHABLE with the matrix string in the detail.
    (4) sanity: the in-repo conformance server CANNOT satisfy the gate
        (real_oai + a LIVE conformance server): the outcome is NOT
        PASSED, and the [SDR] evidence line is absent while the
        environment probe found no SDR device evidence (the
        anti-faking rule: the reference peer never closes the
        SDR-lab criterion).
    (5) NO PASSED observed across all legs (acceptance semantics
        preserved -- SKIP never becomes PASS).
    """
    name = "case_32_b4_gate_hardening_matrix_and_anti_faking"
    env_keys = ("RAN_INTEROP", "RAN_PEER_KIND", "RAN_CONTROL_URL")
    saved = {k: os.environ.get(k) for k in env_keys}
    try:
        # ---- Leg 1: probe matrix on the SKIP path ----
        for key in env_keys:
            os.environ.pop(key, None)
        outcome = run_openran_interop()
        if outcome.status != "SKIP":
            return fail(name, "leg1: gate-disabled run must SKIP; got %s: %s" % (outcome.status, outcome.detail))
        report = probe_ran_interop_capability(RanEnvProbeConfig.from_env())
        if report.forbidden_substitution is not None:
            return fail(name, "leg1: guard must not fire with RAN_PEER_KIND unset; got %s" % report.forbidden_substitution)
        if report.reachable:
            return fail(name, "leg1: probe reports reachable=True; expected False (sandbox cannot host a real SDR lab)")
        matrix = report.summary()
        if "[SDR-LAB CAPABILITY MATRIX]" not in matrix:
            return fail(name, "leg1: matrix header missing; got:\n%s" % matrix)
        for entry in ("build_tools", "sdr_driver", "sctp", "tun", "oai_binaries", "openran_control"):
            if entry not in matrix:
                return fail(name, "leg1: matrix missing check %r; got:\n%s" % (entry, matrix))
        if "PASSED" in matrix:
            return fail(name, "leg1: matrix must never carry PASSED; got:\n%s" % matrix)
        sdr_available = any(
            check.name == "sdr_driver" and check.available
            for check in report.checks
        )

        # ---- Leg 2: FORBIDDEN before ANY network probe ----
        # A connection-counting listener on a real port: the gate's
        # HTTP probes are synchronous, so any connection the gate made
        # would sit in the listen backlog once it returns; a
        # non-blocking accept sweep after the gate returns counts them
        # all (no wall clock, no sleep -- pure backlog drain).
        srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        try:
            srv.bind(("127.0.0.1", 0))
            srv.listen(4)
            port = srv.getsockname()[1]
            os.environ["RAN_INTEROP"] = "1"
            os.environ["RAN_PEER_KIND"] = "reference"
            os.environ["RAN_CONTROL_URL"] = "http://127.0.0.1:%d" % port
            outcome2 = run_openran_interop()
            if outcome2.status != "FORBIDDEN":
                return fail(
                    name,
                    "leg2: gate must return FORBIDDEN on RAN_PEER_KIND=reference; "
                    "got %s: %s" % (outcome2.status, outcome2.detail),
                )
            if "not probed" not in outcome2.detail:
                return fail(name, "leg2: FORBIDDEN detail must disclose the unprobed endpoint")
            srv.setblocking(False)
            connections = 0
            try:
                while True:
                    conn, _addr = srv.accept()
                    connections += 1
                    conn.close()
            except BlockingIOError:
                pass
            if connections != 0:
                return fail(
                    name,
                    "leg2: %d socket connection(s) made during a FORBIDDEN gate "
                    "run (the guard must fire BEFORE any network probe)" % connections,
                )
        finally:
            srv.close()

        # ---- Leg 3: real_oai + unreachable port -> UNREACHABLE ----
        # Reserve then release an ephemeral port (a robustly
        # unreachable endpoint; the fivegc leg-4 discipline with a
        # non-conflicting port choice).
        probe_sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        probe_sock.bind(("127.0.0.1", 0))
        unreachable_port = probe_sock.getsockname()[1]
        probe_sock.close()
        os.environ["RAN_PEER_KIND"] = "real_oai"
        os.environ["RAN_CONTROL_URL"] = "http://127.0.0.1:%d" % unreachable_port
        outcome3 = run_openran_interop()
        if outcome3.status != "UNREACHABLE":
            return fail(
                name,
                "leg3: gate must return UNREACHABLE on an unreachable control "
                "endpoint; got %s: %s" % (outcome3.status, outcome3.detail),
            )
        if "[SDR-LAB CAPABILITY MATRIX]" not in outcome3.detail:
            return fail(name, "leg3: UNREACHABLE detail must carry the capability matrix")

        # ---- Leg 4: the in-repo conformance server cannot close the gate ----
        server = ReferenceRanConformanceServer()
        try:
            os.environ["RAN_CONTROL_URL"] = server.base_url
            outcome4 = run_openran_interop()
            if outcome4.status == "PASSED":
                return fail(
                    name,
                    "leg4: the in-repo conformance peer must NEVER close the "
                    "frozen SDR-lab criterion (anti-faking rule violated)",
                )
            # The [SDR] evidence line is ENVIRONMENT-earned (device-node
            # evidence), never control-plane evidence: with the
            # sdr_driver probe missing, no outcome may claim it.
            if not sdr_available and any(
                line.startswith("[SDR]") for line in outcome4.evidence
            ):
                return fail(
                    name,
                    "leg4: [SDR] evidence line claimed without SDR device "
                    "evidence (the reference peer never closes the SDR-lab "
                    "criterion)",
                )
        finally:
            server.close()

        # ---- Leg 5: acceptance semantics preserved ----
        for label, st in (
            ("leg1", outcome.status),
            ("leg2", outcome2.status),
            ("leg3", outcome3.status),
            ("leg4", outcome4.status),
        ):
            if st == "PASSED":
                return fail(
                    name,
                    "%s: gate must NEVER report PASSED in this sandbox "
                    "(acceptance semantics preserved)" % label,
                )
        return ok(
            name,
            "SKIP-path matrix carries the [SDR-LAB CAPABILITY MATRIX] header + one line "
            "per check (build_tools/sdr_driver/sctp/tun/oai_binaries/openran_control); "
            "RAN_PEER_KIND=reference fires FORBIDDEN with ZERO socket connections "
            "(connection-counting listener + not-probed disclosure); real_oai + "
            "unreachable -> UNREACHABLE with the matrix; the live in-repo conformance "
            "peer cannot close the gate (no [SDR] evidence without device evidence); "
            "no PASSED observed (acceptance semantics preserved)",
        )
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ==========================================================================
# Main
# ==========================================================================


def main() -> int:
    cases: List = [
        case_01_contract_surface_frozen,
        case_02_context_least_authority,
        case_03_context_injected_instant_and_budget,
        case_04_provision_gnb_happy,
        case_05_cell_lifecycle_happy,
        case_06_bind_session_happy,
        case_07_egress_data_happy,
        case_08_access_path_facade_happy,
        case_09_topology_mapping,
        case_10_capability_mapping,
        case_11_health_mapping,
        case_12_resource_mapping,
        case_13_r1_session_ran_identity_separation_green,
        case_14_r1_session_ran_collapse_rejected,
        case_15_r2_identifier_and_credential_isolation,
        case_16_r2_ran_unavailable_fail_closed,
        case_17_r3_facade_surface_audited,
        case_18_r3_leaky_session_rejected,
        case_19_r4_default_swap_preserves_live_binding,
        case_20_r5_standards_boundary_audit,
        case_21_r5_frozen_spec_intact,
        case_22_r5_no_core_ran_leakage,
        case_23_r5_w016_sdk_bridge,
        case_24_determinism_byte_identical_snapshot,
        case_25_determinism_cross_impl_byte_identical,
        case_26_failure_isolation_base_exception,
        case_27_failure_isolation_contract_violation,
        case_28_failure_isolation_budget_exhaustion,
        case_29_failure_isolation_no_secret_leak,
        case_30_b4_real_ran_conformance,
        case_31_b4_real_sdr_lab_interop_gate,
        case_32_b4_gate_hardening_matrix_and_anti_faking,
    ]
    results: List[Result] = []
    for case in cases:
        try:
            results.append(case())
        except Exception as exc:  # noqa: BLE001
            results.append(fail(case.__name__, "case raised %s: %s" % (type(exc).__name__, exc)))
    print("ADCOS 5G RAN integration self-test (WORK-020)")
    print("=" * 72)
    for name, ok_flag, detail in results:
        print("[%s] %-52s %s" % ("ok  " if ok_flag else "FAIL", name, detail))
    print("-" * 72)
    passed = sum(1 for _, ok_flag, _ in results if ok_flag)
    if passed == len(results):
        print("Result: PASS (%d/%d cases)" % (passed, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
