# WORK-041 Implementation Handoff (repository-local)

**Status: ACTIVE — the durable handoff for the WORK-041 implementation
referenced by the active authorization `WORK-041-CORE-001`.**

This is the governance-level handoff on `main`. The implementation-level
handoff (module structure, interfaces, evidence model) will live on the
W041 delivery branch and in its PR body. Nothing in chat is authoritative.

## Authority

- Authorization: `spec/architect/authorizations/WORK-041.yaml` —
  `WORK-041-CORE-001`, `status: active`, baseline
  `1f8833e5cfbb3e1a17bac5c718070a31a7f67775`.
- Decision: DEC-0052 (atomic handoff from WORK-040-CORRECTION-001) —
  `spec/architect/decisions/DEC-0052-work-040-work-041-handoff.yaml`.
- Architecture basis: ACR-005 (accepted by DEC-0047) — First-Class Network
  Path and Platform Boundary.
- Ready-candidate contract: `spec/architect/work-items/WORK-041.md`.
- DEC-0051 (W040 decoupling) is ACCEPTED; W040 physical validation findings
  are advisory input, not a prerequisite.

## Objective (from the W041 contract)

Implement the accepted ACR-005 network-path/platform boundary WITHOUT
creating a second identity, session, routing, transport, federation, or
policy authority.

## Required outcomes

- A technology-neutral `NetworkPath` representation over existing
  authority-owned state.
- Separate platform observation from ADCOS protocol state.
- Separate path detection, validation, binding, activation, and retirement.
- Transactional handover: validate/bind/probe a candidate before activating
  it; preserve the prior active path on failure where possible.
- Preserve a stable logical `session_id` across physical path changes.
- An evidence chain from physical/platform observation through path
  validation and ADCOS binding to traffic proof.

## Acceptance criteria (quoted from the W041 contract)

1. The same logical session can move between distinct validated physical
   paths without changing `session_id`.
2. Candidate paths are detected without automatically becoming active.
3. Failed validation/bind/probe leaves the existing active path intact
   where possible.
4. The path/platform evidence chain is explicit, deterministic,
   replay-safe, and independently verifiable.
5. Existing accepted batteries remain green; no frozen authority ownership
   changes.

## Evidence classes (from the W041 contract)

- Software/architecture conformance: required (SOFTWARE class).
- Deterministic automated verification: required (SOFTWARE class).
- Physical deployment evidence: NOT required to implement W041; physical
  claims remain subject to existing evidence governance (W040's open
  EVID-007/EVID-008 obligations are separate and W040-owned).

## Hard dependencies (must be Architect-accepted and merged)

- WORK-016 Adapter SDK/runtime — accepted-merged (DEC-0016).
- WORK-018 IP integration boundary — accepted-merged (DEC-0018).
- WORK-033 AgentRuntime — accepted-merged (DEC-0033).
- WORK-034 EdgeGateway — accepted-merged (DEC-0034).

Architecture basis: ACR-005 (accepted by DEC-0047).

## Forbidden

- New identity/session/routing/transport/federation/policy authority.
- Wire-schema changes unless separately authorized.
- Private authority access.
- Synthetic physical evidence presented as physical PASS.
- W040 continuation (W040 correction cycle is superseded for the active
  slot only; EVID-007/EVID-008 remain W040-owned and OPEN).
- W042 implementation (W041→W042 interface dependency remains hard).
- W043/W048 implementation.
- Commercial core / payment / settlement implementation (ACR-009 commercial
  control plane is separate Work Item scope).

## Downstream impact

- W042 may consume W041 interfaces once W041 is accepted and merged;
  W042 remains unauthorized pending its own repository-local authorization.
- W048 (provider sharing) composes W041 + W042; it remains unauthorized
  and its interface dependency on W041/W042 is unchanged.

## Verification required before W041 PR review

```bash
python3 tools/spec_check.py
python3 tools/spec_check.py --provenance
python3 tools/spec_check_selftest.py
python3 tools/networkpath_selftest.py   # the W041 selftest (to be created by the implementation PR)
```

All relevant existing batteries must remain green; no frozen authority
ownership changes.
