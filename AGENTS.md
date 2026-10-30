# AGENTS.md

hal-memory: long-term memory in an Obsidian vault, as a Hal pack (`halmem`) and an MCP server.

- Tools: `halmem/tools.py`, declared in `halmem/hal-module.toml` (schema 2). A new tool needs a
  manifest entry with tier and flags, and a test in `tests/test_manifest.py`.
- Skills: `skills/<name>/SKILL.md`; no `$ARGUMENTS`, ASCII only. Installer: `halmem/skillsinstall.py`.
- Tests: `.venv/bin/python -m pytest -q`; lint: `ruff check . && ruff format --check .`;
  ASCII: `scripts/ascii-check.sh`. Tests are hermetic: no network, GPU or real models.
- Rules: tool calls never use the `claude` answerer; note names resolve inside the vault; every
  subprocess has a timeout; setup never edits `.mcp.json` without `--write-mcp`.
- Docs: `docs/README.md` is the index; update the doc and `CHANGELOG.md` with the code.
- Commits: one line, `Add X` or `Fix X`, no body, no trailers.
