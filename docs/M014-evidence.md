# M014 — Production Federation — Evidence Record

**Work Item:** M014 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7
program authorization; M014 is the charter's current child — the LAST chain
child: after its acceptance the R7 gate completion review closes the program)
**Baseline:** `8516d5003ef0539e0ab89e6e1d752297e4249685` (the DEC-0108-accepted
M008 state — the live main head; the current-child pointer advances
M008 → M014; the acceptance is gated on the six accepted prerequisites
M008+M009+M010+M011+M012+M013, all consumed here by reference only)

This record persists the verified facts of the M014 delivery. Every claim
below is reproducible offline from the delivery head; no worker report is
trusted without direct verification (the standing Tech Lead rule). All
evidence in this record is **SOFTWARE class** — simulation/deterministic-
battery evidence only; no PHYSICAL PASS is claimed or implied, and
EVID-002..EVID-008 remain open and untouched.

## 1. Delivered surface — the five-package harden map

The M014 charter scope is `federation/`, `scale/`, `upgrade/`, `identity/`,
`client/` (harvest + harden; `tools/client_selftest.py` re-baseline per the
DEC-0099 disclosure), `tools/scale_selftest.py`, `docs/M014-evidence.md`.
Every harvest seam is a **NEW `convergence.py` module inside the package**;
the frozen package cores are preserved byte-identical (the delta touches no
frozen file — verified by `git diff --name-only origin/main HEAD`, exactly
eight paths: the five NEW convergence modules, the two batteries, and this
record).

- **`federation/convergence.py` (NEW, 2027 lines)** — the convergence
  child's provider-domain surface: the WORK-015 federation package
  harvested onto the Architecture 1.1 authority and production-hardened.
  The frozen citation vocabulary (`CONVERGENCE_AUTHORITIES` = contracts,
  offers, executionplans, adapters, replan, commercial, evidence,
  assurance, vertical-proof; `VERTICAL_PROOF_KINDS` = sharenet/roamlink/
  comos) with the per-authority frozen citation kinds; the `cite_*`
  constructors (`cite_contract`/`cite_offer`/`cite_execution_plan`/
  `cite_adapter_capability`/`cite_replan_decision`/
  `cite_settlement_reference`/`cite_evidence_record`/
  `cite_assurance_evaluation`/`cite_vertical_proof`) each digesting the
  cited record's OWN canonical bytes; `ChildCitation` (typed DATA,
  canonical round-trips, tamper-evident ids); the ONE sanctioned
  peer-evidence lift `peer_evidence_from_citation` into the REAL M005
  `AttestationEvidence` space; `DomainCitationLedger` (append-only,
  idempotent, byte-stable digests) with the `CitationRevocation`
  `pending → propagated → confirmed` forward-only propagation discipline;
  the LOCK-117 production-hardening surfaces `RateLimitPolicy` /
  `RateLimitState` / `check_rate_limit` (a deterministic fixed-window
  admission counter over INJECTED instants; exceed fails closed typed
  `rate-limited`); and `ConvergedAuthorizationRuntime` — the converged
  authorization runtime implementing the frozen W049 duck-typed canonical
  authorization protocol (prepare/grant/authorize/activate/pause/resume/
  close/withdraw/emergency-stop/notify-path-lost/account-traffic/session/
  consent) over a REAL contract store (the lease gate — LOCK-101), a REAL
  typed evidence store (the consent record), the rate-limit surface and
  the declared `AuthorizationScope` quota.
- **`identity/convergence.py` (NEW, 896 lines)** — the identity package's
  M014 harvest (the migration matrix: "Identity / Trust: RETAIN +
  REFACTOR → ADCOS identity/authority"): `PrincipalAuthorization` binds a
  canonical ADCOS NodeID to a REAL M002 contract principal (the
  `contracts.Principal` vocabulary cited by reference; the contract
  citation digests the real contract's OWN canonical bytes —
  LOCK-101/118); the typed `check_principal_authorization` gate
  (authorized / node-mismatch / contract-mismatch / not-yet-valid /
  expired / revoked — possessing a valid identity is NOT trust and NOT
  authorization, LOCK-022); `AuthorizationRevocation` + the append-only
  idempotent `AuthorizationRegistry` (history preserved, sorted
  iteration, byte-stable digest round-trips); `authorization_attestation`
  — the closed-loop lift of one principal authorization into the REAL
  M005 typed evidence space (an immutable `controller-verified`
  `AttestationEvidence`); and the deterministic credential-rotation
  discipline `CredentialLifecyclePolicy` / `CredentialLifecycleState` /
  `evaluate_credential_lifecycle` / `enforce_active_credential_bound`
  (ok / rotation-due / rotation-overdue / expired / revoked /
  not-active / too-many-active) composing the WORK-004 lifecycle
  vocabulary by reference.
- **`upgrade/convergence.py` (NEW, 432 lines)** — the converged-domain
  compatibility surface (the migration matrix: the
  compatibility-orchestration family stays a COMPATIBILITY layer, never
  an authority): `CONVERGED_DOMAIN_SET` — the frozen Architecture 1.1
  domain labels (the 12 accepted child authorities + the five M014
  production-federation domains, carried as DATA only);
  `DomainVersion` (MAJOR.MINOR, the frozen additive-evolution grammar);
  `classify_domain_compatibility` — the deterministic mixed-version
  coexistence verdicts (`compatible` / `additive-gap` — disclosed, never
  silent / `major-mismatch` — NO fallback to a lower common major, no
  clamping, the family's frozen fail-closed discipline / `unknown-domain`
  fails closed); `capability_compatibility` — the capability-id
  consultation through the REAL accepted capability registry (the
  M003-harvested `capabilities.classify_capability_id` authority —
  KNOWN / UNKNOWN_BUT_WELL_FORMED / INVALID, never re-declared here);
  `negotiate_converged_compatibility` — the full deterministic report
  over two peers' converged-domain version sets (sorted domain
  iteration, byte-stable digest, input-order independence,
  `local-missing`/`peer-missing` fail closed — a peer missing a frozen
  domain is never silently skipped).
- **`scale/convergence.py` (NEW, 692 lines)** — the multi-domain
  convergence harness (the charter's disclosed scale-battery evolution
  target): `ConvergenceScenarioSpec` / `run_convergence_scenario` /
  `verify_convergence_replay` / `convergence_summary` — planned
  child-authority citation waves (`ConvergenceCitationPlan`, typed
  `ChildCitation` DATA) appended to per-domain `DomainCitationLedger`s
  over a REAL federation world (one REAL `FederationStore` per domain —
  the frozen W039 discipline, never a centralized second authority);
  every per-domain citation admission passes the deterministic
  fixed-window `RateLimitPolicy` gate (per-tick admission bound;
  violations fail closed at validation time — the plan is deterministic,
  so a violation is a spec error, never a runtime surprise); a citation
  revoked at an origin domain propagates to every peer in EXPLICIT relay
  rounds bounded by the computed graph distance (each round advances the
  revocation one hop; the round count PREDICTED from the topology and
  observed == predicted, fail-closed on divergence); the journal is
  honest evidence only (OBSERVATION events inside the frozen W039
  taxonomy, reused verbatim, never extended; `scale.evidence` stays the
  authority; no deployment claim).
- **`client/convergence.py` (NEW, 944 lines)** — the DEC-0099-disclosed
  re-baseline composition: the frozen WORK-049 client (`ProviderClient`,
  `ClientRuntime`, the gateway read model, the privacy-bounded
  presentation) imported BY REFERENCE, UNCHANGED, and driven over the
  CONVERGED Architecture 1.1 authorities: `ConvergedSharingRuntime` —
  the frozen W049 sharing-protocol facade delegating 1:1 to the
  converged authorization runtime (never reimplemented, never
  weakened); `ConvergedConsentScope` — the frozen consent-presentation
  dimensions projected from the declared `AuthorizationScope` DATA;
  `ConvergedSessionView` — the W049 duck-typed session view
  (`lease_ref` = the CONTRACT id, the canonical commercial record);
  `ConvergedClientGateway` — the canonical read window (the
  sharing/consent reads through the authority, the lease read as the
  M002 contract read with the M003 offer terms resolved by reference,
  and the NOT-wired authorities refusing typed fail-closed — the frozen
  ComposedGateway discipline, never fabricated);
  `build_converged_provider_client` — the composition root (REAL
  authorities only, injected deterministic clock, typed fail-closed
  wiring); `converged_client_citations` — the by-reference citation set
  of one converged world. NOT a W048 restoration (see §3).
- **`tools/client_selftest.py` (RE-BASELINED — the DEC-0099 disclosure
  honored)** — the honest convergence baseline: **24/24 PASS** (§5).
- **`tools/scale_selftest.py` (EVOLVED — disclosed)** — 39 preserved
  W039 cases + 6 new convergence cases = **45/45 PASS** (§4).
- **`docs/M014-evidence.md`** — this record.

The frozen package cores re-run green at their accepted counts on the
M014 delivery head: federation 52/52, identity 19/19, upgrade 41/41
(their batteries are untouched by this delta); scale's frozen 39 cases
are preserved verbatim inside the evolved 45/45 battery; the client core
(14 modules, everything in `client/` except the NEW `convergence.py`) is
byte-identical to origin/main — audited inside the client battery
(case_20).

## 2. The convergence citations (by reference — never reimplemented)

The M008/M009 precedents govern: an accepted child authority is consumed
through its frozen public surface only; no child domain is weakened,
reinterpreted or reimplemented anywhere in this delivery.

- **`federation/convergence.py` cites:** `contracts/` (M002, DEC-0102) —
  every converged authorization binds to a REAL `ConnectivityContract`
  and its own lease lifecycle (`GrantLease`/`RevokeLease`/
  `ExpireLease` through the store's public command surface; the lease
  gate, the expiry projection and the revocation path ARE the contract's
  own semantics — LOCK-101/117); `offers/` (M003, DEC-0103) — provider
  offers cited as typed DATA (the offer's own canonical bytes and
  identity; no second offer model); `executionplans/` + `adapters/`
  (M006/M007, DEC-0106/0107) — plans and adapter capability views cited
  as opaque references with their own digests (LOCK-109/110; this module
  never translates a plan or calls an adapter); `replan/` (M008,
  DEC-0108) — replan decisions cited as DATA with their own decision
  identity (a failover citation is provenance, never a re-decision);
  `usage/commercial/allocation/payment` (M009, DEC-0109) — settlement
  references ride as opaque typed citations (LOCK-113; no commercial
  semantics migrate); `evidence/` + `assurance/` (M005, DEC-0105) —
  peer-domain citations lift into the REAL typed evidence record space
  through the ONE sanctioned seam (`peer_evidence_from_citation`);
  `sharenet/roamlink/comos` (M010/M011/M012, DEC-0110/0111/0112) —
  vertical proofs cited as DATA patterns (LOCK-120; no vertical
  semantics owned here).
- **`identity/convergence.py` cites:** `contracts/` (M002) — the
  `Principal` vocabulary by reference and the real contract's own
  canonical bytes in every binding; `evidence/` (M005) — the
  `controller-verified` attestation lift; the frozen WORK-004 identity
  core (`.lifecycle` `LifecycleState`, `.node_id`
  `NodeIdError`/`parse_node_id`) — the identity authority stays THE
  authority, consumed by reference, never duplicated.
- **`upgrade/convergence.py` cites:** `capabilities` (the M003-harvested
  accepted capability registry — `classify_capability_id` is the one
  capability-id authority, consulted, never re-declared); the frozen
  upgrade family's own surfaces (`upgrade.errors`, and the
  protocol-profile negotiation / staged-upgrade ladder stay
  `upgrade.compatibility`/`upgrade.model`'s own business — this module
  delegates, never duplicates); `protocol.canonicalization` for the
  byte-stable digests.
- **`scale/convergence.py` cites:** `federation.convergence` (the M014
  surface — `ChildCitation`, `DomainCitationLedger`, `RateLimitPolicy`,
  `CitationRevocation`); `federation` (the frozen `Scope`); the frozen
  W039 scale core (`.errors`, `.model`, `.topology`, `.world` — one REAL
  `FederationStore` per domain, the bounded-resource envelopes, the
  replay discipline); `simulator.time` (the injected W031
  `ScenarioClock`).
- **`client/convergence.py` cites:** `contracts/` (M002) — the lease
  read IS the CONTRACT read; the authorization lease gate is the
  contract's own lease lifecycle; the emergency stop drives the store's
  OWN `RevokeLease` command (LOCK-101); `offers/` (M003) — the consent
  presentation's `expected_economic_result` projected from the REAL
  offer records resolved through the REAL `OfferExchange`
  (`resolve_offer_reference` — P1-2: no caller-supplied economics,
  ever); `evidence/` (M005) — the consent record as REAL immutable
  `AttestationEvidence` (pending → granted → withdrawn, LOCK-106/118);
  `federation.convergence` (M014) — the converged authorization
  authority (this module owns NO authorization semantics — it delegates
  1:1); the frozen W049 core (`.adapters`, `.errors`, `.gateway`,
  `.model`, `.provider`, `.runtime`) imported by reference, unchanged.

## 3. The client battery DEC-0099 re-baseline (the honest convergence
baseline)

The W049-era `tools/client_selftest.py` verified the client runtime
against the W048 containment/sharing machinery
(`containment.CapabilityMatrix` + `sharing.*`), whose subject material is
WORK-048 — **accepted-not-restored** under the Architecture 1.1 migration
policy (the charter's migration policy: "W048 stays accepted-not-restored
(its surfaces are forbidden dependencies)"). It crashed on import at the
M009-era baseline and has been carried since as the sole documented CI
skip — the DEC-0099 disclosure, honored visibly, never silently.

This delivery replaces it with the promised honest convergence baseline:
24 deterministic cases driving the frozen WORK-049 client —
`ProviderClient` / `ClientRuntime` / the gateway read window / the
privacy-bounded presentation — imported BY REFERENCE, UNCHANGED
(byte-identical to origin/main, 14 modules, audited in case_20), over the
converged Architecture 1.1 authorities through `client/convergence.py`.

**W048's forbidden surfaces stay forbidden — never restored.** The
re-baseline is NOT a containment restoration: there is no isolation
primitive, no traffic-isolation authority and no buyer-traffic
enforcement anywhere in the composition; the converged admission gate is
the canonical contract lease + the granted consent attestation + the
declared authorization quota (an authorization quota, NOT a containment
proof); the buyer-side purchase chain stays with its own frozen seams.
Verified structurally in the battery (case_17): no `sharing` import
anywhere in `client/`; `containment` limited to the ONE frozen ACR-012
vocabulary seam in the frozen `client/capability.py`
(`containment.state` — pre-existing at the baseline, byte-identical);
the NEW composition imports no containment/sharing at all;
`containment.CapabilityMatrix` stays absent (the CI guard's own probe
cannot silently re-enable it); no isolation primitive is defined in any
convergence module; the facade exposes exactly the frozen protocol
members.

Following the M009 payment+eligibility multi-domain battery precedent
(the DEC-0109 re-baselines), the battery additionally carries the
behavioral verification of the OTHER M014 convergence surfaces: case_23
(the identity harden map) and case_24 (the upgrade harden map) — see
§5.

## 4. The scale battery evolution (39 preserved + 6 convergence = 45/45)

The charter's M014 scope names the disclosed evolution
("`tools/scale_selftest.py` — evolve the scale battery to the converged
state"). Every one of the 39 accepted W039 cases is PRESERVED verbatim
(cases 01–39: the frozen vocabularies, journal/observation records, the
run-result shape, topology construction/shapes, world construction and
store isolation, the horizontal-scaling ladder, the bounded-resource
envelope, spec-validation negatives, scenario determinism, hashseed
invariance, insertion-order independence, replay verification, export
waves, partition isolation, local-first survival, foreign-declaration
fail-closed, poison containment, revocation convergence, unreached
honesty, post-recovery convergence, no-second-authority, import
discipline, core purity, no wall clock, no randomness, secret hygiene,
naming-token freedom, the integration scenario and replay, the evidence
model, py_compile, the frozen API, the frozen spec, the PR-delta shape,
the CI wiring, relay sabotage). Six NEW cases append for
`scale/convergence.py`:

| Case | Verification | Result |
|---|---|---|
| case_40 | the converged citation scenario: a REAL 6-domain ring federation world, six planned child-authority citation admissions onto per-domain ledgers, one revocation propagated to every holder in EXPLICIT relay rounds; round count PREDICTED from the topology and observed == predicted; byte-identical replay | PASS |
| case_41 | the convergence spec fails closed at validation time: out-of-world domains, revocations without an origin admission, plans beyond the horizon, negative seeds, zero tick seconds, zero rate limits, untyped citation plans — seven spec-invalid rejections (never runtime surprises) | PASS |
| case_42 | determinism and input-order independence: the spec digest ignores plan input order; two runs byte-identical; reversed-order specs produce identical run digests; the propagation vocabulary frozen (pending/propagated/confirmed) | PASS |
| case_43 | the honest-evidence journal: every event kind inside the FROZEN W039 taxonomy (reused verbatim, never extended); strictly increasing sequences; admissions, relay rounds and the convergence verdict journaled explicitly; the completion counts honest | PASS |
| case_44 | topology-predicted round counts across shapes: ring=2, hub-spoke/full-mesh/cliques=1 — always the graph distance to the farthest holder domain, observed == predicted on every shape | PASS |
| case_45 | the per-domain per-tick admission rate envelope: the default limit 8, an exactly-8 burst admitted, the 9th admission and tighter-policy violations rejected spec-invalid at validation time | PASS |

**Battery result: PASS (45/45 cases), run 3× consecutively, byte-identical
(the only variance the documented wall-clock elapsed text in case_10,
compared with timing normalized).**

## 5. Deterministic verification matrix (the client battery, 24/24)

All runs offline; instants injected (T0-style constants); no wall clock,
no randomness, no UUIDs, no network; no real sockets; no secrets stored
(LOCK-119); PYTHONHASHSEED-safe (verified across processes and seeds
0/1/42/unset). Exit-code-based verification (a traceback or lowercase
"failed" IS a failure). Every item below is SOFTWARE-class evidence.

| Verification | Result | Evidence |
|---|---|---|
| The frozen converged vocabularies (citation authorities/kinds, session states/transitions/terminals, consent states, rate-limit operations, the client-convergence reason codes) | PASS | case_01 |
| The full frozen provider lifecycle over the composition root (capability gate → READY → prepare → consent facts → granted → authorized → ACTIVE ↔ PAUSED → path-loss degraded observed → authority-side recovery → client re-projection) | PASS | case_02 |
| P1-2 consent economics: the expected economic result is the canonical serialization of the REAL resolved M003 offer record; the INTENT contract carries the honest empty binding; unresolvable economics REFUSE the presentation | PASS | case_03 |
| The consent-attestation closed loop: pending → granted → withdrawn as REAL immutable controller-verified `AttestationEvidence` records bound to the contract; the typed consent state machine | PASS | case_04 |
| The canonical lease gate: the M002 contract's own lease lifecycle (five typed denials, the canonical reason preserved verbatim) | PASS | case_05 |
| The declared authorization quota at the traffic admission point (exceed / exact boundary / paused / unknown) | PASS | case_06 |
| The LOCK-117 fixed-window rate gate (typed burst denial, window reset on injected ticks, pure verdicts, state round-trip) | PASS | case_07 |
| The emergency stop: the local fail-safe detach FIRST, the store's OWN `RevokeLease` (LOCK-101), the withdrawn consent, the verified terminal read, STOPPED → CLOSED | PASS | case_08 |
| Authority-side revocation OBSERVED through the read window (terminal projection; no resurrection) | PASS | case_09 |
| Consent withdrawal (canonical revoked + the withdrawn attestation — no soft revoke) | PASS | case_10 |
| Lease expiry observed through the store's own `expire_leases_if_due` surface (never a local timer) | PASS | case_11 |
| The W049 duck-typed views (`lease_ref` = the CONTRACT id; the scope projection round-trip; sorted sessions) | PASS | case_12 |
| The converged gateway read window (bound + clocked sharing/commercial reads; the unwired networkpath/usage seams refusing typed; offline fail-closed; reconnect reconciles) | PASS | case_13 |
| The by-reference citation set of one world (the contract, its resolved offers, the typed evidence records — each digesting the cited record's OWN canonical bytes; tamper evidence) | PASS | case_14 |
| The wider child-authority citation surface (a REAL M006 execution plan translated from the same contract, a REAL M007 `CapabilityView`, the commercial/vertical-proof seams, duck-typed non-records failing closed, the ONE sanctioned peer-evidence lift into the REAL M005 space) | PASS | case_15 |
| The per-domain citation ledger (idempotent appends, forged same-id content rejected, `pending → propagated → confirmed` forward-only, history-preserving revocation, byte-stable digests and round-trips) | PASS | case_16 |
| WORK-048 stays accepted-not-restored (the structural audit — §3) | PASS | case_17 |
| LOCK-119 discipline (no wall clock/randomness/UUID/network in the five convergence modules; secret-shaped material rejected typed) | PASS | case_18 |
| Determinism (byte-identical fresh worlds + PYTHONHASHSEED 0/1/42/unset subprocesses) | PASS | case_19 |
| The frozen W049 core is byte-identical to origin/main (14 modules; the client delta is exactly `convergence.py`); the composition imports exactly the sanctioned set | PASS | case_20 |
| The PR-delta authorization coverage (every delta path covered by the ACTIVE R7-CORE-001 record; no `spec/` or `.github/` touch; no untracked files) | PASS | case_21 |
| The evidence-class honesty contract (this record's markers: SOFTWARE class, EVID-002..008 open, the W048/DEC-0099 disclosures) | PASS | case_22 |
| The identity harden map: contract-cited principal authorizations, the typed gate, the append-only revocation registry, the M005 lift, and the rotation ladder ok/due/overdue/revoked/not-active/too-many-active | PASS | case_23 |
| The upgrade harden map: 13 frozen domain labels, compatible/additive-gap/major-mismatch (NO fallback), the REAL capability registry consulted, byte-stable input-order-independent negotiation, missing domains fail closed | PASS | case_24 |

**Battery result: PASS (24/24 cases), run 3× consecutively, byte-identical.**

## 6. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the contract stays the sole
  commercial authority everywhere — the converged authorization sessions
  gate on the CONTRACT's own lease states; the client's lease read IS
  the contract read; the emergency stop drives the store's OWN
  `RevokeLease` command; the identity principal bindings cite the real
  contract's OWN canonical bytes; no second contract model exists in any
  convergence module.
- **LOCK-022 (identity ≠ authorization):** a valid NodeID is never
  authorization by itself — the principal authorization is an explicit,
  windowed, revocable record with a typed fail-closed gate.
- **LOCK-105/LOCK-109/LOCK-110:** plans and adapter capability views are
  cited as opaque references with their own digests; no plan is
  translated and no adapter is called by any convergence surface.
- **LOCK-106/LOCK-118 (typed evidence/provenance):** every citation
  digests the cited record's OWN canonical bytes; the consent stream and
  the authorization attestations are REAL immutable typed
  `AttestationEvidence` records inside REAL `EvidenceStore`s; the
  peer-evidence lift is the ONE sanctioned seam; records are
  tamper-evident and canonical-round-trip stable.
- **LOCK-111 (determinism):** every surface is a pure function of
  injected inputs — content-derived ids over canonical JSON, sorted
  iteration, integer arithmetic, byte-stable digests independent of
  input order; verified twice in-process and across PYTHONHASHSEED
  subprocesses.
- **LOCK-113 (commercial isolation):** settlement references ride as
  opaque typed citations; no commercial semantics migrate into the
  federation/identity/upgrade/scale/client packages.
- **LOCK-115/LOCK-116:** simple and complex failover shapes are cited
  as DATA (replan decisions with their own identity — a failover
  citation is provenance, never a re-decision).
- **LOCK-117 (authority uniqueness):** the client stays a CLIENT —
  every authority object is injected and reached through its public
  contract; the converged admission gate is the canonical lease + the
  consent attestation + the declared quota (an authorization quota,
  NOT a containment proof); no second authority is created on either
  side of any seam.
- **LOCK-119 (secrets/determinism):** no wall clock, no randomness, no
  UUIDs, no network anywhere in the five convergence modules
  (AST-audited); secret-shaped material is rejected typed at every
  construction boundary.
- **LOCK-120 (vertical proofs as DATA):** the sharenet/roamlink/comos
  vertical proofs are cited as DATA patterns; no vertical semantics are
  owned by any convergence surface.

## 7. Judgment calls (disclosed)

1. **The harvest seams are NEW `convergence.py` modules inside the five
   packages** (the M005 telemetry / M006 composition-harvest / M008
   `execution_state` precedents: the seam lives in the new surface). An
   in-place refactor of the frozen cores is structurally impossible
   without breaking the frozen WORK-015/WORK-004/WORK-029/WORK-039/
   WORK-049 contracts: the packages' own batteries pin their behavior,
   dozens of sibling batteries import their public APIs directly, and
   the charter's scope discipline says to preserve the public API
   surface. The harvest is therefore one-way (the frozen cores import
   no convergence code) and disclosed at both ends; the frozen cores
   are byte-identical to origin/main (the client core audited inside
   the battery, case_20; the whole delta touches no frozen file).
2. **The DEC-0099 re-baseline is a REPLACEMENT battery, not a
   restoration.** The W048-era skip is retired by replacing the
   crashed W048-dependent battery with the honest convergence baseline
   over the converged 1.1 authorities — never by restoring the
   forbidden containment/sharing surfaces (case_17 audits the
   prohibition structurally, including that the CI guard's own probe
   cannot silently re-enable).
3. **The CI workflow step for the client battery still carries the
   DEC-0099 containment guard** (`if python3 -c "from containment
   import CapabilityMatrix" … else SKIP`), a `.github/` control-plane
   surface OUTSIDE this implementation PR's boundary (the charter's
   out-of-scope rule; the battery's own case_21 rejects any `.github/`
   touch). The guard therefore still echoes its disclosed SKIP in CI;
   retiring it is the acceptance-commit wiring (the DEC-0109 precedent:
   the payment/eligibility guards were retired by the acceptance
   commit, not by the worker's implementation PR). Both facts are
   verified and disclosed here: the STEP skips visibly (rc=0, the
   disclosed DEC-0099 message), and the BATTERY itself is green rc=0
   24/24 when run directly (three consecutive byte-identical runs).
4. **The upgrade convergence's frozen domain set includes the five M014
   domains themselves** (federation, identity, scale, upgrade, client
   alongside the twelve accepted child authorities — 13 labels).
   Self-inclusion is deliberate and disclosed: the converged
   compatibility report must cover EVERY Architecture 1.1 domain a peer
   may speak, including the production-federation domains this delivery
   adds; the labels are compatibility DATA only (each domain's
   semantics stay its own authority's business).
5. **The scale battery's evolution is disclosed, not silent** (§4): 39
   accepted W039 cases preserved verbatim + 6 new convergence cases.
   The frozen W039 discipline (one REAL `FederationStore` per domain,
   never a centralized second authority; the injected W031
   `ScenarioClock`; bounded-resource envelopes; byte-identical replay)
   is preserved and extended onto the citation surface, never
   circumvented.
6. **The rate-limit verdicts are admission-control decisions, never
   enforcement claims.** A `rate-limited` denial fails closed typed at
   the admission point; the surfaces make no QoS or policing claim
   (that would be physical-world evidence — out of scope, §8).

## 8. Out-of-scope discipline (nothing else changed)

The M014 delta contains only: `federation/convergence.py`,
`identity/convergence.py`, `upgrade/convergence.py`,
`scale/convergence.py`, `client/convergence.py` (all NEW),
`tools/client_selftest.py` (the DEC-0099 re-baseline),
`tools/scale_selftest.py` (the disclosed evolution), and
`docs/M014-evidence.md` (this record). No control-plane surface, no
`spec/` file, no `.github/` file, no protocol schema, and no frozen-core
modification in any of the five packages (all consumed by reference
only — verified in the batteries' frozen-core, one-way-harvest and
PR-delta cases). The drift guard classifies the delta
implementation-only; the provenance gate verifies full coverage by
R7-CORE-001 (all eight delta paths are declared M014 scope entries in
the active authorization).

## 9. Evidence classes (honest disclosure)

- All M014 acceptance criteria: **SOFTWARE class** (deterministic offline
  batteries — client 24/24 and scale 45/45 on the delivery head, run 3×
  byte-identical; every blocking battery and governance gate in the CI
  suite green on the delivery head — the one non-green step, the legacy
  `spec_check.py` compatibility audit, is `continue-on-error: true` in
  the CI workflow: it fails (rc=1) on the pre-delivery baseline as
  well, and its ARCH-08 verdict cannot see the R7 program authorization
  by frozen construction (the workflow's own comment; the active-era
  successor gate `authorization_provenance.py` PASSES and verifies the
  delta's R7-CORE-001 coverage)).
- No pending child is claimed delivered: M014 is the last chain child,
  and all six prerequisites are already accepted (M008 DEC-0108, M009
  DEC-0109, M010 DEC-0110, M011 DEC-0111, M012 DEC-0112, M013 DEC-0113,
  plus the earlier chain M002–M007) — consumed only by reference.
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M014 creates and
  closes none; EVID-002..EVID-008 remain open and untouched, and no
  evidence produced by this delivery is physical, production, or
  live-service evidence. No SOFTWARE evidence is converted into a
  physical-world pass claim of any kind.

## 10. Delivery provenance

- Branch: `m014-federation` from the baseline `8516d50` (the
  DEC-0108-accepted M008 state); append-only delivery history (the
  five convergence-surface commits, the two battery commits, and this
  evidence-record commit).
- Batteries on the delivery head: `python3 tools/client_selftest.py` →
  PASS (24/24) ×3 byte-identical; `python3 tools/scale_selftest.py` →
  PASS (45/45) ×3 byte-identical (the case_10 wall-clock text
  normalized).
- Full suite: every battery the CI workflow runs, in exact workflow
  order, on the delivery head with exit-code-based detection — see the
  PR body for the numbered results.
- Governance gates on the delivery head: `authorization_provenance.py`
  PASS, `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only
  classification), `fresh_session_check.py --actual-main-sha
  <origin/main>` PASS (origin/main = `8516d50`, the DEC-0108 governance
  head beyond the ce65c88 pin — accepted per the standing reconciliation
  convention).
- Frozen sibling batteries at this head (re-run green at their accepted
  counts in the full suite): federation 52/52, identity 19/19, upgrade
  41/41 — plus the accepted counts recorded for every other battery in
  the PR verification comment (contract, offer, assurance,
  executionplan, adapter, replan, payment, eligibility, session,
  mobility, multipath, sharenet, roamlink, comos, and the rest of the
  frozen suite).
