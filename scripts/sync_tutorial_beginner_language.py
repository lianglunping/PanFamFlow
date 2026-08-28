#!/usr/bin/env python3
"""Synchronize the 58-row beginner-language contract into the static tutorial."""

# Chinese tutorial strings intentionally use full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import csv
import html
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


def micro_svg(example: dict[str, str]) -> str:
    source_slug = example["source_id"].replace(".", "-")
    visual_type = example["visual_type"]
    shapes = {
        "decision": '<rect x="24" y="62" width="112" height="54" rx="9" class="v-mid"/><path d="M136 89H194"/><path d="m184 80 12 9-12 9"/><rect x="202" y="28" width="126" height="44" rx="9" class="v-good"/><rect x="202" y="82" width="126" height="44" rx="9" class="v-warn"/><rect x="202" y="136" width="126" height="44" rx="9" class="v-bad"/>',
        "tree": '<path d="M45 105H115M115 42V168M115 62H205M115 148H205M205 28V92M205 118V174M205 45H326M205 78H326M205 130H326M205 164H326"/><circle cx="326" cy="45" r="8" class="v-good"/><circle cx="326" cy="78" r="8" class="v-good"/><circle cx="326" cy="130" r="8" class="v-warn"/><circle cx="326" cy="164" r="8" class="v-warn"/>',
        "matrix": '<g class="v-grid"><rect x="75" y="38" width="66" height="40" class="v-low"/><rect x="145" y="38" width="66" height="40" class="v-mid"/><rect x="215" y="38" width="66" height="40" class="v-good"/><rect x="75" y="82" width="66" height="40" class="v-good"/><rect x="145" y="82" width="66" height="40" class="v-low"/><rect x="215" y="82" width="66" height="40" class="v-mid"/><rect x="75" y="126" width="66" height="40" class="v-mid"/><rect x="145" y="126" width="66" height="40" class="v-good"/><rect x="215" y="126" width="66" height="40" class="v-low"/></g>',
        "sequence": '<rect x="32" y="72" width="42" height="54" class="v-mid"/><rect x="79" y="52" width="42" height="74" class="v-good"/><rect x="126" y="84" width="42" height="42" class="v-warn"/><rect x="173" y="40" width="42" height="86" class="v-good"/><rect x="220" y="66" width="42" height="60" class="v-mid"/><rect x="267" y="92" width="42" height="34" class="v-low"/><path d="M25 135H326"/>',
        "distribution": '<path d="M36 174V24M36 174H330"/><path d="M92 52V145M70 91H114M70 110H114"/><circle cx="83" cy="75" r="7" class="v-good"/><circle cx="101" cy="132" r="7" class="v-mid"/><path d="M210 40V158M188 74H232M188 112H232"/><circle cx="197" cy="57" r="7" class="v-warn"/><circle cx="222" cy="140" r="7" class="v-mid"/>',
        "comparison": '<path d="M36 174V24M36 174H330"/><rect x="78" y="86" width="70" height="88" class="v-mid"/><rect x="206" y="48" width="70" height="126" class="v-good"/><path d="M78 72H276M78 64V80M276 64V80"/>',
        "curve": '<path d="M36 174V24M36 174H330"/><path d="M46 146C86 104 116 79 154 63S233 42 320 36" class="v-curve"/><path d="M46 155C84 127 120 109 154 100S233 89 320 85" class="v-curve-alt"/><circle cx="154" cy="63" r="6" class="v-good"/><circle cx="320" cy="36" r="6" class="v-good"/>',
        "chromosome": '<path d="M82 38V170M178 38V170M274 38V170" class="v-chrom"/><circle cx="82" cy="76" r="9" class="v-good"/><circle cx="82" cy="96" r="9" class="v-warn"/><circle cx="178" cy="135" r="9" class="v-good"/><circle cx="274" cy="58" r="9" class="v-mid"/>',
        "links": '<path d="M68 34V174M286 34V174" class="v-chrom"/><path d="M68 58C140 58 210 70 286 76M68 89C140 89 210 108 286 112M68 126C140 126 210 137 286 145" class="v-link"/><circle cx="68" cy="89" r="10" class="v-warn"/><circle cx="286" cy="112" r="10" class="v-warn"/>',
        "scatter": '<path d="M36 174V24M36 174H330M46 158L316 40" class="v-reference"/><circle cx="82" cy="132" r="8" class="v-mid"/><circle cx="132" cy="123" r="8" class="v-good"/><circle cx="186" cy="91" r="8" class="v-warn"/><circle cx="248" cy="74" r="8" class="v-good"/><circle cx="290" cy="52" r="8" class="v-bad"/>',
        "bars": '<path d="M36 174V24M36 174H330"/><rect x="64" y="88" width="54" height="86" class="v-mid"/><rect x="148" y="48" width="54" height="126" class="v-good"/><rect x="232" y="112" width="54" height="62" class="v-warn"/>',
        "expression": '<g class="v-grid"><rect x="74" y="38" width="58" height="38" class="v-good"/><rect x="136" y="38" width="58" height="38" class="v-good"/><rect x="198" y="38" width="58" height="38" class="v-low"/><rect x="74" y="80" width="58" height="38" class="v-low"/><rect x="136" y="80" width="58" height="38" class="v-mid"/><rect x="198" y="80" width="58" height="38" class="v-good"/><rect x="74" y="122" width="58" height="38" class="v-mid"/><rect x="136" y="122" width="58" height="38" class="v-low"/><rect x="198" y="122" width="58" height="38" class="v-mid"/></g>',
    }
    title = html.escape(example["visual_title_zh"])
    description = html.escape(
        f"横向说明：{example['x_axis_zh']}。纵向说明：{example['y_axis_zh']}。"
        f"颜色和符号：{example['legend_zh']}。"
    )
    return (
        f'<svg class="analysis-micro-figure" viewBox="0 0 360 205" role="img" '
        f'aria-labelledby="micro-title-{source_slug} micro-desc-{source_slug}">'
        f'<title id="micro-title-{source_slug}">{title}</title>'
        f'<desc id="micro-desc-{source_slug}">{description}</desc>'
        f'<g class="analysis-micro-shapes">{shapes[visual_type]}</g></svg>'
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
