"""WORK-055 production-conformance vectors -- protocol wire profile
(area: envelope, authority: WORK-003).

Extends the WORK-032 envelope coverage (W032-CNF-ENV-*) with the R3
production-conformance battery:

- the canonicalization profile (conformance/profile.py): every rule
  mechanically verified against the genuine WORK-003 implementation;
- the golden corpus (conformance/vectors/data/, conformance/golden.py):
  byte-exact canonical encoding, convergence, signature-input, and
  codec-cross-agreement verification;
- signature coverage and covered-byte integrity, end-to-end through
  the WORK-004 provider seam;
- unknown-field/extension hardening (required vs optional vs opaque);
- replay/idempotency hardening with no state divergence;
- evidence separation: conformance evidence can never become protocol
  state.

Every vector maps observed behavior of the FROZEN authorities; none of
this module re-decides, repairs, or re-interprets an authority
verdict.  Sabotaged-candidate discrimination for these vectors lives
in tools/conformance_selftest.py (deliberately vulnerable surface
subclasses, never shipped in the package).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, FrozenSet, Tuple

from protocol import (
    CanonicalizationError,
    Classification,
    EnvelopeError,
    ParsePolicy,
    ReplayDecision,
    UnknownTypePolicy,
    accept,
    canonical_json_bytes,
    envelope_from_mapping,
    signature_input_bytes,
    validation_clock,
)

from conformance.model import Verdict

from conformance.golden import (
    corpus_digest,
    corpus_from_entries,
    load_corpus,
    verify_corpus,
)
from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.profile import (
    CANONICALIZATION_PROFILE_RULES,
    PROFILE_RULE_IDS,
    profile_digest,
    profile_statement,
)
from conformance.world import ConformanceWorld

__all__ = ["vectors"]

_AREA = "envelope"
_AUTHORITY = "WORK-003"
_CONTRACT = (
    "spec/architecture.md section 7; spec/schemas/protocol.json; "
    "protocol/canonicalization.py; protocol/signature.py "
    "(the production canonicalization profile, declared by WORK-055)"
)

_PROD = frozenset({"positive:production-conformance"})


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W055-CNF-WIRE-%s" % number,
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


def _minimal_envelope_mapping(**overrides: Any) -> Dict[str, Any]:
    data = {
        "version": 1,
        "message_type": "capability.advertise",
        "message_id": "msg-w055-wire-0001",
        "sender": "node:w055-alpha",
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


def _policy(unknown_type: str = "reject") -> ParsePolicy:
    return ParsePolicy(
        unknown_type=(
            UnknownTypePolicy.REJECT
            if unknown_type == "reject"
            else UnknownTypePolicy.FORWARD_OPAQUE
        )
    )


def _accept_outcome(outcome: Any) -> ObservedOutcome:
    return ObservedOutcome(
        accepted=outcome.accepted,
        result_class=outcome.classification,
        detail=outcome.detail,
    )


def vectors() -> Tuple[ConformanceVector, ...]:
    """All WORK-055 wire-profile conformance vectors."""
    out = []

    # ==================================================================
    # Canonicalization profile rules (CP-01 .. CP-12)
    # ==================================================================

    # -- WIRE-001 (CP-01): key ordering, incl. the UTF-16 case ---------
    def _wire001(world: ConformanceWorld) -> ObservedOutcome:
        insertion_orders = (
            {"z": 1, "a": 2, "m": 3},
            {"m": 3, "z": 1, "a": 2},
            {"a": 2, "m": 3, "z": 1},
        )
        forms = {world.envelope.canonical(d) for d in insertion_orders}
        if len(forms) != 1:
            return ObservedOutcome(
                False, "order-dependent",
                "canonical bytes differ across insertion orders",
            )
        # UTF-16 code-unit order: a supplementary-plane key sorts BEFORE
        # U+FF01 (first UTF-16 unit D83D < FF01), unlike code-point order.
        keys = {"\U0001F600": 1, "\uff01": 2}
        observed = world.envelope.canonical(keys)
        expected = '{"\U0001F600":1,"\uff01":2}'.encode("utf-8")
        if observed != expected:
            return ObservedOutcome(
                False, "sort-key-mismatch",
                "key order is not UTF-16 code-unit order",
            )
        return ObservedOutcome(
            True, "keys-utf16-sorted",
            "insertion-order independent; keys sorted by UTF-16 units",
        )

    out.append(_vector(
        "001", "positive",
        "CP-01: object keys are sorted by UTF-16 code-unit order and "
        "canonical form is insertion-order independent",
        "Three insertion orders converge byte-identically; a key set "
        "whose UTF-16 order differs from code-point order sorts by "
        "UTF-16 units.",
        ExpectedOutcome(True, frozenset({"keys-utf16-sorted"})),
        _wire001,
        frozenset({"positive:core-behavior",
                   "discriminating:canonicalization"} | _PROD),
    ))

    # -- WIRE-002 (CP-02): no insignificant whitespace ------------------
    def _wire002(world: ConformanceWorld) -> ObservedOutcome:
        value = {"a": [1, 2], "b": {"c": None}}
        observed = world.envelope.canonical(value)
        for forbidden in (b" ", b"\n", b"\t", b"\r"):
            if forbidden in observed:
                return ObservedOutcome(
                    False, "whitespace-present",
                    "canonical bytes contain insignificant whitespace %r"
                    % forbidden,
                )
        if observed != b'{"a":[1,2],"b":{"c":null}}':
            return ObservedOutcome(
                False, "separator-mismatch",
                "tokens are not separated by ',' and ':' only",
            )
        return ObservedOutcome(
            True, "no-whitespace", "tokens separated by ',' and ':' only",
        )

    out.append(_vector(
        "002", "positive",
        "CP-02: canonical form carries no insignificant whitespace",
        "A nested value serializes with ',' and ':' separators only.",
        ExpectedOutcome(True, frozenset({"no-whitespace"})),
        _wire002,
        frozenset({"discriminating:canonicalization"} | _PROD),
    ))

    # -- WIRE-003 (CP-03): minimal string escaping -----------------------
    def _wire003(world: ConformanceWorld) -> ObservedOutcome:
        value = {
            "quote": "a\"b", "slash": "a\\b", "ctrl": "\b\f\n\r\t",
            "unit_sep": "\u001f",
        }
        observed = world.envelope.canonical(value)
        expected = (
            '{"ctrl":"\\b\\f\\n\\r\\t","quote":"a\\"b","slash":"a\\\\b",'
            '"unit_sep":"\\u001f"}'
        ).encode("utf-8")
        if observed != expected:
            return ObservedOutcome(
                False, "escaping-mismatch",
                "string escaping is not the minimal frozen form",
            )
        return ObservedOutcome(
            True, "minimal-escaping",
            "short escapes, lowercase \\u00xx for other controls",
        )

    out.append(_vector(
        "003", "positive",
        "CP-03: strings use minimal JSON escaping with lowercase hex",
        "Quotes, backslash, the five control short-escapes, and "
        "\\u001f (lowercase hex) verified byte-exactly.",
        ExpectedOutcome(True, frozenset({"minimal-escaping"})),
        _wire003,
        frozenset({"discriminating:canonicalization"} | _PROD),
    ))

    # -- WIRE-004 (CP-04): literal characters + UTF-8 --------------------
    def _wire004(world: ConformanceWorld) -> ObservedOutcome:
        value = {"text": "好 wörld 😀"}
        observed = world.envelope.canonical(value)
        if b"\\u" in observed:
            return ObservedOutcome(
                False, "over-escaping",
                "non-ASCII characters were escape-encoded instead of "
                "emitted literally",
            )
        if observed != '{"text":"好 wörld 😀"}'.encode("utf-8"):
            return ObservedOutcome(
                False, "literal-mismatch",
                "literal characters are not emitted as UTF-8",
            )
        return ObservedOutcome(
            True, "literal-utf8", "all other characters literal, UTF-8 out",
        )

    out.append(_vector(
        "004", "positive",
        "CP-04: all other characters emit literally with UTF-8 output",
        "Multibyte and supplementary-plane characters never escape.",
        ExpectedOutcome(True, frozenset({"literal-utf8"})),
        _wire004,
        frozenset({"discriminating:canonicalization"} | _PROD),
    ))

    # -- WIRE-005 (CP-05): boolean/null literals -------------------------
    def _wire005(world: ConformanceWorld) -> ObservedOutcome:
        observed = world.envelope.canonical({"t": True, "f": False, "n": None})
        if observed != b'{"f":false,"n":null,"t":true}':
            return ObservedOutcome(
                False, "literal-mismatch",
                "booleans/null did not emit as JSON literals",
            )
        return ObservedOutcome(
            True, "bool-null-literals", "true/false/null literals exact",
        )

    out.append(_vector(
        "005", "positive",
        "CP-05: booleans and null use their JSON literals",
        "True/False/None emit as true/false/null (bool before int).",
        ExpectedOutcome(True, frozenset({"bool-null-literals"})),
        _wire005,
        frozenset({"positive:core-behavior"} | _PROD),
    ))

    # -- WIRE-006 (CP-06): shortest integer form -------------------------
    def _wire006(world: ConformanceWorld) -> ObservedOutcome:
        observed = world.envelope.canonical(
            {"zero": 0, "neg": -12, "big": 9007199254740993}
        )
        expected = (
            '{"big":9007199254740993,"neg":-12,"zero":0}'
        ).encode("utf-8")
        if observed != expected:
            return ObservedOutcome(
                False, "integer-form-mismatch",
                "integers are not in shortest decimal form",
            )
        return ObservedOutcome(
            True, "shortest-integers", "shortest decimal integer forms",
        )

    out.append(_vector(
        "006", "positive",
        "CP-06: integers emit in shortest decimal form at full precision",
        "Zero, negative, and beyond-2^53 magnitudes verified exactly.",
        ExpectedOutcome(True, frozenset({"shortest-integers"})),
        _wire006,
        frozenset({"positive:core-behavior"} | _PROD),
    ))

    # -- WIRE-007 (CP-07): floats rejected --------------------------------
    def _wire007(world: ConformanceWorld) -> ObservedOutcome:
        try:
            world.envelope.canonical({"ratio": 1.5})
        except CanonicalizationError:
            return ObservedOutcome(
                False, "float-rejected",
                "floating-point values fail safely outside the subset",
            )
        return ObservedOutcome(
            True, "float-accepted", "a float was silently canonicalized",
        )

    out.append(_vector(
        "007", "negative",
        "CP-07: floating-point values are rejected (fail safely)",
        "canonical_json_bytes raises CanonicalizationError for floats.",
        ExpectedOutcome(False, frozenset({"float-rejected"})),
        _wire007,
        frozenset({"negative:canonicalization-rejection"} | _PROD),
    ))

    # -- WIRE-008 (CP-08): non-string keys rejected -----------------------
    def _wire008(world: ConformanceWorld) -> ObservedOutcome:
        try:
            world.envelope.canonical({1: "integer-key"})
        except CanonicalizationError:
            return ObservedOutcome(
                False, "key-rejected",
                "non-string object keys fail closed",
            )
        return ObservedOutcome(
            True, "key-accepted", "a non-string key was canonicalized",
        )

    out.append(_vector(
        "008", "negative",
        "CP-08: non-string object keys are rejected",
        "canonical_json_bytes raises for non-string keys.",
        ExpectedOutcome(False, frozenset({"key-rejected"})),
        _wire008,
        frozenset({"negative:canonicalization-rejection"} | _PROD),
    ))

    # -- WIRE-009 (CP-09): depth limit -------------------------------------
    def _wire009(world: ConformanceWorld) -> ObservedOutcome:
        value: Any = "leaf"
        for _ in range(70):
            value = [value]
        try:
            world.envelope.canonical(value)
        except CanonicalizationError:
            return ObservedOutcome(
                False, "depth-rejected",
                "nesting beyond MAX_CANONICAL_DEPTH fails closed",
            )
        return ObservedOutcome(
            True, "depth-accepted", "70-level nesting was canonicalized",
        )

    out.append(_vector(
        "009", "negative",
        "CP-09: values nested deeper than the frozen limit are rejected",
        "A 70-level nested array raises CanonicalizationError.",
        ExpectedOutcome(False, frozenset({"depth-rejected"})),
        _wire009,
        frozenset({"negative:canonicalization-rejection"} | _PROD),
    ))

    # -- WIRE-010 (CP-10): unencodable text rejected -----------------------
    def _wire010(world: ConformanceWorld) -> ObservedOutcome:
        try:
            world.envelope.canonical({"bad": "\ud800"})
        except CanonicalizationError:
            return ObservedOutcome(
                False, "surrogate-rejected",
                "lone surrogates fail closed (not encodable as UTF-8)",
            )
        return ObservedOutcome(
            True, "surrogate-accepted",
            "a lone surrogate was silently canonicalized",
        )

    out.append(_vector(
        "010", "negative",
        "CP-10: text that cannot encode as UTF-8 is rejected",
        "A lone surrogate raises CanonicalizationError.",
        ExpectedOutcome(False, frozenset({"surrogate-rejected"})),
        _wire010,
        frozenset({"negative:canonicalization-rejection"} | _PROD),
    ))

    # -- WIRE-011 (CP-11): absent optionals omitted ------------------------
    def _wire011(world: ConformanceWorld) -> ObservedOutcome:
        with_optional = world.envelope.from_mapping(
            _minimal_envelope_mapping(correlation_id="corr-w055-1")
        )
        without_optional = world.envelope.from_mapping(
            _minimal_envelope_mapping()
        )
        first = world.envelope.canonical(with_optional.to_dict())
        second = world.envelope.canonical(without_optional.to_dict())
        if b'"correlation_id"' in second:
            return ObservedOutcome(
                False, "optional-emitted",
                "an absent optional member was emitted (null restamping)",
            )
        if b'"correlation_id"' not in first:
            return ObservedOutcome(
                False, "optional-dropped",
                "a present optional member was dropped",
            )
        return ObservedOutcome(
            True, "absent-omitted",
            "absent optional members omitted; present ones serialized",
        )

    out.append(_vector(
        "011", "positive",
        "CP-11: absent optional members are omitted, never emitted as null",
        "Envelope with and without correlation_id serialize exactly.",
        ExpectedOutcome(True, frozenset({"absent-omitted"})),
        _wire011,
        frozenset({"positive:core-behavior"} | _PROD),
    ))

    # -- WIRE-012 (CP-12): canonicalization idempotence --------------------
    def _wire012(world: ConformanceWorld) -> ObservedOutcome:
        value = {"b": [1, {"c": None}], "a": "x", "z": True}
        first = world.envelope.canonical(value)
        parsed = json.loads(first.decode("utf-8"))
        second = world.envelope.canonical(parsed)
        if first != second:
            return ObservedOutcome(
                False, "not-idempotent",
                "canonical(canonical(x)) != canonical(x)",
            )
        return ObservedOutcome(
            True, "idempotent", "canonicalization is idempotent",
        )

    out.append(_vector(
        "012", "positive",
        "CP-12: canonicalization is idempotent",
        "Re-canonicalizing the parsed canonical form is byte-identical.",
        ExpectedOutcome(True, frozenset({"idempotent"})),
        _wire012,
        frozenset({"positive:determinism"} | _PROD),
    ))

    # ==================================================================
    # The profile statement and golden corpus
    # ==================================================================

    # -- WIRE-013: the profile statement is complete and attributed --------
    def _wire013(world: ConformanceWorld) -> ObservedOutcome:
        statement = profile_statement()
        rules = statement["rules"]
        if len(rules) != len(CANONICALIZATION_PROFILE_RULES):
            return ObservedOutcome(
                False, "profile-incomplete",
                "profile rule count mismatch",
            )
        rule_ids = {rule["rule_id"] for rule in rules}
        if rule_ids != PROFILE_RULE_IDS:
            return ObservedOutcome(
                False, "rule-ids-mismatch",
                "profile rule ids do not match the frozen rule set",
            )
        if any(rule["authority"] != "WORK-003" for rule in rules):
            return ObservedOutcome(
                False, "authority-mismatch",
                "a profile rule is not attributed to WORK-003",
            )
        if not statement["protocol_version"].startswith("1."):
            return ObservedOutcome(
                False, "version-mismatch",
                "profile does not declare Protocol Version 1.x",
            )
        return ObservedOutcome(
            True, "profile-statement-complete",
            "profile %s: %d rules, every rule attributed to WORK-003"
            % (statement["profile_id"], len(rules)),
        )

    out.append(_vector(
        "013", "positive",
        "the production canonicalization profile statement is explicit, "
        "complete, and attributed to the owning authority",
        "conformance/profile.py: named profile, protocol version from "
        "the frozen artifact, and every rule restated with its source.",
        ExpectedOutcome(True, frozenset({"profile-statement-complete"})),
        _wire013,
        frozenset({"positive:production-conformance"}),
    ))

    # -- WIRE-014: the golden corpus verifies against the authorities -------
    def _wire014(world: ConformanceWorld) -> ObservedOutcome:
        corpus = load_corpus()
        results = verify_corpus(corpus)
        failures = [r for r in results if not r.verified]
        if failures:
            return ObservedOutcome(
                False, "corpus-mismatch",
                "%d/%d corpus entries failed: %s"
                % (len(failures), len(results), failures[0].vector_id),
            )
        categories = {r.category for r in results}
        expected_categories = {
            "canonical-encoding", "encoding-convergence",
            "signature-input", "codec-cross-agreement",
        }
        if categories != expected_categories:
            return ObservedOutcome(
                False, "corpus-categories-mismatch",
                "corpus categories %s" % sorted(categories),
            )
        return ObservedOutcome(
            True, "corpus-verified",
            "%d/%d golden vectors verified byte-exactly across %d "
            "categories" % (len(results), len(results), len(categories)),
        )

    out.append(_vector(
        "014", "positive",
        "every golden vector verifies byte-exactly against its owning "
        "frozen authority",
        "The W055 corpus (canonical encoding, convergence, signature "
        "input, codec cross-agreement) passes verification through the "
        "frozen public APIs; the WORK-029 surfaces are covered from the "
        "battery (the sanctioned composition root).",
        ExpectedOutcome(True, frozenset({"corpus-verified"})),
        _wire014,
        frozenset({"positive:production-conformance"} | _PROD),
    ))

    # -- WIRE-015: corpus and profile digests are stable and order-safe ----
    def _wire015(world: ConformanceWorld) -> ObservedOutcome:
        corpus = load_corpus()
        digest_a = corpus_digest(corpus)
        digest_b = corpus_digest(corpus_from_entries(tuple(reversed(corpus))))
        if digest_a != digest_b:
            return ObservedOutcome(
                False, "digest-order-dependent",
                "the corpus digest depends on entry order",
            )
        first = profile_digest()
        second = profile_digest()
        if first != second:
            return ObservedOutcome(
                False, "profile-digest-unstable",
                "the profile digest is not stable",
            )
        return ObservedOutcome(
            True, "digests-stable",
            "corpus digest order-independent; profile digest stable (%s)"
            % first[:22],
        )

    out.append(_vector(
        "015", "positive",
        "corpus and profile digests are deterministic and "
        "order-independent",
        "Reversed corpus entry order yields the identical digest; the "
        "profile digest is stable in-process.",
        ExpectedOutcome(True, frozenset({"digests-stable"})),
        _wire015,
        frozenset({"positive:determinism",
                   "discriminating:digest-stability"} | _PROD),
    ))

    # -- WIRE-016: an unstable digest is detected ---------------------------
    def _wire016(world: ConformanceWorld) -> ObservedOutcome:
        # The vulnerability being detected: a serialization that iterates
        # an unsorted mapping (insertion order) instead of the canonical
        # sorted order.  The check must distinguish it from the canonical
        # form -- this is the negative half of digest stability.
        value = {"z": 1, "a": 2, "m": 3}
        canonical = world.envelope.canonical(value)
        unstable = json.dumps(value).encode("utf-8")  # insertion order
        if unstable == canonical:
            return ObservedOutcome(
                True, "instability-undetected",
                "an insertion-order serialization is byte-identical to "
                "the canonical form (the check is vacuous here)",
            )
        # A digest over the unstable form differs from the canonical
        # digest: instability is mechanically detectable.
        import hashlib

        digest_canonical = hashlib.sha256(canonical).hexdigest()
        digest_unstable = hashlib.sha256(unstable).hexdigest()
        if digest_canonical == digest_unstable:
            return ObservedOutcome(
                True, "instability-undetected",
                "the digests collided; detection impossible",
            )
        return ObservedOutcome(
            False, "instability-detected",
            "the insertion-order (unstable) serialization and its digest "
            "are distinguishable from the canonical form",
        )

    out.append(_vector(
        "016", "negative",
        "an order-unstable serialization is distinguishable from the "
        "canonical form (digest-instability detection)",
        "The same value serialized in insertion order differs from the "
        "canonical bytes and digest -- the stability check can fail a "
        "nondeterministic candidate.",
        ExpectedOutcome(False, frozenset({"instability-detected"})),
        _wire016,
        frozenset({"negative:digest-instability",
                   "discriminating:digest-stability"} | _PROD),
    ))

    # ==================================================================
    # Signature coverage and covered-byte integrity
    # ==================================================================

    # -- WIRE-017: every covered member participates in the basis ----------
    def _wire017(world: ConformanceWorld) -> ObservedOutcome:
        base = world.envelope.from_mapping(_minimal_envelope_mapping(
            correlation_id="corr-w055-17",
            **{"x-extra": {"kept": True}},
        ))
        baseline = world.envelope.signature_input(base)
        mutations = {
            "version": 2,
            "message_type": "capability.discover",
            "message_id": "msg-w055-wire-0099",
            "sender": "node:w055-beta",
            "issued_at": "2030-01-01T00:00:01Z",
            "expires_at": "2030-01-01T02:00:00Z",
            "extensions": {"future.x": {"required": False}},
            "payload": {"changed": True},
            "evidence": [{"kind": "fixture"}],
        }
        undetected = []
        for member, new_value in sorted(mutations.items()):
            mutated = _minimal_envelope_mapping(
                correlation_id="corr-w055-17",
                **{"x-extra": {"kept": True}},
            )
            mutated[member] = new_value
            envelope = world.envelope.from_mapping(mutated)
            if world.envelope.signature_input(envelope) == baseline:
                undetected.append(member)
        # The optional correlation_id and unknown extra member are covered
        # too.
        optional_mutated = _minimal_envelope_mapping(
            correlation_id="corr-w055-CHANGED",
            **{"x-extra": {"kept": True}},
        )
        if world.envelope.signature_input(
            world.envelope.from_mapping(optional_mutated)
        ) == baseline:
            undetected.append("correlation_id")
        extra_mutated = _minimal_envelope_mapping(
            correlation_id="corr-w055-17",
            **{"x-extra": {"kept": False}},
        )
        if world.envelope.signature_input(
            world.envelope.from_mapping(extra_mutated)
        ) == baseline:
            undetected.append("x-extra")
        if undetected:
            return ObservedOutcome(
                False, "coverage-gap",
                "mutations undetected in the signature basis: %s"
                % sorted(undetected),
            )
        return ObservedOutcome(
            True, "full-coverage",
            "every non-signature member mutation changes the basis",
        )

    out.append(_vector(
        "017", "positive",
        "signature coverage is complete: mutating any covered member "
        "changes the signature-input bytes",
        "The W003 covered-byte basis includes every member except the "
        "signature itself (known fields, optionals, unknown members, "
        "extensions, payload, evidence).",
        ExpectedOutcome(True, frozenset({"full-coverage"})),
        _wire017,
        frozenset({"discriminating:signature-coverage"} | _PROD),
    ))

    # -- WIRE-018: the signature member itself is excluded ------------------
    def _wire018(world: ConformanceWorld) -> ObservedOutcome:
        first = world.envelope.from_mapping(
            _minimal_envelope_mapping(signature="signature-A")
        )
        second = world.envelope.from_mapping(
            _minimal_envelope_mapping(signature={"algorithm": "x", "value": "y"})
        )
        basis_first = world.envelope.signature_input(first)
        basis_second = world.envelope.signature_input(second)
        if basis_first != basis_second:
            return ObservedOutcome(
                False, "signature-member-covered",
                "the signature member leaked into the covered-byte basis",
            )
        if b'"signature"' in basis_first:
            return ObservedOutcome(
                False, "signature-in-basis",
                "a signature key appears in the basis bytes",
            )
        return ObservedOutcome(
            True, "signature-excluded",
            "opaque and structured signatures produce the identical basis",
        )

    out.append(_vector(
        "018", "positive",
        "the signature member is excluded from the covered-byte basis "
        "exactly (opaque and structured forms alike)",
        "Two envelopes differing only in signature material share "
        "identical signature-input bytes.",
        ExpectedOutcome(True, frozenset({"signature-excluded"})),
        _wire018,
        frozenset({"positive:core-behavior",
                   "discriminating:signature-coverage"} | _PROD),
    ))

    # -- WIRE-019: covered-byte integrity through the W004 seam -------------
    def _wire019(world: ConformanceWorld) -> ObservedOutcome:
        import dataclasses

        statement = world.capability.statement(
            capability_id="capability.core.w055-coverage",
            provider=world.node_a,
        )
        credential = world.identity.operational_refs[world.node_a]
        signed = world.capability.sign(statement, credential)
        genuine = world.capability.verify(
            signed, credential, now=validation_clock("2026-06-01T12:00:00Z")
        )
        if not genuine:
            return ObservedOutcome(
                False, "genuine-not-verified",
                "the genuine signed statement failed verification",
            )
        # Covered-member tamper matrix: every semantic member of the
        # statement is inside the signature basis.
        tampered_variants = {
            "capability_id": "capability.core.w055-escalated",
            "provider_identity": world.node_b,
            "schema_version": "9.9",
            "valid_from": "2026-06-02T00:00:00Z",
            "expires_at": "2036-01-01T00:00:00Z",
            "parameters": {"inflated": True},
            "constraints": {"max": 999},
        }
        accepted = []
        for member, value in sorted(tampered_variants.items()):
            mutated = dataclasses.replace(signed, **{member: value})
            if world.capability.verify(
                mutated, credential,
                now=validation_clock("2026-06-01T12:00:00Z"),
            ):
                accepted.append(member)
        # The signature itself is outside the basis: tampering it also fails.
        signature_tampered = dataclasses.replace(
            signed, signature=(signed.signature[:-2] or "00") + "ff"
        )
        if world.capability.verify(
            signature_tampered, credential,
            now=validation_clock("2026-06-01T12:00:00Z"),
        ):
            accepted.append("signature")
        if accepted:
            return ObservedOutcome(
                False, "tamper-verified",
                "tampered members still verified: %s" % accepted,
            )
        return ObservedOutcome(
            False, "tamper-rejected",
            "genuine signature verified; every covered-member tamper and "
            "the signature tamper rejected",
        )

    out.append(_vector(
        "019", "negative",
        "covered-byte integrity end-to-end: post-signing tampering of any "
        "covered semantic member never verifies",
        "Sign through the WORK-004 provider seam, then mutate every "
        "covered member (and the signature): all tampering is rejected.",
        ExpectedOutcome(False, frozenset({"tamper-rejected"})),
        _wire019,
        frozenset({"negative:signature-tampering",
                   "negative:forged-provenance",
                   "discriminating:signature-coverage"} | _PROD),
    ))

    # -- WIRE-020: signature re-attachment is forged provenance -------------
    def _wire020(world: ConformanceWorld) -> ObservedOutcome:
        import dataclasses

        credential = world.identity.operational_refs[world.node_a]
        statement_a = world.capability.statement(
            capability_id="capability.profile.w055-original",
            provider=world.node_a,
        )
        signed_a = world.capability.sign(statement_a, credential)
        # The attack: re-attach A's signature to a DIFFERENT statement
        # (structurally valid, provenance forged).
        statement_b = world.capability.statement(
            capability_id="capability.profile.w055-impostor",
            provider=world.node_a,
        )
        forged = dataclasses.replace(statement_b, signature=signed_a.signature)
        if world.capability.verify(
            forged, credential, now=validation_clock("2026-06-01T12:00:00Z")
        ):
            return ObservedOutcome(
                True, "forgery-verified",
                "a re-attached signature verified (provenance collapse)",
            )
        return ObservedOutcome(
            False, "forgery-rejected",
            "integrity != provenance: the re-attached signature does not "
            "verify",
        )

    out.append(_vector(
        "020", "negative",
        "signature re-attachment to different content is rejected "
        "(integrity is not provenance)",
        "A genuine signature re-attached to an impostor statement fails "
        "verification.",
        ExpectedOutcome(False, frozenset({"forgery-rejected"})),
        _wire020,
        frozenset({"negative:signature-tampering",
                   "negative:forged-provenance"} | _PROD),
    ))

    # ==================================================================
    # Unknown-field / extension hardening
    # ==================================================================

    # -- WIRE-021: unknown REQUIRED extension fails closed ------------------
    def _wire021(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            json.dumps(_minimal_envelope_mapping(
                extensions={"future.critical.example": {"required": True}},
            ), sort_keys=True),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=_policy("reject"),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "021", "negative",
        "an unknown extension marked required:true fails closed",
        "rejected_unknown_required for a constructed required extension "
        "(the W032 ENV-005 golden vector is the paired fixture).",
        ExpectedOutcome(
            False, frozenset({Classification.REJECTED_UNKNOWN_REQUIRED}
        )),
        _wire021,
        frozenset({"negative:unknown-extensions",
                   "discriminating:unknown-fields"} | _PROD),
    ))

    # -- WIRE-022: required:false is unknown-optional ------------------------
    def _wire022(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            json.dumps(_minimal_envelope_mapping(
                extensions={"future.optional.example": {"required": False}},
            ), sort_keys=True),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=_policy("reject"),
        )
        if outcome.accepted and outcome.validated is not None:
            preserved = outcome.validated.envelope.extensions.get(
                "future.optional.example"
            )
            if preserved != {"required": False}:
                return ObservedOutcome(
                    False, "extension-not-preserved",
                    "the optional extension was not preserved verbatim",
                )
        return _accept_outcome(outcome)

    out.append(_vector(
        "022", "positive",
        "an unknown extension marked required:false is preserved and "
        "accepted (known_additive)",
        "Explicitly-optional unknown extensions ride the forward-"
        "compatibility path.",
        ExpectedOutcome(True, frozenset({Classification.KNOWN_ADDITIVE})),
        _wire022,
        frozenset({"negative:unknown-extensions",
                   "discriminating:unknown-fields"} | _PROD),
    ))

    # -- WIRE-023: opaque non-object extension values are optional -----------
    def _wire023(world: ConformanceWorld) -> ObservedOutcome:
        outcome = world.envelope.accept_bytes(
            json.dumps(_minimal_envelope_mapping(
                extensions={"future.opaque.example": "plain-string"},
            ), sort_keys=True),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=_policy("reject"),
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "023", "positive",
        "a non-object unknown extension value is unknown-optional "
        "content (preserved, never treated as required)",
        "Only an object extension carrying required:true is "
        "must-understand; opaque values are additive.",
        ExpectedOutcome(True, frozenset({Classification.KNOWN_ADDITIVE})),
        _wire023,
        frozenset({"negative:unknown-extensions",
                   "discriminating:unknown-fields"} | _PROD),
    ))

    # ==================================================================
    # Replay / idempotency hardening
    # ==================================================================

    # -- WIRE-024: duplicate delivery rejects with no state divergence -----
    def _wire024(world: ConformanceWorld) -> ObservedOutcome:
        seen = set()
        policy = _policy("reject")
        now = validation_clock("2030-01-01T00:00:00Z")
        data = json.dumps(_minimal_envelope_mapping(), sort_keys=True)

        def replay_validator(envelope: Any) -> Any:
            if envelope.message_id in seen:
                return ReplayDecision.REJECT
            seen.add(envelope.message_id)
            return ReplayDecision.ALLOW

        first = world.envelope.accept_bytes(
            data, now=now, policy=policy, replay=replay_validator
        )
        state_after_first = set(seen)
        second = world.envelope.accept_bytes(
            data, now=now, policy=policy, replay=replay_validator
        )
        if not first.accepted:
            return ObservedOutcome(
                False, "first-delivery-rejected", first.detail
            )
        if len(seen) != 1 or seen != state_after_first:
            return ObservedOutcome(
                False, "state-divergence",
                "the rejected duplicate diverged validator state",
            )
        return _accept_outcome(second)

    out.append(_vector(
        "024", "negative",
        "duplicate delivery is rejected with exactly-once state and no "
        "divergence",
        "First accept, duplicate rejected_replay; the rejection mints no "
        "new state.",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_REPLAY})),
        _wire024,
        frozenset({"negative:replay",
                   "recovery:replay-state",
                   "discriminating:replay"} | _PROD),
    ))

    # -- WIRE-025: a failing replay validator fails safely --------------------
    def _wire025(world: ConformanceWorld) -> ObservedOutcome:
        def broken_validator(envelope: Any) -> Any:
            raise RuntimeError("validator crashed")

        outcome = world.envelope.accept_bytes(
            json.dumps(_minimal_envelope_mapping(), sort_keys=True),
            now=validation_clock("2030-01-01T00:00:00Z"),
            policy=_policy("reject"),
            replay=broken_validator,
        )
        return _accept_outcome(outcome)

    out.append(_vector(
        "025", "negative",
        "a replay validator that raises is a rejection, never a crash "
        "or a silent accept",
        "validator exception -> rejected_replay (fail safely).",
        ExpectedOutcome(False, frozenset({Classification.REJECTED_REPLAY})),
        _wire025,
        frozenset({"negative:replay",
                   "recovery:provider-exception"} | _PROD),
    ))

    # -- WIRE-026: idempotent re-evaluation of an allowed redelivery -----------
    def _wire026(world: ConformanceWorld) -> ObservedOutcome:
        policy = _policy("reject")
        now = validation_clock("2030-01-01T00:00:00Z")
        data = json.dumps(_minimal_envelope_mapping(), sort_keys=True)
        outcomes = [
            world.envelope.accept_bytes(data, now=now, policy=policy)
            for _ in range(3)
        ]
        classifications = [o.classification for o in outcomes]
        if len(set(classifications)) != 1 or not outcomes[0].accepted:
            return ObservedOutcome(
                False, "re-evaluation-divergence",
                "repeated evaluation of the same envelope diverged",
            )
        return ObservedOutcome(
            True, classifications[0],
            "three evaluations, one deterministic outcome "
            "(%s), zero divergence" % classifications[0],
        )

    out.append(_vector(
        "026", "positive",
        "re-evaluating the identical envelope is idempotent (same "
        "outcome, no state minted by the envelope layer)",
        "The envelope layer itself is stateless: identical inputs yield "
        "identical outcomes; replay state is the caller's contract.",
        ExpectedOutcome(True, frozenset({Classification.KNOWN_COMPATIBLE})),
        _wire026,
        frozenset({"positive:determinism"} | _PROD),
    ))

    # ==================================================================
    # Evidence separation (evidence can never become protocol state)
    # ==================================================================

    # -- WIRE-027: conformance evidence is not a protocol object --------------
    def _wire027(world: ConformanceWorld) -> ObservedOutcome:
        from conformance.evidence import build_evidence_report
        from conformance.model import (
            ConformanceReport,
            ExpectedOutcome as _Expected,
            ObservedOutcome as _Observed,
            VectorResult,
        )

        result = VectorResult(
            vector_id="W055-CNF-WIRE-self",
            area=_AREA,
            authority=_AUTHORITY,
            contract=_CONTRACT,
            invariant="fixture result for the evidence-separation probe",
            polarity="positive",
            expected=_Expected(True),
            observed=_Observed(True, "fixture", "fixture"),
            verdict=Verdict.CONFORMANT,
            reason_class="conformant",
            tags=frozenset(),
        )
        report = ConformanceReport(results=(result,))
        evidence = build_evidence_report(report)
        # The attack: treat the conformance evidence mapping as a wire
        # envelope (evidence-as-authority).  The frozen authority must
        # reject it.
        try:
            world.envelope.from_mapping(evidence)
        except EnvelopeError as error:
            return ObservedOutcome(
                False, "evidence-rejected",
                "conformance evidence cannot become a protocol envelope "
                "(%s)" % error.code,
            )
        return ObservedOutcome(
            True, "evidence-accepted",
            "a conformance evidence mapping was accepted as a protocol "
            "envelope",
        )

    out.append(_vector(
        "027", "negative",
        "conformance evidence can never be promoted into protocol state",
        "A conformance evidence report mapping is not a valid envelope "
        "and the WORK-003 authority rejects it.",
        ExpectedOutcome(False, frozenset({"evidence-rejected"})),
        _wire027,
        frozenset({"negative:evidence-as-authority",
                   "discriminating:evidence-separation"} | _PROD),
    ))

    return tuple(out)
