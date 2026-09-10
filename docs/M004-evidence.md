# M004 — Eligibility and Policy — Evidence Record

**Work Item:** M004 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7 program
authorization; M004 is the charter's current child)
**Baseline:** `45b71dd6b1f1cc0b48f861681f1353dc78872fd2` (the DEC-0112-accepted main head;
the charter's abbreviated form `45b71dd`)

This record persists the verified facts of the M004 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule).

## 1. Delivered surface

- **`eligibility/contract_constraints.py` (NEW)** — the policy half of the M004 refactor
  (matrix: "Policy: RETAIN + REFACTOR -> Eligibility + contract constraints"):
  deterministic **contract-constraint policy evaluation AROUND the canonical contract**.
  Explicit issuer-carrying rules (`ContractConstraintRule`/`ContractConstraintSet` —
  LOCK-118: anonymous policy never evaluable; deny default effect structural) guard
  opaque `contract.`-namespaced actions and evaluate against caller-composed reference
  facts (`ContractConstraintContext` + `OfferReferenceFacts`) at an injected instant
  through `evaluate_contract_constraints`. The harvested WORK-010 semantics ride over
  case-for-case: deny-by-default for every guarded action (DEFAULT_DENY is a
  decision-producing outcome, never a silent allow); explicit deny beats allow at equal
  precedence; specificity then priority ordering with rule_id as the deterministic
  tiebreaker; equal-precedence distinct allows fail closed (CONFLICT);
  require-review → DENY+FAIL_CLOSED (never a silent ALLOW); a missing fact is a
  non-match with the observation recorded (the harvested case_04 shape); auditable
  decisions (`ContractConstraintDecision`: matched rule ids + set id/version + canonical
  bytes + content-derived id). Typed namespaced `contract-constraint-*` errors; the
  canonical vocabularies (principal/constraint kinds, contract states, M002 command
  kinds) are consumed as opaque DATA — never enumerated in the module (LOCK-101: no
  second vocabulary authority that could drift); the canonical action projection
  (`contract.<kind>` over `contracts.COMMAND_KINDS`) is computed at the composition
  boundary.
- **`eligibility/contract_eligibility.py` (NEW)** — the eligibility half: deterministic
  **contract-reference eligibility evaluation**. The W045 disciplines refactored onto
  the 1.1 authority model: fail-closed explicit rule DATA
  (`ContractEligibilityRuleset`: explicit permitted-provider and permitted-jurisdiction
  allow-lists — empty lists deny, never silently permit); the decision-DATA denial
  family (provider-not-permitted / jurisdiction-not-covered / offer-not-usable /
  contract-not-live / contract-terminal / no-accepted-offers) strictly separated from
  the raised typed-error family (`contract-eligibility-*`); fixed check order with
  deduplicated order-preserving reason tuples; versioned rulesets whose updates change
  NEW evaluation behavior without rewriting historical outcome records;
  `evaluate_offer_reference_eligibility` (one composed offer-reference fact set — an
  unusable offer is a DENIAL, never a raised error) and
  `evaluate_contract_reference_eligibility` (the contract-level checks: terminal-state
  exclusion, live validity window, non-empty accepted offers; then every offer
  reference individually; deterministic reason merge). Tamper-evident outcomes with
  content-derived digests and canonical-JSON round-trips.
- **Consumption discipline (LOCK-101, the harvested W045 snapshot seam — the strongest
  by-reference form):** the two evaluators NEVER import `contracts/` (M002) or
  `offers/` (M003); they consume caller-composed pure-DATA snapshots built from the
  canonical public surfaces (contract identity/state/terminal classification/validity/
  constraint kinds; resolved offer id/provider/jurisdictions/usability). The canonical
  domains' semantics are never re-implemented, and no evaluation ever mutates the
  contract or the exchange (battery-proven byte-identity).
- **`tools/policy_selftest.py` (EVOLVED, disclosed per the M002/M03 battery-evolution
  precedent)** — 74/74 → **103/103**: cases 1-74 retain their case-for-case WORK-010
  semantics (the legacy engine is RETAINED untouched — every dependent battery stays
  green); the M004 section (cases 75-87) owns the **composition seam**
  (`_m4_offer_facts_from_exchange` resolves accepted offer references through the M003
  exchange; `_m4_context_from_contract`/`_m4_contract_facts` read the canonical
  contract's public fields and pin the guarded action against the canonical M002
  command-vocabulary projection) and verifies the full delivery end-to-end.
- **`docs/M004-evidence.md`** — this record.

### Landing-spot judgment call (disclosed)

The worker charter scope lists `policy/` and `eligibility/` as the M004 harvest/refactor
trees. The delivered refactor lands BOTH halves under `eligibility/` — the migration
matrix's single target authority for the Policy row ("Eligibility + contract
constraints") — because the two M009-accepted batteries (DEC-0109, outside M004's
declared boundary) structurally pin the alternatives:

1. `tools/payment_selftest.py` case_38 freezes the whole **`policy` family** against ANY
   delta vs the audit ref (its `_SIBLING_PREFIXES` include `policy`): any change under
   `policy/` fails the payment battery (verified: a policy/README.md touch failed it,
   1/44). The payment battery is the M009 worker's material — the M004 worker charter
   explicitly forbids touching it.
2. `tools/eligibility_selftest.py` case_33 pins the **eligibility family import
   discipline** to stdlib + `protocol.canonicalization` + `agent.clock` only (no
   `contracts`/`offers` imports), and case_41 freezes the eligibility package's public
   API (`__all__`) — so the new modules live in the family UN-exported (the M003
   `marketplace/offer_bridge.py` precedent) and consume the canonical domains through
   caller-composed snapshots (the harvested W45 discipline itself: "consumes the
   accepted ... identities through an injected immutable snapshot built by the caller
   from those authorities' PUBLIC surfaces").

The legacy `policy/` engine (WORK-010) is therefore **RETAINED byte-identical to
origin/main** (battery case_75 asserts it), and the legacy `eligibility/` W045 surface
is **RETAINED untouched** (its frozen public API and family audits stay green). No
stop-condition was reached: nothing outside the declared M004 boundary
(`policy/`, `eligibility/`, `tools/policy_selftest.py`, `docs/M004-evidence.md`)
required change — the matrix's single-target routing made the in-boundary landing
possible, and this disclosure records the judgment call (R7-charter migration policy:
the frozen matrix governs; the Tech Lead records the resolution at acceptance).

### Out of the M004 scope per the worker charter (untouched)

- `tools/eligibility_selftest.py` — the DEC-0099/DEC-0109 commercial-track material:
  untouched (46/46 stays green on the delivery head).

## 2. Deterministic verification matrix

All runs offline; instants injected; no wall clock, no randomness, no UUIDs, no
network; PYTHONHASHSEED-safe (verified across processes and seeds 0/1/12345).
Exit-code-based verification (a traceback or lowercase "failed" IS a failure).

| Verification | Result | Evidence |
|---|---|---|
| Canonical action projection (LOCK-101) | PASS | case_75: CONTRACT_ACTIONS == `contract.<kind>` over `contracts.COMMAND_KINDS` (17 actions), computed at the composition boundary; legacy vocabularies + policy/ tree byte-identical |
| M004 vocabularies closed and namespaced | PASS | case_75: effects/decision-codes/predicates exact; `contract-constraint-*` / `contract-eligibility-*` raised families; denial DATA family unnamespaced |
| Minimal allow around the canonical contract | PASS | case_76: ALLOW on contract.select-offers; matched rule ids + policy version audited; facts read off the canonical record + M003 exchange |
| Explicit deny + deny-by-default | PASS | case_77: DENY matched; unruled action -> DEFAULT_DENY (decision-producing, effect=deny) |
| Fail-closed inputs | PASS | case_78 (+78b/e/f/g): instant required (FAIL_CLOSED); malformed instants typed-rejected at the context boundary; missing offer fact -> DEFAULT_DENY with missing-fact recorded (harvested case_04); expired/not-yet-valid sets; empty issuer / permissive default / non-canonical action rejected |
| Precedence + conflict determinism | PASS | case_79: deny>allow at equal precedence; specificity then priority; equal-precedence distinct allows -> CONFLICT; require-review -> DENY+FAIL_CLOSED; input order never leaks (byte-identical decisions) |
| Temporal windows | PASS | case_80: expired rule skipped; inclusive bounds at both edges |
| Subject selectors + typed conditions | PASS | case_81: 8 matching selectors ALLOW; 8 mismatched (incl. out-of-vocabulary) + out-of-window + stranger subject DEFAULT_DENY; bad predicate shape rejected |
| LOCK-101 by-reference discipline | PASS | case_82: contract identity/state/fingerprint/canonical bytes + exchange catalog digest byte-identical across composition + evaluation; withdrawn offer composes usable=False; offer-fact conditions fail closed on unusable facts |
| Offer-reference eligibility | PASS | case_83 (+83g/h/i): eligible composes via the M003 exchange; provider/jurisdiction denials ordered DATA; unusable offer is a DENIAL; stale ruleset raises typed; empty/absent rule facts fail closed |
| Contract eligibility composition | PASS | case_84: no-accepted-offers -> eligible -> contract-terminal -> past-window (contract-not-live + offer-not-usable, fixed merge order); reasons deduplicated and deterministic |
| LOCK-110 technology-neutral boundary | PASS | case_85: M004 modules import stdlib + protocol.canonicalization + agent.clock (+ intra-family relatives) only — canonical domains consumed via composed snapshots, never imported; no SDK/vendor/transport tokens in code (AST audit) |
| LOCK-119 secrets + round-trips | PASS | case_86 (+86g-l): set/decision/ruleset/outcomes round-trip byte-stably; mutated digests + unknown wire members fail closed; secret-shaped subject values, condition values and issuers rejected |
| Determinism | PASS | case_87: byte-identical decision/outcome bytes across repeated evaluations; identical digests across PYTHONHASHSEED 0/1/12345 subprocesses (pure-DATA evaluators, no canonical imports); no wall-clock/randomness/network tokens in the M004 modules |
| Eligibility-family audits stay green | PASS | `tools/eligibility_selftest.py` 46/46 (case_33 import discipline, case_41 frozen API, case_43 authorization-aware scope audit — all satisfied by the un-exported pure-DATA modules) |
| Payment-family audit stays green | PASS | `tools/payment_selftest.py` 44/44 (case_38 sibling freeze — the `policy` family is untouched by this delta) |

**Battery result: PASS (103/103 cases), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the evaluators never import or re-implement
  `contracts/`/`offers/` semantics; the canonical domains are consumed through
  caller-composed snapshots of their public surfaces; no evaluation mutates the
  contract or the exchange (byte-identity battery-proven); the canonical vocabularies
  (including the M002 command kinds behind the guarded actions) are never enumerated in
  the M004 modules — the projection is computed and pinned at the composition boundary.
- **LOCK-108 (no silent weakening):** policy evaluation reads the hard-constraint kinds
  as opaque DATA and can never mutate the constraint set (the fingerprint is
  battery-proven stable across evaluation).
- **LOCK-110 (adapter isolation):** no provider SDK/vendor/transport types anywhere in
  the M004 surface; providers appear only as opaque reference values (AST-audited);
  evaluation is technology-neutral.
- **LOCK-113 (commercial separation):** no payment surface; commercial material rides
  as the opaque references already stored on the canonical contract.
- **LOCK-117 (authority uniqueness):** eligibility/policy outcomes are DATA records
  with content-derived digests — never authorities; no artifact-authority path exists.
- **LOCK-118 (provenance):** every rule/constraint-set/ruleset carries a mandatory
  issuer + decision references; anonymous policy is never evaluable.
- **LOCK-119 (secrets):** secret-shaped labels and values rejected at construction and
  deserialization; no wall clock, randomness, network, or UUIDs anywhere in the M004
  surface (text + AST audits).
- **LOCK-115 (simple-system validity):** one provider, one offer, one contract, one
  ruleset is a complete valid evaluation (exercised throughout the battery).

## 4. Out-of-scope discipline (nothing else changed)

The M004 delta contains only the files listed in §1 (`eligibility/contract_constraints.py`,
`eligibility/contract_eligibility.py` new; `tools/policy_selftest.py` evolved with
disclosure; `docs/M004-evidence.md` new). The legacy `policy/` tree is byte-identical
to origin/main; `tools/eligibility_selftest.py` (the M009 material) is untouched; no
control-plane surface, no spec/ file, no `.github/` file, no `contracts/` or `offers/`
modification (the canonical domains are consumed, never modified), no W048 material
(containment/sharing), no pilot/ surface, and no historical record is touched. The
drift guard classifies the delta implementation-only; the provenance gate verifies full
coverage by R7-CORE-001 (eligibility/ and tools/ are declared child-scope prefixes;
docs/M004-evidence.md is the declared evidence path).

## 5. Evidence classes (honest disclosure)

- All M004 acceptance criteria: **SOFTWARE** class (deterministic offline battery,
  103/103 PASS on the delivery head; full battery suite green).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M004 creates and closes none;
  EVID-002..EVID-008 remain open and untouched. No simulation or battery result is
  physical, production, or live-service evidence.

## 6. Delivery provenance

- Branch: `m004-eligibility-policy` from the DEC-0112-accepted main head `45b71dd`.
- Battery: `python3 tools/policy_selftest.py` → PASS (103/103) on the delivery head,
  run 3× consecutively (exit-code-based).
- Full suite: every battery the CI workflow runs, in workflow order, all green with
  exit-code-based detection (the payment 44/44 and eligibility 46/46 DEC-0109
  re-baselines included; the era-superseded client battery skips visibly behind its
  DEC-0099 containment guard).
- `contract_selftest.py`: still 54/54 and `offer_selftest.py`: still 49/49 (the M002/
  M003 canonical domains are consumed by reference, never modified).
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
