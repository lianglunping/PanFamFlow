from __future__ import annotations

import re
import runpy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from panfamflow.workflow.scripts.expression_de_utils import (
    audit_de_inputs,
    integrate_de_results,
)

ROOT = Path(__file__).parents[1]
SCRIPT_DIR = ROOT / "src" / "panfamflow" / "workflow" / "scripts"


def _counts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stable_id": ["SpA__G1", "SpA__G2", "SpA__G3"],
            "A_control_1": [100, 40, 10],
            "A_control_2": [110, 42, 12],
            "A_stress_1": [300, 20, 11],
            "A_stress_2": [320, 18, 13],
        }
    )


def _design() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dataset_id": ["DS1"] * 4,
            "sample_id": [
                "A_control_1",
                "A_control_2",
                "A_stress_1",
                "A_stress_2",
            ],
            "species_id": ["SpA"] * 4,
            "condition": ["control", "control", "stress", "stress"],
            "biological_replicate": ["1", "2", "1", "2"],
            "batch": ["B1", "B2", "B1", "B2"],
            "stress_category": ["abiotic"] * 4,
            "evidence_grade": ["VERIFIED_PUBLIC_RAW_COUNTS"] * 4,
            "accession": ["GSE_TOY"] * 4,
            "reference_version": ["toy-v1"] * 4,
            "file_verification_status": ["CHECKSUM_VERIFIED"] * 4,
        }
    )


def _contrasts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contrast_id": ["DS1_stress_vs_control"],
            "dataset_id": ["DS1"],
            "numerator": ["stress"],
            "denominator": ["control"],
            "stress_category": ["abiotic"],
            "is_primary": [True],
        }
    )


def _factorial_design() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for genotype in ("WT", "MUT"):
        for condition in ("Control", "Stress"):
            for replicate in ("1", "2", "3"):
                rows.append(
                    {
                        "dataset_id": "DS_FACTORIAL",
                        "sample_id": f"{genotype}_{condition}_{replicate}",
                        "species_id": "SpA",
                        "condition": condition,
                        "genotype": genotype,
                        "biological_replicate": replicate,
                        "batch": "B1",
                        "stress_category": "abiotic",
                        "evidence_grade": "VERIFIED_PUBLIC_RAW_COUNTS",
                        "accession": "GSE_FACTORIAL",
                        "reference_version": "IRGSP-1.0.63",
                        "file_verification_status": "CHECKSUM_VERIFIED",
                    }
                )
    return pd.DataFrame(rows)


def _factorial_counts() -> pd.DataFrame:
    design = _factorial_design()
    values: dict[str, list[int] | list[str]] = {"stable_id": ["G1", "G2"]}
    for index, sample_id in enumerate(design["sample_id"]):
        values[sample_id] = [100 + index, 50 + index]
    return pd.DataFrame(values)


def _factorial_contrasts() -> pd.DataFrame:
    common = {
        "dataset_id": "DS_FACTORIAL",
        "design_formula": "~ genotype + condition + genotype:condition",
        "factor": "condition",
        "numerator": "Stress",
        "denominator": "Control",
        "context_factor": "genotype",
        "minimum_replicates": 3,
        "stress_category": "abiotic",
        "is_primary": True,
    }
    return pd.DataFrame(
        [
            {
                **common,
                "contrast_id": "WT_Stress_vs_Control",
                "contrast_type": "simple_effect",
                "context_numerator": "WT",
                "context_denominator": "",
            },
            {
                **common,
                "contrast_id": "MUT_Stress_vs_Control",
                "contrast_type": "simple_effect",
                "context_numerator": "MUT",
                "context_denominator": "",
            },
            {
                **common,
                "contrast_id": "Stress_response_interaction",
                "contrast_type": "interaction",
                "context_numerator": "MUT",
                "context_denominator": "WT",
            },
        ]
    )


def test_raw_count_audit_requires_integer_counts_registered_contrast_and_replicates() -> None:
    audited = audit_de_inputs(_counts(), _design(), _contrasts(), min_replicates=2)

    assert audited.dataset_audit.loc[0, "dataset_status"] == "PASS"
    assert audited.contrast_audit.loc[0, "contrast_status"] == "PASS"
    assert audited.contrast_audit.loc[0, "numerator_replicates"] == 2
    assert audited.contrast_audit.loc[0, "design_rank_status"] == "FULL_RANK"
    assert audited.sample_qc["include_in_de"].all()


def test_fractional_counts_are_rejected_before_deseq2() -> None:
    counts = _counts()
    counts["A_control_1"] = counts["A_control_1"].astype(float)
    counts.loc[0, "A_control_1"] = 1.5

    with pytest.raises(ValueError, match="integer raw counts"):
        audit_de_inputs(counts, _design(), _contrasts(), min_replicates=2)


def test_insufficient_replicates_are_rejected_before_deseq2() -> None:
    counts = _counts().drop(columns="A_stress_2")
    design = _design().loc[_design()["sample_id"].ne("A_stress_2")].copy()

    with pytest.raises(ValueError, match="fewer than 2 biological replicates"):
        audit_de_inputs(counts, design, _contrasts(), min_replicates=2)


def test_confounded_batch_and_condition_are_rejected_as_rank_deficient() -> None:
    design = _design()
    design["batch"] = ["control_batch", "control_batch", "stress_batch", "stress_batch"]

    with pytest.raises(ValueError, match="rank deficient"):
        audit_de_inputs(_counts(), design, _contrasts(), min_replicates=2)


def test_factorial_design_audits_simple_effects_and_interaction_cells() -> None:
    audited = audit_de_inputs(
        _factorial_counts(),
        _factorial_design(),
        _factorial_contrasts(),
        min_replicates=2,
    )

    assert audited.dataset_audit.loc[0, "design_formula"] == (
        "~ genotype + condition + genotype:condition"
    )
    assert audited.dataset_audit.loc[0, "design_rank"] == 4
    assert audited.dataset_audit.loc[0, "design_columns"] == 4
    assert audited.contrast_audit["numerator_replicates"].tolist() == [3, 3, 3]
    assert audited.contrast_audit["denominator_replicates"].tolist() == [3, 3, 3]
    assert audited.contrast_audit["contrast_status"].eq("PASS").all()
    assert "genotype" in audited.design.columns


def test_factorial_interaction_rejects_unknown_context_level() -> None:
    contrasts = _factorial_contrasts()
    contrasts.loc[contrasts["contrast_type"].eq("interaction"), "context_denominator"] = "UNKNOWN"

    with pytest.raises(ValueError, match="context level UNKNOWN"):
        audit_de_inputs(
            _factorial_counts(),
            _factorial_design(),
            contrasts,
            min_replicates=2,
        )


def test_result_integration_keeps_effect_fdr_and_cross_dataset_direction_separate() -> None:
    audited = audit_de_inputs(_counts(), _design(), _contrasts(), min_replicates=2)
    results = pd.DataFrame(
        {
            "dataset_id": ["DS1", "DS1"],
            "contrast_id": ["DS1_stress_vs_control"] * 2,
            "stable_id": ["SpA__G1", "SpA__G2"],
            "baseMean": [200.0, 30.0],
            "log2FoldChange": [1.5, -1.2],
            "lfcSE": [0.2, 0.3],
            "stat": [7.5, -4.0],
            "pvalue": [1e-8, 1e-4],
            "padj": [2e-7, 8e-4],
        }
    )
    integrated, membership = integrate_de_results(
        results,
        audited.contrast_audit,
        alpha=0.05,
        lfc_threshold=1.0,
    )

    assert membership["deg_status"].tolist() == ["UP", "DOWN"]
    assert integrated["effect_direction"].tolist() == ["UP", "DOWN"]
    assert integrated["evidence_grade"].eq("VERIFIED_PUBLIC_RAW_COUNTS").all()
    assert integrated["integration_status"].eq("SINGLE_DATASET_EVIDENCE").all()


def test_expression_rule_declares_containerized_deseq2_and_fig34_contract() -> None:
    rule = (ROOT / "src" / "panfamflow" / "workflow" / "rules" / "expression.smk").read_text(
        encoding="utf-8"
    )
    r_script = (ROOT / "src" / "panfamflow" / "workflow" / "scripts" / "run_deseq2.R").read_text(
        encoding="utf-8"
    )
    assert "rule audit_differential_expression_inputs:" in rule
    assert "rule run_deseq2:" in rule
    assert "rule integrate_differential_expression:" in rule
    assert "expression_de_container" in rule
    assert "Fig34_stress_expression_and_comparison.pdf" in rule
    assert "DESeqDataSetFromMatrix" in r_script
    assert "DESeq2" in r_script


def test_deseq2_low_dispersion_fallback_is_exact_and_auditable() -> None:
    r_script = (ROOT / "src" / "panfamflow" / "workflow" / "scripts" / "run_deseq2.R").read_text(
        encoding="utf-8"
    )

    assert "all gene-wise dispersion estimates are within 2 orders" in r_script
    assert "estimateDispersionsGeneEst" in r_script
    assert re.search(r"dispersions\((\w+)\) <- mcols\(\1\)\$dispGeneEst", r_script)
    assert "nbinomWaldTest" in r_script
    assert "dispersion_fit_method" in r_script
    assert "fallback_reason" in r_script


def test_deseq2_factorial_contrasts_are_explicit_numeric_vectors() -> None:
    r_script = (ROOT / "src" / "panfamflow" / "workflow" / "scripts" / "run_deseq2.R").read_text(
        encoding="utf-8"
    )

    assert "contrast_type" in r_script
    assert "context_factor" in r_script
    assert "model.matrix" in r_script
    assert "contrast_vector" in r_script
    assert "results(dds, contrast = contrast_vector" in r_script
    assert not re.search(r"results\(dds\s*\)", r_script)


def test_fig34_integration_executes_without_treating_missing_fit_rows_as_zero(
    tmp_path: Path,
) -> None:
    audited = audit_de_inputs(_counts(), _design(), _contrasts(), min_replicates=2)
    paths = {
        "members": tmp_path / "members.tsv",
        "results": tmp_path / "r_results.tsv",
        "vst": tmp_path / "r_vst.tsv",
        "pca": tmp_path / "r_pca.tsv",
        "fit_qc": tmp_path / "r_fit_qc.tsv",
        "design": tmp_path / "design.tsv",
        "contrasts": tmp_path / "contrasts.tsv",
    }
    pd.DataFrame(
        {
            "stable_id": ["SpA__G1", "SpA__G2", "SpA__G3"],
            "species_id": ["SpA"] * 3,
            "gene_id": ["G1", "G2", "G3"],
            "subfamily": ["A", "A", "B"],
            "group": ["indica"] * 3,
        }
    ).to_csv(paths["members"], sep="\t", index=False)
    pd.DataFrame(
        {
            "dataset_id": ["DS1", "DS1"],
            "contrast_id": ["DS1_stress_vs_control"] * 2,
            "stable_id": ["SpA__G1", "SpA__G2"],
            "baseMean": [200.0, 30.0],
            "log2FoldChange": [1.5, -1.2],
            "lfcSE": [0.2, 0.3],
            "stat": [7.5, -4.0],
            "pvalue": [1e-8, 1e-4],
            "padj": [2e-7, 8e-4],
        }
    ).to_csv(paths["results"], sep="\t", index=False)
    vst_rows = []
    for gene_index, stable_id in enumerate(("SpA__G1", "SpA__G2", "SpA__G3")):
        for sample_index, sample_id in enumerate(_design()["sample_id"]):
            vst_rows.append(
                {
                    "dataset_id": "DS1",
                    "stable_id": stable_id,
                    "sample_id": sample_id,
                    "vst_value": 5 + gene_index + sample_index * 0.2,
                }
            )
    pd.DataFrame(vst_rows).to_csv(paths["vst"], sep="\t", index=False)
    pd.DataFrame(
        {
            "dataset_id": ["DS1"] * 4,
            "sample_id": _design()["sample_id"],
            "PC1": [-2, -1, 1, 2],
            "PC2": [0.2, -0.2, 0.1, -0.1],
            "PC1_variance_fraction": [0.7] * 4,
            "PC2_variance_fraction": [0.2] * 4,
        }
    ).to_csv(paths["pca"], sep="\t", index=False)
    pd.DataFrame(
        {
            "dataset_id": ["DS1"],
            "input_gene_count": [3],
            "fitted_gene_count": [2],
            "sample_count": [4],
            "design_formula": ["~batch+condition"],
            "design_rank": [3],
            "design_columns": [3],
            "fit_status": ["PASS"],
            "independent_dataset_fit": [True],
        }
    ).to_csv(paths["fit_qc"], sep="\t", index=False)
    audited.design.to_csv(paths["design"], sep="\t", index=False)
    audited.contrast_audit.to_csv(paths["contrasts"], sep="\t", index=False)

    result_dir = tmp_path / "integrated"
    output_names = (
        "results",
        "results_xlsx",
        "vst",
        "vst_xlsx",
        "stress_matrix",
        "stress_matrix_xlsx",
        "deg_membership",
        "deg_membership_xlsx",
        "evidence",
        "evidence_xlsx",
        "pca",
        "pca_xlsx",
        "fit_qc",
        "fit_qc_xlsx",
        "qc",
        "qc_xlsx",
        "fig34_pdf",
        "fig34_png",
    )
    output = SimpleNamespace(
        **{
            name: result_dir
            / (
                f"{name}.xlsx"
                if name.endswith("xlsx")
                else f"{name}.pdf"
                if name.endswith("pdf")
                else f"{name}.png"
                if name.endswith("png")
                else f"{name}.tsv"
            )
            for name in output_names
        }
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(**paths),
        output=output,
        params=SimpleNamespace(alpha=0.05, lfc_threshold=1.0, png_dpi=72),
    )
    runpy.run_path(
        str(SCRIPT_DIR / "integrate_expression_evidence.py"),
        init_globals={"snakemake": fake},
    )

    membership = pd.read_csv(output.deg_membership, sep="\t")
    assert membership.set_index("stable_id").loc["SpA__G3", "deg_status"] == (
        "UNTESTED_LOW_INFORMATION"
    )
    assert all(
        Path(path).is_file() and Path(path).stat().st_size > 0 for path in vars(output).values()
    )
