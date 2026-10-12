"""
No author credit for an AI assistant anywhere but the Acknowledgements page.

The project's rule (CLAUDE.md): code comments, docs, changelog entries and commit messages carry no co-author line,
"generated with" note or similar credit for an AI assistant; the one place for acknowledgements is `docs/ATTRIBUTIONS.md`.
This scans the working tree for the common credit phrasings, and checks the commit-msg hook that stops them in commit
messages is in the repo. It reads files directly, so it behaves the same on Windows and Linux.
"""
from __future__ import annotations

import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKIP_DIRS = {".git", "dist", "node_modules", "__pycache__", ".claude"}
TEXT_EXTENSIONS = {".py", ".md", ".mjs", ".js", ".json", ".txt", ".toml", ".yml", ".yaml", ".cfg", ".ini"}
# Files that may name the assistant: the acknowledgements, the assistant's own notes file, and the files that explain or
# enforce this rule.
ALLOWED = {
    os.path.join("docs", "ATTRIBUTIONS.md"), "CLAUDE.md", os.path.join("docs", "DEVELOPMENT.md"),
    os.path.join("tests", "test_no_ai_credit.py"), os.path.join(".githooks", "commit-msg"), ".gitignore",
}
CREDIT = re.compile(
    r"co-authored-by:|noreply@anthropic\.com|generated (?:with|by) (?:claude|anthropic|ai\b)|"
    r"(?:written|authored|created|made) (?:with|by) (?:claude|anthropic|ai\b)|ai[- ]generated|🤖", re.IGNORECASE)


class NoAiCreditTests(unittest.TestCase):
    def test_no_credit_lines_in_the_working_tree(self):
        found = []
        for folder, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                if os.path.splitext(name)[1].lower() not in TEXT_EXTENSIONS:
                    continue
                path = os.path.join(folder, name)
                rel = os.path.relpath(path, ROOT)
                if rel in ALLOWED:
                    continue
                with open(path, encoding="utf-8", errors="replace") as handle:
                    for number, line in enumerate(handle, 1):
                        if CREDIT.search(line):
                            found.append(f"{rel}:{number}")
        self.assertEqual(found, [], "AI author credit outside docs/ATTRIBUTIONS.md: " + ", ".join(found))

    def test_the_commit_message_hook_is_in_the_repo(self):
        hook = os.path.join(ROOT, ".githooks", "commit-msg")
        self.assertTrue(os.path.isfile(hook), "run `git config core.hooksPath .githooks` after adding .githooks/commit-msg")
        with open(hook, encoding="utf-8") as handle:
            self.assertIn("co-authored-by", handle.read().lower())


if __name__ == "__main__":
    unittest.main()
