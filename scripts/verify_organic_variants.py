"""Checks the color variant predictions (plugin/organic_scan.py `predict_variants`, from plugin/organic_variant_data.py) against what your own journals recorded.

    python scripts/verify_organic_variants.py [journal folder]

For every species you logged (`ScanOrganic`, first sample) it takes the star type of the system's arrival star and the body's materials from the journal, predicts the color, and compares it with the
variant the game named. It prints the hits and misses by kind of rule. It reads files and changes nothing; the journals are yours, so nothing in the output is sent anywhere.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plugin import organic_scan as O  # noqa: E402


def main(folder: str) -> None:
    files = sorted(glob.glob(os.path.join(folder, "Journal.*.log")))
    print(f"{len(files)} journals in {folder}")
    stats = collections.Counter()
    misses = []
    seen = set()
    for path in files:
        star, system, bodies = None, None, {}
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '"event"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                event = entry.get("event")
                if event in ("FSDJump", "Location", "CarrierJump"):
                    system, star, bodies = entry.get("StarSystem"), None, {}
                elif event == "Scan":
                    if entry.get("StarType") and entry.get("BodyID") == 0:
                        star = entry["StarType"]
                    if entry.get("PlanetClass"):
                        mats = entry.get("Materials")
                        bodies[entry.get("BodyID")] = O.BodyConditions(
                            body_name=entry["BodyName"], planet_class=entry["PlanetClass"], star_type=star,
                            materials=tuple(str(m.get("Name", "")).casefold() for m in mats) if isinstance(mats, list) else None)
                elif event == "ScanOrganic" and entry.get("ScanType") == "Log" and entry.get("Variant_Localised"):
                    key = (system, entry.get("Body"), entry.get("Species_Localised"))
                    if key in seen:
                        continue
                    seen.add(key)
                    cond = bodies.get(entry.get("Body"))
                    rule = O.variant_rule(entry["Species_Localised"])
                    if cond is None or star is None:
                        stats["body or star not seen in this journal"] += 1
                        continue
                    if rule is None:
                        stats["species with no color rule"] += 1
                        continue
                    cond.star_type = star
                    actual = entry["Variant_Localised"].split(" - ")[-1].strip()
                    predicted = O.predict_variants(entry["Species_Localised"], cond)
                    outcome = "no prediction" if not predicted else "hit" if actual in predicted else "MISS"
                    stats[f"{rule[0]} {outcome}"] += 1
                    if outcome != "hit":
                        misses.append((rule[0], predicted, entry["Species_Localised"], actual, star, cond.planet_class))
    for name, count in sorted(stats.items()):
        print(f"  {name}: {count}")
    for miss in misses[:20]:
        print("  not matched:", miss)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(r"~\Saved Games\Frontier Developments\Elite Dangerous"))
