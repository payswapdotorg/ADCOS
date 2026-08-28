# WORK-030 — Management API

## Status

**IMPLEMENTATION HANDOFF — RECONSTRUCTED (implementer-side)**

No separate WORK-030 handoff existed on the accepted `main` baseline
(62f5b9d, the WORK-029 merge). This brief reconstructs the
implementation boundary from the frozen `spec/work-items.md`,
`spec/architecture.md`, `spec/architecture-lock.md`, and accepted
dependency/review governance only. It does not modify the frozen
architecture or backlog. It lives under `docs/` (the
WORK-023/024/025/028/029 handoff pattern) so that the branch keeps
`spec/` byte-identical to `origin/main`, as the frozen-surface
batteries require.

## Authoritative contract

Frozen `spec/work-items.md` defines WORK-030 as:

- **Objective:** implement management, configuration, audit, and
  operational control APIs.
- **Dependencies:** WORK-010, WORK-011, WORK-012, WORK-015, WORK-026
  (all Architect-accepted and merged).
- **Acceptance:** privileged actions require explicit policy; audit
  logs are immutable or tamper-evident; APIs cannot bypass core
  authority boundaries.
- **Verification:** API security, audit, RBAC tests.
- **Definition of done:** ADCOS can be operated as a real network
  platform.

## Architectural rules

1. The frozen dependency list is exactly WORK-010 (policy),
   WORK-011 (routing), WORK-012 (sessions), WORK-015 (federation),
   WORK-026 (telemetry). No additional dependencies are inferred from
   implementation convenience (`spec/workflow.md` §2.1). The family
   imports the shared cross-cutting protocol primitives
   (`protocol.temporal`, `protocol.canonicalization`) exactly as every
   other family does (federation/telemetry/sessions precedent); it
   imports NO other family — topology/resource state reaches the
   routing authority only as request-supplied opaque materials.
2. `/management` owns lifecycle/control APIs (`spec/architecture.md`
   §29; `spec/architecture-lock.md` §3). It owns NO policy, routing,
   session, federation, telemetry, or identity truth: every privileged
   action is a FRESH genuine WORK-010 engine evaluation performed
   inside the API call over the injected genuine `PolicyStore`, and
   every state change is DELEGATED to the owning authority's genuine
   public API (`P11`; `spec/architecture.md` §19/§22). The provenance
   discipline is the PR #31 review lesson applied at birth: no API
   method accepts a caller-supplied `PolicyDecision`,
   `RouteDecision`, or any other authority-minted object as
   authorization material — the decision executed is the one the
   engine evaluated inside the call (battery case_14 proves both the
   structural absence of an injection surface and the decision
   identity).
3. Privileged actions require explicit policy (acceptance criterion
   1): the two-key design — an ACTIVE role assignment must grant the
   operation's frozen capability (RBAC, deny-by-default, additive
   roles, a role is never an identity per §4) AND the WORK-010
   authority must explicitly ALLOW the frozen policy operation
   (deny-by-default; no applicable set, no matching rule, or an
   explicit deny all deny). Neither key alone ever suffices. Read /
   inspect operations are non-privileged capability checks — the
   frozen WORK-010 operation vocabulary contains no read operation,
   and the policy README's structural classification rule forbids
   inferring one from naming.
4. Audit logs are immutable and tamper-evident (acceptance criterion
   2): every API call — allowed OR denied — produces exactly one
   audit record; the ledger is an append-only sha256 hash chain
   (`record_id_n = sha256(prev + "|" + canonical(content_n))`)
   mechanically verified by `verify_chain()` (field mutation,
   deletion, reordering, and forged insertion all break at an
   identifiable sequence); `chain_head()` exists for external
   notarization (evidence retention, §5.6). The ledger state is
   closure-owned (immutable tuple in closure cells; no instance
   attribute holds the history; no mutation or removal API exists) —
   the accepted WORK-027 closure-owned authority discipline, with the
   public callables' closure cells holding DATA ONLY (the same
   mechanical bar the WORK-027 battery enforces). Records carry
   deterministic diagnostics only, never secrets (§20).
5. APIs cannot bypass core authority boundaries (acceptance criterion
   3): the API HOLDS the genuine injected authorities and DELEGATES —
   policy truth is the engine's verdict; route computation is the
   genuine `RoutingEngine` under the freshly evaluated policy
   decision (request-supplied routing materials passed through
   without interpretation; never recomputed/repaired/replaced —
   WORK-012's rule); session creation/transitions/suspension/
   termination are the session authority's (creation-contract
   verification, frozen transition table); federation
   establish/accept/export/import are the federation authority's
   (identity binding, scope-envelope/anti-escalation discipline); the
   telemetry privacy fence and born-bound promotion flow stay entirely
   with the telemetry authority. Authority rejections surface as
   `management.authority-rejected` — NEVER overridden. The battery's
   AST proof (case_36) shows mechanically that the API never writes
   into an authority object and never touches another authority's
   private members; case_37 shows the constructor rejects duck-typed
   fake authorities.
6. RBAC and audit are the management plane's OWN state (§3
   `/management` ownership): the role-assignment log is append-only
   (grant/revoke events, deterministic temporal fold at an injected
   instant, deny-by-default for expired/revoked/not-yet-granted/
   never-granted); the role catalog is DATA validated against the
   frozen capability vocabulary; role ids are structurally disjoint
   from the NodeID grammar (a role is never an identity). Initial
   assignments are constructor-injected deployment configuration;
   every later RBAC mutation flows through the management API behind
   the policy-gated `management.role-assign` operation.
7. Cross-set policy aggregation is documented, conservative, and
   deterministic: the store's live applicable sets are evaluated in
   snapshot order; the operation is authorized iff at least one set
   explicitly ALLOWS and NO set explicitly denies or fails closed
   (deny/`fail-closed`/`conflict`/`invalid-policy`/`invalid-subject`/
   `unsupported-predicate`); a set that is merely silent
   (`default-deny`, `missing-fact`, `policy-expired`,
   `policy-not-yet-valid`) grants nothing and does not veto another
   set's explicit allow. Management performs no rule interpretation,
   no precedence invention, and no conflict resolution (those are the
   engine's job inside one set); with a single applicable set the
   aggregation reduces exactly to that set's own verdict.
8. Federation domain registration, policy-set publication, and the
   node's initial role assignments remain the authorities' own
   deployment-time surfaces (direct public APIs): the management API
   exposes exactly the frozen policy-gated operation set over its
   declared dependencies. WORK-029's upgrade lifecycle state stays
   node-local and is NOT exposed by this Work Item (out of scope).
9. Vendor specifics stay behind the provider seam (LOCK-016): the
   family is standard-library only, access-technology neutral
   (LOCK-001/002/003); external management-plane integrations belong
   under `management/providers` (§29), which this Work Item does not
   add.

## Deliberate, flagged amendments to accepted dependency surfaces

(the WORK-026/WORK-029 amendment precedent — minimal, justified by
this Work Item's frozen acceptance criteria, documented in both
READMEs and in the amended batteries):

1. **`policy.model.Operation` gains `management.role-assign`** (and
   its structural `Privileged` classification): the ONLY operation
   under which the management plane's RBAC state may be mutated.
   Justification: the acceptance criterion "privileged actions require
   explicit policy" — role-assignment administration grants authority
   (it is the capability half of the two-key design), so without a
   frozen policy operation it could never be policy-gated, and RBAC
   could only be administered outside the audited, policy-gated API
   surface. Deny-by-default like every privileged operation.
   Amended: `policy/model.py`, `policy/README.md`,
   `tools/policy_selftest.py` cases 45/46 (the same fixtures the
   WORK-026 amendment extended).
2. **`tools/telemetry_selftest.py` case_19** admits `management` as a
   dependency-graph-sanctioned downstream consumer of the telemetry
   DATA surface (WORK-030 declares WORK-026), pinned to
   `telemetry.store` / `telemetry.model` / `telemetry.errors` (the
   public vocabulary of authority rejections) only.

## Required proof style

Every acceptance-critical control has a structural proof or a
discriminating regression in `tools/management_selftest.py` (37
cases): the two-key matrix (case_11), the cross-set aggregation both
directions (case_12), deny-by-default over an empty/expired policy
store (case_13), the provenance/no-injection proof (case_14), the
no-bypass AST proof (case_36), the genuine-authorities constructor
proof (case_37), the audit tamper matrix (case_07) and closure-owned
immutability proofs (cases 05/10), the RBAC temporal matrix (case_03)
with additive roles (case_04) and immediate revocation effect
(case_26), authority-verdict non-override (case_16), and the privacy
fence (case_23) and born-bound promotion flow (case_24).

## Out of scope

- any UI/CLI implementation (§29: UI/CLI code may CALL management
  APIs but must not implement protocol authority — no UI exists in
  this repository yet);
- `management/providers` integrations (external management-plane
  technology belongs behind that seam);
- upgrade lifecycle exposure (WORK-029's node-local state), resource
  admission (WORK-008 — not a declared dependency), identity
  lifecycle (WORK-004 — not a declared dependency), policy
  publication (the WORK-010 store's own surface);
- any change to `spec/` (byte-identical to `origin/main`).
