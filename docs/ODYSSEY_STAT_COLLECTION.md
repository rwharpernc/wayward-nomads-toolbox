# Collecting Odyssey stat data in the game

A procedure for gathering, and checking in the game, the numbers the Upgrade planner would need for a stat preview (see
[ODYSSEY_STAT_DATA.md](ODYSSEY_STAT_DATA.md) for why, and for what other tools hold). The game changes, and there is a long history of data about it
that has gone stale, so the aim is to collect everything that can be found and make sure it is current. This page says what to record, how to record it,
and how to keep the record trustworthy.

## Statement of method

For the project's documentation: the data comes from two places. Some is **measured in the game** by the project owner, each value with the game version,
the date and a screenshot. The rest is **other authors' published work**, which is reviewed, **checked against the game**, and used once it has been
verified, with the original authors credited. A value that has not been checked in the game is marked as such and is not presented as verified. The
checklist in [data_verification/](data_verification/README.md) is the record of what has and has not been done, so public text should say only what it
shows. (The same statement is in [ATTRIBUTIONS.md](ATTRIBUTIONS.md) in the present tense, as the project's method; change it to the past tense only when
the checklist has no *Missing* or *Needs verification* rows left. The tables WNTB already carries from other authors were added before this checklist
existed; the checklist lists which of them are still to be verified.)

## License and acknowledgement

This repository is public and licensed under the **GNU GPL v3.0**, and the data collected here is open on the same terms: nothing in it is kept
proprietary. In the spirit of the community it is not restricted any further. The one thing asked in return is **acknowledgement**: anyone who reuses or repurposes the data is asked to credit the project and, through it, the
authors whose published work it was checked against. The GPL itself requires that copyright and license notices travel with the data; the credit is a
courtesy in addition to that. (If a specific attribution requirement is wanted, a data license such as CC BY 4.0 for the data files is the usual way to state
one; that is the copyright holder's decision.)

Other authors' work is respected the same way in the other direction: where a value came from a cited source, the source and its license are named in the
checklist, in [ATTRIBUTIONS.md](ATTRIBUTIONS.md) and, where the license asks for a notice, in `THIRD-PARTY-NOTICES.md`.

## What to collect

Three files in `docs/odyssey_stats/` (and the wider checklist in `docs/data_verification/`, which lists them all) (all comma-separated, one value per row, so a stat the game shows for some items and not others needs no
special handling):

| File | Contains |
|---|---|
| `coverage.csv` | The checklist, already filled in with every item and class (70 rows) and every item and modification the Upgrade planner knows (163 rows). Put the date in `done_on` when a row is finished. |
| `base_stats.csv` | One row per stat shown for an item at a class: `kind` (Suit or Weapon), `item`, `class` (1 to 5), `stat_name` exactly as the game words it, `value` exactly as shown, `unit` as shown, then where and when it was read. |
| `mod_effects.csv` | One row per stat a modification changes: the item and class it was on, the modification, the stat, the value before and after, and where and when. |

Fill in these files in place (or copy them to a spreadsheet and bring the result back). Record the source of any value you did not measure yourself in `notes`,
and keep the `done_on` / verification fields honest: a value from another author's work stays *unverified* until it has been read in the game.

## Procedure

**Before starting**

1. Note the game version. The journal's first line of each file (`Fileheader`) names it (`gameversion` and `build`); put it in `game_version` on every row.
   Stats are changed by game updates, so a value without a version is only half a record.
2. Work in order: base stats for every item at the classes you own or can buy, then modifications.
3. Take a **screenshot** of the stats screen for every reading, and put its file name in `screenshot_ref`. Keep the screenshots with the data files (not in
   this repository). Use the game's screenshot key; WNTB's Screenshots feature can rename them if it is set up.

**Base stats (one item at one class)**

1. Open the screen where the game shows the item's stats (the one used to buy, equip or upgrade it; write its name in `screen`).
2. Record **every** stat the screen lists, as one row each, using the game's own wording for `stat_name` and its own units. If a value is shown as a bar
   with no number, write the position you can read and say so in `notes` rather than guessing a number.
3. Upgrading changes the class: record the same item again at the next class. If the upgrade screen previews the next class's stats before you confirm,
   record the preview (and say `preview` in `notes`); otherwise read the item after the upgrade. Upgrades cost materials and credits: the Upgrade
   planner shows both, and the wishlist can gather the materials.
4. Check each item's rows against the journal when you can: `SuitLoadout` and `UpgradeWeapon` events name the item and class, so the class you
   wrote down can be confirmed afterward.

**Modifications (one modification on one item)**

1. A modification costs materials, and there are reports that one cannot be removed once fitted, so plan which items to spend them on. Use the
   Upgrade planner to see the cost first.
2. If the modification screen previews the change before you confirm, record the stat before and after from the preview (and say `preview` in `notes`).
   If it does not, record the item's stats screen before fitting and again after, and the difference is the effect.
3. One row per stat that changed. Put the item's class in `class`, because an effect may depend on it.
4. To learn whether an effect is a percentage or a fixed amount, measure the same modification on **two different items** (for example Magazine size on
   a Karma AR-50 and on a Manticore Executioner) and compare the before and after values. Note it in `notes`.
5. A modification whose name carries a family in brackets, such as "Greater range (Kinematic kinetic)", is for that family only: test it on one weapon of
   that family.

## Keeping the data trustworthy

- **Two readings for anything surprising.** Read it again on another day or from a second screen, and note both.
- **Sanity checks before relying on a table:** values should rise (or fall, for times) in step from class 1 to 5; a modification's "after" should differ from its
  "before" in the direction its name says; two items of one family should be in the same range.
- **Spot-check against play.** A preview that says a magazine holds 40 rounds should match the ammo counter on screen; the reload time should match a
  stopwatch within a fraction of a second.
- **Never fill a gap by estimating.** A blank cell is honest; the planner can say "not measured" the way it already says "credit cost not recorded".
- **Record what changed.** If an update changes a value, add the new reading as a new row with the new game version; do not overwrite the old one.

## Using the data afterward

When a data set exists, the Upgrade planner can show, for the chosen item and class range and modifications, the stats before and after. It would
read the file from the plugin folder, say which game version the values were measured or checked
in, and show "not measured" for anything missing. The same rule applies as for the rest of the project's data: the documentation lists what is and is not
covered.
