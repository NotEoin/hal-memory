# Tools

The 15 memory tools, served by `hal-memory mcp` and through the Hal hub.

| Tool | Does |
| --- | --- |
| `memory_remember`, `memory_fact`, `memory_profile` | Capture to the inbox; lasting facts in the profile note |
| `memory_search`, `memory_recall`, `memory_read`, `memory_append` | Find, answer from, read and add to notes |
| `memory_daily`, `memory_log_conversation`, `memory_brief` | Daily notes, conversation logs, the morning brief |
| `memory_sort`, `memory_link`, `memory_tidy`, `memory_index`, `memory_status` | The idle passes, on demand |

A note name given to `memory_read`, `memory_append` or `memory_link` must resolve inside the vault
(`..` and symlinks are followed first); anything else returns an error entry and is logged.

