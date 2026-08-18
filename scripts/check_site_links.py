#!/usr/bin/env python3
"""Fail on broken internal links or unsafe content in a built Pages directory."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

FORBIDDEN_TOP_LEVEL = {".git", ".github", "src", "tests", "uv.lock", "results", "work"}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        attribute = "href" if tag in {"a", "link"} else "src" if tag in {"img", "script"} else None
        if attribute and values.get(attribute):
            self.links.append(str(values[attribute]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--base-path", default="/PanFamFlow/")
    return parser.parse_args()


def resolve_internal(site: Path, html_file: Path, raw: str, base_path: str) -> Path | None:
    parsed = urlparse(raw)
    if parsed.scheme in {"https", "mailto"} or raw.startswith("#"):
        return None
    if parsed.scheme == "http":
        raise ValueError(f"Insecure external URL in {html_file}: {raw}")
    path = unquote(parsed.path)
    if path.startswith(base_path):
        target = site / path.removeprefix(base_path)
    elif path.startswith("/"):
        raise ValueError(f"Internal URL misses project base path in {html_file}: {raw}")
    else:
        target = html_file.parent / path
    if path.endswith("/") or target.is_dir():
        target /= "index.html"
    return target.resolve()


def check(site: Path, base_path: str) -> None:
    site = site.resolve()
    required = [site / "index.html", site / "tutorial" / "index.html", site / ".nojekyll"]
    missing_required = [str(path) for path in required if not path.exists()]
    if missing_required:
        raise FileNotFoundError(f"Missing required Pages files: {missing_required}")
    forbidden = sorted(item.name for item in site.iterdir() if item.name in FORBIDDEN_TOP_LEVEL)
    if forbidden:
        raise RuntimeError(f"Forbidden Pages content: {forbidden}")

    errors: list[str] = []
    for html_file in sorted(site.rglob("*.html")):
        parser = LinkParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        for raw in parser.links:
            try:
                target = resolve_internal(site, html_file, raw, base_path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            if target is not None and not target.exists():
                errors.append(f"Broken link in {html_file.relative_to(site)}: {raw}")
    if errors:
        raise RuntimeError("\n".join(errors))


if __name__ == "__main__":
    arguments = parse_args()
    check(arguments.site, arguments.base_path)
