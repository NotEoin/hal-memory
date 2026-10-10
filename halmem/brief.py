"""The morning brief: the day pulled together from the vault and written into the daily note.

It gathers open tasks and deadlines, yesterday's work, active projects and the
last work session, and a concept of the day from the study topics, then has the
chat model write them up. Without a model the gathered facts are written as they
are. Re-running a day replaces that day's brief.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from . import llm, vault
from .config import settings

SYSTEM = (
    "You are Hal, the user's private daily assistant. You are given a PACKET of facts pulled from "
    "their Obsidian vault this morning: open tasks and today's deadlines, yesterday's work, their "
    "projects and last work session, and a concept of the day from their study notes. Turn it into "
    "a SHORT, warm morning brief they can read in under a minute. Use the real task text, project "
    "names and dates from the packet; never invent items. Start with a one-line greeting, then "
    "tight sections with small headings. Keep [[wiki links]] and `- [ ]` checkboxes exactly as "
    "given. Leave out empty sections. Clean Markdown, no preamble, no sign-off."
)
HEADER = "## ☀️ Morning Brief"
START = "<!-- HAL-BRIEF:START -->"
END = "<!-- HAL-BRIEF:END -->"
TASK = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.*)$")
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
HEADING = re.compile(r"^#{1,6}\s+\S")
H1 = re.compile(r"^#\s+\S")
LINK = re.compile(r"\[\[([^\]|#]+)")


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _md(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.md")) if folder.is_dir() else []


def _study(root: Path, p: Path) -> bool:
    return (root / "Areas" / "Study") in p.parents


def section(text: str, name: str) -> str:
    """Returns the lines under the first heading containing `name`, up to the next heading."""
    out, inside = [], False
    for line in text.splitlines():
        if HEADING.match(line.strip()):
            if inside:
                break
            inside = name.lower() in re.sub(r"^#+\s+", "", line.strip()).lower()
            continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def tasks(root: Path, day: str) -> tuple[list[dict], list[dict]]:
    """Returns (open, due) unchecked tasks outside Study; a task dated on or before `day` is due."""
    open_, due = [], []
    for folder in ("Areas", "Calendar", settings()["inbox"]):
        for p in _md(root / folder):
            if _study(root, p):
                continue
            for line in _read(p).splitlines():
                m = TASK.match(line)
                if not m or m.group(1).lower() == "x" or not m.group(2).strip():
                    continue
                item = {"text": m.group(2).strip(), "path": str(p.relative_to(root))}
                (due if any(d <= day for d in DATE.findall(line)) else open_).append(item)
    return open_, due


def yesterday(root: Path, day: date) -> dict | None:
    """Returns yesterday's done notes, completed tasks and unfinished tasks from its daily note."""
    p = root / settings()["daily_folder"] / f"{day - timedelta(days=1)}.md"
    if not p.exists():
        return None
    text = _read(p)
    done = [l for l in section(text, "done today").splitlines()
            if l.strip().lstrip("-*").strip() and not l.strip().startswith("<!--")]
    completed, carry = [], []
    for line in text.splitlines():
        m = TASK.match(line)
        if m and m.group(2).strip():
            (completed if m.group(1).lower() == "x" else carry).append(m.group(2).strip())
    return {"date": p.stem, "done": done[:10], "completed": completed[:10], "carry": carry[:10]}


def projects(root: Path) -> tuple[list[dict], dict | None]:
    """Returns the active projects outside Study, and the newest work session log."""
    active = []
    for p in _md(root / "Areas"):
        if _study(root, p):
            continue
        f = vault.fields(_read(p))
        if f.get("type") == "project" and str(f.get("status", "")).lower() == "active":
            active.append({"name": p.stem, "date": f.get("date", "") if isinstance(f.get("date"), str) else ""})
    logs = sorted((root / "Areas" / "Work" / "Session-Logs").glob("*.md"), key=lambda q: q.stat().st_mtime)
    last = None
    if logs:
        text = _read(logs[-1])
        m = re.search(r"\*\*Outcome:\*\*\s*(.*)", text)
        last = {"name": logs[-1].stem, "outcome": m.group(1).strip() if m else "",
                "quick": section(text, "quick reference")[:500]}
    return active[:8], last


def concept(root: Path, day: date) -> dict | None:
    """Picks a well-linked topic that is still a stub, rotating by date."""
    topics = {p.stem: p for p in (root / "Areas" / "Study" / "Topics").glob("*.md")}
    if not topics:
        return None
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for p in _md(root / "Areas" / "Study"):
        if p.parent.name == "Topics":
            continue
        for name in {n.strip() for n in LINK.findall(_read(p))} & topics.keys():
            counts[name] = counts.get(name, 0) + 1
            examples.setdefault(name, []).append(p.stem)
    def stub(name: str) -> bool:
        notes = section(_read(topics[name]), "notes").lower()
        return not notes or "empty" in notes

    stubs = [(c, n) for n, c in counts.items() if c >= 3 and stub(n)]
    picks = sorted(stubs or [(c, n) for n, c in counts.items()], reverse=True)[:30]
    if not picks:
        return None
    c, name = picks[day.toordinal() % len(picks)]
    return {"name": name, "inlinks": c, "examples": examples[name][:5]}


def packet(root: Path, day: date) -> tuple[str, dict]:
    """Returns the facts for the brief as Markdown, and their counts."""
    open_, due = tasks(root, day.isoformat())
    recap = yesterday(root, day)
    active, last = projects(root)
    topic = concept(root, day)
    out = [f"# Brief packet for {day:%A %d %B %Y}", "", "## Tasks & deadlines"]
    if due:
        out += ["Due today / overdue:"] + [f"- [ ] {t['text']}  ({t['path']})" for t in due[:15]]
    if open_:
        out += ["Other open tasks:"] + [f"- [ ] {t['text']}  ({t['path']})" for t in open_[:15]]
    if not due and not open_:
        out.append("(no open tasks found)")
    out += ["", "## Yesterday"]
    if recap and (recap["completed"] or recap["done"] or recap["carry"]):
        if recap["completed"]:
            out.append("Completed: " + "; ".join(recap["completed"]))
        if recap["done"]:
            out += ["Done-today notes:"] + recap["done"]
        if recap["carry"]:
            out += ["Unfinished (carry forward):"] + [f"- [ ] {c}" for c in recap["carry"]]
    else:
        out.append("(no daily note for yesterday, or it was empty)")
    out += ["", "## Projects & last session"]
    out += [f"- [[{p['name']}]] — active" + (f" (since {p['date']})" if p["date"] else "") for p in active] \
        or ["(no active projects)"]
    if last:
        out.append(f"Last session: [[{last['name']}]]")
        if last["outcome"] or last["quick"]:
            out.append("  " + (last["outcome"] or last["quick"].replace("\n", " ")))
    out += ["", "## Concept of the day"]
    if topic:
        out.append(f"[[{topic['name']}]] — linked from {topic['inlinks']} notes; still a stub worth a "
                   "5-minute review or expand.")
        out.append("Appears in: " + (", ".join(f"[[{e}]]" for e in topic["examples"]) or "—"))
    else:
        out.append("(no topic graph yet)")
    return "\n".join(out), {"open": len(open_), "due": len(due), "projects": len(active), "concept": bool(topic)}


def plain(facts: str, day: date) -> str:
    """Returns the brief without a model: the packet under a greeting."""
    return f"Good morning — here's {day:%A %d %B}.\n\n" + re.sub(r"^# Brief packet.*\n", "", facts).strip()


def daily_note(root: Path, day: date) -> Path:
    """Returns the day's note, creating it from System/Templates/Daily.md when there is one."""
    p = root / settings()["daily_folder"] / f"{day}.md"
    if p.exists():
        return p
    template = root / "System" / "Templates" / "Daily.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    if template.exists():
        p.write_text(_read(template).replace("{{date:YYYY-MM-DD}}", day.isoformat()), encoding="utf-8")
    else:
        p.write_text(vault.set_fields(f"# {day:%A %-d %B %Y}\n\n",
                                      {"type": "daily", "date": day.isoformat(), "tags": ["daily"]}))
    return p


def insert(text: str, brief: str) -> str:
    """Returns the note with the brief block replaced, or added under its H1."""
    text = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", "", text, flags=re.S)
    block = [START, HEADER, "<!-- written by `hal brief`; running it again replaces this block -->",
             *brief.strip().splitlines(), END]
    lines = text.splitlines()
    h1 = next((i for i, l in enumerate(lines) if H1.match(l.strip())), None)
    if h1 is None:
        return "\n".join(block + [""] + lines).rstrip() + "\n"
    tail = lines[h1 + 1:]
    while tail and not tail[0].strip():
        tail.pop(0)
    return "\n".join(lines[:h1 + 1] + [""] + block + [""] + tail).rstrip() + "\n"


def brief(day: str = "", no_llm: bool = False, print_only: bool = False, model: str | None = None,
          root: Path | None = None) -> dict:
    """Builds the brief for a day (today by default), writes it into the daily note, and returns it."""
    root = Path(root or vault.root())
    when = date.fromisoformat(day) if day else date.today()
    facts, stats = packet(root, when)
    text, used = plain(facts, when), "none"
    if not no_llm:
        try:
            reply = llm.chat(SYSTEM, facts, model=model, timeout=300, temperature=0.4, retries=1).strip()
            if reply:
                text, used = reply, model or llm.chat_model()
        except llm.Unavailable as e:
            stats["model_error"] = str(e)[:200]
    out = {"brief": text, "model": used, **stats}
    if not print_only:
        p = daily_note(root, when)
        p.write_text(insert(_read(p), text), encoding="utf-8")
        out["path"] = str(p.relative_to(root))
    return out
