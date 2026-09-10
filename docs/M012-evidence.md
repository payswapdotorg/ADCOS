# M012 — Vertical Proof: COMOS — Evidence Record

**Work Item:** M012 (Vertical Proofs — COMOS) · **Authorization:** R7-CORE-001
(DEC-0101, the bounded R7 program authorization; `comos/` is a declared child
scope of the M010/M011/M012 vertical-proof tranche)
**Baseline:** `1e5c55f9916ff964d3bfc0761d04a8d5fd02c41b` (the R7 activation
baseline; branch rooted at the DEC-0111-accepted main head `52b76ee` — the
live main head at delivery time, inspected per the live-main rule; the M010
and M011 sibling deliveries and their acceptances are upstream of this branch
and outside its delta)
**Frozen boundary under proof:** `spec/integration/vertical-proof.md` (ACR-014,
FROZEN) — the 6-step COMOS flow plus the architectural acceptance clause.
**Dependency:** requires M013 acceptance first — satisfied (DEC-0113; the
`developerapi/` surface the whole vertical composes through).  M009 is also
accepted (DEC-0109) and is composed as REAL authority (the M010-era harness
pre-dated that acceptance; this one does not).

This record persists the verified facts of the M012 delivery: the `comos/`
vertical-proof harness that proves the FROZEN 6-step COMOS flow as a
SOFTWARE-class deterministic simulation battery, composing the ACCEPTED
canonical domains as real authority and representing the NOT-YET-ACCEPTED
children's mechanics as clearly-labeled simulation seams.

## 1. Delivered surface

### 1.1 `comos/` — the vertical-proof harness (NEW)

- **`comos/__init__.py` (NEW)** — the public surface and the composition
  disclosure: the error model, the external application boundary, the
  simulation seams, the evidence ledger and the vertical flow.  The module
  docstring IS the composition map (real authority domains vs simulation
  seams), and the battery pins it exactly (`COMPOSITION_MAP` +
  `SEAM_IDS`).
- **`comos/application.py` (NEW)** — the COMOS EXTERNAL application boundary
  (LOCK-120): `ComosIntentSpec` (the technology-neutral LOCK-102 step-1
  request: frozen member vocabularies, service-level scalar bounds — never
  an implementation mechanism, vendor or access technology),
  `ComosRequirementsSpec` (the step-4 communication requirements envelope:
  the member-audited scalar bounds of the communication traffic its channels
  ride on — derived INSIDE the application from its opaque bundles; the
  semantics never cross), and `ComosApplication` (the application over the
  accepted M013 surface ONLY: imports nothing but `developerapi` + stdlib —
  the frozen boundary's architectural acceptance clause; the SDK client over
  the injected transport, the raw canonical request form for the webhook
  endpoint registration, and the verified observation log).  The outbound
  member audit (`audit_member_name`) rejects network-mechanism tokens
  (node, link, tunnel, socket, ssid, bearer, adapter, ...) AND
  COMOS-domain tokens (channel, conversation, message, delivery receipt,
  ...) fail-closed before any material is built; the retained domains
  (`COMOS_OWNED_DOMAINS`: identity, communication bundles, channel
  semantics, delivery semantics) stay opaque application-side values.
- **`comos/seams.py` (NEW)** — the DETERMINISTIC SIMULATION SEAMS (the
  NOT-YET-ACCEPTED children's mechanics as labeled test doubles; never
  authority, never canonical mutations): `SIMULATION_SEAMS` (the frozen
  registry — the single disclosure point), the M004 selection double
  (`SelectionSeam` + the constraint kernel
  `evaluate_constraint`/`evaluate_offer_against_constraints`/
  `evaluate_requirements_against_offer`: True/False/None semantics over the
  REAL hard constraints and the REAL offer commitments — a
  present-and-violating evaluation rejects the candidate fail-closed with
  the typed trail; an uncommitted dimension abstains), the M005 assurance
  double (`AssuranceSeam`: one-to-one onto the frozen
  `contracts.ASSURANCE_STATES` vocabulary, feeding the REAL `RecordAssurance`
  command), the M006 execution-plan double (`ExecutionPlanSeam` +
  `PlanSegment`: segments verified against the contract's hard constraints
  at construction — a weakening segment is rejected, LOCK-108), and the
  M007 realization double (`ProviderRealizationSeam` + `DeliveredFact` +
  `RealizationEvent`: the gateway-session/realization tokens ride the REAL
  `BindExecutionArtifact` command as opaque references — LOCK-117: data,
  never authority).  M008 (Replan and Failover) has NO step in the frozen
  COMOS flow (the flow carries no degradation/failure/replan step) and is
  deliberately NOT represented by a seam: the pending M008 child is never
  composed, never exercised, never claimed.
- **`comos/evidence.py` (NEW)** — the M012 attributable evidence ledger:
  `EvidenceEntry`/`EvidenceLedger`/`Attribution` over four DISTINCT typed
  kinds (`EVIDENCE_KINDS`: usage-observation, assurance-evaluation,
  requirements-submission, selection-decision — LOCK-106: a usage record is
  never an assurance record, and none is a claim, commitment or attestation)
  with four frozen issuers (`EVIDENCE_ISSUERS`: the REAL M009 usage
  authority, the M005 seam, the COMOS application, the M004 seam — LOCK-118
  provenance).  The ledger is BOUND to the REAL `ContractStore` (read-only
  public projection) and FAILS CLOSED: an entry whose contract does not
  exist in the canonical fold is rejected; an unbound ledger rejects every
  write; secret-shaped token values are rejected at construction
  (LOCK-119).  A `usage-observation` entry's token IS the observation id
  the accepted M009 `UsageLedger` derived — the attribution record bridges
  the authority's own journal and this ledger's contract attribution.
  Canonical-JSON round-trips are exact; iteration is sorted.
- **`comos/vertical.py` (NEW)** — `ComosVertical`: the deterministic 6-step
  vertical run over the REAL authorities (`ContractStore` M002;
  `OfferExchange`/model/bridges M003; `DeveloperApiService` + SDK M013;
  `CommercialCore` in M009 bound mode with journal-first reload;
  `UsageLedger` M009 with the contract-cited evidence index), the frozen
  scenario timeline (T_REQUEST..T_SETTLEMENT, all injected instants), the
  signed observation channel (`connectivity_contract.state_changed`:
  INTENT → CONTRACT_ACTIVE → terminal), the commercial walks (the
  11-command settle chain, journal-first reload included; the compensating
  cancel chain when the contract fails before execution), the usage seal
  (the tariff resolved from the REAL offer pricing DATA: price_minor 250,
  exponent 2 → 250 × 10^(6−2) = 2 500 000 micro-USD per canonical
  billable unit), and the three golden scenarios with their typed
  transcripts and content-derived digests — byte-identical across fresh
  runs and PYTHONHASHSEED values.

### 1.2 Battery

- **`tools/comos_selftest.py` (NEW)** — the M012 battery (33 cases): the
  composition-map pin, the LOCK-119/LOCK-110 AST audits, the frozen-flow
  byte-equality matrix, the 6-step cases (each naming its step), the three
  golden scenarios, the LOCK-108 requirements-purity cases (the step-4
  requirements mutate nothing; the failed contract keeps its original
  bounds), the constraint-kernel semantics, the seam-disclosure registry,
  the evidence attribution and ledger fail-closed negatives, the
  canonical round-trips, in-process and cross-process determinism
  (PYTHONHASHSEED 0/1/12345), the LOCK-120 member audit and boundary
  isolation, the observation channel, the SDK-only boundary, the
  LOCK-106/113/117/118 lock cases, the golden lifecycle chains, the
  commercial walk discipline, the lock-conformance mapping, the
  PR delta shape (authorization-aware — see §6), the real-authority
  composition (verified by type) and the golden scenario matrix.

### 1.3 Evidence

- **`docs/M012-evidence.md` (NEW)** — this record.

## 2. Composition classification (the honest vertical-proof disclosure)

The vertical proof composes two classes of material, and the classification is
pinned by the battery (`case_01`):

**REAL AUTHORITY — the accepted canonical domains, composed by reference
through their PUBLIC surfaces only, never modified, never re-implemented:**

| Domain | Acceptance | Role in the vertical |
|---|---|---|
| `contracts/` | M002, DEC-0102 | the durable authority: the real `ContractStore` journal fold; the real `CreateContract` (via the M013 API route), `SelectOffers`, `ActivateContract`, `BindExecutionArtifact`, `RecordAssurance` and terminal-state commands the flow drives |
| `offers/` | M003, DEC-0103 | step 2: the real `OfferExchange`, `build_advertisement`/`build_offer`, the real commitment/pricing/service-boundary model both provider domains advertise through; offer references ride its bridge shapes |
| `commercial/` + `usage/` | M009, DEC-0109 | the commercial-terms surface (the real bound-mode `CommercialCore` walk; the reconciliation account cites THE canonical contract) and the usage attribution (the real contract-cited `UsageLedger` — `transaction_id` IS the contract id; the sealed statement consumes the tariff resolved from the REAL offer pricing DATA, LOCK-113) |
| `developerapi/` | M013, DEC-0113 | the application-facing surface the whole vertical composes through: the real `DeveloperApiService` route table, the real signed webhook observation channel, and the real SDK client the COMOS boundary drives |

**DETERMINISTIC SIMULATION SEAMS — the NOT-YET-ACCEPTED children's mechanics
as clearly-labeled TEST DOUBLES of their future domains (never imported as
authority, never claimed delivered):**

| Seam | Represents | The double |
|---|---|---|
| `seam:m004-selection` | M004 (eligibility/policy) | `SelectionSeam` + the constraint kernel: deterministic True/False/None evaluation over the real constraints and commitments; verdict recorded as typed selection-decision evidence with the seam issuer |
| `seam:m005-assurance` | M005 (evidence/assurance) | `AssuranceSeam`: deterministic verdicts in the frozen `contracts.ASSURANCE_STATES` vocabulary, feeding the REAL `RecordAssurance` command |
| `seam:m006-execution-plan` | M006 (execution plans) | `ExecutionPlanSeam`/`PlanSegment`: deterministic segments under the contract's hard constraints — a weakening segment is rejected at construction (LOCK-108) |
| `seam:m007-realization` | M007 (realization/adapter) | `ProviderRealizationSeam`/`DeliveredFact`: the delivered-communication-traffic facts riding the REAL `BindExecutionArtifact` command as opaque references (LOCK-117) and feeding the REAL M009 usage observations |

M008 (Replan and Failover) has NO step in the frozen 6-step COMOS flow and is
deliberately absent: no M008 mechanic is doubled, composed, exercised or
claimed.  M009 is NOT a seam here — it is ACCEPTED (DEC-0109) and composed as
real authority.  The seams never import the pending children's real domains
(`policy/`, `eligibility/`, `telemetry/`, `executionplans/`, `composition/`,
`adapters/`, `sessions/`, `mobility/`, `multipath/`, `replan/`,
`networkpath/`, `routing/`) — pinned by `case_01`.  Every seam-produced
reference carries its seam label as the provenance issuer; the
delivered-quantity schedule is injected vertical-battery fixture DATA, not an
observation of the outside world.

## 3. Judgment calls (invariant references)

- **LOCK-102 (intent independence):** the step-1 request and the step-4
  requirements are technology-neutral by construction (frozen member
  vocabularies + service-level scalar bounds); the member audit
  (`case_19`) proves no implementation mechanism, vendor, access
  technology — and no COMOS-owned communication semantics — appears in
  what crosses the boundary.
- **LOCK-103 (application purchasing):** the contracting principal is the
  APPLICATION (`comos-connectivity-app`, developer
  `comos-app-developer`) purchasing for bounded opaque USER beneficiaries
  (`case_04`).
- **LOCK-106 (evidence typing):** usage observations, assurance
  evaluations, requirements submissions and selection decisions are
  DISTINCT typed evidence kinds, each attributable to THE contract —
  including after terminal failure (`case_14`, `case_24`).
- **LOCK-108 (no silent contract weakening):** the step-4 requirements are
  EVALUATED against the committed terms, never APPLIED — no requirements
  mutation command exists anywhere in the harness; the hard-constraint
  fingerprint is byte-identical in every scenario, the failed contract
  keeps its original 200 ms bound against the unsatisfiable 100 ms demand,
  and the M006 seam rejects a constraint-violating segment at construction
  (`case_11`, `case_12`).
- **LOCK-113 (commercial separation):** the usage ledger account key and
  the statement citation ARE the contract id; the commercial walk stays
  bound to the one contract through the journal-first reload; settlement
  material enters as an external reference only; no payment surface
  appears anywhere in the tree (`case_25`, `case_29`).
- **LOCK-117 (authority uniqueness):** the simulated realizations ride the
  REAL bind command as opaque `execution-artifact` references with the
  seam issuer — data, never authority; the boundary drives no contract
  command and holds no store (`case_21`, `case_27`).
- **LOCK-118 (provenance):** offers, commitments, evidence entries and
  seam-produced references all carry issuer + provenance (`case_26`); the
  seam labels are pinned (`case_13`).
- **LOCK-119 (secrets/determinism):** injected instants only, no wall
  clock, no randomness, no UUIDs, no network, no secret literals in the
  package (AST-audited, `case_02`); secret-shaped values are rejected at
  construction; byte-identical digests across fresh runs and
  PYTHONHASHSEED values (`case_17`, `case_18`).
- **LOCK-120 (vertical proof):** COMOS is modeled as an EXTERNAL
  application boundary — opaque retained domains, technology-neutral
  request and requirements, SDK-only composition (imports `developerapi`
  only — the frozen boundary's architectural acceptance clause: the
  application never imports provider-native APIs into its core and never
  becomes a second connectivity-contract authority); the application's
  communication semantics never cross into any ADCOS surface (`case_19`,
  `case_21`, `case_22`, `case_10`); the harness never implements identity,
  communication bundles, channel semantics or delivery semantics — ADCOS
  supplies gateway connectivity for the communication traffic only.

## 4. Deterministic verification matrix

All runs offline; instants injected; no wall clock, no randomness, no UUIDs,
no network; PYTHONHASHSEED-safe (verified across processes and seeds 0/1/
12345).

| Verification | Result | Evidence |
|---|---|---|
| The composition map is pinned exactly (5 real authorities + 4 seam labels; no pending child's real domain imported) | PASS | comos case_01 |
| LOCK-119/LOCK-110 AST audit: no wall clock, randomness, UUID, network or secret literals in `comos/` | PASS | comos case_02 |
| The 6 frozen steps byte-identical to the ACR-014 text; step records titled in order | PASS | comos case_03 |
| Step 1: technology-neutral request through the M013 SDK; contract INTENT; principal APPLICATION; beneficiaries opaque | PASS | comos case_04 |
| Step 2: 2 providers advertising; the dual scenario selects 2; the exclusion scenario rejects 1 with the latency-bound violation trail | PASS | comos case_05 |
| Step 3: exactly one contract per scenario; typed offer references; plan over the selected offers; commercial account contract-bound | PASS | comos case_06 |
| Step 4: member-audited scalar envelope; every committed leg satisfies it | PASS | comos case_07 |
| Step 5: artifacts as DATA; 11-command journal; usage sealed 750 units at the offer-resolved tariff; commercial settled | PASS | comos case_08 |
| Step 4/5 failure path: fail-closed typed termination; journal stops at fail; commercial cancelled; no usage; attribution survives | PASS | comos case_09 |
| Step 6: the boundary-retained record in all 3 scenarios; 4 frozen domains declared | PASS | comos case_10 |
| LOCK-108: hard constraints byte-identical in all scenarios; no requirements command exists; the failed contract keeps the 200 ms bound vs the 100 ms demand | PASS | comos case_11 |
| The constraint kernel: True/False/None semantics; full trails; fail-closed on non-canonical input | PASS | comos case_12 |
| The seam-disclosure registry: 4 disclosed PENDING seams; M008 absent (no step); M009 real; the composition map carries the 5 accepted authorities | PASS | comos case_13 |
| Evidence attribution: per-scenario counts exact (5/4/2 entries); usage tokens == the M009 observation ids; attribution state == terminal state | PASS | comos case_14 |
| The ledger fails closed: unbound ledger, unknown contract, 2 token shapes and 4 payload shapes | PASS | comos case_15 |
| Canonical round-trips: StepRecord / EvidenceEntry byte-exact; digest = canonical hash | PASS | comos case_16 |
| In-process determinism: 3 scenario digests identical across repeated fresh compositions | PASS | comos case_17 |
| Cross-process determinism: identical digests across processes and PYTHONHASHSEED 0/1/12345 | PASS | comos case_18 |
| LOCK-120 member audit: 13 mechanism/COMOS-domain member shapes fail closed; frozen vocabularies pass; bounds validated | PASS | comos case_19 |
| The observation channel: signed state_changed observations INTENT → CONTRACT_ACTIVE → terminal in all 3 scenarios; the app receives them all | PASS | comos case_20 |
| LOCK-120 boundary isolation: the app holds no authority (8 types checked); `application.py` imports only the M013 surface | PASS | comos case_21 |
| The SDK-only boundary: the app rides the M013 SDK + canonical ApiRequest only | PASS | comos case_22 |
| Exception isolation: typed ComosError codes from the closed set; no exception text in state | PASS | comos case_23 |
| LOCK-106: 4 distinct typed evidence kinds; frozen vocabulary; no token crosses kinds | PASS | comos case_24 |
| LOCK-113: usage is DATA with the offer-resolved tariff; settlement cites the external rail only; no payment surface in the tree | PASS | comos case_25 |
| LOCK-118: offers, commitments, evidence entries and accepted references all carry provenance | PASS | comos case_26 |
| LOCK-117: artifacts bind as opaque seam DATA with provenance; no authority conferred | PASS | comos case_27 |
| Golden lifecycle chains: journal/commercial/observation chains exact in all 3 scenarios; the failed scenario stops at fail and cancels | PASS | comos case_28 |
| Commercial walk discipline: contract-cited walk; formation then journal-first reload; settle after the seal; cancel compensates without settling | PASS | comos case_29 |
| Lock-conformance mapping: 13 Architecture 1.1 locks mapped to existing battery cases | PASS | comos case_30 |
| PR delta shape: authorization-aware (confined to the declared scope or sanctioned by the active authorization) | PASS | comos case_31 |
| Real-authority composition: the 5 canonical authorities + SDK client verified by TYPE; both authority digest streams recorded | PASS | comos case_32 |
| The golden scenario matrix: 3 scenarios match the frozen expectations exactly | PASS | comos case_33 |

**Battery result: comos 33/33; the canonical-domain batteries stay green on
this delivery head (contract 54/54, offer 49/49, developerapi 56/56, usage
53/53, commercial 41/41 — consumed, never modified); the sibling vertical
batteries stay green (sharenet 33/33, roamlink 56/56).**

### 4.1 The golden scenario expectations (the frozen matrix)

| Scenario | Contract bound (lat/tp/jit) | Providers (latency) | Step-4 requirements | Selected | Terminal | Usage | Commercial |
|---|---|---|---|---|---|---|---|
| dual-provider-delivery | 200 ms / 500 bps / 50 ms | 120 ms + 180 ms | 190 ms / 500 bps / 50 ms | 2 of 2 | SETTLED | 2 observations; 750 units (400 + 350); 2 500 000 µUSD/unit; gross 1 875 000 000 µUSD; BILLABLE_FINAL | 11 commands → SETTLED |
| constraint-exclusion | 150 ms / 500 bps / 50 ms | 120 ms + 180 ms | 160 ms / 500 bps / 50 ms | 1 of 2 (the 180 ms offer rejected with the typed violation trail) | SETTLED | 1 observation; 750 units; same tariff; gross 1 875 000 000 µUSD; BILLABLE_FINAL | 11 commands → SETTLED |
| requirements-unsatisfied | 200 ms / 500 bps / 50 ms | 120 ms + 180 ms | 100 ms / 500 bps / 50 ms | 2 of 2 | FAILED (typed reason; the committed legs cannot satisfy the demand) | none — delivery never began; nothing sealed | 5 commands + compensating cancel → CANCELLED |

Attribution entries per scenario: 5 (2 usage + 1 assurance + 1 requirements +
1 selection), 4 (1 + 1 + 1 + 1), and 2 (1 requirements + 1 selection — the
attribution SURVIVES the terminal failure).  Each scenario receives 3 signed
`connectivity_contract.state_changed` observations (INTENT →
CONTRACT_ACTIVE → terminal), each carrying the contract id, each verified by
the application.  The tariff is resolved from the REAL M003 offer pricing
DATA (price_minor 250, exponent 2 → 250 × 10^(6−2) = 2 500 000 micro-USD per
canonical billable unit; 750 × 2 500 000 = 1 875 000 000).

## 5. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the vertical composes the canonical
  contract domain through its public surface only; the contract battery
  stays 54/54 on this delivery head.
- **LOCK-102/LOCK-103:** see §3 — the technology-neutral request/
  requirements and the application-purchasing principal are pinned by
  cases.
- **LOCK-104/LOCK-105 (provider sovereignty / no global topology):** no
  topology or routing surface anywhere in the delta; the providers are
  fixture domain identities whose material is registered through the real
  M003 model.
- **LOCK-106/LOCK-107:** assurance events are recorded through the real
  `RecordAssurance` command against the contract's obligations; the closed
  loop (contract walk → signed observation → boundary verification) is
  exercised end-to-end.
- **LOCK-108:** the core acceptance criterion of the step-4/step-5
  coupling — see §3; enforced inside the M006 seam AND verified on the
  contract (byte-identical constraint fingerprints) by both the flow and
  the battery.
- **LOCK-109/LOCK-110 (execution bridge / adapter isolation):** the
  M006/M007 seams are the disclosed doubles of exactly these pending
  surfaces; no provider-native SDK type appears anywhere (the boundary
  imports `developerapi` only).
- **LOCK-113/LOCK-117/LOCK-118/LOCK-119/LOCK-120:** see §3.
- **LOCK-114 (developer semantics):** the whole vertical composes through
  the accepted API surface — connectivity services through typed
  references, no network implementation objects.
- **LOCK-115/LOCK-116 (simple-system validity / complex-system
  composition):** the dual-provider scenario composes BOTH providers under
  the ONE contract (LOCK-116); every scenario is a deterministic closed
  system (LOCK-115).
- **LOCK-112 (standard leverage):** the realization seam's
  gateway-session/realization tokens are opaque references behind the
  capability-oriented boundary — the pending M007 surface's discipline is
  respected by the double.

## 6. Battery evolution disclosure

`tools/comos_selftest.py` is a NEW battery landing with this delivery (the
M002/M003/M010/M011 precedent: the battery lands with the authorized child
delivery).  No existing battery is touched.  The CI battery-step wiring for
this battery is control-plane material outside the M012 scope (the workflow
file is wired by governance commits per the repository's standing pattern —
the M002 CI-wiring precedent); the delivery PR deliberately does not modify
`.github/workflows/spec-check.yml`.

**The authorization-aware PR-shape consultation is built in from first
delivery.**  The M010 delivery's `tools/sharenet_selftest.py` case_31
enforced its PR shape with a frozen scope list alone, which structurally
failed on every later authorized R7 child PR and had to be retro-repaired by
the M011 delivery (its evidence §7.1, commit `fb4a921`).  This battery's
case_31 accepts paths covered by the ACTIVE repository-local authorization
(`authorization_provenance.covers` — the consultation
`tools/developerapi_selftest.py` case_41, `tools/commercial_selftest.py`
case_35, the M009-re-baselined payment/eligibility batteries and the repaired
sharenet case_31 all use) in ADDITION to the frozen M012 scope, preserving
every original property: the M012 PR shape itself still passes (its files are
in the frozen scope), a clean main still passes (no delta), fail-closed is
preserved (no active authorization covers nothing), control-plane and
unauthorized paths still fail, and the frozen scope remains the first-class
check.  The consultation was verified: `policy/predicates.py` (an R7-CORE-001
scope path) is covered; `spec/architecture.md`, `.github/workflows/x.yml`
and out-of-scope paths are not.

## 7. Out-of-scope discipline (nothing else changed)

The M012 delta contains exactly: `comos/` (5 new modules),
`tools/comos_selftest.py` (new), `docs/M012-evidence.md` (new) — 7 files.  No
control-plane surface, no `spec/` file, no `.github/` file, no canonical
domain file (`contracts/`, `offers/`, `usage/`, `commercial/`,
`developerapi/` — consumed, never modified), no sibling battery
(`tools/sharenet_selftest.py`, `tools/roamlink_selftest.py` — both re-run
green on this head, untouched), no W048 material, no historical record.  The
drift guard classifies the delta implementation-only; the provenance gate
verifies full coverage by R7-CORE-001's declared scope (the `comos/`,
`tools/` and `docs/M012-evidence.md` prefixes).

## 8. Evidence classes (honest disclosure)

- All M012 acceptance criteria (the 6-step vertical flow, the step-2
  selection paths, the step-4/step-5 coupling, the step-6 attribution and
  boundary): **SOFTWARE** class — the deterministic, offline, seeded
  simulation battery (comos 33/33) over the accepted canonical surfaces
  with the pending children's mechanics disclosed as simulation seams.
- The simulation seams are disclosed AS SEAMS: M004 (eligibility/policy),
  M005 (evidence/assurance), M006 (execution plans) and M007
  (realization/adapters) are NOT delivered by this work item; their
  mechanics are deterministic test doubles whose outputs are labeled
  simulation material.  No claim is made anywhere that the real children
  are delivered.  M008 has no step in the frozen COMOS flow and is
  deliberately absent — never composed, never claimed.
- Physical-world obligations (real gateway hardware, real provider
  networks, real communication traffic): **NOT-TESTABLE/OPEN** — M012
  creates and closes none; EVID-002..EVID-008 remain open and untouched.
  No SOFTWARE evidence is converted into PHYSICAL PASS anywhere in this
  delivery; the delivered-quantity schedule is injected fixture DATA, and
  the execution-status classifications are honest lifecycle derivations,
  never physical-connectivity claims.

## 9. Delivery provenance

- Branch: `m012-comos-proof` from the live main head `52b76ee` (the
  DEC-0111-accepted head, inspected per the live-main rule; descends from
  the R7-CORE-001 activation baseline `1e5c55f` and carries the accepted
  M010 and M011 sibling deliveries); append-only commits; zero file
  overlap with the M010 (`sharenet/`) or M011 (`roamlink/`) deltas.
- Battery on the delivery head: `comos_selftest` 33/33 — green on
  consecutive runs (exit-code-based verification).
- Canonical-domain batteries on the delivery head: `contract_selftest`
  54/54, `offer_selftest` 49/49, `developerapi_selftest` 56/56,
  `usage_selftest` 53/53, `commercial_selftest` 41/41 (consumed, never
  modified).  Sibling vertical batteries: `sharenet_selftest` 33/33,
  `roamlink_selftest` 56/56.
- Gates on the delivery head: `current_spec_check`, `tech_lead_guard`,
  `architecture_drift_guard` (implementation-only),
  `fresh_session_check --actual-main-sha`, `authorization_provenance` —
  see the PR body for the recorded outputs.
- Full suite: the entire blocking battery set green on the delivery head
  in the exact `.github/workflows/spec-check.yml` order (including the
  PR-only management and simulator batteries); the sole remaining
  tolerated skip is the DEC-0099-disclosed client battery (containment
  surface gone — M014 track).
