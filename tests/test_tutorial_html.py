"""Regression checks for the self-contained Chinese beginner tutorial."""

# Chinese prose assertions intentionally contain fullwidth Chinese punctuation.
# ruff: noqa: RUF001

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
    assert "58 项不是同一种“可用”" in text
    assert "ANALYSIS_COVERAGE.tsv" in text
    assert "TUTORIAL_CONTENT_MATRIX.tsv" in text

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
        "filters",
        "chapter-4",
        "chapter-11",
    ):
        assert required_id in parser.ids
    assert sum(item.startswith("analysis-") for item in parser.ids) == 58


def test_scientific_coverage_explorer_and_mobile_navigation_controls_exist() -> None:
    text = Path("docs/index.html").read_text(encoding="utf-8")
    parser = TutorialParser()
    parser.feed(text)

    for control_id in (
        "tutorialSearch",
        "chapterFilter",
        "stateFilter",
        "filterSummary",
        "noResults",
        "clearFilters",
        "menuToggle",
        "themeToggle",
    ):
        assert control_id in parser.ids

    for state in (
        "ALL",
        "IMPLEMENTED",
        "CONDITIONALLY_AVAILABLE",
        "EXTERNAL_IMPORT",
        "NOT_SUPPORTED",
    ):
        if state != "ALL":
            assert f'<option value="{state}">' in text

    assert 'aria-controls="sidebar"' in text
    assert 'aria-expanded="false"' in text
    assert "function filter()" in text
    assert "card.dataset.state===st" in text
    assert "section.classList.toggle('chapter-filtered',!has)" in text
    assert "MISSING_IN_INPUT" in text


def test_beginner_mode_has_one_clear_path_and_keeps_advanced_content_available() -> None:
    text = Path("docs/index.html").read_text(encoding="utf-8")
    parser = TutorialParser()
    parser.feed(text)

    for required_id in (
        "newbie-path",
        "learningModeToggle",
        "output-reader",
    ):
        assert required_id in parser.ids

    assert "零基础开始学习" in text
    assert "第一次学习，只走这四步" in text
    assert text.count('class="path-step"') == 4
    assert "教学示意，不是真实分析结果" in text
    assert "第 1 看：对象" in text
    assert "第 2 看：质量" in text
    assert "第 3 看：解释" in text
    assert "panfamflowTutorialMode" in text
    assert "dataset.learningMode='beginner'" in text
    assert "切换到进阶模式" in text
    assert "切换到零基础模式" in text
    assert ".analysis-card.beginner-open:not(.hidden){display:block}" in text
