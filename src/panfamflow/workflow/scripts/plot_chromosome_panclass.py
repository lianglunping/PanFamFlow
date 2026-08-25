import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import math

import matplotlib.pyplot as plt
import pandas as pd
from workflow_utils import save_table

distribution = pd.read_csv(snakemake.input.distribution, sep="\t", dtype=str)
membership = pd.read_csv(snakemake.input.membership, sep="\t", dtype=str)
classification = pd.read_csv(snakemake.input.classification, sep="\t", dtype=str)
if distribution["stable_id"].duplicated().any():
    raise ValueError("Chromosome distribution contains duplicate stable_id rows.")
if membership["stable_id"].duplicated().any():
    raise ValueError("HOG membership contains duplicate stable_id assignments.")
if classification["HOG_ID"].duplicated().any():
    raise ValueError("Pan-family classification contains duplicate HOG_ID rows.")

annotation = membership[["stable_id", "HOG_ID"]].merge(
    classification[["HOG_ID", "pan_family_class"]],
    on="HOG_ID",
    how="left",
    validate="many_to_one",
)
annotated = distribution.merge(annotation, on="stable_id", how="left", validate="one_to_one")
annotated["pan_family_class"] = annotated["pan_family_class"].fillna("Unassigned")
annotated["pan_class_assignment_status"] = (
    annotated["HOG_ID"]
    .notna()
    .map({True: "ASSIGNED_SELECTED_HOG_NODE", False: "UNASSIGNED_SELECTED_HOG_NODE"})
)
annotated["interpretation_flag"] = "ANNOTATION_OCCUPANCY_NOT_VALIDATED_GENE_LOSS"
save_table(annotated, snakemake.output.annotated)

valid = annotated.loc[annotated["coordinate_qc"].eq("PASS")].copy()
valid["midpoint"] = pd.to_numeric(valid["midpoint"], errors="coerce")
valid = valid.loc[valid["midpoint"].notna()].copy()
if valid.empty:
    raise RuntimeError("Fig15 requires at least one valid chromosome coordinate.")

class_colors = {
    "Core": "#D55E00",
    "Soft-core": "#E69F00",
    "Shell": "#009E73",
    "Cloud": "#56B4E9",
    "Unassigned": "#999999",
}
markers = ["o", "s", "^", "D", "P", "X", "v", "<", ">"]
subfamilies = sorted(valid["subfamily"].fillna("Unassigned").astype(str).unique())
marker_by_subfamily = {
    subfamily: markers[index % len(markers)] for index, subfamily in enumerate(subfamilies)
}
species_order = list(dict.fromkeys(valid["species_id"].astype(str)))
n_columns = min(2, len(species_order))
n_rows = math.ceil(len(species_order) / n_columns)
figure, axes = plt.subplots(
    n_rows,
    n_columns,
    figsize=(8.2 * n_columns, 4.2 * n_rows),
    squeeze=False,
    facecolor="white",
)
for axis, species in zip(axes.ravel(), species_order, strict=False):
    subset = valid.loc[valid["species_id"].astype(str).eq(species)].copy()
    chromosomes = sorted(
        subset["chromosome"].astype(str).unique(), key=lambda value: (len(value), value)
    )
    y_lookup = {chromosome: index for index, chromosome in enumerate(chromosomes)}
    for (pan_class, subfamily), group in subset.groupby(
        ["pan_family_class", "subfamily"], dropna=False
    ):
        subfamily_label = str(subfamily) if pd.notna(subfamily) else "Unassigned"
        axis.scatter(
            group["midpoint"] / 1_000_000,
            group["chromosome"].astype(str).map(y_lookup),
            color=class_colors.get(str(pan_class), "#999999"),
            marker=marker_by_subfamily[subfamily_label],
            s=42,
            alpha=0.9,
            label=f"{pan_class} | {subfamily_label}",
        )
    axis.set_yticks(range(len(chromosomes)), chromosomes)
    axis.set_xlabel("Position (Mb; species-specific physical coordinates)")
    axis.set_ylabel("Chromosome")
    axis.set_title(species, loc="left", fontweight="bold")
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(False)
for axis in axes.ravel()[len(species_order) :]:
    axis.set_axis_off()
handles, labels = axes.ravel()[0].get_legend_handles_labels()
if handles:
    figure.legend(handles, labels, frameon=False, bbox_to_anchor=(1.01, 1), loc="upper left")
figure.suptitle("Target-family chromosome positions by pan class and subfamily")
figure.tight_layout(rect=(0, 0, 0.88, 0.96))
figure.savefig(snakemake.output.fig15_pdf, facecolor="white", bbox_inches="tight")
figure.savefig(
    snakemake.output.fig15_png,
    dpi=int(snakemake.params.png_dpi),
    facecolor="white",
    bbox_inches="tight",
)
plt.close(figure)
