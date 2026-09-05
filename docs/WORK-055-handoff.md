# WORK-055 — Protocol Production Conformance — Handoff

Work Item `WORK-055` — authorization `WORK-055-CORE-001` — decision
`DEC-0088`. Authorized baseline
`57963858e5a2b9d11faed94b50f94e058cede0a8` (the post-W054-acceptance
mainline). Worker state after the round-2 review-correction delivery:
**WAITING_FOR_ARCHITECT** (re-review at the new exact head of
PR #15).

The full evidence record is `docs/WORK-055-evidence.md`. This handoff
identifies the remaining non-production limitations honestly — none of
them relabeled as passes.

## Review history

- **Round 1** (`372299bfe3b54f79c0238d2927de2224249c4e36`): the
  implementation delivery. Architect review verdict: **CHANGES
  REQUIRED** (PR #15, 2026-09-05) — (1) P1 WIRE-017 did not exercise
  the frozen `protocol` member; (2) P1 the evidence record's
  file/line accounting (24 files, +3477/−5) and the PR body's (25,
  +3496/−5) contradicted the actual Git tree (26 files, +3981/−5);
  (3) P2 the W032 `case_25` output edit made the "W032 unchanged"
  claim too strong; (4) P2 CP-11's claim was broader than WIRE-011's
  direct verification; (5) the CI evidence distinction had to be
  explicit.
- **Round 2** (the review-correction commit, parent `372299b…`):
  WIRE-017 now covers `protocol` (basis presence + document-level
  value mutation) and its mutation matrix is audited complete against
  the frozen `Envelope.KNOWN_FIELDS`; the battery proves BOTH
  covered-byte sabotages (payload-drop and protocol-drop) against
  WIRE-017; WIRE-011 directly verifies unknown top-level-member
  verbatim preservation (both CP-11 conjuncts); `case_25` was reverted
  to the byte-original W032 text; the evidence record carries the
  exact 26-path inventory and totals from the actual Git tree; the
  worker-local vs CI evidence distinction is explicit (§11 of the
  evidence record).

## What was delivered

The R3 production-conformance layer on the WORK-032 foundation,
additive and hardening-only:

1. **The production canonicalization profile**
   (`conformance/profile.py`): the profile `spec/schemas/protocol.json`
   explicitly deferred to "later conformance work" — named, attributed
   to WORK-003, twelve rules each citing its frozen source, digest-
   stable, and mechanically verified rule-by-rule by the WIRE vectors.
   This declares/pins the frozen form; it mints no new semantics.
2. **The golden-vector corpus** (`conformance/golden.py`,
   `conformance/vectors/data/`): 16 byte-exact W003 fixtures (canonical
   encoding, raw-text convergence, signature-input bases, codec
   cross-agreement) with stable ids, owning authorities, invariants,
   and outcome classes; the verifier calls only frozen public APIs.
3. **The WIRE vectors** (`conformance/vectors/wire.py`, 27 vectors,
   envelope area): canonicalization profile rules (with WIRE-011
   directly verifying both CP-11 conjuncts — absent-optional
   omission and unknown top-level-member verbatim preservation),
   corpus verification, complete signature-coverage (the mutation
   matrix includes the frozen `protocol` member and is audited
   complete against `Envelope.KNOWN_FIELDS`) and covered-byte
   integrity (end-to-end through the WORK-004 provider seam),
   unknown-field/extension hardening, replay/idempotency hardening,
   and evidence separation (conformance evidence can never become
   protocol state).
4. **Battery-level R3 coverage of the WORK-029 boundary** (in
   `tools/conformance_selftest.py`): the genuine version-negotiation
   and migration outcome tables with structural fail-closed proofs
   (forged cross-major selections are non-constructible; downgrade
   plans are refused; non-reversible migrations never reverse), plus
   the negotiation-outcome digest.
5. **The extended battery**: the 46 WORK-032 cases byte-identical to
   the accepted WORK-032 delivery and passing, plus 17 WORK-055
   cases — corpus/profile/W029 digest stability across subprocesses
   and `PYTHONHASHSEED` 0/1/7919, digest-instability discrimination,
   seven R3 sabotage families (canonicalization ambiguity,
   covered-byte exclusion — proven against BOTH a payload-blind and a
   protocol-blind basis — negotiation downgrade, migration
   best-effort reversal, unsafe unknown-field handling,
   evidence-as-authority, digest instability), the compatibility-class
   table, W055 tag coverage, evidence-separation re-proof, and the
   exact scope/ancestry/frozen-surface audits against the authorized
   baseline.

Matrix: 163/163 vectors conformant (63 positive / 100 negative;
round-2 report digest `sha256:f7135f97…`). Battery: 63/63. All prior
batteries green at the delivery head (composition 55/55, upgrade
41/41, spec_check byte-identical to the baseline classification). All
battery/matrix/digest results in the evidence record are
**worker-local**; CI does not execute the conformance step for this
PR (inherited spec_check failures — see the evidence record §11).

## Non-production limitations (not passes)

1. **No external interoperability evidence.** In-repo vectors can
   never mint it (mechanically enforced). Wire compatibility with any
   independent implementation remains unproven until operator-side
   external evidence exists — by design, outside this repository.
2. **No R4 physical validation, no W040 disposition, no W048
   restoration.** SOFTWARE conformance evidence cannot close PHYSICAL
   obligations; EVID-007/EVID-008 remain open and W040-owned.
3. **The W029 coverage lives at the battery level, not in the
   registry matrix.** The R3 negotiation/migration coverage is fully
   mechanical but runs from `tools/conformance_selftest.py` (the
   sanctioned composition root) rather than as registry vectors in
   the conformance family, because the frozen
   `spec/dependency-graph.md` carries no W055 family-level edge and
   the accepted W029 battery (case_33) forbids family-level imports
   of `upgrade` outside its spec-recorded list (W033/W038 precedents).
   Moving the coverage into the matrix requires an Architect-side
   amendment (the W033/W038 pattern, citing the WORK-055
   authorization) plus a dependency-graph edge — deliberately NOT
   done here to keep every accepted battery green and the scope
   clean.
4. **CI reachability.** The conformance battery step remains wired in
   `spec-check` but is unreachable in the current PR/main jobs because
   the inherited `spec_check.py` ARCH-02/04/05/06/07 failures
   terminate the job first (the same signature as every post-R0
   delivery, including the accepted W054 PR). The operative R3
   evidence is repository-local and reproducible from the delivery
   commit.
5. **The compact CBOR codec remains provisional** per the frozen
   `protocol.json` (`compact-deterministic-cbor.status =
   "provisional"`); the corpus pins its byte-exact behavior for the
   supported subset, but the frozen production wire codec is the
   canonical JSON form. Changing the CBOR status is ACR territory.

## Authority discipline (unchanged)

The delivery mints no protocol vocabulary, redefines no authority
ownership, creates no second protocol implementation, infers no
provenance from structural validity, promotes no conformance evidence
into protocol state, creates no second source of truth, and promotes
no software evidence into physical evidence. The golden corpus and
the profile statement are conformance evidence — test data and
attributed rule restatements — never authoritative over the frozen
specification. No frozen semantic, wire-schema, or registry change is
present (battery case 63; `git diff` against the baseline over
`protocol/`, `upgrade/`, and `spec/`).

## Exit condition

R3 may close only after Architect adversarial review establishes that
the production conformance layer can distinguish a conforming
implementation from the mandated classes of broken implementation and
that all evidence remains subordinate to the frozen protocol
authorities. The nine mandated sabotage categories are each proven
(genuine CONFORMANT → sabotaged NONCONFORMANT → genuine CONFORMANT
restored); the suite can fail a broken candidate, not merely pass the
genuine one.

## Stop conditions for the worker

Do not merge; do not self-accept; do not modify `spec/architect/`; do
not create or alter authorizations; do not activate R4/R5; do not
amend the W029 battery or the dependency graph (Architect-owned); do
not repair inherited governance debt (the spec_check ARCH-02/04/05/
06/07 failures are inherited and unchanged); do not touch W040/W048.
WAITING_FOR_ARCHITECT.
