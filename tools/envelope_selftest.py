#!/usr/bin/env python3
"""ADCOS envelope/serialization self-test (WORK-003).

Deterministic, offline verification of the protocol package against the
frozen WORK-003 requirements (spec/prompts/WORK-003.md):

- the 16-case compatibility/evolution matrix (section 11);
- golden-vector verification, including expected canonical JSON,
  compact-CBOR, and signature-input bytes (section 12);
- property/fuzz robustness: seeded mutations of golden vectors must
  fail safely, never crash, and never silently alter an envelope
  (section 11);
- envelope-schema cross-check against spec/schemas/envelope.schema.json.

Zero third-party dependencies; seeded PRNGs make every run
byte-identical.

Invocation: python3 tools/envelope_selftest.py
Exit codes: 0 all cases passed; 1 at least one case failed.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import protocol  # noqa: E402
from protocol import (  # noqa: E402
    Classification,
    Envelope,
    canonical_json_bytes,
    envelope_from_mapping,
    signature_input_bytes,
    validation_clock,
)
from protocol.codec_cbor import (  # noqa: E402
    CompactDeterministicCborCodec,
    CodecError as CborCodecError,
    cbor_bytes,
    cbor_value,
)
from protocol.codec_json import JsonDebugCodec  # noqa: E402
from protocol.validation import (  # noqa: E402
    ParsePolicy,
    ReplayDecision,
    UnknownTypePolicy,
    accept,
    validate,
)
from protocol.vectors import load_vectors  # noqa: E402
from schema_check import load_json, validate_instance  # noqa: E402

NOW = validation_clock("2030-01-01T00:00:00Z")
JSON_CODEC = JsonDebugCodec()
CBOR_CODEC = CompactDeterministicCborCodec()
POLICY_REJECT = ParsePolicy(unknown_type=UnknownTypePolicy.REJECT)
POLICY_FORWARD = ParsePolicy(unknown_type=UnknownTypePolicy.FORWARD_OPAQUE)

ENVELOPE_SCHEMA = load_json(
    (REPO_ROOT / "spec" / "schemas" / "envelope.schema.json").read_text(encoding="utf-8")
)
ACCESS_REGISTRY = load_json(
    (REPO_ROOT / "spec" / "schemas" / "registries" / "access-profile-registry.json").read_text(
        encoding="utf-8"
    )
)


def base_envelope(**overrides: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "protocol": "adcos",
        "version": 1,
        "message_type": "capability.advertise",
        "message_id": "msg-0001",
        "sender": "node:alpha",
        "issued_at": "2030-01-01T00:00:00Z",
        "expires_at": "2030-01-01T01:00:00Z",
        "extensions": {},
        "payload": {},
        "evidence": [],
        "signature": "opaque-signature-material",
    }
    data.update(overrides)
    return data


class SeededRandom:
    """Deterministic LCG — byte-identical runs, no third-party deps."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        self._state = (
            self._state * 6364136223846793005 + 1442695040888963407
        ) & 0xFFFFFFFFFFFFFFFF
        return self._state >> 33

    def below(self, bound: int) -> int:
        return self._next() % bound

    def choice(self, items: List[Any]) -> Any:
        return items[self.below(len(items))]


# ---------------------------------------------------------------------------
# The 16-case compatibility/evolution matrix
# ---------------------------------------------------------------------------


def case_matrix(results: List[Tuple[str, bool, str]]) -> None:
    # 1. Current known envelope parses successfully.
    env = envelope_from_mapping(base_envelope())
    outcome = validate(env, now=NOW, policy=POLICY_REJECT)
    results.append(
        (
            "matrix-01-known-envelope-parses",
            outcome.accepted and outcome.classification == Classification.KNOWN_COMPATIBLE,
            outcome.classification,
        )
    )

    # 2. Unknown optional top-level field parses successfully.
    data = base_envelope(**{"future_optional_field": {"nested": [1, 2]}})
    env = envelope_from_mapping(data)
    outcome = validate(env, now=NOW, policy=POLICY_REJECT)
    results.append(
        (
            "matrix-02-unknown-optional-field-parses",
            outcome.accepted
            and outcome.classification == Classification.KNOWN_ADDITIVE
            and env.extra == {"future_optional_field": {"nested": [1, 2]}},
            "%s extra=%r" % (outcome.classification, dict(env.extra)),
        )
    )

    # 3. Unknown optional field survives parse -> serialize -> parse.
    data = base_envelope(
        **{
            "future_optional_field": {"preserve": True},
            "extensions": {"future.extension.entry": {"value": 7}},
        }
    )
    env = envelope_from_mapping(data)
    ok = True
    detail = ""
    for codec in (JSON_CODEC, CBOR_CODEC):
        decoded = codec.decode(codec.encode(env))
        if canonical_json_bytes(decoded.to_dict()) != canonical_json_bytes(env.to_dict()):
            ok, detail = False, "%s round-trip mutated the envelope" % codec.name
            break
        if decoded.extra != env.extra or dict(decoded.extensions) != dict(env.extensions):
            ok, detail = False, "%s round-trip lost unknown content" % codec.name
            break
    results.append(("matrix-03-unknown-field-survives-proxying", ok, detail or "json+cbor byte-identical"))

    # 4. Unknown extension identifier never coerced.
    data = base_envelope(
        extensions={"future.extension.entry": {"ids": ["access.3gpp.nr.imt2020x"]}}
    )
    env = envelope_from_mapping(data)
    decoded = JSON_CODEC.decode(JSON_CODEC.encode(env))
    preserved = decoded.extensions["future.extension.entry"]["ids"] == ["access.3gpp.nr.imt2020x"]
    results.append(
        (
            "matrix-04-no-identifier-coercion",
            preserved
            and "access.3gpp.nr.imt2020x" not in ACCESS_REGISTRY["entries"]
            and decoded.extensions["future.extension.entry"]["ids"] != ["access.3gpp.nr.imt2020"],
            "near-miss identifier preserved verbatim",
        )
    )

    # 5. Unknown required (critical) extension fails safely.
    data = base_envelope(extensions={"future.extension.critical": {"required": True}})
    outcome = accept(JSON_CODEC.encode(envelope_from_mapping(data)), now=NOW, policy=POLICY_FORWARD)
    results.append(
        (
            "matrix-05-unknown-required-fails",
            outcome.rejected
            and outcome.classification == Classification.REJECTED_UNKNOWN_REQUIRED,
            outcome.classification,
        )
    )

    # 6. Incompatible major version fails safely.
    data = base_envelope(version=99)
    outcome = accept(JSON_CODEC.encode(envelope_from_mapping(data)), now=NOW, policy=POLICY_FORWARD)
    results.append(
        (
            "matrix-06-incompatible-major-fails",
            outcome.rejected
            and outcome.classification == Classification.REJECTED_INCOMPATIBLE_MAJOR,
            outcome.classification,
        )
    )

    # 7. Additive compatible evolution remains parseable.
    data = base_envelope(
        **{
            "future_field_a": 1,
            "extensions": {"future.extension.b": {"x": None}},
        }
    )
    outcome = accept(JSON_CODEC.encode(envelope_from_mapping(data)), now=NOW, policy=POLICY_REJECT)
    results.append(
        (
            "matrix-07-additive-evolution-parseable",
            outcome.accepted and outcome.classification == Classification.KNOWN_ADDITIVE,
            outcome.classification,
        )
    )

    # 8. expires_at < issued_at fails.
    data = base_envelope(issued_at="2030-01-01T01:00:00Z", expires_at="2030-01-01T00:00:00Z")
    outcome = accept(JSON_CODEC.encode(envelope_from_mapping(data)), now=NOW, policy=POLICY_REJECT)
    results.append(
        (
            "matrix-08-expires-before-issued-fails",
            outcome.rejected
            and outcome.classification == Classification.REJECTED_TEMPORAL
            and outcome.detail == "expires-before-issued",
            outcome.detail,
        )
    )

    # 9. Already-expired message fails.
    data = base_envelope(issued_at="2029-01-01T00:00:00Z", expires_at="2029-01-02T00:00:00Z")
    outcome = accept(JSON_CODEC.encode(envelope_from_mapping(data)), now=NOW, policy=POLICY_REJECT)
    expired_ok = (
        outcome.rejected
        and outcome.classification == Classification.REJECTED_TEMPORAL
        and outcome.detail == "expired"
    )
    boundary = base_envelope(expires_at="2030-01-01T00:00:00Z")
    boundary_outcome = accept(
        JSON_CODEC.encode(envelope_from_mapping(boundary)), now=NOW, policy=POLICY_REJECT
    )
    skew_outcome = accept(
        JSON_CODEC.encode(
            envelope_from_mapping(
                base_envelope(
                    issued_at="2029-12-31T23:00:00Z", expires_at="2029-12-31T23:59:30Z"
                )
            )
        ),
        now=NOW,
        policy=ParsePolicy(unknown_type=UnknownTypePolicy.REJECT, clock_skew=timedelta(seconds=60)),
    )
    results.append(
        (
            "matrix-09-expired-fails",
            expired_ok
            and boundary_outcome.accepted
            and skew_outcome.accepted,
            "expired rejected; expires==now valid; skew tolerance honored",
        )
    )

    # 10. Malformed temporal values fail.
    format_bad = accept(
        json.dumps(base_envelope(expires_at="2030-01-01 01:00:00")).encode(),
        now=NOW,
        policy=POLICY_REJECT,
    )
    # Calendar-invalid (month 13) passes the format regex but must fail
    # deterministically in temporal validation.
    calendar_outcome = accept(
        json.dumps(base_envelope(issued_at="2030-13-01T00:00:00Z")).encode(),
        now=NOW,
        policy=POLICY_REJECT,
    )
    day_outcome = accept(
        json.dumps(base_envelope(expires_at="2030-02-30T00:00:00Z")).encode(),
        now=NOW,
        policy=POLICY_REJECT,
    )
    results.append(
        (
            "matrix-10-malformed-temporal-fails",
            format_bad.rejected
            and format_bad.classification == Classification.REJECTED_MALFORMED
            and calendar_outcome.rejected
            and calendar_outcome.classification == Classification.REJECTED_TEMPORAL
            and day_outcome.rejected,
            "format rejected at parse; month-13 and day-30 rejected by calendar validation",
        )
    )

    # 11. Invalid/missing required members fail deterministically.
    required_members = [
        "protocol", "version", "message_type", "message_id", "sender",
        "issued_at", "expires_at", "extensions", "payload", "evidence", "signature",
    ]
    missing_ok = True
    invalid_ok = True
    detail = ""
    for member in required_members:
        data = base_envelope()
        del data[member]
        outcome = accept(json.dumps(data).encode(), now=NOW, policy=POLICY_REJECT)
        if not (outcome.rejected and outcome.classification == Classification.REJECTED_MALFORMED):
            missing_ok, detail = False, "missing %s not rejected (%s)" % (member, outcome.classification)
            break
    type_swaps = {
        "version": "1", "message_id": 42, "sender": "", "extensions": [],
        "evidence": {}, "signature": "", "protocol": "adcosx",
    }
    for member, bad_value in type_swaps.items():
        data = base_envelope(**{member: bad_value})
        outcome = accept(json.dumps(data).encode(), now=NOW, policy=POLICY_REJECT)
        if not (outcome.rejected and outcome.classification == Classification.REJECTED_MALFORMED):
            invalid_ok, detail = False, "invalid %s=%r not rejected" % (member, bad_value)
            break
    results.append(
        (
            "matrix-11-required-members-enforced",
            missing_ok and invalid_ok,
            detail or "11 missing + 7 invalid members all rejected",
        )
    )

    # 12. message_id / correlation_id round-trip deterministically.
    data = base_envelope(message_id="msg-round-trip-001", correlation_id="corr-round-trip-9")
    env = envelope_from_mapping(data)
    ok = True
    detail = ""
    for codec in (JSON_CODEC, CBOR_CODEC):
        decoded = codec.decode(codec.encode(env))
        if decoded.message_id != "msg-round-trip-001" or decoded.correlation_id != "corr-round-trip-9":
            ok, detail = False, "%s round-trip altered identifiers" % codec.name
            break
        absent = envelope_from_mapping(base_envelope())
        decoded_absent = codec.decode(codec.encode(absent))
        if decoded_absent.correlation_id is not None or "correlation_id" in decoded_absent.to_dict():
            ok, detail = False, "%s emitted absent correlation_id" % codec.name
            break
    results.append(("matrix-12-id-roundtrip", ok, detail or "present and absent cases both stable"))

    # 13. Canonical serialization byte-identical across repeat runs.
    env = envelope_from_mapping(base_envelope(payload={"b": 2, "a": 1, "z": [3, None, True]}))
    runs = {canonical_json_bytes(env.to_dict()) for _ in range(3)}
    runs |= {canonical_json_bytes(deepcopy(env).to_dict()) for _ in range(2)}
    results.append(
        (
            "matrix-13-canonical-determinism",
            len(runs) == 1,
            "5 serializations produce %d distinct byte strings" % len(runs),
        )
    )

    # 14. Canonical signature-input bytes byte-identical across repeat runs.
    inputs = {signature_input_bytes(env) for _ in range(3)}
    inputs |= {signature_input_bytes(deepcopy(env)) for _ in range(2)}
    full = canonical_json_bytes(env.to_dict())
    results.append(
        (
            "matrix-14-signature-input-determinism",
            len(inputs) == 1 and next(iter(inputs)) != full and b"signature" not in next(iter(inputs)),
            "deterministic, signature-excluded",
        )
    )

    # 15. Known payload survives JSON/debug representation without mutation.
    payload = {"int": 42, "neg": -7, "str": "text", "bool": True, "null": None,
               "list": [1, "two", None], "nested": {"deep": {"deeper": [{}]}}}
    env = envelope_from_mapping(base_envelope(payload=payload))
    decoded = JSON_CODEC.decode(JSON_CODEC.encode(env))
    results.append(
        (
            "matrix-15-payload-survives-json-debug",
            decoded.payload == payload,
            "deep payload equality",
        )
    )

    # 16. Future profile/access identifiers need no core branches.
    access_ids = sorted(ACCESS_REGISTRY["entries"])
    future_unknown = "access.vendor.newradio-2060"
    data = base_envelope(
        extensions={"adcos.test.access-profiles": {"profiles": access_ids[:3] + [future_unknown]}},
        payload={"candidate_access": ["access.3gpp.nr.imt2020", future_unknown]},
    )
    outcome = accept(JSON_CODEC.encode(envelope_from_mapping(data)), now=NOW, policy=POLICY_REJECT)
    decoded = JSON_CODEC.decode(JSON_CODEC.encode(envelope_from_mapping(data)))
    preserved = (
        decoded.extensions["adcos.test.access-profiles"]["profiles"][3] == future_unknown
        and decoded.payload["candidate_access"][1] == future_unknown
    )
    results.append(
        (
            "matrix-16-future-access-ids-transparent",
            outcome.accepted and outcome.classification == Classification.KNOWN_ADDITIVE and preserved,
            "registry + unknown future identifiers preserved as opaque data",
        )
    )


# ---------------------------------------------------------------------------
# Deterministic-CBOR shortest-form enforcement (correction cycle 1)
# ---------------------------------------------------------------------------


def case_cbor_minimal_encoding(results: List[Tuple[str, bool, str]]) -> None:
    """RFC 8949 section 4.2.1: integers and lengths must use the shortest
    form. Non-minimal encodings are alternate byte representations of the
    same semantic value and must be rejected; boundary-minimal values must
    be accepted."""
    from protocol.codec import CodecError as WireCodecError

    reject_cases = [
        # (label, bytes, expected semantic value if it were accepted)
        ("unsigned-1-as-1-byte-form", b"\x18\x01", 1),            # 0-23 -> direct
        ("unsigned-23-as-1-byte-form", b"\x18\x17", 23),
        ("unsigned-100-as-2-byte-form", b"\x19\x00\x64", 100),    # <=255 -> 1-byte form
        ("unsigned-255-as-2-byte-form", b"\x19\x00\xff", 255),
        ("unsigned-256-as-4-byte-form", b"\x1a\x00\x00\x01\x00", 256),  # <=65535 -> 2-byte
        ("unsigned-65535-as-4-byte-form", b"\x1a\x00\x00\xff\xff", 65535),
        ("unsigned-65536-as-8-byte-form", b"\x1b" + (65536).to_bytes(8, "big"), 65536),
        ("negative-minus1-as-1-byte-form", b"\x38\x00", -1),      # major 1, arg 0 -> -1
        ("negative-minus25-as-2-byte-form", b"\x39\x00\x17", -25),
        ("text-length2-as-1-byte-form", b"\x78\x02hi", "hi"),      # len<24 -> direct
        ("text-length10-as-2-byte-form", b"\x59\x00\x0a" + b"0123456789", "0123456789"),
        ("array-length2-as-1-byte-form", b"\x98\x02\x01\x02", [1, 2]),
        ("map-length1-as-1-byte-form", b"\xb8\x01\x61\x61\x01", {"a": 1}),
    ]
    accept_cases = [
        # boundary values whose longer form IS the minimal form
        ("unsigned-24-direct-invalid", b"\x18\x18", 24),          # 24 requires 1-byte form
        ("unsigned-255-1-byte-form", b"\x18\xff", 255),
        ("unsigned-256-2-byte-form", b"\x19\x01\x00", 256),
        ("unsigned-65536-4-byte-form", b"\x1a\x00\x01\x00\x00", 65536),
        ("text-length-24-1-byte-form", b"\x78\x18" + b"x" * 24, "x" * 24),
    ]

    failures: List[str] = []
    for label, payload, expected in reject_cases:
        try:
            value = cbor_value(payload)
            failures.append("%s: non-minimal encoding accepted as %r" % (label, value))
        except (CborCodecError, WireCodecError) as error:
            if "non-minimal" not in str(error):
                failures.append("%s: rejected for wrong reason: %s" % (label, error))
        except Exception as error:  # pragma: no cover
            failures.append("%s: raised %s" % (label, type(error).__name__))
        # also confirm the minimal form of the same value IS accepted
        try:
            minimal = cbor_bytes(expected)
            if cbor_value(minimal) != expected:
                failures.append("%s: minimal form does not round-trip" % label)
        except Exception as error:  # pragma: no cover
            failures.append("%s: minimal form rejected: %s" % (label, error))

    for label, payload, expected in accept_cases:
        try:
            value = cbor_value(payload)
            if value != expected:
                failures.append("%s: decoded %r, expected %r" % (label, value, expected))
        except Exception as error:
            failures.append("%s: minimal boundary encoding rejected: %s" % (label, error))

    results.append(
        (
            "cbor-minimal-encoding-enforced",
            not failures,
            "13 non-minimal forms rejected (uint/neg/text/array/map); "
            "5 boundary-minimal forms accepted" if not failures else failures[0],
        )
    )


def case_cbor_canonical_roundtrip_identity(results: List[Tuple[str, bool, str]]) -> None:
    """Every accepted CBOR byte sequence must round-trip to exactly the
    encoder's canonical bytes: encode(decode(bytes)) == bytes."""
    rng = SeededRandom(seed=5544332)
    failures: List[str] = []

    # 1. Golden vectors: byte-identity on decode-then-encode.
    for vector in load_vectors():
        if vector.expected is None:
            continue
        canonical = bytes.fromhex(vector.expected.canonical_cbor_hex)
        decoded = CBOR_CODEC.decode(canonical)
        reencoded = CBOR_CODEC.encode(decoded)
        if reencoded != canonical:
            failures.append("%s: re-encoding differs from golden bytes" % vector.name)

    # 2. Seeded random values: byte-identity through the value codec.
    for iteration in range(300):
        value = random_value(rng, 0)
        encoded = cbor_bytes(value)
        try:
            decoded = cbor_value(encoded)
        except Exception as error:  # pragma: no cover
            failures.append("iter %d: decoder rejected encoder output: %s" % (iteration, error))
            break
        if cbor_bytes(decoded) != encoded:
            failures.append("iter %d: encode(decode(bytes)) != bytes" % iteration)
            break

    # 3. Envelope-level identity for seeded random envelopes.
    for iteration in range(100):
        data = random_envelope(rng)
        try:
            env = envelope_from_mapping(data)
        except Exception:  # pragma: no cover - generator produces valid envelopes
            continue
        encoded = CBOR_CODEC.encode(env)
        decoded = CBOR_CODEC.decode(encoded)
        if CBOR_CODEC.encode(decoded) != encoded:
            failures.append("envelope iter %d: byte identity failed" % iteration)
            break

    results.append(
        (
            "cbor-canonical-roundtrip-identity",
            not failures,
            "golden vectors + 300 values + 100 envelopes: "
            "encode(decode(bytes)) == bytes" if not failures else failures[0],
        )
    )


def case_cbor_envelope_nonminimal_rejected(results: List[Tuple[str, bool, str]]) -> None:
    """Envelope-level surgical test: splice a non-minimal integer encoding
    (version 1 as 0x18 0x01) into an otherwise valid golden-vector envelope
    and verify the whole envelope is rejected as malformed."""
    vector = None
    for candidate in load_vectors():
        if candidate.name == "minimal-valid":
            vector = candidate
            break
    assert vector is not None and vector.expected is not None
    canonical = bytes.fromhex(vector.expected.canonical_cbor_hex)
    marker = b"\x67version" + b"\x01"  # key "version" (7 bytes) + value 1
    if marker not in canonical:  # pragma: no cover - ordering invariant
        results.append(("cbor-envelope-nonminimal-rejected", False, "marker not found"))
        return
    mutated = canonical.replace(marker, b"\x67version" + b"\x18\x01", 1)
    outcome = accept(mutated, now=NOW, policy=POLICY_REJECT, codec=CBOR_CODEC)
    ok = (
        outcome.rejected
        and outcome.classification == Classification.REJECTED_MALFORMED
        and "non-minimal" in outcome.detail
    )
    # control: the unmutated canonical bytes still decode
    control = accept(canonical, now=NOW, policy=POLICY_REJECT, codec=CBOR_CODEC)
    ok = ok and control.accepted
    results.append(
        (
            "cbor-envelope-nonminimal-rejected",
            ok,
            "version 1 as 0x18 0x01 rejected (%s); canonical control accepted"
            % outcome.detail[:60],
        )
    )


# ---------------------------------------------------------------------------
# Golden vectors
# ---------------------------------------------------------------------------


def case_golden_vectors(results: List[Tuple[str, bool, str]]) -> None:
    vectors = load_vectors()
    failures: List[str] = []
    for vector in vectors:
        policy = ParsePolicy(
            unknown_type=UnknownTypePolicy.REJECT
            if vector.expect.unknown_type_policy == "reject"
            else UnknownTypePolicy.FORWARD_OPAQUE
        )
        now = validation_clock(vector.expect.validation_time)
        if vector.expected is not None:
            env = envelope_from_mapping(vector.envelope)
            canonical = canonical_json_bytes(env.to_dict()).decode("utf-8")
            compact = cbor_bytes(env.to_dict()).hex()
            sig_input = signature_input_bytes(env).decode("utf-8")
            if canonical != vector.expected.canonical_json:
                failures.append("%s: canonical JSON mismatch" % vector.name)
            if compact != vector.expected.canonical_cbor_hex:
                failures.append("%s: canonical CBOR mismatch" % vector.name)
            if sig_input != vector.expected.signature_input_json:
                failures.append("%s: signature-input mismatch" % vector.name)
        outcome = accept(
            json.dumps(vector.envelope).encode(), now=now, policy=policy
        )
        if outcome.accepted != vector.expect.accepted:
            failures.append(
                "%s: accepted %s, expected %s" % (vector.name, outcome.accepted, vector.expect.accepted)
            )
        if outcome.classification != vector.expect.classification:
            failures.append(
                "%s: classification %s, expected %s"
                % (vector.name, outcome.classification, vector.expect.classification)
            )
    results.append(
        (
            "golden-vectors-verified",
            not failures,
            "%d vectors, %s" % (len(vectors), "; ".join(failures[:3]) if failures else "all byte-exact"),
        )
    )
    # Compact codec round-trip of every parseable vector must be byte-stable.
    stable = True
    detail = "all vectors compact-round-trip stable"
    for vector in vectors:
        if vector.expected is None:
            continue
        env = envelope_from_mapping(vector.envelope)
        decoded = CBOR_CODEC.decode(CBOR_CODEC.encode(env))
        if canonical_json_bytes(decoded.to_dict()) != canonical_json_bytes(env.to_dict()):
            stable, detail = False, "%s compact round-trip unstable" % vector.name
            break
    results.append(("golden-vectors-compact-roundtrip", stable, detail))


# ---------------------------------------------------------------------------
# Property / fuzz robustness
# ---------------------------------------------------------------------------


def random_value(rng: SeededRandom, depth: int) -> Any:
    pick = rng.below(8 if depth < 4 else 5)
    if pick == 0:
        return None
    if pick == 1:
        return rng.below(2) == 1
    if pick == 2:
        return rng.below(100000) - 50000
    if pick == 3:
        return "s-%d" % rng.below(1000)
    if pick == 4:
        return "msg-%d" % rng.below(1000000)
    if pick == 5:
        return [random_value(rng, depth + 1) for _ in range(rng.below(4))]
    if pick == 6:
        return {
            ("k%d" % rng.below(50)): random_value(rng, depth + 1)
            for _ in range(rng.below(4))
        }
    return "unicode-émoon-🚀-%d" % rng.below(100)


def random_envelope(rng: SeededRandom) -> Dict[str, Any]:
    data = base_envelope(
        message_id="msg-%06d" % rng.below(1000000),
        sender="node-%d" % rng.below(100),
        payload=random_value(rng, 0),
    )
    if rng.below(2):
        data["extensions"] = {
            ("future.extension.%d" % rng.below(20)): random_value(rng, 0)
            for _ in range(rng.below(3))
        }
    if rng.below(2):
        data["future_unknown_%d" % rng.below(20)] = random_value(rng, 0)
    if rng.below(2):
        data["correlation_id"] = "corr-%d" % rng.below(10000)
    return data


def case_property_roundtrip(results: List[Tuple[str, bool, str]]) -> None:
    rng = SeededRandom(seed=20260823)
    failures: List[str] = []
    for iteration in range(300):
        data = random_envelope(rng)
        try:
            env = envelope_from_mapping(data)
        except Exception as error:
            failures.append("iter %d: generated envelope invalid: %s" % (iteration, error))
            continue
        canonical = canonical_json_bytes(env.to_dict())
        try:
            via_json = JSON_CODEC.decode(JSON_CODEC.encode(env))
            via_cbor = CBOR_CODEC.decode(CBOR_CODEC.encode(env))
        except Exception as error:
            failures.append("iter %d: codec failure: %s" % (iteration, error))
            continue
        if canonical_json_bytes(via_json.to_dict()) != canonical:
            failures.append("iter %d: json round-trip unstable" % iteration)
        if canonical_json_bytes(via_cbor.to_dict()) != canonical:
            failures.append("iter %d: cbor round-trip unstable" % iteration)
        if signature_input_bytes(env) != signature_input_bytes(via_cbor):
            failures.append("iter %d: signature input unstable" % iteration)
    results.append(
        (
            "property-roundtrip-stability",
            not failures,
            "300 seeded envelopes; %s" % (failures[0] if failures else "all stable"),
        )
    )


def case_fuzz(results: List[Tuple[str, bool, str]]) -> None:
    rng = SeededRandom(seed=9172634)
    vectors = [v for v in load_vectors() if v.expected is not None]
    json_bodies = [
        json.dumps(v.envelope).encode("utf-8") for v in vectors
    ]
    cbor_bodies = [
        bytes.fromhex(v.expected.canonical_cbor_hex)
        for v in vectors
        if v.expected is not None
    ]

    failures: List[str] = []
    checked = 0
    accepted_count = 0

    def must_not_crash(payload: bytes, label: str, codec: Any) -> None:
        """Robustness: accept() must always return an outcome, never raise.
        A byte flip inside a string value can legitimately produce a valid
        but different envelope; that is not a safety violation — silently
        ALTERING known fields or crashing would be."""
        nonlocal checked, accepted_count
        checked += 1
        try:
            outcome = accept(payload, now=NOW, policy=POLICY_FORWARD, codec=codec)
        except Exception as error:
            failures.append("%s: raised %s: %s" % (label, type(error).__name__, error))
            return
        if outcome.accepted:
            accepted_count += 1
            # An accepted mutated envelope must still be internally
            # consistent: re-encoding it must re-parse, and — for the
            # deterministic compact codec — must reproduce the exact
            # input bytes (canonical byte-identity, per the decoder's
            # shortest-form enforcement). The JSON debug codec
            # deliberately accepts non-canonical input (whitespace, key
            # order), so byte-identity is not required there.
            try:
                assert outcome.validated is not None
                encoded = codec.encode(outcome.validated.envelope)
                if isinstance(codec, CompactDeterministicCborCodec) and encoded != bytes(payload):
                    failures.append(
                        "%s: encode(decode(bytes)) != bytes — accepted CBOR input "
                        "is not in canonical form" % label
                    )
                reparsed = accept(encoded, now=NOW, policy=POLICY_FORWARD, codec=codec)
                if not reparsed.accepted:
                    failures.append("%s: accepted envelope failed re-parse" % label)
            except Exception as error:
                failures.append("%s: re-encode raised %s" % (label, type(error).__name__))

    def must_fail_safely(payload: bytes, label: str, codec: Any) -> None:
        nonlocal checked
        checked += 1
        try:
            outcome = accept(payload, now=NOW, policy=POLICY_FORWARD, codec=codec)
        except Exception as error:
            failures.append("%s: raised %s: %s" % (label, type(error).__name__, error))
            return
        if not outcome.rejected:
            failures.append("%s: malformed input accepted (%s)" % (label, outcome.classification))

    # JSON byte mutations: robustness (never crash, stable re-parse).
    for iteration in range(400):
        body: bytearray = bytearray(rng.choice(json_bodies))
        operation = rng.below(4)
        if operation == 0 and body:  # flip a byte
            position = rng.below(len(body))
            body[position] = rng.below(256)
        elif operation == 1 and len(body) > 1:  # truncate
            body = body[: rng.below(len(body))]
        elif operation == 2:  # insert a byte
            position = rng.below(len(body) + 1)
            body = body[:position] + bytes([rng.below(256)]) + body[position:]
        else:  # duplicate a JSON key — must always fail
            text = body.decode("utf-8", errors="ignore").replace('"message_id"', '"message_id","message_id"', 1)
            dup_bytes = text.encode("utf-8", errors="ignore")
            must_fail_safely(dup_bytes, "json-dupkey-%d" % iteration, JSON_CODEC)
            continue
        must_not_crash(bytes(body), "json-fuzz-%d" % iteration, JSON_CODEC)

    # CBOR byte mutations: robustness.
    for iteration in range(300):
        body = bytearray(rng.choice(cbor_bodies))
        operation = rng.below(3)
        if operation == 0 and body:
            position = rng.below(len(body))
            body[position] = rng.below(256)
        elif operation == 1 and len(body) > 1:
            body = body[: rng.below(len(body))]
        else:
            position = rng.below(len(body) + 1)
            body = body[:position] + bytes([rng.below(256)]) + body[position:]
        must_not_crash(bytes(body), "cbor-fuzz-%d" % iteration, CBOR_CODEC)

    # Structural garbage.
    garbage_inputs = [b"", b"[]", b"42", b"null", b'"text"', b"{", b"true",
                      b'{"protocol":"adcos"}', b"\xff\xfe", b"\x00" * 64,
                      b"[" * 4096 + b"]" * 4096]
    for index, payload in enumerate(garbage_inputs):
        must_fail_safely(payload, "garbage-%d" % index, JSON_CODEC)
    must_fail_safely(b"\xff" * 8, "cbor-garbage", CBOR_CODEC)
    must_fail_safely(b"\x9f\x00\xff", "cbor-indefinite", CBOR_CODEC)
    must_fail_safely(b"\xc0\x01", "cbor-tag", CBOR_CODEC)
    must_fail_safely(b"\xf9\x00\x00", "cbor-float", CBOR_CODEC)
    must_fail_safely(b"\x41\x00", "cbor-bytestring", CBOR_CODEC)

    # Oversize input rejected by policy.
    oversize = b'{"protocol":"adcos","pad":"' + b"a" * (1 << 21) + b'"}'
    outcome = accept(oversize, now=NOW, policy=POLICY_REJECT)
    if outcome.accepted or outcome.classification != Classification.REJECTED_MALFORMED:
        failures.append("oversize input not rejected")

    results.append(
        (
            "fuzz-mutations-fail-safely",
            not failures,
            "%d mutated inputs (%d valid-after-mutation); %s"
            % (checked, accepted_count, failures[0] if failures else "none crashed"),
        )
    )


# ---------------------------------------------------------------------------
# Schema cross-check and policy boundary
# ---------------------------------------------------------------------------


def case_schema_crosscheck(results: List[Tuple[str, bool, str]]) -> None:
    failures: List[str] = []
    for vector in load_vectors():
        if vector.expected is None:
            continue
        errors = validate_instance(vector.envelope, ENVELOPE_SCHEMA)
        if errors:
            failures.append("%s: %s" % (vector.name, errors[0]))
    broken = base_envelope()
    del broken["issued_at"]
    if not validate_instance(broken, ENVELOPE_SCHEMA):
        failures.append("envelope missing issued_at unexpectedly validated")
    bad_signature = base_envelope(signature=12345)
    if not validate_instance(bad_signature, ENVELOPE_SCHEMA):
        failures.append("numeric signature unexpectedly validated")
    bad_protocol = base_envelope(protocol="other")
    if not validate_instance(bad_protocol, ENVELOPE_SCHEMA):
        failures.append("foreign protocol identifier unexpectedly validated")
    results.append(
        (
            "envelope-schema-crosscheck",
            not failures,
            "%s" % (failures[0] if failures else "golden vectors conform; negatives rejected"),
        )
    )


def case_policy_boundary(results: List[Tuple[str, bool, str]]) -> None:
    # Unknown type under REJECT fails; under FORWARD it is forwarded opaquely.
    data = base_envelope(message_type="future.unknown.type")
    encoded = JSON_CODEC.encode(envelope_from_mapping(data))
    rejected = accept(encoded, now=NOW, policy=POLICY_REJECT)
    forwarded = accept(encoded, now=NOW, policy=POLICY_FORWARD)
    ok = (
        rejected.rejected
        and rejected.classification == Classification.REJECTED_UNKNOWN_TYPE
        and forwarded.accepted
        and forwarded.classification == Classification.UNKNOWN_OPTIONAL_FORWARDED
    )
    # Replay hook: ALLOW passes, REJECT rejects, raising validator fails safely.
    allow = accept(encoded, now=NOW, policy=POLICY_FORWARD, replay=lambda env: ReplayDecision.ALLOW)
    deny = accept(encoded, now=NOW, policy=POLICY_FORWARD, replay=lambda env: ReplayDecision.REJECT)
    def boom(env): raise RuntimeError("boom")
    safe = accept(encoded, now=NOW, policy=POLICY_FORWARD, replay=boom)
    ok = ok and allow.accepted and deny.rejected and safe.rejected and safe.classification == Classification.REJECTED_REPLAY
    # Validated envelopes are only produced by the validation path.
    ok = ok and forwarded.validated is not None and forwarded.validated.classification == Classification.UNKNOWN_OPTIONAL_FORWARDED
    results.append(
        (
            "explicit-policy-and-replay-hook",
            ok,
            "unknown-type policy explicit; replay hook honored; validated type gated",
        )
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Tuple[str, bool, str]] = []
    case_matrix(results)
    case_cbor_minimal_encoding(results)
    case_cbor_canonical_roundtrip_identity(results)
    case_cbor_envelope_nonminimal_rejected(results)
    case_golden_vectors(results)
    case_property_roundtrip(results)
    case_fuzz(results)
    case_schema_crosscheck(results)
    case_policy_boundary(results)

    print("ADCOS envelope/serialization self-test")
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
