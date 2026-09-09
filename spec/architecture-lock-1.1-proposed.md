# ADCOS Architecture 1.1 — Normative Locks

**Status:** ACCEPTED — FROZEN via ACR-014 (accepted proposal record; the normative locks are canonical at `spec/architecture-lock.md`)

1. **LOCK-101 Canonical Contract** — `ConnectivityContract` is the authority for acquired connectivity.
2. **LOCK-102 Intent Independence** — application intent is technology-neutral and does not select implementation mechanisms.
3. **LOCK-103 Application Purchasing** — authorized applications may purchase or sponsor connectivity for bounded beneficiaries.
4. **LOCK-104 Provider Sovereignty** — providers retain domain-local topology, routing and subscriber authority.
5. **LOCK-105 No Global Topology Requirement** — ADCOS MUST NOT require a global graph of all provider infrastructure.
6. **LOCK-106 Evidence Typing** — claim, observation, commitment and attestation are distinct evidence types.
7. **LOCK-107 Closed-loop Assurance** — active contracts are continuously evaluated against their obligations.
8. **LOCK-108 No Silent Contract Weakening** — replanning cannot weaken hard contract constraints.
9. **LOCK-109 Execution Bridge** — ExecutionPlan is the bridge from contract to concrete provider mechanisms.
10. **LOCK-110 Adapter Isolation** — provider-native SDK types remain behind adapters.
11. **LOCK-111 Optimizer Replaceability** — optimizer strategy is not a normative authority.
12. **LOCK-112 Standard Leverage** — ADCOS MUST prefer existing standard mechanisms where they satisfy a requirement.
13. **LOCK-113 Commercial Separation** — payment movement is external; ADCOS records connectivity commercial authority and settlement references.
14. **LOCK-114 Developer Semantics** — application APIs expose connectivity services, not network implementation objects.
15. **LOCK-115 Simple-System Validity** — single-provider/simple deployments do not require federation, multipath or global optimization.
16. **LOCK-116 Complex-System Composition** — multiple providers, segments and access technologies may compose under one contract.
17. **LOCK-117 Authority Uniqueness** — no `Path`, `Session`, `Tunnel`, `eSIM`, adapter or provider record may become a second contract authority.
18. **LOCK-118 Provenance** — every externally asserted capability, commitment, measurement and attestation has issuer and provenance.
19. **LOCK-119 Secrets** — provider credentials and subscriber secrets never enter contract or federation metadata.
20. **LOCK-120 Vertical Proof** — ShareNet, RoamLink and COMOS integration paths are compatibility proofs, not core ownership transfer.
