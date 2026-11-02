"""Reading and writing notes in the Obsidian vault.

Frontmatter is edited line by line, so keys Hal does not manage are kept
exactly as written. Every path is checked to stay inside the vault.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .config import settings, vault

FRONT = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
SKIP_DIRS = {".obsidian", ".trash", ".git", ".claude", "_Import-Staging", "node_modules"}


def root() -> Path:
    """Returns the vault folder."""
    return vault()


def inside(path: Path) -> Path:
    """Returns the path resolved, refusing anything outside the vault."""
    base = root().resolve()
    p = (base / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    if p != base and base not in p.parents:
        raise ValueError(f"{path} is outside the vault")
    return p


def rel(path: Path) -> str:
    """Returns a path relative to the vault root."""
    return str(Path(path).resolve().relative_to(root().resolve()))


def notes() -> list[Path]:
    """Returns every Markdown note, skipping Obsidian's and tools' own folders."""
    out = []
    for p in root().rglob("*.md"):
        if not SKIP_DIRS.intersection(p.relative_to(root()).parts):
            out.append(p)
    return out


def slug(text: str, limit: int = 80) -> str:
    """Returns a filename-safe title: Obsidian forbids * " \\ / < > : | ? # ^ [ ]."""
    text = re.sub(r'[*"\\/<>:|?#^\[\]]', " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit].strip() or "Untitled"


def split(text: str) -> tuple[str, str]:
    """Returns (frontmatter block without fences, body)."""
    m = FRONT.match(text)
    return (m.group(1), text[m.end() :]) if m else ("", text)


def fields(text: str) -> dict:
    """Returns the frontmatter's top-level keys; lists become Python lists."""
    block, _ = split(text)
    out: dict = {}
    key = None
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                out[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            elif value:
                out[key] = value.strip("'\"")
            else:
                out[key] = []
        elif key and re.match(r"^\s*-\s+", line) and isinstance(out.get(key), list):
            out[key].append(re.sub(r"^\s*-\s+", "", line).strip().strip("'\""))
    return out


def _dump(value) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_quote(v) for v in value) + "]"
    return _quote(value)


def _quote(v) -> str:
    s = str(v)
    return f'"{s}"' if re.search(r"[:#\[\],{}]|^\s|\s$", s) else s


def set_fields(text: str, updates: dict) -> str:
    """Returns the note with frontmatter keys set (None removes a key), creating the block if needed."""
    block, body = split(text)
    lines = block.splitlines() if block else []
    for key, value in updates.items():
        start = next(
            (i for i, line in enumerate(lines) if re.match(rf"^{re.escape(key)}:", line)), None
        )
        if start is not None:
            end = start + 1
            while end < len(lines) and re.match(r"^\s+-\s|^\s*-\s", lines[end]):
                end += 1
            del lines[start:end]
        if value is not None:
            lines.insert(start if start is not None else len(lines), f"{key}: {_dump(value)}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body.lstrip("\n")


def title_of(path: Path) -> str:
    """Returns a note's title, which is its file stem."""
    return Path(path).stem


def write_new(folder: str, title: str, body: str, meta: dict) -> Path:
    """Creates a note, adding a number to the name if one already exists; returns its path."""
    d = inside(Path(folder))
    d.mkdir(parents=True, exist_ok=True)
    name = slug(title)
    path = d / f"{name}.md"
    n = 2
    while path.exists():
        path = d / f"{name} {n}.md"
        n += 1
    path.write_text(set_fields(body if body.endswith("\n") else body + "\n", meta))
    return path


def today() -> str:
    """Returns today's local date as `YYYY-MM-DD`."""
    return datetime.now().strftime("%Y-%m-%d")


def now() -> str:
    """Returns the local time as `YYYY-MM-DDTHH:MM`."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def folders() -> dict:
    """Returns the category-to-folder map from settings."""
    return settings()["folders"]


GENERIC = {
    "index",
    "_index",
    "readme",
    "start here",
    "untitled",
    "home",
    "notes",
    "todo",
    "tasks",
    "inbox",
    "summary",
    "overview",
    "introduction",
    "conclusion",
    "references",
    "template",
    "slides",
    "week",
    "lecture",
    "lab",
    "session-log",
    "meeting",
    "daily",
    "claude",
    "claude-archive",
    "profile",
    "dashboard",
    "start",
}


def title_index() -> dict[str, Path]:
    """Returns linkable names (lower case) to notes: titles and aliases that are unique and specific."""
    seen: dict[str, list[Path]] = {}
    for p in notes():
        names = [p.stem]
        try:
            head = p.read_text(errors="ignore")[:2000]
        except OSError:
            continue
        aliases = fields(head).get("aliases")
        if isinstance(aliases, list):
            names += aliases
        elif isinstance(aliases, str):
            names.append(aliases)
        for n in names:
            key = n.strip().lower()
            if (
                len(key) < 4
                or key in GENERIC
                or re.fullmatch(r"[\d\s._-]+", key)
                or re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", key)
            ):
                continue
            seen.setdefault(key, []).append(p)
    # A name shared by two notes is ambiguous in Obsidian, so it is never auto-linked.
    return {k: v[0] for k, v in seen.items() if len(set(v)) == 1}
