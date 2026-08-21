import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from expression_de_utils import integrate_de_results
from workflow_utils import save_table

members = pd.read_csv(snakemake.input.members, sep="\t", dtype=str)
if members["stable_id"].duplicated().any():
    raise ValueError("Family member table contains duplicate stable_id rows.")
family_ids = sorted(members["stable_id"].astype(str))
raw_results = pd.read_csv(snakemake.input.results, sep="\t")
contrast_audit = pd.read_csv(snakemake.input.contrasts, sep="\t")
vst = pd.read_csv(snakemake.input.vst, sep="\t")
pca = pd.read_csv(snakemake.input.pca, sep="\t")
fit_qc = pd.read_csv(snakemake.input.fit_qc, sep="\t")
design = pd.read_csv(snakemake.input.design, sep="\t", dtype=str)

grid = pd.MultiIndex.from_product(
    [contrast_audit["contrast_id"].astype(str), family_ids],
    names=["contrast_id", "stable_id"],
).to_frame(index=False)
grid = grid.merge(
    contrast_audit[["contrast_id", "dataset_id"]],
    on="contrast_id",
    how="left",
    validate="many_to_one",
)
family_results = grid.merge(
    raw_results,
    on=["dataset_id", "contrast_id", "stable_id"],
    how="left",
    validate="one_to_one",
)
integration, membership = integrate_de_results(
    family_results,
    contrast_audit,
    alpha=float(snakemake.params.alpha),
    lfc_threshold=float(snakemake.params.lfc_threshold),
)
member_metadata = members[
    [
        column
        for column in ("stable_id", "species_id", "gene_id", "subfamily", "group")
        if column in members
    ]
].drop_duplicates("stable_id")
integration = integration.merge(member_metadata, on="stable_id", how="left", validate="many_to_one")
membership = membership.merge(member_metadata, on="stable_id", how="left", validate="many_to_one")

family_vst = vst.loc[vst["stable_id"].astype(str).isin(family_ids)].copy()
family_vst = family_vst.merge(
    design[["dataset_id", "sample_id", "condition", "stress_category", "species_id"]],
    on=["dataset_id", "sample_id"],
    how="left",
    validate="many_to_one",
)
if family_vst[["condition", "stress_category"]].isna().any(axis=None):
    raise ValueError("VST output contains samples absent from the audited design.")
family_vst["vst_value"] = pd.to_numeric(family_vst["vst_value"], errors="coerce")
grouped = family_vst.groupby(["dataset_id", "stable_id"])["vst_value"]
family_vst["within_dataset_gene_zscore"] = grouped.transform(
    lambda values: (
        (values - values.mean()) / values.std(ddof=0)
        if values.notna().sum() > 1 and values.std(ddof=0) > 0
        else pd.Series(0.0, index=values.index)
    )
)
family_vst["comparison_scope"] = "WITHIN_DATASET_SAMPLE_PATTERN_ONLY"

qc_rows = []
for row in fit_qc.to_dict(orient="records"):
    qc_rows.extend(
        [
            {
                "dataset_id": row["dataset_id"],
                "qc_metric": "DESEQ2_FIT",
                "value": row["fit_status"],
                "threshold": "PASS",
                "status": "PASS" if row["fit_status"] == "PASS" else "FAIL",
                "message": "Each dataset is fitted independently.",
            },
            {
                "dataset_id": row["dataset_id"],
                "qc_metric": "DESIGN_RANK",
                "value": f"{row['design_rank']}/{row['design_columns']}",
                "threshold": "FULL_RANK",
                "status": (
                    "PASS" if int(row["design_rank"]) == int(row["design_columns"]) else "FAIL"
                ),
                "message": "Rank deficiency blocks contrast estimation.",
            },
        ]
    )
expression_qc = pd.DataFrame(qc_rows)
if expression_qc["status"].ne("PASS").any():
    raise RuntimeError("At least one formal differential-expression QC row failed.")

tables = (
    (integration, snakemake.output.results, snakemake.output.results_xlsx),
    (family_vst, snakemake.output.vst, snakemake.output.vst_xlsx),
    (family_vst, snakemake.output.stress_matrix, snakemake.output.stress_matrix_xlsx),
    (membership, snakemake.output.deg_membership, snakemake.output.deg_membership_xlsx),
    (integration, snakemake.output.evidence, snakemake.output.evidence_xlsx),
    (pca, snakemake.output.pca, snakemake.output.pca_xlsx),
    (fit_qc, snakemake.output.fit_qc, snakemake.output.fit_qc_xlsx),
    (expression_qc, snakemake.output.qc, snakemake.output.qc_xlsx),
)
for table, tsv, xlsx in tables:
    save_table(table, tsv, xlsx)


def heatmap_panel(axis: plt.Axes, category: str) -> None:
    subset = family_vst.loc[family_vst["stress_category"].astype(str).eq(category)].copy()
    if subset.empty:
        axis.text(0.5, 0.5, f"No eligible {category} dataset", ha="center", va="center")
        axis.set_axis_off()
        return
    matrix = subset.pivot_table(
        index="stable_id",
        columns="sample_id",
        values="within_dataset_gene_zscore",
        aggfunc="first",
    ).reindex(family_ids)
    image = axis.imshow(matrix.to_numpy(dtype=float), aspect="auto", cmap="RdBu_r", vmin=-2, vmax=2)
    axis.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=55, ha="right", fontsize=7)
    axis.set_yticks(range(len(matrix.index)), matrix.index, fontsize=7)
    axis.set_title(
        f"{category.capitalize()} stress: within-dataset VST pattern", loc="left", fontweight="bold"
    )
    axis.grid(False)
    plt.colorbar(image, ax=axis, fraction=0.025, pad=0.02, label="Within-dataset gene z-score")


figure_height = max(12.0, 0.28 * len(family_ids) * 2 + 5.0)
figure, axes = plt.subplots(3, 1, figsize=(13.5, figure_height), facecolor="white")
heatmap_panel(axes[0], "abiotic")
heatmap_panel(axes[1], "biotic")
effect_matrix = integration.pivot_table(
    index="stable_id",
    columns="contrast_id",
    values="log2FoldChange",
    aggfunc="first",
).reindex(family_ids)
if effect_matrix.empty or effect_matrix.shape[1] == 0:
    axes[2].text(0.5, 0.5, "No estimable registered contrast", ha="center", va="center")
    axes[2].set_axis_off()
else:
    finite = effect_matrix.to_numpy(dtype=float)
    finite = finite[np.isfinite(finite)]
    limit = max(1.0, float(np.quantile(np.abs(finite), 0.95))) if finite.size else 1.0
    image = axes[2].imshow(
        effect_matrix.to_numpy(dtype=float),
        aspect="auto",
        cmap="RdBu_r",
        vmin=-limit,
        vmax=limit,
    )
    axes[2].set_xticks(
        range(len(effect_matrix.columns)),
        effect_matrix.columns,
        rotation=55,
        ha="right",
        fontsize=7,
    )
    axes[2].set_yticks(range(len(effect_matrix.index)), effect_matrix.index, fontsize=7)
    axes[2].set_title(
        "Registered contrasts: DESeq2 log2 fold change (BH-FDR stored in source table)",
        loc="left",
        fontweight="bold",
    )
    axes[2].grid(False)
    plt.colorbar(image, ax=axes[2], fraction=0.025, pad=0.02, label="log2 fold change")
figure.suptitle(
    "Stress expression and differential-expression evidence",
    fontweight="bold",
    y=0.995,
)
figure.text(
    0.01,
    0.002,
    "Sample VST patterns, contrast effects and cross-dataset evidence are separate objects; raw counts are never pooled across datasets.",
    fontsize=9,
)
figure.tight_layout(rect=(0, 0.015, 1, 0.985))
figure.savefig(snakemake.output.fig34_pdf, facecolor="white", bbox_inches="tight")
figure.savefig(
    snakemake.output.fig34_png,
    dpi=int(snakemake.params.png_dpi),
    facecolor="white",
    bbox_inches="tight",
)
plt.close(figure)
