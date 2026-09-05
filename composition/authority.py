"""WORK-054 authority availability registry.

The composition layer composes the accepted authorities through
their public module boundaries.  Before any composition runs, the
registry PROBES each authority surface and records its
availability honestly:

- ``AVAILABLE``: the public module imports on the current
  mainline and the authority participates in the composition.
- ``ABSENT``: the authority's implementation surface does not
  exist on the current mainline (WORK-048: the sharing runtime is
  ``accepted-not-restored``).  ABSENT is a FAIL-CLOSED
  classification: every chain edge that requires this authority
  must refuse to advance and must never fabricate or substitute
  the missing component.
- ``DEFECT``: the authority's implementation surface exists but
  cannot be imported because of an INHERITED defect in the
  restored artifacts (WORK-046: a stale cross-import against the
  evolved usage surface).  DEFECT is recorded and disclosed; it is
  never repaired by WORK-054 and never silently bypassed.

The probes are importlib-based and deterministic: module
resolution depends only on the repository tree, never on runtime
state, and the recorded details are byte-stable across runs and
hash seeds.  The probe module deliberately uses DYNAMIC importlib
calls (never static ``import`` statements) so the composition
import audit can distinguish the sanctioned availability probe
from an accidental dependency on a defective or absent surface.
"""

from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from typing import Tuple


class AuthorityAvailability:
    """The frozen availability vocabulary of a composed authority."""

    AVAILABLE = "available"
    ABSENT = "absent-fail-closed"
    DEFECT = "defect-inherited"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.AVAILABLE, cls.ABSENT, cls.DEFECT)


#: The fail-closed detail recorded for the W048 sharing runtime
#: absence (the roadmap's own restoration note states the W048
#: implementation artifacts are not part of the accepted
#: restoration tree and require an explicit Architect directive).
W048_ABSENT_DETAIL = (
    "WORK-048 is historically accepted but accepted-not-restored on "
    "this mainline: no 'sharing' package exists and the containment "
    "surface carries only the frozen ACR-012 state vocabulary "
    "(containment/state.py) with no runtime, no authority class, and "
    "no boundary-establishment implementation.  The composition layer "
    "must detect this absence and fail closed wherever W048 authority "
    "is required; it must never restore, recreate, mock, or substitute "
    "the W048 runtime."
)

#: The disclosed detail recorded for the WORK-046 inherited import
#: defect (restored W046 artifacts cross-import
#: ``usage.errors.UsageLedgerError``, a name that no longer exists
#: in the evolved W052 usage surface).
W046_DEFECT_DETAIL = (
    "WORK-046's restored artifacts fail to import on the current "
    "mainline (developerapi.* cross-imports usage.errors."
    "UsageLedgerError, which the evolved W052 usage surface no "
    "longer defines).  This is an inherited restoration defect, "
    "outside the WORK-054 authorized scope: it is detected and "
    "disclosed here, never repaired and never silently bypassed. "
    "API/webhook observation classification is proven through the "
    "receiving authorities' public boundaries (W052 kind table, "
    "W044 callback observation fold, W053 reference kinds)."
)


@dataclass(frozen=True)
class AuthorityProbe:
    """One probed authority surface and its honest availability."""

    work_item: str
    authority_surface: str
    availability: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "work_item": self.work_item,
            "authority_surface": self.authority_surface,
            "availability": self.availability,
            "detail": self.detail,
        }


def _module_available(module_name: str) -> Tuple[bool, str]:
    """Probe one module import (dynamic, deterministic)."""
    try:
        importlib.import_module(module_name)
    except ImportError as error:
        return False, "%s: %s" % (type(error).__name__, error)
    return True, ""


def _spec_absent(module_name: str) -> bool:
    spec = importlib.util.find_spec(module_name)
    return spec is None


def w048_runtime_absent() -> bool:
    """True iff the W048 sharing runtime surface is absent.

    The detection is structural and multi-layered, exactly as the
    WORK-054 contract requires: the ``sharing`` package does not
    exist; the containment surface is a PEP-420 namespace package
    carrying ONLY the frozen ACR-012 vocabulary module (no package
    ``__init__``, no runtime module, no authority implementation);
    and the names the W048-era consumers expected
    (``containment.CapabilityMatrix``,
    ``containment.ContainmentAuthority``) are not importable from
    the namespace package.
    """
    if not _spec_absent("sharing"):
        return False
    if not _spec_absent("containment.runtime"):
        return False
    if importlib.util.find_spec("containment") is None:
        return False
    namespace = importlib.import_module("containment")
    if getattr(namespace, "__file__", None) is not None:
        # a real package __init__ exists: not the restored
        # vocabulary-only surface.
        return False
    # the frozen vocabulary module IS restored (DATA only)
    if _spec_absent("containment.state"):
        return False
    return True


def _w46_defect() -> Tuple[str, str]:
    available, detail = _module_available("developerapi")
    if available:
        return AuthorityAvailability.AVAILABLE, "imports cleanly"
    return AuthorityAvailability.DEFECT, "%s | %s" % (detail, W046_DEFECT_DETAIL)


#: The probed authority table (evaluated lazily and cached: the
#: import graph is fixed for the process lifetime, so the probe
#: results are pure functions of the repository tree).
def probe_authorities() -> Tuple[AuthorityProbe, ...]:
    """Probe every WORK-054 authority surface, honestly."""
    probes: Tuple[AuthorityProbe, ...] = (
        AuthorityProbe(
            work_item="WORK-009",
            authority_surface="intent",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("intent")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="intent normalization authority (public module boundary)",
        ),
        AuthorityProbe(
            work_item="WORK-047",
            authority_surface="marketplace",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("marketplace")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="marketplace discovery/selection + W051/W041 coordination seams",
        ),
        AuthorityProbe(
            work_item="WORK-045",
            authority_surface="eligibility",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("eligibility")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="eligibility/trust/jurisdiction policy authority",
        ),
        AuthorityProbe(
            work_item="WORK-051",
            authority_surface="commercial",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("commercial")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="CommercialCore canonical commercial state authority",
        ),
        AuthorityProbe(
            work_item="WORK-041",
            authority_surface="networkpath",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("networkpath")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="first-class NetworkPath lifecycle authority",
        ),
        AuthorityProbe(
            work_item="WORK-042",
            authority_surface="platform.journal/platform.lifecycle",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("platform.journal")[0]
                and _module_available("platform.lifecycle")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="platform event journal + journal-first recovery authority",
        ),
        AuthorityProbe(
            work_item="WORK-048",
            authority_surface="sharing (runtime) / containment (runtime)",
            availability=(
                AuthorityAvailability.ABSENT
                if w048_runtime_absent()
                else AuthorityAvailability.DEFECT
            ),
            detail=W048_ABSENT_DETAIL,
        ),
        AuthorityProbe(
            work_item="WORK-048",
            authority_surface="containment.state (ACR-012 vocabulary)",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("containment.state")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail=(
                "the frozen boundary-lifecycle vocabulary restored on the "
                "current mainline: capability + boundary state dimensions, "
                "the transition table, and the journaled action vocabulary. "
                "Vocabulary DATA only -- never the runtime authority."
            ),
        ),
        AuthorityProbe(
            work_item="WORK-012",
            authority_surface="sessions",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("sessions")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="logical session lifecycle authority",
        ),
        AuthorityProbe(
            work_item="WORK-052",
            authority_surface="usage",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("usage")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="UsageLedger canonical usage/economic ledger authority",
        ),
        AuthorityProbe(
            work_item="WORK-053",
            authority_surface="allocation",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("allocation")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="EconomicAllocation authority",
        ),
        AuthorityProbe(
            work_item="WORK-044",
            authority_surface="payment",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("payment")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="provider-neutral payment boundary + settlement gateway",
        ),
        AuthorityProbe(
            work_item="WORK-049",
            authority_surface="client",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("client")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="provider/buyer client runtime (projection boundary)",
        ),
        AuthorityProbe(
            work_item="WORK-050",
            authority_surface="platformcaps",
            availability=(
                AuthorityAvailability.AVAILABLE
                if _module_available("platformcaps")[0]
                else AuthorityAvailability.DEFECT
            ),
            detail="platform capability/isolation declaration registry",
        ),
    )
    w046_availability, w046_detail = _w46_defect()
    probes = probes + (
        AuthorityProbe(
            work_item="WORK-046",
            authority_surface="developerapi",
            availability=w046_availability,
            detail=w046_detail,
        ),
    )
    return probes


def _cached_probes() -> Tuple[AuthorityProbe, ...]:
    global _PROBE_CACHE
    try:
        cache = _PROBE_CACHE
    except NameError:
        cache = None
    if cache is None:
        cache = probe_authorities()
        _PROBE_CACHE = cache
    return cache


_PROBE_CACHE = None
#: The frozen probe table for this process (pure function of the
#: repository tree; used by the battery's availability cases and
#: the evidence document).
AUTHORITY_PROBES: Tuple[AuthorityProbe, ...] = _cached_probes()
