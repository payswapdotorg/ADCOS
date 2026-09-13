# ADCOS runtime inventory

Inventory is intentionally created only after verifying the live `main` tree and accepted software entrypoints. The deployment branch currently contains the approved deployment design and work plan; no framework-specific runtime has been assumed.

Current repository facts verified so far:

- Repository: `payswapdotorg/ADCOS`.
- Default branch: `main`.
- Accepted software baseline: R9/M024 merge `d1dbe69cb93ca77f82bf8ec1ab8496a195e13a62`.
- Current execution state is `awaiting-architect-decisions` with no active implementation authorization.
- The accepted software roadmap is complete through R9, while physical evidence remains separate.

Next runtime-specific fields are to be populated from the actual manifests and entrypoints before implementation: language/package manifest, HTTP entrypoint, persistence seams, evidence/object-storage seam, CI command, deploy runtime, and required environment variables.
