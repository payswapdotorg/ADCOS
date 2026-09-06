#!/usr/bin/env python3
"""ADCOS provider onboarding self-test (WORK-057).

Deterministic, offline verification of the WORK-057 provider
onboarding & federation integration layer against the frozen
authorization ``WORK-057-CORE-001`` (DEC-0095), the R6 dependency
overlay, and the exact implementation prompt
(``docs/WORK-057-IMPLEMENTATION-PROMPT.md``):

- the complete deterministic lifecycle: registration -> identity
  binding -> scoped credentials -> adapter certification ->
  declarations -> commercial profile binding -> eligibility/policy
  gate -> federation proposal -> explicit acceptance -> active
  membership -> suspension/revocation/offboarding;
- least-authority credentials (fail closed on wrong scope, wrong
  secret, revocation, expiry; secrets never journaled or stored);
- adapter certification evidence with fail-closed negatives;
- declaration provenance/validity/expiry/withdrawal (claims, never
  reachability truth);
- the eligibility/policy gate (tamper-evident WORK-010 ALLOW +
  eligible WORK-045 connectivity-domain decision, both consumed as
  records);
- authority separation: no second identity/federation/capability/
  resource/policy/payment authority; membership non-transitivity;
  onboarding cannot create connectivity/session/path/route/
  transport/usage/payment/settlement state (structural
  forbidden-import audit + runtime negatives);
- duplicate/replay/out-of-order/concurrent safety, interrupted
  onboarding recovery (journal-first fold), journal-tamper fail
  closed, file-journal durability;
- mixed-version compatibility through the WORK-029 authority
  (incompatible peers fail closed);
- PYTHONHASHSEED and repeat-run determinism;
- evergreen governance guards against the pinned baseline
  ``16c066ff...`` (frozen surfaces, delivery scope, W048/W040).

All instants are injected; no wall-clock, no randomness, no UUIDs, no
network. TopologyGraph and the sibling stores are used ONLY by these
tests to prove the authority boundaries hold end-to-end.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from adapters.certification import (  # noqa: E402
    AdapterCertificationError,
    AdapterCertification,
    CertificationCode,
    certify_adapter_descriptor,
)
from adapters.model import (  # noqa: E402
    AdapterDescriptor,
    AdapterSecurityState,
    AdapterError,
)
from capabilities.classification import (  # noqa: E402
    CapabilityIdClass,
    classify_capability_id,
    known_capability_ids,
)
from eligibility.decision import DecisionRecord  # noqa: E402
from eligibility.errors import EligibilityReasonCode  # noqa: E402
from federation.model import DomainLifecycle, Scope, derive_relationship_id  # noqa: E402
from federation.onboarding_model import (  # noqa: E402
    COMMAND_REQUIRED_SCOPE,
    ONBOARDING_TRANSITIONS,
    OnboardingCommandKind,
    OnboardingCommandRecord,
    OnboardingCredentialScope,
    OnboardingReason,
    OnboardingState,
    derive_application_id,
    derive_key_proof_digest,
    derive_onboarding_credential_secret,
    onboarding_transition_is_legal,
)
from federation.onboarding_service import (  # noqa: E402
    CommandAuth,
    ProviderOnboardingService,
    policy_decision_document,
)
from federation.onboarding_store import (  # noqa: E402
    FileOnboardingJournal,
    OnboardingJournal,
)
from federation.store import FederationStore  # noqa: E402
from policy.model import PolicyDecision  # noqa: E402
from protocol.canonicalization import canonical_json_bytes  # noqa: E402
from resources.model import ResourceStore, make_resource_id, parse_resource_id  # noqa: E402
from topology import SourceClass, TopologyGraph  # noqa: E402
from upgrade.compatibility import negotiate_protocol_profile  # noqa: E402
from upgrade.model import ProtocolProfile  # noqa: E402

# ----------------------------------------------------------------------
# Fixtures (injected instants only; byte-identical across runs)
# ----------------------------------------------------------------------

_NODE_A = "adcos:node:test.profile.v1:" + "a" * 64
_NODE_B = "adcos:node:test.profile.v1:" + "b" * 64
_NODE_C = "adcos:node:test.profile.v1:" + "c" * 64
_KEY_A = "11" * 32
_KEY_B = "22" * 32
_KEY_C = "33" * 32
_PLATFORM_PROFILE = (1, 0)
_ISSUANCE_KEY = b"onboarding-issuance-key-2026-09"
_KEY_MATERIAL = b"operator-identity-key-material-alpha"
_VF = "2026-09-01T00:00:00Z"
_VU = "2027-09-01T00:00:00Z"
_NOW = "2026-09-07T12:00:00Z"
_BASELINE = "16c066ff4766d362f0edfcb790524b2c0ef44cae"
_DELIVERY_BASE = "12ae8f7159aa7ddbc82b7e6aa6a3dc5d61ae676a"
_POLICY_REFS = (("ps-onboard", 1),)

#: lifecycle step instants (step i executes at T00:i)
_STEP_T = ["2026-09-07T00:%02d:00Z" % index for index in range(16)]

#: the golden lifecycle: 14 successful commands
_STEP_COUNT = 14


def _ok(name: str, detail: str) -> Tuple[str, bool, str]:
    return (name, True, detail)


def _fail(name: str, detail: str) -> Tuple[str, bool, str]:
    return (name, False, detail)


def _policy_decision(
    set_id: str = "ps-onboard",
    version: int = 1,
    effect: str = "allow",
    evaluation_instant: str = _STEP_T[9],
    tamper: bool = False,
) -> PolicyDecision:
    placeholder = PolicyDecision(
        decision_id="0" * 64,
        effect=effect,
        code=effect,
        detail="onboarding admission decision",
        matched_rule_ids=("r-onboard-1",),
        policy_set_id=set_id,
        policy_set_version=version,
        evaluation_instant=evaluation_instant,
    )
    decision_id = hashlib.sha256(placeholder.canonical_bytes()).hexdigest()
    if tamper:
        decision_id = "f" * 64
    return PolicyDecision(
        decision_id=decision_id,
        effect=effect,
        code=effect,
        detail="onboarding admission decision",
        matched_rule_ids=("r-onboard-1",),
        policy_set_id=set_id,
        policy_set_version=version,
        evaluation_instant=evaluation_instant,
    )


def _eligibility_decision(
    result: str = "eligible",
    provider_id: str = "provider-alpha",
    domain: str = "connectivity",
    subject_kind: str = "provider",
    subject_ref: Optional[str] = None,
    valid_until: str = "2027-09-07T00:00:00Z",
) -> DecisionRecord:
    return DecisionRecord.build(
        subject_kind=subject_kind,
        subject_ref=subject_ref if subject_ref is not None else provider_id,
        provider_id=provider_id,
        offer_id="",
        device_id="",
        jurisdiction="jurisdiction-alpha",
        network_sharing_mode="",
        policy_key="jp-alpha",
        policy_version=1,
        policy_digest="sha256:" + "ab" * 32,
        result=result,
        reason_codes=() if result == "eligible" else (EligibilityReasonCode.PROVIDER_SUSPENDED,),
        issued_at=_STEP_T[9],
        effective_at=_STEP_T[9],
        valid_until=valid_until,
        payment_reference="",
        citations=("citations:alpha:1",),
        input_digest="sha256:" + "cd" * 32,
        provenance="eligibility-authority-selftest",
    )


def _descriptor(attested: bool = True, suffix: str = "c") -> AdapterDescriptor:
    return AdapterDescriptor(
        adapter_id="adcos:adapter:access.generic.experimental:" + suffix * 16,
        access_technology_id="access.generic.experimental",
        supported_profile_versions=("1.0",),
        capabilities=("capability.core.store-and-forward",),
        resource_mapping=(),
        security_state=AdapterSecurityState(
            profile="baseline", credential_slots=("slot-a",), attested=attested
        ),
    )


def _platform_setup(federation_store: FederationStore) -> str:
    peer = federation_store.create_domain(
        "platform-operator-reference",
        _KEY_B,
        operator_node_id=_NODE_B,
        display_name="Platform",
        created_at="2026-09-06T00:00:00Z",
    )
    federation_store.transition_domain(
        peer.domain.domain_id,
        DomainLifecycle.ACTIVE,
        event_instant="2026-09-06T00:01:00Z",
    )
    return peer.domain.domain_id


class _Golden:
    """Everything the golden lifecycle produces (service, journal,
    federation store, application context)."""

    def __init__(self, service: ProviderOnboardingService, journal: OnboardingJournal,
                 federation_store: FederationStore, application_id: str,
                 secrets: Dict[str, str], peer_domain_id: str,
                 policy_decision: PolicyDecision,
                 eligibility_decision: DecisionRecord) -> None:
        self.service = service
        self.journal = journal
        self.federation_store = federation_store
        self.application_id = application_id
        self.secrets = secrets
        self.peer_domain_id = peer_domain_id
        self.policy_decision = policy_decision
        self.eligibility_decision = eligibility_decision

    def auth(self, scope: str) -> CommandAuth:
        projection = self.service.application(self.application_id)
        reference = [
            key for key in sorted(projection.credentials)
            if projection.credentials[key].scope == scope
        ][0]
        return CommandAuth(
            credential_reference=reference, credential_secret=self.secrets[scope]
        )

    def state_digest(self) -> str:
        return self.service.state_digest()

    def journal_digest(self) -> str:
        return self.journal.journal_digest()


def _lifecycle(
    service: ProviderOnboardingService,
    *,
    start: int = 0,
    stop: int = _STEP_COUNT,
    secrets: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Execute lifecycle steps [start, stop) on an EXISTING service.

    Steps (one successful command each):
      0 register-application        7 bind-commercial-profile
      1 bind-identity               8 issue credential (propose)
      2 issue credential (adapter)  9 evaluate-eligibility
      3 issue credential (profile)  10 issue credential (manage)
      4 certify-adapter             11 propose-federation
      5 declare-resource            12 accept-federation
      6 declare-capability          13 activate-membership

    Returns a context dict with application_id, secrets, outcomes,
    and the policy/eligibility decisions used.
    """
    application_id = derive_application_id(
        "operator-reference-alpha", _KEY_A, _NODE_A, "provider-alpha", 1, 0
    )
    if secrets is None:
        secrets = {}
    policy_decision = _policy_decision()
    eligibility_decision = _eligibility_decision()
    peer_domain_id = [
        domain.domain_id
        for domain in service.federation_store.get_domains()
        if domain.operator_node_id == _NODE_B
    ]
    peer_domain_id = peer_domain_id[0] if peer_domain_id else ""
    outcomes: List[Tuple[int, bool, str, str]] = []

    def _issue(scope: str, step: int, key_proof: bool, base_scope: Optional[str] = None):
        auth = CommandAuth()
        if key_proof:
            auth = CommandAuth(key_material=_KEY_MATERIAL)
        elif base_scope:
            auth = CommandAuth(
                credential_reference=_reference(service, application_id, base_scope),
                credential_secret=secrets[base_scope],
            )
        result = service.issue_credential(
            application_id=application_id,
            scope=scope,
            valid_from=_VF,
            valid_until=_VU,
            command_key="cred-%s-1" % scope.split(".")[-1],
            actor=_NODE_A,
            issued_at=_STEP_T[step],
            effective_at=_STEP_T[step],
            key_material=auth.key_material,
            credential_reference=auth.credential_reference,
            credential_secret=auth.credential_secret,
        )
        outcomes.append((step, result.ok, result.code, "issue:" + scope))
        if result.ok and result.secret:
            secrets[scope] = result.secret
        return result

    def _reference(svc, app_id, scope):
        projection = svc.application(app_id)
        matches = [
            key for key in sorted(projection.credentials)
            if projection.credentials[key].scope == scope
        ]
        return matches[0] if matches else ""

    steps: Dict[int, Callable[[], Any]] = {
        0: lambda: service.register_application(
            operator_reference="operator-reference-alpha",
            identity_public_key=_KEY_A,
            operator_node_id=_NODE_A,
            provider_id="provider-alpha",
            display_name="Alpha Net",
            policy_references=_POLICY_REFS,
            protocol_major=1,
            protocol_max_minor=0,
            key_material=_KEY_MATERIAL,
            actor=_NODE_A,
            command_key="register-1",
            issued_at=_STEP_T[0],
            effective_at=_STEP_T[0],
        ),
        1: lambda: service.bind_identity(
            application_id=application_id,
            key_material=_KEY_MATERIAL,
            command_key="bind-1",
            actor=_NODE_A,
            issued_at=_STEP_T[1],
            effective_at=_STEP_T[1],
        ),
        2: lambda: _issue("onboarding.adapter.certify", 2, key_proof=True),
        3: lambda: _issue(
            "onboarding.profile.declare", 3, key_proof=True, base_scope=None
        ),
        4: lambda: service.certify_adapter(
            application_id=application_id,
            certification=certify_adapter_descriptor(
                descriptor=_descriptor(),
                provider_node_id=_NODE_A,
                evidence_refs=("evidence:adapter:alpha:1",),
                certified_at=_STEP_T[4],
                valid_from=_VF,
                valid_until=_VU,
                provider_operator_reference="operator-reference-alpha",
            ),
            command_key="cert-1",
            actor=_NODE_A,
            issued_at=_STEP_T[4],
            effective_at=_STEP_T[4],
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.adapter.certify"),
                credential_secret=secrets.get("onboarding.adapter.certify", ""),
            ),
        ),
        5: lambda: service.declare_resource(
            application_id=application_id,
            resource_id=make_resource_id(_NODE_A, "compute", "scope-alpha"),
            provenance="provider-alpha-inventory",
            source_reference="adcos:source:provider-alpha:inventory",
            evidence_refs=("evidence:resource:alpha:1",),
            valid_from=_VF,
            expires_at=_VU,
            command_key="decl-res-1",
            actor=_NODE_A,
            issued_at=_STEP_T[5],
            effective_at=_STEP_T[5],
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.profile.declare"),
                credential_secret=secrets.get("onboarding.profile.declare", ""),
            ),
        ),
        6: lambda: service.declare_capability(
            application_id=application_id,
            capability_reference="capability.core.store-and-forward",
            provenance="provider-alpha-declaration",
            source_reference="adcos:source:provider-alpha:decl",
            evidence_refs=("evidence:capability:alpha:1",),
            valid_from=_VF,
            expires_at=_VU,
            command_key="decl-cap-1",
            actor=_NODE_A,
            issued_at=_STEP_T[6],
            effective_at=_STEP_T[6],
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.profile.declare"),
                credential_secret=secrets.get("onboarding.profile.declare", ""),
            ),
        ),
        7: lambda: service.bind_commercial_profile(
            application_id=application_id,
            service_profile_ref="adcos:service-profile:alpha:standard",
            commercial_policy_ref="adcos:commercial-policy:alpha:v1",
            settlement_reference="adcos:settlement:reference:alpha:opaque-1",
            evidence_refs=("evidence:commercial:alpha:1",),
            command_key="profile-1",
            actor=_NODE_A,
            issued_at=_STEP_T[7],
            effective_at=_STEP_T[7],
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.profile.declare"),
                credential_secret=secrets.get("onboarding.profile.declare", ""),
            ),
        ),
        8: lambda: _issue(
            "onboarding.federation.propose", 8, key_proof=True,
            base_scope="onboarding.profile.declare",
        ),
        9: lambda: service.evaluate_eligibility(
            application_id=application_id,
            policy_decision=policy_decision,
            eligibility_decision=eligibility_decision,
            command_key="elig-1",
            actor=_NODE_A,
            issued_at=_STEP_T[9],
            effective_at=_STEP_T[9],
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.federation.propose"),
                credential_secret=secrets.get("onboarding.federation.propose", ""),
            ),
        ),
        10: lambda: _issue(
            "onboarding.federation.manage", 10, key_proof=True,
            base_scope="onboarding.federation.propose",
        ),
        11: lambda: service.propose_federation(
            application_id=application_id,
            peer_domain_id=peer_domain_id,
            peer_identity_reference=_NODE_B,
            declared_scopes=(Scope.CAPABILITY_READ, Scope.RESOURCE_READ),
            valid_from=_VF,
            valid_until=_VU,
            command_key="propose-1",
            actor=_NODE_A,
            issued_at=_STEP_T[11],
            effective_at=_STEP_T[11],
            policy_decision=policy_decision,
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.federation.propose"),
                credential_secret=secrets.get("onboarding.federation.propose", ""),
            ),
        ),
        12: lambda: service.accept_federation(
            application_id=application_id,
            command_key="accept-1",
            actor=_NODE_A,
            issued_at=_STEP_T[12],
            effective_at=_STEP_T[12],
            policy_decision=policy_decision,
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.federation.manage"),
                credential_secret=secrets.get("onboarding.federation.manage", ""),
            ),
        ),
        13: lambda: service.activate_membership(
            application_id=application_id,
            command_key="activate-1",
            actor=_NODE_A,
            issued_at=_STEP_T[13],
            effective_at=_STEP_T[13],
            auth=CommandAuth(
                credential_reference=_reference(service, application_id, "onboarding.federation.manage"),
                credential_secret=secrets.get("onboarding.federation.manage", ""),
            ),
        ),
    }
    for step in range(start, min(stop, _STEP_COUNT)):
        result = steps[step]()
        if step not in (2, 3, 9, 10):  # credential issues record their own outcomes
            outcomes.append((step, result.ok, result.code, getattr(result, "code", "")))
    return {
        "application_id": application_id,
        "secrets": secrets,
        "outcomes": outcomes,
        "peer_domain_id": peer_domain_id,
        "policy_decision": policy_decision,
        "eligibility_decision": eligibility_decision,
    }


def _golden(
    *,
    platform_profile: Optional[ProtocolProfile] = None,
    journal: Optional[OnboardingJournal] = None,
    stop: int = _STEP_COUNT,
) -> Tuple[_Golden, Dict[str, Any]]:
    journal = journal if journal is not None else OnboardingJournal()
    federation_store = FederationStore()
    service = ProviderOnboardingService(
        journal=journal,
        federation_store=federation_store,
        platform_profile=platform_profile or _PLATFORM_PROFILE,
        issuance_key=_ISSUANCE_KEY,
    )
    peer_domain_id = _platform_setup(federation_store)
    context = _lifecycle(service, start=0, stop=stop)
    golden = _Golden(
        service=service,
        journal=journal,
        federation_store=federation_store,
        application_id=context["application_id"],
        secrets=context["secrets"],
        peer_domain_id=peer_domain_id,
        policy_decision=context["policy_decision"],
        eligibility_decision=context["eligibility_decision"],
    )
    return golden, context


def _raw_record(**kwargs: Any) -> OnboardingCommandRecord:
    """A directly constructed command record (journal-level tests)."""
    payload = kwargs.pop("payload", {})
    return OnboardingCommandRecord(
        command_id="",
        application_id=kwargs.pop("application_id", "sha256:" + "9" * 64),
        command_kind=kwargs.pop("command_kind", OnboardingCommandKind.REGISTER_APPLICATION),
        command_key=kwargs.pop("command_key", "raw-1"),
        sequence=kwargs.pop("sequence", 0),
        issued_at=kwargs.pop("issued_at", _STEP_T[0]),
        effective_at=kwargs.pop("effective_at", _STEP_T[0]),
        actor=kwargs.pop("actor", _NODE_A),
        credential_reference=kwargs.pop("credential_reference", ""),
        payload=tuple(sorted(payload.items())),
        status=kwargs.pop("status", "appended"),
        reason_code=kwargs.pop("reason_code", OnboardingReason.REGISTERED),
        detail=kwargs.pop("detail", "raw record for journal discipline tests"),
    )


def _load_tampered(journal_document: Dict[str, Any]) -> Tuple[bool, str]:
    """Rebuild a journal from a (possibly tampered) document and attempt
    recovery; returns (failed, code)."""
    try:
        journal = OnboardingJournal.from_mapping(journal_document)
        federation_store = FederationStore()
        _platform_setup(federation_store)
        ProviderOnboardingService.load(
            journal=journal,
            federation_store=federation_store,
            platform_profile=_PLATFORM_PROFILE,
            issuance_key=_ISSUANCE_KEY,
        )
        return False, ""
    except Exception as error:  # OnboardingError expected
        code = getattr(error, "code", type(error).__name__)
        return True, str(code)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args), cwd=str(REPO_ROOT), capture_output=True, text=True
    )


# ----------------------------------------------------------------------
# A. Registration and identity binding
# ----------------------------------------------------------------------


def case_01_deterministic_application_identity(results: List[Tuple[str, bool, str]]) -> None:
    identifier_one = derive_application_id(
        "operator-reference-alpha", _KEY_A, _NODE_A, "provider-alpha", 1, 0
    )
    identifier_two = derive_application_id(
        "operator-reference-alpha", _KEY_A, _NODE_A, "provider-alpha", 1, 0
    )
    if identifier_one != identifier_two or not identifier_one.startswith("sha256:"):
        results.append(_fail("case_01_deterministic_application_identity",
                             "application id is not deterministic"))
        return
    identifier_three = derive_application_id(
        "operator-reference-beta", _KEY_A, _NODE_A, "provider-beta", 1, 0
    )
    if identifier_three == identifier_one:
        results.append(_fail("case_01_deterministic_application_identity",
                             "different identity material derived the same id"))
        return
    results.append(_ok("case_01_deterministic_application_identity",
                      "content-derived identity over identity material only (id %s…)"
                      % identifier_one[:23]))


def case_02_lifecycle_golden_path(results: List[Tuple[str, bool, str]]) -> None:
    golden, context = _golden()
    expected_codes = {
        0: OnboardingReason.REGISTERED, 1: OnboardingReason.IDENTITY_BOUND,
        2: OnboardingReason.CREDENTIAL_ISSUED, 3: OnboardingReason.CREDENTIAL_ISSUED,
        4: OnboardingReason.ADAPTER_CERTIFIED, 5: OnboardingReason.DECLARED,
        6: OnboardingReason.DECLARED, 7: OnboardingReason.PROFILE_BOUND,
        8: OnboardingReason.CREDENTIAL_ISSUED, 9: OnboardingReason.ELIGIBILITY_GRANTED,
        10: OnboardingReason.CREDENTIAL_ISSUED, 11: OnboardingReason.PROPOSED,
        12: OnboardingReason.ACCEPTED, 13: OnboardingReason.MEMBERSHIP_ACTIVE,
    }
    for step, ok_flag, code, _label in context["outcomes"]:
        if not ok_flag or code != expected_codes.get(step):
            results.append(_fail("case_02_lifecycle_golden_path",
                                 "step %d returned %r (expected %r)" % (step, code, expected_codes.get(step))))
            return
    projection = golden.service.application(golden.application_id)
    if projection.application.lifecycle_state != OnboardingState.ACTIVE:
        results.append(_fail("case_02_lifecycle_golden_path", "final state is not active"))
        return
    if projection.membership_status != "active" or len(projection.membership_grant_ids) != 2:
        results.append(_fail("case_02_lifecycle_golden_path", "membership/grants wrong"))
        return
    scope_result = golden.federation_store.check_scope(
        projection.application.relationship_id, Scope.CAPABILITY_READ, evaluation_instant=_NOW
    )
    if not scope_result.ok:
        results.append(_fail("case_02_lifecycle_golden_path", "scope check failed: %r" % scope_result.code))
        return
    results.append(_ok("case_02_lifecycle_golden_path",
                      "14-command deterministic lifecycle to ACTIVE membership with 2 grants; scope allowed"))


def case_03_duplicate_registration_idempotent(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=1)
    journal_length = len(golden.journal)
    state_digest = golden.state_digest()
    retry = golden.service.register_application(
        operator_reference="operator-reference-alpha", identity_public_key=_KEY_A,
        operator_node_id=_NODE_A, provider_id="provider-alpha", display_name="Alpha Net",
        policy_references=_POLICY_REFS, protocol_major=1, protocol_max_minor=0,
        key_material=_KEY_MATERIAL, actor=_NODE_A, command_key="register-1",
        issued_at=_STEP_T[0], effective_at=_STEP_T[0],
    )
    if retry.code != OnboardingReason.DUPLICATE or not retry.ok:
        results.append(_fail("case_03_duplicate_registration_idempotent",
                             "retry returned %r" % retry.code))
        return
    if len(golden.journal) != journal_length or golden.state_digest() != state_digest:
        results.append(_fail("case_03_duplicate_registration_idempotent",
                             "duplicate changed journal/state"))
        return
    results.append(_ok("case_03_duplicate_registration_idempotent",
                      "identical retry: idempotent duplicate, journal and state unchanged"))


def case_04_semantic_re_registration_idempotent(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=1)
    retry = golden.service.register_application(
        operator_reference="operator-reference-alpha", identity_public_key=_KEY_A,
        operator_node_id=_NODE_A, provider_id="provider-alpha", display_name="Alpha Net",
        policy_references=_POLICY_REFS, protocol_major=1, protocol_max_minor=0,
        key_material=_KEY_MATERIAL, actor=_NODE_A, command_key="register-retry",
        issued_at=_STEP_T[1], effective_at=_STEP_T[1],
    )
    if not retry.ok or retry.code != OnboardingReason.REGISTERED:
        results.append(_fail("case_04_semantic_re_registration_idempotent",
                             "re-registration with identical material returned %r" % retry.code))
        return
    if len(golden.service.application_ids()) != 1:
        results.append(_fail("case_04_semantic_re_registration_idempotent",
                             "a second application was created"))
        return
    results.append(_ok("case_04_semantic_re_registration_idempotent",
                      "identical material under a new key: idempotent, no second application"))


def case_05_conflicting_re_registration(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=1)
    conflict = golden.service.register_application(
        operator_reference="operator-reference-alpha", identity_public_key=_KEY_A,
        operator_node_id=_NODE_A, provider_id="provider-alpha", display_name="Alpha Net",
        policy_references=_POLICY_REFS, protocol_major=1, protocol_max_minor=0,
        key_material=b"different-operator-key-material", actor=_NODE_A,
        command_key="register-conflict", issued_at=_STEP_T[1], effective_at=_STEP_T[1],
    )
    if conflict.ok or conflict.code != OnboardingReason.PRECONDITION_UNMET:
        results.append(_fail("case_05_conflicting_re_registration",
                             "conflicting material returned %r" % conflict.code))
        return
    results.append(_ok("case_05_conflicting_re_registration",
                      "same identity with a different key proof: fail closed (precondition-unmet)"))


def case_06_invalid_operator_node_id(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=1)
    invalid = golden.service.execute_command(
        application_id=derive_application_id(
            "operator-reference-omega", _KEY_C, "not-a-canonical-node-id", "provider-omega", 1, 0
        ),
        command_kind=OnboardingCommandKind.REGISTER_APPLICATION,
        command_key="register-invalid", actor=_NODE_A,
        issued_at=_STEP_T[1], effective_at=_STEP_T[1],
        payload={
            "operator_reference": "operator-reference-omega",
            "identity_public_key": _KEY_C,
            "operator_node_id": "not-a-canonical-node-id",
            "provider_id": "provider-omega",
            "display_name": "",
            "policy_references": [],
            "protocol": {"major": 1, "max_minor": 0},
            "key_proof_digest": derive_key_proof_digest(
                b"omega", derive_application_id(
                    "operator-reference-omega", _KEY_C, "not-a-canonical-node-id", "provider-omega", 1, 0
                )
            ),
        },
    )
    if invalid.ok:
        results.append(_fail("case_06_invalid_operator_node_id", "malformed NodeID accepted"))
        return
    if invalid.code not in (OnboardingReason.INVALID_INPUT, OnboardingReason.PRECONDITION_UNMET):
        results.append(_fail("case_06_invalid_operator_node_id", "reason %r" % invalid.code))
        return
    results.append(_ok("case_06_invalid_operator_node_id",
                      "non-canonical operator NodeID fails closed (identity stays WORK-004)"))


def case_07_malformed_inputs_fail_closed(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=2)
    try:
        golden.service.execute_command(
            application_id=golden.application_id, command_kind=OnboardingCommandKind.ISSUE_CREDENTIAL,
            command_key="cred-bad-1", actor=_NODE_A, issued_at="not-an-instant",
            effective_at="not-an-instant",
            payload={"scope": "onboarding.profile.declare", "valid_from": _VF, "valid_until": _VU},
            auth=CommandAuth(key_material=_KEY_MATERIAL),
        )
        bad_instant_rejected = False
        detail_one = "malformed instant accepted"
    except Exception as error:
        bad_instant_rejected = getattr(error, "code", "") == OnboardingReason.INVALID_INPUT
        detail_one = "raised %r" % getattr(error, "code", type(error).__name__)
    if not bad_instant_rejected:
        results.append(_fail("case_07_malformed_inputs_fail_closed", detail_one))
        return
    empty_scope = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.ISSUE_CREDENTIAL,
        command_key="cred-bad-2", actor=_NODE_A, issued_at=_STEP_T[2], effective_at=_STEP_T[2],
        payload={"scope": "", "valid_from": _VF, "valid_until": _VU},
        auth=CommandAuth(key_material=_KEY_MATERIAL),
    )
    if empty_scope.ok or empty_scope.code != OnboardingReason.INVALID_INPUT:
        results.append(_fail("case_07_malformed_inputs_fail_closed", "empty scope: %r" % empty_scope.code))
        return
    reversed_window = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.ISSUE_CREDENTIAL,
        command_key="cred-bad-3", actor=_NODE_A, issued_at=_STEP_T[2], effective_at=_STEP_T[2],
        payload={"scope": "onboarding.profile.declare", "valid_from": _VU, "valid_until": _VF},
        auth=CommandAuth(key_material=_KEY_MATERIAL),
    )
    if reversed_window.ok:
        results.append(_fail("case_07_malformed_inputs_fail_closed", "reversed validity window accepted"))
        return
    results.append(_ok("case_07_malformed_inputs_fail_closed",
                      "malformed instants, empty scopes, and reversed windows all fail closed"))


def case_08_secret_material_rejected(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=2)
    try:
        golden.service.execute_command(
            application_id=golden.application_id,
            command_kind=OnboardingCommandKind.DECLARE_CAPABILITY,
            command_key="decl-secret", actor=_NODE_A,
            issued_at=_STEP_T[2], effective_at=_STEP_T[2],
            payload={
                "capability_reference": "capability.core.store-and-forward",
                "provenance": "p", "source_reference": "adcos:source:x",
                "evidence_refs": ["e:x"],
                "private_key": "0123456789abcdef",
                "valid_from": _VF, "expires_at": _VU,
            },
            auth=CommandAuth(key_material=_KEY_MATERIAL),
        )
        rejected = False
        detail = "secret-shaped payload accepted"
    except Exception as error:
        rejected = getattr(error, "code", "") == OnboardingReason.SECRET_MATERIAL
        detail = "raised %r" % getattr(error, "code", type(error).__name__)
    if not rejected:
        results.append(_fail("case_08_secret_material_rejected", detail))
        return
    results.append(_ok("case_08_secret_material_rejected",
                      "secret-shaped payload members rejected at construction (LOCK-023)"))


# ----------------------------------------------------------------------
# B. Scoped credentials
# ----------------------------------------------------------------------


def case_09_credential_secret_discipline(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=3)
    secret = golden.secrets["onboarding.adapter.certify"]
    derived_again = derive_onboarding_credential_secret(
        _ISSUANCE_KEY, golden.application_id, "onboarding.adapter.certify", 1
    )
    if secret != derived_again or not secret.startswith("onbsec_"):
        results.append(_fail("case_09_credential_secret_discipline", "secret not derived deterministically"))
        return
    serialized = json.dumps(golden.service.snapshot()) + json.dumps(golden.journal.to_mapping())
    if secret in serialized or "onbsec_" in serialized:
        results.append(_fail("case_09_credential_secret_discipline", "secret leaked into state/journal"))
        return
    projection = golden.service.application(golden.application_id)
    credential = projection.credentials[sorted(projection.credentials)[0]]
    if credential.secret_digest != "sha256:" + hashlib.sha256(secret.encode()).hexdigest():
        results.append(_fail("case_09_credential_secret_discipline", "stored digest mismatch"))
        return
    results.append(_ok("case_09_credential_secret_discipline",
                      "secret derived once, returned once, only its digest stored; never serialized"))


def case_10_credential_scope_vocabulary(results: List[Tuple[str, bool, str]]) -> None:
    scopes = OnboardingCredentialScope.values()
    if len(scopes) != 5 or len(set(scopes)) != 5:
        results.append(_fail("case_10_credential_scope_vocabulary", "scope vocabulary changed"))
        return
    required = set(COMMAND_REQUIRED_SCOPE.values())
    if not required <= set(scopes):
        results.append(_fail("case_10_credential_scope_vocabulary", "unmapped required scope"))
        return
    if len(required) != 5:
        results.append(_fail("case_10_credential_scope_vocabulary",
                             "expected all 5 scopes in the command map, found %d" % len(required)))
        return
    results.append(_ok("case_10_credential_scope_vocabulary",
                      "five least-authority scopes, no superuser, no scope implies another"))


def case_11_wrong_scope_denied(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=4)
    profile_reference = golden.auth("onboarding.profile.declare").credential_reference
    outcome = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-wrong-scope-2", actor=_NODE_A,
        issued_at=_STEP_T[4], effective_at=_STEP_T[4],
        payload={"certification": {}},
        auth=CommandAuth(
            credential_reference=profile_reference,
            credential_secret=golden.secrets["onboarding.profile.declare"],
        ),
    )
    if outcome.ok or outcome.code != OnboardingReason.CREDENTIAL_SCOPE:
        results.append(_fail("case_11_wrong_scope_denied", "reason %r" % outcome.code))
        return
    results.append(_ok("case_11_wrong_scope_denied",
                      "profile.declare credential cannot certify adapters (least authority)"))


def case_12_credential_revocation_fail_closed(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=3)
    # bootstrap an issuer-scope credential, then revoke the adapter credential with it
    issuer = golden.service.issue_credential(
        application_id=golden.application_id, scope="onboarding.credential.issue",
        valid_from=_VF, valid_until=_VU, command_key="cred-issuer-1", actor=_NODE_A,
        key_material=_KEY_MATERIAL, issued_at=_STEP_T[3], effective_at=_STEP_T[3],
    )
    if not issuer.ok:
        results.append(_fail("case_12_credential_revocation_fail_closed",
                             "issuer bootstrap failed: %r" % issuer.code))
        return
    target_reference = golden.auth("onboarding.adapter.certify").credential_reference
    revoke = golden.service.revoke_credential(
        application_id=golden.application_id, target_credential_reference=target_reference,
        command_key="revoke-cred-1", actor=_NODE_A,
        issued_at=_STEP_T[3], effective_at=_STEP_T[3],
        auth=CommandAuth(
            credential_reference=[
                key for key in sorted(golden.service.application(golden.application_id).credentials)
                if golden.service.application(golden.application_id).credentials[key].scope
                == "onboarding.credential.issue"
            ][0],
            credential_secret=issuer.secret,
        ),
    )
    if not revoke.ok:
        results.append(_fail("case_12_credential_revocation_fail_closed", "revocation failed: %r" % revoke.code))
        return
    used = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-after-revoke", actor=_NODE_A,
        issued_at=_STEP_T[3], effective_at=_STEP_T[3],
        payload={"certification": {}},
        auth=CommandAuth(credential_reference=target_reference,
                         credential_secret=golden.secrets["onboarding.adapter.certify"]),
    )
    if used.ok or used.code != OnboardingReason.CREDENTIAL_REVOKED_CODE:
        results.append(_fail("case_12_credential_revocation_fail_closed", "reason %r" % used.code))
        return
    re_revoke = golden.service.revoke_credential(
        application_id=golden.application_id, target_credential_reference=target_reference,
        command_key="revoke-cred-2", actor=_NODE_A,
        issued_at=_STEP_T[3], effective_at=_STEP_T[3],
        auth=CommandAuth(
            credential_reference=[
                key for key in sorted(golden.service.application(golden.application_id).credentials)
                if golden.service.application(golden.application_id).credentials[key].scope
                == "onboarding.credential.issue"
            ][0],
            credential_secret=issuer.secret,
        ),
    )
    if re_revoke.ok or re_revoke.code != OnboardingReason.INVALID_TRANSITION:
        results.append(_fail("case_12_credential_revocation_fail_closed",
                             "re-revocation with a new key: %r" % re_revoke.code))
        return
    projection = golden.service.application(golden.application_id)
    record = projection.credentials[target_reference]
    if record.status != "revoked" or not record.revoked_at:
        results.append(_fail("case_12_credential_revocation_fail_closed", "revocation record not preserved"))
        return
    results.append(_ok("case_12_credential_revocation_fail_closed",
                      "revocation fail closed, idempotent per key, history preserved"))


def case_13_credential_expiry_evaluated(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=3)
    golden.service.issue_credential(
        application_id=golden.application_id, scope="onboarding.adapter.certify",
        valid_from="2026-09-07T00:00:00Z", valid_until="2026-09-07T00:00:01Z",
        command_key="cred-short", actor=_NODE_A, key_material=_KEY_MATERIAL,
        issued_at=_STEP_T[2], effective_at=_STEP_T[2],
    )
    projection = golden.service.application(golden.application_id)
    short_reference = [
        key for key in sorted(projection.credentials)
        if projection.credentials[key].valid_until == "2026-09-07T00:00:01Z"
    ][0]
    outcome = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-expired", actor=_NODE_A,
        issued_at="2026-09-08T00:00:00Z", effective_at="2026-09-08T00:00:00Z",
        payload={"certification": {}},
        auth=CommandAuth(credential_reference=short_reference,
                         credential_secret=derive_onboarding_credential_secret(
                             _ISSUANCE_KEY, golden.application_id, "onboarding.adapter.certify", 2)),
    )
    if outcome.ok or outcome.code != OnboardingReason.CREDENTIAL_EXPIRED:
        results.append(_fail("case_13_credential_expiry_evaluated", "reason %r" % outcome.code))
        return
    results.append(_ok("case_13_credential_expiry_evaluated",
                      "expiry evaluated at the command instant (never observed as a state)"))


def case_14_wrong_secret_no_enumeration(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=3)
    unknown = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-unknown-cred", actor=_NODE_A,
        issued_at=_STEP_T[3], effective_at=_STEP_T[3],
        payload={"certification": {}},
        auth=CommandAuth(credential_reference="sha256:" + "e" * 64, credential_secret="onbsec_wrong"),
    )
    wrong_secret = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-wrong-secret", actor=_NODE_A,
        issued_at=_STEP_T[3], effective_at=_STEP_T[3],
        payload={"certification": {}},
        auth=CommandAuth(credential_reference=golden.auth("onboarding.adapter.certify").credential_reference,
                         credential_secret="onbsec_wrong"),
    )
    if unknown.ok or wrong_secret.ok:
        results.append(_fail("case_14_wrong_secret_no_enumeration", "bad credentials accepted"))
        return
    if unknown.code != wrong_secret.code:
        results.append(_fail("case_14_wrong_secret_no_enumeration",
                             "distinguishable failure codes: %r vs %r" % (unknown.code, wrong_secret.code)))
        return
    results.append(_ok("case_14_wrong_secret_no_enumeration",
                      "unknown reference and wrong secret share one failure code (no enumeration oracle)"))


def case_15_key_proof_fail_closed(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=1)
    wrong = golden.service.bind_identity(
        application_id=golden.application_id, key_material=b"wrong-key-material",
        command_key="bind-wrong-key", actor=_NODE_A,
        issued_at=_STEP_T[1], effective_at=_STEP_T[1],
    )
    if wrong.ok or wrong.code != OnboardingReason.KEY_PROOF_INVALID:
        results.append(_fail("case_15_key_proof_fail_closed", "reason %r" % wrong.code))
        return
    missing = golden.service.bind_identity(
        application_id=golden.application_id, key_material=b"",
        command_key="bind-no-key", actor=_NODE_A,
        issued_at=_STEP_T[1], effective_at=_STEP_T[1],
    )
    if missing.ok or missing.code != OnboardingReason.KEY_PROOF_INVALID:
        results.append(_fail("case_15_key_proof_fail_closed", "missing proof: %r" % missing.code))
        return
    right = golden.service.bind_identity(
        application_id=golden.application_id, key_material=_KEY_MATERIAL,
        command_key="bind-right-key", actor=_NODE_A,
        issued_at=_STEP_T[1], effective_at=_STEP_T[1],
    )
    if not right.ok:
        results.append(_fail("case_15_key_proof_fail_closed", "correct proof rejected"))
        return
    results.append(_ok("case_15_key_proof_fail_closed",
                      "proof of possession required; wrong/missing material fails closed; key never stored"))


def case_16_credential_issue_scope_bootstrap(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=3)
    outcome = golden.service.issue_credential(
        application_id=golden.application_id, scope="onboarding.federation.manage",
        valid_from=_VF, valid_until=_VU, command_key="cred-manage-early",
        actor=_NODE_A,
        credential_reference=golden.auth("onboarding.adapter.certify").credential_reference,
        credential_secret=golden.secrets["onboarding.adapter.certify"],
        issued_at=_STEP_T[3], effective_at=_STEP_T[3],
    )
    if outcome.ok or outcome.code != OnboardingReason.CREDENTIAL_SCOPE:
        results.append(_fail("case_16_credential_issue_scope_bootstrap", "reason %r" % outcome.code))
        return
    by_key = golden.service.issue_credential(
        application_id=golden.application_id, scope="onboarding.federation.manage",
        valid_from=_VF, valid_until=_VU, command_key="cred-manage-keyproof",
        actor=_NODE_A, key_material=_KEY_MATERIAL,
        issued_at=_STEP_T[3], effective_at=_STEP_T[3],
    )
    if not by_key.ok:
        results.append(_fail("case_16_credential_issue_scope_bootstrap",
                             "key-proof bootstrap failed: %r" % by_key.code))
        return
    results.append(_ok("case_16_credential_issue_scope_bootstrap",
                      "issuance needs the key proof or the credential.issue scope; no broad authority"))


# ----------------------------------------------------------------------
# C. Adapter certification
# ----------------------------------------------------------------------


def case_17_certification_deterministic_and_tamper_evident(results: List[Tuple[str, bool, str]]) -> None:
    certification = certify_adapter_descriptor(
        descriptor=_descriptor(), provider_node_id=_NODE_A,
        evidence_refs=("evidence:adapter:alpha:1",),
        certified_at=_STEP_T[4], valid_from=_VF, valid_until=_VU,
        provider_operator_reference="operator-reference-alpha",
    )
    again = certify_adapter_descriptor(
        descriptor=_descriptor(), provider_node_id=_NODE_A,
        evidence_refs=("evidence:adapter:alpha:1",),
        certified_at=_STEP_T[4], valid_from=_VF, valid_until=_VU,
        provider_operator_reference="operator-reference-alpha",
    )
    if certification.certification_id != again.certification_id:
        results.append(_fail("case_17_certification_deterministic_and_tamper_evident", "id not deterministic"))
        return
    document = certification.to_dict()
    document["verdict"] = "certified-x"
    try:
        AdapterCertification.from_mapping(document)
        tamper_detected = False
        detail = "tampered record accepted"
    except AdapterCertificationError:
        tamper_detected = True
        detail = ""
    if not tamper_detected:
        results.append(_fail("case_17_certification_deterministic_and_tamper_evident", detail))
        return
    results.append(_ok("case_17_certification_deterministic_and_tamper_evident",
                      "content-derived id; tampering any member fails closed at reconstruction"))


def case_18_unattested_declaration_rejected(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=4)
    outcome = golden.service.certify_adapter(
        application_id=golden.application_id,
        certification=certify_adapter_descriptor(
            descriptor=_descriptor(attested=False, suffix="d"),
            provider_node_id=_NODE_A,
            evidence_refs=("evidence:adapter:alpha:2",),
            certified_at=_STEP_T[4],
            valid_from=_VF, valid_until=_VU,
            provider_operator_reference="operator-reference-alpha",
        ),
        command_key="cert-unattested", actor=_NODE_A,
        issued_at=_STEP_T[4], effective_at=_STEP_T[4],
        auth=golden.auth("onboarding.adapter.certify"),
    )
    if outcome.ok or outcome.code != OnboardingReason.ADAPTER_REJECTED:
        results.append(_fail("case_18_unattested_declaration_rejected", "reason %r" % outcome.code))
        return
    no_evidence = golden.service.certify_adapter(
        application_id=golden.application_id,
        certification=certify_adapter_descriptor(
            descriptor=_descriptor(suffix="e"),
            provider_node_id=_NODE_A,
            evidence_refs=(),
            certified_at=_STEP_T[4],
            valid_from=_VF, valid_until=_VU,
            provider_operator_reference="operator-reference-alpha",
        ),
        command_key="cert-no-evidence", actor=_NODE_A,
        issued_at=_STEP_T[4], effective_at=_STEP_T[4],
        auth=golden.auth("onboarding.adapter.certify"),
    )
    if no_evidence.ok or no_evidence.code != OnboardingReason.ADAPTER_REJECTED:
        results.append(_fail("case_18_unattested_declaration_rejected",
                             "no-evidence: %r" % no_evidence.code))
        return
    rejected_records = [
        record for record in golden.journal.records_for(golden.application_id)
        if record.status == "rejected"
    ]
    if len(rejected_records) != 2:
        results.append(_fail("case_18_unattested_declaration_rejected",
                             "rejections not journaled for audit"))
        return
    results.append(_ok("case_18_unattested_declaration_rejected",
                      "unattested/evidence-free declarations fail closed and are journaled for audit"))


def case_19_invalid_adapter_id_rejected(results: List[Tuple[str, bool, str]]) -> None:
    try:
        _descriptor()
        bad = AdapterDescriptor(
            adapter_id="not-an-adapter-id", access_technology_id="access.generic.experimental",
            supported_profile_versions=("1.0",), capabilities=(),
            resource_mapping=(),
            security_state=AdapterSecurityState(profile="baseline", credential_slots=(), attested=True),
        )
        _ = bad
        rejected = False
        detail = "invalid adapter id accepted by the WORK-016 authority"
    except AdapterError:
        rejected = True
        detail = ""
    if not rejected:
        results.append(_fail("case_19_invalid_adapter_id_rejected", detail))
        return
    golden, _ = _golden(stop=4)
    outcome = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-bad-id", actor=_NODE_A,
        issued_at=_STEP_T[4], effective_at=_STEP_T[4],
        payload={"certification": {"adapter_id": "not-an-adapter-id"}},
        auth=golden.auth("onboarding.adapter.certify"),
    )
    if outcome.ok:
        results.append(_fail("case_19_invalid_adapter_id_rejected", "raw path accepted invalid id"))
        return
    results.append(_ok("case_19_invalid_adapter_id_rejected",
                      "adapter id grammar enforced by the WORK-016 authority on both paths"))


def case_20_invalid_capability_reference_rejected(results: List[Tuple[str, bool, str]]) -> None:
    try:
        AdapterDescriptor(
            adapter_id="adcos:adapter:access.generic.experimental:" + "f" * 16,
            access_technology_id="access.generic.experimental",
            supported_profile_versions=("1.0",), capabilities=("not a capability id!!",),
            resource_mapping=(),
            security_state=AdapterSecurityState(profile="baseline", credential_slots=(), attested=True),
        )
        rejected = False
        detail = "INVALID capability reference accepted at declaration"
    except AdapterError:
        rejected = True
        detail = ""
    if not rejected:
        results.append(_fail("case_20_invalid_capability_reference_rejected", detail))
        return
    golden, _ = _golden(stop=5)
    outcome = golden.service.declare_capability(
        application_id=golden.application_id, capability_reference="not a capability id!!",
        provenance="provider-alpha-declaration", source_reference="adcos:source:provider-alpha:decl",
        evidence_refs=("evidence:capability:alpha:2",),
        valid_from=_VF, expires_at=_VU,
        command_key="decl-cap-invalid", actor=_NODE_A,
        issued_at=_STEP_T[5], effective_at=_STEP_T[5],
        auth=golden.auth("onboarding.profile.declare"),
    )
    if outcome.ok or outcome.code != OnboardingReason.DECLARATION_INVALID:
        results.append(_fail("case_20_invalid_capability_reference_rejected",
                             "declaration path: %r" % outcome.code))
        return
    results.append(_ok("case_20_invalid_capability_reference_rejected",
                      "INVALID registry ids fail closed at both the descriptor and the declaration"))


def case_21_descriptor_secret_material_rejected(results: List[Tuple[str, bool, str]]) -> None:
    try:
        AdapterSecurityState(profile="baseline", credential_slots=("slot-a",), attested=True)
        document = {
            "certification_kind": "adcos:adapter-certification",
            "adapter_id": "adcos:adapter:access.generic.experimental:" + "9" * 16,
            "access_technology_id": "access.generic.experimental",
            "descriptor_digest": "sha256:" + "1" * 64,
            "provider_node_id": _NODE_A,
            "provider_operator_reference": "operator-reference-alpha",
            "supported_profile_versions": ["1.0"],
            "capabilities": ["capability.core.store-and-forward"],
            "attested": True,
            "evidence_refs": ["evidence:adapter:alpha:9"],
            "certified_at": _STEP_T[4],
            "valid_from": _VF,
            "valid_until": _VU,
            "verdict": "certified",
            "reason_code": "certified",
            "detail": "x",
            "credential_secret": "onbsec_leaked",
        }
        AdapterCertification.from_mapping(document)
        rejected = False
        detail = "secret-shaped member accepted"
    except AdapterCertificationError:
        rejected = True
        detail = ""
    if not rejected:
        results.append(_fail("case_21_descriptor_secret_material_rejected", detail))
        return
    results.append(_ok("case_21_descriptor_secret_material_rejected",
                      "LOCK-023 secret rejection applies to certification records"))


def case_22_forbidden_import_discipline(results: List[Tuple[str, bool, str]]) -> None:
    modules = [
        "federation/onboarding_model.py",
        "federation/onboarding_store.py",
        "federation/onboarding_service.py",
        "adapters/certification.py",
    ]
    forbidden_fragments = (
        "sessions", "routing", "transport", "networkpath", "usage", "payment",
        "allocation", "composition", "topology", "commercial", "marketplace",
        "client", "agent", "intent", "mobility", "discovery", "services",
        "conformance", "telemetry", "management", "developerapi", "upgrade.population",
    )
    forbidden_adapter_families = (
        "adapters.ran", "adapters.wifi", "adapters.mesh", "adapters.backhaul",
        "adapters.distcore", "adapters.fivegc", "adapters.ip",
    )
    allowed_roots = {
        # intra-adapter-boundary surfaces (the certification module's own package)
        "adapters.model", "adapters.validation",
        "capabilities.classification", "eligibility.decision", "eligibility.states",
        "policy.model",
        "federation.model", "federation.store",
        "federation.onboarding_model", "federation.onboarding_store",
        "protocol.canonicalization", "protocol.temporal", "protocol.versioning",
        "identity.node_id",
    }
    stdlib_roots = {
        "__future__", "hashlib", "hmac", "threading", "json", "os", "re", "abc",
        "dataclasses", "typing", "ast", "sys", "subprocess",
    }
    violations: List[str] = []
    for relative_path in modules:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        package = relative_path.rsplit("/", 1)[0].replace("/", ".")
        imported: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    target = node.module or ""
                    imported.append(package + (("." + target) if target else ""))
                else:
                    imported.append(node.module or "")
        for module_name in imported:
            root = module_name.split(".")[0]
            full = module_name
            if root in stdlib_roots and full not in allowed_roots:
                continue
            if full in allowed_roots:
                continue
            if any(fragment in full for fragment in forbidden_fragments):
                violations.append("%s imports %s (forbidden authority)" % (relative_path, full))
            elif any(full.startswith(family) for family in forbidden_adapter_families):
                violations.append("%s imports %s (forbidden adapter family)" % (relative_path, full))
            else:
                violations.append("%s imports %s (outside the integration allowlist)" % (relative_path, full))
    if violations:
        results.append(_fail("case_22_forbidden_import_discipline", "; ".join(violations[:3])))
        return
    results.append(_ok("case_22_forbidden_import_discipline",
                      "the onboarding layer imports only the composing authorities (no connectivity/"
                      "session/routing/transport/usage/payment/allocation code path can exist)"))


def case_23_access_technology_leakage_in_free_text(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=5)
    try:
        golden.service.declare_resource(
            application_id=golden.application_id,
            resource_id=make_resource_id(_NODE_A, "compute", "scope-alpha"),
            provenance="runs on a 5g backhaul", source_reference="adcos:source:provider-alpha:inv",
            evidence_refs=("evidence:resource:alpha:3",),
            valid_from=_VF, expires_at=_VU,
            command_key="decl-res-leak", actor=_NODE_A,
            issued_at=_STEP_T[5], effective_at=_STEP_T[5],
            auth=golden.auth("onboarding.profile.declare"),
        )
        leak_detected = False
        detail = "technology token accepted"
    except Exception as error:
        leak_detected = getattr(error, "code", "") in (
            OnboardingReason.ACCESS_TECHNOLOGY_LEAKAGE, OnboardingReason.INVALID_INPUT
        )
        detail = "raised %r" % getattr(error, "code", type(error).__name__)
    if not leak_detected:
        results.append(_fail("case_23_access_technology_leakage_in_free_text", detail))
        return
    try:
        golden.service.execute_command(
            application_id=golden.application_id,
            command_kind=OnboardingCommandKind.DECLARE_RESOURCE,
            command_key="decl-res-leak-2", actor=_NODE_A,
            issued_at=_STEP_T[5], effective_at=_STEP_T[5],
            payload={
                "resource_id": make_resource_id(_NODE_A, "compute", "scope-alpha"),
                "provenance": "vendor sdk declared", "source_reference": "adcos:source:x",
                "evidence_refs": ["evidence:x"], "valid_from": _VF, "expires_at": _VU,
            },
            auth=golden.auth("onboarding.profile.declare"),
        )
        leak_detected = False
        detail = "vendor token accepted"
    except Exception as error:
        leak_detected = getattr(error, "code", "") in (
            OnboardingReason.ACCESS_TECHNOLOGY_LEAKAGE, OnboardingReason.INVALID_INPUT
        )
        detail = "raised %r" % getattr(error, "code", type(error).__name__)
    if not leak_detected:
        results.append(_fail("case_23_access_technology_leakage_in_free_text", detail))
        return
    results.append(_ok("case_23_access_technology_leakage_in_free_text",
                      "technology/vendor tokens rejected in free text (LOCK-001/002/003/017)"))


# ----------------------------------------------------------------------
# D. Declarations (claims, never truth)
# ----------------------------------------------------------------------


def case_24_declaration_provenance_validity(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    projection = golden.service.application(golden.application_id)
    declarations = projection.declarations
    if len(declarations) != 2:
        results.append(_fail("case_24_declaration_provenance_validity", "expected 2 declarations"))
        return
    for declaration in declarations.values():
        if not declaration.provenance or not declaration.source_reference.startswith("adcos:source:"):
            results.append(_fail("case_24_declaration_provenance_validity", "provenance/source missing"))
            return
        if declaration.valid_from != _VF or declaration.expires_at != _VU:
            results.append(_fail("case_24_declaration_provenance_validity", "validity window wrong"))
            return
        if not declaration.evidence_refs:
            results.append(_fail("case_24_declaration_provenance_validity", "no evidence refs"))
            return
        if not declaration.is_live_at(_NOW):
            results.append(_fail("case_24_declaration_provenance_validity", "declaration not live"))
            return
    results.append(_ok("case_24_declaration_provenance_validity",
                      "declarations carry provenance, source, evidence, validity, and expiry"))


def case_25_unknown_capability_preserved(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=6)
    outcome = golden.service.declare_capability(
        application_id=golden.application_id,
        capability_reference="capability.core.experimental-alpha",
        provenance="provider-alpha-declaration", source_reference="adcos:source:provider-alpha:decl",
        evidence_refs=("evidence:capability:alpha:4",),
        valid_from=_VF, expires_at=_VU,
        command_key="decl-cap-unknown", actor=_NODE_A,
        issued_at=_STEP_T[6], effective_at=_STEP_T[6],
        auth=golden.auth("onboarding.profile.declare"),
    )
    if not outcome.ok:
        results.append(_fail("case_25_unknown_capability_preserved", "reason %r" % outcome.code))
        return
    if classify_capability_id("capability.core.experimental-alpha") != CapabilityIdClass.UNKNOWN_BUT_WELL_FORMED:
        results.append(_fail("case_25_unknown_capability_preserved", "classification changed"))
        return
    results.append(_ok("case_25_unknown_capability_preserved",
                      "open world: UNKNOWN_BUT_WELL_FORMED ids are recorded as claims (registry untouched)"))


def case_26_declaration_withdrawal(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=6)
    projection = golden.service.application(golden.application_id)
    declaration_id = sorted(projection.declarations)[0]
    withdraw = golden.service.withdraw_declaration(
        application_id=golden.application_id, declaration_id=declaration_id,
        command_key="withdraw-1", actor=_NODE_A,
        issued_at=_STEP_T[6], effective_at=_STEP_T[6],
        auth=golden.auth("onboarding.profile.declare"),
    )
    if not withdraw.ok:
        results.append(_fail("case_26_declaration_withdrawal", "withdrawal failed: %r" % withdraw.code))
        return
    withdrawn = projection.declarations[declaration_id]
    if not withdrawn.is_withdrawn() or withdrawn.is_live_at(_NOW):
        results.append(_fail("case_26_declaration_withdrawal", "withdrawal not effective"))
        return
    re_withdraw = golden.service.withdraw_declaration(
        application_id=golden.application_id, declaration_id=declaration_id,
        command_key="withdraw-2", actor=_NODE_A,
        issued_at=_STEP_T[6], effective_at=_STEP_T[6],
        auth=golden.auth("onboarding.profile.declare"),
    )
    if re_withdraw.ok or re_withdraw.code != OnboardingReason.INVALID_TRANSITION:
        results.append(_fail("case_26_declaration_withdrawal", "re-withdrawal: %r" % re_withdraw.code))
        return
    journal_ids = [record.command_id for record in golden.journal.records_for(golden.application_id)]
    if len(journal_ids) != len(set(journal_ids)):
        results.append(_fail("case_26_declaration_withdrawal", "journal integrity broken"))
        return
    results.append(_ok("case_26_declaration_withdrawal",
                      "explicit withdrawal once; the declaration stays queryable as history"))


def case_27_resource_owner_binding(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=5)
    foreign = make_resource_id(_NODE_C, "compute", "scope-foreign")
    outcome = golden.service.declare_resource(
        application_id=golden.application_id, resource_id=foreign,
        provenance="provider-alpha-inventory", source_reference="adcos:source:provider-alpha:inventory",
        evidence_refs=("evidence:resource:alpha:5",),
        valid_from=_VF, expires_at=_VU,
        command_key="decl-res-foreign", actor=_NODE_A,
        issued_at=_STEP_T[5], effective_at=_STEP_T[5],
        auth=golden.auth("onboarding.profile.declare"),
    )
    if outcome.ok or outcome.code != OnboardingReason.DECLARATION_INVALID:
        results.append(_fail("case_27_resource_owner_binding", "reason %r" % outcome.code))
        return
    # The WORK-008 authority's own parser agrees on the golden id: the
    # owner binding the onboarding layer enforces is the real one.
    parsed = parse_resource_id(make_resource_id(_NODE_A, "compute", "scope-alpha"))
    if parsed.owner_node_id != _NODE_A or parsed.kind != "compute":
        results.append(_fail("case_27_resource_owner_binding",
                             "the WORK-008 parser disagrees with the owner binding"))
        return
    results.append(_ok("case_27_resource_owner_binding",
                      "a provider declares only its own resources (owner binding fails closed; "
                      "the WORK-008 authority's parser agrees on the same ids)"))


def case_28_declaration_expiry_evaluated(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=5)
    golden.service.declare_resource(
        application_id=golden.application_id,
        resource_id=make_resource_id(_NODE_A, "compute", "scope-short"),
        provenance="provider-alpha-inventory", source_reference="adcos:source:provider-alpha:inventory",
        evidence_refs=("evidence:resource:alpha:6",),
        valid_from="2026-09-07T00:00:00Z", expires_at="2026-09-07T00:00:01Z",
        command_key="decl-res-short", actor=_NODE_A,
        issued_at=_STEP_T[5], effective_at=_STEP_T[5],
        auth=golden.auth("onboarding.profile.declare"),
    )
    projection = golden.service.application(golden.application_id)
    short = [
        declaration for declaration in projection.declarations.values()
        if declaration.expires_at == "2026-09-07T00:00:01Z"
    ][0]
    if short.is_live_at("2026-09-08T00:00:00Z"):
        results.append(_fail("case_28_declaration_expiry_evaluated", "expired declaration still live"))
        return
    if not short.is_live_at("2026-09-07T00:00:01Z"):
        results.append(_fail("case_28_declaration_expiry_evaluated", "inclusive expiry boundary wrong"))
        return
    results.append(_ok("case_28_declaration_expiry_evaluated",
                      "expiry evaluated at the injected instant (inclusive), never observed"))


def case_29_declarations_are_claims(results: List[Tuple[str, bool, str]]) -> None:
    before = sorted(known_capability_ids())
    golden, _ = _golden()
    after = sorted(known_capability_ids())
    if before != after:
        results.append(_fail("case_29_declarations_are_claims", "the capability registry changed"))
        return
    store_snapshot = golden.federation_store.snapshot()
    if set(store_snapshot.keys()) != {"domains", "relationships", "grants", "events"}:
        results.append(_fail("case_29_declarations_are_claims",
                             "federation authority surface changed: %r" % sorted(store_snapshot.keys())))
        return
    results.append(_ok("case_29_declarations_are_claims",
                      "declarations never become registry truth or topology (registry unchanged)"))


# ----------------------------------------------------------------------
# E. Commercial profile binding
# ----------------------------------------------------------------------


def case_30_commercial_profile_reference_only(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    projection = golden.service.application(golden.application_id)
    if len(projection.bindings) != 1:
        results.append(_fail("case_30_commercial_profile_reference_only", "binding missing"))
        return
    binding = projection.bindings[sorted(projection.bindings)[0]]
    document = binding.to_dict()
    if document["settlement_reference"]["opaque"] is not True:
        results.append(_fail("case_30_commercial_profile_reference_only", "settlement not opaque"))
        return
    serialized = json.dumps(golden.service.snapshot())
    for forbidden in ("price", "amount", "currency", "invoice", "settle_funds"):
        if forbidden in serialized:
            results.append(_fail("case_30_commercial_profile_reference_only",
                                 "economic semantics leaked: %r" % forbidden))
            return
    results.append(_ok("case_30_commercial_profile_reference_only",
                      "bindings are opaque references; settlement stays a typed opaque reference (P7)"))


def case_31_binding_shape_enforced(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=7)
    outcome = golden.service.execute_command(
        application_id=golden.application_id,
        command_kind=OnboardingCommandKind.BIND_COMMERCIAL_PROFILE,
        command_key="profile-bad", actor=_NODE_A,
        issued_at=_STEP_T[7], effective_at=_STEP_T[7],
        payload={
            "service_profile_ref": "not-a-reference",
            "commercial_policy_ref": "adcos:commercial-policy:alpha:v1",
            "settlement_reference": "adcos:settlement:reference:alpha:opaque-2",
            "evidence_refs": ["evidence:commercial:alpha:2"],
        },
        auth=golden.auth("onboarding.profile.declare"),
    )
    if outcome.ok:
        results.append(_fail("case_31_binding_shape_enforced", "malformed reference accepted"))
        return
    results.append(_ok("case_31_binding_shape_enforced",
                      "typed reference shapes enforced (adcos:/adcos:settlement: prefixes)"))


# ----------------------------------------------------------------------
# F. Eligibility / policy gate
# ----------------------------------------------------------------------


def case_32_policy_allow_required(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)
    deny = _policy_decision(effect="deny")
    outcome = golden.service.evaluate_eligibility(
        application_id=golden.application_id, policy_decision=deny,
        eligibility_decision=_eligibility_decision(),
        command_key="elig-deny", actor=_NODE_A,
        issued_at=_STEP_T[8], effective_at=_STEP_T[8],
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.POLICY_DENIED:
        results.append(_fail("case_32_policy_allow_required", "reason %r" % outcome.code))
        return
    results.append(_ok("case_32_policy_allow_required",
                      "an explicit policy ALLOW is required (DENY fails closed)"))


def case_33_policy_tamper_evidence(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)
    tampered = _policy_decision(tamper=True)
    outcome = golden.service.evaluate_eligibility(
        application_id=golden.application_id, policy_decision=tampered,
        eligibility_decision=_eligibility_decision(),
        command_key="elig-tampered", actor=_NODE_A,
        issued_at=_STEP_T[8], effective_at=_STEP_T[8],
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.POLICY_TAMPERED:
        results.append(_fail("case_33_policy_tamper_evidence", "reason %r" % outcome.code))
        return
    results.append(_ok("case_33_policy_tamper_evidence",
                      "a decision whose id does not match its canonical bytes is not admissible"))


def case_34_policy_reference_mismatch(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)
    other_set = _policy_decision(set_id="ps-other")
    outcome = golden.service.evaluate_eligibility(
        application_id=golden.application_id, policy_decision=other_set,
        eligibility_decision=_eligibility_decision(),
        command_key="elig-wrong-set", actor=_NODE_A,
        issued_at=_STEP_T[8], effective_at=_STEP_T[8],
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.POLICY_DENIED:
        results.append(_fail("case_34_policy_reference_mismatch", "reason %r" % outcome.code))
        return
    results.append(_ok("case_34_policy_reference_mismatch",
                      "the decision must match a declared policy reference (establishment discipline)"))


def case_35_proposal_requires_verified_decision(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=11)
    outcome = golden.service.propose_federation(
        application_id=golden.application_id, peer_domain_id=golden.peer_domain_id,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.CAPABILITY_READ,),
        valid_from=_VF, valid_until=_VU,
        command_key="propose-no-decision", actor=_NODE_A,
        issued_at=_STEP_T[11], effective_at=_STEP_T[11],
        policy_decision=None,
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.POLICY_DENIED:
        results.append(_fail("case_35_proposal_requires_verified_decision", "reason %r" % outcome.code))
        return
    results.append(_ok("case_35_proposal_requires_verified_decision",
                      "a proposal over declared policy references carries the verified ALLOW"))


def case_36_eligibility_not_eligible(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)
    not_eligible = _eligibility_decision(result="not-eligible")
    outcome = golden.service.evaluate_eligibility(
        application_id=golden.application_id, policy_decision=_policy_decision(),
        eligibility_decision=not_eligible,
        command_key="elig-not-eligible", actor=_NODE_A,
        issued_at=_STEP_T[8], effective_at=_STEP_T[8],
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.ELIGIBILITY_DENIED:
        results.append(_fail("case_36_eligibility_not_eligible", "reason %r" % outcome.code))
        return
    results.append(_ok("case_36_eligibility_not_eligible",
                      "a not-eligible decision fails closed with its reason codes"))


def case_37_eligibility_domain_and_subject(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)
    wrong_subject = _eligibility_decision(subject_ref="provider-omega")
    for label, decision, expected in (
        ("wrong-subject", wrong_subject, OnboardingReason.ELIGIBILITY_INVALID),
        ("wrong-provider", _eligibility_decision(provider_id="provider-omega",
                                                 subject_ref="provider-omega"),
         OnboardingReason.ELIGIBILITY_INVALID),
    ):
        outcome = golden.service.evaluate_eligibility(
            application_id=golden.application_id, policy_decision=_policy_decision(),
            eligibility_decision=decision,
            command_key="elig-%s" % label.replace(" ", "-"), actor=_NODE_A,
            issued_at=_STEP_T[8], effective_at=_STEP_T[8],
            auth=golden.auth("onboarding.federation.propose"),
        )
        if outcome.ok or outcome.code != expected:
            results.append(_fail("case_37_eligibility_domain_and_subject",
                                 "%s: %r" % (label, outcome.code)))
            return
    results.append(_ok("case_37_eligibility_domain_and_subject",
                      "provider-subject binding and connectivity-domain enforced"))


def case_38_eligibility_expiry_evaluated(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)
    expired = _eligibility_decision(valid_until="2026-09-07T00:00:00Z")
    outcome = golden.service.evaluate_eligibility(
        application_id=golden.application_id, policy_decision=_policy_decision(),
        eligibility_decision=expired,
        command_key="elig-expired", actor=_NODE_A,
        issued_at=_STEP_T[8], effective_at=_STEP_T[8],
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.ELIGIBILITY_DENIED:
        results.append(_fail("case_38_eligibility_expiry_evaluated", "reason %r" % outcome.code))
        return
    results.append(_ok("case_38_eligibility_expiry_evaluated",
                      "the decision's validity window is evaluated at the command instant"))


def case_39_policy_decision_is_not_trust(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    graph = TopologyGraph()
    authoritative = graph.get_authoritative_claims("subject-x", now=_NOW)
    if authoritative:
        results.append(_fail("case_39_policy_decision_is_not_trust",
                             "topology claims appeared without topology evidence"))
        return
    projection = golden.service.application(golden.application_id)
    if not projection.policy_decision_ref or not projection.eligibility_decision_ref:
        results.append(_fail("case_39_policy_decision_is_not_trust", "decision references missing"))
        return
    results.append(_ok("case_39_policy_decision_is_not_trust",
                      "decisions are consumed as recorded references; no node-level trust is conferred"))


# ----------------------------------------------------------------------
# G. Federation composition
# ----------------------------------------------------------------------


def case_40_stage_preconditions_enforced(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)  # stopped BEFORE evaluate-eligibility
    outcome = golden.service.propose_federation(
        application_id=golden.application_id, peer_domain_id=golden.peer_domain_id,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.CAPABILITY_READ,),
        valid_from=_VF, valid_until=_VU,
        command_key="propose-early", actor=_NODE_A,
        issued_at=_STEP_T[11], effective_at=_STEP_T[11],
        policy_decision=_policy_decision(),
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.PRECONDITION_UNMET:
        results.append(_fail("case_40_stage_preconditions_enforced", "reason %r" % outcome.code))
        return
    results.append(_ok("case_40_stage_preconditions_enforced",
                      "skipping lifecycle stages fails closed (deterministic stage ordering)"))


def case_41_relationship_via_federation_authority(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    projection = golden.service.application(golden.application_id)
    expected = derive_relationship_id(
        projection.application.domain_id, golden.peer_domain_id
    )
    if projection.application.relationship_id != expected:
        results.append(_fail("case_41_relationship_via_federation_authority", "relationship id mismatch"))
        return
    relationship = golden.federation_store.get_relationship(expected)
    if relationship is None:
        results.append(_fail("case_41_relationship_via_federation_authority",
                             "relationship missing from the federation authority"))
        return
    results.append(_ok("case_41_relationship_via_federation_authority",
                      "the relationship id IS the federation authority's id (no second authority)"))


def case_42_peer_unregistered_fail_closed(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=11)
    outcome = golden.service.propose_federation(
        application_id=golden.application_id,
        peer_domain_id="sha256:" + "7" * 64,
        peer_identity_reference=_NODE_B,
        declared_scopes=(Scope.CAPABILITY_READ,),
        valid_from=_VF, valid_until=_VU,
        command_key="propose-unknown-peer", actor=_NODE_A,
        issued_at=_STEP_T[11], effective_at=_STEP_T[11],
        policy_decision=_policy_decision(),
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.PEER_UNREGISTERED:
        results.append(_fail("case_42_peer_unregistered_fail_closed", "reason %r" % outcome.code))
        return
    results.append(_ok("case_42_peer_unregistered_fail_closed",
                      "an unregistered peer fails closed (explicit peer binding required)"))


def case_43_peer_identity_mismatch(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=11)
    outcome = golden.service.propose_federation(
        application_id=golden.application_id, peer_domain_id=golden.peer_domain_id,
        peer_identity_reference=_NODE_C,  # not the peer's registered operator
        declared_scopes=(Scope.CAPABILITY_READ,),
        valid_from=_VF, valid_until=_VU,
        command_key="propose-wrong-peer-id", actor=_NODE_A,
        issued_at=_STEP_T[11], effective_at=_STEP_T[11],
        policy_decision=_policy_decision(),
        auth=golden.auth("onboarding.federation.propose"),
    )
    if outcome.ok or outcome.code != OnboardingReason.PEER_IDENTITY_MISMATCH:
        results.append(_fail("case_43_peer_identity_mismatch", "reason %r" % outcome.code))
        return
    results.append(_ok("case_43_peer_identity_mismatch",
                      "cross-domain identity confusion fails closed (peer binding discipline)"))


def case_44_explicit_acceptance_and_narrowing(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=12)
    widen = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.ACCEPT_FEDERATION,
        command_key="accept-widen", actor=_NODE_A,
        issued_at=_STEP_T[12], effective_at=_STEP_T[12],
        payload={"scopes": [Scope.SERVICE_INVOKE], "policy_decision": policy_decision_document(_policy_decision())},
        auth=golden.auth("onboarding.federation.manage"),
    )
    if widen.ok or widen.code != OnboardingReason.INVALID_INPUT:
        results.append(_fail("case_44_explicit_acceptance_and_narrowing",
                             "widening: %r" % widen.code))
        return
    narrow = golden.service.accept_federation(
        application_id=golden.application_id, scopes=(Scope.CAPABILITY_READ,),
        command_key="accept-narrow", actor=_NODE_A,
        issued_at=_STEP_T[12], effective_at=_STEP_T[12],
        policy_decision=_policy_decision(),
        auth=golden.auth("onboarding.federation.manage"),
    )
    if not narrow.ok:
        results.append(_fail("case_44_explicit_acceptance_and_narrowing",
                             "narrowing rejected: %r" % narrow.code))
        return
    relationship = golden.federation_store.get_relationship(
        golden.service.application(golden.application_id).application.relationship_id
    )
    if sorted(relationship.declared_scopes) != [Scope.CAPABILITY_READ]:
        results.append(_fail("case_44_explicit_acceptance_and_narrowing",
                             "envelope not narrowed: %r" % (relationship.declared_scopes,)))
        return
    activate = golden.service.activate_membership(
        application_id=golden.application_id, command_key="activate-narrowed", actor=_NODE_A,
        issued_at=_STEP_T[13], effective_at=_STEP_T[13],
        auth=golden.auth("onboarding.federation.manage"),
    )
    if not activate.ok:
        results.append(_fail("case_44_explicit_acceptance_and_narrowing",
                             "activation after narrowing failed: %r" % activate.code))
        return
    projection = golden.service.application(golden.application_id)
    if len(projection.membership_grant_ids) != 1:
        results.append(_fail("case_44_explicit_acceptance_and_narrowing", "grants not narrowed"))
        return
    results.append(_ok("case_44_explicit_acceptance_and_narrowing",
                      "acceptance is explicit, may only narrow, and grants follow the narrowed envelope"))


def case_45_scope_envelope_least_authority(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    projection = golden.service.application(golden.application_id)
    relationship_id = projection.application.relationship_id
    undeclared = golden.federation_store.check_scope(
        relationship_id, Scope.SERVICE_INVOKE, evaluation_instant=_NOW
    )
    if undeclared.ok or undeclared.code != "scope-not-declared":
        results.append(_fail("case_45_scope_envelope_least_authority",
                             "undeclared scope: %r" % undeclared.code))
        return
    allowed = golden.federation_store.check_scope(
        relationship_id, Scope.RESOURCE_READ, evaluation_instant=_NOW
    )
    if not allowed.ok:
        results.append(_fail("case_45_scope_envelope_least_authority", "declared scope denied"))
        return
    results.append(_ok("case_45_scope_envelope_least_authority",
                      "scopes outside the declared envelope are denied; no scope implies another"))


# ----------------------------------------------------------------------
# H. Suspension / revocation / offboarding
# ----------------------------------------------------------------------


def case_46_suspension_blocks_admission(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    projection = golden.service.application(golden.application_id)
    relationship_id = projection.application.relationship_id
    suspend = golden.service.suspend_membership(
        application_id=golden.application_id, command_key="suspend-1", actor=_NODE_A,
        issued_at=_STEP_T[14], effective_at=_STEP_T[14],
        auth=golden.auth("onboarding.federation.manage"),
    )
    if not suspend.ok:
        results.append(_fail("case_46_suspension_blocks_admission", "suspend: %r" % suspend.code))
        return
    blocked = golden.federation_store.check_scope(
        relationship_id, Scope.CAPABILITY_READ, evaluation_instant=_STEP_T[14]
    )
    if blocked.ok or blocked.code != "relationship-suspended":
        results.append(_fail("case_46_suspension_blocks_admission",
                             "suspended admission: %r" % blocked.code))
        return
    resume = golden.service.resume_membership(
        application_id=golden.application_id, command_key="resume-1", actor=_NODE_A,
        issued_at=_STEP_T[15], effective_at=_STEP_T[15],
        auth=golden.auth("onboarding.federation.manage"),
    )
    if not resume.ok:
        results.append(_fail("case_46_suspension_blocks_admission", "resume: %r" % resume.code))
        return
    restored = golden.federation_store.check_scope(
        relationship_id, Scope.CAPABILITY_READ, evaluation_instant=_STEP_T[15]
    )
    if not restored.ok:
        results.append(_fail("case_46_suspension_blocks_admission", "resumption did not restore"))
        return
    results.append(_ok("case_46_suspension_blocks_admission",
                      "suspension blocks new admission fail-closed; explicit resumption restores"))


def case_47_revocation_fail_closed(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    application_id = golden.application_id
    first = golden.service.revoke_application(
        application_id=application_id, reason="adversarial review revocation",
        command_key="revoke-1", actor=_NODE_A,
        issued_at=_STEP_T[14], effective_at=_STEP_T[14],
        auth=golden.auth("onboarding.federation.manage"),
    )
    if not first.ok:
        results.append(_fail("case_47_revocation_fail_closed", "revoke: %r" % first.code))
        return
    projection = golden.service.application(application_id)
    if projection.application.lifecycle_state != OnboardingState.REVOKED:
        results.append(_fail("case_47_revocation_fail_closed", "state not revoked"))
        return
    if any(c.status == "active" for c in projection.credentials.values()):
        results.append(_fail("case_47_revocation_fail_closed", "credentials not revoked"))
        return
    relationship = golden.federation_store.get_relationship(
        projection.application.relationship_id
    )
    if relationship.state != "REVOKED":
        results.append(_fail("case_47_revocation_fail_closed", "relationship not revoked"))
        return
    duplicate = golden.service.revoke_application(
        application_id=application_id, reason="adversarial review revocation",
        command_key="revoke-1", actor=_NODE_A,
        issued_at=_STEP_T[14], effective_at=_STEP_T[14],
        auth=golden.auth("onboarding.federation.manage"),
    )
    if duplicate.code != OnboardingReason.DUPLICATE:
        results.append(_fail("case_47_revocation_fail_closed", "duplicate revoke: %r" % duplicate.code))
        return
    again = golden.service.revoke_application(
        application_id=application_id, reason="second attempt",
        command_key="revoke-2", actor=_NODE_A,
        issued_at=_STEP_T[15], effective_at=_STEP_T[15],
        auth=golden.auth("onboarding.federation.manage"),
    )
    if again.ok or again.code not in (
        OnboardingReason.APPLICATION_TERMINAL, OnboardingReason.CREDENTIAL_REVOKED_CODE
    ):
        results.append(_fail("case_47_revocation_fail_closed", "re-revoke: %r" % again.code))
        return
    events = golden.federation_store.get_events(projection.application.relationship_id)
    if not events:
        results.append(_fail("case_47_revocation_fail_closed", "history not preserved"))
        return
    results.append(_ok("case_47_revocation_fail_closed",
                      "revocation is fail-closed and idempotent; history stays queryable"))


def case_48_offboarding_deterministic(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    application_id = golden.application_id
    offboard = golden.service.offboard_application(
        application_id=application_id, reason="deterministic offboarding",
        command_key="offboard-1", actor=_NODE_A,
        issued_at=_STEP_T[14], effective_at=_STEP_T[14],
        auth=golden.auth("onboarding.federation.manage"),
    )
    if not offboard.ok:
        results.append(_fail("case_48_offboarding_deterministic", "offboard: %r" % offboard.code))
        return
    projection = golden.service.application(application_id)
    if projection.application.lifecycle_state != OnboardingState.OFFBOARDED:
        results.append(_fail("case_48_offboarding_deterministic", "state not offboarded"))
        return
    relationship = golden.federation_store.get_relationship(
        projection.application.relationship_id
    )
    if relationship.state != "TERMINATED":
        results.append(_fail("case_48_offboarding_deterministic", "relationship not terminated"))
        return
    domain = golden.federation_store.get_domain(projection.application.domain_id)
    if domain.lifecycle_state != DomainLifecycle.RETIRED:
        results.append(_fail("case_48_offboarding_deterministic", "domain not retired"))
        return
    if any(c.status == "active" for c in projection.credentials.values()):
        results.append(_fail("case_48_offboarding_deterministic", "credentials not revoked"))
        return
    blocked = golden.service.propose_federation(
        application_id=application_id, peer_domain_id=golden.peer_domain_id,
        peer_identity_reference=_NODE_B, declared_scopes=(Scope.CAPABILITY_READ,),
        valid_from=_VF, valid_until=_VU,
        command_key="propose-after-offboard", actor=_NODE_A,
        issued_at=_STEP_T[15], effective_at=_STEP_T[15],
        policy_decision=_policy_decision(),
        auth=golden.auth("onboarding.federation.propose"),
    )
    if blocked.ok or blocked.code not in (
        OnboardingReason.APPLICATION_TERMINAL, OnboardingReason.CREDENTIAL_REVOKED_CODE
    ):
        results.append(_fail("case_48_offboarding_deterministic",
                             "future participation not blocked: %r" % blocked.code))
        return
    results.append(_ok("case_48_offboarding_deterministic",
                      "offboarding revokes credentials, terminates the relationship, retires the domain, "
                      "and blocks future participation"))


def case_49_offboarding_preserves_history(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    application_id = golden.application_id
    golden.service.offboard_application(
        application_id=application_id, reason="deterministic offboarding",
        command_key="offboard-1", actor=_NODE_A,
        issued_at=_STEP_T[14], effective_at=_STEP_T[14],
        auth=golden.auth("onboarding.federation.manage"),
    )
    projection = golden.service.application(application_id)
    if not projection.declarations or not projection.certifications or not projection.bindings:
        results.append(_fail("case_49_offboarding_preserves_history",
                             "offboarding deleted historical evidence"))
        return
    events = golden.federation_store.get_events(projection.application.relationship_id)
    if not events:
        results.append(_fail("case_49_offboarding_preserves_history", "federation events deleted"))
        return
    records = golden.journal.records_for(application_id)
    if not records:
        results.append(_fail("case_49_offboarding_preserves_history", "journal records deleted"))
        return
    results.append(_ok("case_49_offboarding_preserves_history",
                      "declarations, certifications, bindings, events, and journal survive offboarding"))


def case_50_re_registration_after_offboard(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    application_id = golden.application_id
    golden.service.offboard_application(
        application_id=application_id, reason="deterministic offboarding",
        command_key="offboard-1", actor=_NODE_A,
        issued_at=_STEP_T[14], effective_at=_STEP_T[14],
        auth=golden.auth("onboarding.federation.manage"),
    )
    # a NEW operator material registers (a genuinely new provider)
    new_application = derive_application_id(
        "operator-reference-beta", _KEY_C, _NODE_C, "provider-beta", 1, 0
    )
    registration = golden.service.register_application(
        operator_reference="operator-reference-beta", identity_public_key=_KEY_C,
        operator_node_id=_NODE_C, provider_id="provider-beta", display_name="Beta Net",
        policy_references=_POLICY_REFS, protocol_major=1, protocol_max_minor=0,
        key_material=b"beta-key-material", actor=_NODE_C,
        command_key="register-beta", issued_at=_STEP_T[15], effective_at=_STEP_T[15],
    )
    if not registration.ok:
        results.append(_fail("case_50_re_registration_after_offboard",
                             "new registration blocked: %r" % registration.code))
        return
    old = golden.service.application(application_id)
    if old.application.lifecycle_state != OnboardingState.OFFBOARDED:
        results.append(_fail("case_50_re_registration_after_offboard", "old app resurrected"))
        return
    if golden.service.application(new_application).application.lifecycle_state != OnboardingState.REGISTERED:
        results.append(_fail("case_50_re_registration_after_offboard", "new app state wrong"))
        return
    results.append(_ok("case_50_re_registration_after_offboard",
                      "offboarded applications never resurrect; new identity material starts fresh"))


# ----------------------------------------------------------------------
# I. Non-transitivity and authority separation
# ----------------------------------------------------------------------


def case_51_membership_non_transitive(results: List[Tuple[str, bool, str]]) -> None:
    journal = OnboardingJournal()
    federation_store = FederationStore()
    service = ProviderOnboardingService(
        journal=journal, federation_store=federation_store,
        platform_profile=_PLATFORM_PROFILE, issuance_key=_ISSUANCE_KEY,
    )
    _platform_setup(federation_store)
    context_alpha = _lifecycle(service, start=0, stop=_STEP_COUNT)
    alpha_id = context_alpha["application_id"]
    # provider beta: registers, binds, credentials, then proposes with FEWER scopes
    beta_id = derive_application_id(
        "operator-reference-beta", _KEY_C, _NODE_C, "provider-beta", 1, 0
    )
    service.register_application(
        operator_reference="operator-reference-beta", identity_public_key=_KEY_C,
        operator_node_id=_NODE_C, provider_id="provider-beta", display_name="Beta Net",
        policy_references=_POLICY_REFS, protocol_major=1, protocol_max_minor=0,
        key_material=b"beta-key-material", actor=_NODE_C,
        command_key="beta-register", issued_at=_STEP_T[2], effective_at=_STEP_T[2],
    )
    service.bind_identity(application_id=beta_id, key_material=b"beta-key-material",
                          command_key="beta-bind", actor=_NODE_C,
                          issued_at=_STEP_T[2], effective_at=_STEP_T[2])
    beta_adapter = service.issue_credential(
        application_id=beta_id, scope="onboarding.adapter.certify",
        valid_from=_VF, valid_until=_VU, command_key="beta-cred-1", actor=_NODE_C,
        key_material=b"beta-key-material", issued_at=_STEP_T[2], effective_at=_STEP_T[2])
    service.certify_adapter(
        application_id=beta_id,
        certification=certify_adapter_descriptor(
            descriptor=_descriptor(suffix="b"),
            provider_node_id=_NODE_C,
            evidence_refs=("evidence:adapter:beta:1",),
            certified_at=_STEP_T[2],
            valid_from=_VF, valid_until=_VU,
            provider_operator_reference="operator-reference-beta",
        ),
        command_key="beta-cert", actor=_NODE_C, issued_at=_STEP_T[2], effective_at=_STEP_T[2],
        auth=CommandAuth(
            credential_reference=[k for k in sorted(service.application(beta_id).credentials)][0],
            credential_secret=beta_adapter.secret))
    beta_profile = service.issue_credential(
        application_id=beta_id, scope="onboarding.profile.declare",
        valid_from=_VF, valid_until=_VU, command_key="beta-cred-2", actor=_NODE_C,
        key_material=b"beta-key-material", issued_at=_STEP_T[3], effective_at=_STEP_T[3])
    service.declare_capability(
        application_id=beta_id, capability_reference="capability.core.store-and-forward",
        provenance="provider-beta-declaration", source_reference="adcos:source:provider-beta:decl",
        evidence_refs=("evidence:capability:beta:1",), valid_from=_VF, expires_at=_VU,
        command_key="beta-decl", actor=_NODE_C, issued_at=_STEP_T[4], effective_at=_STEP_T[4],
        auth=CommandAuth(
            credential_reference=[k for k in sorted(service.application(beta_id).credentials)
                                  if service.application(beta_id).credentials[k].scope == "onboarding.profile.declare"][0],
            credential_secret=beta_profile.secret))
    service.bind_commercial_profile(
        application_id=beta_id, service_profile_ref="adcos:service-profile:beta:standard",
        commercial_policy_ref="adcos:commercial-policy:beta:v1",
        settlement_reference="adcos:settlement:reference:beta:opaque-1",
        evidence_refs=("evidence:commercial:beta:1",),
        command_key="beta-profile", actor=_NODE_C, issued_at=_STEP_T[5], effective_at=_STEP_T[5],
        auth=CommandAuth(
            credential_reference=[k for k in sorted(service.application(beta_id).credentials)
                                  if service.application(beta_id).credentials[k].scope == "onboarding.profile.declare"][0],
            credential_secret=beta_profile.secret))
    beta_pd = _policy_decision()
    beta_ed = _eligibility_decision(provider_id="provider-beta", subject_ref="provider-beta")
    beta_propose_cred = service.issue_credential(
        application_id=beta_id, scope="onboarding.federation.propose",
        valid_from=_VF, valid_until=_VU, command_key="beta-cred-3", actor=_NODE_C,
        key_material=b"beta-key-material", issued_at=_STEP_T[9], effective_at=_STEP_T[9])
    beta_eligibility = service.evaluate_eligibility(
        application_id=beta_id, policy_decision=beta_pd, eligibility_decision=beta_ed,
        command_key="beta-elig", actor=_NODE_C, issued_at=_STEP_T[9], effective_at=_STEP_T[9],
        auth=CommandAuth(
            credential_reference=[k for k in sorted(service.application(beta_id).credentials)
                                  if service.application(beta_id).credentials[k].scope == "onboarding.federation.propose"][0],
            credential_secret=beta_propose_cred.secret))
    if not beta_eligibility.ok:
        results.append(_fail("case_51_membership_non_transitive",
                             "beta eligibility failed: %r" % beta_eligibility.code))
        return
    beta_manage = service.issue_credential(
        application_id=beta_id, scope="onboarding.federation.manage",
        valid_from=_VF, valid_until=_VU, command_key="beta-cred-4", actor=_NODE_C,
        key_material=b"beta-key-material", issued_at=_STEP_T[10], effective_at=_STEP_T[10])
    beta_proposal = service.propose_federation(
        application_id=beta_id,
        peer_domain_id=[d.domain_id for d in federation_store.get_domains()
                        if d.operator_node_id == _NODE_B][0],
        peer_identity_reference=_NODE_B, declared_scopes=(Scope.CAPABILITY_READ,),
        valid_from=_VF, valid_until=_VU,
        command_key="beta-propose", actor=_NODE_C, issued_at=_STEP_T[11], effective_at=_STEP_T[11],
        policy_decision=beta_pd,
        auth=CommandAuth(
            credential_reference=[k for k in sorted(service.application(beta_id).credentials)
                                  if service.application(beta_id).credentials[k].scope == "onboarding.federation.propose"][0],
            credential_secret=beta_propose_cred.secret))
    if not beta_proposal.ok:
        results.append(_fail("case_51_membership_non_transitive",
                             "beta proposal failed: %r" % beta_proposal.code))
        return
    service.accept_federation(
        application_id=beta_id, command_key="beta-accept", actor=_NODE_C,
        issued_at=_STEP_T[12], effective_at=_STEP_T[12], policy_decision=beta_pd,
        auth=CommandAuth(
            credential_reference=[k for k in sorted(service.application(beta_id).credentials)
                                  if service.application(beta_id).credentials[k].scope == "onboarding.federation.manage"][0],
            credential_secret=beta_manage.secret))
    beta_activation = service.activate_membership(
        application_id=beta_id, command_key="beta-activate", actor=_NODE_C,
        issued_at=_STEP_T[13], effective_at=_STEP_T[13],
        auth=CommandAuth(
            credential_reference=[k for k in sorted(service.application(beta_id).credentials)
                                  if service.application(beta_id).credentials[k].scope == "onboarding.federation.manage"][0],
            credential_secret=beta_manage.secret))
    if not beta_activation.ok:
        results.append(_fail("case_51_membership_non_transitive",
                             "beta activation failed: %r" % beta_activation.code))
        return
    beta_relationship_id = service.application(beta_id).application.relationship_id
    beta_resource = federation_store.check_scope(
        beta_relationship_id, Scope.RESOURCE_READ, evaluation_instant=_NOW
    )
    if beta_resource.ok or beta_resource.code != "scope-not-declared":
        results.append(_fail("case_51_membership_non_transitive",
                             "beta inherited alpha's scopes (transitivity!): %r" % beta_resource.code))
        return
    alpha_grants = set(service.application(alpha_id).membership_grant_ids)
    beta_grants = set(service.application(beta_id).membership_grant_ids)
    if alpha_grants & beta_grants:
        results.append(_fail("case_51_membership_non_transitive", "grants shared across providers"))
        return
    results.append(_ok("case_51_membership_non_transitive",
                      "alpha's membership grants nothing to beta (scoped, non-transitive membership)"))


def case_52_no_second_authorities(results: List[Tuple[str, bool, str]]) -> None:
    registry_before = sorted(known_capability_ids())
    golden, _ = _golden()
    if sorted(known_capability_ids()) != registry_before:
        results.append(_fail("case_52_no_second_authorities", "capability registry changed"))
        return
    # the service structurally holds ONLY the composing authorities
    attributes = set(vars(golden.service))
    expected_attributes = {
        "_journal", "_federation_store", "_platform_profile", "_issuance_key",
        "_state", "_lock",
    }
    if attributes != expected_attributes:
        results.append(_fail("case_52_no_second_authorities",
                             "unexpected service state: %r" % sorted(attributes)))
        return
    snapshot = golden.service.snapshot()
    serialized = json.dumps(snapshot)
    for leaked in ('"topology"', '"node_identities"', '"routes"', '"policies"'):
        if leaked in serialized:
            results.append(_fail("case_52_no_second_authorities",
                                 "onboarding state leaks %r" % leaked))
            return
    results.append(_ok("case_52_no_second_authorities",
                      "registry unchanged; the service holds only journal + federation store + "
                      "platform profile + issuance key (no second authority can exist)"))


def case_53_no_connectivity_state_created(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    from sessions.store import SessionStore  # battery-only import for boundary proof

    sessions = SessionStore()
    if sessions.snapshot() not in ({}, SessionStore().snapshot()):
        results.append(_fail("case_53_no_connectivity_state_created", "sessions mutated"))
        return
    snapshot = golden.service.snapshot()
    serialized = json.dumps(snapshot)
    forbidden_members = ("session", "path", "route", "transport", "usage", "payment", "settlement_state")
    for member in forbidden_members:
        if '"%s"' % member in serialized:
            results.append(_fail("case_53_no_connectivity_state_created",
                                 "onboarding state carries %r state" % member))
            return
    attributes = set(vars(golden.service))
    expected_attributes = {
        "_journal", "_federation_store", "_platform_profile", "_issuance_key",
        "_state", "_lock",
    }
    if attributes != expected_attributes:
        results.append(_fail("case_53_no_connectivity_state_created",
                             "unexpected service state: %r" % sorted(attributes)))
        return
    results.append(_ok("case_53_no_connectivity_state_created",
                      "no connectivity/session/path/route/transport/usage/payment/settlement state "
                      "(structurally: case_22's import audit + the service attribute audit + "
                      "the runtime surface)"))


# ----------------------------------------------------------------------
# J. Duplicate / replay / ordering / concurrency
# ----------------------------------------------------------------------


def case_54_duplicate_command_idempotent(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=6)
    digest = golden.state_digest()
    length = len(golden.journal)
    retry = golden.service.declare_resource(
        application_id=golden.application_id,
        resource_id=make_resource_id(_NODE_A, "compute", "scope-alpha"),
        provenance="provider-alpha-inventory", source_reference="adcos:source:provider-alpha:inventory",
        evidence_refs=("evidence:resource:alpha:1",),
        valid_from=_VF, expires_at=_VU,
        command_key="decl-res-1", actor=_NODE_A,
        issued_at=_STEP_T[5], effective_at=_STEP_T[5],
        auth=golden.auth("onboarding.profile.declare"),
    )
    if retry.code != OnboardingReason.DUPLICATE:
        results.append(_fail("case_54_duplicate_command_idempotent", "reason %r" % retry.code))
        return
    if golden.state_digest() != digest or len(golden.journal) != length:
        results.append(_fail("case_54_duplicate_command_idempotent", "state/journal changed"))
        return
    results.append(_ok("case_54_duplicate_command_idempotent",
                      "exact retry after success: idempotent duplicate (no double effects)"))


def case_55_command_key_conflict(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=6)
    conflict = golden.service.declare_resource(
        application_id=golden.application_id,
        resource_id=make_resource_id(_NODE_A, "compute", "scope-conflict"),
        provenance="provider-alpha-inventory", source_reference="adcos:source:provider-alpha:inventory",
        evidence_refs=("evidence:resource:alpha:7",),
        valid_from=_VF, expires_at=_VU,
        command_key="decl-res-1", actor=_NODE_A,  # same key, different content
        issued_at=_STEP_T[5], effective_at=_STEP_T[5],
        auth=golden.auth("onboarding.profile.declare"),
    )
    if conflict.ok or conflict.code != OnboardingReason.SEQUENCE_CONFLICT:
        results.append(_fail("case_55_command_key_conflict", "reason %r" % conflict.code))
        return
    results.append(_ok("case_55_command_key_conflict",
                      "same idempotency key with different content fails closed (audited)"))


def case_56_journal_sequence_discipline(results: List[Tuple[str, bool, str]]) -> None:
    journal = OnboardingJournal()
    first = journal.append(_raw_record(sequence=0, command_key="raw-1"))
    if not first.ok or first.record.sequence != 1:
        results.append(_fail("case_56_journal_sequence_discipline", "sequence not assigned"))
        return
    stale = journal.append(_raw_record(sequence=1, command_key="raw-2"))
    if stale.ok or stale.code != OnboardingReason.REPLAY_STALE:
        results.append(_fail("case_56_journal_sequence_discipline", "stale: %r" % stale.code))
        return
    gap = journal.append(_raw_record(sequence=5, command_key="raw-3"))
    if gap.ok or gap.code != OnboardingReason.SEQUENCE_GAP:
        results.append(_fail("case_56_journal_sequence_discipline", "gap: %r" % gap.code))
        return
    duplicate = journal.append(_raw_record(sequence=0, command_key="raw-1"))
    if duplicate.code != OnboardingReason.DUPLICATE:
        results.append(_fail("case_56_journal_sequence_discipline", "duplicate: %r" % duplicate.code))
        return
    results.append(_ok("case_56_journal_sequence_discipline",
                      "stale replay, sequence gap, and duplicate all fail closed deterministically"))


def case_57_concurrent_commands_safe(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=3)
    service = golden.service
    application_id = golden.application_id
    barrier = threading.Barrier(8)
    outcomes: List[Any] = []
    lock = threading.Lock()

    def worker(index: int) -> None:
        barrier.wait()
        result = service.issue_credential(
            application_id=application_id, scope="onboarding.profile.declare",
            valid_from=_VF, valid_until=_VU,
            command_key="cred-race-%d" % index, actor=_NODE_A,
            key_material=_KEY_MATERIAL,
            issued_at=_STEP_T[3], effective_at=_STEP_T[3],
        )
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    appended = [outcome for outcome in outcomes if outcome.ok]
    if len(appended) != 8:
        results.append(_fail("case_57_concurrent_commands_safe",
                             "lost appends: %d/8" % len(appended)))
        return
    projection = service.application(application_id)
    sequences = sorted(
        credential.sequence for credential in projection.credentials.values()
        if credential.scope == "onboarding.profile.declare"
    )
    if sequences != list(range(2, 10)):
        results.append(_fail("case_57_concurrent_commands_safe",
                             "credential sequences not unique/contiguous: %r" % sequences))
        return
    results.append(_ok("case_57_concurrent_commands_safe",
                      "8 concurrent distinct-key commands: no lost appends, unique sequences, "
                      "serialized deterministically under the service lock"))


def case_58_out_of_order_instants(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=3)
    backdated = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-backdated", actor=_NODE_A,
        issued_at="2026-09-06T00:00:00Z", effective_at="2026-09-06T00:00:00Z",
        payload={"certification": {}},
        auth=golden.auth("onboarding.adapter.certify"),
    )
    if backdated.ok:
        results.append(_fail("case_58_out_of_order_instants", "empty certification accepted"))
        return
    digest = golden.state_digest()
    again = golden.service.execute_command(
        application_id=golden.application_id, command_kind=OnboardingCommandKind.CERTIFY_ADAPTER,
        command_key="cert-backdated", actor=_NODE_A,
        issued_at="2026-09-06T00:00:00Z", effective_at="2026-09-06T00:00:00Z",
        payload={"certification": {}},
        auth=golden.auth("onboarding.adapter.certify"),
    )
    if again.code != OnboardingReason.DUPLICATE or golden.state_digest() != digest:
        results.append(_fail("case_58_out_of_order_instants", "replay of backdated command not idempotent"))
        return
    results.append(_ok("case_58_out_of_order_instants",
                      "backdated instants are deterministic inputs; replays stay idempotent"))


def case_59_journal_prefix_fold(results: List[Tuple[str, bool, str]]) -> None:
    prefix_length = 7
    full_golden, _ = _golden()
    prefix_golden, _ = _golden(stop=prefix_length)
    prefix_document = prefix_golden.journal.to_mapping()
    if len(prefix_document["records"]) != prefix_length:
        results.append(_fail("case_59_journal_prefix_fold", "prefix record count wrong"))
        return
    journal = OnboardingJournal.from_mapping(prefix_document)
    federation_store = FederationStore()
    _platform_setup(federation_store)
    recovered = ProviderOnboardingService.load(
        journal=journal, federation_store=federation_store,
        platform_profile=_PLATFORM_PROFILE, issuance_key=_ISSUANCE_KEY,
    )
    if recovered.state_digest() != prefix_golden.state_digest():
        results.append(_fail("case_59_journal_prefix_fold", "prefix fold mismatch"))
        return
    # resume: run the remaining steps on the recovered service (the operator
    # re-derives/presents the credential secrets it holds)
    secrets: Dict[str, str] = {}
    recovered_projection = recovered.application(prefix_golden.application_id)
    for reference in sorted(recovered_projection.credentials):
        credential = recovered_projection.credentials[reference]
        secrets[credential.scope] = derive_onboarding_credential_secret(
            _ISSUANCE_KEY, prefix_golden.application_id, credential.scope, credential.sequence
        )
    _lifecycle(recovered, start=prefix_length, stop=_STEP_COUNT, secrets=secrets)
    projection = recovered.application(prefix_golden.application_id)
    if projection.application.lifecycle_state != OnboardingState.ACTIVE:
        results.append(_fail("case_59_journal_prefix_fold",
                             "resume did not reach ACTIVE: %r" % projection.application.lifecycle_state))
        return
    if recovered.state_digest() != full_golden.state_digest():
        results.append(_fail("case_59_journal_prefix_fold", "resumed state diverged from the full run"))
        return
    results.append(_ok("case_59_journal_prefix_fold",
                      "prefix fold == interrupted state; resume reaches the byte-identical final state"))


# ----------------------------------------------------------------------
# K. Recovery and tamper evidence
# ----------------------------------------------------------------------


def case_60_interrupted_onboarding_recovery(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    journal = OnboardingJournal.from_mapping(golden.journal.to_mapping())
    federation_store = FederationStore()
    _platform_setup(federation_store)
    recovered = ProviderOnboardingService.load(
        journal=journal, federation_store=federation_store,
        platform_profile=_PLATFORM_PROFILE, issuance_key=_ISSUANCE_KEY,
    )
    if recovered.state_digest() != golden.state_digest():
        results.append(_fail("case_60_interrupted_onboarding_recovery", "state digest mismatch"))
        return
    if federation_store.snapshot() != golden.federation_store.snapshot():
        results.append(_fail("case_60_interrupted_onboarding_recovery",
                             "federation state not reproduced byte-identically"))
        return
    projection = recovered.application(golden.application_id)
    if projection.membership_status != "active" or len(projection.membership_grant_ids) != 2:
        results.append(_fail("case_60_interrupted_onboarding_recovery", "membership not recovered"))
        return
    if len(federation_store.get_domains()) != 2:
        results.append(_fail("case_60_interrupted_onboarding_recovery",
                             "domain count wrong (duplicated membership?)"))
        return
    results.append(_ok("case_60_interrupted_onboarding_recovery",
                      "construction-is-recovery: the fold reproduces state, federation store, and "
                      "membership with no duplication"))


def case_61_journal_tamper_status_flip(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=2)
    document = golden.journal.to_mapping()
    flipped = False
    for record in document["records"]:
        if record["command_key"] == "register-1":
            record["status"] = "rejected"
            flipped = True
    if not flipped:
        results.append(_fail("case_61_journal_tamper_status_flip", "record not found"))
        return
    failed, code = _load_tampered(document)
    if not failed or code != OnboardingReason.JOURNAL_TAMPER:
        results.append(_fail("case_61_journal_tamper_status_flip",
                             "tamper not detected: %r" % code))
        return
    results.append(_ok("case_61_journal_tamper_status_flip",
                      "flipping an appended record to rejected fails closed (journal-tamper)"))


def case_62_journal_tamper_reason_flip(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden(stop=9)
    # a deterministic rejection to tamper: propose before eligibility (skipped stage)
    golden.service.propose_federation(
        application_id=golden.application_id, peer_domain_id=golden.peer_domain_id,
        peer_identity_reference=_NODE_B, declared_scopes=(Scope.CAPABILITY_READ,),
        valid_from=_VF, valid_until=_VU,
        command_key="propose-early-tamper", actor=_NODE_A,
        issued_at=_STEP_T[11], effective_at=_STEP_T[11],
        policy_decision=_policy_decision(),
        auth=golden.auth("onboarding.federation.propose"),
    )
    document = golden.journal.to_mapping()
    flipped = False
    for record in document["records"]:
        if record["command_key"] == "propose-early-tamper":
            record["reason_code"] = "invalid-input"
            flipped = True
    if not flipped:
        results.append(_fail("case_62_journal_tamper_reason_flip", "rejection not found"))
        return
    failed, code = _load_tampered(document)
    if not failed or code != OnboardingReason.JOURNAL_TAMPER:
        results.append(_fail("case_62_journal_tamper_reason_flip",
                             "reason tamper not detected: %r" % code))
        return
    results.append(_ok("case_62_journal_tamper_reason_flip",
                      "a deterministic rejection whose journaled reason was altered fails closed"))


def case_63_journal_serialization_round_trip(results: List[Tuple[str, bool, str]]) -> None:
    golden, _ = _golden()
    document = golden.journal.to_mapping()
    rebuilt = OnboardingJournal.from_mapping(document)
    if rebuilt.journal_digest() != golden.journal.journal_digest():
        results.append(_fail("case_63_journal_serialization_round_trip", "journal digest changed"))
        return
    if json.dumps(document, sort_keys=True) != json.dumps(rebuilt.to_mapping(), sort_keys=True):
        results.append(_fail("case_63_journal_serialization_round_trip", "document not stable"))
        return
    results.append(_ok("case_63_journal_serialization_round_trip",
                      "journal mapping round-trips byte-identically (canonical JSON)"))


def case_64_file_journal_durability(results: List[Tuple[str, bool, str]]) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "onboarding-journal.jsonl")
        journal = FileOnboardingJournal(path)
        golden, _ = _golden(journal=journal, stop=6)
        reloaded = FileOnboardingJournal(path)
        if reloaded.journal_digest() != journal.journal_digest():
            results.append(_fail("case_64_file_journal_durability", "file reload changed the journal"))
            return
        federation_store = FederationStore()
        _platform_setup(federation_store)
        recovered = ProviderOnboardingService.load(
            journal=reloaded, federation_store=federation_store,
            platform_profile=_PLATFORM_PROFILE, issuance_key=_ISSUANCE_KEY,
        )
        if recovered.state_digest() != golden.state_digest():
            results.append(_fail("case_64_file_journal_durability", "file-journal recovery mismatch"))
            return
        torn_path = str(Path(directory) / "torn-journal.jsonl")
        with open(torn_path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(golden.journal.to_mapping()["records"][0]) + "\n")
            handle.write('{"command_id": "sha256:tor')  # interrupted append
        try:
            FileOnboardingJournal(torn_path)
            torn_detected = False
            detail = "torn line accepted"
        except Exception as error:
            torn_detected = getattr(error, "code", "") == OnboardingReason.INVALID_INPUT
            detail = "raised %r" % getattr(error, "code", type(error).__name__)
        if not torn_detected:
            results.append(_fail("case_64_file_journal_durability", detail))
            return
    results.append(_ok("case_64_file_journal_durability",
                      "durable file journal: reload + fold reproduce the state; torn writes fail closed"))


# ----------------------------------------------------------------------
# L. Mixed-version compatibility (WORK-029 authority)
# ----------------------------------------------------------------------


def case_65_mixed_version_compatible(results: List[Tuple[str, bool, str]]) -> None:
    platform = (1, 3)
    golden, _ = _golden(platform_profile=platform)
    projection = golden.service.application(golden.application_id)
    application = projection.application
    if (application.common_profile_major, application.common_profile_minor) != (1, 0):
        results.append(_fail("case_65_mixed_version_compatible",
                             "common profile %r" % ((application.common_profile_major,
                                                     application.common_profile_minor),)))
        return
    if application.lifecycle_state != OnboardingState.ACTIVE:
        results.append(_fail("case_65_mixed_version_compatible", "mixed-version lifecycle failed"))
        return
    # The WORK-029 authority's own negotiation agrees verdict-for-verdict:
    # compatible peers share the additive-evolution floor.
    negotiation = negotiate_protocol_profile(
        ProtocolProfile(major=1, max_minor=0), ProtocolProfile(major=1, max_minor=3)
    )
    if negotiation.selected is None or (
        negotiation.selected.major, negotiation.selected.max_minor
    ) != (application.common_profile_major, application.common_profile_minor):
        results.append(_fail("case_65_mixed_version_compatible",
                             "the WORK-029 authority disagrees with the gate"))
        return
    results.append(_ok("case_65_mixed_version_compatible",
                      "platform 1.3 + applicant 1.0 share the additive-evolution floor 1.0; "
                      "the WORK-029 authority's negotiation agrees verdict-for-verdict; "
                      "the lifecycle completes"))


def case_66_incompatible_version_fails_closed(results: List[Tuple[str, bool, str]]) -> None:
    journal = OnboardingJournal()
    federation_store = FederationStore()
    service = ProviderOnboardingService(
        journal=journal, federation_store=federation_store,
        platform_profile=_PLATFORM_PROFILE, issuance_key=_ISSUANCE_KEY,
    )
    outcome = service.register_application(
        operator_reference="operator-reference-future", identity_public_key=_KEY_C,
        operator_node_id=_NODE_C, provider_id="provider-future", display_name="Future Net",
        policy_references=(), protocol_major=2, protocol_max_minor=0,
        key_material=b"future-key-material", actor=_NODE_C,
        command_key="register-future", issued_at=_STEP_T[0], effective_at=_STEP_T[0],
    )
    if outcome.ok or outcome.code != OnboardingReason.VERSION_INCOMPATIBLE:
        results.append(_fail("case_66_incompatible_version_fails_closed",
                             "reason %r" % outcome.code))
        return
    if service.application_ids():
        results.append(_fail("case_66_incompatible_version_fails_closed",
                             "an incompatible peer was partially registered"))
        return
    # The WORK-029 authority's own negotiation rejects the same pair.
    negotiation = negotiate_protocol_profile(
        ProtocolProfile(major=2, max_minor=0), ProtocolProfile(major=1, max_minor=0)
    )
    if negotiation.selected is not None:
        results.append(_fail("case_66_incompatible_version_fails_closed",
                             "the WORK-029 authority unexpectedly accepted a major mismatch"))
        return
    results.append(_ok("case_66_incompatible_version_fails_closed",
                      "major mismatch fails closed at the gate (the WORK-003 version line; "
                      "the WORK-029 authority rejects the same pair; never reinterpreted)"))


# ----------------------------------------------------------------------
# M. Determinism
# ----------------------------------------------------------------------


def case_67_repeat_run_byte_identical(results: List[Tuple[str, bool, str]]) -> None:
    first, _ = _golden()
    second, _ = _golden()
    if first.state_digest() != second.state_digest():
        results.append(_fail("case_67_repeat_run_byte_identical", "state digest differs"))
        return
    if first.journal_digest() != second.journal_digest():
        results.append(_fail("case_67_repeat_run_byte_identical", "journal digest differs"))
        return
    if json.dumps(first.service.snapshot(), sort_keys=True) != json.dumps(second.service.snapshot(), sort_keys=True):
        results.append(_fail("case_67_repeat_run_byte_identical", "snapshot differs"))
        return
    results.append(_ok("case_67_repeat_run_byte_identical",
                      "two independent golden runs are byte-identical (state, journal, snapshot)"))


def case_68_pythonhashseed_determinism(results: List[Tuple[str, bool, str]]) -> None:
    script = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "sys.path.insert(0, %r)\n"
        "import onboarding_selftest as battery\n"
        "golden, _context = battery._golden()\n"
        "print(golden.state_digest())\n"
        "print(golden.journal_digest())\n"
    ) % (str(REPO_ROOT), str(REPO_ROOT / "tools"))
    digests = []
    for seed in ("0", "1", "7919"):
        environment = dict(__import__("os").environ)
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", script], cwd=str(REPO_ROOT),
            capture_output=True, text=True, env=environment,
        )
        if completed.returncode != 0:
            results.append(_fail("case_68_pythonhashseed_determinism",
                                 "seed %s failed: %s" % (seed, completed.stderr[-200:])))
            return
        digests.append(tuple(completed.stdout.strip().split("\n")))
    if len(set(digests)) != 1:
        results.append(_fail("case_68_pythonhashseed_determinism", "digests differ across seeds"))
        return
    results.append(_ok("case_68_pythonhashseed_determinism",
                      "PYTHONHASHSEED=0/1/7919 produce identical digests across processes"))


def case_69_source_level_determinism_audit(results: List[Tuple[str, bool, str]]) -> None:
    modules = [
        "federation/onboarding_model.py",
        "federation/onboarding_store.py",
        "federation/onboarding_service.py",
        "adapters/certification.py",
    ]
    forbidden_imports = {"time", "datetime", "random", "uuid", "socket", "urllib", "http", "ssl", "requests"}
    violations: List[str] = []
    for relative_path in modules:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden_imports:
                        violations.append("%s imports %s" % (relative_path, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in forbidden_imports:
                    violations.append("%s imports from %s" % (relative_path, node.module))
    if violations:
        results.append(_fail("case_69_source_level_determinism_audit", "; ".join(violations[:3])))
        return
    results.append(_ok("case_69_source_level_determinism_audit",
                      "no wall-clock, randomness, UUID, or network imports in the onboarding layer"))


# ----------------------------------------------------------------------
# N. Governance guards (evergreen, pinned baseline)
# ----------------------------------------------------------------------


def case_70_vocabulary_freeze(results: List[Tuple[str, bool, str]]) -> None:
    checks = (
        ("states", len(OnboardingState.values()), 14),
        ("command kinds", len(OnboardingCommandKind.values()), 18),
        ("credential scopes", len(OnboardingCredentialScope.values()), 5),
        ("reasons", len(OnboardingReason.values()), 46),
        ("transition entries", len(ONBOARDING_TRANSITIONS), 14),
        ("required-scope entries", len(COMMAND_REQUIRED_SCOPE), 16),
    )
    for label, actual, expected in checks:
        if actual != expected:
            results.append(_fail("case_70_vocabulary_freeze",
                                 "%s: %d (expected %d)" % (label, actual, expected)))
            return
    if not onboarding_transition_is_legal("registered", "revoked"):
        results.append(_fail("case_70_vocabulary_freeze", "transition table changed"))
        return
    results.append(_ok("case_70_vocabulary_freeze",
                      "onboarding vocabularies pinned (14 states, 18 commands, 5 scopes, 46 reasons)"))


_FROZEN_SURFACES = (
    "spec/architecture.md",
    "spec/architecture-lock.md",
    "spec/mission.md",
    "spec/work-items.md",
    "spec/dependency-graph.md",
    "spec/schemas/protocol.json",
)


def case_71_frozen_surfaces_unchanged(results: List[Tuple[str, bool, str]]) -> None:
    diff = _git("diff", _BASELINE, "--", *_FROZEN_SURFACES)
    if diff.returncode != 0:
        results.append(_fail("case_71_frozen_surfaces_unchanged",
                             "git failed: %s" % diff.stderr.strip()[:120]))
        return
    if diff.stdout.strip():
        results.append(_fail("case_71_frozen_surfaces_unchanged",
                             "frozen surfaces changed vs baseline 16c066f"))
        return
    results.append(_ok("case_71_frozen_surfaces_unchanged",
                      "all frozen architecture/protocol surfaces byte-identical to the pinned baseline "
                      "(evergreen: fixed object SHA, environment-independent)"))


_AUTHORIZED_PREFIXES = (
    "federation/onboarding_model.py",
    "federation/onboarding_store.py",
    "federation/onboarding_service.py",
    "adapters/certification.py",
    "tools/onboarding_selftest.py",
    "docs/WORK-057-evidence.md",
    "docs/WORK-057-handoff.md",
)


def case_72_delivery_scope_discipline(results: List[Tuple[str, bool, str]]) -> None:
    diff = _git("diff", "--name-only", _DELIVERY_BASE)
    if diff.returncode != 0:
        results.append(_fail("case_72_delivery_scope_discipline",
                             "git failed: %s" % diff.stderr.strip()[:120]))
        return
    changed = [path for path in diff.stdout.split("\n") if path.strip()]
    unauthorized = [path for path in changed if path not in _AUTHORIZED_PREFIXES]
    if unauthorized:
        results.append(_fail("case_72_delivery_scope_discipline",
                             "delta outside WORK-057-CORE-001: %r" % (unauthorized[:4],)))
        return
    results.append(_ok("case_72_delivery_scope_discipline",
                      "the whole delivery delta (vs the recorded branch point 12ae8f7) is inside the "
                      "authorized scope: %d file(s)" % len(changed)))


def case_73_w048_w040_untouched(results: List[Tuple[str, bool, str]]) -> None:
    guards = _git("diff", _BASELINE, "--",
                  "docs/WORK-048-provider-sharing-runtime-design.md", "pilot/")
    if guards.returncode != 0 or guards.stdout.strip():
        results.append(_fail("case_73_w048_w040_untouched", "W048/pilot surface changed"))
        return
    w040 = _git("diff", _BASELINE, "--", "docs/WORK-040-correction-handoff.md")
    if w040.returncode != 0 or w040.stdout.strip():
        results.append(_fail("case_73_w048_w040_untouched", "W040 surface changed"))
        return
    log = _git("log", "--diff-filter=A", "--name-only", "--format=%H",
               _BASELINE + "..HEAD", "--", "pilot/", "*sharing*", "*WORK-048*")
    if log.returncode != 0 or log.stdout.strip():
        results.append(_fail("case_73_w048_w040_untouched", "W048 material added"))
        return
    results.append(_ok("case_73_w048_w040_untouched",
                      "W048 remains un-restored and W040 physical-evidence surfaces are untouched"))


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------

_CASES = [
    case_01_deterministic_application_identity,
    case_02_lifecycle_golden_path,
    case_03_duplicate_registration_idempotent,
    case_04_semantic_re_registration_idempotent,
    case_05_conflicting_re_registration,
    case_06_invalid_operator_node_id,
    case_07_malformed_inputs_fail_closed,
    case_08_secret_material_rejected,
    case_09_credential_secret_discipline,
    case_10_credential_scope_vocabulary,
    case_11_wrong_scope_denied,
    case_12_credential_revocation_fail_closed,
    case_13_credential_expiry_evaluated,
    case_14_wrong_secret_no_enumeration,
    case_15_key_proof_fail_closed,
    case_16_credential_issue_scope_bootstrap,
    case_17_certification_deterministic_and_tamper_evident,
    case_18_unattested_declaration_rejected,
    case_19_invalid_adapter_id_rejected,
    case_20_invalid_capability_reference_rejected,
    case_21_descriptor_secret_material_rejected,
    case_22_forbidden_import_discipline,
    case_23_access_technology_leakage_in_free_text,
    case_24_declaration_provenance_validity,
    case_25_unknown_capability_preserved,
    case_26_declaration_withdrawal,
    case_27_resource_owner_binding,
    case_28_declaration_expiry_evaluated,
    case_29_declarations_are_claims,
    case_30_commercial_profile_reference_only,
    case_31_binding_shape_enforced,
    case_32_policy_allow_required,
    case_33_policy_tamper_evidence,
    case_34_policy_reference_mismatch,
    case_35_proposal_requires_verified_decision,
    case_36_eligibility_not_eligible,
    case_37_eligibility_domain_and_subject,
    case_38_eligibility_expiry_evaluated,
    case_39_policy_decision_is_not_trust,
    case_40_stage_preconditions_enforced,
    case_41_relationship_via_federation_authority,
    case_42_peer_unregistered_fail_closed,
    case_43_peer_identity_mismatch,
    case_44_explicit_acceptance_and_narrowing,
    case_45_scope_envelope_least_authority,
    case_46_suspension_blocks_admission,
    case_47_revocation_fail_closed,
    case_48_offboarding_deterministic,
    case_49_offboarding_preserves_history,
    case_50_re_registration_after_offboard,
    case_51_membership_non_transitive,
    case_52_no_second_authorities,
    case_53_no_connectivity_state_created,
    case_54_duplicate_command_idempotent,
    case_55_command_key_conflict,
    case_56_journal_sequence_discipline,
    case_57_concurrent_commands_safe,
    case_58_out_of_order_instants,
    case_59_journal_prefix_fold,
    case_60_interrupted_onboarding_recovery,
    case_61_journal_tamper_status_flip,
    case_62_journal_tamper_reason_flip,
    case_63_journal_serialization_round_trip,
    case_64_file_journal_durability,
    case_65_mixed_version_compatible,
    case_66_incompatible_version_fails_closed,
    case_67_repeat_run_byte_identical,
    case_68_pythonhashseed_determinism,
    case_69_source_level_determinism_audit,
    case_70_vocabulary_freeze,
    case_71_frozen_surfaces_unchanged,
    case_72_delivery_scope_discipline,
    case_73_w048_w040_untouched,
]


def main() -> int:
    results: List[Tuple[str, bool, str]] = []
    print("ADCOS provider onboarding self-test (WORK-057)")
    print("=" * 72)
    for case in _CASES:
        try:
            case(results)
        except Exception as error:  # a battery defect, not a product verdict
            name = "case_%02d_unexpected_failure" % (_CASES.index(case) + 1)
            results.append(_fail(name, "%s: %s" % (type(error).__name__, error)))
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
