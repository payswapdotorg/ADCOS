# M020 — Access Technology Capability Envelope — Evidence Record

**Work Item:** M020 · **Authorization:** R9-CORE-001 (DEC-0120, the bounded R9 program
authorization; M020 is the R9 charter's current child — the chain root / current child,
authorization R9-CORE-001 issued by DEC-0120)
**Baseline:** `ea4bb64e0d32cfe93384ece71ec0003f447e357f` per the authorization record
(the DEC-0119 R8-completion head); the branch rides the DEC-0120 R9-activation head
`a53910546d04f9555f481f80c29d610f8a136031` (verified `git rev-parse HEAD` equal before
any work; the pre-delivered accesstech CI step exists at that head — the DEC-0120
existence guard wired by the governance commit).

This record persists the verified facts of the M020 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed or implied,
and EVID-002..EVID-008 remain open and untouched.

**Parallel-delivery note (the charter's worker policy):** the chain-independent M023
worker is concurrently delivering on branch `m023-futureimt` (files:
`adapters/reference/futureimt.py`, `tools/futureimt_selftest.py`,
`docs/M023-evidence.md`). This delivery's scope is fully disjoint (verified:
`git diff --name-only origin/main...HEAD` contains zero overlap with that set; the
M023 surface is absent at this head and never claimed). If main advances before the
merge, this branch does NOT rebase (the charter's rule; scope disjointness keeps the
merge clean).

## 1. Delivered surface

- **`accesstech/` (NEW, 6 modules)** — the typed access-technology envelope domain on
  the canonical authority, composing the accepted R7/R8 authorities BY REFERENCE (the
  M014/M019 discipline — import and compose, never reimplement, weakened, forked, or
  bypassed):
  - **`accesstech/errors.py`** — the typed fail-closed error vocabulary
    (`AccessTechError` / `AccessTechReason`: nine typed codes; exception isolation
    everywhere — consumed-seam rejections surface on this domain's vocabulary with
    their deterministic text preserved, never raw exception text into stored state).
  - **`accesstech/envelopes.py`** — the declared capability envelopes per technology
    class: typed deterministic ranges over the four capability dimensions
    (`BpsRange` bandwidth, `LatencyMilliRange` latency, `JitterMilliRange` jitter,
    `AvailabilityWindow`/`AvailabilityWindows` availability windows over injected
    RFC 3339 UTC instants), canonical-JSON serializable with content-derived
    identities (**LOCK-106 discipline: sha256 identities derived from the canonical
    bytes of the content — never wall clock, never randomness**; recomputed and
    compared at reconstruction — tamper evidence), technology ids validated through
    the accepted open-world classifier (`adapters.validation.\
    validate_access_technology_id`: KNOWN and future UNKNOWN_BUT_WELL_FORMED ids
    preserved verbatim, malformed ids rejected with the accepted seam's own typed
    rejection), and deterministic fail-closed validation: **empty ranges**
    (ENVELOPE_DEGENERATE — a bandwidth dimension promising nothing, a zero-width
    latency/jitter range, an availability dimension with no windows), **inverted
    bounds** (ENVELOPE_INCONSISTENT — floor above ceiling, min above max, a window
    ending at or before its start), **contradictory content**
    (ENVELOPE_INCONSISTENT — disordered or overlapping windows; IDENTITY_MISMATCH —
    a declared identity that does not match the derived content) — typed rejections,
    never warnings.
  - **`accesstech/ladders.py`** — the degradation ladders: declared ordered sequences
    of **degradation modes** (named, technology-class-local rungs — the extension
    surface the future M021 wireline capacity steps and M022 propagation-aware margin
    steps will declare) **mapped onto the accepted `resilience/` realization-state
    vocabulary**: the M008-owned `REALIZING/DEGRADED/FAILED/SUPERSEDED` kernel
    imported BY REFERENCE from `resilience.model` (the exact object the accepted R8
    domain itself imported from `replan/` — the battery proves the imported-object
    identity across all three surfaces) with the kernel's terminal-state set and
    transition edges imported from `replan` — **never redefined, never a fifth
    state** (a mode naming any other state is a typed VOCABULARY rejection). The
    ladder discipline (all typed LADDER_ILLEGAL rejections): the first rung maps to
    REALIZING; every middle rung maps to the explicit DEGRADED state (the recovery
    edge never appears inside a one-way ladder — recovery is the accepted
    machinery's edge); the last rung is terminal (FAILED or SUPERSEDED — every
    declared ladder carries its explicit terminal rung); no rung follows a terminal
    rung; every adjacent state pair is the identity (a deeper capacity step on the
    same explicit state) or an edge present in the imported kernel transition map;
    duplicate mode names are contradictory. Deterministic stepping
    (`ladder_step` descends exactly one rung; unknown mode names and terminal rungs
    are typed rejections); content-derived ladder identities (LOCK-106 discipline);
    canonical round-trips with tamper-evident re-verification.
  - **`accesstech/handovers.py`** — the handover characteristic declarations,
    consumed BY REFERENCE from the accepted `resilience/` handover machinery: per
    handover kind (`HANDOVER_KINDS` — the handover shapes the R9 charter itself
    names: `intra-technology`, `cross-technology` (the M024 interchange drill),
    `pass` (the M022 NGSO pass handover), `replacement` (the M024 technology
    replacement drill)) the constraint-preservation declaration **LOCK-108**: the
    preserved-constraint set is EXACTLY the imported frozen 12-kind
    `contracts.CONSTRAINT_KINDS` vocabulary (the same object the accepted
    `resilience.model` freeze-checks and the accepted handover gates validate
    `HardConstraint` records against) declared verbatim per kind — **the FULL set**;
    a weakened subset is a typed HANDOVER_ILLEGAL rejection (the declaration layer
    never weakens what the machinery enforces), an unknown kind is a typed
    VOCABULARY rejection. The `explicit_reconnect` discipline (WORK-012: every
    handover an explicit recorded reconnect naming BOTH the old AND the new
    references) and the `contract_continuity` discipline (LOCK-101/LOCK-117: a
    handover realizes the SAME contract; the successor-contract path is explicit
    renegotiation, a distinct mechanism) are mandatory-True declarations — a kind
    declaring a silent swap or contract-breaking semantics fails closed.
  - **`accesstech/registry.py`** — the technology-extension registration surface:
    the exact declared path by which a new access technology (**envelope + reference
    adapter composition + capability statement**) registers through the accepted
    `adapters/capability.py` seam (the M007 LOCK-110/LOCK-112 boundary: one
    `AdapterRuntime` over the caller's session store, the composition's descriptor +
    implementation registered through the runtime's public `register`, the adapter
    `open_adapter`-ed, the live `CapabilityAdapter` created by the accepted seam
    constructor with the composition's LOCK-112 mechanism tags) and the
    `executionplans/` LOCK-109 bridge (the frozen plan-side `ADAPTER_OPERATIONS`
    carried on every registration and verified name-equal at import time to the
    seam's own frozen `CAPABILITY_OPERATIONS` — the M007 composition-by-name-equality
    discipline) **with ZERO contract-core delta** (the registration path imports no
    `contracts/` surface at all beyond the frozen vocabulary constant the handover
    declarations consume; no contract is created, mutated or re-derived). The
    `TechnologyRegistration` record carries the declared surface (envelope id,
    ladder id, handover characteristic ids, adapter id, the capability statement
    references, the mechanism tags, the bridge operations) with a content-derived
    identity (LOCK-106 discipline) plus the LIVE composition objects held **BY
    REFERENCE** — `resolve_capability_adapter()` / `resolve_runtime()` return the
    SAME live objects every call (identity-preserving; no re-instantiation, no
    second runtime); the canonical `to_dict()` projection deliberately excludes the
    live objects (declared identity-bearing content only). The `TechnologyRegistry`
    holds registrations keyed by technology class (sorted deterministic iteration;
    duplicate classes typed rejections — the duplicate-identity malformed class).
- **`tools/accesstech_selftest.py` (NEW)** — the M020 battery: deterministic,
  offline, seeded — 19 cases covering (a) envelope declaration + validation
  (well-formed round-trips byte-identically; every malformed class typed), (b) the
  degradation ladders (the imported-vocabulary identity proof; deterministic
  stepping; no undeclared modes), (c) the handover declarations (the LOCK-108
  full-set declarations per kind; the REAL accepted machinery driven as the proof),
  (d) the registration surface (the six accepted families registering and resolving
  BY REFERENCE; full typed lifecycles through each registration's public runtime),
  (e) the extension proof (a synthetic future technology class registering through
  the SAME public path), (f) determinism (in-process rebuild byte-identical; the
  registration material byte-identical across PYTHONHASHSEED 0/1/42), plus the zero
  contract-core delta audit, the one-way import audit (AST-level over 26 accepted
  authority packages), the clock/import discipline audit, and the evidence-doc
  honesty check.
- **`docs/M020-evidence.md` (NEW)** — this record.

## 2. The by-reference composition map (the M014/M019 discipline, disclosed)

| Consumed authority | The exact surface consumed | How |
|---|---|---|
| `adapters/capability.py` + `adapters/runtime.py` + `adapters/model.py` + `adapters/validation.py` + `adapters/errors.py` (M007) | `CapabilityAdapter`, `AdapterRuntime`, `AdapterContract`, `AdapterDescriptor`, `CAPABILITY_OPERATIONS`, `validate_access_technology_id`, `AdapterError` | imported; the registration surface DRIVES the seam (`runtime.register` → `runtime.open_adapter` → `CapabilityAdapter(...)`); the seam's mediation, sandbox isolation and step budgets stay in force mechanically |
| `adapters/reference/{backhaul,fivegc,ip,mesh,ran,wifi}.py` (M007 reference compositions) | each family's own public `mount_reference` + `STANDARD_MECHANISMS` + `REFERENCE_TECHNOLOGY_ID` | imported by the battery (the composition root); the mounted products registered through the public path verbatim — never edited, never re-implemented |
| `executionplans/` (M006) | `ADAPTER_OPERATIONS` (the LOCK-109 bridge vocabulary) | imported; carried on every registration and verified name-equal to the seam's `CAPABILITY_OPERATIONS` at import time (fail-loud drift guard) |
| `resilience/model.py` (M015) + `replan/` (M008) | `REALIZATION_STATES` (through `resilience.model` — the accepted R8 surface; identity with the `replan` kernel object proven at import and in the battery), `REALIZATION_TERMINAL_STATES`, `REALIZATION_TRANSITIONS` | imported; the ladders project onto the kernel, never redefine it; the kernel's transition edges validate ladder adjacency |
| `resilience/handover.py` (M015) + `contracts/` (M002) | `CONSTRAINT_KINDS` (the typed constraint vocabulary the accepted handover gates validate against); the handover machinery itself (`handover_candidate`, `handover_verdict`, `validate_handover_preserves_contract`) driven by the battery as the LOCK-108 proof | imported; the declarations state the machinery's OWN frozen semantics verbatim (the FULL 12-kind set); the battery drives the REAL gates: a preserving candidate verdict accepted, a weakening candidate rejected with the typed kind-citing reason |
| `protocol/` | `canonical_json_bytes`, `parse_instant` | imported (the WORK-003 canonical-JSON and RFC 3339 conventions) |

No accepted authority imports `accesstech/` (the one-way boundary, AST-verified over
all 26 accepted packages by the battery's case_17). The legacy 1.0 reservoir
(`imt/`, `transport/`, `topology/`, `networkpath/`, `sessions/`, `mobility/`,
`multipath/`, `edge/`, `appliance/`, `mobile/`, `management/`, `simulator/`,
`resources/`, `services/`) is un-imported source material only.

## 3. The M020 battery (19/19)

`python3 tools/accesstech_selftest.py` — all 19 cases green, run 3× consecutively on
the delivery head (byte-identical output; exit-code-based verification — a traceback
or lowercase "failed" IS a failure).

| Charter criterion | Battery verification | Class | Case(s) |
|---|---|---|---|
| (1) typed technology-envelope surface; deterministic ranges; canonical-JSON round-trips; content-derived identities | 7 declared envelopes (the six family classes + the synthetic future class) round-trip canonical-JSON byte-identically with stable, content-derived, content-sensitive identities; integer base units; injected instants | SOFTWARE | case_01 |
| (1) fail-closed envelope validation (typed rejections) | 5 empty/degenerate classes (ENVELOPE_DEGENERATE), 5 inverted-bound classes (ENVELOPE_INCONSISTENT), contradictory content (disordered/overlapping windows), malformed ids/instants/floats, identity tampering (IDENTITY_MISMATCH) and grammar drift (SERIALIZATION_INVALID) — all typed, never warnings | SOFTWARE | case_02, case_03, case_04 |
| (2) degradation ladders composed from the accepted resilience/ realization-state vocabulary (extended without redefining it) | the imported-object identity proof (accesstech's vocabulary IS `resilience.model`'s object IS the `replan` kernel object; the frozen four-state set); every mode of all 7 ladders maps into the kernel; round-trips byte-identical | SOFTWARE | case_05 |
| (2) deterministic stepping; every mode in the accepted vocabulary; no undeclared modes | full walks to the explicit terminal rungs; rebuilt-ladder stepping identical; 10 malformed classes typed (undeclared states, terminal stepping, recovery edges, post-terminal rungs, duplicates, missing terminal rung) | SOFTWARE | case_06, case_07 |
| (3) handover characteristic declarations consumed BY REFERENCE (LOCK-108 constraint-set declarations per kind) | 4 kinds declared; the preserved set == the imported frozen 12-kind vocabulary verbatim (== the machinery's own set); round-trips byte-identical; identities content-derived per kind | SOFTWARE | case_08 |
| (3) declarations never weaken the machinery | 6 weakened/contradictory declaration classes + identity tampering typed (weakened subsets, unknown kinds, silent swaps, contract-breaking, duplicates) | SOFTWARE | case_09 |
| (3) the REAL machinery drives the proof | the accepted `handover_verdict`/`validate_handover_preserves_contract` over a real mature M002 contract: a preserving candidate ACCEPTED; a weakening candidate REJECTED with the typed kind-citing reason; the raising gate typed; the declared set covers every enforceable kind | SOFTWARE | case_10 |
| (4)+(5) the registration surface through the accepted seam + LOCK-109 bridge, ZERO contract-core delta, proven by registering the six accepted families | all six families register through the ONE public path: envelope/ladder/descriptor carried by reference; capability statement + LOCK-112 tags verbatim; the bridge vocabularies frozen name-equal; identities content-derived and distinct | SOFTWARE | case_11 |
| (4) registration resolves BY REFERENCE (no re-instantiation, no second runtime) | repeated resolution returns the SAME live adapter/runtime/descriptor objects; the public runtime carries the composition's technology; canonical records round-trip with the live references re-supplied | SOFTWARE | case_12 |
| (4) each registration resolves to the accepted composition's public runtime | full typed lifecycles (reserve → activate → measure → release) green through each registration's public runtime for five families; the Wi-Fi AP-release fail-closed family discipline disclosed (the accepted M007 case_65 shape, deterministic through the seam — never papered over); the registry resolves all six (sorted, identity-preserving) | SOFTWARE | case_13 |
| (5) the extension proof: a synthetic future envelope registers through the SAME public path | the synthetic class (never named by the 1.1 architecture, UNKNOWN_BUT_WELL_FORMED via the accepted classifier) registers through the identical function object; full lifecycle green; registry lookup resolves; the registration code branches on no technology name (AST audit) | SOFTWARE | case_14 |
| (4) fail-closed registration validation | 7 cross-surface contradictions + registry duplicate/unknown discipline — all typed rejections | SOFTWARE | case_15 |
| (5) ZERO contract-core delta | the AST import audit (the only `contracts` import anywhere in `accesstech/` is the frozen `CONSTRAINT_KINDS` vocabulary constant); the git-guarded PR delta touches no `contracts/` file and stays inside the R9-CORE-001 scope | SOFTWARE | case_16 |
| (7) every accepted authority consumed by reference only; one-way imports | no accepted authority (26 packages) references `accesstech` in code (AST tokens); the domain itself clock/random/network-free with imports confined to stdlib + protocol + the accepted authorities; the legacy reservoir un-imported | SOFTWARE | case_17 |
| (6) deterministic, offline, seeded; no wall clock, no randomness, no network; secrets never stored | injected instants only; in-process rebuild byte-identical; the full registration material (six families + the synthetic extension) byte-identical across PYTHONHASHSEED 0/1/42 subprocesses | SOFTWARE | case_18 |
| evidence honesty | this record discloses SOFTWARE class, the by-reference map, the lock mapping and the open physical obligations; no affirmative physical claims | SOFTWARE | case_19 |

## 4. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** `accesstech/` imports no contract-authority
  surface at all — the only `contracts` import is the frozen `CONSTRAINT_KINDS`
  vocabulary constant (AST-audited, case_16); the registration path creates,
  mutates and re-derives no contract. `ConnectivityContract` stays the sole
  authority for acquired connectivity.
- **LOCK-105 (no global topology):** the availability windows are
  technology-class-local declared intervals (the technology's own operating
  windows — e.g. the DTN opportunistic contact windows, the future synthetic
  class's declared windows); no provider infrastructure facts, no
  global-availability assertions, nothing topology-shaped crosses.
- **LOCK-106 (content-derived identities / evidence typing):** every identity in
  the domain (envelope, ladder, handover characteristics, registration) is sha256
  over the canonical JSON of the declaration's content, namespaced per record kind;
  identities are recomputed and compared at reconstruction (tamper evidence at
  construction AND load); never wall clock, never randomness.
- **LOCK-108 (no silent contract weakening):** the handover declarations state the
  accepted machinery's OWN frozen semantics — the FULL imported 12-kind
  constraint vocabulary preserved verbatim per kind; weakened declarations fail
  closed (HANDOVER_ILLEGAL) and the battery drives the REAL accepted gates to
  prove the machinery's verdict behavior (a weakening candidate rejected with the
  typed kind-citing reason). The declaration layer never weakens what the
  machinery enforces.
- **LOCK-109 (execution bridge):** every registration carries the frozen plan-side
  adapter-operation vocabulary (`executionplans.ADAPTER_OPERATIONS`) verified
  name-equal at import time to the seam's `CAPABILITY_OPERATIONS` (fail-loud drift
  guard) — the technology is named by the canonical execution bridge, never by the
  contract core.
- **LOCK-110/LOCK-112 (adapter isolation / standard leverage):** access
  technologies enter ONLY through the accepted adapter boundary — the registration
  surface drives the accepted `adapters/capability.py` seam (register → open →
  CapabilityAdapter wrap) and composes through the mediated WORK-016 runtime; the
  LOCK-112 mechanism tags ride as citation DATA (never a branch input; the
  battery's AST audit proves the registration code branches on no technology
  name); provider-SDK types stay behind the seam (the battery verifies the
  boundary returns the canonical typed records).
- **LOCK-117 (authority uniqueness):** an envelope, ladder, handover declaration
  or registration is DECLARED DATA around the canonical authority — never a second
  contract authority; the registration record's canonical projection deliberately
  excludes the live composition objects (in-memory references, never persisted
  authority); the registry is an in-memory composition index.
- **LOCK-119 (secrets):** no wall clock, no randomness, no network, no secrets
  anywhere in `accesstech/` (AST-audited, case_17); injected RFC 3339 UTC instants
  only (validated through `protocol.temporal`); integer base units (the canonical
  JSON subset rejects floats — the degenerate/typed rejections fire on
  non-integers).

## 5. The full suite at the delivery head

The full battery suite in exact CI workflow order with exit-code-based detection —
ALL green at the delivery head (the numbered list in the PR body). The accesstech
step (wired at the branch root by the DEC-0120 governance commit as a pre-delivery
existence guard) ACTIVATES with this delivery and runs 19/19. The accepted batteries
run at their accepted counts (verified at this head, the numbers grepped from the
workflow and the accepted evidence docs before citing): resilience 36/36, localfirst
35/35, recovery 36/36, credential 32/32, scale 53/53, contract 54/54, offer 49/49,
developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33, roamlink 56/56,
comos 33/33, assurance 97/97, executionplan 36/36, adapter 70/70, replan 38/38,
payment 44/44, eligibility 46/46, policy 103/103, client 24/24, conformance 63/63.
The governance gates: `authorization_provenance.py` PASS (the delta exactly covered
by R9-CORE-001: `accesstech/`, `tools/accesstech_selftest.py`,
`docs/M020-evidence.md`), `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
`architecture_drift_guard.py` PASS with an implementation-only classification,
`fresh_session_check.py --actual-main-sha "$(git rev-parse origin/main)"` PASS.

## 6. Judgment calls (disclosed)

1. **The realization-vocabulary import path (both readings of the charter satisfied
   at once).** The charter's M020 section says the ladders compose from "the
   accepted `resilience/` realization-state vocabulary (the M008-owned kernel
   consumed BY REFERENCE — import it, never redefine it)". The kernel object lives
   in `replan/` and the accepted `resilience.model` imports it from there. The
   resolution: `accesstech/ladders.py` imports `REALIZATION_STATES` from
   `resilience.model` (the accepted R8 surface — literally the accepted
   realization-state vocabulary) and the kernel's terminal/transition structures
   from `replan` (the kernel owner, the same import path the accepted resilience
   domain itself uses), with an import-time identity check that the two are the
   SAME object; the battery's case_05 proves the three-way object identity. Both
   authorities are legal one-way imports; nothing is redefined.
2. **The mode-level extension disclosed as extension, not redefinition.** A
   degradation ladder needs multiple DEGRADED rungs (the M021 "declared capacity
   steps" semantics) while the kernel's state-level transition map has no
   DEGRADED→DEGRADED edge. The ladder models MODES (new names) mapped onto the
   frozen four states; adjacent rungs are validated as either the identity (a
   deeper capacity step on the same explicit state — the disclosed mode-level
   extension) or an edge present in the imported kernel map (a ladder never uses a
   kernel-illegal edge and never invents a fifth state). This is the charter's
   "extended without redefining it", stated openly.
3. **The LOCK-108 full-set declaration semantics.** A per-kind preserved-constraint
   set smaller than the full frozen 12-kind vocabulary could read as "some
   constraint kinds are optional across this handover kind" — a weakening of the
   accepted machinery's verbatim-equality semantics. The declarations therefore
   require EXACTLY the full imported set (subset → typed HANDOVER_ILLEGAL; superset
   → typed VOCABULARY), and the battery drives the real machinery to prove the
   enforcement behavior (case_10).
4. **The Wi-Fi release discipline disclosed, not papered over.** The accepted Wi-Fi
   family's frozen 12-op contract has no AP decommission, so the AP-ref release
   fails closed deterministically through the seam (the accepted M007 battery's own
   case_65 disclosure). This delivery's case_13 surfaces exactly that behavior
   (reserve → activate → measure green; the release rejected twice with the same
   typed reason) rather than asserting a green release the family cannot honestly
   produce — the M007 family-discipline precedent, never a weakening of this
   battery's determinism (the expected outcome is deterministic either way).
5. **The RAN composition's None binding requirements accepted verbatim.** The
   accepted `adapters/reference/ran.py` `mount_reference` returns `None` binding
   requirements (the family's documented shape: no caller coordinates). The
   registration surface accepts `None` (normalized to the empty wiring data)
   instead of rejecting the accepted composition's own return shape — consuming the
   accepted surface by reference means accepting its declared shapes.
6. **The battery as composition root for the six families (the M019 house
   pattern).** The family mounts need family-specific reader facades (mesh needs
   nodes+path; wifi an AP-profile reader; ip a topology reader; ran nothing). The
   registration surface receives the mounted products (the caller mounts through
   the accepted public `mount_reference` factories); the battery is the composition
   root wiring the fixtures — the M007 battery's own pattern (`_m007_family_mounts`),
   and the case_66 cross-battery import precedent licenses this battery's reuse of
   the M007 battery's public fixture helpers (`adapter_selftest` /
   `resilience_selftest` — their fixtures, never their assertions).
7. **The canonical registration record excludes the live objects (disclosed).**
   The registration's `to_dict()` carries the declared identity-bearing content
   only; the live `CapabilityAdapter`/`AdapterRuntime`/`AdapterDescriptor` objects
   are in-memory references (not serializable, not persisted authority — LOCK-117).
   Reconstruction (`technology_registration_from_mapping`) re-supplies the live
   objects through the accepted surfaces and re-derives the identity — the
   battery's case_12 verifies the round-trip preserves both the canonical identity
   and the live-object identity.

## 7. Out-of-scope discipline (nothing else changed)

The delta contains ONLY the eight files above (`accesstech/` — six modules,
`tools/accesstech_selftest.py`, `docs/M020-evidence.md`). No control-plane surface
(`spec/`, `.github/`, `AGENTS.md`, `README.md`), no contract-core change, no
accepted-domain modification (`contracts/`, `adapters/`, `executionplans/`,
`replan/`, `resilience/`, or any other authority — all consumed by reference only).
The parallel M023 worker's in-flight surface (`adapters/reference/futureimt.py`,
`tools/futureimt_selftest.py`, `docs/M023-evidence.md`) is untouched and absent at
this head. The CI workflow is unchanged (the accesstech step was wired by the
DEC-0120 governance commit at the branch root; this delivery activates it).

## 8. Evidence classes (honest disclosure)

Every verification in this record is SOFTWARE class — deterministic, offline,
reproducible battery evidence over the accepted code surfaces. No PHYSICAL PASS is
claimed: EVID-002..EVID-008 (the open physical obligations) remain open and
untouched by this delivery, exactly as the R9 charter's evidence policy requires.
The battery never converts software evidence into physical claims; the evidence-doc
honesty case (case_19) mechanically enforces the disclosure.

## 9. Delivery provenance

Delivered in ONE worker session on the append-only branch `m020-accesstech` (no
rebase, no force-push, no amending), rooted at the DEC-0120 activation head
`a53910546d04f9555f481f80c29d610f8a136031`, commit-as-you-go: the domain first
(commit `fa27371`), then the battery, then this evidence record (the final head is
in the PR body). The verification numbers in §3/§5 were produced at the final
delivery head by direct execution (battery x3 byte-identical; the full suite in
exact CI order with exit-code-based detection; the five governance gates).
