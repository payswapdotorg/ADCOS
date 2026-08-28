# WORK-035 — Android/mobile Agent: Implementation Handoff

**Status:** EXECUTION-DESIGNATED — implement only WORK-035.

## Objective
Implement mobile participation with user policy, identity, session continuity, background limitations, and local discovery.

## Hard dependencies
WORK-012, WORK-013, WORK-018, WORK-033.

## Acceptance
- mobile participation without changing core semantics;
- user-controlled resource sharing;
- handover and offline behavior within OS limits.

## Architecture boundary
- Compose over accepted authorities; no second identity/session/routing/multipath/policy authority.
- Preserve the sacred `session_id`, provenance, replay, transaction, and recovery semantics.
- Keep Android/mobile/OS-specific behavior behind the mobile adapter boundary.
- Model OS background limits and offline state explicitly; do not silently mutate authority state.
- User resource sharing is user authorization/input, not a new resource authority.
- Do not implement WORK-036+.

## Verification
Deterministic mobile lifecycle tests covering foreground/background transitions, offline/online transitions, session continuity/handover, user consent/resource sharing, persistence/restart, failure/recovery, and absence of forbidden core/vendor imports.

## Evidence
Automated/mobile lifecycle evidence is required. Physical-device evidence is separate environment evidence and must remain explicitly classified as OPEN until genuinely demonstrated.

## Out of scope
Frozen architecture changes, new protocol semantics, vendor/platform authority leakage into core, later Work Items.
