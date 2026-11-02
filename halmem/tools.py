"""hal-memory's tools, as declared in hal-module.toml."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import audit, capture, search, sorter, vault
from .config import data_dir

log = logging.getLogger(__name__)


def remember(text: str, title: str = "", tags: list[str] | None = None) -> dict:
    """Saves a note to the inbox and returns where it went."""
    p = capture.remember(text, title, tags)
    return {
        "saved": vault.rel(p),
        "note": "it will be filed and linked when the computer is next idle",
    }


def remember_fact(fact: str) -> str:
    """Adds a lasting fact to the profile note."""
    return capture.add_fact(fact)


def profile() -> str:
    """Returns the profile note's facts."""
    return capture.facts()


def search_notes(query: str, limit: int = 8) -> list[dict]:
    """Searches the vault by keyword and by meaning."""
    return search.search(query, int(limit))


def recall(question: str, no_llm: bool = False) -> dict:
    """Answers a question from the vault with the local model.

    Never uses the `claude` answerer, whatever `[memory].answerer` or `HAL_ANSWERER` say: a tool
    call is made by a model, and vault passages must not leave the machine because of one.
    Only the `hal-memory ask` command, run by a person, may use it.
    """
    return search.recall(question, no_llm=no_llm, who="local")


def read(note: str) -> dict:
    """Returns a note by title or vault-relative path.

    The note must resolve inside the vault after `..` and symlinks are followed; anything else
    (an absolute path elsewhere, a `..` escape, a symlink pointing out) is refused with an
    error entry, so a model cannot read other files through a note name.
    """
    path = None
    try:
        if note.endswith(".md") or "/" in note:
            path = vault.inside(Path(note if note.endswith(".md") else note + ".md"))
        else:
            path = vault.title_index().get(note.lower())
            if path is None:
                hits = [p for p in vault.notes() if p.stem.lower() == note.lower()]
                path = hits[0] if hits else None
            if path is not None:
                path = vault.inside(path)
    except ValueError:
        log.warning("refused note name outside the vault: %r", note)
        return {"error": f"{note!r} is not a note inside the vault"}
    if path is None or not path.exists():
        return {"error": f"no note called {note}"}
    return {"path": vault.rel(path), "text": path.read_text(errors="ignore")[:12000]}


def append(note: str, text: str) -> dict:
    """Appends text to an existing note."""
    found = read(note)
    if "error" in found:
        return found
    p = vault.inside(Path(found["path"]))
    p.write_text(p.read_text().rstrip("\n") + "\n\n" + text.strip() + "\n")
    return {"appended": found["path"]}


def log_conversation(user: str, assistant: str, channel: str = "voice") -> str:
    """Appends one exchange to the day's conversation log and returns its path."""
    return vault.rel(capture.log_conversation(user, assistant, channel))


def daily(date: str = "") -> dict:
    """Returns a day's daily note, creating it when missing."""
    p = capture.daily_note(date or None)
    return {"path": vault.rel(p), "text": p.read_text()}


def sort_inbox(limit: int = 10) -> list[dict]:
    """Sorts up to `limit` inbox notes and returns what was done with each."""
    return sorter.sort(int(limit))


def link(note: str = "", limit: int = 200) -> dict:
    """Runs the wikilink pass on one note, or on up to `limit` notes."""
    from .linker import Linker

    linker = Linker()
    if note:
        found = read(note)
        if "error" in found:
            return found
        return {
            "note": found["path"],
            "links_added": linker.link_note(vault.inside(Path(found["path"]))),
        }
    total = 0
    for p in vault.notes()[: int(limit)]:
        total += linker.link_note(p)
    return {"links_added": total}


def tidy(limit: int = 25) -> dict:
    """One quality pass: audit changed notes and fix the next batch of problems."""
    return {"audit": audit.audit(), "fix": audit.fix(int(limit))}


def status() -> dict:
    """Returns the vault path, the inbox size, the audit counts and the last pass."""
    inbox = sorter.pending()
    last = data_dir() / "last-pass.json"
    return {
        "vault": str(vault.root()),
        "inbox": len(inbox),
        **audit.status(),
        "last_pass": json.loads(last.read_text()) if last.exists() else None,
    }


def update_index(limit: int = 400) -> dict:
    """Updates the semantic index for up to `limit` notes."""
    return search.update_index(int(limit))


def brief(date: str = "", no_llm: bool = False, print_only: bool = False) -> dict:
    """Writes the morning brief into the day's daily note and returns it."""
    from . import brief as briefing

    return briefing.brief(date, no_llm=no_llm, print_only=print_only)
