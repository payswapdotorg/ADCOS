# ADCOS Management API family (WORK-030)

Management, configuration, audit, and operational control APIs over
the five declared dependency authorities, so ADCOS can be operated as
a real network platform (spec/architecture.md 5.6 — the Management &
Observability plane; section 22 — the management surface expresses
intent, not internal implementation details; section 19 — role/
capability based authorization and audit evidence for privileged
operations).

## Authority boundaries (the layering contract)

The family is a **composition root and facade — never a new
authority**:

- **Policy truth stays WORK-010.** Every privileged operation is
  authorized by a FRESH genuine `PolicyEngine` evaluation over the
  injected `PolicyStore`'s live applicable sets, evaluated INSIDE the
  API call. No API method accepts a caller-supplied `PolicyDecision`
  (or route decision, or any authority-minted object) as
  authorization material — there is no injection surface to
  duck-type, and a complete-content digest is never mistaken for
  authority provenance (the PR #31 review lesson, applied at birth).
- **Route computation stays WORK-011.** `create_session` passes the
  request's routing snapshot materials (topology graph, resource
  store, link metrics) THROUGH to a genuine `RoutingEngine`
  evaluation under the freshly evaluated policy decision — the
  management layer never interprets routing inputs, never recomputes,
  repairs, or replaces a route (WORK-012's rule).
- **Session state stays WORK-012.** Creation, transition, suspend,
  and terminate are the session authority's: the management layer
  delegates to `SessionStore` and maps its verdicts; the store's
  creation-contract verification and frozen transition table are the
  gate.
- **Federation state stays WORK-015.** The four frozen policy-gated
  federation operations (`federation.join`, `federation.accept-peer`,
  `federation.resource-export`, `federation.resource-import`) flow
  through the genuine `FederationStore` (and, where a relationship
  exists, the policy context is built by WORK-015's own thin policy
  consumer `evaluate_federation_operation`). Domain registration and
  direct protocol-level exchange handling remain the federation
  authority's own deployment-time surfaces — the management plane
  exposes exactly the frozen policy-controlled operation set.
- **Observations stay WORK-026.** Telemetry queries delegate to
  `TelemetryStore.query_observations` (the privacy fence — scope
  required, restricted scopes need purpose, above-scope observations
  filtered never errored — stays entirely with the telemetry
  authority); topology promotion is the born-bound composition-root
  flow: the descriptor declares the exact (observation, subject kind,
  subject ref) scope and privacy disclosure authorization up front,
  the engine derives the binding, and the telemetry authority
  verifies the binding equals the RECORDED observation, freshness,
  and the privacy boundary.
- **Identity stays WORK-004.** Operator references are opaque strings
  resolved by exact match; canonical NodeID enforcement for
  privileged actions happens inside the WORK-010 evaluation context
  (fail-closed `INVALID_SUBJECT`), so management is never a second
  identity authority.
- **RBAC and audit are the management plane's OWN state** (spec/
  architecture-lock.md section 3: `/management` owns lifecycle/
  control APIs): the role-assignment log and the audit ledger are
  closure-owned append-only authorities (the accepted WORK-027
  discipline — immutable tuple history in closure cells, no instance
  attribute holds the ledger, no mutation/removal API exists).

## The four-step flow (every operation)

```text
operator request
  -> [1] RBAC gate      active role assignments must grant the
                        operation's capability (deny-by-default; P6)
  -> [2] policy gate    privileged actions only: fresh genuine
                        WORK-010 evaluation; explicit ALLOW required
                        (deny-by-default)
  -> [3] delegation     the owning authority's genuine public API
                        executes; management never overrides an
                        authority verdict
  -> [4] audit append   exactly one tamper-evident record per call —
                        allowed OR denied (P11)
```

## Two-key authorization

RBAC decides whether THIS operator may even request the operation (a
capability, granted by an active role assignment); WORK-010 policy
decides whether the privileged ACTION is permitted. **Neither key
alone ever suffices**: an operator holding the capability without an
explicit policy ALLOW is denied (`management.policy-denied`), and a
policy ALLOW for a subject without the capability is denied at the
RBAC gate (`management.rbac-denied`). Capabilities are READ/WRITE
separated (least authority); policy operations are the frozen
WORK-010 vocabulary.

Cross-set aggregation (documented, conservative, deterministic): the
store's live applicable sets are evaluated in snapshot order; the
operation is authorized iff at least one evaluation explicitly ALLOWS
and NO evaluation explicitly denies or fails closed. A set that is
merely SILENT about the operation (`default-deny`, `missing-fact`,
`policy-expired`, `policy-not-yet-valid`) grants nothing and does not
veto another set's explicit allow. Management performs no rule
interpretation, precedence invention, or conflict resolution — those
are the engine's job inside one set; with a single applicable set
(the common deployment) the aggregation reduces exactly to that set's
own verdict.

## Roles (DATA; additive; never identities)

Roles are named capability bundles (`RoleDefinition`), granted and
revoked through an append-only event log. Effective capabilities are
the UNION across active assignments at an injected instant. A role is
never an identity (spec/architecture.md section 4): role ids are
structurally disjoint from the NodeID grammar (no colons, no
`adcos:` prefix family). Initial assignments are constructor-injected
deployment configuration; every later mutation flows through the
management API behind the policy-gated `management.role-assign`
operation (the deliberate WORK-030 policy vocabulary extension, the
WORK-026 amendment precedent — deny-by-default like every privileged
operation).

## Audit (immutable + tamper-evident)

Every API call produces exactly one `AuditRecord`. Tamper evidence is
a sha256 hash chain: `record_id_n = sha256(record_id_{n-1} + "|" +
canonical(content_n))` — every record covers its own content AND the
entire prefix chain. `verify_chain` recomputes mechanically: in-place
field mutation, deletion, reordering, and forged insertion all break
at an identifiable sequence. The ledger is immutable by construction
(append-only; no mutation/removal API; closure-owned history).
`chain_head()` is the value deployments pin/notarize externally
(evidence retention). Honest boundary: in-place tampering is detected
mechanically; a wholesale ledger replacement that also controls every
externally pinned head is outside what an in-repo ledger can prove —
external notarization exists for exactly that. Records carry
deterministic diagnostics only, never secrets (section 20).

## File map

- `errors.py` — frozen `ManagementReasonCode` vocabulary +
  `ManagementError`.
- `model.py` — frozen `ManagementCapability` / `ManagementOperation` /
  `AuditOutcome` / `RoleEventKind` vocabularies; `OperationSpec`
  table (the structural privileged classification);
  `RoleDefinition` / `RoleAssignmentEvent` / `AuditRecord` /
  `ManagementResult` (content-identified, validated at construction).
- `rbac.py` — `RoleAssignmentStore` (closure-owned append-only RBAC
  authority; deterministic temporal fold; deny-by-default).
- `audit.py` — `AuditLedger` (closure-owned append-only tamper-evident
  hash chain; `verify_chain`; `chain_head`).
- `api.py` — `ManagementAPI` (the composition root: the four-step
  flow over the five injected genuine authorities).
- `serialization.py` — fail-closed wire round-trips for audit records
  and role events.

External management-plane integrations belong under
`management/providers` (the sanctioned provider seam per spec/
architecture.md section 29); this package is standard-library only
and access-technology neutral (LOCK-001/002/003/016).
