"""ADCOS future access convergence (M024 — Future Access
Convergence, R9-CORE-001, DEC-0120; the R9 convergence child — every
accepted R9 child authority is the composition substrate, and the
child whose acceptance completes the R9 gate — the terminal roadmap
gate).

The R9 convergence surface of the R9 charter M024 scope, living in the
M020-owned shared prefix ``accesstech/`` as a NEW module (the frozen
M020 package surface — ``accesstech/__init__.py`` and the accepted
envelope/ladder/handover/registry modules — is imported here and
NEVER edited):

- **The cross-technology interchange drill**
  (:class:`InterchangeHop`, :class:`InterchangeDrillPlan`,
  :func:`run_interchange_drill`): deterministic technology handovers
  across the three access-technology domains of the R9 gate objective
  — wireline <-> radio-family <-> non-terrestrial — with LOCK-108
  VERBATIM constraint-set equality at every step, driven through the
  ACCEPTED ``resilience/`` handover machinery
  (:func:`resilience.handover.perform_handover` — the candidate
  carries the contract's own hard constraints VERBATIM, so the
  consumed M008 kernel validates and the accepted journal records the
  EXPLICIT reconnect pair).  The composed technologies are the
  accepted M021 wireline, M007 radio-family and M022 non-terrestrial
  reference compositions, mounted and registered through the accepted
  M020 registration surface by the composition root (the battery) and
  consumed here BY REFERENCE as :class:`~accesstech.registry.
  TechnologyRegistration` records — never re-mounted, never
  re-implemented, never re-declared;

- **The technology REPLACEMENT drill** (the "or replace" half of the
  gate objective: :func:`replace_technology` /
  :class:`ReplacementRecord`): a LIVE technology replaced by another
  under an ACTIVE contract with contract continuity — the replacement
  rides the same accepted machinery (an explicit recorded reconnect
  naming BOTH the old AND the new references, the WORK-012 discipline
  the runtime journal enforces mechanically); a replacement that
  changes nothing, a replacement between technologies that never
  declared the replacement kind, and a replacement record missing
  either side of the reconnect pair are all TYPED rejections — never a
  silent swap;

- **The converged-domain compatibility matrix extended over the R9
  domains** (:class:`R9DomainVersion`, :func:`classify_r9_domain`,
  :func:`negotiate_r9_matrix`, :func:`compose_access_convergence_
  matrix`): the accepted ``upgrade/`` matrix discipline (the frozen
  ``MAJOR.MINOR`` additive-evolution grammar, the frozen verdict
  vocabulary, sorted-domain iteration, input-order independence,
  byte-stable digests) extended onto the R9 domain labels, composed
  with the accepted engine's OWN R7-substrate verdict rows and the
  accepted M019 R8 matrix rows into ONE converged matrix — every
  consumed row carried verbatim (DATA consumed by reference at
  runtime, never re-classified here);

- **Federation-scale convergence over the R9 domains**
  (:class:`AccessScaleBounds`, :class:`AccessScaleConvergence`,
  :func:`verify_access_scale_convergence`): the accepted ``scale/``
  harness discipline extended onto the R9 material — the accepted
  harness's run result consumed by reference at runtime (its OWN
  digests and counts carried verbatim, never recomputed here),
  verified against the DECLARED deterministic bounds (the replay
  identity, the world/citation/revocation envelopes, the
  topology-predicted propagation round counts — every one failing
  closed on divergence).

BY-REFERENCE composition map (the M014/M019 discipline — import and
compose, never reimplement, weaken, fork or bypass):

* ``protocol`` (canonical JSON, injected instants) — the
  serialization/temporal conventions;
* ``replan`` — the frozen trigger-kind vocabulary
  (:data:`replan.TRIGGER_KINDS`) and the pure cross-authority LOCK-108
  gate :func:`replan.verify_decision_preserves_contract`, consumed on
  every drill decision;
* ``resilience`` — the ACCEPTED handover machinery
  (:func:`handover_candidate` + :func:`perform_handover`) that drives
  every interchange/replacement handover, the typed runtime-store
  surface (:class:`~resilience.runtime.RuntimeStore`) the drills ride,
  and the accepted M019 convergence surface
  (:mod:`resilience.convergence` — the R8 matrix vocabulary and the
  R8 report type the composed matrix consumes);
* ``accesstech`` (the accepted M020/M021/M022 package surface,
  relative imports) — the registration records the drills resolve, the
  handover-kind declarations whose frozen semantics the drills
  re-verify per hop;
* the composition root (the battery) mounts the accepted M007/M021/
  M022/M023 reference compositions through their OWN public mount
  factories and registers them through the accepted
  :func:`~accesstech.registry.register_access_technology` surface —
  this module consumes the registration records, never the family
  runtimes directly (LOCK-110: the mediated
  :class:`~adapters.capability.CapabilityAdapter` seam stays the only
  path onto the execution boundary).

The consumed engines' own code runs and their own gates fire on every
consumed value.  NOTHING is reimplemented, weakened, forked or
bypassed.

Authority boundaries (the layering contract, frozen 1.1):

- **LOCK-101/LOCK-117**: nothing here becomes a second contract
  authority.  The drill and replacement records ride the contract and
  the runtime journal as opaque declared data (the realization
  references are opaque execution-artifact references); the contract
  object itself is consumed THROUGH the accepted machinery's own
  isinstance gates (this module duck-checks the public surface —
  ``contract_id`` / ``hard_constraints`` /
  ``hard_constraint_fingerprint`` — and imports NO contracts type:
  the M020 zero-contract-import discipline preserved).
- **LOCK-105**: no topology facts cross — the drill's domain labels
  and class names are declared data bounded by their own declaration.
- **LOCK-106**: content-derived identities over canonical JSON for
  every record (deterministic, tamper-evident at reconstruction).
- **LOCK-108**: every interchange/replacement handover preserves the
  contract's hard-constraint set VERBATIM — structurally (the
  candidate carries the contract's own constraint objects) and
  verified (the fingerprint equality plus the consumed
  cross-authority gate on every decision); a weakening candidate can
  never enter through this surface.
- **LOCK-110/LOCK-112**: the technologies enter only through the
  accepted adapter boundary; the drill never touches a family
  runtime, never branches on a technology name.
- **LOCK-118**: every record carries its issuer and
  content-derived identity (provenance by construction).
- **LOCK-119**: no wall clock, no randomness, no network, no
  secrets (secret-shaped values are rejected typed at every
  construction boundary; injected RFC 3339 UTC instants only).

One-way imports (the R9 charter consumption rule): this module
imports the accepted authorities (``protocol``, ``replan``,
``resilience`` and the package's own accepted surface); NO accepted
authority imports this module.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from protocol.canonicalization import CanonicalizationError, canonical_json_bytes
from protocol.temporal import TemporalError, parse_instant

# BY REFERENCE: the accepted M008 trigger vocabulary (the frozen kinds
# the consumed handover machinery validates triggers against) and the
# pure cross-authority LOCK-108 gate over a finished decision record.
from replan import TRIGGER_KINDS, ReplanError, verify_decision_preserves_contract

# BY REFERENCE: the accepted M015 handover machinery (the drills' own
# drive) and the typed runtime-store surface they ride.
from resilience import (
    ResilienceError,
    ResilienceReason,
    RuntimeStore,
    handover_candidate,
    perform_handover,
)

# BY REFERENCE: the accepted M019 convergence surface — the R8 matrix
# vocabulary (itself the accepted upgrade discipline's values), the R8
# domain set and the R8 report type the composed matrix consumes.
from resilience.convergence import (
    MATRIX_VERDICTS as _R8_MATRIX_VERDICTS,
    R8_CONVERGENCE_DOMAINS,
    R8MatrixReport,
)

from .errors import AccessTechError, AccessTechReason
from .handovers import declare_handover_kind, preserved_constraint_kinds
from .registry import TechnologyRegistration, TechnologyRegistry

__all__ = [
    # frozen vocabularies
    "CONVERGENCE_ISSUER",
    "R9_CONVERGENCE_DOMAINS",
    "CROSS_DOMAINS",
    "MATRIX_VERDICTS",
    "INTERCHANGE_KIND",
    "REPLACEMENT_KIND",
    # typed records — the interchange drill
    "InterchangeHop",
    "InterchangeDrillPlan",
    "InterchangeHopResult",
    "InterchangeDrillResult",
    # typed records — the replacement drill
    "ReplacementRecord",
    # the drill engines
    "run_interchange_drill",
    "replace_technology",
    # typed records — the R9 matrix
    "R9DomainVersion",
    "R9DomainVerdict",
    "R9MatrixReport",
    "AccessConvergenceMatrix",
    # the matrix engines
    "classify_r9_domain",
    "negotiate_r9_matrix",
    "compose_access_convergence_matrix",
    # typed records — the federation-scale surface
    "AccessScaleBounds",
    "AccessScaleConvergence",
    # the federation-scale verifier
    "verify_access_scale_convergence",
]


#: The issuer recorded on convergence-surface records (LOCK-118: the
#: convergence surface asserts its own records; the contract stays the
#: sole authority).
CONVERGENCE_ISSUER = "accesstech:convergence"

#: The R9 chain-child domain labels entering the converged
#: compatibility matrix (the M024 extension set — sorted; the four
#: accepted R9 children: the M020 envelope domain, the M021 wireline
#: domain, the M022 non-terrestrial domain, the M023 future-technology
#: domain).  The R7-substrate labels stay owned by the accepted
#: ``upgrade/`` matrix (they enter the composed matrix as that
#: engine's own verdict DATA, never re-declared here); the R8 labels
#: stay owned by the accepted M019 matrix.
R9_CONVERGENCE_DOMAINS: Tuple[str, ...] = (
    "accesstech",
    "futureimt",
    "satellite",
    "wireline",
)

#: The three access-technology domains of the R9 gate objective the
#: cross-technology interchange drill crosses (sorted — declared DATA
#: labels: the M021 wireline families, the M007 radio families, the
#: M022 non-terrestrial families).
CROSS_DOMAINS: Tuple[str, ...] = (
    "non-terrestrial",
    "radio-family",
    "wireline",
)

#: The frozen domain-compatibility verdict vocabulary — the accepted
#: ``upgrade.convergence.DOMAIN_COMPATIBILITY_VERDICTS`` discipline's
#: values, extended onto the R9 labels.  The import boundary of this
#: package's accepted audit (the M020 one-way import set) forbids
#: importing ``upgrade/`` here, so the values are declared and verified
#: against the accepted M019-declared vocabulary (itself the accepted
#: discipline's values) at import time — fail loud on drift, never
#: silently mis-declared; the battery pins the full chain against the
#: accepted ``upgrade/`` engine directly.
MATRIX_VERDICTS: Tuple[str, ...] = (
    "additive-gap",
    "compatible",
    "local-missing",
    "major-mismatch",
    "peer-missing",
    "unknown-domain",
)

#: The declared handover kind every interchange hop rides (the M020
#: frozen four-kind vocabulary's cross-technology entry).
INTERCHANGE_KIND = "cross-technology"

#: The declared handover kind every technology replacement rides (the
#: M020 frozen four-kind vocabulary's replacement entry).
REPLACEMENT_KIND = "replacement"

if tuple(MATRIX_VERDICTS) != tuple(_R8_MATRIX_VERDICTS):
    raise AccessTechError(
        AccessTechReason.VOCABULARY,
        "the R9 matrix verdict vocabulary has drifted from the accepted M019 "
        "matrix vocabulary (itself the accepted upgrade discipline's values) "
        "— the convergence matrix composes over their frozen equality (fail "
        "loud, never silently mis-declared)",
    )


# ----------------------------------------------------------------------
# Internal helpers (the accepted-domain conventions, re-used)
# ----------------------------------------------------------------------

_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_RUN_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_CITATION_ID_PATTERN = re.compile(r"^m014:cite:sha256:[0-9a-f]{64}$")
_REF_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:+/-]{1,128}$")
_TECHNOLOGY_CLASS_PATTERN = re.compile(r"^[a-z][a-z0-9.-]*$")
_SECRET_NAME_PATTERN = re.compile(
    r"(secret|token|password|passwd|private[_-]?key|api[_-]?key|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERN = re.compile(r"^(ghp_|gho_|sk_|ak_|ck_|onbsec_)[A-Za-z0-9_-]+$")

_DRILL_NAMESPACE = "adcos.accesstech.convergence-drill"
_REPLACEMENT_NAMESPACE = "adcos.accesstech.convergence-replacement"
_MATRIX_NAMESPACE = "adcos.accesstech.convergence-matrix"
_SCALE_NAMESPACE = "adcos.accesstech.convergence-scale"

#: The accepted R7-substrate verdict dict members (the
#: ``upgrade.convergence.DomainCompatibilityVerdict.to_dict`` shape —
#: the composed matrix validates every substrate row against this
#: exact member set, so the accepted engine's own serialized verdicts
#: ride verbatim and nothing else does).
_SUBSTRATE_ROW_MEMBERS: Tuple[str, ...] = (
    "domain",
    "verdict",
    "local_major",
    "local_minor",
    "peer_major",
    "peer_minor",
    "detail",
)


def _canonical_bytes(document: Mapping[str, Any], label: str) -> bytes:
    try:
        return canonical_json_bytes(dict(document))
    except (CanonicalizationError, TypeError, ValueError) as error:
        raise AccessTechError(
            AccessTechReason.SERIALIZATION_INVALID,
            "%s is not canonicalizable: %s" % (label, error),
        ) from None


def _derive_id(namespace: str, document: Mapping[str, Any], label: str) -> str:
    payload = dict(document)
    payload["namespace"] = namespace
    return "sha256:" + hashlib.sha256(
        _canonical_bytes(payload, label)
    ).hexdigest()


def _reject_secret(value: object, label: str) -> None:
    """LOCK-119 guard: secret-shaped material never enters convergence data."""
    if _SECRET_NAME_PATTERN.search(label):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s looks like secret material; secrets never enter convergence "
            "data (LOCK-119)" % label,
        )
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.match(value):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s carries a secret-shaped value; secrets never enter "
            "convergence data (LOCK-119)" % label,
        )


def _require_str(
    value: object, label: str, *, pattern: Optional[re.Pattern] = None
) -> str:
    if not isinstance(value, str) or not value:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT, "%s must be a non-empty string" % label
        )
    if pattern is not None and pattern.fullmatch(value) is None:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT, "%s has an invalid format: %r" % (label, value)
        )
    _reject_secret(value, label)
    return value


def _require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s must be the content-derived identity (sha256:...)" % label,
        )
    _reject_secret(value, label)
    return value


def _require_technology_class(value: object, label: str) -> str:
    if not isinstance(value, str) or _TECHNOLOGY_CLASS_PATTERN.fullmatch(value) is None:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s must be a declared technology class (lowercase dotted "
            "grammar; found %r)" % (label, value),
        )
    _reject_secret(value, label)
    return value


def _require_instant(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT, "%s must be a non-empty instant string" % label
        )
    try:
        parse_instant(value)
    except TemporalError as error:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s %r is not an injected RFC 3339 UTC instant: %s" % (label, value, error),
        ) from None
    _reject_secret(value, label)
    return value


def _require_int(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s must be an integer >= %d (found %r)" % (label, minimum, value),
        )
    return value


def _require_in(value: object, vocabulary: Sequence[str], label: str) -> str:
    if value not in vocabulary:
        raise AccessTechError(
            AccessTechReason.VOCABULARY,
            "%s must be one of %s (found %r)" % (label, ", ".join(vocabulary), value),
        )
    return str(value)


def _duck_surface(record: object, names: Sequence[str], label: str) -> None:
    """The duck-typed composition gate (the M014/M019 cite-*
    discipline): a consumed accepted record must expose its OWN public
    surface (every named member, readable) — the accepted record's own
    code produced these values; this surface only reads them.  A
    record missing the surface fails closed typed (never a silent
    partial consumption)."""
    if record is None:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "%s requires the accepted record (got None) — the convergence "
            "surface composes the accepted surfaces by reference" % label,
        )
    for name in names:
        if not hasattr(record, name):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "%s does not expose %r — the convergence surface composes "
                "only the accepted record's own public surface (the "
                "duck-typed by-reference discipline; got %s)"
                % (label, name, type(record).__name__),
            )


def _contract_surface(contract: object) -> None:
    """The duck-typed contract gate: the drill consumes the contract
    THROUGH the accepted machinery's own isinstance gates; this surface
    pre-checks the public members the drive reads (the id, the hard
    constraint sequence, the LOCK-108 fingerprint) — never a contracts
    type import (the M020 zero-contract-import discipline)."""
    _duck_surface(
        contract,
        ("contract_id", "hard_constraints", "hard_constraint_fingerprint"),
        "the interchange/replacement contract",
    )
    _require_id(contract.contract_id, "the contract's contract_id")
    if isinstance(contract.hard_constraints, (str, bytes)) or not isinstance(
        contract.hard_constraints, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the contract's hard_constraints must be a sequence (the "
            "contract's own hard-constraint set the drill carries VERBATIM)",
        )
    if not contract.hard_constraints:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the contract carries no hard constraints — a handover drive "
            "requires the contract's own hard-constraint set (LOCK-108)",
        )
    if not callable(contract.hard_constraint_fingerprint):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the contract's hard_constraint_fingerprint must be callable "
            "(the LOCK-108 evidence convention the drill re-verifies)",
        )


def _require_kind_declared(
    registration: TechnologyRegistration, kind: str
) -> None:
    """The typed interchange/replacement-kind gate: BOTH the from- and
    the to-technology's registrations must DECLARE the handover kind
    the drive rides (the M020 frozen four-kind vocabulary, declared
    with the machinery's own frozen semantics) — a technology that
    never declared the kind never participates in that handover shape
    (fail closed, never a silent undeclared interchange)."""
    for characteristics in registration.handovers:
        if characteristics.kind == kind:
            if characteristics.preserved_constraint_kinds != preserved_constraint_kinds():
                raise AccessTechError(
                    AccessTechReason.HANDOVER_ILLEGAL,
                    "the %s handover-kind declaration of %s carries a "
                    "preserved-constraint set that is not the accepted "
                    "machinery's own frozen full-set semantics (LOCK-108: "
                    "never weakened, never re-typed)"
                    % (kind, registration.technology_class),
                )
            if characteristics.explicit_reconnect is not True:
                raise AccessTechError(
                    AccessTechReason.HANDOVER_ILLEGAL,
                    "the %s handover-kind declaration of %s declares a "
                    "silent reference swap — the WORK-012 discipline the "
                    "accepted machinery enforces is mandatory"
                    % (kind, registration.technology_class),
                )
            if characteristics.contract_continuity is not True:
                raise AccessTechError(
                    AccessTechReason.HANDOVER_ILLEGAL,
                    "the %s handover-kind declaration of %s declares "
                    "contract-breaking semantics — LOCK-101/LOCK-117: a "
                    "handover realizes the SAME contract"
                    % (kind, registration.technology_class),
                )
            return
    raise AccessTechError(
        AccessTechReason.HANDOVER_ILLEGAL,
        "technology class %s does not declare the %r handover kind (the "
        "declared kinds: %s) — an undeclared handover shape never "
        "participates (fail closed, never a silent undeclared interchange)"
        % (
            registration.technology_class,
            kind,
            ", ".join(sorted(item.kind for item in registration.handovers)),
        ),
    )


def _wrap_resilience(error: ResilienceError, drive: str) -> AccessTechError:
    """Exception isolation: the consumed machinery's typed rejection
    surfaces on this domain's vocabulary with its deterministic text
    preserved (never a raw consumer exception leaking)."""
    return AccessTechError(
        AccessTechReason.HANDOVER_ILLEGAL,
        "the accepted resilience handover machinery rejected the %s drive: "
        "%s" % (drive, error.detail),
    )


# ----------------------------------------------------------------------
# The cross-technology interchange drill (the deterministic plan)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class InterchangeHop:
    """One declared interchange hop: a deterministic technology
    handover from one access-technology domain to another (the new
    realization's references and reconnect instant are declared data —
    LOCK-117: opaque execution-artifact references, never constraint
    material, never a topology claim).

    Fail-closed declaration discipline (typed rejections): the domains
    are declared cross domains and the hop CROSSES them (``wireline``
    -> ``radio-family`` -> ``non-terrestrial`` — an intra-domain hop is
    the access-internal shape, a different drill); the technology
    classes carry the declared grammar; the new realization references
    and the reconnect instant are non-empty declared values (injected
    instants only — never wall clock).
    """

    position: int
    from_domain: str
    to_domain: str
    from_class: str
    to_class: str
    new_route_decision_id: str
    new_path_id: str
    reconnect_instant: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "position", _require_int(self.position, "hop.position")
        )
        object.__setattr__(
            self,
            "from_domain",
            _require_in(self.from_domain, CROSS_DOMAINS, "hop.from_domain"),
        )
        object.__setattr__(
            self, "to_domain", _require_in(self.to_domain, CROSS_DOMAINS, "hop.to_domain")
        )
        if self.from_domain == self.to_domain:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "interchange hop %d stays inside the %s domain — the "
                "interchange drill CROSSES technology domains (an "
                "intra-domain hop is the access-internal shape, a "
                "different drill)" % (self.position, self.from_domain),
            )
        object.__setattr__(
            self,
            "from_class",
            _require_technology_class(self.from_class, "hop.from_class"),
        )
        object.__setattr__(
            self,
            "to_class",
            _require_technology_class(self.to_class, "hop.to_class"),
        )
        object.__setattr__(
            self,
            "new_route_decision_id",
            _require_str(
                self.new_route_decision_id,
                "hop.new_route_decision_id",
                pattern=_REF_VALUE_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "new_path_id",
            _require_str(self.new_path_id, "hop.new_path_id", pattern=_REF_VALUE_PATTERN),
        )
        object.__setattr__(
            self,
            "reconnect_instant",
            _require_instant(self.reconnect_instant, "hop.reconnect_instant"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "from_domain": self.from_domain,
            "to_domain": self.to_domain,
            "from_class": self.from_class,
            "to_class": self.to_class,
            "new_route_decision_id": self.new_route_decision_id,
            "new_path_id": self.new_path_id,
            "reconnect_instant": self.reconnect_instant,
        }


@dataclass(frozen=True)
class InterchangeDrillPlan:
    """The deterministic, replayable cross-technology interchange drill
    plan: the ordered hop sequence crossing the three access-technology
    domains of the R9 gate objective.

    Plan discipline (typed rejections, fail closed):

    * at least TWO hops (a single hop exercises one boundary; the
      interchange drill crosses the full domain set);
    * every declared cross domain is COVERED by the hop sequence (the
      drill exercises the wireline, radio-family and non-terrestrial
      domains — the gate objective's own surface);
    * positions ascend deterministically 0..n-1;
    * consecutive hops CHAIN (hop[i].to_class == hop[i+1].from_class
      and hop[i].to_domain == hop[i+1].from_domain — the realization
      walks exactly the declared technology chain);
    * the reconnect instants strictly increase (a deterministic
      replayable operation sequence — never wall clock);
    * the trigger kind is a member of the consumed M008 frozen
      vocabulary (``replan.TRIGGER_KINDS``);
    * ``drill_id`` is content-derived over the full declared core
      (LOCK-106; tamper-evident at reconstruction).
    """

    contract_id: str
    runtime_id: str
    trigger_kind: str
    hops: Tuple[InterchangeHop, ...]
    drill_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "drill.contract_id")
        )
        object.__setattr__(
            self, "runtime_id", _require_id(self.runtime_id, "drill.runtime_id")
        )
        object.__setattr__(
            self,
            "trigger_kind",
            _require_in(self.trigger_kind, TRIGGER_KINDS, "drill.trigger_kind"),
        )
        if isinstance(self.hops, (str, bytes)) or not isinstance(
            self.hops, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the interchange drill plan requires a sequence of "
                "InterchangeHop records",
            )
        hops: List[InterchangeHop] = []
        for index, item in enumerate(self.hops):
            if not isinstance(item, InterchangeHop):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "drill hop %d must be an InterchangeHop record (got %s)"
                    % (index, type(item).__name__),
                )
            hops.append(item)
        hops_tuple = tuple(hops)
        if len(hops_tuple) < 2:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "the interchange drill plan carries %d hop(s) — the drill "
                "crosses the full domain set (at least two hops)"
                % len(hops_tuple),
            )
        for position, hop in enumerate(hops_tuple):
            if hop.position != position:
                raise AccessTechError(
                    AccessTechReason.ENVELOPE_INCONSISTENT,
                    "interchange hop positions are disordered (hop %d "
                    "declares position %d — deterministic plans carry "
                    "ascending 0..n-1 positions)" % (position, hop.position),
                )
        covered = {hop.from_domain for hop in hops_tuple} | {
            hop.to_domain for hop in hops_tuple
        }
        missing = sorted(set(CROSS_DOMAINS) - covered)
        if missing:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_INCONSISTENT,
                "the interchange drill plan does not cover the cross "
                "domains %s (the drill crosses the full domain set — "
                "wireline, radio-family and non-terrestrial)"
                % ", ".join(missing),
            )
        for index in range(len(hops_tuple) - 1):
            current, following = hops_tuple[index], hops_tuple[index + 1]
            if current.to_class != following.from_class:
                raise AccessTechError(
                    AccessTechReason.ENVELOPE_INCONSISTENT,
                    "interchange hops %d and %d do not chain (the "
                    "realization walks exactly the declared technology "
                    "chain: %s then %s)"
                    % (index, index + 1, current.to_class, following.from_class),
                )
            if current.to_domain != following.from_domain:
                raise AccessTechError(
                    AccessTechReason.ENVELOPE_INCONSISTENT,
                    "interchange hops %d and %d do not chain across domains "
                    "(%s then %s)"
                    % (index, index + 1, current.to_domain, following.from_domain),
                )
            if parse_instant(following.reconnect_instant) <= parse_instant(
                current.reconnect_instant
            ):
                raise AccessTechError(
                    AccessTechReason.ENVELOPE_INCONSISTENT,
                    "the interchange hops' reconnect instants are not "
                    "strictly increasing (hop %d at %s, hop %d at %s) — the "
                    "drill is a deterministic replayable operation sequence"
                    % (
                        index,
                        current.reconnect_instant,
                        index + 1,
                        following.reconnect_instant,
                    ),
                )
        object.__setattr__(self, "hops", hops_tuple)
        expected = _derive_id(
            _DRILL_NAMESPACE, self._core_document(), "the interchange drill plan"
        )
        if not isinstance(self.drill_id, str) or not self.drill_id:
            object.__setattr__(self, "drill_id", expected)
        elif self.drill_id != expected:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "drill_id does not match the content-derived identity "
                "(tamper evidence): declared %s, derived %s"
                % (self.drill_id, expected),
            )

    def _core_document(self) -> Dict[str, Any]:
        return {
            "kind": "adcos.accesstech.convergence-drill",
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "trigger_kind": self.trigger_kind,
            "hops": [hop.to_dict() for hop in self.hops],
        }

    def content_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "trigger_kind": self.trigger_kind,
            "hops": [hop.to_dict() for hop in self.hops],
            "drill_id": self.drill_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(
            self.content_dict(), "the interchange drill plan"
        )


# ----------------------------------------------------------------------
# The interchange drill result (typed, canonical, evidence-visible)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class InterchangeHopResult:
    """The typed outcome of ONE interchange hop: the LOCK-108 evidence
    (the decision id and the contract's own constraint fingerprint the
    machinery recorded), the WORK-012 explicit reconnect pair (BOTH the
    old AND the new realization references, with the declared
    reconnect instant), the journal event ids of the reconnect pair,
    and the landed session state — every member derived from the
    accepted machinery's own records (never re-computed here)."""

    position: int
    from_domain: str
    to_domain: str
    from_class: str
    to_class: str
    decision_id: str
    constraint_fingerprint: str
    old_route_decision_id: str
    new_route_decision_id: str
    old_path_id: str
    new_path_id: str
    reconnect_instant: str
    event_ids: Tuple[str, ...]
    state_after: str
    # The LIVE consumed decision record, held BY REFERENCE (the M020
    # registry live-objects discipline: the identity-bearing canonical
    # content serializes; the live in-memory object never does — it is
    # not serializable state, never a persisted authority).  The
    # composition root reads it through :meth:`live_decision` (e.g. to
    # cite the drill material through the accepted federation
    # constructors); the canonical ``to_dict`` projection excludes it.
    _decision: object = None

    @property
    def live_decision(self) -> object:
        """The LIVE :class:`replan.ReplanDecision` the accepted
        machinery produced for this hop (identity-preserving, by
        reference — never serialized, never re-created here)."""
        if self._decision is None:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the hop result carries no live decision record (the live "
                "objects ride only the drive-time construction, never the "
                "reconstructed canonical material)",
            )
        return self._decision

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": self.position,
            "from_domain": self.from_domain,
            "to_domain": self.to_domain,
            "from_class": self.from_class,
            "to_class": self.to_class,
            "decision_id": self.decision_id,
            "constraint_fingerprint": self.constraint_fingerprint,
            "old_route_decision_id": self.old_route_decision_id,
            "new_route_decision_id": self.new_route_decision_id,
            "old_path_id": self.old_path_id,
            "new_path_id": self.new_path_id,
            "reconnect_instant": self.reconnect_instant,
            "event_ids": list(self.event_ids),
            "state_after": self.state_after,
        }


@dataclass(frozen=True)
class InterchangeDrillResult:
    """The typed outcome of the WHOLE interchange drill: the plan's
    identity plus every hop's evidence-visible result, with a
    content-derived drill-result identity over the composed core
    (LOCK-106; canonical-JSON serializable, tamper-evident)."""

    drill_id: str
    contract_id: str
    runtime_id: str
    trigger_kind: str
    hop_results: Tuple[InterchangeHopResult, ...]
    lock108_verified: bool
    drill_result_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "drill_id", _require_id(self.drill_id, "result.drill_id")
        )
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "result.contract_id")
        )
        object.__setattr__(
            self, "runtime_id", _require_id(self.runtime_id, "result.runtime_id")
        )
        object.__setattr__(
            self,
            "trigger_kind",
            _require_in(self.trigger_kind, TRIGGER_KINDS, "result.trigger_kind"),
        )
        if isinstance(self.hop_results, (str, bytes)) or not isinstance(
            self.hop_results, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the drill result requires a sequence of "
                "InterchangeHopResult records",
            )
        results: List[InterchangeHopResult] = []
        for index, item in enumerate(self.hop_results):
            if not isinstance(item, InterchangeHopResult):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "drill hop result %d must be an InterchangeHopResult "
                    "record (got %s)" % (index, type(item).__name__),
                )
            results.append(item)
        if not results:
            raise AccessTechError(
                AccessTechReason.ENVELOPE_DEGENERATE,
                "the drill result carries no hop results",
            )
        object.__setattr__(self, "hop_results", tuple(results))
        if self.lock108_verified is not True:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the drill result asserts LOCK-108 verification that did "
                "not happen (evidence honesty — never a fabricated pass)",
            )
        expected = self._derive_result_id()
        if not isinstance(self.drill_result_id, str) or not self.drill_result_id:
            object.__setattr__(self, "drill_result_id", expected)
        elif self.drill_result_id != expected:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "drill_result_id does not match the content-derived "
                "identity (tamper evidence): declared %s, derived %s"
                % (self.drill_result_id, expected),
            )

    def _derive_result_id(self) -> str:
        document = {
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "trigger_kind": self.trigger_kind,
            "hops": [hop.to_dict() for hop in self.hop_results],
            "lock108_verified": True,
        }
        return _derive_id(_DRILL_NAMESPACE, document, "the drill result")

    def content_dict(self) -> Dict[str, Any]:
        return {
            "drill_id": self.drill_id,
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "trigger_kind": self.trigger_kind,
            "hop_results": [hop.to_dict() for hop in self.hop_results],
            "lock108_verified": self.lock108_verified,
            "drill_result_id": self.drill_result_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.content_dict(), "the drill result")


# ----------------------------------------------------------------------
# The interchange drill engine (the accepted machinery, BY REFERENCE)
# ----------------------------------------------------------------------


def run_interchange_drill(
    plan: InterchangeDrillPlan,
    registry: TechnologyRegistry,
    store: RuntimeStore,
    contract: object,
    runtime_id: object,
) -> InterchangeDrillResult:
    """Run the deterministic cross-technology interchange drill: every
    hop's handover is driven through the ACCEPTED
    :func:`resilience.handover.perform_handover` machinery with the
    contract's OWN hard constraints carried VERBATIM (LOCK-108 — the
    candidate is constructed through the accepted
    :func:`resilience.handover.handover_candidate` with
    ``tuple(contract.hard_constraints)``, so a weakened candidate can
    never enter through this surface), and every decision is re-checked
    through the consumed cross-authority gate
    :func:`replan.verify_decision_preserves_contract` plus the
    fingerprint equality with the contract's own.

    Per hop, all fail-closed typed (the consumed machinery's
    rejections surface on this domain's vocabulary with their
    deterministic text preserved):

    1. both endpoint technology classes are REGISTERED (through the
       accepted registry — an unregistered class is the registry's own
       typed rejection) and both registrations DECLARE the
       ``cross-technology`` handover kind with the machinery's own
       frozen semantics;
    2. the machinery adopts the hop (an impossible handover surfaces
       typed — the machinery's own EXPLICIT degraded/failed state is
       probed at the battery seam, never absorbed here);
    3. LOCK-108: the decision's constraint fingerprint IS the
       contract's own and the consumed cross-authority gate passes;
    4. WORK-012: the EXPLICIT reconnect pair names BOTH the old AND
       the new references, at the hop's declared reconnect instant
       (a missing or one-sided reconnect is the typed silent-swap
       rejection — never a silent swap);
    5. the session lands ACTIVE on the hop's new realization
       references.

    The contract object is consumed through the machinery's own
    isinstance gates (this surface duck-checks the public members
    only — no contracts type is imported).
    """
    if not isinstance(plan, InterchangeDrillPlan):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "run_interchange_drill requires an InterchangeDrillPlan (got %s)"
            % type(plan).__name__,
        )
    if not isinstance(registry, TechnologyRegistry):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "run_interchange_drill requires an accesstech "
            "TechnologyRegistry (got %s)" % type(registry).__name__,
        )
    if not isinstance(store, RuntimeStore):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "run_interchange_drill requires a resilience RuntimeStore (got %s)"
            % type(store).__name__,
        )
    _contract_surface(contract)
    session = store.session(runtime_id)
    if session.contract_id != plan.contract_id:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "runtime session %s rides contract %s, not %s — the drill "
            "realizes exactly its owning contract (LOCK-101/LOCK-117)"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                plan.contract_id[:23],
            ),
        )
    if contract.contract_id != plan.contract_id:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the drill plan names contract %s but the supplied contract is "
            "%s — the drill realizes exactly its declared contract"
            % (plan.contract_id[:23], contract.contract_id[:23]),
        )
    if session.state not in ("ACTIVE", "RECONNECTING", "DEGRADED"):
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "runtime session %s is %s — the interchange drill drives a "
            "reconnectable realization (PENDING is not established and "
            "terminal states never transition)"
            % (session.runtime_id[:23], session.state),
        )
    fingerprint = contract.hard_constraint_fingerprint()
    current_route = session.route_decision_id
    current_path = session.path_id
    hop_results: List[InterchangeHopResult] = []
    for hop in plan.hops:
        old_registration = registry.lookup(hop.from_class)
        new_registration = registry.lookup(hop.to_class)
        _require_kind_declared(old_registration, INTERCHANGE_KIND)
        _require_kind_declared(new_registration, INTERCHANGE_KIND)
        try:
            candidate = handover_candidate(
                contract,
                route_decision_id=hop.new_route_decision_id,
                path_id=hop.new_path_id,
                hard_constraints=tuple(contract.hard_constraints),
            )
            drive = perform_handover(
                store,
                runtime_id,
                contract,
                (candidate,),
                trigger_kind=plan.trigger_kind,
                recorded_at=hop.reconnect_instant,
            )
        except ResilienceError as error:
            raise _wrap_resilience(error, "interchange hop %d" % hop.position) from None
        decision = drive.decision
        if decision.decision != "adopt-alternative":
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "interchange hop %d (%s -> %s) was not adopted (the "
                "machinery decided %r) — the deterministic drill plan "
                "requires adoption at every step; the machinery's own "
                "EXPLICIT degraded/failed state stays the honest outcome, "
                "never absorbed here"
                % (hop.position, hop.from_class, hop.to_class, decision.decision),
            )
        if decision.constraint_fingerprint != fingerprint:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "the interchange hop %d decision's LOCK-108 constraint "
                "fingerprint is not the contract's own (verbatim equality "
                "across every technology handover — tampered or forged "
                "decision material fails closed)" % hop.position,
            )
        try:
            verify_decision_preserves_contract(decision, contract)
        except ReplanError as error:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "the consumed cross-authority LOCK-108 gate rejected the "
                "interchange hop %d decision: %s" % (hop.position, error.detail),
            ) from None
        reconnect = drive.reconnect
        if reconnect is None:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "interchange hop %d produced no reconnect evidence — every "
                "interchange handover is an EXPLICIT recorded reconnect "
                "naming BOTH the old AND the new references (the WORK-012 "
                "discipline; never a silent swap)" % hop.position,
            )
        if reconnect.old_route_decision_id != current_route:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the interchange hop %d reconnect lost the OLD realization "
                "reference (recorded %r, the live realization was %r)"
                % (hop.position, reconnect.old_route_decision_id, current_route),
            )
        if reconnect.old_path_id != current_path:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the interchange hop %d reconnect lost the OLD path "
                "reference (recorded %r, the live realization was %r)"
                % (hop.position, reconnect.old_path_id, current_path),
            )
        if reconnect.new_route_decision_id != hop.new_route_decision_id:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the interchange hop %d reconnect lost the NEW realization "
                "reference (recorded %r, the hop declared %r)"
                % (
                    hop.position,
                    reconnect.new_route_decision_id,
                    hop.new_route_decision_id,
                ),
            )
        if reconnect.new_path_id != hop.new_path_id:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the interchange hop %d reconnect lost the NEW path "
                "reference (recorded %r, the hop declared %r)"
                % (hop.position, reconnect.new_path_id, hop.new_path_id),
            )
        if reconnect.reconnect_instant != hop.reconnect_instant:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the interchange hop %d reconnect instant is not the "
                "declared instant (recorded %r, declared %r)"
                % (hop.position, reconnect.reconnect_instant, hop.reconnect_instant),
            )
        after = drive.session
        if after.state != "ACTIVE":
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the adopted interchange hop %d did not land ACTIVE (%s)"
                % (hop.position, after.state),
            )
        if (after.route_decision_id, after.path_id) != (
            hop.new_route_decision_id,
            hop.new_path_id,
        ):
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the adopted interchange hop %d did not land on the new "
                "realization references" % hop.position,
            )
        hop_results.append(
            InterchangeHopResult(
                position=hop.position,
                from_domain=hop.from_domain,
                to_domain=hop.to_domain,
                from_class=hop.from_class,
                to_class=hop.to_class,
                decision_id=decision.decision_id,
                constraint_fingerprint=decision.constraint_fingerprint,
                old_route_decision_id=reconnect.old_route_decision_id,
                new_route_decision_id=reconnect.new_route_decision_id,
                old_path_id=reconnect.old_path_id,
                new_path_id=reconnect.new_path_id,
                reconnect_instant=reconnect.reconnect_instant,
                event_ids=tuple(drive.event_ids),
                state_after=after.state,
                _decision=decision,
            )
        )
        current_route = hop.new_route_decision_id
        current_path = hop.new_path_id
    return InterchangeDrillResult(
        drill_id=plan.drill_id,
        contract_id=plan.contract_id,
        runtime_id=plan.runtime_id,
        trigger_kind=plan.trigger_kind,
        hop_results=tuple(hop_results),
        lock108_verified=True,
    )


# ----------------------------------------------------------------------
# The technology REPLACEMENT drill (the "or replace" half)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ReplacementRecord:
    """The typed record of ONE technology replacement: a LIVE
    technology (the old realization the runtime session held) replaced
    by ANOTHER technology under an ACTIVE contract with CONTRACT
    CONTINUITY — every replacement an EXPLICIT recorded reconnect
    naming BOTH the old AND the new references (the WORK-012
    discipline the accepted machinery enforces mechanically; this
    record carries the pair's own members, never re-computed).

    Fail-closed construction discipline (typed rejections): the old
    and new technology classes are declared classes that DIFFER (a
    replacement that changes nothing is not a replacement); the
    realization references and reconnect instant are declared values
    (injected instants only); the reconnect members are ALL present (a
    record missing either side of the pair is the typed silent-swap
    rejection); the contract continuity member is TRUE (the
    replacement realized the SAME contract — LOCK-101/LOCK-117); the
    LOCK-108 fingerprint is the contract's own; ``replacement_id`` is
    content-derived over the full core (LOCK-106; tamper-evident at
    reconstruction)."""

    contract_id: str
    runtime_id: str
    old_class: str
    new_class: str
    old_route_decision_id: str
    old_path_id: str
    new_route_decision_id: str
    new_path_id: str
    reconnect_instant: str
    decision_id: str
    constraint_fingerprint: str
    state_after: str
    contract_continuity: bool
    # The LIVE consumed decision record, held BY REFERENCE (the M020
    # registry live-objects discipline — excluded from the canonical
    # projection; read through :meth:`live_decision`).
    _decision: object = None
    replacement_id: str = ""

    @property
    def live_decision(self) -> object:
        """The LIVE :class:`replan.ReplanDecision` the accepted
        machinery produced for this replacement (identity-preserving,
        by reference — never serialized, never re-created here)."""
        if self._decision is None:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the replacement record carries no live decision record "
                "(the live objects ride only the drive-time construction, "
                "never the reconstructed canonical material)",
            )
        return self._decision

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_id", _require_id(self.contract_id, "replacement.contract_id")
        )
        object.__setattr__(
            self, "runtime_id", _require_id(self.runtime_id, "replacement.runtime_id")
        )
        object.__setattr__(
            self,
            "old_class",
            _require_technology_class(self.old_class, "replacement.old_class"),
        )
        object.__setattr__(
            self,
            "new_class",
            _require_technology_class(self.new_class, "replacement.new_class"),
        )
        if self.old_class == self.new_class:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the replacement of %s by itself changes nothing — a "
                "technology replacement replaces the live technology with "
                "ANOTHER technology (the 'or replace' half of the gate "
                "objective; never a no-op swap)" % self.old_class,
            )
        for label, value in (
            ("old_route_decision_id", self.old_route_decision_id),
            ("old_path_id", self.old_path_id),
            ("new_route_decision_id", self.new_route_decision_id),
            ("new_path_id", self.new_path_id),
        ):
            object.__setattr__(
                self, label, _require_str(value, "replacement.%s" % label,
                                          pattern=_REF_VALUE_PATTERN)
            )
        # the WORK-012 discipline, enforced at the record boundary: a
        # replacement record missing EITHER side of the reconnect pair
        # is a silent swap and fails closed (the reason cites the
        # discipline itself)
        missing = [
            label
            for label, value in (
                ("old_route_decision_id", self.old_route_decision_id),
                ("new_route_decision_id", self.new_route_decision_id),
                ("old_path_id", self.old_path_id),
                ("new_path_id", self.new_path_id),
            )
            if not isinstance(value, str) or not value
        ]
        if missing:
            raise AccessTechError(  # pragma: no cover - guarded above
                AccessTechReason.HANDOVER_ILLEGAL,
                "the replacement record is missing the reconnect members "
                "%s (the WORK-012 discipline requires BOTH the old AND the "
                "new references on every replacement — a replacement is "
                "never a silent swap)" % ", ".join(sorted(missing)),
            )
        object.__setattr__(
            self,
            "reconnect_instant",
            _require_instant(self.reconnect_instant, "replacement.reconnect_instant"),
        )
        object.__setattr__(
            self, "decision_id", _require_id(self.decision_id, "replacement.decision_id")
        )
        object.__setattr__(
            self,
            "constraint_fingerprint",
            _require_str(
                self.constraint_fingerprint,
                "replacement.constraint_fingerprint",
                pattern=_RUN_DIGEST_PATTERN,
            ),
        )
        object.__setattr__(
            self,
            "state_after",
            _require_str(self.state_after, "replacement.state_after"),
        )
        if self.contract_continuity is not True:
            raise AccessTechError(
                AccessTechReason.HANDOVER_ILLEGAL,
                "the replacement record declares contract-breaking "
                "semantics — LOCK-101/LOCK-117: a replacement realizes the "
                "SAME contract under continuity (the successor-contract "
                "path is explicit renegotiation, a distinct mechanism)",
            )
        expected = self._derive_replacement_id()
        if not isinstance(self.replacement_id, str) or not self.replacement_id:
            object.__setattr__(self, "replacement_id", expected)
        elif self.replacement_id != expected:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "replacement_id does not match the content-derived identity "
                "(tamper evidence): declared %s, derived %s"
                % (self.replacement_id, expected),
            )

    def _derive_replacement_id(self) -> str:
        document = {
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "old_class": self.old_class,
            "new_class": self.new_class,
            "old_route_decision_id": self.old_route_decision_id,
            "old_path_id": self.old_path_id,
            "new_route_decision_id": self.new_route_decision_id,
            "new_path_id": self.new_path_id,
            "reconnect_instant": self.reconnect_instant,
            "decision_id": self.decision_id,
            "constraint_fingerprint": self.constraint_fingerprint,
            "state_after": self.state_after,
            "contract_continuity": True,
        }
        return _derive_id(_REPLACEMENT_NAMESPACE, document, "the replacement record")

    def content_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "runtime_id": self.runtime_id,
            "old_class": self.old_class,
            "new_class": self.new_class,
            "old_route_decision_id": self.old_route_decision_id,
            "old_path_id": self.old_path_id,
            "new_route_decision_id": self.new_route_decision_id,
            "new_path_id": self.new_path_id,
            "reconnect_instant": self.reconnect_instant,
            "decision_id": self.decision_id,
            "constraint_fingerprint": self.constraint_fingerprint,
            "state_after": self.state_after,
            "contract_continuity": self.contract_continuity,
            "replacement_id": self.replacement_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.content_dict()

    def to_canonical_bytes(self) -> bytes:
        return _canonical_bytes(
            self.content_dict(), "the replacement record"
        )


def replace_technology(
    registry: TechnologyRegistry,
    store: RuntimeStore,
    runtime_id: object,
    contract: object,
    *,
    old_class: str,
    new_class: str,
    new_route_decision_id: str,
    new_path_id: str,
    reconnect_instant: str,
    trigger_kind: str = "route-expiry",
) -> ReplacementRecord:
    """Replace a LIVE technology by ANOTHER technology under an ACTIVE
    contract with contract continuity — the "or replace" half of the
    R9 gate objective.

    The drive is the ACCEPTED machinery (the same
    :func:`resilience.handover.perform_handover` surface, the
    contract's OWN hard constraints carried VERBATIM — LOCK-108), and
    the replacement is recorded as an EXPLICIT reconnect naming BOTH
    the old AND the new references (the WORK-012 discipline the
    machinery's journal enforces mechanically; this surface verifies
    the pair and types the record).  Fail-closed typed gates: both
    classes registered and both declaring the ``replacement`` handover
    kind with the machinery's frozen semantics; the old and new
    classes differ; the session is a live realization on the supplied
    contract; the adoption, the fingerprint equality, the consumed
    cross-authority gate, the reconnect pair (old refs == the LIVE
    realization, new refs == the declared replacement refs, the
    declared instant) and the ACTIVE landing all verified; the
    contract continuity re-asserted from the session record (the
    session realizes the SAME contract before and after — the contract
    core is never touched).
    """
    if not isinstance(registry, TechnologyRegistry):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "replace_technology requires an accesstech TechnologyRegistry "
            "(got %s)" % type(registry).__name__,
        )
    if not isinstance(store, RuntimeStore):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "replace_technology requires a resilience RuntimeStore (got %s)"
            % type(store).__name__,
        )
    _contract_surface(contract)
    if old_class == new_class:
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the replacement of %s by itself changes nothing — a "
            "technology replacement replaces the live technology with "
            "ANOTHER technology" % old_class,
        )
    _require_technology_class(old_class, "the replacement old_class")
    _require_technology_class(new_class, "the replacement new_class")
    old_registration = registry.lookup(old_class)
    new_registration = registry.lookup(new_class)
    _require_kind_declared(old_registration, REPLACEMENT_KIND)
    _require_kind_declared(new_registration, REPLACEMENT_KIND)
    new_route = _require_str(
        new_route_decision_id,
        "the replacement new_route_decision_id",
        pattern=_REF_VALUE_PATTERN,
    )
    new_path = _require_str(
        new_path_id, "the replacement new_path_id", pattern=_REF_VALUE_PATTERN
    )
    instant = _require_instant(reconnect_instant, "the replacement reconnect_instant")
    kind = _require_in(trigger_kind, TRIGGER_KINDS, "the replacement trigger_kind")
    session = store.session(runtime_id)
    if session.contract_id != contract.contract_id:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "runtime session %s rides contract %s, not %s — the "
            "replacement realizes exactly its owning contract (contract "
            "continuity, LOCK-101/LOCK-117)"
            % (
                session.runtime_id[:23],
                session.contract_id[:23],
                contract.contract_id[:23],
            ),
        )
    if session.state not in ("ACTIVE", "RECONNECTING", "DEGRADED"):
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "runtime session %s is %s — a replacement replaces a LIVE "
            "realization (PENDING is not established and terminal states "
            "never transition)" % (session.runtime_id[:23], session.state),
        )
    old_route = session.route_decision_id
    old_path = session.path_id
    if not old_route or not old_path:
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "runtime session %s carries no live realization references — "
            "a replacement replaces a LIVE technology realization"
            % session.runtime_id[:23],
        )
    fingerprint = contract.hard_constraint_fingerprint()
    try:
        candidate = handover_candidate(
            contract,
            route_decision_id=new_route,
            path_id=new_path,
            hard_constraints=tuple(contract.hard_constraints),
        )
        drive = perform_handover(
            store,
            runtime_id,
            contract,
            (candidate,),
            trigger_kind=kind,
            recorded_at=instant,
        )
    except ResilienceError as error:
        raise _wrap_resilience(error, "technology replacement") from None
    decision = drive.decision
    if decision.decision != "adopt-alternative":
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the %s -> %s replacement was not adopted (the machinery "
            "decided %r) — the machinery's own EXPLICIT degraded/failed "
            "state stays the honest outcome, never absorbed here"
            % (old_class, new_class, decision.decision),
        )
    if decision.constraint_fingerprint != fingerprint:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the replacement decision's LOCK-108 constraint fingerprint is "
            "not the contract's own (verbatim equality across the "
            "replacement — tampered or forged decision material fails "
            "closed)",
        )
    try:
        verify_decision_preserves_contract(decision, contract)
    except ReplanError as error:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the consumed cross-authority LOCK-108 gate rejected the "
            "replacement decision: %s" % error.detail,
        ) from None
    reconnect = drive.reconnect
    if reconnect is None:
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the replacement produced no reconnect evidence — every "
            "replacement is an EXPLICIT recorded reconnect naming BOTH "
            "the old AND the new references (the WORK-012 discipline; "
            "never a silent swap)",
        )
    if (reconnect.old_route_decision_id, reconnect.old_path_id) != (
        old_route,
        old_path,
    ):
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the replacement reconnect lost the OLD references (recorded "
            "%r/%r, the live realization was %r/%r)"
            % (
                reconnect.old_route_decision_id,
                reconnect.old_path_id,
                old_route,
                old_path,
            ),
        )
    if (reconnect.new_route_decision_id, reconnect.new_path_id) != (
        new_route,
        new_path,
    ):
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the replacement reconnect lost the NEW references (recorded "
            "%r/%r, the replacement declared %r/%r)"
            % (
                reconnect.new_route_decision_id,
                reconnect.new_path_id,
                new_route,
                new_path,
            ),
        )
    if reconnect.reconnect_instant != instant:
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the replacement reconnect instant is not the declared instant "
            "(recorded %r, declared %r)"
            % (reconnect.reconnect_instant, instant),
        )
    after = drive.session
    if after.state != "ACTIVE":
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the adopted replacement did not land ACTIVE (%s)" % after.state,
        )
    if (after.route_decision_id, after.path_id) != (new_route, new_path):
        raise AccessTechError(
            AccessTechReason.HANDOVER_ILLEGAL,
            "the adopted replacement did not land on the new realization "
            "references",
        )
    if after.contract_id != contract.contract_id:
        raise AccessTechError(  # pragma: no cover - machinery-guaranteed
            AccessTechReason.IDENTITY_MISMATCH,
            "the replacement broke contract continuity (the session "
            "realizes %s after the replacement, not the owning contract "
            "%s) — LOCK-101/LOCK-117" % (after.contract_id, contract.contract_id),
        )
    return ReplacementRecord(
        contract_id=contract.contract_id,
        runtime_id=after.runtime_id,
        old_class=old_class,
        new_class=new_class,
        old_route_decision_id=old_route,
        old_path_id=old_path,
        new_route_decision_id=new_route,
        new_path_id=new_path,
        reconnect_instant=instant,
        decision_id=decision.decision_id,
        constraint_fingerprint=decision.constraint_fingerprint,
        state_after=after.state,
        contract_continuity=True,
        _decision=decision,
    )


# ----------------------------------------------------------------------
# The R9 convergence-domain compatibility matrix (the accepted
# upgrade/ matrix discipline, extended)
# ----------------------------------------------------------------------


def _require_r9_domain(value: object, label: str) -> str:
    if not isinstance(value, str) or value not in R9_CONVERGENCE_DOMAINS:
        raise AccessTechError(
            AccessTechReason.VOCABULARY,
            "%s %r is outside the frozen R9 convergence domain set %s (the "
            "R7-substrate labels stay owned by the accepted upgrade/ "
            "matrix; the R8 labels by the accepted M019 matrix — fail "
            "closed)" % (label, value, list(R9_CONVERGENCE_DOMAINS)),
        )
    return value


@dataclass(frozen=True)
class R9DomainVersion:
    """One R9 convergence domain's implementation version point (the
    accepted ``upgrade.convergence.DomainVersion`` grammar extended
    onto the R9 labels: the frozen additive-evolution ``MAJOR.MINOR`` —
    each side speaks every minor up to its head)."""

    domain: str
    major: int
    minor: int

    def __post_init__(self) -> None:
        _require_r9_domain(self.domain, "the domain version domain")
        for label, value in (("major", self.major), ("minor", self.minor)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "the domain version %s must be an int >= 0 (found %r)"
                    % (label, value),
                )

    def to_dict(self) -> Dict[str, object]:
        return {"domain": self.domain, "major": self.major, "minor": self.minor}


@dataclass(frozen=True)
class R9DomainVerdict:
    """One typed per-domain coexistence verdict on the R9 matrix (the
    accepted ``upgrade.convergence.DomainCompatibilityVerdict`` shape —
    the same serialized members — so the composed matrix digests
    uniformly over the R7-substrate rows, the R8 rows and the R9
    extension rows)."""

    domain: str
    verdict: str
    local_major: int
    local_minor: int
    peer_major: int
    peer_minor: int
    detail: str = ""

    def __post_init__(self) -> None:
        _require_r9_domain(self.domain, "the verdict domain")
        _require_in(self.verdict, MATRIX_VERDICTS, "the verdict")
        for label, value in (
            ("local_major", self.local_major),
            ("local_minor", self.local_minor),
            ("peer_major", self.peer_major),
            ("peer_minor", self.peer_minor),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < -1:
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "the verdict %s must be an int >= -1 (the -1 marks a "
                    "missing side; found %r)" % (label, value),
                )
        if isinstance(self.detail, str) and len(self.detail) > 240:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the verdict detail is bounded (240 characters maximum)",
            )

    def to_dict(self) -> Dict[str, object]:
        return {
            "domain": self.domain,
            "verdict": self.verdict,
            "local_major": self.local_major,
            "local_minor": self.local_minor,
            "peer_major": self.peer_major,
            "peer_minor": self.peer_minor,
            "detail": self.detail,
        }


def classify_r9_domain(
    local: R9DomainVersion, peer: R9DomainVersion
) -> R9DomainVerdict:
    """The deterministic mixed-version coexistence verdict for ONE R9
    convergence domain (the accepted upgrade matrix discipline,
    extended onto the R9 labels — the family's frozen fail-closed
    semantics): incompatible majors have NO fallback, no clamping, no
    best-effort guess; additive minors are disclosed, never silently
    ignored; same-major peers at or below the local additive head are
    compatible."""
    if not isinstance(local, R9DomainVersion) or not isinstance(
        peer, R9DomainVersion
    ):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "classify_r9_domain requires two R9DomainVersion records",
        )
    if local.domain != peer.domain:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "domain mismatch: %r vs %r (one verdict per domain)"
            % (local.domain, peer.domain),
        )
    if local.major != peer.major:
        return R9DomainVerdict(
            domain=local.domain,
            verdict="major-mismatch",
            local_major=local.major,
            local_minor=local.minor,
            peer_major=peer.major,
            peer_minor=peer.minor,
            detail="majors differ (%d vs %d): there is NO fallback to a "
                   "lower common major (fail closed)" % (local.major, peer.major),
        )
    if peer.minor > local.minor:
        return R9DomainVerdict(
            domain=local.domain,
            verdict="additive-gap",
            local_major=local.major,
            local_minor=local.minor,
            peer_major=peer.major,
            peer_minor=peer.minor,
            detail="the peer carries additive minors %d..%d the local side "
                   "does not speak (disclosed; interoperate on the shared "
                   "minor %d)" % (local.minor + 1, peer.minor, local.minor),
        )
    return R9DomainVerdict(
        domain=local.domain,
        verdict="compatible",
        local_major=local.major,
        local_minor=local.minor,
        peer_major=peer.major,
        peer_minor=peer.minor,
        detail="the shared major %d with the peer minor %d at or below the "
               "local additive head %d" % (local.major, peer.minor, local.minor),
    )


def _matrix_digest(local_id: str, peer_id: str, rows: Sequence[Mapping[str, object]]) -> str:
    """The byte-stable matrix digest (canonical JSON over the sorted
    row sequence — input order never matters; hash-seed independent)."""
    document = {
        "local_id": local_id,
        "peer_id": peer_id,
        "verdicts": [dict(row) for row in rows],
    }
    return _derive_id(_MATRIX_NAMESPACE, document, "the matrix digest document")


@dataclass(frozen=True)
class R9MatrixReport:
    """The deterministic compatibility report over two peers' R9 domain
    version sets (sorted domain iteration; input-order independent;
    byte-stable digest).  A domain present on one side only fails
    closed (``local-missing`` / ``peer-missing`` — never silently
    skipped)."""

    local_id: str
    peer_id: str
    verdicts: Tuple[R9DomainVerdict, ...]

    def __post_init__(self) -> None:
        for label, value in (
            ("local_id", self.local_id),
            ("peer_id", self.peer_id),
        ):
            object.__setattr__(
                self, label, _require_str(value, "the R9 matrix report %s" % label)
            )
        if isinstance(self.verdicts, (str, bytes)) or not isinstance(
            self.verdicts, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the R9 matrix report verdicts must be a sequence",
            )
        verdicts = tuple(self.verdicts)
        for i, verdict in enumerate(verdicts):
            if not isinstance(verdict, R9DomainVerdict):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "the R9 matrix report verdicts[%d] must be an "
                    "R9DomainVerdict record" % i,
                )
        object.__setattr__(self, "verdicts", verdicts)

    def digest(self) -> str:
        """The canonical report digest (byte-stable across runs and
        hash seeds; the accepted ``ConvergedCompatibilityReport.digest``
        discipline)."""
        return _matrix_digest(
            self.local_id,
            self.peer_id,
            [
                verdict.to_dict()
                for verdict in sorted(self.verdicts, key=lambda v: v.domain)
            ],
        )

    def by_domain(self) -> Dict[str, R9DomainVerdict]:
        return {verdict.domain: verdict for verdict in self.verdicts}

    def compatible(self) -> bool:
        """True iff NO R9 domain pair fails closed (major mismatches
        and missing sides refuse; additive gaps are disclosed but
        interoperate)."""
        return all(
            verdict.verdict in ("compatible", "additive-gap")
            for verdict in self.verdicts
        )


def negotiate_r9_matrix(
    *,
    local_id: str,
    peer_id: str,
    local_versions: Sequence[R9DomainVersion],
    peer_versions: Sequence[R9DomainVersion],
) -> R9MatrixReport:
    """The deterministic R9-domain compatibility negotiation (the
    accepted ``negotiate_converged_compatibility`` discipline extended
    onto the R9 labels): both sides' version sets are consulted by
    SORTED domain label (input order never matters); a domain present
    on one side only fails closed; every present pair classifies
    through :func:`classify_r9_domain`."""
    if isinstance(local_versions, (str, bytes)) or not isinstance(
        local_versions, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "negotiate_r9_matrix requires version sequences",
        )
    if isinstance(peer_versions, (str, bytes)) or not isinstance(
        peer_versions, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "negotiate_r9_matrix requires version sequences",
        )
    local_map: Dict[str, R9DomainVersion] = {}
    for version in local_versions:
        if not isinstance(version, R9DomainVersion):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the local version entries must be R9DomainVersion records",
            )
        if version.domain in local_map:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "duplicate local domain version for %r" % version.domain,
            )
        local_map[version.domain] = version
    peer_map: Dict[str, R9DomainVersion] = {}
    for version in peer_versions:
        if not isinstance(version, R9DomainVersion):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the peer version entries must be R9DomainVersion records",
            )
        if version.domain in peer_map:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "duplicate peer domain version for %r" % version.domain,
            )
        peer_map[version.domain] = version
    records = []
    for domain in sorted(set(local_map) | set(peer_map)):
        local = local_map.get(domain)
        peer = peer_map.get(domain)
        if local is None:
            records.append(
                R9DomainVerdict(
                    domain=domain,
                    verdict="local-missing",
                    local_major=-1,
                    local_minor=-1,
                    peer_major=peer.major,
                    peer_minor=peer.minor,
                    detail="the local peer does not carry the R9 convergence "
                           "domain (fail closed; never silently skipped)",
                )
            )
            continue
        if peer is None:
            records.append(
                R9DomainVerdict(
                    domain=domain,
                    verdict="peer-missing",
                    local_major=local.major,
                    local_minor=local.minor,
                    peer_major=-1,
                    peer_minor=-1,
                    detail="the remote peer does not carry the R9 convergence "
                           "domain (fail closed; never silently skipped)",
                )
            )
            continue
        records.append(classify_r9_domain(local, peer))
    return R9MatrixReport(
        local_id=local_id,
        peer_id=peer_id,
        verdicts=tuple(records),
    )


@dataclass(frozen=True)
class AccessConvergenceMatrix:
    """The COMPOSED converged-domain compatibility matrix over the R7,
    R8 and R9 domains: the accepted upgrade engine's R7-substrate rows
    (its own serialized verdicts — DATA consumed by reference at
    runtime), the accepted M019 R8 matrix rows and the R9 extension
    rows, iterated by SORTED domain label with a byte-stable digest
    over the composed row sequence (input order never matters)."""

    local_id: str
    peer_id: str
    rows: Tuple[Tuple[str, str, str], ...]

    def __post_init__(self) -> None:
        for label, value in (
            ("local_id", self.local_id),
            ("peer_id", self.peer_id),
        ):
            object.__setattr__(
                self, label, _require_str(value, "the composed matrix %s" % label)
            )
        if isinstance(self.rows, (str, bytes)) or not isinstance(
            self.rows, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the composed matrix rows must be a sequence of "
                "(domain, verdict, detail) triples",
            )
        rows = []
        seen = set()
        for i, triple in enumerate(self.rows):
            if (
                isinstance(triple, (str, bytes))
                or not isinstance(triple, (tuple, list))
                or len(triple) != 3
            ):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "the composed matrix rows[%d] must be a (domain, verdict, "
                    "detail) triple" % i,
                )
            domain, verdict, detail = triple[0], triple[1], triple[2]
            _require_str(domain, "the composed matrix rows[%d].domain" % i)
            _require_in(
                verdict, MATRIX_VERDICTS, "the composed matrix rows[%d].verdict" % i
            )
            _require_str(detail, "the composed matrix rows[%d].detail" % i)
            if domain in seen:
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "the composed matrix carries the domain %r twice — one "
                    "row per domain" % domain,
                )
            seen.add(domain)
            rows.append((domain, verdict, detail))
        # the stored row sequence is SORTED by domain label (the
        # record itself is input-order independent — the composed
        # group order never leaks into the canonical form)
        object.__setattr__(self, "rows", tuple(sorted(rows)))

    def digest(self) -> str:
        """The canonical composed-matrix digest (byte-stable; sorted by
        domain label — the accepted discipline)."""
        document = {
            "local_id": self.local_id,
            "peer_id": self.peer_id,
            "rows": [
                {"domain": domain, "verdict": verdict, "detail": detail}
                for domain, verdict, detail in sorted(self.rows)
            ],
        }
        return _derive_id(_MATRIX_NAMESPACE, document, "the composed matrix digest")

    def by_domain(self) -> Dict[str, str]:
        return {domain: verdict for domain, verdict, _ in self.rows}

    def compatible(self) -> bool:
        """True iff NO composed row fails closed (major mismatches and
        missing sides refuse; additive gaps interoperate)."""
        return all(
            verdict in ("compatible", "additive-gap") for _, verdict, _ in self.rows
        )


def compose_access_convergence_matrix(
    substrate_verdicts: Sequence[Mapping[str, object]],
    r8_report: R8MatrixReport,
    r9_report: R9MatrixReport,
    *,
    local_id: str,
    peer_id: str,
) -> AccessConvergenceMatrix:
    """Compose the full converged-domain compatibility matrix: the
    accepted upgrade engine's R7-substrate rows (the caller passes
    that engine's OWN serialized verdicts — ``[verdict.to_dict() for
    verdict in report.verdicts]`` — consumed by reference at runtime),
    the accepted M019 R8 matrix rows and the R9 extension rows from
    :func:`negotiate_r9_matrix`.

    Fail-closed gates: every substrate row must carry EXACTLY the
    accepted verdict member set (the ``upgrade.convergence`` shape —
    anything else is not the accepted engine's output); every verdict
    value must be inside the frozen :data:`MATRIX_VERDICTS`; no R8 or
    R9 label may ride the substrate rows (the accepted engine
    classifies exactly the R7-substrate labels); the R8 rows must
    cover exactly the R8 domain set; the R9 rows must cover exactly
    the R9 domain set; no row may overlap.  The composed iteration is
    by SORTED domain label (input order never matters) and the digest
    is byte-stable.
    """
    if isinstance(substrate_verdicts, (str, bytes)) or not isinstance(
        substrate_verdicts, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "compose_access_convergence_matrix requires the accepted "
            "engine's serialized substrate verdict sequence",
        )
    if not isinstance(r8_report, R8MatrixReport):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "compose_access_convergence_matrix requires an R8MatrixReport "
            "(the accepted M019 matrix surface)",
        )
    if not isinstance(r9_report, R9MatrixReport):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "compose_access_convergence_matrix requires an R9MatrixReport",
        )
    composed: List[Tuple[str, str, str]] = []
    substrate_domains = set()
    for i, row in enumerate(substrate_verdicts):
        if not isinstance(row, Mapping):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the substrate verdicts[%d] must be a mapping (the accepted "
                "engine's serialized verdict rows)" % i,
            )
        if set(row.keys()) != set(_SUBSTRATE_ROW_MEMBERS):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the substrate verdicts[%d] does not carry exactly the "
                "accepted upgrade verdict member set %s — only that "
                "engine's own serialized verdicts ride the composed matrix"
                % (i, list(_SUBSTRATE_ROW_MEMBERS)),
            )
        domain = row.get("domain")
        verdict = row.get("verdict")
        detail = row.get("detail")
        if not isinstance(domain, str) or not domain:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the substrate verdicts[%d].domain must be a non-empty "
                "string" % i,
            )
        if domain in R8_CONVERGENCE_DOMAINS or domain in R9_CONVERGENCE_DOMAINS:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the substrate verdicts[%d] carries the non-R7-substrate "
                "domain %r — the accepted upgrade engine classifies "
                "exactly the R7-substrate labels (an R8/R9 label on the "
                "substrate rows is not that engine's output)" % (i, domain),
            )
        if domain in substrate_domains:
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the substrate verdicts carry the domain %r twice" % domain,
            )
        substrate_domains.add(domain)
        _require_in(verdict, MATRIX_VERDICTS, "the substrate verdicts[%d].verdict" % i)
        if not isinstance(detail, str):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the substrate verdicts[%d].detail must be a string" % i,
            )
        composed.append((domain, verdict, detail))
    r8_domains = {verdict.domain for verdict in r8_report.verdicts}
    if r8_domains & substrate_domains:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the R8 rows and the substrate rows overlap (%s) — one row per "
            "domain" % sorted(r8_domains & substrate_domains),
        )
    if r8_domains != set(R8_CONVERGENCE_DOMAINS):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the R8 rows must cover exactly the R8 convergence domain set "
            "%s (found %s) — a converged peer that does not carry an R8 "
            "domain is incompatible on that line, never silently skipped"
            % (list(R8_CONVERGENCE_DOMAINS), sorted(r8_domains)),
        )
    for verdict in r8_report.verdicts:
        composed.append((verdict.domain, verdict.verdict, verdict.detail))
    r9_domains = {verdict.domain for verdict in r9_report.verdicts}
    if r9_domains & substrate_domains or r9_domains & r8_domains:
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the R9 rows overlap the composed matrix (%s) — one row per "
            "domain" % sorted(r9_domains & (substrate_domains | r8_domains)),
        )
    if r9_domains != set(R9_CONVERGENCE_DOMAINS):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "the R9 rows must cover exactly the R9 convergence domain set "
            "%s (found %s) — a converged peer that does not carry an R9 "
            "domain is incompatible on that line, never silently skipped"
            % (list(R9_CONVERGENCE_DOMAINS), sorted(r9_domains)),
        )
    for verdict in r9_report.verdicts:
        composed.append((verdict.domain, verdict.verdict, verdict.detail))
    return AccessConvergenceMatrix(
        local_id=local_id,
        peer_id=peer_id,
        rows=tuple(composed),
    )


# ----------------------------------------------------------------------
# The federation-scale convergence over the R9 domains (the accepted
# scale/ harness discipline, extended)
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AccessScaleBounds:
    """The DECLARED deterministic bounds of one R9 federation-scale
    convergence scenario (the accepted ``scale.convergence`` harness
    envelope — the W039 reproducibility contract — declared up front
    and VERIFIED against the accepted harness run by
    :func:`verify_access_scale_convergence`):

    - the world envelope: ``domain_count``, ``shape`` (the accepted
      topology vocabulary), ``tick_seconds``, ``horizon_ticks``;
    - the citation envelope: ``citation_rate_limit`` (the per-domain
      per-tick admission bound) and ``planned_citations`` (the declared
      admission count);
    - the revocation envelope: ``revoked_citation_count`` (the declared
      revoked-holder count) and ``propagation_round_bounds`` — one
      DECLARED predicted-round count per revoked citation id (the
      topology-predicted convergence bound, LOCK-111-class: observed
      must equal predicted, fail closed on divergence).
    """

    domain_count: int
    shape: str
    tick_seconds: int
    horizon_ticks: int
    citation_rate_limit: int
    planned_citations: int
    revoked_citation_count: int
    propagation_round_bounds: Tuple[Tuple[str, int], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "domain_count",
            _require_int(self.domain_count, "bounds.domain_count", minimum=1),
        )
        object.__setattr__(
            self, "shape", _require_str(self.shape, "bounds.shape")
        )
        object.__setattr__(
            self,
            "tick_seconds",
            _require_int(self.tick_seconds, "bounds.tick_seconds", minimum=1),
        )
        object.__setattr__(
            self, "horizon_ticks", _require_int(self.horizon_ticks, "bounds.horizon_ticks")
        )
        object.__setattr__(
            self,
            "citation_rate_limit",
            _require_int(self.citation_rate_limit, "bounds.citation_rate_limit", minimum=1),
        )
        object.__setattr__(
            self,
            "planned_citations",
            _require_int(self.planned_citations, "bounds.planned_citations"),
        )
        object.__setattr__(
            self,
            "revoked_citation_count",
            _require_int(self.revoked_citation_count, "bounds.revoked_citation_count"),
        )
        if isinstance(self.propagation_round_bounds, (str, bytes)) or not isinstance(
            self.propagation_round_bounds, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "bounds.propagation_round_bounds must be a sequence of "
                "(citation id, predicted rounds) pairs",
            )
        bounds = []
        seen = set()
        for i, pair in enumerate(self.propagation_round_bounds):
            if (
                isinstance(pair, (str, bytes))
                or not isinstance(pair, (tuple, list))
                or len(pair) != 2
            ):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "bounds.propagation_round_bounds[%d] must be a (citation "
                    "id, predicted rounds) pair" % i,
                )
            citation_id, rounds = pair[0], pair[1]
            _require_str(
                citation_id,
                "bounds.propagation_round_bounds[%d].citation_id" % i,
                pattern=_CITATION_ID_PATTERN,
            )
            _require_int(
                rounds,
                "bounds.propagation_round_bounds[%d].rounds" % i,
                minimum=1,
            )
            if citation_id in seen:
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "bounds.propagation_round_bounds carries the citation "
                    "%r twice" % citation_id[:40],
                )
            seen.add(citation_id)
            bounds.append((citation_id, rounds))
        object.__setattr__(self, "propagation_round_bounds", tuple(bounds))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_count": self.domain_count,
            "shape": self.shape,
            "tick_seconds": self.tick_seconds,
            "horizon_ticks": self.horizon_ticks,
            "citation_rate_limit": self.citation_rate_limit,
            "planned_citations": self.planned_citations,
            "revoked_citation_count": self.revoked_citation_count,
            "propagation_round_bounds": [
                {"citation_id": citation_id, "predicted_rounds": rounds}
                for citation_id, rounds in self.propagation_round_bounds
            ],
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the scale bounds record")


@dataclass(frozen=True)
class AccessScaleConvergence:
    """The composed R9 federation-scale convergence report: the
    accepted scale harness run consumed by reference at runtime (its
    OWN digests and counts carried verbatim — never recomputed here)
    together with the declared bounds and the VERIFIED convergence
    properties (the replay identity, the topology-predicted round
    counts, the declared envelopes).  ``report_id`` is content-derived
    over the composed core (tamper-evident); the issuer is this
    surface's own convergence issuer (LOCK-118)."""

    report_id: str
    run_digest: str
    spec_digest: str
    citation_ids: Tuple[str, ...]
    domain_count: int
    relationship_count: int
    citation_count: int
    revoked_citation_count: int
    propagation: Tuple[Tuple[str, int, int], ...]
    declared_bounds: AccessScaleBounds
    replay_verified: bool
    issuer: str
    decision_refs: Tuple[str, ...]

    def __post_init__(self) -> None:
        for label, value in (
            ("run_digest", self.run_digest),
            ("spec_digest", self.spec_digest),
        ):
            object.__setattr__(
                self,
                label,
                _require_str(
                    value, "the scale convergence %s" % label,
                    pattern=_RUN_DIGEST_PATTERN,
                ),
            )
        if isinstance(self.citation_ids, (str, bytes)) or not isinstance(
            self.citation_ids, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the scale convergence citation_ids must be a sequence",
            )
        citation_ids = tuple(
            _require_str(
                value,
                "the scale convergence citation_ids[%d]" % i,
                pattern=_CITATION_ID_PATTERN,
            )
            for i, value in enumerate(self.citation_ids)
        )
        if len(set(citation_ids)) != len(citation_ids):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the scale convergence citation_ids carry duplicates",
            )
        object.__setattr__(self, "citation_ids", citation_ids)
        for label, value in (
            ("domain_count", self.domain_count),
            ("relationship_count", self.relationship_count),
            ("citation_count", self.citation_count),
            ("revoked_citation_count", self.revoked_citation_count),
        ):
            object.__setattr__(
                self, label, _require_int(value, "the scale convergence %s" % label)
            )
        if isinstance(self.propagation, (str, bytes)) or not isinstance(
            self.propagation, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the scale convergence propagation must be a sequence of "
                "(citation id, predicted rounds, observed rounds) triples",
            )
        propagation = []
        for i, triple in enumerate(self.propagation):
            if (
                isinstance(triple, (str, bytes))
                or not isinstance(triple, (tuple, list))
                or len(triple) != 3
            ):
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "the scale convergence propagation[%d] must be a "
                    "(citation id, predicted, observed) triple" % i,
                )
            citation_id, predicted, observed = triple[0], triple[1], triple[2]
            _require_str(
                citation_id,
                "the scale convergence propagation[%d].citation_id" % i,
                pattern=_CITATION_ID_PATTERN,
            )
            _require_int(predicted, "the propagation[%d].predicted" % i, minimum=1)
            _require_int(observed, "the propagation[%d].observed" % i, minimum=1)
            propagation.append((citation_id, predicted, observed))
        object.__setattr__(self, "propagation", tuple(propagation))
        if not isinstance(self.declared_bounds, AccessScaleBounds):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the scale convergence requires the declared bounds record",
            )
        if not isinstance(self.replay_verified, bool):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the scale convergence replay_verified must be a boolean",
            )
        object.__setattr__(
            self, "issuer", _require_str(self.issuer, "the scale convergence issuer")
        )
        if isinstance(self.decision_refs, (str, bytes)) or not isinstance(
            self.decision_refs, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "the scale convergence decision_refs must be a sequence",
            )
        object.__setattr__(
            self,
            "decision_refs",
            tuple(
                _require_str(
                    value, "the scale convergence decision_refs[%d]" % i
                )
                for i, value in enumerate(self.decision_refs)
            ),
        )
        expected = self._derive_report_id()
        if not self.report_id:
            object.__setattr__(self, "report_id", expected)
        else:
            if _ID_PATTERN.fullmatch(self.report_id) is None:
                raise AccessTechError(
                    AccessTechReason.INVALID_INPUT,
                    "the scale convergence report_id must be the "
                    "content-derived identity (sha256:...)",
                )
            if self.report_id != expected:
                raise AccessTechError(
                    AccessTechReason.IDENTITY_MISMATCH,
                    "report_id does not match the derived identity (tamper "
                    "evidence)",
                )

    def _derive_report_id(self) -> str:
        document = {
            "run_digest": self.run_digest,
            "spec_digest": self.spec_digest,
            "citation_ids": list(self.citation_ids),
            "domain_count": self.domain_count,
            "relationship_count": self.relationship_count,
            "citation_count": self.citation_count,
            "revoked_citation_count": self.revoked_citation_count,
            "propagation": [
                {
                    "citation_id": citation_id,
                    "predicted_rounds": predicted,
                    "observed_rounds": observed,
                }
                for citation_id, predicted, observed in self.propagation
            ],
            "declared_bounds": self.declared_bounds.to_dict(),
            "replay_verified": self.replay_verified,
            "issuer": self.issuer,
            "decision_refs": list(self.decision_refs),
        }
        return _derive_id(_SCALE_NAMESPACE, document, "the scale report id document")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "run_digest": self.run_digest,
            "spec_digest": self.spec_digest,
            "citation_ids": list(self.citation_ids),
            "domain_count": self.domain_count,
            "relationship_count": self.relationship_count,
            "citation_count": self.citation_count,
            "revoked_citation_count": self.revoked_citation_count,
            "propagation": [
                {
                    "citation_id": citation_id,
                    "predicted_rounds": predicted,
                    "observed_rounds": observed,
                }
                for citation_id, predicted, observed in self.propagation
            ],
            "declared_bounds": self.declared_bounds.to_dict(),
            "replay_verified": self.replay_verified,
            "issuer": self.issuer,
            "decision_refs": list(self.decision_refs),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict(), "the scale convergence report")


def verify_access_scale_convergence(
    bounds: AccessScaleBounds,
    run_result: object,
    replay_result: object,
    *,
    citation_ids: Sequence[str],
    decision_refs: Optional[Sequence[str]] = None,
) -> AccessScaleConvergence:
    """Verify the accepted scale-harness run against the DECLARED
    deterministic bounds and compose the R9 federation-scale
    convergence report (the accepted ``scale.convergence`` run result
    consumed by reference at runtime — its OWN digests and counts
    carried verbatim, never recomputed here; the accepted M019
    verifier discipline extended onto the R9 material).

    The verified properties (every one fails closed typed on
    divergence):

    1. the run and the re-run (the replay) carry the IDENTICAL run
       digest — the byte-identical replay, the accepted harness's own
       reproducibility contract;
    2. the world envelope matches the declared bounds (the domain
       count, one ledger digest per declared domain);
    3. the citation envelope matches (the citation admissions count
       and every R9 material citation id present in the run's
       propagation/journal material — the declared R9 citations);
    4. the revocation envelope matches (the revoked-citation count);
    5. every observed propagation round count equals its DECLARED
       predicted bound (the topology-predicted convergence bound —
       LOCK-111-class: fail closed on divergence, never a silent
       pass).

    ``citation_ids`` are the R9 drill-material citation ids the
    scenario planned across the federation domains (constructed by the
    composition root through the ACCEPTED ``federation.convergence``
    cite-* constructors over the REAL R9 records — the interchange and
    replacement handover decisions).
    """
    if not isinstance(bounds, AccessScaleBounds):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "verify_access_scale_convergence requires AccessScaleBounds "
            "(the declared deterministic envelope)",
        )
    _duck_surface(
        run_result,
        (
            "run_digest",
            "spec_digest",
            "domain_count",
            "relationship_count",
            "citation_count",
            "revoked_citation_count",
            "propagation",
            "ledger_digests",
        ),
        "the accepted scale harness run result",
    )
    _duck_surface(
        replay_result,
        ("run_digest",),
        "the accepted scale harness replay result",
    )
    if isinstance(citation_ids, (str, bytes)) or not isinstance(
        citation_ids, (tuple, list)
    ):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "citation_ids must be a sequence of citation ids",
        )
    r9_citations = tuple(
        _require_str(value, "citation_ids[%d]" % i, pattern=_CITATION_ID_PATTERN)
        for i, value in enumerate(citation_ids)
    )
    if len(set(r9_citations)) != len(r9_citations):
        raise AccessTechError(
            AccessTechReason.INVALID_INPUT,
            "citation_ids carry duplicates",
        )

    # 1. the byte-identical replay (the accepted harness's own
    #    reproducibility contract, verified on the consumed digests)
    replay_verified = replay_result.run_digest == run_result.run_digest
    if not replay_verified:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the accepted scale harness replay diverged (run digest %s vs "
            "%s) — the convergence scenarios are replay-verified, never "
            "silently accepted" % (
                run_result.run_digest[:23], replay_result.run_digest[:23],
            ),
        )

    # 2. the world envelope
    if run_result.domain_count != bounds.domain_count:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the accepted harness ran %d domains, not the declared %d — the "
            "declared deterministic bounds are the contract"
            % (run_result.domain_count, bounds.domain_count),
        )
    ledger_digests = tuple(run_result.ledger_digests)
    if len(ledger_digests) != bounds.domain_count:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the accepted harness carries %d per-domain ledger digests, "
            "not one per declared domain (%d)"
            % (len(ledger_digests), bounds.domain_count),
        )

    # 3. the citation envelope
    if run_result.citation_count != bounds.planned_citations:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the accepted harness admitted %d citations, not the declared "
            "%d — the declared deterministic bounds are the contract"
            % (run_result.citation_count, bounds.planned_citations),
        )

    # 4. the revocation envelope
    if run_result.revoked_citation_count != bounds.revoked_citation_count:
        raise AccessTechError(
            AccessTechReason.IDENTITY_MISMATCH,
            "the accepted harness revoked %d citations, not the declared %d"
            % (
                run_result.revoked_citation_count,
                bounds.revoked_citation_count,
            ),
        )

    # 5. the topology-predicted propagation bounds (observed ==
    #    declared predicted, fail closed).  Every declared bound rides
    #    an R9 material citation (the revocation envelope cites the R9
    #    drill material — a bound naming a foreign citation fails
    #    closed: the composed report's citations stay the R9 set).
    r9_citation_set = set(r9_citations)
    for citation_id, _ in bounds.propagation_round_bounds:
        if citation_id not in r9_citation_set:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "the declared propagation bound cites %s — not one of the "
                "R9 drill-material citations (the revocation envelope "
                "rides the R9 material; fail closed)" % citation_id[:40],
            )
    propagation_records = tuple(run_result.propagation)
    observed_by_citation = {}
    for record in propagation_records:
        _duck_surface(
            record,
            ("citation_id", "predicted_rounds", "observed_rounds"),
            "the accepted propagation record",
        )
        observed_by_citation[record.citation_id] = (
            record.predicted_rounds,
            record.observed_rounds,
        )
    propagation = []
    for citation_id, declared_rounds in bounds.propagation_round_bounds:
        pair = observed_by_citation.get(citation_id)
        if pair is None:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "the declared revoked citation %s never propagated in the "
                "accepted harness run — the declared bounds are the "
                "contract (fail closed)" % citation_id[:40],
            )
        predicted, observed = pair
        if predicted != declared_rounds or observed != declared_rounds:
            raise AccessTechError(
                AccessTechReason.IDENTITY_MISMATCH,
                "the propagation of %s diverged from the declared "
                "topology-predicted bound (declared %d, the harness "
                "predicted %d, observed %d) — the convergence bound fails "
                "closed (LOCK-111-class)" % (
                    citation_id[:40], declared_rounds, predicted, observed,
                ),
            )
        propagation.append((citation_id, declared_rounds, observed))

    if decision_refs is None:
        refs: Tuple[str, ...] = (run_result.run_digest, bounds.shape)
    else:
        if isinstance(decision_refs, (str, bytes)) or not isinstance(
            decision_refs, (tuple, list)
        ):
            raise AccessTechError(
                AccessTechReason.INVALID_INPUT,
                "decision_refs must be a sequence of reference strings",
            )
        refs = tuple(
            _require_str(value, "decision_refs[%d]" % i)
            for i, value in enumerate(decision_refs)
        )
    return AccessScaleConvergence(
        report_id="",
        run_digest=run_result.run_digest,
        spec_digest=run_result.spec_digest,
        citation_ids=r9_citations,
        domain_count=run_result.domain_count,
        relationship_count=run_result.relationship_count,
        citation_count=run_result.citation_count,
        revoked_citation_count=run_result.revoked_citation_count,
        propagation=tuple(propagation),
        declared_bounds=bounds,
        replay_verified=True,
        issuer=CONVERGENCE_ISSUER,
        decision_refs=refs,
    )
