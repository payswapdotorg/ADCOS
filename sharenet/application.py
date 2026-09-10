"""The ShareNet EXTERNAL application boundary (M010 vertical proof,
LOCK-120).

ShareNet is one of the three frozen vertical applications of
``spec/integration/vertical-proof.md``.  This module models ShareNet
exactly as the frozen proof requires: an OPAQUE external application
that speaks to ADCOS ONLY through the accepted M013 developer API
public surface (the SDK client plus the raw request representation)
and retains full authority over its own application semantics
(content distribution, P2P propagation, publisher trust, contribution
accounting, application economics — LOCK-120, Architecture 1.1 §14).

The boundary discipline enforced here:

- **Technology-neutral intent only (LOCK-102/LOCK-114).**  The intent
  spec this boundary can submit carries a frozen member vocabulary;
  any member named after a network implementation mechanism (node,
  link, tunnel, socket, ssid, bearer, adapter, provider SDK, ...) is
  rejected FAIL-CLOSED before any request is built.  ShareNet selects
  outcomes, never implementation mechanisms.
- **One credential, one transport.**  ``ShareNetApplication`` holds an
  M013 ``DeveloperApiClient`` (plus the raw request surface for the
  operations the ergonomic SDK does not wrap).  It never imports or
  touches the canonical ``ContractStore``, the ``OfferExchange``, or
  any provider-native surface: the ONLY composed dependency is the
  accepted developer API public surface.
- **Opaque typed references in, opaque typed references out.**  The
  application re-submits the ADCOS-evaluated eligible offer references
  verbatim (it never interprets offer semantics — the offers
  authority, M003, owns them).
- **No second authority.**  The ShareNet application decides nothing
  on the ADCOS side: no eligibility, no assurance, no execution, no
  settlement.  It observes and requests.

Determinism discipline (LOCK-119, the family precedent): every member
value is a grammar-checked token; every instant is caller-injected;
no wall clock, no randomness, no UUIDs, no network, no secrets.
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


class ShareNetError(ValueError):
    """A typed harness error (fail-closed, reason-coded)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


#: Frozen harness reason codes (fail-closed vocabulary).
REASON_INVALID_INPUT = "sharenet-invalid-input"
REASON_VOCABULARY = "sharenet-vocabulary"
REASON_MEMBER_AUDIT = "sharenet-member-audit"
REASON_BOUNDARY = "sharenet-boundary"
REASON_FAIL_CLOSED = "sharenet-fail-closed"
REASON_NOT_BOUND = "sharenet-not-bound"

# ----------------------------------------------------------------------
# The technology-neutral member vocabulary (LOCK-102/LOCK-114)
# ----------------------------------------------------------------------

#: The frozen member vocabulary of the ShareNet connectivity intent.
#: ShareNet describes WHAT it needs (bounded cohort, relay backhaul),
#: never HOW the network realizes it.
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

#: Network implementation member stems that MUST NOT appear in the
#: intent spec (the frozen LOCK-114 surface discipline: the request
#: members are technology-neutral; execution material rides opaque
#: typed references only).
FORBIDDEN_MEMBER_STEMS: Tuple[str, ...] = (
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

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")


def _require_token(value: object, label: str) -> str:
    if not isinstance(value, str) or _TOKEN_PATTERN.fullmatch(value) is None:
        raise ShareNetError(
            REASON_VOCABULARY,
            "%s must match the reference token grammar "
            "(^[A-Za-z0-9._:+/-]{1,128}$)" % label,
        )
    return value


def audit_member_name(name: object) -> str:
    """Fail-closed member audit (LOCK-102/LOCK-114).

    Rejects non-strings, members outside the frozen vocabulary, and
    members carrying network implementation stems.  Technology-neutral
    means technology-neutral: a ShareNet intent that names a mechanism
    never reaches the API boundary.
    """
    if not isinstance(name, str) or not name:
        raise ShareNetError(
            REASON_MEMBER_AUDIT,
            "intent member %r is not a non-empty string" % (name,),
        )
    if name not in INTENT_MEMBER_VOCABULARY:
        raise ShareNetError(
            REASON_MEMBER_AUDIT,
            "intent member %r is outside the frozen technology-neutral "
            "vocabulary %s" % (name, list(INTENT_MEMBER_VOCABULARY)),
        )
    for stem in FORBIDDEN_MEMBER_STEMS:
        if stem in name.lower():
            raise ShareNetError(
                REASON_MEMBER_AUDIT,
                "intent member %r carries the forbidden network "
                "implementation stem %r (LOCK-114: technology-neutral "
                "surface only)" % (name, stem),
            )
    return name


# ----------------------------------------------------------------------
# The ShareNet technology-neutral intent spec
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ShareNetIntentSpec:
    """ShareNet's technology-neutral connectivity intent for its
    gateway/relay fleet (frozen flow step 1).

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
        _require_token(self.purpose, "intent.purpose")
        if not self.requirements:
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "intent.requirements requires at least one normalized "
                "requirements token",
            )
        for token in self.requirements:
            _require_token(token, "intent.requirements token")
        if len(self.validity) != 2:
            raise ShareNetError(
                REASON_INVALID_INPUT, "intent.validity must be (from, to)"
            )
        if not self.termination_conditions:
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "intent.termination_conditions requires at least one kind",
            )
        _require_token(self.compensation, "intent.compensation")
        for kind, ref in self.beneficiaries:
            _require_token(kind, "beneficiary.kind")
            _require_token(ref, "beneficiary.ref")
        for kind, params in self.hard_constraints:
            if not isinstance(kind, str) or not kind:
                raise ShareNetError(
                    REASON_VOCABULARY,
                    "hard constraint kind %r must be a non-empty string" % (kind,),
                )
            for name, value in params:
                if not isinstance(name, str) or not name:
                    raise ShareNetError(
                        REASON_VOCABULARY,
                        "constraint parameter name %r must be a non-empty string"
                        % (name,),
                    )
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ShareNetError(
                        REASON_VOCABULARY,
                        "constraint parameter %r must carry a scalar numeric "
                        "value (found %s)" % (name, type(value).__name__),
                    )
        for token in self.service_properties:
            _require_token(token, "intent.service_properties token")
        if self.usage_pricing_terms is not None:
            _require_token(self.usage_pricing_terms, "intent.usage_pricing_terms")
        for token in self.assurance_obligations:
            _require_token(token, "intent.assurance_obligations token")
        for token in self.execution_scope:
            _require_token(token, "intent.execution_scope token")

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
                        "issuer": "sharenet-intent-authority",
                        "decision_refs": ["sharenet:intent:v1"],
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
                        "issuer": "sharenet-assurance-authority",
                        "decision_refs": ["sharenet:assurance:v1"],
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
# The ShareNet application (the external boundary over the M013
# public surface only)
# ----------------------------------------------------------------------

#: The ShareNet application's declared developer identity (out-of-band
#: platform material; the credential is issued by the platform, never
#: by the application itself).
SHARENET_DEVELOPER_ID = "sharenet-app-developer"
SHARENET_APPLICATION_NAME = "sharenet-connectivity-app"


@dataclass(frozen=True)
class ObservationDelivery:
    """One signed webhook observation received by the ShareNet
    endpoint (payload + headers, captured verbatim)."""

    payload: Mapping[str, Any]
    headers: Mapping[str, str]


class ShareNetApplication:
    """ShareNet as an EXTERNAL application over the accepted M013
    public surface (LOCK-120).

    Composed dependencies (the ONLY composed dependencies):

    - ``DeveloperApiClient`` — the SDK (request parity by
      construction, no hidden business authority);
    - the raw ``transport`` callable plus the issued application
      credential — for the M013 operations the ergonomic SDK does not
      wrap (webhook endpoint registration), still the exact public
      request representation.

    The application NEVER holds: the ``ContractStore``, the
    ``OfferExchange``, any provider material, any seam.  It requests,
    submits opaque references it is handed, and observes.
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
            raise ShareNetError(
                REASON_BOUNDARY,
                "ShareNetApplication requires a DeveloperApiClient (the "
                "accepted M013 SDK public surface; no other transport)",
            )
        self._client = client
        self._application_id = application_id
        self._secret = secret
        self._transport = transport
        self._api_version = api_version
        self._observations: List[ObservationDelivery] = []

    # -- identity -----------------------------------------------------

    @property
    def application_id(self) -> str:
        return self._application_id

    # -- frozen flow step 1: the technology-neutral intent -----------

    def submit_intent(
        self, *, spec: ShareNetIntentSpec, idempotency_key: str, recorded_at: str
    ) -> Any:
        """Submit the connectivity intent: the canonical contract is
        created in INTENT state (the application never sees network
        mechanics; the body is the audited creation core)."""
        return self._client.create_intent(
            idempotency_key=idempotency_key,
            intent=spec.to_request_body(recorded_at=recorded_at),
        )

    # -- frozen flow step 4: bind the ADCOS-evaluated offers ----------

    def accept_eligible_offers(
        self,
        *,
        intent_id: str,
        offer_references: Tuple[Mapping[str, Any], ...],
        idempotency_key: str,
        recorded_at: str,
    ) -> Any:
        """Accept the offer references ADCOS evaluated as eligible.

        The references are re-submitted VERBATIM (opaque typed
        references; the offers authority — M003 — owns the semantics;
        ShareNet never constructs or interprets an offer).
        """
        if not offer_references:
            raise ShareNetError(
                REASON_INVALID_INPUT,
                "accept_eligible_offers requires at least one evaluated "
                "offer reference",
            )
        for position, reference in enumerate(offer_references):
            if not isinstance(reference, Mapping):
                raise ShareNetError(
                    REASON_INVALID_INPUT,
                    "offer reference [%d] must be an opaque typed "
                    "reference mapping" % position,
                )
            if reference.get("ref_kind") != "offer":
                raise ShareNetError(
                    REASON_VOCABULARY,
                    "offer reference [%d] must carry the offer reference "
                    "kind (ShareNet submits references verbatim, never "
                    "reshapes them)" % position,
                )
        return self._client.accept_offers(
            idempotency_key=idempotency_key,
            intent_id=intent_id,
            offers=list(offer_references),
            recorded_at=recorded_at,
        )

    def activate_contract(
        self,
        *,
        intent_id: str,
        activated_at: str,
        signature_token: str,
        idempotency_key: str,
    ) -> Any:
        """Activate the contract (OFFER_SELECTED -> CONTRACT_ACTIVE)
        under the ShareNet sponsorship signature reference."""
        _require_token(signature_token, "activation.signature token")
        return self._client.activate_contract(
            idempotency_key=idempotency_key,
            intent_id=intent_id,
            activated_at=activated_at,
            signature_refs=[
                {"ref_kind": "signature", "value": signature_token}
            ],
        )

    # -- reads (the application observes; it never decides) ----------

    def contract(self, contract_id: str) -> Any:
        return self._client.get_contract(contract_id)

    def contract_usage_terms(self, contract_id: str) -> Any:
        return self._client.get_contract_usage(contract_id)

    def contract_assurance(self, contract_id: str) -> Any:
        return self._client.get_contract_assurance(contract_id)

    def terminate(
        self,
        *,
        contract_id: str,
        condition: str,
        reason_token: str,
        idempotency_key: str,
        recorded_at: str,
    ) -> Any:
        """Terminate deliberately under the recorded termination
        rules (the application-owned exit path; ADCOS semantics stay
        canonical)."""
        _require_token(reason_token, "termination.reason token")
        return self._client.terminate_contract(
            idempotency_key=idempotency_key,
            contract_id=contract_id,
            condition=condition,
            reason=reason_token,
            recorded_at=recorded_at,
        )

    # -- the observation channel (M013 webhook endpoint) -------------

    def register_observation_endpoint(
        self,
        *,
        url: str,
        event_types: Tuple[str, ...],
        idempotency_key: str,
    ) -> Any:
        """Register the ShareNet webhook endpoint through the raw
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
            raise ShareNetError(
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
    "FORBIDDEN_MEMBER_STEMS",
    "INTENT_MEMBER_VOCABULARY",
    "ObservationDelivery",
    "REASON_BOUNDARY",
    "REASON_FAIL_CLOSED",
    "REASON_INVALID_INPUT",
    "REASON_MEMBER_AUDIT",
    "REASON_NOT_BOUND",
    "REASON_VOCABULARY",
    "SHARENET_APPLICATION_NAME",
    "SHARENET_DEVELOPER_ID",
    "ShareNetApplication",
    "ShareNetError",
    "ShareNetIntentSpec",
    "audit_member_name",
]
