"""Finding things in the vault: keyword search, a semantic index, and question answering.

The semantic index keeps one embedding per note chunk in SQLite and updates
only notes whose modification time changed. numpy speeds up ranking when it
is installed; pure Python is used otherwise.
"""
from __future__ import annotations

import array
import math
import re
import sqlite3
from pathlib import Path

from . import llm, vault
from .config import data_dir

CHUNK = 1200        # characters per chunk
MAX_CHUNKS = 12     # per note, so one huge note cannot dominate the index

ANSWER = """Answer the question using only the vault notes given. Cite every note you use as
[[Note title]]. If the notes do not answer it, say so plainly. Be brief."""


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(data_dir() / "index.db")
    con.execute("""CREATE TABLE IF NOT EXISTS chunks (path TEXT, mtime REAL, n INTEGER, text TEXT, vec BLOB,
                   PRIMARY KEY (path, n))""")
    return con


def keyword(query: str, limit: int = 10) -> list[dict]:
    """Returns notes containing every word of the query, ranked by how often they appear."""
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
    if not words:
        return []
    hits = []
    for p in vault.notes():
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        low = text.lower()
        if all(w in low for w in words):
            score = sum(low.count(w) for w in words) + (5 if all(w in p.stem.lower() for w in words) else 0)
            i = low.find(words[0])
            hits.append((score, p, text[max(0, i - 80):i + 160].replace("\n", " ")))
    hits.sort(key=lambda h: -h[0])
    return [{"note": h[1].stem, "path": vault.rel(h[1]), "snippet": h[2]} for h in hits[:limit]]


def _chunks(text: str) -> list[str]:
    _, body = vault.split(text)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return [body[i:i + CHUNK] for i in range(0, min(len(body), CHUNK * MAX_CHUNKS), CHUNK)] or [""]


def update_index(limit: int | None = None) -> dict:
    """Embeds notes added or changed since the last update; returns counts."""
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
            continue
        vecs = llm.embed([f"{p.stem}\n{c}" for c in chunks])
        con.execute("DELETE FROM chunks WHERE path = ?", (r,))
        con.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?)",
                        [(r, m, i, c, array.array("f", v).tobytes()) for i, (c, v) in enumerate(zip(chunks, vecs))])
        done += 1
        if done % 50 == 0:
            con.commit()
    con.commit()
    return {"embedded": done, "waiting": max(0, len(todo) - done), "removed": len(gone)}


def semantic(query: str, limit: int = 8) -> list[dict]:
    """Returns the note chunks closest in meaning to the query."""
    q = llm.embed([query])[0]
    rows = _db().execute("SELECT path, n, text, vec FROM chunks").fetchall()
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
    """Returns semantic matches when the index is available, merged with keyword matches."""
    results = []
    try:
        results = semantic(query, limit)
    except llm.Unavailable:
        pass
    seen = {r["path"] for r in results}
    for r in keyword(query, limit):
        if r["path"] not in seen:
            results.append(r)
    return results[:limit]


def recall(question: str) -> dict:
    """Answers a question from the vault, citing the notes used."""
    hits = search(question, 6)
    if not hits:
        return {"answer": "Nothing in the vault mentions that.", "notes": []}
    context = "\n\n".join(f"[[{h['note']}]] ({h['path']}):\n{_full(h['path'])}" for h in hits)
    answer = llm.chat(ANSWER, f"Question: {question}\n\nNotes:\n{context[:14000]}")
    return {"answer": answer.strip(), "notes": [h["note"] for h in hits]}


def _full(rel_path: str, limit: int = 2500) -> str:
    try:
        return vault.split(vault.inside(Path(rel_path)).read_text(errors="ignore"))[1][:limit]
    except (OSError, ValueError):
        return ""
