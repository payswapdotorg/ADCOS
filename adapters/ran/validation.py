"""ADCOS 5G RAN integration input validators (WORK-020).

Pure, stdlib-only validators for the RAN domain value types (the
``adapters.ran`` family, mirroring the accepted WORK-019
``adapters.fivegc`` discipline).  No vendor SDK, no RAN state machine,
no radio, no cryptographic material.  The validators check SHAPES only
(3GPP TS 38.300/38.401/38.473/38.463/38.331/38.321/38.413 and
O-RAN.WG4 reference shapes); they never interpret RAN semantics and
never store RAN identifiers as authority (LOCK-002/016/017 -- RAN
identifiers are adapter-private opaque state; the ADCOS ``session_id``
is sacred, LOCK-006).

Standards leverage (LOCK-018): the validators use the Python standard
library ``re``/``unicodedata`` modules for shape checking -- the stdlib
is a standard implementation, not a reinvention.  The 3GPP/O-RAN
reference shapes appear as DATA with citations in docstrings; no
invented RAN primitive exists in this module.

Two structural rules are enforced MECHANICALLY here:

* The R1 identity-separation rule:
  :func:`assert_ref_session_separation` rejects any opaque RAN
  reference that equals or embeds a WORK-012 ``session_id`` (or vice
  versa) -- RAN/session identity collapse (mirrors the WORK-018/019
  route/session separation checks).

* The LOCK-023 secret-smuggling rule:
  :func:`reject_credential_like_text` rejects refs/labels/purposes
  that LOOK like credential material so an implementation cannot
  smuggle a key through a handle (mirrors the WORK-016/019
  ``_CREDENTIAL_SLOT_FORBIDDEN`` discipline).
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING, Tuple

from .errors import RanError, RanReasonCode

if TYPE_CHECKING:  # pragma: no cover - typing only; runtime import is
    from .model import (  # deferred to avoid an import cycle
        GnbProvisionRequest,
        RanObservation,
    )

#: Opaque RAN-side reference grammar:
#: ``ran:<kind>:<hexdigest-or-counter>`` with kind in
#: {gnb, bearer, alloc, ue}.  The kinds are the RAN-side identity
#: handles of the integration boundary.  The suffix is a lowercase hex
#: digest (``[0-9a-f]+``, the canonical form of a content-derived
#: sha256 hexdigest) or a decimal counter -- both are admitted by the
#: single ``[0-9a-f]+`` character class (decimal digits are a subset of
#: lowercase hex digits).  The suffix deliberately contains NO
#: ``session_id`` material (R1).
_REF_KINDS: Tuple[str, ...] = ("gnb", "bearer", "alloc", "ue")
_REF_PATTERN = re.compile(r"^ran:([a-z][a-z0-9-]*):([0-9a-f]+)$")

#: RAN capability-id REFERENCE grammar (the ``capability.access.ran.*``
#: namespace).  These are REFERENCES into WORK-005 registry semantics
#: (exposure by reference, never minted or registered here).  The
#: WORK-002 capability registry grammar today admits the
#: ``capability.core.*`` / ``capability.profile.*`` namespaces; the
#: ``capability.access.*`` namespace is a reserved future extension of
#: that frozen registry -- extending it is a WORK-005 vocabulary change
#: under spec/change-control.md, NOT something an adapter family may
#: do (fail-closed open world).
_RAN_CAPABILITY_PATTERN = re.compile(
    r"^capability\.access\.ran(\.[a-z0-9][a-z0-9-]*)+$"
)

#: LOCK-023 -- forbidden credential-like tokens.  This tuple mirrors
#: the WORK-019 ``adapters.fivegc.validation._CREDENTIAL_SLOT_FORBIDDEN``
#: list exactly, extended minimally with the RAN-relevant concepts the
#: WORK-020 brief pins (``credential``, ``authtoken``, ``private``,
#: ``cert``): a RAN-side reference, label, name, or purpose that
#: contains one of these tokens fails closed so an implementation
#: cannot smuggle secret material through a handle.  RAN bearer/gNB
#: handles are opaque labels, never key carriers.
_FORBIDDEN_TOKENS: Tuple[str, ...] = (
    # WORK-019 fivegc list (verbatim):
    "private_key",
    "secret_key",
    "password",
    "token",
    "api_key",
    "shared_secret",
    "opc",
    "k_",
    "ausf_key",
    "rand",
    "autn",
    "xres",
    "k_asme",
    "kausrp",
    "knasf",
    "kamf",
    "impi_key",
    "subscription_key",
    # WORK-020 minimal extension:
    "credential",
    "authtoken",
    "private",
    "cert",
)


def validate_session_id(value: str) -> str:
    """Validate a WORK-012 ``session_id`` at the RAN seam.

    The ``session_id`` is sacred and access-independent (LOCK-006); the
    RAN boundary treats it as an opaque passthrough identity and never
    derives RAN identity from it.  This checks the SEAM shape only:
    non-empty, no whitespace, no control characters.  Raises
    :class:`RanError` (reason ``invalid-input``) otherwise.
    """
    if not isinstance(value, str) or not value:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "session_id must be a non-empty string",
        )
    for character in value:
        if character.isspace():
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "session_id must not contain whitespace",
            )
        if unicodedata.category(character) in ("Cc", "Cf"):
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "session_id must not contain control characters",
            )
    return value


def validate_opaque_ref(value: str, *, prefix: str) -> str:
    """Validate an opaque RAN-side reference against the frozen grammar.

    Shape: ``ran:<prefix>:<suffix>`` where ``prefix`` is one of the
    accepted RAN reference kinds (``gnb``, ``bearer``, ``alloc``,
    ``ue``) and ``suffix`` is a lowercase hex digest or a decimal
    counter (``[0-9a-f]+``).  Raises :class:`RanError` for a malformed
    reference, an unknown prefix kind, or a prefix mismatch.  The
    reference is RAN-side identity -- it is never a WORK-012
    ``session_id`` and never authoritative for ADCOS state
    (LOCK-006/017).
    """
    if not isinstance(value, str) or not value:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "ran reference must be a non-empty string",
        )
    if prefix not in _REF_KINDS:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "ran reference prefix must be one of %s (got %r)"
            % (list(_REF_KINDS), prefix),
        )
    match = _REF_PATTERN.match(value)
    if match is None:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "ran reference must match ran:<prefix>:<hexdigest-or-counter> "
            "with prefix in %s (lowercase hex or decimal suffix)"
            % (list(_REF_KINDS),),
        )
    if match.group(1) != prefix:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "ran reference prefix must be %r (got %r)" % (prefix, match.group(1)),
        )
    return value


def assert_ref_session_separation(ref: str, session_id: str) -> None:
    """Mechanical R1 check: a RAN reference must never collapse onto a
    WORK-012 ``session_id``.

    The ADCOS ``session_id`` is sacred and access-independent
    (LOCK-006); RAN-side references (bearer/gNB/allocation handles)
    are a SEPARATE identity space.  A reference that EQUALS or EMBEDS a
    ``session_id``, or a ``session_id`` that embeds a RAN reference,
    is a RAN/session identity collapse and fails closed with
    :class:`RanError` reason ``RAN_SESSION_COLLAPSE`` (mirrors the
    WORK-018/019 route/session collapse checks).
    """
    if not isinstance(ref, str) or not isinstance(session_id, str):
        raise RanError(
            RanReasonCode.RAN_SESSION_COLLAPSE,
            "ref and session_id must both be strings for the R1 check",
        )
    if not ref or not session_id:
        return  # nothing to separate against (shape checks own emptiness)
    if ref == session_id or session_id in ref or ref in session_id:
        raise RanError(
            RanReasonCode.RAN_SESSION_COLLAPSE,
            "RAN reference must not equal or embed the sacred session_id "
            "(and vice versa) -- R1: RAN bearer/gNB identity never "
            "collapses onto session identity; LOCK-006",
        )


def _normalized_for_credential_scan(value: str) -> str:
    lowered = value.lower()
    for separator in ("-", " ", "."):
        lowered = lowered.replace(separator, "_")
    return lowered


def reject_credential_like_text(value: str, *, what: str) -> None:
    """Reject credential-like material in a RAN-side text field.

    A reference, label, name, element id, or purpose that contains a
    forbidden token (key/secret/password/token/credential/...) fails
    closed (LOCK-023): RAN-side handles are opaque labels, never key
    carriers.  Separator variants (``secret-key``, ``secret key``) are
    normalized before the scan so hyphenated forms cannot slip past.
    Raises :class:`RanError` (reason ``invalid-input``) with ``what``
    naming the offending field; returns ``None`` when the text is
    clean.
    """
    if not isinstance(value, str) or not value:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "%s must be a non-empty string" % what,
        )
    normalized = _normalized_for_credential_scan(value)
    for forbidden in _FORBIDDEN_TOKENS:
        if forbidden in normalized:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "%s must not resemble secret material "
                "(LOCK-023; forbidden token: %s)" % (what, forbidden),
            )


def validate_ran_capability_reference(value: str) -> str:
    """Validate a RAN capability-id REFERENCE (exposure, never
    registry).

    The reference grammar is the reserved ``capability.access.ran.*``
    namespace (a WORK-005 registry-semantics reference; the adapter
    never mints, registers, or mutates capability entries -- see the
    module docstring note on the frozen WORK-002 registry grammar).
    """
    if not isinstance(value, str) or not _RAN_CAPABILITY_PATTERN.match(value):
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "RAN capability reference must match "
            "capability.access.ran.<segment> (reference only; never "
            "minted here -- WORK-005 registry semantics)",
        )
    return value


def validate_ran_observation(value: "RanObservation") -> "RanObservation":
    """Validate the ``observe()`` return shape (per-op return-shape
    validator).

    Checks: a real :class:`adapters.ran.model.RanObservation`; at
    least one reported cell; capabilities drawn from the known RAN
    reference set or at least generic-shaped
    ``capability.access.ran.*`` strings; and deep re-validation by
    reconstruction -- the frozen model constructors re-run every shape
    check (health states, non-negative integer resource fields, the
    six-metric link vocabulary), so a hand-mangled instance is rejected
    exactly like a freshly malformed one.  Returns the validated
    observation; raises :class:`RanError` on any shape violation.
    (The model import is deferred because the model module imports
    this module's validators -- the WORK-016/019 sandbox convention.)
    """
    from .model import (
        RAN_CAPABILITY_REFERENCES,
        RanHealthSnapshot,
        RanObservation,
        RanResourceSnapshot,
        RanSplitTopology,
    )

    if not isinstance(value, RanObservation):
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "observe must return a RanObservation",
        )
    if not value.health.cell_states:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "observe must report at least one cell in health.cell_states",
        )
    for capability in value.capabilities:
        if capability not in RAN_CAPABILITY_REFERENCES:
            validate_ran_capability_reference(capability)
    try:
        return RanObservation(
            capabilities=tuple(value.capabilities),
            health=RanHealthSnapshot(
                gnb_state=value.health.gnb_state,
                cu_state=value.health.cu_state,
                du_states=tuple(value.health.du_states),
                ru_states=tuple(value.health.ru_states),
                cell_states=dict(value.health.cell_states),
                ngap_connected=value.health.ngap_connected,
            ),
            resources=RanResourceSnapshot(
                prb_total=value.resources.prb_total,
                prb_used=value.resources.prb_used,
                rrc_connected_ue_count=value.resources.rrc_connected_ue_count,
                active_drb_count=value.resources.active_drb_count,
            ),
            topology=RanSplitTopology(
                cu=value.topology.cu,
                dus=tuple(value.topology.dus),
                rus=tuple(value.topology.rus),
            ),
            link_metrics=dict(value.link_metrics),
        )
    except (ValueError, TypeError):
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "observe returned a malformed RanObservation (shape "
            "re-validation failed)",
        ) from None


def validate_gnb_provision_request(
    request: "GnbProvisionRequest",
) -> "GnbProvisionRequest":
    """Validate a ``provision_gnb`` request shape.

    Checks: a real :class:`adapters.ran.model.GnbProvisionRequest`;
    non-empty cells with unique cell ids and valid numerology/PRB
    ranges (deep re-validation by reconstruction); and topology
    consistency -- at least one DU, every DU-served cell id exists in
    the requested cells, and every requested cell is covered by some
    DU.  Raises :class:`RanError` on any violation; returns the
    validated request.  (Deferred model import -- see
    :func:`validate_ran_observation`.)
    """
    from .model import (
        CellSpec,
        CuElement,
        DuElement,
        GnbProvisionRequest,
        RanSplitTopology,
        RuElement,
    )

    if not isinstance(request, GnbProvisionRequest):
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "provision_gnb requires a GnbProvisionRequest",
        )
    if not request.cells:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "gnb provision request must carry at least one cell",
        )
    cell_ids = [cell.cell_id for cell in request.cells]
    if len(set(cell_ids)) != len(cell_ids):
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "gnb provision request cell ids must be unique",
        )
    topology = request.topology
    if not topology.dus:
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "gnb provision topology must carry at least one DU "
            "(TS 38.401 §5: a gNB serves cells through its DUs)",
        )
    served = [cell_id for du in topology.dus for cell_id in du.cell_ids]
    for cell_id in served:
        if cell_id not in cell_ids:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "topology DU serves unknown cell %r (not in the request's "
                "cells)" % cell_id,
            )
    for cell_id in cell_ids:
        if cell_id not in served:
            raise RanError(
                RanReasonCode.INVALID_INPUT,
                "cell %r is not covered by any DU in the topology" % cell_id,
            )
    try:
        return GnbProvisionRequest(
            gnb_name=request.gnb_name,
            cells=tuple(
                CellSpec(
                    cell_id=cell.cell_id,
                    band=cell.band,
                    duplex=cell.duplex,
                    numerology=cell.numerology,
                    arfcn=cell.arfcn,
                    prb_count=cell.prb_count,
                )
                for cell in request.cells
            ),
            topology=RanSplitTopology(
                cu=CuElement(
                    element_id=topology.cu.element_id,
                    split=topology.cu.split,
                    state=topology.cu.state,
                ),
                dus=tuple(
                    DuElement(
                        element_id=du.element_id,
                        split=du.split,
                        state=du.state,
                        cell_ids=tuple(du.cell_ids),
                    )
                    for du in topology.dus
                ),
                rus=tuple(
                    RuElement(
                        element_id=ru.element_id,
                        split=ru.split,
                        state=ru.state,
                        band=ru.band,
                    )
                    for ru in topology.rus
                ),
            ),
        )
    except (ValueError, TypeError):
        raise RanError(
            RanReasonCode.INVALID_INPUT,
            "gnb provision request failed shape re-validation "
            "(numerology/prb/duplex ranges or element shapes)",
        ) from None


__all__ = [
    "validate_session_id",
    "validate_opaque_ref",
    "assert_ref_session_separation",
    "reject_credential_like_text",
    "validate_ran_capability_reference",
    "validate_ran_observation",
    "validate_gnb_provision_request",
]
