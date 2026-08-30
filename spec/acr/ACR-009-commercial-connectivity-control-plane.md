# ACR-009: Commercial Connectivity Control Plane

## Status

ACCEPTED — Architect decision DEC-0050; proposal merged by PR #82.

## Motivation

Roadmap #71 and architecture issues #72–#80 define a connectivity marketplace in which developers can build applications that let providers sell spare connectivity capacity while ADCOS supplies connectivity orchestration, metering, commercial state, and settlement primitives.

The design must preserve ADCOS's permanent mission and the accepted authority boundaries established by ACR-005, ACR-006, and ACR-007.

## Proposed architecture

ADCOS gains a distinct commercial control-plane model with these canonical objects:

- `ConnectivityIntent`
- `Offer`
- `Reservation`
- `Lease`
- `CommercialTransaction`
- `UsageRecord`
- `Allocation`
- `PricingPolicyVersion`
- `SettlementPlan`
- `LedgerEntry`
- `Refund`
- `Dispute`
- `Chargeback`
- `Reversal`
- `Payout`

The canonical economic lifecycle is:

`CONNECTIVITY_INTENT → OFFER_SELECTED → RESERVATION_HELD → SESSION_AUTHORIZED → PATH_ACTIVE → DELIVERY_STARTED → USAGE_ACCRUING → DELIVERY_COMPLETED → BILLABLE_FINAL → SETTLEMENT_PENDING → SETTLED`

Compensating transitions/events cover cancellation, expiry, path failure, non-delivery, refund, dispute, chargeback, reversal, failed payout, and reconciliation correction.

## Authority boundaries

1. Connectivity/session/path/routing/transport authorities remain authoritative for connectivity.
2. Commercial state references logical session IDs, NetworkPath IDs, and delivery evidence but cannot mutate their semantics.
3. Payment providers remain responsible for payment authorization, payment rails, and regulated funds movement.
4. ADCOS owns canonical commercial intent, usage correlation, allocation policy, settlement state, and audit lineage around provider events.
5. Commerce never becomes an identity, routing, session, path, or transport authority.

## Usage integrity

Usage originates only from an already-authorized delivery path plus accepted traffic evidence.

Reservation, payment authorization, or payment capture can never create usage.

Usage records distinguish reserved, attempted, delivered, billable, disputed, refunded, and reversed quantities without rewriting historical delivery facts.

Delayed, duplicated, or out-of-order usage observations are reconciled through idempotent append-only records.

## Economic model

Gross proceeds may be allocated among:

- connectivity provider;
- application/developer;
- ADCOS;
- payment/processing costs;
- reserves;
- refunds/disputes and other explicit adjustments.

The developer selects the provider/application allocation within immutable platform constraints. Each transaction records the pricing/economic policy version used to calculate the allocation.

Settled transactions cannot be rewritten. Policy changes affect future transactions only.

Liability for refunds, disputes, chargebacks, failed payouts, reserves, currency conversion, and provider non-delivery is explicit and may vary by payment-provider configuration and jurisdiction.

## Provider abstraction

The architecture must remain payment-provider agnostic. A provider adapter translates ADCOS commercial commands/events into provider-specific payment operations and translates provider webhooks/events back into ADCOS ledger state.

Payment movement must remain outside the ADCOS packet/data plane.

## Developer experience

The public developer surface should expose simple primitives for:

- onboarding a connectivity provider;
- publishing capacity;
- creating an offer;
- setting pricing;
- choosing provider/application revenue shares;
- creating buyer connectivity intents;
- observing usage and transaction state;
- receiving webhooks;
- reconciling payouts and disputes.

Complex immutable records remain behind these simple APIs.

## Trust and jurisdiction

Connectivity sharing may require telecommunications authorization, internet-service authorization, or other legal permission depending on jurisdiction and business model. Commercial eligibility must therefore be jurisdiction-aware.

Payment eligibility, KYC/KYB, payout capability, sanctions/fraud controls, reserve requirements, taxes, and consumer-protection rules must likewise be provider- and jurisdiction-aware.

The platform must never assume that a provider has unrestricted legal authority to resell or share network access.

## Required invariants

1. Payment success does not imply connectivity delivery success.
2. Reservation does not imply delivery.
3. Delivery does not imply billable finality until usage rules are satisfied.
4. Delivery does not imply settlement finality.
5. Failed payout does not alter delivery facts.
6. Every monetary mutation is append-only, idempotent, attributable, and reconcilable.
7. Refunds/disputes/reversals are compensating events, not history rewrites.
8. Developer/provider/ADCOS allocations are deterministic from a recorded policy version.
9. Commerce can suspend commercial eligibility or payout but cannot directly mutate connectivity routing/session/path/transport state.
10. Historical transaction, usage, and delivery evidence remains immutable.

## Dependencies

- ACR-005 — First-Class Network Path and Platform Boundary
- ACR-006 — Event-Driven Platform Integration and Journal-First Recovery
- ACR-007 — Mission-Immutable, Architecture-Evolvable Governance
- Roadmap #71 and issues #72–#80

## Compatibility and migration

This ACR is an accepted architecture layer and does not itself alter existing wire semantics. Any implementation must introduce the commercial control plane as an additional authority domain that references, but does not redefine, existing connectivity authorities.

Concrete schema/API changes, ledger schemas, payment adapters, and developer interfaces require separate authorized Work Items.

## Research grounding

The design reflects current marketplace payment patterns where platforms may use distinct charge/transfer flows and must explicitly account for refunds, disputes, and connected-account responsibilities. Stripe's marketplace documentation is treated only as a design reference; provider and jurisdiction behavior must remain abstracted.

Ghana's current NCA materials classify Internet/Public Data Service Provision and Internet Hotspot as authorization categories, and the Bank of Ghana continues to maintain licensing frameworks for payment service providers. These facts reinforce the need for jurisdiction-aware connectivity and payment eligibility rather than universal assumptions.

## Architect decision

ACCEPTED — DEC-0050. User-directed acceptance was recorded on PR #82 at 2026-08-30T18:09:03Z; the durable repository decision record is `spec/architect/decisions/DEC-0050-acr-009-acceptance.yaml`.

ACR-009 acceptance does not itself authorize implementation. Concrete commercial implementation remains subject to separately authorized Work Items.

## Learning and revision

This architecture is revisable under ACR-007. Implementation and production experience must be recorded in `spec/experience/` and may motivate superseding ACRs without rewriting historical records.
