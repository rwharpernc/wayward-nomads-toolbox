# Notes for Claude

This repo is developed on two machines, one Windows and one Linux, and tested natively on each. Git is the
only link between them.

- Read `docs/STATUS.md` first: which branch is which, what is being tested, and the working rules for now.
- Check the session's `Platform` before assuming which machine you are on.
- Say which platform a result came from. A pass on one OS says nothing about the other.
- Keep OS-specific code behind the existing platform helpers; don't add OS-only calls elsewhere.
- After a change that touches platform behavior, note what still needs checking on the other OS.
- `git pull --rebase` before starting and push when done. Don't commit machine-specific paths or logs.
- Setup and testing notes live in `docs/`.
- Files are LF on both OSes (`.gitattributes`, `.editorconfig`, `tests/test_line_endings.py`). Write LF; if Git prints a
  "CRLF will be replaced by LF" warning, convert the file rather than ignoring it.
- No author credit for an AI assistant anywhere: no co-author lines or "generated with" notes in commit messages, code comments,
  docs or the changelog. The one place for acknowledgements is `docs/ATTRIBUTIONS.md`. `.githooks/commit-msg` rejects such lines
  in commit messages and `tests/test_no_ai_credit.py` scans the files; on a new machine run `git config core.hooksPath .githooks`.
- Everything saved about play is per commander, never shared (`plugin/commander_data.py`, `tests/test_data_files_per_commander.py`); never put a commander name in a file name. See `docs/DEVELOPMENT.md`.
