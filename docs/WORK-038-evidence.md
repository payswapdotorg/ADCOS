# WORK-038 — Evidence disclosure

## Evidence classes (per the frozen handoff)

| Class | Meaning | Status |
|---|---|---|
| A | Architecture conformance | **supported-verified** (in-repo) |
| B | Automated verification | **supported-verified** (in-repo) |
| C | Physical / future-network interoperability | **not-applicable** (by the handoff's own class list) |

## Class A — architecture conformance (closed in-repo)

- The future profile is an **additive adapter/profile**: descriptor +
  deterministic synthetic implementation + declarative data, over the
  accepted W016 SDK bridge pattern (`agent/bridge.py` precedent).
- **No core schema change**: the WORK-002 access-profile registry is
  digest-pinned across every run and byte-identical to `origin/main`;
  the canonical identifier is the registry's own RESERVED
  `access.3gpp.nr.imt2030` path (reserved since WORK-002; status
  `reserved`; never activated).
- **Open-world safety**: an arbitrary UNKNOWN-but-well-formed future
  identifier registers as DATA, is preserved verbatim in the runtime
  snapshot, stays absent from the known-id set, and its classification
  stays `unknown_but_well_formed`.
- **Core purity**: 102 core modules import no `imt/` and no adapter
  implementation modules; the 14 core directories are untouched in the
  PR delta.
- **No vendor/PHY leakage**: no vendor tokens and no radio/PHY
  implementation tokens anywhere in `imt/`; no vendor SDK import (the
  battery's import-discipline and token audits).
- **No second authority**: `SessionStore`/`RoutingEngine`/
  `ResourceStore` are constructed only inside the scenario's fixture
  world (the accepted W032 `conformance/world.py` pattern); no other
  authority constructor appears anywhere.

## Class B — automated verification (closed in-repo)

The deterministic synthetic conformance run
(`imt.scenario.run_future_profile_conformance`) observes and journals:

1. the declaration validated fail-closed (WORK-002/W005/W008/W016
   delegated validators);
2. the technology identifier classified by the registry's own rule
   (`known` for the reserved id);
3. the future adapter registered as DATA on a REAL `AdapterRuntime`
   wired exactly like the reference agent wires it
   (`AdapterRuntime(session_store=...)` over a REAL WORK-012 store);
4. the nine WORK-016 contract operations exercised through the runtime
   (open, capabilities, observe, allocate, release, bind_session,
   unbind_session, health, close), including binding a REAL
   ESTABLISHED session — with the store's canonical bytes
   digest-proven unchanged across the binding (read-only discipline);
5. an unknown-but-well-formed future identifier registered, preserved
   verbatim, provably gaining no authority;
6. the registry digest-stable across the run (no core schema change);
7. **core equivalence**: routing, sessions, resources, and policy
   canonical digests byte-identical for the same fixed inputs before
   and after the future adapter was registered and fully exercised.

The run digest covers all of it; two honest runs always agree
(fresh-run and `PYTHONHASHSEED=1/99/31337` invariance verified);
replay verification re-runs the scenario and compares digests (a TRUE
replay, with typed divergence on tamper).

The W029/W005 coexistence discriminations are delegated verdicts: the
envelope disposition for the current protocol major stays
`known_compatible`; same-major mixed-version coexistence selects the
additive-evolution floor; major mismatch still fails closed; a
REQUIRED unknown future capability fails closed with the capability
authority's own `unknown-required-capability` reason **even when the
peer advertises the same unknown id** — future data never becomes
negotiation authority by agreement.

The sandbox's deterministic hang model is verified directly: an
under-budget operation yields the isolated `budget-exhausted` failure
value, and a throwing implementation surfaces as a typed failure value
(never an exception crossing the boundary).

## Class C — physical / future-network interoperability: NOT APPLICABLE

The WORK-038 handoff's frozen class list marks class C "not applicable
to this synthetic Work Item; do not invent real-world evidence."

This is enforced **in code, not prose**:

- `imt.assert_no_real_world_claim(claimed_class="C")` raises
  `future.evidence-class-violation`;
- `imt.classify_future_evidence(..., gate_outcome=<anything>)` raises
  the same typed error — unlike W037's OPEN class C (closable by a
  real lab gate), WORK-038's class C admits **no closure path at all**,
  because the hypothetical IMT-2030 technology has no radio, no vendor
  implementation, and no deployed network. Claiming otherwise would be
  fabrication.

The pinned statement (recorded in every evidence report):

> No real-world or future-network interoperability evidence is claimed,
> implied, or closable by this work item. WORK-038's acceptance is
> entirely synthetic (a synthetic future-profile conformance test over
> the accepted adapter/registry/core contracts); the hypothetical
> IMT-2030 technology has no radio, no vendor implementation, and no
> deployed network. When a real future IMT/6G system exists, its
> integration is a NEW work item with its own evidence contract — the
> synthetic evidence here can never be promoted to it.

## Open obligations unchanged after WORK-038

W020 SDR, W034 hardware, W035 Android device, W036 site, W037 real-5G
lab — all still 🟡 OPEN (non-blocking, disclosed). WORK-038 adds no
new external obligation: its verification requirement is entirely
synthetic and fully discharged in-repo.
