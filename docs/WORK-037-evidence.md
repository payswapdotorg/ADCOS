# WORK-037 — Open RAN/Core interoperability profile: Implementation Evidence

**Status:** implementation delivered for Architect review.
**Branch:** `work-037-open-ran-core`, cut from the Architect's anchor
commit `518c071` (the branch-anchored W037 handoff;
`spec/prompts/WORK-037.md` is byte-untouched since that commit).
**Battery:** `tools/oran_selftest.py` — 36 cases, wired into CI after
the WORK-036 appliance step (work-item order).

## Three-class evidence separation (the W020 lesson, enforced structurally)

| Class | Meaning | Status |
| --- | --- | --- |
| A | architecture conformance | **supported-verified** (deterministic battery) |
| B | automated verification | **supported-verified** (deterministic battery) |
| C | real interoperability lab | **OPEN** — until the profile lab gate passes on a real 5G lab |

The disclosure is pinned as `interop.evidence.PROFILE_EVIDENCE_STATUS`
and asserted by battery case_06.  RF simulation, OAI RFsim, software
emulation, in-repo conformance peers, and synthetic interoperability
can never be promoted to class C — `assert_no_real_lab_claim` raises
the typed `interop.evidence-class-violation` on any A/B-to-C claim
(case_25), and `classify_profile_evidence` closes class C ONLY on an
operator-attached `ProfileLabOutcome` with status `PASSED` AND a
coherent session id.

## What was implemented (`interop/`, 7 files)

- **`errors.py`** — `InteropError` + frozen `InteropReasonCode`
  (16 reasons, `interop.` prefix).
- **`model.py`** — frozen vocabularies (5 component kinds, 7
  reference points, 2 access legs, 4 scenario legs, 9 event kinds)
  and value records (`ComponentBinding`, `ProfileDeclaration` with
  canonical bytes + digests, `InteropEvent` with content-derived ids,
  `LegEvidence`, `InteropRunResult` with the replayable
  `interop_digest`) — DATA with validation, in the WORK-033
  `agent.model` style.  `PROFILE_EVIDENCE_CLASS_MAP` REUSES the
  WORK-032 `EvidenceClass` enum as the A/B/C mapping (no second
  vocabulary).  `LegEvidence` refuses to exist with a class other
  than "B" or with a byte mismatch (evidence records are only minted
  for verified legs).
- **`profile.py`** — the pure fail-closed declaration check (5
  components exactly once, family ownership, the complete 7-point
  set, digest coherence) + the class-A completion predicate.
- **`mixed.py`** — the class-B scenario: one sacred WORK-012
  `session_id` (INPUT through a read-only lookup; never minted)
  across four legs over the accepted conformance peers — 5G Core PDU
  session (W019 seam), RAN access path (W020 seam, the canonical
  band-78/F1/O-RAN-7-2x lab shape), N3IWF tunnel (W021 seam), 5G Core
  re-bind — with byte-identical round trips, journaled access
  changes, cross-family ref opacity, and the full-replay
  `verify_interop_replay`.
- **`labgate.py`** — the class-C gate: composes the three accepted
  real interop gates verbatim (each leg keeps its independent
  operator switch; the anti-faking guards fire inside the legs before
  any network probe); the profile adds the session-coherence
  precondition; the pure `aggregate_leg_outcomes` matrix (FORBIDDEN >
  UNREACHABLE > LEG_FAILED > LEG_DISABLED; PASSED only when every leg
  passes); the frozen operator runbook (pure DATA).
- **`evidence.py`** — the three-class evidence model with the
  anti-promotion guard.
- **`__init__.py`** — the frozen 45-export public API.

## Coverage vs the frozen contract

| Required discrimination | Evidence |
| --- | --- |
| mixed access demonstrated | case_07 (one session_id across 4 legs: 3 three-gpp + 1 non-three-gpp; byte-identical echoes; 2 journaled access changes), case_16 (coherence pure), case_11 (journal: no raw refs, content-derived ids) |
| adapter boundaries remain clean | case_10 (cross-family ref opacity: 6 leaky shapes rejected), case_26 (no authority constructor in `interop/`), case_27 (imports only adapters.fivegc/ran/wifi + conformance + protocol.canonicalization + stdlib), case_28 (102 core modules import no interop/ and no adapter implementation modules) |
| profile is declarative + fail-closed | case_03/04 (records + 9-shape negative matrix at BOTH gates) |
| session discipline | case_08 (unknown/unsecureable/mistyped/empty refusals typed, before any peer starts) |
| real-lab criterion NEVER faked | case_17 (GATE_DISABLED default), case_18 (LEG_DISABLED names the independent leg switches), case_19 (FORBIDDEN propagates from the per-leg anti-faking guards), case_20 (UNREACHABLE aggregation: environment blocker, no in-repo fallback), case_21 (aggregation matrix: PASSED only when every leg passes), case_25 (A/B may never claim C; C closes only on a coherent PASSED gate outcome) |
| determinism | case_13 (fresh runs byte-identical), case_14 (`PYTHONHASHSEED` 0/1/7919/None subprocess invariance), case_15 (replay: structural + full re-run; 4 tamper shapes rejected) |
| injected clock / purity | case_29 (no wall clock, randomness, or socket in `interop/`; the environment is read only by the lab gate) |
| secret hygiene | case_30 (no credential material in any result surface or source literal; slot NAMES only) |
| later-work freedom | case_31 (no later-work naming tokens in `interop/`) |
| frozen surfaces | case_01/02/05 (vocabularies + maps + the W032 evidence-class reuse), case_33 (API exact: 45 exports), case_34/35 (spec/ frozen except the Architect's branch-anchored handoff, byte-untouched since `518c071`; PR-delta shape), case_36 (CI wiring + ordering after the appliance step) |

## The real-lab runbook (class C — how to close it)

`interop.labgate.profile_lab_runbook()` records the frozen runbook
(case_23): a real lab host with a real Open5GS core (SBI + UPF data
network), a real SDR-based RAN (OpenAirInterface gNB or O-RAN
O-DU/O-RU on real SDR hardware, with a UE attached through the
radio), and a real N3IWF non-3GPP path (kernel IPsec/XFRM), driven
with `ORAN_INTEROP=1` plus every leg's own switch
(`OPEN5GS_INTEROP=1`, `RAN_INTEROP=1` with `RAN_PEER_KIND=real_oai`,
`WIFI_INTEROP=1` with `WIFI_PEER_KIND=real_n3iwf`) and
`ORAN_INTEROP_SESSION_ID` set to the real session under test.  The
gate closes class C only when every leg passes on real
infrastructure with the one coherent session id.

## Flagged battery amendments (all narrowing, DAG-cited)

1. `tools/agent_selftest.py` case_40 — `allowed_docs` +=
   `docs/WORK-037-handoff.md` + `docs/WORK-037-evidence.md`;
   `allowed_tools` += `tools/oran_selftest.py`; the spec/ delta check
   admits exactly `spec/prompts/WORK-037.md`.  (W033 → W037: the
   profile names the reference agent as its fifth component; the
   Architect anchored the W037 handoff on the designated branch —
   commit `518c071` — with main's accidental publication reverted.)
2. `tools/edge_selftest.py` case_47 — same spec/ admission;
   `allowed_exact` += the interop battery + both docs; the
   `unexpected` filter admits the `interop/` prefix.  (W034 → W037:
   work-item order.)
3. `tools/mobile_selftest.py` case_44 — same admission pattern.
   (W035 → W037: work-item order.)
4. `tools/appliance_selftest.py` case_41 — same admission pattern.
   (W036 → W037: work-item order.)
5. `.github/workflows/spec-check.yml` — one additive step ("Run Open
   RAN/Core interop profile tests") after the appliance step.

No other battery, spec file, or frozen surface was touched.
