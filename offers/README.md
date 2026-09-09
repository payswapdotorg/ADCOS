# ADCOS Offers Package — M003 (R7-CORE-001 child)

## Status

**ACTIVE — Offers and Provider Capability Exchange**

The provider-domain offer model of Architecture 1.1: capability
advertisements, offers, validity, commitments and provenance (LOCK-118),
delivered as per-provider domain objects that REFERENCE the canonical
`contracts/` domain (M002, DEC-0102) — never re-implementing or
duplicating contract semantics (LOCK-101).

**The central boundary (enforced throughout):**

```text
Offer  =  a provider-domain advertisement + commitment record
        ≠  contract authority      (contracts/ owns acquired connectivity)
        ≠  global topology         (LOCK-105: provider-local views only)
        ≠  provider SDK types      (LOCK-110: vendor types never enter)
        ≠  payment authority       (LOCK-113: terms are DATA, money is external)
        ≠  truth                   (an offer is a claim by its issuer)
```

## Module map

```text
offers/
  errors.py           Typed fail-closed errors + the frozen offer-* vocabulary
  model.py            ProviderDomain, CapabilityAdvertisement (+ entries),
                      OfferRecord, OfferCommitment (explicit + bounded),
                      OfferPricing (LOCK-113 integer-money terms),
                      ServiceBoundary (jurisdiction + opaque geography refs),
                      AdvertisementRef, record-level status evaluation
  serialization.py    Canonical JSON round-trips (WORK-003 machinery;
                      duplicate-key rejection; tamper-evident parse)
  exchange.py         OfferExchange: the deterministic provider-domain
                      catalog (W047 index discipline: idempotent /
                      conflicting / supersession; explicit provider-scoped
                      withdrawal; provider-local queries — LOCK-105)
  bridge.py           The M003->M002 reference surface (offer references
                      for SelectOffers; pricing/service-property reference
                      shapes; verify_accepted_offers fail-closed)
```

## Key semantics

- **Provider sovereignty (LOCK-104/LOCK-105):** providers export exactly
  what frozen 1.1 §5 lists — capabilities, service boundaries, offers,
  commitments — as opaque, provenance-carrying DATA. The exchange holds
  no topology, exposes no node/link/path surface, and every query is a
  filter within the catalog (optionally provider-scoped); NO query
  composes material across provider domains. Cross-provider composition
  is an M006+ execution-plan concern, deliberately absent.
- **Provenance first-class (LOCK-118):** every externally asserted
  member — capability advertisement entries, grounding advertisement
  references, commitments, pricing terms, service boundaries, and the
  records themselves — carries `contracts.Provenance` (issuer +
  decision refs). Construction without provenance fails closed.
- **Commitments are explicit and bounded:** every commitment is a typed
  record (frozen kind vocabulary, scalar params) whose window MUST lie
  inside the offer's validity interval — enforced structurally at
  construction, not by convention.
- **Commercial separation (LOCK-113):** pricing is typed DATA with the
  harvested W047 integer-money discipline (integer minor units,
  explicit exponent, frozen billing modes). No payment execution, no
  payment authority, no money movement — the bridge emits reference
  shapes only.
- **Determinism (LOCK-119):** content-derived ids over canonical JSON
  (tamper evidence at construction AND deserialization); injected
  RFC 3339 UTC instants only; no wall clock, no randomness, no UUIDs,
  no network; sorted iteration everywhere; secrets rejected at the
  boundary (label and value shapes).
- **Grounding:** an offer references at least one capability
  advertisement from its OWN provider; the advertisement entries carry
  the capability statement digests produced by the capabilities
  authority (`capabilities/advertisement.py`) — the offers domain
  never classifies capability ids (no second vocabulary authority).
- **Supersession/withdrawal:** deterministic schema-version supersession
  per (provider, listing key) with full audit retention; withdrawal is
  an explicit, provider-scoped, instant-recorded act — withdrawn
  records stay queryable for audit and never present as usable.

## Harvest + refactor provenance (the migration matrix)

Per `spec/migration/classification-matrix.md`:

- Capability registry: **RETAIN + REFACTOR → Offer/capability exchange**
  — the statement/negotiation semantics stay in `capabilities/`; the
  provider-domain advertisement seam (`capabilities/advertisement.py`)
  projects verified statements into offer-grounding entries.
- Discovery: **REFACTOR → Offer discovery, not global topology** —
  `DiscoveryObservation` gains opaque `offer_references` (emitted only
  when non-empty: legacy bytes stay byte-identical); the
  `discovery/offer_view.py` projection surfaces OFFER sightings.
- Marketplace (W047): the listing/index/money disciplines are
  harvested into this package (OfferPricing, the exchange index
  discipline, evidence-distinctness); `marketplace/offer_bridge.py`
  projects W047 listings onto the 1.1 offer records (eligibility stays
  M004; networkpath handoff stays M006+ execution).

## Verification

```bash
python3 tools/offer_selftest.py   # the M003 battery (deterministic, offline)
```

All instants are injected; runs are byte-identical across processes
(PYTHONHASHSEED-safe); no key material, no network, no randomness.
