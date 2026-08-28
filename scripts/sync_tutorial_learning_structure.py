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

try:
    from tutorial_title_contract import (
        PROFESSIONAL_CHAPTER_TITLES,
        professional_analysis_title,
    )
except ModuleNotFoundError:  # Loaded as a module from the repository root in tests.
    from scripts.tutorial_title_contract import (
        PROFESSIONAL_CHAPTER_TITLES,
        professional_analysis_title,
    )

ROOT = Path(__file__).resolve().parents[1]
LESSONS_PATH = ROOT / "docs" / "TUTORIAL_CHAPTER_LESSONS.tsv"
LANGUAGE_PATH = ROOT / "docs" / "TUTORIAL_BEGINNER_LANGUAGE.tsv"
COVERAGE_PATH = ROOT / "docs" / "ANALYSIS_COVERAGE.tsv"
EXAMPLES_PATH = ROOT / "docs" / "TUTORIAL_COURSE_EXAMPLES.tsv"
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
EXAMPLE_FIELDS = (
    "chapter",
    "case_title_zh",
    "case_input_zh",
    "steps_zh",
    "visual_type",
    "visual_title_zh",
    "x_axis_zh",
    "y_axis_zh",
    "legend_zh",
    "read_order_zh",
    "table_headers_zh",
    "table_rows_zh",
    "normal_zh",
    "warning_zh",
    "next_zh",
    "figure_contract_zh",
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
      <div class="diagram-legend"><span><b class="legend-signal"></b>匹配到的短序列线索</span><span>匹配 ≠ 已经发挥调控作用</span></div>
      <div class="promoter-summary-demo"><strong>同一张线索表</strong><b aria-hidden="true">→</b><div><span>按四类汇总</span><span>按家族分组</span><span>按材料或群体</span><span>按成员有无</span></div></div>
      <div class="color-range-demo" role="group" aria-label="原始数值与换算后相对高低的读图差别"><div><strong>原始数值</strong><p><i class="c1"></i><i class="c2"></i><i class="c3"></i></p><small>共同颜色范围，可以比较原始深浅</small></div><div><strong>换算后的相对高低</strong><div class="split-scales"><p><span>线索甲</span><i class="c1"></i><i class="c2"></i><i class="c3"></i></p><p><span>线索乙</span><i class="c1"></i><i class="c2"></i><i class="c3"></i></p></div><small>每种线索先按自身平均水平和波动换算</small></div></div>
      <p class="diagram-side">同一份数据可按不同问题重新汇总。换算会产生相对高低值，原始数值表仍单独保留、不被覆盖；换算图的颜色不能用来比较不同线索的原始多少。</p>""",
    "expression_heatmap": """
      <div class="expression-demo"><div class="heatmap-demo" role="img" aria-label="三个基因在四个样本中活跃程度不同的颜色示意"><i class="v1"></i><i class="v2"></i><i class="v3"></i><i class="v1"></i><i class="v3"></i><i class="v3"></i><i class="v2"></i><i class="v1"></i><i class="v2"></i><i class="v1"></i><i class="v1"></i><i class="v3"></i></div><div class="replicate-demo"><strong>对照</strong><span>● ● ●</span><strong>处理</strong><span>● ● ●</span><small>独立重复后才能严格比较</small></div></div>""",
}

CHAPTER_TEN_GROUPS = (
    ("先认清有哪些线索", ("10.1", "10.2", "10.3")),
    ("按家族分组比较", ("10.4", "10.5", "10.6", "10.7")),
    ("按材料或群体比较", ("10.8", "10.9", "10.10", "10.11")),
    ("看重点线索和组合分组", ("10.12", "10.13", "10.14", "10.15")),
)

RESULT_VISUALS = {
    "membership_tree": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">候选判断与可靠成员关系示意</title><desc id="result-desc-{chapter}">左边列出四条候选记录；只有两个通过检查的成员进入右边的关系图，待复核和排除记录停留在图外。</desc>
        <g class="axis"><line x1="78" y1="296" x2="650" y2="296"/><text x="330" y="334">只有通过检查的成员进入关系图</text></g>
        <g class="plot-label"><text x="24" y="70">基因甲一</text><text x="24" y="135">基因乙一</text><text x="24" y="200">基因丙一</text><text x="24" y="265">基因丁一</text></g>
        <g class="tree-lines"><path d="M150 65H330V165H500"/><path d="M150 260H330V165"/><path d="M150 130H245"/><path d="M150 195H245"/></g>
        <circle class="good" cx="130" cy="65" r="13"/><circle class="review" cx="130" cy="130" r="13"/><circle class="bad" cx="130" cy="195" r="13"/><circle class="good" cx="130" cy="260" r="13"/>
        <text x="515" y="171">可靠成员组</text><text x="255" y="136">待复核：暂不进入关系图</text><text x="255" y="201">排除：不进入关系图</text>
      </svg>""",
    "gene_structure_result": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">基因结构和长度分布示意</title><desc id="result-desc-{chapter}">上半部分为外显子和内含子，下半部分为两个分组的基因长度点图。</desc>
        <g class="axis"><line x1="100" y1="150" x2="650" y2="150"/><text x="330" y="178">基因上的相对位置</text><line x1="100" y1="300" x2="650" y2="300"/><line x1="100" y1="205" x2="100" y2="300"/><text x="360" y="338">家族分组</text><text transform="translate(34 288) rotate(-90)">基因长度</text></g>
        <g class="gene-boxes"><line x1="120" y1="80" x2="625" y2="80"/><rect x="135" y="58" width="70" height="44"/><rect x="300" y="58" width="95" height="44"/><rect x="535" y="58" width="60" height="44"/></g>
        <g class="points"><circle cx="250" cy="256" r="9"/><circle cx="250" cy="230" r="9"/><circle cx="250" cy="275" r="9"/><circle cx="510" cy="270" r="9"/><circle cx="510" cy="245" r="9"/><circle cx="510" cy="220" r="9"/></g><text x="222" y="320">分组一</text><text x="482" y="320">分组二</text>
      </svg>""",
    "presence_curve": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">成员有无矩阵和累计发现曲线</title><desc id="result-desc-{chapter}">左边矩阵显示四个材料是否检出三个分组，右边曲线显示增加材料后的累计发现数。</desc>
        <g class="matrix-cells"><rect x="95" y="70" width="42" height="42"/><rect x="143" y="70" width="42" height="42"/><rect x="191" y="70" width="42" height="42"/><rect x="239" y="70" width="42" height="42"/><rect x="95" y="118" width="42" height="42"/><rect class="empty" x="143" y="118" width="42" height="42"/><rect x="191" y="118" width="42" height="42"/><rect class="empty" x="239" y="118" width="42" height="42"/><rect class="empty" x="95" y="166" width="42" height="42"/><rect x="143" y="166" width="42" height="42"/><rect class="empty" x="191" y="166" width="42" height="42"/><rect class="empty" x="239" y="166" width="42" height="42"/></g>
        <g class="plot-label"><text x="40" y="98">组一</text><text x="40" y="146">组二</text><text x="40" y="194">组三</text><text x="105" y="55">甲</text><text x="153" y="55">乙</text><text x="201" y="55">丙</text><text x="249" y="55">丁</text></g>
        <g class="axis"><line x1="380" y1="270" x2="665" y2="270"/><line x1="380" y1="55" x2="380" y2="270"/><text x="470" y="316">已加入的材料数</text><text transform="translate(335 240) rotate(-90)">累计发现的分组数</text></g><path class="curve" d="M390 230 C440 175 485 145 530 120 S610 95 655 90"/><g class="points"><circle cx="390" cy="230" r="7"/><circle cx="480" cy="150" r="7"/><circle cx="570" cy="108" r="7"/><circle cx="655" cy="90" r="7"/></g>
      </svg>""",
    "chromosome_result": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">染色体位置和密度示意</title><desc id="result-desc-{chapter}">三条染色体按实际相对长度绘制，圆点表示家族成员。</desc>
        <g class="axis"><line x1="115" y1="300" x2="660" y2="300"/><text x="330" y="338">染色体上的位置</text></g>
        <g class="chromosome-lines"><text x="35" y="92">染色体一</text><line x1="115" y1="85" x2="650" y2="85"/><text x="35" y="172">染色体二</text><line x1="115" y1="165" x2="380" y2="165"/><text x="35" y="252">染色体三</text><line x1="115" y1="245" x2="555" y2="245"/></g>
        <g class="points"><circle cx="210" cy="85" r="10"/><circle cx="440" cy="85" r="10"/><circle class="alt" cx="585" cy="85" r="10"/><circle cx="250" cy="165" r="10"/><circle class="alt" cx="330" cy="165" r="10"/><circle cx="475" cy="245" r="10"/></g>
      </svg>""",
    "duplication_synteny": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">两个染色体片段的基因顺序对应</title><desc id="result-desc-{chapter}">上下两排基因之间有多条连续对应线，目标家族成员用粗框标出。</desc>
        <text x="26" y="92">片段甲</text><text x="26" y="267">片段乙</text>
        <g class="synteny-links"><line x1="145" y1="105" x2="170" y2="235"/><line x1="250" y1="105" x2="275" y2="235"/><line x1="355" y1="105" x2="380" y2="235"/><line x1="460" y1="105" x2="485" y2="235"/><line x1="565" y1="105" x2="590" y2="235"/></g>
        <g class="synteny-genes"><rect x="115" y="75" width="60" height="30"/><rect x="220" y="75" width="60" height="30"/><rect class="target" x="325" y="75" width="60" height="30"/><rect x="430" y="75" width="60" height="30"/><rect x="535" y="75" width="60" height="30"/><rect x="140" y="235" width="60" height="30"/><rect x="245" y="235" width="60" height="30"/><rect class="target" x="350" y="235" width="60" height="30"/><rect x="455" y="235" width="60" height="30"/><rect x="560" y="235" width="60" height="30"/></g>
        <text x="250" y="330">连续多条对应支持大片段关系</text>
      </svg>""",
    "kaks_result": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">两类编码变化率散点图</title><desc id="result-desc-{chapter}">横轴是不改变蛋白的变化率，纵轴是改变蛋白的变化率，橙色区域表示除数太低时比值不稳定。</desc>
        <rect class="warning-zone" x="105" y="45" width="92" height="235"/><g class="axis"><line x1="105" y1="280" x2="650" y2="280"/><line x1="105" y1="45" x2="105" y2="280"/><text x="330" y="330">不改变蛋白的变化率</text><text transform="translate(38 245) rotate(-90)">改变蛋白的变化率</text></g><line class="reference-line" x1="105" y1="280" x2="610" y2="55"/>
        <g class="points"><circle cx="250" cy="235" r="10"/><circle class="alt" cx="145" cy="100" r="10"/><circle cx="440" cy="190" r="10"/><circle cx="560" cy="150" r="10"/></g><text x="112" y="70">除数太低</text><text x="465" y="85">两类变化率相等</text>
      </svg>""",
    "promoter_heatmap": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">原始匹配次数与相对高低两种颜色图</title><desc id="result-desc-{chapter}">左图所有短序列线索共用一个颜色范围，可比较原始多少；右图每一列单独换算，只能比较同一线索内部的相对高低。</desc>
        <g class="plot-label"><text x="118" y="38">原始次数：共用色尺</text><text x="420" y="38">相对高低：每列单独换算</text><text x="48" y="117">分组一</text><text x="48" y="172">分组二</text><text x="48" y="227">分组三</text><text x="116" y="78">甲</text><text x="181" y="78">乙</text><text x="246" y="78">丙</text><text x="426" y="78">甲</text><text x="491" y="78">乙</text><text x="556" y="78">丙</text></g>
        <g class="heat-cells"><rect class="h3" x="110" y="90" width="55" height="42"/><rect class="h1" x="175" y="90" width="55" height="42"/><rect class="h2" x="240" y="90" width="55" height="42"/><rect class="h2" x="110" y="145" width="55" height="42"/><rect class="h2" x="175" y="145" width="55" height="42"/><rect class="h1" x="240" y="145" width="55" height="42"/><rect class="h1" x="110" y="200" width="55" height="42"/><rect class="h1" x="175" y="200" width="55" height="42"/><rect class="h2" x="240" y="200" width="55" height="42"/><rect class="h3" x="420" y="90" width="55" height="42"/><rect class="h1" x="485" y="90" width="55" height="42"/><rect class="h2" x="550" y="90" width="55" height="42"/><rect class="h2" x="420" y="145" width="55" height="42"/><rect class="h3" x="485" y="145" width="55" height="42"/><rect class="h1" x="550" y="145" width="55" height="42"/><rect class="h1" x="420" y="200" width="55" height="42"/><rect class="h2" x="485" y="200" width="55" height="42"/><rect class="h3" x="550" y="200" width="55" height="42"/></g>
        <g class="axis"><text x="116" y="280">可比较不同线索的原始多少</text><text x="407" y="280">只比较同一线索内部的高低</text><text x="260" y="325">短序列线索</text></g>
      </svg>""",
    "expression_result": """
      <svg viewBox="0 0 720 350" role="img" aria-labelledby="result-title-{chapter} result-desc-{chapter}">
        <title id="result-title-{chapter}">表达颜色图和处理对照结果</title><desc id="result-desc-{chapter}">左边颜色图显示同一基因在六个样本中的相对高低，右边点图显示处理后的变化方向和证据强弱。</desc>
        <g class="plot-label"><text x="25" y="102">基因甲一</text><text x="25" y="162">基因甲四</text><text x="25" y="222">基因丙二</text><text x="135" y="58">对照一至三</text><text x="290" y="58">处理一至三</text></g>
        <g class="heat-cells"><rect class="h1" x="120" y="75" width="42" height="42"/><rect class="h1" x="168" y="75" width="42" height="42"/><rect class="h2" x="216" y="75" width="42" height="42"/><rect class="h3" x="278" y="75" width="42" height="42"/><rect class="h3" x="326" y="75" width="42" height="42"/><rect class="h3" x="374" y="75" width="42" height="42"/><rect class="h3" x="120" y="135" width="42" height="42"/><rect class="h3" x="168" y="135" width="42" height="42"/><rect class="h2" x="216" y="135" width="42" height="42"/><rect class="h1" x="278" y="135" width="42" height="42"/><rect class="h1" x="326" y="135" width="42" height="42"/><rect class="h1" x="374" y="135" width="42" height="42"/><rect class="h2" x="120" y="195" width="42" height="42"/><rect class="h2" x="168" y="195" width="42" height="42"/><rect class="h2" x="216" y="195" width="42" height="42"/><rect class="h2" x="278" y="195" width="42" height="42"/><rect class="h2" x="326" y="195" width="42" height="42"/><rect class="h2" x="374" y="195" width="42" height="42"/></g>
        <g class="axis"><line x1="480" y1="275" x2="680" y2="275"/><line x1="580" y1="70" x2="580" y2="275"/><text x="515" y="322">处理后变化大小</text></g><g class="points"><circle class="up" cx="650" cy="105" r="10"/><circle class="down" cx="515" cy="140" r="10"/><circle cx="595" cy="235" r="10"/></g><text x="480" y="55">越靠上证据越强</text>
      </svg>""",
}


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
        f'<li class="mindmap-analysis-item {row["state"].lower()}">'
        f'<a href="#analysis-{row["source_id"].replace(".", "-")}">'
        f'<span class="mindmap-analysis-number">{html.escape(row["source_id"])}</span>'
        f'<span class="mindmap-analysis-copy"><strong>{html.escape(row["professional_title_zh"])}</strong>'
        f"<small>{html.escape(row['beginner_title_zh'])}</small></span>"
        f'<span class="mindmap-analysis-state">'
        f"{'已实现' if row['state'] == 'IMPLEMENTED' else '有条件可用'}</span></a></li>"
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
                f'<article class="mindmap-branch" data-chapter="{chapter}">'
                f'<header class="mindmap-branch-heading"><span class="mindmap-chapter">{chapter}</span>'
                f"<span><strong>{html.escape(PROFESSIONAL_CHAPTER_TITLES[chapter])}</strong>"
                f"<small>通俗理解：{html.escape(row['chapter_title_zh'])}</small></span>"
                f"<em>{row['analysis_count']} 项</em></header>"
                '<div class="mindmap-branch-body">'
                f'<p class="mindmap-chapter-question">本节回答：{html.escape(row["question_zh"])}</p>'
                f"<p><b>接着哪里：</b>{html.escape(row['dependency_zh'])}</p>"
                f"<p><b>主要得到：</b>{html.escape(row['output_label_zh'])}</p>"
                '<ol class="mindmap-analysis-list">'
                f"{render_analysis_links(language_by_chapter[chapter])}</ol>"
                f'<a class="mindmap-start button" href="#chapter-{chapter}">学习{html.escape(PROFESSIONAL_CHAPTER_TITLES[chapter])}</a>'
                "</div></article>"
            )
        stage_html.append(
            f'<article class="mindmap-stage" data-stage="{stage_id}">'
            f'<header><span class="mindmap-stage-number">{stage_id}</span><div><h3>{stage_title}</h3>'
            f'<p>{stage_text}</p></div></header><div class="mindmap-stage-chapters">'
            f"{''.join(branches)}</div></article>"
        )
    return (
        "<!-- BEGIN TUTORIAL_MINDMAP -->\n"
        '<section class="reference-section chapter-map beginner-only" id="chapter-map">'
        "<h2>泛基因家族分析课程图谱：8 个专业大节、58 项分析</h2>"
        '<p class="chapter-map-lead">这不是摘要，也不是折叠菜单。下面按研究顺序完整列出 58 项分析；专业标题是课程目录，标题下的一句话负责解释“这一项在做什么”。</p>'
        '<div class="mindmap-summary" aria-label="课程覆盖摘要"><strong>58 / 58 项全部可见</strong><span>8 个专业大节</span><span>53 项已实现</span><span>5 项有条件可用</span></div>'
        '<div class="mindmap-root"><strong>研究一个目标基因家族</strong><span>可靠成员 → 结构与位置 → 来源与变化 → 实际活跃条件</span></div>'
        f'<div class="mindmap-stages">{"".join(stage_html)}</div>'
        '<div class="beginner-note"><span aria-hidden="true">↓</span><div><strong>建议顺序：</strong>第一次学习请按阶段 1 → 4、专业大节 4 → 11 顺序学习。点击任一专业小节，可直接进入该项的基础知识、分析方法和结果解读。</div></div>'
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


def split_items(value: str, separator: str = "｜") -> list[str]:
    return [item.strip() for item in value.split(separator) if item.strip()]


def beginner_plain(value: str) -> str:
    replacements = {
        "非同义变化": "改变蛋白的变化",
        "同义变化": "不改变蛋白的变化",
        "同义": "不改变蛋白",
        "校正后可信程度": "多次比较后的错误概率（越小证据越强）",
        "多重比较后的可信程度": "多次比较后的错误概率，数值越小证据越强",
        "可信程度": "证据强弱",
        "启动子": "基因前方序列",
        "顺式作用元件": "短序列线索",
        "元件名称": "短序列线索名称",
        "元件": "短序列线索",
        "热图": "颜色图",
        "校正": "调整",
        "串联复制": "相邻复制（两个相似基因彼此相邻）",
        "分散复制": "远处复制（相似基因位于较远位置）",
        "基因前方序列序列": "基因前方序列",
    }
    for technical, plain in replacements.items():
        value = value.replace(technical, plain)
    return value


def render_example_table(row: dict[str, str]) -> str:
    headers = split_items(row["table_headers_zh"])
    records = [split_items(record) for record in split_items(row["table_rows_zh"], "；")]
    if not headers or any(len(record) != len(headers) for record in records):
        raise ValueError(f"Malformed teaching table for chapter {row['chapter']}")
    head = "".join(f'<th scope="col">{html.escape(value)}</th>' for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in record) + "</tr>"
        for record in records
    )
    return (
        '<div class="table-scroll course-table-scroll"><table class="course-example-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def render_worked_example(row: dict[str, str]) -> str:
    row = {
        key: value if key == "visual_type" else beginner_plain(value) for key, value in row.items()
    }
    steps = "".join(f"<li>{html.escape(step)}</li>" for step in split_items(row["steps_zh"]))
    visual = RESULT_VISUALS[row["visual_type"]].format(chapter=row["chapter"])
    return (
        f'<section class="course-worked-example" aria-labelledby="course-example-{row["chapter"]}">'
        '<div class="course-example-heading"><div><span class="course-example-label">贯穿全教程的教学示例</span>'
        f'<h4 id="course-example-{row["chapter"]}">{html.escape(row["case_title_zh"])}</h4></div>'
        "<strong>只用于练习读图，不代表真实水稻结论</strong></div>"
        f'<p class="course-input"><b>这一章拿什么来练：</b>{html.escape(row["case_input_zh"])}</p>'
        f'<ol class="course-step-list">{steps}</ol>'
        '<div class="course-result-layout">'
        '<figure class="course-result-figure">'
        f"<h5>{html.escape(row['visual_title_zh'])}</h5>{visual}"
        f"<figcaption><b>横轴：</b>{html.escape(row['x_axis_zh'])}<br>"
        f"<b>纵轴：</b>{html.escape(row['y_axis_zh'])}<br>"
        f"<b>颜色和符号：</b>{html.escape(row['legend_zh'])}</figcaption></figure>"
        '<aside class="course-read-order"><h5>按这个顺序读图</h5>'
        f"<ol>{''.join(f'<li>{html.escape(item)}</li>' for item in split_items(row['read_order_zh']))}</ol>"
        "<p><b>先回答：</b>图里比较的对象是谁？记录数是否齐全？颜色和坐标各表示什么？</p></aside>"
        "</div>"
        '<div class="course-table-block"><h5>再回到结果表核对</h5>'
        f"{render_example_table(row)}</div>"
        '<div class="course-verdict-grid">'
        f'<article class="course-normal"><h5>看到什么算正常</h5><p>{html.escape(row["normal_zh"])}</p></article>'
        f'<article class="course-warning"><h5>出现什么要停下来检查</h5><p>{html.escape(row["warning_zh"])}</p></article>'
        "</div>"
        f'<p class="course-next"><b>学完本章去哪里：</b>{html.escape(row["next_zh"])}</p>'
        "</section>"
    )


def render_inventory(
    lesson: dict[str, str], example: dict[str, str], language_rows: list[dict[str, str]]
) -> str:
    links = "".join(
        f'<li><a href="#analysis-{item["source_id"].replace(".", "-")}">'
        f"{html.escape(item['source_id'])} {html.escape(item['beginner_title_zh'])}</a></li>"
        for item in language_rows
    )
    return (
        '<details class="course-inventory"><summary>查阅本章完整分析清单与原模板图号（选学）</summary>'
        f"<p>本章覆盖 {lesson['analysis_count']} 项分析；对应原模板图："
        f"{html.escape(beginner_plain(example['figure_contract_zh']))}。第一次学习不必逐项展开。</p>"
        f"<ol>{links}</ol></details>"
    )


def render_chapter_intro(
    row: dict[str, str],
    example: dict[str, str],
    language: dict[str, dict[str, str]],
    language_rows: list[dict[str, str]],
) -> str:
    diagram = DIAGRAMS[row["diagram_type"]]
    chapter_ten = render_chapter_ten_groups(language) if row["chapter"] == "10" else ""
    next_link = (
        '<a href="#chapter-map">完成课程，回到分析全图</a>'
        if row["chapter"] == "11"
        else f'<a href="#chapter-{int(row["chapter"]) + 1}" '
        f'data-next-chapter="{int(row["chapter"]) + 1}">继续下一章</a>'
    )
    return (
        f'<section class="beginner-chapter-intro" data-chapter="{row["chapter"]}">'
        '<div class="chapter-lesson-heading"><div><span class="lesson-label">本章学习路线</span>'
        f"<h3>{html.escape(PROFESSIONAL_CHAPTER_TITLES[row['chapter']])}</h3>"
        f'<p class="chapter-plain-title">通俗理解：{html.escape(row["chapter_title_zh"])}</p>'
        f'<p class="beginner-chapter-question">{html.escape(row["question_zh"])}</p></div>'
        f'<span class="lesson-count">{row["analysis_count"]} 项分析</span></div>'
        '<div class="chapter-lesson-layout">'
        f'<figure class="lesson-diagram course-concept-figure" data-diagram="{html.escape(row["diagram_type"])}" '
        f'aria-labelledby="concept-title-{row["chapter"]}">'
        f'<h4 id="concept-title-{row["chapter"]}">先看图，建立概念</h4>{diagram}'
        f"<figcaption>这张图只解释第 {row['chapter']} 章的核心关系，不是分析结果。</figcaption></figure>"
        '<div class="chapter-lesson-grid">'
        f'<article data-lesson="foundation"><h4>① 基础知识</h4><p>{html.escape(row["foundation_zh"])}</p></article>'
        f'<article data-lesson="why"><h4>② 为什么做</h4><p>{html.escape(row["why_zh"])}</p></article>'
        f'<article data-lesson="how"><h4>③ 怎么做</h4><p><b>准备：</b>{html.escape(row["input_zh"])}</p>'
        f"<p><b>过程：</b>{html.escape(row['method_zh'])}</p><p><b>结果：</b>{html.escape(row['output_zh'])}</p></article>"
        f'<article data-lesson="read"><h4>④ 怎么读结果</h4><p>{html.escape(row["read_zh"])}</p>'
        f'<p class="lesson-boundary"><b>不要误读：</b>{html.escape(row["boundary_zh"])}</p></article>'
        "</div></div>"
        f'<p class="lesson-dependency"><b>与前后章节的关系：</b>{html.escape(row["dependency_zh"])}</p>'
        f"{render_worked_example(example)}"
        f"{chapter_ten}{render_inventory(row, example, language_rows)}"
        '<nav class="course-chapter-nav" aria-label="章节学习导航">'
        '<a href="#chapter-map">返回分析全图</a>'
        f"{next_link}"
        "</nav>"
        f'<button class="chapter-toggle primary" type="button" aria-expanded="false">开始本章</button>'
        "</section>"
    )


def render(source: str) -> str:
    lessons = read_rows(LESSONS_PATH, LESSON_FIELDS)
    examples = read_rows(EXAMPLES_PATH, EXAMPLE_FIELDS)
    if [row["chapter"] for row in lessons] != list(EXPECTED_COUNTS):
        raise ValueError("Chapter lessons must follow the frozen chapter order")
    if {row["chapter"]: int(row["analysis_count"]) for row in lessons} != EXPECTED_COUNTS:
        raise ValueError("Chapter analysis counts must sum to the frozen 58 items")
    if [row["chapter"] for row in examples] != list(EXPECTED_COUNTS):
        raise ValueError("Teaching examples must follow the frozen chapter order")
    if any(row["visual_type"] not in RESULT_VISUALS for row in examples):
        raise ValueError("Unknown teaching-result visual type")
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
    coverage_rows = read_rows(
        COVERAGE_PATH,
        (
            "source_id",
            "source_title",
            "state",
            "evidence",
            "output",
            "limitation",
            "tutorial_anchor",
        ),
    )
    if [row["source_id"] for row in coverage_rows] != [row["source_id"] for row in language_rows]:
        raise ValueError("Coverage and beginner-language rows must use the same frozen order")
    coverage = {row["source_id"]: row for row in coverage_rows}
    language_by_chapter: dict[str, list[dict[str, str]]] = defaultdict(list)
    language = {}
    for row in language_rows:
        coverage_row = coverage[row["source_id"]]
        row["professional_title_zh"] = professional_analysis_title(
            row["source_id"], coverage_row["source_title"]
        )
        row["state"] = coverage_row["state"]
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

    example_by_chapter = {row["chapter"]: row for row in examples}
    intro_by_chapter = {
        row["chapter"]: render_chapter_intro(
            row,
            example_by_chapter[row["chapter"]],
            language,
            language_by_chapter[row["chapter"]],
        )
        for row in lessons
    }
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
