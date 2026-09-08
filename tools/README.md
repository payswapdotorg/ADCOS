# ADCOS Specification and Handoff Tooling

## spec_check.py — specification consistency checks

Deterministic, offline consistency checks for the ADCOS specification repository. Introduced by WORK-001. See the check catalog below.

### Invocation

```bash
python3 tools/spec_check.py                    # full check suite
python3 tools/spec_check.py --provenance       # strict ARCH-08 provenance only
python3 tools/fresh_session_check.py            # fresh-agent handoff integrity
```

Requirements: Python 3.8+ standard library only for `spec_check.py` and
`fresh_session_check.py`. No third-party packages are required by either tool.

## fresh_session_check.py — fresh-agent handoff integrity

`fresh_session_check.py` verifies that a new Architect/Tech Lead/worker can
reconstruct the repository's current operating model without chat history. It
checks that required mission, authority, roadmap, execution-state, handoff and
worker-model artifacts exist; the current R7 checkpoint is recorded; the
single-agent Architect+Tech-Lead mode is documented; the 3x3 dispatch ceiling is
documented; and the persisted `main_sha` agrees with `origin/main` when a live
Git ref is available.

The checker never grants authorization. A mismatch between live `origin/main`
and persisted execution state is an explicit fail-closed result requiring
repository reconciliation.

For an external clone or CI job without a usable `origin/main` ref, pass the
live SHA explicitly:

```bash
python3 tools/fresh_session_check.py --actual-main-sha <sha>
```

## spec_check.py check catalog

The existing checker remains the authority for frozen specification mechanics,
backlog integrity, dependency resolution, persistent-Architect state,
authorization provenance, canonical references and evidence obligations. Its
historical check catalog remains in `tools/spec_check.py` and is intentionally
not duplicated here.

## spec_check_selftest.py

Deterministic, offline negative and positive tests for `spec_check.py`.

```bash
python3 tools/spec_check_selftest.py
```

## Fresh-session completion rule

A clean checkout plus GitHub access must be enough to determine what ADCOS is,
what architecture is authoritative, which roadmap gate is next, whether an
implementation is authorized, what the exact Work Item is, how the Tech Lead
may dispatch workers, and what evidence is required for acceptance.
