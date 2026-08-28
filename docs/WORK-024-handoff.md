# WORK-024 — Distributed Core / Local Breakout / UPF Integration

## Authority

This handoff is anchored to the frozen ADCOS architecture and backlog on `main`. WORK-020 is intentionally not a dependency and must not be imported or required.

## Hard dependencies

- WORK-018 — IPv6/IP integration — accepted
- WORK-019 — 5GC adapter — accepted
- WORK-021 — Wi-Fi/non-3GPP adapter — accepted
- WORK-022 — Ethernet/fiber/microwave/satellite backhaul — accepted

WORK-023 is not a hard dependency of WORK-024.

## Objective

Implement distributed user-plane and local-service placement so ADCOS can keep local traffic local, fail over remote gateways, coexist with real 5G UPF and generic IP gateway adapters, and choose local versus remote breakout through policy.

## Required architecture

```text
ADCOS Policy / Routing / Session authority
                 |
                 v
        DistributedCoreManager
          /              \
 local-breakout          remote-breakout
      |                       |
   adapter/provider       adapter/provider
      |                       |
 W018 IPv6/IP seam       W019 5GC/UPF seam
                          W021 Wi-Fi seam
                          W022 backhaul seam
```

## Non-negotiable invariants

1. SESSION authority remains WORK-012. Distributed-core bindings must never replace or reinterpret `session_id`.
2. Policy determines local versus remote breakout; the distributed-core module must not invent a second policy authority.
3. 5G UPF and generic IP gateway state remain adapter-owned. No Open5GS, N3IWF, vendor, or gateway implementation types may cross into core authority.
4. WORK-018 owns ordinary IP semantics. WORK-024 composes IP paths; it must not recreate IPv6/NAT/routing primitives.
5. A gateway is a role, not an identity. Reported gateway evidence remains provenance-bearing DATA until accepted by the appropriate authority.
6. Local breakout must degrade gracefully when unavailable and preserve alternate remote paths where policy/capabilities allow.
7. Gateway/provider replacement must preserve existing logical session identity and must not retroactively rebind established flows to a new implementation without explicit transition semantics.
8. Validation must be side-effect free; externally confirmed operations commit local state only after success, with compensation for partially completed external operations.
9. Canonical state must exclude implementation labels, credentials, sockets, process-specific identifiers, and other non-authoritative diagnostics.
10. Deterministic reference implementations may be used for conformance, but no simulator or in-repo peer may satisfy a required real-provider interoperability criterion.

## Frozen acceptance criteria

- local traffic can remain local;
- remote gateway failover works;
- 5G UPF and generic IP gateway functions can coexist behind adapters;
- policy determines local vs remote breakout.

Required verification: failover, latency, locality, partition tests.

## Expected implementation surface

Prefer a new family under the frozen `/adapters` boundary only where provider-specific behavior is required, plus a small core composition layer if necessary. Do not create a new top-level module unless the frozen architecture already authorizes one.

Expected concerns include:

- local/remote breakout decision representation as DATA from policy;
- gateway candidate and evidence records;
- per-binding/provider ownership;
- local-first path selection composition with WORK-011 routing;
- UPF/IP gateway adapter mediation;
- failover and partition recovery;
- deterministic latency/locality test fixtures;
- W016 SDK bridge where a concrete provider needs generic adapter lifecycle integration.

## Verification gate

Return an open PR only after:

- focused WORK-024 selftest suite covers all acceptance criteria;
- failover and partition behavior are proven;
- local/remote locality decisions are deterministic;
- session identity is preserved across gateway changes;
- adapter/provider state cannot become core authority;
- full existing battery remains green;
- frozen `spec/` remains byte-identical;
- CI is green.

Z.ai must not merge the PR. The Architect performs final acceptance and merge.
