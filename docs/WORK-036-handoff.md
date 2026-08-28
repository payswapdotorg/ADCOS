# WORK-036 — Network-in-a-Box: Implementation Handoff

**Status:** EXECUTION-DESIGNATED — implement only WORK-036.

## Objective
Package ADCOS as an autonomous local network appliance for community or emergency deployment.

## Hard dependencies
WORK-024 (distributed-core adapters), WORK-025 (service registry),
WORK-030 (management API), WORK-033 (Linux agent),
WORK-034 (Raspberry Pi edge gateway) — all Architect-accepted and merged.

## Acceptance
- local services operate without upstream Internet;
- multiple access adapters can coexist;
- operators can provision a complete local fabric.

## Architecture boundary
- Compose over accepted authorities only; no second identity, session,
  routing, multipath, policy, transport, service, or distributed-core
  authority.
- The appliance owns exactly one WORK-034 ``EdgeGateway`` (which owns
  exactly one WORK-033 ``AgentRuntime`` with the WORK-030 management
  surface inside) plus exactly one WORK-025 ``ServiceRegistry`` and one
  WORK-024 ``DistributedCoreManager``, wired to THE runtime's session
  store through read-only projections.
- Preserve the sacred ``session_id``, provenance, replay, transaction,
  and recovery semantics; agent commands flow through the UNCHANGED
  edge scheduling path (resource-awareness inherited, never
  re-implemented).
- Operator provisioning is declarative DATA (the ``FabricManifest``
  over accepted WORK-024/W025/W011 objects), validated fail-closed and
  applied through public contracts only; a validated manifest is either
  applied in full or rejected with typed, journaled reasons.
- The appliance's service surface is LOCAL by construction: federated
  queries are refused with typed reasons under both postures (never
  silently downgraded); no federation trust state is wired.
- Do not implement WORK-037+.

## Verification
Deterministic isolated-site integration: local services register,
discover, resolve, and execute with no upstream Internet; multiple
access adapters coexist OPEN; a complete fabric provisions from a
manifest (and invalid/conflicting manifests are rejected with typed
reasons, nothing partial called provisioned); two complete appliances
form an isolated community network (ordinary session, byte-identical
datagram round-trip, live local service, local breakout through a
provisioned gateway and path); upstream posture transitions are
journaled and forwarded; sessions survive them with their ``session_id``
unchanged; operators work through the accepted WORK-030 surface;
determinism across fresh runs and hash seeds; replay verification;
structural audits (no shadow authority, import discipline, secret
hygiene, injected clock only); frozen surfaces (API, spec/, PR-delta
shape, CI wiring).

## Evidence
Automated/isolated-site software integration evidence is required.
Physical appliance deployment at a real site is separate environment
evidence and must remain explicitly classified as OPEN until genuinely
demonstrated (an isolated-site simulation is engineering verification,
never a physical-deployment PASS).

## Out of scope
Frozen architecture changes, new protocol semantics, federation
exchange wiring, remote-core breakout hosting, vendor/platform
authority leakage into core, later Work Items.
