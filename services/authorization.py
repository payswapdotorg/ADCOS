"""ADCOS service-layer authorization consumption seam (WORK-025).

This module is the ONLY place the service layer interprets WORK-010
policy decisions for invocation authorization.  It exists to close the
authority boundary flagged in the Architect review of PR #26
(blocker 2):

    the service layer must never be able to take a valid ALLOW
    decision and manufacture a different authorization scope
    (service / session / caller / tenant) around it.

The closure is STRUCTURAL: the authorized invocation scope travels
INSIDE the ``policy.model.PolicyDecision`` as an ``extensions`` entry
(the frozen WORK-010 "opaque WORK-003-style mappings" surface), and
because the ``decision_id`` is the content-derived digest over the
decision's canonical bytes -- extensions included -- the binding is
tamper-evident by the same sha256 that already protects the decision.
``ServiceRegistry.apply_policy_decision`` therefore accepts NO scope
parameters at all: it extracts the scope from the decision's own
digest-covered content (:func:`extract_invocation_binding`), so a
rebound decision fails the digest check and a decision without a
binding fails closed.

Composition contract (the composition root is the trusted wiring
point that knows the actual invocation being authorized):

1. build a REAL ``PolicyContext`` for the frozen WORK-010 operation
   ``service.invoke`` -- requester_node_id = the caller, resource_refs
   = (service_ref,), federation_domain = the owning tenant -- and
   evaluate it with the REAL ``PolicyEngine`` under the active
   ``PolicySet`` snapshot;
2. if (and only if) the engine's terminal effect is ALLOW, bind the
   authorized scope onto the decision with
   :func:`bind_invocation_decision` and hand the BOUND decision to
   ``ServiceRegistry.apply_policy_decision``.

``bind_invocation_decision`` is deliberately dumb: it never changes
the effect, code, matched rules, or policy-set identity -- it only
attaches the invocation binding and recomputes the content-derived
``decision_id``.  The service layer remains a policy CONSUMER
(WORK-025 invariant 3): nothing here evaluates rules, invents trust,
or overrides a deny.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from policy.model import PolicyDecision

from .errors import ServiceError, ServiceReasonCode
from .validation import (
    validate_node_id,
    validate_opaque_ref,
    validate_session_ref,
    validate_tenant_domain,
)

#: Discriminator carried inside the binding extension mapping.  The
#: frozen WORK-003-style extension surface is opaque to the policy
#: authority; this marker is what the SERVICE layer looks for, so
#: foreign extensions can never be mistaken for an invocation binding.
INVOCATION_BINDING_KIND = "adcos.service-invocation"

#: The frozen WORK-010 ``Operation`` value an invocation decision must
#: authorize.  Kept as a local constant and cross-checked byte-for-byte
#: against ``policy.model.Operation.SERVICE_INVOKE`` by the WORK-025
#: selftest (the WORK-023 lazy-vocabulary discipline: a local constant,
#: verified against the authority instead of importing it here).
SERVICE_INVOKE_OPERATION = "service.invoke"

#: The exact key set of a binding extension mapping (strict schema:
#: unknown keys fail closed, so nothing can be smuggled alongside the
#: authorized scope).
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

    def to_mapping(self) -> Mapping[str, Any]:
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
    an invocation scope (DECISION_SCOPE_MISMATCH), more than one is
    ambiguous (DECISION_SCOPE_MISMATCH), a malformed binding is
    INVALID_INPUT, and a binding for another operation is a scope
    mismatch.  The caller MUST have verified the decision's digest
    first, so the extracted scope is tamper-evident.
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
            "(fail closed; scope can never be supplied separately)"
            % (INVOCATION_BINDING_KIND,),
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


def bind_invocation_decision(
    policy_decision: PolicyDecision,
    *,
    service_ref: str,
    session_id: str = "",
    caller_node_id: str = "",
    tenant_domain: str,
) -> PolicyDecision:
    """Composition-root helper: bind an invocation scope onto a
    GENUINE engine decision.

    The input decision's own digest is verified first (the binding
    chain never starts from tampered DATA).  The effect, code,
    detail, matched rules, policy-set identity, evaluation instant,
    and conflict trace are carried over VERBATIM; the invocation
    binding is appended to ``extensions`` and the ``decision_id`` is
    recomputed as the content-derived digest of the bound content --
    so the returned decision is tamper-evident against any later
    scope manipulation.

    This helper NEVER upgrades an effect: binding a DENY is possible
    only to produce an auditable artifact; the registry still fails
    closed on any non-allow effect at apply time.
    """
    if not isinstance(policy_decision, PolicyDecision):
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "policy_decision must be a genuine policy.model."
            "PolicyDecision (WORK-010 authority; the service layer "
            "never evaluates policy)",
        )
    expected_id = hashlib.sha256(
        policy_decision.canonical_bytes()
    ).hexdigest()
    if policy_decision.decision_id != expected_id:
        raise ServiceError(
            ServiceReasonCode.INVALID_INPUT,
            "policy decision id does not bind to the decision's "
            "canonical bytes (tampered decision rejected before "
            "binding)",
        )
    binding = InvocationBinding(
        operation=SERVICE_INVOKE_OPERATION,
        service_ref=service_ref,
        session_id=session_id,
        caller_node_id=caller_node_id,
        tenant_domain=tenant_domain,
    )
    extensions: Tuple[Mapping[str, Any], ...] = tuple(policy_decision.extensions) + (
        binding.to_mapping(),
    )
    bound = PolicyDecision(
        decision_id="0" * 64,
        effect=policy_decision.effect,
        code=policy_decision.code,
        detail=policy_decision.detail,
        matched_rule_ids=policy_decision.matched_rule_ids,
        policy_set_id=policy_decision.policy_set_id,
        policy_set_version=policy_decision.policy_set_version,
        evaluation_instant=policy_decision.evaluation_instant,
        conflict_trace=policy_decision.conflict_trace,
        extensions=extensions,
    )
    return PolicyDecision(
        decision_id=hashlib.sha256(bound.canonical_bytes()).hexdigest(),
        effect=bound.effect,
        code=bound.code,
        detail=bound.detail,
        matched_rule_ids=bound.matched_rule_ids,
        policy_set_id=bound.policy_set_id,
        policy_set_version=bound.policy_set_version,
        evaluation_instant=bound.evaluation_instant,
        conflict_trace=bound.conflict_trace,
        extensions=bound.extensions,
    )


__all__ = [
    "INVOCATION_BINDING_KIND",
    "SERVICE_INVOKE_OPERATION",
    "InvocationBinding",
    "extract_invocation_binding",
    "bind_invocation_decision",
]
