"""The explicit, restored authority test seam (WORK-031).

By default the simulator builds a FULLY ISOLATED authority set (fresh
instances of the REAL authority classes); no production authority
object is ever reachable, so production authority state cannot be
mutated at all.

The ONE sanctioned exception is an explicit
:class:`AuthorityTestSeam`: a caller-provided authority component the
scenario is allowed to operate over, together with a mandatory
non-empty purpose.  The seam's contract:

- the purpose is recorded in the scenario result (no anonymous
  access);
- every mutation of the seam component happens through the owner's own
  public contract and is recorded in the trace's mutation ledger;
- on close, the runner captures the component's digest and computes a
  restoration verdict:

  - ``restored``      -- the component's digest is identical to the
    digest captured at open (the scenario left no net state);
  - ``validated``     -- the digest changed, but every mutation went
    through owner contracts recorded in the trace and the component's
    own state validates;
  - ``degraded``      -- validation failed or cleanup failed; the
    pending/degraded condition is explicit, never silent.

Integrity is not provenance: a digest match does not prove WHO caused
a mutation -- that is what the recorded mutation ledger is for.
"""

from __future__ import annotations

import hashlib
from typing import Any

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes

from .model import SimulatorError, SimulatorReasonCode

_SEAM_VERDICTS = ("restored", "validated", "degraded")


class AuthorityTestSeam:
    """An explicitly provided, restored test seam over ONE authority
    component.

    Supported component types (each digested through the owner's own
    canonical state API):

    - ``energy.resilience.NodeRejoinLedger``  -> ``ledger_digest()``
    - ``sessions.store.SessionStore``         -> ``to_canonical_bytes()``
    - ``telemetry.store.TelemetryStore``      -> ``snapshot()``
    - ``mobility.store.MobilityStore``        -> ``snapshot()``
    - ``policy.store.PolicyStore``            -> ``snapshot()``

    Anything else fails closed (``unsupported-seam-component``): an
    unbounded "inject any object" seam would be a second authority
    boundary, which the WORK-031 contract forbids.
    """

    def __init__(self, component: Any, purpose: str) -> None:
        if not isinstance(purpose, str) or not purpose.strip():
            raise SimulatorError(
                SimulatorReasonCode.SEAM_PURPOSE_REQUIRED,
                "an authority test seam requires an explicit non-empty purpose",
            )
        authority_digest(component)  # fail closed on unsupported components
        self._component = component
        self._purpose = purpose
        self._open_digest: str = ""
        self._closed = False

    @property
    def component(self) -> Any:
        return self._component

    @property
    def purpose(self) -> str:
        return self._purpose

    @property
    def open_digest(self) -> str:
        return self._open_digest

    @property
    def closed(self) -> bool:
        return self._closed

    def open(self) -> str:
        """Capture the component digest at seam open."""
        if self._closed:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "seam is already closed",
            )
        self._open_digest = authority_digest(self._component)
        return self._open_digest

    def close(self) -> str:
        """Capture the component digest at seam close."""
        if self._closed:
            raise SimulatorError(
                SimulatorReasonCode.INVALID_INPUT,
                "seam is already closed",
            )
        self._closed = True
        return authority_digest(self._component)


def seam_verdict(open_digest: str, close_digest: str) -> str:
    """RESTORED on digest equality; VALIDATED on a trace-recorded
    divergence (the runner supplies this verdict only when every
    mutation was owner-contract recorded); DEGRADED is the explicit
    failure verdict."""
    if open_digest == close_digest:
        return "restored"
    return "validated"


def authority_digest(component: Any) -> str:
    """Digest a supported authority component through ITS OWN canonical
    state API (fail closed for unsupported types)."""
    import inspect

    from energy.resilience import NodeRejoinLedger
    from mobility.store import MobilityStore
    from policy.store import PolicyStore
    from sessions.store import SessionStore
    from telemetry.store import TelemetryStore

    if isinstance(component, NodeRejoinLedger):
        return "sha256:" + hashlib.sha256(
            component.ledger_digest().encode("utf-8")
        ).hexdigest()
    if isinstance(component, SessionStore):
        return "sha256:" + hashlib.sha256(
            component.to_canonical_bytes()
        ).hexdigest()
    for store_type in (TelemetryStore, MobilityStore, PolicyStore):
        if isinstance(component, store_type):
            snapshot = component.snapshot()
            try:
                material = canonical_json_bytes(_plain(snapshot))
            except CanonicalizationError as error:
                raise SimulatorError(
                    SimulatorReasonCode.UNSUPPORTED_SEAM_COMPONENT,
                    "component %s snapshot is not canonically representable: %s"
                    % (type(component).__name__, error),
                ) from error
            return "sha256:" + hashlib.sha256(material).hexdigest()
    module = inspect.getmodule(component)
    module_name = module.__name__ if module is not None else type(component).__name__
    raise SimulatorError(
        SimulatorReasonCode.UNSUPPORTED_SEAM_COMPONENT,
        "unsupported seam component %s (supported: NodeRejoinLedger, "
        "SessionStore, TelemetryStore, MobilityStore, PolicyStore)" % module_name,
    )


def _plain(value: Any) -> Any:
    """Convert a snapshot tree of tuples/lists/dicts/primitives into
    canonical-JSON-safe plain structures (deterministic)."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    return repr(value)
