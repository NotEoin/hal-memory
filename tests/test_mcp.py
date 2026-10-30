"""Integration test: `hal-memory mcp` serves the memory tools over MCP stdio."""

import json
import subprocess
import sys

import pytest

pytest.importorskip("halhub")

STARTUP_TIMEOUT = 60  # seconds; the server starts in about a second, CI runners are slower
TOOL_COUNT = 15  # REQ-MEM-03


def _rpc(proc: subprocess.Popen, message: dict) -> dict | None:
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    if "id" not in message:
        return None
    return json.loads(proc.stdout.readline())


def test_memory_mcp_lists_fifteen_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("HAL_CONFIG", str(tmp_path / "config.toml"))
    monkeypatch.setenv("HAL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HAL_STATE_DIR", str(tmp_path / "state"))
    proc = subprocess.Popen(
        [sys.executable, "-m", "halmem", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        }
        assert _rpc(proc, init)["result"]["serverInfo"]
        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        listing = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in listing["result"]["tools"]}
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=STARTUP_TIMEOUT)
    assert len(names) == TOOL_COUNT
    assert "memory_recall" in names
