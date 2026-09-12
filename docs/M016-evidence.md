# M016 — Local-First and Offline Operation — Evidence Record

**Work Item:** M016 · **Authorization:** R8-CORE-001 (DEC-0114, the bounded R8 program
authorization; M016 is the R8 charter's current child per DEC-0115)
**Baseline:** `28b31500a928f2f75582bfb79039e315187d72b2` (the DEC-0109 R7-completion head,
per the authorization record; the branch rides the DEC-0115 M015-acceptance head
`6b96438fbef3634ded30c4defb5727d88f74ebb3` — the current main)

This record persists the verified facts of the M016 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed or implied,
and EVID-002..EVID-008 remain open and untouched.

## 1. Delivered surface

- **`localfirst/` (NEW)** — the local-first/offline operation domain of the R8 charter
  M016 scope, composing the accepted surfaces BY REFERENCE (import and compose; never
  reimplemented, weakened, forked, or bypassed):
  - `localfirst/errors.py` — the frozen `localfirst-*` typed reason vocabulary (13
    fail-closed codes; the charter's core fail-closed stale-authority rejections
    `localfirst-authority-stale` / `localfirst-authority-not-yet-valid`; the
    LOCK-108-across-the-boundary `localfirst-constraint-weakened` /
    `localfirst-constraint-mismatch`; consumed-domain errors — `ReplanError`,
    `ResilienceError`, `ContractError` — wrapped at every boundary with their
    deterministic text preserved; exception isolation throughout).
  - `localfirst/model.py` — the typed records: `AuthoritySnapshot` (the local
    replica's view of the canonical authority material with the DECLARED freshness
    window and the contract's own LOCK-108 fingerprint, consumed — never recomputed),
    `OfflineOperation` (the ordered, idempotent, replayable journal record with the
    full kind-member discipline and the POSITION-INDEPENDENT content identity — the
    idempotency key), `LocalState` (the deterministic fold result),
    `DivergenceRecord` / `ConvergenceRejection` / `ResyncResult` (the typed
    divergence and convergence records with the mechanically enforced no-silent-loss
    invariants); the frozen vocabularies; and the resolution-rule kernel (the
    LOCK-111 class over the CONSUMED M008 `TIE_BREAK_KEYS` vocabulary — both
    conflicting sides projected onto the orderable candidate shape, content keys
    only, never temporal).
  - `localfirst/journal.py` — the deterministic offline operation journal (ordered,
    gapless, conflict-free, kind-disciplined, tamper-evident; construction-is-
    recovery; the journal discipline conventions of the accepted
    `resilience/journal.py` studied and consumed as conventions — this is its own
    typed surface, never a fork of the runtime journal).  The append is IDEMPOTENT
    (a retried operation derives the same position-independent identity and never
    double-applies) and ATOMIC (a rejected append leaves the journal
    byte-identical).  The fold MECHANICALLY enforces the core M016 discipline: an
    ADMITTED admission whose instant lies outside its carried freshness window
    fails the fold — a local state past its declared freshness bound never silently
    authorizes.
  - `localfirst/admission.py` — the partition-tolerant admission in the accepted
    raising-gate + typed-twin convention (the `replan/validation.py` pattern):
    `check_authority_fresh` (the raising fail-closed stale-authority gate),
    `check_admission_preserves_contract` (the raising LOCK-108 gate through the
    CONSUMED M008 `validate_constraints_preserved` — a weakening claim rejected
    citing the specific kinds), `admit_operation` (the typed twin returning the
    JOURNALED decision — admitted, or the stale / not-yet-valid / weakened
    rejection classes; every decision carries the authority's declared freshness
    window), and `authority_snapshot` (the snapshot constructor from the accepted
    `ConnectivityContract`).
  - `localfirst/resync.py` — the explicit reconnect-and-resynchronize core: the
    fail-closed pre-gates (the OPEN-episode requirement; the fresh view's LOCK-108
    fingerprint must reproduce the contract's own — a forged/stale authority view
    rejected whole; the declared resolution rule validated against the consumed
    key vocabulary), the per-operation LOCK-108 re-verification against the LIVE
    contract (a weakening journaled-admitted record REJECTED with the typed reason
    — never silently converged, never silently dropped), the divergence detection
    (a local admitted subject also present in the fresh authority records — typed
    with full provenance on BOTH sides), and the deterministic convergence by the
    DECLARED RECORDED rule.
  - `localfirst/offline.py` — the M015 composition substrate (the accepted
    `resilience/` runtime driven BY REFERENCE, never duplicated):
    `attach_runtime_session` (the runtime session realizing the base authority
    view — the WORK-012 member shape), `sync_authority_view` (the connected sync:
    the explicit reconnect pair onto a refreshed view, idempotent on the held
    view), `open_partition` (the journaled offline/degraded ENTRY through the
    accepted `enter_degraded` with the LOCK-106 `observation` evidence kind and the
    episode id as the decision-kinded evidence reference), `local_admit` (the
    gated, idempotent journal admission), and `close_partition` (the fail-closed
    ORDER: the pure convergence FIRST — a typed rejection leaves the runtime
    DEGRADED and the partition open — then the accepted reconnect pair naming BOTH
    the OLD and the NEW authority views, then the journaled offline EXIT carrying
    the resync result id and the M015 reconnect evidence id).
  - `localfirst/__init__.py` — the public surface (35 names).
- **`tools/localfirst_selftest.py` (NEW)** — the M016 battery: 35 deterministic,
  offline, seeded cases covering the charter's (a)-(h) matrix (§2).
- **`docs/M016-evidence.md`** — this record.

## 2. Verification matrix (the battery, SOFTWARE class per case)

`python3 tools/localfirst_selftest.py` — all 35 cases green, run 3× consecutively
on the delivery head (byte-identical output; exit-code-based verification).

| Charter criterion | Battery verification | Class | Case(s) |
|---|---|---|---|
| (a) deterministic offline operation journals: ordered, idempotent, replayable | The journal round-trip: gapless ordered positions, the kind chain (entered → admissions → exited), the fold twice + `from_records` rebuild = the byte-identical state, the exit carrying the resync + reconnect links; the IDEMPOTENT append: the same admission material retried returns the existing record (one application, byte-identical journal), a second admission of the same subject fails the append atomically as journal divergence | SOFTWARE | case_03, case_04 |
| (b) partition-tolerant admission with fail-closed stale-authority rejection (a case per freshness outcome) | Fresh: the within-window admission carries the declared freshness window and the claimed set verbatim; STALE: the past-bound decision is JOURNALED as `stale-rejected` + the raising `localfirst-authority-stale` gate + the fold's MECHANICAL rejection of the forged admitted-outside-window record (never a silent allow); NOT-YET-VALID: the symmetric pre-window rejection; the inclusive boundary outcomes (the window bounds themselves admit; a strictly later instant is stale) | SOFTWARE | case_05, case_06, case_07, case_08 |
| (d) LOCK-108 across the offline boundary — every weakening admission/resync candidate rejected (a case per constraint kind) | All 12 constraint kinds × DROP/RELAX/REINTERPRET: the raising gate rejects `localfirst-constraint-weakened` citing the kind; the typed twin NEVER admits a weakening claim (the rejection is JOURNALED as evidence); a wire-forged ADMITTED journal record carrying the weakened claimed set (ids re-derived over the forged content — the M008 battery's wire-forged precedent) is REJECTED by the resynchronization re-verification with the typed reason citing the kind, accounted exactly once (never silently converged, never silently dropped) | SOFTWARE | case_09..case_20 |
| (c) reconnect + resynchronization: clean convergence, detected divergence, deterministic declared recorded convergence | Clean: zero divergences, every admitted operation applied, the converged set = the fresh authority records + the local subjects in deterministic order, the episode CLOSED and the runtime ACTIVE on the fresh view; DIVERGENCE: ONE typed record citing BOTH sides with full provenance (the local operation id, the authority record verbatim with its own provenance, the subject, the declared rule, the resolution); the conflict loser is cited, never silently dropped; RULES: same inputs → byte-identical resolutions under each declared rule; the two declared rules resolve the SAME conflict in OPPOSITE directions (the projected candidate-kind orders the authority side first; the projected candidate-ids decide the content order) — the rule decides, recorded verbatim; invalid declared rules (temporal keys, non-total, reordered, non-sequence, empty, repeated) all fail closed `localfirst-resolution-invalid` with the journal byte-identical | SOFTWARE | case_21, case_22, case_23, case_24 |
| (e) degraded/offline mode entry/exit journaled and evidence-visible | The entry/exit are journaled on BOTH surfaces with typed provenance and the cross-surface evidence links: the offline journal's `partition-entered`/`partition-exited` records carry the M015 degraded-entry EVENT id and the resync + reconnect ids; the M015 runtime journal carries the `degraded-entered` event with the accepted LOCK-106 `observation` evidence kind and the episode id as the decision-kinded evidence reference | SOFTWARE | case_25 |
| (f) the M015 composition (the runtime session drives the offline transitions) | The attach (the session realizes the base view), the partition entry through the accepted `enter_degraded` (DEGRADED), the resync through the accepted reconnect pair naming BOTH the OLD and the NEW authority views (the WORK-012 discipline — the `RuntimeReconnect` evidence cites both sides + both state digests), the connected sync idempotent on the held view, and TWO episodes chaining on ONE session with the full ten-event runtime chain (created, activated, degraded, reconnect×2, sync×2, degraded, reconnect×2) — the accepted battery's discipline exercised, never duplicated | SOFTWARE | case_26 |
| (g) canonical-JSON round-trips + typed errors | The snapshot/records/state/resync/divergence/rejection records round-trip byte-identically with stable content-derived ids; tampered dicts fail closed (the derived identities re-verified at deserialization); temporal/consumed-M008/fingerprint/composition/input rejections all typed with the deterministic text preserved (the consumed M015 rejection wrapped at the composition boundary; the consumed M008 kind-citing text preserved); no raw exception text reaches stored state; rejected compositions leave the M015 journal byte-identical | SOFTWARE | case_27, case_28 |
| (h) determinism under a re-run (and PYTHONHASHSEED variation) | The full offline scenario (journals, states, resync results, M015 runtime journals, reconnect evidence) is byte-identical across re-runs; construction-is-recovery verified on the serialized replay; byte-identical resync ids, journal digests and resync records across PYTHONHASHSEED 0/1/42 subprocesses | SOFTWARE | case_29, case_30 |
| Frozen vocabularies; the consumed vocabularies by reference | The M016 record-kind/outcome/episode-state/resolution vocabularies frozen; the M008 tie-break keys, the M015 runtime states, the M002 constraint kinds and the LOCK-106 evidence types consumed BY REFERENCE (never redefined) | SOFTWARE | case_01 |
| Vocabulary/input gates fail closed | Kind/outcome/episode-state/rule/temporal/identity/duplicate-record/attribution/unknown/secret gates all reject with the specific typed code (17 probes; the LOCK-119 secret fixture assembled from fragments at runtime) | SOFTWARE | case_02 |
| Lock conformance (aggregate) | LOCK-101/106/108/111/117/118/119 structural evidence: opaque references only; the claimed constraint sets are admission DATA re-validated at admission AND at resynchronization (the `ReplanCandidate` precedent); the snapshot carries the contract's own fingerprint; provenance and content-derived ids on every record; the M015 runtime driven by reference | SOFTWARE | case_31 |
| LOCK-119 clock/import discipline | AST audit: no wall-clock/randomness/network constructs anywhere in `localfirst/`; imports confined to stdlib + `protocol` + the accepted authorities (contracts, replan, resilience) | SOFTWARE | case_32 |
| One-way imports (criterion 7) | No accepted authority (contracts, replan, executionplans, evidence, assurance, offers, eligibility, policy, adapters, usage, commercial, allocation, payment, sharenet, roamlink, comos, developerapi, federation, identity, upgrade, scale, client, resilience) imports `localfirst/`; the legacy reservoir (sessions, mobility, multipath, edge, appliance) is un-imported source material only | SOFTWARE | case_33 |
| PR delta shape | Every delta file covered by the ACTIVE R8-CORE-001 scope (`authorization_provenance.covers`); no `spec/` or `.github/` touch | SOFTWARE | case_34 |
| Evidence-doc honesty | SOFTWARE class, by-reference composition, harvest, lock mapping and the open physical obligations disclosed; no affirmative physical claims | SOFTWARE | case_35 |

**Battery result: PASS (35/35 cases; the 12 per-kind LOCK-108 cases are
individually numbered case_09..case_20 within the set), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `localfirst/` consumes the accepted
  `contracts/` public surface by reference only (the frozen public types imported;
  `contracts/` untouched — verified in the battery's one-way-import and PR-delta
  cases); the local-first records cite the contract id, never re-derive contract
  identity, and never write contract state — the converged replica records are
  local-first material; the authority stays the contract.
- **LOCK-106 (evidence typing):** the degraded/offline-mode entry rides the accepted
  M015 `enter_degraded` with the `observation` evidence kind drawn from the accepted
  four-type vocabulary (consumed BY REFERENCE; import-time drift guard in
  `localfirst/model.py`); the episode id rides as the decision-kinded evidence
  reference (case_25).
- **LOCK-108 (no silent contract weakening — across the offline boundary, the core
  M016 discipline):** enforced at four points — (1) the admission gate: the claimed
  constraint set through the CONSUMED M008 `validate_constraints_preserved`
  (`check_admission_preserves_contract` raising, `admit_operation` as the typed twin;
  a set that drops, relaxes or re-interprets ANY hard constraint is REJECTED citing
  the specific kinds — 12 per-kind battery cases × 3 weakening modes); (2) the
  fold's structural discipline (constraint material rides ONLY the admission
  records, as DATA); (3) the RESYNCHRONIZATION re-verification: every admitted
  operation's claimed set re-validated against the LIVE contract — a weakening
  journaled record is REJECTED with the typed `ConvergenceRejection` citing the
  kinds, never silently converged (case_09..20); (4) the fresh-view fingerprint
  gate: a fresh authority view whose LOCK-108 fingerprint does not reproduce the
  contract's own is rejected whole (never partially trusted).  A weakening during
  partition or resynchronization is never silent.
- **LOCK-111 (optimizer replaceability — the conflict-resolution class):** the
  resolution rule is DECLARED, INJECTED and RECORDED verbatim, validated against
  the CONSUMED M008 `TIE_BREAK_KEYS` vocabulary (content keys only, never
  temporal), and both conflicting sides project onto the orderable candidate shape
  (candidate-kind, candidate-id); same inputs → the byte-identical resolution
  (verified in-process twice, across full scenario re-runs, and across
  PYTHONHASHSEED subprocesses; the two rule directions demonstrably discriminate
  the same conflict — case_23).
- **LOCK-117 (authority uniqueness):** the authority snapshot, the offline
  operations, the local state and the resynchronization records ride the contract
  as opaque references (`sha256:` content ids, `execution-artifact` data); the
  claimed constraint sets riding the journal records are optimizer-supplied DATA
  re-validated by the consumed M008 gates (the `ReplanCandidate` precedent — never
  authority material); no second contract authority exists anywhere on the
  local-first surface.
- **LOCK-118 (provenance):** every record (snapshot, operation, state, divergence,
  rejection, resync result) carries typed provenance; the offline entry/exit cite
  the M015 event and evidence ids; the divergence records cite BOTH sides with
  their own provenance.
- **LOCK-119 (secrets):** secret-shaped material is rejected at the boundary
  (`localfirst-secret-rejected` — the battery fixture assembled from runtime
  fragments); no wall clock, no randomness, no UUIDs, no network anywhere in
  `localfirst/` (AST-audited, case_32); injected instants only; content-derived
  ids over canonical JSON.

## 4. Judgment calls (disclosed)

1. **The offline operation identity is derived over the POSITION-INDEPENDENT
   operation core (the idempotency key).** The `RuntimeEvent` convention derives
   the event id over the full record including the journal position; the M016
   charter requires IDEMPOTENT offline journals (an operation retried while
   partitioned — an uncertain outcome retried after a crash — must never
   double-apply), so the offline operation identity deliberately derives over the
   position-independent core while the journal position stays a separate monotonic
   member validated by the fold (gapless, conflict-free, unique per identity).
   Disclosed as the M016-specific design choice the idempotency criterion requires.
2. **The admission rejections are typed OUTCOMES (journaled), not only raised
   errors.** The charter's "expiry is a typed fail-closed rejection" is delivered in
   the accepted raising-gate + typed-twin convention (the `replan/validation.py`
   pattern): `check_authority_fresh` RAISES `localfirst-authority-stale` /
   `localfirst-authority-not-yet-valid`, and `admit_operation` — the twin — returns
   the JOURNALED decision record whose outcome class IS the typed rejection.  A
   rejected admission is evidence (never a silent allow, never a silent drop), and
   the fold MECHANICALLY rejects a forged admitted record outside its carried
   window (case_06) — the fail-closed discipline is machine-checked at replay.
3. **The local-first node's runtime session names its realization as the authority
   view it operates on.** The M015 runtime session's realization references (the
   WORK-012 member shape) are the authority snapshot id and the authority state
   digest, so every authority-view transition (the connected sync, the partition
   resync) rides the accepted explicit reconnect discipline naming BOTH the OLD and
   the NEW views verbatim — the composition point the charter requires ("the M015
   runtime is the composition substrate"), with the reconnect evidence carrying
   both sides (case_26).
4. **The conflict key is the opaque subject identity.** Divergence is detected by
   opaque reference-value equality between a local admitted subject and a fresh
   authority record (the local-first surface never interprets authority semantics —
   LOCK-117); the default resolution rule orders the projected candidate-kind with
   the authority side first (LOCK-101: the canonical authority never silently loses
   to a local replica unless a caller explicitly declares the content-order rule).
   The battery fixture uses a subject value that sorts after `sha256:` so the two
   declared rules demonstrably resolve the same conflict in opposite directions
   (case_23) — the rule decides, visibly.
5. **The resynchronization's no-silent-loss invariants are mechanically enforced on
   the finished record.** `ResyncResult` fails closed on: a duplicated application,
   a duplicated rejection, an operation both applied and rejected, a divergence
   citing a rejected operation (the LOCK-108 rejection path never reaches conflict
   resolution), and a converged record set carrying a subject twice.  A WON
   conflict is applied AND cited — the citation is the evidence, not a second
   application (the converged set carries the winning subject exactly once).

## 5. By-reference composition and the legacy reservoir (disclosed)

- **By-reference composition:** `localfirst/` imports only the accepted authorities
  — `contracts/` (the canonical record types and the contract's own LOCK-108
  fingerprint), `replan/` (the M008 LOCK-108 gates and the tie-break key
  vocabulary), and `resilience/` (the M015 `RuntimeStore` lifecycle, the reconnect
  discipline and the reconnect evidence — the composition substrate) — plus
  `protocol/` and the stdlib.  AST-audited (case_32); the import direction is
  one-way (case_33: no accepted authority imports `localfirst/`).  Nothing is
  reimplemented, weakened, forked, or bypassed; the M008 vocabulary is consumed,
  never redefined (case_01); the M015 runtime is driven, never duplicated (case_26).
- **The legacy reservoir is source material only.** The WORK-012 journaling
  discipline (the append-only deterministic fold), the handover/resynchronization
  semantics and the edge/offline operational patterns were studied from the legacy
  `sessions/`, `mobility/`, `multipath/`, `edge/`, `appliance/` packages (harvest
  material per the frozen migration classification matrix) and RE-EXPRESSED on the
  1.1 authority inside `localfirst/`.  The legacy packages are NOT imported
  (AST-audited, case_33), NOT modified (their M008 docstring disclosures stay
  byte-identical — the delta contains no legacy-package file), and remain their own
  authorities for their existing consumers.

## 6. Out-of-scope discipline (nothing else changed)

The M016 delta (from the DEC-0115 acceptance head `6b96438`) contains only:
`localfirst/` (NEW, 7 files), `tools/localfirst_selftest.py` (NEW), and
`docs/M016-evidence.md` (this record).  No control-plane surface, no `spec/` file,
no `.github/` file, no protocol schema, and no accepted-domain modification
(`contracts/`, `replan/`, `resilience/`, `executionplans/`, `evidence/`, or any
other canonical domain — all consumed by reference only; verified in the battery's
one-way-import and PR-delta cases).  The drift guard classifies the delta
implementation-only; the provenance gate verifies full coverage by R8-CORE-001
(`localfirst/`, `tools/`, `docs/M016-evidence.md` are declared M016 scope entries).

The CI workflow's M016 step (`tools/localfirst_selftest.py`, the existence-guard
pattern) was wired by the DEC-0115 governance commit BEFORE this delivery (it is
not part of this delta); it activates on this delivery and skips visibly until the
merge.

## 7. Evidence classes (honest disclosure)

- All M016 acceptance criteria: **SOFTWARE** class (deterministic offline battery,
  35/35 PASS on the delivery head; every blocking battery and governance gate in
  the CI suite green on the delivery head).
- No pending child is claimed delivered: M017-M019 surfaces do not exist yet and
  are not faked; the CI existence-guard steps for their batteries skip visibly
  (disclosed, the DEC-0101 wiring convention).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M016 creates and closes none;
  EVID-002..EVID-008 remain open and untouched, and no evidence produced by this
  delivery is physical, production, or live-service evidence.  No SOFTWARE evidence
  is converted into PHYSICAL PASS.

## 8. Delivery provenance

- Branch: `m016-localfirst`, append-only from the DEC-0115 acceptance head
  `6b96438` (the current main); no rebase, no force-push, no amending;
  commit-as-you-go delivery history (the package first, then the battery + this
  record).
- Battery: `python3 tools/localfirst_selftest.py` -> PASS (35/35) on the delivery
  head, run 3× consecutively, byte-identical.
- Full suite: every battery the CI workflow runs, in exact workflow order, on the
  delivery head with exit-code-based detection — see the PR body for the numbered
  results.
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
- Accepted sibling batteries at this head: contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33, roamlink
  56/56, comos 33/33, assurance 97/97, executionplan 36/36, adapter 70/70,
  replan 38/38, payment 44/44, eligibility 46/46, policy 103/103, client 24/24,
  scale 45/45, conformance 63/63, resilience 36/36 (verified by direct execution
  on the delivery head, exit-code-based).
