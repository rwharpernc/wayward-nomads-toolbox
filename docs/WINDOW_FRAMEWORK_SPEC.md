# WNTB Window Kit

The shared look and building blocks for every pop-out (Toplevel) window in WNTB: a dark, consistent
palette, flat cards, striped sortable tables, and an embedded map. It lives in `plugin/uikit/`. The rules
that matter when changing a window are in [TECHNICAL.md](TECHNICAL.md) section 5; this page describes what
the kit provides and where it's used.

**Last updated:** 2026-10-02 (see `CHANGELOG.md`)

## 1. Scope

The kit covers external windows only. The main-window panels (`plugin_app`) are **not** part of it: they
follow EDMC's theme and must obey the width-bounding rules in TECHNICAL.md section 5.

Windows that use it: the Mining Book and the Mining dialogs, Powerplay Sessions, Rare Goods, Inventory,
the BGS Report, Codex Completionist, Ship Builds (window and dialog), the Missions pop-ups and the
Screenshots preview. Settings tabs are not converted, because they live inside EDMC's own preferences
window and follow its theme.

## 2. Hard rule: never touch ttk globally

ttk themes and stock styles (`TButton`, `Treeview` and so on) are application-wide, so changing them
would recolour EDMC's main window and every other plugin. The kit therefore uses classic tk widgets plus
its own `FlatButton`, `Combobox`, `SlimScrollbar` and `tk.PanedWindow`, and `style.skin(window)` colours
a window's classic widgets through Tk's option database, scoped by that window's own name.
`tests/test_ui_kit.py` fails if the kit touches the ttk theme or styles.

A consequence: ttk `Treeview` tables can only be restyled through a name-scoped style, and their headings
stay native on Windows, so table-heavy windows use the kit's own table instead.

## 3. Building blocks

- **Palette and tokens** (`palette.py`): background layers, text, accent, and success, warning and danger
  colours, plus a colour-blind-safe set for status. Shape or a label carries the state, never colour
  alone (the minimap markers work the same way).
- **Style** (`style.py`): applies the look to a window's classic widgets. Fonts derive from
  `TkDefaultFont` so Linux and high-DPI displays behave.
- **Window shell** (`shell.py`): a singleton Toplevel with saved geometry, a minimum size, a header (title,
  subtitle, action buttons), a status footer and Esc-to-close. It never touches EDMC's config: the window
  passes it `load_geometry` and `save_geometry` callables. Windows are built hidden and shown once their
  content is laid out, so they never flash at a default size.
- **Widgets** (`widgets.py`, `table.py`): `Card`, `Pill` (status chip), `StatTile`, `FlatButton`,
  `Combobox`, `SlimScrollbar`, `ProgressBar`, `Tabs` (with an `on_select` callback so a window can redraw only
  the tab being shown), `FoldList` (a collapsible grouped list), `ScrollFrame`, `NoteLabel` (a body-size note that
  spans the full width and re-wraps as the window is resized, for hints under a table), `field_grid`, and
  `DataTable` (striped, sortable, optionally grouped, with an API like Treeview's, and header and body columns
  kept aligned; `set_rows` refills it and does nothing when the rows haven't changed, for windows that refresh often).
- **Map canvas** (`mapview.py`): a `Canvas`-based map with zoom, hover and click-to-select, used by the
  Mining Book. The fixed-size minimap image on the Surface Mining page is drawn separately.

Any window content that comes from outside data (Spansh names, file names) is truncated with a hard cap,
for the same discipline as the main panels.

## 4. The theme choice

WNTB's windows deliberately **do not follow EDMC's theme**. They use their own fixed dark look, which gives
every window a consistent feel and works the same on Linux. The cost is that it ignores a user's EDMC
theme choice. The palette is token-based, so a light variant would be a small change, and a Settings
toggle could be added later without a redesign.

## 5. The Mining Book layout

Three resizable panes with saved geometry:

1. **Bodies:** the current system's scanned landable bodies plus every saved hotspot, grouped in a
   `FoldList`, with a material filter and a rig-count filter. It opens on the body you're at.
2. **Hotspots:** the selected body's hotspots grouped by location, with rigs, mined tons and the tons-left
   range, plus what *you've* found so far on that kind of ground.
3. **Detail and map:** a card for the selected hotspot (material, density and amount, estimate, notes,
   with Mark depleted, Copy coordinates, Edit and Delete) and a map of coverage and hotspots.

See [MINING_TECH_SPEC.md](MINING_TECH_SPEC.md) for the data behind it.

## 6. Display scaling and checking

Default and minimum window sizes are written in 96-dpi pixels and multiplied by `style.dpi_factor` inside
the shell, so keep new layouts expressed that way. Windows have been checked by screenshot at 100% and
150% scaling. Other scales and Linux still need checking, tracked in [LINUX_TESTING.md](LINUX_TESTING.md).
