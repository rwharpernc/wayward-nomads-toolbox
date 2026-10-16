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

## Testing: start here

**1.15.0 is the current release.** 1.10.0 added Materials, Engineering, the material trader finder and the Expedition planner, and was tested on
Linux; 1.10.1 stopped the Expedition and Materials sections from widening the main panel; 1.10.2 made long names wrap instead of being cut off. 1.10.1 and 1.10.2
were tested on Windows only, and so were 1.11.0, 1.12.0, 1.13.0, 1.14.0, 1.14.1 and 1.15.0.

**The Linux checks for 1.15.0** are the items in section 6 below about the Route overlay, the Expedition card and survey counts, and the overlay padding and alignment (every card's text starts at the same left edge, the same distance from its border), plus a look at the new default overlay spots. **The Linux checks for 1.14.0** are the Credits Ledger window (click the Credits line: it opens, fits, and the tabs fill), the Colonization History window (HISTORY button), fold sections starting folded, and Ship Builds folding. **The Linux checks for 1.13.0** are the items in section 6 below marked "added in 1.13.0": mission progress colors and the alert widths. **The Linux checks for 1.12.0** are the items in section 6 below marked "added in 1.12.0": the Missions window and pinned missions, Best picks and Source commodities, the Missions overlay card, the Upgrade planner, Megaship scans and the Ship planner's subtract option.

**The Linux checks for 1.11.0** are also still open: Settings → General → **Help** (Report an issue, Copy diagnostics); the Engineering window's **Engineers** tab
(places, unlock steps, the Bubble / Colonia filter) and **Ship planner** tab; BGS rebuilding a period that closed while EDMC was not running; and finished Colonization builds
losing the "Construction Site:" prefix. The data behind the Engineering window changed too (five recipes corrected, new synthesis rows and materials, the Colonia
engineers' upgrades). The 1.10.2 wrapping and panel-width items are still to do.

**Getting set up**
1. Install the released **1.15.0** the normal way (the automatic update, or the zip from the
   [releases page](https://github.com/rwharpernc/wayward-nomads-toolbox/releases/latest)) and restart EDMC. The line under the mode
   buttons should read `Plugin: v1.15.0`. Work through sections 0 and 1 below first.
2. To get the checklist and the test suite, fetch the repository and use `master`:
   `git fetch --all --tags`, then `git switch master`, then `git pull --rebase`. Once per machine:
   `git config core.hooksPath .githooks`.
3. Run the unit tests: `python3 -m unittest discover -s tests`. The window and panel smoke tests need a display; without one they are
   skipped, so run them from a desktop session.
4. To try the `master` build instead of the release, run `npm run deploy` in the repository. It finds EDMC's plugins folder (native or Flatpak) and copies the
   build there; restart EDMC afterwards. `master` reports the same version as the release until the next one is cut.

**What changed in 1.10.2, in the order to check it:**
- **Wrapping:** in Colonization, a long site, project, system or commodity name (such as `Orbital Construction Site: ...`) is shown in full and
  wraps at the window's width instead of ending in `...`. In Expedition, Materials, Notes and the Trade watch list, lines use the whole width of
  the window when it is wide, and a narrow window is still never widened.
- **History heading:** the Colonization History heading names the commander (`History - NAME`).
- **Busiest site:** shows the site's name and system rather than `Construction site <number>` once you have docked at it.

**What changed in 1.10.1 (still worth checking):**
- **Layout:** with Expedition (Exploration mode) and Materials (Field Ops mode) open, the main EDMC window must not grow wider. In Expedition,
  **Copy on arrival** sits on its own line under **COPY** and **EXPEDITION**; in Materials, **BLUEPRINTS** sits under **MATERIALS**, not beside it.

**What changed in 1.9.1, in the order to check it** (each item is in the section named):
- **Section 5, Overlay:** the Colonization card still showing when the game's Market event arrives late (the overlay now also watches `Market.json`).
- **Section 7f, Overlay Placement:** an exact position that is off the overlay's canvas (such as a leftover `x = 1280`) falls back to the default spot.
- **Section 7g, Overlay Appearance:** the Text size choice (Default, Larger), and boxes holding their text at each size.
- **Layout:** with a large font the Trade page and the Trade History window should not widen the EDMC window.

**New in 1.10.0** (the checklists are in section 5 below):
- **Materials, Engineering and the Material trader** (Field Ops mode).
- **The Expedition planner** (Exploration mode).

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
- [ ] Material trader (Materials window, **Find a trader**; added 2026-10-14): the window opens with your system filled in and the type that has the
      most at the limit; **Find** lists traders nearest first (check one against the galaxy map); the Type, Within and Pad drop-downs change the
      search; **Here** refills the system; a typed system works; double-click copies the system name; with no network the status says Spansh
      could not be reached and **Find** works again afterwards.
- [ ] Engineering (Field Ops, **BLUEPRINTS** on the Materials section; added 2026-10-13): the window opens with **Blueprints** and **Wishlist** tabs;
      Search (it waits a moment after typing) and the Module drop-down narrow the list; picking a row shows its ingredients, what you hold and
      where each is found; **Add to wishlist** and a double-click add; the Wishlist tab shows each entry's crafts, whether it can be made and
      the shopping list; **Set crafts**, **Remove** and **Clear list** ask twice; the Materials section shows the `Wishlist:` line and stays narrow;
      the window keeps its size and place.
      The **Engineers** tab lists engineers with where you stand (after a login), unlocked ones first; **Show their blueprints** switches to the
      Blueprints tab searching for them; **Put their unlock on the wishlist** adds it; the wishlist's **Who can do it** column names an unlocked
      engineer or "No engineer unlocked yet".
- [ ] System-name suggestions (added 2026-10-14; Settings → Window): in the Expedition window's System box type two letters of a system you have been in: a list appears under the box; **Down**, **Enter** take one; **Escape** closes it; **Enter** with nothing highlighted adds the stop. The list must appear in front of the window on your desktop and Wayland compositor and go away when the box loses focus. Tick *Suggest system names from Spansh while typing*, type `outot`: after a pause systems from Spansh appear.
- [ ] Expedition (Exploration mode, **Expedition** section; added 2026-10-14): **EXPEDITION** opens the window; **New** makes an expedition; **Add stop**
      (and **Here**) add stops; **From plotted route** (after plotting a route in the game) and **Import CSV** add many; **Road to Riches** and **Exomastery** (Spansh; press **Plot**, wait, check the new expedition's stops, notes and order against Spansh's own page); **Start**, then jump to a
      stop: the section ticks it, counts the jump and shows the next stop with its distance; **COPY** and **Copy on arrival** put the next stop's
      name on the clipboard (check it pastes into the galaxy map's search box); **Locate and reorder (EDSM)** orders the unvisited stops;
      **Export CSV** saves a file and **Import CSV** reads it back; **Reset** and **Delete** ask twice; the section stays narrow with a long name; the
      window keeps its size and place.
- [ ] Notes (Exploration mode, **Notes** section): the quick-add box saves a line against the current system; **NOTES** opens the window;
      the editor's text box takes typing and paste; **Here** fills the system and body; **Delete** asks twice; the window keeps its size
      and place after closing and reopening.
- [ ] Trade Watch list (Trade mode, **Watch list** row; added 2026-10-13): **WATCH** opens the window; add a commodity by typing (the suggestion
      list appears and a click or Enter picks it) and **Add**; open a station's commodity market in the game and the commodity gets a price, with
      the station under it when picked; **Remove** asks twice; with Trade lookups on, **REFRESH** fills in Spansh prices and says so, and with
      them off it says to turn them on; the row stays narrow with a long system name; restarting EDMC keeps the list and the seen prices.
- [ ] Route overlay (Settings → Overlays → Route): **Test Card** draws a card at the top left with fuel, range and a list of systems, neutron stars and white dwarfs in their own colors, every line starting at the same left edge; plot a real route in the game and the list follows each jump and clears at the end.
- [ ] Exobiology cards (Settings → Overlays → Exobiology): **Test Cards** draws all four as plain panels (no colored bar or outline) with the three circles beside the species name inside the card; sampling on a mapped body fills the circles, moves the progress bar a third per sample, updates the distance and the radar, and shows the popup; scanning a plant with the Composition Scanner and walking off shows a ring, a pointer line and `Tracking <species>` with the little pointers turning as you turn; leaving the planet clears the cards; first footfall is marked on a body nobody has landed on.
- [ ] Layout editor (Settings → Overlays → Overlay Placement): the picture of the screen shows with a box per display, dragging a box fills in the table, a box dropped near an edge snaps flush (offset 0), **Picture size** changes the picture and is remembered; a card placed at the bottom or right with offset 0 sits on the screen edge.
- [ ] A relog, or a return to a system after visiting others, keeps the System targets and Body info cards' bodies: each commander's surveys are saved in `system_surveys.json`, and a system visited before is rebuilt from the journals; the card's summary line and Done list show where you left off.
- [ ] System targets and Body info cards (Settings → Overlays): **Test Card** on each draws a card with every line at the same left edge; after scanning bodies in a system the targets card lists those worth mapping and any with life, and they leave the list when mapped or analysed; targeting a body in the system map shows its Body info card; restarting EDMC mid-system brings the list back.
- [ ] Expedition on the Route card and survey tracking (Exploration → Expedition; Settings → Overlays → Route): start an expedition with two or three stops and turn the Route overlay on; the card shows the expedition's name and progress, the next stop with its distance and note, and the stop just reached, and arriving at a stop updates it at once. At a stop, honk and scan a few bodies (one nobody has discovered, one mapped): the Expedition row, the card (`Here:`) and the window's **Found here** column agree with the game, a body scanned twice counts once, and the counts are still there after restarting EDMC. Unticking *Show the active expedition on this card* removes it from the card.
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

- [ ] Settings -> WNTB -> General -> **Help** (added in 1.11.0, Windows-tested only): **Report an issue** opens the GitHub bug report in your
      browser (check `xdg-open` works from EDMC, native and Flatpak), and its Environment box reads like
      `Ubuntu 24.04, wayland` (distro, X11 or Wayland, `Flatpak` when it is one). **Copy diagnostics** shows *Copied*, pasting gives the
      version lines and recent WNTB log lines, and the commander name reads `<commander>`. Say which log path the Flatpak case used.

- [ ] Engineering window → **Engineers** tab (changed in 1.11.0, Windows-tested only): the table has a **Where** column; selecting an engineer shows
      their find, invite and unlock steps under the table, and the grade-profit line sits below that. Selecting Baltanos shows Deriso and "On-foot engineer";
      Terra Velasquez shows the "reported bugged" note. The **Show** box offers Both / Bubble / Colonia: Colonia lists 8 engineers (`8 of 38 engineers`), Bubble 30, and the choice survives closing and reopening the window. The table stays inside the window with the new column, with no horizontal scroll.

- [ ] **BGS with EDMC closed over a tick** (added in 1.11.0, Windows-tested only): note the BGS archive, close EDMC, do a few BGS actions (missions, bounties)
      in the game, wait for a tick to pass, start EDMC: the archived tick that just closed now includes those actions, and EDMC's log has
      `BGS: rebuilt the closed period ... from the journals`.
- [ ] **Finished colonization build name**: a completed site in the Colonization sites window reads `Wayward Station`, not `Orbital Construction Site: Wayward Station`.

- [ ] **Ship planner** (Engineering window, added after 1.10.2, Windows-tested only): export a build from EDSY or Coriolis as SLEF and **Paste from clipboard**
      (check the clipboard paste works on your desktop, X11 and Wayland). The table lists each engineered module; the summary line shows blueprints and crafts;
      **Add plan to wishlist** puts them on the Wishlist tab (a pre-engineered module and an unknown item show their reason). Set **Rolls per grade** to 2 and add again:
      the crafts double. Tick **Subtract what my current ship already has** with a build for the ship you fly: what the ship holds is left out. Nothing goes online.

- [ ] **Megaship scans** (Powerplay, added in 1.12.0, Windows-tested only): in a Powerplay system, drop out of supercruise at a megaship and scan its datalink. The
      Powerplay panel gains `Cycle N megaships: 1 (N merits)` and **SES → Megaships** lists it with its name and system. Scanning it again changes nothing. A scan at a
      station or a settlement adds nothing. After restarting EDMC the list is still there. Needs the Journal directory set on Linux.

- [ ] **Upgrade planner** (Engineering window, added in 1.12.0, Windows-tested only): pick the Karma AR-50 from class 1 to 5: four steps, 12,500,000 credits, and **Add to wishlist**
      puts four entries on the Wishlist tab. Press **Read my gear**: your suits and weapons are listed with their class (needs the Journal directory set on Linux); picking one fills in its item, class and fitted modifications. Pick the TK Zenith: the credits read "not recorded". Pick a modification not offered for the item (they are filtered), and four at most.

- [ ] **Alert widths** (added in 1.13.0, Windows-tested only; needs EDMCModernOverlay): **Test Notable** and a Discovery alert with a long capitalized name fit inside their cards at Default and Larger text; on the Missions overlay card a long station name drops to a line under its title.
- [ ] **Mission progress colors** (added in 1.13.0, Windows-tested only): the Missions window's Progress column shows a bar and `N/total held` for a source-and-return mission, and rows and overlay lines change color as the hold fills.
- [ ] **Missions window and pinned missions** (added in 1.12.0, Windows-tested only): the **Missions window** button at the bottom of the Missions panel opens the window; the Active and By place tabs fill and the times count down;
      select a row and **Pin / Unpin** puts a ★ on it and (with the Missions overlay on) a PINNED section on the card; the text beside the arrows is bold and readable.
- [ ] **Best picks and Source commodities** (added in 1.12.0, Windows-tested only; needs Trade lookups on): Trade → Market, type a commodity, **Best picks** shows four labelled stations;
      Missions → **Find sources** (bottom of the panel) fills the window as each commodity finishes, **Copy system** puts the system on the clipboard, and **Cancel** stops it.
- [ ] **Missions overlay card** (added in 1.12.0, Windows-tested only; needs EDMCModernOverlay): Settings → Overlays → Missions → **Test Card** draws a sample in the bottom-right corner; with a few
      real missions and the card enabled it lists those for the system you are in under HERE and those for the system you target under NEXT, and times count down. It sits where Overlay Placement says
      and does not widen as lines change.

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
      mode button.
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
      Within a minute EDMC's log reads "Trade read N new or changed journal file(s)", and the trades,
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

- [ ] The BGS panel's gray line shows "Last tick: ..." within a few seconds (network call works).
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

- [ ] **Settings → Colonization → Raven Colonial** has a master switch and two checkboxes (all off, the two grayed out until the master is ticked) and a masked key field. With the master off, Report Complete to Raven refuses.
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
- [x] **Only what [station] sells**: grayed out until you open a station's commodity market; then it names the station and
      narrows the list to what that market has for sale (in stock, with a buy price); it unticks itself when you undock.
      (`Market.json` lives in the journal folder: check EDMC's journal path on Linux/Proton.) Checked on Linux 2026-10-12 (reported by the developer).

## 7f. Overlay Placement and the Overlays settings tab (added 2026-10-11, Windows-tested only: check on Linux)

Written on Windows against a 3840 x 2160 screen in EDMCModernOverlay's fill mode. The logic is platform-neutral, but
reading the screen size from inside the Proton prefix (and the overlay's log), the display scaling under XWayland, and how the
overlay maps its canvas and sizes there, have not been seen on Linux.

- [ ] **Settings -> Overlays** has the tabs Overlay Connection, Overlay Placement, Overlay Appearance, Colonization, Discovery,
      Inventory, Interdiction Warning, Flight Alerts, Landing, Surface Compass, Mining, Notable Bodies and Screenshots; General no
      longer has an overlay tab.
- [ ] **Default spots (1.9.0):** with every box ticked, **Show placement preview** on a screen of 1920 x 1080 or more draws the boxes
      without any two overlapping (Interdiction at the top, Discovery below it, Notable find at the top right above Inventory, Flight
      alerts on the right below Inventory). On a smaller screen some may overlap; that is expected, and moving them on the tab fixes it.
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

- [ ] **Settings -> Overlays -> Appearance** exists, with a Color scheme menu and a Text size menu (Default, Larger; Larger is the starting value). Pick each size and press **Show sample**: no text may run past its box.
- [ ] **Show sample** draws the Colonization card in the game in the picked scheme.
- [ ] At **Larger** (the starting size), each display (Colonization, Discovery, Notable, Landing, Inventory, Mining,
      Screenshots) keeps its text inside its border without wrapping. Note any that do not, with the font and Proton/Wine setup.
- [ ] Changing the scheme recolors every display; Interdiction stays red.
- [ ] After OK, the choices are still set when Settings is reopened. **Reset appearance** restores Elite orange and Larger.

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
