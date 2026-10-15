# Missions

One view of every mission on your board, sorted by type, plus Community Goals and what they paid you.

> **Where this comes from:** everything here comes from the journal alone, and the journal is thin in places: wing and on-foot kills are often missing until a mission completes, active missions are only listed at login, and a Community Goal never announces its end. Where WNTB has to work something out, it marks it (a `~`). See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

## Using it

The panel shows one category at a time, with a line like `◀  Combat (3)  ▶  All`. Click the **◀** or **▶** arrow to
page between categories; the number is how many missions are in that category. The pages, in order, are:

**Massacre (Space) · Settlement Raids (Ground) · Combat · Trade & Mining · Passenger · Covert / On-Foot Ops · Other · Community Goals**

- **Massacre** and **Settlement Raids** missions show grouped **kill-progress bars**, so you can see at a glance how
  many kills are still needed across all your missions for the same faction.
- Everything else shows **one card per mission**. Click a card for that mission's full details.
- **All** (at the right of the arrows) opens one flat table of every active mission, across every category.

The "All" window is titled *WNTB - All Active Missions*.

**Example.** You've taken five massacre missions against the same faction from different stations. Page to
**Massacre (Space)** and the bars show your total progress, rather than five separate counters to remember.

## What the game does and doesn't tell us, and how to work around it

WNTB, like every third-party tool, only knows what Elite Dangerous writes to its journal files. It needs no outside service for missions, so the journal is the whole story, and it works around the gaps below. Where it can't be sure, WNTB says so rather than guess quietly. See [How WNTB knows what it knows](README.md#how-wntb-knows-what-it-knows).

| What you might expect | What the game gives | What to do |
|---|---|---|
| Every kill to be counted | **Wing and on-foot kills** are often missing from the journal until the mission completes, so those counts run low. WNTB marks them with a `~`. Combat-zone kills are recorded as combat bonds, not bounties; WNTB counts them too (checked against real journals), but they carry no ship type, so an on-foot combat-zone kill can be counted as a ship kill. | Read a `~` as "at least this many". The game's own mission screen is the final word. |
| Active missions to appear after restarting EDMC mid-game | The game lists active missions only in its login event, so WNTB works the list out from the last two weeks of journals (the latest login list plus what was accepted, completed, abandoned or failed since). A mission that **expired without a journal entry** can show until your next login. | Log in again to get the game's own list. |
| Cargo mission progress to be exact | The game reports it (`CargoDepot`: collected, delivered and total) when you collect or hand in cargo, and when a wing-mate does. Progress made before WNTB's two-week window, or with no event since, isn't known. | The card shows it once the game has reported any; otherwise check the game's mission screen. |
| The next jump's missions on the overlay when you have a route | The game names the system you have targeted (`FSDTarget`), not the whole route, so only the next hop is NEXT. | Plot the route in the galaxy map and target the hops as you go. |
| Missions accepted a while ago to appear | WNTB reads only the **last two weeks** of journals at start-up. A mission still active but accepted earlier is not found and not shown. | Keep EDMC running while you hold long missions, and check the game's own mission board for older ones. |
| Kills made while EDMC was closed | Counted only if they are in the last two weeks of journal files. | Run EDMC whenever you play. |
| Every mission to land in the right category | Names WNTB does not recognize go to **Other**. | Click the card for details. If a type is always in Other, open an issue so it can be added. |
| A Community Goal's payout to be remembered for long | The game writes the payout (`CommunityGoalReward`) once. WNTB lists the latest three under **Paid out** on the Community Goals page, found in the last two weeks of journals at start-up. | Note a big payout elsewhere if you want to keep it. |
| A Community Goal to disappear when it ends | The game gives no "gone" signal, so the panel relies on each goal's expiry date. | Ignore a goal past its expiry; it clears itself. |

## Missions on the overlay

A small card on your in-game overlay, for flying. It is **off until you tick it** (Settings → Overlays → Missions) and needs EDMCModernOverlay like every
overlay ([setup](../OVERLAY_SETUP.md)). With up to twenty missions a list of all of them would cover the screen, so the card shows what you can act on now:

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

- **HERE** is the missions whose turn-in or destination is the system you are in. **NEXT** is the same for the system you have **targeted** for the next
  jump (plot a route and the game targets each hop in turn). Then the rest (**ELSEWHERE**), and `+N more in M systems` when your row limit cuts it off.
- **Order:** a finished mission (✓) first, with the place to hand it in, then the soonest to expire. A mission with under an hour left (you can change it)
  is red, under six hours amber, a finished one green.
- **Stacking:** massacres and settlement raids against one faction in one place, and any other missions with the same title for the same station, are one
  line with a count (`x3`). A cargo mission shows its progress (`12/40`).
- **Long names** are cut short to keep the card one fixed width; the time left is always shown. The card's top-left corner never moves as lines come and go.
- **Placement:** Settings → Overlays → Overlay Placement ("Missions list"). It starts in the bottom-right corner, above the screenshot messages; move it to
  any corner.
- **Settings:** the number of mission lines to show (3 to 14, 8 by default), whether to show the next jump, and the red limit in minutes. **Test Card**
  draws a made-up card.

What it cannot know: the game lists your active missions only at login, so after restarting EDMC mid-game the card is built from your last two weeks of
journals (as above). The next jump is the system you have *targeted*; with no target there is no NEXT section.

## Settings

**Settings → Missions**: choose what shows on each card (kill progress, mission counts, a commodities-needed
summary and so on).

More detail: [Missions specification](../MISSIONS_TECH_SPEC.md).
