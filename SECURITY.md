# Security

## Reporting a vulnerability

Use the repository's private vulnerability report (the Security tab) and do not open a public
issue. Include the version, what you did and what happened. Expect a first answer within a week.

## What hal-memory protects

- **Vault boundary.** A note name given to `memory_read`, `memory_append` or any tool that opens a
  note must resolve inside `[hal].vault`. `..`, absolute paths elsewhere and symlinks pointing out
  are refused.
- **No vault text leaves the machine from a tool call.** `memory_recall` ignores
  `answerer = "claude"` and uses the local model. Only `hal-memory ask --answerer claude`, run by
  a person, may send passages to Claude Code, and that path is not private and not sandboxed.
- **No config edits by surprise.** `hal-memory setup` leaves `.mcp.json` alone unless
  `--write-mcp` is given. The skills installer replaces only what it installed.
- **Bounded subprocesses.** Every external call (`pdftotext`, `tesseract`, `pandoc`, `git`,
  `ollama`, `claude`) has a timeout.

## What it does not protect

- Note content is untrusted text. Tool results from `memory_search`, `memory_read` and
  `memory_recall` are marked `untrusted_output` so the hub can treat them so; a harness that
  ignores that can be misled by text in a note.
- Anything run outside the Hal hub (for example `hal-memory mcp` under another harness) has only
  the harness's own sandbox.
