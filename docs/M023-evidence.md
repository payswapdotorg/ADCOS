# M023 — Future Technology Extension Drill — Evidence Record

**Work Item:** M023 (R9 child #4, chain-independent — the M013/M018 precedent class)
**Authorization:** R9-CORE-001 (DEC-0120, the bounded R9 program authorization;
M023 is declared by the R9 charter and the R9-CORE-001 scope list; chain-independent
from the M020-M022 chain — may be accepted in any order relative to it).
**Baseline:** the branch `m023-futureimt` rides the DEC-0121 M020-acceptance head
`fe27c9962f5e5ad4da9b355bf3be1172825bf4fe` (verified `git rev-parse HEAD` equal
before any work — the charter's pinned live-main head at dispatch; APPEND-ONLY from
there: never re-rooted, never rebased, never force-pushed, never amended).

This record persists the verified facts of the M023 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without
direct verification (the standing Tech Lead rule). All evidence in this record is
**SOFTWARE class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed
or implied, and EVID-002..EVID-008 remain open and untouched.

**Parallel-delivery note (the charter's worker policy):** the M021 wireline
delivery was concurrently in flight at dispatch (branch `m021-wireline`) and has
since been ACCEPTED (DEC-0122; merge `8ebdb21`, main advanced to `9ee8611`) —
AFTER the charter and the Tech Lead re-dispatch addendum were written against the
fe27c99 context in which M021 was "concurrently delivering". This delivery's scope
is fully disjoint either way (verified: `git diff --name-only origin/main...HEAD`
— the three-dot delivery delta — contains exactly this delivery's three files and
ZERO overlap with the M021 set; the M021 surface is absent at this branch's base
and never claimed). Per the charter's chain-independence rule this branch does NOT
rebase onto the advanced main: the merge is clean by scope disjointness, and the
governance-state reconciliation beyond the branch's pinned snapshot is the Tech
Lead's own standing convention (the live-main rule).

## 0. Known integration artifact (the Tech Lead addendum's documentation duty)

**The failing case id:** `case_68_m007_work016_compat_seam` in the accepted M007
adapter battery (`tools/adapter_selftest.py`, 70/70 at the DEC-0121 head).

**The exact error line (at the delivery verification contexts — the dispatch
baseline `origin/main == fe27c99` and the PR merge-ref, the CI evaluation point):**

```
[FAIL] case_68_m007_work016_compat_seam                     undeclared adapters/ change: ['adapters/reference/futureimt.py']
```

— the adapter battery reads **69/70 at this head** (exactly the one disclosed
artifact; every other case green). The conflict: case_68 part (d) audits the
`adapters/` delta vs `origin/main` against the declared M007 file set (nine
files); this delivery's charter-scoped `adapters/reference/futureimt.py` is, by
construction, an undeclared member of that diff. This is the same conflict class
the M021 delivery surfaced (its evidence record §0) — empirically confirmed by
the prior m023 session and recorded in the Tech Lead's re-dispatch addendum.

**The sanctioning charter sentence (the R9 charter Consumption rule):** "a
disclosed evolution of an accepted shared battery surface follows the M019
`tools/scale_selftest.py` precedent — disclosed, append-only in intent, never
assertion-weakening".

**The resolution (pre-merge, Tech Lead-owned):** per the re-dispatch addendum,
this delivery does NOT touch `tools/adapter_selftest.py` (the scope discipline
stands unchanged); **the Tech Lead evolves case_68's declared set at the
integration station BEFORE the merge** — the expected-set evolution appends
exactly `adapters/reference/futureimt.py` to the declared M007 set (the M021
`8966693` amendment precedent: append-only in intent, no assertion weakened —
the W016 canonical flow, the 54-name baseline export table, the family export
counts, and the six family-subpackage byte-identity assertions unchanged; the
guard still rejects every other undeclared `adapters/` change). The verification
numbers below disclose the 69/70 artifact explicitly wherever the adapter battery
is cited at this head.

**The pre-existing main-advance artifact class (disclosed, not caused by this
delivery):** at the RAW pre-merge head with TODAY'S live `origin/main` (`9ee8611`,
post-DEC-0122), two further pre-existing failures appear in shared batteries
through main's advance beyond this branch's pinned baseline — the adapter
battery's `case_55_frozen_docs_unchanged` ("spec/ differs from origin/main") and
case_68 additionally naming `adapters/reference/wireline.py` — both verified
PRESENT at the CLEAN fe27c99 checkout with zero delta from this delivery
(adapter battery 68/70 at the clean head with the advanced main ref; 70/70 with
the dispatch-baseline ref). The same class touches the conformance/appliance/oran
frozen-spec cases at the raw head. All of these are green at the dispatch-baseline
context and at the PR merge-ref (the CI evaluation point, where the working tree
carries main's post-advance content); they are governance-state reconciliation
artifacts of main advancing past a chain-independent branch's pinned base — the
Tech Lead's live-main convention — never silent patches by this delivery.

## 1. Delivered surface

- **`adapters/reference/futureimt.py` (NEW — the synthetic future-IMT/6G-class
  reference composition)** — the M023 drill's technology, one the 1.1
  architecture NEVER named, composed ENTIRELY through the accepted public
  extension surface in the EXACT pattern of the accepted M007 reference modules
  (one module per family; `adapters/reference/backhaul.py` /
  `adapters/reference/wifi.py` read first and followed):
  - **`ReferenceFutureImtEngine`** — the module's OWN deterministic reference
    engine (no accepted family runtime exists for future-IMT): a pure function
    of its injected instants implementing the frozen WORK-016 nine-op section
    10.1 `AdapterContract` shape (the `GenericAdapter` composition discipline
    re-expressed on the future-IMT vocabulary — deterministic sequence
    counters, fixed step charges, typed fail-closed rejections, LOCK-119:
    no wall clock, no randomness, no network, no secrets);
  - **`reference_descriptor`** — the reference registration descriptor: the
    technology id `access.3gpp.nr.imt2030` (the WORK-002 registry's own
    RESERVED future path — KNOWN by the open-world classifier's design:
    registered entries of any status classify KNOWN; registration is never
    activation, the entry stays reserved), four capability references
    (`capability.profile.imt2030.terahertz-carrier`,
    `.holographic-latency`, `.adaptive-beam`, `.data-transfer` — all
    UNKNOWN_BUT_WELL_FORMED in the WORK-005 grammar, preserved verbatim), the
    resource mapping (terahertz-carrier bandwidth `bandwidth`/`gbps`/100;
    adaptive-beam associations `coverage`/`count`/8 — WORK-008 kinds/units,
    mapping never accounting), profile version `imt2030-study-1`, and the
    credential SLOT NAME only (LOCK-023/LOCK-119);
  - **`mount_reference`** — the composition root: wires the engine and hands
    back `(implementation, descriptor, binding_requirements)` where the
    requirements map (`beam_class` + `carrier_gbps`) is module-declared wiring
    DATA, never an authority; a `technology_id` argument lets the open-world
    probe compose under an UNKNOWN_BUT_WELL_FORMED id through the SAME
    constructor (the boundary branches on no technology name);
  - the declared future-technology capability surface (the semantics declared
    BY the module, deterministically): the terahertz-carrier bandwidth RANGE
    (10..100 Gbps, enforced fail-closed on bindings), the holographic-latency
    bound (100 µs — declared DATA; the observable surface stays the generic
    link-metric vocabulary, LOCK-110), and the AI-native adaptive-beam class
    vocabulary (`thz-wideband` / `thz-focused`, enforced fail-closed);
  - the LOCK-112 citation tags (`itu-r-m2160-imt2030-framework`,
    `3gpp-rel-20-imt2030-study`, `ieee-802-15-3d-thz`) — STUDY-class
    citations for a technology with no deployed standard yet, carried as
    DATA, never branch input.
- **`tools/futureimt_selftest.py` (NEW — the M023 battery, 14 cases)** — the
  deterministic, offline, seeded drill battery (detail in §3).
- **`docs/M023-evidence.md` (NEW — this record).**

ZERO contract-core delta: the delivery diff is EXACTLY the three scope files
(`git diff --name-only origin/main...HEAD`); the module imports NO `contracts/`
surface at all (battery-proven by the AST audit) and writes no contract state;
the module surface is registration + operations only (battery-proven closed
`__all__` + engine method surface).

## 2. The by-reference composition map (the M014/M019 discipline, disclosed)

Every consumed surface is composed BY REFERENCE through its public API —
imported and composed, never reimplemented, weakened, forked, or bypassed:

| Consumed authority | Public surface composed | Where |
|---|---|---|
| `adapters/` (M007, LOCK-110/LOCK-112) | `AdapterContract`, `AdapterRuntime`, `CapabilityAdapter`, `AdapterDescriptor`, `ResourceMappingEntry`, `AdapterSecurityState`, `derive_adapter_id`, `parse_adapter_id`, the capability record constructors, `CAPABILITY_OPERATIONS`, `CAPABILITY_TRANSLATION_MAP` | the module composes the seam; the battery drives all nine §6 operations through it |
| `sessions/` (WORK-012) | `SessionStore` read-only bindability verification (inside the runtime) | exercised through the accepted battery fixture `tools/adapter_selftest._established_session` (imported by reference) |
| `resources/` (WORK-008) | `unit_multiplier_for` / `unit_base_for` via `ResourceMappingEntry.capacity_base` | the descriptor's mapping validates against the frozen kinds/units |
| `capabilities/` (WORK-005) | `CapabilityStatement`, `statement_to_bytes`, `classify_capability_id` | the drill's real capability statements + the authority's own classification verdicts (carried verbatim as offer DATA) |
| `offers/` (M003, LOCK-105/LOCK-118) | `OfferExchange`, `build_advertisement`, `build_offer`, `offer_reference`, `AdvertisementEntry`, `OfferCommitment`, `OfferPricing`, `ServiceBoundary` | the real offer/advertisement records grounding the composition's capability surface; `resolve` for the usability verdict |
| `contracts/` (M002, LOCK-101) | `ContractStore`, `CreateContract`, `SelectOffers`, `ActivateContract`, `HardConstraint`, `OpaqueReference`, `Provenance`, `ValidityInterval`, `COMMAND_KINDS`, `TERMINAL_STATES` | the real contract carried to CONTRACT_ACTIVE — driven by the drill CALLER (never the module); the plan's constraint-truth gates |
| `executionplans/` (M006, LOCK-109) | `translate_contract`, `SegmentInput`, `apply_segment_transition`, `verify_plan_preserves_contract`, `plan_reference`, `ADAPTER_OPERATIONS` | the real LOCK-109 bridge: the contract translated to a plan whose segment (all 8 operations, the future-IMT offer) drives the composition; the vocabulary composed by NAME equality, never by cross-import |
| `eligibility/` (M004) | `ContractEligibilityRuleset`, `ContractReferenceFacts`, `OfferReferenceEligibilityFacts`, `evaluate_offer_reference_eligibility`, `evaluate_contract_reference_eligibility`, `ContractConstraintRule`/`Set`/`Context`, `evaluate_contract_constraints` | the real admission gates: the offer + contract reference sets evaluated ELIGIBLE; the unpermitted-provider denial as decision DATA; the policy ALLOW decision + deny-wins resolution |
| the governance gates | `authorization_provenance.covers`, `architecture_drift_guard.is_control` | the battery's delta-shape consultation (the M001-evidence §4 duty) |

The legacy 1.0 `imt/` domain is harvested as SOURCE MATERIAL ONLY: the reserved
registry path, the open-world probe id, the `imt2030:` opaque-ref grammar, the
profile version, and the DEGRADED-with-outstanding-grants health discipline are
re-expressed on the 1.1 authorities; the module NEVER imports `imt/`
(battery-proven AST assertion — 1.0 material is never a forward dependency).

## 3. The M023 battery (14/14)

`python3 tools/futureimt_selftest.py` — deterministic, offline, seeded
(PYTHONHASHSEED 0/1/42 cross-process byte-identity, case_13); all cases
carry deterministic expected outcomes; exit-code-based verification:

| Case | Verified |
|---|---|
| 01 registration through the accepted seam | the composition registers through `AdapterRuntime` + `CapabilityAdapter` (technology as DATA; the adapter id is the WORK-016 grammar, never a NodeID); the reserved future path classifies KNOWN; the 8-operation vocabulary is NAME-equal to the accepted M006 set; the full lifecycle drives green |
| 02 declared capability surface | the 4 references classify UNKNOWN_BUT_WELL_FORMED through the capabilities authority (by reference) and are preserved verbatim; the offer views mirror the declared mapping; LOCK-110 generic-metric observability |
| 03 typed records + canonical round-trips | the typed Allocation/Activation/Measurement/Reconfiguration/ReleaseReceipt/HealthReport sequence with byte-identical round-trips through the accepted constructors + tamper evidence; deterministic engine counters; failed ops never advance the ledger |
| 04 the re-bind translation | the disclosed (unbind, bind) pair: previous binding RELEASED first, new binding BOUND, same session + preserved reservation; ACTIVE→RECONFIGURED with the replaced snapshot; idempotent re-reconfigure; the reservation guarded |
| 05 the offer exchange | real WORK-005 statements + M003 advertisement/offer composed by reference; the declared surface expressed in the frozen commitment vocabulary (≤1 ms latency, 100 Gbps carrier floor); the reference resolves usable |
| 06 the LOCK-109 bridge | the real CONTRACT_ACTIVE contract translated to a plan whose segment (all 8 operations, the future-IMT offer) drives the composition PLANNED→…→RELEASED with the real M006 kernel; constraints + fingerprint unchanged (LOCK-108); the plan rides as an opaque execution artifact |
| 07 eligibility + policy admission | the offer + contract reference sets ELIGIBLE under a real ruleset; the unpermitted provider denied as decision DATA; the policy ALLOW on the canonical guarded action; deny-wins deterministic |
| 08 LOCK-110 isolation | no opaque `imt2030:beam*` reference crosses into any 1.1 record's canonical bytes; the bearer ref stays opaque behind the runtime; the tags + technology id ride as DATA |
| 09 typed errors fail closed | the declared-surface matrix (6 isolated typed rejections), the LOCK-119 secret rejection, the runtime rejections (mapping/capacity/unknown ids), the terminal-state edges |
| 10 open world + no branching | an UNKNOWN_BUT_WELL_FORMED id composes identically through the same seam; the accepted seam surface carries no technology token; the registry path stays reserved (registration is never activation) |
| 11 ZERO CONTRACT-CORE DELTA | the AST audit (zero authority imports); the closed registration+operations surface; the git-guarded delta touches no contract-core file and stays inside the R9-CORE-001 scope (the drift-guard CONTROL classification + the provenance gate's own `covers`, by reference) |
| 12 one-way import + purity | no accepted module imports the composition; the module never imports the legacy `imt/`; no wall clock / randomness / network anywhere in the drill |
| 13 determinism | in-process rebuild byte-identical; the full drill material byte-identical across PYTHONHASHSEED 0/1/42 |
| 14 evidence honesty | this record: SOFTWARE class, the lock mapping, the by-reference composition, the case_68 artifact, the open physical obligations; no affirmative physical claims |

## 4. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the module imports no `contracts/` surface
  and writes no contract state; activations are adapter-local execution
  bookkeeping; `ConnectivityContract` stays the sole authority (case_11).
- **LOCK-105 (no global topology):** the composition declares provider-local
  mapped resources only; the offer views are the provider-local inventory
  slice; no topology fact ever crosses (cases 02/05/08).
- **LOCK-109 (execution bridge):** the composition is named by the accepted
  `executionplans/` bridge — a real plan's segment operation references drive
  it; the plan rides as an opaque execution-artifact reference (case_06).
- **LOCK-110 (adapter isolation):** every 1.1 operation returns the typed,
  canonical, provider-neutral records; opaque technology references stay
  behind the WORK-016 runtime; the core imports nothing from the module and
  branches on no technology name (cases 03/08/10).
- **LOCK-112 (standard leverage):** the study-class citation tags are DATA
  with issuer provenance, never branch input (cases 01/02/08).
- **LOCK-117 (authority uniqueness):** the activation ledger, the
  reconfiguration records, and the plan are execution artifacts — never a
  second contract authority (cases 03/04/06).
- **LOCK-118 (provenance):** every externally asserted member of the composed
  offer carries issuer + provenance; the views carry LOCK-118 issuer/inspect
  provenance (cases 05/08).
- **LOCK-119 (secrets):** injected instants only; no wall clock, no
  randomness, no network; secret-shaped requirements rejected at the accepted
  seam (cases 09/12/13).

## 5. The full suite at the delivery head

Two verification contexts, both disclosed (the branch's pinned base predates
main's DEC-0122 advance — see §0):

1. **The dispatch-baseline context** (`origin/main` = the charter's pinned
   live-main head `fe27c99` — the context the charter's verification bar was
   written against): the M023 battery **14/14 x3 byte-identical**; the full
   battery suite in the exact CI order of `.github/workflows/spec-check.yml`
   at this head green EXCEPT the one disclosed artifact — the adapter battery
   **69/70** (case_68, `['adapters/reference/futureimt.py']`, §0); the
   accesstech step at its accepted count 19/19; the wireline step SKIPS
   visibly (the pre-delivery existence guard for the in-flight-at-dispatch
   M021 delivery — correct at this head, never created here); the five gates
   (current_spec_check, tech_lead_guard, architecture_drift_guard
   implementation-only, authorization_provenance, fresh_session_check
   against the baseline) rc=0.
2. **The PR merge-ref context** (the local merge of this head with the
   advanced `origin/main` — the exact context the PR's pull_request CI
   evaluates): the M023 battery 14/14; the gates green (provenance: the
   three-file delivery delta fully covered by R9-CORE-001, byte-identical
   authorization inheritance; fresh-session: the reconciled snapshot per the
   standing convention); the adapter battery 69/70 with exactly the §0
   artifact (`['adapters/reference/futureimt.py']`); the wireline battery
   runs at its accepted 14/14 (main's own accepted delivery) and accesstech
   at 19/19.

The addendum-directed survey of the other hardcoded-allowlist batteries
(oran, conformance, appliance) at this head: **none trips on this delivery's
delta** (oran 36/36, conformance 63/63, appliance 42/42 in the
dispatch-baseline context — the conformance battery's docs/ delta admission
covers this evidence doc through the active authorization); their raw-head
spec/-identity failures with TODAY'S advanced main are the §0 main-advance
class, green at both verification contexts above.

## 6. Judgment calls (disclosed)

1. **The branch base stayed at the charter's pinned `fe27c99`** even though
   live main advanced to `9ee8611` (DEC-0122, M021 accepted) after the
   charter and re-dispatch addendum were written against the fe27c99 context:
   the charter pins the exact SHA ("verify `git rev-parse HEAD` equals
   fe27c99… before you start") AND its verification bar states "the wireline
   step SKIPS visibly at your head — the pre-delivery existence guard for
   the in-flight M021 delivery" — an instruction satisfiable only at the
   fe27c99 root. The chain-independence rule then governs the advance: no
   rebase, scope disjointness, the PR merge integrates. (Rooting at the
   advanced main would have violated both explicit charter instructions.)
2. **The battery's zero-core-delta delta audit consults the drift guard's
   own CONTROL classification** (`architecture_drift_guard.is_control`) plus
   the provenance gate's own `covers` — the single-source-of-truth
   composition the M001-evidence §4 duty prescribes for post-M001 batteries;
   this keeps the case robust at every verification context (control-plane
   files are governance-classified, implementation paths scope-checked).
3. **The engine's binding requirements are REQUIRED and validated against
   the declared surface** (a beam class must be named; the carrier must be
   an in-range integer) — the module's own fail-closed discipline, an
   adapter-side typed rejection isolated as a failure VALUE through the
   sandbox (never an exception into core state); this exercises the
   declared-surface semantics rather than leaving the requirements
   unconstrained (the GenericAdapter's neutral shape).
4. **The health discipline (DEGRADED while beam grants are outstanding)** is
   the harvested legacy `imt/` engine's deterministic occupancy shape,
   re-expressed (LOCK-017: reported DATA, the runtime computes the effective
   state) — a harvest disclosure, not an import.

## 7. Out-of-scope discipline (nothing else changed)

The delivery diff is exactly the three declared files
(`git diff --name-only origin/main...HEAD`):
`adapters/reference/futureimt.py`, `tools/futureimt_selftest.py`,
`docs/M023-evidence.md`. NOT touched: `spec/` (any file), `.github/` (the
M023 CI step is NOT wired at this head — the workflow is control-plane, out
of worker scope; the Tech Lead wires it at the acceptance, the
DEC-0116/DEC-0117 wiring precedent), `AGENTS.md`, `README.md`, every other
`adapters/` file (the accepted family modules, `capability.py`, and
`adapters/reference/__init__.py` are composition substrates imported, never
edited — the module is a standalone leaf submodule exactly as the M021
`adapters/reference/wireline.py` precedent), `contracts/`,
`executionplans/`, `offers/`, `eligibility/`, `policy/`, `imt/` (read-only
source material), and every other declared boundary. Zero file overlap with
the M021 delivery set.

## 8. Evidence classes (honest disclosure)

- The M023 battery, the full battery suite, and the governance gates: all
  **SOFTWARE** class (deterministic, offline, seeded; exit-code verified).
- EVID-002..EVID-008 (the open physical obligations) remain open and
  untouched; nothing in this record converts software evidence into a
  PHYSICAL PASS; no live-service, production, or physically-verified claim
  is made anywhere.
- The synthetic technology is declared DATA throughout: registration is
  never activation (the registry's reserved path stays reserved), and the
  open-world probe proves an unknown id gains no authority.

## 9. Delivery provenance

- Branch `m023-futureimt`, rooted at `fe27c9962f5e5ad4da9b355bf3be1172825bf4fe`
  (the DEC-0121 M020-acceptance head), append-only commits, worker identity
  `z-ai-worker <worker@adcos.local>`.
- Authorization: R9-CORE-001 (DEC-0120); the delivery delta fully covered by
  its declared scope (`adapters/reference/futureimt.py`,
  `docs/M023-evidence.md` exact paths + the `tools/` shared battery prefix);
  the authorization file inherited byte-identically from main.
- The battery's CI step is expected to be wired by the Tech Lead at the M023
  acceptance (the DEC-0116/DEC-0117 pre-delivery existence-guard wiring
  precedent) — not by this delivery (the workflow is control-plane).
- The known integration artifact (§0) is resolved by the Tech Lead's
  integration commit BEFORE the merge; this record and the PR body disclose
  the 69/70 expectation explicitly wherever the adapter battery is cited.
