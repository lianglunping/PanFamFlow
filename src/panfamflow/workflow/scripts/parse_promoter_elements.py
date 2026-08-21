import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from promoter_distribution_utils import (
    attach_pan_family_class,
    build_promoter_distributions,
    build_promoter_hog_distributions,
)
from workflow_utils import read_delimited_table, resolve_column, save_table, save_workbook

backend = str(snakemake.params.backend)
coordinates = pd.read_csv(snakemake.input.coordinates, sep="\t")
if backend == "fimo":
    fimo_path = Path(snakemake.input.fimo)
    if not fimo_path.is_file():
        raise FileNotFoundError(f"FIMO table not found: {fimo_path}")
    fimo = pd.read_csv(fimo_path, sep="\t", comment="#")
    if fimo.empty:
        elements = pd.DataFrame(
            columns=[
                "stable_id",
                "element",
                "motif_alt_id",
                "sequence_start",
                "sequence_stop",
                "strand",
                "score",
                "p_value",
                "q_value",
                "matched_sequence",
            ]
        )
    else:
        sequence_column = resolve_column(fimo, ["sequence_name", "sequence"])
        motif_column = resolve_column(fimo, ["motif_id", "motif"])
        rename = {
            sequence_column: "stable_id",
            motif_column: "element",
            "motif_alt_id": "motif_alt_id",
            "start": "sequence_start",
            "stop": "sequence_stop",
            "strand": "strand",
            "score": "score",
            "p-value": "p_value",
            "q-value": "q_value",
            "matched_sequence": "matched_sequence",
        }
        elements = fimo.rename(columns={key: value for key, value in rename.items() if key in fimo})
        keep = [
            "stable_id",
            "element",
            "motif_alt_id",
            "sequence_start",
            "sequence_stop",
            "strand",
            "score",
            "p_value",
            "q_value",
            "matched_sequence",
        ]
        for column in keep:
            if column not in elements.columns:
                elements[column] = pd.NA
        elements = elements[keep]
else:
    source = read_delimited_table(snakemake.params.precomputed_table)
    stable_column = resolve_column(source, ["stable_id", "sequence_id"], required=False)
    element_column = resolve_column(source, ["element", "motif_id", "cis_element"])
    if stable_column is not None:
        elements = source.rename(columns={stable_column: "stable_id", element_column: "element"})
    else:
        gene_column = resolve_column(source, ["gene_id", "gene"])
        species_column = resolve_column(source, ["species_id", "species"], required=False)
        elements = source.rename(columns={element_column: "element"}).copy()
        if species_column is not None:
            separator = str(snakemake.params.separator)
            elements["stable_id"] = [
                f"{species}{separator}{gene}"
                for species, gene in zip(
                    source[species_column].astype(str),
                    source[gene_column].astype(str),
                    strict=True,
                )
            ]
        else:
            lookup = coordinates.groupby("gene_id")["stable_id"].agg(list).to_dict()
            raw_gene_ids = source[gene_column].astype(str)
            ambiguous = [gene for gene in raw_gene_ids if len(lookup.get(gene, [])) != 1]
            if ambiguous:
                raise ValueError(
                    "Precomputed promoter IDs are not stable IDs and are not uniquely mappable "
                    f"gene IDs. Examples: {ambiguous[:10]}"
                )
            elements["stable_id"] = [lookup[gene][0] for gene in raw_gene_ids]

elements["stable_id"] = elements["stable_id"].astype(str)
known_promoters = set(coordinates["stable_id"].astype(str))
unknown_promoters = sorted(set(elements["stable_id"]).difference(known_promoters))
if unknown_promoters:
    raise ValueError(
        "Promoter-element table contains IDs absent from extracted family promoters. Examples: "
        + ", ".join(unknown_promoters[:10])
    )

category_path = str(snakemake.params.category_map or "").strip()
if category_path:
    categories = read_delimited_table(category_path)
    motif_column = resolve_column(categories, ["element", "motif_id", "cis_element"])
    categories = categories.rename(columns={motif_column: "element"})
    elements = elements.merge(categories, on="element", how="left", validate="many_to_one")
if "major_class" not in elements.columns:
    elements["major_class"] = "Unclassified"
else:
    elements["major_class"] = elements["major_class"].fillna("Unclassified")
if "subclass" not in elements.columns:
    elements["subclass"] = elements["element"]

elements = elements.merge(
    coordinates[["stable_id", "species_id", "gene_id", "promoter_length", "promoter_qc"]],
    on="stable_id",
    how="left",
    validate="many_to_one",
)
summary = (
    elements.groupby(["stable_id", "species_id", "gene_id", "major_class", "element"], dropna=False)
    .size()
    .rename("element_count")
    .reset_index()
)
per_gene = (
    elements.groupby(["stable_id", "species_id", "gene_id", "major_class"], dropna=False)
    .size()
    .rename("element_count")
    .reset_index()
)
members = pd.read_csv(snakemake.input.members, sep="\t")
for metadata_column in ("subfamily", "group"):
    if metadata_column not in members:
        members[metadata_column] = "Unassigned"
distributions, distribution_qc = build_promoter_distributions(elements, coordinates, members)
major_class_source = (
    elements.groupby("major_class", dropna=False, as_index=False)
    .agg(motif_hit_count=("element", "size"), n_genes=("stable_id", "nunique"))
    .sort_values(["motif_hit_count", "major_class"], ascending=[False, True])
)
subclass_source = (
    elements.groupby(["major_class", "subclass"], dropna=False, as_index=False)
    .agg(motif_hit_count=("element", "size"), n_genes=("stable_id", "nunique"))
    .sort_values(["motif_hit_count", "major_class", "subclass"], ascending=[False, True, True])
)
subfamily_heatmap_source = distributions.loc[
    distributions["aggregation_level"].eq("SUBFAMILY")
].copy()
group_subfamily_heatmap_source = distributions.loc[
    distributions["aggregation_level"].eq("GROUP_SUBFAMILY")
].copy()
species_heatmap_source = distributions.loc[distributions["aggregation_level"].eq("SPECIES")].copy()

hit_counts = elements.groupby("stable_id").size().rename("total_motif_hits")
representative_registry = (
    members[["stable_id", "species_id", "gene_id", "subfamily", "group"]]
    .merge(hit_counts, on="stable_id", how="left", validate="one_to_one")
    .fillna({"total_motif_hits": 0})
    .sort_values(["subfamily", "total_motif_hits", "stable_id"], ascending=[True, False, True])
    .groupby("subfamily", dropna=False, as_index=False)
    .head(1)
)
top_elements = (
    elements["element"].value_counts().head(int(snakemake.params.top_n_elements)).index.tolist()
)
representative_gene_source = representative_registry.merge(
    elements.loc[elements["element"].isin(top_elements)]
    .groupby(["stable_id", "element"], as_index=False)
    .size()
    .rename(columns={"size": "motif_hit_count"}),
    on="stable_id",
    how="left",
    validate="one_to_many",
)
representative_gene_source["selection_reason"] = "MAX_TOTAL_HITS_PER_SUBFAMILY_TIE_STABLE_ID"
representative_gene_source["display_filter_status"] = "DISPLAY_FILTER_NOT_IMPORTANCE_RANKING"
save_table(elements, snakemake.output.elements)
save_table(summary, snakemake.output.summary)
save_table(per_gene, snakemake.output.per_gene)
save_table(distributions, snakemake.output.distributions)
save_table(distribution_qc, snakemake.output.distribution_qc)
save_table(major_class_source, snakemake.output.major_class_source)
save_table(subclass_source, snakemake.output.subclass_source)
save_table(subfamily_heatmap_source, snakemake.output.subfamily_heatmap_source)
save_table(group_subfamily_heatmap_source, snakemake.output.group_subfamily_heatmap_source)
save_table(species_heatmap_source, snakemake.output.species_heatmap_source)
save_table(representative_gene_source, snakemake.output.representative_gene_source)

if bool(snakemake.params.complete_profile):
    membership = pd.read_csv(snakemake.input.hog_membership, sep="\t")
    classification = pd.read_csv(snakemake.input.pan_classification, sep="\t")
    membership = attach_pan_family_class(membership, classification)
    hog_summary, hog_qc = build_promoter_hog_distributions(
        elements,
        coordinates,
        membership,
    )
else:
    hog_summary = pd.DataFrame(
        columns=[
            "HOG_ID",
            "pan_family_class",
            "element",
            "motif_hit_count",
            "genes_with_hit",
            "n_genes",
            "total_promoter_bp",
            "hits_per_gene",
            "hits_per_kb",
        ]
    )
    hog_qc = pd.DataFrame(
        [
            {
                "total_promoter_genes": int(coordinates["stable_id"].nunique()),
                "assigned_hog_genes": 0,
                "unassigned_genes": 0,
                "n_hogs_including_unassigned": 0,
                "n_elements": int(elements["element"].nunique()),
                "qc_status": "NOT_REQUESTED_LEGACY_PROFILE",
                "scientific_boundary": (
                    "HOG-level promoter aggregation requires deliverables.profile=pdf_md_complete."
                ),
            }
        ]
    )
save_table(hog_summary, snakemake.output.hog_summary)
save_table(hog_qc, snakemake.output.hog_qc)
save_workbook(
    {"promoter_by_hog": hog_summary, "qc": hog_qc},
    snakemake.output.hog_summary_xlsx,
)


def distribution_matrix(aggregation_level: str, value: str) -> pd.DataFrame:
    subset = distributions.loc[distributions["aggregation_level"] == aggregation_level]
    if subset.empty:
        return pd.DataFrame()
    return subset.pivot(index="cell_id", columns="element", values=value).sort_index()


workbook_tables = {
    "hits": elements,
    "element_summary": summary,
    "per_gene_class": per_gene,
    "distributions": distributions,
    "distribution_qc": distribution_qc,
    "major_classes": major_class_source,
    "subclasses": subclass_source,
    "representative_genes": representative_gene_source,
}
for sheet_prefix, aggregation_level in (
    ("sp_subfamily", "SPECIES_SUBFAMILY"),
    ("subfamily", "SUBFAMILY"),
    ("species", "SPECIES"),
    ("group", "GROUP"),
    ("group_subfamily", "GROUP_SUBFAMILY"),
):
    workbook_tables[f"{sheet_prefix}_raw"] = distribution_matrix(
        aggregation_level, "motif_hit_count"
    )
    workbook_tables[f"{sheet_prefix}_z_per_kb"] = distribution_matrix(
        aggregation_level, "zscore_hits_per_kb"
    )
save_workbook(
    workbook_tables,
    snakemake.output.xlsx,
)

class_counts = elements["major_class"].value_counts().sort_values(ascending=False)
fig, axis = plt.subplots(figsize=(7.0, 4.8))
axis.bar(class_counts.index.astype(str), class_counts.values)
axis.set_xlabel("Cis-element major class")
axis.set_ylabel("Number of motif hits")
axis.tick_params(axis="x", rotation=30)
axis.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(snakemake.output.class_plot_pdf)
fig.savefig(snakemake.output.class_plot_png, dpi=int(snakemake.params.png_dpi))
fig.savefig(snakemake.output.fig23_pdf)
fig.savefig(snakemake.output.fig23_png, dpi=int(snakemake.params.png_dpi))
plt.close(fig)

subclass_plot = subclass_source.sort_values("motif_hit_count").tail(
    int(snakemake.params.top_n_elements)
)
fig, axis = plt.subplots(figsize=(8.0, max(4.8, 0.28 * len(subclass_plot))))
axis.barh(subclass_plot["subclass"].astype(str), subclass_plot["motif_hit_count"])
axis.set_xlabel("Number of motif hits")
axis.set_ylabel("Cis-element subclass")
axis.set_title("Promoter cis-element subclasses")
axis.spines[["top", "right"]].set_visible(False)
axis.grid(False)
fig.tight_layout()
fig.savefig(snakemake.output.fig24_pdf)
fig.savefig(snakemake.output.fig24_png, dpi=int(snakemake.params.png_dpi))
plt.close(fig)

top_n = int(snakemake.params.top_n_elements)
top_counts = elements["element"].value_counts().head(top_n).sort_values()
fig, axis = plt.subplots(figsize=(7.2, max(4.8, 0.26 * len(top_counts))))
axis.barh(top_counts.index.astype(str), top_counts.values)
axis.set_xlabel("Number of motif hits")
axis.set_ylabel("Element")
axis.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(snakemake.output.top_plot_pdf)
fig.savefig(snakemake.output.top_plot_png, dpi=int(snakemake.params.png_dpi))
plt.close(fig)


def save_distribution_heatmap(
    aggregation_level: str,
    title: str,
    pdf_path: str,
    png_path: str,
) -> None:
    subset = distributions.loc[distributions["aggregation_level"] == aggregation_level].copy()
    if subset.empty:
        fig, axis = plt.subplots(figsize=(7.2, 4.8))
        axis.text(0.5, 0.5, "No eligible promoter-element cells", ha="center", va="center")
        axis.set_axis_off()
    else:
        top_elements = (
            subset.groupby("element", sort=False)["motif_hit_count"]
            .sum()
            .sort_values(ascending=False, kind="stable")
            .head(int(snakemake.params.top_n_elements))
            .index
        )
        matrix = (
            subset.loc[subset["element"].isin(top_elements)]
            .pivot(index="cell_id", columns="element", values="zscore_hits_per_kb")
            .reindex(columns=top_elements)
            .sort_index()
        )
        matrix.index = [
            " | ".join(part.split("=", 1)[-1] for part in str(cell_id).split("|"))
            for cell_id in matrix.index
        ]
        width = max(7.2, 0.55 * len(matrix.columns) + 3.2)
        height = max(4.8, 0.38 * len(matrix.index) + 2.4)
        fig, axis = plt.subplots(figsize=(width, height))
        numeric = matrix.to_numpy(dtype=float, na_value=np.nan)
        finite = numeric[np.isfinite(numeric)]
        limit = max(1.0, float(np.max(np.abs(finite))) if finite.size else 1.0)
        palette = plt.get_cmap("PuOr_r").copy()
        palette.set_bad("#eeeeee")
        image = axis.imshow(
            np.ma.masked_invalid(numeric),
            aspect="auto",
            interpolation="nearest",
            cmap=palette,
            vmin=-limit,
            vmax=limit,
        )
        axis.set_xticks(
            range(len(matrix.columns)), matrix.columns.astype(str), rotation=45, ha="right"
        )
        axis.set_yticks(range(len(matrix.index)), matrix.index.astype(str))
        axis.set_xlabel("Cis-element")
        axis.set_ylabel("Aggregation cell")
        colorbar = fig.colorbar(image, ax=axis, pad=0.02)
        colorbar.set_label("z-score of hits per kb")
        for spine in axis.spines.values():
            spine.set_visible(False)
    axis.set_title(title)
    fig.text(
        0.01,
        0.01,
        "Population z-score (ddof=0) across cells; gray=missing denominator; use raw/rate/n tables for interpretation.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(pdf_path, facecolor="white")
    fig.savefig(png_path, dpi=int(snakemake.params.png_dpi), facecolor="white")
    plt.close(fig)


save_distribution_heatmap(
    "SPECIES_SUBFAMILY",
    "Species x subfamily promoter-element profile",
    snakemake.output.species_subfamily_plot_pdf,
    snakemake.output.species_subfamily_plot_png,
)
save_distribution_heatmap(
    "SUBFAMILY",
    "Subfamily promoter-element profile",
    snakemake.output.subfamily_plot_pdf,
    snakemake.output.subfamily_plot_png,
)
save_distribution_heatmap(
    "SPECIES",
    "Species promoter-element profile",
    snakemake.output.species_plot_pdf,
    snakemake.output.species_plot_png,
)
save_distribution_heatmap(
    "GROUP",
    "Group promoter-element profile",
    snakemake.output.group_plot_pdf,
    snakemake.output.group_plot_png,
)
save_distribution_heatmap(
    "GROUP_SUBFAMILY",
    "Group x subfamily promoter-element profile",
    snakemake.output.group_subfamily_plot_pdf,
    snakemake.output.group_subfamily_plot_png,
)
save_distribution_heatmap(
    "SUBFAMILY",
    "Promoter-element profile by subfamily",
    snakemake.output.fig25_pdf,
    snakemake.output.fig25_png,
)
save_distribution_heatmap(
    "GROUP_SUBFAMILY",
    "Promoter-element profile by group and subfamily",
    snakemake.output.fig26_pdf,
    snakemake.output.fig26_png,
)
save_distribution_heatmap(
    "SPECIES",
    "Promoter-element profile by species or accession",
    snakemake.output.fig27_pdf,
    snakemake.output.fig27_png,
)

if hog_summary.empty:
    fig, axis = plt.subplots(figsize=(7.2, 4.8))
    axis.text(0.5, 0.5, "No eligible HOG promoter-element cells", ha="center", va="center")
    axis.set_axis_off()
else:
    hog_top_elements = (
        hog_summary.groupby("element")["motif_hit_count"]
        .sum()
        .sort_values(ascending=False, kind="stable")
        .head(int(snakemake.params.top_n_elements))
        .index
    )
    hog_matrix = (
        hog_summary.loc[hog_summary["element"].isin(hog_top_elements)]
        .pivot(index="HOG_ID", columns="element", values="hits_per_kb")
        .reindex(columns=hog_top_elements)
        .sort_index()
    )
    fig, axis = plt.subplots(
        figsize=(
            max(7.2, 0.55 * len(hog_matrix.columns) + 3.2),
            max(4.8, 0.38 * len(hog_matrix.index) + 2.4),
        )
    )
    image = axis.imshow(
        np.ma.masked_invalid(hog_matrix.to_numpy(dtype=float, na_value=np.nan)),
        aspect="auto",
        cmap="YlGnBu",
    )
    axis.set_xticks(
        range(len(hog_matrix.columns)),
        hog_matrix.columns.astype(str),
        rotation=45,
        ha="right",
    )
    axis.set_yticks(range(len(hog_matrix.index)), hog_matrix.index.astype(str))
    axis.set_xlabel("Cis-element")
    axis.set_ylabel("Target-family HOG")
    axis.set_title("Promoter motif-hit rate by target-family HOG")
    fig.colorbar(image, ax=axis, pad=0.02).set_label("Motif hits per kb")
    axis.spines[["top", "right"]].set_visible(False)
fig.text(
    0.01,
    0.01,
    "Descriptive motif-hit rate; not enrichment, TF binding or causal regulation evidence.",
    fontsize=8,
)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(snakemake.output.hog_plot_pdf, facecolor="white")
fig.savefig(
    snakemake.output.hog_plot_png,
    dpi=int(snakemake.params.png_dpi),
    facecolor="white",
)
plt.close(fig)

representative_matrix = representative_gene_source.pivot_table(
    index="stable_id",
    columns="element",
    values="motif_hit_count",
    aggfunc="sum",
    fill_value=0,
).reindex(columns=top_elements, fill_value=0)
fig, axis = plt.subplots(
    figsize=(
        max(8.0, 0.5 * len(representative_matrix.columns) + 3.0),
        max(4.8, 0.38 * len(representative_matrix.index) + 2.4),
    )
)
image = axis.imshow(representative_matrix.to_numpy(dtype=float), aspect="auto", cmap="Blues")
axis.set_xticks(
    range(len(representative_matrix.columns)),
    representative_matrix.columns.astype(str),
    rotation=45,
    ha="right",
)
axis.set_yticks(range(len(representative_matrix.index)), representative_matrix.index.astype(str))
axis.set_xlabel("Top displayed cis-elements")
axis.set_ylabel("Deterministically selected representative gene")
axis.set_title("Representative genes: promoter motif-hit counts")
figure_colorbar = fig.colorbar(image, ax=axis, pad=0.02)
figure_colorbar.set_label("Motif-hit count")
for spine in axis.spines.values():
    spine.set_visible(False)
fig.text(0.01, 0.01, "Top-N is a display filter, not an importance ranking.", fontsize=8)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(snakemake.output.fig28_pdf, facecolor="white")
fig.savefig(snakemake.output.fig28_png, dpi=int(snakemake.params.png_dpi), facecolor="white")
plt.close(fig)
