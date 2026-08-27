"""ADCOS service registry / edge compute contracts (WORK-025).

The provider-neutral edge execution seam (mirrors the WORK-024
breakout contract discipline):

- :class:`ExecutionProviderContract` -- the abstract execution
  provider surface (open / admit / execute / release / observe /
  health / close).  A provider is an EXTERNAL execution
  implementation detail behind an interface (LOCK-016); the core
  service semantics never depend on any concrete runtime, container,
  VM, or vendor edge platform (LOCK-017).
- :class:`ServiceContext` -- the least-authority facade handed to
  every provider operation: the integration id, the injected instant,
  the step budget, and (optionally) a read-only session reader.  A
  provider receives NOTHING else -- no registry tables, no policy
  internals, no identity store, no federation state, no credentials
  (WORK-025 invariant 10).
- :class:`SessionReader` / :class:`SessionView` -- the read-only
  WORK-012 projection (identical in spirit to the WORK-023/024
  session readers; deliberately re-declared here so the service layer
  never imports the session authority -- a test double implements
  this same interface).
- :class:`FederationReader` -- the read-only WORK-015 scope-check
  projection consumed as federation-scoped DATA (the service layer
  never imports federation trust state; a test double or the
  composition root adapts the real ``FederationStore.check_scope``).

The execution surface rejects unauthorized invocations before
provider-side effects (authorization is verified by the registry
BEFORE any provider operation is attempted), carries service identity
explicitly, carries caller/session references only as opaque
authorized DATA, isolates provider exceptions as typed failure
values, and accounts deterministically against a step budget.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from .errors import ServiceError, ServiceReasonCode
from .model import ServiceAdmission, ExecutionOutcome, ServiceObservation
from .validation import validate_instant, validate_opaque_ref

#: Maximum step budget handed to a provider context by default.
DEFAULT_STEP_BUDGET = 10000


class _BudgetExhausted(Exception):
    """Internal sentinel: the provider overdrawn its step budget.

    Never crosses the sandbox boundary as an exception; the sandbox
    converts it into a typed :class:`~services.errors.ServiceFailure`
    value (BUDGET_EXHAUSTED)."""

    __slots__ = ()


@dataclass(frozen=True)
class SessionView:
    """Secret-free WORK-012 session projection (the only session facts
    the service layer may see)."""

    session_id: str
    secureable: bool
    initiator_node_id: str
    responder_node_id: str


class SessionReader(abc.ABC):
    """Read-only session lookup (the WORK-012 surface the service
    boundary may see -- ``lookup`` and nothing else).  The facade
    deliberately exposes NOTHING mutating: no transition, no append,
    no event write.  A test double implements this same interface
    (the import-lock rule for test doubles)."""

    __slots__ = ()

    @abc.abstractmethod
    def lookup(self, session_id: str) -> Optional[SessionView]:
        """Return the secret-free session view, or ``None`` when the
        session does not exist."""


class FederationReader(abc.ABC):
    """Read-only federation scope-check projection (the WORK-015
    surface the service boundary may see -- one scope check and
    nothing else).  The service layer carries federation references,
    scope, and exposure policy as DATA; it never imports federation
    trust state (WORK-025 invariant 4).  The composition root adapts
    the real ``FederationStore.check_scope`` behind this interface; a
    test double implements it directly."""

    __slots__ = ()

    @abc.abstractmethod
    def check_scope(
        self, relationship_id: str, scope: str, *, evaluation_instant: str
    ) -> Tuple[bool, str]:
        """Return ``(allowed, detail_code)`` for one relationship /
        scope at the injected instant.  ``allowed`` is ``False`` for
        unknown relationships (fail closed)."""


class _AbsentSessionReader(SessionReader):
    """Fail-closed reader used when no session authority was injected:
    every lookup misses (nothing is secureable without the
    authority)."""

    __slots__ = ()

    def lookup(self, session_id: str) -> Optional[SessionView]:
        return None


class ServiceContext:
    """Immutable least-authority execution context (mirrors the
    WORK-024 ``BreakoutContext`` discipline).

    Exposes exactly: the integration id, the injected ``now``, the
    step budget ``charge``/``steps_left``, and the read-only session
    reader.  No wall clock exists anywhere in this layer; no registry
    state, policy internal, identity store, or credential is
    reachable from a context."""

    __slots__ = ("_integration_id", "_instant", "_steps_left", "_session_reader")

    _integration_id: str
    _instant: str
    _steps_left: int
    _session_reader: SessionReader

    def __init__(
        self,
        *,
        integration_id: str,
        instant: str,
        step_budget: int,
        session_reader: Optional[SessionReader] = None,
    ) -> None:
        if not isinstance(integration_id, str) or not integration_id:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "context integration_id must be a non-empty str",
            )
        validate_instant(instant, label="context instant")
        if isinstance(step_budget, bool) or not isinstance(step_budget, int):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "context step_budget must be an int",
            )
        if step_budget < 0:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "context step_budget must be non-negative",
            )
        reader = session_reader
        if reader is not None and not isinstance(reader, SessionReader):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "session_reader must implement the SessionReader ABC",
            )
        object.__setattr__(self, "_integration_id", integration_id)
        object.__setattr__(self, "_instant", instant)
        object.__setattr__(self, "_steps_left", step_budget)
        object.__setattr__(
            self, "_session_reader", reader if reader is not None else _AbsentSessionReader()
        )

    # -- immutability (structural least authority) --------------------- #

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(
            "ServiceContext is an immutable least-authority facade "
            "(attribute %r cannot be assigned)" % (name,)
        )

    def __delattr__(self, name: str) -> None:
        raise TypeError(
            "ServiceContext is an immutable least-authority facade "
            "(attribute %r cannot be deleted)" % (name,)
        )

    # -- surface -------------------------------------------------------- #

    @property
    def integration_id(self) -> str:
        return self._integration_id

    def now(self) -> str:
        """The injected instant (no wall clock exists in this layer)."""
        return self._instant

    def charge(self, steps: int = 1) -> None:
        if isinstance(steps, bool) or not isinstance(steps, int):
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "charge steps must be an int",
            )
        if steps < 0:
            raise ServiceError(
                ServiceReasonCode.INVALID_INPUT,
                "charge steps must be non-negative",
            )
        if steps > self._steps_left:
            raise _BudgetExhausted()
        object.__setattr__(self, "_steps_left", self._steps_left - steps)

    def steps_left(self) -> int:
        return self._steps_left

    def session_reader(self) -> SessionReader:
        return self._session_reader


#: The frozen public surface of a :class:`ServiceContext` (pinned by
#: the WORK-025 selftest).
CONTEXT_SURFACE = frozenset(
    {"integration_id", "now", "charge", "steps_left", "session_reader"}
)


class ExecutionProviderContract(abc.ABC):
    """The provider-neutral edge execution seam (WORK-025).

    Implementations are external execution providers (reference
    in-process executor, a real edge runtime behind an adapter, ...).
    ``label`` is informational only and never enters canonical state.
    Operations are keyword-only after ``context`` so the surface
    cannot silently grow positional parameters."""

    __slots__ = ()

    #: Informational provider label (diagnostics only).
    label: str = ""

    @abc.abstractmethod
    def open(self, context: ServiceContext) -> None:
        """Open the provider (lifecycle)."""

    @abc.abstractmethod
    def admit(
        self,
        context: ServiceContext,
        *,
        service_ref: str,
        host_node_id: str,
        tenant_domain: str,
        session_id: str,
        decision_ref: str,
        requirements: Any = None,
    ) -> ServiceAdmission:
        """Prepare / admit one execution: provider-side readiness and
        a standing admission lease.  Authorization has already been
        verified by the registry BEFORE this operation runs."""

    @abc.abstractmethod
    def execute(
        self,
        context: ServiceContext,
        *,
        admission_ref: str,
        request_payload: bytes,
        requirements: Any = None,
    ) -> ExecutionOutcome:
        """Execute one request under a standing admission and return
        the provider-neutral outcome (explicit status; partial
        failures explicit in ``detail``)."""

    @abc.abstractmethod
    def release(
        self, context: ServiceContext, *, admission_ref: str
    ) -> None:
        """Cancel / release a standing admission."""

    @abc.abstractmethod
    def observe(self, context: ServiceContext) -> ServiceObservation:
        """Honest provider-side observation at the injected instant."""

    @abc.abstractmethod
    def health(self) -> str:
        """Provider health ladder: HEALTHY / DEGRADED / FAILED /
        NOT_RUNNING."""

    @abc.abstractmethod
    def close(self, context: ServiceContext) -> None:
        """Close the provider (fails closed with outstanding
        admissions)."""


#: The frozen contract operation order (pinned by the WORK-025
#: selftest).
CONTRACT_OPERATIONS: Tuple[str, ...] = (
    "open", "admit", "execute", "release", "observe", "health", "close",
)


def validate_admission_ref(value: object) -> str:
    """Validate an admission ref (re-exported convenience used by both
    the sandbox and the reference executor)."""
    return validate_opaque_ref(value, "admission")


__all__ = [
    "DEFAULT_STEP_BUDGET",
    "SessionView",
    "SessionReader",
    "FederationReader",
    "ServiceContext",
    "CONTEXT_SURFACE",
    "ExecutionProviderContract",
    "CONTRACT_OPERATIONS",
    "validate_admission_ref",
]
