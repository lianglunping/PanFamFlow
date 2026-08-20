from __future__ import annotations

import csv
import html
import re
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COVERAGE_PATH = REPO_ROOT / "docs" / "ANALYSIS_COVERAGE.tsv"
TUTORIAL_PATH = REPO_ROOT / "docs" / "index.html"
ALLOWED_STATES = {
    "IMPLEMENTED",
    "CONDITIONALLY_AVAILABLE",
    "EXTERNAL_IMPORT",
    "NOT_SUPPORTED",
}


def expected_source_ids() -> list[str]:
    ranges = ((4, 4), (5, 6), (6, 8), (7, 3), (8, 6), (9, 9), (10, 15), (11, 7))
    return [f"{chapter}.{item}" for chapter, count in ranges for item in range(1, count + 1)]


def read_coverage() -> list[dict[str, str]]:
    with COVERAGE_PATH.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def test_coverage_table_has_exact_58_source_items_and_audited_states() -> None:
    rows = read_coverage()
    assert [row["source_id"] for row in rows] == expected_source_ids()
    assert len({row["source_id"] for row in rows}) == 58
    assert set(rows[0]) == {
        "source_id",
        "source_title",
        "state",
        "evidence",
        "output",
        "limitation",
        "tutorial_anchor",
    }
    assert {row["state"] for row in rows} <= ALLOWED_STATES
    assert Counter(row["state"] for row in rows) == {
        "IMPLEMENTED": 21,
        "CONDITIONALLY_AVAILABLE": 29,
        "EXTERNAL_IMPORT": 2,
        "NOT_SUPPORTED": 6,
    }
    assert all(row["source_title"].strip() for row in rows)
    assert all(row["evidence"].strip() for row in rows)
    assert all(row["limitation"].strip() for row in rows)
    assert len({row["tutorial_anchor"] for row in rows}) == 58


def test_tutorial_has_all_analysis_anchors_states_and_teaching_dimensions() -> None:
    rows = read_coverage()
    text = TUTORIAL_PATH.read_text(encoding="utf-8")
    decoded = html.unescape(text)
    for chapter in range(4, 12):
        assert f'<section class="chapter" id="chapter-{chapter}"' in text
    for component in (
        "concepts",
        "why",
        "workflow",
        "table-reading",
        "figure-reading",
        "qc",
        "supported-claims",
        "unsupported-claims",
        "misreads",
    ):
        assert text.count(f'data-component="{component}"') >= 8

    for row in rows:
        article = re.search(
            rf'<article class="analysis-card" id="{re.escape(row["tutorial_anchor"])}" '
            rf'data-source-id="{re.escape(row["source_id"])}" data-chapter="\d+" '
            rf'data-state="{row["state"]}".*?>(.*?)</article>',
            text,
            flags=re.DOTALL,
        )
        assert article is not None
        assert row["state"] in article.group(1)
        for dimension in (
            "dimension-concept",
            "dimension-input",
            "dimension-operation",
            "dimension-interpretation",
        ):
            assert dimension in article.group(1)

    for guardrail in (
        "clade、OrthoFinder HOG、目标家族 pan-locus 不是同一层级",
        "annotation absence 不等于 validated gene loss",
        "单个 pairwise Ka/Ks > 1 既不是正选择证明",
        "TPM 不可天然跨物种比较",
    ):
        assert guardrail in decoded


def test_public_descriptions_do_not_claim_all_58_items_are_implemented() -> None:
    chinese_readme = (REPO_ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    audit = (REPO_ROOT / "docs" / "ANALYSIS_COVERAGE.zh-CN.md").read_text(encoding="utf-8")
    assert "不声称 58 项均已自动实现" in chinese_readme
    assert "不包含真实 HSP 数据复算" not in audit
    assert "不重算 HSP 数据" in audit
