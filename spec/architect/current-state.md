# ADCOS Current State

## Status

**CURRENT — Persistent Architect snapshot (follows the frozen Architecture Version 1.0)**

This is the single current-state artifact of the persistent Architect package.
A fresh Architect needs only this artifact plus the canonical specification
entry point (`README.md` → the four frozen documents) to understand the
current state of ADCOS. It is updated by the Architect through governance
changes; it must never contradict `execution-state.yaml` or the execution
ledger.

Snapshot recorded: 2026-08-30 (UTC), at establishment of the persistent
Architect package (see `decisions/DEC-0044-governance-mandate.yaml`).

---

## Repository

```text
Repository:      github.com/pectoraux/ADCOS
Current main:    1669ae9a396838b72ba461c846b98e84478ab24f
                 (origin/main at package establishment; the merge of
                  WORK-039 — see the execution ledger entry WORK-039)
```

`main_sha` semantics: the main baseline this snapshot was recorded against.
If `main` has advanced past this SHA, a new session reads the commits between
(`git log 1669ae9..main`) as merged decisions, then re-reads this package on
the advanced `main`.

## Architecture version

This package follows the frozen Architecture Version 1.0. The authoritative
declaration lives only in the `## Status` section of `spec/architecture.md`
(single declaration site, `spec/governance.md` §3); it is not restated here.

## Protocol version

Protocol Version 1.0, declared in `spec/schemas/protocol.json`
(`protocol_version`), per `spec/governance.md` §3. The Architecture Version
and the Protocol Version are independent lines and are never conflated.

## Active Work Item

**None.** No Work Item is currently authorized for implementation under this
package. The execution mode is `awaiting-architect-decisions`:

- `WORK-040` (Pilot deployment) is **in review** — implementation delivered
  on PR #48 (branch `work-040-pilot-deployment`, head
  `ee9b356020b6450d85837f60e60c41d08f0ec09a`, delivery record posted
  2026-08-29); no Architect review verdict has been rendered yet.
- The original WORK-040 designation was issued through chat before this
  package existed; it is recorded as deprecated provenance in
  `authorizations/WORK-040.yaml` and is not durable authority. Continuation
  of WORK-040 implementation requires a fresh repository-local authorization
  by the Architect.

**Execution status:** implementation STOPPED — no current authorization.
Pending Architect decisions (in order):

1. Accept or correct this persistent-Architect package (the governance PR
   that establishes `spec/architect/`).
2. Decide WORK-040 PR #48 (in review since 2026-08-29).
3. Disposition the open W035 physical-evidence PRs #45, #46, #47 (see
   decisions DEC-0040 … DEC-0042).
4. Decide ACR-004 / PR #49 (connectivity-economy roadmap; explicitly gated on
   this package per DEC-0044).

## Blocked Work Items

- `WORK-040` — not blocked structurally (all hard dependencies W027, W028,
  W036, W037, W039 are accepted and merged); it is **in review**. Further
  implementation is halted pending the PR #48 decision and a fresh
  authorization.
- `WORK-041+` — **do not exist.** The frozen backlog is exactly
  WORK-001 … WORK-040 (`spec/work-items.md`). `spec/work-items.md` remains
  frozen; no W041+ may be appended until ACR-004 is accepted (DEC-0044).

## Accepted Work Items

`WORK-001` … `WORK-039` — all Architect-accepted and merged into `main`
(acceptance decision records `DEC-0001` … `DEC-0039`; per-item evidence in
`spec/architect/execution-ledger.yaml`).

## Open PRs relevant to architecture

| PR | Head branch | State | Subject |
|---|---|---|---|
| #45 | `work-035-device-evidence` | open | W035 physical Android evidence — calibrated partial run |
| #46 | `work-035-android-mobile-agent` | open | W035 Physical Android Device Validation |
| #47 | `work-035-physical-evidence-v2` | open | W035 Final Physical Protocol Validation |
| #48 | `work-040-pilot-deployment` | open | WORK-040: Pilot deployment (in review) |
| #49 | `roadmap/connectivity-economy` | open | Connectivity commerce roadmap + proposed ACR-004 (incomplete pending this package — DEC-0044) |

## Open ACRs

- `ACR-004` — **PROPOSED** ("Connectivity Commerce Plane"), drafted on branch
  `roadmap/connectivity-economy` (PR #49); not on `main`. Cannot be accepted
  in its current PR: the Architect's follow-up (DEC-0044) requires this
  persistent package first.

Accepted ACRs on `main`: ACR-001, ACR-002, ACR-003 (`spec/acr/`).

## Open architectural questions

None. `docs/specification/open-architectural-questions.md` records OAQ-001 as
resolved by accepted ACR-003, with no remaining open question.

## Open external evidence obligations

Tracked in `spec/architect/evidence-obligations.yaml` (statuses PASS /
PARTIAL / NOT-TESTABLE / OPEN; software PASS never silently becomes physical
PASS):

| ID | Work Item | Criterion | Class | Status |
|---|---|---|---|---|
| EVID-001 | WORK-019 | real Open5GS interop gate | PHYSICAL | **PASS** (closed; N3 capture outstanding per the disclosure, gate PASSED) |
| EVID-002 | WORK-020 | physical SDR-based lab topology (criterion 4) | PHYSICAL | **OPEN** (SDR-LAB RESULT: BLOCKED) |
| EVID-003 | WORK-034 | real Raspberry Pi / edge hardware track | PHYSICAL | **OPEN** |
| EVID-004 | WORK-035 | physical Android device track; physical transport handover | PHYSICAL | **OPEN** (physical observation PASS per DEC-0042; handover re-bind over a handset-backed second path remains open) |
| EVID-005 | WORK-036 | physical appliance deployment at a real site | PHYSICAL | **OPEN** |
| EVID-006 | WORK-037 | real 5G interoperability lab (class C) | PHYSICAL | **OPEN** |
| EVID-007 | WORK-040 | real users/devices participate (criterion 1) | PHYSICAL | **PARTIAL** (software-class participants; pending PR #48 review) |
| EVID-008 | WORK-040 | real 5G access path (criterion 2) | PHYSICAL | **NOT-TESTABLE** on the pilot host (pending PR #48 review) |

## Latest accepted decisions

- `DEC-0039` — WORK-039 (Federation at scale) accepted; merged as `main`
  `1669ae9` (2026-08-29), including correction cycle W039-001 (DEC-0043,
  resolved).
- `ACR-003` accepted (2026-08-28): `WORK-016 → WORK-032` DAG reconciliation.
- `DEC-0038` — WORK-038 (Future IMT/6G adapter profile) accepted (2026-08-29).

## Latest rejected / corrective decisions

- `DEC-0044` — governance mandate (PR #49 Architect follow-up, 2026-08-29):
  CHANGES REQUIRED — the persistent Architect package (this package) must
  exist before PR #49 can be accepted; W041+ gated on ACR-004. Status:
  standing requirement, fulfilled by this package pending Architect
  acceptance.
- `DEC-0042` — W035 physical evidence v6 review (2026-08-29): software
  implementation CLOSED; physical observation PASS; the physical handover
  gate remains OPEN (EVID-004).
- `DEC-0040`, `DEC-0041` — W035 physical evidence reviews (2026-08-29):
  CHANGES REQUIRED (test-double path; synthetic interface authority) — both
  superseded by the v6 review chain.
- `DEC-0043` — WORK-039 blocker W039-001 (2026-08-29): CHANGES REQUIRED
  (multi-hop revocation relay not actually implemented) — resolved at
  correction `c515231`, superseded by DEC-0039.

## Where the durable state lives

- Machine-readable current state: `spec/architect/execution-state.yaml`
- Lifecycle ledger: `spec/architect/execution-ledger.yaml`
- Decision registry: `spec/architect/decisions/` (index in its README)
- Authorizations: `spec/architect/authorizations/`
- Evidence registry: `spec/architect/evidence-obligations.yaml`
