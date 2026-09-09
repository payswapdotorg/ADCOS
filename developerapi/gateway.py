"""M013 developer platform request boundary (the gateway): the
W046-era request-admission machinery harvested and re-bound
onto the canonical Architecture 1.1 authority.

The single request-admission path of the developer API (the
retained W046 pipeline):

    authenticate (constant-time, environment-bound)
      -> resolve the API version (deterministic policy)
      -> rate limit (per application, non-mutating)
      -> authorize the scoped capability
      -> for mutations: the DURABLE WRITE-AHEAD idempotency hold
         (the request digest is journaled BEFORE any canonical
         effect exists), then the DURABLE idempotency ledger
      -> adapt to the canonical authority (the accepted
         contracts domain's PUBLIC command surface ONLY) or the
         developerapi-owned resource projection
      -> append the atomic journal record (persist-then-ack)
         -- the FINALITY POINT: the canonical mutation result
         and its response are final from here
      -> append the DURABLE webhook observation-ADMISSION
         record (the admission-time audience and emission
         identity FROZEN: ``required`` with the exact resolved
         endpoints, or terminal ``not-required`` with none) and,
         when required, its derived delivery OBLIGATION record
         (the retained W046 admission contract, unchanged)
      -> return the canonical response envelope
      -> webhook queue writes + delivery attempts STRICTLY
         AFTER the admission + obligation are durable and fully
         contained

Authority discipline (the M013 re-bind, LOCK-101/LOCK-114):

- The gateway composes EXACTLY ONE canonical authority: the
  accepted contracts domain (M002, DEC-0102) through its PUBLIC
  surface ONLY -- :class:`contracts.store.ContractStore`
  (``next_record``/``merge`` for the two-step public submit,
  and the public reads ``contract``/``contracts``/``lease``/
  ``leases``/``leases_for_contract``/``journal``).  The
  canonical command objects are built from the
  ``contracts.model`` public constructors; the boundary never
  constructs a second contract model, never re-defines a
  contract vocabulary, and never writes contract state through
  any other path.

- Offers, assurance and usage semantics are referenced, never
  re-implemented (LOCK-114): accepted offers enter through
  ``SelectOffers`` as opaque ``offer`` typed references; usage
  and pricing terms ride the contract's opaque
  ``usage-pricing-terms`` reference; assurance obligations ride
  opaque ``assurance-obligation`` references.  There is no offer
  publication route, no usage ledger read, no economic-policy
  surface: those semantics belong to the M003/M005/M009 child
  domains, which are not re-modelled here.

- No network implementation objects appear anywhere in the API
  surface (LOCK-114): the request/response member vocabulary is
  technology-neutral; execution material appears only as the
  contract's opaque ``execution-scope``/``execution-artifact``
  references (LOCK-117: data, never authority).  The developer
  never needs to know about Node, Link, gNB, UPF, radio bearer,
  provider routing or any equivalent implementation detail.

- The gateway NEVER imports the identity, session, NetworkPath,
  routing, transport, packet, payment, eligibility, commercial,
  usage, allocation, adapter, offers, assurance or evidence
  authorities.  There is no authority object, client, or private
  accessor for any of them anywhere in the developerapi family:
  the contract store is injected ALREADY COMPOSED by the
  platform (the execution/assurance/commercial authorities
  drive it through its command surface on the platform side,
  outside this package).

- API success NEVER implies physical connectivity success: the
  lifecycle observation resource keeps the distinct statements
  distinct and never fabricates or promotes physical evidence.

- Webhook emission is OBSERVATION ONLY (the retained W046
  invariant): events are built from public reads, queued before
  delivery, and delivered through the injectable transport
  seam; delivery state never feeds back into any business
  state.  The observation phase runs strictly AFTER the
  mutation's finality point, and its queue and delivery steps
  are fully contained; the DELIVERY OBLIGATION is durable and
  admission-gating exactly as in W046.

- Sandbox and production are non-interchangeable, isolated
  namespaces (retained); sandbox results are never production
  or physical evidence.

- Developer-facing errors preserve the canonical ADCOS reason
  codes unchanged (retained; the canonical table is re-bound to
  the contracts-domain ``ContractReason`` vocabulary).

- The SDK contains no hidden business authority (import
  discipline is battery-audited).

Idempotency over a content-derived canonical command identity
(the M013 crash-window discipline):

The contracts authority's command identity is content-derived
over (contract id, canonical payload, recorded instant).  The
boundary therefore requires every mutation to declare its
command instants IN THE REQUEST (``recorded_at`` /
``activated_at`` / ``granted_at`` -- deterministic, offline),
so an idempotent redelivery of the same key with the same body
derives the BYTE-IDENTICAL canonical command: the canonical
authority's own DUPLICATE discipline recognizes it and the
boundary reconstructs the response from public reads (never
re-executing the mutation).  The write-ahead pending hold
journeys the (key, digest) pair BEFORE the canonical
submission, so the same key with CHANGED content fails closed
``idempotency-conflict`` even inside the crash window, and a
semantically rejected request releases the hold (failures
never consume the key -- the retained W046 contract).

The platform administration surface (credential issuance,
endpoint secret derivation, contract observation emission,
due-delivery processing) is explicit and separated from the
request path: it is how the platform operator provisions and
operates the boundary, never an HTTP route.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from agent.clock import AgentClock

from protocol.canonicalization import canonical_json_bytes

from contracts import (
    ActivateContract,
    BeneficiaryScope,
    ConnectivityPrincipal,
    CreateContract,
    ContractError,
    ContractStore,
    GrantLease,
    HardConstraint,
    OpaqueReference,
    Provenance,
    RenewLease,
    RevokeLease,
    SelectOffers,
    TerminateContract,
    TerminationRules,
    ValidityInterval,
    build_contract,
    build_lease,
)

from . import webhooks as webhook_platform
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
from .environments import Environment, evidence_class, require_environment
from .errors import DeveloperApiError, DeveloperApiReasonCode
from .identifiers import (
    derive_api_command_id,
    derive_request_id,
    derive_resource_id,
)
from .journal import (
    ApiStore,
    ApiIndex,
    AppendOnlyApiJournal,
    CredentialRecord,
    MutationRecord,
    MutationPendingRecord,
    MutationAbandonedRecord,
    WebhookAdmissionRecord,
    WebhookAttemptRecord,
    WebhookObligationRecord,
    WebhookQueueRecord,
    derive_request_digest,
    fold_index,
)
from .pagination import normalize_filters, paginate
from .ratelimit import RateDecision, RateLimiter
from .schema import (
    API_VERSION_HEADER,
    ApiVersionSpec,
    canonical_response_bytes,
    resolve_version,
)

#: The transport seam: (endpoint_id, url, payload, headers) ->
#: (delivered, response_code).  Deterministic, offline, injected.
#: The observation channel's delivery seam only -- never a
#: connectivity implementation object (the API surface itself
#: carries no transport, socket, adapter or provider SDK type).
DeliveryTransport = Callable[
    [str, str, Mapping[str, Any], Mapping[str, str]], Tuple[bool, int]
]

#: The canonical merge statuses that carry a reconstructable
#: canonical contract for the submitted command: ``duplicate``
#: (the byte-identical command already ran -- the crash window)
#: and, for creates only, ``sequence-conflict`` (the
#: content-derived creation core already exists; create is
#: once).  Both respond with the canonical current state.
_DUPLICATE_STATUSES = frozenset({"duplicate"})

#: The merge statuses the boundary's own submit path can never
#: produce (a discipline violation implies concurrent external
#: writers or corruption): fail closed with the canonical
#: reason preserved.
_FAILURE_STATUSES = frozenset({
    "replay-stale",
    "sequence-gap",
    "id-mismatch",
    "unknown-contract",
    "journal-tamper",
})

#: The honest lifecycle statement set (never collapsed): the
#: API reports the canonical CONTRACT state machine and
#: explicitly does NOT claim connectivity or physical evidence.
_LIFECYCLE_STATEMENTS = (
    "api_request_accepted",
    "contract_intent_recorded",
    "contract_offers_selected",
    "contract_active",
    "execution_status_reported_from_contract_state",
    "assurance_reported_from_contract_recorded_outcomes",
    "physical_connectivity_not_claimed",
)

#: The honest execution-status classification, derived purely
#: from the canonical contract state machine (frozen 1.1 §11
#: reference lifecycle + §9 degraded/terminal states).
_EXECUTION_STATUS_BY_STATE = {
    "INTENT": "not-started",
    "OFFER_SELECTED": "not-started",
    "CONTRACT_ACTIVE": "permitted",
    "EXECUTION_ACTIVE": "executing",
    "DELIVERY": "delivering",
    "ASSURED": "delivered-assured",
    "DEGRADED": "degraded",
    "USAGE_FINAL": "usage-accounted",
    "SETTLEMENT_PENDING": "usage-accounted",
    "SETTLED": "closed",
    "TERMINATED": "closed",
    "EXPIRED": "closed",
    "FAILED": "closed",
}


@dataclass(frozen=True)
class ApiRequest:
    """One developer API request (the transport-independent
    representation the SDK reproduces for parity)."""

    method: str
    route: str
    body: Mapping[str, Any]
    api_version: str = ""
    idempotency_key: str = ""
    application_id: str = ""
    secret: str = ""

    def __post_init__(self) -> None:
        if self.method not in ("GET", "POST"):
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "method %r must be GET or POST" % self.method,
            )
        if not isinstance(self.route, str) or not self.route:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "route must be a non-empty string",
            )
        if not isinstance(self.body, Mapping):
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "body must be a mapping",
            )

    def canonical_body(self) -> Dict[str, Any]:
        return dict(self.body)


@dataclass(frozen=True)
class ApiResponse:
    """One developer API response (canonical body + headers)."""

    status: int
    body: Mapping[str, Any]
    headers: Mapping[str, str]

    def canonical_body_bytes(self) -> bytes:
        return canonical_response_bytes(self.body)

    def data(self) -> Any:
        return dict(self.body).get("data")

    def error(self) -> Any:
        return dict(self.body).get("error")


@dataclass(frozen=True)
class RouteSpec:
    """One declared route: operation, required capability,
    whether it mutates (idempotency required), and its request
    schema role (validated against the request's own API
    version schema set)."""

    operation: str
    capability: str
    mutation: bool = False
    schema_role: str = ""


#: The canonical route table (the Architecture 1.1 §12
#: developer-facing API semantics, LOCK-114): create intents,
#: accept offers (typed references), create/get contracts,
#: inspect execution status and assurance, retrieve usage
#: semantics, terminate, leases, and the retained webhook
#: observation surface.  The W046-era commercial-plane routes
#: (offer publication, reservations, usage/billing reads,
#: economic policies) are demoted with the 1.x surface;
#: disclosed in docs/M013-evidence.md.
ROUTES: Dict[Tuple[str, str], RouteSpec] = {
    ("GET", "application"): RouteSpec(
        "application_self", "", False, ""
    ),
    ("POST", "intents"): RouteSpec(
        "intent_create", Capability.INTENTS_WRITE, True, "intent_request"
    ),
    ("GET", "intents"): RouteSpec(
        "intents_list", Capability.INTENTS_READ, False, ""
    ),
    ("GET", "intents/{}"): RouteSpec(
        "intent_get", Capability.INTENTS_READ, False, ""
    ),
    ("GET", "intents/{}/lifecycle"): RouteSpec(
        "intent_lifecycle", Capability.INTENTS_READ, False, ""
    ),
    ("POST", "intents/{}/offers"): RouteSpec(
        "offers_accept", Capability.INTENTS_WRITE, True, "offer_selection"
    ),
    ("POST", "intents/{}/activation"): RouteSpec(
        "contract_activate", Capability.INTENTS_WRITE, True,
        "activation_request",
    ),
    ("GET", "contracts"): RouteSpec(
        "contracts_list", Capability.INTENTS_READ, False, ""
    ),
    ("GET", "contracts/{}"): RouteSpec(
        "contract_get", Capability.INTENTS_READ, False, ""
    ),
    ("GET", "contracts/{}/usage"): RouteSpec(
        "contract_usage", Capability.USAGE_READ, False, ""
    ),
    ("GET", "contracts/{}/assurance"): RouteSpec(
        "contract_assurance", Capability.ASSURANCE_READ, False, ""
    ),
    ("POST", "contracts/{}/termination"): RouteSpec(
        "contract_terminate", Capability.INTENTS_WRITE, True,
        "termination_request",
    ),
    ("POST", "contracts/{}/leases"): RouteSpec(
        "lease_grant", Capability.LEASES_WRITE, True, "lease_request"
    ),
    ("GET", "leases"): RouteSpec(
        "leases_list", Capability.LEASES_READ, False, ""
    ),
    ("GET", "leases/{}"): RouteSpec(
        "lease_get", Capability.LEASES_READ, False, ""
    ),
    ("POST", "leases/{}/renewal"): RouteSpec(
        "lease_renew", Capability.LEASES_WRITE, True, "lease_renewal"
    ),
    ("POST", "leases/{}/revocation"): RouteSpec(
        "lease_revoke", Capability.LEASES_WRITE, True, "lease_revocation"
    ),
    ("GET", "webhook-endpoints"): RouteSpec(
        "endpoints_list", Capability.WEBHOOKS_READ, False, ""
    ),
    ("POST", "webhook-endpoints"): RouteSpec(
        "endpoint_register", Capability.WEBHOOKS_WRITE, True,
        "webhook_endpoint",
    ),
    ("GET", "webhook-endpoints/{}"): RouteSpec(
        "endpoint_get", Capability.WEBHOOKS_READ, False, ""
    ),
    ("GET", "webhook-endpoints/{}/deliveries"): RouteSpec(
        "deliveries_list", Capability.WEBHOOKS_READ, False, ""
    ),
}


def match_route(method: str, route: str) -> Tuple[RouteSpec, List[str]]:
    """Match one request route against the versioned route
    table.

    The route MUST be ``/api/{version}/{resource...}``; the
    version is unambiguous (the route prefix and the version
    header must agree -- enforced by the caller before this
    match).  Unknown routes fail closed ``route-unknown``."""
    if not route.startswith("/"):
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "route must start with '/'",
        )
    parts = [part for part in route.split("/") if part]
    if len(parts) < 2 or parts[0] != "api":
        raise DeveloperApiError(
            DeveloperApiReasonCode.ROUTE_UNKNOWN,
            "route %r is not under the /api/{version}/ namespace"
            % route,
        )
    resolve_version(parts[1])  # fail closed on an unresolvable version
    target = parts[2:]
    for (route_method, route_pattern), spec in sorted(ROUTES.items()):
        if route_method != method:
            continue
        pattern_parts = route_pattern.split("/")
        if len(pattern_parts) != len(target):
            continue
        positional: List[str] = []
        matched = True
        for pattern_part, target_part in zip(pattern_parts, target):
            if pattern_part == "{}":
                positional.append(target_part)
            elif pattern_part != target_part:
                matched = False
                break
        if matched:
            return spec, positional
    raise DeveloperApiError(
        DeveloperApiReasonCode.ROUTE_UNKNOWN,
        "no %s route matches %r (declared: %s)"
        % (method, route, sorted({r[1] for r in ROUTES if r[0] == method})),
    )


# ---------------------------------------------------------------------------
# Request-body helpers (canonical material construction; the canonical
# authority owns every vocabulary, pattern, and secret scan -- the
# boundary enforces only the member-level typed-reference discipline)
# ---------------------------------------------------------------------------


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _require_mapping(value: object, label: str) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "%s must be a mapping" % label,
        )
    return dict(value)


def _require_list(value: object, label: str) -> List[Any]:
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "%s must be a list" % label,
        )
    return list(value)


def _typed_reference(
    entry: object, expected_kind: str, label: str
) -> OpaqueReference:
    """Build one canonical opaque typed reference from a request
    entry.

    The entry carries ``{ref_kind, value, provenance?}``.  The
    boundary enforces the CANONICAL reference kind for the
    member (the typed-reference discipline: offers, usage terms,
    assurance obligations, requirements, execution scope and
    signatures each ride their own frozen kind); the canonical
    authority enforces the value grammar, the provenance shape
    and the LOCK-119 secret scan (a ``ContractError`` propagates
    and is adapted by the caller).  The boundary NEVER
    interprets the referenced semantics."""
    if not isinstance(entry, Mapping):
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "%s must be a mapping carrying a typed reference "
            "(ref_kind, value, provenance?)" % label,
        )
    if entry.get("ref_kind") != expected_kind:
        raise DeveloperApiError(
            DeveloperApiReasonCode.INVALID_INPUT,
            "%s.ref_kind must be %r (the canonical reference kind "
            "for this member; found %r) -- referenced semantics "
            "ride typed references, never re-modelled fields"
            % (label, expected_kind, entry.get("ref_kind")),
        )
    return OpaqueReference.from_dict(entry)


def _typed_references(
    entries: object, expected_kind: str, label: str
) -> Tuple[OpaqueReference, ...]:
    items = _require_list(entries, label)
    return tuple(
        _typed_reference(entry, expected_kind, "%s[%d]" % (label, i))
        for i, entry in enumerate(items)
    )


def _apply_filters(
    items: List[Dict[str, Any]], filters: Mapping[str, str]
) -> List[Dict[str, Any]]:
    """Apply the declared equality filters to a page's item set
    (the pagination module's declared contract: equality filters
    over declared, indexable members)."""
    if not filters:
        return items
    return [
        item
        for item in items
        if all(str(item.get(key, "")) == value for key, value in filters.items())
    ]


@dataclass(frozen=True)
class _MutationEmission:
    """One observation emission an admitted API mutation owes
    (INTERNAL to the boundary -- never exported, never journal
    state by itself).

    The eight primary members are the COMPLETE observation
    payload: they are exactly what the durable admission record
    (:class:`journal.WebhookAdmissionRecord`) and, for a
    required admission, the obligation record
    (:class:`journal.WebhookObligationRecord`) and the queue
    records persist.  ``developer_id`` and ``endpoints`` are
    empty until the audience is RESOLVED at admission time --
    EXACTLY ONCE -- and then FROZEN into the admission record
    (post-finality: the mutation record is durable, the
    response is final, and the audience lives in the folded
    endpoint index at admission time);
    :meth:`resolved` returns the admission-ready emission.
    Building the spec re-executes NOTHING: every member comes
    from the mutation's own executed result."""

    event_type: str
    event_id: str
    occurred_at: str
    resource_kind: str
    resource_id: str
    resource_version: int
    correlation: str
    data: Mapping[str, Any]
    developer_id: str = ""
    endpoints: Tuple[str, ...] = ()

    def resolved(
        self, developer_id: str, endpoints: Tuple[str, ...]
    ) -> "_MutationEmission":
        """The admission-ready emission: the observation payload
        with its resolved audience attached."""
        return _MutationEmission(
            event_type=self.event_type,
            event_id=self.event_id,
            occurred_at=self.occurred_at,
            resource_kind=self.resource_kind,
            resource_id=self.resource_id,
            resource_version=self.resource_version,
            correlation=self.correlation,
            data=self.data,
            developer_id=developer_id,
            endpoints=endpoints,
        )


class DeveloperApiService:
    """The developer platform request boundary (the M013
    canonical surface).

    Construct fresh over an EMPTY store; recover a persisted
    store with :meth:`load` (journal-first recovery: the fold
    IS the state).  One instance is bound to exactly ONE
    environment, exactly ONE boundary journal, and exactly ONE
    canonical contract store (injected ALREADY COMPOSED by the
    platform)."""

    def __init__(
        self,
        *,
        environment: str,
        contracts: ContractStore,
        store: ApiStore,
        clock: AgentClock,
        issuance_key: bytes,
        rate_limiter: Optional[RateLimiter] = None,
        delivery_transports: Optional[Mapping[str, DeliveryTransport]] = None,
    ) -> None:
        self._environment = require_environment(environment)
        if not isinstance(contracts, ContractStore):
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "the developer API requires a ContractStore (the "
                "accepted canonical contracts authority, M002/DEC-0102, "
                "injected already-composed by the platform)",
            )
        if not isinstance(clock, AgentClock):
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "the developer API requires an AgentClock (the injected "
                "clock seam; the boundary never reads a wall clock)",
            )
        if not isinstance(issuance_key, (bytes, bytearray)) or not issuance_key:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "the developer API requires a platform issuance key",
            )
        self._contracts = contracts
        self._clock = clock
        self._issuance_key = bytes(issuance_key)
        self._rate_limiter = rate_limiter
        self._transports: Dict[str, DeliveryTransport] = dict(
            delivery_transports or {}
        )
        self._journal = AppendOnlyApiJournal(store=store)
        if self._journal.tail_sequence() != 0:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "fresh construction requires an EMPTY store; use "
                "DeveloperApiService.load for journal-first recovery",
            )
        self._index = ApiIndex()
        # Post-finality webhook containment state (health data
        # ONLY -- never business state).  The DURABLE truth for
        # webhook observations is the journal's obligation
        # records (folded into the index at load): an obligation
        # write failure is NOT contained -- it fails the
        # admission deterministically (the boundary never
        # returns a success whose observation obligation was not
        # established), and the same-key retry completes the
        # admission from durable truth alone; a queue or
        # delivery failure is contained here as incidents and
        # recovered from the durable obligation through the
        # delivery pump.  There is NO process-local observation
        # state: the incidents are process-local health data
        # only.
        self._observation_incidents: List[Dict[str, Any]] = []

    # -----------------------------------------------------------------
    # Journal-first recovery
    # -----------------------------------------------------------------

    @classmethod
    def load(
        cls,
        *,
        environment: str,
        contracts: ContractStore,
        store: ApiStore,
        clock: AgentClock,
        issuance_key: bytes,
        rate_limiter: Optional[RateLimiter] = None,
        delivery_transports: Optional[Mapping[str, DeliveryTransport]] = None,
    ) -> "DeveloperApiService":
        """Rebuild the boundary from the persisted journal bytes
        (byte-identical replay; construction is recovery)."""
        service = cls(
            environment=environment,
            contracts=contracts,
            store=_FreshStoreView(store),
            clock=clock,
            issuance_key=issuance_key,
            rate_limiter=rate_limiter,
            delivery_transports=delivery_transports,
        )
        # replay the real store through the real journal
        service._journal = AppendOnlyApiJournal(store=store)
        service._index = fold_index(service._journal.records())
        return service

    # -----------------------------------------------------------------
    # Public reads (boundary state, diagnostics)
    # -----------------------------------------------------------------

    def environment(self) -> str:
        return self._environment

    def journal_records(self) -> Tuple[Any, ...]:
        return self._journal.records()

    def journal_digest(self) -> str:
        return self._journal.journal_digest()

    def index(self) -> ApiIndex:
        return self._index

    def verify_integrity(self) -> None:
        """Re-verify the journal fold (tamper evidence): the
        live index must be exactly the journal fold."""
        folded = fold_index(self._journal.records())
        if sorted(folded.mutations) != sorted(self._index.mutations):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "live idempotency ledger diverges from the journal fold",
            )
        if sorted(folded.mutations_pending) != sorted(
            self._index.mutations_pending
        ):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "live write-ahead hold ledger diverges from the journal "
                "fold",
            )
        if sorted(folded.credentials) != sorted(self._index.credentials):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "live credential registry diverges from the journal fold",
            )
        if sorted(folded.obligations) != sorted(self._index.obligations):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "live webhook obligation index diverges from the "
                "journal fold",
            )
        if sorted(folded.admissions) != sorted(self._index.admissions):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "live webhook admission index diverges from the "
                "journal fold",
            )
        if sorted(folded.admissions_by_key) != sorted(
            self._index.admissions_by_key
        ):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "live webhook admission-by-key index diverges from "
                "the journal fold",
            )
        if sorted(folded.deliveries) != sorted(self._index.deliveries):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "live delivery index diverges from the journal fold",
            )

    # -----------------------------------------------------------------
    # Platform administration surface (never an HTTP route)
    # -----------------------------------------------------------------

    def issue_application_credential(
        self,
        *,
        developer_id: str,
        application_name: str,
        capabilities: Tuple[str, ...],
        valid_until: str,
        key_material: str,
        actor: str,
    ) -> IssuedCredential:
        """Provision one developer application credential.

        The platform's out-of-band issuance surface: the secret
        is derived deterministically from the issuance key,
        returned ONCE here, and only its DIGEST is journaled
        (secret hygiene is battery-audited)."""
        for label, value in (
            ("developer_id", developer_id),
            ("application_name", application_name),
            ("valid_until", valid_until),
            ("key_material", key_material),
            ("actor", actor),
        ):
            if not isinstance(value, str) or not value:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.INVALID_INPUT,
                    "%s must be a non-empty string" % label,
                )
        application_id = derive_application_id(
            self._environment, developer_id, application_name, key_material
        )
        if application_id in self._index.credentials:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "application %r is already issued in environment %r"
                % (application_id, self._environment),
            )
        secret = derive_credential_secret(self._issuance_key, application_id)
        issued_at = self._clock.now()
        record = CredentialRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            action="credential-issue",
            application_id=application_id,
            developer_id=developer_id,
            application_name=application_name,
            environment=self._environment,
            capabilities=tuple(capabilities),
            status="active",
            valid_until=valid_until,
            issued_at=issued_at,
            secret_digest=secret_digest(secret),
        )
        self._journal.append(record)
        self._index.apply(record)
        credential = ApplicationCredential(
            application_id=application_id,
            developer_id=developer_id,
            application_name=application_name,
            environment=self._environment,
            capabilities=tuple(capabilities),
            status="active",
            valid_until=valid_until,
            issued_at=issued_at,
            secret_digest=secret_digest(secret),
        )
        return IssuedCredential(record=credential, secret=secret)

    def revoke_application_credential(
        self, *, application_id: str, actor: str
    ) -> None:
        """Revoke one application credential (terminal)."""
        if application_id not in self._index.credentials:
            raise DeveloperApiError(
                DeveloperApiReasonCode.RESOURCE_UNKNOWN,
                "application %r is not issued in this environment"
                % application_id,
            )
        record = CredentialRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            action="credential-revoke",
            application_id=application_id,
            developer_id=self._index.credentials[application_id][
                "developer_id"
            ],
            revoked_at=self._clock.now(),
        )
        self._journal.append(record)
        self._index.apply(record)

    def endpoint_signing_secret(self, endpoint_id: str) -> str:
        """The platform-side signing secret of one webhook
        endpoint (deterministically re-derived; never journaled;
        delivered to the developer through the platform's secure
        channel, never through an API response)."""
        endpoint = self._index.endpoints.get(endpoint_id)
        if endpoint is None:
            raise DeveloperApiError(
                DeveloperApiReasonCode.RESOURCE_UNKNOWN,
                "webhook endpoint %r is not registered" % endpoint_id,
            )
        return webhook_platform.derive_endpoint_signing_secret(
            self._issuance_key, endpoint_id
        )

    def observe_contract(self, contract_id: str) -> int:
        """Emit the lifecycle observation webhook for one
        canonical contract (platform-side surface).

        Reads the canonical CURRENT public projection and emits
        ``connectivity_contract.state_changed`` when the
        contract's journal advanced beyond the last observed
        command.  Returns the number of new deliveries queued.
        The webhook system reports what ADCOS already knows; it
        never decides what ADCOS knows."""
        contract = self._developer_contract_or_none(contract_id)
        if contract is None:
            raise DeveloperApiError(
                DeveloperApiReasonCode.RESOURCE_UNKNOWN,
                "contract %r is not visible in environment %r"
                % (contract_id, self._environment),
                resource_id=contract_id,
                environment=self._environment,
            )
        latest = None
        for record in self._contracts.journal():
            if record.contract_id == contract_id:
                latest = record
        if latest is None:
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "contract %r exists but its canonical journal records "
                "are unreadable" % contract_id,
            )
        return self._emit_event(
            event_type="connectivity_contract.state_changed",
            event_id=latest.command_id,
            occurred_at=latest.recorded_at,
            resource_kind="contract",
            resource_id=contract_id,
            resource_version=sum(
                1
                for record in self._contracts.journal()
                if record.contract_id == contract_id
            ),
            correlation="",
            data=self._contract_resource(contract),
        )

    def process_due_deliveries(self) -> int:
        """Attempt every due webhook delivery (deterministic
        order: delivery id ascending).

        The DURABLE outstanding observation obligations are
        flushed FIRST (obligation-recovery: every obligation
        whose queue phase did not complete -- whether because a
        queue write failed in-process or because the process
        crashed between the obligation and the queue phase -- is
        re-queued for its still-missing endpoints; the delivery
        identity dedupe makes the flush exactly-once), then the
        delivery pass.  A still-failing store keeps the obligation
        outstanding and records an incident; an observation
        failure never surfaces as an API failure and never
        re-executes the canonical mutation.

        Due = pending (never attempted) OR failed with a
        scheduled next attempt that has arrived AND schedule
        capacity remaining.  Delivered is terminal.  Returns the
        number of attempts performed."""
        self._flush_outstanding_obligations()
        now = self._clock.now()
        performed = 0
        for delivery_id in sorted(self._index.deliveries):
            state = self._index.deliveries[delivery_id]
            if state.last_status == "delivered":
                continue
            if state.attempts >= webhook_platform.MAX_DELIVERY_ATTEMPTS:
                continue
            if state.attempts > 0:
                if not state.next_attempt_at:
                    continue
                if state.next_attempt_at > now:
                    continue
            self._attempt_delivery(delivery_id, now)
            performed += 1
        return performed

    def pending_webhook_obligations(self) -> Tuple[Mapping[str, Any], ...]:
        """The durable webhook observation obligations still
        outstanding (platform-side, never an HTTP route).

        An obligation is outstanding exactly when at least one
        of its target endpoints does not yet hold the queue
        record for its event -- the satisfaction condition is
        DERIVED from the journal fold (never separately stored),
        so the live view, a restarted view, and a replayed view
        agree by construction.  One entry per outstanding
        obligation: its identity, the full observation payload
        members, and the endpoints still pending.  This is the
        surface a restarted service (and the delivery pump)
        recovers the observation channel from -- operational
        observation-channel state, never business state."""
        out: List[Dict[str, Any]] = []
        for obligation_id in sorted(self._index.obligations):
            record = self._index.obligations[obligation_id]
            missing = [
                endpoint_id
                for endpoint_id in record.endpoints
                if webhook_platform.derive_delivery_id(
                    endpoint_id, record.event_id
                )
                not in self._index.deliveries
            ]
            if not missing:
                continue
            entry = record.to_dict()
            del entry["sequence"]
            del entry["record_id"]
            entry["pending_endpoints"] = tuple(missing)
            out.append(entry)
        return tuple(out)

    def webhook_observation_incidents(self) -> Tuple[Mapping[str, Any], ...]:
        """The contained post-finality webhook observation
        failures (health DATA only -- never business state, never
        an API response, never the mutation result).

        One incident per contained failure: the phase (the queue
        write at emission time ``emission`` / the durable
        obligation recovery flush ``obligation-retry`` / the
        delivery pass ``delivery``), the error class and message,
        the boundary reason code when the failure is a boundary
        error, and the instant.  Incidents are process-local
        health data: they are NOT journal records, they never
        survive a restart, and durable truth remains the journal
        alone.  An OBLIGATION-write failure is deliberately
        absent from this surface: it is not contained health
        data but the deterministic admission failure the caller
        receives (and the same-key retry heals)."""
        return tuple(
            dict(incident) for incident in self._observation_incidents
        )

    def _observe_after_finality(
        self, emission: _MutationEmission
    ) -> None:
        """Run the contained webhook queue and delivery phase of
        one mutation, strictly after the mutation's finality
        point AND strictly after the observation's durable
        admission state exists (the admission record and, for a
        required admission, the obligation).

        Containment semantics (the retained W046 invariant): the
        per-endpoint queue writes (dedupe by delivery identity)
        and the delivery pass may fail freely -- a queue-write
        failure is recorded as an incident and the DURABLE
        obligation keeps the observation recoverable (the pump
        re-queues the still-missing endpoints exactly once); a
        delivery-pass failure is recorded as an incident and the
        pump retries the due delivery.  NOTHING raised here ever
        reaches the caller: the mutation response was finalized
        before this method is entered, and this method must never
        raise.  The webhook system is an observer, never a
        transaction coordinator for the canonical authority."""
        try:
            self._queue_observation(
                event_id=emission.event_id,
                event_type=emission.event_type,
                occurred_at=emission.occurred_at,
                developer_id=emission.developer_id,
                resource_kind=emission.resource_kind,
                resource_id=emission.resource_id,
                resource_version=emission.resource_version,
                correlation=emission.correlation,
                data=emission.data,
                endpoints=emission.endpoints,
            )
        except Exception as error:
            # a queue write failed: the observation obligation is
            # DURABLE, so the observation is recoverable -- the
            # delivery pump's obligation flush re-queues the
            # still-missing endpoints exactly once; the incident
            # is webhook health data only.  The inline delivery
            # pass is SKIPPED (the pump owns the recovery; the
            # operator runs it).
            self._record_observation_incident("emission", error)
            return
        self._run_delivery_pass()

    def _run_delivery_pass(self) -> None:
        """The inline delivery pass (contained: a failure is
        recorded as an incident, never raised to the caller)."""
        try:
            self.process_due_deliveries()
        except Exception as error:
            # the delivery pass failed: the queue records are
            # durable and the pump will retry the due deliveries;
            # the incident is health data only
            self._record_observation_incident("delivery", error)

    def _flush_outstanding_obligations(self) -> int:
        """Flush the durable outstanding observation obligations
        (contained: never raises).

        For every obligation whose queue phase did not complete
        (in-process failure or a crash before the queue writes),
        the still-missing endpoints are queued now (the delivery
        identity dedupe makes the flush exactly-once; a partial
        multi-endpoint queue phase resumes, never repeats).  A
        still-failing store keeps the obligation outstanding and
        records an incident.  Returns the number of deliveries
        queued."""
        if not self._index.obligations:
            return 0
        queued = 0
        for obligation_id in sorted(self._index.obligations):
            record = self._index.obligations[obligation_id]
            missing = [
                endpoint_id
                for endpoint_id in record.endpoints
                if webhook_platform.derive_delivery_id(
                    endpoint_id, record.event_id
                )
                not in self._index.deliveries
            ]
            if not missing:
                continue
            try:
                queued += self._queue_observation(
                    event_id=record.event_id,
                    event_type=record.event_type,
                    occurred_at=record.occurred_at,
                    developer_id=record.developer_id,
                    resource_kind=record.resource_kind,
                    resource_id=record.resource_id,
                    resource_version=record.resource_version,
                    correlation=record.correlation,
                    data=record.data_dict(),
                    endpoints=tuple(missing),
                )
            except Exception as error:
                # the obligation is durable: it stays outstanding
                # and the next pump pass retries; the incident is
                # webhook health data only
                self._record_observation_incident(
                    "obligation-retry", error
                )
        return queued

    def _admit_observation(
        self, emission: _MutationEmission, *, key: str, request_id: str
    ) -> None:
        """The ADMISSION GATE for the durable observation-
        admission state (the retained W046 successful-admission
        contract).

        Sequence: resolve the observation's audience from the
        folded endpoint index EXACTLY ONCE (a public read; the
        resolved audience is an ADMISSION-TIME FACT and is
        FROZEN into the durable admission record -- it is never
        re-resolved for a historical mutation); persist the
        DURABLE admission record (``required`` with the exact
        frozen audience, or terminal ``not-required`` with
        none); when required, persist the DURABLE obligation
        record (the delivery duty for the frozen audience).
        BOTH writes are NOT contained: when either fails the
        boundary raises the deterministic admission failure
        (:meth:`_admission_failure`) and NEVER returns the
        success whose required observation admission was not
        established; only after the REQUIRED durable state
        exists does the fully contained queue + delivery phase
        run (:meth:`_observe_after_finality`).  The mutation
        itself stays durable either way: no rollback, no
        re-execution (the same-key retry completes the admission
        through :meth:`_complete_prior_admission`)."""
        try:
            developer_id, endpoints = self._establish_observation_admission(
                emission, key=key
            )
        except Exception as error:
            raise self._admission_failure(key, request_id, error) from error
        if not endpoints:
            # terminal not-required admission: no delivery
            # obligation exists (the admission contract is
            # satisfied).  The inline delivery pass still runs --
            # every mutation emission is the pump's deterministic
            # turn (the healthy-path journal stream is
            # clock-stable).
            self._run_delivery_pass()
            return
        # the admission (and its obligation) is durable: the
        # admission contract is satisfied for this response
        self._observe_after_finality(
            emission.resolved(developer_id, endpoints)
        )

    def _establish_observation_admission(
        self, emission: _MutationEmission, *, key: str
    ) -> Tuple[str, Tuple[str, ...]]:
        """Resolve the audience EXACTLY ONCE and persist the
        durable observation-admission state: the admission
        record (with the frozen audience and the frozen emission
        identity/payload) and, when required, the obligation
        record.  The single admission-establishment site for the
        API mutation gate (:meth:`_admit_observation`) AND the
        same-key admission completion
        (:meth:`_complete_prior_admission` -- the branch where
        no admission record exists yet and the admission is
        established NOW from the request + durable canonical
        mutation).  CAN raise: the caller owns the failure
        semantics -- in the request path a failure here is the
        deterministic admission failure, never a contained
        incident.  Returns (developer_id, frozen endpoints)."""
        developer_id, endpoints = self._resolve_observation_audience(emission)
        self._append_observation_admission(
            key=key,
            emission=emission,
            developer_id=developer_id,
            endpoints=endpoints,
        )
        if endpoints:
            self._append_observation_obligation(
                emission.resolved(developer_id, endpoints)
            )
        return developer_id, endpoints

    def _resolve_observation_audience(
        self, emission: _MutationEmission
    ) -> Tuple[str, Tuple[str, ...]]:
        """Resolve one emission's admission-time audience: the
        owning developer (empty when no owner exists) and the
        endpoints subscribed to the event type, from the folded
        endpoint index ONLY (the audience at admission time).
        The endpoints are EMPTY iff no audience exists (no
        delivery obligation; the admission is terminal
        ``not-required``).

        This is the ONLY audience-resolution site in the family
        (battery AST-audited): it is called exactly once per
        admission -- the result is frozen into the durable
        admission record and NEVER re-resolved for a historical
        mutation.  The same mutation + the same idempotency key
        therefore always resolve to the SAME historical
        admission decision; a late-registered endpoint cannot
        change what a completed admission meant."""
        developer_id = self._resource_owner(
            emission.resource_kind, emission.resource_id
        )
        if developer_id is None:
            return "", ()
        endpoints = tuple(
            endpoint_id
            for endpoint_id in sorted(self._index.endpoints)
            if self._index.endpoints[endpoint_id].get("developer_id")
            == developer_id
            and emission.event_type
            in self._index.endpoints[endpoint_id].get("event_types", ())
        )
        return developer_id, endpoints

    def _append_observation_admission(
        self,
        *,
        key: str,
        emission: _MutationEmission,
        developer_id: str,
        endpoints: Tuple[str, ...],
    ) -> None:
        """Append the durable observation-admission record
        (idempotent by admission identity; persist-then-ack):
        the admission-time audience and emission identity/payload,
        frozen as the historical admission decision.

        The single admission-record-write site for EVERY
        admission path (the API mutation gate, the same-key
        admission completion, and the platform-side observation
        surface).  CAN raise: the caller owns the failure
        semantics -- in the request path a failure here is the
        deterministic admission failure, never a contained
        incident."""
        admission_id = webhook_platform.derive_admission_id(
            self._environment, emission.event_id, emission.event_type
        )
        if admission_id in self._index.admissions:
            # the historical admission decision is already
            # durable (a prior attempt or the platform surface
            # established it): never re-decide
            return
        record = WebhookAdmissionRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            admission_id=admission_id,
            idempotency_key=key,
            event_id=emission.event_id,
            status="required" if endpoints else "not-required",
            developer_id=developer_id,
            environment=self._environment,
            event_type=emission.event_type,
            occurred_at=emission.occurred_at,
            resource_kind=emission.resource_kind,
            resource_id=emission.resource_id,
            resource_version=emission.resource_version,
            correlation=emission.correlation,
            data=emission.data,
            endpoints=endpoints,
        )
        self._journal.append(record)
        self._index.apply(record)

    def _append_observation_obligation(
        self, resolved: _MutationEmission
    ) -> None:
        """Append the durable observation obligation record
        (idempotent by obligation identity; persist-then-ack).

        The single obligation-write site for EVERY admission path
        (the API mutation gate, the same-key admission completion,
        and the platform-side observation surface).  CAN raise:
        the caller owns the failure semantics -- in the API
        mutation path a failure here is the deterministic
        admission failure, never a contained incident."""
        obligation_id = webhook_platform.derive_obligation_id(
            self._environment, resolved.event_id
        )
        if obligation_id in self._index.obligations:
            return
        record = WebhookObligationRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            obligation_id=obligation_id,
            event_id=resolved.event_id,
            event_type=resolved.event_type,
            occurred_at=resolved.occurred_at,
            environment=self._environment,
            developer_id=resolved.developer_id,
            resource_kind=resolved.resource_kind,
            resource_id=resolved.resource_id,
            resource_version=resolved.resource_version,
            correlation=resolved.correlation,
            data=resolved.data,
            endpoints=resolved.endpoints,
        )
        self._journal.append(record)
        self._index.apply(record)

    def _ensure_obligation_from_admission(
        self, admission: WebhookAdmissionRecord
    ) -> None:
        """(Re)establish the durable observation obligation for
        one REQUIRED historical admission from its FROZEN values
        alone: the stored event identity/payload and the frozen
        audience, never a current-audience re-resolution
        (idempotent by obligation identity; persist-then-ack).
        This is the recovery half of the admission record: a
        prior attempt that wrote the admission but failed the
        obligation append (its first response was the
        deterministic admission failure) heals HERE, with
        exactly the audience that was frozen at admission time
        -- endpoints registered after the admission can never
        drift into the historical audience.  The queue/delivery
        recovery of the still-missing endpoints is the delivery
        pump's own machinery (the request path establishes the
        obligation only).  CAN raise: the caller owns the
        failure semantics."""
        self._append_observation_obligation(
            _MutationEmission(
                event_type=admission.event_type,
                event_id=admission.event_id,
                occurred_at=admission.occurred_at,
                resource_kind=admission.resource_kind,
                resource_id=admission.resource_id,
                resource_version=admission.resource_version,
                correlation=admission.correlation,
                data=admission.data_dict(),
                developer_id=admission.developer_id,
                endpoints=tuple(admission.endpoints),
            )
        )

    def _admission_failure(
        self, key: str, request_id: str, error: BaseException
    ) -> DeveloperApiError:
        """The deterministic admission-failure error for a
        mutation whose required observation-admission state
        (the durable admission record, and the delivery
        obligation it requires) could not be durably recorded.

        The boundary reason is preserved from the underlying
        boundary failure (store-failed stays store-failed; an
        unexpected error class is classified store-failed); the
        detail states the contract truthfully: the canonical
        mutation is durable and was NOT rolled back or
        re-executed, the response is NOT a success, and the SAME
        request retried with the SAME idempotency key completes
        the admission and receives the canonical stored
        response."""
        if isinstance(error, DeveloperApiError):
            return DeveloperApiError(
                error.reason,
                "the webhook observation admission (admission record "
                "+ delivery obligation) for the admitted mutation "
                "(idempotency key %r) could not be durably recorded: "
                "%s.  The canonical mutation is durable and was NOT "
                "rolled back or re-executed; retry the SAME request "
                "with the SAME idempotency key to complete the "
                "admission and receive the canonical response"
                % (key, error.detail),
                request_id=request_id,
            )
        return DeveloperApiError(
            DeveloperApiReasonCode.STORE_FAILED,
            "the webhook observation admission (admission record "
            "+ delivery obligation) for the admitted mutation "
            "(idempotency key %r) could not be durably recorded: %r.  "
            "The canonical mutation is durable and was NOT rolled "
            "back or re-executed; retry the SAME request with the "
            "SAME idempotency key to complete the admission and "
            "receive the canonical response"
            % (key, error),
            request_id=request_id,
        )

    def _complete_prior_admission(
        self,
        request: ApiRequest,
        request_id: str,
        version: ApiVersionSpec,
        spec: RouteSpec,
        positional: List[str],
        credential: ApplicationCredential,
        prior: MutationRecord,
    ) -> None:
        """Complete the admission of a prior mutation on its
        idempotent replay (the historical admission decision is
        AUTHORITATIVE -- the frozen-state recovery; the retained
        W046 machinery, unchanged).

        Three -- and only three -- durable states exist for a
        prior mutation's observation admission, and each has
        exactly one deterministic behavior:

        - the admission record exists with status
          ``not-required``: the historical mutation completed
          with NO audience and that decision is TERMINAL.  The
          audience is NOT resolved, nothing is created, and no
          later endpoint registration can produce a webhook for
          the historical mutation.  Pure replay.

        - the admission record exists with status ``required``:
          the stored event/payload and the FROZEN audience are
          the admission.  The audience is NEVER re-resolved
          (``_resolve_observation_audience`` is not called for
          a historical replay at all); the missing obligation
          (a prior attempt that failed its obligation write)
          is re-established from the frozen values alone
          (:meth:`_ensure_obligation_from_admission`), so a
          retry can never acquire a different audience than
          the one frozen at admission time.  The queue/
          delivery recovery of still-missing endpoints is the
          delivery pump's own machinery, never the request
          path.

        - NO admission record exists: the prior attempt
          returned the deterministic admission failure BEFORE
          the admission record became durable (the only way a
          current-format mutation exists without its admission
          record).  The admission is established NOW from the
          request and the durable canonical mutation alone:
          the emission is re-derived from durable truth
          (:meth:`_reconstruct_emission`), the audience is
          resolved once, and the admission record (+ the
          obligation it requires) is written through the SAME
          admission gate.  Nothing re-executes.

        In every branch the cached canonical response is
        replayed by the caller ONLY after this gate passes -- a
        replay is therefore never a false success either.  No
        re-execution anywhere."""
        admission = self._index.admissions_by_key.get(
            prior.idempotency_key
        )
        if admission is not None:
            if admission.status == "not-required":
                # the terminal no-audience decision: replay
                # WITHOUT resolving the audience and WITHOUT
                # creating anything
                return
            try:
                self._ensure_obligation_from_admission(admission)
            except Exception as error:
                raise self._admission_failure(
                    prior.idempotency_key, request_id, error
                ) from error
            return
        # no admission record: the prior attempt failed at the
        # admission-record write itself; establish the admission
        # NOW from the request + the durable canonical mutation
        emission = self._reconstruct_emission(
            request, version, spec, positional, credential, prior
        )
        if emission is None:
            return
        try:
            self._establish_observation_admission(
                emission, key=prior.idempotency_key
            )
        except Exception as error:
            raise self._admission_failure(
                prior.idempotency_key, request_id, error
            ) from error

    def _reconstruct_emission(
        self,
        request: ApiRequest,
        version: ApiVersionSpec,
        spec: RouteSpec,
        positional: List[str],
        credential: ApplicationCredential,
        prior: MutationRecord,
    ) -> Optional[_MutationEmission]:
        """Deterministically re-derive the observation emission an
        admitted prior mutation owes, from durable truth alone.

        Sources (all public reads; nothing re-executes): the
        prior mutation record's stored resource projection (the
        developerapi-owned mutations), its stored canonical
        response (the observation payload -- the event data IS
        the mutation's own response data), the canonical
        contracts authority's PUBLIC journal (the command
        identity and instant of the command the byte-identical
        request body re-derives -- the command identity is
        content-derived, so re-deriving it from the digest-
        verified body is a pure read, never a submission), and
        the retry request itself (the correlation, re-derived
        over the byte-identical body the digest match
        guarantees).  Returns None when the operation owes no
        emission; fails closed JOURNAL_CORRUPT when the durable
        truth is inconsistent."""
        body = request.canonical_body()
        developer = credential.developer_id
        stored = _json_loads(prior.response_body)
        data = stored.get("data") if isinstance(stored, Mapping) else None
        if not isinstance(data, Mapping):
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "prior mutation stores a malformed canonical "
                "response body",
            )
        correlation = derive_request_id(
            self._environment,
            version.version,
            request.method,
            request.route,
            body,
        )

        if spec.operation == "endpoint_register":
            resource = prior.resource_dict()
            endpoint_id = prior.resource_id
            return _MutationEmission(
                event_type="webhook_endpoint.registered",
                event_id=webhook_platform.derive_api_event_id(
                    self._environment,
                    "webhook_endpoint",
                    endpoint_id,
                    "webhook_endpoint.registered",
                    1,
                ),
                occurred_at=str(resource.get("created_at", "")),
                resource_kind="webhook_endpoint",
                resource_id=endpoint_id,
                resource_version=1,
                correlation="",
                data=resource,
            )

        # the canonical contract/lease mutations: the command
        # identity is re-derived from the byte-identical body
        # (a pure public read through next_record -- never
        # submitted); the emission members follow the operation
        # table
        command, contract_id, recorded_at = self._rebuild_canonical_command(
            spec, body, credential, prior.idempotency_key, positional
        )
        if command is None:
            return None
        event_type = _EMISSION_EVENT_TYPES.get(spec.operation)
        if event_type is None:
            return None
        record = self._rederive_command_id(contract_id, command, recorded_at)
        if spec.operation == "intent_create":
            resource_kind, resource_id = "contract", record.contract_id
        elif spec.operation in (
            "offers_accept", "contract_activate", "contract_terminate"
        ):
            resource_kind, resource_id = "contract", contract_id
        elif spec.operation == "lease_grant":
            resource_kind = "lease"
            resource_id = _derive_lease_id(contract_id, command)
        elif spec.operation == "lease_renew":
            resource_kind = "lease"
            resource_id = _derive_lease_id(contract_id, command)
        else:  # lease_revoke
            resource_kind, resource_id = "lease", positional[0]
        return _MutationEmission(
            event_type=event_type,
            event_id=record.command_id,
            occurred_at=recorded_at,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=self._contract_journal_position(contract_id)[0],
            correlation=correlation,
            data=data,
        )

    def _rebuild_canonical_command(
        self,
        spec: RouteSpec,
        body: Mapping[str, Any],
        credential: ApplicationCredential,
        key: str,
        positional: List[str],
    ) -> Tuple[Optional[object], Optional[str], str]:
        """Rebuild the canonical command of a prior mutation from
        the digest-verified byte-identical request body (pure
        construction, never submitted -- the command identity is
        content-derived, so rebuilding it reproduces the
        historical id exactly).  Returns (command, contract_id,
        recorded_at); (None, None, "") when the operation is not
        a canonical contract/lease mutation."""
        operation = spec.operation
        if operation == "intent_create":
            command = self._build_create_command(body, credential, key)
            return command, None, _require_text(
                body.get("recorded_at"), "intent_request.recorded_at"
            )
        if operation == "offers_accept":
            contract_id = positional[0]
            command = SelectOffers(
                offers=_typed_references(
                    body.get("offers"), "offer", "offer_selection.offers"
                )
            )
            return command, contract_id, _require_text(
                body.get("recorded_at"), "offer_selection.recorded_at"
            )
        if operation == "contract_activate":
            contract_id = positional[0]
            command = ActivateContract(
                activated_at=_require_text(
                    body.get("activated_at"),
                    "activation_request.activated_at",
                ),
                signature_refs=_typed_references(
                    body.get("signature_refs"),
                    "signature",
                    "activation_request.signature_refs",
                ),
            )
            return command, contract_id, _require_text(
                body.get("activated_at"), "activation_request.activated_at"
            )
        if operation == "contract_terminate":
            contract_id = positional[0]
            command = TerminateContract(
                recorded_at=_require_text(
                    body.get("recorded_at"),
                    "termination_request.recorded_at",
                ),
                condition=_require_text(
                    body.get("condition"), "termination_request.condition"
                ),
                reason=_require_text(
                    body.get("reason"), "termination_request.reason"
                ),
            )
            return command, contract_id, _require_text(
                body.get("recorded_at"),
                "termination_request.recorded_at",
            )
        if operation == "lease_grant":
            contract_id = positional[0]
            command = GrantLease(
                granted_at=_require_text(
                    body.get("granted_at"), "lease_request.granted_at"
                ),
                not_before=_require_text(
                    body.get("not_before"), "lease_request.not_before"
                ),
                not_after=_require_text(
                    body.get("not_after"), "lease_request.not_after"
                ),
            )
            return command, contract_id, _require_text(
                body.get("granted_at"), "lease_request.granted_at"
            )
        if operation == "lease_renew":
            lease_id = positional[0]
            lease = self._developer_lease_or_none(lease_id)
            if lease is None:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.JOURNAL_CORRUPT,
                    "prior mutation references lease %r that the "
                    "canonical authority does not hold" % lease_id,
                )
            command = RenewLease(
                lease_id=lease_id,
                granted_at=_require_text(
                    body.get("granted_at"), "lease_renewal.granted_at"
                ),
                not_before=_require_text(
                    body.get("not_before"), "lease_renewal.not_before"
                ),
                not_after=_require_text(
                    body.get("not_after"), "lease_renewal.not_after"
                ),
            )
            return command, lease.contract_id, _require_text(
                body.get("granted_at"), "lease_renewal.granted_at"
            )
        if operation == "lease_revoke":
            lease_id = positional[0]
            lease = self._developer_lease_or_none(lease_id)
            if lease is None:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.JOURNAL_CORRUPT,
                    "prior mutation references lease %r that the "
                    "canonical authority does not hold" % lease_id,
                )
            command = RevokeLease(
                lease_id=lease_id,
                recorded_at=_require_text(
                    body.get("recorded_at"),
                    "lease_revocation.recorded_at",
                ),
                reason=_require_text(
                    body.get("reason"), "lease_revocation.reason"
                ),
            )
            return command, lease.contract_id, _require_text(
                body.get("recorded_at"),
                "lease_revocation.recorded_at",
            )
        return None, None, ""

    def _rederive_command_id(
        self, contract_id: Optional[str], command: object, recorded_at: str
    ) -> Any:
        """Re-derive the canonical command identity of a prior
        mutation (a PURE public read through ``next_record``:
        the record is built, never submitted -- the identity is
        content-derived, so this reproduces the historical
        command id exactly)."""
        try:
            return self._contracts.next_record(
                contract_id, command, recorded_at
            )
        except ContractError as error:
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "the canonical command identity of a prior mutation "
                "cannot be re-derived from the digest-verified body: %s"
                % error.detail,
            ) from error

    def _record_observation_incident(
        self, phase: str, error: BaseException
    ) -> None:
        """Record one contained webhook observation failure as
        health data (structured, deterministic, secret-free:
        store/journal errors carry paths and record kinds only)."""
        reason = ""
        if isinstance(error, DeveloperApiError):
            reason = error.reason
        self._observation_incidents.append(
            {
                "kind": "webhook_observation_incident",
                "phase": phase,
                "error_class": type(error).__name__,
                "error_message": str(error),
                "reason_code": reason,
                "instant": self._clock.now(),
                "observational_only": True,
            }
        )

    # -----------------------------------------------------------------
    # The request path
    # -----------------------------------------------------------------

    def handle(self, request: ApiRequest) -> ApiResponse:
        """The single request admission path.

        Canonical authority failures surfacing anywhere in the
        read or mutation paths are translated HERE with the
        exact canonical reason preserved (criterion 4)."""
        request_id = derive_request_id(
            self._environment,
            request.api_version or "",
            request.method,
            request.route,
            request.canonical_body(),
        )
        try:
            return self._handle(request, request_id)
        except DeveloperApiError as error:
            return self._error_response(request, request_id, error)
        except ContractError as error:
            return self._error_response(
                request,
                request_id,
                self._adapted_error(error, request_id=request_id),
            )

    def _handle(
        self, request: ApiRequest, request_id: str
    ) -> ApiResponse:
        # 1. the unambiguous API version (route + header must
        #    agree when both are present)
        version = self._resolve_request_version(request)
        # 2. authentication (constant-time, environment-bound)
        credential = self._authenticate(request)
        # 3. rate limiting (per application; non-mutating)
        rate = None
        if self._rate_limiter is not None:
            rate = self._rate_limiter.check(request.application_id)
        # 4. route + scoped capability
        spec, positional = match_route(request.method, request.route)
        if spec.capability:
            require_capability(credential, spec.capability)
        # 5. the mutation gate: durable idempotency
        if spec.mutation:
            return self._handle_mutation(
                request, request_id, version, spec, positional, credential, rate
            )
        return self._handle_read(
            request, request_id, version, spec, positional, credential, rate
        )

    # -- version --------------------------------------------------------

    def _resolve_request_version(self, request: ApiRequest) -> ApiVersionSpec:
        parts = [part for part in request.route.split("/") if part]
        route_version = ""
        if len(parts) >= 2 and parts[0] == "api":
            route_version = parts[1]
        header_version = request.api_version
        if header_version and route_version and header_version != route_version:
            raise DeveloperApiError(
                DeveloperApiReasonCode.VERSION_UNSUPPORTED,
                "route version %r and %s %r disagree (a request must be "
                "unambiguously attributable to one API version)"
                % (route_version, API_VERSION_HEADER, header_version),
            )
        return resolve_version(header_version or route_version)

    # -- authentication ---------------------------------------------------

    def _authenticate(self, request: ApiRequest) -> ApplicationCredential:
        entry = self._index.credentials.get(request.application_id)
        if entry is None:
            raise DeveloperApiError(
                DeveloperApiReasonCode.AUTHENTICATION_INVALID,
                "application %r is not issued in environment %r"
                % (request.application_id, self._environment),
                request_id="",
            )
        credential = ApplicationCredential(
            application_id=entry["application_id"],
            developer_id=entry["developer_id"],
            application_name=entry["application_name"],
            environment=entry["environment"],
            capabilities=tuple(entry["capabilities"]),
            status=entry["status"],
            valid_until=entry["valid_until"],
            issued_at=entry["issued_at"],
            secret_digest=entry["secret_digest"],
        )
        verify_credential(
            credential, self._environment, request.secret, self._clock
        )
        return credential

    # -- reads ------------------------------------------------------------

    def _handle_read(
        self,
        request: ApiRequest,
        request_id: str,
        version: ApiVersionSpec,
        spec: RouteSpec,
        positional: List[str],
        credential: ApplicationCredential,
        rate: Optional[RateDecision],
    ) -> ApiResponse:
        body = request.canonical_body()
        developer = credential.developer_id

        if spec.operation == "application_self":
            data = dict(credential.to_dict())
            data["kind"] = "application"
            data["evidence_class"] = evidence_class(self._environment)
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "intents_list":
            items = [
                self._contract_resource(contract)
                for contract in self._developer_contracts(developer)
                if contract.state == "INTENT"
            ]
            page, cursor, more = self._page(
                items, "contract", developer, {}, body
            )
            data = {"items": page, "next_cursor": cursor, "has_more": more}
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "intent_get":
            contract = self._developer_contract(positional[0], developer)
            return self._envelope(
                request,
                request_id,
                version,
                self._contract_resource(contract),
                rate=rate,
            )

        if spec.operation == "intent_lifecycle":
            contract = self._developer_contract(positional[0], developer)
            data = self._lifecycle_resource(contract)
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "contracts_list":
            items = [
                self._contract_resource(contract)
                for contract in self._developer_contracts(developer)
            ]
            filters = normalize_filters(body.get("filters"), ("state",))
            items = _apply_filters(items, filters)
            page, cursor, more = self._page(
                items, "contract", developer, filters, body
            )
            data = {"items": page, "next_cursor": cursor, "has_more": more}
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "contract_get":
            contract = self._developer_contract(positional[0], developer)
            return self._envelope(
                request,
                request_id,
                version,
                self._contract_resource(contract),
                rate=rate,
            )

        if spec.operation == "contract_usage":
            contract = self._developer_contract(positional[0], developer)
            data = self._usage_terms_resource(contract)
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "contract_assurance":
            contract = self._developer_contract(positional[0], developer)
            data = self._assurance_resource(contract)
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "leases_list":
            items = [
                self._lease_resource(lease)
                for lease in self._developer_leases(developer)
            ]
            filters = normalize_filters(body.get("filters"), ("state",))
            items = _apply_filters(items, filters)
            page, cursor, more = self._page(
                items, "contract_lease", developer, filters, body
            )
            data = {"items": page, "next_cursor": cursor, "has_more": more}
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "lease_get":
            lease = self._developer_lease(positional[0], developer)
            return self._envelope(
                request,
                request_id,
                version,
                self._lease_resource(lease),
                rate=rate,
            )

        if spec.operation == "endpoints_list":
            items = self._developer_endpoints(developer)
            page, cursor, more = self._page(
                items, "webhook_endpoint", developer, {}, body
            )
            data = {"items": page, "next_cursor": cursor, "has_more": more}
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "endpoint_get":
            endpoint = self._index.endpoints.get(positional[0])
            if endpoint is None or endpoint.get("developer_id") != developer:
                raise self._resource_unknown(
                    "webhook endpoint", positional[0], request_id
                )
            data = dict(endpoint)
            data["health"] = self._endpoint_health(positional[0])
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        if spec.operation == "deliveries_list":
            endpoint = self._index.endpoints.get(positional[0])
            if endpoint is None or endpoint.get("developer_id") != developer:
                raise self._resource_unknown(
                    "webhook endpoint", positional[0], request_id
                )
            items = [
                self._delivery_resource(state)
                for delivery_id, state in sorted(
                    self._index.deliveries.items()
                )
                if state.endpoint_id == positional[0]
            ]
            page, cursor, more = self._page(
                items, "webhook_delivery", developer, {}, body
            )
            data = {"items": page, "next_cursor": cursor, "has_more": more}
            return self._envelope(
                request, request_id, version, data, rate=rate
            )

        raise DeveloperApiError(
            DeveloperApiReasonCode.ROUTE_UNKNOWN,
            "operation %r is declared but not dispatched"
            % spec.operation,
        )

    # -- mutations ---------------------------------------------------------

    def _handle_mutation(
        self,
        request: ApiRequest,
        request_id: str,
        version: ApiVersionSpec,
        spec: RouteSpec,
        positional: List[str],
        credential: ApplicationCredential,
        rate: Optional[RateDecision],
    ) -> ApiResponse:
        if not request.idempotency_key:
            raise DeveloperApiError(
                DeveloperApiReasonCode.IDEMPOTENCY_KEY_REQUIRED,
                "mutations require an idempotency key "
                "(X-ADCOS-Idempotency-Key)",
            )
        key = request.idempotency_key
        body = request.canonical_body()
        digest = derive_request_digest(
            request.method,
            request.route,
            body,
            self._environment,
            credential.developer_id,
            key,
        )
        prior = self._index.mutations.get(key)
        if prior is not None:
            if prior.request_digest != digest:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.IDEMPOTENCY_CONFLICT,
                    "idempotency key %r was already admitted with a "
                    "materially different request" % key,
                )
            # the admission-completion gate: a prior mutation whose
            # observation obligation was never established (its
            # first attempt returned the deterministic admission
            # failure) is completed HERE, from durable truth alone,
            # BEFORE the cached canonical response is replayed --
            # a replay is therefore never a false success either.
            # When the obligation is already durable (the common
            # case) this gate is a pure read and grows nothing.
            self._complete_prior_admission(
                request, request_id, version, spec, positional,
                credential, prior,
            )
            # byte-identical canonical prior response
            body_out = _json_loads(prior.response_body)
            return self._response(
                int(prior.response_status),
                body_out,
                {
                    "X-ADCOS-Request-Id": request_id,
                    "X-ADCOS-API-Version": version.version,
                    "X-ADCOS-Environment": self._environment,
                    "X-ADCOS-Idempotent-Replay": "true",
                },
            )

        # the write-ahead hold (the M013 crash-window closure): a
        # prior attempt that crashed anywhere between the hold and
        # the committed record leaves the (key, digest) pair
        # durable, so the same key with CHANGED content fails
        # closed HERE -- even before any canonical submission --
        # and the same key with the SAME content completes through
        # the canonical authority's own duplicate discipline.
        pending = self._index.mutations_pending.get(key)
        if pending is not None:
            if pending.request_digest != digest:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.IDEMPOTENCY_CONFLICT,
                    "idempotency key %r is held by an uncommitted "
                    "attempt with a materially different request (the "
                    "write-ahead hold: the prior attempt may have "
                    "reached the canonical authority; the same key "
                    "never admits changed content)" % key,
                )
            # the hold exists and matches: complete it (no second
            # hold is appended)
        else:
            self._append_pending_mutation(
                key, credential, request, version, request_id, digest
            )

        # strict request validation against the request's OWN
        # version schema set (nothing durable yet for an
        # schema-invalid request -- the retained W046 contract)
        schema_role = spec.schema_role
        deprecations: Tuple[str, ...] = ()
        if schema_role:
            schema = version.schemas.get(schema_role)
            if schema is not None:
                schema.validate(body, "request body")
                deprecations = schema.deprecations_in(body)

        try:
            data, resource_kind, resource_id, resource, emission = (
                self._execute_mutation(
                    request, version, spec, positional, credential, key
                )
            )
        except DeveloperApiError as error:
            # a semantically rejected request NEVER consumes the
            # key (the retained W046 contract): the write-ahead
            # hold is released durably and the error surfaces
            self._append_abandoned_mutation(key, error.reason)
            raise
        except ContractError as error:
            # a canonical construction/submission rejection (the
            # contracts domain's own fail-closed validation):
            # adapt it with the canonical reason preserved and
            # release the write-ahead hold the same way
            adapted = self._adapted_error(error)
            self._append_abandoned_mutation(key, adapted.reason)
            raise adapted

        # FINALITY POINT: the canonical mutation is admitted, its
        # idempotency record is durable, and the envelope below is
        # THE response.  From here the webhook observation phase
        # runs (the retained W046 admission contract):
        #
        #   MutationRecord (finality)
        #       -> WebhookAdmissionRecord (the FROZEN admission-
        #          time audience: required with the exact resolved
        #          endpoints, or terminal not-required with none)
        #       -> WebhookObligationRecord (only when required)
        #       -> the successful response
        envelope = self._envelope(
            request,
            request_id,
            version,
            data,
            rate=rate,
            idempotency={"key": key, "replayed": False},
            deprecations=deprecations,
        )
        record = MutationRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            idempotency_key=key,
            application_id=credential.application_id,
            developer_id=credential.developer_id,
            method=request.method,
            route=request.route,
            api_version=version.version,
            request_id=request_id,
            request_digest=digest,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource=resource,
            response_status=envelope.status,
            response_body=canonical_json_bytes(
                dict(envelope.body)
            ).decode("utf-8"),
        )
        self._journal.append(record)
        self._index.apply(record)
        if emission is not None:
            self._admit_observation(
                emission, key=key, request_id=request_id
            )
        return envelope

    # -- the write-ahead hold sites (single site each) --------------------

    def _append_pending_mutation(
        self,
        key: str,
        credential: ApplicationCredential,
        request: ApiRequest,
        version: ApiVersionSpec,
        request_id: str,
        digest: str,
    ) -> None:
        """Append the durable write-ahead idempotency hold of one
        mutation (persist-then-execute; the single pending-write
        site).  CAN raise (store failure): nothing canonical has
        run yet -- the mutation fails store-failed with no
        side effects."""
        record = MutationPendingRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            idempotency_key=key,
            application_id=credential.application_id,
            developer_id=credential.developer_id,
            method=request.method,
            route=request.route,
            api_version=version.version,
            request_id=request_id,
            request_digest=digest,
        )
        self._journal.append(record)
        self._index.apply(record)

    def _append_abandoned_mutation(self, key: str, reason: str) -> None:
        """Append the durable release of a rejected mutation's
        write-ahead hold (persist-then-ack; the single
        abandonment-write site).  A store failure here propagates
        (store-failed): the hold remains durable and the same-key
        retry re-runs the request deterministically."""
        record = MutationAbandonedRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            idempotency_key=key,
            reason=reason,
        )
        self._journal.append(record)
        self._index.apply(record)

    # -- canonical command submission --------------------------------------

    def _submit_canonical(
        self,
        contract_id: Optional[str],
        command: object,
        recorded_at: str,
    ) -> Tuple[Any, Any]:
        """Submit one canonical command through the contracts
        authority's PUBLIC journal surface (``next_record`` +
        ``merge`` -- the two-step public submit; the boundary
        never touches private state).  Returns (the derived
        CommandRecord, the MergeResult).  Raises the adapted
        canonical error on any semantic rejection (the canonical
        reason is preserved through the boundary)."""
        try:
            record = self._contracts.next_record(
                contract_id, command, recorded_at
            )
            result = self._contracts.merge(record)
        except ContractError as error:
            raise self._adapted_error(error) from error
        return record, result

    def _require_merge_admitted(
        self, result: Any, *, contract_id: str, create: bool
    ) -> Any:
        """Classify one canonical merge outcome for a developer
        mutation.

        Success statuses and ``duplicate`` (the crash-window
        byte-identical redelivery, and for creates the
        content-identity collision under a different key)
        return the canonical contract the result carries; the
        discipline-failure statuses fail closed with the
        canonical reason preserved (the boundary's own submit
        path never produces them -- a concurrent external writer
        or corruption is the only source)."""
        status = result.status
        if status in _DUPLICATE_STATUSES or (
            create and status == "sequence-conflict"
        ):
            contract = result.contract
            if contract is not None and contract.contract_id == contract_id:
                return contract
        elif status not in _FAILURE_STATUSES and status != "sequence-conflict":
            contract = result.contract
            if contract is not None and contract.contract_id == contract_id:
                return contract
        raise self._adapted_error(
            ContractError(
                status,
                "the canonical contract authority returned %s (%s)"
                % (status, result.detail),
            )
        )

    def _build_create_command(
        self,
        body: Mapping[str, Any],
        credential: ApplicationCredential,
        key: str,
    ) -> CreateContract:
        """Build the canonical CreateContract command from the
        request body (LOCK-102/LOCK-114: the technology-neutral
        creation core; the principal is DERIVED from the
        authenticated application -- never request-supplied --
        and the provenance carries the application issuer and
        the boundary's key-derived decision reference).

        Every semantics-bearing member is canonical material:
        typed references, hard constraints, the validity window,
        the termination rules.  Deep validation (vocabularies,
        patterns, LOCK-119 secret scans) is the canonical
        authority's own; a ``ContractError`` propagates and is
        adapted by the mutation path."""
        requirements = _typed_references(
            body.get("requirements"),
            "intent-requirements",
            "intent_request.requirements",
        )
        if not requirements:
            raise DeveloperApiError(
                DeveloperApiReasonCode.INVALID_INPUT,
                "intent_request.requirements requires at least one "
                "normalized-requirements typed reference (LOCK-102: "
                "the contract's normalized requirements)",
            )
        hard_raw = body.get("hard_constraints")
        constraints = tuple(
            HardConstraint.from_dict(entry)
            for entry in (
                _require_list(
                    hard_raw, "intent_request.hard_constraints"
                )
                if hard_raw is not None
                else ()
            )
        )
        validity = ValidityInterval.from_dict(
            _require_mapping(body.get("validity"), "intent_request.validity")
        )
        termination_raw = body.get("termination")
        termination = (
            TerminationRules.from_dict(
                _require_mapping(
                    termination_raw, "intent_request.termination"
                )
            )
            if termination_raw is not None
            else None
        )
        beneficiaries_raw = body.get("beneficiaries")
        beneficiaries = tuple(
            BeneficiaryScope.from_dict(entry)
            for entry in (
                _require_list(
                    beneficiaries_raw, "intent_request.beneficiaries"
                )
                if beneficiaries_raw is not None
                else ()
            )
        )
        service_raw = body.get("service_properties")
        service_properties = (
            _typed_references(
                service_raw,
                "service-property",
                "intent_request.service_properties",
            )
            if service_raw is not None
            else ()
        )
        usage_raw = body.get("usage_pricing_terms")
        usage_pricing_terms = (
            _typed_reference(
                usage_raw,
                "usage-pricing-terms",
                "intent_request.usage_pricing_terms",
            )
            if usage_raw is not None
            else None
        )
        assurance_raw = body.get("assurance_obligations")
        assurance_obligations = (
            _typed_references(
                assurance_raw,
                "assurance-obligation",
                "intent_request.assurance_obligations",
            )
            if assurance_raw is not None
            else ()
        )
        scope_raw = body.get("execution_scope")
        execution_scope = (
            _typed_references(
                scope_raw,
                "execution-scope",
                "intent_request.execution_scope",
            )
            if scope_raw is not None
            else ()
        )
        superseded_raw = body.get("superseded_contract")
        superseded_contract = (
            _typed_reference(
                superseded_raw,
                "superseded-contract",
                "intent_request.superseded_contract",
            )
            if superseded_raw is not None
            else None
        )
        return CreateContract(
            principal=ConnectivityPrincipal(
                principal_kind="APPLICATION",
                principal_ref=credential.application_id,
            ),
            beneficiaries=beneficiaries,
            requirements=requirements,
            hard_constraints=constraints,
            validity=validity,
            service_properties=service_properties,
            usage_pricing_terms=usage_pricing_terms,
            assurance_obligations=assurance_obligations,
            execution_scope=execution_scope,
            termination=termination,
            provenance=Provenance(
                issuer="developerapi-application:%s"
                % credential.application_id,
                decision_refs=(
                    derive_api_command_id(
                        self._environment, credential.developer_id, key
                    ),
                ),
            ),
            superseded_contract=superseded_contract,
        )

    def _execute_mutation(
        self,
        request: ApiRequest,
        version: ApiVersionSpec,
        spec: RouteSpec,
        positional: List[str],
        credential: ApplicationCredential,
        key: str,
    ) -> Tuple[
        Any, str, str, Mapping[str, Any], Optional[_MutationEmission]
    ]:
        """Execute one mutation: adapt to the canonical contracts
        authority or the developerapi-owned projection.  Returns
        (response data, resource kind, resource id, resource
        mapping, webhook emission spec).

        The emission spec is a plain frozen value built from the
        mutation's own executed result (the audience is resolved
        later, at admission time); the crash-window duplicate
        branches owe the SAME emission (the canonical command id
        is content-derived and byte-stable across retries), so
        every admission door is gated by the same
        durable-obligation contract.  Adapted mutations carry
        empty resource mappings (the truth stays in the canonical
        contracts journal); the crash-window idempotency is the
        canonical authority's own (the command identity is
        content-derived over the request-declared instants)."""
        body = request.canonical_body()
        developer = credential.developer_id

        if spec.operation == "intent_create":
            recorded_at = _require_text(
                body.get("recorded_at"), "intent_request.recorded_at"
            )
            command = self._build_create_command(body, credential, key)
            record, result = self._submit_canonical(
                None, command, recorded_at
            )
            contract = self._require_merge_admitted(
                result, contract_id=record.contract_id, create=True
            )
            data = self._contract_resource(contract)
            emission = _MutationEmission(
                event_type="connectivity_intent.created",
                event_id=record.command_id,
                occurred_at=recorded_at,
                resource_kind="contract",
                resource_id=contract.contract_id,
                resource_version=self._contract_journal_position(
                    contract.contract_id
                )[0],
                correlation=derive_request_id(
                    self._environment,
                    version.version,
                    request.method,
                    request.route,
                    body,
                ),
                data=dict(data),
            )
            return dict(data), "", "", {}, emission

        if spec.operation == "endpoint_register":
            url, event_types = webhook_platform.validate_endpoint_registration(
                body.get("url"), body.get("event_types")
            )
            endpoint_id = derive_resource_id(
                self._environment, "webhook_endpoint", developer, key
            )
            resource = {
                "id": endpoint_id,
                "kind": "webhook_endpoint",
                "environment": self._environment,
                "developer_id": developer,
                "created_at": self._clock.now(),
                "api_version": version.version,
                "url": url,
                "event_types": list(event_types),
                "key_id": webhook_platform.derive_webhook_key_id(
                    endpoint_id
                ),
            }

            emission = _MutationEmission(
                event_type="webhook_endpoint.registered",
                event_id=webhook_platform.derive_api_event_id(
                    self._environment,
                    "webhook_endpoint",
                    endpoint_id,
                    "webhook_endpoint.registered",
                    1,
                ),
                occurred_at=resource["created_at"],
                resource_kind="webhook_endpoint",
                resource_id=endpoint_id,
                resource_version=1,
                correlation="",
                data=dict(resource),
            )

            return dict(resource), "webhook_endpoint", endpoint_id, resource, emission

        if spec.operation == "offers_accept":
            contract = self._developer_contract(positional[0], developer)
            recorded_at = _require_text(
                body.get("recorded_at"), "offer_selection.recorded_at"
            )
            command = SelectOffers(
                offers=_typed_references(
                    body.get("offers"), "offer", "offer_selection.offers"
                )
            )
            if not command.offers:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.INVALID_INPUT,
                    "offer_selection.offers requires at least one "
                    "accepted-offer typed reference (the offer "
                    "semantics stay the M003 authority's; this API "
                    "carries the typed references only)",
                )
            record, result = self._submit_canonical(
                contract.contract_id, command, recorded_at
            )
            contract = self._require_merge_admitted(
                result, contract_id=contract.contract_id, create=False
            )
            data = self._contract_resource(contract)
            emission = _MutationEmission(
                event_type="connectivity_contract.offers_selected",
                event_id=record.command_id,
                occurred_at=recorded_at,
                resource_kind="contract",
                resource_id=contract.contract_id,
                resource_version=self._contract_journal_position(
                    contract.contract_id
                )[0],
                correlation=derive_request_id(
                    self._environment,
                    version.version,
                    request.method,
                    request.route,
                    body,
                ),
                data=dict(data),
            )
            return dict(data), "", "", {}, emission

        if spec.operation == "contract_activate":
            contract = self._developer_contract(positional[0], developer)
            activated_at = _require_text(
                body.get("activated_at"), "activation_request.activated_at"
            )
            command = ActivateContract(
                activated_at=activated_at,
                signature_refs=_typed_references(
                    body.get("signature_refs"),
                    "signature",
                    "activation_request.signature_refs",
                ),
            )
            if not command.signature_refs:
                raise DeveloperApiError(
                    DeveloperApiReasonCode.INVALID_INPUT,
                    "activation_request.signature_refs requires at least "
                    "one signature typed reference",
                )
            record, result = self._submit_canonical(
                contract.contract_id, command, activated_at
            )
            contract = self._require_merge_admitted(
                result, contract_id=contract.contract_id, create=False
            )
            data = self._contract_resource(contract)
            emission = _MutationEmission(
                event_type="connectivity_contract.activated",
                event_id=record.command_id,
                occurred_at=activated_at,
                resource_kind="contract",
                resource_id=contract.contract_id,
                resource_version=self._contract_journal_position(
                    contract.contract_id
                )[0],
                correlation=derive_request_id(
                    self._environment,
                    version.version,
                    request.method,
                    request.route,
                    body,
                ),
                data=dict(data),
            )
            return dict(data), "", "", {}, emission

        if spec.operation == "contract_terminate":
            contract = self._developer_contract(positional[0], developer)
            recorded_at = _require_text(
                body.get("recorded_at"), "termination_request.recorded_at"
            )
            command = TerminateContract(
                recorded_at=recorded_at,
                condition=_require_text(
                    body.get("condition"), "termination_request.condition"
                ),
                reason=_require_text(
                    body.get("reason"), "termination_request.reason"
                ),
            )
            record, result = self._submit_canonical(
                contract.contract_id, command, recorded_at
            )
            contract = self._require_merge_admitted(
                result, contract_id=contract.contract_id, create=False
            )
            data = self._contract_resource(contract)
            emission = _MutationEmission(
                event_type="connectivity_contract.terminated",
                event_id=record.command_id,
                occurred_at=recorded_at,
                resource_kind="contract",
                resource_id=contract.contract_id,
                resource_version=self._contract_journal_position(
                    contract.contract_id
                )[0],
                correlation=derive_request_id(
                    self._environment,
                    version.version,
                    request.method,
                    request.route,
                    body,
                ),
                data=dict(data),
            )
            return dict(data), "", "", {}, emission

        if spec.operation == "lease_grant":
            contract = self._developer_contract(positional[0], developer)
            granted_at = _require_text(
                body.get("granted_at"), "lease_request.granted_at"
            )
            command = GrantLease(
                granted_at=granted_at,
                not_before=_require_text(
                    body.get("not_before"), "lease_request.not_before"
                ),
                not_after=_require_text(
                    body.get("not_after"), "lease_request.not_after"
                ),
            )
            record, result = self._submit_canonical(
                contract.contract_id, command, granted_at
            )
            self._require_merge_admitted(
                result, contract_id=contract.contract_id, create=False
            )
            lease_id = _derive_lease_id(
                contract.contract_id, command
            )
            lease = self._current_lease(lease_id)
            data = self._lease_resource(lease)
            emission = _MutationEmission(
                event_type="connectivity_lease.granted",
                event_id=record.command_id,
                occurred_at=granted_at,
                resource_kind="lease",
                resource_id=lease_id,
                resource_version=self._contract_journal_position(
                    contract.contract_id
                )[0],
                correlation=derive_request_id(
                    self._environment,
                    version.version,
                    request.method,
                    request.route,
                    body,
                ),
                data=dict(data),
            )
            return dict(data), "", "", {}, emission

        if spec.operation == "lease_renew":
            lease = self._developer_lease(positional[0], developer)
            granted_at = _require_text(
                body.get("granted_at"), "lease_renewal.granted_at"
            )
            command = RenewLease(
                lease_id=lease.lease_id,
                granted_at=granted_at,
                not_before=_require_text(
                    body.get("not_before"), "lease_renewal.not_before"
                ),
                not_after=_require_text(
                    body.get("not_after"), "lease_renewal.not_after"
                ),
            )
            record, result = self._submit_canonical(
                lease.contract_id, command, granted_at
            )
            self._require_merge_admitted(
                result, contract_id=lease.contract_id, create=False
            )
            successor_id = _derive_lease_id(lease.contract_id, command)
            successor = self._current_lease(successor_id)
            data = self._lease_resource(successor)
            emission = _MutationEmission(
                event_type="connectivity_lease.renewed",
                event_id=record.command_id,
                occurred_at=granted_at,
                resource_kind="lease",
                resource_id=successor_id,
                resource_version=self._contract_journal_position(
                    lease.contract_id
                )[0],
                correlation=derive_request_id(
                    self._environment,
                    version.version,
                    request.method,
                    request.route,
                    body,
                ),
                data=dict(data),
            )
            return dict(data), "", "", {}, emission

        if spec.operation == "lease_revoke":
            lease = self._developer_lease(positional[0], developer)
            recorded_at = _require_text(
                body.get("recorded_at"), "lease_revocation.recorded_at"
            )
            command = RevokeLease(
                lease_id=lease.lease_id,
                recorded_at=recorded_at,
                reason=_require_text(
                    body.get("reason"), "lease_revocation.reason"
                ),
            )
            record, result = self._submit_canonical(
                lease.contract_id, command, recorded_at
            )
            self._require_merge_admitted(
                result, contract_id=lease.contract_id, create=False
            )
            revoked = self._current_lease(lease.lease_id)
            data = self._lease_resource(revoked)
            emission = _MutationEmission(
                event_type="connectivity_lease.revoked",
                event_id=record.command_id,
                occurred_at=recorded_at,
                resource_kind="lease",
                resource_id=lease.lease_id,
                resource_version=self._contract_journal_position(
                    lease.contract_id
                )[0],
                correlation=derive_request_id(
                    self._environment,
                    version.version,
                    request.method,
                    request.route,
                    body,
                ),
                data=dict(data),
            )
            return dict(data), "", "", {}, emission

        raise DeveloperApiError(
            DeveloperApiReasonCode.ROUTE_UNKNOWN,
            "mutation %r is declared but not dispatched" % spec.operation,
        )

    # -- webhook machinery ---------------------------------------------------

    def _emit_event(
        self,
        *,
        event_type: str,
        event_id: str,
        occurred_at: str,
        resource_kind: str,
        resource_id: str,
        resource_version: int,
        correlation: str,
        data: Mapping[str, Any],
    ) -> int:
        """Emit one observation through the SAME durable
        observation-admission model as the API mutation path (one
        canonical admission architecture; the platform surface
        is not a second webhook-admission path -- it writes the
        SAME admission record family, with an EMPTY idempotency
        key because this emission is not an HTTP mutation
        response).

        FIRST the durable admission record (the audience
        resolved at admission time and FROZEN: a ``not-required``
        admission is terminal -- a later observation of the same
        unchanged event can never acquire an audience); THEN the
        durable delivery obligation when required; THEN the
        per-endpoint queue writes (dedupe by delivery identity:
        the same event never queues twice).  When the admission
        already exists, its frozen decision is AUTHORITATIVE:
        the audience is never re-resolved, and a ``required``
        admission queues only its frozen audience's still-missing
        endpoints.

        The PLATFORM-side observation surface (the operator's
        contract-observation emission): an admission-record,
        obligation-write, or queue-write failure raises to the
        OPERATOR, never to a developer response (there is no
        developer response on this path -- the observed
        contract's state is already canonical and final).
        The API mutation path never calls this method: it drives
        the same shared pieces through the admission gate
        (:meth:`_admit_observation`)."""
        emission = _MutationEmission(
            event_type=event_type,
            event_id=event_id,
            occurred_at=occurred_at,
            resource_kind=resource_kind,
            resource_id=resource_id,
            resource_version=resource_version,
            correlation=correlation,
            data=data,
        )
        admission_id = webhook_platform.derive_admission_id(
            self._environment, emission.event_id, emission.event_type
        )
        admission = self._index.admissions.get(admission_id)
        if admission is not None:
            # the historical admission decision is already
            # durable: never re-resolve the audience for a
            # historical emission
            if admission.status == "not-required":
                return 0
            self._ensure_obligation_from_admission(admission)
            return self._queue_observation(
                event_id=admission.event_id,
                event_type=admission.event_type,
                occurred_at=admission.occurred_at,
                developer_id=admission.developer_id,
                resource_kind=admission.resource_kind,
                resource_id=admission.resource_id,
                resource_version=admission.resource_version,
                correlation=admission.correlation,
                data=admission.data_dict(),
                endpoints=tuple(admission.endpoints),
            )
        # first admission of this emission: resolve the audience
        # once and freeze it
        developer_id, endpoints = self._resolve_observation_audience(
            emission
        )
        self._append_observation_admission(
            key="",
            emission=emission,
            developer_id=developer_id,
            endpoints=endpoints,
        )
        if not endpoints:
            # no audience: the admission is terminal not-required
            return 0
        resolved = emission.resolved(developer_id, endpoints)
        self._append_observation_obligation(resolved)
        return self._queue_observation(
            event_id=resolved.event_id,
            event_type=resolved.event_type,
            occurred_at=resolved.occurred_at,
            developer_id=resolved.developer_id,
            resource_kind=resolved.resource_kind,
            resource_id=resolved.resource_id,
            resource_version=resolved.resource_version,
            correlation=resolved.correlation,
            data=resolved.data,
            endpoints=resolved.endpoints,
        )

    def _queue_observation(
        self,
        *,
        event_id: str,
        event_type: str,
        occurred_at: str,
        developer_id: str,
        resource_kind: str,
        resource_id: str,
        resource_version: int,
        correlation: str,
        data: Mapping[str, Any],
        endpoints: Tuple[str, ...],
    ) -> int:
        """Queue one observation for exactly the given target
        endpoints (the obligation's resolved audience or its
        still-missing subset at recovery): per-endpoint delivery
        sequence, deterministic delivery identity, dedupe
        (never twice).  The single queue-write site for the
        emission path AND the crash-recovery flush.  The owner
        is the obligation-recorded audience owner (never
        re-resolved at recovery)."""
        queued = 0
        for endpoint_id in endpoints:
            delivery_id = webhook_platform.derive_delivery_id(
                endpoint_id, event_id
            )
            if delivery_id in self._index.deliveries:
                continue
            sequence = (
                self._index.delivery_sequences.get(endpoint_id, 0) + 1
            )
            event = webhook_platform.build_observation_event(
                event_id=event_id,
                event_type=event_type,
                occurred_at=occurred_at,
                api_version="2.0",
                environment=self._environment,
                resource_kind=resource_kind,
                resource_id=resource_id,
                resource_version=resource_version,
                sequence=sequence,
                delivery_id=delivery_id,
                correlation=correlation,
                data=data,
            )
            record = WebhookQueueRecord.build(
                sequence=self._journal.tail_sequence() + 1,
                prev_record_id=self._journal.tail_record_id(),
                delivery_id=delivery_id,
                endpoint_id=endpoint_id,
                developer_id=developer_id,
                environment=self._environment,
                delivery_sequence=sequence,
                event=event,
            )
            self._journal.append(record)
            self._index.apply(record)
            queued += 1
        return queued

    def _resource_owner(
        self, resource_kind: str, resource_id: str
    ) -> Optional[str]:
        """The developer owning one observed resource (from the
        boundary's public projections; adapted resources are
        resolved through the canonical public reads)."""
        if resource_kind == "webhook_endpoint":
            endpoint = self._index.endpoints.get(resource_id)
            return endpoint.get("developer_id") if endpoint else None
        if resource_kind == "contract":
            contract = self._developer_contract_or_none(resource_id)
            if contract is None:
                return None
            return self._developer_of_application(
                contract.principal.principal_ref
            )
        if resource_kind == "lease":
            lease = self._developer_lease_or_none(resource_id)
            if lease is None:
                return None
            contract = self._developer_contract_or_none(lease.contract_id)
            if contract is None:
                return None
            return self._developer_of_application(
                contract.principal.principal_ref
            )
        return None

    def _attempt_delivery(self, delivery_id: str, now: str) -> None:
        state = self._index.deliveries[delivery_id]
        endpoint = self._index.endpoints.get(state.endpoint_id)
        if endpoint is None:
            # the endpoint was never registered in this index
            # (cannot happen via the fold; fail closed)
            raise DeveloperApiError(
                DeveloperApiReasonCode.JOURNAL_CORRUPT,
                "delivery %r references unknown endpoint %r"
                % (delivery_id, state.endpoint_id),
            )
        event = dict(state.event)
        attempt_number = state.attempts + 1
        headers = webhook_platform.delivery_headers(
            secret=self.endpoint_signing_secret(state.endpoint_id),
            key_id=webhook_platform.derive_webhook_key_id(
                state.endpoint_id
            ),
            timestamp=now,
            event_id=event["event_id"],
            delivery_id=delivery_id,
            sequence=event["sequence"],
            payload=event,
        )
        transport = self._transports.get(state.endpoint_id)
        if transport is None:
            delivered, response_code = False, 0
        else:
            try:
                delivered, response_code = transport(
                    state.endpoint_id,
                    endpoint.get("url", ""),
                    event,
                    headers,
                )
            except Exception:
                # a raising transport is recorded as a failed
                # attempt (code 0 = no transport response); the
                # canonical mutation outcome is unaffected --
                # delivery state is observational only
                delivered, response_code = False, 0
        status = "delivered" if delivered else "failed"
        next_at = ""
        if status == "failed":
            next_at = webhook_platform.next_attempt_at(
                now, attempt_number
            )
        record = WebhookAttemptRecord.build(
            sequence=self._journal.tail_sequence() + 1,
            prev_record_id=self._journal.tail_record_id(),
            delivery_id=delivery_id,
            endpoint_id=state.endpoint_id,
            event_id=event["event_id"],
            attempt=attempt_number,
            status=status,
            response_code=response_code,
            instant=now,
            next_attempt_at=next_at,
        )
        self._journal.append(record)
        self._index.apply(record)

    # -- resource serializers (the canonical projections) ------------------

    def _contract_journal_position(
        self, contract_id: str
    ) -> Tuple[int, str]:
        """The canonical contract journal's public position for
        one contract: (record count, last recorded instant).
        Pure public read over ``ContractStore.journal()``; the
        count is the emission order metadata (resource_version)
        and the honest ``entered_at`` of the lifecycle
        observation."""
        count = 0
        last_instant = ""
        for record in self._contracts.journal():
            if record.contract_id == contract_id:
                count += 1
                last_instant = record.recorded_at
        return count, last_instant

    def _contract_resource(
        self, contract: Any
    ) -> Dict[str, Any]:
        """The developer-facing contract projection: the
        canonical ``ConnectivityContract`` serialization,
        VERBATIM in meaning, plus the boundary envelope members
        only (id, kind, environment, and the canonical journal
        position).  The boundary never re-shapes, renames, or
        re-semantics the canonical record (no second domain
        model)."""
        resource: Dict[str, Any] = {
            "id": contract.contract_id,
            "kind": "contract",
            "environment": self._environment,
        }
        resource.update(contract.to_dict())
        resource["command_count"] = self._contract_journal_position(
            contract.contract_id
        )[0]
        return resource

    def _lease_resource(self, lease: Any) -> Dict[str, Any]:
        """The developer-facing lease projection: the canonical
        ``ContractLease`` serialization, verbatim in meaning,
        plus the boundary envelope members only."""
        resource: Dict[str, Any] = {
            "id": lease.lease_id,
            "kind": "contract_lease",
            "environment": self._environment,
        }
        resource.update(lease.to_dict())
        return resource

    def _lifecycle_resource(self, contract: Any) -> Dict[str, Any]:
        state = contract.state
        position, last_instant = self._contract_journal_position(
            contract.contract_id
        )
        # The honest classification: the developer API reports
        # the canonical CONTRACT state machine (frozen 1.1 §11);
        # it NEVER claims connectivity or physical evidence.
        # Execution material rides as opaque typed references
        # (LOCK-117: data, never authority).
        return {
            "id": contract.contract_id,
            "kind": "contract_lifecycle",
            "environment": self._environment,
            "contract_state": state,
            "entered_at": last_instant,
            "command_count": position,
            "validity": contract.validity.to_dict(),
            "execution_status": _EXECUTION_STATUS_BY_STATE.get(
                state, "unknown"
            ),
            "execution_scope_refs": [
                ref.to_dict() for ref in contract.execution_scope
            ],
            "execution_artifact_refs": [
                ref.to_dict() for ref in contract.execution_artifacts
            ],
            "assurance_obligation_refs": [
                ref.to_dict() for ref in contract.assurance_obligations
            ],
            "physical_connectivity_observed": False,
            "physical_evidence": "not-claimed",
            "statements": list(_LIFECYCLE_STATEMENTS),
            "note": (
                "API success never implies physical connectivity "
                "success: this observation reports the canonical "
                "contract state machine only (the frozen 1.1 "
                "reference lifecycle); execution material appears "
                "as opaque typed references and physical "
                "connectivity evidence is never fabricated or "
                "promoted by the developer API."
            ),
            "evidence_class": evidence_class(self._environment),
        }

    def _usage_terms_resource(self, contract: Any) -> Dict[str, Any]:
        """The developer-facing usage-semantics read: the
        contract's usage/pricing terms as the OPAQUE TYPED
        REFERENCE the canonical record carries -- never
        interpreted, never re-modelled.  The usage authority
        (the M009 commercial track) owns the referenced
        semantics; this API exposes the typed reference only
        (LOCK-113/LOCK-114)."""
        return {
            "id": contract.contract_id,
            "kind": "contract_usage_terms",
            "environment": self._environment,
            "contract_state": contract.state,
            "usage_pricing_terms": (
                contract.usage_pricing_terms.to_dict()
                if contract.usage_pricing_terms is not None
                else None
            ),
            "note": (
                "usage semantics are referenced, never interpreted: "
                "the usage/pricing authority (the commercial "
                "reconciliation track) owns the referenced material; "
                "this API exposes the contract's opaque typed "
                "reference only"
            ),
            "evidence_class": evidence_class(self._environment),
        }

    def _assurance_resource(self, contract: Any) -> Dict[str, Any]:
        """The developer-facing assurance-semantics read: the
        contract's assurance obligations as OPAQUE TYPED
        REFERENCES, plus the assurance-relevant contract state
        (the frozen 1.1 §9 vocabulary integration: ASSURED /
        DEGRADED / FAILED record the latest assurance evaluation
        outcome).  The assurance authority (M005) owns the
        obligations and their evaluation; this API reports the
        contract-recorded outcomes only (LOCK-106/LOCK-114)."""
        return {
            "id": contract.contract_id,
            "kind": "contract_assurance",
            "environment": self._environment,
            "contract_state": contract.state,
            "assurance_obligations": [
                ref.to_dict() for ref in contract.assurance_obligations
            ],
            "note": (
                "assurance semantics are referenced, never evaluated: "
                "the assurance authority owns the obligations; the "
                "contract state machine records the evaluation "
                "outcomes (ASSURED/DEGRADED/FAILED per the frozen "
                "1.1 §9 vocabulary)"
            ),
            "evidence_class": evidence_class(self._environment),
        }

    def _delivery_resource(self, state: Any) -> Dict[str, Any]:
        event = dict(state.event)
        return {
            "id": state.delivery_id,
            "kind": "webhook_delivery",
            "environment": self._environment,
            "endpoint_id": state.endpoint_id,
            "delivery_sequence": state.delivery_sequence,
            "event_id": event.get("event_id", ""),
            "event_type": event.get("event_type", ""),
            "resource_id": event.get("resource_id", ""),
            "resource_version": event.get("resource_version", 0),
            "occurred_at": event.get("occurred_at", ""),
            "attempts": state.attempts,
            "last_status": state.last_status,
            "last_attempt_at": state.last_attempt_at,
            "next_attempt_at": state.next_attempt_at,
            "response_codes": list(state.response_codes),
        }

    def _endpoint_health(self, endpoint_id: str) -> Dict[str, Any]:
        states = [
            state
            for state in self._index.deliveries.values()
            if state.endpoint_id == endpoint_id
        ]
        states.sort(key=lambda state: state.delivery_id)
        delivered = sum(
            1 for state in states if state.last_status == "delivered"
        )
        pending = sum(
            1
            for state in states
            if state.last_status in ("pending", "failed")
        )
        last_status = states[-1].last_status if states else "idle"
        return {
            "deliveries": len(states),
            "delivered": delivered,
            "undelivered": pending,
            "last_status": last_status,
            "observational_only": True,
            "note": (
                "webhook delivery state is an observation channel: "
                "delivery success or failure never changes canonical "
                "contract or lease state"
            ),
        }

    # -- pagination helper -------------------------------------------------

    def _page(
        self,
        items: List[Dict[str, Any]],
        kind: str,
        developer: str,
        filters: Mapping[str, str],
        body: Mapping[str, Any],
    ) -> Tuple[List[Dict[str, Any]], str, bool]:
        return paginate(
            items,
            environment=self._environment,
            kind=kind,
            developer_id=developer,
            filters=dict(filters),
            cursor=body.get("cursor"),
            limit=body.get("limit"),
        )

    # -- tenant scoping ----------------------------------------------------

    def _developer_application_ids(
        self, developer_id: str
    ) -> set:
        """The applications issued to one developer in this
        environment (the ownership scope: a contract's canonical
        principal IS the application; the developer owns the
        contracts of ALL their applications)."""
        return {
            application_id
            for application_id, entry in self._index.credentials.items()
            if entry.get("developer_id") == developer_id
        }

    def _developer_contracts(self, developer_id: str) -> List[Any]:
        owned = self._developer_application_ids(developer_id)
        return [
            contract
            for contract in self._contracts.contracts()
            if contract.principal.principal_ref in owned
        ]

    def _developer_contract_or_none(
        self, contract_id: str
    ) -> Optional[Any]:
        try:
            return self._contracts.contract(contract_id)
        except ContractError:
            return None

    def _developer_contract(
        self, contract_id: str, developer_id: str
    ) -> Any:
        try:
            contract = self._contracts.contract(contract_id)
        except ContractError as error:
            raise self._adapted_error(
                error,
                resource_id=contract_id,
            ) from error
        if (
            contract.principal.principal_ref
            not in self._developer_application_ids(developer_id)
        ):
            raise self._resource_unknown(
                "contract", contract_id, ""
            )
        return contract

    def _developer_leases(self, developer_id: str) -> List[Any]:
        out: List[Any] = []
        for contract in self._developer_contracts(developer_id):
            for lease_id in self._contracts.leases_for_contract(
                contract.contract_id
            ):
                out.append(self._contracts.lease(lease_id))
        return sorted(out, key=lambda lease: lease.lease_id)

    def _developer_lease_or_none(
        self, lease_id: str
    ) -> Optional[Any]:
        try:
            return self._contracts.lease(lease_id)
        except ContractError:
            return None

    def _developer_lease(self, lease_id: str, developer_id: str) -> Any:
        try:
            lease = self._contracts.lease(lease_id)
        except ContractError as error:
            raise self._adapted_error(
                error,
                resource_id=lease_id,
            ) from error
        # the lease rides its contract's ownership scope
        self._developer_contract(lease.contract_id, developer_id)
        return lease

    def _developer_of_application(
        self, application_id: str
    ) -> Optional[str]:
        entry = self._index.credentials.get(application_id)
        return entry.get("developer_id") if entry else None

    def _developer_endpoints(self, developer: str) -> List[Dict[str, Any]]:
        return [
            dict(endpoint)
            for endpoint_id, endpoint in sorted(
                self._index.endpoints.items()
            )
            if endpoint.get("developer_id") == developer
        ]

    def _current_lease(self, lease_id: str) -> Any:
        """The canonical lease record for a derived lease id
        (the pure public read; the canonical authority raised on
        any semantic rejection before the merge, so a missing
        lease here is boundary inconsistency -- fail closed)."""
        try:
            return self._contracts.lease(lease_id)
        except ContractError as error:
            raise self._adapted_error(error) from error

    # -- envelope / error mapping -------------------------------------------

    def _envelope(
        self,
        request: ApiRequest,
        request_id: str,
        version: ApiVersionSpec,
        data: Any,
        *,
        rate: Optional[RateDecision] = None,
        idempotency: Optional[Mapping[str, Any]] = None,
        deprecations: Tuple[str, ...] = (),
    ) -> ApiResponse:
        body: Dict[str, Any] = {
            "api_version": version.version,
            "environment": self._environment,
            "request_id": request_id,
            "data": data,
        }
        headers: Dict[str, str] = {
            "X-ADCOS-Request-Id": request_id,
            "X-ADCOS-API-Version": version.version,
            "X-ADCOS-Environment": self._environment,
        }
        if idempotency is not None:
            body["idempotency"] = dict(idempotency)
        if rate is not None:
            body["rate_limit"] = rate.to_dict()
            headers["X-RateLimit-Limit"] = str(rate.limit)
            headers["X-RateLimit-Remaining"] = str(rate.remaining)
            headers["X-RateLimit-Reset"] = rate.reset_at
        if version.status == "deprecated":
            body["deprecation"] = {
                "version": version.version,
                "message": version.notice,
            }
            headers["X-ADCOS-Deprecation"] = version.notice
        if deprecations:
            body["deprecated_fields"] = list(deprecations)
        return self._response(200, body, headers)

    def _response(
        self, status: int, body: Mapping[str, Any], headers: Mapping[str, str]
    ) -> ApiResponse:
        return ApiResponse(status=status, body=body, headers=headers)

    def _error_response(
        self, request: ApiRequest, request_id: str, error: DeveloperApiError
    ) -> ApiResponse:
        error_body = error.to_dict()
        error_body["request_id"] = error_body.get("request_id") or request_id
        if not error_body.get("environment"):
            error_body["environment"] = self._environment
        body: Dict[str, Any] = {
            "api_version": request.api_version or "",
            "environment": self._environment,
            "request_id": request_id,
            "error": error_body,
        }
        headers: Dict[str, str] = {
            "X-ADCOS-Request-Id": request_id,
            "X-ADCOS-Environment": self._environment,
        }
        if error.retry_after:
            headers["Retry-After"] = error.retry_after
        return self._response(error.http_status, body, headers)

    def _adapted_error(
        self,
        error: Exception,
        *,
        request_id: str = "",
        resource_id: str = "",
    ) -> DeveloperApiError:
        """Map one canonical authority failure to the boundary,
        preserving the EXACT canonical reason code (criterion 4).

        The boundary reason classifies the failure family; the
        HTTP status derives from the canonical reason (the
        frozen mapping); the developer-facing error body always
        carries the canonical reason string unchanged."""
        canonical_reason = getattr(error, "code", "") or getattr(
            error, "reason", ""
        )
        detail = getattr(error, "detail", "") or str(error)
        if canonical_reason == "sequence-conflict":
            # the canonical create-once / command-content conflict
            # family surfaces as the boundary idempotency
            # conflict, with the canonical reason attached
            # unchanged
            boundary_reason = DeveloperApiReasonCode.IDEMPOTENCY_CONFLICT
        elif canonical_reason in ("unknown-contract",):
            # the canonical not-found family
            boundary_reason = DeveloperApiReasonCode.RESOURCE_UNKNOWN
        else:
            boundary_reason = DeveloperApiReasonCode.INVALID_INPUT
        return DeveloperApiError(
            boundary_reason,
            detail,
            canonical_reason=canonical_reason,
            request_id=request_id,
            resource_id=resource_id,
            environment=self._environment,
        )

    def _resource_unknown(
        self, kind: str, resource_id: str, request_id: str
    ) -> DeveloperApiError:
        return DeveloperApiError(
            DeveloperApiReasonCode.RESOURCE_UNKNOWN,
            "%s %r is not visible in environment %r for this application"
            % (kind, resource_id, self._environment),
            request_id=request_id,
            resource_id=resource_id,
            environment=self._environment,
        )


#: The emission event-type table of the canonical mutations (the
#: single operation -> event-type mapping shared by the execution
#: path and the admission-completion reconstruction).
_EMISSION_EVENT_TYPES = {
    "intent_create": "connectivity_intent.created",
    "offers_accept": "connectivity_contract.offers_selected",
    "contract_activate": "connectivity_contract.activated",
    "contract_terminate": "connectivity_contract.terminated",
    "lease_grant": "connectivity_lease.granted",
    "lease_renew": "connectivity_lease.renewed",
    "lease_revoke": "connectivity_lease.revoked",
}


def _derive_lease_id(contract_id: str, command: Any) -> str:
    """The content-derived lease identity of a grant/renewal
    command (pure: the canonical derivation over (contract,
    granted_at, not_before, not_after) -- the state is not part
    of the identity)."""
    return build_lease(
        contract_id=contract_id,
        state="granted",
        granted_at=command.granted_at,
        not_before=command.not_before,
        not_after=command.not_after,
    ).lease_id


def _json_loads(text: str) -> Any:
    import json

    return json.loads(text)


class _FreshStoreView(ApiStore):
    """A zero-record view over a real store (load-construction
    aid): the fresh constructor sees an empty store, then the
    real store is replayed through the real journal."""

    def __init__(self, store: ApiStore) -> None:
        self._store = store

    def append_line(self, line: str) -> None:  # pragma: no cover
        raise DeveloperApiError(
            DeveloperApiReasonCode.STORE_FAILED,
            "the fresh-construction view never persists",
        )

    def read_lines(self) -> List[str]:
        return []
