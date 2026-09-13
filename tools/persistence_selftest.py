#!/usr/bin/env python3
"""ADCOS deployment persistence battery (DEC-0126 bounded scope) — the
Neon PostgreSQL durable-adapter contract (deterministic, stdlib only,
NO Postgres, NO network).

Verifies ``backends/postgres.py`` against a deterministic FAKE pg
connection implementing exactly the adapter's minimal DB-API seam
(``cursor().execute(sql, params)`` / ``fetchall()`` / ``close()`` +
``commit()`` / ``rollback()`` — transactional row buffering, so
all-or-nothing batches are exercised for real):

- the ApiStore seam contract: ``append_line`` / ``read_lines`` byte
  exact round-trip, ``seq`` ordering, the newline discipline the ABC's
  own stores enforce, and journal-first gateway recovery over durable
  rows (byte-identical journal digests);
- the contract-journal round-trip: ``load_lines`` / ``append_lines``
  (single transaction), namespace isolation, ``materialize_store``
  (the local JSONL materialization + the accepted construction-time
  re-fold), subsequent appends landing in BOTH the file and postgres,
  and re-materialization reproducing the byte-identical fold;
- the evidence-journal round-trip (the same discipline over the
  accepted EvidenceStore);
- the fail-closed discipline: every backend failure raises
  ``PostgresBackendError`` with the machine-readable ``reason_code``
  and ``backend = "postgres"`` — NEVER a silent in-memory fallback
  (asserted as the error TYPE, with the durable state untouched);
- LOCK-119: journal lines pass through the ACCEPTED store's own
  secret scan before any durable row exists (a secret-shaped line is
  rejected by the store itself; the table is untouched);
- the lazy-import discipline: importing ``backends.postgres`` (and
  the whole runtime wiring) never imports ``pg8000`` — the driver is
  only ever imported inside the real connection factory (verified in
  subprocesses via ``sys.modules``);
- production assembly over the fake backend: the full
  ``build_production_services`` composition (durable schema bootstrap,
  materialization, journal-first gateway recovery, the deterministic
  demonstration writing through the durable stores) and its recovery
  on a second assembly.

No third-party requirements; runs offline; byte-identical outputs
across runs (fixed instants, no wall clock, no randomness).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from contracts import ContractStore  # noqa: E402
from contracts.model import ContractError, ContractReason  # noqa: E402

from developerapi.gateway import DeveloperApiService  # noqa: E402
from developerapi.journal import MemoryApiStore  # noqa: E402

from evidence import EvidenceStore, ObservationEvidence  # noqa: E402

import backends.postgres as pg  # noqa: E402
from backends.postgres import (  # noqa: E402
    PostgresApiStore,
    PostgresBackendError,
    PostgresContractJournal,
    PostgresEvidenceJournal,
)

from runtime.wiring import build_production_services  # noqa: E402

Result = Tuple[str, bool, str]


def ok(name: str, detail: str = "") -> Result:
    return (name, True, detail)


def fail(name: str, detail: str) -> Result:
    return (name, False, detail)


# ---------------------------------------------------------------------------
# The deterministic fake pg connection (the minimal DB-API seam)
# ---------------------------------------------------------------------------


class FakeCursor:
    """One cursor over the fake database (own-transaction visibility:
    SELECTs see committed + pending rows)."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection
        self._rows: List[Tuple[Any, ...]] = []
        self.closed = False

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        if self.closed:
            raise RuntimeError("cursor is closed")
        self._connection.executed.append((sql, tuple(params)))
        marker = self._connection.fail_on_marker
        if marker and marker in sql:
            raise RuntimeError("injected failure on %s" % marker)
        budget = self._connection.fail_after_execute
        if budget is not None and len(self._connection.executed) >= budget:
            raise RuntimeError("injected failure after %d executes" % budget)
        self._connection._apply(sql, tuple(params), self._rows)

    def fetchall(self) -> List[Tuple[Any, ...]]:
        return list(self._rows)

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    """The deterministic fake: one shared in-memory database, per-
    connection transaction buffering (commit applies, rollback
    discards), optional failure injection."""

    def __init__(self, database: "FakeDatabase") -> None:
        self._database = database
        self.executed: List[Tuple[str, Tuple[Any, ...]]] = []
        self._pending: List[Tuple[str, str, str]] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on_marker: Optional[str] = None
        self.fail_after_execute: Optional[int] = None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1
        for table, namespace, line in self._pending:
            self._database.apply_committed(table, namespace, line)
        self._pending = []

    def rollback(self) -> None:
        self.rollbacks += 1
        self._pending = []

    # -- the fake SQL engine (the exact statements the adapter emits) --

    def _apply(self, sql: str, params: Tuple[Any, ...], rows: List[Tuple[Any, ...]]) -> None:
        normalized = " ".join(sql.split()).strip().rstrip(";")
        if normalized.startswith("CREATE TABLE"):
            table = normalized.split()[5]
            self._database.tables.add(table)
            return
        if normalized == "SELECT 1":
            rows.append((1,))
            return
        if normalized.startswith("INSERT INTO adcos_"):
            table = normalized.split()[2]
            if table not in self._database.tables:
                raise RuntimeError("table %s does not exist" % table)
            if table == "adcos_api_journal":
                namespace, line = "default", params[0]
            else:
                namespace, line = params[0], params[1]
            self._pending.append((table, namespace, line))
            return
        if normalized.startswith("SELECT line FROM "):
            table = normalized.split()[3]
            if table not in self._database.tables:
                raise RuntimeError("table %s does not exist" % table)
            if "ORDER BY seq" not in normalized:
                raise RuntimeError("the adapter must order journal reads by seq")
            rows.extend(
                (row[2],)
                for row in self._database.visible_rows(table, self)
                if _namespace_filter(normalized, params, row[0])
            )
            return
        raise RuntimeError("unexpected SQL: %r" % normalized)


def _namespace_filter(normalized: str, params: Tuple[Any, ...], namespace: str) -> bool:
    if "WHERE namespace = %s" in normalized:
        return bool(params) and namespace == params[0]
    return True


class FakeDatabase:
    """The shared durable state: tables, per-table seq counters, and
    committed (namespace, seq, line) rows."""

    def __init__(self) -> None:
        self.tables = set()
        self._rows: Dict[str, List[Tuple[str, int, str]]] = {}
        self._seq: Dict[str, int] = {}

    def apply_committed(self, table: str, namespace: str, line: str) -> None:
        seq = self._seq.get(table, 0) + 1
        self._seq[table] = seq
        self._rows.setdefault(table, []).append((namespace, seq, line))

    def visible_rows(
        self, table: str, connection: "FakeConnection"
    ) -> List[Tuple[str, int, str]]:
        # own-transaction visibility: committed rows + this connection's
        # pending rows (pseudo-seq above every committed seq)
        committed = list(self._rows.get(table, ()))
        pending = [
            (namespace, 10**9 + index, line)
            for index, (pending_table, namespace, line) in enumerate(connection._pending)
            if pending_table == table
        ]
        return committed + pending

    def rows(self, table: str, namespace: Optional[str] = None) -> List[str]:
        rows = self._rows.get(table, ())
        if namespace is None:
            return [row[2] for row in sorted(rows, key=lambda r: r[1])]
        return [
            row[2]
            for row in sorted(rows, key=lambda r: r[1])
            if row[0] == namespace
        ]

    def count(self, table: str) -> int:
        return len(self._rows.get(table, ()))


def fake_factory(database: FakeDatabase, *, connect_error: Optional[str] = None):
    def _factory() -> FakeConnection:
        if connect_error is not None:
            raise RuntimeError(connect_error)
        return FakeConnection(database)

    return _factory


# ---------------------------------------------------------------------------
# Fixtures (the accepted composition idioms, fixed instants)
# ---------------------------------------------------------------------------

_T0 = "2026-09-13T00:00:00Z"


def _api_lines() -> List[str]:
    """Two newline-terminated journal lines (the accepted store's own
    format)."""
    return ['{"kind":"a","seq":1}\n', '{"kind":"b","seq":2}\n']


def _contract_journal_store(
    database: FakeDatabase, namespace: str = "default"
) -> PostgresContractJournal:
    journal = PostgresContractJournal(
        connection_factory=fake_factory(database), namespace=namespace
    )
    journal.ensure_schema()
    return journal


def _drive_one_contract_command(store: ContractStore) -> str:
    """Submit ONE canonical command through the store's public surface
    (create: the cheapest accepted command)."""
    from contracts import (
        CreateContract,
        HardConstraint,
        OpaqueReference,
        Provenance,
        ValidityInterval,
    )
    from contracts.model import BeneficiaryScope, ConnectivityPrincipal, TerminationRules

    command = CreateContract(
        principal=ConnectivityPrincipal(
            principal_kind="APPLICATION", principal_ref="app:demo"
        ),
        beneficiaries=(
            BeneficiaryScope(beneficiary_kind="DEVICE", beneficiary_ref="dev:1"),
        ),
        requirements=(
            OpaqueReference(
                ref_kind="intent-requirements",
                value="demo:requirements",
                provenance=Provenance(issuer="intent-authority", decision_refs=()),
            ),
        ),
        hard_constraints=(
            HardConstraint(
                kind="latency-bound",
                params={"ms": 100},
                provenance=Provenance(issuer="demo", decision_refs=()),
            ),
        ),
        validity=ValidityInterval(
            not_before=_T0, not_after="2026-10-13T00:00:00Z"
        ),
        service_properties=(),
        usage_pricing_terms=None,
        assurance_obligations=(),
        execution_scope=(),
        termination=TerminationRules(
            conditions=("principal-requested", "validity-expired"),
            compensation=OpaqueReference(
                ref_kind="compensation", value="demo:compensation"
            ),
        ),
        provenance=Provenance(issuer="demo", decision_refs=()),
    )
    result = store.submit(command, recorded_at=_T0)
    assert result.accepted, result.detail
    return result.contract.contract_id


# ---------------------------------------------------------------------------
# The cases
# ---------------------------------------------------------------------------


def case_01_lazy_import_discipline() -> Result:
    name = "case_01_lazy_import_discipline"
    script = (
        "import sys; sys.path.insert(0, %r); "
        "import backends.postgres, runtime.wiring, runtime.asgi; "
        "print('pg8000' in sys.modules)" % str(REPO_ROOT)
    )
    outputs = []
    for _ in range(2):
        probe = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": "0", "PATH": ""},
        )
        if probe.returncode != 0:
            return fail(name, "subprocess import failed: %s" % probe.stderr[:200])
        outputs.append(probe.stdout.strip())
    if outputs != ["False", "False"]:
        return fail(name, "pg8000 leaked into sys.modules: %r" % outputs)
    return ok(name, "backends.postgres + runtime wiring import without pg8000")


def case_02_typed_error_surface() -> Result:
    name = "case_02_typed_error_surface"
    error = PostgresBackendError("backend-unavailable", "probe")
    if error.reason_code != "backend-unavailable":
        return fail(name, "reason_code not carried")
    if error.backend != "postgres":
        return fail(name, "backend identity not carried")
    try:
        raise PostgresBackendError("config-invalid", "probe")
    except PostgresBackendError as caught:
        if caught.reason_code != "config-invalid":
            return fail(name, "round-trip reason mismatch")
    if not issubclass(PostgresBackendError, Exception):
        return fail(name, "not an Exception")
    return ok(name, "typed error: reason_code + backend=postgres")


def case_03_config_invalid_url() -> Result:
    name = "case_03_config_invalid_url"
    try:
        PostgresApiStore(url="mysql://user:pw@host/db")
    except PostgresBackendError as error:
        if error.reason_code != "config-invalid":
            return fail(name, "wrong reason: %s" % error.reason_code)
        return ok(name, "non-postgres scheme rejected config-invalid")
    return fail(name, "a bad URL scheme was accepted")
    # (also: no URL and no factory)


def case_04_config_invalid_missing_url() -> Result:
    name = "case_04_config_invalid_missing_url"
    try:
        PostgresApiStore()
    except PostgresBackendError as error:
        if error.reason_code != "config-invalid":
            return fail(name, "wrong reason: %s" % error.reason_code)
        return ok(name, "missing URL + factory rejected config-invalid")
    return fail(name, "a parameterless construction was accepted")


def case_05_api_store_round_trip() -> Result:
    name = "case_05_api_store_round_trip"
    database = FakeDatabase()
    store = PostgresApiStore(connection_factory=fake_factory(database))
    store.ensure_schema()
    lines = _api_lines()
    for line in lines:
        store.append_line(line)
    read = store.read_lines()
    expected = [line.rstrip("\n") for line in lines]
    if read != expected:
        return fail(name, "round-trip mismatch: %r != %r" % (read, expected))
    if database.rows("adcos_api_journal") != expected:
        return fail(name, "durable rows mismatch")
    return ok(
        name,
        "append_line/read_lines byte-exact round-trip (FileApiStore "
        "splitlines semantics)",
    )


def case_06_api_store_ordering_by_seq() -> Result:
    name = "case_06_api_store_ordering_by_seq"
    database = FakeDatabase()
    store = PostgresApiStore(connection_factory=fake_factory(database))
    store.ensure_schema()
    lines = ['{"n":%d}\n' % index for index in range(1, 26)]
    for line in lines:
        store.append_line(line)
    if store.read_lines() != [line.rstrip("\n") for line in lines]:
        return fail(name, "seq ordering violated")
    return ok(name, "25 lines ordered by seq (byte-exact)")


def case_07_api_store_newline_discipline() -> Result:
    name = "case_07_api_store_newline_discipline"
    database = FakeDatabase()
    store = PostgresApiStore(connection_factory=fake_factory(database))
    store.ensure_schema()
    try:
        store.append_line('{"a":1}')
    except Exception as error:
        from developerapi.errors import DeveloperApiError

        if not isinstance(error, DeveloperApiError):
            return fail(name, "wrong error type: %r" % error)
        if "newline" not in str(error):
            return fail(name, "wrong error text: %s" % error)
        if database.count("adcos_api_journal") != 0:
            return fail(name, "a rejected line was persisted")
        return ok(name, "non-newline line rejected exactly like the ABC stores")
    return fail(name, "a non-newline line was accepted")


def case_08_backend_failure_is_typed_never_fallback() -> Result:
    name = "case_08_backend_failure_is_typed_never_fallback"
    database = FakeDatabase()
    store = PostgresApiStore(connection_factory=fake_factory(database))
    store.ensure_schema()
    store.append_line('{"a":1}\n')
    database_shared = database
    # a failing connection on the NEXT statement
    connection = store._connect()
    connection.fail_on_marker = "INSERT INTO adcos_api_journal"
    try:
        store.append_line('{"b":2}\n')
    except PostgresBackendError as error:
        if error.reason_code != "backend-unavailable":
            return fail(name, "wrong reason: %s" % error.reason_code)
        if error.backend != "postgres":
            return fail(name, "backend not named")
        if database_shared.count("adcos_api_journal") != 1:
            return fail(name, "state changed despite the failure")
        if connection.rollbacks < 1:
            return fail(name, "the failed transaction was not rolled back")
        return ok(
            name,
            "typed backend-unavailable + rollback; durable state untouched; "
            "NO in-memory fallback",
        )
    return fail(name, "a backend failure did not raise the typed error")


def case_09_read_failure_is_typed() -> Result:
    name = "case_09_read_failure_is_typed"
    database = FakeDatabase()
    store = PostgresApiStore(connection_factory=fake_factory(database))
    store.ensure_schema()
    connection = store._connect()
    connection.fail_on_marker = "SELECT line FROM"
    try:
        store.read_lines()
    except PostgresBackendError as error:
        if error.reason_code != "backend-unavailable":
            return fail(name, "wrong reason: %s" % error.reason_code)
        return ok(name, "a read failure raises the typed backend error")
    return fail(name, "a read failure did not raise")


def case_10_health_probe() -> Result:
    name = "case_10_health_probe"
    database = FakeDatabase()
    store = PostgresApiStore(connection_factory=fake_factory(database))
    store.ensure_schema()
    healthy = store.health()
    if healthy.get("state") != "ready":
        return fail(name, "healthy probe: %r" % healthy)
    connection = store._connect()
    connection.fail_on_marker = "SELECT 1"
    broken = store.health()
    if broken.get("state") != "unavailable":
        return fail(name, "broken probe: %r" % broken)
    if "detail" not in broken:
        return fail(name, "the unavailable probe carries no detail")
    return ok(name, "health(): ready / unavailable with detail")


def case_11_contract_journal_round_trip() -> Result:
    name = "case_11_contract_journal_round_trip"
    database = FakeDatabase()
    journal = _contract_journal_store(database)
    # the newline is the FILE framing materialize_store adds; the
    # newline-free line content is the durable row convention
    lines = ['{"command":"create","sequence":1}', '{"command":"activate","sequence":2}']
    journal.append_lines(lines)
    loaded = journal.load_lines()
    if loaded != lines:
        return fail(name, "round-trip mismatch: %r" % loaded)
    return ok(name, "append_lines/load_lines byte-exact, seq-ordered")


def case_12_append_lines_single_transaction() -> Result:
    name = "case_12_append_lines_single_transaction"
    database = FakeDatabase()
    journal = _contract_journal_store(database)
    connection = journal._connect()
    # fail DURING the batch (all-or-nothing proof: the transaction is
    # rolled back and no row survives)
    connection.fail_after_execute = 2
    lines = ['{"a":1}', '{"b":2}', '{"c":3}']
    try:
        journal.append_lines(lines)
    except PostgresBackendError as error:
        if error.reason_code != "backend-unavailable":
            return fail(name, "wrong reason: %s" % error.reason_code)
        if database.count("adcos_contract_journal") != 0:
            return fail(name, "a partial batch was committed")
        if connection.rollbacks < 1:
            return fail(name, "the batch was not rolled back")
        return ok(name, "batch failure: all-or-nothing + rollback")
    return fail(name, "a failing batch did not raise")


def case_13_contract_journal_namespaces() -> Result:
    name = "case_13_contract_journal_namespaces"
    database = FakeDatabase()
    one = _contract_journal_store(database, namespace="one")
    two = _contract_journal_store(database, namespace="two")
    one.append_lines(['{"ns":"one"}'])
    two.append_lines(['{"ns":"two-a"}', '{"ns":"two-b"}'])
    if one.load_lines() != ['{"ns":"one"}']:
        return fail(name, "namespace one leaked: %r" % one.load_lines())
    if two.load_lines() != ['{"ns":"two-a"}', '{"ns":"two-b"}']:
        return fail(name, "namespace two leaked: %r" % two.load_lines())
    return ok(name, "namespace streams are isolated")


def case_14_materialize_store_and_dual_persistence() -> Result:
    name = "case_14_materialize_store_and_dual_persistence"
    database = FakeDatabase()
    journal = _contract_journal_store(database)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "contract-journal.jsonl"
        store = journal.materialize_store(path)
        before = database.count("adcos_contract_journal")
        contract_id = _drive_one_contract_command(store)
        if database.count("adcos_contract_journal") != before + 1:
            return fail(name, "the canonical append did not reach postgres")
        if not path.is_file():
            return fail(name, "the local journal file was not written")
        file_lines = path.read_text(encoding="utf-8").splitlines()
        if database.rows("adcos_contract_journal") != file_lines:
            return fail(name, "file and postgres journal diverged")
        # the fold is the authority: a fresh materialization reproduces
        # the byte-identical state
        store_two = journal.materialize_store(Path(tmp) / "again.jsonl")
        if store_two.contract(contract_id).contract_id != contract_id:
            return fail(name, "re-materialization lost the contract")
        if store_two.journal_digest() != store.journal_digest():
            return fail(name, "re-materialization changed the fold")
        return ok(name, "dual persistence (file + rows); re-fold byte-identical")


def case_15_lock119_secret_rejected_before_durable_row() -> Result:
    name = "case_15_lock119_secret_rejected_before_durable_row"
    database = FakeDatabase()
    journal = _contract_journal_store(database)

    class _SecretShapedRecord:
        """A record whose SERIALIZED LINE is secret-shaped (the accepted
        contract battery's case_38 discipline: the model layer rejects
        secrets at construction, so the journal scan is probed directly
        through the store's own persist path)."""

        def to_dict(self) -> Dict[str, Any]:
            return {"payload": {"note": "ghp_supersecrettoken123"}}

    with tempfile.TemporaryDirectory() as tmp:
        store = journal.materialize_store(Path(tmp) / "cj.jsonl")
        before = database.count("adcos_contract_journal")
        try:
            store._persist(_SecretShapedRecord())
        except ContractError as error:
            if error.code != ContractReason.SECRET_REJECTED:
                return fail(name, "wrong reason: %s" % error.code)
            if database.count("adcos_contract_journal") != before:
                return fail(name, "a secret-shaped line reached postgres")
            return ok(name, "LOCK-119: the store's own scan fired first; no row")
        except PostgresBackendError:
            return fail(name, "the LOCK-119 rejection surfaced as a backend error")
    return fail(name, "the secret-shaped line was not rejected")


def case_16_evidence_journal_round_trip() -> Result:
    name = "case_16_evidence_journal_round_trip"
    database = FakeDatabase()
    journal = PostgresEvidenceJournal(
        connection_factory=fake_factory(database), namespace="default"
    )
    journal.ensure_schema()
    with tempfile.TemporaryDirectory() as tmp:
        store = journal.materialize_store(Path(tmp) / "evidence.jsonl")
        record = ObservationEvidence(
            subject_ref="subject:demo",
            contract_ref="sha256:" + "ab" * 32,
            instant=_T0,
            producer="producer:demo",
            metric="link-up",
            value=1,
            confidence_basis_points=10_000,
            freshness_until="2026-09-14T00:00:00Z",
        )
        first = store.ingest(record)
        second = store.ingest(record)
        if not first.accepted or second.accepted:
            return fail(name, "ingest idempotency broken")
        if database.count("adcos_evidence_journal") != 1:
            return fail(name, "durable evidence rows: %d" % database.count("adcos_evidence_journal"))
        reloaded = journal.materialize_store(Path(tmp) / "again.jsonl")
        if reloaded.state_digest() != store.state_digest():
            return fail(name, "re-materialization changed the evidence fold")
        if len(reloaded) != 1:
            return fail(name, "re-materialization lost records")
        return ok(name, "evidence round-trip: durable row, idempotent, re-fold equal")


def case_17_gateway_recovery_over_durable_rows() -> Result:
    name = "case_17_gateway_recovery_over_durable_rows"
    database = FakeDatabase()
    store = PostgresApiStore(connection_factory=fake_factory(database))
    store.ensure_schema()
    from agent.clock import FixedClock

    issuance = b"battery-issuance-key-material"
    first = DeveloperApiService(
        environment="sandbox",
        contracts=ContractStore(),
        store=store,
        clock=FixedClock(_T0),
        issuance_key=issuance,
    )
    first.issue_application_credential(
        developer_id="dev:one",
        application_name="app:one",
        capabilities=("intents:read",),
        valid_until="2036-01-01T00:00:00Z",
        key_material="key-one",
        actor="platform",
    )
    digest_one = first.journal_digest()
    # journal-first recovery over the SAME durable rows
    second = DeveloperApiService.load(
        environment="sandbox",
        contracts=ContractStore(),
        store=store,
        clock=FixedClock(_T0),
        issuance_key=issuance,
    )
    if second.journal_digest() != digest_one:
        return fail(name, "recovery changed the journal digest")
    if second.verify_integrity() is not None:
        return fail(name, "recovery failed integrity verification")
    return ok(name, "DeveloperApiService.load over postgres rows: byte-identical")


def case_18_schema_error_is_typed() -> Result:
    name = "case_18_schema_error_is_typed"
    database = FakeDatabase()
    journal = PostgresContractJournal(connection_factory=fake_factory(database))
    connection_probe = fake_factory(database, connect_error="Neon quota exceeded")
    broken = PostgresContractJournal(connection_factory=connection_probe)
    try:
        broken.ensure_schema()
    except PostgresBackendError as error:
        if error.reason_code != "schema-error":
            return fail(name, "wrong reason: %s" % error.reason_code)
        if "quota" not in str(error):
            return fail(name, "the failure detail was swallowed")
        return ok(name, "a failing bootstrap raises schema-error (quota visible)")
    return fail(name, "a failing bootstrap did not raise")


def case_19_production_assembly_and_recovery() -> Result:
    name = "case_19_production_assembly_and_recovery"
    database = FakeDatabase()
    environ = {
        "ADCOS_ENVIRONMENT": "production",
        "ADCOS_DATABASE_URL": "postgresql://user:pw@neon.example/db?sslmode=require",
        "ADCOS_ISSUANCE_KEY": "00" * 32,
    }
    with tempfile.TemporaryDirectory() as tmp:
        services = build_production_services(
            environ=environ,
            journal_dir=Path(tmp),
            connection_factory=fake_factory(database),
        )
        if services.mode != "production":
            return fail(name, "mode is %r" % services.mode)
        from runtime.demo import run_contract_fulfillment_demo
        from protocol.canonicalization import canonical_json_bytes

        document_one = run_contract_fulfillment_demo(services)
        body_one = canonical_json_bytes(document_one)
        for table in (
            "adcos_api_journal",
            "adcos_contract_journal",
            "adcos_evidence_journal",
        ):
            if database.count(table) == 0:
                return fail(name, "no durable rows landed in %s" % table)
        # a SECOND assembly over the same durable state (recovery)
        services_two = build_production_services(
            environ=environ,
            journal_dir=Path(tmp) / "second",
            connection_factory=fake_factory(database),
        )
        document_two = run_contract_fulfillment_demo(services_two)
        body_two = canonical_json_bytes(document_two)
        if body_one != body_two:
            return fail(name, "the recovered demonstration diverged")
        if services_two.contracts.journal_digest() != services.contracts.journal_digest():
            return fail(name, "the recovered contract fold diverged")
        return ok(
            name,
            "production mode: durable rows in all three journals; recovery "
            "reproduces the byte-identical demonstration",
        )


def case_20_production_backend_failure_aborts_build() -> Result:
    name = "case_20_production_backend_failure_aborts_build"
    environ = {
        "ADCOS_ENVIRONMENT": "production",
        "ADCOS_DATABASE_URL": "postgresql://user:pw@neon.example/db",
        "ADCOS_ISSUANCE_KEY": "00" * 32,
    }
    try:
        build_production_services(
            environ=environ,
            connection_factory=fake_factory(FakeDatabase(), connect_error="unreachable"),
        )
    except PostgresBackendError as error:
        if error.reason_code not in ("backend-unavailable", "schema-error"):
            return fail(name, "wrong reason: %s" % error.reason_code)
        return ok(name, "a dead backend ABORTS the production build (no fallback)")
    except Exception as error:  # noqa: BLE001
        return fail(name, "wrong error type: %r" % (error,))
    return fail(name, "the production build silently succeeded")


def case_21_production_requires_issuance_key() -> Result:
    name = "case_21_production_requires_issuance_key"
    from runtime.asgi import RuntimeBoundaryError

    environ = {
        "ADCOS_ENVIRONMENT": "production",
        "ADCOS_DATABASE_URL": "postgresql://user:pw@neon.example/db",
    }
    try:
        build_production_services(
            environ=environ,
            connection_factory=fake_factory(FakeDatabase()),
        )
    except RuntimeBoundaryError as error:
        if error.reason_code != "config-invalid":
            return fail(name, "wrong reason: %s" % error.reason_code)
        return ok(name, "a missing ADCOS_ISSUANCE_KEY fails closed (no default)")
    return fail(name, "a missing issuance key was silently accepted")


def case_22_production_environment_requires_database() -> Result:
    name = "case_22_production_environment_requires_database"
    from runtime.asgi import RuntimeBoundaryError

    try:
        build_production_services(
            environ={"ADCOS_ENVIRONMENT": "production"},
            connection_factory=fake_factory(FakeDatabase()),
        )
    except RuntimeBoundaryError as error:
        if error.reason_code != "config-invalid":
            return fail(name, "wrong reason: %s" % error.reason_code)
        if "in-memory" not in error.message and "durable" not in error.message:
            return fail(name, "the failure did not explain the durable mandate")
        return ok(name, "production environment without a database fails closed")
    return fail(name, "a production environment without a database was accepted")


def case_23_file_store_semantics_parity() -> Result:
    name = "case_23_file_store_semantics_parity"
    # the postgres ApiStore must match the FILE store's read semantics
    # exactly: splitlines() of the newline-terminated journal.
    with tempfile.TemporaryDirectory() as tmp:
        from developerapi.journal import FileApiStore

        file_store = FileApiStore(Path(tmp) / "journal.jsonl")
        for line in _api_lines():
            file_store.append_line(line)
        database = FakeDatabase()
        pg_store = PostgresApiStore(connection_factory=fake_factory(database))
        pg_store.ensure_schema()
        for line in _api_lines():
            pg_store.append_line(line)
        if file_store.read_lines() != pg_store.read_lines():
            return fail(
                name,
                "divergence: %r != %r"
                % (file_store.read_lines(), pg_store.read_lines()),
            )
        if file_store.read_lines() != [line.rstrip("\n") for line in _api_lines()]:
            return fail(name, "the file baseline itself is unexpected")
        return ok(name, "read_lines() matches FileApiStore exactly")


def case_24_memory_store_not_silently_substituted() -> Result:
    name = "case_24_memory_store_not_silently_substituted"
    # structural: the postgres adapters NEVER wrap or fall back to the
    # in-memory stores; a broken backend surfaces the typed error.
    database = FakeDatabase()
    journal = _contract_journal_store(database)
    with tempfile.TemporaryDirectory() as tmp:
        store = journal.materialize_store(Path(tmp) / "cj.jsonl")
        if not isinstance(store, ContractStore):
            return fail(name, "the materialized store is not a ContractStore")
        connection = store._postgres._connect()
        connection.fail_on_marker = "INSERT INTO adcos_contract_journal"
        before = database.count("adcos_contract_journal")
        try:
            _drive_one_contract_command(store)
        except PostgresBackendError as error:
            if error.backend != "postgres":
                return fail(name, "backend not named: %r" % error.backend)
            if database.count("adcos_contract_journal") != before:
                return fail(name, "state changed despite the failure")
            return ok(name, "a failing durable append surfaces the typed error")
        except ContractError as error:
            return fail(name, "persist failure misclassified: %s" % error.code)
    return fail(name, "the failing append did not raise")


_CASES = (
    case_01_lazy_import_discipline,
    case_02_typed_error_surface,
    case_03_config_invalid_url,
    case_04_config_invalid_missing_url,
    case_05_api_store_round_trip,
    case_06_api_store_ordering_by_seq,
    case_07_api_store_newline_discipline,
    case_08_backend_failure_is_typed_never_fallback,
    case_09_read_failure_is_typed,
    case_10_health_probe,
    case_11_contract_journal_round_trip,
    case_12_append_lines_single_transaction,
    case_13_contract_journal_namespaces,
    case_14_materialize_store_and_dual_persistence,
    case_15_lock119_secret_rejected_before_durable_row,
    case_16_evidence_journal_round_trip,
    case_17_gateway_recovery_over_durable_rows,
    case_18_schema_error_is_typed,
    case_19_production_assembly_and_recovery,
    case_20_production_backend_failure_aborts_build,
    case_21_production_requires_issuance_key,
    case_22_production_environment_requires_database,
    case_23_file_store_semantics_parity,
    case_24_memory_store_not_silently_substituted,
)


def main() -> int:
    print("ADCOS deployment persistence self-test (Neon durable adapter contract)")
    print("=" * 78)
    results: List[Result] = []
    for case in _CASES:
        try:
            results.append(case())
        except Exception as error:  # noqa: BLE001 - the battery never crashes silently
            results.append(fail(case.__name__, "raised: %r" % (error,)))
    for name, passed, detail in results:
        print("[%s] %-52s %s" % ("ok  " if passed else "FAIL", name, detail))
    print("-" * 78)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == len(results):
        print("Result: PASS (%d/%d cases)" % (passed_count, len(results)))
        return 0
    print("Result: FAIL (%d/%d cases passed)" % (passed_count, len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
