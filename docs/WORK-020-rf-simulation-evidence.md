# WORK-020 RF-simulation evidence record

## Evidence classification (the Architect work order's required form)

```text
W020 architecture conformance       PASS
W020 automated verification         PASS
W020 RF-simulation interoperability PASS
W020 physical-SDR lab evidence      OPEN
```

- **Architecture conformance — PASS.** The RAN adapter family satisfies the
  frozen WORK-020 boundary: ADCOS core imports no vendor/Open RAN types
  (case_22), RAN capability/health/resource state is mapped through the
  adapter (cases 09-12), RAN failure is isolated from core state (cases
  26-29, 38-39), and the W016 SDK bridge stays a thin sanctioned
  translation (case_23).
- **Automated verification — PASS.** `python3 tools/ran_selftest.py`
  reports `PASS (46/46 cases)` — the deterministic reference battery
  (01-29), the standards-boundary/frozen-spec/leakage audits (20-23),
  the real-HTTP conformance legs (25, 30), the environment-gated
  SDR-lab gate cases (31-32, honest SKIP/FORBIDDEN/UNREACHABLE), and
  the RF-simulation phase (33-46).
- **RF-simulation interoperability — PASS.** The independent
  OAI-RFsim-style environment (below) exercises the existing RAN
  adapter boundary end to end: control-plane provisioning and cell
  lifecycle, UE/session establishment, bearer/data-plane establishment,
  byte-identical application delivery over the full adapter path,
  radio-driven failure isolation, and three-way implementation
  substitution with byte-identical canonical core semantics.
- **Physical-SDR lab evidence — OPEN.** The frozen WORK-020 acceptance
  criterion ("at least one SDR-based lab topology works") requires a
  real SDR-based lab run (see `docs/WORK-020-real-sdr-acceptance.md`
  for the recorded host blocker and `RAN_INTEROP_RUNBOOK` in
  `adapters/ran/interop_env_probe.py` for the lab recipe). RF
  simulation is NOT physical SDR evidence: `rf_simulation`/`rfsim`
  are FORBIDDEN peer kinds in the interop gate, which keeps requiring
  the `[SDR]` device-evidence line. This phase does not redefine,
  weaken, or close that criterion.

## Simulator environment

`adapters/ran/rfsim.py` — an INDEPENDENTLY implemented OAI-RFsim-style
gNB/UE emulation environment (Architect work order, PR #21 comment
5452614288), NOT the in-repo `ReferenceRanConformanceServer`:

- `RfSimRanPeer`: a real REST-over-HTTP RAN control-plane peer on
  `127.0.0.1:<ephemeral>` serving the frozen O1/E2-style surface the
  production `OpenRanAdapter` speaks (capabilities/state, gNB
  provision/decommission, cell activate/deactivate, bearer
  bind/unbind, bearer data, allocations).
- `RfSimScenario` / `RfSimEnvironment`: the radio-channel model, all
  integer arithmetic with frozen constants — TR 38.901 UMa NLOS
  path-loss anchors (3.5 GHz), TR 38.901 shadowing (sigma = 6 dB,
  discretized), per-transmission fast fading (±3 dB), per-PRB thermal
  noise (-111437 milli-dBm), dB-domain interference combination, and a
  TS 38.214-inspired SINR -> MCS ladder.
- Radio-derived control-plane behavior: admission requires an
  rx-power floor and an mcs-1 SINR floor; PRB demand grows as MCS
  falls; health degrades when a live bearer's SINR drops below the
  healthy floor; per-transmission decode success is conditioned on the
  current SINR (typed 503 failure, never a corrupted echo); serving
  cells are selected geometrically (strongest received power), not by
  insertion order.
- Determinism: every shadowing/fading draw is a pure content-addressed
  function of (seed, label) via sha256 rejection sampling — no wall
  clock, no randomness, no `os`, no `math`, no environment reads.

Independence is mechanical (battery case_43): `rfsim.py` imports
nothing from `conformance.py`; its only engine imports are the
conformance-precedent ref-minting helper set
(`_mint_ref`/`FIRST_RNTI`/`LAST_RNTI`/`RAN_ALLOCATION_KINDS`), so
identical operation histories mint identical references and canonical
manager state stays byte-identical across the engine, the conformance
peer, and the RF-sim peer (case_41) — while the RF-sim peer's
radio-driven behavior diverges from both (cases 37/40/46).

## Commands

```bash
python3 tools/ran_selftest.py          # full battery incl. RF-sim cases 33-46
python3 -m mypy --strict --follow-imports=silent adapters/ran/rfsim.py
python3 tools/spec_check.py            # governance checker
```

## What the RF-simulation phase verified (work-order item 3)

| Work-order requirement | Evidence |
| --- | --- |
| ADCOS session_id remains distinct from RAN bearer/RNTI/DRB identity | case_35 (R1 through the RF-sim path, wire-level identity hygiene) |
| Control-plane provisioning and cell lifecycle | case_36 (strict transitions, degrade-not-kill, decommission-under-live-bearer) |
| UE/session establishment | case_34 (rrc >= 1, drb >= 1), case_40 (coverage admission + mobility) |
| Bearer/data-plane establishment | case_34, case_37 (geometric cell selection, channel-derived PRB demand) |
| Application bytes traverse the complete adapter path and return byte-identically | case_34 (twice, two fading draws), case_38 (recovery), case_41 (three implementations) |
| RAN failures remain isolated from core state | case_38 (RF degradation), case_39 (cell outage; new work on a second gNB during outage) |
| Adapter implementation substitution does not alter canonical core semantics | case_41 (engine == conformance peer == RF-sim peer, DIRECT byte-identical canonical state) |
| Deterministic evidence/reporting and secret-free diagnostics | case_33 (two peers, identical bytes), case_44 (subprocess + PYTHONHASHSEED 0/1/7919), case_45 (reason-token wire errors, no credential material) |

Discriminating regressions (work-order item 5): case_46 — seed
sensitivity, geometry sensitivity, exact-loss degradation sensitivity,
fading variance per transmission, and rejection of an RF-sim peer that
collapses the session identity onto the bearer ref
(ran-session-collapse, no binding registered); case_37 (geometric vs
insertion-order selection); case_40 (the radio-less reference engine
accepts the bind the RF-sim environment refuses — the channel model
provably drives admission).

## Anti-faking rules preserved

- `rf_simulation` and `rfsim` are FORBIDDEN peer kinds in the SDR-lab
  interop gate (case_42: FORBIDDEN fires BEFORE any network probe;
  zero socket connections; no `[SDR]` evidence; no PASSED).
- The gate-disabled SKIP disclosure names BOTH in-sandbox paths — the
  conformance suite and the RF-simulation environment — and states
  that neither can satisfy the frozen SDR criterion (case_31).
- No new PASSED path exists in `run_openran_interop`; the `[SDR]`
  evidence line remains environment/device evidence only.

## Remaining SDR gap (explicit)

Full WORK-020 acceptance still requires the real SDR-based lab run on
a host with an attached, authorized SDR; a supported real
OpenAirInterface/O-RAN build; a real radio UE; and a shielded or
authorized lab frequency, per `RAN_INTEROP_RUNBOOK`
(`adapters/ran/interop_env_probe.py`) and
`docs/WORK-020-real-sdr-acceptance.md`. That run alone can close
criterion 4; this RF-simulation phase closes engineering and
conformance uncertainty only, as the work order's acceptance
consequence states.
