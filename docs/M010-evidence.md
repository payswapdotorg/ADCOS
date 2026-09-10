# M010 — Vertical Proof — ShareNet: Delivery Evidence

**Work item:** R7 child M010 (Vertical Proofs: ShareNet)
**Authorization:** R7-CORE-001 (bounded R7 program authorization, DEC-0101)
**Dependency:** M013 Developer Connectivity API — accepted (DEC-0113, chain-independent)
**Delivery class:** SOFTWARE vertical proof (deterministic simulation/emulation battery)
**Frozen flow:** `spec/integration/vertical-proof.md` §ShareNet (ACR-014 FROZEN)

---

## 1. What was delivered

| Artifact | Path | Role |
| --- | --- | --- |
| Vertical harness package | `sharenet/` | The 8-step ShareNet vertical proof: external application boundary, disclosed simulation seams, attributable evidence ledger, scenario driver |
| Battery | `tools/sharenet_selftest.py` | 33-case deterministic, offline verification of the frozen flow, both failure paths, LOCK-108, step-8 attribution, determinism, and the delivery delta shape |
| Evidence doc | `docs/M010-evidence.md` | This document |

The delta is implementation-only and confined to the declared scope
(`sharenet/`, `tools/sharenet_selftest.py`, `docs/M010-evidence.md`);
the drift guard classifies it independently.

## 2. Composition map (the authoritative disclosure)

### 2.1 Real accepted authorities (composed through public surfaces ONLY)

| Authority | Acceptance | How the vertical uses it |
| --- | --- | --- |
| `contracts` (M002 Connectivity Contract Core) | DEC-0102 | The canonical `ContractStore` is the ONLY contract writer: create → select-offers → activate → bind-artifact → record-execution-activation → record-delivery → record-assurance → fail / record-usage-final → record-settlement-pending → record-settled all go through its public command surface |
| `offers` (M003 Offers and Provider Capability Exchange) | DEC-0103 | The canonical `OfferExchange`: both provider domains advertise capability-grounded offers; the eligible offer references ride the M003 bridge shapes (`offer_reference`) verbatim |
| `developerapi` (M013 Developer Connectivity API) | DEC-0113 | The canonical application boundary: ShareNet is modeled as an EXTERNAL application over the `DeveloperApiClient` SDK (+ the raw public request form for webhook endpoint registration); the observation channel is the M013 webhook platform |

### 2.2 Disclosed deterministic simulation seams (PENDING children — never authorities)

The six seams are registered in the single disclosure registry
`sharenet.seams.SIMULATION_SEAMS` (battery case 17). Every seam
produces DATA only, never mutates the canonical contract, and every
canonical mutation still goes through the real command surface.

| Seam | Stands in for | Status at this head |
| --- | --- | --- |
| `EligibilitySeam` | M004 Eligibility and Policy | PENDING DELIVERY — simulated |
| `AssuranceSeam` | M005 Evidence and Assurance | PENDING DELIVERY — simulated |
| `ExecutionPlanSeam` | M006 Execution Plan (LOCK-109 bridge) | PENDING DELIVERY — simulated |
| `ProviderRealizationSeam` | M007 provider realization plane | PENDING DELIVERY — simulated |
| `ReplanEngine` | M008 Replan and Failover (LOCK-108) | PENDING DELIVERY — simulated |
| `UsageObservationSeam` | M009 Usage and Commercial Reconciliation | PENDING DELIVERY — simulated |

**No claim is made anywhere in this delivery that M004/M005/M006/
M007/M008/M009 real child semantics exist, are accepted, or are
exercised.** When those children are accepted, the seams must be
re-composed onto their real authorities (fail-loud by review, never
silently).

## 3. The frozen 8-step proof map

The harness (`sharenet.vertical.ShareNetVertical.run()`) drives the
exact ACR-014 flow; battery cases 03–13 verify each step:

| Frozen step | How the harness proves it | Battery |
| --- | --- | --- |
| 1. ShareNet submits a technology-neutral connectivity intent for gateway/relay nodes | The `ShareNetApplication` submits the audited creation core through the M013 SDK; the canonical contract is created in INTENT state with the APPLICATION principal (LOCK-102/103/114; member audit rejects mechanism names fail-closed) | case_04, case_22 |
| 2. At least two provider domains advertise offers | Two canonical NodeID provider domains register real capability advertisements and offers on the real M003 exchange | case_05 |
| 3. ADCOS evaluates eligibility and evidence | The M004 seam evaluates the REAL offers against the REAL hard constraints (LOCK-108 kernel: present-and-violating → rejection trail); un-provenanced offers are ineligible (LOCK-118) | case_06, case_16 |
| 4. ADCOS creates one connectivity contract | Exactly ONE contract identity: the eligible offer references bind once (INTENT → OFFER_SELECTED) and activation completes the formation; the fold holds one contract for the whole scenario | case_07 |
| 5. ADCOS executes via one or more providers | The M006 seam plans over the accepted offers; the primary realization's artifact binds as DATA (LOCK-117); record-execution-activation, record-delivery and compliant assurance land on the canonical journal | case_08, case_15 |
| 6. A provider realization degrades or fails | BOTH paths: degradation → explicit DEGRADED state via record-assurance(degraded); failure → honest unknown-stale observation (evidence-class honesty — never compliant by inference) | case_09, case_10 |
| 7. ADCOS replans/fails over without weakening hard contract constraints | The M008 seam evaluates candidates against the UNCHANGED constraint set (byte-identical before/after snapshots); recovery binds the failover artifact under the SAME contract; when no candidate qualifies, LOCK-108 fail-closes: FailContract with the rejection trail | case_11, case_12 |
| 8. Usage and assurance evidence remain attributable to the contract | The M009 seam observes usage (DATA + settlement reference, LOCK-113); the evidence ledger records typed entries (LOCK-106) bound to the canonical fold; attribution holds in every scenario INCLUDING after terminal failure | case_13, case_26, case_30 |

## 4. The three golden scenarios

| Scenario | Step 6 | Step 7 | Terminal | Evidence |
| --- | --- | --- | --- | --- |
| `degraded-recovery` | primary realization degrades → DEGRADED | failover to the second provider under the SAME contract; DEGRADED → ASSURED | SETTLED | 2 usage + 3 assurance entries |
| `failed-recovery` | primary realization dies → unknown-stale (no state change) | failover to the second provider; closed-loop assurance continues | SETTLED | 2 usage + 3 assurance entries |
| `terminal-failure` | primary realization dies → unknown-stale | LOCK-108 fail-closed: the only remaining candidate violates the hard latency bound; contract FAILED with the rejection trail | FAILED | 2 usage + 2 assurance entries (attribution survives terminal failure) |

The exact canonical journal chains are pinned by battery case 18;
byte-stable digests in-process and cross-process by cases 19–20.

## 5. Verification matrix (SOFTWARE class)

All verification is deterministic, offline, reproducible
(LOCK-119: injected instants, no wall clock, no randomness, no
network, no secrets; PYTHONHASHSEED-safe).

| Verification | Result |
| --- | --- |
| `python3 tools/sharenet_selftest.py` (3 consecutive runs) | **PASS 33/33 ×3** (exit 0) |
| `python3 tools/contract_selftest.py` (M002, unchanged) | **PASS 54/54** |
| `python3 tools/offer_selftest.py` (M003, unchanged) | **PASS 49/49** |
| `python3 tools/developerapi_selftest.py` (M013, unchanged) | **PASS 56/56** |
| Full CI-order battery suite (per `.github/workflows/spec-check.yml`, PR event class) | **0 hard failures** — the only tolerated non-zero exits are the disclosed DEC-0099 era-superseded skips (`payment`, `eligibility`, `client` — guarded to exit 0 with visible SKIPs) and the standing legacy `spec_check.py` continue-on-error audit (baseline pinned by its own selftest) |
| `python3 tools/authorization_provenance.py` | **PASS** (R7-CORE-001 scope covers the delta) |
| `python3 tools/current_spec_check.py` | **PASS** |
| `python3 tools/tech_lead_guard.py` | **PASS** |
| `python3 tools/architecture_drift_guard.py` | **PASS — implementation-only delta** |
| `python3 tools/fresh_session_check.py --actual-main-sha <origin/main>` | **PASS** |

**Evidence class: SOFTWARE.** EVID-002..EVID-008 (the physical
obligations) remain OPEN and untouched by this delivery; nothing here
converts software evidence into PHYSICAL PASS.

## 6. Lock-conformance mapping

| Lock | Conformance (battery case) |
| --- | --- |
| LOCK-101 canonical contract | Every contract mutation goes through the real `ContractStore` fold (case 14, 18) |
| LOCK-102 intent independence | The intent spec is technology-neutral; the member audit rejects mechanism names fail-closed (case 22) |
| LOCK-103 application purchasing | The ShareNet APPLICATION principal sponsors bounded DEVICE beneficiaries (case 04) |
| LOCK-104 provider sovereignty | Providers advertise their own grounded offers; nothing mutates provider material (case 05, 28) |
| LOCK-105 no global topology | The harness consumes the exchange's offer listings only; no topology is composed (case 01, 05) |
| LOCK-106 evidence typing | Usage observations and assurance evaluations are distinct frozen kinds; scalar payloads (case 26) |
| LOCK-107 closed-loop assurance | Assurance observations accumulate across the lifecycle, including post-failover (case 09, 10, 23) |
| LOCK-108 no silent contract weakening | The failover decision carries byte-identical constraint snapshots; the terminal path fail-closes with the rejection trail; the raising form refuses to weaken (case 11, 12) |
| LOCK-109 execution bridge | The plan seam translates contract → segments as DATA; artifacts bind through the canonical command (case 08) |
| LOCK-110 adapter isolation | AST audit: no provider SDK types, no network modules (case 02) |
| LOCK-113 commercial separation | Usage is DATA + settlement reference; no payment surface in the tree (case 27) |
| LOCK-117 authority uniqueness | Execution artifacts bind as opaque references; no artifact-to-authority path exists (case 15) |
| LOCK-118 provenance | Offers, commitments, evidence entries and accepted-offer references all carry issuer + provenance (case 28) |
| LOCK-119 secrets | AST audit + determinism: no wall clock/randomness/UUID/network/secret literals; cross-process byte-stable digests (case 02, 19, 20) |
| LOCK-120 vertical proof | ShareNet holds no ADCOS authority: its boundary imports only the M013 public surface and references no canonical store/exchange (case 21, 32) |

LOCK-111 (optimizer replaceability) and LOCK-112 (standard
leverage) are structurally satisfied by absence: the harness adds no
optimizer and no new mechanism surface — the vertical flow rides the
canonical surfaces and disclosed seams only.

## 7. Judgment calls (disclosed)

1. **Seams, not authorities.** The pending M004/M005/M006/M007/M008/
   M009 mechanics are deterministic, clearly-labeled simulation seams
   (`SIMULATION_SEAMS`). This is the ONLY way to prove the frozen
   vertical flow end-to-end today without pretending pending children
   are delivered. The battery audits the registry (case 17) and the
   import discipline (case 01): the harness tree imports no pending
   child domain.
2. **Step 4 = ONE contract identity.** The frozen flow's "creates one
   connectivity contract" is proven as: exactly one contract identity
   carries the entire flow (intent → offers → activation → execution
   → failure → failover → attribution). Failover happens UNDER the
   same contract (new execution artifact bound); renegotiation (a new
   contract referencing a superseded one) is deliberately NOT
   exercised — it is not part of the frozen ShareNet flow.
3. **Assurance continuity vs. state transitions.** The M005 seam
   observes continuously (every observation lands in the evidence
   ledger); the canonical `record-assurance` command is applied
   exactly where the frozen M002 lifecycle admits the transition.
   From ASSURED, a post-failover compliant observation is ledger
   evidence only (LOCK-107 closed-loop, no no-op state command).
   A dead realization is observed as `unknown-stale` — never
   compliant by inference.
4. **LOCK-108 kernel semantics.** `evaluate_constraint` returns
   True / False / None: present-and-satisfying, present-and-VIOLATING
   (the rejection trail — a commitment that exists but violates the
   bound), and uncommitted (abstention). Fail-open never happens on
   violating data; abstention never converts into a pass.
5. **Replan candidate scope.** The M008 seam considers the
   contract's accepted offers first, then the other live advertised
   offers (as an M008-era replan may). In the terminal scenario the
   second provider's offer is advertised but was REJECTED at step 3
   (constraint violation); at step 7 the replan re-evaluates and
   re-rejects it against the UNCHANGED constraints — the same
   violation, the LOCK-108 trail, and the contract fails closed.
6. **Physical obligations stay open.** No claim in this delivery
   touches EVID-002..EVID-008; the SOFTWARE evidence class is stated
   everywhere evidence is stated.
