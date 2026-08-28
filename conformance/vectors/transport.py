"""WORK-032 conformance vectors -- secure transport (WORK-017).

Covers: the 4-step handshake, session/identity binding, replay and
integrity rejection, downgrade protection (offer-digest echo,
selection eligibility, policy floor), key lifecycle (rekey
generations, suspend/resume rekey), zero-trust credential recheck,
and cross-transport frame injection.  The reference engine is a
deterministic model, NOT a TLS/QUIC/IPsec/WireGuard implementation
(LOCK-018); conformance here verifies the frozen CONTRACT.
"""

from __future__ import annotations

from typing import Any, Callable, FrozenSet, Tuple

import dataclasses

from transport import (
    TransportSecurityPolicy,
    default_profile_offers,
)

from conformance.model import ConformanceVector, ExpectedOutcome, ObservedOutcome
from conformance.world import LATER, NOW, PAST, ConformanceWorld

__all__ = ["vectors"]

_AREA = "transport"
_AUTHORITY = "WORK-017"
_CONTRACT = "spec/architecture.md section 19 (secure transport) / WORK-017"

_TLS = "transport.tls.v1-3"
_QUIC = "transport.quic.v1"
_GENERIC = "transport.generic.experimental"


def _vector(number: str, polarity: str, invariant: str,
            description: str, expected: ExpectedOutcome,
            execute: Callable[[ConformanceWorld], ObservedOutcome],
            tags: FrozenSet[str] = frozenset()) -> ConformanceVector:
    return ConformanceVector(
        vector_id="W032-CNF-TRA-%s" % number,
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


def _op_outcome(result: Any) -> ObservedOutcome:
    return ObservedOutcome(
        bool(result.ok),
        getattr(result, "reason", "") or ("ok" if result.ok else "failed"),
        result.detail,
    )


def vectors() -> Tuple[ConformanceVector, ...]:
    out = []

    # -- TRA-001: full handshake establishes both sides ---------------------------
    def _tra001(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, offer, acceptance, confirmation = \
            surface.establish_pair()
        del offer, acceptance, confirmation
        registered_i = transport_id in mgr_i.transports()
        registered_r = transport_id in mgr_r.transports()
        state_i = mgr_i.get_security_state(transport_id)
        state_r = mgr_r.get_security_state(transport_id)
        if (registered_i and registered_r
                and state_i.profile_id == state_r.profile_id
                and state_i.profile_id != ""
                and state_i.session_id == state_r.session_id):
            return ObservedOutcome(
                True, "established",
                "4-step handshake established matching security state on "
                "both sides",
            )
        return ObservedOutcome(
            False, "not-established",
            "registered=%s/%s profiles=%r/%r" % (
                registered_i, registered_r, state_i.profile_id,
                state_r.profile_id,
            ),
        )

    out.append(_vector(
        "001", "positive",
        "the 4-step handshake binds session, identity, and profile",
        "establish -> respond -> complete -> confirm yields established "
        "security state on both managers.",
        ExpectedOutcome(True, frozenset({"established"})),
        _tra001,
        frozenset({"positive:core-behavior"}),
    ))

    # -- TRA-002: bidirectional exchange ----------------------------------------------
    def _tra002(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        sent = mgr_i.send(transport_id, b"conformance-payload", now=NOW)
        if not sent.ok or sent.value is None:
            return _op_outcome(sent)
        received = mgr_r.receive(transport_id, sent.value, now=NOW)
        if received.ok and received.value == b"conformance-payload":
            return ObservedOutcome(
                True, "delivered", "payload delivered intact end to end"
            )
        return _op_outcome(received)

    out.append(_vector(
        "002", "positive",
        "protected frames deliver payloads intact",
        "send -> receive round-trips the payload bytes.",
        ExpectedOutcome(True, frozenset({"delivered"})),
        _tra002,
        frozenset({"positive:core-behavior"}),
    ))

    # -- TRA-003: replayed frame rejected ------------------------------------------------
    def _tra003(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        sent = mgr_i.send(transport_id, b"replay-me", now=NOW)
        if not sent.ok or sent.value is None:
            return _op_outcome(sent)
        first = mgr_r.receive(transport_id, sent.value, now=NOW)
        if not first.ok:
            return _op_outcome(first)
        replayed = mgr_r.receive(transport_id, sent.value, now=LATER)
        if not replayed.ok and replayed.reason == "replay-rejected":
            return ObservedOutcome(
                False, "replay-rejected",
                "identical frame replay rejected by the replay window",
            )
        return ObservedOutcome(
            bool(replayed.ok), getattr(replayed, "reason", ""),
            "replay outcome %s" % getattr(replayed, "reason", ""),
        )

    out.append(_vector(
        "003", "negative",
        "frame replays are rejected (replay windows are authoritative)",
        "Delivering the identical frame twice fails the second time with "
        "replay-rejected.",
        ExpectedOutcome(False, frozenset({"replay-rejected"})),
        _tra003,
        frozenset({
            "negative:replay",
            "discriminating:replay",
            "recovery:replay-state",
        }),
    ))

    # -- TRA-004: tampered frame integrity -----------------------------------------------
    def _tra004(world: ConformanceWorld) -> ObservedOutcome:
        import copy

        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        sent = mgr_i.send(transport_id, b"integrity-check", now=NOW)
        if not sent.ok or sent.value is None:
            return _op_outcome(sent)
        frame = copy.deepcopy(sent.value)
        payload = frame.get("wire_payload")
        if isinstance(payload, str) and len(payload) >= 2:
            # Flip one hex digit, staying valid lowercase hex.
            last = payload[-1]
            frame["wire_payload"] = payload[:-1] + (
                "0" if last != "0" else "1"
            )
        else:
            for key in frame:
                if isinstance(frame[key], int):
                    frame[key] = frame[key] + 1
                    break
        result = mgr_r.receive(transport_id, frame, now=NOW)
        if not result.ok and result.reason in ("integrity-rejected",
                                               "replay-rejected"):
            return ObservedOutcome(
                False, result.reason, "tampered frame rejected"
            )
        return ObservedOutcome(
            bool(result.ok), getattr(result, "reason", ""),
            "tampered frame outcome %s" % getattr(result, "reason", ""),
        )

    out.append(_vector(
        "004", "negative",
        "tampered frames fail integrity verification",
        "Mutating the wire payload yields integrity-rejected.",
        ExpectedOutcome(False, frozenset({"integrity-rejected",
                                          "replay-rejected"})),
        _tra004,
        frozenset({"negative:canonicalization-mismatch",
                   "negative:forged-provenance"}),
    ))

    # -- TRA-005: forged offer-digest echo (downgrade) -------------------------------------
    def _tra005(world: ConformanceWorld) -> ObservedOutcome:
        import dataclasses

        surface = world.transport
        mgr_i, offer, handle = surface.begin(
            policy=surface.default_policy(),
            offers=list(default_profile_offers()),
            label="downgrade",
        )
        mgr_r, acceptance = surface.respond(offer, label="downgrade")
        # The attack: a forged echo claiming a different offer.
        forged = dataclasses.replace(
            acceptance, offer_digest="f" * 64
        )
        completed = surface.complete_initiator(
            mgr_i, handle, forged, now=NOW
        )
        if not completed.ok and completed.reason == "downgrade-rejected":
            return ObservedOutcome(
                False, "downgrade-rejected",
                "forged offer-digest echo rejected as a downgrade attack",
            )
        return ObservedOutcome(
            bool(completed.ok), getattr(completed, "reason", ""),
            "forged echo outcome %s" % getattr(completed, "reason", ""),
        )

    out.append(_vector(
        "005", "negative",
        "offer-digest echo mismatches are downgrade attacks",
        "An acceptance echoing a different offer digest fails with "
        "downgrade-rejected.",
        ExpectedOutcome(False, frozenset({"downgrade-rejected"})),
        _tra005,
        frozenset({
            "negative:transport-downgrade",
            "discriminating:downgrade",
            "negative:forged-provenance",
        }),
    ))

    # -- TRA-006: integrity cannot be waived -----------------------------------------------
    def _tra006(world: ConformanceWorld) -> ObservedOutcome:
        from transport import TransportError

        surface = world.transport
        try:
            policy = TransportSecurityPolicy(require_integrity=False)
            result = surface.manager().establish_initiator(
                surface.session_id, policy=policy,
                offered_profiles=list(default_profile_offers()),
                now=NOW, instance_label="waiver-initiator",
            )
        except TransportError as error:
            return ObservedOutcome(
                False, getattr(error, "reason", "policy-invalid"), str(error)
            )
        except ValueError as error:
            # The policy floor may fail closed at construction instead.
            return ObservedOutcome(
                False, "policy-invalid", str(error)
            )
        if not result.ok and result.reason == "policy-invalid":
            return ObservedOutcome(
                False, "policy-invalid",
                "integrity waiver rejected: integrity cannot be waived",
            )
        return ObservedOutcome(
            bool(result.ok), getattr(result, "reason", ""),
            "integrity waiver outcome %s" % getattr(result, "reason", ""),
        )

    out.append(_vector(
        "006", "negative",
        "the transport policy floor cannot waive integrity",
        "TransportSecurityPolicy(require_integrity=False) is rejected as "
        "policy-invalid.",
        ExpectedOutcome(False, frozenset({"policy-invalid"})),
        _tra006,
        frozenset({"negative:transport-downgrade",
                   "discriminating:downgrade"}),
    ))

    # -- TRA-007: negotiation selects maximal rank --------------------------------------------
    def _tra007(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        policy = surface.default_policy()
        outcome = surface.negotiate(
            list(default_profile_offers()), [_GENERIC, _TLS], policy
        )
        if outcome.selected is not None and \
                getattr(outcome.selected, "profile_id", outcome.selected) == _TLS:
            return ObservedOutcome(
                True, "maximal-rank",
                "negotiation selects the maximal-rank eligible profile",
            )
        return ObservedOutcome(
            False, outcome.reason,
            "negotiation produced %r" % (outcome.selected,),
        )

    out.append(_vector(
        "007", "positive",
        "profile negotiation is deterministic and rank-maximal",
        "Offers including tls/quic with a generic-only remote selects a "
        "higher-rank eligible profile.",
        ExpectedOutcome(True, frozenset({"maximal-rank"})),
        _tra007,
        frozenset({"positive:determinism",
                   "discriminating:downgrade"}),
    ))

    # -- TRA-008: no eligible profile ------------------------------------------------------------
    def _tra008(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        policy = surface.default_policy()
        outcome = surface.negotiate([_GENERIC], [_GENERIC], policy)
        if outcome.selected is None:
            return ObservedOutcome(
                False, outcome.reason or "no-eligible-profile",
                "policy-incompatible offers yield no eligible profile",
            )
        return ObservedOutcome(
            True, "ineligible-selected",
            "generic-only negotiation selected %r" % outcome.selected,
        )

    out.append(_vector(
        "008", "negative",
        "no intersection under the policy floor fails explicitly",
        "Generic-only offers under a confidentiality+FS policy yield "
        "no-eligible-profile.",
        ExpectedOutcome(False, frozenset({"no-eligible-profile",
                                          "negotiation-failed"})),
        _tra008,
        frozenset({"negative:transport-downgrade"}),
    ))

    # -- TRA-009: non-secureable session ------------------------------------------------------------
    def _tra009(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        requested_sid = world.session.requested(world.node_a, world.node_b)
        result = surface.manager().establish_initiator(
            requested_sid, policy=surface.default_policy(),
            offered_profiles=list(default_profile_offers()),
            now=NOW, instance_label="insecure-initiator",
        )
        if not result.ok and result.reason == "session-not-secureable":
            return ObservedOutcome(
                False, "session-not-secureable",
                "REQUESTED session cannot be secured",
            )
        return ObservedOutcome(
            bool(result.ok), getattr(result, "reason", ""),
            "insecure session outcome %s" % getattr(result, "reason", ""),
        )

    out.append(_vector(
        "009", "negative",
        "only secureable session states may establish transports",
        "establish_initiator on a REQUESTED session fails with "
        "session-not-secureable.",
        ExpectedOutcome(False, frozenset({"session-not-secureable"})),
        _tra009,
        frozenset({"negative:binding-violation"}),
    ))

    # -- TRA-010: rekey advances the generation --------------------------------------------------------
    def _tra010(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        before = mgr_i.get_security_state(transport_id).generation
        rekeyed = mgr_i.rekey(transport_id, "conformance-rekey", now=NOW)
        if not rekeyed.ok:
            return _op_outcome(rekeyed)
        after = mgr_i.get_security_state(transport_id).generation
        if after > before:
            return ObservedOutcome(
                True, "rekeyed",
                "rekey chained to a new key generation",
            )
        return ObservedOutcome(
            False, "generation-stalled",
            "generation %d -> %d" % (before, after),
        )

    out.append(_vector(
        "010", "positive",
        "rekey chains key generations (bounded by MAX_KEY_GENERATIONS)",
        "rekey advances the security state generation.",
        ExpectedOutcome(True, frozenset({"rekeyed"})),
        _tra010,
        frozenset({"positive:core-behavior"}),
    ))

    # -- TRA-011: resume rekeys (no suspended-generation reuse) -----------------------------------------
    def _tra011(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        mgr_i.suspend(transport_id, now=NOW)
        suspended_state = mgr_i.get_security_state(transport_id)
        resumed = mgr_i.resume(transport_id, now=NOW)
        if not resumed.ok:
            return _op_outcome(resumed)
        resumed_state = mgr_i.get_security_state(transport_id)
        if resumed_state.generation > suspended_state.generation:
            return ObservedOutcome(
                True, "resumed",
                "resume rekeyed: the suspended generation is never reused",
            )
        return ObservedOutcome(
            False, "generation-reused",
            "generation %d -> %d across suspend/resume"
            % (suspended_state.generation, resumed_state.generation),
        )

    out.append(_vector(
        "011", "positive",
        "suspended generations are never reused on resume",
        "suspend -> resume advances the generation.",
        ExpectedOutcome(True, frozenset({"resumed"})),
        _tra011,
        frozenset({"positive:core-behavior", "recovery:replay-state"}),
    ))

    # -- TRA-012: expired offer rejected ------------------------------------------------------------------
    def _tra012(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i = surface.manager()
        result = mgr_i.establish_initiator(
            surface.session_id, policy=surface.default_policy(),
            offered_profiles=list(default_profile_offers()),
            now="2026-06-01T00:00:00Z", instance_label="expiry-initiator",
            offer_expires_at="2026-06-01T11:00:00Z",
        )
        if result.ok:
            responded = surface.manager().respond(
                result.value, now=NOW, instance_label="expiry-responder",
            )
            if not responded.ok and responded.reason == "offer-expired":
                return ObservedOutcome(
                    False, "offer-expired", "expired offer rejected"
                )
            return _op_outcome(responded)
        if result.reason == "offer-expired":
            return ObservedOutcome(
                False, "offer-expired", "expired offer rejected at creation"
            )
        return _op_outcome(result)

    out.append(_vector(
        "012", "negative",
        "expired offers are rejected (establishment metadata has teeth)",
        "An offer with a past expiry fails with offer-expired.",
        ExpectedOutcome(False, frozenset({"offer-expired"})),
        _tra012,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    # -- TRA-013: envelope protection round-trip ------------------------------------------------------------
    def _tra013(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        envelope = world.envelope.from_mapping({
            "version": 1,
            "message_type": "capability.advertise",
            "message_id": "msg-conformance-transport",
            "sender": "node:conformance-alpha",
            "issued_at": "2026-06-01T00:00:00Z",
            "expires_at": "2026-12-31T23:59:59Z",
            "extensions": {},
            "payload": {"hello": "transport"},
            "evidence": [],
            "protocol": "adcos",
            "signature": "opaque",
        })
        protected = mgr_i.protect_envelope(transport_id, envelope, now=NOW)
        if not protected.ok or protected.value is None:
            return _op_outcome(protected)
        received = mgr_r.receive_envelope(
            transport_id, protected.value, now=NOW
        )
        if received.ok and received.value is not None:
            return ObservedOutcome(
                True, "envelope-delivered",
                "envelope protected, delivered, and validated end to end",
            )
        return _op_outcome(received)

    out.append(_vector(
        "013", "positive",
        "envelopes ride protected transports (section 7 rule 6)",
        "protect_envelope -> receive_envelope delivers a validated "
        "envelope.",
        ExpectedOutcome(True, frozenset({"envelope-delivered"})),
        _tra013,
        frozenset({"positive:core-behavior", "matrix:envelope-interop"}),
    ))

    # -- TRA-014: cross-transport frame injection -------------------------------------------------------------
    def _tra014(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair(
            label="first"
        )
        mgr_i2, mgr_r2, transport_id2, *_ = surface.establish_pair(
            label="second"
        )
        sent = mgr_i2.send(transport_id2, b"other-transport", now=NOW)
        if not sent.ok or sent.value is None:
            return _op_outcome(sent)
        # The attack: deliver transport-2's frame to transport-1's receiver.
        result = mgr_r.receive(transport_id, sent.value, now=NOW)
        if not result.ok:
            return ObservedOutcome(
                False, getattr(result, "reason", "") or "rejected",
                "frame from another transport rejected",
            )
        return ObservedOutcome(
            True, "cross-transport-accepted",
            "foreign transport frame accepted",
        )

    out.append(_vector(
        "014", "negative",
        "frames never cross transports",
        "Delivering transport-2's frame on transport-1 fails closed.",
        ExpectedOutcome(False, frozenset({"integrity-rejected",
                                          "replay-rejected",
                                          "generation-exhausted",
                                          "state-conflict",
                                          "invalid-input",
                                          "rejected"})),
        _tra014,
        frozenset({"recovery:cross-authority-injection"}),
    ))

    # -- TRA-015: transport state envelope recovery --------------------------------------------------------------
    def _tra015(world: ConformanceWorld) -> ObservedOutcome:
        from transport import (
            transport_state_from_envelope,
            transport_state_to_envelope,
            transport_view,
        )

        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        view = transport_view(mgr_i, transport_id)
        envelope = transport_state_to_envelope(
            view,
            message_type="transport.state",
            message_id="msg-conformance-transport-state",
            sender=world.node_a,
            issued_at="2026-06-01T00:00:00Z",
            expires_at="2026-12-31T23:59:59Z",
        )
        restored = transport_state_from_envelope(envelope)
        if restored.get("transport_id") == transport_id:
            return ObservedOutcome(
                True, "state-envelope-recovered",
                "transport state persisted and recovered via WORK-003",
            )
        return ObservedOutcome(
            False, "state-envelope-mismatch",
            "recovered %r" % restored.get("transport_id"),
        )

    out.append(_vector(
        "015", "positive",
        "transport state persists through the WORK-003 envelope (restart)",
        "transport_state_to_envelope -> transport_state_from_envelope "
        "recovers the state view.",
        ExpectedOutcome(True, frozenset({"state-envelope-recovered"})),
        _tra015,
        frozenset({"recovery:restart", "matrix:envelope-interop"}),
    ))

    # -- TRA-016: zero-trust credential recheck --------------------------------------------------------------------
    def _tra016(world: ConformanceWorld) -> ObservedOutcome:
        surface = world.transport
        mgr_i, mgr_r, transport_id, *_ = surface.establish_pair()
        # Revoke the initiator's operational credential, then recheck.
        world.identity.revoke(
            world.identity.operational_refs[world.node_a],
            reason="conformance-recheck", now=NOW,
        )
        result = mgr_i.recheck(transport_id, now=NOW)
        state = mgr_i.get_security_state(transport_id)
        suspended = hasattr(state, "lifecycle") and \
            str(state.lifecycle) in ("SUSPENDED", "TransportLifecycle.SUSPENDED")
        if not result.ok or suspended:
            return ObservedOutcome(
                False, getattr(result, "reason", "") or "suspended",
                "credential revocation detected by the zero-trust recheck",
            )
        # The transport may also fail closed at the next privileged op.
        rekeyed = mgr_i.rekey(transport_id, "post-revocation", now=NOW)
        if not rekeyed.ok and rekeyed.reason in (
            "credential-revoked", "identity-unusable",
        ):
            return ObservedOutcome(
                False, rekeyed.reason,
                "revoked credential fails closed at the next privileged op",
            )
        return ObservedOutcome(
            True, "revoked-credential-ignored",
            "revoked credential had no effect on the transport",
        )

    out.append(_vector(
        "016", "negative",
        "revoked credentials fail closed (zero-trust recheck)",
        "recheck/rekey after credential revocation suspends or rejects.",
        ExpectedOutcome(False, frozenset({
            "credential-revoked", "identity-unusable", "suspended",
            "state-conflict",
        })),
        _tra016,
        frozenset({"negative:expired-future-data", "recovery:stale-future"}),
    ))

    return tuple(out)
