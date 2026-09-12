# M018 — Credential and Key Lifecycle Operations — Evidence Record

**Work Item:** M018 · **Authorization:** R8-CORE-001 (DEC-0114, the bounded R8 program
authorization; M018 is the R8 charter's chain-independent fourth child)
**Baseline:** `28b31500a928f2f75582bfb79039e315187d72b2` (the DEC-0109 R7-completion head,
per the authorization record; the branch rides the DEC-0116 M016-acceptance head
`bda91c39fb80c89dc3df1eaf1864f6560558a16b` — the current main, the accepted R7 state
including the M014 identity/federation/client convergence surfaces that are this
delivery's composition substrate, plus the accepted M015 `resilience/` and M016
`localfirst/` domains)

**Chain independence (the M013 precedent class, the R8 overlay rule):** this branch
composes ONLY the accepted R7/M014 surfaces (`identity/`, `federation/`, `client/`
and, through them, `contracts/`, `evidence/`, `offers/`) — the M015-M017 chain
siblings (`resilience/`, `localfirst/`, `recovery/`) are neither imported nor touched,
so the branch merges in any order relative to the chain (verified in the battery's
one-way-import case: no chain sibling is imported).

This record persists the verified facts of the M018 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule). All evidence in this record is **SOFTWARE
class** — deterministic-battery evidence only; no PHYSICAL PASS is claimed or implied,
and EVID-002..EVID-008 remain open and untouched.

## 1. Delivered surface

- **`credentials/` (NEW)** — the operational credential-lifecycle domain of the R8
  charter M018 scope, composing the accepted M014 identity/federation/client
  convergence surfaces BY REFERENCE (import and compose; never reimplemented,
  weakened, forked, or bypassed):
  - `credentials/errors.py` — the frozen `credential-*` typed reason vocabulary
    (11 fail-closed codes; the zero-coverage-gap kernel's
    `credential-rotation-nonatomic`; the declared-bound
    `credential-propagation-unconverged`; the fail-closed inventory
    `credential-inventory-incomplete`; consumed-domain errors — `IdentityError`,
    `IdentityConvergenceError`, `ConvergenceError`, `ClientError`, `EvidenceError`
    — wrapped at every boundary with their deterministic text preserved; exception
    isolation throughout).
  - `credentials/model.py` — the typed records: `LifecycleOperationRecord` (the
    journaled operation with the before/after ADMITTED SETS fully recorded, the
    position-independent content identity as the idempotency key, and the
    kind-conditional member discipline — only a rotation carries a replacement,
    only the DISTINCT emergency kind carries the frozen three steps),
    `EmergencyStep` (the evidence-visible emergency step), `PropagationPlan`
    (the declared round-count convergence bound), `AdmissionProbe` (the composed
    admission verdict with the three CONSUMED verdicts recorded verbatim — the
    composed verdict is mechanical, never caller-supplied), `InventoryTrace` /
    `InventoryAuditRecord` (the fail-closed audit evidence), `LifecycleFold` (the
    replay result with the admitted-set timeline); the frozen vocabularies
    (operation kinds, emergency step kinds, the 7 inventory break kinds, the
    admitting verdict subsets imported from the consumed M014 vocabularies with
    import-time drift guards); and the pure kernels (`derive_operation_id`,
    `check_rotation_flip_is_atomic`, `check_removal_is_atomic`,
    `check_zero_coverage_gap`, `admitted_set_from_records`, `round_deliveries`,
    `consumer_observed_revocation`, `plan_propagation`).
  - `credentials/journal.py` — the deterministic lifecycle operation journal
    (ordered, gapless, IDEMPOTENT, replayable, tamper-evident; construction-is-
    recovery; the append is atomic — a rejected append leaves the journal
    byte-identical).  The fold is the sole writer of the replayed view and
    MECHANICALLY enforces the zero-coverage-gap invariants at replay: gapless
    positions, unique identities, CONTINUITY (every record's before-set equals
    its predecessor's after-set — an unrecorded admitted-set transition is
    journal divergence, so there is NO operation window the journal does not
    account for), and the per-kind atomicity kernels.
  - `credentials/rotation.py` — the rotation drills: `run_rotation_drill` (the
    accepted `IdentityService.rotate` — the authority's own all-or-nothing
    `StoreBatch` — driven by reference; the before/after sets read from the
    identity authority's own public records; the authority outcome MECHANICALLY
    verified as an exact single flip BEFORE journaling; the M014 bookkeeping
    maintained) and `run_revocation_drill` (the ordinary non-emergency
    revocation through the accepted `IdentityService.revoke` — the distinct
    emergency path structurally cannot ride this kind).
  - `credentials/propagation.py` — the revocation propagation as deterministic
    rounds: `run_revocation_propagation` (the declared fanout over the declared
    consumer order — a pure function of the plan; every round journaled; the
    DECLARED ROUND-COUNT bound enforced — an unconvergeable plan fails closed
    citing the bound and the pending consumers, its bounded rounds staying
    journaled as the evidence of the bounded failure) and `propagation_verdict`.
  - `credentials/emergency.py` — the emergency revocation path: the DISTINCT
    TYPED JOURNALED operation (`emergency-revocation`, exactly the three frozen
    steps in order — the ordinary `revocation` kind structurally cannot carry
    them): the identity revocation through the accepted `IdentityService.revoke`
    + the controller-verified LOCK-106 attestation, the M014 authorization
    revocation through the accepted `AuthorizationRegistry.revoke` + the M014
    closed-loop attestation lift, and the accepted emergency stop driven through
    the frozen W049 client's OWN `emergency_stop` control (the frozen sequence:
    the local fail-safe, the canonical lease revoked through the contract
    store's OWN `RevokeLease` command, the consent withdrawn with a typed
    attestation append, the verified terminal state).  `verify_emergency_evidence`
    fails closed unless every step's LOCK-106 references resolve in the REAL
    evidence store.
  - `credentials/inventory.py` — the credential inventory verification:
    `run_inventory_audit` (the fail-closed audit over the journal's folded
    admitted set, the identity authority's own records and the accepted M014
    bookkeeping — an admitted credential without a complete lifecycle record
    chain is the TYPED `credential-inventory-incomplete` failure citing the
    break kind, never a warning) and `journal_inventory_audit` (the clean audit
    journaled as read-only evidence).
  - `credentials/gate.py` — the admission gate consumed BY REFERENCE from the
    accepted `client/`/`federation/` surfaces (LOCK-117: no second
    authorization runtime): `admission_gate_world` (the ACCEPTED
    `client.convergence.build_converged_provider_client` composition root
    driven 1:1 over the injected REAL authorities),
    `probe_credential_admission` (the composed probe: the M014
    credential-lifecycle verdict, the M014 principal-authorization registry
    verdict, and the converged traffic-admission point
    `ConvergedAuthorizationRuntime.account_traffic` driven with a ZERO-byte
    probe — every canonical gate evaluated, no state advanced), and
    `check_credential_admission` (the raising twin).  A non-accepted gate
    object is rejected (isinstance-guarded against the REAL federation
    runtime).
  - `credentials/__init__.py` — the public surface (42 names).
- **`tools/credential_selftest.py` (NEW)** — the M018 battery: 32 deterministic,
  offline, seeded cases covering the charter's (a)-(f) matrix (§2).
- **`docs/M018-evidence.md`** — this record.

## 2. Verification matrix (the battery, SOFTWARE class per case)

`python3 tools/credential_selftest.py` — all 32 cases green, run 3× consecutively
on the delivery head (byte-identical output; exit-code-based verification).

| Charter criterion | Battery verification | Class | Case(s) |
|---|---|---|---|
| (a) rotation drills — zero coverage gaps; the admitted-set transition atomic and journaled | The journal round-trips: the gapless kind chain (rotation → revocation → 2 rounds → audit), the IDEMPOTENT append (the identical record replays as a no-op), the ATOMIC append (a rejected append leaves the journal byte-identical), the fold twice + `from_records` rebuild = the byte-identical state; the zero-coverage-gap probes: the admitted set probed at EVERY journaled instant (the flip lands exactly AT the journaled instant; no between-instant intermediate window; no post-flip admission — 3 `check_zero_coverage_gap` checks; the pre-history instant never fabricated); the journal truth cross-checked against the identity authority's own records; the atomic flip through the accepted identity authority (a rejected rotation leaves the identity state AND the journal byte-identical — the authority's own all-or-nothing StoreBatch; v1-superseded + v2-active in ONE commit; the identity-role credential untouched — NodeID stability); the wire-forged non-atomic shapes (both generations admitted / neither / a revocation that keeps the revoked credential admitted / more than the single flip) all fail closed at construction, and the tampered record id fails closed at deserialization | SOFTWARE | case_03, case_04, case_05, case_06 |
| (b) revocation propagation — deterministic rounds with declared convergence bounds (a ROUND COUNT, never wall clock) | `round_deliveries` a pure function of the plan; two independent runs → byte-identical round ids; the rounds carry the declared fanout slices in the declared order with 1-based indices and convergence flags; the authoritative admitted set UNCHANGED by propagation; the unconvergeable plan (3 consumers, fanout 1, bound 2) fails closed `credential-propagation-unconverged` citing the declared ROUND-COUNT bound and the pending consumer — its bounded rounds STAY JOURNALED (the evidence of the bounded failure); the exact-bound plan converges at round 3; the bound is an integer round count (the plan carries ints only); one deterministic instant per DECLARED round — a count mismatch fails closed; the rounds replay byte-identically from records with the consumer-observation model (`consumer_observed_revocation`) and the converged verdict; propagating a non-revocation fails closed | SOFTWARE | case_07, case_08, case_09 |
| (c) emergency revocation — explicit, evidence-visible at every step | The DISTINCT typed kind (`emergency-revocation`) carrying exactly the three frozen steps in order (the ordinary `revocation` kind structurally cannot carry them — the emergency path is never a silent shortcut); the reason journaled verbatim; every step's LOCK-106 evidence references RESOLVE in the REAL evidence store (`verify_emergency_evidence` — the controller-verified emergency attestation, the M014 closed-loop authorization attestation, and the withdrawn-consent attestation the ACCEPTED authority's emergency stop appended); the identity record REVOKED with its revocation metadata; the M014 registry revoked (the `revoked` verdict observed first); the canonical session terminal with `emergency-stop`; the post-probes fail closed (`lifecycle:revoked` for the revoked credential, `authorization:revoked` for the node); the frozen W049 client driven through its OWN emergency-stop control (STOPPED, the local fail-safe detach first, the stop notification, the canonical lease revoked through the contract store's OWN command, the consent withdrawn); failed emergencies (a client not operating; an unknown authorization) raise the typed composition error and journal NO partial record | SOFTWARE | case_10, case_11 |
| (d) credential inventory verification — every admitted credential traces to a valid lifecycle record; a broken chain fails closed (a case per break kind) | The clean audit: 2 admitted credentials traced (status, key version, activation instant, the journaled operation references — rotation subjects AND replacements cited); the audit + trace records round-trip; the journaled audit is read-only evidence; the 7 break kinds each the typed `credential-inventory-incomplete` failure citing the kind: unknown-reference (a wire-forged journal carrying a phantom admitted reference), status-mismatch (the journal claiming a SUPERSEDED generation admitted — the local admitted set is never silently trusted over the authority), missing-activation (a forged ACTIVE record without an activation instant), missing-supersession, missing-revocation-info (forged public store records), generation-gap (a raw gapped v1/v3 chain), bookkeeping-missing (the M014 bookkeeping lacking the activation — the consumed M014 evaluation fails closed where the audit does) | SOFTWARE | case_12, case_13, case_14, case_15, case_16, case_17, case_18, case_19 |
| (e) the admission gate consumed BY REFERENCE from the accepted client//federation/ surfaces (no second authorization runtime — LOCK-117) | The composed probe drives the three ACCEPTED gates: the M014 credential-lifecycle verdict, the M014 principal-authorization registry check, and the converged traffic-admission point — the verdicts consumed VERBATIM (ok/authorized/active); the ZERO-byte probe idempotent (repeated probes admit, `bytes_admitted` unchanged); per-gate rejections recorded with the consumed typed classes (`lifecycle:not-active` for the superseded generation, `authorization:revoked` after a registry revocation, `admission-gate:rejected:lease-not-active` after an authority-side session revocation — the converged gate's own typed code, the registry intact); the raising twin; a non-accepted gate object rejected (isinstance-guarded — a second authorization runtime is never composed); the full drill through the frozen W049 client protocol (check_capability → become_ready → prepare_sharing → grant_consent → request_handoff → activate — the client journal and the idempotent request ledger carry the chain; the rotation flips the credential generation WITHOUT disturbing the canonical session or the frozen client; the canonical read window provider-bound) | SOFTWARE | case_20, case_21 |
| (f) LOCK-119 — key material never stored, logged, or echoed (fixtures assembled from fragments) | The structural probes: NO public M018 record type carries a bytes-typed member (all six record types walked; a bytes member rejected at the boundary); the assembled secret absent from EVERY journaled/serialized/echoed surface (the canonical journal snapshot, the fold digest, the emergency record, the probe record, the evidence store's snapshot lines, the reprs, the exception texts); the domain NEVER opens the store's secret path (`get_secret`/`put_secret` absent from the AST of every `credentials/` file); the fragment discipline: the FULL secret shape (head + seed + tail) appears in NO source — battery or domain; the fragments are inert; the assembly deterministic and distinct per seed; the only secret path is the accepted store (the secrets entered through the service's public APIs and are retrievable only through `get_secret`) | SOFTWARE | case_22, case_23 |
| Frozen vocabularies; the consumed vocabularies by reference | The M018 operation-kind/emergency-step/break-kind vocabularies frozen; the admitting verdict subsets strict subsets of the consumed M014 `CREDENTIAL_VERDICTS`/`AUTHORIZATION_VERDICTS` (import-time drift guards in `credentials/model.py`); the WORK-004 lifecycle states and the LOCK-106 `EVIDENCE_TYPES` consumed by reference | SOFTWARE | case_01 |
| Vocabulary/input gates fail closed | 18 typed probes: unknown kind, emergency-without-steps, ordinary-revocation-with-emergency-steps (the distinctness), the three non-atomic rotation shapes, read-only-op set changes, bad instants, secret-shaped references, plan fanout/rounds/duplicates, probe verdicts outside the consumed vocabularies, caller-supplied admitted/rejection (the composed verdict is mechanical), journal sequence gaps and unrecorded transitions — all reject with the specific typed code | SOFTWARE | case_02 |
| Canonical-JSON round-trips + typed errors + exception isolation | The operation/probe/plan/journal records round-trip byte-identically with the tamper-evident ids re-verified at deserialization; tampered dicts fail closed; consumed identity/M014/client rejections all wrap onto the typed error with the deterministic text preserved (no raw exception escapes the public surface); rejected compositions journal nothing | SOFTWARE | case_24, case_25 |
| Determinism under a re-run (and PYTHONHASHSEED variation) | The full drill scenario (journal digest, 6 record ids, the mid-scenario probe id, the emergency evidence refs) byte-identical across in-process re-runs AND across PYTHONHASHSEED 0/1/42 subprocesses | SOFTWARE | case_26, case_27 |
| One-way imports (criterion 8) | No accepted authority (contracts, replan, executionplans, evidence, assurance, offers, eligibility, policy, adapters, usage, commercial, allocation, payment, sharenet, roamlink, comos, developerapi, federation, identity, upgrade, scale, client, resilience, localfirst, recovery) imports `credentials/` (imports-only AST check — relative imports inside their own packages excluded); the legacy reservoir (sessions, mobility, multipath, edge, appliance) is un-imported source material only; the M015-M017 chain siblings are un-imported (the chain-independent composition) | SOFTWARE | case_28 |
| LOCK-119 clock/import discipline | AST audit: no wall-clock/randomness/network constructs anywhere in `credentials/`; imports confined to stdlib + `protocol` + the accepted M014 substrate (identity, federation, client, evidence) — by reference only | SOFTWARE | case_29 |
| Lock conformance (aggregate) | LOCK-101/106/111-class/117/118/119 structural evidence: opaque reference records with namespaced content-derived ids; the emergency evidence citations resolve to real LOCK-106 records; the declared-round determinism; byte-stable secret-free digests | SOFTWARE | case_30 |
| PR delta shape | Every delta file covered by the ACTIVE R8-CORE-001 scope (`authorization_provenance.covers`); no `spec/` or `.github/` touch | SOFTWARE | case_31 |
| Evidence-doc honesty | SOFTWARE class, by-reference composition, harvest, lock mapping, the fragment discipline and the open physical obligations disclosed; no affirmative physical claims | SOFTWARE | case_32 |

**Battery result: PASS (32/32 cases; the 7 per-kind inventory break cases are
individually numbered case_13..case_19 within the set), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** the emergency path's admission-gate step
  drives the canonical lease revocation through the contract store's OWN
  `RevokeLease` command (the converged authority's own path — never a local
  lease authority); `credentials/` consumes the accepted public surfaces by
  reference only (verified in the battery's one-way-import and PR-delta cases).
- **LOCK-106 (evidence typing):** the emergency path's every step carries
  evidence references that resolve to REAL typed evidence records inside the
  real evidence store — the controller-verified emergency attestation (the
  accepted `AttestationEvidence` typing), the M014 closed-loop authorization
  attestation lift, and the withdrawn-consent attestation the ACCEPTED
  authority's emergency stop appended; `verify_emergency_evidence` fails closed
  on any unresolvable citation (case_10, case_11, case_22).
- **LOCK-108-class (no silent weakening, the M018 reading):** the
  zero-coverage-gap kernel — no operation window in which a superseded or
  revoked credential is still admitted; the transition verified at construction
  AND at replay (the fold's continuity + atomicity kernels); a non-atomic
  authority outcome is never journaled as a rotation (case_04, case_05, case_06).
- **LOCK-111 (optimizer replaceability, the declared-rule class):** the
  propagation rounds are a pure function of the declared plan (same inputs →
  identical rounds, verified in-process and across PYTHONHASHSEED subprocesses);
  the convergence bound is a DECLARED ROUND COUNT, never wall clock (case_07,
  case_08, case_27).
- **LOCK-117 (authority uniqueness):** the identity authority stays the sole
  credential authority (the drill drives `IdentityService.rotate`/`revoke` —
  never a local lifecycle engine); the converged authorization runtime stays
  the sole admission gate (`probe_credential_admission` isinstance-guards the
  REAL `ConvergedAuthorizationRuntime` and rejects any other object; the
  composed verdict records the consumed verdicts verbatim — no second
  authorization runtime exists anywhere in `credentials/`) (case_20, case_28).
- **LOCK-118 (provenance):** every record carries typed provenance (the issuer
  + the namespaced content-derived ids over canonical JSON; the emergency steps
  carry their evidence references; the traces cite the journaled operations).
- **LOCK-119 (secrets):** the public types are structurally secret-free (no
  bytes-typed member on any record; a bytes member rejected at the boundary);
  secret material lives only behind the accepted `CredentialStore` interface,
  which this package never opens (`get_secret`/`put_secret` AST-absent); the
  rotation drill's `new_secret` transits verbatim to the accepted
  `IdentityService.rotate` and never enters any record; no wall clock, no
  randomness, no UUIDs, no network anywhere in `credentials/` (AST-audited);
  the battery's fixtures are assembled at runtime from fragments so the full
  shape never appears in source (case_22, case_23, case_29).

## 4. Judgment calls (disclosed)

1. **The lifecycle operation identity is derived over the POSITION-INDEPENDENT
   operation core (the idempotency key).** The accepted journal conventions
   derive record ids over content; the M018 journal additionally requires
   IDEMPOTENT appends (a retried operation re-derives the same identity and
   never double-applies), so the operation identity deliberately derives over
   the position-independent core while the journal position stays the separate
   monotonic `sequence` member validated by the fold (gapless, unique per
   identity).  Disclosed as the M016-journal-precedent design choice the
   idempotency discipline requires.
2. **The admitted set is node-scoped and read from the identity authority's own
   records.** The M018 journal records the node's admitted credential-reference
   set (ALL roles — the identity credential stays admitted through operational
   rotations, exercising the NodeID-stability discipline) as read from the
   identity authority's public records (ACTIVE status only) immediately before
   and after each operation.  The journal records the transitions as EVIDENCE;
   the authority remains the truth (the battery cross-checks journal == authority
   at every step).  A drill-scoped revocation of a NON-admitted credential
   fails the one-removal kernel — the M018 journal semantics cover admitted-set
   transitions only (revoking non-admitted generations remains directly
   available through the accepted identity authority).
3. **The composed admission verdict is mechanical, never re-decided.** The
   probe's `admitted`/`rejection` members are DERIVED at construction from the
   three consumed verdicts (a caller-supplied disagreement fails closed), and
   the first rejecting gate is named deterministically.  This is the LOCK-117
   discipline made structural: `credentials/gate.py` contains zero policy rules
   — it composes the accepted M014 gates and the converged traffic-admission
   point and records their decisions.
4. **The emergency path journals ONE distinct typed operation after the three
   steps complete.** The steps run in the frozen order through the accepted
   authorities; the journal append happens only on full completion (a failed
   emergency leaves the M018 journal without a partial record — the
   authority-side transitions that DID complete remain visible at their own
   authorities, the fail-safe direction, and the typed error discloses the
   failing step).  The three steps' LOCK-106 evidence references are carried ON
   the single distinct `emergency-revocation` record — the emergency path is
   one journaled operation, never a silent shortcut and never three loose
   writes.
5. **The emergency controller's attestation producer is
   `m018-lifecycle:emergency`.** The accepted evidence domain rejects
   secret-shaped reference text including the token "credential"
   (`evidence/model.py`'s frozen LOCK-119 grammar), so the M018 emergency
   producer name deliberately avoids the package name's noun; the producer
   string is DATA identifying the emergency controller, nothing more.
6. **The battery's per-case worlds are rebuilt fresh.** Every case composes its
   own identity world + admission-gate world + journal (the client battery's
   `_build` convention) so mutating cases stay isolated; the secrets are
   assembled per seed from fragments (`_secret(seed)`) so no case's fixture
   shares material with another's except through the deterministic assembly.

## 5. By-reference composition and the legacy reservoir (disclosed)

- **By-reference composition:** `credentials/` imports only the accepted
  authorities — `identity/` (the WORK-004 credential machinery and the M014
  convergence surfaces: `IdentityService`, the `CredentialStore` public reads,
  `CredentialLifecyclePolicy`/`State`, `AuthorizationRegistry`,
  `authorization_attestation`), `federation/` (the M014 converged admission
  gate: `ConvergedAuthorizationRuntime`, `AuthorizationScope`), `client/` (the
  frozen W049 provider client, the sandbox adapter, and the M014 composition
  root `build_converged_provider_client`), and `evidence/` (the accepted
  LOCK-106 `AttestationEvidence` typing and the real `EvidenceStore`) — plus
  `protocol/` and the stdlib.  AST-audited (case_29); the import direction is
  one-way (case_28: no accepted authority imports `credentials/`).  Nothing is
  reimplemented, weakened, forked, or bypassed; the M014 verdict vocabularies
  are consumed, never redefined (case_01, with import-time drift guards); the
  identity rotation/revocation and the converged admission gate are driven
  through their public APIs, never duplicated (case_05, case_20, case_21).
- **The M015-M017 chain siblings are not composed.** M018 is chain-independent
  (the M013 precedent class): the substrate is the accepted R7/M014 state, so
  `resilience/`, `localfirst/` and `recovery/` are neither imported nor touched
  (case_28) — the branch composes only what the R8 charter names as the M018
  composition substrate and merges in any order relative to the chain.
- **The legacy reservoir is source material only.** The credential-drill
  disciplines (rotation drills, revocation propagation, emergency paths,
  inventory audits) are re-expressed on the accepted 1.1 authorities inside
  `credentials/`; the legacy packages are NOT imported (AST-audited, case_28),
  NOT modified, and remain their own authorities for their existing consumers.

## 6. Out-of-scope discipline (nothing else changed)

The M018 delta (from the DEC-0116 acceptance head `bda91c39`) contains only:
`credentials/` (NEW, 8 files), `tools/credential_selftest.py` (NEW), and
`docs/M018-evidence.md` (this record).  No control-plane surface, no `spec/`
file, no `.github/` file, no protocol schema, and no accepted-domain
modification (`identity/`, `federation/`, `client/`, `contracts/`, `evidence/`,
`offers/`, or any other canonical domain — all consumed by reference only;
verified in the battery's one-way-import and PR-delta cases).  The drift guard
classifies the delta implementation-only; the provenance gate verifies full
coverage by R8-CORE-001 (`credentials/`, `tools/`, `docs/M018-evidence.md` are
declared M018 scope entries).

The CI workflow's M018 step does not exist at this head and is NOT added by
this delivery: the battery's CI wiring is made by the acceptance decision (the
DEC-0113 chain-independent precedent — the workflow file is control-plane, out
of the implementation scope).  When the Architect records the M018 acceptance,
the governance commit wires `tools/credential_selftest.py` with the
established existence-guard pattern, exactly as the M016/M017 steps were wired
by their acceptance decisions.

## 7. Evidence classes (honest disclosure)

- All M018 acceptance criteria: **SOFTWARE** class (deterministic offline
  battery, 32/32 PASS on the delivery head; every blocking battery and
  governance gate in the CI suite green on the delivery head).
- No pending child is claimed delivered: the M017 `recovery/` surface does not
  exist at this head and is not faked (another worker's in-flight surface,
  never touched); the CI existence-guard step for its battery skips visibly
  (disclosed, the DEC-0116 wiring convention).  The M018 battery's own CI step
  is not present at this head (the acceptance-wiring convention above).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M018 creates and closes
  none; EVID-002..EVID-008 remain open and untouched, and no evidence produced
  by this delivery is physical, production, or live-service evidence.  No
  SOFTWARE evidence is converted into PHYSICAL PASS.

## 8. Delivery provenance

- Branch: `m018-credentials`, append-only from the DEC-0116 acceptance head
  `bda91c39` (the current main, the accepted R7 state); no rebase, no
  force-push, no amending; commit-as-you-go delivery history (the package
  first, then the battery, then this record).
- Battery: `python3 tools/credential_selftest.py` -> PASS (32/32) on the
  delivery head, run 3× consecutively, byte-identical.
- Full suite: every battery the CI workflow runs, in exact workflow order, on
  the delivery head with exit-code-based detection — see the PR body for the
  numbered results.
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
- Accepted sibling batteries at this head: contract 54/54, offer 49/49,
  developerapi 56/56, usage 53/53, commercial 41/41, sharenet 33/33, roamlink
  56/56, comos 33/33, assurance 97/97, executionplan 36/36, adapter 70/70,
  replan 38/38, payment 44/44, eligibility 46/46, policy 103/103, client 24/24,
  scale 45/45, conformance 63/63, resilience 36/36, localfirst 35/35 (verified
  by direct execution on the delivery head, exit-code-based).
