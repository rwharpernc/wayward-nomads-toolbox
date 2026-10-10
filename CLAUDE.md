# Notes for Claude

This repo is developed on two machines, one Windows and one Linux, and tested natively on each. Git is the
only link between them.

- Check the session's `Platform` before assuming which machine you are on.
- Say which platform a result came from. A pass on one OS says nothing about the other.
- Keep OS-specific code behind the existing platform helpers; don't add OS-only calls elsewhere.
- After a change that touches platform behaviour, note what still needs checking on the other OS.
- `git pull --rebase` before starting and push when done. Don't commit machine-specific paths or logs.
- Setup and testing notes live in `docs/`.
- Everything saved about play is per commander, never shared (`plugin/commander_data.py`, `tests/test_data_files_per_commander.py`); never put a commander name in a file name. See `docs/DEVELOPMENT.md`.
