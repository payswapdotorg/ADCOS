"""The RoamLink EXTERNAL application boundary (M011, LOCK-120).

This module models RoamLink as what the frozen vertical-proof
boundary (spec/integration/vertical-proof.md, ACR-014) demands:
an EXTERNAL application that requests connectivity for a defined
subscriber cohort and retains authority over mobile observation,
device context, eSIM product behavior and mobile UX.

The discipline here is STRUCTURAL (LOCK-120, LOCK-102):

- The boundary composes ADCOS ONLY through the accepted
  developer API surface (M013, DEC-0113): the
  :class:`developerapi.sdk.DeveloperApiClient` over an injected
  transport.  This module imports NOTHING but ``developerapi``
  and the standard library -- never ``contracts``, ``offers``,
  ``usage``, ``commercial``, and never any pending child domain
  (the battery AST-audits this).  RoamLink never imports
  provider-native APIs into its core (the frozen boundary's
  architectural acceptance clause).
- The subscriber cohort is OPAQUE: a bounded set of opaque
  member handles (``roamlink-cohort:v1:<region>:<handle>``).
  No subscriber identity, no device identifiers, no mobile
  subscription material ever crosses into ADCOS; the cohort
  membership stays RoamLink's (LOCK-120) and secret-shaped
  material is rejected (LOCK-119).
- The connectivity request is TECHNOLOGY-NEUTRAL (LOCK-102):
  normalized requirements as opaque typed references, service-
  level hard constraints, a validity window, termination rules,
  and referenced usage/assurance/execution semantics.  It never
  names an implementation mechanism, a vendor, or an access
  technology.
- The boundary NEVER implements RoamLink's mobile observation,
  device context, eSIM product behavior, or mobile UX.  It holds
  an OPAQUE application-owned state blob (the application's own
  product/UX material, never sent through any request surface)
  -- ADCOS supplies connectivity for the cohort only.
- The boundary never becomes a connectivity-contract authority
  (LOCK-117/LOCK-120): it holds no contract store, drives no
  contract command, and mutates no ADCOS authority.  It observes
  execution status, assurance events and usage semantics
  through the developer API's public reads and the signed
  webhook observation channel only.

Determinism: injected instants only (no wall clock), no
randomness, no UUIDs, no network, sorted iteration everywhere,
content-derived digests over canonical JSON.  Fail closed with
typed errors on every boundary violation.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from developerapi import (
    Capability,
    DeveloperApiClient,
    DeveloperApiError,
)
from developerapi.sdk import DuplicateDetector, WebhookVerifier

from .errors import RoamLinkError, RoamLinkReason

#: The opaque cohort-handle grammar: a bounded, lowercase,
#: region-and-handle-scoped opaque reference.  Deliberately NOT
#: a subscriber identity: no MSISDN/IMSI/EID-shaped material can
#: match it (LOCK-120/LOCK-119).
COHORT_HANDLE_PATTERN = re.compile(
    r"^roamlink-cohort:v1:[a-z0-9][a-z0-9-]{0,31}:[a-z0-9][a-z0-9-]{0,31}$"
)

#: The opaque cohort member grammar (one bounded beneficiary
#: handle inside the cohort; enumerated, never identified).
COHORT_MEMBER_PATTERN = re.compile(
    r"^roamlink-cohort:v1:[a-z0-9][a-z0-9-]{0,31}:[a-z0-9][a-z0-9-]{0,31}"
    r":m[0-9]{3}$"
)

#: Subscriber-identity-shaped tokens that may NEVER cross the
#: application boundary into ADCOS (opaque-handle discipline;
#: the battery scans every request the boundary builds).
_SUBSCRIBER_IDENTITY_TOKENS = (
    "msisdn",
    "imsi",
    "eid",
    "iccid",
    "ki",
    "opc",
    "subscription_key",
    "sim_serial",
    "phone_number",
)

#: Vertical application-semantics tokens that may never appear
#: in what the boundary sends ADCOS (LOCK-120: ADCOS supplies
#: connectivity; the mobile/eSIM/UX semantics stay RoamLink's).
_VERTICAL_SEMANTIC_TOKENS = (
    "esim",
    "sim_profile",
    "install_profile",
    "roaming_banner",
    "home_screen",
    "ux_flow",
    "device_telemetry",
    "mobile_observation",
)

#: The capability set the RoamLink application credential
#: carries: the developer-API surface of the vertical (create
#: intents, accept offers, activate, read lifecycle/assurance/
#: usage, register webhooks + receive signed observations).  It
#: is exactly the accepted M013 route surface -- nothing more.
ROAMLINK_CAPABILITIES: Tuple[str, ...] = (
    Capability.INTENTS_READ,
    Capability.INTENTS_WRITE,
    Capability.USAGE_READ,
    Capability.ASSURANCE_READ,
    Capability.WEBHOOKS_READ,
    Capability.WEBHOOKS_WRITE,
)


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RoamLinkError(
            RoamLinkReason.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    return value


def _token_pattern(token: str) -> "re.Pattern[str]":
    """A word-boundary pattern for one forbidden token (the scan
    must not false-positive on substrings of legitimate member
    names like ``kind``)."""
    return re.compile(r"\b%s\b" % re.escape(token), re.IGNORECASE)


_TOKEN_PATTERNS = tuple(
    (token, _token_pattern(token)) for token in _SUBSCRIBER_IDENTITY_TOKENS
) + tuple(
    (token, _token_pattern(token)) for token in _VERTICAL_SEMANTIC_TOKENS
)


def _scan_boundary_material(material: str, label: str) -> None:
    """The LOCK-120/LOCK-119 outbound scan: subscriber-identity-
    shaped and vertical-semantics tokens never cross the
    application boundary into ADCOS."""
    for token, pattern in _TOKEN_PATTERNS:
        if pattern.search(material):
            raise RoamLinkError(
                RoamLinkReason.COHORT_NOT_OPAQUE
                if token in _SUBSCRIBER_IDENTITY_TOKENS
                else RoamLinkReason.VERTICAL_SEMANTICS_REJECTED,
                "%s carries %s (%r); the cohort stays opaque to "
                "ADCOS and ADCOS supplies connectivity only "
                "(LOCK-120)" % (label, token, token),
            )


@dataclass(frozen=True)
class SubscriberCohort:
    """A DEFINED subscriber cohort as an opaque bounded scope.

    ``cohort_handle`` is the opaque cohort identity (grammar-
    validated); ``member_count`` is the bounded cohort size (a
    COUNT, never an identity list).  The enumerated opaque
    member handles are derived deterministically from the
    handle + count: they are bounded beneficiary references for
    the canonical contract, never subscriber identities.  The
    real membership table (which subscriber is which member)
    stays inside RoamLink and never crosses this boundary."""

    cohort_handle: str
    member_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.cohort_handle, str) or (
            COHORT_HANDLE_PATTERN.fullmatch(self.cohort_handle) is None
        ):
            raise RoamLinkError(
                RoamLinkReason.COHORT_NOT_OPAQUE,
                "cohort_handle %r must match the opaque cohort grammar "
                "roamlink-cohort:v1:<region>:<handle> (no subscriber "
                "identity material may cross; LOCK-120)" % (self.cohort_handle,),
            )
        if (
            not isinstance(self.member_count, int)
            or isinstance(self.member_count, bool)
            or not 1 <= self.member_count <= 100000
        ):
            raise RoamLinkError(
                RoamLinkReason.INVALID_INPUT,
                "member_count must be an integer in [1, 100000] "
                "(a bounded cohort scope)",
            )

    def member_handles(self) -> Tuple[str, ...]:
        """The enumerated OPAQUE member handles (deterministic,
        sorted; bounded beneficiary references)."""
        return tuple(
            "%s:m%03d" % (self.cohort_handle, index)
            for index in range(1, self.member_count + 1)
        )

    def beneficiaries_payload(self) -> Tuple[Dict[str, str], ...]:
        """The canonical beneficiary-scope payload for the
        technology-neutral creation core (opaque refs only)."""
        return tuple(
            {"beneficiary_kind": "USER", "beneficiary_ref": handle}
            for handle in self.member_handles()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cohort_handle": self.cohort_handle,
            "member_count": self.member_count,
            "opaque": True,
        }

    def opaque_digest(self) -> str:
        """A digest over the opaque cohort scope (handles +
        count; no identity material exists to digest)."""
        document = {
            "cohort_handle": self.cohort_handle,
            "member_count": self.member_count,
            "members": list(self.member_handles()),
        }
        return "sha256:" + hashlib.sha256(
            ("%s" % sorted(document.items())).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class CohortConnectivityRequest:
    """The technology-neutral cohort connectivity request
    (LOCK-102): what RoamLink asks ADCOS for, expressed as
    service-level facts only.

    - ``requirement_values``: opaque normalized-requirements
      reference VALUES (the requirements authority owns their
      semantics; RoamLink cites them opaquely).
    - ``hard_constraints``: the service-level constraint
      envelope (latency bound, throughput floor, geography,
      availability floor -- the frozen M002 constraint
      vocabulary kinds; never an implementation mechanism).
    - ``validity``/``termination``/``recorded_at``: the canonical
      creation-core members.
    - ``usage_pricing_terms_value`` / ``assurance_obligation_values``
      / ``execution_scope_values``: the referenced semantics
      (typed reference VALUES; the owning authorities stay
      theirs).
    """

    cohort: SubscriberCohort
    requirement_values: Tuple[str, ...]
    hard_constraints: Tuple[Dict[str, Any], ...]
    validity: Dict[str, str]
    termination: Dict[str, Any]
    recorded_at: str
    usage_pricing_terms_value: Optional[str] = None
    assurance_obligation_values: Tuple[str, ...] = ()
    execution_scope_values: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.recorded_at, "request.recorded_at")
        reqs = self.requirement_values
        if not isinstance(reqs, tuple) or not reqs:
            raise RoamLinkError(
                RoamLinkReason.INVALID_INPUT,
                "request.requirement_values requires at least one opaque "
                "normalized-requirements reference (LOCK-102)",
            )
        for value in reqs:
            _require_text(value, "request.requirement_values entry")
        if not isinstance(self.hard_constraints, tuple):
            raise RoamLinkError(
                RoamLinkReason.INVALID_INPUT,
                "request.hard_constraints must be a tuple of constraint "
                "payloads",
            )
        for constraint in self.hard_constraints:
            if not isinstance(constraint, Mapping) or "kind" not in constraint:
                raise RoamLinkError(
                    RoamLinkReason.INVALID_INPUT,
                    "request.hard_constraints entries must carry a kind",
                )

    def intent_body(self) -> Dict[str, Any]:
        """The canonical technology-neutral creation-core request
        body for ``POST /api/{version}/intents``.

        The outbound LOCK-120/LOCK-119 scan runs on the built
        body: subscriber-identity-shaped or vertical-semantics
        material never crosses into ADCOS."""
        body: Dict[str, Any] = {
            "requirements": [
                {
                    "ref_kind": "intent-requirements",
                    "value": value,
                    "provenance": {
                        "issuer": "roamlink-application",
                        "decision_refs": ["roamlink-cohort-request"],
                    },
                }
                for value in self.requirement_values
            ],
            "beneficiaries": list(self.cohort.beneficiaries_payload()),
            "hard_constraints": [dict(c) for c in self.hard_constraints],
            "validity": dict(self.validity),
            "termination": dict(self.termination),
            "recorded_at": self.recorded_at,
        }
        if self.usage_pricing_terms_value is not None:
            body["usage_pricing_terms"] = {
                "ref_kind": "usage-pricing-terms",
                "value": self.usage_pricing_terms_value,
                "provenance": {
                    "issuer": "roamlink-application",
                    "decision_refs": ["roamlink-commercial-envelope"],
                },
            }
        if self.assurance_obligation_values:
            body["assurance_obligations"] = [
                {
                    "ref_kind": "assurance-obligation",
                    "value": value,
                    "provenance": {
                        "issuer": "adcos-assurance",
                        "decision_refs": ["roamlink-cohort-request"],
                    },
                }
                for value in self.assurance_obligation_values
            ]
        if self.execution_scope_values:
            body["execution_scope"] = [
                {"ref_kind": "execution-scope", "value": value}
                for value in self.execution_scope_values
            ]
        import json

        _scan_boundary_material(
            json.dumps(body, sort_keys=True), "the cohort request body"
        )
        return body


class RoamLinkBoundary:
    """The RoamLink application boundary over the developer API.

    Holds: the SDK client (injected transport), the consumer-side
    webhook verifier + duplicate detector, the opaque
    application-owned state blob (never sent anywhere), and the
    observation log (what RoamLink received: execution status,
    assurance events, signed observations -- all attributable to
    the one contract)."""

    def __init__(
        self,
        *,
        client: DeveloperApiClient,
        webhook_secret: str,
        verifier_clock: Any,
        verifier_tolerance: int = 86400,
        application_state_blob: bytes = b"",
    ) -> None:
        if not isinstance(client, DeveloperApiClient):
            raise RoamLinkError(
                RoamLinkReason.INVALID_INPUT,
                "the boundary requires a developerapi DeveloperApiClient "
                "(the accepted M013 application surface; LOCK-120)",
            )
        self._client = client
        self._verifier = WebhookVerifier(
            secret=webhook_secret,
            clock=verifier_clock,
            tolerance=verifier_tolerance,
        )
        self._duplicates = DuplicateDetector()
        # LOCK-120: the application-owned opaque state (RoamLink's
        # own product/UX material).  ADCOS never sees it; there is
        # no request surface that carries it.
        self._application_state_blob = bytes(application_state_blob)
        self._observations: List[Dict[str, Any]] = []

    # -- application-owned material (never crosses) ------------------

    def application_state_digest(self) -> str:
        """A digest over the opaque application-owned state (the
        proof artifact: the blob exists, stays RoamLink's, and
        never enters any ADCOS surface)."""
        return "sha256:" + hashlib.sha256(
            b"roamlink-application-state:" + self._application_state_blob
        ).hexdigest()

    def application_state_crossed(
        self, material: str
    ) -> bool:
        """True when the opaque application state material appears
        in some ADCOS-side surface (the battery's negative probe:
        it must always be False)."""
        return self._application_state_blob.decode("utf-8", "replace") in material

    # -- the vertical flow surface (the M013 route set) ----------------

    def register_observation_endpoint(
        self, *, idempotency_key: str, url: str, event_types: Tuple[str, ...]
    ) -> Any:
        """Register the RoamLink webhook observation endpoint
        (where ADCOS delivers signed observation events)."""
        _require_text(url, "endpoint url")
        return self._client.register_webhook_endpoint(
            idempotency_key=idempotency_key,
            url=url,
            event_types=event_types,
        )

    def request_cohort_connectivity(
        self, *, idempotency_key: str, request: CohortConnectivityRequest
    ) -> Any:
        """STEP 1: request connectivity for the defined subscriber
        cohort (technology-neutral; LOCK-102/LOCK-120)."""
        return self._client.create_intent(
            idempotency_key=idempotency_key,
            intent=request.intent_body(),
        )

    def accept_provider_offers(
        self,
        *,
        idempotency_key: str,
        intent_id: str,
        offer_references: Tuple[Mapping[str, Any], ...],
        recorded_at: str,
    ) -> Any:
        """STEP 3: accept the exposed provider offers (opaque
        TYPED REFERENCES ONLY -- the offers authority owns the
        semantics; RoamLink never sees provider-native APIs)."""
        if not offer_references:
            raise RoamLinkError(
                RoamLinkReason.INVALID_INPUT,
                "offer acceptance requires at least one typed offer "
                "reference",
            )
        return self._client.accept_offers(
            idempotency_key=idempotency_key,
            intent_id=intent_id,
            offers=offer_references,
            recorded_at=recorded_at,
        )

    def activate_acceptance(
        self,
        *,
        idempotency_key: str,
        intent_id: str,
        activated_at: str,
        signature_value: str,
    ) -> Any:
        """STEP 3: activate the accepted contract (the acceptance
        signature rides as a typed reference)."""
        return self._client.activate_contract(
            idempotency_key=idempotency_key,
            intent_id=intent_id,
            activated_at=activated_at,
            signature_refs=(
                {
                    "ref_kind": "signature",
                    "value": signature_value,
                },
            ),
        )

    def read_execution_status(self, contract_id: str) -> Any:
        """STEP 4: read the execution status observation for the
        one contract (the lifecycle route: the honest
        classification derived from the canonical contract state
        machine; physical connectivity is never claimed)."""
        _require_text(contract_id, "contract id")
        return self._client.get_intent_lifecycle(contract_id)

    def read_assurance(self, contract_id: str) -> Any:
        """STEP 4: read the assurance observation for the one
        contract (obligations as typed references + the
        contract-recorded outcomes)."""
        _require_text(contract_id, "contract id")
        return self._client.get_contract_assurance(contract_id)

    def read_usage_semantics(self, contract_id: str) -> Any:
        """STEP 4: read the usage semantics for the one contract
        (the opaque usage-pricing-terms typed reference)."""
        _require_text(contract_id, "contract id")
        return self._client.get_contract_usage(contract_id)

    def receive_observation(
        self, headers: Mapping[str, str], payload: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """STEP 4: receive + verify one signed observation event
        (signature verification, duplicate detection, attribution
        to the one contract through the event's resource id)."""
        try:
            event = self._verifier.verify(headers, payload)
        except DeveloperApiError as error:
            raise RoamLinkError(
                RoamLinkReason.ATTRIBUTION_INVALID,
                "the observation failed consumer-side verification: %s"
                % error.reason,
            ) from None
        if not self._duplicates.observe(event.event_id):
            raise RoamLinkError(
                RoamLinkReason.ATTRIBUTION_INVALID,
                "duplicate observation event %r (rejected by the "
                "consumer-side duplicate detector)" % event.event_id,
            )
        record = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "resource_kind": event.resource_kind,
            "resource_id": event.resource_id,
            "resource_version": event.resource_version,
            "correlation": event.correlation,
        }
        self._observations.append(record)
        return dict(record)

    def received_observations(self) -> Tuple[Dict[str, Any], ...]:
        """Every verified observation RoamLink received (sorted by
        event id; each attributable to a resource id)."""
        return tuple(
            sorted(self._observations, key=lambda r: r["event_id"])
        )

    def observations_for(self, contract_id: str) -> Tuple[Dict[str, Any], ...]:
        """The verified observations attributable to the one
        contract (typed-reference attribution)."""
        _require_text(contract_id, "contract id")
        return tuple(
            record
            for record in self.received_observations()
            if record["resource_id"] == contract_id
        )


__all__ = [
    "COHORT_HANDLE_PATTERN",
    "COHORT_MEMBER_PATTERN",
    "ROAMLINK_CAPABILITIES",
    "CohortConnectivityRequest",
    "RoamLinkBoundary",
    "SubscriberCohort",
]
