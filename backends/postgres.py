"""The Neon PostgreSQL durable adapter of the ADCOS deployment
(DEC-0126 bounded scope; stdlib only at import time).

THE ADAPTER MOVES JOURNAL BYTES — NEVER COMPUTES STATE. Every
canonical fold stays inside the ACCEPTED authorities: the
:class:`~contracts.store.ContractStore` re-fold on construction IS the
recovery, the :class:`~evidence.store.EvidenceStore` fold likewise,
and the developer-API journal's hash chain + idempotency fold lives in
:class:`~developerapi.journal.AppendOnlyApiJournal`. This adapter
round-trips the persisted journal lines as durable rows and
materializes the local JSONL files the accepted stores re-fold; there
is NO second state computation, NO schema interpretation, NO
canonical semantics here (LOCK-101/LOCK-117 preserved structurally).

Fail-closed discipline (the deployment design mandate): every backend
failure raises :class:`PostgresBackendError` with a machine-readable
``reason_code`` and ``backend = "postgres"`` — a database failure is
EXPLICIT and OBSERVABLE, NEVER a silent fallback to in-memory
canonical state (free-tier quota exhaustion included).

Imports: pure standard library at module import time. The ``pg8000``
driver (pure-Python PostgreSQL DB-API) is imported LAZILY inside
:func:`_real_connection_factory` ONLY when a real connection is
actually attempted (the established optional-dependency pattern of
``tools/service_selftest.py``); importing this module never requires
any third-party package, and the CI batteries run the full adapter
contract against deterministic fake connections — no Postgres, no
network.

Tables (minimal schema; the journal streams are single-stream by the
ABC's own semantics):

- ``adcos_api_journal(seq BIGSERIAL PRIMARY KEY, line TEXT NOT NULL)``
  — the developer-API boundary journal lines (idempotency ledger +
  webhook records; append-only, ordered by ``seq``);
- ``adcos_contract_journal(namespace TEXT NOT NULL DEFAULT 'default',
  seq BIGSERIAL, line TEXT, PRIMARY KEY(namespace, seq))`` — the
  canonical contract command-journal lines (append-only per
  namespace, ordered by ``seq``);
- ``adcos_evidence_journal(namespace TEXT NOT NULL DEFAULT 'default',
  seq BIGSERIAL, line TEXT, PRIMARY KEY(namespace, seq))`` — the typed
  evidence-record journal lines.

LOCK-119 discipline is PRESERVED STRUCTURALLY: every line this
adapter persists passes through the ACCEPTED store's own serialization
+ secret scan first (the backed stores call ``super()._persist`` —
the real accepted persist path with its LOCK-119 line scan — BEFORE
the durable row is appended), so secret-shaped material is rejected
by the store exactly as it is without any backend adapter in place.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, Sequence
from urllib.parse import unquote, urlparse

from contracts.store import CommandRecord, ContractStore

from developerapi.errors import DeveloperApiError, DeveloperApiReasonCode
from developerapi.journal import ApiStore

from evidence.store import EvidenceStore

__all__ = [
    "PostgresBackendError",
    "PostgresApiStore",
    "PostgresContractJournal",
    "PostgresEvidenceJournal",
]

#: The reason codes of the postgres backend (machine-readable).
REASON_BACKEND_UNAVAILABLE = "backend-unavailable"
REASON_CONFIG_INVALID = "config-invalid"
REASON_SCHEMA_ERROR = "schema-error"

#: The backend identity carried by every failure of this adapter.
BACKEND_NAME = "postgres"

#: The connection protocol this adapter drives (pg8000's DB-API
#: surface): ``cursor()`` -> cursor with ``execute(sql, params)`` /
#: ``fetchall()`` / ``close()``; plus ``commit()`` / ``rollback()``.
#: The batteries inject deterministic fakes implementing exactly this
#: minimal protocol — that is the whole seam.
ConnectionFactory = Callable[[], Any]


class PostgresBackendError(Exception):
    """A typed postgres-backend failure (explicit, never silent).

    ``reason_code`` is one of ``"backend-unavailable"`` (connect /
    execute / commit failure — includes a missing driver and quota
    exhaustion), ``"config-invalid"`` (a malformed connection URL) or
    ``"schema-error"`` (the DDL bootstrap failed).
    """

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.backend = BACKEND_NAME
        self.message = message


# ---------------------------------------------------------------------------
# The connection seam (lazy pg8000; injectable factory for the batteries)
# ---------------------------------------------------------------------------


def _pin_stdlib_platform_for_driver() -> None:
    """Pin the STDLIB ``uuid``/``platform`` pair for the driver import.

    The repository root carries the accepted top-level ``platform/``
    domain package (consumed by ``composition/world.py`` and the domain
    batteries), and deployment runtimes place the repository root BEFORE
    the stdlib on ``sys.path`` (Vercel's Python functions; any cwd/``-m``
    execution from the root).  The pg8000 import chain (``converters``
    does ``from uuid import UUID``; stdlib ``uuid.py`` calls
    ``platform.system()`` at module level) would resolve the DOMAIN
    package instead — either straight off ``sys.path`` or from the
    ``sys.modules`` cache once ``composition.world`` has loaded it —
    and crash with ``AttributeError: module 'platform' has no attribute
    'system'``.

    The pin: with any cached domain ``platform`` module temporarily
    swapped out of ``sys.modules`` and the repository root temporarily
    masked off ``sys.path``, import the stdlib ``uuid`` (whose module
    body then binds the STDLIB ``platform`` by direct reference), then
    restore the domain package and the path exactly as they were.  The
    stdlib ``uuid`` keeps its own reference forever after, so the pin is
    idempotent and needs no further masking on later connections.  The
    accepted domain package is never modified — only the stdlib
    resolution is pinned for the driver's import window.
    """
    modules = sys.modules
    cached_uuid = modules.get("uuid")
    if (
        cached_uuid is not None
        and isinstance(getattr(cached_uuid, "__file__", ""), str)
        and cached_uuid.__file__.endswith("uuid.py")
        and "site-packages" not in cached_uuid.__file__
    ):
        # the stdlib uuid is already cached: its module body imported
        # (and successfully called) the platform it needs at ITS import
        # time, and holds that reference directly — the driver import is
        # already safe regardless of what ``platform`` resolves to now.
        return
    repo_root = Path(__file__).resolve().parent.parent
    saved_platform = modules.pop("platform", None)
    saved_path = list(sys.path)
    try:
        masked: list = []
        for entry in saved_path:
            text = str(entry)
            if text in ("", "."):
                try:
                    if Path(".").resolve() == repo_root:
                        continue
                except OSError:
                    pass
                masked.append(entry)
                continue
            try:
                if Path(text).resolve() == repo_root:
                    continue
            except OSError:
                pass
            masked.append(entry)
        sys.path[:] = masked
        import uuid as _stdlib_uuid  # noqa: F401 - the pinned import
    finally:
        sys.path[:] = saved_path
        if saved_platform is not None:
            modules["platform"] = saved_platform
        else:
            # leave no stdlib platform cached: the accepted domain
            # ``platform`` package must stay importable by its own
            # consumers (composition/world.py) through sys.path
            modules.pop("platform", None)


def _real_connection_factory(url: str) -> Callable[[], Any]:
    """Build the real connection factory from a Neon-style URL.

    ``postgres://`` or ``postgresql://`` scheme; the driver is imported
    LAZILY here (never at module import time). TLS is enabled by
    default (Neon requires it); ``?sslmode=disable`` opts out.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise PostgresBackendError(
            REASON_CONFIG_INVALID,
            "ADCOS_DATABASE_URL must use the postgres:// or postgresql:// "
            "scheme (found %r)" % parsed.scheme,
        )
    if not parsed.hostname:
        raise PostgresBackendError(
            REASON_CONFIG_INVALID, "ADCOS_DATABASE_URL carries no host"
        )

    def _connect() -> Any:
        try:
            import ssl as _ssl

            _pin_stdlib_platform_for_driver()
            import pg8000.dbapi  # the lazy third-party import site
        except ImportError as error:
            raise PostgresBackendError(
                REASON_BACKEND_UNAVAILABLE,
                "the pg8000 PostgreSQL driver is not installed "
                "(pip install pg8000): %s" % error,
            ) from None
        kwargs: dict = {
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or "") or None,
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": (parsed.path or "/").lstrip("/"),
        }
        if "sslmode=disable" not in (parsed.query or ""):
            kwargs["ssl_context"] = _ssl.create_default_context()
        try:
            return pg8000.dbapi.connect(**kwargs)
        except Exception as error:  # noqa: BLE001 - typed, never silent
            raise PostgresBackendError(
                REASON_BACKEND_UNAVAILABLE,
                "cannot connect to the Neon PostgreSQL backend: %s" % error,
            ) from None

    return _connect


def connection_factory_from_env(
    environ: Optional[Mapping[str, str]] = None,
) -> Callable[[], Any]:
    """Resolve the real connection factory from ``ADCOS_DATABASE_URL``
    (``environ`` defaults to ``os.environ``; a missing variable raises
    the typed config error — this factory is only called in production
    mode)."""
    source = os.environ if environ is None else environ
    url = source.get("ADCOS_DATABASE_URL", "")
    if not url:
        raise PostgresBackendError(
            REASON_CONFIG_INVALID,
            "ADCOS_DATABASE_URL is not set (production mode requires the "
            "Neon PostgreSQL connection string)",
        )
    return _real_connection_factory(url)


# ---------------------------------------------------------------------------
# The shared DB-API access core (the tiny _execute seam)
# ---------------------------------------------------------------------------


class _PostgresAccess:
    """The shared connection + execution core of the postgres adapters.

    ONE lazily-opened connection per adapter instance; every statement
    goes through one cursor's ``execute(sql, params)``; every mutation
    is committed explicitly; every failure rolls back and raises the
    typed backend error. The batteries' fakes implement exactly this
    minimal protocol.
    """

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        connection_factory: Optional[ConnectionFactory] = None,
    ) -> None:
        if connection_factory is None:
            if not url:
                raise PostgresBackendError(
                    REASON_CONFIG_INVALID,
                    "the postgres adapter requires a connection URL or an "
                    "injectable connection factory",
                )
            connection_factory = _real_connection_factory(url)
        self._connection_factory = connection_factory
        self._connection: Optional[Any] = None

    # -- the seam ---------------------------------------------------------

    def _connect(self) -> Any:
        if self._connection is None:
            self._connection = self._connection_factory()
        return self._connection

    def _execute(
        self, sql: str, params: Sequence[Any] = (), *, commit: bool = False
    ) -> List[Any]:
        """Execute ONE statement; return the fetched rows; commit when
        asked. Any failure (including the connection attempt itself)
        rolls the transaction back and raises the typed backend error
        (fail closed)."""
        cursor = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            cursor.execute(sql, tuple(params))
            # DB-API 2.0 contract: ``description`` is None when the
            # statement produces no result set (DDL, INSERT without
            # RETURNING).  pg8000 raises ProgrammingError if fetchall
            # is forced on such a statement — fetch conditionally.
            if cursor.description is None:
                rows: List[Any] = []
            else:
                rows = list(cursor.fetchall() or ())
            cursor.close()
            if commit:
                connection.commit()
            return rows
        except PostgresBackendError:
            self._rollback()
            raise
        except Exception as error:  # noqa: BLE001 - typed, never silent
            self._rollback()
            raise PostgresBackendError(
                REASON_BACKEND_UNAVAILABLE,
                "postgres statement failed (%s): %s" % (sql.split()[0], error),
            ) from None
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:  # noqa: BLE001 - cleanup only
                    pass

    def _execute_batch(
        self, sql: str, params_list: Sequence[Sequence[Any]]
    ) -> None:
        """Execute MANY statements inside ONE transaction (all-or-
        nothing: a single commit after every statement succeeded; any
        failure — including the connection attempt — rolls the whole
        batch back and raises the typed error)."""
        cursor = None
        try:
            connection = self._connect()
            cursor = connection.cursor()
            for params in params_list:
                cursor.execute(sql, tuple(params))
            cursor.close()
            connection.commit()
        except Exception as error:  # noqa: BLE001 - typed, never silent
            self._rollback()
            raise PostgresBackendError(
                REASON_BACKEND_UNAVAILABLE,
                "postgres batch failed (%s): %s" % (sql.split()[0], error),
            ) from None
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:  # noqa: BLE001 - cleanup only
                    pass

    def _rollback(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.rollback()
        except Exception:  # noqa: BLE001 - best-effort rollback
            pass

    # -- schema + health ---------------------------------------------------

    def ensure_schema(self, ddl: Sequence[str]) -> None:
        """Apply the idempotent DDL bootstrap (CREATE TABLE IF NOT
        EXISTS); a failure raises the typed schema error."""
        try:
            for statement in ddl:
                self._execute(statement, commit=True)
        except PostgresBackendError as error:
            raise PostgresBackendError(
                REASON_SCHEMA_ERROR,
                "the postgres schema bootstrap failed: %s" % error.message,
            ) from None

    def health(self) -> Mapping[str, Any]:
        """The readiness probe: ``SELECT 1`` through the real seam."""
        try:
            rows = self._execute("SELECT 1", commit=False)
        except PostgresBackendError as error:
            return {"state": "unavailable", "detail": error.message}
        if rows and list(rows[0])[0] == 1:
            return {"state": "ready", "detail": ""}
        return {"state": "unavailable", "detail": "unexpected probe result"}


def _journal_line(record: Any) -> str:
    """The canonical JSONL line of one accepted store record (the SAME
    serialization the accepted stores' own persist paths write — bytes
    only, never state)."""
    return json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# The developer-API journal adapter (the ApiStore seam)
# ---------------------------------------------------------------------------

_API_JOURNAL_DDL = (
    "CREATE TABLE IF NOT EXISTS adcos_api_journal ("
    "seq BIGSERIAL PRIMARY KEY, line TEXT NOT NULL)",
)


class PostgresApiStore(ApiStore, _PostgresAccess):
    """The durable ``ApiStore`` over Neon PostgreSQL rows.

    Matches the REAL ABC surface from ``developerapi.journal``
    EXACTLY: ``append_line(line)`` (newline-terminated; the same
    ``STORE_FAILED`` rejection the accepted stores raise on a
    non-newline line) and ``read_lines()`` (the full journal, in
    ``seq`` order — byte-identical to the file store's splitlines()).
    Durable rows replace the JSONL file; the hash chain, the
    idempotency fold and every record semantic stay in the ACCEPTED
    :class:`~developerapi.journal.AppendOnlyApiJournal`.
    """

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        connection_factory: Optional[ConnectionFactory] = None,
    ) -> None:
        _PostgresAccess.__init__(
            self, url=url, connection_factory=connection_factory
        )

    def ensure_schema(self) -> None:  # type: ignore[override]
        _PostgresAccess.ensure_schema(self, _API_JOURNAL_DDL)

    def append_line(self, line: str) -> None:
        if not isinstance(line, str) or not line.endswith("\n"):
            raise DeveloperApiError(
                DeveloperApiReasonCode.STORE_FAILED,
                "journal lines must be newline-terminated",
            )
        # the newline is the FILE framing of the accepted stores; the
        # durable row carries the line content exactly
        # (read_lines() then matches FileApiStore.read_lines()
        # byte-for-byte: splitlines() semantics).
        content = line[:-1] if line.endswith("\n") else line
        self._execute_batch(
            "INSERT INTO adcos_api_journal (line) VALUES (%s)",
            ((content,),),
        )

    def read_lines(self) -> List[str]:
        rows = self._execute(
            "SELECT line FROM adcos_api_journal ORDER BY seq"
        )
        return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# The canonical contract-journal round-trip
# ---------------------------------------------------------------------------

_CONTRACT_JOURNAL_DDL = (
    "CREATE TABLE IF NOT EXISTS adcos_contract_journal ("
    "namespace TEXT NOT NULL DEFAULT 'default', "
    "seq BIGSERIAL, "
    "line TEXT, "
    "PRIMARY KEY(namespace, seq))",
)


class _PgBackedContractStore(ContractStore):
    """A :class:`~contracts.store.ContractStore` whose journal persists
    to BOTH the local JSONL file (through the ACCEPTED persist path —
    LOCK-119 scan included) AND the postgres journal rows.

    The subclass overrides ONLY the persist hook: the fold, the merge
    discipline, the secret scan and every read stay 100% inside the
    accepted implementation (composition BY REFERENCE — the accepted
    module is untouched). The adapter moves journal bytes; it never
    computes state.
    """

    def __init__(self, journal_path: Path, postgres: "PostgresContractJournal") -> None:
        self._postgres = postgres
        ContractStore.__init__(self, journal_path=journal_path)

    def _persist(self, record: CommandRecord) -> None:
        # 1. the ACCEPTED persist path: LOCK-119 secret scan + the
        #    local JSONL append + fsync (a secret-shaped line is
        #    rejected HERE, before any durable row exists);
        # 2. the durable row (fail closed: a backend failure raises
        #    the typed postgres error — never a silent fallback; the
        #    next materialize-from-postgres re-folds the journal
        #    prefix WITHOUT the un-acked line, so recovery rolls the
        #    fold back rather than inventing state).
        ContractStore._persist(self, record)
        self._postgres.append_lines([_journal_line(record)])


class PostgresContractJournal(_PostgresAccess):
    """The canonical contract-journal round-trip over Neon PostgreSQL.

    - :meth:`load_lines` — the namespace's journal lines in ``seq``
      order (byte-exact round-trip);
    - :meth:`append_lines` — ONE transaction appending every line
      (all-or-nothing);
    - :meth:`materialize_store` — write the loaded lines to a local
      JSONL file, construct the store over it (construction-is-
      recovery: the ACCEPTED re-fold IS the state), and hook
      subsequent appends to persist to BOTH the file and postgres.

    The ContractStore fold stays the ONLY state authority: this
    adapter round-trips journal bytes, never state.
    """

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        connection_factory: Optional[ConnectionFactory] = None,
        namespace: str = "default",
    ) -> None:
        _PostgresAccess.__init__(
            self, url=url, connection_factory=connection_factory
        )
        if not isinstance(namespace, str) or not namespace:
            raise PostgresBackendError(
                REASON_CONFIG_INVALID, "the journal namespace must be non-empty"
            )
        self.namespace = namespace

    def ensure_schema(self) -> None:  # type: ignore[override]
        _PostgresAccess.ensure_schema(self, _CONTRACT_JOURNAL_DDL)

    def load_lines(self) -> List[str]:
        rows = self._execute(
            "SELECT line FROM adcos_contract_journal WHERE namespace = %s "
            "ORDER BY seq",
            (self.namespace,),
        )
        return [row[0] for row in rows]

    def append_lines(self, lines: Sequence[str]) -> None:
        """Append journal lines in ONE transaction (all-or-nothing).

        The line convention is NEWLINE-FREE: the newline is the JSONL
        file framing :meth:`materialize_store` adds when writing the
        local journal file (and the accepted stores' own persist
        serialization never emits one) — a durable row carries the
        line content exactly as :meth:`load_lines` returns it."""
        if not lines:
            return
        for line in lines:
            if not isinstance(line, str) or not line or "\n" in line:
                raise PostgresBackendError(
                    REASON_CONFIG_INVALID,
                    "journal lines must be non-empty single-line strings "
                    "(the newline is the file framing, not the content)",
                )
        self._execute_batch(
            "INSERT INTO adcos_contract_journal (namespace, line) "
            "VALUES (%s, %s)",
            tuple((self.namespace, line) for line in lines),
        )

    def materialize_store(self, journal_path: Path) -> ContractStore:
        """Materialize the live store over the durable journal rows.

        The loaded lines are written to ``journal_path`` (a FRESH
        rewrite — postgres is the durable authority of the journal
        bytes) and the store is constructed over the file; the
        accepted construction-time re-fold (tamper checks, LOCK-119
        scans, the merge discipline) validates every line exactly as
        it would a local journal.
        """
        journal_path = Path(journal_path)
        lines = self.load_lines()
        try:
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            with journal_path.open("w", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(line + "\n")
        except OSError as error:
            raise PostgresBackendError(
                REASON_BACKEND_UNAVAILABLE,
                "cannot materialize the contract journal file: %s" % error,
            ) from None
        return _PgBackedContractStore(journal_path, self)


# ---------------------------------------------------------------------------
# The typed evidence-journal round-trip
# ---------------------------------------------------------------------------

_EVIDENCE_JOURNAL_DDL = (
    "CREATE TABLE IF NOT EXISTS adcos_evidence_journal ("
    "namespace TEXT NOT NULL DEFAULT 'default', "
    "seq BIGSERIAL, "
    "line TEXT, "
    "PRIMARY KEY(namespace, seq))",
)


class _PgBackedEvidenceStore(EvidenceStore):
    """An :class:`~evidence.store.EvidenceStore` whose journal persists
    to BOTH the local JSONL file (the ACCEPTED persist path — LOCK-119
    scan included) AND the postgres journal rows. The fold, the
    idempotent ingest and every read stay 100% inside the accepted
    implementation."""

    def __init__(self, journal_path: Path, postgres: "PostgresEvidenceJournal") -> None:
        self._postgres = postgres
        EvidenceStore.__init__(self, journal_path=journal_path)

    def _persist(self, record: Any) -> None:
        EvidenceStore._persist(self, record)
        self._postgres.append_lines([_journal_line(record)])


class PostgresEvidenceJournal(_PostgresAccess):
    """The typed evidence-record journal round-trip over Neon
    PostgreSQL (the same discipline as the contract journal: the
    accepted EvidenceStore fold stays the only state authority)."""

    def __init__(
        self,
        *,
        url: Optional[str] = None,
        connection_factory: Optional[ConnectionFactory] = None,
        namespace: str = "default",
    ) -> None:
        _PostgresAccess.__init__(
            self, url=url, connection_factory=connection_factory
        )
        if not isinstance(namespace, str) or not namespace:
            raise PostgresBackendError(
                REASON_CONFIG_INVALID, "the journal namespace must be non-empty"
            )
        self.namespace = namespace

    def ensure_schema(self) -> None:  # type: ignore[override]
        _PostgresAccess.ensure_schema(self, _EVIDENCE_JOURNAL_DDL)

    def load_lines(self) -> List[str]:
        rows = self._execute(
            "SELECT line FROM adcos_evidence_journal WHERE namespace = %s "
            "ORDER BY seq",
            (self.namespace,),
        )
        return [row[0] for row in rows]

    def append_lines(self, lines: Sequence[str]) -> None:
        """Append evidence journal lines in ONE transaction (the same
        newline-free line convention as the contract journal)."""
        if not lines:
            return
        for line in lines:
            if not isinstance(line, str) or not line or "\n" in line:
                raise PostgresBackendError(
                    REASON_CONFIG_INVALID,
                    "journal lines must be non-empty single-line strings "
                    "(the newline is the file framing, not the content)",
                )
        self._execute_batch(
            "INSERT INTO adcos_evidence_journal (namespace, line) "
            "VALUES (%s, %s)",
            tuple((self.namespace, line) for line in lines),
        )

    def materialize_store(self, journal_path: Path) -> EvidenceStore:
        """Materialize the live store over the durable journal rows
        (fresh rewrite of the local JSONL; the accepted construction-
        time re-fold validates every line)."""
        journal_path = Path(journal_path)
        lines = self.load_lines()
        try:
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            with journal_path.open("w", encoding="utf-8") as handle:
                for line in lines:
                    handle.write(line + "\n")
        except OSError as error:
            raise PostgresBackendError(
                REASON_BACKEND_UNAVAILABLE,
                "cannot materialize the evidence journal file: %s" % error,
            ) from None
        return _PgBackedEvidenceStore(journal_path, self)
