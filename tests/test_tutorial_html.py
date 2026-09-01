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
        "chapter-map",
        "learningModeToggle",
        "output-reader",
    ):
        assert required_id in parser.ids

    assert "第一次来：先走四步学习路线" in text
    assert "沿着完整课程，学会目标基因家族分析" in text
    assert "用一个完整例子，学会目标基因家族分析" not in text
    assert 'href="#newbie-path"' in text
    assert "查阅完整 58 项思维导图" in text
    assert "第一次学习，只走这四步" in text
    assert text.count('class="path-step"') == 4
    assert "练习启动流程" in text
    assert "不会生成 58 项正式分析结果" in text
    assert "教学示意，不是真实分析结果" in text
    assert "第 1 看：对象" in text
    assert "第 2 看：质量" in text
    assert "第 3 看：解释" in text
    assert "泛基因家族分析课程图谱：8 个专业大节、58 项分析" in text
    assert (
        text.index('id="newbie-path"')
        < text.index('id="basic-concepts"')
        < text.index('id="chapter-map"')
    )
    assert "58 / 58 项完整收录" in text
    assert 'class="mindmap-course-start"><a class="button primary" href="#chapter-4"' in text
    assert "看完全图：从第 4 节开始按顺序学习" in text
    assert "58 / 58 项全部可见" not in text
    assert text.count('class="mindmap-stage"') == 4
    assert text.count('class="mindmap-branch"') == 8
    assert text.count('class="mindmap-analysis-list"') == 8
    assert text.count('class="mindmap-analysis-item ') == 58
    assert '<details class="mindmap-branch"' not in text
    assert text.count('class="beginner-chapter-intro"') == 8
    assert text.count('class="chapter-toggle primary"') == 8
    assert "哪些基因真正属于目标家族，它们彼此谁更接近？" in text
    assert "这些基因在什么组织或处理下更活跃，哪些变化有可靠证据？" in text
    for lesson in ("① 基础知识", "② 为什么做", "③ 怎么做", "④ 怎么读结果"):
        assert text.count(lesson) == 8
    assert text.count('class="lesson-diagram course-concept-figure"') == 8
    assert "examples/toy/config.yaml" in text
    assert "panfamflowTutorialMode" in text
    assert "dataset.learningMode='beginner'" in text
    assert "切换到进阶模式" in text
    assert "切换到零基础模式" in text
    assert ".analysis-card.beginner-open:not(.hidden){display:block}" in text
    assert 'html[data-learning-mode="beginner"] .chapter{display:none}' in text
    assert ".chapter.beginner-chapter-open{display:flex;flex-direction:column}" in text
    assert 'html[data-learning-mode="beginner"] .analysis-question{display:none}' in text
    assert 'html[data-learning-mode="beginner"] .chapter-foundation{display:none!important}' in text
    assert (
        'html[data-learning-mode="beginner"] .chapter>.chapter-block{display:none!important}'
        in text
    )
    assert "function setBeginnerChapterOpen(chapter, open)" in text
    assert "document.getElementById(decodeURIComponent(location.hash.slice(1)))" in text
    assert "button.textContent=expanded?'返回分析思维导图':'开始本节'" in text
    assert "const visitedAnalyses = new Set" in text
    assert "const done=visitedAnalyses.size;const total=58" in text
    assert "已打开 ${done} / ${total} 项" in text
    assert "已读 ${done} / ${total} 项" not in text
    assert (
        "beginner:{concept:'先懂它',input:'准备什么',run:'怎么运行',interpret:'怎么看结果'}" in text
    )
    assert (
        "advanced:{concept:'概念与问题',input:'输入与前提',run:'运行与输出',interpret:'解读与边界'}"
        in text
    )
    assert "location.hash='chapter-map'" in text
    assert 'href="#start">课程内容学完：练习启动流程（只做输入检查）' in text
    assert 'href="#output-reader">运行完成：下一步学习怎样读结果' in text
    assert "const readingTarget=getHashTarget()" in text
    assert "scheduleBeginnerKeyboardTarget(readingTarget)" in text
    assert (
        'html[data-learning-mode="beginner"] .beginner-analysis-nav{display:grid;'
        "grid-template-columns:1fr;gap:10px;"
        "padding:0 13px 18px}" in text
    )
    assert ".beginner-analysis-nav{display:none;" in text
    assert 'html[data-learning-mode="beginner"] .beginner-analysis-nav{display:flex}' in text
    assert "}.beginner-analysis-nav{display:flex" not in text
    assert text.index(".beginner-analysis-nav{display:none;") < text.index(
        'html[data-learning-mode="beginner"] .beginner-analysis-nav{display:flex}'
    )
    assert (
        'html[data-learning-mode="beginner"] .beginner-analysis-nav a{display:flex;'
        "align-items:center;width:100%;min-height:44px" in text
    )
    assert "}.beginner-analysis-nav{display:grid" not in text
    assert 'html[data-learning-mode="beginner"] .chapter-quick-nav{display:none!important}' in text


def test_course_map_supports_overview_search_and_truthful_state_filters() -> None:
    text = Path("docs/index.html").read_text(encoding="utf-8")
    parser = TutorialParser()
    parser.feed(text)

    for control_id in (
        "mindmap-finder-title",
        "mapOverviewButton",
        "mapCompleteButton",
        "mapSearch",
        "mapStateFilter",
        "mapClearFilters",
        "mapFilterSummary",
        "mapNoResults",
    ):
        assert control_id in parser.ids

    assert "只看 8 个大节" in text
    assert "显示全部 58 项分析" in text
    assert '<button id="mapOverviewButton" type="button" aria-pressed="false">' in text
    assert (
        '<button id="mapCompleteButton" class="primary" type="button" aria-pressed="true">' in text
    )
    assert "按编号或名称查找" in text
    assert "按结果条件查看" in text
    assert text.count('data-map-search="') == 58
    assert text.count('data-map-state="direct"') == 50
    assert text.count('data-map-state="postprocess"') == 3
    assert text.count('data-map-state="conditional"') == 5
    assert 'option value="direct">已有直接结果' in text
    assert 'option value="postprocess">需要后处理' in text
    assert 'option value="conditional">满足条件后运行' in text
    assert "function setMapView(view)" in text
    assert "当前显示 58 / 58 项分析" in text
    assert "let mapView='complete', mapVisible=58" in text
    assert "setMapView('complete');filterMap()" in text
    assert "function filterMap()" in text
    assert "item.dataset.mapState===state" in text
    assert "branch.classList.toggle('map-filtered'" in text
    assert "stage.classList.toggle('map-filtered'" in text
    assert "mapNoResults.hidden=mapVisible!==0" in text
    assert ".chapter-map.map-overview .mindmap-analysis-list{display:none}" in text
    assert 'aria-live="polite"' in text


def test_course_map_exact_search_and_visits_have_explicit_meaning() -> None:
    text = Path("docs/index.html").read_text(encoding="utf-8")
    assert text.count('data-map-id="') == 58
    assert 'aria-describedby="mapSearchHelp"' in text
    assert "输入完整编号（如 10.1）只找这一项" in text
    assert "不表示已经学会或分析已经完成" in text
    assert 'content:" · 已打开"' in text
    assert 'content:" ✓"' not in text
    assert "function matchesMapQuery(sourceId, searchText, rawQuery)" in text
    assert "rawQuery.normalize('NFKC')" in text
    assert "return sourceId===query" in text
    assert "sourceId.split('.')[0]" in text
    assert "matchesMapQuery(item.dataset.mapId" in text


def test_beginner_semantic_closure_keeps_internal_drawing_contracts_advanced_only() -> None:
    text = Path("docs/index.html").read_text(encoding="utf-8")
    assert 'class="advanced-plot-contract technical-mode-only"' in text
    assert 'class="micro-column-label advanced-plot-contract"' in text
    assert 'class="micro-plot-contract advanced-plot-contract"' in text
    assert (
        'html[data-learning-mode="beginner"] .advanced-plot-contract{display:none!important}'
        in text
    )
    assert "缺失值不会转换为零，也不会进入连续颜色范围" in text
    assert "正式分析前的三道输入门" in text
    assert "第 0 门：样本说明可比较" in text
    assert "第 1 门：基因组与注释配套" in text
    assert "第 2 门：每个基因只选一条代表记录" in text
