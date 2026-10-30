# Changelog

All notable changes are listed here, newest first.

## 0.1.0 - unreleased

- Packaging: `pyproject.toml`, the `hal-memory` command, the `hal.packs` entry point, CI with
  ruff, an ASCII gate, tests on Python 3.11 to 3.13 and gitleaks.
- Model calls go through `halkit.llm` (gateway aliases `hal-chat`, `hal-embed`). `HAL_CHAT_API`
  and `HAL_CHAT_URL` are gone; with the gateway stopped a call fails instead of using another route.
- Config is read through `halkit.config`: an unknown or invalid `[memory]` key is an error that
  names the key.
- The manifest is schema 2 with tiers, `untrusted_output`, `always_offer` and `content`
  parameters.
- `hal-memory mcp` serves the 15 tools over MCP stdio.
- The 12 slash commands became Agent Skills in `skills/`; `hal-memory skills install` links them
  into any harness and removes the old `~/.claude/commands` links.
- `hal-memory setup` no longer edits `.mcp.json` unless `--write-mcp` is given;
  `hal-memory connect HARNESS` prints the config.
- Note names are confined to the vault.
- The `memory_recall` tool never uses the `claude` answerer.
- Every subprocess call has a timeout.
- All tracked text is ASCII.
- Docs are split into `docs/user`, `docs/howto` and `docs/dev`.
