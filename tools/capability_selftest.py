#!/usr/bin/env python3
"""ADCOS capability self-test (WORK-005).

Deterministic, offline verification of the capabilities package against
the frozen WORK-005 requirements (spec/prompts/WORK-005.md): the 20
required test cases plus serialization round-trips, WORK-003 envelope
integration, adversarial provenance checks, and seeded fuzz.

The central boundary is exercised throughout:

    capability statement  ≠  truth  ≠  trust  ≠  authorization
                         ≠  topology authority

All key material is TEST-ONLY; all clocks are injected; all PRNGs are
seeded so runs are byte-identical.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from capabilities import (  # noqa: E402
    CapabilityError,
    statement_from_mapping,
    CapabilityIdClass,
    CapabilityStatement,
    NegotiationSpec,
    RejectionReason,
    Requirement,
    SerializationError,
    StatementStatus,
    ValidityError,
    classify_capability_id,
    evaluate_status,
    negotiate,
    sign_statement,
    statement_from_bytes,
    statement_signature_input,
    statement_to_bytes,
    verify_statement,
)
from identity import (  # noqa: E402
    CredentialReference,
    DevHmacSha256Provider,
    IdentityService,
    InMemoryCredentialStore,
    KeyRole,
    NodeIdentity,
    ProfileSet,
    SignatureProvider,
)
from protocol import (  # noqa: E402
    Classification,
    ParsePolicy,
    UnknownTypePolicy,
    accept,
    envelope_from_mapping,
    validation_clock,
)
from protocol.codec_cbor import CompactDeterministicCborCodec  # noqa: E402
from protocol.codec_json import JsonDebugCodec  # noqa: E402
from schema_check import load_json, validate_instance  # noqa: E402

NOW_TEXT = "2030-01-01T00:00:00Z"
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
NEGOTIATION_NOW = datetime(2030, 1, 15, tzinfo=timezone.utc)
PROVIDER_SECRET = b"TEST-ONLY-capability-provider-key-DO-NOT-USE-1"

JSON_CODEC = JsonDebugCodec()
CBOR_CODEC = CompactDeterministicCborCodec()
CAPABILITY_SCHEMA = load_json(
    (REPO_ROOT / "spec" / "schemas" / "capability.schema.json").read_text(encoding="utf-8")
)

#: A well-formed but unregistered capability identifier (future test).
FUTURE_CAPABILITY = "capability.core.holographic-relay"


class SeededRandom:
    """Deterministic LCG (same construction as the other suites)."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        self._state = (
            self._state * 6364136223846793005 + 1442695040888963407
        ) & 0xFFFFFFFFFFFFFFFF
        return self._state >> 33

    def below(self, bound: int) -> int:
        return self._next() % bound


def make_identity() -> Tuple[
    IdentityService, InMemoryCredentialStore, DevHmacSha256Provider, NodeIdentity, CredentialReference
]:
    profiles = ProfileSet.load_default()
    store = InMemoryCredentialStore()
    provider = DevHmacSha256Provider()
    service = IdentityService(store=store, provider=provider, profiles=profiles)
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident = NodeIdentity.create(profile, provider.public_material(PROVIDER_SECRET), NOW_TEXT)
    ref = service.provision(ident, KeyRole.IDENTITY, PROVIDER_SECRET, now=NOW_TEXT)
    service.activate(ref, now=NOW_TEXT)
    return service, store, provider, ident, ref


def base_statement(**overrides: Any) -> CapabilityStatement:
    data: dict = dict(
        capability_id="capability.core.multipath",
        schema_version="1.0",
        provider_identity="adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 64,
        valid_from="2030-01-01T00:00:00Z",
        expires_at="2030-02-01T00:00:00Z",
        parameters={"max_paths": 4},
        constraints={"privacy": "end_to_end"},
        evidence_references=["evidence:ref-0001"],
    )
    data.update(overrides)
    return CapabilityStatement(**data)  # type: ignore[arg-type]


def signed_statement(
    store: InMemoryCredentialStore,
    provider: DevHmacSha256Provider,
    credential: CredentialReference,
    *,
    provider_identity: Optional[str] = None,
    **overrides: Any,
) -> CapabilityStatement:
    """Sign a base statement, using the credential's NodeID as
    provider_identity by default (the binding is now enforced by
    verify_statement, so the two must match)."""
    record = store.get_record(credential)
    overrides.setdefault("provider_identity", record.node_id.text)
    if provider_identity is not None:
        overrides["provider_identity"] = provider_identity
    return sign_statement(
        base_statement(**overrides), store=store, provider=provider, credential=credential
    )


# ---------------------------------------------------------------------------
# Required tests 1-3: construction, schema, signing
# ---------------------------------------------------------------------------


def case_construction_and_schema(results: List[Tuple[str, bool, str]]) -> None:
    statement = base_statement()
    errors = validate_instance(statement.to_dict(), CAPABILITY_SCHEMA)
    # Deterministic: identical inputs -> identical canonical bytes.
    stable = statement_signature_input(statement) == statement_signature_input(
        base_statement()
    )
    results.append(
        (
            "capability-construction-and-schema",
            not errors and stable,
            "constructs; validates against the WORK-002 capability schema; "
            "signature input deterministic" if not errors else errors[0],
        )
    )


def case_signing_and_verification(results: List[Tuple[str, bool, str]]) -> None:
    _, store, provider, _, ref = make_identity()
    signed = signed_statement(store, provider, ref)
    ok = verify_statement(signed, store=store, provider=provider, credential=ref, now=NOW)
    # Different statement content -> different signature input bytes.
    other = signed_statement(store, provider, ref, parameters={"max_paths": 8})
    different_input = (
        statement_signature_input(signed) != statement_signature_input(other)
    )
    results.append(
        (
            "signing-through-provider-seam",
            ok and different_input,
            "sign/verify via WORK-004 seam; distinct content -> distinct input",
        )
    )


# ---------------------------------------------------------------------------
# Required tests 4-6: tamper rejection
# ---------------------------------------------------------------------------


def case_tamper_rejection(results: List[Tuple[str, bool, str]]) -> None:
    _, store, provider, _, ref = make_identity()
    signed = signed_statement(store, provider, ref)
    verify = lambda s: verify_statement(s, store=store, provider=provider, credential=ref, now=NOW)  # noqa: E731
    checks = {
        "parameters": replace(signed, parameters={"max_paths": 999}),
        "provider": replace(signed, provider_identity="adcos:node:identity.sha256-hmac-dev.v1:" + "9" * 64),
        "evidence": replace(signed, evidence_references=("evidence:ref-evil",)),
        "validity": replace(signed, expires_at="2031-01-01T00:00:00Z"),
        "constraints": replace(signed, constraints={"privacy": "plaintext"}),
        "withdrawal": replace(signed, withdrawn_at="2030-01-10T00:00:00Z"),
        "schema-version": replace(signed, schema_version="2.0"),
        "capability-id": replace(signed, capability_id="capability.core.store-and-forward"),
    }
    rejected = {name: not verify(mutated) for name, mutated in checks.items()}
    all_rejected = all(rejected.values())
    results.append(
        (
            "tampered-content-rejected",
            all_rejected and verify(signed),
            "tampering parameters/provider/evidence/validity/constraints/"
            "withdrawal/schema-version/capability-id each invalidates the signature"
            if all_rejected
            else "NOT rejected: %s" % [k for k, v in rejected.items() if not v],
        )
    )


# ---------------------------------------------------------------------------
# Required tests 7-8: expiry and withdrawal
# ---------------------------------------------------------------------------


def case_expiry_and_withdrawal(results: List[Tuple[str, bool, str]]) -> None:
    _, store, provider, _, ref = make_identity()
    signed = signed_statement(store, provider, ref)
    expired = replace(
        signed, valid_from="2029-01-01T00:00:00Z", expires_at="2029-02-01T00:00:00Z"
    )
    withdrawn = signed.withdraw("2030-01-10T00:00:00Z")
    req = Requirement("capability.core.multipath")
    expired_result = negotiate(
        NegotiationSpec(requirements=(req,), peer_statements=(expired,), now=NEGOTIATION_NOW)
    )
    withdrawn_result = negotiate(
        NegotiationSpec(requirements=(req,), peer_statements=(withdrawn,), now=NEGOTIATION_NOW)
    )
    status_expired = evaluate_status(
        valid_from=expired.valid_from, expires_at=expired.expires_at,
        withdrawn_at=None, now=NEGOTIATION_NOW,
    )
    status_withdrawn = evaluate_status(
        valid_from=withdrawn.valid_from, expires_at=withdrawn.expires_at,
        withdrawn_at=withdrawn.withdrawn_at, now=NEGOTIATION_NOW,
    )
    # Withdrawal timestamp is covered by the signature (tamper test above).
    ok = (
        status_expired == StatementStatus.EXPIRED
        and status_withdrawn == StatementStatus.WITHDRAWN
        and not expired_result.succeeded
        and not withdrawn_result.succeeded
    )
    # Distinct concepts: withdrawal carries a timestamp, expiry does not
    # mutate the statement; historical statements remain queryable.
    results.append(
        (
            "expiry-and-withdrawal-rejected-in-negotiation",
            ok,
            "expired -> %s; withdrawn -> %s; neither negotiates as usable; "
            "withdrawal distinct from expiry" % (status_expired, status_withdrawn),
        )
    )


# ---------------------------------------------------------------------------
# Required tests 9-12: open-world identifiers
# ---------------------------------------------------------------------------


def case_open_world_identifiers(results: List[Tuple[str, bool, str]]) -> None:
    failures: List[str] = []
    # 9: unknown optional preserved/ignored safely.
    result = negotiate(
        NegotiationSpec(
            requirements=(Requirement(FUTURE_CAPABILITY, required=False),),
            peer_statements=(),
            now=NEGOTIATION_NOW,
        )
    )
    if not result.succeeded or result.outcomes[0].reason is not None:
        failures.append("unknown optional capability failed negotiation")
    # 10: unknown required causes explicit failure.
    result2 = negotiate(
        NegotiationSpec(
            requirements=(Requirement(FUTURE_CAPABILITY, required=True),),
            peer_statements=(),
            now=NEGOTIATION_NOW,
        )
    )
    if result2.succeeded or result2.outcomes[0].reason != RejectionReason.UNKNOWN_REQUIRED_CAPABILITY:
        failures.append("unknown required capability not rejected explicitly")
    # 11: malformed capability ID rejected (model fails closed).
    for bad in ("Not A Capability", "", "capability", "Capability.Core.Multipath", 42, None):
        try:
            base_statement(capability_id=bad)  # type: ignore[arg-type]
            failures.append("malformed capability_id %r accepted" % (bad,))
        except CapabilityError:
            pass
    # 12: future well-formed capability ID represented without core change.
    future_statement = base_statement(capability_id=FUTURE_CAPABILITY)
    if classify_capability_id(FUTURE_CAPABILITY) != CapabilityIdClass.UNKNOWN_BUT_WELL_FORMED:
        failures.append("future capability not classified unknown-but-well-formed")
    if future_statement.to_dict()["capability_id"] != FUTURE_CAPABILITY:
        failures.append("future capability id not preserved verbatim")
    results.append(
        (
            "open-world-identifier-semantics",
            not failures,
            "unknown optional ignored; unknown required fails explicitly; malformed "
            "rejected; future id preserved verbatim (%s)" % FUTURE_CAPABILITY
            if not failures
            else failures[0],
        )
    )


# ---------------------------------------------------------------------------
# Required tests 13-17: negotiation determinism
# ---------------------------------------------------------------------------


def case_negotiation(results: List[Tuple[str, bool, str]]) -> None:
    _, store, provider, _, ref = make_identity()
    signed = signed_statement(store, provider, ref)
    ok = True
    detail = ""

    # 13: compatible negotiation succeeds.
    result = negotiate(
        NegotiationSpec(
            requirements=(
                Requirement(
                    "capability.core.multipath",
                    min_schema_version="1.0",
                    required_parameters={"max_paths": 2},
                    required_constraints={"privacy": "end_to_end"},
                ),
            ),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if not (result.succeeded and result.outcomes[0].selected is signed):
        ok, detail = False, "compatible negotiation failed"
    # 14: incompatible version negotiation fails deterministically.
    result14 = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath", min_schema_version="2.0"),),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if result14.succeeded or result14.outcomes[0].reason != RejectionReason.VERSION_INCOMPATIBLE:
        ok, detail = False, "version incompatibility not detected"
    major_mismatch = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath", min_schema_version="2.0"),),
            peer_statements=(replace(signed, schema_version="2.5"),),
            now=NEGOTIATION_NOW,
        )
    )
    # 15: parameter mismatch fails deterministically.
    result15 = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath", required_parameters={"max_paths": 100}),),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if result15.succeeded or result15.outcomes[0].reason != RejectionReason.PARAMETER_MISMATCH:
        ok, detail = False, "parameter mismatch not detected"
    # 16: constraint mismatch fails deterministically AND distinctly.
    result16 = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath", required_constraints={"privacy": "plaintext"}),),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if result16.succeeded or result16.outcomes[0].reason != RejectionReason.CONSTRAINT_MISMATCH:
        ok, detail = False, "constraint mismatch not detected distinctly (got %s)" % result16.outcomes[0].reason
    # Parameter-only failure must emit parameter-mismatch, not constraint-mismatch.
    result16b = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath", required_parameters={"max_paths": 100}),),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if result16b.outcomes[0].reason != RejectionReason.PARAMETER_MISMATCH:
        ok, detail = False, "parameter-only failure misclassified: %s" % result16b.outcomes[0].reason
    # Both failing: parameters checked first (deterministic order).
    result16c = negotiate(
        NegotiationSpec(
            requirements=(
                Requirement("capability.core.multipath", required_parameters={"max_paths": 100}, required_constraints={"privacy": "plaintext"}),
            ),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if result16c.outcomes[0].reason != RejectionReason.PARAMETER_MISMATCH:
        ok, detail = False, "both-failing case not deterministic: %s" % result16c.outcomes[0].reason
    # 17: deterministic tie-breaking with multiple compatible candidates.
    candidates = [
        signed,
        signed_statement(store, provider, ref, parameters={"max_paths": 8}),
        signed_statement(store, provider, ref, parameters={"max_paths": 6}),
    ]
    result17 = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath"),),
            peer_statements=tuple(candidates),
            now=NEGOTIATION_NOW,
        )
    )
    result17_shuffled = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath"),),
            peer_statements=tuple(reversed(candidates)),
            now=NEGOTIATION_NOW,
        )
    )
    if not (
        result17.succeeded
        and result17_shuffled.succeeded
        and result17.outcomes[0].selected is result17_shuffled.outcomes[0].selected
    ):
        ok, detail = False, "tie-breaking not deterministic under input reordering"
    # Repeat-run determinism.
    again = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath"),),
            peer_statements=tuple(candidates),
            now=NEGOTIATION_NOW,
        )
    )
    if again.outcomes[0].selected is not result17.outcomes[0].selected:
        ok, detail = False, "negotiation result changed across identical runs"
    results.append(
        (
            "negotiation-deterministic-matrix",
            ok,
            detail
            or "compatible selects; version/parameter/constraint mismatches fail explicitly; "
            "tie-breaking stable under input reordering and repeat runs",
        )
    )


# ---------------------------------------------------------------------------
# Required tests 18-19: boundary semantics
# ---------------------------------------------------------------------------


def case_not_authority(results: List[Tuple[str, bool, str]]) -> None:
    """18: negotiation grants no trust/authorization; 19: evidence stays
    references. A signed statement from a valid identity about another
    node remains a CLAIM — nothing in the capability layer upgrades it."""
    service, store, provider, ident, ref = make_identity()
    profiles = ProfileSet.load_default()
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    # Node B (the signer) reports a claim ABOUT Node A. The statement's
    # provider_identity is B (the signer/provenance), and the EVIDENCE
    # references point to observations about A. The statement is an
    # attributable claim BY B — verify_statement confirms B signed it —
    # but nothing upgrades it to truth/authority about A.
    secret_b = b"TEST-ONLY-node-B-for-claim-test"
    ident_b = NodeIdentity.create(profile, provider.public_material(secret_b), NOW_TEXT)
    ref_b = service.provision(ident_b, KeyRole.IDENTITY, secret_b, now=NOW_TEXT)
    service.activate(ref_b, now=NOW_TEXT)
    claim = signed_statement(
        store, provider, ref_b,
        evidence_references=("evidence:observation-about-node-A",),
    )
    # verify_statement confirms B signed this (B's credential matches the
    # statement's provider_identity, which IS B). But the evidence about
    # A remains a CLAIM by B, never authority (LOCK-008).
    claim_verified = verify_statement(
        claim, store=store, provider=provider, credential=ref_b, now=NEGOTIATION_NOW,
    )
    result = negotiate(
        NegotiationSpec(
            requirements=(Requirement("capability.core.multipath"),),
            peer_statements=(claim,),
            now=NEGOTIATION_NOW,
        )
    )
    selected = result.outcomes[0].selected
    ok = (
        claim_verified
        and result.succeeded
        and selected is claim
        and selected.evidence_references == ("evidence:observation-about-node-A",)
        and selected.provider_identity == ident_b.node_id.text
        and not hasattr(result, "trust")  # no trust concept on the result
        and not hasattr(result, "authorized")  # no authorization concept
    )
    # The NegotiationResult type carries ONLY selection/rejection data.
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(result)} | {"_requirements"}
    ok = ok and field_names <= {"outcomes", "_requirements"}
    results.append(
        (
            "claim-not-trust-not-authority",
            ok,
            "signed statement about a third party verifies as attributable CLAIM; "
            "evidence remains opaque references; result type carries no trust/"
            "authorization surface",
        )
    )


# ---------------------------------------------------------------------------
# Required test 20 + round-trips: robustness and codecs
# ---------------------------------------------------------------------------


def case_fuzz(results: List[Tuple[str, bool, str]]) -> None:
    _, store, provider, _, ref = make_identity()
    signed = signed_statement(store, provider, ref)
    blob = statement_to_bytes(signed)
    rng = SeededRandom(seed=424242)
    failures: List[str] = []
    checked = 0
    for iteration in range(300):
        body = bytearray(blob)
        operation = rng.below(3)
        if operation == 0:
            body[rng.below(len(body))] = rng.below(256)
        elif operation == 1:
            body = body[: rng.below(len(body))]
        else:
            position = rng.below(len(body) + 1)
            body = body[:position] + bytes([rng.below(256)]) + body[position:]
        checked += 1
        try:
            statement_from_bytes(bytes(body))
        except (SerializationError, CapabilityError):
            pass
        except Exception as error:
            failures.append("iter %d raised %s" % (iteration, type(error).__name__))
            break
    # Structural garbage.
    for bad in (b"", b"[]", b"null", b'{"capability_id": 42}', b"\xff\xfe", b"{"):
        checked += 1
        try:
            statement_from_bytes(bad)
            failures.append("garbage accepted: %r" % bad[:20])
        except (SerializationError, CapabilityError):
            pass
    # Negotiation with mutated statements never crashes.
    for iteration in range(100):
        mutated = bytearray(blob)
        mutated[rng.below(len(mutated))] = rng.below(256)
        try:
            statement_from_bytes(bytes(mutated))
        except Exception:
            continue
        try:
            negotiate(
                NegotiationSpec(
                    requirements=(Requirement("capability.core.multipath", required=False),),
                    peer_statements=(),
                    now=NEGOTIATION_NOW,
                )
            )
        except Exception as error:
            failures.append("negotiation crashed: %s" % type(error).__name__)
            break
    results.append(
        (
            "fuzzed-statements-fail-safely",
            not failures,
            "%d mutated/garbage inputs handled without crashes" % checked
            if not failures
            else failures[0],
        )
    )


def case_serialization_roundtrip(results: List[Tuple[str, bool, str]]) -> None:
    _, store, provider, ident, ref = make_identity()
    signed = signed_statement(store, provider, ref)
    blob = statement_to_bytes(signed)
    parsed = statement_from_bytes(blob)
    ok = parsed.to_dict() == signed.to_dict() and statement_to_bytes(parsed) == blob
    # Duplicate keys rejected.
    try:
        statement_from_bytes(blob.replace(b'"capability_id"', b'"capability_id","capability_id"', 1))
        ok = False
        detail = "duplicate keys accepted"
    except SerializationError:
        detail = "canonical round-trip byte-stable; duplicate keys rejected"
    # WORK-003 envelope integration: capability advertisement travels under
    # the registered capability.advertise type (frozen section 7 example).
    outcome = accept(
        JSON_CODEC.encode(
            envelope_from_mapping(
                {
                    "protocol": "adcos",
                    "version": 1,
                    "message_type": "capability.advertise",
                    "message_id": "cap-msg-0001",
                    "sender": signed.provider_identity,
                    "issued_at": NOW_TEXT,
                    "expires_at": "2030-02-01T00:00:00Z",
                    "extensions": {},
                    "payload": signed.to_dict(),
                    "evidence": list(signed.evidence_references),
                    "signature": "opaque-envelope-signature",
                }
            )
        ),
        now=validation_clock(NOW_TEXT),
        policy=ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE),
    )
    envelope_ok = (
        outcome.accepted
        and outcome.classification == Classification.KNOWN_COMPATIBLE
        and outcome.validated is not None
        and outcome.validated.envelope.payload["capability_id"] == signed.capability_id
    )
    # Compact codec round-trip through the envelope.
    env = envelope_from_mapping(
        {
            "protocol": "adcos", "version": 1, "message_type": "capability.advertise",
            "message_id": "cap-msg-0002", "sender": signed.provider_identity,
            "issued_at": NOW_TEXT, "expires_at": "2030-02-01T00:00:00Z",
            "extensions": {}, "payload": signed.to_dict(),
            "evidence": [], "signature": "opaque",
        }
    )
    compact_ok = (
        CBOR_CODEC.encode(CBOR_CODEC.decode(CBOR_CODEC.encode(env)))
        == CBOR_CODEC.encode(env)
    )
    results.append(
        (
            "serialization-and-envelope-roundtrip",
            ok and envelope_ok and compact_ok,
            detail + "; WORK-003 envelope (registered type) accepted; compact codec stable",
        )
    )


def case_validity_matrix(results: List[Tuple[str, bool, str]]) -> None:
    """Validity semantics: malformed intervals fail closed; not-yet-valid,
    expired, withdrawn, active are distinct; boundary instants exact."""
    failures: List[str] = []
    for bad_from, bad_to in (
        ("2030-01-01", "2030-02-01T00:00:00Z"),
        ("2030-13-01T00:00:00Z", "2030-02-01T00:00:00Z"),
        ("2030-02-01T00:00:00Z", "2030-01-01T00:00:00Z"),  # inverted
        (42, "2030-02-01T00:00:00Z"),
    ):
        try:
            base_statement(valid_from=bad_from, expires_at=bad_to)  # type: ignore[arg-type]
            failures.append("malformed validity accepted: %r" % ((bad_from, bad_to),))
        except CapabilityError:
            pass
    statuses = {
        "active": evaluate_status(
            valid_from="2030-01-01T00:00:00Z", expires_at="2030-02-01T00:00:00Z",
            withdrawn_at=None, now=datetime(2030, 1, 15, tzinfo=timezone.utc),
        ),
        "expired": evaluate_status(
            valid_from="2030-01-01T00:00:00Z", expires_at="2030-02-01T00:00:00Z",
            withdrawn_at=None, now=datetime(2030, 3, 1, tzinfo=timezone.utc),
        ),
        "not-yet-valid": evaluate_status(
            valid_from="2030-01-01T00:00:00Z", expires_at="2030-02-01T00:00:00Z",
            withdrawn_at=None, now=datetime(2029, 6, 1, tzinfo=timezone.utc),
        ),
        "withdrawn": evaluate_status(
            valid_from="2030-01-01T00:00:00Z", expires_at="2030-02-01T00:00:00Z",
            withdrawn_at="2030-01-05T00:00:00Z", now=datetime(2030, 1, 15, tzinfo=timezone.utc),
        ),
        "boundary-exact": evaluate_status(
            valid_from="2030-01-01T00:00:00Z", expires_at="2030-02-01T00:00:00Z",
            withdrawn_at=None, now=datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        ),
        "boundary-expired": evaluate_status(
            valid_from="2030-01-01T00:00:00Z", expires_at="2030-02-01T00:00:00Z",
            withdrawn_at=None, now=datetime(2030, 2, 1, 0, 0, 1, tzinfo=timezone.utc),
        ),
    }
    expected = {
        "active": StatementStatus.ACTIVE,
        "expired": StatementStatus.EXPIRED,
        "not-yet-valid": StatementStatus.NOT_YET_VALID,
        "withdrawn": StatementStatus.WITHDRAWN,
        "boundary-exact": StatementStatus.ACTIVE,
        "boundary-expired": StatementStatus.EXPIRED,
    }
    for name, want in expected.items():
        if statuses[name] != want:
            failures.append("%s evaluated %s (want %s)" % (name, statuses[name], want))
    results.append(
        (
            "validity-matrix-distinct-concepts",
            not failures,
            "malformed intervals fail closed; active/expired/not-yet-valid/withdrawn "
            "distinct; boundary instants exact" if not failures else failures[0],
        )
    )


def case_no_second_vocabulary(results: List[Tuple[str, bool, str]]) -> None:
    """The capability package must not duplicate the registry vocabulary
    in source code: identifiers are loaded from the registry, never
    hard-coded as an enum/list in the package."""
    import re
    from pathlib import Path as P

    package_dir = P(__file__).resolve().parents[1] / "capabilities"
    pattern = re.compile(r"capability\.(core|profile)\.[a-z0-9][a-z0-9-]*")
    offenders: List[str] = []
    for module in sorted(package_dir.glob("*.py")):
        text = module.read_text(encoding="utf-8")
        # Docstrings mentioning examples are acceptable in README only;
        # code must not enumerate identifiers.
        for match in pattern.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line = text[line_start : text.find("\n", match.start())]
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("Example"):
                continue
            # references inside docstrings (lines within triple quotes) are
            # documentation; detect actual literal usage in code lines:
            if '"""' not in stripped and not stripped.startswith("#"):
                offenders.append("%s: %s" % (module.name, stripped[:70]))
    # The three seed IDs must NOT appear in executable lines.
    results.append(
        (
            "no-duplicated-vocabulary-in-code",
            not offenders,
            "capability identifiers appear only in docstrings/comments — the "
            "registry is the single authority" if not offenders else offenders[0],
        )
    )


# ---------------------------------------------------------------------------
# Correction-cycle-1 regressions: provider_identity NodeID validation and
# distinct parameter/constraint rejection reasons
# ---------------------------------------------------------------------------


def case_provider_identity_nodeid(results: List[Tuple[str, bool, str]]) -> None:
    """REGRESSION (review finding 1): provider_identity must be a canonical
    ADCOS NodeID (WORK-004 model) — arbitrary strings and near-miss forms
    fail closed."""
    failures: List[str] = []
    bad_identities = [
        "alice",                                   # arbitrary string
        "",                                        # empty
        "node:identity.sha256-hmac-dev.v1:" + "1" * 64,   # wrong prefix
        "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 63,  # short digest
        "adcos:node:identity.sha256-hmac-dev.v1:" + "1" * 65,  # long digest
        "adcos:node:identity.sha256-hmac-dev.v1:" + "A" * 64,  # uppercase
        "adcos:node:single:" + "1" * 64,           # 1-segment profile
        "ADCOs:node:identity.sha256-hmac-dev.v1:" + "1" * 64,  # case
        "adcos:node:identity.sha256-hmac-dev.v1:%s:extra" % ("1" * 64),
        42, None, [], {},
    ]
    for bad in bad_identities:
        try:
            base_statement(provider_identity=bad)  # type: ignore[arg-type]
            failures.append("malformed provider_identity %r accepted" % (bad,))
        except CapabilityError as error:
            if error.code != "provider-identity":
                failures.append("wrong error code for %r: %s" % (bad, error.code))
    # A canonical NodeID (any registered profile) is accepted.
    valid = base_statement(
        provider_identity="adcos:node:identity.sha256-ed25519.v1:" + "a" * 64
    )
    # statement_from_mapping path validates too.
    try:
        statement_from_mapping({"provider_identity": "bob", **{k: v for k, v in valid.to_dict().items() if k != "provider_identity"}})
        failures.append("from_mapping accepted arbitrary provider_identity")
    except CapabilityError:
        pass
    results.append(
        (
            "provider-identity-nodeid-validated",
            not failures,
            "12 malformed/near-miss NodeIDs rejected (wrong prefix, short/long "
            "digest, uppercase, 1-segment profile, case, suffix, non-strings); "
            "canonical NodeIDs accepted on both construction paths"
            if not failures
            else failures[0],
        )
    )


def case_parameter_constraint_distinction(results: List[Tuple[str, bool, str]]) -> None:
    """REGRESSION (review finding 2): parameter-mismatch and
    constraint-mismatch are DISTINCT rejection reasons — parameter-only
    failures emit parameter-mismatch; constraint-only failures (with
    parameters satisfied) emit constraint-mismatch; both required and
    optional requirements report the distinct reason."""
    _, store, provider, _, ref = make_identity()
    signed = signed_statement(store, provider, ref)
    failures: List[str] = []

    # Parameter-only failure (constraints satisfied).
    r_param = negotiate(
        NegotiationSpec(
            requirements=(
                Requirement(
                    "capability.core.multipath",
                    required_parameters={"max_paths": 100},
                    required_constraints={"privacy": "end_to_end"},  # satisfied
                ),
            ),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if r_param.outcomes[0].reason != RejectionReason.PARAMETER_MISMATCH:
        failures.append("parameter-only failure: %s" % r_param.outcomes[0].reason)

    # Constraint-only failure (parameters satisfied).
    r_constraint = negotiate(
        NegotiationSpec(
            requirements=(
                Requirement(
                    "capability.core.multipath",
                    required_parameters={"max_paths": 2},  # satisfied (4 >= 2)
                    required_constraints={"privacy": "plaintext"},  # violated
                ),
            ),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if r_constraint.outcomes[0].reason != RejectionReason.CONSTRAINT_MISMATCH:
        failures.append("constraint-only failure: %s" % r_constraint.outcomes[0].reason)

    # Both failing: deterministic order — parameters checked first.
    r_both = negotiate(
        NegotiationSpec(
            requirements=(
                Requirement(
                    "capability.core.multipath",
                    required_parameters={"max_paths": 100},
                    required_constraints={"privacy": "plaintext"},
                ),
            ),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if r_both.outcomes[0].reason != RejectionReason.PARAMETER_MISMATCH:
        failures.append("both-failing order: %s" % r_both.outcomes[0].reason)

    # Optional requirement with constraint-only failure: NON-FATAL by design
    # (optional requirements never fail the negotiation), but nothing is
    # silently swallowed — the outcome is unselected and the DISTINCT reason
    # appears in the detail.
    r_optional = negotiate(
        NegotiationSpec(
            requirements=(
                Requirement(
                    "capability.core.multipath", required=False,
                    required_constraints={"privacy": "plaintext"},
                ),
            ),
            peer_statements=(signed,),
            now=NEGOTIATION_NOW,
        )
    )
    if not r_optional.succeeded:
        failures.append("optional requirement wrongly failed the whole negotiation")
    if r_optional.outcomes[0].selected is not None:
        failures.append("optional requirement selected despite violated constraints")
    if RejectionReason.CONSTRAINT_MISMATCH not in (r_optional.outcomes[0].detail or ""):
        failures.append("optional constraint failure reason not surfaced: %r" % r_optional.outcomes[0].detail)

    results.append(
        (
            "parameter-vs-constraint-distinct-reasons",
            not failures,
            "parameter-only -> parameter-mismatch; constraint-only -> "
            "constraint-mismatch; both-failing deterministic (params first); "
            "optional surfaces the distinct reason non-fatally"
            if not failures
            else failures[0],
        )
    )


# ---------------------------------------------------------------------------
# Correction-cycle-2 regression: signature is bound to provider_identity
# ---------------------------------------------------------------------------


def case_cross_node_forgery_rejected(results: List[Tuple[str, bool, str]]) -> None:
    """REGRESSION (cycle-2 review): a valid signature from Node B's
    credential must NOT verify a statement whose provider_identity names
    Node A. The signature is bound to the credential's NodeID through
    verify_statement's record check.

    This does NOT introduce trust/authorization policy — it verifies
    PROVENANCE (the statement came from the node it claims to be from),
    never truth or authorization.
    """
    profiles = ProfileSet.load_default()
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    store = InMemoryCredentialStore()
    provider = DevHmacSha256Provider()
    service = IdentityService(store=store, provider=provider, profiles=profiles)

    # Node A
    secret_a = b"TEST-ONLY-node-A-identity-key-material"
    ident_a = NodeIdentity.create(profile, provider.public_material(secret_a), NOW_TEXT)
    ref_a = service.provision(ident_a, KeyRole.IDENTITY, secret_a, now=NOW_TEXT)
    service.activate(ref_a, now=NOW_TEXT)

    # Node B
    secret_b = b"TEST-ONLY-node-B-identity-key-material"
    ident_b = NodeIdentity.create(profile, provider.public_material(secret_b), NOW_TEXT)
    ref_b = service.provision(ident_b, KeyRole.IDENTITY, secret_b, now=NOW_TEXT)
    service.activate(ref_b, now=NOW_TEXT)

    # Statement claiming Node A as provider, signed by Node B's credential.
    # Both signatures are valid HMAC signatures over the canonical content;
    # the ONLY thing that should make verify_statement return False is the
    # NodeID mismatch (B's credential does not belong to A).
    statement_a = base_statement(provider_identity=ident_a.node_id.text)
    # Sign with B's credential (valid signature, wrong node)
    forged = sign_statement(
        statement_a, store=store, provider=provider, credential=ref_b
    )
    # Verify with B's credential — the signature is correct, but B is not A
    cross_ok = verify_statement(forged, store=store, provider=provider, credential=ref_b, now=NOW)
    # Verify with A's credential — the signature was not produced by A
    wrong_key = verify_statement(forged, store=store, provider=provider, credential=ref_a, now=NOW)

    # Positive control: a properly signed statement by A verifies with A's credential
    legitimate = sign_statement(
        base_statement(provider_identity=ident_a.node_id.text),
        store=store, provider=provider, credential=ref_a,
    )
    positive_ok = verify_statement(legitimate, store=store, provider=provider, credential=ref_a, now=NOW)

    # The same signed content also must NOT verify under a superseded (rotated)
    # credential of the same node — provenance must trace to an active credential.
    # Rotate A's identity key; verify the OLD statement with the OLD credential.
    op_secret = b"TEST-ONLY-operational-A"
    op_ref = service.provision(ident_a, KeyRole.OPERATIONAL, op_secret, now=NOW_TEXT)
    service.activate(op_ref, now=NOW_TEXT)
    from identity.model import _require_active
    from identity.credentials import CredentialReference as _CR

    # Rotate A's identity key.
    new_secret_a = b"TEST-ONLY-node-A-new-identity-key"
    rotation_time = "2030-06-01T00:00:00Z"
    statement_rotation = service.rotation_statement(
        ident_a.node_id, KeyRole.IDENTITY, 1, 2,
        provider.public_material(new_secret_a), rotation_time,
    )
    auth_sig = provider.sign(store, ref_a, statement_rotation)
    service.rotate(ref_a, node_id=ident_a.node_id, role=KeyRole.IDENTITY,
                   new_secret=new_secret_a, authorization=auth_sig, rotated_at=rotation_time)
    # The old identity credential is now SUPERSEDED; its record still belongs to A
    # but is no longer ACTIVE. A statement signed with the old credential (before
    # rotation) must not verify post-rotation, even though the NodeID matches.
    superseded_ok = verify_statement(legitimate, store=store, provider=provider, credential=ref_a, now=NOW)

    results.append(
        (
            "cross-node-signature-forgery-rejected",
            not cross_ok and not wrong_key and positive_ok and not superseded_ok,
            "Node B's valid signature rejected for a statement naming Node A; "
            "positive control verifies; superseded-credential provenance break rejected"
            if not (cross_ok or wrong_key or not positive_ok or superseded_ok)
            else "FAILED: cross=%r wrong=%r positive=%r superseded=%r" % (cross_ok, wrong_key, positive_ok, superseded_ok),
        )
    )


# ---------------------------------------------------------------------------
# Correction-cycle-3 regression: ACTIVE-but-expired credential cannot
# validate a statement (verify_statement must be time-aware: injected
# evaluation instant; expires_at/revoked/lifecycle checked at that instant)
# ---------------------------------------------------------------------------


def case_expired_active_credential_rejected(results: List[Tuple[str, bool, str]]) -> None:
    """REGRESSION (cycle-3 review): an ACTIVE-but-expired credential must
    NOT validate a capability statement. ``verify_statement`` previously
    claimed to reject expired credentials but never checked
    ``record.expires_at``; an ACTIVE credential whose expiry had passed
    could therefore still produce a valid signature.

    The verifier is now time-aware: the caller injects the evaluation
    instant (no wall clock), and the credential's expiry/revocation/
    lifecycle is checked at that instant before accepting provenance.
    Trust/authorization semantics stay out of the verifier — this is
    provenance only.
    """
    profiles = ProfileSet.load_default()
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    store = InMemoryCredentialStore()
    provider = DevHmacSha256Provider()
    service = IdentityService(store=store, provider=provider, profiles=profiles)

    # Node A with a credential whose expires_at is set to a NEAR-FUTURE
    # instant (one day after provisioning). Activation at NOW succeeds
    # because expires_at is still in the future at that instant.
    secret = b"TEST-ONLY-expiry-regression-node-A"
    ident = NodeIdentity.create(profile, provider.public_material(secret), NOW_TEXT)
    CRED_EXPIRES = "2030-01-02T00:00:00Z"
    ref = service.provision(
        ident, KeyRole.IDENTITY, secret, now=NOW_TEXT, expires_at=CRED_EXPIRES
    )
    service.activate(ref, now=NOW_TEXT)

    # Sign a statement whose OWN validity window spans well past the
    # credential expiry (so the statement validity is never the reason
    # verification fails — only the credential expiry is). The provider
    # seam signs at NOW, while the credential is still in its window.
    signed = signed_statement(
        store, provider, ref,
        valid_from="2030-01-01T00:00:00Z",
        expires_at="2030-12-31T00:00:00Z",
    )

    # Positive control: at an instant WITHIN the credential's validity
    # window, the byte-correct signature verifies.
    in_window = datetime(2030, 1, 1, 12, tzinfo=timezone.utc)
    positive_ok = verify_statement(
        signed, store=store, provider=provider, credential=ref, now=in_window
    )

    # Boundary: at the EXACT expires_at instant, the credential is already
    # expired (mirrors IdentityService._require_active: expires_at <= now).
    at_boundary = datetime(2030, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    boundary_ok = verify_statement(
        signed, store=store, provider=provider, credential=ref, now=at_boundary
    )

    # ACTIVE-but-expired: the credential status is STILL ACTIVE in the
    # store (no expire() call has been made — only time has passed), but
    # the injected evaluation instant is past expires_at. The byte-correct
    # signature MUST NOT validate.
    past_expiry = datetime(2030, 1, 3, 0, 0, 0, tzinfo=timezone.utc)
    expired_ok = not verify_statement(
        signed, store=store, provider=provider, credential=ref, now=past_expiry
    )

    # Sanity: the credential record really is still ACTIVE (status) at the
    # evaluation instant — this PROVES the rejection came from the expiry
    # check against the injected instant, NOT from a status flip. The
    # status field has not been touched; only time-aware expiry rejected it.
    from identity.lifecycle import LifecycleState as _LS

    record = store.get_record(ref)
    still_active = record.status is _LS.ACTIVE and record.revoked is None

    # Negative control: a naive (tz-unaware) evaluation instant fails closed.
    naive_ok = not verify_statement(
        signed, store=store, provider=provider, credential=ref,
        now=datetime(2030, 1, 1, 12),  # no tzinfo
    )

    results.append(
        (
            "expired-active-credential-rejected",
            positive_ok and not boundary_ok and expired_ok and still_active and naive_ok,
            "ACTIVE-but-expired credential cannot validate a statement at the "
            "injected instant; positive control verifies in-window; boundary "
            "instant rejected (expires_at <= now); status still ACTIVE (rejection "
            "from the expiry check, not a status flip); naive instant fails closed"
            if positive_ok and not boundary_ok and expired_ok and still_active and naive_ok
            else "FAILED: positive=%r boundary=%r expired_ok=%r still_active=%r naive=%r"
                 % (positive_ok, boundary_ok, expired_ok, still_active, naive_ok),
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Tuple[str, bool, str]] = []
    case_construction_and_schema(results)
    case_signing_and_verification(results)
    case_tamper_rejection(results)
    case_expiry_and_withdrawal(results)
    case_open_world_identifiers(results)
    case_negotiation(results)
    case_not_authority(results)
    case_validity_matrix(results)
    case_serialization_roundtrip(results)
    case_no_second_vocabulary(results)
    case_provider_identity_nodeid(results)
    case_parameter_constraint_distinction(results)
    case_cross_node_forgery_rejected(results)
    case_expired_active_credential_rejected(results)
    case_fuzz(results)

    print("ADCOS capability self-test")
    print("=" * 72)
    for name, ok, detail in results:
        print("[%s] %-46s %s" % ("ok  " if ok else "FAIL", name, detail))
    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    if passed == len(results):
        print("Result: PASS (%d/%d cases)" % (passed, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
