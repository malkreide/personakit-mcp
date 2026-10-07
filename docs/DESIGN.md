# personakit-mcp – Design-Notiz

Stand 2026-10-07 · Status: angenommen (alle vier offenen Entscheide bestätigt, siehe Abschnitt 10) · Grundlage: personakit `main` (6c2e9ad), github-repo-Skill `references/mcp-spec.md` (Zielstand `2026-07-28`), journeykit ADR-0004, Skills mcp-builder und mcp-data-fidelity.

## 1 Zweck und Abgrenzung

Personas sollen in jeder Claude-Session als Voreinstellung verfügbar sein, ohne Dateien zu kopieren. Der Server liest ein konfiguriertes Personas-Verzeichnis und liefert Listen, Exporte, Prompt-Blöcke und Lint-Befunde. **Er schreibt nie.**

**Verhältnis zu journeykit Variante B (ADR-0004):** Übernommen wird die Architektur «Skill + MCP-Server, der Skill steuert». **Nicht** übernommen wird der Datenbestand im Server (SQLite/Notion, `journey_save`). Bei personakit bleibt die Datei in Git die Quelle der Wahrheit (CLAUDE.md); Versionierung, `bump`, Changelog und Review laufen über Git und die CLI. Ein Server, der schreibt, würde diese Kette umgehen. Variante B heisst hier also «Server als Lesezugang», nicht «Server als Datenbestand».

**Name:** `personakit-mcp` folgt der Konvention `{service}-mcp` der github-repo-Skill. Hinweis am Rand: journeykit plant `journeys-mcp`; für ein konsistentes Portfolio wäre dort `journeykit-mcp` naheliegend. Das ist nicht Teil dieses Auftrags.

## 2 Architektur

```
Claude-Session ──stdio──▶ personakit-mcp                 personakit (Abhängigkeit)
                          server.py   (MCPServer, Tools)   model · validate · sets · lint · render
                          service.py  (Filter, Hinweise) ─▶ api.py (neu, Schritt 0)
                          PERSONAKIT_DIR (nur lesen)
```

- **Python**, MCP-SDK `mcp>=2.0,<3`. Geprüft an den Wheels: `mcp 1.30.0` spricht höchstens `2025-11-25`, ab `mcp 2.0.0` gibt es `server/discover` (aktuell 2.3.0). Vor dem ersten Commit gleiche ich die Untergrenze mit dem SDK-Changelog ab und weise den Stand am Draht nach (mcp-spec S3/S4). Das 2.x-SDK nennt `FastMCP` jetzt `MCPServer`; der Python-Leitfaden in mcp-builder zeigt noch die 1.x-API. Ich übernehme seine Prinzipien, nicht seinen Code.
- **Transport: nur stdio.** Das Verzeichnis ist lokal, Personas können interne Arbeitsstände sein, und ohne HTTP entfallen Auth, Header-Pflichten (`Mcp-Method`/`Mcp-Name`) und Exposition. HTTP lässt sich später ergänzen.
- **Zustandslos:** jeder Aufruf liest das Verzeichnis neu (Dutzende Dateien, Millisekunden). Ein `git pull` ist sofort sichtbar; ein Cache, der veraltet, entfällt. Keine Handles, keine Sessions.
- **Keine Render-, Lint- oder Set-Logik im Server.** Er ruft `render()`, `render_list`-Bausteine, `build_groups()` und `lint_*` aus personakit auf.

## 3 Schritt 0 – kleine Ergänzung in personakit (eigener PR, vor dem Server)

Zwei Stellen würden den Server sonst zum Duplizieren zwingen oder Daten verschlucken:

1. **Lint-Orchestrierung steckt in `cli.cmd_lint`** (Laden, Schema, `lint_persona`, `load_sets`, `lint_sets`, ~25 Zeilen). Extrahiert als `personakit.api.lint_workspace(paths) -> list[Finding]`; die CLI ruft sie auf, Ausgabe unverändert.
2. **`load_many`/`load_workspace` brechen bei der ersten defekten Datei ab** (`PersonaError`). Für den Server hiesse das: ein halbfertiger Entwurf im Verzeichnis → alle Tools liefern nichts. Neu `personakit.api.load_workspace_tolerant(paths) -> Workspace` mit `personas`, `groups`, `problems` (Datei + Meldung). Die CLI-Befehle bleiben strikt.

Keine Formatänderung, `personakit: "1.0"` bleibt. Version 0.2.0, CHANGELOG, Tests.

## 4 Tools

Alle mit `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, `openWorldHint: false`. Strukturierte Results (Pydantic → `outputSchema` + `structuredContent`), Textteil als Markdown. Tool-Descriptions Englisch (Code-Konvention), Meldungen im Result Deutsch wie die CLI.

| Tool | Parameter | Liefert |
|---|---|---|
| `list_sets` | – | je Set: id, title, solution, scope, status, owner, Anzahl je wirksamer Priorität, `unknown`-Mitglieder; das lose Set «Ohne Set», falls vorhanden; `problems` (defekte `set.yml`) |
| `list_personas` | `set?`, `status?` (draft·active·retired), `priority?` (primary·secondary·supplemental·negative) | je Persona: id, archetype, status, evidence_level, version, review_by, `memberships: [{set, priority}]`; dazu `applied_filters`, `total_in_workspace`, `problems`, bei 0 Treffern `hint` |
| `get_persona` | `id`, `format` (md·card·json·prompt, Default md), `mode?` (simulate·audience, nur bei prompt) | Ausgabe von `personakit.render.render()`, unverändert (Parität mit `personakit render`; Status, Evidenz und Sets liefert `list_personas`) |
| `persona_prompt` | `id`, `mode` (simulate·audience, **Pflicht**) | `render(p, "prompt", mode=…)` |
| `lint_personas` | `id?` | Findings wie `personakit lint --json` (level, code, set, persona, message) + Zählung und geprüfter Umfang |

**Abweichungen vom Auftrag (bestätigt):**
- `lint` → `lint_personas`: «lint» kollidiert in einer Session mit mehreren Servern (journeykit hätte dasselbe Verb). Die übrigen Namen tragen das Nomen bereits.
- `persona_prompt.mode` ohne Default: Die Wahl zwischen Hypothesen-Simulation und Zielpublikum soll bewusst fallen. `get_persona(format=prompt)` behält den CLI-Default `simulate`, damit die Ausgabe der CLI entspricht.
- `mode` bei einem anderen Format als `prompt` → Fehler statt stilles Ignorieren.

### Filtersemantik (mcp-data-fidelity, Regel 1)

- Weglassen = **kein Filter**, auch `retired` ist enthalten. Das steht in der Parameterbeschreibung und im Result (`applied_filters`).
- `priority` ist die **wirksame Priorität pro Set** (`set.yml` vor Persona-Default). Ohne `set` trifft eine Persona, wenn sie in irgendeinem Set (oder im losen Set) diese Priorität hat; `memberships` zeigt, wo.
- Unbekanntes `set` → **Fehler** mit den vorhandenen Set-IDs, keine leere Liste.

### Leermengen und Fehler (Regel 3)

- 0 Treffer → `hint` mit konkretem nächstem Schritt, z. B. «Set ‹x› hat 3 Personas, keine mit wirksamer Priorität primary. Ohne `priority` erneut aufrufen oder `list_sets` für die Verteilung.»
- Unbekannte `id` → Fehler mit den ähnlichsten IDs (difflib) und Verweis auf `list_personas`.
- Doppelte `id` (X001) → Fehler mit beiden Dateien, **nicht** stillschweigend die erste nehmen.
- Persona verletzt das Schema → Fehler mit den Schema-Meldungen, keine Teilausgabe.
- `lint_personas` ohne Befund → «0 Befunde in N Personas und M Sets geprüft», nie eine leere Antwort.
- `PERSONAKIT_DIR` fehlt, ist kein Ordner oder enthält keine `*.persona.md` → jedes Tool liefert diese Meldung samt Abhilfe (statt Startabbruch, den das Modell nicht sieht); zusätzlich eine Zeile auf stderr beim Start.

### Description-Kernsätze (Regel 4: nichts, was eine Leermenge deutet)

- **proto:** «`evidence_level` tells how far a persona is grounded: `proto` = assembled from team assumptions in a workshop, not from research; treat every statement in it as an unvalidated hypothesis and keep its `assumptions` visible wherever you use it. `qualitative` = 5–30 interviews or observations; `statistical` = mixed methods, n > 100.»
- **simulate:** «`mode=simulate` makes you answer as this persona. Whatever you produce in that mode is a hypothesis for a quick counter-check, never user research: do not report it as what users said, think or need, and do not cite it as evidence. `mode=audience` makes you produce content for this persona instead.»
- Beides steht in `get_persona` und `persona_prompt`; die proto-Erklärung zusätzlich in `list_personas`.

## 5 Read-only und Pfadsicherheit

- Kein Schreibaufruf im Code; ein Test hasht das Fixture-Verzeichnis vor und nach allen Tool-Aufrufen.
- `id` wird gegen das Schema-Pattern geprüft und nur über den Index aufgelöst, nie zu einem Pfad zusammengesetzt → kein Path Traversal.
- Dateien ausserhalb von `PERSONAKIT_DIR` (Symlinks) werden ignoriert und als `problems` gemeldet.
- Ein Verzeichnis pro Server-Instanz. Mehrere Verzeichnisse = mehrere Einträge in der Client-Konfiguration.

## 6 «Voreinstellung in jeder Session»

- Claude Code: `claude mcp add personakit --scope user -e PERSONAKIT_DIR=<pfad> -- uvx personakit-mcp` → in jeder Session verfügbar. Claude Desktop analog über die JSON-Konfiguration. README zeigt beides plus Windows-Pfade.
- **Umgesetzt (bestätigt):** zusätzlich zwei MCP-**Prompts** `persona_audience(id)` und `persona_simulate(id)`. Tools muss das Modell selbst aufrufen; Prompts erscheinen im Client als wählbare Vorlage (in Claude Code als `/mcp__personakit__persona_audience`). Das entspricht «Voreinstellung» am direktesten. Sie nutzen denselben Renderer, also keine zusätzliche Logik.

## 7 MCP-Spec `2026-07-28` (mcp-spec.md S1–S5)

| Punkt | Umsetzung |
|---|---|
| Handshake/`_meta`/`server/discover`/`resultType` | vom SDK ≥ 2.0; Nachweis am Draht (S4) als Test und in CI |
| `ttlMs`/`cacheScope` auf `tools/list` (und `prompts/list`) | explizit gesetzt: statische Liste, `cacheScope: public`; `tools/list` deterministisch sortiert |
| Sessions, `ping`, `logging/setLevel` | nicht genutzt; Diagnose nur auf stderr |
| Roots, Sampling, SSE (S2) | nicht gebaut; Verzeichnis kommt aus Server-Konfiguration |
| Fehlercodes | ungültige Argumente `-32602`; keine eigenen Codes im Bereich `-32020…-32099` |
| S5 | `repo-meta.yml: mcp_spec_version: 2026-07-28`, Satz zum Protokollstand im README |

## 8 Datentreue-Nachweise (statt Recall gegen eine Web-UI: Parität mit der CLI)

Die «offizielle Oberfläche» ist hier die personakit-CLI. Tests gegen die Beispiel-Personas aus personakit (als Fixture kopiert, synthetisch):

- `get_persona(format=f)` == `personakit render -f f` für alle vier Formate und beide Modi
- `lint_personas()` == `personakit lint --json` auf demselben Verzeichnis
- `list_personas()` liefert so viele Personas wie `*.persona.md` vorhanden, abzüglich der als `problems` gemeldeten
- Filter-Delta: ohne `status` == alle drei Status explizit
- defekte Datei im Fixture → gemeldet, die übrigen weiterhin gelistet
- Descriptions enthalten «proto» und «hypothesis», keine Formulierung wie «usually means», «likely», «wahrscheinlich»
- `evaluations/personakit-mcp.xml`: 10 Fragen nach mcp-builder Phase 4, gegen die Beispiel-Personas verifiziert

## 9 Repo-Gerüst (github-repo-Skill)

```
personakit-mcp/
├── src/personakit_mcp/{__init__,server,service,models}.py
├── tests/  (Fixtures, Parität, Leermengen, read-only, Spec-Probe)
├── evaluations/personakit-mcp.xml
├── server.json · pyproject.toml · README.md (EN, mcp-name-Marker) · README.de.md
├── CHANGELOG.md · LICENSE (MIT) · SECURITY.md · CONTRIBUTING.md · CLAUDE.md
└── .github/{workflows/ci.yml, repo-meta.yml}
```

`repo-meta.yml` (Entwurf): `repo_name: personakit-mcp` · `description: MCP server that serves personakit personas read-only to LLM sessions` (69 Zeichen) · `topics: [mcp, model-context-protocol, llm, personas, jobs-to-be-done, ux, python]` · `project_type: mcp-server` · `mcp_name: io.github.malkreide/personakit-mcp` · `mcp_spec_version: 2026-07-28` · `version: 0.1.0`.

## 10 Entscheide (am 2026-10-07 bestätigt)

1. **PyPI-Blocker.** personakit ist nicht auf PyPI (`repo-meta.yml → offen`). PyPI lehnt Pakete mit Direkt-URL-Abhängigkeiten ab, also kann personakit-mcp weder auf PyPI noch in die MCP-Registry, solange personakit dort fehlt. Empfehlung: bauen mit Git-Pin auf den personakit-Tag `v0.2.0`, Installation vorerst `uvx --from git+https://github.com/malkreide/personakit-mcp personakit-mcp`; personakit auf PyPI vor dem ersten Server-Release.
2. Schritt 0 in personakit als eigener PR: umgesetzt in malkreide/personakit#7, Release `v0.2.0` (`75f45e2`).
3. `lint` → `lint_personas`: umgesetzt.
4. MCP-Prompts `persona_audience`/`persona_simulate`: umgesetzt.

## 11 Nachträge aus der Umsetzung

- **Rückwärtskompatibilität am Draht:** Das SDK (`mcp` 2.x) beantwortet neben `server/discover` auch den alten `initialize`-Handshake. Clients auf `2025-11-25` verbinden sich deshalb ebenfalls; `tests/test_protocol.py` prüft beide Wege.
- **Fehler in Prompts:** Prompts kennen kein `isError`-Ergebnis. Erwartete Fehler (unbekannte ID, Konfiguration) gehen als JSON-RPC-Fehler `-32602` mit der Meldung hinaus, nicht als generischer `-32603`.
- **Listen-Results:** Die Tools liefern Markdown als Text und das Modell als `structuredContent` (mit `outputSchema`); `ttlMs` und `cacheScope: public` auf `tools/list`, `prompts/list` und `server/discover`. `subscriptions/listen` wird nicht angeboten, weil es nichts zu melden gibt.
- **Fixtures:** Die Tests laufen gegen eine Kopie der synthetischen Beispiel-Personas aus personakit `v0.2.0`, weil das personakit-Paket die Beispiele nicht mitliefert.
