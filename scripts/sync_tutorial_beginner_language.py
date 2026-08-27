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
    "10": "寻找基因上游可能的调控信号",
    "11": "比较基因在不同样本中的活跃程度",
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
DEFAULT_BEGINNER_CONDITION = "输入、对应关系和质量检查都通过；否则先修复问题，再继续。"
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
    return (
        f'\n<section class="beginner-guide" aria-label="{value["source_id"]} 零基础说明">'
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
        '<p class="beginner-warning"><strong>不要这样理解：</strong>'
        f"{value['beginner_warning_zh']}</p>"
        '<p class="beginner-condition"><strong>继续前先确认：</strong>'
        f"{condition}</p>"
        "</section>"
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

    for source_id in EXPECTED_IDS:
        beginner = html.escape(rows[source_id]["beginner_title_zh"], quote=True)
        advanced = html.escape(advanced_titles[source_id], quote=True)
        pattern = rf'<a href="#analysis-{re.escape(source_id.replace(".", "-"))}">.*?</a>'
        replacement = (
            f'<a href="#analysis-{source_id.replace(".", "-")}">'
            f'<span class="beginner-title">{source_id} {beginner}</span>'
            f'<span class="advanced-title">{source_id} {advanced}</span></a>'
        )
        rendered, link_count = re.subn(pattern, replacement, rendered, flags=re.DOTALL)
        if link_count < 1:
            raise ValueError(f"Could not replace quick-navigation label for {source_id}")

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
    return rendered


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
