"""ADCOS reference adapter compositions (M007, R7-CORE-001) — the
``adapters/reference/`` subpackage.

The M007 reference adapters for the six technology families
(``backhaul/``, ``fivegc/``, ``ip/``, ``mesh/``, ``ran/``, ``wifi/``):
one module per family, each composing that family's ACCEPTED runtime
(the family manager + deterministic reference engine +, where the
family grew one, the accepted WORK-016 SDK bridge) into a WORK-016
``AdapterContract`` implementation the 1.1 capability-oriented boundary
(:class:`adapters.capability.CapabilityAdapter`) registers and drives.

Placement disclosure (the harvest shape): the reference compositions
live HERE, not inside the family directories, because the family
batteries freeze their packages' boundary audits (the
WORK-020/021/022 standards-boundary audits allow only each family
bridge's single sanctioned SDK import).  The six family subpackages
are byte-identical to the accepted baseline; the M007 seam lives in
the new domain — the M006 composition-harvest precedent (the seam
lives in the new domain; the harvested surface is preserved verbatim).
Nothing is re-implemented here: every composition calls the family's
OWN public runtime APIs (LOCK-112 — the families model the standard
mechanisms; the modules carry their own frozen citations).

Per-family modules:

- ``mesh``     — 3GPP IAB / sidelink relay + DTN-class
                 store-and-forward (WORK-023);
- ``ran``      — 3GPP NR + O-RAN F1/E1/7-2x splits (WORK-020);
- ``backhaul`` — IEEE 802.3-2018 / 802.1Q-2022 / ITU-T G.709
                 transport (WORK-022);
- ``wifi``     — IEEE 802.11-2020 / 802.1X / TS 23.316 N3IWF /
                 RFC 7296 (WORK-021);
- ``fivegc``   — 3GPP TS 23.501 PDU sessions + TS 23.316 steering
                 (WORK-019; includes the family's WORK-016 reference
                 adapter — the family never grew one);
- ``ip``       — RFC 4291/6437/6146 IPv6 flow/NAT64 boundary
                 (WORK-018; includes the family's WORK-016 reference
                 adapter — the family never grew one).

Determinism (LOCK-119): every composition is a pure function of its
injected inputs (read-only facades + injected instants); no wall
clock, no randomness, no network, no secrets.
"""

from __future__ import annotations

from . import backhaul, fivegc, ip, mesh, ran, wifi

__all__ = ["backhaul", "fivegc", "ip", "mesh", "ran", "wifi"]
