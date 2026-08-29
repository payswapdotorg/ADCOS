# WORK-039 — Evidence disclosure

## Evidence classes (per the frozen handoff)

| Class | Meaning | Status |
|---|---|---|
| A | Architecture conformance | **supported-verified** (in-repo) |
| B | Automated verification | **supported-verified** (in-repo) |
| C | Real deployment evidence | **not-required-not-claimable** (per the frozen handoff: "Real deployment evidence is not part of the frozen W039 acceptance criterion unless a new ACR says otherwise") |

## Class A — architecture conformance (closed in-repo)

- The harness composes ONLY accepted surfaces: one real WORK-015
  `FederationStore` per domain (never a second, centralized federation
  authority — 12 distinct real store instances at N=12, asserted by the
  battery), the WORK-031 `ScenarioClock` + `DeterministicStream`
  primitives (injected time, documented PRNG), and the WORK-033/W036
  agent/appliance composition surfaces constructed exactly the way the
  accepted batteries construct them.
- **No frozen protocol semantic modified**: `spec/` byte-identical to
  `origin/main` except the Architect's branch-anchored handoff
  (unmodified since commit `7274384`); the PR delta touches no core
  directory; 102 core modules import no `scale/`.
- **No duplicated authority**: domain ids derive ONLY through the real
  WORK-015 fingerprint; NodeIDs are referenced by canonical text, never
  derived or rotated; the harness holds zero route/session/policy
  state; no foreign authority constructor appears anywhere in the
  family (the battery's constructor-zone audit pins `FederationStore`
  to `world.py` and `AgentRuntime`/`NetworkAppliance` to
  `integration.py`).
- **Simulation never becomes protocol truth**: the failure model is
  delivery-plane only; every protocol mutation flows through a real
  store's public contract; the journal is evidence, never protocol
  state; the real store validation is the only state-changing gate
  (proven by the foreign-declaration negative matrix).
- **Access neutrality**: no access-technology/vendor tokens, no wall
  clock, no randomness, no secrets (the battery's structural audits).

## Class B — automated verification (closed in-repo)

The deterministic large-scale simulation (`scale.scenario.run_scale_scenario`)
observes and journals, with exact hand-verified counts:

- **Horizontal scaling**: the 6/12/24/48 ladder over `cliques` produces
  relationships 15/31/64/128 and grants 120/248/512/1024 exactly as
  the frozen formulas predict; journal growth tracks topology growth;
  the resource envelope holds (measured peak 4.0 MiB against the 64 MiB
  gate; N=48 in ~5.6 s against the 120 s gate).
- **Large-scale capability/route exchange**: 202 declarations across the
  canonical 12-domain scenario (124 wave-1 + 6 revocations + 72
  wave-2), every one applied through the real `apply_exchange` with
  provenance journaled; 0 rejections.
- **Failure-domain isolation**: every failure window leaves all ten
  non-failed stores byte-identical (`IsolationProof`); a local
  mutation at one store never reaches another domain's store;
  identity-confused, third-domain, and same-slot-conflict declarations
  fail closed with side-effect-free rejections; a poisoned
  (sequence-gap) declaration is contained at its target store with the
  world digest byte-identical.
- **LOCK-012 local-first**: relationships with partitioned peers remain
  queryable with full history, including across link partitions (both
  endpoint stores stay queryable).
- **Revocation propagation**: convergence observed in EXPLICIT rounds
  that always equal the pre-computed graph-distance bound (1 round
  direct; exactly 5 rounds for the LINK-partitioned relay around a
  6-ring); idempotent re-delivery (`replayed` verdicts, unchanged
  digests); predictable scope closure (`relationship-terminal`) at
  every converged store; partitioned peers honestly `unreached` with
  their stores digest-identical to a no-revocation world (no fabricated
  convergence); post-recovery convergence exactly at the healing tick.
- **Determinism**: fresh runs byte-identical; `PYTHONHASHSEED`
  1/99/31337 reproduce the run digest; reversed plan/scope tuples
  produce identical spec and run digests; TRUE replay verification
  (fresh re-run) with seed-tamper and digest-forgery divergence.
- **Integration**: the three-participant run (two real agents + one
  real appliance, booted through their public construction surfaces)
  passes all ten checks — boots, capability exchange between agents,
  route exchange into the appliance federation store, authoritative
  revocation at the issuing agent, propagation to the appliance store,
  terminal REVOKED state, closed scope evaluation, isolation of the
  unrelated agent store (digest-identical across the revocation), and
  idempotent replay — with a deterministic replayable digest.

The integration leg runs on genuine WORK-004 identity machinery (the
dev HMAC profile), real policy publication, and the real appliance
provisioning path — all through public contracts.

## Class C — real deployment evidence: NOT REQUIRED, NOT CLAIMABLE

The frozen WORK-039 contract requires in-repo architecture conformance
and automated large-scale simulation/integration only. Real multi-region
deployment evidence is **not required** by that contract — and nothing
in this repository can claim it:

- `scale.evidence.classify_scale_evidence` refuses any
  `deployment_outcome` attachment with the typed
  `scale.evidence-class-violation` error;
- `scale.evidence.assert_no_deployment_claim("C")` raises the same
  violation (classes A and B may never be promoted to class C);
- the recorded statement
  (`scale.evidence.DEPLOYMENT_EVIDENCE_STATEMENT`) states that the
  simulated multi-domain evidence can never be promoted to
  real-deployment evidence and that a future requirement arrives as a
  new ACR with its own contract.

This is the honest reading of the handoff's Evidence section. It
differs deliberately from WORK-037 (class C OPEN and closable only by a
real lab) and WORK-038 (class C NOT APPLICABLE at all): for WORK-039
the class exists, is not required by the frozen acceptance, and is
structurally unclaimable in-repo.

## Open external obligations (unchanged after WORK-039)

| Obligation | Status |
|---|---|
| W020 physical SDR evidence | 🟡 OPEN |
| W034 Raspberry Pi hardware evidence | 🟡 OPEN |
| W035 real Android device evidence | 🟡 OPEN |
| W036 site evidence | 🟡 OPEN |
| W037 real 5G interoperability lab | 🟡 OPEN |

WORK-039 adds **no** new external evidence obligation.
