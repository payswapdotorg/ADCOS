# WORK-041 Implementation Directive

**Authority:** WORK-041-CORE-001 / DEC-0052  
**Active Work Item:** WORK-041  
**Architecture basis:** ACR-005 (DEC-0047), with ACR-006 (DEC-0048) consumed where applicable  
**Implementation scope:** `networkpath/` and its required selftest/evidence surfaces only

## Objective

Implement the accepted ACR-005 NetworkPath/platform boundary over existing accepted authorities. Do not create a second identity, session, routing, transport, federation, or policy authority.

## Required behavior

1. `NetworkPath` is a technology-neutral representation of an access path composed from existing authority-owned state.
2. Platform observations remain platform evidence; they are not silently converted into protocol state.
3. Candidate path discovery is distinct from validation, binding, activation, and retirement.
4. Candidate paths must not become active merely because they are detected.
5. Handover is transactional: validate/probe/bind the candidate before activation; on failure preserve the previous active path where possible.
6. Logical session identity remains stable across physical path changes: `session_id` must not be recreated merely to make handover succeed.
7. Path activation/retirement ordering follows the accepted ACR-005/ACR-006 semantics and must be journal-verifiable.
8. Evidence must preserve source boundaries across platform, path, ADCOS, and transport layers.
9. Replay and restart behavior must be deterministic and fail closed where authoritative state is missing or contradictory.
10. Existing accepted authority owners remain the only authorities for identity, sessions, routing, transport, adapters, policy, and IP integration.

## Hard dependencies

- WORK-016
- WORK-018
- WORK-033
- WORK-034

All are Architect-accepted and merged.

## Forbidden

- Changes to frozen architecture documents.
- Wire-schema changes.
- Private-method authority access.
- A new session/path/routing authority outside the declared W041 boundary.
- W042/W043/W048 implementation.
- Commercial/payment/settlement work.
- W040 continuation.
- Physical validation claims or promotion of software evidence to PHYSICAL evidence.
- Changing `spec/architect/` as part of the implementation PR.

## Required verification

Before requesting Architect acceptance, run and report exact results for:

```bash
python3 tools/spec_check.py
python3 tools/spec_check.py --provenance
python3 tools/spec_check_selftest.py
python3 tools/networkpath_selftest.py
```

Also run every existing battery materially affected by the changed authorities, plus static analysis/type checking available in the repository environment.

## Definition of done

The implementation is not complete merely because tests pass. Acceptance requires a complete mapping from each W041 acceptance criterion to deterministic evidence, explicit authority ownership, failure/recovery semantics, adapter-boundary compliance, and no architecture drift.

The authoritative repository state is `main`. Do not infer requirements from chat or from this directive when the repository contracts provide a more specific rule; resolve any conflict in favor of the frozen architecture and persistent Architect state.
