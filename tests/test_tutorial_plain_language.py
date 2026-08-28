"""Plain-language and terminology regression checks for the PanFamFlow tutorial."""

# Chinese prose assertions intentionally contain fullwidth Chinese punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import re
import subprocess
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "index.html"
TERMINOLOGY_PATH = ROOT / "docs" / "TUTORIAL_TERMINOLOGY.tsv"
BEGINNER_LANGUAGE_PATH = ROOT / "docs" / "TUTORIAL_BEGINNER_LANGUAGE.tsv"
BEGINNER_SYNC_PATH = ROOT / "scripts" / "sync_tutorial_beginner_language.py"
LESSON_PATH = ROOT / "docs" / "TUTORIAL_CHAPTER_LESSONS.tsv"
LESSON_SYNC_PATH = ROOT / "scripts" / "sync_tutorial_learning_structure.py"

EXPECTED_IDS = (
    [f"4.{index}" for index in range(1, 5)]
    + [f"5.{index}" for index in range(1, 7)]
    + [f"6.{index}" for index in range(1, 9)]
    + [f"7.{index}" for index in range(1, 4)]
    + [f"8.{index}" for index in range(1, 7)]
    + [f"9.{index}" for index in range(1, 10)]
    + [f"10.{index}" for index in range(1, 16)]
    + [f"11.{index}" for index in range(1, 8)]
)

STATE_LABELS = {
    "IMPLEMENTED": "已实现",
    "CONDITIONALLY_AVAILABLE": "有条件可用",
    "EXTERNAL_IMPORT": "需外部分析结果",
    "NOT_SUPPORTED": "当前未支持",
}

EXPECTED_STATE_COUNTS = Counter(
    {
        "IMPLEMENTED": 53,
        "CONDITIONALLY_AVAILABLE": 5,
    }
)

TERMINOLOGY_FIELDS = [
    "term_id",
    "chinese_primary",
    "technical_form",
    "category",
    "plain_definition_zh",
    "panfamflow_usage_zh",
    "is_internal",
    "first_use_anchor",
]

BEGINNER_LANGUAGE_FIELDS = [
    "source_id",
    "beginner_title_zh",
    "beginner_question_zh",
    "beginner_input_zh",
    "beginner_output_zh",
    "beginner_read_zh",
    "beginner_warning_zh",
]

LESSON_FIELDS = [
    "chapter",
    "stage_id",
    "chapter_title_zh",
    "analysis_count",
    "question_zh",
    "foundation_zh",
    "why_zh",
    "input_zh",
    "method_zh",
    "output_zh",
    "read_zh",
    "boundary_zh",
    "diagram_type",
    "output_label_zh",
    "dependency_zh",
]

BEGINNER_FORBIDDEN_JARGON = (
    "系统发育",
    "正交组",
    "泛基因组",
    "亚家族",
    "共线性",
    "选择压力",
    "启动子",
    "顺式作用元件",
    "转录组",
    "差异表达",
    "热图",
    "分母",
    "命中",
    "富集",
    "校正",
    "拟合",
    "表达矩阵",
    "正向选择",
    "同义变化",
    "外群",
    "独立基因簇",
    "单位长度",
    "随机重复",
    "抽样",
    "原始整数计数",
    "上游信号",
    "按各组自身范围",
)

ALLOWED_TERM_CATEGORIES = {
    "STANDARD_TERM",
    "SOFTWARE_OR_FORMAT",
    "PANFAMFLOW_FIELD",
    "PANFAMFLOW_STATUS",
}

REQUIRED_INTERNAL_TERMS = {
    "stable_id": "PANFAMFLOW_FIELD",
    "analysis_scope": "PANFAMFLOW_FIELD",
    "orthology_group_type": "PANFAMFLOW_FIELD",
    "hog_node_status": "PANFAMFLOW_FIELD",
    "AUTO_ORTHOGROUP_FALLBACK": "PANFAMFLOW_STATUS",
    "MISSING_IN_INPUT": "PANFAMFLOW_STATUS",
    "NOT_APPLICABLE": "PANFAMFLOW_STATUS",
    "TARGET_GENE_FAMILY_ONLY": "PANFAMFLOW_STATUS",
}


class Node:
    """Small dependency-free DOM node used by the regression tests."""

    def __init__(self, tag: str, attrs: dict[str, str], parent: Node | None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[Node] = []
        self.text_parts: list[str] = []

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def all_text(self) -> str:
        return " ".join(self.text_parts + [child.all_text() for child in self.children]).strip()

    def descendants(self):
        for child in self.children:
            yield child
            yield from child.descendants()


class TutorialParser(HTMLParser):
    VOID: ClassVar[set[str]] = {
        "meta",
        "link",
        "input",
        "br",
        "hr",
        "img",
        "source",
        "area",
        "base",
        "embed",
        "param",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {}, None)
        self.stack = [self.root]
        self.all_nodes = [self.root]
        self.external_scripts: list[str] = []
        self.external_stylesheets: list[str] = []
        self.remote_media: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        values = {key: (value or "") for key, value in attrs}
        node = Node(tag, values, self.stack[-1])
        self.stack[-1].children.append(node)
        self.all_nodes.append(node)
        if tag == "script" and values.get("src"):
            self.external_scripts.append(values["src"])
        if tag == "link" and values.get("href"):
            self.external_stylesheets.append(values["href"])
        for attribute in ("src", "href"):
            value = values.get(attribute, "")
            if tag in {"script", "link", "img", "source", "iframe"} and re.match(
                r"^(?:https?:)?//", value, re.I
            ):
                self.remote_media.append((tag, value))
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].text_parts.append(data)


def parse_html() -> TutorialParser:
    parser = TutorialParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    return parser


def nodes_with_class(parser: TutorialParser, class_name: str) -> list[Node]:
    return [node for node in parser.all_nodes if class_name in node.classes]


def find_by_id(parser: TutorialParser, node_id: str) -> Node:
    matches = [node for node in parser.all_nodes if node.attrs.get("id") == node_id]
    assert len(matches) == 1, (node_id, len(matches))
    return matches[0]


def read_terms() -> list[dict[str, str]]:
    with TERMINOLOGY_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert reader.fieldnames == TERMINOLOGY_FIELDS
        return list(reader)


def read_beginner_language() -> list[dict[str, str]]:
    with BEGINNER_LANGUAGE_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert reader.fieldnames == BEGINNER_LANGUAGE_FIELDS
        return list(reader)


def test_beginner_language_contract_has_58_plain_chinese_rows() -> None:
    rows = read_beginner_language()
    assert [row["source_id"] for row in rows] == EXPECTED_IDS
    assert len({row["source_id"] for row in rows}) == 58

    for row in rows:
        for field in BEGINNER_LANGUAGE_FIELDS[1:]:
            value = row[field].strip()
            assert value, (row["source_id"], field)
            assert re.search(r"[A-Za-z]", value) is None, (row["source_id"], field, value)
            assert all(term not in value for term in BEGINNER_FORBIDDEN_JARGON), (
                row["source_id"],
                field,
                value,
            )
        assert 6 <= len(row["beginner_title_zh"]) <= 28
        assert row["beginner_question_zh"].endswith("？")
        assert row["beginner_warning_zh"].endswith("。")


def test_beginner_cards_show_only_the_plain_language_contract() -> None:
    parser = parse_html()
    rows = {row["source_id"]: row for row in read_beginner_language()}
    cards = nodes_with_class(parser, "analysis-card")
    assert len(cards) == 58

    for card in cards:
        source_id = card.attrs["data-source-id"]
        beginner_titles = [node for node in card.descendants() if "beginner-title" in node.classes]
        advanced_titles = [node for node in card.descendants() if "advanced-title" in node.classes]
        guides = [node for node in card.descendants() if "beginner-guide" in node.classes]
        conditions = [node for node in card.descendants() if "beginner-condition" in node.classes]
        assert len(beginner_titles) == 1
        assert len(advanced_titles) == 1
        assert len(guides) == 1
        assert len(conditions) == 1
        assert beginner_titles[0].all_text().strip() == rows[source_id]["beginner_title_zh"]
        guide_text = re.sub(r"\s+", " ", guides[0].all_text())
        for field in BEGINNER_LANGUAGE_FIELDS[2:]:
            assert rows[source_id][field] in guide_text
        assert re.search(r"[A-Za-z]", guide_text) is None, (source_id, guide_text)
        assert all(term not in guide_text for term in BEGINNER_FORBIDDEN_JARGON)

        condition_text = conditions[0].all_text()
        assert "继续前先确认" in condition_text
        assert re.search(r"[A-Za-z]", condition_text) is None, (source_id, condition_text)
        assert all(term not in condition_text for term in BEGINNER_FORBIDDEN_JARGON)

    css = HTML_PATH.read_text(encoding="utf-8")
    for hidden_selector in (
        'html[data-learning-mode="beginner"] .analysis-takeaway',
        'html[data-learning-mode="beginner"] .analysis-tabs',
        'html[data-learning-mode="beginner"] .analysis-panels',
        'html[data-learning-mode="beginner"] .analysis-head .source-id',
        'html[data-learning-mode="beginner"] .analysis-head .state-badge',
        'html[data-learning-mode="beginner"] .technical-note',
    ):
        assert hidden_selector in css


def test_beginner_navigation_and_chapter_intros_avoid_unexplained_jargon() -> None:
    parser = parse_html()

    def is_inside_sidebar(node: Node) -> bool:
        parent = node.parent
        while parent is not None:
            if parent.attrs.get("id") == "sidebar":
                return True
            parent = parent.parent
        return False

    plain_regions = (
        nodes_with_class(parser, "mindmap-stage")
        + nodes_with_class(parser, "beginner-chapter-intro")
        + [node for node in parser.all_nodes if node.tag == "small" and is_inside_sidebar(node)]
    )
    assert len(nodes_with_class(parser, "mindmap-stage")) == 4
    assert len(nodes_with_class(parser, "mindmap-branch")) == 8
    assert len(nodes_with_class(parser, "beginner-chapter-intro")) == 8

    for node in plain_regions:
        text = re.sub(r"\s+", " ", node.all_text()).strip()
        assert text
        assert re.search(r"[A-Za-z]", text) is None, text
        assert all(term not in text for term in BEGINNER_FORBIDDEN_JARGON), text

    html = HTML_PATH.read_text(encoding="utf-8")
    for hidden_selector in (
        'html[data-learning-mode="beginner"] #scientific-redlines',
        'html[data-learning-mode="beginner"] .sidebar a[href="#scientific-redlines"]',
        'html[data-learning-mode="beginner"] .top-actions .desktop-only',
        'html[data-learning-mode="beginner"] #printPage',
    ):
        assert hidden_selector in html

    beginner_footer = [
        child
        for node in parser.all_nodes
        if node.tag == "footer"
        for child in node.descendants()
        if "beginner-title" in child.classes
    ]
    assert len(beginner_footer) == 1
    footer_text = beginner_footer[0].all_text()
    assert re.search(r"[A-Za-z]", footer_text) is None
    assert all(term not in footer_text for term in BEGINNER_FORBIDDEN_JARGON)


def test_beginner_global_guidance_avoids_unexplained_statistics_and_domain_terms() -> None:
    parser = parse_html()
    newbie_path = find_by_id(parser, "newbie-path")
    example_readers = nodes_with_class(parser, "example-reader")

    assert newbie_path is not None
    assert len(example_readers) == 1
    assert "P 值" not in newbie_path.all_text()
    assert "结构域" not in example_readers[0].all_text()
    assert "某一个数值" in newbie_path.all_text()
    assert "关键片段完整" in example_readers[0].all_text()
    assert "示例基因 A" not in example_readers[0].all_text()
    assert "示例基因 B" not in example_readers[0].all_text()

    start = find_by_id(parser, "start")
    assert start is not None
    beginner_notes = [node for node in start.descendants() if "beginner-note" in node.classes]
    assert len(beginner_notes) == 1
    assert "results/" not in beginner_notes[0].all_text()
    assert "结果目录" in beginner_notes[0].all_text()


def test_beginner_mode_defines_its_five_required_basic_concepts() -> None:
    parser = parse_html()
    concepts = find_by_id(parser, "basic-concepts")
    chapter_map = find_by_id(parser, "chapter-map")

    assert "beginner-only" in concepts.classes
    concept_cards = [node for node in concepts.descendants() if "basic-concept" in node.classes]
    assert len(concept_cards) == 5

    text = re.sub(r"\s+", " ", concepts.all_text()).strip()
    for required in (
        "基因与蛋白",
        "基因家族",
        "材料、样本与重复",
        "家族分组",
        "染色体位置与复制",
    ):
        assert required in text
    assert "同一条件下分别取得的多个样本才是重复" in text
    assert "分组名称只是分类，不等于功能已经相同" in text
    assert "可能产生位置不同的相似基因" in text
    assert re.search(r"[A-Za-z]", text) is None

    map_text = re.sub(r"\s+", " ", chapter_map.all_text()).strip()
    assert "58 项分析怎样连成一个故事" in map_text
    assert "可靠成员 → 结构与位置 → 来源与变化 → 实际活跃条件" in map_text
    assert "第 4 章是共同起点" in map_text


def test_mindmap_and_chapter_lessons_form_a_complete_learning_route() -> None:
    parser = parse_html()
    stages = nodes_with_class(parser, "mindmap-stage")
    branches = nodes_with_class(parser, "mindmap-branch")
    analysis_lists = nodes_with_class(parser, "mindmap-analysis-list")
    intros = nodes_with_class(parser, "beginner-chapter-intro")

    assert [node.attrs["data-stage"] for node in stages] == ["1", "2", "3", "4"]
    assert [node.attrs["data-chapter"] for node in branches] == [str(i) for i in range(4, 12)]
    assert len(analysis_lists) == 8
    assert (
        sum(
            len([child for child in item.descendants() if child.tag == "a"])
            for item in analysis_lists
        )
        == 58
    )
    assert len(intros) == 8
    start_links = nodes_with_class(parser, "mindmap-start")
    assert len(start_links) == 8
    assert all(link.parent is not None and link.parent.tag == "article" for link in start_links)
    assert [link.attrs["href"] for link in start_links] == [f"#chapter-{i}" for i in range(4, 12)]

    expected_diagrams = {
        "member_funnel",
        "gene_structure",
        "presence_matrix",
        "chromosome_map",
        "duplication_paths",
        "coding_change",
        "promoter_signals",
        "expression_heatmap",
    }
    diagrams = nodes_with_class(parser, "lesson-diagram")
    assert {node.attrs["data-diagram"] for node in diagrams} == expected_diagrams
    for intro in intros:
        lesson_parts = [
            node.attrs.get("data-lesson")
            for node in intro.descendants()
            if node.attrs.get("data-lesson")
        ]
        assert lesson_parts == ["foundation", "why", "how", "read"]
        text = re.sub(r"\s+", " ", intro.all_text()).strip()
        for heading in ("基础知识", "为什么做", "怎么做", "怎么读结果", "不要误读"):
            assert heading in text

    chapter_ten = find_by_id(parser, "chapter-10")
    subgroup_grids = [
        node for node in chapter_ten.descendants() if "lesson-subgroup-grid" in node.classes
    ]
    assert len(subgroup_grids) == 1
    assert len([node for node in subgroup_grids[0].children if node.tag == "div"]) == 4
    assert len([node for node in subgroup_grids[0].descendants() if node.tag == "a"]) == 15


def test_chapter_ten_items_keep_group_context_and_explain_color_ranges() -> None:
    parser = parse_html()
    chapter_ten = find_by_id(parser, "chapter-10")
    locations = [
        node for node in chapter_ten.descendants() if "beginner-item-location" in node.classes
    ]
    assert len(locations) == 15
    location_text = [re.sub(r"\s+", " ", node.all_text()).strip() for node in locations]
    assert sum("第 1 组 / 4：先认清有哪些线索" in text for text in location_text) == 3
    assert sum("第 2 组 / 4：按家族分组比较" in text for text in location_text) == 4
    assert sum("第 3 组 / 4：按材料或群体比较" in text for text in location_text) == 4
    assert sum("第 4 组 / 4：看重点线索和组合分组" in text for text in location_text) == 4
    assert location_text[0].endswith("第 1 / 15 项")
    assert location_text[-1].endswith("第 15 / 15 项")

    promoter_diagrams = [
        node
        for node in chapter_ten.descendants()
        if node.attrs.get("data-diagram") == "promoter_signals"
    ]
    assert len(promoter_diagrams) == 1
    diagram_text = re.sub(r"\s+", " ", promoter_diagrams[0].all_text()).strip()
    for teaching_point in (
        "同一张线索表",
        "按四类汇总",
        "按家族分组",
        "按材料或群体",
        "按成员有无",
        "统一颜色范围",
        "每种线索分别调色",
        "颜色深浅不能跨线索直接比较",
    ):
        assert teaching_point in diagram_text


def test_all_58_items_have_linear_navigation_and_learning_progress() -> None:
    parser = parse_html()
    cards = nodes_with_class(parser, "analysis-card")
    navigations = nodes_with_class(parser, "beginner-analysis-nav")
    assert len(cards) == len(navigations) == 58
    html = HTML_PATH.read_text(encoding="utf-8")
    assert html.count('rel="prev"') == 50
    assert html.count('rel="next"') == 50
    assert html.count("本章完成：返回分析思维导图") == 8
    assert "panfamflowTutorialVisitedAnalyses" in html
    assert "const done=visitedAnalyses.size;const total=58" in html
    assert "已读 ${done} / ${total} 项" in html


def test_chapter_lesson_contract_and_html_are_synchronized() -> None:
    with LESSON_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert reader.fieldnames == LESSON_FIELDS
        rows = list(reader)
    assert [row["chapter"] for row in rows] == [str(i) for i in range(4, 12)]
    assert sum(int(row["analysis_count"]) for row in rows) == 58
    assert len({row["diagram_type"] for row in rows}) == 8
    for row in rows:
        for field in set(LESSON_FIELDS) - {"chapter", "stage_id", "analysis_count", "diagram_type"}:
            value = row[field].strip()
            assert value
            assert re.search(r"[A-Za-z]", value) is None, (row["chapter"], field, value)

    subprocess.run(
        [sys.executable, str(LESSON_SYNC_PATH), "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_five_conditional_analyses_explain_their_extra_input_in_plain_chinese() -> None:
    parser = parse_html()
    cards = {
        card.attrs["data-source-id"]: card for card in nodes_with_class(parser, "analysis-card")
    }
    expected = {
        "4.4": "可靠截取核心蛋白片段",
        "8.6": "完整染色体位置",
        "11.3": "每个基因在每个样本中的原始计数",
        "11.4": "环境处理与对照的原始计数",
        "11.5": "病原处理与对照的原始计数",
    }

    for source_id, phrase in expected.items():
        conditions = [
            node for node in cards[source_id].descendants() if "beginner-condition" in node.classes
        ]
        assert len(conditions) == 1
        assert phrase in conditions[0].all_text()


def test_beginner_html_is_synchronized_from_its_tsv_contract() -> None:
    subprocess.run(
        [sys.executable, str(BEGINNER_SYNC_PATH), "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_all_58_cards_have_beginner_takeaways() -> None:
    parser = parse_html()
    cards = nodes_with_class(parser, "analysis-card")
    assert len(cards) == 58
    assert [card.attrs["data-source-id"] for card in cards] == EXPECTED_IDS

    technical_starts = re.compile(
        r"^(?:stable_id|analysis_scope|results/|HMMER|BLASTP|MAFFT|OrthoFinder|"
        r"IMPLEMENTED|CONDITIONALLY_AVAILABLE|EXTERNAL_IMPORT|NOT_SUPPORTED)\b",
        re.I,
    )
    for card in cards:
        takeaways = [node for node in card.descendants() if "analysis-takeaway" in node.classes]
        assert len(takeaways) == 1, card.attrs["data-source-id"]
        takeaway = takeaways[0]
        labels = [
            node
            for node in takeaway.descendants()
            if node.tag == "strong" and node.all_text().strip() == "一句话先懂："
        ]
        assert len(labels) == 1, card.attrs["data-source-id"]
        body = re.sub(r"\s+", " ", " ".join(takeaway.text_parts)).strip()
        assert len(body) >= 45, (card.attrs["data-source-id"], len(body))
        assert len(re.findall(r"[。！？]", body)) in {1, 2}, (
            card.attrs["data-source-id"],
            body,
        )
        assert technical_starts.search(body) is None, (card.attrs["data-source-id"], body)


def test_statuses_are_chinese_first_but_machine_values_are_preserved() -> None:
    parser = parse_html()
    cards = nodes_with_class(parser, "analysis-card")
    assert Counter(card.attrs["data-state"] for card in cards) == EXPECTED_STATE_COUNTS

    for card in cards:
        state = card.attrs["data-state"]
        badges = [node for node in card.descendants() if "state-badge" in node.classes]
        assert len(badges) == 1
        badge_text = re.sub(r"\s+", " ", badges[0].all_text()).strip()
        assert badge_text.startswith(STATE_LABELS[state]), (state, badge_text)
        assert state in badge_text
        assert badges[0].attrs.get("data-state-label") == state

    state_filter = find_by_id(parser, "stateFilter")
    options = [node for node in state_filter.descendants() if node.tag == "option"]
    option_by_value = {option.attrs.get("value"): option.all_text().strip() for option in options}
    for state, chinese in STATE_LABELS.items():
        assert option_by_value[state].startswith(chinese)
        assert state in option_by_value[state]


def test_terminology_tsv_has_chinese_primary_labels_and_internal_categories() -> None:
    rows = read_terms()
    assert len(rows) >= 40
    assert {row["category"] for row in rows} == ALLOWED_TERM_CATEGORIES
    assert len({row["term_id"] for row in rows}) == len(rows)
    assert all(row["chinese_primary"].strip() for row in rows)
    assert all(row["technical_form"].strip() for row in rows)
    assert all(len(row["plain_definition_zh"].strip()) >= 18 for row in rows)
    assert all(len(row["panfamflow_usage_zh"].strip()) >= 18 for row in rows)
    assert {row["is_internal"] for row in rows} <= {"TRUE", "FALSE"}

    by_technical = {row["technical_form"]: row for row in rows}
    for technical_form, category in REQUIRED_INTERNAL_TERMS.items():
        row = by_technical[technical_form]
        assert row["category"] == category
        assert row["is_internal"] == "TRUE"

    for row in rows:
        if row["category"].startswith("PANFAMFLOW_"):
            assert row["is_internal"] == "TRUE"
        else:
            assert row["is_internal"] == "FALSE"


def test_glossary_visually_separates_chinese_technical_and_internal_terms() -> None:
    parser = parse_html()
    glossary = find_by_id(parser, "glossary")
    text = re.sub(r"\s+", " ", glossary.all_text())
    for label in (
        "学界常用概念",
        "软件、文件格式与通用缩写",
        "PanFamFlow 内部字段",
        "PanFamFlow 内部状态码与固定值",
        "通俗解释",
        "在 PanFamFlow 中怎么用",
    ):
        assert label in text
    assert len([node for node in glossary.descendants() if "term-cn" in node.classes]) == len(
        read_terms()
    )
    assert len([node for node in glossary.descendants() if "technical-term" in node.classes]) == 0
    internal_labels = [node for node in glossary.descendants() if "internal-label" in node.classes]
    assert len(internal_labels) >= len(REQUIRED_INTERNAL_TERMS)


def test_known_english_titles_have_chinese_primary_forms() -> None:
    text = HTML_PATH.read_text(encoding="utf-8")
    for phrase in (
        "核心型 / 近核心型 / 壳层型 / 稀有型",
        "标准化显示",
        "全条件汇总",
        "非生物胁迫响应",
        "生物胁迫响应",
    ):
        assert phrase in text

    parser = parse_html()
    headings = [
        re.sub(r"\s+", " ", node.all_text()).strip()
        for node in parser.all_nodes
        if node.tag in {"h1", "h2", "h3", "h4"}
    ]
    assert "Abiotic Stress 响应" not in headings
    assert "Biotic Stress 响应" not in headings
    assert "差异表达基因跨条件重叠分析（Global）" not in headings
    assert all(not re.match(r"^[A-Z][A-Z0-9 _/.-]{5,}$", heading) for heading in headings)


def test_legacy_ogg_label_is_explained_and_not_used_as_a_primary_heading() -> None:
    parser = parse_html()
    headings = [
        re.sub(r"\s+", " ", node.all_text()).strip()
        for node in parser.all_nodes
        if node.tag in {"h1", "h2", "h3", "h4"}
    ]
    assert all("OGG" not in heading for heading in headings)

    chapter_six = find_by_id(parser, "chapter-6")
    explanation = re.sub(r"\s+", " ", chapter_six.all_text())
    assert "PanFamFlow 不把 OGG 当作第三种规范数据类型" in explanation
    assert "分层正交组（HOG）" in explanation
    assert "普通正交组（OG）" in explanation


def test_toy_and_fixture_are_not_primary_teaching_labels() -> None:
    parser = parse_html()
    headings_and_controls = [
        re.sub(r"\s+", " ", node.all_text()).strip()
        for node in parser.all_nodes
        if node.tag in {"h1", "h2", "h3", "h4", "button"}
    ]
    assert all("fixture" not in text.lower() for text in headings_and_controls)
    assert all("toy" not in text.lower() for text in headings_and_controls)
    assert "专门构造的极小测试数据" in parser.root.all_text()


def test_conditional_de_tutorial_describes_reachable_toy_complete_path() -> None:
    """The tutorial must not contradict the executable raw-count DE path."""
    parser = parse_html()
    de_cards_text = " ".join(
        find_by_id(parser, f"analysis-11-{index}").all_text() for index in (3, 4, 5)
    )

    for stale_claim in (
        "当前没有可到达的完整规则和规范输出",
        "当前教程只能说明合规 DEG overlap 所需的输入和 QC，不能报告分析结果",
        "本地 toy 未生成该分析",
        "toy 示例未提供满足 raw counts、重复、design/contrast、效应量与 FDR 要求的外部结果",
    ):
        assert stale_claim not in de_cards_text

    for source_id in ("11-3", "11-4", "11-5"):
        evidence = re.sub(r"\s+", " ", find_by_id(parser, f"toy-{source_id}").all_text())
        assert "toy_complete" in evidence
        assert "原始整数计数" in evidence
        assert "DESeq2" in evidence

    chapter_text = re.sub(r"\s+", " ", find_by_id(parser, "chapter-11").all_text())
    for output in (
        "deseq2_fit_qc.tsv",
        "deseq2_contrast_results.tsv",
        "deg_membership.tsv",
        "Fig34_stress_expression_and_comparison.pdf",
    ):
        assert output in chapter_text
    assert "gene-wise dispersion" in chapter_text
    run_panel = find_by_id(parser, "panel-analysis-11-3-run").all_text()
    assert run_panel.count("results/11_expression/deseq2_fit_qc.tsv") == 1


def test_conditional_synteny_tutorial_separates_precomputed_and_native_evidence() -> None:
    parser = parse_html()
    card_text = re.sub(r"\s+", " ", find_by_id(parser, "analysis-8-6").all_text())
    evidence = re.sub(r"\s+", " ", find_by_id(parser, "toy-8-6").all_text())

    assert "本地 toy 未生成该分析" not in card_text
    for phrase in ("toy_complete", "预计算", "有序多锚点块", "原生 JCVI"):
        assert phrase in evidence
    for figure in ("Fig17", "Fig21", "Fig22"):
        assert figure in evidence


def test_four_plain_language_scientific_redlines_are_visible() -> None:
    text = re.sub(r"\s+", " ", parse_html().root.all_text())
    for phrase in (
        "树上分支不等于 OrthoFinder HOG",
        "注释中没有检出，不等于已经验证基因丢失",
        "单个成对 Ka/Ks > 1 不等于已经证明正选择",
        "不同物种的 TPM 不能直接比较",
    ):
        assert phrase in text
    for exact_boundary in (
        "clade、OrthoFinder HOG、目标家族 pan-locus 不是同一层级",
        "annotation absence 不等于 validated gene loss",
        "单个 pairwise Ka/Ks > 1 既不是正选择证明",
        "TPM 不可天然跨物种比较",
    ):
        assert exact_boundary in text


def test_no_remote_runtime_assets_or_retired_domain() -> None:
    raw = HTML_PATH.read_text(encoding="utf-8")
    parser = parse_html()
    retired_domain = "llp98" + ".work"
    assert retired_domain not in raw
    assert parser.external_scripts == []
    assert parser.external_stylesheets == []
    assert parser.remote_media == []
    assert "@import" not in raw
    assert re.search(r"url\(\s*['\"]?(?:https?:)?//", raw, re.I) is None


def test_analysis_and_chapter_anchors_remain_unique() -> None:
    parser = parse_html()
    all_ids = [node.attrs["id"] for node in parser.all_nodes if node.attrs.get("id")]
    assert len(all_ids) == len(set(all_ids))

    analysis_ids = [
        node.attrs["id"]
        for node in nodes_with_class(parser, "analysis-card")
        if node.attrs.get("id", "").startswith("analysis-")
    ]
    assert analysis_ids == ["analysis-" + source_id.replace(".", "-") for source_id in EXPECTED_IDS]
    chapter_ids = [
        node.attrs["id"]
        for node in nodes_with_class(parser, "chapter")
        if node.attrs.get("id", "").startswith("chapter-")
    ]
    assert chapter_ids == [f"chapter-{chapter}" for chapter in range(4, 12)]
