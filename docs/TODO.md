# To do

Open work and open questions. Finished work is in [CHANGELOG.md](../CHANGELOG.md); what is being tested right now, and the working rules, are in
[STATUS.md](STATUS.md). Step-by-step Linux checks are in [LINUX_TESTING.md](LINUX_TESTING.md). Bug reports and ideas are welcome on the
[Issues page](https://github.com/rwharpernc/wayward-nomads-toolbox/issues).

## Needs checking in the game

These are built and covered by unit tests, but have not all been seen working in the game. "Then Linux" means the Linux checklist covers it too.

- [ ] **Flight Alerts.** The Test Card, the fuel warnings with a plotted neutron star and a high fuel percentage, the carrier jump countdown with a
  real scheduled jump (never seen working: it reads `CarrierJumpRequest`, and the field names and flag bits come from the journal documentation, not
  from a real event), the sound, and the card's spot (right, below the Inventory display). Then Linux (the sound needs `canberra-gtk-play` or `paplay`).
- [ ] **Surface Compass.** It replaces Mining's waypoint arrow. On a landable surface: **Test Compass**, the arrow following the nearest hotspot as you
  turn, **MARK** (the body name comes from `Status.json`'s `BodyName`, taken from the documentation and not yet seen), **TARGET**, the Marks window,
  and that the old Mining tick and arrow are gone with your old placement kept. Then Linux.
- [ ] **Trade Watch list.** Add a few commodities, open real markets (the `Market` event and `Market.json` for a watched item), press **REFRESH**
  against real Spansh with Trade lookups on (two requests per commodity), the window's age and place columns, Remove twice, and that the EDMC window
  does not get wider. Then Linux.
- [ ] **Materials.** The login `Materials` list against the in-game inventory, MaterialCollected and MaterialDiscarded, a trade, a synthesis and an
  engineer craft each moving the right counts, the count at a grade limit, and that the row does not widen the EDMC window. EDMC's state keys `Raw`,
  `Manufactured` and `Encoded` were checked against EDMC's `monitor.py` on 2026-10-13. Then Linux.
- [ ] **Material trader finder.** Find a trader from your system, compare a result with the galaxy map (the station really has that trader, and its
  pad), the Within and Pad filters, a typed system, double-click copy, and that no other network call happens. Spansh's `material_trader` filter was
  checked live for all three values but not through the window. Then Linux.
- [ ] **Engineering blueprints, wishlist and Engineers tab.** Pick a few blueprints (a ship module and an Odyssey suit or weapon one) and check each
  ingredient's Have against the in-game inventory; that an Odyssey ingredient counts the **ship locker** (the game's own rule is unconfirmed: does an
  upgrade also use the backpack?); that an unlock needing trade goods says "not counting"; who can do each wishlist entry; that "ready" follows list
  order; and the Wishlist line on the Materials section. On the Engineers tab, compare status, rank and rank-ups (a rank-only event) with the in-game
  Engineers panel, and the **Where** column, the details and the Bubble / Colonia filter with what the game shows. The Colonia engineers' upgrades
  and places come from EDDiscovery's table and a community list, not from the game. Also check a few recipes against the game: the table is from
  March 2024 plus later corrections. Then Linux.
- [ ] **Ship planner.** Export a build from EDSY and from Coriolis as SLEF, paste it, and compare the modules, levels and experimental effects with
  the build. Check **Add plan to wishlist** (and the refusal when it would pass 100 blueprints or 99 crafts), the **Rolls per grade** setting, a
  pre-engineered module, and a `Loadout` line copied from a journal. Then **Subtract what my current ship already has** with a build for the ship you
  are flying (it reads your newest journal). Then Linux (the clipboard paste).
- [ ] **System-name suggestions.** Try every box that takes a system name (Expedition System, the planner's Start and End, the trader finder,
  Colonization Around, Notes, Waypoint Route, Boxel Survey seed): the list under the box, Down / Enter / Escape, Enter with nothing highlighted still
  acting, and the list matching the EDMC theme in the main panel boxes. Then Settings → Window → Suggest system names from Spansh and type `outot`.
  Then Linux.
- [ ] **Expedition planner.** Replayed against 132 recorded sessions (2,354 jumps) on 2026-10-13: every stop was ticked in order and the jump and
  light-year totals were exact; `JumpDist` and `StarPos` are in the real events. What is left is the screen itself. Also check that stop names are
  respelled and located through EDSM when added (type `sol`, expect `Sol`; try a mixed-case boxel name; an invented name should be kept with a note),
  and the **Road to Riches** and **Exomastery** buttons (press Plot and compare the new expedition's stops and notes with spansh.co.uk/riches and
  /exobiology; both endpoints were checked with live calls). Make an expedition and add stops by hand, from a plotted route and from a CSV; Start; jump
  to a stop and see it ticked, the jump counted and the next stop's distance; COPY and Copy on arrival pasting into the galaxy map; **Locate and reorder
  (EDSM)** against real EDSM; and that the row does not widen the EDMC window. Then Linux.
- [ ] **Notes.** Quick add, the window, **Here**, Delete twice, the count when jumping into a system with notes, and that the EDMC window does not get
  wider. Then Linux.
- [ ] **Alert widths.** Trigger a Notable Bodies alert (or **Test Notable**) and a Discovery alert on a body or system with a long catalog name in capitals, and check the whole name sits inside the card at Smaller, Default and Larger text. On the Missions overlay card, check a mission whose station or system name is long: the place should drop to a second line under the title, in the same colour. Say if any text still runs past an edge.
- [ ] **Mission progress colours.** Take two source-and-return missions, buy some of the cargo, and check the Missions window shows `N/total held` with a bar, the row turns blue and then lime past half, and the overlay line follows; hand a mission in and check it goes green. Check a massacre stack's colour moves as kills land. Say if the colours or the held counting (everything of that commodity in the hold) are wrong for how you play.
- [ ] **Missions window and pinned missions.** With a real board: open the window from the **Missions window** button at the bottom of the panel, check the Active and By place tabs, the summary line and the detail strip against the game's mission board;
  pin two missions and check the PINNED section on the overlay card (and that it goes when you hand the mission in). Look at the text size beside the panel arrows. Then Linux.
- [ ] **Best picks and Source commodities.** With Trade lookups on: Market → type a commodity → **Best picks** (buy and sell), and Missions → **Find sources** with a few Collect or Mining
  missions active. Compare the four picks with what EDCoPilot says for the same commodity, ship and system; note any that differ (the 10% band is measured against the cheapest station in the galaxy).
  Then Linux. Not built: the nearest ring hotspot for Mining missions in the same window.
- [ ] **Missions overlay card.** Enable it (Settings → Overlays → Missions), press **Test Card**, then fly with a real board of missions: HERE and NEXT follow your system and the system you target,
  the times count down, a finished mission shows a tick, the card stays one width, and it sits in the corner you chose without covering the HUD. Note which rows you would drop or add (the label
  for each kind of mission, the row limit). Then Linux.
- [ ] **Upgrade planner.** Pick an item, a class range and modifications and add them to the wishlist; compare the materials with the in-game upgrade screen for an item
  other than the eight confirmed ones (Karma P-15, Manticore Intimidator and Oppressor, TK Aphelion, Eclipse and Zenith), and try **Read my gear** and compare it with your loadouts, and note the credits shown at the upgrade screen:
  each one confirmed is a line in `odyssey_upgrade_plan.CREDIT_UNIT` (or send the `UpgradeWeapon` journal line). Then Linux.
- [ ] **Megaship scans.** In a Powerplay system drop out of supercruise at a megaship and scan its datalink: the panel line and **SES → Megaships** row appear with
  the right name and system, the merits fill in a moment later, a second scan of the same megaship changes nothing, and a scan at a station adds nothing. Restart EDMC and
  check the list is kept. Then Linux.
- [ ] **Help tab** (Settings → General → Help). **Report an issue** opens the prefilled form (it needs the issue template on GitHub), and **Copy
  diagnostics** puts the versions and recent WNTB log lines on the clipboard with the commander name redacted. Then Linux, native and Flatpak.
- [ ] **BGS** after a tick passes with EDMC closed: the period that closed holds the play made meanwhile. And a finished Colonization build showing
  its name without the "Construction Site:" prefix.
- [ ] The Powerplay panel and the other mode panels (bold and small fonts, grouping rules) under the Default, Dark and Transparent EDMC themes.
- [ ] Colonization window, in game: **Find all** against real Spansh, **Only what [station] sells** with a real `Market.json`, and clicking a result
  row copies that system.
- [ ] **Raven Colonial writes not yet seen:** Report Complete on a finished build, and carrier cargo sharing (the second switch; it needs a transfer at
  your own carrier with that box ticked, then a look at Raven's carrier record). Depot progress and deliveries have been seen working, and the Test key
  button accepts a real key.
- [ ] **Raven Progress and Open Selected Build on Raven** on real in-progress builds (the Raven Colonial menu). They find a build by name, since Raven
  has no market id until a build is finished, so a renamed station needs a re-dock first for WNTB to take the new name.
- [ ] Colonization Sites window header menus on Linux (colors, opening and closing, links opening the browser): LINUX_TESTING.md 7e-4.
- [ ] Overlay right-edge placement after an EDMC restart (Overlay Placement → Show placement preview): the offset's units and ordering were read
  from the overlay's code and not yet seen. The two Mining displays share one group and are not offset.
- [ ] Overlay Placement and the Overlays tab on Linux (Proton prefix path, XWayland scaling): LINUX_TESTING.md 7f.
- [ ] Colonization mode in game and on Linux: LINUX_TESTING.md 7h.
- [ ] A real EDMC: the Inventory start-up sync from EDMC's rebuilt state, and whether the `Complete` ids in the login `Missions` event are a subset of
  `Active` (assumed).

## Colonization

Raven Colonial was first a read-only reference, then WNTB's own tracking was judged better, so reporting is **opt-in**: a finished build, depot
progress, deliveries and (separately) carrier cargo changes. Not done: creating or linking a project from WNTB (it does not store the system address
or build type Raven needs), ready flags, and Raven's `supply` call, which Raven documents as wrong for a tool that reads the journal.

- [ ] **Where to buy: see it working.** The "sells everything" search goes first and skips per-commodity searches it satisfies in full; a second
  request covers leftovers from the returned whole markets. Checked from a script against real Spansh (a 6-commodity list took 1 request; a
  14-commodity list took 1 + 12 searches + 1 leftover request, and the 2 commodities with no stock within 50 ly were reported as not covered). Still to
  see in the window itself, then on Linux.

## Ideas from other tools

Surveyed: SrvSurvey (GPL-3.0), EDDiscovery (Apache-2.0), Elite Dangerous Odyssey Materials Helper (MIT), EDEngineer (MIT), ODEliteTracker and OD-Explorer
(no licence given: its source is read for how things work and none is copied). Built so far: the fleet carrier jump countdown, low-fuel and next-star warnings, system and body
notes, the Surface Compass with marks, the Trade watch list, materials and engineering (including the blueprint wishlist, the engineers and the ship
planner), the material trader finder, and expedition planning. Later, in rough order:

- [ ] **Odyssey upgrade planner, next step:** a stat preview (needs each item's base stats and the effect of each level and modification, which are not open data).
- [ ] **Expedition planning, not done:** an overlay card and per-stop scan or discovery tracking.

## Very low priority

Nothing here is planned. It stays on the list so the idea is not lost.

- [ ] Raven Colonial: read-only polling of tracked projects (its remaining needs and others' progress beside ours), then opt-in writes. Completion,
  progress, deliveries and carrier cargo are done; the rest is deferred. Reads need no key. The public docs would have to list exactly what is sent and
  when.
- [ ] **Team projects:** several commanders on one project. The depot event gives only the project's totals, so "who delivered what" has to come from
  each member. Everything today is per commander and stays that way until a commander opts in to sharing.
- [ ] Co-op building and colony tracking through a separate project that is still in development. The README says Colonization is a work in progress.
- [ ] History ideas: tonnes per hour (the journal does not say how long you spent hauling, so it would be a guess from the gaps between deliveries)
  and credits earned from deliveries (the depot reports a `Payment` per commodity, but it is not verified that this is what is paid out).
- [ ] Round trip: a Powerplay bonus filter (it depends on what the price service can tell WNTB and on what "bonus" should mean).

## Not planned

The journal does not carry what these would need. See [STATUS.md](STATUS.md) for the decisions already made.

- Guardian ruin and structure surveying: it is SrvSurvey's own territory.
- Landing-pad diagrams: the journal gives no layout, orientation or positions.
