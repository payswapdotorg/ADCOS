# WORK-056 — Developer Connectivity Platform Production Hardening (R5) — Evidence Record

Work Item: `WORK-056` — authorization `WORK-056-CORE-001` — decision
`DEC-0089` (scope amended by `DEC-0090`).

- Authorized baseline (ancestor of the delivery): `7ae438d46041b228164cc8880be37dc21f972b6f`
- Branch root (the post-governance mainline the Architect cut): `4852a016fce61cecec8078084da1d9bbe81d2681` (the PR #16 guarded merge)
- Authoritative mainline incorporated by the round-2 delivery: `e0b8e0f39a7adc885e0a8da9180ad06db9bd14a8` (PR #18, DEC-0090)
- Authorized branch: `work-056-developer-platform-hardening`
- Round-2 delivery: the round-1 commit `4ac8107811546e14f9a29a50139000e1a0231752`, then a plain merge of the DEC-0090 mainline, then the round-2 correction commit directly on top (no rebase of published history, no force; the exact head SHA is recorded in the PR body, the PR head, and the worker worklog — the battery's scope/ancestry case verifies the lineage mechanically on every run, so the claim does not depend on this document).

Everything in this record is reproducible from a fresh checkout
of the delivery head with a single command per section (Python
3, standard library only, no network, no wall clock).

---

# ROUND 2 — the Architect disposition correction

The round-1 delivery (head `4ac8107`) received **CHANGES
REQUIRED** with two findings. This section records the round-2
correction of both; the round-1 record below is retained as the
historical baseline and is superseded ONLY where this section
says so (the route-delta disclosure in its §2 and §7 is
superseded: the route delta is ELIMINATED, not disclosed).

## R2.1 Finding 1 corrected — the frozen 1.x contract is preserved

The round-1 delivery had changed the accepted W046 1.x
economic-policy REST contract:

| 1.x surface | accepted W046 (frozen) | round-1 delivery (defect) | round-2 (this delivery) |
|---|---|---|---|
| policy read route | `GET /economic-policies/{id}/{version}` | `GET /economic-policies/{id}` (silent break) | **`GET /economic-policies/{id}/{version}` restored** |
| request members | 11 members, `effective_until` optional, `tax_bps` required, client-chosen `policy_id` + integer `version` | 9 canonical terms, different required-member model (silent break) | **the exact 11-member 1.x model restored** (schema table + strict validation + handler) |
| response members | `id = "policy_id@version"`, kind, environment + the 11 members | canonical PolicyVersion serialization | **the exact 1.x projection restored** |
| mutation resource id | `policy_id@version` | the derived canonical id | **`policy_id@version` restored** |
| conflict semantic | same `(policy_id, version)` + different content fails closed; versions immutable; exact redelivery idempotent | different terms silently mint a new version | **fail closed 409 restored** (boundary-detected, before any canonical admission) |

The boundary still re-binds its INTERNALS to the current
canonical W053 terms-derived immutable `PolicyVersion` (the
round-1 import repair is retained) — but the 1.x wire contract
is now adapted, never redefined. The compatibility layer
(module-level in `developerapi/gateway.py`, single-sited):

- **The label-block encoding.** The canonical free-text `label`
  term carries the 1.x-only coordinate block
  (`{policy_id, version, tax_bps, open_ended}` as canonical JSON
  under the reserved prefix `adc-os-1x-policy:v1:`). The label
  participates in the canonical policy-id derivation, so
  distinct 1.x coordinates stay distinct immutable versions,
  identical 1.x bodies deduplicate canonically (the canonical
  REGISTER_POLICY duplicate path), and a same-coordinate/
  different-content re-registration derives a different label
  and is detected by the boundary's pre-admission conflict check.
- **The shared economics map 1:1** onto the canonical terms:
  `adc_os_share_bps -> adcos_share_bps`,
  `developer_share_min/max_bps -> provider_min/max_bps`,
  `rounding -> rounding_mode`, `exponent -> minor_unit_digits`,
  `currency` and the effective window unchanged.
- **The open-ended window** (absent/empty 1.x `effective_until`)
  is represented canonically as the maximal closed window
  (`9999-12-31T23:59:59Z`); the `open_ended` flag round-trips in
  the label block so the 1.x response projects
  `effective_until = ""` exactly as the 1.x contract defines.
- **1.x-only member constraints** the current canonical model
  cannot carry (`version >= 1`, `tax_bps` in `[0, 10000]`, and
  the frozen `adc_os_share_bps + tax_bps <= 10000` sum rule) are
  enforced at the boundary as boundary-local `invalid-input`
  validation (empty `canonical_reason` — never a fabricated
  canonical reason).
- **Non-1.x canonical policies are not projected**: the 1.x list
  and coordinate reads resolve only policies whose label carries
  a 1.x coordinate block (registered through the 1.x contract);
  canonical policies registered through other surfaces are never
  given fabricated 1.x members.
- The stale `_reconstruct_emission` /
  `_resource_owner` policy fragments (round-1 remnants that
  still referenced the retired W046-era
  `record.command.policy_id` / two-argument `policy()` shape)
  are re-bound to the 1.x compatibility layer.

**Disclosed honest boundaries of the adaptation** (value-level,
not contract-level — the wire contract, routes, member set,
required-ness, idempotency, conflict, and immutability semantics
are all preserved):

1. The 1.x `rounding` value vocabulary included `ceiling`; the
   current canonical RoundingMode vocabulary (`floor`,
   `half-up`, `half-even`) retired it, and the 1.x `exponent`
   range (0..12) exceeds the canonical `minor_unit_digits` range
   (0..6). A 1.x body carrying a retired/narrowed value fails
   closed through the canonical `policy-invalid` classification
   (never silently reinterpreted); shared-member value validity
   is the canonical authority's, per the boundary discipline.
2. The 1.x conflicting re-registration now surfaces as HTTP 409
   with boundary reason `idempotency-conflict` (the boundary's
   frozen durable-conflict family — the same family the boundary
   already maps the canonical `command-conflict` to) and an
   EMPTY `canonical_reason` (the conflict is boundary-enforced;
   the current canonical register_policy never raises it, and the
   boundary never fabricates a canonical reason). The old-world
   observable `canonical_reason: "policy-conflict"` belonged to
   the retired canonical vocabulary and is not resurrected. The
   status (409), fail-closed behavior, and the immutable-versions
   message wording are preserved.

Case 27 now pins the full restored contract end to end (the
11-member round-trip, the `policy_id@version` identity, replay,
canonical dedup, the 1.x conflict, the open-ended window, the
coordinate-exact reads, the non-integer version-segment
rejection, the strict rejection of a terms-shaped non-1.x body,
the 1.x-only constraints, and the canonical
`policy-invalid`/`policy-unknown` preservation), and case 46's
version-laundering discrimination now ALSO covers the 1.x policy
version coordinate (an unregistered coordinate fails genuine
`policy-unknown` while the laundering candidate silently
substitutes a registered one and fabricates success).

## R2.2 Finding 2 applied — the DEC-0090 W054 oracle reconciliation

The DEC-0090 amendment (on the incorporated mainline
`e0b8e0f`) authorizes exactly one behavioral-classification
change in `tools/composition_selftest.py`: the W054 WORK-046
availability oracle, case_03, must expect `AVAILABLE` with the
repaired-state detail instead of the obsolete import-broken/
no-repair wording. Applied as authorized:

- `case_03_w046_inherited_defect_disclosed` — the named
  reconciliation: `AuthorityAvailability.AVAILABLE` + the
  repaired-state detail ("imports cleanly") asserted; the ok
  message rewritten to the repaired-state wording.
- **The same single oracle's other pin sites** — `case_01` (the
  availability-table classification check "WORK-046 is not
  classified DEFECT") and `case_24` (the webhook-case
  availability pin "W046 is not disclosed as defective") pin the
  IDENTICAL oracle value. The battery is fail-fast
  (`main()` breaks on the first failure), and DEC-0090's own
  governance requirement #4 is "The composition battery must
  return to 55/55 with no other changes introduced under this
  amendment" — reconciling the oracle VALUE at its three pin
  sites is the only way to satisfy it (reconciling case_03
  literally alone leaves case_01 red). The three-site
  reconciliation changes ONE semantic (the expected W046
  availability classification, DEFECT -> AVAILABLE) plus its
  stale wording; the two module-level docstrings that state the
  old classification as current fact are updated to the
  reconciled fact. Nothing else in the file changes: the
  composition package (`composition/authority.py`'s
  `W046_DEFECT_DETAIL` and `_w46_defect`, which already report
  AVAILABLE honestly post-repair) is untouched; no composition
  authority, production code, W048 behavior, or other test
  semantics change.

Fresh proof: the W054 composition battery returns to **55/55**
at the delivery head (byte-identical repeat runs; the
round-1-red 54/55-classified state is gone).

## R2.3 Fresh verification at the round-2 delivery head

| Battery | Round-2 result at the exact head | Classification |
|---|---|---|
| `tools/developerapi_selftest.py` | **PASS 56/56** (45 re-bound W046 cases + 11 discrimination; case 27 and case 46 now pin the restored 1.x contract) | the W056 acceptance battery |
| determinism (case 35/36 in-battery + two full runs + `PYTHONHASHSEED=0/1/7919/unset`) | byte-identical outputs | deterministic evidence |
| `tools/composition_selftest.py` | **PASS 55/55** (the DEC-0090 oracle reconciled; every other case byte-identical in name and outcome to the accepted W054 battery) | the amended W054 battery, restored green |
| commercial / usage / allocation selftests | 38/38, 49/49, 60/60 — unchanged, verified at the head | accepted sibling batteries remain green |
| `spec_check.py` | 12/16 blocking + 2 advisory (ARCH-08 SKIP) — byte-identical to the clean branch root and to round 1 | inherited governance-state failure (pre-existing on main), no new failure |
| conformance selftest | 2/63 — the same two cases fail as at the clean branch root and current main | inherited (post-W055-baseline governance merges), no new failure |
| CI | the W050 exact-head battery runs on the pushed head; the specification-consistency job carries the inherited `spec_check` failure signature (its subsequent steps are skipped by CI design) | no CI success claimed for the spec job; the exact-head battery is the CI-verified ancestry leg |

Scope and ancestry at the round-2 head: the worker's own
commits (the merge + the correction) touch ONLY the amended
authorized scope (`developerapi/`,
`tools/developerapi_selftest.py`,
`tools/composition_selftest.py` [DEC-0090 only],
`docs/WORK-056-evidence.md`, `docs/WORK-056-handoff.md`);
`spec/architect/` arrives ONLY through the merged Architect
mainline `e0b8e0f` (the DEC-0090 record and the amended
authorization — authored and merged by the Architect, carried
into the branch by the plain merge, never edited by the
worker); the frozen surfaces are untouched; the cumulative PR
delta measured from `merge-base(HEAD, main)` is confined to the
amended scope; case 41 verifies the scope + the
7ae438d/4852a016/e0b8e0f ancestry mechanically.

## R2.4 Honest boundaries (round 2)

- All W056 evidence remains SOFTWARE; nothing promotes or closes
  W040's PHYSICAL obligations (EVID-007/EVID-008 remain open).
- The value-level adaptation boundaries of §R2.1 (retired
  `ceiling` rounding, narrowed exponent range, the conflict
  classification's boundary-local reason) are disclosed above
  and are the honest maximum within the worker authorization:
  the alternative (a versioned breaking transition) requires
  durable governance the worker cannot self-issue.
- No CI success is claimed for the specification-consistency
  job (the inherited signature); the W050 exact-head battery is
  green on the pushed head.
- `WAITING_FOR_ARCHITECT` at the round-2 head; not
  self-accepted, not self-merged; the guarded merge remains
  Architect-only.

---


## 1. Delivery shape

The complete changed-path inventory of the exact Git tree
(`git diff --numstat 4852a016 <head>`):

| Path | Kind | Purpose |
|---|---|---|
| `developerapi/errors.py` | modified | the canonical-reason table re-bound to the three CURRENT frozen vocabularies |
| `developerapi/gateway.py` | modified | the adapted-authority layer re-bound to the current W052/W053 public APIs |
| `developerapi/schema.py` | modified | the economic-policy request schema re-bound to the current canonical policy terms |
| `tools/developerapi_selftest.py` | modified | the battery re-bound + the W056 discrimination layer (cases 46–56) + the W056 scope/ancestry proof (case 41) |
| `docs/WORK-056-evidence.md` | added | this record |
| `docs/WORK-056-handoff.md` | modified | the delivery/waiting state recorded |

Exactly the authorized scope of `WORK-056-CORE-001` — no other
path is touched, `spec/architect/` is untouched, and the frozen
contract surfaces (`spec/architecture.md`,
`spec/architecture-lock.md`, `spec/schemas/`) are untouched.

## 2. The hardening problem found and repaired (the re-binding)

The accepted W046 boundary was **import-broken at the authorized
baseline**: `developerapi/gateway.py` cross-imported
`usage.errors.UsageLedgerError` and the `usage.lifecycle` /
`allocation.lifecycle` module layout — names that the accepted
W052/W053 review corrections had replaced (`usage.ledger`,
`usage.errors.UsageError`, `allocation.ledger`) while reshaping
the usage/policy projections (`account()`/`accounts()` reads and
the versioned policy model no longer exist). The W054
composition battery had honestly classified this state as
`WORK-046 DEFECT (defect-inherited)` because repairing it was
outside W054's authorized scope.

WORK-056 (whose scope IS `developerapi/`) repairs exactly this,
with the frozen boundary contract preserved:

- **imports**: `usage.ledger.UsageLedger`,
  `usage.errors.UsageError`, `allocation.ledger.AllocationLedger`
  — the module allow-list audit (case 28) re-bound with them;
- **usage/billing reads** project the CURRENT transaction-scoped
  W052 model: `_developer_usage_ids` = the usage transactions
  whose cited commercial transaction is developer-owned; the
  usage resource = the canonical `UsageTransaction` projection;
  the billing record = the sealed `BILLABLE_FINAL` fact with the
  canonical `reconciliation_statement` and the W053 allocation
  projection (keyed by the usage transaction id, the current
  model);
- **economic policy** follows the CURRENT terms-derived immutable
  policy version: the request schema carries exactly the
  canonical `register_policy` terms (`label`,
  `adcos_share_bps`, `provider_min_bps`, `provider_max_bps`,
  `rounding_mode`, `currency`, `minor_unit_digits`,
  `effective_from`, `effective_until` — the closed window; the
  current canonical model has no open-ended form), the
  `policy_id` is derived canonically from the terms (the
  developer never chooses it), and identical terms deduplicate
  canonically (the boundary's new-key/identical-terms path
  returns the SAME policy version);
- **the canonical-reason table** (`CANONICAL_REASON_HTTP_STATUS`)
  is the exact union of the three CURRENT frozen vocabularies
  (W051: 20, W052: 23, W053: 27 reasons) with honest HTTP
  classifications; every stale W046-era name is removed; unknown
  canonical reasons still fall back to 400/non-retryable (the
  boundary never guesses);
- **the route table delta** (disclosed): `policy_get` is the
  single-segment `GET /economic-policies/{policy_id}` — the
  current canonical policy identity has no separate version
  coordinate, so the W046-era two-segment
  `/economic-policies/{id}/{version}` shape described an
  addressability that no longer exists. Every other route,
  capability, envelope, idempotency, webhook, pagination, and
  version-registration surface is unchanged (case 01 pins the
  route count at 21 and the 5 mutating routes byte-for-byte).

The usage/billing/policy read flows now compose through the
sanctioned W054 composition-world builders
(`build_usage_evidence_index`,
`build_delivery_evidence`,
`build_allocation_evidence_index`) over public reads only, and
case 26 drives the full honest chain: delivery-plane traffic →
the commercial chain to `DELIVERY_COMPLETED` → delivery-evidence
windows → `DELIVERED` observations citing that evidence → the
explicit `seal_billable` → the commercial `finalize_billable` →
the three-way allocation → journal-first re-composition
(`DeveloperApiService.load` over the same API store) → the API
reads (usage transactions, the sealed billing record, tenant
isolation, usage read-only).

## 3. The discrimination layer (cases 46–56)

The W054/W055 family mandate: a suite that passes the genuine
implementation but would ALSO pass a sabotaged candidate has no
discriminating power. The W056 layer implements eleven
sabotaged candidates — each a battery fixture ONLY, implemented
over public APIs, never shipped, never exported — and proves
each paired vector FAILS the candidate while PASSING the genuine
boundary:

| Case | Category (handoff §Required outcome) | Sabotaged candidate | Detection |
|---|---|---|---|
| 46 | 1 versioned contract | version laundering (silent rewrite to the current version) | retired-version + attribution-disagreement requests fail genuine (400) and are admitted by the candidate (200) |
| 47 | 2 idempotency | per-attempt re-keying (the duplicate re-executes) | duplicate replays byte-identically genuine (1 canonical transaction, replay header) and mints a second transaction through the candidate |
| 48 | 3 scoped credentials | identifier-substitution privilege escalation (full-privilege service credentials swapped in) | scoped POST fails genuine (403 capability-denied, no state) and succeeds through the candidate (200 + state) |
| 49 | 4 environment isolation | the sandbox bridge (production-bound mismatch answered from the sandbox namespace) | production-bound sandbox credential fails genuine (403 environment-mismatch) and succeeds through the bridge |
| 50 | 5 canonical reason codes | the lossy remap (canonical reasons rewritten to a generic boundary reason) | `lifecycle-illegal` survives genuine (422) and is flattened by the candidate (400/invalid-input) |
| 51 | 6 webhook integrity | signature blindness (the comparison skipped) | a tampered payload under a valid envelope fails genuine verification and verifies through the candidate |
| 52 | 6 webhook replay/order | tolerance-blind verifier + memoryless duplicate detector + version-blind order tracker | stale/duplicate/out-of-order each classified genuine and each admitted by its blind candidate |
| 53 | 7 stable retrieval | caller-order pages + forged cursors | canonical order, exact cursor continuation, and forged-cursor rejection genuine; the candidate follows insertion order and accepts the forged cursor |
| 54 | 8 SDK equivalence | request reshaping + response fabrication (`physical_connectivity: true` invented) | SDK request bytes and parsed members exact genuine; the reshaping/fabricating candidates diverge |
| 55 | 9 resource protection | the business limiter (throttle decisions mint canonical transactions) | the throttled request mints nothing genuine and mints a canonical transaction through the candidate |
| 56 | 10 anti-authority | observation-as-command (the consumer submits a canonical mutation per delivered event) | the delivery adds nothing beyond the API mutation genuine and mints an observation-born transaction through the candidate |

## 4. Reproduction

From a fresh checkout of the delivery head:

```
python3 tools/developerapi_selftest.py
```

Result at the delivery head:

```
Result: PASS (56/56 cases passed)
```

(45 inherited W046 cases — all re-bound to the current
authorities — plus the 11 discrimination cases.)

Determinism (the same battery, subprocess-isolated):

```
python3 tools/developerapi_selftest.py            # repeat-run: identical output
PYTHONHASHSEED=0    python3 tools/developerapi_selftest.py
PYTHONHASHSEED=1    python3 tools/developerapi_selftest.py
PYTHONHASHSEED=7919 python3 tools/developerapi_selftest.py
                                                    # byte-identical PASS lines
```

(case 35 pins the golden scenario stream across two in-process
runs; case 36 pins the four hash-seed subprocesses.)

## 5. Sibling battery classification (honest)

| Battery | In CI | At the branch root | At the delivery head | Classification |
|---|---|---|---|---|
| `developerapi_selftest.py` | yes | ImportError (the inherited W046 defect) | **PASS 56/56** | the W056 repair itself |
| `commercial_selftest.py` | no | PASS 38/38 | PASS 38/38 | unchanged |
| `usage_selftest.py` | yes | PASS 49/49 | PASS 49/49 | unchanged |
| `allocation_selftest.py` | yes | PASS 60/60 | PASS 60/60 | unchanged |
| `spec_check.py` | yes (first step) | FAIL 12/16 blocking, 2 advisory, ARCH-08 SKIP | FAIL 12/16 — **byte-identical** | inherited (governance-state ARCH-04/06/07; the same classification the R3 reconciliation recorded; no W056 delta reaches any surface spec_check inspects) |
| `conformance_selftest.py` | yes | FAIL 2/63 (cases 62/63) | FAIL 2/63 | inherited (the post-W055-baseline governance merges; the W056 delta merely adds its own authorized-scope files to case 62's working-tree disclosure list) |
| `composition_selftest.py` | **no** | PASS 55/55 | FAIL 1/55 (case 01) | **disclosed below** |

**The composition pin disclosure**: the W054 composition
battery's case 01 pins the W046 `DEFECT (defect-inherited)`
classification it honestly recorded at its own delivery. The
underlying probe is dynamic (`import developerapi`) and now
honestly reports `AVAILABLE` because the W056 repair — the exact
work this authorization mandates — fixed the import defect. The
one-line pin update lives in
`tools/composition_selftest.py`, which is OUTSIDE the W056
authorized scope, so it is NOT edited here; it is surfaced for
Architect disposition (the follow-up is mechanical: case 01
should expect the W046 probe to classify `AVAILABLE` post-W056,
and the `W046_DEFECT_DETAIL` disclosure in
`composition/authority.py` becomes historical). The battery is
not invoked by CI, and no accepted authority code changes.

No CI success is claimed for the delivery head: the workflow's
first step (`spec_check.py`) fails with the byte-identical
inherited signature, exactly as it does on the branch root and
on current main.

## 6. Structural audits (unchanged and strengthened)

- import discipline (case 28): the family imports ONLY stdlib +
  canonicalization + the clock seam + the three adapted
  commercial-plane surfaces (re-bound to the current module
  layout); zero connectivity/payment/eligibility authority
  imports;
- the cross-authority call surface (case 29): exactly
  `submit_intent` / `hold_reservation` / `register_policy` + the
  public reads;
- SDK authority honesty (case 30) and physical-evidence honesty
  (case 31): unchanged;
- the frozen public API (case 38): 85 exports pinned, unchanged
  by W056 (the boundary surface is not extended);
- the frozen spec surfaces (case 40) and the PR delta shape +
  ancestry (case 41): the W056 authorized paths + the baseline
  ancestry (7ae438d / 4852a016) proven mechanically;
- secret hygiene (case 37): unchanged.

## 7. Honest boundaries

- All W056 evidence is SOFTWARE. Nothing here is OPERATIONAL
  evidence, and nothing can promote or close W040's PHYSICAL
  obligations (EVID-007/EVID-008 remain open, physical,
  W040-owned).
- API success never implies physical connectivity; sandbox
  results are `sandbox-simulation` and are never production
  evidence.
- The developer boundary creates no new canonical authority: the
  API and webhooks remain projections/observations over the
  canonical server state (case 56 proves the observation channel
  cannot mutate it; case 10/30/31 pin the structural side).
- W048 remains accepted-not-restored; W040 remains independently
  in-review; R4 stays parallel.
- No frozen Architecture 1.0 or Protocol 1.0 semantic or
  wire-schema change is part of this delivery; the one
  route-shape delta (the single-segment policy read) is the
  honest consequence of the current canonical policy identity
  and is disclosed in §2.
- No CI success is claimed (§5); the composition pin follow-up
  (§5) awaits Architect disposition and is not silently applied.

## 8. Worker state

`WAITING_FOR_ARCHITECT` at the delivery head. Not self-accepted;
not self-merged; the guarded merge remains Architect-only.
