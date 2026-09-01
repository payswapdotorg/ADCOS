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
