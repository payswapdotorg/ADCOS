"""M014 client convergence — the W049 client runtime converged onto
the Architecture 1.1 surfaces (R7-CORE-001, DEC-0101).

The client package's M014 harvest onto the Architecture 1.1
authority: the frozen WORK-049 client stays EXACTLY what its package
rules freeze — a CLIENT / CONTROLLER / PROJECTION boundary that is
never an authority — and this module is the DEC-0099-disclosed
re-baseline composition: the *unchanged* frozen client code
(:class:`client.provider.ProviderClient`,
:class:`client.runtime.ClientRuntime`, the gateway/read model, the
privacy-bounded presentation) imported BY REFERENCE and driven over
the CONVERGED 1.1 authorities:

- **contracts/** (M002) — the canonical commercial record: the W049
  "lease read" is the CONTRACT read (its own state, its own
  principal, its own accepted-offer citations); the authorization
  lease gate IS the contract's own lease lifecycle (LOCK-101 — the
  contract stays the sole authority; the emergency stop drives the
  store's OWN ``RevokeLease`` command through the converged
  authorization runtime).
- **offers/** (M003) — the canonical economic terms: the consent
  presentation's ``expected_economic_result`` is PROJECTED from the
  REAL offer records the contract selected, resolved through the
  REAL ``OfferExchange`` (``resolve_offer_reference`` — never a
  client-side offer model; the P1-2 discipline: no caller-supplied
  economics, ever).
- **evidence/** (M005) — the closed loop: the consent record is a
  REAL typed ``AttestationEvidence`` stream (pending -> granted ->
  withdrawn, one immutable ``controller-verified`` record per
  transition) inside a REAL ``EvidenceStore`` (LOCK-106/LOCK-118).
- **federation/** (M014) — the converged authorization authority:
  :class:`federation.convergence.ConvergedAuthorizationRuntime`
  implements the frozen W049 duck-typed sharing protocol over the
  contract store + the evidence store + the rate-limit surface +
  the declared authorization scope quota; this module owns NO
  authorization semantics — it delegates 1:1.

NOT a W048 restoration (the DEC-0099 discipline): there is no
containment primitive, no isolation authority, no traffic-isolation
enforcement and no ``containment.CapabilityMatrix`` here — WORK-048
stays accepted-not-restored, and the frozen ACR-012 invariant is
carried by the CONVERGED admission gate instead: the canonical
contract lease + the granted consent attestation + the declared
scope quota (an authorization quota, NOT a containment proof; the
buyer-side purchase chain — discovery/marketplace/commercial/
networkpath — stays with its own frozen seams and is NOT converged
here: no marketplace composition authority is created in this
package).

Surfaces:

- :class:`ConvergedConsentScope` — the frozen W049
  consent-presentation dimensions (``exposed_egress`` /
  ``time_quota_expiry`` / ``byte_quota`` /
  ``max_concurrent_buyers``) projected from the declared
  :class:`federation.convergence.AuthorizationScope` DATA (typed,
  fail-closed, canonical round-trip);
- :class:`ConvergedSessionView` — the W049 duck-typed session view
  over the authority's own view (``sharing_session_id`` /
  ``lease_ref`` (the CONTRACT id — the canonical commercial record)
  / ``scope`` / the canonical state family);
- :class:`ConvergedSharingRuntime` — the frozen W049 sharing
  protocol facade delegating 1:1 to the converged authorization
  runtime (prepare/grant/authorize/activate/pause/resume/withdraw/
  emergency-stop/close/notify-path-lost/account-traffic/session/
  consent — never reimplemented, never weakened);
- :class:`ConvergedClientGateway` — the canonical read window:
  the sharing/consent reads through the authority, the lease read
  as the M002 contract read with the M003 offer terms resolved by
  reference, and the authorities NOT wired here (networkpath /
  usage) refusing typed fail-closed (the frozen ComposedGateway
  discipline — never fabricated);
- :func:`build_converged_provider_client` — the composition root
  (REAL authorities only, injected deterministic clock, the
  platform-adapter boundary, typed fail-closed wiring);
- :func:`converged_client_citations` — the by-reference citation
  set of one converged world (the contract, its resolved offers,
  its typed evidence records — each digesting the cited record's
  OWN canonical bytes, LOCK-101/106/118).

Determinism (LOCK-119): injected RFC 3339 UTC instants only (no
wall clock, no randomness, no UUIDs, no network); content-derived
ids over canonical JSON; sorted iteration; typed fail-closed errors
with stable codes; secret-shaped material rejected at every
construction boundary; the frozen client's own event/request/
projection machinery is reused verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from protocol.canonicalization import canonical_json_bytes

from contracts import ContractStore
from evidence import EvidenceStore
from offers import OfferExchange, resolve_offer_reference

from federation.convergence import (
    AuthorizationScope,
    ConvergedAuthorizationRuntime,
    RateLimitPolicy,
    cite_contract,
    cite_evidence_record,
    cite_offer,
)
from federation.convergence import ChildCitation  # noqa: F401  (re-export)

from .adapters import PlatformAdapter, require_adapter
from .errors import ClientError, ClientReasonCode, FailClosedResolution
from .gateway import CanonicalGateway, GatewayRead
from .model import ClientContext, ReasonRef
from .provider import ProviderClient
from .runtime import ClientRuntime

#: The namespaced prefix for converged client identity material.
CLIENT_CONVERGENCE_PREFIX = "m014-client"

#: The gateway read authorities WIRED by this convergence (the
#: frozen ``GATEWAY_AUTHORITIES`` vocabulary consulted by label).
CONVERGED_READ_AUTHORITIES: Tuple[str, ...] = ("sharing", "commercial")

#: The frozen gateway read authorities deliberately NOT wired here
#: (their seams stay with their own authorities — the networkpath
#: and usage families; the converged client never fabricates their
#: reads and never reimplements their surfaces).
UNWIRED_READ_AUTHORITIES: Tuple[str, ...] = ("networkpath", "usage")

#: The frozen W049 presentation dimensions carried by the scope
#: projection (the consent-facts grammar — reused, never extended).
CONSENT_SCOPE_DIMENSIONS: Tuple[str, ...] = (
    "exposed_egress",
    "time_quota_expiry",
    "byte_quota",
    "max_concurrent_buyers",
)

#: Secret-shaped markers (LOCK-119; the frozen defensive grammar).
_SECRET_MARKERS = tuple(sorted((
    "private_key", "secret_key", "password", "passwd",
    "client_secret", "credential_secret", "api_key",
)))


class ClientConvergenceReasonCode:
    """The frozen typed reason vocabulary (stable codes)."""

    INVALID_INPUT = "invalid-input"
    VOCABULARY = "vocabulary"
    SECRET_REJECTED = "secret-rejected"
    TEMPORAL_INVALID = "temporal-invalid"
    NOT_FOUND = "not-found"
    AUTHORITY_REJECTED = "authority-rejected"
    COMPOSITION_INVALID = "composition-invalid"


class ClientConvergenceError(Exception):
    """The typed fail-closed composition error (stable code +
    bounded detail; consumed-domain failures are wrapped with their
    own typed reason preserved — never raw exception text into
    stored state)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = str(code)
        self.detail = str(detail)

    @property
    def reason(self) -> str:
        return self.code


def _require_reference(value: object, label: str) -> str:
    """A non-empty, non-secret-shaped reference string."""
    if not isinstance(value, str) or not value:
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    lowered = value.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.SECRET_REJECTED,
                "%s is secret-shaped material; secrets never enter "
                "converged client metadata (LOCK-119)" % label,
            )
    return value


# ---------------------------------------------------------------------------
# The consent-scope projection (the frozen W049 presentation dimensions)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvergedConsentScope:
    """The frozen W049 consent-presentation scope, projected from the
    provider's DECLARED :class:`AuthorizationScope` (the M014
    production-hardening envelope) as pure DATA.

    The projection is total and typed: ``time_quota_expiry`` is the
    declared scope's own ``valid_until`` (the authorization window's
    end); ``max_concurrent_buyers`` is the declared
    ``max_concurrent_sessions``; ``byte_quota`` is the declared
    authorization quota.  No dimension is invented, defaulted or
    clamped — a malformed declared scope fails closed at the
    authority's own construction boundary before it can reach the
    presentation."""

    exposed_egress: Tuple[str, ...]
    time_quota_expiry: str
    byte_quota: int
    max_concurrent_buyers: int

    def __post_init__(self) -> None:
        if not isinstance(self.exposed_egress, tuple) or any(
            not isinstance(item, str) or not item for item in self.exposed_egress
        ):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.INVALID_INPUT,
                "consent scope exposed_egress must be a tuple of "
                "non-empty strings",
            )
        if not isinstance(self.time_quota_expiry, str) or not self.time_quota_expiry:
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.TEMPORAL_INVALID,
                "consent scope time_quota_expiry must be a non-empty "
                "instant string",
            )
        for label, value in (
            ("byte_quota", self.byte_quota),
            ("max_concurrent_buyers", self.max_concurrent_buyers),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ClientConvergenceError(
                    ClientConvergenceReasonCode.INVALID_INPUT,
                    "consent scope %s must be an int" % label,
                )
            if value < 0:
                raise ClientConvergenceError(
                    ClientConvergenceReasonCode.INVALID_INPUT,
                    "consent scope %s must be >= 0" % label,
                )

    def to_dict(self) -> Dict[str, object]:
        return {
            "exposed_egress": list(self.exposed_egress),
            "time_quota_expiry": self.time_quota_expiry,
            "byte_quota": self.byte_quota,
            "max_concurrent_buyers": self.max_concurrent_buyers,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ConvergedConsentScope":
        if not isinstance(data, dict):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.INVALID_INPUT,
                "consent scope material must be a mapping",
            )
        return cls(
            exposed_egress=tuple(
                str(item) for item in data.get("exposed_egress", ())
            ),
            time_quota_expiry=str(data.get("time_quota_expiry", "")),
            byte_quota=int(data.get("byte_quota", -1)),
            max_concurrent_buyers=int(
                data.get("max_concurrent_buyers", -1)
            ),
        )


def consent_scope_from_declared(scope: AuthorizationScope) -> ConvergedConsentScope:
    """Project the DECLARED authorization envelope into the frozen
    W049 presentation dimensions (pure DATA; the declared scope is
    the authority's own typed record — never reconstructed here)."""
    if not isinstance(scope, AuthorizationScope):
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.INVALID_INPUT,
            "cons_scope_from_declared requires the declared "
            "AuthorizationScope (the M014 authorization envelope)",
        )
    return ConvergedConsentScope(
        exposed_egress=scope.exposed_egress,
        time_quota_expiry=scope.valid_until,
        byte_quota=scope.byte_quota,
        max_concurrent_buyers=scope.max_concurrent_sessions,
    )


# ---------------------------------------------------------------------------
# The W049 duck-typed session view (over the authority's own view)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvergedSessionView:
    """The frozen W049 duck-typed sharing-session view: the converged
    authorization authority's own session view plus the two W049
    presentation attributes the frozen client reads — ``lease_ref``
    (the CONTRACT id: the canonical commercial record that owns the
    lease) and ``scope`` (the declared envelope projected into the
    consent-presentation dimensions)."""

    session_id: str
    contract_id: str
    lease_id: str
    buyer_ref: str
    provider_ref: str
    session_ref: str
    consent_ref: str
    path_ref: str
    platform_id: str
    state: str
    termination_reason: str
    bytes_admitted: int
    prepared_at: str
    scope: ConvergedConsentScope

    @property
    def sharing_session_id(self) -> str:
        """The W049 protocol's session identity attribute."""
        return self.session_id

    @property
    def lease_ref(self) -> str:
        """The W049 protocol's canonical commercial record reference
        (the CONTRACT — the M002 authority's own id; the lease is
        the contract's own sub-record, never a parallel truth)."""
        return self.contract_id


def _session_view(
    view: Any, scope: ConvergedConsentScope
) -> ConvergedSessionView:
    """The one projection path from the authority's view onto the
    W049 duck-typed view (attribute-preserving; fail-closed on a
    non-view input)."""
    session_id = getattr(view, "session_id", None)
    if not isinstance(session_id, str) or not session_id:
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.AUTHORITY_REJECTED,
            "the converged authorization authority produced a session "
            "view without an identity (fail closed; never fabricated)",
        )
    return ConvergedSessionView(
        session_id=session_id,
        contract_id=str(getattr(view, "contract_id", "")),
        lease_id=str(getattr(view, "lease_id", "")),
        buyer_ref=str(getattr(view, "buyer_ref", "")),
        provider_ref=str(getattr(view, "provider_ref", "")),
        session_ref=str(getattr(view, "session_ref", "")),
        consent_ref=str(getattr(view, "consent_ref", "")),
        path_ref=str(getattr(view, "path_ref", "")),
        platform_id=str(getattr(view, "platform_id", "")),
        state=str(getattr(view, "state", "")),
        termination_reason=str(getattr(view, "termination_reason", "")),
        bytes_admitted=int(getattr(view, "bytes_admitted", 0) or 0),
        prepared_at=str(getattr(view, "prepared_at", "")),
        scope=scope,
    )


# ---------------------------------------------------------------------------
# The W049 sharing-protocol facade (1:1 delegation to the authority)
# ---------------------------------------------------------------------------


class ConvergedSharingRuntime:
    """The frozen W049 duck-typed sharing protocol over the CONVERGED
    authorization authority (:class:`ConvergedAuthorizationRuntime`).

    Every protocol member delegates 1:1 to the authority's public
    surface — nothing is reimplemented, weakened or cached.  The
    authority's typed denials (``ConvergenceError``, carrying the
    duck-typed ``reason`` attribute) propagate AS the canonical
    denials the frozen client preserves verbatim (the frozen
    ``_wrap_sharing_error`` discipline); this facade never swallows
    one.  NOT a W048 restoration: there is no containment or
    isolation primitive here — the admission gate is the canonical
    lease + the consent attestation + the declared quota."""

    def __init__(
        self,
        authority: ConvergedAuthorizationRuntime,
        *,
        scope: AuthorizationScope,
    ) -> None:
        if not isinstance(authority, ConvergedAuthorizationRuntime):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.COMPOSITION_INVALID,
                "the converged sharing facade requires the REAL "
                "federation ConvergedAuthorizationRuntime (the "
                "canonical authorization authority)",
            )
        if not isinstance(scope, AuthorizationScope):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.COMPOSITION_INVALID,
                "the converged sharing facade requires the DECLARED "
                "AuthorizationScope (the frozen W049 presentation "
                "dimensions ride the declared envelope as DATA)",
            )
        self._authority = authority
        self._scope = consent_scope_from_declared(scope)
        self._declared = scope

    @property
    def authority(self) -> ConvergedAuthorizationRuntime:
        """The converged authorization authority (read-only)."""
        return self._authority

    @property
    def declared_scope(self) -> AuthorizationScope:
        """The declared authorization envelope (DATA)."""
        return self._declared

    @property
    def consent_scope(self) -> ConvergedConsentScope:
        """The frozen W049 presentation dimensions (the projection)."""
        return self._scope

    # -- the frozen W049 protocol (1:1 delegation) ---------------------------

    def prepare_sharing_session(
        self,
        *,
        lease_ref: str,
        buyer_ref: str,
        provider_ref: str,
        session_ref: str,
        path_ref: str,
        scope: Any,
        platform_id: str,
    ) -> ConvergedSessionView:
        if scope is not self._declared:
            # the declared envelope is the composition's own; a
            # caller-supplied alternative would fork the presentation
            # truth — fail closed (the P1-2 discipline)
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.COMPOSITION_INVALID,
                "prepare must carry the composition's DECLARED "
                "AuthorizationScope (the presentation dimensions never "
                "fork from the declared envelope)",
            )
        view = self._authority.prepare_sharing_session(
            lease_ref=lease_ref,
            buyer_ref=buyer_ref,
            provider_ref=provider_ref,
            session_ref=session_ref,
            path_ref=path_ref,
            scope=self._declared,
            platform_id=platform_id,
        )
        return _session_view(view, self._scope)

    def grant_consent(self, session_id: str) -> Any:
        return self._authority.grant_consent(session_id)

    def authorize_sharing_session(self, session_id: str) -> Any:
        return self._authority.authorize_sharing_session(session_id)

    def activate_sharing_session(self, session_id: str) -> Any:
        return self._authority.activate_sharing_session(session_id)

    def pause_sharing_session(self, session_id: str) -> Any:
        return self._authority.pause_sharing_session(session_id)

    def resume_sharing_session(self, session_id: str) -> Any:
        return self._authority.resume_sharing_session(session_id)

    def withdraw_consent(self, session_id: str) -> Any:
        return self._authority.withdraw_consent(session_id)

    def emergency_stop(self, session_id: str) -> Any:
        return self._authority.emergency_stop(session_id)

    def close_sharing_session(self, session_id: str) -> Any:
        return self._authority.close_sharing_session(session_id)

    def notify_path_lost(
        self, session_id: str, *, candidate_path_id: Any = None
    ) -> Any:
        return self._authority.notify_path_lost(
            session_id, candidate_path_id=candidate_path_id
        )

    def account_traffic(self, session_id: str, byte_count: int) -> Any:
        return self._authority.account_traffic(session_id, byte_count)

    def session(self, session_id: str) -> ConvergedSessionView:
        return _session_view(
            self._authority.session(session_id), self._scope
        )

    def consent(self, consent_ref: str) -> Any:
        return self._authority.consent(consent_ref)


# ---------------------------------------------------------------------------
# The converged canonical read window
# ---------------------------------------------------------------------------


def _wrap_authority_read_error(
    error: Exception, authority: str, subject: str
) -> ClientError:
    """Normalize one consumed-authority read failure fail-closed (the
    frozen ComposedGateway discipline: the canonical reason is
    preserved verbatim; an unreadable subject is UNKNOWN — never a
    fabricated state)."""
    return ClientError(
        ClientReasonCode.CANONICAL_DENIED,
        "the canonical %s read for %r failed (%s: %s) — the state is "
        "UNKNOWN and the client fails closed (never fabricated)"
        % (authority, subject, getattr(error, "reason", "error"), error),
        resolution=FailClosedResolution.UNKNOWN,
        canonical_reason=ReasonRef(
            code=str(getattr(error, "reason", "%s-error" % authority)),
            source=authority,
            severity="error",
        ),
    )


class ConvergedClientGateway(CanonicalGateway):
    """The converged canonical read window over the 1.1 authorities.

    Reads (public accessors only — never store writes, never an
    authority construction):

    - ``read_clock`` — the injected deterministic clock seam;
    - ``read_sharing_session`` / ``read_consent`` — the converged
      authorization authority's OWN ``session``/``consent`` reads
      (through the W049 facade; the frozen binding tuple);
    - ``read_lease`` — the M002 CONTRACT read: the canonical
      commercial record's own state and principal, plus the
      canonical economic terms resolved from the REAL M003 offer
      records the contract selected (``resolve_offer_reference`` —
      by reference, fail-closed typed on any consumed-domain
      failure; NO offer model exists on this side);
    - ``read_path`` / ``read_usage_account`` — NOT WIRED: the
      networkpath/usage seams stay with their own authorities; the
      reads refuse typed fail-closed (the frozen ComposedGateway
      discipline — UNKNOWN, never fabricated).
    """

    def __init__(
        self,
        *,
        clock: Any,
        sharing: ConvergedSharingRuntime,
        store: ContractStore,
        exchange: OfferExchange,
    ) -> None:
        super().__init__()
        if clock is None or not callable(getattr(clock, "now", None)):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.COMPOSITION_INVALID,
                "the converged gateway requires an injected clock seam "
                "(deterministic batteries always wire one; never a wall "
                "clock)",
            )
        if not isinstance(sharing, ConvergedSharingRuntime):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.COMPOSITION_INVALID,
                "the converged gateway requires the ConvergedSharingRuntime "
                "facade (the canonical authorization reads ride it)",
            )
        if not isinstance(store, ContractStore):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.COMPOSITION_INVALID,
                "the converged gateway requires a REAL contracts."
                "ContractStore (LOCK-101 — the canonical commercial record)",
            )
        if not isinstance(exchange, OfferExchange):
            raise ClientConvergenceError(
                ClientConvergenceReasonCode.COMPOSITION_INVALID,
                "the converged gateway requires a REAL offers."
                "OfferExchange (LOCK-109 — the canonical economic terms "
                "resolved by reference)",
            )
        self._clock = clock
        self._sharing = sharing
        self._store = store
        self._exchange = exchange

    # -- the clock seam -------------------------------------------------------

    def read_clock(self) -> str:
        return str(self._clock.now())

    # -- the sharing reads (through the authority) ------------------------------

    def read_sharing_session(self, sharing_session_id: str) -> GatewayRead:
        if not isinstance(sharing_session_id, str) or not sharing_session_id:
            raise ClientError(
                ClientReasonCode.INVALID_INPUT,
                "sharing_session_id must be non-empty",
            )
        self._require_reachable()
        try:
            session = self._sharing.session(sharing_session_id)
        except ClientError:
            raise
        except Exception as error:
            raise _wrap_authority_read_error(
                error, "sharing", sharing_session_id
            ) from error
        return GatewayRead(
            authority="sharing",
            subject=sharing_session_id,
            state=str(session.state),
            observed_at=self.read_clock(),
            bindings=(
                ("buyer_ref", str(session.buyer_ref)),
                ("provider_ref", str(session.provider_ref)),
                ("session_ref", str(session.session_ref)),
                ("consent_ref", str(session.consent_ref)),
                ("termination_reason", str(session.termination_reason)),
                ("path_ref", str(session.path_ref)),
            ),
        )

    def read_consent(self, consent_id: str) -> GatewayRead:
        if not isinstance(consent_id, str) or not consent_id:
            raise ClientError(
                ClientReasonCode.INVALID_INPUT,
                "consent_id must be non-empty",
            )
        self._require_reachable()
        try:
            consent = self._sharing.consent(consent_id)
        except ClientError:
            raise
        except Exception as error:
            raise _wrap_authority_read_error(
                error, "sharing", consent_id
            ) from error
        return GatewayRead(
            authority="sharing",
            subject=consent_id,
            state=str(consent.state),
            observed_at=self.read_clock(),
            bindings=(
                ("provider_ref", str(consent.provider_ref)),
                ("buyer_ref", str(consent.buyer_ref)),
            ),
        )

    # -- the commercial read (the CONTRACT + the resolved offers) ----------------

    def read_lease(self, transaction_id: str) -> GatewayRead:
        """The converged commercial read: ``transaction_id`` is the
        CONTRACT id (the canonical commercial record).  The economic
        terms binding is the CANONICAL serialization of the REAL
        offer records the contract selected — resolved through the
        offers authority's own resolution surface at the read
        instant, never client-supplied (P1-2).  A contract whose
        selected offers cannot be resolved (withdrawn / expired /
        unknown) fails closed typed — the economics are UNKNOWN and
        the consent presentation over them is refused downstream by
        the frozen client."""
        if not isinstance(transaction_id, str) or not transaction_id:
            raise ClientError(
                ClientReasonCode.INVALID_INPUT,
                "transaction_id must be non-empty",
            )
        self._require_reachable()
        at_instant = self.read_clock()
        try:
            contract = self._store.contract(transaction_id)
        except Exception as error:
            raise _wrap_authority_read_error(
                error, "commercial", transaction_id
            ) from error
        accepted = getattr(contract, "accepted_offers", None)
        if not isinstance(accepted, tuple) or not accepted:
            # the honest empty binding: the frozen client refuses
            # the consent presentation over unknown economics
            offer_terms = ""
        else:
            terms: list = []
            try:
                for reference in accepted:
                    record = resolve_offer_reference(
                        self._exchange, reference, at_instant=at_instant
                    )
                    terms.append(record.to_dict())
            except Exception as error:
                raise _wrap_authority_read_error(
                    error, "commercial", transaction_id
                ) from error
            offer_terms = canonical_json_bytes(
                {"offers": terms}
            ).decode("utf-8")
        principal = getattr(contract, "principal", None)
        buyer_ref = str(getattr(principal, "principal_ref", "") or "")
        return GatewayRead(
            authority="commercial",
            subject=transaction_id,
            state=str(contract.state),
            observed_at=at_instant,
            bindings=(
                ("buyer_ref", buyer_ref),
                ("offer_terms", offer_terms),
            ),
        )

    # -- the deliberately unwired reads (fail closed) -----------------------------

    def read_path(self, path_id: str) -> GatewayRead:
        raise ClientError(
            ClientReasonCode.STALE_STATE,
            "no NetworkPath machinery is wired into this gateway "
            "(the networkpath seam stays with its own authority; "
            "UNKNOWN; never fabricated)",
        )

    def read_usage_account(self, transaction_id: str) -> GatewayRead:
        raise ClientError(
            ClientReasonCode.STALE_STATE,
            "no usage ledger is wired into this gateway (the usage seam "
            "stays with its own authority; UNKNOWN; never fabricated)",
        )


# ---------------------------------------------------------------------------
# The composition root (the DEC-0099 re-baseline wiring)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConvergedProviderWorld:
    """One fully-wired converged provider-mode client world (the
    composition record: every member is the REAL object; nothing is
    duplicated or shadowed)."""

    client: ProviderClient
    runtime: ClientRuntime
    gateway: ConvergedClientGateway
    sharing: ConvergedSharingRuntime
    authority: ConvergedAuthorizationRuntime
    store: ContractStore
    evidence: EvidenceStore
    exchange: OfferExchange
    scope: AuthorizationScope
    clock: Any


def build_converged_provider_client(
    *,
    store: ContractStore,
    evidence: EvidenceStore,
    exchange: OfferExchange,
    adapter: PlatformAdapter,
    clock: Any,
    scope: AuthorizationScope,
    user_ref: str,
    device_ref: str,
    application_ref: str,
    platform_id: str,
    rate_policy: Any = None,
) -> ConvergedProviderWorld:
    """Compose the frozen W049 provider client over the converged 1.1
    authorities (the DEC-0099 re-baseline composition root).

    Every authority is REAL and injected (typed fail-closed wiring):
    the contract store owns the commercial record and the lease
    gate; the evidence store owns the consent attestation stream;
    the offers exchange owns the economic terms; the converged
    authorization runtime (constructed here over exactly those
    authorities) owns the canonical authorization protocol; the
    platform adapter stays behind the frozen W049 adapter boundary;
    the clock is the deterministic injected seam.  The frozen
    :class:`ProviderClient` is imported BY REFERENCE — unchanged,
    never wrapped, never subclassed into an authority."""

    if not isinstance(store, ContractStore):
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.COMPOSITION_INVALID,
            "the converged provider world requires a REAL contracts."
            "ContractStore (LOCK-101)",
        )
    if not isinstance(evidence, EvidenceStore):
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.COMPOSITION_INVALID,
            "the converged provider world requires a REAL evidence."
            "EvidenceStore (LOCK-106)",
        )
    if not isinstance(exchange, OfferExchange):
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.COMPOSITION_INVALID,
            "the converged provider world requires a REAL offers."
            "OfferExchange (LOCK-109)",
        )
    if rate_policy is not None and not isinstance(
        rate_policy, RateLimitPolicy
    ):
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.COMPOSITION_INVALID,
            "the optional rate policy must be a REAL "
            "federation.RateLimitPolicy (LOCK-117 production hardening)",
        )
    adapter = require_adapter(adapter)
    for label, value in (
        ("user_ref", user_ref),
        ("device_ref", device_ref),
        ("application_ref", application_ref),
        ("platform_id", platform_id),
    ):
        _require_reference(value, "the converged client context %s" % label)
    authority = ConvergedAuthorizationRuntime(
        store=store,
        evidence=evidence,
        clock=clock,
        rate_policy=rate_policy,
    )
    sharing = ConvergedSharingRuntime(authority, scope=scope)
    gateway = ConvergedClientGateway(
        clock=clock, sharing=sharing, store=store, exchange=exchange
    )
    context = ClientContext(
        user_ref=user_ref,
        device_ref=device_ref,
        application_ref=application_ref,
        platform_id=platform_id,
    )
    runtime = ClientRuntime(
        context=context, adapter=adapter, gateway=gateway
    )
    client = ProviderClient(runtime=runtime, sharing=sharing)
    return ConvergedProviderWorld(
        client=client,
        runtime=runtime,
        gateway=gateway,
        sharing=sharing,
        authority=authority,
        store=store,
        evidence=evidence,
        exchange=exchange,
        scope=scope,
        clock=clock,
    )


# ---------------------------------------------------------------------------
# The by-reference citation set (the convergence proof surface)
# ---------------------------------------------------------------------------


def converged_client_citations(
    world: ConvergedProviderWorld,
    *,
    issuer: str,
    cited_at: str,
) -> Tuple[Any, ...]:
    """The by-reference citation set of one converged client world:
    the M002 contract (its own canonical bytes), every REAL M003
    offer record the contract selected (resolved through the
    exchange and digested over their OWN canonical serialization),
    and every REAL M005 typed evidence record the world's consent
    stream produced (their own record identities and dicts).

    The citations are DATA with provenance (LOCK-118): each digest
    is computed at construction from the cited record's OWN
    canonical bytes — never caller-supplied, never reimplemented
    (LOCK-101/106/109/117).  Fail-closed typed on any
    consumed-domain failure."""

    if not isinstance(world, ConvergedProviderWorld):
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.INVALID_INPUT,
            "converged_client_citations requires a "
            "ConvergedProviderWorld",
        )
    _require_reference(issuer, "citation issuer")
    citations: list = []
    try:
        for session_view in sorted(
            world.authority.sessions(), key=lambda view: view.session_id
        ):
            contract = world.store.contract(session_view.contract_id)
            citations.append(
                cite_contract(
                    contract, issuer=issuer, cited_at=cited_at
                )
            )
            for reference in contract.accepted_offers:
                record = resolve_offer_reference(
                    world.exchange, reference, at_instant=cited_at
                )
                citations.append(
                    cite_offer(
                        record, issuer=issuer, cited_at=cited_at
                    )
                )
            for record in world.evidence.records():
                if str(getattr(record, "contract_ref", "")) == str(
                    session_view.contract_id
                ):
                    citations.append(
                        cite_evidence_record(
                            record, issuer=issuer, cited_at=cited_at
                        )
                    )
    except ClientConvergenceError:
        raise
    except Exception as error:  # consumed-domain isolation
        raise ClientConvergenceError(
            ClientConvergenceReasonCode.AUTHORITY_REJECTED,
            "the citation composition was rejected by a consumed "
            "authority (%s: %s)"
            % (getattr(error, "reason", "authority-error"), error),
        ) from error
    return tuple(citations)


__all__ = [
    # the frozen vocabularies
    "CLIENT_CONVERGENCE_PREFIX",
    "CONVERGED_READ_AUTHORITIES",
    "UNWIRED_READ_AUTHORITIES",
    "CONSENT_SCOPE_DIMENSIONS",
    # typed errors
    "ClientConvergenceError",
    "ClientConvergenceReasonCode",
    # the consent-scope projection (the frozen W049 dimensions)
    "ConvergedConsentScope",
    "consent_scope_from_declared",
    # the W049 duck-typed session view
    "ConvergedSessionView",
    # the W049 sharing-protocol facade (1:1 delegation)
    "ConvergedSharingRuntime",
    # the converged canonical read window
    "ConvergedClientGateway",
    # the composition root (the DEC-0099 re-baseline wiring)
    "ConvergedProviderWorld",
    "build_converged_provider_client",
    # the by-reference citation surface
    "converged_client_citations",
    # the re-exported citation record type (the convergence DATA)
    "ChildCitation",
]
