# Linux test checklist

For anyone testing WNTB on Linux with Elite Dangerous under Steam Proton (or Wine, Lutris or Heroic).
Linux support is new and has only been unit-tested with mocked system calls, so real reports are
valuable. Note your distro, desktop (GNOME, KDE, Sway...), session type (X11 or Wayland), and whether
you run EDMC natively or as a Flatpak.

**Already seen working:** the WNTB Settings panel, and the test overlay, Discovery and Notable Bodies
overlays (KDE Wayland, Flatpak EDMC). A Flatpak EDMC needs the host-spawn permission in section 0 before
overlays will draw. Please note exactly what you see (which tabs, which overlays, how often) so anything
that differs can be checked against it.

Where a step fails, copy the relevant lines from EDMC's log
(`~/.local/share/EDMarketConnector/EDMarketConnector.log`) into your report.

## 0. Setup

- [ ] `xdotool` is installed (`xdotool version` works in a terminal).
- [ ] Elite has been launched at least once through Steam, so its Proton prefix exists.
- [ ] EDMC's **Journal directory** points at
      `<prefix>/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous`. The
      prefix is usually `~/.local/share/Steam/steamapps/compatdata/359320/pfx`.
- [ ] For overlay features: EDMCModernOverlay is installed and its overlay is running.
- [ ] If EDMC is a Flatpak: `flatpak override --user --show io.edcd.EDMarketConnector` lists all four
      permissions from the README (Linux, Step 3): the journals folder, the Bindings folder (`:ro`), the
      Pictures folder, and `org.freedesktop.Flatpak=talk`. Without the last one the overlay's sockets open (so
      **Check connection** passes) but its window never starts, and `xdotool` is invisible to WNTB.
- [ ] If EDMC is a Flatpak: the EDMC log has no "Host lookup of ... failed" lines from WNTB.
- [ ] **Elite Wine/Proton prefix** in Settings is empty unless you use a custom setup.
- [ ] An `overlay_client` process is running (`ps -eo args | grep overlay_client`).
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
- [ ] The honk key stays down for the whole **hold time** (set 8 to 10 seconds): the scan completes instead
      of stopping after about a second.
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

- [ ] Landing Assist, Interdiction Warning (**Test Warning**), Discovery (**Test Discovery**) and
      Notable Bodies (**Test Notable**, after ticking Enable) all draw over the game.
- [ ] Notable Bodies: scan a terraformable or an Earth-like, water or ammonia world and a violet banner
      appears; the same body does not alert twice.
- [ ] Card backgrounds are visible, not just the text.
- [ ] It works in borderless mode; note what happens in fullscreen.

## 6. Other features

- [ ] The Inventory pickup **sound** plays (Field Ops → Inventory settings).
- [ ] Codex **BKF** (backfill from journal history) finds your journals.
- [ ] Codex details window: the Entry and Times found headings sort both ways, the **Not found** tab fills in
      (needs network the first time), and double-clicking an entry opens its Canonn search in your browser.
- [ ] Field Ops → **REPORT** (colonisation sites): after docking at a construction depot, the site appears with its
      outstanding commodities, In Cargo matches your hold, and **Copy Shopping List** pastes elsewhere.
- [ ] Mining: journal backfill works, and in an SRV the surface bearing arrow and coverage map work.
- [ ] Copy buttons (Powerplay, BGS, Boxel **RND**): pasting into another app works.
- [ ] Network lookups (EDSM, Spansh, Canonn, GEC) return results.
- [ ] Exploration **N.S.** and **W.D.** buttons: after a jump, each shows a system and distance and copies the
      name to the clipboard (paste it elsewhere to check).
- [ ] Hovering a short-named button (for example **A.H.**, **RND**, **SES**, **P.P.**) shows its full name in a
      tooltip that disappears when you move away, and the GEC, Canonn and Codex sections start minimized.
- [ ] Powerplay → **RARES** (rares) opens the Rare Goods Finder: after a jump or login it lists the nearest
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
      "Credits this session: no change yet". The game-mode line stays visible on every mode button (the credits line
      is hidden on Exploration and Trade) and both disappear when you collapse the WNTB title.
- [ ] Switch modes: the credits line is **hidden on Exploration and Trade** and shown on Powerplay, BGS, Mining,
      Missions and Field Ops; the game-mode line stays on every mode.
- [ ] Earn or spend some credits: the second line changes to "+N cr earned" or "-N cr lost", and an hourly rate
      appears after a few minutes.
- [ ] Log out to the main menu and back in: the credits total carries on (same session). Restart EDMC while the
      game is running: the mode line and the credits total come back. Quit the game: the mode line goes back to
      "waiting for login".
- [ ] `session_credits.json` appears in the WNTB plugin folder, and a plugin update leaves it alone.

## 6d. Trade mode (new)

Tested on Windows only so far. Settings → WNTB → Trade first: tick **Enable Spansh trade lookups**.

- [ ] The **TRD** button appears with the others, and the **◀** / **▶** buttons at the top of the Trade panel are
      large and show their arrow glyphs (not empty boxes). The same buttons on Mining and Missions look right.
- [ ] **Session**: after docking, the ship and its pad size show; the hold line shows used, capacity and free
      tonnes. Buy and sell something: the profit lines appear. Refuel and repair: a **Net profit** headline appears
      with Fuel and Repairs lines under it. **Reset** clears it.
- [ ] Trade History: do some trading, press **Save session** (the message at the top says it saved), then **History**.
      The window opens like the BGS and Powerplay ones, with the session in the drop-down. Visit every tab: the tables fit
      the window with no column cut off at the right, the numbers look right, **Route** lists the stations in the order you
      flew them, **Trades** pages with Earlier / Later. Press **Save session** again after another trade: the entry updates
      (no duplicate). **Copy summary** pastes into another app; **Export log (CSV)** opens a file dialog and writes the file;
      **Delete session** asks first. **Reset** with unsaved trades asks whether to save first.
- [ ] Rebuild: trade for a while, then restart EDMC with the game still running. The Session page still shows the whole
      session (trades from before the restart included), the numbers don't double when new trades arrive, and after
      **Save session** the **Route** tab lists the stations from before and after the restart.
- [ ] Stock: buy some cargo and the Session page shows "Stock bought, not yet sold" with the cost and how much is
      aboard. Sell some: it comes down. Transfer cargo to a carrier: the total stays the same and "elsewhere" grows.
      Restart EDMC after buying while it was closed: the purchase is still counted. **Clear stock** empties it.
- [ ] Carriers (only if you have one): open Carrier Management once. The carrier's used and free cargo tonnes
      appear. Transfer cargo to it: the figure follows. Restart EDMC: it comes back without opening Carrier
      Management again (this reads the journal folder, so it also checks the Proton journal path).
- [ ] Settings → Trade lists your commanders with a carrier choice each; choosing **None** hides the carrier.
- [ ] **Market**: click the Commodity box; a suggestion list appears **under the box and does not steal the
      keyboard** (this is a borderless window, so check it stacks above EDMC under your window manager). Typing
      narrows it; Up/Down/Enter/Esc work; clicking a name fills the box.
- [ ] Layout: the Session, Routes and Market pages show orange section headings with a rule between them, values on the
      right, and aligned number columns; long station names wrap instead of being cut off; nothing is clipped on the
      right edge or makes the EDMC window wider. The buttons and (on Market) the Commodity box and **Sell** / **Buy**
      are **above** the results.
- [ ] Settings → Trade: untick **Search ground facilities** and **Search fleet carriers**; the results then show
      orbital stations only, and a search makes one request instead of two.
- [ ] The **Sell** / **Buy** buttons under the Commodity box: the chosen one is lit, switching clears the results,
      and the results heading says "Selling" or "Buying". All the page's buttons show their full labels (**Near me**,
      **Galaxy**, **Price finder**) with nothing cut off.
- [ ] **Near me** and **Galaxy** each return results for a common commodity (try Gold and Liquid oxygen). Each
      station says **orbital** or **ground** and its type. A
      fleet carrier appears in its own section, not mixed with stations. Stations without a pad for your ship are
      missing.
- [ ] **Routes**: **Find routes** shows "Asking Spansh..." with a counting timer, and a route within a couple of
      minutes. **Cancel** stops it. **Copy next system** puts the system name on the clipboard.
- [ ] No Python errors in the EDMC log, and the EDMC window did not get wider when you opened Trade.

## 7. BGS (rebuilt in 1.1.0)

- [ ] The BGS panel's grey line shows "Last tick: ..." within a few seconds (network call works).
- [ ] With the Journal directory set, the log has "BGS journal replay done for <CMDR>" and the totals
      cover the whole tick. With it cleared, the log says the replay was skipped and why.
- [ ] **REPORT** (view BGS report) opens; the tick drop-down, the tabs (full system names, wrapping onto a second row
      when there are many), **Pin**, **× Close tab** and the footer key all render, with no missing glyphs.
- [ ] **Show a system**: typing narrows the list while you keep typing (the list must not steal the
      keyboard), the arrow shows every system, Up/Down/Enter/Esc work, clicking a name adds its tab.
- [ ] Pins and closed tabs survive restarting EDMC.

## Reporting

Open an issue with your setup line, the failing step number, and the log excerpt.
