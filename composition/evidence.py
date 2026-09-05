"""WORK-054 evidence discipline.

The evidence model of the composition layer, reconciled with the
W032 precedent and the WORK-054 evidence classes:

- SOFTWARE: every deterministic composition test, authority-
  boundary proof, negative proof, replay/idempotency result, and
  scope audit.  This is the ONLY class the composition layer can
  mint.
- PHYSICAL: none.  W040's physical validation obligations
  (EVID-007, EVID-008) remain open and W040-owned; software
  evidence can never close them.  The classifier fails closed on
  any physical claim, and ``physical_obligations_open`` proves --
  read-only, against the durable governance projection -- that
  the physical obligations are still open.
- EXTERNAL: none minted in-repo (no external evidence is claimed
  by any composition run; the assertion guards it mechanically).

Every evidence record is content-derived over the WORK-003
canonical JSON form: ``"sha256:" + sha256(canonical_json_bytes(
content))`` -- the same convention every composed authority uses,
so composition digests correlate with (and only cite) authority-
sourced identities.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from protocol.canonicalization import canonical_json_bytes

#: The single evidence class this layer may mint.
EVIDENCE_CLASS_SOFTWARE = "SOFTWARE"

#: The read-only path of the durable evidence-obligations
#: projection (W040-owned physical obligations live here; the
#: composition layer never writes to spec/).
EVIDENCE_OBLIGATIONS_PATH = "spec/architect/evidence-obligations.yaml"

#: The physical obligations that must remain open and W040-owned.
PHYSICAL_OBLIGATION_IDS: Tuple[str, ...] = ("EVID-007", "EVID-008")


class CompositionEvidenceError(ValueError):
    """Raised when an evidence claim violates the WORK-054
    discipline (fail closed)."""


def classify_evidence(evidence_class: str) -> str:
    """Classify one evidence claim (fail closed).

    The composition layer mints SOFTWARE evidence only: a
    PHYSICAL claim fails closed because software evidence can
    never close physical evidence (W040/EVID-007/EVID-008 stay
    open and independently owned); an EXTERNAL claim fails closed
    because an in-repo deterministic run can never mint external
    evidence.
    """

    if evidence_class == EVIDENCE_CLASS_SOFTWARE:
        return EVIDENCE_CLASS_SOFTWARE
    if evidence_class in ("PHYSICAL", "physical"):
        raise CompositionEvidenceError(
            "SOFTWARE_EVIDENCE_CANNOT_CLOSE_PHYSICAL: the composition "
            "layer mints SOFTWARE evidence only; physical evidence "
            "obligations (EVID-007/EVID-008) belong to WORK-040 and "
            "cannot be closed by any in-repo deterministic run"
        )
    if evidence_class in ("EXTERNAL", "external-evidence", "OPERATIONAL"):
        raise CompositionEvidenceError(
            "EVIDENCE_CLASS_FORBIDDEN: an in-repo composition run can "
            "never mint %r evidence; only SOFTWARE conformance evidence "
            "is producible here" % evidence_class
        )
    raise CompositionEvidenceError(
        "EVIDENCE_CLASS_UNKNOWN: %r is not an evidence class of the "
        "composition layer" % evidence_class
    )


def composition_digest(content: Any) -> str:
    """The WORK-003-convention content digest (sha256 over the
    canonical JSON form; floats and non-canonical values fail
    closed inside the canonicalization itself)."""
    return "sha256:" + hashlib.sha256(canonical_json_bytes(content)).hexdigest()


@dataclass(frozen=True)
class SoftwareEvidenceRecord:
    """One deterministic SOFTWARE evidence record.

    ``subject`` names the proven fact, ``produced_by`` names the
    authority or battery surface that produced it, ``correlation``
    carries authority-sourced identities/digests only, and
    ``evidence_class`` is pinned to SOFTWARE (classified through
    :func:`classify_evidence` at construction).
    """

    record_id: str
    subject: str
    produced_by: str
    correlation: Dict[str, Any]
    evidence_class: str = EVIDENCE_CLASS_SOFTWARE

    def __post_init__(self) -> None:
        classify_evidence(self.evidence_class)
        if not self.subject:
            raise CompositionEvidenceError(
                "an evidence record requires a subject"
            )
        if not self.produced_by:
            raise CompositionEvidenceError(
                "an evidence record requires its producing surface"
            )

    def content(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "subject": self.subject,
            "produced_by": self.produced_by,
            "evidence_class": self.evidence_class,
            "correlation": self.correlation,
        }

    def digest(self) -> str:
        return composition_digest(self.content())

    def to_dict(self) -> Dict[str, Any]:
        return self.content()


def build_evidence_document(
    records: Tuple[SoftwareEvidenceRecord, ...],
) -> Dict[str, Any]:
    """Assemble the deterministic SOFTWARE evidence document.

    The document carries every record in canonical (record-id
    sorted) order, asserts the class separation mechanically (no
    external claim, no physical claim), and derives its digest
    over the WORK-003 canonical form.
    """
    table: Dict[str, SoftwareEvidenceRecord] = {}
    for record in records:
        if record.record_id in table:
            raise CompositionEvidenceError(
                "duplicate evidence record id %r" % record.record_id
            )
        classify_evidence(record.evidence_class)
        table[record.record_id] = record
    document = {
        "kind": "work-054-software-evidence",
        "evidence_class": EVIDENCE_CLASS_SOFTWARE,
        "records": [
            table[key].to_dict() for key in sorted(table)
        ],
    }
    document["digest"] = composition_digest(document)
    return document


def assert_no_external_claim(document: Dict[str, Any]) -> None:
    """Fail closed if any record claims a non-SOFTWARE class."""
    for record in document.get("records", ()):
        claimed = record.get("evidence_class", "")
        if claimed != EVIDENCE_CLASS_SOFTWARE:
            raise CompositionEvidenceError(
                "NON_SOFTWARE_CLAIM: record %r claims class %r" % (
                    record.get("record_id", "?"), claimed
                )
            )


def physical_obligations_open(obligations_text: str) -> Dict[str, Dict[str, str]]:
    """Prove (read-only) that the W040 physical obligations are
    still open in the durable evidence-obligations projection.

    Parses the projection TEXT for the EVID-007/EVID-008 entries
    and their honest status labels.  Returns a mapping of
    obligation id -> {status, owner} extracted from the durable
    document; the battery asserts every returned obligation is
    open and W040-owned (never closed by any software run).
    """
    statuses: Dict[str, Dict[str, str]] = {}
    for obligation in PHYSICAL_OBLIGATION_IDS:
        pattern = re.compile(
            r"-\s*obligation_id:\s*%s\b(.*?)(?=\n\s*-\s*obligation_id:|\Z)"
            % re.escape(obligation),
            re.DOTALL,
        )
        match = pattern.search(obligations_text)
        if match is None:
            statuses[obligation] = {
                "status": "absent-from-projection",
                "owner": "",
            }
            continue
        block = match.group(1)
        status_match = re.search(r"status:\s*([A-Za-z_-]+)", block)
        owner_match = re.search(r"owner:\s*([A-Za-z0-9_-]+)", block)
        work_match = re.search(r"work_item:\s*(WORK-\d+)", block)
        class_match = re.search(r"evidence_class:\s*([A-Za-z_-]+)", block)
        statuses[obligation] = {
            "status": status_match.group(1) if status_match else "",
            "owner": (
                (owner_match.group(1) if owner_match else "")
                or (work_match.group(1) if work_match else "")
            ),
            "evidence_class": class_match.group(1) if class_match else "",
        }
    return statuses
