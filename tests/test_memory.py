"""Tests for frontmatter editing, the wikilink pass and capture, on a throwaway vault."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "vault" / "People").mkdir(parents=True)
        (base / "vault" / "People" / "Ada Lovelace.md").write_text("---\naliases: [Lovelace, Ada]\n---\n# Ada\n")
        (base / "vault" / "Topics").mkdir()
        (base / "vault" / "Topics" / "Analytical Engine.md").write_text("# Engine\n")
        cfg = base / "config.toml"
        cfg.write_text(f'[hal]\nvault = "{base / "vault"}"\n')
        os.environ["HAL_CONFIG"] = str(cfg)
        os.environ["HAL_DATA"] = str(base / "data")
        from halmem import vault
        self.vault = vault

    def tearDown(self):
        self.tmp.cleanup()

    def test_set_fields_keeps_other_keys(self):
        text = "---\ntitle: x\ntags:\n  - a\n  - b\nother: keep\n---\nBody\n"
        out = self.vault.set_fields(text, {"tags": ["c"], "hal": "ok"})
        self.assertIn("other: keep", out)
        self.assertEqual(self.vault.fields(out)["tags"], ["c"])
        self.assertTrue(out.endswith("Body\n"))

    def test_linker_links_first_mention_and_skips_code(self):
        from halmem.linker import Linker
        body = "Lovelace wrote about the analytical engine. Lovelace again. Ada too.\n```\nLovelace in code\n```\n"
        out, n = Linker().link_text(body, "note", 10)
        self.assertEqual(n, 2)
        self.assertIn("[[Ada Lovelace|Lovelace]] wrote", out)
        self.assertIn("[[Analytical Engine|analytical engine]]", out)
        self.assertIn("Lovelace again", out)
        self.assertIn("Lovelace in code", out)
        # Names under four letters are never linked: too many false matches.
        self.assertIn("Ada too", out)

    def test_remember_writes_to_inbox(self):
        from halmem import capture
        p = capture.remember("Buy milk", "milk")
        self.assertEqual(p.parent.name, "+Inbox")
        self.assertEqual(self.vault.fields(p.read_text())["hal"], "inbox")

    def test_paths_cannot_escape_the_vault(self):
        with self.assertRaises(ValueError):
            self.vault.inside(Path("../outside.md"))

    def test_empty_notes_count_as_indexed(self):
        from halmem import search
        search.llm.embed = lambda texts, timeout=120: [[1.0, 0.0] for _ in texts]
        (Path(self.tmp.name) / "vault" / "Empty.md").write_text("---\ntags: []\n---\n")
        self.assertEqual(search.update_index()["waiting"], 0)
        self.assertEqual(search.update_index()["embedded"], 0)

    def test_facts_are_not_duplicated(self):
        from halmem import capture
        self.assertEqual(capture.add_fact("Prefers tea"), "added")
        self.assertEqual(capture.add_fact("prefers tea"), "already known")


if __name__ == "__main__":
    unittest.main()
