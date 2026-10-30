# Run idle sorting

While the computer is idle, hal-memory files the inbox, links notes, audits and indexes.

1. Install the unit with Hal. The unit runs `@PYTHON@ -m halmem.idle`.

   ```bash
   hal ext add memory          # clones, runs setup and installs the unit
   ```

2. Run one full pass by hand to see it work.

   ```bash
   python3 -m halmem.idle --once   # sort, fix, index and audit once
   ```

3. Tune it in `~/.config/hal/config.toml`.

   ```toml
   [memory]
   idle_minutes = 10   # idle time before a pass
   batch = 25          # notes per pass
   ```

4. Run single passes on demand through the tools.

   ```bash
   hal-memory sort limit=10    # file inbox notes now
   hal-memory tidy limit=10    # quality pass
   hal-memory index            # update the search index
   ```

| Symptom | Fix |
| --- | --- |
| Nothing is filed | `hal-memory status` shows the inbox size and the last pass; check the unit is running. |
| Passes never start | The desktop was not idle for `idle_minutes`; lower it or run `--once`. |
| Model work waits | Another program holds the GPU; set `embed_on_cpu = true` in `[hal]`. |
| Notes are filed wrongly | They carry `hal: needs-review`; the next pass re-checks them. |
