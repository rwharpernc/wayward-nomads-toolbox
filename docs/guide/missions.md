# Missions

One view of every mission on your board, sorted by type, plus Community Goals and what they paid you.

> **Where this comes from:** everything here comes from the journal alone, and the journal is thin in places: wing and on-foot kills are often missing until a mission completes, active missions are only listed at login, and a Community Goal never announces its end. Where WNTB has to work something out, it marks it (a `~`). See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

## Using it

The panel shows one category at a time, with a line like `◀  Combat (3)  ▶`. Click the **◀** or **▶** arrow to
page between categories; the number is how many missions are in that category. The pages, in order, are:

**Massacre (Space) · Settlement Raids (Ground) · Combat · Trade & Mining · Passenger · Covert / On-Foot Ops · Other · Community Goals**

- **Massacre** and **Settlement Raids** missions show grouped **kill-progress bars**, so you can see at a glance how
  many kills are still needed across all your missions for the same faction.
- Everything else shows **one card per mission**. Click a card to open the Missions window on that mission.
- Two buttons at the very bottom of the panel, on every page: **Missions window** (every active mission across every category) and **Find sources** (where to buy the cargo your missions need).

## The Missions window

Opens from the **Missions window** button at the bottom of the panel (or by clicking a mission's card). It stays live while you play: times left count down, progress moves, and missions
come and go as you accept and hand them in.

- **Active** tab: one row per mission, ready ones (✓, green) first, then the soonest to expire. A row's color tells you where it stands: **green** ready to hand in, **red** under an hour left, **amber** under six hours, otherwise **lime** for a mission half or more done and **blue** for one that is started but under half. The progress column also draws a small bar, so it reads by shape as well as color. Columns: mission,
  kind, faction, where to go now (the hand-in place once a mission is done), progress (see below), reward, and
  time left. Above the table, the summary: how many missions, how many are ready or under an hour from expiring, how many are pinned, and the rewards held.
- **By place** tab: the same missions grouped by the system to go to, your own system first, then the next jump you have targeted, then the places with
  something ready. A route plan at a glance.
- **Detail strip** below the tabs: click a mission for the faction, status, where to go, cargo and commodity (with the tonnes still needed), exact reward, wing,
  when it was accepted and when it expires.
- **Pin / Unpin** pins the selected mission; **Pin all here** pins every mission for the system you are in; **Unpin all** clears them. **Copy system** puts the
  selected mission's system on the clipboard for the galaxy map. **Sources** opens [Source commodities](#source-commodities).

### Progress

Where the number comes from depends on the mission, and the window says which:

| Shown as | Meaning |
|---|---|
| `20/60` | The game's own count of cargo handed in (from the journal's cargo depot events). |
| `36/36 loaded` | Cargo picked up for a haulage mission but not yet handed in. |
| `~18/40 kills` | Massacre and settlement-raid kills. `~` means an estimate: wing and on-foot kills are often missing from the journal until the mission completes. |
| `36/60 held` | A **source and return** mission, while you are still buying the cargo. The game writes nothing about these until you hand cargo in, so WNTB compares what is in your hold with what the mission asks for. Several missions for one commodity share the hold, the soonest to expire first, so a tonne is never counted twice. |

The colors are the same on the [overlay card](#missions-on-the-overlay). "Held" counts everything of that commodity in your hold, whether or not it was bought for the mission, and it follows the hold as you buy and sell. Cargo in a fleet carrier or another ship is not counted.

### Pinned missions

A pinned mission (★) is shown on the [Missions overlay card](#missions-on-the-overlay) in its own **PINNED** section above everything else, on its own line (never
stacked with others), with its place and time left. Pinned missions are listed first, then HERE, NEXT and the rest, within the same row limit. A pin is kept
for each commander (`mission_pins.json`, mission numbers only) and goes when its mission is handed in, fails, is abandoned or expires.

**Example.** You've taken five massacre missions against the same faction from different stations. Page to
**Massacre (Space)** and the bars show your total progress, rather than five separate counters to remember.

## What the game does and doesn't tell us, and how to work around it

WNTB, like every third-party tool, only knows what Elite Dangerous writes to its journal files. It needs no outside service for missions, so the journal is the whole story, and it works around the gaps below. Where it can't be sure, WNTB says so rather than guess quietly. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

| What you might expect | What the game gives | What to do |
|---|---|---|
| Every kill to be counted | **Wing and on-foot kills** are often missing from the journal until the mission completes, so those counts run low. WNTB marks them with a `~`. Combat-zone kills are recorded as combat bonds, not bounties; WNTB counts them too (checked against real journals), but they carry no ship type, so an on-foot combat-zone kill can be counted as a ship kill. | Read a `~` as "at least this many". The game's own mission screen is the final word. |
| Active missions to appear after restarting EDMC mid-game | The game lists active missions only in its login event, so WNTB works the list out from the last two weeks of journals (the latest login list plus what was accepted, completed, abandoned or failed since). A mission that **expired without a journal entry** can show until your next login. | Log in again to get the game's own list. |
| Cargo mission progress to be exact | The game reports it (`CargoDepot`: collected, delivered and total) when you collect or hand in cargo, and when a wing-mate does. Progress made before WNTB's two-week window, or with no event since, isn't known. | The card shows it once the game has reported any; otherwise check the game's mission screen. |
| Where to find a mission's cargo for sale, offline | It asks Spansh, so it needs Trade's online lookups switched on and a button press. | Turn the switch on in Settings → Trade. |
| Progress on a source-and-return mission before you hand cargo in | The game writes nothing about it until then. | WNTB shows what is in your hold against what the mission asks for (`36/60 held`). Cargo in a carrier does not count. |
| The next jump's missions on the overlay when you have a route | The game names the system you have targeted (`FSDTarget`), not the whole route, so only the next hop is NEXT. | Plot the route in the galaxy map and target the hops as you go. |
| Missions accepted a while ago to appear | WNTB reads only the **last two weeks** of journals at start-up. A mission still active but accepted earlier is not found and not shown. | Keep EDMC running while you hold long missions, and check the game's own mission board for older ones. |
| Kills made while EDMC was closed | Counted only if they are in the last two weeks of journal files. | Run EDMC whenever you play. |
| Every mission to land in the right category | Names WNTB does not recognize go to **Other**. | Click the card for details. If a type is always in Other, open an issue so it can be added. |
| A Community Goal's payout to be remembered for long | The game writes the payout (`CommunityGoalReward`) once. WNTB lists the latest three under **Paid out** on the Community Goals page, found in the last two weeks of journals at start-up. | Note a big payout elsewhere if you want to keep it. |
| A Community Goal to disappear when it ends | The game gives no "gone" signal, so the panel relies on each goal's expiry date. | Ignore a goal past its expiry; it clears itself. |

## Missions on the overlay

A small card on your in-game overlay, for flying. It is **off until you tick it** (Settings → Overlays → Missions) and needs an overlay like every
overlay, WNTB's built-in one (Windows) or EDMCModernOverlay ([setup](../OVERLAY_SETUP.md)). With up to twenty missions a list of all of them would cover the screen, so the card shows what you can act on now:

```
MISSIONS 14 · 2 ready · 3 soon
HERE Jarogee
✓ Gold > Newcomb Orbital              35m
40 Palladium 12/40 > Fabian Port   3h20m
Massacre x2 Li Yong-Rui > Fabian Port   1d
NEXT Sol
Passengers > Abraham Lincoln       5h00m
ELSEWHERE
Combat > HIP 20019                  3d
+8 more in 5 systems
```

- **PINNED** (when you have pinned any in the Missions window) comes first, one line per pinned mission, the station when it is in your system and the system otherwise.
- **HERE** is the missions whose turn-in or destination is the system you are in. **NEXT** is the same for the system you have **targeted** for the next
  jump (plot a route and the game targets each hop in turn). Then the rest (**ELSEWHERE**), and `+N more in M systems` when your row limit cuts it off.
- **Order:** a finished mission (✓) first, with the place to hand it in, then the soonest to expire. A mission with under an hour left (you can change it)
  is red, under six hours amber, a finished one (ready to hand in) is always a clear green, whichever overlay color scheme you use. Otherwise a line takes its color from [progress](#progress): lime when a mission is half or more done, blue when it is started. These colors are fixed and do not follow the overlay color scheme; time pressure (red, amber) comes before progress.
- **Stacking:** massacres and settlement raids against one faction in one place, and any other missions with the same title for the same station, are one
  line with a count (`x3`). A cargo mission shows its progress (`12/40`).
- **Long names** keep the card one fixed width: when a mission's title and place do not fit on one line, the place goes on a line under it, and only a name longer than a whole line is cut short. The time left is always shown. The card's top-left corner never moves as lines come and go.
- **Placement:** Settings → Overlays → Overlay Placement ("Missions list"). It starts in the bottom-right corner, above the screenshot messages; move it to
  any corner.
- **Settings:** the number of mission lines to show (3 to 14, 8 by default), whether to show the next jump, and the red limit in minutes. **Test Card**
  draws a made-up card.

What it cannot know: the game lists your active missions only at login, so after restarting EDMC mid-game the card is built from your last two weeks of
journals (as above). The next jump is the system you have *targeted*; with no target there is no NEXT section.

## Source commodities

Collect and Mining missions need cargo you have to find. The **Find sources** button at the bottom of the panel (or **Sources** in the Missions window) opens the
Source commodities window: for each commodity, summed over all your active missions, the same four picks as Trade's [Best picks](trade.md#best-picks) (closest,
best local, cheapest anywhere, recommended within 10% of the cheapest), for buying.

1. Pick where to measure from: **From where I am** (your current system; if WNTB has not seen you jump since EDMC started, it reads it from EDMC and then from your newest journal, so you do not need to jump first) or **From the turn-in system** (where most of the missions for that commodity are
   handed in, so you can see what is nearest to the place you will deliver to).
2. Press **Find sources**. It asks Spansh a few times per commodity, one commodity after another, and shows each as it finishes. Press **Cancel** to stop.
3. Pick a row and press **Copy system** to put its system name on the clipboard for the galaxy map.

It uses the landing pad size, "Near me" radius, carriers and ground settings from Trade, and it only works when **Enable Spansh trade lookups** is on in
Settings → Trade (it is off by default; if it is off when you press **Find sources**, the window asks whether to turn it on, and nothing is searched until you say yes).
Nothing is searched until you press the button. If none of your missions needs cargo to be found, the window says so. The window lists at most twelve commodities, the biggest need first.

Not covered: the nearest ring hotspot for a Mining mission (use Mining's hotspot finder), and market data older than 7 days is ignored.

## Settings

**Settings → Missions**: choose what shows on each card (kill progress, mission counts, a commodities-needed
summary and so on).

More detail: [Missions specification](../MISSIONS_TECH_SPEC.md).
