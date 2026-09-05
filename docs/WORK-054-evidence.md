# WORK-054 Evidence Record (System Composition Conformance)

**Status: delivered for review under authorization
`WORK-054-CORE-001` (activation DEC-0085; live-baseline
reconciliation DEC-0086; implementation baseline
`461d1482180222f4b63f780d6d9ea1d54c49d643`). SOFTWARE-class
evidence only. NO PHYSICAL claim is made (the composition layer
is a pure software conformance/orchestration model; EVID-007
PARTIAL and EVID-008 NOT-TESTABLE remain OPEN and W040-owned;
W040 stays in-review and NOT accepted). The strict production
composition verdict on the current mainline is
`BLOCKED_MISSING_AUTHORITY` (WORK-048 accepted-not-restored):
the absence is detected and fails closed and is NEVER counted as
a passing production composition.**

## 1. Authorization and provenance

- Authorization: `spec/architect/authorizations/WORK-054.yaml` —
  `WORK-054-CORE-001`, `status: active`, `authorized: true`,
  `authorization_decision: DEC-0086`, `baseline_sha:
  461d1482180222f4b63f780d6d9ea1d54c49d643`, inherited
  **byte-identically from main** (unmodified; the authorization
  record is durable provenance and is never touched by this PR —
  battery case_50 pins it byte-identical to `origin/main`).
- Activation decision: DEC-0085 (`spec/architect/decisions/
  DEC-0085-r2-work-054-activation.yaml`) — the R2 activation of
  WORK-054 with the sole implementation authorization
  `WORK-054-CORE-001` from the R1 snapshot `13bfbda5`.
- Baseline reconciliation: DEC-0086
  (`DEC-0086-r2-live-baseline-reconciliation.yaml`) — `461d148`
  is "the only permitted WORK-054 worker branch point"; the
  worker branch is cut exactly from it (battery case_51 verifies
  the baseline is an ancestor of the delivery head).
- Delivery: branch `work-054-system-composition-conformance`
  (the name the authorization record specifies), PR against main
  (this PR; the exact head SHA is in the PR body).
- Historical W054 material NOT used: the earlier lineage's
  implementation PR (#4, head `f6824cc0`), its hardening/
  acceptance/repair governance PRs (#5–#7), and every historical
  W054 branch were treated as forbidden replay sources. This
  implementation is entirely fresh code written against the
  CURRENT public authority surfaces; the remote
  `work-054-system-composition-conformance` branch was reset to
  the clean authorized baseline by the Architect before this
  delivery (non-forced push on top of `461d148`).

## 2. Delivered scope (exactly the authorized scope)

| Path | Content |
|---|---|
| `composition/` | The System Composition Conformance package (6 modules) |
| `tools/composition_selftest.py` | The deterministic battery (55 cases) |
| `docs/WORK-054-handoff.md` | The Architect directive preserved verbatim + the implementation-level handoff append (this PR) |
| `docs/WORK-054-evidence.md` | This evidence record |

NO other path is modified (battery case_51 verifies the delta
lies exactly within this scope when the `origin/main` ref is
available; the CI provenance step enforces the same rule on the
PR). `spec/architect/` is untouched (case_50: the frozen
architecture/lock/mission/governance/workflow/backlog/schema
files and the entire Architect package byte-identical to
`origin/main`). NO CI wiring was added: the authorized scope does
not include `.github/`, so the composition battery is
standalone deterministic evidence (re-runnable with
`python3 tools/composition_selftest.py`; the full 55/55 output
is recorded in §10 and its digest stream in §8).

Package layout:

```
composition/
  __init__.py       frozen 36-name public API (battery case_53 pin)
  authority.py      the authority availability registry:
                    dynamic importlib probes over every composed
                    authority; WORK-048 ABSENT (fail-closed) and
                    WORK-046 DEFECT (inherited, disclosed) are
                    recorded honestly, never masked
  chain.py          the frozen 13-edge chain model (14 stages,
                    owning authority + SOFTWARE evidence class per
                    edge), the edge-outcome/verdict vocabularies,
                    and the deterministic trace document
  evidence.py       the evidence discipline: SOFTWARE class only;
                    PHYSICAL/EXTERNAL claims fail closed
                    (SOFTWARE_EVIDENCE_CANNOT_CLOSE_PHYSICAL);
                    read-only proof that EVID-007/EVID-008 stay
                    open and W040-owned
  world.py          the composed conformance world: every member
                    an EXISTING authority built through its own
                    public constructor over injected seams; the
                    caller-side public-read snapshot builders
                    (W051 ReferenceIndex, W052 UsageEvidenceIndex,
                    W053 AllocationEvidenceIndex, W044
                    CommercialSnapshot, delivery evidence-window
                    records from the W042 journal)
  orchestrator.py   run_full_chain (the STRICT production
                    composition, fail-closed at W048),
                    run_available_segments (the honest segment
                    conformance with the traveling disclaimer),
                    and compose_scenario_stream (the byte-stable
                    deterministic digest stream)
```

## 3. The strict production-composition chain

The frozen contract chain
`intent -> offer -> eligibility -> reservation/lease -> candidate
selection -> NetworkPath validation -> containment -> session ->
delivered traffic -> usage -> BILLABLE_FINAL -> allocation ->
external payment reference -> reconciliation`
is driven edge by edge, each edge by its OWNING authority through
its public surface (battery cases 07–10; every edge outcome cites
authority-sourced identities/digests only):

| Edge | Owning authority | Outcome |
|---|---|---|
| intent -> offer | WORK-009/WORK-047 | ADVANCED (normalized intent digest; 2 ranked candidates) |
| offer -> eligibility | WORK-045 | ADVANCED (decision `eligible`, zero denial codes) |
| eligibility -> reservation/lease | WORK-051 | ADVANCED (RESERVATION_HELD; journal digest cited) |
| reservation/lease -> candidate selection | WORK-047 | ADVANCED (proposal `proposed`; nothing validated/bound/activated) |
| candidate selection -> NetworkPath validation | WORK-041 | ADVANCED (the sanctioned W047 handoff seam drives discover/validate/bind/probe/activate; path ACTIVE) |
| NetworkPath validation -> containment | WORK-048 | **FAIL_CLOSED — `w048-runtime-absent-fail-closed`** |
| containment -> session (and the 6 further edges) | — | NOT_ENTERED (upstream-blocked; never skipped, never guessed) |

**Verdict: `BLOCKED_MISSING_AUTHORITY`, blocked at containment,
missing authority WORK-048, `production_composition=False`.** The
verdict vocabulary has exactly one value (there is deliberately
NO verdict form that reports a passing production composition
while a required authority is absent), so the trace can never
promote the W048 absence into a success claim. Chain trace
digest:
`sha256:23bf4c98a511238a23db6baaf6d9fded57662b86e5730c6285293427f8f2ba9e`.

## 4. Segment conformance (the available links)

Every AVAILABLE link downstream of the blocked edge is exercised
end to end through the existing authorities' public boundaries,
on the SAME commercial transaction, labeled segment-conformance
(battery cases 11–18; the disclaimer travels with the report):

- **session** — commercial SESSION_AUTHORIZED + PATH_ACTIVE
  through the W047 record seam (which PROVES the W041 ACTIVE
  state via the machinery's own public reads first), plus a
  genuine W012 logical session created through the real W011
  `RoutingEngine` and W010 `PolicyDecision`.
- **delivered traffic** — the delivery evidence-window records
  (210 + 150 bytes) derived from the W042 platform journal's
  public reads; the commercial core records delivery against
  them (DELIVERY_COMPLETED).
- **usage** — the W052 ledger admits the delivered observations
  (each citing the authoritative evidence) plus one DATA-only
  reserved observation.
- **BILLABLE_FINAL** — the explicit seal: 360 delivered bytes x 3
  micros = 1080 micros (integer arithmetic; the 500 reserved
  bytes stay non-billable DATA); the commercial core records
  billable finality.
- **allocation** — the W053 immutable three-way split
  (adcos 162, provider 459, developer 459; conservation exact)
  and the settlement acknowledgement citing the external
  settlement reference.
- **external payment reference** — the W044 boundary creates,
  authorizes, and captures the intent (1080 micros) citing the
  W051/W052 public snapshots, and emits + transfers the payout
  from the finalized W053 allocation citation.
- **reconciliation** — 5 provider callbacks ingested as
  OBSERVATIONS (no auto-fold), the one provider-ahead transfer
  observation folded explicitly exactly once, and the report
  classifying both subjects `matched` without rewriting any
  canonical state.

Segment report digest:
`sha256:b57bc14a78163b5a1faef4aaedeeffbb61ad78f175b1605481af1f3497f9e6a9` (the byte-stable fingerprint of
the full composed run).

## 5. The Seven mandatory negative proofs

Every proof is mechanical (battery case_55 registers the
statement -> case mapping):

1. **Payment success cannot create connectivity** (case_19). A
   CAPTURED payment intent is refused as delivery justification
   (`payment-not-delivery` on `start_delivery` and
   `accrue_usage`); the payment observation is refused by the
   W052 kind table (`payment-not-delivery`); and no connectivity
   state advanced (the commercial state and the reservation were
   unchanged).
2. **Reservation success cannot imply reachability** (case_20).
   A usage observation citing the reserved transaction is
   refused (`reservation-not-usage`); delivery without evidence
   is refused (`command-invalid`); and the W041 machinery (not
   the reservation) is the only path-activation authority
   (`lifecycle-illegal` on an unbound candidate).
3. **Marketplace discovery cannot activate a path** (case_21).
   The selection proposal stays `proposed` (a PROPOSAL: nothing
   validated, bound, or activated); a DISCOVERED path cannot be
   activated; and a proposal id is not a NetworkPath reference
   (`reference-unknown` at family resolution).
4. **W050 capability declaration cannot enforce containment**
   (case_22). The registry declares `supported` (a SOFTWARE
   compatibility statement), yet the containment edge still
   fails closed: `prepared -> active` remains illegal in the
   frozen vocabulary (verify is runtime-only) and no containment
   runtime exists to consume the declaration.
5. **W049 client state cannot become canonical state**
   (case_23). Sharing reads fail closed
   (`client-stale-state`; never fabricated); the provider client
   refuses construction without the W048 runtime
   (`client-invalid-input`); a future-dated local ACTIVE
   observation cannot displace canonical truth in the projection
   cache (authority-class dominance); and client subject ids are
   not authority references (`reference-unknown`).
6. **API/webhook observation cannot become a second source of
   truth** (case_24). Verified callbacks stay OBSERVATIONS
   (canonical state folds only through the explicit
   exactly-once `apply_observation` command); exact redelivery
   is an idempotent no-op (no journal growth); payment/provider
   observations are refused by the W052 kind table; and the W046
   webhook boundary itself is the DISCLOSED inherited defect
   (never bypassed).
7. **Software evidence cannot close physical evidence**
   (case_25). PHYSICAL and EXTERNAL evidence claims fail closed
   (`SOFTWARE_EVIDENCE_CANNOT_CLOSE_PHYSICAL` / class
   forbidden); EVID-007 stays PARTIAL and EVID-008
   NOT-TESTABLE, both WORK-0040-owned PHYSICAL obligations in
   the durable projection; every composition record is SOFTWARE
   class.

## 6. The W048 fail-closed proof (the headline)

Battery case_02, case_09, case_10, case_30, and case_23 prove,
structurally and at every boundary:

- **Detection**: no `sharing/` package exists; `containment/` is
  a PEP-420 namespace package carrying ONLY the frozen ACR-012
  vocabulary (`state.py` — no `__init__.py`, no runtime module,
  no `CapabilityMatrix`/`ContainmentAuthority` names); no
  `tools/sharing_selftest.py`; no `docs/WORK-048-evidence.md`;
  the roadmap's own restoration note records
  `accepted-not-restored`.
- **Fail-closed behavior**: the strict chain's containment edge
  records the typed `w048-runtime-absent-fail-closed` reason and
  every downstream edge is NOT_ENTERED; the W049 client's
  sharing/consent reads raise `client-stale-state` ("UNKNOWN;
  never fabricated"); the W049 provider client refuses
  construction without the sharing runtime; the W048-era
  client battery import failure (it wants the absent
  `containment.CapabilityMatrix` and the absent `sharing`
  module) is the structural evidence that provider-mode
  composition cannot be driven.
- **No substitution**: the composition package imports no
  `sharing`, defines no containment runtime, no boundary store,
  no sharing session/consent classes (case_45/case_46 audits);
  the W050 declaration registry is consumed as the DECLARATION
  surface it is (case_22: `supported` never enforces).
- **No downgrade**: the verdict stays BLOCKED; the segment
  conformance is explicitly labeled NOT a production composition
  (case_18 pins the disclaimer).

## 7. The WORK-046 inherited-defect disclosure

Battery case_03: the restored W046 artifacts (the Developer API/
SDK/Webhook platform) fail to import on the current mainline —
`developerapi.*` cross-imports `usage.errors.UsageLedgerError`,
which the evolved W052 usage surface no longer defines. This is
an INHERITED restoration defect, outside the authorized WORK-054
scope: it is detected and disclosed in the authority registry
(`defect-inherited` with the exact stale symbol), never repaired
(Do not repair inherited defects outside the Work Item), and
never silently bypassed (composition never statically imports
`developerapi`; the API/webhook observation classification
negatives are proven through the RECEIVING authorities' public
boundaries — the W052 kind table, the W044 callback observation
fold, and the W053 reference kinds — which exist and are
importable). The four restored batteries that fail at import
(payment/eligibility/developerapi/client) fail on the base
mainline identically and are NOT modified by this PR.

## 8. Determinism, replay, and recovery evidence

- **Repeated-run byte stability** (case_41): two fully fresh
  composed runs are byte-identical across all 33 scenario-stream
  entries.
- **PYTHONHASHSEED invariance** (case_42/43): subprocess runs
  under seeds 0, 1, 7919, and UNSET reproduce the baseline
  stream byte for byte.
- **Idempotency** (case_38): replaying the full command sequence
  across W051/W052/W053/W044 is entirely `duplicate` no-ops; all
  four authority journal digests are byte-identical.
- **Journal-first recovery** (case_39): `CommercialCore.load`,
  `UsageLedger.load`, `AllocationLedger.load`, and
  `SettlementGateway.load` from the same stores reproduce
  byte-identical journal digests, verify integrity/replay, and
  resume the exact canonical state.
- **Platform checkpoint/recovery** (case_40): the W042 platform
  integrator checkpointed the session bindings and recovered
  journal-first (tail sequence 5, 4 fresh events, 4
  changed/appeared-during-downtime divergences classified, the
  lost session recorded, journal digest preserved).
- **Digest convention** (case_44): every composition digest is
  `sha256:` + hex over the WORK-003 canonical JSON form; floats
  fail closed inside the canonicalization itself.

Scenario-stream digest (the whole-run fingerprint; sha256 over
the sorted `key=value` stream entries joined with `|`):
`sha256:85180d65194da04c8a7a6acce1cf73747dd41af2c71b9c2a61d2a090d6c5f3e9`.
The `--determinism-stream` mode prints the same 33 entries one
per line (byte-identical across the delivery branch and the PR
merge context; the piped-line digest is
`46a379b7a1259fb1e3f229bcc878860fe6c2f789cbaf842e0d5228dc3b1d98d2`).

## 9. Authority ownership and import/dependency audit

- **Import audit** (case_45): `composition/` imports only the
  standard library, the WORK-003 canonicalization, the WORK-033
  clock seam, and the composed authority families of the WORK-054
  authority-input table (intent, marketplace, eligibility,
  commercial, networkpath, platform.journal/lifecycle/
  integration, sessions, usage, allocation, payment, client,
  platformcaps, containment.state, plus the W012-mandated
  W011/W010/W008/W007 fixtures). NO `sharing`, NO `developerapi`,
  no out-of-scope family.
- **No second authority** (case_46): `composition/` defines and
  subclasses NO authority class, defines no
  store/journal/ledger/gateway/manager class, and touches no
  filesystem — it is strictly a conformance/evidence layer; the
  cross-authority inputs are immutable caller-built snapshots
  derived from PUBLIC reads only.
- **Vendor neutrality** (case_47): no vendor/technology tokens
  in the composition family (adapter-boundary discipline: no
  5G/Wi-Fi/Ethernet/satellite/provider implementation becomes a
  core branching dependency).
- **Nondeterminism scan** (case_48): no wall-clock, entropy, or
  uuid surface (WORK-033 StepClock only).
- **Private-access scan** (case_49): no other family's private
  members are accessed (public boundaries only).
- **Chain ownership** (case_07): all 13 frozen edges carry the
  contract's owning authority and SOFTWARE evidence class across
  the 14 ordered stages.

## 10. The failure matrix (adversarial coverage)

| Failure | Case | The fail-closed behavior proven |
|---|---|---|
| denied eligibility | 26 | suspended provider denied (`provider-suspended`); chain blocked at eligibility; NO reservation created |
| failed reservation | 27 | hold without a selected offer refused (`lifecycle-illegal`); nothing mutated |
| unreachable candidate | 28 | distance-constrained discovery excludes all; selection fails closed (`marketplace-selection-empty`) |
| failed NetworkPath validation | 29 | link-down candidate rejected (`validation-rejected`/`link-down`); stays DISCOVERED; the ACTIVE path is undisturbed |
| unavailable containment | 30 | the W048 headline (see §6) |
| session failure | 31 | W012 refuses creation from a deny PolicyDecision (`policy-binding-mismatch`) |
| absent delivery evidence | 32 | DELIVERED observation without evidence refused; `start_delivery` without evidence refused (`command-invalid`) |
| non-billable usage | 33 | reserved/attempted DATA only: sealed statement 0/0 with the classes separated |
| allocation rejection | 34 | non-final citation refused (`usage-not-final`); out-of-policy share refused (`split-out-of-bounds`) |
| payment-provider divergence | 35 | provider REFUNDED vs gateway AUTHORIZED classified `provider-ahead` without rewriting state; orphan callback stays divergence evidence, never an intent |
| duplicate observations | 36 | usage/commercial/callback duplicates are idempotent no-ops (no journal growth) |
| out-of-order observations | 37 | out-of-bounds window refused (`window-invalid`); over-quantity refused (`quantity-exceeded`); already-covered observation fold refused (`observation-conflict`) |

## 11. Physical evidence separation

The composition layer mints SOFTWARE evidence only (case_25):
the evidence classifier fails closed on any PHYSICAL or EXTERNAL
claim; the W040 physical obligations EVID-007 (PARTIAL) and
EVID-008 (NOT-TESTABLE) remain open and W040-owned in the
durable evidence-obligations projection (read-only check); no
composition artifact writes to `spec/`; W040, EVID-007, and
EVID-008 are untouched by this PR.

## 12. Honest battery status

`python3 tools/composition_selftest.py` — **Result: PASS
(55/55 cases passed)** on the delivery head (the exact head SHA
is in the PR body), with the `--determinism-stream` mode
reproducing the byte-identical stream. The battery is NOT
CI-wired (the authorized scope does not include `.github/`); it
is standalone deterministic evidence, and every claim in this
document is mechanically backed by a numbered case.

## 13. Battery case index

| Group | Cases |
|---|---|
| Authority availability | 01–06 |
| Strict full chain | 07–10 |
| Segment conformance | 11–18 |
| Seven negative proofs | 19–25 |
| Failure matrix | 26–37 |
| Replay/recovery | 38–40 |
| Determinism | 41–44 |
| Audits | 45–55 |
