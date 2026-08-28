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


def read_advanced_titles() -> dict[str, str]:
    with COVERAGE_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    titles = {row["source_id"]: row["source_title"] for row in rows}
    titles.update(ADVANCED_TITLE_OVERRIDES)
    if list(titles) != EXPECTED_IDS:
        raise ValueError("Coverage source IDs no longer match the frozen 58-item order")
    return titles


def beginner_guide(row: dict[str, str]) -> str:
    value = {key: html.escape(row[key], quote=True) for key in FIELDS}
    condition = html.escape(
        CONDITIONAL_BEGINNER_CONDITIONS.get(row["source_id"], DEFAULT_BEGINNER_CONDITION),
        quote=True,
    )
    chapter = row["source_id"].split(".", 1)[0]
    action = html.escape(
        ITEM_ACTION_OVERRIDES.get(row["source_id"], CHAPTER_ACTIONS[chapter]), quote=True
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
        '<div class="beginner-bridge"><span><strong>一条输入记录</strong>'
        f'{value["beginner_input_zh"]}</span><b aria-hidden="true">→</b>'
        f'<span><strong>本项怎样处理</strong>{action}</span><b aria-hidden="true">→</b>'
        f"<span><strong>在结果中看到</strong>{value['beginner_output_zh']}</span></div>"
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
        rf"\1{beginner_guide(row)}",
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
    advanced_titles = read_advanced_titles()
    rendered, count = re.subn(
        r'<article class="analysis-card".*?</article>',
        lambda match: replace_card(match, rows, advanced_titles),
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
