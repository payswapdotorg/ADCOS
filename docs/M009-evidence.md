# M009 — Usage and Commercial Reconciliation — Evidence Record

**Work Item:** M009 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7 program
authorization; M009 is an authorized child scope)
**Baseline:** `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (the R7 activation baseline;
branch rooted at the reconciled main head `9e16cb0`)

This record persists the verified facts of the M009 delivery: the `usage/`,
`commercial/`, `allocation/`, `payment/` domains harvested and re-bound to the
canonical `contracts/` domain (M002, DEC-0102) — usage records and settlement
references carry canonical contract references (LOCK-113), never a second
contract model — plus the DEC-0099-disclosed era-superseded battery re-baselines
(payment and eligibility) assigned to the M009 commercial track.

## 1. Delivered surface

### 1.1 `usage/` — the contract-bound usage evidence boundary (harvest + re-bind)

- **`usage/families.py` (NEW)** — the M009 family-classified citation surface:
  the frozen `EvidenceFamily` vocabulary (DELIVERY_EVIDENCE / COMMERCIAL /
  SESSION / NETWORK_PATH / PAYMENT), `EvidenceReference` (one family-classified
  public read carrying the canonical `contract_id` binding member, validated
  when non-empty), `EvidenceIndex` (the immutable fail-closed family-classified
  collection: `by_family`, exact-id resolution, canonical round-trips),
  `UsageState` (the era name for the frozen `UsageTransactionState` account
  walk), and the canonical contract-id grammar citation
  (`validate_contract_id` / `matches_contract_id_grammar` — pure string
  predicate, no second vocabulary).  This is the honest re-establishment of
  the W044-era import surface (`from usage import EvidenceFamily …`) on the
  M009 semantics: the names classify commercial-track citations; the typed
  admission surface stays `UsageEvidenceIndex`.
- **`usage/contract_binding.py` (NEW)** — the canonical re-bind of the typed
  evidence boundary: `ContractCommercialSnapshot(CommercialTransactionSnapshot)`
  — the account key IS the canonical contract id (M002 `sha256:` grammar,
  fail-closed), `commercial_state` cites the canonical contract state
  (validated against `contracts.CONTRACT_STATES`, imported from the canonical
  domain — LOCK-101: the vocabulary is consumed, never duplicated),
  `is_delivery_eligible()` re-based onto
  `CONTRACT_DELIVERY_ELIGIBLE_STATES` (EXECUTION_ACTIVE, DELIVERY, ASSURED,
  DEGRADED, USAGE_FINAL, SETTLEMENT_PENDING, SETTLED), and
  `is_reservation_phase()` re-based onto the canonical CONTRACT_ACTIVE
  lease-holding state (the W051 RESERVATION_HELD counterpart); the
  `contract_commercial_snapshot(...)` builder; index deserialization
  reconstructs contract-cited snapshots so the binding survives canonical
  round-trips byte-identically.
- **`usage/evidence.py` (evolved)** — the binding-preserving
  `_reconstruct_snapshot` deserialization path (entries carrying
  `binding == "contract"` reconstruct as the contract-cited snapshot).
- **`usage/validation.py` (evolved)** — `validate_delivery_eligibility` gained
  the canonical reservation fork: a contract-cited snapshot at CONTRACT_ACTIVE
  fails closed `RESERVATION_NOT_USAGE` exactly like the legacy RESERVATION_HELD
  citation; INTENT/OFFER_SELECTED fail closed `TRANSACTION_NOT_DELIVERING`;
  the legacy W051-state snapshots keep their frozen semantics (the M006
  composition-track compatibility).
- **`usage/__init__.py` (evolved)** — the public surface exports the M009
  symbols (additive; every W052 name retained).

### 1.2 `commercial/` — the contract-bound commercial reconciliation core (harvest + re-bind)

- **`commercial/contract_binding.py` (NEW)** — the canonical binding surface:
  `ContractCitation` (contract id + canonical state + provenance, both
  validated against the canonical domain's frozen grammar and vocabulary),
  `ContractReferenceIndex` (the immutable fail-closed injected index built
  from `contracts.ContractStore` public reads),
  `CONTRACT_STATE_FLOOR_BY_ACTION` + `CONTRACT_STATE_RANK` (the canonical-state
  floor each commercial action requires — the commercial reconciliation walk
  NEVER runs ahead of the canonical contract: SELECT_OFFER requires
  OFFER_SELECTED+, the reservation/session/path actions require
  CONTRACT_ACTIVE+, START_DELIVERY/ACCRUE_USAGE require EXECUTION_ACTIVE+,
  COMPLETE_DELIVERY requires DELIVERY+, FINALIZE_BILLABLE requires USAGE_FINAL+,
  INITIATE_SETTLEMENT requires SETTLEMENT_PENDING+, SETTLE requires SETTLED+;
  compensating actions require only a resolvable citation), and
  `validate_contract_binding` (fail-closed `CONTRACT_STATE_INVALID`; terminal
  contract states admit no forward action).
- **`commercial/errors.py` (evolved)** — two additive reason codes
  (`CONTRACT_UNKNOWN`, `CONTRACT_STATE_INVALID`); every W051-era code retained.
- **`commercial/model.py` (evolved)** — `CommercialTransaction` gained the
  `contract_id` member (the LOCK-113 binding; empty ONLY in the unbound legacy
  mode), carried in `content()` (digest-stable, self-consistent for the
  accepted composition consumers).
- **`commercial/lifecycle.py` (evolved)** — `CommercialCore.__init__`/`load`
  gained the optional `contract_references` parameter (the bound mode — the
  M009 normative surface for the commercial track); `_execute` gained the
  contract-binding gate (step 5b): bound-mode `submit_intent` requires the
  canonical contract citation in the intent payload (fail-closed
  `CONTRACT_UNKNOWN`), every subsequent command resolves the transaction's
  binding against the injected index, and every forward action validates the
  canonical-state floor BEFORE any clock read or journal growth; the fold
  carries `contract_id` from the intent payload through the whole walk and
  replay.
- **`commercial/__init__.py` (evolved)** — the public surface exports the
  binding symbols (additive).

### 1.3 `allocation/` — the contract-bound economic allocation (harvest + re-bind)

- **`allocation/facts.py` (NEW)** — the M009 family-classified fact surface:
  the frozen `FactFamily` vocabulary (USAGE_FINAL / COMMERCIAL / SETTLEMENT /
  PAYMENT_PROVIDER), `FactReference` (one family-classified public read
  carrying the canonical `contract_id` binding member, validated when
  non-empty), `FactIndex` (the immutable fail-closed family-classified
  collection), `AllocationState` (the era name for the frozen
  `AllocationSubjectState` walk: PLANNED/SETTLED), `EconomicPolicy` (the era
  name for `PolicyVersion` — concept aliases, never a second state machine or
  policy model), and the canonical contract-id grammar citation.  This is the
  honest re-establishment of the W044-era import surface (`FactFamily`,
  `FactIndex`, `FactReference`, `AllocationState`, `EconomicPolicy`) on the
  M009 semantics.
- **`allocation/evidence.py` (evolved)** — `BillableUsageSnapshot` gained the
  `contract_id` binding member (optional DATA; fail-closed grammar validation
  when non-empty; serialized only when present; the unbound legacy citations
  of the M006 composition track stay constructible).
- **`allocation/__init__.py` (evolved)** — the public surface exports the fact
  symbols (additive).

### 1.4 `payment/` — the contract-citing settlement boundary (harvest + re-bind)

- **`payment/evidence.py` (evolved)** — `CommercialCitation` gained the
  `contract_id` binding member (optional DATA; fail-closed grammar validation
  when non-empty; serialized always): the commercial, usage-final, and
  allocation citations CARRY the canonical contract reference (LOCK-113) while
  the boundary keeps consuming the authorities' public projections — payment
  movement stays external (LOCK-113: the boundary never owns the contract, the
  usage account, or the allocation).
- **`payment/model.py` / `payment/validation.py` (evolved)** — the payout
  emission basis vocabulary re-based onto the CURRENT W053/M009 allocation
  states (PLANNED/SETTLED; the era "ALLOCATED" name mapped onto PLANNED — the
  immutable allocation snapshot exists).  The conservation and
  positive-billable gates are unchanged.

### 1.5 Batteries

- **`tools/payment_selftest.py` (RE-BASELINED)** — the DEC-0099-disclosed
  era-superseded battery re-established onto the delivered M009 surfaces:
  **44/44 PASS** (see §5).
- **`tools/eligibility_selftest.py` (RE-BASELINED)** — same disclosure class:
  **46/46 PASS** (see §5).
- **`tools/usage_selftest.py` (evolved)** — the API/import pins updated for
  the M009 surface; **4 new contract-binding cases** (construction validation,
  the canonical eligibility gate, the contract-bound golden run with
  round-trip binding preservation, the family surface): **53/53 PASS**
  (49 legacy + 4 M009).
- **`tools/commercial_selftest.py` (evolved)** — the vocabulary/API/import
  pins updated; **3 new bound-mode cases** (the binding gate, the contract-
  bound golden walk with replay binding preservation, the floor-gate
  semantics + the legacy-mode compatibility pin): **41/41 PASS** (38 legacy +
  3 M009).
- **`tools/allocation_selftest.py` (evolved)** — the API pin updated; **2 new
  contract-binding cases** (the bound usage facts + round-trip, the fact
  family surface): **62/62 PASS** (60 legacy + 2 M009).
- **`docs/M009-evidence.md`** — this record.

## 2. Harvest/re-bind classification (per the migration matrix)

| W051/W052/W053/W044-era element | Classification | Disposition |
|---|---|---|
| Usage account key (W051 transaction id) | RE-BIND | the account key IS the canonical contract citation (LOCK-113) |
| Usage evidence commercial snapshot (W051 state citation) | RE-BIND | `ContractCommercialSnapshot`: canonical contract state, validated vocabulary |
| Usage delivery-eligibility gate (W051 states) | RE-BIND | canonical contract states (EXECUTION_ACTIVE+ eligible; CONTRACT_ACTIVE = reservation) |
| W051 CommercialCore lifecycle (11-state walk) | REFACTOR | the contract-bound reconciliation account: canonical-state floors at every step; never ahead of the contract |
| W051 CommercialTransaction binding | RE-BIND | the `contract_id` member (canonical citation; immutable through the walk) |
| W051 unbound mode | RETAIN (compatibility) | the accepted M003 marketplace composition + the M006 composition-track consumers; their tracks own the later re-bases (disclosed) |
| W053 allocation over billable-final usage | RETAIN + RE-BIND | the current W053/M009 surface (typed evidence index); citations carry `contract_id` |
| W053 era states (ALLOCATED / PAYOUT_FAILED) | SUPERSEDED | PLANNED/SETTLED + append-only compensation records (the accepted W053 rewrite); the payout basis re-based |
| W044 payment boundary (adapter, sandbox, callbacks) | RETAIN | unchanged semantics; citations gain the contract binding DATA |
| W044-era usage import surface (EvidenceFamily et al.) | RE-ESTABLISH | the M009 family-classified citation semantics (usage/families.py) |
| W044-era allocation import surface (FactFamily et al.) | RE-ESTABLISH | the M009 family-classified citation semantics (allocation/facts.py) |
| W044-era usage lifecycle API (ingest_observation/reconcile/finalize_billable) | SUPERSEDED | the accepted W052 public API (observe_usage/seal_billable/…); the batteries' world composition evolved (disclosed) |

The matrix row "Commercial: REFACTOR → Contract/usage/settlement reference" is
satisfied by this translation: the W051 transaction model is refactored into
the contract-bound reconciliation account whose every citation — usage
records, settlement references, allocation facts, payment citations — carries
the canonical contract reference.

## 3. Judgment calls (invariant references)

1. **The re-bind is additive at the constructor seam.**  The bound mode
   (`contract_references=…`) is the M009 normative surface for the commercial
   track, but the unbound mode remains constructible because the ACCEPTED M003
   marketplace composition (`marketplace/`) and the M006 composition track
   (`composition/world.py`) construct `CommercialCore(store, clock, references)`
   with the three-argument form — both outside the M009 scope boundary.  The
   scope boundary (HARD: only `usage/ commercial/ allocation/ payment/` + the
   five batteries + this doc) forbids touching them, so the compatibility mode
   is retained and DISCLOSED here; their own tracks own the later re-bases.
   Within the M009 commercial track every battery runs bound.  LOCK-101/113.
2. **The usage account key IS the contract id.**  Under the M009 re-bind the
   usage ledger's account key (`transaction_id`) cites the canonical contract —
   the account is bound by construction (the evidence index carries
   contract-cited snapshots only in the bound batteries), and the admission
   gate resolves the contract citation through the index exactly like the W051
   citation it replaces.  The field NAME is retained (the frozen W052 journal
   schema and reason codes stay stable; `TRANSACTION_UNKNOWN` /
   `TRANSACTION_NOT_DELIVERING` keep their meaning: the cited commercial
   authority is not resolvable / not delivering); the SEMANTICS are the
   canonical binding.  LOCK-113.
3. **The era symbols are re-established where they genuinely map.**
   `EvidenceFamily`/`EvidenceIndex`/`EvidenceReference`/`UsageState` (usage)
   and `FactFamily`/`FactIndex`/`FactReference`/`AllocationState`/
   `EconomicPolicy` (allocation) carry M009 semantics — family-classified
   citations with the contract binding member, and concept aliases of the
   current frozen vocabularies — and are genuinely load-bearing in the
   re-baselined payment/eligibility batteries' world composition.  The era
   usage LIFECYCLE API (`ingest_observation`/`reconcile`/`finalize_billable`,
   the era `UsageLedger(evidence=…)` index parameter) is superseded by the
   accepted W052 public API: the batteries' world composition EVOLVED onto it
   (never faked).  This is the CI-guard discharging mechanism: the
   precondition guards in `.github/workflows/spec-check.yml` test
   `from usage import EvidenceFamily`; the surface now genuinely exists, so
   the payment/eligibility battery steps RUN again (the skip never triggers);
   the guard text itself is governance-plane material outside the M009 scope
   and is left untouched (disclosed).
4. **The compensated-allocation payout negative is honestly superseded.**  The
   W044-era case asserted that compensated-STATE allocation citations fail
   payout emission; the accepted W053 rewrite replaced compensated states with
   append-only compensation records (the account state stays SETTLED; the
   immutable snapshot split remains the emission basis), making the era
   negative structurally unrepresentable.  The re-baselined case pins the
   current-surface discipline: the compensated account keeps its immutable
   split and visible compensation record, and a REAL current-surface negative
   (a conservation-violating citation) fails closed `citation-state-invalid`.
   Payment case_19 discloses this in its case detail.  LOCK-113/118.
5. **The payout basis vocabulary is re-based, not widened.**  `payment/
   validation.py` and `payment/model.py` accepted the era states
   ("ALLOCATED"/"SETTLED"); the M009 re-base accepts the CURRENT W053/M009
   states ("PLANNED"/"SETTLED") — the era "ALLOCATED" maps onto PLANNED (the
   immutable allocation snapshot exists).  No gate is weakened: unknown
   citations, non-positive billables, and conservation violations still fail
   closed.
6. **Secrets and determinism carry over unchanged.**  The new modules import
   only stdlib value types + the canonical `contracts` domain (public
   vocabulary consumption; never instantiation) — the batteries' import
   disciplines evolve to admit exactly that (the M013 precedent), and every
   touched surface keeps injected instants, sorted iteration, canonical-JSON
   round-trips, and fail-closed typed errors.  LOCK-119.

## 4. Deterministic verification matrix

All runs offline; instants injected; no wall clock, no randomness, no UUIDs, no
network; PYTHONHASHSEED-safe (verified across processes and seeds).

| Verification | Result | Evidence |
|---|---|---|
| Usage: contract-cited snapshot construction (canonical id + state) | PASS | usage case_50 |
| Usage: grammar helpers; malformed citations fail closed | PASS | usage case_50 |
| Usage: canonical delivery-eligibility subsets cite CONTRACT_STATES | PASS | usage case_51 |
| Usage: CONTRACT_ACTIVE rejects delivered usage RESERVATION_NOT_USAGE | PASS | usage case_51 |
| Usage: INTENT rejects delivered usage TRANSACTION_NOT_DELIVERING | PASS | usage case_51 |
| Usage: contract-bound golden run (records cite the contract; sealed statement bound; round-trip preserves the binding) | PASS | usage case_52 |
| Usage: family surface (era symbols, contract binding member, fail-closed resolution, round-trip) | PASS | usage case_53 |
| Usage: the 49 legacy W052 cases (admission, kind tables, idempotency, tamper, recovery, determinism) | PASS | usage cases 01–49 |
| Commercial: citation model + floor table coverage + floor/terminal gates | PASS | commercial case_39 |
| Commercial: bound golden walk (citation at every step; full walk settles; replay preserves the binding) | PASS | commercial case_40 |
| Commercial: bound submit_intent without/with unknown citation fails CONTRACT_UNKNOWN | PASS | commercial case_40 |
| Commercial: floor violation through the real admission path (zero journal growth) | PASS | commercial case_41 |
| Commercial: the unbound legacy mode stays constructible (disclosed compatibility) | PASS | commercial case_41 |
| Commercial: a bound core refuses to continue unbound (recovered legacy) transactions | PASS | commercial case_41 |
| Commercial: the 38 legacy W051 cases (lifecycle, compensations, settlement integrity, tamper, determinism) | PASS | commercial cases 01–38 |
| Allocation: contract-bound billable-final facts (binding member; round-trip; malformed fail-closed; legacy unbound constructible) | PASS | allocation case_61 |
| Allocation: fact family surface (era symbols; allocation-creating family; fail-closed; round-trip) | PASS | allocation case_62 |
| Allocation: the 60 legacy W053 cases (split conservation, policy versions, callbacks, tamper, determinism) | PASS | allocation cases 01–60 |
| Payment (RE-BASELINE): frozen vocabularies incl. the re-based payout basis | PASS | payment case_01 |
| Payment: citation snapshot (contract-bound citations; fail-closed resolution) | PASS | payment case_06 |
| Payment: full golden lifecycle over the contract-bound world (pinned digest re-pinned honestly) | PASS | payment case_07 |
| Payment: every legal/illegal transition over the re-baselined world | PASS | payment cases 08–09 |
| Payment: intent create/retrieve, duplicates, conflicts, provider references | PASS | payment cases 10–14 |
| Payment: authorize/capture/refund/reversal/payout/callback flows | PASS | payment cases 15–22 |
| Payment: provider failures, reconciliation, capability gates | PASS | payment cases 23–26 |
| Payment: the seven negative proofs (payment-never-usage; callbacks-never-delivery; history-never-rewritten; no vendor leakage; import discipline; API stability; store failures) | PASS | payment cases 27–32, 42 |
| Payment: journal-first recovery, restart replay, two-run + PYTHONHASHSEED determinism, clock discipline | PASS | payment cases 33–37 |
| Payment: scope audit (authorization-aware: R7-CORE-001 + the M009 child scope) | PASS | payment case_38 |
| Payment: closed-loop composition (the canonical contract cited at every step; payment DATA cited by REAL W053/W051 records; payment DATA never justifies settlement) | PASS | payment case_40 |
| Payment: open usage stays open; deep immutable projections | PASS | payment cases 43–44 |
| Eligibility (RE-BASELINE): citation snapshot over the contract-bound world | PASS | eligibility case_07 |
| Eligibility: golden lifecycle (pinned digest re-pinned honestly) | PASS | eligibility case_08 |
| Eligibility: the full W045 case set (declarations, conferral, offers, devices, payment independence, KYC-reference-only, jurisdiction, tamper, recovery, determinism, scope, closed loop, atomic admission, lifecycle counts) | PASS | eligibility cases 01–46 |
| contract battery untouched and green | PASS | contract_selftest 54/54 |
| Full blocking suite in the exact workflow order | PASS | all batteries green locally; the sole remaining skip is the DEC-0099-disclosed client battery (containment surface gone — M014 track) |

**Battery results: usage 53/53 · commercial 41/41 · allocation 62/62 ·
payment 44/44 · eligibility 46/46 · contract 54/54; the full blocking battery
suite green on the delivery head (3 consecutive runs).**

## 5. Battery re-baseline disclosure (the DEC-0099 discharge)

The DEC-0099 disclosure recorded that `tools/payment_selftest.py` and
`tools/eligibility_selftest.py` skip behind CI precondition guards because
their W044-era import surfaces (`from usage import EvidenceFamily` etc.) were
gone (the accepted W052 usage rewrite).  The M009 delivery re-establishes the
surfaces they need and re-baselines both batteries onto the delivered M009
surfaces — the guards' conditions are now genuinely TRUE, so the CI steps RUN
the batteries again (the guard text in `.github/workflows/spec-check.yml` is
control-plane material outside the M009 scope and is untouched; a governance
change may retire the now-dead guards later):

- **Re-established**: the import surfaces — `EvidenceFamily`, `EvidenceIndex`,
  `EvidenceReference`, `UsageState` (usage) and `FactFamily`, `FactIndex`,
  `FactReference`, `AllocationState`, `EconomicPolicy` (allocation) — now
  genuinely exist on the M009 family-classified citation semantics and are
  load-bearing in both batteries' world composition.
- **Evolved (superseded era semantics, never faked)**: the era usage lifecycle
  API (`ingest_observation`/`reconcile`/`finalize_billable`, the
  `UsageLedger(evidence=…)` parameter) → the accepted W052 public API
  (`observe_usage`/`seal_billable` over the typed `evidence_index`); the era
  allocation API (`facts=FactIndex`, `register_policy(policy_id=, version=, …)`,
  `allocate(usage_record_id=, …)`, `acknowledge_settlement(settlement_refs=)`,
  `compensate_payout_failure(usage_record_id=)`) → the current W053/M009
  public API (`evidence_index=AllocationEvidenceIndex`,
  terms-derived `register_policy`, `allocate(usage_transaction_id=, …)`,
  `acknowledge_settlement(settlement_reference=)`,
  `record_payment_reference` + `record_payout_failure`); the era
  compensated-STATE payout negative → the current append-only compensation
  semantics plus a real conservation negative; the usage account keys and the
  allocation account key → the canonical contract id (LOCK-113); the world
  composition drives the REAL canonical contract (M002 public surface) with
  the contract walked ahead of every commercial step.
- **Stayed skipped and why**: the `client` battery (`tools/client_selftest.py`)
  — untouched per the charter (W048 accepted-not-restored; the containment
  guard still fails; M014 track material).  It is the only remaining tolerated
  skip.
- **Honest re-pins**: the golden digest pins of both re-baselined batteries
  (`_GOLDEN_STREAM_SHA256` in payment, `_GOLDEN_STREAM_SHA` in eligibility)
  were re-pinned once after the world re-composition — the digests are
  byte-identical across runs, hash seeds, and replays on the new pins (the
  determinism cases verify exactly that).

## 6. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the commercial track consumes the
  canonical domain through its public surface only (vocabulary + identity
  grammar imports; no instantiation, no mutation, no duplication); the
  contract battery stays 54/54 on this delivery head.
- **LOCK-104/105 (provider sovereignty / no global topology):** no topology
  or routing surface anywhere in the delta; the re-bind touches commercial
  semantics only.
- **LOCK-108 (no silent weakening):** the contract-state floors only
  STRENGTHEN the commercial walk (it may never run ahead of the contract); no
  constraint-mutating surface was added.
- **LOCK-113 (commercial separation):** usage records and settlement
  references carry canonical contract references — the usage account key, the
  commercial transaction binding, the allocation citations, and the payment
  citations all cite the canonical contract; payment movement stays external
  (the payment boundary records references only; no payment execution
  authority entered any core); no commercial authority migrated into any
  networking domain (the delta touches no connectivity/networking code).
- **LOCK-117 (authority uniqueness):** the canonical contract is the sole
  authority; the W051 transaction model is refactored into a mirroring
  reconciliation account bounded by the contract's state floors; no second
  contract model is introduced anywhere.
- **LOCK-118 (provenance):** every citation and binding carries provenance
  labels naming the public surface it was read from.
- **LOCK-119 (secrets):** no secret material anywhere in the delta; the
  batteries' secret-hygiene cases stay green.

## 7. Out-of-scope discipline (nothing else changed)

The M009 delta contains only the files listed in §1 (18 implementation files
plus the 5 batteries and this record).  No control-plane surface, no `spec/`
file, no `.github/` file, no `contracts/` file (consumed, never modified), no
other domain or battery (`tools/client_selftest.py` untouched — M014 track),
no W048 material (containment/sharing), no historical record.  The drift guard
classifies the delta implementation-only; the provenance gate verifies full
coverage by R7-CORE-001's declared scope (byte-identical authorization
inheritance from main).

## 8. Evidence classes (honest disclosure)

- All M009 acceptance criteria: **SOFTWARE** class (deterministic offline
  batteries; usage 53/53, commercial 41/41, allocation 62/62, payment 44/44,
  eligibility 46/46, contract 54/54 on the delivery head; the full blocking
  suite green).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M009 creates and closes
  none; EVID-002..EVID-008 remain open and untouched.  No SOFTWARE evidence is
  converted into PHYSICAL PASS anywhere in this delivery.

## 9. Delivery provenance

- Branch: `m009-usage-commercial` from the main head `9e16cb0` (which descends
  from the R7-CORE-001 activation baseline `1e5c55f`); append-only commits.
- Batteries on the delivery head: `usage_selftest` 53/53, `commercial_selftest`
  41/41, `allocation_selftest` 62/62, `payment_selftest` 44/44,
  `eligibility_selftest` 46/46 — green on 3 consecutive runs each
  (exit-code-based verification).
- `contract_selftest` 54/54 on the delivery head (the canonical authority
  untouched).
- Gates: `current_spec_check`, `tech_lead_guard`, `architecture_drift_guard`
  (implementation-only, 21 files), `fresh_session_check --actual-main-sha`,
  `authorization_provenance`, `experience_check` PASS on the delivery head.
- Full suite: the entire blocking battery set green on the delivery head in
  the exact `.github/workflows/spec-check.yml` order; the sole remaining
  tolerated skip is the DEC-0099-disclosed client battery (containment surface
  gone — M014 track).  The payment and eligibility batteries RUN again (the
  DEC-0099 skip guards' conditions are genuinely satisfied).
