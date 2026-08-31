"""WORK-041 candidate path validation.

A PURE, deterministic verdict over explicit inputs: the candidate
record, the fresh platform observation, and the adapter-side facts
(lifecycle + health) read through the WORK-016 AdapterRuntime PUBLIC
surface.  Validation is one explicitly separated lifecycle step --
it never binds, activates, or mutates any authority state.

Verdict inputs and failure families (all deterministic):

- observation identity: the fresh observation must describe the SAME
  interface and link kind as the candidate (content drift between
  discovery and validation fails closed);
- platform facts: the observed link must be up;
- adapter discipline: the interface's adapter (exposed through the
  ordinary WORK-033 ``expose_interfaces`` path, the W040-corrected
  dynamic exposure mechanism) must be OPEN and not FAILED.

The validator never consults policy (the policy authority decides
route/session admission elsewhere); it never probes traffic (that is
the post-binding probe step); it never inspects private state.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import NetworkPathError, NetworkPathReasonCode
from .model import (
    NetworkPath,
    PlatformObservation,
    derive_network_path_id,
)
from .state import NetworkPathState

#: The adapter lifecycle value required of a validated candidate (the
#: WORK-016 vocabulary, read through the public AdapterRuntime).
REQUIRED_ADAPTER_LIFECYCLE = "OPEN"

#: The adapter health value that fails validation (the WORK-016
#: worse-of ladder vocabulary; DEGRADED remains a validating state).
FAILED_ADAPTER_HEALTH = "FAILED"


@dataclass(frozen=True)
class ValidationVerdict:
    """The deterministic validation verdict for one candidate path."""

    accepted: bool
    reason: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "detail": self.detail,
        }


def validate_candidate(
    path: NetworkPath,
    observation: PlatformObservation,
    adapter_lifecycle: str,
    adapter_health_state: str,
) -> ValidationVerdict:
    """Deterministic verdict: may this candidate advance to VALIDATED?

    The same logical inputs always produce the same verdict and the
    same canonical detail text (battery-pinned determinism).
    """
    if not isinstance(path, NetworkPath):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT, "path must be a NetworkPath"
        )
    if not isinstance(observation, PlatformObservation):
        raise NetworkPathError(
            NetworkPathReasonCode.INVALID_INPUT,
            "observation must be a PlatformObservation",
        )
    if observation.interface_name != path.interface_name:
        return ValidationVerdict(
            accepted=False,
            reason="observation-mismatch",
            detail="observation reports interface %r, candidate holds %r"
            % (observation.interface_name, path.interface_name),
        )
    # Staleness gate: the fresh observation must describe the SAME
    # path identity the candidate recorded.  Any content drift
    # (addresses, link kind) means the observed path is a DIFFERENT
    # path -- a stale candidate fails closed instead of validating
    # against facts it no longer holds.
    observed_identity = derive_network_path_id(
        path.node_id,
        observation.interface_name,
        observation.link_kind,
        tuple(sorted(observation.snapshot.addresses)),
    )
    if observed_identity != path.network_path_id:
        return ValidationVerdict(
            accepted=False,
            reason="identity-drift",
            detail="interface %r content drifted since discovery (the "
            "observed path is a different identity -- stale candidate "
            "fails closed)" % path.interface_name,
        )
    if not observation.state_up:
        return ValidationVerdict(
            accepted=False,
            reason="link-down",
            detail="interface %r is observed down (platform fact)"
            % path.interface_name,
        )
    if adapter_lifecycle != REQUIRED_ADAPTER_LIFECYCLE:
        return ValidationVerdict(
            accepted=False,
            reason="adapter-not-open",
            detail="adapter for interface %r is %r, not %r"
            % (path.interface_name, adapter_lifecycle, REQUIRED_ADAPTER_LIFECYCLE),
        )
    if adapter_health_state == FAILED_ADAPTER_HEALTH:
        return ValidationVerdict(
            accepted=False,
            reason="adapter-health-failed",
            detail="adapter for interface %r reports health %r"
            % (path.interface_name, adapter_health_state),
        )
    return ValidationVerdict(
        accepted=True,
        reason="accepted",
        detail="interface %r observed up, adapter OPEN and healthy "
        "(observation digest %s)"
        % (path.interface_name, observation.snapshot_digest[:23]),
    )

#: The state a candidate must be in when validation runs (fail-closed
#: gate for duplicate/stale validation attempts -- enforced by the
#: lifecycle manager, re-declared here as validation contract data).
VALIDATION_REQUIRED_STATE = NetworkPathState.DISCOVERED
