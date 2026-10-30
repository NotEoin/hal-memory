"""Tests that the docs index lists every document under docs/."""

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_docs_index_lists_every_doc():
    index = (DOCS / "README.md").read_text()
    listed = set(re.findall(r"\]\(([^)]+\.md)\)", index))
    found = {p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*.md") if p.name != "README.md"}
    assert listed == found


def test_every_relative_link_in_the_docs_resolves():
    for page in DOCS.rglob("*.md"):
        for target in re.findall(r"\]\((?!https?:|#)([^)#]+)", page.read_text()):
            assert (page.parent / target).exists(), f"{page}: {target}"
