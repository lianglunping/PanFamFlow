"""Frozen professional titles used by every tutorial navigation layer."""

# Chinese tutorial titles intentionally use full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

PROFESSIONAL_CHAPTER_TITLES = {
    "4": "第 4 节：家族成员鉴定与系统发育",
    "5": "第 5 节：基因结构",
    "6": "第 6 节：HOG、目标家族占有与核心型 / 近核心型 / 壳层型 / 稀有型",
    "7": "第 7 节：染色体定位",
    "8": "第 8 节：复制类型与共线性",
    "9": "第 9 节：Ka、Ks、Ka/Ks 与选择压力",
    "10": "第 10 节：启动子与顺式作用元件",
    "11": "第 11 节：表达模式与外部表达结果整合",
}

PROFESSIONAL_ANALYSIS_TITLE_OVERRIDES = {
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


def professional_analysis_title(source_id: str, source_title: str) -> str:
    """Return the reader-facing professional title for one frozen analysis."""

    return PROFESSIONAL_ANALYSIS_TITLE_OVERRIDES.get(source_id, source_title)
