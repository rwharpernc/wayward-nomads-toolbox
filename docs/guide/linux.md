# WNTB on Linux

WNTB runs on Linux wherever EDMC does. It has been tested on a real install (KDE Plasma on Wayland, Elite under
Steam Proton, EDMC as a Flatpak): the Settings panel, the on-screen overlays (test overlay, Discovery Alerts,
Notable Bodies), Auto-Honk, the screenshot features and Trade all work. Please report anything odd.

Elite runs under Steam Proton or Wine on Linux, which needs a few extras. **Work through the steps in order.**

**Which steps do I need?**

| Your setup | Steps |
|---|---|
| Just the journal-based features (Powerplay, Missions, BGS, Trade...) | 2 (and 3 if EDMC is a Flatpak) |
| Plus Auto-Honk or the screenshot timer | 1, 2, 4 (and 3 if Flatpak) |
| Plus on-screen overlays | 1, 2, 5 (and 3 if Flatpak) |

## Step 1: Install the helper tools

- **`xdotool`** presses keys in Elite's window for Auto-Honk and the screenshot auto-timer. Install it **on your
  system** (not inside anything):

  | Distribution | Command |
  |---|---|
  | Debian / Ubuntu | `sudo apt install xdotool` |
  | Arch / CachyOS | `sudo pacman -S xdotool` |
  | Fedora | `sudo dnf install xdotool` |

  It works on X11, and on Wayland through XWayland (which is where a Proton game's window lives). It does not
  work with a *native* Wayland window.

- **EDMCModernOverlay** draws the on-screen cards. Install it as an EDMC plugin from its
  [project page](https://github.com/SweetJonnySauce/EDMCModernOverlay). The original EDMCOverlay is Windows-only.
  WNTB's default connection settings (`127.0.0.1`, port 5010) already match it.
- Optional: `canberra-gtk-play` or `paplay` for notification sounds.

## Step 2: Tell EDMC where Elite's journals are

Linux has no default journal folder, and without one WNTB's journal-based features have nothing to read (that
includes BGS rebuilding the tick's totals).

1. In EDMC, open **File → Settings → Configuration**.
2. Set **Journal directory** to the `Saved Games/Frontier Developments/Elite Dangerous` folder inside Elite's
   Proton folder. It is usually:

   ```
   ~/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous
   ```

3. Restart EDMC.

WNTB shows a hint under **Settings → Exploration → Alerts** and **Settings → BGS** if it looks wrong, and logs one
at startup.

**The Elite Wine/Proton prefix box.** WNTB finds the Proton folder itself, including extra Steam library folders
and Flatpak Steam. Only if you use Lutris, Heroic or a custom setup should you enter the folder under
**Settings → Exploration → Alerts → Elite Wine/Proton prefix**. Otherwise **leave that field empty**.

> A wrong value in that box stops WNTB from finding your keybindings, because it deliberately does not fall back
> to auto-detection.

## Step 3: If EDMC is a Flatpak, grant it four permissions

A Flatpak runs in a sandbox that cannot see your Steam folders, your keyboard tools or your desktop. Without these
permissions, WNTB looks fine in its settings but does nothing.

Run each command once in a terminal, then **restart EDMC**. They only widen what EDMC can reach; nothing else
about the sandbox changes.

```bash
# Set this to your Elite Proton folder (the same one as Step 2, without the trailing parts).
PFX="$HOME/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser"

# 1. Journals (EDMC reads the journal and Status.json, and keeps a lock file there)
flatpak override --user --filesystem="$PFX/Saved Games/Frontier Developments/Elite Dangerous" io.edcd.EDMarketConnector

# 2. Keybindings (read-only; Auto-Honk needs to know which key you bound)
flatpak override --user --filesystem="$PFX/AppData/Local/Frontier Developments/Elite Dangerous/Options/Bindings:ro" io.edcd.EDMarketConnector

# 3. Screenshots (read and write; WNTB converts and files them)
flatpak override --user --filesystem="$PFX/Pictures/Frontier Developments/Elite Dangerous" io.edcd.EDMarketConnector

# 4. Run host programs: lets the overlay window start, and lets WNTB use your system's xdotool
flatpak override --user --talk-name=org.freedesktop.Flatpak io.edcd.EDMarketConnector
```

(If your shell is fish, replace the first line with `set PFX "$HOME/.local/share/Steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser"`
and use `$PFX` in the rest.)

Check them with:

```bash
flatpak override --user --show io.edcd.EDMarketConnector
```

Other things to know:

- **Flatpak Steam:** your Proton folder is under `~/.var/app/com.valvesoftware.Steam/.local/share/Steam/` instead.
- **Plugin folder:** a Flatpak EDMC keeps its plugins in
  `~/.var/app/io.edcd.EDMarketConnector/data/EDMarketConnector/plugins`.
- **Not a Flatpak?** (A native or AppImage install.) Skip this whole step.

**Why permission 4 matters.** EDMCModernOverlay starts its drawing window through the host, and WNTB runs
`xdotool` the same way. Without it, WNTB's **Check connection** still reports success (the overlay's port is open)
but nothing is drawn, and Auto-Honk says `xdotool` is not installed even though it is.

## Step 4: Bind a keyboard key for the honk (Auto-Honk only)

Auto-Honk can only press **keyboard** keys. If your fire buttons are bound only to a mouse button or a HOTAS
button, it reports "only bound to a joystick/HOTAS button".

1. In Elite, open **Options → Controls → Ship → Cockpit Modes**.
2. Add a keyboard key to the **second** slot of **Secondary Fire**. Keep your mouse or stick binding in the first
   slot.
3. In EDMC, open **Settings → Exploration → Alerts** and press **Rescan**. It should say "Will press &lt;your
   key&gt;".
4. Press **Test Honk Now** with the ship able to use its scanner.
5. Set the **hold time** to the seconds the scan needs (8 to 10 is typical). The key is held down for the full
   time.

## Step 5: Check the overlay

1. Start EDMC and Elite (borderless or windowed).
2. Open **Settings → WNTB → General → Overlay Connection** and press **Check connection**.
3. Press a **Test** button, such as **Test Discovery** or **Test Notable** under **Exploration → Alerts**.

Cards should appear over the game. If they don't, see the Linux items in [Troubleshooting](troubleshooting.md).
The general overlay guide is [Setting up the on-screen overlay](../OVERLAY_SETUP.md).

## Step 6: Trade (nothing extra to install)

Trade needs nothing beyond Step 2, but it leans on it more than most features. EDMC's **Journal directory** is what
lets WNTB:

- catch a trading session up after you played with EDMC closed,
- rebuild your carrier's cargo history at start-up,
- read the docked station's `Market.json`.

If it is wrong or empty, those quietly find nothing, and the session only counts what EDMC delivered while it was
running. For a Flatpak EDMC, the journals permission in Step 3 already covers it.

The Spansh lookups just need the network. **Export log (CSV)** in Trade History uses a standard file dialog. If EDMC
is a Flatpak and the save fails, pick a folder EDMC is allowed to write to (WNTB shows the error).

## More help

- A step-by-step checklist for testers: [LINUX_TESTING.md](../LINUX_TESTING.md).
- The platform differences and the reasoning behind them:
  [TECHNICAL.md section 18](../TECHNICAL.md#18-platform-support-windows-and-linux).
- What works where: [Windows and Linux](platforms.md).
