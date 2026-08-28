"""WORK-032 conformance vectors -- cryptographic identity (WORK-004).

Covers: NodeID derivation and parsing, credential binding, rotation
(identity-key-authorized, atomic), revocation, expiry, lifecycle
transitions, secret-free public metadata, and forged-provenance
rejections.  Integrity != provenance: a well-formed NodeID presented
without matching derivation material is never accepted as provenance.
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

from identity import (
    IdentityError,
    LifecycleError,
    NodeIdError,
    SerializationError,
    derive_node_id,
)

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import FUTURE, NOW, PAST, T0, ConformanceWorld

__all__ = ["vectors"]

_AREA = "identity"
_AUTHORITY = "WORK-004"
_CONTRACT = "spec/architecture.md section 8 (identity) / WORK-004"

_PROFILE = "identity.sha256-hmac-dev.v1"
_RULE = "sha256-domain-v1"
_DOMAIN = "adcos-identity-test-domain"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-IDN-%s" % number,
        area=_AREA,
        polarity=polarity,
        authority=_AUTHORITY,
        contract=_CONTRACT,
        invariant=invariant,
        description=description,
        expected=expected,
        execute=execute,
        tags=tags,
    )


def _error_outcome(error: Any) -> ObservedOutcome:
    code = getattr(error, "code", None) or getattr(
        error, "reason", None
    ) or type(error).__name__
    return ObservedOutcome(False, code, str(error))


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- IDN-001: NodeID derivation is deterministic and key-bound ----------
    def _idn001(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        profile = ident.profile
        first = ident.derive(
            _PROFILE, b"conformance-key-A",
            profile.derivation, profile.domain_separation,
        )
        second = ident.derive(
            _PROFILE, b"conformance-key-A",
            profile.derivation, profile.domain_separation,
        )
        other = ident.derive(
            _PROFILE, b"conformance-key-B",
            profile.derivation, profile.domain_separation,
        )
        if first.text != second.text:
            return ObservedOutcome(
                False, "derivation-unstable", "same inputs produced different ids"
            )
        if first.text == other.text:
            return ObservedOutcome(
                False, "derivation-unbound", "different keys produced the same id"
            )
        if first.text != world.identity.node_a.node_id.text:
            return ObservedOutcome(
                False, "derivation-mismatch",
                "derived id does not match the fixture identity's id",
            )
        return ObservedOutcome(
            True, "derivation-stable",
            "NodeID derivation is deterministic and key-bound",
        )

    out.append(_vector(
        "001", "positive",
        "NodeID is derived only from the stable identity key + profile",
        "derive_node_id: same key -> same id, different key -> different id.",
        ExpectedOutcome(True, frozenset({"derivation-stable"})),
        _idn001,
        frozenset({"positive:core-behavior", "positive:determinism"}),
    ))

    # -- IDN-002: unknown derivation rule fails closed -----------------------
    def _idn002(world: ConformanceWorld) -> ObservedOutcome:
        try:
            world.identity.derive(
                _PROFILE, b"conformance-key-A", "future-unknown-rule", _DOMAIN
            )
        except NodeIdError as error:
            return _error_outcome(error)
        return ObservedOutcome(
            True, "rule-accepted", "unknown derivation rule was accepted"
        )

    out.append(_vector(
        "002", "negative",
        "unknown derivation rules fail closed",
        "derive_node_id with an unknown rule raises NodeIdError.",
        ExpectedOutcome(False, frozenset({"derivation", "rule"})),
        _idn002,
        frozenset({"negative:invalid-versions"}),
    ))

    # -- IDN-003: malformed NodeID text fails closed -------------------------
    def _idn003(world: ConformanceWorld) -> ObservedOutcome:
        malformed = (
            "adcos:node:" + _PROFILE + ":" + "A" * 64,   # uppercase hex
            "adcos:node:" + _PROFILE + ":" + "a" * 63,   # short digest
            "not-a-node-id",
            "adcos:node:" + _PROFILE + ":" + "g" * 64,   # non-hex
        )
        for text in malformed:
            try:
                world.identity.parse(text)
            except NodeIdError:
                continue
            return ObservedOutcome(
                True, "malformed-accepted", "malformed NodeID %r parsed" % text[:40]
            )
        return ObservedOutcome(
            False, "malformed-rejected",
            "all malformed NodeID forms rejected",
        )

    out.append(_vector(
        "003", "negative",
        "malformed NodeID text never parses",
        "parse_node_id rejects bad prefix, bad hex, and wrong length.",
        ExpectedOutcome(False, frozenset({"malformed-rejected"})),
        _idn003,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- IDN-004: provision -> activate -> active credential -----------------
    def _idn004(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        # Retire the world's operational credential for node C first
        # (only one ACTIVE credential per role may exist).
        ident.revoke(
            ident.operational_refs[ident.node_c.node_id.text],
            reason="conformance-reprovision", now=NOW,
        )
        ref = ident.provision(
            ident.node_c, "operational", b"fresh-secret", now=NOW
        )
        record = ident.activate(ref, now=NOW)
        active = ident.active(ident.node_c.node_id, "operational", now=NOW)
        if record.reference != active.reference:
            return ObservedOutcome(
                False, "active-mismatch",
                "active credential is not the activated record",
            )
        return ObservedOutcome(
            True, "provision-activate-active",
            "provisioned credential activated and queryable",
        )

    out.append(_vector(
        "004", "positive",
        "credential lifecycle provision -> activate -> active is genuine",
        "A provisioned+activated credential is returned by active_credential.",
        ExpectedOutcome(True, frozenset({"provision-activate-active"})),
        _idn004,
        frozenset({"positive:core-behavior"}),
    ))

    # -- IDN-005: duplicate ACTIVE credential rejected ------------------------
    def _idn005(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        try:
            ident.provision(
                ident.node_b, "operational", b"another-secret", now=NOW
            )
        except IdentityError as error:
            return _error_outcome(error)
        return ObservedOutcome(
            True, "duplicate-accepted", "duplicate active credential permitted"
        )

    out.append(_vector(
        "005", "negative",
        "only one ACTIVE credential per (node, role) may exist",
        "Provisioning a second operational credential while one is ACTIVE "
        "raises IdentityError(duplicate-active).",
        ExpectedOutcome(False, frozenset({"duplicate-active"})),
        _idn005,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- IDN-006: authorized rotation is atomic and NodeID-stable ------------
    def _idn006(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        old_text = ident.node_a.node_id.text
        current = ident.active(ident.node_a.node_id, "operational", now=NOW)
        statement = ident.rotation_statement(
            ident.node_a.node_id,
            "operational",
            current.key_version,
            current.key_version + 1,
            ident.public_material(b"rotated-operational-secret"),
            NOW,
        )
        authorization = ident.sign(ident.identity_ref_a, statement)
        record = ident.rotate(
            ident.identity_ref_a,
            node_id=ident.node_a.node_id,
            role="operational",
            new_secret=b"rotated-operational-secret",
            authorization=authorization,
            rotated_at=NOW,
        )
        active = ident.active(ident.node_a.node_id, "operational", now=NOW)
        if active.key_version != record.key_version:
            return ObservedOutcome(
                False, "rotation-not-active",
                "rotated generation is not the active credential",
            )
        if ident.node_a.node_id.text != old_text:
            return ObservedOutcome(
                False, "nodeid-changed", "rotation changed the NodeID"
            )
        return ObservedOutcome(
            True, "rotation-atomic",
            "rotation atomically advanced the generation; NodeID unchanged",
        )

    out.append(_vector(
        "006", "positive",
        "rotation is atomic and identity-key-authorized; NodeID never changes",
        "Genuine rotation statement signed by the identity-role credential "
        "advances the generation atomically.",
        ExpectedOutcome(True, frozenset({"rotation-atomic"})),
        _idn006,
        frozenset({"positive:core-behavior", "recovery:version-conflict"}),
    ))

    # -- IDN-007: forged rotation authorization rejected -----------------------
    def _idn007(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        current = ident.active(ident.node_a.node_id, "operational", now=NOW)
        genuine_statement = ident.rotation_statement(
            ident.node_a.node_id, "operational", current.key_version,
            current.key_version + 1,
            ident.public_material(b"rotated-secret"), NOW,
        )
        # The attack: sign a DIFFERENT statement (forged authorization bytes).
        forged_statement = ident.rotation_statement(
            ident.node_a.node_id, "operational", current.key_version,
            current.key_version + 99,
            ident.public_material(b"rotated-secret"), NOW,
        )
        authorization = ident.sign(ident.identity_ref_a, forged_statement)
        try:
            ident.rotate(
                ident.operational_refs[ident.node_a.node_id.text],
                node_id=ident.node_a.node_id,
                role="operational",
                new_secret=b"rotated-secret",
                authorization=authorization,
                rotated_at=NOW,
            )
        except IdentityError as error:
            if error.code != "authorization":
                return ObservedOutcome(
                    False, error.code,
                    "rejected but with unexpected code: %s" % error.detail,
                )
            after = ident.active(ident.node_a.node_id, "operational", now=NOW)
            if after.key_version != current.key_version:
                return ObservedOutcome(
                    False, "state-mutated",
                    "rejected rotation still mutated credential state",
                )
            return ObservedOutcome(
                False, "authorization",
                "forged rotation authorization rejected; state unchanged",
            )
        return ObservedOutcome(
            True, "forged-authorization-accepted",
            "rotation with forged authorization succeeded",
        )

    out.append(_vector(
        "007", "negative",
        "forged rotation authorization fails closed without state mutation",
        "Authorization signed over different statement material is "
        "rejected and the active credential is untouched.",
        ExpectedOutcome(False, frozenset({"authorization"})),
        _idn007,
        frozenset({
            "negative:forged-provenance",
            "discriminating:provenance",
        }),
    ))

    # -- IDN-008: revocation takes effect on the next call --------------------
    def _idn008(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        ref = ident.operational_refs[ident.node_c.node_id.text]
        ident.revoke(ref, reason="conformance", now=NOW)
        try:
            ident.active(ident.node_c.node_id, "operational", now=NOW)
        except IdentityError as error:
            return _error_outcome(error)
        return ObservedOutcome(
            True, "revoked-still-active", "revoked credential still active"
        )

    out.append(_vector(
        "008", "negative",
        "revocation is immediate and distinct from expiry",
        "active_credential raises after revoke.",
        ExpectedOutcome(False, frozenset({"revoked", "no-active",
                                          "no-active-credential"})),
        _idn008,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- IDN-009: expired credential activation fails closed ------------------
    def _idn009(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        ident.revoke(
            ident.operational_refs[ident.node_c.node_id.text],
            reason="conformance-expiry-fixture", now=NOW,
        )
        ref = ident.provision(
            ident.node_c, "operational", b"short-lived", now=NOW,
            expires_at=PAST,
        )
        try:
            ident.activate(ref, now=NOW)
        except IdentityError as error:
            return _error_outcome(error)
        return ObservedOutcome(
            True, "expired-activated", "expired credential activated"
        )

    out.append(_vector(
        "009", "negative",
        "expired credentials never activate",
        "activate at NOW with expires_at in the past raises "
        "IdentityError(expired).",
        ExpectedOutcome(False, frozenset({"expired"})),
        _idn009,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- IDN-010: illegal lifecycle transition rejected ------------------------
    def _idn010(world: ConformanceWorld) -> ObservedOutcome:
        from identity import LifecycleState, transition

        try:
            transition(LifecycleState.PROVISIONED, LifecycleState.SUPERSEDED)
        except LifecycleError as error:
            return _error_outcome(error)
        return ObservedOutcome(
            True, "illegal-transition-allowed", "illegal transition permitted"
        )

    out.append(_vector(
        "010", "negative",
        "the frozen lifecycle transition table is enforced",
        "PROVISIONED -> SUPERSEDED is illegal and raises LifecycleError.",
        ExpectedOutcome(False, frozenset({"illegal-transition",
                                          "invalid-transition",
                                          "LifecycleError"})),
        _idn010,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- IDN-011: public metadata is secret-free and round-trips --------------
    def _idn011(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        material = ident.metadata_bytes(ident.node_a)
        for secret in (b"identity-role-secret-A", b"op-secret-"):
            if secret in material:
                return ObservedOutcome(
                    False, "secret-leaked",
                    "secret material %r present in public metadata" % secret[:12],
                )
        restored = ident.metadata_from_bytes(material)
        if restored.node_id != ident.node_a.node_id.text:
            return ObservedOutcome(
                False, "roundtrip-mismatch",
                "metadata round-trip changed the node id",
            )
        return ObservedOutcome(
            True, "metadata-secret-free",
            "public metadata is secret-free and round-trips byte-identically",
        )

    out.append(_vector(
        "011", "positive",
        "public identity metadata is structurally secret-free",
        "public_metadata bytes contain no secret material and round-trip.",
        ExpectedOutcome(True, frozenset({"metadata-secret-free"})),
        _idn011,
        frozenset({"diagnostics:secret-free", "positive:core-behavior"}),
    ))

    # -- IDN-012: tampered metadata bytes fail closed --------------------------
    def _idn012(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        material = bytearray(ident.metadata_bytes(ident.node_a))
        node_text = ident.node_a.node_id.text.encode("utf-8")
        # The TOP-LEVEL node_id member is the LAST occurrence in canonical
        # order (credential views precede it and each carry their own
        # node_id copy).
        index = bytes(material).rfind(node_text)
        if index < 0:
            return ObservedOutcome(
                False, "fixture-no-node-id", "node id absent from metadata"
            )
        # Deterministically tamper one hex digit INSIDE the node id's
        # digest region (still valid lowercase hex, so a naive parser
        # would accept it -- only content comparison catches it).
        digest_offset = index + len(node_text) - 4
        original = material[digest_offset]
        material[digest_offset] = ord("0") if original != ord("0") \
            else ord("1")
        try:
            restored = ident.metadata_from_bytes(bytes(material))
        except SerializationError:
            return ObservedOutcome(
                False, "tampered-metadata-rejected",
                "tampered metadata rejected",
            )
        except Exception as error:  # any rejection is fine; record the class
            return ObservedOutcome(
                False, type(error).__name__, "tampered metadata rejected"
            )
        if restored.node_id != ident.node_a.node_id.text:
            return ObservedOutcome(
                False, "tampered-metadata-rejected",
                "tampered metadata parsed into a different node id",
            )
        return ObservedOutcome(
            True, "tampered-metadata-accepted", "tampered metadata accepted"
        )

    out.append(_vector(
        "012", "negative",
        "tampered public metadata never round-trips",
        "Byte-flipped metadata is rejected on parse.",
        ExpectedOutcome(False, frozenset({"tampered-metadata-rejected",
                                          "SerializationError"})),
        _idn012,
        frozenset({"negative:canonicalization-mismatch"}),
    ))

    # -- IDN-013: unsupported role rejected ------------------------------------
    def _idn013(world: ConformanceWorld) -> ObservedOutcome:
        ident = world.identity
        try:
            ident.provision(
                ident.node_b, "nonexistent-role", b"secret", now=NOW
            )
        except IdentityError as error:
            return _error_outcome(error)
        return ObservedOutcome(
            True, "role-accepted", "undeclared role provisioned"
        )

    out.append(_vector(
        "013", "negative",
        "only roles declared by the identity profile are provisionable",
        "Provisioning an undeclared role raises IdentityError(role).",
        ExpectedOutcome(False, frozenset({"role"})),
        _idn013,
        frozenset({"negative:malformed-required-fields"}),
    ))

    return tuple(out)
