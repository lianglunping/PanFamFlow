"""Regression checks for the self-contained Chinese beginner tutorial."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


class TutorialParser(HTMLParser):
    """Collect structural properties without external parser dependencies."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.external_scripts: list[str] = []
        self.external_stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "script" and values.get("src"):
            self.external_scripts.append(values["src"] or "")
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.external_stylesheets.append(values["href"] or "")


def test_chinese_beginner_tutorial_is_self_contained() -> None:
    tutorial = Path("docs/index.html")
    assert tutorial.is_file()
    text = tutorial.read_text(encoding="utf-8")
    assert "PanFamFlow 中文入门教程" in text
    assert "目标家族" in text
    assert "不做泛基因组组装" in text
    assert "交互式 config.yaml 片段生成器" in text
    assert "uv run panfamflow resume -c config.yaml" in text
    assert "树上 clade ≠ 自动成为 HOG" in text

    parser = TutorialParser()
    parser.feed(text)
    assert len(parser.ids) == len(set(parser.ids))
    assert parser.external_scripts == []
    assert parser.external_stylesheets == []
    for required_id in (
        "overview",
        "step-0",
        "step-11",
        "generator",
        "troubleshooting",
        "quiz",
    ):
        assert required_id in parser.ids
