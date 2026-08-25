# Chinese prose assertions intentionally contain full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "TEMPLATE_FIGURE_EQUIVALENCE.tsv"
AUDIT = ROOT / "docs" / "TEMPLATE_EQUIVALENCE_AUDIT.zh-CN.md"


def test_template_figure_audit_covers_fig01_through_fig34_without_overclaiming() -> None:
    with MATRIX.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    assert len(rows) == 33  # Fig21-22 is one caption and one audit row.
    assert rows[0]["template_figure"] == "Fig01"
    assert rows[-1]["template_figure"] == "Fig34"
    assert Counter(row["equivalence_status"] for row in rows) == {
        "MATCHED_CORE": 28,
        "CONDITIONAL_MATCH": 5,
    }
    assert all(row["related_coverage"] != "UNMAPPED" for row in rows)
    assert all(row["current_evidence"] for row in rows)
    assert all(row["material_gap"] for row in rows)


def test_public_tutorial_distinguishes_capability_from_template_equivalence() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    tutorial = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    chinese_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    assert "工程交付层面" in audit
    assert "真实研究结论层面" in audit
    assert "14/14" in audit
    assert "仍不是对任意目标家族的生物学等价性证明" in audit
    assert "能力主题覆盖不等于 PDF/MD 模板等价" in tutorial
    assert "上述 58 项是“主题能力状态”，不是 PDF 图件完成率" in chinese_readme
    assert "TEMPLATE_FIGURE_EQUIVALENCE.tsv" in tutorial
