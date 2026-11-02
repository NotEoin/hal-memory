"""Tests for the WSL2 differences: platform check, idle monitor, GPU guard and vault location."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from halmem import hostplatform, idle, install, llm


@pytest.fixture
def wsl2(tmp_path, monkeypatch):
    """Fakes a WSL2 kernel release."""
    release = tmp_path / "osrelease"
    release.write_text("5.15.153.1-microsoft-standard-WSL2\n")
    monkeypatch.setenv(hostplatform.OSRELEASE_ENV, str(release))


@pytest.fixture
def plain_linux(tmp_path, monkeypatch):
    """Fakes a plain Linux kernel release."""
    release = tmp_path / "osrelease"
    release.write_text("6.8.0-generic\n")
    monkeypatch.setenv(hostplatform.OSRELEASE_ENV, str(release))


def _no_tools(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError(args[0][0])

    monkeypatch.setattr(idle.subprocess, "run", missing)


def test_wsl2_kernel_release_is_detected(wsl2):
    assert hostplatform.is_wsl2()


def test_plain_linux_kernel_release_is_not_wsl2(plain_linux):
    assert not hostplatform.is_wsl2()


def test_unreadable_osrelease_is_not_wsl2(tmp_path, monkeypatch):
    monkeypatch.setenv(hostplatform.OSRELEASE_ENV, str(tmp_path / "missing"))
    assert not hostplatform.is_wsl2()


def test_a_path_under_a_windows_drive_is_recognised():
    assert hostplatform.on_windows_drive(Path("/mnt/c/Users/me/vault"))
    assert not hostplatform.on_windows_drive(Path("/mnt/data/vault"))
    assert not hostplatform.on_windows_drive(Path("/home/me/vault"))


def test_idle_daemon_stops_with_advice_on_wsl2_without_an_idle_monitor(wsl2, monkeypatch, capsys):
    _no_tools(monkeypatch)
    monkeypatch.setattr(idle.sys, "argv", ["halmem.idle"])
    monkeypatch.setattr(idle, "settings", lambda: {"idle_minutes": 10})
    with pytest.raises(SystemExit) as stop:
        idle.main()
    assert stop.value.code == idle.NO_IDLE_MONITOR_EXIT
    assert "idle_minutes = 0" in capsys.readouterr().err


def test_idle_daemon_with_zero_idle_minutes_starts_on_wsl2(wsl2, monkeypatch):
    _no_tools(monkeypatch)
    monkeypatch.setattr(idle.sys, "argv", ["halmem.idle"])
    monkeypatch.setattr(idle, "settings", lambda: {"idle_minutes": 0})
    monkeypatch.setattr(idle, "run_pass", lambda: [])

    def stop(_seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(idle.time, "sleep", stop)
    with pytest.raises(KeyboardInterrupt):
        idle.main()


def test_idle_seconds_is_zero_when_no_monitor_answers(plain_linux, monkeypatch):
    _no_tools(monkeypatch)
    assert idle.measure_idle() is None
    assert idle.idle_seconds() == 0.0


def _fake_smi(monkeypatch, text):
    done = subprocess.CompletedProcess([], 0, stdout=text, stderr="")
    monkeypatch.setattr(llm.subprocess, "run", lambda *a, **k: done)
    monkeypatch.setattr(llm, "shared", lambda: {})


def test_unnamed_gpu_process_is_ignored_on_wsl2(wsl2, monkeypatch):
    _fake_smi(monkeypatch, "4242, [N/A]\n")
    assert llm.gpu_busy() is None


def test_unnamed_gpu_process_still_counts_on_plain_linux(plain_linux, monkeypatch):
    _fake_smi(monkeypatch, "4242, [N/A]\n")
    assert llm.gpu_busy() is not None


def test_named_gpu_process_counts_on_wsl2(wsl2, monkeypatch):
    _fake_smi(monkeypatch, "4242, /usr/bin/blender\n")
    assert llm.gpu_busy() == "blender"


def test_setup_warns_when_the_vault_is_on_a_windows_drive_under_wsl2(wsl2, capsys):
    assert install.check_wsl2(Path("/mnt/c/Users/me/vault")) == 1
    assert "slow" in capsys.readouterr().out


def test_setup_accepts_a_vault_in_the_linux_filesystem_under_wsl2(wsl2):
    with tempfile.TemporaryDirectory() as tmp:
        assert install.check_wsl2(Path(tmp)) == 0


def test_setup_says_nothing_about_wsl2_on_plain_linux(plain_linux, capsys):
    assert install.check_wsl2(Path("/mnt/c/vault")) == 0
    assert capsys.readouterr().out == ""
