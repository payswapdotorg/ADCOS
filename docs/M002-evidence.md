# M002 — Connectivity Contract Core — Evidence Record

**Work Item:** M002 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7 program
authorization; M002 is the charter's current child)
**Baseline:** `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (activation baseline)

This record persists the verified facts of the M002 delivery. Every claim below was
reproduced against the live repository by the sole Architect/Tech Lead — no worker
report is trusted without direct verification (Tech Lead handoff, non-negotiable rule).

## 1. Delivered surface

- `contracts/` — the canonical ConnectivityContract domain package:
  - `contracts/model.py` — the frozen 1.1 §3 field set on `ConnectivityContract`
    (contract identity; principal and beneficiary scope; normalized requirements as
    opaque references; accepted offer references; hard constraints; committed service
    properties; validity interval; usage and pricing terms as an opaque commercial
    reference; assurance obligations; permitted execution scope; termination and
    compensation rules; provenance; signature references), the contract-level
    lifecycle state machine (frozen 1.1 §11 reference lifecycle plus the §9 degraded
    and terminal states, with an exhaustive legal-transition table), the
    command vocabulary (17 kinds), the contract-scoped lease model
    (grant/renew/revoke/expire with an audit trail), and the pure lifecycle kernel
    (`apply_command` / `build_contract`).
  - `contracts/store.py` — the deterministic fold over an append-only command
    journal (construction-is-recovery; JSONL persistence with fsync; idempotent
    duplicates; replay-stale / sequence-conflict / sequence-gap fail-closed; secret
    scanning on every persisted line; thread-safe).
  - `contracts/__init__.py` — the public surface.
- `tools/contract_selftest.py` — the M002 battery (54 deterministic cases).
- `tools/*_selftest.py` (battery-scope consultation repairs) — the delta-shape and
  frozen-surface cases across the battery suite now consult the ACTIVE
  repository-local authorization scope (`tools/authorization_provenance.py`,
  `active_authorization()`/`covers()`), exactly discharging the duty pre-recorded in
  `docs/M001-evidence.md` §4 for the post-M001 implementation era. Historical
  per-battery scopes remain in force for paths the active authorization does not
  cover; fail-closed behavior is preserved (no unique active authorization ⇒
  nothing is covered).
- `docs/M002-evidence.md` — this record.

## 2. Deterministic verification matrix

All runs offline; instants injected; no wall clock, no randomness, no UUIDs, no
network; PYTHONHASHSEED-safe (verified across processes and seeds).

| Verification | Result | Evidence |
|---|---|---|
| Canonical field set (frozen 1.1 §3) | PASS | case_01: every §3 field present on the record |
| Principal vocabulary frozen (1.1 §4) | PASS | case_02: 8 kinds; unknown kinds fail closed |
| Reference-kind authority boundary | PASS | case_03: non-vocabulary kinds rejected |
| Construction validation fail-closed | PASS | case_04a-h: empty core, bad instants, bad vocabularies, wrong kinds |
| Canonical round-trips | PASS | case_09: serialize→JSON→deserialize byte-stable |
| Content-derived ids | PASS | case_10: deterministic, collision-free, sha256 grammar |
| Tamper evidence (records) | PASS | case_11: mutated constraints/leases fail the derived identity |
| Tamper evidence (journal) | PASS | case_12: mutated journal lines fail closed at load |
| Full §11 reference lifecycle | PASS | case_13: INTENT→…→SETTLED terminal |
| Transition legality (exhaustive) | PASS | case_14: every illegal transition fails closed across all 13 states |
| Offers bind once | PASS | case_15 |
| Activation preconditions | PASS | case_16a-d: offers/signatures/validity window |
| Termination declared-conditions-only | PASS | case_17 |
| Assurance honesty (1.1 §9) | PASS | case_18a-d: unknown-stale never advances; violated→FAILED; degraded explicit and recoverable |
| Terminal rejects commands | PASS | case_19 |
| LOCK-108 structural immutability | PASS | case_20: no constraint-mutating command exists; fingerprint stable across the lifecycle |
| LOCK-117 artifacts are data | PASS | case_21: binding artifacts never changes identity or state |
| No artifact-authority API | PASS | case_22 |
| Wrong reference kinds rejected | PASS | case_23 |
| Supersession = new contract | PASS | case_24: explicit chain link; predecessor untouched (no silent weakening) |
| Lease scoped to contract | PASS | case_25 |
| Lease window ⊆ validity | PASS | case_26 |
| Lease renewal audit trail | PASS | case_27: successor lease; predecessor renewed; activation promotes granted leases |
| Lease expiry determinism | PASS | case_28: pure function of the injected instant; early expiry fails closed |
| Contract expiry | PASS | case_29: not-due→due→EXPIRED terminal; post-expiry commands rejected |
| Expiry requires past validity | PASS | case_30 |
| Duplicate idempotency | PASS | case_31: exact retries are journal no-ops |
| Journal discipline | PASS | case_32a-c: gap / replay-stale / sequence-conflict fail closed |
| Persistence recovery | PASS | case_33: byte-identical fold from the JSONL journal; resume at the next slot |
| Cross-process determinism | PASS | case_34: identical digest across PYTHONHASHSEED 0/1/12345 and processes |
| Sorted iteration | PASS | case_35 |
| Clock discipline | PASS | case_36: no wall clock/randomness/UUIDs in contracts/ |
| LOCK-118 provenance | PASS | case_37: issuer + provenance on external material |
| LOCK-119 secrets | PASS | case_38a-c: secret labels/values rejected at construction; journal lines scanned |
| LOCK-113 commercial boundary | PASS | case_39: commercial material stays an opaque external reference |
| Vocabulary freeze | PASS | case_40: state/assurance/lease vocabularies byte-frozen |
| Lock conformance mapping | PASS | case_41: LOCK-101/102/103/108/113/117/118 evidenced |

**Battery result: PASS (54/54 cases).**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `ConnectivityContract` is the sole durable
  authority for acquired connectivity; the store is its only writer.
- **LOCK-102 (intent independence):** requirements ride as opaque
  `intent-requirements` references; the model never interprets intent.
- **LOCK-103 (application purchasing):** APPLICATION principals sponsor bounded
  DEVICE/USER beneficiaries through reference-only scope.
- **LOCK-108 (no silent weakening):** the constraint set is immutable by
  construction — the command vocabulary has no constraint mutation path, the
  fingerprint is stable across the lifecycle, and renegotiation is explicit
  supersession (a new contract with a chain link).
- **LOCK-113 (commercial separation):** usage/pricing terms and compensation are
  opaque external references; no payment semantics in the core.
- **LOCK-117 (authority uniqueness):** execution artifacts bind as data; identity
  and state are unaffected; no artifact-authority API exists.
- **LOCK-118 (provenance):** every externally asserted reference carries issuer
  and provenance.
- **LOCK-119 (secrets):** secret-shaped labels and values are rejected at
  construction and re-scanned on every persisted journal line.

## 4. Out-of-scope discipline (nothing else changed)

The M002 delta contains only the files listed in §1. No control-plane surface, no
spec/ file, no protocol schema, no W048 material (containment/sharing), no pilot/
surface, and no historical record is touched. The drift guard classifies the delta
implementation-only; the provenance gate verifies full coverage by R7-CORE-001.

## 5. Evidence classes (honest disclosure)

- All M002 acceptance criteria: **SOFTWARE** class (deterministic offline battery,
  54/54 PASS on the delivery head).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M002 creates and closes none;
  EVID-002..EVID-008 remain open and untouched.

## 6. Delivery provenance

- Branch: `m002-contract-core` from the activation head (DEC-0101 baseline
  `1e5c55f`).
- Battery: `python3 tools/contract_selftest.py` → PASS (54/54) on the delivery head.
- Full suite: the entire blocking battery set green on the delivery head (this
  file's §2 plus the per-battery results in CI); the three era-superseded batteries
  (payment/eligibility/client) skip visibly per the DEC-0099 disclosure.
