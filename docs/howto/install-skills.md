# Install the skills for a harness

The 12 skills are Agent Skills folders (`skills/<name>/SKILL.md`). The installer links them into
the skills folder your harness reads.

1. List what ships.

   ```bash
   hal-memory skills list                    # the 12 skill names
   ```

2. See what would change, then install. With no `--target`, the targets are `agents`, `hal`, and
   `claude` when `~/.claude` exists.

   ```bash
   hal-memory skills install --check         # report only; exit 1 if anything is left to do
   hal-memory skills install                 # link the skills into the default targets
   hal-memory skills install --target claude # one harness only
   hal-memory skills install --target dir:/path/to/skills --mode copy   # any folder, copied
   ```

3. Check the harness sees them: start it and list its skills.

4. To remove them again, or to replace a folder you made yourself:

   ```bash
   hal-memory skills remove --target claude  # removes only what hal-memory installed
   hal-memory skills install --force         # replaces a foreign folder, keeping <name>.bak
   ```

Targets: `claude` (`~/.claude/skills`), `agents` (`~/.agents/skills`, read by OpenCode), `hal`
(`~/.config/hal/skills`), `codex`, `qwen`, `goose`, and `dir:PATH`. The `codex`, `qwen` and
`goose` paths are unverified; check them against the harness docs.

| Symptom | Fix |
| --- | --- |
| `refused ...: not installed by hal-memory` | A folder of that name is yours. Move it, or use `--force`; the old one is kept as `<name>.bak`. |
| The harness does not list the skills | Its skills folder differs from the target; use `--target dir:PATH`. |
| Old `/name` commands still show in Claude Code | Run `hal-memory setup`; it removes the old symlinks in `~/.claude/commands`. Files you edited there are kept. |
| `no skills found` | Run from a checkout that has `skills/`, or reinstall the package. |
