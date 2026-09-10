# M005 — Evidence and Assurance — Evidence Record

**Work Item:** M005 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7 program
authorization; M005 is a charter child under the active program authorization)
**Baseline:** `45b71dd6b1f1cc0b48f861681f1353dc78872fd2` (the live main head at re-root — the DEC-0112-accepted M012 state, per the live-main rule and the M011 delivery precedent; the delivery commit replays cleanly with zero file overlap with the M012 acceptance delta)

This record persists the verified facts of the M005 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule).

## 1. Delivered surface

- **`evidence/` (NEW)** — the typed evidence-record domain (frozen 1.1 §9 closed-loop
  evidence base; LOCK-106; the R7 charter M005 scope):
  - `evidence/model.py` — the four DISTINCT typed records: `ClaimEvidence`
    (an assertion a producer makes without measuring; required integer confidence in
    basis points), `ObservationEvidence` (a measured value with an explicit validity
    window — `freshness_until` strictly after `instant`; staleness is DERIVED at
    evaluation time, never stored fresh; required integer confidence),
    `CommitmentEvidence` (a forward-looking promise over an explicit two-sided
    `valid_from`..`valid_until` window; DATA about a promise, never an authority —
    LOCK-117), `AttestationEvidence` (a third-party certification with its own
    validity boundary; the attestor IS the producer — LOCK-118). Type distinction is
    STRUCTURAL (different payload field sets; the `record_type` member is fixed per
    class; `from_dict` rejects a payload whose `record_type` does not match the
    class — no type confusion, no untyped evidence). Every record carries the
    LOCK-118 provenance envelope: subject reference, canonical contract reference,
    injected RFC 3339 UTC production instant, producer identity, confidence where
    applicable, plus opaque lineage `source_refs`. Identity is content-derived
    (SHA-256 over the canonical JSON of the record minus the id, per-type id
    namespaces) — tamper-evident at construction AND deserialization. Fail-closed
    typed validation everywhere (reference grammar, integer-only values, basis-point
    confidence scale, frozen per-kind vocabularies, LOCK-119 secret-shaped rejection
    at construction and deserialization); raw exception text never enters typed
    error details.
  - `evidence/store.py` — `EvidenceStore`: the append-only, idempotent,
    immutable evidence store (no update/delete path; a different record under a
    retained id is RECORD_TAMPER; a byte-identical duplicate is a no-op);
    construction-is-recovery JSONL persistence with an idempotent re-fold; per-line
    LOCK-119 secret scanning on persist AND on load; sorted record-id iteration
    (PYTHONHASHSEED-safe); contract-scoped reads; fail-closed unknown-id reads.
  - `evidence/telemetry_seam.py` — the single explicit, disclosed, one-directional
    harvest seam (classification matrix: Telemetry RETAIN → Assurance evidence):
    `telemetry_observation_to_evidence` translates one
    `telemetry.TelemetryObservation` into one typed `ObservationEvidence`
    (field mapping complete and disclosed: observing node → producer, observation id
    → lineage `source_refs`, validity window verbatim; the CONTRACT reference is
    injected by the CALLER — raw operational measurements never carry contract
    identity, LOCK-101). The seam never mutates the telemetry record, never writes
    telemetry state, and there is NO reverse translation (evidence is not a
    measurement authority). Fail-closed and typed: non-observation input, an
    untranslatable metric, or a malformed contract reference raise `EvidenceError`
    with stable reason codes.
  - `evidence/errors.py` — the frozen `evidence-*` typed reason vocabulary
    (`EvidenceError` with stable `code`/`detail`; adding a code is a deliberate
    vocabulary change).
  - `evidence/__init__.py` — the additive public surface with the authority
    boundary documented in the package docstring.
- **`assurance/` (NEW)** — the contract-level closed-loop assurance evaluation domain
  (LOCK-107):
  - `assurance/model.py` — the FROZEN §9 assurance state vocabulary
    `ASSURANCE_STATES` = exactly (compliant, degraded, violated, unknown (stale/absent
    evidence), failed, deliberately_terminated — no state outside it ever leaves the
    evaluation); `AssuranceObligation` (the typed obligation record: one obligation
    kind per LOCK-106 evidence type — observation-bound / claim-level /
    commitment-window / attestation-required; optional value bound (floor/ceiling);
    hard/degradable severity; optional evidence deadline; LOCK-118 producer and
    lineage; content-derived tamper-evident id, contract-AGNOSTIC by design — the
    contract's opaque reference is the binding, LOCK-117);
    `AssuranceReason`/`AssuranceEvaluation` (the typed, deterministic evaluation
    outcome: breach reasons reference the specific obligation AND the triggering
    evidence — or the evidence ABSENCE — with stable machine-readable details; the
    evaluation id is content-derived over the canonical result);
    `to_contract_references`/`resolve_obligations` (the fail-closed 1:1 binding
    between the canonical contract's opaque `assurance-obligation` references and the
    typed obligations — unresolved contract references and unreferenced obligations
    both fail closed; there is no second contract model);
    `evaluate_contract` (the PURE evaluation kernel: same (contract, obligations,
    evidence, injected instant) → byte-identical state, reasons and evaluation id;
    contract-state dispatch — TERMINATED → deliberately_terminated and FAILED →
    failed short-circuits with NO re-evaluation and NO side effects, the §9
    assurance-evaluable lifecycle states evaluate, everything else fails closed
    NOT_EVALUABLE; per-obligation typed evidence matching with the evidence TYPE
    part of the match (no cross-type satisfaction), contract scoping by the evidence
    records' own contract references, NO TIME TRAVEL (records produced after the
    evaluation instant are ignored), per-kind eligibility at the injected instant
    (freshness window / commitment window / attestation validity; claims carry no
    expiry), latest-evidence-wins (max by (instant, record_id) — an older satisfying
    record never masks a newer breach), deadline absence-breaches (the evidence
    ABSENCE triggers the breach at the obligation severity), worst-of aggregation
    violated > degraded > unknown > compliant; import-time consistency guards against
    contract-vocabulary drift).
  - `assurance/journal.py` — `AssuranceJournal`: the append-only, idempotent
    evaluation-history journal (construction-is-recovery persistence; tampered
    duplicate evaluations fail closed; LOCK-119 per-line secret scanning; sorted
    (evaluated_at, evaluation_id) iteration; latest-per-contract closed-loop query
    surface, fail-closed when never evaluated).
  - `assurance/bridge.py` — the sole, explicit recording path back into the accepted
    `contracts/` domain through its OWN frozen M002 command vocabulary (consumed,
    never extended): compliant → `RecordAssurance("compliant")`, degraded →
    `RecordAssurance("degraded")`, violated → `RecordAssurance("violated")`,
    unknown → `RecordAssurance("unknown-stale")` (the consumed four-state recorded
    vocabulary); failed / deliberately_terminated → NO command (terminal contracts
    reject all commands — the honest no-op with an explicit result, never a silent
    write attempt). The evaluation id rides the command's `decision`-kinded evidence
    reference with provenance (LOCK-117/118). Bridging a contract outside the
    assurance-recordable lifecycle states raises BRIDGE_NOT_APPLICABLE before any
    submission; genuine contract-authority errors propagate unchanged (the contract
    store stays the sole writer of contract state — LOCK-101). Import-time
    consistency guard: the mapping is closed against the CONSUMED contracts
    vocabularies.
  - `assurance/errors.py` — the frozen `assurance-*` typed reason vocabulary.
  - `assurance/__init__.py` — the additive public surface.
- **`telemetry/` (HARVEST — disclosed, BYTE-IDENTICAL)** — migration classification:
  Telemetry RETAIN → Assurance evidence. Telemetry stays the owner of raw
  operational measurement: the package is **byte-identical to origin/main**
  (pure RETAIN — the strongest preservation of its frozen surface: the privacy
  fence, the policy-gated topology-promotion semantics, and the public API
  surface consumed by the existing batteries (`telemetry.model`,
  `telemetry.store`, `telemetry.serialization`, the package `__init__`
  re-exports) are untouched by construction — verified in the M005 battery
  (the tracked telemetry delta vs origin/main is EMPTY). `telemetry/`
  imports no evidence/assurance API and gains no evidence responsibility; the
  seam lives in `evidence/` (the M005 authority). The harvest disclosure
  lives HERE (this record), in the seam module's own docstring, and in the
  disclosed `tools/telemetry_selftest.py` case_19 amendment (below). The
  `telemetry_selftest.py` battery re-runs at 34/34 PASS on the delivery head
  with its single disclosed change: the case_19 DAG-sanctioned-consumer
  amendment for the `evidence` family (the same allowlist pattern as the six
  precedents — energy/upgrade/management/simulator/agent/edge — pinned to
  the telemetry DATA surface `telemetry.model` only).
- **`tools/assurance_selftest.py` (NEW)** — the M005 battery: **97/97 PASS**.
- **`docs/M005-evidence.md`** — this record.

## 2. Deterministic verification matrix

All runs offline; instants injected (T0-style constants); no wall clock, no
randomness, no UUIDs, no network; no real sockets; no secrets stored (LOCK-119);
PYTHONHASHSEED-safe (verified across processes and seeds). Exit-code-based
verification (a traceback or lowercase "failed" IS a failure).

| Verification | Result | Evidence |
|---|---|---|
| LOCK-106 type vocabulary frozen (4 distinct types + per-kind name sets) | PASS | case_01 |
| Four types STRUCTURALLY distinct (payload sets; confidence only where probabilistic) | PASS | case_02 |
| No type confusion (12 cross-type `from_dict` rejections + unknown/untyped dispatch) | PASS | case_03 (14 sub-cases) |
| Canonical-JSON round-trips (all four types byte-identical, both directions) | PASS | case_04 |
| LOCK-118 provenance envelope (subject/contract/instant/producer/confidence + lineage) | PASS | case_05 |
| Content-derived ids (deterministic, per-type namespaces, re-derivation agrees) | PASS | case_06 |
| Tamper evidence (retained-id mutation rejected for all four types) | PASS | case_07 (4 sub-cases) |
| Malformed input fail-closed (13 typed sub-cases: empties, bool/float as int, confidence overflow, invalid instants, inverted windows, vocabulary, secret-shaped; no raw exception text) | PASS | case_08a-m |
| Store append-only + idempotent (duplicate no-op; tampered duplicate; untyped ingest rejected) | PASS | case_09a-d |
| Persistence recovery (JSONL fold byte-identical; replay idempotent; corrupted line and secret line fail closed on re-fold) | PASS | case_10 |
| Store reads (sorted iteration; contract scoping; unknown-id and empty-ref fail closed) | PASS | case_11 |
| Structural immutability (frozen dataclasses; no mutation API; append-only persistence) | PASS | case_12 |
| Harvest seam translation complete (field mapping, determinism, non-mutation, ingestable, disclosed) | PASS | case_13 |
| Harvest seam fail-closed (non-observation input; untranslatable metric; missing caller contract binding) | PASS | case_14a-d |
| Seam vocabulary cross-check (OBSERVATION_METRICS == the frozen telemetry metric registry, 18 names) | PASS | case_15 |
| Telemetry surface unchanged (no evidence/assurance import; telemetry/ BYTE-IDENTICAL to origin/main — pure RETAIN) | PASS | case_16 |
| Obligation records typed (frozen vocabularies; bound pair; per-kind name vocabulary; tamper; round-trip) | PASS | case_17a-f |
| Contract binding by reference (opaque `assurance-obligation` references; deterministic 1:1 resolution; unresolved/not-referenced/non-contract fail closed) | PASS | case_18a-e |
| Evaluation inputs fail closed (non-contract; untyped evidence; invalid instant; pre-activation NOT_EVALUABLE) | PASS | case_19a-d |
| No second contract model (evidence/ imports no contracts API; contracts/ byte-identical to main; bridge is the sole submit path; no in-place contract mutation) | PASS | case_20a-d |
| §9 state vocabulary frozen (exactly the six states; reason kinds; evaluable states) | PASS | case_21 |
| `compliant` reachable (4/4 satisfied reasons cite obligation + evidence; canonical evaluation bytes) | PASS | case_22 |
| `violated` reachable (hard value-breach cites obligation + the triggering evidence record) | PASS | case_23 |
| `degraded` reachable (degradable value-breach AND degradable deadline absence-breach) | PASS | case_24a-b |
| `unknown` reachable (stale window; absent evidence; missing evidence never aggregates to compliant) | PASS | case_25a-c |
| `failed` reachable (FAILED contract short-circuits, no re-evaluation) | PASS | case_26 |
| `deliberately_terminated` reachable (TERMINATED short-circuit; verdict evidence-immune, same evaluation id under different evidence) | PASS | case_27 |
| Instant-threshold staleness (SAME evidence set fresh at T2, stale at T3 — injected instants only) | PASS | case_28 |
| Deadline absence-breach (pre-deadline absence is honest unknown; post-deadline absence breaches citing the ABSENCE) | PASS | case_29 |
| Latest-evidence-wins (newer breach over older satisfaction AND newer satisfaction over older breach) | PASS | case_30 |
| No time travel (records produced after the evaluation instant ignored entirely) | PASS | case_31 |
| Contract scoping + type-strict matching (foreign-contract evidence ignored; a claim never satisfies an observation-bound obligation) | PASS | case_32 |
| Per-kind eligibility (expired commitment/attestation stale; claim exempt by design) | PASS | case_33 |
| Deterministic replay (same inputs → byte-identical evaluation; input order independent; reasons in obligation-id order) | PASS | case_34 |
| Journal idempotent recovery (duplicate no-op; tampered evaluation; secret line; re-fold digest; fail-closed queries) | PASS | case_35 |
| Bridge mapping frozen (closed mapping onto the consumed contracts vocabulary; unknown → unknown-stale; recordable states derived from the frozen M002 transition table) | PASS | case_36 |
| Bridge closed loop (decision reference carries the evaluation id + provenance; DELIVERY → ASSURED; violated → contract FAILED with constraint-violated termination reason) | PASS | case_37 |
| Bridge terminal no-op (failed/deliberately_terminated build NO command; no write attempt; state untouched) | PASS | case_38 |
| Bridge not applicable (non-recordable lifecycle states fail closed BEFORE submission; contract unchanged) | PASS | case_39 |
| Clock discipline (no wall clock/randomness/UUIDs/network constructs in evidence/ + assurance/) | PASS | case_40 |
| Import discipline (AST-audited stdlib allowlist; evidence/ imports no contracts/assurance; telemetry imported ONLY by the seam module) | PASS | case_41 |
| Lock conformance mapping (LOCK-101/106/107/113/117/118/119 evidenced on the closed loop; no payment vocabulary) | PASS | case_42 |
| Cross-process determinism (byte-identical store digest, journal digest and evaluation id across PYTHONHASHSEED 0/1/42) | PASS | case_43 |
| PR delta shape (authorization-aware consultation: every delta file covered by the ACTIVE R7-CORE-001 scope; no spec/ or .github/ touch) | PASS | case_44 |
| Evidence doc honesty (SOFTWARE class disclosed; lock mapping disclosed; no affirmative physical claims) | PASS | case_45 |

**Battery result: PASS (97/97 cases), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `evidence/` imports NO contracts API (the
  evidence domain is typed DATA, contract-agnostic); `assurance/` consumes
  `contracts/` by reference (imports the frozen public surface only) and
  `contracts/` is byte-identical to the baseline in this delivery (verified in the
  battery); the bridge is the ONLY path that writes contract state, through the
  contract's own `RecordAssurance` command vocabulary — the contract store stays
  the sole writer.
- **LOCK-106 (evidence typing):** claim, observation, commitment and attestation
  are DISTINCT typed records with structurally distinct payloads, per-class fixed
  `record_type`, fail-closed type dispatch, no untyped ingest path, and the
  evidence TYPE is part of obligation matching (no cross-type satisfaction).
- **LOCK-107 (closed-loop assurance):** ACTIVE canonical contracts are evaluated
  against their obligations on demand, deterministically and reproducibly
  ((contract, obligation set, evidence set, injected instant) → state + typed
  reasons + content-derived evaluation id); the evaluation journal is the durable
  trail; the bridge closes the loop back into the contract; terminal states
  short-circuit honestly without re-evaluation or side effects.
- **LOCK-108 (no silent contract weakening):** the assurance bridge records
  verdicts only (the frozen four-state recorded vocabulary); a `violated` verdict
  FAILS the contract (constraint-violated) rather than weakening anything; hard
  constraints are never touched by the assurance domain.
- **LOCK-113 (commercial separation):** no payment/charge/settle/invoice
  vocabulary exists in `evidence/` or `assurance/` (battery-audited); usage and
  pricing terms stay contract-domain material the evaluation never interprets.
- **LOCK-117 (authority uniqueness):** obligations ride contracts as OPAQUE
  `assurance-obligation` references (the contract alone decides WHICH obligations
  apply; the assurance authority alone owns their SEMANTICS — no second contract
  or obligation model); an evidence record asserts, never authorizes; evaluation
  ids ride the bridge as `decision` references; execution artifacts are never
  consulted.
- **LOCK-118 (provenance):** every evidence record carries subject reference,
  contract reference, production instant, producer identity and applicable
  confidence; the attestor is the producer; the seam maps the observing node to
  the producer and the telemetry observation id to lineage `source_refs`; bridge
  decision references carry provenance.
- **LOCK-119 (secrets):** secret-shaped labels and values are rejected at
  construction and deserialization in both domains; every persisted journal line
  (evidence store and assurance journal) is secret-scanned on write AND on load.
- **LOCK-115 (simple-system validity):** a single contract with one obligation and
  one evidence record evaluates, journals and bridges completely — no federation,
  multipath, or global services are required (exercised in fixtures throughout).

## 4. Out-of-scope discipline (nothing else changed)

The M005 delta contains only: `evidence/` (new), `assurance/` (new),
`tools/assurance_selftest.py` (new), `tools/telemetry_selftest.py` (the single
disclosed case_19 DAG-sanctioned-consumer amendment for the `evidence` family —
the six-precedent allowlist pattern, pinned to `telemetry.model` only), and
`docs/M005-evidence.md` (this record). `telemetry/` itself is byte-identical to
origin/main (pure RETAIN). No control-plane surface, no spec/ file, no
`.github/` file, no protocol schema, no `contracts/` modification (the M002
canonical domain is consumed, never modified), no W048 material
(containment/sharing), no pilot/ surface, and no historical record is touched. The
drift guard classifies the delta implementation-only; the provenance gate verifies
full coverage by R7-CORE-001 (assurance/, evidence/, telemetry/, tools/ and
docs/M005-evidence.md are all declared M005 scope entries).

Note (honest limitation, the M003 precedent): the CI workflow does not yet run
`tools/assurance_selftest.py` — wiring a new battery step into `.github/` is a
control-plane change outside this implementation PR's boundary. The battery runs
locally on the delivery head (97/97 ×3, exit-code-based) and is the SOFTWARE
evidence for this delivery; CI wiring is a Tech Lead/governance action at
acceptance time (the M010/M011 precedent: their battery steps landed with the
respective acceptance governance commits).

## 5. Evidence classes (honest disclosure)

- All M005 acceptance criteria: **SOFTWARE** class (deterministic offline battery,
  97/97 PASS on the delivery head; every blocking battery and governance gate in
  the CI suite green on the delivery head — the one non-green step, the legacy
  `spec_check.py` compatibility audit, is `continue-on-error: true` in the CI
  workflow, fails identically on the pre-delivery baseline, and is structurally
  superseded by the `authorization_provenance.py` gate, which PASSES).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M005 creates and closes none;
  EVID-002..EVID-008 remain open and untouched, and no evidence produced by this
  delivery is physical, production, or live-service evidence. No SOFTWARE evidence
  is converted into PHYSICAL PASS.

## 6. Delivery provenance

- Branch: `m005-assurance`, re-rooted onto the live main head `45b71dd` (the
  DEC-0112-accepted M012 state) per the live-main rule — the M011 delivery
  precedent; the single delivery commit replays cleanly (zero file overlap with
  the M012 acceptance delta).
- Battery: `python3 tools/assurance_selftest.py` → PASS (97/97) on the re-rooted
  delivery head.
- Full suite: every battery the CI workflow runs, in exact workflow order, on the
  re-rooted delivery head with exit-code-based detection: 64 PASS (66 steps,
  including the M012-era `comos_selftest` now on main — 33/33), 1 disclosed skip
  (client
  battery existence guard, DEC-0099), and the single non-green step is the legacy
  `spec_check.py` compatibility audit (rc=1; `continue-on-error: true` in CI — it
  cannot see the R7 program authorization by frozen construction and fails
  identically on the pre-delivery baseline; the active-era successor gate
  `authorization_provenance.py` PASSES). `telemetry_selftest.py`
  re-runs 34/34 with its single disclosed case_19 amendment (the harvested
  domain is byte-identical and intact);
  `contract_selftest.py` still 54/54 (the M002 canonical domain is unmodified and
  consumed by reference only); `payment_selftest.py` 44/44 (its frozen
  scope/sibling audits stay unmodified and pass — telemetry is byte-identical,
  so no accepted authority family changed); the accepted sibling batteries
  (`sharenet` 33/33, `roamlink` 56/56, `comos` 33/33) green at this head.
- Governance gates on the re-rooted delivery head: `authorization_provenance.py`
  PASS (13/13 delta files covered by R7-CORE-001, byte-identical authorization
  inheritance from origin/main), `current_spec_check.py` PASS,
  `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha 45b71dd` PASS.
