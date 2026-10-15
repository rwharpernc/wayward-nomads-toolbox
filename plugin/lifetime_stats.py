"""
Lifetime totals from the game's own `Statistics` event, for the Credits Ledger window's Lifetime tab (pure, no Tk).

The game writes a `Statistics` event at every login with the commander's lifetime figures: trading, mining, exobiology and,
for an owner, the fleet carrier. They are the game's numbers for the whole of the commander's career, not any one session's,
so they live in the ledger window (a report), never on a mode's panel, and are labelled with when they were taken.

`parse` keeps the few figures worth a glance (anything missing is simply left out); `groups` turns them into titled rows and
`blocks` into the same rows as panel blocks (for tests and logs); `latest_in_journals` finds each commander's newest event so
the window has them straight after EDMC starts rather than at the next login.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from . import commander_data, journal_files
from .trade_blocks import Block, Heading, Note, Pair

EVENT = "Statistics"
MAX_FILES = 40   # newest journal files looked through for the latest event


@dataclass(frozen=True)
class Lifetime:
    at: str                                   # the event's timestamp (ISO, UTC)
    trading: Mapping[str, float]              # market_profits, tonnes, markets, best_deal, average_profit
    mining: Mapping[str, float]               # profits, tonnes
    exobiology: Mapping[str, float]           # profits, species
    carrier: Mapping[str, float]              # jumps, distance_ly, exported_t, imported_t, trade_profit (empty without one)


def _number(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _pick(section: Any, names: Iterable[Tuple[str, str]]) -> Dict[str, float]:
    """`{our name: value}` for each `(our name, journal key)` the section has as a number."""
    if not isinstance(section, dict):
        return {}
    found: Dict[str, float] = {}
    for ours, key in names:
        value = _number(section.get(key))
        if value is not None:
            found[ours] = value
    return found


def parse(entry: Any) -> Optional[Lifetime]:
    """The lifetime figures from a `Statistics` event, or None if it is not one (or holds nothing we show)."""
    if not isinstance(entry, dict) or entry.get("event") != EVENT:
        return None
    life = Lifetime(
        at=str(entry.get("timestamp") or ""),
        trading=_pick(entry.get("Trading"), (("market_profits", "Market_Profits"), ("tonnes", "Resources_Traded"),
                                             ("markets", "Markets_Traded_With"), ("best_deal", "Highest_Single_Transaction"),
                                             ("average_profit", "Average_Profit"))),
        mining=_pick(entry.get("Mining"), (("profits", "Mining_Profits"), ("tonnes", "Quantity_Mined"))),
        exobiology=_pick(entry.get("Exobiology"), (("profits", "Organic_Data_Profits"), ("species", "Organic_Species_Encountered"))),
        carrier=_pick(entry.get("FLEETCARRIER"), (("jumps", "FLEETCARRIER_TOTAL_JUMPS"), ("distance_ly", "FLEETCARRIER_DISTANCE_TRAVELLED"),
                                                  ("exported_t", "FLEETCARRIER_EXPORT_TOTAL"), ("imported_t", "FLEETCARRIER_IMPORT_TOTAL"),
                                                  ("trade_profit", "FLEETCARRIER_TRADEPROFIT_TOTAL"))))
    return life if (life.trading or life.mining or life.exobiology or life.carrier) else None


def _cr(value: float) -> str:
    return f"{int(round(value)):,} cr"


def _t(value: float) -> str:
    return f"{int(round(value)):,} t"


def _n(value: float) -> str:
    return f"{int(round(value)):,}"


def groups(life: Optional[Lifetime]) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """The figures in four short groups of `(label, value)` rows (a group with nothing in it is left out). Empty with no event."""
    if life is None:
        return []
    out: List[Tuple[str, List[Tuple[str, str]]]] = []

    def group(title: str, rows: List[Tuple[str, str]]) -> None:
        if rows:
            out.append((title, rows))

    t = life.trading
    group("Trading", [row for row in (
        ("Market profits", _cr(t["market_profits"]) if "market_profits" in t else ""),
        ("Traded", _t(t["tonnes"]) if "tonnes" in t else ""),
        ("Markets traded with", _n(t["markets"]) if "markets" in t else ""),
        ("Best single deal", _cr(t["best_deal"]) if "best_deal" in t else ""),
        ("Average profit", _cr(t["average_profit"]) if "average_profit" in t else "")) if row[1]])
    m = life.mining
    group("Mining", [row for row in (
        ("Mining profits", _cr(m["profits"]) if "profits" in m else ""),
        ("Mined", _t(m["tonnes"]) if "tonnes" in m else "")) if row[1]])
    e = life.exobiology
    group("Exobiology", [row for row in (
        ("Data sold", _cr(e["profits"]) if "profits" in e else ""),
        ("Species found", _n(e["species"]) if "species" in e else "")) if row[1]])
    c = life.carrier
    group("Fleet carrier", [row for row in (
        ("Jumps", _n(c["jumps"]) if "jumps" in c else ""),
        ("Distance", f"{int(round(c['distance_ly'])):,} ly" if "distance_ly" in c else ""),
        ("Exported / imported", f"{_t(c['exported_t'])} / {_t(c['imported_t'])}" if "exported_t" in c and "imported_t" in c else ""),
        ("Trade profit", _cr(c["trade_profit"]) if "trade_profit" in c else "")) if row[1]])
    return out


def taken_note(life: Lifetime) -> str:
    """Says when the game took the figures."""
    when = life.at[:10]
    return ("Taken from the game's statistics at " + (f"your last login ({when})." if when else "your last login.")
            + " They update when you next log in.")


def blocks(life: Optional[Lifetime]) -> List[Block]:
    """`groups` as panel blocks under a heading, with the line saying when the game took the figures. Nothing with no event."""
    if life is None:
        return []
    out: List[Block] = [Heading("Lifetime (the game's own totals)")]
    for title, rows in groups(life):
        out.append(Heading(title, minor=True))
        out.extend(Pair(label, value) for label, value in rows)
    out.append(Note(taken_note(life)))
    return out


def latest_in_journals(cmdrs: Iterable[str], folder: Optional[str] = None, max_files: int = MAX_FILES) -> Dict[str, Lifetime]:
    """Each commander's newest `Statistics` event in the newest journal files, as `{commander key: Lifetime}`. Stops as soon as
    every commander has one; a commander with none in those files is simply not in the result. Real file reading, so call it off
    the Tk thread."""
    wanted = {commander_data.key_for(c) for c in cmdrs if commander_data.key_for(c)}
    found: Dict[str, Lifetime] = {}
    if not wanted:
        return found
    pattern = journal_files.event_pattern("Commander", "LoadGame", EVENT)
    for path in reversed(journal_files.files_modified_since(0.0, folder)[-max_files:]):
        try:
            with open(path, "rb") as handle:
                if EVENT.encode() not in handle.read():
                    continue
        except OSError:
            continue
        current = ""
        newest: Dict[str, Lifetime] = {}
        for entry in journal_files.read_events(path, pattern):
            kind = entry.get("event")
            if kind == "Commander" and entry.get("Name"):
                current = commander_data.key_for(entry["Name"])
            elif kind == "LoadGame" and entry.get("Commander"):
                current = commander_data.key_for(entry["Commander"])
            elif kind == EVENT and current in wanted:
                life = parse(entry)
                if life is not None:
                    newest[current] = life          # a later one in the same file replaces an earlier one
        for key, life in newest.items():
            found.setdefault(key, life)             # files are visited newest first, so the first found is the latest
        if len(found) == len(wanted):
            break
    return found
