"""Fixtures: writable copies of the synthetic example personas and two probe runs from personakit v0.5.0."""

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "personas"
PROBE_FIXTURES = Path(__file__).parent / "fixtures" / "probe"
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


@pytest.fixture
def probe(root: Path, tmp_path: Path, monkeypatch) -> Path:
    """probe/beispiel (current) and calibration stage 3 (same ids and versions, thinned prompts) as PERSONAKIT_PROBE_DIR."""
    dst = tmp_path / "probe"
    shutil.copytree(PROBE_FIXTURES, dst)
    monkeypatch.setenv("PERSONAKIT_PROBE_DIR", str(dst))
    return dst
