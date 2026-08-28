"""Regression tests for the 58 per-analysis beginner micro-lessons."""

# Chinese prose assertions intentionally contain fullwidth punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import html
import importlib.util
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
    "paired",
    "stacked",
    "multi_indicator",
    "de",
    "test",
}


def read_rows() -> list[dict[str, str]]:
    with CONTRACT.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert reader.fieldnames == FIELDS
        return list(reader)


def load_sync_module():
    spec = importlib.util.spec_from_file_location("tutorial_sync", SYNC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_every_micro_figure_contains_its_own_result_rows() -> None:
    sync = load_sync_module()
    for row in read_rows():
        svg = sync.micro_svg(row)
        output_rows = [item.split("｜") for item in row["output_rows_zh"].split("；")]
        assert f'data-source-id="{row["source_id"]}"' in svg
        assert f'data-result-rows="{len(output_rows)}"' in svg
        assert svg.count('class="micro-data-row"') == len(output_rows), row[
            "source_id"
        ]
        for output_row in output_rows:
            for cell in output_row:
                assert html.escape(cell) in svg, (row["source_id"], output_row, cell)


def test_micro_figure_changes_when_result_data_changes() -> None:
    sync = load_sync_module()
    example = next(row for row in read_rows() if row["source_id"] == "5.3")
    before = sync.micro_svg(example)
    changed = dict(example)
    changed["output_rows_zh"] = example["output_rows_zh"].replace(
        "乙组高一千一百", "乙组高九千九百九十九", 1
    )
    after = sync.micro_svg(changed)
    assert before != after
    assert "乙组高九千九百九十九" in after
    assert "乙组高九千九百九十九" not in before
    before_points = re.findall(r'<circle cx="(\d+)"', before)
    after_points = re.findall(r'<circle cx="(\d+)"', after)
    assert before_points != after_points


def test_percentage_geometry_uses_the_reported_percentage_not_the_prefix() -> None:
    sync = load_sync_module()
    rows = {row["source_id"]: row for row in read_rows()}

    sequence = rows["4.4"]
    sequence_headers = sequence["output_headers_zh"].split("｜")
    sequence_rows = [item.split("｜") for item in sequence["output_rows_zh"].split("；")]
    assert [sync.row_value(sequence_headers, row, "sequence") for row in sequence_rows] == [
        95,
        60,
        90,
    ]

    composition = rows["8.1"]
    composition_headers = composition["output_headers_zh"].split("｜")
    composition_rows = [
        item.split("｜") for item in composition["output_rows_zh"].split("；")
    ]
    assert [
        sync.row_value(composition_headers, row, "bars") for row in composition_rows
    ] == [40, 30, 20, 10]


def test_special_items_use_semantic_micro_figure_types() -> None:
    rows = {row["source_id"]: row for row in read_rows()}
    expected = {
        "4.4": "sequence",
        "6.1": "paired",
        "6.6": "stacked",
        "9.7": "multi_indicator",
        "11.4": "de",
        "11.5": "de",
    }
    assert {source_id: rows[source_id]["visual_type"] for source_id in expected} == expected
    assert "一致比例" in rows["4.4"]["output_headers_zh"]
    assert "家族组甲" in rows["6.1"]["output_headers_zh"]
    assert "普遍" in rows["6.6"]["output_headers_zh"]
    assert "基准值过小" in rows["9.7"]["output_rows_zh"]
    assert "不能计算" in rows["9.7"]["output_rows_zh"]


def test_special_statistical_lessons_have_verifiable_fields() -> None:
    rows = {row["source_id"]: row for row in read_rows()}
    required_headers = {
        "独立",
        "效应方向与大小",
        "多项比较后错误概率",
        "质量状态",
        "允许解释",
    }
    for source_id in ("5.3", "5.6", "11.3", "11.4", "11.5"):
        row = rows[source_id]
        headers = row["output_headers_zh"]
        assert all(term in headers for term in required_headers), source_id
        assert "越小" in row["concept_zh"], source_id
        assert "零点零五" in row["operation_zh"], source_id
        assert "通过" in row["output_rows_zh"], source_id
        assert "可以" in row["output_rows_zh"], source_id
        assert not re.search(r"较强|一般|可靠", row["output_rows_zh"]), source_id


def test_member_totals_and_unlocated_rows_are_internally_consistent() -> None:
    rows = {row["source_id"]: row for row in read_rows()}
    composition = rows["8.1"]["output_rows_zh"]
    assert "待定｜三｜百分之十" in composition
    assert all(
        item in composition
        for item in ("百分之四十", "百分之三十", "百分之二十", "百分之十")
    )

    chromosome = rows["7.3"]["output_rows_zh"]
    assert "未定位｜一｜不计算" in chromosome
    assert "第二染色体｜二｜零点六" in chromosome


def test_legend_claims_match_visible_svg_elements() -> None:
    sync = load_sync_module()
    for row in read_rows():
        svg = sync.micro_svg(row)
        legend = row["legend_zh"]
        assert "点形" not in legend, row["source_id"]
        if "圆点" in legend or "点" in legend:
            assert "<circle" in svg, row["source_id"]
        if "柱" in legend or "格" in legend:
            assert "<rect" in svg, row["source_id"]
        if any(
            term in legend
            for term in ("分支", "细线", "粗线", "横线", "中线", "竖线", "线段")
        ):
            assert "<path" in svg, row["source_id"]
        if "缺失" in legend:
            assert "缺失" in row["output_rows_zh"], row["source_id"]


def test_decision_and_qc_colors_match_the_legend() -> None:
    sync = load_sync_module()
    rows = {row["source_id"]: row for row in read_rows()}

    expected = {
        "4.1": {"基因甲｜保留": "v-good", "基因乙｜待复核": "v-warn", "基因丙｜排除": "v-bad"},
        "6.3": {"组甲｜八｜零｜通过": "v-good", "组乙｜三｜二｜复核": "v-warn", "组丙｜一｜四｜暂停": "v-bad"},
        "8.1": {"待定｜三｜百分之十｜三": "v-low"},
    }
    for source_id, markers in expected.items():
        svg = sync.micro_svg(rows[source_id])
        for marker, css_class in markers.items():
            group = re.search(
                rf'<g class="micro-data-row"[^>]*><title>[^<]*{re.escape(marker)}[^<]*</title>(.*?)</g>',
                svg,
                re.DOTALL,
            )
            assert group is not None, (source_id, marker)
            assert f'class="{css_class}"' in group.group(1), (source_id, marker)


def test_no_javascript_keeps_all_beginner_lessons_and_titles_visible() -> None:
    text = HTML.read_text(encoding="utf-8")
    noscript = re.search(r"<noscript><style>(.*?)</style>", text, re.DOTALL)
    assert noscript is not None
    css = re.sub(r"\s+", "", noscript.group(1))
    assert ".beginner-guide{display:block!important}" in css
    assert ".beginner-title{display:inline!important}" in css
    assert ".advanced-title{display:none!important}" in css
    assert text.count('<section class="beginner-guide"') == 58


def test_micro_lesson_sync_preserves_the_eight_step_first_run() -> None:
    text = HTML.read_text(encoding="utf-8")
    start = re.search(
        r'<section class="reference-section" id="start".*?</section>',
        text,
        re.DOTALL,
    )
    assert start is not None
    body = start.group(0)
    assert body.count('class="first-run-step"') == 8
    assert re.findall(r'class="first-run-step" data-step="([1-8])"', body) == [
        str(index) for index in range(1, 9)
    ]
    assert "uv run panfamflow validate -c examples/toy/config.yaml" in body
    assert "uv run --with 'snakemake==9.25.1' panfamflow run" in body
    assert "TOY RUN PASSED" in body


def test_analysis_example_sync_is_idempotent() -> None:
    subprocess.run([sys.executable, str(SYNC), "--check"], cwd=ROOT, check=True)
