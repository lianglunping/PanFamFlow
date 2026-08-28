"""Regression tests for the 58 per-analysis beginner micro-lessons."""

# Chinese prose assertions intentionally contain fullwidth punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import html
import importlib.util
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

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
    "plot_value_source_column_zh",
    "plot_color_source_column_zh",
    "plot_values",
    "plot_colors",
    "plot_value_label_zh",
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
PLOT_COLORS = {"blue", "green", "orange", "red", "grey", "neutral", "purple"}
PLOT_VALUE_SPECIAL_SOURCES = {"教学行序"}
PLOT_COLOR_SPECIAL_SOURCES = {"plot_values连续色", "固定教学色"}


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
        assert len(row["input_headers_zh"].split("｜")) == len(row["input_row_zh"].split("｜"))
        output_headers = row["output_headers_zh"].split("｜")
        output_rows = row["output_rows_zh"].split("；")
        assert len(output_headers) >= 2
        assert len(output_rows) >= 2
        assert all(len(item.split("｜")) == len(output_headers) for item in output_rows)
        value_source = row["plot_value_source_column_zh"]
        color_source = row["plot_color_source_column_zh"]
        assert value_source in output_headers or value_source in PLOT_VALUE_SPECIAL_SOURCES
        assert color_source in output_headers or color_source in PLOT_COLOR_SPECIAL_SOURCES
        assert row["plot_value_label_zh"] == value_source
        plot_values = [float(item) for item in row["plot_values"].split("｜")]
        plot_colors = row["plot_colors"].split("｜")
        assert len(plot_values) == len(plot_colors) == len(output_rows)
        assert all(math.isfinite(item) for item in plot_values)
        assert set(plot_colors) <= PLOT_COLORS
        if value_source == "教学行序":
            assert plot_values == list(range(1, len(output_rows) + 1))
        assert row["reading_question_zh"].endswith("？")
        assert row["reading_answer_zh"].endswith("。")
        assert row["normal_zh"].endswith("。")
        assert row["stop_zh"].endswith("。")
        assert row["next_zh"].endswith("。")


def test_color_source_contract_is_consistent_for_all_58_rows() -> None:
    for row in read_rows():
        headers = row["output_headers_zh"].split("｜")
        output_rows = [item.split("｜") for item in row["output_rows_zh"].split("；")]
        values = [float(item) for item in row["plot_values"].split("｜")]
        colors = row["plot_colors"].split("｜")
        color_source = row["plot_color_source_column_zh"]
        if color_source in headers:
            index = headers.index(color_source)
            mapping: dict[str, str] = {}
            for output_row, color in zip(output_rows, colors, strict=True):
                source_value = output_row[index]
                assert mapping.setdefault(source_value, color) == color, row["source_id"]
        elif color_source == "固定教学色":
            assert len(set(colors)) == 1, row["source_id"]
        else:
            assert color_source == "plot_values连续色"
            for output_row, value, color in zip(output_rows, values, colors, strict=True):
                row_text = "｜".join(output_row)
                if color == "grey":
                    assert re.search(r"缺失|不计算|不能解释|只描述方向|先暂停", row_text)
                elif value < 0:
                    assert color == "blue", row["source_id"]
                elif any(item < 0 for item in values):
                    assert color == ("neutral" if value == 0 else "red"), row["source_id"]


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
    color_labels = {
        "blue": "蓝色",
        "green": "绿色",
        "orange": "橙色",
        "red": "红色",
        "grey": "灰色",
        "neutral": "白色",
        "purple": "紫色",
    }
    for row in read_rows():
        svg = sync.micro_svg(row)
        output_rows = [item.split("｜") for item in row["output_rows_zh"].split("；")]
        assert f'data-source-id="{row["source_id"]}"' in svg
        assert f'data-result-rows="{len(output_rows)}"' in svg
        assert svg.count('class="micro-data-row"') == len(output_rows), row["source_id"]
        assert row["plot_value_label_zh"] in svg
        for value, color in zip(
            row["plot_values"].split("｜"),
            row["plot_colors"].split("｜"),
            strict=True,
        ):
            assert f'data-plot-value="{sync.format_plot_value(float(value))}"' in svg
            assert f'data-plot-color="{color}"' in svg
            assert color_labels[color] in svg
        assert 'data-plot-value="1.2e+06"' not in svg
        assert 'data-plot-value="1.3e+06"' not in svg
        for output_row in output_rows:
            for cell in output_row:
                assert html.escape(cell) in svg, (row["source_id"], output_row, cell)


def geometry(svg: str) -> list[str]:
    return re.findall(r"<(?:rect|circle|path)\b[^>]*>", svg)


def row_group(svg: str, row_index: int) -> str:
    match = re.search(
        rf'<g class="micro-data-row" data-row="{row_index}".*?</g>',
        svg,
        re.DOTALL,
    )
    assert match is not None
    return match.group(0)


def test_micro_figure_geometry_uses_only_explicit_plot_contract() -> None:
    sync = load_sync_module()
    example = next(row for row in read_rows() if row["source_id"] == "5.3")
    before = sync.micro_svg(example)
    prose_changed = dict(example)
    prose_changed["output_rows_zh"] = example["output_rows_zh"].replace(
        "乙组高一千一百", "乙组高九千九百九十九", 1
    )
    prose_after = sync.micro_svg(prose_changed)
    assert geometry(before) == geometry(prose_after)
    assert "乙组高九千九百九十九" in prose_after
    assert "乙组高九千九百九十九" not in before

    plot_changed = dict(example)
    plot_changed["plot_values"] = "0.04｜0.18"
    plot_after = sync.micro_svg(plot_changed)
    assert geometry(before) != geometry(plot_after)


def test_required_plot_values_are_exact_ascii_numbers() -> None:
    rows = {row["source_id"]: row for row in read_rows()}
    assert rows["5.2"]["plot_values"] == "3100｜4200"
    assert rows["5.5"]["plot_values"] == "380｜420"
    assert rows["10.13"]["plot_values"] == "2｜1｜1"
    assert rows["7.1"]["plot_values"] == "1200000｜1300000｜900000"
    assert rows["7.1"]["plot_colors"] == "blue｜blue｜orange"
    assert rows["7.2"]["plot_color_source_column_zh"] == "材料"
    assert rows["7.3"]["plot_values"] == "1｜0.6｜0"
    assert rows["7.3"]["plot_value_label_zh"] == "每千万长度成员数"
    assert rows["8.2"]["plot_values"] == "40｜25｜35"
    assert rows["5.5"]["plot_value_label_zh"] == "中间蛋白长度"
    assert rows["10.3"]["plot_values"] == "16｜9｜12"
    assert rows["10.6"]["plot_values"] == "20｜10｜15"
    assert rows["10.10"]["plot_values"] == "1.3｜0.9｜1.1"
    assert rows["10.12"]["plot_values"] == "1.2｜0.8｜1.5"
    assert rows["10.13"]["plot_values"] == "2｜1｜1"
    assert rows["10.14"]["plot_values"] == "1｜2｜6"
    assert rows["10.14"]["plot_value_label_zh"] == "名次"
    assert rows["10.14"]["y_axis_zh"] == "名次"
    assert "名次" in rows["10.14"]["legend_zh"]
    assert "总出现次数" not in rows["10.14"]["legend_zh"]
    assert "chinese_number" not in SYNC.read_text(encoding="utf-8")


def test_legends_do_not_claim_unrendered_secondary_geometry() -> None:
    rows = {row["source_id"]: row for row in read_rows()}
    assert "浅色点" not in rows["6.4"]["legend_zh"]
    assert "整根柱为百分之百" not in rows["6.7"]["legend_zh"]
    assert "深色柱为总次数" not in rows["10.2"]["legend_zh"]
    assert rows["11.3"]["x_axis_zh"] == "效应方向与大小"
    assert rows["11.4"]["x_axis_zh"] == "效应方向与大小"
    assert rows["11.5"]["x_axis_zh"] == "效应方向与大小"


def test_plot_contract_parser_rejects_bad_length_token_and_nonfinite_values() -> None:
    sync = load_sync_module()
    base = next(row for row in read_rows() if row["source_id"] == "4.2")
    bad_contracts = (
        {"plot_values": "1"},
        {"plot_values": "1｜nan"},
        {"plot_colors": "blue｜unknown"},
    )
    for update in bad_contracts:
        changed = dict(base)
        changed.update(update)
        with pytest.raises(ValueError):
            sync.parse_plot_contract(changed, 2)


def test_plot_source_contract_rejects_drifted_sources_labels_and_group_colors() -> None:
    sync = load_sync_module()
    base = next(row for row in read_rows() if row["source_id"] == "7.1")
    headers = base["output_headers_zh"].split("｜")
    output_rows = [item.split("｜") for item in base["output_rows_zh"].split("；")]
    bad_contracts = (
        {"plot_value_source_column_zh": "不存在的列", "plot_value_label_zh": "不存在的列"},
        {"plot_value_label_zh": "自行改名的单位"},
        {"plot_color_source_column_zh": "不存在的列"},
        {"plot_colors": "blue｜green｜orange"},
    )
    for update in bad_contracts:
        changed = dict(base)
        changed.update(update)
        with pytest.raises(ValueError):
            sync.validate_plot_source_contract(changed, headers, output_rows)


def test_explicit_signed_percentage_and_fdr_values_change_geometry() -> None:
    sync = load_sync_module()
    rows = {row["source_id"]: row for row in read_rows()}
    cases = (
        ("5.3", "0.02｜0.18", "0.04｜0.18", None),
        ("8.1", "40｜30｜20｜10", "45｜30｜20｜5", None),
        ("10.5", "1.5｜-0.3｜0", "1.5｜0.3｜0", "red｜red｜neutral"),
    )
    for source_id, before_values, after_values, after_colors in cases:
        example = rows[source_id]
        assert example["plot_values"] == before_values
        changed = dict(example)
        changed["plot_values"] = after_values
        if after_colors is not None:
            changed["plot_colors"] = after_colors
        assert geometry(sync.micro_svg(example)) != geometry(sync.micro_svg(changed))


def test_semantic_color_contract_matches_de_signed_zero_and_missing_states() -> None:
    sync = load_sync_module()
    rows = {row["source_id"]: row for row in read_rows()}
    expected = {
        "10.5": ((1, "v-bad"), (2, "v-mid"), (3, "v-neutral")),
        "11.4": ((1, "v-bad"), (2, "v-mid"), (3, "v-low")),
        "11.5": ((1, "v-bad"), (2, "v-mid"), (3, "v-low")),
        "11.7": ((4, "v-low"),),
    }
    for source_id, states in expected.items():
        svg = sync.micro_svg(rows[source_id])
        for row_index, css_class in states:
            assert f'class="{css_class}"' in row_group(svg, row_index)


def test_continuous_matrix_intensity_follows_explicit_values() -> None:
    sync = load_sync_module()
    rows = {row["source_id"]: row for row in read_rows()}
    for source_id, expected_order in (("4.3", [2, 1, 3]), ("11.7", [1, 3, 2])):
        svg = sync.micro_svg(rows[source_id])
        opacity = {}
        for row_index in expected_order:
            match = re.search(r'opacity="([0-9.]+)"', row_group(svg, row_index))
            assert match is not None
            opacity[row_index] = float(match.group(1))
        assert opacity[expected_order[0]] > opacity[expected_order[1]] > opacity[expected_order[2]]


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
        item in composition for item in ("百分之四十", "百分之三十", "百分之二十", "百分之十")
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
        if any(term in legend for term in ("分支", "细线", "粗线", "横线", "中线", "竖线", "线段")):
            assert "<path" in svg, row["source_id"]
        if "缺失" in legend:
            assert "缺失" in row["output_rows_zh"], row["source_id"]


def test_decision_and_qc_colors_match_the_legend() -> None:
    sync = load_sync_module()
    rows = {row["source_id"]: row for row in read_rows()}

    expected = {
        "4.1": {"基因甲｜保留": "v-good", "基因乙｜待复核": "v-warn", "基因丙｜排除": "v-bad"},
        "6.3": {
            "组甲｜八｜零｜通过": "v-good",
            "组乙｜三｜二｜复核": "v-warn",
            "组丙｜一｜四｜暂停": "v-bad",
        },
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
    for official_url in (
        "https://learn.microsoft.com/en-us/windows/wsl/install",
        "https://git-scm.com/install/",
        "https://docs.astral.sh/uv/getting-started/installation/",
        "https://docs.conda.io/projects/conda/en/stable/user-guide/install/",
    ):
        assert f'href="{official_url}"' in body


def test_mobile_micro_figure_scroll_is_contained_inside_the_figure() -> None:
    css = re.sub(r"\s+", "", HTML.read_text(encoding="utf-8"))
    assert "html,body{max-width:100%;overflow-x:hidden}" in css
    assert ".analysis-result-grid>figure{min-width:0;max-width:100%;overflow-x:auto" in css
    assert ".analysis-result-grid>div{min-width:0;max-width:100%}" in css
    assert ".analysis-micro-figure{display:block;width:100%;min-width:680px;max-width:none" in css
    assert (
        "@media(max-width:760px){.analysis-result-grid{grid-template-columns:minmax(0,1fr)}" in css
    )


def test_analysis_example_sync_is_idempotent() -> None:
    subprocess.run([sys.executable, str(SYNC), "--check"], cwd=ROOT, check=True)
