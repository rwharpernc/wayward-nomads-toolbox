"""
What Trade mode puts on screen, as a small list of typed blocks instead of lines of text (pure, no Tk).

The panel used to be one label of text lines padded with spaces, which can't line numbers up, set a heading
apart from its rows, or wrap a long station name without wrecking the rest. Describing the page as blocks lets
`trade_view.py` draw real sections and aligned columns, while the logic that decides *what* to show stays free of
widgets and can be tested. `to_text` renders the same blocks as plain lines for tests and logs.

Blocks (all frozen, so two renderings compare equal and an unchanged page is not redrawn):
- `Heading`  a section title. `minor` is a quieter sub-heading.
- `Pair`     a label on the left and a value on the right ("Hold", "1,265/1,265 t").
- `Columns`  the headings above a table's number columns.
- `Item`     a table row: a title, number cells aligned under the `Columns`, and a detail line beneath.
- `Note`     a wrapped paragraph; `warn` marks something to watch, `strong` something to read first.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple, Union


@dataclass(frozen=True)
class Heading:
    text: str
    minor: bool = False


@dataclass(frozen=True)
class Pair:
    label: str
    value: str
    bold: bool = False
    indent: int = 0


@dataclass(frozen=True)
class Columns:
    labels: Tuple[str, ...]


@dataclass(frozen=True)
class Item:
    title: str
    cells: Tuple[str, ...] = ()
    detail: str = ""
    warn: str = ""
    indent: int = 0


@dataclass(frozen=True)
class Note:
    text: str
    warn: bool = False
    strong: bool = False


Block = Union[Heading, Pair, Columns, Item, Note]


def to_text(blocks: Sequence[Block]) -> List[str]:
    """The blocks as plain lines: a heading is its text, a pair is `label: value` (indented by `indent` x 2
    spaces), a table row is its title and cells with the detail beneath, a note is its own lines."""
    lines: List[str] = []
    for block in blocks:
        if isinstance(block, Heading):
            lines.append(block.text)
        elif isinstance(block, Pair):
            lines.append(f"{'  ' * block.indent}{block.label}: {block.value}")
        elif isinstance(block, Columns):
            lines.append("  ".join(label for label in block.labels if label))
        elif isinstance(block, Item):
            pad = "  " * (block.indent + 1)
            lines.append(f"{pad}{block.title}" + (f"  {'  '.join(block.cells)}" if block.cells else ""))
            detail = " - ".join(part for part in (block.detail, block.warn) if part)
            if detail:
                lines.append(f"{pad}  {detail}")
        elif isinstance(block, Note):
            lines.extend(block.text.splitlines() or [""])
    return lines
