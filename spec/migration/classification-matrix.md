# ADCOS Architecture 1.0 -> 1.1 Classification Matrix

| Existing concept/area | Classification | Target authority |
|---|---|---|
| Identity / Trust | RETAIN + REFACTOR | ADCOS identity/authority |
| Capability registry | RETAIN + REFACTOR | Offer/capability exchange |
| Discovery | REFACTOR | Offer discovery, not global topology |
| Topology | DEMOTE | Provider-local execution input |
| Node / Link / Path graph | DEMOTE | Execution model, not contract model |
| Session | RETAIN | Execution/runtime artifact |
| Multipath | RETAIN | Optional execution capability |
| Mobility | RETAIN | Execution/runtime capability |
| Federation | REFACTOR | Provider-domain federation |
| Adapter runtime | RETAIN + REFACTOR | Execution bridge |
| Transport mechanisms | DEMOTE | Standard/provider mechanisms |
| Resource allocation | REFACTOR | Contract/execution reservation |
| Policy | RETAIN + REFACTOR | Eligibility + contract constraints |
| Evidence | REFACTOR | Typed evidence/assurance |
| Routing | DEMOTE | Provider/local execution optimizer |
| Services | REFACTOR | Developer connectivity service |
| Commercial | REFACTOR | Contract/usage/settlement reference |
| Telemetry | RETAIN | Assurance evidence |
| Simulator | RETAIN | Reference implementation |
| Access-specific modules | DEMOTE/REFACTOR | Adapters |
| Old Architecture 1.0 docs | ARCHIVE | Historical evidence |

No historical acceptance record is rewritten or deleted.
