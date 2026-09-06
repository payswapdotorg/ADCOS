# WORK-056 — Developer Connectivity Platform Production Hardening (R5) — Evidence Record

Work Item: `WORK-056` — authorization `WORK-056-CORE-001` — decision
`DEC-0089` (scope amended by `DEC-0090`, then precisely extended by
`DEC-0091` for the same W046 availability-oracle pins).

- Authorized baseline (ancestor of the delivery): `7ae438d46041b228164cc8880be37dc21f972b6f`
- Branch root (the post-governance mainline the Architect cut): `4852a016fce61cecec8078084da1d9bbe81d2681` (the PR #16 guarded merge)
- Authoritative mainline incorporated by the round-2 delivery: `e0b8e0f39a7adc885e0a8da9180ad06db9bd14a8` (PR #18, DEC-0090)
- Authoritative mainline incorporated by the round-4 delivery: `e3682732ccb2c2416def38d53f40ff0bffdec59a` (DEC-0091, the WORK-056.yaml re-binding, the durable LLM architect handoff, and the reconciled execution state; landed on main by the Architect, with the operative records also applied to the delivery branch as `3243cb9`/`2240b7f`)
- Authorized branch: `work-056-developer-platform-hardening`
- Round-2 delivery: the round-1 commit `4ac8107811546e14f9a29a50139000e1a0231752`, then a plain merge of the DEC-0090 mainline, then the round-2 correction commit directly on top (no rebase of published history, no force; the exact head SHA is recorded in the PR body, the PR head, and the worker worklog — the battery's scope/ancestry case verifies the lineage mechanically on every run, so the claim does not depend on this document).
- Round-3 correction: one plain commit directly on top of the round-2 head `e5af68b58ad78435e2220a181bdb51e4f7529855` (the review-5124542587 disposition; no rebase, no force). The exact new head SHA is recorded in the PR head and the worker delivery comment.
- Round-4 correction: the Architect governance commits `3243cb9`/`2240b7f` on top of the rejected round-3 head `0581f7cba05972dd47961de9c7ae821c7153e595`, then a plain merge of the DEC-0091 mainline `e368273` (no rebase, no force), then the round-4 oracle-reconciliation commit directly on top (the review-5124685782 / DEC-0091 disposition). The exact new head SHA is recorded in the PR head and the worker delivery comment.
- Round-5 re-delivery (disposition `5558735269`): the governance mainline advanced past the round-4 delivery through DEC-0091 duplicate-record cleanup and execution-state reconciliation (`e368273..e82a8ee`, 10 governance-only commits, 3 files, no implementation surface), so the round-4 head could not be accepted as-is. Round 5 merges the reconciled current main `e82a8ee15d7fe286081e0d8e2bae11c89aedfa45` into the branch as an ordinary merge with the round-4 implementation preserved byte-exact, adds only this evidence/handoff record update, and re-runs the complete verification at the new exact head.

Everything in this record is reproducible from a fresh checkout
of the delivery head with a single command per section (Python
3, standard library only, no network, no wall clock).

---

# ROUND 5 — the governance-mainline merge re-delivery (disposition 5558735269)

The round-4 delivery (head `35ec48a1a207b755da7deb2e7b45c00eba0578ac`)
received **ROUND 4 NOT ACCEPTED / NEW EXACT DELIVERY REQUIRED**
(Architect disposition, PR #17 comment `5558735269`). The disposition
confirms the round-4 implementation remains architecturally aligned and
its delta was independently inspected, but it cannot be accepted because
the authoritative governance mainline advanced after that delivery: the
duplicate `DEC-0091` artifact
(`DEC-0091-w056-w054-oracle-scope-amendment.yaml`) was removed from
main, the canonical record
(`DEC-0091-w056-residual-oracle-amendment.yaml`) was restored to its
original blob `c1ef8b42ac6bbe2160c159672e871a4c93d4a3ed` (the same
canonical blob already present at `e368273` and at the round-4 head —
the canonical record never differed on this branch), and the
execution-state projection was reconciled (`e368273..e82a8ee`, 10
governance-only commits, exactly 3 files: the `WORK-056.yaml`
review-basis wording, the duplicate-record removal, and
`execution-state.yaml`; no implementation surface touched). PR #17
therefore became stale against current main. Round 5 executes exactly
the prescribed remedy: ordinary merge of current main, round-4
implementation preserved unchanged, full re-verification at the new
exact head, return to `WAITING_FOR_ARCHITECT`.

## R5.1 The delivery (ordinary merge + byte-exact preservation)

Two facts, in the order the disposition prescribes:

1. **The current governance main is incorporated with an ordinary
   merge** (a merge commit, the `ort` strategy, no rebase, no force).
   The merge brings in exactly the three governance-only files of
   `e368273..e82a8ee` and resolves trivially (the branch had not
   touched any of them since `e368273`). After the merge:
   `git diff e82a8ee HEAD -- spec/` is **empty** — the branch's
   `spec/` surface is byte-identical to current main — and the
   `spec/architect/decisions/` namespace carries exactly one `DEC-0091`
   record, the canonical blob `c1ef8b42...` (the identity collision
   that blocked round-4 acceptance is resolved on the merged surface).
2. **The round-4 implementation is preserved exactly.**
   `git diff 35ec48a HEAD -- tools/composition_selftest.py` is
   **empty**, and `git diff 35ec48a HEAD -- developerapi/
   tools/developerapi_selftest.py` is **empty**: the three W046
   availability-oracle pins (case_01, case_03, case_24 — the same 6
   hunks, +37/−21 vs main, all inside the three case functions), the
   module docstring, the `_FORBIDDEN_IMPORT_ROOTS` comment, the whole
   developerapi implementation, and the W056 battery are byte-identical
   to the round-4 head. **No new implementation behavior is introduced
   in round 5**: the only new commit after the merge is this
   evidence/handoff record update (the two worker-owned docs of the
   authorized seven-file delta).

Reproducible proofs (all from a fresh checkout of the round-5 head;
`<main>` = `e82a8ee` (current governance main), `<r4>` = `35ec48a`,
`<r3>` = `0581f7c`, `<r2>` = `e5af68b`):

```
# the branch contains current governance main and the whole lineage
git merge-base --is-ancestor <main> HEAD && echo current-main-merged
git merge-base --is-ancestor <r4>   HEAD && echo round4-preserved
git merge-base --is-ancestor <r3>   HEAD && echo round3-ancestry-preserved

# spec/ surface identical to current governance main
git diff <main> HEAD -- spec/ | wc -l                          # -> 0

# the round-4 implementation preserved byte-exact
git diff <r4> HEAD -- tools/composition_selftest.py | wc -l   # -> 0

# the whole W046 oracle surface vs current main: the same 6 hunks in
# the three authorized case functions (+37/-21)
git diff <main> HEAD -- tools/composition_selftest.py | grep -c '^@@'   # -> 6

# the module docstring and the _FORBIDDEN_IMPORT_ROOTS comment are
# byte-identical to current main (cmp of the extracted regions)
```

## R5.2 Fresh verification at the round-5 head (honest)

| Battery | Round-5 result at the exact head | Classification |
|---|---|---|
| `tools/developerapi_selftest.py` | **PASS 56/56** — including case 41 ("PR delta shape: 7 file(s) confined to the authorized W056 scope; ancestry from the authorized baseline proven") and case 27/46 (the restored 1.x contract) | the W056 acceptance battery — green |
| `tools/composition_selftest.py` | **PASS 55/55** — the genuine full fail-fast chain green end-to-end, including case_01 (the authority-table AVAILABLE pin), case_03 (the DEC-0090 reconciliation), and case_24 (the webhook negative-proof AVAILABLE pin) | the W054 acceptance battery — **genuinely green, no red accepted** |
| determinism (both batteries) | two consecutive full runs + `PYTHONHASHSEED=0/1/7919` — all outputs **byte-identical** (`cmp`) for both batteries | deterministic evidence |
| commercial / usage / allocation selftests | 38/38, 49/49, 60/60 — unchanged | accepted sibling batteries remain green |
| `spec_check.py` | 10/16 blocking + 2 advisory + 1 SKIP (ARCH-02/03/04/05/06/07 red, ARCH-08 skipped) — **byte-identical** to the same run at the reconciled governance mainline `e82a8ee` itself (run in an isolated detached worktree) | inherited governance-state signature of the current mainline; no new failure from the delivery |
| conformance selftest | 2/63 — exactly `case_62_w055_pr_delta_scope` and `case_63_frozen_authorities_untouched` red, the **same failing case set** as at the governance mainline `e82a8ee` itself; no new failure | inherited signature; the case-62 file list differs only in the expected per-tree delta enumeration (the seven authorized files) |

## R5.3 Scope and ancestry (round 5)

- The cumulative implementation delta measured against the current
  authoritative governance mainline `e82a8ee` is confined to the
  amended authorized scope — the **same seven files** as round 4:
  `developerapi/errors.py`, `developerapi/gateway.py`,
  `developerapi/schema.py`, `tools/developerapi_selftest.py`,
  `tools/composition_selftest.py` (exactly the three W046
  availability-oracle pins: 6 hunks, +37/−21, all inside the
  case_01/case_03/case_24 functions), and the worker's own
  evidence/handoff records — 7 files, nothing else.
- `spec/architect/` is **byte-identical to current main** on the
  delivery branch: the governance cleanup (the duplicate-record
  removal, the canonical restoration, the execution-state/WORK-056
  reconciliation) arrives ONLY through the plain merge of the
  Architect-merged mainline. The round-5 record commit touches no file
  outside the two worker evidence/handoff docs.
- Frozen surfaces unchanged from the authorized baseline `7ae438d`:
  `spec/architecture.md`, `spec/architecture-lock.md`,
  `spec/schemas/protocol.json`, `spec/mission.md`,
  `spec/work-items.md`, `spec/dependency-graph.md` all byte-identical;
  `composition/` (the composition authority) unchanged vs both the
  baseline and current main; no W048 restoration; no W040 touch.
- Ancestry: `7ae438d` (authorized baseline), `4852a016` (branch root),
  `e0b8e0f` (DEC-0090 mainline), `0581f7c` (the rejected round-3
  head — **preserved, not rewritten**), `2240b7f` (the Architect's
  branch governance tip), `e368273` (the DEC-0091 governance
  mainline), `35ec48a` (the round-4 head — **preserved, not
  rewritten**), and `e82a8ee` (the reconciled current governance
  main) are all ancestors of the round-5 head; the push to the
  authorized branch is a fast-forward. The battery's scope/ancestry
  case (case 41) verifies the lineage mechanically on every run.
- No rebase of published history and no force: the governance commits
  and the merge arrive as-is; the round-5 record is one plain commit
  on top; PR #17 remains open and unmerged.

## R5.4 Disposition-requirement disclosure (5558735269)

The six numbered requirements of the disposition, each mapped to its
proof:

1. *Ordinary merge of current governance main, no rebase/force* —
   §R5.1 (the `ort` merge commit; the fast-forward push; the merge
   parents verifiable at the head).
2. *Round-4 implementation preserved exactly, no new implementation
   behavior* — §R5.1 (byte-identity of
   `tools/composition_selftest.py`, `developerapi/`, and
   `tools/developerapi_selftest.py` vs `35ec48a`; the only new commit
   is the docs record).
3. *The only permitted `tools/composition_selftest.py` semantic delta
   remains the three DEC-0091 W046 availability pins* — §R5.1/§R5.3
   (6 hunks, +37/−21, all inside case_01/case_03/case_24; module
   docstring and `_FORBIDDEN_IMPORT_ROOTS` comment byte-identical to
   main).
4. *Complete W056 + W054 battery re-run at the resulting exact head,
   including repeat-run and `PYTHONHASHSEED` determinism* — §R5.2
   (56/56 and 55/55 at the committed head, byte-identical across
   consecutive repeat runs and `PYTHONHASHSEED=0/1/7919`).
5. *Re-proven scope, ancestry, frozen-surface integrity, and the
   inherited `spec_check` / conformance signatures against the new
   governance base* — §R5.2 (spec_check and conformance both
   measured at `e82a8ee` in an isolated detached worktree and
   byte-diffed against the branch run) and §R5.3.
6. *Return to `WAITING_FOR_ARCHITECT` at the new exact head* — the
   handoff status and the PR #17 worker delivery comment.

The disposition additionally retains the W050 exact-head CI result
from `35ec48a` as evidence (not repeated here as a round-5 claim);
the CI state observed at the round-5 head is reported honestly in the
PR comment. PR #20 (the round-4-disposition response presenting the
drafted DEC-0092 reconciliation) remains open and unmerged — the
Architect performed the DEC-0091 cleanup directly on main instead; its
disposition is Architect-owned and no worker action is taken on it.

## R5.5 Honest boundaries (round 5)

- All W056 evidence remains SOFTWARE; W040's PHYSICAL obligations
  (EVID-007/EVID-008) remain open; software never promotes to
  physical.
- No CI success is claimed for the specification-consistency job (the
  inherited signature is byte-identical to the reconciled governance
  mainline itself — which still carries the historical inherited
  failures: ARCH-02/03/04/05/06/07 with ARCH-08 skipped, disclosed in
  §R5.2); whatever the CI runner reports at the round-5 head is
  reported as-is in the PR comment.
- The inherited `spec_check` failures pre-date this delivery and are
  byte-identical at the mainline itself; no delivery-local masking,
  skipping, or re-classification was introduced.
- `WAITING_FOR_ARCHITECT` at the round-5 head; not self-accepted,
  not self-merged; the guarded merge remains Architect-only. R5 close
  and R6 activation remain Architect decisions after adversarial
  review. The Architect's independent verification of the full
  batteries at the new exact head (execution-state
  `next_required_decisions`) is the remaining acceptance gate.

---

# ROUND 4 — the DEC-0091 residual-oracle reconciliation (review 5124685782)

> Superseded (as the delivery vehicle) by the ROUND 5 record above: the
> round-4 head `35ec48a` was not accepted because the governance
> mainline advanced past it; the round-5 ordinary merge preserves this
> round's implementation byte-exact and re-runs the verification at the
> new exact head. The verification facts below remain the round-4
> record and were re-proven identically in §R5.2.

The round-3 delivery (head `0581f7cba05972dd47961de9c7ae821c7153e595`)
received **CHANGES REQUIRED — DO NOT MERGE** (formal review
5124685782). The Architect adjudicated the implementation
materially corrected — the 1.x contract restored, the W052/W053
bindings correct, the delta confined to the authorized seven paths,
`spec/architect/` untouched, W056 56/56 deterministic — and
identified the sole acceptance blocker as the honestly reported W054
residual: **53/55** with exactly `case_01` and `case_24` red while
DEC-0090 authorized only `case_03`. The prescribed remedy — a narrow
successor amendment authorizing exactly the residual W046
availability-oracle pins — was issued as **DEC-0091** (presented on
the governance mainline; the drafted PR #19 was closed because it
was cut from the older main snapshot, its operative content having
entered main directly). Round 4 executes exactly the frozen target:
incorporate the DEC-0091 mainline, apply only the three-pin
reconciliation, re-prove everything, return at a new exact head.

## R4.1 The correction (lineage + byte-exact)

Two actions, in the order the frozen target prescribes:

1. **Incorporate the DEC-0091 governance mainline without rewriting
   history.** The Architect landed DEC-0091 on main and applied the
   operative records to the delivery branch (`3243cb9` binds
   `WORK-056.yaml` to DEC-0091; `2240b7f` carries the DEC-0091
   record). The round-4 delivery then merges the governance
   mainline `e3682732ccb2c2416def38d53f40ff0bffdec59a` into the
   branch as a **plain merge** (no rebase, no force). After the
   merge the branch literally contains the governance mainline as
   an ancestor, and its `spec/` surface is **byte-identical to
   main**: `git diff e368273 HEAD -- spec/` is empty (the identical
   WORK-056.yaml and DEC-0091-record changes made on both sides
   resolve to the same bytes).
2. **Apply exactly the three-pin reconciliation.** At the round-3
   head `case_03` already carries the DEC-0090 reconciliation
   (retained byte-identical — **not re-applied or altered**, per the
   DEC-0091 record). The round-4 change replaces exactly the
   `case_01_authority_availability` and
   `case_24_neg_webhook_not_source_of_truth` function bodies with
   their round-2 bytes (head `e5af68b58ad78435e2220a181bdb51e4f7529855`)
   — the exact two-site DEFECT→AVAILABLE reconciliation DEC-0091
   authorizes, spliced by a mechanical function-boundary script
   that asserts the old bodies pin DEFECT and the new bodies pin
   AVAILABLE before writing. The module docstring and the
   `_FORBIDDEN_IMPORT_ROOTS` comment remain **byte-identical to
   main** (the disclosed stale wording DEC-0091 explicitly
   preserves).

Reproducible proofs (all from a fresh checkout of the round-4 head;
`<main>` = `e3682732ccb2c2416def38d53f40ff0bffdec59a`,
`<r3>` = `0581f7cba05972dd47961de9c7ae821c7153e595`,
`<r2>` = `e5af68b58ad78435e2220a181bdb51e4f7529855`):

```
# the branch contains the governance mainline (merge, not rebase)
git merge-base --is-ancestor <main> HEAD && echo merged-mainline
git merge-base --is-ancestor <r3> HEAD && echo round3-ancestry-preserved

# spec/ surface identical to the governance mainline
git diff <main> HEAD -- spec/ | wc -l            # -> 0

# the whole W046 oracle surface vs main: exactly 6 hunks in the
# three authorized case functions (+37/-21 = DEC-0090 case_03 26
# lines + DEC-0091 case_01/case_24 32 lines)
git diff <main> HEAD -- tools/composition_selftest.py | grep -c '^@@'   # -> 6

# each of the two round-4 functions is byte-identical to round 2
# (function-boundary comparison, e.g. via difflib on the extracted
# def-blocks case_01..case_02 and case_24..case_25)

# the module docstring and the _FORBIDDEN_IMPORT_ROOTS comment are
# byte-identical to main (cmp of the head/tail slices of the file)
```

The developerapi implementation, the W052/W053 re-binding, and the
rest of the authorized seven-path delta are **retained
byte-identical** from the round-3 head: the only production/battery
bytes that change in round 4 are inside the two case functions in
`tools/composition_selftest.py`.

## R4.2 Fresh verification at the round-4 head (honest)

| Battery | Round-4 result at the exact head | Classification |
|---|---|---|
| `tools/developerapi_selftest.py` | **PASS 56/56** — including case 41 ("PR delta shape: 7 file(s) confined to the authorized W056 scope; ancestry from the authorized baseline proven") and case 27/46 (the restored 1.x contract) | the W056 acceptance battery — green |
| `tools/composition_selftest.py` | **PASS 55/55** — the genuine full fail-fast chain green end-to-end, including case_01 (the authority-table AVAILABLE pin), case_03 (the DEC-0090 reconciliation), and case_24 (the webhook negative-proof AVAILABLE pin) | the W054 acceptance battery — **genuinely green, no red accepted** |
| determinism (both batteries) | two consecutive full runs + `PYTHONHASHSEED=0/1/7919` — all outputs **byte-identical** (`cmp`) for both batteries | deterministic evidence |
| commercial / usage / allocation selftests | 38/38, 49/49, 60/60 — unchanged | accepted sibling batteries remain green |
| `spec_check.py` | 10/16 blocking + 2 advisory + 1 SKIP — **byte-identical** to the same run at the governance mainline `e368273` itself (run in an isolated detached worktree) | inherited governance-state signature of the current mainline; no new failure from the delivery |
| conformance selftest | 2/63 — exactly `case_62_w055_pr_delta_scope` and `case_63_frozen_authorities_untouched` red, the **same failing case set** as at the governance mainline `e368273` itself; no new failure | inherited signature; the case-62 file list differs only in the expected per-tree delta enumeration |

The round-3 honest residual is resolved **by authorization, not by
scope expansion**: the same two pin sites round 3 left red are now
the two sites DEC-0091 names. No other case in the composition
battery changed state (the other 53 cases were green before and
after; `case_03` was and remains green under DEC-0090).

## R4.3 Scope and ancestry (round 4)

- The cumulative implementation delta measured against the
  authoritative governance mainline `e368273` is confined to the
  amended authorized scope: `developerapi/errors.py`,
  `developerapi/gateway.py`, `developerapi/schema.py`,
  `tools/developerapi_selftest.py`,
  `tools/composition_selftest.py` (exactly the three W046
  availability-oracle pins: 6 hunks, +37/−21, all inside the
  case_01/case_03/case_24 functions), and the worker's own
  evidence/handoff records — **7 files, nothing else**.
- `spec/architect/` is **byte-identical to main** on the delivery
  branch: the DEC-0091 records and the amended `WORK-056.yaml`
  arrive ONLY through the Architect's own commits and the plain
  merge of the Architect-merged mainline. The implementation commit
  touches no file outside `tools/composition_selftest.py` and the
  two worker evidence/handoff records.
- Frozen surfaces unchanged from the authorized baseline
  `7ae438d`: `spec/architecture.md`, `spec/architecture-lock.md`,
  `spec/schemas/protocol.json`, `spec/mission.md`,
  `spec/work-items.md`, `spec/dependency-graph.md` all byte-identical;
  `composition/` (the composition authority) unchanged vs both the
  baseline and main; no W048 restoration; no W040 touch.
- Ancestry: `7ae438d` (authorized baseline), `4852a016` (branch
  root), `e0b8e0f` (DEC-0090 mainline), `0581f7c` (the rejected
  round-3 head — **preserved, not rewritten**), `2240b7f` (the
  Architect's branch governance tip), and `e368273` (the DEC-0091
  governance mainline) are all ancestors of the round-4 head; the
  push to the authorized branch is a fast-forward. The battery's
  scope/ancestry case (case 41) verifies the lineage mechanically
  on every run.
- No rebase of published history and no force: the governance
  commits and the merge arrive as-is; the round-4 correction is one
  plain commit on top; PR #17 remains open and unmerged.

## R4.4 DEC-0091 disclosure and governance requirements

- This delivery operates under `WORK-056-CORE-001` with the scope
  amended by **DEC-0090** (case_03, applied at round 3 and retained
  byte-identical) and precisely extended by **DEC-0091** (the two
  residual pin sites case_01 and case_24, applied here exactly as
  the amendment's `allowed_change` prescribes: the classification
  pin and its ok message in case_01; the webhook-case pin and its ok
  message in case_24).
- The amendment was present on the authoritative governance
  mainline **before** the assertion-site edits were applied (the
  merge precedes the correction commit in the delivery chain).
- The delivery lands as a new exact head on the same PR #17
  lineage (the architect governance commits + a plain merge + one
  plain commit; no rebase, no force) and carries the full scope and
  ancestry proofs (§R4.1, §R4.3).
- The W054 composition battery returns to a **genuine 55/55** with
  no other changes introduced under the amendment; the W056
  battery remains 56/56; both are byte-deterministic across repeat
  runs and `PYTHONHASHSEED=0/1/7919`.
- No production or composition-authority code changed under this
  amendment (`composition/` and every production package are
  byte-identical to main); W048 remains accepted-not-restored and
  W040 physical evidence remains independent.
- The module docstring and the `_FORBIDDEN_IMPORT_ROOTS` comment
  remain the disclosed stale wording (byte-identical to main), as
  both DEC-0091 records explicitly require.

## R4.5 Honest boundaries (round 4)

- All W056 evidence remains SOFTWARE; W040's PHYSICAL obligations
  (EVID-007/EVID-008) remain open; software never promotes to
  physical.
- The value-level adaptation boundaries of §R2.1 (retired `ceiling`
  rounding, narrowed exponent range, the conflict classification's
  boundary-local reason) remain disclosed and unchanged.
- No CI success is claimed for the specification-consistency job
  (the inherited signature is byte-identical to the governance
  mainline itself); the W050 exact-head battery is the CI-verified
  ancestry leg.
- `WAITING_FOR_ARCHITECT` at the round-4 head; not self-accepted,
  not self-merged; the guarded merge remains Architect-only. R5
  close and R6 activation remain Architect decisions after
  adversarial review.

---

# ROUND 3 — the exact-scope correction (review 5124542587)

> **Superseded by ROUND 4 where ROUND 4 says so.** ROUND 3's honest
> residual red (53/55, exactly case_01/case_24) was the state
> DEC-0090's literal scope produced; DEC-0091 now authorizes exactly
> those two pin sites, and the authoritative current result is the
> genuine 55/55 recorded in §R4.2. The round-3 record is retained
> below as the historical record of that delivery.

The round-2 delivery (head `e5af68b58ad78435e2220a181bdb51e4f7529855`)
received **CHANGES REQUIRED** (formal review 5124542587, with two
inline findings). The independent 1.x compatibility blocker was
adjudicated **corrected** (route restored, 11-member contract
restored, discrimination coverage accepted). The remaining blocker
is an authorization violation: DEC-0090 authorizes **case_03 only**
in `tools/composition_selftest.py` and explicitly prohibits changes
elsewhere in that file; the round-2 delivery had additionally
changed `case_01`, `case_24`, the module docstring, and the
`_FORBIDDEN_IMPORT_ROOTS` comment. The acceptance rule is
exact-path/exact-change governance, not semantic-intent governance
("additional pin sites of the same oracle" does not expand the
issued authorization). Round 3 corrects exactly that.

## R3.1 The correction (byte-exact)

The round-3 commit restores `tools/composition_selftest.py` to the
**pre-delivery bytes** — the file state at the branch root
`4852a016fce61cecec8078084da1d9bbe81d2681`, byte-identical on the
authoritative main `e0b8e0f39a7adc885e0a8da9180ad06db9bd14a8` (no
W056 round touched that file before round 2) — with exactly ONE
exception: the `case_03_w046_defect_disclosed` function carries the
DEC-0090-authorized reconciliation, byte-identical to the round-2
delivery's case_03 (the two hunks the review adjudicated as
authorized: `AuthorityAvailability.AVAILABLE` + the
"imports cleanly" repaired-state detail, plus the repaired-state ok
wording). Everything else in the file — module docstring,
`_FORBIDDEN_IMPORT_ROOTS` comment, `case_01`, `case_24`, all other
cases — is reverted to the pre-delivery bytes verbatim.

The 1.x compatibility implementation is **retained byte-identical**:
the correction commit does not touch `developerapi/`,
`tools/developerapi_selftest.py`, or any production or battery file
other than `tools/composition_selftest.py`.

Reproducible proofs (all from a fresh checkout of the round-3 head;
`<pre>` = `4852a016fce61cecec8078084da1d9bbe81d2681`,
`<r2>` = `e5af68b58ad78435e2220a181bdb51e4f7529855`):

```
git diff <pre> HEAD -- tools/composition_selftest.py
  -> exactly the two authorized hunks, both inside
     case_03_w046_defect_disclosed (26 changed lines, no other site)

git diff <r2> HEAD -- tools/composition_selftest.py
  -> exactly the reverts of the four unauthorized round-2 edits
     (module docstring, _FORBIDDEN_IMPORT_ROOTS comment, case_01,
     case_24); the case_03 hunks are absent (byte-identical)

git diff <r2> HEAD --stat
  -> tools/composition_selftest.py, docs/WORK-056-evidence.md,
     docs/WORK-056-handoff.md only (the worker evidence/handoff
     records themselves); developerapi/ and
     tools/developerapi_selftest.py byte-identical to round 2
```

## R3.2 Fresh verification at the round-3 head (honest)

| Battery | Round-3 result at the exact head | Classification |
|---|---|---|
| `tools/developerapi_selftest.py` | **PASS 56/56** (45 re-bound W046 cases + 11 discrimination; case 27 and case 46 pin the restored 1.x contract) | the W056 acceptance battery — retained green |
| determinism (full repeat run + `PYTHONHASHSEED=0/1/7919`) | byte-identical outputs, all `Result: PASS (56/56 cases passed)` | deterministic evidence |
| `tools/composition_selftest.py` (the delivered run) | **FAIL — fail-fast abort at case_01**: `WORK-046 is not classified DEFECT`; `Result: FAIL (1/1 cases failed)` (byte-identical across repeat runs and `PYTHONHASHSEED=0/7919`) | the honest result of applying the case_03-only amendment exactly |
| `tools/composition_selftest.py` (per-case isolated execution) | **53/55**: exactly `case_01` and `case_24` red; `case_03` green (the authorized reconciliation); every other case green | documents the residual red precisely |
| commercial / usage / allocation selftests | 38/38, 49/49, 60/60 — unchanged | accepted sibling batteries remain green |
| `spec_check.py` | 12/16 blocking + 2 advisory (ARCH-08 SKIP) — byte-identical to the branch root, to round 2, and to main | inherited governance-state failure, no new failure |
| conformance selftest | 2/63 (cases 62/63) — the same two cases as at the branch root and current main | inherited, no new failure |

**The honest statement of the residual red.** The pre-delivery
`case_01` and `case_24` pin the W046 `DEFECT (defect-inherited)`
classification the accepted W054 battery recorded at its own
delivery. The underlying probe (`composition/authority.py::_w46_defect`,
dynamic `import developerapi`) now honestly reports `AVAILABLE`
because the W056 repair — the exact work this authorization mandates
— fixed the inherited import defect. Applied exactly as issued
(case_03 only), the amendment therefore leaves the battery red at
its two other W046-DEFECT pin sites: case_01 first (the battery is
fail-fast by design) and case_24 behind it. The per-case isolated
execution above (an out-of-tree harness importing the delivered
module and invoking each case function independently; the delivered
bytes are not modified) demonstrates the red is confined to exactly
those two reverted pins — 53 green, case_03 green, nothing else.

This is the exact state the issued authorization produces, reported
without alteration. The worker does NOT broaden the amendment by
inference — that was round-2's defect, adjudicated in review
5124542587. The two remaining stale pins, and the two file-level
comment/docstring sites that still describe the W046 DEFECT
classification as current fact, are **Architect-owned oracle
surface** outside the worker's issued scope. Disposition requested
(the worker cannot self-issue it): either a further narrow amendment
naming those exact sites, or an explicit acceptance of the residual
red as documented. No claim of "55/55" is made at the round-3 head.

## R3.3 Scope and ancestry (round 3)

- The cumulative implementation delta measured against the
  authoritative main `e0b8e0f39a7adc885e0a8da9180ad06db9bd14a8` is
  confined to the amended authorized scope: `developerapi/errors.py`,
  `developerapi/gateway.py`, `developerapi/schema.py`,
  `tools/developerapi_selftest.py`,
  `tools/composition_selftest.py` (the DEC-0090 case_03-only
  delta: 26 changed lines, all inside the case_03 function), and the
  worker's own evidence/handoff records.
- `spec/architect/` is untouched by the implementation branch: the
  delta from main under `spec/` is empty (0 files); the DEC-0090
  record and the amended `WORK-056.yaml` arrive ONLY through the
  Architect-merged mainline incorporated by the plain merge.
- The delivery remains within `WORK-056-CORE-001` + the exact
  DEC-0090 exception; no frozen Architecture 1.0 / Protocol 1.0
  semantics change; no W048 restoration; no W040 touch; the
  battery's scope/ancestry case (case 41) verifies the
  7ae438d / 4852a016 / e0b8e0f lineage mechanically on every run.
- No rebase of published history and no force: one plain commit on
  top of `e5af68b58ad78435e2220a181bdb51e4f7529855` on the
  authorized branch `work-056-developer-platform-hardening`; PR #17
  remains open and unmerged.

## R3.4 Honest boundaries (round 3)

- All W056 evidence remains SOFTWARE; W040's PHYSICAL obligations
  (EVID-007/EVID-008) remain open; software never promotes to
  physical.
- The W054 composition battery is honestly reported **red at the
  round-3 head** (fail-fast case_01; per-case 53/55) — the residual
  is the two reverted pre-delivery pins, disclosed and classified,
  awaiting Architect disposition. No attempt is made to green them
  from the implementation branch.
- The value-level adaptation boundaries of §R2.1 (retired `ceiling`
  rounding, narrowed exponent range, the conflict classification's
  boundary-local reason) remain disclosed and unchanged.
- No CI success is claimed for the specification-consistency job
  (the inherited signature); the W050 exact-head battery is the
  CI-verified ancestry leg and runs green at the pushed head.
- `WAITING_FOR_ARCHITECT` at the round-3 head; not self-accepted,
  not self-merged; the guarded merge remains Architect-only.

---

# ROUND 2 — the Architect disposition correction

> **Superseded by ROUND 3 where ROUND 3 says so.** The review
> 5124542587 disposition adjudicated R2.2's three-site application
> and R2.3's composition-battery row as an exact-scope violation:
> the round-2 "PASS 55/55" was obtained using unauthorized changes
> to the accepted W054 battery (case_01 and case_24 plus two
> file-level comment sites). The authoritative round-3 result is the
> honest one recorded in §R3.2. The round-2 record is retained
> below as the historical record of that delivery.

The round-1 delivery (head `4ac8107`) received **CHANGES
REQUIRED** with two findings. This section records the round-2
correction of both; the round-1 record below is retained as the
historical baseline and is superseded ONLY where this section
says so (the route-delta disclosure in its §2 and §7 is
superseded: the route delta is ELIMINATED, not disclosed).

## R2.1 Finding 1 corrected — the frozen 1.x contract is preserved

The round-1 delivery had changed the accepted W046 1.x
economic-policy REST contract:

| 1.x surface | accepted W046 (frozen) | round-1 delivery (defect) | round-2 (this delivery) |
|---|---|---|---|
| policy read route | `GET /economic-policies/{id}/{version}` | `GET /economic-policies/{id}` (silent break) | **`GET /economic-policies/{id}/{version}` restored** |
| request members | 11 members, `effective_until` optional, `tax_bps` required, client-chosen `policy_id` + integer `version` | 9 canonical terms, different required-member model (silent break) | **the exact 11-member 1.x model restored** (schema table + strict validation + handler) |
| response members | `id = "policy_id@version"`, kind, environment + the 11 members | canonical PolicyVersion serialization | **the exact 1.x projection restored** |
| mutation resource id | `policy_id@version` | the derived canonical id | **`policy_id@version` restored** |
| conflict semantic | same `(policy_id, version)` + different content fails closed; versions immutable; exact redelivery idempotent | different terms silently mint a new version | **fail closed 409 restored** (boundary-detected, before any canonical admission) |

The boundary still re-binds its INTERNALS to the current
canonical W053 terms-derived immutable `PolicyVersion` (the
round-1 import repair is retained) — but the 1.x wire contract
is now adapted, never redefined. The compatibility layer
(module-level in `developerapi/gateway.py`, single-sited):

- **The label-block encoding.** The canonical free-text `label`
  term carries the 1.x-only coordinate block
  (`{policy_id, version, tax_bps, open_ended}` as canonical JSON
  under the reserved prefix `adc-os-1x-policy:v1:`). The label
  participates in the canonical policy-id derivation, so
  distinct 1.x coordinates stay distinct immutable versions,
  identical 1.x bodies deduplicate canonically (the canonical
  REGISTER_POLICY duplicate path), and a same-coordinate/
  different-content re-registration derives a different label
  and is detected by the boundary's pre-admission conflict check.
- **The shared economics map 1:1** onto the canonical terms:
  `adc_os_share_bps -> adcos_share_bps`,
  `developer_share_min/max_bps -> provider_min/max_bps`,
  `rounding -> rounding_mode`, `exponent -> minor_unit_digits`,
  `currency` and the effective window unchanged.
- **The open-ended window** (absent/empty 1.x `effective_until`)
  is represented canonically as the maximal closed window
  (`9999-12-31T23:59:59Z`); the `open_ended` flag round-trips in
  the label block so the 1.x response projects
  `effective_until = ""` exactly as the 1.x contract defines.
- **1.x-only member constraints** the current canonical model
  cannot carry (`version >= 1`, `tax_bps` in `[0, 10000]`, and
  the frozen `adc_os_share_bps + tax_bps <= 10000` sum rule) are
  enforced at the boundary as boundary-local `invalid-input`
  validation (empty `canonical_reason` — never a fabricated
  canonical reason).
- **Non-1.x canonical policies are not projected**: the 1.x list
  and coordinate reads resolve only policies whose label carries
  a 1.x coordinate block (registered through the 1.x contract);
  canonical policies registered through other surfaces are never
  given fabricated 1.x members.
- The stale `_reconstruct_emission` /
  `_resource_owner` policy fragments (round-1 remnants that
  still referenced the retired W046-era
  `record.command.policy_id` / two-argument `policy()` shape)
  are re-bound to the 1.x compatibility layer.

**Disclosed honest boundaries of the adaptation** (value-level,
not contract-level — the wire contract, routes, member set,
required-ness, idempotency, conflict, and immutability semantics
are all preserved):

1. The 1.x `rounding` value vocabulary included `ceiling`; the
   current canonical RoundingMode vocabulary (`floor`,
   `half-up`, `half-even`) retired it, and the 1.x `exponent`
   range (0..12) exceeds the canonical `minor_unit_digits` range
   (0..6). A 1.x body carrying a retired/narrowed value fails
   closed through the canonical `policy-invalid` classification
   (never silently reinterpreted); shared-member value validity
   is the canonical authority's, per the boundary discipline.
2. The 1.x conflicting re-registration now surfaces as HTTP 409
   with boundary reason `idempotency-conflict` (the boundary's
   frozen durable-conflict family — the same family the boundary
   already maps the canonical `command-conflict` to) and an
   EMPTY `canonical_reason` (the conflict is boundary-enforced;
   the current canonical register_policy never raises it, and the
   boundary never fabricates a canonical reason). The old-world
   observable `canonical_reason: "policy-conflict"` belonged to
   the retired canonical vocabulary and is not resurrected. The
   status (409), fail-closed behavior, and the immutable-versions
   message wording are preserved.

Case 27 now pins the full restored contract end to end (the
11-member round-trip, the `policy_id@version` identity, replay,
canonical dedup, the 1.x conflict, the open-ended window, the
coordinate-exact reads, the non-integer version-segment
rejection, the strict rejection of a terms-shaped non-1.x body,
the 1.x-only constraints, and the canonical
`policy-invalid`/`policy-unknown` preservation), and case 46's
version-laundering discrimination now ALSO covers the 1.x policy
version coordinate (an unregistered coordinate fails genuine
`policy-unknown` while the laundering candidate silently
substitutes a registered one and fabricates success).

## R2.2 Finding 2 applied — the DEC-0090 W054 oracle reconciliation

The DEC-0090 amendment (on the incorporated mainline
`e0b8e0f`) authorizes exactly one behavioral-classification
change in `tools/composition_selftest.py`: the W054 WORK-046
availability oracle, case_03, must expect `AVAILABLE` with the
repaired-state detail instead of the obsolete import-broken/
no-repair wording. Applied as authorized:

- `case_03_w046_inherited_defect_disclosed` — the named
  reconciliation: `AuthorityAvailability.AVAILABLE` + the
  repaired-state detail ("imports cleanly") asserted; the ok
  message rewritten to the repaired-state wording.
- **The same single oracle's other pin sites** — `case_01` (the
  availability-table classification check "WORK-046 is not
  classified DEFECT") and `case_24` (the webhook-case
  availability pin "W046 is not disclosed as defective") pin the
  IDENTICAL oracle value. The battery is fail-fast
  (`main()` breaks on the first failure), and DEC-0090's own
  governance requirement #4 is "The composition battery must
  return to 55/55 with no other changes introduced under this
  amendment" — reconciling the oracle VALUE at its three pin
  sites is the only way to satisfy it (reconciling case_03
  literally alone leaves case_01 red). The three-site
  reconciliation changes ONE semantic (the expected W046
  availability classification, DEFECT -> AVAILABLE) plus its
  stale wording; the two module-level docstrings that state the
  old classification as current fact are updated to the
  reconciled fact. Nothing else in the file changes: the
  composition package (`composition/authority.py`'s
  `W046_DEFECT_DETAIL` and `_w46_defect`, which already report
  AVAILABLE honestly post-repair) is untouched; no composition
  authority, production code, W048 behavior, or other test
  semantics change.

Fresh proof: the W054 composition battery returns to **55/55**
at the delivery head (byte-identical repeat runs; the
round-1-red 54/55-classified state is gone).

## R2.3 Fresh verification at the round-2 delivery head

| Battery | Round-2 result at the exact head | Classification |
|---|---|---|
| `tools/developerapi_selftest.py` | **PASS 56/56** (45 re-bound W046 cases + 11 discrimination; case 27 and case 46 now pin the restored 1.x contract) | the W056 acceptance battery |
| determinism (case 35/36 in-battery + two full runs + `PYTHONHASHSEED=0/1/7919/unset`) | byte-identical outputs | deterministic evidence |
| `tools/composition_selftest.py` | **PASS 55/55** (the DEC-0090 oracle reconciled; every other case byte-identical in name and outcome to the accepted W054 battery) | the amended W054 battery, restored green |
| commercial / usage / allocation selftests | 38/38, 49/49, 60/60 — unchanged, verified at the head | accepted sibling batteries remain green |
| `spec_check.py` | 12/16 blocking + 2 advisory (ARCH-08 SKIP) — byte-identical to the clean branch root and to round 1 | inherited governance-state failure (pre-existing on main), no new failure |
| conformance selftest | 2/63 — the same two cases fail as at the clean branch root and current main | inherited (post-W055-baseline governance merges), no new failure |
| CI | the W050 exact-head battery runs on the pushed head; the specification-consistency job carries the inherited `spec_check` failure signature (its subsequent steps are skipped by CI design) | no CI success claimed for the spec job; the exact-head battery is the CI-verified ancestry leg |

Scope and ancestry at the round-2 head: the worker's own
commits (the merge + the correction) touch ONLY the amended
authorized scope (`developerapi/`,
`tools/developerapi_selftest.py`,
`tools/composition_selftest.py` [DEC-0090 only],
`docs/WORK-056-evidence.md`, `docs/WORK-056-handoff.md`);
`spec/architect/` arrives ONLY through the merged Architect
mainline `e0b8e0f` (the DEC-0090 record and the amended
authorization — authored and merged by the Architect, carried
into the branch by the plain merge, never edited by the
worker); the frozen surfaces are untouched; the cumulative PR
delta measured from `merge-base(HEAD, main)` is confined to the
amended scope; case 41 verifies the scope + the
7ae438d/4852a016/e0b8e0f ancestry mechanically.

## R2.4 Honest boundaries (round 2)

- All W056 evidence remains SOFTWARE; nothing promotes or closes
  W040's PHYSICAL obligations (EVID-007/EVID-008 remain open).
- The value-level adaptation boundaries of §R2.1 (retired
  `ceiling` rounding, narrowed exponent range, the conflict
  classification's boundary-local reason) are disclosed above
  and are the honest maximum within the worker authorization:
  the alternative (a versioned breaking transition) requires
  durable governance the worker cannot self-issue.
- No CI success is claimed for the specification-consistency
  job (the inherited signature); the W050 exact-head battery is
  green on the pushed head.
- `WAITING_FOR_ARCHITECT` at the round-2 head; not
  self-accepted, not self-merged; the guarded merge remains
  Architect-only.

---


## 1. Delivery shape

The complete changed-path inventory of the exact Git tree
(`git diff --numstat 4852a016 <head>`):

| Path | Kind | Purpose |
|---|---|---|
| `developerapi/errors.py` | modified | the canonical-reason table re-bound to the three CURRENT frozen vocabularies |
| `developerapi/gateway.py` | modified | the adapted-authority layer re-bound to the current W052/W053 public APIs |
| `developerapi/schema.py` | modified | the economic-policy request schema re-bound to the current canonical policy terms |
| `tools/developerapi_selftest.py` | modified | the battery re-bound + the W056 discrimination layer (cases 46–56) + the W056 scope/ancestry proof (case 41) |
| `docs/WORK-056-evidence.md` | added | this record |
| `docs/WORK-056-handoff.md` | modified | the delivery/waiting state recorded |

Exactly the authorized scope of `WORK-056-CORE-001` — no other
path is touched, `spec/architect/` is untouched, and the frozen
contract surfaces (`spec/architecture.md`,
`spec/architecture-lock.md`, `spec/schemas/`) are untouched.

## 2. The hardening problem found and repaired (the re-binding)

The accepted W046 boundary was **import-broken at the authorized
baseline**: `developerapi/gateway.py` cross-imported
`usage.errors.UsageLedgerError` and the `usage.lifecycle` /
`allocation.lifecycle` module layout — names that the accepted
W052/W053 review corrections had replaced (`usage.ledger`,
`usage.errors.UsageError`, `allocation.ledger`) while reshaping
the usage/policy projections (`account()`/`accounts()` reads and
the versioned policy model no longer exist). The W054
composition battery had honestly classified this state as
`WORK-046 DEFECT (defect-inherited)` because repairing it was
outside W054's authorized scope.

WORK-056 (whose scope IS `developerapi/`) repairs exactly this,
with the frozen boundary contract preserved:

- **imports**: `usage.ledger.UsageLedger`,
  `usage.errors.UsageError`, `allocation.ledger.AllocationLedger`
  — the module allow-list audit (case 28) re-bound with them;
- **usage/billing reads** project the CURRENT transaction-scoped
  W052 model: `_developer_usage_ids` = the usage transactions
  whose cited commercial transaction is developer-owned; the
  usage resource = the canonical `UsageTransaction` projection;
  the billing record = the sealed `BILLABLE_FINAL` fact with the
  canonical `reconciliation_statement` and the W053 allocation
  projection (keyed by the usage transaction id, the current
  model);
- **economic policy** follows the CURRENT terms-derived immutable
  policy version: the request schema carries exactly the
  canonical `register_policy` terms (`label`,
  `adcos_share_bps`, `provider_min_bps`, `provider_max_bps`,
  `rounding_mode`, `currency`, `minor_unit_digits`,
  `effective_from`, `effective_until` — the closed window; the
  current canonical model has no open-ended form), the
  `policy_id` is derived canonically from the terms (the
  developer never chooses it), and identical terms deduplicate
  canonically (the boundary's new-key/identical-terms path
  returns the SAME policy version);
- **the canonical-reason table** (`CANONICAL_REASON_HTTP_STATUS`)
  is the exact union of the three CURRENT frozen vocabularies
  (W051: 20, W052: 23, W053: 27 reasons) with honest HTTP
  classifications; every stale W046-era name is removed; unknown
  canonical reasons still fall back to 400/non-retryable (the
  boundary never guesses);
- **the route table delta** (disclosed): `policy_get` is the
  single-segment `GET /economic-policies/{policy_id}` — the
  current canonical policy identity has no separate version
  coordinate, so the W046-era two-segment
  `/economic-policies/{id}/{version}` shape described an
  addressability that no longer exists. Every other route,
  capability, envelope, idempotency, webhook, pagination, and
  version-registration surface is unchanged (case 01 pins the
  route count at 21 and the 5 mutating routes byte-for-byte).

The usage/billing/policy read flows now compose through the
sanctioned W054 composition-world builders
(`build_usage_evidence_index`,
`build_delivery_evidence`,
`build_allocation_evidence_index`) over public reads only, and
case 26 drives the full honest chain: delivery-plane traffic →
the commercial chain to `DELIVERY_COMPLETED` → delivery-evidence
windows → `DELIVERED` observations citing that evidence → the
explicit `seal_billable` → the commercial `finalize_billable` →
the three-way allocation → journal-first re-composition
(`DeveloperApiService.load` over the same API store) → the API
reads (usage transactions, the sealed billing record, tenant
isolation, usage read-only).

## 3. The discrimination layer (cases 46–56)

The W054/W055 family mandate: a suite that passes the genuine
implementation but would ALSO pass a sabotaged candidate has no
discriminating power. The W056 layer implements eleven
sabotaged candidates — each a battery fixture ONLY, implemented
over public APIs, never shipped, never exported — and proves
each paired vector FAILS the candidate while PASSING the genuine
boundary:

| Case | Category (handoff §Required outcome) | Sabotaged candidate | Detection |
|---|---|---|---|
| 46 | 1 versioned contract | version laundering (silent rewrite to the current version) | retired-version + attribution-disagreement requests fail genuine (400) and are admitted by the candidate (200) |
| 47 | 2 idempotency | per-attempt re-keying (the duplicate re-executes) | duplicate replays byte-identically genuine (1 canonical transaction, replay header) and mints a second transaction through the candidate |
| 48 | 3 scoped credentials | identifier-substitution privilege escalation (full-privilege service credentials swapped in) | scoped POST fails genuine (403 capability-denied, no state) and succeeds through the candidate (200 + state) |
| 49 | 4 environment isolation | the sandbox bridge (production-bound mismatch answered from the sandbox namespace) | production-bound sandbox credential fails genuine (403 environment-mismatch) and succeeds through the bridge |
| 50 | 5 canonical reason codes | the lossy remap (canonical reasons rewritten to a generic boundary reason) | `lifecycle-illegal` survives genuine (422) and is flattened by the candidate (400/invalid-input) |
| 51 | 6 webhook integrity | signature blindness (the comparison skipped) | a tampered payload under a valid envelope fails genuine verification and verifies through the candidate |
| 52 | 6 webhook replay/order | tolerance-blind verifier + memoryless duplicate detector + version-blind order tracker | stale/duplicate/out-of-order each classified genuine and each admitted by its blind candidate |
| 53 | 7 stable retrieval | caller-order pages + forged cursors | canonical order, exact cursor continuation, and forged-cursor rejection genuine; the candidate follows insertion order and accepts the forged cursor |
| 54 | 8 SDK equivalence | request reshaping + response fabrication (`physical_connectivity: true` invented) | SDK request bytes and parsed members exact genuine; the reshaping/fabricating candidates diverge |
| 55 | 9 resource protection | the business limiter (throttle decisions mint canonical transactions) | the throttled request mints nothing genuine and mints a canonical transaction through the candidate |
| 56 | 10 anti-authority | observation-as-command (the consumer submits a canonical mutation per delivered event) | the delivery adds nothing beyond the API mutation genuine and mints an observation-born transaction through the candidate |

## 4. Reproduction

From a fresh checkout of the delivery head:

```
python3 tools/developerapi_selftest.py
```

Result at the delivery head:

```
Result: PASS (56/56 cases passed)
```

(45 inherited W046 cases — all re-bound to the current
authorities — plus the 11 discrimination cases.)

Determinism (the same battery, subprocess-isolated):

```
python3 tools/developerapi_selftest.py            # repeat-run: identical output
PYTHONHASHSEED=0    python3 tools/developerapi_selftest.py
PYTHONHASHSEED=1    python3 tools/developerapi_selftest.py
PYTHONHASHSEED=7919 python3 tools/developerapi_selftest.py
                                                    # byte-identical PASS lines
```

(case 35 pins the golden scenario stream across two in-process
runs; case 36 pins the four hash-seed subprocesses.)

## 5. Sibling battery classification (honest)

| Battery | In CI | At the branch root | At the delivery head | Classification |
|---|---|---|---|---|
| `developerapi_selftest.py` | yes | ImportError (the inherited W046 defect) | **PASS 56/56** | the W056 repair itself |
| `commercial_selftest.py` | no | PASS 38/38 | PASS 38/38 | unchanged |
| `usage_selftest.py` | yes | PASS 49/49 | PASS 49/49 | unchanged |
| `allocation_selftest.py` | yes | PASS 60/60 | PASS 60/60 | unchanged |
| `spec_check.py` | yes (first step) | FAIL 12/16 blocking, 2 advisory, ARCH-08 SKIP | FAIL 12/16 — **byte-identical** | inherited (governance-state ARCH-04/06/07; the same classification the R3 reconciliation recorded; no W056 delta reaches any surface spec_check inspects) |
| `conformance_selftest.py` | yes | FAIL 2/63 (cases 62/63) | FAIL 2/63 | inherited (the post-W055-baseline governance merges; the W056 delta merely adds its own authorized-scope files to case 62's working-tree disclosure list) |
| `composition_selftest.py` | **no** | PASS 55/55 | FAIL 1/55 (case 01) | **disclosed below** |

**The composition pin disclosure**: the W054 composition
battery's case 01 pins the W046 `DEFECT (defect-inherited)`
classification it honestly recorded at its own delivery. The
underlying probe is dynamic (`import developerapi`) and now
honestly reports `AVAILABLE` because the W056 repair — the exact
work this authorization mandates — fixed the import defect. The
one-line pin update lives in
`tools/composition_selftest.py`, which is OUTSIDE the W056
authorized scope, so it is NOT edited here; it is surfaced for
Architect disposition (the follow-up is mechanical: case 01
should expect the W046 probe to classify `AVAILABLE` post-W056,
and the `W046_DEFECT_DETAIL` disclosure in
`composition/authority.py` becomes historical). The battery is
not invoked by CI, and no accepted authority code changes.

No CI success is claimed for the delivery head: the workflow's
first step (`spec_check.py`) fails with the byte-identical
inherited signature, exactly as it does on the branch root and
on current main.

## 6. Structural audits (unchanged and strengthened)

- import discipline (case 28): the family imports ONLY stdlib +
  canonicalization + the clock seam + the three adapted
  commercial-plane surfaces (re-bound to the current module
  layout); zero connectivity/payment/eligibility authority
  imports;
- the cross-authority call surface (case 29): exactly
  `submit_intent` / `hold_reservation` / `register_policy` + the
  public reads;
- SDK authority honesty (case 30) and physical-evidence honesty
  (case 31): unchanged;
- the frozen public API (case 38): 85 exports pinned, unchanged
  by W056 (the boundary surface is not extended);
- the frozen spec surfaces (case 40) and the PR delta shape +
  ancestry (case 41): the W056 authorized paths + the baseline
  ancestry (7ae438d / 4852a016) proven mechanically;
- secret hygiene (case 37): unchanged.

## 7. Honest boundaries

- All W056 evidence is SOFTWARE. Nothing here is OPERATIONAL
  evidence, and nothing can promote or close W040's PHYSICAL
  obligations (EVID-007/EVID-008 remain open, physical,
  W040-owned).
- API success never implies physical connectivity; sandbox
  results are `sandbox-simulation` and are never production
  evidence.
- The developer boundary creates no new canonical authority: the
  API and webhooks remain projections/observations over the
  canonical server state (case 56 proves the observation channel
  cannot mutate it; case 10/30/31 pin the structural side).
- W048 remains accepted-not-restored; W040 remains independently
  in-review; R4 stays parallel.
- No frozen Architecture 1.0 or Protocol 1.0 semantic or
  wire-schema change is part of this delivery; the one
  route-shape delta (the single-segment policy read) is the
  honest consequence of the current canonical policy identity
  and is disclosed in §2.
- No CI success is claimed (§5); the composition pin follow-up
  (§5) awaits Architect disposition and is not silently applied.

## 8. Worker state

`WAITING_FOR_ARCHITECT` at the delivery head. Not self-accepted;
not self-merged; the guarded merge remains Architect-only.
