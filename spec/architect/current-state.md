# ADCOS Current State

**READY (fail-closed) — R0 restored, R1 reconciled; next gate R2; zero active authorizations.**

## Repository

- Repository: `github.com/payswapdotorg/ADCOS`
- Current `main`: `a3391e86851e06032de848e6eb0b4267fa33310a`
- Reconciled governance snapshot: `a3391e86851e06032de848e6eb0b4267fa33310a` (DEC-0084 / LEDGER-RECON-012)
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Program authority

The frozen roadmap is `spec/architect/roadmap.yaml`, Version 1.1 (advanced from 1.0 by DEC-0084 — a governance/version transition only; Architecture Version 1.0 and Protocol Version 1.0 are unchanged). The next gate is `R2_SYSTEM_COMPOSITION_CONFORMANCE`. The roadmap is the only program roadmap; chat, issue prose, old handoffs, and external planning documents do not govern execution.

## R0 — complete

R0 was accepted and merged as PR #8: the canonical mainline restoration landed on the exact frozen main `3bdfb6daf50f7c000d29a027584c0de5b376d8a8` as merge commit `a3391e86851e06032de848e6eb0b4267fa33310a` (tree `1d16c241`, byte-identical to the historical restoration tree `7fb47bb`; 58,500 insertions / 0 deletions / 79 files, additive only).

## R1 — complete

DEC-0084 reconciled the durable governance projections (roadmap, current-state, execution-state, execution-ledger) to the restored mainline. Historical R1 records on the former repository lineage remain discoverable Git history only; the current authoritative R1 reconciliation is DEC-0084 at `a3391e86851e06032de848e6eb0b4267fa33310a`.

## Restored and accepted delivery history

| Work Item | Reviewed head | Accepted merge | Current mainline |
|---|---|---|---|
| W044 | `6720d220e390999e17707537ab587c1da3b09eb9` | `90864ac257a3d93d94852cfa3a74577903f508d3` | restored present (PR #8) |
| W045 | `827234ec3a245a6b9f2f2de5d6525afb495684cc` | `a789d9b403d0e2a6e05276bb3cdc2b7d092c6d88` | restored present (PR #8) |
| W046 | `09960ea24315e5d0ccfd516d3bdca0802b62d8b7` | `f45be6dd0544a2fd6cbc910805def28bbe0c71eb` | restored present (PR #8) |
| W047 | `348154d063c0e0a12d5635cb2093c67a507a4064` | `7bc31f2899307c56639887416d602b41b4c16f43` | restored present (PR #8) |
| W048 | `e2af4bd20e403c1d4ee9717f7eea8809c16a53cd` | `ce1ccaea328743a05cf8d6fa87a114e69d9e253c` | accepted; artifacts not part of the accepted restoration tree (W048 disposition below) |
| W049 | `b8cc17ef21f6c38266152552590dc73f80c056ce` | `89ad6ff3d168c59256c3e805539eb9ca22f6b3bc` | restored present (PR #8) |
| W050 | accepted staged history `4a37408`/`c5cb509`/`279871c`/`0fa231c` | present via the accepted reconstruction (`815f4fe`) | present (accepted) |
| W051 | `e247b4e32e7b1dc345292af5ad7e1b49297cad6f` | `41b338080fbeb79627bff45cd79ddf09bf5cbb29` | present (accepted) |
| W052 | `7d883b227e9792b98efdbc1916d413491d20d458` | `bcaf0d0677437d1ffca8f5e493cab516c87e7194` | present (accepted) |
| W053 | `4a0021c4d464bf1e0e9d9b29ff8a87ed8eb8146a` | `bb29c11c8bba6c9db5b87f85b1d62faad0bf7825` | present (accepted) |

These are historical acceptance facts reconciled by DEC-0084 with the original provenance preserved exactly. The current-mainline restoration merge (PR #8) is **not** the original Work Item acceptance merge and does not replace the original acceptance provenance. They do not constitute current implementation permission.

W048 disposition (exactly as accepted with R0): the W048 sharing package, its containment variant, the W048 evidence document, and the W048 selftest battery are not part of the accepted historical restoration tree (`7fb47bb`, reproduced byte-identically by PR #8) and remain absent from current main; W048's acceptance provenance is preserved unchanged, and restoring its implementation artifacts would intentionally diverge from the accepted restoration tree and requires an explicit Architect directive.

## Execution

- Mode: `ready` (fail-closed)
- Active Work Item: none
- Active authorization: none
- Governing decision: `DEC-0084`
- R2 awaits a fresh Work Item and exactly one implementation authorization issued by a new Architect decision; until then exactly zero authorizations are active and no implementation may start. No historical authorization is revived merely because its corresponding implementation is now present.

## Independent physical track

W040 remains `in-review`, unaccepted, and independent. EVID-007 and EVID-008 remain open and W040-owned. No software evidence is promoted to physical evidence.

## Next actions

1. R2: the Architect activates `R2_SYSTEM_COMPOSITION_CONFORMANCE` with a fresh Work Item and exactly one implementation authorization.
2. R4 remains the independent parallel physical track (W040).
3. No W054 or any ungoverned Work Item exists or may be created outside the frozen Work Item process.

## Source of truth

This file is a current-state projection only. The program is governed by `roadmap.yaml`; lifecycle history by `execution-ledger.yaml`; permission by repository-local authorizations; contracts by the frozen specification. No conversation context is required or authoritative.
