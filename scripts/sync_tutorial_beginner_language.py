#!/usr/bin/env python3
"""Synchronize the 58-row beginner-language contract into the static tutorial."""

# Chinese tutorial strings intentionally use full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import csv
import html
import math
import re
from pathlib import Path

try:
    from tutorial_title_contract import PROFESSIONAL_ANALYSIS_TITLE_OVERRIDES
except ModuleNotFoundError:  # Loaded as a module from the repository root in tests.
    from scripts.tutorial_title_contract import PROFESSIONAL_ANALYSIS_TITLE_OVERRIDES

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs" / "TUTORIAL_BEGINNER_LANGUAGE.tsv"
EXAMPLES_PATH = ROOT / "docs" / "TUTORIAL_ANALYSIS_EXAMPLES.tsv"
COVERAGE_PATH = ROOT / "docs" / "ANALYSIS_COVERAGE.tsv"
HTML_PATH = ROOT / "docs" / "index.html"

FIELDS = (
    "source_id",
    "beginner_title_zh",
    "beginner_question_zh",
    "beginner_input_zh",
    "beginner_output_zh",
    "beginner_read_zh",
    "beginner_warning_zh",
)
EXAMPLE_FIELDS = (
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
PLOT_COLOR_CLASSES = {
    "blue": "v-mid",
    "green": "v-good",
    "orange": "v-warn",
    "red": "v-bad",
    "grey": "v-low",
    "neutral": "v-neutral",
    "purple": "v-purple",
}
PLOT_COLOR_LABELS = {
    "blue": "蓝色",
    "green": "绿色",
    "orange": "橙色",
    "red": "红色",
    "grey": "灰色",
    "neutral": "白色",
    "purple": "紫色",
}
PLOT_VALUE_SPECIAL_SOURCES = {"教学行序"}
PLOT_COLOR_SPECIAL_SOURCES = {"plot_values连续色", "固定教学色"}
PLOT_SOURCE_DISPLAY = {
    "plot_values连续色": "绘图数值的连续颜色",
    "固定教学色": "固定教学颜色",
}
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
CHAPTER_BEGINNER_TITLES = {
    "4": "先找全家族成员，再看它们的关系",
    "5": "比较基因内部结构",
    "6": "区分普遍成员和少见成员",
    "7": "查看基因位于染色体哪里",
    "8": "判断家族成员怎样复制产生",
    "9": "比较编码序列变化的快慢",
    "10": "寻找基因前方可能的调控线索",
    "11": "比较基因在不同样本中的活跃程度",
}
CHAPTER_TEN_GROUPS = (
    ("先认清有哪些线索", ("10.1", "10.2", "10.3")),
    ("按家族分组比较", ("10.4", "10.5", "10.6", "10.7")),
    ("按材料或群体比较", ("10.8", "10.9", "10.10", "10.11")),
    ("看重点线索和组合分组", ("10.12", "10.13", "10.14", "10.15")),
)
CHAPTER_TEN_ITEM_CONTEXT = {
    source_id: (group_index, label)
    for group_index, (label, source_ids) in enumerate(CHAPTER_TEN_GROUPS, start=1)
    for source_id in source_ids
}
DEFAULT_BEGINNER_CONDITION = "前一项结果已经看懂，材料名称和结果没有缺项；有疑问时先返回本章说明。"
CHAPTER_ACTIONS = {
    "4": "先按家族特征筛选，再把可靠成员放入关系比较",
    "5": "逐个统计长度和片段数量，再按分组比较",
    "6": "把每个材料中的成员记为检出或未检出，再汇总出现比例",
    "7": "把每个成员放到对应染色体位置，再汇总数量和密度",
    "8": "结合成员位置和周围连续对应基因，判断可能的复制来源",
    "9": "先配对相似基因，再分别统计两类编码变化",
    "10": "在每个基因前方寻找短序列线索，再按指定分组汇总",
    "11": "按样本整理每个基因的读数，再在可比条件内描述或比较",
}
ITEM_ACTION_OVERRIDES = {
    "4.1": "把相似候选逐个检查，记录保留、排除和待复核的依据",
    "4.2": "把可靠成员逐位置排齐，再根据序列差异建立成员关系图",
    "4.3": "按材料和家族分组计数，同时计算每个材料内部的组成比例",
    "4.4": "把可靠核心片段逐位置排齐，统计每个位置最常出现的氨基酸",
    "6.1": "分别建立材料关系图和成员有无图，再比较两者是否呈现相似分组",
    "6.2": "把每个家族组包含的基因和所在材料逐项列出，空缺也保留",
    "6.3": "汇总每个家族组的完整度、成员数和异常记录，标出不可靠分组",
    "6.4": "按成员出现于多少材料，把它们分成四类并同时报告两种总数口径",
    "6.5": "用不同材料加入顺序反复累计，记录每增加材料还能发现多少新成员",
    "6.6": "逐个材料统计四类成员的实际数量，再并列比较",
    "6.7": "把每个材料的四类数量除以该材料成员总数，再比较组成比例",
    "6.8": "把四类成员分别按家族分组计数，查看它们主要落在哪些分组",
    "8.5": "按复制来源给成员分组，再比较每组基因长度和内部片段数量",
    "8.6": "检查两个染色体片段上的多个相邻基因是否保持相同顺序和方向",
    "11.3": "先分别完成每个处理与对照的严格比较，再汇总各处理共有或特有的变化基因",
    "11.4": "在同一实验中比较环境处理与对照的独立样本，报告变化方向和大小",
    "11.5": "在同一实验中比较病原处理与对照的独立样本，报告变化方向和大小",
}
CONDITIONAL_BEGINNER_CONDITIONS = {
    "4.4": "已经可靠截取核心蛋白片段，并完成逐位置排齐；否则不运行本项。",
    "8.6": "已经准备完整染色体位置、全基因组蛋白序列和成片段对应证据；否则不运行本项。",
    "11.3": "已经准备每个基因在每个样本中的原始计数（必须是整数）、独立重复和预先确定的比较方向；否则不报告可靠变化。",
    "11.4": "已经准备环境处理与对照的原始计数（必须是整数）、独立重复和完整样本说明；否则不报告可靠变化。",
    "11.5": "已经准备病原处理与对照的原始计数（必须是整数）、独立重复和完整样本说明；否则不报告可靠变化。",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError(f"Unexpected columns in {path}: {reader.fieldnames}")
        rows = list(reader)
    if [row["source_id"] for row in rows] != EXPECTED_IDS:
        raise ValueError("Beginner-language source IDs must be the frozen 58-item order")
    for row in rows:
        for field in FIELDS[1:]:
            if not row[field].strip():
                raise ValueError(f"Blank {field} for {row['source_id']}")
    return rows


def split_cells(value: str) -> list[str]:
    return [item.strip() for item in value.split("｜")]


def parse_plot_contract(example: dict[str, str], row_count: int) -> tuple[list[float], list[str]]:
    source_id = example["source_id"]
    value_cells = split_cells(example["plot_values"])
    color_tokens = split_cells(example["plot_colors"])
    if len(value_cells) != row_count or len(color_tokens) != row_count:
        raise ValueError(f"Plot contract length mismatch for {source_id}")
    try:
        values = [float(item) for item in value_cells]
    except ValueError as exc:
        raise ValueError(f"Non-numeric plot value for {source_id}") from exc
    if not all(math.isfinite(item) for item in values):
        raise ValueError(f"Non-finite plot value for {source_id}")
    invalid_colors = set(color_tokens) - set(PLOT_COLOR_CLASSES)
    if invalid_colors:
        raise ValueError(f"Invalid plot colors for {source_id}: {sorted(invalid_colors)}")
    return values, color_tokens


def validate_plot_source_contract(
    example: dict[str, str], headers: list[str], rows: list[list[str]]
) -> None:
    source_id = example["source_id"]
    value_source = example["plot_value_source_column_zh"]
    color_source = example["plot_color_source_column_zh"]
    if value_source not in headers and value_source not in PLOT_VALUE_SPECIAL_SOURCES:
        raise ValueError(f"Plot value source is not an output column for {source_id}")
    if example["plot_value_label_zh"] != value_source:
        raise ValueError(f"Plot value label does not match its source for {source_id}")
    if color_source not in headers and color_source not in PLOT_COLOR_SPECIAL_SOURCES:
        raise ValueError(f"Plot color source is not an output column for {source_id}")

    values, colors = parse_plot_contract(example, len(rows))
    if value_source == "教学行序" and values != list(range(1, len(rows) + 1)):
        raise ValueError(f"Teaching row order is not 1..n in {source_id}")
    if color_source in headers:
        source_index = headers.index(color_source)
        mapping: dict[str, str] = {}
        for row, color in zip(rows, colors, strict=True):
            source_value = row[source_index]
            previous = mapping.setdefault(source_value, color)
            if previous != color:
                raise ValueError(
                    f"Inconsistent color for {color_source}={source_value} in {source_id}"
                )
        return
    if color_source == "固定教学色":
        if len(set(colors)) != 1:
            raise ValueError(f"Fixed teaching color varies within {source_id}")
        return

    has_negative = any(value < 0 for value in values)
    non_grey_colors = {color for color in colors if color != "grey"}
    if not has_negative and len(non_grey_colors) > 1:
        raise ValueError(f"Continuous non-negative color uses multiple base colors in {source_id}")
    for row, value, color in zip(rows, values, colors, strict=True):
        row_text = "｜".join(row)
        if color == "grey":
            if not re.search(r"缺失|不计算|不能解释|只描述方向|先暂停", row_text):
                raise ValueError(f"Grey continuous row lacks an explicit stop state in {source_id}")
        elif value < 0 and color != "blue":
            raise ValueError(f"Negative continuous value is not blue in {source_id}")
        elif has_negative and value == 0 and color != "neutral":
            raise ValueError(f"Zero signed value is not neutral in {source_id}")
        elif has_negative and value > 0 and color != "red":
            raise ValueError(f"Positive signed value is not red in {source_id}")


def format_plot_value(value: float) -> str:
    """Render a validated finite plot value without scientific notation."""
    if value == 0:
        return "0"
    if value.is_integer():
        return str(int(value))
    return f"{value:.15f}".rstrip("0").rstrip(".")


def plot_source_display(value: str) -> str:
    return PLOT_SOURCE_DISPLAY.get(value, value)


def read_examples() -> list[dict[str, str]]:
    with EXAMPLES_PATH.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != EXAMPLE_FIELDS:
            raise ValueError(f"Unexpected columns in {EXAMPLES_PATH}: {reader.fieldnames}")
        rows = list(reader)
    if [row["source_id"] for row in rows] != EXPECTED_IDS:
        raise ValueError("Analysis-example source IDs must be the frozen 58-item order")
    for row in rows:
        source_id = row["source_id"]
        for field in EXAMPLE_FIELDS[1:]:
            if not row[field].strip():
                raise ValueError(f"Blank {field} for {source_id}")
        if row["visual_type"] not in SUPPORTED_VISUALS:
            raise ValueError(f"Unsupported visual type for {source_id}: {row['visual_type']}")
        input_headers = split_cells(row["input_headers_zh"])
        input_values = split_cells(row["input_row_zh"])
        if len(input_headers) < 2 or len(input_headers) != len(input_values):
            raise ValueError(f"Input example has mismatched columns for {source_id}")
        output_headers = split_cells(row["output_headers_zh"])
        output_rows = [split_cells(item) for item in row["output_rows_zh"].split("；")]
        if len(output_headers) < 2 or len(output_rows) < 2:
            raise ValueError(f"Output example is too small for {source_id}")
        if any(len(item) != len(output_headers) for item in output_rows):
            raise ValueError(f"Output example has mismatched columns for {source_id}")
        parse_plot_contract(row, len(output_rows))
        validate_plot_source_contract(row, output_headers, output_rows)
    return rows


def read_advanced_titles() -> dict[str, str]:
    with COVERAGE_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    titles = {row["source_id"]: row["source_title"] for row in rows}
    titles.update(PROFESSIONAL_ANALYSIS_TITLE_OVERRIDES)
    if list(titles) != EXPECTED_IDS:
        raise ValueError("Coverage source IDs no longer match the frozen 58-item order")
    return titles


def render_table(headers: list[str], rows: list[list[str]], class_name: str) -> str:
    head = "".join(f'<th scope="col">{html.escape(item)}</th>' for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(item)}</td>" for item in row) + "</tr>" for row in rows
    )
    return (
        f'<div class="analysis-table-scroll" tabindex="0"><table class="{class_name}">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def svg_text(x: int, y: int, value: str, class_name: str) -> str:
    escaped = html.escape(value)
    fit = ' textLength="505" lengthAdjust="spacingAndGlyphs"' if len(value) > 34 else ""
    return f'<text x="{x}" y="{y}" class="{class_name}"{fit}>{escaped}</text>'


def micro_svg(example: dict[str, str]) -> str:
    source_slug = example["source_id"].replace(".", "-")
    visual_type = example["visual_type"]
    headers = split_cells(example["output_headers_zh"])
    rows = [split_cells(item) for item in example["output_rows_zh"].split("；")]
    height = 94 + 78 * len(rows)
    values, color_tokens = parse_plot_contract(example, len(rows))
    max_abs = max((abs(item) for item in values), default=1) or 1
    non_grey_values = [
        abs(value) for value, token in zip(values, color_tokens, strict=True) if token != "grey"
    ]
    min_continuous = min(non_grey_values, default=0)
    max_continuous = max(non_grey_values, default=1)

    def magnitude(index: int, low: int = 24, high: int = 128) -> int:
        return round(low + (high - low) * abs(values[index]) / max_abs)

    def matrix_opacity(index: int) -> float:
        if color_tokens[index] == "grey":
            return 0.24
        span = max_continuous - min_continuous
        proportion = 1 if span == 0 else (abs(values[index]) - min_continuous) / span
        return 0.22 + 0.62 * proportion

    parts: list[str] = []
    header_line = "结果列：" + "｜".join(headers)
    parts.append(svg_text(22, 27, header_line, "micro-column-label"))
    for index, row in enumerate(rows):
        y = 60 + 78 * index
        label = " · ".join(row[:2])
        detail = " ｜ ".join(
            f"{headers[cell_index]}：{cell}" for cell_index, cell in enumerate(row[2:], start=2)
        )
        row_class = PLOT_COLOR_CLASSES[color_tokens[index]]
        row_title = html.escape("｜".join(row))
        parts.append(
            f'<g class="micro-data-row" data-row="{index + 1}" '
            f'data-plot-value="{format_plot_value(values[index])}" '
            f'data-plot-color="{color_tokens[index]}">'
            f"<title>{row_title}</title>"
        )
        if visual_type == "tree":
            endpoint = 20 + magnitude(index)
            parts.append(f'<path d="M20 39V{y}H{endpoint}" class="v-link"/>')
            parts.append(f'<circle cx="{endpoint}" cy="{y}" r="8" class="{row_class}"/>')
        elif visual_type == "paired":
            endpoint = 32 + magnitude(index)
            parts.append(f'<path d="M28 {y}H{endpoint}" class="v-link"/>')
            parts.append(
                f'<rect x="{endpoint - 18}" y="{y - 18}" width="36" height="36" rx="6" class="{row_class}"/>'
            )
        elif visual_type == "sequence":
            parts.append(
                f'<rect x="22" y="{y - 19}" width="{magnitude(index)}" height="39" rx="5" class="{row_class}"/>'
            )
        elif visual_type == "chromosome":
            position = 22 + round(126 * abs(values[index]) / max_abs)
            parts.append(f'<path d="M22 {y}H148" class="v-chrom"/>')
            parts.append(f'<circle cx="{position}" cy="{y}" r="8" class="{row_class}"/>')
        elif visual_type == "links":
            endpoint = 32 + magnitude(index)
            parts.append(
                f'<path d="M32 {y - 20}V{y + 20}M{endpoint} {y - 20}V{y + 20}" class="v-chrom"/>'
            )
            parts.append(
                f'<path d="M32 {y - 6}C68 {y - 6} 90 {y + 6} {endpoint} {y + 6}" class="v-link"/>'
            )
        elif visual_type in {"matrix", "expression"}:
            parts.append(
                f'<rect x="18" y="{y - 25}" width="712" height="52" rx="8" '
                f'class="{row_class}" opacity="{matrix_opacity(index):.2f}"/>'
            )
        elif visual_type in {"scatter", "de"}:
            x = 84 + round(62 * values[index] / max_abs)
            parts.append(f'<path d="M22 {y + 25}H148" class="v-reference"/>')
            parts.append(f'<circle cx="{x}" cy="{y}" r="10" class="{row_class}"/>')
        elif visual_type == "curve":
            x = 72 + index * 125
            point_y = y - round(30 * abs(values[index]) / max_abs)
            if index:
                previous_x = 72 + (index - 1) * 125
                previous_y = (60 + 78 * (index - 1)) - round(30 * abs(values[index - 1]) / max_abs)
                parts.append(
                    f'<path d="M{previous_x} {previous_y}L{x} {point_y}" class="v-curve"/>'
                )
            parts.append(f'<circle cx="{x}" cy="{point_y}" r="8" class="{row_class}"/>')
        elif visual_type == "decision":
            parts.append(
                f'<rect x="18" y="{y - 24}" width="{magnitude(index)}" height="50" rx="8" class="{row_class}"/>'
            )
        else:
            width = magnitude(index)
            start = 84 if values[index] >= 0 else 84 - width
            parts.append(
                f'<rect x="{start}" y="{y - 20}" width="{width}" height="39" rx="6" class="{row_class}" opacity=".36"/>'
            )
            parts.append(f'<path d="M22 {y + 23}H148" class="v-reference"/>')
            endpoint = start + width if values[index] >= 0 else start
            parts.append(f'<circle cx="{endpoint}" cy="{y}" r="9" class="{row_class}"/>')
        text_x = 170 if visual_type not in {"matrix", "expression"} else 36
        parts.append(svg_text(text_x, y - 5, label, "micro-row-label"))
        parts.append(svg_text(text_x, y + 15, detail, "micro-row-value"))
        contract_text = (
            f"{example['plot_value_label_zh']}：{format_plot_value(values[index])}；"
            f"颜色：{PLOT_COLOR_LABELS[color_tokens[index]]}"
        )
        parts.append(svg_text(text_x, y + 34, contract_text, "micro-plot-contract"))
        parts.append("</g>")

    title = html.escape(example["visual_title_zh"])
    description = html.escape(
        f"横向说明：{example['x_axis_zh']}。纵向说明：{example['y_axis_zh']}。"
        f"颜色和符号：{example['legend_zh']}。显式绘图值：{example['plot_value_label_zh']}。"
        f"绘图值来自结果列：{plot_source_display(example['plot_value_source_column_zh'])}。"
        f"颜色来自：{plot_source_display(example['plot_color_source_column_zh'])}。"
        "逐行颜色：" + "、".join(PLOT_COLOR_LABELS[item] for item in color_tokens) + "。"
    )
    return (
        f'<svg class="analysis-micro-figure" viewBox="0 0 760 {height}" role="img" '
        f'data-source-id="{html.escape(example["source_id"])}" data-result-rows="{len(rows)}" '
        f'aria-labelledby="micro-title-{source_slug} micro-desc-{source_slug}">'
        f'<title id="micro-title-{source_slug}">{title}</title>'
        f'<desc id="micro-desc-{source_slug}">{description}</desc>'
        f'<g class="analysis-micro-shapes">{"".join(parts)}</g></svg>'
    )


def micro_lesson(example: dict[str, str]) -> str:
    value = {key: html.escape(example[key], quote=True) for key in EXAMPLE_FIELDS}
    input_table = render_table(
        split_cells(example["input_headers_zh"]),
        [split_cells(example["input_row_zh"])],
        "analysis-input-table",
    )
    output_table = render_table(
        split_cells(example["output_headers_zh"]),
        [split_cells(item) for item in example["output_rows_zh"].split("；")],
        "analysis-example-table",
    )
    return (
        '<div class="analysis-micro-lesson">'
        '<div class="analysis-foundation-grid">'
        f"<div><h4>先懂一个概念</h4><p>{value['concept_zh']}</p></div>"
        f'<div><h4 class="analysis-why-title">为什么要做</h4><p>{value["why_zh"]}</p></div></div>'
        "<h4>看一条具体输入记录</h4>"
        f"{input_table}"
        f'<p class="analysis-operation"><strong>本项怎样处理：</strong>{value["operation_zh"]}</p>'
        '<div class="analysis-result-grid"><figure>'
        f"{micro_svg(example)}"
        "<figcaption><b>横向说明：</b>"
        f"{value['x_axis_zh']}<br><b>纵向说明：</b>{value['y_axis_zh']}"
        f"<br><b>图中颜色与符号：</b>{value['legend_zh']}"
        f"<br><b>本图显式数值：</b>{value['plot_value_label_zh']}（按结果表行顺序）"
        f"<br><b>绘图值来自：</b>{plot_source_display(example['plot_value_source_column_zh'])}"
        f"<br><b>颜色来自：</b>{plot_source_display(example['plot_color_source_column_zh'])}"
        "<br><b>逐行颜色：</b>"
        + "、".join(PLOT_COLOR_LABELS[item] for item in split_cells(example["plot_colors"]))
        + "</figcaption></figure>"
        "<div><h4>用结果小表核对图</h4>"
        f"{output_table}</div></div>"
        f'<details class="analysis-reading-check"><summary>先试着回答：{value["reading_question_zh"]}</summary>'
        f"<p><strong>参考答案：</strong>{value['reading_answer_zh']}</p></details>"
        '<div class="analysis-verdict-grid">'
        f'<div class="analysis-normal"><h4>看到什么算正常</h4><p>{value["normal_zh"]}</p></div>'
        f'<div class="analysis-stop"><h4>什么情况先暂停</h4><p>{value["stop_zh"]}</p></div></div>'
        f'<p class="analysis-next"><strong>这项完成后：</strong>{value["next_zh"]}</p>'
        '<p class="analysis-teaching-note">本页数值只用于练习读图，不代表真实水稻分析结果。</p>'
        "</div>"
    )


def beginner_guide(row: dict[str, str], example: dict[str, str]) -> str:
    value = {key: html.escape(row[key], quote=True) for key in FIELDS}
    condition = html.escape(
        CONDITIONAL_BEGINNER_CONDITIONS.get(row["source_id"], DEFAULT_BEGINNER_CONDITION),
        quote=True,
    )
    location = ""
    if row["source_id"] in CHAPTER_TEN_ITEM_CONTEXT:
        group_index, group_label = CHAPTER_TEN_ITEM_CONTEXT[row["source_id"]]
        item_index = int(row["source_id"].split(".", 1)[1])
        location = (
            '<p class="beginner-item-location">'
            f"第 10 章 · 第 {group_index} 组 / 4：{html.escape(group_label)}"
            f" · 第 {item_index} / 15 项</p>"
        )
    return (
        f'\n<section class="beginner-guide" aria-label="{value["source_id"]} 零基础说明">'
        f"{location}"
        "<h4>这一项要回答什么？</h4>"
        f"<p>{value['beginner_question_zh']}</p>"
        '<div class="beginner-guide-grid">'
        "<div><h5>需要准备</h5>"
        f"<p>{value['beginner_input_zh']}</p></div>"
        "<div><h5>会得到什么</h5>"
        f"<p>{value['beginner_output_zh']}</p></div>"
        "<div><h5>按什么顺序看</h5>"
        f"<p>{value['beginner_read_zh']}</p></div>"
        "</div>"
        f"{micro_lesson(example)}"
        '<p class="beginner-warning"><strong>不要这样理解：</strong>'
        f"{value['beginner_warning_zh']}</p>"
        '<p class="beginner-condition"><strong>继续前先确认：</strong>'
        f"{condition}</p>"
        "</section>"
    )


def beginner_analysis_nav(source_id: str, rows: dict[str, dict[str, str]]) -> str:
    chapter = source_id.split(".", 1)[0]
    chapter_ids = [item for item in EXPECTED_IDS if item.split(".", 1)[0] == chapter]
    index = chapter_ids.index(source_id)
    links = [f'<a href="#chapter-{chapter}">返回本章路线</a>']
    if index > 0:
        previous_id = chapter_ids[index - 1]
        links.append(
            f'<a rel="prev" href="#analysis-{previous_id.replace(".", "-")}">'
            f"上一项：{html.escape(rows[previous_id]['beginner_title_zh'])}</a>"
        )
    if index + 1 < len(chapter_ids):
        next_id = chapter_ids[index + 1]
        links.append(
            f'<a rel="next" href="#analysis-{next_id.replace(".", "-")}">'
            f"下一项：{html.escape(rows[next_id]['beginner_title_zh'])}</a>"
        )
    else:
        links.append('<a href="#chapter-map">本章完成：返回分析思维导图</a>')
    return (
        '<nav class="beginner-analysis-nav beginner-only" aria-label="本项学习导航">'
        + "".join(links)
        + "</nav>"
    )


def replace_card(
    match: re.Match[str],
    rows: dict[str, dict[str, str]],
    examples: dict[str, dict[str, str]],
    advanced_titles: dict[str, str],
) -> str:
    card = match.group(0)
    source_match = re.search(r'data-source-id="([0-9.]+)"', card)
    if source_match is None:
        raise ValueError("Analysis card without data-source-id")
    source_id = source_match.group(1)
    row = rows[source_id]
    beginner_title = html.escape(row["beginner_title_zh"], quote=True)
    advanced_title = html.escape(advanced_titles[source_id], quote=True)
    card = re.sub(
        r'\n?<section class="beginner-guide".*?</section>',
        "",
        card,
        count=1,
        flags=re.DOTALL,
    )
    card = re.sub(
        r'\n?<nav class="beginner-analysis-nav beginner-only".*?</nav>',
        "",
        card,
        count=1,
        flags=re.DOTALL,
    )
    card, count = re.subn(
        r'(<header class="analysis-head">.*?<h3>).*?(</h3>)',
        rf'\1<span class="advanced-title">{advanced_title}</span>'
        rf'<span class="beginner-title">{beginner_title}</span>\2',
        card,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError(f"Could not replace title for {source_id}")
    card, count = re.subn(
        r"(</header>)",
        rf"\1{beginner_guide(row, examples[source_id])}",
        card,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Could not insert beginner guide for {source_id}")
    card, count = re.subn(
        r'(<a class="back-to-chapter")',
        beginner_analysis_nav(source_id, rows) + r"\n\1",
        card,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Could not insert beginner navigation for {source_id}")
    return card


def render(source: str) -> str:
    row_list = read_tsv(CONTRACT_PATH)
    rows = {row["source_id"]: row for row in row_list}
    example_list = read_examples()
    examples = {row["source_id"]: row for row in example_list}
    advanced_titles = read_advanced_titles()
    rendered, count = re.subn(
        r'<article class="analysis-card".*?</article>',
        lambda match: replace_card(match, rows, examples, advanced_titles),
        source,
        flags=re.DOTALL,
    )
    if count != len(EXPECTED_IDS):
        raise ValueError(f"Expected 58 analysis cards, found {count}")

    quick_nav_replacements = 0

    def replace_quick_nav(match: re.Match[str]) -> str:
        nonlocal quick_nav_replacements
        nav = match.group(0)
        for source_id in EXPECTED_IDS:
            beginner = html.escape(rows[source_id]["beginner_title_zh"], quote=True)
            advanced = html.escape(advanced_titles[source_id], quote=True)
            pattern = rf'<a href="#analysis-{re.escape(source_id.replace(".", "-"))}">.*?</a>'
            replacement = (
                f'<a href="#analysis-{source_id.replace(".", "-")}">'
                f'<span class="advanced-title">{source_id} {advanced}</span>'
                f'<span class="beginner-title">{beginner}</span></a>'
            )
            nav, link_count = re.subn(pattern, replacement, nav, count=1, flags=re.DOTALL)
            quick_nav_replacements += link_count
        return nav

    rendered = re.sub(
        r'<nav class="chapter-quick-nav".*?</nav>',
        replace_quick_nav,
        rendered,
        flags=re.DOTALL,
    )
    if quick_nav_replacements != len(EXPECTED_IDS):
        raise ValueError(f"Expected 58 quick-navigation labels, replaced {quick_nav_replacements}")

    for chapter, beginner in CHAPTER_BEGINNER_TITLES.items():
        pattern = rf'(<h2 id="chapter-{chapter}-title">)(.*?)(</h2>)'
        current = re.search(pattern, rendered, flags=re.DOTALL)
        if current is None:
            raise ValueError(f"Missing chapter title {chapter}")
        current_inner = current.group(2)
        advanced_match = re.search(r'<span class="advanced-title">(.*?)</span>', current_inner)
        if advanced_match is not None:
            advanced = advanced_match.group(1)
        else:
            advanced = re.sub(r"<[^>]+>", "", current_inner)
        replacement = (
            rf'\1<span class="advanced-title">{advanced}</span>'
            rf'<span class="beginner-title">{html.escape(beginner)}</span>\3'
        )
        rendered = re.sub(pattern, replacement, rendered, count=1, flags=re.DOTALL)
    return re.sub(r"^[ \t]+$", "", rendered, flags=re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    source = HTML_PATH.read_text(encoding="utf-8")
    rendered = render(source)
    if arguments.check:
        if rendered != source:
            raise SystemExit("docs/index.html is not synchronized with beginner-language TSV")
        return
    HTML_PATH.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
