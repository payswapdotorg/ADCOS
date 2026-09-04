# ADCOS Canonical Implementation Roadmap

**Status: AUTHORITATIVE PROJECTION**

Machine-readable authority: `spec/architect/roadmap.yaml`.
Frozen architecture remains authoritative in `spec/architecture.md`, `spec/architecture-lock.md`, `spec/work-items.md`, and `spec/dependency-graph.md`. This roadmap does not authorize implementation.

## Current execution state

- Live main at W052 acceptance/transition: `bcaf0d0677437d1ffca8f5e493cab516c87e7194`
- Active Work Item: **WORK-053 EconomicAllocation**
- Active authorization: **WORK-053-CORE-001**
- Authorized baseline: **bcaf0d0677437d1ffca8f5e493cab516c87e7194**
- W051: accepted/merged
- W052: accepted/merged at exact reviewed head `7d883b2`, merge `bcaf0d0677437d1ffca8f5e493cab516c87e7194`
- W053: active-authorized; implementation not yet delivered
- W040: independent physical-validation/evidence track, in-review and not accepted
- W043: retired/unassigned

The live baseline was reconciled by DEC-0060 / LEDGER-RECON-009 and PR #147, merged as `2e87cb3`. The authorization itself is unchanged; only the persistent baseline was advanced to the authorization-bearing post-transition mainline.

## Authority model

`roadmap.yaml` answers what Work Items exist, how they depend on one another, and their verified program state. It does **not** authorize implementation.

Authorization is authoritative only through `spec/architect/authorizations/` and the governing decision record. Execution facts are authoritative in `execution-state.yaml` and `execution-ledger.yaml`.

A Work Item reaches accepted/merged only through Architect review and acceptance of the exact delivery head.

## Program DAG

```text
W001 → W002 → W003 → W004 → W005 → W006 → W007
                               ↘       ↘
                                W008 → W009 → W010
W007 + W008 + W009 + W010 → W011 → W012 → W013 → W014
W004 + W005 + W007 + W010 + W011 → W015
W003 + W005 + W012 → W016
W003 + W004 + W012 → W017
W012 + W017 → W018
W016 + W017 + W018 → W019 → W020
W018 + W019 → W021
W016 + W018 → W022
W011 + W013 + W022 → W023
W018 + W019 + W021 + W022 → W024 → W025
W007 + W008 + W011 + W012 + W016 → W026 → W027
W004 + W005 + W007 + W010 + W015 + W017 → W028
W003 + W005 + W016 + W026 → W029
W010 + W011 + W012 + W015 + W026 → W030
W007 + W011 + W012 + W013 + W027 → W031
W003 + W004 + W005 + W007 + W011 + W012 + W015 + W016 + W017 → W032
W016 + W017 + W018 + W026 + W029 + W030 + W032 → W033
W020 + W021 + W022 + W023 + W024 + W033 → W034
W012 + W013 + W018 + W033 → W035
W024 + W025 + W030 + W033 + W034 → W036
W019 + W020 + W021 + W032 + W033 → W037
W016 + W029 + W032 + W033 → W038
W015 + W031 + W033 + W036 → W039

W016 + W018 + W033 + W034 → W041
W012 + W013 + W014 + W033 + W035 + W041 → W042

W051 → W052 → W053
W051 + W053 → W044
W051 + W053 + W044 → W045
W051 + W052 + W053 + W044 + W045 → W046
W051 + W044 + W045 + W046 → W047
W041 + W042 + W051 → W048
W046 + W047 + W048 → W049

W050 ──advisory capability input──→ W048
W050 ──advisory capability input──→ W049

W040 is independent of the implementation DAG.
W043 is retired and intentionally unassigned.
```

## Dependency semantics

**hard** — downstream execution may not be accepted/merged before the dependency is accepted.

**advisory** — the dependency supplies bounded input but does not gate authorization or execution. W050→W048/W049 is advisory only.

**independent** — no execution-order obligation. W040 is the independent physical-evidence track.

## Current Work Item states

| State | Work Items |
|---|---|
| Accepted / merged | W001–W039, W041, W042, W044–W052 |
| Active / authorized | W053 |
| In review / not accepted | W040 |
| Retired | W043 |

## W053 execution packet

Contract: `spec/work-items.md` WORK-053 + `docs/WORK-053-handoff.md` + `spec/architect/authorizations/WORK-053.yaml`.

Scope: `usage/`, `tools/usage_selftest.py`, `docs/WORK-052-handoff.md`, `docs/WORK-052-evidence.md`, and one additive CI battery step. The implementation PR must not modify `spec/architect/`.

Authority: W052 owns usage/economic ledger state only. It consumes authoritative delivery evidence and references W051/W041/W042/W033 interfaces; it must not create or mutate identity, session, NetworkPath, routing, transport, payment, or delivery authority.

Acceptance: authoritative delivery evidence only; payment capture never creates usage; reservation/lease never creates usage; duplicates do not double-charge; out-of-order/delayed observations are deterministic; billable finality is explicit/immutable; corrections are append-only; restart/replay is byte-identical; unknown/fabricated evidence fails closed.

## Next-order rule

Exactly one Work Item may be active-authorized. The current target is W053 under `WORK-053-CORE-001`. Roadmap placement alone never authorizes W044 or any other downstream item.

## Fresh-architect recovery

To recover after context loss, read in order:

1. `spec/architect/roadmap.yaml`
2. `spec/architect/execution-state.yaml`
3. `spec/architect/execution-ledger.yaml`
4. the active `spec/architect/authorizations/WORK-XXX.yaml`
5. its Work Item contract/handoff
6. the corresponding GitHub issue and open implementation PR

The implementation branch must start from the exact live mainline carrying the active authorization. One Work Item, one branch, one implementation PR. No self-authorization and no self-merge.
