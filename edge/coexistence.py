"""WORK-034 Ethernet / Wi-Fi / cellular access coexistence.

A Pi-class gateway carries several access technologies at once: wired
Ethernet, Wi-Fi, and cellular (a WWAN interface declared by the
deployment, or the WORK-020 RAN access path beside the agent).  This
module makes that coexistence explicit and deterministic WITHOUT
duplicating any access-family semantics:

- the access technologies themselves stay owned by the accepted
  adapter families (WORK-016 bridge, WORK-020 RAN, WORK-021 Wi-Fi,
  WORK-022 backhaul) -- nothing here opens, closes, or re-implements
  an adapter;
- classification maps the FROZEN interface-link vocabulary (and a
  deployment-declared access plan for interfaces the link vocabulary
  cannot classify, e.g. ``wwan0`` -> cellular) onto the frozen
  access-class vocabulary -- classification is registry DATA;
- selection is a deterministic order over the agent's own live
  adapter views (lifecycle + health + capacity), with the frozen
  engineering preference (Ethernet, then Wi-Fi, then cellular:
  cheapest and highest-capacity first) and health gating -- FAILED
  access never carries traffic;
- the connectivity posture (connected / degraded / offline) is the
  worse-of view over the classified access adapters.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from agent.bridge import technology_for_snapshot
from agent.model import InterfaceSnapshot

from .errors import EdgeError, EdgeReasonCode
from .model import ConnectivityPosture


class AccessClass:
    """The frozen access-class vocabulary (coexistence DATA)."""

    ETHERNET = "ethernet"
    WIFI = "wifi"
    CELLULAR = "cellular"

    @classmethod
    def values(cls) -> Tuple[str, ...]:
        return (cls.ETHERNET, cls.WIFI, cls.CELLULAR)


#: Frozen mapping from the agent bridge's access-technology ids to
#: access classes (registry DATA; the bridge vocabulary is owned by
#: WORK-016/W033).  ``access.generic.experimental`` (the bridge's
#: honest catch-all for kinds like WWAN) is deliberately ABSENT: an
#: interface the link vocabulary cannot classify participates in
#: coexistence only through an explicit deployment access-plan
#: declaration.
TECHNOLOGY_ACCESS_CLASS: Dict[str, str] = {
    "access.ieee.8023": AccessClass.ETHERNET,
    "access.ieee.80211": AccessClass.WIFI,
}

#: The frozen coexistence preference order (engineering default:
#: cheapest, highest-capacity, most stable first -- wired before
#: wireless before metered cellular).  Deployment DATA.
COEXISTENCE_PREFERENCE: Tuple[str, ...] = (
    AccessClass.ETHERNET,
    AccessClass.WIFI,
    AccessClass.CELLULAR,
)

#: Health ladder used for gating and ordering (the WORK-016 ladder;
#: lower == better).
_ACCESS_HEALTH_ORDINALS: Dict[str, int] = {
    "HEALTHY": 0,
    "DEGRADED": 1,
    "FAILED": 2,
}

#: Access views with health worse than DEGRADED never carry traffic.
_MAX_CARRYING_HEALTH_ORDINAL = 1


def validate_access_plan(plan: Mapping[str, str]) -> None:
    """Validate a deployment access plan (interface name -> access
    class).  Unknown classes fail closed."""
    for name, access_class in plan.items():
        if not isinstance(name, str) or not name:
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "access-plan keys must be non-empty interface names",
            )
        if access_class not in AccessClass.values():
            raise EdgeError(
                EdgeReasonCode.INVALID_INPUT,
                "access-plan class for %r must be one of %s (got %r)"
                % (name, AccessClass.values(), access_class),
            )


def classify_access(
    snapshot: InterfaceSnapshot, plan: Mapping[str, str] = {}
) -> str:
    """Classify one interface onto the access-class vocabulary.

    Loopback never classifies (it is not an access technology).  The
    link kind maps through the frozen technology table; interfaces
    the table cannot classify (``other`` -- e.g. WWAN) classify only
    through the deployment access plan.  Returns "" when the
    interface carries no declared access class.
    """
    if not isinstance(snapshot, InterfaceSnapshot):
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "access classification requires a genuine InterfaceSnapshot",
        )
    validate_access_plan(plan)
    if snapshot.link_kind == "loopback":
        return ""
    technology = technology_for_snapshot(snapshot)
    mapped = TECHNOLOGY_ACCESS_CLASS.get(technology, "")
    if mapped:
        return mapped
    declared = plan.get(snapshot.name, "")
    return declared if declared in AccessClass.values() else ""


class AccessView:
    """One live access-adapter view: the interface snapshot joined
    with the agent's adapter lifecycle/health (read-only DATA for
    selection and posture)."""

    __slots__ = (
        "interface_name", "adapter_id", "access_class", "technology",
        "lifecycle", "computed_health", "state_up", "speed_mbps",
    )

    def __init__(
        self,
        *,
        interface_name: str,
        adapter_id: str,
        access_class: str,
        technology: str,
        lifecycle: str,
        computed_health: str,
        state_up: bool,
        speed_mbps: int,
    ) -> None:
        self.interface_name = interface_name
        self.adapter_id = adapter_id
        self.access_class = access_class
        self.technology = technology
        self.lifecycle = lifecycle
        self.computed_health = computed_health
        self.state_up = bool(state_up)
        self.speed_mbps = speed_mbps

    def to_dict(self) -> dict:
        return {
            "interface_name": self.interface_name,
            "adapter_id": self.adapter_id,
            "access_class": self.access_class,
            "technology": self.technology,
            "lifecycle": self.lifecycle,
            "computed_health": self.computed_health,
            "state_up": self.state_up,
            "speed_mbps": self.speed_mbps,
        }

    @property
    def carries_traffic(self) -> bool:
        """Whether this view may carry traffic: OPEN lifecycle, link
        up, and health no worse than degraded."""
        if self.lifecycle != "OPEN":
            return False
        if not self.state_up:
            return False
        ordinal = _ACCESS_HEALTH_ORDINALS.get(self.computed_health, 2)
        return ordinal <= _MAX_CARRYING_HEALTH_ORDINAL


def build_access_views(
    snapshots: Sequence[InterfaceSnapshot],
    adapter_views: Sequence[Mapping[str, object]],
    adapter_interfaces: Mapping[str, str],
    plan: Mapping[str, str] = {},
) -> Tuple[AccessView, ...]:
    """Join interface snapshots with the agent's adapter views (the
    ``MonitoringReport.adapters`` entries plus the runtime snapshot's
    ``adapter_interfaces`` mapping).  Read-only composition: no
    adapter state is touched."""
    validate_access_plan(plan)
    by_interface: Dict[str, Mapping[str, object]] = {}
    for adapter_id, interface_name in adapter_interfaces.items():
        by_interface[interface_name] = {"adapter_id": adapter_id}
    health_by_adapter: Dict[str, Mapping[str, object]] = {}
    for view in adapter_views:
        view_adapter_id = str(view.get("adapter_id", ""))
        if view_adapter_id:
            health_by_adapter[view_adapter_id] = view
    views: List[AccessView] = []
    for snapshot in snapshots:
        interface_info = by_interface.get(snapshot.name)
        if interface_info is None:
            continue
        adapter_id = str(interface_info["adapter_id"])
        health_view = health_by_adapter.get(adapter_id, {})
        views.append(
            AccessView(
                interface_name=snapshot.name,
                adapter_id=adapter_id,
                access_class=classify_access(snapshot, plan),
                technology=technology_for_snapshot(snapshot),
                lifecycle=str(health_view.get("lifecycle", "")),
                computed_health=str(health_view.get("computed_health", "")),
                state_up=snapshot.state_up,
                speed_mbps=snapshot.speed_mbps,
            )
        )
    return tuple(views)


def select_access(
    views: Sequence[AccessView],
    *,
    required_class: str = "",
    preference: Tuple[str, ...] = COEXISTENCE_PREFERENCE,
) -> Optional[AccessView]:
    """Deterministically select one CLASSIFIED access view for
    traffic.

    Fail-closed: only views that carry traffic AND carry a declared
    access class participate (an unclassified interface is not an
    access-class candidate; the agent's own binding path remains
    available for it).  With ``required_class`` set, only that class
    is eligible (explicit coexistence routing by the deployment).
    Ordering: preference index first (frozen default: Ethernet,
    Wi-Fi, cellular), then health (better first), then capacity
    (higher first), then interface name (total order, no
    insertion-order dependence).  Returns ``None`` when no eligible
    view exists.
    """
    if required_class and required_class not in AccessClass.values():
        raise EdgeError(
            EdgeReasonCode.INVALID_INPUT,
            "required access class %r not in the frozen vocabulary"
            % (required_class,),
        )
    candidates = [
        view for view in views
        if view.carries_traffic and view.access_class
    ]
    if required_class:
        candidates = [
            view for view in candidates if view.access_class == required_class
        ]
    if not candidates:
        return None

    def sort_key(view: AccessView) -> Tuple[int, int, int, str]:
        try:
            preference_index = preference.index(view.access_class)
        except ValueError:
            preference_index = len(preference)
        health = _ACCESS_HEALTH_ORDINALS.get(view.computed_health, 2)
        return (
            preference_index,
            health,
            -view.speed_mbps,
            view.interface_name,
        )

    return sorted(candidates, key=sort_key)[0]


def connectivity_posture(views: Sequence[AccessView]) -> str:
    """The worse-of coexistence posture over the classified access
    views: connected when every declared class carries traffic,
    degraded when some are lost, offline when none carry traffic.

    ``degraded`` is the failover state -- the acceptance-relevant
    behavior is that the node keeps operating on the remaining
    classes (and re-binds through them) rather than dying.
    """
    declared = {
        view.access_class for view in views if view.access_class
    }
    carrying = {
        view.access_class
        for view in views
        if view.access_class and view.carries_traffic
    }
    if not carrying:
        return ConnectivityPosture.OFFLINE
    if carrying != declared:
        return ConnectivityPosture.DEGRADED
    return ConnectivityPosture.CONNECTED


__all__ = [
    "AccessClass",
    "TECHNOLOGY_ACCESS_CLASS",
    "COEXISTENCE_PREFERENCE",
    "validate_access_plan",
    "classify_access",
    "AccessView",
    "build_access_views",
    "select_access",
    "connectivity_posture",
]
