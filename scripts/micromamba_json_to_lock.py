#!/usr/bin/env python3
"""Convert a micromamba dry-run JSON solve into an auditable explicit lock."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def solved_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions = payload.get("actions", {})
    # LINK is the complete solved prefix. FETCH can omit packages already in
    # the local cache, so it must never be used preferentially for a lock.
    records = actions.get("LINK") or actions.get("FETCH") or []
    if not records:
        raise ValueError("Micromamba JSON contains no solved package records.")
    return sorted(
        records, key=lambda record: (str(record.get("name", "")), str(record.get("fn", "")))
    )


def package_url(record: dict[str, Any]) -> str:
    if record.get("url"):
        return str(record["url"])
    channel = str(record.get("channel") or record.get("base_url") or "").rstrip("/")
    filename = str(record.get("fn") or "")
    if not channel or not filename:
        raise ValueError(f"Solved package lacks a reconstructable URL: {record}")
    return f"{channel}/{filename}"


def write_lock(payload: dict[str, Any], lock_path: Path, receipt_path: Path) -> None:
    records = solved_records(payload)
    lock_lines = ["@EXPLICIT"]
    receipt_lines = ["name\tversion\tbuild\tfilename\tsha256\turl"]
    for record in records:
        url = package_url(record)
        sha256 = str(record.get("sha256") or "")
        if sha256:
            url = f"{url}#{sha256}"
        lock_lines.append(url)
        receipt_lines.append(
            "\t".join(
                str(record.get(field) or "")
                for field in ("name", "version", "build_string", "fn", "sha256")
            )
            + "\t"
            + package_url(record)
        )
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("\n".join(lock_lines) + "\n", encoding="utf-8")
    receipt_path.write_text("\n".join(receipt_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("solve_json", type=Path)
    parser.add_argument("lock_path", type=Path)
    parser.add_argument("receipt_path", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.solve_json.read_text(encoding="utf-8"))
    write_lock(payload, args.lock_path, args.receipt_path)


if __name__ == "__main__":
    main()
