"""Protocol 2026-07-28 on the wire (references/mcp-spec.md, S4): server/discover over stdio, no handshake."""

import json
import os
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "personas"

DISCOVER = {
    "jsonrpc": "2.0",
    "id": "discover-1",
    "method": "server/discover",
    "params": {
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "release-check", "version": "1.0.0"},
            "io.modelcontextprotocol/clientCapabilities": {},
        }
    },
}


INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "legacy", "version": "1"}},
}


def _run(request: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, "PERSONAKIT_DIR": str(FIXTURES)}
    return subprocess.run(
        [sys.executable, "-m", "personakit_mcp"],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )


def test_server_discover_over_stdio():
    proc = _run(DISCOVER)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines, f"no answer on stdout – not a pass (stderr: {proc.stderr})"
    message = json.loads(lines[0])
    assert "error" not in message, message
    result = message["result"]
    assert result["resultType"] == "complete"
    assert "2026-07-28" in result["supportedVersions"]
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "personakit-mcp"
    assert result["ttlMs"] > 0 and result["cacheScope"] in ("public", "private")
    assert "personakit-mcp" in proc.stderr and "lese" in proc.stderr  # startup line on stderr, never stdout


def test_legacy_initialize_still_answered():
    """README promises that 2025-11-25 clients connect too; the SDK keeps the old handshake."""
    proc = _run(INITIALIZE)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines, f"no answer on stdout (stderr: {proc.stderr})"
    result = json.loads(lines[0])["result"]
    assert result["protocolVersion"] == "2025-11-25"
    assert result["serverInfo"]["name"] == "personakit-mcp"
