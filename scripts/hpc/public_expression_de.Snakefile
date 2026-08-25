"""Audit and fit the two frozen public rice 2x2 factorial experiments."""

from pathlib import Path


PUBLIC_ROOT = Path(config["public_root"]).resolve()
COUNTS = str(PUBLIC_ROOT / "counts" / "raw_counts.tsv")
AUDIT_ROOT = PUBLIC_ROOT / "de" / "audit"
DE_ROOT = PUBLIC_ROOT / "de" / "model"
EXPRESSION_IMAGE = (
    "docker://ghcr.io/lianglunping/panfamflow-expression-de"
    "@sha256:57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29"
)


rule all:
    input:
        str(DE_ROOT / "deseq2_all_results.tsv"),
        str(DE_ROOT / "expression_vst_long.tsv"),
        str(DE_ROOT / "deseq2_sample_pca.tsv"),
        str(DE_ROOT / "deseq2_fit_qc.tsv"),
        str(DE_ROOT / "deseq2_session_info.txt"),


rule audit_public_de_inputs:
    input:
        counts=COUNTS,
        design="examples/public_rice_expression/de_design.tsv",
        contrasts="examples/public_rice_expression/contrasts.tsv",
    output:
        counts=str(AUDIT_ROOT / "raw_counts.tsv"),
        counts_xlsx=str(AUDIT_ROOT / "raw_counts.xlsx"),
        design=str(AUDIT_ROOT / "de_design_audit.tsv"),
        design_xlsx=str(AUDIT_ROOT / "de_design_audit.xlsx"),
        contrasts=str(AUDIT_ROOT / "de_contrast_audit.tsv"),
        contrasts_xlsx=str(AUDIT_ROOT / "de_contrast_audit.xlsx"),
        datasets=str(AUDIT_ROOT / "expression_dataset_audit.tsv"),
        datasets_xlsx=str(AUDIT_ROOT / "expression_dataset_audit.xlsx"),
        sample_qc=str(AUDIT_ROOT / "expression_sample_qc.tsv"),
        sample_qc_xlsx=str(AUDIT_ROOT / "expression_sample_qc.xlsx"),
    params:
        min_replicates=3,
    script:
        "../../src/panfamflow/workflow/scripts/audit_expression_datasets.py"


rule run_public_deseq2:
    input:
        counts=rules.audit_public_de_inputs.output.counts,
        design=rules.audit_public_de_inputs.output.design,
        contrasts=rules.audit_public_de_inputs.output.contrasts,
    output:
        results=str(DE_ROOT / "deseq2_all_results.tsv"),
        vst=str(DE_ROOT / "expression_vst_long.tsv"),
        pca=str(DE_ROOT / "deseq2_sample_pca.tsv"),
        fit_qc=str(DE_ROOT / "deseq2_fit_qc.tsv"),
        session=str(DE_ROOT / "deseq2_session_info.txt"),
    params:
        alpha=0.05,
        min_total_count=10,
    container:
        EXPRESSION_IMAGE
    script:
        "../../src/panfamflow/workflow/scripts/run_deseq2.R"
