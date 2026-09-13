"""The env-based assembly of the ADCOS deployment runtime.

:func:`build_app_from_env` reads the production environment contract
and assembles the ASGI application:

===========================  ==========================================
variable                     role
===========================  ==========================================
``ADCOS_ENVIRONMENT``        the environment name bound at the gateway
                             (``sandbox`` | ``production``; default
                             ``sandbox``). A ``production`` environment
                             REQUIRES the durable backend (fail closed).
``ADCOS_DATABASE_URL``       the Neon PostgreSQL connection string.
                             PRESENT -> production mode (Neon-backed
                             durable authorities: the contract journal,
                             the developer-API journal and the evidence
                             journal as durable rows). ABSENT ->
                             deterministic sandbox mode (in-memory
                             authorities).
``ADCOS_ISSUANCE_KEY``       the developer-API issuance key material
                             (hex-encoded bytes). REQUIRED in production
                             mode (fail closed — never a default). In
                             sandbox mode it is HONORED when present
                             (malformed hex still fails closed); when
                             absent the documented DEMO-ONLY key is
                             derived and a warning is logged — the
                             fallback exists ONLY in sandbox mode and is
                             never acceptable in production.
``ADCOS_REDIS_REST_URL``     Upstash Redis REST coordinates (with
``ADCOS_REDIS_REST_TOKEN``   the token). BOTH present -> the Upstash
                             rate limiter adapter (worker 2's
                             ``backends.upstash.UpstashRateLimiter``,
                             imported LAZILY only here); otherwise the
                             accepted deterministic in-process default.
``ADCOS_R2_ACCOUNT_ID``      Cloudflare R2 coordinates. Worker 2's
``ADCOS_R2_ACCESS_KEY_ID``   evidence/artifact adapter consumes them;
``ADCOS_R2_SECRET_ACCESS_KEY`` this runtime surface consumes NO R2
``ADCOS_R2_BUCKET``          seam, so they are validated (all four
                             together, fail closed) and reported in
                             readiness as DELEGATED — never probed,
                             never counted against readiness here.
===========================  ==========================================

HARD RULE (the deployment design mandate): a database failure in
production mode FAILS EXPLICITLY — the typed postgres error names the
backend and aborts the assembly (schema bootstrap, journal
materialization, the journal-first gateway recovery). There is NO
in-memory fallback for canonical state anywhere in this wiring.

Determinism: the production service clock is the sanctioned
:class:`~agent.clock.SystemClock` (the ONE accepted wall-clock site —
the live control plane's own timestamps); the contract-fulfillment
demonstration stays byte-identical for identical inputs because every
instant it surfaces is REQUEST-DECLARED (never the service clock).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional

from agent.clock import SystemClock

from contracts import ContractStore

from developerapi import Capability
from developerapi.credentials import (
    derive_application_id,
    derive_credential_secret,
)
from developerapi.errors import DeveloperApiError
from developerapi.gateway import DeveloperApiService
from developerapi.ratelimit import RateLimiter

from evidence import EvidenceStore

from backends.postgres import (
    PostgresApiStore,
    PostgresContractJournal,
    PostgresEvidenceJournal,
    connection_factory_from_env,
)

from .asgi import RuntimeBoundaryError, build_app
from .sandbox import (
    DEMO_APPLICATION_NAME,
    DEMO_DEVELOPER_ID,
    DEMO_KEY_MATERIAL,
    DEMO_VALID_UNTIL,
    SANDBOX_ISSUANCE_KEY,
    build_sandbox_execution,
    build_sandbox_services,
)
from .services import PRODUCTION_MODE, RuntimeServices

__all__ = [
    "R2_ENV_VARS",
    "build_app_from_env",
    "build_production_services",
]

#: The R2 environment contract (worker 2's consumption; validated
#: together — all or none).
R2_ENV_VARS = (
    "ADCOS_R2_ACCOUNT_ID",
    "ADCOS_R2_ACCESS_KEY_ID",
    "ADCOS_R2_SECRET_ACCESS_KEY",
    "ADCOS_R2_BUCKET",
)

#: The fixed journal-namespace of the single deployed stream.
_JOURNAL_NAMESPACE = "default"


def _validated_environment(environ: Mapping[str, str]) -> str:
    environment = environ.get("ADCOS_ENVIRONMENT", "sandbox")
    if environment not in ("sandbox", "production"):
        raise RuntimeBoundaryError(
            "config-invalid",
            "ADCOS_ENVIRONMENT %r must be 'sandbox' or 'production'" % environment,
            status=500,
        )
    return environment


def _validated_r2(environ: Mapping[str, str]) -> Mapping[str, str]:
    """Validate the R2 environment contract: all four variables
    together or none (fail closed on a partial configuration)."""
    present = [name for name in R2_ENV_VARS if environ.get(name)]
    if not present:
        return {}
    if len(present) != len(R2_ENV_VARS):
        raise RuntimeBoundaryError(
            "config-invalid",
            "the R2 environment contract is partial (present: %s; required "
            "with them: %s)"
            % (", ".join(present), ", ".join(R2_ENV_VARS)),
            status=500,
        )
    return {
        "r2": "configured; consumed by the worker-2 evidence/artifact "
        "adapter integration (not probed by this runtime surface)"
    }


def _upstash_rate_limiter(environ: Mapping[str, str]):
    """The Upstash coordination seam: worker 2's adapter, imported
    LAZILY only when its environment variables are present (the
    optional-import discipline; the batteries never require it)."""
    rest_url = environ.get("ADCOS_REDIS_REST_URL", "")
    rest_token = environ.get("ADCOS_REDIS_REST_TOKEN", "")
    if not rest_url and not rest_token:
        return None
    if not rest_url or not rest_token:
        raise RuntimeBoundaryError(
            "config-invalid",
            "the Upstash environment contract is partial "
            "(ADCOS_REDIS_REST_URL and ADCOS_REDIS_REST_TOKEN are "
            "required together)",
            status=500,
        )
    try:
        from backends.upstash import UpstashRateLimiter
    except ImportError as error:
        raise RuntimeBoundaryError(
            "upstash-unavailable",
            "the Upstash coordination adapter (backends.upstash) is not "
            "available: %s" % error,
            backend="upstash",
            status=503,
        ) from None
    return UpstashRateLimiter(rest_url=rest_url, rest_token=rest_token)


def _production_issuance_key(environ: Mapping[str, str]) -> bytes:
    """The REQUIRED production issuance key (hex; fail closed — the
    sandbox demo constant is NEVER acceptable here)."""
    material = environ.get("ADCOS_ISSUANCE_KEY", "")
    if not material:
        raise RuntimeBoundaryError(
            "config-invalid",
            "ADCOS_ISSUANCE_KEY is required in production mode "
            "(hex-encoded issuance key material; never committed, never "
            "printed)",
            status=500,
        )
    try:
        key = bytes.fromhex(material)
    except ValueError as error:
        raise RuntimeBoundaryError(
            "config-invalid",
            "ADCOS_ISSUANCE_KEY must be hex-encoded bytes: %s" % error,
            status=500,
        ) from None
    if not key:
        raise RuntimeBoundaryError(
            "config-invalid", "ADCOS_ISSUANCE_KEY is empty", status=500
        )
    return key


def _demo_credential(
    gateway: DeveloperApiService, issuance_key: bytes, environment: str
) -> str:
    """The platform-held demonstration credential secret.

    First deployment: the platform out-of-band issuance surface issues
    the credential (the secret is returned ONCE and only its digest is
    journaled). Recovered instances: the application id is
    content-derived and the secret is a deterministic function of the
    issuance key, so it is RE-DERIVED (never stored, never logged).
    """
    application_id = derive_application_id(
        environment, DEMO_DEVELOPER_ID, DEMO_APPLICATION_NAME, DEMO_KEY_MATERIAL
    )
    try:
        issued = gateway.issue_application_credential(
            developer_id=DEMO_DEVELOPER_ID,
            application_name=DEMO_APPLICATION_NAME,
            capabilities=Capability.values(),
            valid_until=DEMO_VALID_UNTIL,
            key_material=DEMO_KEY_MATERIAL,
            actor="platform",
        )
        return issued.secret
    except DeveloperApiError:
        # journal-first recovery: the credential already exists in the
        # durable boundary journal — re-derive the secret (the
        # deterministic issuance derivation; the digest in the journal
        # is its verification form).
        return derive_credential_secret(issuance_key, application_id)


def build_production_services(
    *,
    environ: Mapping[str, str],
    journal_dir: Optional[Path] = None,
    connection_factory: Optional[Any] = None,
) -> RuntimeServices:
    """Assemble the Neon-backed production services.

    Every canonical authority is durable: the contract journal, the
    developer-API journal and the evidence journal live as postgres
    rows (round-tripped by :mod:`backends.postgres` — the ACCEPTED
    folds stay the only state authorities). A backend failure raises
    the typed postgres error and ABORTS the assembly — never an
    in-memory fallback.

    ``connection_factory`` is the battery injection seam (the
    deterministic fake connection); production resolves the real
    factory from ``ADCOS_DATABASE_URL``.
    """
    environment = _validated_environment(environ)
    database_url = environ.get("ADCOS_DATABASE_URL", "")
    if environment == "production" and not database_url:
        raise RuntimeBoundaryError(
            "config-invalid",
            "ADCOS_ENVIRONMENT=production requires ADCOS_DATABASE_URL "
            "(the durable Neon backend; a production environment never "
            "runs on in-memory canonical state)",
            status=500,
        )
    if not database_url:
        raise RuntimeBoundaryError(
            "config-invalid",
            "build_production_services requires ADCOS_DATABASE_URL",
            status=500,
        )
    issuance_key = _production_issuance_key(environ)
    delegated = _validated_r2(environ)

    if connection_factory is None:
        connection_factory = connection_factory_from_env(environ)
    api_store = PostgresApiStore(connection_factory=connection_factory)
    contract_journal = PostgresContractJournal(
        connection_factory=connection_factory,
        namespace=_JOURNAL_NAMESPACE,
    )
    evidence_journal = PostgresEvidenceJournal(
        connection_factory=connection_factory,
        namespace=_JOURNAL_NAMESPACE,
    )
    # the schema bootstrap: an explicit typed failure aborts the build
    # (a broken backend never becomes in-memory state).
    api_store.ensure_schema()
    contract_journal.ensure_schema()
    evidence_journal.ensure_schema()

    if journal_dir is None:
        journal_dir = Path(tempfile.gettempdir()) / "adcos-runtime"
    journal_dir = Path(journal_dir)

    contracts: ContractStore = contract_journal.materialize_store(
        journal_dir / ("contract-journal-%s.jsonl" % _JOURNAL_NAMESPACE)
    )
    evidence: EvidenceStore = evidence_journal.materialize_store(
        journal_dir / ("evidence-journal-%s.jsonl" % _JOURNAL_NAMESPACE)
    )

    clock = SystemClock()
    upstash = _upstash_rate_limiter(environ)
    rate_limiter = upstash or RateLimiter(
        capacity=1000, refill_per_second=100, clock=clock
    )
    # journal-first recovery over the durable developer-API journal
    # (the ACCEPTED load path: byte-identical replay; construction is
    # recovery).
    gateway = DeveloperApiService.load(
        environment=environment,
        contracts=contracts,
        store=api_store,
        clock=clock,
        issuance_key=issuance_key,
        rate_limiter=rate_limiter,
    )
    demo_credential = _demo_credential(gateway, issuance_key, environment)

    backends = {"postgres": api_store, "evidence_store": evidence_journal}
    if upstash is not None:
        backends["upstash"] = upstash
    return RuntimeServices(
        environment=environment,
        mode=PRODUCTION_MODE,
        contracts=contracts,
        api_store=api_store,
        evidence=evidence,
        gateway=gateway,
        clock=clock,
        rate_limiter=rate_limiter,
        sandbox_execution=True,
        execution_factory=build_sandbox_execution,
        issuance_key=issuance_key,
        backends=backends,
        delegated_backends=delegated,
        demo_application_id=derive_application_id(
            environment, DEMO_DEVELOPER_ID, DEMO_APPLICATION_NAME, DEMO_KEY_MATERIAL
        ),
        demo_credential=demo_credential,
    )


def _sandbox_issuance_key(environ: Mapping[str, str]) -> bytes:
    """The sandbox-mode issuance key.

    ``ADCOS_ISSUANCE_KEY`` is honored when present (malformed hex still
    fails closed — an explicit, observable configuration error). When
    absent the documented DEMO-ONLY constant is derived and a warning
    is logged to stderr (sandbox mode only; production requires the
    real key through :func:`_production_issuance_key`)."""
    material = environ.get("ADCOS_ISSUANCE_KEY", "")
    if not material:
        print(
            "warning: ADCOS_ISSUANCE_KEY is not set; the sandbox runtime "
            "derived the documented DEMO-ONLY issuance key (never "
            "acceptable in production mode)",
            file=sys.stderr,
        )
        return SANDBOX_ISSUANCE_KEY
    try:
        key = bytes.fromhex(material)
    except ValueError as error:
        raise RuntimeBoundaryError(
            "config-invalid",
            "ADCOS_ISSUANCE_KEY must be hex-encoded bytes: %s" % error,
            status=500,
        ) from None
    if not key:
        raise RuntimeBoundaryError(
            "config-invalid", "ADCOS_ISSUANCE_KEY is empty", status=500
        )
    return key


def build_app_from_env(
    environ: Optional[Mapping[str, str]] = None,
):
    """Assemble the ASGI application from the environment.

    ``ADCOS_DATABASE_URL`` present -> the Neon-backed production mode
    (every canonical write lands in postgres; backend failures fail
    explicitly). Absent -> the deterministic sandbox mode (in-memory
    authorities, the documented demo-only issuance material).
    """
    source = os.environ if environ is None else environ
    database_url = source.get("ADCOS_DATABASE_URL", "")
    if database_url:
        services = build_production_services(environ=source)
    else:
        environment = _validated_environment(source)
        # validate the delegated R2 contract even in sandbox mode (fail
        # closed on partial configuration); the Upstash limiter is
        # wired in EITHER mode when its full environment contract is
        # present (the coordination seam is mode-independent).
        _validated_r2(source)
        upstash = _upstash_rate_limiter(source)
        services = build_sandbox_services(
            environment=environment,
            issuance_key=_sandbox_issuance_key(source),
            rate_limiter=upstash,
        )
    return build_app(services)
