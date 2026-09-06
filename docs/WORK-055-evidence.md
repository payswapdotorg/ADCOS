# WORK-055 — Protocol Production Conformance (R3) — Evidence Record

Work Item: `WORK-055` — authorization `WORK-055-CORE-001` — decision `DEC-0088`.

- Authorized baseline (ancestor of the delivery): `57963858e5a2b9d11faed94b50f94e058cede0a8`
- Authorized branch: `work-055-protocol-production-conformance`
- Delivery: three commits on the exact authorized lineage (round 1 —
  the implementation delivery; round 2 — the review-correction commit
  responding to the Architect's CHANGES REQUIRED review of PR #15;
  round 3 — the documentation-correction commit responding to the
  Architect's round-2 re-review finding; exact SHAs in §13).

Everything in this record is reproducible from a fresh checkout of the
delivery head with a single command per section (Python 3, standard
library only, no network, no wall clock).

---

## 1. Delivery shape

The branch carries exactly three commits, all on the authorized
lineage — round 1 directly descended from the authorized baseline,
round 2 directly descended from round 1, round 3 directly descended
from round 2 (no rebase, no force over shared work, no other
ancestry):

1. **Round 1 — implementation delivery**
   `372299bfe3b54f79c0238d2927de2224249c4e36` (parent:
   `57963858e5a2b9d11faed94b50f94e058cede0a8`; 26 files, +3981/−5 —
   the exact Git measurement of that commit).
2. **Round 2 — review-correction commit** on top of round 1 (same
   PR lineage, per the repository's correction-round precedent),
   addressing the five review findings of PR #15: the WIRE-017
   `protocol`-member coverage gap, the evidence accounting errors, the
   W032 `case_25` edit, the CP-11/WIRE-011 traceability over-claim,
   and the CI-vs-local evidence distinction.
3. **Round 3 — documentation-correction commit** directly descended
   from round 2 (the same correction-round pattern), carrying the
   single P2 correction of the Architect's round-2 re-review: this
   §1 previously described the branch's commits as "both direct
   descendants of the authorized baseline" — true of round 1 only;
   round 2's parent is round 1, and round 3's parent is round 2.
   Documentation-only: no code, vector, battery, or frozen-surface
   change; every digest and battery result is unchanged from round 2.

The complete changed-path inventory of the exact Git tree
(`git diff --numstat 57963858e5a2b9d11faed94b50f94e058cede0a8 <head>`):

| Path | Kind | Δ lines |
|---|---|---|
| `conformance/README.md` | modified (W055 section appended; round 2: covered-byte row names both dropped-member fixtures) | +71/−0 |
| `conformance/__init__.py` | modified (additive exports: golden-corpus + profile sections; every W032 symbol unchanged) | +58/−2 |
| `conformance/golden.py` | added (golden-vector corpus loader/verifier) | +443/−0 |
| `conformance/model.py` | modified (additive `W055_REQUIRED_NEGATIVE_TAGS` / `W055_REQUIRED_DISCRIMINATION_TAGS`; W032 vocabularies unchanged) | +30/−1 |
| `conformance/profile.py` | added (production canonicalization profile) | +243/−0 |
| `conformance/vectors/__init__.py` | modified (registers the wire module) | +8/−0 |
| `conformance/vectors/data/w055-gld-cnv-0001.json` | added (golden vector, test data) | +13/−0 |
| `conformance/vectors/data/w055-gld-cnv-0002.json` | added (golden vector, test data) | +13/−0 |
| `conformance/vectors/data/w055-gld-cnv-0003.json` | added (golden vector, test data) | +13/−0 |
| `conformance/vectors/data/w055-gld-enc-0001.json` | added (golden vector, test data) | +26/−0 |
| `conformance/vectors/data/w055-gld-enc-0002.json` | added (golden vector, test data) | +58/−0 |
| `conformance/vectors/data/w055-gld-enc-0003.json` | added (golden vector, test data) | +32/−0 |
| `conformance/vectors/data/w055-gld-enc-0004.json` | added (golden vector, test data) | +34/−0 |
| `conformance/vectors/data/w055-gld-enc-0005.json` | added (golden vector, test data) | +35/−0 |
| `conformance/vectors/data/w055-gld-enc-0006.json` | added (golden vector, test data) | +30/−0 |
| `conformance/vectors/data/w055-gld-enc-0007.json` | added (golden vector, test data) | +19/−0 |
| `conformance/vectors/data/w055-gld-enc-0008.json` | added (golden vector, test data) | +48/−0 |
| `conformance/vectors/data/w055-gld-sig-0001.json` | added (golden vector, test data) | +25/−0 |
| `conformance/vectors/data/w055-gld-sig-0002.json` | added (golden vector, test data) | +47/−0 |
| `conformance/vectors/data/w055-gld-sig-0003.json` | added (golden vector, test data) | +28/−0 |
| `conformance/vectors/data/w055-gld-xcd-0001.json` | added (golden vector, test data) | +41/−0 |
| `conformance/vectors/data/w055-gld-xcd-0002.json` | added (golden vector, test data) | +23/−0 |
| `conformance/vectors/wire.py` | added (27 envelope-area R3 vectors; round 2: WIRE-011 extended to verify unknown-member preservation directly, WIRE-017 extended with the frozen `protocol` member + the `KNOWN_FIELDS` completeness audit) | +1184/−0 |
| `docs/WORK-055-evidence.md` | added (this record; round 2: corrected delivery-shape accounting, W032 preservation statement, digest, CI classification; round 3: lineage wording corrected to the actual parent chain) | +490/−0 |
| `docs/WORK-055-handoff.md` | added (handoff; round 2: correction-round disclosure; round 3: round-2 verdict and round-3 correction recorded) | +174/−0 |
| `tools/conformance_selftest.py` | extended (W032 cases 1–46 byte-identical — the round-1 `case_25` output edit was reverted in round 2; W055 cases 47–63, round 2: `case_52` proves both covered-byte sabotages) | +1101/−0 |

**Totals (exact Git tree): 26 files, +4287/−3.** Frozen surfaces
untouched: `spec/` (root documents, `schemas/`, `architect/`),
`protocol/`, `upgrade/`, W040/W048, all
business/economic/identity/session/routing/transport authorities —
verified mechanically by battery cases 62–63 and by the scope audit
below.

Reproduce (round-1 measurement, round-3 head, and ancestry):

```bash
git diff --numstat 57963858e5a2b9d11faed94b50f94e058cede0a8 <head>    # the table above
git diff --shortstat 57963858e5a2b9d11faed94b50f94e058cede0a8 <head>   # the totals above
git log --format='%h parents:%p %s' 57963858e5a2b9d11faed94b50f94e058cede0a8..<head>
git merge-base --is-ancestor 57963858e5a2b9d11faed94b50f94e058cede0a8 <head> && echo ANCESTRY-OK
```

Battery cases 62 (`case_62_w055_pr_delta_scope`) and 63
(`case_63_frozen_authorities_untouched`) perform exactly this audit on
every run (context-aware: the exact PR-base diff when `origin/main` is
available — the CI merge context; the exact baseline-relative diff in
the local delivery context).

---

## 2. The battery

Command:

```bash
python3 tools/conformance_selftest.py
```

Result at the delivery head: **PASS (63/63 cases)**.

- Cases 1–46 are the complete WORK-032 battery. **The W032 case
  bodies are byte-identical to the accepted WORK-032 delivery**:
  the file's changes are confined to the import block (the W055
  symbols), the W055 sabotage fixture classes, the W055 cases
  appended after `case_46`, and the `main()` wiring — verified by
  hunk-level diff against the authorized baseline (round 1 had also
  edited `case_25`'s output string to a dynamic count; the round-2
  correction reverted that edit, restoring the byte-identical W032
  case text, with no behavioral change: the dependency count is
  still nine). The pure WORK-032 battery was additionally run at the
  exact authorized baseline in an isolated worktree: **PASS (46/46)**.
- Cases 47–63 are the WORK-055 battery (see §4–§9). Round 2
  strengthened `case_52` (see §9).

Two consecutive full runs produced **byte-identical output**
(`cmp`-verified), and the matrix/corpus/profile digests are identical
across subprocesses and `PYTHONHASHSEED` values (§8).

---

## 3. The conformance matrix

```bash
python3 -c "from conformance import build_default_registry, run_matrix, ConformanceWorld, report_digest; r = run_matrix(build_default_registry().canonical_vectors(), ConformanceWorld); print(r.verdict.value, r.conformant, '/', r.total, report_digest(r))"
```

Result: **conformant 163/163** (63 positive / 100 negative vectors);
report digest `sha256:f7135f974f31ff287ca44d6b52a79e0e772d7c2c128e7f54fb60dafdcc6c6c17`
(round-2 value: WIRE-011/WIRE-017 were strengthened by the review
correction, which changes the vector statements and therefore the
report digest; the counts are unchanged: 163 vectors, 63/100
polarity split, same ten areas).

Area counts: envelope 44 (17 W032 + 27 W055-CNF-WIRE), identity 13,
capabilities 14, topology 13, routing 12, sessions 14, federation 15,
adapter 15, transport 16, structure 7. The ten WORK-032 areas,
authorities, registry, tag vocabularies, world composition, and public
API surface are unchanged (battery cases 20, 24, 25, 46); the matrix
grew from 136 to 163 vectors, additively.

## 4. Canonicalization profile (R3 coverage 1)

`conformance/profile.py` declares the production canonicalization
profile — the thing `spec/schemas/protocol.json` explicitly left to
"later conformance work before production wire compatibility is
declared":

- profile id: `adcos.canonical-json.production.v1`
- owning authority: WORK-003; protocol version read live from the
  frozen artifact (`1.0`)
- 12 rules (CP-01..CP-12), each a restatement of frozen WORK-003
  behavior with its frozen source citation
- profile digest (canonical-form SHA-256):
  `sha256:38cf39198501b9761fcee42c85c1b094e16166f1d8351170988ce9f8dd8a856b`

Every rule is mechanically verified by a paired WIRE vector:
key ordering incl. the UTF-16-vs-code-point discriminating key set
(WIRE-001), no whitespace (002), minimal escaping incl. lowercase
`\u00xx` (003), literal UTF-8 output (004), bool/null literals (005),
shortest integer forms (006), float rejection (007), non-string-key
rejection (008), depth limit (009), unencodable-text rejection (010),
absent-optional omission **and unknown-member verbatim preservation**
(011 — both CP-11 conjuncts are directly verified since the round-2
correction: an unknown top-level member rides serialization and the
canonical round trip byte-verbatim, never dropped or re-stamped),
idempotence (012). The profile
statement itself is verified complete and attributed (WIRE-013;
battery case 47).

## 5. Golden vectors (R3 coverage 2, 3, 8)

`conformance/golden.py` + `conformance/vectors/data/` — the golden
corpus: 16 byte-exact test fixtures. Each entry carries a stable
vector id (`W055-GLD-*`), the owning frozen authority, a contract
citation, an invariant, an outcome class from the frozen vocabulary,
the input, and the expected bytes.

| Category | Count | Authority |
|---|---|---|
| canonical-encoding | 8 | WORK-003 |
| encoding-convergence | 3 | WORK-003 |
| signature-input | 3 | WORK-003 |
| codec-cross-agreement | 2 | WORK-003 |

Corpus verification result: **16/16 verified byte-exactly**; corpus
digest (entries + verification outcomes):
`sha256:cf27067092ea5b869f79b56455d687ad5826981d1fb033aaeda050159c3520ba`
(battery case 48; WIRE-014; order-independence proven by
`corpus_from_entries(reversed(...))` yielding the identical digest —
WIRE-015, battery case 49).

Signature coverage (R3 coverage 3): the covered-byte basis is verified
complete — the WIRE-017 mutation matrix mutates every non-signature
envelope member (version, message_type, message_id, sender,
issued_at, expires_at, extensions, payload, evidence,
correlation_id, unknown extra members) and, since the round-2
correction, the frozen `protocol` member as well (basis presence of
`"protocol":"adcos"` plus a document-level protocol-value mutation,
because the frozen constructor fail-closes on any other protocol
value — itself the correct frozen behavior); the matrix is audited
complete against the frozen `Envelope.KNOWN_FIELDS` set so no covered
member can pass unexercised (WIRE-017); the signature member itself
is excluded exactly, opaque and structured forms alike (WIRE-018);
post-signing tampering of every covered capability-statement member —
including the signature — never verifies through the WORK-004 provider
seam (WIRE-019); signature re-attachment to different content is
rejected (WIRE-020, integrity != provenance).

## 6. Version negotiation and downgrade resistance (R3 coverage 4) — battery level

The WORK-029 surfaces are consumed from `tools/conformance_selftest.py`
— the sanctioned composition root — not from the conformance family
(see §10 for the boundary decision). Battery case 53 proves the
genuine negotiation table at the owning frozen boundary:

- shared known major at unequal heads selects the additive-evolution
  floor `1.2 = min(3, 2)` (symmetric); equal heads select themselves;
- mismatched majors fail closed with `MAJOR_MISMATCH` (no cross-major
  fallback, ever);
- an unknown major fails closed with `MAJOR_UNKNOWN` even when both
  peers agree on it (the WORK-003 artifact is the truth, not
  agreement);
- structural fail-closed: a forged `ProfileNegotiation` selecting a
  profile across mismatched majors, or above the floor, is not a
  constructible value;
- downgrade resistance: a downgrade plan is not a constructible record
  (`NOT_AN_UPGRADE`), while a genuine upgrade passes the check and
  fails later on the required gates (no over-rejection);
- the envelope-level disposition delegates to the WORK-003
  classification (`classify_major`: 1 → known_compatible, 99 →
  rejected_incompatible_major).

The W029 negotiation-outcome table digest (canonical-form SHA-256 of
the outcome table): `sha256:0e9b7565281f6c94c2a76ce2c018f08b0870fe7af5261da933bacd3a4cd3411f`.

Unknown fields (R3 coverage 5, family level): unknown
`required:true` extensions fail closed (`WIRE-021`, rejected_unknown_required);
`required:false` and opaque non-object extension values are preserved
as unknown-optional content (`WIRE-022`/`WIRE-023`, known_additive);
unknown top-level members are preserved verbatim through
serialization and the canonical round trip (`WIRE-011`, the CP-11
second conjunct — directly verified since the round-2 correction);
unknown message types follow the explicit caller policy (W032
ENV-008/ENV-009 preserved).

## 7. Schema evolution and migration (R3 coverage 7) — battery level

Battery case 55 proves the genuine migration contract at the owning
frozen boundary over a fixture schema line (`conformance.fixture-state`
— a harness label; the registry is the genuine WORK-029 authority, the
fixture steps are pure caller-supplied inputs):

- compatible migration preserves semantics: every prior member
  byte-identical after the additive step (the schema-version stamp is
  the migration's definition), the additive field appears, and the
  input state is never mutated (purity);
- reversible chains round-trip byte-identically (forward then backward
  == the original canonical state); chain reversibility is the
  conjunction of its edges (additive chain reversible, breaking chain
  not);
- incompatible transitions fail closed: non-reversible reversal
  (`MIGRATION_NOT_REVERSIBLE`), unknown path
  (`MIGRATION_PATH_UNKNOWN` — no identity migration), no-op
  (`MIGRATION_INVALID_STEP`), duplicate edge
  (`MIGRATION_DUPLICATE_EDGE`, registry unchanged), malformed step
  shapes (additive must bump exactly one minor; breaking must bump one
  major and reset the minor), tampered complete-content migration ids
  rejected at construction;
- registry introspection is canonical and deterministic across fresh
  constructions.

Replay/idempotency (R3 coverage 6, family level): duplicate delivery
rejects with exactly-once validator state and no divergence
(WIRE-024); a failing replay validator is a rejection, never a crash
or silent accept (WIRE-025); repeated evaluation of the identical
envelope is idempotent with zero state minted (WIRE-026); plus the
preserved W032 coverage (ENV-010 replay, TOP-003 idempotent merge,
TOP-004 out-of-order stale watermark, FED-011 replay provenance).

Compatibility classes (R3 coverage 8): all 9 frozen WORK-003
Classification values are produced by the matrix with stable codes and
owning-authority attribution (battery case 60); the W029 reason codes
are pinned by the negotiation/migration tables (§6/§7) and their
stability is digest-verified (§8).

## 8. Determinism (R3 coverage 9)

- Matrix digest stable across in-process runs (battery case 12),
  fresh subprocesses, and `PYTHONHASHSEED` 0/1/7919 (cases 17/18 — the
  W032 proofs, now over the 163-vector matrix).
- Corpus, profile, and W029-outcome digests identical across two fresh
  subprocesses with unset seed (case 49) and across `PYTHONHASHSEED`
  0/1/7919 (case 50).
- Digest-instability discrimination (case 50): a deliberately
  hash-order-dependent digest (set-iteration serialization) produces 3
  distinct values across the three seeds while the genuine digests
  stay byte-identical — the stability check can FAIL a
  nondeterministic candidate, not merely pass the genuine one.
- Registration/entry order never affects results: the registry
  canonicalizes by vector id (case 16); the corpus canonicalizes by
  vector id (WIRE-015); two full battery runs are byte-identical.
- No wall clock, no randomness, no network: the structure scan
  (STR-004) and its discrimination proof (case 40) run over the whole
  family, including every W055 module.

## 9. Discrimination (R3 "required discrimination")

Every mandated sabotage category is proven with the pattern
genuine → CONFORMANT, sabotaged → detected, genuine → CONFORMANT
restored:

| R3 category | Sabotaged candidate | Paired proof | Case |
|---|---|---|---|
| canonicalization ambiguity | insertion-order-preserving canonicalizer | W055-CNF-WIRE-001 | 51 |
| signature/covered-byte tampering | a covered member silently dropped from the basis — `payload` (round 1) **or the frozen `protocol` member** (round 2) | W055-CNF-WIRE-017 | 52 |
| version downgrade/incompatible negotiation | cross-major clamping fallback | genuine W029 negotiation table | 54 |
| unsafe unknown-field handling | required:true silently downgraded | W055-CNF-WIRE-021 | 57 |
| replay/idempotency failure | replay hook dropped | W032-CNF-ENV-010 | 33 (W032, preserved) |
| incompatible migration | best-effort reversal of a non-reversible step | genuine W029 registry | 56 |
| digest nondeterminism | hash-order-dependent digest | genuine digests | 50 |
| provenance/authority collapse | provenance-blind topology query | W032-CNF-TOP-002 | 32 (W032, preserved) |
| conformance evidence as authoritative state | CONFORMANT report verdict overruling validation | W032-CNF-ENV-002 | 58 |

The W032 sabotage classes (capability inflation, authority boundary,
adapter isolation, forbidden dependency — cases 35–37, 38–42) remain
and pass. `case_52` now proves the covered-byte category with TWO
sabotaged candidates — the round-1 `payload`-drop and the round-2
`protocol`-drop — each independently flipping W055-CNF-WIRE-017 to
NONCONFORMANT with the genuine implementation CONFORMANT before and
after. A suite that merely passes the genuine implementation is
insufficient; these paired proofs are the W055 answer to that
requirement.

## 10. Evidence separation and authority boundary (R3 coverage 10)

- Three evidence classes, strictly separated; no in-repo external
  evidence (battery cases 26–28 preserved).
- Conformance evidence can never become protocol state: a conformance
  evidence mapping is rejected by the WORK-003 envelope authority
  (W055-CNF-WIRE-027; battery case 61 re-proves it for the corpus
  digest and the full-matrix evidence report).
- Authority-boundary sabotage: a candidate whose acceptance path
  trusts a CONFORMANT report verdict over the frozen validation
  pipeline is detected (case 58).
- Structural audits over the whole family (including every W055
  module): import discipline (STR-001/002 — the family imports ONLY
  the nine W032 declared roots + sanctioned transitive inputs +
  stdlib; `upgrade` is NOT imported by the family), vendor scan
  (STR-003), nondeterminism scan (STR-004), private-access scan
  (STR-005), shadow-authority scan (STR-006: no authority class is
  defined or subclassed by the suite), audit discrimination (STR-007).
  The audits are themselves discriminating (battery cases 38–42).
- Public API surface: frozen at 49 symbols (case 46) — the W032
  symbols unchanged, the W055 additions (golden-corpus + profile
  sections) documented in `conformance/__init__.py`.
- `py_compile` clean over all 22 family files (case 43).

### The WORK-029 boundary decision (disclosed)

The WORK-055 authorization lists WORK-029 among the dependencies and
authority inputs, and the R3 coverage for version negotiation and
schema migration can only be satisfied by consuming those public
contracts. This delivery consumes them **from the battery**
(`tools/conformance_selftest.py`), NOT from the conformance family,
because:

1. the frozen `spec/dependency-graph.md` carries no W055 (or
   W032→W029) edge and cannot be modified from an implementation PR;
2. the accepted WORK-029 battery (`tools/upgrade_selftest.py`,
   case_33) enforces that no family outside the spec-recorded list
   (W033 agent, W038 imt) imports `upgrade` — a family-level import
   would fail that accepted battery, and repairing it is outside the
   W055 authorized scope ("do not repair inherited governance debt");
3. `tools/` is the sanctioned composition root by the W029 family's
   own documented discipline.

Consequence: the W029 batteries remain green at the delivery head
(`tools/upgrade_selftest.py`: **41/41**), the conformance family stays
within its frozen import surface, and the R3 negotiation/migration
coverage is fully mechanical at the battery level. Moving that
coverage into the registry matrix (two new areas) would require the
Architect-side amendment of the W029 sanctioned-importer list (the
W033/W038 precedent) plus a dependency-graph edge — recorded as a
non-blocking limitation in `docs/WORK-055-handoff.md`, never as a
pass.

## 11. Scope, ancestry, and frozen-surface proof

- Battery case 62: the delivery delta (26 changed paths at the
  round-3 head) lies exactly within the authorized scope
  (`conformance/`, `tools/conformance_selftest.py`,
  `docs/WORK-055-*.md`) and the authorized baseline
  `57963858e5a2b9d11faed94b50f94e058cede0a8` is an ancestor of HEAD.
- Battery case 63: `protocol/`, `upgrade/`, the spec root documents,
  and `spec/schemas/` are byte-identical to the authorized baseline;
  `spec/architect/` differs only from its owning ref (the PR base in
  the CI merge context, the baseline locally) — never from this
  delivery. `spec/architect/` was not modified by this PR.
- `tools/spec_check.py` output is byte-identical to the authorized
  baseline (11/16 blocking checks, the inherited ARCH-02/04/05/06/07
  historical failures, ARCH-03 passing in the local baseline-relative
  context, ARCH-08 SKIP in the base-less local context) — the W055
  delta introduces no new spec_check failure.
- The accepted W054 composition battery is unaffected:
  `tools/composition_selftest.py` → **55/55** (input state preserved).

### CI context (honest classification: worker-local vs CI evidence)

**Every result in this record is repository-local worker evidence,
executed from the working tree / delivery commits in this repository.
None of it is CI-derived evidence.** The conformance battery step
remains wired into CI (`python3 tools/conformance_selftest.py` in
`.github/workflows/spec-check.yml`; verified by battery case 44), but
in the live PR #15 workflow the job terminates at the first step
(`tools/spec_check.py`) with the inherited governance failures
(ARCH-02/03/04/05/06/07 in the PR merge context) **before the
conformance step executes** — the same signature as every delivery
since the R0 restoration (including the accepted W054 PR #13), and
repairing those inherited failures is outside the W055 authorized
scope. Consequently:

- the **63/63 battery result, the matrix/corpus/profile/W029 digests,
  the repeat runs, the hash-seed matrix, and the prior-battery runs
  (§12) are worker-local**, each reproducible from a fresh checkout of
  the delivery head with the exact commands in this record;
- **CI contributes no conformance evidence for this PR** — the CI
  status of PR #15 reflects the inherited spec_check failures only,
  and must not be read as either supporting or contradicting the R3
  conformance claims;
- closing R3 on the strength of CI is therefore not claimed; the
  operative evidence is this repository-local record.

---

## 12. Reproduction summary (fresh checkout of the delivery head;
worker-local execution — see §11 for the CI/local distinction)

```bash
python3 tools/conformance_selftest.py          # 63/63 PASS (byte-identical repeats)
PYTHONHASHSEED=0 python3 tools/conformance_selftest.py    # 63/63 (seeds 0/1/7919/unset)
python3 tools/composition_selftest.py          # 55/55 PASS (W054 input state intact)
python3 tools/upgrade_selftest.py              # 41/41 PASS (W029 authority intact)
python3 tools/spec_check.py                    # identical to the baseline classification
git diff --numstat 57963858e5a2b9d11faed94b50f94e058cede0a8 HEAD  # the §1 inventory
python3 -c "..."                               # matrix digest (§3), corpus digest (§5)
```

No external/network evidence is used to establish any R3 conformance
claim. No simulator or reference implementation is used as
interoperability proof. Conformance evidence remains subordinate to
the frozen protocol authorities.

## 13. Delivery record

- Ancestor (authorized baseline):
  `57963858e5a2b9d11faed94b50f94e058cede0a8` — verified mechanically
  on every battery run (case 62: `git merge-base --is-ancestor`).
- Round 1 — implementation delivery:
  `372299bfe3b54f79c0238d2927de2224249c4e36` (parent: the authorized
  baseline; 26 files, +3981/−5), superseded by round 2 in response to
  the Architect's CHANGES REQUIRED review of PR #15; the SHA remains
  quoted here as the reviewed round-1 artifact.
- Round 2 — review-correction commit:
  `f88289a95431421b8f367a9e60011405f92ca9fa` (parent: `372299b…`),
  carrying the five corrections of the first review; directly
  descended from round 1, not from the baseline; superseded as the
  branch head by round 3.
- Round 3 — documentation-correction head: exactly one additional
  commit on the same branch/PR lineage (parent: the round-2 head
  `f88289a…`), carrying only the §1 lineage-wording correction of
  the Architect's round-2 re-review (P2). The exact head SHA is
  recorded in the PR body, the PR head, and the worker worklog; the
  battery's scope/ancestry cases verify the lineage mechanically on
  every run, so the claim does not depend on this document.
- Lineage discipline: no rebase, no force over shared work, no
  cherry-picks from superseded branches — each correction is a plain
  child of the previously reviewed commit on the authorized lineage
  (the same correction-round pattern as the accepted W052
  PR #149 lineage).
