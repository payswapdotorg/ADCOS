# WORK-055 — Protocol Production Conformance

## Status

**Active implementation authorization:** `WORK-055-CORE-001`

**Governance decision:** `DEC-0088`

**Authorized baseline:** `57963858e5a2b9d11faed94b50f94e058cede0a8`

## Objective

Complete the production conformance layer required before ADCOS may declare wire compatibility. This Work Item hardens and extends the existing `conformance/` and WORK-032 verifier foundation against the frozen Architecture Version 1.0 and Protocol Version 1.0 contracts.

The output is conformance evidence, not a new protocol authority.

## Frozen authority boundary

The repository's frozen protocol/schema/contracts remain authoritative. WORK-055 may verify, serialize, compare, classify, and produce deterministic evidence against those contracts.

WORK-055 MUST NOT:

- change frozen protocol semantics, schemas, registries, or wire meanings;
- mint new protocol vocabulary or authority ownership;
- create a parallel/reference protocol implementation and treat it as authoritative;
- infer provenance from structural validity;
- promote conformance evidence into business, connectivity, routing, identity, session, federation, or economic authority;
- modify `spec/architect/` from the implementation PR;
- use network access, wall clock, process randomness, or host-specific state to make conformance outcomes nondeterministic;
- use simulator/reference implementations as interoperability evidence;
- restore or implement W048;
- close or alter W040 physical-evidence obligations.

Any requirement that cannot be satisfied without changing frozen semantics is **blocked and requires the ACR/change-control process** rather than local implementation discretion.

## Required coverage

The implementation must establish deterministic, mechanically discriminating conformance coverage for:

1. **Canonicalization profile** — the exact canonical representation used for protocol objects and digests is explicit and testable against the current frozen contracts.
2. **Canonical encoding vectors** — accepted and rejected encodings are covered by golden vectors; semantically equivalent inputs converge exactly where the frozen protocol requires it, and ambiguity is rejected where required.
3. **Signature coverage** — the signed/covered bytes or fields are explicit; mutations outside and inside the covered region are classified according to the frozen contract; forged provenance is rejected.
4. **Version negotiation** — supported version negotiation, unsupported versions, downgrade attempts, and incompatible combinations fail or succeed exactly as frozen.
5. **Unknown fields and extensions** — permitted extension behavior is explicit; unknown required/incompatible material fails closed; optional/forward-compatible behavior preserves frozen semantics.
6. **Replay/idempotency** — duplicate, replayed, and out-of-order messages/commands are classified exactly according to existing contracts; idempotent replays do not mint new authority or divergent state.
7. **Schema evolution/migration** — compatible migrations preserve semantics; incompatible migrations are rejected; downgrade/upgrade vectors are deterministic.
8. **Compatibility vectors** — compatibility classes and failure reasons are stable, explicit, and attributable to the owning frozen contract.
9. **Deterministic digest stability** — report/object digests are byte-stable across independent processes and `PYTHONHASHSEED` values and do not depend on registration/order artifacts.
10. **Evidence and authority separation** — conformance results remain conformance/automated-verification evidence and cannot become external, physical, or protocol authority.

## Required discriminating power

The suite must demonstrate both positive and negative behavior. At minimum, deliberately sabotaged candidate behavior must be shown to fail paired vectors for:

- canonicalization ambiguity;
- signature/covered-byte tampering;
- version downgrade/incompatible negotiation;
- unsafe unknown-field handling;
- replay/idempotency violations;
- schema migration incompatibility;
- deterministic digest instability;
- authority/provenance collapse;
- use of conformance evidence as authoritative state.

The genuine frozen implementation must pass the corresponding vectors. A suite that only passes the genuine implementation without rejecting the sabotaged candidate is nonconformant.

## Existing foundation

WORK-032 is the required starting point. Reuse its public API, deterministic matrix model, evidence classification, structural audits, and discrimination approach. Do not duplicate its authority model or create an independent protocol stack.

The implementation must preserve the existing separation among protocol envelope/serialization, identity, capabilities, topology, routing, sessions, federation, adapter, and transport authorities. Transitive dependencies already sanctioned by WORK-032 remain inputs through their public contracts rather than new DAG edges.

## Scope

Authorized implementation surfaces:

- `conformance/`
- `tools/conformance_selftest.py`
- `docs/WORK-055-evidence.md`
- `docs/WORK-055-handoff.md`

Generated/static golden vectors may be added only beneath the existing conformance boundary and only where they are test data for the already-frozen protocol. They must not alter `spec/schemas/protocol.json` or any other frozen authority file.

## Acceptance criteria

WORK-055 is accepted only when all of the following are proven from the delivery commit:

1. Canonicalization and canonical encoding behavior is explicit, deterministic, and covered by golden vectors.
2. Signature coverage is testable and tamper/provenance vectors discriminate genuine and forged artifacts.
3. Version negotiation rejects downgrade/incompatible cases exactly at the owning frozen boundary.
4. Unknown-field/extension behavior is explicit and fail-closed where the frozen contract requires it.
5. Replay, duplicate, and idempotency behavior is deterministic and does not mint duplicate authority/state.
6. Schema evolution/migration vectors demonstrate semantic preservation for compatible transitions and fail-closed behavior for incompatible ones.
7. Compatibility vectors provide stable result classes/reason codes with authoritative ownership.
8. Report/object digests are identical across repeated runs, subprocesses, and required hash seeds.
9. Deliberately sabotaged candidates are rejected by the suite across all mandatory discrimination categories.
10. No new protocol/business/connectivity authority exists in the implementation delta.
11. No frozen semantic/wire-schema change is present.
12. No `spec/architect/` change is present in the implementation PR.
13. No network, external evidence, physical evidence, or simulator output is used to establish production protocol conformance.
14. The evidence record is reproducible from a fresh checkout of the delivery commit and identifies exact files, commands, vectors, digests, and verdicts.
15. The existing WORK-032 conformance foundation remains intact; the new layer is additive/hardening work rather than a fork or replacement.

## Required evidence

The delivery must include:

- a deterministic self-test battery covering every requirement above;
- golden/conformance vectors with stable identifiers and owning authority;
- positive and negative reports;
- sabotage/discrimination reports;
- determinism/hash-seed evidence;
- structural import/private-access/shadow-authority/vendor/nondeterminism audits;
- exact delivery SHA and parent SHA;
- a scope audit proving the authorized-path boundary;
- a concise handoff identifying any remaining non-production limitations without relabeling them as passes.

## Out of scope

- Architecture Version or Protocol Version changes;
- schema/wire semantic redesign;
- W048 restoration;
- R4 physical validation;
- R5 developer-platform product expansion;
- provider onboarding/federation expansion;
- new economic, payment, marketplace, eligibility, allocation, usage, session, route, transport, identity, or policy authority;
- CI governance changes outside the authorized implementation surfaces;
- modifying `spec/architect/`;
- resolving inherited governance-debt records unless separately authorized.

## Exit condition

R3 may close only after Architect adversarial review establishes that the production conformance layer can distinguish a conforming implementation from the mandated classes of broken implementation and that all evidence remains subordinate to the frozen protocol authorities.
