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
