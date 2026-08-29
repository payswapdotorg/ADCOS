"""WORK-039 federation-at-scale error values.

The typed failure vocabulary of the federation-at-scale harness.
Every reason code carries the ``scale.`` prefix (the W033 agent
error-vocabulary style; the W037 ``interop.`` and W038 ``future.``
precedents).  The prefix makes harness-scoped failures greppable and
structurally distinct from federation (``domain-exists``,
``sequence-conflict``), simulator (``simulator.``), agent, and
appliance failures: a scale-harness problem can never masquerade as a
protocol-authority problem, and no federation reason code is ever
re-defined here.
"""

from __future__ import annotations

from typing import Tuple

_DETAIL_LIMIT = 200

#: The frozen reason-code prefix (the W033/W037/W038 typed-error style).
SCALE_PREFIX = "scale."


class ScaleError(Exception):
    """A typed WORK-039 failure (never a bare exception crossing the
    harness boundary)."""

    def __init__(self, reason: str, detail: str) -> None:
        detail = detail[:_DETAIL_LIMIT]
        super().__init__("%s: %s" % (reason, detail))
        self.reason = reason
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "%s: %s" % (self.reason, self.detail)


class ScaleReasonCode:
    """The frozen reason vocabulary (13 codes).

    Fail-closed semantics: scenario/spec failures identify the exact
    violated contract; delivery refusals identify the failed domain;
    the convergence checker refuses any observation that diverges from
    the computed bound; the isolation checker refuses any digest drift
    in non-failed stores; the authority guard refuses any attempt to
    mutate a composed authority through anything but its public
    contract; the evidence guard refuses any real-deployment claim
    (the W039 frozen contract does not require one, and synthetic
    simulation evidence can never be promoted to it).
    """

    INVALID_INPUT = "scale.invalid-input"
    SPEC_INVALID = "scale.spec-invalid"
    SHAPE_UNKNOWN = "scale.shape-unknown"
    TOPOLOGY_INVALID = "scale.topology-invalid"
    WORLD_INVALID = "scale.world-invalid"
    DOMAIN_UNKNOWN = "scale.domain-unknown"
    DELIVERY_REFUSED = "scale.delivery-refused"
    CONVERGENCE_MISMATCH = "scale.convergence-mismatch"
    ISOLATION_VIOLATION = "scale.isolation-violation"
    AUTHORITY_VIOLATION = "scale.authority-violation"
    REPLAY_DIVERGENCE = "scale.replay-divergence"
    INTEGRATION_INVALID = "scale.integration-invalid"
    EVIDENCE_CLASS_VIOLATION = "scale.evidence-class-violation"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (
            cls.INVALID_INPUT,
            cls.SPEC_INVALID,
            cls.SHAPE_UNKNOWN,
            cls.TOPOLOGY_INVALID,
            cls.WORLD_INVALID,
            cls.DOMAIN_UNKNOWN,
            cls.DELIVERY_REFUSED,
            cls.CONVERGENCE_MISMATCH,
            cls.ISOLATION_VIOLATION,
            cls.AUTHORITY_VIOLATION,
            cls.REPLAY_DIVERGENCE,
            cls.INTEGRATION_INVALID,
            cls.EVIDENCE_CLASS_VIOLATION,
        )
