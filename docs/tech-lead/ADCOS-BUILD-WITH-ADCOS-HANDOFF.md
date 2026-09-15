# ADCOS Tech Lead Handoff — Build with ADCOS & LLM Integration

## Mission

Implement and productionize the approved **Build with ADCOS** experience and canonical LLM Integration Pack.

Authoritative artifacts:
- `docs/superpowers/specs/2026-09-15-adcos-build-with-adcos-llm-integration-design.md`
- `docs/superpowers/plans/2026-09-15-adcos-build-with-adcos-llm-integration.md`

## Worker orchestration

Use at most **3 direct workers**:

**W1 — Knowledge / generated assets**
- integration registry
- registry consistency tests
- LLM pack and public machine assets

**W2 — Product / Docs**
- `/build`
- integration blueprint UX
- Build documentation
- navigation/search

**W3 — API education / acceptance**
- contextual API Explorer links
- ShareNet reference guide
- production checklist
- browser acceptance and regression verification

W2/W3 consume W1 registry contracts. No worker may create a second API/endpoint catalog.

## Architecture authority

Read actual repository code before implementation. The following are authorities, not the new docs layer:

- `developerapi/` — canonical developer HTTP boundary
- `web/src/lib/api/coverage` — executable API coverage registry
- `web/src/lib/education` — concept/operation/guide education registry
- `web/src/features/docs` — human documentation system
- `spec/application-model.md` — frozen application boundary
- `spec/integration/vertical-proof.md` — accepted ShareNet proof

## Non-negotiables

1. `ConnectivityContract` is the sole durable ADCOS contract authority.
2. Applications request technology-neutral connectivity outcomes.
3. Provider-native topology/routing/subscriber authority stays provider-owned.
4. Provider SDK types never appear in application-facing integration examples.
5. Webhooks are observations, not canonical business state.
6. API success never proves physical connectivity success.
7. Software and physical/network evidence remain distinct.
8. `/build` is presentation/education state, not a new domain authority.
9. ShareNet's local/P2P data plane remains separate from ADCOS gateway/backhaul orchestration.
10. No fake credentials, providers, telemetry or unsupported endpoints.

## Required product result

`adcos.vercel.app` must expose a first-class **Build with ADCOS** destination where a developer or architect can:

1. choose an integration pattern;
2. inspect application/ADCOS/provider ownership;
3. understand the canonical lifecycle;
4. see the required supported API operations;
5. understand webhooks, errors and degraded behavior;
6. read anti-patterns;
7. jump into docs/API Explorer;
8. download the same integration model for an LLM.

## Public LLM assets

The deployed site must return HTTP 200 and valid content for:

- `/llms.txt`
- `/llms-full.txt`
- `/adcos-integration-context.json`
- `/adcos-capabilities.json`
- `/adcos-operations.json`

The long-term implementation must derive these from the canonical registries so they cannot drift from the console.

## ShareNet acceptance

Teach this exact boundary:

```text
ShareNet content/P2P plane
        |
        | technology-neutral gateway/relay connectivity outcome
        v
ADCOS Connectivity Contract
        |
        v
Provider realization
```

ShareNet remains authoritative for content, P2P distribution, publisher trust, delivery receipts and application economics. ADCOS is authoritative for connectivity contract/orchestration. Providers remain authoritative for provider-native realization/topology.

## Verification

Run:

```bash
python3 tools/spec_check.py
python3 tools/fresh_session_check.py
```

Then run the complete backend/frontend batteries and new integration/LLM consistency tests.

Browser acceptance must demonstrate:

```text
/build
  -> choose pattern
  -> inspect ownership/lifecycle
  -> open API operation
  -> open docs
  -> retrieve LLM context

/llms.txt -> 200
/llms-full.txt -> 200
/adcos-integration-context.json -> 200 + valid JSON
/adcos-capabilities.json -> 200 + valid JSON
/adcos-operations.json -> 200 + valid JSON
```

Re-test existing Console V2 entry points and expert workbench routes before promotion.

## Definition of done

Completion requires production UI inspection, not just green tests. A first-time developer must be able to understand where ADCOS belongs in their architecture, and an architect/coding LLM must be able to obtain an authoritative machine-readable integration model without conversation history or internal repository-only knowledge.
