# Architecture

hal-memory is a pack for Hal's hub: one distribution (`hal-memory`), one package (`halmem`), one
manifest (`halmem/hal-module.toml`, schema 2, `pack = "memory"`).

| Part | Where | Job |
| --- | --- | --- |
| Tools | `halmem/tools.py` | The 15 functions the manifest names. Note names resolve inside the vault only. |
| Command line | `halmem/__main__.py`, `halmem/cli.py` | Subcommands, tool passthrough, and the pack commands (`mcp`, `tools`, `call`, `doctor`) from `halhub.pack`. |
| Config | `halmem/config.py` | The `[memory]` table, registered with `halkit.config`; `[hal]` comes from `halkit.config.hal()`. |
| Vault | `halmem/vault.py`, `capture.py`, `sorter.py`, `linker.py`, `audit.py` | Reading, capture, filing, wikilinks and the quality audit. |
| Search | `halmem/search.py` | Keyword plus semantic search, and recall. |
| Models | `halmem/llm.py` | Chat and embeddings through `halkit.llm` (gateway aliases `hal-chat`, `hal-embed`); retries and the GPU guard. |
| Skills | `skills/`, `halmem/skillsinstall.py` | The 12 Agent Skills and their installer. |
| Setup | `halmem/install.py`, `halmem/connect.py` | `setup` and `connect`. |
| Idle service | `halmem/idle.py`, `systemd/hal-memory-idle.service` | Sorting passes while the desktop is idle. |

Decisions:

- A tool call never uses the `claude` answerer, whatever the config says: vault text must not
  leave the machine because a model asked (`tools.recall`).
- Setup does not edit `.mcp.json` unless `--write-mcp` is given; `connect` prints config instead.
- The installer replaces only what it installed or what is byte-identical to a shipped skill.
- Model calls go through `halkit.llm` only; `tests/test_llm.py` scans the package for direct Ollama
  or HTTP use. With the Hal gateway stopped a call raises `Unavailable`, never a direct URL.
  A standalone install (no `hal-gateway`) reaches `[hal].ollama_url` inside `halkit.llm`.
