"""
Trade mode's page order - kept in its own tiny module (like mining_pages.py) so
config defaulting can reference PAGE_ORDER[0] without a circular import.
"""

SESSION = "Session"
ROUTES = "Routes"
MARKET = "Market"

PAGE_ORDER: tuple[str, ...] = (SESSION, ROUTES, MARKET)
"""Session (what you have traded, offline) first, then the two Spansh lookups
(routes near you, best price for a commodity). Order is what the nav cycles through."""
