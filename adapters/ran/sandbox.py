"""ADCOS 5G RAN integration sandbox (WORK-020): the failure-isolation
boundary.

:class:`SandboxedRan` mediates EVERY call from the manager to a 5G RAN
integration implementation.  The mediator guarantees, mechanically
(mirroring the WORK-016 adapter SDK, WORK-017 transport, WORK-018 IP
integration, and WORK-019 5G Core integration sandboxes):

1. **Exception isolation** -- any exception the implementation raises
   (``Exception`` AND ``BaseException``: a ``SystemExit`` or
   ``KeyboardInterrupt`` from a vendor RAN SDK crashes the operation,
   never the manager) is converted into a typed
   :class:`adapters.ran.errors.RanFailure` VALUE.  RAN-side faults
   never propagate into core callers as exceptions.  Exception MESSAGE
   TEXT is deliberately NOT captured (LOCK-023: an implementation
   cannot leak credential-like material through failure diagnostics).

2. **Contract enforcement** -- every return value is validated against
   the frozen contract shape BEFORE it can reach the caller.  A
   non-contract return is a ``CONTRACT_VIOLATION`` failure and is
   DISCARDED; it can never be stored, keyed, or echoed.  Opaque
   references are checked against the frozen ``ran:<kind>:<hex>``
   grammar and scanned for credential-like material, ``observe``
   returns are deep-validated by reconstruction, and a bearer
   reference returned by ``bind_session`` that equals or embeds the
   caller's sacred ``session_id`` (or vice versa) is rejected at the
   seam (the R1 identity-separation rule, LOCK-006).

3. **Deterministic budget** -- each operation receives a fresh
   least-authority :class:`RanContext` carrying the step budget; the
   sandbox charges the fixed per-operation :data:`STEP_CHARGES` step
   (the WORK-016 ``GenericAdapter`` charge-table discipline) before
   delegating, and the implementation may charge its own additional
   work against the same context; spending beyond the budget is the
   deterministic model of a hung operation (``BUDGET_EXHAUSTED``).
   There is no wall-clock timeout anywhere in the RAN integration
   layer.  The two context-free contract operations (``capabilities``,
   ``health``) receive no :class:`RanContext` by contract, so their
   table entries pin the family's charge vocabulary but are not
   chargeable at mediation.

4. **Least authority** -- implementations receive ONLY the context
   facade: no session stores, no identity material, no credential
   material, no policy engines, no topology graphs, no resource
   stores, no manager references.

5. **Health accounting** -- consecutive-failure counting drives the
   deterministic DEGRADED/FAILED thresholds; successes reset the
   consecutive counter (probes never do).

The sandbox knows nothing about sessions, identity, radio parameters,
or topology: it is pure mediation between the manager and the
implementation.  The split of error responsibility mirrors the accepted
family discipline: CALLER-side input/state errors (malformed refs, bad
``session_id``, non-bytes payload, malformed provision request) RAISE
:class:`RanError` BEFORE the implementation is invoked;
IMPLEMENTATION-side faults (raising, shape violations, budget
exhaustion, unknown gNB/cell/bearer/allocation reported by the
implementation) RETURN a :class:`RanOpResult` failure VALUE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional

from .contract import RanContext, RanContract, _BudgetExhausted
from .errors import RanError, RanFailure, RanReasonCode
from .model import (
    GnbProvisionRequest,
    HealthState,
    RAN_CAPABILITY_REFERENCES,
)
from .validation import (
    assert_ref_session_separation,
    reject_credential_like_text,
    validate_gnb_provision_request,
    validate_opaque_ref,
    validate_ran_capability_reference,
    validate_ran_observation,
    validate_session_id,
)

__all__ = [
    "RanOpResult",
    "SandboxedRan",
    "DEFAULT_STEP_BUDGET",
    "FAILURE_THRESHOLD_DEGRADED",
    "FAILURE_THRESHOLD_FAILED",
    "STEP_CHARGES",
]

#: Default deterministic step budget (mirrors WORK-016/W018/W019).
DEFAULT_STEP_BUDGET = 10000

#: Deterministic health thresholds (mirrors WORK-016/W018/W019).
FAILURE_THRESHOLD_DEGRADED = 2
FAILURE_THRESHOLD_FAILED = 5

#: Fixed per-operation step charges (the WORK-016
#: ``GenericAdapter.STEP_CHARGES`` discipline, extended with the
#: RAN-local operations).  The sandbox charges exactly this fixed step
#: against the fresh per-call context before delegating to the
#: implementation; the implementation may charge its own additional
#: work against the same context, so the total charge per operation is
#: deterministic.  The two context-free contract operations
#: (``capabilities``, ``health``) take no :class:`RanContext` and
#: therefore charge nothing -- their entries pin the family-wide
#: charge vocabulary (a later bridge that mediates them through a
#: context-bearing path charges the same table).
STEP_CHARGES: Dict[str, int] = {
    "open": 4,
    "close": 4,
    "capabilities": 1,
    "observe": 2,
    "provision_gnb": 10,
    "decommission_gnb": 4,
    "activate_cell": 3,
    "deactivate_cell": 3,
    "bind_session": 6,
    "unbind_session": 3,
    "egress_data": 2,
    "allocate": 10,
    "release": 4,
    "health": 1,
}

#: Contract-shape bounds for implementation return values (mirrors the
#: WORK-016/W018 sandbox bounds): a hostile implementation cannot
#: flood the caller with unbounded reference or capability garbage.
MAX_REF_LENGTH = 256
MAX_CAPABILITY_REFS = 64


def _require_non_empty_str(value: Any, what: str) -> None:
    """Caller-side shape check: a non-empty string or ``RanError``."""
    if not isinstance(value, str) or not value:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % what,
        )


class _ContractViolation:
    """Internal sentinel: the implementation returned a value that does
    not satisfy the frozen contract shape.  The sandbox discards the
    value (never stores, keys, or echoes it) and reports a
    ``CONTRACT_VIOLATION`` failure."""

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        self.detail = detail


@dataclass
class RanOpResult:
    """The mediated result of a RAN integration operation.

    * ``ok=True``: ``value`` carries the validated contract return.
    * ``ok=False``: ``failure`` carries the typed, isolated
      :class:`RanFailure` (never an exception).  ``detail`` is a
      generic, secret-free diagnostic string (exception message text
      is NEVER captured -- LOCK-023).

    Caller-side input/state errors (malformed refs, bad ``session_id``,
    non-bytes payload, malformed provision request) RAISE
    :class:`RanError` before the implementation is invoked;
    implementation-side faults RETURN this typed value.
    """

    ok: bool
    value: Any = None
    failure: Optional[RanFailure] = None
    detail: str = ""

    @property
    def reason(self) -> str:
        return self.failure.reason_code if self.failure is not None else ""

    def __bool__(self) -> bool:
        return self.ok


class SandboxedRan:
    """The failure-isolation mediator for a 5G RAN integration
    implementation.

    Constructed with a :class:`RanContract` implementation (NOT
    ``hasattr`` duck-typed -- ``isinstance`` enforced) and the
    integration instance id.  Every public method validates caller
    input, builds a fresh :class:`RanContext` (the injected instant
    plus the step budget -- a fresh budget per call), charges the
    fixed :data:`STEP_CHARGES` step, delegates to the implementation,
    validates the return against the frozen contract shape, and returns
    a :class:`RanOpResult`.  A per-call ``step_budget`` keyword
    overrides the constructor budget for that one operation.

    The sandbox never consults a wall clock: the instant of every
    operation comes ONLY from the injected ``now`` argument
    (WORK-003 grammar).
    """

    def __init__(
        self,
        implementation: RanContract,
        *,
        ran_integration_id: str,
        step_budget: int = DEFAULT_STEP_BUDGET,
    ) -> None:
        if not isinstance(implementation, RanContract):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "implementation must satisfy the RanContract ABC "
                "(isinstance enforced; no hasattr duck-typing)",
            )
        if not isinstance(ran_integration_id, str) or not ran_integration_id:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "ran_integration_id must be a non-empty string",
            )
        if isinstance(step_budget, bool) or not isinstance(step_budget, int):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "step_budget must be an integer",
            )
        self._implementation = implementation
        self._ran_integration_id = ran_integration_id
        self._step_budget = step_budget
        # Health accounting (mirrors WORK-016/W018/W019).
        self._consecutive_failures = 0
        self._total_failures = 0
        self._total_contract_violations = 0
        self._open = False

    # ------------------------------------------------------------------
    # Least-authority context construction
    # ------------------------------------------------------------------

    def _context(self, now: str, step_budget: Optional[int]) -> RanContext:
        """Build the fresh per-call context.

        The :class:`RanContext` constructor performs the caller-side
        shape checks on the instant and the budget (a bad ``now`` or a
        bad per-call ``step_budget`` raises :class:`RanError` here --
        BEFORE the implementation is invoked).
        """
        budget = self._step_budget if step_budget is None else step_budget
        return RanContext(
            ran_integration_id=self._ran_integration_id,
            instant=now,
            step_budget=budget,
        )

    # ------------------------------------------------------------------
    # Universal mediation guard
    # ------------------------------------------------------------------

    def _mediate(
        self,
        operation: str,
        body: Callable[[], Any],
        *,
        validate: Callable[[Any], Any],
        context: Optional[RanContext] = None,
    ) -> RanOpResult:
        """Charge the fixed step (when a context crosses the seam),
        delegate to ``body``, validate the return, and convert every
        exception (including ``BaseException``) into an isolated
        failure value.

        The context is built by the CALLER of this method (outside the
        ``try``), so caller-side context errors raise; everything the
        implementation does happens inside the ``try`` and can never
        propagate (mirrors the WORK-019 ``SandboxedFiveGCore._mediate``
        mechanics exactly).
        """
        try:
            if context is not None:
                context.charge(STEP_CHARGES.get(operation, 1))
            value = body()
        except _BudgetExhausted:
            self._record_failure()
            return RanOpResult(
                ok=False,
                failure=RanFailure(
                    reason_code=RanReasonCode.BUDGET_EXHAUSTED,
                    ran_integration_id=self._ran_integration_id,
                    operation=operation,
                ),
                detail="RAN integration operation exceeded its deterministic "
                       "step budget (hang model); no wall clock is consulted",
            )
        except RanError as exc:
            # The reason CODE is safe (a vocabulary token).  The
            # exception MESSAGE TEXT (exc.detail) is deliberately NOT
            # captured -- an implementation cannot leak credential-like
            # material through failure diagnostics (LOCK-023).
            self._record_failure()
            return RanOpResult(
                ok=False,
                failure=RanFailure(
                    reason_code=exc.reason_code,
                    ran_integration_id=self._ran_integration_id,
                    operation=operation,
                ),
                detail="implementation raised RanError (reason=%s); "
                       "exception message text not captured" % exc.reason_code,
            )
        except BaseException as exc:  # full isolation: nothing crosses
            self._record_failure()
            return RanOpResult(
                ok=False,
                failure=RanFailure(
                    reason_code=RanReasonCode.RAN_FAILURE,
                    ran_integration_id=self._ran_integration_id,
                    operation=operation,
                    exception_class_name=type(exc).__name__,
                ),
                detail="implementation raised %s (message text not captured; "
                       "exception is fully isolated)" % type(exc).__name__,
            )
        validated = validate(value)
        if isinstance(validated, _ContractViolation):
            self._record_failure(violation=True)
            return RanOpResult(
                ok=False,
                failure=RanFailure(
                    reason_code=RanReasonCode.CONTRACT_VIOLATION,
                    ran_integration_id=self._ran_integration_id,
                    operation=operation,
                ),
                detail=validated.detail,
            )
        self._record_success()
        return RanOpResult(ok=True, value=validated)

    # ------------------------------------------------------------------
    # Return-shape validators (the frozen contract surface)
    # ------------------------------------------------------------------

    def _validate_nothing(self, value: Any) -> Any:
        if value is not None:
            return _ContractViolation("operation must return None")
        return value

    def _validate_capabilities(self, value: Any) -> Any:
        """Capabilities must be an ordered sequence of capability-id
        REFERENCES (a set or generator would be order-nondeterministic
        and is rejected; so is a bare string)."""
        if not isinstance(value, (tuple, list)):
            return _ContractViolation(
                "capabilities must return a sequence of capability "
                "reference strings"
            )
        if len(value) > MAX_CAPABILITY_REFS:
            return _ContractViolation(
                "capabilities returned more than %d references"
                % MAX_CAPABILITY_REFS
            )
        for capability in value:
            if not isinstance(capability, str):
                return _ContractViolation(
                    "capabilities entries must be strings"
                )
            if capability not in RAN_CAPABILITY_REFERENCES:
                try:
                    validate_ran_capability_reference(capability)
                except RanError:
                    return _ContractViolation(
                        "capabilities entries must be capability.access.ran.* "
                        "references (exposure only; never minted here)"
                    )
        return tuple(value)

    def _validate_observation(self, value: Any) -> Any:
        # Deep re-validation by reconstruction (the public per-op
        # return-shape validator); a violation becomes a
        # CONTRACT_VIOLATION failure value, never an exception.
        try:
            return validate_ran_observation(value)
        except RanError:
            return _ContractViolation(
                "observe must return a contract-shaped RanObservation "
                "(deep re-validation failed; the value is discarded)"
            )

    def _validate_opaque_ref(
        self,
        value: Any,
        *,
        prefix: str,
        what: str,
        session_id: Optional[str] = None,
    ) -> Any:
        """Validate an opaque RAN-side reference return value against
        the frozen grammar, the LOCK-023 credential scan, and (for
        ``bind_session`` results) the R1 session-separation check."""
        if not isinstance(value, str) or not value or len(value) > MAX_REF_LENGTH:
            return _ContractViolation(
                "%s must return an opaque ran:%s:* reference string" % (what, prefix)
            )
        try:
            validate_opaque_ref(value, prefix=prefix)
            reject_credential_like_text(value, what=what)
            if session_id is not None:
                # R1: the returned handle must never equal or embed the
                # sacred session_id (and vice versa) -- LOCK-006.
                assert_ref_session_separation(value, session_id)
        except RanError:
            return _ContractViolation(
                "%s returned a reference that violates the frozen "
                "ran:%s:* grammar, the LOCK-023 credential scan, or the "
                "R1 session-separation rule (value discarded)" % (what, prefix)
            )
        return value

    def _validate_bytes(self, value: Any) -> Any:
        if not isinstance(value, (bytes, bytearray)):
            return _ContractViolation("egress_data must return bytes")
        return bytes(value)

    def _validate_health(self, value: Any) -> Any:
        if not isinstance(value, str) or value not in HealthState.values():
            return _ContractViolation(
                "health must return one of %s" % (list(HealthState.values()),)
            )
        return value

    # ------------------------------------------------------------------
    # Health accounting
    # ------------------------------------------------------------------

    def _record_failure(self, *, violation: bool = False) -> None:
        self._consecutive_failures += 1
        self._total_failures += 1
        if violation:
            self._total_contract_violations += 1

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def computed_health(self) -> str:
        """The deterministic effective health from mediated outcomes."""
        if not self._open:
            return "NOT_RUNNING"
        if self._consecutive_failures >= FAILURE_THRESHOLD_FAILED:
            return "FAILED"
        if self._consecutive_failures >= FAILURE_THRESHOLD_DEGRADED:
            return "DEGRADED"
        return "HEALTHY"

    # ------------------------------------------------------------------
    # Public mediated operations (the 14 contract operations)
    # ------------------------------------------------------------------

    def open(self, now: str, *, step_budget: Optional[int] = None) -> RanOpResult:
        """Bring the RAN integration up (injected instant + budget)."""
        context = self._context(now, step_budget)
        result = self._mediate(
            "open",
            lambda: self._implementation.open(context),
            validate=self._validate_nothing,
            context=context,
        )
        if result.ok:
            self._open = True
        return result

    def close(self, now: str, *, step_budget: Optional[int] = None) -> RanOpResult:
        """Bring the RAN integration down (fails closed in the
        implementation while live bearers exist)."""
        context = self._context(now, step_budget)
        result = self._mediate(
            "close",
            lambda: self._implementation.close(context),
            validate=self._validate_nothing,
            context=context,
        )
        if result.ok:
            self._open = False
        return result

    def capabilities(self) -> RanOpResult:
        """Current capability-id REFERENCES (context-free by contract:
        no instant, no budget -- nothing crosses but the call)."""
        return self._mediate(
            "capabilities",
            lambda: self._implementation.capabilities(),
            validate=self._validate_capabilities,
        )

    def observe(self, now: str, *, step_budget: Optional[int] = None) -> RanOpResult:
        """The mapped RAN state snapshot (deep shape validation)."""
        context = self._context(now, step_budget)
        return self._mediate(
            "observe",
            lambda: self._implementation.observe(context),
            validate=self._validate_observation,
            context=context,
        )

    def provision_gnb(
        self,
        now: str,
        *,
        request: GnbProvisionRequest,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Provision a gNB; returns the opaque ``ran:gnb:<hex>`` ref.

        Caller-side: the request shape is validated (deep, by
        reconstruction) BEFORE the implementation is invoked.
        """
        validate_gnb_provision_request(request)
        context = self._context(now, step_budget)
        return self._mediate(
            "provision_gnb",
            lambda: self._implementation.provision_gnb(context, request=request),
            validate=lambda value: self._validate_opaque_ref(
                value, prefix="gnb", what="provision_gnb"
            ),
            context=context,
        )

    def decommission_gnb(
        self,
        now: str,
        *,
        gnb_ref: str,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Decommission a gNB by opaque reference (fails closed in the
        implementation while live bearers are served)."""
        validate_opaque_ref(gnb_ref, prefix="gnb")
        context = self._context(now, step_budget)
        return self._mediate(
            "decommission_gnb",
            lambda: self._implementation.decommission_gnb(context, gnb_ref=gnb_ref),
            validate=self._validate_nothing,
            context=context,
        )

    def activate_cell(
        self,
        now: str,
        *,
        gnb_ref: str,
        cell_id: str,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Activate a served cell (TS 38.413 activation semantics as
        adapter state; no RRC state machine crosses the seam)."""
        validate_opaque_ref(gnb_ref, prefix="gnb")
        _require_non_empty_str(cell_id, "cell_id")
        context = self._context(now, step_budget)
        return self._mediate(
            "activate_cell",
            lambda: self._implementation.activate_cell(
                context, gnb_ref=gnb_ref, cell_id=cell_id
            ),
            validate=self._validate_nothing,
            context=context,
        )

    def deactivate_cell(
        self,
        now: str,
        *,
        gnb_ref: str,
        cell_id: str,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Deactivate a served cell (live bearers degrade, never die --
        the honest DEGRADED state; egress fails closed meanwhile)."""
        validate_opaque_ref(gnb_ref, prefix="gnb")
        _require_non_empty_str(cell_id, "cell_id")
        context = self._context(now, step_budget)
        return self._mediate(
            "deactivate_cell",
            lambda: self._implementation.deactivate_cell(
                context, gnb_ref=gnb_ref, cell_id=cell_id
            ),
            validate=self._validate_nothing,
            context=context,
        )

    def bind_session(
        self,
        now: str,
        *,
        session_id: str,
        requirements: Optional[Mapping[str, Any]] = None,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Create a radio bearer for a WORK-012 session.

        The ``session_id`` is sacred, access-independent identity
        (LOCK-006): it crosses as an opaque READ-ONLY passthrough, and
        the returned bearer reference is mechanically checked to never
        equal or embed it (R1).  Caller-side shape errors raise BEFORE
        the implementation is invoked.
        """
        validate_session_id(session_id)
        if requirements is not None and not isinstance(requirements, Mapping):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "requirements must be a mapping or None",
            )
        context = self._context(now, step_budget)
        return self._mediate(
            "bind_session",
            lambda: self._implementation.bind_session(
                context, session_id=session_id, requirements=requirements
            ),
            validate=lambda value: self._validate_opaque_ref(
                value,
                prefix="bearer",
                what="bind_session",
                session_id=session_id,
            ),
            context=context,
        )

    def unbind_session(
        self,
        now: str,
        *,
        bearer_ref: str,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Tear down a radio bearer by opaque reference (releases the
        adapter-private UE context and the cell's PRB reservation)."""
        validate_opaque_ref(bearer_ref, prefix="bearer")
        context = self._context(now, step_budget)
        return self._mediate(
            "unbind_session",
            lambda: self._implementation.unbind_session(context, bearer_ref=bearer_ref),
            validate=self._validate_nothing,
            context=context,
        )

    def egress_data(
        self,
        now: str,
        *,
        bearer_ref: str,
        payload: bytes,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Carry the payload over the bearer's radio user plane
        (byte-exact return; non-bytes payload is a caller error)."""
        validate_opaque_ref(bearer_ref, prefix="bearer")
        if not isinstance(payload, (bytes, bytearray)):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "payload must be bytes",
            )
        context = self._context(now, step_budget)
        return self._mediate(
            "egress_data",
            lambda: self._implementation.egress_data(
                context, bearer_ref=bearer_ref, payload=payload
            ),
            validate=self._validate_bytes,
            context=context,
        )

    def allocate(
        self,
        now: str,
        *,
        kind: str,
        quantity_base: int,
        purpose: str,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Reserve radio capacity; returns the opaque
        ``ran:alloc:<hex>`` ref (WORK-016 allocate semantics: integer
        base units).  Kind MEMBERSHIP is implementation authority
        (the reference engine's vocabulary lives in
        :mod:`adapters.ran.engine`); the sandbox checks shape only."""
        _require_non_empty_str(kind, "kind")
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "quantity_base must be an integer",
            )
        if quantity_base < 0:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "quantity_base must be >= 0",
            )
        _require_non_empty_str(purpose, "purpose")
        reject_credential_like_text(purpose, what="purpose")
        context = self._context(now, step_budget)
        return self._mediate(
            "allocate",
            lambda: self._implementation.allocate(
                context, kind=kind, quantity_base=quantity_base, purpose=purpose
            ),
            validate=lambda value: self._validate_opaque_ref(
                value, prefix="alloc", what="allocate"
            ),
            context=context,
        )

    def release(
        self,
        now: str,
        *,
        technology_ref: str,
        step_budget: Optional[int] = None,
    ) -> RanOpResult:
        """Release a previously returned radio-capacity reservation."""
        validate_opaque_ref(technology_ref, prefix="alloc")
        context = self._context(now, step_budget)
        return self._mediate(
            "release",
            lambda: self._implementation.release(context, technology_ref=technology_ref),
            validate=self._validate_nothing,
            context=context,
        )

    def health(self) -> RanOpResult:
        """Implementation-local health (context-free by contract:
        reported, never authoritative by itself -- LOCK-017)."""
        return self._mediate(
            "health",
            lambda: self._implementation.health(),
            validate=self._validate_health,
        )

    # ------------------------------------------------------------------
    # Diagnostic surface (NOT canonical public state; B2)
    # ------------------------------------------------------------------

    def diagnostic_state(self) -> dict:
        return {
            "implementation_label": self._implementation.label,
            "computed_health": self.computed_health(),
            "consecutive_failures": self._consecutive_failures,
            "total_failures": self._total_failures,
            "total_contract_violations": self._total_contract_violations,
        }
