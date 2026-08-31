# ADCOS Commercial Roadmap — Canonical Dependency Model

**Status: CANONICAL PLANNING RECORD — reconciled by LEDGER-RECON-005 (2026-08-31).**

This is the canonical planning/guidance record for the commercial roadmap
(ACR-009) and its Work Item decomposition. It is a governance-only
reconciliation of planning surfaces: it creates **no implementation
authorization**, modifies **no frozen architecture document** (the frozen
backlog `spec/work-items.md` terminates at WORK-040 and is unchanged), and
grants **no acceptance**. Every Work Item below still requires its own
repository-local `WORK-XXX.yaml` (`status: active`) before any implementation
branch may proceed (review-protocol §3.1; ARCH-08).

**Reconciliation basis (repository-decided):** DEC-0050 (ACR-009 acceptance),
DEC-0051 (W040 decoupled as non-blocking advisory), DEC-0052 (atomic
W040→W041 handoff; W041 = ACR-005 NetworkPath/platform boundary under
WORK-041-CORE-001), DEC-0053 (single-Architect review/merge authority).

---

## 1. Canonical Work Item decomposition

| Work Item | Title | Architecture basis | Tracking issue | Status | Authorization |
|---|---|---|---|---|---|
| W040 | Pilot deployment (physical validation / evidence track) | — | #48 (in-review) | in-review, NOT accepted | superseded (WORK-040-CORRECTION-001, DEC-0052) |
| W041 | First-Class Network Path and Platform Integration | ACR-005 (DEC-0047) | #68 | **active** | **WORK-041-CORE-001 (DEC-0052)** |
| W042 | Event-Driven Platform Integration and Journal-First Recovery | ACR-006 (DEC-0048) | #69 | ready-candidate | none |
| W043 | *(retired — unassigned; see §4)* | — | — | — | — |
| W044 | Payment Provider Adapters & Settlement Gateway | ACR-009 | #88 | ready-candidate | none |
| W045 | Connectivity Eligibility, Provider Trust & Jurisdiction Policy | ACR-009 | #89 | ready-candidate | none |
| W046 | Developer Connectivity API, SDK & Webhook Platform | ACR-009 | #90 | ready-candidate | none |
| W047 | Connectivity Marketplace Discovery, Proximity & Path Selection | ACR-009 | #91 | ready-candidate | none |
| W048 | Provider Connectivity Sharing Runtime, Isolation & Quota Enforcement | ACR-009 | #92 | design-only (PR #97) | none |
| W049 | Provider & Buyer Connectivity Client Runtime (canonical) | ACR-009 | #98 | ready-candidate | none |
| W050 | Platform Connectivity Sharing Capability & Isolation Matrix | ACR-009 | #96 | ready-candidate | none |
| W051 | CommercialCore: connectivity intent, offers, reservation, lease, and transaction lifecycle | ACR-009 (DEC-0050) | #83 | ready-candidate | none |
| W052 | UsageLedger: delivered-usage metering, billable finality, and append-only reconciliation | ACR-009 | #84 | ready-candidate | none |
| W053 | EconomicAllocation: developer/provider/ADCOS revenue-share policy and external payment boundary | ACR-009 | #85 | ready-candidate | none |

## 2. Canonical dependency graph

```text
ACR-009 (accepted, DEC-0050 — architecture only; authorizes no Work Item)
   ↓
W051 CommercialCore ──────────────→ W052 UsageLedger ─→ W053 EconomicAllocation
   ↓ (interfaces consumed)                                   ↓
W044 Payment adapters            W045 Eligibility/trust     W046 Developer API
W047 Discovery

W048 Provider sharing runtime:
   hard interface dependencies — W041 NetworkPath accepted/merged
                                + W042 usage/journal accepted/merged
                                + W051 CommercialCore (commercial Lease authority) where consumed
W049 Client runtime (canonical #98):
   consumes W048 sharing-runtime, W047 discovery, W046 developer-API interfaces
W050 Platform capability/isolation matrix:
   capability model consumed BY W048/W049 — NOT an implementation vehicle for W048
```

Genuine interface dependencies (consumed → consumer):

- W041 NetworkPath → W042 (journal/platform integration consumes path lifecycle interfaces)
- W041 + W042 + W051 → W048 (provider sharing runtime composes all three)
- W051 → W052 → W053 (commercial chain)
- W051/W053 → W044 (payment adapters interface the commercial core's settlement states)
- W051/W053 + W044 → W045 (eligibility/trust consumes commercial + payment capability boundaries)
- W051/W052/W053/W044/W045 → W046 (developer API surfaces the commercial plane)
- W051/W044/W045/W046 → W047 (discovery presents paid, eligible, API-visible offers)
- W048/W047/W046 → W049 (client runtime hands off to each canonical authority)
- W050 → W048/W049 (capability declarations constrain sharing modes; advisory input, not a gate)

**W040 representation (governing rule):** W040 is the **physical validation /
evidence track** — an independent, in-review, not-accepted Work Item. Per
DEC-0051 its findings are **advisory experience input** to future commercial
authorization reviews, **NOT a hard execution prerequisite** for any Work Item
above. EVID-007 (real users/devices, PARTIAL) and EVID-008 (real 5G path,
NOT-TESTABLE) remain OPEN and W040-owned; the physical track may resume under
a future `type: evidence-continuation` authorization.

## 3. W041/W042 binding (decided by the repository)

- **W041 = First-Class Network Path and Platform Integration (ACR-005,
  DEC-0047, issue #68)** — the ACTIVE Work Item under WORK-041-CORE-001
  (DEC-0052). Its scope is `networkpath/`, `tools/networkpath_selftest.py`,
  and its handoff/evidence docs; commercial core/payment/settlement is
  explicitly out of scope of that authorization.
- **W042 = Event-Driven Platform Integration and Journal-First Recovery
  (ACR-006, DEC-0048, issue #69)** — ready-candidate contract
  `spec/architect/work-items/WORK-042.md`, unauthorized, dependent on W041
  where its interfaces are consumed.

The ACR-005/006-era contract files are **live canonical contracts**, not
superseded history.

## 4. Resequencing record (superseded commercial-era labels — history preserved)

Between 2026-08-30 and 2026-08-31 the commercial planning surface
(GitHub issues #83–#96 and the then-current `planned_work_items` pointers)
numbered the commercial chain as `W041 CommercialCore → W042 UsageLedger →
W043 EconomicAllocation`. DEC-0052 (2026-08-31) then bound **W041 to the
ACR-005 NetworkPath contract** (and the W042 event-driven/ACR-006 contract
remains live), superseding that commercial-era numbering for the first three
chain positions. This model resequences the commercial chain head to fresh,
collision-free numbers:

- CommercialCore → **W051** (issue #83, retitled)
- UsageLedger → **W052** (issue #84, retitled)
- EconomicAllocation → **W053** (issue #85, retitled)
- **W043 is retired from commercial use and left unassigned** (never reused or
  renumbered per the registry convention) so no future reader can bind the
  superseded commercial-era "W043" label to a live artifact.
- W044–W050 keep their existing issue labels (#88–#92, #98, #96); the
  dependency *order* is expressed by §2, not by the numbering.

Superseded definitions remain discoverable, verbatim:

- The original issue titles `#83 "W041 — CommercialCore…"`, `#84 "W042 —
  UsageLedger…"`, `#85 "W043 — EconomicAllocation…"` (visible in each issue's
  edit history and in the reconciliation comments posted with this change).
- `spec/roadmap/connectivity-economy.md` (PR #49, proposed ACR-004 era) — a
  THIRD, earlier numbering (`W041 Provider identity… W045 Provider
  settlement`); the PR is superseded by accepted ACR-009 and retained as
  historical proposal evidence only.
- PR #100 `governance: reconcile W041/W042 contracts…` — the prior
  W041=CommercialCore contract reconciliation; superseded by DEC-0052's
  opposite binding and by this model; awaiting Architect disposition (close).
- PR #102 `governance: W040→W041 execution handoff review` — analysis-only;
  superseded by merged PR #103; awaiting Architect disposition (close).
- `docs/WORK-048-provider-sharing-runtime-design.md` originally stated the
  W048 hard-dependency chain as `WORK-040 dispositioned → WORK-041
  accepted/merged → WORK-042 accepted/merged → W048 authorized` and used
  "W041" for both NetworkPath and commercial-Lease senses; §6 of this model
  and the in-file reconciliation note supersede those readings (the
  original text is quoted in the note).

### 4.1 W049 canonical decomposition (duplicate definition resolved)

Two overlapping W049 planning definitions existed:

- issue #95 — "Buyer Connectivity Runtime & Secure Lease Consumption"
  (buyer-side runtime: lease retrieval, path consumption, usage reporting,
  expiry enforcement);
- issue #98 — "Provider & Buyer Connectivity Client Runtime"
  (platform-neutral client/runtime boundary for BOTH provider and buyer
  modes: consent UX, capability discovery, policy presentation, secure
  handoffs to W046/W047/W048, status/events, offline/reconnect).

**Canonical W049 = issue #98** (one canonical scope covering the
client/runtime boundary for both provider and buyer modes). The buyer-mode
runtime mechanics of #95 are safely unified into the canonical scope: lease
retrieval and lifecycle presentation become client-boundary concerns;
enforcement, attachment, isolation, and metering mechanics remain delegated
to their canonical authorities (W048 runtime, W050 capabilities, W051 lease
authority, W042 usage journal) exactly as #98's scope already requires.
**#95 is the superseded definition** — retitled with a superseded marker,
left open for Architect disposition; its text remains verbatim in the issue
and in this record. Nothing is silently deleted.

### 4.2 W050 boundary statement

W050 (issue #96) is and remains the **platform capability/isolation matrix**:
a versioned capability registry and isolation-primitive declaration model
(provider and buyer roles, sharing-mode capability classes, minimum security
properties, metering/lease-enforcement capability declarations, unsupported
platform classes). It is a capability **model consumed by** W048/W049 — it is
**NOT an implementation vehicle for W048** (no runtime, no enforcement code,
no per-platform sharing implementation; those belong to W048/W049 under their
own authorizations).

## 5. Authorization state (unchanged by this record)

- Sole active authorization: **WORK-041-CORE-001** (WORK-041, DEC-0052,
  status active, baseline reconciled by LEDGER-RECON-005).
- WORK-040-CORRECTION-001: superseded (DEC-0052) — record preserved unchanged.
- W042–W053: **authorization "none"** for every item. This model authorizes
  nothing; the one-active-Work-Item rule and ARCH-08 fail-closed provenance
  are untouched.

## 6. Effect on existing planning documents

- `docs/WORK-048-provider-sharing-runtime-design.md` — reconciled by this
  change: the W040-dispositioned prerequisite link is removed (DEC-0051:
  advisory only), and its commercial-plane references ("W041 control plane",
  "W041 contract; Lease, UsageRecord", "ACR-009 / W041") are resequenced to
  the W051 CommercialCore binding; its NetworkPath (W041) and usage-journal
  (W042) references were already correct and are unchanged. See the in-file
  reconciliation note (§ "Dependency reconciliation (LEDGER-RECON-005)").
- `spec/architect/execution-state.yaml` / `spec/architect/current-state.md` /
  `spec/architect/execution-ledger.yaml` — persistent state pointers
  reconciled by this change (see LEDGER-RECON-005).
- GitHub planning issues #83–#98 — mapping comments + retitles posted with
  this reconciliation; issue texts are preserved verbatim (history is never
  rewritten).

## 7. Frozen-surface audit

No frozen architecture document is modified by this model:
`spec/architecture.md`, `spec/architecture-lock.md`, `spec/work-items.md`,
`spec/dependency-graph.md` are untouched (the frozen backlog and DAG
terminate at WORK-040; W041+ are planning-surface labels, not frozen nodes).
No ACR is required: this reconciliation changes planning/process records and
documentation only (change-control.md §8; authority-order levels 8–11), adds
no architectural semantic, and grants no acceptance. If the Architect judges
the commercial resequencing (§4) to alter architectural semantics, it must be
converted into an ACR per review-protocol §6 rather than merged as-is.
