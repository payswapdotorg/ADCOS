# WORK-032 — Conformance Suite: Implementation Handoff

## Status

**IMPLEMENTED — PR submitted, awaiting Architect review.**

Branch: `work-032-conformance-suite` (anchored at `main@c2a25668`, the
W031-merge + ACR-003 + CI-correction baseline designated by the
Architect work order).

## What was built

A dedicated `conformance/` family (8 modules + 10 vector modules +
README) and `tools/conformance_selftest.py` (46-case battery), plus one
additive CI step. The suite is a deterministic verifier and evidence
classifier over the frozen contracts — never a second protocol
authority.

- `conformance/model.py` — frozen vocabularies: verdicts, the three
  evidence classes, polarities, stable reason classes, the 10 required
  areas, the 15 negative/security categories, the 7 failure/recovery
  categories, and the 7 discrimination areas as a frozen TAG
  vocabulary; immutable vector/result/report dataclasses.
- `conformance/registry.py` — deterministic registry: unique ids,
  frozen tag vocabulary, area/authority attribution enforced at
  registration; canonical (vector-id sorted) order independent of
  registration order.
- `conformance/world.py` — the fixture world composing the nine
  accepted authorities through their public contracts (identity ->
  policy/routing -> sessions -> federation/adapter/transport), with
  narrow per-area surfaces that delegate every verdict unchanged.
- `conformance/vectors/` — 136 vectors: envelope 17, identity 13,
  capabilities 14, topology 13, routing 12, sessions 14, federation 15,
  adapter 15, transport 16, structure 7 (47 positive / 89 negative).
- `conformance/doubles.py` — in-vector SUBJECT doubles (throwing,
  misshapen, budget-burning, inflating, lying-health adapters)
  subclassing only the sanctioned W016 SDK ABC.
- `conformance/harness.py` — fail-closed execution: one fresh world
  per vector; exceptions escaping a vector's own error mapping are
  NONCONFORMANT (`unexpected-exception`), never guesses.
- `conformance/evidence.py` — the three-class evidence model; external
  evidence is unattainable from in-repo vectors and attachable only
  explicitly by an operator-side caller.
- `conformance/serialization.py` — canonical report bytes with
  byte-identical round-trips.

## Coverage against the frozen contract

Every required bullet is covered and mechanically asserted
(battery cases 20–24):

- all 10 matrix areas, each with BOTH polarities;
- all 15 negative/security categories (malformed fields, invalid
  versions, canonicalization mismatch, expired/future data, replay and
  replay poisoning, forged identity/provenance, capability inflation,
  topology claim poisoning, route/session binding violations, scope
  escalation, transport downgrade, unknown required-vs-optional
  extensions, adapter/provider exceptions, hidden/private-authority
  access, forbidden imports);
- all 7 failure/recovery categories (restart via W003 state-envelope
  round-trips, stale/future data, version conflicts, provider
  exceptions, cleanup failure, replay state, cross-authority
  injection);
- every vector carries explicit authority attribution; all nine
  declared dependencies (W003/004/005/007/011/012/015/016/017) are
  attributed.

**Integrity != provenance** is preserved throughout: structurally
valid artifacts with forged claim ids, forged rotation authorizations,
tampered signatures, inflated capability ids, forged offer-digest
echoes, and never-accepted replayed events are all negative vectors.

**Multipath coverage** rides the session area: W012's frozen reconnect
contract owns the session-path binding surface (`META_OLD_PATH_ID` /
`META_NEW_PATH_ID`, vector SES-010). W013 (multipath) is NOT a declared
W032 dependency and is never imported — asserted mechanically by
structure vectors STR-001/002 and the import audit.

## Discriminating proofs (required)

Battery cases 31–42 prove the suite can FAIL a broken candidate, not
merely pass the accepted one:

- **provenance** (case 32): a sabotaged topology surface whose
  authoritative query ignores reporter/source-class makes TOP-002
  NONCONFORMANT (provenance collapse detected);
- **replay** (case 33): an envelope surface that drops the
  caller-supplied replay validator makes ENV-010 NONCONFORMANT;
- **downgrade** (case 34): an initiator that "repairs" forged
  offer-digest echoes makes TRA-005 NONCONFORMANT;
- **capability inflation** (case 35): a verify that re-signs the
  presented statement (structural validity treated as provenance)
  makes CAP-003 NONCONFORMANT;
- **authority boundary** (case 36): a session surface that re-computes
  routes when the authority rejects one (a shadow authority) makes
  SES-003 NONCONFORMANT;
- **adapter isolation** (case 37): a runtime whose allocate bypasses
  the sandbox (provider exceptions propagate) makes ADP-005
  NONCONFORMANT;
- **forbidden dependencies** (case 38 + structure vector STR-007): the
  import audit flags a smuggled `multipath`/`telemetry` fixture source.

Each sabotage follows the genuine -> sabotaged -> genuine-restored
pattern. Cases 39–42 prove the vendor, determinism, private-access,
and shadow-authority audits are likewise discriminating. Case 31
proves the harness comparison itself detects inverted expectations.

## Evidence model (battery cases 26–28)

`build_evidence_report` separates architecture conformance (the
coverage map), automated verification (verdict/counts/digest), and
external evidence. In-repo runs record NO external evidence and carry
the explicit statement; external records attach only explicitly and
never affect automated verification. `assert_no_external_claim`
enforces the separation mechanically.

## Determinism (battery cases 12, 16–18, 30)

No wall clock, randomness, or network (AST-enforced by STR-004).
Identical report digests across in-process runs, reversed
registration order, fresh subprocesses, and hash seeds 0/1/7919.
Byte-identical serialization round-trips. Stable reason classes from a
frozen vocabulary.

## Frozen-surface discipline

- `spec/` byte-identical to `origin/main` (battery case 45, context
  aware: PR delta on branches, committed-wiring verification on main,
  clean-spec degraded mode when the origin/main ref is absent).
- `docs/` delta = this handoff only; `tools/` delta = the battery
  only; `.github/` delta = one additive CI step (the conformance
  battery runs unconditionally — mandatory on PRs and directly
  verified on main pushes; its frozen-spec case handles every context).
- Public API surface frozen at 31 symbols (case 46).
- mypy `--strict --follow-imports=silent` clean over all 19 family
  files (the accepted W030/W031 invocation).

## Import discipline (structure vectors + battery case 38)

Imports are limited to: the nine declared dependency families +
`resources`/`policy.model` as documented TRANSITIVE input surfaces
(RoutingContext requires a genuine `ResourceStore` and
`PolicyDecision`; `SessionStore.create` requires a genuine
`RouteDecision` + `PolicyDecision` — these are input types of the
declared W011/W012 contracts themselves, the same transitive
composition pattern accepted for W031) + stdlib. No accepted selftest
required amendment this time: the guarded families (telemetry, energy,
management, upgrade, adapter/transport core-scans) are not imported,
and the frozen `_CORE_MODULES`/`CORE_DIRS` lists in those batteries do
not include the new family.

## Local verification evidence

- `tools/conformance_selftest.py`: **46/46 PASS** (matrix 136/136
  conformant; report digest
  `sha256:d132bb67c554d94e418b0d7a704626e768eef15bc6f705b0b43502ea7913eb26`
  stable across runs/subprocesses/hash-seeds).
- Full local battery: **34/34 tools PASS** (all 33 prior batteries +
  conformance) — zero cross-family reactions.
- mypy --strict clean (19 files).

## Out of scope (unchanged)

No production protocol implementation, no new protocol semantics, no
authority changes, no vendor stacks, no Linux Agent / W033+ runtime, no
external interoperability claims, no DAG or ACR-003/OAQ-001 changes.
Frozen `spec/` untouched.
