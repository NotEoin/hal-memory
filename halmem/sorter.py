"""The inbox sorter: classifies captured notes, files them, and links them into the vault.

For each note in +Inbox/ the local model returns a category, a title, tags,
a one-line summary, the people, organisations, places, projects and topics it
mentions, and its confidence. The note moves to the category's folder with that
frontmatter; each entity gets a note of its own if it has none, and is linked.
Low-confidence notes are filed but marked needs-review for another pass.
"""

from __future__ import annotations

from pathlib import Path

from . import llm, vault
from .config import settings
from .linker import Linker

CLASSIFY = """You file notes in a personal Obsidian vault. Reply with JSON only:
{{"category": one of {categories},
 "title": a short, specific note title (no date unless the note is about a date),
 "tags": [up to 5 lower-case tags],
 "summary": one sentence saying what the note records,
 "people": [full names of people mentioned], "organisations": [companies, universities, groups],
 "places": [places], "projects": [named projects], "topics": [up to 5 subject concepts worth their own note],
 "actions": [things the owner said they need to do, if any],
 "confidence": 0.0 to 1.0, how sure you are of the category}}
Use names exactly as written in the note. Existing people and projects in the vault: {known}."""

ENTITY_FOLDERS = {
    "people": "person",
    "organisations": "organisation",
    "places": "place",
    "projects": "project",
    "topics": "topic",
}


def inbox() -> Path:
    return vault.inside(Path(settings()["inbox"]))


def pending(limit: int | None = None) -> list[Path]:
    """Returns inbox notes waiting to be sorted, oldest first."""
    d = inbox()
    if not d.exists():
        return []
    # README and underscore files describe the inbox itself and stay put.
    items = sorted(
        (p for p in d.glob("*.md") if p.stem.lower() != "readme" and not p.name.startswith("_")),
        key=lambda p: p.stat().st_mtime,
    )
    return items[:limit] if limit else items


def _known() -> str:
    names = []
    for folder in ("People", "Areas/Work/Projects"):
        d = vault.root() / folder
        if d.exists():
            names += [p.stem for p in d.rglob("*.md")][:60]
    return ", ".join(names) or "none yet"


def classify(text: str) -> dict:
    """Returns the model's filing decision for one note's text."""
    cats = list(settings()["folders"])
    out = llm.chat_json(CLASSIFY.format(categories=cats, known=_known()), text[:6000])
    if out.get("category") not in cats:
        out["category"] = "other"
        out["confidence"] = min(float(out.get("confidence") or 0), 0.3)
    return out


_index: dict | None = None


def _titles() -> dict:
    global _index
    if _index is None:
        _index = vault.title_index()
    return _index


def ensure_entity(kind: str, name: str, source_title: str) -> Path | None:
    """Returns the note for a person, place or other entity, creating a stub that links back."""
    name = vault.slug(name)
    if len(name) < 3:
        return None
    existing = _titles().get(name.lower())
    if existing:
        return existing
    folder = settings()["folders"][ENTITY_FOLDERS[kind]]
    body = f"# {name}\n\nFirst mentioned in [[{source_title}]].\n"
    note = vault.write_new(
        folder,
        name,
        body,
        {
            "type": ENTITY_FOLDERS[kind],
            "created": vault.now(),
            "hal": "needs-index",
            "tags": [ENTITY_FOLDERS[kind]],
        },
    )
    _titles()[name.lower()] = note
    return note


def file_note(path: Path, decision: dict) -> Path:
    """Moves an inbox note to its folder with frontmatter, entity links and a daily-note entry."""
    cfg = settings()
    text = path.read_text(errors="ignore")
    meta = vault.fields(text)
    title = vault.slug(decision.get("title") or path.stem)
    confidence = float(decision.get("confidence") or 0)
    status = "needs-review" if confidence < cfg["review_below"] else "filed"
    entities = []
    for kind in ENTITY_FOLDERS:
        for name in decision.get(kind) or []:
            note = ensure_entity(kind, name, title)
            if note is not None:
                entities.append(note.stem)
    _, body = vault.split(text)
    actions = [a for a in decision.get("actions") or [] if isinstance(a, str)]
    if actions and "## Actions" not in body:
        body = body.rstrip() + "\n\n## Actions\n\n" + "".join(f"- [ ] {a}\n" for a in actions)
    if entities:
        body = (
            body.rstrip()
            + "\n\nRelated: "
            + ", ".join(f"[[{e}]]" for e in dict.fromkeys(entities))
            + "\n"
        )
    tags = sorted(
        {
            *(meta.get("tags") or []),
            *(t.lower().replace(" ", "-") for t in decision.get("tags") or []),
        }
    )
    new_meta = {
        "created": meta.get("created") or vault.now(),
        "type": decision["category"],
        "tags": tags,
        "summary": decision.get("summary", ""),
        "hal": status,
        "hal-confidence": round(confidence, 2),
        "source": meta.get("source") or "inbox",
    }
    folder = cfg["folders"][decision["category"]]
    dest = vault.write_new(folder, title, body, new_meta)
    path.unlink()
    _titles()[dest.stem.lower()] = dest
    Linker(_titles()).link_note(dest)
    add_to_daily(
        f"Filed [[{dest.stem}]] in {folder}"
        + (" (needs review)" if status == "needs-review" else "")
    )
    return dest


def add_to_daily(line: str) -> None:
    """Appends a line under 'Hal' in today's daily note, creating the note if needed."""
    from .capture import daily_note

    p = daily_note()
    text = p.read_text()
    if "\n## Hal\n" not in text:
        text = text.rstrip() + "\n\n## Hal\n\n"
    p.write_text(text.rstrip("\n") + f"\n- {line}\n")


def sort(limit: int | None = None) -> list[dict]:
    """Files up to `limit` inbox notes; returns what happened to each."""
    reason = llm.gpu_busy()
    if reason:
        return [{"skipped": f"GPU in use by {reason}"}]
    global _index
    _index = None
    results = []
    for path in pending(limit or settings()["batch"]):
        try:
            text = path.read_text(errors="ignore")
            if not text.strip():
                path.unlink()
                continue
            decision = classify(text)
            dest = file_note(path, decision)
            results.append(
                {
                    "note": vault.rel(dest),
                    "category": decision["category"],
                    "confidence": decision.get("confidence"),
                }
            )
        except llm.Unavailable as e:
            results.append({"error": str(e)})
            break
        except Exception as e:  # noqa: BLE001 - one bad note must not block the rest of the inbox
            results.append({"note": path.name, "error": f"{type(e).__name__}: {e}"})
    return results
