"""Fixtures: a writable copy of the synthetic example personas from personakit v0.2.0."""

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "personas"
ELTERN = "elternkommunikation-schuleintritt"
KI = "ki-leitplanken-lehrpersonen"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    """Example personas in two sets, configured as PERSONAKIT_DIR."""
    dst = tmp_path / "personas"
    shutil.copytree(FIXTURES, dst)
    monkeypatch.setenv("PERSONAKIT_DIR", str(dst))
    return dst


@pytest.fixture
def broken(root: Path) -> Path:
    """The examples plus an unreadable file, a schema violation and a broken set.yml."""
    (root / ELTERN / "kaputt.persona.md").write_text("kein frontmatter\n", encoding="utf-8")
    (root / ELTERN / "ohne-ziele.persona.md").write_text(
        '---\npersonakit: "1.0"\nid: ohne-ziele\n---\n\n## Szenario\n', encoding="utf-8"
    )
    (root / "defektes-set").mkdir()
    (root / "defektes-set" / "set.yml").write_text("- keine\n- mapping\n", encoding="utf-8")
    return root
