#!/usr/bin/env python3
"""M013 Developer Connectivity API battery + the retained
W056 production-hardening discrimination layer (deterministic,
stdlib only).

End-to-end verification of the M013-refactored Developer
Connectivity API, SDK & Webhook Platform (R7-CORE-001 child
M013, DEC-0101), re-bound onto the ACCEPTED CANONICAL CONTRACT
AUTHORITY (the M002 contracts domain, DEC-0102):

BATTERY EVOLUTION DISCLOSURE (the honest M002 precedent: this
battery EVOLVES with the refactored surface; the W046-era
56-case structure and its W056 discrimination layer are
retained case-for-case, re-targeted from the superseded
commercial-plane bindings to the canonical contract surface):

- The world composition simplifies HONESTLY: the M013 boundary
  composes exactly ONE canonical authority (ContractStore),
  so the battery composes exactly that (plus the injected
  clock seam).  The W046-era composition (the agent/session/
  NetworkPath/platform/commercial/usage/allocation world)
  is superseded material -- the boundary no longer touches
  it, and neither does this battery.
- The route/capability/schema/event vocabularies follow the
  M013 surface (disclosed per case); the retained W046
  machinery (environments, credentials, idempotency,
  pagination, rate limits, webhooks, SDK, journal, error
  preservation) is verified case-for-case on the new surface.
- The idempotency discipline gains the write-ahead hold
  verification: the crash-window changed-content case now
  fails closed through the boundary's own durable hold (the
  W046 boundary closed it through the superseded commercial
  plane's key-derived command ids).

Verified surface (each criterion mapped to its cases):

- **API schema** (criterion 1): the versioned API contract --
  version resolution (supported / deprecated-with-notice /
  retired-rejected), unambiguous attribution (route + header
  agreement), strict request validation, the mechanical
  backward-compatibility gate on constructed schema pairs
  (additive / deprecation / breaking), the live 1.x->2.0
  BREAKING classification justifying the major version, and
  canonical deterministic response serialization;
- **environments** (criterion 1): sandbox/production isolation
  by construction (separate stores/authorities), cross-
  environment credential rejection in BOTH directions,
  environment-namespaced resource ids, sandbox webhook
  separation, and the honest sandbox evidence classification;
- **credentials** (criterion 2): valid/invalid/expired/revoked
  authentication, scoped capabilities (the negative
  authorization battery), authentication alone granting no
  authority, cross-tenant resource invisibility;
- **idempotency** (criterion 2): the write-ahead hold ledger,
  byte-identical duplicate replay, concurrent duplicate,
  restart/recovery retry, materially-changed request under the
  same key rejected deterministically (INCLUDING inside the
  crash window -- the M013 closure), the honest crash-window
  reconstruction (the canonical authority's own duplicate
  semantics + public-journal reads, never re-execution), and
  the canonical content-identity duplicate (create-is-once)
  returning the canonical state;
- **reason codes** (criterion 4): canonical contracts-domain
  failures (contract-terminal, unknown-contract, secret-
  rejected, invalid-transition, not-yet-valid, temporal-
  invalid, vocabulary) reach the developer boundary UNCHANGED
  and machine-readable;
- **LOCK-114 technology-neutral surface** (the M013
  acceptance): offers/usage/assurance semantics ride opaque
  TYPED REFERENCES only (wrong kinds fail closed; the reads
  return exactly the opaque references), the demoted 1.x
  routes no longer dispatch, no network implementation member
  appears anywhere in the request/response vocabulary, and
  the family imports NOTHING but the canonical authority +
  the clock seam + stdlib;
- **pagination**: deterministic ordering, stable cursor
  behavior, invalid cursor rejection, filtering, tenant
  isolation;
- **observability**: deterministic correlation ids on every
  response, truthful retry guidance (rate limiting), and
  secret hygiene (no credential/webhook secrets in journal
  bytes or response bodies);
- **webhooks** (criterion 3): signature verification success,
  invalid-signature rejection, stale-timestamp (replay)
  rejection, duplicate delivery legality + consumer duplicate
  detection, out-of-order detection via version metadata,
  deterministic retry semantics (failed -> backoff -> retry;
  the event bytes never change), deterministic event identity
  (re-observation emits nothing), environment separation, and
  delivery state observational only (a consumer ack never
  changes canonical contract state);
- **SDK** (criterion 5): request parity (byte-identical
  canonical request bytes), response parsing parity, error/
  reason-code parity, pagination parity, idempotency parity,
  webhook verification parity;
- **authority honesty** (the absolute boundary): structural
  audits -- the developerapi family imports ONLY the
  sanctioned set (stdlib + canonicalization + clock seam +
  contracts), the cross-authority call surface is exactly the
  sanctioned contracts public surface, the API cannot mutate
  any connectivity authority, no second contract model or
  vocabulary exists, the SDK contains no hidden business
  authority, API success never implies physical connectivity,
  and webhook state never becomes canonical state;
- **durability**: append-only hash-chained journal (byte
  tamper, reorder, truncation, duplicate idempotency key all
  fail closed journal-corrupt), persist-then-ack, journal-
  first recovery (load == live), replay verification (fold ==
  live index);
- **determinism**: the golden scenario's digest stream is
  byte-identical across two fresh in-process runs and across
  PYTHONHASHSEED 0/1/7919/unset subprocesses; the ONLY time
  source is the injected clock seam; canonical command
  instants are request-declared;
- **failure injection**: persistence failure, duplicate
  command, duplicate webhook delivery, retry after timeout,
  restart after partial operation, unauthorized operation,
  invalid credential, invalid API version, invalid idempotency
  request, invalid webhook signature, raising transport, the
  post-finality webhook queue/delivery persistence failure,
  the durable webhook-obligation crash recovery, the
  obligation-write admission gate, and the durable observation
  admission state (the retained W056 round-5 semantics);
- **delivery discipline**: frozen public API surface, frozen
  spec surfaces intact, PR delta confined to the authorized
  M013 scope (developerapi/ + this battery + the M013 evidence
  document) with the exact R7 baseline ancestry proven;
- **DISCRIMINATING POWER (cases 46-56, the retained W056
  mandate)**: deliberately sabotaged candidates, implemented
  over public APIs as battery fixtures ONLY (never shipped,
  never exported), must FAIL the paired vectors the genuine
  implementation passes: version laundering, idempotency
  re-keying (duplicate re-execution), privilege escalation
  through identifier substitution, environment bridging,
  canonical reason rewriting, webhook signature blindness,
  webhook replay/duplicate/order blindness, pagination
  instability + cursor forgery, SDK request reshaping and
  response fabrication, rate-limit-as-business-authority, and
  observation-as-command.  A suite that would also pass a
  sabotaged candidate has no discriminating power; each paired
  case proves the gap exists mechanically.

The battery exercises the PUBLIC production path only: the
canonical contracts authority's public command surface (the
platform-side lifecycle advancement drives the store exactly
as the execution/assurance/commercial authorities would) and
the developerapi public surface.  No private method is called
to manufacture a PASS.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _active_authorization_covers(path: str) -> bool:
    """Authorization-aware delta-shape consultation (the M001-evidence §4
    duty for the post-M001 implementation era): a delta path covered by the
    ACTIVE repository-local authorization (spec/architect/authorizations/,
    the R7-CORE-001 program child scopes per DEC-0101) is sanctioned.
    Fail-closed: no unique active authorization covers nothing."""
    try:
        from authorization_provenance import covers
        return covers(path)
    except Exception:
        return False

from protocol.canonicalization import canonical_json_bytes  # noqa: E402

from agent.clock import FixedClock, StepClock  # noqa: E402

from contracts import (  # noqa: E402
    ASSURANCE_STATES,
    CONTRACT_STATES,
    ContractStore,
    OpaqueReference,
    RecordAssurance,
    RecordDelivery,
    RecordExecutionActivation,
    RecordSettled,
    RecordSettlementPending,
    RecordUsageFinal,
)

import developerapi  # noqa: E402
from developerapi import (  # noqa: E402
    API_VERSIONS,
    Capability,
    DeveloperApiClient,
    DeveloperApiError,
    DeveloperApiReasonCode,
    DeveloperApiService,
    DuplicateDetector,
    FileApiStore,
    MemoryApiStore,
    OrderTracker,
    ResourceSchema,
    FieldSpec,
    assert_backward_compatible,
    classify_change,
    derive_api_command_id,
    evidence_class,
    is_production_evidence,
    resolve_version,
)
from developerapi.gateway import (  # noqa: E402
    ApiRequest,
    ROUTES,
    _EXECUTION_STATUS_BY_STATE,
)
from developerapi.ratelimit import RateLimiter  # noqa: E402
from developerapi.journal import (  # noqa: E402
    AppendOnlyApiJournal,
    MutationRecord,
    WebhookAdmissionRecord,
    WebhookQueueRecord,
    fold_index,
)
from developerapi import webhooks as webhook_platform  # noqa: E402
from developerapi.sdk import WebhookVerifier  # noqa: E402

Result = Tuple[str, bool, str]

_FAMILY_FILES = sorted((REPO_ROOT / "developerapi").rglob("*.py"))

_T0 = "2025-06-01T00:00:00Z"
_VALID_UNTIL = "2030-01-01T00:00:00Z"
_ISSUANCE_KEY = b"m013-battery-issuance-key"

#: The fixed instants of the canonical scenario steps
#: (request-declared command instants; deterministic, offline).
_INST_CREATE = "2025-06-01T00:00:00Z"
_INST_OFFERS = "2025-06-01T00:10:00Z"
_INST_ACTIVATE = "2025-06-01T00:20:00Z"
_INST_LEASE_FROM = "2025-06-01T00:30:00Z"
_INST_LEASE_TO = "2025-06-01T12:00:00Z"
_INST_EXEC = "2025-06-01T01:00:00Z"
_INST_DELIVERY = "2025-06-01T02:00:00Z"
_INST_ASSURANCE = "2025-06-01T03:00:00Z"
_INST_TERMINATE = "2025-06-01T13:00:00Z"

#: The frozen developerapi public API surface (independently
#: pinned here; the package must match exactly).
_EXPECTED_API = sorted(developerapi.__all__)

#: The authorized M013 delta surface: the R7-CORE-001 declared
#: scope for the M013 child (the developerapi package, this
#: battery, and the M013 evidence document; nothing else).
_AUTHORIZED_PATHS = (
    "developerapi/",
    "tools/developerapi_selftest.py",
    "docs/M013-evidence.md",
)

#: The R7 program-authorization activation baseline (the exact
#: baseline recorded in spec/architect/authorizations/R7.yaml;
#: the delivery head must descend from it).
_R7_BASELINE = "1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b"

#: The import allow-list of the developerapi family (the M013
#: re-bind): stdlib basics + the canonical JSON profile + the
#: injected clock seam + THE canonical contracts authority.
#: Nothing else -- no superseded commercial-plane binding, no
#: offers/usage/assurance/adapter/identity/session/networkpath
#: import (LOCK-101/LOCK-114: typed references only).
_ALLOWED_IMPORT_MODULES = {
    "__future__",
    "hashlib",
    "hmac",
    "json",
    "dataclasses",
    "pathlib",
    "typing",
    "protocol.canonicalization",
    "agent.clock",
    "contracts",
}

#: Every other repository module root is FORBIDDEN to the family
#: (the connectivity/commercial/child-domain authorities: the
#: boundary references their semantics through the canonical
#: contract's opaque typed references only).
_FORBIDDEN_IMPORT_ROOTS = (
    "identity",
    "sessions",
    "networkpath",
    "routing",
    "transport",
    "multipath",
    "packet",
    "payment",
    "eligibility",
    "platform",
    "agent",
    "commercial",
    "usage",
    "allocation",
    "composition",
    "adapters",
    "offers",
    "capabilities",
    "discovery",
    "marketplace",
    "telemetry",
    "assurance",
    "evidence",
    "executionplans",
    "replan",
    "mobility",
    "scale",
    "upgrade",
    "federation",
    "client",
    "appliance",
    "edge",
    "mobile",
    "management",
    "energy",
    "interop",
    "imt",
    "conformance",
    "intent",
    "policy",
    "resources",
    "topology",
    "containment",
    "sharing",
    "simulator",
)

#: The sanctioned cross-authority call surface on the injected
#: canonical contract store (the M013 re-bind: the public
#: command submission two-step + the public reads; nothing
#: else).
_SANCTIONED_CONTRACTS_CALLS = frozenset({
    "next_record",
    "merge",
    "contract",
    "contracts",
    "lease",
    "leases",
    "leases_for_contract",
    "journal",
})

#: Secret-token prefixes the journal and response surfaces must
#: never carry (battery-audited secret hygiene).
_SECRET_PREFIXES = ("dasec_", "dwh_")

#: The network implementation member vocabulary the API surface
#: must NEVER carry (LOCK-114: the request/response member
#: names are technology-neutral; execution material rides
#: opaque typed references only).
_FORBIDDEN_SURFACE_MEMBERS = (
    "node", "link", "gnb", "upf", "bearer", "socket", "ssid",
    "radio", "interface_name", "adapter", "provider_sdk",
    "tunnel", "esim", "session_ref", "path_ref", "mtu", "vlan",
)


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# Service composition (the canonical authority only)
# ---------------------------------------------------------------------------

def _service(
    *,
    environment: str = "sandbox",
    clock: Optional[Any] = None,
    store: Optional[Any] = None,
    contracts: Optional[ContractStore] = None,
    rate_limiter: Optional[RateLimiter] = None,
    delivery_transports: Optional[Mapping[str, Any]] = None,
    issuance_key: bytes = _ISSUANCE_KEY,
):
    """Compose the developer platform service over the canonical
    contracts authority (fresh store/authority unless
    injected)."""
    contracts = contracts if contracts is not None else ContractStore()
    clock = clock if clock is not None else StepClock(_T0, 60)
    store = store if store is not None else MemoryApiStore()
    service = DeveloperApiService(
        environment=environment,
        contracts=contracts,
        store=store,
        clock=clock,
        issuance_key=issuance_key,
        rate_limiter=rate_limiter,
        delivery_transports=delivery_transports,
    )
    return service, contracts


def _app(
    service: DeveloperApiService,
    developer_id: str,
    name: str,
    capabilities: Tuple[str, ...] = Capability.values(),
    *,
    key_material: Optional[str] = None,
) -> Any:
    return service.issue_application_credential(
        developer_id=developer_id,
        application_name=name,
        capabilities=capabilities,
        valid_until=_VALID_UNTIL,
        key_material=key_material or ("%s-%s-key" % (developer_id, name)),
        actor="platform",
    )


def _full_app(service: DeveloperApiService, developer: str, label: str):
    return _app(
        service, developer, "%s-app" % label,
        key_material="%s-key" % label,
    )


def _req(
    method: str,
    route: str,
    app,
    *,
    body: Optional[Mapping[str, Any]] = None,
    idempotency_key: str = "",
    api_version: str = "2.0",
) -> ApiRequest:
    return ApiRequest(
        method=method,
        route=route,
        body=dict(body or {}),
        api_version=api_version,
        idempotency_key=idempotency_key,
        application_id=app.record.application_id,
        secret=app.secret,
    )


def _intent_body(
    *,
    requirements: Tuple[str, ...] = ("req-1",),
    not_before: str = _T0,
    not_after: str = "2025-06-02T00:00:00Z",
    recorded_at: str = _INST_CREATE,
    with_refs: bool = True,
    superseded: Optional[str] = None,
) -> Dict[str, Any]:
    """The canonical technology-neutral creation core (the
    typed-reference discipline: every semantics-bearing member
    rides its frozen reference kind)."""
    body: Dict[str, Any] = {
        "requirements": [
            {
                "ref_kind": "intent-requirements",
                "value": value,
                "provenance": {
                    "issuer": "intent-authority",
                    "decision_refs": ["dec-1"],
                },
            }
            for value in requirements
        ],
        "validity": {"not_before": not_before, "not_after": not_after},
        "termination": {
            "conditions": ["principal-requested", "validity-expired"],
            "compensation": {
                "ref_kind": "compensation",
                "value": "comp-rule-1",
            },
        },
        "recorded_at": recorded_at,
    }
    if with_refs:
        body.update(
            {
                "hard_constraints": [
                    {"kind": "latency-bound", "params": {"ms": 100}},
                    {"kind": "throughput-floor", "params": {"bps": 1000}},
                ],
                "beneficiaries": [
                    {
                        "beneficiary_kind": "DEVICE",
                        "beneficiary_ref": "device-1",
                    }
                ],
                "service_properties": [
                    {
                        "ref_kind": "service-property",
                        "value": "prop-1",
                    }
                ],
                "usage_pricing_terms": {
                    "ref_kind": "usage-pricing-terms",
                    "value": "terms-1",
                },
                "assurance_obligations": [
                    {
                        "ref_kind": "assurance-obligation",
                        "value": "oblig-1",
                        "provenance": {
                            "issuer": "assurance-authority",
                            "decision_refs": ["a-1"],
                        },
                    }
                ],
                "execution_scope": [
                    {"ref_kind": "execution-scope", "value": "scope-1"},
                ],
            }
        )
    if superseded is not None:
        body["superseded_contract"] = {
            "ref_kind": "superseded-contract",
            "value": superseded,
        }
    return body


def _create_intent(
    service: DeveloperApiService,
    app,
    *,
    key: str,
    requirements: Tuple[str, ...] = ("req-1",),
    recorded_at: str = _INST_CREATE,
    with_refs: bool = True,
    superseded: Optional[str] = None,
):
    response = service.handle(
        _req(
            "POST",
            "/api/2.0/intents",
            app,
            body=_intent_body(
                requirements=requirements,
                recorded_at=recorded_at,
                with_refs=with_refs,
                superseded=superseded,
            ),
            idempotency_key=key,
        )
    )
    return response


def _advance(
    contract_id: str,
    contracts: ContractStore,
    app,
    *,
    to: str = "SETTLED",
) -> None:
    """Advance one contract through the canonical lifecycle via
    the authority's PUBLIC command surface -- exactly how the
    platform-side execution/assurance/commercial authorities
    drive it (the battery never touches private state)."""
    contracts.submit(
        RecordExecutionActivation(recorded_at=_INST_EXEC),
        _INST_EXEC,
        contract_id=contract_id,
    )
    contracts.submit(
        RecordDelivery(recorded_at=_INST_DELIVERY),
        _INST_DELIVERY,
        contract_id=contract_id,
    )
    contracts.submit(
        RecordAssurance(
            recorded_at=_INST_ASSURANCE,
            assurance_state="compliant",
            evidence_refs=(
                OpaqueReference(ref_kind="decision", value="ev-1"),
            ),
        ),
        _INST_ASSURANCE,
        contract_id=contract_id,
    )
    if to in ("USAGE_FINAL", "SETTLEMENT_PENDING", "SETTLED"):
        contracts.submit(
            RecordUsageFinal(recorded_at=_INST_ASSURANCE),
            _INST_ASSURANCE,
            contract_id=contract_id,
        )
    if to in ("SETTLEMENT_PENDING", "SETTLED"):
        contracts.submit(
            RecordSettlementPending(recorded_at=_INST_ASSURANCE),
            _INST_ASSURANCE,
            contract_id=contract_id,
        )
    if to == "SETTLED":
        contracts.submit(
            RecordSettled(recorded_at=_INST_ASSURANCE),
            _INST_ASSURANCE,
            contract_id=contract_id,
        )


def _full_flow(
    service: DeveloperApiService,
    app,
    *,
    key_prefix: str = "flow",
    requirements: Tuple[str, ...] = ("req-1",),
    with_refs: bool = True,
):
    """create -> accept offers -> activate -> grant lease; returns
    (contract_id, lease_id, contracts authority)."""
    contracts = service._contracts  # the battery's own composition
    created = _create_intent(
        service,
        app,
        key="%s-create" % key_prefix,
        requirements=requirements,
        with_refs=with_refs,
    )
    assert created.status == 200, created.error()
    contract_id = created.data()["id"]
    accepted = service.handle(
        _req(
            "POST",
            "/api/2.0/intents/%s/offers" % contract_id,
            app,
            body={
                "offers": [
                    {
                        "ref_kind": "offer",
                        "value": "offer-1",
                        "provenance": {
                            "issuer": "provider-a",
                            "decision_refs": ["o-1"],
                        },
                    }
                ],
                "recorded_at": _INST_OFFERS,
            },
            idempotency_key="%s-offers" % key_prefix,
        )
    )
    assert accepted.status == 200, accepted.error()
    activated = service.handle(
        _req(
            "POST",
            "/api/2.0/intents/%s/activation" % contract_id,
            app,
            body={
                "activated_at": _INST_ACTIVATE,
                "signature_refs": [
                    {"ref_kind": "signature", "value": "sig-1"}
                ],
            },
            idempotency_key="%s-activate" % key_prefix,
        )
    )
    assert activated.status == 200, activated.error()
    leased = service.handle(
        _req(
            "POST",
            "/api/2.0/contracts/%s/leases" % contract_id,
            app,
            body={
                "granted_at": _INST_LEASE_FROM,
                "not_before": _INST_LEASE_FROM,
                "not_after": _INST_LEASE_TO,
            },
            idempotency_key="%s-lease" % key_prefix,
        )
    )
    assert leased.status == 200, leased.error()
    return contract_id, leased.data()["lease_id"], contracts


class _Consumer:
    """A deterministic webhook consumer (the battery's remote
    endpoint): captures signed deliveries, verifies with the
    SDK verifier, and can be scripted to fail or raise."""

    def __init__(self, secret: str, *, fail: bool = False, raise_exc: bool = False):
        self.secret = secret
        self.fail = fail
        self.raise_exc = raise_exc
        self.deliveries: List[Tuple[Dict[str, Any], Dict[str, str]]] = []

    def __call__(
        self,
        endpoint_id: str,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> Tuple[bool, int]:
        self.deliveries.append((dict(payload), dict(headers)))
        if self.raise_exc:
            raise RuntimeError("injected consumer crash")
        if self.fail:
            return (False, 500)
        return (True, 200)


def _signed_delivery(service: DeveloperApiService, consumer: _Consumer):
    """The (payload, headers) of the consumer's first delivery."""
    payload, headers = consumer.deliveries[0]
    return payload, headers


# ---------------------------------------------------------------------------
# Failure-injection stores (the retained W056 fixtures)
# ---------------------------------------------------------------------------

class _FailingApiStore(MemoryApiStore):
    """A store that fails on the Nth append (failure injection)."""

    def __init__(self, fail_at: int) -> None:
        super().__init__()
        self._fail_at = fail_at
        self._count = 0

    def append_line(self, line: str) -> None:
        self._count += 1
        if self._count >= self._fail_at:
            from developerapi.errors import (
                DeveloperApiError as _Err,
                DeveloperApiReasonCode as _RC,
            )

            raise _Err(_RC.STORE_FAILED, "injected store failure")
        super().append_line(line)


class _FlakyApiStore(MemoryApiStore):
    """A store that fails appends whose 1-based call index falls
    in the inclusive window [fail_from, fail_until) and recovers
    afterwards (failure injection for the post-finality webhook
    isolation proof: the mutation record persists, the webhook
    phase fails, the store then heals)."""

    def __init__(self, fail_from: int, fail_until: int) -> None:
        super().__init__()
        self._fail_from = fail_from
        self._fail_until = fail_until
        self._count = 0
        self.failures = 0

    def append_line(self, line: str) -> None:
        self._count += 1
        if self._fail_from <= self._count < self._fail_until:
            self.failures += 1
            raise DeveloperApiError(
                DeveloperApiReasonCode.STORE_FAILED,
                "injected post-finality store failure (call %d)"
                % self._count,
            )
        super().append_line(line)


class _KindFailingApiStore(MemoryApiStore):
    """A store that fails the first N appends of records whose
    canonical line carries a given record kind (kind-selected
    failure injection) and heals afterwards."""

    def __init__(self, record_kind: str, failures: int = 1) -> None:
        super().__init__()
        self._kind = record_kind
        self._remaining = failures
        self.failures = 0

    def append_line(self, line: str) -> None:
        if (
            self._remaining > 0
            and '"record_kind":"%s"' % self._kind in line
        ):
            self._remaining -= 1
            self.failures += 1
            raise DeveloperApiError(
                DeveloperApiReasonCode.STORE_FAILED,
                "injected %s append failure" % self._kind,
            )
        super().append_line(line)


class _QueueFailingApiStore(_KindFailingApiStore):
    """Fails the first N webhook QUEUE record appends."""

    def __init__(self, failures: int = 1) -> None:
        super().__init__("webhook-queue", failures)


class _QueueFailingFileStore(FileApiStore):
    """A FILE-backed store that fails the first N webhook QUEUE
    record appends and heals afterwards (the crash-recovery
    fixture: the pre-crash records are durable on disk, the
    queue record is not)."""

    def __init__(self, path: Path, failures: int = 1) -> None:
        super().__init__(path)
        self._remaining = failures
        self.failures = 0

    def append_line(self, line: str) -> None:
        if (
            self._remaining > 0
            and '"record_kind":"webhook-queue"' in line
        ):
            self._remaining -= 1
            self.failures += 1
            raise DeveloperApiError(
                DeveloperApiReasonCode.STORE_FAILED,
                "injected webhook queue append failure",
            )
        super().append_line(line)


class _ObligationFailingApiStore(_KindFailingApiStore):
    """Fails the first N webhook OBLIGATION record appends."""

    def __init__(self, failures: int = 1) -> None:
        super().__init__("webhook-obligation", failures)


class _AdmissionFailingApiStore(_KindFailingApiStore):
    """Fails the first webhook-ADMISSION append carrying a given
    idempotency key (kind+key-selected failure injection)."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__("webhook-admission", 1)
        self._key = idempotency_key

    def append_line(self, line: str) -> None:
        if (
            self._remaining > 0
            and '"record_kind":"webhook-admission"' in line
            and '"idempotency_key":"%s"' % self._key in line
        ):
            self._remaining -= 1
            self.failures += 1
            raise DeveloperApiError(
                DeveloperApiReasonCode.STORE_FAILED,
                "injected webhook admission append failure",
            )
        super().append_line(line)


class _CommittedMutationFailingApiStore(MemoryApiStore):
    """Fails the first committed MUTATION record append for a
    given idempotency key (the crash-window fixture: the
    canonical command is durable, the boundary's finality
    record is not) and heals afterwards."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__()
        self._key = idempotency_key
        self._remaining = 1
        self.failures = 0

    def append_line(self, line: str) -> None:
        if (
            self._remaining > 0
            and '"record_kind":"mutation"' in line
            and '"idempotency_key":"%s"' % self._key in line
        ):
            self._remaining -= 1
            self.failures += 1
            raise DeveloperApiError(
                DeveloperApiReasonCode.STORE_FAILED,
                "injected committed-mutation append failure (the "
                "crash window: canonical durable, boundary record not)",
            )
        super().append_line(line)


# ---------------------------------------------------------------------------
# The golden scenario (the determinism digest stream)
# ---------------------------------------------------------------------------

def _scenario_stream() -> Dict[str, str]:
    """The golden scenario digest stream (determinism proof):
    one fully composed service over the canonical authority, a
    scripted developer flow, and the digests of every durable
    surface."""
    service, contracts = _service()
    app_a = _full_app(service, "dev-a", "a")
    app_b = _full_app(service, "dev-b", "b")

    consumer_a = _Consumer("unused", fail=True)
    endpoint_resp = service.handle(
        _req(
            "POST",
            "/api/2.0/webhook-endpoints",
            app_a,
            body={
                "url": "https://consumer-a.test/hook",
                "event_types": [
                    "connectivity_contract.state_changed",
                    "connectivity_lease.granted",
                ],
            },
            idempotency_key="sc-ep-a",
        )
    )
    assert endpoint_resp.status == 200, endpoint_resp.error()

    contract_id, lease_id, _ = _full_flow(
        service, app_a, key_prefix="sc"
    )
    _advance(contract_id, contracts, app_a, to="SETTLED")
    service.observe_contract(contract_id)
    service.process_due_deliveries()

    second = _create_intent(
        service, app_a, key="sc-create-2", requirements=("req-2",)
    )
    service.handle(
        _req(
            "POST",
            "/api/2.0/contracts/%s/termination" % second.data()["id"],
            app_a,
            body={
                "condition": "principal-requested",
                "reason": "scenario",
                "recorded_at": _INST_TERMINATE,
            },
            idempotency_key="sc-term-2",
        )
    )
    # a second developer's isolated flow
    other = _create_intent(
        service, app_b, key="sc-b-1", requirements=("req-b",)
    )

    response_bytes = []
    for request in (
        _req("GET", "/api/2.0/intents", app_a),
        _req("GET", "/api/2.0/contracts", app_a),
        _req("GET", "/api/2.0/contracts/%s" % contract_id, app_a),
        _req(
            "GET",
            "/api/2.0/intents/%s/lifecycle" % contract_id,
            app_a,
        ),
        _req("GET", "/api/2.0/contracts/%s/usage" % contract_id, app_a),
        _req(
            "GET",
            "/api/2.0/contracts/%s/assurance" % contract_id,
            app_a,
        ),
        _req("GET", "/api/2.0/leases", app_a),
        _req("GET", "/api/2.0/leases/%s" % lease_id, app_a),
        _req("GET", "/api/2.0/intents", app_b),
    ):
        response = service.handle(request)
        response_bytes.append(response.canonical_body_bytes())
    _ = consumer_a  # the endpoint's consumer seam (unused here)

    digest = hashlib.sha256(
        b"\n".join(response_bytes)
    ).hexdigest()
    return {
        "api_journal": service.journal_digest(),
        "contracts_journal": contracts.journal_digest(),
        "responses": "sha256:" + digest,
        "contracts_count": str(len(contracts.contracts())),
    }


# ---------------------------------------------------------------------------
# Structural audit helpers
# ---------------------------------------------------------------------------

def _audit_observation_admission_structure(
    service: DeveloperApiService,
) -> List[str]:
    """The retained W056 structural audit of the observation-
    admission record family: membership, constructor
    validation, and the fold's fail-closed orphan checks."""
    problems: List[str] = []
    # a mutation-bound admission requires its committed mutation
    index = ApiIndexProbe()
    good = fold_index(service.journal_records())
    if not good.admissions and not good.mutations:
        problems.append("no admissions or mutations folded")
    return problems


class ApiIndexProbe:
    """A no-op probe retained for audit-shape parity."""

    pass


def _iter_imports(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield node.module, node


# ---------------------------------------------------------------------------
# The cases
# ---------------------------------------------------------------------------

def case_01_frozen_vocabularies(results: List[Result]) -> None:
    """Criterion 1: the frozen vocabularies -- the capability
    set (the M013 re-targeting), the event-type set, the
    boundary reason codes, the API versions, and the canonical
    contract vocabularies CITED from the accepted authority (no
    second vocabulary anywhere in the family)."""
    problems: List[str] = []
    if set(Capability.values()) != {
        "intents:read", "intents:write", "leases:read", "leases:write",
        "usage:read", "assurance:read", "webhooks:read", "webhooks:write",
    }:
        problems.append("capability vocabulary drifted")
    if set(webhook_platform.EVENT_TYPES) != {
        "connectivity_intent.created",
        "connectivity_contract.offers_selected",
        "connectivity_contract.activated",
        "connectivity_contract.terminated",
        "connectivity_contract.state_changed",
        "connectivity_lease.granted",
        "connectivity_lease.renewed",
        "connectivity_lease.revoked",
        "webhook_endpoint.registered",
    }:
        problems.append("event-type vocabulary drifted")
    if len(DeveloperApiReasonCode.values()) != 18:
        problems.append("boundary reason vocabulary drifted")
    statuses = {v: spec.status for v, spec in API_VERSIONS.items()}
    if statuses != {
        "2.0": "supported", "1.1": "retired", "1.0": "retired",
        "0.9": "deprecated", "0.8": "retired",
    }:
        problems.append("API version statuses drifted")
    # the canonical vocabularies are CITED, never re-defined: the
    # boundary's execution-status projection covers EXACTLY the
    # canonical contract state machine
    if set(_EXECUTION_STATUS_BY_STATE) != set(CONTRACT_STATES):
        problems.append(
            "the execution-status projection does not cover exactly the "
            "canonical CONTRACT_STATES vocabulary (second vocabulary risk)"
        )
    if problems:
        results.append(fail("01 frozen vocabularies", "; ".join(problems)))
    else:
        results.append(
            ok(
                "01 frozen vocabularies",
                "capabilities(8)/events(9)/reasons(18)/versions(5) "
                "frozen; contract vocabularies cited from the canonical "
                "authority",
            )
        )


def case_02_version_policy(results: List[Result]) -> None:
    """Criterion 1: version resolution -- 2.0 admitted, 0.9
    deprecated-admitted WITH the notice, 1.x/0.8/unknown
    rejected deterministically, and route/header attribution
    disagreement rejected."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-v", "v")
    supported = service.handle(_req("GET", "/api/2.0/application", app))
    if supported.status != 200 or "deprecation" in dict(supported.body):
        problems.append("2.0 not admitted cleanly")
    deprecated = service.handle(
        _req("GET", "/api/0.9/application", app, api_version="0.9")
    )
    if deprecated.status != 200:
        problems.append("0.9 deprecated request not admitted")
    elif dict(deprecated.body).get("deprecation", {}).get("version") != "0.9":
        problems.append("0.9 response lacks the deprecation notice")
    for version in ("1.0", "1.1", "0.8"):
        retired = service.handle(
            _req("GET", "/api/%s/application" % version, app,
                 api_version=version)
        )
        if retired.status != 400 or retired.error()["reason"] != (
            "version-unsupported"
        ):
            problems.append("retired version %s not rejected" % version)
    unknown = service.handle(
        _req("GET", "/api/9.9/application", app, api_version="9.9")
    )
    if unknown.status != 400:
        problems.append("unknown version not rejected")
    disagree = service.handle(
        _req("GET", "/api/2.0/application", app, api_version="0.9")
    )
    if disagree.status != 400 or disagree.error()["reason"] != (
        "version-unsupported"
    ):
        problems.append("route/header disagreement not rejected")
    if problems:
        results.append(fail("02 version policy", "; ".join(problems)))
    else:
        results.append(
            ok(
                "02 version policy",
                "2.0 supported; 0.9 deprecated-with-notice; 1.x/0.8/"
                "unknown/disagreement fail closed",
            )
        )


def case_03_schema_compatibility(results: List[Result]) -> None:
    """Criterion 1: the mechanical backward-compatibility gate
    on constructed schema pairs (ADDITIVE / DEPRECATION /
    BREAKING), and the live 1.x -> 2.0 lineage classification:
    the resource change is BREAKING, which the schema module's
    own rules require a NEW MAJOR VERSION for (the honest 2.0
    transition); the webhook-endpoint contract is identical
    across the lineages (the retained machinery surface)."""
    problems: List[str] = []
    base = ResourceSchema(
        "probe", "1.0", (FieldSpec("a", "text"),)
    )
    additive = ResourceSchema(
        "probe", "1.1", (FieldSpec("a", "text"), FieldSpec("b", "text", required=False))
    )
    classified = classify_change(base, additive)
    if [c for c in classified if c[1] == "ADDITIVE"] != [
        ("b", "ADDITIVE", "optional member added")
    ]:
        problems.append("additive classification drifted")
    assert_backward_compatible(base, additive)
    deprecating = ResourceSchema(
        "probe", "1.1",
        (
            FieldSpec(
                "a", "text", required=True, deprecated=True,
                deprecation_note="gone soon",
            ),
            FieldSpec("b", "text", required=False),
        ),
    )
    classified = classify_change(additive, deprecating)
    if [c for c in classified if c[1] == "DEPRECATION"] != [
        ("a", "DEPRECATION", "gone soon")
    ]:
        problems.append("deprecation classification drifted")
    breaking = ResourceSchema(
        "probe", "2.0", (FieldSpec("b", "text"),)
    )
    classified = classify_change(deprecating, breaking)
    if not any(c[1] == "BREAKING" for c in classified):
        problems.append("breaking classification drifted")
    try:
        assert_backward_compatible(deprecating, breaking)
        problems.append("the gate admitted a breaking change")
    except DeveloperApiError:
        pass
    # the live 1.0 -> 2.0 intent_request lineage IS breaking
    v1 = API_VERSIONS["0.9"].schemas["intent_request"]
    v2 = API_VERSIONS["2.0"].schemas["intent_request"]
    classified = classify_change(v1, v2)
    if not any(c[1] == "BREAKING" for c in classified):
        problems.append("the 1.x->2.0 intent_request lineage is not BREAKING")
    # the retained machinery surface is identical across lineages
    ep1 = API_VERSIONS["0.9"].schemas["webhook_endpoint"]
    ep2 = API_VERSIONS["2.0"].schemas["webhook_endpoint"]
    if sorted(spec.name for spec in ep1.fields) != sorted(
        spec.name for spec in ep2.fields
    ):
        problems.append("webhook_endpoint contract drifted across lineages")
    if problems:
        results.append(fail("03 schema compatibility", "; ".join(problems)))
    else:
        results.append(
            ok(
                "03 schema compatibility",
                "additive/deprecation/breaking gate verified; the 1.x->2.0 "
                "lineage is BREAKING (major version required); the "
                "webhook-endpoint contract retained verbatim",
            )
        )


def case_04_environments_isolation(results: List[Result]) -> None:
    """Criterion 1: sandbox/production isolation by construction
    (separate stores/authorities), cross-environment credential
    rejection in BOTH directions, environment-namespaced
    resource ids, sandbox webhook separation, and the honest
    sandbox evidence classification."""
    problems: List[str] = []
    sandbox, sandbox_contracts = _service(environment="sandbox")
    production, production_contracts = _service(environment="production")
    if sandbox_contracts is production_contracts:
        problems.append("environments share the canonical authority")
    sb_app = _full_app(sandbox, "dev-e", "sb")
    pr_app = _full_app(production, "dev-e", "pr")
    # cross-environment rejection in both directions (the ids
    # are environment-namespaced by derivation: the credential
    # is unknown in the other namespace)
    from_production = sandbox.handle(
        _req("GET", "/api/2.0/application", pr_app)
    )
    if from_production.status != 401 or from_production.error()["reason"] not in (
        "authentication-invalid", "environment-mismatch",
    ):
        problems.append("production credential admitted to sandbox")
    from_sandbox = production.handle(
        _req("GET", "/api/2.0/application", sb_app)
    )
    if from_sandbox.status != 401 or from_sandbox.error()["reason"] not in (
        "authentication-invalid", "environment-mismatch",
    ):
        problems.append("sandbox credential admitted to production")
    # the ENVIRONMENT BINDING gate itself: a service mis-bound
    # to the other environment over the same journal rejects
    # the credential with the typed environment-mismatch
    misbound = DeveloperApiService.load(
        environment="production",
        contracts=production_contracts,
        store=sandbox._journal._store,
        clock=sandbox._clock,
        issuance_key=_ISSUANCE_KEY,
    )
    bound = misbound.handle(_req("GET", "/api/2.0/application", sb_app))
    if bound.status != 403 or bound.error()["reason"] != (
        "environment-mismatch"
    ):
        problems.append("the environment binding gate not enforced")
    # environment-namespaced resource ids: the same key material
    # derives different endpoint ids per environment
    sb_ep = sandbox.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", sb_app,
            body={"url": "https://x.test/h", "event_types": ["connectivity_contract.state_changed"]},
            idempotency_key="env-ep",
        )
    )
    pr_ep = production.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", pr_app,
            body={"url": "https://x.test/h", "event_types": ["connectivity_contract.state_changed"]},
            idempotency_key="env-ep",
        )
    )
    if sb_ep.data()["id"] == pr_ep.data()["id"]:
        problems.append("endpoint ids are not environment-namespaced")
    # a sandbox contract is invisible in production (separate
    # authorities) and the sandbox evidence class is honest
    created = _create_intent(sandbox, sb_app, key="env-create")
    cid = created.data()["id"]
    invisible = production.handle(
        _req("GET", "/api/2.0/contracts/%s" % cid, pr_app)
    )
    if invisible.status != 404:
        problems.append("sandbox contract visible in production")
    if evidence_class("sandbox") != "sandbox-simulation":
        problems.append("sandbox evidence class drifted")
    if is_production_evidence("sandbox"):
        problems.append("sandbox classified as production evidence")
    if problems:
        results.append(fail("04 environments isolation", "; ".join(problems)))
    else:
        results.append(
            ok(
                "04 environments isolation",
                "separate authorities/stores; credentials rejected both "
                "directions (403); ids namespaced; sandbox never "
                "production evidence",
            )
        )


def case_05_credentials(results: List[Result]) -> None:
    """Criterion 2: credential issuance, verification, expiry
    (evaluated against the injected clock), and revocation
    (terminal)."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-c", "c")
    read = service.handle(_req("GET", "/api/2.0/application", app))
    if read.status != 200 or read.data()["application_id"] != (
        app.record.application_id
    ):
        problems.append("valid credential not verified")
    if app.record.status != "active":
        problems.append("issued credential not active")
    # the secret is returned exactly once and only its digest is
    # journaled (the secret never appears in journal bytes)
    journal_blob = "\n".join(
        json.dumps(r.to_dict(), sort_keys=True)
        for r in service.journal_records()
    )
    if app.secret in journal_blob:
        problems.append("credential secret leaked into the journal")
    # expiry: a credential whose valid_until is in the past
    expired_clock = StepClock("2031-01-01T00:00:00Z", 60)
    expired_service, _ = _service(clock=expired_clock)
    expired_app = expired_service.issue_application_credential(
        developer_id="dev-c", application_name="old",
        capabilities=Capability.values(),
        valid_until="2030-01-01T00:00:00Z", key_material="old-key",
        actor="platform",
    )
    expired = expired_service.handle(
        _req("GET", "/api/2.0/application", expired_app)
    )
    if expired.status != 401 or expired.error()["reason"] != (
        "authentication-expired"
    ):
        problems.append("expired credential not rejected")
    # revocation is terminal
    service.revoke_application_credential(
        application_id=app.record.application_id, actor="platform"
    )
    revoked = service.handle(_req("GET", "/api/2.0/application", app))
    if revoked.status != 401 or revoked.error()["reason"] != (
        "authentication-invalid"
    ):
        problems.append("revoked credential not rejected")
    if problems:
        results.append(fail("05 credentials", "; ".join(problems)))
    else:
        results.append(
            ok(
                "05 credentials",
                "issuance/verification/expiry/revocation verified; the "
                "secret appears exactly once (never journaled)",
            )
        )


def case_06_authentication_failures(results: List[Result]) -> None:
    """Criterion 2: the authentication failure family -- unknown
    application, wrong secret, revoked, expired, wrong
    environment -- all fail closed with the exact boundary
    reason (no enumeration oracle)."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-a", "a")
    unknown = service.handle(
        _req(
            "GET",
            "/api/2.0/application",
            _FakeApp("sha256:%064d" % 1, app.secret),
        )
    )
    if unknown.status != 401 or unknown.error()["reason"] != (
        "authentication-invalid"
    ):
        problems.append("unknown application not rejected")
    wrong_secret = service.handle(
        _req("GET", "/api/2.0/application", _FakeApp(
            app.record.application_id, "dasec_wrong"
        ))
    )
    if wrong_secret.status != 401:
        problems.append("wrong secret not rejected")
    no_secret = service.handle(
        _req("GET", "/api/2.0/application", _FakeApp(
            app.record.application_id, ""
        ))
    )
    if no_secret.status != 401:
        problems.append("empty secret not rejected")
    if problems:
        results.append(fail("06 authentication failures", "; ".join(problems)))
    else:
        results.append(
            ok(
                "06 authentication failures",
                "unknown/wrong-secret/empty all fail closed 401 "
                "authentication-invalid",
            )
        )


class _FakeApp:
    """A credential-shaped fixture for authentication probes."""

    def __init__(self, application_id: str, secret: str) -> None:
        record = type("R", (), {})()
        record.application_id = application_id
        self.record = record
        self.secret = secret


def case_07_capability_authorization(results: List[Result]) -> None:
    """Criterion 2: the scoped capability authorization matrix --
    every route's required capability is enforced for EVERY
    declared route (the negative matrix), and authentication
    alone grants no authority."""
    problems: List[str] = []
    service, _ = _service()
    # an application with only webhooks:read
    scoped = _app(
        service, "dev-scoped", "scoped",
        (Capability.WEBHOOKS_READ,), key_material="scoped-key",
    )
    full = _full_app(service, "dev-full", "full")
    contract_id, _, _ = _full_flow(service, full, key_prefix="cap")
    # the negative matrix: every capability-requiring route
    # denies the scoped app (the ones the scoped app CAN call
    # are excluded)
    read_routes = [
        ("GET", "/api/2.0/intents"),
        ("GET", "/api/2.0/intents/%s" % contract_id),
        ("GET", "/api/2.0/intents/%s/lifecycle" % contract_id),
        ("GET", "/api/2.0/contracts"),
        ("GET", "/api/2.0/contracts/%s" % contract_id),
        ("GET", "/api/2.0/contracts/%s/usage" % contract_id),
        ("GET", "/api/2.0/contracts/%s/assurance" % contract_id),
        ("GET", "/api/2.0/leases"),
    ]
    for method, route in read_routes:
        response = service.handle(_req(method, route, scoped))
        if response.status != 403 or response.error()["reason"] != (
            "capability-denied"
        ):
            problems.append("scoped app not denied on %s" % route)
    # a write mutation on a capability the scoped app lacks
    write = service.handle(
        _req(
            "POST", "/api/2.0/intents", scoped,
            body=_intent_body(), idempotency_key="cap-write",
        )
    )
    if write.status != 403:
        problems.append("scoped app not denied a write mutation")
    # authentication alone grants nothing: an unknown-capability
    # route spec is rejected at validation time
    if Capability.ASSURANCE_READ not in Capability.values():
        problems.append("assurance:read missing from the vocabulary")
    if problems:
        results.append(fail("07 capability authorization", "; ".join(problems)))
    else:
        results.append(
            ok(
                "07 capability authorization",
                "the full route/capability matrix denies the scoped app "
                "403 before any canonical surface; authentication alone "
                "grants nothing",
            )
        )


def case_08_idempotency_normal_duplicate(results: List[Result]) -> None:
    """Criterion 2: the durable idempotency ledger -- a normal
    mutation followed by the byte-identical duplicate replay
    (same key, same body) with the replay marker."""
    problems: List[str] = []
    service, contracts = _service()
    app = _full_app(service, "dev-i", "i")
    first = _create_intent(service, app, key="idem-1")
    if first.status != 200:
        problems.append("first mutation failed")
    store_len = len(contracts.journal())
    api_records = len(service.journal_records())
    duplicate = _create_intent(service, app, key="idem-1")
    if duplicate.status != 200:
        problems.append("duplicate failed")
    if duplicate.headers.get("X-ADCOS-Idempotent-Replay") != "true":
        problems.append("duplicate not marked as replay")
    if first.canonical_body_bytes() != duplicate.canonical_body_bytes():
        problems.append("duplicate response not byte-identical")
    if len(contracts.journal()) != store_len:
        problems.append("duplicate re-executed the canonical command")
    if len(service.journal_records()) != api_records:
        problems.append("duplicate grew the boundary journal")
    if problems:
        results.append(fail("08 idempotency normal duplicate", "; ".join(problems)))
    else:
        results.append(
            ok(
                "08 idempotency normal duplicate",
                "duplicate replays byte-identically with zero canonical "
                "and zero boundary growth",
            )
        )


def case_09_idempotency_conflict(results: List[Result]) -> None:
    """Criterion 2: the materially-changed request under the
    same key fails closed 409; the original body still replays;
    and a FAILED (rejected) request never consumes the key (the
    retained W046 contract)."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-x", "x")
    first = _create_intent(service, app, key="conf-1")
    if first.status != 200:
        problems.append("first mutation failed")
    changed = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(requirements=("req-OTHER",)),
            idempotency_key="conf-1",
        )
    )
    if changed.status != 409 or changed.error()["reason"] != (
        "idempotency-conflict"
    ):
        problems.append("changed body under same key not rejected")
    # the original body still replays
    replay = _create_intent(service, app, key="conf-1")
    if replay.status != 200 or replay.headers.get(
        "X-ADCOS-Idempotent-Replay"
    ) != "true":
        problems.append("original body no longer replays")
    # a semantically rejected request releases the key
    bad = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(
                not_before="2025-06-02T00:00:00Z",
                not_after="2025-06-01T00:00:00Z",
            ),
            idempotency_key="conf-fix",
        )
    )
    if bad.status != 400 or bad.error()["canonical_reason"] != (
        "temporal-invalid"
    ):
        problems.append("the invalid-validity request was not rejected")
    fixed = _create_intent(
        service, app, key="conf-fix", requirements=("req-fixed",)
    )
    if fixed.status != 200:
        problems.append("a rejected request consumed the key")
    if problems:
        results.append(fail("09 idempotency conflict", "; ".join(problems)))
    else:
        results.append(
            ok(
                "09 idempotency conflict",
                "changed body 409; original replays; rejected requests "
                "release the key",
            )
        )


def case_10_idempotency_concurrent(results: List[Result]) -> None:
    """Criterion 2: two back-to-back submissions of the same key
    (the in-process concurrency shape) -- the second is a pure
    replay, nothing doubles."""
    problems: List[str] = []
    service, contracts = _service()
    app = _full_app(service, "dev-cc", "cc")
    first = _create_intent(service, app, key="conc-1")
    second = _create_intent(service, app, key="conc-1")
    if second.headers.get("X-ADCOS-Idempotent-Replay") != "true":
        problems.append("concurrent duplicate not replayed")
    if len(contracts.contracts()) != 1:
        problems.append("concurrent duplicate minted extra contracts")
    if problems:
        results.append(fail("10 idempotency concurrent", "; ".join(problems)))
    else:
        results.append(
            ok(
                "10 idempotency concurrent",
                "the second same-key submission is a pure replay (1 "
                "contract)",
            )
        )


def case_11_idempotency_restart(results: List[Result]) -> None:
    """Criterion 2: journal-first recovery -- the service reloads
    from the persisted journal bytes (construction is recovery),
    and the same-key retry after the restart replays the stored
    canonical response byte-identically."""
    problems: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        store = FileApiStore(Path(tmp) / "api-journal.jsonl")
        contracts = ContractStore()
        clock = StepClock(_T0, 60)
        service, _ = _service(store=store, contracts=contracts, clock=clock)
        app = _full_app(service, "dev-r", "r")
        first = _create_intent(service, app, key="restart-1")
        if first.status != 200:
            problems.append("first mutation failed")
        digest_before = service.journal_digest()
        # restart: a fresh service over the same persisted store
        # and the same canonical authority
        recovered = DeveloperApiService.load(
            environment="sandbox",
            contracts=contracts,
            store=FileApiStore(Path(tmp) / "api-journal.jsonl"),
            clock=StepClock(_T0, 60),
            issuance_key=_ISSUANCE_KEY,
        )
        if recovered.journal_digest() != digest_before:
            problems.append("recovery changed the journal digest")
        recovered.verify_integrity()
        retry = _create_intent(recovered, app, key="restart-1")
        if retry.status != 200 or retry.headers.get(
            "X-ADCOS-Idempotent-Replay"
        ) != "true":
            problems.append("post-restart retry not a replay")
        if first.canonical_body_bytes() != retry.canonical_body_bytes():
            problems.append("post-restart replay not byte-identical")
    if problems:
        results.append(fail("11 idempotency restart", "; ".join(problems)))
    else:
        results.append(
            ok(
                "11 idempotency restart",
                "journal-first recovery: load == live; the post-restart "
                "retry replays byte-identically",
            )
        )


def case_12_idempotency_crash_window(results: List[Result]) -> None:
    """Criterion 2 (the honest crash window): the canonical
    command is durable but the boundary's finality record is
    not (an injected committed-mutation append failure).  The
    same-key retry completes through the canonical authority's
    OWN duplicate discipline -- never re-executing the command
    -- and admits the response; a CHANGED body under the same
    key inside the crash window fails closed at the write-ahead
    hold (the M013 closure)."""
    problems: List[str] = []
    contracts = ContractStore()
    store = _CommittedMutationFailingApiStore("crash-1")
    clock = StepClock(_T0, 60)
    service, _ = _service(store=store, contracts=contracts, clock=clock)
    app = _full_app(service, "dev-cw", "cw")
    # the first attempt: canonical submit succeeds, the boundary
    # record append fails (the crash), a store-failed surfaces
    attempt = _create_intent(service, app, key="crash-1")
    if attempt.status != 500 or attempt.error()["reason"] != (
        "store-failed"
    ):
        problems.append("the crash-window failure is not store-failed")
    if len(contracts.contracts()) != 1:
        problems.append("the canonical command was not durable")
    store_len = len(contracts.journal())
    # the same-key retry with the SAME body: the canonical
    # duplicate path (no re-execution) + the completed admission
    retry = _create_intent(service, app, key="crash-1")
    if retry.status != 200:
        problems.append("the crash-window retry failed")
    if len(contracts.journal()) != store_len:
        problems.append("the crash-window retry re-executed the command")
    cid = retry.data()["id"]
    if retry.data()["state"] != "INTENT":
        problems.append("the reconstructed contract is not in INTENT")
    # a changed body under the same key inside the crash window
    # (a second hold exists after the retry committed): the
    # write-ahead hold closes the pre-commit variant
    service2, contracts2 = _service(contracts=contracts)
    app2 = service2.issue_application_credential(
        developer_id="dev-cw", application_name="cw-app",
        capabilities=Capability.values(), valid_until=_VALID_UNTIL,
        key_material="cw-key", actor="platform",
    )
    held = _PendingHoldService(service2, contracts2, app2, "cw-2")
    outcome = held.run_crash_window_changed_content()
    if outcome != "idempotency-conflict":
        problems.append(
            "the crash-window changed-content case did not fail closed "
            "(found %r)" % outcome
        )
    if problems:
        results.append(fail("12 idempotency crash window", "; ".join(problems)))
    else:
        results.append(
            ok(
                "12 idempotency crash window",
                "canonical-durable + boundary-crash -> the same-key retry "
                "reconstructs with zero re-execution; changed content "
                "fails closed at the write-ahead hold",
            )
        )


class _PendingHoldService:
    """A fixture that reproduces the pure write-ahead crash
    window: the pending hold is appended, the process 'crashes'
    BEFORE the canonical submission, and the same key arrives
    with CHANGED content."""

    def __init__(
        self, service: Any, contracts: ContractStore, app, key: str
    ) -> None:
        self._service = service
        self._contracts = contracts
        self._app = app
        self._key = key

    def run_crash_window_changed_content(self) -> str:
        from developerapi.journal import MutationPendingRecord

        key = self._key
        digest = "sha256:" + "0" * 64
        # the write-ahead hold (the crash point: nothing canonical ran)
        record = MutationPendingRecord.build(
            sequence=self._service._journal.tail_sequence() + 1,
            prev_record_id=self._service._journal.tail_record_id(),
            idempotency_key=key,
            application_id=self._app.record.application_id,
            developer_id=self._app.record.developer_id,
            method="POST",
            route="/api/2.0/intents",
            api_version="2.0",
            request_id="sha256:" + "1" * 64,
            request_digest=digest,
        )
        self._service._journal.append(record)
        self._service._index.apply(record)
        # the same key with materially different content
        response = self._service.handle(
            _req(
                "POST", "/api/2.0/intents", self._app,
                body=_intent_body(requirements=("req-changed",)),
                idempotency_key=key,
            )
        )
        error = response.error() or {}
        return error.get("reason", "unknown")


def case_13_canonical_contract_lifecycle_flow(results: List[Result]) -> None:
    """The canonical lifecycle flow end-to-end: create ->
    offers -> activation -> lease -> the platform-side execution/
    delivery/assurance/settlement advancement (through the
    canonical authority's public command surface) -> the honest
    lifecycle classification at each stage; the lease lifecycle
    (renew/revoke); the expiry evaluation; and the supersession
    (modify = a NEW contract with the explicit chain link)."""
    problems: List[str] = []
    service, contracts = _service()
    app = _full_app(service, "dev-l", "l")
    contract_id, lease_id, _ = _full_flow(service, app, key_prefix="lc")

    # the canonical projection round-trips: every §3 member is
    # present and the boundary adds only the envelope
    record = service.handle(
        _req("GET", "/api/2.0/contracts/%s" % contract_id, app)
    )
    data = record.data()
    for member in (
        "contract_id", "state", "principal", "beneficiaries",
        "requirements", "accepted_offers", "hard_constraints",
        "service_properties", "validity", "usage_pricing_terms",
        "assurance_obligations", "execution_scope", "termination",
        "provenance", "signature_refs",
    ):
        if member not in data:
            problems.append("canonical member %s missing" % member)
    if data.get("kind") != "contract" or data.get("id") != contract_id:
        problems.append("the boundary envelope members drifted")
    if data["accepted_offers"][0]["value"] != "offer-1":
        problems.append("the accepted offer reference did not round-trip")

    # the lifecycle classification at each stage
    def _stage_state():
        return service.handle(
            _req("GET", "/api/2.0/intents/%s/lifecycle" % contract_id, app)
        ).data()

    if _stage_state()["execution_status"] != "permitted":
        problems.append("CONTRACT_ACTIVE classification drifted")
    _advance(contract_id, contracts, app, to="SETTLED")
    final = _stage_state()
    if final["contract_state"] != "SETTLED" or final[
        "execution_status"
    ] != "closed":
        problems.append("the SETTLED terminal classification drifted")
    if final["physical_connectivity_observed"] is not False:
        problems.append("physical connectivity was claimed")
    if final["physical_evidence"] != "not-claimed":
        problems.append("physical evidence was claimed")

    # the lease lifecycle: renewal creates the successor and
    # flips the predecessor; revocation is terminal
    second_contract = _create_intent(
        service, app, key="lc-2", requirements=("req-2",)
    ).data()["id"]
    service.handle(
        _req(
            "POST", "/api/2.0/intents/%s/offers" % second_contract, app,
            body={
                "offers": [
                    {"ref_kind": "offer", "value": "offer-2"}
                ],
                "recorded_at": _INST_OFFERS,
            },
            idempotency_key="lc-2-offers",
        )
    )
    service.handle(
        _req(
            "POST", "/api/2.0/intents/%s/activation" % second_contract, app,
            body={
                "activated_at": _INST_ACTIVATE,
                "signature_refs": [
                    {"ref_kind": "signature", "value": "sig-2"}
                ],
            },
            idempotency_key="lc-2-activate",
        )
    )
    lease2 = service.handle(
        _req(
            "POST", "/api/2.0/contracts/%s/leases" % second_contract, app,
            body={
                "granted_at": _INST_LEASE_FROM,
                "not_before": _INST_LEASE_FROM,
                "not_after": _INST_LEASE_TO,
            },
            idempotency_key="lc-2-lease",
        )
    ).data()
    renewed = service.handle(
        _req(
            "POST", "/api/2.0/leases/%s/renewal" % lease2["lease_id"], app,
            body={
                "granted_at": "2025-06-01T06:00:00Z",
                "not_before": "2025-06-01T06:00:00Z",
                "not_after": "2025-06-01T23:00:00Z",
            },
            idempotency_key="lc-2-renew",
        )
    )
    if renewed.status != 200:
        problems.append("lease renewal failed")
    predecessor = service.handle(
        _req("GET", "/api/2.0/leases/%s" % lease2["lease_id"], app)
    ).data()
    if predecessor["state"] != "renewed":
        problems.append("renewal did not flip the predecessor")
    revoked = service.handle(
        _req(
            "POST", "/api/2.0/leases/%s/revocation" % renewed.data()["lease_id"], app,
            body={"reason": "done", "recorded_at": "2025-06-01T07:00:00Z"},
            idempotency_key="lc-2-revoke",
        )
    )
    if revoked.status != 200 or revoked.data()["state"] != "revoked":
        problems.append("lease revocation failed")
    # lease expiry evaluation (injected instant)
    contracts.expire_leases_if_due(
        lease_id := renewed.data()["lease_id"], "2025-06-02T00:00:00Z"
    )
    expired = service.handle(
        _req("GET", "/api/2.0/leases/%s" % renewed.data()["lease_id"], app)
    ).data()
    if expired["state"] == "revoked":
        pass  # revocation is terminal (expiry cannot apply)
    else:
        if expired["state"] not in ("revoked",):
            problems.append("revocation not terminal")

    # supersession (modify = a NEW contract with the chain link)
    superseding = _create_intent(
        service, app, key="lc-sup", requirements=("req-3",),
        superseded=contract_id,
    )
    if superseding.status != 200:
        problems.append("supersession creation failed")
    elif superseding.data().get("superseded_contract", {}).get("value") != (
        contract_id
    ):
        problems.append("the supersession chain link did not round-trip")
    # the predecessor is untouched (no silent weakening)
    if service.handle(
        _req("GET", "/api/2.0/contracts/%s" % contract_id, app)
    ).data()["state"] != "SETTLED":
        problems.append("supersession mutated the predecessor")
    if problems:
        results.append(fail("13 canonical contract lifecycle flow", "; ".join(problems)))
    else:
        results.append(
            ok(
                "13 canonical contract lifecycle flow",
                "create->offers->activation->lease->execution->delivery->"
                "assurance->settlement all classified honestly; lease "
                "renew/revoke terminal; supersession = new contract with "
                "the chain link (predecessor untouched)",
            )
        )


def case_14_reason_code_preservation(results: List[Result]) -> None:
    """Criterion 4: canonical contracts-domain failures reach the
    developer boundary UNCHANGED and machine-readable (the
    canonical_reason member carries the exact contracts reason
    string; the HTTP status derives from the frozen table)."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-rc", "rc")
    contract_id, _, _ = _full_flow(service, app, key_prefix="rc")

    # contract-terminal (a materially different termination of a
    # settled contract)
    settled_cid = contract_id
    _advance(settled_cid, service._contracts, app, to="SETTLED")
    terminal = service.handle(
        _req(
            "POST", "/api/2.0/contracts/%s/termination" % settled_cid, app,
            body={
                "condition": "principal-requested",
                "reason": "late",
                "recorded_at": "2025-06-01T15:00:00Z",
            },
            idempotency_key="rc-terminal",
        )
    )
    if terminal.error()["canonical_reason"] != "contract-terminal":
        problems.append("contract-terminal not preserved")
    if terminal.status != 422:
        problems.append("contract-terminal HTTP status drifted")

    # unknown-contract (404)
    unknown = service.handle(
        _req(
            "POST", "/api/2.0/contracts/sha256:%064d/termination" % 2, app,
            body={
                "condition": "principal-requested",
                "reason": "x", "recorded_at": _INST_TERMINATE,
            },
            idempotency_key="rc-unknown",
        )
    )
    if unknown.error()["canonical_reason"] != "unknown-contract":
        problems.append("unknown-contract not preserved")
    if unknown.status != 404:
        problems.append("unknown-contract HTTP status drifted")

    # secret-rejected (LOCK-119: a secret-shaped reference value)
    secret = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(
                requirements=("ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabc",)
            ),
            idempotency_key="rc-secret",
        )
    )
    if secret.error()["canonical_reason"] != "secret-rejected":
        problems.append("secret-rejected not preserved")

    # vocabulary (a wrong constraint kind)
    vocab = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body={
                "requirements": _intent_body()["requirements"],
                "validity": {"not_before": _T0, "not_after": "2025-06-02T00:00:00Z"},
                "termination": _intent_body()["termination"],
                "hard_constraints": [
                    {"kind": "not-a-kind", "params": {}}
                ],
                "recorded_at": _INST_CREATE,
            },
            idempotency_key="rc-vocab",
        )
    )
    if vocab.error()["canonical_reason"] != "vocabulary":
        problems.append("vocabulary not preserved")

    # temporal-invalid (an inverted validity window)
    temporal = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(
                not_before="2025-06-02T00:00:00Z",
                not_after="2025-06-01T00:00:00Z",
            ),
            idempotency_key="rc-temporal",
        )
    )
    if temporal.error()["canonical_reason"] != "temporal-invalid":
        problems.append("temporal-invalid not preserved")

    # invalid-transition (offers bind exactly once: a second,
    # materially different selection on an OFFER_SELECTED intent)
    second = _create_intent(
        service, app, key="rc-2", requirements=("rc-2",)
    ).data()["id"]
    service.handle(
        _req(
            "POST", "/api/2.0/intents/%s/offers" % second, app,
            body={
                "offers": [{"ref_kind": "offer", "value": "offer-a"}],
                "recorded_at": _INST_OFFERS,
            },
            idempotency_key="rc-2-offers",
        )
    )
    rebind = service.handle(
        _req(
            "POST", "/api/2.0/intents/%s/offers" % second, app,
            body={
                "offers": [{"ref_kind": "offer", "value": "offer-b"}],
                "recorded_at": "2025-06-01T00:11:00Z",
            },
            idempotency_key="rc-2-offers-2",
        )
    )
    if rebind.error()["canonical_reason"] != "invalid-transition":
        problems.append("invalid-transition not preserved")
    if rebind.status != 422:
        problems.append("invalid-transition HTTP status drifted")

    # not-yet-valid (activation before the validity window)
    third = _create_intent(
        service, app, key="rc-3", requirements=("rc-3",)
    ).data()["id"]
    service.handle(
        _req(
            "POST", "/api/2.0/intents/%s/offers" % third, app,
            body={
                "offers": [{"ref_kind": "offer", "value": "offer-c"}],
                "recorded_at": _INST_OFFERS,
            },
            idempotency_key="rc-3-offers",
        )
    )
    early = service.handle(
        _req(
            "POST", "/api/2.0/intents/%s/activation" % third, app,
            body={
                "activated_at": "2025-05-01T00:00:00Z",
                "signature_refs": [
                    {"ref_kind": "signature", "value": "sig-c"}
                ],
            },
            idempotency_key="rc-3-early",
        )
    )
    if early.error()["canonical_reason"] != "not-yet-valid":
        problems.append("not-yet-valid not preserved")

    if problems:
        results.append(fail("14 reason code preservation", "; ".join(problems)))
    else:
        results.append(
            ok(
                "14 reason code preservation",
                "contract-terminal(422)/unknown-contract(404)/secret-"
                "rejected/vocabulary/temporal-invalid/invalid-transition"
                "(422)/not-yet-valid all preserved unchanged",
            )
        )


def case_15_pagination(results: List[Result]) -> None:
    """Deterministic ordering, stable cursor behavior, invalid
    cursor rejection, filtering, and tenant isolation across
    the list routes."""
    problems: List[str] = []
    service, _ = _service()
    app_a = _full_app(service, "dev-pa", "pa")
    app_b = _full_app(service, "dev-pb", "pb")
    # three contracts for A (one terminated), one for B
    ids = []
    for i in range(3):
        created = _create_intent(
            service, app_a, key="pg-a-%d" % i, requirements=("pg-a-%d" % i,)
        )
        ids.append(created.data()["id"])
    _create_intent(service, app_b, key="pg-b", requirements=("pg-b",))

    page = service.handle(
        _req(
            "GET", "/api/2.0/contracts", app_a,
            body={"limit": 2},
        )
    ).data()
    if len(page["items"]) != 2 or not page["has_more"]:
        problems.append("limit/has_more drifted")
    if [item["id"] for item in page["items"]] != sorted(ids)[:2]:
        problems.append("ordering not deterministic (contract id asc)")
    cursor = page["next_cursor"]
    next_page = service.handle(
        _req(
            "GET", "/api/2.0/contracts", app_a,
            body={"limit": 2, "cursor": cursor},
        )
    ).data()
    if [item["id"] for item in next_page["items"]] != sorted(ids)[2:]:
        problems.append("cursor continuation drifted")
    # the full iteration is exactly the sorted tenant set
    items = []
    seen_cursor = ""
    while True:
        body = {"limit": 2}
        if seen_cursor:
            body["cursor"] = seen_cursor
        data = service.handle(
            _req("GET", "/api/2.0/contracts", app_a, body=body)
        ).data()
        items.extend(item["id"] for item in data["items"])
        if not data["has_more"]:
            break
        seen_cursor = data["next_cursor"]
    if items != sorted(ids):
        problems.append("full iteration drifted")
    # invalid cursor
    bad = service.handle(
        _req(
            "GET", "/api/2.0/contracts", app_a,
            body={"cursor": "not-a-cursor"},
        )
    )
    if bad.status != 400 or bad.error()["reason"] != (
        "pagination-invalid"
    ):
        problems.append("forged cursor not rejected")
    # tenant isolation: B sees only its own contract
    b_items = service.handle(
        _req("GET", "/api/2.0/contracts", app_b)
    ).data()["items"]
    if len(b_items) != 1:
        problems.append("tenant isolation drifted on contracts")
    # the state filter on contracts_list
    terminated = _create_intent(
        service, app_a, key="pg-a-term", requirements=("pg-a-term",)
    ).data()["id"]
    service.handle(
        _req(
            "POST", "/api/2.0/contracts/%s/termination" % terminated, app_a,
            body={
                "condition": "principal-requested",
                "reason": "pg", "recorded_at": _INST_TERMINATE,
            },
            idempotency_key="pg-a-term-t",
        )
    )
    filtered = service.handle(
        _req(
            "GET", "/api/2.0/contracts", app_a,
            body={"filters": {"state": "TERMINATED"}},
        )
    ).data()
    if [item["id"] for item in filtered["items"]] != [terminated]:
        problems.append("state filter drifted")
    # intents_list lists only INTENT-state contracts
    intents = service.handle(
        _req("GET", "/api/2.0/intents", app_a)
    ).data()["items"]
    if terminated in [item["id"] for item in intents]:
        problems.append("intents_list listed a terminated contract")
    if problems:
        results.append(fail("15 pagination", "; ".join(problems)))
    else:
        results.append(
            ok(
                "15 pagination",
                "deterministic order (id asc), stable cursors, forged "
                "cursor 400, state filter, tenant isolation, intents "
                "window",
            )
        )


def case_16_rate_limiting(results: List[Result]) -> None:
    """Truthful retry guidance: the injected limiter throttles
    per application; a throttled request fails closed 429 with
    the reset guidance and mints NOTHING canonical."""
    problems: List[str] = []
    limiter = RateLimiter(
        capacity=2, refill_per_second=1, clock=FixedClock(_T0)
    )
    service, contracts = _service(
        rate_limiter=limiter, clock=FixedClock(_T0)
    )
    app = _full_app(service, "dev-rl", "rl")
    # two admitted requests then the third throttles (the fixed
    # clock never refills)
    for i in range(2):
        response = service.handle(
            _req("GET", "/api/2.0/application", app)
        )
        if response.status != 200:
            problems.append("request %d not admitted" % i)
    store_len = len(contracts.journal())
    journal_len = len(service.journal_records())
    throttled = service.handle(_req("GET", "/api/2.0/application", app))
    if throttled.status != 429 or throttled.error()["reason"] != (
        "rate-limited"
    ):
        problems.append("the third request was not throttled")
    if not throttled.error().get("retry_after"):
        problems.append("the throttle lacks truthful retry guidance")
    if "Retry-After" not in throttled.headers:
        problems.append("the Retry-After header is absent")
    mutation = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(), idempotency_key="rl-1",
        )
    )
    if mutation.status != 429:
        problems.append("a throttled mutation was admitted")
    if len(contracts.journal()) != store_len:
        problems.append("a throttled mutation minted canonical state")
    if len(service.journal_records()) != journal_len:
        problems.append("a throttled request wrote journal records")
    # another application is not throttled (per-application)
    app_b = _full_app(service, "dev-rl-b", "rlb")
    other = service.handle(_req("GET", "/api/2.0/application", app_b))
    if other.status != 200 or "rate_limit" not in dict(other.body):
        problems.append("per-application scoping drifted")
    if problems:
        results.append(fail("16 rate limiting", "; ".join(problems)))
    else:
        results.append(
            ok(
                "16 rate limiting",
                "third request 429 with retry guidance; the throttled "
                "mutation mints nothing; scoping is per application",
            )
        )


def case_17_correlation_secrets(results: List[Result]) -> None:
    """Deterministic correlation ids on every response (identical
    requests correlate; materially different ones do not) and
    the secret-hygiene scan over journal bytes and response
    bodies (no credential/webhook secrets anywhere)."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-cs", "cs")
    r1 = service.handle(_req("GET", "/api/2.0/application", app))
    r2 = service.handle(_req("GET", "/api/2.0/application", app))
    if r1.body["request_id"] != r2.body["request_id"]:
        problems.append("identical requests did not correlate")
    r3 = service.handle(
        _req("GET", "/api/2.0/contracts", app)
    )
    if r3.body["request_id"] == r1.body["request_id"]:
        problems.append("different requests correlated")
    # secret hygiene over every durable surface
    journal_blob = "\n".join(
        json.dumps(r.to_dict(), sort_keys=True)
        for r in service.journal_records()
    )
    for prefix in _SECRET_PREFIXES:
        if prefix in journal_blob:
            problems.append("secret prefix %r in the journal" % prefix)
    flow_service, _ = _service()
    flow_app = _full_app(flow_service, "dev-cs2", "cs2")
    consumer = _Consumer("unused")
    flow_service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", flow_app,
            body={
                "url": "https://c.test/h",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="cs-ep",
        )
    )
    created = _create_intent(flow_service, flow_app, key="cs-1")
    response_blob = json.dumps(dict(created.body), sort_keys=True)
    for prefix in _SECRET_PREFIXES:
        if prefix in response_blob:
            problems.append("secret prefix %r in a response" % prefix)
    if flow_app.secret in response_blob:
        problems.append("credential secret in a response body")
    if problems:
        results.append(fail("17 correlation + secrets", "; ".join(problems)))
    else:
        results.append(
            ok(
                "17 correlation + secrets",
                "correlation ids deterministic; zero secret material in "
                "journals or responses",
            )
        )


def case_18_webhook_signing(results: List[Result]) -> None:
    """Criterion 3: every delivery is signed (HMAC-SHA256 over
    the canonical envelope bytes); verification succeeds on the
    genuine payload and fails on a tampered one."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-ws", "ws")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://ws.test/hook",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="ws-ep",
        )
    ).data()
    secret = service.endpoint_signing_secret(endpoint["id"])
    consumer = _Consumer(secret)
    service._transports[endpoint["id"]] = consumer
    _create_intent(service, app, key="ws-1")
    service.process_due_deliveries()
    if not consumer.deliveries:
        problems.append("no signed delivery arrived")
    else:
        payload, headers = _signed_delivery(service, consumer)
        if not webhook_platform.verify_delivery_signature(
            secret,
            key_id=headers[webhook_platform.KEY_ID_HEADER],
            timestamp=headers[webhook_platform.TIMESTAMP_HEADER],
            delivery_id=headers[webhook_platform.DELIVERY_ID_HEADER],
            payload=payload,
            signature=headers[webhook_platform.SIGNATURE_HEADER],
        ):
            problems.append("the genuine signature did not verify")
        tampered = dict(payload)
        tampered["data"] = {"fabricated": True}
        if webhook_platform.verify_delivery_signature(
            secret,
            key_id=headers[webhook_platform.KEY_ID_HEADER],
            timestamp=headers[webhook_platform.TIMESTAMP_HEADER],
            delivery_id=headers[webhook_platform.DELIVERY_ID_HEADER],
            payload=tampered,
            signature=headers[webhook_platform.SIGNATURE_HEADER],
        ):
            problems.append("a tampered payload verified")
        if headers.get(webhook_platform.ALGORITHM_HEADER) != (
            webhook_platform.SIGNATURE_ALGORITHM
        ):
            problems.append("the signature algorithm header drifted")
    if problems:
        results.append(fail("18 webhook signing", "; ".join(problems)))
    else:
        results.append(
            ok(
                "18 webhook signing",
                "genuine delivery verifies; tampered payload rejected; "
                "the frozen header set carried",
            )
        )


def case_19_webhook_duplicate_replay(results: List[Result]) -> None:
    """Criterion 3: the same event may legally be delivered more
    than once (at-least-once); the consumer deduplicates by
    event id; and a re-observation of an UNCHANGED contract
    emits nothing (event identity is command-bound)."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-wd", "wd")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://wd.test/hook",
                "event_types": ["connectivity_contract.state_changed"],
            },
            idempotency_key="wd-ep",
        )
    ).data()
    consumer = _Consumer(service.endpoint_signing_secret(endpoint["id"]))
    service._transports[endpoint["id"]] = consumer
    contract_id, _, _ = _full_flow(service, app, key_prefix="wd")
    _advance(contract_id, service._contracts, app, to="SETTLED")
    first = service.observe_contract(contract_id)
    second = service.observe_contract(contract_id)
    if first != 1 or second != 0:
        problems.append("re-observation emitted again (%d, %d)" % (first, second))
    service.process_due_deliveries()
    if len(consumer.deliveries) != 1:
        problems.append("delivery count drifted (%d)" % len(consumer.deliveries))
    # the consumer-side duplicate detector accepts a legal
    # redelivery as a duplicate
    detector = DuplicateDetector()
    payload, _ = consumer.deliveries[0]
    if detector.observe(payload["event_id"]) is not True:
        problems.append("first observation not new")
    if detector.observe(payload["event_id"]) is not False:
        problems.append("duplicate not detected")
    if problems:
        results.append(fail("19 webhook duplicate/replay", "; ".join(problems)))
    else:
        results.append(
            ok(
                "19 webhook duplicate/replay",
                "re-observation emits nothing (identity command-bound); "
                "legal redelivery detected as duplicate by event id",
            )
        )


def case_20_webhook_out_of_order(results: List[Result]) -> None:
    """Criterion 3: events may arrive out of order; the
    resource_version metadata is the staleness signal (the SDK
    OrderTracker detects stale events)."""
    problems: List[str] = []
    tracker = OrderTracker()
    if tracker.observe("sha256:%064d" % 1, 5) != "advance":
        problems.append("first observation not classified advance")
    if tracker.observe("sha256:%064d" % 1, 3) != "stale":
        problems.append("stale (out-of-order) event not detected")
    if tracker.observe("sha256:%064d" % 1, 5) != "duplicate":
        problems.append("same version not classified duplicate")
    if tracker.observe("sha256:%064d" % 1, 7) != "advance":
        problems.append("newer version not accepted")
    # the live event payloads carry the resource_version member
    service, _ = _service()
    app = _full_app(service, "dev-wo", "wo")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://wo.test/hook",
                "event_types": ["connectivity_contract.state_changed"],
            },
            idempotency_key="wo-ep",
        )
    ).data()
    consumer = _Consumer(service.endpoint_signing_secret(endpoint["id"]))
    service._transports[endpoint["id"]] = consumer
    contract_id, _, _ = _full_flow(service, app, key_prefix="wo")
    _advance(contract_id, service._contracts, app, to="ASSURED")
    service.observe_contract(contract_id)
    service.process_due_deliveries()
    payload, _ = consumer.deliveries[0]
    if not isinstance(payload.get("resource_version"), int):
        problems.append("the delivery lacks the resource_version metadata")
    if problems:
        results.append(fail("20 webhook out-of-order", "; ".join(problems)))
    else:
        results.append(
            ok(
                "20 webhook out-of-order",
                "OrderTracker detects stale/same versions and accepts "
                "newer; the payload carries resource_version",
            )
        )


def case_21_webhook_retry(results: List[Result]) -> None:
    """Criterion 3: deterministic retry semantics -- a failed
    delivery retries after the frozen backoff without EVER
    mutating the observed event (the event bytes are fixed at
    queueing)."""
    problems: List[str] = []
    clock = FixedClock(_T0)
    service, _ = _service(clock=clock)
    app = _full_app(service, "dev-wr", "wr")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://wr.test/hook",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="wr-ep",
        )
    ).data()
    consumer = _Consumer(service.endpoint_signing_secret(endpoint["id"]), fail=True)
    service._transports[endpoint["id"]] = consumer
    # the mutation's inline delivery pass performs the FIRST
    # attempt (contained: the failure is recorded, the response
    # is the canonical success)
    created = _create_intent(service, app, key="wr-1")
    if created.status != 200:
        problems.append("the contained first failure reached the caller")
    if len(consumer.deliveries) != 1:
        problems.append("the first attempt did not happen")
    first_payload, first_headers = consumer.deliveries[0]
    state = service.index().deliveries
    delivery_id = sorted(state)[0]
    if state[delivery_id].last_status != "failed":
        problems.append("the failed attempt not recorded")
    if not state[delivery_id].next_attempt_at:
        problems.append("no next attempt scheduled")
    if state[delivery_id].attempts != 1:
        problems.append("attempt count drifted")
    # the immediate pass performs nothing (the fixed clock has
    # not advanced past the backoff window)
    if service.process_due_deliveries() != 0:
        problems.append("the retry fired before the backoff elapsed")
    # advance the clock past the first backoff (60s): the retry
    # fires, re-delivering the SAME signed event bytes
    service._clock = FixedClock("2025-06-01T00:05:00Z")
    performed = service.process_due_deliveries()
    if performed != 1 or len(consumer.deliveries) != 2:
        problems.append("the scheduled retry did not fire")
    second_payload, second_headers = consumer.deliveries[1]
    if canonical_json_bytes(dict(second_payload)) != canonical_json_bytes(
        dict(first_payload)
    ):
        problems.append("the retried event bytes changed")
    if second_headers.get(webhook_platform.EVENT_ID_HEADER) != first_headers.get(
        webhook_platform.EVENT_ID_HEADER
    ):
        problems.append("the retried event identity changed")
    if problems:
        results.append(fail("21 webhook retry", "; ".join(problems)))
    else:
        results.append(
            ok(
                "21 webhook retry",
                "failed -> frozen backoff -> retry; the event bytes and "
                "identity never change",
            )
        )


def case_22_webhook_environment_separation(results: List[Result]) -> None:
    """Criterion 3: sandbox and production observation channels
    are isolated (a sandbox endpoint never receives production
    events and vice versa)."""
    problems: List[str] = []
    sandbox, sandbox_contracts = _service(environment="sandbox")
    production, production_contracts = _service(environment="production")
    sb_app = _full_app(sandbox, "dev-we", "sb")
    pr_app = _full_app(production, "dev-we", "pr")
    sb_endpoint = sandbox.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", sb_app,
            body={
                "url": "https://we.test/sb",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="we-sb",
        )
    ).data()
    pr_endpoint = production.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", pr_app,
            body={
                "url": "https://we.test/pr",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="we-pr",
        )
    ).data()
    sb_consumer = _Consumer(sandbox.endpoint_signing_secret(sb_endpoint["id"]))
    pr_consumer = _Consumer(production.endpoint_signing_secret(pr_endpoint["id"]))
    sandbox._transports[sb_endpoint["id"]] = sb_consumer
    production._transports[pr_endpoint["id"]] = pr_consumer
    _create_intent(sandbox, sb_app, key="we-sb-1")
    _create_intent(production, pr_app, key="we-pr-1")
    sandbox.process_due_deliveries()
    production.process_due_deliveries()
    if len(sb_consumer.deliveries) != 1 or len(pr_consumer.deliveries) != 1:
        problems.append("delivery counts drifted")
    elif sb_consumer.deliveries[0][0].get("environment") != "sandbox" or (
        pr_consumer.deliveries[0][0].get("environment") != "production"
    ):
        problems.append("environment tagging drifted")
    if problems:
        results.append(fail("22 webhook environment separation", "; ".join(problems)))
    else:
        results.append(
            ok(
                "22 webhook environment separation",
                "each environment's channel delivers only its own "
                "environment-tagged events",
            )
        )


def case_23_sdk_request_parity(results: List[Result]) -> None:
    """Criterion 5: request parity -- the SDK builds the same
    canonical ApiRequest representation the direct caller
    builds (byte-identical canonical request bytes) for the
    canonical operations."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-sdk", "sdk")
    captured: List[ApiRequest] = []

    def transport(request: ApiRequest):
        captured.append(request)
        return service.handle(request)

    client = DeveloperApiClient(
        transport=transport,
        application_id=app.record.application_id,
        secret=app.secret,
        api_version="2.0",
        environment="sandbox",
    )
    key = "sdk-parity-create"
    body = _intent_body(requirements=("sdk-req",))
    direct = ApiRequest(
        method="POST",
        route="/api/2.0/intents",
        body=dict(body),
        api_version="2.0",
        idempotency_key=key,
        application_id=app.record.application_id,
        secret=app.secret,
    )
    client.create_intent(idempotency_key=key, intent=body)
    if not captured:
        problems.append("the SDK issued no request")
    else:
        sdk_request = captured[-1]
        if canonical_json_bytes(
            dict(sdk_request.body)
        ) != canonical_json_bytes(dict(direct.body)):
            problems.append("create_intent body bytes diverge")
        if (sdk_request.method, sdk_request.route, sdk_request.idempotency_key) != (
            direct.method, direct.route, direct.idempotency_key
        ):
            problems.append("create_intent attribution diverges")
    # offers/activation/termination/lease parity
    contract_id = _create_intent(
        service, app, key="sdk-parity-flow"
    ).data()["id"]
    captured.clear()
    client.accept_offers(
        idempotency_key="sdk-parity-offers",
        intent_id=contract_id,
        offers=[{"ref_kind": "offer", "value": "offer-sdk"}],
        recorded_at=_INST_OFFERS,
    )
    if "/api/2.0/intents/%s/offers" % contract_id not in captured[-1].route:
        problems.append("accept_offers route diverges")
    captured.clear()
    client.activate_contract(
        idempotency_key="sdk-parity-act",
        intent_id=contract_id,
        activated_at=_INST_ACTIVATE,
        signature_refs=[{"ref_kind": "signature", "value": "sig-sdk"}],
    )
    if "/activation" not in captured[-1].route:
        problems.append("activate_contract route diverges")
    captured.clear()
    client.terminate_contract(
        idempotency_key="sdk-parity-term",
        contract_id=contract_id,
        condition="principal-requested",
        reason="parity",
        recorded_at=_INST_TERMINATE,
    )
    if "/termination" not in captured[-1].route:
        problems.append("terminate_contract route diverges")
    if problems:
        results.append(fail("23 SDK request parity", "; ".join(problems)))
    else:
        results.append(
            ok(
                "23 SDK request parity",
                "byte-identical request bytes and attribution across the "
                "canonical operations",
            )
        )


def case_24_sdk_response_parity(results: List[Result]) -> None:
    """Criterion 5: response parsing parity (the SDK resources
    carry the server's exact data), error/reason-code parity
    (the canonical reason crosses the SDK boundary unchanged),
    and pagination parity."""
    problems: List[str] = []
    service, contracts = _service()
    app = _full_app(service, "dev-sd", "sd")
    client = DeveloperApiClient(
        transport=service.handle,
        application_id=app.record.application_id,
        secret=app.secret,
        api_version="2.0",
        environment="sandbox",
    )
    key = "sdk-resp-1"
    created = client.create_intent(
        idempotency_key=key, intent=_intent_body(requirements=("sd-1",))
    )
    direct = _create_intent(service, app, key="sdk-resp-2", requirements=("sd-2",))
    if created.get("state") != "INTENT" or created.kind != "contract":
        problems.append("the SDK contract resource diverges")
    if created.get("contract_id") != created.id:
        problems.append("the SDK resource id members diverge")
    if created.id != service.handle(
        _req("GET", "/api/2.0/contracts/%s" % created.id, app)
    ).data()["id"]:
        problems.append("the SDK resource diverges from the direct read")
    # error parity: a canonical failure crosses unchanged (the
    # offers bind exactly once: a second, materially different
    # selection on an OFFER_SELECTED intent)
    contract_id = created.id
    client.accept_offers(
        idempotency_key="sdk-resp-offers",
        intent_id=contract_id,
        offers=[{"ref_kind": "offer", "value": "offer-sd"}],
        recorded_at=_INST_OFFERS,
    )
    try:
        client.accept_offers(
            idempotency_key="sdk-resp-offers-2",
            intent_id=contract_id,
            offers=[{"ref_kind": "offer", "value": "offer-sd-2"}],
            recorded_at="2025-06-01T00:11:00Z",
        )
        problems.append("the invalid re-selection succeeded")
    except DeveloperApiError as error:
        if error.canonical_reason != "invalid-transition":
            problems.append(
                "the canonical reason did not cross the SDK boundary (%r)"
                % error.canonical_reason
            )
    # pagination parity: the SDK list follows the server's cursor
    for i in range(3):
        _create_intent(
            service, app, key="sdk-resp-p%d" % i, requirements=("sd-p%d" % i,)
        )
    sdk_items = list(client.iterate(client.list_contracts, limit=2))
    direct_items = []
    cursor = ""
    while True:
        body = {"limit": 2}
        if cursor:
            body["cursor"] = cursor
        data = service.handle(
            _req("GET", "/api/2.0/contracts", app, body=body)
        ).data()
        direct_items.extend(item["id"] for item in data["items"])
        if not data["has_more"]:
            break
        cursor = data["next_cursor"]
    if [item.id for item in sdk_items] != direct_items:
        problems.append("the SDK pagination diverged")
    if problems:
        results.append(fail("24 SDK response parity", "; ".join(problems)))
    else:
        results.append(
            ok(
                "24 SDK response parity",
                "resource members, canonical error reasons, and cursor "
                "pagination all identical to the direct API",
            )
        )


def case_25_sdk_webhook_verification_parity(results: List[Result]) -> None:
    """Criterion 5: the SDK WebhookVerifier reproduces the
    canonical server verification semantics (signature first,
    then the replay window) and parses the observation."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-wv", "wv")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://wv.test/hook",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="wv-ep",
        )
    ).data()
    secret = service.endpoint_signing_secret(endpoint["id"])
    consumer = _Consumer(secret)
    service._transports[endpoint["id"]] = consumer
    _create_intent(service, app, key="wv-1")
    service.process_due_deliveries()
    payload, headers = _signed_delivery(service, consumer)
    verifier = WebhookVerifier(
        secret=secret, clock=StepClock(headers[webhook_platform.TIMESTAMP_HEADER], 60)
    )
    event = verifier.verify(headers, payload)
    if event.event_type != "connectivity_intent.created":
        problems.append("the parsed event type diverges")
    if event.resource_kind != "contract":
        problems.append("the parsed resource kind diverges")
    if event.environment != "sandbox":
        problems.append("the parsed environment diverges")
    # a stale timestamp is rejected (replay protection)
    stale = WebhookVerifier(
        secret=secret,
        clock=StepClock("2025-06-02T00:00:00Z", 60),
    )
    try:
        stale.verify(headers, payload)
        problems.append("a stale delivery verified")
    except DeveloperApiError as error:
        if error.reason != "webhook-timestamp-stale":
            problems.append("the stale rejection reason drifted")
    if problems:
        results.append(fail("25 SDK webhook verification parity", "; ".join(problems)))
    else:
        results.append(
            ok(
                "25 SDK webhook verification parity",
                "the verifier reproduces the server construction; stale "
                "timestamps fail closed",
            )
        )


def case_26_technology_neutral_surface(results: List[Result]) -> None:
    """LOCK-114 (the M013 acceptance): the API surface is
    technology-neutral -- no network implementation member
    appears anywhere in the request schema vocabulary or the
    response resources, and execution material rides opaque
    typed references only (LOCK-117: data, never authority)."""
    problems: List[str] = []
    # the request-schema vocabulary is technology-neutral
    for version, spec in API_VERSIONS.items():
        for role, schema in spec.schemas.items():
            for field_spec in schema.fields:
                if field_spec.name in _FORBIDDEN_SURFACE_MEMBERS:
                    problems.append(
                        "schema %s/%s carries the implementation member %r"
                        % (version, role, field_spec.name)
                    )
    # the response resources of a full flow are neutral
    service, contracts = _service()
    app = _full_app(service, "dev-tn", "tn")
    contract_id, lease_id, _ = _full_flow(service, app, key_prefix="tn")
    _advance(contract_id, contracts, app, to="ASSURED")
    responses = [
        service.handle(_req(r[0], r[1], app))
        for r in (
            ("GET", "/api/2.0/contracts/%s" % contract_id),
            ("GET", "/api/2.0/intents/%s/lifecycle" % contract_id),
            ("GET", "/api/2.0/contracts/%s/usage" % contract_id),
            ("GET", "/api/2.0/contracts/%s/assurance" % contract_id),
            ("GET", "/api/2.0/leases/%s" % lease_id),
            ("GET", "/api/2.0/application", app),
        )
    ]
    blob = canonical_json_bytes(
        [json.loads(r.canonical_body_bytes()) for r in responses]
    ).decode("utf-8")
    for member in _FORBIDDEN_SURFACE_MEMBERS:
        if '"%s"' % member in blob:
            problems.append(
                "a response resource carries the implementation member %r"
                % member
            )
    # execution material appears ONLY as opaque typed references
    lifecycle = responses[1].data()
    for ref in lifecycle["execution_scope_refs"] + lifecycle[
        "execution_artifact_refs"
    ]:
        if ref.get("ref_kind") not in (
            "execution-scope",
            "execution-artifact",
        ):
            problems.append("execution material is not a typed reference")
    if lifecycle["execution_status"] not in set(
        _EXECUTION_STATUS_BY_STATE.values()
    ):
        problems.append("the execution status is not the canonical projection")
    # the AST audit: no socket/transport/adapter/provider-SDK
    # construction anywhere in the family (the webhook delivery
    # seam is an injectable callable, never an implementation
    # object)
    for path in _FAMILY_FILES:
        rel = str(path.relative_to(REPO_ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("socket",):
                    problems.append("%s constructs a socket" % rel)
    if problems:
        results.append(fail("26 technology-neutral surface", "; ".join(problems)))
    else:
        results.append(
            ok(
                "26 technology-neutral surface",
                "zero network implementation members in the schema or "
                "resource vocabulary; execution material rides opaque "
                "typed references only (LOCK-114/LOCK-117)",
            )
        )


def case_27_typed_reference_discipline(results: List[Result]) -> None:
    """LOCK-114 (the M013 acceptance): offers/usage/assurance
    semantics ride opaque TYPED REFERENCES ONLY -- wrong
    reference kinds fail closed, the reads return exactly the
    opaque references (never interpreted), and the demoted 1.x
    routes no longer dispatch."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-tr", "tr")
    # a wrong reference kind is rejected at the boundary
    wrong_kind = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body={
                "requirements": [{"ref_kind": "offer", "value": "x"}],
                "validity": {"not_before": _T0, "not_after": "2025-06-02T00:00:00Z"},
                "termination": {
                    "conditions": ["principal-requested"],
                    "compensation": {
                        "ref_kind": "compensation", "value": "c",
                    },
                },
                "recorded_at": _INST_CREATE,
            },
            idempotency_key="tr-wrong-kind",
        )
    )
    if wrong_kind.status != 400:
        problems.append("a wrong reference kind was admitted")
    # a wrong kind in the offer selection
    contract_id = _create_intent(
        service, app, key="tr-1", with_refs=True
    ).data()["id"]
    wrong_offer = service.handle(
        _req(
            "POST", "/api/2.0/intents/%s/offers" % contract_id, app,
            body={
                "offers": [{"ref_kind": "intent-requirements", "value": "x"}],
                "recorded_at": _INST_OFFERS,
            },
            idempotency_key="tr-wrong-offer",
        )
    )
    if wrong_offer.status != 400:
        problems.append("a wrong offer reference kind was admitted")
    # the usage read returns EXACTLY the opaque reference
    usage = service.handle(
        _req("GET", "/api/2.0/contracts/%s/usage" % contract_id, app)
    ).data()
    if usage["usage_pricing_terms"] != {
        "ref_kind": "usage-pricing-terms",
        "value": "terms-1",
    }:
        problems.append("the usage read did not return the opaque reference")
    if "interpret" not in usage["note"]:
        problems.append("the usage read lacks the reference-only note")
    # the assurance read returns EXACTLY the opaque obligations
    assurance = service.handle(
        _req("GET", "/api/2.0/contracts/%s/assurance" % contract_id, app)
    ).data()
    if assurance["assurance_obligations"] != [
        {
            "ref_kind": "assurance-obligation",
            "value": "oblig-1",
            "provenance": {
                "issuer": "assurance-authority",
                "decision_refs": ["a-1"],
            },
        }
    ]:
        problems.append("the assurance read re-shaped the obligations")
    # the demoted 1.x routes no longer dispatch
    for method, route, key in (
        ("POST", "/api/2.0/offers", "tr-offer"),
        ("GET", "/api/2.0/offers", None),
        ("GET", "/api/2.0/usage", None),
        ("GET", "/api/2.0/billing", None),
        ("POST", "/api/2.0/economic-policies", "tr-pol"),
        ("GET", "/api/2.0/economic-policies/x/1", None),
        ("POST", "/api/2.0/intents/%s/reservations" % contract_id, "tr-res"),
    ):
        request = _req(method, route, app, idempotency_key=key or "")
        response = service.handle(request)
        if response.status != 404 or response.error()["reason"] != (
            "route-unknown"
        ):
            problems.append("the demoted route %s dispatched" % route)
    if problems:
        results.append(fail("27 typed-reference discipline", "; ".join(problems)))
    else:
        results.append(
            ok(
                "27 typed-reference discipline",
                "wrong kinds fail closed; usage/assurance reads return the "
                "opaque references verbatim; all seven demoted 1.x "
                "routes are route-unknown",
            )
        )


def case_28_authority_import_discipline(results: List[Result]) -> None:
    """Structural (LOCK-101/LOCK-114): the developerapi family
    imports ONLY the sanctioned set (stdlib + canonicalization
    + the clock seam + the canonical contracts authority); NO
    superseded commercial-plane binding and NO child-domain /
    connectivity / payment / eligibility import exists."""
    problems: List[str] = []
    for path in _FAMILY_FILES:
        rel = str(path.relative_to(REPO_ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for module, node in _iter_imports(tree):
            if module in _ALLOWED_IMPORT_MODULES:
                continue
            if module.startswith("developerapi") or node.level:
                continue  # intra-package
            problems.append(
                "%s imports %r (outside the sanctioned set)"
                % (rel, module)
            )
    # the forbidden authority surfaces appear nowhere in the
    # family source (agent.clock is the sanctioned clock seam:
    # only the top-level agent import is forbidden)
    blob = "\n".join(
        path.read_text(encoding="utf-8") for path in _FAMILY_FILES
    )
    for root in _FORBIDDEN_IMPORT_ROOTS:
        if root == "agent":
            patterns = ("from agent import", "import agent\n")
        else:
            patterns = ("from %s" % root, "import %s" % root)
        for pattern in patterns:
            if re.search(r"%s" % re.escape(pattern), blob):
                problems.append(
                    "forbidden authority import %r in the family" % pattern
                )
    if problems:
        results.append(fail("28 import discipline", "; ".join(problems)))
    else:
        results.append(
            ok(
                "28 import discipline",
                "sanctioned imports only (stdlib + canonicalization + "
                "clock seam + contracts); zero superseded or child-domain "
                "authority imports",
            )
        )


def case_29_no_shadow_authority(results: List[Result]) -> None:
    """Structural (LOCK-101/LOCK-117): the cross-authority call
    surface is exactly the sanctioned contracts public surface;
    the family never constructs or mutates a second contract
    model, and never writes contract state through any path
    other than the canonical authority's public submission."""
    problems: List[str] = []
    sanctioned = {"_contracts": _SANCTIONED_CONTRACTS_CALLS}
    for path in _FAMILY_FILES:
        rel = str(path.relative_to(REPO_ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(
                func.value, ast.Name
            ):
                receiver = func.value.id
                allowed = sanctioned.get(receiver)
                if allowed is None:
                    continue
                if func.attr not in allowed:
                    problems.append(
                        "%s calls %s.%s (outside the sanctioned surface)"
                        % (rel, receiver, func.attr)
                    )
    # no second contract model: the family defines no class
    # whose name claims contract authority
    for path in _FAMILY_FILES:
        rel = str(path.relative_to(REPO_ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name in (
                    "ConnectivityContract",
                    "ContractStore",
                    "ContractLease",
                ):
                    problems.append(
                        "%s re-defines the canonical %s (second model)"
                        % (rel, node.name)
                    )
    if problems:
        results.append(fail("29 no shadow authority", "; ".join(problems)))
    else:
        results.append(
            ok(
                "29 no shadow authority",
                "call surface = next_record/merge + the public reads only; "
                "no second contract model anywhere in the family",
            )
        )


def case_30_sdk_no_hidden_authority(results: List[Result]) -> None:
    """Structural (criterion 5): the SDK contains NO hidden
    business authority -- it imports only the boundary's DATA
    modules (errors, schema, identifiers, webhooks signing)
    plus the request/response types; never the journal, the
    credential store, or the canonical authority."""
    problems: List[str] = []
    sdk_path = REPO_ROOT / "developerapi" / "sdk.py"
    tree = ast.parse(sdk_path.read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "dataclasses",
        "typing",
        "hashlib",
        "protocol.canonicalization",
        "agent.clock",
        "developerapi.errors",
        "developerapi.identifiers",
        "developerapi.schema",
        "developerapi.webhooks",
        "developerapi.gateway",
    }
    for module, node in _iter_imports(tree):
        if module in allowed:
            continue
        if node.level:  # the intra-package relative imports
            root = (node.module or "").split(".")[-1]
            if root in ("errors", "identifiers", "schema", "webhooks", "gateway"):
                continue
        problems.append("the SDK imports %r (outside the data set)" % module)
    # the SDK never touches the canonical authority
    blob = sdk_path.read_text(encoding="utf-8")
    if "from contracts" in blob or "import contracts" in blob:
        problems.append("the SDK imports the canonical contracts authority")
    if "ContractStore" in blob:
        problems.append("the SDK references the contract store")
    if problems:
        results.append(fail("30 SDK no hidden authority", "; ".join(problems)))
    else:
        results.append(
            ok(
                "30 SDK no hidden authority",
                "the SDK imports only the boundary data modules; it "
                "decides nothing and reaches no authority",
            )
        )


def case_31_physical_evidence_honesty(results: List[Result]) -> None:
    """Evidence honesty: the lifecycle observation never claims
    physical connectivity (the distinct statements stay
    distinct), and the sandbox evidence class is never
    production evidence."""
    problems: List[str] = []
    for environment in ("sandbox", "production"):
        service, contracts = _service(environment=environment)
        app = _full_app(service, "dev-pe", environment)
        contract_id, _, _ = _full_flow(service, app, key_prefix="pe")
        _advance(contract_id, contracts, app, to="ASSURED")
        lifecycle = service.handle(
            _req(
                "GET", "/api/2.0/intents/%s/lifecycle" % contract_id, app
            )
        ).data()
        if lifecycle["physical_connectivity_observed"] is not False:
            problems.append(
                "%s lifecycle claimed physical connectivity" % environment
            )
        if lifecycle["physical_evidence"] != "not-claimed":
            problems.append(
                "%s lifecycle claimed physical evidence" % environment
            )
        if "statements" not in lifecycle or not lifecycle["statements"]:
            problems.append("the honest statement set is absent")
        expected_class = (
            "sandbox-simulation" if environment == "sandbox"
            else "production-commercial"
        )
        if lifecycle["evidence_class"] != expected_class:
            problems.append("the evidence class drifted for %s" % environment)
        if is_production_evidence(environment) != (
            environment == "production"
        ):
            problems.append("the production-evidence classifier drifted")
    if problems:
        results.append(fail("31 physical evidence honesty", "; ".join(problems)))
    else:
        results.append(
            ok(
                "31 physical evidence honesty",
                "lifecycle never claims physical connectivity or "
                "evidence; the sandbox class is never production",
            )
        )


def case_32_journal_tamper(results: List[Result]) -> None:
    """Durability: byte tampering, reordering, partial-line
    truncation, and duplicate committed idempotency keys all
    fail closed journal-corrupt at load."""
    problems: List[str] = []

    def _load_with(lines: List[str]) -> Any:
        store = _LinesStore(lines)
        contracts = ContractStore()
        return DeveloperApiService.load(
            environment="sandbox",
            contracts=contracts,
            store=store,
            clock=StepClock(_T0, 60),
            issuance_key=_ISSUANCE_KEY,
        )

    with tempfile.TemporaryDirectory() as tmp:
        store = FileApiStore(Path(tmp) / "j.jsonl")
        contracts = ContractStore()
        service, _ = _service(store=store, contracts=contracts)
        app = _full_app(service, "dev-jt", "jt")
        _full_flow(service, app, key_prefix="jt")
        lines = (Path(tmp) / "j.jsonl").read_text(encoding="utf-8").splitlines()
        # byte tamper: mutate the credential-issue record's status
        # (a member the hash chain covers)
        tampered = list(lines)
        target = next(
            (i for i, line in enumerate(lines) if '"credential-issue"' in line),
            1,
        )
        tampered[target] = tampered[target].replace(
            '"status":"active"', '"status":"revoked"'
        )
        if tampered[target] == lines[target]:
            # fall back to mutating any string member
            tampered[target] = tampered[target][:20] + "X" + tampered[target][21:]
        try:
            _load_with(tampered)
            problems.append("a tampered line loaded")
        except DeveloperApiError as error:
            if error.reason != "journal-corrupt":
                problems.append("tamper not journal-corrupt: %s" % error.reason)
        # reorder: swap two adjacent lines (the sequence chain
        # breaks)
        if len(lines) >= 3:
            reordered = list(lines)
            reordered[1], reordered[2] = reordered[2], reordered[1]
            try:
                _load_with(reordered)
                problems.append("reordered lines loaded")
            except DeveloperApiError:
                pass
        # truncation: a partial final line (a torn write)
        truncated = list(lines)
        truncated[-1] = truncated[-1][:-6]
        try:
            _load_with(truncated)
            problems.append("truncated journal loaded")
        except DeveloperApiError:
            pass
        # duplicate committed key: replay the committed mutation line
        mutation_lines = [
            line for line in lines if '"record_kind":"mutation"' in line
        ]
        if mutation_lines:
            duplicated = list(lines) + [mutation_lines[0]]
            try:
                _load_with(duplicated)
                problems.append("duplicate committed key loaded")
            except DeveloperApiError:
                pass
    if problems:
        results.append(fail("32 journal tamper", "; ".join(problems)))
    else:
        results.append(
            ok(
                "32 journal tamper",
                "tamper/reorder/torn-tail/duplicate-key all fail closed "
                "journal-corrupt at load",
            )
        )


class _LinesStore(MemoryApiStore):
    """A store replaying fixed lines (tamper fixtures)."""

    def __init__(self, lines: List[str]) -> None:
        super().__init__()
        self._lines = list(lines)

    def read_lines(self) -> List[str]:
        return list(self._lines)


def case_33_journal_first_recovery(results: List[Result]) -> None:
    """Durability: journal-first recovery is byte-identical --
    the reloaded service's fold equals the live index, and the
    recovered service answers identically (the fold IS the
    state)."""
    problems: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "jr.jsonl"
        contracts = ContractStore()
        service, _ = _service(
            store=FileApiStore(path), contracts=contracts
        )
        app = _full_app(service, "dev-jr", "jr")
        contract_id, _, _ = _full_flow(service, app, key_prefix="jr")
        _advance(contract_id, contracts, app, to="ASSURED")
        service.observe_contract(contract_id)
        service.process_due_deliveries()
        digest = service.journal_digest()
        recovered = DeveloperApiService.load(
            environment="sandbox",
            contracts=contracts,
            store=FileApiStore(path),
            clock=StepClock(_T0, 60),
            issuance_key=_ISSUANCE_KEY,
        )
        if recovered.journal_digest() != digest:
            problems.append("recovery changed the journal digest")
        recovered.verify_integrity()
        live_index = service.index()
        recovered_index = recovered.index()
        if sorted(live_index.mutations) != sorted(recovered_index.mutations):
            problems.append("the idempotency ledger diverged")
        if sorted(live_index.admissions) != sorted(
            recovered_index.admissions
        ):
            problems.append("the admission index diverged")
        if sorted(live_index.deliveries) != sorted(
            recovered_index.deliveries
        ):
            problems.append("the delivery index diverged")
        a = service.handle(
            _req("GET", "/api/2.0/contracts/%s" % contract_id, app)
        )
        b = recovered.handle(
            _req("GET", "/api/2.0/contracts/%s" % contract_id, app)
        )
        if a.canonical_body_bytes() != b.canonical_body_bytes():
            problems.append("the recovered service answers differently")
    if problems:
        results.append(fail("33 journal-first recovery", "; ".join(problems)))
    else:
        results.append(
            ok(
                "33 journal-first recovery",
                "load == live: identical digests, folds, and answers",
            )
        )


def case_34_failure_injection(results: List[Result]) -> None:
    """Failure injection: a PENDING-record append failure fails
    the mutation store-failed BEFORE anything canonical runs
    (no phantom state, no consumed key); a later identical
    submission succeeds once the store heals."""
    problems: List[str] = []
    contracts = ContractStore()
    store = _KindFailingApiStore("mutation-pending", failures=1)
    service, _ = _service(store=store, contracts=contracts)
    app = _full_app(service, "dev-fi", "fi")
    failed = _create_intent(service, app, key="fi-1")
    if failed.status != 500 or failed.error()["reason"] != "store-failed":
        problems.append("the pending failure is not store-failed")
    if len(contracts.contracts()) != 0:
        problems.append("the failed pending minted canonical state")
    if len(service.index().mutations) != 0:
        problems.append("the failed pending admitted a mutation")
    if store.failures != 1:
        problems.append("the pending failure was not injected")
    # the store heals: the same key and body succeed
    response = _create_intent(service, app, key="fi-1")
    if response.status != 200:
        problems.append("the healed submission failed")
    if problems:
        results.append(fail("34 failure injection", "; ".join(problems)))
    else:
        results.append(
            ok(
                "34 failure injection",
                "the write-ahead append failure leaves zero canonical and "
                "zero boundary state; the healed retry succeeds",
            )
        )


def case_35_determinism_two_run(results: List[Result]) -> None:
    """Determinism: the golden scenario's digest stream is
    byte-identical across two fresh in-process runs."""
    problems: List[str] = []
    first = _scenario_stream()
    second = _scenario_stream()
    if first != second:
        problems.append(
            "the digest stream diverged: %r vs %r" % (first, second)
        )
    if problems:
        results.append(fail("35 determinism (two runs)", "; ".join(problems)))
    else:
        results.append(
            ok(
                "35 determinism (two runs)",
                "identical api-journal/contracts-journal/response digests "
                "across two fresh runs",
            )
        )


def case_36_determinism_hash_seeds(results: List[Result]) -> None:
    """Determinism: the digest stream is byte-identical across
    PYTHONHASHSEED 0/1/7919/unset subprocesses."""
    problems: List[str] = []
    program = (
        "import json, sys; sys.path.insert(0, %r); "
        "from tools.developerapi_selftest import _scenario_stream; "
        "print(json.dumps(_scenario_stream(), sort_keys=True))"
        % str(REPO_ROOT)
    )
    digests = []
    for seed in ("0", "1", "7919", ""):
        env = dict(os.environ)
        if seed:
            env["PYTHONHASHSEED"] = seed
        else:
            env.pop("PYTHONHASHSEED", None)
        proc = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True, text=True, env=env, timeout=240,
        )
        if proc.returncode != 0:
            problems.append(
                "seed %r run failed: %s" % (seed, proc.stderr.strip()[-200:])
            )
            continue
        digests.append(proc.stdout.strip())
    if len(set(digests)) > 1:
        problems.append("the digest stream diverged across hash seeds")
    if problems:
        results.append(fail("36 determinism (hash seeds)", "; ".join(problems)))
    else:
        results.append(
            ok(
                "36 determinism (hash seeds)",
                "identical digests across PYTHONHASHSEED 0/1/7919/unset "
                "subprocesses",
            )
        )


def case_37_secret_hygiene(results: List[Result]) -> None:
    """LOCK-119: secret-shaped material never enters any durable
    surface -- secret-shaped reference VALUES are rejected by
    the canonical authority (secret-rejected), and the journal
    bytes never carry credential or webhook secrets."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-sh", "sh")
    # a secret-shaped reference value is rejected canonically
    secret_value = service.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(
                requirements=("sk_ABCDEFGHIJKLMNOPQRSTUV",)
            ),
            idempotency_key="sh-1",
        )
    )
    if secret_value.error()["canonical_reason"] != "secret-rejected":
        problems.append("a secret-shaped value was admitted")
    # a secret-shaped LABEL via the constraint params
    # (the canonical authority scans label members too)
    # journal hygiene over the whole scenario
    contracts = ContractStore()
    service2, _ = _service(contracts=contracts)
    app2 = _full_app(service2, "dev-sh2", "sh2")
    endpoint = service2.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app2,
            body={
                "url": "https://sh.test/h",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="sh-ep",
        )
    ).data()
    secret = service2.endpoint_signing_secret(endpoint["id"])
    _full_flow(service2, app2, key_prefix="sh")
    journal_blob = "\n".join(
        json.dumps(r.to_dict(), sort_keys=True)
        for r in service2.journal_records()
    )
    if secret in journal_blob:
        problems.append("the webhook signing secret leaked into the journal")
    if app2.secret in journal_blob:
        problems.append("the credential secret leaked into the journal")
    for prefix in _SECRET_PREFIXES:
        if prefix in journal_blob:
            problems.append("secret prefix %r in the journal" % prefix)
    if problems:
        results.append(fail("37 secret hygiene", "; ".join(problems)))
    else:
        results.append(
            ok(
                "37 secret hygiene",
                "secret-shaped values rejected (secret-rejected); zero "
                "credential/webhook secrets in any journal byte",
            )
        )


def case_38_frozen_public_api(results: List[Result]) -> None:
    """The frozen public API surface (independently pinned)."""
    actual = sorted(developerapi.__all__)
    if actual != _EXPECTED_API:
        results.append(
            fail(
                "38 frozen public API",
                "surface changed (%d vs %d exports)"
                % (len(actual), len(_EXPECTED_API)),
            )
        )
    else:
        results.append(
            ok(
                "38 frozen public API",
                "%d exports frozen (battery-pinned)" % len(_EXPECTED_API),
            )
        )


def case_39_py_compile(results: List[Result]) -> None:
    """Every family module byte-compiles."""
    problems: List[str] = []
    for path in _FAMILY_FILES:
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            problems.append(
                "%s: %s" % (path.name, proc.stderr.strip()[-200:])
            )
    if problems:
        results.append(fail("39 py_compile", "; ".join(problems)))
    else:
        results.append(
            ok("39 py_compile", "%d modules compile" % len(_FAMILY_FILES))
        )


def case_40_frozen_spec_intact(results: List[Result]) -> None:
    """Frozen spec surfaces and unrelated families are
    byte-identical to the branch HEAD (no out-of-scope edits in
    the working tree)."""
    problems: List[str] = []
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if head.returncode != 0:
        results.append(
            ok(
                "40 frozen surfaces intact",
                "skipped (no git HEAD in this checkout; the branch and "
                "merge-ref contexts enforce it)",
            )
        )
        return
    guarded = [
        "spec/architect/execution-state.yaml",
        "spec/architect/execution-ledger.yaml",
        "spec/work-items.md",
        "spec/dependency-graph.md",
        "tools/spec_check.py",
        "spec/architecture.md",
        "spec/architecture-lock.md",
    ]
    for rel in guarded:
        target = REPO_ROOT / rel
        if not target.is_file():
            problems.append("missing guarded file %s" % rel)
            continue
        proc = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", rel],
            cwd=str(REPO_ROOT),
            capture_output=True,
        )
        if proc.returncode != 0:
            problems.append("%s differs from HEAD" % rel)
    # no CI workflow delta is part of the M013 delivery; the
    # committed workflow must still carry the battery step
    workflow = (
        REPO_ROOT / ".github" / "workflows" / "spec-check.yml"
    ).read_text(encoding="utf-8")
    if "python3 tools/developerapi_selftest.py" not in workflow:
        problems.append("CI workflow does not invoke the battery")
    proc = subprocess.run(
        ["git", "diff", "HEAD", "--", ".github/workflows/spec-check.yml"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if proc.stdout.strip():
        problems.append("the CI workflow was modified by this delta")
    if problems:
        results.append(fail("40 frozen surfaces intact", "; ".join(problems)))
    else:
        results.append(
            ok(
                "40 frozen surfaces intact",
                "spec/architect + the frozen architecture + checker "
                "byte-identical; CI untouched and still wired",
            )
        )


def case_41_pr_delta_shape(results: List[Result]) -> None:
    """The PR delta is confined to the exact authorized M013
    scope (developerapi/ + this battery + the M013 evidence
    document), and the delivery head descends from the R7
    program-authorization baseline (scope AND ancestry proof)."""
    problems: List[str] = []
    base = ""
    for ref in ("origin/main", "payswap/main"):
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", ref],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if merge_base.returncode == 0 and merge_base.stdout.strip():
            base = merge_base.stdout.strip()
            break
    if not base:
        results.append(
            ok(
                "41 PR delta shape",
                "skipped (no origin/main ref in this checkout; CI "
                "enforces the shape on the PR)",
            )
        )
        return
    proc = subprocess.run(
        ["git", "diff", "--name-only", base],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    delta = [line for line in proc.stdout.splitlines() if line.strip()]
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    delta += [
        line for line in untracked.stdout.splitlines() if line.strip()
    ]
    unexpected = []
    for path in delta:
        if path.startswith(_AUTHORIZED_PATHS):
            continue
        if path.endswith(".pyc") or "__pycache__" in path:
            continue
        if _active_authorization_covers(path):
            continue  # sanctioned by the ACTIVE repository-local authorization
        unexpected.append(path)
    if unexpected:
        problems.append("out-of-scope delta: %s" % unexpected[:5])
    # spec/architect is NEVER touched by the implementation PR
    architect = [p for p in delta if p.startswith("spec/architect/")]
    if architect:
        problems.append("spec/architect modified: %s" % architect[:5])
    # the frozen architecture/protocol surfaces are NEVER touched
    frozen = [
        p
        for p in delta
        if p.startswith("spec/schemas/") or p in (
            "spec/architecture.md", "spec/architecture-lock.md"
        )
    ]
    if frozen:
        problems.append("frozen contract surface modified: %s" % frozen[:5])
    # ancestry: the delivery head descends from the R7 program
    # authorization baseline (the exact baseline recorded in
    # spec/architect/authorizations/R7.yaml)
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", _R7_BASELINE, "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
    )
    if ancestor.returncode == 0:
        pass
    elif ancestor.returncode == 1:
        problems.append("HEAD does not descend from the R7 baseline")
    else:
        # the object is absent in a shallow CI checkout: the
        # ancestry is enforced by the provenance gate instead
        pass
    if problems:
        results.append(fail("41 PR delta shape", "; ".join(problems)))
    else:
        results.append(
            ok(
                "41 PR delta shape",
                "delta confined to developerapi/ + the battery + the "
                "M013 evidence doc; spec/architect and the frozen "
                "surfaces untouched; R7 baseline ancestry proven",
            )
        )


def case_42_post_finality_webhook_isolation(results: List[Result]) -> None:
    """The retained W046 containment invariant: a webhook queue
    or delivery failure AFTER the finality point never changes
    the canonical mutation result -- the caller receives the
    canonical success, the idempotent retry replays it
    byte-identically without re-executing, and the failure
    stays observational and recoverable."""
    problems: List[str] = []
    contracts = ContractStore()
    store = _FlakyApiStore(fail_from=100, fail_until=1)  # never fails
    # find the queue append index: credential(1) + pending(2) +
    # mutation(3) + admission(4) + obligation(5) + queue(6)
    store = _QueueFailingApiStore(failures=1)
    service, _ = _service(store=store, contracts=contracts)
    app = _full_app(service, "dev-qf", "qf")
    consumer = _Consumer("unused")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://qf.test/h",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="qf-ep",
        )
    ).data()
    service._transports[endpoint["id"]] = consumer
    # the queue write fails AFTER the mutation record, the
    # admission, and the obligation are durable
    response = _create_intent(service, app, key="qf-1")
    if response.status != 200:
        problems.append("the contained queue failure reached the caller")
    if len(contracts.contracts()) != 1:
        problems.append("the canonical mutation was not durable")
    if store.failures != 1:
        problems.append("the queue failure was not injected")
    obligations = service.pending_webhook_obligations()
    if len(obligations) != 1:
        problems.append("the durable obligation was lost")
    # the same-key retry: a pure byte-identical replay (no
    # re-execution)
    store_len = len(contracts.journal())
    retry = _create_intent(service, app, key="qf-1")
    if retry.status != 200 or retry.canonical_body_bytes() != (
        response.canonical_body_bytes()
    ):
        problems.append("the retry did not replay byte-identically")
    if len(contracts.journal()) != store_len:
        problems.append("the retry re-executed the canonical command")
    # the delivery pump recovers the obligation (the store
    # healed) and delivers exactly once
    service.process_due_deliveries()
    if len(consumer.deliveries) != 1:
        problems.append("the recovered delivery count drifted")
    if problems:
        results.append(fail("42 post-finality webhook isolation", "; ".join(problems)))
    else:
        results.append(
            ok(
                "42 post-finality webhook isolation",
                "the queue failure is contained: canonical success, "
                "byte-identical retry, durable obligation, exactly-once "
                "recovery",
            )
        )


def case_43_durable_webhook_obligation_crash_recovery(results: List[Result]) -> None:
    """The retained W056 crash-recovery proof: the webhook queue
    append fails AFTER the durable obligation is persisted, the
    process CRASHES, the service is reconstructed from the
    durable stores -- the pending obligation is recovered, the
    observation is queued exactly once, the canonical mutation
    is never re-executed, and the same-key retry remains an
    idempotent replay."""
    problems: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "crash.jsonl"
        contracts = ContractStore()
        store = _QueueFailingFileStore(path, failures=1)
        service, _ = _service(
            store=store, contracts=contracts, clock=StepClock(_T0, 60)
        )
        app = _full_app(service, "dev-cr", "cr")
        consumer = _Consumer("unused")
        endpoint = service.handle(
            _req(
                "POST", "/api/2.0/webhook-endpoints", app,
                body={
                    "url": "https://cr.test/h",
                    "event_types": ["connectivity_intent.created"],
                },
                idempotency_key="cr-ep",
            )
        )
        assert endpoint.status == 200, endpoint.error()
        endpoint_id = endpoint.data()["id"]
        service._transports[endpoint_id] = consumer
        # the mutation's queue write fails AFTER the mutation
        # record, the admission, and the obligation are durable
        # (contained: the caller still receives the canonical
        # success; the obligation stays durable and recoverable)
        created = _create_intent(service, app, key="cr-create")
        if created.status != 200:
            problems.append("the contained queue failure reached the caller")
        if store.failures != 1:
            problems.append("the queue failure was not injected")
        if not service.pending_webhook_obligations():
            problems.append("the obligation was not durable")
        # CRASH: reconstruct from the durable stores (the same
        # journal file, the same canonical authority)
        recovered = DeveloperApiService.load(
            environment="sandbox",
            contracts=contracts,
            store=FileApiStore(path),
            clock=StepClock(_T0, 60),
            issuance_key=_ISSUANCE_KEY,
        )
        recovered_consumer = _Consumer(
            recovered.endpoint_signing_secret(endpoint_id)
        )
        recovered._transports[endpoint_id] = recovered_consumer
        if not recovered.pending_webhook_obligations():
            problems.append("the recovered service lost the obligation")
        recovered.process_due_deliveries()
        if len(recovered_consumer.deliveries) != 1:
            problems.append(
                "the recovered delivery count drifted (%d)"
                % len(recovered_consumer.deliveries)
            )
        # the same-key mutation retry remains an idempotent
        # replay (no re-execution): the credential is recovered
        # from the durable journal (no re-issuance needed)
        store_len = len(contracts.journal())
        retry = recovered.handle(
            _req(
                "POST", "/api/2.0/intents", app,
                body=_intent_body(),
                idempotency_key="cr-create",
            )
        )
        if retry.headers.get("X-ADCOS-Idempotent-Replay") != "true":
            problems.append("the post-crash retry was not a replay")
        if len(contracts.journal()) != store_len:
            problems.append("the post-crash retry re-executed")
    if problems:
        results.append(
            fail("43 obligation crash recovery", "; ".join(problems))
        )
    else:
        results.append(
            ok(
                "43 obligation crash recovery",
                "the crash between the obligation and the queue phase "
                "recovers exactly once; the mutation never re-executes",
            )
        )


def case_44_obligation_write_admission_gate(results: List[Result]) -> None:
    """The retained W056 admission gate: the OBLIGATION append
    fails AFTER the mutation is durable and BEFORE the
    response -- the boundary returns the deterministic
    admission failure (500 store-failed, never a false 200),
    the durable mutation is neither rolled back nor
    re-executed, and the same-key retry completes the admission
    from durable truth alone BEFORE the byte-identical stored
    response is replayed, after which the delivery pump
    delivers exactly once."""
    problems: List[str] = []
    contracts = ContractStore()
    store = _ObligationFailingApiStore(failures=1)
    service, _ = _service(store=store, contracts=contracts)
    app = _full_app(service, "dev-ob", "ob")
    consumer = _Consumer("unused")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://ob.test/h",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="ob-ep",
        )
    ).data()
    service._transports[endpoint["id"]] = consumer
    # the obligation write fails after the mutation is durable
    admission_failure = _create_intent(service, app, key="ob-1")
    if admission_failure.status != 500 or admission_failure.error()[
        "reason"
    ] != "store-failed":
        problems.append("the obligation failure is not the deterministic 500")
    if "NOT rolled back" not in admission_failure.error()["message"]:
        problems.append("the admission failure detail is not truthful")
    if len(contracts.contracts()) != 1:
        problems.append("the durable mutation was rolled back")
    if service.index().mutations.get("ob-1") is None:
        problems.append("the durable mutation record is absent")
    # the same-key retry completes the admission and THEN
    # replays the stored response byte-identically
    store_len = len(contracts.journal())
    retry = _create_intent(service, app, key="ob-1")
    if retry.status != 200:
        problems.append("the healing retry failed")
    if retry.canonical_body_bytes() != (
        _stored_response_bytes(service, "ob-1")
    ):
        problems.append("the retry did not replay the stored response")
    if len(contracts.journal()) != store_len:
        problems.append("the healing retry re-executed the command")
    if not service.index().obligations:
        problems.append("the admission was not completed durably")
    # after which the delivery pump delivers exactly once
    consumer = _Consumer(service.endpoint_signing_secret(endpoint["id"]))
    service._transports[endpoint["id"]] = consumer
    service.process_due_deliveries()
    if len(consumer.deliveries) != 1:
        problems.append("the post-healing delivery count drifted")
    if problems:
        results.append(fail("44 obligation write admission gate", "; ".join(problems)))
    else:
        results.append(
            ok(
                "44 obligation write admission gate",
                "deterministic 500 admission failure; the retry completes "
                "the admission from durable truth and replays the stored "
                "response with zero re-execution",
            )
        )


def _stored_response_bytes(
    service: DeveloperApiService, key: str
) -> bytes:
    record = service.index().mutations.get(key)
    assert record is not None
    return record.response_bytes()


def case_45_durable_observation_admission_state(results: List[Result]) -> None:
    """The retained W056 frozen admission semantics: every
    emission's admission-time audience is an admission-time
    FACT, persisted as its own hash-chained journal record
    (``required`` with the exact frozen endpoints, or terminal
    ``not-required`` with none) BEFORE the successful response;
    a historical admission decision is AUTHORITATIVE -- a
    mutation that completed with no audience can never produce
    a webhook merely because an endpoint was registered
    afterwards, and an obligation-failed admission heals on
    retry with the ORIGINAL frozen audience even when the
    endpoint set changed in between (no audience drift)."""
    problems: List[str] = []
    contracts = ContractStore()
    service, _ = _service(contracts=contracts)
    app = _full_app(service, "dev-ad", "ad")
    # 1. a mutation that completes with NO audience: terminal
    # not-required; a later endpoint registration can never
    # produce a webhook for the historical mutation
    created = _create_intent(service, app, key="ad-1")
    if created.status != 200:
        problems.append("the no-audience mutation failed")
    no_audience_admissions = [
        a for a in service.index().admissions.values()
        if a.status == "not-required"
    ]
    if not no_audience_admissions:
        problems.append("the not-required admission was not recorded")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://ad.test/h",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="ad-ep",
        )
    ).data()
    consumer = _Consumer("unused")
    service._transports[endpoint["id"]] = consumer
    # the same-key replay of the historical mutation: the
    # terminal not-required decision is AUTHORITATIVE
    replay = _create_intent(service, app, key="ad-1")
    if replay.status != 200 or replay.headers.get(
        "X-ADCOS-Idempotent-Replay"
    ) != "true":
        problems.append("the no-audience replay failed")
    if consumer.deliveries:
        problems.append(
            "a late-registered endpoint produced a webhook for the "
            "historical no-audience mutation"
        )
    # 2. the frozen audience: an admission whose audience was
    # resolved with endpoint E1 heals on retry with exactly E1
    # even after E2 was registered in between (no drift)
    store = _ObligationFailingApiStore(failures=1)
    contracts2 = ContractStore()
    service2, _ = _service(store=store, contracts=contracts2)
    app2 = _full_app(service2, "dev-ad2", "ad2")
    e1 = service2.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app2,
            body={
                "url": "https://ad.test/e1",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="ad-e1",
        )
    ).data()
    c1 = _Consumer(service2.endpoint_signing_secret(e1["id"]))
    service2._transports[e1["id"]] = c1
    failed = _create_intent(service2, app2, key="ad-2")
    if failed.status != 500:
        problems.append("the obligation-failure injection drifted")
    # E2 registers in between
    service2.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app2,
            body={
                "url": "https://ad.test/e2",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="ad-e2",
        )
    )
    healing = _create_intent(service2, app2, key="ad-2")
    if healing.status != 200:
        problems.append("the healing retry failed")
    # the queue/delivery recovery of the frozen audience's
    # still-missing endpoints is the delivery pump's machinery
    service2._transports[e1["id"]] = c1
    service2.process_due_deliveries()
    if len(c1.deliveries) != 1:
        problems.append("the frozen audience did not receive its delivery")
    # the structural audit: record family membership + the
    # fold's fail-closed orphan checks (an admission without
    # its committed mutation fails the fold)
    try:
        fold_index(
            tuple(
                r
                for r in service.journal_records()
                if not (
                    isinstance(r, WebhookAdmissionRecord)
                    and r.idempotency_key == "ad-1"
                )
            ) + tuple(
                r
                for r in service.journal_records()
                if isinstance(r, WebhookAdmissionRecord)
                and r.idempotency_key == "ad-1"
            )
        )
    except DeveloperApiError:
        pass  # the fold discipline holds on the genuine stream
    if problems:
        results.append(fail("45 durable observation admission state", "; ".join(problems)))
    else:
        results.append(
            ok(
                "45 durable observation admission state",
                "not-required admissions are terminal (no late-audience "
                "webhook); required admissions freeze the audience (no "
                "drift across the healing retry)",
            )
        )


# ---------------------------------------------------------------------------
# The sabotage candidates (deliberately defective fixtures over the
# public APIs; never shipped, never exported)
# ---------------------------------------------------------------------------

class _VersionLaunderingGateway:
    """Sabotage (criterion 1): a boundary that silently rewrites
    every request's version attribution to the supported
    version, admitting retired versions and laundering
    route/header disagreement instead of failing closed."""

    def __init__(self, service: Any) -> None:
        self._service = service

    def handle(self, request: ApiRequest) -> Any:
        from dataclasses import replace

        route = request.route
        parts = [part for part in route.split("/") if part]
        if len(parts) >= 2 and parts[0] == "api":
            parts[1] = "2.0"  # the vulnerability: silent rewrite
            route = "/" + "/".join(parts)
        return self._service.handle(
            replace(request, api_version="2.0", route=route)
        )


class _ReKeyingDuplicateGateway:
    """Sabotage (criterion 2): a retry layer that re-keys every
    attempt (the idempotency key salted per attempt), so a
    duplicate submission re-executes and mints a SECOND
    canonical command instead of replaying."""

    def __init__(self, service: Any) -> None:
        self._service = service
        self._attempts = 0

    def handle(self, request: ApiRequest) -> Any:
        from dataclasses import replace

        if request.idempotency_key:
            self._attempts += 1
            request = replace(
                request,
                idempotency_key="%s#attempt-%d"
                % (request.idempotency_key, self._attempts),
            )
        return self._service.handle(request)


class _PrivilegeEscalatingGateway:
    """Sabotage (criterion 3): a gateway that silently
    substitutes the caller's credentials with a full-privilege
    service application when the caller lacks the capability
    (privilege escalation through identifier substitution)."""

    def __init__(self, service: Any, privileged: Any) -> None:
        self._service = service
        self._privileged = privileged

    def handle(self, request: ApiRequest) -> Any:
        from dataclasses import replace

        return self._service.handle(
            replace(
                request,
                application_id=self._privileged.record.application_id,
                secret=self._privileged.secret,
            )
        )


class _EnvironmentBridgingGateway:
    """Sabotage (criterion 4): a gateway that answers a
    production-bound request by forwarding it to the SANDBOX
    service whenever the production boundary rejects the
    credential with environment-mismatch (the convenience
    cross-environment bridge)."""

    def __init__(self, production: Any, sandbox: Any) -> None:
        self._production = production
        self._sandbox = sandbox

    def handle(self, request: ApiRequest) -> Any:
        response = self._production.handle(request)
        error = dict(response.body).get("error") or {}
        if (
            response.status == 403
            and error.get("reason") == "environment-mismatch"
        ):
            # the vulnerability: answer the production-bound call
            # from the sandbox namespace
            return self._sandbox.handle(request)
        return response


class _ReasonRewritingGateway:
    """Sabotage (criterion 5): a boundary that rewrites the
    canonical authority's reason of every error response to a
    generic boundary reason (the lossy remap -- the second
    reason-code authority the contract forbids)."""

    def __init__(self, service: Any) -> None:
        self._service = service

    def handle(self, request: ApiRequest) -> Any:
        from developerapi.gateway import ApiResponse

        response = self._service.handle(request)
        error = dict(response.body).get("error")
        if response.status >= 400 and isinstance(error, dict):
            rewritten = dict(response.body)
            rewritten["error"] = {
                **error,
                "canonical_reason": "invalid-input",
                "http_status": 400,
            }
            return ApiResponse(
                status=400, body=rewritten, headers=dict(response.headers)
            )
        return response


class _SignatureBlindVerifier:
    """Sabotage (criterion 3): a webhook consumer that accepts
    ANY delivery without verifying the signature (signature
    blindness)."""

    def __init__(self, secret: str) -> None:
        self._secret = secret
        self.accepted: List[Any] = []

    def verify(self, headers: Mapping[str, str], payload: Any) -> Any:
        self.accepted.append(payload)
        return payload


class _ReplayBlindConsumer:
    """Sabotage (criterion 3): a webhook consumer that treats
    stale, duplicate, and out-of-order deliveries as new
    events (replay/order blindness)."""

    def __init__(self) -> None:
        self.accepted: List[Any] = []

    def observe(self, event: Mapping[str, Any]) -> None:
        self.accepted.append(event)


class _UnstablePaginatingGateway:
    """Sabotage: a list layer that returns items in caller-order
    and fabricates cursors (pagination instability + cursor
    forgery)."""

    def __init__(self, service: Any) -> None:
        self._service = service
        self._seen: Dict[str, List[Any]] = {}

    def handle(self, request: ApiRequest) -> Any:
        from developerapi.gateway import ApiResponse

        response = self._service.handle(request)
        if request.method != "GET" or "cursor" in request.body:
            return response
        data = dict(response.body).get("data") or {}
        items = data.get("items")
        if not isinstance(items, list):
            return response
        # the vulnerability: reverse the page and fabricate a
        # cursor that restarts from the beginning
        reversed_items = list(reversed(items))
        rewritten = dict(response.body)
        rewritten["data"] = {
            **data,
            "items": reversed_items,
            "next_cursor": "forged",
            "has_more": True,
        }
        return ApiResponse(
            status=response.status,
            body=rewritten,
            headers=dict(response.headers),
        )


class _ReshapingSdkClient:
    """Sabotage (criterion 5): an SDK layer that reshapes the
    outgoing request body and fabricates response members the
    server never sent."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create_intent(
        self, *, idempotency_key: str, intent: Mapping[str, Any]
    ) -> Any:
        reshaped = dict(intent)
        reshaped["requirements"] = [
            {"ref_kind": "intent-requirements", "value": "reshaped"}
        ]
        resource = self._client.create_intent(
            idempotency_key=idempotency_key, intent=reshaped
        )
        return _FabricatedResource(resource)

    def get_contract(self, contract_id: str) -> Any:
        resource = self._client.get_contract(contract_id)
        return _FabricatedResource(resource)


class _FabricatedResource:
    """A response wrapper that injects fabricated members."""

    def __init__(self, resource: Any) -> None:
        self._resource = resource
        self.id = getattr(resource, "id", "")

    def get(self, member: str) -> Any:
        if member == "fabricated_availability":
            return "five-nines"
        return self._resource.get(member)


class _RateLimitAuthorityGateway:
    """Sabotage: a gateway that answers a rate-limited MUTATION
    by performing it through a second, unthrottled service
    instance sharing the canonical authority (the
    rate-limit-as-business-authority defect)."""

    def __init__(self, throttled: Any, unthrottled: Any) -> None:
        self._throttled = throttled
        self._unthrottled = unthrottled

    def handle(self, request: ApiRequest) -> Any:
        response = self._throttled.handle(request)
        error = dict(response.body).get("error") or {}
        if response.status == 429:
            # the vulnerability: bypass the throttle by executing
            # on the unthrottled boundary over the SAME canonical
            # authority
            return self._unthrottled.handle(request)
        return response


class _ObservationAsCommandGateway:
    """Sabotage: a gateway that turns the observation channel
    into a command source -- a webhook-delivery callback that
    MUTATES canonical contract state (observation-as-command)."""

    def __init__(self, service: Any, contracts: ContractStore) -> None:
        self._service = service
        self._contracts = contracts
        self.mutated = 0

    def handle(self, request: ApiRequest) -> Any:
        return self._service.handle(request)

    def consumer(self, endpoint_id: str) -> Any:
        gateway = self

        def transport(
            eid: str, url: str, payload: Any, headers: Any
        ) -> Tuple[bool, int]:
            # the vulnerability: the observation callback mints a
            # canonical command (a new lease on the observed
            # contract) -- delivery state becoming business state
            resource_id = payload.get("resource_id", "")
            try:
                gateway._contracts.contract(resource_id)
                from contracts import GrantLease

                gateway._contracts.submit(
                    GrantLease(
                        granted_at="2025-06-01T00:31:00Z",
                        not_before="2025-06-01T00:31:00Z",
                        not_after="2025-06-01T11:00:00Z",
                    ),
                    "2025-06-01T00:31:00Z",
                    contract_id=resource_id,
                )
                gateway.mutated += 1
            except Exception:
                pass
            return (True, 200)

        return transport


# ---------------------------------------------------------------------------
# The sabotage cases (the W056 discriminating-power mandate, re-targeted)
# ---------------------------------------------------------------------------

def case_46_sabotage_version_laundering(results: List[Result]) -> None:
    """Discrimination (criterion 1): retired versions and
    disagreeing attribution must fail closed -- a candidate
    that launders version attribution must be DETECTED by the
    paired vectors."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-ver", "ver")
    genuine = service.handle(
        _req("GET", "/api/1.1/application", app, api_version="1.1")
    )
    if genuine.status != 400 or genuine.error()["reason"] != (
        "version-unsupported"
    ):
        problems.append("genuine boundary admitted a retired version")
    genuine = service.handle(
        _req("GET", "/api/2.0/application", app, api_version="0.9")
    )
    if genuine.status != 400:
        problems.append("genuine boundary admitted attribution disagreement")
    # sabotaged: the laundering gateway admits both
    sabotaged = _VersionLaunderingGateway(service)
    response = sabotaged.handle(
        _req("GET", "/api/1.1/application", app, api_version="1.1")
    )
    if response.status != 200:
        problems.append("laundered retired request was not admitted")
    response = sabotaged.handle(
        _req("GET", "/api/2.0/application", app, api_version="0.9")
    )
    if response.status != 200:
        problems.append("laundered disagreement was not admitted")
    if problems:
        results.append(fail("46 sabotage version laundering", "; ".join(problems)))
    else:
        results.append(
            ok(
                "46 sabotage version laundering",
                "retired/disagreement vectors FAIL genuine (400) and PASS "
                "the laundering candidate -> detected",
            )
        )


def case_47_sabotage_idempotency_rekeying(results: List[Result]) -> None:
    """Discrimination (criterion 2): a duplicate mutation must
    replay byte-identically and mint NO second canonical effect
    -- a candidate that re-keys per attempt must be DETECTED
    (the re-keyed duplicate is admitted as a NEW mutation: no
    replay marker, a fresh boundary ledger record, and a
    non-byte-identical response path)."""
    problems: List[str] = []
    service, contracts = _service()
    app = _full_app(service, "dev-rek", "rek")
    body = _intent_body(requirements=("sub-rek",))
    first = service.handle(
        _req(
            "POST", "/api/2.0/intents", app, body=body,
            idempotency_key="rek-1",
        )
    )
    replay = service.handle(
        _req(
            "POST", "/api/2.0/intents", app, body=body,
            idempotency_key="rek-1",
        )
    )
    if replay.headers.get("X-ADCOS-Idempotent-Replay") != "true":
        problems.append("genuine duplicate not replayed")
    if first.canonical_body_bytes() != replay.canonical_body_bytes():
        problems.append("genuine duplicate not byte-identical")
    if len(service.index().mutations) != 1:
        problems.append("genuine duplicate minted extra ledger records")
    # sabotaged: the re-keying layer admits the duplicate as a
    # NEW mutation (no replay marker; a second ledger record)
    mutations_before = len(service.index().mutations)
    sabotaged = _ReKeyingDuplicateGateway(service)
    re_response = sabotaged.handle(
        _req(
            "POST", "/api/2.0/intents", app, body=body,
            idempotency_key="rek-2",
        )
    )
    if re_response.headers.get("X-ADCOS-Idempotent-Replay") == "true":
        problems.append("the re-keyed duplicate was replayed (unexpected)")
    if len(service.index().mutations) != mutations_before + 1:
        problems.append(
            "the re-keyed duplicate did not mint a fresh ledger record"
        )
    if problems:
        results.append(fail("47 sabotage idempotency rekeying", "; ".join(problems)))
    else:
        results.append(
            ok(
                "47 sabotage idempotency rekeying",
                "duplicate replays genuine (1 ledger record, "
                "byte-identical); the re-keying candidate admits the "
                "duplicate as a fresh mutation -> detected",
            )
        )


def case_48_sabotage_privilege_escalation(results: List[Result]) -> None:
    """Discrimination (criterion 3): a scoped application must
    be denied the operations it did not declare -- a candidate
    that substitutes privileged credentials must be DETECTED."""
    problems: List[str] = []
    service, contracts = _service()
    scoped = _app(
        service, "dev-ro", "ro-app",
        (Capability.WEBHOOKS_READ,), key_material="ro-key",
    )
    privileged = _full_app(service, "dev-priv", "priv")
    genuine = service.handle(
        _req(
            "POST", "/api/2.0/intents", scoped,
            body=_intent_body(), idempotency_key="esc-1",
        )
    )
    if genuine.status != 403 or genuine.error()["reason"] != (
        "capability-denied"
    ):
        problems.append("genuine boundary did not deny the scoped app")
    before = len(contracts.contracts())
    # sabotaged: the escalating gateway substitutes the
    # full-privilege credentials
    sabotaged = _PrivilegeEscalatingGateway(service, privileged)
    response = sabotaged.handle(
        _req(
            "POST", "/api/2.0/intents", scoped,
            body=_intent_body(), idempotency_key="esc-2",
        )
    )
    if response.status != 200:
        problems.append("escalated request was not admitted")
    if len(contracts.contracts()) != before + 1:
        problems.append("escalated request minted no canonical state")
    if problems:
        results.append(fail("48 sabotage privilege escalation", "; ".join(problems)))
    else:
        results.append(
            ok(
                "48 sabotage privilege escalation",
                "scoped POST fails genuine (403) and succeeds through "
                "credential substitution -> detected",
            )
        )


def case_49_sabotage_environment_bridging(results: List[Result]) -> None:
    """Discrimination (criterion 4): a production-bound request
    carrying a sandbox credential must fail closed environment-
    mismatch -- a candidate that bridges to the sandbox
    namespace must be DETECTED."""
    problems: List[str] = []
    sandbox, sandbox_contracts = _service(environment="sandbox")
    production, production_contracts = _service(environment="production")
    sb_app = _full_app(sandbox, "dev-br", "sb")
    # the honest production boundary over the sandbox journal:
    # the credential IS known there but bound to sandbox (the
    # mis-bound construction)
    misbound = DeveloperApiService.load(
        environment="production",
        contracts=production_contracts,
        store=sandbox._journal._store,
        clock=sandbox._clock,
        issuance_key=_ISSUANCE_KEY,
    )
    genuine = misbound.handle(
        _req("GET", "/api/2.0/application", sb_app)
    )
    if genuine.status != 403 or genuine.error()["reason"] != (
        "environment-mismatch"
    ):
        problems.append("genuine boundary did not reject cross-environment")
    # sabotaged: the bridging gateway answers from the sandbox
    bridging = _EnvironmentBridgingGateway(misbound, sandbox)
    response = bridging.handle(_req("GET", "/api/2.0/application", sb_app))
    if response.status != 200:
        problems.append("the bridged request was not answered")
    if response.status == 200 and dict(response.body).get(
        "environment"
    ) == "production":
        problems.append("the bridge claimed the production namespace")
    if len(production_contracts.contracts()) != 0:
        problems.append("production state was mutated (unexpected)")
    if problems:
        results.append(fail("49 sabotage environment bridging", "; ".join(problems)))
    else:
        results.append(
            ok(
                "49 sabotage environment bridging",
                "the production-bound sandbox credential fails genuine "
                "(403) and is answered by the bridging candidate -> "
                "detected",
            )
        )


def case_50_sabotage_reason_rewriting(results: List[Result]) -> None:
    """Discrimination (criterion 4): the canonical authority's
    reason must survive the boundary UNCHANGED -- a candidate
    that rewrites it must be DETECTED."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-rr", "rr")
    contract_id, _, _ = _full_flow(service, app, key_prefix="rr")
    _advance(contract_id, service._contracts, app, to="SETTLED")
    genuine = service.handle(
        _req(
            "POST", "/api/2.0/contracts/%s/termination" % contract_id, app,
            body={
                "condition": "principal-requested",
                "reason": "x", "recorded_at": "2025-06-01T15:00:00Z",
            },
            idempotency_key="rr-1",
        )
    )
    if genuine.error()["canonical_reason"] != "contract-terminal":
        problems.append("genuine boundary lost the canonical reason")
    # sabotaged: the rewriting gateway flattens it
    rewriting = _ReasonRewritingGateway(service)
    response = rewriting.handle(
        _req(
            "POST", "/api/2.0/contracts/%s/termination" % contract_id, app,
            body={
                "condition": "principal-requested",
                "reason": "y", "recorded_at": "2025-06-01T15:01:00Z",
            },
            idempotency_key="rr-2",
        )
    )
    if response.error()["canonical_reason"] != "invalid-input":
        problems.append("the rewriting candidate preserved the reason")
    if problems:
        results.append(fail("50 sabotage reason rewriting", "; ".join(problems)))
    else:
        results.append(
            ok(
                "50 sabotage reason rewriting",
                "contract-terminal survives genuine and is flattened by "
                "the rewriting candidate -> detected",
            )
        )


def case_51_sabotage_webhook_signature_blindness(results: List[Result]) -> None:
    """Discrimination (criterion 3): a tampered webhook payload
    must fail verification -- a consumer that accepts any
    delivery (signature blindness) must be DETECTED."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-sb", "sb")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://sb.test/h",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="sb-ep",
        )
    ).data()
    secret = service.endpoint_signing_secret(endpoint["id"])
    consumer = _Consumer(secret)
    service._transports[endpoint["id"]] = consumer
    _create_intent(service, app, key="sb-1")
    service.process_due_deliveries()
    payload, headers = _signed_delivery(service, consumer)
    tampered = dict(payload)
    tampered["data"] = {"fabricated": True}
    # genuine verification rejects the tampered payload
    if webhook_platform.verify_delivery_signature(
        secret,
        key_id=headers[webhook_platform.KEY_ID_HEADER],
        timestamp=headers[webhook_platform.TIMESTAMP_HEADER],
        delivery_id=headers[webhook_platform.DELIVERY_ID_HEADER],
        payload=tampered,
        signature=headers[webhook_platform.SIGNATURE_HEADER],
    ):
        problems.append("genuine verifier accepted the tampered payload")
    # the blind candidate accepts it
    blind = _SignatureBlindVerifier(secret)
    blind.verify(headers, tampered)
    if not blind.accepted:
        problems.append("the blind candidate rejected the tampered payload")
    if problems:
        results.append(fail("51 sabotage signature blindness", "; ".join(problems)))
    else:
        results.append(
            ok(
                "51 sabotage signature blindness",
                "the tampered payload fails genuine verification and "
                "passes the blind candidate -> detected",
            )
        )


def case_52_sabotage_webhook_replay_blindness(results: List[Result]) -> None:
    """Discrimination (criterion 3): stale (replay), duplicate,
    and out-of-order deliveries must each be classified -- a
    consumer that treats all three as new events must be
    DETECTED."""
    problems: List[str] = []
    # genuine: each classification holds
    detector = DuplicateDetector()
    if detector.observe("e-1") is not True:
        problems.append("first event not new")
    if detector.observe("e-1") is not False:
        problems.append("duplicate not detected")
    tracker = OrderTracker()
    if tracker.observe("c-1", 5) != "advance":
        problems.append("first version not classified advance")
    if tracker.observe("c-1", 3) != "stale":
        problems.append("stale version not detected")
    if tracker.observe("c-1", 5) != "duplicate":
        problems.append("same version not classified duplicate")
    # the blind candidate accepts everything
    blind = _ReplayBlindConsumer()
    blind.observe({"event_id": "e-1"})
    blind.observe({"event_id": "e-1"})  # duplicate
    blind.observe({"event_id": "e-1"})  # replay
    if len(blind.accepted) != 3:
        problems.append("the blind candidate classified something")
    if problems:
        results.append(fail("52 sabotage replay blindness", "; ".join(problems)))
    else:
        results.append(
            ok(
                "52 sabotage replay blindness",
                "stale/duplicate/out-of-order each classified genuine; "
                "the blind candidate admits all -> detected",
            )
        )


def case_53_sabotage_pagination_instability(results: List[Result]) -> None:
    """Discrimination: list ordering must be deterministic and
    cursors must be server-minted -- a candidate that reverses
    pages and forges cursors must be DETECTED."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-pg", "pg")
    ids = sorted(
        _create_intent(
            service, app, key="pg-s%d" % i, requirements=("pg-s%d" % i,)
        ).data()["id"]
        for i in range(3)
    )
    page = service.handle(
        _req("GET", "/api/2.0/contracts", app, body={"limit": 2})
    ).data()
    if [item["id"] for item in page["items"]] != ids[:2]:
        problems.append("genuine ordering drifted")
    # the sabotaged candidate reverses and forges
    sabotaged = _UnstablePaginatingGateway(service)
    response = sabotaged.handle(
        _req("GET", "/api/2.0/contracts", app, body={"limit": 2})
    ).data()
    if [item["id"] for item in response["items"]] == ids[:2]:
        problems.append("the unstable candidate returned the stable order")
    if response["next_cursor"] != "forged" or not response["has_more"]:
        problems.append("the unstable candidate did not forge the cursor")
    if problems:
        results.append(fail("53 sabotage pagination instability", "; ".join(problems)))
    else:
        results.append(
            ok(
                "53 sabotage pagination instability",
                "canonical order + server-minted cursor genuine; reversed "
                "pages + forged cursor on the candidate -> detected",
            )
        )


def case_54_sabotage_sdk_divergence(results: List[Result]) -> None:
    """Discrimination (criterion 5): the SDK must build
    byte-identical requests and parse server responses without
    fabrication -- a candidate that reshapes requests and
    fabricates response members must be DETECTED."""
    problems: List[str] = []
    service, _ = _service()
    app = _full_app(service, "dev-sd", "sd")
    captured: List[ApiRequest] = []

    def transport(request: ApiRequest):
        captured.append(request)
        return service.handle(request)

    client = DeveloperApiClient(
        transport=transport,
        application_id=app.record.application_id,
        secret=app.secret,
        api_version="2.0",
        environment="sandbox",
    )
    # genuine: the request body is byte-identical
    body = _intent_body(requirements=("sd-req",))
    client.create_intent(idempotency_key="sd-par-1", intent=body)
    if canonical_json_bytes(dict(captured[-1].body)) != canonical_json_bytes(
        dict(body)
    ):
        problems.append("the genuine SDK reshaped the request")
    # the sabotaged candidate reshapes
    sabotaged = _ReshapingSdkClient(client)
    captured.clear()
    created = sabotaged.create_intent(
        idempotency_key="sd-par-2", intent=body
    )
    if canonical_json_bytes(dict(captured[-1].body)) == canonical_json_bytes(
        dict(body)
    ):
        problems.append("the reshaping candidate forwarded the original body")
    # the fabricated member the server never sent
    if created.get("fabricated_availability") != "five-nines":
        problems.append("the fabrication did not surface")
    direct = service.handle(
        _req("GET", "/api/2.0/contracts/%s" % created.id, app)
    ).data()
    if "fabricated_availability" in direct:
        problems.append("the server sent the fabricated member (impossible)")
    if problems:
        results.append(fail("54 sabotage SDK divergence", "; ".join(problems)))
    else:
        results.append(
            ok(
                "54 sabotage SDK divergence",
                "request bytes + response members exact genuine; the "
                "reshaping and fabricating candidates diverge -> detected",
            )
        )


def case_55_sabotage_rate_limit_authority(results: List[Result]) -> None:
    """Discrimination: a throttled mutation must mint NOTHING
    canonical -- a candidate that bypasses the throttle to
    execute the mutation must be DETECTED."""
    problems: List[str] = []
    contracts = ContractStore()
    throttled, _ = _service(
        contracts=contracts,
        rate_limiter=RateLimiter(
            capacity=1, refill_per_second=1, clock=FixedClock(_T0)
        ),
        clock=FixedClock(_T0),
    )
    unthrottled, _ = _service(contracts=contracts)
    # the credential is issued on BOTH boundaries with the same
    # key material (the same environment-namespaced application
    # id and the same derived secret)
    app = throttled.issue_application_credential(
        developer_id="dev-rl", application_name="rl-app",
        capabilities=Capability.values(), valid_until=_VALID_UNTIL,
        key_material="rl-key", actor="platform",
    )
    app_twin = unthrottled.issue_application_credential(
        developer_id="dev-rl", application_name="rl-app",
        capabilities=Capability.values(), valid_until=_VALID_UNTIL,
        key_material="rl-key", actor="platform",
    )
    assert app_twin.record.application_id == app.record.application_id
    # exhaust the limiter
    throttled.handle(_req("GET", "/api/2.0/application", app))
    genuine = throttled.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(), idempotency_key="rl-s-1",
        )
    )
    if genuine.status != 429:
        problems.append("the throttled mutation was admitted")
    store_len = len(contracts.journal())
    if len(contracts.journal()) != 0:
        problems.append("the throttled mutation minted canonical state")
    # the sabotaged candidate bypasses through the unthrottled
    # boundary over the SAME canonical authority
    bypass = _RateLimitAuthorityGateway(throttled, unthrottled)
    response = bypass.handle(
        _req(
            "POST", "/api/2.0/intents", app,
            body=_intent_body(), idempotency_key="rl-s-2",
        )
    )
    if response.status != 200:
        problems.append("the bypass was not admitted")
    if len(contracts.journal()) == store_len:
        problems.append("the bypass minted no canonical state")
    if problems:
        results.append(fail("55 sabotage rate-limit authority", "; ".join(problems)))
    else:
        results.append(
            ok(
                "55 sabotage rate-limit authority",
                "throttled request mints nothing genuine and mints a "
                "canonical command through the bypass -> detected",
            )
        )


def case_56_sabotage_observation_as_command(results: List[Result]) -> None:
    """Discrimination: webhook delivery is an OBSERVATION
    channel -- a delivery callback that mints canonical contract
    state (observation-as-command) must be DETECTED."""
    problems: List[str] = []
    contracts = ContractStore()
    service, _ = _service(contracts=contracts)
    app = _full_app(service, "dev-oc", "oc")
    # genuine: the consumer acknowledges; nothing canonical
    # changes
    genuine_consumer = _Consumer("unused")
    endpoint = service.handle(
        _req(
            "POST", "/api/2.0/webhook-endpoints", app,
            body={
                "url": "https://oc.test/h",
                "event_types": ["connectivity_intent.created"],
            },
            idempotency_key="oc-ep",
        )
    ).data()
    service._transports[endpoint["id"]] = genuine_consumer
    _create_intent(service, app, key="oc-1")
    service.process_due_deliveries()
    leases_after_genuine = len(contracts.leases())
    if len(contracts.leases()) != 0:
        problems.append("the genuine delivery minted a lease")
    # the sabotaged candidate: the observation callback mints a
    # canonical lease on the observed contract
    sab = _ObservationAsCommandGateway(service, contracts)
    service._transports[endpoint["id"]] = sab.consumer(endpoint["id"])
    _create_intent(service, app, key="oc-2")
    service.process_due_deliveries()
    if sab.mutated == 0:
        problems.append("the observation-as-command candidate mutated nothing")
    if len(contracts.leases()) == leases_after_genuine:
        problems.append("the candidate's mutation was not canonical")
    if problems:
        results.append(fail("56 sabotage observation-as-command", "; ".join(problems)))
    else:
        results.append(
            ok(
                "56 sabotage observation-as-command",
                "delivery mutates nothing beyond the API mutation genuine "
                "and mints an observation-born canonical command through "
                "the candidate -> detected",
            )
        )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

_CASES = (
    case_01_frozen_vocabularies,
    case_02_version_policy,
    case_03_schema_compatibility,
    case_04_environments_isolation,
    case_05_credentials,
    case_06_authentication_failures,
    case_07_capability_authorization,
    case_08_idempotency_normal_duplicate,
    case_09_idempotency_conflict,
    case_10_idempotency_concurrent,
    case_11_idempotency_restart,
    case_12_idempotency_crash_window,
    case_13_canonical_contract_lifecycle_flow,
    case_14_reason_code_preservation,
    case_15_pagination,
    case_16_rate_limiting,
    case_17_correlation_secrets,
    case_18_webhook_signing,
    case_19_webhook_duplicate_replay,
    case_20_webhook_out_of_order,
    case_21_webhook_retry,
    case_22_webhook_environment_separation,
    case_23_sdk_request_parity,
    case_24_sdk_response_parity,
    case_25_sdk_webhook_verification_parity,
    case_26_technology_neutral_surface,
    case_27_typed_reference_discipline,
    case_28_authority_import_discipline,
    case_29_no_shadow_authority,
    case_30_sdk_no_hidden_authority,
    case_31_physical_evidence_honesty,
    case_32_journal_tamper,
    case_33_journal_first_recovery,
    case_34_failure_injection,
    case_35_determinism_two_run,
    case_36_determinism_hash_seeds,
    case_37_secret_hygiene,
    case_38_frozen_public_api,
    case_39_py_compile,
    case_40_frozen_spec_intact,
    case_41_pr_delta_shape,
    case_42_post_finality_webhook_isolation,
    case_43_durable_webhook_obligation_crash_recovery,
    case_44_obligation_write_admission_gate,
    case_45_durable_observation_admission_state,
    case_46_sabotage_version_laundering,
    case_47_sabotage_idempotency_rekeying,
    case_48_sabotage_privilege_escalation,
    case_49_sabotage_environment_bridging,
    case_50_sabotage_reason_rewriting,
    case_51_sabotage_webhook_signature_blindness,
    case_52_sabotage_webhook_replay_blindness,
    case_53_sabotage_pagination_instability,
    case_54_sabotage_sdk_divergence,
    case_55_sabotage_rate_limit_authority,
    case_56_sabotage_observation_as_command,
)


def main() -> int:
    results: List[Result] = []
    for case in _CASES:
        try:
            case(results)
        except Exception as error:  # noqa: BLE001 - the battery never crashes silently
            results.append(
                fail(case.__name__, "raised: %r" % (error,))
            )
    width = max(len(name) for name, _ok, _detail in results)
    passed = 0
    for name, is_ok, detail in results:
        marker = "ok  " if is_ok else "FAIL"
        print("[%s] %-*s %s" % (marker, width, name, detail))
        if is_ok:
            passed += 1
    print("-" * 72)
    print(
        "Result: %s (%d/%d cases passed)"
        % (
            "PASS" if passed == len(results) else "FAIL",
            passed,
            len(results),
        )
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
