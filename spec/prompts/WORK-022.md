# WORK-022 — Ethernet/fiber/microwave/satellite adapter family

## Architect-anchored implementation brief

Implement WORK-022 against accepted `main`, independent of WORK-020 and WORK-021.

Objective: add generic high-capacity, fixed, and long-haul access/backhaul adapters under the existing `/adapters` boundary, using the accepted WORK-016 Adapter SDK. Do not introduce vendor, modem, PHY, or hardware-specific types into core.

Hard dependencies: WORK-016 and WORK-018 only. WORK-020 and WORK-021 are not dependencies.

Acceptance criteria:
1. Link metrics and resource state map into the existing technology-neutral resource model.
2. Adapter-specific APIs remain isolated behind `/adapters`.
3. Backhaul paths can be selected by the existing routing system.
4. Ethernet/fiber/microwave/satellite implementations remain replaceable behind the same generic adapter boundary.
5. Failures are sandboxed and cannot corrupt core/session state.

Required verification: multi-link integration tests, deterministic resource mapping, route-selection tests, adapter failure isolation, frozen-spec integrity, and mypy/module cleanliness where configured.

Out of scope: modem firmware, PHY implementation, satellite waveform implementation, vendor SDK leakage into core, changes to frozen architecture/specification documents, and WORK-020 SDR acceptance.

Required delivery: one open PR against `main`; do not merge. Include objective, architecture sections, dependencies, acceptance mapping, changed files, out-of-scope statement, verification results, lock compliance, and no-drift statement.

Architectural constraints:
- Use WORK-016 `AdapterContract`/`AdapterContext` rather than inventing a second generic adapter SDK.
- Keep access technology identity in adapter/profile data, not core state-machine branches.
- Preserve `session_id` independently of link/bearer/interface identity.
- Do not import or reference WORK-020 `adapters/ran` or WORK-021 `adapters/wifi`.
- Prefer data-only profiles for technology-specific capabilities.
- A reported gateway/backhaul claim is not authoritative without evidence.
- Keep satellite/microwave/vendor-specific control surfaces behind adapters.
