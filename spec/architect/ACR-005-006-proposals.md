# Durable Architecture Proposals — ACR-005 and ACR-006

This file is the repository-local discovery record for two architecture improvement proposals arising from the W035 physical validation lessons. They are proposals, not accepted architecture changes.

## ACR-005 — First-Class Network Path and Platform Boundary

GitHub Issue: #62

Status: PROPOSED

Canonical record:
`spec/acr/ACR-005-network-path-platform-boundary.md`

Proposal summary:

- distinguish physical fact, platform fact, and ADCOS fact;
- model a technology-neutral network path without creating a new routing/session authority;
- separate path detection, validation, binding, activation, and retirement;
- make handover transactional;
- preserve logical session identity while physical path/interface/bearer changes;
- make physical evidence a chain from physical observation through platform observation, path state, ADCOS binding, and traffic proof.

Reason:
W035 repeatedly demonstrated that Android-reported connectivity, host routing, ADCOS binding, and actual traffic can diverge. Explicit boundaries reduce false handover claims and provide a reusable path model for mobile, Wi-Fi, 5G, Ethernet, mesh, satellite, and USB-tethered access.

## ACR-006 — Event-Driven Platform Integration and Journal-First Recovery

GitHub Issue: #63

Status: PROPOSED

Canonical record:
`spec/acr/ACR-006-event-driven-platform-and-journal-first-recovery.md`

Proposal summary:

- retain authoritative snapshots but prefer ordered platform events for change notification;
- reduce polling and race conditions at platform boundaries;
- make intermittent/mobile recovery journal-first with immutable configuration, append-only journal, and compact checkpoints;
- require safe durable persistence before voluntary suspension where the platform permits it;
- treat Android background execution as an external constraint rather than a protocol guarantee;
- explicitly separate control-plane path operations from data-plane traffic.

Reason:
W035 exposed races caused by Android lifecycle timing, polling, process suspension, and host path changes. Event-driven integration and journal-first recovery should improve reliability, efficiency, battery behavior, and forensic clarity.

## Governance

Neither proposal changes the frozen architecture by itself. Acceptance requires a formal Architect decision, followed by updates to the persistent Architect state and any affected Work Item authorizations. Implementation must not begin solely because an issue or proposal exists.

GitHub Issues #62 and #63 are discussion/proposal surfaces. The repository ACR records and accepted persistent-Architect decisions remain authoritative.