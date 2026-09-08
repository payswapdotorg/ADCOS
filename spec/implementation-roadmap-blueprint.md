# ADCOS Implementation Roadmap Blueprint

This document is a subordinate implementation blueprint for the roadmap. It does
not override frozen architecture, locks, ACRs, dependency semantics, or
repository-local authorization.

## Program operating model

A single autonomous LLM may act as both Architect and Tech Lead. It must persist
governance decisions before implementation and may dispatch at most 3 direct
workers, each with at most 3 subagents.

Every implementation unit must have:

- a durable Work Item contract;
- an explicit dependency set;
- repository-local authorization before implementation;
- executable acceptance tests;
- negative/authority tests where applicable;
- exact provenance for the reviewed delivery;
- Architect acceptance before merge.

## Transition 1 — Architecture 1.0 to 1.1

### Objective
Promote the proposed connectivity-exchange architecture only through the
normal ACR process.

### Required artifacts

- accepted ACR for Architecture 1.1;
- `spec/architecture.md` updated to 1.1;
- `spec/architecture-lock.md` updated to 1.1 locks;
- Architecture 1.0 archived without rewriting historical records;
- current `spec/work-items.md` and `spec/dependency-graph.md` updated under the
  architecture-change rules;
- roadmap/current-state/execution-state/authority order reconciled;
- exact migration classification preserved.

### Acceptance
A fresh clone must resolve exactly one current architecture authority and must
not be able to mistake a proposal/archive for the current contract.

## R7 — Universal Connectivity Commerce

### R7.1 Contract model
Implement canonical `ConnectivityContract` lifecycle and authority.

Required invariants:

- contract is independent of path/session/provider-native resource;
- beneficiary scope is explicit;
- hard constraints are immutable unless explicitly renegotiated;
- start/end/expiry are authoritative;
- idempotent creation and mutation;
- cancellation/expiration/failure are explicit states;
- contract provenance is retained.

Tests:

- duplicate create is idempotent;
- expired contract cannot activate;
- path replacement does not create a new contract;
- unauthorized caller cannot modify another principal's contract;
- hard constraint cannot be weakened by optimizer output.

### R7.2 Offers and eligibility
Implement provider offer discovery and deterministic eligibility.

Offer must contain provider identity, validity, service boundary, capabilities,
commitments, constraints, commercial terms and evidence references.

Tests:

- expired offer is rejected;
- provider-native identifiers never become contract authority;
- ineligible offer cannot be selected;
- same input snapshot produces stable ordering/tie-breaking;
- missing/stale evidence is not silently treated as a guarantee.

### R7.3 Provider federation exchange
Reuse R6 federation onboarding and expose only capability/offer/commitment
surfaces required by R7.

Tests:

- federated provider remains scoped/revocable;
- provider cannot see another provider's private topology;
- membership cannot imply universal trust;
- provider secret never enters offer/contract metadata.

### R7.4 Execution plan
Translate an accepted contract into an `ExecutionPlan` with bounded
`ExecutionSegment` values.

Required plan fields:

- contract reference;
- selected provider/domain references;
- ordered execution segments;
- required capabilities;
- reservation references;
- security requirements;
- expiry/deadline;
- failover alternatives;
- evidence obligations.

Tests:

- plan cannot reference a contract that does not exist;
- plan cannot violate hard contract constraints;
- unsupported provider capability fails closed;
- segment failure can be replaced without mutating contract identity.

### R7.5 Standard/provider adapters
Implement reference adapters around existing mechanisms rather than inventing
new transport protocols.

Adapter boundary:

```text
inspect_capabilities()
inspect_offers()
reserve()
activate()
measure()
reconfigure()
release()
health()
```

Tests:

- provider-native type does not cross the core boundary;
- adapter failure is represented without changing contract authority;
- reserve/activate/release are idempotent;
- health/measurement evidence carries provenance.

### R7.6 Application-funded connectivity API
Expose service semantics to authorized applications.

Required operations:

```text
createConnectivityIntent
listOffers
checkEligibility
acceptOffer
createConnectivityContract
getContract
getExecutionStatus
getAssurance
getUsage
terminateContract
subscribeToEvents
```

Applications MAY purchase/sponsor connectivity for authorized beneficiaries.

Tests:

- ShareNet can request connectivity for a relay/user cohort without knowing an
  access technology;
- RoamLink can request connectivity for a subscriber cohort;
- COMOS can request connectivity for gateway/relay infrastructure;
- application APIs do not expose provider SDK types;
- API state cannot become a second source of truth.

### R7.7 Usage and settlement reconciliation
Record connectivity usage against the contract and produce settlement
references for external payment systems.

Tests:

- usage cannot be attributed to a nonexistent contract;
- duplicate measurement events do not double-count billable usage;
- finalization is idempotent;
- external payment confirmation cannot itself create connectivity;
- settlement references reconcile to contract/usage evidence.

## R8 — Resilience, Mobility and Scale

### R8.1 Closed-loop assurance
Implement continuous evaluation of contract obligations using typed evidence.

Assurance states:

```text
COMPLIANT
DEGRADED
VIOLATED
UNKNOWN
STALE
FAILED
TERMINATED
```

Tests distinguish actual violation from missing/stale evidence.

### R8.2 Replan/failover
Implement replan against the existing contract.

Tests:

- failed segment triggers alternate realization;
- replan never weakens hard constraints;
- no compliant realization yields explicit degraded/failed state;
- successful failover preserves contract identity;
- repeated failure/replan is idempotent.

### R8.3 Mobility and multipath
Integrate existing session/mobility/multipath authorities as optional execution
capabilities.

Tests:

- session remains stable across supported access change;
- multipath is used only when capability/policy permits;
- path/session remain execution artifacts rather than contract authority.

### R8.4 Local-first/offline operation
Support local policy/evidence caches and delayed synchronization where the
contract allows intermittent operation.

Tests:

- offline cache cannot bypass authorization expiry;
- delayed evidence retains original timestamps/provenance;
- reconnection reconciles duplicate events deterministically.

### R8.5 Scale and operational resilience
Harden rate/resource protection, persistence recovery, key rotation/revocation,
upgrade/rollback, federation scale and observability.

Tests include recovery from partial failure and deterministic replay of durable
journals.

## R9 — Future Access Technology

### R9.1 Adapter-only technology introduction
Add future access profiles without changing normative contract semantics.

### R9.2 5G/6G coexistence
5G, Wi-Fi, satellite, mesh and future IMT profiles coexist behind the same
contract/execution boundary.

### R9.3 Upgrade compatibility
Unknown optional capabilities fail soft; unsupported required capabilities
fail closed; no flag-day protocol migration is required.

### R9.4 Interoperability evidence
External interoperability evidence is separately classified from in-repo
conformance and separately accepted.

## Vertical proofs

### ShareNet
Prove application-funded gateway/relay connectivity plus user-cohort
connectivity, ordinary IP traffic, provider failover and usage reconciliation.
ShareNet remains authoritative for content, P2P distribution, publisher trust,
contributions and model economics.

### RoamLink
Prove wholesale connectivity acquisition for roaming/mobile subscribers across
multiple provider offers, with execution changes hidden behind the ADCOS
contract. RoamLink remains authoritative for device context, mobile observation,
eSIM/product behavior and UX.

### COMOS
Prove communication-gateway connectivity with online and offline/DTN-capable
realizations. COMOS remains authoritative for communication identity, bundles,
conversations, channels and delivery semantics.

## Program exit

The roadmap is complete only when a third-party application can buy/sponsor
connectivity through the stable developer API; ADCOS can select and execute one
or more provider realizations; failures can be assured/replanned; usage and
settlement can be reconciled; and none of the application or provider systems
must surrender their own domain authority.
