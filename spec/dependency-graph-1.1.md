# ADCOS Architecture 1.1 Dependency Graph

**Status:** ACCEPTED via ACR-014 (accepted proposal record; the canonical dependency model is `spec/dependency-graph.md`)

```text
M001 Architecture Freeze
 |
 +--> M002 Contract Core
 |      |
 |      +--> M003 Offers
 |      |      |
 |      |      +--> M004 Eligibility/Policy
 |      |             |
 |      |             +--> M005 Evidence/Assurance
 |      |                    |
 |      |                    +--> M006 Execution Plan
 |      |                           |
 |      |                           +--> M007 Adapters
 |      |                                  |
 |      |                                  +--> M008 Replan/Failover
 |      |
 |      +--> M009 Usage/Commercial
 |
 +--> M013 Developer API
        |
        +--> M010 ShareNet Proof
        +--> M011 RoamLink Proof
        +--> M012 COMOS Proof

M008 + M009 + M010 + M011 + M012 + M013
    |
    v
M014 Production Federation
```

The optimizer is replaceable and may be developed in parallel after M006,
provided it cannot redefine normative authority.
