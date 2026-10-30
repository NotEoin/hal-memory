"""Installs hal-memory's Agent Skills into the skills folder of a harness.

Each skill is a folder `<name>/SKILL.md`. `link` mode symlinks the folder to the shipped copy,
so an upgrade of the package updates every harness; `copy` mode copies it.

Design decisions:

- A folder in a target is replaced or removed only when this installer owns it: it is a
  symlink to the shipped folder, its `SKILL.md` is byte-identical to the shipped one, or it
  matches the hash recorded in the state file. Anything else is the user's and is refused
  unless `force` is set, and then it is renamed to `<name>.bak` first.
- The state file `memory-skills.json` under `halkit.paths.state_dir()` maps each target folder
  to the skills installed there and the hash of each `SKILL.md`.
- The legacy cleanup removes only symlinks into a `claude-commands` folder (what the old
  `hal-memory setup` made). The shipped commands no longer exist to compare with, so a
  regular file in `~/.claude/commands` is reported and kept, never deleted.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from halkit import paths
from halkit.files import write_atomic

log = logging.getLogger(__name__)

PACKAGE_SKILLS = Path(__file__).resolve().parent / "skills"
SOURCE_SKILLS = Path(__file__).resolve().parents[1] / "skills"
STATE_NAME = "memory-skills.json"
LEGACY_DIR = "claude-commands"  # the folder the old setup symlinked from
MODES = ("link", "copy")


def _home(*parts: str) -> Path:
    return Path.home().joinpath(*parts)


def targets() -> dict[str, Path]:
    """Returns the known skill targets by name, resolved against the current home."""
    shared = _home(".agents", "skills")
    return {
        "claude": _home(".claude", "skills"),
        "agents": shared,
        "hal": paths.config_dir() / "skills",
        "codex": shared,  # unverified: Codex documents `.agents/skills` per repository
        "qwen": _home(".qwen", "skills"),  # unverified
        "goose": _home(".config", "goose", "skills"),  # unverified
    }


def default_targets() -> list[str]:
    """Returns `agents` and `hal`, plus `claude` when `~/.claude` exists."""
    names = ["agents", "hal"]
    if _home(".claude").is_dir():
        names.append("claude")
    return names


def resolve_target(spec: str) -> Path:
    """Returns the folder for a target name or `dir:PATH`; raises `ValueError` for others."""
    if spec.startswith("dir:") and spec[4:]:
        return Path(spec[4:]).expanduser()
    known = targets()
    if spec not in known:
        raise ValueError(f"unknown target {spec!r}; use {', '.join(known)} or dir:PATH")
    return known[spec]


def shipped_dir() -> Path:
    """Returns the folder that holds the shipped skills (the wheel's, else the checkout's)."""
    return PACKAGE_SKILLS if PACKAGE_SKILLS.is_dir() else SOURCE_SKILLS


def skill_names() -> list[str]:
    """Returns the names of the shipped skills."""
    root = shipped_dir()
    return sorted(p.parent.name for p in root.glob("*/SKILL.md"))


def _sha(skill_dir: Path) -> str | None:
    try:
        return hashlib.sha256((skill_dir / "SKILL.md").read_bytes()).hexdigest()
    except OSError:
        return None


def state_file() -> Path:
    """Returns the file that records what this installer put where."""
    return paths.state_dir() / STATE_NAME


def _load_state() -> dict[str, dict[str, str]]:
    try:
        data = json.loads(state_file().read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, dict[str, str]]) -> None:
    write_atomic(state_file(), json.dumps(state, indent=2, sort_keys=True) + "\n")


@dataclass
class Report:
    """What an install or remove did, or with `check` would do."""

    lines: list[str] = field(default_factory=list)
    todo: int = 0
    refused: int = 0


def _owned(dest: Path, src: Path, recorded: str | None) -> bool:
    if dest.is_symlink():
        try:
            if dest.resolve() == src.resolve():
                return True
        except OSError:
            pass
        return recorded is not None and not dest.exists()
    here = _sha(dest)
    return here is not None and here in (_sha(src), recorded)


def _is_current(dest: Path, src: Path, mode: str) -> bool:
    if mode == "link":
        return dest.is_symlink() and dest.resolve() == src.resolve()
    return not dest.is_symlink() and _sha(dest) == _sha(src)


def _place(src: Path, dest: Path, mode: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if mode == "link":
        dest.symlink_to(src, target_is_directory=True)
    else:
        shutil.copytree(src, dest)


def _clear(dest: Path) -> None:
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    else:
        shutil.rmtree(dest)


def _backup(dest: Path) -> Path:
    bak = dest.with_name(dest.name + ".bak")
    n = 1
    while bak.exists() or bak.is_symlink():
        bak = dest.with_name(f"{dest.name}.bak.{n}")
        n += 1
    dest.rename(bak)
    return bak


def install(
    folders: list[Path],
    *,
    mode: str = "link",
    check: bool = False,
    force: bool = False,
) -> Report:
    """Installs every shipped skill into each folder; with `check`, only reports.

    A folder that is not the installer's is refused (counted in `refused`) unless `force`.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    report = Report()
    root = shipped_dir()
    names = skill_names()
    if not names:
        raise FileNotFoundError(f"no skills found in {root}")
    state = _load_state()
    for folder in dict.fromkeys(folders):
        recorded = state.setdefault(str(folder), {})
        for name in names:
            src, dest = root / name, folder / name
            if not (dest.exists() or dest.is_symlink()):
                action = "install"
            elif _owned(dest, src, recorded.get(name)):
                action = "ok" if _is_current(dest, src, mode) else "update"
            else:
                action = "force" if force else "refuse"
            if action == "ok":
                continue
            report.todo += 1
            if action == "refuse":
                report.refused += 1
                report.lines.append(f"refused {dest}: not installed by hal-memory (use --force)")
                continue
            verb = {"install": "install", "update": "update", "force": "replace"}[action]
            report.lines.append(f"{'would ' if check else ''}{verb} {dest}")
            if check:
                continue
            if action == "force":
                report.lines.append(f"backup {dest} -> {_backup(dest).name}")
            elif action == "update":
                _clear(dest)
            _place(src, dest, mode)
            recorded[name] = _sha(src) or ""
    if not check:
        _save_state({k: v for k, v in state.items() if v})
    return report


def remove(folders: list[Path], *, check: bool = False) -> Report:
    """Removes the skills this installer put in each folder; others are left and reported."""
    report = Report()
    root = shipped_dir()
    state = _load_state()
    for folder in dict.fromkeys(folders):
        recorded = state.get(str(folder), {})
        for name in skill_names():
            dest = folder / name
            if not (dest.exists() or dest.is_symlink()):
                recorded.pop(name, None)
                continue
            if not _owned(dest, root / name, recorded.get(name)):
                report.lines.append(f"kept {dest}: not installed by hal-memory")
                continue
            report.todo += 1
            report.lines.append(f"{'would remove' if check else 'remove'} {dest}")
            if not check:
                _clear(dest)
                recorded.pop(name, None)
        if not recorded:
            state.pop(str(folder), None)
    if not check:
        _save_state(state)
    return report


def clean_legacy(commands_dir: Path, *, check: bool = False) -> Report:
    """Removes the symlinks the old setup made in `commands_dir`; reports other files kept."""
    report = Report()
    for name in skill_names():
        link = commands_dir / f"{name}.md"
        if link.is_symlink() and LEGACY_DIR in Path(os.readlink(link)).parts:
            report.todo += 1
            report.lines.append(f"{'would remove' if check else 'remove'} old command link {link}")
            if not check:
                link.unlink()
        elif link.exists():
            report.lines.append(f"kept {link}: not a link made by hal-memory")
    return report
