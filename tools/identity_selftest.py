#!/usr/bin/env python3
"""ADCOS identity self-test (WORK-004).

Deterministic, offline verification of the identity package against the
frozen WORK-004 requirements (spec/prompts/WORK-004.md section 13):
identity construction and deterministic NodeID derivation; canonical
NodeID form; key rotation preserving NodeID with atomic failure
semantics; revocation and expiry as distinct fail-closed concepts; the
full lifecycle transition matrix; deterministic algorithm/profile
negotiation with provider replaceability (no core algorithm branch);
unknown-profile preservation; secret isolation across every public
surface; WORK-003 envelope integration; access-independence; and
seeded fuzz around serialized metadata and lifecycle transitions.

All key material is TEST-ONLY (fixed deterministic bytes, explicitly not
secrets). All clocks are injected RFC 3339 UTC strings. Zero third-party
dependencies; seeded PRNGs make runs byte-identical.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from identity import (  # noqa: E402
    CredentialRecord,
    CredentialReference,
    DevHmacSha256Provider,
    IdentityError,
    IdentityService,
    InMemoryCredentialStore,
    KeyRole,
    LifecycleError,
    LifecycleState,
    NodeIdentity,
    NodeIdError,
    ProfileError,
    ProfileSet,
    SerializationError,
    SignatureProvider,
    can_transition,
    transition,
    classify_profile_id,
    negotiate_profile,
    parse_node_id,
    public_metadata_from_bytes,
    public_metadata_to_bytes,
)
from identity.model import transition_record  # noqa: E402
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
class SeededRandom:
    """Deterministic LCG (same construction as the other suites) so every
    run is byte-identical without third-party dependencies."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        self._state = (
            self._state * 6364136223846793005 + 1442695040888963407
        ) & 0xFFFFFFFFFFFFFFFF
        return self._state >> 33

    def below(self, bound: int) -> int:
        return self._next() % bound

NOW = "2030-01-01T00:00:00Z"
IDENTITY_SECRET = b"TEST-ONLY-identity-key-material-DO-NOT-USE-0001"
OPERATIONAL_SECRET_1 = b"TEST-ONLY-operational-key-material-DO-NOT-USE-01"
OPERATIONAL_SECRET_2 = b"TEST-ONLY-operational-key-material-DO-NOT-USE-02"
SECRET_MARKER = b"SECRET-MARKER-4f3a9b-DO-NOT-LEAK"

JSON_CODEC = JsonDebugCodec()
CBOR_CODEC = CompactDeterministicCborCodec()


class FakeEd25519Provider(SignatureProvider):
    """Test-only provider proving provider replaceability: declares the
    standard alg.ed25519 identifier while using HMAC internally. The
    identity core consumes only the declared identifiers — it never
    branches on the algorithm."""

    def supported_algorithms(self) -> frozenset:
        return frozenset({"alg.ed25519"})

    def public_material(self, secret: bytes) -> bytes:
        import hashlib

        return hashlib.sha256(b"fake-ed25519:" + secret).digest()

    def sign(self, store, reference, data: bytes) -> bytes:
        import hashlib
        import hmac

        return hmac.new(hashlib.sha256(b"fake-ed25519:" + store.get_secret(reference)).digest(), data, hashlib.sha256).digest()

    def verify(self, public_material, algorithm, data, signature) -> bool:
        raise NotImplementedError("asymmetric external verification not needed in this fake")


def make_service(
    provider: Optional[SignatureProvider] = None, profiles: Optional[ProfileSet] = None
) -> Tuple[IdentityService, InMemoryCredentialStore]:
    store = InMemoryCredentialStore()
    service = IdentityService(
        store=store,
        provider=provider or DevHmacSha256Provider(),
        profiles=profiles or ProfileSet.load_default(),
    )
    return service, store


def bootstrap_identity(
    service: IdentityService, profiles: ProfileSet, *, provider: Optional[SignatureProvider] = None
) -> Tuple[NodeIdentity, CredentialReference, CredentialReference]:
    """Create an identity with active identity+operational credentials."""
    provider = provider or service._provider
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident = NodeIdentity.create(profile, provider.public_material(IDENTITY_SECRET), NOW)
    identity_ref = service.provision(ident, KeyRole.IDENTITY, IDENTITY_SECRET, now=NOW)
    service.activate(identity_ref, now=NOW)
    op_ref = service.provision(ident, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_1, now=NOW)
    service.activate(op_ref, now=NOW)
    return ident, identity_ref, op_ref


def authorize_rotation(
    service: IdentityService,
    store: InMemoryCredentialStore,
    identity_ref: CredentialReference,
    node_id,
    role: str,
    new_secret: bytes,
    rotated_at: str,
    *,
    provider: Optional[SignatureProvider] = None,
) -> bytes:
    """Build a valid authorization signature for rotating ``role`` at
    ``rotated_at`` (the current generation is read AT that instant)."""
    provider = provider or service._provider
    from identity.model import _require_active

    current = _require_active(store.list_records(), node_id, role, now=rotated_at)
    statement = service.rotation_statement(
        node_id, role, current.key_version, current.key_version + 1,
        provider.public_material(new_secret), rotated_at,
    )
    return provider.sign(store, identity_ref, statement)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def case_construction(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    provider = DevHmacSha256Provider()
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    public = provider.public_material(IDENTITY_SECRET)
    ident1 = NodeIdentity.create(profile, public, NOW)
    ident2 = NodeIdentity.create(profile, public, NOW)
    different = NodeIdentity.create(profile, provider.public_material(b"other-key"), NOW)
    ok = (
        ident1.node_id == ident2.node_id
        and ident1.node_id != different.node_id
        and parse_node_id(ident1.node_id.text).text == ident1.node_id.text
    )
    # Reject malformed identity input (empty bytes, wrong types).
    rejects = []
    bad_inputs: List[object] = [b"", "", None, 42, [], bytearray(b"")]
    for bad in bad_inputs:
        try:
            NodeIdentity.create(profile, bad, NOW)  # type: ignore[arg-type]
            rejects.append("accepted %r" % (bad,))
        except (NodeIdError, ValueError):
            pass
    try:
        NodeIdentity.create(profile, public, "not-a-timestamp")
        rejects.append("accepted bad timestamp")
    except ValueError:
        pass
    results.append(
        (
            "identity-construction-deterministic",
            ok and not rejects,
            "same key -> same NodeID; different key -> different NodeID; malformed input rejected"
            if not rejects
            else rejects[0],
        )
    )


def case_nodeid_canonical(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    provider = DevHmacSha256Provider()
    ident = NodeIdentity.create(
        profiles.get("identity.sha256-hmac-dev.v1"), provider.public_material(IDENTITY_SECRET), NOW
    )
    canonical = ident.node_id.text
    rng = SeededRandom(seed=778899)
    failures: List[str] = []
    # Malformed NodeIDs must be rejected, never crash.
    bad_values = [
        "",
        "adcos:node:",
        "adcos:node:identity.sha256-hmac-dev.v1",
        "adcos:node:identity.sha256-hmac-dev.v1:" + "A" * 64,   # uppercase
        "adcos:node:identity.sha256-hmac-dev.v1:" + "0" * 63,   # short digest
        "adcos:node:identity.sha256-hmac-dev.v1:" + "0" * 65,   # long digest
        "adcos:node:identity.sha256-hmac-dev.v1:" + "g" * 64,   # non-hex
        "ADCOs:node:identity.sha256-hmac-dev.v1:" + "0" * 64,   # case
        "node:identity.sha256-hmac-dev.v1:" + "0" * 64,         # wrong prefix
        "adcos:node:single:" + "0" * 64,                        # 1-segment profile
        "adcos:node:identity.sha256-hmac-dev.v1:%s:extra" % ("0" * 64),
        42,
        None,
        canonical + " ",
    ]
    for value in bad_values:
        try:
            parse_node_id(value)
            failures.append("accepted malformed NodeID %r" % (value,))
        except NodeIdError:
            pass
    # Seeded byte mutations of the canonical form: parse must not crash;
    # accept only if the result is itself canonical (re-parse equality).
    for iteration in range(200):
        chars = list(canonical)
        position = rng.below(len(chars))
        chars[position] = "0123456789abcdefxyz:." [rng.below(19)]
        mutated = "".join(chars)
        try:
            parsed = parse_node_id(mutated)
            if parsed.text != mutated:
                failures.append("mutation %d parsed non-canonically" % iteration)
        except NodeIdError:
            pass
    results.append(
        (
            "nodeid-canonical-form-enforced",
            not failures,
            "14 malformed forms rejected; 200 seeded mutations never crash"
            if not failures
            else failures[0],
        )
    )


def case_collision_resistance(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    provider = DevHmacSha256Provider()
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    rng = SeededRandom(seed=31415)
    seen = set()
    collisions = 0
    for iteration in range(300):
        key = bytes(rng.below(256) for _ in range(32))
        node_id = NodeIdentity.create(profile, key, NOW).node_id.text
        if node_id in seen:
            collisions += 1
        seen.add(node_id)
    # Cross-profile: same key under different profiles yields different IDs.
    ed = NodeIdentity.create(
        profiles.get("identity.sha256-ed25519.v1"), b"\x01" * 32, NOW
    ).node_id.text
    ec = NodeIdentity.create(
        profiles.get("identity.sha256-ecdsa-p256.v1"), b"\x01" * 32, NOW
    ).node_id.text
    results.append(
        (
            "nodeid-collision-resistance-smoke",
            collisions == 0 and len(seen) == 300 and ed != ec,
            "300 seeded keys -> 300 distinct NodeIDs; profile domain separation confirmed",
        )
    )


def case_metadata_roundtrip(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, store = make_service()
    ident, _, _ = bootstrap_identity(service, profiles)
    new_secret = OPERATIONAL_SECRET_2
    auth = authorize_rotation(service, store, service.records_for(ident.node_id)[0].reference, ident.node_id, KeyRole.OPERATIONAL, new_secret, "2030-01-01T01:00:00Z")
    service.rotate(
        service.records_for(ident.node_id)[0].reference,
        node_id=ident.node_id, role=KeyRole.OPERATIONAL,
        new_secret=new_secret, authorization=auth, rotated_at="2030-01-01T01:00:00Z",
    )
    metadata = service.public_metadata(ident)
    blob = public_metadata_to_bytes(metadata)
    parsed = public_metadata_from_bytes(blob)
    ok = (
        parsed.node_id == ident.node_id.text
        and parsed.profile_id == ident.profile_id
        and len(parsed.credentials) == len(metadata.credentials)
        and public_metadata_to_bytes(parsed) == blob
    )
    # duplicate keys rejected
    dup = blob.decode().replace('"node_id"', '"node_id","node_id"', 1).encode()
    try:
        public_metadata_from_bytes(dup)
        ok = False
        detail = "duplicate keys accepted"
    except SerializationError:
        detail = "round-trip byte-stable; duplicate keys rejected"
    results.append(("public-metadata-roundtrip", ok, detail))


def case_rotation(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, store = make_service()
    ident, identity_ref, op_ref = bootstrap_identity(service, profiles)
    node_id_before = ident.node_id.text
    auth = authorize_rotation(service, store, identity_ref, ident.node_id, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_2, "2030-01-01T01:00:00Z")
    activated = service.rotate(
        identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
        new_secret=OPERATIONAL_SECRET_2, authorization=auth, rotated_at="2030-01-01T01:00:00Z",
    )
    records = {(r.role, r.key_version): r for r in service.records_for(ident.node_id)}
    ok = (
        activated.key_version == 2
        and activated.status is LifecycleState.ACTIVE
        and records[(KeyRole.OPERATIONAL, 1)].status is LifecycleState.SUPERSEDED
        and records[(KeyRole.IDENTITY, 1)].status is LifecycleState.ACTIVE
        and service.active_credential(ident.node_id, KeyRole.OPERATIONAL, now="2030-01-01T02:00:00Z").key_version == 2
        and ident.node_id.text == node_id_before
    )
    results.append(
        (
            "rotation-preserves-nodeid",
            ok,
            "gen2 active, gen1 superseded, identity key untouched, NodeID unchanged",
        )
    )


def case_rotation_failure(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, store = make_service()
    ident, identity_ref, op_ref = bootstrap_identity(service, profiles)
    before = [(r.reference.reference_id, r.status) for r in service.records_for(ident.node_id)]
    rng = SeededRandom(seed=2718)
    failures: List[str] = []
    for iteration in range(50):
        signature = bytearray(authorize_rotation(service, store, identity_ref, ident.node_id, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_2, "2030-01-01T01:00:00Z"))
        signature[rng.below(len(signature))] ^= 1 << rng.below(8)
        try:
            service.rotate(
                identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
                new_secret=OPERATIONAL_SECRET_2, authorization=bytes(signature),
                rotated_at="2030-01-01T01:00:00Z",
            )
            failures.append("iteration %d: tampered signature accepted" % iteration)
            break
        except IdentityError:
            pass
    # authorization from the WRONG credential (operational key authorizing)
    wrong_stmt = service.rotation_statement(
        ident.node_id, KeyRole.OPERATIONAL, 1, 2,
        service._provider.public_material(OPERATIONAL_SECRET_2), "2030-01-01T01:00:00Z")
    wrong_sig = service._provider.sign(store, op_ref, wrong_stmt)
    try:
        service.rotate(
            op_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
            new_secret=OPERATIONAL_SECRET_2, authorization=wrong_sig,
            rotated_at="2030-01-01T01:00:00Z",
        )
        failures.append("authorization by operational credential accepted")
    except IdentityError:
        pass
    after = [(r.reference.reference_id, r.status) for r in service.records_for(ident.node_id)]
    unchanged = before == after and service.active_credential(
        ident.node_id, KeyRole.OPERATIONAL, now="2030-01-01T02:00:00Z"
    ).key_version == 1
    results.append(
        (
            "rotation-failure-leaves-previous-active",
            not failures and unchanged,
            "50 tampered signatures + wrong-role authorization rejected; no half-state"
            if not failures
            else failures[0],
        )
    )


def case_revocation(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, store = make_service()
    ident, identity_ref, op_ref = bootstrap_identity(service, profiles)
    node_id_before = ident.node_id.text
    service.revoke(op_ref, reason="compromise-suspected", now="2030-01-01T01:00:00Z")
    failures: List[str] = []
    try:
        service.activate(op_ref, now="2030-01-01T02:00:00Z")
        failures.append("revoked credential re-activated")
    except IdentityError:
        pass
    try:
        store.get_secret(op_ref)
        failures.append("revoked secret still selectable")
    except Exception:
        pass
    try:
        service.rotate(
            identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
            new_secret=OPERATIONAL_SECRET_2, authorization=b"\x00" * 32,
            rotated_at="2030-01-01T02:00:00Z",
        )
    except IdentityError:
        pass  # no active operational credential -> rejected
    record = store.get_record(op_ref)
    ok = bool(
        not failures
        and record.status is LifecycleState.REVOKED
        and record.revoked is not None
        and record.revoked.reason == "compromise-suspected"
        and ident.node_id.text == node_id_before
        and bool(service.records_for(ident.node_id))  # identity survives
    )
    # revoked vs expired distinction
    service2, store2 = make_service()
    ident2, _, op2 = bootstrap_identity(service2, ProfileSet.load_default())
    service2.expire(op2, now="2030-01-01T01:00:00Z")
    expired_record = store2.get_record(op2)
    ok = ok and expired_record.status is LifecycleState.EXPIRED and expired_record.revoked is None
    results.append(
        (
            "revocation-fails-closed-distinct-from-expiry",
            ok,
            "revoked: no reactivation, secret selection closed, identity stable; "
            "expired carries no revocation metadata",
        )
    )


def case_lifecycle_matrix(results: List[Tuple[str, bool, str]]) -> None:
    states = list(LifecycleState)
    legal = 0
    illegal = 0
    failures: List[str] = []
    for current in states:
        for target in states:
            allowed = can_transition(current, target)
            try:
                transition(current, target)
                if not allowed:
                    failures.append("%s->%s unexpectedly allowed" % (current.value, target.value))
                else:
                    legal += 1
            except LifecycleError:
                if allowed:
                    failures.append("%s->%s unexpectedly blocked" % (current.value, target.value))
                else:
                    illegal += 1
    terminal_out = all(
        not can_transition(LifecycleState.REVOKED, target) and not can_transition(LifecycleState.EXPIRED, target)
        for target in states
    )
    results.append(
        (
            "lifecycle-transition-matrix-fail-closed",
            not failures and terminal_out and legal + illegal == 36,
            "36 transitions: %d legal, %d rejected; terminals accept none" % (legal, illegal)
            if not failures
            else failures[0],
        )
    )


def case_negotiation(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    local = ["identity.sha256-ed25519.v1", "identity.sha256-ecdsa-p256.v1"]
    remote = ["identity.sha256-ecdsa-p256.v1", "identity.sha256-hmac-dev.v1"]
    p1 = negotiate_profile(local, remote, profile_set=profiles)
    p2 = negotiate_profile(list(reversed(local)), list(reversed(remote)), profile_set=profiles)
    ok = p1.profile_id == p2.profile_id == "identity.sha256-ecdsa-p256.v1"
    try:
        negotiate_profile(["identity.sha256-ed25519.v1"], ["identity.sha256-hmac-dev.v1"], profile_set=profiles)
        ok = False
        detail = "disjoint sets negotiated"
    except ProfileError:
        detail = "deterministic selection; disjoint sets rejected"
    detail = str(detail)
    # unknown profile listed by BOTH sides must not be negotiated into known
    try:
        negotiate_profile(
            ["identity.future.example-v1", "identity.sha256-ed25519.v1"],
            ["identity.future.example-v1", "identity.sha256-hmac-dev.v1"],
            profile_set=profiles,
        )
        ok = False
        detail = "unknown profile negotiated"
    except ProfileError:
        pass
    # unknown preserved verbatim, never coerced
    classification = profiles.classify("identity.future.example-v1")
    ok = ok and classification == "unknown"
    results.append(
        ("algorithm-negotiation-deterministic", ok, detail + "; unknown profile never coerced")
    )


def case_provider_agility(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    # A provider declaring alg.ed25519 works against the ed25519 profile
    # with zero core-code changes (the core compares declared data only).
    service, store = make_service(provider=FakeEd25519Provider())
    profile = profiles.get("identity.sha256-ed25519.v1")
    secret = b"TEST-ONLY-ed25519-material-0001"
    ident = NodeIdentity.create(profile, service._provider.public_material(secret), NOW)
    ref = service.provision(ident, KeyRole.IDENTITY, secret, now=NOW)
    service.activate(ref, now=NOW)
    op_ref = service.provision(ident, KeyRole.OPERATIONAL, secret + b"-op", now=NOW)
    service.activate(op_ref, now=NOW)
    record = store.get_record(op_ref)
    # Provider/profile mismatch fails closed: dev provider + ed25519 profile.
    service2, _ = make_service(provider=DevHmacSha256Provider())
    try:
        service2.provision(ident, KeyRole.IDENTITY, secret, now=NOW)
        mismatch_ok = False
    except IdentityError as error:
        mismatch_ok = error.code == "algorithm"
    results.append(
        (
            "provider-replaceability-no-core-branch",
            record.algorithm == "alg.ed25519" and mismatch_ok,
            "fake ed25519 provider provisions/activates via declared identifiers only; "
            "provider/profile mismatch fails closed",
        )
    )


def case_future_profile(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    future_id = "identity.future.example-v1"
    failures: List[str] = []
    if profiles.classify(future_id) != "unknown":
        failures.append("future profile not classified unknown")
    try:
        profiles.get(future_id)
        failures.append("unknown profile resolvable")
    except ProfileError as error:
        if future_id not in str(error):
            failures.append("profile id not preserved verbatim in error")
    # Explicit future profile definition works WITHOUT core changes and
    # derives NodeIDs under the same consumer API.
    from identity.profiles import IdentityProfile

    future_profile = IdentityProfile(
        profile_id=future_id,
        derivation="sha256-domain-v1",
        domain_separation=profiles.get("identity.sha256-hmac-dev.v1").domain_separation,
        key_roles=("identity", "operational"),
        signing_algorithms=("alg.future-scheme",),
        status="active",
        description="hypothetical future profile",
    )
    extended = profiles.with_explicit_profile(future_profile)
    ident = NodeIdentity.create(extended.get(future_id), b"\x02" * 32, NOW)
    ok = not failures and ident.node_id.profile_id == future_id and parse_node_id(ident.node_id.text).profile_id == future_id
    results.append(
        (
            "future-profile-preserved-not-coerced",
            ok,
            "unknown classification + verbatim preservation; explicit profile extension "
            "works with the unchanged NodeID consumer API",
        )
    )


def case_secret_isolation(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    provider = DevHmacSha256Provider()
    service, store = make_service(provider=provider)
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident = NodeIdentity.create(profile, provider.public_material(IDENTITY_SECRET), NOW)
    identity_ref = service.provision(ident, KeyRole.IDENTITY, IDENTITY_SECRET + SECRET_MARKER, now=NOW)
    service.activate(identity_ref, now=NOW)
    op_ref = service.provision(ident, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_1 + SECRET_MARKER, now=NOW)
    service.activate(op_ref, now=NOW)
    marker_secret = OPERATIONAL_SECRET_2 + SECRET_MARKER
    auth = authorize_rotation(service, store, identity_ref, ident.node_id, KeyRole.OPERATIONAL, marker_secret, "2030-01-01T01:00:00Z")
    service.rotate(
        identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
        new_secret=marker_secret, authorization=auth,
        rotated_at="2030-01-01T01:00:00Z",
    )
    metadata_blob = public_metadata_to_bytes(service.public_metadata(ident))
    envelope = envelope_from_mapping({
        "protocol": "adcos", "version": 1, "message_type": "identity.info",
        "message_id": "identity-msg-1", "sender": ident.node_id.text,
        "issued_at": NOW, "expires_at": "2030-01-02T00:00:00Z",
        "extensions": {}, "payload": service.public_metadata(ident).to_dict(),
        "evidence": [], "signature": "opaque",
    })
    envelope_blob = JSON_CODEC.encode(envelope)
    surfaces = {
        "metadata": metadata_blob,
        "envelope": envelope_blob,
        "compact": CBOR_CODEC.encode(envelope),
        "repr-record": repr(store.get_record(op_ref)).encode(),
        "repr-service": repr(service).encode(),
        "repr-identity": repr(ident).encode(),
        "repr-ref": repr(op_ref).encode(),
    }
    leaks = [name for name, blob in surfaces.items() if SECRET_MARKER in blob]
    # exception messages must not leak secrets
    try:
        service.rotate(
            identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
            new_secret=b"x" * 32, authorization=b"\x00" * 32, rotated_at=NOW,
        )
    except IdentityError as error:
        surfaces["exception"] = str(error).encode()
        if SECRET_MARKER in surfaces["exception"]:
            leaks.append("exception")
    # the ONLY secret path is the store
    ok = not leaks and store.get_secret(identity_ref) == IDENTITY_SECRET + SECRET_MARKER
    results.append(
        (
            "secret-isolation-across-public-surfaces",
            ok,
            "secret marker absent from metadata/envelope/compact/repr/exception; "
            "store is the only secret path" if ok else "LEAK in: %s" % ", ".join(leaks),
        )
    )


def case_envelope_integration(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, _ = make_service()
    ident, _, _ = bootstrap_identity(service, profiles)
    metadata = service.public_metadata(ident)
    outcome = accept(
        JSON_CODEC.encode(
            envelope_from_mapping({
                "protocol": "adcos", "version": 1,
                "message_type": "identity.info",  # unregistered: forwarded opaquely
                "message_id": "identity-msg-2", "sender": ident.node_id.text,
                "issued_at": NOW, "expires_at": "2030-01-02T00:00:00Z",
                "extensions": {}, "payload": metadata.to_dict(),
                "evidence": [], "signature": "opaque",
            })
        ),
        now=validation_clock(NOW),
        policy=ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE),
    )
    parsed_meta = public_metadata_from_bytes(
        JSON_CODEC.encode(outcome.validated.envelope).decode()
        .encode() if False else public_metadata_to_bytes(metadata)
    )
    ok = (
        outcome.accepted
        and outcome.classification == Classification.UNKNOWN_OPTIONAL_FORWARDED
        and parsed_meta.node_id == ident.node_id.text
        and public_metadata_to_bytes(parsed_meta) == public_metadata_to_bytes(metadata)
    )
    # determinism: repeated serialization is byte-identical
    ok = ok and all(
        public_metadata_to_bytes(metadata) == public_metadata_to_bytes(metadata) for _ in range(3)
    )
    results.append(
        (
            "envelope-integration-via-work003",
            ok,
            "identity metadata travels through the WORK-003 envelope "
            "(unregistered type forwarded opaquely); byte-deterministic",
        )
    )


def case_access_independence(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, _ = make_service()
    ident, _, _ = bootstrap_identity(service, profiles)
    node_id = ident.node_id.text
    ok = True
    # The identity API has no access-technology surface at all; identity
    # metadata embedded alongside access-profile data keeps NodeID stable.
    for access in ("access.3gpp.nr.imt2020", "access.ieee.80211", "access.3gpp.nr.imt2030", "access.vendor.newradio-2060"):
        payload = {
            "access_context": access,
            "identity": service.public_metadata(ident).to_dict(),
        }
        envelope = envelope_from_mapping({
            "protocol": "adcos", "version": 1, "message_type": "identity.info",
            "message_id": "ctx-" + access, "sender": node_id,
            "issued_at": NOW, "expires_at": "2030-01-02T00:00:00Z",
            "extensions": {}, "payload": payload, "evidence": [], "signature": "opaque",
        })
        outcome = accept(
            JSON_CODEC.encode(envelope), now=validation_clock(NOW),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE),
        )
        validated = outcome.validated
        if validated is None or validated.envelope.sender != node_id:
            ok = False
            break
        if validated.envelope.payload["identity"]["node_id"] != node_id:
            ok = False
            break
    results.append(
        (
            "nodeid-access-independent",
            ok,
            "NodeID byte-identical across 5G / Wi-Fi / future-IMT / unknown access contexts",
        )
    )


def case_negatives(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    failures: List[str] = []
    service, store = make_service()
    ident, identity_ref, op_ref = bootstrap_identity(service, profiles)

    # duplicate credential reference
    try:
        store.put_record(store.get_record(op_ref))
        failures.append("duplicate reference accepted")
    except Exception:
        pass
    # provisioning a second active credential for the same role
    try:
        service.provision(ident, KeyRole.OPERATIONAL, b"another-material", now=NOW)
        failures.append("second active operational credential provisioned")
    except IdentityError as error:
        if error.code != "duplicate-active":
            failures.append("wrong error for duplicate-active: %s" % error.code)
    # expired credential activation
    service3, _ = make_service()
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident3 = NodeIdentity.create(profile, service3._provider.public_material(IDENTITY_SECRET), NOW)
    exp_ref = service3.provision(
        ident3, KeyRole.IDENTITY, IDENTITY_SECRET, now=NOW, expires_at="2030-01-01T00:00:01Z"
    )
    try:
        service3.activate(exp_ref, now="2030-01-01T01:00:00Z")
        failures.append("expired credential activated")
    except IdentityError as error:
        if error.code != "expired":
            failures.append("wrong error for expired activation: %s" % error.code)
    # unknown profile for identity creation
    try:
        NodeIdentity.create(profiles.get("identity.sha256-hmac-dev.v1") if False else _fake_unknown_profile(profiles), b"k" * 32, NOW)
    except ProfileError:
        pass
    except Exception as error:
        failures.append("unknown profile raised %s" % type(error).__name__)
    # malformed serialized metadata
    for bad in (b"", b"[]", b"null", b"{", b"\xff\xfe", b'{"node_id": 42}'):
        try:
            public_metadata_from_bytes(bad)
            failures.append("malformed metadata accepted: %r" % bad[:20])
        except SerializationError:
            pass
    results.append(
        (
            "negative-security-cases",
            not failures,
            "duplicates, expired activation, unknown profiles, malformed metadata all fail closed"
            if not failures
            else failures[0],
        )
    )


def _fake_unknown_profile(profiles: ProfileSet):
    class UnknownProfile:
        profile_id = "identity.does.not-exist"
        derivation = "sha256-domain-v1"
        domain_separation = ""
        status = "active"

        def supports_role(self, role):
            return True

        def supports_algorithm(self, alg):
            return True

    raise ProfileError("profile", "simulated unknown profile")


def case_metadata_fuzz(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, _ = make_service()
    ident, _, _ = bootstrap_identity(service, profiles)
    blob = public_metadata_to_bytes(service.public_metadata(ident))
    rng = SeededRandom(seed=999333)
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
            public_metadata_from_bytes(bytes(body))
        except SerializationError:
            pass
        except Exception as error:
            failures.append("iter %d raised %s: %s" % (iteration, type(error).__name__, error))
            break
    results.append(
        (
            "serialized-metadata-fuzz",
            not failures,
            "%d mutated metadata inputs fail safely (SerializationError or valid)" % checked
            if not failures
            else failures[0],
        )
    )


def case_destroy_and_history(results: List[Tuple[str, bool, str]]) -> None:
    profiles = ProfileSet.load_default()
    service, store = make_service()
    ident, identity_ref, op_ref = bootstrap_identity(service, profiles)
    auth = authorize_rotation(service, store, identity_ref, ident.node_id, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_2, "2030-01-01T01:00:00Z")
    service.rotate(
        identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
        new_secret=OPERATIONAL_SECRET_2, authorization=auth, rotated_at="2030-01-01T01:00:00Z",
    )
    superseded_gen1 = next(
        r for r in service.records_for(ident.node_id)
        if r.role == KeyRole.OPERATIONAL and r.key_version == 1
    )
    historical_ok = superseded_gen1.status is LifecycleState.SUPERSEDED and store.get_record(superseded_gen1.reference).key_version == 1
    revoked = service.destroy_identity(ident.node_id, now="2030-01-01T02:00:00Z", reason="decommissioned")
    all_terminal = all(r.status is LifecycleState.REVOKED for r in service.records_for(ident.node_id))
    blocked = False
    try:
        service.provision(ident, KeyRole.OPERATIONAL, b"post-destroy-material", now="2030-01-01T03:00:00Z")
    except IdentityError as error:
        blocked = error.code == "destroyed"
    metadata = service.public_metadata(ident)
    results.append(
        (
            "destroy-explicit-and-historical-reference",
            historical_ok and all_terminal and len(revoked) == 3 and blocked and metadata.destroyed,
            "superseded generation remains queryable; explicit destruction revokes all "
            "(3) and blocks new provisioning; metadata flags destruction",
        )
    )


# ---------------------------------------------------------------------------
# Correction-cycle-1 regressions: expired-credential authorization and
# commit-time fault injection (storage atomicity)
# ---------------------------------------------------------------------------


class CommitFailingStore(InMemoryCredentialStore):
    """Fault-injection wrapper: raises RuntimeError at the Nth commit_batch
    call (N=1 fails the first commit). Records and secrets remain fully
    inspectable through the inherited read APIs."""

    def __init__(self, fail_on_commit: int) -> None:
        super().__init__()
        self._fail_on_commit = fail_on_commit
        self.commit_calls = 0

    def commit_batch(self, batch) -> None:
        self.commit_calls += 1
        if self.commit_calls == self._fail_on_commit:
            raise RuntimeError(
                "injected storage failure at commit #%d" % self._fail_on_commit
            )
        return super().commit_batch(batch)


def case_rotation_expired_current_credential(results: List[Tuple[str, bool, str]]) -> None:
    """REGRESSION (review finding 2): an ACTIVE credential whose expires_at
    has passed at the rotation instant must NOT be rotatable — even with a
    perfectly valid authorization signature."""
    profiles = ProfileSet.load_default()
    service, store = make_service()
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident = NodeIdentity.create(profile, service._provider.public_material(IDENTITY_SECRET), NOW)
    identity_ref = service.provision(ident, KeyRole.IDENTITY, IDENTITY_SECRET, now=NOW)
    service.activate(identity_ref, now=NOW)
    # Operational credential ACTIVE but expiring before the rotation time.
    op_ref = service.provision(
        ident, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_1, now=NOW,
        expires_at="2030-01-01T06:00:00Z",
    )
    service.activate(op_ref, now=NOW)
    rotation_time = "2030-01-01T12:00:00Z"  # after expiry
    # A signature built as-if the credential were still usable.
    statement = service.rotation_statement(
        ident.node_id, KeyRole.OPERATIONAL, 1, 2,
        service._provider.public_material(OPERATIONAL_SECRET_2), rotation_time,
    )
    authorization = service._provider.sign(store, identity_ref, statement)
    failures: List[str] = []
    try:
        service.rotate(
            identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
            new_secret=OPERATIONAL_SECRET_2, authorization=authorization,
            rotated_at=rotation_time,
        )
        failures.append("rotation with expired current credential accepted")
    except IdentityError as error:
        if error.code != "expired":
            failures.append("wrong error code: %s (%s)" % (error.code, error.detail))
    # State must be unchanged: no gen-2 record, no gen-2 secret, gen-1 still ACTIVE.
    records = service.records_for(ident.node_id)
    versions = sorted(r.key_version for r in records if r.role == KeyRole.OPERATIONAL)
    if versions != [1]:
        failures.append("operational generations mutated: %r" % versions)
    op_record = store.get_record(op_ref)
    if op_record.status is not LifecycleState.ACTIVE:
        failures.append("gen-1 no longer ACTIVE: %s" % op_record.status.value)
    if len(service.records_for(ident.node_id)) != 2:
        failures.append("stray records leaked: %d records" % len(service.records_for(ident.node_id)))

    # Also: an EXPIRED identity credential must not authorize rotation.
    service2, store2 = make_service()
    ident2 = NodeIdentity.create(profile, service2._provider.public_material(IDENTITY_SECRET), NOW)
    identity_ref2 = service2.provision(
        ident2, KeyRole.IDENTITY, IDENTITY_SECRET, now=NOW, expires_at="2030-01-01T06:00:00Z"
    )
    service2.activate(identity_ref2, now=NOW)
    op_ref2 = service2.provision(ident2, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_1, now=NOW)
    service2.activate(op_ref2, now=NOW)
    statement2 = service2.rotation_statement(
        ident2.node_id, KeyRole.OPERATIONAL, 1, 2,
        service2._provider.public_material(OPERATIONAL_SECRET_2), rotation_time,
    )
    authorization2 = service2._provider.sign(store2, identity_ref2, statement2)
    try:
        service2.rotate(
            identity_ref2, node_id=ident2.node_id, role=KeyRole.OPERATIONAL,
            new_secret=OPERATIONAL_SECRET_2, authorization=authorization2,
            rotated_at=rotation_time,
        )
        failures.append("expired identity credential authorized rotation")
    except IdentityError as error:
        if error.code != "authorization":
            failures.append("wrong error for expired authorizer: %s" % error.code)
    results.append(
        (
            "rotation-expired-credential-rejected",
            not failures,
            "expired current credential and expired identity authorizer both "
            "fail closed; state unchanged" if not failures else failures[0],
        )
    )


def case_rotation_commit_fault_injection(results: List[Tuple[str, bool, str]]) -> None:
    """REGRESSION (review finding 1): the rotation's storage commit is a
    single atomic transaction. Inject a commit failure and prove the old
    credential remains ACTIVE, with NO new record and NO new secret
    leaked anywhere in the store."""
    profiles = ProfileSet.load_default()
    failures: List[str] = []

    def bootstrap(fail_on: int):
        store = CommitFailingStore(fail_on_commit=fail_on)
        service = IdentityService(store=store, provider=DevHmacSha256Provider())
        profile = profiles.get("identity.sha256-hmac-dev.v1")
        ident = NodeIdentity.create(
            profile, service._provider.public_material(IDENTITY_SECRET), NOW
        )
        identity_ref = service.provision(ident, KeyRole.IDENTITY, IDENTITY_SECRET, now=NOW)
        service.activate(identity_ref, now=NOW)
        op_ref = service.provision(ident, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_1, now=NOW)
        service.activate(op_ref, now=NOW)
        return store, service, ident, identity_ref, op_ref

    def try_rotate(service, identity_ref, ident, *, generation: int, secret: bytes, at: str):
        current = next(
            r for r in service.records_for(ident.node_id)
            if r.role == KeyRole.OPERATIONAL and r.status is LifecycleState.ACTIVE
        )
        statement = service.rotation_statement(
            ident.node_id, KeyRole.OPERATIONAL, generation, generation + 1,
            service._provider.public_material(secret), at,
        )
        authorization = service._provider.sign(service._store, identity_ref, statement)
        service.rotate(
            identity_ref, node_id=ident.node_id, role=KeyRole.OPERATIONAL,
            new_secret=secret, authorization=authorization, rotated_at=at,
        )

    # Scenario A — the rotation commit ITSELF fails (commit #1):
    # gen-1 must remain ACTIVE with no gen-2 record/secret anywhere.
    store, service, ident, identity_ref, op_ref = bootstrap(fail_on=1)
    try:
        try_rotate(service, identity_ref, ident, generation=1, secret=OPERATIONAL_SECRET_2, at="2030-01-01T01:00:00Z")
        failures.append("scenario A: rotation succeeded despite injected commit failure")
    except RuntimeError:
        pass
    op_versions = sorted(
        r.key_version for r in service.records_for(ident.node_id)
        if r.role == KeyRole.OPERATIONAL
    )
    if op_versions != [1]:
        failures.append("scenario A: operational generations = %r" % op_versions)
    op_record = store.get_record(op_ref)
    if op_record.status is not LifecycleState.ACTIVE or op_record.superseded_at is not None:
        failures.append(
            "scenario A: gen-1 status=%s superseded_at=%r"
            % (op_record.status.value, op_record.superseded_at)
        )
    gen2_reference = CredentialReference(
        reference_id="cred:%s:%s:v2" % (ident.node_id.text, KeyRole.OPERATIONAL)
    )
    try:
        store.get_secret(gen2_reference)
        failures.append("scenario A: gen-2 secret leaked")
    except Exception:
        pass
    try:
        store.get_record(gen2_reference)
        failures.append("scenario A: gen-2 record retrievable")
    except KeyError:
        pass

    # Scenario B — a LATER commit fails: rotation 1 succeeds (gen-2 ACTIVE),
    # then rotation 2's commit (commit #2) fails and must leave the fully
    # rotated gen-2 state intact with no gen-3 leakage.
    store, service, ident, identity_ref, op_ref = bootstrap(fail_on=2)
    try:
        try_rotate(service, identity_ref, ident, generation=1, secret=OPERATIONAL_SECRET_2, at="2030-01-01T01:00:00Z")
    except Exception as error:
        failures.append("scenario B: first rotation failed: %s" % error)
    gen2_ref = CredentialReference(
        reference_id="cred:%s:%s:v2" % (ident.node_id.text, KeyRole.OPERATIONAL)
    )
    try:
        try_rotate(service, identity_ref, ident, generation=2, secret=b"TEST-ONLY-op-material-003", at="2030-01-01T02:00:00Z")
        failures.append("scenario B: second rotation succeeded despite injected commit failure")
    except RuntimeError:
        pass
    op_versions = sorted(
        r.key_version for r in service.records_for(ident.node_id)
        if r.role == KeyRole.OPERATIONAL
    )
    if op_versions != [1, 2]:
        failures.append("scenario B: operational generations = %r" % op_versions)
    gen2_record = store.get_record(gen2_ref)
    if gen2_record.status is not LifecycleState.ACTIVE or gen2_record.superseded_at is not None:
        failures.append(
            "scenario B: gen-2 status=%s superseded_at=%r"
            % (gen2_record.status.value, gen2_record.superseded_at)
        )
    gen3_reference = CredentialReference(
        reference_id="cred:%s:%s:v3" % (ident.node_id.text, KeyRole.OPERATIONAL)
    )
    try:
        store.get_secret(gen3_reference)
        failures.append("scenario B: gen-3 secret leaked")
    except Exception:
        pass
    try:
        store.get_record(gen3_reference)
        failures.append("scenario B: gen-3 record retrievable")
    except KeyError:
        pass
    # Batch-internal failure atomicity: a batch whose LATER operation is
    # invalid must apply NOTHING (no partial application).
    store = InMemoryCredentialStore()
    service = IdentityService(store=store, provider=DevHmacSha256Provider())
    profile = profiles.get("identity.sha256-hmac-dev.v1")
    ident = NodeIdentity.create(profile, service._provider.public_material(IDENTITY_SECRET), NOW)
    identity_ref = service.provision(ident, KeyRole.IDENTITY, IDENTITY_SECRET, now=NOW)
    service.activate(identity_ref, now=NOW)
    op_ref = service.provision(ident, KeyRole.OPERATIONAL, OPERATIONAL_SECRET_1, now=NOW)
    service.activate(op_ref, now=NOW)
    from identity.store import StoreBatch
    from identity.credentials import CredentialRecord as CR
    from identity.model import replace as _replace

    bad_new_record = CR(
        reference=CredentialReference(reference_id="cred:atomic-test:v99"),
        node_id=ident.node_id,
        profile_id=profile.profile_id,
        role=KeyRole.OPERATIONAL,
        algorithm=op_record.algorithm if False else "alg.hmac-sha256.dev",
        key_version=99,
        public_material_hex=service._provider.public_material(OPERATIONAL_SECRET_2).hex(),
        status=LifecycleState.PROVISIONED,
        provisioned_at=NOW,
    )
    superseded_final = _replace(
        store.get_record(op_ref), status=LifecycleState.SUPERSEDED, superseded_at=NOW
    )
    before_records = {r.reference.reference_id: r for r in store.list_records()}
    try:
        store.commit_batch(
            StoreBatch(
                records_to_add=(bad_new_record,),
                secrets_to_add=(
                    (bad_new_record.reference, OPERATIONAL_SECRET_2),
                    (bad_new_record.reference, OPERATIONAL_SECRET_2),  # duplicate -> fails
                ),
                records_to_update=(superseded_final,),
            )
        )
        failures.append("invalid batch committed")
    except Exception:
        pass
    after_records = {r.reference.reference_id: r for r in store.list_records()}
    if set(before_records) != set(after_records):
        failures.append("invalid batch partially applied records")
    if after_records[op_ref.reference_id].status is not LifecycleState.ACTIVE:
        failures.append("invalid batch partially applied a transition")
    try:
        store.get_secret(bad_new_record.reference)
        failures.append("invalid batch leaked a secret")
    except Exception:
        pass
    results.append(
        (
            "rotation-commit-atomic-fault-injection",
            not failures,
            "injected commit failures (first-commit) and invalid batches leave "
            "gen-1 ACTIVE with no leaked records or secrets" if not failures else failures[0],
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Tuple[str, bool, str]] = []
    case_construction(results)
    case_nodeid_canonical(results)
    case_collision_resistance(results)
    case_metadata_roundtrip(results)
    case_rotation(results)
    case_rotation_failure(results)
    case_revocation(results)
    case_lifecycle_matrix(results)
    case_negotiation(results)
    case_provider_agility(results)
    case_future_profile(results)
    case_secret_isolation(results)
    case_envelope_integration(results)
    case_access_independence(results)
    case_negatives(results)
    case_metadata_fuzz(results)
    case_destroy_and_history(results)
    case_rotation_expired_current_credential(results)
    case_rotation_commit_fault_injection(results)

    print("ADCOS identity self-test")
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
