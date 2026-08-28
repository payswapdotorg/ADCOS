"""ADCOS 5G RAN RF-simulation environment (WORK-020, Architect work order).

An INDEPENDENTLY implemented OAI-RFsim-style gNB/UE emulation
environment (Architect work order, PR #21 comment 5452614288): a real
REST-over-HTTP RAN control-plane peer whose gNB/cell/bearer behavior is
derived from a DETERMINISTIC RADIO-CHANNEL MODEL -- UE positions,
3GPP TR 38.901 UMa NLOS path-loss anchors, seeded shadowing and
fast-fading draws, inter-cell interference, per-PRB thermal noise, and
a TS 38.214-inspired SINR -> MCS ladder that drives admission, PRB
demand, health, and per-transmission decode success.  This is the RF
analogue of OpenAirInterface's ``--rfsim`` mode (the RF front end
replaced by a simulated channel between virtual gNB and UE); the RRC
state shapes follow TS 38.331 and the DRB/QoS-flow mapping follows
TS 23.501 section 5.4 (the same family conventions).

HONESTLY DISCLOSED (the anti-faking rule): this module is an RF
CHANNEL SIMULATION, not a software-defined radio and not a real RAN
stack.  It can NEVER satisfy the frozen WORK-020 SDR-based lab
topology acceptance criterion: ``rf_simulation``/``rfsim`` are
registered FORBIDDEN peer kinds in the interop gate exactly like
``reference``/``simulator`` (see :mod:`.interop_env_probe`), and the
real gate keeps requiring ``[SDR]`` device evidence.  Its purpose is
the Architect-authorized RF-simulation VALIDIDATION phase: maximize
the boundary evidence obtainable without physical SDR hardware.

Independence from the in-repo :class:`~.conformance.ReferenceRanConformanceServer`
is structural, not cosmetic:

* a SEPARATE state machine (its own gNB/bearer/UE registries, its own
  HTTP handler plumbing) that imports NOTHING from
  ``conformance.py`` -- only the family's frozen shared vocabularies
  (``model.py`` value types, ``validation.py`` seam validators) and
  the engine's content-derived ref-minting helpers
  (``_mint_ref``/``FIRST_RNTI``/``LAST_RNTI``/``RAN_ALLOCATION_KINDS``
  -- the exact precedent set the conformance peer itself imports, so
  identical operation histories mint identical references and manager
  canonical state stays byte-identical across implementations);
* CONTROL-PLANE BEHAVIOR DERIVED FROM RADIO STATE, not registry
  bookkeeping: bearer admission requires sufficient received power
  and SINR; the bearer's PRB demand grows as channel quality (MCS)
  falls; health reports DEGRADE when a live bearer's SINR falls below
  the healthy floor; per-transmission decode success is conditioned
  on the current SINR with a seeded fast-fading draw; serving-cell
  selection is geometric (strongest received power), not
  insertion-order -- outcomes the conformance peer cannot produce.

Determinism: everything is content-derived -- integer-only channel
arithmetic (no float), a sha256 counter-based seeded stream for
shadowing/fading draws keyed by (label, index) content, no wall
clock, no randomness, no environment reads.  Two peers built from the
same scenario produce byte-identical radio reports and byte-identical
mediated manager state for the same operation history.

All diagnostics are secret-free (LOCK-023): RNTI/DRB/QFI material is
peer-private and never crosses the wire; failure responses carry
vocabulary reason tokens only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import unquote

from .engine import (
    FIRST_RNTI,
    LAST_RNTI,
    RAN_ALLOCATION_KINDS,
    _mint_ref,
)
from .model import (
    RAN_CAPABILITY_CELL_FDD,
    RAN_CAPABILITY_CELL_TDD,
    RAN_CAPABILITY_CU_DU_SPLIT_F1,
    RAN_CAPABILITY_DRB_QOS_FLOW,
    RAN_CAPABILITY_GNB_PROVISION,
    RAN_CAPABILITY_O_RU_FRONTHAUL,
    RAN_CAPABILITY_REFERENCES,
    CellDescriptor,
    CellSpec,
    CellState,
    CuElement,
    DuplexMode,
    DuElement,
    GnbProvisionRequest,
    HealthState,
    RanDrb,
    RanSplitOption,
    RanSplitTopology,
    RanUeContext,
    RuElement,
)
from .serialization import to_canonical_bytes
from .validation import (
    reject_credential_like_text,
    validate_gnb_provision_request,
    validate_session_id,
)

__all__ = ["RfSimScenario", "RfSimEnvironment", "RfSimRanPeer"]


# ---------------------------------------------------------------------------
# Deterministic seeded draws (no random module, no wall clock)
# ---------------------------------------------------------------------------


def _seeded_uint(seed: str, label: str, bound: int) -> int:
    """A PURE content-addressed deterministic draw: uint in ``[0, bound)``.

    ``sha256("<seed>|<label>|<round>")`` with rejection sampling over
    successive rounds -- the simulator-family STREAM PATTERN
    re-implemented independently inside this module (no ``simulator``
    import; the RAN family owns its own draw).  Because the draw is a
    pure function of ``(seed, label, bound)`` -- no shared counter --
    repeated queries of the same channel quantity (e.g. the per-(cell,
    UE) shadowing) are STABLE across calls, and the same scenario
    replays byte-identically.
    """
    if not isinstance(seed, str) or not seed:
        raise ValueError("rfsim seed must be a non-empty string")
    if isinstance(bound, bool) or not isinstance(bound, int) or bound <= 0:
        raise ValueError("bound must be a positive integer")
    round_index = 0
    while True:
        digest = hashlib.sha256(
            ("%s|%s|%d" % (seed, label, round_index)).encode("utf-8")
        ).hexdigest()
        raw = int(digest[:8], 16)
        limit = (0x100000000 // bound) * bound
        if raw < limit:
            return raw % bound
        round_index += 1


# ---------------------------------------------------------------------------
# Frozen integer channel constants (TR 38.901 / TS 38.214 anchors)
# ---------------------------------------------------------------------------

#: TR 38.901 UMa NLOS path-loss anchors at fc = 3.5 GHz (band n78):
#: PL = 13.54 + 39.08*log10(d) + 20*log10(3.5) (d in meters), sampled
#: at anchor distances and frozen as INTEGER MILLI-DECIBELS.  Pure
#: integer linear interpolation between anchors (clamped below 10 m;
#: fixed 5.2 milli-dB/m extrapolation slope above 5 km).
_PATH_LOSS_ANCHORS: Tuple[Tuple[int, int], ...] = (
    (10, 63501),
    (25, 79053),
    (50, 90817),
    (100, 102581),
    (250, 118133),
    (500, 129897),
    (1000, 141661),
    (2000, 153426),
    (5000, 168977),
)

#: TR 38.901 UMa NLOS shadowing sigma = 6 dB, modeled as a symmetric
#: discrete draw in 0.5 dB steps over [-6, +6] dB (25 levels).
_SHADOWING_STEP_MDB = 500
_SHADOWING_LEVELS = 25

#: Fast-fading margin per transmission: a symmetric discrete draw in
#: 0.5 dB steps over [-3, +3] dB (13 levels) -- the small-scale
#: variation the decode check must survive at nominal SINR.
_FADING_STEP_MDB = 500
_FADING_LEVELS = 13

#: Thermal noise per PRB (30 kHz SCS, 12 subcarriers = 360 kHz) plus
#: a 7 dB receiver noise figure: -174 dBm/Hz + 10*log10(360e3) + 7 dB,
#: frozen as integer milli-dBm.
_NOISE_PER_PRB_MDBM = -111437

#: Power-ratio combination in the dB domain: the correction
#: 10*log10(1 + 10^(-delta/10)) in MILLI-DB for delta = 0..30 dB in
#: 1 dB steps (integer table; delta > 30 dB -> the weaker power is
#: negligible, correction 0).  Lets SINR combine interferers with pure
#: integer arithmetic.
_DB_COMBINE_MDB: Tuple[int, ...] = (
    3010, 2539, 2124, 1764, 1455, 1193, 973, 790, 639, 515,
    414, 332, 266, 212, 170, 135, 108, 86, 68, 54,
    43, 34, 27, 22, 17, 14, 11, 9, 7, 5, 4,
)

#: TS 38.214-inspired SINR -> MCS ladder (a documented simplification
#: of the CQI/MCS tables): each entry is (minimum SINR in milli-dB,
#: PRBs the bearer demands at that MCS for the baseline throughput
#: budget).  At healthy SINR (>= 12 dB) a bearer costs 1 PRB --
#: matching the reference engine's 1-PRB-per-bearer accounting; as
#: the channel degrades the bearer demands MORE PRBs until the cell
#: cannot afford it (channel-driven admission failure).
_MCS_LADDER: Tuple[Tuple[int, int], ...] = (
    (18000, 1),  # mcs 15
    (16000, 1),  # mcs 14
    (14000, 1),  # mcs 13
    (12000, 1),  # mcs 12
    (10000, 2),  # mcs 11
    (8000, 2),   # mcs 10
    (6500, 3),   # mcs 9
    (5000, 3),   # mcs 8
    (3500, 4),   # mcs 7
    (2000, 5),   # mcs 6
    (500, 7),    # mcs 5
    (-1000, 9),  # mcs 4
    (-2500, 10), # mcs 3
    (-4000, 12), # mcs 2
    (-5500, 15), # mcs 1
)

#: Below the mcs-1 SINR threshold there is no service at all.
_MCS_MIN_SINR_MDB = _MCS_LADDER[-1][0]

#: gNB transmit power (integer milli-dBm; a lab macro-cell EIRP
#: starting point -- TR 38.901 BS power class shape).
_DEFAULT_TX_POWER_MDBM = 43000

#: Minimum received power for a cell to be a coverage candidate
#: (integer milli-dBm; an RSRP-style admission floor).
_ADMISSION_RX_MIN_MDBM = -110000

#: A live bearer whose current SINR is below this floor makes the
#: gNB health DEGRADED (still serviceable above the mcs threshold).
_HEALTHY_SINR_MIN_MDB = 13000


def _isqrt(n: int) -> int:
    """Exact integer square root (Newton's method, pure integer)."""
    if n < 0:
        raise ValueError("negative distance")
    if n < 2:
        return n
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x


def _path_loss_mdb(distance_m: int) -> int:
    """Integer path loss (milli-dB) from the frozen anchor table."""
    if distance_m <= _PATH_LOSS_ANCHORS[0][0]:
        return _PATH_LOSS_ANCHORS[0][1]
    if distance_m >= _PATH_LOSS_ANCHORS[-1][0]:
        overshoot = distance_m - _PATH_LOSS_ANCHORS[-1][0]
        return _PATH_LOSS_ANCHORS[-1][1] + overshoot * 52 // 10
    lo_d, lo_pl = _PATH_LOSS_ANCHORS[0]
    for hi_d, hi_pl in _PATH_LOSS_ANCHORS[1:]:
        if distance_m <= hi_d:
            span = hi_d - lo_d
            return lo_pl + (distance_m - lo_d) * (hi_pl - lo_pl) // span
        lo_d, lo_pl = hi_d, hi_pl
    return lo_pl


def _combine_powers_mdbm(strong: int, weak: int) -> int:
    """Combine two dBm powers (integer milli-dBm) via the frozen
    dB-addition table: result = strong + correction(strong - weak)."""
    delta_mdb = strong - weak
    if delta_mdb < 0:
        strong, weak = weak, strong
        delta_mdb = -delta_mdb
    delta_db = delta_mdb // 1000
    if delta_db >= len(_DB_COMBINE_MDB):
        return strong
    return strong + _DB_COMBINE_MDB[delta_db]


def _mcs_for_sinr(sinr_mdb: int) -> Optional[int]:
    """The highest MCS index whose SINR threshold is met (1-based;
    ``None`` when even mcs 1 is out of range)."""
    for index, (threshold, _prbs) in enumerate(_MCS_LADDER):
        if sinr_mdb >= threshold:
            return len(_MCS_LADDER) - index
    return None


def _mcs_threshold(mcs: int) -> int:
    """The minimum SINR (milli-dB) admitted for ``mcs`` (1-based)."""
    if mcs < 1 or mcs > len(_MCS_LADDER):
        raise ValueError("mcs out of range")
    return _MCS_LADDER[len(_MCS_LADDER) - mcs][0]


def _mcs_prbs(mcs: int) -> int:
    """The PRB demand of ``mcs`` (1-based)."""
    if mcs < 1 or mcs > len(_MCS_LADDER):
        raise ValueError("mcs out of range")
    return _MCS_LADDER[len(_MCS_LADDER) - mcs][1]


# ---------------------------------------------------------------------------
# Scenario (frozen pure-DATA configuration) + environment (mutable state)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RfSimScenario:
    """The frozen RF-simulation scenario configuration (pure DATA).

    ``seed`` drives every shadowing/fading draw (same seed + same
    geometry -> byte-identical channel outcomes; different seed ->
    genuinely different draws).  ``ue_positions`` is the UE inventory
    in attach order (integer meters).  ``cell_positions`` maps cell
    ids to integer-meter positions (cells default to the origin).
    ``tx_power_mdbm`` is the per-cell transmit power.  ``extra_loss_mdb``
    seeds per-cell additional propagation loss (obstruction/rain --
    the degradation the environment can also apply at runtime).
    """

    seed: str
    ue_positions: Tuple[Tuple[int, int], ...] = ((80, 60),)
    cell_positions: Mapping[str, Tuple[int, int]] = field(default_factory=dict)
    tx_power_mdbm: int = _DEFAULT_TX_POWER_MDBM
    extra_loss_mdb: Mapping[str, int] = field(default_factory=dict)


class RfSimEnvironment:
    """The mutable RF channel state + the integer channel computation.

    The battery scripts the environment IN PROCESS (never over the
    REST surface): UE mobility, per-cell degradation, and interference
    are environment-control operations, exactly like an RFsim harness
    scripts UE positions and propagation.  The ADAPTER side only ever
    sees the frozen REST surface -- the channel model drives what the
    peer answers on that surface.
    """

    def __init__(self, scenario: RfSimScenario) -> None:
        self._scenario = scenario
        self._ue_positions: List[Tuple[int, int]] = list(scenario.ue_positions)
        self._extra_loss: Dict[str, int] = dict(scenario.extra_loss_mdb)

    # -- scenario configuration (read-only views) -----------------------

    @property
    def scenario(self) -> RfSimScenario:
        return self._scenario

    def cell_position(self, cell_id: str) -> Tuple[int, int]:
        return self._scenario.cell_positions.get(cell_id, (0, 0))

    # -- environment control (battery scripting surface) ----------------

    def set_ue_position(self, index: int, x: int, y: int) -> None:
        """Move UE ``index`` (integer meters; mobility)."""
        if index < 0 or index >= len(self._ue_positions):
            raise ValueError("ue index out of range")
        if (
            isinstance(x, bool)
            or isinstance(y, bool)
            or not isinstance(x, int)
            or not isinstance(y, int)
        ):
            raise ValueError("positions must be integers")
        self._ue_positions[index] = (x, y)

    def ue_position(self, index: int) -> Tuple[int, int]:
        if index < 0 or index >= len(self._ue_positions):
            raise ValueError("ue index out of range")
        return self._ue_positions[index]

    @property
    def ue_count(self) -> int:
        return len(self._ue_positions)

    def apply_extra_loss(self, cell_id: str, milli_db: int) -> None:
        """Apply additional propagation loss to a cell (obstruction)."""
        if isinstance(milli_db, bool) or not isinstance(milli_db, int):
            raise ValueError("loss must be integer milli-dB")
        if milli_db < 0:
            raise ValueError("loss must be non-negative")
        self._extra_loss[cell_id] = milli_db

    def clear_extra_loss(self, cell_id: str) -> None:
        """Clear a cell's additional propagation loss (recovery)."""
        self._extra_loss.pop(cell_id, None)

    def current_extra_loss(self, cell_id: str) -> int:
        return self._extra_loss.get(cell_id, 0)

    # -- channel computation (all integer, all content-keyed) -----------

    def shadowing_mdb(self, cell_id: str, ue_index: int) -> int:
        """The stable per-(cell, UE) shadowing draw (TR 38.901 sigma=6 dB
        discretized; a PURE function of the scenario seed -- repeated
        queries return the same value)."""
        label = "shadow:%s:%d" % (cell_id, ue_index)
        level = _seeded_uint(self._scenario.seed, label, _SHADOWING_LEVELS)
        return (level - (_SHADOWING_LEVELS - 1) // 2) * _SHADOWING_STEP_MDB

    def fading_mdb(self, bearer_ref: str, tx_index: int) -> int:
        """The per-transmission fast-fading draw for a bearer (a PURE
        function of seed + bearer ref + transmission index -- content,
        never object id; stable for the same transmission)."""
        label = "fade:%s:%d" % (bearer_ref, tx_index)
        level = _seeded_uint(self._scenario.seed, label, _FADING_LEVELS)
        return (level - (_FADING_LEVELS - 1) // 2) * _FADING_STEP_MDB

    def _distance_m(self, cell_id: str, ue_index: int) -> int:
        cx, cy = self.cell_position(cell_id)
        ux, uy = self.ue_position(ue_index)
        return _isqrt((ux - cx) * (ux - cx) + (uy - cy) * (uy - cy))

    def received_power_mdbm(self, cell_id: str, ue_index: int) -> int:
        """Received power from ``cell_id`` at UE ``ue_index`` (integer
        milli-dBm): tx power - path loss - extra loss - shadowing."""
        distance = self._distance_m(cell_id, ue_index)
        loss = (
            _path_loss_mdb(distance)
            + self.current_extra_loss(cell_id)
            + self.shadowing_mdb(cell_id, ue_index)
        )
        return self._scenario.tx_power_mdbm - loss

    def sinr_mdb(
        self,
        serving_cell_id: str,
        ue_index: int,
        interferer_cell_ids: Tuple[str, ...] = (),
    ) -> int:
        """SINR at UE ``ue_index`` served by ``serving_cell_id``
        (integer milli-dB): serving rx power minus the dB-domain
        combination of noise + every interferer's rx power."""
        serving = self.received_power_mdbm(serving_cell_id, ue_index)
        interference = _NOISE_PER_PRB_MDBM
        for cell_id in interferer_cell_ids:
            if cell_id == serving_cell_id:
                continue
            interference = _combine_powers_mdbm(
                interference, self.received_power_mdbm(cell_id, ue_index)
            )
        return serving - interference


# ---------------------------------------------------------------------------
# HTTP plumbing (independent implementation of the frozen REST surface)
# ---------------------------------------------------------------------------


def _json_response(status: int, payload: Dict[str, Any]) -> Tuple[int, bytes]:
    return status, json.dumps(payload).encode("utf-8")


def _error(status: int, reason: str) -> Tuple[int, bytes]:
    return status, json.dumps({"reason": reason}).encode("utf-8")


class _RfSimHTTPServer(ThreadingHTTPServer):
    """A :class:`ThreadingHTTPServer` delegating control-surface
    requests to the owning :class:`RfSimRanPeer`."""

    def __init__(self, addr: Any, handler: Any, peer: "RfSimRanPeer") -> None:
        super().__init__(addr, handler)
        self._peer = peer

    def _handle_control(self, method: str, path: str, body: bytes) -> Tuple[int, bytes]:
        return self._peer._handle_control(method, path, body)


class _RfSimControlHandler(BaseHTTPRequestHandler):
    """Minimal O1/E2-style REST handler (real HTTP, real JSON) --
    this module's own plumbing, independent of ``conformance.py``."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        self._delegate("GET")

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        self._delegate("POST")

    def do_DELETE(self) -> None:  # noqa: N802 (stdlib naming)
        self._delegate("DELETE")

    def _delegate(self, method: str) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length > 0 else b""
        server: "_RfSimHTTPServer" = self.server  # type: ignore[assignment]
        try:
            response = server._handle_control(method, self.path, body)
        except Exception:  # noqa: BLE001 -- the peer must not crash
            response = _error(500, "internal")
        status, payload = response
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _RfGnbEntry:
    """Peer-private provisioned-gNB record (never core state)."""

    __slots__ = ("gnb_name", "cells", "topology")

    def __init__(
        self,
        gnb_name: str,
        cells: Dict[str, CellDescriptor],
        topology: RanSplitTopology,
    ) -> None:
        self.gnb_name = gnb_name
        self.cells = cells
        self.topology = topology


class _RfBearerEntry:
    """Peer-private bound-bearer record with its RADIO state.

    ``session_id`` is stored EXACTLY as provided (LOCK-006 read-only
    passthrough); the UE context (RNTI/DRB/QFI), the admitted MCS, and
    the UE index are peer-private adapter-side state that NEVER crosses
    the wire -- responses carry only the opaque ``ran:bearer:<hex>``
    ref and the mapped serving cell.
    """

    __slots__ = (
        "session_id",
        "gnb_ref",
        "cell_id",
        "ue_context",
        "ue_index",
        "admitted_mcs",
        "admitted_sinr_mdb",
        "tx_count",
    )

    def __init__(
        self,
        session_id: str,
        gnb_ref: str,
        cell_id: str,
        ue_context: RanUeContext,
        ue_index: int,
        admitted_mcs: int,
        admitted_sinr_mdb: int,
    ) -> None:
        self.session_id = session_id
        self.gnb_ref = gnb_ref
        self.cell_id = cell_id
        self.ue_context = ue_context
        self.ue_index = ue_index
        self.admitted_mcs = admitted_mcs
        self.admitted_sinr_mdb = admitted_sinr_mdb
        self.tx_count = 0


class RfSimRanPeer:
    """A real REST-over-HTTP RAN control-plane peer backed by the
    RF-simulation channel model.

    Runs as user ``z`` (no root).  Starts a real
    :class:`ThreadingHTTPServer` on ``127.0.0.1:<ephemeral>`` serving
    the SAME frozen O1/E2-style control surface the production
    :class:`~.openran.OpenRanAdapter` speaks (and the same surface the
    in-repo conformance peer serves) -- but the answers are derived
    from :class:`RfSimEnvironment`'s radio state.  Use as a context
    manager or call :meth:`close`.

    This peer is an RF SIMULATION (the OAI-RFsim analogue): it is
    FORBIDDEN as an SDR-lab substitution in the interop gate and can
    never close the frozen SDR acceptance criterion.
    """

    def __init__(
        self,
        scenario: Optional[RfSimScenario] = None,
        *,
        host: str = "127.0.0.1",
    ) -> None:
        self._environment = RfSimEnvironment(
            scenario if scenario is not None else RfSimScenario(seed="adcos-rfsim-default")
        )
        self._host = host
        # One reentrant mutation lock: the threading HTTP server may
        # dispatch concurrent requests, and the diagnostics helpers
        # below take the same lock while already holding it -- peer
        # mutations + channel reads must stay deterministic (the
        # conformance peer has the same exposure with a plain Lock;
        # this peer's radio-state diagnostics nest, hence RLock).
        self._lock = threading.RLock()
        # Deterministic counters (no wall clock, no randomness) --
        # mirrors of the reference engine's counters so identical
        # operation histories mint identical references.
        self._sequence = 0
        self._rnti_next = FIRST_RNTI
        self._ue_attach_next = 0
        # gnb_ref -> provisioned gNB (insertion order = provision order).
        self._gnbs: Dict[str, _RfGnbEntry] = {}
        # bearer_ref -> bound bearer (session_id stored EXACTLY as given).
        self._bearers: Dict[str, _RfBearerEntry] = {}
        # alloc_ref -> purpose (radio-capacity reservations).
        self._allocations: Dict[str, str] = {}
        # Real HTTP server (the simulated RAN control plane).
        self._http = _RfSimHTTPServer((host, 0), _RfSimControlHandler, self)
        self._http.timeout = 5
        self._http_thread = threading.Thread(target=self._http.serve_forever, daemon=True)
        self._http_thread.start()

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    @property
    def environment(self) -> RfSimEnvironment:
        """The mutable RF channel environment (battery scripting
        surface: UE mobility, degradation, interference)."""
        return self._environment

    @property
    def port(self) -> int:
        """The ephemeral port the real HTTP server listens on."""
        return int(self._http.server_address[1])

    @property
    def base_url(self) -> str:
        return "http://%s:%d" % (self._host, self.port)

    def close(self) -> None:
        """Shut the HTTP server down and release the socket."""
        try:
            self._http.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._http.server_close()
        except Exception:  # noqa: BLE001
            pass
        self._http_thread.join(timeout=5)

    def __enter__(self) -> "RfSimRanPeer":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Radio-state diagnostics (peer-private; NOT on the REST surface;
    # no session_id/RNTI/DRB material -- LOCK-023-clean by construction)
    # ------------------------------------------------------------------

    def bearer_radio_state(self, bearer_ref: str) -> Optional[Dict[str, Any]]:
        """The radio state of a live bearer (diagnostic view for the
        deterministic evidence runs): serving cell, UE index, admitted
        MCS/SINR, CURRENT SINR (no fading), and PRB demand."""
        with self._lock:
            bearer = self._bearers.get(bearer_ref)
            if bearer is None:
                return None
            current = self._current_sinr(bearer)
            return {
                "cell_id": bearer.cell_id,
                "ue_index": bearer.ue_index,
                "admitted_mcs": bearer.admitted_mcs,
                "admitted_sinr_mdb": bearer.admitted_sinr_mdb,
                "current_sinr_mdb": current,
                "prb_demand": _mcs_prbs(bearer.admitted_mcs),
            }

    def radio_report(self) -> List[Dict[str, Any]]:
        """The sorted radio state of every live bearer (the
        deterministic RF-simulation evidence view)."""
        with self._lock:
            report = []
            for bearer_ref in sorted(self._bearers):
                state = self.bearer_radio_state(bearer_ref)
                if state is not None:
                    report.append({"bearer_ref": bearer_ref, **state})
            return report

    def radio_report_bytes(self) -> bytes:
        """Canonical bytes of the radio report (determinism proof)."""
        return to_canonical_bytes(self.radio_report())

    # ------------------------------------------------------------------
    # Request entry point
    # ------------------------------------------------------------------

    def _handle_control(self, method: str, path: str, body: bytes) -> Tuple[int, bytes]:
        with self._lock:
            return self._dispatch(method, path, body)

    def _dispatch(self, method: str, path: str, body: bytes) -> Tuple[int, bytes]:
        segments = [unquote(segment) for segment in path.split("/") if segment]
        if method == "GET" and segments == ["capabilities"]:
            return _json_response(200, {"capabilities": list(self._current_capabilities())})
        if method == "GET" and segments == ["state"]:
            return _json_response(200, self._state_view())
        if method == "POST" and segments == ["gnb"]:
            return self._handle_provision(body)
        if method == "DELETE" and len(segments) == 2 and segments[0] == "gnb":
            return self._handle_decommission(segments[1])
        if (
            method == "POST"
            and len(segments) == 5
            and segments[0] == "gnb"
            and segments[2] == "cells"
            and segments[4] in ("activate", "deactivate")
        ):
            return self._handle_cell_transition(segments[1], segments[3], segments[4])
        if method == "POST" and segments == ["bearers"]:
            return self._handle_bind(body)
        if method == "DELETE" and len(segments) == 2 and segments[0] == "bearers":
            return self._handle_unbind(segments[1])
        if method == "POST" and len(segments) == 3 and segments[0] == "bearers" and segments[2] == "data":
            return self._handle_data(segments[1], body)
        if method == "POST" and segments == ["allocations"]:
            return self._handle_allocate(body)
        if method == "DELETE" and len(segments) == 2 and segments[0] == "allocations":
            return self._handle_release(segments[1])
        return _error(404, "path-not-found")

    @staticmethod
    def _parse_body(body: bytes) -> Optional[Dict[str, Any]]:
        if not body:
            return None
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    # ------------------------------------------------------------------
    # RF-simulation RAN model (channel-derived, not registry bookkeeping)
    # ------------------------------------------------------------------

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _active_cells(self) -> List[Tuple[str, str, CellDescriptor]]:
        """Every ACTIVE cell across all gNBs (gnb insertion order, then
        cell insertion order -- the deterministic iteration order for
        geometric selection ties)."""
        result: List[Tuple[str, str, CellDescriptor]] = []
        for gnb_ref, entry in self._gnbs.items():
            for cell_id, cell in entry.cells.items():
                if cell.state == CellState.ACTIVE:
                    result.append((gnb_ref, cell_id, cell))
        return result

    def _cell_prbs_used(self, gnb_ref: str, cell_id: str) -> int:
        used = 0
        for bearer in self._bearers.values():
            if bearer.gnb_ref == gnb_ref and bearer.cell_id == cell_id:
                used += _mcs_prbs(bearer.admitted_mcs)
        return used

    def _current_sinr(self, bearer: _RfBearerEntry) -> int:
        """The bearer's CURRENT SINR (stable shadowing, current UE
        position, current degradation -- no fast fading)."""
        interferers = tuple(
            cell_id
            for _gnb_ref, cell_id, _cell in self._active_cells()
            if cell_id != bearer.cell_id
        )
        return self._environment.sinr_mdb(bearer.cell_id, bearer.ue_index, interferers)

    def _current_capabilities(self) -> Tuple[str, ...]:
        served = {RAN_CAPABILITY_GNB_PROVISION}
        active = tuple(
            cell
            for entry in self._gnbs.values()
            for cell in entry.cells.values()
            if cell.state == CellState.ACTIVE
        )
        if any(cell.duplex == DuplexMode.TDD for cell in active):
            served.add(RAN_CAPABILITY_CELL_TDD)
        if any(cell.duplex == DuplexMode.FDD for cell in active):
            served.add(RAN_CAPABILITY_CELL_FDD)
        if self._bearers:
            served.add(RAN_CAPABILITY_DRB_QOS_FLOW)
        for entry in self._gnbs.values():
            elements = (entry.topology.cu, *entry.topology.dus, *entry.topology.rus)
            for element in elements:
                if element.split == RanSplitOption.F1_CU_DU:
                    served.add(RAN_CAPABILITY_CU_DU_SPLIT_F1)
                if element.split == RanSplitOption.O_RAN_7_2X:
                    served.add(RAN_CAPABILITY_O_RU_FRONTHAUL)
        return tuple(cap for cap in RAN_CAPABILITY_REFERENCES if cap in served)

    def _health_view(self) -> Dict[str, Any]:
        """Per-element health view with the CHANNEL-derived degradation:
        a live bearer whose current SINR fell below the healthy floor
        (or whose cell went INACTIVE) makes the gNB DEGRADED -- radio
        state the registry-only conformance peer cannot see."""
        degraded_gnb_refs = set()
        for bearer in self._bearers.values():
            entry = self._gnbs.get(bearer.gnb_ref)
            cell = entry.cells.get(bearer.cell_id) if entry is not None else None
            if cell is None or cell.state != CellState.ACTIVE:
                degraded_gnb_refs.add(bearer.gnb_ref)
                continue
            if self._current_sinr(bearer) < _HEALTHY_SINR_MIN_MDB:
                degraded_gnb_refs.add(bearer.gnb_ref)
        gnb_states: List[str] = []
        cu_states: List[str] = []
        du_states: List[str] = []
        ru_states: List[str] = []
        cell_states: Dict[str, str] = {}
        for gnb_ref, entry in self._gnbs.items():
            elements = (entry.topology.cu, *entry.topology.dus, *entry.topology.rus)
            if any(element.state == HealthState.FAILED for element in elements):
                gnb_state = HealthState.FAILED
            elif (
                any(element.state == HealthState.DEGRADED for element in elements)
                or any(cell.state == CellState.INACTIVE for cell in entry.cells.values())
                or gnb_ref in degraded_gnb_refs
            ):
                gnb_state = HealthState.DEGRADED
            else:
                gnb_state = HealthState.HEALTHY
            gnb_states.append(gnb_state)
            cu_states.append(entry.topology.cu.state)
            du_states.extend(du.state for du in entry.topology.dus)
            ru_states.extend(ru.state for ru in entry.topology.rus)
            for cell_id, cell in entry.cells.items():
                cell_states[cell_id] = cell.state
        if any(state == HealthState.FAILED for state in gnb_states):
            overall_gnb = HealthState.FAILED
        elif any(state == HealthState.DEGRADED for state in gnb_states):
            overall_gnb = HealthState.DEGRADED
        else:
            overall_gnb = HealthState.HEALTHY
        if any(state == HealthState.FAILED for state in cu_states):
            overall_cu = HealthState.FAILED
        elif any(state == HealthState.DEGRADED for state in cu_states):
            overall_cu = HealthState.DEGRADED
        else:
            overall_cu = HealthState.HEALTHY
        return {
            "gnb_state": overall_gnb,
            "cu_state": overall_cu,
            "du_states": du_states,
            "ru_states": ru_states,
            "cell_states": dict(sorted(cell_states.items())),
            "ngap_connected": bool(self._gnbs),
        }

    def _resources_view(self) -> Dict[str, Any]:
        """Integer PRB/RRC/DRB accounting with CHANNEL-DERIVED PRB
        demand: a bearer consumes the PRBs its admitted MCS requires
        (1 PRB at healthy SINR -- the reference engine's accounting;
        more as the channel degrades)."""
        active = tuple(
            cell
            for entry in self._gnbs.values()
            for cell in entry.cells.values()
            if cell.state == CellState.ACTIVE
        )
        prb_used = 0
        for bearer in self._bearers.values():
            entry = self._gnbs.get(bearer.gnb_ref)
            cell = entry.cells.get(bearer.cell_id) if entry is not None else None
            if cell is not None and cell.state == CellState.ACTIVE:
                prb_used += _mcs_prbs(bearer.admitted_mcs)
        return {
            "prb_total": sum(cell.prb_count for cell in active),
            "prb_used": prb_used,
            "rrc_connected_ue_count": len(self._bearers),
            "active_drb_count": len(self._bearers),
        }

    def _state_view(self) -> Dict[str, Any]:
        topology: Optional[Dict[str, Any]] = None
        for entry in self._gnbs.values():
            topology = entry.topology.to_dict()
            break
        return {
            "health": self._health_view(),
            "resources": self._resources_view(),
            "topology": topology,
        }

    def _select_serving_cell(self) -> Optional[Tuple[str, str, CellDescriptor, int, int, int]]:
        """GEOMETRIC serving-cell selection: among ACTIVE cells with
        free PRB capacity, the one with the STRONGEST received power
        at the NEXT UE's position (ties resolved by the deterministic
        gNB-then-cell insertion order -- NOT the reference engine's
        first-fit).  Returns ``(gnb_ref, cell_id, cell, ue_index,
        rx_mdbm, sinr_mdb)`` or ``None`` when no candidate both covers
        the UE (rx power at/above the admission floor) and supports
        at least mcs 1 (SINR at/above the mcs-1 threshold) with the
        PRBs it demands."""
        ue_index = self._ue_attach_next
        if ue_index >= self._environment.ue_count:
            return None
        best: Optional[Tuple[int, str, str, CellDescriptor, int, int]] = None
        for gnb_ref, cell_id, cell in self._active_cells():
            used = self._cell_prbs_used(gnb_ref, cell_id)
            rx = self._environment.received_power_mdbm(cell_id, ue_index)
            if rx < _ADMISSION_RX_MIN_MDBM:
                continue
            interferers = tuple(
                other_cell_id
                for _other_gnb, other_cell_id, _other in self._active_cells()
                if other_cell_id != cell_id
            )
            sinr = self._environment.sinr_mdb(cell_id, ue_index, interferers)
            mcs = _mcs_for_sinr(sinr)
            if mcs is None:
                continue
            if _mcs_prbs(mcs) > cell.prb_count - used:
                continue
            if best is None or rx > best[0]:
                best = (rx, gnb_ref, cell_id, cell, ue_index, sinr)
        if best is None:
            return None
        _rx, gnb_ref, cell_id, cell, index, sinr = best
        return gnb_ref, cell_id, cell, index, best[0], sinr

    # ------------------------------------------------------------------
    # Endpoint handlers
    # ------------------------------------------------------------------

    def _handle_provision(self, body: bytes) -> Tuple[int, bytes]:
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        try:
            raw_cells = request.get("cells")
            if not isinstance(raw_cells, list) or not raw_cells:
                raise KeyError("cells")
            if any(not isinstance(raw, dict) for raw in raw_cells):
                raise KeyError("cells")
            cells = tuple(
                CellSpec(
                    cell_id=raw["cell_id"],
                    band=raw["band"],
                    duplex=raw["duplex"],
                    numerology=raw["numerology"],
                    arfcn=raw["arfcn"],
                    prb_count=raw["prb_count"],
                )
                for raw in raw_cells
            )
            provision = GnbProvisionRequest(
                gnb_name=request["name"],
                cells=cells,
                topology=self._parse_topology(request.get("topology")),
            )
            validate_gnb_provision_request(provision)
        except (KeyError, TypeError, ValueError):
            return _error(400, "invalid-input")
        sequence = self._next_sequence()
        gnb_ref = _mint_ref(
            "gnb",
            {
                "gnb_name": provision.gnb_name,
                "cells": [cell.to_dict() for cell in provision.cells],
                "topology": provision.topology.to_dict(),
                "sequence": sequence,
            },
        )
        if gnb_ref in self._gnbs:
            return _error(409, "binding-exists")
        self._gnbs[gnb_ref] = _RfGnbEntry(
            gnb_name=provision.gnb_name,
            cells={
                cell.cell_id: CellDescriptor(
                    cell_id=cell.cell_id,
                    band=cell.band,
                    duplex=cell.duplex,
                    numerology=cell.numerology,
                    arfcn=cell.arfcn,
                    prb_count=cell.prb_count,
                    state=CellState.INACTIVE,
                )
                for cell in provision.cells
            },
            topology=provision.topology,
        )
        return _json_response(201, {"gnb_ref": gnb_ref})

    @staticmethod
    def _parse_topology(raw: Any) -> RanSplitTopology:
        if not isinstance(raw, dict):
            raise KeyError("topology")
        cu_raw = raw.get("cu")
        dus_raw = raw.get("dus")
        rus_raw = raw.get("rus")
        if not isinstance(cu_raw, dict) or not isinstance(dus_raw, list) or not isinstance(rus_raw, list):
            raise KeyError("topology")
        if any(not isinstance(item, dict) for item in dus_raw + rus_raw):
            raise KeyError("topology")
        if any(not isinstance(item.get("cell_ids"), list) for item in dus_raw):
            raise KeyError("topology")
        try:
            cu = CuElement(
                element_id=cu_raw["element_id"],
                split=cu_raw["split"],
                state=cu_raw["state"],
            )
            dus = tuple(
                DuElement(
                    element_id=du["element_id"],
                    split=du["split"],
                    state=du["state"],
                    cell_ids=tuple(du["cell_ids"]),
                )
                for du in dus_raw
            )
            rus = tuple(
                RuElement(
                    element_id=ru["element_id"],
                    split=ru["split"],
                    state=ru["state"],
                    band=ru["band"],
                )
                for ru in rus_raw
            )
            return RanSplitTopology(cu=cu, dus=dus, rus=rus)
        except (KeyError, TypeError, ValueError):
            raise KeyError("topology") from None

    def _handle_decommission(self, gnb_ref: str) -> Tuple[int, bytes]:
        entry = self._gnbs.get(gnb_ref)
        if entry is None:
            return _error(404, "gnb-unknown")
        if any(bearer.gnb_ref == gnb_ref for bearer in self._bearers.values()):
            return _error(409, "binding-exists")
        del self._gnbs[gnb_ref]
        return _json_response(200, {"status": "decommissioned"})

    def _handle_cell_transition(self, gnb_ref: str, cell_id: str, action: str) -> Tuple[int, bytes]:
        entry = self._gnbs.get(gnb_ref)
        if entry is None:
            return _error(404, "gnb-unknown")
        cell = entry.cells.get(cell_id)
        if cell is None:
            return _error(404, "cell-unknown")
        target = CellState.ACTIVE if action == "activate" else CellState.INACTIVE
        if cell.state == target:
            return _error(400, "invalid-input")
        entry.cells[cell_id] = CellDescriptor(
            cell_id=cell.cell_id,
            band=cell.band,
            duplex=cell.duplex,
            numerology=cell.numerology,
            arfcn=cell.arfcn,
            prb_count=cell.prb_count,
            state=target,
        )
        return _json_response(
            200, {"status": "active" if target == CellState.ACTIVE else "inactive"}
        )

    def _handle_bind(self, body: bytes) -> Tuple[int, bytes]:
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        session_id = request.get("session_id")
        requirements = request.get("requirements")
        if requirements is not None and not isinstance(requirements, dict):
            return _error(400, "invalid-input")
        if not isinstance(session_id, str):
            return _error(400, "invalid-input")
        try:
            validate_session_id(session_id)
        except ValueError:
            return _error(400, "invalid-input")
        if not self._gnbs:
            return _error(404, "gnb-unknown")
        # Radio admission: geometric serving-cell selection with
        # coverage (rx power) + link-budget (SINR/MCS) + PRB-capacity
        # gates -- failures the registry-only conformance peer cannot
        # produce for the same operation history.
        choice = self._select_serving_cell()
        if choice is None:
            return _error(503, "ran-unavailable")
        gnb_ref, cell_id, _cell, ue_index, _rx, sinr = choice
        rnti = self._rnti_next
        if rnti > LAST_RNTI:
            return _error(503, "ran-unavailable")
        self._rnti_next += 1
        sequence = self._next_sequence()
        ue_ref = _mint_ref("ue", {"session_id": session_id, "rnti": rnti, "sequence": sequence})
        ue_context = RanUeContext(
            ue_ref=ue_ref,
            rnti=rnti,
            drbs=(RanDrb(drb_id=1, qfi=5),),
        )
        bearer_ref = _mint_ref(
            "bearer",
            {
                "session_id": session_id,
                "gnb_ref": gnb_ref,
                "cell_id": cell_id,
                "rnti": rnti,
                "sequence": sequence,
            },
        )
        if bearer_ref in self._bearers:
            return _error(409, "binding-exists")
        self._bearers[bearer_ref] = _RfBearerEntry(
            session_id=session_id,
            gnb_ref=gnb_ref,
            cell_id=cell_id,
            ue_context=ue_context,
            ue_index=ue_index,
            admitted_mcs=_mcs_for_sinr(sinr) or 1,
            admitted_sinr_mdb=sinr,
        )
        self._ue_attach_next += 1
        # Only the opaque ref + the mapped serving cell cross the wire
        # -- the UE context (RNTI/DRB/QFI) and the radio state are
        # peer-private.
        return _json_response(201, {"bearer_ref": bearer_ref, "cell_id": cell_id})

    def _handle_unbind(self, bearer_ref: str) -> Tuple[int, bytes]:
        if bearer_ref not in self._bearers:
            return _error(404, "bearer-unknown")
        del self._bearers[bearer_ref]
        return _json_response(200, {"status": "released"})

    def _handle_data(self, bearer_ref: str, body: bytes) -> Tuple[int, bytes]:
        bearer = self._bearers.get(bearer_ref)
        if bearer is None:
            return _error(404, "bearer-unknown")
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        payload_b64 = request.get("payload_b64")
        if not isinstance(payload_b64, str) or not payload_b64:
            return _error(400, "invalid-input")
        try:
            payload = base64.b64decode(payload_b64, validate=True)
        except (TypeError, ValueError):
            return _error(400, "invalid-input")
        entry = self._gnbs.get(bearer.gnb_ref)
        cell = entry.cells.get(bearer.cell_id) if entry is not None else None
        if cell is None or cell.state != CellState.ACTIVE:
            return _error(503, "ran-unavailable")
        # Radio-conditioned delivery: the CURRENT SINR (with a seeded
        # fast-fading draw keyed by bearer ref + transmission index)
        # must still support the ADMITTED MCS, else the transmission
        # fails closed (a typed 503 -- never a corrupted echo).
        tx_index = bearer.tx_count
        fading = self._environment.fading_mdb(bearer_ref, tx_index)
        effective = self._current_sinr(bearer) + fading
        bearer.tx_count += 1
        if effective < _mcs_threshold(bearer.admitted_mcs):
            return _error(503, "ran-unavailable")
        # Byte-identical user-plane echo over the simulated channel.
        echoed = base64.b64encode(payload).decode("ascii")
        return _json_response(200, {"payload_b64": echoed})

    def _handle_allocate(self, body: bytes) -> Tuple[int, bytes]:
        request = self._parse_body(body)
        if request is None:
            return _error(400, "invalid-input")
        kind = request.get("kind")
        quantity_base = request.get("quantity_base")
        purpose = request.get("purpose")
        if not isinstance(kind, str) or kind not in RAN_ALLOCATION_KINDS:
            return _error(400, "invalid-input")
        if isinstance(quantity_base, bool) or not isinstance(quantity_base, int) or quantity_base < 0:
            return _error(400, "invalid-input")
        if not isinstance(purpose, str) or not purpose:
            return _error(400, "invalid-input")
        try:
            reject_credential_like_text(purpose, what="purpose")
        except ValueError:
            return _error(400, "invalid-input")
        sequence = self._next_sequence()
        alloc_ref = _mint_ref(
            "alloc",
            {
                "kind": kind,
                "quantity_base": quantity_base,
                "purpose": purpose,
                "sequence": sequence,
            },
        )
        if alloc_ref in self._allocations:
            return _error(409, "binding-exists")
        self._allocations[alloc_ref] = purpose
        return _json_response(201, {"technology_ref": alloc_ref})

    def _handle_release(self, alloc_ref: str) -> Tuple[int, bytes]:
        if alloc_ref not in self._allocations:
            return _error(404, "allocation-unknown")
        del self._allocations[alloc_ref]
        return _json_response(200, {"status": "released"})
