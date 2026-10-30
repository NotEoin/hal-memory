"""`hal-memory setup`: skills, document tools, the embedding model and the vault's MCP servers.

Safe to re-run; with check=True it only reports. Nothing here uses sudo: missing
system packages are reported with the command that installs them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import skillsinstall
from .config import shared, vault

ROOT = Path(__file__).resolve().parents[1]
OLLAMA_LIST_TIMEOUT = 30  # seconds; `ollama list` answers at once when the server is up
OLLAMA_PULL_TIMEOUT = 3600  # seconds; an embedding model is under 1 GB
APT = {
    "pdftotext": "poppler-utils",
    "pdftoppm": "poppler-utils",
    "tesseract": "tesseract-ocr",
    "pandoc": "pandoc",
}
PIP = {"fitz": "pymupdf", "docx": "python-docx", "pptx": "python-pptx"}
OBSIDIAN = {
    "command": "uvx",
    "args": ["mcp-obsidian"],
    "env": {
        "OBSIDIAN_API_KEY": "${OBSIDIAN_API_KEY}",
        "OBSIDIAN_HOST": "127.0.0.1",
        "OBSIDIAN_PORT": "27124",
    },
}


def say(kind: str, text: str) -> None:
    print(f"  {kind:6} {text}", flush=True)


def key_file() -> Path:
    """Returns where the Obsidian Local REST API key is kept; HAL_OBSIDIAN_KEY_FILE overrides it."""
    return Path(
        os.environ.get("HAL_OBSIDIAN_KEY_FILE", "~/.config/hal/obsidian_api_key")
    ).expanduser()


def save_key(key: str) -> Path:
    """Stores the Obsidian API key readable by the owner only."""
    p = key_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key.strip())
    p.chmod(0o600)
    return p


def check_tools() -> int:
    """Reports missing document tools with the commands that install them."""
    apt = sorted({pkg for tool, pkg in APT.items() if not shutil.which(tool)})
    pip = sorted(pkg for mod, pkg in PIP.items() if not _importable(mod))
    if apt:
        say("todo", "install document tools: sudo apt-get install " + " ".join(apt))
    if pip:
        say(
            "note",
            "optional Python extractors (PPTX needs python-pptx): pip install --user "
            + " ".join(pip),
        )
    if not apt:
        say("ok", "pdftotext, tesseract and pandoc are installed")
    for tool, why in (
        ("uvx", "the obsidian MCP server"),
        ("claude", 'answerer = "claude" and the slash commands'),
    ):
        if not shutil.which(tool):
            say("note", f"{tool} is not on the PATH (needed for {why})")
    return len(apt)


def _importable(module: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def embed_model(check: bool) -> int:
    """Pulls the configured embedding model into Ollama if it is missing."""
    model = shared()["embed_model"]
    if not shutil.which("ollama"):
        say("todo", f"install Ollama (https://ollama.com), then: ollama pull {model}")
        return 1
    env = {**os.environ, "OLLAMA_HOST": shared()["ollama_url"]}
    try:
        r = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=OLLAMA_LIST_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        say(
            "todo",
            f"Ollama did not answer in {OLLAMA_LIST_TIMEOUT}s; start it, then: ollama pull {model}",
        )
        return 1
    if r.returncode != 0:
        say("todo", f"start Ollama (ollama serve), then: ollama pull {model}")
        return 1
    names = {line.split()[0] for line in r.stdout.splitlines()[1:] if line.strip()}
    if model in names or f"{model}:latest" in names:
        say("ok", f"embedding model {model} is pulled")
        return 0
    if check:
        say("todo", f"ollama pull {model}")
        return 1
    say("pull", model)
    try:
        pulled = subprocess.run(
            ["ollama", "pull", model], env=env, check=False, timeout=OLLAMA_PULL_TIMEOUT
        ).returncode
    except subprocess.TimeoutExpired:
        pulled = 1
    if pulled != 0:
        say("warn", f"could not pull {model}; search falls back to keywords until it is")
        return 1
    return 0


def hub_command() -> str | None:
    """Returns the hal-hub launcher: the one on the PATH, else the ecosystem copy beside this module."""
    found = shutil.which("hal-hub")
    if found:
        return found
    local = ROOT.parent.parent / "core" / "hal-hub" / "bin" / "hal-hub"
    return str(local) if local.exists() else None


def merge_mcp(cfg: dict, hub: str | None) -> list[str]:
    """Updates an .mcp.json document in place and returns what changed.

    Adds obsidian if missing, points hal-hub at its launcher, and drops the old
    `hal` server that ran hal-mcp.py. Other servers are left alone.
    """
    servers = cfg.setdefault("mcpServers", {})
    changes = []
    if "obsidian" not in servers:
        servers["obsidian"] = json.loads(json.dumps(OBSIDIAN))
        changes.append("add obsidian")
    current = servers.get("hal-hub", {})
    if hub and not (
        current.get("command")
        and shutil.which(current["command"])
        and current.get("args") == ["mcp"]
    ):
        servers["hal-hub"] = {**current, "command": hub, "args": ["mcp"]}
        changes.append(f"set hal-hub to {hub}")
    old = servers.get("hal")
    if isinstance(old, dict) and any(
        "hal-mcp.py" in str(a) for a in [old.get("command", ""), *old.get("args", [])]
    ):
        del servers["hal"]
        changes.append("remove hal (hal-mcp.py, replaced by hal-hub)")
    return changes


def mcp_file(path: Path, check: bool) -> int:
    """Merges the vault's .mcp.json, keeping a .bak of the previous version."""
    if not path.parent.is_dir():
        say("warn", f"no vault at {path.parent}; set [hal].vault in the config")
        return 1
    try:
        cfg = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, json.JSONDecodeError) as e:
        say("warn", f"{path} is not valid JSON ({e}); fix it by hand")
        return 1
    hub = hub_command()
    if not hub:
        say("warn", "hal-hub not found: link core/hal-hub/bin/hal-hub into ~/.local/bin and re-run")
    changes = merge_mcp(cfg, hub)
    for c in changes:
        say("todo" if check else "mcp", f"{path}: {c}")
    if not changes:
        say("ok", f"{path} has the obsidian and hal-hub servers")
    elif not check:
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        path.write_text(json.dumps(cfg, indent=2) + "\n")
    return (len(changes) if check else 0) + (0 if hub else 1)


def make_vault(root: Path, check: bool) -> int:
    """Creates an empty vault (with its inbox) on a first install; an existing one is left alone."""
    if root.is_dir():
        return 0
    if check:
        say("todo", f"create the vault at {root} (or set [hal].vault to yours)")
        return 1
    (root / "+Inbox").mkdir(parents=True)
    say("created", f"an empty vault at {root}; open it in Obsidian with 'Open folder as vault'")
    return 0


def link_bin(bin_dir: Path, check: bool) -> int:
    """Puts bin/hal-memory on the PATH through a symlink in `bin_dir`."""
    src = ROOT / "bin" / "hal-memory"
    target = bin_dir / "hal-memory"
    if target.is_symlink() and target.resolve() == src.resolve():
        say("ok", f"{target} -> {src}")
        return 0
    if target.exists() or target.is_symlink():
        say("warn", f"{target} exists and is not this hal-memory; left alone")
        return 1
    if check:
        say("todo", f"link {target} -> {src}")
        return 1
    bin_dir.mkdir(parents=True, exist_ok=True)
    target.symlink_to(src)
    say("linked", str(target))
    return 0


def install_skills(skills_dir: str | None, commands: Path, check: bool) -> int:
    """Installs the skills and removes the old command links; returns how many things are left."""
    folders = (
        [Path(skills_dir).expanduser()]
        if skills_dir
        else [skillsinstall.resolve_target(t) for t in skillsinstall.default_targets()]
    )
    todo = 0
    for report in (
        skillsinstall.install(folders, check=check),
        skillsinstall.clean_legacy(commands, check=check),
    ):
        for line in report.lines:
            say("skills", line)
        todo += report.todo if check else report.refused
    if not todo:
        say("ok", "skills installed in " + ", ".join(str(f) for f in folders))
    return todo


def run(
    check: bool = False,
    commands_dir: str | None = None,
    bin_dir: str | None = None,
    pull: bool = True,
    skills_dir: str | None = None,
) -> int:
    """Runs every setup step; returns the exit status (with check, 1 when anything is left to do).

    `commands_dir` is where the old setup linked slash commands; those links are removed.
    """
    commands = Path(
        commands_dir or os.environ.get("HAL_CLAUDE_COMMANDS", "~/.claude/commands")
    ).expanduser()
    bins = Path(bin_dir or os.environ.get("HAL_BIN_DIR", "~/.local/bin")).expanduser()
    root = vault()
    print(f"hal-memory setup{' --check' if check else ''}: vault {root}")
    todo = install_skills(skills_dir, commands, check) + link_bin(bins, check) + check_tools()
    todo += embed_model(check) if pull else 0
    todo += make_vault(root, check)
    todo += mcp_file(root / ".mcp.json", check) if root.is_dir() or not check else 0
    if not key_file().exists():
        say("todo", "save the Obsidian Local REST API key: hal-memory obsidian-key KEY")
        todo += 1
    if (root / "System" / ".rag").is_dir():
        say(
            "note",
            f"{root / 'System' / '.rag'} is the old search index; hal-memory does not use it, so it can be deleted",
        )
    print("all set" if not todo else f"{todo} thing(s) {'to do' if check else 'still need you'}")
    return 1 if check and todo else 0
