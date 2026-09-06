# WORK-032 — Protocol/Adapter Conformance Suite

A deterministic verifier and evidence classifier over the frozen ADCOS
contracts. The suite composes the accepted authority implementations
(WORK-003/004/005/007/011/012/015/016/017) through their public
contracts, runs known-good and known-bad conformance vectors, and
classifies the results — it is never a second protocol authority.

## Authority boundary (frozen)

The suite MAY load frozen schemas/registries/vectors, compose the
accepted implementations through public contracts, define positive and
negative vectors, compare observed with frozen expected outcomes,
classify conformance, and exercise adapters/transport through the
stable W016/W017 contracts.

The suite MUST NOT (and does not): mint protocol vocabulary; redefine
authority ownership; mint authoritative protocol objects; treat
structural validity as provenance; use simulator/reference
implementations as interoperability evidence; modify frozen semantics;
or import W033+ runtime semantics. These rules are enforced
mechanically by the structure-area vectors (import audit, vendor scan,
determinism scan, private-access scan, shadow-authority scan) on every
run, and the audits are themselves discriminating (deliberately
sabotaged fixture sources are detected; see
`tools/conformance_selftest.py`).

## Composition surface

| Area | Authority | Contract |
|---|---|---|
| envelope | WORK-003 | protocol envelope / serialization / canonicalization |
| identity | WORK-004 | NodeID, credentials, rotation, revocation |
| capabilities | WORK-005 | signed statements, provenance, negotiation |
| topology | WORK-007 | evidence-aware claims, provenance containment |
| routing | WORK-011 | deterministic selection under policy binding |
| sessions | WORK-012 | lifecycle, route binding, reconnect (session-path binding — the multipath surface owned by the frozen W012 contract) |
| federation | WORK-015 | scopes, grants, exchanges, isolation |
| adapter | WORK-016 | SDK contract, sandbox isolation, runtime |
| transport | W017 | handshake, replay/downgrade protection, key lifecycle |
| structure | WORK-032 | the suite's own boundary discipline |

**Transitive composition (documented):** `RoutingContext` requires a
genuine `ResourceStore` (WORK-008) and `PolicyDecision` (WORK-010), and
`SessionStore.create` requires a genuine `RouteDecision` +
`PolicyDecision`. These are INPUT surfaces of the declared W011/W012
contracts themselves; importing `resources` and `policy.model` is
sanctioned transitive composition through declared dependencies, not a
hidden DAG edge. W013 (multipath) is NOT a declared W032 dependency
and is never imported — the required multipath coverage rides the
W012 session-path binding surface (reconnect records
`META_OLD_PATH_ID`/`META_NEW_PATH_ID`).

## Model

- `ConformanceVector` — one contract interaction with an explicit
  `ExpectedOutcome` (accept/reject + stable result classes), the
  authority whose frozen semantics decide the outcome, an invariant
  statement, and coverage tags from a frozen vocabulary.
- `ConformanceWorld` — a fresh, fully composed fixture per vector
  (identity -> routing -> sessions -> federation/adapter/transport),
  built from the accepted authorities with injected instants only.
- `harness.run_matrix` — executes vectors in canonical (vector-id
  sorted) order, one fresh world per vector; results are
  order-independent and reproducible by content digest. An exception
  escaping a vector's own error mapping is fail-closed
  NONCONFORMANT (`unexpected-exception`), never a guess.
- Integrity != provenance: a well-formed object with a forged
  identity-bearing digest/signature/event id is a negative vector
  wherever provenance is authoritative.

## Evidence model

Every result classifies into exactly three evidence classes
(`conformance.evidence`):

1. **architecture-conformance** — what frozen surface the matrix
   covers (the coverage map: area -> vectors -> invariants ->
   owning authority);
2. **automated-verification** — what the deterministic in-repo run
   observed (verdict, counts, content digest);
3. **external-evidence** — evidence gathered outside this repository.
   In-repo vectors can NEVER mint external evidence: the run entry
   points accept no external records, and `assert_no_external_claim`
   enforces the separation mechanically. External records may only be
   attached explicitly by an operator-side caller.

## Determinism

No wall clock, no runtime randomness, no network (enforced by the
structure scan). Fixed fixture instants and key material; canonical
(vector-id) ordering independent of registration order; canonical JSON
report serialization with byte-identical round-trips; identical report
digests across processes and hash seeds (verified by
`tools/conformance_selftest.py`).

## Discriminating power

The security vectors pair genuine artifacts with forged/tampered
variants (vulnerable behavior fails, corrected behavior passes), and
`tools/conformance_selftest.py` proves the harness itself is
discriminating: for each of provenance, replay, downgrade, capability
inflation, authority-boundary violations, adapter isolation, and
forbidden dependency directions, a deliberately SABOTAGED candidate
world (the vulnerable behavior implemented over public APIs) makes the
paired vector NONCONFORMANT while the genuine world stays CONFORMANT.

## Public API

See `conformance/__init__.py` (frozen surface; checked by the battery).
Subject doubles live in `conformance/doubles.py` and subclass only the
sanctioned SDK extension points (`AdapterContract`); sabotaged
candidate worlds live only in the selftest, never in the shipped
package.

## Verification

`python3 tools/conformance_selftest.py` — the conformance battery
(matrix run, coverage completeness, determinism, evidence separation,
discrimination proofs, structural audits, frozen-surface and CI
wiring checks). CI runs it as part of `spec-check` (mandatory on PRs;
committed wiring verified directly on main).

# WORK-055 — Protocol Production Conformance (R3 extension)

WORK-055 (WORK-055-CORE-001, DEC-0088) extended this foundation
additively with the R3 production-conformance layer. Every WORK-032
behavior is preserved: the ten matrix areas, the registry and tag
vocabularies, the world composition, the declared import surface, and
all W032 battery cases remain and pass. The matrix grew from 136 to
163 vectors.

Family-level additions (all within the frozen W032 import surface --
the nine declared roots plus sanctioned transitive inputs):

- **`conformance/profile.py`** — the production canonicalization
  profile: a named, attributed, digest-stable statement of every rule
  of the WORK-003 canonical JSON form (the profile that frozen
  protocol.json deliberately left to "later conformance work"); every
  rule is mechanically verified by the WIRE vectors, and a sabotaged
  canonicalizer is detected.
- **`conformance/golden.py` + `conformance/vectors/data/`** — the
  golden-vector corpus: 16 byte-exact test fixtures (canonical
  encoding, raw-text convergence, signature-input bases, codec
  cross-agreement) with stable ids, owning authorities, invariants,
  and outcome classes. The verifier calls only frozen public APIs and
  compares; the corpus is test data, never a protocol definition and
  never authoritative over the frozen specification.
- **`conformance/vectors/wire.py`** (envelope area) — canonicalization
  profile rules, corpus verification, signature coverage and
  covered-byte integrity end-to-end through the WORK-004 provider
  seam, unknown-field/extension hardening, replay/idempotency
  hardening, and evidence separation.

Battery-level R3 coverage (in `tools/conformance_selftest.py`, the
sanctioned composition root): the WORK-029 surfaces — version
negotiation/downgrade resistance and schema evolution/migration — are
consumed from the battery rather than from this family, because the
frozen spec/dependency-graph.md carries no W055 family-level edge and
the WORK-029 family's own import discipline (tools/upgrade_selftest.py
case_33) permits only spec-recorded family importers (the W033/W038
precedents). Amending those records is Architect-owned; see
docs/WORK-055-handoff.md for the boundary decision and the unlock
path.

R3 discrimination proofs (each: genuine CONFORMANT -> sabotaged
NONCONFORMANT -> genuine CONFORMANT restored):

- canonicalization ambiguity — an insertion-order-preserving
  canonicalizer (family sabotage, paired with W055-CNF-WIRE-001);
- covered-byte exclusion — a covered member (payload, or the frozen
  `protocol` member) silently dropped from the signature basis
  (paired with W055-CNF-WIRE-017, whose mutation matrix is audited
  complete against the frozen `Envelope.KNOWN_FIELDS` set);
- unsafe unknown-field handling — required:true extensions silently
  downgraded to optional (paired with W055-CNF-WIRE-021);
- evidence-as-authority — a CONFORMANT conformance report verdict
  overruling the frozen validation pipeline (paired with
  W032-CNF-ENV-002);
- negotiation downgrade — a cross-major clamping fallback
  (battery-level, over the genuine WORK-029 API);
- migration best-effort reversal — reversing a declared
  non-reversible step (battery-level, over the genuine registry);
- digest instability — hash-order-dependent digests detected as
  unstable across PYTHONHASHSEED values while the genuine
  corpus/profile/W029-outcome digests stay byte-identical.

The battery also verifies the corpus/profile/W029-outcome digests
across subprocesses and hash seeds, the complete compatibility-class
table, the authorized W055 scope/ancestry (from the baseline
57963858e5a2b9d11faed94b50f94e058cede0a8), and that the frozen
authorities (protocol/, upgrade/, spec/) are untouched by the
delivery.
