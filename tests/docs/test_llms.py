from dataclasses import dataclass
from pathlib import Path

import pytest

from docs.hooks.llms import on_post_build


@dataclass(frozen=True)
class _Config:
    site_name: str
    site_description: str | None
    site_url: str | None
    docs_dir: str
    site_dir: str


def _config(docs_dir: Path, *, site_dir: Path) -> _Config:
    return _Config(
        site_name="atpx",
        site_description="Agentic mathematics workbench",
        site_url="https://phvv.me/atpx/",
        docs_dir=str(docs_dir),
        site_dir=str(site_dir),
    )


@pytest.fixture
def site_after_build(tmp_path: Path) -> Path:
    """`site_dir` after `on_post_build` ran over one populated docs tree."""
    docs_dir, site_dir = tmp_path / "docs", tmp_path / "site"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Home\n\nWelcome.\n", encoding="utf-8")
    (docs_dir / "api.md").write_text(
        "---\ntitle: ignored\n---\nNo heading here.\n", encoding="utf-8"
    )
    (docs_dir / "config.md").write_text(
        "# Configuration reference\n\nFour tables.\n", encoding="utf-8"
    )
    (docs_dir / "release.md").write_text("# Release notes\n\nv0.0.3.\n", encoding="utf-8")
    site_dir.mkdir()
    on_post_build(_config(docs_dir, site_dir=site_dir))
    return site_dir


def test_on_post_build_indexes_every_page_by_its_heading(site_after_build: Path) -> None:
    index = (site_after_build / "llms.txt").read_text(encoding="utf-8")
    assert index.startswith("# atpx\n\n> Agentic mathematics workbench\n")
    assert "- [Home](https://phvv.me/atpx/index.md)" in index
    assert "- [api](https://phvv.me/atpx/api/index.md)" in index
    assert "- [Configuration reference](https://phvv.me/atpx/config/index.md)" in index
    assert "- [Release notes](https://phvv.me/atpx/release/index.md)" in index


def test_on_post_build_strips_front_matter_from_the_full_text(site_after_build: Path) -> None:
    full = (site_after_build / "llms-full.txt").read_text(encoding="utf-8")
    assert "# Home\n\nWelcome." in full
    assert "No heading here." in full
    assert "title: ignored" not in full
