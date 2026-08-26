# ADCOS 5G RAN Integration — 5G RAN integration adapter (WORK-020)

## Status

**ACTIVE — Module Authority: 5G RAN integration boundary (the session↔radio-bearer mapping + RAN control-plane interop, NOT session/identity/resource/RAN-state authority).**

Implements `spec/work-items.md` WORK-020 (5G RAN integration adapter); architecture §3/§10/§16/§25-rule-9/§29 + locks LOCK-002/006/016/017/018/023; accepted WORK-016 (adapter SDK) + WORK-019 (5G Core integration) as authoritative handoff. Anchored to the frozen sources (`spec/work-items.md`, `spec/dependency-graph.md`, `spec/architecture-lock.md`) and the architect-anchored implementation brief recorded in worklog `1-orchestrator`.

## Authority boundary

```
RAN INTEGRATION
    != SESSION AUTHORITY        (session_id is sacred and access-independent
                                  -- LOCK-006; read-only passthrough, never
                                  minted/mutated/re-derived here)
    != RAN ROUTE IDENTITY       (bearer/gNB refs are RAN-side opaque
                                  identity, never collapsed onto
                                  session_id -- R1 invariant, checked
                                  mechanically at the seam)
    != IDENTITY AUTHORITY       (WORK-004)
    != RESOURCE AUTHORITY       (WORK-008; PRB/DRB accounting is mapped DATA)
    != POLICY AUTHORITY         (caller-supplied policy DATA)
    != TOPOLOGY AUTHORITY       (CU/DU/RU boundary mapping is adapter-owned
                                  DATA)
    != ACCESS/VENDOR AUTHORITY  (LOCK-016/017; concrete RAN stacks --
                                  OpenAirInterface, O-CU/O-DU/O-RU-style
                                  open implementations, future RAN -- are
                                  adapters behind the seam)
    != RAN STATE AUTHORITY      (gNB/CU/DU/RU/cell/RRC state lives in the
                                  adapter, NEVER in ADCOS core)
```

## The standards boundary (LOCK-018)

```
ADCOS RAN INTEGRATION CONTRACT (core semantics)
    session↔radio-bearer mapping, route/session identity separation,
    CU/DU/RU split mapping, capability/health/resource observation
        |
        |  behind RanContract -> SandboxedRan -> RanManager
        v
CONCRETE RAN STACKS (external implementations)
    OpenAirInterface (real gNB on real SDR hardware: CU/DU + nr-softmodem)
    an O-RAN O-DU/O-RU combination (O-RAN.WG4 split 7-2x fronthaul)
    another 3GPP R15/R16 NG-RAN implementation
    future IMT-2030/6G radio (WORK-038)
```

Three consequences, stated plainly:

1. The ADCOS core defines NO RAN primitive of its own. The 3GPP TS 38.300/38.401/38.473/38.463/38.331/38.321/38.413 and O-RAN.WG1/WG2/WG4 reference SHAPES appear as DATA with TS citations; no RAN state machine, no RRC/F1/E1 type, no RNTI/DRB material is imported into the core (LOCK-002/016; verified by the WORK-020 selftest's no-core-RAN-leakage audit).
2. Concrete RAN stacks plug in behind `RanContract` without modifying the manager or any core semantics. The `OpenRanAdapter` is one production-shaped implementation; another RAN plugs in behind the same ABC (the W020 acceptance criterion "ADCOS core imports no vendor/Open RAN implementation types").
3. RAN identifiers (RNTI, DRB id, QFI, UE context) live ONLY inside the adapter/implementation and the RAN stack itself — they are adapter-private opaque state. The boundary exposes `ran:<kind>:<digest>` opaque references only (LOCK-006/023).

## Bearer/session identity separation (R1)

The boundary holds the mapping between a WORK-012 session (sacred content-derived `session_id`) and a RAN-side ROUTE identity (the content-derived `ran:bearer:<digest>` reference). Route/session identity SEPARATION is the central invariant: a bearer re-bind produces a NEW `ran:bearer:` reference bound to the SAME `session_id`; the boundary NEVER collapses them (`assert_ref_session_separation` rejects any ref that embeds or equals the session_id — mirrors the WORK-018 `flow_id`/`session_id` and WORK-019 `pdu_session_id` separations).

## Credential and identifier isolation (LOCK-023)

No credential material crosses the RAN boundary at all — the RAN carries no subscriber credentials (those are 5GC AUSF/UDM territory, WORK-019). What IS enforced here is identifier hygiene: `reject_credential_like_text` scans caller-supplied labels (cell ids, gNB names, element ids, allocation purposes) for credential-like material so an implementation cannot smuggle a key through a RAN label, and failure diagnostics carry exception CLASS NAMES only, never message text.

## SDK bridge (WORK-016)

`RanTechnologyAdapter` implements the WORK-016 nine-op `AdapterContract` over any `RanContract` implementation — the sanctioned translation layer (RAN implementation -> adapter translation -> generic AdapterContract -> ADCOS capabilities/resources/session mapping). It imports ONLY `AdapterContract` + `AdapterContext` from the SDK (the sanctioned dependency direction) and stays a thin translation with no state beyond its label. The RAN family deliberately defines its OWN contract ABC (the gNB/cell/bearer vocabulary is distinct from the W016 allocate/release vocabulary); the bridge is where the two vocabularies meet.

## Application transparency (LOCK-019 analog — the DoD surface)

```python
# An ordinary application uses ONLY standard session semantics.
# It imports NO ADCOS symbol, NO 3GPP type, NO RAN SDK, and never
# sees a cell id, an RNTI, or a DRB reference.
session = manager.access_path(session_id="...", now="...").value
session.connect()                   # the standards-compliant 5G access path
session.send(b"hello")              # bytes traverse AccessPathSession ->
                                    # manager -> sandbox -> OpenRanAdapter ->
                                    # real RAN bearer path
data = session.recv()                # real bytes from the radio path
session.close()
```

This is the WORK-020 definition-of-done surface: "ADCOS can provision/use a standards-compliant 5G access path."

## Real RAN interoperability (conformance evidence)

```
ordinary application
      |  standard session semantics (connect/send/recv/close)
      v
AccessPathSession.send  ->  RanManager egress
      v
SandboxedRan  ->  RanContract.egress_data
      v
OpenRanAdapter  (production-shaped; targets real O1/E2-style control)
      |  egress_data() POSTs the payload over the real bearer path
      |  provision_gnb()/activate_cell() drive real cell lifecycle
      v
RAN control-plane peer  (real HTTP + real TCP; O1/E2-style REST shapes)
      v
real HTTP response / echoed bytes
      v
AccessPathSession.recv  =  real bytes
```

A real OpenAirInterface/SDR lab cannot run in this sandbox (no root, no Docker, no cmake/meson/ninja, no SDR device nodes, no SCTP, no OAI binaries). The `OpenRanAdapter` is PRODUCTION-SHAPED: it targets a real lab's O1/E2-style control endpoint with real stdlib `http.client` requests; pointing it at a running OpenAirInterface/O-RAN lab is an endpoint config change, NOT a core change. The in-sandbox conformance evidence runs against `ReferenceRanConformanceServer`, a real REST-over-HTTP RAN control-plane peer that runs as user `z` (real sockets, real JSON, byte-identical bearer-path echo) — the WORK-019 `Reference5GCoreConformanceServer` analog, honestly disclosed: an ADCOS test implementation, NOT a real RAN stack.

## Real SDR-lab interop gate (frozen WORK-020 acceptance)

The frozen WORK-020 criterion is "at least one SDR-based lab topology works" + required verification "end-to-end lab tests". The in-repo conformance peer CANNOT close it (it has no SDR, no radio, no RF). The required gate is `adapters/ran/openran_interop.py` — environment-gated, with the frozen semantics:

- `RAN_INTEROP` unset → **SKIP** with a transparent gate-disabled disclosure (the conformance suite remains the strongest honest in-sandbox evidence).
- `RAN_INTEROP=1` + `RAN_PEER_KIND` asserting a non-real peer (`reference|inrepo|conformance_server|simulator`) → **FORBIDDEN** before any network probe — the anti-faking rule: the in-repo conformance peer can NEVER satisfy the SDR-based-lab criterion, not even as a fallback.
- `RAN_INTEROP=1` + environment cannot host a real RAN/SDR lab (control endpoint unreachable, or build_tools+oai_binaries+sdr_driver all absent) → **UNREACHABLE** with the explicit `[SDR-LAB CAPABILITY MATRIX]` (`adapters/ran/interop_env_probe.py`).
- `RAN_INTEROP=1` + reachable stack but a real phase fails (control plane, cell activation, UE/DRB evidence, SDR device evidence, payload equality) → **FAILED** with the phase named — never masked as SKIP. Notably: the `[SDR]` evidence line is earned from device-node/driver evidence in the environment, NEVER from the control plane alone, so a control-plane-only peer cannot pass.
- All six evidence lines earned — `[SDR]` `[CTRL]` `[CELL]` `[UE]` `[DRB]` `[IP]` (see `RAN_INTEROP_RUNBOOK` in `interop_env_probe.py`) — → **PASSED** with full provenance (control URL, peer kind, opaque gNB/bearer refs, payload length/equality/SHA-256, evidence tuple). This is the outcome that closes the criterion.

CI / local acceptance invocation (run ON the lab host — the `[SDR]` evidence is local device-node evidence; the case numbering lives in the WORK-020 RAN selftest, the immediately following family task):

```bash
RAN_INTEROP=1 RAN_PEER_KIND=real_oai RAN_CONTROL_URL=http://<lab-host>:9091 python3 tools/ran_selftest.py
```

**Sandbox environment blocker (honestly disclosed):** this sandbox (user `z`, no root, no Docker) cannot host a real OpenAirInterface/SDR lab — no cmake/meson/ninja on PATH (only gcc), no SDR device nodes (no `/dev/usrp*`/`/dev/soapy*`, not even `/dev/bus/usb`), no SCTP, no `/dev/net/tun`, and no OAI binaries. The gate therefore reports `UNREACHABLE` in this sandbox — a verification-environment blocker, NOT architecture permission to redefine "SDR-based lab topology" as "our reference server." The gate closes the criterion the moment it runs on a real lab host (see `RAN_INTEROP_RUNBOOK` in `adapters/ran/interop_env_probe.py`: Linux + SCTP + build tools + a USRP B2xx/N2xx-class SDR, an upstream OpenAirInterface gNB build, an attached UE, and the O1/E2-style control endpoint exposed at `RAN_CONTROL_URL`); the adapter, contract, and sandbox code need no change.

## Determinism

All instants are injected (WORK-003 `parse_instant` grammar); no wall clock. All ids are content-derived over `protocol.canonicalization.canonical_json_bytes`; no `urandom`/`secrets`/`random` anywhere in the family. The `RanManager` canonical snapshot is byte-identical across runs and across implementations (B2: `implementation_label` excluded from canonical state, exposed only via `diagnostic_state()`).

## Out of scope

- Concrete RAN vendor stacks (the OpenAirInterface process, vendor gNBs, SDR drivers) behind the seam — production deployments, not this module. This module ships a production-shaped `OpenRanAdapter` + a real conformance peer + a real-SDR-lab interop gate; running the real OpenAirInterface/SDR lab needs a lab host with an attached SDR (a verification-environment requirement, NOT an architecture permission to redefine "SDR-based lab topology" as "our reference server" — see the interop-gate section above).
- The 5G Core side of the NG interface (WORK-019), N3IWF/TNGF (W021), RAN intelligence/xApps (W026 semantics), future radio (WORK-038).
- Reinventing 3GPP/O-RAN standards (LOCK-018) — the model uses TS 38.300/38.401/38.473/38.463/38.331/38.321/38.413 and O-RAN.WG4 reference SHAPES as DATA with TS citations.
- Any second session/identity/topology/resource authority — the WORK-012 sessions module owns the session identity; the WORK-004 identity module owns node identity; this module owns the session↔radio-bearer MAPPING + RAN control-plane interop translation only.

## Verification

```
python3 tools/ran_selftest.py
```

Real RAN interoperability evidence in two layers:

1. **Conformance suite (always runs):** real HTTP + real TCP + real JSON + real bytes traversing the AccessPathSession→RanManager→SandboxedRan→OpenRanAdapter→real conformance peer path. This is the strongest honest evidence achievable in the sandbox (no root, no Docker, no SDR); the WORK-019 conformance-peer analog.
2. **Real SDR-lab interop gate (environment-gated by `RAN_INTEROP=1`):** exercises the full byte-path against a REAL OpenAirInterface/O-RAN lab on real SDR hardware (capabilities/state → gNB provisioned + cell ACTIVE on the real SDR → UE attach → DRB bound to the ADCOS session_id → payload byte-identical). Closes the frozen SDR-lab criterion when the lab is reachable; reports UNREACHABLE with the explicit capability matrix when it is not (no in-repo simulator fallback), and FORBIDDEN before any network probe on a forbidden peer-kind assertion.

Plus R1 (bearer/session identity separation), LOCK-023 (identifier hygiene + class-name-only failure diagnostics), sandbox failure isolation (BaseException isolation with class name only; contract-violation value discard), the SDK-bridge translation audit, and determinism (byte-identical snapshots across runs and implementations).
