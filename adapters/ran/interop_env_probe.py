"""ADCOS Open RAN interop environment-capability probe + anti-faking
guard (WORK-020).

The W019 hardening pattern (Architect-accepted for the fivegc B1 gate,
mirrored here family-internally with the RAN vocabulary).  The probe
does two things and only two things:

  1. Replace the gate's opaque ``UNREACHABLE`` string with an EXPLICIT,
     structured SDR-lab environment-capability matrix
     (``[SDR-LAB CAPABILITY MATRIX]``) so a future run on capable
     infrastructure fails or passes unambiguously instead of reporting
     an opaque skip.

  2. Add a HARD anti-faking ``peer_kind`` guard: when the operator
     EXPLICITLY tags the peer as an in-repo reference/conformance peer
     (``RAN_PEER_KIND=reference|inrepo|conformance_server|simulator``)
     the gate returns ``FORBIDDEN`` -- NOT a SKIP, NOT a PASS -- so the
     forbidden substitution (pointing the gate at the in-repo
     :class:`adapters.ran.conformance.ReferenceRanConformanceServer`
     instead of a real, independent SDR-based RAN lab) is enforced in
     code rather than prose.  The guard fires BEFORE any network probe:
     when a forbidden kind is asserted, the control-endpoint
     reachability check is deliberately NOT executed.

ACCEPTANCE SEMANTICS -- UNCHANGED
---------------------------------
This module introduces NO new PASS path.  The gate STILL reports
``PASSED`` ONLY after real evidence of a real SDR present ->
real control-plane interaction -> real cell activation on the real
SDR -> real UE attach through the radio -> a real data radio bearer
bound to an ADCOS session_id -> ordinary application bytes received
end-to-end byte-identical.  That PASSED path lives in the UNCHANGED
real interop gate (:func:`adapters.ran.openran_interop.
run_openran_interop`); this module only enriches the
``UNREACHABLE``/``FORBIDDEN`` branches and the preflight.

The independence guard is a PREFLIGHT assertion, not a runtime proof.
It catches the EXPLICIT forbidden assertion (operator says
``reference``).  It does NOT catch a lying operator who sets
``RAN_PEER_KIND=real_oai`` while pointing at the in-repo conformance
peer -- that is caught at RUNTIME by the real interop gate: the
frozen criterion is an SDR-BASED lab topology, and the [SDR] evidence
line is earned from device/driver evidence in the environment (the
``sdr_driver`` probe below), NEVER from the control plane alone, so a
control-plane-only peer can never close the criterion.  The guard
makes the operator's independence claim explicit and auditable; the
gate does the actual independence verification.

The in-repo conformance peer binds to ``127.0.0.1`` on EPHEMERAL ports
(see :class:`ReferenceRanConformanceServer.__init__`), so there is no
fixed host:port signature a denylist could match; the guard therefore
relies on the explicit ``RAN_PEER_KIND`` assertion.
``_FORBIDDEN_HOST_FRAGMENTS`` is an integrator-populated denylist for
any FUTURE reference-peer signature that acquires a fixed endpoint.

RAN_INTEROP_RUNBOOK (external SDR-lab environment)
--------------------------------------------------
To produce the acceptance evidence the frozen WORK-020 criterion
requires ("at least one SDR-based lab topology works" + required
verification "end-to-end lab tests" + DoD "ADCOS can provision/use a
standards-compliant 5G access path"), run the gate ON THE LAB HOST
(the [SDR] evidence line is device-node/driver evidence, so the host
running the gate must be the host that carries the SDR).  At minimum:

  1. A Linux lab host with SCTP support (NGAP/F1 transport), build
     tools (``cmake``/``gcc``/``meson``/``ninja``), a USB3 bus, and a
     USRP B2xx/N2xx-class SDR attached (root access or a udev rule
     exposing the ``/dev/usrp*`` device nodes).
  2. Build an OpenAirInterface gNB (or an O-RAN O-DU/O-RU combination)
     from upstream sources, against the attached SDR.
  3. Attach a UE: the OAI UE on a second SDR, or a COTS UE carrying a
     test SIM for the lab PLMN.
  4. Expose the stack's O1/E2-style control endpoint (or an OAI
     control bridge translating the frozen REST control surface) at
     ``RAN_CONTROL_URL`` on the lab host.
  5. Run the gate with::

       RAN_INTEROP=1
       RAN_PEER_KIND=real_oai
       RAN_CONTROL_URL=http://<lab-host>:9091

     The URL MUST NOT target the in-repo conformance peer (setting
     ``RAN_PEER_KIND=reference`` or any of ``inrepo``/
     ``conformance_server``/``simulator`` is a hard FORBIDDEN).

On a real run the gate MUST produce, and the reviewer MUST attach as
acceptance evidence, the six evidence lines::

  [SDR]  real SDR hardware present (device node / driver evidence)
  [CTRL] real control-plane interaction (capabilities + state from the real stack)
  [CELL] real cell activation on the real SDR (RF on air)
  [UE]   real UE attach through the radio (RRC connected)
  [DRB]  real data radio bearer bound to an ADCOS session_id
  [IP]   real end-to-end application bytes (payload equality + SHA-256)

Until all six evidence lines are produced from a real, independent
SDR-based RAN lab, the gate remains ``UNREACHABLE``/``FORBIDDEN``/
``FAILED`` and WORK-020's SDR-lab criterion is NOT accepted.  This
probe CANNOT turn ``SKIP`` into acceptance -- it can only make the
verification-environment limitation explicit.
"""

from __future__ import annotations

import os
import shutil
import socket as _socket
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from .openran import DEFAULT_RAN_CONTROL_URL

__all__ = [
    "RAN_PEER_KIND_ENV",
    "RanCheck",
    "RanCapabilityReport",
    "RanEnvProbeConfig",
    "probe_ran_interop_capability",
]


#: The environment variable carrying the operator's peer-kind assertion
#: (``real_oai``/``real_oran``/``real_sdr``/``real_other_ran`` for a
#: real, independent peer; ``reference``/``inrepo``/
#: ``conformance_server``/``simulator`` are the FORBIDDEN kinds).
RAN_PEER_KIND_ENV = "RAN_PEER_KIND"

#: Bounded connect timeout for the control-endpoint TCP reachability
#: probe (an I/O bound; never a source of wall-clock-derived state).
_CONNECT_TIMEOUT_SECONDS = 2.0


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RanCheck:
    """A single SDR-lab environment-capability probe result.

    ``available`` is ``True`` only when the probed capability was
    affirmatively found; ``detail`` records WHAT was probed and what
    was actually found (the matrix is evidence, never a guess).
    """

    name: str
    available: bool
    detail: str = ""


@dataclass(frozen=True)
class RanCapabilityReport:
    """Preflight report for the WORK-020 real SDR-lab interop gate.

    ``reachable`` is ``True`` ONLY when no forbidden substitution was
    detected AND every environment-capability check passed.  It is
    NEVER ``True`` via faking; the ``PASSED`` acceptance outcome is
    produced only by the real interop gate, not here.
    """

    reachable: bool
    checks: Tuple[RanCheck, ...]
    forbidden_substitution: Optional[str] = None

    def summary(self) -> str:
        """Render the explicit multi-line capability matrix.

        Mirrors the fivegc renderer's discipline: the ``[ok ]``/``[miss]``
        tag column, the trailing ``.rstrip()`` applied to the FORMATTED
        string (never to the tuple -- the fivegc renderer hit exactly
        that bug once), and a ``[GATE]`` verdict line that is always a
        non-acceptance verdict unless every check passed.
        """
        lines: List[str] = [
            "[SDR-LAB CAPABILITY MATRIX] reachable=%s" % self.reachable
        ]
        for c in self.checks:
            lines.append(
                ("  %-18s [%s] %s" % (c.name, "ok " if c.available else "miss", c.detail)).rstrip()
            )
        if self.forbidden_substitution:
            lines.append("[FORBIDDEN] %s" % self.forbidden_substitution)
        if self.forbidden_substitution:
            lines.append("[GATE] FORBIDDEN (anti-faking rule violated; not acceptance)")
        elif not self.reachable:
            lines.append(
                "[GATE] UNREACHABLE (verification-environment limitation; not acceptance)"
            )
        else:
            lines.append(
                "[GATE] preflight passed; proceed to the real interop gate"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gate configuration (env-driven; the gate passes its own
# RanInteropConfig separately -- this config drives the probe only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RanEnvProbeConfig:
    """Minimal env-driven config for the capability probe.

    ``from_env`` reads exactly two variables (``RAN_CONTROL_URL`` with
    its default, ``RAN_PEER_KIND``) and nothing else.
    """

    control_url: str = DEFAULT_RAN_CONTROL_URL
    peer_kind: str = ""

    @classmethod
    def from_env(cls) -> "RanEnvProbeConfig":
        return cls(
            control_url=os.environ.get("RAN_CONTROL_URL", "").strip()
            or DEFAULT_RAN_CONTROL_URL,
            peer_kind=os.environ.get(RAN_PEER_KIND_ENV, "").strip(),
        )


# ---------------------------------------------------------------------------
# Anti-faking independence guard (encodes the Architect's no-faking rule
# in code).  Fires FORBIDDEN on an EXPLICIT in-repo-peer assertion --
# BEFORE any network probe.
# ---------------------------------------------------------------------------

#: Asserted-real peer kinds (a real, independent SDR-based RAN lab).
_PEER_KIND_REAL: Tuple[str, ...] = (
    "real_oai",
    "real_oran",
    "real_sdr",
    "real_other_ran",
)

#: FORBIDDEN peer kinds (in-repo reference/conformance peers and any
#: simulator substitution -- they can NEVER satisfy the frozen
#: SDR-based lab topology criterion, not even as a fallback).
_PEER_KIND_FORBIDDEN: Tuple[str, ...] = (
    "reference",
    "inrepo",
    "conformance_server",
    "simulator",
)

#: Integrator-populated host-fragment denylist for any FUTURE
#: reference-peer signature that acquires a fixed endpoint.  The
#: in-repo conformance peer uses ephemeral ports today, so there is no
#: reliable fixed signature; the primary anti-faking signal is the
#: explicit ``RAN_PEER_KIND`` assertion.
_FORBIDDEN_HOST_FRAGMENTS: Tuple[str, ...] = ()


def _assert_independent_peer(config: RanEnvProbeConfig) -> Optional[str]:
    """Return a FORBIDDEN reason string if the configured peer is an
    explicitly-asserted in-repo reference/conformance peer or
    simulator; otherwise ``None``.

    NEVER returns acceptance.  The guard is a preflight assertion; the
    runtime independence verification is the real interop gate's job
    (the [SDR] evidence line is environment/device evidence, so a
    control-plane-only peer can never close the frozen criterion).
    """
    kind = config.peer_kind.strip().lower()
    if kind in _PEER_KIND_FORBIDDEN:
        return (
            "RAN_PEER_KIND=%r; the gate forbids running acceptance "
            "against an in-repo reference/conformance peer or simulator "
            "(Architect rule: the in-repo reference/conformance peer "
            "cannot satisfy the frozen SDR-based lab topology criterion "
            "-- no in-repo peer may be substituted for a real, "
            "independent SDR-based RAN lab)" % kind
        )
    if kind not in _PEER_KIND_REAL:
        # Unset (or unrecognized) -- the operator did not assert a real
        # peer.  This is NOT a forbidden substitution (the operator did
        # not claim the in-repo peer); the gate proceeds and the real
        # interop gate verifies independence at runtime through the
        # SDR-device evidence rule.
        return None
    # Operator asserted a real RAN lab.  Cross-check the configured
    # control host against any known in-repo reference-peer signatures
    # (denylist).
    host = _hostport(config.control_url)[0].lower()
    for frag in _FORBIDDEN_HOST_FRAGMENTS:
        if frag and frag in host:
            return (
                "RAN_PEER_KIND=%r but control peer %r matches a known "
                "in-repo reference-peer signature %r; the operator "
                "assertion is contradicted by the endpoint"
                % (kind, host, frag)
            )
    return None


# ---------------------------------------------------------------------------
# Individual capability probes (each isolated -- never raises; the W016
# BaseException isolation discipline mirrored at the probe level)
# ---------------------------------------------------------------------------


def _probe_build_tools() -> RanCheck:
    """cmake/gcc/meson/ninja discoverable on PATH (an OAI/O-RAN build)."""
    tools = ("cmake", "gcc", "meson", "ninja")
    present = [t for t in tools if shutil.which(t)]
    missing = [t for t in tools if not shutil.which(t)]
    if not missing:
        return RanCheck("build_tools", True, "cmake+gcc+meson+ninja present")
    return RanCheck(
        "build_tools",
        False,
        "probed PATH for cmake/gcc/meson/ninja; present=%s; missing=%s"
        % (present or ["none"], missing),
    )


def _sdr_device_nodes() -> Tuple[str, ...]:
    """The ``/dev/usrp*`` / ``/dev/soapy*`` device nodes actually present."""
    found: List[str] = []
    try:
        entries = os.listdir("/dev")
    except OSError:
        return ()
    for name in sorted(entries):
        if name.startswith("usrp") or name.startswith("soapy"):
            found.append("/dev/" + name)
    return tuple(found)


def _probe_sdr_driver() -> RanCheck:
    """Real SDR device evidence.

    Sysfs USB presence (``/dev/bus/usb``) is NOT sufficient alone --
    every PC has a USB bus.  The check looks for the common SDR device
    nodes (``/dev/usrp*`` for a USRP under the udev rules,
    ``/dev/soapy*`` for a SoapySDR-managed device) and the detail
    records exactly what was probed and what was actually found.
    """
    nodes = _sdr_device_nodes()
    usb_present = os.path.isdir("/dev/bus/usb")
    if nodes:
        return RanCheck(
            "sdr_driver",
            True,
            "SDR device node(s) present: %s" % ",".join(nodes),
        )
    return RanCheck(
        "sdr_driver",
        False,
        "probed /dev/usrp* and /dev/soapy* device nodes and /dev/bus/usb: "
        "no SDR device node found (/dev/bus/usb %s; sysfs USB presence "
        "alone is not SDR evidence)" % ("present" if usb_present else "absent"),
    )


def _probe_sctp() -> RanCheck:
    """IPPROTO_SCTP (132) socket support (the fivegc probe mirrored
    exactly -- SCTP is the NGAP/F1-C transport, TS 38.412/38.470)."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM, 132)  # IPPROTO_SCTP
        s.close()
        return RanCheck("sctp", True, "SCTP usable (NGAP/F1-C transport)")
    except OSError as exc:
        return RanCheck("sctp", False, "%s: %s" % (exc.__class__.__name__, exc))


def _probe_tun() -> RanCheck:
    """/dev/net/tun presence (the fivegc probe mirrored exactly -- the
    UE/gNB user-plane TUN interface)."""
    if os.path.exists("/dev/net/tun"):
        return RanCheck("tun", True, "/dev/net/tun present (UE user plane)")
    return RanCheck(
        "tun",
        False,
        "/dev/net/tun absent -> no userspace UE user-plane interface",
    )


def _probe_oai_binaries() -> RanCheck:
    """OAI CU/DU entrypoints discoverable on PATH."""
    binaries = ("nr-softmodem", "oai_gnb", "gnb")
    present = [b for b in binaries if shutil.which(b)]
    missing = [b for b in binaries if not shutil.which(b)]
    if present:
        return RanCheck(
            "oai_binaries",
            True,
            "OAI gNB entrypoint(s) on PATH: %s" % ",".join(present),
        )
    return RanCheck(
        "oai_binaries",
        False,
        "probed PATH for nr-softmodem/oai_gnb/gnb (OAI CU/DU entrypoints); "
        "none found",
    )


def _probe_openran_control_reachability(config: RanEnvProbeConfig) -> RanCheck:
    """TCP reachability of the configured RAN control endpoint (the
    fivegc sbi_endpoint probe mechanics mirrored: a bounded socket
    connect; on failure the detail carries the exception class name
    only)."""
    url = config.control_url
    if not url:
        return RanCheck("openran_control", False, "RAN_CONTROL_URL not configured")
    host, port = _hostport(url)
    if not host:
        return RanCheck("openran_control", False, "cannot parse host from %s" % url)
    try:
        with _socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT_SECONDS):
            return RanCheck(
                "openran_control",
                True,
                "TCP %s:%d reachable" % (host, port),
            )
    except OSError as exc:
        return RanCheck(
            "openran_control",
            False,
            "%s:%d -> %s" % (host, port, exc.__class__.__name__),
        )


def _hostport(url: str) -> Tuple[str, int]:
    """Minimal ``http(s)://host[:port]`` parser (the fivegc helper)."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def probe_ran_interop_capability(
    config: Optional[RanEnvProbeConfig] = None,
) -> RanCapabilityReport:
    """Run the SDR-lab gate preflight.

    Returns a :class:`RanCapabilityReport` whose ``reachable`` is
    ``True`` ONLY when no forbidden substitution was detected AND every
    environment-capability check passed.  Never raises (probe-level
    isolation).  Never produces acceptance -- ``PASSED`` is the real
    interop gate's job, not this probe's.

    Anti-faking ordering guarantee: when the peer-kind guard fires, the
    control-endpoint reachability check is deliberately NOT executed
    (the guard fires BEFORE any network probe; the matrix records that
    the endpoint was left unprobed).
    """
    cfg = config if config is not None else RanEnvProbeConfig.from_env()
    forbidden = _assert_independent_peer(cfg)
    checks: List[RanCheck] = [
        _probe_build_tools(),
        _probe_sdr_driver(),
        _probe_sctp(),
        _probe_tun(),
        _probe_oai_binaries(),
    ]
    if forbidden is not None:
        checks.append(
            RanCheck(
                "openran_control",
                False,
                "not probed: the peer-kind guard fires before any network "
                "probe",
            )
        )
    else:
        checks.append(_probe_openran_control_reachability(cfg))
    reachable = forbidden is None and all(c.available for c in checks)
    return RanCapabilityReport(
        reachable=reachable,
        checks=tuple(checks),
        forbidden_substitution=forbidden,
    )
