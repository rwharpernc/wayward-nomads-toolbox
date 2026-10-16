# To do

Open work and open questions. Completed work is recorded in [CHANGELOG.md](../CHANGELOG.md). Current test status and working rules are in
[STATUS.md](STATUS.md). Step-by-step Linux checks are in [LINUX_TESTING.md](LINUX_TESTING.md). Bug reports and suggestions are welcome on the
[Issues page](https://github.com/rwharpernc/wayward-nomads-toolbox/issues).

## In progress

Work that is under way and will take time. Items here are active, not waiting; they are listed once, here, and not again below.

- [ ] **Data verification.** Work through [data_verification/verification_checklist.csv](data_verification/README.md) (about 335 rows, for a spreadsheet): what is
  missing and what is carried from other authors' work but not yet checked in the game. Mark each row as it is verified, and change the method statement in
  [ATTRIBUTIONS.md](ATTRIBUTIONS.md) to the past tense only when none are left.
- [ ] **Odyssey upgrade planner, next step:** a stat preview. The stat tables are not available as open data, so they are being gathered and checked in the
  game ([ODYSSEY_STAT_COLLECTION.md](ODYSSEY_STAT_COLLECTION.md); the sources looked at, with their licenses, are in [ODYSSEY_STAT_DATA.md](ODYSSEY_STAT_DATA.md)).
  The preview itself waits for that data. A request to the Materials Helper's developer for its tables is a possible shortcut.

## Verification in the game

The items below are implemented and covered by unit tests, but have not all been verified in the game. "Then Linux" means the Linux checklist
covers the item as well.

- [ ] **Flight Alerts.** Verify the Test Card; fuel warnings with a plotted neutron star and with a high fuel percentage; the carrier jump countdown
  with a real scheduled jump (not yet verified: the feature reads `CarrierJumpRequest`, and its field names and flag bits come from the journal
  documentation rather than from a recorded event); the sound; and the card position (right side, below the Inventory display). Then Linux (the sound
  requires `canberra-gtk-play` or `paplay`).
- [ ] **Surface Compass.** The compass replaces the Mining waypoint arrow. On a landable surface, verify **Test Compass**, that the arrow follows the
  nearest hotspot as the commander turns, **MARK** (the body name is taken from `Status.json`'s `BodyName`, which was seen in a real file on 2026-10-16, game 4.4.1.1), **TARGET**, the Marks window, and that the previous Mining tick and arrow are removed while the saved placement is kept. Then Linux.
- [ ] **Trade Watch list.** Add several commodities; open real markets (the `Market` event and `Market.json` for a watched item); press **REFRESH**
  against Spansh with Trade lookups enabled (two requests per commodity); verify the age and place columns, removal, and that the EDMC window does not
  become wider. Then Linux.
- [ ] **Materials.** Compare the login `Materials` list with the in-game inventory. Verify that MaterialCollected, MaterialDiscarded, a trade, a
  synthesis and an engineer craft each change the correct counts, the display at a grade limit, and that the row does not widen the EDMC window. EDMC's
  state keys `Raw`, `Manufactured` and `Encoded` were checked against EDMC's `monitor.py` on 2026-10-13. Then Linux.
- [ ] **Material trader finder.** Find a trader from the current system and compare a result with the galaxy map (the station has that trader type and
  the stated pad size). Verify the Within and Pad filters, a typed system, copy on double-click, and that no other network request is made. Spansh's
  `material_trader` filter was checked with live requests for all three values, but not through the window. Then Linux.
- [ ] **Engineering blueprints, wishlist and Engineers tab.** Select several blueprints (a ship module, and an Odyssey suit or weapon blueprint) and
  compare each ingredient's Have value with the in-game inventory. Confirm that an Odyssey ingredient counts the **ship locker** (the game's rule is
  unconfirmed: does an upgrade also draw on the backpack?); that an unlock requiring trade goods states that they are not counted; which engineer can
  complete each wishlist entry; that "ready" follows list order; and the Wishlist line on the Materials section. On the Engineers tab, compare status,
  rank and rank-ups (a rank-only event) with the in-game Engineers panel, and verify the **Where** column, the detail text and the Bubble / Colonia
  filter. The Colonia engineers' upgrades and locations come from EDDiscovery's table and a community list, not from the game. Also compare several
  recipes with the game: the table dates from March 2024 plus later corrections. Then Linux.
- [ ] **Ship planner.** Export a build from EDSY and from Coriolis as SLEF, paste it, and compare the modules, levels and experimental effects with the
  build. Verify **Add plan to wishlist** (including the refusal when it would exceed 100 blueprints or 99 crafts), the **Rolls per grade** setting, a
  pre-engineered module, and a `Loadout` line copied from a journal. Then verify **Subtract what my current ship already has** with a build for the
  ship currently flown (it reads the newest journal). Then Linux (clipboard paste).
- [ ] **System-name suggestions.** Test every box that accepts a system name (Expedition System, the planner's Start and End, the trader finder,
  Colonization Around, Notes, Waypoint Route, Boxel Survey seed): the list below the box; Down, Enter and Escape; Enter with nothing highlighted still
  acting; and the list matching the EDMC theme in the main panel boxes. Then enable Settings → Window → Suggest system names from Spansh and type
  `outot`. Then Linux.
- [ ] **Expedition planner.** The planner was replayed against 132 recorded sessions (2,354 jumps) on 2026-10-13: every stop was ticked in order and the
  jump and light-year totals were exact; `JumpDist` and `StarPos` are present in the real events. The user interface itself remains to be verified.
  Confirm that stop names are respelled and located through EDSM when added (type `sol`, expect `Sol`; try a mixed-case boxel name; an invented name
  should be kept with a note), and the **Road to Riches** and **Exomastery** buttons (press Plot and compare the new expedition's stops and notes with
  spansh.co.uk/riches and /exobiology; both endpoints were checked with live requests). Create an expedition and add stops manually, from a plotted
  route and from a CSV file; press Start; jump to a stop and confirm that it is ticked, the jump is counted and the next stop's distance is shown;
  verify COPY and Copy on arrival pasting into the galaxy map; **Locate and reorder (EDSM)** against EDSM; and that the row does not widen the EDMC
  window. Then Linux.
- [ ] **Notes.** Verify quick add, the window, **Here**, deletion with confirmation, the count shown when jumping into a system that has notes, and that
  the EDMC window does not become wider. Then Linux.
- [ ] **Expedition on the Route card, and survey tracking.** Start an Expedition with two or three stops and enable the Route overlay. Confirm that the card shows the expedition's name and progress, the next stop with its distance and note, and the stop just reached; that arriving in a stop updates it at once; and that unticking *Show the active expedition* removes it. At a stop, honk and scan some bodies, including one nobody has discovered and one you map, and confirm that the Expedition row, the card (`Here:`) and the window's **Found here** column agree with the game (the body count after the honk, scans, first discoveries, maps), that a body scanned twice counts once, and that the counts survive restarting EDMC. Confirmed in a real journal on 2026-10-16 (game 4.4.1.1): `Scan` carries `StarSystem` and `WasDiscovered`, `SAAScanComplete` carries `BodyName` and no system (the planner uses the system the commander is in), `FSSDiscoveryScan` carries `BodyCount` and `SystemName`, and `FSSAllBodiesFound` carries `Count`. Then Linux.
- [ ] **System targets and Body info cards.** Enable both (Settings → Overlays), press **Test Card** on each, then explore a system. After a honk and some scans, confirm that System targets lists the scanned planets and moons at or above the threshold with sensible values (compare a few with the credits the game pays when you scan them; the estimate is the scan value, not the mapping value), that a body drops off when you map it, that bodies with life appear with the right count and drop off when you analyse the last organism, that it clears when you jump, and that restarting EDMC mid-system brings it back. Target a body in the system map and fly close to one: Body info should show the body you targeted, then the one you are near. Check the new default spots (lower middle of the right half) against your HUD and tell me where you would rather have them. Not yet confirmed: the format of `Status.json`'s `Destination` (`System`, `Body`, `Name`), which is taken from the journal documentation. Then Linux.
- [ ] **Alert widths.** Trigger a Notable Bodies alert (or **Test Notable**) and a Discovery alert for a body or system with a long capitalized catalog
  name, and confirm that the whole name fits inside the card at Default and Larger text sizes. On the Missions overlay card, check a mission
  with a long station or system name: the place should move to a second line under the title, in the same color. Report any text that still extends
  past an edge.
- [ ] **Route overlay.** Enable it (Settings → Overlays → Route), press **Test Card**, then plot a real route in the galaxy map, ideally a neutron
  highway. Confirm that the listed systems and their stars match the plotted route (`NavRoute.json`), that neutron stars and white dwarfs are picked
  out, that the card moves on after each jump, that "jumps left" and the light years agree with the galaxy map, that the fuel, range and last-jump
  figures match the ship, and that the card clears at the end of the route, when the route is cleared, and when you jump to a system that is not on
  it. Restart EDMC mid-route and confirm that the card comes back. Check that the new default spots (Route top left; Surface Compass, Mining stats,
  Flight Alerts and Missions moved in the right-hand column) do not cover the HUD. Not yet confirmed: the field names in `NavRoute.json` (`StarSystem`,
  `StarClass`, `StarPos`) come from the journal documentation and from how the Expedition planner already reads the file. Then Linux.
- [ ] **Overlay padding and alignment.** The overlay cards share one padding and left-justify their text. On each of Colonization, Discovery (system and
  body), Notable Bodies, Interdiction, Landing, Missions, Flight Alerts, Mining, Surface Compass and the Screenshot message, confirm that the text sits
  the same distance from the border on all four sides, that every line starts at the same left edge (no centered title or name), that the right edge
  has no extra blank strip, and that no text runs past the border at Default and Larger text sizes. Also confirm the Text size menu offers only Default
  and Larger. Then Linux.
- [ ] **Mission progress colors.** Take two source-and-return missions and buy part of the cargo. Confirm that the Missions window shows `N/total held`
  with a bar, that the row turns blue and then lime past halfway, and that the overlay line follows; hand a mission in and confirm that it turns green.
  Confirm that a massacre stack's color changes as kills are recorded. Report whether the colors, or the held count (all of that commodity in the hold),
  do not match expected behavior.
- [ ] **Missions window and pinned missions.** With a real mission board, open the window from the **Missions window** button at the bottom of the
  panel; check the Active and By place tabs, the summary line and the detail strip against the game's mission board; pin two missions and confirm the
  PINNED section on the overlay card (and that a pinned mission is removed when it is handed in). Check the text size beside the panel arrows. Then Linux.
- [ ] **Best picks and Source commodities.** With Trade lookups enabled: Market → enter a commodity → **Best picks** (buy and sell), and Missions →
  **Find sources** with several Collect or Mining missions active. Compare the four picks with EDCoPilot's results for the same commodity, ship and
  system, and record any differences (the 10% band is measured against the cheapest station in the galaxy). Then Linux. Not implemented: the nearest
  ring hotspot for Mining missions in the same window.
- [ ] **Missions overlay card.** Enable the card (Settings → Overlays → Missions), press **Test Card**, and then fly with a real mission board. Verify
  that HERE and NEXT follow the current system and the targeted system, that times count down, that a finished mission shows a tick, that the card keeps
  one width, and that it sits in the chosen corner without covering the HUD. Record which rows should be added or removed (the label for each kind of
  mission, and the row limit). Then Linux.
- [ ] **Upgrade planner.** Select an item, a class range and modifications and add them to the wishlist. Compare the materials with the in-game upgrade
  screen for an item other than the eight confirmed ones (Karma P-15, Manticore Intimidator and Oppressor, TK Aphelion, Eclipse and Zenith). Test
  **Read my gear** and compare the result with the commander's loadouts. Record the credits shown at the upgrade screen: each confirmed value is a line
  in `odyssey_upgrade_plan.CREDIT_UNIT` (or submit the `UpgradeWeapon` journal line). Then Linux.
- [ ] **Megaship scans.** In a Powerplay system, drop out of supercruise at a megaship and scan its datalink. Confirm that the panel line and the
  **SES → Megaships** row appear with the correct name and system, that the merits are filled in shortly afterward, that a second scan of the same
  megaship changes nothing, and that a scan at a station adds nothing. Restart EDMC and confirm that the list is retained. Then Linux.
- [ ] **Help tab** (Settings → General → Help). Verify that **Report an issue** opens the prefilled form (this requires the issue template on GitHub),
  and that **Copy diagnostics** places the versions and recent WNTB log lines on the clipboard with the commander name redacted. Then Linux, native and
  Flatpak.
- [ ] **BGS** after a tick passes while EDMC is closed: the period that closed should contain the play made in the meantime. Also verify that a finished
  Colonization build is displayed without the "Construction Site:" prefix.
- [ ] **Credits Ledger and Colonization History windows** (added in 1.14.0). Verify that clicking the Credits line opens the ledger; that the Income, By
  day and Lifetime tabs fill for each commander; that **Rebuild from journals** reports its progress and result; and that the HISTORY button on the
  Colonization panel opens its window. Then Linux.
- [ ] The Powerplay panel and the other mode panels (bold and small fonts, grouping rules) under the Default, Dark and Transparent EDMC themes.
- [ ] Colonization window: **Find all** against Spansh, **Only what [station] sells** with a real `Market.json`, and copying a system by clicking a
  result row.
- [ ] **Raven Colonial writes not yet observed:** Report Complete on a finished build, and carrier cargo sharing (the second switch; this requires a
  transfer at the commander's own carrier with that option enabled, followed by a check of Raven's carrier record). Depot progress and deliveries have
  been verified, and the Test key button accepts a valid key.
- [ ] **Raven Progress and Open Selected Build on Raven** on real in-progress builds (the Raven Colonial menu). These find a build by name, because
  Raven has no market id until a build is finished; a renamed station therefore requires a new dock before WNTB uses the new name.
- [ ] Colonization Sites window header menus on Linux (colors, opening and closing, links opening the browser): LINUX_TESTING.md 7e-4.
- [ ] Overlay right-edge placement after an EDMC restart (Overlay Placement → Show placement preview): the offset's units and ordering were derived
  from the overlay's code and have not yet been observed. The two Mining displays share one group and are not offset.
- [ ] Overlay Placement and the Overlays tab on Linux (Proton prefix path, XWayland scaling): LINUX_TESTING.md 7f.
- [ ] Colonization mode in the game and on Linux: LINUX_TESTING.md 7h.
- [ ] In a running EDMC: the Inventory start-up synchronization from EDMC's rebuilt state, and whether the `Complete` ids in the login `Missions`
  event are a subset of `Active` (currently assumed).

## Colonization

Raven Colonial integration began as a read-only reference. WNTB's own tracking was later judged more reliable, so reporting is **opt-in**: a finished
build, depot progress, deliveries and (separately) carrier cargo changes. Not implemented: creating or linking a project from WNTB (WNTB does not
store the system address or build type that Raven requires), ready flags, and Raven's `supply` call, which Raven's documentation describes as unsuitable
for a tool that reads the journal.

- [ ] **Where to buy: verify in the window.** The "sells everything" search runs first and skips per-commodity searches that it satisfies in full; a
  second request covers leftovers from the returned whole markets. Checked with a script against Spansh: a 6-commodity list required 1 request; a
  14-commodity list required 1 + 12 searches + 1 leftover request, and the 2 commodities with no stock within 50 ly were reported as not covered.
  Verification in the window itself remains, followed by Linux.

## Ideas from other tools

Projects reviewed: SrvSurvey (GPL-3.0), EDDiscovery (Apache-2.0), Elite Dangerous Odyssey Materials Helper (MIT), EDEngineer (MIT), ODEliteTracker and
OD-Explorer (no license stated; their source was consulted only to understand how they read the journal, and none of it is copied). WNTB's code is
written independently, and data used from the licensed projects is credited in [ATTRIBUTIONS.md](ATTRIBUTIONS.md). Implemented so far: the fleet
carrier jump countdown, low-fuel and next-star warnings, system and body notes, the Surface Compass with marks, the Trade watch list, materials and
engineering (including the blueprint wishlist, the engineers and the ship planner), the material trader finder, and expedition planning. What remains of it is under "In progress" above.

## Low priority

No work is planned on these items. They are retained so that the ideas are not lost.

- [ ] Raven Colonial: read-only polling of tracked projects (remaining needs and other commanders' progress alongside WNTB's own), followed by opt-in
  writes. Completion, progress, deliveries and carrier cargo are implemented; the remainder is deferred. Reads need no key. The public documentation
  would need to list exactly what is sent and when.
- [ ] **Team projects:** several commanders working on one project. The depot event reports only the project's totals, so a per-commander breakdown
  would have to come from each member. All data is currently per commander and will remain so unless a commander opts in to sharing.
- [ ] Co-operative building and colony tracking through a separate project that is still in development. The README states that Colonization is a work
  in progress.
- [ ] History ideas: tonnes per hour (the journal does not record time spent hauling, so this would be estimated from the gaps between deliveries) and
  credits earned from deliveries (the depot reports a `Payment` per commodity, but it has not been verified that this is the amount paid out).
- [ ] Round trip: a Powerplay bonus filter (this depends on what the price service can report and on how "bonus" should be defined).

## Not planned

The journal does not contain the data these features would require. Earlier decisions are recorded in [STATUS.md](STATUS.md).

- Guardian ruin and structure surveying: this is the focus of SrvSurvey.
- Landing-pad diagrams: the journal provides no layout, orientation or positions.
