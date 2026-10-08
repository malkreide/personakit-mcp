# personakit-mcp

<!-- mcp-name: io.github.malkreide/personakit-mcp -->

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-blue)

> MCP server that serves [personakit](https://github.com/malkreide/personakit) personas read-only to LLM sessions.

🇩🇪 [Deutsche Version](README.de.md)

## Overview

personakit keeps evidence-based personas as versioned files (`*.persona.md`) in Git. This server makes a folder of those files available in every Claude session as a preset – list the sets of a solution, pick a persona, load it as a prompt block for writing *for* it or for a synthetic counter-check *as* it – without copying files around. It reads the folder on every call and never writes; personas are still edited in Git with the personakit CLI.

All persona logic – loading, schema, sets, lint, rendering – comes from personakit as a library. The server adds no rendering of its own, so `get_persona` returns exactly what `personakit render` returns.

## Features

- Five read-only tools: sets, filtered persona list, one persona in four formats, prompt preset, lint
- Two MCP prompts (`persona_audience`, `persona_simulate`) that clients show as selectable presets
- Tool descriptions say what `proto` means and that `simulate` output is a hypothesis, never user research
- Nothing dropped silently: unreadable files, schema violations and broken `set.yml` are reported as `problems`; an empty result carries a `hint` with a concrete next step; unknown sets and ids are errors with suggestions
- Filters are explicit: an omitted filter is not applied, and `priority` is the effective priority per set
- Protocol `2026-07-28` (stateless, `server/discover`), stdio transport

## Prerequisites

- Python 3.10+
- A folder with personakit personas (`*.persona.md`, optionally `set.yml` per set)
- An MCP client that speaks protocol `2026-07-28`

## Installation

personakit is not on PyPI yet, so the server installs from GitHub for now:

```bash
uvx --from git+https://github.com/malkreide/personakit-mcp personakit-mcp
```

or into an environment:

```bash
pip install git+https://github.com/malkreide/personakit-mcp
```

## Usage / Quickstart

Claude Code, available in every session (`--scope user`):

```bash
claude mcp add personakit --scope user -e PERSONAKIT_DIR=/path/to/personakit/personas -- uvx --from git+https://github.com/malkreide/personakit-mcp personakit-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "personakit": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/malkreide/personakit-mcp", "personakit-mcp"],
      "env": { "PERSONAKIT_DIR": "C:\\Users\\me\\personakit\\personas" }
    }
  }
}
```

Then, for example: *«Which persona is primary for the Schuleintritt solution? Load it as the audience for a letter.»* In Claude Code the prompts appear as `/mcp__personakit__persona_audience` and `/mcp__personakit__persona_simulate`.

## Available Tools

| Tool | Description |
|---|---|
| `list_sets` | Sets (one per solution) with solution, scope, status and members with their effective priority; the loose set «Ohne Set» |
| `list_personas` | Personas with archetype, status, evidence level, version and set memberships; optional filters `set`, `status`, `priority` |
| `get_persona` | One persona as `md`, `card`, `json` or `prompt` (`mode` only for `prompt`, default `simulate`) – identical to `personakit render` |
| `persona_prompt` | Prompt block of one persona; `mode` (`simulate` or `audience`) is required |
| `lint_personas` | personakit's method checks for the folder or one persona (and its sets) – identical to `personakit lint --json` |

| Prompt | Description |
|---|---|
| `persona_audience` | Preset: write for this persona |
| `persona_simulate` | Preset: answer as this persona – a hypothesis, not user research |

All tools are annotated `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `PERSONAKIT_DIR` | yes | Folder with `*.persona.md` files, searched recursively (typically `personas/` of a personakit repository) |

If the variable is missing or points to the wrong place, the server still starts and every tool returns a message that says what to fix. One folder per server entry; register the server twice for two folders. Files that resolve outside the folder (symlinks) are not read.

**Protocol:** the server targets MCP `2026-07-28` (stateless, no `initialize` handshake, `server/discover`). The MCP SDK it runs on also answers the older `initialize` handshake, so clients on `2025-11-25` connect as well (checked on the wire with both).

## Project Structure

```
personakit-mcp/
├── src/personakit_mcp/
│   ├── server.py         # MCPServer: tools, prompts, descriptions, entry point
│   ├── service.py        # read-only view on the folder: filters, lookups, messages (no MCP)
│   └── models.py         # structured results (outputSchema)
├── tests/                # parity with the personakit CLI, fidelity, read-only, protocol probe
│   └── fixtures/personas # synthetic example personas from personakit v0.2.0
├── evaluations/          # 10 questions for an LLM evaluation (mcp-builder)
├── docs/DESIGN.md        # design note and decisions
├── server.json           # MCP registry metadata
└── scripts/              # validate_repo.py, check_release_artifacts.py
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## Contributing

Contributions are welcome – see [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Please report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## License

MIT License – see [LICENSE](LICENSE)

## Author

Hayal Özkan · [malkreide](https://github.com/malkreide)
