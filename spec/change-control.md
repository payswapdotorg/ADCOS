# ADCOS Architecture Change Control

## Status

**ACTIVE — Process Authority**

This document defines the Architecture Change Request (ACR) process required by `spec/architecture-lock.md` §6 (Change Control). It is process documentation maintained by the Architect; it does not alter any frozen architectural rule.

---

## 1. Scope

The ACR process applies to any change that modifies the semantic content of the frozen specification documents:

- `spec/architecture.md`
- `spec/architecture-lock.md`
- `spec/work-items.md`
- `spec/dependency-graph.md`

Strictly editorial corrections (typo or formatting fixes that provably do not alter architecture meaning) are exempt, but must be explicitly flagged in the PR so the Architect can verify that no semantics changed.

## 2. Architecture Change Request

An Architecture Change Request is a written request to change the frozen architecture. ACRs are recorded at:

```text
spec/acr/ACR-NNN-<short-title>.md
```

with sequential zero-padded numbering starting at `ACR-001`. The required record template is in section 8 of this document.

Anyone — including Z.ai — may draft and propose an ACR. Only the Architect approves or rejects one. Approval is never implied by silence, by inaction, or by a passing CI run.

## 3. Required Elements

Every ACR must contain all eight elements. An ACR missing any element is incomplete and must not be approved.

1. **Architecture Change Request** — the proposed change, its motivation, and the alternatives considered.
2. **Statement of affected architecture sections and locks** — an explicit enumeration of the `spec/architecture.md` sections affected and the `LOCK-XXX` identifiers from `spec/architecture-lock.md` that are touched.
3. **Compatibility analysis** — impact on wire compatibility, persisted state, live sessions, federation relationships, existing deployments, and mixed-version operation.
4. **Work-item and dependency impact analysis** — the affected Work Items from `spec/work-items.md`, and the recalculated dependency graph, as required by `spec/dependency-graph.md` rule 5 (architecture changes require graph recalculation before implementation continues).
5. **Migration/rollback plan** — where applicable: how existing deployments and in-flight Work Items transition to the changed architecture, and how to roll back.
6. **Architect approval** — the explicit, recorded decision of the Architect (approval or rejection, with rationale and date).
7. **New architecture version** — when semantics change, the Architecture Version is bumped according to `spec/governance.md` §3 (major for semantic change, minor for additive clarification) and the new version is recorded in `spec/architecture.md`.
8. **Synchronized updates** — all affected frozen documents, and the governance tooling expectations in `tools/spec_check.py`, are updated atomically in the same change set. Frozen documents are never left mutually inconsistent.

## 4. Rules

1. A normal implementation PR is never allowed to silently become an architecture change.
2. No Work Item may silently modify a frozen rule.
3. If Z.ai believes an implementation requires changing a frozen rule — or that the frozen architecture is internally inconsistent — it must stop, describe the exact conflict, and request an ACR (or Architect clarification). It must not reinterpret, simplify, work around, or extend the frozen rule.
4. Until an ACR is approved, the frozen documents remain authoritative, and implementations must not proceed on the changed premise.
5. Process-authority documents (`spec/governance.md`, `spec/change-control.md`, `spec/workflow.md`) may be updated by the Architect through normal PR review; if such an update would alter a frozen rule, it requires an ACR.

## 5. Process Flow

```text
proposal (any contributor, including Z.ai)
    -> draft ACR record at spec/acr/ACR-NNN-<title>.md
    -> Architect review of all eight required elements
    -> approval (or rejection with rationale — recorded in the ACR)
    -> synchronized updates to affected frozen documents
    -> new Architecture Version recorded when semantics change
    -> dependency graph recalculated
    -> affected Work Items and prompts re-planned
```

## 6. Relationship to Implementation PRs

An implementation PR that discovers it would need an architecture change must stop and report the conflict in the PR (per `spec/prompts/WORK-001.md` and `spec/workflow.md`), leaving the frozen documents untouched. The architecture change proceeds only through the ACR process, after which the affected Work Item is re-baselined by the Architect.

## 7. ACR Status Vocabulary

- `PROPOSED` — drafted, awaiting Architect review.
- `ACCEPTED` — approved by the Architect; synchronized updates merged.
- `REJECTED` — declined; rationale recorded; frozen documents unchanged.
- `SUPERSEDED` — replaced by a later ACR.

## 8. ACR Record Template

```markdown
# ACR-NNN: <short title>

## Status
PROPOSED | ACCEPTED | REJECTED | SUPERSEDED

## Proposed change
<what changes, and why; alternatives considered>

## Affected architecture sections and locks
- spec/architecture.md sections: <list>
- LOCK-XXX identifiers: <list>

## Compatibility analysis
<wire compatibility, persisted state, sessions, federation, deployments, mixed-version operation>

## Work-item and dependency impact
- Affected Work Items: <list>
- Dependency graph recalculation: <result>

## Migration / rollback plan
<where applicable>

## Architect decision
<decision, rationale, date>

## Resulting architecture version
<version, or "unchanged" for non-semantic edits>
```
