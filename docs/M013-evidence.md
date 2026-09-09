# M013 — Developer Connectivity API — Evidence Record

**Work Item:** M013 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7 program
authorization; M013 is an authorized child scope)
**Baseline:** `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (the R7 activation baseline;
branch rooted at the reconciled main head `d022e06f`)

This record persists the verified facts of the M013 delivery: the W046-era developer API
surface harvested and refactored (not rewritten) onto the canonical Architecture 1.1
authority — the accepted contracts domain (M002, DEC-0102).

## 1. Delivered surface

- **`developerapi/`** — the refactored Developer Connectivity API, SDK & Webhook platform:
  - `gateway.py` — the request boundary re-bound onto the canonical authority:
    `DeveloperApiService` composes EXACTLY ONE canonical authority
    (`contracts.ContractStore`) through its PUBLIC surface only
    (`next_record`/`merge` + the public reads).  The canonical route table
    (Architecture 1.1 §12 semantics): intents (create), accepted offers (typed
    references), activation, contracts (get/list/lifecycle/usage/assurance),
    termination, contract-scoped leases (grant/renew/revoke), and the retained
    webhook-endpoint family.  The write-ahead idempotency hold discipline (§3
    below); the crash-window reconstruction through the canonical authority's own
    duplicate discipline; the retained W046/W056 observation-admission machinery
    (admission records, obligations, queue, delivery pump) unchanged in semantics.
  - `schema.py` — the versioned API contract: the 2.0 canonical schema set
    (technology-neutral request members; every semantics-bearing member a typed
    reference or canonical contract material); the 1.x line RETIRED with honest
    migration notices (the schema module's own gate classifies 1.x→2.0 as BREAKING,
    which requires the new major version); 0.9 deprecated (historical schemas, the
    retained machinery surfaces); 0.8 retired.
  - `journal.py` — the append-only hash-chained journal with the M013
    write-ahead hold records (`MutationPendingRecord`/`MutationAbandonedRecord`)
    and the fold evolution (the offers index removed with the demoted route
    family; unknown developerapi-owned resource kinds fail closed).
  - `errors.py` — the canonical-reason table re-bound to the contracts-domain
    `ContractReason` vocabulary (every reason carried UNCHANGED through the
    boundary; no second reason-code authority).
  - `credentials.py` — the capability vocabulary re-targeted (8 capabilities;
    the W046 offers/billing/economic-policy capabilities demoted with their
    routes; `assurance:read` added).
  - `webhooks.py` — the event-type vocabulary re-targeted onto the canonical
    contract/lease lifecycle (9 event types; the commercial-plane events demoted).
  - `sdk.py` — the client surface evolved to the canonical operations (create
    intent, accept offers, activate, get/list contracts, usage/assurance reads,
    terminate, leases, webhooks); no hidden authority (import audit retained).
  - `__init__.py` — the public surface: 87 exports (85 retained verbatim + the
    two new journal record families); the module-level names otherwise unchanged.
- **`tools/developerapi_selftest.py`** — the evolved M013 battery: **56/56 PASS**
  (the W046 56-case structure and the W056 discrimination layer retained
  case-for-case, re-targeted from the superseded commercial-plane bindings to
  the canonical contract surface; disclosed below).
- **`docs/M013-evidence.md`** — this record.

## 2. Harvest/refactor classification (per the migration matrix)

| W046-era element | Classification | Disposition |
|---|---|---|
| Environments (sandbox/production isolation) | RETAIN | unchanged module, case-for-case battery coverage |
| Credentials/capabilities model | RETAIN + REFACTOR | model retained; capability vocabulary re-targeted (8) |
| Versioned schema machinery (classify/backward gate) | RETAIN | machinery unchanged; 2.0 schema set + 1.x retirement |
| Errors/reason preservation | RETAIN + REFACTOR | boundary vocabulary unchanged; canonical table → contracts reasons |
| Identifiers/correlation | RETAIN | unchanged |
| Journal (hash chain, fold, recovery) | RETAIN + REFACTOR | family retained; + write-ahead pending/abandoned records; offers fold demoted |
| Pagination | RETAIN + REFACTOR | retained; the declared equality filters now applied to the page items |
| Rate limiting | RETAIN | unchanged |
| Webhook platform (signing/retry/admission/obligation) | RETAIN | machinery unchanged; event types re-targeted |
| SDK | RETAIN + REFACTOR | parity machinery retained; operations re-targeted |
| Commercial-plane bindings (CommercialCore/UsageLedger/AllocationLedger) | DEMOTE | replaced by the single canonical `ContractStore` binding (LOCK-101) |
| `POST/GET /offers` (developerapi-owned offer resources) | DEMOTE | offers are the M003 child's semantics: typed `offer` references only |
| `GET /usage`, `GET /billing` (usage ledger reads) | DEMOTE | usage is the M009 child's semantics: the opaque `usage-pricing-terms` reference |
| `POST/GET /economic-policies` (allocation binding, 1.x compat layer) | DEMOTE | policy semantics belong to the policy/commercial child tracks |
| `POST /intents/{}/reservations` | TRANSLATE | contract-scoped leases (`POST /contracts/{}/leases`, grant/renew/revoke) |
| Commercial intent/reservation projections | TRANSLATE | canonical contract/lease projections (verbatim in meaning + envelope) |
| `connectivity_transaction.state_changed` observation | TRANSLATE | `connectivity_contract.state_changed` (the canonical journal position) |
| The 1.x REST wire contract | RETIRE | 2.0 major version (the breaking classification); honest notices |

The matrix row "Services → REFACTOR → Developer connectivity service" is satisfied by
this translation: the service-class boundary machinery is the reservoir; its resource
semantics are re-bound to the canonical authority.

## 3. Judgment calls (invariant references)

1. **Request-declared canonical command instants.** The contracts authority's command
   identity is content-derived over (contract, payload, recorded instant).  To keep the
   idempotency contract (a redelivered key never re-executes), every mutation declares
   its command instants in the request (`recorded_at`/`activated_at`/`granted_at`), so
   the same key + same body derives the byte-identical canonical command and the
   canonical DUPLICATE discipline closes the crash window (case 12).  LOCK-119-adjacent
   honesty: no wall clock, no fabrication — the instants are request data validated by
   the canonical authority.
2. **Write-ahead idempotency holds.** The W046 boundary closed the crash-window
   changed-content case through the superseded commercial plane's key-derived command
   ids.  The canonical authority has content-derived command ids, so the boundary owns
   the key discipline itself: the (key, request digest) pair is journaled BEFORE the
   canonical submission (`mutation-pending`), a semantically rejected request releases
   the hold (`mutation-abandoned` — failures never consume the key, the retained W046
   contract), and a changed-digest redelivery under a held key fails closed
   `idempotency-conflict` including inside the crash window (cases 9, 12).  This is a
   disclosed strengthening of the idempotency invariant.
3. **The principal is derived, never request-supplied.** The canonical contracting
   principal is the authenticated APPLICATION (`ConnectivityPrincipal` APPLICATION /
   the application id); beneficiaries are request-supplied bounded scope (LOCK-103).
   Tenant visibility is developer-scoped across their applications (the W046 observable
   tenancy contract), while the canonical authority carries the application principal.
4. **The webhook delivery seam is retained.** LOCK-114's "no transports" is about the
   CONNECTIVITY surface (§12: no Node/Link/gNB/UPF/bearer/routing objects).  The
   observation channel's injectable delivery callable (how ADCOS delivers signed events
   to the developer's HTTPS endpoint) is retained W046 machinery — never a connectivity
   implementation object; the battery's LOCK-114 audit pins both the member vocabulary
   and the absence of socket/adapter/provider-SDK constructions (case 26).
5. **The 0.9 deprecated line is retained as machinery demonstration.** 0.9 remains
   admitted-with-notice over the retained machinery surfaces (application self,
   webhook endpoints — the 1.x-era shapes that survive verbatim); the canonical routes
   validate against 0.9's historical schema set, so 1.x-shaped bodies fail closed
   there.  This keeps the version-policy machinery (supported/deprecated/retired)
   fully live and battery-pinned (cases 2, 3).
6. **Pagination filters are applied.** The pagination module declares equality filters
   over declared members; the W046 gateway passed them as cursor context only.  The
   M013 read paths apply the declared equality filters to the page items (a disclosed,
   battery-pinned tightening of the declared contract).

## 4. Deterministic verification matrix

All runs offline; instants injected/request-declared; no wall clock, no randomness, no
UUIDs, no network; PYTHONHASHSEED-safe (verified across processes and seeds 0/1/7919/
unset).

| Verification | Result | Evidence |
|---|---|---|
| Frozen vocabularies (capabilities 8 / events 9 / reasons 18 / versions 5) | PASS | case_01 |
| Version policy (2.0 supported; 0.9 deprecated-with-notice; 1.x/0.8/unknown/disagreement rejected) | PASS | case_02 |
| Schema compatibility gate (additive/deprecation/breaking; the 1.x→2.0 lineage BREAKING) | PASS | case_03 |
| Environments isolation (both directions + the binding gate) | PASS | case_04 |
| Credentials (issuance/verification/expiry/revocation; secret never journaled) | PASS | case_05 |
| Authentication failures (unknown/wrong-secret/empty) | PASS | case_06 |
| Capability authorization (the full route/capability negative matrix) | PASS | case_07 |
| Idempotency: normal duplicate (byte-identical replay, zero growth) | PASS | case_08 |
| Idempotency: conflict + rejected requests release the key | PASS | case_09 |
| Idempotency: concurrent same-key submission | PASS | case_10 |
| Idempotency: restart (journal-first recovery, byte-identical replay) | PASS | case_11 |
| Idempotency: crash window (canonical duplicate, zero re-execution; changed content fails closed) | PASS | case_12 |
| Canonical contract lifecycle flow (§11 states, honest classification, lease lifecycle, supersession) | PASS | case_13 |
| Reason-code preservation (contract-terminal/unknown-contract/secret-rejected/vocabulary/temporal-invalid/invalid-transition/not-yet-valid) | PASS | case_14 |
| Pagination (order/cursor/forgery/filter/tenant/intents window) | PASS | case_15 |
| Rate limiting (429 + guidance; mints nothing; per-application) | PASS | case_16 |
| Correlation + response secret hygiene | PASS | case_17 |
| Webhook signing (genuine verifies; tampered rejected) | PASS | case_18 |
| Webhook duplicate/replay (re-observation emits nothing; detector) | PASS | case_19 |
| Webhook out-of-order (version metadata + OrderTracker) | PASS | case_20 |
| Webhook retry (frozen backoff; event bytes never change) | PASS | case_21 |
| Webhook environment separation | PASS | case_22 |
| SDK request parity (byte-identical) | PASS | case_23 |
| SDK response/error/pagination parity | PASS | case_24 |
| SDK webhook verification parity (+ stale rejection) | PASS | case_25 |
| LOCK-114 technology-neutral surface (member vocabulary + opaque execution references) | PASS | case_26 |
| Typed-reference discipline (wrong kinds fail; opaque reads; demoted routes 404) | PASS | case_27 |
| Import discipline (stdlib + canonicalization + clock seam + contracts ONLY) | PASS | case_28 |
| No shadow authority (sanctioned call surface; no second contract model) | PASS | case_29 |
| SDK no hidden authority | PASS | case_30 |
| Physical evidence honesty (never claimed; evidence classes) | PASS | case_31 |
| Journal tamper (tamper/reorder/torn-tail/duplicate-key fail closed) | PASS | case_32 |
| Journal-first recovery (load == live) | PASS | case_33 |
| Failure injection (pending-append failure: zero phantom state; healed retry) | PASS | case_34 |
| Determinism (two fresh runs, identical digests) | PASS | case_35 |
| Determinism (PYTHONHASHSEED 0/1/7919/unset subprocesses) | PASS | case_36 |
| LOCK-119 secret hygiene (secret-shaped values rejected; journal scan) | PASS | case_37 |
| Frozen public API (87 exports pinned) | PASS | case_38 |
| py_compile (12 modules) | PASS | case_39 |
| Frozen spec surfaces intact (guarded files byte-identical; CI untouched) | PASS | case_40 |
| PR delta shape (M013 scope + R7 baseline ancestry) | PASS | case_41 |
| Post-finality webhook isolation (contained queue failure; exactly-once recovery) | PASS | case_42 |
| Durable obligation crash recovery | PASS | case_43 |
| Obligation-write admission gate (deterministic 500; healing retry) | PASS | case_44 |
| Durable observation admission state (terminal not-required; frozen audience, no drift) | PASS | case_45 |
| Sabotage: version laundering detected | PASS | case_46 |
| Sabotage: idempotency re-keying detected | PASS | case_47 |
| Sabotage: privilege escalation detected | PASS | case_48 |
| Sabotage: environment bridging detected | PASS | case_49 |
| Sabotage: reason rewriting detected | PASS | case_50 |
| Sabotage: webhook signature blindness detected | PASS | case_51 |
| Sabotage: webhook replay/order blindness detected | PASS | case_52 |
| Sabotage: pagination instability + cursor forgery detected | PASS | case_53 |
| Sabotage: SDK divergence detected | PASS | case_54 |
| Sabotage: rate-limit-as-authority detected | PASS | case_55 |
| Sabotage: observation-as-command detected | PASS | case_56 |

**Battery result: PASS (56/56 cases), green on 3 consecutive runs (exit-code-based
verification).**

## 5. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the boundary consumes the accepted contracts
  domain through its public surface only; no modification, no duplication (cases 28,
  29); `contract_selftest` remains 54/54 on this delivery head.
- **LOCK-102 (intent independence):** normalized requirements ride opaque
  `intent-requirements` typed references; the boundary never interprets intent
  semantics (cases 26, 27).
- **LOCK-103 (application purchasing):** the derived APPLICATION principal sponsors
  request-declared bounded beneficiaries; reference-only scope (case 13).
- **LOCK-106/LOCK-107 (assurance):** assurance obligations ride opaque
  `assurance-obligation` references; the API reports the contract-recorded outcomes
  only, never evaluates assurance (case 27).
- **LOCK-110 (adapter isolation):** no adapter or provider SDK type anywhere in the
  family (case 28 import audit; case 26 vocabulary audit).
- **LOCK-113 (commercial separation):** usage/pricing terms ride the opaque
  `usage-pricing-terms` reference; the usage/billing/economic-policy routes are
  demoted to the M009 child track (cases 26, 27).
- **LOCK-114 (developer semantics):** technology-neutral contract/offers/assurance/
  usage semantics as opaque typed references; no network implementation objects in
  the API surface (cases 26, 27 — the M013 acceptance criteria).
- **LOCK-117 (authority uniqueness):** execution material rides the contract's opaque
  `execution-scope`/`execution-artifact` references — data, never authority (cases 13,
  26).
- **LOCK-118 (provenance):** the contract provenance carries the application issuer
  and the boundary's key-derived decision reference (case 13 round-trip).
- **LOCK-119 (secrets):** secret-shaped values rejected by the canonical authority and
  surfaced unchanged; zero credential/webhook secrets in any journal byte (cases 14,
  17, 37).

## 6. Battery evolution disclosure (the M002 precedent)

The W046-era 56-case battery is evolved with the refactored surface, case-for-case:
the world composition simplifies honestly (the M013 boundary composes exactly one
canonical authority, so the battery composes exactly that); the route/capability/
schema/event vocabularies follow the M013 surface; the idempotency cases gain the
write-ahead hold verification; the LOCK-114 acceptance gains two dedicated structural
cases (26, 27).  The W056 discriminating-power layer (cases 46–56) is retained with
re-targeted sabotage candidates.  The case count is unchanged (56); every case name
maps to its W046-era predecessor.

## 7. Out-of-scope discipline (nothing else changed)

The M013 delta contains only the files listed in §1.  No control-plane surface, no
`spec/` file, no protocol schema, no other domain or battery (the payment/eligibility/
client era-superseded batteries are untouched), no W048 material, no historical record.
The drift guard classifies the delta implementation-only; the provenance gate verifies
full coverage by R7-CORE-001's declared scope.

## 8. Evidence classes (honest disclosure)

- All M013 acceptance criteria: **SOFTWARE** class (deterministic offline battery,
  56/56 PASS on the delivery head; the full blocking battery suite green).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M013 creates and closes none;
  EVID-002..EVID-008 remain open and untouched.  No SOFTWARE evidence is converted
  into PHYSICAL PASS anywhere in this delivery.

## 9. Delivery provenance

- Branch: `m013-developer-api` from the main head `d022e06f` (which descends from the
  R7-CORE-001 activation baseline `1e5c55f`).
- Battery: `python3 tools/developerapi_selftest.py` → PASS (56/56) on the delivery
  head, green on 3 consecutive runs.
- `python3 tools/contract_selftest.py` → PASS (54/54) on the delivery head (the
  canonical authority untouched).
- Gates: `current_spec_check`, `tech_lead_guard`, `architecture_drift_guard`
  (implementation-only), `fresh_session_check --actual-main-sha`, and
  `authorization_provenance` PASS on the delivery head.
- Full suite: the entire blocking battery set green on the delivery head in the exact
  `.github/workflows/spec-check.yml` order; the three era-superseded batteries
  (payment/eligibility/client) skip visibly per the DEC-0099 disclosure.
