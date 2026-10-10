# Missions

One view of every mission on your board, sorted by type, plus Community Goals.

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

WNTB can only show what Elite Dangerous writes to its journal files and what the online services it asks (none are needed for missions) publish. Where it can't be sure, WNTB says so rather than guess quietly.

| What you might expect | What the game gives | What to do |
|---|---|---|
| Every kill to be counted | **Wing and on-foot kills** are often missing from the journal until the mission completes, so those counts run low. WNTB marks them with a `~`. Combat-zone kills are recorded as combat bonds, not bounties; WNTB counts them too (checked against real journals), but they carry no ship type, so an on-foot combat-zone kill can be counted as a ship kill. | Read a `~` as "at least this many". The game's own mission screen is the final word. |
| Active missions to appear after restarting EDMC mid-game | The game lists active missions only in its login event, so WNTB works the list out from the last two weeks of journals (the latest login list plus what was accepted, completed, abandoned or failed since). A mission that **expired without a journal entry** can show until your next login. | Log in again to get the game's own list. |
| Cargo mission progress to be exact | The game reports it (`CargoDepot`: collected, delivered and total) when you collect or hand in cargo, and when a wing-mate does. Progress made before WNTB's two-week window, or with no event since, isn't known. | The card shows it once the game has reported any; otherwise check the game's mission screen. |
| Missions accepted a while ago to appear | WNTB reads only the **last two weeks** of journals at start-up. A mission still active but accepted earlier is not found and not shown. | Keep EDMC running while you hold long missions, and check the game's own mission board for older ones. |
| Kills made while EDMC was closed | Counted only if they are in the last two weeks of journal files. | Run EDMC whenever you play. |
| Every mission to land in the right category | Names WNTB does not recognise go to **Other**. | Click the card for details. If a type is always in Other, open an issue so it can be added. |
| A Community Goal to disappear when it ends | The game gives no "gone" signal, so the panel relies on each goal's expiry date. | Ignore a goal past its expiry; it clears itself. |

## Settings

**Settings → Missions**: choose what shows on each card (kill progress, mission counts, a commodities-needed
summary and so on).

More detail: [Missions specification](../MISSIONS_TECH_SPEC.md).
