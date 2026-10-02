# WNTB Window Framework — scoping

Status: **built (2026-10-01)** - the `plugin/uikit/` kit, the Mining Book, and every external window converted (see section 6). Decisions taken: own fixed look (option A), no material-rate ranking for now, Canvas map. Verified by screenshot against stubbed EDMC modules; a live EDMC pass is still to do. Goal: one shared look and one shared set of building
blocks for every external (Toplevel) window in WNTB, with a three-pane layout, cards, a dark
consistent palette and an embedded map.

## 1. Why

Every window today styles itself: `powerplay_window.py` builds its own bold ttk styles,
`inventory_window.py` its own tab style, others use bare `ttk.Treeview` + default widgets. The
result is functional but plain, and inconsistent from window to window. Mining's six dialogs
(`mining_*_dialog.py`) are the plainest of all.

## 2. Windows in scope

| Window | Today | Becomes |
|---|---|---|
| Mining — System Bodies / hotspot browser | did not exist (only a flat body-survey dialog) | the **Mining Book**, the flagship three-pane window (§4) |
| Mining — hotspot add/edit, search, finder, price finder, reserve lookup, import/export, body survey | 7 separate basic dialogs | forms/tables on the shared kit; search + finder fold into the browser |
| Powerplay sessions, Rares | ttk notebook / treeview | shared header, tabs, tables |
| Field Ops inventory | custom tab style | shared tabs and tables |
| BGS detail, Codex Completionist | treeview popups | shared tables |
| Missions, Ship Builds | large mixed UIs | shared kit, later |

Not in scope: the main-window `plugin_app` panels. Those must follow EDMC's theme and the
width-bounding rules in the global CLAUDE.md; this framework only covers Toplevels.

## 3. Building blocks (`plugin/uikit/`, new package)

**Hard rule: the kit never touches ttk globally.** ttk themes and stock styles (`TButton`,
`Treeview`, ...) are application-wide, so changing them would recolour EDMC's main window and
every other plugin. The kit therefore uses classic tk widgets plus its own `FlatButton`,
`Combobox`, `SlimScrollbar` and `tk.PanedWindow`, and `style.skin(window)` colours a window's
classic widgets through Tk's option database scoped by that window's own name. A test enforces
this (`tests/test_ui_kit.py`). Consequence for later phases: ttk `Treeview` tables can only be
restyled through a name-scoped style (`WNTB.Treeview`) and headings stay native on Windows, so
table-heavy windows get a kit-built table instead.

- **Palette + tokens** (`ui/palette.py`): background layers, text, accent, success/warn/danger,
  and a colour-blind-safe set for status (shape/label carries state, as the minimap now does).
- **Style setup** (`ui/style.py`): one `ttk.Style` theme ("clam"-based) applied per window —
  flat cards, hairline separators, padded rows, striped tables, styled tabs/scrollbars/inputs.
  Fonts derive from `TkDefaultFont` so Linux and HiDPI still behave.
- **Window shell** (`ui/shell.py`): singleton Toplevel with saved geometry, min size, header bar
  (title, subtitle, action buttons), status footer, Esc-to-close. Replaces the per-window
  copies of show/refresh/close/_restore_geometry.
- **Widgets** (`ui/widgets.py`, `ui/table.py`): `Card`, `Pill` (status chip), `StatTile`,
  `FlatButton`, `Combobox`, `SlimScrollbar`, `ProgressBar`, `Tabs`, `FoldList` (collapsible grouped
  list), `ScrollFrame`, `field_grid`, and `DataTable` (striped, sortable, grouped, Treeview-like
  API; header and body columns kept aligned).
- **Map canvas** (`ui/mapview.py`): a `Canvas`-based replacement for the PIL→GIF minimap, so
  zoom, hover and click-to-select work. The existing `mining_coverage_render` stays for the
  fixed-size panel image.

Constraint kept from the project rules: any window content derived from external data
(Spansh names, filenames) is truncated/ellipsised with a hard cap; Toplevels don't affect main
window width, but the same discipline avoids runaway windows.

## 4. Flagship: Mining Book window

Three panes, resizable sashes, saved geometry:

1. **Left — bodies.** System bodies from our existing scan/Spansh data, grouped by ground type
   in a `FoldList`, each row showing distance, mining-location count and your hotspot count.
   Material filter dropdown. Auto-opens the body you are at.
2. **Middle — materials and hotspots.** Best materials for the body (our own data only —
   see Open Questions), then hotspots grouped by location with rigs, bearing/distance,
   `mined_tons`, and the tons-left range from `mining_deposit.py`.
3. **Right — detail card + map.** Hotspot card: material, density/amount pills, estimate,
   notes; actions Guide me there, Mark depleted, Copy coords, Edit, Delete. Below it a map
   view of coverage + hotspots (colour-blind-safe markers already done).

Data it needs already exists: `mining_hotspots.py` (incl. `mined_tons`), `mining_deposit.py`,
`mining_coverage.py`, `mining_body_survey.py`, `mining_spansh_client.py`. New: nothing
persistent beyond window geometry and the last-selected body.

## 5. Theme decision (settled: option A)

EDMC has its own light/dark/transparent themes and `theme.update()` recolours widgets to match.
WNTB's windows deliberately do **not** follow it:

- **A. Own fixed look, independent of EDMC theme — chosen.** Guarantees consistency, and works the same on Linux. Cost: it ignores a user's EDMC
  theme choice. The palette is token-based (`ui/palette.py`), so a light variant is a one-dict
  change if wanted.
- B. Derive the palette from EDMC's current theme — rejected: most of the "designed" feel is lost.
- C. A plus a Settings toggle — possible later without redesign.

Main-window panels (`plugin_app`) are unchanged and still follow EDMC's theme.

## 6. Status

All phases are built; everything below uses the kit and has been checked by screenshot against
stubbed EDMC modules (not yet in a live EDMC session):

| Phase | Windows | State |
|---|---|---|
| 1 | Mining Book (new) | Done; opened from a button on both Mining pages. Replaces the "Search Known Hotspots" and "Show System Bodies" dialogs. Rig-count and material filters, per-hotspot card and map. |
| 2 | Mining dialogs (hotspot add/edit, finder, price finder, reserve lookup, import/export) | Skinned with `ui_style.skin(dialog)`; dropdowns are the kit's `Combobox`. |
| 3 | Powerplay sessions, Rare Goods, Inventory | Ported to `WindowShell` + `Tabs` + `DataTable` (+ `ProgressBar`). Behaviour and wording unchanged. |
| 4 | BGS report, Codex Completionist, Ship Builds (window and dialog) | Ported; grouped tables use `DataTable(group=True)`. |
| 4 | Missions popups, Screenshots preview | Skinned only (they are plain-tk content builders). |

Not converted on purpose: the Mining *Settings tab* list (`mining_hotspot_settings.py`) and every
other Settings tab, since those live inside EDMC's own preferences window and follow its theme.

The sample-data prototype (`plugin/uikit/demo.py`) has been removed now that the real browser exists.

## 7. Decisions taken on the open questions

1. **Material rates:** done, from your own records only. A bundled third-party sheet was used briefly
   and removed (provenance unverifiable; see `docs/ATTRIBUTIONS.md`). The browser shows, per kind of
   body, the share of the deposits you have saved there that were each material (`mining_ground.py`),
   flags materials you have saved on the body, and the material filter ranks scanned bodies by that
   share. It stays empty until you record hotspots. The "materials you have saved here" line stays
   alongside it as the record of what the body *does* hold.
2. **Demo:** retired; the real windows are the reference.
3. **Live pass:** font scaling checked at 100% and 150% by screenshot (Mining Book, BGS, Codex); other
   scales and Linux are still unchecked, tracked in `docs/LINUX_TESTING.md`. Windows now scale
   their default and minimum sizes with the display (`ui.style.dpi_factor`), which fixed a clipped
   right-hand pane at 150%.
