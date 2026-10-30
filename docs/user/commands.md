# Commands

The `hal-memory` command and its subcommands.

`hal-memory` runs from anywhere. The `hal` launcher hands `hal ask`, `hal index`, `hal brief` and
`hal summarize` to it.

| Command | What it does |
| --- | --- |
| `hal-memory ask "question" [--k N] [--show-context] [--no-llm] [--answerer local\|claude]` | Answer from the vault, citing notes. `--no-llm` shows the matching notes only. |
| `hal-memory index [--rebuild] [--limit N]` | Update the semantic index now; the idle service does this anyway. |
| `hal-memory brief [--print-only] [--no-llm] [--date D] [--model M]` | Write the morning brief into the daily note. |
| `hal-memory summarize [--course C] [--limit N] [--interactive] [--include-maybe] [--model M] [--mock]` | Summarise outstanding slide decks into study notes, unattended. |
| `hal-memory import stage OLD_VAULT [--dry-run]` | Copy an old vault into `_Import-Staging/` and write `IMPORT-MANIFEST.md`. |
| `hal-memory import prepare [DIR] [--ocr] [--force]` | Extract text from every document and write `SLIDES-REPORT.md`. |
| `hal-memory import extract pdf\|docx\|pptx\|html [DIR] [--ocr] [--force]` | Run one extractor. |
| `hal-memory register-repos [PATH ...] [--github URL [NAME]] [--depth N] [--refresh]` | Add git repos to `Areas/Code/` as hub notes. |
| `hal-memory setup [--check] [--write-mcp]` | See Install. |
| `hal-memory connect claude\|codex\|opencode\|qwen\|goose\|hal\|json` | Print the MCP config that connects that harness to `hal-memory mcp`. The codex, opencode, qwen and goose shapes are unverified. |
| `hal-memory obsidian-key KEY` | Save the Obsidian Local REST API key to `~/.config/hal/obsidian_api_key` (mode 600). |
| `hal-memory mcp` | Serve the 15 memory tools over MCP stdio, through halhub's pack runner; needs no Hal core. `tools`, `call` and `doctor` are the other pack commands. |
| `hal-memory TOOL key=value ...` | Run any tool below, as `python3 -m halmem` does. |

Every tool also runs through hal-hub as `hal-hub memory_<tool>`, and Claude Code reaches them
through hal-hub's MCP server:

```bash
hal-memory remember text="Sam's birthday is 3 March" title="Sam birthday"
hal-memory search query="probe request sniffer tests"
hal-memory recall question="What did I decide about the dissertation caching?"
hal-memory status
python3 -m halmem.idle --once      # one full sort, fix, index and audit pass now
```

## Recall

Recall searches by keyword and by meaning, merges the two by rank, and gives the model short
passages (6000 characters at most) around the matched words, in one call without thinking, so it
is quick enough for a voice turn. Questions are matched on their meaningful words, so "What did I
decide about caching for my dissertation?" searches for *decide*, *caching* and *dissertation*,
and works before the semantic index has been built.

The answer is written by the local chat model, or by Claude Code (`claude -p`, with its own login)
when `answerer = "claude"` is set (this path is not private and not sandboxed) in `[memory]` or `HAL_ANSWERER=claude`. Retrieval is local
either way; with Claude the retrieved passages leave the machine. That is why only the
`hal-memory ask` command, run by you, can use Claude: the `memory_recall` tool (and so any model
or MCP client) always answers with the local model, whatever `answerer` says.


## Morning brief

`hal-memory brief` (`hal brief`, `/morning-brief`, or the `memory_brief` tool) gathers open tasks
and today's deadlines, yesterday's done list, active projects and the last session log, and a
concept of the day (a well-linked study topic that is still a stub). The chat model writes it up;
with `--no-llm`, or when the model is unavailable, the gathered facts are written as they are. The
brief sits between `HAL-BRIEF` markers under the daily note's title, so running it again replaces
it. To have it ready at 07:00:

```cron
0 7 * * *  $HOME/.local/bin/hal-memory brief >> $HOME/.cache/hal-brief.log 2>&1
```

