# M006 — Execution Plan — Evidence Record

**Work Item:** M006 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7
program authorization; M006 is the charter's current child)
**Baseline:** `db2f003d0db087c59dcde46569b9445ed3fe8e03` (the DEC-0105-accepted
M005 state — the live main head; the current-child pointer advances M005 → M006)

This record persists the verified facts of the M006 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without
direct verification (the standing Tech Lead rule). All evidence in this record is
**SOFTWARE class** — simulation/deterministic-battery evidence only; no
PHYSICAL PASS is claimed or implied, and EVID-002..EVID-008 remain open and
untouched.

## 1. Delivered surface

- **`executionplans/` (NEW)** — the contract-to-execution-plan translation domain
  (LOCK-109), composed of:
  - `executionplans/errors.py` — the frozen `plan-*` typed reason vocabulary
    (15 fail-closed codes; `ExecutionPlanError` with stable `code`/`detail`;
    consumed-domain validation errors are wrapped — exception isolation, no raw
    exception text into stored state).
  - `executionplans/model.py` — the plan/segment model and the frozen
    vocabularies: the segment state vocabulary **exactly**
    `PLANNED/RESERVED/ACTIVATED/MEASURED/RELEASED` (`RELEASED` terminal; the
    explicit idempotent re-measurement transition `MEASURED → MEASURED` is the
    only self-loop; the M008 replan surface — degraded/failed realization
    states — is deliberately NOT invented here), the segment roles
    `primary/alternative/access` (frozen 1.1 §10: simple = one primary
    segment; complex = multiple providers/segments/access mechanisms/failover
    alternatives under ONE contract, LOCK-116), the capability-oriented
    **adapter-operation vocabulary taken verbatim from frozen 1.1 §6**
    (`inspect-capabilities, inspect-offers, reserve, activate, measure,
    reconfigure, release, health` — names only, LOCK-110: M007 owns the
    adapters and is NOT implemented here), the plannable contract states
    (`OFFER_SELECTED/CONTRACT_ACTIVE/EXECUTION_ACTIVE/DEGRADED` — INTENT has no
    accepted offers; terminal and post-execution states never plan), and the
    tie-break key vocabulary (`role/operation/offer/segment-id` — content keys
    only, never temporal). `ExecutionSegment`: typed, attributable to exactly
    one contract (contract_id), carrying the verbatim accepted-offer
    `OpaqueReference` (LOCK-117/118), role, canonical §6 operation sequence,
    state, and provenance — with a **state-independent content-derived id**
    (state evolution never changes identity). `ExecutionPlan`: attribution,
    the contract's hard-constraint set **preserved verbatim** plus the
    contract's own LOCK-108 fingerprint, the validity window (contained in the
    contract validity), the ordered segments, the declared tie-break rule, and
    planning provenance — with a state-independent content-derived id and
    construction-boundary tamper evidence (constraint-set/fingerprint
    consistency, derived-identity check, attribution, no duplicates, ≥1
    primary, declared-order consistency). The pure transition kernel
    `check_segment_transition`/`apply_segment_transition`: every transition
    validated fail-closed (unknown segment, illegal transition, terminal
    segment, out-of-window engagement — `RESERVED/ACTIVATED/MEASURED` past or
    before the plan validity fails closed; `RELEASE` stays legal at any valid
    instant as cleanup), identity- and constraint-preserving by construction.
  - `executionplans/translation.py` — the LOCK-109 bridge:
    `translate_contract` (deterministic, offline, typed, provenance-carrying;
    the plannable-state gate, the verbatim accepted-offer-only realization
    gate — a lookalike reference with different provenance fails closed —, the
    plan-window containment gate, the declared tie-break normalization with
    the `segment-id` total-order guarantee, and LOCK-108 point 1: **the
    plan's constraint set and fingerprint are taken from the contract; there
    is NO constraint input anywhere on the translation surface**);
    `SegmentInput` (the replaceable optimizer's proposal as DATA, with no
    constraint member by construction); `verify_plan_preserves_contract` (the
    pure LOCK-108 cross-authority gate: verbatim constraint-set equality by
    canonical content in BOTH directions — dropped, relaxed, re-interpreted or
    invented constraints fail `plan-constraint-weakened` citing the specific
    kinds —, fingerprint agreement, attribution, verbatim accepted-offer
    realization, validity containment); `plan_reference` (LOCK-117: the plan
    rides as an opaque `execution-artifact` reference for the contract's own
    frozen `BindExecutionArtifact` command — data, never authority).
  - `executionplans/conformance.py` — **the disclosed composition harvest
    seam**: the WORK-054 chain-orchestration pattern (ordered typed steps
    attributed to owning surfaces, fail-closed) refactored as the plan's typed
    execution sequence, and the WORK-054 conformance-evidence pattern
    (derived-only, digest-carrying, SOFTWARE-class documents with mandatory
    honesty disclaimers) refactored as the plan conformance document —
    `conformance_document` **fail-closes unless
    `verify_plan_preserves_contract` passes** (no evidence over a weakened
    plan, LOCK-108), `conformance_digest` (the WORK-003 canonical-JSON
    SHA-256 convention), `PLAN_BRIDGE_DISCLAIMER` + `HARVEST_DISCLOSURE`
    (the M007-not-implemented honesty, the BLOCKED_MISSING_AUTHORITY chain
    state, the one-way harvest direction, and the no-second-authority
    statement travel with every document).
  - `executionplans/__init__.py` — the public surface (35 names).
- **`composition/` (HARVEST — disclosed, DOCSTRING-ONLY)** — the R7 charter
  M006 scope entry `composition/ (harvest)`: the chain-orchestration and
  conformance-evidence patterns of the WORK-054 layer are harvested onto the
  1.1 authority by `executionplans/` (the patterns live on, refactored, where
  the execution-plan translation is the canonical bridge). The package delta
  is **documentation-only** (module docstrings of `__init__.py`, `chain.py`,
  `orchestrator.py`, `evidence.py` carry the M006 harvest disclosure): **no
  behavior change, no public-API change, no import change** — the frozen
  WORK-054 contract (DEC-0085/DEC-0086) is preserved verbatim, the pinned
  35-name `__all__` export table is byte-identical to origin/main (verified
  in the battery, case_28), WORK-048 stays accepted-not-restored (detected,
  fail-closed, never implicitly restored), and the composition battery itself
  re-runs green at its accepted **55/55** on the M006 delivery head (battery
  case_29). The one-way harvest direction is structural:
  `executionplans/` imports NO composition code, and composition's own
  battery-pinned import allowlist forbids importing `executionplans/` (the
  minimal consistent refactor that preserves every consumer surface — the
  M005 telemetry-harvest precedent: the seam lives in the new domain).
- **`tools/executionplan_selftest.py` (NEW)** — the M006 battery: **36/36 PASS**
  (plus the 12 per-kind LOCK-108 sub-cases folded into the numbered case set —
  see §2), deterministic, offline, seeded.
- **`docs/M006-evidence.md`** — this record.

## 2. Deterministic verification matrix

All runs offline; instants injected (T0-style constants); no wall clock, no
randomness, no UUIDs, no network; no real sockets; no secrets stored
(LOCK-119); PYTHONHASHSEED-safe (verified across processes and seeds 0/1/42).
Exit-code-based verification (a traceback or lowercase "failed" IS a failure).

| Verification | Result | Evidence |
|---|---|---|
| Frozen vocabularies (states/roles/operations/transitions/plannable/tie-break; §6 operation names verbatim; capability-oriented only) | PASS | case_01 |
| (a) Simple translation: real contract via the accepted `contracts/` API + real accepted offer via the accepted `offers/` API → ONE primary segment; constraints verbatim; fingerprint == the contract's; verify passes (frozen 1.1 §10) | PASS | case_02 |
| (b) Complex translation: 4 typed segments over 2 providers (2 primary + 1 failover alternative + 1 access mechanism) under ONE contract; each attributable with accepted-offer provenance (LOCK-116) | PASS | case_03 |
| Plannable-state matrix: all 13 contract lifecycle states probed; exactly OFFER_SELECTED/CONTRACT_ACTIVE/EXECUTION_ACTIVE/DEGRADED translate; INTENT/terminal/post-execution fail closed `plan-contract-not-plannable` | PASS | case_04 |
| Translation inputs fail closed (non-contract, empty, non-SegmentInput, lookalike offer ref, unaccepted offer, wrong ref kind, no primary, duplicate cores, secret-shaped issuer at the boundary, unknown role/operation, repeated operation) | PASS | case_05 |
| Plan window containment (escaping windows fail `plan-temporal-invalid` both directions; contained sub-windows carried; default = the contract validity) | PASS | case_06 |
| (c) **LOCK-108 per constraint kind — all 12 kinds** (latency-bound, throughput-floor, availability-floor, loss-bound, jitter-bound, isolation, jurisdiction, security-level, provider-trust, evidence-obligation, geography, priority): DROP (plan from a contract missing the constraint vs the strict contract), RELAX (weakened params), REINTERPRET (a different kind carrying the strict kind's params) all fail `plan-constraint-weakened` **citing the kind**; wire forgery of the strict plan (relaxed params on the serialized record) fails `plan-constraint-mismatch` at the deserialization boundary | PASS | case_07..case_18 (one case per kind) |
| LOCK-108 structural no-override surface: `SegmentInput` has NO constraint member; `translate_contract` has NO constraint parameter; the authority-true shape (attribution/constraints/fingerprint/validity) is invariant across optimizer proposals; `replace()`-weakened construction fails `plan-constraint-mismatch` | PASS | case_19 |
| (d) Segment state machine legal path: PLANNED→RESERVED→ACTIVATED→MEASURED→(re-MEASURED)→RELEASED with plan id, segment id, constraint fingerprint and constraint set stable at every step | PASS | case_20 |
| Segment state machine exhaustive illegal matrix: all 25 (state, target) pairs probed on real plans — exactly the 8 legal transitions succeed (incl. the idempotent re-measurement), 17 fail closed (`plan-invalid-transition`; out of RELEASED: `plan-segment-terminal`) | PASS | case_21 |
| Transition discipline: unknown segment, past-expiry engagement, before-window engagement, malformed instant, unknown target, non-plan all fail closed; release past expiry legal (cleanup); constraints verbatim across transitions | PASS | case_22 |
| (e) Canonical round-trips: plan/segment/segment-input `to_dict → from_dict → to_dict` byte-stable; canonical bytes stable; stdlib JSON round-trip; transitioned-state round-trips; tampered plan_id (`plan-id-mismatch`) and illegal serialized states (`plan-vocabulary`) fail closed | PASS | case_23 |
| Deterministic ids: sha256 grammar for plan/segment/fingerprint; re-derivation agrees; re-translation byte-identical; distinct cores never collide | PASS | case_24 |
| Cross-process determinism: byte-identical plan ids and conformance digests across PYTHONHASHSEED 0/1/42 subprocesses | PASS | case_25 |
| (f) Provenance resolves: plan.contract_id resolves to the REAL stored contract; every segment offer reference resolves through the REAL exchange (`OfferExchange.resolve`) to the real `OfferRecord`; the offers authority's own `verify_accepted_offers` passes on the fixture; issuers and decision refs preserved (LOCK-118) | PASS | case_26 |
| LOCK-117 plan-is-data: `plan_reference` is the opaque `execution-artifact` kind carrying the plan id + provenance; binding via the contract's own `BindExecutionArtifact` changes NO identity, state, or constraint (artifacts are data, never authorities) | PASS | case_27 |
| (g) Composition harvest seam: W048 still absent-fail-closed (never implicitly restored); the frozen verdict vocabulary (`BLOCKED_MISSING_AUTHORITY` only) unchanged; the WORK-054 chain still blocks at the containment edge with `production_composition=False`; the plan bridge is the canonical 1.1 translation; both sides mint WORK-003 `sha256:` digests; SOFTWARE class + disclaimer + harvest disclosure carried; the derived document deterministic; the composition `__all__` export table byte-identical to origin/main | PASS | case_28 |
| The harvested surface's own battery re-runs green at the accepted count on the M006 delivery head: composition 55/55 | PASS | case_29 |
| (h) Optimizer replaceability (LOCK-111): input order never changes the plan (byte-identical); declared tie-break rules are recorded, deterministic and reproducible (different rules → different disclosed orders/ids); the authority-true shape invariant under every declared rule; omitted total-order keys auto-completed | PASS | case_30 |
| Tie-break validation: unknown key (`plan-vocabulary`), repeated key, non-total rule, empty rule fail closed; the key vocabulary is content-only — no temporal key exists | PASS | case_31 |
| Conformance document discipline: ordered typed execution sequence matches the plan; NO evidence over a weakened plan (the LOCK-108 gate inside `conformance_document`); derived data follows segment state deterministically | PASS | case_32 |
| Clock + import discipline (AST): no wall-clock/randomness/UUID/network constructs in `executionplans/`; imports only stdlib + `protocol` + `contracts` (by reference); NO offers, NO composition, NO provider-SDK family inside the domain | PASS | case_33 |
| Lock conformance mapping: LOCK-101/108/109/110/111/115/116/117/118/119 evidenced on the bridge (simple and complex deployments) | PASS | case_34 |
| PR delta shape: every delta file covered by the ACTIVE R7-CORE-001 scope (`authorization_provenance.covers`); no `spec/` or `.github/` touch | PASS | case_35 |
| Evidence doc honesty: SOFTWARE class, the lock mapping, the state vocabulary, the harvest, and no affirmative physical claims | PASS | case_36 |

**Battery result: PASS (36/36 cases; the 12 per-kind LOCK-108 cases are
individually numbered case_07..case_18 within the set), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `executionplans/` consumes the accepted
  `contracts/` public surface by reference only (imports the frozen public
  types; `contracts/` is untouched — verified in the battery); the plan never
  writes contract state; there is no second contract model (the plan's
  constraint set IS the contract's own set, and its fingerprint is the
  contract's own `hard_constraint_fingerprint()` output).
- **LOCK-108 (no silent contract weakening):** enforced at three points —
  (1) the translation surface has no constraint input (structural);
  (2) plan construction/deserialization verifies the carried constraint set
  against the carried fingerprint and the derived identity (tamper evidence);
  (3) `verify_plan_preserves_contract` fails closed on ANY set difference —
  drop, relaxation, re-interpretation, or invention — citing the specific
  constraint kinds; every transition of the segment state machine preserves
  the constraint set structurally.
- **LOCK-109 (execution bridge):** `ExecutionPlan` is the typed, deterministic,
  provenance-carrying bridge from the canonical contract to capability-oriented
  provider mechanisms; simple and complex (LOCK-115/LOCK-116) deployments
  translate under one contract.
- **LOCK-110 (adapter isolation):** segments reference adapter OPERATIONS by
  name only, from the frozen 1.1 §6 vocabulary; the domain imports no provider
  SDK family; the M007 adapter surface is a pending child — segments never
  carry SDK types, and the battery's AST audits prove it mechanically.
- **LOCK-111 (optimizer replaceability):** the optimizer is replaceable input
  data (`SegmentInput`); the plan shape is authority-true (derived from the
  contract); tie-breaking is deterministic, DECLARED, INJECTED
  (content-key vocabulary only — never wall-clock) and recorded on the plan;
  input order never affects the plan.
- **LOCK-115/LOCK-116:** one contract → one segment (simple) and one contract
  → multiple providers/segments/access mechanisms/failover alternatives
  (complex) are both exercised; no federation/multipath machinery is required
  for the simple path.
- **LOCK-117 (authority uniqueness):** the plan is an EXECUTION ARTIFACT — it
  rides as an opaque `execution-artifact` reference via the contract's own
  frozen command vocabulary; binding changes no identity/state/constraint;
  plan and segment identities are content-derived references, never
  authorities; the composition layer stays the WORK-054 conformance layer
  (no second authority on either side of the harvest).
- **LOCK-118 (provenance):** the plan carries planning provenance (issuer +
  decision refs); every segment carries the verbatim accepted-offer reference
  WITH its provenance and its own planning provenance; `plan_reference`
  carries provenance.
- **LOCK-119 (secrets):** secret-shaped material is rejected at construction
  and deserialization through the consumed contracts-domain guards, surfaced
  as the typed `plan-secret-rejected` reason; no wall clock, no randomness,
  no UUIDs, no network anywhere in the domain (AST-audited).

## 4. Judgment calls (disclosed)

1. **The composition harvest is disclosure-only on the composition side.** The
   charter scope `composition/ (harvest)` is discharged by harvesting the two
   WORK-054 patterns onto the 1.1 authority in `executionplans/conformance.py`
   (the seam, the M005 telemetry precedent) plus the documentation-only
   disclosure in the composition docstrings. A deeper in-place refactor of
   `composition/` to route through the plan bridge is structurally impossible
   without breaking the frozen WORK-054 contract: the composition battery
   (outside this PR's boundary) pins the exact `__all__` export table, the
   import allowlist (which forbids importing `executionplans/`), and the chain
   behavior — and the charter's own scope discipline says to preserve the
   public API surface the batteries consume. The harvest seam is therefore
   one-way and disclosed at both ends.
2. **The plannable-state set** is `OFFER_SELECTED/CONTRACT_ACTIVE/
   EXECUTION_ACTIVE/DEGRADED` (post-offer-binding, pre-settlement). DEGRADED
   is included so a failover alternative can be planned for a degraded
   realization (LOCK-116) without M008; replan semantics themselves remain
   M008 and are not implemented here. DELIVERY/ASSURED/USAGE_FINAL/
   SETTLEMENT_PENDING are post-execution evaluation states and fail closed.
3. **The segment state vocabulary stops at the five charter-named states.**
   No FAILED/DEGRADED segment state is invented — those belong to the M008
   replan/failover child (frozen 1.1 §9: "a realization that cannot satisfy a
   hard contract must enter an explicit degraded/failed state" — M008's
   surface, not M006's).
4. **MEASURED → MEASURED** is the one disclosed self-loop: closed-loop
   assurance re-observes an active segment; each re-measurement is an
   explicit, validated, idempotent transition (the battery proves it in the
   exhaustive matrix).
5. **`apply_segment_transition` temporal gate:** engaging execution mechanisms
   (RESERVED/ACTIVATED/MEASURED) past or before the plan validity fails
   closed; RELEASE remains legal at any valid instant (release is cleanup,
   never engagement).

## 5. Out-of-scope discipline (nothing else changed)

The M006 delta contains only: `executionplans/` (new, 5 files),
`composition/` (the 4 docstring-only harvest disclosures — no code, API, or
import change), `tools/executionplan_selftest.py` (new), and
`docs/M006-evidence.md` (this record). No control-plane surface, no `spec/`
file, no `.github/` file, no protocol schema, no `contracts/` or `offers/`
modification (both canonical domains are consumed by reference only), no W048
material (containment/sharing — stays accepted-not-restored, verified absent
in the battery), no pilot/ surface, and no historical record is touched. The
drift guard classifies the delta implementation-only; the provenance gate
verifies full coverage by R7-CORE-001 (`executionplans/`, `composition/`,
`tools/`, `docs/M006-evidence.md` are all declared M006 scope entries).

Note (honest limitation, the M005 precedent): the CI workflow does not yet run
`tools/executionplan_selftest.py` — wiring a new battery step into `.github/`
is a control-plane change outside this implementation PR's boundary. The
battery runs locally on the delivery head (36/36 ×3, exit-code-based) and is
the SOFTWARE evidence for this delivery; CI wiring is a Tech Lead/governance
action at acceptance time (the M010/M011/M012/M005 precedent: their battery
steps landed with the respective acceptance governance commits). Note also
that `tools/composition_selftest.py` is likewise not a CI step (its
accepted-state verification lives in this battery's case_29 re-run plus the
full local suite).

## 6. Evidence classes (honest disclosure)

- All M006 acceptance criteria: **SOFTWARE** class (deterministic offline
  battery, 36/36 PASS on the delivery head; every blocking battery and
  governance gate in the CI suite green on the delivery head — the one
  non-green step, the legacy `spec_check.py` compatibility audit, is
  `continue-on-error: true` in the CI workflow: it fails (rc=1) on the
  pre-delivery baseline as well, and its ARCH-08 verdict cannot see the R7
  program authorization by frozen construction (the workflow's own comment;
  the active-era successor gate `authorization_provenance.py` PASSES and
  verifies the delta's R7-CORE-001 coverage).
- M007 adapter mechanics are NOT implemented here: segments reference
  capability-oriented adapter operations **by name only** — never provider SDK
  types — and the plan conformance disclaimer states this on every document.
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M006 creates and closes
  none; EVID-002..EVID-008 remain open and untouched, and no evidence produced
  by this delivery is physical, production, or live-service evidence. No
  SOFTWARE evidence is converted into PHYSICAL PASS.

## 7. Delivery provenance

- Branch: `m006-execplan` from the baseline `db2f003` (the DEC-0105-accepted
  M005 state); append-only delivery history.
- Battery: `python3 tools/executionplan_selftest.py` → PASS (36/36) on the
  delivery head, run 3× consecutively.
- Full suite: every battery the CI workflow runs, in exact workflow order, on
  the delivery head with exit-code-based detection — see the PR body for the
  numbered results — plus the composition battery 55/55 (the harvested
  surface, run because the M006 delta touches `composition/` even though CI
  does not run it as a step).
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
- Accepted sibling batteries at this head: contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33,
  roamlink 56/56, comos 33/33, assurance 97/97, composition 55/55, payment
  44/44, eligibility 46/46 (the M009 DEC-0109 re-baselines), policy 103/103
  (the M004 DEC-0104 evolved count).
