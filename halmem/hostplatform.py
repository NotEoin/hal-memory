"""Tells whether hal-memory runs under WSL2, from the kernel's `osrelease`.

WSL2 kernels say `microsoft-standard-WSL2`. Three things differ there: the desktop idle monitors
do not exist, `nvidia-smi` cannot name Windows processes, and a vault under `/mnt/c` is slow.
`$HALMEM_OSRELEASE` names a file that replaces `/proc/sys/kernel/osrelease`, which is how the
tests fake WSL2.
"""

from __future__ import annotations

import os
from pathlib import Path

OSRELEASE = Path("/proc/sys/kernel/osrelease")
OSRELEASE_ENV = "HALMEM_OSRELEASE"
DOCS_HINT = "docs/howto/run-on-windows-with-wsl2.md"


def is_wsl2() -> bool:
    """True when the kernel release names Microsoft or WSL; False when it cannot be read."""
    path = Path(os.environ.get(OSRELEASE_ENV) or OSRELEASE)
    try:
        text = path.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return False
    return "microsoft" in text.lower() or "WSL" in text


def on_windows_drive(path: Path) -> bool:
    """True when the path is on a Windows drive mounted by WSL, such as `/mnt/c/...`."""
    parts = path.expanduser().parts
    return len(parts) > 2 and parts[1] == "mnt" and len(parts[2]) == 1 and parts[2].isalpha()
