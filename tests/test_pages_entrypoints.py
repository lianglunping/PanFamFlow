"""Regression tests for README and GitHub Pages entry points."""

from html.parser import HTMLParser
from pathlib import Path

PROJECT_SITE_URL = (
    "https://lianglunping.github.io/PanFamFlow/index.html?rev=pages-entry-fix-20260819"
)
TUTORIAL_URL = "https://lianglunping.github.io/PanFamFlow/tutorial/"


class EntryPointParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta_refreshes: list[str] = []
        self.stylesheets: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "meta" and str(values.get("http-equiv", "")).lower() == "refresh":
            self.meta_refreshes.append(str(values.get("content", "")))
        if tag == "link" and str(values.get("rel", "")).lower() == "stylesheet":
            self.stylesheets.append(str(values.get("href", "")))
        if tag == "a" and values.get("href"):
            self.links.append(str(values["href"]))


def parse_html(path: Path) -> EntryPointParser:
    parser = EntryPointParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def test_readmes_use_explicit_cache_busted_project_site_entry() -> None:
    for readme in (Path("README.md"), Path("README.zh-CN.md")):
        text = readme.read_text(encoding="utf-8")
        assert PROJECT_SITE_URL in text
        assert TUTORIAL_URL in text


def test_repository_root_entry_never_redirects_to_itself() -> None:
    parser = parse_html(Path("index.html"))
    assert parser.meta_refreshes == []
    assert PROJECT_SITE_URL in parser.links
    assert TUTORIAL_URL in parser.links


def test_published_home_is_self_contained_and_links_to_tutorial() -> None:
    homepage = Path("site/index.html")
    parser = parse_html(homepage)
    text = homepage.read_text(encoding="utf-8")
    assert parser.meta_refreshes == []
    assert parser.stylesheets == []
    assert "<style>" in text
    assert "/PanFamFlow/tutorial/" in parser.links
