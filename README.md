# hal-memory

> *Stop small local models from making things up.*

hal-memory gives Hal a memory in an Obsidian vault, and answers from it with `[[citations]]` you
can click. Tell Hal to remember something and it lands in the inbox at once; while the computer is
idle, a local model files, titles, tags and links it. Ask a question and hal-memory searches by
keyword and by meaning, then hands the model only the notes that matter, so a small model with a
short context answers from your notes instead of guessing.

## What it does

- Captures anything Hal is told to remember into `+Inbox/` at once, with no model in the way.
- While the computer is idle, a local model classifies each note, files it by category, creates
  notes for the people, organisations, places, projects and topics it mentions, and links them.
  Doubtful filings are marked `hal: needs-review` and re-checked by the next pass.
- A wikilink pass turns the first mention of an existing note's title or alias into a `[[link]]`,
  never inside code, URLs, headings or existing links.
- A quality audit records notes without links, frontmatter or backlinks and fixes them in later
  passes.
- Searches by keyword and by meaning (local embeddings) and merges the two by rank, so new notes
  are found before the index catches up.
- Answers questions from the vault with `[[citations]]`, by the local model or by Claude Code.
- Imports old vaults, PDF, DOCX, PPTX and HTML files, and turns slide decks into linked study notes.
- Writes a morning brief into the daily note, keeps conversation logs and a profile note of lasting
  facts about the owner.

## Part of the Hal suite

hal-memory is one part of [Hal](https://github.com/NotEoin/Hal), a modular AI assistant that runs on
your own machine, built privacy and security first. Around Hal,
[hal-tools](https://github.com/NotEoin/hal-tools) adds the tools of a desktop assistant,
[hal-voice](https://github.com/NotEoin/hal-voice) a voice,
[gpu-light](https://github.com/NotEoin/gpu-light) a fair share of the GPU, and
[hal-employment](https://github.com/NotEoin/hal-employment) a job-search helper. Each repo
works on its own; installed together they make one assistant. See [how it fits
together](https://github.com/NotEoin/Hal#how-it-fits-together).

## Requirements

- Linux, or Windows 11 through WSL2 ([how-to](docs/howto/run-on-windows-with-wsl2.md)). Native
  Windows and macOS are unsupported.
- Python 3.11 or later.
- [Hal](https://github.com/NotEoin/Hal), whose gateway serves a chat model and an embedding model.
  Standalone, Ollama can serve both.
- An Obsidian vault (any folder of Markdown notes works).
- Optional: numpy for faster semantic search; `pdftotext`, `tesseract` and `pandoc` for document
  import, and `python-pptx` for PowerPoint files.

## Install

```bash
hal packs add memory        # or: hal packs add --local PATH for a checkout
hal packs setup memory      # runs `hal-memory setup`; each step is shown and confirmed
hal units install           # the idle sorter then starts with Hal's other services
```

The unit runs `@PYTHON@ -m halmem.idle`; Hal's unit renderer fills in the Python that has
hal-memory installed. `hal-memory setup` is safe to re-run. It does the following:

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

## Privacy and safety

| Path | Private? | Notes |
| --- | --- | --- |
| Capture, sort, link, search, index, brief | Yes | Local files and local models only. |
| `memory_recall` and every other tool call | Yes | Always answers with the local model, whatever `answerer` says. |
| `hal-memory ask --answerer claude` | No | Not private, not sandboxed: the retrieved passages go to Claude Code (`claude -p`). Off by default (`answerer = "local"`); only a person at the command line can use it. |

A note name given to a tool must resolve inside the vault; `..` and symlinks that leave it are
refused. Setup never edits `.mcp.json` unless you pass `--write-mcp`. See [SECURITY.md](SECURITY.md).

## Run

```bash
hal-memory ask "What did I decide about caching?"   # answer from the vault
hal-memory index                                    # update the search index
hal-memory brief                                    # write today's morning brief
hal-memory mcp                                      # serve the tools over MCP stdio
```

The commands are in [commands](docs/user/commands.md), the tools in [tools](docs/user/tools.md)
and the settings in [configuration](docs/user/configuration.md). `skills/` holds 12 Agent Skills
for the vault; see [skills](docs/user/skills.md) and [install the skills](docs/howto/install-skills.md).

## Test

```bash
python -m pytest -q                       # hermetic tests, see docs/dev/testing.md
ruff check . && ruff format --check .     # lint and format
```

## Documentation

The [docs index](docs/README.md) lists every page. To contribute, see
[CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md). Changes are listed in
[CHANGELOG.md](CHANGELOG.md).

## Licence

MIT. See [LICENSE](LICENSE).
