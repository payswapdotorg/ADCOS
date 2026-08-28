"""ADCOS service-layer authorization consumption seam (WORK-025).

This module is the ONLY place the service layer interprets WORK-010
policy decisions for invocation authorization.  It exists to enforce
the authority boundary required by the Architect review of PR #26
(blocker 2, remediation 2 -- comment 5434924645):

    WORK-010 policy authority / composition root
            ->
    decision already bound to exact invocation context
            ->
    services verification + extraction ONLY   <-- this module
            ->
    execution

The invocation scope a ``service.invoke`` decision authorizes is
established UPSTREAM, inside the policy authority: the composition
root declares the exact (service, session, caller, tenant) scope as an
``adcos.service-invocation`` descriptor in the
``PolicyContext.extensions`` (the frozen WORK-003-style opaque
surface), and the WORK-010 evaluator derives the binding from that
descriptor with strict mirror checks against the first-class context
fields (``policy.invocation.invocation_binding_from_context``), so
every ``service.invoke`` decision the engine emits is BORN carrying
its exact invocation scope among its ``extensions`` -- covered by the
decision's content-derived ``decision_id`` digest.

This module deliberately possesses NO binding-construction capability:
there is no function here (or anywhere in the ``services`` package)
that can take an ALLOW decision and attach, rewire, or re-stamp an
authorization scope around it.  The service layer is a pure policy
CONSUMER (WORK-025 invariant 3): it verifies the decision's own
tamper-evidence and EXTRACTS the scope the decision itself carries.

``ServiceRegistry.apply_policy_decision`` therefore accepts NO scope
parameters at all: the scope comes from the decision's own
digest-covered content (:func:`extract_invocation_binding`), so a
decision with no binding fails closed, a decision whose binding was
re-stamped fails the digest check, and the only way to obtain a bound
decision at all is to have the policy authority evaluate the exact
invocation context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from policy.invocation import INVOCATION_BINDING_KIND
from policy.model import PolicyDecision

from .errors import ServiceError, ServiceReasonCode
from .validation import (
    validate_node_id,
    validate_opaque_ref,
    validate_session_ref,
    validate_tenant_domain,
)

#: ``INVOCATION_BINDING_KIND`` (imported above) is the discriminator
#: carried inside the invocation binding of a BORN-BOUND engine
#: decision.  It is owned by the WORK-010 policy authority
#: (``policy.invocation``) and imported here read-only for consumers;
#: the service layer never defines (and never mints) it.  The
#: companion authority-side pieces are
#: ``policy.invocation.INVOCATION_BINDING_KEYS`` (the strict descriptor
#: schema) and ``policy.invocation.invocation_binding_from_context``
#: (the fail-closed derivation the engine applies to every
#: service.invoke evaluation).  Nothing in ``services`` can construct
#: a binding.

#: The frozen WORK-010 ``Operation`` value an invocation decision must
#: authorize.  Kept as a local constant and cross-checked byte-for-byte
#: against ``policy.model.Operation.SERVICE_INVOKE`` by the WORK-025
#: selftest (the WORK-023 lazy-vocabulary discipline: a local constant,
#: verified against the authority instead of importing it here).
SERVICE_INVOKE_OPERATION = "service.invoke"

#: The exact key set of an invocation binding mapping (strict schema:
#: unknown keys fail closed, so nothing can be smuggled alongside the
#: authorized scope).  Mirrors the authority-side schema
#: (``policy.invocation.INVOCATION_BINDING_KEYS``); cross-checked by
#: the WORK-025 selftest so the two definitions can never drift.
_BINDING_KEYS = frozenset(
    {
        "kind",
        "operation",
        "service_ref",
        "session_id",
        "caller_node_id",
        "tenant_domain",
    }
)


@dataclass(frozen=True)
class InvocationBinding:
    """The invocation scope a policy decision authorizes, extracted
    from the decision's own tamper-evident content.

    ``session_id`` / ``caller_node_id`` may be empty (an invocation
    not bound to a governing session or an anonymous-node caller --
    exactly what the composition root put in the authorized context);
    ``tenant_domain`` is always explicit (tenant isolation is never
    optional on the authorization path either)."""

    operation: str
    service_ref: str
    session_id: str
    caller_node_id: str
    tenant_domain: str

    def __post_init__(self) -> None:
        if self.operation != SERVICE_INVOKE_OPERATION:
            raise ServiceError(
                ServiceReasonCode.DECISION_SCOPE_MISMATCH,
                "invocation binding authorizes operation %r, not the "
                "frozen WORK-010 %r operation (a decision evaluated for "
                "another operation is a scope mismatch and fails closed)"
                % (self.operation, SERVICE_INVOKE_OPERATION),
            )
        object.__setattr__(
            self, "service_ref", validate_opaque_ref(self.service_ref, "service")
        )
        if self.session_id:
            object.__setattr__(self, "session_id", validate_session_ref(self.session_id))
        if self.caller_node_id:
            object.__setattr__(
                self, "caller_node_id",
                validate_node_id(self.caller_node_id, label="caller node id"),
            )
        object.__setattr__(
            self, "tenant_domain", validate_tenant_domain(self.tenant_domain)
        )
        if not self.tenant_domain:
            raise ServiceError(
                ServiceReasonCode.TENANT_ISOLATION,
                "an invocation binding must carry an explicit tenant "
                "domain (tenant-scoped authorization is never optional)",
            )

    def to_mapping(self) -> Mapping[str, str]:
        return {
            "kind": INVOCATION_BINDING_KIND,
            "operation": self.operation,
            "service_ref": self.service_ref,
            "session_id": self.session_id,
            "caller_node_id": self.caller_node_id,
            "tenant_domain": self.tenant_domain,
        }

    def scope(self) -> Tuple[str, str, str, str]:
        """The authorization scope tuple (service, session, caller,
        tenant) -- the exact scope the decision authorizes."""
        return (
            self.service_ref,
            self.session_id,
            self.caller_node_id,
            self.tenant_domain,
        )


def extract_invocation_binding(
    policy_decision: PolicyDecision,
) -> InvocationBinding:
    """Extract the invocation binding from a REAL policy decision's
    own ``extensions`` (fail closed).

    Exactly one ``adcos.service-invocation`` binding must be present:
    a decision with NO binding is a decision that was never tied to
    an invocation scope (DECISION_SCOPE_MISMATCH -- the engine emits
    such bindings only for born-bound service.invoke evaluations, so
    an unbound decision is one that was never authorized for ANY
    invocation), more than one is ambiguous (DECISION_SCOPE_MISMATCH),
    a malformed binding is INVALID_INPUT, and a binding for another
    operation is a scope mismatch.  The caller MUST have verified the
    decision's digest first, so the extracted scope is tamper-evident.
    """
    bindings = []
    for extension in policy_decision.extensions:
        kind = extension.get("kind") if hasattr(extension, "get") else None
        if kind == INVOCATION_BINDING_KIND:
            bindings.append(extension)
    if not bindings:
        raise ServiceError(
            ServiceReasonCode.DECISION_SCOPE_MISMATCH,
            "policy decision carries no %r invocation binding -- the "
            "authorized operation/context is not tied to the decision "
            "(fail closed; scope can never be supplied separately and "
            "the services layer possesses no binding construction "
            "capability)" % (INVOCATION_BINDING_KIND,),
        )
    if len(bindings) > 1:
        raise ServiceError(
            ServiceReasonCode.DECISION_SCOPE_MISMATCH,
            "policy decision carries %d invocation bindings (exactly "
            "one is required; ambiguity fails closed)" % (len(bindings),),
        )
    binding = bindings[0]
    if not _BINDING_KEYS.issuperset(binding.keys()):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "invocation binding carries unknown keys %s (strict schema; "
            "nothing rides alongside the authorized scope)"
            % (sorted(set(binding.keys()) - _BINDING_KEYS),),
        )
    missing = _BINDING_KEYS - set(binding.keys())
    if missing:
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "invocation binding is missing keys %s" % (sorted(missing),),
        )
    return InvocationBinding(
        operation=binding["operation"],
        service_ref=binding["service_ref"],
        session_id=binding["session_id"],
        caller_node_id=binding["caller_node_id"],
        tenant_domain=binding["tenant_domain"],
    )


__all__ = [
    "INVOCATION_BINDING_KIND",
    "SERVICE_INVOKE_OPERATION",
    "InvocationBinding",
    "extract_invocation_binding",
]
