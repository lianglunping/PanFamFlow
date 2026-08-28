# Chinese tutorial strings intentionally use full-width punctuation.
# ruff: noqa: RUF001

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "index.html"
EXAMPLES = ROOT / "docs" / "TUTORIAL_COURSE_EXAMPLES.tsv"


def test_course_contract_has_one_complete_example_per_chapter() -> None:
    with EXAMPLES.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["chapter"] for row in rows] == [str(chapter) for chapter in range(4, 12)]
    assert all(len(row["steps_zh"].split("｜")) >= 4 for row in rows)
    assert all(len(row["table_rows_zh"].split("；")) >= 3 for row in rows)
    assert all(row["normal_zh"] and row["warning_zh"] and row["next_zh"] for row in rows)


def test_beginner_course_renders_figures_tables_and_reading_guides() -> None:
    text = HTML.read_text(encoding="utf-8")
    assert text.count('class="course-worked-example"') == 8
    assert text.count('class="course-result-figure"') == 8
    assert text.count('class="course-example-table"') == 8
    assert text.count('class="course-normal"') == 8
    assert text.count('class="course-warning"') == 8
    assert text.count('class="course-inventory"') == 8
    assert text.count("只用于练习读图，不代表真实水稻结论") == 8
    for chapter in range(4, 12):
        assert f'id="result-title-{chapter}"' in text
        assert f'id="result-desc-{chapter}"' in text
        assert f'id="course-example-{chapter}"' in text


def test_every_result_figure_teaches_axes_legend_and_read_order() -> None:
    text = HTML.read_text(encoding="utf-8")
    assert text.count("<b>横轴：</b>") == 8
    assert text.count("<b>纵轴：</b>") == 8
    assert text.count("<b>颜色和符号：</b>") == 8
    assert text.count("按这个顺序读图") == 8
    assert text.count("再回到结果表核对") == 8


def test_internal_chapter_blocks_do_not_leak_into_beginner_course() -> None:
    text = HTML.read_text(encoding="utf-8")
    assert (
        'html[data-learning-mode="beginner"] .chapter>.chapter-block{display:none!important}'
        in text
    )
    assert 'html[data-learning-mode="beginner"] .chapter-quick-nav{display:none!important}' in text


def test_no_javascript_fallback_keeps_course_and_manual_readable() -> None:
    text = HTML.read_text(encoding="utf-8")
    assert (
        "<noscript><style>.beginner-only,.beginner-chapter-intro{display:block!important}" in text
    )
    assert "零基础课程和完整技术正文仍可从上到下阅读" in text


def test_beginner_course_closes_known_novice_teaching_traps() -> None:
    text = HTML.read_text(encoding="utf-8")
    beginner_course = "".join(
        re.findall(r'<section class="course-worked-example".*?</section>', text, re.DOTALL)
    )
    assert beginner_course.count('class="course-worked-example"') == 8
    assert "非不改变蛋白" not in beginner_course
    assert "同义" not in beginner_course
    assert "元件" not in beginner_course
    assert "序列序列" not in beginner_course
    assert "红色表示排除" in beginner_course
    assert "待复核：暂不进入关系图" in beginner_course
    assert "排除：不进入关系图" in beginner_course
    assert "原始次数：共用色尺" in beginner_course
    assert "相对高低：每列单独换算" in beginner_course
    assert "多次比较后的错误概率（越小证据越强）" in beginner_course
    assert "相邻复制（两个相似基因彼此相邻）" in beginner_course
    assert "远处复制（相似基因位于较远位置）" in beginner_course
