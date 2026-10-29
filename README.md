# hal-memory

hal-memory gives Hal a lasting memory in one Obsidian vault. Anything Hal is told to remember
lands in the inbox at once; while the computer is idle, a local model files, titles, tags and links
it, and quality passes keep every note in the vault linked and findable. It also brings outside
material in (old vaults, lecture slides, code repos), writes a morning brief, and ships the Claude
Code slash commands that work on the vault.

## Highlights

- Instant capture to `+Inbox/`, with no model in the way.
- Idle-time sorter: classifies each note, files it by category, creates notes for the people,
  organisations, places, projects and topics it mentions, and links them.
- Confidence from the classifier; doubtful filings are marked `hal: needs-review` and re-checked
  by the next pass.
- Wikilink pass: the first mention of any existing note's title or alias becomes a `[[link]]`,
  never inside code, URLs, headings or existing links.
- Quality audit: notes without links, without frontmatter or with no backlinks are recorded and
  fixed in later passes, using semantic neighbours and folder index notes.
- Search by keyword and by meaning (local embeddings), merged by rank, so new notes are found
  before the index catches up.
- Recall: questions answered from the vault with `[[citations]]`, by the local model or by
  Claude Code.
- Import: old vaults staged and inventoried, text pulled from PDF, DOCX, PPTX and HTML, and an
  unattended summariser that turns slide decks into linked study notes.
- A morning brief written into the daily note.
- Conversation logs, daily notes and a profile note of lasting facts about the owner.

## Install

hal-memory needs Python 3.11 or later, Ollama with an embedding model and a chat model, and an
Obsidian vault. numpy makes semantic search faster but is optional. Importing documents uses
`pdftotext`, `tesseract` and `pandoc` (and `python-pptx` for PowerPoint files).

```bash
hal ext add memory
```

That clones it into the ecosystem's `extensions/` folder, runs `hal-memory setup` (its install
step) and starts the idle sorter with Hal's other services. `hal-memory setup` is safe to re-run. It:

| Step | What it does |
| --- | --- |
| Slash commands | Symlinks `claude-commands/*.md` into `~/.claude/commands/`. A different file of the same name is kept as `<name>.md.bak`. |
| Command | Symlinks `bin/hal-memory` into `~/.local/bin/`. |
| Document tools | Reports missing `pdftotext`, `tesseract` and `pandoc` with the `apt-get` command; it never runs sudo. |
| Embedding model | Pulls `[hal].embed_model` with `ollama pull` if it is missing. |
| MCP servers | Merges `<vault>/.mcp.json`: adds `obsidian` (`uvx mcp-obsidian`) if missing, points `hal-hub` at its launcher, and removes the old `hal` server that ran `hal-mcp.py`. The previous file is kept as `.mcp.json.bak`. |
| Obsidian key | Reminds you to save the Local REST API key with `hal-memory obsidian-key KEY`. |

`hal-memory setup --check` only reports, and exits 1 if anything is left to do.
`--commands-dir`, `--bin-dir` and `--no-pull` change or skip those steps.

## Use

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
| `hal-memory setup [--check]` | See Install. |
| `hal-memory obsidian-key KEY` | Save the Obsidian Local REST API key to `~/.config/hal/obsidian_api_key` (mode 600). |
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

| Tool | Does |
| --- | --- |
| `memory_remember`, `memory_fact`, `memory_profile` | Capture to the inbox; lasting facts in the profile note |
| `memory_search`, `memory_recall`, `memory_read`, `memory_append` | Find, answer from, read and add to notes |
| `memory_daily`, `memory_log_conversation`, `memory_brief` | Daily notes, conversation logs, the morning brief |
| `memory_sort`, `memory_link`, `memory_tidy`, `memory_index`, `memory_status` | The idle passes, on demand |

## Recall

Recall searches by keyword and by meaning, merges the two by rank, and gives the model short
passages (6000 characters at most) around the matched words, in one call without thinking, so it
is quick enough for a voice turn. Questions are matched on their meaningful words, so "What did I
decide about caching for my dissertation?" searches for *decide*, *caching* and *dissertation*,
and works before the semantic index has been built.

The answer is written by the local chat model, or by Claude Code (`claude -p`, with its own login)
when `answerer = "claude"` is set in `[memory]` or `HAL_ANSWERER=claude`. Retrieval is local
either way; with Claude the retrieved passages leave the machine.

## Importing old notes and slides

Originals are never modified; everything works on a copy inside the vault.

1. `hal-memory import stage ~/old/Vault` copies it into `_Import-Staging/` and writes
   `IMPORT-MANIFEST.md`, with a list of duplicate file names (the one real risk when moving notes,
   since Obsidian resolves links by name).
2. In Claude Code, `/import-vault` proposes where each folder goes and files the notes with
   frontmatter, folder by folder, after you agree.
3. `hal-memory import prepare` (add `--ocr` for scanned decks) extracts the text of every PDF,
   DOCX, PPTX and HTML file and writes `_Import-Staging/SLIDES-REPORT.md`, marking the decks that
   have no note yet.
4. `hal summarize` (or `/summarize-slides` for a few decks) writes a study note per deck under
   `Areas/Study/<Year>/<Module>/`, links its concepts to stubs in `Areas/Study/Topics/`, and
   rebuilds the module, year and university index notes. Each deck is its own model call and each
   note is saved at once, so a stopped run carries on where it left off.

The summariser uses `HAL_MODEL` when the launcher sets one, else `[hal].chat_model`. When the
launcher runs llama.cpp it sets `HAL_CHAT_API=openai` and `HAL_CHAT_URL`, and every chat call in
hal-memory goes there instead of Ollama. The study root note is named by `[memory].university`.

Code repos join as a linked layer: `hal-memory register-repos ~/code` writes one hub note per
repo into `Areas/Code/` from git metadata only (no code, no file contents, credentials stripped
from remotes), then `/index-repos` fills in summaries from the READMEs.

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

## Slash commands

`claude-commands/` holds the Claude Code commands for the vault: `/load-context`, `/compress`,
`/preserve`, `/daily-note`, `/morning-brief`, `/inbox-process`, `/weekly-review`, `/ask`,
`/meeting-note`, `/summarize-slides`, `/import-vault` and `/index-repos`. See
[SLASH-COMMANDS.md](SLASH-COMMANDS.md).

## How the vault is organised

The sorter files notes by category into these folders by default:

| Category | Folder |
| --- | --- |
| conversation | `Conversations` |
| journal, personal, finance, home, idea | `Areas/Personal/...` |
| health | `Areas/Health` |
| work, project | `Areas/Work`, `Areas/Work/Projects` |
| code | `Areas/Code` |
| study | `Areas/Study/Notes` |
| job | `Areas/Job Search/Notes` |
| person, organisation, place, topic | `People`, `Organisations`, `Places`, `Topics` |
| reference, other | `Resources` |

Hal's own frontmatter keys are `hal` (`inbox`, `filed`, `needs-review`, `needs-index`, `ok`),
`hal-confidence`, `summary` and `type`. Other keys in a note are never changed.

## Configuration

Settings live in the `[memory]` table of `~/.config/hal/config.toml`, and the vault path and
models in `[hal]`:

```toml
[hal]
vault = "~/Documents/vaults/Hal"
chat_model = "qwen3.5:9b"
embed_model = "embeddinggemma"
user_name = ""          # your name in conversation logs and the profile; empty means "You"

[memory]
idle_minutes = 10        # idle time before a pass
batch = 25               # notes per pass
review_below = 0.6       # confidence under which a filing needs review
answerer = "local"       # or "claude": who writes recall answers
university = "University"  # root note of the study hierarchy
[memory.folders]
idea = "Areas/Personal/Ideas"
```

Model work waits while another program holds the GPU; Hal's own voice server does not count. Set
`embed_on_cpu = true` in `[hal]` to keep the semantic index entirely off the GPU (a 300M embedding
model is fast enough on the CPU).

| Variable | Effect |
| --- | --- |
| `HAL_CONFIG`, `HAL_DATA` | Another config file, another data folder (the index lives in `<data>/memory/index.db`) |
| `HAL_VAULT` | Another vault for one run of `import`, `summarize`, `register-repos` and `brief`; search, recall and the index always use `[hal].vault` |
| `HAL_MODEL`, `HAL_CHAT_API`, `HAL_CHAT_URL` | Chat model and server, as set by the `hal` launcher |
| `HAL_ANSWERER`, `HAL_UNIVERSITY` | Override `answerer` and `university` |

## Migrating from the old Hal vault tools

These used to live in the `hal` launcher's repo and now live here:

| Old | Now |
| --- | --- |
| `extract-*.sh`, `prepare-import.sh`, `import-vault.sh`, `register-repos.sh` | `halmem/ingest/`, run as `hal-memory import ...` and `hal-memory register-repos` |
| `summarize-all.py`, `hal_chat.py` | `halmem/summarize.py`, `halmem/llm.py` (`hal summarize`) |
| `morning-brief.py` | `halmem/brief.py` (`hal brief`, `memory_brief`) |
| `vault-index.py`, `hal_rag.py`, `ask.py` | hal-memory's search and recall (`hal index`, `hal ask`) |
| `hal-mcp.py` (the `hal` MCP server) | hal-hub's MCP server, with `memory_search`, `memory_recall` and `memory_read` |
| `claude-commands/`, `SLASH-COMMANDS.md` | Here, linked by `hal-memory setup` |
| `hal obsidian-key` | `hal-memory obsidian-key` |

The old index under `<vault>/System/.rag/` is no longer read and can be deleted. Run
`hal-memory setup` once to replace the `hal` server in the vault's `.mcp.json` with `hal-hub`,
and `hal-memory index` to build the new index (the idle service will also build it, a batch at a
time). `hal ask --mock` is now `--no-llm`; `hal index --mock` is gone.

## Licence

MIT. See [LICENSE](LICENSE).
