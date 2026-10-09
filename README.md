# hal-memory

hal-memory gives Hal a lasting memory in one Obsidian vault. Anything Hal is told to remember
lands in the inbox at once; while the computer is idle, a local model files, titles, tags and links
it, and quality passes keep every note in the vault linked and findable.

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
- Semantic search over the whole vault with local embeddings, merged with keyword search.
- Recall: questions answered from the vault with `[[citations]]`.
- Conversation logs, daily notes and a profile note of lasting facts about the owner.

## Install

hal-memory needs Python 3.11 or later, Ollama with an embedding model and a chat model, and an
Obsidian vault. numpy makes semantic search faster but is optional.

```bash
git clone <url> ~/src/hal-ecosystem/hal-memory
ollama pull embeddinggemma
ln -s ~/src/hal-ecosystem/hal-memory/systemd/hal-memory-idle.service ~/.config/systemd/user/
systemctl --user enable --now hal-memory-idle.service
```

## Use

Every tool runs from the command line, or through hal-hub as `hal-hub memory_<tool>`:

```bash
cd ~/src/hal-ecosystem/hal-memory
python3 -m halmem remember text="Sam's birthday is 3 March" title="Sam birthday"
python3 -m halmem search query="probe request sniffer tests"
python3 -m halmem recall question="What did I decide about the dissertation caching?"
python3 -m halmem status
python3 -m halmem.idle --once      # one full sort, fix, index and audit pass now
```

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

[memory]
idle_minutes = 10        # idle time before a pass
batch = 25               # notes per pass
review_below = 0.6       # confidence under which a filing needs review
[memory.folders]
idea = "Areas/Personal/Ideas"
```

Model work waits while another program holds the GPU; Hal's own voice server does not count. Set
`embed_on_cpu = true` in `[hal]` to keep the semantic index entirely off the GPU (a 300M embedding
model is fast enough on the CPU).

## Licence

MIT. See [LICENSE](LICENSE).
