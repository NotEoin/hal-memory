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

hal-memory needs Python 3.11 or later, the Hal gateway (or, standalone, Ollama) with an embedding model and a chat model, and an
Obsidian vault. numpy makes semantic search faster but is optional. Importing documents uses
`pdftotext`, `tesseract` and `pandoc` (and `python-pptx` for PowerPoint files).

```bash
hal ext add memory
```

That clones it into the ecosystem's `extensions/` folder, runs `hal-memory setup` (its install
step) and starts the idle sorter with Hal's other services. The unit runs `@PYTHON@ -m halmem.idle`, where Hal's unit renderer fills in the Python that has hal-memory installed. `hal-memory setup` is safe to re-run. It:

| Step | What it does |
| --- | --- |
| Skills | Links `skills/<name>` into `~/.agents/skills`, `~/.config/hal/skills` and, when `~/.claude` exists, `~/.claude/skills`. A folder it did not install is refused unless `hal-memory skills install --force` (then kept as `<name>.bak`). It also removes the old symlinks in `~/.claude/commands`. |
| Command | Symlinks `bin/hal-memory` into `~/.local/bin/`. |
| Document tools | Reports missing `pdftotext`, `tesseract` and `pandoc` with the `apt-get` command; it never runs sudo. |
| Embedding model | Pulls `[hal].embed_model` with `ollama pull` if it is missing. |
| MCP servers | Only with `--write-mcp`; by default `.mcp.json` is left alone and `hal-memory connect HARNESS` prints the config to paste. With the flag it merges `<vault>/.mcp.json`: adds `obsidian` (`uvx mcp-obsidian`) if missing, points `hal-hub` at its launcher, and removes the old `hal` server that ran `hal-mcp.py`. The previous file is kept as `.mcp.json.bak`. |
| Obsidian key | Reminds you to save the Local REST API key with `hal-memory obsidian-key KEY`. |

`hal-memory setup --check` only reports, and exits 1 if anything is left to do.
`--commands-dir`, `--skills-dir`, `--bin-dir` and `--no-pull` change or skip those steps.

## Use

`hal-memory` runs from anywhere. See [commands](docs/user/commands.md), [tools](docs/user/tools.md) and
[configuration](docs/user/configuration.md); the full list is in the [docs index](docs/README.md).

## Skills

`skills/` holds 12 Agent Skills for the vault. See [skills](docs/user/skills.md) and the how-to
[install the skills](docs/howto/install-skills.md).

## Privacy and safety

| Path | Private? | Notes |
| --- | --- | --- |
| Capture, sort, link, search, index, brief | Yes | Local files and local models only. |
| `memory_recall` and every other tool call | Yes | Always answers with the local model, whatever `answerer` says. |
| `hal-memory ask --answerer claude` | No | Not private, not sandboxed: the retrieved passages go to Claude Code (`claude -p`). Off by default (`answerer = "local"`); only a person at the command line can use it. |

A note name given to a tool must resolve inside the vault; `..` and symlinks that leave it are
refused. Setup never edits `.mcp.json` unless you pass `--write-mcp`. See [SECURITY.md](SECURITY.md).

## Run and test

```bash
hal-memory ask "What did I decide about caching?"   # answer from the vault
hal-memory mcp                                      # serve the tools over MCP stdio
python -m pytest -q                                 # hermetic tests, see docs/dev/testing.md
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Changes are listed in
[CHANGELOG.md](CHANGELOG.md).

## Licence

MIT. See [LICENSE](LICENSE).
