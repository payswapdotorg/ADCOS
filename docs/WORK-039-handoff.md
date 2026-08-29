# WORK-039 — Federation at scale: implementation handoff

**Branch:** `work-039-federation-at-scale` (anchored on `main@06c445a`)
**Architect handoff:** `spec/prompts/WORK-039.md` (commit `7274384`, byte-untouched)
**Package:** `scale/` (9 modules, 46 frozen exports)
**Battery:** `tools/scale_selftest.py` (38 cases)
**Status:** delivered for Architect review; not self-merged.

## What was built

A deterministic multi-domain federation-at-scale harness proving the
frozen acceptance criteria over the ACCEPTED authorities only:

| Criterion (frozen) | Where it is proven |
|---|---|
| **Federation scales horizontally** | `scale/topology.py` (4 frozen shapes with EXACT edge-count formulas), `scale/world.py` (one REAL WORK-015 `FederationStore` per domain — never a second, centralized authority), the battery's scaling ladder (N = 6/12/24/48 over `cliques`: relationships 15/31/64/128 and grants 120/248/512/1024 exactly as predicted; monotone journal growth; 64 MiB / 120 s resource envelope; measured 4 MiB peak). |
| **Failure domains remain isolated** | `scale/partition.py`: failures partition DELIVERY only (never protocol state). Isolation is PROVEN by byte-identical store digests across every failure window (`IsolationProof`), fail-closed foreign/identity-confused/third-domain/same-slot declarations with side-effect-free rejections, poison containment at the target store, and LOCK-012 local-first survival (relationships with a failed peer stay queryable with full history). |
| **Revocation propagates predictably** | `scale/revocation.py`: the revoking domain's own store executes the authoritative `revoke_relationship`; declarations then propagate in EXPLICIT ROUNDS bounded by the pre-computed graph distance (BFS over the UP delivery subgraph); the `convergence-mismatch` guard fails closed if observation ever diverges from the bound; idempotent re-delivery proven by `replayed` verdicts with unchanged digests; partitioned peers are honestly `unreached` (no fabricated state — digest-proven identical to a no-revocation world) and converge exactly at partition healing. |
| **Large-scale simulation + integration** | `scale/scenario.py` (the deterministic journaled scenario runner: content-derived event ids, injected W031 `ScenarioClock`, TRUE replay verification, insertion-order independence, `PYTHONHASHSEED` invariance) + `scale/integration.py` (three REAL participants: two booted WORK-033 `AgentRuntime` instances + one booted WORK-036 `NetworkAppliance`, federating through their own `federation()` stores with the domain operator NodeID bound to each participant's REAL agent node id). |

## Composition surfaces (all accepted, all reused as-is)

- **WORK-015 federation authority** — `FederationStore` (one per domain),
  `create_domain` / `transition_domain` / `establish_relationship` /
  `publish_grant` / `revoke_relationship` / `apply_exchange` /
  `check_scope` / `snapshot`, `FederationExchange` authoring,
  `derive_domain_id` (the ONLY domain-id derivation — the harness never
  invents a second grammar), the frozen `Scope` vocabulary.
- **WORK-031 simulator primitives** — `ScenarioClock` (the injected
  deterministic time base: ticks → RFC 3339 UTC) and
  `DeterministicStream` (the documented counter-based sha256 PRNG for
  domain key material). The harness reuses the W031 disciplines
  verbatim: explicit `(at_tick, sequence)` execution keys,
  content-derived ids, trace digests, replay verification, and the
  failure taxonomy split (domain failure = node-down; link partition =
  link-down; the simulator's own battery holds those precedents).
- **WORK-033 Linux reference agent** — `AgentRuntime` booted exactly the
  way the agent battery boots it (`StepClock` +
  `StaticInterfaceSource` + boot secret), its `federation()` store as
  the integration participant's real authority, `runtime.node_id` as
  the domain operator NodeID (the honest binding).
- **WORK-036 Network-in-a-Box appliance** — `NetworkAppliance` in the
  ISOLATED upstream posture, booted through `run_appliance` with BOOT +
  EXPOSE_INTERFACES commands (the appliance battery's own construction
  pattern), the gateway runtime's `federation()` store as the third
  participant.
- **Transitive fixture material** — `edge` (the appliance's own
  hardware-inventory fixture surface: `board_for`,
  `HardwareInventory`, `StaticHardwareSource`) and `conformance.model`
  (the W032 `EvidenceClass` vocabulary, reused as DATA — the W037/W038
  precedent; W033, a declared W039 dependency, composes W032 the same
  way in `agent/runtime.py`).

## Boundaries held

- **No second federation authority**: the harness constructs exactly one
  `FederationStore` per domain (in `world.py` only), never a central
  store, never a shadow relationship/grant/event table. Every protocol
  mutation flows through a real store's public contract; the journal is
  evidence, never protocol state (a journal entry can never be replayed
  into a store).
- **No duplicated identity/session/routing/policy semantics**: the
  harness derives domain ids through the real WORK-015 fingerprint,
  references WORK-004 NodeIDs by canonical text (never derives or
  rotates them), and holds zero route/session/policy state.
- **Simulation never becomes protocol truth**: the failure model is
  delivery-plane only. A failed domain is a domain the harness will not
  deliver to or from; a partitioned link is a link the harness will not
  deliver across. Neither is a lifecycle mutation, a topology claim, or
  any store state — and the stores' own validation remains the only
  gate that decides what state may change (the battery's foreign-
  declaration matrix proves the real store rejects identity confusion,
  third-domain declarations, sequence conflicts, and gaps).
- **No frozen protocol semantic modified**: `spec/` is byte-identical to
  `origin/main` except the Architect's branch-anchored handoff
  (battery case_36); the PR delta touches no core directory (case_26 +
  case_37).
- **Access neutrality**: no access-technology or vendor tokens anywhere
  in `scale/` (case_30); no wall-clock reads (case_27); no randomness
  (case_28); no secrets in any artifact (case_29).
- **No W040+ semantics**: the harness implements exactly the W039
  objective; nothing beyond.

## Verification

- `tools/scale_selftest.py`: 38/38 (two complete full-context runs
  byte-identical).
- Determinism: fresh runs byte-identical; `PYTHONHASHSEED` 1/99/31337
  reproduce the run digest; reversed plan/scope tuples produce the
  identical spec and run digests (insertion-order independence).
- TRUE replay: `verify_scale_replay` re-runs from the spec and compares
  digests; seed tamper and digest forgery both fail.
- Hand-verified exact counts for the canonical 12-domain scenario:
  31 relationships, 248 grants, 202 declarations (124 + 6 + 72), all
  applied, 0 rejected, 4 idempotent replays, 420 journal events;
  convergence rounds 1 with bound 1 (direct) and exactly 5 with bound 5
  (LINK-partitioned relay around a 6-ring); peers 1+2 converge exactly
  at the recovery tick.
- All prior batteries green after the DAG-sanctioned allowlist
  amendments: agent 45/45, edge 48/48, mobile 45/45, appliance 42/42,
  oran 36/36, imt 34/34.
- CI: one additive step ("Run federation-at-scale tests") after the
  imt step (work-item order).

## Narrowing amendments to accepted surfaces (all DAG-cited)

The six successor batteries' PR-delta shapes admit this branch's files
(the W038 precedent, work-item order in every case): `agent` case_40,
`edge` case_46/47, `mobile` case_43/44, `appliance` case_40/41, `oran`
case_34/35/36, `imt` case_32/33 — each gains the WORK-039 anchor
admission (commit `7274384`, byte-untouched), the
`tools/scale_selftest.py` + `docs/WORK-039-*.md` entries, and the
`scale/` prefix. The `oran` case_35 workflow-delta check adopts the
agent case_40 "never weakened" successor pattern (a successor appending
its own CI step further down the workflow pushes the interop step out
of the diff hunk context; the discipline becomes "present in the delta
OR present in the committed workflow and never weakened").

## Evidence disclosure

See `docs/WORK-039-evidence.md`. Classes A and B are closed in-repo;
real-deployment evidence is NOT part of the frozen W039 acceptance
criterion (per the handoff) and is not claimable by any in-repo
artifact — the anti-promotion rule is enforced in code
(`scale.evidence.assert_no_deployment_claim`).

## Open external obligations (unchanged)

W020 SDR, W034 hardware, W035 Android device, W036 site, W037 real 5G
lab — all 🟡 OPEN, all non-blocking, none affected by WORK-039.
WORK-039 adds NO new external evidence obligation.
