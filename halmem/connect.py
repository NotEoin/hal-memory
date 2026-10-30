"""Prints the MCP config that connects a harness to the hal-memory server.

The server is `hal-memory mcp` (stdio). Nothing here writes a file: the person copies the
output into the harness's own config, so setup never edits a config it does not own.

Config locations and shapes for `codex`, `opencode`, `qwen` and `goose` follow each project's
documentation as remembered when this was written and are unverified; check them against the
harness's current docs before relying on them.
"""

from __future__ import annotations

import json
import shutil
import sys

NAME = "hal-memory"
HARNESSES = ("claude", "codex", "opencode", "qwen", "goose", "hal", "json")


def server_command() -> list[str]:
    """Returns the argv that starts the MCP server: the `hal-memory` on PATH, else this Python."""
    found = shutil.which("hal-memory")
    return [found, "mcp"] if found else [sys.executable, "-m", "halmem", "mcp"]


def _json(obj: object) -> str:
    return json.dumps(obj, indent=2)


def render(harness: str) -> str:
    """Returns the config text for `harness`; raises `ValueError` for an unknown one."""
    argv = server_command()
    command, args = argv[0], argv[1:]
    if harness == "json":
        return _json({"mcpServers": {NAME: {"command": command, "args": args}}})
    if harness == "claude":
        line = "claude mcp add --scope user " + NAME + " -- " + " ".join(argv)
        return f"# run once:\n{line}"
    if harness == "codex":
        quoted = ", ".join(json.dumps(a) for a in args)
        return (
            "# add to ~/.codex/config.toml\n"
            f"[mcp_servers.{NAME}]\ncommand = {json.dumps(command)}\nargs = [{quoted}]"
        )
    if harness == "opencode":
        body = {"mcp": {NAME: {"type": "local", "command": argv, "enabled": True}}}
        return "# merge into opencode.json\n" + _json(body)
    if harness == "qwen":
        body = {"mcpServers": {NAME: {"command": command, "args": args}}}
        return "# merge into ~/.qwen/settings.json\n" + _json(body)
    if harness == "goose":
        return (
            "# add under extensions: in ~/.config/goose/config.yaml\n"
            f"  {NAME}:\n    type: stdio\n    enabled: true\n    cmd: {json.dumps(command)}\n"
            f"    args: {json.dumps(args)}\n    timeout: 300"
        )
    if harness == "hal":
        return "# Hal finds hal-memory by its hal.packs entry point; no config is needed."
    raise ValueError(f"unknown harness {harness!r}; use one of {', '.join(HARNESSES)}")
