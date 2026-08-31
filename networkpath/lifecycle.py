"""WORK-041 NetworkPath lifecycle manager.

:class:`NetworkPathManager` is the PUBLIC production surface of the
NetworkPath family.  It composes the accepted authorities through
their public seams ONLY:

- interface discovery: ``runtime.interface_source()`` (the WORK-033/
  W040 seam, read-only);
- adapter exposure/health: ``runtime.adapters_runtime()`` (WORK-016,
  read-only here -- adapters were exposed through the ordinary
  ``expose_interfaces`` path);
- binding: ``runtime.bind_session`` (the ordinary WORK-033 path --
  the W040-corrected handover mechanism);
- traffic: ``runtime.send_datagram`` (the ordinary WORK-017 path);
- session truth: ``runtime.sessions`` (WORK-012, read-only --
  binding/probing/activating require an ESTABLISHED session, and the
  session authority alone owns that state).

The manager OWNS exactly one thing: the candidate-path lifecycle
journal (discover/validate/bind/probe/activate/retire) and its
records.  It never creates identity, session, route, transport,
policy, or federation state, and it never mutates another authority's
internals (the structural audits in ``tools/networkpath_selftest.py``
pin the import and call discipline).

Fail-closed and replay-safety discipline (battery-pinned):

- every action gate requires the path's CURRENT state to equal the
  action's required state -- duplicate, stale, and out-of-order
  transitions fail closed with ``LIFECYCLE_ILLEGAL`` and NEVER mutate
  state (``RETIRED -> ACTIVE`` and ``UNVALIDATED -> ACTIVE`` cannot
  succeed);
- an exact journal replay (identical event content, identical
  instant) fails closed with ``DUPLICATE_TRANSITION``;
- duplicate discovery is idempotent: the existing record is returned
  unchanged, no event is appended, no state mutates;
- activation additionally requires recorded traffic-proof evidence
  (a probe) -- ``BOUND`` alone never activates;
- transactional handover orders the steps exactly as the W041
  contract requires (validate -> bind -> probe -> activate -> retire
  OLD LAST); any failure preserves the existing ACTIVE path, leaves
  the candidate NOT ACTIVE, and never touches the logical session.

Determinism: the injected WORK-033 clock seam is the only time
source; each journaled transition consumes EXACTLY ONE clock read
(the record timestamp and the journal event instant are the same
instant, so event ids verify deterministically); all ids/digests are
content-derived; iteration is sorted; no randomness, no UUIDs, no
wall clock.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from adapters import derive_adapter_id
from adapters.errors import AdapterError
from agent.bridge import technology_for_snapshot
from agent.clock import AgentClock
from agent.errors import AgentError
from agent.runtime import AgentRuntime
from sessions import SessionState

from .binding import bind_candidate, probe_candidate
from .errors import NetworkPathError, NetworkPathReasonCode
from .evidence import PathEvidenceRecord, assemble_path_evidence
from .model import (
    LifecycleEvent,
    NetworkPath,
    derive_network_path_event_id,
    lifecycle_event_list_digest,
)
from .observation import (
    candidate_from_observation,
    observation_for,
    read_observations,
)
from .state import (
    ACTION_REQUIRED_STATE,
    NetworkPathAction,
    NetworkPathState,
    transition_is_legal,
)
from .validation import validate_candidate

#: The auto-set timestamp field for each transitioned-to state (the
#: record timestamp and the journal event instant are one read).
_STATE_TIMESTAMP_FIELD = {
    NetworkPathState.VALIDATED: "validated_at",
    NetworkPathState.BOUND: "bound_at",
    NetworkPathState.ACTIVE: "activated_at",
    NetworkPathState.RETIRED: "retired_at",
}


@dataclass(frozen=True)
class HandoverResult:
    """The recorded outcome of one transactional handover."""

    session_id: str
    old_network_path_id: str
    new_network_path_id: str
    new_ip_binding_id: str
    probe_digest: str
    event_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "old_network_path_id": self.old_network_path_id,
            "new_network_path_id": self.new_network_path_id,
            "new_ip_binding_id": self.new_ip_binding_id,
            "probe_digest": self.probe_digest,
            "event_ids": list(self.event_ids),
        }


class NetworkPathManager:
    """The W041 public surface: candidate paths + lifecycle journal.

    Holds only its owner references (the runtime and the injected
    clock) plus its OWN journal state -- the mobile-participation
    ownership pattern.  Construct with the SAME clock the runtime
    reads when a coherent instant sequence is required.
    """

    def __init__(self, runtime: AgentRuntime, clock: AgentClock) -> None:
        if not isinstance(runtime, AgentRuntime):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "runtime must be an AgentRuntime",
            )
        if not isinstance(clock, AgentClock):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "clock must be an AgentClock (the injected WORK-033 seam)",
            )
        self._runtime = runtime
        self._clock = clock
        self._paths: Dict[str, NetworkPath] = {}
        self._events: List[LifecycleEvent] = []
        self._event_ids: set = set()
        self._probe_sequence = 0
        self._active_for_session: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public reads (deterministic)
    # ------------------------------------------------------------------

    def paths(self) -> Tuple[str, ...]:
        """All known network path ids (sorted, deterministic order)."""
        return tuple(sorted(self._paths))

    def path(self, network_path_id: str) -> NetworkPath:
        """One path record (fail closed when unknown)."""
        return self._require_path(network_path_id)

    def events(self) -> Tuple[LifecycleEvent, ...]:
        """The append-only lifecycle journal."""
        return tuple(self._events)

    def event_log_digest(self) -> str:
        return lifecycle_event_list_digest(list(self._events))

    def active_path_id(self, session_id: str) -> Optional[str]:
        """The path currently ACTIVE for one logical session (if any)."""
        return self._active_for_session.get(session_id)

    def snapshot(self) -> Dict[str, Any]:
        """A deterministic, serializable state snapshot."""
        return {
            "paths": [
                self._paths[path_id].to_dict() for path_id in sorted(self._paths)
            ],
            "events": [event.to_dict() for event in self._events],
            "probe_sequence": self._probe_sequence,
            "active_for_session": {
                session_id: self._active_for_session[session_id]
                for session_id in sorted(self._active_for_session)
            },
        }

    def content_digest(self) -> str:
        """Digest over the whole manager state (replay verification)."""
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.snapshot())
        ).hexdigest()

    def evidence(self, network_path_id: str) -> PathEvidenceRecord:
        """Assemble one path's evidence chain record."""
        path = self._require_path(network_path_id)
        events = [
            event
            for event in self._events
            if event.network_path_id == network_path_id
        ]
        return assemble_path_evidence(path, events)

    def evidence_digest(self) -> str:
        """Digest over all path evidence records (sorted by path id)."""
        digests = [
            self.evidence(path_id).record_digest()
            for path_id in sorted(self._paths)
        ]
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(digests)
        ).hexdigest()

    # ------------------------------------------------------------------
    # Lifecycle: detection (candidates are NOT active)
    # ------------------------------------------------------------------

    def discover(self) -> Tuple[str, ...]:
        """One observation cycle: platform facts -> DISCOVERED candidates.

        Candidates are NEVER activated here (the W041 acceptance
        criterion).  Duplicate discovery of a known path identity is
        an idempotent no-op: the record, its state, and the journal
        are left untouched (replay safety).
        """
        now = self._now()
        observations = read_observations(self._runtime.interface_source, now=now)
        for observation in observations:
            candidate = candidate_from_observation(
                observation, node_id=self._runtime.node_id, now=now
            )
            if candidate.network_path_id in self._paths:
                continue  # idempotent duplicate discovery (no mutation)
            self._paths[candidate.network_path_id] = candidate
            self._journal(
                candidate,
                NetworkPathAction.DISCOVER,
                NetworkPathState.DISCOVERED,
                detail="interface %r observed (%s)"
                % (candidate.interface_name, candidate.link_kind),
                instant=now,
            )
        return tuple(sorted(self._paths))

    # ------------------------------------------------------------------
    # Lifecycle: validation
    # ------------------------------------------------------------------

    def validate(self, network_path_id: str) -> NetworkPath:
        """Validate one DISCOVERED candidate against fresh facts.

        Reads a fresh observation of the interface, derives the
        adapter id exactly as the runtime's ``expose_interfaces`` does
        (public derivation), and applies the deterministic verdict.
        A rejected candidate FAILS CLOSED: state is unchanged
        (DISCOVERED), the journal is unchanged, and the typed
        ``VALIDATION_REJECTED`` error carries the deterministic
        reason.
        """
        path = self._require_path(network_path_id)
        self._require_action_state(path, NetworkPathAction.VALIDATE)
        observation = self._fresh_observation(path)
        adapter_id = derive_adapter_id(
            technology_for_snapshot(observation.snapshot),
            observation.interface_name,
        )
        lifecycle_state = self._adapter_lifecycle(adapter_id)
        health_state = self._adapter_health(adapter_id, observation.observed_at)
        verdict = validate_candidate(path, observation, lifecycle_state, health_state)
        if not verdict.accepted:
            raise NetworkPathError(
                NetworkPathReasonCode.VALIDATION_REJECTED,
                "candidate %s rejected: %s (%s)"
                % (network_path_id[:23], verdict.reason, verdict.detail),
            )
        updated = replace(
            path,
            validation_observation_digest=observation.observation_digest(),
        )
        return self._journal_transition(
            updated,
            NetworkPathAction.VALIDATE,
            NetworkPathState.VALIDATED,
            detail="verdict %s" % verdict.reason,
        )

    # ------------------------------------------------------------------
    # Lifecycle: authority-mediated binding
    # ------------------------------------------------------------------

    def bind(self, network_path_id: str, session_id: str) -> NetworkPath:
        """Bind one VALIDATED candidate to an ESTABLISHED session.

        Binding flows through the ordinary WORK-033
        ``AgentRuntime.bind_session`` path (adapter binding + WORK-018
        IP integration); the recorded facts never become owned state.
        Rejections fail closed: the candidate stays VALIDATED, no
        journal entry is appended.
        """
        path = self._require_path(network_path_id)
        self._require_action_state(path, NetworkPathAction.BIND)
        self._require_established_session(session_id)
        facts = bind_candidate(self._runtime, session_id, path)
        updated = replace(
            path,
            session_id=session_id,
            binding_adapter_id=facts.adapter_id,
            binding_id=facts.binding_id,
            bearer_ref=facts.bearer_ref,
            ip_binding_id=facts.ip_binding_id,
        )
        return self._journal_transition(
            updated,
            NetworkPathAction.BIND,
            NetworkPathState.BOUND,
            detail="adapter %s, ip binding %s"
            % (facts.adapter_id, facts.ip_binding_id[:23]),
        )

    # ------------------------------------------------------------------
    # Lifecycle: traffic probe (required before activation)
    # ------------------------------------------------------------------

    def probe(self, network_path_id: str) -> Dict[str, Any]:
        """Probe one BOUND path with a deterministic traffic proof.

        Sends one content-derived datagram through the ordinary
        WORK-017 transport path and records the probe evidence on the
        path record (state-preserving journaled action: the path
        remains BOUND).  Rejections fail closed: no evidence is
        recorded, activation remains impossible.
        """
        path = self._require_path(network_path_id)
        self._require_action_state(path, NetworkPathAction.PROBE)
        if not path.session_id:
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "path %s carries no session binding (bind first)"
                % network_path_id[:23],
            )
        # NOTE: no ESTABLISHED pre-gate here by design -- the transport
        # authority is the authority on sendability.  A suspended or
        # transport-less session surfaces as the typed PROBE_REJECTED
        # from the ordinary WORK-017 send path (the honest probe
        # failure family), not as a session-lifecycle error.
        now = self._now()
        self._probe_sequence += 1
        facts = probe_candidate(
            self._runtime,
            path.session_id,
            path.network_path_id,
            self._probe_sequence,
        )
        updated = replace(
            path,
            probe_digest=facts.frame_digest,
            probe_payload_digest=facts.payload_digest,
            probed_at=now,
        )
        self._paths[network_path_id] = updated
        self._journal(
            updated,
            NetworkPathAction.PROBE,
            NetworkPathState.BOUND,
            detail="probe %d, payload %s"
            % (facts.probe_sequence, facts.payload_digest[:23]),
            instant=now,
        )
        return facts.to_dict()

    # ------------------------------------------------------------------
    # Lifecycle: activation (the candidate-not-active invariant)
    # ------------------------------------------------------------------

    def activate(self, network_path_id: str) -> NetworkPath:
        """Activate one BOUND, PROBED candidate for its session.

        The gate chain is exhaustive: the path must be BOUND (never
        DISCOVERED/VALIDATED/RETIRED -- unvalidated paths cannot
        activate), must carry recorded traffic-proof evidence (a
        probe), and its logical session must still be ESTABLISHED.
        Activation marks the path ACTIVE for the session; the OLD
        active path (if any) is preserved at this instant -- retiring
        it is the explicit, separate next step (the transactional
        handover ordering).
        """
        path = self._require_path(network_path_id)
        self._require_action_state(path, NetworkPathAction.ACTIVATE)
        if not path.probe_digest:
            raise NetworkPathError(
                NetworkPathReasonCode.LIFECYCLE_ILLEGAL,
                "activation requires recorded traffic-proof evidence: "
                "path %s is BOUND but was never probed (probe/verify "
                "before activate -- fail closed)" % network_path_id[:23],
            )
        if not path.session_id:
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "path %s carries no session binding" % network_path_id[:23],
            )
        self._require_established_session(path.session_id)
        updated = self._journal_transition(
            path,
            NetworkPathAction.ACTIVATE,
            NetworkPathState.ACTIVE,
            detail="session %s, probe %s"
            % (path.session_id[:23], path.probe_digest[:23]),
        )
        self._active_for_session[path.session_id] = network_path_id
        return updated

    # ------------------------------------------------------------------
    # Lifecycle: retirement (terminal)
    # ------------------------------------------------------------------

    def retire(self, network_path_id: str) -> NetworkPath:
        """Retire one path (terminal; any non-terminal source state).

        Retiring a BOUND/ACTIVE path also releases its adapter-side
        binding through the ordinary WORK-016 unbind path (the
        recorded outcome is journaled honestly; the adapter authority
        owns that state).  Retiring a RETIRED path fails closed
        (duplicate retirement).  RETIRED is terminal: no path returns
        from it.
        """
        path = self._require_path(network_path_id)
        if path.state == NetworkPathState.RETIRED:
            raise NetworkPathError(
                NetworkPathReasonCode.LIFECYCLE_ILLEGAL,
                "path %s is RETIRED (terminal): duplicate retirement and "
                "RETIRED -> ACTIVE are both illegal (fail closed)"
                % network_path_id[:23],
            )
        unbind_note = ""
        if path.binding_id and path.state in (
            NetworkPathState.BOUND,
            NetworkPathState.ACTIVE,
        ):
            unbind_note = self._release_adapter_binding(path)
        updated = self._journal_transition(
            path,
            NetworkPathAction.RETIRE,
            NetworkPathState.RETIRED,
            detail="retired from %s%s" % (path.state, unbind_note),
        )
        if self._active_for_session.get(path.session_id) == network_path_id:
            self._active_for_session.pop(path.session_id, None)
        return updated

    def _release_adapter_binding(self, path: NetworkPath) -> str:
        """Release the path's adapter binding (ordinary unbind path).

        The adapter authority owns the binding; retirement records the
        honest outcome without claiming ownership.  A failed unbind is
        journaled (never silently dropped); retirement itself still
        completes -- the path-layer truth is the retirement.
        """
        try:
            result = self._runtime.adapters_runtime.unbind_session(
                path.binding_id, now=self._now()
            )
        except (AdapterError, AgentError):
            return "; adapter unbind rejected (typed adapter error)"
        if getattr(result, "ok", False):
            return "; adapter binding released"
        failure = getattr(result, "failure", None)
        reason = getattr(failure, "reason", "unknown")
        return "; adapter unbind failed (%s)" % reason

    # ------------------------------------------------------------------
    # Transactional handover
    # ------------------------------------------------------------------

    def handover(self, session_id: str, candidate_network_path_id: str) -> HandoverResult:
        """Transactional handover, exactly the W041 contract ordering:

        existing ACTIVE path + candidate
            -> validate candidate
            -> bind candidate
            -> probe/verify candidate
            -> activate candidate
            -> retire old path (LAST)

        The OLD path is never retired first.  A failed validation,
        bind, or probe aborts the handover with the typed error: the
        old ACTIVE path is preserved, the candidate is NOT ACTIVE,
        and the logical session (whose identity the session authority
        owns) is never recreated.
        """
        self._require_established_session(session_id)
        old_id = self._active_for_session.get(session_id)
        if old_id is None:
            raise NetworkPathError(
                NetworkPathReasonCode.LIFECYCLE_ILLEGAL,
                "handover requires an existing ACTIVE path for session %s "
                "(none is recorded -- fail closed)" % session_id[:23],
            )
        candidate = self._require_path(candidate_network_path_id)
        if candidate.state not in (
            NetworkPathState.DISCOVERED,
            NetworkPathState.VALIDATED,
        ):
            raise NetworkPathError(
                NetworkPathReasonCode.LIFECYCLE_ILLEGAL,
                "handover candidate %s is %s (a handover candidate must be "
                "DISCOVERED or VALIDATED -- duplicate/stale handover fails "
                "closed)" % (candidate_network_path_id[:23], candidate.state),
            )
        journal_start = len(self._events)
        if candidate.state == NetworkPathState.DISCOVERED:
            self.validate(candidate_network_path_id)
        self.bind(candidate_network_path_id, session_id)
        probe_facts = self.probe(candidate_network_path_id)
        self.activate(candidate_network_path_id)
        # candidate is ACTIVE; retire the old path LAST
        self.retire(old_id)
        new_path = self._require_path(candidate_network_path_id)
        event_ids = tuple(
            event.event_id for event in self._events[journal_start:]
        )
        return HandoverResult(
            session_id=session_id,
            old_network_path_id=old_id,
            new_network_path_id=candidate_network_path_id,
            new_ip_binding_id=new_path.ip_binding_id,
            probe_digest=probe_facts["payload_digest"],
            event_ids=event_ids,
        )

    # ------------------------------------------------------------------
    # Internal gates (fail closed, replay safe)
    # ------------------------------------------------------------------

    def _require_path(self, network_path_id: str) -> NetworkPath:
        if not isinstance(network_path_id, str):
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "network_path_id must be a string",
            )
        path = self._paths.get(network_path_id)
        if path is None:
            raise NetworkPathError(
                NetworkPathReasonCode.PATH_UNKNOWN,
                "network path %r is unknown (discover first -- fail closed)"
                % network_path_id[:80],
            )
        return path

    def _require_action_state(self, path: NetworkPath, action: str) -> None:
        """The duplicate/stale/out-of-order fail-closed gate."""
        required = ACTION_REQUIRED_STATE.get(action, "")
        if required and path.state != required:
            raise NetworkPathError(
                NetworkPathReasonCode.LIFECYCLE_ILLEGAL,
                "%s requires state %s, path %s is %s (duplicate, stale, or "
                "out-of-order transition rejected -- state unchanged)"
                % (action, required, path.network_path_id[:23], path.state),
            )

    def _require_established_session(self, session_id: str) -> None:
        if not isinstance(session_id, str) or not session_id:
            raise NetworkPathError(
                NetworkPathReasonCode.INVALID_INPUT,
                "session_id must be a non-empty string",
            )
        session = self._runtime.sessions.get(session_id)
        if session is None:
            raise NetworkPathError(
                NetworkPathReasonCode.SESSION_UNKNOWN,
                "session %r is unknown to the session authority (fail "
                "closed)" % session_id[:80],
            )
        if session.state != SessionState.ESTABLISHED:
            raise NetworkPathError(
                NetworkPathReasonCode.SESSION_UNKNOWN,
                "session %r is %s, not ESTABLISHED (the session authority "
                "owns lifecycle truth -- fail closed)"
                % (session_id[:80], session.state),
            )

    def _fresh_observation(self, path: NetworkPath):
        """One fresh observation cycle for this path's interface."""
        now = self._now()
        observations = read_observations(
            self._runtime.interface_source, now=now
        )
        return observation_for(observations, path.interface_name)

    def _adapter_lifecycle(self, adapter_id: str) -> str:
        """The adapter's lifecycle state (UNKNOWN when unexposed)."""
        try:
            return self._runtime.adapters_runtime.lifecycle(adapter_id)
        except (AdapterError, AgentError):
            return "UNKNOWN"

    def _adapter_health(self, adapter_id: str, now: str) -> str:
        """The adapter's health state (UNKNOWN when unexposed)."""
        try:
            report = self._runtime.adapters_runtime.health(adapter_id, now=now)
        except (AdapterError, AgentError):
            return "UNKNOWN"
        return report.state

    def _journal(
        self,
        path: NetworkPath,
        action: str,
        to_state: str,
        *,
        detail: str,
        instant: Optional[str] = None,
    ) -> None:
        """Append one journaled action (transition or state-preserving).

        The event id is derived at the SAME instant the event records
        (one clock read), so exact replays reproduce the id and are
        rejected as duplicates below.
        """
        now = self._now() if instant is None else instant
        event_id = derive_network_path_event_id(
            path.network_path_id, action, path.state, to_state, now
        )
        if event_id in self._event_ids:
            raise NetworkPathError(
                NetworkPathReasonCode.DUPLICATE_TRANSITION,
                "event %s replays an already-journaled transition exactly "
                "(fail closed; no mutation)" % event_id[:23],
            )
        event = LifecycleEvent(
            event_id=event_id,
            network_path_id=path.network_path_id,
            action=action,
            from_state=path.state,
            to_state=to_state,
            instant=now,
            detail=detail,
        )
        self._events.append(event)
        self._event_ids.add(event_id)

    def _journal_transition(
        self, path: NetworkPath, action: str, to_state: str, *, detail: str
    ) -> NetworkPath:
        """Apply one legal transition + journal it (one clock read)."""
        if not transition_is_legal(path.state, to_state):
            raise NetworkPathError(
                NetworkPathReasonCode.LIFECYCLE_ILLEGAL,
                "%s -> %s is not a legal NetworkPath transition "
                "(frozen table; fail closed)" % (path.state, to_state),
            )
        now = self._now()
        timestamp_field = _STATE_TIMESTAMP_FIELD.get(to_state)
        fields: Dict[str, str] = {}
        if timestamp_field is not None:
            fields[timestamp_field] = now
        updated = replace(path, state=to_state, **fields)
        self._paths[updated.network_path_id] = updated
        # journal the OLD state as from_state (the event records the
        # transition itself, not the post-state)
        self._journal(path, action, to_state, detail=detail, instant=now)
        return updated

    def _now(self) -> str:
        return self._clock.now()
