# Data verification checklist

`verification_checklist.csv` lists every piece of data WNTB carries, or would carry, that is **missing** or still **needs verification** in the game,
with where it came from and under what license. It is meant to be imported into a Google Sheet and worked through. The project's method is stated in
[ATTRIBUTIONS.md](../ATTRIBUTIONS.md) ("Data"): values are measured in the game by the project owner, and other authors' published values are reviewed,
checked against the game, and used once verified, with credit.

## Import into Google Sheets

1. In Google Sheets choose **File → Import → Upload**, pick `verification_checklist.csv`, set **Import location** to *Insert new sheet(s)* (or *Replace
   spreadsheet* for a new file), **Separator type** to *Comma*, and untick **Convert text to numbers, dates, and formulas** so values such as `1,875,000` and
   `+50%` stay as written.
2. **View → Freeze → 1 row** and **2 columns** (id and status stay visible). Turn on **Data → Create a filter** and filter by `area` or `status`.
3. Optional: also import `sheet_lists.csv` into a second sheet. Select the `status` column, choose **Data → Data validation → Dropdown (from a range)** and point it at
   the status list there; do the same for `priority`. Then **Format → Conditional formatting** by `status` (for example red for Missing, amber for Needs
   verification, green for the two Verified values).
4. Widen `what_to_check`, `how_to_verify_in_game` and `notes`, and set them to *wrap text*.

## Columns

| Column | Meaning |
|---|---|
| `id` | Stable row number (`V-0001`). Do not renumber; add new rows at the bottom with the next number. |
| `status` | **Missing** (nothing recorded yet), **Needs verification** (a value exists but has not been checked in the game), **Verified - journal** (confirmed by real journal events, which are the game's own records), **Verified - in game** (the project owner has read it in the game). |
| `priority` | High, Medium or Low: what to do first. |
| `area` / `item` | Where the data belongs and exactly which piece it is. Rows are sorted by area, then priority. |
| `what_to_check` | What to look at. |
| `current_value_in_wntb` | What WNTB carries now, if anything. |
| `value_from_source` | A value from a cited source that is not in WNTB yet (a candidate to verify). |
| `source`, `source_license`, `source_url` | Where it came from and its license. "Confirm" in a license cell means it was not checked. |
| `how_to_verify_in_game` | The steps. |
| `verified_value` ... `screenshot_ref` | Fill in when you check it: the value you read, the date, the game version (the journal's `Fileheader` has it) and the screenshot's file name. |
| `notes` | Anything else, including disagreements between sources. |

## Working through it

1. Start with **High** rows, then the Odyssey stat rows (`docs/ODYSSEY_STAT_COLLECTION.md` says how to record those).
2. When a row is checked, set `status` to *Verified - in game*, fill in the verified columns, and, if the game disagrees with WNTB or the source, say so in
   `notes` and tell the project so the data can be corrected.
3. A value from a source stays *Needs verification* until you have read it in the game yourself. Do not change a status on the strength of another tool.
4. Bring the checked values back into the repository (the Odyssey ones as `docs/odyssey_stats/base_stats.csv` and `mod_effects.csv`), and credit the
   source of any value that began as another author's published data. The data is open; the request is acknowledgement. See the license note in
   [ODYSSEY_STAT_COLLECTION.md](../ODYSSEY_STAT_COLLECTION.md).

The checklist was generated from the project's own tables and from [TODO.md](../TODO.md) on 2026-10-16. It lists only what is known to be unverified; a table
not listed has not been audited, not been proven right.
