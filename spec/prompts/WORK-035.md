# WORK-035 — Android/mobile Agent: Architect Work Order

Status: EXECUTION-DESIGNATED

Implement only WORK-035 from the frozen `spec/work-items.md` contract.

Objective: implement mobile participation with user policy, identity, session continuity, background limitations, and local discovery.

Hard dependencies: WORK-012, WORK-013, WORK-018, WORK-033. These are consumed through their accepted public contracts. Do not introduce hidden dependencies on later Work Items.

Acceptance criteria:
- mobile device participates without changing core semantics;
- user-controlled resource sharing;
- handover and offline behavior are supported within OS limits.

Required verification: deterministic mobile lifecycle tests.

Architecture boundary:
- compose over accepted core/agent authorities; do not create second session, identity, routing, multipath, or policy authorities;
- preserve `session_id` semantics and all existing provenance/replay/transactional invariants;
- mobile/OS-specific APIs remain behind the mobile adapter boundary;
- background limitations and offline behavior must be explicit state/decision inputs, not hidden authority changes;
- user resource sharing is user-authorized policy/input, not a new resource authority;
- do not begin WORK-036+ implementation.

Evidence:
- automated/mobile lifecycle evidence is required now;
- physical-device evidence may be environment-gated and must be explicitly classified, never fabricated.

Out of scope: frozen architecture changes, new protocol semantics, later Work Items, vendor/platform authority leakage into core.
