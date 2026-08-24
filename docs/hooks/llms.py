"""MkDocs post-build hook that writes `llms.txt` and `llms-full.txt`.

This replaces `mkdocs-llmstxt`, which needs a plugin release per mkdocs
minor version and lags behind. The hook runs once after the whole build
and reads the source markdown straight from the `docs/` tree.

`_SECTIONS` mirrors the section layout this package wants in its index.
Each entry maps a section name to the doc paths under `docs/`, in order.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

_SECTIONS: dict[str, list[str]] = {
    "Usage": ["index.md"],
    "Reference": ["api.md", "release.md"],
}

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_FENCED_CODE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class LlmsTxtBuild:
    """Write `llms.txt` and `llms-full.txt` from one finished mkdocs build.

    Storing the whole `config` (rather than the handful of values `write` reads
    from it) keeps this the one seam mkdocs's `on_post_build(config)` hook
    contract has to satisfy; `write` reads it exactly the way any other method
    reads its own instance state.
    """

    def __init__(self, config: MkDocsConfig) -> None:
        self.config = config

    def write(self) -> None:
        """Render both files and write them into the built `site/`."""
        header = f"# {self.config.site_name}\n\n> {self.config.site_description or ''}\n"
        index_lines, full_lines = [header], [header]
        for section, doc_paths in _SECTIONS.items():
            index_lines.append(f"\n## {section}\n")
            for doc_path in doc_paths:
                markdown = self._read_page(doc_path)
                title = self._title_for(markdown, doc_path=doc_path)
                url = self._page_url(doc_path=doc_path)
                index_lines.append(f"- [{title}]({url})")
                full_lines.append(f"\n# {title}\n\n{markdown}\n")
        site_dir = Path(self.config.site_dir)
        (site_dir / "llms.txt").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
        (site_dir / "llms-full.txt").write_text("\n".join(full_lines) + "\n", encoding="utf-8")

    def _page_url(self, *, doc_path: str) -> str:
        """Build the page URL the way `mkdocs-llmstxt` does.

        With directory URLs, `foo/bar.md` is served at `foo/bar/` and the
        markdown twin lives at `foo/bar/index.md`. `index.md` maps to the
        section root, so its twin is `index.md` at the site root.

        doc_path: path of the page relative to `docs/`.
        """
        site_url = self.config.site_url or ""
        base = site_url if site_url.endswith("/") else f"{site_url}/"
        stem = doc_path[: -len(".md")]
        twin = "index.md" if stem == "index" else f"{stem}/index.md"
        return f"{base}{twin}"

    def _read_page(self, doc_path: str) -> str:
        """Read one source page and strip any YAML front-matter."""
        text = (Path(self.config.docs_dir) / doc_path).read_text(encoding="utf-8")
        return _FRONT_MATTER.sub("", text).strip()

    def _title_for(self, markdown: str, *, doc_path: str) -> str:
        """Pick a link title: the page's first `# ` heading, else the file stem.

        Headings inside fenced code blocks (like `# paste ...` comments) do not
        count, so a hero-only page with no real heading falls back to the stem.

        markdown: full source text of the page.
        doc_path: path of the page relative to `docs/`, used for the fallback.
        """
        match = _H1.search(_FENCED_CODE.sub("", markdown))
        if match:
            return match.group(1)
        stem = Path(doc_path).stem
        return "Home" if stem == "index" else stem


def on_post_build(config: MkDocsConfig) -> None:
    """Write `llms.txt` and `llms-full.txt` into the built `site/`."""
    LlmsTxtBuild(config).write()
