"""Settings for hal-memory: the [memory] table of ~/.config/hal/config.toml over DEFAULTS.

The shared [hal] table supplies the vault path and the local model settings.
"""
import os
import tomllib
from pathlib import Path

SECTION = "memory"
DEFAULTS: dict = {
    # Where the sorter files each kind of note, relative to the vault root.
    "folders": {
        "conversation": "Conversations",
        "journal": "Areas/Personal/Journal",
        "personal": "Areas/Personal",
        "health": "Areas/Health",
        "finance": "Areas/Personal/Finance",
        "home": "Areas/Personal/Home",
        "idea": "Areas/Personal/Ideas",
        "work": "Areas/Work",
        "project": "Areas/Work/Projects",
        "code": "Areas/Code",
        "study": "Areas/Study/Notes",
        "job": "Areas/Job Search/Notes",
        "person": "People",
        "organisation": "Organisations",
        "place": "Places",
        "topic": "Topics",
        "reference": "Resources",
        "other": "Resources",
    },
    "inbox": "+Inbox",
    "daily_folder": "Calendar/Daily",
    "profile_note": "System/Profile.md",
    "review_below": 0.6,        # classifier confidence under this marks a note needs-review
    "idle_minutes": 10,         # how long the desktop must be idle before a sorting pass
    "batch": 25,                # notes per pass, so a pass never runs for long
    "max_links_per_note": 40,
    "related_min": 0.8,         # semantic similarity a note needs to be listed as Related
}
SHARED = {
    "vault": "~/Documents/vaults/Hal",
    "ollama_url": "http://localhost:11434",
    "chat_model": "qwen3.5:9b",
    "fast_model": "qwen3.5:4b",
    "embed_model": "embeddinggemma",
    "vision_model": "qwen3-vl:8b",
}


def config_path() -> Path:
    """Returns the shared config file; HAL_CONFIG overrides it, read on every call."""
    return Path(os.environ.get("HAL_CONFIG", "~/.config/hal/config.toml")).expanduser()


def _file() -> dict:
    try:
        return tomllib.loads(config_path().read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def settings() -> dict:
    """Returns this module's settings merged over its defaults."""
    return {**DEFAULTS, **_file().get(SECTION, {})}


def shared() -> dict:
    """Returns the ecosystem-wide settings."""
    return {**SHARED, **_file().get("hal", {})}


def vault() -> Path:
    return Path(shared()["vault"]).expanduser()


def data_dir() -> Path:
    """Returns this module's data directory, creating it."""
    base = Path(os.environ.get("HAL_DATA", "~/.local/share/hal")).expanduser()
    path = base / SECTION
    path.mkdir(parents=True, exist_ok=True)
    return path
