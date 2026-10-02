# Technical Specification — Missions

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-02 (see `CHANGELOG.md`)

The standing reference for Missions mode: what it reads, the rules it applies, and what its numbers can
and can't tell you. For how to use it, see the [README](../README.md#missions). For how the code is
organised in general, see [TECHNICAL.md](TECHNICAL.md).

## 1. Goals

- Show every mission on the commander's board in one place, sorted into pages by type.
- For kill-count missions (massacres and settlement raids), show **stacked** progress: how many kills
  you have, how many each mission-giving faction still needs, and the reward.
- Show Community Goals and the commander's own contribution.
- Survive an EDMC restart without losing the picture, and keep each commander's missions separate.

## 2. Non-goals

- **No exact kill counts.** The journal never reports per-mission kill progress, so progress is an
  estimate (see §5).
- **No network access.** Everything comes from the journal. Nothing is sent or fetched.
- **No mission planning.** It doesn't suggest missions or routes.
- **No colonisation missions.** They're dropped from every page on purpose (see §4).

## 3. Architecture

All modules live in `plugin/`; `PANEL_PLACEMENT = "missions"`.

```
missions.py            Entry point (feature-module contract). Reads settings, starts the backlog scan,
                       and routes each journal event to the modules below.
journal_scan.py        Reads the last two weeks of journals at start-up (Backlog).
active_missions.py     Per-commander roster of accepted and active missions (ActiveMissions).
kill_tracker.py        Per-commander kill evidence: Bounty events, completed mission ids, new turn-in
                       places, and the on-foot/ship kill test.
kill_missions.py       The kill-count missions among the active ones, plus the progress estimate.
all_missions.py        A generic summary of every active mission (the "All Missions" view).
community_goal_state.py Community Goal snapshots and the commander's contribution.
mission_types.py       The rules that decide a mission's category. Pure, no dependencies.
missions_ui.py         The panel (category pages) and the "All Missions" and detail pop-ups.
notifier.py            A small subscribe/notify helper the views use to tell the UI something changed.
```

Data flows one way. `ActiveMissions` announces the active set; `kill_missions` and `all_missions`
subscribe and rebuild; the UI subscribes to those. The data layer never imports UI code.

### 3.1 Journal events used

| Event | What it does here |
|---|---|
| `Commander`, and the commander name EDMC supplies | Decides whose roster an event belongs to |
| `MissionAccepted` | Adds the mission to the commander's roster and marks it active |
| `Missions` (sent at login) | Lists the ids that are active, and the ids already complete |
| `MissionRedirected` | The mission's objective is done; may carry a new turn-in station/system |
| `MissionCompleted`, `MissionAbandoned`, `MissionFailed` | Removes the mission |
| `Bounty` | One kill; the `VictimFaction` says whose |
| `CommunityGoal` | Community Goal snapshots (may list several goals at once) |

## 4. Classification

Frontier doesn't document mission types, but each mission's internal `Name` carries underscore-separated
tags (for example `Mission_Massacre_Onslaught`, `Mission_Delivery_Illegal_MB`) that the community has
learned to read. `mission_types.classify()` buckets a `MissionAccepted` event like this, first match wins:

1. **Massacre-shaped** (see below) → *Massacre (Space)* or *Settlement Raids (Ground)*.
2. Name contains a combat hint (`assassinate`, `disable`, `skimmer`, `conflict`, `piracy`, `scout`,
   `thargoid` and similar) → **Combat**.
3. Name contains a trade hint (`delivery`, `courier`, `collect`, `mining`, `salvage`, `smuggle`) →
   **Trade & Mining**.
4. Name contains a passenger hint (`passenger`, `sightseeing`, `vip`, `bulk`, `evacuation`) →
   **Passenger**.
5. Name contains a covert hint (`hack`, `heist`, `sabotage`, `download`, `upload` and similar), or the
   mission is on foot → **Covert / On-Foot Ops**.
6. Anything else → **Other**.

- **Massacre-shaped** means the event has both a `KillCount` and a `TargetFaction` (the mission's
  *shape*), or the name contains `massacre`, `onslaught` or `raid`. Using the shape first means a
  kill mission with an unfamiliar name is still recognised.
- **On foot / ground** means `OnFoot` in the name, or a `DestinationSettlement` on the event.
- **Illegal** means `illegal` or `smuggle` in the name; the card shows a "⚠ Illegal" badge.
- **Mining missions** need `mining` in the name. This is deliberately narrower than "has a Commodity
  field": Collect and Delivery missions also carry one, but you buy or collect that cargo, so showing a
  mining hint on them would be wrong.
- **Colonisation missions** (`colonisation` in the name) are excluded from every page.

New or odd mission names fall into **Other**, which is the safe default. The name hints are community
knowledge and may need extending when Frontier adds mission types.

## 5. The kill-progress estimate

**Why an estimate.** Elite doesn't tell plugins how many kills a mission has. What the journal gives is
a stream of `Bounty` events, each naming the faction of the ship or person killed. WNTB replays those
against your active kill missions using the game's known stacking rules.

**Rules** (`kill_missions.estimate_progress`), per commander:

1. A mission whose id is in the *completed* set (from `MissionRedirected` or the login `Missions`
   event) counts as **fully done**.
2. For the rest, missions are queued **per mission-giving faction**, oldest first.
3. Each `Bounty` counts as one kill, but only if the victim's faction matches the mission's target
   faction, the kill is in the same arena (on foot or in a ship, from the victim's type), and it
   happened after the mission was accepted.
4. A qualifying kill is credited to the **oldest unfinished mission of every giver** that fits. That is
   what makes stacking work: one kill advances several missions from different factions at once, but only
   one mission per faction.

**What the panel shows for a stack**
- **Progress `done/required`** for each giver faction, with a bar. A `~` in front means the number is an
  estimate (it appears for any wing or on-foot mission).
- **Δ (the remaining-kills column).** For a faction's stack, how many more kills it needs to reach the
  tallest stack. For the tallest stack, the gap down to the next-tallest.
- **Sum row.** Total progress against the tallest stack (your effective kill target when stacking).
- **Reward** is shown as the total, with the share you'd get from wing-shareable missions in brackets.
- **Warnings** appear when the missions have several target factions or systems, and a standing note
  that wing and on-foot kills are often unreported until the mission completes.

**Limits to know about**
- **Wing and on-foot kills** are frequently missing from the journal, so those counts run low until the
  game reports completion. That's why they're marked `~`.
- **Only the last two weeks of journals are read at start-up.** Kills from before that aren't counted,
  and a mission still active but accepted earlier isn't found at all (the log notes "active but not
  found in the scanned journals", and it isn't shown).
- **Kills made while EDMC wasn't running** are caught by the backlog scan only if they're in the last
  two weeks of files.
- It is an **estimate by design**. When the game reports a mission redirected or complete, that is
  authoritative and replaces the estimate.

## 6. Completion and drop-off

A mission is **Complete** once its id appears in the completed set, which two events feed:
`MissionRedirected` as it happens, and the `Complete[]` list in the login `Missions` event (so a relog
is correct immediately). When the redirect named a new station or system, that becomes the **drop-off**
shown on the card. Completion state is dropped when the mission is handed in, abandoned or failed.

## 7. Community Goals

`CommunityGoal` events list `CurrentGoals`, which can include goals in several systems at once. The
journal never says a goal has gone away, and finished goals keep reappearing for a while, so state is
**additive**: every goal id ever seen is kept and the newest snapshot wins. The panel then filters to
goals that haven't expired. Each card shows the title, system, market, expiry, the community's tier
reached, your contribution and rank, and the bonus. The tier shown is the *community's*, not yours.

## 8. Commanders and persistence

Every roster, kill list and goal set is keyed by commander, so switching commander in EDMC immediately
shows that commander's data and never leaks another's. Nothing is written to disk: the picture is rebuilt
each start from the two-week backlog plus the login `Missions` event. The only saved setting that isn't a
checkbox is the last category page you were on.

## 9. Settings

Under **File → Settings → WNTB → Missions** (config keys start `wntb_missions_`): kill progress, the
remaining-kills column, the totals row, mission count, target settlement (for ground missions), and the
commodities-needed summary on the Trade & Mining page. All default to on.

## 10. Testing

`tests/test_missions_data.py` covers the active-missions roster (commander separation, login sync,
accept and finish), the kill-progress rules (stacking, oldest-first, arena and timing, redirected
missions) and the journal backlog reader (per-commander collection, malformed lines, age cut-off,
missing folder). The category rules and the panel are exercised by hand in EDMC.

## 11. Known gaps

- Mission names the rules don't recognise land in **Other**; the hint lists need upkeep.
- Kill counts for wing and on-foot missions are estimates and can lag.
- Nothing older than two weeks is read at start-up.
- Community Goals have no "gone" signal, so the panel relies on each goal's expiry date.
