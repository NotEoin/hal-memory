# Connect a harness to hal-memory

`hal-memory mcp` serves the 15 memory tools over MCP stdio. `hal-memory connect` prints the
config for your harness; nothing edits your config for you.

1. Print the config.

   ```bash
   hal-memory connect claude      # claude, codex, opencode, qwen, goose, hal or json
   ```

2. Paste it where the harness expects it (the first line of the output says where).

3. Restart the harness and ask it to list its tools: `memory_search` and the other 14 appear.

4. To check the server by hand:

   ```bash
   hal-memory tools               # lists the tools with their tier
   hal-memory doctor              # checks the pack
   ```

To have `setup` merge the vault's `.mcp.json` (the `obsidian` and `hal-hub` servers) instead, run
`hal-memory setup --write-mcp`. The old file is kept as `.mcp.json.bak`.

The `codex`, `opencode`, `qwen` and `goose` shapes are unverified; check them against each
harness's docs.

| Symptom | Fix |
| --- | --- |
| The harness shows no memory tools | Run `hal-memory mcp` in a terminal; it should wait silently. An import error means the install is broken. |
| `hal-memory: command not found` in the harness | Use the `json` output, which holds the full path, or run `hal-memory setup` to link the command. |
| Tools answer "vault not found" | Set `[hal].vault` in `~/.config/hal/config.toml`. |
