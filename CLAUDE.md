# personakit-mcp – Hinweise für Claude Code

## Was das ist

Lesender MCP-Server (stdio, Protokollstand `2026-07-28`) für einen Ordner mit personakit-Personas (`PERSONAKIT_DIR`). Design und Entscheide: `docs/DESIGN.md`. Die ganze Persona-Logik kommt aus personakit (`personakit.api`, `render`, `lint`); hier wird nichts gerendert oder validiert.

Module: `service.py` (Ordner auflösen, Filter, Suche, Meldungen – ohne MCP) → `models.py` (strukturierte Ergebnisse) → `server.py` (`MCPServer`, Tools, Prompts, Beschreibungen, `main`).

## Gates – vor jedem Commit alle grün

```bash
pip install -e ".[dev]"
pip install -r requirements-lint.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python scripts/validate_repo.py .
```

## Regeln

- Der Server schreibt nie (`test_server_never_writes`).
- Ausgaben entsprechen der personakit-CLI (Paritätstests). Fehlt etwas in personakit, dort ergänzen, nicht hier nachbauen.
- mcp-data-fidelity: Weggelassene Filter gelten nicht; Leermengen tragen einen konkreten `hint`; übersprungene Dateien stehen unter `problems`; keine Beschreibung erklärt eine Leermenge.
- Tool-Beschreibungen Englisch; Meldungen im Ergebnis Deutsch in Schweizer Rechtschreibung (kein ß).
- Tool-Namen im README = registrierte Namen.
- Fixtures unter `tests/fixtures/personas` sind die synthetischen Beispiele aus personakit `v0.2.0`; bei einem neuen personakit-Tag gemeinsam nachziehen.
- Die SDK-Untergrenze bleibt auf einer Version, die `2026-07-28` spricht; `tests/test_protocol.py` prüft das am Draht.
- `README.md` (EN) und `README.de.md` (DE) synchron halten; `mcp-name`-Marker nur in `README.md`, Anzahl vor und nach README-Änderungen vergleichen.
- Conventional Commits. Unter Windows/PowerShell keine `&&`-Ketten.

## Offen

Siehe `.github/repo-meta.yml` → `offen` (PyPI erst nach personakit auf PyPI).
