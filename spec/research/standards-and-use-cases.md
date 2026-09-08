# ADCOS Architecture Basis

The Architecture 1.1 direction is grounded in existing standards and systems rather than requiring ADCOS to replace them.

## Standards/system boundaries

- IETF RFC 9315 (Intent-Based Networking): intent includes fulfillment and assurance; this supports ADCOS treating contract fulfillment and assurance as first-class concerns.
- QUIC (RFC 9000): transport-level connection migration is an execution mechanism rather than an ADCOS contract primitive.
- MPTCP (RFC 8684) and MP-QUIC: multipath can be an execution capability.
- 3GPP ATSSS: steering, switching and splitting demonstrate that access selection is already a domain-specific execution concern.
- DTN (RFC 4838, RFC 9171): store-and-forward is a specialized execution mode for disrupted networks.
- SCION: path-aware, trust-aware routing demonstrates a useful provider/domain execution technology without requiring universal ADCOS ownership of topology.
- O-RAN: programmable, observable RAN control supports adapter-based domain execution.
- GSMA/TM Forum/CAMARA ecosystem APIs: provider federation and network APIs support exchange/orchestration boundaries.
- ETSI MEC: edge capabilities demonstrate service-specific demand for heterogeneous connectivity.

## Use cases ADCOS should enable

1. Application-funded user connectivity.
2. Multi-provider enterprise connectivity.
3. Roaming and eSIM aggregation.
4. Community relay/gateway connectivity.
5. Emergency/disaster connectivity.
6. IoT and fleet connectivity.
7. Satellite/terrestrial hybrid connectivity.
8. Communication gateway connectivity.
9. Content-distribution backhaul.
10. AI/edge workloads with connectivity requirements.

## Design implication

These use cases are best served by a common connectivity contract and exchange layer rather than by making every application implement provider-specific network integrations.
