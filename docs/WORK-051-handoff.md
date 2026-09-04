# WORK-051 Implementation Handoff (repository-local)

**Status: ACTIVE — the durable handoff for the WORK-051 implementation
referenced by the active authorization `WORK-051-CORE-001`.**

This is the governance-level handoff on `main`. The implementation-level
handoff (module structure, interfaces, evidence model) will live on the
W051 delivery branch and in its PR body, per the WORK-041/W042
precedent. Nothing in chat is authoritative.

## Authority

- Authorization: `spec/architect/authorizations/WORK-051.yaml` —
  `WORK-051-CORE-001`, `status: active`, baseline
  `fe6e6e35a49cb2113315d0ec1569f7e93a3cf200` (current main at activation,
  the post-PR-#110/#111/#115 mainline reconciled by LEDGER-RECON-007;
  moves only through a formally recorded reconciliation).
- Decision: DEC-0058 (atomic W042 acceptance → W051 activation) —
  `spec/architect/decisions/DEC-0058-work-051-activation.yaml`.
- Architecture basis: ACR-009 — Commercial Connectivity Control Plane
  (accepted by DEC-0050, proposal merged by PR #82); ACR-005 (DEC-0047),
  ACR-006 (DEC-0048), and ACR-007 (DEC-0049) are accepted and bound by
  the contract's dependency section.
- Ready-candidate contract: tracking issue #83 (canonical identity per
  the ACR-011 registered entry in `spec/work-items.md` and
  `docs/roadmap/commercial-dependency-model.md`).
- WORK-042 is accepted-merged (DEC-0057; PR #110 head `708a432`, merge
  `207d70e`, CI run 33444952103 SUCCESS) — the slot transfer is complete
  and the WORK-042-CORE-001 authorization is superseded (DEC-0058, scope
  and provenance preserved in the record).
- WORK-041 is accepted-merged (DEC-0054; PR #107) — NetworkPath
  identities are referenced (never owned) where consumed.
- W051 is the commercial chain head: the frozen registry declares
  `Dependencies: none`; ACR-009 acceptance is the architectural
  precondition (satisfied by DEC-0050), not a Work Item dependency.
- W040 remains an independent physical validation track (in-review, NOT
  accepted; EVID-007/EVID-008 OPEN and W040-owned). W040 physical
  validation findings are advisory input (DEC-0051), not a prerequisite.

## Objective (from the W051 contract, issue #83)

Implement the minimum commercial control-plane core described by ACR-009,
without changing existing identity, session, routing, path, transport, or
packet semantics.

## Scope (from the W051 contract)

Introduce the canonical commercial state model for:

`ConnectivityIntent → OfferSelected → ReservationHeld → SessionAuthorized → PathActive → DeliveryStarted → UsageAccruing → DeliveryCompleted → BillableFinal → SettlementPending → Settled`

Include compensating states/events for cancellation, expiry, path
failure, and non-delivery. The implementation must be append-only,
deterministic, idempotent, and explicitly separate reservation/payment
state from actual delivery.

The core must be able to reference existing logical session IDs,
NetworkPath IDs, and delivery evidence without becoming authoritative
for them.

## Required invariants (from the W051 contract)

1. Payment success never implies delivery.
2. Reservation never implies delivery.
3. Delivery facts cannot be rewritten by later commercial events.
4. Every state transition is attributable and idempotent.
5. Historical records remain immutable; corrections are compensating events.
6. Commerce cannot mutate connectivity/session/path/routing/transport authorities.
7. No payment-provider-specific assumptions leak into the core.

## Acceptance criteria (quoted from the frozen registry entry)

1. The full canonical commercial lifecycle is representable, append-only,
   deterministic, and idempotent, with every state transition
   attributable.
2. Compensating states/events exist for cancellation, expiry, path
   failure, and non-delivery; historical records remain immutable.
3. The core references existing logical session IDs, NetworkPath IDs, and
   delivery evidence without becoming authoritative for them.
4. Payment success never implies delivery; reservation never implies
   delivery; delivery facts cannot be rewritten by later commercial
   events.
5. Commerce cannot mutate connectivity/session/path/routing/transport
   authorities; no payment-provider-specific assumptions leak into the
   core.

## Explicit non-scope (from the W051 contract)

Payment rails, custody, payout execution, KYC/KYB, jurisdiction rules,
marketplace discovery, and developer SDKs — later authorized Work Items.
Frozen architecture modification. Implementation before ACR-009
acceptance (satisfied) and a repository-local authorization (this one).

## Verification target (from the W051 contract)

Deterministic unit/integration coverage for the full lifecycle,
cancellation/expiry, non-delivery, duplicate/out-of-order event handling,
immutable-history guarantees, and authority-boundary checks.

## Downstream consumers (advisory, not scope)

The canonical chain per the accepted registry: WORK-052 UsageLedger
(hard dep on W051), WORK-053 EconomicAllocation (W051+W052), WORK-044
through WORK-049 (the provider/payment/settlement/experience chain, all
hard-gated on W051 directly or transitively), and WORK-048 (requires
W041+W042+W051 including the CommercialCore Lease authority where
consumed). None of these is authorized by this handoff; each awaits its
own repository-local authorization.

## Physical evidence boundary

No PHYSICAL PASS claim is made or required for W051 implementation (the
commercial core is a pure software control-plane model). EVID-007
(PARTIAL) and EVID-008 (NOT-TESTABLE) remain OPEN and W040-owned; W040
stays in-review and NOT accepted; anti-promotion discipline is
preserved.

## Next implementer's first steps

1. Read `spec/mission.md`, `spec/architect/current-state.md`,
   `spec/architect/authority-order.md`, `spec/architect/execution-state.yaml`,
   `spec/architect/execution-ledger.yaml`, this handoff, and the
   authorization record.
2. Read ACR-009 (`spec/acr/ACR-009-commercial-connectivity-control-plane.md`)
   and the canonical model
   (`docs/roadmap/commercial-dependency-model.md`).
3. Study the accepted precedents for the discipline this Work Item must
   match: `networkpath/` + `tools/networkpath_selftest.py` (W041) and
   `platform/` + `tools/platform_selftest.py` (W042) — deterministic
   batteries, honest evidence, append-only durable state, frozen-API
   discipline, authority-boundary AST audits.
4. Cut the implementation branch from a main carrying this exact
   authorization record (byte-identical inheritance; ARCH-08 provenance
   is enforced on the PR).
5. Deliver inside the authorized scope only:
   `commercial/`, `tools/commercial_selftest.py`,
   `docs/WORK-051-handoff.md` (implementation-level append),
   `docs/WORK-051-evidence.md`.

---

# Implementation-level handoff (delivered on the W051 branch)

**Appended by the W051 implementation PR under `WORK-051-CORE-001`
(the W041/W042 precedent: the governance-level handoff above stays on
main; this section records what was actually built).**

## Package / API surface

`commercial/` — 8 modules, frozen 52-name public API
(`commercial/__init__.py` `__all__`, pinned by battery case_29):

- **error model**: `CommercialError` + `CommercialReasonCode` (20
  typed reasons: input/command integrity, duplicates and conflicts,
  lifecycle discipline, expiry, compensating gates, settlement
  integrity, payment separation, reference integrity, journal
  corruption, store failure, instant validation).
- **value model** (`model.py`): `CommercialState` (11 canonical states
  + 4 compensating terminals), `CommercialAction` (15 actions),
  `LIFECYCLE_TRANSITIONS` (25 edges, 2 state-preserving self-edges:
  transaction creation and subsequent usage accruals),
  `CommercialCommand` (idempotency-keyed input with content-derived
  digest), `CommercialEvent` (append-only journaled fact with
  content-derived id and full attribution),
  `CommercialTransaction` (the fold projection), and the
  `derive_*`/digest helpers (WORK-003 canonical JSON,
  `sha256:` fingerprints).
- **reference boundary** (`references.py`): `ReferenceFamily`
  (session / network-path / delivery-evidence / usage / settlement /
  payment), `Reference` (id + family + provenance, DATA only),
  `ReferenceIndex` (immutable caller-built snapshot from public
  authority reads), `resolve_references` (fail-closed resolvability;
  the index is the family authority).
- **admission rules** (`validation.py`): `ACTION_FAMILY_RULES` (the
  payment/delivery separation table), payload shape validation,
  reservation-deadline gates, compensating-state gates, and
  settlement integrity (settlement-family citation + intact
  delivery-evidence chain).
- **journal** (`journal.py`): ONE atomic
  (admitted-command + resulting-event) record per executed command;
  hash chain over (sequence, content, prev); command digest
  verification; duplicate command ids rejected at load; canonical-JSON
  lines; `CommercialStore` seam (`MemoryCommercialStore`,
  `FileCommercialStore` — the only filesystem-write site,
  append-binary); persist-then-ack.
- **lifecycle** (`lifecycle.py`): `CommercialCore` (fresh construction
  over an EMPTY store; `load` = journal-first recovery), 15 typed
  command methods, `CommandOutcome` (`appended`/`duplicate`),
  `apply_record`/`fold_state` (the SINGLE state-derivation function
  shared by the live manager and replay), `verify_integrity`,
  `digest_stream`.
- **digests** (`digest.py`): state/ledger/index digests and
  `assemble_digest_stream` (the canonical evidence document).

## Lifecycle table

See `commercial/model.py` `LIFECYCLE_TRANSITIONS` and the battery's
case_02 (exact-table pin). Terminal states: `SETTLED`, `CANCELLED`,
`EXPIRED`, `PATH_FAILED`, `NON_DELIVERED` (no outgoing edges —
historical commercial facts are immutable; corrections are
compensating records).

## Reference boundaries

The core may reference (never own or mutate): logical session ids
(WORK-012), NetworkPath ids (W041), delivery evidence (delivery
plane), usage references (the W052 input plane), settlement
confirmations, and payment observations (external DATA). The
`ReferenceIndex` is built by the caller from public authority reads
and injected; no authority object, client, or private accessor ever
crosses the boundary (battery cases 27/28/31).

## Persistence model

Append-only `commercial-journal.jsonl` (one canonical-JSON line per
admitted command+event record, hash-chained, content-derived ids);
the command idempotency ledger is journaled with each record (durable
across restart); `MemoryCommercialStore` for deterministic
verification; fresh construction requires an empty store.

## Replay / recovery behavior

`CommercialCore.load(store, clock, references)`: load -> verify the
full chain (ids, sequence, digests, duplicate command ids) -> fold
with the single apply function -> resume. Live state == replayed state
byte-identical by construction; redelivered commands are durable
no-ops; the reference index is injected fresh at load (future commands
re-validate citations against the CURRENT index — evicted delivery
citations fail settlement, never silently). A store failure leaves no
phantom state (persist-then-ack).

## Extension points for W052 / W053 (advisory only — NOT authorized)

- **W052 UsageLedger** (hard dep on W051): the `usage` reference
  family and the state-preserving `accrue_usage` journal records are
  the citation seam; metering itself stays outside W051.
- **W053 EconomicAllocation** (W051+W052): allocation policy attaches
  at `BILLABLE_FINAL`/`INITIATE_SETTLEMENT` (the commercial decision
  points); the payload-DATA discipline (canonical JSON, no floats)
  keeps economic quantities representable without provider leakage.
- The compensating-record discipline extends (refund/dispute/
  chargeback/reversal per ACR-009) as ADDITIONAL compensating records
  on the same journal — settled history is never rewritten.

## Explicit non-scope (W044-W050, W052, W053)

Payment rails, custody, payout execution, KYC/KYB, jurisdiction rules,
marketplace discovery, developer SDKs, usage metering, allocation
policy, and any second authority remain OUTSIDE this delivery and
require their own repository-local authorizations. Nothing in this PR
authorizes, activates, or pre-implements them.

## Physical evidence boundary

No PHYSICAL claim. EVID-007/EVID-008 remain OPEN and W040-owned; W040
stays in-review and NOT accepted.

---

# Conformance-completion delivery (the W050 merge-isolation era)

Appended by the second WORK-051-CORE-001 delivery session (the
sections above are the PR #117 implementation-level handoff, preserved
unchanged). Context: the Architect's W050 merge-isolation directive
merged the isolated WORK-050 delivery onto the authoritative mainline
(`fc3ace9` + the four reconstructed W050 stages = main
`815f4febbc64d55d3576386e65adaa6244c4f7cb`); WORK-051 execution
resumed from that exact SHA under the authorization present on it.

## What this delivery is

Reconnaissance against the post-W050 mainline found the canonical
CommercialCore implementation already merged there (PR #117, in the
`fc3ace9` ancestry) and conforming to the frozen contract. This
delivery completes the permanent conformance battery around the
directive's fourteen named categories and corrects the one real gap
the new vectors exposed:

1. **The out-of-order replay correction** (fail-closed only):
   `apply_record` verifies the walk linkage at replay (an event's
   declared `from_state` must be the folded current state; the
   creation record must be the `CONNECTIVITY_INTENT` self-edge) and
   `CommercialEvent` enforces action-target coherence at the model
   gate (an event claiming action A must land in
   `ACTION_TARGET_STATE[A]`). Before the correction, a fully
   recomputed, table-legal, chain-valid record whose declared
   predecessor did not connect to the folded walk was accepted at
   `CommercialCore.load` (empirically demonstrated; see
   docs/WORK-051-evidence.md §15.2). Honest journals are contiguous
   walks by construction and are unaffected; the golden digest
   stream is byte-identical.
2. **Three named battery vectors** making the three implicitly
   covered directive categories explicit: case_36 (out-of-order
   events at admission, the model gate, and replay), case_37
   (delivery immutability: no compensating action after
   DELIVERY_COMPLETED, no evidence re-pointing, delivery events
   survive byte-identically through settlement), case_38
   (fresh-world independence: interleaved coexisting worlds
   reproduce their isolated baselines byte-for-byte). The battery is
   now 38 cases; the full fourteen-category mapping is in the
   evidence record §15.3.

## Delivery facts

- Branch: `work-051-conformance-completion`, cut from main
  `815f4febbc64d55d3576386e65adaa6244c4f7cb` (the post-W050 mainline
  carrying the WORK-051-CORE-001 authorization byte-identically).
- Scope: `commercial/lifecycle.py`, `commercial/model.py`,
  `tools/commercial_selftest.py`, `docs/WORK-051-evidence.md`,
  `docs/WORK-051-handoff.md` — exactly the WORK-051-CORE-001 scope;
  no CI wiring change (the battery step is already wired); no
  spec/ change (ARCH-08/case_34 enforce).
- Verification: battery 38/38; two consecutive runs byte-identical;
  PYTHONHASHSEED=0/1/7919/unset byte-identical; spec_check 17/17;
  provenance PASS; the W050 platformcaps battery 76/76 unchanged.
- No governance change: the WORK-051 acceptance transition (DEC
  record, ledger update, supersession, next activation) remains the
  Architect's; this delivery awaits Architect acceptance.

## Next implementer's first steps (unchanged in substance)

Read the authorization record and current-state; re-run
`python3 tools/commercial_selftest.py` and `python3
tools/spec_check.py` on the exact delivery head; the acceptance
review should check the fourteen-category mapping (evidence §15.3)
against the vectors, the §15.2 correction against the original PR
#117 behavior, and the honest-disclosure conditions (evidence
§15.4/§15.5).
