---
name: meeting-note
description: Turn a transcript or rough notes into a structured meeting note. Use when the user gives meeting notes or a transcript.
license: MIT
compatibility: Needs the hal-memory command on PATH and a vault set as [hal].vault in ~/.config/hal/config.toml.
metadata:
  source: hal-memory
  version: "0.1.0"
allowed-tools: Bash Read Write Glob
---

# meeting-note -- Process a Meeting

Input: a path to a transcript/recording-transcript/notes file, or the user
will paste the raw notes. If neither is given, ask for the source and the project it relates to.

## Build the note
Create `$HAL_VAULT/Areas/Work/Meetings/YYYY-MM-DD <topic>.md` using
`$HAL_VAULT/System/Templates/Meeting.md`. Fill:
- **Frontmatter:** `type: meeting`, `date` (the meeting's date, ask if unclear),
  `project` (must match an existing project name so it surfaces on that project's page),
  `attendees: [...]`, `status: completed`.
- **Summary** -- 3-6 sentences, what was discussed and why it matters.
- **Decisions** -- concrete decisions made.
- **Action Items** -- as `- [ ]` checkboxes, with owner names where known.
- **Notes** -- supporting detail.

Getting `project` right is what makes the note auto-appear under that project's
"Related Meetings". Confirm the project name before saving. Report the saved path.
