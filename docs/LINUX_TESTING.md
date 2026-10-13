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
      permissions from the [Linux guide](guide/linux.md) (Step 3): the journals folder, the Bindings folder (`:ro`), the
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

- [ ] Settings → Exploration → Auto-Honk shows **no** orange journal hint when the Journal directory is right.
- [ ] Clear the Journal directory: the hint appears, and the log has a "Linux journal folder" warning.
- [ ] Set **Elite Wine/Proton prefix** to a wrong path: Auto-Honk reports the binds file can't be found.
- [ ] Clear it again: the Proton prefix is auto-detected.
- [ ] If you have them: a second Steam library folder, or Flatpak Steam, is detected.

## 3. Auto-Honk

- [ ] Settings → Exploration → Auto-Honk → **Rescan** shows "Will press [key]" for your fire button.
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
- [ ] Surface Compass (Exploration mode, **Compass** section; Settings → Overlays → Surface Compass): **Test Compass** draws an arrow and a name
      on the left; on a planet surface the section shows the nearest hotspot with a distance; **MARK** makes a mark; **TARGET** steps through
      the marks here; **MARKS** opens the window (edit, **Here**, Delete twice); with the compass enabled the arrow follows the target as you
      move and turn, and clears when you lift off. Check the Mining settings tab no longer has the waypoint tick.
- [ ] Materials (Field Ops mode, **Materials** section; added 2026-10-13): log in and the row shows the pieces of each type; collect or discard a
      material and "Last: ..." follows; a material at its limit is named; **MATERIALS** opens the window; Search, Type, Grade and **Only what is at
      the limit** narrow the table; headings sort; the window keeps its size and place; restart EDMC mid-session and the counts are right.
- [ ] Engineering (Field Ops, **BLUEPRINTS** on the Materials section; added 2026-10-13): the window opens with **Blueprints** and **Wishlist** tabs;
      Search (it waits a moment after typing) and the Module drop-down narrow the list; picking a row shows its ingredients, what you hold and
      where each is found; **Add to wishlist** and a double-click add; the Wishlist tab shows each entry's crafts, whether it can be made and
      the shopping list; **Set crafts**, **Remove** and **Clear list** ask twice; the Materials section shows the `Wishlist:` line and stays narrow;
      the window keeps its size and place.
- [ ] Notes (Exploration mode, **Notes** section): the quick-add box saves a line against the current system; **NOTES** opens the window;
      the editor's text box takes typing and paste; **Here** fills the system and body; **Delete** asks twice; the window keeps its size
      and place after closing and reopening.
- [ ] Trade Watch list (Trade mode, **Watch list** row; added 2026-10-13): **WATCH** opens the window; add a commodity by typing (the suggestion
      list appears and a click or Enter picks it) and **Add**; open a station's commodity market in the game and the commodity gets a price, with
      the station under it when picked; **Remove** asks twice; with Trade lookups on, **REFRESH** fills in Spansh prices and says so, and with
      them off it says to turn them on; the row stays narrow with a long system name; restarting EDMC keeps the list and the seen prices.
- [ ] Flight Alerts (Settings → Overlays → Flight Alerts): **Test Card** draws a card on the right, below where the Inventory display sits; with a carrier jump
      scheduled the countdown ticks every second and turns red in the last minute; a plotted neutron star with the tank at or under 50%
      shows the unscoopable-star line; the sound box is available only when `canberra-gtk-play` or `paplay` is installed, and a sound plays
      when an alert starts.
- [ ] Notable Bodies: scan a terraformable or an Earth-like, water or ammonia world and a violet banner
      appears; the same body does not alert twice.
- [ ] Landing Assist when the overlay starts late: request docking right after starting EDMC and the game, before the
      overlay client has finished starting. The card and pad diagram appear once the overlay is up (within about a
      minute), without needing another docking event. Switching between a starport and a fleet carrier removes the
      old diagram straight away.
- [ ] Card backgrounds are visible, not just the text.
- [ ] It works in borderless mode; note what happens in fullscreen.

## 6. Other features

- [ ] The Inventory pickup **sound** plays (Field Ops → Inventory settings).
- [ ] Codex **BKF** (backfill from journal history) finds your journals.
- [ ] Codex details window: the Entry and Times found headings sort both ways, the **Not found** tab fills in
      (needs network the first time), and double-clicking an entry opens its Canonn search in your browser.
- [ ] COL mode → **DASHBOARD** (colonization sites): after docking at a construction depot, the site appears with its
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

- [ ] Settings → Exploration → Auto-Honk, Field Ops → Screenshots and Field Ops → Inventory each show a **Works on:** line, green when
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
      "Credits this session: no change yet". Both lines (and the Plugin version line above them) stay visible on every
      mode button, and all disappear when you collapse the WNTB title.
- [ ] Switch through every mode, including Exploration and Trade: the whole block under the mode buttons stays visible.
- [ ] After earning a Powerplay merit, a **Merits this session: +N (+N merits/hr)** line appears under the credits line, on
      every mode; the rate appears after a few minutes. It is absent before the first merit.
- [ ] Earn or spend some credits: the second line changes to "+N cr earned" or "-N cr lost", and an hourly rate
      appears after a few minutes.
- [ ] Log out to the main menu and back in: the credits total carries on (same session). Restart EDMC while the
      game is running: the mode line and the credits total come back. Quit the game: the mode line goes back to
      "waiting for login".
- [ ] `session_credits.json` appears in the WNTB plugin folder, and a plugin update leaves it alone.

## 6d. Trade mode

Windows was checked as Trade was built. Linux was checked against this list on 2026-10-09 with no new issues (the boxes
below stay unticked, like the rest of this file, so it can be run again). Settings → WNTB → Trade first: tick **Enable Spansh trade lookups**.

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
- [ ] A session spans play sessions: trade, log out of the game and back in (a new journal file), restart EDMC, then trade
      some more. The Session page keeps one running tally through all of it (nothing starts afresh until you press
      **Reset**), the numbers don't double, and after **Save session** the **Route** tab lists the stations from every
      part. Also play a short stretch with EDMC closed, then start EDMC: that stretch is added the next time it sees you.
      With two commanders, switching to the other and back leaves each one's tally as it was.
- [ ] Session page: the sections read "This session", "In your ship" (Ship hold, and the cargo with an "In hold"
      column; "Hold space" above it) and, if you have a carrier, "Carrier cargo used / free". There is no unsold-stock list and no Clear stock
      button. Buy cargo, then save the session: Trade History's **Stock & carrier** tab shows it under "Bought, not yet
      sold (journal estimate...)".
- [ ] Two computers: copy the other computer's newer journal files into this one's journal folder while EDMC is running.
      Within a minute the foot of the Session page reads "Journals reviewed [local date and time]. N new journals since the last review.", and the trades,
      stock and carrier figure from those files appear (nothing doubles if you copy the same files again). Press
      **Rebuild** on the Session page, type the date and time the session began (UTC), and check the totals against the
      other computer. A carrier figure with a `~` in front means estimate: open Carrier Management and it goes away.
- [ ] Carriers (only if you have one): open Carrier Management once. "Carrier cargo used" and "Carrier cargo free" appear
      (separate from the "Ship hold" line). Transfer cargo to it: the figure follows. Restart EDMC: it comes back without opening Carrier
      Management again (this reads the journal folder, so it also checks the Proton journal path).
- [ ] Settings → Trade lists your commanders with a carrier choice each; choosing **None** hides the carrier.
- [ ] **Market**: click the Commodity box; a suggestion list appears **under the box and does not steal the
      keyboard** (this is a borderless window, so check it stacks above EDMC under your window manager). Typing
      narrows it; Up/Down/Enter/Esc work; clicking a name fills the box.
- [ ] Layout: the Session, Routes and Market pages show orange section headings with a rule between them, values on the
      right, and aligned number columns; long station names wrap instead of being cut off; nothing is clipped on the
      right edge or makes the EDMC window wider. The buttons and (on Market) the Commodity box and **Sell** / **Buy**
      are **above** the results.
- [ ] Settings → Trade: untick **Include ground facilities** and **Include fleet carriers**; the results then show
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
- [ ] **Hops** button cycles 2, 3, 4, 5. **Round trip** (docked at a normal station, not a carrier) answers in about
      20 seconds with up to three pairs, each showing what to carry out and back; both legs are loaded. A route's page
      shows an estimated profit per hour and supply/demand per hop.
- [ ] Settings → Trade route filters: set **ignore prices older than** to a small number of hours and tick **Routes may use
      systems that need a permit**; **Find routes** and **Round trip** still answer (an old-price filter can leave fewer results).
- [ ] No Python errors in the EDMC log, and the EDMC window did not get wider when you opened Trade.

## 7. BGS (rebuilt in 1.1.0)

- [ ] The BGS panel's grey line shows "Last tick: ..." within a few seconds (network call works).
- [ ] With the Journal directory set, the log has "BGS journal replay done for [CMDR]" and the totals
      cover the whole tick. With it cleared, the log says the replay was skipped and why.
- [ ] **REPORT** (view BGS report) opens; the tick drop-down, the tabs (full system names, wrapping onto a second row
      when there are many), **Pin**, **× Close tab** and the footer key all render, with no missing glyphs.
- [ ] **Show a system**: typing narrows the list while you keep typing (the list must not steal the
      keyboard), the arrow shows every system, Up/Down/Enter/Esc work, clicking a name adds its tab.
- [ ] Pins and closed tabs survive restarting EDMC.

## 7b. Catching up after EDMC was closed (added 2026-10-10, Windows-tested only)

All of this is platform-neutral Python reading the journal folder, but it has only been tried on Windows. The Linux
risks are the Journal directory (section 0), file modified times on the Proton prefix, and large journal folders.
To test, play a short session with EDMC **closed** (or close it mid-session), then start EDMC and look at each:

- [ ] **Missions**: accept a mission, close EDMC, start it mid-game: the mission shows without logging in again. Hand a
      mission in with EDMC closed: it disappears after the restart. (An expired mission with no journal entry can stay
      until the next login; that is expected.)
- [ ] **Colonisation**: deliver cargo to a depot with EDMC closed, then start EDMC: the site's figures include the
      delivery once. Restart EDMC again: nothing changes (no double count).
- [ ] **Codex**: find a Codex entry with EDMC closed, start EDMC: the summary line goes up by one. The first start
      after updating only sets the starting point.
- [ ] **Boxel Survey**: jump to a few systems with EDMC closed; after a restart the visited count (Settings → Boxel
      Survey) includes them.
- [ ] **Trade**: the route start (Routes page) is the last real station you docked at, also after a restart and after
      switching commander; carrier tritium, location and orders appear under the carrier lines if you have one.
- [ ] **Inventory**: restart EDMC while on foot or with items in the ship locker: the bars fill without a login.
- [ ] **Exploration Value**: after a restart mid-system, "System bodies" shows scanned of total, and "Last data sale"
      shows the last sale of the session.
- [ ] Startup is not noticeably slower, and the EDMC log has no Python errors from `colonisation_catchup`,
      `journal_files`, `visited_systems`, `codex_backfill` or `journal_scan`.

## 7c. Per-commander data (added 2026-10-10, Windows-tested only)

Nothing should be shared between commanders. Needs two commanders (or one commander and a second journal), on Linux with
the Journal directory set (section 0). The code only uses JSON keys, UTF-8 files and `os.replace`, so the Linux risks are
the journal folder and the order file modified times give.

- [ ] **Mining**: save a hotspot as commander A; log in as B: the Mining Book shows none of A's. Save one as B, log back
      in as A: only A's. The coverage map follows the same way.
- [ ] **Codex**: log in as each commander in turn: the details window subtitle names whose tally it is, and the counts
      differ. After updating from an older version, each commander's tally is rebuilt once from their own journals (the
      panel says so while it reads).
- [ ] **Powerplay**: the Sessions window's History tab and its total show only the commander you are playing.
- [ ] **Boxel Survey**: the "Surveyed: N systems" line and the exported CSV change with the commander.
- [ ] **Trade**: switching commander clears the previous one's ship, hold and route results from the Session page; the
      History window opens on the active commander.
- [ ] A commander typed in another case (the journal can write `BOCHEAUX` for `Bocheaux`) is the same commander.
- [ ] Nothing under the plugin folder is named after a commander except the `mining_sessions/` archive files.

## 7d. Colonization FC column, shopping-list overlay, start-up commander (added 2026-10-10, Linux-tested only: check on Windows)

Written and tried on Linux (Flatpak EDMC, Proton game, EDMCModernOverlay). The code is platform-neutral Python, but none
of it has been run on Windows yet. Needs a commander with a fleet carrier and a registered construction site.

- [ ] **FC column**: the Colonization Sites window shows an FC column for a commander with a fleet carrier (and not for one
      without), and it follows a transfer made at the carrier. Restarting EDMC keeps the figures and never counts a
      transfer twice. A commander set to None in the Trade settings gets no FC column.
- [ ] **Window follows the commander**: with the window open, log in as another commander; its sites change.
- [ ] **Start-up commander**: start EDMC with the game closed; the Field Ops panels (Colonization, Codex, Ship Builds, Trade)
      show the last commander instead of "waiting for commander login", and the EDMC log has "No game running at
      start-up; restored commander ..." (about four seconds after start). Then log in as someone else: everything switches.
- [ ] **Overlay card** (Settings, Colonisation: tick the overlay option; **Test Overlay** draws a sample): the table shows
      Commodity, Required, Remaining, FC, Cargo and To buy, with a tick when the hold covers a row, and a remaining/trips footer.
- [ ] The card appears: in a commodity market at a station; at your own carrier in the station-services screens (the game
      writes no `Market` event for a carrier's market); with the right-hand cockpit panel open when docked at the carrier
      (the cargo transfer); in Carrier Management; docked at a construction site. It goes when you leave, and the OVERLAY
      button forces it on and off. The EDMC debug log lines "Colonization overlay ..." say what was decided and why.
- [ ] Rows left at the default list every commodity; the card fits on screen from the default position (20, 300).
- [ ] Windows paths: `Status.json` reports the same `GuiFocus` values (5 in the services screens, 1 for the right-hand panel).

## 7e-3. Overlay Placement: Show checkbox (Windows-tested only: check on Linux)

- [ ] Each row on **Overlays → Overlay Placement** has a **Show** checkbox. Unticking one (then OK) hides that display; ticking it brings it back
      where it was. **Reset all to defaults** ticks them all.

## 7e-2. Raven Colonial sharing (needs a Raven project for a site; Windows-tested only: check on Linux)

- [ ] **Settings → Colonization → Raven Colonial** has a master switch and two checkboxes (all off, the two greyed out until the master is ticked) and a masked key field. With the master off, Report Complete to Raven refuses.
- [ ] With the first on, a delivery at a construction site Raven has a project for appears on Raven; with it off, nothing is sent.
- [ ] **Raven Progress** shows Raven's remaining need beside WNTB's for the selected site, including one still being built.
- [ ] **Test key** (beside the key box) says the key is accepted, with Raven's name for you, or that it was not accepted.
- [ ] The link under the key box opens ravencolonial.com/user in your browser.

## 7e-4. Colonization Sites window header (Windows-tested only: check on Linux)

- [ ] The header has **Copy Shopping List**, **Rescan Carrier**, **Raven Colonial ▾** and **Manage Sites ▾**. The two menus open under their buttons,
      are readable (dark colors) and close when you click elsewhere or pick an item.
- [ ] **Raven Colonial ▾** lists Planned Builds, Raven Progress, Open Selected Build on Raven, Open This System on Raven, Raven Colonial
      Website and Report Complete to Raven; the three Open items open the right page in your browser.
- [ ] A site you renamed in the game takes its new name after you dock at it again.

## 7e-1. Rescan Carrier (Windows-tested only: check on Linux)

- [ ] With a fleet carrier and some transfers in the journals, **Rescan Carrier** in the Colonization Sites window rebuilds the FC column
      from the last 30 days; the status line names the commodities and tons. Pressing it twice gives the same figures.

## 7e. Colonization Sites window: sites list, totals, Where to buy (added 2026-10-11, Windows-tested only: check on Linux)

Written and tried on Windows. The code is platform-neutral Python and Tk, but the window layout has only been seen on
Windows. Needs a commander with at least one registered construction site and an internet connection.

- [ ] The window opens at about 1300 x 780 with the sites on the left and the detail on the right; nothing is clipped at
      its minimum size (1180 x 640), and the divider between the commodity table and Where to buy drags.
- [ ] Picking a site shows its progress bar, the six totals, and its commodities; the Filter box, **Hide rows
      already covered** and the column headings (click, click again to reverse) all work.
- [ ] **Buy Trips and Haul Trips** (needs a fleet carrier with stock stored on it): a commodity fully on the carrier shows Buy
      Trips 0 and a Haul Trips above 0; the totals show **t on your carrier**, **trips to buy** and **trips to haul**.
- [ ] **Row colors**: a commodity row turns green when the hold plus the FC column covers the site's remaining need
      (exactly equal is green), orange when together they are more than needed, and keeps the normal look while short.
      The tint stays visible, only lightened, when the row is hovered or selected.
- [ ] **Where to buy**: pick a commodity row, press **Find nearest**: results appear, closest first, the button is
      disabled while it searches, and the window stays responsive.
- [ ] **Landing pad**: Any size lists stations whose largest pad is Medium or Small; Large only lists none of those.
- [ ] **Include fleet carriers** off lists no carriers; on adds a **Fleet carriers** group under the stations.
- [ ] The **Planetary** column says Yes for planetary ports, outposts and settlements and No for orbital stations and
      carriers; the whole results table fits at the window's minimum width.
- [ ] **Here** puts the system you are in (the last system EDMC saw) into Around. **Copy System** copies the selected row, and so does clicking a result row (a station or a route stop) at once.
- [ ] With no network, the panel says the search failed and the button comes back.
- [x] **Find all** (added 2026-10-12): lists a heading per commodity still to buy with up to 5 stations under each; the
      button reads **Stop** while it runs and stopping keeps what was found; the window stays responsive.
- [ ] **Planned Builds (added 2026-10-12, needs the internet):** select a site, press **Planned Builds** (in the **Raven Colonial** menu): a window lists Raven Colonial's sites for its system (building, planned, complete), marks the ones you track and shows each planned or building site's **Full cost**; clicking a row names its biggest commodities; **Refresh** works; with no network it says it could not reach Raven Colonial.
- [ ] **Suggested route (added 2026-10-12):** after Find all, a "Suggested route" group comes first with numbered stops and the commodities to buy under each; **Copy Route** puts plain lines on the clipboard.
- [x] **Remembered choices**: change Within, Sort, Landing pad and Include fleet carriers, run a search, close and reopen
      the window: the same choices are back.
- [x] **Only what [station] sells**: greyed out until you open a station's commodity market; then it names the station and
      narrows the list to what that market has for sale (in stock, with a buy price); it unticks itself when you undock.
      (`Market.json` lives in the journal folder: check EDMC's journal path on Linux/Proton.) Checked on Linux 2026-10-12 (reported by the developer).

## 7f. Overlay Placement and the Overlays settings tab (added 2026-10-11, Windows-tested only: check on Linux)

Written on Windows against a 3840 x 2160 screen in EDMCModernOverlay's fill mode. The logic is platform-neutral, but
reading the screen size from inside the Proton prefix (and the overlay's log), the display scaling under XWayland, and how the
overlay maps its canvas and sizes there, have not been seen on Linux.

- [ ] **Settings -> Overlays** has the tabs Overlay Connection, Overlay Placement, Colonization, Discovery, Inventory,
      Interdiction Warning, Landing, Mining, Notable Bodies and Screenshots; General no longer has an overlay tab.
- [ ] The Overlay Placement tab's info line shows your real screen size and display scaling, from the EDMCModernOverlay log or
      `DisplaySettings.xml` (if it says "game files not found", note the Wine/Proton prefix path and report it). Under
      XWayland or Wayland scaling the overlay's log is the best source; check its numbers match what you see.
- [ ] It shows the overlay mode EDMCModernOverlay uses (fit or fill).
- [ ] **Show placement preview** draws a labeled box for every display, at its real size, all on the screen.
- [ ] Change a display to **Bottom left** with offsets 20 / 20, press OK, then **Test Overlay** (or the feature's test
      button): it appears in the bottom left corner of the game screen.
- [ ] A display set to **Bottom left** with offsets 40 / 40 sits 40 pixels in from the bottom left corner of the screen.
- [ ] A display set to a **Right** spot (Inventory pickups, Screenshot messages) sits against the right edge of the screen at its
      full width, not short of it; Settings -> Overlays -> Overlay Placement -> **Show placement preview** shows the same.
      (WNTB sets an offset on that display's EDMCModernOverlay group; if it sits short of the edge, the EDMC log has
      "Could not set the EDMCModernOverlay offset".) Unticking **Carry displays on the right to the screen edge** puts them back at
      the limit.
- [ ] A position set in an older version's X/Y boxes shows as **Exact position** with the same numbers.

## 7g. Overlay Appearance (added 2026-10-11, Windows-tested only: check on Linux)

- [ ] **Settings -> Overlays -> Appearance** exists, with a Color scheme menu only (text size and spacing are fixed).
- [ ] **Show sample** draws the Colonization card in the game in the picked scheme.
- [ ] At **Largest** with **Roomy** padding, each display (Colonization, Discovery, Notable, Landing, Inventory, Mining,
      Screenshots) keeps its text inside its border without wrapping. Note any that do not, with the font and Proton/Wine setup.
- [ ] Changing the scheme recolors every display; Interdiction stays red.
- [ ] After OK, the choices are still set when Settings is reopened. **Reset to defaults** restores Elite orange / Default /
      Comfortable / Normal.

## 7h. Colonization mode (added 2026-10-11, Windows-tested only: check on Linux)

- [ ] The button row has a **COL** button (eight buttons); the panel is not noticeably wider than before.
- [ ] COL shows **Current project** for your newest active site and a **History** block; DASHBOARD opens the sites window, and
      OVERLAY toggles the overlay card (lit while on).
- [ ] Without a fleet carrier there is no Carrier row, Trips left reads like "3 loads of 400 t", and the sites window has a single
      Trips column. With one, Carrier is shown and Trips left reads "N to buy · N to haul".
- [ ] After delivering cargo to a depot, "You delivered" and "Recently" go up by the same tonnes, and again after restarting EDMC
      (no double counting).
- [ ] After a build completes, History's "done" count goes up.
- [ ] **History rebuild (added 2026-10-12):** the first start after updating, the log says "Colonization history rebuilt for [CMDR]"
      and the History note's "Counted since" date moves back to the oldest delivery in your journals. Restarting EDMC does not
      rebuild again, and the totals do not double. (Needs Elite's journal folder set; on Linux that is inside the Proton prefix.)
- [ ] **Claims line (added 2026-10-12):** after the history rebuild, the History block has a "Claims" line (for example "5 systems claimed · 5 beacons") for a commander who has claimed systems.
- [ ] **History chart:** the "Last 14 days" line draws a row of blocks of different heights (no empty boxes) and "Busiest site" names a site.
- [ ] **Overlay card footer:** with a fleet carrier it reads `N remaining  N to buy  N to haul`; without one, `N trips to finish`.

## 7i. Added in 1.7.0 (Windows-tested only: check on Linux)

- [ ] **Boxel Survey catch-up:** scan a few bodies with EDMC closed, start EDMC: Settings -> Boxel Survey shows them, and a second
      restart changes nothing. (Needs the journal folder; on Linux that is inside the Proton prefix.)
- [ ] **Powerplay cycle tally:** the panel shows **Cycle N merits** and **Cycle N CP** under the session lines, and they are still
      there after restarting EDMC.
- [ ] **Trade, Round trip:** each pair lists its loads with prices, profit per tonne, supply and demand; docked at a fleet carrier
      the result says it started from the carrier. The Trade setting for the search radius changes how far it looks.
- [ ] **Trade, Session page:** ends with the game's career totals for the commander.
- [ ] **Waypoint Route, From plotted route:** plot a route in the game, press the button: its systems are added.
- [ ] **Community goals:** the Community Goals page lists payouts under **Paid out**.
- [ ] **Colonization, Find all:** the results begin with a suggested shopping route, and **Copy Route** puts it on the clipboard.
- [ ] **Planned Builds:** the **Full cost** column fills, the window's subtitle adds up the planned builds, and clicking a row names
      the building and its five biggest commodities.

## 7j. Plugin version line (added after 1.7.0, Windows-tested only: check on Linux)

- [ ] The first line under the mode buttons reads **Plugin: vX.Y.Z** above the game-mode line, and does not widen the panel.
- [ ] After an automatic update is downloaded it reads **vX.Y.Z download - Restart EDMC** in bold black on orange (check the Default,
      Dark and Transparent themes); after the restart it reads **Plugin: vX.Y.Z (updated)** in green for about 15 seconds.

## Reporting

Open an issue with your setup line, the failing step number, and the log excerpt.
