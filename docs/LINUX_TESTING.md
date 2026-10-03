# Linux test checklist

For anyone testing WNTB on Linux with Elite Dangerous under Steam Proton (or Wine, Lutris or Heroic).
Linux support is new and has only been unit-tested with mocked system calls, so real reports are
valuable. Note your distro, desktop (GNOME, KDE, Sway...), session type (X11 or Wayland), and whether
you run EDMC natively or as a Flatpak.

Where a step fails, copy the relevant lines from EDMC's log
(`~/.local/share/EDMarketConnector/EDMarketConnector.log`) into your report.

## 0. Setup

- [ ] `xdotool` is installed (`xdotool version` works in a terminal).
- [ ] Elite has been launched at least once through Steam, so its Proton prefix exists.
- [ ] EDMC's **Journal directory** points at
      `<prefix>/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous`. The
      prefix is usually `~/.local/share/Steam/steamapps/compatdata/359320/pfx`.
- [ ] For overlay features: EDMCModernOverlay is installed and its overlay is running.
- [ ] WNTB is copied into EDMC's `plugins` folder, EDMC is restarted, and the panel appears.

## 1. Basics

- [ ] Mode buttons switch, the panel collapses, and text and buttons look right (fonts, colors, dark
      theme).
- [ ] Settings → WNTB opens with every tab.
- [ ] Jump to a system: Powerplay, Exploration Value and Boxel Survey react to the journal event.
- [ ] No Python errors in the EDMC log.

## 2. Paths and journal

- [ ] Settings → Auto-Honk shows **no** orange journal hint when the Journal directory is right.
- [ ] Clear the Journal directory: the hint appears, and the log has a "Linux journal folder" warning.
- [ ] Set **Elite Wine/Proton prefix** to a wrong path: Auto-Honk reports the binds file can't be found.
- [ ] Clear it again: the Proton prefix is auto-detected.
- [ ] If you have them: a second Steam library folder, or Flatpak Steam, is detected.

## 3. Auto-Honk

- [ ] Settings → Auto-Honk → **Rescan** shows "Will press <key>" for your fire button.
- [ ] Elite running and focused: **Test Honk Now** reports "sent" and the scanner fires.
- [ ] Elite not focused, **Focus game window first** on: Elite comes forward and the honk fires.
- [ ] Elite not running: it reports "Elite Dangerous window not found".
- [ ] `xdotool` uninstalled: it reports that it isn't installed, with the install hint.
- [ ] A real jump with Auto-Honk enabled honks once, and not again on a revisit.
- [ ] Try a fire button bound to a letter, an F-key, a numpad key and a modifier if you can.

## 4. Screenshots

- [ ] Take an in-game screenshot: it converts to PNG and appears in the panel.
- [ ] The default source folder is the prefix's `Pictures/Frontier Developments/Elite Dangerous`.
- [ ] The cropped preview matches the panel that was open (this needs `Status.json`).
- [ ] **Open Folder** opens your file manager.
- [ ] The timer icon and auto-capture timer take a screenshot in-game.
- [ ] A folder you can't write to shows a plain permission message, with no Windows text.

## 5. Overlay (needs EDMCModernOverlay)

- [ ] Landing Assist, Interdiction Warning (**Test Warning**) and Discovery (test) all draw over the
      game.
- [ ] Card backgrounds are visible, not just the text.
- [ ] It works in borderless mode; note what happens in fullscreen.

## 6. Other features

- [ ] The Inventory pickup **sound** plays (Field Ops → Inventory settings).
- [ ] Codex **Backfill from Journal History** finds your journals.
- [ ] Codex details window: the Entry and Times found headings sort both ways, the **Not found** tab fills in
      (needs network the first time), and double-clicking an entry opens its Canonn search in your browser.
- [ ] Field Ops → **Colonisation Sites**: after docking at a construction depot, the site appears with its
      outstanding commodities, In Cargo matches your hold, and **Copy Shopping List** pastes elsewhere.
- [ ] Mining: journal backfill works, and in an SRV the surface bearing arrow and coverage map work.
- [ ] Copy buttons (Powerplay, BGS, Boxel Random): pasting into another app works.
- [ ] Network lookups (EDSM, Spansh, Canonn, GEC) return results.
- [ ] Powerplay → **Rares** opens the Rare Goods Finder: after a jump or login it lists the nearest
      rare goods, the Controlling Power column fills in from Spansh, and double-click opens Inara in
      your browser.
- [ ] Restart EDMC: per-commander data (BGS, Boxel, Codex) is still there.

## 7. BGS (rebuilt in 1.1.0)

- [ ] The BGS panel's grey line shows "Last tick: ..." within a few seconds (network call works).
- [ ] With the Journal directory set, the log has "BGS journal replay done for <CMDR>" and the totals
      cover the whole tick. With it cleared, the log says the replay was skipped and why.
- [ ] **View BGS Report** opens; the tick drop-down, the tabs (full system names, wrapping onto a second row
      when there are many), **Pin**, **× Close tab** and the footer key all render, with no missing glyphs.
- [ ] **Show a system**: typing narrows the list while you keep typing (the list must not steal the
      keyboard), the arrow shows every system, Up/Down/Enter/Esc work, clicking a name adds its tab.
- [ ] Pins and closed tabs survive restarting EDMC.

## Reporting

Open an issue with your setup line, the failing step number, and the log excerpt.
