"""Getting things into the vault: quick capture, conversations, daily notes and the owner's profile.

Everything lands in +Inbox/ or in a dated note first; the sorter files and
links it later, so capture is instant and never needs the local model.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import vault
from .config import settings


def remember(text: str, title: str = "", tags: list[str] | None = None, source: str = "hal") -> Path:
    """Writes a capture to the inbox and returns its path."""
    stamp = datetime.now().strftime("%Y-%m-%d %H%M%S")
    name = f"{stamp} {vault.slug(title or text.split(chr(10))[0], 50)}"
    return vault.write_new(settings()["inbox"], name, text.strip() + "\n",
                           {"created": vault.now(), "source": source, "tags": tags or [], "hal": "inbox"})


def daily_note(day: str | None = None) -> Path:
    """Returns the daily note for a date (YYYY-MM-DD, default today), creating it if needed."""
    day = day or vault.today()
    path = vault.inside(Path(settings()["daily_folder"]) / f"{day}.md")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        d = datetime.strptime(day, "%Y-%m-%d")
        path.write_text(vault.set_fields(f"# {d:%A %-d %B %Y}\n\n", {"type": "daily", "date": day, "tags": ["daily"]}))
    return path


def log_conversation(user: str, assistant: str, channel: str = "voice") -> Path:
    """Appends one exchange to today's conversation log, linked from the daily note."""
    day = vault.today()
    folder = Path(settings()["folders"]["conversation"]) / day[:4] / day[5:7]
    path = vault.inside(folder / f"{day} Conversations.md")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(vault.set_fields(f"# Conversations on {day}\n\nDay: [[{day}]]\n",
                                         {"type": "conversation", "date": day, "tags": ["conversation"],
                                          "hal": "needs-index"}))
        _daily_link(day, path.stem)
    t = datetime.now().strftime("%H:%M")
    with path.open("a") as f:
        f.write(f"\n## {t} ({channel})\n\n**You:** {user.strip()}\n\n**Hal:** {assistant.strip()}\n")
    return path


def _daily_link(day: str, stem: str) -> None:
    p = daily_note(day)
    text = p.read_text()
    if f"[[{stem}]]" not in text:
        p.write_text(text.rstrip("\n") + f"\n\nConversations: [[{stem}]]\n")


def profile_path() -> Path:
    path = vault.inside(Path(settings()["profile_note"]))
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(vault.set_fields(
            "# Profile\n\nWhat Hal knows about you. Hal reads this first and adds to it when told a lasting fact.\n\n## Facts\n\n",
            {"type": "profile", "tags": ["system", "profile"]}))
    return path


def add_fact(fact: str) -> str:
    """Adds a lasting fact about the owner to the profile note, skipping duplicates."""
    path = profile_path()
    text = path.read_text()
    line = f"- {fact.strip().rstrip('.')}. ({vault.today()})"
    if fact.strip().rstrip(".").lower() in text.lower():
        return "already known"
    path.write_text(text.rstrip("\n") + "\n" + line + "\n")
    return "added"


def facts() -> str:
    """Returns the profile's facts section."""
    text = profile_path().read_text()
    _, body = vault.split(text)
    return body.split("## Facts", 1)[-1].strip()
