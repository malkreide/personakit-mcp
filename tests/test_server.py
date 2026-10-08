"""Tools and prompts through an in-memory MCP client, plus parity with the personakit CLI."""

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest
from conftest import ELTERN, KI
from mcp.client.client import Client
from mcp.shared.exceptions import MCPError
from personakit.cli import main as personakit_cli

from personakit_mcp.server import mcp

pytestmark = pytest.mark.anyio

TOOLS = ["list_sets", "list_personas", "get_persona", "persona_prompt", "lint_personas"]
ALL_IDS = [
    "eltern-neu-in-zuerich",
    "lehrperson-ki-explorierend",
    "schulleitung-entscheidungsorientiert",
    "verwaltungs-insider",
]


async def call(name: str, args: dict | None = None):
    async with Client(mcp) as c:
        return await c.call_tool(name, args or {})


def text(result) -> str:
    return result.content[0].text


def cli(capsys, *argv: str) -> str:
    capsys.readouterr()
    personakit_cli(list(argv))
    return capsys.readouterr().out


def persona_file(root: Path, pid: str) -> Path:
    return next(root.rglob(f"{pid}.persona.md"))


# ------------------------------------------------------------------ surface
async def test_tools_list_is_read_only_cached_and_ordered(root):
    async with Client(mcp) as c:
        result = await c.list_tools()
    assert [t.name for t in result.tools] == TOOLS
    assert result.ttl_ms > 0 and result.cache_scope == "public"
    for t in result.tools:
        a = t.annotations
        assert (a.read_only_hint, a.destructive_hint, a.idempotent_hint, a.open_world_hint) == (
            True,
            False,
            True,
            False,
        )
    schemas = {t.name: t.output_schema for t in result.tools}
    assert schemas["list_personas"] and schemas["list_sets"] and schemas["lint_personas"]


async def test_descriptions_explain_proto_and_simulate():
    async with Client(mcp) as c:
        tools = {t.name: t.description for t in (await c.list_tools()).tools}
        prompts = {p.name: p.description for p in (await c.list_prompts()).prompts}
    for name in ("list_personas", "get_persona", "persona_prompt"):
        assert "`proto`" in tools[name] and "unvalidated hypothesis" in tools[name]
    for name in ("get_persona", "persona_prompt"):
        assert "hypothesis" in tools[name] and "never user research" in tools[name]
    assert "never user research" in prompts["persona_simulate"]
    # mcp-data-fidelity rule 4: no sentence that explains away an empty result
    banned = re.compile(r"usually means|likely|probably|wahrscheinlich|bedeutet meist", re.IGNORECASE)
    for desc in [*tools.values(), *prompts.values(), mcp.instructions or ""]:
        assert not banned.search(desc), desc


# ------------------------------------------------------------------ parity with the CLI
@pytest.mark.parametrize("fmt", ["md", "card", "json"])
async def test_get_persona_equals_cli_render(root, capsys, fmt):
    for pid in ALL_IDS:
        expected = cli(capsys, "render", str(persona_file(root, pid)), "-f", fmt)
        assert text(await call("get_persona", {"id": pid, "format": fmt})) == expected


@pytest.mark.parametrize("mode", ["simulate", "audience"])
async def test_prompt_tools_equal_cli_render(root, capsys, mode):
    pid = "lehrperson-ki-explorierend"
    expected = cli(capsys, "render", str(persona_file(root, pid)), "-f", "prompt", "-m", mode)
    assert text(await call("get_persona", {"id": pid, "format": "prompt", "mode": mode})) == expected
    assert text(await call("persona_prompt", {"id": pid, "mode": mode})) == expected
    async with Client(mcp) as c:
        prompt = await c.get_prompt(f"persona_{mode}", {"id": pid})
    assert prompt.messages[0].content.text == expected


async def test_get_persona_prompt_defaults_to_simulate_like_cli(root, capsys):
    expected = cli(capsys, "render", str(persona_file(root, "verwaltungs-insider")), "-f", "prompt")
    assert text(await call("get_persona", {"id": "verwaltungs-insider", "format": "prompt"})) == expected


@pytest.mark.parametrize("folder", ["clean", "broken"])
async def test_lint_equals_cli_lint_json(request, capsys, folder):
    root = request.getfixturevalue("root" if folder == "clean" else "broken")
    expected = json.loads(cli(capsys, "lint", str(root), "--json"))
    result = (await call("lint_personas")).structured_content
    assert result["findings"] == expected
    assert result["personas_checked"] == 4  # kaputt (P000) and ohne-ziele (SCHEMA) are findings, not personas
    if folder == "clean":
        assert result["findings"] == [] and result["summary"].startswith("0 Befunde")


# ------------------------------------------------------------------ fidelity: nothing dropped silently
async def test_list_personas_counts_every_file(broken):
    data = (await call("list_personas")).structured_content
    files = list(broken.rglob("*.persona.md"))
    persona_problems = [p for p in data["problems"] if p["code"] in ("P000", "SCHEMA")]
    assert data["total_in_workspace"] == len(files) - len({p["path"] for p in persona_problems})
    assert {p["code"] for p in data["problems"]} == {"P000", "SCHEMA", "X000"}
    assert sorted(p["id"] for p in data["personas"]) == ALL_IDS


async def test_omitted_status_equals_all_statuses(root):
    unfiltered = {p["id"] for p in (await call("list_personas")).structured_content["personas"]}
    explicit = set()
    for status in ("draft", "active", "retired"):
        explicit |= {p["id"] for p in (await call("list_personas", {"status": status})).structured_content["personas"]}
    assert unfiltered == explicit == set(ALL_IDS)


async def test_priority_is_the_effective_priority_per_set(root):
    data = (await call("list_personas", {"set": KI, "priority": "primary"})).structured_content
    assert [p["id"] for p in data["personas"]] == ["lehrperson-ki-explorierend"]
    assert data["personas"][0]["default_priority"] == "supplemental"
    assert data["applied_filters"] == {"set": KI, "priority": "primary"}
    across = (await call("list_personas", {"priority": "primary"})).structured_content
    assert {p["id"] for p in across["personas"]} == {"eltern-neu-in-zuerich", "lehrperson-ki-explorierend"}


async def test_empty_result_carries_a_concrete_hint(root):
    data = (await call("list_personas", {"set": ELTERN, "status": "retired"})).structured_content
    assert data["returned"] == 0 and data["personas"] == []
    assert f"nur set={ELTERN}: 3" in data["hint"] and "nur status=retired: 0" in data["hint"]
    assert "list_sets" in data["hint"]


async def test_unknown_set_is_an_error_not_an_empty_list(root):
    r = await call("list_personas", {"set": "gibt-es-nicht"})
    assert r.is_error and ELTERN in text(r) and KI in text(r)


async def test_list_sets(root):
    data = (await call("list_sets")).structured_content
    by_id = {s["id"]: s for s in data["sets"]}
    assert set(by_id) == {ELTERN, KI}
    assert by_id[KI]["status"] == "draft"
    assert {m["id"]: m["priority"] for m in by_id[KI]["personas"]}["lehrperson-ki-explorierend"] == "primary"
    assert by_id[ELTERN]["priority_counts"] == {"primary": 1, "secondary": 1, "negative": 1}
    assert data["hint"] is None and data["problems"] == []


async def test_list_sets_without_set_yml_says_so(root):
    for f in root.rglob("set.yml"):
        f.unlink()
    data = (await call("list_sets")).structured_content
    assert [s["id"] for s in data["sets"]] == [None]
    assert "Keine set.yml" in data["hint"] and "Ohne Set" in data["hint"]


# ------------------------------------------------------------------ errors that guide the next step
async def test_unknown_id_suggests_close_matches(root):
    r = await call("get_persona", {"id": "eltern-neu-in-zuerih"})
    assert r.is_error and "eltern-neu-in-zuerich" in text(r) and "list_personas" in text(r)


async def test_invalid_id_pattern(root):
    r = await call("get_persona", {"id": "../set"})
    assert r.is_error and "Ungültige Persona-ID" in text(r)


async def test_duplicate_id_is_not_resolved_silently(root):
    src = persona_file(root, "verwaltungs-insider")
    shutil.copy(src, root / KI / src.name)
    r = await call("get_persona", {"id": "verwaltungs-insider"})
    assert r.is_error and "mehrfach" in text(r) and "X001" in text(r)


async def test_schema_violation_is_reported_for_its_id(broken):
    r = await call("get_persona", {"id": "ohne-ziele"})
    assert r.is_error and "verletzt das Schema" in text(r)


async def test_mode_only_with_prompt(root):
    r = await call("get_persona", {"id": "verwaltungs-insider", "format": "card", "mode": "audience"})
    assert r.is_error and "nur für format=prompt" in text(r)


async def test_persona_prompt_requires_mode(root):
    r = await call("persona_prompt", {"id": "verwaltungs-insider"})
    assert r.is_error


# ------------------------------------------------------------------ lint for one persona
async def test_lint_for_one_persona(broken, capsys):
    pid = "lehrperson-ki-explorierend"
    data = (await call("lint_personas", {"id": pid})).structured_content
    assert KI in data["scope"]
    for f in data["findings"]:
        assert f["persona"] == pid or (f["persona"] == "" and f["set"] in (ELTERN, KI))
    assert not any(f["code"] in ("P000", "X000") for f in data["findings"])


async def test_prompt_error_carries_the_message(root):
    async with Client(mcp) as c:
        with pytest.raises(MCPError) as exc:
            await c.get_prompt("persona_audience", {"id": "eltern-neu-in-zuerih"})
    assert exc.value.code == -32602 and "eltern-neu-in-zuerich" in exc.value.error.message


async def test_lint_unknown_id(root):
    r = await call("lint_personas", {"id": "niemand"})
    assert r.is_error and "Keine Persona" in text(r)


# ------------------------------------------------------------------ configuration
@pytest.mark.parametrize("case", ["unset", "missing", "file", "empty"])
async def test_configuration_errors_reach_the_model(tmp_path, monkeypatch, case):
    if case == "unset":
        monkeypatch.delenv("PERSONAKIT_DIR", raising=False)
    elif case == "missing":
        monkeypatch.setenv("PERSONAKIT_DIR", str(tmp_path / "fehlt"))
    elif case == "file":
        (tmp_path / "datei.txt").write_text("x", encoding="utf-8")
        monkeypatch.setenv("PERSONAKIT_DIR", str(tmp_path / "datei.txt"))
    else:
        monkeypatch.setenv("PERSONAKIT_DIR", str(tmp_path))
    for tool in ("list_sets", "list_personas", "lint_personas"):
        r = await call(tool)
        assert r.is_error and "PERSONAKIT_DIR" in text(r)


# ------------------------------------------------------------------ safety
def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(root.rglob("*")):
        h.update(f.relative_to(root).as_posix().encode())
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


async def test_server_never_writes(broken):
    before = _tree_hash(broken)
    async with Client(mcp) as c:
        await c.call_tool("list_sets", {})
        await c.call_tool("list_personas", {"status": "active"})
        for fmt in ("md", "card", "json", "prompt"):
            await c.call_tool("get_persona", {"id": "eltern-neu-in-zuerich", "format": fmt})
        await c.call_tool("persona_prompt", {"id": "eltern-neu-in-zuerich", "mode": "audience"})
        await c.call_tool("lint_personas", {})
        await c.call_tool("lint_personas", {"id": "verwaltungs-insider"})
        await c.get_prompt("persona_simulate", {"id": "verwaltungs-insider"})
    assert _tree_hash(broken) == before


async def test_files_outside_the_folder_are_not_read(root, tmp_path):
    outside = tmp_path / "ausserhalb"
    outside.mkdir()
    src = persona_file(root, "verwaltungs-insider")
    target = outside / "fremd.persona.md"
    target.write_text(src.read_text(encoding="utf-8").replace("id: verwaltungs-insider", "id: fremd"), encoding="utf-8")
    try:
        (root / "link.persona.md").symlink_to(target)
    except OSError:
        pytest.skip("symlinks not available")
    data = (await call("list_personas")).structured_content
    assert "fremd" not in {p["id"] for p in data["personas"]}
    assert [p["code"] for p in data["problems"]] == ["OUTSIDE"]
    r = await call("get_persona", {"id": "fremd"})
    assert r.is_error
