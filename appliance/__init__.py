"""ADCOS Network-in-a-Box appliance (WORK-036).

An autonomous local network appliance for community or emergency
deployment, composed over the accepted authorities:

- exactly one WORK-034 ``EdgeGateway`` (which owns exactly one
  WORK-033 ``AgentRuntime`` with its WORK-030 management surface);
- exactly one WORK-025 ``ServiceRegistry`` (local services operate
  with NO upstream Internet -- the isolated-site posture);
- exactly one WORK-024 ``DistributedCoreManager`` (local breakout
  gateways and ordinary WORK-011 paths);
- operator provisioning through the declarative ``FabricManifest``
  (pure DATA; validated fail-closed; applied through public
  contracts only).

The appliance adds NO second authority of any kind: no second
identity, session, routing, multipath, policy, transport, service,
or distributed-core authority -- and no vendor/platform leakage into
core.  The frozen public API surface is asserted by the battery.
"""

from .appliance import (
    DISTCORE_PROVIDER_LABEL,
    SERVICES_PROVIDER_LABEL,
    NetworkAppliance,
    run_appliance_headless,
    verify_appliance_replay,
)
from .errors import ApplianceError, ApplianceReasonCode
from .fabric import (
    FabricView,
    build_fabric_view,
    fabric_complete,
    fabric_view_digest,
)
from .isolation import (
    APPLIANCE_EVIDENCE_STATUS,
    check_service_query,
    isolated_site_ready,
    upstream_mode_for,
)
from .model import (
    ApplianceCommand,
    ApplianceCommandKind,
    ApplianceEvent,
    ApplianceEventType,
    ApplianceOutcome,
    ApplianceRunResult,
    ApplianceVerdict,
    FabricManifest,
    GatewayEntry,
    ProvisionState,
    ProvisionStep,
    ProvisionStepKind,
    ServiceEntry,
    UpstreamMode,
    appliance_event_list_digest,
    appliance_events_canonical_bytes,
    derive_appliance_command_id,
    derive_appliance_event_id,
)
from .provisioning import planned_refs, validate_manifest

__all__ = [
    # errors
    "ApplianceError",
    "ApplianceReasonCode",
    # vocabularies and value records
    "UpstreamMode",
    "ProvisionState",
    "ApplianceVerdict",
    "ApplianceCommandKind",
    "ProvisionStepKind",
    "ApplianceEventType",
    "GatewayEntry",
    "ServiceEntry",
    "FabricManifest",
    "ProvisionStep",
    "ApplianceCommand",
    "ApplianceEvent",
    "ApplianceOutcome",
    "ApplianceRunResult",
    "derive_appliance_command_id",
    "derive_appliance_event_id",
    "appliance_events_canonical_bytes",
    "appliance_event_list_digest",
    # isolation boundary
    "APPLIANCE_EVIDENCE_STATUS",
    "upstream_mode_for",
    "check_service_query",
    "isolated_site_ready",
    # provisioning
    "validate_manifest",
    "planned_refs",
    # fabric view
    "FabricView",
    "fabric_complete",
    "build_fabric_view",
    "fabric_view_digest",
    # composition
    "NetworkAppliance",
    "run_appliance_headless",
    "verify_appliance_replay",
    "SERVICES_PROVIDER_LABEL",
    "DISTCORE_PROVIDER_LABEL",
]
