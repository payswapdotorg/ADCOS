# M024 — Future Access Convergence — Evidence Record

**Work Item:** M024 (R9 child #5 — the convergence child; requires M020+M021+M022+M023,
ALL FOUR satisfied by DEC-0121/DEC-0122/DEC-0123/DEC-0124)
**Authorization:** R9-CORE-001 (DEC-0120, the bounded R9 program authorization; M024 is
the R9 charter's convergence child — the FINAL child, whose acceptance completes the R9
gate, the terminal roadmap gate, and evaluates the program_exit conditions).
**Baseline:** the branch `m024-convergence` rides the DEC-0124 M023-acceptance head
`dee77954e78653fd586ef5e277a76aecded2c3ff` (the live main; `git rev-parse HEAD` verified
equal before any work — APPEND-ONLY from there: never re-rooted, never rebased, never
force-pushed, never amended).

This record persists the verified facts of the M024 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed or implied,
and EVID-002..EVID-008 remain open and untouched (§8).

**Solo-worker note (the charter's worker policy):** this is the FINAL R9 child — no
parallel workers remain (M020/M021/M022/M023 are all ACCEPTED on main under
DEC-0121/DEC-0122/DEC-0123/DEC-0124); all four are composed BY REFERENCE. Main did not
advance past the baseline during the delivery (the dispatch head equals the live main;
verified at every commit).

## 1. Delivered surface

**The M024 convergence surface — 3 files, all NEW (the delta touches ONLY the declared
M024 scope; `git diff --name-only origin/main...HEAD` = exactly these three):**

1. **`accesstech/convergence.py`** — the R9 convergence module under the M020-owned
   shared prefix (`accesstech/`, NEW FILES ONLY — the frozen M020 package surface
   `__init__.py`/`envelopes.py`/`ladders.py`/`handovers.py`/`registry.py`/`wireline.py`/
   `satellite.py` imported, never edited):
   - **The cross-technology interchange drill** (`InterchangeHop` /
     `InterchangeDrillPlan` / `InterchangeHopResult` / `InterchangeDrillResult` /
     `run_interchange_drill`): deterministic technology handovers across the three
     access-technology domains of the gate objective — **wireline ↔ radio-family ↔
     non-terrestrial** — with **LOCK-108 VERBATIM constraint-set equality at every
     step**, driven through the ACCEPTED `resilience/` handover machinery
     (`resilience.handover.perform_handover` over the RUNTIME journal). The handover
     candidate is constructed through the accepted
     `resilience.handover.handover_candidate` with `tuple(contract.hard_constraints)` —
     the contract's OWN constraint objects, so **a weakened candidate can never enter
     through this surface** (LOCK-108 by construction); every adopted decision is
     re-verified through the consumed pure cross-authority gate
     `replan.verify_decision_preserves_contract` plus the fingerprint equality with the
     contract's own `hard_constraint_fingerprint()`. Every hop requires BOTH endpoint
     technology classes to be REGISTERED (the accepted `TechnologyRegistry` lookup) and
     BOTH registrations to DECLARE the `cross-technology` handover kind with the
     machinery's own frozen semantics (the full preserved-constraint set, the mandatory
     explicit-reconnect, the mandatory contract continuity). The composed technologies
     are the accepted M021 wireline, M007 radio-family and M022 non-terrestrial
     reference compositions — consumed as `TechnologyRegistration` records resolved
     through the accepted registry (the battery is the composition root mounting them
     through their OWN public factories and the accepted M020 registration surface;
     the module never references the composition modules — the leaf discipline).
   - **The technology REPLACEMENT drill** (the "or replace" half of the gate objective;
     `replace_technology` / `ReplacementRecord`): a LIVE technology replaced by ANOTHER
     technology under an ACTIVE contract with **contract continuity** (the session
     realizes the SAME contract before and after; the contract core never touched).
     Every replacement is an **explicit recorded reconnect naming BOTH the old AND the
     new references** (the WORK-012 discipline the accepted runtime journal enforces
     mechanically, verified typed here) — a replacement that changes nothing, a
     replacement between technologies that never declared the `replacement` kind, and a
     record missing either side of the reconnect pair are all TYPED rejections —
     **never a silent swap**.
   - **The converged-domain compatibility matrix extended over the R9 domains**
     (`R9DomainVersion` / `R9DomainVerdict` / `R9MatrixReport` /
     `classify_r9_domain` / `negotiate_r9_matrix` /
     `AccessConvergenceMatrix` / `compose_access_convergence_matrix`): the ACCEPTED
     `upgrade/` matrix discipline extended onto the R9 domain labels (the frozen
     `MAJOR.MINOR` additive-evolution grammar, the frozen verdict vocabulary —
     import-time-verified against the accepted M019-declared values and pinned against
     the accepted engine's own set by the battery, sorted-domain iteration,
     input-order-independent byte-stable digests, one row per domain with missing sides
     failing closed) — COMPOSED with the accepted upgrade engine's OWN R7-substrate
     serialized verdict rows and the accepted M019 `R8MatrixReport` rows into one
     20-domain converged matrix (fail-closed: no R8/R9 label may ride the substrate
     rows; the R8 rows must cover exactly the R8 set; the R9 rows exactly the R9 set;
     no overlaps).
   - **Federation-scale convergence over the R9 domains** (`AccessScaleBounds` /
     `AccessScaleConvergence` / `verify_access_scale_convergence`): the ACCEPTED
     `scale/` harness discipline extended onto the R9 material — the harness run result
     consumed by reference at runtime (its OWN digests and counts carried verbatim,
     never recomputed), verified against the DECLARED deterministic bounds: the
     byte-identical replay, the world/citation/revocation envelopes, and the
     topology-predicted propagation round counts (observed == declared predicted —
     LOCK-111-class, fail closed on divergence).
   - The live consumed decision records are held BY REFERENCE on the drill results
     (the M020 registry live-objects discipline: identity-bearing canonical content
     serializes; the live in-memory objects never do) so the composition root can cite
     the drill material through the accepted `federation.convergence` cite-*
     constructors.

2. **`tools/accessconvergence_selftest.py`** — the M024 battery (15 cases; the CI step
   wired at the DEC-0124 pre-delivery existence guard ACTIVATES with this delivery):
   see §3.

3. **`docs/M024-evidence.md`** — this record (the verification matrix + the R9 gate
   completion review, §7).

## 2. The by-reference composition map (the M014/M019 discipline, disclosed)

Every consumed authority is imported and composed through its OWN public surface —
never reimplemented, weakened, forked or bypassed:

| Consumed authority | The surface this delivery composes through |
| --- | --- |
| `resilience.handover` (M015) | `handover_candidate` + `perform_handover` drive EVERY interchange/replacement handover; the machinery's own isinstance gates, LOCK-108 kernel validation and journal recording stay in force mechanically |
| `resilience` runtime (M015) | `RuntimeStore` — the drills ride the real journal (`reconnect_evidence`, the explicit reconnect pair); the machinery's silent-replacement gate probed intact |
| `replan` (M008) | `TRIGGER_KINDS` (the frozen trigger vocabulary the plan validates against) + `verify_decision_preserves_contract` (the pure cross-authority LOCK-108 gate re-run on every drill decision) + `ReplanError` (the wrap surface) |
| `resilience.convergence` (M019) | `MATRIX_VERDICTS` (import-time equality — the verdict vocabulary is the accepted discipline's own values), `R8_CONVERGENCE_DOMAINS`, `R8MatrixReport` (the composed matrix's R8 rows are that accepted surface's OWN records, isinstance-gated) |
| `upgrade/convergence` (M014) | the matrix discipline — the grammar/verdict/iteration/digest semantics re-expressed per the M019 precedent (the package's accepted import boundary forbids a direct import); the battery drives the ACCEPTED engine (`negotiate_converged_compatibility`) and passes its OWN serialized verdicts as the composed matrix's substrate rows |
| `scale/convergence` (M014/M019) | the harness discipline — the battery runs the ACCEPTED `run_convergence_scenario` (real `FederationStore` world, citation ledgers, rate-limited admissions, relay-round propagation) and the verifier consumes the run result's OWN digests/counts by reference (duck-typed public surface) |
| `federation.convergence` (M014) | `cite_replan_decision` — the R9 drill material (the interchange/replacement decisions) cited through the ACCEPTED constructors over the REAL records |
| `accesstech` (M020/M021/M022) | relative imports only: the `TechnologyRegistry`/`TechnologyRegistration` records the drills resolve, `declare_handover_kind`'s frozen semantics re-verified per hop, `preserved_constraint_kinds` |
| the four R9 child compositions (M021 wireline, M007 radio-family, M022 satellite, M023 futureimt) | mounted by the battery through their OWN public `mount_*` factories and registered through the accepted `register_access_technology` surface — the module consumes the registration records only (the leaf discipline; never a family runtime) |
| `protocol` | canonical JSON + injected-instant conventions |

One-way imports verified (battery case_09): the module imports ONLY
`protocol`/`replan`/`resilience` + the package's own relative surface + stdlib —
**ZERO contracts imports** (the M020 zero-contract-import discipline preserved: the
contract object is consumed through the machinery's own isinstance gates, this surface
duck-checks the public members only); NO accepted authority references the new module;
the module never references the M021/M022/M023 composition modules by name.

## 3. The M024 battery (15/15)

`python3 tools/accessconvergence_selftest.py` — **15/15 cases green, run three times
consecutively with byte-identical logs** (sha256-verified), plus the full material
byte-identical across `PYTHONHASHSEED` 0/1/42 subprocesses (case_13). SOFTWARE class
only:

| Case | Verified (deterministic expected outcome) |
| --- | --- |
| case_01 | the interchange plan declarations: the full domain circle (wireline → radio-family → non-terrestrial → wireline), end-to-end class chaining, strictly increasing injected instants, content-derived tamper-evident identity; 7 malformed-plan classes typed |
| case_02 | **the interchange drill through the accepted machinery**: all 3 hops LOCK-108 verbatim (the fingerprint IS the contract's own; the consumed cross-authority gate green on every live decision); the EXPLICIT reconnect pair naming BOTH old AND new references at the declared instants; ACTIVE landings; the journal reconnect evidence chained; contract continuity; the result canonical and tamper-evident |
| case_03 | the interchange fail-closed probes: the machinery's weakened-candidate discipline (typed kind-citing rejection, EXPLICIT FAILED landing, zero silent reconnects), the machinery's silent-completion gate (`resilience-silent-replacement`), and the drill's own typed gates (unregistered class, undeclared cross-technology kind, wrong-contract) |
| case_04 | **the replacement drill**: the live radio technology replaced by the accepted M023 future-IMT composition under the active contract — contract continuity (the session on the SAME contract before/after; the contract store state and bytes unchanged), the EXPLICIT recorded reconnect naming old AND new references, the journal evidence, LOCK-108 verbatim, the record canonical |
| case_05 | the replacement fail-closed probes: the silent-swap record shape, the no-op replacement, the undeclared replacement kind, the contract-breaking record — all typed; the machinery disciplines intact |
| case_06 | the R9 matrix: the verdict vocabulary pinned against the accepted upgrade engine's own set (and the accepted M019 values); compatible/additive-gap/major-mismatch/missing-side classification; input-order-independent byte-stable digests; 3 malformed classes typed |
| case_07 | **the composed converged-domain matrix** over 20 domains (the accepted upgrade engine's OWN R7 substrate rows + the accepted M019 R8 rows + the R9 rows — one row per domain, sorted); input-order independent, byte-stable; 4 malformed classes typed |
| case_08 | **the federation-scale convergence over the R9 domains**: 4 R9 material citations (the interchange + replacement decisions) through the accepted cite constructors over the accepted 6-domain ring harness; the revocation confirmed in 2 topology-predicted rounds; the replay byte-identical (the accepted harness's own verification agreeing); the composed report byte-stable; diverging-bound/diverging-replay probes typed |
| case_09 | the by-reference composition audit (one-way imports; zero contracts imports; the leaf discipline; the four accepted compositions mounted through their own factories, resolving identity-preserving through the accepted capability seam) |
| case_10 | LOCK-110 provider-SDK isolation (no family-opaque reference in any canonical record byte; no technology-branching names; the mediated seam) |
| case_11 | LOCK-119 purity (no wall-clock/randomness/network anywhere in the module; secret-shaped values rejected typed) |
| case_12 | the typed-error matrix (12 deterministic fail-closed classes across the drills/matrix/scale) |
| case_13 | determinism: in-process rebuild byte-identical + PYTHONHASHSEED 0/1/42 cross-process byte-identity |
| case_14 | zero contract-core delta + authorization scope (the contract bytes/state unchanged through both drills; the PR delta touches no contract file and stays inside R9-CORE-001) |
| case_15 | this evidence record's honesty (SOFTWARE class; the by-reference disclosure; the lock mapping; EVID-002..008 open; the program_exit completion review recorded SOFTWARE-class; no affirmative physical claims) |

## 4. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract)** — the contract stays the sole authority: the
  module imports NO contracts type (battery case_09/case_14 AST-audited); every drill
  realizes exactly its owning contract (the machinery's own contract_id gates plus the
  surface's typed checks); the contract bytes and state are unchanged through both
  drills (case_14).
- **LOCK-105 (no global topology)** — the drill's domain labels, technology classes
  and realization references are declared data bounded by their own declaration; no
  infrastructure facts cross.
- **LOCK-106 (evidence typing)** — every record carries a content-derived identity
  over canonical JSON (the plan, the drill result, the replacement record, the matrix
  digests, the scale report) — tamper-evident at reconstruction (probed).
- **LOCK-108 (no silent contract weakening)** — the core discipline of this delivery:
  the candidate carries the contract's OWN constraint objects VERBATIM (by
  construction); the fingerprint equality is asserted on every decision; the consumed
  cross-authority gate re-runs on every decision; the machinery's weakened-candidate
  and silent-swap gates probed intact (cases 03/05).
- **LOCK-109 (execution bridge)** — the drill technologies register through the
  accepted registration surface carrying the LOCK-109 bridge vocabulary (the accepted
  `REGISTRATION_OPERATIONS` name-equality guard stays in force at import).
- **LOCK-110 (adapter isolation)** — the drills consume registration records; the
  family runtimes stay behind the accepted mediated `CapabilityAdapter` seam; no
  family-opaque reference crosses into any canonical record byte (case_10).
- **LOCK-111 (optimizer replaceability)** — no optimizer strategy is asserted by the
  convergence surface; the scale propagation bounds are declared-and-verified
  deterministic bounds (LOCK-111-class, fail closed on divergence).
- **LOCK-112 (standard leverage)** — the composed technologies are the accepted
  reference compositions over the standards base; the mechanism tags are citation DATA
  (never a branch input — case_10's no-branching scan).
- **LOCK-117 (authority uniqueness)** — the drill/replacement/matrix/scale records are
  DATA around the contract and the accepted planes; nothing becomes a second contract
  authority.
- **LOCK-118 (provenance)** — every record carries its issuer and content-derived
  identity.
- **LOCK-119 (secrets)** — no wall clock, no randomness, no network; injected
  instants only; secret-shaped values rejected typed at every construction boundary
  (case_11).

## 5. The full suite at the delivery head

Full battery suite in the exact CI order of `.github/workflows/spec-check.yml` at the
delivery head, exit-code-based detection (a traceback or lowercase "failed" IS a
failure) — **ALL green at the R9-CORE-001 scope-covered head**:

- The M024 battery `tools/accessconvergence_selftest.py` **15/15** (this delivery; the
  DEC-0124-wired step ACTIVATES — no pre-disclosed red step remains for this
  delivery).
- The accepted R9 batteries at their accepted counts: **accesstech 19/19, wireline
  14/14, satellite 17/17, futureimt 14/14** (DEC-0121/DEC-0122/DEC-0123/DEC-0124) and
  the **adapter battery 70/70** (the case_68 expected-set guard NOT tripped — this
  delivery adds no `adapters/reference/` module, exactly as pre-disclosed).
- The accepted R8/R7 batteries at their accepted counts: resilience 36/36, localfirst
  35/35, recovery 36/36, credential 32/32, scale 53/53, contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, allocation 62/62, payment 44/44,
  eligibility 46/46, policy 103/103, client 24/24, assurance 97/97, executionplan
  36/36, replan 38/38, sharenet 33/33, roamlink 56/56, comos 33/33, conformance 63/63,
  plus the platform/compatibility set (platform 32/32, platformcaps scope-audit PASS,
  schema 25/25, schema_check 8/8, envelope 25/25, identity 19/19, capability 18/18,
  discovery 29/29, topology 33/33, resource 53/53, intent 47/47, routing 80/80,
  session 55/55, multipath 45/45, mobility 43/43, federation 52/52, transport 69/69,
  ipintegration 45/45, networkpath 36/36 (x2 in the order), fivegc 31/31, ran 46/46,
  wifi 36/36, backhaul 48/48, mesh 38/38, distcore 40/40, service 47/47, telemetry
  34/34, energy 38/38, security PASS, upgrade 41/41, management 39/39, simulator
  44/44, agent 45/45, edge 48/48, mobile 45/45, appliance 42/42, oran 36/36, imt
  34/34, marketplace 48/48, experience_check PASS, experience_selftest 8/8,
  spec_check_selftest 9/9).
- The governance gates: `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS with an **implementation-only classification**
  (1 implementation file delta — this delivery's module), `fresh_session_check.py
  --actual-main-sha` PASS (origin/main == the execution-state snapshot
  `dee77954`), `authorization_provenance.py` PASS (the implementation delta —
  `accesstech/convergence.py`, `tools/accessconvergence_selftest.py`,
  `docs/M024-evidence.md` — fully covered by the R9-CORE-001 scope, byte-identical
  authorization inheritance from origin/main).
- The legacy `tools/spec_check.py` compatibility audit stays non-blocking in CI
  (`continue-on-error: true`, the frozen 7/17-clean baseline disclosed by its own
  selftest) — unchanged by this delivery.

**CI:** the PR head run green end-to-end (the run URL recorded in §9).

## 6. Judgment calls (disclosed)

1. **The matrix vocabulary re-declared, not imported** (the M019 precedent):
   `accesstech/`'s accepted one-way import boundary (the M020 battery's frozen audit
   set: `protocol/contracts/replan/resilience/adapters/executionplans` + stdlib +
   relative) forbids importing `upgrade/` directly, so the R9 matrix declares the
   verdict VALUES and verifies them against the accepted M019-declared vocabulary at
   import time (fail-loud drift guard) — exactly the discipline `resilience/
   convergence.py` applied for the R8 matrix; the battery pins the full chain against
   the accepted `upgrade.convergence.DOMAIN_COMPATIBILITY_VERDICTS` directly (case_06).
   Charter reference: the R9 charter Consumption rule ("a disclosed evolution ... of
   an accepted shared battery surface follows the M019 precedent — disclosed,
   append-only in intent"); this is the import-boundary half of that same precedent.
2. **The live decision records ride the drill results as by-reference members**
   (`_decision`, excluded from the canonical projection): the composition root must
   cite the REAL drill material through the accepted federation cite-* constructors
   (the frozen citation authorities admit replan decisions), and the M024 scale
   scenario composes over the drills' own decisions — the M020 registry live-objects
   discipline applied verbatim (identity-bearing canonical content serializes; the
   live objects never do). Charter reference: the M014/M019 convergence discipline
   ("the battery is the composition root").
3. **The engine surfaces machinery rejections as
   `accesstech-handover-illegal`/`accesstech-identity-mismatch` with the deterministic
   text preserved** (exception isolation): the consumed `ResilienceError`/`ReplanError`
   texts are wrapped, never leaked raw into stored state — the M020/M021 wrap pattern.
4. **The future-IMT domain's cross-domain label**: the M023 composition participates
   in the replacement drill as the replacing technology (its class
   `access.3gpp.nr.imt2030` is an IMT radio-class technology); the interchange drill
   itself composes exactly the charter's three families (M021 wireline, M007
   radio-family, M022 non-terrestrial) — the M023 child enters the convergence
   through the replacement drill, the matrix's `futureimt` domain row and the R9
   scale material, never by re-labelling the interchange set.
5. **The battery imports the sibling batteries' public fixtures**
   (`adapter_selftest`/`wireline_selftest`/`satellite_selftest`) for the composition
   root — the accepted case_66 cross-battery import precedent (the M020/M021/M022
   batteries' own pattern), disclosed here.

## 7. The R9 gate completion review (composed from repository evidence — the
program_exit evaluation, SOFTWARE-class only)

R9 is the TERMINAL roadmap gate (`spec/architect/roadmap.yaml`: "next_gate: null ...
the M024 acceptance evaluates the program_exit conditions ... SOFTWARE-class
evaluation only, the open physical obligations EVID-002..EVID-008 recorded as open").
This section composes the evaluation from repository citations — the accepted
decisions, the batteries' accepted counts at this head, and the execution ledger — for
the Architect's M024 acceptance decision. **Nothing here converts SOFTWARE evidence
into PHYSICAL PASS; the open physical obligations are recorded as open (§8).**

### 7.1 The gate sequence R0–R9 (repository citations)

- R0 restored the accepted implementation trees (ledger: `spec/architect/
  execution-ledger.yaml`); M001 — Architecture 1.1 Freeze ACCEPTED (DEC-0100: the
  canonical `spec/architecture.md` + `spec/architecture-lock.md` FROZEN with
  LOCK-101..LOCK-120; ACR-014). R1–R3, R5, R6 complete (current-state projection;
  R4 remains the independent physical-validation track under W040 — recorded open,
  not claimed).
- **R7 — Universal Connectivity Commerce COMPLETE** (DEC-0109): all thirteen children
  accepted — M002 DEC-0102, M003 DEC-0103, M004 DEC-0104, M005 DEC-0105, M006
  DEC-0106, M007 DEC-0107, M008 DEC-0108, M009 DEC-0109, M010 DEC-0110, M011
  DEC-0111, M012 DEC-0112, M013 DEC-0113, M014 DEC-0109 (the R7-CORE-001 program
  authorization CLOSED).
- **R8 — Resilience, Mobility and Scale COMPLETE** (DEC-0119): M015 DEC-0115, M016
  DEC-0116, M017 DEC-0117, M018 DEC-0118 (chain-independent), M019 DEC-0119 (the
  convergence child — the R8-CORE-001 program authorization CLOSED).
- **R9 — Future Access Technology**: M020 ACCEPTED (DEC-0121; PR #44 head 035242de,
  merge c75a7c70), M021 ACCEPTED (DEC-0122; PR #45 head 8966693, merge 8ebdb21), M022
  ACCEPTED (DEC-0123; PR #46 head 16eb274, merge 68060d9), M023 ACCEPTED (DEC-0124;
  PR #47 head 385be97, merge 67d99d1 — chain-independent, the pointer does not move),
  M024 this delivery (the convergence child — the acceptance is the sole Architect's
  decision, recorded as DEC-0125+ at the exact reviewed head + merge SHA per the R9
  charter acceptance rules).

### 7.2 The stripe-of-connectivity test (SOFTWARE-class evaluation)

The test (roadmap `program_exit.stripe_of_connectivity_test`): "An external
application can request connectivity from ADCOS by API, ADCOS can evaluate policy and
eligible offers, reserve capacity, select and validate a path, establish controlled
connectivity, meter delivered usage, finalize billing, allocate economic value,
integrate with an external payment provider, reconcile provider events, and expose
canonical status via API/webhooks — without the application needing an ADCOS UI or
knowledge of the underlying access technology/provider."

Evaluated from repository evidence — every link of the stripe exists as an ACCEPTED
child authority with its deterministic battery green at this head (the counts cited
from §5's full-suite run):

| Stripe link | Repository evidence (ACCEPTED authority + battery at this head) |
| --- | --- |
| request connectivity by API | `developerapi/` 56/56 (M013, DEC-0113); `client/` 24/24 (M014, DEC-0109) |
| evaluate policy and eligible offers | `policy/` 103/103 (M004, DEC-0104); `eligibility/` 46/46 + `offers/` 49/49 (M003, DEC-0103) |
| reserve capacity | `adapters/` 70/70 (M007, DEC-0107 — the WORK-016 reserve/activate/measure operations); `executionplans/` 36/36 (M006, DEC-0106 — the LOCK-109 bridge) |
| select and validate a path | `routing/` 80/80; `replan/` 38/38 (M008, DEC-0108) |
| establish controlled connectivity | `contracts/` 54/54 (M002, DEC-0102 — the canonical authority); `resilience/` 36/36 (M015, DEC-0115 — the handover/realization runtime) |
| meter delivered usage | `usage/` 53/53 (M009, DEC-0109) |
| finalize billing | `commercial/` 41/41 (M009, DEC-0109) |
| allocate economic value | `allocation/` 62/62 (M009, DEC-0109) |
| integrate with an external payment provider | `payment/` 44/44 (M009, DEC-0109 — the external-movement boundary, LOCK-113) |
| reconcile provider events | `assurance/` 97/97 + `evidence/` (M005, DEC-0105 — the closed loop, LOCK-107) |
| expose canonical status via API/webhooks | `developerapi/` webhooks surface 56/56 (M013) |
| no ADCOS UI / no access-technology knowledge | LOCK-102 intent independence + LOCK-110 adapter isolation: the M023 extension drill (14/14, DEC-0124) proved a technology the 1.1 architecture never named enters PURELY as declared data; THIS delivery's interchange/replacement drills prove technologies interchange and replace with the contract core byte-identical (case_14) and LOCK-108 verbatim across every technology change (case_02) |

**SOFTWARE-class verdict (this delivery's contribution): the stripe is complete as
deterministic-battery evidence** — every link is an accepted authority with its
battery green at this head, and the access-technology-neutral composition is proven by
the R9 chain end-to-end (the application-facing surfaces never see a technology
class). **The LIVE-NETWORK halves — a real external application over a real API, real
provider payment integration, real usage metering against delivered traffic — are the
open physical obligations (EVID-002 real SDR topology, EVID-005 the real site
deployment, EVID-006 the real 5G interop lab, EVID-007 real users/devices for the
W040 pilot) and are NOT claimed here; no PHYSICAL PASS is asserted.**

### 7.3 The architecture test (SOFTWARE-class evaluation)

The test (roadmap `program_exit.architecture_test`): "All success and recovery paths
preserve the single-authority model, evidence discipline, least authority,
access-technology neutrality, and graceful degradation requirements."

| Requirement | Repository evidence (cited) |
| --- | --- |
| single-authority model | LOCK-101/LOCK-117: `contracts/` the sole authority — every R7/R8/R9 delivery's zero-contract-core-delta case (M020..M023 evidence docs; this delivery case_09/case_14: the convergence module imports ZERO contracts types and the contract bytes are unchanged through interchange AND replacement); the contract-core scope constraint held across the whole R9 gate (the R9 charter's own objective constraint, an acceptance criterion on every child — DEC-0121..DEC-0124) |
| evidence discipline | LOCK-106: content-derived identities over canonical JSON in every accepted domain (the batteries' round-trip/tamper-evidence cases); the typed evidence records (M005, 97/97) and the closed loop (LOCK-107) |
| least authority | LOCK-104 provider sovereignty + LOCK-105 no global topology: declared data only (the M021 site topology, the M022 pass schedules — LOCK-105 declared data per their evidence docs); LOCK-118 provenance on every externally asserted record |
| access-technology neutrality | LOCK-102/LOCK-110/LOCK-112: technologies enter ONLY through the accepted adapter boundary as declared data — proven in the strongest form by the M023 drill (a technology the architecture never named, ZERO core delta) and by THIS delivery (cross-technology interchange and replacement with LOCK-108 verbatim equality and no technology branching — case_10); the contract core never names a technology |
| graceful degradation | The M008-owned REALIZING/DEGRADED/FAILED/SUPERSEDED kernel preserved everywhere: the R8 recovery paths (M016 offline 35/35, M017 recovery 36/36, M018 credentials 32/32, M019 convergence 53/53), the R9 degradation ladders (M020/M021/M022 — the explicit terminal rungs), and THIS delivery's drills (every handover failure lands the EXPLICIT degraded/failed state or the EXPLICIT renegotiation path — never a silent downgrade; the weakened-candidate probes, cases 03/05) |

**SOFTWARE-class verdict: the architecture invariants hold on every success and
recovery path proven by the deterministic batteries at this head.** The
physical-deployment halves of the recovery paths (real partitions, real site
destruction cycles) are the open physical obligations — recorded open, not claimed.

### 7.4 The program_exit record (for the acceptance decision)

- The gate sequence R0–R9 is complete in the repository evidence with this delivery
  as the final child (§7.1); R4 (the independent physical-validation track under
  W040) remains in-review and separate — the software track never absorbs it.
- Both program_exit tests evaluate **satisfied at the SOFTWARE evidence class**
  (§7.2/§7.3 — composed from the accepted decisions and the batteries' counts at this
  head); **EVID-002..EVID-008 remain OPEN** (recorded as open; never satisfied by
  software evidence — the standing evidence rule).
- The completion itself is the Architect's decision: this review is the evaluation
  input the R9 charter requires the M024 delivery to carry; the R9-CORE-001
  authorization closes only with the recorded acceptance ("the M024 acceptance and
  the completion review with the program_exit evaluation, the DEC-0109/DEC-0119
  precedent" — the R9 authorization record's own closure rule).

## 8. Evidence classes (honest disclosure)

- Every claim in this record is **SOFTWARE class** — deterministic, offline,
  reproducible battery evidence at the delivery head (§3/§5).
- **EVID-002** (real SDR hardware topology for WORK-020), **EVID-003** (Raspberry
  Pi-class physical hardware for WORK-034), **EVID-004** (physical handset-backed
  second-path rebind/handover for WORK-035), **EVID-005** (physical Network-in-a-Box
  at a real isolated site for WORK-036), **EVID-006** (real 5G interoperability lab
  for WORK-037), **EVID-007** (real users and physical devices for the WORK-040
  pilot), **EVID-008** (the physical topology validation) — all remain **open and
  untouched** by this delivery; no battery or evidence doc converts software evidence
  into PHYSICAL PASS; EVID-001 closure is undisturbed.
- The R9 gate completion review (§7) is SOFTWARE-class evaluation only.

## 9. Delivery provenance

- **Branch:** `m024-convergence` (APPEND-ONLY from the baseline `dee77954`; the
  commits carry the module, the battery and this record).
- **Scope:** exactly the R9-CORE-001 M024 scope entries — `accesstech/` (the
  convergence module — the M020-owned shared prefix, new files only),
  `tools/accessconvergence_selftest.py`, `docs/M024-evidence.md`;
  `tools/authorization_provenance.py` PASS at the head (the delta fully covered,
  byte-identical authorization inheritance).
- **Verification at the head:** the battery 15/15 green x3 byte-identical; the full
  suite in the exact CI order ALL green (§5); the gates
  (current_spec/tech_lead/architecture_drift [implementation-only]/
  fresh_session/authorization_provenance) ALL PASS.
- **CI:** the PR head run (the workflow as it exists at this head — the one delivery
  with no pre-disclosed red step): green end-to-end; the run URL recorded on the PR.
