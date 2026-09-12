# M021 — Wireline Access Adapters — Evidence Record

**Work Item:** M021 · **Authorization:** R9-CORE-001 (DEC-0120, the bounded R9 program
authorization; M021 is the R9 charter's current chain child — its M020 dependency
satisfied by the DEC-0121 acceptance; the current child, authorization R9-CORE-001)
**Baseline:** the branch rides the DEC-0121 M020-acceptance head
`fe27c9962f5e5ad4da9b355bf3be1172825bf4fe` (verified `git rev-parse HEAD` equal before
any work — the live main; the pre-delivered wireline CI step exists at that head —
the DEC-0121 existence guard wired by the governance acceptance commit).

This record persists the verified facts of the M021 delivery. Every claim below is
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

**DISCLOSED CONFLICT (the battery-scope-repair stop class, surfaced per the worker
charter — the Tech Lead records the resolution):** the accepted M007 adapter battery
(`tools/adapter_selftest.py`, 70/70 at the DEC-0121 head) freezes its case_68
adapters/-delta guard to exactly the nine declared M007 files
(`expected_delta`), asserting the adapters/ delta vs `origin/main` is exactly the
M007 harvest set. The M021 charter scope REQUIRES the new
`adapters/reference/wireline.py` (declared by the R9 charter and the R9-CORE-001
authorization), so once this delivery's file is committed, case_68 reports
`undeclared adapters/ change: ['adapters/reference/wireline.py']` and the adapter
battery reads 69/70 at this head — VERIFIED experimentally at this head (probe commit
→ 69/70 with exactly that case failing → revert → 70/70). The same guard will meet
the M022 (`adapters/reference/satellite.py`) and M023
(`adapters/reference/futureimt.py`) deliveries identically. Per the worker charter's
battery-scope-repair clause this delivery does NOT patch another domain's battery
(none are pre-authorized for this delivery); the resolution belongs to the Tech Lead
(the R9 charter's declared path for a disclosed evolution of an accepted shared
battery surface — the M019 `tools/scale_selftest.py` precedent, or a Tech Lead-owned
expected-set reconciliation). Every other verification below is green at this head.

**TECH LEAD RESOLUTION (2026-09-12, pre-merge amendment commit):** the conflict
above is resolved on the R9 charter's own declared path. The Consumption rule
(live charter text, ratified by DEC-0120 at activation) sanctions "a disclosed
evolution of an accepted shared battery surface [that] follows the M019
`tools/scale_selftest.py` precedent — disclosed, append-only in intent, never
assertion-weakening". Applied to case_68: the `expected_delta` set gains
EXACTLY `adapters/reference/wireline.py` (this delivery's declared file),
authored by the Tech Lead on this branch as an amendment commit — the worker
session ended after its push and PR (the turn's stream died mid-report; the
delivery itself, this record, and the PR body carry the complete report), and
the worker charter's battery-scope-repair clause correctly left this battery
untouched. Nothing is weakened: the W016 canonical flow, the 54-name baseline
export table, the family export counts, and the six family-subpackage
byte-identity assertions are unchanged; the guard still rejects every other
undeclared adapters/ change. The M022 (satellite.py) and M023 (futureimt.py)
siblings repeat this pattern at their own acceptances — never before
(pre-adding them would weaken the guard for unaccepted deliveries).
Re-verified at the amended head by the integration station (direct execution):
adapter battery **70/70**; wireline battery **14/14 x3 byte-identical**; the
five R8 batteries at their accepted counts (scale 53/53, credential 32/32,
recovery 36/36, resilience 36/36, localfirst 35/35); accesstech 19/19; all six
governance gates rc=0 (the acceptance decision DEC-0122 records the reviewed
numbers).

## 1. Delivered surface

- **`adapters/reference/wireline.py` (NEW — the wireline reference compositions)** —
  the Ethernet, fiber and enterprise-WAN access families of the R9 charter M021
  scope as reference adapter compositions on the M020 envelope domain, composing the
  ACCEPTED `adapters/backhaul/` family runtime — the
  `BackhaulManager` over the deterministic `ReferenceBackhaulEngine` with the
  accepted WORK-016 SDK bridge (`BackhaulTechnologyAdapter`) — **BY REFERENCE**
  through the accepted `adapters/capability.py` seam (the M007 LOCK-110/LOCK-112
  boundary; every composition calls the family's OWN public runtime APIs — the
  M007 `adapters/reference/backhaul.py` pattern, followed exactly):
  - **`mount_reference`** — the ETHERNET family (technology class
    `access.ieee.8023`, KNOWN in the WORK-002 registry — the same registry entry
    the accepted M007 backhaul reference composition declares): one IEEE 802.3
    Ethernet link profile provisioned through the manager's public
    `provision_link` (1 Gbps, 8 bearers);
  - **`mount_fiber_reference`** — the FIBER family (technology class
    `access.itu.g709`, open-world well-formed declared data — the ITU-T G.709
    OTN class the architecture's registry never named, entering as data exactly
    the open-world classifier's design): one G.709 OTN fiber trail provisioned
    through the same public API (10 Gbps, 8 bearers);
  - **`mount_enterprise_wan_reference`** — the ENTERPRISE-WAN family (technology
    class `access.enterprise.wan`, open-world well-formed declared data) over
    IEEE 802.1Q bridged Ethernet: the DECLARED site topology
    (`SiteTopology`) with one bridged circuit provisioned per declared site
    pair, plus the declared site-pair link map handed back to the composition
    root.
  - **`SiteTopology`** — the declared enterprise-WAN site topology as DECLARED
    DATA ONLY (LOCK-105 — never global topology): the enterprise's own declared
    site set (operator-chosen site labels on the accepted family's
    endpoint-label grammar — a grammar that mechanically excludes NodeID-shaped
    values) plus the declared site pairs the WAN interconnects; bounded
    (16 sites / 64 pairs), canonically ordered, canonical-JSON serializable
    with a content-derived identity (LOCK-106 — sha256 over the canonical
    bytes, recomputed and compared at reconstruction); fail-closed typed
    rejections on every malformed class (a pair referencing a site OUTSIDE the
    declared set — the topology-leak class; self-pairs; duplicates; disordered
    sites/pairs; empty sets; grammar violations; identity tampering);
    `declares_pair` is an EXACT declared lookup — the record never computes a
    transitive closure, so an undeclared pair stays undeclared however many
    declared pairs share its endpoints.
  - The LOCK-112 standard-mechanism tags (`ieee-802.3-ethernet`,
    `ieee-802.1q-bridged`, `itu-t-g709-otn`) are the accepted family's own
    frozen citation tags, carried verbatim as citation DATA (never a branch
    input); the descriptors declare the family's accepted capability statement
    (`REFERENCE_CAPABILITIES`, imported BY REFERENCE from the accepted M007
    reference composition module).
- **`accesstech/wireline.py` (NEW — the wireline family declarations, under the
  M020-owned shared prefix)** — the wireline family envelope/ladder/handover
  declarations built ONLY through the accepted M020 public surface
  (`accesstech.envelopes` / `accesstech.ladders` / `accesstech.handovers`
  imported relative, never edited): the three capability envelopes with
  **static-availability semantics** (exactly ONE continuous declared window per
  family — the standing service interval; NO mobility vocabulary anywhere on
  the declared surface; the multi-window pass/mobility shape is the typed
  ENVELOPE_INCONSISTENT rejection — `require_static_availability` /
  `is_static_availability`, the typed discipline on the accepted grammar); the
  three degradation ladders as **declared capacity steps** (named rungs on the
  accepted M008-owned REALIZING/DEGRADED/FAILED kernel — REALIZING at the
  satisfying root, the explicit DEGRADED state on every middle rung, the
  explicit FAILED terminal rung; every step an evidence-visible deterministic
  transition through `ladder_step`); and the handover declarations per family
  through the accepted `declare_handover_kind` constructor (the machinery's own
  frozen LOCK-108 semantics — the FULL preserved constraint-kind set, the
  mandatory explicit-reconnect and contract-continuity disciplines). The
  frozen `accesstech/__init__.py` surface stays untouched (the new module is
  imported directly by the battery — the accepted initializer never imports
  it; one-way imports hold).
- **`tools/wireline_selftest.py` (NEW — the M021 battery)** — deterministic,
  offline, seeded — 14 cases covering (a) the declarations (canonical
  round-trips, content-derived identities, static availability, capacity-step
  ladders), (b) the three families registered through the accepted M020
  extension surface and resolving BY REFERENCE to the accepted backhaul
  runtime, (c) the nine WORK-016 operations in deterministic
  reserve/activate/measure flows including the deterministic re-bind
  translation for mid-session reconfiguration (with the enterprise-WAN's
  mid-session site reselection), (d) the declared enterprise-WAN site topology
  as declared data (LOCK-105 — the topology-leak class a typed failure; no
  transitive closure; exactly the declared pairs provisioned), (e) LOCK-110
  provider-SDK isolation (canonical typed records; zero opaque family
  references outside the disclosed caller-supplied wiring snapshots; no
  technology branching in the composition code) and the typed fail-closed
  matrix, (f) the one-way import audit, the zero contract-core delta +
  authorization-scope audit, determinism (in-process rebuild and
  PYTHONHASHSEED 0/1/42 cross-process byte-identity), and the evidence-doc
  honesty check (this record).
- **`docs/M021-evidence.md` (NEW)** — this record.

## 2. The by-reference composition map (the M014/M019 discipline, disclosed)

| Consumed authority | The exact surface consumed | How |
|---|---|---|
| `adapters/backhaul/` (the accepted WORK-022 family runtime — the IEEE 802.3/802.1Q/ITU-T G.709 standards base) | `BackhaulManager` (public `register_implementation` / `provision_link`), `ReferenceBackhaulEngine`, `BackhaulTechnologyAdapter` (the accepted WORK-016 SDK bridge), `BackhaulProfile` / `LinkDescriptor`, `validate_endpoint_label`, `BackhaulError` / `BackhaulReasonCode` | imported; every composition wires the family runtime EXACTLY as the accepted M007 reference composition does (manager + default engine + public link provisioning + the bridge) — the family contract never changes, never re-implemented, never bypassed |
| `adapters/reference/backhaul.py` (the accepted M007 reference composition) | `REFERENCE_CAPABILITIES` (the family's accepted capability statement) | imported; the wireline descriptors declare the family's accepted capability references verbatim (the mediated runtime filters exposure to the declared set — the honest composition) |
| `adapters/capability.py` + `adapters/runtime.py` + `adapters/model.py` + `adapters/validation.py` + `adapters/errors.py` (M007) | `CapabilityAdapter`, `AdapterRuntime`, `AdapterDescriptor`, `CAPABILITY_OPERATIONS`, `CAPABILITY_TRANSLATION_MAP`, the typed record vocabularies (`CapabilityView`, `OfferView`, `Allocation`, `Activation`, `Measurement`, `Reconfiguration`, `ReleaseReceipt`, `HealthReport`), `AdapterError` | consumed through the accepted M020 registration surface (the battery registers the compositions through `register_access_technology`, which drives `runtime.register` → `runtime.open_adapter` → `CapabilityAdapter(...)`); the seam's mediation, sandbox isolation and deterministic step budgets stay in force mechanically |
| `accesstech/` (the accepted M020 envelope domain — the composition substrate, imported and driven, never edited) | `CapabilityEnvelope` / `BpsRange` / `LatencyMilliRange` / `JitterMilliRange` / `AvailabilityWindow` / `AvailabilityWindows`, `DegradationLadder` / `DegradationMode`, `declare_handover_kind`, `register_access_technology` / `TechnologyRegistry` / `technology_registration_from_mapping`, `AccessTechError` | imported (relative, inside the M020-owned prefix); the wireline declarations are constructed ONLY through these accepted typed constructors; the registrations drive the accepted extension surface verbatim |
| `executionplans/` (M006) | `ADAPTER_OPERATIONS` (the LOCK-109 bridge vocabulary) | carried on every registration by the accepted surface and verified name-equal to the seam's `CAPABILITY_OPERATIONS` (the battery re-asserts the frozen equality) |
| `protocol/` | `canonical_json_bytes` | imported (the WORK-003 canonical-JSON convention — the site-topology identity and the battery's byte-comparisons) |

One-way imports (AST-verified by the battery's case_11 over the 27 authority
packages): no accepted authority references `wireline`; the frozen package
initializers (`accesstech/__init__.py`, `adapters/reference/__init__.py`) stay
untouched; `adapters/reference/wireline.py` never imports `accesstech`;
`accesstech/wireline.py` imports only the accepted accesstech surface (relative
imports only). The legacy 1.0 reservoir (`imt/`, `transport/`, `topology/`,
`networkpath/`, `sessions/`, `mobility/`, `multipath/`, `edge/`, `appliance/`,
`mobile/`, `management/`, `simulator/`, `resources/`, `services/`) is un-imported
source material only.

## 3. The M021 battery (14/14)

`python3 tools/wireline_selftest.py` — all 14 cases green, run 3× consecutively on
the delivery head (byte-identical output; exit-code-based verification — a traceback
or lowercase "failed" IS a failure).

| Charter criterion | Battery verification | Class | Case(s) |
|---|---|---|---|
| (1) Ethernet/fiber/enterprise-WAN families as reference adapter compositions on the M020 envelope, composing the accepted adapters/backhaul/ family runtime BY REFERENCE through the accepted adapters/capability.py seam | all three compositions mount the accepted family runtime (manager + engine + SDK bridge, the M007 wiring) and register through the accepted M020 public path; envelopes/ladders/handover declarations carried by reference; the LOCK-109 bridge frozen name-equal; LOCK-112 tags + LOCK-108 preserved sets verbatim; identities content-derived and distinct | SOFTWARE | case_01, case_04 |
| (1) registration resolves BY REFERENCE to the accepted backhaul runtime | identity-preserving resolution (the SAME live adapter, runtime and descriptor objects — no re-instantiation, no second runtime); the public runtime carries the composition's technology; canonical records round-trip with the live references re-supplied | SOFTWARE | case_05 |
| (2) wireline capability envelopes with static-availability semantics; degradation ladders as declared capacity steps (each an explicit evidence-visible transition) | exactly ONE continuous declared window per family (the standing service interval); the multi-window pass/mobility shape is the typed ENVELOPE_INCONSISTENT rejection; no mobility vocabulary anywhere on the declared surface (the canonical envelope members are exactly the frozen grammar); every ladder walked rung-by-rung — every middle rung an explicit DEGRADED capacity step, the terminal rung FAILED, each transition materialized as a canonical evidence-visible trail (rebuilt-ladder walks identical); undeclared/terminal stepping typed | SOFTWARE | case_02, case_03 |
| (3) deterministic reserve/activate/measure flows through the nine WORK-016 operations with the deterministic re-bind translation for mid-session reconfiguration | the frozen disclosed translation map verified; every flow green through the mediated nine-op runtime (capabilities / allocate / bind_session / observe / unbind_session / release / health + the registration open drive); typed canonical records at every step; the re-bind translation verified per family (the SAME session, the PRESERVED reservation, the previous binding released FIRST, a NEW binding created — typed Reconfiguration records; ACTIVE → RECONFIGURED; idempotent second reconfiguration; measure + release green after the re-bind) — including the enterprise-WAN mid-session SITE RESELECTION onto another declared site pair | SOFTWARE | case_06, case_07 |
| (4) declared enterprise-WAN site-topology as declared data only (LOCK-105 — never global topology) | canonical round-trips with tamper evidence; 9 malformed classes typed-rejected (the undeclared-site pair IS the topology-leak class; self-pairs, duplicates, disorder, empty sets, NodeID-shaped labels, identity tampering, grammar drift); NO transitive closure (an undeclared pair stays undeclared); the composition provisions EXACTLY the declared pairs; the boundary views carry no topology facts | SOFTWARE | case_08 |
| (5) LOCK-112 (the families model the standard mechanisms) and LOCK-110 (provider-SDK types never enter the core) | every 1.1 operation returns the canonical typed provider-neutral records; zero opaque family technology references in any canonical record byte outside the disclosed caller-supplied wiring snapshots (LOCK-017 binding DATA); the binding ids are ADCOS content-derived (sha256:), never the opaque bearer refs; the LOCK-112 tags are citation DATA; the composition code branches on no technology name (AST audit over the modules' own vocabulary) | SOFTWARE | case_09 |
| (6) deterministic, offline, seeded; no wall clock, no randomness, no network; secrets never stored (LOCK-119); typed fail-closed everywhere | injected instants only; the typed fail-closed matrix (4 isolated failure classes with deterministic reasons twice each, 4 caller-side typed raises, 3 terminal-state rejections, declaration rejections re-firing identically); both new modules clock/random/network-free; in-process rebuild byte-identical (registrations, envelopes, ladders, lifecycle records, site links, registry order); the full wireline material byte-identical across PYTHONHASHSEED 0/1/42 subprocesses | SOFTWARE | case_10, case_13 |
| (7) every accepted authority consumed by reference only; one-way imports | no accepted authority references the new modules (AST tokens over 27 packages); the frozen package initializers untouched; `adapters/reference/wireline.py` never imports accesstech; `accesstech/wireline.py` imports only the accepted accesstech surface; zero contracts imports in the new modules; the PR delta touches no contract-core file and stays inside the R9-CORE-001 scope | SOFTWARE | case_11, case_12 |
| evidence honesty | this record discloses SOFTWARE class, the by-reference composition, the lock mapping, the disclosed case_68 conflict and the open physical obligations; no affirmative physical claims | SOFTWARE | case_14 |

## 4. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the new modules import NO contracts surface at
  all (AST-audited, case_12 — zero contracts imports, a stronger shape than the
  M020 CONSTRAINT_KINDS-only audit); no contract is created, mutated or re-derived
  anywhere in the delivery. `ConnectivityContract` stays the sole authority for
  acquired connectivity.
- **LOCK-105 (no global topology):** the declared enterprise-WAN site topology is
  the enterprise's OWN declared site set — operator-chosen labels on the accepted
  family's endpoint-label grammar (mechanically excluding NodeID-shaped values),
  bounded by its own declaration (a pair referencing an undeclared site is the
  typed topology-leak rejection), computing NO transitive closure (undeclared pairs
  stay undeclared), never a global topology database; the boundary views carry no
  topology facts (case_08).
- **LOCK-106 (content-derived identities / evidence typing):** every identity in the
  delivery (the three envelopes, the three ladders, the handover characteristics,
  the registrations, the site topology) is sha256 over the canonical JSON of the
  declared content through the accepted surfaces' own derivation conventions;
  identities are recomputed and compared at reconstruction (tamper evidence at
  construction AND load); never wall clock, never randomness.
- **LOCK-108 (no silent contract weakening):** the wireline handover declarations
  are built ONLY through the accepted `declare_handover_kind` constructor — the
  machinery's own frozen full-set semantics (the FULL imported 12-kind constraint
  vocabulary preserved verbatim per kind; the mandatory explicit-reconnect and
  contract-continuity disciplines); the declarations never weaken what the
  machinery enforces (the accepted M020 surface rejects weakened declarations
  itself).
- **LOCK-109 (execution bridge):** every registration carries the frozen plan-side
  adapter-operation vocabulary (`executionplans.ADAPTER_OPERATIONS`) verified
  name-equal to the seam's `CAPABILITY_OPERATIONS` (the accepted import-time guard;
  the battery re-asserts the frozen equality) — the wireline technologies are named
  by the canonical execution bridge, never by the contract core.
- **LOCK-110 (adapter isolation):** the wireline families enter ONLY through the
  accepted adapter boundary — the compositions are registered through the accepted
  `adapters/capability.py` seam (register → open → CapabilityAdapter wrap) and
  compose through the mediated WORK-016 runtime; every 1.1 operation returns the
  canonical typed provider-neutral records; the opaque family technology references
  (`backhaul:link:<hex>` / `backhaul:bearer:<hex>`) stay behind the runtime (the
  disclosed caller-supplied wiring snapshots are LOCK-017 binding DATA, and the
  activation ledger's binding ids are ADCOS content-derived) — case_09.
- **LOCK-112 (standard leverage):** the families model the standard mechanisms —
  the compositions drive the accepted backhaul family runtime (the IEEE
  802.3-2018 / 802.1Q-2022 / ITU-T G.709 standards base) whose own frozen
  citation tags the wireline compositions carry verbatim as DATA (never a branch
  input; the AST audit proves the composition code branches on no technology
  name); nothing is reinvented.
- **LOCK-119 (secrets):** no wall clock, no randomness, no network, no secrets
  anywhere in the new modules (AST-audited, case_11); injected RFC 3339 UTC
  instants only; integer base units; the credential SLOT NAME only (never
  material); the site labels and link profiles are fixed declared data.

## 5. The full suite at the delivery head

The full battery suite in exact CI workflow order with exit-code-based detection —
**one disclosed exception** (the battery-scope-repair stop class, §0 above): the
adapter battery reads **69/70** at this head (case_68's frozen M007-era
`expected_delta` set cannot see the R9-CORE-001-declared
`adapters/reference/wireline.py`; root-caused and evidenced; NOT patched per the
worker charter — the Tech Lead records the resolution). Every other step is green
at this head, the wireline step ACTIVATING with this delivery (the DEC-0121
pre-delivery existence guard finding `tools/wireline_selftest.py`) at 14/14, the
accesstech step at its accepted count 19/19 (verified with the new
`accesstech/wireline.py` present — its audits govern the new module and pass), and
the accepted batteries at their accepted counts (resilience 36/36, localfirst
35/35, recovery 36/36, credential 32/32, scale 53/53, contract 54/54, offer 49/49,
developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33, roamlink 56/56,
comos 33/33, assurance 97/97, executionplan 36/36, replan 38/38, payment 44/44,
eligibility 46/46, policy 103/103, client 24/24, conformance 63/63 — the numbers
grepped from the workflow and the accepted evidence docs before citing). The
governance gates: `authorization_provenance.py` PASS (the delta exactly covered by
R9-CORE-001: `adapters/reference/wireline.py`, `accesstech/wireline.py`,
`tools/wireline_selftest.py`, `docs/M021-evidence.md`), `current_spec_check.py`
PASS, `tech_lead_guard.py` PASS, `architecture_drift_guard.py` PASS with an
implementation-only classification, `fresh_session_check.py --actual-main-sha
"$(git rev-parse origin/main)"` PASS.

## 6. Judgment calls (disclosed)

1. **The adapter battery case_68 conflict surfaced, not patched.** The worker
   charter's battery-scope-repair clause reserves cross-battery repairs for the
   Tech Lead ("NONE are pre-authorized for this delivery"), and the R9 charter
   reserves disclosed evolutions of accepted shared battery surfaces for explicit
   decisions (the M019 `tools/scale_selftest.py` precedent). This delivery
   therefore lands its complete in-scope work item and discloses the conflict with
   experimental evidence (probe commit → 69/70 → revert → 70/70) rather than
   editing another domain's battery. The M022/M023 deliveries will meet the same
   guard identically (both add `adapters/reference/*.py` files) — one Tech
   Lead-owned resolution (an expected-set reconciliation or a disclosed evolution)
   covers the whole tranche.
2. **The fiber and enterprise-WAN technology classes are open-world declared
   data.** The WORK-002 registry knows `access.ieee.8023` (the Ethernet entry the
   accepted M007 backhaul composition declares) but has no fiber or enterprise-WAN
   entry. The R9 gate's objective is exactly this open-world shape: the fiber
   family declares `access.itu.g709` (the ITU-T G.709 class) and the enterprise
   WAN declares `access.enterprise.wan`, both UNKNOWN_BUT_WELL_FORMED through the
   accepted classifier — the classes enter as data through the same registration
   path, no registry edit, no code change (the M020 extension-proof discipline
   applied to the wireline tranche).
3. **The wireline descriptors declare the family's accepted capability statement.**
   The mediated runtime filters the implementation's reported capability ladder to
   the descriptor's declared set; the backhaul family's ladder reports the
   family's own four references. Declaring wireline-flavored references the
   family never reports would yield an empty mediated exposure (an dishonest
   composition); the wireline descriptors therefore import
   `REFERENCE_CAPABILITIES` from the accepted M007 reference composition module
   BY REFERENCE and declare them verbatim — the capability statement is the
   accepted family's own, exactly the by-reference discipline.
4. **The static-availability discipline is a typed check on the accepted grammar,
   not a grammar change.** The M020 envelope grammar has no mobility vocabulary to
   suppress; the wireline discipline (exactly ONE continuous declared window) is
   enforced by `require_static_availability` in the new declarations module — a
   pure function over the accepted types raising the accepted typed error — never
   by editing the accepted envelope surface. A future non-terrestrial family
   (M022) declares its pass windows on the SAME grammar with a different
   discipline; the grammars stay shared, the semantics stay per-family declared.
5. **The enterprise-WAN mount returns a four-tuple.** The accepted M007
   `mount_reference` pattern returns `(implementation, descriptor,
   binding_requirements)`; the enterprise-WAN composition additionally hands back
   the declared site-pair link map (the composition root's own wiring data —
   LOCK-105 declared data) so the battery can drive activations and the
   mid-session site reselection on specific declared circuits. The registration
   surface consumes the same three products as every family; the fourth element
   is disclosed composition-root wiring data, never registration state.
6. **The battery as composition root (the M019/M020 house pattern).** The mounts
   need the accepted reader facade over a real WORK-012 store; the battery wires
   the fixtures (the `adapter_selftest` public fixture helpers — the case_66
   cross-battery import precedent, the M020 battery's own pattern: their fixtures,
   never their assertions).
7. **The LOCK-110 opaque-reference scan excludes the requirements snapshots.** The
   activation/reconfiguration requirements legitimately carry the wiring
   `link_ref` — the M007 reference composition's own disclosed shape ("family-side
   wiring data the caller passes to the 1.1 activate/reconfigure operations" —
   LOCK-017 binding DATA). The isolation audit therefore scans every canonical
   record byte OUTSIDE the caller-supplied requirements snapshots and
   additionally asserts the snapshots carry exactly the caller-supplied keys —
   the provider-SDK HANDLES (bearer/link internals) provably stay behind the
   runtime, while the disclosed wiring data crosses as data.
8. **The no-tech-branching audit scans the modules' own vocabulary.** The
   imported accepted identifiers (the family bridge class
   `BackhaulTechnologyAdapter` among them) are the by-reference composition
   itself, not this delivery's branching — excluded from the token scan exactly
   as the accepted M007 audit scoped itself to the M007-owned files (the accepted
   audit never scanned the family subpackages' own identifiers either).

## 7. Out-of-scope discipline (nothing else changed)

The delta contains ONLY the four files above (`adapters/reference/wireline.py`,
`accesstech/wireline.py`, `tools/wireline_selftest.py`, `docs/M021-evidence.md`).
No control-plane surface (`spec/`, `.github/`, `AGENTS.md`, `README.md`), no
contract-core change, no accepted-domain modification (`contracts/`,
`adapters/capability.py`, `adapters/backhaul/`, the accepted
`adapters/reference/` modules, `accesstech/`'s accepted six files — all consumed
by reference only; the frozen `accesstech/__init__.py` and
`adapters/reference/__init__.py` are untouched). The parallel M023 worker's
in-flight surface (`adapters/reference/futureimt.py`,
`tools/futureimt_selftest.py`, `docs/M023-evidence.md`) is untouched and absent
at this head. The CI workflow is unchanged (the wireline step was wired by the
DEC-0121 acceptance commit as a pre-delivery existence guard; this delivery
activates it).

## 8. Evidence classes (honest disclosure)

Every verification in this record is SOFTWARE class — deterministic, offline,
reproducible battery evidence over the accepted code surfaces. No PHYSICAL PASS is
claimed: EVID-002..EVID-008 (the open physical obligations) remain open and
untouched by this delivery, exactly as the R9 charter's evidence policy requires.
The battery never converts software evidence into physical claims; the
evidence-doc honesty case (case_14) mechanically enforces the disclosure.

## 9. Delivery provenance

Delivered in ONE worker session on the append-only branch `m021-wireline` (no
rebase, no force-push, no amending), rooted at the DEC-0121 M020-acceptance head
`fe27c9962f5e5ad4da9b355bf3be1172825bf4fe` (verified `git rev-parse HEAD` equal
before any work), commit-as-you-go: the compositions + declarations first, then
the battery, then this evidence record (the final head is in the PR body). The
verification numbers in §3/§5 were produced at the final delivery head by direct
execution (battery x3 byte-identical; the full suite in exact CI order with
exit-code-based detection — the one disclosed case_68 exception root-caused in
§0; the five governance gates).

**Amendment provenance:** the case_68 resolution amendment (see §0 — TECH LEAD
RESOLUTION) is the ONE post-delivery commit on this branch, authored by the
Tech Lead (`z-ai-architect`), not the worker session; it touches only
`tools/adapter_selftest.py`'s declared set and this record (the §0 resolution
addendum + this note). The delivery commit itself is untouched (append-only;
no rebase, no force-push, no amending — the amendment rides ON TOP, exactly as
the M019 branch's resolution amendment rode on top of its delivery).
