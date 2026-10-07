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

- [ ] Settings → Exploration → Alerts shows **no** orange journal hint when the Journal directory is right.
- [ ] Clear the Journal directory: the hint appears, and the log has a "Linux journal folder" warning.
- [ ] Set **Elite Wine/Proton prefix** to a wrong path: Auto-Honk reports the binds file can't be found.
- [ ] Clear it again: the Proton prefix is auto-detected.
- [ ] If you have them: a second Steam library folder, or Flatpak Steam, is detected.

## 3. Auto-Honk

- [ ] Settings → Exploration → Alerts → **Rescan** shows "Will press <key>" for your fire button.
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
- [ ] Codex **BKF** (backfill from journal history) finds your journals.
- [ ] Codex details window: the Entry and Times found headings sort both ways, the **Not found** tab fills in
      (needs network the first time), and double-clicking an entry opens its Canonn search in your browser.
- [ ] Field Ops → **COL** (colonisation sites): after docking at a construction depot, the site appears with its
      outstanding commodities, In Cargo matches your hold, and **Copy Shopping List** pastes elsewhere.
- [ ] Mining: journal backfill works, and in an SRV the surface bearing arrow and coverage map work.
- [ ] Copy buttons (Powerplay, BGS, Boxel **RND**): pasting into another app works.
- [ ] Network lookups (EDSM, Spansh, Canonn, GEC) return results.
- [ ] Exploration **N.S.** and **W.D.** buttons: after a jump, each shows a system and distance and copies the
      name to the clipboard (paste it elsewhere to check).
- [ ] Hovering a short-named button (for example **A.H.**, **RND**, **SES**, **P.P.**) shows its full name in a
      tooltip that disappears when you move away, and the GEC, Canonn and Codex sections start minimized.
- [ ] Powerplay → **RAR** (rares) opens the Rare Goods Finder: after a jump or login it lists the nearest
      rare goods, the Controlling Power column fills in from Spansh, and double-click opens Inara in
      your browser.
- [ ] Restart EDMC: per-commander data (BGS, Boxel, Codex) is still there.

## 6b. Fixed in the platform audit - please confirm

- [ ] Settings → Exploration → Alerts, Field Ops → Screenshots and Field Ops → Inventory each show a **Works on:** line, green when
      it can work here and orange (with the reason) when it can't. Try it with and without `xdotool`.
- [ ] Take a normal screenshot and an Alt+F10 hi-res one: both are found, converted and named, and the
      hi-res one is treated as hi-res (the journal path is Windows-style, `\ED_Pictures\...`).
- [ ] Open every modal dialog without it erroring or staying behind the main window: Mining → Add/Edit
      Hotspot, Find Hotspots, Find Best Price, Check Ring Reserve, Import/Export Hotspots, and Field Ops →
      Add/Edit Ship Build. Each should stay on top and block the window behind it.

## 6c. Game mode and credits lines (under the mode buttons)

- [ ] Before logging in, the first line reads "Game mode: waiting for login…" and the second "Credits this
      session: waiting for your balance…".
- [ ] After loading into the game: "You are in Solo mode." (or Open, or Private Group with its name) and
      "Credits this session: no change yet". Both stay visible when you switch between every mode button and
      disappear only when you collapse the WNTB title.
- [ ] Earn or spend some credits: the second line changes to "+N cr earned" or "-N cr lost", and an hourly rate
      appears after a few minutes.
- [ ] Log out to the main menu and back in: the credits total carries on (same session). Restart EDMC while the
      game is running: the mode line and the credits total come back. Quit the game: the mode line goes back to
      "waiting for login".
- [ ] `session_credits.json` appears in the WNTB plugin folder, and a plugin update leaves it alone.

## 7. BGS (rebuilt in 1.1.0)

- [ ] The BGS panel's grey line shows "Last tick: ..." within a few seconds (network call works).
- [ ] With the Journal directory set, the log has "BGS journal replay done for <CMDR>" and the totals
      cover the whole tick. With it cleared, the log says the replay was skipped and why.
- [ ] **RPT** (view BGS report) opens; the tick drop-down, the tabs (full system names, wrapping onto a second row
      when there are many), **Pin**, **× Close tab** and the footer key all render, with no missing glyphs.
- [ ] **Show a system**: typing narrows the list while you keep typing (the list must not steal the
      keyboard), the arrow shows every system, Up/Down/Enter/Esc work, clicking a name adds its tab.
- [ ] Pins and closed tabs survive restarting EDMC.

## Reporting

Open an issue with your setup line, the failing step number, and the log excerpt.
