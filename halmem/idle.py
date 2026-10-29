"""Background daemon: tidies the vault while the computer is idle.

Every minute it checks how long the desktop has been idle (GNOME's idle
monitor, else xprintidle). Once past [memory].idle_minutes, and with the GPU
free, it runs one small step at a time: sort the inbox, fix flagged notes,
update the semantic index, audit changed notes. It stops between steps the
moment the user is back.

    python -m halmem.idle            run the daemon
    python -m halmem.idle --once     one full pass now, ignoring idleness
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

from . import audit, llm, search, sorter
from .config import data_dir, settings

POLL = 60  # seconds


def idle_seconds() -> float:
    """Returns how long the desktop has been idle, or 0 when it cannot tell."""
    try:
        out = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Mutter.IdleMonitor",
                "--object-path",
                "/org/gnome/Mutter/IdleMonitor/Core",
                "--method",
                "org.gnome.Mutter.IdleMonitor.GetIdletime",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        return int(out.strip("()\n, ").split()[-1]) / 1000
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    try:
        return (
            int(subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=5).stdout)
            / 1000
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


def steps(batch: int):
    """The work of one pass, as (name, function) pairs run in order."""
    return [
        ("sort", lambda: sorter.sort(batch)),
        ("fix", lambda: audit.fix(batch)),
        ("index", lambda: search.update_index(batch * 8)),
        ("audit", lambda: audit.audit(2000)),
    ]


def run_pass(check_idle: bool = True) -> list[dict]:
    """Runs one pass and records its outcome; returns the step results."""
    cfg = settings()
    threshold = cfg["idle_minutes"] * 60
    results = []
    for name, fn in steps(cfg["batch"]):
        if check_idle and idle_seconds() < threshold:
            results.append({"step": name, "stopped": "user is back"})
            break
        busy = llm.gpu_busy()
        if busy and name in ("sort", "index"):
            results.append({"step": name, "skipped": f"GPU in use by {busy}"})
            continue
        started = time.time()
        try:
            out = fn()
        except llm.Unavailable as e:
            out = {"error": str(e)}
        except Exception as e:  # noqa: BLE001 - the daemon logs and carries on with the next step
            out = {"error": f"{type(e).__name__}: {e}"}
        results.append({"step": name, "seconds": round(time.time() - started, 1), "result": out})
    (data_dir() / "last-pass.json").write_text(
        json.dumps(
            {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": results}, indent=1, default=str
        )
    )
    return results


def main() -> None:
    if "--once" in sys.argv:
        print(json.dumps(run_pass(check_idle=False), indent=1, default=str))
        return
    while True:
        threshold = settings()["idle_minutes"] * 60
        if idle_seconds() >= threshold:
            for r in run_pass():
                print(json.dumps(r, default=str), flush=True)
        time.sleep(POLL)


if __name__ == "__main__":
    main()
