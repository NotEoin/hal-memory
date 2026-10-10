"""hal-memory's tools, as declared in hal-module.toml."""
from __future__ import annotations

import json
from pathlib import Path

from . import audit, capture, search, sorter, vault
from .config import data_dir


def remember(text: str, title: str = "", tags: list[str] | None = None) -> dict:
    p = capture.remember(text, title, tags)
    return {"saved": vault.rel(p), "note": "it will be filed and linked when the computer is next idle"}


def remember_fact(fact: str) -> str:
    return capture.add_fact(fact)


def profile() -> str:
    return capture.facts()


def search_notes(query: str, limit: int = 8) -> list[dict]:
    return search.search(query, int(limit))


def recall(question: str, no_llm: bool = False) -> dict:
    return search.recall(question, no_llm=no_llm)


def read(note: str) -> dict:
    """Returns a note by title or vault-relative path."""
    path = None
    if note.endswith(".md") or "/" in note:
        path = vault.inside(Path(note if note.endswith(".md") else note + ".md"))
    else:
        path = vault.title_index().get(note.lower())
        if path is None:
            hits = [p for p in vault.notes() if p.stem.lower() == note.lower()]
            path = hits[0] if hits else None
    if path is None or not path.exists():
        return {"error": f"no note called {note}"}
    return {"path": vault.rel(path), "text": path.read_text(errors="ignore")[:12000]}


def append(note: str, text: str) -> dict:
    found = read(note)
    if "error" in found:
        return found
    p = vault.inside(Path(found["path"]))
    p.write_text(p.read_text().rstrip("\n") + "\n\n" + text.strip() + "\n")
    return {"appended": found["path"]}


def log_conversation(user: str, assistant: str, channel: str = "voice") -> str:
    return vault.rel(capture.log_conversation(user, assistant, channel))


def daily(date: str = "") -> dict:
    p = capture.daily_note(date or None)
    return {"path": vault.rel(p), "text": p.read_text()}


def sort_inbox(limit: int = 10) -> list[dict]:
    return sorter.sort(int(limit))


def link(note: str = "", limit: int = 200) -> dict:
    """Runs the wikilink pass on one note, or on up to `limit` notes."""
    from .linker import Linker
    linker = Linker()
    if note:
        found = read(note)
        if "error" in found:
            return found
        return {"note": found["path"], "links_added": linker.link_note(vault.inside(Path(found["path"])))}
    total = 0
    for p in vault.notes()[: int(limit)]:
        total += linker.link_note(p)
    return {"links_added": total}


def tidy(limit: int = 25) -> dict:
    """One quality pass: audit changed notes and fix the next batch of problems."""
    return {"audit": audit.audit(), "fix": audit.fix(int(limit))}


def status() -> dict:
    inbox = sorter.pending()
    last = data_dir() / "last-pass.json"
    return {"vault": str(vault.root()), "inbox": len(inbox), **audit.status(),
            "last_pass": json.loads(last.read_text()) if last.exists() else None}


def update_index(limit: int = 400) -> dict:
    return search.update_index(int(limit))


def brief(date: str = "", no_llm: bool = False, print_only: bool = False) -> dict:
    """Writes the morning brief into the day's daily note and returns it."""
    from . import brief as briefing
    return briefing.brief(date, no_llm=no_llm, print_only=print_only)
