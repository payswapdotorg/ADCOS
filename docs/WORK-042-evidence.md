# WORK-042 Evidence — Event-Driven Platform Integration and Journal-First Recovery

**Authorization:** `WORK-042-CORE-001` (DEC-0055) — active, baseline
`96db8aa4423dff845a223e0c93c67f3dc14e314d` (the recorded main
baseline in `spec/architect/execution-state.yaml`)
**Architecture basis:** ACR-006 (accepted by DEC-0048); ACR-005
(accepted by DEC-0047) consumed through the accepted WORK-041
NetworkPath interfaces
**Implementation branch:** `work-042-platform-journal-core` (cut from
main `1909479`, which carries the authorization record
byte-identically from the recorded baseline — ARCH-08 provenance
verified)
**Evidence classes (per the authorization record):** Software /
architecture conformance — SOFTWARE; Deterministic automated
verification — SOFTWARE; Physical-device evidence — **not required
for W042**; any physical claims remain governed by WORK-040's open
PHYSICAL obligations (EVID-007 PARTIAL, EVID-008 NOT-TESTABLE, both
OPEN and W040-owned). **No PHYSICAL PASS claim is made anywhere in
this delivery.**

## 1. What was implemented

The ACR-006 event-driven platform integration and journal-first
recovery model, exactly inside the authorized scope
(`platform/`, `tools/platform_selftest.py`, the two W042 docs):

```text
platform/                (new package, 11 modules, 3827 lines)
    __init__.py             public API (55 frozen names)
    errors.py               typed error model + frozen reason vocabulary
    model.py                PlatformEvent / EventKind / SessionBindingRef /
                            IngestionOutcome + content-derived ids
    boundary.py             platform-event ingestion boundary
                            (push primary; change-detected polling fallback)
    state.py                ReconciledState + the deterministic fold
    journal.py              append-only hash-chained journal + durable
                            store seam (memory + real file store)
    checkpoint.py           journal-tail-bound compact checkpoints
    recovery.py             journal-first recovery + honest report
    lifecycle.py            PlatformIntegrator + reconciled seam views
    evidence.py             recovery evidence chain + honest disclosure
    integration.py          session-binding references (public reads)
tools/platform_selftest.py   the W042 battery (32 cases)
docs/WORK-042-handoff.md     governance part unchanged + the
                            implementation-level handoff (this delivery)
docs/WORK-042-evidence.md    this document
```

The implemented flow (ACR-006 §3 exactly):

```text
platform authority (accepted W033/W035 seams, read-only)
    -> platform event boundary (push primary / change-detected fallback)
    -> deterministic event/snapshot reconciliation (pure fold)
    -> append-only journal (hash chain, persist-then-ack)
    -> durable journal-bound checkpoint (persist-before-suspend)
    -> restart/process recovery (verify + replay tail + ONE fresh
       platform observation + honest session loss)
    -> existing session/path/authority semantics (frozen-seam
       composition; re-establishment through ordinary paths)
```

No new identity/session/routing/transport/federation/policy
authority exists (see §6). No wire schema changed. No W043+/W048
code. W040 and its evidence obligations are untouched.

## 2. Deterministic automated verification

Run on the implementation branch (`work-042-platform-journal-core`,
base `1909479` = origin/main), local full-clone context (strictest
available):

| Command | Result |
| --- | --- |
| `python3 tools/platform_selftest.py` | **PASS 32/32** |
| `python3 tools/spec_check.py` | PASS 17/17 |
| `python3 tools/spec_check.py --provenance` | PASS 2/2 (implementation delta covered by WORK-042-CORE-001) |
| `python3 tools/spec_check_selftest.py` | PASS 32/32 |
| `python3 tools/networkpath_selftest.py` | 35/36 functional PASS; case_35 fails closed on the documented branch-context scope class (the W041 battery's frozen 4-path scope gate does not admit W042 successor files; in the CI PR-context checkout it skips — the W041-accepted precedent class; on merged main it passes with no delta) |
| `python3 tools/agent_selftest.py` | 44/45 functional PASS; case_40 fails closed on the documented successor-file class (see §7) |
| `python3 tools/mobile_selftest.py` | 44/45 functional PASS; case_44 fails closed on the documented successor-file class (see §7) |
| `python3 tools/session_selftest.py` | PASS 55/55 |
| `python3 tools/adapter_selftest.py` | PASS 56/56 |
| `python3 tools/transport_selftest.py` | PASS 69/69 |
| `python3 tools/ipintegration_selftest.py` | PASS 45/45 |
| `python3 tools/schema_selftest.py` | PASS 25/25 |

The full CI-equivalent battery (every step of
`.github/workflows/spec-check.yml`) was additionally run; see §7
for the honest context matrix (CI PR-context green; the local
strict-context delta-shape class is the W041-accepted precedent and
is itemized there).

## 3. Acceptance-criterion mapping

### Criterion 1 — platform changes delivered event-first, without polling-only semantics

- Battery cases: `case_32_polling_fallback_change_detection` (an
  UNCHANGED platform sweep emits NOTHING — the fallback is
  change-detected, never a polling-only semantic),
  `case_02_event_schema_round_trip`, `case_04_event_ordering`.
- Evidence: the boundary's primary path is PUSH —
  `ingest_interface_observation` / `ingest_interface_removal` /
  `ingest_platform_state` accept one host-pushed observation each
  with its observation instant and provenance label (the platform's
  change callbacks). The polling fallback
  (`ingest_from_sources`) reads the accepted seams ONCE per call
  and emits events ONLY where the fresh observation differs from
  the reconciled state (canonical-payload comparison). ACR-006 §1
  satisfied: polling remains available as a fallback, never the
  normative mechanism.

### Criterion 2 — deterministic and idempotent event/snapshot reconciliation

- Battery cases: `case_06_event_to_snapshot_reconciliation`
  (fold == incremental state; replay identical),
  `case_07_idempotent_replay` (replaying the whole event sequence
  through the boundary is a full no-op — journal and state
  byte-stable), `case_08_duplicate_and_contradiction_rejection`
  (exact duplicate = idempotent no-op; equal-instant conflicting
  content fails closed `EVENT_CONTRADICTORY` at ingest AND in the
  fold), `case_13_journal_tail_replay`
  (`fold_state_from(checkpoint state, tail) == fold(whole journal)`
  — byte-identical for arbitrary splits),
  `case_15_stale_state_handling` (older observation journaled but
  deterministically inert — ACR-006 §2),
  `case_18_deterministic_multi_run` + `case_19_subprocess_hash_seeds`
  (determinism proofs), `case_05_snapshot_round_trip`.
- Evidence: reconciliation is a PURE fold over the ordered journal
  record list; per platform reference the latest observation is
  the greatest (observed_at, sequence) key; session-loss outcome
  records are discriminated from observations at the record-kind
  level and never enter platform state.

### Criterion 3 — process death/suspension does not lose durable authorization/journal state

- Battery cases: `case_09_journal_append_only` (the journal file
  only ever grows; no mutation API exists; the medium bytes ARE the
  canonical record serialization), `case_10_journal_tamper_detection`
  (byte flip / line reorder / half-line truncation / sequence gap
  all fail closed `JOURNAL_CORRUPT`), `case_11_snapshot_journal_
  consistency` (checkpoint state == fold of its journal prefix;
  fabricated or tampered checkpoints fail closed),
  `case_12_restart_recovery` (all in-memory state dropped; the
  successor reconstructs journal + state EXACTLY and the journal
  continues from the tail), `case_24_fail_closed_battery`
  (persist-then-ack: a store failure leaves no phantom record and
  no phantom state; construction with a non-empty store is
  rejected — `RECOVERY_REJECTED` — so durable state is never
  silently adopted).
- Evidence: every journal append is persisted BEFORE the in-memory
  acknowledgment through the injectable `PlatformStore` seam;
  `FilePlatformStore` is the real durable store (journal file
  opened append-binary only). Checkpoints are compact, secret-free,
  content-addressed, and bound to (journal tail sequence, journal
  prefix digest).

### Criterion 4 — recovery reconstructs state correctly and records session loss honestly

- Battery cases: `case_12_restart_recovery`,
  `case_13_journal_tail_replay`, `case_14_fresh_observation_
  reconciliation` (changed/removed/appeared divergences reported
  honestly, then reconciled through the ORDINARY boundary with its
  duplicate/contradiction gates), `case_16_session_loss_honesty`
  (a real WORK-012 session held through a real WORK-041 NetworkPath
  binding is durably recorded lost at recovery — idempotently; a
  COMPLETELY UNCHANGED platform still loses the session: a present
  interface never fabricates transport liveness),
  `case_17_no_session_recreation` (recovery's signature contains
  NO authority parameters — store, clock, two read-only platform
  sources only — so it cannot touch session/routing/identity state
  BY CONSTRUCTION; the successor re-establishes through the
  ordinary authority path with a NEW session id and exactly ONE
  `created` event; the dead session id never appears in the
  successor's session store), `case_26_full_integration_scenario`
  (the golden path: production session -> path lifecycle ->
  checkpoint with binding references -> process death -> recovery
  with platform drift -> successor re-establishment).
- Evidence: session loss is journaled as a `session-loss` record
  (an honest OUTCOME, discriminated from observations) with cause
  `process-restart` (the WORK-035 `SESSION_LOST_AT_RESTART`
  semantics restated as journal DATA), bound to the checkpoint it
  recovered from, idempotently keyed on (session_id,
  checkpoint_id). No session is ever recreated, resurrected, or
  mutated by recovery.

### Criterion 5 — existing accepted batteries remain green; authority ownership unchanged

- Battery table in §2; authority-ownership audit in §6.
- Every existing battery's FUNCTIONAL cases pass. The only local
  strict-context failures are delta-shape scope gates that fail
  closed on the W042 successor files (the documented W041-accepted
  branch-context class — their frozen allowlists end at their own
  work items; in CI's base-less PR checkout they skip, and on
  merged main they pass). Itemized honestly in §7.

## 4. Determinism proof

The core recovery scenario (the full golden path: production ->
death -> recovery -> successor) run at least twice in-process, then
in subprocesses under `PYTHONHASHSEED=0`, `=1`, `=7919`, and
unset. All runs produce a byte-identical digest stream:

```text
bindings=1
checkpoint_id=sha256:640aba5262651d28e99baa44ad14d163ec80d3221b7ad0f3bd4dea259e31ab00
content_digest=sha256:de8e67969cc74870055cad09abbc1e94de52d8254e0ac7498615aa8f60b97548
divergences=appeared-during-downtime:vpn0,changed-during-downtime:platform,changed-during-downtime:wlan0,removed-during-downtime:usb0
evidence_digest=sha256:4ec1bb59b6977355dda7be3f524cb8e05c0cc8511090447e2295a018fc1422b1
journal_digest=sha256:1d40e4e993f3f259fe00d107fa5894b50235b755a731a3575ec5603f19a9d3e7
lost_sessions=sha256:05d3aa00691b9e468dd3477217e0a03deee69ecd4185efd2000b3bb169e8b0fc
recovery_digest=sha256:9e66e2718bac9b8005676e1d2010612880ee402abaf1c6dff4e1cf327e6a17e7
session_id=sha256:05d3aa00691b9e468dd3477217e0a03deee69ecd4185efd2000b3bb169e8b0fc
state_digest=sha256:ac71f4025ce59b5dfb5fca565832a2de39f60f7354a0063b5bd73f2b7ff28d8c
successor_paths=4
successor_session_id=sha256:53ab9aa70d82e41e199c05a613abae3ee80aa5326559ed0204746120c1c305e8
```

Reproduction:

```bash
python3 tools/platform_selftest.py --determinism-stream   # twice
PYTHONHASHSEED=0   python3 tools/platform_selftest.py --determinism-stream
PYTHONHASHSEED=1   python3 tools/platform_selftest.py --determinism-stream
PYTHONHASHSEED=7919 python3 tools/platform_selftest.py --determinism-stream
env -u PYTHONHASHSEED python3 tools/platform_selftest.py --determinism-stream
```

The five outputs are byte-identical (`md5sum` identical; the
battery's `case_18`/`case_19` pin this continuously). The stream
includes the content-derived session ids (the WORK-012 authority's
own fingerprints), the checkpoint id, the journal digest, the
reconciled-state digest, the recovery-report digest, and the
recovery-evidence digest.

## 5. Negative tests (fail-closed coverage)

All negative paths raise the typed `PlatformError` with the
pinned reason and never mutate partial state
(`case_24_fail_closed_battery`, `case_08`, `case_10`, `case_11`):

| Negative input | Rejection |
| --- | --- |
| malformed event dict (8 shapes: non-mapping, missing fields, tampered id, unknown kind, non-instant, wrong payload family) | `EVENT_INVALID` / `OBSERVATION_INVALID`, at construction and deserialization |
| duplicate event, identical content | idempotent no-op (`DUPLICATE` outcome; no new record; journal file unchanged) |
| duplicate event id with conflicting payload | `EVENT_INVALID` (content binding, tamper evidence) |
| two events, same (reference, instant), different content (incl. observation vs removal) | `EVENT_CONTRADICTORY` at the ingest gate; re-checked by the fold on replay; nothing journaled |
| journal byte tamper (payload edit) | `JOURNAL_CORRUPT` (record fingerprint) |
| journal line reorder | `JOURNAL_CORRUPT` (hash-chain link) |
| journal half-line truncation (crash mid-append) | `JOURNAL_CORRUPT` (unparseable tail — never silently repaired) |
| journal sequence gap (impossible journal transition) | `JOURNAL_CORRUPT` (contiguity) |
| checkpoint positioned ahead of the journal | `CHECKPOINT_MISMATCH` |
| checkpoint journal-binding digest mismatch | `CHECKPOINT_MISMATCH` |
| checkpoint state not the fold of its prefix (fabricated) | `CHECKPOINT_MISMATCH` |
| checkpoint content tamper / incompatible schema | `CHECKPOINT_INVALID` |
| store append failure | `STORE_FAILED`; NO phantom in-memory record or state (persist-then-ack) |
| fresh integrator over a non-empty durable store | `RECOVERY_REJECTED` (no silent adoption; `recover()` is the only continuation path) |
| invalid platform observation (bad link kind / wrong snapshot family) | `OBSERVATION_INVALID` (typed re-wrap of the accepted models' rejections) |
| observation source raising | `OBSERVATION_SOURCE_FAILED` (OS exception never crosses the boundary) |
| ambiguous observation set (duplicate interface name) | `OBSERVATION_INVALID` (fail closed, whole set) |
| fabricated recovery evidence (no-loss claim) | `verify_recovery_evidence` -> False |

Never is an ambiguous, stale, contradictory, tampered, or corrupt
input silently converted into a PASS.

## 6. Authority ownership audit (unchanged, one of each)

| Authority | Owner (unchanged) | W042's relationship |
| --- | --- | --- |
| identity | WORK-004 | none (no NodeID is minted; ids are fingerprints only) |
| session lifecycle | WORK-012 | composed read-only: session ids appear ONLY as recorded DATA references (checkpoint bindings / loss records); recovery has NO session parameters and creates/mutates nothing; re-establishment is the successor's ordinary path |
| multipath | WORK-013 | untouched |
| mobility | WORK-014 | untouched |
| AgentRuntime | WORK-033 | composed: the battery builds runtimes over the reconciled seam views; the platform family itself never constructs or drives a runtime |
| MobileAgent | WORK-035 | semantics consumed: session-loss-at-restart honesty and checkpoint discipline are restated as journal DATA; no mobile code changed |
| NetworkPath | WORK-041 | composed through the PUBLIC surface only: `session_bindings_from_manager` reads public binding facts; the reconciled views implement the same frozen seams the manager consumes |
| routing / policy / transport / federation / adapters | WORK-011/010/017/… | untouched |

Structural proofs (battery-pinned): `case_21_no_shadow_authority`
(AST token scan — no authority construction/mutation call tokens
in `platform/`), `case_17_no_session_recreation` (recovery's
parameter set is exactly {store, clock, interface_source,
platform_source}), `case_22_import_discipline` (sanctioned imports
only: stdlib types + protocol/agent/mobile/networkpath; no
random/secrets/uuid/os/time/socket/subprocess; no vendor tokens;
stdlib-`platform` shadowing hazard scanned across the whole repo —
zero usages), `case_23_public_api_stability` (frozen 55-name API),
`case_29_frozen_spec_intact` (frozen surfaces byte-identical to
origin/main, including the authorization record itself),
`case_30_pr_delta_shape` (delta confined to the authorized scope +
the sanctioned additive-only CI wiring).

Secret hygiene (`case_20`): the durable journal bytes, checkpoint
bytes, and report streams are secret-free (battery keys/secrets
absent; no secret-like tokens); event payloads are TYPED accepted
snapshot models only — no arbitrary payloads can enter the
journal.

## 7. Full CI-equivalent battery and the honest context matrix

The complete `.github/workflows/spec-check.yml` battery was run
locally on the delivery branch (full-clone context, the strictest
available). Every battery's FUNCTIONAL cases pass. The batteries
whose PR-delta scope gates enumerate frozen successor allowlists
(W029–W039-era plus the W041 networkpath battery) fail closed on
exactly one delta-shape case each, because the W042 files postdate
their own work items — the identical, Architect-accepted class
PR #107 shipped under (documented there as "the documented
branch-context class"): in the CI PR-context checkout (no
origin/main ref) those cases skip by design, and on merged main
they pass (no delta). Concretely:

- CI PR-context (the authoritative run for this PR): all steps
  green — the delta-shape cases skip in the base-less checkout and
  the final provenance step enforces ARCH-08 strictly
  (implementation delta covered by the inherited active
  authorization).
- Local strict context: the 12 mandated commands in §2 (all green
  except the networkpath case_35 documented class) plus the full
  workflow battery: functional green everywhere; the delta-shape
  scope cases of the older successor-allowlist batteries fail
  closed on the W042 files (upgrade, management, simulator,
  conformance, agent, edge, mobile, appliance, oran, imt, scale,
  networkpath — each exactly one case, each the same class).

CI wiring: `.github/workflows/spec-check.yml` gained exactly one
additive step (`Run event-driven platform integration tests` ->
`python3 tools/platform_selftest.py`), appended after the W041
networkpath step, before the provenance-last block — the W033/W035/
W041 battery precedent for an additive `.github` delta in the
implementation PR (governance-classified in ARCH-08; never weakens
any existing step; battery case_30 verifies additivity).

## 8. Physical evidence boundary (honest disclosure)

`PLATFORM_EVIDENCE_STATUS`:

```text
software_deterministic_event_journal: supported-verified
software_deterministic_recovery:       supported-verified
physical_device:                       open
```

No PHYSICAL PASS claim is made. Physical-device evidence is not
required for W042 implementation (the authorization record's
evidence classes); any physical claims remain governed separately
by W040's OPEN obligations (EVID-007 PARTIAL, EVID-008
NOT-TESTABLE — W040-owned, untouched by this delivery).

## 9. Scope confirmation

- `git status --short`: only `platform/` (11 new files),
  `tools/platform_selftest.py` (new),
  `docs/WORK-042-handoff.md` (implementation-level handoff
  appended; governance part byte-identical),
  `docs/WORK-042-evidence.md` (new), and the one additive CI
  wiring step.
- No `spec/` path is touched (the frozen surfaces are
  byte-identical to origin/main — battery case_29); no
  `spec/architect/` modification (review-protocol §3); no W040
  continuation (EVID-007/EVID-008 remain OPEN and W040-owned);
  no W043+/W048 code; no commercial/payment functionality; no
  wire-schema change; no self-authorization (the WORK-042.yaml
  record is inherited byte-identically from main — ARCH-08
  verified); no self-merge.
