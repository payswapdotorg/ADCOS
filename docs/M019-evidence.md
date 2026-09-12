# M019 — Resilience Convergence and Scale Hardening — Evidence Record

**Work Item:** M019 · **Authorization:** R8-CORE-001 (DEC-0114, the bounded R8 program
authorization; M019 is the R8 charter's current chain child per DEC-0117 — the
convergence child, THE R8 gate completion carrier)
**Baseline:** `28b31500a928f2f75582bfb79039e315187d72b2` (the DEC-0109 R7-completion head,
per the authorization record; the branch rides the DEC-0117 M017-acceptance head
`d16093d9f60bd9f7824774f35d07be928abd1bc6` — the current main)

This record persists the verified facts of the M019 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed or implied,
and EVID-002..EVID-008 remain open and untouched.

**Acceptance status (the charter's overlay rule, stated honestly):** M019's acceptance
is BLOCKED until the chain-independent M018 lands. This delivery is the parallel
preparation the charter explicitly permits ("parallel preparation is permitted but never
falsely claimed as acceptance"); the PR may open before the M018 acceptance — the Tech
Lead sequences the MERGE after it. Nothing in this record claims the M019 acceptance,
the M018 delivery, or the R8 gate completion; §8 composes the completion-review material
from repository citations for the Tech Lead's DEC-0119 decision.

**Main advancement during delivery (the parallel-delivery note in action, disclosed
exactly):** while this PR was in flight, main advanced past the branch root — the
parallel M018 delivery (PR #42, branch `m018-credentials`, merge `e037ca8`) landed
with `credentials/` + `tools/credential_selftest.py` + `docs/M018-evidence.md`. The
consequences, disclosed precisely: (a) this branch does NOT rebase onto the advanced
main (the charter's rule; the scopes are disjoint and the merge is clean — verified
by a local simulation of the exact merge: every battery green on the merged state,
§6); (b) the M018 credential CI step's existence guard ACTIVATES on the merged PR
checkout (the battery runs 32/32 green there — verified locally); (c) the
`fresh_session_check` CI step fails on the merged checkout with
"main advanced beyond the snapshot 438acb66 with implementation-domain changes
(baa28dab: credentials/__init__.py); reconcile the execution-state snapshot before
implementation" — a GOVERNANCE-STATE condition that is identical at the live main
head with ZERO delta of this delivery (verified by direct execution at `e037ca8`):
the M018 merge landed before its DEC-0118 acceptance reconciliation commit, and the
snapshot reconciliation (the execution-state/roadmap/ledger update) is the Tech
Lead's governance action, outside this delivery's declared scope (`spec/` is
control-plane). Reported with evidence on the PR; never patched silently. The step
goes green when the DEC-0118 acceptance governance commit lands on main — which is
exactly the sequencing this PR's merge already waits for.

**Resolution (observed and verified):** the DEC-0118 acceptance governance commit
landed on main (`6da2c3c` — "Governance: DEC-0118 — accept the M018 delivery
(chain-independent), unblock the current child M019"; the roadmap advanced to v2.15;
M018 recorded ACCEPTED with reviewed head `dba0e9a` and acceptance merge `e037ca8`;
M019 recorded UNBLOCKED — all its declared dependencies accepted). The
`fresh_session_check` step now PASSES on this PR's merged checkout state (verified
by direct execution on a local simulation of the exact merge with the reconciled
main: the full suite 71/71 green — the M018 credential battery included at 32/32).

## 1. Delivered surface

- **`resilience/convergence.py` (NEW, 2879 lines)** — the R8 convergence surface in the
  M015-owned shared prefix, three composed surfaces:
  - **The end-to-end resilience drill** (fault -> detect -> replan/failover -> recover
    -> reconcile): `run_fault_phase` drives the deterministic fault injection (the typed
    `FaultRecord` naming the lost realization verbatim — the WORK-012 member shape), the
    LOCK-106 detection observation (the frozen `health-state` metric, the NOT_RUNNING
    ordinal 3 — the same frozen class the accepted M017 drill uses for its plane-loss
    observations), and the accepted `resilience.failover.orchestrate_failover` (the
    consumed M008 kernel validates every alternative against the contract's FULL
    hard-constraint set — LOCK-108; the adopted realization lands through the EXPLICIT
    reconnect pair naming BOTH the old AND the new references); the failover outcome is
    attested on the evidence plane (controller-verified: adopted, or the honest disclosed
    non-adoption). `assemble_convergence_drill` composes the accepted M016 offline phase
    and the accepted M017 drill result and VERIFIES the convergence verdict: the LOCK-108
    trail (the contract's OWN `hard_constraint_fingerprint` re-verified equal at every
    phase boundary — fault, detect, replan-failover, offline-operation, recover,
    reconcile), and the LOCK-106 citation chain (the detection observation, the failover
    attestation, and every accepted M017 drill evidence record must RESOLVE on the
    evidence plane — a broken chain fails closed, never a silent pass).
  - **The converged-domain compatibility matrix over the R8 domains**: the accepted
    `upgrade/convergence.py` matrix discipline (the additive-evolution `MAJOR.MINOR`
    grammar, the frozen six-value verdict vocabulary, sorted domain iteration,
    input-order independence, byte-stable digests, the fail-closed missing/mismatch
    rows) extended onto the R8 domain labels — `R8_CONVERGENCE_DOMAINS = (localfirst,
    recovery, resilience)` (the accepted R8 chain children; `credentials` is deliberately
    NOT a member — the in-flight M018 child is never claimed). The R7-substrate rows
    ride the COMPOSED matrix as the accepted engine's own serialized verdicts (DATA,
    consumed by reference at runtime); `compose_convergence_matrix` validates every
    substrate row against the accepted verdict member set and refuses any R8 label on
    the substrate rows.
  - **The federation-scale convergence over the R8 domains**: the accepted
    `scale/convergence.py` harness discipline extended — `FederationScaleBounds` (the
    DECLARED deterministic envelope: the world shape, the citation and revocation
    counts, the per-domain per-tick rate limit, and the topology-PREDICTED propagation
    round bound per revoked citation) and `verify_federation_scale_convergence` over the
    accepted harness run consumed by reference at runtime: the byte-identical replay
    (the two runs' digests compared), the world/citation/revocation envelopes, and
    observed == declared-predicted round counts (fail closed on divergence — the
    LOCK-111-class convergence bound). The composed `FederationScaleConvergence` report
    carries the accepted run digest VERBATIM (never recomputed).
- **`resilience/__init__.py` (ADDITIVE ONLY)** — the convergence module's exports
  appended to the package public surface; the M015-accepted surface stays frozen
  (verified by the battery: the M015 `__all__` prefix is byte-identical and in the
  accepted order; nothing was modified, removed, or reordered).
- **`tools/scale_selftest.py` (EVOLVED — disclosed)** — 45 preserved cases + 8 new
  convergence cases = **53/53 PASS** (§3).
- **`docs/M019-evidence.md` (this record)** — the verification matrix + the composed R8
  completion-review material (§8).

## 2. The by-reference composition map (the M014 discipline, disclosed)

Every R8 child authority and every crossed R7 authority is consumed BY REFERENCE —
import and compose, never reimplemented, weakened, forked, or bypassed. The composition
has TWO mechanically distinct forms, both the house style, chosen by the frozen one-way
import boundary:

- **Direct imports** (the authorities at or below this prefix in the one-way dependency
  DAG — the sanctioned import set the accepted M015 battery audits for EVERY file under
  `resilience/`): `contracts/` (the canonical authority, the contract's own LOCK-108
  fingerprint), `replan/` (the M008 kernel decision records and the tie-break key
  vocabulary), `executionplans/` (the M006 plans), `evidence/` (the LOCK-106 typed
  records and the append-only `EvidenceStore` — the evidence plane), `protocol/` (the
  canonical JSON + temporal machinery), and this package's own M015 runtime
  (`RuntimeStore`, `orchestrate_failover`, `DriveResult`).
- **Duck-typed runtime consumption** (the authorities ABOVE or BESIDE this prefix in
  the one-way DAG — importing them would create the package cycles the accepted
  batteries' one-way import checks forbid): `localfirst/` (the M016 authority views and
  the offline journal state — consumed through their OWN public surfaces:
  `.state()`, `.realization_refs()`, `.constraint_fingerprint`), `recovery/` (the M017
  `DrillResult` and its reconciliation — `.drill_run_id`, `.recovery_points`,
  `.restorations`, `.reconciliation.outcome/.constraint_fingerprint/
  .evidence_record_ids`, `.measured_counts`, `.completed_at`), `upgrade/` (the accepted
  matrix's serialized verdict rows), and `scale/` (the accepted harness run result —
  `.run_digest`, `.citation_count`, `.revoked_citation_count`, `.propagation`,
  `.ledger_digests`). This is EXACTLY the discipline `federation/convergence.py`
  established in M014 for the accepted child authorities it cannot import (the
  `cite_offer`/`cite_execution_plan`/`cite_replan_decision` duck-typed records): the
  accepted objects' own code runs and their own gates fire on every consumed value;
  this surface only reads their outputs. The battery (`tools/scale_selftest.py` — the
  M019-owned evolution surface, where no import audit applies) is the composition root
  that wires the accepted M016/M017/upgrade/scale/federation engines into the module's
  surface — the work item's own words: "the drill/matrix/harness cases live in the
  battery; the module provides the surface".

The end-to-end drill's full composition sequence (all driven deterministically,
injected instants only — the battery's `_full_convergence_drill` fixture):

| Phase | The accepted surface driven | The gate that fires |
|---|---|---|
| fault | the M015 runtime read (`realization_refs`) — the fault names the lost realization verbatim | the WORK-012 member shape (structural) |
| detect | the accepted `evidence.ObservationEvidence` + `EvidenceStore.ingest` | the LOCK-106 typing + the acceptance gate |
| replan/failover | the accepted `orchestrate_failover` (the consumed M008 kernel + the M006 plan gate) | LOCK-108 (the kernel validates every alternative against the contract's full hard-constraint set), LOCK-111 (the declared tie-break), WORK-012 (the explicit reconnect pair) |
| offline-operation | the accepted M016 `sync_authority_view` + `open_partition` + `local_admit` (battery-driven) | the M016 freshness/LOCK-108 admission gates; the M015 degraded-entry discipline |
| recover | the accepted M017 `run_drill` (snapshot -> loss -> restore -> verify) | the M017 fail-closed point verification, the LOCK-106 observations/attestations, the RTO operation-count budget |
| reconcile | the accepted M017 `reconcile_planes` (the M016 resync drive + the cross-plane reconciliation) | the M016 LOCK-108 fingerprint gate, the composition-link and evidence-preservation gates |

## 3. The scale battery evolution (45 preserved + 8 convergence = 53/53)

The charter's M019 scope names the disclosed evolution ("`tools/scale_selftest.py` —
the M014 precedent"). Every one of the 45 accepted cases is PRESERVED verbatim (the
delta to the accepted battery is purely appended content: the eight new case functions,
their fixtures and imports, the appended `main()` entries — verified by direct
inspection; no pre-existing case, fixture, or expectation was touched, re-baselined, or
weakened), with ONE disclosed exception — the delta-semantics defect fix on the two
accepted delta-shape cases (case_36/case_37: the two-dot `git diff origin/main HEAD`
replaced by the MERGE-BASE three-dot `origin/main...HEAD` form — the
M018-ratified precedent, commit `687fb82`, accepted under DEC-0118, applied to THIS
battery's own cases after the DEC-0118 governance advancement environmentally tripped
them in a local non-rebased checkout; NO assertion weakened — the spec//.github/
control-plane rejection and the active-authorization coverage checks are unchanged;
see §7 judgment call 7). Eight NEW cases append for `resilience/convergence.py` — the
second disclosed evolution of this battery (39 -> 45 at M014; **45 -> 53 here**):

| Case | Verification | Result |
|---|---|---|
| case_46 | the end-to-end drill: the failover ADOPTED through the explicit WORK-012 reconnect pair (old AND new references; the runtime lands on the adopted realization); the LOCK-108 trail equal at all 6 phases (the contract's own fingerprint); 6 LOCK-106 citations resolve on the evidence plane; the restores byte-exact; the accepted M016 resync preserved; the drill outcome converged; the result round-trips | PASS |
| case_47 | the drill fails closed: 6 rejection classes (the unknown fault kind, the non-increasing phase instants, the attribution mismatch BEFORE any state change, the non-replan-surface runtime — the accepted engine's own gate, the forged LOCK-108 authority view at assembly, the broken LOCK-106 citation chain, plus the recovery result without a reconciliation) | PASS |
| case_48 | the drill determinism: the full composed sequence re-run byte-identically (the composed result, the M017 run, the fault phase); byte-identical digests across PYTHONHASHSEED 0/1/42 subprocesses | PASS |
| case_49 | the R8 matrix: the verdict vocabulary IDENTICAL to the accepted `upgrade.DOMAIN_COMPATIBILITY_VERDICTS` (the by-reference drift guard); the R8 rows classify (additive-gap / compatible / major-mismatch — NO fallback); digests byte-stable and input-order independent; the COMPOSED 16-label matrix carries the accepted engine's R7 rows verbatim (driven through the accepted `negotiate_converged_compatibility`) | PASS |
| case_50 | the matrix fails closed: the unknown domain (incl. the in-flight `credentials` label), the substrate label on the extension record, duplicates, the missing sides (local-missing/peer-missing refuse), the substrate row carrying an R8 label, the malformed substrate row, the R8 rows not covering the full R8 set | PASS |
| case_51 | the federation-scale convergence: the drill's REAL material (the M008 replan decision + the 6 LOCK-106 evidence records) cited through the ACCEPTED `cite_replan_decision`/`cite_evidence_record` constructors, propagated across the accepted 6-domain ring harness with DECLARED bounds (9 admissions, 3 revoked copies, the revocation confirmed in 2 topology-predicted rounds — observed == declared); the replay byte-identical (the accepted `verify_convergence_replay` agrees); the composed report stable across a full re-run; diverging declared bounds and diverging replays fail closed | PASS |
| case_52 | the LOCK-119 discipline: no wall-clock/randomness/network/importlib constructs anywhere in `resilience/convergence.py`; imports confined to the sanctioned set (NO upward imports — the duck-typed composition keeps the one-way import DAG intact); 7 record classes round-trip byte-identically with tamper-evident ids (a tampered drill result fails closed at deserialization) | PASS |
| case_53 | the disclosed-evolution checks: the 45 -> 53 evolution disclosed in the battery source; the M015 package surface ADDITIVE-ONLY (the accepted `__all__` prefix intact); the parallel M018 `credentials/` surface absent at this head and never claimed; the evidence doc honest (the markers + no affirmative physical claims) | PASS |

**Battery result: PASS (53/53 cases), run 3× consecutively, byte-identical.**

## 4. Verification matrix (SOFTWARE class per case)

`python3 tools/scale_selftest.py` — the EVOLVED battery, all 53 cases green, run 3×
consecutively on the delivery head (byte-identical output; exit-code-based
verification — a traceback or lowercase "failed" IS a failure).

| Charter criterion | Battery verification | Class | Case(s) |
|---|---|---|---|
| (1) the R8 convergence surface: every R8 child authority consumed BY REFERENCE (the M014 discipline) | The composition map (§2): the M015 runtime + the accepted contracts/replan/executionplans/evidence imported directly; the M016/M017/upgrade/scale surfaces composed duck-typed at runtime (their own public surfaces, their own gates firing); the battery is the composition root; no accepted authority reimplemented, weakened, forked, or bypassed — the accepted batteries' one-way import audits stay green at their accepted counts | SOFTWARE | case_46, case_51, case_52 |
| (2) the end-to-end drill: fault -> detect -> replan/failover -> recover -> reconcile, deterministic, every hard constraint preserved at each step, every transition evidence-visible | The full sequence over the real accepted surfaces (the adopted failover through the explicit WORK-012 reconnect pair; the byte-exact restores; the converged reconciliation with the accepted resync preserved); the LOCK-108 trail equal at all 6 phases; the 6 LOCK-106 citations resolving on the evidence plane; the determinism in-process and across PYTHONHASHSEED subprocesses | SOFTWARE | case_46, case_47, case_48 |
| (3) the converged-domain compatibility matrix over the R8 domains (the accepted upgrade/ matrix discipline; input-order independent; byte-stable digests) | The verdict vocabulary pinned equal to the accepted set (the drift guard); the R8 classification rows (compatible/additive-gap/major-mismatch with NO fallback); the composed 16-label matrix with the accepted engine's R7 rows verbatim; digests byte-stable and input-order independent; the missing/unknown/forged rows fail closed | SOFTWARE | case_49, case_50 |
| (4) federation-scale convergence over the R8 domains (the accepted scale/ harness discipline extended, declared deterministic bounds) | The drill's REAL R8 material cited through the accepted constructors, propagated across the accepted multi-domain harness; the declared envelopes verified (the world, the citations, the revocations); the topology-PREDICTED round bound observed == declared (fail closed); the byte-identical replay; the composed report stable; diverging bounds/replays fail closed | SOFTWARE | case_51 |
| (5) the scale battery evolution disclosed (the M014 precedent; existing cases untouched; new cases appended) | 45 preserved verbatim + 8 appended (45 -> 53, disclosed in the battery source and here); the M015 package surface additive-only; the accepted resilience battery green at its accepted 36/36 at this head (the new module passes its frozen import audit) | SOFTWARE | case_53 + the accepted batteries re-run (§6) |
| (6) deterministic, offline, seeded; no wall clock, no randomness, no network, no secrets (LOCK-119); canonical-JSON round-trips | The AST audit of the new module (no clock/randomness/network/importlib constructs; the sanctioned import set only); the LOCK-119 secret-shaped rejection at every construction boundary (the module's guards); 7 record classes round-trip byte-identically with tamper-evident ids; the drill determinism across fresh runs and hash seeds | SOFTWARE | case_46, case_48, case_52 |
| (7) the evidence doc composes the R8 completion review from repository evidence (no false completion claim) | This record: §8 composes the per-child repository citations (the decisions, the heads, the battery counts, the M018 in-flight state); no acceptance or gate-completion claim (the overlay status statement above) | SOFTWARE | case_53 + §8 |

## 5. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the convergence surface consumes the accepted
  `contracts/` public surface by reference only; the drill records, matrix rows and
  scale reports cite the contract id, never re-derive contract identity, and never
  write contract state. The authority stays the contract.
- **LOCK-106 (evidence typing):** the drill's evidence records are typed through the
  accepted four-type vocabulary (the detection observation with the frozen
  `health-state` metric; the failover-outcome attestation with the frozen
  `controller-verified` kind — consumed BY REFERENCE); every evidence-visible
  transition resolves on the evidence plane (the assembler's citation gate fails
  closed); the accepted M017 drill's own LOCK-106 records are cited and preserved.
- **LOCK-108 (no silent contract weakening):** enforced through the CONSUMED gates —
  the M008 kernel validates every failover alternative against the contract's full
  hard-constraint set (a weakening candidate is rejected with the typed reason, never
  adopted); the M016 admission and resynchronization gates re-verify the claimed
  constraint sets and the authority-view fingerprints; the M017 reconciliation carries
  the contract's own fingerprint. This surface ADDITIONALLY re-verifies the trail at
  assembly: the contract's own `hard_constraint_fingerprint()` equal at every phase
  boundary (a forged view or a forged reconciliation fails closed
  `resilience-constraint-mismatch`). The convergence records carry no constraint
  material anywhere (structural).
- **LOCK-111 (determinism):** the drill's conflict-resolution rule is the accepted
  declared recorded rule over the consumed M008 key vocabulary; the failover selection
  runs the accepted declared tie-break; the scale convergence bound is the
  topology-PREDICTED declared round count (observed must equal predicted, fail
  closed); the matrix digests are byte-stable and input-order independent.
- **LOCK-117 (authority uniqueness):** nothing here becomes a second contract
  authority — the drill records, the phase citations, the matrix rows and the scale
  reports ride the contract and the accepted planes as opaque references; the
  duck-typed composition never re-types an accepted record (the accepted objects'
  own values ride verbatim).
- **LOCK-118 (provenance):** every record (the drill plan, the fault record, the phase
  results, the composed result, the matrix records, the scale bounds and reports)
  carries typed provenance; the drill's evidence records carry the convergence
  producer.
- **LOCK-119 (secrets):** no wall clock, no randomness, no network, no importlib
  anywhere in `resilience/convergence.py` (AST-audited, case_52); injected instants
  only (the drill plan's non-decreasing phase instants are validated fail-closed);
  content-derived ids over canonical JSON; secret-shaped material rejected typed at
  every construction boundary (the module's LOCK-119 guards); the RTO material stays
  the accepted M017 operation counts (never timing).

## 6. The full suite at the delivery head

The full battery suite in exact CI workflow order with exit-code-based detection —
ALL green at the delivery head (see the PR body for the numbered list). The accepted
batteries run at their accepted counts: resilience 36/36 (the new module passes the
accepted battery's frozen import/clock audits — the additive `__init__` exports change
no accepted case), localfirst 35/35, recovery 36/36, contract 54/54, offer 49/49,
developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33, roamlink 56/56,
comos 33/33, assurance 97/97, executionplan 36/36, adapter 70/70, replan 38/38,
payment 44/44, eligibility 46/46, policy 103/103, client 24/24, conformance 63/63,
scale **45 -> 53** (this delivery's disclosed evolution), and the governance gates:
`authorization_provenance.py` PASS (the delta exactly covered by R8-CORE-001:
`resilience/` — convergence.py + the additive `__init__` exports —
`tools/scale_selftest.py`, `docs/M019-evidence.md`), `current_spec_check.py` PASS,
`tech_lead_guard.py` PASS, `architecture_drift_guard.py` PASS (implementation-only
classification), `fresh_session_check.py --actual-main-sha <origin/main>` PASS. At the
branch root `d16093d` the M018 credential CI step skipped visibly (the pre-delivery
existence guard wired by the DEC-0117 governance commit); after the parallel M018
merge landed on main (see the main-advancement disclosure above), the step ACTIVATES
on the merged PR checkout and its battery runs 32/32 green there (verified locally on
the simulated merge, together with every other battery in this section). After the DEC-0118
reconciliation landed on main (`6da2c3c`), the fresh-session step PASSES on the
merged checkout state (verified locally: the full suite 71/71 batteries green on
the simulated merge with the reconciled main, the M018 credential battery included
at 32/32).

## 7. Judgment calls (disclosed)

1. **The duck-typed composition boundary (the defining judgment call of this
   delivery).** The work item requires `resilience/convergence.py` to compose
   `localfirst/`, `recovery/`, `upgrade/`, `scale/` "imported and composed" — but the
   accepted batteries mechanically forbid ANY file under `resilience/` from importing
   them (the M015 battery's case_33 AST audit allows exactly stdlib + protocol +
   contracts + evidence + replan + executionplans + resilience; the M017 battery's
   case_34 forbids resilience importing recovery; the M016 battery's one-way check
   likewise). These boundaries exist because localfirst/recovery sit ABOVE resilience
   in the one-way dependency DAG (they import it) — a direct import would be a package
   cycle. The resolution is the M014 house pattern applied verbatim:
   `federation/convergence.py` composes the accepted child authorities it cannot
   import through DUCK-TYPED RECORDS (the cite_* functions read the accepted records'
   own public surfaces via their methods — never importing their packages, never
   re-typing their values). `resilience/convergence.py` does exactly that for
   localfirst/recovery/upgrade/scale, and the BATTERY (the M019-owned evolution
   surface, import-unaudited) is the composition root wiring the accepted engines —
   the work item's own instruction: "the drill/matrix/harness cases live in the
   battery; the module provides the surface". No accepted surface is reimplemented
   (the accepted objects' code runs — their folds, their gates, their digests); none
   is weakened (every consumed gate fires at its accepted strength); none is forked
   (the R8 matrix's verdict vocabulary is pinned EQUAL to the accepted
   `DOMAIN_COMPATIBILITY_VERDICTS` by the battery's drift-guard case_49; the R7
   substrate rows ARE the accepted engine's own output). Disclosed as the mechanical
   consequence of the frozen import boundary; NOT treated as a stop condition because
   the composition satisfies the charter's substantive rule (by-reference consumption
   — no reimplementation/weakening/forking/bypassing) through the established M014
   discipline.
2. **The drill's offline and recovery phases are driven by the battery (the
   composition root), not re-driven inside the module.** The module's
   `run_fault_phase` drives the phases it owns (fault/detect/failover — its own
   package's accepted engines plus the importable evidence plane);
   `offline_phase_record`/`recovery_phase_record` read the accepted M016/M017 phase
   results from their own public surfaces; `assemble_convergence_drill` verifies and
   composes. The alternative (the module re-driving open_partition/local_admit/
   run_drill) would require either upward imports (forbidden, judgment call 1) or
   injecting the accepted functions as callables (a weaker, less typed composition).
   The deterministic operation sequence is fully specified by the injected instants
   and the battery's replayable fixture — the same drill inputs produce the
   byte-identical composed result (case_48, including across hash seeds).
3. **The fault vocabulary is one kind (`path-failure`), projecting onto the accepted
   failover trigger `path-failed`.** The charter's fault injection is the failover
   trigger class; a second fault kind (e.g. plane-loss) is the M017 drill's own
   vocabulary and is composed (not duplicated) through the recovery phase. The
   `FAULT_KINDS` vocabulary is fail-closed (an unknown kind is rejected at plan
   construction — case_47).
4. **The R8 matrix covers the R8 labels only; the R7 substrate enters the COMPOSED
   matrix as the accepted engine's own serialized verdicts.** Redeclaring the 13
   accepted labels inside `resilience/` would fork a frozen vocabulary (the upgrade
   package is un-importable here — judgment call 1); instead
   `compose_convergence_matrix` accepts the accepted engine's own verdict DICTS
   (validated against the exact accepted member set) and refuses any R8 label on the
   substrate rows and any incomplete R8 row set. The composed 16-label matrix is
   therefore the union of the accepted engine's output and the extension — the R7
   rows are literally that engine's values (case_49 verifies every R7 row came back
   from the accepted negotiation verbatim).
5. **The declared propagation bound is per distinct revoked citation, not per revoked
   copy.** The accepted harness counts `revoked_citation_count` as revoked LEDGER
   COPIES (one per holder domain) while the propagation record is per citation id;
   the `FederationScaleBounds` carries the declared revoked-copy count AND the
   per-citation predicted-round bounds as separate members, and the verifier checks
   both against the run (case_51: 3 revoked copies, one 2-round bound).
6. **The drill result's LOCK-106 citation chain includes the module-produced records
   AND the accepted M017 drill's records, and the assembler re-verifies their
   presence.** The M017 engine already ingests its evidence into the caller's store;
   the assembler's `evidence_store.has` gate makes the composed drill FAIL CLOSED if
   any cited record is missing from the plane (a broken evidence chain is never a
   silent pass — case_47's empty-evidence-plane probe).
7. **The one modification to an accepted case pair: the case_36/case_37
   delta-semantics defect fix (the M018-ratified precedent).** After the DEC-0118
   governance commit landed on main (the sibling M018 acceptance — main advanced
   past this never-rebased branch's root, as the charter's parallel-delivery rule
   requires), the two accepted delta-shape cases' TWO-DOT form
   (`git diff origin/main HEAD`) began reporting main-side governance files
   (`spec/architect/...`) as though this branch touched them — the exact
   environmental false-negative class the M018 worker documented and the Architect
   ratified the fix for (commit `687fb82`, accepted under DEC-0118: the MERGE-BASE
   three-dot `origin/main...HEAD` semantics — "correct in both environments",
   "no assertion weakened"). Because `tools/scale_selftest.py` is THIS delivery's
   declared evolution surface (the fix is inside the authorized path, not another
   domain's battery), the ratified precedent was applied to this battery's own two
   delta cases and is disclosed here for the DEC-0119 acceptance review. The
   spec//.github/ control-plane rejections, the authorization-coverage checks and
   the Architect-handoff exception are byte-identical in strength; only the diff's
   base changed from "main's tip" to "the merge base" — the delta shape every
   authoritative consumer (the CI provenance step, the charter's own zero-overlap
   instruction) already computes.

## 8. The composed R8 completion-review material (from repository evidence)

This section composes the review material for the Tech Lead's gate-completion decision
(DEC-0119, the DEC-0109/R7 precedent). It composes REPOSITORY CITATIONS only — no
acceptance or completion is claimed here (M019's acceptance is blocked until M018
lands, per the charter's overlay rule; the citations below are the repository's own
records):

- **M015 — Execution Resilience Runtime: ACCEPTED (DEC-0115).** Delivery head
  `95a65a5`, merge `d77a561` (PR #39); the `resilience/` runtime domain composing the
  accepted contracts/, replan/, executionplans/, evidence/ authorities BY REFERENCE;
  the 36/36 resilience battery CI-wired and green (the battery's frozen import audit
  is the boundary this delivery's duck-typed composition preserves — §7 judgment call
  1). Cited from: `spec/architect/authorizations/R8.yaml` (the M015 acceptance
  annotation), `AGENTS.md`, `docs/M015-evidence.md`.
- **M016 — Local-First and Offline Operation: ACCEPTED (DEC-0116).** Delivery head
  `0d5cfb7`, merge `a0ebd019` (PR #40); the `localfirst/` domain composing contracts/,
  replan/, resilience/ BY REFERENCE — the M015 runtime the composition substrate; the
  35/35 localfirst battery CI-wired and green. Cited from: `R8.yaml` (the M016
  acceptance annotation), `AGENTS.md`, `docs/M016-evidence.md`.
- **M017 — Disaster Recovery and State Reconciliation: ACCEPTED (DEC-0117).**
  Delivery head `f016124`, merge `438acb66` (PR #41); the `recovery/` domain composing
  contracts/, resilience/, localfirst/, evidence/ BY REFERENCE; the 36/36 recovery
  battery CI-wired and green; the M018 credential battery's CI existence guard wired
  by the same governance commit. Cited from: `R8.yaml` (the M017 acceptance
  annotation), `AGENTS.md`, `docs/M017-evidence.md`.
- **M018 — Credential and Key Lifecycle Operations: ACCEPTED (DEC-0118; delivery
  head `dba0e9a`, acceptance merge `e037ca8`, PR #42).** At this branch's root
  (`d16093d`) the `credentials/` surface did not exist; while this PR was in flight
  the parallel delivery landed on main and was accepted by the DEC-0118 governance
  commit (`6da2c3c`: the roadmap at v2.15, the 32/32 credential battery recorded
  green at the accepted head, the current-child M019 UNBLOCKED — all its declared
  dependencies M015+M016+M017+M018 accepted; M019's acceptance as DEC-0119 completes
  the R8 gate). This branch's own delta never touches `credentials/` (verified by
  the battery's case_53 against the branch's own delivery files — the parallel
  delivery is never claimed here). With M018 accepted, M019's acceptance is no
  longer blocked by the overlay rule — the acceptance decision itself remains the
  Architect's DEC-0119 from this delivery's repository evidence. Cited from: the
  DEC-0118 governance commit on main (`6da2c3c`), `spec/architect/roadmap.yaml` at
  v2.15, `R8.yaml`, the R8 charter's "### M018" section.
- **M019 (this delivery): the convergence surface delivered, NOT accepted.** The
  end-to-end drill, the R8 matrix, the federation-scale convergence and this composed
  review material are the acceptance-ready material at this head; the acceptance
  decision (the exact reviewed head + merge SHA) is the Architect's alone, sequenced
  after M018.
- **The gate-completion conditions the DEC-0119 decision will verify from the
  repository:** every R8 child accepted (M015+M016+M017 accepted above; M018's
  acceptance pending); the R8-CORE-001 authorization closes only with the gate
  completion (its own `authorization_rules`); the roadmap's R8 activation line
  (`R8_RESILIENCE_MOBILITY_AND_SCALE_ACTIVE`) converts to COMPLETE through the
  governance decision — never through an implementation PR (this delivery touches no
  `spec/` file).

## 9. Out-of-scope discipline (nothing else changed)

The M019 delta (from the DEC-0117 acceptance head `d16093d`) contains ONLY:
`resilience/convergence.py` (NEW), `resilience/__init__.py` (additive exports only),
`tools/scale_selftest.py` (the disclosed evolution — appended content only), and
`docs/M019-evidence.md` (this record). No control-plane surface, no `spec/` file, no
`.github/` file, no protocol schema, and no accepted-domain modification
(`contracts/`, `replan/`, `executionplans/`, `evidence/`, `localfirst/`, `recovery/`,
`upgrade/`, `scale/`, `federation/`, or any other canonical domain — all consumed by
reference only; verified by the battery's import-audit and PR-delta cases and the
provenance gate). The parallel M018 worker's surface (`credentials/`) is untouched by this branch's
own delta (absent at the branch root; present on the advanced main only through the
parallel delivery's own merge — never claimed, never modified here). The CI workflow's M019 wiring decision (NO new existence guard —
the battery is the disclosed evolution of the already-wired
`tools/scale_selftest.py`) was recorded by the DEC-0117 governance commit; this
delivery adds no workflow change.

## 10. Evidence classes (honest disclosure)

- All M019 acceptance criteria: **SOFTWARE** class (deterministic offline battery,
  53/53 PASS on the delivery head; every blocking battery and governance gate in the
  CI suite green on the delivery head).
- No pending child is claimed delivered: the M018 `credentials/` surface does not
  exist at this head and is not faked; its battery does not exist and was not created
  by this delivery. The M019 acceptance and the R8 gate completion are NOT claimed
  (§8 composes the review material only).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M019 creates and closes none;
  EVID-002..EVID-008 remain open and untouched, and no evidence produced by this
  delivery is physical, production, or live-service evidence. No SOFTWARE evidence is
  converted into PHYSICAL PASS.

## 11. Delivery provenance

- Branch: `m019-convergence`, append-only from the DEC-0117 acceptance head
  `d16093d` (the live main at dispatch); no rebase, no force-push, no amending —
  held through the mid-flight M018 merge (`e037ca8`) and the DEC-0118 acceptance
  governance commit (`6da2c3c`) landing on main (the parallel-delivery rule);
  commit-as-you-go delivery history: the module (`60a0285`), the battery + this
  record (`dba1cd6`), the case_53 parallel-delivery precision fix (`9685f3d`), the
  main-advancement disclosure (`ab83a48`), the DEC-0118-resolution amendment +
  the case_36/case_37 ratified delta-semantics fix (the final head).
- Battery: `python3 tools/scale_selftest.py` -> PASS (53/53) on the delivery head,
  run 3× consecutively, byte-identical.
- Full suite: every battery the CI workflow runs, in exact workflow order, on the
  delivery head with exit-code-based detection — see the PR body for the numbered
  results.
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
