# WORK-038 — Future IMT / 6G adapter profile: implementation handoff

**Branch:** `work-038-future-imt-6g` (anchored on `main@cebe9f9`)
**Architect handoff:** `spec/prompts/WORK-038.md` (commit `0be736e`, byte-untouched)
**Package:** `imt/` (8 modules, 41 frozen exports)
**Battery:** `tools/imt_selftest.py` (34 cases)
**Status:** delivered for Architect review; not self-merged.

## What was built

A synthetic future-profile conformance layer proving the frozen
acceptance criteria over the ACCEPTED contracts only:

| Criterion (frozen) | Where it is proven |
|---|---|
| New profile identifier added **without a core schema change** | The profile uses the registry's own RESERVED `access.3gpp.nr.imt2030` path (reserved by WORK-002, status `reserved`, never activated). The registry file is digest-pinned before/after every run (`imt/scenario.py:registry_file_digest`); the battery additionally proves a hypothetical future registration is additive in a TEMP tree, never committed. |
| **Capabilities are additive** | Capability references are carried as DATA by reference (one KNOWN core + one profile-scoped UNKNOWN_BUT_WELL_FORMED). The W005 authority's own open-world rule is exercised: a REQUIRED unknown capability fails closed with `unknown-required-capability` EVEN WHEN the peer advertises the same id; an OPTIONAL one is "safely ignored (preserved, not coerced)" (`imt/coexistence.py:future_capability_negotiation`). |
| **Routing/session/resource/policy layers unchanged** | (a) Structural: `git diff origin/main HEAD` over the 14 core dirs is empty (battery case_33 + core-purity audit over 102 modules). (b) Runtime: the synthetic scenario digest-proves all four layers' canonical bytes byte-identical for the same fixed inputs before and after the future adapter was registered and fully exercised (`CoreEquivalenceRecord`, covered by the run digest). |
| **Synthetic future-profile conformance test** | `imt/scenario.py:run_future_profile_conformance` — 16 journaled decisions: validate → classify → register (DATA) → open → capabilities → observe → allocate → release → bind a REAL established WORK-012 session (read-only; store canonical bytes digest-proven unchanged across the bind) → unbind → health → close → unknown-id preservation → registry pinning → core equivalence → verified. Deterministic digest, TRUE replay verification. |

## Composition surfaces (all accepted, all reused as-is)

- **W016 Adapter SDK/runtime** — `AdapterRuntime.register` (the technology enters as DATA), the nine-operation contract through the real sandbox, `AdapterContext` least-authority facade, `SandboxedAdapter` budget/exception isolation.
- **W002 access-profile registry** — read-only classification (`classify_access_technology_id`), the reserved id, the open-world unknown path (`access.3gpp.future.unknown`, the architecture §8 example).
- **W005 capability classification/negotiation** — delegated verdicts only.
- **W029 compatibility/upgrade contracts** — `envelope_version_disposition` (the future profile adds nothing at the protocol-version line), `negotiate_protocol_profile` (mixed-version coexistence unchanged; major mismatch still fails closed).
- **W032 conformance suite** — the `EvidenceClass` vocabulary (reused as DATA) and the `conformance/world.py` fixture-world composition pattern.
- **W033 Linux reference agent** — the `agent/bridge.py` SDK-bridge pattern (the future adapter imports ONLY `AdapterContract` + `AdapterContext`) and the `AdapterRuntime(session_store=...)` wiring seam.

## Boundaries held

- No core schema change; no registry mutation; no status flip of the
  reserved entry (activation is a standards-body act, not ours).
- No vendor SDK, radio/PHY implementation type, or platform API
  (battery case_28 token audit + import discipline).
- No second authority: fixture composition of
  `SessionStore`/`RoutingEngine`/`ResourceStore` in `scenario.py`
  only (the W032 conformance-world pattern); no other authority
  constructor anywhere in `imt/`.
- No W039+ work; no modifications to frozen `spec/`; unknown/future
  identifiers never silently gain authority.
- Evidence classes: A/B closed in-repo; **C NOT APPLICABLE** (the
  handoff's own class list) — the anti-fabrication guard
  (`assert_no_real_world_claim`, `classify_future_evidence`) refuses
  ANY class-C claim and ANY operator-attached gate outcome: there is
  no closure path at all for the synthetic work item.

## Verification

- `tools/imt_selftest.py`: 34/34 (vocabularies, records, scenario,
  negatives, coexistence matrix, budget model, replay, structural
  audits, frozen surfaces).
- Determinism: fresh-run digest stable; invariant across
  `PYTHONHASHSEED=1/99/31337`.
- CI: one additive step after the W037 interop step (work-item
  order); all 40 tools wired.
- DAG-cited narrowing amendments: agent case_40, edge case_46/47,
  mobile case_43/44, appliance case_40/41 (additive-only workflow
  form for the appliance step, the W033→W035 precedent), oran
  case_34/35/36.
