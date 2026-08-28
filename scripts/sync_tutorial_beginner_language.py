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
ADVANCED_TITLE_OVERRIDES = {
    "6.1": "物种系统树与正交组有无聚类（两类对象分开）",
    "6.2": "正交组成员与占有明细",
    "6.3": "正交组质量综合评估",
    "6.4": "目标家族占有类型双分母分布",
    "9.1": "正交组内成对 Ka/Ks 分析",
    "9.2": "物种间正交组配对 Ka/Ks 分析",
    "10.12": "正交组层面的启动子分布",
    "11.3": "差异表达基因跨条件重叠分析（全条件汇总）",
    "11.4": "非生物胁迫响应",
    "11.5": "生物胁迫响应",
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
    return rows


def read_advanced_titles() -> dict[str, str]:
    with COVERAGE_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    titles = {row["source_id"]: row["source_title"] for row in rows}
    titles.update(ADVANCED_TITLE_OVERRIDES)
    if list(titles) != EXPECTED_IDS:
        raise ValueError("Coverage source IDs no longer match the frozen 58-item order")
    return titles


def render_table(headers: list[str], rows: list[list[str]], class_name: str) -> str:
    head = "".join(f"<th scope=\"col\">{html.escape(item)}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(item)}</td>" for item in row) + "</tr>"
        for row in rows
    )
    return (
        f'<div class="analysis-table-scroll" tabindex="0"><table class="{class_name}">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


CHINESE_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def chinese_number(value: str) -> float | None:
    """Read the first plain-Chinese number so teaching geometry follows its table."""
    percentage = re.search(r"百分之(负?[零一二两三四五六七八九十百千万点]+)", value)
    if percentage:
        token = percentage.group(1)
    else:
        matches = re.findall(r"负?[零一二两三四五六七八九十百千万点]+", value)
        if not matches:
            return None
        token = matches[0]
    negative = token.startswith("负")
    token = token.removeprefix("负")
    if "点" in token:
        integer, decimal = token.split("点", 1)
        integer_value = chinese_number(integer) if integer else 0
        if integer_value is None or any(item not in CHINESE_DIGITS for item in decimal):
            return None
        fraction = float("0." + "".join(str(CHINESE_DIGITS[item]) for item in decimal))
        result = integer_value + fraction
        return -result if negative else result
    total = 0
    current = 0
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    if all(item in CHINESE_DIGITS for item in token):
        result = float("".join(str(CHINESE_DIGITS[item]) for item in token))
        return -result if negative else result
    for item in token:
        if item in CHINESE_DIGITS:
            current = CHINESE_DIGITS[item]
        elif item in units:
            total += (current or 1) * units[item]
            current = 0
        else:
            return None
    result = float(total + current)
    return -result if negative else result


def svg_text(x: int, y: int, value: str, class_name: str) -> str:
    escaped = html.escape(value)
    fit = ' textLength="505" lengthAdjust="spacingAndGlyphs"' if len(value) > 34 else ""
    return f'<text x="{x}" y="{y}" class="{class_name}"{fit}>{escaped}</text>'


def row_value(headers: list[str], row: list[str], visual_type: str) -> float | None:
    preferred_headers = {
        "bars": ("比例",),
        "sequence": ("一致比例",),
        "de": ("效应方向与大小",),
        "test": ("效应方向与大小",),
        "multi_indicator": ("中间比值", "中间基准变化率"),
    }.get(visual_type, ())
    for preferred in preferred_headers:
        for index, header in enumerate(headers):
            if preferred in header:
                number = chinese_number(row[index])
                if number is not None:
                    return number
    for cell in reversed(row):
        number = chinese_number(cell)
        if number is not None:
            return number
    return None


def micro_svg(example: dict[str, str]) -> str:
    source_slug = example["source_id"].replace(".", "-")
    visual_type = example["visual_type"]
    headers = split_cells(example["output_headers_zh"])
    rows = [split_cells(item) for item in example["output_rows_zh"].split("；")]
    height = 78 + 64 * len(rows)
    values = [row_value(headers, row, visual_type) for row in rows]

    def magnitude(index: int) -> int:
        value = values[index]
        if value is None:
            return 260
        return round(130 + min(320, 75 * math.log10(abs(value) + 1)))

    def color(index: int, row: list[str]) -> str:
        combined = "".join(row)
        if (
            "不允许" in combined
            or "只描述" in combined
            or "暂不" in combined
            or "待定" in combined
            or "不能" in combined
            or "未检出" in combined
        ):
            return "v-low"
        if "排除" in combined or "暂停" in combined:
            return "v-bad"
        if "复核" in combined:
            return "v-warn"
        if "保留" in combined or "通过" in combined or "可以解释" in combined:
            return "v-good"
        if "上升" in combined:
            return "v-bad"
        if "下降" in combined:
            return "v-mid"
        return ("v-mid", "v-good", "v-warn")[index % 3]

    parts: list[str] = []
    header_line = "结果列：" + "｜".join(headers)
    parts.append(svg_text(22, 27, header_line, "micro-column-label"))
    if visual_type == "stacked":
        height = 82 + 92 * len(rows)
        cell_width = 125
        for index, row in enumerate(rows):
            y = 55 + 92 * index
            row_title = html.escape("｜".join(row))
            parts.append(
                f'<g class="micro-data-row" data-row="{index + 1}"><title>{row_title}</title>'
            )
            parts.append(svg_text(22, y, row[0], "micro-row-label"))
            for cell_index, cell in enumerate(row[1:]):
                x = 22 + cell_index * cell_width
                parts.append(
                    f'<rect x="{x}" y="{y + 12}" width="116" height="42" rx="7" '
                    f'class="{("v-mid", "v-good", "v-warn", "v-bad")[cell_index % 4]}"/>'
                )
                parts.append(svg_text(x + 6, y + 29, headers[cell_index + 1], "micro-cell-label"))
                parts.append(svg_text(x + 6, y + 47, cell, "micro-cell-value"))
            parts.append("</g>")
    else:
        for index, row in enumerate(rows):
            y = 58 + 64 * index
            label = " · ".join(row[:2])
            detail = " ｜ ".join(
                f"{headers[cell_index]}：{cell}"
                for cell_index, cell in enumerate(row[2:], start=2)
            )
            row_class = color(index, row)
            row_title = html.escape("｜".join(row))
            data_value = "" if values[index] is None else f' data-value="{values[index]:g}"'
            parts.append(
                f'<g class="micro-data-row" data-row="{index + 1}"{data_value}>'
                f"<title>{row_title}</title>"
            )
            if visual_type == "tree":
                parts.append(f'<path d="M28 45V{y}H118" class="v-link"/>')
                parts.append(f'<circle cx="118" cy="{y}" r="8" class="{row_class}"/>')
            elif visual_type == "paired":
                parts.append(f'<path d="M28 45V{y}H92" class="v-link"/>')
                parts.append(f'<rect x="102" y="{y - 18}" width="44" height="38" rx="6" class="{row_class}"/>')
            elif visual_type == "sequence":
                parts.append(f'<rect x="22" y="{y - 19}" width="126" height="39" rx="5" class="{row_class}"/>')
            elif visual_type == "chromosome":
                parts.append(f'<path d="M72 {y - 25}V{y + 25}" class="v-chrom"/>')
                parts.append(f'<circle cx="72" cy="{y}" r="8" class="{row_class}"/>')
            elif visual_type == "links":
                parts.append(f'<path d="M32 {y - 20}V{y + 20}M126 {y - 20}V{y + 20}" class="v-chrom"/>')
                parts.append(f'<path d="M32 {y - 6}C68 {y - 6} 90 {y + 6} 126 {y + 6}" class="v-link"/>')
            elif visual_type in {"matrix", "expression"}:
                parts.append(
                    f'<rect x="18" y="{y - 25}" width="712" height="52" rx="8" '
                    f'class="{row_class}" opacity=".22"/>'
                )
            elif visual_type in {"scatter", "de"}:
                x = 58 + magnitude(index)
                parts.append(f'<path d="M30 {y + 25}H520" class="v-reference"/>')
                parts.append(f'<circle cx="{x}" cy="{y}" r="10" class="{row_class}"/>')
            elif visual_type == "curve":
                x = 72 + index * 125
                point_y = y - round(magnitude(index) / 8)
                if index:
                    previous_x = 72 + (index - 1) * 125
                    previous_y = (58 + 64 * (index - 1)) - round(magnitude(index - 1) / 8)
                    parts.append(f'<path d="M{previous_x} {previous_y}L{x} {point_y}" class="v-curve"/>')
                parts.append(f'<circle cx="{x}" cy="{point_y}" r="8" class="{row_class}"/>')
            elif visual_type == "decision":
                parts.append(f'<rect x="18" y="{y - 24}" width="138" height="50" rx="8" class="{row_class}"/>')
            else:
                width = magnitude(index)
                parts.append(f'<rect x="18" y="{y - 20}" width="{width}" height="39" rx="6" class="{row_class}" opacity=".28"/>')
                parts.append(
                    f'<path d="M18 {y + 23}H{18 + width}" class="v-reference"/>'
                )
                parts.append(f'<circle cx="{18 + width}" cy="{y}" r="9" class="{row_class}"/>')
            text_x = 170 if visual_type not in {"matrix", "expression"} else 36
            parts.append(svg_text(text_x, y - 5, label, "micro-row-label"))
            parts.append(svg_text(text_x, y + 15, detail, "micro-row-value"))
            parts.append("</g>")

    title = html.escape(example["visual_title_zh"])
    description = html.escape(
        f"横向说明：{example['x_axis_zh']}。纵向说明：{example['y_axis_zh']}。"
        f"颜色和符号：{example['legend_zh']}。"
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
        f'<div><h4>先懂一个概念</h4><p>{value["concept_zh"]}</p></div>'
        f'<div><h4 class="analysis-why-title">为什么要做</h4><p>{value["why_zh"]}</p></div></div>'
        '<h4>看一条具体输入记录</h4>'
        f"{input_table}"
        f'<p class="analysis-operation"><strong>本项怎样处理：</strong>{value["operation_zh"]}</p>'
        '<div class="analysis-result-grid"><figure>'
        f"{micro_svg(example)}"
        '<figcaption><b>横向说明：</b>'
        f'{value["x_axis_zh"]}<br><b>纵向说明：</b>{value["y_axis_zh"]}'
        f'<br><b>图中颜色与符号：</b>{value["legend_zh"]}</figcaption></figure>'
        '<div><h4>用结果小表核对图</h4>'
        f"{output_table}</div></div>"
        f'<details class="analysis-reading-check"><summary>先试着回答：{value["reading_question_zh"]}</summary>'
        f'<p><strong>参考答案：</strong>{value["reading_answer_zh"]}</p></details>'
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
        rf'\1<span class="beginner-title">{beginner_title}</span>'
        rf'<span class="advanced-title">{advanced_title}</span>\2',
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
                f'<span class="beginner-title">{source_id} {beginner}</span>'
                f'<span class="advanced-title">{source_id} {advanced}</span></a>'
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
            rf'\1<span class="beginner-title">{html.escape(beginner)}</span>'
            rf'<span class="advanced-title">{advanced}</span>\3'
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
