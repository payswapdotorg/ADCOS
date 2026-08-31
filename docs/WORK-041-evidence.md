# WORK-041 Evidence — First-Class Network Path and Platform Integration

**Authorization:** `WORK-041-CORE-001` (DEC-0052) — active, baseline
`bb964a1bd94176dc55f6870ffcdaf75445cc657`
**Architecture basis:** ACR-005 (accepted by DEC-0047); ACR-006
(accepted by DEC-0048) consumed where applicable
**Implementation branch:** `work-041-networkpath-core` (cut from main
`ece53db`, which carries the authorization record byte-identically
from `bb964a1`)
**Evidence classes (per the authorization record):** Software /
architecture conformance — SOFTWARE; Deterministic automated
verification — SOFTWARE; Physical deployment evidence — **not
required for W041**; any physical claims remain governed by WORK-040's
open PHYSICAL obligations (EVID-007 PARTIAL, EVID-008 NOT-TESTABLE,
both OPEN and W040-owned).

## 1. What was implemented

A technology-neutral `NetworkPath` family over existing
authority-owned state, exactly inside the authorized scope:

```text
networkpath/                (new package, 11 modules)
    __init__.py             public API (45 frozen names)
    errors.py               typed error model + frozen reason vocabulary
    state.py                frozen lifecycle vocabulary + transition table
    model.py                NetworkPath / PlatformObservation / LifecycleEvent
    observation.py          platform-observation boundary (reuses InterfaceSource)
    validation.py           deterministic candidate validation verdict
    binding.py              authority-mediated binding + deterministic probe
    lifecycle.py            NetworkPathManager (the public production surface)
    evidence.py             evidence chain records + digests + disclosure
    integration.py          session-continuity facts (public session reads)
tools/networkpath_selftest.py   the W041 battery (36 cases)
docs/WORK-041-handoff.md       implementation-level handoff (this delivery)
docs/WORK-041-evidence.md      this document
```

Lifecycle (the contract's own vocabulary — no invented state names):

```text
DISCOVERED -> VALIDATED -> BOUND -> ACTIVE -> RETIRED
```

with `PROBE` a journaled state-preserving action (`BOUND -> BOUND`)
that activation requires. The WORK-013 constituent-status vocabulary
(`ACTIVE / DEGRADED / FAILED`) is a different concern (multipath plan
constituents) and is neither reused nor redefined here.

## 2. Deterministic automated verification

All commands run from the implementation branch
(`work-041-networkpath-core`, base `ece53db` = origin/main):

| Command | Result |
| --- | --- |
| `python3 tools/networkpath_selftest.py` | **PASS 36/36** |
| `python3 tools/spec_check.py` | PASS 17/17 |
| `python3 tools/spec_check.py --provenance` | PASS 2/2 (implementation delta covered by WORK-041-CORE-001) |
| `python3 tools/spec_check_selftest.py` | PASS 32/32 |
| `python3 tools/agent_selftest.py` | PASS 45/45 |
| `python3 tools/mobile_selftest.py` | PASS 46/46 |
| `python3 tools/pilot_selftest.py` | PASS 30/30 |

Existing accepted batteries remain green; no frozen authority
ownership changed (see §4).

## 3. Acceptance-criterion mapping

### Criterion 1 — session continuity across distinct validated paths

- Battery cases: `case_11_session_continuity_handover`,
  `case_13_technology_neutral_breadth`,
  `case_12_handover_ordering_old_retired_last`.
- Evidence: one logical session established through the ordinary
  production chain (policy gate -> route evaluation -> session create
  -> transport handshake) moves Wi-Fi (`wlan0`, wireless) ->
  Ethernet (`eth0`) -> USB-tethering class (`usb0`, link kind
  `other`) -> cellular class (`cellular0`, link kind `other`) with:
  - `session_id` byte-identical before/after (content-derived by the
    session authority; never recreated);
  - exactly **one** `created` event in the session's append-only
    journal on both sides (never destroyed and re-created);
  - session state `ESTABLISHED` throughout;
  - **no** `reconnected` session events (the handover is a
    binding-level path change, not a logical session replacement);
  - the WORK-018 IP binding id CHANGES across the handover (real
    re-binding through the ordinary WORK-033 `bind_session` path —
    the W040-corrected mechanism);
  - old path RETIRED only AFTER the candidate is ACTIVE.

### Criterion 2 — candidates are detected without becoming active

- Battery cases: `case_07_discovery_candidates_not_active`,
  `case_08_duplicate_discovery_idempotent`,
  `case_10_candidate_gates_before_chain`,
  `case_19_activate_requires_probe_evidence`.
- Evidence: discovery leaves every candidate `DISCOVERED` with no
  binding facts, no probe evidence, no session reference, and the
  active-path table untouched; `activate`/`bind`/`probe` from
  `DISCOVERED` all fail closed; activation additionally requires
  recorded traffic-proof evidence (`BOUND` alone never activates);
  duplicate discovery is an idempotent no-op.

### Criterion 3 — failed validation/bind/probe preserves the active path

- Battery cases: `case_15_validation_failure_preserves_active`
  (link-down interface),
  `case_16_stale_candidate_identity_drift` (content drift),
  `case_14_dynamic_exposure_gates_validation` (adapter not yet
  exposed), `case_17_bind_failure_preserves_active` (unknown session;
  suspended session), `case_18_probe_failure_preserves_active`
  (transport-level probe rejection on a suspended session).
- Evidence: in every failure family the existing ACTIVE path record
  is untouched, the candidate is NOT ACTIVE (and carries no
  fabricated evidence), and the logical session remains valid. The
  transactional `handover` composes exactly the contract ordering
  (validate -> bind -> probe -> activate -> retire old LAST); any
  step failure aborts with a typed error before the old path is
  touched.

### Criterion 4 — evidence is explicit, deterministic, replay-safe, independently verifiable

- Battery cases: `case_24_determinism_two_runs`,
  `case_25_subprocess_hash_seeds`,
  `case_26_evidence_chain_explicit_and_verifiable`,
  `case_27_evidence_replay_safe_and_tamper_evident`,
  `case_28_evidence_secret_free`, `case_23_replay_of_operation_sequence`.
- Evidence: each `PathEvidenceRecord` carries the named chain links
  (observation digest/instant, validation verdict digest, binding
  facts, traffic-proof digests, ordered lifecycle events); two fresh
  runs produce byte-identical content/evidence/journal digests;
  `PYTHONHASHSEED` 0/1/2 subprocess runs agree byte-for-byte;
  replaying the whole operation sequence fails closed with digests
  unchanged; tampered records are digest-evident; illegal chains
  (binding without validation) are rejected by
  `verify_path_evidence`; records carry ids and digests only (no
  boot secrets, no key material — battery-pinned).

### Criterion 5 — existing accepted batteries remain green; no frozen authority ownership changes

- Evidence: `agent_selftest` 45/45, `mobile_selftest` 46/46,
  `pilot_selftest` 30/30, `spec_check` 17/17, `spec_check
  --provenance` 2/2, `spec_check_selftest` 32/32 (§2).
- Structural audits (battery cases 29–36): imports confined to
  `protocol` / `agent` / `adapters` / `sessions`; no authority
  construction or session-mutation tokens; no foreign-private
  attribute access; no vendor/platform tokens; frozen public API
  surface; the five frozen spec files byte-identical to origin/main;
  the PR delta confined to the authorized WORK-041-CORE-001 scope;
  honest two-track evidence disclosure.

## 4. Authority ownership (unchanged, one of each)

| Authority | Owner | NetworkPath relationship |
| --- | --- | --- |
| Identity | WORK-004 | consumes `node_id`; path id is a fingerprint, never a NodeID |
| Session | WORK-012 | read-only continuity checks; binding flows through the runtime's session gates; `session_id` never recreated |
| Routing | WORK-011 | untouched; exposes path facts only |
| Transport | WORK-017 | probe drives the ordinary `send_datagram` path |
| Adapters | WORK-016 | binding drives the ordinary `bind_session`/`unbind_session` paths |
| IP integration | WORK-018 | the runtime's ordinary IP binding path (changed on handover, as in the W040-corrected mobile flow) |
| Policy | WORK-010 | untouched (session admission remains policy-gated in the runtime) |
| Federation | WORK-014 family | untouched |
| Discovery | WORK-006 / WORK-033 | reuses `InterfaceSource` — no competing discovery authority |
| Evidence chain | W041's own journal | the one thing NetworkPath owns: candidate-path lifecycle evidence |

## 5. Physical evidence boundary (honest disclosure)

`NETWORKPATH_EVIDENCE_STATUS` (pinned by the battery):

```text
software_deterministic_path_lifecycle: supported-verified
physical_device: open
```

No software or emulator run in this delivery claims `5G PASS`,
`Android physical PASS`, or any PHYSICAL-class result. EVID-007
(PARTIAL) and EVID-008 (NOT-TESTABLE) remain OPEN and W040-owned.

## 6. Determinism discipline

- All instants through the injected WORK-033 clock seam
  (`StepClock`/`FixedClock`; `SystemClock` is the only sanctioned
  wall-clock site, unused here); each journaled transition consumes
  exactly one clock read so record timestamps and journal event
  instants coincide and event ids verify deterministically.
- All ids/digests content-derived over WORK-003 canonical JSON bytes.
- No `uuid`, no `random`, no wall-clock reads, no network access in
  the family (battery-pinned by source scans and digest equality
  across fresh runs and hash-seed subprocesses).

## 7. CI wiring note (out of authorized scope)

`.github/workflows/spec-check.yml` does not yet run
`tools/networkpath_selftest.py`: the workflow file is outside the
WORK-041-CORE-001 scope (`networkpath/`,
`tools/networkpath_selftest.py`, the two W041 docs), so the
implementation PR deliberately does not modify it. Wiring the battery
into CI is a one-line workflow addition for the Architect to make at
acceptance (consistent with how prior work items wired their
batteries). The mandated local verification commands (§2) have all
been run and reported here.
