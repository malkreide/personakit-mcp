# personakit-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.10+-blue)

> MCP-Server, der [personakit](https://github.com/malkreide/personakit)-Personas lesend in LLM-Sessions bereitstellt.

🇬🇧 [English Version](README.md)

## Übersicht

personakit hält evidenzbasierte Personas als versionierte Dateien (`*.persona.md`) in Git. Dieser Server macht einen Ordner solcher Dateien in jeder Claude-Session als Voreinstellung verfügbar – die Sets einer Lösung auflisten, eine Persona wählen, sie als Prompt-Block laden, um *für* sie zu schreiben oder *als* sie eine synthetische Gegenprobe zu machen – ohne Dateien zu kopieren. Er liest den Ordner bei jedem Aufruf und schreibt nie; gepflegt werden Personas weiterhin in Git mit der personakit-CLI.

Die ganze Persona-Logik – Laden, Schema, Sets, Lint, Rendern – kommt aus personakit als Bibliothek. Der Server rendert nichts selbst; `get_persona` liefert genau, was `personakit render` liefert.

## Funktionen

- Fünf lesende Tools: Sets, gefilterte Persona-Liste, eine Persona in vier Formaten, Prompt-Voreinstellung, Lint
- Zwei MCP-Prompts (`persona_audience`, `persona_simulate`), die Clients als wählbare Vorlagen anzeigen
- Die Tool-Beschreibungen sagen, was `proto` bedeutet und dass `simulate`-Ausgaben Hypothesen sind, nie Nutzerforschung
- Nichts verschwindet still: unlesbare Dateien, Schema-Verstösse und defekte `set.yml` stehen unter `problems`; ein leeres Ergebnis trägt einen `hint` mit konkretem nächstem Schritt; unbekannte Sets und IDs sind Fehler mit Vorschlägen
- Filter sind explizit: Ein weggelassener Filter gilt nicht, und `priority` ist die wirksame Priorität pro Set
- Protokollstand `2026-07-28` (zustandslos, `server/discover`), Transport stdio

## Voraussetzungen

- Python 3.10+
- Ein Ordner mit personakit-Personas (`*.persona.md`, optional `set.yml` pro Set)
- Ein MCP-Client, der den Protokollstand `2026-07-28` spricht

## Installation

personakit ist noch nicht auf PyPI, deshalb wird der Server vorerst von GitHub installiert:

```bash
uvx --from git+https://github.com/malkreide/personakit-mcp personakit-mcp
```

oder in eine Umgebung:

```bash
pip install git+https://github.com/malkreide/personakit-mcp
```

## Verwendung / Schnellstart

Claude Code, in jeder Session verfügbar (`--scope user`):

```bash
claude mcp add personakit --scope user -e PERSONAKIT_DIR=/pfad/zu/personakit/personas -- uvx --from git+https://github.com/malkreide/personakit-mcp personakit-mcp
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "personakit": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/malkreide/personakit-mcp", "personakit-mcp"],
      "env": { "PERSONAKIT_DIR": "C:\\Users\\ich\\personakit\\personas" }
    }
  }
}
```

Danach zum Beispiel: *«Welche Persona ist für die Lösung Schuleintritt primär? Lade sie als Zielpublikum für einen Elternbrief.»* In Claude Code erscheinen die Prompts als `/mcp__personakit__persona_audience` und `/mcp__personakit__persona_simulate`.

## Verfügbare Tools

| Tool | Beschreibung |
|---|---|
| `list_sets` | Sets (eines pro Lösung) mit Lösung, Gültigkeit, Status und Mitgliedern samt wirksamer Priorität; das lose Set «Ohne Set» |
| `list_personas` | Personas mit Archetyp, Status, Evidenzniveau, Version und Set-Zugehörigkeit; optionale Filter `set`, `status`, `priority` |
| `get_persona` | Eine Persona als `md`, `card`, `json` oder `prompt` (`mode` nur bei `prompt`, Default `simulate`) – identisch mit `personakit render` |
| `persona_prompt` | Prompt-Block einer Persona; `mode` (`simulate` oder `audience`) ist Pflicht |
| `lint_personas` | Methodik-Prüfungen von personakit für den Ordner oder eine Persona (und ihre Sets) – identisch mit `personakit lint --json` |

| Prompt | Beschreibung |
|---|---|
| `persona_audience` | Voreinstellung: für diese Persona schreiben |
| `persona_simulate` | Voreinstellung: als diese Persona antworten – eine Hypothese, keine Nutzerforschung |

Alle Tools tragen `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`.

## Konfiguration

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `PERSONAKIT_DIR` | ja | Ordner mit `*.persona.md`-Dateien, rekursiv durchsucht (typisch `personas/` eines personakit-Repos) |

Fehlt die Variable oder zeigt sie an den falschen Ort, startet der Server trotzdem, und jedes Tool liefert eine Meldung, was zu korrigieren ist. Ein Ordner pro Server-Eintrag; für zwei Ordner den Server zweimal eintragen. Dateien, die ausserhalb des Ordners liegen (Symlinks), werden nicht gelesen.

**Protokollstand:** Der Server zielt auf MCP `2026-07-28` (zustandslos, kein `initialize`-Handshake, `server/discover`). Das MCP-SDK, auf dem er läuft, beantwortet auch den älteren `initialize`-Handshake, Clients auf `2025-11-25` verbinden sich also ebenfalls (am Draht mit beiden geprüft).

## Projektstruktur

```
personakit-mcp/
├── src/personakit_mcp/
│   ├── server.py         # MCPServer: Tools, Prompts, Beschreibungen, Einstiegspunkt
│   ├── service.py        # lesende Sicht auf den Ordner: Filter, Suche, Meldungen (ohne MCP)
│   └── models.py         # strukturierte Ergebnisse (outputSchema)
├── tests/                # Parität mit der personakit-CLI, Datentreue, read-only, Protokoll-Probe
│   └── fixtures/personas # synthetische Beispiel-Personas aus personakit v0.2.0
├── evaluations/          # 10 Fragen für eine LLM-Evaluation (mcp-builder)
├── docs/DESIGN.md        # Design-Notiz und Entscheide
├── server.json           # Metadaten für die MCP-Registry
└── scripts/              # validate_repo.py, check_release_artifacts.py
```

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

## Mitwirken

Beiträge sind willkommen – siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## Sicherheit

Sicherheitslücken bitte wie in [SECURITY.md](SECURITY.md) beschrieben melden.

## Lizenz

MIT License – siehe [LICENSE](LICENSE)

## Autor

Hayal Özkan · [malkreide](https://github.com/malkreide)
