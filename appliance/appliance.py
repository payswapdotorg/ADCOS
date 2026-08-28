"""WORK-036 Network-in-a-Box: the appliance composition layer.

``NetworkAppliance`` packages ADCOS as an autonomous local network
appliance for community or emergency deployment.  It owns exactly
ONE of each accepted authority surface and adds what the box needs
ON TOP of them:

- **the agent core** -- exactly one WORK-034 ``EdgeGateway`` (which
  owns exactly one WORK-033 ``AgentRuntime`` with its WORK-030
  management surface inside): every agent command flows through the
  UNCHANGED ``EdgeGateway.run_edge`` scheduling path (no agent or
  edge semantic is re-implemented, patched, or shadowed);

- **local services** -- exactly one WORK-025 ``ServiceRegistry``
  over the reference edge executor, with a read-only WORK-012
  session projection of THE runtime's session store: local services
  register, discover, resolve, and execute with NO upstream
  Internet (the W025 ``set_upstream_state`` lever is the appliance's
  isolated-site posture control);

- **local breakout** -- exactly one WORK-024
  ``DistributedCoreManager`` over the reference LOCAL-mode IP
  gateway engine, with the same read-only session projection:
  provisioned gateways and ordinary WORK-011 paths serve local
  breakout for local sessions;

- **operator provisioning** -- the declarative
  :class:`~appliance.model.FabricManifest` (pure DATA composed of
  accepted WORK-024/W025/W011 objects) is validated by the pure
  :mod:`appliance.provisioning` check and applied step-by-step
  through the public manager/registry surfaces; a validated manifest
  is either applied in full or rejected with typed, journaled
  reasons (nothing partial is ever called "provisioned");

- **the upstream boundary** -- the appliance's service surface is
  LOCAL by construction; a federated query is refused with a typed
  reason under both postures (never silently downgraded), and the
  anti-faking two-track evidence disclosure lives in
  :mod:`appliance.isolation`.

The agent runtime's authorities, event log, and trace digests remain
the single record of protocol state; the appliance adds its own
append-only decision journal (:class:`~appliance.model.ApplianceEvent`)
and digests, so a whole appliance scenario is one deterministic,
replayable value.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from adapters.distcore import (
    BreakoutMode,
    BreakoutProviderContract,
    DistCoreError,
    DistributedCoreManager,
    ReferenceIPGatewayEngine,
    SessionReader as DistCoreSessionReaderBase,
    SessionView as DistCoreSessionView,
)
from agent import (
    AgentClock,
    AgentCommand,
    AgentConfig,
    AgentError,
    InterfaceSource,
)
from edge import (
    EdgeGateway,
    HardwareInventorySource,
    ResourceBudget,
)
from protocol.canonicalization import canonical_json_bytes
from services import (
    ExecutionProviderContract,
    ReferenceEdgeExecutor,
    ServiceError,
    ServiceRegistry,
    SessionReader as ServicesSessionReaderBase,
    SessionView as ServicesSessionView,
)

from .errors import ApplianceError, ApplianceReasonCode
from .fabric import build_fabric_view
from .isolation import check_service_query, upstream_mode_for
from .model import (
    ApplianceCommand,
    ApplianceCommandKind,
    ApplianceEvent,
    ApplianceEventType,
    ApplianceOutcome,
    ApplianceRunResult,
    ApplianceVerdict,
    FabricManifest,
    ProvisionState,
    ProvisionStepKind,
    UpstreamMode,
    appliance_event_list_digest,
)
from .provisioning import validate_manifest

#: The appliance's registered service-execution provider label.
SERVICES_PROVIDER_LABEL = "appliance-edge"

#: The appliance's registered breakout provider label (LOCAL mode:
#: the box breaks out locally; no remote-core provider is hosted).
DISTCORE_PROVIDER_LABEL = "appliance-local"

_PASSTHROUGH_KINDS = frozenset(
    {
        ApplianceCommandKind.BOOT,
        ApplianceCommandKind.EXPOSE_INTERFACES,
        ApplianceCommandKind.MONITOR,
    }
)

_AGENT_KIND_FOR_APPLIANCE_KIND = {
    ApplianceCommandKind.BOOT: "boot",
    ApplianceCommandKind.EXPOSE_INTERFACES: "expose-interfaces",
    ApplianceCommandKind.MONITOR: "monitor",
}


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ----------------------------------------------------------------------
# Read-only WORK-012 session projections (the composition-root wiring)
# ----------------------------------------------------------------------


class _RuntimeServicesSessionReader(ServicesSessionReaderBase):
    """The read-only WORK-012 session projection the WORK-025 service
    boundary may see, adapted over THE runtime's genuine
    ``SessionStore`` (validated by type: no duck-typed replacement)."""

    def __init__(self, store: Any) -> None:
        from sessions.store import SessionStore

        if not isinstance(store, SessionStore):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "the appliance's service reader requires the runtime's "
                "genuine WORK-012 SessionStore (read-only use)",
            )
        self._store = store

    def lookup(self, session_id: str) -> Optional[ServicesSessionView]:
        from sessions import SessionState

        session = self._store.get(session_id)
        if session is None:
            return None
        return ServicesSessionView(
            session_id=session.session_id,
            secureable=session.state
            in (SessionState.ESTABLISHED, SessionState.DEGRADED),
            initiator_node_id=session.binding.source_node_id,
            responder_node_id=session.binding.destination_node_id,
        )


class _RuntimeDistCoreSessionReader(DistCoreSessionReaderBase):
    """The read-only WORK-012 session projection the WORK-024
    distributed-core boundary may see, adapted over THE runtime's
    genuine ``SessionStore``."""

    def __init__(self, store: Any) -> None:
        from sessions.store import SessionStore

        if not isinstance(store, SessionStore):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "the appliance's distcore reader requires the runtime's "
                "genuine WORK-012 SessionStore (read-only use)",
            )
        self._store = store

    def lookup(self, session_id: str) -> Optional[DistCoreSessionView]:
        from sessions import SessionState

        session = self._store.get(session_id)
        if session is None:
            return None
        return DistCoreSessionView(
            session_id=session.session_id,
            secureable=session.state
            in (SessionState.ESTABLISHED, SessionState.DEGRADED),
            initiator_node_id=session.binding.source_node_id,
            responder_node_id=session.binding.destination_node_id,
        )


# ----------------------------------------------------------------------
# The appliance
# ----------------------------------------------------------------------


class NetworkAppliance:
    """The Network-in-a-Box composition over one ``EdgeGateway``."""

    def __init__(
        self,
        *,
        config: AgentConfig,
        clock: AgentClock,
        interface_source: InterfaceSource,
        hardware_source: HardwareInventorySource,
        budget: Optional[ResourceBudget] = None,
        access_plan: Mapping[str, str] = {},
        upstream_mode: str = UpstreamMode.ISOLATED,
        execution_provider: Optional[ExecutionProviderContract] = None,
        breakout_provider: Optional[Any] = None,
    ) -> None:
        if not isinstance(config, AgentConfig):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "network appliance requires a genuine AgentConfig",
            )
        if not isinstance(clock, AgentClock):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "network appliance requires a genuine AgentClock "
                "(injected time)",
            )
        if not isinstance(interface_source, InterfaceSource):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "network appliance requires a genuine InterfaceSource",
            )
        if not isinstance(hardware_source, HardwareInventorySource):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "network appliance requires a genuine "
                "HardwareInventorySource",
            )
        if upstream_mode not in UpstreamMode.values():
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "upstream_mode must be one of %s (got %r)"
                % (UpstreamMode.values(), upstream_mode),
            )
        if execution_provider is None:
            execution_provider = ReferenceEdgeExecutor()
        if not isinstance(execution_provider, ExecutionProviderContract):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "execution_provider must implement the WORK-025 "
                "ExecutionProviderContract",
            )
        if breakout_provider is None:
            breakout_provider = ReferenceIPGatewayEngine()
        if not isinstance(breakout_provider, BreakoutProviderContract):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "breakout_provider must implement the WORK-024 "
                "BreakoutProviderContract",
            )

        # -- exactly one edge gateway -> exactly one agent runtime --
        self._gateway = EdgeGateway(
            config=config,
            clock=clock,
            interface_source=interface_source,
            hardware_source=hardware_source,
            budget=budget,
            access_plan=access_plan,
        )
        self._clock = clock

        # -- exactly one service registry + one distcore manager ----
        session_store = self._gateway.runtime.sessions
        self._services = ServiceRegistry(
            session_reader=_RuntimeServicesSessionReader(session_store),
        )
        self._distcore = DistributedCoreManager(
            session_reader=_RuntimeDistCoreSessionReader(session_store),
        )
        provider_instant = self._clock.now()
        services_registration = self._services.register_execution_provider(
            execution_provider,
            label=SERVICES_PROVIDER_LABEL,
            now=provider_instant,
        )
        if not services_registration.ok:
            raise ApplianceError(
                ApplianceReasonCode.ILLEGAL_STATE,
                "service execution provider registration failed: %s"
                % (services_registration.detail,),
            )
        distcore_registration = self._distcore.register_provider(
            breakout_provider,
            label=DISTCORE_PROVIDER_LABEL,
            breakout_mode=BreakoutMode.LOCAL,
            now=provider_instant,
        )
        if not distcore_registration.ok:
            raise ApplianceError(
                ApplianceReasonCode.ILLEGAL_STATE,
                "breakout provider registration failed: %s"
                % (distcore_registration.detail,),
            )

        # -- the isolated-site posture (strict toggle sync) ----------
        self._upstream_mode = upstream_mode
        if upstream_mode == UpstreamMode.ISOLATED:
            # The registry defaults to upstream-available; an
            # isolated appliance declares the honest posture up front.
            self._services.set_upstream_state(available=False)

        # -- appliance state ------------------------------------------
        self._provision_state = ProvisionState.UNPROVISIONED
        self._site_label = ""
        self._manifest_digest = ""
        self._provisioned_gateway_refs: List[str] = []
        self._provisioned_path_count = 0
        self._provisioned_service_refs: List[str] = []
        self._events: List[ApplianceEvent] = []
        self._event_sequence = 0

    # -- read-only surfaces ------------------------------------------

    @property
    def gateway(self) -> EdgeGateway:
        return self._gateway

    @property
    def runtime(self) -> Any:
        """THE agent runtime (owned by the owned edge gateway)."""
        return self._gateway.runtime

    @property
    def services(self) -> ServiceRegistry:
        return self._services

    @property
    def distcore(self) -> DistributedCoreManager:
        return self._distcore

    @property
    def upstream_mode(self) -> str:
        return self._upstream_mode

    @property
    def provision_state(self) -> str:
        return self._provision_state

    @property
    def site_label(self) -> str:
        return self._site_label

    @property
    def manifest_digest(self) -> str:
        return self._manifest_digest

    def appliance_events(self) -> Tuple[ApplianceEvent, ...]:
        return tuple(self._events)

    def appliance_event_digest(self) -> str:
        return appliance_event_list_digest(tuple(self._events))

    def fabric_view(self) -> Any:
        """The deterministic local-fabric projection (public reads
        only)."""
        from .fabric import FabricView

        snapshot = self._services.snapshot()
        service_refs = tuple(
            str(entry.get("service_ref", ""))
            for entry in snapshot.get("services", ())
        )
        view: FabricView = build_fabric_view(
            site_label=self._site_label,
            upstream_mode=self._upstream_mode,
            provision_state=self._provision_state,
            adapter_ids=self._gateway.runtime.adapters_runtime.adapter_ids(),
            access_posture=self._gateway.posture,
            gateway_refs=tuple(self._provisioned_gateway_refs),
            path_count=self._provisioned_path_count,
            service_refs=service_refs,
        )
        return view

    def appliance_snapshot(self) -> Dict[str, Any]:
        view = self.fabric_view()
        return {
            "site_label": self._site_label,
            "upstream_mode": self._upstream_mode,
            "provision_state": self._provision_state,
            "manifest_digest": self._manifest_digest,
            "fabric": view.to_dict(),
            "appliance_event_digest": self.appliance_event_digest(),
        }

    def content_digest(self) -> str:
        payload = canonical_json_bytes(
            {
                "appliance": self.appliance_snapshot(),
                "services": self._services.content_digest(),
                "distcore": self._distcore.content_digest(),
                "edge": self._gateway.content_digest(),
            }
        )
        return "sha256:" + _sha256_hex(payload)

    # -- event journal -------------------------------------------------

    def _record_event(
        self, kind: str, instant: str, *, subject: str = "",
        detail: str = "", ref: str = "",
    ) -> None:
        self._event_sequence += 1
        self._events.append(
            ApplianceEvent(
                kind=kind,
                sequence=self._event_sequence,
                instant=instant,
                subject=subject,
                detail=detail,
                ref=ref,
            )
        )

    # -- upstream posture ----------------------------------------------

    def set_upstream(self, available: bool) -> None:
        """Declare the site's upstream-Internet availability.

        Strict toggling (the WORK-024/W025 discipline): re-declaring
        the current posture raises ``UPSTREAM_UNCHANGED``.  The
        registry's upstream lever is forwarded verbatim; local
        service state is never erased by an outage.
        """
        if not isinstance(available, bool):
            raise ApplianceError(
                ApplianceReasonCode.INVALID_INPUT,
                "upstream availability must be a bool",
            )
        mode = upstream_mode_for(available)
        if mode == self._upstream_mode:
            raise ApplianceError(
                ApplianceReasonCode.UPSTREAM_UNCHANGED,
                "upstream posture is already %r" % (mode,),
            )
        self._services.set_upstream_state(available=available)
        self._upstream_mode = mode

    def _set_upstream_command(
        self, command: ApplianceCommand, instant: str,
    ) -> ApplianceOutcome:
        available = command.params.get("available")
        if not isinstance(available, bool):
            self._record_event(
                ApplianceEventType.UPSTREAM_REJECTED, instant,
                subject=command.kind,
                detail="available must be a bool",
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=ApplianceReasonCode.PARAMS_INVALID,
                detail="available must be a bool",
            )
        try:
            self.set_upstream(available)
        except ApplianceError as error:
            self._record_event(
                ApplianceEventType.UPSTREAM_REJECTED, instant,
                subject=command.kind,
                detail=error.reason,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=error.reason,
                detail="upstream posture unchanged",
            )
        self._record_event(
            ApplianceEventType.UPSTREAM_CHANGED, instant,
            subject=command.kind,
            detail="mode=%s" % (self._upstream_mode,),
            ref=command.command_id,
        )
        return ApplianceOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=ApplianceVerdict.EXECUTED,
            detail="mode=%s" % (self._upstream_mode,),
        )

    # -- provisioning ----------------------------------------------------

    def _provision_fabric(
        self, command: ApplianceCommand, instant: str,
    ) -> ApplianceOutcome:
        manifest = command.params.get("manifest")
        if not isinstance(manifest, FabricManifest):
            self._record_event(
                ApplianceEventType.FABRIC_PROVISION_REJECTED, instant,
                subject=command.kind,
                detail="manifest missing or mistyped",
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=ApplianceReasonCode.PARAMS_INVALID,
                detail="params.manifest must be a FabricManifest",
            )
        try:
            steps = validate_manifest(manifest)
        except ApplianceError as error:
            self._record_event(
                ApplianceEventType.FABRIC_PROVISION_REJECTED, instant,
                subject=command.kind,
                detail=error.reason,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=error.reason,
                detail="manifest rejected before any application",
            )

        applied_gateway_refs: List[str] = []
        applied_path_count = 0
        applied_service_refs: List[str] = []
        for step in steps:
            try:
                if step.kind == ProvisionStepKind.REGISTER_GATEWAY:
                    gateway_entry = manifest.gateways[
                        len(applied_gateway_refs)
                    ]
                    result = self._distcore.register_gateway(
                        now=instant,
                        label=DISTCORE_PROVIDER_LABEL,
                        descriptor=gateway_entry.descriptor,
                        evidence=gateway_entry.evidence,
                    )
                    if not result.ok:
                        failure = getattr(result, "failure", None)
                        raise ApplianceError(
                            str(getattr(
                                failure, "reason_code",
                                ApplianceReasonCode.ILLEGAL_STATE,
                            )),
                            "gateway registration rejected: %s"
                            % (result.detail or "distcore refusal",),
                        )
                    applied_gateway_refs.append(step.ref)
                elif step.kind == ProvisionStepKind.REGISTER_PATH:
                    path_entry = manifest.paths[applied_path_count]
                    result = self._distcore.register_path(
                        now=instant, path=path_entry,
                    )
                    if not result.ok:
                        failure = getattr(result, "failure", None)
                        raise ApplianceError(
                            str(getattr(
                                failure, "reason_code",
                                ApplianceReasonCode.ILLEGAL_STATE,
                            )),
                            "path registration rejected: %s"
                            % (result.detail or "distcore refusal",),
                        )
                    applied_path_count += 1
                else:
                    service_entry = manifest.services[
                        len(applied_service_refs)
                    ]
                    service_result = self._services.register_service(
                        now=instant,
                        advertisement=service_entry.advertisement,
                        evidence=service_entry.evidence,
                    )
                    if not service_result.ok:
                        failure = getattr(service_result, "failure", None)
                        raise ApplianceError(
                            str(getattr(
                                failure, "reason_code",
                                ApplianceReasonCode.ILLEGAL_STATE,
                            )),
                            "service registration rejected: %s"
                            % (service_result.detail or "registry refusal",),
                        )
                    applied_service_refs.append(step.ref)
            except (ApplianceError, ServiceError, DistCoreError) as error:
                reason = getattr(error, "reason", ApplianceReasonCode.ILLEGAL_STATE)
                self._record_event(
                    ApplianceEventType.FABRIC_PROVISION_REJECTED, instant,
                    subject=command.kind,
                    detail="%s step %s: %s"
                    % (step.kind, step.ref[:24], reason),
                    ref=command.command_id,
                )
                return ApplianceOutcome(
                    command_id=command.command_id,
                    kind=command.kind,
                    verdict=ApplianceVerdict.REJECTED,
                    reason=str(reason),
                    detail="step %s refused: applied=%d gateways, "
                           "%d paths, %d services before the refusal "
                           "(nothing partial is provisioned)"
                    % (
                        step.kind, len(applied_gateway_refs),
                        applied_path_count, len(applied_service_refs),
                    ),
                )

        # Full application: the fabric is provisioned.
        self._site_label = manifest.site_label
        self._manifest_digest = manifest.content_digest()
        self._provisioned_gateway_refs = applied_gateway_refs
        self._provisioned_path_count = applied_path_count
        self._provisioned_service_refs = applied_service_refs
        self._provision_state = ProvisionState.PROVISIONED
        self._record_event(
            ApplianceEventType.FABRIC_PROVISIONED, instant,
            subject=command.kind,
            detail="site=%s gateways=%d paths=%d services=%d"
            % (
                manifest.site_label, len(applied_gateway_refs),
                applied_path_count, len(applied_service_refs),
            ),
            ref=self._manifest_digest,
        )
        return ApplianceOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=ApplianceVerdict.EXECUTED,
            detail="site=%s gateways=%d paths=%d services=%d"
            % (
                manifest.site_label, len(applied_gateway_refs),
                applied_path_count, len(applied_service_refs),
            ),
        )

    # -- service operations ---------------------------------------------

    def _discover_services(
        self, command: ApplianceCommand, instant: str,
    ) -> ApplianceOutcome:
        tenant_domain = command.params.get("tenant_domain", "")
        if not isinstance(tenant_domain, str) or not tenant_domain:
            return self._params_rejected(
                command, instant, "tenant_domain must be a non-empty string",
            )
        include_federated = command.params.get("include_federated", False)
        try:
            check_service_query(include_federated=include_federated)
        except ApplianceError as error:
            self._record_event(
                ApplianceEventType.COMMAND_REJECTED, instant,
                subject=command.kind,
                detail=error.reason,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=error.reason,
                detail="federated queries are out of the appliance's "
                       "local-fabric scope (refused, never downgraded)",
            )
        try:
            candidates = self._services.discover_services(
                now=instant,
                tenant_domain=tenant_domain,
                caller_node_id=self._gateway.runtime.node_id,
            )
        except ServiceError as error:
            self._record_event(
                ApplianceEventType.SERVICE_LOOKUP_FAILED, instant,
                subject=command.kind,
                detail=error.reason,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=error.reason,
                detail="discovery refused by the registry",
            )
        refs = tuple(candidate.service_ref for candidate in candidates)
        self._record_event(
            ApplianceEventType.SERVICE_DISCOVERED, instant,
            subject=command.kind,
            detail="candidates=%d" % (len(refs),),
            ref=command.command_id,
        )
        return ApplianceOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=ApplianceVerdict.EXECUTED,
            detail="candidates=%d %s"
            % (len(refs), ",".join(refs)),
        )

    def _lookup_service(
        self, command: ApplianceCommand, instant: str,
    ) -> ApplianceOutcome:
        service_ref = command.params.get("service_ref", "")
        tenant_domain = command.params.get("tenant_domain", "")
        if not isinstance(service_ref, str) or not service_ref:
            return self._params_rejected(
                command, instant, "service_ref must be a non-empty string",
            )
        if not isinstance(tenant_domain, str) or not tenant_domain:
            return self._params_rejected(
                command, instant, "tenant_domain must be a non-empty string",
            )
        try:
            candidate = self._services.lookup_service(
                now=instant,
                service_ref=service_ref,
                tenant_domain=tenant_domain,
                caller_node_id=self._gateway.runtime.node_id,
            )
        except ServiceError as error:
            self._record_event(
                ApplianceEventType.SERVICE_LOOKUP_FAILED, instant,
                subject=command.kind,
                detail=error.reason,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=error.reason,
                detail="lookup refused by the registry",
            )
        self._record_event(
            ApplianceEventType.SERVICE_DISCOVERED, instant,
            subject=command.kind,
            detail="state=%s" % (candidate.state,),
            ref=service_ref,
        )
        return ApplianceOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=ApplianceVerdict.EXECUTED,
            detail="state=%s host=%s"
            % (candidate.state, candidate.host_node_id[:24]),
        )

    def _service_request(
        self, command: ApplianceCommand, instant: str,
    ) -> ApplianceOutcome:
        service_ref = command.params.get("service_ref", "")
        tenant_domain = command.params.get("tenant_domain", "")
        payload_hex = command.params.get("payload_hex", "")
        decision = command.params.get("decision")
        if not isinstance(service_ref, str) or not service_ref:
            return self._params_rejected(
                command, instant, "service_ref must be a non-empty string",
            )
        if not isinstance(tenant_domain, str) or not tenant_domain:
            return self._params_rejected(
                command, instant, "tenant_domain must be a non-empty string",
            )
        if not isinstance(payload_hex, str) or not payload_hex:
            return self._params_rejected(
                command, instant, "payload_hex must be a non-empty hex string",
            )
        try:
            payload = bytes.fromhex(payload_hex)
        except ValueError:
            return self._params_rejected(
                command, instant, "payload_hex must be valid hex",
            )
        from policy.model import PolicyDecision

        if not isinstance(decision, PolicyDecision):
            self._record_event(
                ApplianceEventType.SERVICE_REQUEST_REJECTED, instant,
                subject=command.kind,
                detail=ApplianceReasonCode.POLICY_DECISION_REQUIRED,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=ApplianceReasonCode.POLICY_DECISION_REQUIRED,
                detail="a genuine born-bound WORK-010 invocation "
                       "decision is required INPUT (the appliance "
                       "never mints one)",
            )
        # Request-scope coherence (the composition-root cross-check,
        # the WORK-024 manager precedent): the decision's BORN-BOUND
        # invocation scope must match the requested scope -- a
        # decision the engine granted for another service or tenant
        # can never authorize this request (fail closed BEFORE the
        # registry is touched).
        from services import extract_invocation_binding

        try:
            binding = extract_invocation_binding(decision)
        except ServiceError as error:
            self._record_event(
                ApplianceEventType.SERVICE_REQUEST_REJECTED, instant,
                subject=command.kind,
                detail=error.reason,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=error.reason,
                detail="the decision carries no usable invocation "
                       "binding (unbound or ambiguous decisions never "
                       "authorize a request)",
            )
        if binding.service_ref != service_ref \
                or binding.tenant_domain != tenant_domain:
            self._record_event(
                ApplianceEventType.SERVICE_REQUEST_REJECTED, instant,
                subject=command.kind,
                detail=ApplianceReasonCode.POLICY_DECISION_REQUIRED,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=ApplianceReasonCode.POLICY_DECISION_REQUIRED,
                detail="the decision is born-bound to ANOTHER "
                       "invocation scope (service/tenant mismatch; "
                       "re-targeting is impossible)",
            )
        try:
            applied = self._services.apply_policy_decision(
                now=instant, policy_decision=decision,
            )
            if not applied.ok:
                raise ServiceError(
                    getattr(
                        getattr(applied, "failure", None),
                        "reason_code", "services.invalid-input",
                    ),
                    applied.detail or "decision application refused",
                )
            decision_ref = applied.value
            admitted = self._services.admit_execution(
                now=instant, decision_ref=decision_ref,
            )
            if not admitted.ok:
                raise ServiceError(
                    getattr(
                        getattr(admitted, "failure", None),
                        "reason_code", "services.invalid-input",
                    ),
                    admitted.detail or "admission refused",
                )
            admission_ref = admitted.value.admission_ref
            executed = self._services.execute_request(
                now=instant,
                admission_ref=admission_ref,
                request_payload=payload,
            )
            if not executed.ok:
                raise ServiceError(
                    getattr(
                        getattr(executed, "failure", None),
                        "reason_code", "services.invalid-input",
                    ),
                    executed.detail or "execution refused",
                )
            outcome = executed.value
            released = self._services.release_execution(
                now=instant, admission_ref=admission_ref,
            )
            if not released.ok:
                raise ServiceError(
                    getattr(
                        getattr(released, "failure", None),
                        "reason_code", "services.invalid-input",
                    ),
                    released.detail or "release refused",
                )
        except ServiceError as error:
            self._record_event(
                ApplianceEventType.SERVICE_REQUEST_REJECTED, instant,
                subject=command.kind,
                detail=error.reason,
                ref=command.command_id,
            )
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=ApplianceVerdict.REJECTED,
                reason=error.reason,
                detail="request refused by the service authority",
            )
        response = outcome.response_payload
        self._record_event(
            ApplianceEventType.SERVICE_REQUESTED, instant,
            subject=command.kind,
            detail="request_bytes=%d" % (outcome.request_bytes,),
            ref=service_ref,
        )
        return ApplianceOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=ApplianceVerdict.EXECUTED,
            detail="request_bytes=%d response_digest=sha256:%s"
            % (outcome.request_bytes, _sha256_hex(response)),
        )

    def _params_rejected(
        self, command: ApplianceCommand, instant: str, detail: str,
    ) -> ApplianceOutcome:
        self._record_event(
            ApplianceEventType.COMMAND_REJECTED, instant,
            subject=command.kind,
            detail=ApplianceReasonCode.PARAMS_INVALID,
            ref=command.command_id,
        )
        return ApplianceOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=ApplianceVerdict.REJECTED,
            reason=ApplianceReasonCode.PARAMS_INVALID,
            detail=detail,
        )

    # -- observation ------------------------------------------------------

    def _observe_fabric(
        self, command: ApplianceCommand, instant: str,
    ) -> ApplianceOutcome:
        view = self.fabric_view()
        self._record_event(
            ApplianceEventType.FABRIC_OBSERVED, instant,
            subject=command.kind,
            detail="complete=%s adapters=%d gateways=%d services=%d"
            % (
                view.complete, len(view.adapter_ids),
                len(view.gateway_refs), len(view.service_refs),
            ),
            ref=self._manifest_digest,
        )
        return ApplianceOutcome(
            command_id=command.command_id,
            kind=command.kind,
            verdict=ApplianceVerdict.EXECUTED,
            detail="complete=%s posture=%s upstream=%s"
            % (view.complete, view.access_posture, view.upstream_mode),
        )

    # -- command dispatch ---------------------------------------------------

    def _dispatch(
        self,
        command: ApplianceCommand,
        instant: str,
        *,
        boot_secret: Optional[bytes] = None,
    ) -> ApplianceOutcome:
        if command.kind in _PASSTHROUGH_KINDS:
            agent_command = AgentCommand(
                _AGENT_KIND_FOR_APPLIANCE_KIND[command.kind],
            )
            edge_result = self._gateway.run_edge(
                (agent_command,), boot_secret=boot_secret,
            )
            if not edge_result.outcomes:
                return ApplianceOutcome(
                    command_id=command.command_id,
                    kind=command.kind,
                    verdict=ApplianceVerdict.FAILED,
                    reason=ApplianceReasonCode.ILLEGAL_STATE,
                    detail="edge epoch produced no outcome",
                )
            edge_outcome = edge_result.outcomes[0]
            detail = "agent_verdict=%s" % (edge_outcome.agent_verdict,)
            if edge_outcome.detail:
                detail += " %s" % (edge_outcome.detail,)
            return ApplianceOutcome(
                command_id=command.command_id,
                kind=command.kind,
                verdict=edge_outcome.verdict,
                reason=edge_outcome.reason,
                detail=detail,
            )
        if command.kind == ApplianceCommandKind.PROVISION_FABRIC:
            return self._provision_fabric(command, instant)
        if command.kind == ApplianceCommandKind.SET_UPSTREAM:
            return self._set_upstream_command(command, instant)
        if command.kind == ApplianceCommandKind.DISCOVER_SERVICES:
            return self._discover_services(command, instant)
        if command.kind == ApplianceCommandKind.LOOKUP_SERVICE:
            return self._lookup_service(command, instant)
        if command.kind == ApplianceCommandKind.SERVICE_REQUEST:
            return self._service_request(command, instant)
        if command.kind == ApplianceCommandKind.OBSERVE_FABRIC:
            return self._observe_fabric(command, instant)
        raise ApplianceError(
            ApplianceReasonCode.COMMAND_UNKNOWN,
            "unhandled appliance command kind %r" % (command.kind,),
        )

    def run_appliance(
        self,
        commands: Sequence[ApplianceCommand],
        *,
        boot_secret: Optional[bytes] = None,
    ) -> ApplianceRunResult:
        """Execute one appliance epoch over a command batch.

        Deterministic order: the epoch instant is read ONCE (injected
        clock; a single epoch never observes drifting time), then
        each command dispatches through its frozen handler.  Every
        decision is journaled; nothing is dropped silently.
        """
        instant = self._clock.now()
        outcomes: List[ApplianceOutcome] = []
        executed = rejected = failed = deferred = shed = 0
        for command in commands:
            if not isinstance(command, ApplianceCommand):
                raise ApplianceError(
                    ApplianceReasonCode.INVALID_INPUT,
                    "run_appliance requires genuine ApplianceCommand "
                    "values",
                )
            try:
                outcome = self._dispatch(
                    command, instant, boot_secret=boot_secret,
                )
            except ApplianceError as error:
                # Caller-side shape violations surface as typed
                # rejections (class-name-only failure detail).
                self._record_event(
                    ApplianceEventType.COMMAND_REJECTED, instant,
                    subject=command.kind,
                    detail=error.reason,
                    ref=command.command_id,
                )
                outcome = ApplianceOutcome(
                    command_id=command.command_id,
                    kind=command.kind,
                    verdict=ApplianceVerdict.REJECTED,
                    reason=error.reason,
                    detail=type(error).__name__,
                )
            except (AgentError, ServiceError, DistCoreError) as error:
                # Authority-side failures are typed, never silent; the
                # detail carries the reason code, never payload
                # content (LOCK-023: class name only).
                reason = getattr(error, "reason", "authority-rejected")
                self._record_event(
                    ApplianceEventType.COMMAND_REJECTED, instant,
                    subject=command.kind,
                    detail=str(reason),
                    ref=command.command_id,
                )
                outcome = ApplianceOutcome(
                    command_id=command.command_id,
                    kind=command.kind,
                    verdict=ApplianceVerdict.FAILED,
                    reason=str(reason),
                    detail=type(error).__name__,
                )
            outcomes.append(outcome)
            if outcome.verdict == ApplianceVerdict.EXECUTED:
                executed += 1
            elif outcome.verdict == ApplianceVerdict.REJECTED:
                rejected += 1
            elif outcome.verdict == ApplianceVerdict.FAILED:
                failed += 1
            elif outcome.verdict == ApplianceVerdict.DEFERRED:
                deferred += 1
            else:
                shed += 1
        payload = ApplianceRunResult(
            status=self._gateway.runtime.status,
            executed=executed,
            rejected=rejected,
            failed=failed,
            deferred=deferred,
            shed=shed,
            outcomes=tuple(outcomes),
            upstream_mode=self._upstream_mode,
            provision_state=self._provision_state,
            agent_trace_digest=self._gateway.runtime.event_log_digest(),
            edge_event_digest=self._gateway.edge_event_digest(),
            appliance_event_digest=self.appliance_event_digest(),
        )
        payload_dict = payload.to_dict()
        object.__setattr__(
            payload,
            "appliance_digest",
            "sha256:" + _sha256_hex(canonical_json_bytes(payload_dict)),
        )
        return payload


# ----------------------------------------------------------------------
# Headless entry points
# ----------------------------------------------------------------------


def run_appliance_headless(
    config: AgentConfig,
    commands: Sequence[ApplianceCommand],
    *,
    clock: AgentClock,
    interface_source: InterfaceSource,
    hardware_source: HardwareInventorySource,
    boot_secret: Optional[bytes] = None,
    budget: Optional[ResourceBudget] = None,
    access_plan: Mapping[str, str] = {},
    upstream_mode: str = UpstreamMode.ISOLATED,
    execution_provider: Optional[ExecutionProviderContract] = None,
    breakout_provider: Optional[Any] = None,
) -> ApplianceRunResult:
    """Construct an appliance and run one epoch (the WORK-033
    ``run_headless`` discipline: everything is DATA + an injected
    clock)."""
    appliance = NetworkAppliance(
        config=config,
        clock=clock,
        interface_source=interface_source,
        hardware_source=hardware_source,
        budget=budget,
        access_plan=access_plan,
        upstream_mode=upstream_mode,
        execution_provider=execution_provider,
        breakout_provider=breakout_provider,
    )
    return appliance.run_appliance(commands, boot_secret=boot_secret)


def verify_appliance_replay(
    config: AgentConfig,
    commands: Sequence[ApplianceCommand],
    *,
    clock_factory: Callable[[], AgentClock],
    interface_source_factory: Callable[[], InterfaceSource],
    hardware_source_factory: Callable[[], HardwareInventorySource],
    boot_secret: Optional[bytes] = None,
    budget: Optional[ResourceBudget] = None,
    access_plan: Mapping[str, str] = {},
    upstream_mode: str = UpstreamMode.ISOLATED,
    execution_provider: Optional[ExecutionProviderContract] = None,
    breakout_provider: Optional[Any] = None,
    expected_appliance_digest: str = "",
) -> Tuple[bool, str]:
    """Re-run an appliance scenario with fresh factories; the whole
    scenario digest must reproduce byte-identically or the replay
    fails closed."""
    result = run_appliance_headless(
        config,
        commands,
        clock=clock_factory(),
        interface_source=interface_source_factory(),
        hardware_source=hardware_source_factory(),
        boot_secret=boot_secret,
        budget=budget,
        access_plan=access_plan,
        upstream_mode=upstream_mode,
        execution_provider=execution_provider,
        breakout_provider=breakout_provider,
    )
    if expected_appliance_digest and result.appliance_digest != expected_appliance_digest:
        return (False, "appliance digest diverged on replay")
    return (True, result.appliance_digest)


__all__ = [
    "SERVICES_PROVIDER_LABEL",
    "DISTCORE_PROVIDER_LABEL",
    "NetworkAppliance",
    "run_appliance_headless",
    "verify_appliance_replay",
]
