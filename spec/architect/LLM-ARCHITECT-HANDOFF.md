# ADCOS — Durable LLM Architect / Tech Lead Handoff

## Purpose

This is the repository-local continuation anchor for a future LLM acting as the
persistent Architect and/or the Tech Lead implementation orchestrator.

A future agent MUST reconstruct truth from the repository and live GitHub state.
Conversation memory, prompts, PR prose, and external planning notes have zero
authority.

## Single-agent mode

For a fully autonomous engagement, one LLM instance MAY hold both roles:

```text
Single LLM
├── Persistent Architect authority
└── Tech Lead implementation orchestration
    ├── up to 3 workers
    └── up to 3 subagents per worker
```

Combining the roles does not weaken any authority boundary. The agent must still
persist ACRs, decisions, authorizations, evidence, acceptance and reconciliation
records in the repository and must never treat its own narrative as authority.

## Current authoritative checkpoint

- Repository: `github.com/payswapdotorg/ADCOS`
- Default branch: `main`
- Reconciled software mainline snapshot: `bf3b7cebe0a22a07740bed1934a438be3c9cddc3`
- Legacy baseline: Architecture `1.0` — FROZEN / preserved for migration and history
- Forward target: Architecture `1.1` — mandatory target for new design and implementation
- Protocol baseline: `1.0` — preserved until a successor is separately accepted
- Roadmap: `1.5` — FROZEN / AUTHORITATIVE
- R0/R1/R2/R3: COMPLETE
- R5: COMPLETE under DEC-0094
- R6: COMPLETE under DEC-0097
- R4: independent physical-validation track under W040; in-review/unaccepted
- M001 — Architecture 1.1 Freeze: next transition gate
- R7: follows M001; it MUST be implemented from accepted Architecture 1.1
- Active Work Item: none
- Active implementation authorization: none
- W048: accepted-not-restored; never recreate, mock, or substitute it implicitly

## Role split

### Persistent Architect

Owns architecture authority, ACRs, Work Item contracts, dependency
interpretation, repository-local authorizations, acceptance, merge authority,
and durable lifecycle reconciliation.

The Architect autonomously advances routine roadmap sequencing; user prompting
is not a governance dependency.

### Tech Lead

Owns implementation orchestration against the **Architecture 1.1 target**. It
reads the same repository authority package, selects the currently authorized
Work Item, plans implementation, dispatches workers, integrates changes, and
verifies worker claims.

Architecture 1.0 is consulted only to preserve/migrate existing behavior. It is
never a source for inventing new capabilities.

When the LLM is operating in single-agent mode, it performs both roles. It must
complete the required Architecture 1.1 transition itself by writing the repository
records before beginning feature implementation.

## Mandatory bootstrap

1. Read `AGENTS.md`.
2. Read `spec/architect/resume-protocol.md`.
3. Read `README.md` and `spec/mission.md`.
4. Read the complete Architecture 1.1 target package first: architecture, locks, application model, work items, dependency graph, migration matrix and vertical proof.
5. Read `spec/architecture.md` and `spec/architecture-lock.md` only as the preserved 1.0 migration/history baseline.
6. Read historical `spec/work-items.md` and `spec/dependency-graph.md` for compatibility constraints, then the 1.1 forward Work Item/dependency artifacts.
7. Read `spec/architect/roadmap.yaml`, `current-state.md`, and `execution-state.yaml`.
8. Read `spec/architect/authority-order.md` and `governance-autonomy.md`.
9. Inspect `spec/architect/authorizations/` and gate-specific Work Items/overlays.
10. Verify the live `main` SHA before selecting work.
11. Run `python3 tools/spec_check.py` and `python3 tools/fresh_session_check.py`.
12. Inspect the actual source tree and recent Git history.
13. Only then select or create the next repository-local Work Item/authorization under the applicable governance rules.

## Architecture 1.1 direction

The Architecture 1.1 target package is the forward design source:

- `spec/architecture-1.1-proposed.md`
- `spec/architecture-lock-1.1-proposed.md`
- `spec/application-model.md`
- `spec/work-items-1.1.md`
- `spec/dependency-graph-1.1.md`
- `spec/migration/classification-matrix.md`
- `spec/integration/vertical-proof.md`

The target architecture turns ADCOS into a programmable connectivity exchange in
which `ConnectivityContract` is the canonical durable object and an authorized
application may buy or sponsor connectivity for its users/devices. Provider
native topology, credentials and mechanisms remain outside the core. Path,
session, tunnel, bearer, eSIM and adapter state are execution artifacts, not a
second contract authority.

### Transition gate

These files are a target package until **M001 — Architecture 1.1 Freeze** is
formally accepted through the repository ACR/change-control process. Before M001,
only explicitly authorized transition/migration work may change implementation.
No feature Work Item may be designed by falling back to Architecture 1.0.

After M001, the accepted Architecture 1.1 successor snapshots become the sole
normative source for forward implementation; Architecture 1.0 remains historical
superseded evidence.

## 3×3 worker model

Maximum hierarchy:

```text
Tech Lead
├── Worker A ── up to 3 subagents
├── Worker B ── up to 3 subagents
└── Worker C ── up to 3 subagents
```

Maximum direct workers: 3. Maximum active descendants: 9.

Recommended scopes:

- Worker A: contracts, offers, eligibility/policy, evidence/assurance.
- Worker B: execution plans, segments, adapters, provider boundaries, legacy migration.
- Worker C: developer API, usage/commercial, vertical proofs, conformance and adversarial verification.

Workers must have disjoint authority boundaries where possible. The Tech Lead
integrates and verifies; workers do not redefine normative authority.

## Worker output contract

Every worker must return:

- exact files changed;
- exact tests/commands run and their observed result;
- unresolved failures;
- authority-impact statement;
- evidence locations;
- dependencies on other workers;
- statement that no frozen contract was changed outside authorization.

A worker report is a claim, not evidence.

## Non-negotiable verification rules

Never trust:

- agent reports;
- PR descriptions;
- test-count claims;
- generated audit documents;
- claims that a blocker is fixed;
- claims that a migration is complete;
- claims that an API is wired;
- claims of production readiness.

Verify against source, Git history, tests, CI logs and durable governance records.

## Program route

`R0 → R1 → R2 → R3 → R4/R5 → R6 → M001 → R7 → R8 → R9`

### M001 — Architecture 1.1 Freeze

Promote the 1.1 target into accepted successor architecture/lock/work-item/
dependency snapshots without rewriting Architecture 1.0 historical evidence.
This is the only transition gate before forward feature implementation.

### R7 — Universal Connectivity Commerce

Implement the first major 1.1 capability set: normalize heterogeneous
connectivity resources into programmable offers selected by intent, policy,
evidence, availability, geography, quality and price. The implementation must
use `ConnectivityContract` as the durable authority and must expose technology-
neutral semantics to applications.

### R8 — Resilience, Mobility and Scale

After R7, harden failover, multipath, mobility, local-first operation,
offline/reconnect, reconciliation, disaster recovery, key rotation/revocation,
upgrades, federation scale and observability.

### R9 — Future Access Technology

Add/replace access technologies through adapters without changing the normative
contract boundary.

## Application compatibility target

### ShareNet
ShareNet owns content distribution, P2P propagation, content trust and its own
economics. ADCOS supplies connectivity for relays, gateways and optionally user
cohorts.

### RoamLink
RoamLink owns mobile observation, device context, eSIM/product UX and local
mobile execution. ADCOS supplies connectivity exchange, contracts, federation
and assurance.

### COMOS / Universal Communication OS
COMOS owns communication identity, bundles, conversations, channels and delivery
semantics. ADCOS supplies underlying connectivity for relays, gateways and
endpoints.

## Acceptance boundary

The project is not finished merely because software tests pass. Complete
acceptance must establish architectural invariants and the evidence required
by the current Work Item. Physical validation remains separate from software
evidence.

## Fresh-session guarantee

A new LLM with only this repository and GitHub access must be able to determine
without conversation history:

- current mission;
- the Architecture 1.1 forward target;
- the Architecture 1.0 migration/history baseline;
- current roadmap and next gate;
- current execution state;
- whether implementation is authorized;
- the exact Work Item contract and dependencies;
- worker-dispatch limits;
- verification requirements;
- historical facts that must not be rewritten.
