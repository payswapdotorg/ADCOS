# Governance Review — WORK-040 as a Hard Prerequisite for Downstream Work

**Status: GOVERNANCE PROPOSAL — PROPOSED.**

**Document class:** Persistent-Architect governance review (lives under
`docs/governance/`; `docs/` is a `GOVERNANCE_PREFIX` per `tools/spec_check.py`).
This is a governance-only review proposing a decision record and an updated
dependency model. It introduces **no implementation delta**, creates **no Work
Item authorizations**, and modifies **no frozen architecture document**.

**Acting role:** Chief Architect (governance review). This document and the
drafted `DEC-0051` are submitted as a governance PR for ratification; they do
not govern until accepted and merged by the Architect (review-protocol §5, §7).

**Question under review:** *Should physical validation work (WORK-040) remain a
blocking dependency for unrelated software architecture work?*

**Authored against base SHA:** `5da120f6e0945410a8fc9346692058ca9a8b49f3`
(current `origin/main`).

---

## 0. Scope and non-negotiable constraints

This review is bounded by the rules supplied for the governance task:

1. **W040 remains active and unchanged.** No change to WORK-040, its
   correction cycle (WORK-040-CORRECTION-001, DEC-0046), its in-review PR #48,
   or its review verdict (CHANGES_REQUIRED).
2. **W041/W042/W048 require their own authorizations.** Decoupling W040 as a
   prerequisite does **not** authorize W041/W042/W043/W048. Each still requires
   its own repository-local `WORK-XXX.yaml` (`status: active`) before any
   implementation branch may proceed (review-protocol §3.1; ARCH-08).
3. **Physical evidence criteria remain owned by W040.** EVID-007 (real
   users/devices, PARTIAL) and EVID-008 (real 5G access path, NOT-TESTABLE)
   remain W040's open PHYSICAL obligations. They are not transferred,
   redefined, or closed by this review.
4. **No acceptance criteria are weakened.** Every Work Item's frozen
   acceptance criteria and evidence-class discipline (workflow §2.2) are
   preserved unchanged.
5. **No authorization bypass occurs.** ACR-009 acceptance still *"does not
   itself authorize implementation"* (DEC-0050). The one-Work-Item-at-a-time
   rule (workflow §1, dependency-graph §6) is preserved.

Anything outside these constraints is explicitly out of scope and would
require a separate governance change or ACR.

---

## 1. Dependency graph analysis

### 1.1 What the frozen DAG actually says

`spec/dependency-graph.md` is **FROZEN**. Its DAG (§2) terminates at W040.
W041/W042/W043/W048 are **not nodes in the frozen DAG**. W040's only incoming
edges are:

```
W027 → W040
W028 → W040
W036 → W040
W037 → W040
W039 → W040
```

There is **no edge W040 → W041**, **no edge W040 → W042**, and **no edge
W040 → W048** in the frozen DAG. By the frozen graph's own semantics
(§5 "Hard dependency": *"the downstream Work Item must not be accepted/merged
before the upstream item is accepted"*), W040 is **not a hard dependency of
W041/W042/W043/W048**.

### 1.2 Where the W040-blocks-W041/W042 coupling actually lives

The coupling is encoded in **process / execution-state records**, not frozen
architecture:

| Artifact | Location (file, not frozen) | Wording |
|---|---|---|
| Execution state | `spec/architect/execution-state.yaml` `planned_work_items[0].prerequisite` | `"WORK-040 formally accepted/dispositioned"` (W041) |
| Execution state | `spec/architect/execution-state.yaml` `halted_reason` | *"W041/W042/W043 remain unauthorized until W040 is formally dispositioned"* |
| Current-state snapshot | `spec/architect/current-state.md` line 49 | *"W041 … remains blocked while W040 is active"* |
| Ready-candidate contract | `spec/architect/work-items/WORK-041.md` `Execution gate` | requires an ACTIVE W041 authorization; does NOT list W040 as a hard dependency |
| Ready-candidate contract | `spec/architect/work-items/WORK-042.md` `Execution gate` | requires W041 accepted/merged *where its interfaces are consumed*; does NOT list W040 |

These are **persistent governance state and process records**, owned by the
Architect (review-protocol §3.2; authority-order level 8). They are **not** the
frozen architecture snapshot (authority-order level 2), **not** an accepted ACR
(level 4), and **not** the frozen dependency DAG (the DAG does not encode the
edge).

### 1.3 Classification of the coupling

Using the dependency semantics defined in `dependency-graph.md` §5 and
`workflow.md` §2.1, the W040→W041/W042 coupling is best classified as a
**sequence preference / risk-management gate**, not a hard interface
dependency:

- **Hard interface dependency? No.** W041's `Required dependencies`
  (W016/W018/W033/W034) are all W001–W039, already Architect-accepted and
  merged. W041 does not import or consume any W040 artifact. W042 consumes
  W041 interfaces (where present), not W040. W048 (proposed) composes
  W041/W042 + existing authorities; it does not consume W040.
- **Evidence dependency? Partially.** W040 owns PHYSICAL evidence
  (EVID-007/EVID-008) that is *referenced by* the broader platform story but
  is *not a criterion of* W041/W042 (their contracts explicitly state
  *"Physical-device evidence: not required for W041/W042 implementation"*).
  The evidence stays owned by W040; it does not block W041/W042 software
  conformance.
- **Sequence preference? Yes.** The "formally dispositioned" / "while W040
  is active" language encodes an Architect risk preference: don't layer more
  software on top until the pilot's physical story is dispositioned. This is
  legitimate Architect discretion, but it is a *preference*, not a structural
  invariant, and can be revised by the Architect through a governance decision
  (workflow §2: *"must be resolved by the Architect — directly, or through an
  ACR"*).

### 1.4 Why W048 is also in scope

W048 (issue #92) is not yet a registered Work Item contract and has no
authorization. The prior W048 design reconnaissance (PR #97) already
established its hard dependency chain as `W040 dispositioned → W041 merged →
W042 merged → W048 authorized`. This review addresses the **first** edge of
that chain (W040 → W041/W042). The later edges (W041 → W042 → W048) are
genuine interface dependencies and remain in force.

### 1.5 The DAG-ready vs execution-ready distinction (already in the spec)

`workflow.md` §2.1 already defines the exact distinction this review relies on:

> *"A Work Item can therefore be DAG-ready but execution-blocked."*

And §2 explicitly authorizes the Architect to resolve dependency divergence
directly:

> *"Such divergence is a specification-consistency finding that must be
> resolved by the Architect — directly, or through an Architecture Change
> Request — and never by an implementation PR."*

So the governance vehicle is unambiguous: an **Architect decision record**
(DEC-0051), **not an ACR**, because no frozen architectural semantic content
changes (change-control §1, §8).

---

## 2. Risks of keeping the coupling (status quo)

R1. **Indefinite software-roadmap stall.** W040 is CHANGES_REQUIRED
   (DEC-0046) on a correction cycle whose criteria include *real users/devices*
   (EVID-007, PARTIAL) and *a real 5G access path* (EVID-008,
   NOT-TESTABLE on the pilot host). These are physical/environment-gated and
   may be unavailable for an unbounded time. Coupling all downstream software
   architecture (W041/W042/W048) to W040's physical disposition serializes
   decided architecture (ACR-005/006/009 are ACCEPTED) behind an environment
   gate the software does not depend on.

R2. **Contradicts the ready-candidate contracts' own evidence class.** W041
   and W042 contracts explicitly state physical-device evidence is *"not
   required for W041/W042 implementation; physical claims remain governed
   separately."* Blocking W041/W042 software behind W040's physical evidence
   contradicts the contracts' own evidence-class discipline.

R3. **Conflates "architecture decided" with "architecture physically proven."**
   ACR-005/006/009 are ACCEPTED — the architecture is decided. W040 is the
   physical *proof* of the integrated fabric. Preventing implementation of
   decided architecture because a separate validation work item is stuck
   conflates two distinct concerns and blocks software parallelism without
   architectural benefit.

R4. **Grows the correction-blast-radius.** The longer W041/W042 software is
   deferred, the larger the gap between the accepted architecture and its
   realized form, increasing the eventual rework surface if assumptions drift
   in the interim. Parallel software implementation against frozen contracts
   reduces, not increases, this risk.

R5. **W048 (and future commercial work) inherits the stall.** W048's design
   (PR #97) already shows the stall propagating: W048 cannot even begin until
   W040→W041→W042 all resolve. The coupling compounds downstream.

---

## 3. Risks of decoupling (must be stated honestly)

D1. **Software may be built against assumptions W040's physical validation
   would have corrected.** If W041/W042 implement against an interpretation
   of ACR-005/006 that W040's real-device/real-5G evidence would have
   refined, the software may need rework. *Mitigation:* W041/W042 implement
   against the FROZEN accepted ACRs (DEC-0047/0048) and frozen architecture
   locks, not against W040 evidence. The ACRs are the architecture authority;
   W040 is validation evidence. Conformance is to the ACRs, not to W040's
   findings.

D2. **Architectural risk-signal loss.** The "while W040 is active" gate
   arguably encodes the Architect's risk preference that the pilot should
   inform later software. *Mitigation:* DEC-0051 preserves the signal as a
   **non-blocking advisory** rather than a hard prerequisite: W040's physical
   findings are recorded in `spec/experience/` (authority-order level 5) and
   explicitly fed back into W041/W042/W048 design review — but they no longer
   *block* implementation authorization. The Architect retains the authority to
   refuse an authorization on risk grounds at any time.

D3. **Perception of "weakening the gate."** A casual reading might see
   decoupling as lowering standards. *Mitigation:* DEC-0051 changes **no
   acceptance criterion** of any Work Item, creates **no authorization**, and
   preserves **all evidence-class discipline** (workflow §2.2). It only removes
   a sequence-preference edge between two unrelated concerns. The
   one-Work-Item-at-a-time rule and per-item authorization remain fully in
   force.

D4. **Decoupling precedent.** Establishing that prerequisites can be relaxed
   by governance decision could be misapplied later to weaken genuine hard
   dependencies. *Mitigation:* DEC-0051 is scoped **exclusively** to the
   W040→software sequence-preference coupling. It explicitly does **not**
   touch any frozen-DAG hard edge, does not relax W041→W042 or W042→W048
   interface dependencies, and states that genuine hard dependencies remain
   governed by the frozen DAG + change-control §1.

---

## 4. Proposed governance change

**Decision:** Reclassify the W040→W041/W042/W048 coupling from a *blocking
prerequisite* to a *non-blocking advisory*, via Architect decision DEC-0051.

### 4.1 What changes

| Artifact | Change |
|---|---|
| `spec/architect/decisions/DEC-0051-*.yaml` | **New** decision record (status: PROPOSED, type: governance) recording the reclassification. |
| `spec/architect/execution-state.yaml` `planned_work_items[].prerequisite` | (proposed, on ratification) W041 prerequisite changes from `"WORK-040 formally accepted/dispositioned"` to `"None (W040 decoupled by DEC-0051; W040 physical findings are a non-blocking advisory via spec/experience/)"`. W042/W043 prerequisites unchanged (they reference W041/W042 interface dependencies, not W040). |
| `spec/architect/current-state.md` | (proposed, on ratification) W041/W042 line reworded from "remains blocked while W040 is active" to "DAG-ready; execution-blocked pending its own repository-local authorization (W040 decoupled as non-blocking advisory by DEC-0051)". |
| `spec/architect/decisions/README.md` registry table | (proposed, on ratification) add the DEC-0051 row. |
| Frozen `spec/dependency-graph.md` | **UNCHANGED.** No frozen edge is added, removed, or relabeled. |
| Frozen `spec/work-items.md` | **UNCHANGED.** No acceptance criteria altered. |
| `spec/architect/work-items/WORK-041.md` / `WORK-042.md` contracts | **UNCHANGED.** Their `Execution gate` already requires only their own active authorization (plus W041-interfaces for W042). The "Execution gate" text is not modified. |
| Any implementation file | **NONE.** No implementation delta. |
| Any `spec/architect/authorizations/WORK-*.yaml` | **NONE CREATED.** No authorization is created or modified. |

### 4.2 What does NOT change

- W040 remains active, in-review, CHANGES_REQUIRED, on its correction cycle.
- W041/W042/W043/W048 each still require their own `status: active`
  repository-local authorization before any implementation branch proceeds.
- The one-Work-Item-at-a-time rule (workflow §1) is preserved.
- EVID-007 / EVID-008 remain W040's open PHYSICAL obligations, owned by W040,
  governed by evidence-obligations.yaml; they are not transferred or closed.
- All frozen acceptance criteria and evidence-class discipline are preserved.
- The frozen dependency DAG is untouched (no edge changed).
- ACR-009 acceptance still does not authorize implementation (DEC-0050).
- ARCH-08 provenance enforcement is unchanged: any implementation delta still
  requires an active authorization inherited from main.

### 4.3 The non-blocking advisory mechanism

W040's physical findings (when eventually produced) are recorded as
**experience records** in `spec/experience/` (authority-order level 5). Per
authority-order §2, experience *"informs the Architect's reasoning; it cannot
directly change architecture"* and cannot block implementation authorization
on its own. DEC-0051 makes this explicit for the W040→W041/W042/W048 edge:
W040 findings become **review input** for W041/W042/W048 authorization
decisions, not a **prerequisite** for them.

The Architect retains full authority to refuse a W041/W042/W048 authorization
on risk grounds at the authorization decision point — decoupling the
prerequisite does not remove the Architect's gate; it removes only the
automatic, unconditional W040-blocks-everything edge.

---

## 5. Governance vehicle: decision record, not ACR

Per `spec/change-control.md` §1, the ACR process applies to changes that
*"modify the semantic content of the current architectural snapshot,"*
including the frozen documents (`architecture.md`, `architecture-lock.md`,
`work-items.md`, `dependency-graph.md`). This proposal modifies **none** of
those: no frozen edge changes, no acceptance criterion changes, no lock
changes.

Per `spec/change-control.md` §8: *"Process-authority documents may be updated
by the Architect through normal PR review; if an update would alter an
architectural rule, the corresponding ACR must be used."* The artifacts being
updated (execution-state.yaml, current-state.md, decision registry) are
**persistent governance state and process records** (authority-order level 8),
not frozen architecture (level 2). The change alters a *prerequisite
preference*, not an architectural rule.

Per `spec/workflow.md` §2: dependency divergence *"must be resolved by the
Architect — directly, or through an ACR."* The Architect-direct path is
explicitly available. This review takes that path: a governance PR carrying a
PROPOSED decision record (DEC-0051), ratified by Architect acceptance.

If, on review, the Architect judges that this change *does* alter
architectural semantics (e.g. weakens a structural invariant), the correct
response is to convert it into an ACR per review-protocol §6 — **not** to
merge it as-is. This review explicitly invites that conversion if warranted.

---

## 6. Drafted decision record (DEC-0051)

The full proposed decision record is at
`spec/architect/decisions/DEC-0051-work-item-dependency-decoupling.yaml`
(included in this PR with `status: PROPOSED`, `decision: PROPOSED`). Summary:

- **decision_id:** DEC-0051
- **type:** governance
- **work_item:** null (governance-level)
- **acr:** null (not an ACR; no frozen architecture change)
- **decision / status:** PROPOSED — awaiting Architect ratification
- **findings:** the W040→W041/W042/W048 coupling is a sequence preference in
  process-state records, not a hard edge in the frozen DAG; W041/W042 contracts
  do not list W040 as a hard dependency; W041/W042 evidence class explicitly
  does not require physical-device evidence; ACR-005/006/009 are accepted.
- **accepted_scope (on ratification):** reclassify the coupling as a
  non-blocking advisory; W040 findings enter W041/W042/W048 authorization
  review as experience input, not as a prerequisite.
- **rejected_scope:** any change to W040 status; any authorization of
  W041/W042/W043/W048; any weakening of acceptance criteria or evidence-class
  discipline; any change to the frozen DAG; any bypass of ARCH-08.
- **downstream_effect:** W041/W042/W048 remain each gated by their own active
  authorization; the W041→W042 and W042→W048 *interface* dependencies remain
  hard; W040's PHYSICAL evidence obligations remain W040-owned and OPEN.

On Architect ratification, the execution-state prerequisites and current-state
wording would be updated in the same governance transition (review-protocol
§5), and the decision record's `status` would move PROPOSED → ACCEPTED with
`reviewed_sha` and `evidence.merge_sha` set.

---

## 7. Recommendation

**Approve the decoupling**, conditional on the non-negotiable constraints in
§0. The coupling is a sequence preference, not a structural invariant; the
frozen DAG does not encode it; the ready-candidate contracts' evidence class
explicitly does not require W040's physical evidence; and the stall
propagates to all future commercial work (W048+) without architectural
benefit. The risks of decoupling (D1–D4) are real but mitigated by the
frozen-ACR conformance target, the experience-record advisory mechanism, and
the unchanged per-item authorization gate.

**Do not** treat this as weakening any criterion. It is a precise, scoped
reclassification of one prerequisite edge from *blocking* to *advisory*,
leaving every authority, every acceptance criterion, every evidence
obligation, and every authorization requirement intact.

---

## 8. Delivery metadata

| Field | Value |
|---|---|
| Review type | Governance-only dependency review (no implementation) |
| Base SHA | `5da120f6e0945410a8fc9346692058ca9a8b49f3` (origin/main) |
| Branch | `governance/w040-dependency-decoupling-review` |
| Decision record | `spec/architect/decisions/DEC-0051-work-item-dependency-decoupling.yaml` (status: PROPOSED) |
| Updated dependency model | proposed in §4 (executed on ratification; frozen DAG untouched) |
| Authorizations created | **NONE** |
| Implementation files | **NONE** |
| Frozen-doc changes | **NONE** (dependency-graph.md, work-items.md, architecture.md, architecture-lock.md all untouched) |
| spec_check | must remain 17/17 PASS (verified at base; DEC-0051 is `type: governance`, `status: PROPOSED`, machine-valid per ARCH-04) |
| Self-merge | Prohibited (review-protocol §7); the Architect ratifies and merges. |
