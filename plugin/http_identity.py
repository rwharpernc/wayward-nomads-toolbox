"""
How WNTB identifies itself to the web services it calls.

Every request carries a User-Agent that names WNTB, its version and where to
find the project, so a service operator who sees traffic can tell what it is
and get in touch. `feature` says which part of WNTB made the request.

Example: "WNTB/1.0.0 (rare-goods; +https://github.com/rwharpernc/wayward-nomads-toolbox)"
"""
from __future__ import annotations

from . import __version__

HOMEPAGE = "https://github.com/rwharpernc/wayward-nomads-toolbox"


def user_agent(feature: str = "") -> str:
    detail = f"{feature}; " if feature else ""
    return f"WNTB/{__version__} ({detail}+{HOMEPAGE})"
