# Configuration

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
answerer = "local"       # or "claude": who writes `hal-memory ask` answers (never tool calls)
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
| `HAL_MODEL` | Chat model, as set by the `hal` launcher; default is the `hal-chat` gateway alias |
| `HAL_ANSWERER`, `HAL_UNIVERSITY` | Override `answerer` and `university` |
| `HAL_TOOL_TIMEOUT` | Seconds each external tool call in the import scripts (`pandoc`, `pdftotext`, `tesseract`, `git`) may run before it is stopped; default 120 |


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

