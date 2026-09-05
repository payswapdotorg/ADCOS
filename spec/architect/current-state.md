# ADCOS Current State

**BLOCKED — canonical mainline-integrity reconciliation required before implementation.**

## Repository

- Repository: `github.com/pectoraux/ADCOS`
- Actual `main`: `a7d913385f866df6da890093c26539ad876f3ee4`
- Last persisted execution snapshot: `bb29c11c8bba6c9db5b87f85b1d62faad0bf7825`
- Architecture: `1.0` frozen
- Protocol: `1.0`

## Program authority

The frozen roadmap is `spec/architect/roadmap.yaml`, Version 1.0. The immediate gate is `R0_MAINLINE_RESTORATION`. The roadmap is the only program roadmap; chat, issue prose, old handoffs, and external planning documents do not govern execution.

## Execution

- Mode: `blocked`
- Active Work Item: none
- Active authorization: none
- Governing decision: `DEC-0080`
- Halt reason: the actual mainline advanced to `a7d9133`, while the persisted snapshot remained `bb29c11`. More importantly, durable repository/GitHub history proves accepted W044-W049 deliveries whose implementation artifacts are not all present on current main. This is a mainline-integrity defect.

## Durable accepted delivery history requiring restoration

| Work Item | Reviewed head | Accepted merge | Current mainline |
|---|---|---|---|
| W044 | `6720d220e390999e17707537ab587c1da3b09eb9` | `90864ac257a3d93d94852cfa3a74577903f508d3` | missing |
| W045 | `827234ec3a245a6b9f2f2de5d6525afb495684cc` | `a789d9b403d0e2a6e05276bb3cdc2b7d092c6d88` | missing |
| W046 | `09960ea24315e5d0ccfd516d3bdca0802b62d8b7` | `f45be6dd0544a2fd6cbc910805def28bbe0c71eb` | missing |
| W047 | `348154d063c0e0a12d5635cb2093c67a507a4064` | `7bc31f2899307c56639887416d602b41b4c16f43` | missing |
| W048 | `e2af4bd20e403c1d4ee9717f7eea8809c16a53cd` | `ce1ccaea328743a05cf8d6fa87a114e69d9e253c` | missing |
| W049 | `b8cc17ef21f6c38266152552590dc73f80c056ce` | `89ad6ff3d168c59256c3e805539eb9ca22f6b3bc` | missing |
| W050 | accepted staged history | reconstructed implementation | present |
| W051 | `e247b4e32e7b1dc345292af5ad7e1b49297cad6f` | `41b338080fbeb79627bff45cd79ddf09bf5cbb29` | present |
| W052 | `7d883b227e9792b98efdbc1916d413491d20d458` | `bcaf0d0677437d1ffca8f5e493cab516c87e7194` | present |
| W053 | `4a0021c4d464bf1e0e9d9b29ff8a87ed8eb8146a` | `bb29c11c8bba6c9db5b87f85b1d62faad0bf7825` | present |

These are historical facts recorded for restoration planning. They do not constitute current implementation permission.

## Independent physical track

W040 remains `in-review`, unaccepted, and independent. EVID-007 and EVID-008 remain open and W040-owned. No software evidence is promoted to physical evidence.

## Next actions

1. R0: restore accepted W044-W049 implementation/evidence/CI artifacts from repository Git history only, without unrelated ancestry.
2. R1: reconcile the durable governance snapshot to the restored mainline and ensure exactly zero active implementation authorizations until a fresh authorization is issued.
3. R2 onward: continue strictly in the frozen roadmap order.

## Source of truth

This file is a current-state projection only. The program is governed by `roadmap.yaml`; lifecycle history by `execution-ledger.yaml`; permission by repository-local authorizations; contracts by the frozen specification. No conversation context is required or authoritative.
