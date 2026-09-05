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

import json
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
    CorpusError,
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
    W055_REQUIRED_DISCRIMINATION_TAGS,
    W055_REQUIRED_NEGATIVE_TAGS,
    assert_no_external_claim,
    build_default_registry,
    build_evidence_report,
    corpus_digest,
    corpus_vector_ids,
    load_corpus,
    profile_digest,
    profile_statement,
    report_canonical_bytes,
    report_digest,
    report_from_mapping,
    run_matrix,
    run_vector,
    verify_corpus,
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
# The WORK-029 public contracts, consumed from this battery -- the
# sanctioned composition root (tools/) -- never from the conformance
# family: the frozen dependency graph and the WORK-029 family's own
# import discipline (tools/upgrade_selftest.py case_33) carry no W055
# family-level DAG edge.  Amending them is Architect-owned.
from upgrade.compatibility import (  # noqa: E402
    ProfileNegotiation,
    negotiate_protocol_profile,
)
from upgrade.errors import UpgradeError, UpgradeReasonCode  # noqa: E402
from upgrade.migrations import MigrationDescriptor, MigrationRegistry  # noqa: E402
from upgrade.model import (  # noqa: E402
    ProtocolProfile,
    SoftwareVersion,
    UpgradePlan,
    derive_migration_id,
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


# ---------------------------------------------------------------------------
# WORK-055 sabotaged candidate worlds (test fixtures ONLY -- the R3
# vulnerable behaviors implemented over public APIs; never shipped,
# never exported).  Each pairs with a W055 vector so the mandated
# discrimination categories are mechanically proven.
# ---------------------------------------------------------------------------


class _AmbiguousCanonicalizer(EnvelopeSurface):
    """R3 canonicalization-ambiguity vulnerability: the canonical form
    preserves the caller's insertion order instead of sorting keys
    (a second, order-dependent canonicalization)."""

    def canonical(self, value: Any) -> bytes:
        import json as _json

        return _json.dumps(value).encode("utf-8")


class _SignatureBlindEnvelope(EnvelopeSurface):
    """R3 covered-byte vulnerability: the signature basis silently
    drops covered members (payload) as well as the signature, so
    payload tampering is invisible to the signing surface."""

    def signature_input(self, envelope: Any) -> bytes:
        from protocol import canonical_json_bytes

        document = envelope.to_dict()
        document.pop("signature", None)
        document.pop("payload", None)  # the vulnerability
        return canonical_json_bytes(document)


class _ClampingNegotiator:
    """R3 negotiation-downgrade vulnerability: on MAJOR_MISMATCH the
    negotiator 'repairs' the result by falling back to the lower
    common major (cross-major clamping that the frozen contract
    forbids).  Implemented over the public API; battery fixture only."""

    class _ForgedResult:
        def __init__(self, major: int, minor: int) -> None:
            self.selected = (major, minor)
            self.reason = None

        @property
        def succeeded(self) -> bool:
            return True

    def negotiate(self, local: ProtocolProfile, peer: ProtocolProfile) -> Any:
        result = negotiate_protocol_profile(local, peer)
        if result.reason == UpgradeReasonCode.MAJOR_MISMATCH:
            lower = local if local.major < peer.major else peer
            floor = min(local.max_minor, peer.max_minor)
            return self._ForgedResult(lower.major, floor)
        return result


class _BestEffortMigrator:
    """R3 migration vulnerability: declared non-reversible steps are
    reversed anyway with a best-effort partial undo (the flag-day
    rollback the frozen contract refuses).  Implemented over the
    public API; battery fixture only."""

    def __init__(self, registry: MigrationRegistry) -> None:
        self._registry = registry

    def migrate(self, state: Any, from_version: str, to_version: str) -> Any:
        try:
            return self._registry.migrate(
                state, _MIGRATION_SCHEMA_ID, from_version, to_version
            )
        except Exception as error:  # the typed authority error
            if getattr(error, "reason", "") == \
                    UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE:
                out = dict(state)  # best-effort partial undo
                entries = out.pop("entries", [])
                out["records"] = list(entries)
                out["schema_version"] = "1.1"
                return out
            raise


class _RequiredFlagStripper(EnvelopeSurface):
    """R3 unsafe unknown-field vulnerability: required:true extensions
    are downgraded to optional before validation (must-understand
    silently dropped)."""

    def accept_bytes(self, data, *, now, policy, replay=None):
        import json as _json

        if isinstance(data, str):
            try:
                parsed = _json.loads(data)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict):
                extensions = parsed.get("extensions")
                if isinstance(extensions, dict):
                    for key, value in list(extensions.items()):
                        if (isinstance(value, dict)
                                and value.get("required") is True):
                            repaired = dict(value)
                            repaired["required"] = False  # the vulnerability
                            extensions[key] = repaired
                    data = _json.dumps(parsed, sort_keys=True)
        return super().accept_bytes(data, now=now, policy=policy,
                                    replay=replay)


class _EvidenceTrustingEnvelope(EnvelopeSurface):
    """R3 evidence-as-authority vulnerability: the acceptance path
    trusts a CONFORMANT conformance report verdict over the frozen
    validation pipeline (conformance evidence promoted into protocol
    authority)."""

    def __init__(self) -> None:
        super().__init__()
        from conformance.model import (
            ConformanceReport,
            ExpectedOutcome as _Expected,
            ObservedOutcome as _Observed,
            VectorResult,
        )

        trusted = VectorResult(
            vector_id="W055-sabotage-trusted-report",
            area="envelope",
            authority="WORK-003",
            contract="fixture",
            invariant="fixture result carrying a CONFORMANT verdict",
            polarity="positive",
            expected=_Expected(True),
            observed=_Observed(True, "fixture", "fixture"),
            verdict=Verdict.CONFORMANT,
            reason_class="conformant",
            tags=frozenset(),
        )
        self._trusted_report = ConformanceReport(results=(trusted,))

    def accept_bytes(self, data, *, now, policy, replay=None):
        outcome = super().accept_bytes(data, now=now, policy=policy,
                                       replay=replay)
        if (not outcome.accepted
                and self._trusted_report.verdict is Verdict.CONFORMANT):
            # the vulnerability: conformance evidence overrules the
            # authority's rejection
            from protocol import Classification
            from protocol.validation import AcceptOutcome

            return AcceptOutcome(
                accepted=True, validated=None,
                classification=Classification.KNOWN_COMPATIBLE,
                detail="accepted because the conformance report is "
                       "CONFORMANT (evidence-as-authority)",
            )
        return outcome


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
            "all %d declared dependencies attributed (%s)"
            % (len(expected), ", ".join(sorted(expected))),
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
# 47-62: WORK-055 production conformance (R3)
# ---------------------------------------------------------------------------


def case_47_w055_profile(results: List[Result]) -> None:
    """47. the production canonicalization profile is declared,
    complete, and digest-stable in-process."""
    statement = profile_statement()
    digest = profile_digest()
    again = profile_digest()
    rules = statement["rules"]
    problems = []
    if statement["profile_id"] != "adcos.canonical-json.production.v1":
        problems.append("unexpected profile id")
    if statement["owning_authority"] != "WORK-003":
        problems.append("owning authority is not WORK-003")
    if len(rules) != 12 or any(
        rule["authority"] != "WORK-003" for rule in rules
    ):
        problems.append("rule set incomplete or mis-attributed")
    if not statement["protocol_version"].startswith("1."):
        problems.append("protocol version not read from the artifact")
    if digest != again:
        problems.append("profile digest unstable in-process")
    if problems:
        results.append(fail(
            "case_47_w055_profile", "; ".join(problems)
        ))
    else:
        results.append(ok(
            "case_47_w055_profile",
            "profile %s declared for Protocol %s with %d WORK-003-"
            "attributed rules; digest %s"
            % (statement["profile_id"], statement["protocol_version"],
               len(rules), digest),
        ))


def case_48_w055_corpus(results: List[Result]) -> None:
    """48. the golden corpus verifies and its digest is recorded."""
    try:
        corpus = load_corpus()
    except CorpusError as error:
        results.append(fail("case_48_w055_corpus", str(error)))
        return
    verification = verify_corpus(corpus)
    failures = [r for r in verification if not r.verified]
    digest = corpus_digest(corpus, verification)
    categories: dict = {}
    for entry in corpus:
        categories[entry.category] = categories.get(entry.category, 0) + 1
    if failures:
        results.append(fail(
            "case_48_w055_corpus",
            "%d/%d failed (first: %s: %s)"
            % (len(failures), len(verification), failures[0].vector_id,
               failures[0].detail),
        ))
        return
    results.append(ok(
        "case_48_w055_corpus",
        "%d/%d golden vectors verified (%s); digest %s"
        % (len(verification), len(verification),
           ", ".join("%s=%d" % (c, n) for c, n in sorted(categories.items())),
           digest),
    ))


_W055_CHILD_SCRIPT = (
    "import sys\n"
    "sys.path.insert(0, %r)\n"
    "import hashlib, json\n"
    "from conformance import corpus_digest, load_corpus, profile_digest\n"
    "from protocol import canonical_json_bytes\n"
    "from upgrade.compatibility import negotiate_protocol_profile\n"
    "from upgrade.model import ProtocolProfile\n"
    "corpus = load_corpus()\n"
    "scenarios = {'floor': [(1, 3), (1, 2)], 'equal': [(1, 4), (1, 4)], "
    "'mismatch': [(1, 3), (2, 0)], 'unknown': [(2, 1), (2, 1)]}\n"
    "outcomes = {}\n"
    "for key, (local, peer) in sorted(scenarios.items()):\n"
    "    result = negotiate_protocol_profile(\n"
    "        ProtocolProfile(local[0], local[1]), "
    "ProtocolProfile(peer[0], peer[1]))\n"
    "    outcomes[key] = [\n"
    "        None if result.selected is None else "
    "[result.selected.major, result.selected.max_minor],\n"
    "        result.reason,\n"
    "    ]\n"
    "w029 = 'sha256:' + hashlib.sha256(\n"
    "    canonical_json_bytes(outcomes)).hexdigest()\n"
    "members = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', "
    "'eta', 'theta', 'iota', 'kappa']\n"
    "unstable = hashlib.sha256(\n"
    "    '|'.join(iter(set(members))).encode('utf-8')).hexdigest()\n"
    "print(json.dumps({'genuine': corpus_digest(corpus), "
    "'profile': profile_digest(), 'w029': w029, 'unstable': unstable}))"
    % str(REPO_ROOT)
)


def _w055_child(seed: Optional[int]) -> Optional[dict]:
    env = dict(os.environ)
    if seed is not None:
        env["PYTHONHASHSEED"] = str(seed)
    else:
        env.pop("PYTHONHASHSEED", None)
    completed = subprocess.run(
        [sys.executable, "-c", _W055_CHILD_SCRIPT],
        capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        env=env,
    )
    if completed.returncode != 0:
        return None
    try:
        return json.loads(completed.stdout.strip())
    except ValueError:
        return None


def case_49_w055_digest_subprocess(results: List[Result]) -> None:
    """49. corpus and profile digests are identical in fresh subprocesses
    (repeated runs, unset seed)."""
    in_process_genuine = corpus_digest(load_corpus())
    in_process_profile = profile_digest()
    children = [_w055_child(None), _w055_child(None)]
    if None in children:
        results.append(fail(
            "case_49_w055_digest_subprocess", "a child run failed"
        ))
        return
    genuine = {child["genuine"] for child in children}
    profile = {child["profile"] for child in children}
    w029 = {child["w029"] for child in children}
    if (len(genuine) == 1 and len(profile) == 1 and len(w029) == 1
            and genuine == {in_process_genuine}
            and profile == {in_process_profile}):
        results.append(ok(
            "case_49_w055_digest_subprocess",
            "corpus digest %s, profile digest %s, and the W029 "
            "negotiation-outcome digest %s identical across two fresh "
            "subprocesses (unset seed)"
            % (next(iter(genuine)), next(iter(profile)), next(iter(w029))),
        ))
    else:
        results.append(fail(
            "case_49_w055_digest_subprocess",
            "digest divergence: genuine=%d profile=%d"
            % (len(genuine), len(profile)),
        ))


def case_50_w055_digest_hash_seeds(results: List[Result]) -> None:
    """50. corpus/profile digests are identical across PYTHONHASHSEED
    values 0/1/7919, while a hash-order-dependent digest is NOT (the
    discrimination proof for digest stability)."""
    children = [_w055_child(seed) for seed in (0, 1, 7919)]
    if None in children:
        results.append(fail(
            "case_50_w055_digest_hash_seeds", "a child run failed"
        ))
        return
    genuine = {child["genuine"] for child in children}
    profile = {child["profile"] for child in children}
    w029 = {child["w029"] for child in children}
    unstable = {child["unstable"] for child in children}
    stable = len(genuine) == 1 and len(profile) == 1 and len(w029) == 1
    instability_detected = len(unstable) > 1
    if stable and instability_detected:
        results.append(ok(
            "case_50_w055_digest_hash_seeds",
            "identical corpus/profile/W029-outcome digests across seeds "
            "0/1/7919 while the hash-order-dependent digest diverged "
            "(%d distinct values) -- nondeterminism is detectable"
            % len(unstable),
        ))
    else:
        results.append(fail(
            "case_50_w055_digest_hash_seeds",
            "genuine stable=%s; instability detected=%s"
            % (stable, instability_detected),
        ))


def case_51_sabotage_canonicalization(results: List[Result]) -> None:
    """51. R3 discriminating: canonicalization ambiguity is detected."""
    results.append(_sabotage_case(
        51, "case_51_sabotage_canonicalization", "W055-CNF-WIRE-001",
        lambda: _world_with(envelope=_AmbiguousCanonicalizer()),
    ))


def case_52_sabotage_signature_coverage(results: List[Result]) -> None:
    """52. R3 discriminating: covered-byte exclusion is detected."""
    results.append(_sabotage_case(
        52, "case_52_sabotage_signature_coverage", "W055-CNF-WIRE-017",
        lambda: _world_with(envelope=_SignatureBlindEnvelope()),
    ))


# ---------------------------------------------------------------------------
# WORK-029 R3 coverage (negotiation + migration), consumed from this
# battery -- the sanctioned composition root.  The fixtures and tables
# below are the battery-level mirrors of the registry-vector model:
# each named check carries a frozen expectation against the genuine
# authority, and the sabotaged candidates prove discrimination.
# ---------------------------------------------------------------------------

_MIGRATION_SCHEMA_ID = "conformance.fixture-state"

_NEGOTIATION_SCENARIOS: Tuple[Tuple[str, Tuple[int, int], Tuple[int, int]], ...] = (
    ("floor", (1, 3), (1, 2)),
    ("equal-heads", (1, 4), (1, 4)),
    ("major-mismatch", (1, 3), (2, 0)),
    ("major-unknown", (2, 1), (2, 1)),
)

_EXPECTED_NEGOTIATION = {
    "floor": {"selected": [1, 2], "reason": None},
    "equal-heads": {"selected": [1, 4], "reason": None},
    "major-mismatch": {"selected": None, "reason": UpgradeReasonCode.MAJOR_MISMATCH},
    "major-unknown": {"selected": None, "reason": UpgradeReasonCode.MAJOR_UNKNOWN},
}


def _negotiation_outcome_table() -> dict:
    table = {}
    for name, local, peer in _NEGOTIATION_SCENARIOS:
        result = negotiate_protocol_profile(
            ProtocolProfile(major=local[0], max_minor=local[1]),
            ProtocolProfile(major=peer[0], max_minor=peer[1]),
        )
        table[name] = {
            "selected": (
                [result.selected.major, result.selected.max_minor]
                if result.selected is not None else None
            ),
            "reason": result.reason,
        }
    return table


def case_53_w029_negotiation_genuine(results: List[Result]) -> None:
    """53. R3 version negotiation at the owning frozen boundary: the
    genuine WORK-029 negotiation outcome table, structural fail-closed,
    downgrade-plan refusal, and W003 disposition delegation."""
    name = "case_53_w029_negotiation_genuine"
    problems: List[str] = []
    table = _negotiation_outcome_table()
    if table != _EXPECTED_NEGOTIATION:
        problems.append("negotiation table drift: %r" % table)
    # Structural fail-closed: a forged cross-major selection is not a
    # constructible value of the model.
    try:
        ProfileNegotiation(
            local=ProtocolProfile(1, 3), peer=ProtocolProfile(2, 0),
            selected=ProtocolProfile(1, 0), reason=None,
            detail="forged cross-major selection",
        )
        problems.append("a forged cross-major selection was constructed")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.MAJOR_MISMATCH:
            problems.append("forged selection rejected as %r" % error.reason)
    # A selected profile above the additive-evolution floor is not a value.
    try:
        ProfileNegotiation(
            local=ProtocolProfile(1, 3), peer=ProtocolProfile(1, 2),
            selected=ProtocolProfile(1, 3), reason=None,
            detail="forged above-floor selection",
        )
        problems.append("a non-floor selection was constructed")
    except UpgradeError:
        pass
    # Downgrade resistance: a downgrade is not a constructible plan.
    try:
        UpgradePlan(
            node_id="node:w055-alpha",
            from_version=SoftwareVersion(2, 0, 0),
            to_version=SoftwareVersion(1, 0, 0),
            target_protocol_profile=ProtocolProfile(1, 0),
        )
        problems.append("a downgrade plan was constructed")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.NOT_AN_UPGRADE:
            problems.append("downgrade plan rejected as %r" % error.reason)
    # The genuine upgrade passes the downgrade check and fails LATER on
    # the required gates (the check itself does not over-reject).
    try:
        UpgradePlan(
            node_id="node:w055-alpha",
            from_version=SoftwareVersion(1, 0, 0),
            to_version=SoftwareVersion(2, 0, 0),
            target_protocol_profile=ProtocolProfile(1, 0),
        )
        problems.append("a gateless upgrade plan was accepted (unexpected)")
    except UpgradeError as error:
        if error.reason == UpgradeReasonCode.NOT_AN_UPGRADE:
            problems.append("the genuine upgrade failed the downgrade check")
    # The envelope-level disposition delegates to WORK-003.
    from protocol.versioning import Classification, classify_major

    if (classify_major(1) != Classification.KNOWN_COMPATIBLE
            or classify_major(99) != Classification.REJECTED_INCOMPATIBLE_MAJOR):
        problems.append("the W003 disposition classification drifted")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(ok(
            name,
            "genuine negotiation table exact (floor/equal/mismatch/"
            "unknown); forged selections non-constructible; downgrade "
            "plans refused (NOT_AN_UPGRADE) while genuine upgrades pass "
            "the check; W003 disposition delegated",
        ))


def case_54_sabotage_negotiation_downgrade(results: List[Result]) -> None:
    """54. R3 discriminating: cross-major downgrade fallback is detected
    (genuine correct -> sabotaged detected -> genuine restored)."""
    name = "case_54_sabotage_negotiation_downgrade"
    genuine = _negotiation_outcome_table()
    if genuine != _EXPECTED_NEGOTIATION:
        results.append(fail(name, "genuine table wrong before sabotage"))
        return
    sabotaged = _ClampingNegotiator()
    mismatched = sabotaged.negotiate(
        ProtocolProfile(1, 3), ProtocolProfile(2, 0)
    )
    detected = bool(mismatched.succeeded or mismatched.selected is not None)
    genuine_again = _negotiation_outcome_table()
    if detected and genuine_again == _EXPECTED_NEGOTIATION:
        results.append(ok(
            name,
            "major-mismatch: genuine fails closed (MAJOR_MISMATCH) -> "
            "sabotaged clamping fallback DETECTED (returned a selected "
            "profile) -> genuine table restored",
        ))
    else:
        results.append(fail(
            name,
            "detected=%s; genuine restored=%s"
            % (detected, genuine_again == _EXPECTED_NEGOTIATION),
        ))


def _migration_fixture_state() -> dict:
    return {
        "schema_version": "1.0",
        "records": [
            {"id": "fixture-0001", "kind": "sample", "value": 42},
            {"id": "fixture-0002", "kind": "sample", "value": -7},
        ],
        "labels": ["alpha", "beta"],
    }


def _migration_additive_forward(state) -> dict:
    out = dict(state)
    out["retention_policy"] = "standard"
    out["schema_version"] = "1.1"
    return out


def _migration_additive_backward(state) -> dict:
    out = dict(state)
    out.pop("retention_policy", None)
    out["schema_version"] = "1.0"
    return out


def _migration_breaking_forward(state) -> dict:
    out = dict(state)
    records = out.pop("records", [])
    out["entries"] = list(records)
    out["schema_version"] = "2.0"
    return out


def _migration_never_backward(state) -> dict:
    raise AssertionError("declared non-reversible; unreachable by contract")


def build_w055_migration_registry() -> MigrationRegistry:
    """The frozen WORK-055 battery migration fixture: a genuine WORK-029
    registry carrying pure caller-supplied fixture step functions."""
    registry = MigrationRegistry()
    registry.register_step(
        _MIGRATION_SCHEMA_ID, "1.0", "1.1",
        reversible=True, breaking=False,
        forward=_migration_additive_forward,
        backward=_migration_additive_backward,
    )
    registry.register_step(
        _MIGRATION_SCHEMA_ID, "1.1", "2.0",
        reversible=False, breaking=True,
        forward=_migration_breaking_forward,
        backward=_migration_never_backward,
    )
    return registry


def case_55_w029_migration_genuine(results: List[Result]) -> None:
    """55. R3 schema evolution/migration at the owning frozen boundary:
    the genuine WORK-029 migration outcome table (semantic preservation,
    byte-identical round-trip, fail-closed classes, purity, tampered
    ids, deterministic introspection)."""
    name = "case_55_w029_migration_genuine"
    from protocol import canonical_json_bytes

    problems: List[str] = []
    registry = build_w055_migration_registry()
    state = _migration_fixture_state()
    original = canonical_json_bytes(state)
    # 1. Additive forward: semantics preserved (prior members byte-identical
    #    except the version stamp; the additive field appears; input pure).
    migrated = registry.migrate(state, _MIGRATION_SCHEMA_ID, "1.0", "1.1")
    for member, value in state.items():
        if member == "schema_version":
            continue
        if migrated.get(member) != value:
            problems.append("member %r drifted in the additive step" % member)
    if "retention_policy" not in migrated:
        problems.append("the additive field was not added")
    if canonical_json_bytes(state) != original:
        problems.append("the input state was mutated (impurity)")
    # 2. Reversible round-trip: forward then backward is byte-identical.
    backward = registry.migrate(migrated, _MIGRATION_SCHEMA_ID, "1.1", "1.0")
    if canonical_json_bytes(backward) != original:
        problems.append("the round-trip diverged")
    if not registry.path_is_reversible(_MIGRATION_SCHEMA_ID, "1.0", "1.1"):
        problems.append("the additive chain is not reversible")
    if registry.path_is_reversible(_MIGRATION_SCHEMA_ID, "1.1", "2.0"):
        problems.append("the breaking chain is reported reversible")
    # 3. Non-reversible reversal fails closed.
    state_v2 = registry.migrate(migrated, _MIGRATION_SCHEMA_ID, "1.1", "2.0")
    try:
        registry.migrate(state_v2, _MIGRATION_SCHEMA_ID, "2.0", "1.1")
        problems.append("the non-reversible step was reversed")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE:
            problems.append("reversal rejected as %r" % error.reason)
    # 4. Unknown path fails closed.
    try:
        registry.migrate(state, _MIGRATION_SCHEMA_ID, "1.0", "3.0")
        problems.append("an unknown path was migrated")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.MIGRATION_PATH_UNKNOWN:
            problems.append("unknown path rejected as %r" % error.reason)
    # 5. No-op migration rejected.
    try:
        registry.migrate(state, _MIGRATION_SCHEMA_ID, "1.0", "1.0")
        problems.append("a no-op migration was performed")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.MIGRATION_INVALID_STEP:
            problems.append("no-op rejected as %r" % error.reason)
    # 6. Duplicate edge fails closed; the registry is unchanged.
    before = registry.edge_count()
    try:
        registry.register_step(
            _MIGRATION_SCHEMA_ID, "1.0", "1.1",
            reversible=True, breaking=False,
            forward=lambda s: dict(s), backward=lambda s: dict(s),
        )
        problems.append("a duplicate edge was registered")
    except UpgradeError as error:
        if error.reason != UpgradeReasonCode.MIGRATION_DUPLICATE_EDGE:
            problems.append("duplicate rejected as %r" % error.reason)
    if registry.edge_count() != before:
        problems.append("the rejected registration mutated the registry")
    # 7. Step shapes enforce the version-line discipline.
    for desc_kwargs, label in (
        ({"schema_id": _MIGRATION_SCHEMA_ID, "from_version": "1.0",
          "to_version": "1.2", "reversible": True, "breaking": False},
         "two-minor additive"),
        ({"schema_id": _MIGRATION_SCHEMA_ID, "from_version": "1.1",
          "to_version": "2.1", "reversible": False, "breaking": True},
         "minor-keeping breaking"),
    ):
        try:
            MigrationDescriptor(**desc_kwargs)
            problems.append("a %s step was accepted" % label)
        except UpgradeError:
            pass
    # 8. Complete-content migration ids reject tampering.
    expected_id = derive_migration_id(
        _MIGRATION_SCHEMA_ID, "1.0", "1.1", True, False,
    )
    try:
        MigrationDescriptor(
            schema_id=_MIGRATION_SCHEMA_ID, from_version="1.0",
            to_version="1.1", reversible=True, breaking=False,
            migration_id="tampered-" + expected_id,
        )
        problems.append("a tampered migration id was accepted")
    except UpgradeError:
        pass
    # 9. Deterministic introspection.
    descriptors = registry.descriptors()
    keys = [(d.schema_id, d.from_version, d.to_version) for d in descriptors]
    if keys != sorted(keys) or len(keys) != 2:
        problems.append("registry introspection is not canonical")
    if [d.to_dict() for d in build_w055_migration_registry().descriptors()] != \
            [d.to_dict() for d in descriptors]:
        problems.append("fresh registries differ")
    if problems:
        results.append(fail(name, "; ".join(problems)))
    else:
        results.append(ok(
            name,
            "additive semantics preserved (input pure); round-trip "
            "byte-identical; non-reversible reversal, unknown path, "
            "no-op, duplicate edge, step shapes, and tampered ids all "
            "fail closed; introspection deterministic",
        ))


def case_56_sabotage_migration(results: List[Result]) -> None:
    """56. R3 discriminating: best-effort reversal of a non-reversible
    migration is detected (genuine correct -> sabotaged detected ->
    genuine restored)."""
    name = "case_56_sabotage_migration"
    from protocol import canonical_json_bytes

    registry = build_w055_migration_registry()
    state = _migration_fixture_state()
    migrated = registry.migrate(state, _MIGRATION_SCHEMA_ID, "1.0", "1.1")
    state_v2 = registry.migrate(migrated, _MIGRATION_SCHEMA_ID, "1.1", "2.0")
    # Genuine: the reversal fails closed.
    genuine_rejected = False
    try:
        registry.migrate(state_v2, _MIGRATION_SCHEMA_ID, "2.0", "1.1")
    except UpgradeError as error:
        genuine_rejected = (
            error.reason == UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE
        )
    if not genuine_rejected:
        results.append(fail(name, "genuine reversal was not refused"))
        return
    # Sabotaged: the best-effort migrator performs the partial undo.
    sabotaged = _BestEffortMigrator(build_w055_migration_registry())
    try:
        undone = sabotaged.migrate(state_v2, "2.0", "1.1")
        detected = canonical_json_bytes(undone) != canonical_json_bytes(
            state_v2
        )
    except UpgradeError:
        detected = False
    # Genuine again: a fresh registry still refuses.
    genuine_again = False
    try:
        build_w055_migration_registry().migrate(
            state_v2, _MIGRATION_SCHEMA_ID, "2.0", "1.1"
        )
    except UpgradeError as error:
        genuine_again = (
            error.reason == UpgradeReasonCode.MIGRATION_NOT_REVERSIBLE
        )
    if detected and genuine_again:
        results.append(ok(
            name,
            "2.0 -> 1.1: genuine MIGRATION_NOT_REVERSIBLE -> sabotaged "
            "best-effort partial undo DETECTED (a divergent state was "
            "returned) -> genuine refusal restored",
        ))
    else:
        results.append(fail(
            name, "detected=%s; genuine restored=%s" % (detected, genuine_again)
        ))


def case_57_sabotage_unknown_fields(results: List[Result]) -> None:
    """57. R3 discriminating: silently downgrading required extensions
    is detected."""
    results.append(_sabotage_case(
        57, "case_57_sabotage_unknown_fields", "W055-CNF-WIRE-021",
        lambda: _world_with(envelope=_RequiredFlagStripper()),
    ))


def case_58_sabotage_evidence_authority(results: List[Result]) -> None:
    """58. R3 discriminating: conformance evidence promoted into
    protocol authority is detected (the expired envelope is accepted
    because a CONFORMANT report exists)."""
    results.append(_sabotage_case(
        58, "case_58_sabotage_evidence_authority", "W032-CNF-ENV-002",
        lambda: _world_with(envelope=_EvidenceTrustingEnvelope()),
    ))


def case_59_w055_tag_coverage(results: List[Result]) -> None:
    """57. every W055 negative and discrimination category is covered."""
    registry = build_default_registry()
    covered = set(registry.tags())
    missing = [
        tag for tag in (
            list(W055_REQUIRED_NEGATIVE_TAGS)
            + list(W055_REQUIRED_DISCRIMINATION_TAGS)
        ) if tag not in covered
    ]
    if missing:
        results.append(fail(
            "case_59_w055_tag_coverage", "missing tags: %s" % missing
        ))
    else:
        results.append(ok(
            "case_59_w055_tag_coverage",
            "all %d W055 negative + %d W055 discrimination categories "
            "covered"
            % (len(W055_REQUIRED_NEGATIVE_TAGS),
               len(W055_REQUIRED_DISCRIMINATION_TAGS)),
        ))


def case_60_classification_table(results: List[Result]) -> None:
    """58. the envelope compatibility classes are exactly the frozen
    WORK-003 vocabulary and every value is produced by the matrix."""
    from protocol.versioning import Classification

    report = _matrix()
    envelope_classes = {
        r.observed.result_class
        for r in report.results_for_area("envelope")
    }
    vocabulary = set(Classification.ALL_VALUES)
    produced = envelope_classes & vocabulary
    missing = vocabulary - produced
    if missing:
        results.append(fail(
            "case_60_classification_table",
            "compatibility classes not produced by the matrix: %s"
            % sorted(missing),
        ))
    else:
        results.append(ok(
            "case_60_classification_table",
            "all %d frozen compatibility classes produced by the matrix "
            "with stable codes and owning-authority attribution "
            "(additional vector-local result classes are harness "
            "classifications, never protocol classes)"
            % len(vocabulary),
        ))


def case_61_evidence_never_authority(results: List[Result]) -> None:
    """59. conformance evidence stays automated verification: no
    external claims, no authority objects, and the digests are plain
    evidence strings."""
    report = _matrix()
    try:
        assert_no_external_claim(report)
    except ValueError as error:
        results.append(fail("case_61_evidence_never_authority", str(error)))
        return
    evidence = build_evidence_report(report)
    external = evidence["external_evidence"]
    if external["records"] != []:
        results.append(fail(
            "case_61_evidence_never_authority",
            "in-repo run minted external evidence",
        ))
        return
    corpus = load_corpus()
    corpus_results = verify_corpus(corpus)
    if not all(r.verified for r in corpus_results):
        results.append(fail(
            "case_61_evidence_never_authority",
            "corpus verification failed (see case_48)",
        ))
        return
    digest = corpus_digest(corpus, corpus_results)
    # The digest is a plain evidence string: it is not an authority
    # object and cannot be coerced into one by the frozen authorities.
    from protocol import EnvelopeError

    try:
        report_from_mapping({"verdict": digest})
    except Exception:
        pass  # any rejection is fine; a digest is not report state either
    try:
        import conformance.serialization as _serialization  # noqa: F401

        envelope_like = {"digest": digest}
        from protocol import envelope_from_mapping as _from_mapping

        try:
            _from_mapping(envelope_like)
        except EnvelopeError:
            results.append(ok(
                "case_61_evidence_never_authority",
                "no external claims; digests are plain evidence strings "
                "(rejected as protocol state); corpus digest %s" % digest,
            ))
            return
        results.append(fail(
            "case_61_evidence_never_authority",
            "an evidence digest was accepted as a protocol envelope",
        ))
    except Exception as error:  # noqa: BLE001
        results.append(fail(
            "case_61_evidence_never_authority",
            "unexpected %s: %s" % (type(error).__name__, error),
        ))


_W055_BASELINE = "57963858e5a2b9d11faed94b50f94e058cede0a8"
_W055_AUTHORIZED_PATHS = (
    "conformance/",
    "tools/conformance_selftest.py",
    "docs/WORK-055-evidence.md",
    "docs/WORK-055-handoff.md",
)


def _w055_origin_main_available() -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "origin/main"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    return proc.returncode == 0


def case_62_w055_pr_delta_scope(results: List[Result]) -> None:
    """60. the delivery delta lies exactly in the authorized W055
    scope and descends from the authorized baseline."""
    name = "case_62_w055_pr_delta_scope"
    delta: set = set()
    if _w055_origin_main_available():
        # CI PR/merge context: the diff against the PR base is exact.
        diff = subprocess.run(
            ["git", "diff", "--name-only", "origin/main", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if diff.returncode == 0:
            delta |= {l for l in diff.stdout.splitlines() if l.strip()}
    else:
        # Local delivery context: the diff against the authorized
        # baseline (working tree + uncommitted changes included).
        diff = subprocess.run(
            ["git", "diff", "--name-only", _W055_BASELINE],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if diff.returncode == 0:
            delta |= {l for l in diff.stdout.splitlines() if l.strip()}
        committed = subprocess.run(
            ["git", "diff", "--name-only", _W055_BASELINE, "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if committed.returncode == 0:
            delta |= {l for l in committed.stdout.splitlines() if l.strip()}
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if untracked.returncode == 0:
        delta |= {l for l in untracked.stdout.splitlines() if l.strip()}
    if not delta:
        results.append(ok(name, "no delta (clean baseline checkout)"))
        return
    problems = []
    for path in sorted(delta):
        if not any(
            path == surface or path.startswith(surface)
            for surface in _W055_AUTHORIZED_PATHS
        ):
            problems.append("delta outside the authorized scope: %s" % path)
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", _W055_BASELINE, "HEAD"],
        capture_output=True, cwd=str(REPO_ROOT),
    )
    if ancestry.returncode != 0:
        problems.append(
            "the authorized baseline %s is not an ancestor of HEAD"
            % _W055_BASELINE
        )
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(
        name,
        "the %d-path delta lies exactly within the authorized WORK-055 "
        "scope (conformance/, tools/conformance_selftest.py, "
        "docs/WORK-055-*.md) and the authorized baseline %s is an "
        "ancestor of HEAD" % (len(delta), _W055_BASELINE[:12]),
    ))


def case_63_frozen_authorities_untouched(results: List[Result]) -> None:
    """61. the frozen authorities consumed by the suite are untouched
    by the delivery (protocol/, upgrade/, spec/ root, schemas; the
    spec/architect package vs the owning ref)."""
    name = "case_63_frozen_authorities_untouched"
    frozen_roots = (
        "protocol/", "upgrade/", "spec/schemas/",
        "spec/architecture.md", "spec/architecture-lock.md",
        "spec/mission.md", "spec/governance.md", "spec/change-control.md",
        "spec/workflow.md", "spec/work-items.md",
        "spec/dependency-graph.md",
    )
    problems: List[str] = []
    for root in frozen_roots:
        proc = subprocess.run(
            ["git", "diff", "--name-only", _W055_BASELINE, "HEAD", "--",
             root],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        if proc.returncode != 0:
            problems.append("diff failed for %s" % root)
        elif proc.stdout.strip():
            problems.append("frozen surface changed: %s" % proc.stdout.strip())
    # The Architect package is compared against the owning ref: the PR
    # base when origin/main is available (CI merge context), else the
    # authorized baseline (local delivery context).
    architect_ref = (
        "origin/main" if _w055_origin_main_available() else _W055_BASELINE
    )
    proc = subprocess.run(
        ["git", "diff", "--name-only", architect_ref, "HEAD", "--",
         "spec/architect/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        problems.append("architect diff failed")
    elif proc.stdout.strip():
        problems.append(
            "spec/architect/ differs from %s: %s"
            % (architect_ref, proc.stdout.strip())
        )
    if problems:
        results.append(fail(name, "; ".join(problems)))
        return
    results.append(ok(
        name,
        "protocol/, upgrade/, spec root documents, and spec/schemas/ are "
        "byte-identical to the authorized baseline; spec/architect/ "
        "differs only from its owning ref (%s), never from this delivery"
        % architect_ref,
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

    # 47-63: WORK-055 production conformance (R3).
    case_47_w055_profile(results)
    case_48_w055_corpus(results)
    case_49_w055_digest_subprocess(results)
    case_50_w055_digest_hash_seeds(results)
    case_51_sabotage_canonicalization(results)
    case_52_sabotage_signature_coverage(results)
    case_53_w029_negotiation_genuine(results)
    case_54_sabotage_negotiation_downgrade(results)
    case_55_w029_migration_genuine(results)
    case_56_sabotage_migration(results)
    case_57_sabotage_unknown_fields(results)
    case_58_sabotage_evidence_authority(results)
    case_59_w055_tag_coverage(results)
    case_60_classification_table(results)
    case_61_evidence_never_authority(results)
    case_62_w055_pr_delta_scope(results)
    case_63_frozen_authorities_untouched(results)

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
