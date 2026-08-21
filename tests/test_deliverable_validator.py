from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from panfamflow.workflow.scripts.artifact_contract import save_figure_pair, save_table_pair
from panfamflow.workflow.scripts.validate_deliverable_contract import evaluate_figure_contract


def _contract_row() -> dict[str, str]:
    return {
        "figure_id": "Fig09",
        "module": "phylogeny",
        "stem": "results/03_phylogeny/Fig09_core_domain_logo",
        "source_table": "results/03_phylogeny/family_domain_segments.tsv",
        "activation": "domain_logo.enabled",
        "missing_input_status": "NOT_REQUESTED",
        "tutorial_anchor": "fig09",
        "scientific_boundary": "Logo is conservation evidence only.",
    }


def test_disabled_missing_figure_is_not_requested(tmp_path: Path) -> None:
    observed = evaluate_figure_contract(
        _contract_row(),
        project_root=tmp_path,
        enabled_features=set(),
    )
    assert observed["status"] == "NOT_REQUESTED"
    assert observed["pdf_sha256"] == ""
    assert observed["png_sha256"] == ""


def test_enabled_missing_figure_is_blocked_input(tmp_path: Path) -> None:
    observed = evaluate_figure_contract(
        _contract_row(),
        project_root=tmp_path,
        enabled_features={"domain_logo.enabled"},
    )
    assert observed["status"] == "BLOCKED_INPUT"
    assert "source table" in observed["reason"]


def test_complete_figure_pair_and_source_table_are_generated(tmp_path: Path) -> None:
    row = _contract_row()
    source_stem = tmp_path / Path(row["source_table"]).with_suffix("")
    save_table_pair(pd.DataFrame({"stable_id": ["SpA__Gene1"]}), source_stem)
    figure, axis = plt.subplots()
    axis.plot([0, 1], [1, 0])
    save_figure_pair(figure, tmp_path / row["stem"], png_dpi=600)

    observed = evaluate_figure_contract(
        row,
        project_root=tmp_path,
        enabled_features={"domain_logo.enabled"},
    )
    assert observed["status"] == "GENERATED"
    assert len(observed["pdf_sha256"]) == 64
    assert len(observed["png_sha256"]) == 64
    assert observed["source_table_status"] == "GENERATED"


def test_half_figure_pair_fails_closed(tmp_path: Path) -> None:
    row = _contract_row()
    pdf = tmp_path / f"{row['stem']}.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF incomplete pair")

    with pytest.raises(ValueError, match="incomplete PDF/PNG pair"):
        evaluate_figure_contract(
            row,
            project_root=tmp_path,
            enabled_features={"domain_logo.enabled"},
        )
