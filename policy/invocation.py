"""WORK-010 invocation-binding vocabulary and derivation (PR #26 blocker 2).

Authority statement (the PR #26 Architect review, comment 5434924645):

    WORK-010 policy authority / composition root
            ->
    decision already bound to exact invocation context
            ->
    services verification + extraction ONLY
            ->
    execution

This module is where the FIRST arrow lives.  The invocation scope a
``service.invoke`` policy decision authorizes -- the exact (service,
session, caller, tenant) quadruple -- is established HERE, inside the
policy authority, from the EVALUATION CONTEXT the rules actually
evaluated.  It is not a post-hoc decoration that any downstream layer
can append to an unrelated decision: the composition root declares the
invocation scope as an opaque descriptor inside
``PolicyContext.extensions`` (the frozen WORK-003-style surface), the
engine derives the binding from that descriptor with strict
mirror checks against the context's first-class fields, and the
resulting :class:`~policy.model.PolicyDecision` is BORN with the
binding among its own ``extensions`` -- covered by the decision's
content-derived ``decision_id`` digest.

What this structurally guarantees:

- the binding's ``caller_node_id`` and ``tenant_domain`` are exactly
  the ``requester_node_id`` / ``federation_domain`` the rules saw (the
  mirror checks below reject any self-inconsistent context), so the
  authorized scope can never drift from the evaluated scope;
- a ``service.invoke`` context without a valid descriptor FAILS CLOSED
  at evaluation (``INVALID_POLICY``): the engine never emits an
  unbound ``service.invoke`` decision, so the only decisions that can
  exist for the frozen ``service.invoke`` operation already carry
  their exact invocation scope;
- the ``services`` layer (WORK-025) possesses NO binding-construction
  capability at all -- it verifies the digest and extracts the scope
  (``services.authorization``), which is the third arrow of the trust
  chain above.  There is deliberately no function anywhere in the
  ``services`` package that can turn an arbitrary ALLOW into a bound
  ALLOW.

The descriptor schema is deliberately minimal and technology-neutral
(LOCK-001/002/003/004): opaque identifiers owned by their respective
authorities, no vendor/platform vocabulary, no executable content.
The policy authority does NOT interpret service-layer identifier
FORMATS (that remains ``services.validation``); it enforces only the
structural schema and the context mirror, and copies the descriptor
verbatim.
"""

from __future__ import annotations

from typing import Any, Mapping

from .model import Operation, PolicyContext, PolicyError

#: Discriminator carried inside the invocation descriptor (context
#: side) and the invocation binding (decision side).  The descriptor
#: rides in the context's opaque WORK-003-style ``extensions``; this
#: marker is what the POLICY authority looks for when deriving the
#: binding, so foreign extensions can never be mistaken for an
#: invocation descriptor.  Owned HERE (the authority), consumed by the
#: engine and re-exported read-only by consumers such as WORK-025.
INVOCATION_BINDING_KIND = "adcos.service-invocation"

#: The exact key set of an invocation descriptor / binding mapping
#: (strict schema: unknown keys fail closed, so nothing can be
#: smuggled alongside the authorized scope).
INVOCATION_BINDING_KEYS = frozenset(
    {
        "kind",
        "operation",
        "service_ref",
        "session_id",
        "caller_node_id",
        "tenant_domain",
    }
)


def invocation_binding_from_context(
    context: PolicyContext,
) -> Mapping[str, Any]:
    """Derive the invocation binding for a ``service.invoke`` context.

    The descriptor must be present in ``context.extensions`` EXACTLY
    once, carry exactly :data:`INVOCATION_BINDING_KEYS`, have string
    values, declare the frozen ``service.invoke`` operation, carry a
    non-empty ``service_ref`` and a non-empty ``tenant_domain``, and
    MIRROR the context's first-class facts:

    - ``descriptor["caller_node_id"] == context.requester_node_id``
    - ``descriptor["tenant_domain"] == context.federation_domain``

    (both may be empty on the caller side only when the first-class
    field is empty too; ``tenant_domain`` is never optional -- an
    invocation authorization without an explicit tenant scope fails
    closed, the WORK-025 tenant-isolation discipline).  A descriptor
    that disagrees with the context it rides in is a self-inconsistent
    authorization input: the rules evaluated the first-class fields,
    so the binding must restate exactly those facts.

    Returns the validated descriptor as a plain mapping (verbatim
    content).  Raises :class:`~policy.model.PolicyError` with code
    ``invocation-binding`` on ANY violation -- the engine turns that
    into a fail-closed ``INVALID_POLICY`` evaluation outcome, so a
    malformed or missing descriptor can never produce an unbound
    ``service.invoke`` decision.
    """
    if not isinstance(context, PolicyContext):
        raise PolicyError(
            "invocation-binding",
            "invocation binding derivation requires a genuine "
            "policy.model.PolicyContext (got %s)"
            % type(context).__name__,
        )
    if context.operation != Operation.SERVICE_INVOKE:
        raise PolicyError(
            "invocation-binding",
            "invocation binding derivation requires the frozen %r "
            "operation (context operation is %r)"
            % (Operation.SERVICE_INVOKE, context.operation),
        )
    descriptors = []
    for extension in context.extensions:
        kind = extension.get("kind") if hasattr(extension, "get") else None
        if kind == INVOCATION_BINDING_KIND:
            descriptors.append(extension)
    if not descriptors:
        raise PolicyError(
            "invocation-binding",
            "service.invoke context carries no %r invocation descriptor "
            "in extensions -- the exact invocation scope (service, "
            "session, caller, tenant) must be declared up front; the "
            "engine never emits an unbound service.invoke decision "
            "(fail closed)" % (INVOCATION_BINDING_KIND,),
        )
    if len(descriptors) > 1:
        raise PolicyError(
            "invocation-binding",
            "service.invoke context carries %d %r invocation descriptors "
            "(exactly one is required; ambiguity fails closed)"
            % (len(descriptors), INVOCATION_BINDING_KIND),
        )
    descriptor = descriptors[0]
    keys = set(descriptor.keys())
    unknown = keys - INVOCATION_BINDING_KEYS
    if unknown:
        raise PolicyError(
            "invocation-binding",
            "invocation descriptor carries unknown keys %s (strict "
            "schema; nothing rides alongside the authorized scope)"
            % (sorted(unknown),),
        )
    missing = INVOCATION_BINDING_KEYS - keys
    if missing:
        raise PolicyError(
            "invocation-binding",
            "invocation descriptor is missing keys %s"
            % (sorted(missing),),
        )
    for key in sorted(INVOCATION_BINDING_KEYS):
        if not isinstance(descriptor[key], str):
            raise PolicyError(
                "invocation-binding",
                "invocation descriptor key %r must be a string (got %s)"
                % (key, type(descriptor[key]).__name__),
            )
    if descriptor["operation"] != Operation.SERVICE_INVOKE:
        raise PolicyError(
            "invocation-binding",
            "invocation descriptor declares operation %r, not the "
            "frozen %r operation" % (descriptor["operation"], Operation.SERVICE_INVOKE),
        )
    if not descriptor["service_ref"]:
        raise PolicyError(
            "invocation-binding",
            "invocation descriptor carries an empty service_ref (the "
            "authorized service is never optional)",
        )
    if not descriptor["tenant_domain"]:
        raise PolicyError(
            "invocation-binding",
            "invocation descriptor carries an empty tenant_domain "
            "(tenant-scoped authorization is never optional)",
        )
    # Mirror checks: the binding must restate exactly the first-class
    # facts the rules evaluated.  A descriptor that disagrees with its
    # own context is a self-inconsistent authorization input -- the
    # authorized scope would not be the evaluated scope.
    if descriptor["caller_node_id"] != context.requester_node_id:
        raise PolicyError(
            "invocation-binding",
            "invocation descriptor caller_node_id does not mirror the "
            "context requester_node_id (the authorized caller must be "
            "exactly the requester the rules evaluated; fail closed)",
        )
    if descriptor["tenant_domain"] != context.federation_domain:
        raise PolicyError(
            "invocation-binding",
            "invocation descriptor tenant_domain does not mirror the "
            "context federation_domain (the authorized tenant must be "
            "exactly the domain the rules evaluated; fail closed)",
        )
    return dict(descriptor)


__all__ = [
    "INVOCATION_BINDING_KIND",
    "INVOCATION_BINDING_KEYS",
    "invocation_binding_from_context",
]
