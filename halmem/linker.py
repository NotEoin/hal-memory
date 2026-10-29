"""The wikilink pass: turns mentions of existing notes into [[wikilinks]].

Links the first mention of each known note title or alias in a note's body,
leaving frontmatter, code, headings, URLs and existing links alone. Names
shared by two notes are never linked, since Obsidian could not tell them apart.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import vault
from .config import settings

# Regions that must never be rewritten: fenced and inline code, links, URLs and headings.
PROTECTED = re.compile(
    r"```.*?```|~~~.*?~~~|`[^`\n]*`|\[\[[^\]]*\]\]|!?\[[^\]]*\]\([^)]*\)|https?://\S+|^#+ .*$|<[^>\n]+>",
    re.S | re.M,
)


class Linker:
    """Holds the compiled title index so many notes can be linked in one pass."""

    def __init__(self, index: dict[str, Path] | None = None) -> None:
        self.index = index if index is not None else vault.title_index()
        names = sorted(self.index, key=len, reverse=True)
        # One alternation, longest names first, so "Machine Learning Systems" wins over "Machine Learning".
        self.pattern = (
            re.compile(
                r"(?<![\w\[/])(" + "|".join(re.escape(n) for n in names) + r")(?![\w\]])", re.I
            )
            if names
            else None
        )

    def _linkable(self, key: str, found: str) -> bool:
        """A one-word name links only as a proper noun or technical term: capitals in the
        note's title and in the text ("Java", "GitHub"), so everyday words like "time" do not."""
        if " " in key.strip():
            return True
        title = self.index[key].stem
        return bool(re.search(r"[A-Z0-9]", title)) and bool(re.search(r"[A-Z0-9]", found))

    def link_text(self, body: str, self_name: str, limit: int) -> tuple[str, int]:
        """Returns the body with mentions linked, and how many links were added."""
        if self.pattern is None:
            return body, 0
        done = {self_name.lower()}
        for existing in re.findall(r"\[\[([^\]|#]+)", body):
            done.add(existing.strip().lower())
        added = 0
        out = []
        for chunk_start, chunk_end, protected in _segments(body):
            text = body[chunk_start:chunk_end]
            if protected or added >= limit:
                out.append(text)
                continue

            def repl(m: re.Match) -> str:
                nonlocal added
                key = m.group(1).lower()
                if key in done or added >= limit or not self._linkable(key, m.group(1)):
                    return m.group(1)
                done.add(key)
                added += 1
                target = self.index[key].stem
                return f"[[{target}]]" if target == m.group(1) else f"[[{target}|{m.group(1)}]]"

            out.append(self.pattern.sub(repl, text))
        return "".join(out), added

    def link_note(self, path: Path, write: bool = True) -> int:
        """Links one note in place; returns the number of links added."""
        text = path.read_text(errors="ignore")
        block, body = vault.split(text)
        new_body, added = self.link_text(body, path.stem, int(settings()["max_links_per_note"]))
        if added and write:
            path.write_text((f"---\n{block}\n---\n" if block else "") + new_body)
        return added


def _segments(body: str):
    """Yields (start, end, protected) spans covering the whole body."""
    pos = 0
    for m in PROTECTED.finditer(body):
        if m.start() > pos:
            yield pos, m.start(), False
        yield m.start(), m.end(), True
        pos = m.end()
    if pos < len(body):
        yield pos, len(body), False
