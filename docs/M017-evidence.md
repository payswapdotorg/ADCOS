# M017 — Disaster Recovery and State Reconciliation — Evidence Record

**Work Item:** M017 · **Authorization:** R8-CORE-001 (DEC-0114, the bounded R8 program
authorization; M017 is the R8 charter's current child per DEC-0116)
**Baseline:** `28b31500a928f2f75582bfb79039e315187d72b2` (the DEC-0109 R7-completion head,
per the authorization record; the branch rides the DEC-0116 M016-acceptance head
`bda91c39fb80c89dc3df1eaf1864f6560558a16b` — the current main)

This record persists the verified facts of the M017 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed or implied,
and EVID-002..EVID-008 remain open and untouched.

## 1. Delivered surface

- **`recovery/` (NEW)** — the disaster-recovery and state-reconciliation domain of the
  R8 charter M017 scope, ON the canonical authority, composing the accepted surfaces
  BY REFERENCE (import and compose; never reimplemented, weakened, forked, or
  bypassed):
  - `recovery/errors.py` — the frozen `recovery-*` typed reason vocabulary (11
    fail-closed codes; the charter's core fail-closed snapshot rejection
    `recovery-snapshot-unverifiable` (an unverifiable snapshot REJECTED WHOLE —
    never partially trusted, never best-effort loaded); the LOCK-106
    `recovery-history-fabricated` (no historical record rewritten, no gapless
    sequence silently renumbered); the RTO `recovery-rto-exceeded` (the bound as a
    declared operation count, never wall clock); `recovery-restore-diverged` /
    `recovery-plane-mismatch`; consumed-domain errors — `ResilienceError`,
    `LocalFirstError`, `ContractError`, `EvidenceError`, `ReplanError` — wrapped at
    every boundary with their deterministic text preserved; exception isolation
    throughout).
  - `recovery/model.py` — the typed records: `RecoveryPoint` (the typed recovery
    point over one journal-bearing plane — the plane journal carried as immutable
    canonical JSON record lines (the byte-exact restore material), the
    CONTENT-DERIVED identity over the plane content (the LOCK-106 class: identity
    from content, never position or time), the content-derived state digest, the
    journal watermark and the full provenance envelope), `DrillPlan`/`DrillStep`
    (the deterministic, replayable drill operation sequence — strictly increasing
    injected instants, never wall-clock dependent), `OperationBudget`/
    `OperationCounts` (the RTO-style bound as DECLARED deterministic operation
    counts — journal appends, folds, verifications), `RestoreVerification`/
    `RestoreDivergence` (byte-exact or disclosed-and-reconciled — the mechanically
    enforced outcome discipline: a divergence outcome without its disclosed
    records fails closed, never silently absorbed), `CrossPlaneDivergence`/
    `PlaneReconciliation` (the cross-plane convergence with typed divergence
    records; the accepted `ResyncResult` serialization preserved VERBATIM),
    `DrillResult` (the content-derived run outcome carrying the measured RTO
    accounting — defense in depth: an over-budget result fails closed at
    construction).
  - `recovery/snapshot.py` — the snapshot/recovery-point construction over BOTH
    journal-bearing planes through the ACCEPTED read surfaces
    (`snapshot_runtime_plane` over the M015 `RuntimeStore` journal;
    `snapshot_offline_plane` over the M016 `OfflineJournal`); the fail-closed
    WHOLE-POINT verification (`verify_recovery_point`: unparseable material, a
    missing provenance envelope, a payload record whose content-derived identity
    does not re-derive through the ACCEPTED constructor, an attribution mismatch,
    or a renumbered/watermark-mismatched journal shape — each rejects the snapshot
    WHOLE); and the restores through the ACCEPTED construction-is-recovery
    constructors (`RuntimeStore.from_events` / `OfflineJournal.from_records` —
    the accepted folds stay the sole writers of plane state; the restore never
    writes around them).
  - `recovery/verify.py` — `verify_restore` (the typed restore verification: the
    recovered plane MUST reproduce its recovery point identity-for-identity and
    position-for-position — a re-identified or renumbered recovered record fails
    closed as `recovery-history-fabricated`; the pre-failure plane MUST carry the
    point's history verbatim as its prefix — a rewrite fails closed, never a
    "reconciliation"; the records the pre-failure plane carried BEYOND the point
    are LOST with the failure, disclosed one typed record each cited by their
    ORIGINAL content-derived identities and reconciled onto the recovery point as
    the authoritative base — restoring them would fabricate history, dropping
    them silently would absorb the divergence) and `reconcile_planes` (the
    cross-plane reconciliation: the attribution gates FIRST — a journal that does
    not ride the owning contract is unreconcilable and fails closed before any
    convergence drive (LOCK-101/LOCK-117); the accepted M016
    `close_partition` driven BY REFERENCE when the episode is open — the accepted
    fail-closed order, the accepted reconnect pair naming BOTH the OLD and the
    NEW authority views (the WORK-012 discipline), the accepted typed divergence
    records preserved VERBATIM in the reconciliation record; the composition
    links between the journal planes verified (an unresolved citation disclosed
    as a typed divergence record); the LOCK-106 evidence records verified present
    on the evidence plane (a missing record disclosed as a typed divergence
    record — never silently dropped)).
  - `recovery/drill.py` — `run_drill`, the deterministic drill engine (the plan's
    steps executed in order: snapshot -> induced loss -> restore -> verify ->
    reconcile), with the RTO ledger (the deterministic operation counters —
    journal appends measured mechanically as the per-plane record-count deltas
    across each step, the evidence-plane ingests included; folds counted per the
    engine's driving convention, 2 per restore — the accepted construction fold
    plus the accepted integrity re-fold — and 1 per reconcile; verifications
    counted at every identity re-derivation, digest computation, byte-comparison
    and cross-plane check; a counter that exceeds the declared bound fails
    closed at the increment point) and the drill's LOCK-106 evidence records
    (the plane-loss `ObservationEvidence` — the frozen `health-state` metric,
    the NOT_RUNNING ordinal 3 — and the restore-verification
    `AttestationEvidence` — the frozen `controller-verified` kind; both consumed
    from the accepted evidence typing BY REFERENCE and ingested into the
    caller's accepted `EvidenceStore`).
  - `recovery/__init__.py` — the public surface (37 names).
- **`tools/recovery_selftest.py` (NEW)** — the M017 battery: 36 deterministic,
  offline, seeded cases covering the charter's (a)-(h) matrix (§2).
- **`docs/M017-evidence.md`** — this record.

## 2. Verification matrix (the battery, SOFTWARE class per case)

`python3 tools/recovery_selftest.py` — all 36 cases green, run 3× consecutively
on the delivery head (byte-identical output; exit-code-based verification).

| Charter criterion | Battery verification | Class | Case(s) |
|---|---|---|---|
| (a) deterministic disaster-recovery drills over the journal-bearing state planes (the M015 runtime journals and the M016 offline journals) | The snapshot construction + restore round-trips across BOTH planes: the point captured at the plane head through the ACCEPTED read surfaces, restored byte-exactly through the ACCEPTED `RuntimeStore.from_events` / `OfflineJournal.from_records` (identities, journal positions and canonical bytes preserved; the folded session/state byte-identical; the serialized replay reproduces); the restored planes remain LIVE accepted surfaces (the restored store takes the explicit degraded transitions, the restored journal takes a new accepted admission — construction composes forward, history append-only); the drill engine's step-order gates fail closed (a loss before its snapshot, a restore without a point or without a loss, a verify while lost, a reconcile while lost, a double snapshot, an evidence-producing final step — the drill never invents a plane) | SOFTWARE | case_03, case_04, case_05, case_06 |
| (b) the drill determinism (same drill inputs, run twice, byte-identical outcome) | The full drill scenario (the drill result, the plan, the evidence-plane state digest, both recovery points) run twice = byte-identical; the content-derived run id and the measured operation counts identical; byte-identical digests across PYTHONHASHSEED 0/1/42 subprocesses; the serialized replay (the drill result and the recovery points replay from their canonical serializations; the serialized-point restore equals the live-point restore) | SOFTWARE | case_07, case_08, case_31 |
| (c) restore verification with induced divergence (disclosed and reconciled, never silently absorbed) | The plane advances 2 accepted admissions BEYOND the recovery point: BOTH disclosed as typed divergence records cited by their ORIGINAL content-derived identities, reconciled onto the recovery point (the only legal resolution — a divergence never reconciles onto partially-trusted material); the failure-during-recovery drill (a SECOND loss after the reconciliation) discloses the 2 reconciliation-appended reconnect events the same way; the silent-absorption rejections (an outcome without its disclosed records, a byte-exact outcome carrying records, a byte-exact outcome with differing digests — all fail closed at the record boundary) | SOFTWARE | case_09, case_10, case_11 |
| (d) recovery-time bounds as declared deterministic operation counts (no wall clock) | The bound is EXPRESSED as pure integer operation counts on the plan (journal appends, folds, verifications — no time members anywhere on the budget/counts records); the MEASURED accounting recorded on the result, deterministic across re-runs, within the declared bound; the declared budget carried verbatim; ENFORCED: three tight budgets fail closed `recovery-rto-exceeded` at the increment point (the deterministic detail names the counter, the measured count and the declared bound) and an over-budget hand-built drill result fails closed at construction; no wall clock, no sleeps, no timing measurements anywhere in `recovery/` (AST-audited) | SOFTWARE | case_12, case_13, case_33 |
| (e) cross-plane reconciliation (the contracts/journal/evidence planes converge with typed divergence records) | The converged outcome: zero divergences, the contract's OWN LOCK-108 fingerprint consumed by reference (never recomputed), the plane digests reproducing an INDEPENDENT accepted replay (restore both points, drive the same accepted close — the same post-drill journals), the accepted resync preserved VERBATIM and re-validating through the accepted `ResyncResult` constructor, 4 LOCK-106 drill evidence records preserved on the evidence plane; the accepted resync's OWN typed divergence records preserved verbatim (the contested subject, the local operation cited, the declared rule, the authority-side resolution — the localfirst/ divergence vocabulary consumed by reference where it fits; the no-silent-loss accounting 3 admitted = 2 applied + 1 cited); the evidence-record-missing and composition-link-unresolved divergences disclosed as typed records (never silently dropped); the attribution mismatch failing closed BEFORE any convergence drive (unreconcilable — LOCK-101/LOCK-117) | SOFTWARE | case_14, case_15, case_16, case_17, case_18 |
| (f) recovery never fabricates history (LOCK-106) | Every recovered record preserves its original content-derived identity, its journal position AND its canonical bytes; the drill's recovery points reproduce the independently constructed points (same inputs, same content identities); a forged/re-identified record fails closed BOTH as a restored record (`recovery-history-fabricated`) and as a snapshot payload (`recovery-snapshot-unverifiable`, rejected whole); a silently renumbered journal position fails closed; a rewritten pre-failure history fails closed (never a "reconciliation"); a point claiming unevidenced history fails closed | SOFTWARE | case_19, case_20, case_21, case_22 |
| (g) fail-closed recovery (an unverifiable snapshot rejected, never partially trusted) | Five rejection classes, each REJECTED WHOLE at the load, the verification and the restore: unparseable record lines, provenance-missing (the point's own envelope at the load; a payload record's envelope at the verification — LOCK-118), a tampered payload identity (the accepted constructor's tamper evidence surfaced as the typed whole-point rejection), a state digest / recovery-point identity that does not re-derive (bad integrity), and renumbered/watermark-mismatched journal shapes | SOFTWARE | case_23, case_24, case_25, case_26, case_27 |
| (h) the composition substrate exercised (the M015 runtime session and the M016 offline journal driven BY REFERENCE inside the drills) | The fixture drives the accepted surfaces (the attach, the partition entry through the accepted `enter_degraded` with the LOCK-106 `observation` evidence kind, the accepted admissions); the drill drives the accepted reads (the snapshots), the accepted constructors (the restores) and the accepted close (the resync + the reconnect pair) inside its steps; the composition links resolve pre-drill and post-drill; the preserved resync re-validates through the ACCEPTED constructor and its applied set equals the journaled admissions; the drill's evidence records are the accepted LOCK-106 classes | SOFTWARE | case_28 |
| Canonical-JSON round-trips + typed errors | 9 record classes round-trip byte-identically with tamper-evident ids; tampered dicts fail closed at deserialization; consumed errors wrapped with their deterministic text preserved; composition boundaries typed (`recovery-composition` citing the substrate); the LOCK-119 secret fixture (assembled from runtime fragments) rejected at the boundary | SOFTWARE | case_29, case_30 |
| Frozen vocabularies; the consumed vocabularies by reference | The 9 M017 vocabularies frozen (planes, step kinds, outcomes, divergence codes/resolutions, reconciliation outcomes) + the 11-code reason vocabulary; the LOCK-106 evidence types/metrics/kinds and the M015 event kinds consumed BY REFERENCE (never redefined) | SOFTWARE | case_01 |
| Vocabulary/input gates fail closed | 11 record-level probes (step kind, reconcile carrying a plane, missing plane, step instant, plan contract id, non-increasing instants, empty steps, negative/boolean budget counts, point plane, point subject id, cross-plane same-plane/bad-code) all reject with the specific typed code | SOFTWARE | case_02 |
| Lock conformance (aggregate) | LOCK-101/106/108/111/117/118/119 structural evidence: content-derived ids everywhere; the contract's own fingerprint consumed; a forged-fingerprint fresh view rejected THROUGH the consumed accepted gate (the deterministic text preserved); the drill's LOCK-106 records typed with the drill producer; provenance on every serialized record | SOFTWARE | case_32 |
| LOCK-119 clock/import discipline | AST audit: no wall-clock/randomness/network constructs anywhere in `recovery/`; imports confined to stdlib + `protocol` + the accepted authorities (contracts, resilience, localfirst, evidence) | SOFTWARE | case_33 |
| One-way imports (criterion 9) | No accepted authority (contracts, replan, executionplans, evidence, assurance, offers, eligibility, policy, adapters, usage, commercial, allocation, payment, sharenet, roamlink, comos, developerapi, federation, identity, upgrade, scale, client, resilience, localfirst) imports `recovery/` (the check is import-statement-precise: the pre-existing English-word identifier `recovery` in the accepted adapters/transport sandbox surfaces is not an import); the legacy reservoir (sessions, mobility, multipath, edge, appliance) is un-imported source material only | SOFTWARE | case_34 |
| PR delta shape | Every delta file covered by the ACTIVE R8-CORE-001 scope (`authorization_provenance.covers`); no `spec/` or `.github/` touch | SOFTWARE | case_35 |
| Evidence-doc honesty | SOFTWARE class, by-reference composition, harvest, lock mapping, the RTO-as-operation-counts disclosure and the open physical obligations disclosed; no affirmative physical claims | SOFTWARE | case_36 |

**Battery result: PASS (36/36 cases), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `recovery/` consumes the accepted
  `contracts/` public surface by reference only; the recovery points, drills and
  reconciliations cite the contract id, never re-derive contract identity, and
  never write contract state (the delta contains no contract file — verified in
  the battery's one-way-import and PR-delta cases). The authority stays the
  contract.
- **LOCK-106 (evidence typing):** the drill's evidence records are typed through
  the accepted four-type vocabulary (the plane-loss observation with the frozen
  `health-state` metric, the restore-verification attestation with the frozen
  `controller-verified` kind — consumed BY REFERENCE); the recovered records
  preserve their original content-derived identities and the recovery points
  derive their identities over content (never position or time) — recovery never
  fabricates history (case_19..case_22, case_28, case_32).
- **LOCK-108 (no silent contract weakening):** enforced through the CONSUMED
  gates — the reconciliation's fresh authority view passes through the accepted
  M016 resynchronization, whose LOCK-108 fingerprint gate and per-operation
  constraint re-verification reject a forged or weakened view (the battery's
  forged-fingerprint probe fails closed through the consumed gate with its
  deterministic text preserved — case_32). The recovery surface itself carries
  no constraint material anywhere (structural — no constraint member exists on
  any recovery record).
- **LOCK-111 (optimizer replaceability):** the resynchronization's conflict
  resolution is the ACCEPTED declared recorded rule (the consumed M008 key
  vocabulary, content keys only, never temporal), preserved VERBATIM in the
  reconciliation record; same inputs -> the byte-identical resolution (the
  drill determinism, case_07/case_08).
- **LOCK-117 (authority uniqueness):** the recovery points, drill plans and
  reconciliation records ride the contract and the accepted journal-bearing
  planes as opaque references (`sha256:` content ids and canonical record
  lines); no recovery record becomes a second contract authority; the
  attribution gates fail closed on any journal that does not ride the owning
  contract (case_18).
- **LOCK-118 (provenance):** every record (point, step, plan, divergence,
  verification, cross-plane divergence, reconciliation, result) carries typed
  provenance; the drill's evidence records carry the drill producer; a
  provenance-missing snapshot is rejected whole (case_24).
- **LOCK-119 (secrets):** secret-shaped material is rejected at the boundary
  (`recovery-secret-rejected` — including a line-level scan of the payload
  record lines, the accepted evidence-store convention; the battery fixture
  assembled from runtime fragments); no wall clock, no randomness, no network,
  no sleeps anywhere in `recovery/` (AST-audited, case_33); injected instants
  only; content-derived ids over canonical JSON; the recovery-time bound is a
  DECLARED deterministic operation count, never a timing measurement
  (case_12/case_13).

## 4. Judgment calls (disclosed)

1. **The recovery point carries the plane journal as canonical JSON record
   LINES (immutable bytes), not re-typed records.** The byte-exact restore
   requirement ("recovered state equals the pre-failure state BYTE-EXACTLY")
   is delivered by carrying the accepted records' canonical serializations
   verbatim: the restore re-parses and RECONSTRUCTS them through the ACCEPTED
   constructors (whose identity re-derivation is the tamper evidence), so the
   payload is never re-interpreted by this domain — the accepted records stay
   the sole authority over their own shape. Disclosed as the M017-specific
   design choice the byte-exactness criterion requires.
2. **The RTO fold count follows a disclosed engine convention; the append and
   verification counts are measured mechanically.** Journal appends are
   measured as the per-plane record-count deltas across each engine step (the
   evidence-plane ingests included — an idempotent re-ingest that grows the
   journal by 0 counts 0, honestly). Folds are counted per the engine's driving
   convention (2 per restore — the accepted construction fold plus the accepted
   integrity re-fold; 1 per reconcile — the accepted resynchronization's episode
   fold; the append-atomicity folds inside the accepted stores are counted
   within their append operations): the accepted surfaces cannot be instrumented
   without forking them, so the convention is declared, deterministic and
   enforced identically on every run. Verifications are counted at each check
   site. Every counter is enforced at the increment point and recorded on the
   result. Disclosed as the LOCK-119-compliant realization of "recovery-time
   bounds as declared deterministic operation counts".
3. **The drill restores into FRESH holders; the caller's input holders are never
   mutated by the drill (the evidence plane excepted).** The induced loss is
   simulated by rebuilding the plane into new accepted holders from the recovery
   point (the caller's in-memory objects linger unused, exactly as a real lost
   plane would be gone); the drill's LOCK-106 evidence records ARE ingested into
   the caller's evidence plane (the evidence-visible drill — the evidence plane
   is the drill's output surface). The convergence drive (the accepted close)
   runs on the RESTORED holders. Disclosed so the composition is unambiguous.
4. **An evidence-producing drill step requires a successor step.** The drill's
   LOCK-106 records need a deterministic evidence window horizon (the
   observation's `freshness_until` / the attestation's `valid_until`); the
   engine uses the NEXT step's injected instant (the drill's own next
   operation) and fails closed when an evidence-producing step is the final
   step. Disclosed as the deterministic-window discipline (never wall clock).
5. **The cross-plane attribution mismatch fails CLOSED rather than producing a
   divergence record.** The charter's cross-plane reconciliation says the planes
   "converge with typed divergence records"; the M016 convention (the closest
   accepted material — the loser stays cited, only explicitly superseded IN THE
   REPLICA) is applied to the RECONCILABLE differences (an unresolved
   composition link, a missing evidence record — both disclosed as typed
   records). A journal that does not ride the owning contract is NOT
   reconcilable by the recovery surface (LOCK-101/LOCK-117: attribution is
   never rewritten), so it fails closed BEFORE any convergence drive — never a
   divergence record, never a silent drive. Disclosed with the lock citations.
6. **The one-way-import battery check is import-statement-precise.** The
   accepted `adapters/sandbox.py` and `transport/sandbox.py` carry a
   pre-existing local parameter named `recovery` (evidence-recovery semantics,
   predating M017); the M016 battery's identifier-token check shape would false
   positive on the English word. The M017 check flags only ACTUAL import
   statements importing the `recovery` package — the boundary the criterion
   names ("no accepted authority imports recovery/"). Disclosed as the
   check-precision judgment call.
7. **A second snapshot of the same plane within one drill run fails closed.**
   A plane carries one recovery point per drill run: a second snapshot would
   orphan the first (the loss/restore rounds key on the plane's current point).
   Multi-round drills (the failure-during-recovery shape) reuse the ONE point
   per plane — which is exactly the divergence scenario (the post-first-round
   records are lost beyond the point at the second loss). Disclosed as the
   engine's replay discipline.

## 5. By-reference composition and the legacy reservoir (disclosed)

- **By-reference composition:** `recovery/` imports only the accepted
  authorities — `contracts/` (the canonical record types and the contract's own
  LOCK-108 fingerprint), `resilience/` (the M015 `RuntimeStore`, the runtime
  journal events and the accepted `from_events` construction — the composition
  substrate), `localfirst/` (the M016 `OfflineJournal`, the accepted
  `from_records` construction, the accepted `close_partition`/resynchronization
  with its typed divergence records — the composition substrate), and
  `evidence/` (the LOCK-106 typed records and the append-only `EvidenceStore` —
  the evidence plane) — plus `protocol/` and the stdlib. AST-audited (case_33);
  the import direction is one-way (case_34: no accepted authority imports
  `recovery/`). Nothing is reimplemented, weakened, forked, or bypassed: the
  accepted folds stay the sole writers of plane state; the accepted gates stay
  the sole validators; the accepted divergence vocabulary is preserved verbatim
  where it fits (case_15); the accepted evidence typing is consumed, never
  duplicated (case_28).
- **The legacy reservoir is source material only.** No legacy package
  (`sessions/`, `mobility/`, `multipath/`, `edge/`, `appliance/`) is imported
  (AST-audited, case_34), modified, or referenced; the DR disciplines are
  re-expressed on the accepted 1.1 journal-bearing planes inside `recovery/`.

## 6. Out-of-scope discipline (nothing else changed)

The M017 delta (from the DEC-0116 acceptance head `bda91c3`) contains only:
`recovery/` (NEW, 6 files), `tools/recovery_selftest.py` (NEW), and
`docs/M017-evidence.md` (this record). No control-plane surface, no `spec/`
file, no `.github/` file, no protocol schema, and no accepted-domain
modification (`contracts/`, `replan/`, `resilience/`, `localfirst/`,
`executionplans/`, `evidence/`, or any other canonical domain — all consumed by
reference only; verified in the battery's one-way-import and PR-delta cases).
The drift guard classifies the delta implementation-only; the provenance gate
verifies full coverage by R8-CORE-001 (`recovery/`,
`tools/recovery_selftest.py`, `docs/M017-evidence.md` are declared M017 scope
entries).

The CI workflow's M017 step (`tools/recovery_selftest.py`, the existence-guard
pattern) was wired by the DEC-0116 governance commit BEFORE this delivery (it
is not part of this delta); it activates on this delivery and skips visibly
until the merge.

## 7. Evidence classes (honest disclosure)

- All M017 acceptance criteria: **SOFTWARE** class (deterministic offline
  battery, 36/36 PASS on the delivery head; every blocking battery and
  governance gate in the CI suite green on the delivery head).
- No pending child is claimed delivered: the M018/M019 surfaces do not exist
  yet and are not faked; the CI existence-guard steps for their batteries skip
  visibly (disclosed, the DEC-0101 wiring convention; the M018/M019 batteries
  do not exist yet and are not created by this delivery).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M017 creates and closes
  none; EVID-002..EVID-008 remain open and untouched, and no evidence produced
  by this delivery is physical, production, or live-service evidence. No
  SOFTWARE evidence is converted into PHYSICAL PASS.

## 8. Delivery provenance

- Branch: `m017-recovery`, append-only from the DEC-0116 acceptance head
  `bda91c3` (the current main); no rebase, no force-push, no amending;
  commit-as-you-go delivery history (the package first, then the battery + this
  record).
- Battery: `python3 tools/recovery_selftest.py` -> PASS (36/36) on the delivery
  head, run 3× consecutively, byte-identical.
- Full suite: every battery the CI workflow runs, in exact workflow order, on
  the delivery head with exit-code-based detection — see the PR body for the
  numbered results.
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
- Accepted sibling batteries at this head: contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33, roamlink
  56/56, comos 33/33, assurance 97/97, executionplan 36/36, adapter 70/70,
  replan 38/38, payment 44/44, eligibility 46/46, policy 103/103, client 24/24,
  scale 45/45, conformance 63/63, resilience 36/36, localfirst 35/35 (verified
  by direct execution on the delivery head, exit-code-based).
