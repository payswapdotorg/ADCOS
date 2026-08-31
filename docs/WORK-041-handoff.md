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

---

# Implementation-level handoff (WORK-041-CORE-001 delivery)

**Delivery branch:** `work-041-networkpath-core` (cut from main
`ece53db`, which carries the active authorization record
byte-identically from baseline `bb964a1`). This section is the
implementation-level handoff the governance section above promised;
the repository remains the sole authority for scope and acceptance.

## Module structure

```text
networkpath/
    __init__.py       public API (45 frozen names; battery-pinned)
    errors.py         NetworkPathError + frozen reason vocabulary (11 codes)
    state.py          frozen lifecycle: DISCOVERED/VALIDATED/BOUND/ACTIVE/RETIRED
                      + journaled action vocabulary + transition table
    model.py          NetworkPath (content-derived id, tamper-evident),
                      PlatformObservation (evidence DATA), LifecycleEvent
    observation.py    InterfaceSource -> PlatformObservation -> DISCOVERED
                      candidate (fail-closed, ambiguity-rejecting)
    validation.py     pure deterministic verdict (fresh observation +
                      adapter lifecycle/health, identity-drift gate)
    binding.py        ordinary WORK-033 bind_session + WORK-017 probe
                      (deterministic content-derived probe payloads)
    lifecycle.py      NetworkPathManager: the public production surface
                      (discover/validate/bind/probe/activate/retire,
                      transactional handover, replay-safe journal)
    evidence.py       PathEvidenceRecord chain + digests + the honest
                      two-track disclosure (physical: OPEN)
    integration.py    session-continuity facts through the public
                      session-authority reads
tools/networkpath_selftest.py  36-case battery (all five acceptance
                      criteria + negatives + structural audits)
docs/WORK-041-evidence.md      criterion-to-evidence mapping
```

## Key interfaces (public, frozen)

- `NetworkPathManager(runtime, clock)` — construct with the agent
  runtime and the SAME injected clock the runtime reads.
- `discover()` -> candidate ids (detection only; idempotent).
- `validate(path_id)` -> `NetworkPath` (`VALIDATED`) or typed
  `VALIDATION_REJECTED` (state unchanged).
- `bind(path_id, session_id)` -> `NetworkPath` (`BOUND`, binding facts
  recorded) or typed `BIND_REJECTED`/`SESSION_UNKNOWN`.
- `probe(path_id)` -> probe facts (`BOUND`, state-preserving; the
  transport authority decides sendability) or typed `PROBE_REJECTED`.
- `activate(path_id)` -> `NetworkPath` (`ACTIVE`; requires recorded
  probe evidence; the old active path is preserved at this instant).
- `retire(path_id)` -> `NetworkPath` (`RETIRED`, terminal; releases
  the adapter binding through the ordinary unbind path).
- `handover(session_id, candidate_id)` -> `HandoverResult` — the
  transactional ordering: validate -> bind -> probe -> activate ->
  retire old LAST; failures preserve the old ACTIVE path and never
  touch the logical session.
- `evidence(path_id)` / `evidence_digest()` / `content_digest()` /
  `event_log_digest()` — deterministic evidence and replay digests.
- `session_continuity_facts(runtime, session_id)` /
  `assert_session_continuity(before, after)` — public session-authority
  continuity verification.

## Verification results (delivery branch)

```text
networkpath_selftest        PASS 36/36
spec_check                  PASS 17/17
spec_check --provenance     PASS 2/2 (delta covered by WORK-041-CORE-001)
spec_check_selftest         PASS 32/32
agent_selftest              PASS 45/45
mobile_selftest             PASS 46/46
pilot_selftest              PASS 30/30
```

## Boundaries honored

- No second authority: imports confined to `protocol` / `agent` /
  `adapters` / `sessions`; no session/route/policy/transport/identity
  mutation calls (battery-pinned source audits).
- No wire-schema change; no frozen-spec change (byte-identical to
  origin/main, battery-pinned).
- No physical claims (PHYSICAL evidence remains OPEN and W040-owned).
- CI wiring of `tools/networkpath_selftest.py` is intentionally left
  to the Architect at acceptance (the workflow file is outside the
  authorized scope; see docs/WORK-041-evidence.md §7).
- W042/W043/W048+ not implemented, not authorized here.
