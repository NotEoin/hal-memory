"""Quality passes over the whole vault, so every note ends up linked and findable.

audit() scores notes against simple rules (frontmatter, outgoing links,
backlinks) and records the problems in a state table, so an unchanged note is
never re-checked. fix() works through the problems: the wikilink pass, a
"Related" line built from the semantic index, folder index notes that give
every note a backlink, and a second classification for needs-review notes.
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

from . import llm, vault
from .config import data_dir, settings, shared
from .linker import Linker

LINK = re.compile(r"\[\[([^\]|#]+)")
# Folders whose notes get a generated index note listing them all.
INDEXED = ("People", "Organisations", "Places", "Topics", "Resources", "Conversations",
           "Areas/Personal/Ideas", "Areas/Study/Notes", "Areas/Job Search/Notes")
INDEX_DIR = "System/Indexes"


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(data_dir() / "audit.db")
    con.execute("""CREATE TABLE IF NOT EXISTS notes (path TEXT PRIMARY KEY, mtime REAL, checked REAL,
                   issues TEXT, fixed REAL)""")
    return con


def _graph() -> tuple[dict[str, set[str]], dict[str, int]]:
    """Returns each note's outgoing link targets and every note's backlink count, by lower-case title."""
    out: dict[str, set[str]] = {}
    back: dict[str, int] = {}
    for p in vault.notes():
        try:
            links = {t.strip().lower() for t in LINK.findall(p.read_text(errors="ignore"))}
        except OSError:
            continue
        out[vault.rel(p)] = links
        for t in links:
            back[t] = back.get(t, 0) + 1
    return out, back


# Files that describe the vault or its folders rather than hold knowledge.
SYSTEM_NOTES = {"readme", "claude", "claude-archive", "start here", "home"}


def issues_for(path: Path, links: set[str], backlinks: int) -> list[str]:
    if path.stem.lower() in SYSTEM_NOTES:
        return []
    text = path.read_text(errors="ignore")
    meta = vault.fields(text)
    body = vault.split(text)[1].strip()
    found = []
    if len(body) < 20:
        found.append("empty")
    if not meta:
        found.append("no-frontmatter")
    if not links and len(body) > 200:
        found.append("no-links")
    if backlinks == 0 and not path.stem[:4].isdigit():
        found.append("orphan")
    if meta.get("hal") in ("needs-review", "needs-index", "inbox"):
        found.append(meta["hal"])
    return found


def audit(limit: int = 2000) -> dict:
    """Checks notes changed since their last check; returns counts by problem."""
    con = _db()
    seen = dict(con.execute("SELECT path, mtime FROM notes"))
    out, back = _graph()
    checked = 0
    for p in vault.notes():
        r = vault.rel(p)
        m = p.stat().st_mtime
        if seen.get(r) == m:
            continue
        found = issues_for(p, out.get(r, set()), back.get(p.stem.lower(), 0))
        con.execute("INSERT OR REPLACE INTO notes (path, mtime, checked, issues) VALUES (?, ?, ?, ?)",
                    (r, m, time.time(), ",".join(found)))
        checked += 1
        if checked >= limit:
            break
    con.commit()
    return {"checked": checked, **status()}


def status() -> dict:
    """Returns how many notes have each problem."""
    counts: dict[str, int] = {}
    for (issues,) in _db().execute("SELECT issues FROM notes WHERE issues != ''"):
        for i in issues.split(","):
            counts[i] = counts.get(i, 0) + 1
    return {"problems": counts}


def build_indexes() -> int:
    """Writes one index note per managed folder, so every note in it has a backlink."""
    written = 0
    for folder in INDEXED:
        d = vault.root() / folder
        if not d.exists():
            continue
        members = sorted(p for p in d.rglob("*.md") if p.parent != vault.root() / INDEX_DIR)
        if not members:
            continue
        name = folder.replace("/", " - ")
        lines = [f"# {name}", "", f"Every note in `{folder}`, kept current by Hal's quality pass.", ""]
        for p in members:
            summary = vault.fields(p.read_text(errors="ignore")[:1500]).get("summary")
            lines.append(f"- [[{p.stem}]]" + (f": {summary}" if isinstance(summary, str) and summary else ""))
        target = vault.inside(Path(INDEX_DIR) / f"{name}.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        text = vault.set_fields("\n".join(lines) + "\n", {"type": "index", "tags": ["index"], "hal": "generated"})
        if not target.exists() or target.read_text() != text:
            target.write_text(text)
            written += 1
    return written


def _related(path: Path, limit: int = 3) -> list[str]:
    from .search import semantic
    text = vault.split(path.read_text(errors="ignore"))[1]
    hits = semantic(f"{path.stem}\n{text[:800]}", limit + 1)
    return [h["note"] for h in hits if h["note"] != path.stem][:limit]


def fix(limit: int | None = None) -> dict:
    """Works through recorded problems; returns what was done."""
    limit = limit or settings()["batch"]
    con = _db()
    rows = con.execute("""SELECT path, issues FROM notes WHERE issues != '' AND (fixed IS NULL OR fixed < checked)
                          ORDER BY checked LIMIT ?""", (limit,)).fetchall()
    linker = Linker()
    done = {"linked": 0, "related": 0, "reclassified": 0, "indexes": build_indexes()}
    gpu_free = llm.gpu_busy() is None
    # Related links only need embeddings; on the CPU they do not touch the GPU.
    model_ok = gpu_free or bool(shared().get("embed_on_cpu"))
    for r, issues in rows:
        try:
            p = vault.inside(Path(r))
        except ValueError:
            continue
        if not p.exists():
            con.execute("DELETE FROM notes WHERE path = ?", (r,))
            continue
        found = issues.split(",")
        if linker.link_note(p):
            done["linked"] += 1
        text = p.read_text(errors="ignore")
        if model_ok and "no-links" in found and "[[" not in vault.split(text)[1]:
            try:
                rel = _related(p)
            except llm.Unavailable:
                rel, model_ok = [], False
            if rel:
                p.write_text(text.rstrip("\n") + "\n\nRelated: " + ", ".join(f"[[{n}]]" for n in rel) + "\n")
                done["related"] += 1
        if gpu_free and "needs-review" in found:
            done["reclassified"] += _reclassify(p)
        meta = vault.fields(p.read_text(errors="ignore"))
        if meta.get("hal") == "needs-index":
            p.write_text(vault.set_fields(p.read_text(errors="ignore"), {"hal": "ok"}))
        con.execute("UPDATE notes SET fixed = ? WHERE path = ?", (time.time(), r))
    con.commit()
    return done


def _reclassify(path: Path) -> int:
    """Asks the stronger model to confirm a doubtful filing; marks the note ok when it agrees."""
    from .sorter import classify
    text = path.read_text(errors="ignore")
    decision = classify(text)
    if float(decision.get("confidence") or 0) >= settings()["review_below"]:
        path.write_text(vault.set_fields(text, {"hal": "ok", "hal-confidence": decision.get("confidence"),
                                               "summary": vault.fields(text).get("summary") or decision.get("summary")}))
        return 1
    return 0
