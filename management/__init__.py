"""ADCOS management API package (WORK-030).

The Management & Observability plane's operator surface
(spec/architecture.md 5.6, 22; spec/architecture-lock.md section 3:
``/management`` owns lifecycle/control APIs): management,
configuration, audit, and operational control APIs over the five
declared dependency authorities (WORK-010 policy, WORK-011 routing,
WORK-012 sessions, WORK-015 federation, WORK-026 telemetry).

Public API:

- :class:`ManagementAPI` -- the composition-root facade.  Every
  operation runs the four-step flow: RBAC gate (deny-by-default) ->
  WORK-010 policy gate for privileged actions (fresh genuine engine
  evaluation; explicit ALLOW required) -> DELEGATION to the owning
  authority's genuine public API -> tamper-evident audit append.
- :class:`RoleAssignmentStore`, :class:`RoleDefinition`,
  :class:`RoleAssignmentEvent`, :class:`RoleEventKind` -- the
  management plane's own RBAC authority (append-only role log,
  closure-owned state, additive roles; a role is never an identity).
- :class:`AuditLedger`, :class:`AuditRecord`, :class:`AuditOutcome`,
  :class:`AuditVerification` -- the tamper-evident audit authority
  (append-only sha256 hash chain; every call audited, allowed or
  denied).
- :class:`ManagementOperation`, :class:`ManagementCapability`,
  :class:`OperationSpec`, :data:`OPERATION_SPECS`,
  :data:`PRIVILEGED_OPERATIONS`, :data:`READ_OPERATIONS` -- the frozen
  operation/capability vocabularies with structural privileged
  classification.
- :class:`ManagementResult`, :class:`ManagementReasonCode`,
  :class:`ManagementError` -- the uniform result envelope and frozen
  reason vocabulary.
- serialization helpers: fail-closed wire round-trips for audit
  records and role events.

Module authority: ``/management`` owns lifecycle/control APIs.  It
owns NO policy, routing, session, federation, telemetry, or identity
truth -- those authorities are consumed through their public APIs
only, and the management layer never re-implements, bypasses, or
mutates another authority's state directly.  ``management/providers``
is the sanctioned location for any external management-plane
integration; this package is standard-library only.
"""

from __future__ import annotations

from .api import ManagementAPI
from .audit import AuditLedger, AuditVerification
from .errors import ManagementError, ManagementReasonCode
from .model import (
    AuditOutcome,
    AuditRecord,
    ManagementCapability,
    ManagementOperation,
    ManagementResult,
    OperationSpec,
    PRIVILEGED_OPERATIONS,
    READ_OPERATIONS,
    OPERATION_SPECS,
    RoleAssignmentEvent,
    RoleDefinition,
    RoleEventKind,
    derive_audit_record_id,
    derive_role_event_id,
    instant_le,
    instant_lt,
    operation_spec,
    require_instant,
    validate_role_catalog,
    validate_role_id,
)
from .rbac import RoleAssignmentStore
from .serialization import (
    audit_record_canonical_bytes,
    audit_record_from_mapping,
    audit_record_to_mapping,
    role_event_canonical_bytes,
    role_event_from_mapping,
    role_event_to_mapping,
)

__all__ = [
    # API
    "ManagementAPI",
    # RBAC
    "RoleAssignmentStore",
    "RoleDefinition",
    "RoleAssignmentEvent",
    "RoleEventKind",
    "validate_role_catalog",
    "validate_role_id",
    "derive_role_event_id",
    # audit
    "AuditLedger",
    "AuditVerification",
    "AuditRecord",
    "AuditOutcome",
    "derive_audit_record_id",
    # vocabularies
    "ManagementCapability",
    "ManagementOperation",
    "OperationSpec",
    "OPERATION_SPECS",
    "PRIVILEGED_OPERATIONS",
    "READ_OPERATIONS",
    "operation_spec",
    # results
    "ManagementResult",
    "ManagementReasonCode",
    "ManagementError",
    # serialization
    "audit_record_canonical_bytes",
    "audit_record_from_mapping",
    "audit_record_to_mapping",
    "role_event_canonical_bytes",
    "role_event_from_mapping",
    "role_event_to_mapping",
    # temporal helpers
    "instant_le",
    "instant_lt",
    "require_instant",
]
