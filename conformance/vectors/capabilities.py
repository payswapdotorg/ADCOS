"""WORK-032 conformance vectors -- capability statements (WORK-005).

Covers: signed capability statements, provenance-bound verification,
validity windows, withdrawal, negotiation with distinct rejection
reasons, classification, serialization, and capability inflation
(mutated capability ids after signing are never verifiable).
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

from capabilities import CapabilityError, SerializationError, classify_capability_id
from capabilities import evaluate_status

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import FUTURE, NOW, PAST, T0, T1, ConformanceWorld

import datetime

__all__ = ["vectors"]

_AREA = "capabilities"
_AUTHORITY = "WORK-005"
_CONTRACT = "spec/architecture.md section 9 (capabilities) / WORK-005"

_KNOWN_CAP = "capability.core.store-and-forward"
_UNKNOWN_WELL_FORMED = "capability.profile.future-6g-sensing"
_INVALID_CAP = "not-a-capability-id!!"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-CAP-%s" % number,
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


def _now_dt() -> datetime.datetime:
    from protocol import parse_instant

    return parse_instant(NOW)


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- CAP-001: sign -> verify (genuine provenance) ------------------------
    def _cap001(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        statement = caps.statement(capability_id=_KNOWN_CAP,
                                   provider=world.node_a)
        signed = caps.sign(
            statement, world.identity.operational_refs[world.node_a]
        )
        verified = caps.verify(
            signed, world.identity.operational_refs[world.node_a], now=_now_dt()
        )
        if verified:
            return ObservedOutcome(
                True, "verified",
                "genuinely signed statement verified against its credential",
            )
        return ObservedOutcome(False, "not-verified", "genuine signature failed")

    out.append(_vector(
        "001", "positive",
        "a statement signed by an ACTIVE credential verifies",
        "sign_statement then verify_statement with the same credential.",
        ExpectedOutcome(True, frozenset({"verified"})),
        _cap001,
        frozenset({"positive:core-behavior"}),
    ))

    # -- CAP-002: forged signature rejected ----------------------------------
    def _cap002(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        statement = caps.statement(capability_id=_KNOWN_CAP,
                                   provider=world.node_a)
        signed = caps.sign(
            statement, world.identity.operational_refs[world.node_a]
        )
        # The attack: mutate the signature bytes (structurally valid hex
        # string, forged provenance).
        tampered = signed.signature[:-2] + "ff" if signed.signature else "ff"
        forged = _replace(signed, signature=tampered)
        verified = caps.verify(
            forged, world.identity.operational_refs[world.node_a], now=_now_dt()
        )
        if verified:
            return ObservedOutcome(
                True, "forged-signature-verified",
                "forged signature accepted as provenance",
            )
        return ObservedOutcome(
            False, "forged-signature-rejected",
            "forged signature does not verify",
        )

    out.append(_vector(
        "002", "negative",
        "a mutated signature never verifies (integrity != provenance)",
        "Tampering the signature hex fails verification.",
        ExpectedOutcome(False, frozenset({"forged-signature-rejected"})),
        _cap002,
        frozenset({"negative:forged-provenance",
                   "discriminating:provenance"}),
    ))

    # -- CAP-003: capability inflation rejected -------------------------------
    def _cap003(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        statement = caps.statement(capability_id=_KNOWN_CAP,
                                   provider=world.node_a)
        signed = caps.sign(
            statement, world.identity.operational_refs[world.node_a]
        )
        # The attack: inflate the capability id AFTER signing.
        inflated = _replace(signed, capability_id=_UNKNOWN_WELL_FORMED)
        verified = caps.verify(
            inflated, world.identity.operational_refs[world.node_a],
            now=_now_dt(),
        )
        if verified:
            return ObservedOutcome(
                True, "inflation-verified",
                "inflated capability id accepted with the original signature",
            )
        return ObservedOutcome(
            False, "inflation-rejected",
            "capability inflation invalidates the signature",
        )

    out.append(_vector(
        "003", "negative",
        "mutating the capability id after signing is capability inflation",
        "The signed statement's id cannot be inflated to another capability.",
        ExpectedOutcome(False, frozenset({"inflation-rejected"})),
        _cap003,
        frozenset({
            "negative:capability-inflation",
            "discriminating:capability-inflation",
        }),
    ))

    # -- CAP-004: wrong-credential verification rejected ----------------------
    def _cap004(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        statement = caps.statement(capability_id=_KNOWN_CAP,
                                   provider=world.node_a)
        signed = caps.sign(
            statement, world.identity.operational_refs[world.node_a]
        )
        verified = caps.verify(
            signed, world.identity.operational_refs[world.node_b],
            now=_now_dt(),
        )
        if verified:
            return ObservedOutcome(
                True, "cross-credential-verified",
                "statement verified against a different node's credential",
            )
        return ObservedOutcome(
            False, "cross-credential-rejected",
            "provenance binding requires the signing credential",
        )

    out.append(_vector(
        "004", "negative",
        "verification is bound to the signing node's credential",
        "A statement signed by node A does not verify against node B.",
        ExpectedOutcome(False, frozenset({"cross-credential-rejected"})),
        _cap004,
        frozenset({"negative:forged-provenance"}),
    ))

    # -- CAP-005: serialization round-trip ------------------------------------
    def _cap005(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        statement = caps.statement(capability_id=_KNOWN_CAP,
                                   provider=world.node_a)
        data = caps.to_bytes(statement)
        restored = caps.from_bytes(data)
        if caps.to_bytes(restored) == data:
            return ObservedOutcome(
                True, "roundtrip-byte-stable",
                "statement serialization round-trips byte-identically",
            )
        return ObservedOutcome(
            False, "roundtrip-mismatch", "statement bytes changed on round-trip"
        )

    out.append(_vector(
        "005", "positive",
        "statement serialization is byte-stable on round-trip",
        "statement_to_bytes -> statement_from_bytes -> statement_to_bytes.",
        ExpectedOutcome(True, frozenset({"roundtrip-byte-stable"})),
        _cap005,
        frozenset({"positive:determinism"}),
    ))

    # -- CAP-006: tampered serialization bytes rejected ------------------------
    def _cap006(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        statement = caps.statement(capability_id=_KNOWN_CAP,
                                   provider=world.node_a)
        data = bytearray(caps.to_bytes(statement))
        data[len(data) // 2] ^= 0x01
        try:
            caps.from_bytes(bytes(data))
        except (SerializationError, CapabilityError):
            return ObservedOutcome(
                False, "tampered-bytes-rejected",
                "tampered statement bytes rejected",
            )
        except Exception as error:
            return ObservedOutcome(
                False, type(error).__name__, "tampered statement bytes rejected"
            )
        return ObservedOutcome(
            True, "tampered-bytes-accepted", "tampered statement bytes accepted"
        )

    out.append(_vector(
        "006", "negative",
        "tampered statement bytes fail closed on parse",
        "Byte-flipped canonical statement bytes are rejected.",
        ExpectedOutcome(False, frozenset({"tampered-bytes-rejected"})),
        _cap006,
        frozenset({"negative:canonicalization-mismatch"}),
    ))

    # -- CAP-007: successful negotiation ---------------------------------------
    def _cap007(world: ConformanceWorld) -> ObservedOutcome:
        from capabilities.negotiation import NegotiationSpec, Requirement

        caps = world.capability
        signed = caps.sign(
            caps.statement(capability_id=_KNOWN_CAP, provider=world.node_b),
            world.identity.operational_refs[world.node_b],
        )
        spec = NegotiationSpec(
            requirements=(
                Requirement(capability_id=_KNOWN_CAP, min_schema_version="1.0"),
            ),
            peer_statements=(signed,),
            now=_now_dt(),
        )
        result = caps.negotiate(spec)
        outcome = result.outcomes[0]
        if outcome.succeeded and outcome.selected is not None:
            return ObservedOutcome(
                True, "negotiation-selected",
                "compatible peer statement selected",
            )
        return ObservedOutcome(
            False, outcome.reason or "negotiation-failed",
            "negotiation failed unexpectedly",
        )

    out.append(_vector(
        "007", "positive",
        "negotiation selects a compatible active statement",
        "Known capability at a compatible version negotiates successfully.",
        ExpectedOutcome(True, frozenset({"negotiation-selected"})),
        _cap007,
        frozenset({"positive:core-behavior"}),
    ))

    # -- CAP-008: unknown required capability ----------------------------------
    def _cap008(world: ConformanceWorld) -> ObservedOutcome:
        from capabilities.negotiation import NegotiationSpec, Requirement

        caps = world.capability
        spec = NegotiationSpec(
            requirements=(
                Requirement(capability_id=_UNKNOWN_WELL_FORMED, required=True),
            ),
            peer_statements=(),
            now=_now_dt(),
        )
        result = caps.negotiate(spec)
        outcome = result.outcomes[0]
        if outcome.succeeded:
            return ObservedOutcome(
                True, "unknown-required-selected",
                "unknown required capability negotiated",
            )
        return ObservedOutcome(
            False, outcome.reason or "negotiation-failed",
            outcome.detail,
        )

    out.append(_vector(
        "008", "negative",
        "an unknown REQUIRED capability yields a distinct rejection reason",
        "Negotiating an unknown required capability fails with "
        "unknown-required-capability.",
        ExpectedOutcome(False, frozenset({"unknown-required-capability"})),
        _cap008,
        frozenset({"negative:unknown-extensions"}),
    ))

    # -- CAP-009: version-incompatible -----------------------------------------
    def _cap009(world: ConformanceWorld) -> ObservedOutcome:
        from capabilities.negotiation import NegotiationSpec, Requirement

        caps = world.capability
        signed = caps.sign(
            caps.statement(capability_id=_KNOWN_CAP, provider=world.node_b,
                           schema_version="2.0"),
            world.identity.operational_refs[world.node_b],
        )
        spec = NegotiationSpec(
            requirements=(
                Requirement(capability_id=_KNOWN_CAP, min_schema_version="3.0"),
            ),
            peer_statements=(signed,),
            now=_now_dt(),
        )
        result = caps.negotiate(spec)
        outcome = result.outcomes[0]
        if outcome.succeeded:
            return ObservedOutcome(
                True, "version-incompatible-selected",
                "incompatible version negotiated",
            )
        return ObservedOutcome(
            False, outcome.reason or "negotiation-failed", outcome.detail
        )

    out.append(_vector(
        "009", "negative",
        "schema-version incompatibility is an explicit rejection reason",
        "min_schema_version above the offered statement -> "
        "version-incompatible.",
        ExpectedOutcome(False, frozenset({"version-incompatible"})),
        _cap009,
        frozenset({"negative:invalid-versions"}),
    ))

    # -- CAP-010: expired statement is not usable ------------------------------
    def _cap010(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        del caps
        status = evaluate_status(
            valid_from="2025-06-01T00:00:00Z", expires_at=PAST,
            withdrawn_at=None, now=_now_dt(),
        )
        if status == "expired":
            return ObservedOutcome(
                False, "expired", "expired statement evaluates as expired"
            )
        return ObservedOutcome(
            status == "expired", status, "unexpected status %r" % status
        )

    out.append(_vector(
        "010", "negative",
        "expired statements are not usable at later instants",
        "evaluate_status reports expired past the expiry instant.",
        ExpectedOutcome(False, frozenset({"expired"})),
        _cap010,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- CAP-011: withdrawn statement ------------------------------------------
    def _cap011(world: ConformanceWorld) -> ObservedOutcome:
        caps = world.capability
        signed = caps.sign(
            caps.statement(capability_id=_KNOWN_CAP, provider=world.node_b),
            world.identity.operational_refs[world.node_b],
        )
        withdrawn = signed.withdraw(NOW)
        status = evaluate_status(
            valid_from=withdrawn.valid_from,
            expires_at=withdrawn.expires_at,
            withdrawn_at=withdrawn.withdrawn_at,
            now=_now_dt(),
        )
        if status == "withdrawn":
            return ObservedOutcome(
                False, "withdrawn", "withdrawn statement evaluates as withdrawn"
            )
        return ObservedOutcome(
            status == "withdrawn", status, "unexpected status %r" % status
        )

    out.append(_vector(
        "011", "negative",
        "withdrawal is distinct from expiry and takes effect immediately",
        "evaluate_status reports withdrawn after withdraw().",
        ExpectedOutcome(False, frozenset({"withdrawn"})),
        _cap011,
        frozenset({"negative:expired-future-data"}),
    ))

    # -- CAP-012: not-yet-valid statement ---------------------------------------
    def _cap012(world: ConformanceWorld) -> ObservedOutcome:
        status = evaluate_status(
            valid_from=FUTURE, expires_at="2028-01-01T00:00:00Z",
            withdrawn_at=None, now=_now_dt(),
        )
        if status == "not-yet-valid":
            return ObservedOutcome(
                False, "not-yet-valid",
                "future statement evaluates as not-yet-valid",
            )
        return ObservedOutcome(
            status == "not-yet-valid", status, "unexpected status %r" % status
        )

    out.append(_vector(
        "012", "negative",
        "future-dated statements are not usable before their window",
        "evaluate_status reports not-yet-valid before valid_from.",
        ExpectedOutcome(False, frozenset({"not-yet-valid"})),
        _cap012,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- CAP-013: classification discipline --------------------------------------
    def _cap013(world: ConformanceWorld) -> ObservedOutcome:
        known = classify_capability_id(_KNOWN_CAP)
        well_formed = classify_capability_id(_UNKNOWN_WELL_FORMED)
        invalid = classify_capability_id(_INVALID_CAP)
        if (known, well_formed, invalid) == (
            "known", "unknown_but_well_formed", "invalid"
        ):
            return ObservedOutcome(
                True, "classification-correct",
                "known / unknown-but-well-formed / invalid classification",
            )
        return ObservedOutcome(
            False, "classification-wrong",
            "classification %r/%r/%r" % (known, well_formed, invalid),
        )

    out.append(_vector(
        "013", "positive",
        "capability id classification is never coerced",
        "Registry classification: known, unknown_but_well_formed, invalid.",
        ExpectedOutcome(True, frozenset({"classification-correct"})),
        _cap013,
        frozenset({"positive:core-behavior"}),
    ))

    # -- CAP-014: malformed validity rejected at construction -------------------
    def _cap014(world: ConformanceWorld) -> ObservedOutcome:
        try:
            world.capability.statement(
                capability_id=_KNOWN_CAP,
                provider=world.node_a,
                valid_from="2030-01-01T00:00:00Z",
                expires_at="2029-01-01T00:00:00Z",
            )
        except CapabilityError as error:
            return ObservedOutcome(
                False, getattr(error, "code", "validity"), str(error)
            )
        return ObservedOutcome(
            True, "inverted-validity-accepted",
            "statement with inverted validity window constructed",
        )

    out.append(_vector(
        "014", "negative",
        "inverted validity windows fail closed at construction",
        "expires_at before valid_from raises CapabilityError(validity).",
        ExpectedOutcome(False, frozenset({"validity"})),
        _cap014,
        frozenset({"negative:malformed-required-fields"}),
    ))

    return tuple(out)


def _replace(obj: Any, **changes: Any) -> Any:
    import dataclasses

    return dataclasses.replace(obj, **changes)
