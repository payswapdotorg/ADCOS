# ADCOS Dependency Graph

## Status

FROZEN — Architecture Version 1.1 successor dependency model.

- Accepted: ACR-014 (DEC-0098 approval; synchronized updates merged with the M001 delivery)
- Supersedes: the Architecture 1.0 dependency graph, preserved verbatim at `spec/history/dependency-graph-1.0.md`

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

## Roadmap sequencing

The program roadmap (`spec/architect/roadmap.yaml`) sequences these work
items through the R7 (universal connectivity commerce), R8 (resilience,
mobility and scale) and R9 (future access technology) gates after M001.
