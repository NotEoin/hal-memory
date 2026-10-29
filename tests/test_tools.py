"""Tests for the memory tools that open vault notes by name."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class NoteNameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.vault = base / "vault"
        (self.vault / "Topics").mkdir(parents=True)
        (self.vault / "Topics" / "Caching.md").write_text("# Caching\nUse Redis.\n")
        self.secret = base / "secret.md"
        self.secret.write_text("# Secret\nnot for the model\n")
        (self.vault / "Topics" / "Linked.md").symlink_to(self.secret)
        cfg = base / "config.toml"
        cfg.write_text(f'[hal]\nvault = "{self.vault}"\n')
        self.saved = {k: os.environ.get(k) for k in ("HAL_CONFIG", "HAL_DATA")}
        os.environ["HAL_CONFIG"] = str(cfg)
        os.environ["HAL_DATA"] = str(base / "data")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def test_note_inside_vault_is_read_by_title_and_by_path(self):
        from halmem import tools

        self.assertIn("Redis", tools.read("Caching")["text"])
        self.assertEqual(tools.read("Topics/Caching")["path"], "Topics/Caching.md")

    def test_note_outside_vault_is_refused(self):
        from halmem import tools

        for name in ("../secret.md", "../secret", str(self.secret), "Topics/../../secret.md"):
            out = tools.read(name)
            self.assertIn("error", out, name)
            self.assertNotIn("text", out, name)
            self.assertIn("not a note inside the vault", out["error"], name)

    def test_symlink_pointing_out_of_the_vault_is_refused(self):
        from halmem import tools

        for name in ("Linked", "Topics/Linked.md"):
            out = tools.read(name)
            self.assertIn("not a note inside the vault", out["error"], name)
            self.assertNotIn("text", out, name)

    def test_append_refuses_a_note_outside_the_vault(self):
        from halmem import tools

        out = tools.append("../secret.md", "injected")
        self.assertIn("error", out)
        self.assertNotIn("injected", self.secret.read_text())
        out = tools.append("Linked", "injected")
        self.assertIn("error", out)
        self.assertNotIn("injected", self.secret.read_text())

    def test_missing_note_reports_no_note_called(self):
        from halmem import tools

        self.assertEqual(tools.read("Nope"), {"error": "no note called Nope"})


if __name__ == "__main__":
    unittest.main()
