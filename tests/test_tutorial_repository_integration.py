"""Compatibility gates for replacing the tutorial in the current PanFamFlow repository."""

from __future__ import annotations

import csv
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "index.html"
PRO_CONTENT_BASELINE = "eebe5af5f58de3b932bc54a2b1b540579053889b"
CURRENT_STATUS_SUMMARY = "53 `IMPLEMENTED`、5 `CONDITIONALLY_AVAILABLE`"


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.external_scripts: list[str] = []
        self.external_stylesheets: list[str] = []
        self.menu_attrs: dict[str, str | None] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag == "script" and values.get("src"):
            self.external_scripts.append(values["src"] or "")
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.external_stylesheets.append(values["href"] or "")
        if values.get("id") == "menuToggle":
            self.menu_attrs = values


def parse() -> tuple[str, Parser]:
    text = HTML.read_text(encoding="utf-8")
    parser = Parser()
    parser.feed(text)
    return text, parser


def test_current_repository_legacy_tutorial_contract_is_preserved() -> None:
    text, parser = parse()
    for phrase in (
        "PanFamFlow 中文入门教程",
        "目标家族",
        "不做泛基因组组装",
        "交互式 config.yaml 片段生成器",
        "uv run panfamflow resume -c config.yaml",
        "树上 clade ≠ 自动成为 HOG",
    ):
        assert phrase in text
    for legacy_id in (
        "overview",
        "step-0",
        "step-11",
        "generator",
        "troubleshooting",
        "quiz",
    ):
        assert legacy_id in parser.ids
    assert len(parser.ids) == len(set(parser.ids))
    assert parser.external_scripts == []
    assert parser.external_stylesheets == []


def test_content_baseline_local_validation_and_pages_compatibility_are_explicit() -> None:
    text, _ = parse()
    assert "教程内容基线" in text
    assert PRO_CONTENT_BASELINE[:12] in text
    assert "本地验证日期 2026-08-26" in text
    assert "修复尚未提交" not in text
    assert 'href="../README.zh-CN.md"' in text
    assert 'href="../README.md"' in text


def test_mobile_menu_exposes_and_updates_aria_state() -> None:
    text, parser = parse()
    assert parser.menu_attrs.get("aria-controls") == "sidebar"
    assert parser.menu_attrs.get("aria-expanded") == "false"
    assert "setSidebarOpen" in text
    assert "setAttribute('aria-expanded', String(open))" in text
    assert "event.key === 'Escape'" in text


def test_responsive_overflow_guards_are_present() -> None:
    text, _ = parse()
    for guard in (
        "overflow-wrap:anywhere",
        "max-width:100%",
        ".legacy-anchor",
        ".chapter-quick-nav{max-width:100%}",
    ):
        assert guard in text


def test_published_supporting_docs_match_current_capability_release() -> None:
    gap_audit = (ROOT / "docs/TUTORIAL_GAP_AUDIT.zh-CN.md").read_text(encoding="utf-8")
    integration_qa = (ROOT / "docs/TUTORIAL_REPOSITORY_INTEGRATION_QA.zh-CN.md").read_text(
        encoding="utf-8"
    )
    validation = (ROOT / "docs/VALIDATION.md").read_text(encoding="utf-8")
    for text in (gap_audit, integration_qa, validation):
        assert CURRENT_STATUS_SUMMARY in text
    for stale in (
        "21 `IMPLEMENTED`、29 `CONDITIONALLY_AVAILABLE`",
        "远程 GitHub Pages 尚未部署",
        "当前能力矩阵明确为 NOT_SUPPORTED",
    ):
        assert stale not in gap_audit
        assert stale not in integration_qa

    assert "PR #11" in integration_qa
    assert "HTTP 200" in integration_qa
    assert "当前发布验收快照（2026-08-25）" in validation  # noqa: RUF001


def test_synteny_toy_evidence_matches_conditional_implementation() -> None:
    text = (ROOT / "docs/TUTORIAL_TOY_EVIDENCE_SCHEMA.tsv").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if "\tC8-SYNTENY\t" in line)
    assert "results/08_duplication/synteny_anchors.tsv" in row
    assert "\tVERIFIED\t" in row
    assert "NONE_CURRENTLY" not in row
    assert "NOT_SUPPORTED" not in row


def test_implemented_matrix_rows_do_not_describe_missing_or_future_paths() -> None:
    with (ROOT / "docs/TUTORIAL_CONTENT_MATRIX.tsv").open(encoding="utf-8", newline="") as handle:
        rows = {row["source_id"]: row for row in csv.DictReader(handle, delimiter="\t")}

    forbidden_by_id = {
        "7.2": ("当前没有专用联合规则或图",),
        "9.8": ("未来应在每个亚家族内比较群体", "当前只能说明该问题已被正式列入范围"),
        "11.1": ("当前没有联合汇总或统计规则",),
        "11.6": ("未来应先在物种内按组织汇总", "当前只能确认该问题被纳入范围"),
        "11.7": ("未来应先区分基因层", "当前只能说明该交互问题已正式登记"),
    }
    for source_id, forbidden_phrases in forbidden_by_id.items():
        row = rows[source_id]
        assert row["state"] == "IMPLEMENTED"
        text = " ".join(row.values())
        for phrase in forbidden_phrases:
            assert phrase not in text, (source_id, phrase)


def test_rendered_tutorial_and_chapter_status_match_reachable_paths() -> None:
    text, _ = parse()
    for phrase in (
        "核心结构域 sequence Logo 尚无裁剪、同源位点 QC 和规范输出",
        "当前没有专用联合规则或图",
        "当前没有联合汇总或统计规则",
        "当前只能说明该问题已被正式列入范围",
        "当前只能确认该问题被纳入范围",
        "当前只能说明该交互问题已正式登记",
    ):
        assert phrase not in text
    assert "本地验证日期 2026-08-26" in text


def test_template_equivalence_audit_records_closed_engineering_acceptance() -> None:
    text = (ROOT / "docs/TEMPLATE_EQUIVALENCE_AUDIT.zh-CN.md").read_text(encoding="utf-8")
    for stale in (
        "B10 与 14 门验收完成前",
        "当前仍在等待 B10 clean run",
        "当前待完成的验收工作",
    ):
        assert stale not in text
    for evidence in ("14/14", "原生 JCVI", "24 个公共 RNA-seq 生物学样本"):
        assert evidence in text
    with (ROOT / "docs/IMPLEMENTATION_ORDER.tsv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert rows
    assert all(row["status"] == "PASS" for row in rows)


def test_current_quality_count_is_not_stale() -> None:
    integration_qa = (ROOT / "docs/TUTORIAL_REPOSITORY_INTEGRATION_QA.zh-CN.md").read_text(
        encoding="utf-8"
    )
    assert "PR #11" in integration_qa
    assert "278 passed" in integration_qa
    assert "277 passed" not in integration_qa
    assert "268 passed" not in integration_qa
