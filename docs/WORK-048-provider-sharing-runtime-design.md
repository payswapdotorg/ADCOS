# WORK-048 — Provider Connectivity Sharing Runtime: Implementation Design

**Status: DESIGN PROPOSAL — NOT AN IMPLEMENTATION.**

**Document class:** Governance / design reconnaissance (lives under `docs/`, a
governance prefix per `tools/spec_check.py` `GOVERNANCE_PREFIXES`). This document
introduces NO implementation delta, modifies NO frozen architecture document,
and modifies NOTHING under `spec/architect/` (review-protocol §3.2).

**Tracking issue:** #92 — W048 Provider Connectivity Sharing Runtime, Isolation &
Quota Enforcement.

**Authored against base SHA:** `5da120f6e0945410a8fc9346692058ca9a8b49f3`
(current `origin/main`).

---

## 0. Authorization gate (read first)

> **W048 is NOT authorized for implementation.**

This is verified against the repository's own durable governance, not chat:

1. `spec/architect/authorizations/` contains only `WORK-040.yaml`. There is no
   `WORK-048.yaml`. Per `spec/architect/authorizations/README.md`:
   *"An authorization is the ONLY durable authority to implement"* and
   *"NO CURRENT AUTHORIZATION = IMPLEMENTATION MUST STOP."*
2. `spec/architect/execution-state.yaml` records:
   - `execution.active_work_item: WORK-040`
   - `execution.active_authorization: WORK-040-CORRECTION-001`
   - `planned_work_items` lists only WORK-041/042/043, each with
     `authorization: "none"`. WORK-048 is not listed.
3. The canonical backlog `spec/work-items.md` ends at WORK-040. WORK-048 is not
   a registered Work Item contract.
4. `ACR-009` (Commercial Connectivity Control Plane) is ACCEPTED (DEC-0050) but
   states explicitly: *"ACR-009 acceptance does not itself authorize
   implementation. Concrete commercial implementation remains subject to
   separately authorized Work Items."*
5. `spec/architect/review-protocol.md` §3.1: *"No authorization, no
   implementation."* §3.2: *"Implementation PRs must not modify
   `spec/architect/`."* §7: *"Z.ai must never merge its own PR."*
6. CI gate `ARCH-08` (provenance mode, `tools/spec_check.py --provenance`)
   fails closed on any implementation-file delta without an ACTIVE authorization
   inherited byte-identically from the base.

**Consequence:** Per the W048 task's own AUTHORIZATION clause — *"If W048 lacks
an active repository authorization: DO NOT IMPLEMENT. Perform technical
reconnaissance and produce an implementation design only"* — this document is
**technical reconnaissance + implementation design only**. It is delivered as a
docs-only governance PR. It must NOT be treated as implementation, must NOT be
merged by the author, and must NOT be promoted to a PASS of any kind.

When the Architect issues a repository-local `WORK-048.yaml` authorization
(`status: active`, exact baseline, scope, dependencies, evidence classes), the
runtime sections below are intended to drive that implementation — subject to
the architectural finding in §11, which may require an ACR before the isolation
layer can land.

---

## 1. Reconnaissance summary

### 1.1 Authority map (what already exists and must NOT be duplicated)

From `spec/architecture-lock.md` §3 (Module Ownership) and §5 (Authority
Rules), the authoritative owners W048 must compose — never recreate — are:

| Concern | Owner (frozen) | W048 relationship |
|---|---|---|
| Node identity / credentials | `/identity` (LOCK-005,006,023) | Reference only. W048 never mints identity. |
| Logical session identity | `/session` (W012; LOCK-006,021) | Reference only. A sharing session reuses a logical `session_id`; W048 does not become a session authority. |
| Path computation/selection | `/routing` (W011) | Reference only. W048 selects/configures a validated NetworkPath; it does not compute paths. |
| Secure transport mappings | `/transport` (W017) | **Composed.** The tunnel that carries buyer traffic and binds it to the leased egress is a transport profile. |
| Access/provider-specific impl | `/adapters` (W016; LOCK-016,017) | **Composed.** Platform isolation primitives (Linux netns/nftables, Android `VpnService`, iOS Network Extension) live in adapters. |
| Local service boundary | `/services` + `/edge` (W025) | **Composed.** The exposure policy (which local services, if any, the lease exposes) is a service-authority concern. |
| Policy evaluation | `/policy` (W010; deny-by-default) | Composed. Lease/quota/consent decisions route through policy. |
| Telemetry / observations | `/telemetry` (W026) | Composed. Usage observations originate as telemetry; W048 correlates, never owns. |
| Commercial control plane | ACR-009 (W051 CommercialCore contract, issue #83; `Lease`, `UsageRecord`, …) | **Referenced.** The commercial `Lease` is the lifecycle authority; W048 is a local enforcement mechanism that observes it. |
| Usage authority | ACR-006 / W042 (journal-first) | **Referenced.** W048 emits idempotent usage evidence correlated INTO W042; W048 is never the canonical usage ledger. |
| NetworkPath authority | ACR-005 / W041 (`discover→validate→activate→retire`) | **Referenced.** W048 activates/retires a path through the existing lifecycle; it creates no new path abstraction. |

### 1.2 What W041/W042 provide (and why W048 depends on them)

**W041 — NetworkPath (ACR-005).** Active under WORK-041-CORE-001 (DEC-0052);
at reconciliation time the W041 implementation itself was still pending. It
provides the `discover→validate→bind→activate→retire` lifecycle, stable
`session_id` across path changes, and the physical→platform→ADCOS evidence chain.
W048 **requires** W041 accepted/merged because every sharing session must
activate a *validated* NetworkPath and survive path loss/change through W041's
existing transition semantics (not a W048-invented one).

**W042 — Usage / Journal (ACR-006).** Ready-candidate, not execution-authorized.
Provides append-only journal, event/snapshot reconciliation, process-death
survival, and idempotent recovery. W048 **requires** W042 accepted/merged because
usage evidence must be correlated *into* W042 idempotently; W048 must not become
a second usage ledger (ACR-009 invariant 6; W048 authority boundary).

**Hard dependency chain for any future W048 implementation:**
`WORK-041 accepted/merged → WORK-042 accepted/merged → W051 CommercialCore
accepted/merged where consumed → WORK-048 authorized`. Today none of these are
satisfied, which independently confirms the design-only outcome.

**Dependency reconciliation (LEDGER-RECON-005, 2026-08-31).** This section was
reconciled against the repository's decided state. The original chain as
authored read (superseded, preserved verbatim):

> `WORK-040 dispositioned → WORK-041 accepted/merged → WORK-042
> accepted/merged → WORK-048 authorized`

Two corrections apply. First, **DEC-0051 (ACCEPTED)** decouples WORK-040: it
is the independent physical validation / evidence track whose findings are
*advisory experience input* to future W048 authorization review — not a hard
execution prerequisite, so the `WORK-040 dispositioned` link is removed.
Second, **DEC-0052 (ACCEPTED)** bound W041 to the ACR-005 NetworkPath contract
(issue #68) and left the ACR-006 event-driven/journal contract (W042, issue
#69) live, while the commercial control plane (`Lease`, `UsageRecord`,
settlement states) is resequenced to **W051 CommercialCore** (issue #83) under
the canonical model `docs/roadmap/commercial-dependency-model.md`. Throughout
this document, references to the NetworkPath authority remain **W041**
(ACR-005) and usage/journal references remain **W042** (ACR-006) — unchanged;
references that used “W041” for the *commercial Lease/control-plane* sense are
resequenced to W051 CommercialCore. No authority ownership changes; the
W048 task remains unauthorized.

### 1.3 Reusable implementation patterns observed in-repo

The codebase already establishes a consistent least-authority mediation
pattern that W048's runtime should mirror (not reinvent):

- `transport/sandbox.py` — `SandboxedTransport` mediates every call to a
  transport implementation: exceptions (incl. `BaseException`) become typed
  `TransportFailure` *values*; return shapes are contract-validated before
  entering manager state; a deterministic step budget (no wall clock) models
  hangs; least-authority `TransportContext` facade; health ladder
  HEALTHY→DEGRADED→FAILED; LOCK-023 discipline (exception *class name* only,
  never message text).
- `services/sandbox.py` — `SandboxedExecutionProvider` mirrors the same
  discipline for local-service execution: fresh immutable
  `ServiceContext`, contract-shape validation with content-derived ref
  re-derivation (tampered outcomes rejected), `cleanup_pending` made explicit
  on otherwise-successful operations.
- `conformance/harness.py` — deterministic vector/world model: one fresh world
  per vector, ordering-independent, fail-closed on unmodeled exceptions
  (`UNEXPECTED_EXCEPTION`), every result carries the authority's own stable
  result class.

W048's runtime should adopt this mediation pattern for (a) the consent/lease
enforcement boundary and (b) the isolation-enforcement adapter boundary, so
that a failing isolation primitive degrades the sharing session deterministically
and never corrupts commercial/session state.

---

## 2. The product question

> A provider has 40 GB monthly allowance, 20 GB expected personal use, 20 GB
> surplus. Can ADCOS safely expose the surplus to an authorized buyer for a
> bounded lease?

**Answer: yes, conditionally — and only if every one of the following holds.**
ADCOS can expose a *bounded portion* of real provider connectivity to an
*authorized* buyer for a *bounded lease* if and only if:

1. **The provider consents** (§4). Consent is mandatory, recorded, revocable,
   and supports emergency stop. No consent ⇒ no exposure, fail-closed.
2. **A commercial Lease exists** (ACR-009 / W051 CommercialCore). The lease is the commercial
   lifecycle authority; W048 only enforces locally against it.
3. **A validated NetworkPath exists** (ACR-005 / W041). Discovery alone is
   insufficient; the path must pass `validate→bind→probe` before activation.
4. **The surplus is bounded and reserved.** Byte quota (e.g. 20 GB), time quota
   (lease expiry), and concurrent-buyer limit are enforced *before* traffic
   flows and *throughout* the session (§5). Capacity is reserved, not
   over-committed beyond the configured limit.
5. **Buyer traffic is isolated** (§6). Traffic cannot reach the provider
   control-plane interfaces, administration services, private/local resources
   not in the lease, or unrelated local services. This is the highest-risk
   requirement and is enforced by an *explicit platform-appropriate isolation
   mechanism*, not application-level declarations alone.
6. **Usage evidence is produced and correlated** into W042 (§8),
   idempotently, with provider/session/lease/buyer/path correlation — but W048
   is not the canonical ledger.
7. **The platform can actually do it** (§7). Capability is explicitly
   `supported` / `unsupported` / `restricted` / `unknown`. An `unsupported` or
   `unknown` platform must refuse to expose connectivity (fail-closed), never
   silently degrade to an unsafe mechanism.

If any of 1–7 cannot be satisfied, the answer is **no** for that
provider/platform/lease, and the runtime must fail-closed rather than expose.

The provider must be able to define, per §4–§5:
*what* is shared (which path, which egress, which bytes), *who* can use it
(authorized buyer identity), *for how long* (time quota / expiry), *how many
bytes* (byte quota), *how many simultaneous buyers* (concurrent limit), *how to
revoke* (consent revocation / emergency stop), and *what evidence is produced*
(W042-correlated usage records).

---

## 3. Authority boundary (non-negotiable)

W048 is a **local enforcement mechanism**. It MUST NOT create a second:

```
identity authority       — /identity owns NodeID/credentials
session authority        — /session owns logical session_id
NetworkPath authority    — ACR-005/W041 owns path lifecycle
routing authority        — /routing owns path computation/selection
transport authority      — /transport owns secure transport mappings
commercial truth authority — ACR-009/W051 CommercialCore owns Lease/UsageRecord/...
usage authority          — ACR-006/W042 owns the canonical usage journal
```

Concretely, W048's runtime:

- **Reads** commercial Lease state from the W051 CommercialCore control plane (it does not
  mint, mutate, or settle leases).
- **References** a logical `session_id` from `/session` (it does not create
  session identity).
- **Activates/retires** a NetworkPath through W041's lifecycle (it does not
  invent a path abstraction).
- **Configures** a transport tunnel profile and a platform-isolation adapter
  (it does not reimplement transport or platform isolation).
- **Emits** usage evidence *into* W042 idempotently (it does not keep a
  competing ledger).

If any W048 design would require mutating commercial/session/path/transport
truth, that design is wrong and must be converted into an ACR (review-protocol
§6; architecture-lock §6).

---

## 4. Provider consent

Consent is mandatory before any connectivity is exposed. The consent object is
a **local enforcement record** (W048-owned), not a commercial authority object.

### 4.1 Consent record (design shape, not frozen schema)

```
ProviderConsent:
  consent_id            # W048-local, opaque
  provider_node_id      # /identity reference (not owned)
  lease_ref             # ACR-009 Lease reference (not owned)
  network_path_ref      # ACR-005 NetworkPath reference (not owned)
  buyer_identity_ref     # authorized buyer (identity claim, LOCK-008)
  scope:
    exposed_egress      # what is shared (egress destination set)
    byte_quota          # how many bytes
    time_quota          # for how long (expiry instant)
    max_concurrent_buyers
    exposed_local_services   # deny-by-default; empty = none
  granted_at            # deterministic instant
  state                 # granted | withdrawn | emergency_stopped
  transition_reasons[] # append-only, with instant + cause
```

### 4.2 Consent invariants

1. **No consent ⇒ no exposure.** A sharing session cannot leave `prepared`
   without a `granted` consent whose `scope` covers the lease/path/buyer.
2. **Revocation is always supported.** `withdraw(cause)` and
   `emergency_stop(cause)` are always available to the provider. Emergency
   stop is the kill-switch: it transitions the sharing session to `revoked`
   (or `closed`) immediately and tears down isolation.
3. **Consent transitions are append-only.** `transition_reasons` is an
   append-only list; historical consent is immutable (mirrors ACR-009
   invariant 6/10).
4. **Consent scope is checked at every enforcement point**, not only at grant
   time: each byte counted against `byte_quota`, each tick against
   `time_quota`, each concurrent buyer against `max_concurrent_buyers`.

### 4.3 Consent fail-closed behavior

- If the consent record is missing, malformed, expired, or withdrawn, the
  enforcement boundary refuses to admit buyer traffic
  (`CONSENT_REQUIRED` / `CONSENT_WITHDRAWN`), and any active session is moved
  to `revoked`.
- If the lease referenced by the consent is no longer active (W051 CommercialCore authority),
  the consent is treated as withdrawn-by-external-state and the session is
  revoked with reason `LEASE_NO_LONGER_ACTIVE`.

---

## 5. Lease / quota enforcement

W048 enforces — locally — against the commercial Lease owned by ACR-009/W051 CommercialCore.
The Lease is the authority; W048 is the enforcement mechanism.

### 5.1 Enforced dimensions

```
active lease              — must be ACTIVE in the W051 CommercialCore control plane
expiry                    — time quota; no traffic after expiry
byte quota                — no traffic after bytes consumed
time quota                — no traffic after duration
concurrent buyer limit    — no new buyer beyond the limit
capacity reservation      — reserved bytes are not over-committed
emergency stop            — provider kill-switch (§4.2)
revocation                — consent withdrawal / lease termination
```

### 5.2 Enforcement invariants

1. **No traffic continues indefinitely after expiry/revocation.** The
   enforcement boundary is the gate between buyer traffic and the
   NetworkPath; once `expiry` or `byte_quota` is reached, or consent is
   withdrawn/emergency-stopped, the boundary drops buyer traffic
   deterministically. This is enforced at the *isolation primitive* level
   (§6), not only at the application level — the tunnel/namespace is torn down.
2. **Historical usage remains immutable.** Quota counters are append-only
   accounting; reaching/exceeding a quota records the fact without rewriting
   prior usage (ACR-009 invariant 6/10; ACR-006 journal discipline).
3. **Over-reservation is rejected.** A lease whose `byte_quota` + already
   reserved bytes would exceed the provider's declared surplus capacity is
   rejected at `prepared` (`OVER_RESERVATION`), never silently admitted.
4. **Concurrent buyer limit is enforced at admission.** A buyer beyond
   `max_concurrent_buyers` is refused (`CONCURRENT_LIMIT`); an existing buyer
   is not displaced to make room.
5. **Quota checks are fail-closed.** If the quota counter cannot be read
   (e.g. journal unavailable), buyer traffic is refused
   (`QUOTA_UNVERIFIABLE`), never admitted on a best-effort basis.

### 5.3 Relationship to the commercial Lease

- W048 **reads** `Lease.state`, `Lease.expiry`, `Lease.byte_quota`,
  `Lease.buyer`, `Lease.pricing_policy_version` from W051 CommercialCore.
- W048 **never** mutates Lease state. If W048 detects lease expiry/quota
  exhaustion, it (a) revokes the sharing session locally and (b) emits a usage
  evidence event into W042 that the W051 CommercialCore control plane may
  observe to advance the commercial lifecycle (e.g. `DELIVERY_COMPLETED` /
  `BILLABLE_FINAL`). W051 CommercialCore remains the commercial lifecycle
  authority.

---

## 6. Isolation (highest-risk section)

This is the section that determines whether W048 can be implemented under the
current architecture or requires a new ACR. The honest architectural finding is
in §11; this section states the *requirement* and the *candidate mechanisms*.

### 6.1 The requirement (verbatim from the task)

Buyer traffic must NOT reach:
- provider control-plane interfaces;
- provider administration services;
- private/local resources not included in the lease;
- unrelated local services.

Constraints:
- Do NOT rely only on application-level declarations where OS/network isolation
  is required.
- Use an EXPLICIT platform-appropriate isolation mechanism.
- Do NOT introduce arbitrary packet interception / plaintext inspection without
  SEPARATE authorization.

### 6.2 Candidate isolation mechanisms (platform-appropriate)

The runtime MUST select a mechanism per platform and record it in the
capability matrix (§7). Candidate mechanisms, mapped to existing module
ownership:

| Platform | Mechanism | Owner module | Notes |
|---|---|---|---|
| Linux | network namespace + nftables egress allow-list + veth/tunnel to leased path | `/adapters` (platform impl) + `/transport` (tunnel) | namespaces give OS-level containment; nftables denies local-service reach by default. |
| Linux (alt) | VRF / policy routing table scoped to the tunnel | `/adapters` + `/transport` | lighter-weight than netns; sufficient when a separate routing table + firewall deny-list is enforceable. |
| Android | `VpnService` per-app tunnel routing buyer traffic; exclude provider/admin packages | `/adapters` (mobile) | OS grants the VPN a restricted routing scope; platform enforces per-app. |
| iOS | Network Extension (packet tunnel provider) with included-routes limited to the lease | `/adapters` (mobile) | OS-enforced; platform capabilities vary. |
| Router/appliance | per-tenant VRF / firewall zone | `/adapters` (appliance) | depends on platform (OpenWrt, etc.). |

In ALL cases the mechanism must be **OS/network-level**, not a pure
application declaration. A tunnel (`/transport`) carries buyer traffic to the
leased egress; a platform primitive (`/adapters`) constrains the buyer's
routing/firewall scope so it cannot reach provider control-plane/local
interfaces; a service-exposure policy (`/services`) defines the (deny-by-default)
set of local services reachable through the lease.

### 6.3 What W048 does NOT do

- W048 does NOT perform arbitrary packet interception or plaintext payload
  inspection. Byte-counting (for quota) operates on frame/byte counts at the
  tunnel boundary, not on payload content. Any deeper inspection requires
  separate authorization (out of scope for W048).
- W048 does NOT become a transport, routing, or service authority. It
  *configures* existing transport/adapter/service primitives; it does not
  reimplement them.
- W048 does NOT assume all platforms can provide the same mechanism. The
  capability matrix (§7) makes support explicit; `unsupported`/`unknown`
  platforms refuse to expose connectivity.

### 6.4 Isolation fail-closed behavior

- If the isolation primitive cannot be established (e.g. netns creation fails,
  VPN permission denied), the sharing session cannot leave `prepared`
  (`ISOLATION_UNAVAILABLE`) and no buyer traffic is admitted.
- If the isolation primitive is lost mid-session (e.g. netns destroyed, VPN
  revoked by the OS), the session transitions to `revoked` with reason
  `ISOLATION_LOST` and usage evidence is emitted.
- If an isolation-breach attempt is detected (buyer traffic observed reaching
  a denied local interface), the session is emergency-stopped and the event is
  recorded as security evidence (LOCK-022 zero-trust; LOCK-023 no secret
  leakage in diagnostics).

---

## 7. Platform capability matrix

W048 explicitly represents capability per platform; it never assumes uniform
support.

```
CapabilityState ∈ { supported, unsupported, restricted, unknown }
```

| Platform | Sharing capability | Mechanism | Rationale |
|---|---|---|---|
| Linux (agent) | `supported` (designed) | netns + nftables + tunnel | OS provides network namespaces; deterministic containment. |
| Android | `restricted` (designed) | VpnService per-app tunnel | OS-enforced; background-lifecycle limits (W042); per-app routing only. |
| iOS | `restricted` (designed) | Network Extension | OS-enforced; capability depends on entitlement availability. |
| Router/appliance | `unknown` (default) | per-platform VRF/zone | must be proven per appliance profile (W036). |
| Untested platform | `unknown` (default) | — | fail-closed: no exposure until proven. |

Invariants:

1. `unknown` and `unsupported` platforms MUST refuse to expose connectivity
   (fail-closed). They never silently degrade to a weaker mechanism.
2. `restricted` platforms expose connectivity only within the documented
   restriction set (e.g. Android background-lifecycle caveats from W042).
3. The matrix is evidence-grounded: a `supported` claim requires
   software-conformance evidence; a *physical* containment claim requires
   physical evidence (review-protocol §2; sandbox evidence ≠ physical
   evidence, §10).
4. The matrix is W048-local data, not architecture authority. Adding a
   platform does not change frozen architecture (LOCK-025: Linux-first ≠
   Linux-dependent).

---

## 8. Usage evidence (correlated into W042, not owned)

W048 emits usage evidence that is **correlated into** the W042 canonical
journal; W048 is NEVER the canonical usage ledger (ACR-009 invariant 6;
W048 authority boundary).

### 8.1 Evidence correlation keys

Each usage evidence event carries:

```
provider_node_id          # /identity reference
sharing_session_id         # W048-local session correlation id
commercial_lease_ref       # ACR-009 Lease reference
buyer_identity_ref         # authorized buyer (claim, LOCK-008)
network_path_ref           # ACR-005 NetworkPath reference
session_id                 # /session logical session id (path correlation)
transport_id               # /transport tunnel carrying the traffic
observed_bytes             # counted at the tunnel boundary
observed_instant            # deterministic instant
isolation_mechanism        # from the capability matrix (§7)
evidence_class             # SOFTWARE | PHYSICAL | OPERATIONAL
correlation_id              # idempotency key (deterministic from content)
```

### 8.2 Correlation invariants

1. **Idempotent.** A duplicate usage event (same `correlation_id`) is
   reconciled, not double-counted (ACR-006 event/snapshot reconciliation;
   ACR-009 invariant 6).
2. **Append-only.** Usage events are never rewritten; corrections are
   compensating events (ACR-009 invariant 7).
3. **Correlated, not authoritative.** W048's evidence references W042 journal
   entries; it does not become the journal. If W042 is unavailable, W048
   buffers evidence locally and reconciles on recovery (W042 journal-first
   recovery) — but never silently drops evidence.
4. **Evidence class discipline.** Sandbox-derived evidence is SOFTWARE; a
   physical containment claim is PHYSICAL and remains OPEN until physically
   proven (review-protocol §2; §10 below). Software PASS never becomes physical
   PASS.

---

## 9. Sharing session lifecycle (deterministic)

```
prepared
  → authorized
    → active
      → paused
      → expired
      → revoked
      → closed
```

Every transition carries an explicit `transition_reason`. Deterministic
state machine:

| From | To | Reason (examples) | Authority consulted |
|---|---|---|---|
| (init) | `prepared` | `SESSION_PREPARED` | local |
| `prepared` | `authorized` | `CONSENT_GRANTED` + `LEASE_ACTIVE` + `PATH_VALIDATED` | consent §4, W051 lease, W041 path |
| `prepared` | (rejected) | `CONSENT_REQUIRED` / `OVER_RESERVATION` / `ISOLATION_UNAVAILABLE` / `CAPABILITY_UNSUPPORTED` | consent §4, §5, §6, §7 |
| `authorized` | `active` | `ISOLATION_ESTABLISHED` + `PATH_ACTIVATED` | W041 path activate, §6 |
| `active` | `paused` | `PROVIDER_PAUSE` / `QUOTA_PAUSE` | consent §4, §5 |
| `paused` | `active` | `PROVIDER_RESUME` (re-checks consent/lease/quota) | consent §4, §5 |
| `active`/`paused` | `expired` | `TIME_QUOTA_REACHED` / `BYTE_QUOTA_REACHED` / `LEASE_EXPIRED` | §5 |
| any | `revoked` | `CONSENT_WITHDRAWN` / `EMERGENCY_STOP` / `LEASE_NO_LONGER_ACTIVE` / `ISOLATION_LOST` / `ISOLATION_BREACH` | §4, §5, §6 |
| `active`/`paused`/`expired`/`revoked` | `closed` | `SESSION_CLOSED` (final teardown; isolation torn down; final usage emitted) | local |

Invariants:

1. **No transition skips consent.** `prepared→authorized` requires consent;
   any later re-entry to `active` from `paused` re-checks consent, lease, and
   quota.
2. **No traffic after `expired`/`revoked`.** The isolation primitive is torn
   down on entry to `expired`/`revoked`; only `closed` remains, which is
   terminal.
3. **`closed` is terminal and immutable.** Historical usage (emitted up to
   `closed`) remains immutable (§5.2, §8.2).
4. **Path loss/change routes through W041.** If the active NetworkPath is lost
   or changes, the event is handled by W041's path lifecycle
   (`activate→retire`, candidate re-validation). W048 observes the path
   transition; if no validated replacement path exists, the session moves to
   `revoked` with reason `PATH_LOST` (or `paused` if a candidate is being
   validated, per provider policy). W048 does NOT invent a parallel path
   lifecycle.

---

## 10. Sandbox rule (evidence honesty)

Deterministic sandbox networking may be used for the INITIAL implementation
and the deterministic test battery. But:

```
sandbox evidence ≠ physical evidence
```

- A sandbox netns/tunnel proves the *mechanism* and the *deterministic
  enforcement*; it does NOT prove physical containment on a real device/network
  (review-protocol §2; ACR-005 three-truth-layers: physical ≠ platform ≠ ADCOS).
- Software PASS (sandbox) never becomes physical PASS. A physical containment
  claim (e.g. "buyer traffic cannot reach the provider's 5G control-plane on a
  real Android device") requires PHYSICAL evidence and remains OPEN until then
  (evidence-obligations registry).
- Any W048 physical-evidence obligation must be registered in
  `spec/architect/evidence-obligations.yaml` by the Architect (W048 must not
  self-register or self-close obligations — review-protocol §3.2).

---

## 11. Architectural finding (the decision the Architect must make)

> **If safe sharing requires an architectural change beyond ACR-009/ACR-005,
> STOP and report that requirement instead of bypassing it.**

The commercial / consent / lease-quota / session-lifecycle / usage-correlation
layers of W048 fit cleanly within ACR-009 (commercial control plane) + ACR-006
(usage/journal) + existing `/session`, `/routing`, `/policy`, `/telemetry`
authority. **No new ACR is required for those layers.**

The **isolation layer** (§6) is the genuine architectural question. The current
architecture:

- ACR-005 made `NetworkPath` first-class: a technology-neutral *conceptual
  record* of an available/active path, with `discover→validate→bind→activate→
  retire`. But ACR-005 did **not** make *"traffic containment to a bounded
  path"* first-class. NetworkPath describes *what path is selected*; there is
  no first-class contract for *"traffic is constrained to that path and cannot
  escape to local resources."*
- The *mechanisms* for containment exist across three module owners:
  `/transport` (tunnels), `/adapters` (platform netns/VRF/VpnService), and
  `/services` (local-service exposure policy). But there is **no single frozen
  contract** that ties them into one auditable containment object.

This presents two architecturally sound options. **The Architect must choose;
W048 must not silently pick one.**

### Option A — Composition (no new ACR)

W048's runtime composes `/transport` + `/adapters` + `/services` directly:
activate a tunnel profile, configure a platform-isolation adapter, apply a
deny-by-default service-exposure policy. The "containment contract" is
implicit — spread across three modules' interaction, verified by the W048 test
battery exercising their combined behavior.

- **Pro:** no ACR needed; reuses existing authority; fastest path once W048 is
  authorized.
- **Con:** the highest-risk property (isolation) is an *emergent* property of
  three modules' interaction, not a single auditable object. A reviewer must
  verify containment across transport+adapter+service jointly; the
  "isolation-breach / local-service-reachability" tests verify an interaction,
  which is harder to keep deterministic and replay-safe than a single
  contract.

### Option B — New ACR-010 "Traffic Containment Boundary" (recommended if the
Architect judges isolation risk warrants a first-class contract)

Introduce a first-class `ContainmentBoundary` concept (analogous to
NetworkPath): a single frozen contract, owned by one authority (proposed:
`/transport` or a new `/containment` module), that references a NetworkPath +
an allowed-egress set + a deny-by-default local-service policy + the
platform mechanism. The sharing runtime activates/retires one
`ContainmentBoundary` per session; isolation becomes a single auditable
object with its own `discover→validate→activate→retire`-style lifecycle.

- **Pro:** the highest-risk property gets a single first-class, auditable
  contract — directly matching the precedent ACR-005 set for NetworkPath.
  Isolation-breach tests verify one contract, not a three-way interaction.
  Reviewers and future platforms get one object to reason about.
- **Con:** requires ACR acceptance (the full §3 change-control process) BEFORE
  W048's isolation layer can land. W048's commercial/consent/lease/quota layers
  could proceed under Option A while ACR-010 is evaluated, with the isolation
  layer deferred — but that splits W048 and must be explicitly authorized.

### Recommendation (for the Architect)

I recommend **Option B** if the Architect agrees that isolation — explicitly
flagged by the task as "the highest-risk section" demanding "an explicit
platform-appropriate isolation mechanism" (not an implicit composition) —
deserves the same first-class treatment ACR-005 gave NetworkPath. The
enforcement dual of NetworkPath ("traffic is constrained to the selected
path") is arguably as architecturally significant as the selection itself.

I recommend **Option A** only if the Architect judges that
`/transport` + `/adapters` + `/services` already constitute sufficient
authority and that a three-way composition is reviewable to the standard the
task demands.

**Either way, this design does not bypass the architecture.** It surfaces the
decision. If the Architect selects Option B, the W048 implementation PR (when
eventually authorized) must be scoped to the non-isolation layers, with the
isolation layer blocked on ACR-010 acceptance.

---

## 12. Test battery design (deterministic)

When W048 is authorized, the test battery must be deterministic
(one fresh world per vector, ordering-independent, fail-closed on unmodeled
exceptions — mirroring `conformance/harness.py`). The following scenarios are
REQUIRED; each maps to a frozen vector with an explicit expected outcome and
reason class.

### 12.1 Consent & authorization
1. `consent_required` — `prepared→authorized` without consent ⇒ NONCONFORMANT,
   `CONSENT_REQUIRED`; no traffic admitted.
2. `consent_granted_authorizes` — with consent + active lease + validated path
   ⇒ `authorized`; isolation proceeds.
3. `consent_revoked_stops_session` — withdrawal mid-session ⇒ `revoked`,
   reason `CONSENT_WITHDRAWN`; traffic dropped.

### 12.2 Lease & quota
4. `active_lease_required` — lease not ACTIVE in W051 CommercialCore ⇒ `prepared` rejected,
   `LEASE_NOT_ACTIVE`.
5. `lease_expiry_revokes` — `time_quota` reached ⇒ `expired`,
   `TIME_QUOTA_REACHED`; isolation torn down.
6. `byte_quota_revokes` — `byte_quota` consumed ⇒ `expired`,
   `BYTE_QUOTA_REACHED`; further traffic refused.
7. `concurrent_buyer_limit` — buyer beyond `max_concurrent_buyers` ⇒
   `CONCURRENT_LIMIT`; existing buyer unaffected.
8. `over_reservation_rejected` — reservation exceeds declared surplus ⇒
   `OVER_RESERVATION` at `prepared`.
9. `revocation_terminates` — emergency stop ⇒ `revoked`,
   `EMERGENCY_STOP`; isolation torn down; final usage emitted.

### 12.3 Isolation enforcement (must PROVE enforcement, not just declare it)
10. `isolation_breach_to_control_plane` — buyer traffic attempts provider
    control-plane interface ⇒ DENIED at isolation primitive; session
    emergency-stopped; `ISOLATION_BREACH` recorded.
11. `local_service_reachability` — buyer traffic attempts a local service not
    in `exposed_local_services` ⇒ DENIED (deny-by-default).
12. `unrelated_network_access` — buyer traffic attempts an unrelated local
    network/Subnet ⇒ DENIED.
13. `isolation_unavailable_fail_closed` — isolation primitive cannot be
    established ⇒ session cannot leave `prepared`, `ISOLATION_UNAVAILABLE`.
14. `isolation_lost_mid_session` — isolation primitive lost mid-session ⇒
    `revoked`, `ISOLATION_LOST`; usage emitted.

These tests must demonstrate enforcement at the OS/network primitive level
(netns/nftables/VRF/VpnService), not only at the application level — i.e. they
must show that traffic is *blocked by the platform mechanism*, not merely that
the application chose not to send it.

### 12.4 NetworkPath lifecycle
15. `path_loss` — active NetworkPath lost (W041 retire) ⇒ session `revoked`
    (`PATH_LOST`) or `paused` (candidate validating) per policy; no
    W048-invented path transition.
16. `path_change` — validated candidate path replaces active (W041
    activate/retire) ⇒ `session_id` stable; sharing session continues on new
    path; usage correlation preserved.
17. `candidate_validation` — unvalidated candidate does NOT become active ⇒
    `prepared`/`paused` until validation passes (ACR-005 "discovering a path
    does not make it active").

### 12.5 Usage correlation
18. `usage_correlation_idempotent` — duplicate usage event (same
    `correlation_id`) ⇒ reconciled, not double-counted.
19. `usage_correlated_to_w042` — evidence references W042 journal entry; W048
    is not the canonical ledger (W042 authority unchanged).

### 12.6 Restart / shutdown / fail-closed
20. `restart_preserves_durable_state` — process restart reconstructs
    session/consent/quota state from journal (W042); active sessions resume
    enforcement; revoked sessions stay revoked.
21. `shutdown_tears_down_isolation` — clean shutdown tears down isolation
    primitives; no buyer traffic leaks past shutdown.
22. `fail_closed_on_unverifiable_quota` — quota counter unverifiable ⇒
    traffic refused (`QUOTA_UNVERIFIABLE`), never admitted best-effort.
23. `fail_closed_on_capability_unknown` — `unknown`/`unsupported` platform ⇒
    no exposure (`CAPABILITY_UNSUPPORTED`).

### 12.7 Determinism / replay
24. `deterministic_replay` — same inputs ⇒ same session state transitions,
    same usage evidence, same isolation decisions, across processes
    (no wall-clock dependence; mirrors `transport/sandbox.py` step-budget
    discipline).

### 12.8 Boundary audits
- `import_audit` — W048 runtime imports no provider SDKs, no 3GPP RAN/CN
  types, no Android/iOS SDKs into core (LOCK-016/017; architecture-lock §4).
  Platform isolation primitives live in `/adapters`.
- `authority_duplication_audit` — W048 introduces no second identity/session/
  path/routing/transport/commercial/usage authority (grep/static analysis
  against the authority map in §1.1).

### Evidence-class honesty for the battery
- All 24 vectors above are SOFTWARE-class conformance vectors. They prove the
  *mechanism* and *deterministic enforcement* in the sandbox.
- They do NOT prove physical containment on real hardware. Physical
  containment evidence (e.g. "buyer traffic cannot reach a real provider 5G
  control-plane on a physical Android device") is a separate PHYSICAL
  obligation that must be registered by the Architect and remains OPEN until
  physically proven (§10).

---

## 13. Delivery metadata

| Field | Value |
|---|---|
| Work Item | WORK-048 (Provider Connectivity Sharing Runtime) |
| Tracking issue | #92 |
| Authorization status | **NOT AUTHORIZED** — no `WORK-048.yaml` in `spec/architect/authorizations/`; not in `planned_work_items`; not in canonical backlog. ACR-009 acceptance does not authorize implementation. |
| Base SHA | `5da120f6e0945410a8fc9346692058ca9a8b49f3` (origin/main) |
| Implementation SHA | N/A — design-only deliverable, no implementation delta. |
| Branch | `work-048/provider-sharing-runtime-design` |
| Isolation mechanism (proposed) | Platform-appropriate: Linux netns+nftables+tunnel; Android VpnService; iOS Network Extension; appliance VRF/zone. Owned by `/transport` + `/adapters` + `/services`. |
| Capability matrix | Linux=supported(designed); Android/iOS=restricted(designed); appliance=unknown(default); untested=unknown(default). See §7. |
| Tests | 24 deterministic conformance vectors designed (§12); not implemented (no authorization). SOFTWARE-class only; physical containment remains a separate OPEN obligation. |
| CI | docs-only governance PR; `docs/` is a `GOVERNANCE_PREFIX` so ARCH-08 provenance gate does not require a W048 authorization. `tools/spec_check.py` passes on base. |
| Known unsupported platforms | Any platform without a determinable OS/network isolation primitive (e.g. a platform exposing only an application-level API with no namespace/VRF/VPN scope) ⇒ `unsupported`, fail-closed, no exposure. |
| Architectural findings | §11: isolation layer presents a genuine Option A (composition, no ACR) vs Option B (new ACR-010 "Traffic Containment Boundary") decision. Recommended Option B if the Architect judges isolation risk warrants a first-class contract. W048 must not bypass this decision. |
| Hard dependency chain | W041 accepted/merged → W042 accepted/merged → W051 CommercialCore accepted/merged where consumed → W048 authorized. None satisfied today. (W040: advisory only per DEC-0051; original chain preserved in §1.2's reconciliation note.) |
| Self-merge | Prohibited (review-protocol §7). The Architect merges. |

---

## 14. Acceptance lens (restated)

> Can a provider expose a bounded portion of their real connectivity to an
> authorized buyer while keeping control-plane/local resources isolated,
> enforcing the commercial lease, and producing trustworthy usage evidence?

**Conditional yes, per §2** — provided consent, lease, validated path,
bounded quota, explicit isolation, W042-correlated usage, and a `supported`
platform capability all hold. The runtime described here is the local
enforcement mechanism; the commercial/path/usage authorities remain with
W041 (NetworkPath, ACR-005) / W042 (usage journal, ACR-006) / W051
CommercialCore (ACR-009) per the canonical dependency model.

**The one open architectural question** is whether the isolation layer should
be a composed property (Option A) or a first-class `ContainmentBoundary`
authority (Option B / ACR-010). This design surfaces that question rather than
bypassing it. Until the Architect resolves it AND issues a W048 authorization,
**no implementation may proceed**.
