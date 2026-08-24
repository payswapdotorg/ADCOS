# WORK-012 — Session Lifecycle and Connectivity Execution Boundary

## Status

**FROZEN HANDOFF — Architect-issued implementation prompt**

**Architecture Version:** 1.0

**Base:** Architect-accepted `main` after WORK-011 merge (`38a8f950252f16e86fa3e245e29c67ef21722b49`).

**Depends on:** WORK-003, WORK-004, WORK-011.

**Purpose:** Implement the technology-neutral ADCOS session lifecycle that turns an accepted routing decision into a tracked logical connectivity session, without implementing packet forwarding, tunnel execution, adapter selection, radio control, 5G core/RAN, Wi-Fi, transport, billing, or mobility.

## 1. Frozen authority boundary

WORK-012 owns **logical session lifecycle state** only.

```text
Identity     = who participates
Topology     = what connectivity/evidence exists
Resources    = what capacity/measurements/accounting exist
Intent       = what outcome is desired
Policy       = what is permitted
Routing      = which feasible path is selected
Session      = lifecycle/state of an accepted logical connectivity relationship
Transport    = how bytes are carried
Adapter      = how a concrete technology realizes transport
```

Therefore:

```text
Session ≠ topology authority
Session ≠ routing authority
Session ≠ resource accounting authority
Session ≠ policy engine
Session ≠ identity authority
Session ≠ packet forwarding
Session ≠ tunnel implementation
Session ≠ adapter selection
Session ≠ access technology
Session ≠ mobility controller
Session ≠ billing/settlement
```

A session MUST reference the accepted routing decision; it MUST NOT recompute, repair, or silently replace the route.

## 2. Core objects

Implement a technology-neutral `sessions/` package with at minimum:

- `Session` — immutable identity/reference fields plus lifecycle state.
- `SessionBinding` — immutable binding to source, destination, intent digest, policy decision id, and route decision id.
- `SessionState` — frozen lifecycle vocabulary:
  - `REQUESTED`
  - `AUTHORIZED`
  - `ESTABLISHED`
  - `DEGRADED`
  - `RECONNECTING`
  - `SUSPENDED`
  - `TERMINATING`
  - `TERMINATED`
  - `FAILED`
- `SessionEvent` — append-only transition evidence with injected event instant and monotonic sequence.
- `SessionResult` / transition result — deterministic success/failure envelope with stable reason codes.
- `SessionStore` — deterministic, atomic lifecycle persistence in memory for this work item.

Do not add a second identity vocabulary. Reuse WORK-004 NodeIDs.
Do not add a second routing vocabulary. Reuse WORK-011 `RouteDecision`/`Path` identifiers.
Do not add a second intent vocabulary. Store only the WORK-009 normalized intent digest/reference.
Do not add a second policy vocabulary. Store only the accepted WORK-010 decision id and set/version binding.

## 3. Session creation contract

A session may be created only from an explicit accepted route decision.

Creation MUST verify:

1. source and destination NodeIDs are canonical;
2. route decision is structurally valid and content-bound;
3. route decision code is `selected`;
4. selected path is present and `path_id` matches its content;
5. selected path source/destination match the requested session endpoints;
6. policy decision reference is present and consistent with the session binding;
7. intent digest, when supplied, matches the binding;
8. evaluation/session creation instant is injected, never read from wall clock;
9. the selected path is not expired at creation;
10. the resulting session id is content-derived and reproducible.

No route may be silently recomputed during creation.

## 4. State machine

Only these transitions are legal unless explicitly stated otherwise:

```text
REQUESTED    → AUTHORIZED | FAILED
AUTHORIZED  → ESTABLISHED | FAILED
ESTABLISHED  → DEGRADED | RECONNECTING | TERMINATING | FAILED
DEGRADED     → ESTABLISHED | RECONNECTING | TERMINATING | FAILED
RECONNECTING → ESTABLISHED | DEGRADED | TERMINATING | FAILED
SUSPENDED    → RECONNECTING | TERMINATING
TERMINATING  → TERMINATED | FAILED
TERMINATED   → (terminal)
FAILED       → (terminal)
```

For this work item, `SUSPENDED` is entered only through an explicit suspend operation and may not be inferred from an arbitrary resource measurement.

A transition MUST be atomic: the event and new session state become visible together or neither does.

Illegal transitions MUST fail closed without mutating the previous state.

## 5. Event model

Every accepted transition produces exactly one append-only `SessionEvent` with:

```text
session_id
sequence
previous_state
new_state
event_type
event_instant
actor_reference
reason_code
metadata/extensions
```

`sequence` is strictly monotonic per session.

Duplicate replay of the exact same event is idempotent.

Conflicting reuse of an existing sequence with different content MUST fail closed.

Do not introduce a global replay database.

Event identifiers MUST be content-derived.

## 6. Session identity

`session_id` MUST be a content-derived fingerprint over stable binding material, not a random UUID and not a transport connection id.

The stable binding MUST include at least:

```text
source_node_id
destination_node_id
route_decision_id
policy_decision_id
intent_digest (or explicit absent marker)
creation_instant
```

Do not derive session identity from MAC addresses, SIM/IMSI, modem identifiers, socket tuples, vendor ids, or access technology.

## 7. Route binding invariants

Once created, a session stores the accepted `route_decision_id` and selected `path_id`.

The session layer MUST reject:

- route decision id tampering;
- selected path id tampering;
- a route decision whose selected path no longer matches its own content;
- endpoint mismatch;
- route expiry before establishment;
- route decision changes presented as though they were the original route.

A future work item may implement reconnect/re-route, but WORK-012 must represent a route change as an explicit lifecycle operation/event rather than silently changing `path_id`.

## 8. Reconnect boundary

Implement the logical `RECONNECTING` state and a deterministic reconnect intent/event contract, but do NOT implement path discovery or route computation inside sessions.

A reconnect operation accepts an externally produced new `RouteDecision` and verifies:

```text
old session endpoints == new route endpoints
new route decision is selected
new route path is valid and not expired
policy binding remains valid
intent binding remains valid
```

The session then emits a transition event recording old and new route references.

The session package must not call `RoutingEngine` internally.

## 9. Termination

Termination is explicit and idempotent.

`TERMINATING → TERMINATED` must be possible without transport knowledge.

Attempting to transition a terminal session again is deterministic and non-mutating.

Do not perform resource release, billing, settlement, or transport teardown here. Those belong to later authorities/adapters.

## 10. Snapshot and time semantics

All lifecycle evaluation uses injected RFC 3339 UTC instants via WORK-003 primitives.

No `datetime.now()`, `time.time()`, UUID generation, randomness, environment-dependent identity, or network access.

Expiry boundaries must be explicit and tested, including `now == expires_at` semantics according to the accepted temporal conventions.

## 11. Serialization and canonicalization

Provide deterministic canonical JSON serialization using WORK-003 canonicalization.

Unknown fields MUST survive round-trips where the existing repository contract requires forward compatibility.

Derived identifiers MUST be recomputed and verified on deserialization.

A tampered `session_id` or `event_id` MUST be rejected rather than trusted.

## 12. Store semantics

`SessionStore` must provide atomic operations for:

- create;
- transition;
- append/replay an event;
- reconnect binding update;
- explicit terminate.

A failed transition must leave the full prior session state and event history unchanged.

No operation may partially apply state.

Concurrent transitions must serialize deterministically per session.

## 13. Forbidden shortcuts

Do NOT:

- open sockets;
- send packets;
- create tunnels;
- manipulate Linux networking;
- import 5G/LTE/NR/Wi-Fi/vendor SDKs;
- implement adapter selection;
- implement mobility/handover;
- mutate topology/resource/policy/identity stores;
- reserve or consume resources;
- perform billing/settlement;
- compute trust/reputation;
- invoke `RoutingEngine` internally;
- use wall clock/randomness;
- introduce a second NodeID, policy, intent, route, resource, or capability vocabulary.

## 14. Required regression coverage

At minimum test:

1. valid creation from selected route;
2. reject non-selected route;
3. reject tampered route decision id;
4. reject tampered path id;
5. reject endpoint mismatch;
6. reject expired selected path at creation;
7. deterministic session id;
8. duplicate creation idempotency/conflict behavior;
9. every legal state transition;
10. every illegal transition fails closed and does not mutate state;
11. atomic transition failure;
12. monotonic event sequence;
13. exact duplicate event replay is idempotent;
14. conflicting same-sequence event fails closed;
15. event id content binding;
16. session id tamper rejection on deserialization;
17. reconnect requires an externally supplied selected route;
18. reconnect endpoint mismatch rejected;
19. reconnect route-expiry rejection;
20. reconnect binding event retains old/new path ids;
21. termination is idempotent;
22. terminal state cannot transition;
23. no resource/account mutation;
24. no topology mutation;
25. no policy mutation;
26. no identity mutation;
27. no RoutingEngine invocation/import cycle;
28. no wall-clock/randomness/network access;
29. canonical serialization round-trip;
30. unknown-field preservation where applicable;
31. deterministic cross-process output;
32. concurrent per-session transition determinism;
33. secret-material rejection;
34. access-technology/vendor leakage rejection.

Add further adversarial cases as needed. Passing tests do not override an architectural violation.

## 15. Governance integration

Register the package and `tools/session_selftest.py` with the existing deterministic specification/tooling checks and CI.

Do not modify frozen architecture documents.

Do not modify prior WORK-001..011 prompts.

Only add WORK-012 implementation artifacts, required tooling registration, CI wiring, and documentation needed to describe the implementation.

## 16. Definition of Done

WORK-012 is complete only when:

- session lifecycle is fully implemented inside its frozen boundary;
- all required tests pass deterministically;
- atomicity and replay semantics are proven;
- route/policy/intent/identity bindings are mechanically verified;
- reconnect is represented but routing remains external;
- no transport/adapter/access-technology implementation exists;
- all prior frozen documents remain byte-identical;
- CI is green;
- Architect review finds no authority duplication or hidden dependency.

## 17. Architect review emphasis

The Architect will specifically inspect for:

1. session state becoming an implicit topology or routing authority;
2. route replacement without an explicit reconnect event;
3. policy/intent bindings being stored but not verified;
4. terminal-state mutation bugs;
5. partial transition commits;
6. replay/sequence ambiguity;
7. random or wall-clock session identity;
8. transport/access-technology leakage;
9. hidden invocation of routing/resource/policy engines;
10. resource/billing side effects hidden inside lifecycle transitions.

A passing selftest does not imply acceptance. The implementation must match the frozen protocol boundary exactly.
