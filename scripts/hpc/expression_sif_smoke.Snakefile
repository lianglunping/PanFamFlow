"""Run the two-dataset DESeq2 fixture against a pre-verified SIF cache."""

from pathlib import Path


SMOKE_ROOT = str(Path(config["smoke_root"]).resolve())
EXPRESSION_IMAGE = (
    "docker://ghcr.io/lianglunping/panfamflow-expression-de"
    "@sha256:57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29"
)


rule all:
    input:
        f"{SMOKE_ROOT}/deseq2_all_results.tsv",
        f"{SMOKE_ROOT}/expression_vst_long.tsv",
        f"{SMOKE_ROOT}/deseq2_sample_pca.tsv",
        f"{SMOKE_ROOT}/deseq2_fit_qc.tsv",
        f"{SMOKE_ROOT}/deseq2_session_info.txt",


rule smoke_two_datasets:
    input:
        counts="examples/toy_complete/references/raw_counts.tsv",
        design="examples/toy_complete/references/de_design.tsv",
        contrasts="examples/toy_complete/references/de_contrasts.tsv",
    output:
        results=f"{SMOKE_ROOT}/deseq2_all_results.tsv",
        vst=f"{SMOKE_ROOT}/expression_vst_long.tsv",
        pca=f"{SMOKE_ROOT}/deseq2_sample_pca.tsv",
        fit_qc=f"{SMOKE_ROOT}/deseq2_fit_qc.tsv",
        session=f"{SMOKE_ROOT}/deseq2_session_info.txt",
    params:
        alpha=0.05,
        min_total_count=10,
    container:
        EXPRESSION_IMAGE
    script:
        "../../src/panfamflow/workflow/scripts/run_deseq2.R"
