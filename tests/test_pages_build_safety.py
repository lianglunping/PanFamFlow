from pathlib import Path

import pytest

from scripts.build_pages_site import build


@pytest.mark.parametrize("output_name", [".", "site", "site/nested", "docs"])
def test_build_rejects_output_that_overlaps_inputs(tmp_path: Path, output_name: str) -> None:
    source = tmp_path / "site"
    source.mkdir()
    (source / "index.html").write_text("home", encoding="utf-8")
    tutorial = tmp_path / "docs" / "index.html"
    tutorial.parent.mkdir()
    tutorial.write_text("tutorial", encoding="utf-8")
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
    output = tmp_path / "_site"

    build(source, tutorial, output)

    assert (output / "index.html").read_text(encoding="utf-8") == "home"
    assert (output / "tutorial" / "index.html").read_text(encoding="utf-8") == "tutorial"
    assert (output / "SITE_MANIFEST.tsv").is_file()
