---
name: morning-brief
description: Build today's local morning brief and put it into today's daily note. Use when the user asks for a morning brief or a plan for the day.
license: MIT
compatibility: Needs the hal-memory command on PATH and a vault set as [hal].vault in ~/.config/hal/config.toml.
metadata:
  source: hal-memory
  version: "0.1.0"
allowed-tools: Bash Read Write
---

# morning-brief: Morning Brief

Pull the day together from the vault, open tasks & today's deadlines, yesterday's wins, the
state of active projects and the last work session, and a "concept of the day" from the topic
graph, and write it into today's daily note as a `Sun Morning Brief` block.

## Step 1: Run the brief
hal-memory builds it locally (it reads and writes files on disk and talks only to the local
model). Run:

```bash
hal-memory brief [--print-only] [--date YYYY-MM-DD]
```

(`hal brief` runs the same command.) It:
- assembles a compact **packet** from the vault (so the 32K window stays light),
- asks the local model for a warm, one-minute brief (falls back to a plain brief if the model
  is down, pass `--no-llm` to force that),
- inserts/replaces the brief block right under today's daily-note H1 (idempotent, re-running
  just refreshes it), and prints the brief to the terminal.

Useful flags: `--print-only` (don't touch the note), `--no-llm` (deterministic, no model call),
`--date YYYY-MM-DD` (build a brief for another day).

## Step 2: Read it back and offer to act
Show the brief, then offer to:
- set the **Top 3 priorities** in today's daily note (ask the user for them),
- carry any **unfinished tasks** forward, and
- open the **concept of the day** stub if they want to flesh it out now.

Keep it tight. The brief is meant to be read in under a minute.

## Scheduling (set once)
This is built to run unattended at 07:00; docs/user/commands.md, "Morning brief", has the
cron line. Cron runs `hal-memory brief` directly; Claude Code isn't needed for the scheduled run.
