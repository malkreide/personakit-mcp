# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Read-only MCP server for a personakit folder (`PERSONAKIT_DIR`), protocol `2026-07-28`, stdio, built on `mcp>=2.0,<3` and personakit `v0.2.0` (`personakit.api`)
- Tools `list_sets`, `list_personas` (filters `set`, `status`, `priority`), `get_persona` (`md`, `card`, `json`, `prompt`), `persona_prompt` (`mode` required) and `lint_personas`; all annotated read-only, idempotent and closed-world
- Prompts `persona_audience` and `persona_simulate` as selectable presets
- Descriptions explain `proto` and mark `simulate` output as a hypothesis, never user research
- Data fidelity: unreadable files, schema violations and broken `set.yml` reported as `problems`; `hint` with a concrete next step on empty results; unknown sets and ids are errors with suggestions; duplicate ids are not resolved silently; files outside the folder are not read
- Tests for parity with `personakit render` and `personakit lint --json`, filter semantics, read-only behaviour and `server/discover` on the wire; 10 evaluation questions
