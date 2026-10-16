# Built-in overlay: specification and plan

WNTB can draw its own overlays, in a window it lays over Elite, instead of sending them to EDMCModernOverlay. This page records why, how it works, what is done and what is still to do. It is
optional and off until the player turns it on (Settings → Overlays → Overlay Connection → **Which overlay draws**). Windows only; Linux keeps EDMCModernOverlay. For players, the guide is [Setting up the overlay](OVERLAY_SETUP.md); the code is described in [TECHNICAL.md](TECHNICAL.md) section 10.

**Relation to EDMCModernOverlay.** The built-in overlay draws WNTB's displays only. Other plugins' overlays still need EDMCModernOverlay (or the older EDMCOverlay it replaces), and Linux needs it for everything. Both can run at once: with the built-in overlay chosen WNTB sends nothing to EDMCModernOverlay, so nothing of WNTB's is drawn twice, and the other plugins keep drawing there.

## Why

EDMCModernOverlay is a separate program with its own font, scaling and lifetime. Problems met while using it with WNTB: its default font has capital letters only, an old overlay window left
running after EDMC closed reconnects to the next session and draws a second copy of every card (see [Known issues](guide/known-issues.md)), WNTB cannot choose the font for its own cards, and
placement has to work around its right-hand clamp. Owning the window removes these, and matches the aim that WNTB alone is enough. `scripts/native_overlay_test.py` proved that a transparent,
click-through, layered window over Elite is clean, follows the game window, hides on alt-tab and does not stutter.

## How it works

- **The feature code does not change.** Every overlay feature already sends small payloads through `overlay.OverlayClient` (`send_message`, `send_shape`, `send_circle`, `send_vector`, each with an
  id and a ttl). With the built-in overlay chosen, `OverlayClient._send_raw` hands the payload to a scene instead of the socket (`overlay_native.py`). The hide-everything switch works unchanged.
- **The scene** (`overlay_scene.py`) keeps what is on the screen with when each item runs out. Sending an id again replaces it; a payload that draws nothing removes it. Drawing order is
  fixed by kind, panels then circles and lines then text, so text is always above its panel (no payload order can cover text).
- **The picture** (`overlay_raster.py`) draws the scene onto a transparent Pillow image the size of the game window. Conventions are the ones the features already use: a position is in canvas
  units (a 1280 × 960 canvas stretched over the window), and a size (a rectangle's width and height, a circle's radius, the text size) is in logical pixels, multiplied by the display scaling.
- **The window** (`overlay_window.py`) runs on a thread inside EDMC. It finds Elite's window, follows its position, size and display scaling, and hands each new picture to a topmost, layered,
  click-through window that never takes focus (`UpdateLayeredWindow`, per-pixel alpha). It shows only while Elite is the window you are in and there is something to show. Because it is a
  thread of EDMC, it ends with EDMC: no window can be left behind.
- **Staying on top.** Elite's window takes its place above other topmost windows when it is brought back to the front, which left the overlay showing but underneath it after an alt-tab. While it is showing, the window puts itself back above the game every half second, and one failed frame is logged and skipped instead of ending the overlay.
- **Rounded corners** are a built-in-only extra: a panel rectangle carries a `radius` in the payload and the raster draws it rounded (setting Appearance → Corners).
- **Pillow** is the one dependency, and EDMC's own build ships it.
- **Groups.** Each feature's overlay is a group of items (a panel, lines, circles) sharing an id prefix. Like EDMCModernOverlay, the built-in overlay places a group at the canvas position of its top left item and treats the distances between the items inside it as logical pixels (times the display scaling), so a card's lines are the same distance apart on any screen. The registered prefixes come from `register_modern_overlay_groups`.
- **Screenshots.** The game's own screenshot never includes an overlay, and a snipping tool takes the focus (the overlay hides unless **Keep showing** is on). `overlay_native.snapshot()` draws the scene at a screenshot's size so the Screenshots setting can lay it onto the converted copy.
- **Placement** reads the game window's real size and scaling from the window thread (`overlay_native.screen()`), is told there is no right-hand clamp (`Screen.native`), and uses no group
  offsets. The layout editor, anchors and saved placements work as before.
- **The font** is WNTB's own, independent of EDMCModernOverlay's: the file named by `wntb_overlay_builtin_font` in WNTB's `plugin/fonts` folder, else the bundled Source Sans 3 (SIL Open Font License, shipped with its license), else a system font. Appearance → Overlay font lists the files in that folder and
  **Add font file...** copies one in; a change is used within two seconds, and a font file added stays through updates (the updater only replaces what the release zip holds). EDMCModernOverlay's font is chosen separately, in its own list, when it is the overlay in use.

## What is done

- Scene, raster, window thread (with the re-raise above Elite and capture tools recognized), the switch and its Settings choice, group placement, hide-everything, keep-showing, screenshots with the overlay, text measuring, WNTB's own fonts (bundled Source Sans 3, add your own), the player documentation, tests, and the in-game test script. The player confirmed in the game (2026-10-16) that the cards line up, converted and captured screenshots include it, it stays above Elite after an alt-tab, and font size and color scheme changes hold.

## Still to do

1. **Try it in the game** and fix what shows: text sizes against the card layouts (the layouts size boxes from character estimates tuned on EDMCModernOverlay), circle radius units, the radar's
   lines and markers, vertical text position, placement at the edges, ultrawide and multiple monitors, fullscreen-windowed behavior, and the game's own menus.
2. ~~**Measure text** with the font itself~~ Done: while the built-in overlay is chosen, `overlay_native.measure` (Pillow's `getlength` at eight times the size, in the font in use) replaces the width estimates through `overlay_style.set_text_measurer`, padded 5% for whole-pixel font rounding, and right-aligned text uses the exact width. Boxes came out 5 to 8% narrower on the sample cards.
3. ~~**A font of its own**~~ Done (see above). Still to do: a text size that is not tied to EDMCModernOverlay's step sizes, and bold or other weights of the same family.
4. **Per-pixel quality**: text drawn over transparent areas (a few cards have text outside a panel), sub-pixel positioning, and a draw-on-change guard so a busy scene costs little.
5. **Reliability**: what happens when Elite restarts, the display changes or EDMC is slow; log and report problems in Check connection and Copy diagnostics.
6. ~~**Documentation** for players~~ Done: Overlay setup (the two overlays, using both, fonts), Known issues, Troubleshooting, the Linux and platforms guides, TECHNICAL and the module index.
7. **Linux**: not planned for now. It needs a compositor-aware window and input-shape handling that differs between X11 and Wayland.

## Decisions to revisit

- WNTB used to never start an overlay. The built-in window is WNTB's own, in EDMC's process, and only exists when the player chooses it.
- Running inside EDMC means a long stall in EDMC's Python could delay a redraw; the window thread keeps its own loop and EDMC's network calls release the lock, so this is expected to be small.
  A helper process remains an option if it is not.
