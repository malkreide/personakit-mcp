"""MCP server: personakit personas as a read-only preset for every session.

Transport is stdio only. The server is stateless: every call re-reads the folder in
PERSONAKIT_DIR, so a ``git pull`` there is visible on the next call.
"""

from __future__ import annotations

import sys
from typing import Annotated, Literal

from mcp.server.caching import CacheHint
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from . import __version__, service
from .models import LintResult, PersonaList, ProbeStatusResult, ProblemInfo, SetList
from .service import ENV_VAR, PROBE_ENV_VAR, ServiceError

EVIDENCE = (
    "`evidence_level` tells how far a persona is grounded: `proto` = assembled from team assumptions in a "
    "workshop, not from research; treat every statement in a proto persona as an unvalidated hypothesis and "
    "keep its `assumptions` visible wherever you use it. `qualitative` = 5–30 interviews or observations; "
    "`statistical` = mixed methods, n > 100."
)
SIMULATE = (
    "`mode=simulate` makes you answer as this persona. Whatever you produce in that mode is a hypothesis for a "
    "quick counter-check, never user research: do not report it as what users said, think or need, and do not "
    "cite it as evidence. `mode=audience` makes you produce content for this persona instead (letters, web "
    "copy, FAQ)."
)
READ_ONLY = f"Read-only: reads the folder in {ENV_VAR} on every call and never writes."
PROBED = (
    "Whether this persona's simulation has been probed for collapse, and against which version, is reported "
    "by `probe_status`."
)

INSTRUCTIONS = f"""personakit-mcp serves evidence-based personas (personakit format) from one local folder.

Start with `list_sets` (which solutions exist, which persona is primary there), then `list_personas`
to filter, then `get_persona` or `persona_prompt` for one persona. `lint_personas` shows the method
checks; `probe_status` shows whether existing collapse-probe runs still match today's personas. {READ_ONLY} Personas are edited in Git with the personakit CLI, not through this server.

{EVIDENCE}

{SIMULATE}"""

ANNOTATIONS = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
STATIC = CacheHint(ttl_ms=3_600_000, scope="public")  # tool and prompt lists never change at runtime

mcp = MCPServer(
    "personakit-mcp",
    title="personakit",
    description="Evidence-based personas from a local personakit folder, read-only",
    instructions=INSTRUCTIONS,
    version=__version__,
    cache_hints={"tools/list": STATIC, "prompts/list": STATIC, "server/discover": STATIC},
    subscriptions=False,  # nothing to notify: the folder is re-read on every call
)

Format = Literal["md", "card", "json", "prompt"]
Mode = Literal["simulate", "audience"]
Status = Literal["draft", "active", "retired"]
Priority = Literal["primary", "secondary", "supplemental", "negative"]
PersonaId = Annotated[str, Field(description="Persona id (slug), e.g. eltern-neu-in-zuerich; see list_personas")]


def _snapshot() -> service.Snapshot:
    try:
        return service.load(service.resolve_root())
    except ServiceError as e:
        raise ToolError(str(e)) from e


def _structured(model: BaseModel, markdown: str) -> CallToolResult:
    """Markdown for the reader, the model as structuredContent (validated against the outputSchema)."""
    return CallToolResult(
        content=[TextContent(type="text", text=markdown)], structured_content=model.model_dump(mode="json")
    )


def _problems_md(problems: list[ProblemInfo]) -> list[str]:
    if not problems:
        return []
    out = ["", f"**Nicht gelesen ({len(problems)}):**"]
    out += [f"- `{p.path}` {p.code}: {p.message}" for p in problems]
    return out


# ------------------------------------------------------------------ tools
@mcp.tool(
    name="list_sets",
    title="List persona sets",
    annotations=ANNOTATIONS,
    description=(
        "List the persona sets in the folder: one set per solution (set.yml) with title, solution, scope, status "
        "and its members with their effective priority there (a set can override the persona's default "
        "priority, so the same persona can be primary in one set and secondary in another). Personas that no "
        "set lists form the loose set «Ohne Set» (id null). Files that could not be read are listed under "
        f"`problems` with their lint code instead of being dropped. {READ_ONLY}"
    ),
)
def list_sets() -> Annotated[CallToolResult, SetList]:
    snap = _snapshot()
    result = service.list_sets(snap)
    lines = [f"# Sets in {result.root}", ""]
    for s in result.sets:
        head = f"## {s.title}" + (f" (`{s.id}`)" if s.id else "")
        lines += [head, ""]
        for label, value in (("Lösung", s.solution), ("Gilt für", s.scope), ("Status", s.status), ("Owner", s.owner)):
            if value:
                lines.append(f"- {label}: {value}")
        lines += [f"- {m.id}: {m.priority}" for m in s.personas]
        if s.unknown:
            lines.append(f"- unbekannt in set.yml (X007): {', '.join(s.unknown)}")
        lines.append("")
    if result.hint:
        lines.append(result.hint)
    lines += _problems_md(result.problems)
    return _structured(result, "\n".join(lines).rstrip() + "\n")


@mcp.tool(
    name="list_personas",
    title="List personas",
    annotations=ANNOTATIONS,
    description=(
        "List personas with id, archetype, status, evidence level, version, review date and their set "
        "memberships. Every filter is optional; an omitted filter is not applied, so without `status` the list "
        "includes draft and retired personas too. `priority` matches the effective priority within a set; "
        "without `set` a persona matches if it has that priority in any set. The result names the applied "
        f"filters and the total in the folder, and carries a `hint` with a next step when nothing matched. "
        f"{EVIDENCE} {READ_ONLY}"
    ),
)
def list_personas(
    set: Annotated[str | None, Field(description="Set id from list_sets; omit for all sets and the loose set")] = None,
    status: Annotated[Status | None, Field(description="draft, active or retired; omit for all")] = None,
    priority: Annotated[Priority | None, Field(description="Effective priority within a set; omit for all")] = None,
) -> Annotated[CallToolResult, PersonaList]:
    snap = _snapshot()
    try:
        result = service.list_personas(snap, set_id=set, status=status, priority=priority)
    except ServiceError as e:
        raise ToolError(str(e)) from e
    filters = ", ".join(f"{k}={v}" for k, v in result.applied_filters.items()) or "keine"
    lines = [
        f"# Personas in {result.root}",
        "",
        f"Filter: {filters} · {result.returned} von {result.total_in_workspace}",
        "",
    ]
    if result.personas:
        lines += ["| id | Archetyp | Status | Evidenz | Version | Sets (Priorität) |", "|---|---|---|---|---|---|"]
        for p in result.personas:
            sets = ", ".join(f"{m.set or 'Ohne Set'} ({m.priority})" for m in p.memberships)
            lines.append(f"| {p.id} | {p.archetype} | {p.status} | {p.evidence_level} | {p.version} | {sets} |")
    if result.hint:
        lines.append(result.hint)
    lines += _problems_md(result.problems)
    return _structured(result, "\n".join(lines) + "\n")


@mcp.tool(
    name="get_persona",
    title="Get one persona",
    annotations=ANNOTATIONS,
    description=(
        "Return one persona rendered by personakit, identical to `personakit render -f <format>`: `md` (full "
        "profile), `card` (one-page summary), `json` (all fields) or `prompt` (a prompt block with the persona's "
        "guardrails; `mode` applies only here and defaults to simulate, like the CLI). The priority inside is "
        "the persona's default; the priority per set is in list_personas. "
        f"{EVIDENCE} {SIMULATE} {READ_ONLY}"
    ),
)
def get_persona(
    id: PersonaId,
    format: Annotated[Format, Field(description="md, card, json or prompt")] = "md",
    mode: Annotated[Mode | None, Field(description="Only with format=prompt: simulate or audience")] = None,
) -> str:
    snap = _snapshot()
    try:
        return service.get_persona(snap, id, fmt=format, mode=mode)
    except ServiceError as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="persona_prompt",
    title="Persona as prompt preset",
    annotations=ANNOTATIONS,
    description=(
        "Return the prompt block of one persona, to use as a preset for the rest of the conversation. `mode` "
        "is required, so the choice between simulating the persona and writing for it is made on purpose. "
        f"{SIMULATE} {PROBED} {EVIDENCE} {READ_ONLY}"
    ),
)
def persona_prompt(
    id: PersonaId,
    mode: Annotated[Mode, Field(description="simulate (answer as the persona) or audience (write for it)")],
) -> str:
    snap = _snapshot()
    try:
        return service.get_persona(snap, id, fmt="prompt", mode=mode)
    except ServiceError as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="lint_personas",
    title="Lint personas",
    annotations=ANNOTATIONS,
    description=(
        "Run personakit's method checks, the same as `personakit lint <folder> --json`: schema, evidence hygiene, "
        "jobs, simulation guardrails, lifecycle and per-set rules. Without `id` the whole folder; with `id` the "
        "findings for that persona plus the set-level findings of the sets it belongs to. The result states how "
        f"many personas and sets were checked, also when there is no finding. {READ_ONLY}"
    ),
)
def lint_personas(
    id: Annotated[str | None, Field(description="Persona id; omit to lint the whole folder")] = None,
) -> Annotated[CallToolResult, LintResult]:
    snap = _snapshot()
    try:
        result = service.lint(snap.root, snap, id)
    except ServiceError as e:
        raise ToolError(str(e)) from e
    lines = [f"# Lint: {result.scope}", "", result.summary]
    if result.findings:
        lines.append("")
        for f in result.findings:
            ctx = " › ".join(x for x in (f.set, f.persona) if x)
            lines.append(f"- {f.level} {f.code}" + (f" [{ctx}]" if ctx else "") + f" {f.message}")
    return _structured(result, "\n".join(lines) + "\n")


@mcp.tool(
    name="probe_status",
    title="Collapse-probe status",
    annotations=ANNOTATIONS,
    description=(
        "Report which collapse-probe runs exist for the personas and whether they still match today's files, "
        f"identical to `personakit probe status <{ENV_VAR}> <{PROBE_ENV_VAR}> --json`. A run was made earlier "
        "outside this server (`personakit probe build`, an external model runner with one fresh conversation per "
        "answer, `personakit probe evaluate`); this tool only reads plans and answers below "
        f"{PROBE_ENV_VAR} and never asks a model. Per persona in a run it compares the simulate prompt stored in "
        "the plan with today's: `current`, `stale` (with the reason, e.g. another version) or `unknown`. Only "
        "pairs of two current personas count; stale runs are not evaluated. Per persona: the worst light of its "
        "current pairs per run (red, yellow, green); runs of different models are kept apart. Green means the "
        "simulated answers differ in wording; it does not mean the persona keeps its voice or is accurate, and "
        "it is no evidence about real users – read `limits` before reporting a light. A persona without a "
        "current run has not been checked: say so, never call it checked. No answer texts are returned. `set` "
        "and `id` are optional; an omitted filter is not applied. Skipped files are listed under `problems`; "
        f"when nothing in scope has a current probe, `hint` names the next step. Read-only: reads {ENV_VAR} and "
        f"{PROBE_ENV_VAR} on every call and never writes."
    ),
)
def probe_status(
    set: Annotated[
        str | None, Field(description="Set id from list_sets: runs whose plan names this set, and its personas")
    ] = None,
    id: Annotated[str | None, Field(description="Persona id: runs with this persona and only its pairs")] = None,
) -> Annotated[CallToolResult, ProbeStatusResult]:
    snap = _snapshot()
    try:
        result, markdown = service.probe_status(snap, service.resolve_probe_dir(), set_id=set, pid=id)
    except ServiceError as e:
        raise ToolError(str(e)) from e
    return _structured(result, markdown)


# ------------------------------------------------------------------ prompts
def _prompt(pid: str, mode: str) -> str:
    """Prompts have no isError result: an anticipated failure goes out as -32602 with the message, not -32603."""
    try:
        snap = service.load(service.resolve_root())
        return service.get_persona(snap, pid, fmt="prompt", mode=mode)
    except ServiceError as e:
        raise MCPError(INVALID_PARAMS, str(e)) from e


@mcp.prompt(
    name="persona_audience",
    title="Write for a persona",
    description=(
        "Preset: everything you produce in this conversation is for this persona (letters, web copy, FAQ, UI "
        "text) and must work in its situation. Carries the persona's guardrails; a proto persona is marked as "
        "a hypothesis."
    ),
)
def persona_audience(id: PersonaId) -> str:
    return _prompt(id, "audience")


@mcp.prompt(
    name="persona_simulate",
    title="Simulate a persona",
    description=(
        "Preset: you answer as this persona for a quick counter-check of a draft or to rehearse an interview. "
        "The answers are hypotheses, never user research, and must not be reported as what users said."
    ),
)
def persona_simulate(id: PersonaId) -> str:
    return _prompt(id, "simulate")


# ------------------------------------------------------------------ entry point
def main() -> None:
    try:
        root = service.resolve_root()
        print(f"personakit-mcp {__version__}: lese {root}", file=sys.stderr)
    except ServiceError as e:  # start anyway: every tool returns the message, which the model can relay
        print(f"personakit-mcp {__version__}: {e}", file=sys.stderr)
    mcp.run("stdio")
