# Technical Specification — Screenshots and input automation

**Author:** R.W. Harper (CMDR Bocheaux)
**Last updated:** 2026-10-02 (pre-1.0 development; see `CHANGELOG.md`)

Two WNTB features press keys in the game for you: **Auto-Honk** and **timed or automatic screenshot
capture**. This document explains exactly what they do and don't do, how Screenshots converts and crops
pictures, and how it all differs on Linux. For how to use them, see the
[README](../README.md#field-ops). For how the code is organised in general, see
[TECHNICAL.md](TECHNICAL.md).

## 1. Input automation: what it is, and isn't

**What WNTB does.** It asks the operating system to press a key, exactly as if you pressed it on your
keyboard, and only while an Elite Dangerous window exists (and, for the screenshot timer, has focus).

- **Windows:** ordinary Win32 key events (`keybd_event`, and `ctypes` calls to `user32.dll`).
- **Linux:** the `xdotool` program, which sends keys to the focused window through the X server (X11, or
  XWayland on a Wayland desktop).

**What WNTB does not do.**
- It does not read or change the game's memory, inject into the game, or alter game files.
- It does not send anything over the network as part of this.
- It cannot press joystick or HOTAS buttons, only keyboard keys.
- It does nothing at all unless you turn it on (see §6 for the one automatic exception).

**Every entry point is a safe no-op when unsupported** (for example on macOS, or Linux without
`xdotool`): it returns "not done" and the rest of WNTB carries on. Failure to press a key never breaks
journal handling.

## 2. Auto-Honk

Fires your ship's **Discovery Scanner** (the basic system-wide "honk", not the surface scanner) when you
arrive in a system. **Off by default.**

1. **Trigger:** a `FSDJump` or `CarrierJump` journal event. A fresh login (`LoadGame`) clears the
   "visited this session" memory.
2. **Skip repeats (default on):** each system is honked once per session, by its system address.
3. **Find the key:** it reads your active **binds file** (`*.binds`, the game's own control settings) and
   finds the keyboard key assigned to the chosen fire button (Primary or Secondary; default Secondary).
   If that button is bound only to a joystick button, or isn't bound, or the key isn't one WNTB can
   produce, nothing is sent and the Settings tab says why.
4. **Press and hold:** the key is held down for a set time (default **10 seconds**), because the scanner
   charges while the button is held and a quick tap never honks. The time depends on your scanner and
   engineering, so it's adjustable. This runs on a background thread so EDMC never freezes.
5. **Focus the game (default on):** it can bring the Elite window to the front first.

Outcomes shown in Settings: sent; Elite window not found; no usable keybind; unsupported OS;
`xdotool` missing (Linux); error (see the EDMC log). The **Test Honk Now** button runs the same steps on
demand. **EDCoPilot** also has an auto-honk, so WNTB warns you to turn one off if both run.

## 3. Screenshots

### 3.1 What it does
When Elite takes a screenshot (by you, or by the timer), the game writes a raw file and logs a
`Screenshot` event. WNTB then:

1. **Finds the file.** The event's `Filename` isn't a real path, so only its base name is used, searched
   for in the configured Screenshot Directory first, then in fallback locations. If it was found
   somewhere other than the configured folder, the setting is corrected.
2. **Converts it to PNG** (using Pillow) and saves it, renamed, in the output folder. The folder can be
   grouped into one sub-folder per system.
3. **Shows thumbnails:** the newest capture, an optional cropped version, and a strip of the last 8
   (wrapped four to a row). Click one for a larger preview.
4. **Optionally deletes the original**, but only after a **60-second** grace period so other plugins that
   want the raw file can see it first. Off by default.
5. **Notifies:** a status line in the panel and, if you use an overlay, a short on-screen message.

Conversion and cropping work on every platform; only the key simulation is platform-specific.

### 3.2 File names
Names come from a **mask** you choose. The tokens are `SYSTEM`, `BODY`, `CMDR` and `DATE` (a UTC
timestamp), plus `NNNNN`, a five-digit sequence number that is unique per output folder (WNTB looks at the
files already there and uses the next number). Characters a file system might reject are stripped. A
hi-res capture (the game's `HighRes` file names) gets a `HighRes_` prefix. The `BODY` token drops the
leading system name so a mask using both doesn't repeat it.

### 3.3 Cropping
The game doesn't say which panel you had open in the screenshot event, so WNTB reads **`GuiFocus`** from
`Status.json` (the game's live status file) at that moment. For the **Target**, **Comms**, **Role** and
**Systems** panels it makes a second, cropped picture of just that panel. The crop rectangles are defined
on a 1920×1080 reference frame and scaled **uniformly** (by the smaller axis ratio) and centred, because
the HUD panels keep their proportions and sit centred on ultrawide and multi-monitor setups. Scaling the
two axes separately would stretch the crop. Hi-res captures are not cropped.

A **Thargoid** capture crops the bottom-left quarter of the screen instead (see §6).

### 3.4 The timer
An optional **auto-capture timer** (a clock icon) presses the screenshot key every **poll interval**
(default 1 second, never faster than 0.2 s, because it presses a real key combination and a mistyped value
shouldn't hammer it). Safeguards:
- It starts **off** every time EDMC starts.
- It only fires while an **Elite window has focus**; otherwise the status says "paused (Elite not
  focused)".
- It stops itself on `ShutDown` and `Died`.
- The key is held for only **60 ms** and released on a timer, so it is never left held waiting for the next
  journal event.
- **Hi-res on timer** (off by default) adds Left Alt for an Alt+F10 capture, and is only used in **Solo**
  mode, where the game allows hi-res captures.

## 4. Keeping the main window from growing

Every image in the panel sits in a fixed width-and-height box, so an ultrawide capture can't widen EDMC's
main window. See [TECHNICAL.md](TECHNICAL.md) section 5.

## 5. Linux

On Linux, Elite runs under Steam Proton or Wine, so the game's "Windows" folders live inside a Wine
prefix. `platform_support.py` finds that prefix (including extra Steam library folders and Flatpak Steam,
with a Settings override for Lutris, Heroic or custom setups), and from it the binds folder, the
Pictures (screenshot) folder and the journal folder. Keys are sent with `xdotool` after focusing the game
window, because synthetic per-window key events are ignored by most games. Auto-Honk and the timer work
on X11 and on XWayland. Everything is returned as "not found" rather than raising when something is
missing.

## 6. The one automatic behaviour: Thargoid captures

**On by default**, a setting called *Thargoid capture*: when you collect Thargoid ship flight data or an
unknown ship signature (`MaterialCollected`), WNTB presses the screenshot key once and crops the result.
The game's `Music` event for the Thargoid encounter tracks also marks the next capture for the same crop.
This is the only input WNTB sends without you turning something on first. To stop it, turn off
*Thargoid capture* in **Settings → Screenshots**.

## 7. Settings

**File → Settings → WNTB → Screenshots** (keys start `wntb_screenshot_`): source and output folders,
delete originals, group by system, the file-name mask, the timer icon, hi-res on timer, Thargoid capture,
the overlay notification, and the poll interval. **Settings → Auto-Honk** (keys start `wntb_autohonk_`):
enabled, fire button, hold time, focus the game, skip repeats, and the Linux prefix override.

## 8. Testing

`tests/test_platform_support.py` covers the Linux helpers (prefix and folder finding, key naming). The
file-name, crop and conversion code is pure logic but has **no automated tests yet**, and the key
simulation is checked by hand in a live game. Every failure path returns a plain result rather than
raising.

## 9. Known gaps

- Auto-Honk and the timer can only press **keyboard** keys.
- The crop rectangles are fixed measurements and may need adjusting if Frontier changes the HUD.
- Windows may block file access with Controlled Folder Access or antivirus; the error message says so.
- macOS isn't supported for key simulation (conversion and cropping still work).
- Linux on Wayland **without** XWayland is unsupported for key simulation.
