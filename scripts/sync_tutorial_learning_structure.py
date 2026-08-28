#!/usr/bin/env python3
"""Synchronize the beginner mind map and eight chapter lessons into the tutorial."""

# Chinese tutorial strings intentionally use full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import csv
import html
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LESSONS_PATH = ROOT / "docs" / "TUTORIAL_CHAPTER_LESSONS.tsv"
LANGUAGE_PATH = ROOT / "docs" / "TUTORIAL_BEGINNER_LANGUAGE.tsv"
HTML_PATH = ROOT / "docs" / "index.html"

LESSON_FIELDS = (
    "chapter",
    "stage_id",
    "chapter_title_zh",
    "analysis_count",
    "question_zh",
    "foundation_zh",
    "why_zh",
    "input_zh",
    "method_zh",
    "output_zh",
    "read_zh",
    "boundary_zh",
    "diagram_type",
    "output_label_zh",
    "dependency_zh",
)
EXPECTED_COUNTS = {"4": 4, "5": 6, "6": 8, "7": 3, "8": 6, "9": 9, "10": 15, "11": 7}
STAGES = {
    "1": ("先确定对象", "先建立一份可信成员名单，后面所有分析才有共同起点。"),
    "2": ("再描述差异", "依次看内部结构、材料中的有无和染色体位置。"),
    "3": ("再解释来源与变化", "结合复制关系、编码变化和基因前方线索提出候选解释。"),
    "4": ("最后连接实际条件", "把家族成员放入组织和处理条件中，寻找可验证的活跃模式。"),
}

DIAGRAMS = {
    "member_funnel": """
      <div class="diagram-flow"><span>全部相似候选</span><b aria-hidden="true">→</b><span>检查家族特征</span><b aria-hidden="true">→</b><span class="diagram-good">可靠成员</span><b aria-hidden="true">→</b><span>成员关系图</span></div>
      <p class="diagram-side">证据不足的候选进入“待复核或排除”，不静默消失。</p>""",
    "gene_structure": """
      <div class="gene-model" aria-hidden="true"><i></i><b>片段一</b><i></i><b>片段二</b><i></i><b>片段三</b><i></i></div>
      <div class="diagram-legend"><span><b class="legend-box"></b>保留片段</span><span><b class="legend-line"></b>中间间隔</span><span>← 还要看方向与长度 →</span></div>""",
    "presence_matrix": """
      <div class="presence-demo" role="table" aria-label="四个材料中三个家族分组的检出与未检出示意"><div></div><b>甲</b><b>乙</b><b>丙</b><b>丁</b><strong>组一</strong><i class="on"></i><i class="on"></i><i class="on"></i><i class="on"></i><strong>组二</strong><i class="on"></i><i></i><i class="on"></i><i></i><strong>组三</strong><i></i><i class="on"></i><i></i><i></i></div>
      <div class="diagram-legend"><span><b class="legend-dot on"></b>当前数据检出</span><span><b class="legend-dot"></b>当前数据未检出</span></div>""",
    "chromosome_map": """
      <div class="chromosome-demo" aria-hidden="true"><div><span>染色体一</span><b style="--p:18%"></b><b style="--p:62%"></b><b style="--p:78%"></b></div><div><span>染色体二</span><b style="--p:34%"></b></div><div><span>染色体三</span><b style="--p:12%"></b><b style="--p:48%"></b></div></div>
      <p class="diagram-side">点的数量表示基因个数；还要结合染色体长度判断是否相对集中。</p>""",
    "duplication_paths": """
      <div class="duplication-demo"><div><strong>相邻重复</strong><p><i></i><i></i><span></span></p><small>两个相似基因彼此相邻</small></div><div><strong>大片段重复</strong><p><i></i><i></i><i></i></p><p><i></i><i></i><i></i></p><small>周围多个基因连续对应</small></div><div><strong>远处复制</strong><p><i></i><span></span><i></i></p><small>相似成员位于较远位置</small></div></div>""",
    "coding_change": """
      <div class="coding-demo"><div><span>三个字母一组</span><b>甲乙丙</b><b>甲乙丁</b></div><div><span>不改变蛋白</span><strong>变化率甲</strong></div><div><span>改变蛋白</span><strong>变化率乙</strong></div><div class="ratio"><span>最后再看</span><strong>乙 ÷ 甲</strong></div></div>
      <p class="diagram-side">先看两类变化率本身，再看比值；用来做除数的变化率接近零时必须停下检查。</p>""",
    "promoter_signals": """
      <div class="promoter-demo" aria-hidden="true"><span>基因前方序列</span><div><i></i><b></b><i></i><b></b><i></i></div><strong>基因</strong></div>
      <div class="diagram-legend"><span><b class="legend-signal"></b>匹配到的短序列线索</span><span>匹配 ≠ 已经发挥调控作用</span></div>""",
    "expression_heatmap": """
      <div class="expression-demo"><div class="heatmap-demo" role="img" aria-label="三个基因在四个样本中活跃程度不同的颜色示意"><i class="v1"></i><i class="v2"></i><i class="v3"></i><i class="v1"></i><i class="v3"></i><i class="v3"></i><i class="v2"></i><i class="v1"></i><i class="v2"></i><i class="v1"></i><i class="v1"></i><i class="v3"></i></div><div class="replicate-demo"><strong>对照</strong><span>● ● ●</span><strong>处理</strong><span>● ● ●</span><small>独立重复后才能严格比较</small></div></div>""",
}

CHAPTER_TEN_GROUPS = (
    ("先认清有哪些线索", ("10.1", "10.2", "10.3")),
    ("按家族分组比较", ("10.4", "10.5", "10.6", "10.7")),
    ("按材料或群体比较", ("10.8", "10.9", "10.10", "10.11")),
    ("看重点线索和组合分组", ("10.12", "10.13", "10.14", "10.15")),
)


def read_rows(path: Path, expected_fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != expected_fields:
            raise ValueError(f"Unexpected columns in {path}: {reader.fieldnames}")
        rows = list(reader)
    if any(not value.strip() for row in rows for value in row.values()):
        raise ValueError(f"Blank value in {path}")
    return rows


def render_analysis_links(rows: list[dict[str, str]]) -> str:
    return "".join(
        f'<li><a href="#analysis-{row["source_id"].replace(".", "-")}">'
        f"{html.escape(row['source_id'])} {html.escape(row['beginner_title_zh'])}</a></li>"
        for row in rows
    )


def render_mindmap(
    lessons: list[dict[str, str]], language_by_chapter: dict[str, list[dict[str, str]]]
) -> str:
    lessons_by_stage: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in lessons:
        lessons_by_stage[row["stage_id"]].append(row)
    stage_html = []
    for stage_id, (stage_title, stage_text) in STAGES.items():
        branches = []
        for row in lessons_by_stage[stage_id]:
            chapter = row["chapter"]
            branches.append(
                f'<details class="mindmap-branch" data-chapter="{chapter}">'
                f'<summary><span class="mindmap-chapter">第 {chapter} 章</span>'
                f"<span><strong>{html.escape(row['chapter_title_zh'])}</strong>"
                f"<small>{html.escape(row['question_zh'])}</small></span>"
                f"<em>{row['analysis_count']} 项</em></summary>"
                '<div class="mindmap-branch-body">'
                f"<p><b>接着哪里：</b>{html.escape(row['dependency_zh'])}</p>"
                f"<p><b>主要得到：</b>{html.escape(row['output_label_zh'])}</p>"
                '<ol class="mindmap-analysis-list">'
                f"{render_analysis_links(language_by_chapter[chapter])}</ol>"
                "</div></details>"
                f'<a class="mindmap-start button" href="#chapter-{chapter}">开始第 {chapter} 章</a>'
            )
        stage_html.append(
            f'<article class="mindmap-stage" data-stage="{stage_id}">'
            f'<header><span class="mindmap-stage-number">{stage_id}</span><div><h3>{stage_title}</h3>'
            f"<p>{stage_text}</p></div></header>{''.join(branches)}</article>"
        )
    return (
        "<!-- BEGIN TUTORIAL_MINDMAP -->\n"
        '<section class="reference-section chapter-map beginner-only" id="chapter-map">'
        "<h2>先看全图：58 项分析怎样连成一个故事</h2>"
        '<p class="chapter-map-lead">中心问题不是“要画多少张图”，而是：从多个材料中找到可靠家族成员，说明它们长什么样、在哪里、怎样产生和变化，最后看它们在什么条件下活跃。</p>'
        '<div class="mindmap-root"><strong>研究一个目标基因家族</strong><span>可靠成员 → 结构与位置 → 来源与变化 → 实际活跃条件</span></div>'
        f'<div class="mindmap-stages">{"".join(stage_html)}</div>'
        '<div class="beginner-note"><span aria-hidden="true">↓</span><div><strong>建议顺序：</strong>第一次学习请按 1 → 4 走；每个分支都能展开查看该章全部分析。第 4 章是共同起点，后面的箭头表示需要前一章提供的结果。</div></div>'
        "</section>\n<!-- END TUTORIAL_MINDMAP -->"
    )


def render_chapter_ten_groups(language: dict[str, dict[str, str]]) -> str:
    groups = []
    for label, source_ids in CHAPTER_TEN_GROUPS:
        links = "".join(
            f'<li><a href="#analysis-{source_id.replace(".", "-")}">'
            f"{html.escape(language[source_id]['beginner_title_zh'])}</a></li>"
            for source_id in source_ids
        )
        groups.append(f"<div><h4>{label}</h4><ol>{links}</ol></div>")
    return (
        '<div class="lesson-subgroups"><h4>本章 15 项先分成四组</h4>'
        f'<div class="lesson-subgroup-grid">{"".join(groups)}</div></div>'
    )


def render_chapter_intro(row: dict[str, str], language: dict[str, dict[str, str]]) -> str:
    diagram = DIAGRAMS[row["diagram_type"]]
    chapter_ten = render_chapter_ten_groups(language) if row["chapter"] == "10" else ""
    return (
        f'<section class="beginner-chapter-intro" data-chapter="{row["chapter"]}">'
        '<div class="chapter-lesson-heading"><div><span class="lesson-label">本章学习路线</span>'
        f"<h3>{html.escape(row['chapter_title_zh'])}</h3>"
        f'<p class="beginner-chapter-question">{html.escape(row["question_zh"])}</p></div>'
        f'<span class="lesson-count">{row["analysis_count"]} 项分析</span></div>'
        '<div class="chapter-lesson-layout">'
        f'<div class="lesson-diagram" data-diagram="{html.escape(row["diagram_type"])}" '
        f'role="group" aria-label="第 {row["chapter"]} 章概念示意图">'
        f"<h4>先看图，建立概念</h4>{diagram}</div>"
        '<div class="chapter-lesson-grid">'
        f'<article data-lesson="foundation"><h4>① 基础知识</h4><p>{html.escape(row["foundation_zh"])}</p></article>'
        f'<article data-lesson="why"><h4>② 为什么做</h4><p>{html.escape(row["why_zh"])}</p></article>'
        f'<article data-lesson="how"><h4>③ 怎么做</h4><p><b>准备：</b>{html.escape(row["input_zh"])}</p>'
        f"<p><b>过程：</b>{html.escape(row['method_zh'])}</p><p><b>结果：</b>{html.escape(row['output_zh'])}</p></article>"
        f'<article data-lesson="read"><h4>④ 怎么读结果</h4><p>{html.escape(row["read_zh"])}</p>'
        f'<p class="lesson-boundary"><b>不要误读：</b>{html.escape(row["boundary_zh"])}</p></article>'
        "</div></div>"
        f'<p class="lesson-dependency"><b>与前后章节的关系：</b>{html.escape(row["dependency_zh"])}</p>'
        f"{chapter_ten}"
        f'<button class="chapter-toggle primary" type="button" aria-expanded="false">开始本章</button>'
        "</section>"
    )


def render(source: str) -> str:
    lessons = read_rows(LESSONS_PATH, LESSON_FIELDS)
    if [row["chapter"] for row in lessons] != list(EXPECTED_COUNTS):
        raise ValueError("Chapter lessons must follow the frozen chapter order")
    if {row["chapter"]: int(row["analysis_count"]) for row in lessons} != EXPECTED_COUNTS:
        raise ValueError("Chapter analysis counts must sum to the frozen 58 items")
    language_rows = read_rows(
        LANGUAGE_PATH,
        (
            "source_id",
            "beginner_title_zh",
            "beginner_question_zh",
            "beginner_input_zh",
            "beginner_output_zh",
            "beginner_read_zh",
            "beginner_warning_zh",
        ),
    )
    language_by_chapter: dict[str, list[dict[str, str]]] = defaultdict(list)
    language = {}
    for row in language_rows:
        language_by_chapter[row["source_id"].split(".", 1)[0]].append(row)
        language[row["source_id"]] = row
    if {chapter: len(rows) for chapter, rows in language_by_chapter.items()} != EXPECTED_COUNTS:
        raise ValueError("Beginner-language rows no longer match the frozen 58-item chapter counts")

    mindmap = render_mindmap(lessons, language_by_chapter)
    rendered, count = re.subn(
        r"<!-- BEGIN TUTORIAL_MINDMAP -->.*?<!-- END TUTORIAL_MINDMAP -->",
        mindmap,
        source,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError("Missing tutorial mind-map markers")

    intro_by_chapter = {row["chapter"]: render_chapter_intro(row, language) for row in lessons}
    # The legacy page used a div, while generated lessons use a section.  Each
    # intro has exactly one final chapter-toggle button, which is a stable
    # boundary even for chapter 6 (it has an extra callout before foundation).
    intro_pattern = re.compile(
        r'<(?:div|section) class="beginner-chapter-intro".*?'
        r"</button></(?:div|section)>",
        re.DOTALL,
    )
    found = intro_pattern.findall(rendered)
    if len(found) != 8:
        raise ValueError(f"Expected 8 beginner chapter intros, found {len(found)}")
    iterator = iter(lessons)
    rendered = intro_pattern.sub(lambda _: intro_by_chapter[next(iterator)["chapter"]], rendered)
    return rendered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    source = HTML_PATH.read_text(encoding="utf-8")
    rendered = render(source)
    if arguments.check:
        if rendered != source:
            raise SystemExit("docs/index.html is not synchronized with chapter lessons")
        return
    HTML_PATH.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
