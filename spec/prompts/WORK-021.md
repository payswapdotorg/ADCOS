# WORK-021 — Wi-Fi / non-3GPP Access Adapter

## Status

ARCHITECT-ANCHORED IMPLEMENTATION BRIEF

## Work Item

WORK-021 — Wi-Fi/non-3GPP access adapter

## Dependencies

Hard dependencies satisfied by accepted main: WORK-018 (IPv6/IP integration) and WORK-019 (5G Core integration adapter). WORK-020 is NOT a dependency and remains independently blocked on SDR-lab evidence; do not import or depend on the unaccepted WORK-020 branch.

## Objective

Integrate Wi-Fi and non-3GPP access, including a standards-based 5G Core-compatible path where required, while keeping all access/vendor authority behind `/adapters` and preserving the access-independent ADCOS session model.

## Acceptance Criteria

1. The same ADCOS logical session model can use Wi-Fi and 5G.
2. N3IWF/TNGF or an equivalent standards-based mechanism remains behind the adapter boundary.
3. Access change is transparent to session authority where supported.
4. Wi-Fi/non-3GPP adapter failures are isolated from ADCOS core state.
5. No Wi-Fi chipset/vendor API or non-3GPP implementation type crosses into core.
6. Real mixed-access interoperability is exercised as far as the available environment permits; any hardware/environment limitation must remain an explicit gate, never a fabricated PASS.

## Required Architecture

Build under the frozen `/adapters` boundary, using the accepted WORK-016 Adapter SDK as the generic bridge. Establish a Wi-Fi/non-3GPP domain seam with least-authority context, sandbox mediation, deterministic reference implementation, concrete standards-shaped adapter, and environment-gated real interoperability path as appropriate.

Critical identity invariant:

`session_id` is sacred and access-independent. Wi-Fi access identity, station association identifiers, N3IWF tunnel/session identifiers, NAS/IPsec tunnel identifiers, and vendor/chipset identifiers must remain adapter-side opaque data. Access changes must bind to the existing logical session rather than creating a new SessionID merely because the access changes.

NAT/IPv4 remains adapter/policy behavior, not core identity. N3IWF/TNGF and any 5G-core-specific state remain outside core authority.

## Out of Scope

WORK-020 RAN implementation or SDR acceptance; Wi-Fi chipset firmware; vendor SDKs crossing into core; application-layer Wi-Fi APIs; replacing WORK-018 IP semantics; changes to frozen architecture/specification documents unless explicitly authorized by an ACR.

## Verification

Implement a comprehensive `tools/wifi_selftest.py` (or equivalent family naming consistent with repository conventions) covering:

- WORK-016 SDK bridge and nine-op surface;
- Wi-Fi/non-3GPP capability/health/resource translation;
- session identity/access identity separation;
- adapter failure isolation, BaseException isolation, contract-shape validation, deterministic budget;
- per-binding implementation ownership across implementation swaps;
- standards-boundary audit for N3IWF/TNGF/vendor leakage;
- mixed-access session continuity with 5G where environment supports it;
- deterministic snapshots and cross-implementation canonical equivalence;
- environment-gated real interoperability with anti-faking behavior.

Run the full accumulated battery and preserve frozen `spec/` byte identity.

## Review Gate

Z.ai must not merge this Work Item. Return the implementation as an open PR for Architect review. WORK-022 remains blocked until WORK-021 is Architect-accepted.
