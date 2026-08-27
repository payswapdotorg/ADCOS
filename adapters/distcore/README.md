# ADCOS Distributed-Core Adapter Family (WORK-024)

**Status: ACTIVE — Module Authority: distributed user-plane / local breakout / UPF placement behind the frozen `/adapters` boundary.**

Implements the frozen WORK-024 backlog entry (spec/work-items.md): distributed user-plane and local-service placement so ADCOS can keep local traffic local, fail over remote gateways, coexist with real 5G UPF and generic IP gateway adapters, and choose local versus remote breakout through policy. Peers: `adapters.ip` (WORK-018), `adapters.fivegc` (WORK-019), `adapters.wifi` (WORK-021), `adapters.backhaul` (WORK-022), `adapters.mesh` (WORK-023).

## Authority boundary

The central W024 rule — the distributed core **composes existing authorities; it does not create competing ones**:

```
ADCOS session_id (WORK-012, sacred)      != breakout gateway identity
                                         != ordinary path identity (WORK-011, DATA)
                                         != breakout identity (mutable, opaque)
                                         != allocation identity
                                         != external gateway identifier (DATA)

ADCOS policy authority (WORK-010)        != this family (records policy DATA, never evaluates)
ADCOS routing authority (WORK-011)       != this family (consumes ordinary Paths, never scores)
ADCOS IP semantics (WORK-018)            != this family (composes IP paths, recreates no IPv6/NAT primitive)
5G UPF / gateway implementation state    stays adapter-owned (LOCK-016/017)
```

## Module catalog

| Module | Role |
|---|---|
| `contract.py` | `BreakoutProviderContract` ABC (11 operations) + `BreakoutContext` least-authority facade + `SessionReader`/`SessionView` |
| `model.py` | frozen vocabularies + `GatewayDescriptor`/`GatewayEvidence`/`GatewayCandidate`, `BreakoutDecision` (policy DATA), `BreakoutBinding`, `BreakoutAllocation`, `EgressOutcome`, `BreakoutEgress`, `DistCoreObservation`, `DistCoreEvent` + the deterministic `derive_*` family |
| `validation.py` | opaque-ref grammar, ref/session separation, credential-like rejection, NodeID/path/session shapes, external-gateway-id DATA validation |
| `errors.py` | `DistCoreError`/`DistCoreReasonCode`/`DistCoreFailure` (typed, isolated, secret-free) |
| `sandbox.py` | `SandboxedBreakoutProvider` (exception isolation, contract enforcement, deterministic budget) + `STEP_CHARGES` |
| `engine.py` | `ReferenceIPGatewayEngine` — the LOCAL breakout reference implementation (validate/commit split, candidate-sequence discipline) |
| `upf.py` | `ReferenceUPFEngine` — the INDEPENDENT remote breakout (5G-UPF-shaped, TS 23.501 N6/PDU-session reference shapes as DATA) implementation |
| `manager.py` | `DistributedCoreManager` — the mediated composition service (B2 ownership, policy decision verification, path/gateway resolution, failover with compensation, canonical state) |
| `bridge.py` | `DistCoreTechnologyAdapter` — the WORK-016 nine-op SDK bridge over the manager |
| `serialization.py` | canonical-JSON reduction helpers |

## Local vs remote breakout is a policy determination (DATA)

`DistributedCoreManager.apply_policy_decision` consumes a **REAL** `policy.model.PolicyDecision` — `isinstance`-enforced, tamper-evident (the `decision_id` is verified against the decision's canonical bytes), ALLOW-effect (a denied decision never authorizes a breakout; the distributed core never overrides policy), and fresh (future-dated decisions are stale). The mode (`local` / `remote`) is the policy determination the composition root read off the policy evaluation (e.g. a locality-domain allow); the manager records it on a **session-scoped** decision record (`distcore:decision:<hex>` derived over session + decision + mode + instant) so a decision applied for one session can never authorize another.

## Local-first path selection composes WORK-011

`register_path` consumes an ordinary `routing.model.Path` object **as DATA** (feasible paths only, fail-closed): the ordinary path fingerprint IS the breakout path reference; the family mints no parallel route identity and never enumerates, scores, or selects paths. The local-first composition: the composition root registers a short LOCAL path (destination = the local gateway node) and a REMOTE path (destination = the remote gateway node), and the policy-determined mode picks the mode-matching one at establish — the manager resolves the path's destination node to a mode-matching gateway (`PATH_GATEWAY_MISMATCH` / `GATEWAY_AMBIGUOUS` fail closed). The egress record composes the policy-determined locality with the path's deterministic latency (WORK-011 `RouteMetrics` captured at establishment).

## Gateway evidence (a gateway is a role, not an identity)

`register_gateway` requires `GatewayEvidence` whose `claim_digest` binds to the **whole** claim (SHA-256 over the canonical descriptor content): unevidenced registration or a digest mismatch fails closed with `GATEWAY_UNEVIDENCED` (the WORK-018 `GatewayResolver` discipline). The evidence provenance class (`direct-observation` / `remote-claim`) is preserved verbatim on the candidate — a relay-reported gateway never silently becomes direct-observed (LOCK-008). External seam identifiers (an Open5GS UPF instance id, an N3IWF gateway id, a vendor element name) ride as opaque DATA and are rejected if they match any ADCOS identifier grammar.

## Failover and partition recovery (explicit transition semantics)

`failover_binding` is the **explicit** gateway/provider transition (invariant 7): validation is side-effect free; the external confirmation (the NEW provider breakout) commits only on success — a failed confirmation leaves the OLD binding byte-identically intact; on success the old binding is SUPERSEDED with the supersedes/superseded_by chain preserved and the **session_id never changes**; the OLD provider breakout is released best-effort AFTER the authoritative commit, so a partitioned old provider never blocks failover (exactly when failover is needed); a commit-phase fault compensates by releasing the NEW breakout (the WORK-022 `managed.py` discipline). Local breakout degrades gracefully: an unavailable gateway fails closed (`GATEWAY_UNAVAILABLE`) at establish and egress while alternate remote paths stay establishable; recovery is the same explicit transition back.

## Composing the REAL seams (the composition root)

The family imports no other family (the frozen family-separation discipline; enforced by the selftest's AST audit). Real-provider composition happens at the **composition root**, where the integrator wraps the accepted public manager APIs behind `BreakoutProviderContract`:

```python
manager = DistributedCoreManager(session_reader=reader)
manager.register_provider(ReferenceIPGatewayEngine(), label="local",
                          breakout_mode="local", now=now)
manager.register_provider(ReferenceUPFEngine(), label="remote",
                          breakout_mode="remote", make_default=False, now=now)
```

The WORK-024 selftest proves the identical recipe against the **REAL** WORK-018 `IPIntegrationManager` (local breakout: `bind_session` → `app_socket().send()` through the mediated egress path) and the **REAL** WORK-019 `FiveGCoreManager` (remote breakout: `bind_session` → `authenticate` → `establish_pdu_session` → `egress_pdu`) wrapped as breakout providers — 5G UPF and generic IP gateway functions coexisting behind adapters, session identity preserved across the gateway change.

## Determinism and honest scope

Deterministic by construction: no wall clock, no randomness, no I/O; every identity is content-derived over WORK-003 canonical bytes; repeated runs and `PYTHONHASHSEED` variation produce byte-identical canonical digests (pinned by the selftest). The reference engines are deterministic in-process models — the handoff's sanctioned conformance vehicles; **no simulator or in-repo peer may satisfy a required real-provider interoperability criterion** (invariant 10), and no real-provider interop gate is required by the WORK-024 handoff (its verification matrix — failover, latency, locality, partition — is deterministic). No proprietary UPF/gateway element is implemented (frozen out-of-scope); no NAT/IPv6/routing primitive is recreated (W018 owns IP semantics).

## Verification

`python3 tools/distcore_selftest.py` — the WORK-024 battery (40 cases): family-surface freeze, least-authority context, model/validation invariants, gateway evidence fail-closed, REAL WORK-010 policy decision verification (tampered/denied/stale/cross-session), ordinary-Path registration (REAL WORK-011 metrics), local and remote establishment, **UPF/IP-gateway coexistence**, **local traffic stays local** (the remote provider's delivery log stays empty), deterministic latency/locality, **policy determines local vs remote**, **session identity across failover** (chain preservation), **remote gateway failover under partition**, graceful degradation with alternate remote paths, **partition recovery**, failover validation fail-closed, no retroactive rebinding (B2 provider swap), capacity fail-closed (zero-capacity gateways contribute nothing), sandbox/contract/budget isolation, secret isolation, canonical-state shape, teardown fail-closed, the WORK-016 nine-op bridge, standards-boundary and no-core-leakage audits, determinism (repeated runs + `PYTHONHASHSEED`), frozen-`spec/` byte-identity, observation honesty, cross-implementation byte identity, the **REAL W018 IP-seam** and **REAL W019 5GC-seam** composition cases (coexistence + failover across the real seams), and the validate/commit sequence discipline (failed operations consume no identity-derivation state — the PR #24 lesson applied from day one, with the discriminating regression).
