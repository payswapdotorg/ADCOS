# ADCOS Vertical Integration Proof

## ShareNet

1. ShareNet submits a technology-neutral connectivity intent for gateway/relay nodes.
2. At least two provider domains advertise offers.
3. ADCOS evaluates eligibility and evidence.
4. ADCOS creates one connectivity contract.
5. ADCOS executes via one or more providers.
6. A provider realization degrades or fails.
7. ADCOS replans/fails over without weakening hard contract constraints.
8. Usage and assurance evidence remain attributable to the contract.

ShareNet retains authority over content, P2P distribution, publisher trust and its own application economics.

## RoamLink

1. RoamLink requests connectivity for a defined subscriber cohort.
2. ADCOS exposes provider offers and commercial terms.
3. A contract is accepted.
4. RoamLink receives execution status and assurance events.
5. Provider changes are absorbed behind the ADCOS contract.
6. RoamLink retains authority over mobile observation, device context, eSIM product behavior and mobile UX.

## COMOS

1. COMOS requests gateway connectivity for communication traffic.
2. ADCOS selects suitable offers.
3. A contract is created.
4. COMOS sends technology-neutral communication requirements.
5. ADCOS supplies connectivity execution.
6. COMOS retains authority over identity, communication bundles, channel semantics and delivery semantics.

## Architectural acceptance

The proof succeeds only if none of the three applications must import provider-native APIs into their core and none becomes a second connectivity-contract authority.
