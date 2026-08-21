"""Shared table, figure and manifest contracts for formal deliverables."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from panfamflow.workflow.scripts.workflow_utils import (
    commit_partial,
    partial_path,
    save_table,
    sha256_file,
)

if TYPE_CHECKING:
    import pandas as pd
    from matplotlib.figure import Figure


class DeliverableStatus(StrEnum):
    GENERATED = "GENERATED"
    BLOCKED_INPUT = "BLOCKED_INPUT"
    BLOCKED_QC = "BLOCKED_QC"
    NOT_REQUESTED = "NOT_REQUESTED"
    EXTERNAL_REQUIRED = "EXTERNAL_REQUIRED"


def save_table_pair(table: pd.DataFrame, stem: str | Path) -> tuple[Path, Path]:
    """Atomically write one authoritative table as matching TSV and XLSX files."""

    output_stem = Path(stem)
    tsv = output_stem.with_suffix(".tsv")
    xlsx = output_stem.with_suffix(".xlsx")
    save_table(table, tsv, xlsx)
    return tsv, xlsx


def save_figure_pair(
    figure: Figure,
    stem: str | Path,
    *,
    png_dpi: int = 600,
) -> tuple[Path, Path]:
    """Atomically write a vector PDF and white-background high-resolution PNG."""

    if png_dpi < 72:
        raise ValueError("png_dpi must be at least 72")
    output_stem = Path(stem)
    pdf = output_stem.with_suffix(".pdf")
    png = output_stem.with_suffix(".png")
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf_temporary = partial_path(pdf)
    png_temporary = partial_path(png)
    try:
        figure.savefig(pdf_temporary, format="pdf", bbox_inches="tight", facecolor="white")
        figure.savefig(
            png_temporary,
            format="png",
            dpi=png_dpi,
            bbox_inches="tight",
            facecolor="white",
        )
        if pdf_temporary.stat().st_size == 0 or png_temporary.stat().st_size == 0:
            raise RuntimeError(f"Figure export produced an empty file for stem: {output_stem}")
        commit_partial(pdf_temporary, pdf)
        commit_partial(png_temporary, png)
    except Exception:
        pdf_temporary.unlink(missing_ok=True)
        png_temporary.unlink(missing_ok=True)
        raise
    return pdf, png


def artifact_record(
    path: str | Path,
    status: DeliverableStatus,
    *,
    root: str | Path,
    reason: str = "",
    artifact_id: str = "",
    source_table: str = "",
) -> dict[str, Any]:
    """Return one truthful manifest row; generated artifacts must exist."""

    artifact = Path(path)
    root_path = Path(root)
    exists = artifact.is_file() and artifact.stat().st_size > 0
    if status is DeliverableStatus.GENERATED and not exists:
        raise ValueError(f"GENERATED artifact is missing or empty: {artifact}")
    if status is not DeliverableStatus.GENERATED and not reason:
        raise ValueError(f"{status.value} artifact requires a reason: {artifact}")
    try:
        relative = artifact.relative_to(root_path)
    except ValueError:
        relative = artifact
    return {
        "artifact_id": artifact_id,
        "relative_path": str(relative),
        "status": status.value,
        "size_bytes": artifact.stat().st_size if exists else 0,
        "sha256": sha256_file(artifact) if exists else "",
        "suffix": artifact.suffix.lower(),
        "source_table": source_table,
        "reason": reason,
    }
