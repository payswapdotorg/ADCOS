# WORK-020 — 5G RAN/gNB Adapter

Status: Architect-anchored implementation brief derived from the frozen WORK-020 backlog entry, architecture, and architecture-lock because no WORK-020 handoff prompt is present on `main`.

Work Item: WORK-020
Dependencies: WORK-019
Objective: Integrate open 5G RAN implementations, initially OCUDU and/or OpenAirInterface, including CU/DU/RU boundary mapping.
Acceptance criteria:
- ADCOS core imports no vendor/Open RAN implementation types.
- RAN capability/health/resource state is mapped through adapters.
- RAN failure is isolated from core state.
- at least one SDR-based lab topology works.
Required verification: end-to-end lab tests.
Out of scope: new PHY implementation.
Definition of done: ADCOS can provision/use a standards-compliant 5G access path.

Architectural anchors:
- LOCK-002: 5G is an adapter; 3GPP RAN/core functions remain outside ADCOS core.
- LOCK-004: no arbitrary-phone-gNB fiction.
- LOCK-006: logical session identity is access independent.
- LOCK-007: capability negotiation is normative.
- LOCK-008: claims require provenance.
- LOCK-016: external RAN/modem/SDR implementations remain behind adapter/provider interfaces.
- LOCK-017: vendor implementations are not ADCOS authority.
- LOCK-018: use standard primitives rather than reinventing them.
- LOCK-021: mobility is session-level.
- LOCK-024: conformance is architectural.
- Module ownership: provider-specific implementation belongs under `/adapters`; core must not import provider SDKs or 3GPP RAN/CN implementation types.

Implementation direction:
- Build a provider-neutral RAN adapter contract under `/adapters`.
- Model CU/DU/RU and gNB boundary state as adapter-owned data, not core authority.
- Keep access technology identity separate from ADCOS NodeID and logical Session identity.
- Preserve least-authority/failure-isolation patterns established by WORK-016/017/018/019.
- Real Open RAN implementation bindings belong behind the adapter boundary; no vendor SDK types may cross into core.
- At least one real SDR-based lab topology must be exercised for acceptance; use standard/open components such as OpenAirInterface or O-RAN-compatible/open-source implementations as the first target, subject to actual environment availability.

The implementation must not modify frozen architecture/specification documents without a separately approved architecture change.
