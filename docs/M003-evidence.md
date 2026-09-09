# M003 — Offers and Provider Capability Exchange — Evidence Record

**Work Item:** M003 · **Authorization:** R7-CORE-001 (DEC-0101, the bounded R7 program
authorization; M003 is the charter's current child)
**Baseline:** `d022e06f8c3d881d2cc484aa5899483c24ed5fe8` (M002-accepted main head, DEC-0102)

This record persists the verified facts of the M003 delivery. Every claim below is
reproducible offline from the delivery head; no worker report is trusted without direct
verification (the standing Tech Lead rule).

## 1. Delivered surface

- **`offers/` (NEW)** — the provider-domain offer model (frozen 1.1 §2/§5/§6; the R7
  charter M003 scope):
  - `offers/model.py` — `ProviderDomain` (NodeID-validated through the accepted identity
    grammar — never a duplicated grammar); `AdvertisementEntry` (capability advertisement
    entry material: capability id, schema version, the content digest over the canonical
    capability-statement bytes, and the registry classification carried verbatim as DATA —
    the offers domain never classifies, no second vocabulary authority);
    `CapabilityAdvertisement` (the provider-domain capability advertisement: entries,
    validity, provenance); `OfferRecord` (the provider offer: provider, listing key,
    schema version, grounding advertisements, explicit bounded commitments, pricing
    terms, service boundaries, validity, provenance); `OfferCommitment` (explicit:
    typed kind + scalar params + MANDATORY provenance; bounded: the window MUST lie
    inside the offer validity — enforced structurally at construction);
    `OfferPricing` (LOCK-113: integer-money terms as DATA, frozen billing modes — the
    harvested W047 discipline; no payment authority, no payment movement);
    `ServiceBoundary` (jurisdiction + OPAQUE geography references — provider-declared
    data, never resolved into positions, never aggregated into topology); record-level
    status evaluation (`advertised` / `not-yet-valid` / `expired`, pure functions of
    record + injected instant); content-derived tamper-evident ids over canonical JSON
    (construction AND deserialization); secret rejection (LOCK-119).
    The record set REFERENCES the canonical `contracts/` domain (M002, DEC-0102) for
    `Provenance` and `ValidityInterval` — never re-implements or duplicates contract
    semantics (LOCK-101); contracts-domain errors are wrapped into offers-typed errors
    at the boundary (exception isolation).
  - `offers/serialization.py` — canonical-JSON round-trips through the WORK-003
    machinery (byte-stable; duplicate-key rejection; tamper-evident parse).
  - `offers/exchange.py` — `OfferExchange`: the deterministic provider-domain catalog
    (the harvested W047 index discipline: idempotent by content, conflicting
    same-version registration fails closed, deterministic schema-version supersession
    with full audit retention, explicit provider-scoped withdrawal with injected
    instants). LOCK-105 is structural: no topology/path/route/graph surface; every
    query is a filter within the catalog (optionally provider-scoped — the
    provider-local view); no query composes material across provider domains
    (cross-provider composition is M006+, deliberately absent).
  - `offers/bridge.py` — the M003↔M002 reference surface: `offer_reference` (the exact
    `offer` opaque-reference shape the canonical `SelectOffers` command stores),
    `pricing_reference`/`service_property_references` (LOCK-113: reference shapes
    only), `accepted_offer_values` (reads opaque data out of a contract — no contract
    semantics interpreted), `verify_accepted_offers` (resolves every accepted offer
    reference against the exchange at an injected instant; fail-closed on wrong kind /
    unknown / withdrawn / expired / superseded; never mutates the contract).
  - `offers/errors.py` — the frozen namespaced `offer-*` reason vocabulary.
  - `offers/README.md` — the package documentation with the harvest/refactor
    provenance per the migration matrix.
- **`capabilities/` (RETAIN + REFACTOR)** — migration matrix: "Capability registry:
  RETAIN + REFACTOR → Offer/capability exchange":
  - RETAINED (untouched): the statement model and frozen §6.4 field shape, the
    registry-backed classification (the single vocabulary authority), validity
    evaluation, deterministic negotiation, signing/verification, canonical
    serialization — every existing dependent unaffected (verified: topology, mobile,
    conformance, imt, federation, upgrade, onboarding, service, resource batteries
    all green).
  - REFACTORED (added): `capabilities/advertisement.py` — the provider-domain
    advertisement seam: `advertisement_entry` projects ONE verified statement into
    the typed entry material (digest = sha256 over the canonical statement bytes;
    classification flows from the registry, never enumerated in code);
    `advertisement_entries` projects the currently-ACTIVE batch at an injected
    instant (deterministic data-model ordering; ambiguous same-key content fails
    closed). `capabilities/__init__.py` exports the seam additively;
    `capabilities/README.md` documents the classification outcome.
- **`discovery/` (REFACTOR)** — migration matrix: "Discovery: REFACTOR → Offer
  discovery, not global topology":
  - `discovery/model.py` — `DiscoveryObservation` gains OPAQUE `offer_references`
    (validated non-empty strings; preserved verbatim; never resolved/classified by
    discovery — the offers authority owns them). The serialized member is emitted
    ONLY when non-empty and accepted as absent on parse: every legacy record and
    byte-stream stays byte-identical (verified by case in both the discovery battery
    and the M003 battery). Offer references are covered by the signature input and
    the derived observation fingerprint (tamper resistance unchanged).
  - `discovery/offer_view.py` (NEW) — the offer-discovery projection:
    `offer_sightings` surfaces `OfferSighting` records (provider, opaque offer
    reference, source provenance, issued/freshness instants, sighting freshness,
    source observation id) from the merged store at an injected instant — OFFERS,
    never topology (no node/link/path/graph material; the sighting record set cannot
    represent it); `active_offer_sightings` (fresh only; stale retained for audit);
    `sighted_offer_references` (the distinct opaque offer identities — the bridge a
    consumer hands to the M003 exchange). Deterministic: sorted by the data model,
    stable under reordering, injected instant only, naive instants fail closed.
  - `discovery/service.py` — `build_observation` accepts `offer_references`
    pass-through. `discovery/__init__.py` exports the projection additively;
    `discovery/README.md` documents the classification outcome and the explicit
    demotion (endpoints/context = provider-local execution input DATA per the
    matrix's Topology classification; the sighting projection surfaces none of it).
- **`marketplace/` (HARVEST + REFACTOR)** — the W047 reservoir:
  - HARVESTED INTO `offers/`: the integer-money commercial-terms discipline
    (currency/price_minor/exponent/billing_mode → `OfferPricing`); the deterministic
    listing-index discipline (idempotent/conflicting/supersession →
    `OfferExchange`); the evidence-distinctness discipline (advertised ≠ observed:
    the projection carries advertisement material only); the privacy-bounded
    coverage cells as opaque geography references.
  - REFACTORED: `marketplace/offer_bridge.py` (NEW) — `project_listing` projects one
    W047 listing onto the 1.1 `OfferRecord` (identity, terms, jurisdiction +
    coverage cells as opaque geography refs, advertised quality/capacity as explicit
    bounded commitments; deterministic; fail-closed on windowless listings — the
    legacy optional-window surface cannot project, never silently). The projection
    takes the provider's canonical NodeID, the grounding advertisement id and the
    provenance issuer as explicit inputs (never invents identity/grounding).
  - DEMOTED (documented, untouched as legacy surface for dependents): the W045
    eligibility composition → the M004 track; the NetworkPath handoff → the M006+
    execution track; the W051 reservation/lease coordination → the M009 commercial
    track. `marketplace/__init__.py` is untouched (its frozen public API case stays
    byte-identical).
- **`tools/offer_selftest.py` (NEW)** — the M003 battery: **49/49 PASS**.
- **Battery evolution (disclosed, per the M002 precedent)** — the per-domain
  batteries for the harvested domains evolved with their tested surfaces; the R7
  authorization's `tools/` scope entry covers every current/future per-child battery:
  - `tools/capability_selftest.py` — 15/15 → **18/18**: +3 M003 cases
    (advertisement entry projection: digest = canonical-bytes sha256, classification
    preserved; ACTIVE-only batch determinism + ambiguity fail-closed; entry
    serialization determinism). All historical cases unchanged.
  - `tools/discovery_selftest.py` — 27/27 → **29/29**: +2 M003 cases (offer
    references opaque/signed/round-trip with legacy byte-identity; the sighting
    projection fresh/stale/provider-scoped/topology-free). The `base_observation`
    fixture helper gained the `offer_references` pass-through parameter (default
    empty — all historical fixtures unchanged). All historical cases unchanged.
  - `tools/marketplace_selftest.py` — 46/46 → **48/48**: +2 M003 cases (the
    projection bridge mapping; the fail-closed surface). ONE disclosed in-place
    amendment: `_ALLOWED_IMPORT_MODULES` (case_32's sanctioned composition surface)
    gains `offers` and `contracts` — the 1.1 canonical domains the M003 bridge
    module composes. All historical cases otherwise unchanged.
- **`docs/M003-evidence.md`** — this record.

## 2. Deterministic verification matrix

All runs offline; instants injected; no wall clock, no randomness, no UUIDs, no
network; no real sockets in the new surface; PYTHONHASHSEED-safe (verified across
processes and seeds). Exit-code-based verification (a traceback or lowercase
"failed" IS a failure).

| Verification | Result | Evidence |
|---|---|---|
| Canonical field sets (advertisement 5, offer 10, nested shapes) | PASS | case_01 |
| Provider NodeID validation (malformed/near-miss fail closed, both paths) | PASS | case_02: 9 bad identities rejected |
| Vocabulary freeze (commitment kinds, billing modes, statuses) | PASS | case_03 |
| Construction validation fail-closed (empties, bad currency, ranges, non-scalars, digests, key grammar) | PASS | case_04a-h |
| LOCK-118 provenance mandatory (ads/commitments/pricing/boundaries/refs/records) | PASS | case_05 |
| Commitments explicit AND bounded (window ⊆ validity, both edges) | PASS | case_06 |
| LOCK-119 secrets rejected (labels + values) | PASS | case_07a-c |
| Canonical round-trips (byte-stable; duplicate keys rejected; mutated parse fails) | PASS | case_08 |
| Content-derived ids (deterministic, collision-free, re-derivation) | PASS | case_09 |
| Tamper evidence (construction AND deserialization) | PASS | case_10 |
| Status matrix (advertised/not-yet-valid/expired, exact boundaries; malformed instants fail) | PASS | case_11 |
| Registration idempotency (catalog digest unchanged) | PASS | case_12 |
| Conflicting same-version registration fails closed | PASS | case_13 |
| Deterministic supersession (order-independent; history retained) | PASS | case_14 |
| Withdrawal (unknown key fails; semantics at injected instants; resolve fails; audit retention) | PASS | case_15a-d |
| LOCK-105 no global topology (provider-local views; no topology API; opaque geography) | PASS | case_16 |
| LOCK-110 no SDK types (offers/ imports stdlib+protocol+identity+contracts only — AST audit) | PASS | case_17 |
| Grounding discipline (unregistered/cross-provider grounding rejected) | PASS | case_18a-b |
| Capabilities seam composition (digest, classification, ACTIVE-only, order-invariant) | PASS | case_19 |
| Discovery composition (offer refs opaque+signed+round-trip; legacy bytes identical; sightings fresh/stale/scoped) | PASS | case_20 |
| Marketplace projection (mapping, determinism, telemetry never projects) | PASS | case_21 |
| Contract composition (bridge shape; SelectOffers binds; verify resolves; withdrawn fails closed; wrong kind/unknown rejected; contract untouched) | PASS | case_22a-f |
| LOCK-117 offer ≠ contract authority (identity unchanged; ref kinds exact; no contract-state API) | PASS | case_23 |
| LOCK-113 commercial boundary (terms as DATA; no payment surface; references only) | PASS | case_24 |
| Clock discipline (no wall clock/randomness/UUIDs in offers/ + refactored modules) | PASS | case_25 |
| Cross-process determinism (PYTHONHASHSEED 0/1/12345) | PASS | case_26 |
| Sorted iteration (listings by (provider, key); advertisements by id) | PASS | case_27 |
| Lock conformance mapping (LOCK-101/104/105/110/113/117/118/119) | PASS | case_28 |
| Exception isolation (typed errors only; contracts errors wrapped) | PASS | case_29 |
| Fuzz (120 seeded byte mutations + garbage payloads) | PASS | case_30 |

**Battery result: PASS (49/49 cases), run 3× consecutively.**

## 3. Lock-conformance summary (Architecture 1.1)

- **LOCK-101 (canonical contract):** offers REFERENCE `contracts/` (import
  `Provenance`/`ValidityInterval`/`OpaqueReference`; never re-implement contract
  semantics); the canonical `ConnectivityContract` stays the sole authority — offers
  produce the opaque reference shapes it stores, and `verify_accepted_offers` never
  mutates a contract.
- **LOCK-104 (provider sovereignty):** providers export exactly the 1.1 §5 list
  (capabilities, service boundaries, offers, commitments); an offer grounds ONLY in
  its own provider's advertisements (cross-provider grounding fails closed);
  provider identity is an identity reference, never a trust claim.
- **LOCK-105 (no global topology):** the exchange holds only provider-exported
  offer/advertisement records; every query is a filter (optionally provider-scoped);
  no query composes across providers; there is no node/link/path/graph surface; the
  record set cannot represent topology; discovery sightings carry (provider, offer)
  pairs with freshness — never topology.
- **LOCK-110 (adapter isolation):** no provider SDK/vendor types anywhere in the
  offers surface; `offers/` imports stdlib + protocol + identity + contracts only
  (AST-audited in the battery).
- **LOCK-113 (commercial separation):** pricing is typed integer DATA (the
  harvested W047 discipline); no payment/charge/settle/reserve surface exists; the
  bridge emits `usage-pricing-terms` reference shapes only.
- **LOCK-117 (authority uniqueness):** an offer is reference DATA — binding offers
  never changes contract identity; `resolve` accepts exactly the `offer` reference
  kind; no artifact-authority path exists.
- **LOCK-118 (provenance):** every externally asserted member (advertisement
  entries' grounding refs, commitments, pricing, boundaries, and the records
  themselves) carries `contracts.Provenance`; construction without provenance fails
  closed; the capability statement digests bind advertisement entries to the exact
  statement bytes.
- **LOCK-119 (secrets):** secret-shaped labels and values rejected at construction
  and deserialization (offer keys, params, geography refs).
- **LOCK-115 (simple-system validity):** single-provider offer exchange requires no
  federation, multipath, or global optimization — a one-provider exchange with one
  offer is a complete, valid deployment (exercised throughout the battery).

## 4. Out-of-scope discipline (nothing else changed)

The M003 delta contains only the files listed in §1 (offers/ new; capabilities/,
discovery/, marketplace/ refactored; the three per-domain batteries evolved with
disclosure; tools/offer_selftest.py and docs/M003-evidence.md new). No control-plane
surface, no spec/ file, no `.github/` file, no protocol schema, no `contracts/`
modification (the M002 canonical domain is consumed, never modified), no W048
material (containment/sharing), no pilot/ surface, and no historical record is
touched. The drift guard classifies the delta implementation-only; the provenance
gate verifies full coverage by R7-CORE-001 (offers/, capabilities/, discovery/,
marketplace/, tools/, docs/M003-evidence.md are all declared child-scope prefixes).

Note (honest limitation): the CI workflow does not yet run
`tools/offer_selftest.py` — wiring a new battery step into `.github/` is a
control-plane change outside this implementation PR's boundary (the M002 precedent:
its step was pre-wired by a governance commit before delivery). The battery runs
locally on the delivery head (49/49 ×3, exit-code-based) and is the SOFTWARE
evidence for this delivery; CI wiring is a Tech Lead/governance action.

## 5. Evidence classes (honest disclosure)

- All M003 acceptance criteria: **SOFTWARE** class (deterministic offline battery,
  49/49 PASS on the delivery head; full battery suite green).
- Physical-world obligations: **NOT-TESTABLE/OPEN** — M003 creates and closes none;
  EVID-002..EVID-008 remain open and untouched. No simulation or battery result is
  physical, production, or live-service evidence.

## 6. Delivery provenance

- Branch: `m003-offer-exchange` from the DEC-0102-accepted main head `d022e06`.
- Battery: `python3 tools/offer_selftest.py` → PASS (49/49) on the delivery head,
  run 3× consecutively.
- Full suite: every battery the CI workflow runs, in workflow order, all green with
  exit-code-based detection (the three era-superseded batteries — payment,
  eligibility, client — skip visibly per the DEC-0099 disclosure; the sole tolerated
  non-zero exits on direct local runs are their ImportError guards).
- `contract_selftest.py`: still 54/54 (the M002 canonical domain is unmodified and
  consumed by reference only).
- Governance gates on the delivery head: `authorization_provenance.py` PASS,
  `current_spec_check.py` PASS, `tech_lead_guard.py` PASS,
  `architecture_drift_guard.py` PASS (implementation-only classification),
  `fresh_session_check.py --actual-main-sha <origin/main>` PASS.
