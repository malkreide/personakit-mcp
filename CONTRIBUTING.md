# Contributing

Thanks for considering a contribution. The server is deliberately thin: everything about personas – format, sets, lint rules, rendering – belongs in [personakit](https://github.com/malkreide/personakit). A change that would render, validate or lint personas here belongs there first.

## Setup

```bash
pip install -e ".[dev]"
pip install -r requirements-lint.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python scripts/validate_repo.py .
```

## Ground rules

- Read-only stays read-only. No tool writes, moves or deletes files.
- Every data-returning tool says what it checked, reports what it skipped, and gives a concrete next step on an empty result. No description explains away an empty result.
- Tool output must match the personakit CLI; the parity tests guard that.
- Test fixtures stay synthetic. No real interview data, no personal data, no internal documents.
- Keep `README.md` and `README.de.md` in sync; note changes in `CHANGELOG.md` under `[Unreleased]`.
- Conventional commits: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
