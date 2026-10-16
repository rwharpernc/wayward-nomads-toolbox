# Reporting a problem

Found a bug, or a number that looks wrong? WNTB has two buttons that make a good report quick to write. Both are in
**File → Settings → WNTB → General → Help**.

| Button | What it does |
|---|---|
| **Report an issue** | Opens a bug report on GitHub in your browser, with the title started and your versions and operating system already filled in |
| **Copy diagnostics** | Copies the same version lines plus the newest WNTB lines from EDMC's log to your clipboard, so you can paste them into the report |

Neither button sends anything by itself. The report only exists on GitHub if you press **Submit new issue** there, and that needs your
own free GitHub account. You can always write the report by hand on the
[Issues page](https://github.com/rwharpernc/wayward-nomads-toolbox/issues) instead.

## How to report a problem, step by step

1. **Check whether it is a setting first.** Most "nothing happens" reports are a feature that is switched off. See
   [Troubleshooting](troubleshooting.md#nothing-happens-settings-that-start-off), and check whether the gap is a known limit of what the
   game records (each mode guide ends with "What the game does and doesn't tell us").
2. **Make the problem happen again if you can**, with EDMC still open, so the log has the lines from it. A problem from an hour ago may
   have scrolled out of the part of the log WNTB copies (see [what gets copied](#what-copy-diagnostics-copies)).
3. Open **File → Settings → WNTB → General → Help**.
4. Press **Copy diagnostics**. The line under the button reads *Copied. Paste it into the report's log box.* If it reads *Could not copy
   to the clipboard*, see [If something does not work](#if-something-does-not-work).
5. Press **Report an issue**. Your browser opens GitHub's bug report form. If you are not signed in to GitHub, it asks you to sign in
   first.
6. Fill in the form:
   - **Title:** it starts with your version, like `[1.16.0] `. Finish it with a few words on what went wrong.
   - **What happened?** What you saw, and what you expected to see instead.
   - **Steps to reproduce:** what you did, in order, and which panel, window or Settings page it was in.
   - **Environment:** already filled in with your WNTB, EDMC and Python versions and your operating system. Leave it as it is.
   - **Log lines (optional):** click in the box and paste (**Ctrl+V**). This is where the diagnostics go.
7. **Read the whole form before you submit it**, the pasted log included, and delete anything you would rather not post. This is a public
   project, so everything you submit is visible to everyone (see [what is left out](#what-is-left-out-and-what-to-check)).
8. Press **Submit new issue**.

## What "Report an issue" fills in

The form opens with the title started and the **Environment** box filled in, like this:

```
- WNTB: 1.16.0
- EDMC: 5.13.1
- Python: 3.11.9
- OS: Windows 11 (10.0.26200)
```

On Linux the OS line names your distribution, the session type and whether EDMC is a Flatpak, for example
`Ubuntu 24.04.1 LTS, wayland, Flatpak`. That is what the Linux problems in [Troubleshooting](troubleshooting.md#linux) usually turn on.

The form is a template (`.github/ISSUE_TEMPLATE/bug_report.yml`), and the bug label is set for you. If your browser opened the plain
new-issue page instead, the template was not found; write the same information in the box by hand.

## What "Copy diagnostics" copies

The text on your clipboard is:

- the same four version lines as above, then
- **WNTB log lines:** the newest lines from EDMC's log file (`EDMarketConnector-debug.log`) that were written by WNTB, up to 80 lines and
  about 12,000 characters. A traceback (the lines that start `Traceback (most recent call last)`) comes with the line that caused it.
  Lines written by other plugins and by EDMC itself are left out.

If the log has no WNTB lines in the part WNTB looked at, the text says `(no WNTB lines found in the log)`. That is not an error; it means
WNTB logged nothing recently. Describe what happened in the form instead.

WNTB reads only the last part of the log (roughly the last 400 KB), so a long play session can push an earlier problem out of reach. If
what you need is older, open the log folder from **EDMC → Help → Open Log Folder** and copy the lines by hand.

## What is left out, and what to check

Before the log lines are copied, WNTB:

- replaces your **commander name** with `<commander>`, in any capitals. It knows the commander EDMC currently has and the one in your
  newest journal;
- replaces your **home folder** (for example `C:\Users\you` or `/home/you`) with `~`.

The version lines never hold a commander name, a system name or a file path. The address that **Report an issue** opens carries only the
title, the versions and the OS line, nothing from your play.

Two things WNTB cannot know, so please look for them yourself before you press **Submit**:

- **Other commander names.** If you play more than one commander, another name could appear in a log line. Replace it by hand.
- **System, station and carrier names.** They are in the log whenever WNTB logged something about them. They are game data, not
  personal, but you may prefer not to show where you were.

You can paste the diagnostics into a text editor first and read them there, then copy again from the editor.

## If something does not work

| What you see | What to do |
|---|---|
| **Report an issue** opens nothing | Your system has no default browser set. Open the [new-issue page](https://github.com/rwharpernc/wayward-nomads-toolbox/issues/new?template=bug_report.yml) yourself and use **Copy diagnostics** to fill the form |
| The form opens but the Environment box is empty | The address was cut off. Press **Copy diagnostics** and paste the first lines into the box |
| *Could not copy to the clipboard* | Another program holds the clipboard, or (Linux) there is no clipboard service. Try again; if it persists, open the log from **EDMC → Help → Open Log Folder** and copy lines by hand |
| The text says `(no WNTB lines found in the log)` | Nothing from WNTB was logged lately. Make the problem happen again, then press **Copy diagnostics** straight away |
| Linux Flatpak: the log is not found | A Flatpak EDMC keeps its log under `~/.var/app/io.edcd.EDMarketConnector/data/EDMarketConnector/logs/`. Attach lines from the file by hand |

The version lines and the OS line are copied even when the log cannot be found.

## Good reports

A report that gets fixed quickly says:

- **what you did**, step by step, and where (the mode, panel or window);
- **what you expected** and **what happened instead**, in your words;
- **whether it happens every time** or only sometimes;
- for a **number that looks wrong**, the number you expected and why. For Colonization, Trade and Powerplay figures, the line of the
  relevant event in your journal helps most (for example the `CarrierStats` line for a fleet carrier). The journal is in the folder EDMC's
  settings show as the Journal directory, and the file is `Journal.<date>.log`.

For ideas and requests rather than bugs, the Issues page is the same place, or find the author in the Wayward Nomads squadron.

## Privacy

**Report an issue** only asks your browser to open a GitHub address, and **Copy diagnostics** only writes to your clipboard. WNTB makes
no connection to GitHub itself, and nothing is filed unless you submit it. It is listed with everything else in
[What goes on the internet](internet-and-privacy.md).
