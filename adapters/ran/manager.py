"""ADCOS 5G RAN integration manager (WORK-020): the runtime.

:class:`RanManager` owns the integration instance state (the binding
table, the provisioned-gNB and allocation registries, the event log)
and mediates every call through
:class:`adapters.ran.sandbox.SandboxedRan`.  It is the single
authoritative invocation path for the 5G RAN integration boundary
(mirrors the WORK-019 :class:`FiveGCoreManager` and the WORK-018
``IPIntegrationManager``):

* ``register_implementation`` wraps EACH implementation in its OWN
  :class:`SandboxedRan` (per-binding sandbox ownership -- the R4
  pattern): a ``make_default=True`` registration swaps the DEFAULT
  sandbox for NEW work only (new gNBs, new bindings, new
  allocations); live bindings -- and the gNBs/cells they were
  established on -- keep their OWNING sandbox, so a swap never
  re-routes a live session-to-bearer mapping underneath an
  application (B2/R4; mirrors WORK-018/019).
* Callers never hold the raw RAN-side bearer reference: the manager
  keys its binding registry by an OPAQUE, content-derived
  ``adcos:ran:binding:<hex>`` token minted over
  :func:`protocol.canonicalization.canonical_json_bytes` (mirroring
  the WORK-019 ``derive_binding_id``/``derive_pdu_session_ref``
  indirection, where the manager-facing handle is deliberately
  distinct from the implementation's own route identity).
* ``snapshot()`` carries only integration-instance state (bindings,
  events, counters) -- NEVER RAN technology state (LOCK-016/017:
  gNB/CU/DU/RU/cell/RRC state lives in the adapter) and NEVER the
  ``implementation_label`` (B2; mirrors WORK-018/019).
* ``to_canonical_bytes()`` / ``content_digest()`` are byte-identical
  across runs and across equivalent implementations (determinism;
  R6): the canonical form contains no implementation identity, only
  the mediated operation history.
* ``diagnostic_state()`` exposes the ``implementation_label`` and
  health accounting SEPARATELY (NOT canonical public state; B2).

R1 identity separation (the WORK-020 review trap) is enforced at
THREE manager-side layers in addition to the sandbox seam check:
the ``session_id`` is stored EXACTLY as provided (LOCK-006: sacred,
access-independent, read-only passthrough); a ``bind_session`` whose
implementation-returned bearer reference is ALREADY registered under
a DIFFERENT ``session_id`` fails closed with
``RAN_SESSION_COLLAPSE`` (mirroring the WORK-018 ``rebind_route``
collapse rejection); and a requirements map that tries to smuggle a
``session_id``/``session``/``bearer_ref``/``binding_ref`` override
key fails closed with ``RAN_SESSION_COLLAPSE`` before the
implementation is ever invoked.

The manager knows nothing about radio parameters, 3GPP message
schemas, RNTI/DRB allocation, or RAN state machines: it is pure
integration-instance bookkeeping.  Concrete RAN stacks
(OpenAirInterface, O-CU/O-DU/O-RU-style open implementations,
future RAN) plug in behind the same ABC without modifying the
manager or any core semantics.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from protocol.canonicalization import canonical_json_bytes

from .contract import RanContract
from .errors import RAN_PREFIX, RanError, RanReasonCode
from .model import CellState, GnbProvisionRequest
from .sandbox import DEFAULT_STEP_BUDGET, RanOpResult, SandboxedRan
from .serialization import to_canonical_dict
from .session import AccessPathSession
from .validation import (
    assert_ref_session_separation,
    reject_credential_like_text,
    validate_opaque_ref,
    validate_session_id,
)

__all__ = ["RanManager", "RanEvent", "DEFAULT_INTEGRATION_ID"]


#: The default RAN integration instance id (a deterministic constant;
#: the manager's own id, never core state and never a RAN-side
#: reference).
DEFAULT_INTEGRATION_ID = "ran-integration"

#: Requirement keys that would smuggle a session/binding IDENTITY
#: override into the caller-supplied QoS requirements map.  The
#: requirements map is DATA for the RAN's own QoS enforcement (TS
#: 23.501 §5.4 QoS-flow mapping); it must never re-identify the
#: sacred ``session_id`` or override the binding handles (R1;
#: LOCK-006).
_FORBIDDEN_REQUIREMENT_KEYS: Tuple[str, ...] = (
    "session_id",
    "session",
    "bearer_ref",
    "binding_ref",
)

#: Truncated sha256 hexdigest length of a minted binding token.
_BINDING_TOKEN_DIGEST_LENGTH = 32

#: Truncated sha256 hexdigest length of a minted event id.
_EVENT_ID_DIGEST_LENGTH = 16


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mint_binding_token(material: Mapping[str, Any]) -> str:
    """Content-derive the manager's OPAQUE binding token.

    Deterministic (sha256 over canonical JSON bytes of the binding
    content; never ``urandom``, never wall clock -- the WORK-019
    ``derive_binding_id`` discipline).  The token is MANAGER-side
    identity in the ``adcos:ran:binding:<hex>`` space -- structurally
    disjoint from the implementation's ``ran:<kind>:<hex>`` grammar
    (so callers can never confuse the manager's binding handle with a
    RAN-side reference) and from every other family's prefix by
    construction.  It is a truncated hexdigest, so it cannot carry
    caller-chosen identity material (the R1 string-embedding check
    applies to the RAN-side bearer reference, which the seam checks;
    the token is only ever compared for registry equality).
    """
    digest = _sha256_hex(canonical_json_bytes(dict(material)))
    token = "%s:binding:%s" % (RAN_PREFIX, digest[:_BINDING_TOKEN_DIGEST_LENGTH])
    reject_credential_like_text(token, what="binding token")
    return token


def _mint_event_id(material: Mapping[str, Any]) -> str:
    """Content-derive an event id (deterministic; WORK-003 canonical
    JSON + sha256, mirroring the WORK-016 ``derive_event_id``
    discipline)."""
    digest = _sha256_hex(canonical_json_bytes(dict(material)))
    return "%s:event:%s" % (RAN_PREFIX, digest[:_EVENT_ID_DIGEST_LENGTH])


@dataclass(frozen=True)
class RanEvent:
    """A RAN integration event (manager event log).

    ``binding_ref`` carries the MANAGER's opaque binding token (never
    the implementation's bearer reference); ``gnb_ref`` carries the
    opaque gNB handle.  Event ids are content-derived.  The event log
    is canonical public state, so it carries NO implementation label
    (B2) and no RAN technology state (LOCK-016/017).
    """

    event_id: str
    event_type: str
    ran_integration_id: str
    instant: str
    binding_ref: str = ""
    gnb_ref: str = ""
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "ran_integration_id": self.ran_integration_id,
            "instant": self.instant,
            "binding_ref": self.binding_ref,
            "gnb_ref": self.gnb_ref,
            "detail": self.detail,
        }


@dataclass
class _BindingRecord:
    """A live binding's owning sandbox + binding (B2/R4 per-binding
    ownership).  Captured at ``bind_session`` time; subsequent
    binding-scoped ops (unbind/egress/close_binding) dispatch to
    ``record.sandbox`` (never the default sandbox).  The
    ``implementation_label`` is DIAGNOSTIC-ONLY and never enters the
    canonical public state (B2)."""

    binding_token: str
    session_id: str  # stored EXACTLY as provided (LOCK-006; R1)
    bearer_ref: str
    gnb_ref: str
    created_instant: str
    sandbox: SandboxedRan
    implementation_label: str

    def to_public_dict(self) -> Dict[str, Any]:
        """The canonical (B2) projection: NO implementation label."""
        return {
            "binding_token": self.binding_token,
            "session_id": self.session_id,
            "bearer_ref": self.bearer_ref,
            "gnb_ref": self.gnb_ref,
            "created_instant": self.created_instant,
        }


@dataclass
class _GnbRecord:
    """The manager's bookkeeping mirror of ONE provisioned gNB.

    This is integration-instance bookkeeping of the manager's OWN
    mediated operations (provision/activate/deactivate), NOT RAN
    authority: the implementation remains authoritative for its own
    gNB/cell state (LOCK-016/017), and the mirror records only what
    the manager itself mediated.  ``sandbox`` is the OWNING sandbox
    (the one the gNB was provisioned through); gNB-scoped lifecycle
    ops dispatch to it so a default swap never orphaned an existing
    gNB (R4)."""

    gnb_ref: str
    gnb_name: str
    cells: Dict[str, str]  # cell_id -> CellState mirror (provision order)
    sandbox: SandboxedRan
    implementation_label: str
    created_instant: str


@dataclass
class _AllocationRecord:
    """The manager's bookkeeping record of ONE radio-capacity
    allocation (owning sandbox captured at ``allocate`` time; release
    dispatches to the owner -- R4)."""

    technology_ref: str
    kind: str
    quantity_base: int
    purpose: str
    sandbox: SandboxedRan
    created_instant: str


class RanManager:
    """The 5G RAN integration runtime.

    Constructed with the integration instance id and the default step
    budget; NO implementation is registered initially.  ``register_
    implementation`` validates ``isinstance(implementation,
    RanContract)`` (NOT ``hasattr``), wraps the implementation in its
    OWN :class:`SandboxedRan`, opens it, probes health, and -- only
    when ``make_default=True`` -- reassigns
    ``self._default_sandbox``.  Live bindings keep their owning
    sandbox (B2/R4).  Labels are unique per manager instance
    (re-registering a label fails closed with ``BINDING_EXISTS``,
    the caller-side state-error discipline the WORK-019 family uses
    for duplicate bindings).
    """

    def __init__(
        self,
        *,
        ran_integration_id: str = DEFAULT_INTEGRATION_ID,
        default_step_budget: int = DEFAULT_STEP_BUDGET,
    ) -> None:
        if not isinstance(ran_integration_id, str) or not ran_integration_id:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "ran_integration_id must be a non-empty string",
            )
        if isinstance(default_step_budget, bool) or not isinstance(default_step_budget, int):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "default_step_budget must be an integer",
            )
        if default_step_budget < 0:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "default_step_budget must be >= 0",
            )
        self._ran_integration_id = ran_integration_id
        self._default_step_budget = default_step_budget
        self._default_sandbox: Optional[SandboxedRan] = None
        self._default_label = ""
        self._registrations: List[Tuple[str, SandboxedRan]] = []
        self._bindings: Dict[str, _BindingRecord] = {}
        self._bindings_by_bearer: Dict[str, str] = {}  # bearer_ref -> token (R1 index)
        self._gnbs: Dict[str, _GnbRecord] = {}
        self._allocations: Dict[str, _AllocationRecord] = {}
        self._events: List[RanEvent] = []
        self._closed = False
        self._sequence = 0  # deterministic content sequence (tokens/events)
        # Monotonic counters (canonical public state; impl-independent).
        self._bindings_created = 0
        self._gnbs_provisioned = 0
        self._allocations_created = 0
        self._events_appended = 0

    # ------------------------------------------------------------------
    # Implementation registration
    # ------------------------------------------------------------------

    def register_implementation(
        self,
        implementation: RanContract,
        *,
        label: str,
        make_default: bool = False,
        now: str,
    ) -> RanOpResult:
        """Register a 5G RAN integration implementation.

        Validates ``isinstance(implementation, RanContract)``, wraps
        it in its OWN :class:`SandboxedRan` (per-binding sandbox
        ownership -- R4), opens it, probes health, and reassigns ONLY
        ``self._default_sandbox`` when ``make_default=True``.  Live
        bindings keep their owning sandbox; registering with
        ``make_default=False`` is a verification pass that does not
        cut over the default.  Returns the health probe result.
        ``label`` is informational only (diagnostic state, never
        canonical state -- B2) and unique per manager instance.
        """
        if self._closed:
            raise RanError(RanReasonCode.NOT_OPEN, "manager is closed")
        self._require_now(now)
        if not isinstance(label, str) or not label:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "label must be a non-empty string",
            )
        if not isinstance(implementation, RanContract):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "implementation must satisfy the RanContract ABC",
            )
        for registered_label, _sandbox in self._registrations:
            if registered_label == label:
                raise RanError(
                    RanReasonCode.BINDING_EXISTS,
                    "implementation label %r is already registered "
                    "(labels are unique per manager instance)" % label,
                )
        sandbox = SandboxedRan(
            implementation,
            ran_integration_id=self._ran_integration_id,
            step_budget=self._default_step_budget,
        )
        open_result = sandbox.open(now)
        if not open_result.ok:
            self._append_event("REGISTER_FAILED", now=now, detail=open_result.detail)
            return open_result
        health_result = sandbox.health()
        self._registrations.append((label, sandbox))
        if make_default:
            self._default_sandbox = sandbox
            self._default_label = label
        # The REGISTERED event carries NO implementation label (B2:
        # the label is diagnostic-only and must never enter the
        # byte-identical canonical state; mirrors the WORK-018/019
        # register event discipline).
        self._append_event("REGISTERED", now=now)
        return health_result

    # ------------------------------------------------------------------
    # Public mediated operations
    # ------------------------------------------------------------------

    def _require_not_closed(self) -> None:
        if self._closed:
            raise RanError(RanReasonCode.NOT_OPEN, "manager is closed")

    def _require_now(self, now: str) -> None:
        if not isinstance(now, str) or not now:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "now must be an RFC 3339 instant string",
            )

    def _require_default(self) -> SandboxedRan:
        self._require_not_closed()
        if self._default_sandbox is None:
            raise RanError(
                RanReasonCode.RAN_UNAVAILABLE,
                "no RAN implementation registered (register_implementation "
                "with make_default=True first)",
            )
        return self._default_sandbox

    def _require_binding(self, binding_ref: str) -> _BindingRecord:
        self._require_not_closed()
        if not isinstance(binding_ref, str) or not binding_ref:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "binding_ref must be a non-empty string",
            )
        record = self._bindings.get(binding_ref)
        if record is None:
            raise RanError(
                RanReasonCode.BINDING_UNKNOWN,
                "binding %s not found" % binding_ref,
            )
        return record

    def _require_gnb(self, gnb_ref: str) -> _GnbRecord:
        self._require_not_closed()
        validate_opaque_ref(gnb_ref, prefix="gnb")
        record = self._gnbs.get(gnb_ref)
        if record is None:
            raise RanError(
                RanReasonCode.GNB_UNKNOWN,
                "gnb %s not found (provision it through this manager first)"
                % gnb_ref,
            )
        return record

    def provision_gnb(self, *, now: str, request: GnbProvisionRequest) -> RanOpResult:
        """Provision a gNB through the DEFAULT sandbox (new gNBs are
        created on the current default implementation; the returned
        opaque ``ran:gnb:<hex>`` reference is RAN-side identity)."""
        sandbox = self._require_default()
        self._require_now(now)
        result = sandbox.provision_gnb(now, request=request)
        if result.ok:
            gnb_ref = str(result.value)
            # Manager bookkeeping mirror: cells start INACTIVE (the
            # engine's own discipline -- TS 38.413 activation is a
            # separate, explicit mediated step).
            self._gnbs[gnb_ref] = _GnbRecord(
                gnb_ref=gnb_ref,
                gnb_name=request.gnb_name,
                cells={
                    cell.cell_id: CellState.INACTIVE for cell in request.cells
                },
                sandbox=sandbox,
                implementation_label=self._default_label,
                created_instant=now,
            )
            self._gnbs_provisioned += 1
            self._append_event("GNB_PROVISIONED", now=now, gnb_ref=gnb_ref)
        return result

    def decommission_gnb(self, *, now: str, gnb_ref: str) -> RanOpResult:
        """Decommission a provisioned gNB (dispatched to the gNB's
        OWNING sandbox -- R4; fails closed in the implementation while
        live bearers are served)."""
        record = self._require_gnb(gnb_ref)
        self._require_now(now)
        result = record.sandbox.decommission_gnb(now, gnb_ref=gnb_ref)
        if result.ok:
            del self._gnbs[gnb_ref]
            self._append_event("GNB_DECOMMISSIONED", now=now, gnb_ref=gnb_ref)
        return result

    def _require_cell(self, gnb_record: _GnbRecord, gnb_ref: str, cell_id: str) -> None:
        """Caller-side cell check: shape + membership in the gNB's
        provisioning records (``CELL_UNKNOWN`` otherwise)."""
        if not isinstance(cell_id, str) or not cell_id:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "cell_id must be a non-empty string",
            )
        if cell_id not in gnb_record.cells:
            raise RanError(
                RanReasonCode.CELL_UNKNOWN,
                "cell %s is not served by gnb %s (per this manager's "
                "provisioning records)" % (cell_id, gnb_ref),
            )

    def activate_cell(self, *, now: str, gnb_ref: str, cell_id: str) -> RanOpResult:
        """Activate a served cell (dispatched to the gNB's owning
        sandbox; the manager mirrors the mediated state change only
        on success)."""
        record = self._require_gnb(gnb_ref)
        self._require_now(now)
        self._require_cell(record, gnb_ref, cell_id)
        result = record.sandbox.activate_cell(now, gnb_ref=gnb_ref, cell_id=cell_id)
        if result.ok:
            record.cells[cell_id] = CellState.ACTIVE
            self._append_event("CELL_ACTIVATED", now=now, gnb_ref=gnb_ref,
                               detail="cell_id=%s" % cell_id)
        return result

    def deactivate_cell(self, *, now: str, gnb_ref: str, cell_id: str) -> RanOpResult:
        """Deactivate a served cell (live bearers on it degrade, never
        die -- the honest DEGRADED state; egress fails closed until
        reactivation)."""
        record = self._require_gnb(gnb_ref)
        self._require_now(now)
        self._require_cell(record, gnb_ref, cell_id)
        result = record.sandbox.deactivate_cell(now, gnb_ref=gnb_ref, cell_id=cell_id)
        if result.ok:
            record.cells[cell_id] = CellState.INACTIVE
            self._append_event("CELL_DEACTIVATED", now=now, gnb_ref=gnb_ref,
                               detail="cell_id=%s" % cell_id)
        return result

    def _reject_identity_smuggling(
        self, requirements: Optional[Mapping[str, Any]]
    ) -> None:
        """R1: a requirements map must never re-identify the binding.

        The requirements map is caller-supplied QoS DATA for the
        RAN's own enforcement; a key that would override the sacred
        ``session_id`` or the binding handles is a session/binding
        identity-collapse attempt and fails closed BEFORE the
        implementation is invoked (extends the WORK-018/019 collapse
        rejection to the requirements-map vector).
        """
        if requirements is None:
            return
        if not isinstance(requirements, Mapping):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "requirements must be a mapping or None",
            )
        for key in requirements:
            if isinstance(key, str) and key in _FORBIDDEN_REQUIREMENT_KEYS:
                raise RanError(
                    RanReasonCode.RAN_SESSION_COLLAPSE,
                    "requirements key %r would override the session/binding "
                    "identity (R1: RAN QoS requirements are DATA and never "
                    "re-identify the sacred session_id; LOCK-006)" % key,
                )

    def bind_session(
        self,
        *,
        now: str,
        session_id: str,
        gnb_ref: str,
        requirements: Optional[Mapping[str, Any]] = None,
    ) -> RanOpResult:
        """Bind a WORK-012 session onto a provisioned gNB.

        The ``session_id`` is sacred and stored EXACTLY as given
        (LOCK-006); the sandbox checks the returned bearer reference
        against it mechanically (R1), and the manager ADDITIONALLY
        rejects a bearer reference already registered under a
        DIFFERENT ``session_id`` (``RAN_SESSION_COLLAPSE``) or under
        the SAME one (``BINDING_EXISTS``).  The returned value is the
        manager's OPAQUE binding token -- callers never hold the raw
        RAN-side bearer reference.  ``gnb_ref`` names the caller's
        requested gNB (validated against this manager's provisioning
        records); the actual serving-cell choice remains
        implementation authority (LOCK-016).
        """
        sandbox = self._require_default()
        self._require_now(now)
        validate_session_id(session_id)
        self._reject_identity_smuggling(requirements)
        gnb_record = self._require_gnb(gnb_ref)
        if gnb_record.sandbox is not sandbox:
            raise RanError(
                RanReasonCode.GNB_UNKNOWN,
                "gnb %s is served by another registered implementation; "
                "new bindings go through the DEFAULT implementation "
                "(register it with make_default=True, or provision a gNB "
                "on the default first) -- R4 per-binding ownership" % gnb_ref,
            )
        result = sandbox.bind_session(
            now, session_id=session_id, requirements=requirements
        )
        if result.ok:
            bearer_ref = str(result.value)
            # R1 (defense in depth; the sandbox seam already checked
            # the returned handle against THIS call's session_id).
            assert_ref_session_separation(bearer_ref, session_id)
            existing_token = self._bindings_by_bearer.get(bearer_ref)
            if existing_token is not None:
                existing = self._bindings[existing_token]
                if existing.session_id != session_id:
                    raise RanError(
                        RanReasonCode.RAN_SESSION_COLLAPSE,
                        "implementation returned bearer reference already "
                        "bound to a DIFFERENT session_id (R1: RAN bearer "
                        "identity never collapses onto session identity; "
                        "LOCK-006) -- registration rejected; any engine-side "
                        "state the implementation created is its own",
                    )
                raise RanError(
                    RanReasonCode.BINDING_EXISTS,
                    "implementation returned a bearer reference already "
                    "bound to this session (binding already exists)",
                )
            self._sequence += 1
            binding_token = _mint_binding_token(
                {
                    "ran_integration_id": self._ran_integration_id,
                    "session_id": session_id,
                    "bearer_ref": bearer_ref,
                    "gnb_ref": gnb_ref,
                    "created_instant": now,
                    "sequence": self._sequence,
                }
            )
            # B2/R4: capture the OWNING sandbox at bind time.
            # Subsequent binding-scoped ops dispatch to
            # record.sandbox (never the default sandbox) -- so a
            # register_implementation swap leaves live bindings on
            # their original sandbox.
            self._bindings[binding_token] = _BindingRecord(
                binding_token=binding_token,
                session_id=session_id,  # stored EXACTLY as provided
                bearer_ref=bearer_ref,
                gnb_ref=gnb_ref,
                created_instant=now,
                sandbox=sandbox,
                implementation_label=self._default_label,
            )
            self._bindings_by_bearer[bearer_ref] = binding_token
            self._bindings_created += 1
            self._append_event("BIND_SESSION", now=now, binding_ref=binding_token)
            # The caller receives the MANAGER's opaque binding token --
            # never the raw RAN-side bearer reference (the sandbox's
            # ok-result value is deliberately replaced here; mirrors
            # the WORK-019 pdu_session_ref indirection).
            return RanOpResult(ok=True, value=binding_token)
        return result

    def unbind_session(self, *, now: str, binding_ref: str) -> RanOpResult:
        """Tear down a radio bearer by its manager binding token
        (dispatched to the binding's OWNING sandbox; the manager
        removes its session-to-bearer mapping only after the mediated
        teardown succeeds -- the RanContract unbind discipline)."""
        record = self._require_binding(binding_ref)
        self._require_now(now)
        result = record.sandbox.unbind_session(now, bearer_ref=record.bearer_ref)
        if result.ok:
            self._remove_binding(binding_ref)
            self._append_event("UNBIND_SESSION", now=now, binding_ref=binding_ref)
        return result

    def egress_data(self, *, now: str, binding_ref: str, payload: bytes) -> RanOpResult:
        """Carry a payload over the bound radio bearer's user plane
        (dispatched to the binding's OWNING sandbox -- a default swap
        never re-routes a live binding's bytes)."""
        record = self._require_binding(binding_ref)
        self._require_now(now)
        result = record.sandbox.egress_data(
            now, bearer_ref=record.bearer_ref, payload=payload
        )
        if result.ok:
            self._append_event(
                "EGRESS_DATA", now=now, binding_ref=binding_ref,
                detail="payload_len=%d" % len(payload),
            )
        return result

    def allocate(
        self, *, now: str, kind: str, quantity_base: int, purpose: str
    ) -> RanOpResult:
        """Reserve radio capacity through the DEFAULT sandbox (new
        work goes to the default; the opaque ``ran:alloc:<hex>``
        reference is released through its owning sandbox)."""
        sandbox = self._require_default()
        self._require_now(now)
        result = sandbox.allocate(
            now, kind=kind, quantity_base=quantity_base, purpose=purpose
        )
        if result.ok:
            technology_ref = str(result.value)
            self._allocations[technology_ref] = _AllocationRecord(
                technology_ref=technology_ref,
                kind=kind,
                quantity_base=quantity_base,
                purpose=purpose,
                sandbox=sandbox,
                created_instant=now,
            )
            self._allocations_created += 1
            self._append_event(
                "ALLOCATED", now=now, detail="technology_ref=%s" % technology_ref
            )
        return result

    def release(self, *, now: str, technology_ref: str) -> RanOpResult:
        """Release a radio-capacity reservation (dispatched to the
        allocation's OWNING sandbox -- R4)."""
        self._require_not_closed()
        self._require_now(now)
        if not isinstance(technology_ref, str) or not technology_ref:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "technology_ref must be a non-empty string",
            )
        record = self._allocations.get(technology_ref)
        if record is None:
            raise RanError(
                RanReasonCode.ALLOCATION_UNKNOWN,
                "radio capacity reservation %s not found (allocate through "
                "this manager first)" % technology_ref,
            )
        result = record.sandbox.release(now, technology_ref=technology_ref)
        if result.ok:
            del self._allocations[technology_ref]
            self._append_event(
                "RELEASED", now=now, detail="technology_ref=%s" % technology_ref
            )
        return result

    def health(self, *, now: str) -> RanOpResult:
        """The DEFAULT implementation's health (context-free by
        contract; reported, never authoritative by itself --
        LOCK-017)."""
        self._require_now(now)
        sandbox = self._require_default()
        return sandbox.health()

    def access_path_session(self, *, now: str, session_id: str) -> RanOpResult:
        """Return the ordinary application session facade for a NEW
        binding on the DEFAULT implementation.

        Mirrors the WORK-019 ``app_session`` mechanics (validate the
        sacred ``session_id``, construct the facade, inject the
        manager + the operation instant, append the event), including
        the gNB provisioning requirement: the manager auto-selects
        the default implementation's first gNB (provisioning order)
        with an ACTIVE cell per its mediated-operation mirror, and
        fails closed with ``RAN_UNAVAILABLE`` when there is none (no
        standards-compliant access path exists yet).  The actual
        serving-cell choice remains implementation authority.  The
        value is an :class:`AccessPathSession` whose public surface
        is standard session semantics only (LOCK-019 analog).
        """
        self._require_now(now)
        sandbox = self._require_default()
        validate_session_id(session_id)
        gnb_ref = self._first_active_gnb_cell(sandbox)
        result = self.bind_session(now=now, session_id=session_id, gnb_ref=gnb_ref)
        if not result.ok:
            return result
        binding_token = str(result.value)
        session = AccessPathSession()
        # The manager injects itself + the binding's MANAGER-side
        # routing handle (the opaque binding token) + the injected
        # instant so the session's standard send() routes through the
        # binding's OWNING sandbox (B2/R4).  All of it is PRIVATE
        # routing metadata (LOCK-019 analog).
        session._bind_access_path(manager=self, binding_ref=binding_token)
        session._set_now(now)
        self._append_event(
            "ACCESS_PATH_SESSION", now=now, binding_ref=binding_token
        )
        return RanOpResult(ok=True, value=session)

    def close_binding(self, *, now: str, binding_ref: str) -> RanOpResult:
        """Close ONE binding (the WORK-019 ``close_binding`` lifecycle
        entry point).

        The RAN contract has no separate per-binding close operation
        -- tearing down the radio bearer IS the binding close -- so
        mechanically this performs the same mediated unbind as
        :meth:`unbind_session` on the binding's OWNING sandbox, and
        removes the manager's binding record only after it succeeds
        (fail closed).  The two entry points differ in intent and
        event type, not in the invariant.
        """
        record = self._require_binding(binding_ref)
        self._require_now(now)
        result = record.sandbox.unbind_session(now, bearer_ref=record.bearer_ref)
        if result.ok:
            self._remove_binding(binding_ref)
            self._append_event("CLOSE_BINDING", now=now, binding_ref=binding_ref)
        return result

    def close(self) -> None:
        """Close the manager (fail-closed bookkeeping; mirrors the
        WORK-019 manager close: the binding registry is dropped and
        every subsequent op raises ``NOT_OPEN``).

        This is MANAGER-level bookkeeping only.  The implementation's
        own close remains a mediated operation the caller performs
        first (``unbind_session``/``close_binding`` per live binding,
        then the implementation's ``close`` via its sandbox) -- the
        manager never tears a live session-to-bearer mapping out from
        under an application as a side effect of its own shutdown.
        """
        self._closed = True
        self._bindings.clear()
        self._bindings_by_bearer.clear()
        self._gnbs.clear()
        self._allocations.clear()

    # ------------------------------------------------------------------
    # Canonical public state (B2: implementation_label EXCLUDED)
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """The canonical public state (byte-identical across impls).

        Carries ONLY integration-instance state (bindings, events,
        counters).  NEVER RAN technology state (LOCK-016/017) and
        NEVER the ``implementation_label`` (B2; mirrors WORK-018/019).
        Bindings are sorted by binding token; events are in append
        order -- byte-stable across runs and across equivalent
        implementations for a given operation history.
        """
        bindings = [
            self._bindings[token].to_public_dict()
            for token in sorted(self._bindings)
        ]
        events = [event.to_dict() for event in self._events]
        return {
            "ran_integration_id": self._ran_integration_id,
            "closed": self._closed,
            "binding_count": len(self._bindings),
            "bindings": bindings,
            "events": events,
            "counters": {
                "bindings_created": self._bindings_created,
                "gnbs_provisioned": self._gnbs_provisioned,
                "allocations_created": self._allocations_created,
                "events_appended": self._events_appended,
            },
        }

    def to_canonical_bytes(self) -> bytes:
        """Canonical-JSON bytes of the public state (byte-identical
        across runs and across equivalent implementations)."""
        return canonical_json_bytes(to_canonical_dict(self.snapshot()))

    def content_digest(self) -> str:
        """SHA-256 of the canonical public state."""
        return hashlib.sha256(self.to_canonical_bytes()).hexdigest()

    def diagnostic_state(self) -> Dict[str, Any]:
        """Diagnostic state (NOT canonical public state; B2).  Exposes
        the registered ``implementation_label`` and health accounting
        so operators can inspect the live implementation without it
        entering the byte-identical canonical state."""
        if self._default_sandbox is None:
            return {
                "ran_integration_id": self._ran_integration_id,
                "implementation_label": "",
                "sandbox_health": "NOT_RUNNING",
                "registered_implementations": len(self._registrations),
                "binding_count": len(self._bindings),
                "gnb_count": len(self._gnbs),
                "allocation_count": len(self._allocations),
                "closed": self._closed,
            }
        diag = self._default_sandbox.diagnostic_state()
        diag["ran_integration_id"] = self._ran_integration_id
        diag["implementation_label"] = self._default_label
        diag["registered_implementations"] = len(self._registrations)
        diag["binding_count"] = len(self._bindings)
        diag["gnb_count"] = len(self._gnbs)
        diag["allocation_count"] = len(self._allocations)
        diag["closed"] = self._closed
        return diag

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _first_active_gnb_cell(self, sandbox: SandboxedRan) -> str:
        """The first gNB (provisioning order) of the given sandbox
        with an ACTIVE cell, per the manager's mediated-op mirror.

        The cell CHOICE itself stays implementation-side (the engine's
        own deterministic first-fit over its live state); the manager
        only names a gNB whose activation it mediated, and fails
        closed when there is none -- an honest ``RAN_UNAVAILABLE``
        (no standards-compliant access path exists on the default
        implementation yet).
        """
        for gnb_ref, record in self._gnbs.items():
            if record.sandbox is not sandbox:
                continue
            for cell_state in record.cells.values():
                if cell_state == CellState.ACTIVE:
                    return gnb_ref
        raise RanError(
            RanReasonCode.RAN_UNAVAILABLE,
            "no active cell on the default implementation (provision a gNB "
            "and activate a cell first -- no standards-compliant access "
            "path exists yet)",
        )

    def _remove_binding(self, binding_token: str) -> None:
        record = self._bindings.pop(binding_token, None)
        if record is not None:
            self._bindings_by_bearer.pop(record.bearer_ref, None)

    def _append_event(
        self,
        event_type: str,
        *,
        now: str,
        binding_ref: str = "",
        gnb_ref: str = "",
        detail: str = "",
    ) -> None:
        self._sequence += 1
        content = {
            "event_type": event_type,
            "ran_integration_id": self._ran_integration_id,
            "instant": now,
            "sequence": self._sequence,
            "binding_ref": binding_ref,
            "gnb_ref": gnb_ref,
            "detail": detail,
        }
        self._events.append(
            RanEvent(
                event_id=_mint_event_id(content),
                event_type=event_type,
                ran_integration_id=self._ran_integration_id,
                instant=now,
                binding_ref=binding_ref,
                gnb_ref=gnb_ref,
                detail=detail,
            )
        )
        self._events_appended += 1

    @property
    def ran_integration_id(self) -> str:
        return self._ran_integration_id

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def closed(self) -> bool:
        return self._closed
