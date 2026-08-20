"""Plain-language and terminology regression checks for the PanFamFlow tutorial."""

# Chinese prose assertions intentionally contain fullwidth Chinese punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "docs" / "index.html"
TERMINOLOGY_PATH = ROOT / "docs" / "TUTORIAL_TERMINOLOGY.tsv"

EXPECTED_IDS = (
    [f"4.{index}" for index in range(1, 4)]
    + [f"5.{index}" for index in range(1, 7)]
    + [f"6.{index}" for index in range(1, 9)]
    + [f"7.{index}" for index in range(1, 4)]
    + [f"8.{index}" for index in range(1, 7)]
    + [f"9.{index}" for index in range(1, 7)]
    + [f"10.{index}" for index in range(1, 15)]
    + [f"11.{index}" for index in range(1, 6)]
)

STATE_LABELS = {
    "IMPLEMENTED": "已实现",
    "CONDITIONALLY_AVAILABLE": "有条件可用",
    "EXTERNAL_IMPORT": "需外部分析结果",
    "NOT_SUPPORTED": "当前未支持",
}

EXPECTED_STATE_COUNTS = Counter(
    {
        "IMPLEMENTED": 11,
        "CONDITIONALLY_AVAILABLE": 29,
        "EXTERNAL_IMPORT": 2,
        "NOT_SUPPORTED": 9,
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


def test_all_51_cards_have_beginner_takeaways() -> None:
    parser = parse_html()
    cards = nodes_with_class(parser, "analysis-card")
    assert len(cards) == 51
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
    assert "llp98.work" not in raw
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
