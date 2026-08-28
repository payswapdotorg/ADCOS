#!/usr/bin/env python3
"""WORK-032 conformance-suite battery (deterministic, stdlib only).

Runs the complete conformance matrix against the accepted authority
implementations and verifies:

- every area's vectors are CONFORMANT (positive and negative);
- coverage completeness: all required areas, all 15 negative/security
  categories, all 7 failure/recovery categories, all 7 discrimination
  areas, both polarities per area, and authority attribution for every
  declared dependency;
- determinism: identical report digests across runs, subprocesses, and
  hash seeds; canonical ordering independent of registration order;
  byte-identical serialization round-trips;
- the evidence model: three strictly separated evidence classes, with
  external evidence unattainable from in-repo vectors;
- discriminating power: for each required security property
  (provenance, replay, downgrade, capability inflation,
  authority-boundary violations, adapter isolation, forbidden
  dependency directions), a deliberately SABOTAGED candidate world
  (the vulnerable behavior implemented over public APIs) makes the
  paired vector NONCONFORMANT while the genuine world stays
  CONFORMANT -- the suite can fail a broken candidate, not merely pass
  the accepted one;
- structural audits are themselves discriminating (sabotaged fixture
  sources are detected);
- frozen surfaces: spec/ byte-identical to origin/main, docs/ limited
  to the handoff, additive CI wiring, frozen public API, and a clean
  compile.
"""

from __future__ import annotations

import os
import py_compile
import subprocess  # noqa: S404 - deterministic child processes of this repo's own tools
import sys
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from conformance import (  # noqa: E402
    API_SURFACE,
    ConformanceVector,
    ConformanceWorld,
    ExpectedOutcome,
    ExternalEvidenceRecord,
    ObservedOutcome,
    Polarity,
    RegistryError,
    REQUIRED_AREAS,
    REQUIRED_DISCRIMINATION_TAGS,
    REQUIRED_NEGATIVE_TAGS,
    REQUIRED_RECOVERY_TAGS,
    REASON_VALUES,
    Verdict,
    assert_no_external_claim,
    build_default_registry,
    build_evidence_report,
    report_canonical_bytes,
    report_digest,
    report_from_mapping,
    run_matrix,
    run_vector,
)
from conformance.model import ConformanceReport  # noqa: E402
from conformance.world import (  # noqa: E402
    AdapterSurface,
    CapabilitySurface,
    EnvelopeSurface,
    SessionSurface,
    TopologySurface,
    TransportSurface,
)
from conformance.vectors.structure import (  # noqa: E402
    find_import_violations,
    find_nondeterminism,
    find_private_access,
    find_shadow_authority,
    find_vendor_tokens,
)

Result = Tuple[str, bool, str]

_FAMILY_FILES = sorted((REPO_ROOT / "conformance").rglob("*.py"))

#: The full expected battery set wired into CI (32 prior tools + this one).
_EXPECTED_TOOLS = [
    "spec_check.py", "spec_check_selftest.py", "schema_check.py",
    "schema_selftest.py", "envelope_selftest.py", "identity_selftest.py",
    "capability_selftest.py", "discovery_selftest.py",
    "topology_selftest.py", "resource_selftest.py", "intent_selftest.py",
    "policy_selftest.py", "routing_selftest.py", "session_selftest.py",
    "multipath_selftest.py", "mobility_selftest.py",
    "federation_selftest.py", "adapter_selftest.py",
    "transport_selftest.py", "ipintegration_selftest.py",
    "fivegc_selftest.py", "wifi_selftest.py", "backhaul_selftest.py",
    "mesh_selftest.py", "distcore_selftest.py", "service_selftest.py",
    "telemetry_selftest.py", "energy_selftest.py", "security_selftest.py",
    "upgrade_selftest.py", "management_selftest.py", "simulator_selftest.py",
    "conformance_selftest.py",
]


def ok(name: str, detail: str) -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _matrix() -> ConformanceReport:
    registry = build_default_registry()
    return run_matrix(registry.canonical_vectors(), ConformanceWorld)


def _vector_by_id(vector_id: str) -> ConformanceVector:
    registry = build_default_registry()
    for vector in registry.canonical_vectors():
        if vector.vector_id == vector_id:
            return vector
    raise KeyError(vector_id)


def _run_one(vector_id: str, world: ConformanceWorld):
    return run_vector(_vector_by_id(vector_id), world)


def _area_results(report: ConformanceReport, area: str) -> List:
    results = report.results_for_area(area)
    if not results:
        raise AssertionError("no results for area %r" % area)
    return list(results)


# ---------------------------------------------------------------------------
# 1-10: per-area conformance
# ---------------------------------------------------------------------------


def _area_case(area: str) -> Result:
    name = "case_%02d_%s_area_matrix" % (
        REQUIRED_AREAS.index(area) + 1, area,
    )
    report = _matrix()
    results = _area_results(report, area)
    bad = [r for r in results if r.verdict is Verdict.NONCONFORMANT]
    if bad:
        return fail(
            name,
            "nonconformant vectors: %s" % "; ".join(
                "%s (%s)" % (r.vector_id, r.reason_class) for r in bad[:3]
            ),
        )
    positives = sum(1 for r in results if r.polarity == "positive")
    negatives = len(results) - positives
    return ok(
        name,
        "%d/%d %s vectors conformant (%d positive / %d negative)"
        % (len(results) - len(bad), len(results), area, positives, negatives),
    )


# ---------------------------------------------------------------------------
# Sabotaged candidate worlds (test fixtures ONLY -- the vulnerable
# behaviors implemented over public APIs; never shipped, never exported)
# ---------------------------------------------------------------------------


class _ProvenanceSabotagedTopology(TopologySurface):
    """The provenance-collapse vulnerability: the authoritative query
    ignores reporter/source-class, so remote claims leak in."""

    def authoritative(self, subject: str, *, now) -> tuple:
        return self.graph.get_claims_for_subject(subject, now=now)


class _ReplayBlindEnvelope(EnvelopeSurface):
    """The replay vulnerability: the replay-validation hook is dropped."""

    def accept_bytes(self, data, *, now, policy, replay=None):
        from protocol import accept

        del replay  # the vulnerability: caller replay state ignored
        return accept(data, now=now, policy=policy)


class _InflationBlindCapability(CapabilitySurface):
    """The capability-inflation vulnerability: verification re-signs the
    presented statement (structural validity treated as provenance)."""

    def verify(self, statement, credential, *, now) -> bool:
        from capabilities import sign_statement, verify_statement

        resigned = sign_statement(
            statement,
            store=self.identity.store,
            provider=self.identity.provider,
            credential=credential,
        )
        return verify_statement(
            resigned,
            store=self.identity.store,
            provider=self.identity.provider,
            credential=credential,
            now=now,
        )


class _RecomputingSessionSurface(SessionSurface):
    """The authority-boundary vulnerability: the harness re-computes a
    route when the authority rejects one (a second, shadow authority)."""

    def create(self, route, policy, *, source: str, destination: str,
               instant: str, intent_digest: str = "",
               extensions: tuple = ()):
        result = self.store.create(
            route, policy, source_node_id=source,
            destination_node_id=destination, creation_instant=instant,
            intent_digest=intent_digest, extensions=extensions,
        )
        if (not result.ok
                and result.code in ("route-not-selected", "route-tampered")):
            fresh = self.routing.decision(source, destination, instant)
            return self.store.create(
                fresh, policy, source_node_id=source,
                destination_node_id=destination, creation_instant=instant,
                intent_digest=intent_digest, extensions=extensions,
            )
        return result


class _RawRuntimeProxy:
    """The isolation vulnerability: allocation bypasses the sandbox and
    calls the raw implementation directly, so provider exceptions
    propagate out of the adapter layer."""

    def __init__(self, runtime, implementation, adapter_id: str) -> None:
        self._runtime = runtime
        self._implementation = implementation
        self.adapter_id = adapter_id

    def __getattr__(self, name: str):
        return getattr(self._runtime, name)

    def allocate(self, adapter_id: str, *, kind: str, quantity: int,
                 unit: str, purpose: str, now: str,
                 expires_at: Optional[str] = None):
        from adapters.contract import AdapterContext

        del kind, unit, expires_at
        context = AdapterContext(
            adapter_id, "access.generic.experimental", now, 10_000,
        )
        return self._implementation.allocate(
            context, kind="bandwidth", quantity_base=quantity,
            purpose=purpose,
        )


class _RawAdapterSurface(AdapterSurface):
    """Hands out runtimes whose allocate path bypasses the sandbox."""

    def runtime_with(self, implementation, *,
                     label: str = "conformance-x"):
        runtime, adapter_id = super().runtime_with(
            implementation, label=label,
        )
        return _RawRuntimeProxy(runtime, implementation, adapter_id), \
            adapter_id


class _DowngradeBlindTransport(TransportSurface):
    """The downgrade vulnerability: the initiator 'repairs' a forged
    offer-digest echo instead of comparing it (naive echo arithmetic)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._genuine_digest: Optional[str] = None

    def respond(self, offer, *, now: str = "2026-06-01T12:00:00Z",
                label: str = "pair"):
        manager, acceptance = super().respond(offer, now=now, label=label)
        self._genuine_digest = acceptance.offer_digest
        return manager, acceptance

    def complete_initiator(self, manager, handle, acceptance, *,
                           now: str = "2026-06-01T12:00:00Z"):
        import dataclasses

        if self._genuine_digest is not None:
            repaired = dataclasses.replace(
                acceptance, offer_digest=self._genuine_digest,
            )
            return super().complete_initiator(manager, handle, repaired,
                                              now=now)
        return super().complete_initiator(manager, handle, acceptance,
                                          now=now)


def _sabotage_case(number: int, name: str, vector_id: str,
                   build_world) -> Result:
    """One discriminating proof: genuine CONFORMANT -> sabotaged
    NONCONFORMANT -> genuine CONFORMANT again."""
    genuine_first = _run_one(vector_id, ConformanceWorld())
    world = build_world()
    sabotaged = _run_one(vector_id, world)
    genuine_again = _run_one(vector_id, ConformanceWorld())
    if genuine_first.verdict is not Verdict.CONFORMANT:
        return fail(name, "genuine world failed first: %s"
                    % genuine_first.reason_class)
    if sabotaged.verdict is not Verdict.CONFORMANT:
        if genuine_again.verdict is Verdict.CONFORMANT:
            return ok(
                name,
                "%s: genuine CONFORMANT -> sabotaged NONCONFORMANT "
                "(%s) -> genuine CONFORMANT restored"
                % (vector_id, sabotaged.reason_class),
            )
        return fail(name, "genuine world failed after sabotage: %s"
                    % genuine_again.reason_class)
    return fail(
        name,
        "%s stayed CONFORMANT against the sabotaged candidate -- the "
        "suite is NOT discriminating here" % vector_id,
    )


# ---------------------------------------------------------------------------
# Audit discrimination fixtures
# ---------------------------------------------------------------------------


def _with_fixture_sources(files: dict, run_audit) -> Tuple[List[str], List[str]]:
    """Run an audit over sabotaged fixture sources; returns (findings,
    clean_findings)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bad_dir = root / "bad"
        good_dir = root / "good"
        bad_dir.mkdir()
        good_dir.mkdir()
        for relative, source in files["bad"].items():
            path = bad_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        for relative, source in files["good"].items():
            path = good_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        return run_audit(bad_dir), run_audit(good_dir)


# ---------------------------------------------------------------------------
# The cases
# ---------------------------------------------------------------------------


def case_11_full_matrix(results: List[Result]) -> None:
    """11. the full matrix is CONFORMANT with both polarities."""
    report = _matrix()
    if report.verdict is Verdict.CONFORMANT:
        results.append(ok(
            "case_11_full_matrix",
            "%d/%d vectors conformant (%d positive / %d negative)"
            % (report.conformant, report.total, report.positive_count,
               report.negative_count),
        ))
    else:
        bad = report.nonconformant_results()
        results.append(fail(
            "case_11_full_matrix",
            "nonconformant: %s" % "; ".join(
                "%s (%s)" % (r.vector_id, r.reason_class) for r in bad[:5]
            ),
        ))


def case_12_digest_stable(results: List[Result]) -> None:
    """12. the report digest is stable across in-process runs."""
    first = report_digest(_matrix())
    second = report_digest(_matrix())
    if first == second:
        results.append(ok("case_12_digest_stable", first))
    else:
        results.append(fail(
            "case_12_digest_stable", "%s != %s" % (first, second)
        ))


def case_13_registry_duplicate_id(results: List[Result]) -> None:
    """13. duplicate vector ids fail closed."""
    registry = build_default_registry()
    vector = registry.canonical_vectors()[0]
    try:
        registry.register(vector)
        results.append(fail(
            "case_13_registry_duplicate_id", "duplicate accepted"
        ))
    except RegistryError:
        results.append(ok(
            "case_13_registry_duplicate_id", "duplicate id rejected"
        ))


def case_14_registry_unknown_tag(results: List[Result]) -> None:
    """14. tags outside the frozen vocabulary fail closed."""
    registry = build_default_registry()
    vector = registry.canonical_vectors()[0]
    import dataclasses

    mutated = dataclasses.replace(
        vector, vector_id="W032-CNF-STR-999",
        tags=frozenset({"negative:not-a-known-tag"}),
    )
    try:
        registry.register(mutated)
        results.append(fail(
            "case_14_registry_unknown_tag", "unknown tag accepted"
        ))
    except RegistryError:
        results.append(ok(
            "case_14_registry_unknown_tag", "unknown tag rejected"
        ))


def case_15_registry_wrong_authority(results: List[Result]) -> None:
    """15. a vector attributing its area to the wrong authority fails."""
    registry = build_default_registry()
    vector = registry.canonical_vectors()[0]
    import dataclasses

    mutated = dataclasses.replace(
        vector, vector_id="W032-CNF-STR-998", authority="WORK-099",
    )
    try:
        registry.register(mutated)
        results.append(fail(
            "case_15_registry_wrong_authority", "wrong authority accepted"
        ))
    except RegistryError:
        results.append(ok(
            "case_15_registry_wrong_authority", "wrong authority rejected"
        ))


def case_16_registry_order_independent(results: List[Result]) -> None:
    """16. registration order never affects canonical order or results."""
    forward = build_default_registry()
    reverse = build_default_registry()
    vectors = list(forward.canonical_vectors())
    reverse_registry = type(forward)()
    reverse_registry.register_all(reversed(vectors))
    if (forward.vector_ids() == reverse_registry.vector_ids()
            and list(forward.vector_ids()) == sorted(forward.vector_ids())):
        digest_forward = report_digest(run_matrix(
            forward.canonical_vectors(), ConformanceWorld,
        ))
        digest_reverse = report_digest(run_matrix(
            reverse_registry.canonical_vectors(), ConformanceWorld,
        ))
        if digest_forward == digest_reverse:
            results.append(ok(
                "case_16_registry_order_independent",
                "reversed registration: identical order and digest",
            ))
            return
    results.append(fail(
        "case_16_registry_order_independent",
        "registration order influenced the canonical order or digest",
    ))


_CHILD_SCRIPT = (
    "import sys; sys.path.insert(0, %r); "
    "from conformance import build_default_registry, run_matrix, "
    "ConformanceWorld, report_digest; "
    "r = build_default_registry(); "
    "print(report_digest(run_matrix(r.canonical_vectors(), "
    "ConformanceWorld)))" % str(REPO_ROOT)
)


def _child_digest(seed: Optional[int]) -> Optional[str]:
    env = dict(os.environ)
    if seed is not None:
        env["PYTHONHASHSEED"] = str(seed)
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_SCRIPT],
        capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        env=env,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def case_17_determinism_subprocess(results: List[Result]) -> None:
    """17. the matrix digest is identical in a fresh subprocess."""
    in_process = report_digest(_matrix())
    child = _child_digest(None)
    if child == in_process:
        results.append(ok(
            "case_17_determinism_subprocess", "digest %s" % child[:22]
        ))
    else:
        results.append(fail(
            "case_17_determinism_subprocess",
            "in-process %r vs child %r" % (in_process[:22],
                                           (child or "ERROR")[:22]),
        ))


def case_18_determinism_hash_seeds(results: List[Result]) -> None:
    """18. the digest is identical across hash seeds 0/1/7919."""
    digests = [_child_digest(seed) for seed in (0, 1, 7919)]
    if None in digests:
        results.append(fail(
            "case_18_determinism_hash_seeds", "a child run failed"
        ))
        return
    if len(set(digests)) == 1:
        results.append(ok(
            "case_18_determinism_hash_seeds",
            "identical digest across seeds 0/1/7919",
        ))
    else:
        results.append(fail(
            "case_18_determinism_hash_seeds",
            "digests differ: %s" % [d[:16] for d in digests],
        ))


def case_19_serialization_roundtrip(results: List[Result]) -> None:
    """19. reports round-trip byte-identically through canonical JSON."""
    from conformance import report_to_dict

    report = _matrix()
    data = report_to_dict(report)
    restored = report_from_mapping(data)
    if report_canonical_bytes(restored) == report_canonical_bytes(report):
        results.append(ok(
            "case_19_serialization_roundtrip",
            "canonical bytes byte-identical after round-trip",
        ))
    else:
        results.append(fail(
            "case_19_serialization_roundtrip",
            "canonical bytes changed across the round-trip",
        ))


def case_20_coverage_areas(results: List[Result]) -> None:
    """20. every required matrix area is covered."""
    registry = build_default_registry()
    present = set(registry.areas())
    missing = [a for a in REQUIRED_AREAS if a not in present]
    if missing:
        results.append(fail(
            "case_20_coverage_areas", "missing areas: %s" % missing
        ))
    else:
        results.append(ok(
            "case_20_coverage_areas",
            "all %d areas covered: %s" % (
                len(REQUIRED_AREAS), registry.counts_by_area(),
            ),
        ))


def _tag_coverage_case(name: str, required: Tuple[str, ...],
                       results: List[Result]) -> None:
    registry = build_default_registry()
    covered = set(registry.tags())
    missing = [t for t in required if t not in covered]
    if missing:
        results.append(fail(name, "missing tags: %s" % missing))
    else:
        results.append(ok(
            name, "all %d required tags covered" % len(required),
        ))


def case_21_coverage_negative_tags(results: List[Result]) -> None:
    """21. every required negative/security category is covered."""
    _tag_coverage_case(
        "case_21_coverage_negative_tags", REQUIRED_NEGATIVE_TAGS, results,
    )


def case_22_coverage_recovery_tags(results: List[Result]) -> None:
    """22. every required failure/recovery category is covered."""
    _tag_coverage_case(
        "case_22_coverage_recovery_tags", REQUIRED_RECOVERY_TAGS, results,
    )


def case_23_coverage_discrimination_tags(results: List[Result]) -> None:
    """23. every required discrimination area is tagged."""
    _tag_coverage_case(
        "case_23_coverage_discrimination_tags",
        REQUIRED_DISCRIMINATION_TAGS, results,
    )


def case_24_polarity_balance(results: List[Result]) -> None:
    """24. every area carries both positive and negative vectors."""
    report = _matrix()
    problems = []
    for area in report.areas():
        subset = report.results_for_area(area)
        positives = [r for r in subset if r.polarity == "positive"]
        negatives = [r for r in subset if r.polarity == "negative"]
        if not positives or not negatives:
            problems.append(
                "%s (pos=%d neg=%d)" % (area, len(positives), len(negatives))
            )
    if problems:
        results.append(fail(
            "case_24_polarity_balance", "unbalanced areas: %s" % problems
        ))
    else:
        results.append(ok(
            "case_24_polarity_balance",
            "every area has both polarities (total %d positive / %d "
            "negative)" % (report.positive_count, report.negative_count),
        ))


def case_25_dependency_attribution(results: List[Result]) -> None:
    """25. every declared dependency authority is attributed."""
    from conformance.model import AREA_AUTHORITY

    report = _matrix()
    attributed = {r.authority for r in report.results}
    expected = {
        authority for area, authority in AREA_AUTHORITY.items()
        if area != "structure"
    }
    missing = sorted(expected - attributed)
    empty = [r.vector_id for r in report.results if not r.authority]
    if missing or empty:
        results.append(fail(
            "case_25_dependency_attribution",
            "missing %s; empty %s" % (missing, empty[:3]),
        ))
    else:
        results.append(ok(
            "case_25_dependency_attribution",
            "all nine declared dependencies attributed "
            "(%s)" % ", ".join(sorted(expected)),
        ))


def case_26_evidence_three_classes(results: List[Result]) -> None:
    """26. the evidence report separates the three evidence classes."""
    evidence = build_evidence_report(_matrix())
    sections = set(evidence.keys())
    expected = {
        "architecture_conformance", "automated_verification",
        "external_evidence",
    }
    external = evidence["external_evidence"]
    if (sections == expected
            and external["records"] == []
            and "No external interoperability evidence" in
            external["statement"]):
        results.append(ok(
            "case_26_evidence_three_classes",
            "three distinct sections; external evidence explicitly none",
        ))
    else:
        results.append(fail(
            "case_26_evidence_three_classes",
            "sections %r; external %r" % (sorted(sections),
                                          external["records"][:1]),
        ))


def case_27_external_evidence_explicit_only(results: List[Result]) -> None:
    """27. external evidence attaches only explicitly (operator side)."""
    report = _matrix()
    automated_before = build_evidence_report(report)["automated_verification"]
    evidence = build_evidence_report(report, external=(
        ExternalEvidenceRecord(
            source="operator-side lab", scope="external interop",
            description="explicitly supplied record",
        ),
    ))
    external = evidence["external_evidence"]
    automated = evidence["automated_verification"]
    if (len(external["records"]) == 1
            and automated == automated_before
            and "operator-supplied" in external["statement"]):
        results.append(ok(
            "case_27_external_evidence_explicit_only",
            "explicit record attached; automated verification unchanged",
        ))
    else:
        results.append(fail(
            "case_27_external_evidence_explicit_only",
            "external %r; automated changed=%s"
            % (external["records"], automated != automated_before),
        ))


def case_28_no_external_claim(results: List[Result]) -> None:
    """28. no automated result claims external evidence (guard)."""
    try:
        assert_no_external_claim(_matrix())
        results.append(ok(
            "case_28_no_external_claim",
            "automated verification never claims external evidence",
        ))
    except ValueError as error:
        results.append(fail("case_28_no_external_claim", str(error)))


def case_29_no_secret_diagnostics(results: List[Result]) -> None:
    """29. diagnostics carry no fixture secret material."""
    material = report_canonical_bytes(_matrix())
    secrets = (b"identity-role-secret-A", b"op-secret-")
    leaked = [s for s in secrets if s in material]
    if leaked:
        results.append(fail(
            "case_29_no_secret_diagnostics",
            "secret material leaked: %r" % leaked,
        ))
    else:
        results.append(ok(
            "case_29_no_secret_diagnostics",
            "no fixture secret bytes in the canonical report",
        ))


def case_30_reason_vocabulary(results: List[Result]) -> None:
    """30. reason classes stay within the frozen vocabulary."""
    report = _matrix()
    observed = {r.reason_class for r in report.results}
    outside = observed - REASON_VALUES
    if outside:
        results.append(fail(
            "case_30_reason_vocabulary", "unknown classes: %s" % outside
        ))
    else:
        results.append(ok(
            "case_30_reason_vocabulary",
            "reason classes within the frozen vocabulary (%s)"
            % sorted(observed),
        ))


def case_31_harness_comparison_discriminating(results: List[Result]) -> None:
    """31. the harness comparison itself is discriminating: an inverted
    expectation against the genuine world is detected as
    nonconformance."""
    vector = _vector_by_id("W032-CNF-ENV-001")
    import dataclasses

    inverted = dataclasses.replace(
        vector,
        expected=ExpectedOutcome(
            accepted=not vector.expected.accepted,
            result_classes=vector.expected.result_classes,
        ),
    )
    result = run_vector(inverted, ConformanceWorld())
    if result.verdict is Verdict.NONCONFORMANT:
        results.append(ok(
            "case_31_harness_comparison_discriminating",
            "inverted expectation detected (%s)" % result.reason_class,
        ))
    else:
        results.append(fail(
            "case_31_harness_comparison_discriminating",
            "inverted expectation was NOT detected",
        ))


def case_32_sabotage_provenance(results: List[Result]) -> None:
    """32. discriminating: provenance collapse is detected."""
    results.append(_sabotage_case(
        32, "case_32_sabotage_provenance", "W032-CNF-TOP-002",
        lambda: _world_with(topology=_ProvenanceSabotagedTopology()),
    ))


def case_33_sabotage_replay(results: List[Result]) -> None:
    """33. discriminating: replay blindness is detected."""
    results.append(_sabotage_case(
        33, "case_33_sabotage_replay", "W032-CNF-ENV-010",
        lambda: _world_with(envelope=_ReplayBlindEnvelope()),
    ))


def case_34_sabotage_downgrade(results: List[Result]) -> None:
    """34. discriminating: downgrade blindness is detected."""
    results.append(_sabotage_case(
        34, "case_34_sabotage_downgrade", "W032-CNF-TRA-005",
        lambda: _world_with(transport=_DowngradeBlindTransport(
            _world().identity, _world().session.store,
            _world().established_session_id,
        )),
    ))


def case_35_sabotage_capability_inflation(results: List[Result]) -> None:
    """35. discriminating: capability inflation is detected."""
    results.append(_sabotage_case(
        35, "case_35_sabotage_capability_inflation",
        "W032-CNF-CAP-003",
        lambda: _world_with(
            capability=_InflationBlindCapability(_world().identity),
        ),
    ))


def case_36_sabotage_authority_boundary(results: List[Result]) -> None:
    """36. discriminating: a shadow route authority is detected."""
    results.append(_sabotage_case(
        36, "case_36_sabotage_authority_boundary", "W032-CNF-SES-003",
        lambda: _world_with(session=_RecomputingSessionSurface(
            _world().routing,
        )),
    ))


def case_37_sabotage_adapter_isolation(results: List[Result]) -> None:
    """37. discriminating: sandbox bypass (exception propagation) is
    detected."""
    results.append(_sabotage_case(
        37, "case_37_sabotage_adapter_isolation", "W032-CNF-ADP-005",
        lambda: _world_with(adapter=_RawAdapterSurface(
            _world().session.store, _world().established_session_id,
        )),
    ))


def case_38_audit_forbidden_dependency(results: List[Result]) -> None:
    """38. the import audit detects a smuggled forbidden dependency."""
    bad, good = _with_fixture_sources(
        {
            "bad": {
                "vectors/smuggled.py": (
                    "import multipath\n"
                    "from telemetry import TelemetryStore\n"
                ),
            },
            "good": {
                "vectors/clean.py": (
                    "from protocol import accept\n"
                    "from sessions import SessionStore\n"
                ),
            },
        },
        find_import_violations,
    )
    if bad and not good:
        results.append(ok(
            "case_38_audit_forbidden_dependency",
            "smuggled multipath/telemetry imports detected: %s" % bad[0],
        ))
    else:
        results.append(fail(
            "case_38_audit_forbidden_dependency",
            "bad=%r good=%r" % (bad[:2], good[:2]),
        ))


def case_39_audit_vendor_tokens(results: List[Result]) -> None:
    """39. the vendor scan detects vendor tokens."""
    bad, good = _with_fixture_sources(
        {
            "bad": {"provider.py": "import open5gs\n"},
            "good": {"provider.py": "import json\n"},
        },
        find_vendor_tokens,
    )
    if bad and not good:
        results.append(ok(
            "case_39_audit_vendor_tokens",
            "vendor import detected: %s" % bad[0],
        ))
    else:
        results.append(fail(
            "case_39_audit_vendor_tokens",
            "bad=%r good=%r" % (bad[:2], good[:2]),
        ))


def case_40_audit_nondeterminism(results: List[Result]) -> None:
    """40. the determinism scan detects wall clock and randomness."""
    bad, good = _with_fixture_sources(
        {
            "bad": {
                "clock.py": (
                    "import random\n"
                    "import time\n"
                    "value = time.time()\n"
                ),
            },
            "good": {"clock.py": "value = 1\n"},
        },
        find_nondeterminism,
    )
    if bad and not good:
        results.append(ok(
            "case_40_audit_nondeterminism",
            "wall clock / randomness detected: %s" % bad[0],
        ))
    else:
        results.append(fail(
            "case_40_audit_nondeterminism",
            "bad=%r good=%r" % (bad[:2], good[:2]),
        ))


def case_41_audit_private_access(results: List[Result]) -> None:
    """41. the private-access scan detects hidden authority access."""
    bad, good = _with_fixture_sources(
        {
            "bad": {
                "sneaky.py": (
                    "def poke(store):\n"
                    "    return store._sessions\n"
                ),
            },
            "good": {
                "clean.py": (
                    "def read(store, sid):\n"
                    "    return store.get(sid)\n"
                ),
            },
        },
        find_private_access,
    )
    if bad and not good:
        results.append(ok(
            "case_41_audit_private_access",
            "private authority access detected: %s" % bad[0],
        ))
    else:
        results.append(fail(
            "case_41_audit_private_access",
            "bad=%r good=%r" % (bad[:2], good[:2]),
        ))


def case_42_audit_shadow_authority(results: List[Result]) -> None:
    """42. the shadow-authority scan detects authority subclassing."""
    bad, good = _with_fixture_sources(
        {
            "bad": {
                "shadow.py": (
                    "from sessions import SessionStore\n"
                    "from topology import TopologyGraph\n"
                    "class MyStore(SessionStore):\n"
                    "    pass\n"
                    "class MyGraph(TopologyGraph):\n"
                    "    pass\n"
                ),
            },
            "good": {
                "clean.py": (
                    "from adapters.contract import AdapterContract\n"
                    "class Impl(AdapterContract):\n"
                    "    pass\n"
                ),
            },
        },
        find_shadow_authority,
    )
    if bad and not good:
        results.append(ok(
            "case_42_audit_shadow_authority",
            "authority subclassing detected: %s" % bad[0],
        ))
    else:
        results.append(fail(
            "case_42_audit_shadow_authority",
            "bad=%r good=%r" % (bad[:2], good[:2]),
        ))


def case_43_py_compile(results: List[Result]) -> None:
    """43. the conformance family compiles clean."""
    for path in _FAMILY_FILES:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            results.append(fail(
                "case_43_py_compile",
                "%s does not compile: %s" % (path.name, error),
            ))
            return
    results.append(ok(
        "case_43_py_compile",
        "%d files compile clean" % len(_FAMILY_FILES),
    ))


def case_44_ci_wiring(results: List[Result]) -> None:
    """44. CI wired: the conformance battery + all 32 prior tools."""
    workflow_path = REPO_ROOT / ".github" / "workflows" / "spec-check.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    if "python3 tools/conformance_selftest.py" not in workflow:
        results.append(fail(
            "case_44_ci_wiring", "conformance battery not wired into CI"
        ))
        return
    missing = [
        tool for tool in _EXPECTED_TOOLS
        if ("tools/%s" % tool) not in workflow
    ]
    if missing:
        results.append(fail(
            "case_44_ci_wiring", "batteries missing from CI: %s" % missing
        ))
    else:
        results.append(ok(
            "case_44_ci_wiring",
            "CI wired: conformance battery + all %d prior tools"
            % (len(_EXPECTED_TOOLS) - 1),
        ))


def case_45_frozen_spec_intact(results: List[Result]) -> None:
    """45. frozen surfaces: spec/ clean and CI wiring additive (context
    aware: PR delta on branches; committed wiring on main; clean spec/
    when the origin/main ref is unavailable)."""
    name = "case_45_frozen_spec_intact"
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "spec/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if status.stdout.strip():
        results.append(fail(
            name, "uncommitted spec/ changes: %s" % status.stdout.strip()
        ))
        return
    workflow_path = REPO_ROOT / ".github" / "workflows" / "spec-check.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    ref_check = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if ref_check.returncode != 0:
        # Degraded context (no origin/main ref): the working tree must be
        # clean over spec/ and the committed wiring must be present.
        if "python3 tools/conformance_selftest.py" in workflow:
            results.append(ok(
                name,
                "spec/ clean; committed CI wiring present "
                "(origin/main ref unavailable)",
            ))
        else:
            results.append(fail(
                name, "committed CI wiring missing"
            ))
        return
    delta = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    changed = {line for line in delta.stdout.splitlines() if line.strip()}
    if not changed:
        # MAIN context: HEAD == origin/main; verify committed wiring
        # directly (a PR-delta assertion cannot exist here).
        if "python3 tools/conformance_selftest.py" in workflow:
            results.append(ok(
                name,
                "spec/ clean on main; committed CI wiring verified directly",
            ))
        else:
            results.append(fail(name, "committed CI wiring missing on main"))
        return
    # PR/branch context: the delta must be exactly the sanctioned shape.
    spec_changed = [c for c in changed if c.startswith("spec/")]
    if spec_changed:
        results.append(fail(
            name, "spec/ differs from origin/main: %s" % spec_changed
        ))
        return
    allowed_docs = {"docs/WORK-032-handoff.md"}
    docs_changed = {c for c in changed if c.startswith("docs/")}
    if not docs_changed <= allowed_docs:
        results.append(fail(
            name, "docs/ changes beyond the handoff: %s" % docs_changed
        ))
        return
    workflow_delta = subprocess.run(
        ["git", "diff", "origin/main", "--", ".github/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if "conformance_selftest.py" not in workflow_delta.stdout:
        results.append(fail(
            name, ".github delta does not include the conformance CI step"
        ))
        return
    tools_changed = {c for c in changed if c.startswith("tools/")}
    allowed_tools = {"tools/conformance_selftest.py"}
    if not tools_changed <= allowed_tools:
        results.append(fail(
            name, "tools/ changes beyond the battery: %s" % tools_changed
        ))
        return
    results.append(ok(
        name,
        "spec/ byte-identical to origin/main; docs/ = the W032 handoff; "
        "CI step additive; tools/ = the battery only",
    ))


def case_46_api_surface_frozen(results: List[Result]) -> None:
    """46. the public API surface is exactly the frozen export set."""
    import conformance

    actual = set(vars(conformance).keys())
    missing = API_SURFACE - actual
    unexpected_public = {
        name for name in actual
        if not name.startswith("_") and name not in API_SURFACE
        and callable(getattr(conformance, name, None))
    }
    if missing or unexpected_public:
        results.append(fail(
            "case_46_api_surface_frozen",
            "missing %s; unexpected %s" % (sorted(missing),
                                           sorted(unexpected_public)),
        ))
    else:
        results.append(ok(
            "case_46_api_surface_frozen",
            "public API surface frozen at %d symbols" % len(API_SURFACE),
        ))


# ---------------------------------------------------------------------------
# World-with helpers
# ---------------------------------------------------------------------------


def _world() -> ConformanceWorld:
    return ConformanceWorld()


def _world_with(*, topology=None, envelope=None, capability=None,
                session=None, adapter=None, transport=None) -> ConformanceWorld:
    world = ConformanceWorld()
    if topology is not None:
        world.topology = topology
    if envelope is not None:
        world.envelope = envelope
    if capability is not None:
        world.capability = capability
    if session is not None:
        world.session = session
    if adapter is not None:
        world.adapter = adapter
    if transport is not None:
        world.transport = transport
    return world


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    results: List[Result] = []

    # 1-10: per-area matrix runs.
    for area in REQUIRED_AREAS:
        results.append(_area_case(area))

    case_11_full_matrix(results)
    case_12_digest_stable(results)
    case_13_registry_duplicate_id(results)
    case_14_registry_unknown_tag(results)
    case_15_registry_wrong_authority(results)
    case_16_registry_order_independent(results)
    case_17_determinism_subprocess(results)
    case_18_determinism_hash_seeds(results)
    case_19_serialization_roundtrip(results)
    case_20_coverage_areas(results)
    case_21_coverage_negative_tags(results)
    case_22_coverage_recovery_tags(results)
    case_23_coverage_discrimination_tags(results)
    case_24_polarity_balance(results)
    case_25_dependency_attribution(results)
    case_26_evidence_three_classes(results)
    case_27_external_evidence_explicit_only(results)
    case_28_no_external_claim(results)
    case_29_no_secret_diagnostics(results)
    case_30_reason_vocabulary(results)
    case_31_harness_comparison_discriminating(results)
    case_32_sabotage_provenance(results)
    case_33_sabotage_replay(results)
    case_34_sabotage_downgrade(results)
    case_35_sabotage_capability_inflation(results)
    case_36_sabotage_authority_boundary(results)
    case_37_sabotage_adapter_isolation(results)
    case_38_audit_forbidden_dependency(results)
    case_39_audit_vendor_tokens(results)
    case_40_audit_nondeterminism(results)
    case_41_audit_private_access(results)
    case_42_audit_shadow_authority(results)
    case_43_py_compile(results)
    case_44_ci_wiring(results)
    case_45_frozen_spec_intact(results)
    case_46_api_surface_frozen(results)

    failures = [r for r in results if not r[1]]
    for name, passed, detail in results:
        print("[%s] %-55s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 72)
    if failures:
        print("Result: FAIL (%d/%d cases failed)" % (
            len(failures), len(results),
        ))
        for name, _, detail in failures:
            print("  - %s" % name)
        return 1
    print("Result: PASS (%d/%d cases passed)" % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
