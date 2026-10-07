# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |

## Reporting a vulnerability

personakit-mcp is a local stdio server without network access of its own. It reads one folder (`PERSONAKIT_DIR`) and never writes. Relevant findings are therefore mostly about reading outside that folder, about parsing untrusted persona files, and about content from persona files reaching a model as instructions.

Please report vulnerabilities privately via [GitHub Security Advisories](https://github.com/malkreide/personakit-mcp/security/advisories/new) rather than as public issues. Include the affected version, steps to reproduce and, if possible, a minimal persona folder. You will receive an acknowledgement within 7 days.

## Scope notes

- Persona ids are checked against the personakit schema and resolved through an index, never joined into a path. Files that resolve outside `PERSONAKIT_DIR` (symlinks) are skipped and reported. A way around either is in scope.
- Persona files are user-authored text that is handed to a model. Treat a persona folder from an unknown source like any other prompt input.
- Test fixtures are synthetic and contain no personal data. Please keep it that way in contributions.
