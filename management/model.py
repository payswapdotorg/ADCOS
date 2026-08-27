"""Management-plane domain model (WORK-030).

Frozen vocabularies and immutable, content-identified domain objects
for the management API plane (spec/architecture.md 5.6 -- the
Management & Observability plane's operator API surface; section 22 --
the management surface expresses intent, not internal implementation
details; section 19 -- role/capability based authorization and audit
evidence for privileged operations).

Vocabularies (closed sets -- adding a member is a deliberate schema
change, never a silent extension):

- :class:`ManagementCapability` -- what a role may grant.  Management-
  owned identifiers over the five declared dependency surfaces ONLY
  (policy / routing / sessions / federation / telemetry) plus the
  management plane's own RBAC and audit surfaces.  A capability is
  never a WORK-010 policy operation (those authorize individual
  privileged ACTIONS; capabilities bound what an operator may even
  REQUEST -- the two-key design documented in the package README).
- :class:`ManagementOperation` -- the frozen management API operation
  vocabulary, each operation bound structurally to (required
  capability, required WORK-010 policy operation or ``None``).
  Read/inspect operations are non-privileged (the frozen WORK-010
  operation vocabulary contains no read operation, and the policy
  README's structural classification rule forbids inferring one from
  naming); control operations are privileged and policy-gated.
- :class:`AuditOutcome` -- what the audit trail records.
- :class:`RoleEventKind` -- GRANT / REVOKE (the append-only RBAC log).

Domain objects:

- :class:`RoleDefinition` -- a named bundle of capabilities (DATA).
  Roles are additive and dynamic; a role is NEVER an identity
  (spec/architecture.md section 4: "A role is never itself an
  identity") -- role ids are structurally disjoint from the NodeID
  grammar and may never carry the ``adcos:`` prefix family.
- :class:`RoleAssignmentEvent` -- one append-only grant/revoke record
  with a content-derived event id.
- :class:`AuditRecord` -- one tamper-evident hash-chained audit record
  with a content-derived record id.
- :class:`ManagementResult` -- the uniform API result envelope.

Module authority: ``/management`` owns lifecycle/control APIs
(spec/architecture-lock.md section 3).  It owns NO policy, routing,
session, federation, telemetry, or identity truth: those authorities
are consumed through their public APIs only.  The model deliberately
imports NOTHING from the domain families -- the vocabularies above
reference the dependency surfaces by frozen string identifiers so the
management plane can never grow a back-door import of another
authority's types through the model layer.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Set, Tuple

from protocol.canonicalization import canonical_json_bytes

from .errors import ManagementError, ManagementReasonCode

# ---------------------------------------------------------------------------
# Temporal discipline (shared cross-cutting primitive, the same one every
# family consumes -- federation/telemetry/sessions all use it)
# ---------------------------------------------------------------------------

from protocol.temporal import TemporalError, parse_instant


def require_instant(value: object, label: str) -> None:
    """Fail closed on a non-RFC-3339 UTC instant (injected clock only --
    the management plane never reads the wall clock)."""
    if not isinstance(value, str) or not value:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "%s must be a non-empty RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "%s %r is not RFC 3339 UTC: %s" % (label, value, error),
        ) from error


def instant_lt(a: str, b: str) -> bool:
    """Strictly-before comparison over two validated RFC 3339 UTC
    instants (deterministic; never string-lexicographic)."""
    return parse_instant(a) < parse_instant(b)


def instant_le(a: str, b: str) -> bool:
    return parse_instant(a) <= parse_instant(b)


# ---------------------------------------------------------------------------
# Frozen vocabularies
# ---------------------------------------------------------------------------


class ManagementCapability:
    """Frozen management capability vocabulary (the RBAC grant surface).

    Capabilities bound what an operator may REQUEST through the
    management API.  Least authority (P6): a capability never bundles a
    read with its control surface -- reading state and changing state
    are distinct grants.
    """

    POLICY_READ = "management.capability.policy.read"
    SESSION_READ = "management.capability.session.read"
    SESSION_CONTROL = "management.capability.session.control"
    FEDERATION_READ = "management.capability.federation.read"
    FEDERATION_CONTROL = "management.capability.federation.control"
    TELEMETRY_READ = "management.capability.telemetry.read"
    TELEMETRY_PROMOTE = "management.capability.telemetry.promote"
    AUDIT_READ = "management.capability.audit.read"
    ROLES_READ = "management.capability.roles.read"
    ROLES_ADMINISTER = "management.capability.roles.administer"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.POLICY_READ,
            cls.SESSION_READ,
            cls.SESSION_CONTROL,
            cls.FEDERATION_READ,
            cls.FEDERATION_CONTROL,
            cls.TELEMETRY_READ,
            cls.TELEMETRY_PROMOTE,
            cls.AUDIT_READ,
            cls.ROLES_READ,
            cls.ROLES_ADMINISTER,
        )


class ManagementOperation:
    """Frozen management API operation vocabulary.

    Every API entry point is named here with its structural
    authorization requirements:

    - ``capability`` -- the RBAC capability an ACTIVE role assignment
      must grant (deny-by-default when absent);
    - ``policy_operation`` -- the frozen WORK-010 operation an explicit
      engine ALLOW must cover for PRIVILEGED operations, or ``None``
      for read-only inspection (the frozen WORK-010 vocabulary has no
      read operation, and reads are non-privileged by structural
      classification -- never inferred from naming).

    ``PRIVILEGED_OPERATIONS`` / ``READ_OPERATIONS`` are derived from
    the specs table, never maintained by hand.
    """

    # -- read / inspect (non-privileged; RBAC capability-gated) ----------
    POLICY_SNAPSHOT = "management.op.policy.snapshot"
    SESSION_SNAPSHOT = "management.op.session.snapshot"
    FEDERATION_SNAPSHOT = "management.op.federation.snapshot"
    TELEMETRY_QUERY = "management.op.telemetry.query"
    AUDIT_VERIFY = "management.op.audit.verify"
    ROLES_SNAPSHOT = "management.op.roles.snapshot"

    # -- privileged control (RBAC + explicit WORK-010 ALLOW + delegation) -
    SESSION_CREATE = "management.op.session.create"
    SESSION_MODIFY = "management.op.session.modify"
    SESSION_TERMINATE = "management.op.session.terminate"
    FEDERATION_JOIN = "management.op.federation.join"
    FEDERATION_ACCEPT_PEER = "management.op.federation.accept-peer"
    FEDERATION_RESOURCE_EXPORT = "management.op.federation.resource-export"
    FEDERATION_RESOURCE_IMPORT = "management.op.federation.resource-import"
    TELEMETRY_TOPOLOGY_PROMOTE = "management.op.telemetry.topology-promote"
    MANAGEMENT_ROLE_ASSIGN = "management.op.role-assign"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        # OPERATION_SPECS is defined below the class but resolved at
        # call time (module fully loaded) -- the specs table is the
        # single source of truth.
        return tuple(sorted(OPERATION_SPECS.keys()))


class RoleEventKind:
    """Frozen role-assignment event vocabulary (append-only log)."""

    GRANT = "grant"
    REVOKE = "revoke"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.GRANT, cls.REVOKE)


class AuditOutcome:
    """Frozen audit outcome vocabulary.

    Every management API call -- allowed OR denied -- produces exactly
    one audit record (P11: observable and auditable).  The outcome
    distinguishes WHERE the request stopped so denials are explainable:
    RBAC denial, policy denial, invalid input, authority rejection,
    execution, or internal failure.
    """

    DENIED_RBAC = "denied-rbac"
    DENIED_POLICY = "denied-policy"
    DENIED_INVALID_INPUT = "denied-invalid-input"
    AUTHORITY_REJECTED = "authority-rejected"
    EXECUTED = "executed"
    FAILED = "failed"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.DENIED_RBAC,
            cls.DENIED_POLICY,
            cls.DENIED_INVALID_INPUT,
            cls.AUTHORITY_REJECTED,
            cls.EXECUTED,
            cls.FAILED,
        )


# ---------------------------------------------------------------------------
# Operation specs (the single structural source of truth)
# ---------------------------------------------------------------------------

#: The frozen WORK-010 ``Operation`` string values referenced by
#: management specs.  Management re-states them as string constants
#: (cross-checked byte-for-byte against ``policy.model.Operation`` in
#: the self-test battery) so the model layer imports no policy types;
#: the API layer performs the genuine engine evaluation.
_POLICY_SESSION_CREATE = "session.create"
_POLICY_SESSION_MODIFY = "session.modify"
_POLICY_SESSION_TERMINATE = "session.terminate"
_POLICY_FEDERATION_JOIN = "federation.join"
_POLICY_FEDERATION_ACCEPT_PEER = "federation.accept-peer"
_POLICY_FEDERATION_RESOURCE_EXPORT = "federation.resource-export"
_POLICY_FEDERATION_RESOURCE_IMPORT = "federation.resource-import"
_POLICY_TELEMETRY_PROMOTE = "telemetry.topology-promote"
_POLICY_MANAGEMENT_ROLE_ASSIGN = "management.role-assign"


@dataclass(frozen=True)
class OperationSpec:
    """The structural authorization requirements of one operation."""

    operation: str
    capability: str
    policy_operation: str  # "" for non-privileged reads

    @property
    def privileged(self) -> bool:
        return self.policy_operation != ""

    def content_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "capability": self.capability,
            "policy_operation": self.policy_operation,
        }


_OPERATION_SPECS: Tuple[OperationSpec, ...] = (
    # reads
    OperationSpec(
        ManagementOperation.POLICY_SNAPSHOT,
        ManagementCapability.POLICY_READ,
        "",
    ),
    OperationSpec(
        ManagementOperation.SESSION_SNAPSHOT,
        ManagementCapability.SESSION_READ,
        "",
    ),
    OperationSpec(
        ManagementOperation.FEDERATION_SNAPSHOT,
        ManagementCapability.FEDERATION_READ,
        "",
    ),
    OperationSpec(
        ManagementOperation.TELEMETRY_QUERY,
        ManagementCapability.TELEMETRY_READ,
        "",
    ),
    OperationSpec(
        ManagementOperation.AUDIT_VERIFY,
        ManagementCapability.AUDIT_READ,
        "",
    ),
    OperationSpec(
        ManagementOperation.ROLES_SNAPSHOT,
        ManagementCapability.ROLES_READ,
        "",
    ),
    # privileged control
    OperationSpec(
        ManagementOperation.SESSION_CREATE,
        ManagementCapability.SESSION_CONTROL,
        _POLICY_SESSION_CREATE,
    ),
    OperationSpec(
        ManagementOperation.SESSION_MODIFY,
        ManagementCapability.SESSION_CONTROL,
        _POLICY_SESSION_MODIFY,
    ),
    OperationSpec(
        ManagementOperation.SESSION_TERMINATE,
        ManagementCapability.SESSION_CONTROL,
        _POLICY_SESSION_TERMINATE,
    ),
    OperationSpec(
        ManagementOperation.FEDERATION_JOIN,
        ManagementCapability.FEDERATION_CONTROL,
        _POLICY_FEDERATION_JOIN,
    ),
    OperationSpec(
        ManagementOperation.FEDERATION_ACCEPT_PEER,
        ManagementCapability.FEDERATION_CONTROL,
        _POLICY_FEDERATION_ACCEPT_PEER,
    ),
    OperationSpec(
        ManagementOperation.FEDERATION_RESOURCE_EXPORT,
        ManagementCapability.FEDERATION_CONTROL,
        _POLICY_FEDERATION_RESOURCE_EXPORT,
    ),
    OperationSpec(
        ManagementOperation.FEDERATION_RESOURCE_IMPORT,
        ManagementCapability.FEDERATION_CONTROL,
        _POLICY_FEDERATION_RESOURCE_IMPORT,
    ),
    OperationSpec(
        ManagementOperation.TELEMETRY_TOPOLOGY_PROMOTE,
        ManagementCapability.TELEMETRY_PROMOTE,
        _POLICY_TELEMETRY_PROMOTE,
    ),
    OperationSpec(
        ManagementOperation.MANAGEMENT_ROLE_ASSIGN,
        ManagementCapability.ROLES_ADMINISTER,
        _POLICY_MANAGEMENT_ROLE_ASSIGN,
    ),
)

#: operation id -> spec (frozen at import; never mutated)
OPERATION_SPECS: Mapping[str, OperationSpec] = {
    spec.operation: spec for spec in _OPERATION_SPECS
}

#: The frozen privileged operation subset (structural classification --
#: exactly the operations whose spec carries a policy operation).
PRIVILEGED_OPERATIONS: Tuple[str, ...] = tuple(
    sorted(spec.operation for spec in _OPERATION_SPECS if spec.privileged)
)

#: The frozen read-only operation subset.
READ_OPERATIONS: Tuple[str, ...] = tuple(
    sorted(spec.operation for spec in _OPERATION_SPECS if not spec.privileged)
)


def operation_spec(operation: str) -> OperationSpec:
    """Look up the frozen spec for ``operation`` (fail closed)."""
    spec = OPERATION_SPECS.get(operation) if isinstance(operation, str) else None
    if spec is None:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "operation %r is not a frozen management operation (known: %s)"
            % (operation, list(ManagementOperation.values())),
        )
    return spec


# ---------------------------------------------------------------------------
# Roles (DATA; additive; never identities)
# ---------------------------------------------------------------------------

#: Role-id grammar: lowercase letters, digits, dots and hyphens.  This
#: is structurally DISJOINT from the canonical NodeID grammar
#: (``adcos:node:<profile>:<digest>`` uses colons and the ``adcos:``
#: prefix family), so a role id can never be mistaken for an identity
#: and vice versa.  The prefix ban is enforced explicitly below.
_ROLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9.-]*$")

#: Identifiers reserved for the identity authority's namespace.
_ROLE_ID_FORBIDDEN_PREFIX = "adcos:"


def validate_role_id(role_id: object) -> str:
    """Validate a role id (fail closed).  A role is never an identity:
    NodeID-shaped ids (the ``adcos:`` prefix family) are rejected
    outright, and the grammar admits no colons at all."""
    if not isinstance(role_id, str) or not role_id:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role id must be a non-empty string (got %r)" % (role_id,),
        )
    if role_id.startswith(_ROLE_ID_FORBIDDEN_PREFIX) or ":" in role_id:
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role id %r is identity-shaped (the 'adcos:' family / colon "
            "grammar belongs to WORK-004 NodeIDs) -- a role is never an "
            "identity (spec/architecture.md section 4)" % role_id,
        )
    if not _ROLE_ID_PATTERN.match(role_id):
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role id %r does not match the frozen role grammar "
            "^[a-z][a-z0-9.-]*$" % role_id,
        )
    return role_id


@dataclass(frozen=True)
class RoleDefinition:
    """A named bundle of capabilities.  DATA only -- never executable,
    never a trust assertion, never an identity.

    Effective capabilities are additive across a single operator's
    active role assignments (union), mirroring the additive-roles rule
    for node roles (spec/architecture.md section 4).
    """

    role_id: str
    capabilities: Tuple[str, ...]
    description: str = ""

    def __post_init__(self) -> None:
        validate_role_id(self.role_id)
        if not isinstance(self.description, str):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "role description must be a string",
            )
        if not isinstance(self.capabilities, tuple):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "role capabilities must be a tuple of frozen capability ids",
            )
        seen: Set[str] = set()
        for cap in self.capabilities:
            if cap not in ManagementCapability.values():
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "role %r grants unknown capability %r (frozen vocabulary: %s)"
                    % (self.role_id, cap, list(ManagementCapability.values())),
                )
            if cap in seen:
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "role %r grants capability %r more than once"
                    % (self.role_id, cap),
                )
            seen.add(cap)

    def content_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "capabilities": list(self.capabilities),
            "description": self.description,
        }


def validate_role_catalog(
    roles: Tuple[RoleDefinition, ...],
) -> Tuple[RoleDefinition, ...]:
    """Validate a role catalog: a tuple of genuine, distinct role
    definitions.  Duplicate role ids fail closed (an ambiguous catalog
    is never acceptable RBAC configuration)."""
    if not isinstance(roles, tuple):
        raise ManagementError(
            ManagementReasonCode.INVALID_INPUT,
            "role catalog must be a tuple of RoleDefinition",
        )
    seen: Set[str] = set()
    for role in roles:
        if not isinstance(role, RoleDefinition):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "role catalog entries must be RoleDefinition instances "
                "(got %s)" % type(roles[0]).__name__ if roles else "",
            )
        if role.role_id in seen:
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "role catalog contains duplicate role id %r" % role.role_id,
            )
        seen.add(role.role_id)
    return roles


# ---------------------------------------------------------------------------
# Role assignment events (append-only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleAssignmentEvent:
    """One append-only RBAC mutation record.

    The CURRENT assignment state is the deterministic fold over the
    event log (last event per (operator, role) wins; a GRANT is active
    only inside its validity window).  History is never rewritten --
    revocation is a new event, which is exactly what makes RBAC changes
    auditable.
    """

    event_id: str
    kind: str
    operator_node_id: str
    role_id: str
    instant: str
    actor_node_id: str
    reason: str = ""
    valid_from: str = ""
    valid_until: str = ""

    def __post_init__(self) -> None:
        if self.kind not in RoleEventKind.values():
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "role event kind %r is not one of %s"
                % (self.kind, list(RoleEventKind.values())),
            )
        validate_role_id(self.role_id)
        for label, value in (
            ("operator_node_id", self.operator_node_id),
            ("actor_node_id", self.actor_node_id),
            ("instant", self.instant),
        ):
            if not isinstance(value, str) or not value:
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "%s must be a non-empty string" % label,
                )
        require_instant(self.instant, "role event instant")
        if self.valid_from:
            require_instant(self.valid_from, "role event valid_from")
        if self.valid_until:
            require_instant(self.valid_until, "role event valid_until")
        if self.valid_from and self.valid_until and instant_lt(
            self.valid_until, self.valid_from
        ):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "role event validity window is inverted (%s .. %s)"
                % (self.valid_from, self.valid_until),
            )
        if not isinstance(self.reason, str) or len(self.reason) > 256:
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "role event reason must be a string of at most 256 chars",
            )
        if self.kind == RoleEventKind.REVOKE and (
            self.valid_from or self.valid_until
        ):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "a REVOKE event carries no validity window",
            )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "operator_node_id": self.operator_node_id,
            "role_id": self.role_id,
            "instant": self.instant,
            "actor_node_id": self.actor_node_id,
            "reason": self.reason,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.content_dict())


def derive_role_event_id(event: RoleAssignmentEvent) -> str:
    """Content-derived event id (sha256 over the canonical event
    content).  Identity of an event is its content -- replaying the
    identical grant is detectable by id, and any tampering with the
    recorded content breaks the id."""
    return hashlib.sha256(event.canonical_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Audit records (tamper-evident hash chain)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditRecord:
    """One tamper-evident audit record.

    Every management API call produces exactly one record.  Tamper
    evidence is the sha256 hash CHAIN:

    - ``record_id`` = sha256(prev_digest + "|" + canonical content) --
      each record's id covers its own content AND the entire prefix
      chain (a Merkle-style sequential chain);
    - ``prev_digest`` links to the previous record's ``record_id``
      ("" for the first record);
    - ``chain_digest`` = the record's own ``record_id`` (the running
      head).

    Consequences (mechanically verified by ``AuditLedger.verify_chain``):

    - mutating ANY field of ANY record breaks that record's id AND
      every later record's linkage;
    - deleting a record breaks the linkage of its successor;
    - reordering records breaks linkage immediately;
    - inserting a forged record with a recomputed id changes the head,
      which is detectable against any externally pinned head
      (``chain_head()`` exists exactly for external notarization /
      evidence retention).

    The record carries NO secrets: deterministic diagnostics only
    (spec/architecture.md section 20 discipline -- the audit trail is
    inspectable without disclosing credential material).
    """

    record_id: str
    sequence: int
    recorded_instant: str
    operation: str
    operator_node_id: str
    outcome: str
    detail: str
    evidence_refs: Tuple[str, ...] = ()
    prev_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.record_id, str) or not self.record_id:
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit record id must be a non-empty string",
            )
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit sequence must be an int (got %s)" % type(self.sequence).__name__,
            )
        if self.sequence < 1:
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit sequence must be >= 1 (1-based append-only ledger)",
            )
        if self.operation not in ManagementOperation.values():
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit operation %r is not a frozen management operation",
            )
        if self.outcome not in AuditOutcome.values():
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit outcome %r is not a frozen audit outcome",
            )
        for label, value in (
            ("recorded_instant", self.recorded_instant),
            ("operator_node_id", self.operator_node_id),
            ("detail", self.detail),
            ("prev_digest", self.prev_digest),
        ):
            if not isinstance(value, str):
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "audit %s must be a string" % label,
                )
        require_instant(self.recorded_instant, "audit recorded_instant")
        if not isinstance(self.evidence_refs, tuple):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "audit evidence_refs must be a tuple of strings",
            )
        for ref in self.evidence_refs:
            if not isinstance(ref, str) or not ref:
                raise ManagementError(
                    ManagementReasonCode.INVALID_INPUT,
                    "audit evidence refs must be non-empty strings",
                )

    def content_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "recorded_instant": self.recorded_instant,
            "operation": self.operation,
            "operator_node_id": self.operator_node_id,
            "outcome": self.outcome,
            "detail": self.detail,
            "evidence_refs": list(self.evidence_refs),
            "prev_digest": self.prev_digest,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.content_dict())


def derive_audit_record_id(prev_digest: str, record: AuditRecord) -> str:
    """Content-derived record id: sha256(prev_digest + '|' + canonical
    content).  Chained coverage -- the id proves the record's content
    AND its position in the chain."""
    return hashlib.sha256(
        (prev_digest + "|").encode("utf-8") + record.canonical_bytes()
    ).hexdigest()


# ---------------------------------------------------------------------------
# The uniform API result envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ManagementResult:
    """The uniform result envelope for every management API operation.

    ``ok`` is True only for :attr:`ManagementReasonCode.EXECUTED`.
    ``evidence_refs`` carries the machine-verifiable references for the
    decision trail (WORK-010 decision ids, authority result codes,
    subject ids); ``audit_record_id`` always references the audit
    record this call produced (every call is audited, allowed or
    denied).  ``payload`` carries read results (snapshots, query
    results, verification reports) or authority objects (sessions,
    relationships, promotions) -- DATA, never authority capability.
    """

    ok: bool
    code: str
    detail: str
    evidence_refs: Tuple[str, ...] = ()
    payload: Any = None
    audit_record_id: str = ""

    def __post_init__(self) -> None:
        if not ManagementReasonCode.is_valid(self.code):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "result code %r is not a frozen management reason code" % self.code,
            )
        if self.ok != (self.code in ManagementReasonCode.ok_values()):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "result ok=%r contradicts code %r" % (self.ok, self.code),
            )
        if not isinstance(self.detail, str):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "result detail must be a string",
            )
        if not isinstance(self.evidence_refs, tuple):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "result evidence_refs must be a tuple",
            )
        if not isinstance(self.audit_record_id, str):
            raise ManagementError(
                ManagementReasonCode.INVALID_INPUT,
                "result audit_record_id must be a string",
            )


__all__ = [
    # vocabularies
    "AuditOutcome",
    "ManagementCapability",
    "ManagementOperation",
    "RoleEventKind",
    # specs
    "OPERATION_SPECS",
    "OperationSpec",
    "PRIVILEGED_OPERATIONS",
    "READ_OPERATIONS",
    "operation_spec",
    # roles
    "RoleAssignmentEvent",
    "RoleDefinition",
    "derive_role_event_id",
    "validate_role_catalog",
    "validate_role_id",
    # audit
    "AuditRecord",
    "derive_audit_record_id",
    # result
    "ManagementResult",
    # temporal helpers
    "instant_le",
    "instant_lt",
    "require_instant",
]
