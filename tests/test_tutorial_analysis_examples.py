"""Regression tests for the 58 per-analysis beginner micro-lessons."""

# Chinese prose assertions intentionally contain fullwidth punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "TUTORIAL_ANALYSIS_EXAMPLES.tsv"
HTML = ROOT / "docs" / "index.html"
SYNC = ROOT / "scripts" / "sync_tutorial_beginner_language.py"

FIELDS = [
    "source_id",
    "concept_zh",
    "why_zh",
    "input_headers_zh",
    "input_row_zh",
    "operation_zh",
    "visual_type",
    "visual_title_zh",
    "x_axis_zh",
    "y_axis_zh",
    "legend_zh",
    "output_headers_zh",
    "output_rows_zh",
    "reading_question_zh",
    "reading_answer_zh",
    "normal_zh",
    "stop_zh",
    "next_zh",
]
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
SUPPORTED_VISUALS = {
    "decision",
    "tree",
    "matrix",
    "sequence",
    "distribution",
    "comparison",
    "curve",
    "chromosome",
    "links",
    "scatter",
    "bars",
    "expression",
}


def read_rows() -> list[dict[str, str]]:
    with CONTRACT.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert reader.fieldnames == FIELDS
        return list(reader)


def test_analysis_example_contract_is_complete_and_frozen() -> None:
    rows = read_rows()
    assert [row["source_id"] for row in rows] == EXPECTED_IDS
    assert len(rows) == len({row["source_id"] for row in rows}) == 58

    for row in rows:
        assert all(row[field].strip() for field in FIELDS[1:]), row["source_id"]
        assert row["visual_type"] in SUPPORTED_VISUALS
        assert len(row["input_headers_zh"].split("｜")) >= 2
        assert len(row["input_headers_zh"].split("｜")) == len(
            row["input_row_zh"].split("｜")
        )
        output_headers = row["output_headers_zh"].split("｜")
        output_rows = row["output_rows_zh"].split("；")
        assert len(output_headers) >= 2
        assert len(output_rows) >= 2
        assert all(len(item.split("｜")) == len(output_headers) for item in output_rows)
        assert row["reading_question_zh"].endswith("？")
        assert row["reading_answer_zh"].endswith("。")
        assert row["normal_zh"].endswith("。")
        assert row["stop_zh"].endswith("。")
        assert row["next_zh"].endswith("。")


def test_analysis_examples_are_item_specific_not_majority_boilerplate() -> None:
    rows = read_rows()
    for field in ("concept_zh", "why_zh", "operation_zh", "stop_zh", "next_zh"):
        values = [row[field] for row in rows]
        assert len(set(values)) >= 55, field


def test_all_58_micro_lessons_render_a_figure_and_result_table() -> None:
    text = HTML.read_text(encoding="utf-8")
    assert text.count('class="analysis-micro-lesson"') == 58
    assert text.count('class="analysis-micro-figure"') == 58
    assert text.count('class="analysis-example-table"') == 58
    assert text.count('role="img"') >= 58
    assert text.count("本页数值只用于练习读图，不代表真实水稻分析结果") == 58
    assert text.count("先懂一个概念") == 58
    assert text.count('class="analysis-why-title"') == 58
    assert text.count("先试着回答") == 58
    assert text.count("什么情况先暂停") == 58

    for source_id in EXPECTED_IDS:
        slug = source_id.replace(".", "-")
        card = re.search(
            rf'<article class="analysis-card"[^>]*data-source-id="{re.escape(source_id)}".*?</article>',
            text,
            re.DOTALL,
        )
        assert card is not None, source_id
        body = card.group(0)
        assert f'id="micro-title-{slug}"' in body
        assert f'id="micro-desc-{slug}"' in body
        assert f'aria-labelledby="micro-title-{slug} micro-desc-{slug}"' in body


def test_analysis_example_sync_is_idempotent() -> None:
    subprocess.run([sys.executable, str(SYNC), "--check"], cwd=ROOT, check=True)
