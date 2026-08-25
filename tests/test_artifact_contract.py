from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from PIL import Image

from panfamflow.workflow.scripts.artifact_contract import (
    DeliverableStatus,
    artifact_record,
    save_figure_pair,
    save_table_pair,
)


def test_table_pair_has_matching_columns_rows_and_values(tmp_path: Path) -> None:
    table = pd.DataFrame(
        {
            "stable_id": ["SpA__Gene1", "SpB__Gene2"],
            "value": [1.5, None],
            "status": ["GENERATED", "BLOCKED_INPUT"],
        }
    )

    tsv, xlsx = save_table_pair(table, tmp_path / "family_summary")

    from_tsv = pd.read_csv(tsv, sep="\t", na_values=["NA"])
    from_xlsx = pd.read_excel(xlsx)
    pd.testing.assert_frame_equal(from_tsv, from_xlsx, check_dtype=False)


def test_figure_pair_is_pdf_and_600_dpi_png(tmp_path: Path) -> None:
    figure, axis = plt.subplots(figsize=(4, 3))
    axis.plot([0, 1], [0, 1])

    pdf, png = save_figure_pair(figure, tmp_path / "Fig01_demo", png_dpi=600)

    assert pdf.read_bytes().startswith(b"%PDF")
    with Image.open(png) as image:
        dpi = image.info["dpi"]
        assert dpi[0] == pytest.approx(600, abs=1)
        assert dpi[1] == pytest.approx(600, abs=1)


def test_generated_artifact_requires_a_nonempty_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.tsv"
    with pytest.raises(ValueError, match="GENERATED artifact is missing or empty"):
        artifact_record(missing, DeliverableStatus.GENERATED, root=tmp_path)


def test_blocked_artifact_records_reason_without_fake_hash(tmp_path: Path) -> None:
    missing = tmp_path / "Fig34_de.pdf"

    record = artifact_record(
        missing,
        DeliverableStatus.BLOCKED_INPUT,
        root=tmp_path,
        reason="raw integer counts were not configured",
    )

    assert record["relative_path"] == "Fig34_de.pdf"
    assert record["status"] == "BLOCKED_INPUT"
    assert record["sha256"] == ""
    assert record["size_bytes"] == 0
    assert record["reason"] == "raw integer counts were not configured"
