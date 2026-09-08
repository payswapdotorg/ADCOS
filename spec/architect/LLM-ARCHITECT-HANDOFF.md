# ADCOS — Durable LLM Architect / Tech Lead Handoff

## Purpose

This is the repository-local continuation anchor for a future LLM acting as the
persistent Architect and/or the Tech Lead implementation orchestrator.

A future agent MUST reconstruct truth from the repository and live GitHub state.
Conversation memory, prompts, PR prose, and external planning notes have zero
authority.

## Current authoritative checkpoint

- Repository: `github.com/payswapdotorg/ADCOS`
- Default branch: `main`
- Actual latest reconciled mainline: `88a73720d8ff28e95728a03e13db631ffdf9688f`
- Architecture: `1.0` — FROZEN
- Protocol: `1.0` — FROZEN
- Roadmap: `1.5` — FROZEN / AUTHORITATIVE
- R0/R1/R2/R3: COMPLETE
- R5: COMPLETE under DEC-0094
- R6: COMPLETE under DEC-0097
- R4: independent physical-validation track under W040; in-review/unaccepted
- R7: next unlocked software gate; NOT ACTIVATED
- Active Work Item: none
- Active implementation authorization: none
- W048: accepted-not-restored; never recreate, mock, or substitute it implicitly

## Immediate role split

### Persistent Architect

The Architect owns architecture authority, ACRs, Work Item contracts, dependency
interpretation, repository-local authorizations, acceptance, merge authority,
and durable lifecycle reconciliation.

The Architect autonomously advances routine roadmap sequencing; user prompting
is not a governance dependency.

### Tech Lead

The Tech Lead is the implementation orchestrator. The Tech Lead reads the same
repository authority package, selects the currently authorized Work Item, plans
its implementation, dispatches workers, integrates changes, and verifies
worker claims.

The Tech Lead MUST NOT invent implementation permission. No authorization means
no implementation. If the next gate is unlocked but not activated, the Tech Lead
waits for the repository's Architect governance transition rather than using
chat as approval.

## Mandatory bootstrap

1. Read `AGENTS.md`.
2. Read `spec/architect/resume-protocol.md`.
3. Read `README.md` and `spec/mission.md`.
4. Read `spec/architecture.md` and `spec/architecture-lock.md`.
5. Read `spec/work-items.md` and `spec/dependency-graph.md`.
6. Read `spec/architect/roadmap.yaml`, `current-state.md`, and `execution-state.yaml`.
7. Read `spec/architect/authority-order.md` and `governance-autonomy.md`.
8. Inspect `spec/architect/authorizations/` and gate-specific Work Items/overlays.
9. Verify the live `main` SHA before selecting work.
10. Inspect the actual source tree and recent Git history.
11. Only then select or implement the exact authorized Work Item.

## Architecture 1.1 direction

The repository contains the proposed Architecture 1.1 package:

- `spec/architecture-1.1-proposed.md`
- `spec/architecture-lock-1.1-proposed.md`
- `spec/application-model.md`
- `spec/migration/classification-matrix.md`
- `spec/integration/vertical-proof.md`

These files describe the intended evolution toward a programmable connectivity
exchange in which `ConnectivityContract` is the canonical durable object and an
authorized application may buy or sponsor connectivity for its users/devices.

They are **NOT current architecture authority** until an accepted ACR formally
promotes them. Until that happens, implementation follows Architecture 1.0.

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
integrates and verifies; workers do not redefine frozen authority.

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

`R0 → R1 → R2 → R3 → R4/R5 → R6 → R7 → R8 → R9`

### R7 — Universal Connectivity Commerce

The next software gate is to normalize heterogeneous connectivity resources into
programmable offers selected by intent, policy, evidence, availability,
geography, quality and price.

The target product behavior is that external applications can acquire
connectivity by API without knowing the provider, access technology, path,
routing implementation or payment rail.

### R8 — Resilience, Mobility and Scale

After R7, harden failover, multipath, mobility, local-first operation,
offline/reconnect, reconciliation, disaster recovery, key rotation/revocation,
upgrades, federation scale and observability.

### R9 — Future Access Technology

Add/replace access technologies through adapters without changing protocol core
semantics.

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

The project is not finished merely because software tests pass. A complete
acceptance must establish both architectural invariants and the evidence
required by the current Work Item. Physical validation remains separate from
software evidence.

## Fresh-session guarantee

A new LLM with only this repository and GitHub access must be able to determine
without conversation history:

- current mission;
- current authoritative architecture;
- current roadmap and next gate;
- current execution state;
- whether implementation is authorized;
- the exact Work Item contract and dependencies;
- worker-dispatch limits;
- verification requirements;
- historical facts that must not be rewritten.
