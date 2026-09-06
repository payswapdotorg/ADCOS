# WORK-057 Evidence — Provider Onboarding & Federation (R6)

**Work Item:** WORK-057 — Provider Onboarding & Federation
**Authorization:** `WORK-057-CORE-001` (DEC-0095) — the only active implementation authorization
**Delivery branch:** `work-057-provider-onboarding-federation` (created from main `12ae8f7`)
**Pinned baseline:** `16c066ff4766d362f0edfcb790524b2c0ef44cae`
**Governed baseline of the branch point:** `12ae8f7159aa7ddbc82b7e6aa6a3dc5d61ae676a`
**Architecture Version:** 1.0 (unchanged) — **Protocol Version:** 1.0 (unchanged)

---

## §E.1 What was delivered

A deterministic, auditable **provider onboarding and federation lifecycle integration
layer** over the existing authorities — exactly the smallest coherent set required by
`docs/WORK-057-IMPLEMENTATION-PROMPT.md`:

```text
registration → operator/domain identity binding → scoped credential issuance →
adapter declaration/certification → capability/resource declaration →
service/commercial profile binding → eligibility/policy evaluation →
federation proposal → explicit acceptance → active federated membership →
suspension/revocation/offboarding
```

New files (the complete delivery delta — see §E.8):

| Path | Role |
|---|---|
| `federation/onboarding_model.py` | Domain model: 14-state lifecycle, 18 command kinds, 5 least-authority credential scopes, 46 reason codes; application/credential/declaration/profile-binding/journal records; content-derived ids; LOCK-023 secret rejection; LOCK-001/002/003/017 token rejection |
| `federation/onboarding_store.py` | Append-only command journal (memory + file-backed, single-writer canonical JSON lines, torn-write fail closed) with per-application sequence watermarks, idempotent duplicate detection, key-conflict fail-closed; the fold-state projection with deterministic snapshot |
| `federation/onboarding_service.py` | The lifecycle executor: authentication (key proof-of-possession + scoped credentials), journal-first fold, `load()` construction-is-recovery with journal-tamper verification, all 18 command handlers composing the federation authority |
| `adapters/certification.py` | The adapters authority's certification record + fail-closed certification evaluation (attestation + evidence required; tamper-evident content-derived ids; LOCK-023; vendor isolation) |
| `tools/onboarding_selftest.py` | The WORK-057 acceptance battery: 73 deterministic adversarial cases |
| `docs/WORK-057-evidence.md` | This evidence manifest |
| `docs/WORK-057-handoff.md` | Updated with the delivery record |

**Not delivered (deliberately):** no successor Work Item, no new authorization, no
CI workflow change (`.github/` is outside the authorized scope), no modification of
any frozen governance/architecture surface, no W048 restoration, no W040 alteration.

## §E.2 Authority composition (what is consumed, never duplicated)

Every authority boundary in the frozen discipline batteries holds at the exact head
of this delivery (see §E.3). The layering that achieves it:

- **Federation (WORK-015) is the only federation authority.** Every relationship,
  grant, domain, and event is created through `FederationStore`'s public API; the
  onboarding relationship id IS `derive_relationship_id` of the owning authority
  (case_41); no federation vocabulary value was added (the WORK-015 freeze battery
  passes 52/52 unmodified).
- **Identity (WORK-004)** is consumed only by validated NodeID reference
  (`parse_node_id(...).text`); the onboarding application id is a content-derived
  fingerprint over identity material, never a second NodeID grammar.
- **Policy (WORK-010) and eligibility (WORK-045) are consumed as records.** The
  eligibility gate requires a tamper-evident policy ALLOW whose recomputed
  `sha256(canonical_bytes)` matches its id and whose `(set_id, version)` matches a
  declared reference (the `verify_establishment_policy` discipline), plus an
  eligible connectivity-domain provider-subject `DecisionRecord` inside its validity
  window. Onboarding confers neither allow nor eligibility (cases 32–39).
- **Capabilities (WORK-005) and resources (WORK-008) stay authorities.** Capability
  declarations are classified claims (KNOWN preserved, UNKNOWN_BUT_WELL_FORMED
  preserved, INVALID rejected; the registry is untouched — case_29); resource
  declarations bind ownership over the frozen WORK-008 reference grammar, and the
  battery proves the resource authority's own parser agrees on the same ids
  (case_27). Declarations never become reachability truth.
- **Adapters (WORK-016) stay behind the boundary.** Certification records are built
  by `adapters.certification` (the adapter authority's own surface, importing only
  its own package + protocol) and are consumed by the onboarding layer as validated
  data documents — the federation package never imports the adapter boundary
  (case_22 pins this at source level; the frozen core-import discipline passes).
- **Upgrade/version (WORK-029/WORK-003).** No runtime package may import the
  upgrade family (frozen reverse-import discipline), so the mixed-version gate
  consumes the WORK-003 version line (`protocol.versioning.classify_major`) and
  carries the additive-evolution floor as data; the battery proves the gate agrees
  verdict-for-verdict with the WORK-029 authority's own
  `negotiate_protocol_profile` — compatible pairs share the floor, major mismatches
  fail closed with no cross-major fallback (cases 65–66).
- **Commercial/settlement (WORK-051/052/053, P7).** Profile bindings are opaque
  references only; settlement stays a typed opaque reference; there is no billing,
  pricing, token, payment, or settlement code path (cases 30–31; import audit).
- **No connectivity state.** Structurally the service writes only its own journal,
  its own fold state, and the injected federation store (case_52/53 attribute +
  import audits); no session/path/route/transport/usage/payment/settlement state can
  be created by onboarding.

## §E.3 Verification (the exact numbers)

**The WORK-057 battery:**

```text
$ python3 tools/onboarding_selftest.py
ADCOS provider onboarding self-test (WORK-057)
========================================================================
... 73 cases ...
------------------------------------------------------------------------
Result: PASS (73/73 cases)
```

- Two consecutive runs: **byte-identical** (`cmp`).
- `PYTHONHASHSEED=0 / 1 / 7919` + default: **all byte-identical** (`cmp`, including
  the in-battery cross-process golden-path digest checks, cases 67–68).
- Recovery: `ProviderOnboardingService.load` reproduces the byte-identical state
  AND federation-store snapshot from the journaled prefix; a mid-lifecycle prefix
  folds to the exact interrupted state and resumes to the byte-identical final
  state (cases 59–60); the file journal reloads identically and torn writes fail
  closed (case 64).

**Sibling regression (all at this exact working tree, vs. the same batteries at
the clean branch point `12ae8f7`):**

| Battery | At `12ae8f7` (clean) | At this delivery | Verdict |
|---|---|---|---|
| federation (W015) | PASS 52/52 | PASS 52/52 | unchanged |
| adapter (W016) | PASS 56/56 | PASS 56/56 | unchanged |
| composition (W054) | PASS 55/55 | PASS 55/55 | unchanged (case_51 evergreen per DEC-0093) |
| upgrade (W029) | PASS 41/41 | PASS 41/41 | unchanged |
| fivegc / ran / wifi / mesh / distcore / backhaul / ipintegration / networkpath | PASS | PASS | unchanged |
| sessions / multipath / mobility / transport / routing / policy / intent / topology / resources / capabilities / identity / discovery / envelope | PASS | PASS | unchanged |
| commercial / usage / allocation / marketplace / telemetry / energy / security / service / simulator / platform / edge / mobile / appliance / oran / imt / scale / agent-family / platformcaps | PASS | PASS | unchanged |
| spec_check | FAIL 10/16 + 2 advisory + 1 SKIP | **byte-identical output** (verified `cmp` vs baseline) | inherited mainline signature |
| spec_check_selftest | FAIL (mutation-anchor drift in `spec/architect/execution-state.yaml`) | same | inherited (the R6 governance text itself) |
| management | FAIL 1/39 (case_29: `composition/world.py` imports management) | same failing case, identical | inherited |
| conformance (W032) | FAIL 2/63 {case_62, case_63} | same failing set | inherited (case_62 is the W055-era live-delta oracle whose detail list already enumerated 34 post-W055 governance files at baseline; at this delivery its list additionally names this work item's four new code files) |
| agent | FAIL (case_29 runs the conformance selftest) | same failing case, identical | inherited |
| payment / eligibility | ImportError `EvidenceFamily` (usage export) | identical | inherited |
| client | ImportError `CapabilityMatrix` (containment) | identical | inherited |
| developerapi (W056) | PASS 56/56 | **55/56** | see §E.6 — the one cross-era live-delta condition |

**CI boundary (honest):** `.github/` is outside the WORK-057 authorized scope, so
no CI workflow change was made. On this PR the unchanged `spec-check` workflow runs:
job 1 (`specification-consistency`) fails at its first step — `spec_check.py` with
the byte-identical inherited 10/16 signature — which skips that job's later battery
steps (the known mainline condition, identical to every PR against this main);
job 2 (`platform-capability-runtime`, the W050 exact-head battery) runs against this
PR's head and is green. The W057 battery has no CI vehicle (the DEC-0092 vehicle
runs only the W056/W054 batteries, and dispatching it at this head would reproduce
exactly the §E.6 condition through the W056 battery) — the W057 battery's evidence
is the worker-local execution with full determinism proofs above.

## §E.4 Acceptance-criteria mapping (prompt §"Acceptance requirements" → cases)

| Requirement | Cases |
|---|---|
| deterministic registration and identity binding | 01–07, 67–68 |
| adapter certification and forbidden-import discipline | 17–22 (and the frozen adapter/import batteries, §E.3) |
| capability/resource provenance, validity, and expiry | 24–29 |
| eligibility/policy fail-closed behavior | 32–39 |
| federation proposal/acceptance/activation | 40–45 |
| suspension/revocation/offboarding and historical preservation | 46–50 |
| non-transitivity and authority separation | 51–53 |
| duplicate/replay/out-of-order/concurrent safety | 03–04, 54–58 |
| interrupted onboarding recovery | 59–64 |
| mixed-version behavior | 65–66 |
| credential and secret separation | 08–16 |
| auditability and evidence provenance | 02, 18, 49, 61–63 (journal + snapshot discipline) |
| onboarding cannot create connectivity/…/settlement state | 22, 52–53 (+ §E.2 structural proof) |
| deterministic repeat-run evidence | 67–68 (+ battery-level `cmp`, §E.3) |
| regression compatibility with accepted W054/W055/W056 surfaces | §E.3 table |
| no W048 restoration and W040 untouched | 73 |

## §E.5 Security model evidence

Malformed, expired, incompatible, unauthorized, conflicting, revoked, replayed,
duplicated, out-of-order, concurrent, and stale inputs all fail closed with stable
reason codes and journaled audit records (cases 03–08, 11–16, 18–21, 23, 27–28,
32–39, 42–44, 54–58, 61–62). Trust is explicit: peer binding is enforced by the
federation authority (case_43), membership never confers node trust (case_39) and
never crosses providers (case_51). Secrets are separated from ordinary state:
credential secrets are derived once, returned once, and only their digests are
stored or journaled (case_09); secret-shaped payload members are rejected at
construction (case_08); wrong secrets and unknown references share one failure code
so no enumeration oracle exists (case_14); operator key material is proof-of-
possession only — never stored, never journaled (case_15).

## §E.6 The one cross-era condition (surfaced, not pre-empted)

The accepted W056 battery's `case_41_pr_delta_shape` measures the **live worktree
delta from the current merge-base with main** and asserts it stays inside the
W056-era authorized path tuple. At this delivery's tree it flags this work item's
five authorized new files, so the W056 battery reads 55/56 worker-locally
(56/56 at the clean branch point). This is the same structural condition DEC-0093
corrected in the W054 battery (`case_51`: live-delta oracle → immutable historical
baseline-to-accepted-delivery proof): a scope oracle pinned to one Work Item's era
is hostile to any later authorized Work Item. Per the DEC-0091 discipline, the
correction of an accepted battery's oracle is Architect-owned; it is **surfaced
here and NOT pre-empted**. No other accepted battery changes verdict at this
delivery (§E.3; the conformance case_62 list growth is the same already-failing
cross-era oracle that already enumerated 34 governance files at baseline).

## §E.7 Architecture-lock compliance and no-drift statements

**Architecture-lock compliance:** this delivery adds an integration layer strictly
subordinate to the existing authorities. It creates no identity, federation,
capability, resource, policy, routing, session, transport, NetworkPath, usage,
payment, allocation, settlement, or topology authority; it registers no protocol
message type and no federation extension key; it adds no vendor or
access-technology semantics anywhere (LOCK-001/002/003/017 audits in §E.3); it
never modifies `spec/architect/` (case_71/72 prove the frozen surfaces and the
delivery scope against pinned, environment-independent object SHAs — the
DEC-0093 evergreen discipline).

**No-drift statement:** Architecture Version 1.0 and Protocol Version 1.0 are
unchanged; the frozen documents (`spec/architecture.md`,
`spec/architecture-lock.md`, `spec/mission.md`, `spec/work-items.md`,
`spec/dependency-graph.md`, `spec/schemas/protocol.json`) are byte-identical to
the pinned baseline `16c066ff…` (case_71); `spec/architect/` is untouched by this
delta (case_72); all prior frozen vocabulary freezes pass unmodified
(the W015/W016/W005/W008/W010/W029/W032 batteries, §E.3).

**W048/W040 statements:** WORK-048 was **not restored** — no sharing-runtime
material was added or modified (case_73: no delta under any W048 path, no new
W048-named files in history). WORK-040 was **not altered** — its
`docs/WORK-040-correction-handoff.md` and `pilot/` surfaces are byte-identical to
the baseline and its physical-evidence obligations remain W040-owned (case_73).

## §E.8 Baseline, ancestry, and changed-file proof

```text
Baseline (pinned, evergreen): 16c066ff4766d362f0edfcb790524b2c0ef44cae
Branch point (delivery base): 12ae8f7159aa7ddbc82b7e6aa6a3dc5d61ae676a
Delivery delta (git diff --name-only 12ae8f7):
    adapters/certification.py           (new)
    federation/onboarding_model.py      (new)
    federation/onboarding_service.py    (new)
    federation/onboarding_store.py      (new)
    tools/onboarding_selftest.py        (new)
    docs/WORK-057-evidence.md           (new)
    docs/WORK-057-handoff.md            (modified: delivery record)
```

Every delta path is inside the `WORK-057-CORE-001` scope list (proven in-battery,
case_72, against the recorded branch point — fixed object SHA,
environment-independent). The branch was created from current main `12ae8f7` and
advances by plain commits only (no rebase, no force).

## §E.9 Exact verification commands

```bash
python3 tools/onboarding_selftest.py            # PASS 73/73
python3 tools/onboarding_selftest.py > r1.txt 2>&1
python3 tools/onboarding_selftest.py > r2.txt 2>&1
cmp r1.txt r2.txt                               # byte-identical
for seed in 0 1 7919; do PYTHONHASHSEED=$seed \
  python3 tools/onboarding_selftest.py > s$seed.txt 2>&1; done
cmp s0.txt s1.txt && cmp s0.txt s7919.txt       # byte-identical
# sibling regression (see the §E.3 table for the full list and results):
python3 tools/federation_selftest.py            # PASS 52/52
python3 tools/composition_selftest.py           # PASS 55/55
python3 tools/developerapi_selftest.py          # 55/56 (§E.6 condition)
python3 tools/upgrade_selftest.py               # PASS 41/41
# frozen-surface / scope / W048/W040 guards (pinned object SHAs):
git diff 16c066ff4766d362f0edfcb790524b2c0ef44cae -- \
    spec/architecture.md spec/architecture-lock.md spec/mission.md \
    spec/work-items.md spec/dependency-graph.md spec/schemas/protocol.json  # empty
git diff --name-only 12ae8f7159aa7ddbc82b7e6aa6a3dc5d61ae676a                # §E.8 list
```

## §E.10 Known boundaries (honest)

1. The W057 battery runs worker-locally; no CI vehicle exists for it under the
   current authorization boundary (§E.3 CI paragraph).
2. The W056 battery's case_41 live-delta condition (§E.6) — surfaced for
   Architect adjudication.
3. The fold's journal-tamper verification trusts secret-dependent authentication
   rejection reasons as journaled (they cannot be re-derived without the secrets —
   by design); every deterministic outcome is fold-verified, and a success reason
   on a rejected record (or any unreproducible deterministic outcome) fails closed
   (cases 61–62).
4. Registration-time key-material proof is proof-of-possession by HMAC digest; the
   repository never sees the material itself (the digest is journaled).
