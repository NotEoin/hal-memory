"""Tests for the hal-memory command, setup, the morning brief, the ingest scripts and recall.

Every test uses a throwaway vault, config and home; Ollama is pointed at a closed port
and replaced by fakes, so nothing here touches a real vault or model.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HAL_ENV = ("HAL_VAULT", "HAL_MODEL", "HAL_CHAT_API", "HAL_CHAT_URL", "HAL_ANSWERER", "HAL_UNIVERSITY",
           "HAL_CLAUDE_COMMANDS", "HAL_BIN_DIR", "HAL_OBSIDIAN_KEY_FILE")
QUESTION = "What did I decide about caching for my dissertation?"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.vault = self.base / "vault"
        (self.vault / "Areas" / "Study").mkdir(parents=True)
        (self.vault / "Areas" / "Study" / "Dissertation decisions.md").write_text(
            "- 2026-09-14: Decided to use Redis as the caching layer for the dissertation prototype.\n")
        (self.vault / "Areas" / "Work").mkdir(parents=True)
        (self.vault / "Areas" / "Work" / "Lunch.md").write_text("Lunch with Sam about the house move.\n")
        self.config = self.base / "config.toml"
        self.config.write_text(f'[hal]\nvault = "{self.vault}"\nollama_url = "http://127.0.0.1:9"\n'
                               'embed_model = "embeddinggemma"\n')
        self.saved = {k: os.environ.get(k) for k in HAL_ENV + ("HAL_CONFIG", "HAL_DATA")}
        for k in HAL_ENV:
            os.environ.pop(k, None)
        os.environ["HAL_CONFIG"] = str(self.config)
        os.environ["HAL_DATA"] = str(self.base / "data")
        os.environ["HAL_OBSIDIAN_KEY_FILE"] = str(self.base / "home" / "obsidian_api_key")
        from halmem import llm
        self.llm = llm
        self.real = (llm.embed, llm.chat)

        def offline(*a, **kw):
            raise llm.Unavailable("offline in tests")
        llm.embed = offline

    def tearDown(self):
        self.llm.embed, self.llm.chat = self.real
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def run_cli(self, *args, path_dir=None):
        """Runs bin/hal-memory in a clean environment with a throwaway HOME."""
        env = {k: v for k, v in os.environ.items() if k not in HAL_ENV}
        env.update(HOME=str(self.base / "home"), HAL_CONFIG=str(self.config), HAL_DATA=str(self.base / "data"),
                   HAL_OBSIDIAN_KEY_FILE=str(self.base / "home" / "obsidian_api_key"))
        if path_dir:
            env["PATH"] = f"{path_dir}{os.pathsep}{env['PATH']}"
        return subprocess.run([str(ROOT / "bin" / "hal-memory"), *args], capture_output=True, text=True,
                              env=env, timeout=60)


class RecallTest(Base):
    def test_recall_without_an_index_finds_the_note(self):
        """Regression: a natural-language question found nothing until the index was built."""
        from halmem import search
        self.assertEqual(search.terms(QUESTION), ["decide", "caching", "dissertation"])
        out = search.recall(QUESTION, no_llm=True)
        self.assertEqual(out["notes"], ["Dissertation decisions"])
        self.assertIn("Redis", out["answer"])
        self.assertEqual([h["note"] for h in search.search("caching dissertation")], ["Dissertation decisions"])

    def test_recall_answers_in_one_small_model_call(self):
        from halmem import search
        calls = []
        self.llm.chat = lambda system, user, **kw: calls.append(user) or "You chose Redis."
        out = search.recall(QUESTION)
        self.assertEqual(len(calls), 1)
        self.assertIn("Redis", calls[0])
        self.assertLessEqual(len(calls[0]), search.CONTEXT + len(QUESTION) + 40)
        self.assertIn("[[Dissertation decisions]]", out["answer"])   # sources are always cited

    def test_stale_index_still_finds_new_notes(self):
        from halmem import search
        (self.vault / "Areas" / "Study" / "Dissertation decisions.md").rename(self.base / "later.md")
        self.llm.embed = lambda texts, timeout=120: [[1.0, 0.0] for _ in texts]
        search.update_index()                       # indexes Lunch only
        (self.base / "later.md").rename(self.vault / "Areas" / "Study" / "Dissertation decisions.md")
        self.assertIn("Dissertation decisions", search.recall(QUESTION, no_llm=True)["notes"])

    def test_claude_answerer_uses_claude_p(self):
        from halmem import search
        fake = self.base / "claude"
        fake.write_text('#!/bin/sh\necho "From [[Dissertation decisions]]: Redis. args=$1"\n')
        fake.chmod(0o755)
        os.environ["HAL_CLAUDE_COMMAND"] = str(fake)
        try:
            out = search.recall(QUESTION, who="claude")
        finally:
            os.environ.pop("HAL_CLAUDE_COMMAND")
        self.assertIn("args=-p", out["answer"])

    def test_ask_command_no_llm(self):
        r = self.run_cli("ask", "--no-llm", QUESTION)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("[[Dissertation decisions]]", r.stdout)
        self.assertIn("Redis", r.stdout)


class ModelClientTest(Base):
    def test_openai_backend_follows_the_launcher(self):
        sent = {}

        def post(url, payload, timeout):
            sent.update(url=url, payload=payload)
            return {"choices": [{"message": {"content": "ok"}}]}
        real_post = self.llm._post
        self.llm._post = post
        os.environ.update(HAL_CHAT_API="openai", HAL_CHAT_URL="http://127.0.0.1:8080", HAL_MODEL="hal-gpu")
        try:
            self.assertEqual(self.real[1]("sys", "hi"), "ok")
        finally:
            self.llm._post = real_post
        self.assertEqual(sent["url"], "http://127.0.0.1:8080/v1/chat/completions")
        self.assertEqual(sent["payload"]["model"], "hal-gpu")
        self.assertFalse(sent["payload"]["chat_template_kwargs"]["enable_thinking"])


class CommandTest(Base):
    def test_help_lists_subcommands_and_tools(self):
        r = self.run_cli("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for word in ("ask QUESTION", "index [--rebuild]", "brief [--print-only]", "summarize", "import prepare",
                     "register-repos", "setup [--check]", "obsidian-key", "remember"):
            self.assertIn(word, r.stdout)

    def test_tool_passthrough(self):
        r = self.run_cli("search", "query=caching dissertation")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)[0]["note"], "Dissertation decisions")

    def test_unknown_import_step_fails(self):
        self.assertEqual(self.run_cli("import", "nonsense-step").returncode, 2)

    def test_import_stage_copies_into_staging(self):
        old = self.base / "OldVault"
        (old / "Course").mkdir(parents=True)
        (old / "Course" / "Week 1.md").write_text("# Week 1\n")
        r = self.run_cli("import", "stage", str(old))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        staged = self.vault / "_Import-Staging" / "OldVault"
        self.assertTrue((staged / "Course" / "Week 1.md").exists())
        self.assertTrue((staged / "IMPORT-MANIFEST.md").exists())

    def test_ingest_scripts_are_present_and_executable(self):
        names = ["extract-pdfs.sh", "extract-docx.sh", "extract-pptx.sh", "extract-html.sh",
                 "prepare-import.sh", "import-vault.sh", "register-repos.sh"]
        for name in names:
            p = ROOT / "ingest" / name
            self.assertTrue(p.exists(), name)
            self.assertTrue(p.stat().st_mode & stat.S_IXUSR, name)
            self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0, name)
            self.assertNotIn("HAL_ROOT", p.read_text(), name)
        self.assertTrue(os.access(ROOT / "bin" / "hal-memory", os.X_OK))


class BriefTest(Base):
    def setUp(self):
        super().setUp()
        (self.vault / "Areas" / "Work" / "Projects").mkdir()
        (self.vault / "Areas" / "Work" / "Projects" / "Thesis.md").write_text(
            "---\ntype: project\nstatus: active\n---\n# Thesis\n- [ ] send draft 2026-10-01\n- [ ] book room\n")
        daily = self.vault / "Calendar" / "Daily"
        daily.mkdir(parents=True)
        (daily / "2026-10-09.md").write_text("# 9 Oct\n\n## Done Today\n- fixed the cache bug\n- [x] gym\n")

    def test_brief_without_a_model_writes_once_into_the_daily_note(self):
        from halmem import brief
        out = brief.brief("2026-10-10", no_llm=True)
        self.assertEqual((out["due"], out["open"], out["projects"], out["model"]), (1, 1, 1, "none"))
        note = self.vault / "Calendar" / "Daily" / "2026-10-10.md"
        self.assertIn("send draft", note.read_text())
        self.assertIn("fixed the cache bug", out["brief"])
        again = brief.brief("2026-10-10", no_llm=True)          # its own tasks are not counted again
        self.assertEqual((again["due"], again["open"]), (1, 1))
        self.assertEqual(note.read_text().count(brief.START), 1)

    def test_brief_print_only_leaves_the_vault_alone(self):
        r = self.run_cli("brief", "--no-llm", "--print-only", "--date", "2026-10-10")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("book room", r.stdout)
        self.assertFalse((self.vault / "Calendar" / "Daily" / "2026-10-10.md").exists())


class SetupTest(Base):
    def setUp(self):
        super().setUp()
        self.fakes = self.base / "fakebin"
        self.fakes.mkdir()
        self.pulls = self.base / "pulls.log"
        (self.fakes / "ollama").write_text(
            f'#!/bin/sh\nif [ "$1" = list ]; then echo "NAME ID SIZE"; echo "qwen3.5:2b x 1GB"; '
            f'else echo "$@" >> "{self.pulls}"; fi\n')
        (self.fakes / "hal-hub").write_text("#!/bin/sh\n")
        for f in self.fakes.iterdir():
            f.chmod(0o755)
        self.commands = self.base / "commands"
        self.commands.mkdir()
        (self.commands / "ask.md").write_text("my own ask\n")
        (self.commands / "jobs.md").write_text("someone else's command\n")
        self.mcp = self.vault / ".mcp.json"
        self.mcp.write_text(json.dumps({"mcpServers": {
            "obsidian": {"command": "uvx", "args": ["mcp-obsidian"], "env": {"OBSIDIAN_PORT": "1"}},
            "hal": {"command": "uv", "args": ["run", "--with", "mcp", "/old/Hal/hal-mcp.py"]},
            "other": {"command": "x"}}}))

    def setup_cli(self, *extra):
        return self.run_cli("setup", "--commands-dir", str(self.commands), "--bin-dir", str(self.base / "bin"),
                            *extra, path_dir=self.fakes)

    def test_check_changes_nothing(self):
        before = self.mcp.read_text()
        r = self.setup_cli("--check")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("remove hal", r.stdout)
        self.assertEqual(self.mcp.read_text(), before)
        self.assertFalse((self.commands / "load-context.md").exists())
        self.assertFalse(self.pulls.exists())

    def test_setup_links_commands_merges_mcp_and_pulls(self):
        r = self.setup_cli()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        servers = json.loads(self.mcp.read_text())["mcpServers"]
        self.assertNotIn("hal", servers)
        self.assertEqual(servers["hal-hub"], {"command": str(self.fakes / "hal-hub"), "args": ["mcp"]})
        self.assertEqual(servers["obsidian"]["env"], {"OBSIDIAN_PORT": "1"})    # the user's own entry is kept
        self.assertEqual(servers["other"], {"command": "x"})
        self.assertTrue((self.vault / ".mcp.json.bak").exists())
        ask = self.commands / "ask.md"
        self.assertTrue(ask.is_symlink())
        self.assertEqual(ask.resolve(), (ROOT / "claude-commands" / "ask.md").resolve())
        self.assertEqual((self.commands / "ask.md.bak").read_text(), "my own ask\n")
        self.assertEqual((self.commands / "jobs.md").read_text(), "someone else's command\n")
        self.assertTrue((self.base / "bin" / "hal-memory").is_symlink())
        self.assertIn("pull embeddinggemma", self.pulls.read_text())
        # A second run finds nothing left to change.
        mcp = self.mcp.read_text()
        r = self.setup_cli("--no-pull")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.mcp.read_text(), mcp)
        self.assertFalse((self.commands / "ask.md.bak.1").exists())

    def test_first_install_creates_the_vault(self):
        from halmem import install
        root = self.base / "new-vault"
        self.assertEqual(install.make_vault(root, check=True), 1)
        self.assertFalse(root.exists())
        self.assertEqual(install.make_vault(root, check=False), 0)
        self.assertTrue((root / "+Inbox").is_dir())
        self.assertEqual(install.make_vault(root, check=False), 0)

    def test_merge_adds_obsidian_when_missing(self):
        from halmem import install
        cfg = {}
        changes = install.merge_mcp(cfg, "/usr/bin/true")
        self.assertEqual(cfg["mcpServers"]["obsidian"]["env"]["OBSIDIAN_API_KEY"], "${OBSIDIAN_API_KEY}")
        self.assertEqual(len(changes), 2)
        self.assertEqual(install.merge_mcp(cfg, "/usr/bin/true"), [])

    def test_obsidian_key_is_private(self):
        r = self.run_cli("obsidian-key", "secret-test-key")
        self.assertEqual(r.returncode, 0, r.stderr)
        key = self.base / "home" / "obsidian_api_key"
        self.assertEqual(key.read_text(), "secret-test-key")
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
