"""Opens the real Notes window and the Notes panel row (plugin/notes_window.py, plugin/notes_panel.py) with EDMC stubbed, and checks
that notes can be written, found, changed and deleted, that the panel row follows the system and the commander, and that the long text
a note can hold never widens the panel. Run by test_notes_window_smoke.py in a subprocess so the stand-ins never leak into other
tests. Exits 0 if everything holds, 1 if not, 77 if Tk is unavailable."""
import os
import sys
import tempfile
import types
from unittest import mock

repo = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, repo)
import tkinter as tk


class Any(types.ModuleType):
    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return mock.MagicMock()


for n in ("monitor", "plug", "EDMCLogging", "l10n", "killswitch", "requests", "win32api", "win32con", "win32gui",
          "win32process", "win32clipboard", "pywintypes", "psutil", "ttkHyperlinkLabel"):
    sys.modules[n] = Any(n)
nbmod = Any("myNotebook")
nbmod.Frame, nbmod.Label, nbmod.Button, nbmod.Checkbutton = tk.Frame, tk.Label, tk.Button, tk.Checkbutton
sys.modules["myNotebook"] = nbmod
theme = Any("theme")
theme.theme = mock.MagicMock()
theme.theme.active = None
theme.theme.THEME_DEFAULT = 0
sys.modules["theme"] = theme
saved = {}


class Cfg:
    default_journal_dir = ""

    def get_str(self, key, default=""):
        return saved.get(key, default) or ""

    def get_bool(self, key, default=False):
        return saved.get(key, default)

    def get_int(self, key, default=0):
        return default

    def get(self, key, default=None):
        return saved.get(key, default)

    def set(self, key, value):
        saved[key] = value


cfgmod = types.ModuleType("config")
cfgmod.appname = "EDMarketConnector"
cfgmod.config = Cfg()
cfgmod.user_agent = "WNTB-test"
cfgmod.appversion = lambda: "5.13.0"
sys.modules["config"] = cfgmod

try:
    root = tk.Tk()
except tk.TclError:
    print("no display available")
    sys.exit(77)
root.withdraw()

from plugin import notes_data, notes_panel, notes_window  # noqa: E402

problems = []


def check(condition, message):
    if not condition:
        problems.append(message)


def widgets(widget, kind):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, kind):
            found.append(child)
        found += widgets(child, kind)
    return found


def pump():
    root.update_idletasks()
    root.update()


folder = tempfile.mkdtemp()
panel = notes_panel.NotesController()      # a fresh controller; it listens to the shared book
book = notes_panel.book
book.load(folder)

# --- the panel row ----------------------------------------------------------------------------------------------------------------------
saved["wntb_notes_collapsed"] = False      # open, so its widgets count towards the panel's width
host = tk.Frame(root)
host.pack()
panel.build_panel(host)
pump()
check(panel.summary()[0] == "Log in to use notes.", f"before a commander: {panel.summary()}")

panel.handle_event({"event": "LoadGame"}, "Bocheaux", "Sol", None, {})
check(panel.summary() == ("No notes for Sol.", ""), f"a commander and a system: {panel.summary()}")
check(panel._summary_var.get() == "No notes for Sol.", "the label follows the summary")

panel._entry_var.set("  Rings are lovely  ")
panel._add_quick()
check(book.count() == 1 and book.all()[0].system == "Sol" and book.all()[0].text == "Rings are lovely", f"quick add: {book.all()}")
check(panel._entry_var.get() == "", "the quick-add box is emptied")
check(panel.summary()[0].startswith("1 note for Sol. Newest: Rings are lovely"), f"summary after an add: {panel.summary()}")
check(panel.summary()[1] == "- 1 here", "the folded title says how many")

panel._entry_var.set("   ")
panel._add_quick()
check(book.count() == 1 and "text" in panel._summary_var.get(), f"an empty quick note is refused with a reason: {panel._summary_var.get()!r}")

panel.handle_event({"event": "FSDJump", "StarSystem": "Colonia"}, "Bocheaux", "Colonia", None, {})
check(panel.summary() == ("No notes for Colonia.", ""), f"jumping changes the system: {panel.summary()}")
panel.dashboard_status({"BodyName": "Colonia 3 a"})
check(panel.context() == ("Colonia", "Colonia 3 a"), f"the body comes from Status.json: {panel.context()}")
panel.dashboard_status({})
check(panel.context() == ("Colonia", ""), "no BodyName in Status.json, no body")
panel.handle_event({"event": "Music"}, "Bocheaux", None, None, {})
check(panel.context()[0] == "Colonia", "an event that does not know the system keeps the last one")

panel.handle_event({"event": "LoadGame"}, "Other Cmdr", "Sol", None, {})
check(panel.summary() == ("No notes for Sol.", ""), f"another commander does not see them: {panel.summary()}")
panel.handle_event({"event": "LoadGame"}, "BOCHEAUX", "Sol", None, {})
check(panel.summary()[0].startswith("1 note for Sol"), f"the first commander's notes are back: {panel.summary()}")

# The panel never gets wider because of what is typed or saved.
long_text = "word " * 400
book.add("Sol", "", long_text.strip()[:notes_data.MAX_TEXT])
book.add("S" * 90, "", "x")
panel.handle_event({"event": "Location", "StarSystem": "S" * 90}, "Bocheaux", "S" * 90, None, {})
pump()
text, _suffix = panel.summary()
check(len(text) <= 140, f"the summary line stays short: {len(text)} characters")
check("S" * 50 not in text, "a very long system name is clipped in the panel")
entry = widgets(host, tk.Entry)[0]
check(int(entry.cget("width")) <= notes_panel._ENTRY_WIDTH and entry.winfo_reqwidth() <= notes_panel._ENTRY_MAX_PX,
      f"the quick-add box has a fixed width, no wider than {notes_panel._ENTRY_MAX_PX} px in any font: {entry.winfo_reqwidth()}")
# EDMC sizes its window to the widest row of every plugin: with a very long system name and a note at the limit shown, the Notes
# section must still be no wider than the main panel is by default (216 px at the default fonts).
check(host.winfo_reqwidth() <= 216, f"the open Notes section asks for {host.winfo_reqwidth()} px, wider than the main panel")

# --- the window ---------------------------------------------------------------------------------------------------------------------------
panel.handle_event({"event": "Location", "StarSystem": "Sol"}, "Bocheaux", "Sol", None, {})
panel.dashboard_status({"BodyName": "Earth"})
notes_window.show(root, book, panel.context)
win = notes_window._window
pump()
check(win is not None and win.alive, "the window opens")
check(len(win._table) == book.count(), f"every note is listed: {len(win._table)} of {book.count()}")
check(win._system.get() == "Sol" and win._body.get() == "Earth", "a new note starts with where you are")

win._text.insert("1.0", "A note written in the window")
win._save()
check(book.count() == 4 and any(n.text == "A note written in the window" and n.body == "Earth" for n in book.all()), "saving adds a note")
check(len(win._table) == 4, "the table shows the new note")
check(win._editing is not None, "after a save the note stays in the editor")

win._text.delete("1.0", "end")
win._save()
check(book.count() == 4 and "text" in win._shell._status.cget("text"), f"an empty note is refused: {win._shell._status.cget('text')!r}")

# search and the "only here" filter
win._query.set("window")
pump()
check(len(win._table) == 1, f"search narrows the table: {len(win._table)}")
win._query.set("")
win._here_only.set(True)
win._fill_table()
check(len(win._table) == 3, f"only the system I am in: {len(win._table)}")   # Sol has 3 of the 4 notes
win._here_only.set(False)
win._fill_table()

# select a note, change it, delete it
target = next(n for n in book.all() if n.text == "Rings are lovely")
win._table.select(target.id, notify=True)
check(win._text.get("1.0", "end").strip() == "Rings are lovely" and win._editing == target.id, "selecting loads the note into the editor")
win._text.delete("1.0", "end")
win._text.insert("1.0", "Rings are lovely and wide")
win._save()
check(book.get(target.id).text == "Rings are lovely and wide", "saving a selected note changes it")
check(book.count() == 4, "changing a note does not add one")

win._delete()
check(book.get(target.id) is not None and "again" in win._shell._status.cget("text"), "the first press of Delete only asks")
win._delete()
check(book.get(target.id) is None and book.count() == 3, "the second press deletes")
check(win._editing is None, "the editor is cleared after a delete")
win._delete()
check(book.count() == 3, "Delete with nothing selected does nothing")

win._new()
win._text.insert("1.0", "second thoughts")
win._system.set("")
win._save()
check("system" in win._shell._status.cget("text") and book.count() == 3, "a note without a system is refused")

# a commander switch refreshes the open window; closing removes its listener
panel.handle_event({"event": "LoadGame"}, "Other Cmdr", "Sol", None, {})
pump()
check(len(win._table) == 0 and "Other Cmdr" in win._shell._subtitle.cget("text"), "another commander's window starts empty")
listeners = len(book._listeners)
notes_window.close()
pump()
check(not win.alive and len(book._listeners) == listeners - 1, "closing the window removes its listener")
notes_window.show(root, book, panel.context)
pump()
check(notes_window._window.alive and notes_window._window is not win, "it can be opened again")
notes_window.close()

# the file holds each commander's notes under a key, never in a file name
check(sorted(os.listdir(folder)) == [notes_data.STATE_FILENAME], f"one data file: {os.listdir(folder)}")

if problems:
    print("PROBLEMS:", len(problems))
    for line in problems:
        print(" -", line)
    sys.exit(1)
print("NOTES OK")
