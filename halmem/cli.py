"""hal-memory's subcommands; the hal launcher delegates `hal ask`, `hal index`, `hal brief` and
`hal summarize` to them.

    hal-memory ask QUESTION [--k N] [--show-context] [--no-llm] [--answerer local|claude] [--model M]
    hal-memory index [--rebuild] [--limit N]
    hal-memory brief [--print-only] [--no-llm] [--date YYYY-MM-DD] [--model M]
    hal-memory summarize [REPORT] [--course C] [--limit N] [--interactive] [--include-maybe] [--model M] [--mock]
    hal-memory import stage OLD_VAULT [--dry-run]       copy an old vault into _Import-Staging
    hal-memory import prepare [DIR] [--ocr] [--force]   extract text from every document, write SLIDES-REPORT.md
    hal-memory import extract pdf|docx|pptx|html [DIR] [--ocr] [--force]
    hal-memory register-repos [PATH ...] [--github URL [NAME]] [--depth N] [--refresh]
    hal-memory setup [--check] [--commands-dir DIR] [--bin-dir DIR] [--no-pull]
    hal-memory obsidian-key KEY
    hal-memory TOOL [key=value ...]                       run any tool in hal-module.toml
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .config import settings, vault

PACKAGE = Path(__file__).resolve().parent
INGEST = PACKAGE / "ingest"
EXTRACTORS = {"pdf": "extract-pdfs.sh", "docx": "extract-docx.sh", "pptx": "extract-pptx.sh",
              "html": "extract-html.sh"}


def pipeline_vault() -> Path:
    """Returns the vault for import, summarize, register-repos and brief: HAL_VAULT, else [hal].vault."""
    return Path(os.environ.get("HAL_VAULT") or vault()).expanduser()


def _script(name: str, args: list[str]) -> int:
    env = {**os.environ, "HAL_VAULT": str(pipeline_vault()),
           "HAL_UNIVERSITY": os.environ.get("HAL_UNIVERSITY") or settings()["university"],
           "PYTHONPATH": os.pathsep.join(filter(None, [str(PACKAGE.parent), os.environ.get("PYTHONPATH")]))}
    try:
        return subprocess.call(["bash", str(INGEST / name), *args], env=env)
    except KeyboardInterrupt:
        return 130


def ask(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="hal-memory ask", description="Answer a question from the vault, with citations.")
    ap.add_argument("question", nargs="+")
    ap.add_argument("--k", type=int, default=6, help="notes to retrieve (default 6)")
    ap.add_argument("--show-context", action="store_true", help="also list the notes used and their scores")
    ap.add_argument("--no-llm", "--mock", action="store_true", help="show the matching notes only, no model call")
    ap.add_argument("--answerer", choices=("local", "ollama", "claude"), help="who writes the answer")
    ap.add_argument("--model", help="chat model for the local answerer")
    a = ap.parse_args(argv)
    from . import llm, search
    question = " ".join(a.question)
    try:
        out = search.recall(question, a.k, no_llm=a.no_llm, who=a.answerer, model=a.model)
    except llm.Unavailable as e:
        print(f"hal-memory ask: {e}", file=sys.stderr)
        return 1
    if a.show_context and not a.no_llm:
        for h in out["passages"]:
            score = f"  score={h['score']:.3f}" if "score" in h else "  (keyword match)"
            print(f"  [[{h['note']}]]  {h['path']}{score}")
        print()
    print(out["answer"])
    return 0


def index(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="hal-memory index", description="Update the semantic search index.")
    ap.add_argument("--rebuild", action="store_true", help="forget every embedding and index the vault again")
    ap.add_argument("--limit", type=int, help="most notes to embed this run")
    a = ap.parse_args(argv)
    from . import llm, search
    if a.rebuild:
        search.clear_index()
    try:
        out = search.update_index(a.limit, progress=lambda d, n: print(f"  {d}/{n} notes", flush=True))
    except llm.Unavailable as e:
        print(f"hal-memory index: {e}\n  is the embedding model pulled? hal-memory setup --check", file=sys.stderr)
        return 1
    print(f"embedded {out['embedded']} note(s), {out['waiting']} waiting, {out['removed']} removed")
    return 0


def brief(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="hal-memory brief", description="Write today's morning brief into the daily note.")
    ap.add_argument("--date", default="", help="YYYY-MM-DD (default today)")
    ap.add_argument("--print-only", action="store_true", help="print it without touching the daily note")
    ap.add_argument("--no-llm", "--mock", action="store_true", help="the gathered facts only, no model call")
    ap.add_argument("--model", help="chat model (default HAL_MODEL or [hal].chat_model)")
    a = ap.parse_args(argv)
    from . import brief as briefing
    out = briefing.brief(a.date, no_llm=a.no_llm, print_only=a.print_only, model=a.model, root=pipeline_vault())
    print(out["brief"])
    if "model_error" in out:
        print(f"\n(model unavailable, wrote the plain brief: {out['model_error']})", file=sys.stderr)
    if "path" in out:
        print(f"\nwritten into {out['path']}")
    print(f"{out['due']} due or overdue, {out['open']} open, {out['projects']} active project(s)")
    return 0


def summarize(argv: list[str]) -> int:
    from . import summarize as runner
    return runner.main(argv) or 0


def import_(argv: list[str]) -> int:
    usage = ("usage: hal-memory import stage OLD_VAULT [--dry-run]\n"
             "       hal-memory import prepare [DIR] [--ocr] [--force]\n"
             "       hal-memory import extract pdf|docx|pptx|html [DIR] [--ocr] [--force]")
    step, rest = (argv[0], argv[1:]) if argv else ("", [])
    if step == "stage":
        return _script("import-vault.sh", rest)
    if step == "prepare":
        return _script("prepare-import.sh", rest)
    if step == "extract" and rest and rest[0] in EXTRACTORS:
        return _script(EXTRACTORS[rest[0]], rest[1:])
    if step and not step.startswith("-") and Path(step).expanduser().is_dir():
        return _script("import-vault.sh", argv)       # `hal-memory import OLD_VAULT` stages it
    print(usage, file=sys.stderr if step not in ("-h", "--help") else sys.stdout)
    return 0 if step in ("-h", "--help") else 2


def register_repos(argv: list[str]) -> int:
    return _script("register-repos.sh", argv)


def setup(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="hal-memory setup", description="Install or check hal-memory's commands and tools.")
    ap.add_argument("--check", action="store_true", help="only report what is missing")
    ap.add_argument("--commands-dir", help="where Claude Code slash commands go (default ~/.claude/commands)")
    ap.add_argument("--bin-dir", help="where to link the hal-memory command (default ~/.local/bin)")
    ap.add_argument("--no-pull", action="store_true", help="skip checking and pulling the embedding model")
    a = ap.parse_args(argv)
    from . import install
    return install.run(a.check, a.commands_dir, a.bin_dir, pull=not a.no_pull)


def obsidian_key(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0].startswith("-"):
        print("usage: hal-memory obsidian-key KEY", file=sys.stderr)
        return 2
    from . import install
    print(f"saved the Obsidian API key to {install.save_key(argv[0])}")
    return 0


COMMANDS = {"ask": ask, "index": index, "brief": brief, "summarize": summarize, "import": import_,
            "register-repos": register_repos, "setup": setup, "obsidian-key": obsidian_key}


def run(argv: list[str]) -> int:
    """Runs one subcommand; argv[0] is its name."""
    return COMMANDS[argv[0]](argv[1:])
