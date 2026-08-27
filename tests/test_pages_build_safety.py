import hashlib
import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_pages_site.py"
SPEC = importlib.util.spec_from_file_location("panfamflow_build_pages_site", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build = MODULE.build


def write_tutorial_assets(tutorial: Path) -> None:
    fixtures = {
        "ANALYSIS_COVERAGE.tsv": "source_id\tstate\n4.1\tIMPLEMENTED\n",
        "ANALYSIS_COVERAGE.zh-CN.md": "# coverage\n",
        "EXTERNAL_EVIDENCE_IMPORTS.zh-CN.md": "# external evidence imports\n",
        "TEMPLATE_EQUIVALENCE_AUDIT.zh-CN.md": "# template equivalence\n",
        "TEMPLATE_FIGURE_EQUIVALENCE.tsv": (
            "template_figure\tequivalence_status\nFig01\tMATCHED_CORE\n"
        ),
        "TUTORIAL_CONTENT_MATRIX.tsv": "source_id\tstate\n4.1\tIMPLEMENTED\n",
        "TUTORIAL_BEGINNER_LANGUAGE.tsv": (
            "source_id\tbeginner_title_zh\n4.1\t确认哪些基因属于这个家族\n"
        ),
        "TUTORIAL_BEGINNER_LANGUAGE_AUDIT.zh-CN.md": "# beginner language audit\n",
        "TUTORIAL_GAP_AUDIT.zh-CN.md": "# gap audit\n",
        "TUTORIAL_REPOSITORY_INTEGRATION_QA.zh-CN.md": "# integration QA\n",
        "TUTORIAL_TERMINOLOGY.tsv": (
            "term_id\tchinese_primary\ttechnical_form\tcategory\n"
            "hog\t分层正交组\tHOG\tSTANDARD_TERM\n"
        ),
        "TUTORIAL_TOY_EVIDENCE_SCHEMA.tsv": "evidence_id\tstatus\nC4\tVERIFIED\n",
    }
    for name, content in fixtures.items():
        (tutorial.parent / name).write_text(content, encoding="utf-8")


@pytest.mark.parametrize("output_name", [".", "site", "site/nested", "docs"])
def test_build_rejects_output_that_overlaps_inputs(tmp_path: Path, output_name: str) -> None:
    source = tmp_path / "site"
    source.mkdir()
    (source / "index.html").write_text("home", encoding="utf-8")
    tutorial = tmp_path / "docs" / "index.html"
    tutorial.parent.mkdir()
    tutorial.write_text("tutorial", encoding="utf-8")
    write_tutorial_assets(tutorial)
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsafe output directory"):
        build(source, tutorial, tmp_path / output_name)

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_build_accepts_disjoint_output(tmp_path: Path) -> None:
    source = tmp_path / "site"
    source.mkdir()
    (source / "index.html").write_text("home", encoding="utf-8")
    tutorial = tmp_path / "docs" / "index.html"
    tutorial.parent.mkdir()
    tutorial.write_text("tutorial", encoding="utf-8")
    write_tutorial_assets(tutorial)
    output = tmp_path / "_site"

    build(source, tutorial, output)

    assert (output / "index.html").read_text(encoding="utf-8") == "home"
    assert (output / "tutorial" / "index.html").read_text(encoding="utf-8") == "tutorial"
    for name in MODULE.TUTORIAL_ASSETS:
        source_asset = tutorial.parent / name
        published_asset = output / "tutorial" / name
        assert published_asset.read_bytes() == source_asset.read_bytes()
        digest = hashlib.sha256(source_asset.read_bytes()).hexdigest()
        assert f"tutorial/{name}\t{source_asset.stat().st_size}\t{digest}" in (
            output / "SITE_MANIFEST.tsv"
        ).read_text(encoding="utf-8")
    assert (output / "SITE_MANIFEST.tsv").is_file()


def test_every_published_tutorial_asset_triggers_pages_deployment() -> None:
    workflow = (SCRIPT_PATH.parents[1] / ".github/workflows/pages.yml").read_text(encoding="utf-8")

    for name in MODULE.TUTORIAL_ASSETS:
        assert f'"docs/{name}"' in workflow, name
