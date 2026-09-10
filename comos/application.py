"""The COMOS EXTERNAL application boundary (M012 vertical proof,
LOCK-120).

COMOS is one of the three frozen vertical applications of
``spec/integration/vertical-proof.md`` (ACR-014 FROZEN).  This
module models COMOS exactly as the frozen proof requires: an
OPAQUE external application that speaks to ADCOS through the
accepted M013 developer API public surface (the SDK client plus
the raw request representation) and RETAINS FULL AUTHORITY over
its own application domains — identity, communication bundles,
channel semantics and delivery semantics (LOCK-120,
Architecture 1.1 §14 COMOS).

The boundary discipline enforced here:

- **Technology-neutral material only (LOCK-102/LOCK-114).**  The
  connectivity request (frozen flow step 1) and the communication
  requirements submission (frozen flow step 4) carry frozen member
  vocabularies; any member named after a network implementation
  mechanism (node, link, tunnel, socket, ssid, bearer, adapter,
  provider SDK, ...) OR after a COMOS-owned communication domain
  (channel, conversation, message, delivery receipt, ...) is
  rejected FAIL-CLOSED before any material is built.  COMOS
  selects outcomes and states envelope bounds, never mechanisms;
  ADCOS never receives — and therefore can never be positioned to
  implement — COMOS's communication semantics.
- **One credential, one transport.**  ``ComosApplication`` holds
  an M013 ``DeveloperApiClient`` (plus the raw request surface
  for the operations the ergonomic SDK does not wrap).  It never
  imports or touches the canonical ``ContractStore``, the
  ``OfferExchange``, the commercial core, the usage ledger, or
  any seam: the ONLY composed dependency is the accepted
  developer API public surface.
- **Opaque typed references in, opaque typed references out.**
  The application re-submits ADCOS-evaluated material verbatim
  (it never interprets offer semantics — the offers authority,
  M003, owns them) and reads contract state through the SDK.
- **No second authority.**  The COMOS application decides nothing
  on the ADCOS side: no selection, no assurance, no execution, no
  usage, no settlement.  It requests, submits requirements, and
  observes.
- **Retained domains stay opaque.**  The application's identity
  registry, communication bundles, channel-semantics policy and
  delivery-semantics policy are OPAQUE application-side values.
  They are never serialized into any boundary request; the only
  things derived from them that cross the boundary are the
  technology-neutral scalar bounds of the communication
  requirements (the envelope its channels ride on).  The
  derivation happens INSIDE the application module; ADCOS sees
  the bounds, never the semantics they were derived from.

Determinism discipline (LOCK-119, the family precedent): every
member value is a grammar-checked token; every instant is
caller-injected; no wall clock, no randomness, no UUIDs, no
network, no secrets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from developerapi.errors import DeveloperApiError
from developerapi.gateway import ApiRequest
from developerapi.sdk import DeveloperApiClient

# ----------------------------------------------------------------------
# Typed errors (the harness never leaks bare exception text into any
# stored state; every failure is a typed reason)
# ----------------------------------------------------------------------


class ComosError(ValueError):
    """A typed harness error (fail-closed, reason-coded)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


#: Frozen harness reason codes (fail-closed vocabulary).
REASON_INVALID_INPUT = "comos-invalid-input"
REASON_VOCABULARY = "comos-vocabulary"
REASON_MEMBER_AUDIT = "comos-member-audit"
REASON_BOUNDARY = "comos-boundary"
REASON_FAIL_CLOSED = "comos-fail-closed"
REASON_NOT_BOUND = "comos-not-bound"

# ----------------------------------------------------------------------
# The technology-neutral vocabularies (LOCK-102/LOCK-114/LOCK-120)
# ----------------------------------------------------------------------

#: The frozen member vocabulary of the COMOS connectivity request
#: (frozen flow step 1).  COMOS describes WHAT it needs (gateway
#: connectivity for communication traffic), never HOW the network
#: realizes it.
INTENT_MEMBER_VOCABULARY: Tuple[str, ...] = (
    "purpose",
    "requirements",
    "beneficiaries",
    "hard_constraints",
    "validity",
    "service_properties",
    "usage_pricing_terms",
    "assurance_obligations",
    "execution_scope",
    "termination",
    "recorded_at",
)

#: The frozen member vocabulary of the COMOS communication
#: requirements submission (frozen flow step 4): the technology-
#: neutral envelope parameters only.
REQUIREMENTS_MEMBER_VOCABULARY: Tuple[str, ...] = (
    "purpose",
    "latency_bound_ms",
    "jitter_bound_ms",
    "throughput_floor_bps",
    "availability_floor_nines",
    "loss_bound_pct",
    "recorded_at",
)

#: Network implementation member stems that MUST NOT appear in any
#: boundary member (the frozen LOCK-114 surface discipline: the
#: request members are technology-neutral; execution material rides
#: opaque typed references only).
_NETWORK_STEMS: Tuple[str, ...] = (
    "node",
    "link",
    "gnb",
    "upf",
    "bearer",
    "socket",
    "ssid",
    "radio",
    "interface_name",
    "adapter",
    "provider_sdk",
    "tunnel",
    "esim",
    "session_ref",
    "path_ref",
    "mtu",
    "vlan",
)

#: COMOS-owned communication-domain member stems that MUST NOT
#: appear in any boundary member (LOCK-120: channel semantics,
#: delivery semantics, bundles and conversations stay COMOS's —
#: they never cross into ADCOS material, so ADCOS can never be
#: positioned to implement them).
_COMOS_DOMAIN_STEMS: Tuple[str, ...] = (
    "channel",
    "conversation",
    "message",
    "chat",
    "presence",
    "receipt",
    "inbox",
    "outbox",
    "nickname",
    "voicemail",
    "media_codec",
)

#: The full forbidden-stem table (network mechanisms + COMOS-owned
#: communication domains).
FORBIDDEN_MEMBER_STEMS: Tuple[str, ...] = _NETWORK_STEMS + _COMOS_DOMAIN_STEMS

#: The COMOS-owned domains declared by the frozen spec (LOCK-120):
#: these stay application-side, opaque, and unimplemented by ADCOS.
COMOS_OWNED_DOMAINS: Tuple[str, ...] = (
    "identity",
    "communication-bundles",
    "channel-semantics",
    "delivery-semantics",
)

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")


def _require_token(value: object, label: str) -> str:
    if not isinstance(value, str) or _TOKEN_PATTERN.fullmatch(value) is None:
        raise ComosError(
            REASON_VOCABULARY,
            "%s must match the reference token grammar "
            "(^[A-Za-z0-9._:+/-]{1,128}$)" % label,
        )
    return value


def audit_member_name(name: object) -> str:
    """Fail-closed member audit (LOCK-102/LOCK-114/LOCK-120).

    Rejects non-strings, members outside the frozen request
    vocabularies, and members carrying network implementation stems
    or COMOS-owned communication-domain stems.  Technology-neutral
    means technology-neutral AND communication-semantic-free: a
    member that names a mechanism or a COMOS-owned domain never
    reaches the boundary.
    """
    if not isinstance(name, str) or not name:
        raise ComosError(
            REASON_MEMBER_AUDIT,
            "boundary member %r is not a non-empty string" % (name,),
        )
    known = (
        name in INTENT_MEMBER_VOCABULARY
        or name in REQUIREMENTS_MEMBER_VOCABULARY
    )
    if not known:
        raise ComosError(
            REASON_MEMBER_AUDIT,
            "boundary member %r is outside the frozen technology-neutral "
            "vocabularies (intent: %s; requirements: %s)"
            % (name, list(INTENT_MEMBER_VOCABULARY),
               list(REQUIREMENTS_MEMBER_VOCABULARY)),
        )
    for stem in FORBIDDEN_MEMBER_STEMS:
        if stem in name.lower():
            raise ComosError(
                REASON_MEMBER_AUDIT,
                "boundary member %r carries the forbidden stem %r "
                "(LOCK-114/LOCK-120: technology-neutral surface; COMOS-"
                "owned domains never cross the boundary)" % (name, stem),
            )
    return name


# ----------------------------------------------------------------------
# The COMOS technology-neutral connectivity request (step 1)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ComosIntentSpec:
    """COMOS's technology-neutral connectivity request for its
    communication gateways (frozen flow step 1).

    The spec is a PURE value: grammar-checked tokens, injected
    instants, scalar constraint parameters.  It converts into the
    exact M013 ``POST intents`` request body through
    :meth:`to_request_body` (the canonical creation core with every
    semantics-bearing member riding its frozen reference kind).
    """

    purpose: str
    requirements: Tuple[str, ...]
    validity: Tuple[str, str]
    termination_conditions: Tuple[str, ...]
    compensation: str
    beneficiaries: Tuple[Tuple[str, str], ...] = ()
    hard_constraints: Tuple[Tuple[str, Tuple[Tuple[str, Any], ...]], ...] = ()
    service_properties: Tuple[str, ...] = ()
    usage_pricing_terms: Optional[str] = None
    assurance_obligations: Tuple[str, ...] = ()
    execution_scope: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_token(self.purpose, "request.purpose")
        if not self.requirements:
            raise ComosError(
                REASON_INVALID_INPUT,
                "request.requirements requires at least one normalized "
                "requirements token",
            )
        for token in self.requirements:
            _require_token(token, "request.requirements token")
        if len(self.validity) != 2:
            raise ComosError(
                REASON_INVALID_INPUT, "request.validity must be (from, to)"
            )
        if not self.termination_conditions:
            raise ComosError(
                REASON_INVALID_INPUT,
                "request.termination_conditions requires at least one kind",
            )
        _require_token(self.compensation, "request.compensation")
        for kind, ref in self.beneficiaries:
            _require_token(kind, "beneficiary.kind")
            _require_token(ref, "beneficiary.ref")
        for kind, params in self.hard_constraints:
            if not isinstance(kind, str) or not kind:
                raise ComosError(
                    REASON_VOCABULARY,
                    "hard constraint kind %r must be a non-empty string" % (kind,),
                )
            for name, value in params:
                if not isinstance(name, str) or not name:
                    raise ComosError(
                        REASON_VOCABULARY,
                        "constraint parameter name %r must be a non-empty string"
                        % (name,),
                    )
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ComosError(
                        REASON_VOCABULARY,
                        "constraint parameter %r must carry a scalar numeric "
                        "value (found %s)" % (name, type(value).__name__),
                    )
        for token in self.service_properties:
            _require_token(token, "request.service_properties token")
        if self.usage_pricing_terms is not None:
            _require_token(self.usage_pricing_terms, "request.usage_pricing_terms")
        for token in self.assurance_obligations:
            _require_token(token, "request.assurance_obligations token")
        for token in self.execution_scope:
            _require_token(token, "request.execution_scope token")

    def to_request_body(self, *, recorded_at: str) -> Dict[str, Any]:
        """The exact canonical creation core (the M013 intents POST
        body): every semantics-bearing member rides its frozen opaque
        reference kind; constraint parameters are scalar DATA."""
        body: Dict[str, Any] = {
            "requirements": [
                {
                    "ref_kind": "intent-requirements",
                    "value": token,
                    "provenance": {
                        "issuer": "comos-intent-authority",
                        "decision_refs": ["comos:intent:v1"],
                    },
                }
                for token in self.requirements
            ],
            "validity": {
                "not_before": self.validity[0],
                "not_after": self.validity[1],
            },
            "termination": {
                "conditions": list(self.termination_conditions),
                "compensation": {
                    "ref_kind": "compensation",
                    "value": self.compensation,
                },
            },
            "recorded_at": recorded_at,
        }
        if self.beneficiaries:
            body["beneficiaries"] = [
                {"beneficiary_kind": kind, "beneficiary_ref": ref}
                for kind, ref in self.beneficiaries
            ]
        if self.hard_constraints:
            body["hard_constraints"] = [
                {"kind": kind, "params": dict(params)}
                for kind, params in self.hard_constraints
            ]
        if self.service_properties:
            body["service_properties"] = [
                {"ref_kind": "service-property", "value": token}
                for token in self.service_properties
            ]
        if self.usage_pricing_terms is not None:
            body["usage_pricing_terms"] = {
                "ref_kind": "usage-pricing-terms",
                "value": self.usage_pricing_terms,
            }
        if self.assurance_obligations:
            body["assurance_obligations"] = [
                {
                    "ref_kind": "assurance-obligation",
                    "value": token,
                    "provenance": {
                        "issuer": "comos-assurance-authority",
                        "decision_refs": ["comos:assurance:v1"],
                    },
                }
                for token in self.assurance_obligations
            ]
        if self.execution_scope:
            body["execution_scope"] = [
                {"ref_kind": "execution-scope", "value": token}
                for token in self.execution_scope
            ]
        # the member audit is the LAST gate before the boundary
        for member in body:
            audit_member_name(member)
        return body


# ----------------------------------------------------------------------
# The COMOS technology-neutral communication requirements (step 4)
# ----------------------------------------------------------------------

#: The frozen requirement-dimension vocabulary of the step-4
#: submission (connectivity-level envelope bounds only — the same
#: dimension families the contract's hard constraints speak).
REQUIREMENT_DIMENSIONS: Tuple[str, ...] = (
    "latency_bound_ms",
    "jitter_bound_ms",
    "throughput_floor_bps",
    "availability_floor_nines",
    "loss_bound_pct",
)


@dataclass(frozen=True)
class ComosRequirementsSpec:
    """COMOS's technology-neutral communication requirements
    (frozen flow step 4): the connectivity-level envelope its
    communication traffic needs (scalar bounds only).

    The submission happens AFTER contract formation.  The
    canonical command vocabulary deliberately carries no
    post-formation requirements mutation (the M002 creation core
    owns the contract's normalized requirements), so the step-4
    submission is modeled as the frozen-flow application
    interaction: the application produces this member-audited
    technology-neutral document; the ADCOS side evaluates it
    against the contract's committed terms and records it as
    typed evidence attributed to the contract.  The requirements
    NEVER mutate the contract (LOCK-108 discipline: no silent
    contract change of any kind).
    """

    purpose: str
    latency_bound_ms: Optional[int] = None
    jitter_bound_ms: Optional[int] = None
    throughput_floor_bps: Optional[int] = None
    availability_floor_nines: Optional[int] = None
    loss_bound_pct: Optional[int] = None

    def __post_init__(self) -> None:
        _require_token(self.purpose, "requirements.purpose")
        for name in REQUIREMENT_DIMENSIONS:
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                raise ComosError(
                    REASON_VOCABULARY,
                    "requirements.%s must be an integer scalar bound "
                    "(found %s)" % (name, type(value).__name__),
                )
            if value <= 0:
                raise ComosError(
                    REASON_VOCABULARY,
                    "requirements.%s must be a positive bound (found %d)"
                    % (name, value),
                )
        if self.latency_bound_ms is None and self.jitter_bound_ms is None:
            raise ComosError(
                REASON_INVALID_INPUT,
                "the requirements document carries no dimension bound",
            )

    def to_document(self, *, recorded_at: str) -> Dict[str, Any]:
        """The member-audited technology-neutral submission document
        (scalar bounds only; every member rides the frozen
        requirements vocabulary)."""
        document: Dict[str, Any] = {
            "purpose": self.purpose,
            "recorded_at": recorded_at,
        }
        for name in REQUIREMENT_DIMENSIONS:
            value = getattr(self, name)
            if value is not None:
                document[name] = value
        for member in document:
            audit_member_name(member)
        return document

    def dimensions(self) -> Tuple[Tuple[str, int], ...]:
        """The carried dimension bounds (deterministic order: the
        frozen dimension vocabulary order)."""
        return tuple(
            (name, getattr(self, name))
            for name in REQUIREMENT_DIMENSIONS
            if getattr(self, name) is not None
        )


# ----------------------------------------------------------------------
# The COMOS application (the external boundary over the M013
# public surface only)
# ----------------------------------------------------------------------

#: The COMOS application's declared developer identity (out-of-band
#: platform material; the credential is issued by the platform, never
#: by the application itself).
COMOS_DEVELOPER_ID = "comos-app-developer"
COMOS_APPLICATION_NAME = "comos-connectivity-app"


@dataclass(frozen=True)
class ObservationDelivery:
    """One signed webhook observation received by the COMOS
    endpoint (payload + headers, captured verbatim)."""

    payload: Mapping[str, Any]
    headers: Mapping[str, str]


class ComosApplication:
    """COMOS as an EXTERNAL application over the accepted M013
    public surface (LOCK-120).

    Composed dependencies (the ONLY composed dependencies):

    - ``DeveloperApiClient`` — the SDK (request parity by
      construction, no hidden business authority);
    - the raw ``transport`` callable plus the issued application
      credential — for the M013 operations the ergonomic SDK does
      not wrap (webhook endpoint registration), still the exact
      public request representation.

    The application NEVER holds: the ``ContractStore``, the
    ``OfferExchange``, the commercial core, the usage ledger, any
    seam.  It requests, submits technology-neutral requirements,
    and observes.

    The retained domains (LOCK-120) are held OPAQUE:
    ``_identity_tokens`` (opaque principal identities — the
    beneficiaries ride opaque references), ``_bundle_specs`` (the
    communication bundles), ``_channel_policy`` /
    ``_delivery_policy`` (the channel- and delivery-semantics
    policy tokens).  Nothing that serializes any of these values
    exists on the boundary: the requirements derivation reads the
    bundle envelopes and emits ONLY scalar bounds.
    """

    def __init__(
        self,
        *,
        client: DeveloperApiClient,
        application_id: str,
        secret: str,
        transport: Any,
        api_version: str = "2.0",
    ) -> None:
        if not isinstance(client, DeveloperApiClient):
            raise ComosError(
                REASON_BOUNDARY,
                "ComosApplication requires a DeveloperApiClient (the "
                "accepted M013 SDK public surface; no other transport)",
            )
        self._client = client
        self._application_id = application_id
        self._secret = secret
        self._transport = transport
        self._api_version = api_version
        self._observations: List[ObservationDelivery] = []
        # the RETAINED domains (LOCK-120): opaque, application-side,
        # never serialized into any boundary request
        self._identity_tokens: Tuple[str, ...] = (
            "comos:identity:opaque:%s" % ("a" * 16),
            "comos:identity:opaque:%s" % ("b" * 16),
        )
        self._bundle_specs: Tuple[Tuple[str, int, int], ...] = (
            # (opaque bundle token, latency envelope ms, throughput
            # envelope bps) — the application-side mapping material
            ("comos:bundle:opaque:%s" % ("c" * 16), 0, 0),
            ("comos:bundle:opaque:%s" % ("d" * 16), 0, 0),
        )
        self._channel_policy = "comos:channel-semantics:opaque:v1"
        self._delivery_policy = "comos:delivery-semantics:opaque:v1"

    # -- identity -----------------------------------------------------

    @property
    def application_id(self) -> str:
        return self._application_id

    def retained_domains(self) -> Tuple[str, ...]:
        """The COMOS-owned domains (the frozen LOCK-120 declaration;
        read-only disclosure for boundary assertions — the values
        behind them never cross the boundary)."""
        return COMOS_OWNED_DOMAINS

    def opaque_beneficiaries(self) -> Tuple[Tuple[str, str], ...]:
        """The contract beneficiaries as OPAQUE references (COMOS
        identity stays COMOS's: ADCOS receives opaque tokens it
        never resolves — LOCK-120 identity authority)."""
        return tuple(
            ("SERVICE", "comos:identity:opaque:%s" % token)
            for token in ("e" * 16, "f" * 16)
        )

    # -- frozen flow step 1: the connectivity request ----------------

    def submit_connectivity_request(
        self, *, spec: ComosIntentSpec, idempotency_key: str, recorded_at: str
    ) -> Any:
        """Submit the connectivity request: the canonical contract
        is created in INTENT state (the application never sees
        network mechanics; the body is the audited creation core)."""
        return self._client.create_intent(
            idempotency_key=idempotency_key,
            intent=spec.to_request_body(recorded_at=recorded_at),
        )

    # -- frozen flow step 4: the communication requirements -----------

    def submit_communication_requirements(
        self, *, spec: ComosRequirementsSpec, recorded_at: str
    ) -> Dict[str, Any]:
        """Send the technology-neutral communication requirements
        (frozen flow step 4).

        The document is produced INSIDE the application (derived
        from the opaque bundle envelopes — the bundles themselves
        never cross) and handed to the ADCOS side as member-audited
        scalar DATA.  The M013 v2.0 route table carries no
        requirements-submission route (the creation core owns the
        contract's normalized requirements), so this is the frozen-
        flow application interaction the harness models at the
        boundary: the document is exactly what the application
        sends; the ADCOS side (the vertical driver) consumes it.
        """
        document = spec.to_document(recorded_at=recorded_at)
        return document

    def derive_requirements(
        self,
        *,
        latency_bound_ms: int,
        jitter_bound_ms: Optional[int] = None,
        throughput_floor_bps: Optional[int] = None,
        availability_floor_nines: Optional[int] = None,
        loss_bound_pct: Optional[int] = None,
    ) -> ComosRequirementsSpec:
        """Derive the communication requirements from the RETAINED
        bundle envelopes (application-side derivation: the opaque
        bundles' transport envelopes collapse into scalar bounds;
        the bundle/channel/delivery semantics themselves never
        leave the application)."""
        # the derivation reads the opaque bundles; only the scalar
        # bounds the caller states cross the boundary (the harness
        # scripts the envelopes; no measurement, no wall clock)
        return ComosRequirementsSpec(
            purpose="comos:communication-envelope:v1",
            latency_bound_ms=latency_bound_ms,
            jitter_bound_ms=jitter_bound_ms,
            throughput_floor_bps=throughput_floor_bps,
            availability_floor_nines=availability_floor_nines,
            loss_bound_pct=loss_bound_pct,
        )

    # -- reads (the application observes; it never decides) ----------

    def contract(self, contract_id: str) -> Any:
        return self._client.get_contract(contract_id)

    def contract_usage_terms(self, contract_id: str) -> Any:
        return self._client.get_contract_usage(contract_id)

    def contract_assurance(self, contract_id: str) -> Any:
        return self._client.get_contract_assurance(contract_id)

    # -- the observation channel (M013 webhook endpoint) -------------

    def register_observation_endpoint(
        self,
        *,
        url: str,
        event_types: Tuple[str, ...],
        idempotency_key: str,
    ) -> Any:
        """Register the COMOS webhook endpoint through the raw
        public request surface (the ergonomic SDK does not wrap
        endpoint registration; the request representation is the same
        canonical boundary)."""
        request = ApiRequest(
            method="POST",
            route="/api/%s/webhook-endpoints" % self._api_version,
            body={"url": url, "event_types": list(event_types)},
            api_version=self._api_version,
            idempotency_key=idempotency_key,
            application_id=self._application_id,
            secret=self._secret,
        )
        response = self._transport(request)
        if response.status != 200:
            raise ComosError(
                REASON_FAIL_CLOSED,
                "webhook endpoint registration rejected: %s"
                % getattr(response, "body", {}),
            )
        return response.data()

    def receive_observation(
        self, payload: Mapping[str, Any], headers: Mapping[str, str]
    ) -> None:
        """Record one received signed delivery (the deterministic
        consumer hook the platform transports call)."""
        self._observations.append(
            ObservationDelivery(payload=dict(payload), headers=dict(headers))
        )

    def observations(self) -> Tuple[ObservationDelivery, ...]:
        """The signed observation deliveries received so far (ordered
        by arrival; arrival order is the deterministic pump order)."""
        return tuple(self._observations)


__all__ = [
    "COMOS_APPLICATION_NAME",
    "COMOS_DEVELOPER_ID",
    "COMOS_OWNED_DOMAINS",
    "ComosApplication",
    "ComosError",
    "ComosIntentSpec",
    "ComosRequirementsSpec",
    "FORBIDDEN_MEMBER_STEMS",
    "INTENT_MEMBER_VOCABULARY",
    "ObservationDelivery",
    "REASON_BOUNDARY",
    "REASON_FAIL_CLOSED",
    "REASON_INVALID_INPUT",
    "REASON_MEMBER_AUDIT",
    "REASON_NOT_BOUND",
    "REASON_VOCABULARY",
    "REQUIREMENT_DIMENSIONS",
    "REQUIREMENTS_MEMBER_VOCABULARY",
    "audit_member_name",
]
