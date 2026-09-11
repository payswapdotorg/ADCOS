# M015 — Execution Resilience Runtime — Evidence Record

**Work Item:** M015 · **Authorization:** R8-CORE-001 (DEC-0114, the bounded R8 program
authorization; M015 is the R8 charter's current child)
**Baseline:** `28b31500a928f2f75582bfb79039e315187d72b2` (the DEC-0109 R7-completion head,
per the authorization record; the branch rides the DEC-0114 R8-activation head
`b0145f1feaf42b6dffdf3772aa4380ce71029a67`)

This record persists the verified facts of the M015 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed or implied,
and EVID-002..EVID-008 remain open and untouched.

## 0. Continuation disclosure (the delivery history)

M015 was delivered in two sessions on the append-only branch `m015-resilience`
(no rebase, no force-push, no amending):

- **Milestone 1** (the prior worker session, commit `8949002`): the complete
  `resilience/` package (7 files, 3273 lines as delivered) — the session-runtime
  lifecycle model, the deterministic replayable journal, the runtime store with the
  replan-kernel composition core, the mobility handover engine, and the multipath
  failover orchestrator.
- **Milestone 2** (this session): the battery `tools/resilience_selftest.py`
  (NEW, 36 cases), this evidence record, and two disclosed defect fixes in
  `resilience/` required to make the battery honestly pass (§4).

## 1. Delivered surface

- **`resilience/` (NEW, milestone 1)** — the execution-runtime resilience domain
  of the R8 charter M015 scope, composing the accepted R7 authorities BY
  REFERENCE (import and compose; never reimplemented, weakened, forked, or
  bypassed):
  - `resilience/errors.py` — the frozen `resilience-*` typed reason vocabulary
    (15 fail-closed codes; `ResilienceError` with stable `code`/`detail`;
    consumed-domain errors — `ContractError`, `ReplanError`,
    `ExecutionPlanError` — wrapped at every consumed boundary with their
    deterministic text preserved; exception isolation throughout).
  - `resilience/model.py` — the M015-owned session-runtime lifecycle vocabulary
    (`PENDING/ACTIVE/RECONNECTING/DEGRADED/FAILED/TERMINATED`) with the frozen
    additive projection onto the M008-owned realization states
    (`RUNTIME_REALIZATION_MAP` — consumed BY REFERENCE from `replan/`, never
    redefined, never extended); the typed records (`RuntimeSession`,
    `RuntimeEvent` with the full kind-member discipline, `RuntimeReconnect` —
    the WORK-012 old+new evidence shape); the realization snapshot projection;
    the LOCK-106/LOCK-118 evidence-typing conventions consumed from the
    accepted `evidence/` vocabulary.
  - `resilience/journal.py` — the deterministic replayable runtime journal
    (construction-is-recovery fold; sequence gap/conflict divergence; the
    reconnect discipline MECHANICALLY enforced — route references change only
    through the explicit initiated+completed pair, old refs verbatim, new refs
    equal to the declared candidates, orphaned completions fail closed as
    `resilience-silent-replacement`).
  - `resilience/runtime.py` — the `RuntimeStore` (atomic lifecycle operations;
    the fold is the sole state writer) + `drive_replan_decision` — the
    replan-kernel composition core (the runtime drives the accepted M008
    decisions onto the journal: adopt -> the explicit reconnect pair; degraded
    -> the journaled evidence-visible degraded entry; failed/renegotiate -> the
    explicit terminal failure).
  - `resilience/handover.py` — the mobility handover engine (LOCK-108 through
    the consumed replan gates — typed weakened-constraint rejection; LOCK-111
    declared tie-breaking; `perform_handover` driving `replan.decide_replan`).
  - `resilience/failover.py` — the multipath failover orchestrator (the
    accepted `executionplans/` alternative segments read BY REFERENCE with the
    M006 `verify_plan_preserves_contract` gate consumed; declared recorded
    tie-breaking; `orchestrate_failover` driving `replan.decide_replan`).
  - `resilience/__init__.py` — the public surface (35 names).
- **`tools/resilience_selftest.py` (NEW, milestone 2)** — the M015 battery: 36
  deterministic, offline, seeded cases covering the charter's (a)-(j) matrix
  (§2).
- **`docs/M015-evidence.md`** — this record.
- **Disclosed defect fixes in `resilience/` (milestone 2)** — see §4: two
  minimal fixes, each its own append-only commit, each exposed by a battery
  case and disclosed here.

## 2. Verification matrix (the battery, SOFTWARE class per case)

`python3 tools/resilience_selftest.py` — all 36 cases green, run 3× consecutively
on the delivery head (byte-identical output; exit-code-based verification).

| Charter criterion | Battery verification | Class | Case(s) |
|---|---|---|---|
| (a) session-runtime create/transition/reconnect/terminate round-trips; every reconnect event records old AND new references | The full lifecycle round-trip (create -> activate -> reconnect pair -> degraded -> recovered -> failed reconnect -> reconnect -> terminate) folds, replays and rebuilds byte-identically; every initiating event carries old+candidates, every completing event carries old+new; the typed `RuntimeReconnect` evidence derives from the pairs | SOFTWARE | case_03, case_04 |
| (b) a silent-replacement attempt rejected (WORK-012 functionally enforced) | Orphaned completions (store-level and fold-level), initiations naming wrong old refs, completions naming undeclared new refs, route members on non-reconnect kinds, realization holders without named references, reconnect records missing one side — all fail closed `resilience-silent-replacement`; rejected operations leave the journal byte-identical | SOFTWARE | case_05 |
| Journal determinism/replayability (the fold) | Sequence gaps, attribution conflicts, kind/state divergence, illegal state edges, post-terminal events, non-created journal heads, identity tampering — all fail closed `resilience-journal-divergence`/`resilience-id-mismatch` | SOFTWARE | case_06 |
| (c) successful handover — the new realization satisfies the SAME hard constraints (typed record, provenance intact) | The strict handover candidate is adopted through the explicit reconnect pair onto the new references; the consumed `replan.verify_decision_preserves_contract` gate re-verifies the decision against the contract; the fingerprint is the contract's own; every appended event cites the decision id (LOCK-118) | SOFTWARE | case_07 |
| (d) LOCK-108 — every weakening handover/failover candidate rejected, a case per constraint kind | All 12 constraint kinds × DROP/RELAX/REINTERPRET: the raising gate rejects with `resilience-constraint-weakened` citing the kind; the verdict twin rejects citing the kind; the engine drive NEVER adopts a weakening candidate (the runtime lands the explicit FAILED state, no reconnect evidence); a wire-forged weakened plan is rejected by the consumed M006 gate with the typed weakened-constraint reason citing the kind | SOFTWARE | case_08..case_19 |
| (e) impossible realization -> explicit degraded/failed state + the explicit renegotiation trigger path | Soft trigger (`assurance-degraded`): the runtime lands the explicit DEGRADED state, the journaled `degraded-entered` event carries an accepted LOCK-106 evidence kind and the decision id as decision-kinded evidence; the contract records degraded through its OWN command vocabulary. Hard trigger (`segment-loss`/`adapter-failure`): the terminal FAILED state with the journaled reason; the contract records the violation. `constraint-unsatisfiable`: the typed notice -> the `superseded-contract` reference -> the successor contract through the M002 `CreateContract` surface | SOFTWARE | case_20, case_21, case_22 |
| (f) deterministic multipath failover selection with declared recorded tie-breaking | The full failover scenario run twice from scratch -> byte-identical decision records, journals, sessions and reconnect evidence; reversed segment input order -> the byte-identical plan (LOCK-111 input-order independence); declared rules recorded verbatim on the decision with the same selection; LOCK-115: a simple plan (no alternative segments) yields the typed `resilience-no-candidates` outcome; empty/temporal/reordered/repeated/non-sequence rules fail closed `resilience-tie-break-invalid` with the journal byte-identical | SOFTWARE | case_23, case_24, case_25 |
| (g) the replan-kernel composition (the gate exercised, not duplicated) | The runtime drives all four consumed decision kinds onto the journal (adopt -> the explicit pair; degraded -> the evidence-visible entry; failed/renegotiate -> the reasoned terminal failure); attribution gates (foreign-contract decision, divergent adopted references, PENDING surface, terminal runtime, foreign runtime contract) all fail closed typed | SOFTWARE | case_26 |
| (h) degraded-mode entry/exit journaled and evidence-visible | The entry/exit are journaled events with the accepted LOCK-106 evidence typing and decision-kinded references; the M008 DEGRADED projection verified; silent recoveries and untyped evidence fail closed | SOFTWARE | case_27 |
| (i) canonical-JSON round-trips + typed errors | Session/event/reconnect records round-trip byte-identically with stable content-derived ids; tampered dicts fail closed; temporal/secret/consumed-wrap/engine-isolation rejections all typed with deterministic text preserved (LOCK-119 secret fixtures assembled from fragments); no raw exception text reaches stored state | SOFTWARE | case_28, case_29 |
| (j) determinism under a re-run (and PYTHONHASHSEED variation) | The full lifecycle and failover scenarios are byte-identical across re-runs; construction-is-recovery verified; the session ordering deterministic; byte-identical decision ids, journal digests and decision records across PYTHONHASHSEED 0/1/42 subprocesses | SOFTWARE | case_30, case_31 |
| Frozen vocabularies; the M008 vocabulary consumed additively | The runtime/event/outcome vocabularies frozen; the realization projection maps only onto the consumed four-state set (no SUPERSEDED invention, nothing redefined); the trigger/candidate/tie-break/evidence/constraint-kind vocabularies consumed BY REFERENCE | SOFTWARE | case_01 |
| Vocabulary/input gates fail closed | Every gate (transitions, surfaces, states, kinds, store reads, triggers, candidates, evidence kinds, drive inputs) rejects with the specific typed code | SOFTWARE | case_02 |
| Lock conformance (aggregate) | LOCK-101/106/108/111/115/116/117/118/119 structural evidence: no constraint material on the runtime surface; opaque references only; the contract's own fingerprint rides every driving decision | SOFTWARE | case_32 |
| LOCK-119 clock/import discipline | AST audit: no wall-clock/randomness/network constructs anywhere in `resilience/`; imports confined to stdlib + `protocol` + the accepted authorities | SOFTWARE | case_33 |
| One-way imports (criterion 7) | No accepted authority (`contracts/`, `replan/`, `executionplans/`, `evidence/`, `assurance/`, `offers/`, `eligibility/`, `policy/`, `adapters/`, `usage/`, `commercial/`, `allocation/`, `payment/`, `sharenet/`, `roamlink/`, `comos/`, `developerapi/`, `federation/`, `identity/`, `upgrade/`, `scale/`, `client/`) imports `resilience/`; the legacy reservoir is un-imported source material only | SOFTWARE | case_34 |
| PR delta shape | Every delta file covered by the ACTIVE R8-CORE-001 scope (`authorization_provenance.covers`); no `spec/` or `.github/` touch | SOFTWARE | case_35 |
| Evidence-doc honesty | SOFTWARE class, by-reference composition, harvest, lock mapping and the open physical obligations disclosed; no affirmative physical claims | SOFTWARE | case_36 |

**Battery result: PASS (36/36 cases; the 12 per-kind LOCK-108 cases are
individually numbered case_08..case_19 within the set), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `resilience/` consumes the accepted
  `contracts/` public surface by reference only (frozen public types imported;
  `contracts/` untouched — verified in the battery's one-way-import and
  PR-delta cases); the runtime store never writes contract state — adopted
  realizations ride back toward the contract only through the contract's own
  frozen command vocabulary (the M008 `replan.bridge`, consumed: the degraded
  and violated `RecordAssurance` recordings and the `superseded-contract`
  successor path are exercised in case_20/21/22).
- **LOCK-106 (evidence typing):** the degraded-mode evidence kinds are drawn
  from the accepted `evidence/` four-type vocabulary (consumed BY REFERENCE;
  import-time drift guard in `resilience/model.py`); the degraded entry's
  evidence references are `decision`-kinded opaque references; untyped or
  wrong-kinded evidence fails closed (case_27).
- **LOCK-108 (no silent contract weakening — the core discipline):** enforced
  at four points — (1) structural: the runtime session and its events carry NO
  constraint material at all (field-set-audited in case_32); (2) the consumed
  M008 per-candidate gates (`replan.validate_constraints_preserved` /
  `replan.candidate_verdict` wrapped on this surface) fail closed on ANY set
  difference — drop, relaxation, re-interpretation — citing the specific
  constraint kinds (12 per-kind battery cases × 3 weakening modes); (3) the
  consumed M006 plan gate (`executionplans.verify_plan_preserves_contract`)
  rejects a weakened plan BEFORE any alternative is read, surfacing as this
  surface's own typed weakened-constraint rejection (per-kind, case_08..19);
  (4) the consumed cross-authority gate `replan.verify_decision_preserves_
  contract` re-verifies every finished driving decision against the contract
  (case_07/case_32). Impossible realizations enter the EXPLICIT DEGRADED/FAILED
  runtime states or trigger the EXPLICIT renegotiation path (the typed notice +
  the `superseded-contract` successor) — never a silent downgrade.
- **LOCK-111 (optimizer replaceability):** the resilience engines are
  deterministic strategies over DATA inputs; tie-breaking rules are validated
  against the CONSUMED M008 key vocabulary (content keys only, never temporal),
  injected, and recorded verbatim on the decision; same inputs -> byte-identical
  decision records (verified in-process twice, across full scenario re-runs, and
  across PYTHONHASHSEED subprocesses).
- **LOCK-115/LOCK-116:** a simple deployment (a plan with no alternative-role
  segments) yields the typed `resilience-no-candidates` outcome (never an
  invented alternative, never a silent no-op); the complex failover shape
  (primary + alternatives under ONE contract) is exercised end-to-end.
- **LOCK-117 (authority uniqueness):** the runtime session, its events, the
  reconnect evidence and the realization snapshot ride the contract as opaque
  references (`sha256:` content ids, `execution-artifact` data); the runtime
  identity is content-derived over the STATE-INDEPENDENT creation core (the
  artifact evolves while the contract stays stable); no second contract
  authority exists anywhere on the resilience surface.
- **LOCK-118 (provenance):** every record (session, event, reconnect) carries
  typed provenance; the replan-drive events cite the applied decision id; the
  degraded entry cites the decision as decision-kinded evidence; the
  renegotiation successor carries the `superseded-contract` reference with
  provenance.
- **LOCK-119 (secrets):** secret-shaped material is rejected at the boundary
  (`resilience-secret-rejected` — battery fixtures assembled from runtime
  fragments); no wall clock, no randomness, no UUIDs, no network anywhere in
  `resilience/` (AST-audited); injected instants only; content-derived ids over
  canonical JSON.

## 4. Defect fixes in `resilience/` (disclosed; milestone 2)

Two defects in the delivered milestone-1 package were exposed by battery cases
and fixed as their own append-only commits (the charter's defect-fix path;
never a weakened case):

1. **Terminal typed-reason uniformity (`resilience/runtime.py`).** The
   delivered store surfaced `resilience-session-terminal` for terminal
   sessions on `enter_degraded`/`fail`/`terminate` (through
   `check_runtime_transition`) but `resilience-transition-illegal` on
   `activate`/`initiate_reconnect`/`complete_reconnect`/`fail_reconnect`/
   `recover_degraded` (the operation-specific state gates masked
   terminality).  The vocabulary's own semantics ("FAILED/TERMINATED
   sessions never transition") require the specific terminal reason
   uniformly.  Fix: a `_require_not_terminal` guard at the top of the five
   masking lifecycle operations (exposed by case_03/case_21's terminal
   probes).
2. **The failover plan-gate typed reason (`resilience/failover.py`).** The
   delivered wrap mapped EVERY consumed M006 plan-gate failure onto
   `resilience-constraint-mismatch`, including the weakened-constraint
   rejection (`plan-constraint-weakened`) — while the vocabulary's own
   docstring reserves `resilience-constraint-weakened` for exactly "a
   handover/failover candidate drops, relaxes or re-interprets a hard
   contract constraint" and the charter's acceptance criterion requires the
   TYPED weakened-constraint rejection across the failover transition.
   Fix: the wrap discriminates the consumed gate's
   `plan-constraint-weakened` code onto this surface's own
   `resilience-constraint-weakened` (deterministic detail preserved); every
   other plan-gate failure keeps the constraint-mismatch wrap (exposed by
   the per-kind forged-plan probes, case_08..case_19).

## 5. Judgment calls (disclosed)

1. **The battery drives the consumed kernel, never a duplicate.** The
   composition cases (case_26) build the M008 decision through the ACCEPTED
   `replan.decide_replan` engine (with the resilience realization-snapshot
   projection as the snapshot input) and apply it through
   `resilience.runtime.drive_replan_decision` — the same composition path
   `perform_handover`/`orchestrate_failover` use internally.  No decision
   semantics are re-implemented in the battery or the package (the R8 charter
   consumption rule).
2. **The failover-side weakening probe uses a wire-forged plan.** The
   alternatives of an honest plan carry the contract's constraint set
   verbatim (the M006 translation takes it from the contract — a weakening
   failover candidate is structurally unreachable through the honest
   surface), so the per-kind LOCK-108 failover demonstration forges a plan
   whose constraint set is weakened but whose ids/fingerprint are re-derived
   over the forged content (exactly what the accepted derivation computes —
   ids are tamper-EVIDENT, not tamper-proof secrets; the M008 battery's
   wire-forged-fingerprint precedent).  The consumed M006 gate rejects it
   with the typed kind-citing reason BEFORE any alternative is read.
3. **The handover surface carries the candidate-level weakening matrix.**
   The 12-kind × DROP/RELAX/REINTERPRET matrix runs on the handover gate
   (`validate_handover_preserves_contract` + `handover_verdict` + the engine
   drive), matching the M008 battery's per-kind convention; the failover
   side is probed per-kind through the forged-plan gate (DROP mode).  Both
   surfaces' rejections cite the kind.
4. **The degraded drive's evidence kind is `observation`.** The M008 kernel's
   degraded decision is a closed-loop evaluation outcome; the drive maps it
   onto the accepted LOCK-106 `observation` evidence kind with the decision
   id as the decision-kinded evidence reference (the M002 record-assurance
   discipline consumed) — recorded, visible, never silent.
5. **Terminal sessions keep their last-named realization references** as
   historical evidence (the delivered milestone-1 semantics, verified in
   case_03); only PENDING sessions carry none.

## 6. By-reference composition and the legacy reservoir (disclosed)

- **By-reference composition:** `resilience/` imports only the accepted
  authorities — `contracts/` (the canonical record types, consumed from the
  frozen public surface), `replan/` (the realization-state vocabulary, the
  decision engine, the LOCK-108 gates, the bridge), `executionplans/` (the
  plan translation, the alternative segments, the M006 LOCK-108 gate), and
  `evidence/` (the LOCK-106 type vocabulary) — plus `protocol/` and the
  stdlib.  AST-audited (case_33); the import direction is one-way (case_34:
  no accepted authority imports `resilience/`).  Nothing is reimplemented,
  weakened, forked, or bypassed; the M008 realization vocabulary is projected
  onto additively and never redefined (case_01).
- **The legacy reservoir is source material only.** The WORK-012
  explicit-reconnect discipline, the WORK-035/WORK-014 handover semantics,
  and the WORK-013 multipath failover model were studied from the legacy
  `sessions/`, `mobility/`, `multipath/` packages (harvest material per the
  frozen migration classification matrix) and RE-EXPRESSED on the 1.1
  authority inside `resilience/`.  The legacy packages are NOT imported
  (AST-audited, case_34), NOT modified (their M008 docstring disclosures
  stay byte-identical — the delta contains no legacy-package file), and
  remain their own authorities for their existing consumers.

## 7. Out-of-scope discipline (nothing else changed)

The M015 delta (from the DEC-0114 baseline range) contains only: `resilience/`
(NEW in milestone 1 + the two disclosed defect fixes in milestone 2),
`tools/resilience_selftest.py` (NEW), and `docs/M015-evidence.md` (this
record).  No control-plane surface, no `spec/` file, no `.github/` file, no
protocol schema, and no accepted-domain modification (`contracts/`, `replan/`,
`executionplans/`, `evidence/`, or any other canonical domain — all consumed
by reference only; verified in the battery's one-way-import and PR-delta
cases).  The drift guard classifies the delta implementation-only; the
provenance gate verifies full coverage by R8-CORE-001 (`resilience/`,
`tools/`, `docs/M015-evidence.md` are declared M015 scope entries).

The CI workflow's M015 step (`tools/resilience_selftest.py`, the existence-
guard pattern) was wired by the DEC-0114 governance commit BEFORE this
delivery (it is not part of this delta); it activates on this delivery and
skips visibly until the merge.

## 8. Evidence classes (honest disclosure)

- All M015 acceptance criteria: **SOFTWARE** class (deterministic offline
  battery, 36/36 PASS on the delivery head; every blocking battery and
  governance gate in the CI suite green on the delivery head).
- No pending child is claimed delivered: M016-M019 surfaces do not exist yet
  and are not faked; the CI existence-guard steps for their batteries skip
  visibly (disclosed, the DEC-0101 wiring convention).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M015 creates and closes
  none; EVID-002..EVID-008 remain open and untouched, and no evidence produced
  by this delivery is physical, production, or live-service evidence.  No
  SOFTWARE evidence is converted into PHYSICAL PASS.

## 9. Delivery provenance

- Branch: `m015-resilience`, append-only from the milestone-1 commit
  `8949002` (which rides the DEC-0114 R8-activation head `b0145f1`); no
  rebase, no force-push, no amending; commit-as-you-go delivery history.
- Milestone-1 verification (this session, before any milestone-2 work): every
  file under `resilience/` read end to end; the import proof
  `python3 -c "import resilience; print(len(resilience.__all__))"` -> `35`
  (the declared public surface); the branch-state verification (HEAD
  `8949002`, exactly one commit over `b0145f1`, the roadmap
  `R8_RESILIENCE_MOBILITY_AND_SCALE_ACTIVE` marker present).
- Battery: `python3 tools/resilience_selftest.py` -> PASS (36/36) on the
  delivery head, run 3× consecutively, byte-identical.
- Full suite: every battery the CI workflow runs, in exact workflow order, on
  the delivery head with exit-code-based detection — see the PR body for the
  numbered results.
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
- Accepted sibling batteries at this head: contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33,
  roamlink 56/56, comos 33/33, assurance 97/97, executionplan 36/36,
  adapter 70/70, replan 38/38, payment 44/44, eligibility 46/46,
  policy 103/103, client 24/24, scale 45/45, conformance 63/63 (verified
  by direct execution on the delivery head, exit-code-based).
