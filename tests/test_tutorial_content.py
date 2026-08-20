# Chinese teaching assertions intentionally contain full-width punctuation.
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
MATRIX_PATH = ROOT / "docs" / "TUTORIAL_CONTENT_MATRIX.tsv"
TOY_PATH = ROOT / "docs" / "TUTORIAL_TOY_EVIDENCE_SCHEMA.tsv"
COVERAGE_PATH = ROOT / "docs" / "ANALYSIS_COVERAGE.tsv"
PENDING = "待本地 toy pipeline 验证后回填"
EXPECTED_IDS = (
    [f"4.{i}" for i in range(1, 5)]
    + [f"5.{i}" for i in range(1, 7)]
    + [f"6.{i}" for i in range(1, 9)]
    + [f"7.{i}" for i in range(1, 4)]
    + [f"8.{i}" for i in range(1, 7)]
    + [f"9.{i}" for i in range(1, 10)]
    + [f"10.{i}" for i in range(1, 16)]
    + [f"11.{i}" for i in range(1, 8)]
)
EXPECTED_COMPONENTS = {
    "learning-objectives",
    "concepts",
    "why",
    "research-unit",
    "inputs",
    "support-status",
    "config",
    "command",
    "workflow",
    "outputs",
    "table-reading",
    "figure-reading",
    "normal-abnormal",
    "qc",
    "supported-claims",
    "unsupported-claims",
    "misreads",
    "self-test",
}
EXPECTED_DIMENSIONS = {
    "dimension-concept",
    "dimension-input",
    "dimension-operation",
    "dimension-interpretation",
}


class Node:
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

    def has_ancestor_class(self, class_name: str) -> bool:
        node: Node | None = self
        while node is not None:
            if class_name in node.classes:
                return True
            node = node.parent
        return False


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
        self.pending_nodes: list[Node] = []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        self.all_nodes.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for idx in range(len(self.stack) - 1, 0, -1):
            if self.stack[idx].tag == tag:
                del self.stack[idx:]
                return

    def handle_data(self, data):
        self.stack[-1].text_parts.append(data)
        if PENDING in data:
            self.pending_nodes.append(self.stack[-1])


def read_matrix():
    with MATRIX_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_html():
    parser = TutorialParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    return parser


def find_by_id(parser: TutorialParser, node_id: str) -> Node:
    matches = [n for n in parser.all_nodes if n.attrs.get("id") == node_id]
    assert len(matches) == 1, (node_id, len(matches))
    return matches[0]


def test_matrix_has_exact_58_rows_and_stable_ids():
    rows = read_matrix()
    assert len(rows) == 58
    assert [row["source_id"] for row in rows] == EXPECTED_IDS
    assert [row["anchor"] for row in rows] == [
        "analysis-" + x.replace(".", "-") for x in EXPECTED_IDS
    ]
    assert len({row["anchor"] for row in rows}) == 58


def test_status_distribution_and_allowed_states():
    rows = read_matrix()
    counts = Counter(row["state"] for row in rows)
    assert counts == Counter(
        {
            "IMPLEMENTED": 21,
            "CONDITIONALLY_AVAILABLE": 29,
            "EXTERNAL_IMPORT": 2,
            "NOT_SUPPORTED": 6,
        }
    )
    assert {row["state"] for row in rows} == {
        "IMPLEMENTED",
        "CONDITIONALLY_AVAILABLE",
        "EXTERNAL_IMPORT",
        "NOT_SUPPORTED",
    }


def test_rich_matrix_and_chapter_statuses_match_authoritative_coverage():
    matrix = {row["source_id"]: row for row in read_matrix()}
    with COVERAGE_PATH.open(encoding="utf-8", newline="") as handle:
        coverage = list(csv.DictReader(handle, delimiter="\t"))
    assert list(matrix) == [row["source_id"] for row in coverage]
    for current in coverage:
        row = matrix[current["source_id"]]
        assert row["title"] == current["source_title"]
        assert row["state"] == current["state"]
        assert row["anchor"] == current["tutorial_anchor"]
        assert row["evidence_basis"] == current["evidence"]
        assert row["limitation"] == current["limitation"]

    parser = parse_html()
    state_order = (
        "IMPLEMENTED",
        "CONDITIONALLY_AVAILABLE",
        "EXTERNAL_IMPORT",
        "NOT_SUPPORTED",
    )
    for chapter in map(str, range(4, 12)):
        counts = Counter(
            row["state"] for row in coverage if row["source_id"].split(".", 1)[0] == chapter
        )
        summary = "；".join(f"{state}={counts[state]}" for state in state_order if counts[state])
        assert summary in find_by_id(parser, f"chapter-{chapter}").all_text()


def test_html_has_exact_anchors_and_matches_matrix_states():
    rows = read_matrix()
    parser = parse_html()
    ids = [
        n.attrs.get("id")
        for n in parser.all_nodes
        if n.attrs.get("id", "").startswith("analysis-") and "analysis-card" in n.classes
    ]
    assert ids == [row["anchor"] for row in rows]
    assert len(ids) == len(set(ids)) == 58
    for row in rows:
        card = find_by_id(parser, row["anchor"])
        assert "analysis-card" in card.classes
        assert card.attrs.get("data-source-id") == row["source_id"]
        assert card.attrs.get("data-state") == row["state"]
        assert row["title"] in card.all_text()


def test_every_analysis_card_has_four_teaching_dimensions_and_depth():
    parser = parse_html()
    for source_id in EXPECTED_IDS:
        card = find_by_id(parser, "analysis-" + source_id.replace(".", "-"))
        desc = list(card.descendants())
        present = set().union(*(node.classes for node in desc))
        assert present >= EXPECTED_DIMENSIONS, (source_id, EXPECTED_DIMENSIONS - present)
        for dim in EXPECTED_DIMENSIONS:
            nodes = [n for n in desc if dim in n.classes]
            assert len(nodes) == 1
            assert len(nodes[0].all_text()) >= 50, (source_id, dim, len(nodes[0].all_text()))


def test_each_chapter_has_all_18_required_components_and_self_test():
    parser = parse_html()
    for chapter in map(str, range(4, 12)):
        section = find_by_id(parser, f"chapter-{chapter}")
        components = {
            n.attrs.get("data-component")
            for n in section.descendants()
            if n.attrs.get("data-component")
        }
        assert components == EXPECTED_COMPONENTS, (
            chapter,
            EXPECTED_COMPONENTS - components,
            components - EXPECTED_COMPONENTS,
        )
        self_test = [
            n for n in section.descendants() if n.attrs.get("data-component") == "self-test"
        ]
        assert len(self_test) == 1
        assert any(n.tag == "details" for n in self_test[0].descendants())


def test_no_external_css_javascript_fonts_or_tracking():
    text = HTML_PATH.read_text(encoding="utf-8")
    parser = parse_html()
    for node in parser.all_nodes:
        if node.tag == "script":
            assert not node.attrs.get("src")
        if node.tag == "link":
            assert node.attrs.get("rel", "").lower() != "stylesheet"
        for attr in ("src", "href"):
            value = node.attrs.get(attr, "")
            if node.tag in {"script", "link", "img", "source", "iframe"}:
                assert not re.match(r"^(?:https?:)?//", value, re.I), (node.tag, attr, value)
    assert "@import" not in text
    assert not re.search(r"url\(\s*['\"]?(?:https?:)?//", text, re.I)
    assert "google-analytics" not in text.lower()
    assert "googletagmanager" not in text.lower()


def test_toy_evidence_is_backfilled_without_pending_claims():
    parser = parse_html()
    assert parser.pending_nodes == []
    assert PENDING not in HTML_PATH.read_text(encoding="utf-8")
    with TOY_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert rows
    assert all(row["status"] != PENDING for row in rows)
    assert {row["status"] for row in rows} <= {
        "VERIFIED",
        "DOCUMENTED",
        "VERIFIED_BY_TESTS",
        "TEST_COVERED_NOT_CAPTURED",
        "NOT_CAPTURED",
        "NOT_APPLICABLE",
        "NOT_PROVIDED",
    }
    assert any(row["status"] == "VERIFIED" for row in rows)
    assert any(row["status"] == "NOT_PROVIDED" for row in rows)


def test_no_obvious_unfinished_body_markers():
    text = HTML_PATH.read_text(encoding="utf-8")
    stripped = text.replace(PENDING, "")
    banned = [r"\bTODO\b", r"\bTBD\b", r"\bFIXME\b", r"Lorem ipsum", r"待补", r"此处插入"]
    for pattern in banned:
        assert re.search(pattern, stripped, re.I) is None, pattern


def test_required_scientific_boundaries_are_explicit():
    text = parse_html().root.all_text()
    required = [
        "clade、OrthoFinder HOG、目标家族 pan-locus 不是同一层级",
        "annotation absence 不等于 validated gene loss",
        "gene tree 不等于 species tree",
        "duplication pair 只是候选基因对，不等于 MCScanX/WGDI 识别的全基因组共线块",
        "单个 pairwise Ka/Ks>1 不等于已证明正选择",
        "Ks=0",
        "POTENTIAL_SATURATION",
        "motif hit 不等于 TF 结合",
        "TPM 不可天然跨物种比较",
        "NOT_APPLICABLE",
        "MISSING_IN_INPUT",
        "TPM 热图不能替代 raw counts + 设计矩阵的差异表达",
    ]
    normalized = re.sub(r"\s+", " ", text)
    for phrase in required:
        if phrase == "单个 pairwise Ka/Ks>1 不等于已证明正选择":
            assert re.search(
                r"单个 pairwise Ka/Ks\s*>\s*1 不等于(?:已|已经)证明正选择", normalized
            ), phrase
        else:
            assert phrase in normalized, phrase


def test_resolved_runtime_contracts_and_plot_truth_are_visible():
    text = HTML_PATH.read_text(encoding="utf-8")
    for phrase in [
        "orthofinder_result_dir.txt",
        "input.gff3s",
        "params.separator",
        "AUTO_ORTHOGROUP_FALLBACK",
        "orthology_group_type=ORTHOGROUP",
        "pan_family_class_dual_denominator.pdf",
        "duplication_stratified_distributions.pdf",
    ]:
        assert phrase in text
    assert "orthofinder.result_dir.txt" not in text
    assert "当前已知执行阻断" not in text


def test_selected_capability_states_match_current_local_audit():
    rows = {row["source_id"]: row for row in read_matrix()}
    assert rows["6.1"]["state"] == "CONDITIONALLY_AVAILABLE"
    assert rows["6.2"]["state"] == "IMPLEMENTED"
    assert rows["6.4"]["state"] == "IMPLEMENTED"
    assert rows["6.5"]["state"] == "IMPLEMENTED"
    assert rows["8.1"]["state"] == "IMPLEMENTED"
    assert rows["5.3"]["state"] == "CONDITIONALLY_AVAILABLE"
    assert rows["5.6"]["state"] == "CONDITIONALLY_AVAILABLE"
    assert rows["8.5"]["state"] == "CONDITIONALLY_AVAILABLE"
    assert rows["8.6"]["state"] == "NOT_SUPPORTED"
    assert rows["10.5"]["state"] == "CONDITIONALLY_AVAILABLE"
    assert rows["10.7"]["state"] == "CONDITIONALLY_AVAILABLE"
    assert rows["10.8"]["state"] == "IMPLEMENTED"
    assert rows["10.9"]["state"] == "IMPLEMENTED"
    assert rows["10.11"]["state"] == "CONDITIONALLY_AVAILABLE"
    assert rows["10.14"]["state"] == "IMPLEMENTED"
    assert rows["11.3"]["state"] == "NOT_SUPPORTED"


def test_external_expression_items_require_real_de_evidence():
    rows = {row["source_id"]: row for row in read_matrix()}
    assert rows["11.3"]["state"] == "NOT_SUPPORTED"
    for source_id in ("11.4", "11.5"):
        row = rows[source_id]
        assert row["state"] == "EXTERNAL_IMPORT"
        blob = " ".join(row.values()).lower()
        for token in ("raw", "design", "log2foldchange", "padj"):
            assert token in blob, (source_id, token)
        assert "tpm" in blob


def test_self_contained_interactions_and_print_support_exist():
    text = HTML_PATH.read_text(encoding="utf-8")
    for element_id in [
        "themeToggle",
        "menuToggle",
        "tutorialSearch",
        "chapterFilter",
        "stateFilter",
        "generatedConfig",
        "progressFill",
        "printPage",
        "claimExercise",
    ]:
        assert f'id="{element_id}"' in text
    assert "@media print" in text
    assert "localStorage" in text
    assert 'role="tab"' in text
    assert "<noscript>" in text


def test_matrix_required_fields_are_nonempty_and_specific():
    rows = read_matrix()
    required = [
        "source_id",
        "chapter",
        "title",
        "state",
        "biological_question",
        "required_inputs",
        "pipeline_entry",
        "canonical_outputs",
        "how_to_read",
        "qc_checks",
        "supported_claims",
        "unsupported_claims",
        "limitation",
        "toy_evidence_slot",
        "anchor",
    ]
    for row in rows:
        for field in required:
            assert row[field].strip(), (row["source_id"], field)
        assert len(row["how_to_read"]) >= 30
        assert len(row["qc_checks"]) >= 28
        assert "进一步分析" not in row["limitation"]
