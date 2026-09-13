"""The deterministic contract-fulfillment demonstration of the runtime.

:func:`run_contract_fulfillment_demo` composes ONLY accepted services,
BY REFERENCE, into the full software-class demonstration chain the
DEC-0126 deployment exposes:

1. **the request boundary leg** — the ``developerapi`` gateway
   (``DeveloperApiService.handle``) drives the canonical lifecycle the
   way an external developer application does: create a connectivity
   intent -> accept an offer (an opaque typed reference, LOCK-114) ->
   activate the contract. Every mutation rides the boundary's own
   durable write-ahead idempotency discipline, so a re-run with the
   same instant replays byte-identically (never a second canonical
   execution);
2. **the planning leg** — ``executionplans.translate_contract``
   (LOCK-109) translates the ACCEPTED contract into a typed
   ``ExecutionPlan`` (the optimizer proposal is fixed DATA:
   ``SegmentInput`` records over the contract's own verbatim accepted
   offer reference), then the pure LOCK-108 gate
   ``verify_plan_preserves_contract`` re-verifies the plan against the
   contract, and the plan is BOUND to the contract as an opaque
   ``execution-artifact`` reference through the store's public
   ``BindExecutionArtifact`` command (LOCK-117: data, never authority);
3. **the execution leg** — the plan's single primary segment is
   executed through the ACCEPTED adapter boundary
   (``adapters.capability.CapabilityAdapter`` over the WORK-016
   sandboxed runtime) in deterministic sandbox mode: reserve ->
   activate -> measure -> release, each adapter operation mirrored by
   the plan's own segment-state kernel
   (``apply_segment_transition``: PLANNED -> RESERVED -> ACTIVATED ->
   MEASURED -> RELEASED). The deterministic reference adapters ARE the
   sandbox providers (no provider claim is made);
4. **the evidence leg** — typed evidence records land in the injected
   ``EvidenceStore``: one OBSERVATION (the adapter-reported ``link-up``
   measurement sample, attributed to the sandbox activation, with the
   measurement id as its source reference) and one ATTESTATION (the
   controller-verified count of released realization segments). Both
   carry LOCK-118 provenance and content-derived ids; ingest is
   idempotent, so a re-run never duplicates a record.

DETERMINISM MANDATE: the ONLY time source is the injected instants —
the demo request's ``instant`` (default a fixed constant) drives every
command instant through deterministic arithmetic
(:func:`agent.clock.add_seconds`); no wall clock, no randomness, no
network, no UUIDs. Identical inputs produce the byte-identical
canonical-JSON response. The idempotency keys are derived from the
instant, so one instant == one demonstration identity (re-runs replay;
a different instant is a genuinely new demonstration contract).

EVIDENCE HONESTY: the response is explicitly and only
``"evidence_class": "SOFTWARE"`` — a software deployment demonstration
over the accepted domains. It NEVER claims physical connectivity;
EVID-002..EVID-008 remain open. In production mode the writes land in
the injected durable stores (the Neon-backed journal adapters), so the
contract journal, the boundary journal and the evidence records are
persisted — the DEMONSTRATION response itself stays software-class.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from agent.clock import add_seconds, parse_utc

from contracts import BindExecutionArtifact, Provenance

from developerapi.errors import DeveloperApiError
from developerapi.gateway import ApiRequest

from executionplans import (
    SegmentInput,
    apply_segment_transition,
    plan_reference,
    translate_contract,
    verify_plan_preserves_contract,
)

from evidence import AttestationEvidence, ObservationEvidence

from protocol.canonicalization import canonical_json_bytes

from .services import RuntimeServices

__all__ = [
    "DEFAULT_DEMO_INSTANT",
    "DEMO_EVIDENCE_CLASS",
    "run_contract_fulfillment_demo",
]


#: The fixed default demonstration instant (request-declared command
#: instants derive from it by deterministic arithmetic).
DEFAULT_DEMO_INSTANT = "2026-09-13T00:00:00Z"

#: The honest classification of everything this demonstration produces.
DEMO_EVIDENCE_CLASS = "SOFTWARE"

#: The deterministic instant offsets of the demonstration chain
#: (seconds after the base instant; fixed constants, never wall clock).
_OFFSET_CREATE = 0
_OFFSET_OFFERS = 600
_OFFSET_ACTIVATE = 1200
_OFFSET_BIND = 1500
_OFFSET_RESERVE = 1800
_OFFSET_EXEC_ACTIVATE = 1810
_OFFSET_MEASURE = 3600
_OFFSET_RELEASE = 7200
_OFFSET_FRESHNESS = 3600
_OFFSET_ATTEST_VALIDITY = 86400
_OFFSET_CONTRACT_VALIDITY = 2592000

#: The fixed demonstration material (technology-neutral, opaque typed
#: references only — LOCK-114; no network implementation vocabulary).
_DEMO_REQUIREMENT_VALUE = "demo:intent-requirements:v1"
_DEMO_OFFER_VALUE = "demo:offer:ran-reference:v1"
_DEMO_SIGNATURE_VALUE = "demo:signature:v1"
_DEMO_PLANNER = "adcos:runtime:demo-planner"
_DEMO_OPTIMIZER = "adcos:runtime:demo-optimizer"
_DEMO_ATTESTOR = "adcos:runtime:demo-attestor"
_DEMO_OFFER_ISSUER = "provider:ran-reference"
_DEMO_INTENT_AUTHORITY = "intent-authority"
_DEMO_ASSURANCE_AUTHORITY = "assurance-authority"
_API_VERSION = "2.0"


def _require_instant(value: object) -> str:
    """Validate the request-declared base instant (fail closed)."""
    if value is None:
        return DEFAULT_DEMO_INSTANT
    if not isinstance(value, str) or not value:
        raise DeveloperApiError(
            "invalid-input", "the demo instant must be an RFC 3339 UTC string"
        )
    try:
        parse_utc(value)
    except Exception as error:  # noqa: BLE001 - translated, never leaked raw
        raise DeveloperApiError(
            "invalid-input",
            "the demo instant %r is not RFC 3339 UTC (YYYY-MM-DDTHH:MM:SSZ): %s"
            % (value, error),
        ) from None
    return value


def _intent_body(base: str) -> Dict[str, Any]:
    """The canonical technology-neutral creation core (the accepted
    battery idiom: every semantics-bearing member rides its frozen
    reference kind)."""
    return {
        "requirements": [
            {
                "ref_kind": "intent-requirements",
                "value": _DEMO_REQUIREMENT_VALUE,
                "provenance": {
                    "issuer": _DEMO_INTENT_AUTHORITY,
                    "decision_refs": ["demo:intent:v1"],
                },
            }
        ],
        "validity": {
            "not_before": base,
            "not_after": add_seconds(base, _OFFSET_CONTRACT_VALIDITY),
        },
        "termination": {
            "conditions": ["principal-requested", "validity-expired"],
            "compensation": {
                "ref_kind": "compensation",
                "value": "demo:compensation:v1",
            },
        },
        "recorded_at": add_seconds(base, _OFFSET_CREATE),
        "hard_constraints": [
            {"kind": "latency-bound", "params": {"ms": 100}},
            {"kind": "throughput-floor", "params": {"bps": 1000}},
        ],
        "beneficiaries": [
            {"beneficiary_kind": "DEVICE", "beneficiary_ref": "demo:device:v1"}
        ],
        "service_properties": [
            {"ref_kind": "service-property", "value": "demo:service-property:v1"}
        ],
        "usage_pricing_terms": {
            "ref_kind": "usage-pricing-terms",
            "value": "demo:usage-pricing:v1",
        },
        "assurance_obligations": [
            {
                "ref_kind": "assurance-obligation",
                "value": "demo:assurance-obligation:v1",
                "provenance": {
                    "issuer": _DEMO_ASSURANCE_AUTHORITY,
                    "decision_refs": ["demo:assurance:v1"],
                },
            }
        ],
        "execution_scope": [
            {"ref_kind": "execution-scope", "value": "demo:execution-scope:v1"},
        ],
    }


def _boundary_request(
    services: RuntimeServices,
    method: str,
    route: str,
    body: Mapping[str, Any],
    *,
    idempotency_key: str,
):
    """Build one authenticated gateway request (the platform-held demo
    credential; the secret never enters a journal line or a response)."""
    return ApiRequest(
        method=method,
        route=route,
        body=dict(body),
        api_version=_API_VERSION,
        idempotency_key=idempotency_key,
        application_id=services.demo_application_id,
        secret=services.demo_credential,
    )


def _drive(
    services: RuntimeServices,
    method: str,
    route: str,
    body: Mapping[str, Any],
    *,
    idempotency_key: str,
):
    """Drive one gateway mutation/read and fail closed on any non-200
    canonical outcome (the boundary's own reason is preserved)."""
    response = services.gateway.handle(
        _boundary_request(
            services, method, route, body, idempotency_key=idempotency_key
        )
    )
    if response.status != 200:
        error = response.error() or {}
        raise DeveloperApiError(
            error.get("reason") or "invalid-input",
            "the demonstration boundary request %s %s failed: %s"
            % (method, route, error.get("message") or "unspecified failure"),
            canonical_reason=error.get("canonical_reason") or "",
        )
    return response


def _require_ok(op_result: Any, operation: str) -> Any:
    """Fail closed on an isolated adapter failure VALUE (the sandbox
    adapter boundary returns typed failures, never exceptions)."""
    if getattr(op_result, "ok", False):
        return op_result.value
    failure = getattr(op_result, "failure", None)
    reason = getattr(failure, "reason", "adapter-failure") if failure else "adapter-failure"
    detail = getattr(failure, "detail", "?") if failure else "?"
    raise DeveloperApiError(
        "invalid-input",
        "the sandbox execution operation %s failed (%s): %s"
        % (operation, reason, detail),
    )


def _link_up_sample(measurement: Any) -> Dict[str, Any]:
    """The ``link-up`` sample of one sandbox measurement (deterministic;
    the frozen evidence observation-metric vocabulary)."""
    for sample in getattr(measurement, "samples", ()) or ():
        if isinstance(sample, Mapping) and sample.get("metric") == "link-up":
            return dict(sample)
    raise DeveloperApiError(
        "invalid-input",
        "the sandbox measurement carries no link-up sample "
        "(the frozen observation metric vocabulary)",
    )


def run_contract_fulfillment_demo(
    services: RuntimeServices,
    instant: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the deterministic contract-fulfillment demonstration.

    See the module docstring for the composed chain. Returns the full
    response document (canonical-JSON-serializable; the ASGI layer
    serializes it). Identical ``(services-composition, instant)``
    inputs produce the byte-identical document: the boundary mutations
    replay through the durable idempotency ledger, the canonical
    commands replay through the journal's duplicate discipline, the
    plan is a pure translation, the sandbox execution is a fresh
    deterministic composition, and evidence ingest is idempotent.
    """
    if services.execution_factory is None:
        raise DeveloperApiError(
            "invalid-input",
            "the runtime carries no execution provider composition "
            "(the demonstration requires the sandbox execution factory)",
        )
    base = _require_instant(instant)

    inst_create = add_seconds(base, _OFFSET_CREATE)
    inst_offers = add_seconds(base, _OFFSET_OFFERS)
    inst_activate = add_seconds(base, _OFFSET_ACTIVATE)
    inst_bind = add_seconds(base, _OFFSET_BIND)
    inst_reserve = add_seconds(base, _OFFSET_RESERVE)
    inst_exec_activate = add_seconds(base, _OFFSET_EXEC_ACTIVATE)
    inst_measure = add_seconds(base, _OFFSET_MEASURE)
    inst_release = add_seconds(base, _OFFSET_RELEASE)

    key_create = "demo:%s:create" % base
    key_offers = "demo:%s:offers" % base
    key_activate = "demo:%s:activate" % base

    # -- 1. the request boundary leg (intent -> offer -> activation) ----
    created = _drive(
        services,
        "POST",
        "/api/%s/intents" % _API_VERSION,
        _intent_body(base),
        idempotency_key=key_create,
    )
    contract_id = created.data()["id"]

    _drive(
        services,
        "POST",
        "/api/%s/intents/%s/offers" % (_API_VERSION, contract_id),
        {
            "offers": [
                {
                    "ref_kind": "offer",
                    "value": _DEMO_OFFER_VALUE,
                    "provenance": {
                        "issuer": _DEMO_OFFER_ISSUER,
                        "decision_refs": ["demo:offer:v1"],
                    },
                }
            ],
            "recorded_at": inst_offers,
        },
        idempotency_key=key_offers,
    )

    _drive(
        services,
        "POST",
        "/api/%s/intents/%s/activation" % (_API_VERSION, contract_id),
        {
            "activated_at": inst_activate,
            "signature_refs": [
                {"ref_kind": "signature", "value": _DEMO_SIGNATURE_VALUE}
            ],
        },
        idempotency_key=key_activate,
    )

    boundary_trace: List[Dict[str, Any]] = [
        {
            "method": "POST",
            "route": "/api/%s/intents" % _API_VERSION,
            "status": created.status,
            "request_id": created.body.get("request_id", ""),
        }
    ]

    # -- 2. the planning leg (translate -> verify -> bind) ---------------
    contract = services.contracts.contract(contract_id)
    if not contract.accepted_offers:
        raise DeveloperApiError(
            "invalid-input",
            "the demonstration contract carries no accepted offers",
        )
    offer = sorted(contract.accepted_offers, key=lambda ref: ref.value)[0]
    segment_input = SegmentInput(
        offer_reference=offer,
        role="primary",
        operations=("reserve", "activate", "measure", "release"),
        provenance=Provenance(
            issuer=_DEMO_OPTIMIZER,
            decision_refs=("demo:segment:v1",),
        ),
    )
    plan = translate_contract(
        contract,
        (segment_input,),
        provenance=Provenance(
            issuer=_DEMO_PLANNER,
            decision_refs=("demo:contract-fulfillment:v1",),
        ),
    )
    verify_plan_preserves_contract(plan, contract)
    services.contracts.submit(
        BindExecutionArtifact(artifact=plan_reference(plan)),
        recorded_at=inst_bind,
        contract_id=contract_id,
    )
    contract = services.contracts.contract(contract_id)

    # -- 3. the execution leg (sandbox adapter boundary) ------------------
    execution = services.execution_factory()
    adapter = execution.adapter
    segment_id = plan.segments[0].segment_id

    reserved = _require_ok(
        adapter.reserve(
            kind=execution.reserve_kind,
            quantity=execution.reserve_quantity,
            unit=execution.reserve_unit,
            purpose="demo:%s" % contract_id,
            now=inst_reserve,
        ),
        "reserve",
    )
    plan = apply_segment_transition(
        plan, segment_id, "RESERVED", at_instant=inst_reserve
    )

    activation = _require_ok(
        adapter.activate(
            reservation_id=reserved.allocation_id,
            session_id=execution.session_id,
            requirements=None,
            now=inst_exec_activate,
        ),
        "activate",
    )
    plan = apply_segment_transition(
        plan, segment_id, "ACTIVATED", at_instant=inst_exec_activate
    )

    measurement = _require_ok(
        adapter.measure(
            activation_id=activation.activation_id, now=inst_measure
        ),
        "measure",
    )
    plan = apply_segment_transition(
        plan, segment_id, "MEASURED", at_instant=inst_measure
    )

    release = _require_ok(
        adapter.release(activation_id=activation.activation_id, now=inst_release),
        "release",
    )
    plan = apply_segment_transition(
        plan, segment_id, "RELEASED", at_instant=inst_release
    )

    # -- 4. the evidence leg (typed records, idempotent ingest) -----------
    link_up = _link_up_sample(measurement)
    observation = ObservationEvidence(
        subject_ref=activation.activation_id,
        contract_ref=contract_id,
        instant=inst_measure,
        producer=_DEMO_OFFER_ISSUER,
        metric="link-up",
        value=link_up["value"],
        confidence_basis_points=10_000,
        freshness_until=add_seconds(inst_measure, _OFFSET_FRESHNESS),
        source_refs=(measurement.measurement_id,),
    )
    released_segments = sum(
        1 for segment in plan.segments if segment.state == "RELEASED"
    )
    attestation = AttestationEvidence(
        subject_ref=plan.plan_id,
        contract_ref=contract_id,
        instant=inst_release,
        producer=_DEMO_ATTESTOR,
        attestation_kind="controller-verified",
        attested_value=released_segments,
        valid_until=add_seconds(inst_release, _OFFSET_ATTEST_VALIDITY),
        source_refs=(plan.plan_id, activation.activation_id),
    )
    services.evidence.ingest_many((observation, attestation))

    execution_document: Dict[str, Any] = {
        "sandbox": bool(services.sandbox_execution),
        "provider": "deterministic-reference-adapter",
        "adapter_id": execution.adapter_id,
        "access_technology_id": execution.access_technology_id,
        "standard_mechanisms": list(execution.standard_mechanisms),
        "session_id": execution.session_id,
        "reservation_id": reserved.allocation_id,
        "activation_id": activation.activation_id,
        "binding_id": activation.binding_id,
        "measurement_id": measurement.measurement_id,
        "samples": [dict(sample) for sample in measurement.samples],
        "release_id": release.release_id,
        "released_kinds": list(release.released_kinds),
        "segment_states": [
            "PLANNED",
            "RESERVED",
            "ACTIVATED",
            "MEASURED",
            "RELEASED",
        ],
    }

    return {
        "mode": services.mode,
        "environment": services.environment,
        "evidence_class": DEMO_EVIDENCE_CLASS,
        "instant": base,
        "boundary": boundary_trace,
        "contract": contract.to_dict(),
        "plan": plan.to_dict(),
        "execution": execution_document,
        "evidence": [observation.to_dict(), attestation.to_dict()],
    }
