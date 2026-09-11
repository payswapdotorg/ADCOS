# M008 — Replan and Failover — Evidence Record

**Work Item:** M008 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7 program
authorization; M008 is the charter's current child)
**Baseline:** `4d501dad1ea4424dc91ede3c5f3e26b527b29b83` (the DEC-0107-accepted M007
state — the live main head; the current-child pointer advances M007 → M008)

This record persists the verified facts of the M008 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — simulation/deterministic-battery evidence only; no PHYSICAL PASS is claimed or
implied, and EVID-002..EVID-008 remain open and untouched.

## 1. Delivered surface

- **`replan/` (NEW)** — the closed-loop replan domain (frozen 1.1 §9:
  Replan / Failover / Compensation entry point of the closed loop),
  composed of:
  - `replan/errors.py` — the frozen `replan-*` typed reason vocabulary
    (17 fail-closed codes; `ReplanError` with stable `code`/`detail`;
    consumed-domain validation errors are wrapped — exception
    isolation, no raw exception text into stored state; the consumed
    domain's LOCK-119 secret rejection surfaces as this surface's own
    `replan-secret-rejected`).
  - `replan/model.py` — the typed replan records and the frozen
    vocabularies: the trigger kinds (`adapter-failure`, `segment-loss`,
    `assurance-degraded`, `assurance-violated`, `route-expiry`,
    `constraint-unsatisfiable`), the **M008-owned realization-state
    vocabulary** (`REALIZING / DEGRADED / FAILED / SUPERSEDED` — the
    frozen §9 explicit degraded/failed realization states the M006
    domain deliberately did not invent; `FAILED`/`SUPERSEDED`
    terminal; the recovery edge `DEGRADED → REALIZING` and the
    make-before-break `REALIZING → SUPERSEDED`), the realization
    surfaces (`execution-plan`, `session`, `mobility-handover`,
    `multipath-plan`), the candidate kinds (`execution-plan`,
    `mobility-handover`, `multipath-path`, `provider-alternative`),
    the decision kinds (`adopt-alternative`, `degraded`, `failed`,
    `renegotiate`), and the tie-break key vocabulary
    (`candidate-kind`/`candidate-id` — content keys only, never
    temporal). `ReplanTrigger` (what failed — typed, evidence-carrying,
    injected-instant); `RealizationSnapshot` (the contract-attributable
    execution-state view); `ReplanCandidate` (one alternative
    realization as DATA — the claimed constraint set is optimizer
    input, re-validated by the engine; there is NO
    constraint-mutation power anywhere on the surface);
    `CandidateVerdict` (the typed per-candidate LOCK-108 verdict);
    `ReplanDecision` (the closed-loop record: trigger, every candidate
    considered with its verdict, the constraints RE-VALIDATED (the
    contract's own set carried verbatim with the contract's own
    LOCK-108 fingerprint), the decision, the declared tie-break rule,
    the adopted candidate, provenance referencing the contract and the
    realization being replaced, and the explicit renegotiation notice);
    `RenegotiationNotice` (the explicit renegotiation trigger citing
    the contract to supersede); `ReconnectRecord` (the harvested
    WORK-012 reconnect discipline as typed evidence — old AND new
    route references enforced fail-closed
    `replan-silent-replacement`). All records: content-derived
    namespaced ids over WORK-003 canonical JSON, tamper-evident
    (re-derived at construction AND deserialization), canonical-JSON
    round-trips. The pure kernels `check_realization_transition` /
    `apply_realization_transition` (identity- and material-preserving,
    fail-closed, terminal never exits).
  - `replan/validation.py` — the LOCK-108 enforcement core:
    `validate_constraints_preserved` (the per-candidate gate — verbatim
    constraint-set equality by canonical content BOTH directions:
    dropped, relaxed, re-interpreted or invented constraints fail
    `replan-constraint-weakened` citing the specific kinds; then the
    LOCK-108 fingerprint agreement over the claimed set —
    `replan-constraint-mismatch` for reordered/tampered material);
    `candidate_verdict` (the non-raising twin the engine records:
    a candidate that weakens/drops ANY hard constraint is REJECTED
    with the typed reason — never silently swallowed, never an
    exception across the engine boundary); `verify_decision_
    preserves_contract` (the pure cross-authority gate over the
    finished record — the M006 `verify_plan_preserves_contract`
    discipline applied to replan: set equality, fingerprint,
    attribution, adopted-candidate consistency, and the
    no-silent-downgrade shape).
  - `replan/engine.py` — `decide_replan`, the deterministic engine
    (trigger gate → realization gate → candidate evaluation →
    decision): the replannable contract states
    (`CONTRACT_ACTIVE/EXECUTION_ACTIVE/DELIVERY/ASSURED/DEGRADED` —
    INTENT/OFFER_SELECTED carry no engaged realization; terminal and
    post-execution states never replan), trigger attribution and
    contract-validity temporal gates, non-terminal realization gate,
    non-empty candidate gate, duplicate-candidate gate, and the
    decision selection: the first constraint-preserving candidate in
    the declared (injected, recorded) tie-break order is adopted; with
    NO acceptable candidate the outcome is EXPLICIT per the trigger
    class — `degraded` for a soft (assurance-degraded) trigger, `
    renegotiate` for the impossible-realization class
    (constraint-unsatisfiable), `failed` for every other hard trigger;
    the failed and renegotiate decisions carry the typed renegotiation
    notice (never a silent downgrade). LOCK-111: same inputs → the
    byte-identical decision, same reasons; input order never matters;
    the declared rule is recorded on the decision.
  - `replan/execution_state.py` — **the disclosed harvest seam**: the
    WORK-era execution packages harvested onto the 1.1 authority BY
    REFERENCE (one-way). `SESSION_STATE_MAP` (the frozen
    WORK-012-session → M008-realization projection: ESTABLISHED/
    RECONNECTING/SUSPENDED → REALIZING, DEGRADED → DEGRADED, FAILED →
    FAILED; deliberately terminated and pre-establishment sessions
    fail closed with typed reasons — never a replan surface);
    `session_realization_snapshot` (the session lifecycle discipline
    as THE execution-state surface replan operates over);
    `reconnect_history` (the explicit-reconnect discipline — every
    `reconnected` event must carry BOTH the old AND the new route
    references, else `replan-silent-replacement`: the WORK-012
    authority rules PRESERVED and mechanically enforced);
    `handover_surface` / `multipath_surface` (the WORK-014/WORK-013
    alternative models the engine selects among, read by reference —
    the view never prepares/commits/cancels a handover and never
    adds/removes/re-statuses a path).
  - `replan/alternatives.py` — the candidate constructors consuming
    the accepted sibling domains BY REFERENCE: `plan_candidate` (a
    new M006 `ExecutionPlan` translated from the SAME contract, with
    attribution checked and the plan's opaque
    `execution-artifact` reference), `route_candidate` (a WORK-011
    accepted route decision as a mobility-handover / multipath-path
    alternative), `capability_candidate` (an M007 `OfferView` as a
    provider-alternative — provider-neutral DATA, LOCK-110).
  - `replan/bridge.py` — the explicit, sole recording path back into
    the accepted `contracts/` domain through its own frozen command
    vocabulary (the M005 bridge pattern): adopt-alternative →
    `BindExecutionArtifact` per adopted artifact (LOCK-117: opaque
    data, binding changes no identity/state/constraint); degraded →
    `RecordAssurance("degraded")`; failed/renegotiate →
    `RecordAssurance("violated")`; `renegotiation_reference` → the
    successor contract's `superseded-contract` opaque reference (the
    explicit renegotiation trigger path; the successor creation
    happens through the M002 `CreateContract` surface — the replan
    domain never creates contracts, LOCK-101). Bridge-applicability
    pre-checked against the contract's own frozen transition table
    (`replan-bridge-inapplicable`, mirroring the M005
    `BRIDGE_NOT_APPLICABLE` honesty); import-time vocabulary-drift
    guard.
  - `replan/__init__.py` — the public surface (40 names).
- **`sessions/`, `mobility/`, `multipath/` (HARVEST — disclosed, DOCSTRING-ONLY)** —
  the R7 charter M008 scope entry `(harvest)`: the WORK-012 session
  lifecycle discipline (explicit reconnect events recording old AND
  new route, never silent replacement) becomes the execution-state
  surface replan operates over; mobility/multipath provide the
  handover/multi-path alternative models the engine selects among.
  The functional harvest lives in `replan/execution_state.py`
  (consumes the three packages' frozen public APIs by reference,
  one-way); the packages themselves carry **docstring-only** harvest
  disclosures (module docstrings of `sessions/__init__.py`,
  `mobility/__init__.py`, `multipath/__init__.py`): **no behavior
  change, no public-API change, no import change** — the frozen
  WORK-012/013/014 contracts are preserved verbatim, the `__all__`
  export tables are byte-identical to origin/main (verified in the
  battery, case_32), and the three packages' own batteries re-run
  green at their accepted counts on the M008 delivery head
  (session 55/55, mobility 43/43, multipath 45/45 — battery
  case_33). The one-way harvest direction is structural:
  the three packages import no `replan/` code (AST-audited,
  case_32). This is the minimal consistent refactor that preserves
  every consumer surface (the M006 composition-harvest precedent,
  DEC-0106 judgment call #1; the M005 telemetry precedent: the seam
  lives in the new domain).
- **`tools/replan_selftest.py` (NEW)** — the M008 battery: **38/38 PASS**
  (plus the 12 per-kind LOCK-108 cases individually numbered
  case_06..case_17 within the set — see §2), deterministic, offline,
  seeded.
- **`docs/M008-evidence.md`** — this record.

## 2. Deterministic verification matrix

All runs offline; instants injected (T0-style constants); no wall clock, no
randomness, no UUIDs, no network; no real sockets; no secrets stored
(LOCK-119); PYTHONHASHSEED-safe (verified across processes and seeds 0/1/42).
Exit-code-based verification (a traceback or lowercase "failed" IS a failure).

| Verification | Result | Evidence |
|---|---|---|
| Frozen vocabularies (trigger kinds; realization states/transitions/terminals/surfaces; candidate kinds; decision kinds; soft/renegotiation trigger classes; tie-break keys; replannable contract states; the frozen session-state mapping) | PASS | case_01 |
| Vocabulary violations fail closed `replan-vocabulary` (trigger/candidate/snapshot/verdict kinds) | PASS | case_02 |
| (a) **Successful failover**: real contract via the accepted `contracts/` API + a real NEW plan via the accepted `executionplans/` API translated from the SAME contract → `adopt-alternative`; typed record, provenance and `replaces` intact; the adopted plan binds via the contract's own `BindExecutionArtifact` with identity/state/constraints unchanged (LOCK-117); the M006 `verify_plan_preserves_contract` gate passes on the plan | PASS | case_03 |
| Contract-state gate matrix: all 13 lifecycle states probed — exactly CONTRACT_ACTIVE/EXECUTION_ACTIVE/DELIVERY/ASSURED/DEGRADED replan; INTENT/OFFER_SELECTED/USAGE_FINAL/SETTLEMENT_PENDING/SETTLED fail closed `replan-contract-not-replannable`; terminal states fail closed `replan-contract-terminal` | PASS | case_04 |
| Engine inputs fail closed (non-contract/non-trigger/non-snapshot, empty candidates `replan-no-candidates`, non-candidate entries, trigger/snapshot attribution, trigger instant outside validity, terminal realizations, duplicate candidate ids, invalid tie-break rules, provenance type) — 13 typed gates | PASS | case_05 |
| (b) **LOCK-108 per constraint kind — all 12 kinds** (latency-bound, throughput-floor, availability-floor, loss-bound, jitter-bound, isolation, jurisdiction, security-level, provider-trust, evidence-obligation, geography, priority): the weakening candidate is REJECTED with `replan-constraint-weakened` citing the kind (DROP probed in the numbered case; RELAX and REINTERPRET probed inside each); a strict alternative alongside is adopted instead; the pure gate raises with the kind cited | PASS | case_06..case_17 (one case per kind) |
| LOCK-108 structural no-override surface: the decision's constraint set IS the contract's own; a relaxed serialized record fails `replan-constraint-mismatch`; a forged fingerprint fails; the verify gate rejects foreign contracts; an adopt marker on a non-adopt record is rejected; a tie-break change invalidates the record id | PASS | case_16 (structural) |
| (c) **Impossible realization, soft trigger** → the EXPLICIT `DEGRADED` realization state; bridge → the contract's own `RecordAssurance("degraded")` → the contract's own explicit DEGRADED state; constraints intact — never a silent downgrade | PASS | case_17 (c) |
| (c) **Impossible realization, hard trigger** → the EXPLICIT `FAILED` realization state with the typed renegotiation notice; bridge → `RecordAssurance("violated")` → contract FAILED with `constraint-violated` | PASS | case_18 (c) |
| (c) **Explicit renegotiation trigger path**: `constraint-unsatisfiable` → decision `renegotiate` + notice; `renegotiation_reference` → the `superseded-contract` reference; the SUCCESSOR contract created through the real M002 `CreateContract` surface carrying the reference; the superseded contract FAILED explicitly; distinct contract identity (supersession is a new contract, never a mutation) | PASS | case_19 (c) |
| (d) **Determinism**: same inputs → byte-identical decisions (twice); input order never changes the decision; different declared rules produce different records with the same verdict set; different triggers produce different ids (sensitivity) | PASS | case_20 |
| (d) Cross-process determinism: byte-identical decision ids and canonical records across PYTHONHASHSEED 0/1/42 subprocesses | PASS | case_21 |
| (e) **Session reconnect discipline**: the explicit reconnect event records old AND new route references (typed `ReconnectRecord`, round-trip stable); the session identity survives; a one-sided reconnect record fails closed `replan-silent-replacement` | PASS | case_22 |
| (e) The execution-state surface: the frozen SESSION_STATE_MAP projection (ESTABLISHED/RECONNECTING/SUSPENDED → REALIZING; DEGRADED → DEGRADED; FAILED → FAILED); the engine rejects FAILED realizations; pre-establishment (`replan-realization-not-established`) and deliberately terminated (`replan-realization-terminal`) sessions fail closed; unknown session and non-store inputs fail closed | PASS | case_23 |
| (f) **Mobility handover fixture**: a real WORK-014 `MobilityStore` — prepare → the PREPARED transaction read through `handover_surface` → a mobility-handover candidate adopted by the engine → the handover COMMITTED through the real WORK-012/014 contracts (session identity preserved, reconnect evidence with old+new recorded, the consumed alternative leaves the open surface) | PASS | case_24 |
| (f) **Multipath fixture**: a real WORK-013 `MultipathStore` — add_path → the plan's constituents read through `multipath_surface` → a multipath-path candidate adopted; ACTIVE/DEGRADED constituents available, FAILED never (terminal) | PASS | case_25 |
| (g) **Assurance-state-triggered replan**: REAL M005 `evaluate_contract` evaluations — a degradable obligation breach evaluates `degraded` and a hard breach evaluates `violated`; both construct replan triggers (the evaluation id riding the `decision`-kinded evidence reference) and drive the engine: without alternatives → degraded/failed (explicit), with an acceptable alternative → adopt | PASS | case_26 |
| (h) Canonical round-trips: trigger/snapshot/candidate/verdict/decision/notice `to_dict → from_dict → to_dict` byte-stable; stdlib-JSON round-trips; canonical bytes stable; tampered ids fail `replan-id-mismatch` | PASS | case_27 |
| (h) Typed errors + exception isolation: secret-shaped material at the deserialization boundary fails `replan-secret-rejected` (the consumed guard surfaced typed); malformed instants fail `replan-temporal-invalid`; artifact-less candidates fail `replan-candidate-invalid`; consumed `ContractError`s are wrapped; bridge inapplicability (`replan-bridge-inapplicable` for a degraded decision with no DEGRADED edge); renegotiation reference without a notice fails | PASS | case_28 |
| The realization-state kernel: all 16 (state, target) pairs probed — exactly the 6 legal edges pass; terminals never exit; attribution/routes/artifacts preserved across transitions; the recovery and make-before-break edges exercised | PASS | case_29 |
| Alternative constructors BY REFERENCE: `plan_candidate` (same-contract plan, foreign plan fails `replan-id-mismatch`), `capability_candidate` (real M007 `OfferView` typed; non-view fails), `route_candidate` (kind discipline; a weakening claim rejected by the engine) | PASS | case_30 |
| Clock + import discipline (AST): no wall-clock/randomness/UUID/network constructs in `replan/`; imports only stdlib + `protocol` + `contracts` + `executionplans` + `routing` + `adapters` + `sessions` + `mobility` + `multipath` (all by reference; no topology, no offers resolution inside the domain — LOCK-105) | PASS | case_31 |
| One-way harvest: sessions/mobility/multipath never import `replan/`; their `__all__` export tables are byte-identical to origin/main (docstring-only disclosure) | PASS | case_32 |
| The harvested surfaces' own batteries re-run green at the accepted counts on the M008 delivery head: session 55/55, mobility 43/43, multipath 45/45 | PASS | case_33 |
| Lock conformance mapping: LOCK-101/105/108/111/115/116/117/118/119 evidenced (simple and complex failover under one contract) | PASS | case_34 |
| PR delta shape: every delta file covered by the ACTIVE R7-CORE-001 scope (`authorization_provenance.covers`); no `spec/` or `.github/` touch | PASS | case_35 |
| Evidence doc honesty: SOFTWARE class, the lock mapping, the harvest, and the open physical obligations disclosed; no affirmative physical claims | PASS | case_36 |

**Battery result: PASS (38/38 cases; the 12 per-kind LOCK-108 cases are
individually numbered case_06..case_17 within the set), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `replan/` consumes the accepted
  `contracts/` public surface by reference only (imports the frozen public
  types; `contracts/` is untouched — verified in the battery); the engine
  never writes contract state; every effect enters through the contract's
  own command vocabulary (`replan.bridge`); the renegotiation successor is
  created through the M002 `CreateContract` surface, never by the replan
  domain; there is no second contract model (the decision's constraint set
  IS the contract's own set, and its fingerprint is the contract's own
  `hard_constraint_fingerprint()` output).
- **LOCK-105 (no global topology):** the replan domain imports no topology
  surface — alternatives arrive as typed references and views (AST-audited).
- **LOCK-108 (no silent contract weakening — the core discipline):**
  enforced at five points — (1) structural: no constraint input or
  mutation path exists on any replan surface (the candidate's claimed set
  is DATA, re-validated); (2) the per-candidate gate
  `validate_constraints_preserved`/`candidate_verdict` fails closed on ANY
  set difference — drop, relaxation, re-interpretation, or invention —
  citing the specific constraint kinds (12 per-kind battery cases); (3)
  decision construction/deserialization verifies the carried constraint set
  against the carried fingerprint and the derived identity (tamper
  evidence); (4) `verify_decision_preserves_contract` re-verifies the
  finished record against the contract (set equality + the contract's own
  fingerprint + attribution + adopted-candidate consistency); (5) the
  adopted M006 plan must itself pass the M006 LOCK-108 gate (consumed
  discipline, re-verified in case_03). Impossible realizations enter the
  EXPLICIT DEGRADED/FAILED realization states or trigger EXPLICIT
  renegotiation (the typed notice + the `superseded-contract` successor
  path) — never a silent downgrade.
- **LOCK-111 (optimizer replaceability):** the engine is a deterministic
  strategy over DATA inputs; tie-breaking rules are injected, DECLARED and
  recorded on the decision (content-key vocabulary only — never
  wall-clock); input order never affects the decision; same inputs →
  byte-identical records (verified twice in-process and across
  PYTHONHASHSEED subprocesses).
- **LOCK-115/LOCK-116:** one contract → one adopted alternative (simple)
  and the complex failover shapes (multiple providers/segments/access
  mechanisms/failover alternatives under ONE contract; a DEGRADED contract
  replans) are both exercised.
- **LOCK-117 (authority uniqueness):** the decision, its candidates, the
  adopted plan, the session paths and the offer views ride as opaque
  `execution-artifact` data; binding via the contract's own
  `BindExecutionArtifact` changes no identity/state/constraint; the
  sessions/mobility/multipath stores stay their own authorities (the
  harvest seam only READS); no second authority is created on either side.
- **LOCK-118 (provenance):** the trigger, snapshot, candidate and decision
  records all carry provenance (issuer + decision refs); the decision's
  `replaces` material references the realization being replaced (snapshot
  id, session ref, trigger realization ref); the bridge's decision
  reference and the renegotiation reference carry provenance.
- **LOCK-119 (secrets):** secret-shaped material is rejected at the
  deserialization boundary through the consumed contracts-domain guards,
  surfaced as the typed `replan-secret-rejected` reason; no wall clock, no
  randomness, no UUIDs, no network anywhere in the domain (AST-audited).

## 4. Judgment calls (disclosed)

1. **The sessions/mobility/multipath harvest is disclosure-only on the
   harvested side.** The charter scope `(harvest)` is discharged by
   harvesting the three WORK-era packages onto the 1.1 authority in
   `replan/execution_state.py` (the seam — the M006 composition-harvest
   and M005 telemetry precedents: the seam lives in the new domain) plus
   the docstring-only disclosure in the three packages' module
   docstrings. A deeper in-place refactor (e.g., routing the session
   store's reconnect through the replan engine, or adding contract
   awareness inside `sessions/`) is structurally impossible without
   breaking the frozen WORK-012/013/014 contracts: the three packages'
   batteries (outside this PR's boundary) pin their behavior, ~50
   sibling batteries import their public APIs directly (including
   `import sessions.store as …`, `from mobility.validation import …`,
   and string-embedded import proofs), and the charter's own scope
   discipline says to preserve the public API surface the batteries
   consume. The harvest is therefore one-way and disclosed at both
   ends, with the WORK-012 explicit-reconnect discipline PRESERVED and
   mechanically enforced on the replan side
   (`replan-silent-replacement`).
2. **The replannable-contract-state set** is `CONTRACT_ACTIVE/
   EXECUTION_ACTIVE/DELIVERY/ASSURED/DEGRADED` (the active-realization
   states). CONTRACT_ACTIVE is included (the M006 plannable shape: a
   plan may exist pre-execution-recording and be replanned);
   OFFER_SELECTED is excluded (no accepted realization exists to
   replace); DELIVERY/ASSURED are included (the M005 assurance-recordable
   states — the closed loop's evaluation surface); DEGRADED is included
   (the LOCK-116 failover-for-a-degraded-realization shape, mirroring
   M006's plannable set). The bridge pre-checks the contract's own
   frozen transition table and fails closed `replan-bridge-inapplicable`
   where the recording edge does not exist (e.g., a degraded decision on
   a CONTRACT_ACTIVE contract — the M005 `BRIDGE_NOT_APPLICABLE`
   honesty, exercised in case_28).
3. **The no-acceptable-candidate decision mapping is trigger-class-based
   and deterministic:** `assurance-degraded` (soft) → the EXPLICIT
   degraded realization (the closed loop keeps observing — frozen §9
   degraded is an evaluated, recorded state); `constraint-unsatisfiable`
   → `renegotiate` (the impossible-realization class: the realization
   fails AND an explicit renegotiation is triggered); every other hard
   trigger (`adapter-failure`, `segment-loss`, `assurance-violated`,
   `route-expiry`) → `failed`, carrying the explicit renegotiation
   notice (a failed realization is exactly when renegotiation becomes
   relevant — both explicit paths are demonstrated in case_17/18/19).
   This mapping is frozen vocabulary, not a policy input: the decision
   is a pure function of (contract, trigger, snapshot, candidates,
   tie-break, provenance).
4. **The decision record is terminal evidence.** `ReplanDecision` never
   re-decides in place; a later trigger produces a NEW decision record
   (the M002 supersession discipline applied to replan decisions).
5. **`MEASURED → MEASURED`-style idempotence is NOT invented here**: the
   realization vocabulary has no self-loop; recovery is the explicit
   `DEGRADED → REALIZING` edge through an adopted alternative (the
   closed-loop shape), and a terminal FAILED/SUPERSEDED realization
   never transitions (case_29's exhaustive matrix).
6. **The harvested surfaces' alternative semantics are frozen as
   declared:** a PREPARED (not COMMITTED) mobility transaction is an
   open handover alternative (a committed handover's effect is read
   through the session surface instead); multipath ACTIVE/DEGRADED
   constituents are available alternatives while FAILED (terminal) is
   never one — the WORK-013 table's own recovery edge motivates keeping
   DEGRADED plannable (disclosed in the module docstring).

## 5. Out-of-scope discipline (nothing else changed)

The M008 delta contains only: `replan/` (new, 7 files), `sessions/`,
`mobility/`, `multipath/` (the 3 docstring-only harvest disclosures — no
code, API, or import change), `tools/replan_selftest.py` (new), and
`docs/M008-evidence.md` (this record). No control-plane surface, no
`spec/` file, no `.github/` file, no protocol schema, no `contracts/`,
`executionplans/`, `adapters/`, `assurance/`, `offers/` or any other
canonical-domain modification (all consumed by reference only — verified
in the battery's one-way-harvest and PR-delta cases). The drift guard
classifies the delta implementation-only; the provenance gate verifies
full coverage by R7-CORE-001 (`replan/`, `sessions/`, `mobility/`,
`multipath/`, `tools/`, `docs/M008-evidence.md` are all declared M008
scope entries).

Note (honest limitation, the M006 precedent): the CI workflow does not yet run
`tools/replan_selftest.py` — wiring a new battery step into `.github/` is a
control-plane change outside this implementation PR's boundary. The battery
runs locally on the delivery head (38/38 ×3, exit-code-based) and is the
SOFTWARE evidence for this delivery; CI wiring is a Tech Lead/governance action
at acceptance time (the M005/M006 precedent: their battery steps landed with
the respective acceptance governance commits; the M007 adapter battery was
already wired at its baseline). The three harvested batteries
(`session_selftest.py`, `mobility_selftest.py`, `multipath_selftest.py`) ARE
CI-wired already and run green on the PR head.

## 6. Evidence classes (honest disclosure)

- All M008 acceptance criteria: **SOFTWARE** class (deterministic offline
  battery, 38/38 PASS on the delivery head; every blocking battery and
  governance gate in the CI suite green on the delivery head — the one
  non-green step, the legacy `spec_check.py` compatibility audit, is
  `continue-on-error: true` in the CI workflow: it fails (rc=1) on the
  pre-delivery baseline as well, and its ARCH-08 verdict cannot see the R7
  program authorization by frozen construction (the workflow's own comment;
  the active-era successor gate `authorization_provenance.py` PASSES and
  verifies the delta's R7-CORE-001 coverage).
- No pending child is claimed delivered: M009-M014 surfaces are consumed
  only where already accepted (M003 offers, M005 assurance, M006
  executionplans, M007 adapters — all by reference); no unaccepted child
  semantics are faked.
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M008 creates and closes
  none; EVID-002..EVID-008 remain open and untouched, and no evidence produced
  by this delivery is physical, production, or live-service evidence. No
  SOFTWARE evidence is converted into PHYSICAL PASS.

## 7. Delivery provenance

- Branch: `m008-replan` from the baseline `4d501da` (the DEC-0107-accepted
  M007 state); append-only delivery history.
- Battery: `python3 tools/replan_selftest.py` → PASS (38/38) on the delivery
  head, run 3× consecutively.
- Full suite: every battery the CI workflow runs, in exact workflow order, on
  the delivery head with exit-code-based detection — see the PR body for the
  numbered results — plus the three harvested batteries' accepted counts
  (session 55/55, mobility 43/43, multipath 45/45 — re-run inside the M008
  battery as well, case_33).
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
- Accepted sibling batteries at this head: contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33,
  roamlink 56/56, comos 33/33, assurance 97/97, executionplan 36/36,
  adapter 70/70 (the DEC-0107 accepted count), policy 103/103, payment
  44/44, eligibility 46/46 (the M009 DEC-0109 re-baselines), session
  55/55, mobility 43/43, multipath 45/45 (the harvested surfaces).
