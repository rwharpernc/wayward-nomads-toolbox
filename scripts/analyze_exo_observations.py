"""Checks the species prediction against the finds WNTB has recorded (plugin/exo_observations.py, `exo_observations.json`).

    python scripts/analyze_exo_observations.py [path to exo_observations.json]

With no path it reads the copy deployed to EDMC's plugin folder. It prints, for each genus, how often the species the game confirmed was on the
predicted list (a miss means a rule is missing or too strict), the conditions of each miss, where each species was found, the temperature, gravity and
pressure each species was seen at beside the range its rules allow, the species found together on one body, and any finds you reviewed in the Prediction
review window. The same report is behind that window's Copy report button. Records filled in from older saved state ("backfill") are marked: their prediction
is today's rules applied afterwards. It reads a file and changes nothing.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import exo_analysis  # noqa: E402


def _default_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "EDMarketConnector", "plugins", "WNTB", "exo_observations.json")


def main(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            bodies = json.load(handle).get("bodies", {})
    except (OSError, ValueError) as exc:
        print(f"Could not read {path}: {exc}")
        return 1
    print(exo_analysis.report_text(bodies))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else _default_path()))
