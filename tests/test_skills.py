"""Tests for the shipped Agent Skills and the installer that puts them in a harness."""

import json
import re
from pathlib import Path

import pytest

from halmem import skillsinstall as si

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SKILL_COUNT = 12  # REQ-MEM-05
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64  # Agent Skills format
MAX_DESCRIPTION = 1024  # Agent Skills format


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text()
    assert text.startswith("---\n")
    block = text.split("\n---\n", 1)[0].removeprefix("---\n")
    return {m.group(1): m.group(2) for m in re.finditer(r"(?m)^([a-z-]+):[ ]?(.*)$", block)}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("HAL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HAL_CONFIG", str(tmp_path / "config.toml"))
    (tmp_path / "home").mkdir()


def test_skills_follow_agent_skills_format():
    files = sorted(SKILLS.glob("*/SKILL.md"))
    assert len(files) == SKILL_COUNT
    for f in files:
        fm = _frontmatter(f)
        assert fm["name"] == f.parent.name
        assert NAME_RE.match(fm["name"]) and len(fm["name"]) <= MAX_NAME
        assert 0 < len(fm["description"]) <= MAX_DESCRIPTION
        assert {"license", "compatibility", "metadata"} <= set(fm)
        text = f.read_text()
        assert "argument-hint" not in text and "$ARGUMENTS" not in text
        text.encode("ascii")


def test_install_links_skills_into_target(tmp_path):
    target = tmp_path / "t"
    report = si.install([target])
    assert report.refused == 0
    assert (target / "ask").is_symlink()
    assert (target / "ask" / "SKILL.md").is_file()
    assert si.install([target]).todo == 0
    state = json.loads(si.state_file().read_text())
    assert set(state[str(target)]) == set(si.skill_names())


def test_install_copy_mode_copies_the_folder(tmp_path):
    target = tmp_path / "t"
    si.install([target], mode="copy")
    assert not (target / "ask").is_symlink()
    assert si.install([target], mode="copy").todo == 0


def test_install_check_changes_nothing(tmp_path):
    target = tmp_path / "t"
    report = si.install([target], check=True)
    assert report.todo == SKILL_COUNT
    assert not target.exists()


def test_install_refuses_foreign_file_without_force(tmp_path):
    target = tmp_path / "t"
    (target / "ask").mkdir(parents=True)
    (target / "ask" / "SKILL.md").write_text("mine\n")
    report = si.install([target])
    assert report.refused == 1
    assert (target / "ask" / "SKILL.md").read_text() == "mine\n"
    forced = si.install([target], force=True)
    assert forced.refused == 0
    assert (target / "ask.bak" / "SKILL.md").read_text() == "mine\n"
    assert (target / "ask").is_symlink()


def test_remove_keeps_foreign_and_removes_installed(tmp_path):
    target = tmp_path / "t"
    si.install([target])
    (target / "ask").unlink()
    (target / "ask").mkdir()
    (target / "ask" / "SKILL.md").write_text("mine\n")
    si.remove([target])
    assert (target / "ask" / "SKILL.md").exists()
    assert not (target / "compress").exists()


def test_install_removes_legacy_command_links(tmp_path):
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "ask.md").symlink_to("/old/hal-memory/claude-commands/ask.md")
    (commands / "compress.md").write_text("edited by hand\n")
    (commands / "jobs.md").write_text("unrelated\n")
    report = si.clean_legacy(commands)
    assert report.todo == 1
    assert not (commands / "ask.md").is_symlink()
    assert (commands / "compress.md").read_text() == "edited by hand\n"
    assert (commands / "jobs.md").exists()


def test_unknown_target_is_refused():
    with pytest.raises(ValueError, match="unknown target"):
        si.resolve_target("emacs")
