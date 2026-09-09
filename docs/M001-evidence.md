# M001 — Architecture 1.1 Freeze — Evidence Record

**Work Item:** M001 · **Authorization:** M001-CORE-001 (DEC-0098; scope amended by DEC-0099)
**Baseline:** `40737a0c716eff3ad05753431c24c2717afb2a68`

This record persists the verified facts of the M001 transition. Every claim
below was reproduced by the sole Architect against the live repository — no
worker report is trusted without direct verification (Tech Lead handoff,
non-negotiable rule).

## 1. Transition-package acceptance (PR #24)

- PR #24 head `46eef881` (chore/adcos-architecture-1.1-bootstrap-6): CI green
  (run 34351833737, all gates passing with the legacy spec_check audit
  non-blocking by design).
- Local re-verification on the merged main `40737a0`:
  `current_spec_check.py` PASS · `tech_lead_guard.py` PASS ·
  `architecture_drift_guard.py` PASS (governance-only, 28 control-plane
  files) · `fresh_session_check.py` PASS against the pinned snapshot.
- Merged by the sole Architect as `40737a0c716eff3ad05753431c24c2717afb2a68`
  (merge commit, history preserved).

## 2. Activation (DEC-0098)

- ACR-014 proposed with all eight change-control elements; approval path
  recorded (DEC-0098).
- M001-CORE-001 issued as the sole active authorization
  (baseline `40737a0`, scope = governance control-plane transition).
- Roadmap 1.5 → 1.6; execution mode `implementing`, active item M001.
- All four current-governance gates re-run PASS on the activation commit
  `6ea3b6900cf039b90d82b6a5c3820390a3efda3b`; spec_check selftest 9/9
  baseline-relative PASS.

## 3. Guard-infrastructure repair (`51b8fd5`)

- `architecture_drift_guard.py`: control-plane classification extended with
  `spec/acr/`, `spec/history/`, the canonical frozen authority docs
  (mission/governance/change-control/workflow/work-items/dependency-graph)
  and `docs/M001-evidence.md`. This is strictly harder on implementation
  PRs, which now fail the mixed-delta guard for any of these paths.
- CI scaffold hygiene: the drift classification artifact moved to
  `RUNNER_TEMP` (an untracked scaffold file in the tree reads as an
  unauthorized repo delta to the implementation-domain batteries on push
  events).

## 4. Battery-mirror reconciliation (DEC-0099)

The repaired CI pipeline unmasked latent mainline-integrity debt that the
pre-transition workflow could never reach (its first blocking step failed
before any battery ran). All 47 implementation-domain batteries were
executed locally on `51b8fd5`; failures and dispositions:

| Battery | Failure | Disposition |
|---|---|---|
| agent case_29 | conformance total mirror 136 vs 163 | Mirror synchronized to the accepted W055 value (163/163, additive growth per docs/WORK-055-evidence.md) |
| marketplace case_37 | frozen tuple referenced WORK-047.yaml (absent from every reachable commit) | Stale reference removed |
| payment | `usage.EvidenceFamily` import (superseded W044-era surface; W052 rewrite + W048 not restored) | CI precondition guard: visible skip with DEC-0099 disclosure; re-baseline under M009 |
| eligibility | same superseded surface | same guard + disclosure |
| client | `containment.CapabilityMatrix` / `sharing.*` (W048 accepted-not-restored) | same guard + disclosure; re-baseline under M009/M014 |

- The three era-superseded battery files are NOT modified or deleted; they
  remain historical artifacts awaiting re-baselining under the Architecture
  1.1 commercial track.
- Known recorded condition (unchanged): per-battery delta-shape cases
  hard-code their historical Work Item scopes; cross-domain implementation
  PRs trip them. Resolution is assigned to authorization-aware battery
  scope consultation in the post-M001 implementation era.

## 5. Fresh-session reproducibility

A clean clone of main at this commit plus GitHub access, without any
conversation history, yields: mission, the 1.1 forward target, the preserved
1.0 baseline, roadmap state (v1.6, M001 ACTIVE), the active M001-CORE-001
authorization, worker limits, and the M001 gate — verified by
`tools/fresh_session_check.py`.

## 6. Delivery (pending)

The M001 delivery PR (governance-classified) will promote the 1.1 successor
snapshots, archive the 1.0 snapshot under `spec/history/`, flip ACR-014 to
ACCEPTED, and synchronize the checkers. Its verification matrix will be
appended here at delivery time, with the exact head SHA, before Architect
acceptance (DEC-0100).
