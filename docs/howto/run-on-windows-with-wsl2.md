# Run on Windows with WSL2

This page shows how to run hal-memory on a Windows 11 PC through WSL2, and which parts of
hal-memory work there. Native Windows and macOS are not supported: hal-memory runs shell
scripts, symlinks, systemd user units and Unix tools such as `pdftotext`. WSL2 runs a real Linux
kernel, so it is the supported route.

Support is new and has not been run on a Windows PC yet. The table after the steps marks every
feature as verified or unverified.

## Steps

1. Enable WSL and install Ubuntu. In an administrator PowerShell on Windows:

   ```powershell
   wsl --install -d Ubuntu-24.04   # installs WSL2 and the distro; reboot when asked
   wsl --status                    # Default Version: 2
   ```

2. Enable systemd inside the distro, so Hal can run the idle sorter as a user unit. Inside Ubuntu:

   ```bash
   printf '[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf   # edit by hand if [boot] exists
   ```

   ```powershell
   wsl --shutdown   # run in PowerShell; stops every WSL distro, then reopen Ubuntu
   ```

   ```bash
   systemctl --user is-system-running   # running or degraded, not "offline"
   ```

3. Put the vault in the Linux filesystem, not under `/mnt/c`. Indexing and sorting read every
   note, and a Windows drive is much slower than the distro's own disk. Set it in the Hal config:

   ```toml
   [hal]
   vault = "~/vault"   # in ~/.config/hal/config.toml, inside Ubuntu
   ```

4. Open the vault from Windows Obsidian through the WSL share, if you use Obsidian on Windows.
   In Obsidian choose "Open folder as vault" and type the path:

   ```text
   \\wsl$\Ubuntu-24.04\home\<you>\vault
   ```

5. Install the tools for importing documents, then install and check hal-memory:

   ```bash
   sudo apt-get update && sudo apt-get install -y poppler-utils tesseract-ocr pandoc   # pdftotext, tesseract, pandoc
   hal packs add memory        # installs the pack
   hal packs setup memory      # runs setup; under WSL2 it also checks where the vault is
   hal-memory setup --check    # reports what is left; a vault on /mnt/c is a warning
   ```

6. Turn off the idle wait. WSLg has no desktop idle monitor, so hal-memory cannot tell when you
   are away. Without this step the idle sorter stops at start with an explanation.

   ```toml
   [memory]
   idle_minutes = 0   # sort at any time; the GPU guard still applies
   ```

7. Optional: an NVIDIA GPU. Install the driver on Windows, not in Ubuntu.

   ```bash
   nvidia-smi   # lists your GPU; if not, update the Windows driver
   ```

## What works under WSL2

"Unverified" means the design expects it to work, but nobody has run it on WSL2. Run the check
in the last column and report the result.

| Feature | Status | How to check |
| --- | --- | --- |
| Platform check (`osrelease` says `microsoft` or `WSL`) | Verified with a fake `osrelease` in the test suite | `python -m pytest -q tests/test_hostplatform.py` |
| Idle sorter stops with advice when no idle monitor exists | Verified with fake missing tools | `python -m halmem.idle` with `idle_minutes = 10` |
| Idle sorter with `idle_minutes = 0` | Verified with fakes; unverified on WSL2 | `python -m halmem.idle --once` |
| `setup --check` warns about a vault under `/mnt/c` | Verified with a fake `osrelease` | `hal-memory setup --check` |
| GPU guard ignores unnamed `nvidia-smi` processes | Verified with a fake `[N/A]` row; unverified that WSL2 prints one | `nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader` |
| Hermetic test suite | Wired into CI on a Windows runner; not yet seen green | The `wsl` job of the CI workflow |
| Search, capture, recall, brief, MCP server | Unverified on WSL2; they use files and the Hal gateway only | `hal-memory ask "test"` |
| Vault on the Linux filesystem | Unverified | `hal-memory setup --check` |
| Vault on `/mnt/c` | Unverified; works at most slowly, and symlinks and case rules differ | Time `hal-memory index` on both |
| Obsidian on Windows reading the vault through `\\wsl$` | Unverified | Open the vault in Obsidian |
| Obsidian Local REST API from WSL2 (`mcp-obsidian`) | Unverified; Windows `localhost` is not reachable from WSL2 unless `networkingMode=mirrored` is set in `.wslconfig` | `curl -s http://127.0.0.1:27123/` inside Ubuntu |
| Document import (`pdftotext`, `tesseract`, `pandoc`) | Unverified; plain Ubuntu packages | `hal-memory setup --check`, the document tools line |
| systemd idle unit | Unverified; needs systemd in `/etc/wsl.conf` | `systemctl --user status hal-memory-idle` |

## Symptoms and fixes

| Symptom | Fix |
| --- | --- |
| The idle unit stops at once and the log says there is no desktop idle monitor | Intended. Set `idle_minutes = 0` (step 6), or sort by hand with `hal-memory sort`. |
| The unit does not restart after that message | Intended: exit status 78 is excluded from restarts. Change the setting, then `systemctl --user restart hal-memory-idle`. |
| `setup --check` warns that the vault is on a Windows drive | Move the vault into `~` and set `[hal].vault` (step 3). |
| Indexing takes very long | The vault is on `/mnt/c`. Move it. |
| Obsidian cannot open `\\wsl$\...` | Start the distro first (`wsl -d Ubuntu-24.04`), then retry. |
| `mcp-obsidian` cannot reach the Local REST API | Windows `localhost` is not WSL2's. Set `networkingMode=mirrored` under `[wsl2]` in `%UserProfile%\.wslconfig`, then `wsl --shutdown` (unverified). |
| Model work waits for the GPU | Another program holds it. Set `embed_on_cpu = true` in `[hal]`, or add the program to `gpu_ignore`. |
| `systemctl --user` says `Failed to connect to bus` | Do step 2, then `wsl --shutdown`. |
| `nvidia-smi` is not found in Ubuntu | Install or update the NVIDIA driver on Windows, then `wsl --shutdown`. Do not install a Linux driver in the distro. |
| `pdftotext` or `pandoc` not found when importing | Run the `apt-get` line in step 5. |
