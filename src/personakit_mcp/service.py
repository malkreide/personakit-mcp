"""Read-only view on a personakit folder, independent of MCP.

Everything persona-specific – loading, schema, sets, lint, rendering – comes from
personakit. This module only resolves the configured folder, filters, looks up ids
and phrases the messages the model reads. It never writes.
"""

from __future__ import annotations

import difflib
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from personakit.api import Problem, Workspace, lint_workspace, load_workspace_tolerant
from personakit.lint import ERROR, INFO, WARN, Finding, sort_findings
from personakit.model import SUFFIX, Persona, PersonaError
from personakit.render import render
from personakit.sets import LOOSE_TITLE, Group, build_groups
from personakit.validate import load_schema

from .models import (
    LintFinding,
    LintResult,
    Membership,
    PersonaList,
    PersonaSummary,
    ProblemInfo,
    SetInfo,
    SetList,
    SetMember,
)

ENV_VAR = "PERSONAKIT_DIR"
FORMATS = ("md", "card", "json", "prompt")
MODES = ("simulate", "audience")


class ServiceError(Exception):
    """An anticipated failure; the message is shown to the model as the tool result."""


# ------------------------------------------------------------------ folder
def resolve_root(env: dict[str, str] | None = None) -> Path:
    """The configured personas folder, or a ServiceError that says how to fix the configuration."""
    raw = (env if env is not None else os.environ).get(ENV_VAR, "").strip()
    if not raw:
        raise ServiceError(
            f"{ENV_VAR} ist nicht gesetzt. In der MCP-Konfiguration des Clients den Ordner mit den "
            f"*.persona.md-Dateien angeben, z. B. env: {{{ENV_VAR}: /pfad/zu/personas}}."
        )
    root = Path(raw).expanduser()
    if not root.exists():
        raise ServiceError(f"{ENV_VAR}={raw}: Ordner existiert nicht. Pfad in der MCP-Konfiguration prüfen.")
    if not root.is_dir():
        raise ServiceError(f"{ENV_VAR}={raw}: ist eine Datei, kein Ordner. Den Ordner mit den Personas angeben.")
    if next(root.rglob(f"*{SUFFIX}"), None) is None:
        raise ServiceError(
            f"{ENV_VAR}={raw}: enthält keine *{SUFFIX}-Datei (auch nicht in Unterordnern). "
            "Ist es der richtige Ordner, z. B. personas/ eines personakit-Repos?"
        )
    return root.resolve()


@dataclass
class Snapshot:
    """The folder as read for one tool call."""

    root: Path
    personas: list[Persona]
    groups: list[Group]
    problems: list[ProblemInfo]
    by_id: dict[str, list[Persona]] = field(default_factory=dict)

    def rel(self, path: Path | None) -> str:
        if path is None:
            return "?"
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()


def _inside(root: Path, path: Path | None) -> bool:
    return path is not None and path.resolve().is_relative_to(root)


def load(root: Path) -> Snapshot:
    """Read the folder tolerantly; broken files and files outside the folder become problems."""
    try:
        ws: Workspace = load_workspace_tolerant([root])
    except PersonaError as e:
        raise ServiceError(str(e)) from e
    snap = Snapshot(root=root, personas=[], groups=[], problems=[])
    outside = [p for p in ws.personas if not _inside(root, p.path)]
    snap.personas = [p for p in ws.personas if _inside(root, p.path)]
    snap.groups = build_groups(snap.personas, ws.sets) if outside else ws.groups
    snap.problems = [_problem(snap, pr) for pr in ws.problems] + [
        ProblemInfo(
            path=snap.rel(p.path),
            code="OUTSIDE",
            persona=p.id,
            message=f"Datei liegt (über einen Link) ausserhalb von {ENV_VAR} und wird nicht gelesen",
        )
        for p in outside
    ]
    for p in snap.personas:
        snap.by_id.setdefault(p.id, []).append(p)
    return snap


def _problem(snap: Snapshot, pr: Problem) -> ProblemInfo:
    f = pr.finding
    return ProblemInfo(path=snap.rel(pr.path), code=f.code, persona=f.persona, set=f.set_id, message=f.message)


# ------------------------------------------------------------------ lookup
def check_id(pid: str) -> None:
    if not re.fullmatch(load_schema()["properties"]["id"]["pattern"], pid):
        raise ServiceError(
            f"Ungültige Persona-ID «{pid}»: nur Kleinbuchstaben, Ziffern und Bindestriche, "
            "z. B. eltern-neu-in-zuerich. list_personas zeigt alle IDs."
        )


def _invalid(snap: Snapshot, pid: str) -> list[ProblemInfo]:
    """Problems that belong to a persona with this id (schema violations carry the id)."""
    return [pr for pr in snap.problems if pr.code == "SCHEMA" and pr.persona == pid]


def find(snap: Snapshot, pid: str) -> Persona:
    check_id(pid)
    hits = snap.by_id.get(pid, [])
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        files = ", ".join(snap.rel(p.path) for p in hits)
        raise ServiceError(
            f"Persona-ID «{pid}» ist mehrfach vergeben ({files}; Lint X001). "
            "Erst im Repo bereinigen – der Server wählt nicht still eine Datei aus."
        )
    broken = _invalid(snap, pid)
    if broken:
        details = "; ".join(pr.message for pr in broken)
        raise ServiceError(
            f"Persona «{pid}» ({broken[0].path}) verletzt das Schema und wird nicht ausgegeben: {details}"
        )
    close = difflib.get_close_matches(pid, sorted(snap.by_id), n=3, cutoff=0.5)
    near = f" Ähnlich: {', '.join(close)}." if close else ""
    raise ServiceError(f"Keine Persona mit der ID «{pid}» in {snap.root}.{near} list_personas zeigt alle IDs.")


def memberships(snap: Snapshot, pid: str) -> list[Membership]:
    return [
        Membership(set=g.id or None, priority=m.priority) for g in snap.groups for m in g.members if m.persona.id == pid
    ]


# ------------------------------------------------------------------ tools
def list_sets(snap: Snapshot) -> SetList:
    sets = []
    for g in snap.groups:
        data = g.set.data if g.set else {}
        sets.append(
            SetInfo(
                id=g.id or None,
                title=g.title,
                solution=data.get("solution"),
                scope=data.get("scope"),
                status=data.get("status"),
                owner=data.get("owner"),
                personas=[SetMember(id=m.persona.id, priority=m.priority) for m in g.members],
                priority_counts=dict(Counter(m.priority for m in g.members)),
                unknown=list(g.unknown),
            )
        )
    hint = None
    if not any(g.set for g in snap.groups):
        hint = (
            f"Keine set.yml in {snap.root}: alle {len(snap.personas)} Personas bilden das lose Set «{LOOSE_TITLE}». "
            "list_personas listet sie ohne set-Filter."
        )
    return SetList(root=str(snap.root), sets=sets, problems=snap.problems, hint=hint)


def _summary(snap: Snapshot, p: Persona) -> PersonaSummary:
    d = p.data
    review = d.get("review_by")
    return PersonaSummary(
        id=p.id,
        archetype=p.archetype,
        name=d.get("name") or None,
        status=str(d.get("status", "")),
        evidence_level=str(d.get("evidence_level", "")),
        version=str(d.get("version", "")),
        review_by=str(review) if review else None,
        default_priority=str(d.get("priority", "")),
        memberships=memberships(snap, p.id),
        path=snap.rel(p.path),
    )


def _set_ids(snap: Snapshot) -> list[str]:
    return [g.id for g in snap.groups if g.set]


def _matches(snap: Snapshot, p: Persona, set_id: str | None, status: str | None, priority: str | None) -> bool:
    if status is not None and p.data.get("status") != status:
        return False
    ms = memberships(snap, p.id)
    if set_id is not None:
        ms = [m for m in ms if m.set == set_id]
        if not ms:
            return False
    if priority is not None and not any(m.priority == priority for m in ms):
        return False
    return True


def list_personas(
    snap: Snapshot, set_id: str | None = None, status: str | None = None, priority: str | None = None
) -> PersonaList:
    if set_id is not None and set_id not in _set_ids(snap):
        known = ", ".join(_set_ids(snap)) or "keine (es gibt keine set.yml)"
        raise ServiceError(f"Unbekanntes Set «{set_id}». Vorhandene Sets: {known}. list_sets zeigt Details.")
    applied = {k: v for k, v in (("set", set_id), ("status", status), ("priority", priority)) if v is not None}
    hits = sorted(
        (p for p in snap.personas if _matches(snap, p, set_id, status, priority)),
        key=lambda p: p.id,
    )
    hint = None
    if not hits:
        hint = _empty_hint(snap, set_id, status, priority)
    return PersonaList(
        root=str(snap.root),
        applied_filters=applied,
        total_in_workspace=len(snap.personas),
        returned=len(hits),
        personas=[_summary(snap, p) for p in hits],
        problems=snap.problems,
        hint=hint,
    )


def _empty_hint(snap: Snapshot, set_id: str | None, status: str | None, priority: str | None) -> str:
    if not snap.personas:
        return (
            f"Im Ordner ist keine gültige Persona lesbar ({len(snap.problems)} Datei(en) unter problems). "
            "lint_personas zeigt die Befunde."
        )
    parts = []
    for name, kwargs in (
        (f"set={set_id}", {"set_id": set_id}),
        (f"status={status}", {"status": status}),
        (f"priority={priority}", {"priority": priority}),
    ):
        if next(iter(kwargs.values())) is None:
            continue
        n = sum(
            1
            for p in snap.personas
            if _matches(snap, p, **{"set_id": None, "status": None, "priority": None, **kwargs})
        )
        parts.append(f"nur {name}: {n}")
    detail = "; ".join(parts)
    return (
        f"Keine Persona erfüllt alle Filter zusammen. Ohne Filter: {len(snap.personas)}; {detail}. "
        "priority gilt pro Set (wirksame Priorität). Einen Filter weglassen oder list_sets für die Verteilung aufrufen."
    )


def get_persona(snap: Snapshot, pid: str, fmt: str = "md", mode: str | None = None) -> str:
    if fmt not in FORMATS:
        raise ServiceError(f"Unbekanntes Format «{fmt}». Erlaubt: {', '.join(FORMATS)}.")
    if mode is not None and fmt != "prompt":
        raise ServiceError(
            f"mode gilt nur für format=prompt, nicht für format={fmt}. mode weglassen oder format=prompt."
        )
    if mode is not None and mode not in MODES:
        raise ServiceError(f"Unbekannter mode «{mode}». Erlaubt: {', '.join(MODES)}.")
    p = find(snap, pid)
    if fmt == "prompt":
        return render(p, "prompt", mode=mode or "simulate")
    return render(p, fmt)


def lint(root: Path, snap: Snapshot, pid: str | None = None) -> LintResult:
    report = lint_workspace([root])
    findings: list[Finding] = sort_findings(report.findings)
    scope = f"alle Personas und Sets in {root}"
    if pid is not None:
        check_id(pid)
        if pid not in snap.by_id and not _invalid(snap, pid):
            find(snap, pid)  # raises with suggestions
        sets_of = {
            g.id for g in snap.groups if g.set and (pid in g.unknown or any(m.persona.id == pid for m in g.members))
        }
        findings = [f for f in findings if f.persona == pid or (not f.persona and f.set_id in sets_of)]
        scope = f"Persona «{pid}» und ihre Sets ({', '.join(sorted(sets_of)) or 'keines'})"
    rows = [
        LintFinding(level=f.level, code=f.code, set=f.set_id, persona=f.persona, message=f.message) for f in findings
    ]
    n_err = sum(1 for f in findings if f.level == ERROR)
    n_warn = sum(1 for f in findings if f.level == WARN)
    n_info = sum(1 for f in findings if f.level == INFO)
    checked = f"{len(report.personas)} Personas und {len(report.sets)} Sets geprüft"
    if rows:
        summary = f"{n_err} Fehler, {n_warn} Warnungen, {n_info} Hinweise für {scope} ({checked})."
    else:
        summary = f"0 Befunde für {scope} ({checked})."
    return LintResult(
        root=str(root),
        scope=scope,
        personas_checked=len(report.personas),
        sets_checked=len(report.sets),
        errors=n_err,
        warnings=n_warn,
        infos=n_info,
        findings=rows,
        summary=summary,
    )
