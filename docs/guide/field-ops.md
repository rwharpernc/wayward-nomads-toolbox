# Field Ops

Field Ops holds the on-foot and housekeeping tools: screenshots, your inventory, saved ship builds, and
colonisation sites.

**On this page:** [Screenshots](#screenshots) · [Inventory](#inventory) · [Ship Builds](#ship-builds) ·
[Colonisation](#colonisation)

## Screenshots

Converts Elite's screenshots to PNG automatically, with an optional crop to just the relevant HUD panel.

**How to use it:** nothing to do. Screenshots convert as you take them.

- Click **"Click to expand"** in the panel to see thumbnails of recent ones.
- An optional auto-capture timer (a small clock icon) takes screenshots periodically for you.

**Settings → Field Ops → Screenshots:**

- where converted screenshots are saved,
- whether to delete the originals,
- the file-name format,
- the auto-capture timing,
- an optional "Screenshot saved" message on your game screen (needs an overlay).

*On Linux, the auto-timer needs `xdotool`, and a Flatpak EDMC needs the screenshots permission. See
[WNTB on Linux](linux.md). On Windows, OneDrive-redirected folders are handled automatically.*

## Inventory

Tracks your Odyssey backpack, ship locker, fleet carrier locker and cargo hold as capacity bars.

**How to use it:** just play. Each bar fills and empties as you pick things up, use them or transfer them.

**Click any bar** to open the full inventory window. It has tabs for:

- **Backpack**
- **Ship Locker**
- **Carrier Locker** (once WNTB knows you own a carrier)
- **Cargo**: the hold of whatever you're in, ship or SRV. It has a **Filter** box to find a particular item.

**Settings:** pickup notifications (sound, on-screen message, what it says), and capacity numbers if your loadout
doesn't match the defaults.

## Ship Builds

A place to keep ship builds you've designed on sites like Coriolis, EDSY or Spansh, one list per commander. WNTB
doesn't design ships itself. This just helps you find a build again later.

**To save a build:**

1. Design your build on whichever site you like.
2. Click **SHIPS** (manage ship builds) in the WNTB panel.
3. Click **Add**.
4. Give it a name, and optionally a role such as "PvE Exploration".
5. Pick the site and paste the build's web address.
6. Click **Save**.

**Example:** name `Krait Phantom explorer`, role `Exploration`, site `Coriolis`, and paste the link from your
browser's address bar.

**To use it later:** select a saved build and use **Open Link** to open it in your browser, or **Copy Link** to copy
the address. **Edit** and **Delete** work the same way.

## Colonisation

Keeps track of what each colonisation construction site still needs, so you can see it without being docked, and
what you still have to find after counting the cargo already in your hold.

**To start tracking a site:**

1. Dock at a construction depot (or open its market) **once**. WNTB registers the site from the game's journal.
   There's nothing to type in.
2. The Field Ops panel shows your most recently updated site: its progress and the tonnes still to go.
3. Click **REPORT** for the full list. Each site is a group with its outstanding commodities underneath:
   - required,
   - delivered,
   - remaining,
   - how much is in your cargo now,
   - how much is left **To Source**.

Deliveries are counted from your journal as you hand cargo over, and corrected to the game's own figures each time
you dock at the depot again.

**Buttons in the report:**

- **Copy Shopping List**: select a commodity row, then use it to copy that site's list. Handy for a squadron
  channel.
- **Remove Site**: stop tracking it.
- **Remove Finished**: clear completed and failed sites.
