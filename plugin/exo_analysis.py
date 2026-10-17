"""
The analysis of the recorded finds (`exo_observations.py`): how the species prediction did against what the game confirmed. Pure: no Tk, no EDMC.

`finds` flattens the record into one `Find` per confirmed species with whether the prediction listed it and where its body's conditions fall against the
species' rule ranges. The rest summarizes that: `genus_rows` (hit rate by genus), `range_rows` (observed against allowed temperature, gravity and pressure),
`together_rows` (species found on one body) and `report_text`, the whole thing as plain text for the review window's Copy report and
`scripts/analyze_exo_observations.py`. A **miss** (the confirmed species was not on the predicted list) means a rule is missing or too strict; a long
predicted list means the rules are loose. Finds filled in from older saved state are marked `backfill`: their list is today's rules applied afterward.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import organic_species_data as species_data

FIELDS = (("temperature", "temperature_k", "K", 0), ("gravity", "gravity_g", "g", 2), ("pressure", "pressure_atm", "atm", 3))
UNREVIEWED = ""
REVIEW_STATUSES = (
    (UNREVIEWED, "Not reviewed"),
    ("rule", "Needs a rule change"),
    ("data", "Bad data or journal quirk"),
    ("expected", "Expected, no change"),
    ("later", "Look at again later"),
)
REVIEW_LABELS = dict(REVIEW_STATUSES)


@dataclass(frozen=True)
class Find:
    body_key: str
    genus_key: str
    genus: str
    species_key: str
    species: str
    variant: str
    system: str
    body: str
    planet_class: str
    atmosphere: str
    record: Dict[str, Any] = field(compare=False, hash=False, repr=False)
    predicted: Tuple[str, ...] = ()
    seen: str = ""
    source: str = "live"
    status: str = UNREVIEWED
    note: str = ""
    outside: Tuple[str, ...] = ()           # which of temperature/gravity/pressure the species was found outside the rules' range of

    @property
    def hit(self) -> bool:
        return self.species_key in self.predicted

    @property
    def list_length(self) -> int:
        return len(self.predicted)


def genus_name(genus_key: str) -> str:
    info = species_data.GENUS.get(genus_key)
    return info.name if info else genus_key


def species_info(species_key: str):
    return next((s for s in species_data.SPECIES.values() if s.species_key == species_key), None)


def allowed(info, name: str) -> Optional[Tuple[float, float]]:
    """(lowest, highest) the species' rulesets allow for `name` ('gravity', 'temperature' or 'pressure'); None when any value is allowed."""
    lows, highs = [], []
    for rules in info.rulesets:
        low, high = getattr(rules, f"min_{name}"), getattr(rules, f"max_{name}")
        if low is None and high is None:
            return None
        lows.append(low if low is not None else float("-inf"))
        highs.append(high if high is not None else float("inf"))
    return (min(lows), max(highs)) if lows else None


def _outside(record: Dict[str, Any], info) -> Tuple[str, ...]:
    if info is None:
        return ()
    found = []
    for name, key, _unit, _digits in FIELDS:
        value, span = record.get(key), allowed(info, name)
        if isinstance(value, (int, float)) and span and not span[0] <= value <= span[1]:
            found.append(name)
    return tuple(found)


def finds(bodies: Dict[str, Dict[str, Any]]) -> List[Find]:
    """One Find per species confirmed, oldest body first by key."""
    rows = []
    for key in sorted(bodies):
        record = bodies[key]
        for genus_key, entry in (record.get("species") or {}).items():
            review = entry.get("review") if isinstance(entry.get("review"), dict) else {}
            rows.append(Find(
                key, genus_key, genus_name(genus_key), entry.get("species_key") or "", entry.get("species") or entry.get("species_key") or "",
                entry.get("variant") or "", record.get("system") or "", record.get("body") or "", record.get("planet_class") or "",
                record.get("atmosphere") or "", record, tuple(entry.get("predicted") or ()), entry.get("seen") or "", record.get("source") or "live",
                review.get("status") or UNREVIEWED, review.get("note") or "", _outside(record, species_info(entry.get("species_key") or ""))))
    return rows


def conditions_text(record: Dict[str, Any]) -> str:
    """One line of a body's conditions, leaving out what the journal did not give."""
    parts = []
    for _name, key, unit, digits in FIELDS:
        if isinstance(record.get(key), (int, float)):
            parts.append(f"{record[key]:.{digits}f} {unit}")
    parts.append(f"star {record.get('star_type') or '?'}")
    parts.append(f"volcanism {record.get('volcanism') or 'none'}")
    return ", ".join(parts)


def predicted_names(find: Find) -> List[str]:
    """The species the prediction listed, by name (the key when the name is not known)."""
    names = []
    for key in find.predicted:
        info = species_info(key)
        names.append(info.name if info else key)
    return names


@dataclass(frozen=True)
class GenusRow:
    genus: str
    finds: int
    hits: int
    average_list: float

    @property
    def percent(self) -> int:
        return 100 * self.hits // self.finds if self.finds else 0


def genus_rows(rows: Iterable[Find]) -> List[GenusRow]:
    grouped: Dict[str, List[Find]] = collections.defaultdict(list)
    for row in rows:
        grouped[row.genus].append(row)
    return [GenusRow(genus, len(items), sum(1 for f in items if f.hit), sum(f.list_length for f in items) / len(items))
            for genus, items in sorted(grouped.items())]


@dataclass(frozen=True)
class RangeRow:
    species: str
    name: str                       # temperature, gravity or pressure
    unit: str
    finds: int
    low: float
    high: float
    rule_low: Optional[float]       # None: the rules allow any value
    rule_high: Optional[float]

    @property
    def outside(self) -> bool:
        return self.rule_low is not None and (self.low < self.rule_low or self.high > self.rule_high)

    @property
    def observed_text(self) -> str:
        return f"{self.low:.4g} to {self.high:.4g}"

    @property
    def rule_text(self) -> str:
        if self.rule_low is None:
            return "any"
        lo = "any" if self.rule_low == float("-inf") else f"{self.rule_low:.4g}"
        hi = "any" if self.rule_high == float("inf") else f"{self.rule_high:.4g}"
        return f"{lo} to {hi}"


def range_rows(rows: Iterable[Find]) -> List[RangeRow]:
    seen: Dict[Tuple[str, str], List[float]] = collections.defaultdict(list)
    keys: Dict[str, str] = {}
    for row in rows:
        keys[row.species] = row.species_key
        for name, key, _unit, _digits in FIELDS:
            if isinstance(row.record.get(key), (int, float)):
                seen[(row.species, name)].append(row.record[key])
    result = []
    for (species, name), values in sorted(seen.items()):
        info = species_info(keys[species])
        span = allowed(info, name) if info else None
        unit = next(u for n, _k, u, _d in FIELDS if n == name)
        result.append(RangeRow(species, name, unit, len(values), min(values), max(values), span[0] if span else None, span[1] if span else None))
    return result


@dataclass(frozen=True)
class TogetherRow:
    planet_class: str
    atmosphere: str
    species: Tuple[str, ...]
    bodies: int


def together_rows(bodies: Dict[str, Dict[str, Any]]) -> List[TogetherRow]:
    """Which sets of species were found on one body, with how many bodies, most common first. Bodies with one species are left out."""
    counts: Dict[Tuple[str, str, Tuple[str, ...]], int] = collections.Counter()
    for record in bodies.values():
        names = tuple(sorted((e.get("species") or e.get("species_key") or "") for e in (record.get("species") or {}).values()))
        if len(names) > 1:
            counts[(record.get("planet_class") or "", record.get("atmosphere") or "none", names)] += 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [TogetherRow(p, a, names, n) for (p, a, names), n in ordered]


def report_text(bodies: Dict[str, Dict[str, Any]]) -> str:
    """Everything above as plain text, to read or to paste to someone tuning the rules."""
    rows = finds(bodies)
    live = sum(1 for f in rows if f.source == "live")
    out = [f"{len(bodies)} bodies, {len(rows)} species finds ({live} recorded live, {len(rows) - live} filled in from older saved state)", ""]
    if not rows:
        return "\n".join(out)
    out.append("== Prediction hit rate by genus ==")
    for g in genus_rows(rows):
        out.append(f"  {g.genus:<20} {g.hits:>3}/{g.finds:<3} on the list ({g.percent}%)   average list length {g.average_list:.1f}")
    misses = [f for f in rows if not f.hit]
    out += ["", f"== Finds the prediction did not list ({len(misses)}) =="]
    for f in misses:
        out.append(f"  {f.species} on {f.planet_class} / {f.atmosphere or 'no atmosphere'} [{f.system} {f.body}]")
        out.append(f"      {conditions_text(f.record)}; listed: {', '.join(predicted_names(f)) or 'nothing'}")
    out += ["", "== Where each species was found =="]
    where: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for f in rows:
        where[f.species][f"{f.planet_class} / {f.atmosphere or 'none'}"] += 1
    for name, counts in sorted(where.items()):
        out.append(f"  {name}: " + "; ".join(f"{k} x{n}" for k, n in counts.most_common()))
    out += ["", "== Observed conditions against the rules' range (a find outside the range means the range is too tight) =="]
    by_species: Dict[str, List[RangeRow]] = collections.defaultdict(list)
    for r in range_rows(rows):
        by_species[r.species].append(r)
    for species, items in sorted(by_species.items()):
        out.append(f"  {species}: " + "; ".join(f"{r.name} {r.observed_text} (rules {r.rule_text}){'  <-- outside' if r.outside else ''}" for r in items))
    out += ["", "== Species found together on one body =="]
    together = together_rows(bodies)
    out += [f"  {t.planet_class} / {t.atmosphere}: {' + '.join(t.species)} x{t.bodies}" for t in together[:25]] or ["  none yet"]
    reviewed = [f for f in rows if f.status]
    if reviewed:
        out += ["", f"== Reviewed finds ({len(reviewed)}) =="]
        out += [f"  {f.species} [{f.system} {f.body}]: {REVIEW_LABELS.get(f.status, f.status)}" + (f" - {f.note}" if f.note else "") for f in reviewed]
    return "\n".join(out)
