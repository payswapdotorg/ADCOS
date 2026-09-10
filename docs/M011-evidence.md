# M011 — Vertical Proof: RoamLink — Evidence Record

**Work Item:** M011 (Vertical Proofs — RoamLink) · **Authorization:** R7-CORE-001
(DEC-0101, the bounded R7 program authorization; `roamlink/` is a declared child
scope of the M010/M011/M012 vertical-proof tranche)
**Baseline:** `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (the R7 activation
baseline; branch rooted at the DEC-0110-accepted main head `ba76496` — the
live main head at delivery time, inspected per the live-main rule; the M010
sibling delivery and its acceptance are upstream of this branch and outside
its delta)
**Frozen boundary under proof:** `spec/integration/vertical-proof.md` (ACR-014,
FROZEN) — the 6-step RoamLink flow plus the architectural acceptance clause.
**Dependency:** requires M013 acceptance first — satisfied (DEC-0113; the
`developerapi/` surface the whole vertical composes through).

This record persists the verified facts of the M011 delivery: the `roamlink/`
vertical-proof harness that proves the FROZEN 6-step RoamLink flow as a
SOFTWARE-class deterministic simulation battery, composing the ACCEPTED
canonical domains as real authority and representing the NOT-YET-ACCEPTED
children's mechanics as clearly-labeled simulation seams.

## 1. Delivered surface

### 1.1 `roamlink/` — the vertical-proof harness (NEW)

- **`roamlink/__init__.py` (NEW)** — the public surface and the composition
  disclosure: the error model, the external application boundary, the
  simulation seams, and the vertical flow.  The module docstring IS the
  composition map (real authority domains vs simulation seams), and the
  battery pins it exactly (`AUTHORITY_DOMAINS` + `SIMULATION_SEAMS`).
- **`roamlink/errors.py` (NEW)** — the typed error model: `RoamLinkError`
  (ValueError subclass) with a stable machine-readable `code` from the frozen
  `RoamLinkReason` vocabulary (ten `roamlink-` namespaced reasons: invalid
  input, vocabulary, temporal, secret-rejected, cohort-not-opaque,
  vertical-semantics-rejected, seam-misused, constraint-violation,
  attribution-invalid, step-invalid).  Fail closed everywhere; error detail is
  deterministic and never echoes secret-shaped material.
- **`roamlink/cohort.py` (NEW)** — the RoamLink EXTERNAL application boundary
  (LOCK-120): `SubscriberCohort` (an opaque bounded cohort scope — grammar-
  validated handle, member COUNT, deterministic enumerated opaque member
  handles; no subscriber identity ever crosses), `CohortConnectivityRequest`
  (the technology-neutral LOCK-102 creation core: opaque normalized-
  requirements references, service-level hard constraints, validity,
  termination rules, referenced usage/assurance/execution semantics — never an
  implementation mechanism, vendor or access technology), and
  `RoamLinkBoundary` (the application over the accepted M013 surface ONLY:
  imports nothing but `developerapi` + stdlib — the frozen boundary's
  architectural acceptance clause; the SDK client over an injected transport,
  the consumer-side webhook verifier + duplicate detector, the OPAQUE
  application-owned state blob that never crosses into any ADCOS surface, and
  the verified observation log).  The outbound LOCK-120/LOCK-119 scan rejects
  subscriber-identity-shaped tokens (msisdn/imsi/eid/iccid/ki/opc/...) and
  vertical-semantics tokens (esim/sim_profile/ux_flow/...) at the request-body
  boundary before anything is sent.
- **`roamlink/simulation.py` (NEW)** — the DETERMINISTIC SIMULATION SEAMS (the
  NOT-YET-ACCEPTED children's mechanics as labeled test doubles; never
  authority, never claimed delivered): `SIMULATION_SEAMS` (the frozen registry
  — the composition disclosure), the M004 eligibility/policy double
  (`SimulatedPolicyGate`: pure constraint matching over the exposed offers),
  the M005 evidence/assurance double (`SimulatedAssuranceEvaluator`: one-to-one
  mapping onto the frozen `contracts.ASSURANCE_STATES` vocabulary, feeding the
  REAL `RecordAssurance` command), the M006/M007 execution-plan/realization
  doubles (`SimulatedExecutionPlanner`/`SimulatedRealization`/
  `SimulatedSegment`: segments verified against the contract's hard
  constraints at construction, riding the REAL `BindExecutionArtifact`
  command as opaque `execution-artifact` references — LOCK-117: data, never
  authority), and the M008 replan/failover double (`SimulatedReplanner`: the
  provider-change absorption path, with LOCK-108 enforced INSIDE the seam — a
  weakening alternate is REJECTED and recorded, never bound; with no
  admissible alternate the honest verdict is `unrecoverable`).  The provider
  world is REAL M003 material (advertisements + offers built through the
  accepted public builders, registered in a REAL `OfferExchange`); the
  deterministic provider-change injection is vertical-battery fixture DATA at
  fixed instants.
- **`roamlink/flow.py` (NEW)** — `RoamLinkVerticalFlow`: the deterministic
  6-step vertical run and its typed transcript + digest.  The frozen scenario
  timeline (T0..T_SETTLED, all injected instants), the two-provider world,
  the step sequence (cohort request → offer/term exposure with the policy seam
  verdict → contract acceptance through the real typed offer references →
  execution status + assurance events through the real contract walk and the
  signed webhook channel → provider-change absorption with LOCK-108
  verification (hard-constraint fingerprint byte-identical, accepted offers
  unchanged, identity unchanged, weakened successor rejected, admissible
  replacement bound behind the SAME contract) → the usage attribution and
  commercial settlement walk behind the ONE contract (the REAL M009 usage
  ledger — the account key IS the contract citation — and the REAL M009
  commercial core walk) → the application-authority audit record).  The
  transcript digest covers the transcript, the contract journal digest, the
  offer catalog digest, the API journal digest, the usage digest stream, the
  commercial journal digest and the boundary's verified observations:
  byte-identical across fresh runs and PYTHONHASHSEED values.

### 1.2 Battery

- **`tools/roamlink_selftest.py` (NEW)** — the M011 battery (56 cases): the
  composition-map pin, SOFTWARE-class honesty, the 6-step flow cases (each
  naming its step), the LOCK-108 change-absorption cases (weakened-successor
  rejection, constraint-fingerprint preservation, accepted-offer/identity
  invariance, replacement binding, recovery), the usage/commercial closing
  cases (LOCK-113 account-key attribution, statement arithmetic, the
  11-command commercial walk bound to the one contract, final SETTLED state),
  the LOCK-120 authority cases (application state never crosses, all
  observations attributed, the boundary surface is the M013 route set only),
  determinism (two fresh runs + PYTHONHASHSEED subprocesses + transcript
  round-trip + tamper detection), ten fail-closed negatives (subscriber
  identity, vertical semantics, malformed cohorts, unsatisfiable policy,
  planner/replanner LOCK-108 violations, vocabulary enforcement, webhook
  signature tampering, duplicate observations), structural discipline (import
  discipline for the boundary and against the pending children's real
  domains, no wall clock/randomness/network/secrets, secret hygiene,
  py_compile, frozen-spec intact, the authorization-aware PR delta shape) and
  the evidence-doc honesty check.

### 1.3 Evidence

- **`docs/M011-evidence.md` (NEW)** — this record.

## 2. Composition classification (the honest vertical-proof disclosure)

The vertical proof composes two classes of material, and the classification is
pinned by the battery (`case_01`):

**REAL AUTHORITY — the accepted canonical domains, composed by reference
through their PUBLIC surfaces only, never modified, never re-implemented:**

| Domain | Acceptance | Role in the vertical |
|---|---|---|
| `contracts/` | M002, DEC-0102 | the durable authority: the real `ContractStore` journal fold; the real `CreateContract` (via the API route), `SelectOffers`, `ActivateContract`, `RecordExecutionActivation`, `BindExecutionArtifact`, `RecordDelivery`, `RecordAssurance`, `RecordUsageFinal`, `RecordSettlementPending`, `RecordSettled` commands |
| `offers/` | M003, DEC-0103 | step 2: the real `OfferExchange`, `build_advertisement`/`build_offer`, the real bridge reference shape (`offer_reference`), fail-closed resolution (the superseded listing is unresolvable at the change instant) |
| `commercial/` + `usage/` | M009, DEC-0109 | the commercial-terms surface (the real `OfferPricing` integer-minor-unit terms resolved from public reads) and the usage/commercial attribution: the real contract-cited `ContractCommercialSnapshot`, `UsageEvidenceIndex`, `UsageLedger` (the account key IS the contract citation — LOCK-113) and the real bound `CommercialCore` 11-command settlement walk |
| `developerapi/` | M013, DEC-0113 | the application-facing surface the whole vertical composes through: the real `DeveloperApiService` route table (create intents, accept offers, activate, inspect lifecycle/assurance/usage), the real signed webhook observation channel with admission-time audience resolution, and the real SDK client the RoamLink boundary drives |

**DETERMINISTIC SIMULATION SEAMS — the NOT-YET-ACCEPTED children's mechanics
as clearly-labeled TEST DOUBLES of their future domains (never imported as
authority, never claimed delivered):**

| Seam | Represents | The double |
|---|---|---|
| `simulation-seam:m004-eligibility-policy` | M004 (eligibility/policy) | `SimulatedPolicyGate`: deterministic constraint matching; verdict recorded as a typed `decision` reference whose provenance issuer IS the seam label |
| `simulation-seam:m005-evidence-assurance` | M005 (evidence/assurance) | `SimulatedAssuranceEvaluator`: deterministic verdicts in the frozen `contracts.ASSURANCE_STATES` vocabulary, feeding the REAL `RecordAssurance` command |
| `simulation-seam:m006-execution-plan` | M006 (execution plans) | `SimulatedExecutionPlanner`: deterministic segments under the contract's permitted execution scope |
| `simulation-seam:m007-realization-adapter` | M007 (realization/adapter) | `SimulatedRealization`/`SimulatedSegment`: provider-scoped realizations riding the REAL `BindExecutionArtifact` command as opaque references (LOCK-117) |
| `simulation-seam:m008-replan-failover` | M008 (replan/failover) | `SimulatedReplanner`: the change-absorption path with LOCK-108 enforced inside the seam |

The seams never import the pending children's real domains (`policy/`,
`eligibility/`, `telemetry/`, `executionplans/`, `composition/`, `adapters/`,
`sessions/`, `mobility/`, `multipath/`, `replan/`, `networkpath/`,
`routing/`) — pinned by `case_50`.  Every seam-produced reference carries its
seam label as the provenance issuer.  The provider-change injection
(`ProviderChange`) is vertical-battery fixture DATA (fixed kinds, fixed
instants), not an observation of the outside world.

## 3. Judgment calls (invariant references)

- **LOCK-102 (intent independence):** the cohort request is technology-
  neutral by construction (opaque typed requirement references + service-level
  constraint kinds); the battery's mechanism-token scan (`case_04`) proves no
  implementation mechanism, vendor or access technology appears in what
  crosses the boundary.
- **LOCK-103 (application purchasing):** the contracting principal is the
  APPLICATION (`roamlink-cohort-app`) purchasing for bounded USER
  beneficiaries — the enumerated opaque cohort members (`case_03`/`case_05`).
- **LOCK-106 (evidence typing):** execution status, assurance events, usage
  evidence and commercial references are distinct typed references, each
  attributable to the one contract (`case_14`/`case_17`/`case_33`).
- **LOCK-108 (no silent contract weakening):** enforced at BOTH seams — the
  planner fails closed on a constraint-violating offer (`case_43`), and the
  replanner rejects the weakened successor at the change seam, records it as
  a rejected realization, binds only the admissible alternate behind the SAME
  contract, and the hard-constraint fingerprint / accepted-offer set /
  contract identity are verified byte-identical across the absorption
  (`case_22`/`case_23`/`case_24`/`case_25`/`case_45`); with no admissible
  alternate the verdict is the explicit `unrecoverable` — never a silent
  weakening (`case_44`).
- **LOCK-113 (commercial separation):** the usage ledger account key and the
  sealed statement citation ARE the contract id; the commercial walk stays
  bound to the one contract through all 11 commands; payment/settlement
  material enters as external references only (`case_28`/`case_29`/
  `case_30`).
- **LOCK-117 (authority uniqueness):** the simulated realizations ride the
  REAL bind command as opaque `execution-artifact` references with the seam
  issuer — data, never authority (`case_14`); the boundary drives no contract
  command and holds no store (`case_34`).
- **LOCK-118 (provenance):** every exposed term, commitment, boundary and
  seam-produced reference carries issuer + provenance (`case_08`); every
  seam label is pinned (`case_01`).
- **LOCK-119 (secrets/determinism):** injected instants only, no wall clock,
  no randomness, no UUIDs, no network, no secret generation in the package
  (`case_51`); no signing secret, issuance key or application key material
  in any journal or transcript (`case_52`); byte-identical digests across
  fresh runs and PYTHONHASHSEED values (`case_35`/`case_36`).
- **LOCK-120 (vertical proof):** RoamLink is modeled as an EXTERNAL
  application boundary — opaque subscriber cohort (grammar-enforced,
  identity-token scan), technology-neutral request, SDK-only composition
  (imports `developerapi` only — the frozen boundary's architectural
  acceptance clause: the application never imports provider-native APIs into
  its core and never becomes a second connectivity-contract authority);
  the opaque application-owned state blob never crosses into any ADCOS
  surface (`case_32`/`case_34`/`case_49`); the harness never implements
  mobile observation, device context, eSIM product behavior or mobile UX —
  ADCOS supplies connectivity for the cohort only.

## 4. Deterministic verification matrix

All runs offline; instants injected; no wall clock, no randomness, no UUIDs,
no network; PYTHONHASHSEED-safe (verified across processes and seeds).

| Verification | Result | Evidence |
|---|---|---|
| The composition map is pinned exactly (4 authority domains + 5 seam labels) | PASS | roamlink case_01 |
| SOFTWARE-class honesty: sandbox transcript, no physical claim in the package | PASS | roamlink case_02 |
| Step 1: the cohort request creates an INTENT contract, APPLICATION principal | PASS | roamlink case_03 |
| Step 1: technology-neutral request (mechanism-token scan clean) | PASS | roamlink case_04 |
| Step 1: opaque beneficiaries (3 grammar-valid USER member handles) | PASS | roamlink case_05 |
| Step 1: the opaque cohort grammar (positive + negative shapes) | PASS | roamlink case_06 |
| Step 2: two live provider listings exposed at the exposure instant | PASS | roamlink case_07 |
| Step 2: commercial terms shape (integer minor units, bounded commitments, jurisdictions) | PASS | roamlink case_08 |
| Step 2: the M004 seam verdict eligible, seam-labeled | PASS | roamlink case_09 |
| Step 2: service boundaries declare the requested jurisdiction | PASS | roamlink case_10 |
| Step 3: both offers bound through real typed offer references | PASS | roamlink case_11 |
| Step 3: the acceptance activated the contract (journal-recorded) | PASS | roamlink case_12 |
| Step 3: the policy decision recorded as seam-labeled decision data | PASS | roamlink case_13 |
| Step 4: execution artifacts ride the real bind command (seam issuer) | PASS | roamlink case_14 |
| Step 4: delivery + compliant assurance recorded, ASSURED observed | PASS | roamlink case_15 |
| Step 4: the honest delivered-assured classification | PASS | roamlink case_16 |
| Step 4: signed observations received, verified, subscribed types only | PASS | roamlink case_17 |
| Step 4: the assurance read (state + typed obligation references) | PASS | roamlink case_18 |
| Step 4: the usage semantics read (opaque usage-pricing-terms reference) | PASS | roamlink case_19 |
| Step 5: the superseded listing is unresolvable (fail-closed resolution) | PASS | roamlink case_20 |
| Step 5: the honest DEGRADED assurance recorded at the change | PASS | roamlink case_21 |
| Step 5: the weakened successor REJECTED at the change seam (LOCK-108) | PASS | roamlink case_22 |
| Step 5: the hard-constraint fingerprint byte-identical across absorption | PASS | roamlink case_23 |
| Step 5: accepted offers + contract identity unchanged | PASS | roamlink case_24 |
| Step 5: the admissible replacement bound behind the SAME contract | PASS | roamlink case_25 |
| Step 5: the recovered delivered-assured status observed | PASS | roamlink case_26 |
| Step 5: the change injection is a fixed fixture event (frozen vocabulary) | PASS | roamlink case_27 |
| Usage: the account key and statement citation ARE the contract id (LOCK-113) | PASS | roamlink case_28 |
| Usage: sealed statement attribution + arithmetic (315 units × 190 = 59850) | PASS | roamlink case_29 |
| Commercial: the 11-command settlement walk bound to the one contract, SETTLED | PASS | roamlink case_30 |
| The ONE contract walked to SETTLED behind the whole vertical | PASS | roamlink case_31 |
| Step 6: the opaque application state never enters any ADCOS surface | PASS | roamlink case_32 |
| Step 6: every received observation attributable to the one contract | PASS | roamlink case_33 |
| Step 6: the boundary surface is the M013 route set only (no authority) | PASS | roamlink case_34 |
| Determinism: two fresh runs byte-identical (transcript + digest) | PASS | roamlink case_35 |
| Determinism: PYTHONHASHSEED 0/1/7919 subprocesses agree | PASS | roamlink case_36 |
| The transcript round-trips through sorted and canonical JSON | PASS | roamlink case_37 |
| Transcript tampering changes the deterministic digest | PASS | roamlink case_38 |
| Negative: subscriber-identity-shaped material rejected (LOCK-119/120) | PASS | roamlink case_39 |
| Negative: vertical-semantics tokens rejected (LOCK-120) | PASS | roamlink case_40 |
| Negative: malformed cohort handles/counts fail closed | PASS | roamlink case_41 |
| Negative: unsatisfiable constraints → the honest rejected verdict | PASS | roamlink case_42 |
| Negative: planning a weakening realization fails closed (LOCK-108) | PASS | roamlink case_43 |
| Negative: no admissible alternate → the explicit unrecoverable verdict | PASS | roamlink case_44 |
| Negative: binding a weakening replacement fails closed | PASS | roamlink case_45 |
| Negative: vocabulary enforcement (observation states, change kinds, instants) | PASS | roamlink case_46 |
| Negative: a tampered webhook signature never enters the observation log | PASS | roamlink case_47 |
| Negative: a replayed observation rejected by the duplicate detector | PASS | roamlink case_48 |
| Import discipline: the boundary imports ONLY developerapi + stdlib | PASS | roamlink case_49 |
| Import discipline: no pending child's real domain imported | PASS | roamlink case_50 |
| LOCK-119: no wall clock, randomness, uuid, network, secret generation | PASS | roamlink case_51 |
| Secret hygiene: no key material in any journal or transcript | PASS | roamlink case_52 |
| py_compile: the package + the battery compile | PASS | roamlink case_53 |
| Frozen spec intact (vertical-proof boundary, architecture, locks, charter, R7 authorization) | PASS | roamlink case_54 |
| PR delta shape: authorization-aware (R7-CORE-001 covers the delta) | PASS | roamlink case_55 |
| The evidence doc discloses SOFTWARE class, the seams, no physical claims | PASS | roamlink case_56 |

**Battery result: roamlink 56/56; the canonical-domain batteries stay green on
this delivery head (contract 54/54, offer 49/49, developerapi 56/56, usage
53/53, commercial 41/41 — consumed, never modified).**

## 5. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the vertical composes the canonical
  contract domain through its public surface only; the contract battery stays
  54/54 on this delivery head.
- **LOCK-102/LOCK-103:** see §3 — the technology-neutral request and the
  application-purchasing principal are pinned by cases.
- **LOCK-104/105 (provider sovereignty / no global topology):** no topology or
  routing surface anywhere in the delta; the providers are fixture domain
  identities whose behavior is injected fixture data.
- **LOCK-106/107:** assurance events are recorded through the real
  `RecordAssurance` command against the contract's obligations, and the
  closed loop (contract walk → observation → boundary verification) is
  exercised end-to-end.
- **LOCK-108:** the core acceptance criterion of step 5 — see §3; enforced
  inside the M008 seam AND verified on the contract (fingerprint byte-
  identity) by both the flow and the battery.
- **LOCK-109/110 (execution bridge / adapter isolation):** the M006/M007
  seams are the disclosed doubles of exactly these pending surfaces; no
  provider-native SDK type appears anywhere (the boundary imports
  `developerapi` only).
- **LOCK-113/LOCK-117/LOCK-118/LOCK-119/LOCK-120:** see §3.
- **LOCK-114 (developer semantics):** the whole vertical composes through the
  accepted API surface — connectivity services through typed references, no
  network implementation objects.

## 6. Battery evolution disclosure

`tools/roamlink_selftest.py` is a NEW battery landing with this delivery (the
M002/M003 precedent: the battery lands with the authorized child delivery).
No existing battery is touched.  The CI battery-step wiring for this battery
is control-plane material outside the M011 scope (the workflow file is wired
by governance commits per the repository's standing pattern — the M002
CI-wiring precedent); the delivery PR deliberately does not modify
`.github/workflows/spec-check.yml`.

## 7. Out-of-scope discipline (nothing else changed)

The M011 delta contains exactly: `roamlink/` (5 new modules),
`tools/roamlink_selftest.py` (new), `docs/M011-evidence.md` (new) — 7 files.
No control-plane surface, no `spec/` file, no `.github/` file, no canonical
domain file (`contracts/`, `offers/`, `usage/`, `commercial/`,
`developerapi/` — consumed, never modified), no other battery, no W048
material, no historical record.  The drift guard classifies the delta
implementation-only; the provenance gate verifies full coverage by R7-CORE-
001's declared scope (byte-identical authorization inheritance from main).

## 8. Evidence classes (honest disclosure)

- All M011 acceptance criteria (the 6-step vertical flow, the LOCK-108
  change absorption, the typed-reference attribution, the LOCK-120
  application-authority boundary): **SOFTWARE** class — the deterministic,
  offline, seeded simulation battery (roamlink 56/56) over the accepted
  canonical surfaces with the pending children's mechanics disclosed as
  simulation seams.
- The simulation seams are disclosed AS SEAMS: M004 (eligibility/policy),
  M005 (evidence/assurance), M006 (execution plans), M007 (realization/
  adapters) and M008 (replan/failover) are NOT delivered by this work item;
  their mechanics are deterministic test doubles whose outputs are labeled
  simulation material.  No claim is made anywhere that the real children are
  delivered.
- Physical-world obligations (real mobile-network connectivity, real eSIM
  provisioning, real provider changes): **NOT-TESTABLE/OPEN** — M011 creates
  and closes none; EVID-002..EVID-008 remain open and untouched.  No
  SOFTWARE evidence is converted into PHYSICAL PASS anywhere in this
  delivery; the execution-status classifications are the honest lifecycle
  derivations, never physical-connectivity claims.

## 9. Delivery provenance

- Branch: `m011-roamlink-proof` from the main head `ba76496` (which descends
  from the R7-CORE-001 activation baseline `1e5c55f` and carries the accepted
  M010 ShareNet delivery); append-only commits; zero file overlap with the
  M010 delta (`sharenet/` — the sibling vertical proof).
- Battery on the delivery head: `roamlink_selftest` 56/56 — green on 3
  consecutive runs (exit-code-based verification).
- Canonical-domain batteries on the delivery head: `contract_selftest`
  54/54, `offer_selftest` 49/49, `developerapi_selftest` 56/56,
  `usage_selftest` 53/53, `commercial_selftest` 41/41 (consumed, never
  modified).
- Gates: `current_spec_check`, `tech_lead_guard`, `architecture_drift_guard`
  (implementation-only), `fresh_session_check --actual-main-sha`,
  `authorization_provenance` PASS on the delivery head.
- Full suite: the entire blocking battery set green on the delivery head in
  the exact `.github/workflows/spec-check.yml` order (including the PR-only
  management and simulator batteries); the sole remaining tolerated skip is
  the DEC-0099-disclosed client battery (containment surface gone — M014
  track).
