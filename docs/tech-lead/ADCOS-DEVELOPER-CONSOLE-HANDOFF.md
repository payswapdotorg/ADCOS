# ADCOS Developer Console — Tech Lead Handoff

## Mission
Implement the approved ADCOS Developer Console so the deployed product is useful to developers, not merely reachable as an API. The UI must emerge every meaningful capability of the accepted backend without creating a second source of truth.

## Start here
1. Read `docs/superpowers/specs/2026-09-14-adcos-developer-console-design.md`.
2. Read `docs/superpowers/plans/2026-09-14-adcos-developer-console.md`.
3. Read `docs/tech-lead/ADCOS-TECH-LEAD-HANDOFF.md`.
4. Reinspect the actual backend and enumerate every supported endpoint/domain capability before writing frontend abstractions.
5. Do not trust this handoff or worker reports when they conflict with code, tests or live behavior.

## Worker allocation
Use at most 3 direct workers:

- Worker 1: web shell, routing, design system, typed API client, search/command infrastructure.
- Worker 2: Home, Connectivity, Contracts, Networks, Eligibility/Policy, Fulfillment and Replan.
- Worker 3: Developers, API Explorer, request inspector, Evidence, Assurance, Errors and trust/operations surfaces.

Workers 2 and 3 consume Worker 1's published client/type interfaces. Do not duplicate transport implementations.

## Integration authority
The Tech Lead owns integration, backend gap closure, deployment, browser verification, production promotion, rollback and acceptance. Workers do not widen backend semantics, change architecture locks or invent frontend-only domain rules.

## Critical product rule
The console is not a marketing site and not a generic admin template. A developer must be able to:

- discover a backend capability;
- understand its object/state model;
- execute the supported workflow;
- see the exact resulting object;
- inspect its related objects/evidence;
- understand failures;
- reproduce the operation through the API.

## Backend fidelity checks
Before accepting implementation, verify:

- contract fields map to canonical `ConnectivityContract` semantics;
- hard constraints cannot be dropped by UI serialization;
- provider data does not imply global ADCOS topology ownership;
- replan decisions identify requirements, observed values, eligibility/policy reasoning and evidence;
- evidence class is preserved, especially SOFTWARE vs physical/network evidence;
- backend reason codes are shown verbatim;
- credentials/secrets are handled according to backend issuance/reveal rules;
- API Explorer only exposes actually supported operations.

## UX quality bar
Use a Stripe-quality developer workflow as inspiration: high information density without clutter, excellent object inspection, contextual API visibility, copyable requests, strong error explanations, keyboard-first navigation, progressive disclosure and minimal context switching. The goal is developer flow state, not decorative polish.

## Deployment acceptance
Do not declare success because the build is green. Live acceptance must demonstrate:

1. `GET /` returns the actual ADCOS console.
2. Existing `/api/healthz` and `/api/readyz` semantics remain intact.
3. Core resource journeys work in a deployed environment.
4. At least one create/read/mutation journey can be reproduced through the displayed API request.
5. API errors retain canonical reason codes.
6. Existing R0-R9 software governance and deployment checks remain green.
7. No physical evidence obligations are claimed as satisfied by UI/software tests.

## Stop conditions
Stop and escalate to the Architect if implementation would require:

- a new durable authority in the browser;
- changing `ConnectivityContract` semantics;
- replacing provider-owned topology with an ADCOS-owned universal topology;
- silently weakening a hard requirement for UX convenience;
- changing the accepted deployment authority without explicit architectural decision;
- treating software evidence as physical connectivity proof.
