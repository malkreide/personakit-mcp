"""probe_status: parity with `personakit probe status --json`, configuration, fidelity, read-only."""

import hashlib
import json
from pathlib import Path

import pytest
from conftest import ELTERN, KI
from mcp.client.client import Client
from personakit.cli import main as personakit_cli

from personakit_mcp.server import mcp

pytestmark = pytest.mark.anyio
ELTERN_ID = "eltern-neu-in-zuerich"


async def call(args: dict | None = None):
    async with Client(mcp) as c:
        return await c.call_tool("probe_status", args or {})


def cli(capsys, *argv: str) -> str:
    capsys.readouterr()
    personakit_cli(list(argv))
    return capsys.readouterr().out


@pytest.mark.parametrize("args", [[], ["--set", KI], ["--id", ELTERN_ID]])
async def test_equals_cli_probe_status(root, probe, capsys, args):
    expected_json = json.loads(cli(capsys, "probe", "status", str(root), str(probe.resolve()), "--json", *args))
    expected_md = cli(capsys, "probe", "status", str(root), str(probe.resolve()), *args)
    tool_args = {"set": args[1]} if args[:1] == ["--set"] else {"id": args[1]} if args else {}
    r = await call(tool_args)
    assert not r.is_error
    assert r.structured_content == expected_json
    assert r.content[0].text == expected_md


async def test_real_run_current_calibration_run_stale(root, probe):
    data = (await call()).structured_content
    states = {r["answers"]: r["state"] for r in data["runs"]}
    assert states == {"beispiel/answers-haiku.json": "current", "kalibrierung-stufe-3/answers-haiku.json": "stale"}
    stale = next(r for r in data["runs"] if r["state"] == "stale")
    assert stale["pairs"] == [] and all("gleicher Version" in p["reason"] for p in stale["personas"])
    eltern = next(p for p in data["personas"] if p["id"] == ELTERN_ID)
    assert eltern["light"] == "green" and [r["answers"] for r in eltern["runs"]] == ["beispiel/answers-haiku.json"]
    assert data["hint"] is None and data["limits"]


async def test_version_bump_makes_the_persona_unchecked(root, probe):
    f = next(root.rglob(f"{ELTERN_ID}.persona.md"))
    f.write_text(f.read_text(encoding="utf-8").replace('version: "1.1.0"', 'version: "1.2.0"', 1), encoding="utf-8")
    data = (await call({"id": ELTERN_ID})).structured_content
    eltern = data["personas"][0]
    assert eltern["light"] is None and eltern["runs"] == []
    assert any("Plan mit Version 1.1.0, heute 1.2.0" in s["reason"] for s in eltern["stale"])
    assert "keiner passt zum heutigen Stand" in data["hint"]


async def test_no_answer_texts_in_the_result(root, probe):
    answers = json.loads((probe / "beispiel" / "answers-haiku.json").read_text(encoding="utf-8"))
    sample = next(iter(next(iter(answers["answers"].values())).values()))[0]
    snippet = " ".join(sample.split()[:12])
    r = await call()
    assert snippet not in r.content[0].text and snippet not in json.dumps(r.structured_content, ensure_ascii=False)


@pytest.mark.parametrize("case", ["unset", "missing", "file"])
async def test_probe_dir_configuration_errors(root, tmp_path, monkeypatch, case):
    if case == "unset":
        monkeypatch.delenv("PERSONAKIT_PROBE_DIR", raising=False)
    elif case == "missing":
        monkeypatch.setenv("PERSONAKIT_PROBE_DIR", str(tmp_path / "fehlt"))
    else:
        (tmp_path / "datei.txt").write_text("x", encoding="utf-8")
        monkeypatch.setenv("PERSONAKIT_PROBE_DIR", str(tmp_path / "datei.txt"))
    r = await call()
    assert r.is_error and "PERSONAKIT_PROBE_DIR" in r.content[0].text
    if case == "unset":
        assert "nicht, dass sie geprüft ist" in r.content[0].text


async def test_empty_probe_dir_gives_a_hint(root, tmp_path, monkeypatch):
    (tmp_path / "leer").mkdir()
    monkeypatch.setenv("PERSONAKIT_PROBE_DIR", str(tmp_path / "leer"))
    data = (await call({"set": ELTERN})).structured_content
    assert data["runs"] == [] and all(p["light"] is None for p in data["personas"])
    assert "Keine Probe-Läufe" in data["hint"] and f"personas/{ELTERN}" in data["hint"]


async def test_skipped_files_are_problems(root, probe):
    (probe / "notiz.json").write_text('{"text": "keine Probe"}', encoding="utf-8")
    data = (await call()).structured_content
    assert {"path": "notiz.json", "message": "weder Probe-Plan noch Antwortdatei – übersprungen"} in data["problems"]


async def test_unknown_set_and_id_are_errors(root, probe):
    r = await call({"set": "gibt-es-nicht"})
    assert r.is_error and ELTERN in r.content[0].text and KI in r.content[0].text
    r = await call({"id": "eltern-neu-in-zuerih"})
    assert r.is_error and ELTERN_ID in r.content[0].text


async def test_description_does_not_turn_green_into_validity():
    async with Client(mcp) as c:
        tools = {t.name: t.description for t in (await c.list_tools()).tools}
    d = tools["probe_status"]
    assert "does not mean the persona keeps its voice or is accurate" in d
    assert "never call it checked" in d and "No answer texts" in d and "never asks a model" in d
    assert "probe_status" in tools["persona_prompt"]


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(root.rglob("*")):
        h.update(f.relative_to(root).as_posix().encode())
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


async def test_probe_status_never_writes(root, probe):
    before = _tree_hash(root), _tree_hash(probe)
    async with Client(mcp) as c:
        await c.call_tool("probe_status", {})
        await c.call_tool("probe_status", {"set": ELTERN})
        await c.call_tool("probe_status", {"id": ELTERN_ID})
    assert (_tree_hash(root), _tree_hash(probe)) == before
