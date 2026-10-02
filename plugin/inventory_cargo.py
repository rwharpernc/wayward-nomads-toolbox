"""
Ship/SRV cargo-hold tracking for Field Ops' Inventory content.

Cargo tonnage is a different game system from the on-foot microresources
tracked in inventory.py — this module is deliberately separate and only
concerns itself with capacity/used-tonnage, never commodity names, prices,
or market data.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

# Known SRV types, matched as a lowercased substring of the journal's
# SRVType/SRVType_Localised value (the exact raw string isn't documented, so
# matching is deliberately fuzzy/case-insensitive rather than an exact
# lookup) -> (display name, confirmed cargo capacity or None).
#
# Scarab/Scorpion capacities are stable since Odyssey Update 9. The Rhino
# has a display name but no capacity: Frontier describes its cargo hold as
# expandable up to 24t, and there's no confirmed journal field yet for its
# actual fitted capacity. Rather than guess, its bar shows the current
# cargo count with capacity=None ("unknown") until that's confirmed against
# a real journal entry — see VehicleState.cargo_bar.
SRV_INFO: Mapping[str, Tuple[str, Optional[int]]] = {
    "scarab": ("Scarab", 4),
    "scorpion": ("Scorpion", 2),
    "rhino": ("Rhino", None),
}

VEHICLE_SHIP = "ship"
VEHICLE_FOOT = "foot"
VEHICLE_SRV = "srv"


def _cargo_total(state: Mapping[str, Any]) -> int:
    """Sum of state['Cargo'] (EDMC's live commodity-count map for whichever
    vessel's hold is currently active — ship or SRV, the game writes the
    same Cargo.json either way)."""
    cargo = state.get("Cargo")
    if not isinstance(cargo, Mapping):
        return 0
    return sum(int(count) for count in cargo.values())


class VehicleState:
    """
    Tracks which vehicle (ship, on foot, or SRV) the commander currently
    occupies, and the SRV type when applicable.

    Derived purely from Embark/Disembark/LaunchSRV/DockSRV journal events —
    EDMC's own monitor state doesn't retain this distinction after
    processing an event (it only tracks OnFoot, which is the same for "on
    foot near your ship" and "on foot near your SRV"). Starts assuming
    "ship", the common case at login; a session that starts mid-SRV or
    on-foot self-corrects from the first relevant event, including EDMC's
    own startup replay of the session log before live events arrive.
    """

    def __init__(self) -> None:
        self._vehicle: str = VEHICLE_SHIP
        self._srv_type: Optional[str] = None

    @property
    def vehicle(self) -> str:
        return self._vehicle

    def reset(self) -> None:
        """Back to the LoadGame/Start default - a fresh journal file replays
        its own Embark/LaunchSRV history from scratch, so any state carried
        over from a previous session would otherwise go stale."""
        self._vehicle = VEHICLE_SHIP
        self._srv_type = None

    def apply_embark(self, entry: Mapping[str, Any]) -> None:
        self._vehicle = VEHICLE_SRV if entry.get("SRV") else VEHICLE_SHIP
        if self._vehicle != VEHICLE_SRV:
            self._srv_type = None

    def apply_disembark(self, entry: Mapping[str, Any]) -> None:
        self._vehicle = VEHICLE_FOOT

    def apply_launch_srv(self, entry: Mapping[str, Any]) -> None:
        self._vehicle = VEHICLE_SRV
        self._srv_type = _canonical_srv_type(
            entry.get("SRVType_Localised") or entry.get("SRVType"),
        )

    def apply_dock_srv(self, entry: Mapping[str, Any]) -> None:
        self._vehicle = VEHICLE_SHIP
        self._srv_type = None

    def cargo_bar(self, state: Mapping[str, Any]) -> Optional[Tuple[str, int, Optional[int]]]:
        """
        (label, current_total, capacity_or_None) for the panel's
        location-dependent cargo bar, or None while on foot with no vehicle
        (a cargo hold doesn't apply).
        """
        if self._vehicle == VEHICLE_FOOT:
            return None

        total = _cargo_total(state)

        if self._vehicle == VEHICLE_SHIP:
            capacity = state.get("CargoCapacity")
            return "Ship Cargo", total, capacity if isinstance(capacity, int) and capacity > 0 else None

        name, capacity = _match_srv(self._srv_type)
        return f"{name} Cargo", total, capacity


def _canonical_srv_type(raw: Optional[Any]) -> Optional[str]:
    if not raw:
        return None
    return str(raw).strip().lower()


def _match_srv(srv_type: Optional[str]) -> Tuple[str, Optional[int]]:
    if srv_type:
        for needle, info in SRV_INFO.items():
            if needle in srv_type:
                return info
    return "SRV", None
