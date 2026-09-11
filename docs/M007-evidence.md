# M007 — Provider/Standard Adapters — Evidence Record

**Work Item:** M007 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7
program authorization; M007 is the charter's current child — the DEC-0106
acceptance advanced the current-child pointer M006 → M007)
**Baseline:** `2b25090ddc3800c38dc995e1f0628746e9615529` (the DEC-0106-accepted
M006 state — the live main head at branch time)

This record persists the verified facts of the M007 delivery. Every claim below
is reproducible offline from the delivery head; no worker report is trusted
without direct verification (the standing Tech Lead rule). All evidence in
this record is **SOFTWARE class** — deterministic-battery evidence only; no
PHYSICAL PASS is claimed or implied, and EVID-002..EVID-008 remain open and
untouched.

## 1. Delivered surface

- **`adapters/capability.py` (NEW)** — the Architecture 1.1 §6
  capability-oriented execution boundary, harvested onto the WORK-016-era
  `/adapters` package (a refactor, never a rewrite — the WORK-016 public API
  stays byte-compatible; see §1.4):
  - **`CAPABILITY_OPERATIONS`** — the frozen 1.1 §6 operation vocabulary
    (`inspect-capabilities, inspect-offers, reserve, activate, measure,
    reconfigure, release, health`), hyphenated **exactly** as the accepted
    M006 `executionplans.ADAPTER_OPERATIONS` carries them. The relationship
    is NAME EQUALITY verified in the battery (case_57) — the adapters
    package imports no plan-layer module (the frozen 1.1 §6 direction:
    plans reference adapter operations; adapters never reference plans —
    also mechanically audited in case_67).
  - **`CAPABILITY_TRANSLATION_MAP`** — the **explicit, disclosed translation
    seam**: every 1.1 operation declared as its WORK-016 nine-op composition
    (`inspect-capabilities → capabilities`, `inspect-offers → capabilities`,
    `reserve → allocate`, `activate → bind_session`, `measure → observe`,
    `reconfigure → (unbind_session, bind_session)` — the deterministic
    re-bind translation of a mid-session reconfiguration: the previous
    binding is released first, the reservation is preserved, the same
    session re-binds with the NEW requirements —, `release →
    release/unbind_session`, `health → health`). Every 1.1 operation
    composes through the WORK-016 `AdapterRuntime`, so the sandbox's
    exception isolation, contract-shape enforcement and deterministic step
    budgets remain in force **mechanically** (LOCK-110 preserved
    structurally, not conventionally; battery case_62 proves the budget
    still binds through the seam).
  - **Typed, provider-neutral records** — `CapabilityView` (capability
    inspection: mediated descriptor-filtered references + LOCK-112 mechanism
    tags + lifecycle, LOCK-118 issuer/instant provenance), `OfferView` (one
    per mapped technology resource: the provider-local LOCK-105-safe
    inventory slice — an inspection VIEW, never an M003 authority object,
    never topology), `Activation` (the adapter-local execution bookkeeping
    mapping reservation→session→binding; LOCK-117: an execution artifact,
    never a second contract authority — no `bearer_ref`/`technology_ref`
    member by construction, battery case_60), `Measurement` (mediated
    generic link-metric samples, adapter-REPORTED data, never topology
    authority), `Reconfiguration` (the applied re-bind record:
    previous/new binding, applied requirements), `ReleaseReceipt` (the
    applied teardown: exactly which kinds were released). All ids
    content-derived over WORK-003 canonical JSON; all instants injected;
    `ActivationState` (`ACTIVE/RECONFIGURED/RELEASED`, terminal RELEASED,
    frozen transition table — an ADAPTER-LOCAL lifecycle that never
    re-invents the M006 segment vocabulary); canonical `to_dict` /
    `from_mapping` round-trips with the identity recomputed at load (tamper
    evidence at construction AND load, the WORK-016 convention).
  - **`CapabilityAdapter`** — the seam class for one registered adapter:
    wraps a WORK-016 `AdapterRuntime` + adapter id + the declared
    LOCK-112 mechanism tags (DATA, never a branch input), and exposes the
    eight 1.1 operations with the WORK-016 result convention (caller-side
    input/state errors RAISE typed `AdapterError`; adapter-side faults and
    deterministic runtime rejections RETURN `AdapterOpResult` with a typed
    `AdapterFailure` — isolated values, never exceptions). Failed
    operations never advance the ledger sequence; a failed re-bind after a
    committed unbind reports the TORN activation explicitly (no silent
    partial success); `release` tolerates an already-released binding so a
    torn activation can always be torn down explicitly.
- **`adapters/reference/` (NEW subpackage, seven files)** — the reference
  adapters for the charter's six technology subpackages
  (`backhaul/`, `fivegc/`, `ip/`, `mesh/`, `ran/`, `wifi/`): one module per
  family plus the package surface. **Placement disclosure:** the
  compositions live in `adapters/reference/`, NOT inside the family
  directories, because the family batteries freeze their packages'
  boundary audits (the WORK-020/021/022 standards-boundary audits allow
  only each family bridge's single sanctioned SDK import — a new
  SDK-importing file inside `adapters/ran|wifi|backhaul/` fails those
  accepted batteries by construction). The six family subpackages are
  **byte-identical** to origin/main (battery case_68 asserts it); the M007
  seam lives in the new domain — the M006 composition-harvest precedent.
  Each module declares its family's
  **LOCK-112 `STANDARD_MECHANISMS`** (citation tags taken from the family's
  own frozen citations — 3GPP IAB/sidelink + DTN-class
  store-and-forward; 3GPP NR + O-RAN F1/E1/7-2x splits; IEEE
  802.3-2018/802.1Q-2022/ITU-T G.709; IEEE 802.11-2020/802.1X-2020/RFC
  3748/TS 23.316 N3IWF/RFC 7296; 3GPP TS 23.501/TS 23.316; RFC
  4291/6437/6146 — never new technologies), the reference registration
  data (descriptor, resource mapping into the WORK-008 kinds/units), and a
  deterministic `mount_reference()` composition root:
  - **mesh / backhaul / wifi** compose the REAL accepted family runtimes
    (manager + reference engine + the accepted WORK-016 bridges); the
    binding coordinates (route ref / link ref / AP ref + SSID) come back
    as family wiring DATA the caller passes to `activate`/
    `reconfigure` — the W016 runtime's own technology refs stay opaque.
  - **ran** composes the deterministic reference engine + the accepted
    bridge; the composition root performs the canonical gNB/cell
    provisioning at SDK `open` (the WORK-020 battery's own flow) and
    translates the mapped WORK-008 `bandwidth` kind onto the family's
    `ran.radio-capacity` reservation kind (disclosed, the
    backhaul/Wi-Fi bridge-fixed-default pattern).
  - **fivegc / ip** add the W016 `AdapterContract` reference adapters the
    two families never had (`FiveGCTechnologyAdapter` /
    `IPIntegrationTechnologyAdapter` over their family RUNTIMES — the
    manager-mediating bridge pattern; the 5G Core adapter translates the
    binding-coordinate DATA into the family's typed `Supi`/`Snssai`/`Dnn`
    values; the IP adapter consumes the opaque transport/route
    coordinates as DATA).
  - **Honest family disclosures surfaced through the seam (asserted, never
    papered over — battery case_65):** the Wi-Fi family's frozen
    disciplines make mid-session re-bind fail closed
    (`ACCESS_SESSION_COLLAPSE` — replacement after family-side release
    only) and the AP-allocation release fail closed (the frozen 12-op
    family contract has no AP decommission); the RAN bridge's
    `capability.access.*` references are not yet admitted by the frozen
    WORK-002 grammar, so its mediated exposure through the W016 runtime is
    EMPTY (the family's own documented behavior, preserved verbatim).
- **`adapters/__init__.py` (MODIFIED — additive only)** — 22 new M007
  exports appended (76 total); every one of the 54 baseline WORK-016
  exports preserved (battery case_68 asserts the full baseline list).
  The WORK-016 modules (`contract.py`, `model.py`, `sandbox.py`,
  `runtime.py`, `serialization.py`, `validation.py`, `errors.py`,
  `certification.py`) are **byte-identical** to origin/main, as are the
  six family subpackages in full (byte-level diff asserted + the family
  batteries re-run green at their accepted counts: ran 46/46, wifi
  36/36, backhaul 48/48, mesh 38/38, fivegc 31/31, ipintegration
  45/45, distcore 40/40).
- **`tools/adapter_selftest.py` (EXTENDED)** — the M007 battery: the 56
  WORK-016 cases preserved verbatim + **14 new M007 cases (57-70)** →
  **70/70 PASS**, deterministic, offline, seeded (details in §2).
- **`docs/M007-evidence.md`** — this record.

### 1.1 The adapter map (1.1 operation surface)

| 1.1 §6 operation | WORK-016 translation (the seam) | Return type |
|---|---|---|
| `inspect-capabilities` | mediated `capabilities()` filtered by the descriptor declaration + descriptor data | `CapabilityView` |
| `inspect-offers` | descriptor resource-mapping data + mediated current references | `Tuple[OfferView, ...]` |
| `reserve` | `allocate()` (the adapter-scoped capacity ledger; integer base units, lease expiry) | `Allocation` |
| `activate` | `bind_session()` (read-only WORK-012 bindability verification + mediated bearer creation) | `Activation` |
| `measure` | `observe()` (generic link metrics, injected instant) | `Measurement` |
| `reconfigure` | `(unbind_session(), bind_session())` with the SAME session and the NEW requirements | `Reconfiguration` |
| `release` | `unbind_session()` and/or `release()` (activation teardown / reservation cancellation) | `ReleaseReceipt` |
| `health` | mediated `health()` (computed state wins, LOCK-017) | `HealthReport` |

### 1.2 The M006 composition seam

M006 is ACCEPTED at this baseline (DEC-0106), so the segment reference seam
is the REAL thing (no test double): battery case_66 builds a real contract
and a real plan (through the accepted `contracts/`+`offers/`+`executionplans/`
APIs) whose segment carries **all eight** operation references, drives every
operation through the mesh reference adapter, advances the segment with the
REAL M006 transition kernel (PLANNED→RESERVED→ACTIVATED→MEASURED→RELEASED
plus the idempotent MEASURED→MEASURED re-measurement edge), and proves
LOCK-108: the plan's hard-constraint set and fingerprint are byte-identical
before and after execution, and `verify_plan_preserves_contract` still
passes. `reconfigure` deliberately does NOT move the segment state (the M006
segment vocabulary owns segment states and has no RECONFIGURED state); the
typed transition lands on the adapter-side Activation record (disclosed).
The adapter operations are the concrete mechanism surface the
ExecutionSegment references compose down onto, consumed **by name only**
(LOCK-110) — `adapters/` imports no `executionplans/` code (mechanically
audited both directions).

### 1.3 Isolation points (LOCK-110)

- Every 1.1 operation return is a typed, canonical, provider-neutral record
  (case_60 asserts the type module of EVERY boundary return is
  `adapters.capability` / `adapters.model` / `adapters.runtime` /
  `adapters.sandbox` / builtins, and that NO family-side opaque reference
  text — `mesh:`/`ran:`/`wifi:`/`backhaul:`/`fivegc:`/`ip:` — appears in any
  returned record's canonical bytes).
- The core imports no adapter implementation and branches on no technology
  name: case_67 scans `executionplans/`, `contracts/`, `offers/` for
  `adapters` imports (none), the seam for plan/contract/offer/routing/
  topology/policy imports (none), and every `ast.Compare` operand in the
  seam for technology tokens (none).
- The WORK-016 import-boundedness, vendor-token, and
  no-wall-clock/randomness/network audits (battery cases 24/25/26) continue
  to cover the new top-level `adapters/capability.py` (stdlib +
  `protocol` only; no banned identifiers; no banned calls).

## 2. Deterministic verification matrix

All runs offline; instants injected (T0-style constants); no wall clock, no
randomness, no UUIDs, no network; no real sockets; no secrets stored
(LOCK-119); PYTHONHASHSEED-safe (verified across processes and seeds 0/1/42).
Exit-code-based verification (a traceback or lowercase "failed" IS a failure).

| Verification | Result | Evidence |
|---|---|---|
| Frozen 1.1 §6 vocabulary == M006 `ADAPTER_OPERATIONS` (name equality; no plan import in adapters) | PASS | case_57 |
| Translation map: every 1.1 op composes onto the WORK-016 nine-op surface only | PASS | case_57 |
| (a) All six family reference compositions mount/register/open and answer every inspection + health operation typed and deterministic | PASS | case_58 |
| (a) LOCK-112 mechanism tags carried as DATA on every view | PASS | case_58 |
| RAN exposure EMPTY through the mediated surface (family-documented WORK-002 grammar gap, preserved verbatim) | PASS | case_58 |
| (e) Full lifecycle reserve→activate→measure→reconfigure→release with typed transitions (Allocation ACTIVE→RELEASED; Activation ACTIVE→RECONFIGURED→RELEASED) | PASS | case_59 |
| (e) Content-derived ids; capacity ledger restored on release; canonical round-trip identity | PASS | case_59 |
| (b) LOCK-110: every boundary return is a canonical type (type-level audit of the full lifecycle) | PASS | case_60 |
| (b) LOCK-110: no family-side opaque reference text crosses in any record | PASS | case_60 |
| (b) Activation carries binding_id and no bearer/technology-ref member | PASS | case_60 |
| (a/f) Nine deterministic failure paths: unknown reservation, unmapped kind, capacity exhaustion (isolated value), unbindable session (isolated value), expired lease, missing release target, terminal-state discipline (reconfigure/measure/double-release/unknown), reservation-held guard | PASS | case_61 |
| (f) The deterministic step budget binds THROUGH the seam (hung op → isolated BUDGET_EXHAUSTED; ledger unchanged) | PASS | case_62 |
| (d) Capability/offer inspection determinism: byte-stable per state+instant; offers mirror the descriptor mapping verbatim; closed adapter exposes nothing | PASS | case_63 |
| (d) Canonical serialization: `to_dict` == the canonical projection; instant the only varying member | PASS | case_63 |
| Canonical round-trips + fail-closed tamper/grammar gates on all four record kinds | PASS | case_64 |
| (a/f) Wi-Fi family honest fail-closed paths: re-bind rejected (family discipline), torn activation disclosed, AP release fails closed, retry deterministic | PASS | case_65 |
| (g) The M006 segment reference seam: all 8 operation references drive the reference adapter; the REAL M006 kernel advances the segment; LOCK-108 fingerprint/constraint identity; attribution preserved | PASS | case_66 |
| LOCK-110 branch discipline: core imports no adapters; seam imports no core domain; no technology-token comparisons in the seam | PASS | case_67 |
| (c) WORK-016 compatibility seam: canonical pre-M007 flow green; 54 baseline exports preserved; 6 family export tables pinned; adapters/ delta == exactly the 8 declared M007 files | PASS | case_68 |
| Cross-process/seed determinism of the M007 scenario (PYTHONHASHSEED 0/1/42) | PASS | case_69 |
| LOCK-119: secret-shaped and non-canonical requirements rejected; activation vocabulary + transitions frozen; declaration bounds enforced | PASS | case_70 |
| WORK-016 cases 1-56 (the frozen WORK-016 battery) still green — the compatibility seam from the battery side | PASS | cases 1-56 |
| Mechanical audits re-run over the extended tree: imports bounded, no vendor tokens, no wall clock/randomness/network, frozen docs, vocabulary freeze | PASS | cases 23-26, 55-56 |
| Battery run 3× consecutively, exit-code-based | PASS 70/70 ×3 | §7 |

## 3. Lock-conformance mapping

| Lock | Conformance |
|---|---|
| LOCK-101 (canonical contract) | The activation ledger and every M007 record are execution artifacts under LOCK-117; `contracts/` stays the sole authority — the seam never constructs, mutates, or re-derives contract state (case_66: the plan/contract truth byte-identical through execution). |
| LOCK-104/LOCK-105 (provider sovereignty / no global topology) | `inspect_offers` returns the provider-local declared inventory slice only (descriptor data + mediated references); no topology crosses (case_63); the mechanism tags are citations, never topology claims. |
| LOCK-108 (no silent weakening) | Execution through the seam cannot touch contract constraints: case_66 proves the plan's constraint set + fingerprint byte-identical and `verify_plan_preserves_contract` green after the full run. |
| LOCK-109 (execution bridge) | The 1.1 operations are the concrete mechanism surface the accepted M006 ExecutionSegment references compose down onto (case_66). |
| LOCK-110 (adapter isolation) | Structural: every return is a typed provider-neutral record (case_60); the core imports no adapter implementation and branches on no technology name (cases 23/67); provider-native family types stay behind the family seams; the W016 sandbox's isolation/budget/contract-shape mechanics stay in force through the seam (case_62). |
| LOCK-111 (optimizer replaceability) | Not touched: the seam consumes the plan's declared operation references verbatim; no optimizer behavior is added or altered. |
| LOCK-112 (standard leverage) | The reference adapters wrap the mechanisms their families already model (LOCK-112 tags with the family's own citations); no technology is invented; nothing is reinvented (case_58 tags; §1 family modules). |
| LOCK-117 (authority uniqueness) | No adapter record becomes a second contract authority: the Activation/Measurement/Reconfiguration/ReleaseReceipt records are data riding behind the execution boundary (case_60 field audit; case_66 LOCK-101 row). |
| LOCK-118 (provenance) | Every view/record carries issuer (adapter_id) + injected instant; ids are content-derived (cases 59/63). |
| LOCK-119 (secrets) | Secret-shaped requirements rejected at the boundary; no credential material anywhere (case_70; the family credential slots stay NAMES). |

## 4. Judgment calls (disclosed)

1. **The 1.1 operation vocabulary is declared, not imported.** M007 could have
   imported `executionplans.ADAPTER_OPERATIONS` into `adapters/`; the frozen
   1.1 §6 direction is the opposite (plans reference adapter operations,
   never the reverse), and the WORK-016 battery's import-boundedness audit
   (case_24) pins the adapters package to stdlib + protocol/capabilities/
   sessions/resources. The seam therefore declares its own frozen copy and
   the battery asserts NAME EQUALITY with the accepted M006 vocabulary
   (case_57) — the composition seam is by name, verified, never silently
   duplicated. (Justified by frozen 1.1 §6 + the WORK-016 frozen module
   authority rules the package documents.)
2. **`reconfigure` is translated as a re-bind pair.** The WORK-016 surface
   has no mid-session reconfiguration primitive. The seam translates one
   onto the deterministic pair (`unbind_session`, `bind_session`) with the
   SAME session id and the NEW requirements — the reservation is preserved,
   the previous binding is released first (auditable), a failed re-bind
   leaves a disclosed TORN activation (never a silent partial success), and
   release tolerates the already-released binding so teardown always
   remains possible. This is the reference semantics of standards-native
   steering updates (TS 23.316 ATSSS-style) at reference granularity.
   (Justified by the charter's "explicit, disclosed translation seam".)
3. **The RAN family exposes an EMPTY mediated capability set.** The family
   bridge's `capability.access.ran.*` references are not admitted by the
   frozen WORK-002 grammar (the family documents this itself in
   `adapters/ran/bridge.py`). The M007 seam preserves the family behavior
   verbatim — it never rewrites capability references to make exposure
   non-empty — and the battery asserts the empty exposure as the
   family-documented outcome (case_58). (Justified by LOCK-017/§6.4:
   exposure is by reference, never rewritten.)
4. **The RAN composition translates the resource kind.** The W016 runtime
   admits only WORK-008 mapped kinds (`bandwidth`) while the RAN engine's
   reservation vocabulary is its own (`ran.radio-capacity`); the composition
   root translates the mapped kind onto the family kind verbatim in
   quantity — the same bridge-fixed-default pattern the accepted
   backhaul/Wi-Fi bridges document for their family parameters. (Justified
   by the W016 definition-of-done: technology enters as DATA; the
   composition root is the family wiring point.)
5. **The Wi-Fi family's fail-closed paths are surfaced, not worked around.**
   A re-bind of the same session through the SDK surface is rejected by the
   family's frozen `ACCESS_SESSION_COLLAPSE` discipline, and the
   AP-allocation release fails closed (the frozen 12-op family contract has
   no AP decommission). The M007 battery asserts both as deterministic
   fail-closed paths with the torn activation disclosed (case_65) — the
   honest outcome, never a silent success. (Justified by the charter's
   evidence policy: every battery case has a deterministic expected
   outcome; and by LOCK-108's spirit extended to execution truth.)
6. **The activation ledger lives in the seam, adapter-scoped.** The 1.1
   `activate` needs bookkeeping the WORK-016 runtime does not own (the
   session↔reservation↔binding mapping). It lives in the `CapabilityAdapter`
   as adapter-local execution data with content-derived ids, injected
   instants, and a frozen vocabulary — never a second contract authority
   (LOCK-117), never session authority (the runtime's read-only WORK-012
   verification remains the single bindability gate). (Justified by
   LOCK-117 + the WORK-016 frozen module authority rules.)
7. **The reference compositions live in `adapters/reference/`, not inside
   the family directories.** The family batteries freeze their packages'
   boundary audits (the WORK-020/021/022 standards audits allow only each
   family bridge's single sanctioned SDK import — placing the new
   SDK-importing composition modules inside `adapters/ran/`, `wifi/`, or
   `backhaul/` fails those ACCEPTED batteries by construction, and
   amending them is outside this PR's scope boundary). The within-scope
   resolution is the M006 composition-harvest precedent: the seam lives in
   the new domain (`adapters/reference/`), and the six family subpackages
   stay byte-identical to the accepted baseline (case_68 asserts the
   byte-level family diff is empty; every family battery re-runs green at
   its accepted count). (Justified by the charter's scope discipline:
   preserve every consumer surface; never touch another battery.)

## 5. Out-of-scope discipline (nothing else changed)

The M007 delta contains only: `adapters/capability.py` (new),
`adapters/reference/` (new, seven files — the six family reference
compositions + the package surface), `adapters/__init__.py` (additive
exports only), `tools/adapter_selftest.py` (the 56 WORK-016 cases preserved
verbatim + 14 new M007 cases), and `docs/M007-evidence.md` (this record) —
nine adapters/ files in total (case_68 pins the exact set).
The seven WORK-016 core modules (`contract.py`, `model.py`, `sandbox.py`,
`runtime.py`, `serialization.py`, `validation.py`, `errors.py`,
`certification.py`) are byte-identical to origin/main (battery case_68
asserts the adapters/ delta is exactly the eight declared files; cases 1-56
re-run the frozen WORK-016 verification). No control-plane surface, no
`spec/` file, no `.github/` file, no `executionplans/`/`contracts/`/
`offers/`/`composition/` modification (all consumed by reference only), no
other top-level domain, no other battery, and no historical record is
touched. The drift guard classifies the delta implementation-only; the
provenance gate verifies full coverage by R7-CORE-001 (`adapters/`, `tools/`,
`docs/M007-evidence.md` are all declared M007 scope entries).

## 6. The disclosed blocking conflict (charter stop-condition)

**`tools/payment_selftest.py` case_38_scope_audit fails on this delivery —
by frozen construction, not by any M007 defect — and the fix is outside this
worker's boundary.** Precise facts:

- The payment battery (the M009/DEC-0109 re-baseline) freezes 31 legacy
  authority families byte-identical in its `_SIBLING_PREFIXES` audit
  (`agent, identity, sessions, routing, networkpath, transport, platform,
  policy, protocol, topology, management, mobile, conformance, **adapters**,
  appliance, capabilities, discovery, edge, energy, federation, imt, intent,
  interop, mobility, multipath, resources, scale, services, simulator,
  telemetry, upgrade`): `git diff --name-only <audit-ref> -- <prefixes>`
  must be EMPTY. The gate has NO authorization exemption — unlike the same
  case's FIRST gate, which consults the active authorization
  (`_active_authorization_covers`, the docs/M001-evidence §4
  authorization-aware battery-scope consultation duty).
- M007's charter scope IS `adapters/` (R7-CORE-001; machine-verified by
  `authorization_provenance.py` PASS), so any real M007 delivery changes
  `adapters/` and trips the frozen-family gate: verified on the exact
  GitHub-direction PR-merge simulation (first parent = `origin/main`
  2b25090, second parent = the delivery head) —
  `case_38_scope_audit: accepted authority families changed vs HEAD^1:
  adapters/__init__ .py (+ the eight new adapters files)` → payment
  **43/44**; every other battery and gate green on the same simulation.
- Every accepted R7 child so far dodged the gate by scope geography:
  M002 `contracts/`, M003 `offers/capabilities/discovery/marketplace/`,
  M004 `eligibility/`, M005 `assurance/evidence/`, M006
  `executionplans/composition/` — none in the frozen list. M007
  (`adapters/`) is the FIRST child delivered inside a frozen family; M008
  (`sessions/multipath/mobility/`) and M014
  (`federation/scale/upgrade/identity/`) will hit the same gate.
- The conflict is therefore a charter **scope-amendment** decision for the
  Tech Lead: the natural repair (disclosed, NOT implemented — outside this
  worker's boundary: "You MUST NOT change … any other battery") is to make
  the payment sibling gate authorization-aware exactly as its own first
  gate already is (consult `_active_authorization_covers` before failing on
  a frozen family, so R7-covered children can deliver inside legacy
  families), or to retire `adapters` from the frozen list for the R7 era.
  `tools/payment_selftest.py` is inside the R7 program authorization's
  declared `tools/` shared-battery-surface scope, so the decision is the
  Tech Lead's to record per the charter's scope-amendment path.
- Everything else in the verification bar is green on the delivery head
  (§7): the full CI-order suite, all governance gates, the merge-commit
  drift/provenance classification. The ONE non-green blocking step is this
  payment case; the legacy `spec_check.py` compatibility audit remains
  `continue-on-error` (rc=1 identically on clean `origin/main`, pre-existing
  baseline behavior).

## 7. Evidence classes (honest disclosure)

- All M007 acceptance criteria: **SOFTWARE** class (deterministic offline
  battery, 70/70 PASS on the delivery head; every blocking battery and
  governance gate in the CI suite green on the delivery head EXCEPT the
  disclosed payment-battery conflict of §6 — see the PR body for the
  numbered results; the other non-green step, the legacy
  `spec_check.py` compatibility audit, is `continue-on-error: true` in the
  CI workflow: it fails (rc=1) on the pre-delivery baseline as well, and
  its ARCH-08 verdict cannot see the R7 program authorization by frozen
  construction (the workflow's own comment; the active-era successor gate
  `authorization_provenance.py` PASSES and verifies the delta's R7-CORE-001
  coverage).
- The reference adapters are simulation-class reference compositions over
  the accepted deterministic family engines — NO real provider network,
  vendor SDK, radio, or core is contacted, and none is claimed.
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M007 creates and
  closes none; EVID-002..EVID-008 remain open and untouched, and no
  evidence produced by this delivery is physical, production, or
  live-service evidence. No SOFTWARE evidence is converted into PHYSICAL
  PASS.
- M008 (replan/failover), M009+ commercial reconciliation, M014 production
  federation are NOT delivered here and never claimed; the M006 segment
  vocabulary is consumed as accepted (DEC-0106) without modification.

## 8. Delivery provenance

- Branch: `m007-adapters` from the baseline `2b25090` (the DEC-0106-accepted
  M006 state); append-only delivery history.
- Battery: `python3 tools/adapter_selftest.py` → PASS (70/70) on the
  delivery head, run 3× consecutively (exit-code-based).
- Full suite: every battery the CI workflow runs, in exact workflow order
  (PR event class, incl. management + simulator + the existence-guarded
  accepted batteries + the exact-head platformcaps job), on the delivery
  head with exit-code-based detection — see the PR body for the numbered
  results; the sole failing step is the §6 payment conflict (43/44, the
  frozen-family gate), re-verified on the exact GitHub-direction
  PR-merge simulation; the legacy spec_check rc=1 is the pre-existing
  `continue-on-error` baseline (identical on clean origin/main).
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
- Accepted sibling batteries at this head: contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33,
  roamlink 56/56, comos 33/33, assurance 97/97, executionplan 36/36,
  eligibility 46/46, policy 103/103, and the adapter-domain families
  ran 46/46, wifi 36/36, backhaul 48/48, mesh 38/38, fivegc 31/31,
  ipintegration 45/45, distcore 40/40 (the family subpackages stay
  byte-identical; the accepted counts re-verified on this head by the
  full-suite run). payment 44/44 → **43/44** solely on the §6 frozen-family
  gate (every other payment case green).
