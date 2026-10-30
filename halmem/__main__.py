"""hal-memory command line: the subcommands in halmem.cli, and every tool in hal-module.toml.

    hal-memory                            list the subcommands and tools
    hal-memory ask|index|brief|...        a subcommand (see below)
    hal-memory mcp|tools|call|doctor      the pack commands of halhub: `mcp` serves the tools
                                          over MCP stdio (no Hal core needed)
    hal-memory TOOL [key=value ...]       run a tool (the module prefix is optional)
    hal-memory --stdin FUNCTION           run a function with JSON arguments on stdin

bin/hal-memory runs this from anywhere; `python3 -m halmem` works inside the repo.
"""

import json
import sys
import tomllib
from pathlib import Path

from halhub import pack
from halhub.cli import PACK_COMMANDS

from . import cli, tools

PACK = "memory"
MANIFEST = Path(__file__).resolve().parent / "hal-module.toml"


def _coerce(value: str, kind: str):
    if kind == "integer":
        return int(value)
    if kind == "number":
        return float(value)
    if kind == "boolean":
        return value.lower() in ("1", "true", "yes", "on")
    if kind == "array":
        return [v.strip() for v in value.split(",") if v.strip()]
    if kind == "object":
        return json.loads(value)
    return value


def _show(result) -> None:
    print(result if isinstance(result, str) else json.dumps(result, indent=2, default=str))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] and argv[0] in PACK_COMMANDS:
        return pack.main(PACK, (PACK,), argv)
    spec = tomllib.loads(MANIFEST.read_text())
    if argv[:1] == ["--stdin"]:
        _show(getattr(tools, argv[1])(**json.loads(sys.stdin.read() or "{}")))
        return 0
    if argv and argv[0] in cli.COMMANDS:
        return cli.run(argv)
    prefix = spec["module"]["name"] + "_"
    by_name = {}
    for t in spec.get("tools", []):
        by_name[t["name"]] = by_name[t["name"].removeprefix(prefix)] = t
    if not argv or argv[0] in ("-h", "--help", "--list", "help"):
        print(__doc__)
        print(cli.__doc__.split("\n\n", 1)[1].rstrip())
        print(
            "\ntools (index and brief name the subcommands above; memory_index and memory_brief the tools):"
        )
        for t in spec.get("tools", []):
            print(f"  {t['name'].removeprefix(prefix):22} {t['description'].splitlines()[0][:80]}")
        return 0
    tool = by_name.get(argv[0])
    if tool is None:
        print(f"no tool {argv[0]}", file=sys.stderr)
        return 2
    params = tool.get("params", {})
    kwargs = {}
    for a in argv[1:]:
        key, _, value = a.partition("=")
        kwargs[key] = _coerce(value, params.get(key, {}).get("type", "string"))
    _show(getattr(tools, tool.get("function", tool["name"]))(**kwargs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
