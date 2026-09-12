"""ADCOS credential-lifecycle admission-gate composition (M018 —
Credential and Key Lifecycle Operations).

The admission gate consumed BY REFERENCE from the accepted
``client/``/``federation/`` surfaces (LOCK-117: no second
authorization runtime anywhere in this package — this module composes
the ACCEPTED admission/authorization surfaces through their public
APIs and records their verdicts; it never re-decides trust):

- **Gate 1 — the M014 credential-lifecycle verdict** (the accepted
  ``identity/`` convergence surface):
  :func:`identity.convergence.evaluate_credential_lifecycle` over the
  accepted :class:`CredentialLifecyclePolicy` and
  :class:`CredentialLifecycleState`.  Admitting verdicts: ``ok`` /
  ``rotation-due``; every other verdict (``revoked``, ``expired``,
  ``not-active``, ``rotation-overdue``) fails closed.
- **Gate 2 — the M014 principal-authorization verdict** (the accepted
  ``identity/`` convergence surface): the accepted
  :class:`identity.convergence.AuthorizationRegistry`'s own ``check``
  gate (node/contract/window/revocation verdicts — the M014
  authorization authority; revoked authorizations surface the
  ``revoked`` verdict first).
- **Gate 3 — the operational admission** (the accepted
  ``federation/``/``client/`` surfaces): the converged authorization
  runtime's TRAFFIC-ADMISSION point
  (:meth:`federation.convergence.ConvergedAuthorizationRuntime.
  account_traffic`) driven with a ZERO-byte probe — every canonical
  gate (the consent state, the lease expiry observation, the lease
  validity window, the active-session requirement, the declared
  quota) is evaluated while NO state advances (byte-for-byte
  idempotent probing).  A typed canonical rejection is recorded
  verbatim as the operational rejection class.

The composed probe is MECHANICAL: ``admitted`` is true iff all three
consumed verdicts admit.  No policy rule exists in this module.

The world builder composes the frozen W049 provider client over the
converged 1.1 authorities through the ACCEPTED composition root
(:func:`client.convergence.build_converged_provider_client`) —
injected REAL authorities only (the M002 contract store, the M005
evidence store, the M003 offers exchange, the W049 platform adapter,
the deterministic clock seam, the declared authorization scope).

Determinism (LOCK-119): injected instants only; no wall clock, no
randomness, no network, no secrets (the probe carries references and
consumed verdict strings only — structurally secret-free).
"""

from __future__ import annotations

from typing import Any

from identity.convergence import (
    AuthorizationRegistry,
    CredentialLifecyclePolicy,
    CredentialLifecycleState,
    evaluate_credential_lifecycle,
)

from .errors import CredentialLifecycleError, CredentialLifecycleReason
from .model import (
    AdmissionProbe,
    _wrap_consumed_error,
)

__all__ = [
    "admission_gate_world",
    "probe_credential_admission",
    "check_credential_admission",
]


def admission_gate_world(
    *,
    store: Any,
    evidence: Any,
    exchange: Any,
    adapter: Any,
    clock: Any,
    scope: Any,
    user_ref: str,
    device_ref: str,
    application_ref: str,
    platform_id: str,
    rate_policy: Any = None,
) -> Any:
    """Compose the frozen W049 provider client over the converged 1.1
    authorities — through the ACCEPTED composition root
    ``client.convergence.build_converged_provider_client`` (by
    reference, 1:1: every authority is REAL and injected; this
    function adds no authority of its own and constructs none)."""
    from client.convergence import build_converged_provider_client

    with _wrap_consumed_error("the admission-gate world composition"):
        return build_converged_provider_client(
            store=store,
            evidence=evidence,
            exchange=exchange,
            adapter=adapter,
            clock=clock,
            scope=scope,
            user_ref=user_ref,
            device_ref=device_ref,
            application_ref=application_ref,
            platform_id=platform_id,
            rate_policy=rate_policy,
        )


def probe_credential_admission(
    *,
    policy: CredentialLifecyclePolicy,
    state: CredentialLifecycleState,
    registry: AuthorizationRegistry,
    authorization_id: str,
    node_id: str,
    contract_id: str,
    credential_ref: str,
    at_instant: str,
    authority: Any,
    session_id: str,
) -> AdmissionProbe:
    """One composed admission-gate probe for a credential at an
    injected instant — the three CONSUMED verdicts recorded verbatim.

    This is the M018 admission gate: the accepted M014 identity gates
    plus the accepted converged traffic-admission point (the
    ``federation``/``client`` surfaces), all driven through their
    public APIs.  The verdict is mechanical (never re-decided here);
    a consumed gate's typed rejection is preserved as the operational
    rejection class (fail closed, never fabricated)."""
    if not isinstance(policy, CredentialLifecyclePolicy):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "probe_credential_admission requires the accepted M014 "
            "CredentialLifecyclePolicy (by reference)",
        )
    if not isinstance(state, CredentialLifecycleState):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "probe_credential_admission requires the accepted M014 "
            "CredentialLifecycleState (by reference)",
        )
    if not isinstance(registry, AuthorizationRegistry):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "probe_credential_admission requires the accepted M014 "
            "AuthorizationRegistry (by reference)",
        )
    # Gate 1 — the M014 credential-lifecycle verdict (identity/, by
    # reference; a typed lifecycle verdict, never an exception for a
    # plain denial; malformed bookkeeping surfaces as the typed
    # composition error).
    with _wrap_consumed_error("the credential-lifecycle admission gate"):
        verdict = evaluate_credential_lifecycle(
            policy, state, credential_ref, at_instant
        )
    lifecycle_verdict = verdict.verdict
    # Gate 2 — the M014 principal-authorization verdict (identity/, by
    # reference; the registry observes revocation first).
    with _wrap_consumed_error("the principal-authorization admission gate"):
        authorization_verdict = registry.check(
            authorization_id,
            node_id=node_id,
            contract_id=contract_id,
            at_instant=at_instant,
        )
    # Gate 3 — the operational admission (federation/, by reference):
    # the converged traffic-admission point with a ZERO-byte probe —
    # every canonical gate evaluated, no state advanced (idempotent).
    operational_state = _probe_operational_admission(
        authority, session_id
    )
    admitted = (
        lifecycle_verdict in ("ok", "rotation-due")
        and authorization_verdict == "authorized"
        and operational_state == "active"
    )
    rejection = ""
    if not admitted:
        if lifecycle_verdict not in ("ok", "rotation-due"):
            rejection = "lifecycle:%s" % lifecycle_verdict
        elif authorization_verdict != "authorized":
            rejection = "authorization:%s" % authorization_verdict
        else:
            rejection = "admission-gate:%s" % operational_state
    return AdmissionProbe(
        probe_id="",
        credential_ref=credential_ref,
        node_id=node_id,
        at_instant=at_instant,
        lifecycle_verdict=lifecycle_verdict,
        authorization_verdict=authorization_verdict,
        operational_state=operational_state,
        admitted=admitted,
        rejection=rejection,
    )


def _probe_operational_admission(authority: Any, session_id: str) -> str:
    """The accepted converged traffic-admission point, probed with a
    ZERO byte count: every canonical gate (consent, lease expiry
    observation, lease validity, active-session, quota) evaluates
    while ``bytes_admitted`` advances by zero (byte-for-byte
    idempotent).  A typed canonical rejection class is recorded
    verbatim (``rejected:<reason>``); a non-typed failure surfaces as
    the composition error (fail closed, never fabricated)."""
    if authority is None or not hasattr(authority, "account_traffic"):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "probe_credential_admission requires the accepted "
            "federation.ConvergedAuthorizationRuntime (the converged "
            "admission gate, consumed by reference)",
        )
    from federation.convergence import ConvergedAuthorizationRuntime

    if not isinstance(authority, ConvergedAuthorizationRuntime):
        raise CredentialLifecycleError(
            CredentialLifecycleReason.INVALID_INPUT,
            "the operational admission gate must be the accepted "
            "federation.ConvergedAuthorizationRuntime (got %s — LOCK-117: "
            "no second authorization runtime is ever composed here)"
            % type(authority).__name__,
        )
    try:
        view = authority.account_traffic(session_id, 0)
    except CredentialLifecycleError:
        raise
    except Exception as error:  # noqa: BLE001 - consumed-domain isolation
        # the consumed gate's TYPED rejection class is recorded
        # verbatim (code or reason — the federation convergence
        # runtime carries ``code``, the frozen client carries
        # ``reason``); a non-typed failure is the composition error
        code = str(
            getattr(error, "code", "") or getattr(error, "reason", "") or ""
        )
        if code:
            return "rejected:%s" % code
        raise CredentialLifecycleError(
            CredentialLifecycleReason.COMPOSITION,
            "the converged admission gate rejected the probe with an "
            "untyped error (%s)" % (error,),
        ) from None
    return str(view.state)


def check_credential_admission(
    *,
    policy: CredentialLifecyclePolicy,
    state: CredentialLifecycleState,
    registry: AuthorizationRegistry,
    authorization_id: str,
    node_id: str,
    contract_id: str,
    credential_ref: str,
    at_instant: str,
    authority: Any,
    session_id: str,
) -> AdmissionProbe:
    """The raising twin of the probe: fail closed (typed
    ``credential-lifecycle-illegal``) when the composed verdict is
    NOT admitting — for callers that REQUIRE admission at an
    instant (the drill sequencing).  The typed verdict twin remains
    :func:`probe_credential_admission`."""
    probe = probe_credential_admission(
        policy=policy,
        state=state,
        registry=registry,
        authorization_id=authorization_id,
        node_id=node_id,
        contract_id=contract_id,
        credential_ref=credential_ref,
        at_instant=at_instant,
        authority=authority,
        session_id=session_id,
    )
    if not probe.admitted:
        raise CredentialLifecycleError(
            CredentialLifecycleReason.LIFECYCLE_ILLEGAL,
            "credential %r is not admitted at %s (%s — the composed "
            "admission gate rejected the probe; fail closed)"
            % (credential_ref, at_instant, probe.rejection),
        )
    return probe
