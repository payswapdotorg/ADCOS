"""WORK-032 conformance vectors -- protocol envelope (WORK-003).

Covers: envelope versions, canonicalization, extension handling
(unknown optional vs unknown required), expiration and replay metadata,
codec round-trips, and the frozen golden vectors shipped with WORK-003.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, FrozenSet, Tuple

from protocol.codec import registered_codecs
from protocol import (
    Classification,
    EnvelopeError,
    ParsePolicy,
    UnknownTypePolicy,
    accept,
    validation_clock,
)
from protocol.vectors import load_vectors

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import ConformanceWorld, FUTURE, NOW, T0, T1

__all__ = ["vectors"]

_AREA = "envelope"
_AUTHORITY = "WORK-003"
_CONTRACT = "spec/architecture.md section 7 (protocol envelope)"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-ENV-%s" % number,
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


def _accept_outcome(outcome: Any) -> ObservedOutcome:
    return ObservedOutcome(
        accepted=outcome.accepted,
        result_class=outcome.classification,
        detail=outcome.detail,
    )


def _minimal_envelope_mapping(**overrides: Any) -> Dict[str, Any]:
    data = {
        "version": 1,
        "message_type": "capability.advertise",
        "message_id": "msg-conformance-0001",
        "sender": "node:conformance-alpha",
        "issued_at": "2030-01-01T00:00:00Z",
        "expires_at": "2030-01-01T01:00:00Z",
        "extensions": {},
        "payload": {},
        "evidence": [],
        "protocol": "adcos",
        "signature": "opaque-signature-material",
    }
    data.update(overrides)
    return data


def vectors() -> Tuple[ConformanceVector, ...]:
    """All envelope-area conformance vectors (frozen set)."""
    out = []

    # -- ENV-001: golden known-good vector -------------------------------
    def _env001(world: ConformanceWorld) -> ObservedOutcome:
        golden = {v.name: v for v in load_vectors()}["minimal-valid"]
        outcome = world.envelope.accept_bytes(
            _golden_bytes(golden),
            now=validation_clock(golden.expect.validation_time),
            policy=_golden_policy(golden),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "001", "positive",
        "a frozen known-good golden vector is accepted as known_compatible",
        "WORK-003 golden vector minimal-valid: accepted with classification "
        "known_compatible under the reject policy.",
        ExpectedOutcome(True, frozenset({Classification.KNOWN_COMPATIBLE})),
        _env001,
        frozenset({"positive:core-behavior"}),
    ))

    # -- ENV-002: expired golden vector ------------------------------------
    def _env002(world: ConformanceWorld) -> ObservedOutcome:
        golden = {v.name: v for v in load_vectors()}["expired-message"]
        outcome = world.envelope.accept_bytes(
            _golden_bytes(golden),
            now=validation_clock(golden.expect.validation_time),
            policy=_golden_policy(golden),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "002", "negative",
        "expired messages are rejected with a stable temporal classification",
        "WORK-003 golden vector expired-message: rejected_temporal.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_TEMPORAL})),
        _env002,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- ENV-003: inverted temporal window ---------------------------------
    def _env003(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            _json_text(_minimal_envelope_mapping(
                issued_at="2030-01-01T01:00:00Z",
                expires_at="2030-01-01T00:00:00Z",
            )),
            now=validation_clock("2030-01-01T00:30:00Z"),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.REJECT),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "003", "negative",
        "expires_at before issued_at fails closed",
        "Inverted temporal window is rejected deterministically.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_TEMPORAL})),
        _env003,
        frozenset({"negative:expired-future-data"}),
    ))

    # -- ENV-004: unknown OPTIONAL extension preserved ---------------------
    def _env004(world: ConformanceWorld) -> ObservedOutcome:
        golden = {v.name: v for v in load_vectors()}["unknown-extension-preserved"]
        outcome = world.envelope.accept_bytes(
            _golden_bytes(golden),
            now=validation_clock(golden.expect.validation_time),
            policy=_golden_policy(golden),
        )
        if outcome.accepted and outcome.validated is not None:
            preserved = outcome.validated.envelope.extensions.get(
                "future.extension.example"
            )
            if preserved != {"data": "preserve-me", "nested": [1, 2, 3]}:
                return ObservedOutcome(
                    False, "extension-not-preserved",
                    "unknown optional extension was not preserved verbatim",
                )
        return _accept_outcome(outcome)

    out.append(_vector(
        "004", "positive",
        "unknown OPTIONAL extensions are preserved verbatim and accepted",
        "WORK-003 golden vector unknown-extension-preserved: known_additive.",
        ExpectedOutcome(True, frozenset({Classification.KNOWN_ADDITIVE})),
        _env004,
        frozenset({"negative:unknown-extensions", "positive:core-behavior"}),
    ))

    # -- ENV-005: unknown REQUIRED extension rejected -----------------------
    def _env005(world: ConformanceWorld) -> ObservedOutcome:
        golden = {v.name: v for v in load_vectors()}["unknown-critical-extension"]
        outcome = world.envelope.accept_bytes(
            _golden_bytes(golden),
            now=validation_clock(golden.expect.validation_time),
            policy=_golden_policy(golden),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "005", "negative",
        "unknown REQUIRED (must-understand) extensions fail closed",
        "WORK-003 golden vector unknown-critical-extension: "
        "rejected_unknown_required.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_UNKNOWN_REQUIRED})),
        _env005,
        frozenset({"negative:unknown-extensions"}),
    ))

    # -- ENV-006: incompatible major version --------------------------------
    def _env006(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            _json_text(_minimal_envelope_mapping(version=99)),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.REJECT),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "006", "negative",
        "incompatible major versions fail closed",
        "Version 99 envelope rejected as rejected_incompatible_major.",
        ExpectedOutcome(
            False, frozenset({Classification.REJECTED_INCOMPATIBLE_MAJOR}
        )),
        _env006,
        frozenset({"negative:invalid-versions"}),
    ))

    # -- ENV-007: malformed message type ------------------------------------
    def _env007(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            _json_text(_minimal_envelope_mapping(
                message_type="not a valid message type!!"
            )),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.REJECT),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "007", "negative",
        "malformed message types fail closed",
        "Structurally invalid message_type rejected as rejected_malformed.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_MALFORMED})),
        _env007,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- ENV-008: unknown type under REJECT policy --------------------------
    def _env008(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            _json_text(_minimal_envelope_mapping(
                message_type="conformance.unknown.type"
            )),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.REJECT),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "008", "negative",
        "unknown message types are rejected under the reject policy",
        "Unknown type + REJECT policy -> rejected_unknown_type.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_UNKNOWN_TYPE})),
        _env008,
        frozenset({"negative:unknown-extensions"}),
    ))

    # -- ENV-009: unknown type under FORWARD_OPAQUE policy ------------------
    def _env009(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            _json_text(_minimal_envelope_mapping(
                message_type="conformance.unknown.type"
            )),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "009", "positive",
        "unknown message types are forwarded opaquely under the "
        "forward-opaque policy",
        "Unknown type + FORWARD_OPAQUE -> unknown_optional_forwarded.",
        ExpectedOutcome(
            True, frozenset({Classification.UNKNOWN_OPTIONAL_FORWARDED}
        )),
        _env009,
        frozenset({"positive:core-behavior"}),
    ))

    # -- ENV-010: replay via the caller-supplied validator ------------------
    def _env010(world: ConformanceWorld) -> ObservedOutcome:
        seen = set()
        policy = ParsePolicy(unknown_type=UnknownTypePolicy.REJECT)
        now = validation_clock("2030-01-01T00:00:00Z")
        data = _json_text(_minimal_envelope_mapping())

        def replay_validator(envelope: Any) -> Any:
            from protocol import ReplayDecision

            if envelope.message_id in seen:
                return ReplayDecision.REJECT
            seen.add(envelope.message_id)
            return ReplayDecision.ALLOW

        first = world.envelope.accept_bytes(data, now=now, policy=policy,
                                            replay=replay_validator)
        second = world.envelope.accept_bytes(data, now=now, policy=policy,
                                             replay=replay_validator)
        if not first.accepted:
            return ObservedOutcome(
                False, "first-delivery-rejected", first.detail
            )
        return _accept_outcome(second)

    out.append(_vector(
        "010", "negative",
        "replayed messages are rejected by the replay hook",
        "Identical message delivered twice: first accepted, replay "
        "rejected as rejected_replay.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_REPLAY})),
        _env010,
        frozenset({
            "negative:replay",
            "discriminating:replay",
            "recovery:replay-state",
        }),
    ))

    # -- ENV-011: duplicate JSON keys fail closed ---------------------------
    def _env011(world: ConformanceWorld) -> ObservedOutcome:
        text = (
            '{"version": 1, "version": 2, "message_type": '
            '"capability.advertise", "message_id": "m1", "sender": '
            '"node:alpha", "issued_at": "2030-01-01T00:00:00Z", '
            '"expires_at": "2030-01-01T01:00:00Z", "extensions": {}, '
            '"payload": {}, "protocol": "adcos"}'
        )
        outcome = world.envelope.accept_bytes(
            text,
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.REJECT),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "011", "negative",
        "duplicate JSON keys are rejected (canonicalization mismatch)",
        "Duplicate-key JSON text rejected as rejected_malformed.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_MALFORMED})),
        _env011,
        frozenset({"negative:canonicalization-mismatch"}),
    ))

    # -- ENV-012: canonical JSON is insertion-order independent -------------
    def _env012(world: ConformanceWorld) -> ObservedOutcome:
        first = world.envelope.canonical({
            "z": 1, "a": {"y": 2, "b": 3}, "m": [3, 1, 2],
        })
        second = world.envelope.canonical({
            "m": [3, 1, 2], "a": {"b": 3, "y": 2}, "z": 1,
        })
        if first == second:
            return ObservedOutcome(
                True, "byte-identical",
                "canonical bytes identical across insertion orders",
            )
        return ObservedOutcome(
            False, "byte-mismatch",
            "canonical bytes differ across insertion orders",
        )

    out.append(_vector(
        "012", "positive",
        "canonical JSON encoding is independent of key insertion order",
        "Two mappings differing only in insertion order produce "
        "identical canonical bytes.",
        ExpectedOutcome(True, frozenset({"byte-identical"})),
        _env012,
        frozenset({"positive:determinism",
                   "negative:canonicalization-mismatch"}),
    ))

    # -- ENV-013: signature input excludes the signature member -------------
    def _env013(world: ConformanceWorld) -> ObservedOutcome:
        envelope = world.envelope.from_mapping(_minimal_envelope_mapping())
        material = world.envelope.signature_input(envelope)
        if b'"signature"' in material:
            return ObservedOutcome(
                False, "signature-in-input",
                "signature member leaked into signature input bytes",
            )
        again = world.envelope.signature_input(envelope)
        if material != again:
            return ObservedOutcome(
                False, "unstable-input",
                "signature input bytes are not stable",
            )
        return ObservedOutcome(
            True, "signature-excluded",
            "signature input stable with the signature member excluded",
        )

    out.append(_vector(
        "013", "positive",
        "signature input bytes exclude the signature member and are stable",
        "signature_input_bytes produces deterministic signing material.",
        ExpectedOutcome(True, frozenset({"signature-excluded"})),
        _env013,
        frozenset({"positive:determinism"}),
    ))

    # -- ENV-014: codec round-trip byte identity -----------------------------
    def _env014(world: ConformanceWorld) -> ObservedOutcome:
        envelope = world.envelope.from_mapping(_minimal_envelope_mapping())
        for name in sorted(registered_codecs()):
            codec = world.envelope.codec(name)
            encoded = codec.encode(envelope)
            decoded = codec.decode(encoded)
            reencoded = codec.encode(decoded)
            if reencoded != encoded:
                return ObservedOutcome(
                    False, "roundtrip-mismatch:" + name,
                    "codec %s round-trip is not byte-stable" % name,
                )
        return ObservedOutcome(
            True, "roundtrip-byte-stable",
            "all registered codecs round-trip byte-identically",
        )

    out.append(_vector(
        "014", "positive",
        "encode(decode(bytes)) == bytes for every registered codec",
        "Both registered codecs round-trip the fixture envelope "
        "byte-identically.",
        ExpectedOutcome(True, frozenset({"roundtrip-byte-stable"})),
        _env014,
        frozenset({"positive:determinism",
                   "negative:canonicalization-mismatch"}),
    ))

    # -- ENV-015: tampered wire bytes fail closed ----------------------------
    def _env015(world: ConformanceWorld) -> ObservedOutcome:
        codec = world.envelope.codec("json-debug")
        envelope = world.envelope.from_mapping(_minimal_envelope_mapping())
        encoded = bytearray(codec.encode(envelope))
        encoded[len(encoded) // 2] ^= 0x20
        try:
            codec.decode(bytes(encoded))
        except Exception:
            return ObservedOutcome(
                False, "decode-rejected",
                "tampered wire bytes rejected at decode",
            )
        return ObservedOutcome(
            True, "decode-accepted", "tampered wire bytes were accepted"
        )

    out.append(_vector(
        "015", "negative",
        "tampered wire bytes never decode into a different valid envelope",
        "Flipping a byte in the encoded form fails closed at decode.",
        ExpectedOutcome(False, frozenset({"decode-rejected"})),
        _env015,
        frozenset({"negative:canonicalization-mismatch"}),
    ))

    # -- ENV-016: missing required member ------------------------------------
    def _env016(world: ConformanceWorld) -> ObservedOutcome:
        data = _minimal_envelope_mapping()
        del data["message_id"]
        try:
            world.envelope.from_mapping(data)
        except EnvelopeError as error:
            return ObservedOutcome(
                False, "missing-member-rejected", error.code
            )
        return ObservedOutcome(
            True, "missing-member-accepted", "envelope without message_id built"
        )

    out.append(_vector(
        "016", "negative",
        "envelopes missing required members fail closed at construction",
        "envelope_from_mapping without message_id raises EnvelopeError.",
        ExpectedOutcome(False, frozenset({"missing-member-rejected"})),
        _env016,
        frozenset({"negative:malformed-required-fields"}),
    ))

    # -- ENV-017: not-yet-valid message --------------------------------------
    def _env017(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            _json_text(_minimal_envelope_mapping(
                issued_at="2030-01-02T00:00:00Z",
                expires_at="2030-01-02T01:00:00Z",
            )),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=ParsePolicy(unknown_type=UnknownTypePolicy.REJECT),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "017", "negative",
        "future-dated messages are rejected until their issue instant",
        "issued_at in the future -> rejected_temporal (not-yet-valid).",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_TEMPORAL})),
        _env017,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    return tuple(out)


def _golden_bytes(golden: Any) -> str:
    import json

    return json.dumps(golden.envelope, sort_keys=True)


def _golden_policy(golden: Any) -> ParsePolicy:
    policy = UnknownTypePolicy.REJECT
    if golden.expect.unknown_type_policy == "forward-opaque":
        policy = UnknownTypePolicy.FORWARD_OPAQUE
    return ParsePolicy(unknown_type=policy)


def _json_text(data: Dict[str, Any]) -> str:
    import json

    return json.dumps(data, sort_keys=True)
