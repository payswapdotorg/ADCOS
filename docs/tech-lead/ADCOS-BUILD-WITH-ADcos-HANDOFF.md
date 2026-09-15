# ADCOS Tech Lead Handoff — Build with ADCOS & LLM Integration

## Mission

Implement the approved `Build with ADCOS` experience and canonical LLM Integration Pack described by:

- `docs/superpowers/specs/2026-09-15-adcos-build-with-adcos-llm-integration-design.md`
- `docs/superpowers/plans/2026-09-15-adcos-build-with-adcos-llm-integration.md`

This is an extension of Console V2. Preserve every accepted V1/V2 capability.

## Worker orchestration

Use at most **3 direct workers**. Prefer:

- **Worker 1 — Knowledge / generated assets**
  - integration registry
  - consistency gates
  - LLM pack
  - public machine assets

- **Worker 2 — Product / Docs**
  - `/build`
  - architecture-pattern UX
  - integration blueprint
  - Build documentation
  - navigation/search entry points

- **Worker 3 — Integration education / acceptance**
  - API Explorer contextual integration links
  - ShareNet reference guide
  - production checklist
  - browser acceptance and regression verification

Workers may use up to 3 subagents each, within the repository's established worker model. Worker 2 and Worker 3 consume Worker 1's registry contracts and must not create duplicate operation catalogs.

## Repository truth

The current ADCOS repository already contains the accepted Developer API and Console V2 documentation/learning surfaces. Inspect actual code before assuming any route or registry exists.

Relevant authorities:

- `developerapi/` — canonical developer-facing HTTP/API boundary
- `web/src/lib/api/coverage` — operation coverage registry
- `web/src/lib/education` — concept/operation/guide education metadata
- `web/src/features/docs` — user-facing documentation system
- `web/src/features/` API Explorer / Playbooks / Quickstart / tour surfaces
- `spec/application-model.md` — frozen application boundary
- `spec/integration/vertical-proof.md` — frozen ShareNet integration proof

## Architectural rules

1. Do not create a second connectivity-contract authority.
2. Do not create a second API operation catalog.
3. Do not expose provider SDKs or provider-native topology in application-facing examples.
4. Keep the application model technology-neutral.
5. Treat webhook events as observations, not canonical business state.
6. Never describe API success as proof of physical connectivity.
7. Keep software/deployment evidence distinct from physical/network evidence.
8. No fake credentials, fake providers, fake telemetry or fabricated API operations.
9. `/build` produces presentation state only; it does not persist architectural decisions as ADCOS domain authority.
10. ShareNet's P2P/content plane remains independent of ADCOS control-plane reachability.

## Required user-visible result

`adcos.vercel.app` must have a prominent **Build with ADCOS** destination where a new developer or architect can:

1. choose an integration pattern;
2. see application/ADCOS/provider ownership;
3. see the canonical connectivity lifecycle;
4. see the exact API operations and webhook classes required;
5. understand failure/degraded connectivity behavior;
6. read anti-patterns;
7. access relevant API Explorer operations and docs;
8. retrieve the same context in machine-readable form for an LLM.

## Required public assets

The deployed web app must serve:

- `/llms.txt`
- `/llms-full.txt`
- `/adcos-integration-context.json`
- `/adcos-capabilities.json`
- `/adcos-operations.json`

These must be projections of the canonical frontend metadata, not separately curated endpoint lists.

## ShareNet reference acceptance

The ShareNet pattern must explicitly teach:

```text
ShareNet content/P2P plane
        |
        | gateway/relay connectivity outcome
        v
ADCOS Connectivity Contract
        |
        v
Provider execution
```

ShareNet owns content, publisher trust, P2P distribution, delivery receipts and application economics. ADCOS owns connectivity contract/orchestration state. Providers own provider-native realization/topology.

The documentation must explicitly say that ordinary ShareNet device-to-device transfers do not become ADCOS connectivity transactions.

## Verification gates

Before opening/updating the implementation PR, run:

```bash
python3 tools/spec_check.py
python3 tools/fresh_session_check.py
```

Then run the full existing frontend/backend batteries plus new integration-registry and LLM-pack tests.

Browser acceptance must prove:

```text
/build
  -> choose pattern
  -> inspect blueprint
  -> open API operation
  -> open supporting docs
  -> retrieve LLM context

/llms.txt                 -> 200
/llms-full.txt            -> 200
/adcos-integration-context.json -> 200 + valid JSON
/adcos-capabilities.json       -> 200 + valid JSON
/adcos-operations.json         -> 200 + valid JSON
```

Also re-verify the existing `/`, `/docs`, `/quickstart`, `/playbooks`, `/tour`, `/connectivity`, `/developers`, `/evidence`, `/assurance`, `/settings` surfaces.

## Definition of done

Do not declare completion from tests alone. The Tech Lead must inspect the resulting production UI and prove that a developer who has never used ADCOS can understand how to incorporate it into an application architecture, and that an LLM can obtain an authoritative, machine-readable integration model without internal repository context.
