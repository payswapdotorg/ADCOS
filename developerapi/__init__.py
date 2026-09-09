"""ADCOS developer platform package (M013 — Developer
Connectivity API, R7-CORE-001 child): the developer-facing
Connectivity API, SDK & Webhook platform, harvested from the
accepted WORK-046 era and translated onto the canonical
Architecture 1.1 authority.

Implements the M013 contract (a REFACTOR of the W046-era
surface, not a greenfield rewrite): a versioned, scoped,
idempotent, deterministic developer API boundary over the
ACCEPTED CANONICAL CONTRACT AUTHORITY (the M002 contracts
domain, DEC-0102), with signed webhook observation delivery
and an SDK that reproduces the canonical server semantics
exactly.

The developer operations the boundary supports (the frozen
Architecture 1.1 §12 developer-facing API semantics):

- creating connectivity intents (canonical contracts in
  INTENT state, technology-neutral creation cores)
- accepting provider offers (opaque TYPED REFERENCES ONLY --
  the offers authority owns the semantics)
- activating, inspecting and terminating connectivity
  contracts (the full canonical state machine)
- inspecting execution status and assurance (opaque typed
  references + the contract-recorded outcomes)
- retrieving usage semantics (the opaque usage-pricing-terms
  typed reference)
- contract-scoped leases (grant/renew/revoke)
- receiving signed webhooks (observations only)

Frozen authority boundary (LOCK-101/LOCK-114, the M013
re-bind):

- The developer platform is an INTERFACE BOUNDARY, not a new
  system authority.  It composes EXACTLY ONE canonical
  authority -- the accepted contracts domain (M002) -- through
  its PUBLIC surfaces only: the command submission
  (``ContractStore.next_record``/``merge``) and the public
  reads (contract/lease/journal projections).  It is NOT an
  identity authority, NOT a session authority, NOT a
  NetworkPath authority, NOT a routing engine, NOT a
  transport manager, NOT an eligibility authority, NOT a
  payment boundary, and NOT an offers/usage/assurance
  authority (those child domains -- M003/M005/M009 -- are
  referenced through opaque typed references ONLY; no second
  domain model, no re-implementation of their internals).
  There is no authority object, client, or private accessor
  for any of those planes anywhere in this family: the
  contract store is injected ALREADY COMPOSED by the platform.
- No network implementation objects appear in the API surface
  (LOCK-114): no sockets, adapters, transports or provider SDK
  types; execution material rides the contract's opaque
  typed references (LOCK-117: data, never authority).
- API success NEVER implies physical connectivity success.  The
  lifecycle observation keeps the distinct statements distinct
  and never fabricates or promotes physical evidence.
- Webhook delivery is an observation channel only (the retained
  W046 architecture): delivery state never becomes canonical
  business state.  The channel's DELIVERY OBLIGATION, however,
  is durable operational state of the channel itself (persisted
  before the API response, recovered across restart) --
  durability of the obligation, observational purity of the
  delivery state.
- Sandbox and production are non-interchangeable, isolated
  namespaces; sandbox results are never production or physical
  evidence.
- Developer-facing errors preserve the canonical ADCOS reason
  codes unchanged (no second reason-code authority; the table
  is re-bound to the contracts-domain vocabulary).
- The SDK contains no hidden business authority (import
  discipline is battery-audited).

Determinism discipline (the family precedent): every id,
digest, record, and response body is content-derived over
the canonical JSON profile; the ONLY time source is the
injected clock seam; no randomness, no UUIDs, no wall clock,
no network, no live credentials; secrets (credential secrets,
webhook signing secrets) are derived from the injected platform
issuance key and NEVER journaled or logged.  Canonical command
instants are REQUEST-DECLARED, so the canonical command
identity is byte-stable across idempotent retries and the
crash window closes through the canonical authority's own
duplicate discipline plus the boundary's write-ahead
idempotency holds.
"""

from __future__ import annotations

from .credentials import (
    ApplicationCredential,
    Capability,
    IssuedCredential,
    derive_application_id,
    derive_credential_secret,
    require_capability,
    secret_digest,
    verify_credential,
)
from .environments import (
    Environment,
    evidence_class,
    is_production_evidence,
    require_environment,
)
from .errors import (
    CANONICAL_REASON_HTTP_STATUS,
    REASON_HTTP_STATUS,
    RETRYABLE_REASONS,
    DeveloperApiError,
    DeveloperApiReasonCode,
)
from .gateway import (
    ApiRequest,
    ApiResponse,
    RouteSpec,
    DeveloperApiService,
    match_route,
)
from .identifiers import (
    derive_api_command_id,
    derive_request_id,
    derive_resource_id,
)
from .journal import (
    ApiStore,
    AppendOnlyApiJournal,
    CredentialRecord,
    FileApiStore,
    MemoryApiStore,
    MutationAbandonedRecord,
    MutationPendingRecord,
    MutationRecord,
    WebhookAttemptRecord,
    WebhookObligationRecord,
    WebhookQueueRecord,
    derive_record_id,
    derive_request_digest,
    fold_index,
)
from .pagination import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    decode_cursor,
    encode_cursor,
    normalize_filters,
    normalize_limit,
    paginate,
)
from .ratelimit import RateDecision, RateLimiter
from .schema import (
    API_VERSION_CURRENT,
    API_VERSION_HEADER,
    API_VERSIONS,
    ApiVersionSpec,
    FieldSpec,
    ResourceSchema,
    assert_backward_compatible,
    canonical_response_bytes,
    classify_change,
    resolve_version,
)
from . import webhooks as webhook_platform
from .webhooks import (
    DEFAULT_TIMESTAMP_TOLERANCE_SECONDS,
    EVENT_TYPES,
    MAX_DELIVERY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    SIGNATURE_ALGORITHM,
    backoff_for_attempt,
    build_observation_event,
    canonical_signing_input,
    check_timestamp_freshness,
    delivery_headers,
    derive_api_event_id,
    derive_delivery_id,
    derive_endpoint_signing_secret,
    derive_obligation_id,
    derive_webhook_key_id,
    next_attempt_at,
    sign_delivery,
    validate_endpoint_registration,
    verify_delivery_signature,
)
from .sdk import (
    DeveloperApiClient,
    DuplicateDetector,
    OrderTracker,
    SdkError,
    SdkList,
    SdkResource,
    SdkWebhookEvent,
    WebhookVerifier,
    deterministic_key,
)

__all__ = [
    # boundary model
    "ApiRequest",
    "ApiResponse",
    "RouteSpec",
    "DeveloperApiService",
    "match_route",
    # credentials / capabilities
    "ApplicationCredential",
    "Capability",
    "IssuedCredential",
    "derive_application_id",
    "derive_credential_secret",
    "require_capability",
    "secret_digest",
    "verify_credential",
    # environments
    "Environment",
    "evidence_class",
    "is_production_evidence",
    "require_environment",
    # errors (canonical reason preservation)
    "CANONICAL_REASON_HTTP_STATUS",
    "REASON_HTTP_STATUS",
    "RETRYABLE_REASONS",
    "DeveloperApiError",
    "DeveloperApiReasonCode",
    # identifiers / correlation
    "derive_api_command_id",
    "derive_request_id",
    "derive_resource_id",
    # journal (durable idempotency + observational deliveries)
    "ApiStore",
    "AppendOnlyApiJournal",
    "CredentialRecord",
    "FileApiStore",
    "MemoryApiStore",
    "MutationAbandonedRecord",
    "MutationPendingRecord",
    "MutationRecord",
    "WebhookAttemptRecord",
    "WebhookObligationRecord",
    "WebhookQueueRecord",
    "derive_record_id",
    "derive_request_digest",
    "fold_index",
    # pagination
    "DEFAULT_PAGE_LIMIT",
    "MAX_PAGE_LIMIT",
    "decode_cursor",
    "encode_cursor",
    "normalize_filters",
    "normalize_limit",
    "paginate",
    # rate limiting
    "RateDecision",
    "RateLimiter",
    # schema (the versioned API contract)
    "API_VERSION_CURRENT",
    "API_VERSION_HEADER",
    "API_VERSIONS",
    "ApiVersionSpec",
    "FieldSpec",
    "ResourceSchema",
    "assert_backward_compatible",
    "canonical_response_bytes",
    "classify_change",
    "resolve_version",
    # webhooks (observation channel)
    "webhook_platform",
    "DEFAULT_TIMESTAMP_TOLERANCE_SECONDS",
    "EVENT_TYPES",
    "MAX_DELIVERY_ATTEMPTS",
    "RETRY_BACKOFF_SECONDS",
    "SIGNATURE_ALGORITHM",
    "backoff_for_attempt",
    "build_observation_event",
    "canonical_signing_input",
    "check_timestamp_freshness",
    "delivery_headers",
    "derive_api_event_id",
    "derive_delivery_id",
    "derive_endpoint_signing_secret",
    "derive_obligation_id",
    "derive_webhook_key_id",
    "next_attempt_at",
    "sign_delivery",
    "validate_endpoint_registration",
    "verify_delivery_signature",
    # SDK
    "DeveloperApiClient",
    "DuplicateDetector",
    "OrderTracker",
    "SdkError",
    "SdkList",
    "SdkResource",
    "SdkWebhookEvent",
    "WebhookVerifier",
    "deterministic_key",
]
