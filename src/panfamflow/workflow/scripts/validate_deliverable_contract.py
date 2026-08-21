"""Validate formal figure contracts without turning missing evidence into success."""

from __future__ import annotations

import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from panfamflow.workflow.scripts.workflow_utils import sha256_file


def _nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _validate_pdf(path: Path) -> None:
    if not path.read_bytes()[:4] == b"%PDF":
        raise ValueError(f"Formal PDF is not parseable by signature: {path}")


def _validate_png(path: Path, minimum_dpi: int = 600) -> None:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Formal PNG has an invalid signature: {path}")
    offset = 8
    dpi: tuple[float, float] | None = None
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        if chunk_type == b"pHYs" and len(payload) == 9 and payload[8] == 1:
            pixels_x, pixels_y = struct.unpack(">II", payload[:8])
            dpi = (pixels_x * 0.0254, pixels_y * 0.0254)
            break
        offset += 12 + length
    if not dpi or min(dpi) < minimum_dpi - 1:
        raise ValueError(f"Formal PNG does not meet {minimum_dpi} dpi: {path}")


def evaluate_figure_contract(
    row: Mapping[str, str],
    *,
    project_root: str | Path,
    enabled_features: set[str],
) -> dict[str, Any]:
    """Evaluate one Fig row and return a truthful manifest record."""

    root = Path(project_root)
    stem = root / row["stem"]
    source = root / row["source_table"]
    pdf = stem.with_suffix(".pdf")
    png = stem.with_suffix(".png")
    pdf_exists = _nonempty(pdf)
    png_exists = _nonempty(png)
    source_exists = _nonempty(source)
    activation = row["activation"]
    enabled = activation in enabled_features

    if pdf_exists != png_exists:
        raise ValueError(f"{row['figure_id']} has an incomplete PDF/PNG pair")
    if (pdf_exists or png_exists) and not enabled:
        raise ValueError(f"{row['figure_id']} exists although {activation} is disabled")

    if pdf_exists and png_exists:
        if not source_exists:
            raise ValueError(f"{row['figure_id']} has figures but its source table is missing")
        _validate_pdf(pdf)
        _validate_png(png)
        status = "GENERATED"
        reason = ""
    elif not enabled:
        status = row["missing_input_status"]
        reason = f"{activation} is disabled"
    elif not source_exists:
        status = "BLOCKED_INPUT"
        reason = f"required source table is missing: {row['source_table']}"
    else:
        status = "BLOCKED_QC"
        reason = "source table exists but the formal PDF/PNG pair was not produced"

    return {
        "figure_id": row["figure_id"],
        "module": row["module"],
        "status": status,
        "activation": activation,
        "pdf_path": str(pdf.relative_to(root)),
        "png_path": str(png.relative_to(root)),
        "source_table": row["source_table"],
        "source_table_status": "GENERATED" if source_exists else "MISSING",
        "pdf_sha256": sha256_file(pdf) if pdf_exists else "",
        "png_sha256": sha256_file(png) if png_exists else "",
        "tutorial_anchor": row["tutorial_anchor"],
        "scientific_boundary": row["scientific_boundary"],
        "reason": reason,
    }
