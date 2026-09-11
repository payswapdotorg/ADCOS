"""M014 Production Federation convergence (R7-CORE-001, DEC-0101).

The CONVERGENCE CHILD's provider-domain surface: the WORK-015
federation package harvested onto the Architecture 1.1 authority and
production-hardened (the R7 charter "### M014" scope: provider
domains, authorization, evidence, compatibility, rate limits and
revocation under the LOCK-117 discipline — deterministic, typed,
fail-closed).

The convergence is consumed BY REFERENCE, never reimplemented (the
M008/M009 precedents):

- **contracts/** (M002) — the canonical citation: every converged
  authorization binds to a REAL ``ConnectivityContract`` and its own
  lease lifecycle (``GrantLease``/``RevokeLease``/``ExpireLease``
  through the store's public command surface); the lease gate, the
  expiry projection and the revocation path ARE the contract's own
  semantics (LOCK-101/LOCK-117).
- **offers/** (M003) — the capability-exchange citation: provider
  offers are cited as typed DATA (the offer's own canonical bytes and
  identity); no second offer model exists here.
- **executionplans/** + **adapters/** (M006/M007) — the mechanism
  surface: plans and adapter capability views are cited as opaque
  references with their own digests (LOCK-109/LOCK-110); this module
  never translates a plan or calls an adapter.
- **replan/** (M008) — the failover discipline: replan decisions are
  cited as DATA with their own decision identity; a failover citation
  is provenance, never a re-decision.
- **usage/commercial/allocation/payment** (M009) — the commercial
  track: settlement references ride as opaque typed citations
  (LOCK-113); no commercial semantics migrate into this package.
- **evidence/ + assurance/** (M005) — the closed loop: peer-domain
  citations lift into the REAL typed evidence record space
  (``AttestationEvidence``) through the ONE sanctioned seam
  (:func:`peer_evidence_from_citation`, the
  ``peer_claim_from_exchange`` discipline); assurance evaluations are
  cited by their own evaluation identity.
- **sharenet/roamlink/comos** (M010/M011/M012) — the integration
  patterns: vertical proofs are cited as DATA patterns (LOCK-120);
  no vertical semantics are owned here.

Production hardening (LOCK-117 discipline):

- **rate limits** — :class:`RateLimitPolicy` /
  :class:`RateLimitState` / :func:`check_rate_limit`: a deterministic
  fixed-window admission counter over INJECTED instants (no wall
  clock); exceed fails closed with the typed ``rate-limited`` reason.
- **revocation** — :class:`CitationRevocation` with the explicit
  ``pending -> propagated -> confirmed`` propagation discipline
  (idempotent, append-only, history-preserving — the M008/M039
  disciplines) and the authority-side session revocation
  (:meth:`ConvergedAuthorizationRuntime.revoke_authorization`).
- **lease lifecycle** — the converged authorization sessions gate on
  the CONTRACT's own lease states; expiry is observed through the
  store's own ``expire_leases_if_due`` surface (never a local timer).
- **compatibility** — the citation vocabulary is frozen and typed;
  unknown authorities/kinds fail closed.

The DEC-0099 client re-baseline authority:
:class:`ConvergedAuthorizationRuntime` implements the frozen W049
client's duck-typed canonical-authorization protocol
(``prepare_sharing_session``/``grant_consent``/``authorize_sharing_
session``/``activate_sharing_session``/``pause_sharing_session``/
``resume_sharing_session``/``close_sharing_session``/
``withdraw_consent``/``emergency_stop``/``notify_path_lost``/
``account_traffic``/``session``/``consent``) over the converged 1.1
authorities — a REAL contract store (the lease gate), a REAL typed
evidence store (the consent record), the rate-limit surface and the
declared authorization scope quota.  This is NOT a W048 restoration:
WORK-048 (containment/sharing) stays accepted-not-restored — there is
no isolation primitive, no traffic-isolation authority and no buyer-
traffic enforcement here; the canonical authorization gate is the
contract lease + the consent attestation + the declared quota, and
the client stays a client (every authority object is injected and
reached through its public contract).

Determinism (LOCK-119): content-derived ids over canonical JSON;
injected RFC 3339 UTC instants only (no wall clock, no randomness,
no UUIDs, no network); sorted iteration; integer arithmetic only;
typed fail-closed errors with stable codes; secret-shaped material
is rejected at every construction boundary.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from protocol.canonicalization import canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

from contracts import ContractStore, RevokeLease
from evidence import AttestationEvidence, EvidenceStore

#: The namespaced id prefix (content-derived ids only).
CONVERGENCE_PREFIX = "m014"

#: The frozen accepted-authority citation vocabulary (the
#: convergence by reference — exactly the accepted child domains).
CONVERGENCE_AUTHORITIES: Tuple[str, ...] = (
    "contracts",
    "offers",
    "executionplans",
    "adapters",
    "replan",
    "commercial",
    "evidence",
    "assurance",
    "vertical-proof",
)

#: The frozen citation kinds per authority (fail-closed elsewhere).
CITATION_KINDS: Dict[str, Tuple[str, ...]] = {
    "contracts": ("connectivity-contract",),
    "offers": ("provider-offer",),
    "executionplans": ("execution-plan",),
    "adapters": ("adapter-capability",),
    "replan": ("replan-decision",),
    "commercial": ("settlement-reference",),
    "evidence": ("evidence-record",),
    "assurance": ("assurance-evaluation",),
    "vertical-proof": ("vertical-proof",),
}

#: The frozen vertical-proof integration patterns (LOCK-120).
VERTICAL_PROOF_KINDS: Tuple[str, ...] = ("sharenet", "roamlink", "comos")

#: The converged authorization-session state vocabulary (the frozen
#: W049 protocol's canonical states — the values the client projects;
#: terminals never resurrect).
SESSION_STATES: Tuple[str, ...] = (
    "prepared",
    "authorized",
    "active",
    "paused",
    "degraded",
    "revoked",
    "expired",
    "closed",
)

#: The explicit session transition table (fail-closed elsewhere).
SESSION_TRANSITIONS: Dict[str, frozenset] = {
    "prepared": frozenset({"authorized", "revoked", "expired", "closed"}),
    "authorized": frozenset({"active", "revoked", "expired", "closed"}),
    "active": frozenset({"paused", "degraded", "revoked", "expired", "closed"}),
    "paused": frozenset({"active", "revoked", "expired", "closed"}),
    "degraded": frozenset({"active", "revoked", "expired", "closed"}),
    "revoked": frozenset({"closed"}),
    "expired": frozenset({"closed"}),
    "closed": frozenset(),
}

#: The terminal session states (one-way; the M008 discipline).
SESSION_TERMINAL_STATES: Tuple[str, ...] = ("revoked", "expired", "closed")

#: The consent-attestation state vocabulary.
CONSENT_STATES: Tuple[str, ...] = ("pending", "granted", "withdrawn")

#: The consent states as typed evidence values (integer DATA only).
_CONSENT_ATTESTED = {"pending": 0, "granted": 1, "withdrawn": 2}

#: The rate-limited operation vocabulary (the production-hardening
#: surface; every mutating converged operation passes the gate).
RATE_LIMIT_OPERATIONS: Tuple[str, ...] = (
    "prepare",
    "authorize",
    "activate",
    "account",
)

#: Secret-shaped key/value patterns (LOCK-119; the frozen defensive
#: rejection grammar shared with the accepted domains).
_SECRET_KEY_PATTERN = tuple(sorted((
    "private_key", "secret_key", "password", "passwd",
    "client_secret", "credential_secret", "api_key",
)))


class ConvergenceReasonCode:
    """The frozen typed reason vocabulary (stable codes)."""

    INVALID_INPUT = "invalid-input"
    VOCABULARY = "vocabulary"
    TEMPORAL_INVALID = "temporal-invalid"
    SECRET_REJECTED = "secret-rejected"
    NOT_FOUND = "not-found"
    LIFECYCLE_ILLEGAL = "lifecycle-illegal"
    LEASE_NOT_ACTIVE = "lease-not-active"
    LEASE_EXPIRED = "lease-expired"
    CONSENT_REQUIRED = "consent-required"
    QUOTA_EXCEEDED = "quota-exceeded"
    RATE_LIMITED = "rate-limited"
    ID_MISMATCH = "id-mismatch"
    REVOCATION_INVALID = "revocation-invalid"
    EVIDENCE_REJECTED = "evidence-rejected"


class ConvergenceError(Exception):
    """The typed fail-closed error (stable code + bounded detail)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__("%s: %s" % (code, detail))
        self.code = str(code)
        self.detail = str(detail)

    @property
    def reason(self) -> str:
        """The duck-typed reason attribute the W049 client protocol
        reads (the canonical reason surfaces verbatim)."""
        return self.code


def _require_instant(value: object, label: str) -> str:
    """An explicit RFC 3339 UTC instant (injected, never a wall
    clock); typed rejection on malformed material."""
    if not isinstance(value, str) or not value:
        raise ConvergenceError(
            ConvergenceReasonCode.TEMPORAL_INVALID,
            "%s must be a non-empty RFC 3339 UTC instant string" % label,
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise ConvergenceError(
            ConvergenceReasonCode.TEMPORAL_INVALID,
            "%s must be an RFC 3339 UTC instant (%s)" % (label, error),
        ) from error
    return value


def _require_reference(value: object, label: str) -> str:
    """A non-empty reference string that is not secret-shaped."""
    if not isinstance(value, str) or not value:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % label,
        )
    lowered = value.lower()
    for marker in _SECRET_KEY_PATTERN:
        if marker in lowered:
            raise ConvergenceError(
                ConvergenceReasonCode.SECRET_REJECTED,
                "%s is secret-shaped material; secrets never enter "
                "convergence metadata (LOCK-119)" % label,
            )
    return value


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _citation_id_material(
    authority: str,
    subject_ref: str,
    ref_kind: str,
    payload_digest: str,
) -> bytes:
    return canonical_json_bytes({
        "authority": authority,
        "subject_ref": subject_ref,
        "ref_kind": ref_kind,
        "payload_digest": payload_digest,
    })


def derive_citation_id(
    authority: str,
    subject_ref: str,
    ref_kind: str,
    payload_digest: str,
) -> str:
    """The content-derived citation identity (tamper-evident)."""
    return "%s:cite:sha256:%s" % (
        CONVERGENCE_PREFIX,
        _sha256_hex(_citation_id_material(
            authority, subject_ref, ref_kind, payload_digest,
        )),
    )


# ---------------------------------------------------------------------------
# The typed child-authority citations (BY REFERENCE — the convergence)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChildCitation:
    """One typed citation of an accepted child authority's record.

    The citation is immutable DATA with provenance (LOCK-118): the
    authority label, the cited subject's own identity, the frozen
    citation kind, the citing issuer, the injected instant and the
    SHA-256 digest of the cited record's OWN canonical bytes (computed
    at construction from the real record — never caller-supplied).
    A citation asserts a reference; it never becomes a second
    authority for the cited material (LOCK-117).
    """

    citation_id: str
    authority: str
    subject_ref: str
    ref_kind: str
    issuer: str
    cited_at: str
    payload_digest: str

    def __post_init__(self) -> None:
        for label, value in (
            ("citation_id", self.citation_id),
            ("authority", self.authority),
            ("subject_ref", self.subject_ref),
            ("ref_kind", self.ref_kind),
            ("issuer", self.issuer),
            ("cited_at", self.cited_at),
            ("payload_digest", self.payload_digest),
        ):
            if not isinstance(value, str) or not value:
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "citation %s must be a non-empty string" % label,
                )
        if self.authority not in CONVERGENCE_AUTHORITIES:
            raise ConvergenceError(
                ConvergenceReasonCode.VOCABULARY,
                "citation authority %r is outside the frozen converged "
                "set %s" % (self.authority, sorted(CONVERGENCE_AUTHORITIES)),
            )
        if self.ref_kind not in CITATION_KINDS[self.authority]:
            raise ConvergenceError(
                ConvergenceReasonCode.VOCABULARY,
                "citation kind %r is not valid for authority %r"
                % (self.ref_kind, self.authority),
            )
        _require_reference(self.issuer, "citation issuer")
        _require_reference(self.subject_ref, "citation subject_ref")
        _require_instant(self.cited_at, "citation cited_at")
        expected = derive_citation_id(
            self.authority, self.subject_ref, self.ref_kind,
            self.payload_digest,
        )
        if self.citation_id != expected:
            raise ConvergenceError(
                ConvergenceReasonCode.ID_MISMATCH,
                "citation id %r does not digest its content (expected %r)"
                % (self.citation_id, expected),
            )

    def to_dict(self) -> Dict[str, str]:
        return {
            "citation_id": self.citation_id,
            "authority": self.authority,
            "subject_ref": self.subject_ref,
            "ref_kind": self.ref_kind,
            "issuer": self.issuer,
            "cited_at": self.cited_at,
            "payload_digest": self.payload_digest,
        }

    @classmethod
    def from_dict(cls, data: object) -> "ChildCitation":
        if not isinstance(data, dict):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "citation material must be a mapping",
            )
        return cls(
            citation_id=str(data.get("citation_id", "")),
            authority=str(data.get("authority", "")),
            subject_ref=str(data.get("subject_ref", "")),
            ref_kind=str(data.get("ref_kind", "")),
            issuer=str(data.get("issuer", "")),
            cited_at=str(data.get("cited_at", "")),
            payload_digest=str(data.get("payload_digest", "")),
        )


def _build_citation(
    *,
    authority: str,
    subject_ref: str,
    ref_kind: str,
    issuer: str,
    cited_at: str,
    canonical_payload: bytes,
) -> ChildCitation:
    """The single citation construction path (digest over the cited
    record's OWN canonical bytes)."""
    digest = _sha256_hex(canonical_payload)
    return ChildCitation(
        citation_id=derive_citation_id(
            authority, subject_ref, ref_kind, digest
        ),
        authority=authority,
        subject_ref=_require_reference(subject_ref, "citation subject_ref"),
        ref_kind=ref_kind,
        issuer=_require_reference(issuer, "citation issuer"),
        cited_at=_require_instant(cited_at, "citation cited_at"),
        payload_digest=digest,
    )


def cite_contract(contract: Any, *, issuer: str, cited_at: str) -> ChildCitation:
    """Cite a REAL M002 ``ConnectivityContract`` (the canonical
    citation — LOCK-101).  The digest is the contract's own canonical
    bytes; the subject is the contract's own id."""
    contract_id = getattr(contract, "contract_id", None)
    canonical = getattr(contract, "canonical_bytes", None)
    if not isinstance(contract_id, str) or not contract_id:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_contract requires a real ConnectivityContract "
            "(contract_id missing)",
        )
    if not callable(canonical):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_contract requires the contract's canonical_bytes surface",
        )
    return _build_citation(
        authority="contracts",
        subject_ref=contract_id,
        ref_kind="connectivity-contract",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical(),
    )


def cite_offer(offer: Any, *, issuer: str, cited_at: str) -> ChildCitation:
    """Cite a REAL M003 ``OfferRecord`` (the capability exchange —
    provider offers as typed DATA)."""
    provider = getattr(offer, "provider", None)
    key = getattr(offer, "provider_offer_key", None)
    canonical = getattr(offer, "canonical_bytes", None)
    if not isinstance(provider, str) or not isinstance(key, str):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_offer requires a real OfferRecord (provider/"
            "provider_offer_key missing)",
        )
    if not callable(canonical):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_offer requires the offer's canonical_bytes surface",
        )
    return _build_citation(
        authority="offers",
        subject_ref="%s/%s" % (provider, key),
        ref_kind="provider-offer",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical(),
    )


def cite_execution_plan(plan: Any, *, issuer: str, cited_at: str) -> ChildCitation:
    """Cite a REAL M006 ``ExecutionPlan`` (the mechanism surface —
    LOCK-109; the plan is DATA, never translated here)."""
    plan_id = getattr(plan, "plan_id", None)
    canonical = getattr(plan, "canonical_bytes", None)
    if not isinstance(plan_id, str) or not plan_id:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_execution_plan requires a real ExecutionPlan "
            "(plan_id missing)",
        )
    if not callable(canonical):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_execution_plan requires the plan's canonical_bytes "
            "surface",
        )
    return _build_citation(
        authority="executionplans",
        subject_ref=plan_id,
        ref_kind="execution-plan",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical(),
    )


def cite_adapter_capability(
    view: Any, *, issuer: str, cited_at: str
) -> ChildCitation:
    """Cite a REAL M007 adapter capability view (the capability-
    oriented boundary — LOCK-110; provider-neutral DATA)."""
    to_bytes = getattr(view, "to_canonical_bytes", None)
    if not callable(to_bytes):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_adapter_capability requires a real adapter capability "
            "view (to_canonical_bytes missing)",
        )
    payload = to_bytes()
    if not isinstance(payload, bytes):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "the adapter capability view did not produce canonical bytes",
        )
    adapter_id = getattr(view, "adapter_id", None)
    if not isinstance(adapter_id, str) or not adapter_id:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_adapter_capability requires the view's adapter_id",
        )
    return _build_citation(
        authority="adapters",
        subject_ref=adapter_id,
        ref_kind="adapter-capability",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=payload,
    )


def cite_replan_decision(
    decision: Any, *, issuer: str, cited_at: str
) -> ChildCitation:
    """Cite a REAL M008 ``ReplanDecision`` (the failover discipline —
    the decision is provenance DATA, never re-decided here)."""
    decision_id = getattr(decision, "decision_id", None)
    canonical = getattr(decision, "canonical_bytes", None)
    if not isinstance(decision_id, str) or not decision_id:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_replan_decision requires a real ReplanDecision "
            "(decision_id missing)",
        )
    if not callable(canonical):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_replan_decision requires the decision's canonical_bytes "
            "surface",
        )
    return _build_citation(
        authority="replan",
        subject_ref=decision_id,
        ref_kind="replan-decision",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical(),
    )


def cite_settlement_reference(
    *,
    subject_ref: str,
    canonical_payload: bytes,
    issuer: str,
    cited_at: str,
) -> ChildCitation:
    """Cite a M009 commercial-track settlement reference (LOCK-113:
    an opaque typed reference — the commercial semantics stay in the
    commercial track; only the reference crosses into federation
    metadata)."""
    if not isinstance(canonical_payload, bytes) or not canonical_payload:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_settlement_reference requires canonical reference bytes",
        )
    return _build_citation(
        authority="commercial",
        subject_ref=subject_ref,
        ref_kind="settlement-reference",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical_payload,
    )


def cite_evidence_record(
    record: Any, *, issuer: str, cited_at: str
) -> ChildCitation:
    """Cite a REAL M005 typed evidence record (the closed loop —
    LOCK-106/LOCK-118)."""
    record_id = getattr(record, "record_id", None)
    to_dict = getattr(record, "to_dict", None)
    if not isinstance(record_id, str) or not record_id:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_evidence_record requires a real typed evidence record "
            "(record_id missing)",
        )
    if not callable(to_dict):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_evidence_record requires the record's to_dict surface",
        )
    return _build_citation(
        authority="evidence",
        subject_ref=record_id,
        ref_kind="evidence-record",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical_json_bytes(to_dict()),
    )


def cite_assurance_evaluation(
    evaluation: Any, *, issuer: str, cited_at: str
) -> ChildCitation:
    """Cite a REAL M005 assurance evaluation (the closed-loop verdict
    — DATA with its own evaluation identity)."""
    evaluation_id = getattr(evaluation, "evaluation_id", None)
    canonical = getattr(evaluation, "canonical_bytes", None)
    if not isinstance(evaluation_id, str) or not evaluation_id:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_assurance_evaluation requires a real AssuranceEvaluation "
            "(evaluation_id missing)",
        )
    if not callable(canonical):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_assurance_evaluation requires the evaluation's "
            "canonical_bytes surface",
        )
    return _build_citation(
        authority="assurance",
        subject_ref=evaluation_id,
        ref_kind="assurance-evaluation",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical(),
    )


def cite_vertical_proof(
    *,
    proof_kind: str,
    subject_ref: str,
    issuer: str,
    cited_at: str,
    canonical_payload: bytes,
) -> ChildCitation:
    """Cite a vertical-proof integration pattern (LOCK-120: ShareNet/
    RoamLink/COMOS paths are compatibility proofs — DATA patterns,
    never owned semantics)."""
    if proof_kind not in VERTICAL_PROOF_KINDS:
        raise ConvergenceError(
            ConvergenceReasonCode.VOCABULARY,
            "vertical proof kind %r is outside the frozen set %s"
            % (proof_kind, sorted(VERTICAL_PROOF_KINDS)),
        )
    if not isinstance(canonical_payload, bytes) or not canonical_payload:
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "cite_vertical_proof requires canonical pattern bytes",
        )
    return _build_citation(
        authority="vertical-proof",
        subject_ref="%s/%s" % (proof_kind, subject_ref),
        ref_kind="vertical-proof",
        issuer=issuer,
        cited_at=cited_at,
        canonical_payload=canonical_payload,
    )


# ---------------------------------------------------------------------------
# The peer evidence lift (the closed-loop convergence seam)
# ---------------------------------------------------------------------------


def peer_evidence_from_citation(
    citation: ChildCitation,
    *,
    producer: str,
    valid_until: str,
) -> AttestationEvidence:
    """The ONE sanctioned lift of a peer-domain citation into the M005
    typed evidence space (the ``peer_claim_from_exchange``
    discipline): always an ATTESTATION-type record carrying the frozen
    ``remotely-attested`` kind (a peer's assertion about its cited
    authority is a REMOTE assertion), provenance preserved, the
    citation's own identity as the source reference — never local
    truth.  ``valid_until`` is an injected validity instant strictly
    after the citation instant."""
    if not isinstance(citation, ChildCitation):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "peer_evidence_from_citation requires a ChildCitation",
        )
    _require_reference(producer, "peer evidence producer")
    _require_instant(valid_until, "peer evidence valid_until")
    try:
        return AttestationEvidence(
            subject_ref=citation.subject_ref,
            contract_ref="m014-convergence:%s" % citation.authority,
            instant=citation.cited_at,
            producer=producer,
            attestation_kind="remotely-attested",
            attested_value=1,
            valid_until=valid_until,
            source_refs=(citation.citation_id,),
        )
    except Exception as error:  # consumed-domain isolation
        raise ConvergenceError(
            ConvergenceReasonCode.EVIDENCE_REJECTED,
            "the peer evidence lift was rejected by the evidence domain "
            "(%s: %s)"
            % (getattr(error, "reason", "evidence-error"), error),
        ) from error


# ---------------------------------------------------------------------------
# The rate-limit surface (LOCK-117 production hardening)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateLimitPolicy:
    """The deterministic fixed-window admission policy.

    ``limit`` operations per ``window_seconds`` per subject; the
    window origin is derived from the INJECTED instant (never a wall
    clock); integer arithmetic only.
    """

    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if not isinstance(self.limit, int) or isinstance(self.limit, bool):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "rate limit must be an int",
            )
        if self.limit < 1:
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "rate limit must be >= 1 (a zero-capacity policy would "
                "deny everything — configure it explicitly, never by "
                "accident)",
            )
        if not isinstance(self.window_seconds, int) or isinstance(
            self.window_seconds, bool
        ):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "rate window seconds must be an int",
            )
        if self.window_seconds < 1:
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "rate window seconds must be >= 1",
            )


@dataclass
class RateLimitState:
    """The deterministic per-subject window counters (mutable state,
    injected instants only; sorted-subject iteration)."""

    _windows: Dict[str, Tuple[int, int]] = field(default_factory=dict)

    def window(self, subject: str) -> Optional[Tuple[int, int]]:
        return self._windows.get(subject)

    def subjects(self) -> Tuple[str, ...]:
        return tuple(sorted(self._windows))

    def to_dict(self) -> Dict[str, Dict[str, int]]:
        return {
            subject: {"window_origin": origin, "count": count}
            for subject, (origin, count) in sorted(self._windows.items())
        }

    @classmethod
    def from_dict(cls, data: object) -> "RateLimitState":
        if not isinstance(data, dict):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "rate limit state material must be a mapping",
            )
        state = cls()
        for subject, window in data.items():
            if not isinstance(window, dict):
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "rate limit window material must be a mapping",
                )
            origin = window.get("window_origin")
            count = window.get("count")
            if not isinstance(origin, int) or not isinstance(count, int):
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "rate limit window members must be ints",
                )
            state._windows[str(subject)] = (origin, count)
        return state


@dataclass(frozen=True)
class RateLimitVerdict:
    """One deterministic admission verdict (typed, fail-closed)."""

    allowed: bool
    subject: str
    window_origin: int
    count: int
    reason: str = ""


def _epoch_seconds(instant: str) -> int:
    """The deterministic epoch second of an RFC 3339 UTC instant
    (integer arithmetic only; validated upstream)."""
    parsed = parse_instant(instant)
    return int(parsed.timestamp())


def check_rate_limit(
    policy: RateLimitPolicy,
    state: RateLimitState,
    subject: str,
    instant: str,
) -> RateLimitVerdict:
    """Advance the fixed window for ``subject`` at ``instant`` and
    return the typed verdict.

    The check CONSUMES one admission slot when allowed (the counter
    advances deterministically; identical replay inputs in the same
    window are themselves subject to the limit — idempotency of the
    CALLER's request ledger is the caller's discipline, mirroring the
    accepted usage-ledger seam).  Fail-closed: exceeded windows deny
    with ``rate-limited``; malformed instants reject typed.
    """
    if not isinstance(policy, RateLimitPolicy):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "check_rate_limit requires a RateLimitPolicy",
        )
    if not isinstance(state, RateLimitState):
        raise ConvergenceError(
            ConvergenceReasonCode.INVALID_INPUT,
            "check_rate_limit requires a RateLimitState",
        )
    _require_reference(subject, "rate limit subject")
    _require_instant(instant, "rate limit instant")
    now_seconds = _epoch_seconds(instant)
    window_origin = now_seconds - (now_seconds % policy.window_seconds)
    current = state._windows.get(subject)
    if current is None or current[0] != window_origin:
        count = 0
    else:
        count = current[1]
    if count >= policy.limit:
        return RateLimitVerdict(
            allowed=False,
            subject=subject,
            window_origin=window_origin,
            count=count,
            reason=ConvergenceReasonCode.RATE_LIMITED,
        )
    state._windows[subject] = (window_origin, count + 1)
    return RateLimitVerdict(
        allowed=True,
        subject=subject,
        window_origin=window_origin,
        count=count + 1,
        reason="",
    )


# ---------------------------------------------------------------------------
# The citation revocation discipline (LOCK-117 production hardening)
# ---------------------------------------------------------------------------


def _revocation_id_material(
    citation_id: str,
    reason: str,
    revoked_at: str,
    propagated_to: Tuple[str, ...],
    confirmed_by: Tuple[str, ...],
    state: str,
) -> bytes:
    return canonical_json_bytes({
        "citation_id": citation_id,
        "reason": reason,
        "revoked_at": revoked_at,
        "propagated_to": list(propagated_to),
        "confirmed_by": list(confirmed_by),
        "state": state,
    })


@dataclass(frozen=True)
class CitationRevocation:
    """One explicit citation revocation with the deterministic
    ``pending -> propagated -> confirmed`` propagation discipline
    (idempotent, append-only, history-preserving)."""

    revocation_id: str
    citation_id: str
    reason: str
    revoked_at: str
    propagated_to: Tuple[str, ...]
    confirmed_by: Tuple[str, ...]
    state: str

    def __post_init__(self) -> None:
        for label, value in (
            ("revocation_id", self.revocation_id),
            ("citation_id", self.citation_id),
            ("reason", self.reason),
            ("revoked_at", self.revoked_at),
            ("state", self.state),
        ):
            if not isinstance(value, str) or not value:
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "revocation %s must be a non-empty string" % label,
                )
        if self.state not in ("pending", "propagated", "confirmed"):
            raise ConvergenceError(
                ConvergenceReasonCode.VOCABULARY,
                "revocation state %r is outside the frozen propagation "
                "vocabulary" % self.state,
            )
        for label, values in (
            ("propagated_to", self.propagated_to),
            ("confirmed_by", self.confirmed_by),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item for item in values
            ):
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "revocation %s must be a tuple of non-empty strings"
                    % label,
                )
        _require_reference(self.reason, "revocation reason")
        _require_instant(self.revoked_at, "revocation revoked_at")
        expected = "%s:revoke:sha256:%s" % (
            CONVERGENCE_PREFIX,
            _sha256_hex(_revocation_id_material(
                self.citation_id, self.reason, self.revoked_at,
                self.propagated_to, self.confirmed_by, self.state,
            )),
        )
        if self.revocation_id != expected:
            raise ConvergenceError(
                ConvergenceReasonCode.ID_MISMATCH,
                "revocation id %r does not digest its content" % (
                    self.revocation_id,
                ),
            )

    def to_dict(self) -> Dict[str, object]:
        return {
            "revocation_id": self.revocation_id,
            "citation_id": self.citation_id,
            "reason": self.reason,
            "revoked_at": self.revoked_at,
            "propagated_to": list(self.propagated_to),
            "confirmed_by": list(self.confirmed_by),
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: object) -> "CitationRevocation":
        if not isinstance(data, dict):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "revocation material must be a mapping",
            )
        return cls(
            revocation_id=str(data.get("revocation_id", "")),
            citation_id=str(data.get("citation_id", "")),
            reason=str(data.get("reason", "")),
            revoked_at=str(data.get("revoked_at", "")),
            propagated_to=tuple(
                str(item) for item in data.get("propagated_to", ())
            ),
            confirmed_by=tuple(
                str(item) for item in data.get("confirmed_by", ())
            ),
            state=str(data.get("state", "")),
        )


def citation_revocation(
    *,
    citation_id: str,
    reason: str,
    revoked_at: str,
    propagated_to: Sequence[str] = (),
    confirmed_by: Sequence[str] = (),
    state: str = "pending",
) -> CitationRevocation:
    """Construct one citation revocation record (content-derived id)."""
    revocation_id = "%s:revoke:sha256:%s" % (
        CONVERGENCE_PREFIX,
        _sha256_hex(_revocation_id_material(
            citation_id, reason, revoked_at,
            tuple(propagated_to), tuple(confirmed_by), state,
        )),
    )
    return CitationRevocation(
        revocation_id=revocation_id,
        citation_id=citation_id,
        reason=reason,
        revoked_at=revoked_at,
        propagated_to=tuple(propagated_to),
        confirmed_by=tuple(confirmed_by),
        state=state,
    )


# ---------------------------------------------------------------------------
# The per-domain citation ledger
# ---------------------------------------------------------------------------


class DomainCitationLedger:
    """The append-only, idempotent per-domain citation ledger.

    Deterministic (sorted iteration, content digests), fail-closed
    (typed vocabulary + tamper-evident ids), history-preserving
    (revocation never deletes; the revoked citation stays visible with
    its typed revocation record).
    """

    def __init__(self) -> None:
        self._citations: Dict[str, ChildCitation] = {}
        self._revocations: Dict[str, CitationRevocation] = {}

    # -- construction ------------------------------------------------------

    def append(self, citation: ChildCitation) -> ChildCitation:
        """Idempotent append: the identical citation replays as a
        no-op returning the stored record; a DIFFERENT citation with
        the same id fails closed (id collision — tamper evidence)."""
        if not isinstance(citation, ChildCitation):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "append requires a ChildCitation",
            )
        existing = self._citations.get(citation.citation_id)
        if existing is not None:
            if existing.to_dict() != citation.to_dict():
                raise ConvergenceError(
                    ConvergenceReasonCode.ID_MISMATCH,
                    "citation id %r already exists with different content"
                    % citation.citation_id,
                )
            return existing
        if citation.citation_id in self._revocations:
            raise ConvergenceError(
                ConvergenceReasonCode.REVOCATION_INVALID,
                "citation %r is revoked; revoked citations are never "
                "re-appended (history is append-only)" % citation.citation_id,
            )
        self._citations[citation.citation_id] = citation
        return citation

    def revoke(self, revocation: CitationRevocation) -> CitationRevocation:
        """Idempotent revocation append (the explicit propagation
        discipline).  The citation must exist; the propagation state
        advances only forward (pending -> propagated -> confirmed);
        a confirmed revocation never moves."""
        if not isinstance(revocation, CitationRevocation):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "revoke requires a CitationRevocation",
            )
        if revocation.citation_id not in self._citations:
            raise ConvergenceError(
                ConvergenceReasonCode.NOT_FOUND,
                "revocation cites unknown citation %r"
                % revocation.citation_id,
            )
        existing = self._revocations.get(revocation.citation_id)
        if existing is not None:
            if existing.to_dict() == revocation.to_dict():
                return existing  # exact idempotent replay
            order = {"pending": 0, "propagated": 1, "confirmed": 2}
            if order[revocation.state] <= order[existing.state]:
                raise ConvergenceError(
                    ConvergenceReasonCode.REVOCATION_INVALID,
                    "revocation for %r may only advance (%s -> %s is not "
                    "forward)" % (
                        revocation.citation_id, existing.state,
                        revocation.state,
                    ),
                )
        self._revocations[revocation.citation_id] = revocation
        return revocation

    # -- reads ---------------------------------------------------------------

    def citations(self) -> Tuple[ChildCitation, ...]:
        return tuple(
            self._citations[key] for key in sorted(self._citations)
        )

    def citation(self, citation_id: str) -> ChildCitation:
        citation = self._citations.get(citation_id)
        if citation is None:
            raise ConvergenceError(
                ConvergenceReasonCode.NOT_FOUND,
                "unknown citation %r" % citation_id,
            )
        return citation

    def is_revoked(self, citation_id: str) -> bool:
        return citation_id in self._revocations

    def revocation(self, citation_id: str) -> CitationRevocation:
        record = self._revocations.get(citation_id)
        if record is None:
            raise ConvergenceError(
                ConvergenceReasonCode.NOT_FOUND,
                "citation %r is not revoked" % citation_id,
            )
        return record

    def revocations(self) -> Tuple[CitationRevocation, ...]:
        return tuple(
            self._revocations[key] for key in sorted(self._revocations)
        )

    def digest(self) -> str:
        """The canonical ledger digest (citations + revocations,
        sorted; byte-stable across runs and hash seeds)."""
        return _sha256_hex(canonical_json_bytes({
            "citations": [
                citation.to_dict() for citation in self.citations()
            ],
            "revocations": [
                revocation.to_dict() for revocation in self.revocations()
            ],
        }))

    def to_dict(self) -> Dict[str, object]:
        return {
            "citations": [
                citation.to_dict() for citation in self.citations()
            ],
            "revocations": [
                revocation.to_dict() for revocation in self.revocations()
            ],
        }

    @classmethod
    def from_dict(cls, data: object) -> "DomainCitationLedger":
        if not isinstance(data, dict):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "ledger material must be a mapping",
            )
        ledger = cls()
        for item in data.get("citations", ()):
            ledger.append(ChildCitation.from_dict(item))
        for item in data.get("revocations", ()):
            ledger.revoke(CitationRevocation.from_dict(item))
        return ledger


# ---------------------------------------------------------------------------
# The declared authorization scope (the production quota envelope)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthorizationScope:
    """The provider's DECLARED authorization envelope (DATA — the
    frozen W049 presentation dimensions carried over the converged
    boundary): bounded egress labels, an integer byte quota, an
    explicit expiry instant, bounded concurrent sessions and declared
    local services.  This is an AUTHORIZATION quota (the right to
    admit traffic at all) — billable usage stays the M009 usage
    authority's business, cited by reference."""

    exposed_egress: Tuple[str, ...]
    byte_quota: int
    valid_until: str
    max_concurrent_sessions: int
    exposed_local_services: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for label, values in (
            ("exposed_egress", self.exposed_egress),
            ("exposed_local_services", self.exposed_local_services),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(item, str) or not item for item in values
            ):
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "scope %s must be a tuple of non-empty strings" % label,
                )
        for label, value in (
            ("byte_quota", self.byte_quota),
            ("max_concurrent_sessions", self.max_concurrent_sessions),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "scope %s must be an int" % label,
                )
            if value < 0:
                raise ConvergenceError(
                    ConvergenceReasonCode.INVALID_INPUT,
                    "scope %s must be >= 0" % label,
                )
        _require_instant(self.valid_until, "scope valid_until")

    def to_dict(self) -> Dict[str, object]:
        return {
            "exposed_egress": list(self.exposed_egress),
            "byte_quota": self.byte_quota,
            "valid_until": self.valid_until,
            "max_concurrent_sessions": self.max_concurrent_sessions,
            "exposed_local_services": list(self.exposed_local_services),
        }

    @classmethod
    def from_dict(cls, data: object) -> "AuthorizationScope":
        if not isinstance(data, dict):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "scope material must be a mapping",
            )
        return cls(
            exposed_egress=tuple(
                str(item) for item in data.get("exposed_egress", ())
            ),
            byte_quota=int(data.get("byte_quota", 0)),
            valid_until=str(data.get("valid_until", "")),
            max_concurrent_sessions=int(
                data.get("max_concurrent_sessions", 0)
            ),
            exposed_local_services=tuple(
                str(item) for item in data.get("exposed_local_services", ())
            ),
        )


# ---------------------------------------------------------------------------
# The converged authorization runtime (the DEC-0099 re-baseline
# authority — the frozen W049 client protocol over the 1.1 surfaces)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AuthorizationSession:
    """The internal authorization-session record (content-derived
    identity; the external view is :class:`AuthorizationSessionView`)."""

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
    scope_valid_until: str
    scope_byte_quota: int


@dataclass(frozen=True)
class AuthorizationSessionView:
    """The read view the frozen W049 client protocol consumes
    (duck-typed attributes: ``sharing_session_id``/``state``/
    ``buyer_ref``/``provider_ref``/``session_ref``/``consent_ref``/
    ``path_ref``/``termination_reason``)."""

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

    @property
    def sharing_session_id(self) -> str:
        """The W049 protocol's session identity attribute."""
        return self.session_id


@dataclass(frozen=True)
class AuthorizationConsentView:
    """The consent read view (duck-typed: ``state``/``provider_ref``/
    ``buyer_ref`` — the frozen protocol's consent record)."""

    consent_ref: str
    session_id: str
    provider_ref: str
    buyer_ref: str
    state: str


def _session_id_material(record: _AuthorizationSession) -> bytes:
    return canonical_json_bytes({
        "contract_id": record.contract_id,
        "lease_id": record.lease_id,
        "buyer_ref": record.buyer_ref,
        "provider_ref": record.provider_ref,
        "session_ref": record.session_ref,
        "consent_ref": record.consent_ref,
        "path_ref": record.path_ref,
        "platform_id": record.platform_id,
        "prepared_at": record.prepared_at,
    })


class ConvergedAuthorizationRuntime:
    """The provider-mode canonical authorization authority over the
    converged 1.1 surfaces — the DEC-0099 client re-baseline surface.

    Implements the frozen W049 client's duck-typed protocol verbatim
    (the method names and record attributes the unchanged client code
    drives) with the canonical truth owned by:

    - a REAL ``contracts.ContractStore`` — the lease gate: prepare
      requires the contract in an authorization-capable state with a
      currently-valid granted/active lease; expiry flows through the
      store's OWN ``expire_leases_if_due``; the emergency stop and
      the authority-side revocation drive the store's OWN
      ``RevokeLease`` command (LOCK-101/LOCK-117: the contract stays
      the sole authority);
    - a REAL ``evidence.EvidenceStore`` — the consent record as TYPED
      attestation evidence (pending -> granted -> withdrawn; every
      transition appends a new immutable ``controller-verified``
      record — LOCK-106/LOCK-118);
    - the rate-limit surface — every mutating operation passes the
      injected policy (production hardening);
    - the declared :class:`AuthorizationScope` — the authorization
      quota enforced at the traffic-admission point.

    NOT a W048 restoration: no isolation primitive, no traffic-
    isolation authority, no buyer-traffic enforcement — WORK-048
    stays accepted-not-restored.  The converged admission gate is the
    canonical lease + the consent attestation + the declared quota.
    """

    def __init__(
        self,
        *,
        store: ContractStore,
        evidence: EvidenceStore,
        clock: Any,
        rate_policy: Optional[RateLimitPolicy] = None,
    ) -> None:
        if not isinstance(store, ContractStore):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "the converged authorization runtime requires a REAL "
                "contracts.ContractStore (LOCK-101)",
            )
        if not isinstance(evidence, EvidenceStore):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "the converged authorization runtime requires a REAL "
                "evidence.EvidenceStore (LOCK-106)",
            )
        if clock is None or not callable(getattr(clock, "now", None)):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "the converged authorization runtime requires an injected "
                "clock seam (deterministic batteries always wire one)",
            )
        self._store = store
        self._evidence = evidence
        self._clock = clock
        self._rate_policy = rate_policy
        self._rate_state = RateLimitState()
        self._sessions: Dict[str, _AuthorizationSession] = {}
        self._consent_states: Dict[str, str] = {}

    # -- the clock seam ------------------------------------------------------

    def _now(self) -> str:
        instant = str(self._clock.now())
        _require_instant(instant, "clock seam instant")
        return instant

    def _rate_gate(self, operation: str, subject: str) -> None:
        if self._rate_policy is None:
            return
        if operation not in RATE_LIMIT_OPERATIONS:
            raise ConvergenceError(
                ConvergenceReasonCode.VOCABULARY,
                "rate gate operation %r is outside the frozen set" % (
                    operation,
                ),
            )
        verdict = check_rate_limit(
            self._rate_policy, self._rate_state,
            "%s:%s" % (operation, subject), self._now(),
        )
        if not verdict.allowed:
            raise ConvergenceError(
                ConvergenceReasonCode.RATE_LIMITED,
                "operation %r for %r exceeded the injected rate policy "
                "(%d admissions in window %d)" % (
                    operation, subject, verdict.count, verdict.window_origin,
                ),
            )

    # -- the canonical lease gate --------------------------------------------

    def _lease_for(self, contract_id: str) -> Tuple[str, Any]:
        lease_ids = self._store.leases_for_contract(contract_id)
        if not lease_ids:
            raise ConvergenceError(
                ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                "contract %r carries no lease (no canonical right-to-use; "
                "fail closed)" % contract_id,
            )
        # the deterministic first lease (sorted ids; the canonical
        # lease identity is content-derived)
        lease_id = sorted(lease_ids)[0]
        return lease_id, self._store.lease(lease_id)

    def _require_valid_lease(self, contract_id: str) -> Tuple[str, Any]:
        lease_id, lease = self._lease_for(contract_id)
        if str(lease.state) not in ("granted", "active", "renewed"):
            raise ConvergenceError(
                ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                "the canonical lease %r is %r (a terminal/absent lease "
                "never authorizes; fail closed)" % (lease_id, lease.state),
            )
        now = self._now()
        if now > str(lease.not_after):
            raise ConvergenceError(
                ConvergenceReasonCode.LEASE_EXPIRED,
                "the canonical lease %r expired at %r (observed at %r)"
                % (lease_id, lease.not_after, now),
            )
        if now < str(lease.not_before):
            raise ConvergenceError(
                ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                "the canonical lease %r is not yet valid (window opens %r; "
                "observed at %r)" % (lease_id, lease.not_before, now),
            )
        return lease_id, lease

    def _expire_due_leases(self, contract_id: str) -> None:
        """Observe lease expiry through the store's OWN surface (never
        a local timer)."""
        try:
            self._store.expire_leases_if_due(contract_id, self._now())
        except Exception as error:  # consumed-domain isolation
            raise ConvergenceError(
                ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                "the canonical lease expiry observation failed (%s: %s)"
                % (getattr(error, "reason", "contract-error"), error),
            ) from error

    # -- the consent attestation discipline ------------------------------------

    def _append_consent_attestation(
        self,
        session: _AuthorizationSession,
        consent_state: str,
    ) -> None:
        """Append the typed consent-state attestation (an immutable
        ``controller-verified`` record; the consumed evidence domain's
        typed rejections surface as this surface's own typed error)."""
        instant = self._now()
        if not str(session.scope_valid_until) > instant:
            raise ConvergenceError(
                ConvergenceReasonCode.QUOTA_EXCEEDED,
                "the declared authorization scope expired at %r (observed "
                "at %r); the consent attestation window is closed"
                % (session.scope_valid_until, instant),
            )
        try:
            record = AttestationEvidence(
                subject_ref=session.consent_ref,
                contract_ref=session.contract_id,
                instant=instant,
                producer="m014-convergence:%s" % session.provider_ref,
                attestation_kind="controller-verified",
                attested_value=_CONSENT_ATTESTED[consent_state],
                valid_until=session.scope_valid_until,
                source_refs=(session.session_id,),
            )
            self._evidence.ingest(record)
        except ConvergenceError:
            raise
        except Exception as error:  # consumed-domain isolation
            raise ConvergenceError(
                ConvergenceReasonCode.EVIDENCE_REJECTED,
                "the consent attestation was rejected by the evidence "
                "domain (%s: %s)"
                % (getattr(error, "reason", "evidence-error"), error),
            ) from error

    def _consent_state(self, session: _AuthorizationSession) -> str:
        return self._consent_states.get(session.consent_ref, "pending")

    # -- the frozen W049 protocol ----------------------------------------------

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
    ) -> AuthorizationSessionView:
        """The canonical prepare: the lease gate + the rate gate + the
        consent-attestation opening.  ``lease_ref`` cites the CANONICAL
        CONTRACT id (the M002 authority); ``scope`` is the provider's
        declared :class:`AuthorizationScope` (DATA — the frozen W049
        presentation dimensions)."""
        contract_ref = _require_reference(lease_ref, "prepare lease_ref")
        for label, value in (
            ("buyer_ref", buyer_ref),
            ("provider_ref", provider_ref),
            ("session_ref", session_ref),
            ("path_ref", path_ref),
            ("platform_id", platform_id),
        ):
            _require_reference(value, "prepare %s" % label)
        if not isinstance(scope, AuthorizationScope):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "prepare requires the declared AuthorizationScope (the "
                "frozen W049 presentation dimensions as DATA)",
            )
        self._rate_gate("prepare", provider_ref)
        self._expire_due_leases(contract_ref)
        contract = self._store.contract(contract_ref)
        if str(contract.state) not in (
            "CONTRACT_ACTIVE", "EXECUTION_ACTIVE", "DELIVERY",
            "ASSURED", "DEGRADED",
        ):
            raise ConvergenceError(
                ConvergenceReasonCode.LEASE_NOT_ACTIVE,
                "the canonical contract %r is %r (not authorization-"
                "capable; fail closed)" % (contract_ref, contract.state),
            )
        lease_id, _lease = self._require_valid_lease(contract_ref)
        prepared_at = self._now()
        if not scope.valid_until > prepared_at:
            raise ConvergenceError(
                ConvergenceReasonCode.QUOTA_EXCEEDED,
                "the declared authorization scope expired at %r (observed "
                "at %r)" % (scope.valid_until, prepared_at),
            )
        consent_ref = "%s:consent:sha256:%s" % (
            CONVERGENCE_PREFIX,
            _sha256_hex(canonical_json_bytes({
                "contract_id": contract_ref,
                "session_ref": session_ref,
                "buyer_ref": buyer_ref,
                "provider_ref": provider_ref,
                "prepared_at": prepared_at,
            })),
        )
        record = _AuthorizationSession(
            session_id="pending",
            contract_id=contract_ref,
            lease_id=lease_id,
            buyer_ref=buyer_ref,
            provider_ref=provider_ref,
            session_ref=session_ref,
            consent_ref=consent_ref,
            path_ref=path_ref,
            platform_id=platform_id,
            state="prepared",
            termination_reason="",
            bytes_admitted=0,
            prepared_at=prepared_at,
            scope_valid_until=scope.valid_until,
            scope_byte_quota=scope.byte_quota,
        )
        session_id = "%s:authz:sha256:%s" % (
            CONVERGENCE_PREFIX,
            _sha256_hex(_session_id_material(record)),
        )
        record = _AuthorizationSession(
            session_id=session_id,
            contract_id=record.contract_id,
            lease_id=record.lease_id,
            buyer_ref=record.buyer_ref,
            provider_ref=record.provider_ref,
            session_ref=record.session_ref,
            consent_ref=record.consent_ref,
            path_ref=record.path_ref,
            platform_id=record.platform_id,
            state="prepared",
            termination_reason="",
            bytes_admitted=0,
            prepared_at=record.prepared_at,
            scope_valid_until=record.scope_valid_until,
            scope_byte_quota=record.scope_byte_quota,
        )
        self._sessions[session_id] = record
        self._consent_states[consent_ref] = "pending"
        self._append_consent_attestation(record, "pending")
        return self._view(record)

    def session(self, session_id: str) -> AuthorizationSessionView:
        """The canonical session read (expiry observed first — the
        store's own surface)."""
        record = self._require_session(session_id)
        self._expire_due_leases(record.contract_id)
        updated = self._apply_lease_observation(record)
        return self._view(updated)

    def consent(self, consent_ref: str) -> AuthorizationConsentView:
        """The canonical consent read."""
        _require_reference(consent_ref, "consent_ref")
        for key in sorted(self._sessions):
            record = self._sessions[key]
            if record.consent_ref == consent_ref:
                state = self._consent_state(record)
                return AuthorizationConsentView(
                    consent_ref=consent_ref,
                    session_id=record.session_id,
                    provider_ref=record.provider_ref,
                    buyer_ref=record.buyer_ref,
                    state=state,
                )
        raise ConvergenceError(
            ConvergenceReasonCode.NOT_FOUND,
            "unknown consent record %r" % consent_ref,
        )

    def grant_consent(self, session_id: str) -> AuthorizationConsentView:
        """Grant the consent THROUGH the canonical attestation record
        (pending -> granted; a typed immutable append)."""
        record = self._require_session(session_id)
        state = self._consent_state(record)
        if state != "pending":
            raise ConvergenceError(
                ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                "the canonical consent for %r is %r (only a pending "
                "consent can be granted)" % (session_id, state),
            )
        self._consent_states[record.consent_ref] = "granted"
        self._append_consent_attestation(record, "granted")
        return AuthorizationConsentView(
            consent_ref=record.consent_ref,
            session_id=record.session_id,
            provider_ref=record.provider_ref,
            buyer_ref=record.buyer_ref,
            state="granted",
        )

    def withdraw_consent(
        self, session_id: str
    ) -> AuthorizationSessionView:
        """Withdraw the consent (granted -> withdrawn) and REVOKE the
        session (the canonical authorization terminates; history
        preserved)."""
        record = self._require_session(session_id)
        state = self._consent_state(record)
        if state != "granted":
            raise ConvergenceError(
                ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                "the canonical consent for %r is %r (only a granted "
                "consent can be withdrawn)" % (session_id, state),
            )
        self._consent_states[record.consent_ref] = "withdrawn"
        self._append_consent_attestation(record, "withdrawn")
        updated = self._transition(record, "revoked", "consent-withdrawn")
        return self._view(updated)

    def authorize_sharing_session(
        self, session_id: str
    ) -> AuthorizationSessionView:
        """The canonical authorization: consent granted + the lease
        valid -> ``authorized``."""
        record = self._require_session(session_id)
        self._rate_gate("authorize", record.provider_ref)
        self._require_consent_granted(record)
        self._expire_due_leases(record.contract_id)
        self._require_valid_lease(record.contract_id)
        updated = self._transition(record, "authorized", "")
        return self._view(updated)

    def activate_sharing_session(
        self, session_id: str
    ) -> AuthorizationSessionView:
        """The canonical activation: authorized + the lease valid ->
        ``active`` (the W049 protocol's traffic-admission state)."""
        record = self._require_session(session_id)
        self._rate_gate("activate", record.provider_ref)
        self._require_consent_granted(record)
        self._expire_due_leases(record.contract_id)
        self._require_valid_lease(record.contract_id)
        updated = self._transition(record, "active", "")
        return self._view(updated)

    def pause_sharing_session(
        self, session_id: str
    ) -> AuthorizationSessionView:
        record = self._require_session(session_id)
        updated = self._transition(record, "paused", "")
        return self._view(updated)

    def resume_sharing_session(
        self, session_id: str
    ) -> AuthorizationSessionView:
        record = self._require_session(session_id)
        self._require_consent_granted(record)
        self._expire_due_leases(record.contract_id)
        self._require_valid_lease(record.contract_id)
        updated = self._transition(record, "active", "")
        return self._view(updated)

    def notify_path_lost(
        self, session_id: str, *, candidate_path_id: Optional[str] = None
    ) -> AuthorizationSessionView:
        """The path-loss observation: the session enters the explicit
        ``degraded`` state (never silently active)."""
        record = self._require_session(session_id)
        updated = self._transition(record, "degraded", "path-lost")
        return self._view(updated)

    def account_traffic(
        self, session_id: str, byte_count: int
    ) -> AuthorizationSessionView:
        """The traffic-admission point: the canonical lease + the
        granted consent + the declared scope quota + the rate policy
        gate every admission (NO W048 isolation — the authorization
        quota only; billable usage stays the M009 authority)."""
        record = self._require_session(session_id)
        if not isinstance(byte_count, int) or isinstance(byte_count, bool):
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "account_traffic byte_count must be an int",
            )
        if byte_count < 0:
            raise ConvergenceError(
                ConvergenceReasonCode.INVALID_INPUT,
                "account_traffic byte_count must be >= 0",
            )
        self._rate_gate("account", session_id)
        self._require_consent_granted(record)
        self._expire_due_leases(record.contract_id)
        self._require_valid_lease(record.contract_id)
        if record.state != "active":
            raise ConvergenceError(
                ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                "the canonical authorization session %r is %r (only an "
                "active session admits traffic; fail closed)" % (
                    session_id, record.state,
                ),
            )
        # the declared scope quota (the authorization envelope)
        if record.bytes_admitted + byte_count > record.scope_byte_quota:
            raise ConvergenceError(
                ConvergenceReasonCode.QUOTA_EXCEEDED,
                "the declared authorization quota %d would be exceeded "
                "(%d admitted + %d requested)" % (
                    record.scope_byte_quota, record.bytes_admitted,
                    byte_count,
                ),
            )
        updated = _AuthorizationSession(
            session_id=record.session_id,
            contract_id=record.contract_id,
            lease_id=record.lease_id,
            buyer_ref=record.buyer_ref,
            provider_ref=record.provider_ref,
            session_ref=record.session_ref,
            consent_ref=record.consent_ref,
            path_ref=record.path_ref,
            platform_id=record.platform_id,
            state=record.state,
            termination_reason=record.termination_reason,
            bytes_admitted=record.bytes_admitted + byte_count,
            prepared_at=record.prepared_at,
            scope_valid_until=record.scope_valid_until,
            scope_byte_quota=record.scope_byte_quota,
        )
        self._sessions[session_id] = updated
        return self._view(updated)

    def emergency_stop(self, session_id: str) -> AuthorizationSessionView:
        """The frozen emergency-stop sequence: the canonical lease is
        REVOKED through the contract store's OWN ``RevokeLease``
        command (the canonical termination — LOCK-101), then the
        session enters the terminal ``revoked`` state with the
        emergency-stop reason (never a boolean flip)."""
        record = self._require_session(session_id)
        self._revoke_lease(record, "m014-emergency-stop")
        if self._consent_state(record) == "granted":
            self._consent_states[record.consent_ref] = "withdrawn"
            self._append_consent_attestation(record, "withdrawn")
        updated = self._transition(record, "revoked", "emergency-stop")
        return self._view(updated)

    def revoke_authorization(
        self, session_id: str, reason: str
    ) -> AuthorizationSessionView:
        """The AUTHORITY-side revocation driver (outside the client):
        the canonical lease is revoked through the contract store's
        own command and the session terminates — the client only
        OBSERVES the terminal truth through the read window."""
        record = self._require_session(session_id)
        _require_reference(reason, "revocation reason")
        self._revoke_lease(record, reason[:64])
        updated = self._transition(record, "revoked", reason)
        return self._view(updated)

    def close_sharing_session(
        self, session_id: str
    ) -> AuthorizationSessionView:
        record = self._require_session(session_id)
        updated = self._transition(record, "closed", "closed")
        return self._view(updated)

    # -- internal discipline -----------------------------------------------------

    def _revoke_lease(
        self, record: _AuthorizationSession, reason: str
    ) -> None:
        """Revoke the canonical lease through the contract store's OWN
        command surface (LOCK-101 — the sole authority path)."""
        try:
            self._store.submit(
                RevokeLease(
                    lease_id=record.lease_id,
                    recorded_at=self._now(),
                    reason=reason,
                ),
                recorded_at=self._now(),
                contract_id=record.contract_id,
            )
        except Exception as error:  # consumed-domain isolation
            raise ConvergenceError(
                ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                "the canonical lease revocation failed (%s: %s)"
                % (getattr(error, "reason", "contract-error"), error),
            ) from error

    def _require_session(self, session_id: str) -> _AuthorizationSession:
        _require_reference(session_id, "session_id")
        record = self._sessions.get(session_id)
        if record is None:
            raise ConvergenceError(
                ConvergenceReasonCode.NOT_FOUND,
                "unknown canonical authorization session %r" % session_id,
            )
        return record

    def _require_consent_granted(
        self, record: _AuthorizationSession
    ) -> None:
        state = self._consent_state(record)
        if state != "granted":
            raise ConvergenceError(
                ConvergenceReasonCode.CONSENT_REQUIRED,
                "the canonical consent for %r is %r (a non-granted consent "
                "never authorizes; fail closed)" % (
                    record.session_id, state,
                ),
            )

    def _apply_lease_observation(
        self, record: _AuthorizationSession
    ) -> _AuthorizationSession:
        """Project the CANONICAL lease state onto the session (expiry
        and revocation observed through the store's own records —
        never local timers)."""
        try:
            lease = self._store.lease(record.lease_id)
        except Exception as error:
            raise ConvergenceError(
                ConvergenceReasonCode.NOT_FOUND,
                "the canonical lease %r became unreadable (%s)"
                % (record.lease_id, error),
            ) from error
        lease_state = str(lease.state)
        if lease_state == "expired" and record.state not in (
            "expired", "revoked", "closed",
        ):
            return self._transition(record, "expired", "lease-expired")
        if lease_state == "revoked" and record.state not in (
            "revoked", "closed",
        ):
            return self._transition(record, "revoked", "lease-revoked")
        return record

    def _transition(
        self, record: _AuthorizationSession, target: str, reason: str
    ) -> _AuthorizationSession:
        if target not in SESSION_STATES:
            raise ConvergenceError(
                ConvergenceReasonCode.VOCABULARY,
                "session state %r is outside the frozen vocabulary" % target,
            )
        allowed = SESSION_TRANSITIONS[record.state]
        if target not in allowed:
            raise ConvergenceError(
                ConvergenceReasonCode.LIFECYCLE_ILLEGAL,
                "session %r cannot move %r -> %r (the frozen transition "
                "table refuses)" % (record.session_id, record.state, target),
            )
        updated = _AuthorizationSession(
            session_id=record.session_id,
            contract_id=record.contract_id,
            lease_id=record.lease_id,
            buyer_ref=record.buyer_ref,
            provider_ref=record.provider_ref,
            session_ref=record.session_ref,
            consent_ref=record.consent_ref,
            path_ref=record.path_ref,
            platform_id=record.platform_id,
            state=target,
            termination_reason=reason or record.termination_reason,
            bytes_admitted=record.bytes_admitted,
            prepared_at=record.prepared_at,
            scope_valid_until=record.scope_valid_until,
            scope_byte_quota=record.scope_byte_quota,
        )
        self._sessions[record.session_id] = updated
        return updated

    def _view(
        self, record: _AuthorizationSession
    ) -> AuthorizationSessionView:
        return AuthorizationSessionView(
            session_id=record.session_id,
            contract_id=record.contract_id,
            lease_id=record.lease_id,
            buyer_ref=record.buyer_ref,
            provider_ref=record.provider_ref,
            session_ref=record.session_ref,
            consent_ref=record.consent_ref,
            path_ref=record.path_ref,
            platform_id=record.platform_id,
            state=record.state,
            termination_reason=record.termination_reason,
            bytes_admitted=record.bytes_admitted,
            prepared_at=record.prepared_at,
        )

    # -- the converged read surface (deterministic, sorted) ---------------------

    def sessions(self) -> Tuple[AuthorizationSessionView, ...]:
        return tuple(
            self._view(self._sessions[key]) for key in sorted(self._sessions)
        )

    def rate_state(self) -> RateLimitState:
        return self._rate_state

    def citations(self) -> Tuple[ChildCitation, ...]:
        """The converged citation set of this runtime's sessions (the
        contract citations — the canonical references, present by
        construction for every session)."""
        citations: List[ChildCitation] = []
        for key in sorted(self._sessions):
            record = self._sessions[key]
            contract = self._store.contract(record.contract_id)
            citations.append(cite_contract(
                contract,
                issuer="m014-convergence:%s" % record.provider_ref,
                cited_at=self._now(),
            ))
        return tuple(citations)


__all__ = [
    # the frozen vocabularies
    "CONVERGENCE_PREFIX",
    "CONVERGENCE_AUTHORITIES",
    "CITATION_KINDS",
    "VERTICAL_PROOF_KINDS",
    "SESSION_STATES",
    "SESSION_TRANSITIONS",
    "SESSION_TERMINAL_STATES",
    "CONSENT_STATES",
    "RATE_LIMIT_OPERATIONS",
    # typed errors
    "ConvergenceError",
    "ConvergenceReasonCode",
    # the child-authority citations (BY REFERENCE)
    "ChildCitation",
    "derive_citation_id",
    "cite_contract",
    "cite_offer",
    "cite_execution_plan",
    "cite_adapter_capability",
    "cite_replan_decision",
    "cite_settlement_reference",
    "cite_evidence_record",
    "cite_assurance_evaluation",
    "cite_vertical_proof",
    "peer_evidence_from_citation",
    # the rate-limit surface (LOCK-117 hardening)
    "RateLimitPolicy",
    "RateLimitState",
    "RateLimitVerdict",
    "check_rate_limit",
    # the citation revocation discipline (LOCK-117 hardening)
    "CitationRevocation",
    "citation_revocation",
    # the per-domain citation ledger
    "DomainCitationLedger",
    # the declared authorization scope
    "AuthorizationScope",
    # the converged authorization runtime (the DEC-0099 re-baseline)
    "ConvergedAuthorizationRuntime",
    "AuthorizationSessionView",
    "AuthorizationConsentView",
]
