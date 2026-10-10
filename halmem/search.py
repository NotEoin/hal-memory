"""Finding things in the vault: keyword search, a semantic index, and question answering.

The semantic index keeps one embedding per note chunk in SQLite and updates
only notes whose modification time changed. numpy speeds up ranking when it
is installed; pure Python is used otherwise.
"""
from __future__ import annotations

import array
import math
import os
import re
import sqlite3
import subprocess
from pathlib import Path

from . import llm, vault
from .config import data_dir, settings

CHUNK = 1200        # characters per chunk
MAX_CHUNKS = 12     # per note, so one huge note cannot dominate the index

CONTEXT = 6000      # characters of notes given to the answering model, so a voice turn stays quick

ANSWER = """Answer the question using only the vault notes given. Cite every note you use as
[[Note title]]. If the notes do not answer it, say so plainly. Be brief."""


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(data_dir() / "index.db")
    con.execute("""CREATE TABLE IF NOT EXISTS chunks (path TEXT, mtime REAL, n INTEGER, text TEXT, vec BLOB,
                   PRIMARY KEY (path, n))""")
    return con


# Words that carry no meaning in a question, so "What did I decide about caching?" searches for
# "decide" and "caching".
STOP = set("""a an the and or but if then so of to in on at by for from with about into over under
is are was were be been being am do does did done have has had having i me my mine we our us you your
he she it its they them their this that these those what which who whom whose when where why how
can could should would will shall may might must not no yes any all some each more most other such
just than too very also only own same there here out up down off again once tell show find give know
remember note notes vault anything something thing things""".split())


def terms(query: str) -> list[str]:
    """Returns the query's meaningful words: no stop words, nothing under three letters."""
    seen = []
    for w in re.findall(r"\w+", query.lower()):
        if len(w) > 2 and w not in STOP and w not in seen:
            seen.append(w)
    return seen


def keyword(query: str, limit: int = 10) -> list[dict]:
    """Returns notes containing most of the query's meaningful words, best matches first.

    A note needs at least half the words (all of them for one or two); notes with more
    distinct words rank first, then by how often they appear, with a bonus for the title.
    """
    words = terms(query)
    if not words:
        return []
    need = len(words) if len(words) <= 2 else (len(words) + 1) // 2
    hits = []
    for p in vault.notes():
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        low = text.lower()
        found = [w for w in words if w in low or w in p.stem.lower()]
        if len(found) < need:
            continue
        score = (len(found), sum(low.count(w) for w in found) + 5 * sum(w in p.stem.lower() for w in found))
        i = max(0, low.find(found[0]))
        hits.append((score, p, text[max(0, i - 80):i + 160].replace("\n", " ")))
    hits.sort(key=lambda h: h[0], reverse=True)
    return [{"note": h[1].stem, "path": vault.rel(h[1]), "snippet": h[2]} for h in hits[:limit]]


def _chunks(text: str) -> list[str]:
    _, body = vault.split(text)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return [body[i:i + CHUNK] for i in range(0, min(len(body), CHUNK * MAX_CHUNKS), CHUNK)] or [""]


def clear_index() -> None:
    """Forgets every embedding, so the next update rebuilds the index."""
    con = _db()
    con.execute("DELETE FROM chunks")
    con.commit()


def update_index(limit: int | None = None, progress=None) -> dict:
    """Embeds notes added or changed since the last update; returns counts.

    `progress(done, total)` is called every 50 notes when given.
    """
    con = _db()
    known = dict(con.execute("SELECT path, MAX(mtime) FROM chunks GROUP BY path"))
    present = set()
    todo = []
    for p in vault.notes():
        r = vault.rel(p)
        present.add(r)
        m = p.stat().st_mtime
        if known.get(r) != m:
            todo.append((r, p, m))
    gone = set(known) - present
    for r in gone:
        con.execute("DELETE FROM chunks WHERE path = ?", (r,))
    done = 0
    for r, p, m in todo[:limit]:
        chunks = [c for c in _chunks(p.read_text(errors="ignore")) if c.strip()]
        if not chunks:
            # Recorded with no vector, so an empty note counts as indexed instead of waiting forever.
            con.execute("DELETE FROM chunks WHERE path = ?", (r,))
            con.execute("INSERT INTO chunks VALUES (?, ?, 0, '', ?)", (r, m, b""))
            done += 1
            continue
        vecs = llm.embed([f"{p.stem}\n{c}" for c in chunks])
        con.execute("DELETE FROM chunks WHERE path = ?", (r,))
        con.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?)",
                        [(r, m, i, c, array.array("f", v).tobytes()) for i, (c, v) in enumerate(zip(chunks, vecs))])
        done += 1
        if done % 50 == 0:
            con.commit()
            if progress:
                progress(done, len(todo[:limit]))
    con.commit()
    return {"embedded": done, "waiting": max(0, len(todo) - done), "removed": len(gone)}


def semantic(query: str, limit: int = 8) -> list[dict]:
    """Returns the note chunks closest in meaning to the query."""
    q = llm.embed([query])[0]
    rows = _db().execute("SELECT path, n, text, vec FROM chunks WHERE length(vec) > 0").fetchall()
    if not rows:
        return []
    try:
        import numpy as np
        mat = np.frombuffer(b"".join(r[3] for r in rows), dtype=np.float32).reshape(len(rows), -1)
        qv = np.asarray(q, dtype=np.float32)
        scores = (mat @ qv) / (np.linalg.norm(mat, axis=1) * np.linalg.norm(qv) + 1e-9)
        order = np.argsort(-scores)
        ranked = [(float(scores[i]), rows[i]) for i in order[: limit * 4]]
    except ImportError:
        qn = math.sqrt(sum(x * x for x in q))
        ranked = []
        for r in rows:
            v = array.array("f", r[3])
            ranked.append((sum(a * b for a, b in zip(v, q)) / (math.sqrt(sum(a * a for a in v)) * qn + 1e-9), r))
        ranked.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for score, (path, _n, text, _v) in ranked:
        if path in seen:
            continue
        seen.add(path)
        out.append({"note": Path(path).stem, "path": path, "score": round(score, 3), "snippet": text[:300]})
        if len(out) >= limit:
            break
    return out


def search(query: str, limit: int = 8) -> list[dict]:
    """Returns keyword and semantic matches merged by rank, so a note either finds ranks well.

    Keyword search needs no index, so new notes and a missing or stale index still find
    their matches; semantic matches join in when the embedding model is reachable.
    """
    lists = [keyword(query, limit)]
    try:
        lists.append(semantic(query, limit))
    except llm.Unavailable:
        pass
    # Reciprocal rank fusion: a note high in either list, or present in both, comes first.
    score: dict[str, float] = {}
    best: dict[str, dict] = {}
    for results in lists:
        for rank, r in enumerate(results):
            score[r["path"]] = score.get(r["path"], 0) + 1 / (60 + rank)
            best[r["path"]] = {**r, **best.get(r["path"], {})}
    return [best[p] for p in sorted(score, key=lambda p: -score[p])][:limit]


def answerer() -> str:
    """Returns who writes recall answers: "local" (the chat model) or "claude" (the claude CLI)."""
    who = os.environ.get("HAL_ANSWERER") or settings()["answerer"]
    return "claude" if who == "claude" else "local"


def ask_claude(system: str, prompt: str, timeout: float = 600) -> str:
    """Returns Claude Code's answer through `claude -p`, using its own login.

    The retrieved passages leave the machine this way; HAL_CLAUDE_COMMAND names another binary.
    """
    cmd = os.environ.get("HAL_CLAUDE_COMMAND", "claude")
    try:
        r = subprocess.run([cmd, "-p", "--append-system-prompt", system, prompt],
                           capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise llm.Unavailable(f"{cmd} is not on the PATH; set [memory].answerer to local") from None
    except subprocess.TimeoutExpired:
        raise llm.Unavailable(f"{cmd} timed out after {timeout:.0f}s") from None
    if r.returncode != 0:
        # Claude Code reports problems such as "Not logged in" on stdout.
        detail = f"{r.stderr.strip()} {r.stdout.strip()}".strip()[:300] or "no output"
        raise llm.Unavailable(f"{cmd} failed (exit {r.returncode}): {detail}")
    return r.stdout.strip()


def recall(question: str, limit: int = 6, *, no_llm: bool = False, who: str | None = None,
           model: str | None = None) -> dict:
    """Answers a question from the vault, citing the notes used.

    With no_llm the matching notes and passages are returned without an answer.
    `who` is "local" or "claude"; [memory].answerer (or HAL_ANSWERER) by default.
    """
    hits = search(question, limit)
    notes = [h["note"] for h in hits]
    if not hits:
        return {"answer": "Nothing in the vault mentions that.", "notes": [], "passages": []}
    if no_llm:
        listing = "\n\n".join(f"[[{h['note']}]] ({h['path']})\n{h['snippet']}" for h in hits)
        return {"answer": f"Notes matching: {question}\n\n{listing}", "notes": notes, "passages": hits}
    words = terms(question)
    context = "\n\n".join(f"[[{h['note']}]] ({h['path']}):\n{_passage(h['path'], words)}" for h in hits)
    prompt = f"Question: {question}\n\nNotes:\n{context[:CONTEXT]}"
    if (who or answerer()) == "claude":
        answer = ask_claude(ANSWER, prompt)
    else:
        answer = llm.chat(ANSWER, prompt, model=model)
    answer = answer.strip()
    if "[[" not in answer:
        answer += "\n\nSources: " + ", ".join(f"[[{n}]]" for n in notes)
    return {"answer": answer, "notes": notes, "passages": hits}


def _passage(rel_path: str, words: list[str], size: int = 900) -> str:
    """Returns about `size` characters of a note's body around the first of `words` it contains."""
    try:
        body = vault.split(vault.inside(Path(rel_path)).read_text(errors="ignore"))[1].strip()
    except (OSError, ValueError):
        return ""
    low = body.lower()
    at = min((i for i in (low.find(w) for w in words) if i >= 0), default=0)
    start = max(0, min(at - size // 3, len(body) - size))
    return body[start:start + size].strip()
