"""Settings for hal-memory: the [memory] table over defaults, through `halkit.config`.

The shared [hal] table (vault path, models, user name) comes from `halkit.config.hal()`, so a
bad file or key raises `ConfigError` naming the file and key instead of falling back silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from halkit import config as kitconfig
from halkit import paths

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
    "review_below": 0.6,  # classifier confidence under this marks a note needs-review
    "idle_minutes": 10,  # how long the desktop must be idle before a sorting pass
    "batch": 25,  # notes per pass, so a pass never runs for long
    "max_links_per_note": 40,
    "related_min": 0.8,  # semantic similarity a note needs to be listed as Related
    "answerer": "local",  # who writes recall answers: local (the chat model) or claude (claude -p)
    "university": "University",  # root note of the study hierarchy that summarize builds
}


def _keys() -> tuple[kitconfig.Key, ...]:
    docs = {
        "folders": "Where the sorter files each kind of note, relative to the vault root",
        "answerer": "Who writes recall answers: local (the chat model) or claude (claude -p)",
        "review_below": "Classifier confidence under this marks a note needs-review",
        "idle_minutes": "Minutes the desktop must be idle before a sorting pass",
        "batch": "Notes per sorting pass, so a pass never runs for long",
        "related_min": "Semantic similarity a note needs to be listed as Related",
    }
    keys = []
    for name, default in DEFAULTS.items():
        kind = type(default)
        keys.append(
            kitconfig.Key(
                name,
                (int, float) if kind is float else kind,
                default,
                choices=("local", "claude") if name == "answerer" else None,
                doc=docs.get(name, name.replace("_", " ")),
            )
        )
    return tuple(keys)


MEMORY_TABLE = kitconfig.register(kitconfig.Table(name=SECTION, keys=_keys(), owner="hal-memory"))


def config_path() -> Path:
    """Returns the shared config file; HAL_CONFIG overrides it, read on every call."""
    return paths.config_file()


def settings() -> dict:
    """Returns this module's settings merged over its defaults; raises `ConfigError` if bad."""
    return dict(kitconfig.load(MEMORY_TABLE))


def shared() -> Mapping[str, object]:
    """Returns the ecosystem-wide `[hal]` settings."""
    return kitconfig.hal()


def user_name() -> str:
    """Returns `[hal].user_name`, or an empty string when it is not set."""
    return str(shared()["user_name"]).strip()


def vault() -> Path:
    """Returns the vault root from `[hal].vault`."""
    return Path(str(shared()["vault"])).expanduser()


def data_dir() -> Path:
    """Returns this module's data directory, creating it."""
    path = paths.data_dir() / SECTION
    path.mkdir(parents=True, exist_ok=True)
    return path
