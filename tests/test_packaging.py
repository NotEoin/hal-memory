"""Tests for the hal-memory wheel: it carries the manifest, scripts and entry points."""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD_TIMEOUT = 120  # seconds; a wheel build of this small package takes about a second


@pytest.fixture(scope="module")
def wheel(tmp_path_factory) -> zipfile.ZipFile:
    pytest.importorskip("hatchling")
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        [sys.executable, "-m", "hatchling", "build", "-t", "wheel", "-d", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=BUILD_TIMEOUT,
    )
    return zipfile.ZipFile(next(out.glob("hal_memory-*.whl")))


@pytest.mark.slow
def test_wheel_contains_manifest_and_script(wheel):
    names = set(wheel.namelist())
    assert "halmem/hal-module.toml" in names
    assert "halmem/ingest/extract-pdfs.sh" in names
    assert "halmem/systemd/hal-memory-idle.service" in names
    assert "halmem/skills/ask/SKILL.md" in names
    entry = next(n for n in names if n.endswith("entry_points.txt"))
    text = wheel.read(entry).decode()
    assert "hal-memory = halmem.__main__:main" in text
    assert "memory = halmem" in text


def test_idle_unit_runs_from_the_package_python():
    unit = (ROOT / "systemd" / "hal-memory-idle.service").read_text()
    assert "ExecStart=@PYTHON@ -m halmem.idle" in unit
    assert "/usr/bin/python3" not in unit
