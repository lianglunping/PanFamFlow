#!/usr/bin/env python3
"""Build the minimal PanFamFlow GitHub Pages artifact."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

FORBIDDEN_TOP_LEVEL = {
    ".git",
    ".github",
    "src",
    "tests",
    "uv.lock",
    "results",
    "work",
}
TUTORIAL_ASSETS = (
    "ANALYSIS_COVERAGE.tsv",
    "ANALYSIS_COVERAGE.zh-CN.md",
    "EXTERNAL_EVIDENCE_IMPORTS.zh-CN.md",
    "TEMPLATE_EQUIVALENCE_AUDIT.zh-CN.md",
    "TEMPLATE_FIGURE_EQUIVALENCE.tsv",
    "TUTORIAL_CONTENT_MATRIX.tsv",
    "TUTORIAL_GAP_AUDIT.zh-CN.md",
    "TUTORIAL_REPOSITORY_INTEGRATION_QA.zh-CN.md",
    "TUTORIAL_TERMINOLOGY.tsv",
    "TUTORIAL_TOY_EVIDENCE_SCHEMA.tsv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("site"))
    parser.add_argument("--tutorial", type=Path, default=Path("docs/index.html"))
    parser.add_argument("--output", type=Path, default=Path("_site"))
    return parser.parse_args()


def build(source: Path, tutorial: Path, output: Path) -> None:
    source = source.resolve()
    tutorial = tutorial.resolve()
    output = output.resolve()
    if output == output.parent or output.name in {"", ".", ".."}:
        raise ValueError(f"Unsafe output directory: {output}")
    if (
        output in (source, tutorial)
        or output in source.parents
        or source in output.parents
        or output in tutorial.parents
        or tutorial in output.parents
    ):
        raise ValueError(f"Unsafe output directory (overlaps inputs): {output}")
    if not (source / "index.html").is_file():
        raise FileNotFoundError(source / "index.html")
    if not tutorial.is_file():
        raise FileNotFoundError(tutorial)
    tutorial_assets = [tutorial.parent / name for name in TUTORIAL_ASSETS]
    for asset in tutorial_assets:
        if not asset.is_file():
            raise FileNotFoundError(asset)

    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(source, output)
    tutorial_target = output / "tutorial" / "index.html"
    tutorial_target.parent.mkdir(parents=True, exist_ok=True)
    tutorial_html = tutorial.read_text(encoding="utf-8")
    tutorial_links = {
        "../README.zh-CN.md": (
            "https://github.com/lianglunping/PanFamFlow/blob/main/README.zh-CN.md"
        ),
        "../README.md": "https://github.com/lianglunping/PanFamFlow/blob/main/README.md",
        "BIOLOGICAL_BENCHMARK.md": (
            "https://github.com/lianglunping/PanFamFlow/blob/main/docs/BIOLOGICAL_BENCHMARK.md"
        ),
        "RESUME.md": "https://github.com/lianglunping/PanFamFlow/blob/main/docs/RESUME.md",
        "SCOPE.md": "https://github.com/lianglunping/PanFamFlow/blob/main/docs/SCOPE.md",
        "CONFIG.md": "https://github.com/lianglunping/PanFamFlow/blob/main/docs/CONFIG.md",
        "EXTERNAL_EVIDENCE_IMPORTS.zh-CN.md": "EXTERNAL_EVIDENCE_IMPORTS.zh-CN.md",
    }
    for source_link, published_link in tutorial_links.items():
        tutorial_html = tutorial_html.replace(f'href="{source_link}"', f'href="{published_link}"')
    tutorial_target.write_text(tutorial_html, encoding="utf-8")
    for asset in tutorial_assets:
        shutil.copy2(asset, tutorial_target.parent / asset.name)
    (output / ".nojekyll").touch()

    published = {item.name for item in output.iterdir()}
    forbidden = sorted(published & FORBIDDEN_TOP_LEVEL)
    if forbidden:
        raise RuntimeError(f"Forbidden top-level Pages content: {forbidden}")

    manifest_lines = ["path\tsize_bytes\tsha256"]
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        relative = path.relative_to(output).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_lines.append(f"{relative}\t{path.stat().st_size}\t{digest}")
    (output / "SITE_MANIFEST.tsv").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    arguments = parse_args()
    build(arguments.source, arguments.tutorial, arguments.output)
