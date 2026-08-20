from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPT_DIR = Path(__file__).parents[1] / "src" / "panfamflow" / "workflow" / "scripts"
MODULE_PATH = SCRIPT_DIR / "gene_structure_statistics.py"


def load_module():
    assert MODULE_PATH.is_file(), "gene-structure statistics module has not been implemented"
    spec = importlib.util.spec_from_file_location("gene_structure_statistics", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_benjamini_hochberg_adjusts_within_one_test_family() -> None:
    module = load_module()

    adjusted = module.benjamini_hochberg([0.01, 0.04, 0.03, 1.0])

    assert adjusted == pytest.approx([0.04, 0.0533333333, 0.0533333333, 1.0])


def test_group_comparison_uses_species_medians_and_reports_effect_direction() -> None:
    module = load_module()
    table = pd.DataFrame(
        {
            "stable_id": [f"A{i}" for i in range(4)] + [f"B{i}" for i in range(4)],
            "species_id": [f"Sp{i}" for i in range(4)] * 2,
            "structure_qc": ["PASS"] * 8,
            "subfamily": ["A"] * 4 + ["B"] * 4,
            "gene_length": [1.0, 2.0, 1.5, 2.5, 10.0, 11.0, 12.0, 9.0],
        }
    )

    global_tests, pairwise, qc = module.compare_grouped_metrics(
        table,
        group_field="subfamily",
        metrics=["gene_length"],
        min_group_units=2,
        alpha=0.05,
    )

    assert global_tests.loc[0, "analysis_unit"] == "SPECIES_MEDIAN"
    assert global_tests.loc[0, "test_name"] == "Kruskal-Wallis"
    assert global_tests.loc[0, "p_value"] < 0.05
    assert pairwise.loc[0, "test_name"] == "Mann-Whitney U"
    assert pairwise.loc[0, "test_status"] == "PASS"
    assert pairwise.loc[0, "rank_biserial_effect"] == pytest.approx(-1.0)
    assert pairwise.loc[0, "p_adjusted_bh"] == pytest.approx(pairwise.loc[0, "p_value"])
    assert pairwise.loc[0, "n_genes_1"] == 4
    assert pairwise.loc[0, "n_species_1"] == 4
    assert qc.loc[0, "eligible_species_group_units"] == 8


def test_group_comparison_with_one_species_per_group_withholds_p_values() -> None:
    module = load_module()
    table = pd.DataFrame(
        {
            "stable_id": ["A1", "A2", "B1", "B2"],
            "species_id": ["SpA", "SpA", "SpB", "SpB"],
            "structure_qc": ["PASS"] * 4,
            "group": ["Cultivated", "Cultivated", "Wild", "Wild"],
            "exon_count": [2, 3, 8, 9],
        }
    )

    global_tests, pairwise, qc = module.compare_grouped_metrics(
        table,
        group_field="group",
        metrics=["exon_count"],
        min_group_units=2,
        alpha=0.05,
    )

    assert global_tests.loc[0, "test_status"] == "INSUFFICIENT_GROUP_UNITS"
    assert pd.isna(global_tests.loc[0, "p_value"])
    assert pairwise.loc[0, "test_status"] == "INSUFFICIENT_GROUP_UNITS"
    assert pairwise.loc[0, "inference_warning"] == "INSUFFICIENT_SPECIES_REPLICATION"
    assert pd.isna(pairwise.loc[0, "p_value"])
    assert qc.loc[0, "inference_warning"] == "INSUFFICIENT_SPECIES_REPLICATION"


def test_group_comparison_rejects_conflicting_stable_id_assignments() -> None:
    module = load_module()
    table = pd.DataFrame(
        {
            "stable_id": ["SpA__Gene1", "SpA__Gene1"],
            "species_id": ["SpA", "SpA"],
            "structure_qc": ["PASS", "PASS"],
            "subfamily": ["A", "B"],
            "gene_length": [100, 100],
        }
    )

    with pytest.raises(ValueError, match="conflicting subfamily assignments"):
        module.compare_grouped_metrics(
            table,
            group_field="subfamily",
            metrics=["gene_length"],
            min_group_units=2,
            alpha=0.05,
        )


def test_group_comparison_plot_writes_pdf_and_png(tmp_path: Path) -> None:
    module = load_module()
    table = pd.DataFrame(
        {
            "stable_id": ["A1", "A2", "B1", "B2"],
            "species_id": ["Sp1", "Sp2", "Sp1", "Sp2"],
            "structure_qc": ["PASS"] * 4,
            "subfamily": ["A", "A", "B", "B"],
            "gene_length": [100, 120, 300, 320],
        }
    )
    pdf = tmp_path / "comparisons.pdf"
    png = tmp_path / "comparisons.png"

    module.plot_grouped_metrics(
        table,
        group_fields=["subfamily"],
        metrics=["gene_length"],
        pdf_path=pdf,
        png_path=png,
        png_dpi=120,
        seed=20260807,
    )

    assert pdf.stat().st_size > 1000
    assert png.stat().st_size > 1000


def test_panel_inference_note_exposes_withheld_and_zero_variance_states() -> None:
    module = load_module()

    withheld = module.describe_panel_inference([[2.0], [8.0]], min_group_units=2)
    zero_variance = module.describe_panel_inference([[3.0, 3.0], [3.0, 3.0]], min_group_units=2)

    assert "Inference withheld" in withheld
    assert "<2 species units" in withheld
    assert "No between-unit variation" in zero_variance
