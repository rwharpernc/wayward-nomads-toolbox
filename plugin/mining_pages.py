"""
The panel's page order - kept in its own tiny module (rather than in
mining_panel.py) so config defaulting can reference PAGE_ORDER[0] without a
circular import, matching how mission_types.py serves the same role for
Missions mode's CATEGORY_ORDER.
"""

SPACE_MINING = "Space Mining"
SURFACE_MINING = "Surface Mining"

PAGE_ORDER: tuple[str, ...] = (SPACE_MINING, SURFACE_MINING)
"""Space Mining (ship-based, any vessel) first, Surface Mining (Rhino)
second - order otherwise has no significance, just what the panel's page
nav cycles through."""
