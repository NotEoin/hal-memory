# Migrating from the old Hal vault tools

These used to live in the `hal` launcher's repo and now live here:

| Old | Now |
| --- | --- |
| `extract-*.sh`, `prepare-import.sh`, `import-vault.sh`, `register-repos.sh` | `halmem/ingest/`, run as `hal-memory import ...` and `hal-memory register-repos` |
| `summarize-all.py`, `hal_chat.py` | `halmem/summarize.py`, `halmem/llm.py` (`hal summarize`) |
| `morning-brief.py` | `halmem/brief.py` (`hal brief`, `memory_brief`) |
| `vault-index.py`, `hal_rag.py`, `ask.py` | hal-memory's search and recall (`hal index`, `hal ask`) |
| `hal-mcp.py` (the `hal` MCP server) | hal-hub's MCP server, with `memory_search`, `memory_recall` and `memory_read` |
| `claude-commands/`, `SLASH-COMMANDS.md` | Here as `skills/` and `docs/user/skills.md`, linked by `hal-memory setup` |
| `hal obsidian-key` | `hal-memory obsidian-key` |

The old index under `<vault>/System/.rag/` is no longer read and can be deleted. Run
`hal-memory setup` once to replace the `hal` server in the vault's `.mcp.json` with `hal-hub`,
and `hal-memory index` to build the new index (the idle service will also build it, a batch at a
time). `hal ask --mock` is now `--no-llm`; `hal index --mock` is gone.

