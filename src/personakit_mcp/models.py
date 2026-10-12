"""Structured tool results (published as ``outputSchema``)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProblemInfo(BaseModel):
    """A file the server skipped: unreadable, schema violation or broken ``set.yml``."""

    path: str = Field(description="Path relative to PERSONAKIT_DIR")
    code: str = Field(description="Lint code: P000, SCHEMA, X000, or OUTSIDE (file resolves outside PERSONAKIT_DIR)")
    persona: str = Field(default="", description="Persona id (SCHEMA, OUTSIDE) or file name (P000)")
    set: str = Field(default="", description="Set folder for X000")
    message: str


class SetMember(BaseModel):
    id: str
    priority: str = Field(description="Effective priority in this set (set.yml overrides the persona default)")


class SetInfo(BaseModel):
    id: str | None = Field(description="Set id; null for the loose set «Ohne Set» (personas no set.yml lists)")
    title: str
    solution: str | None = None
    scope: str | None = None
    status: str | None = None
    owner: str | None = None
    personas: list[SetMember]
    priority_counts: dict[str, int] = Field(description="Number of members per effective priority")
    unknown: list[str] = Field(description="Ids listed in set.yml that match no valid persona (lint X007)")


class SetList(BaseModel):
    root: str
    sets: list[SetInfo]
    problems: list[ProblemInfo]
    hint: str | None = Field(default=None, description="Next step when there is no set.yml")


class Membership(BaseModel):
    set: str | None = Field(description="Set id; null for the loose set")
    priority: str = Field(description="Effective priority in that set")


class PersonaSummary(BaseModel):
    id: str
    archetype: str
    name: str | None = None
    status: str
    evidence_level: str = Field(description="proto = team assumptions, unvalidated; qualitative; statistical")
    version: str
    review_by: str | None = None
    default_priority: str = Field(description="priority in the persona file; sets may override it")
    memberships: list[Membership]
    path: str


class PersonaList(BaseModel):
    root: str
    applied_filters: dict[str, str] = Field(description="Filters that were applied; an omitted filter is not applied")
    total_in_workspace: int
    returned: int
    personas: list[PersonaSummary]
    problems: list[ProblemInfo]
    hint: str | None = Field(default=None, description="Concrete next step when nothing matched")


class LintFinding(BaseModel):
    level: str
    code: str
    set: str
    persona: str
    message: str


class LintResult(BaseModel):
    root: str
    scope: str = Field(description="What was checked")
    personas_checked: int
    sets_checked: int
    errors: int
    warnings: int
    infos: int
    findings: list[LintFinding]
    summary: str


# ------------------------------------------------------------------ probe_status (personakit probe status --json)
class ProbePersonaRun(BaseModel):
    answers: str = Field(description="Answers file of the run, relative to PERSONAKIT_PROBE_DIR")
    model: str = Field(description="Model as recorded in the answers file")
    light: str = Field(description="Worst light of this persona's current pairs in the run: red, yellow or green")
    current_pairs: int = Field(description="Pairs with another current persona that count")


class ProbeStale(BaseModel):
    answers: str
    reason: str = Field(description="Why the run says nothing about today's persona")


class ProbePersona(BaseModel):
    id: str
    version: str = Field(description="Today's version")
    light: str | None = Field(description="Worst light over all current runs; null when no current run exists")
    runs: list[ProbePersonaRun] = Field(description="Current runs, one entry per run (models are not merged)")
    stale: list[ProbeStale] = Field(description="Runs with this persona that do not match today's file")


class ProbeRunPersona(BaseModel):
    id: str
    plan_version: str
    version: str | None = Field(description="Today's version; null when the persona is not in PERSONAKIT_DIR")
    state: str = Field(description="current (same simulate prompt as today), stale or unknown")
    reason: str


class ProbePair(BaseModel):
    a: str
    b: str
    light: str = Field(description="red, yellow, green or none")
    nearness: float | None = Field(description="Similarity between / similarity within (two or more samples)")
    mean: float | None = Field(description="Mean TF-IDF cosine of the answers to the same questions")
    current: bool = Field(description="Both personas current; only these pairs count")


class ProbeRunFinding(BaseModel):
    level: str
    code: str = Field(description="Q code from personakit docs/FORMAT.md")
    subject: str
    message: str


class ProbeRun(BaseModel):
    plan: str
    answers: str
    keywords: str | None
    plan_id: str
    generator: str | None
    model: str | None
    samples: int
    sets: list[str]
    state: str = Field(description="current (all personas current), partial (at least two) or stale (not evaluated)")
    personas: list[ProbeRunPersona]
    pairs: list[ProbePair]
    findings: list[ProbeRunFinding] = Field(description="WARN findings of the evaluation")


class ProbeProblem(BaseModel):
    path: str
    message: str


class ProbeStatusResult(BaseModel):
    generator: str
    limits: list[str] = Field(description="Limits of the method; read them before reporting a light")
    probe_dir: str
    filters: dict[str, str | None] = Field(description="Applied filters; null = not applied")
    hint: str | None = Field(description="Concrete next step when nothing in scope has a current probe")
    personas: list[ProbePersona]
    runs: list[ProbeRun]
    problems: list[ProbeProblem] = Field(description="Skipped probe files and unusable persona files")
