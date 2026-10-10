---
description: Answer a question using ONLY your own notes, with [[wikilink]] citations
argument-hint: "\"your question\"  [--k N] [--show-context] [--no-llm]"
allowed-tools: Bash, Read
---

# /ask — Chat with your brain

Answer a question grounded in the user's own vault. hal-memory finds the most relevant notes
(keyword search merged with its local semantic index), and asks the configured model to answer
**using only those passages**, citing each note it leaned on as an Obsidian `[[wikilink]]`. If
the notes don't cover it, it says so rather than inventing an answer. Retrieval always runs on
the machine; with `answerer = "claude"` in `[memory]` (the cloud setup) Claude Code writes the
answer.

## Step 1 — Ask
```bash
hal-memory ask $ARGUMENTS
```

(`hal ask` runs the same command.) Useful flags:
- `--k N` — retrieve N notes (default 6); raise it for broad "compare/contrast" questions.
- `--show-context` — also print which notes were used and their similarity scores.
- `--no-llm` — show the matching notes and passages only, no model call (fast sanity check).
- `--answerer local|claude` — who writes the answer, overriding `[memory].answerer`.

## Step 2 — Refresh the index if answers look thin
Keyword search works without an index, but meaning-based matches need the semantic index. The
idle service keeps it current; to bring it up to date now (incremental, only changed notes):

```bash
hal-memory index
```

## Step 3 — Present the answer
Show the model's answer verbatim — it already contains inline `[[wikilinks]]` to the notes it
used, so the user can click straight through in Obsidian. Don't add outside knowledge on top; the
whole point is a citation-grounded answer from *their* notes. If nothing matched, try Step 2 and
ask again.

## Also available as MCP tools
The **hal-hub** MCP server exposes the same retrieval as `memory_search`, `memory_recall` and
`memory_read` (through `hal_call`, or directly when pinned), so any MCP client can query the vault.
