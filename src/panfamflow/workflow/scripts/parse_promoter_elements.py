import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from promoter_distribution_utils import build_promoter_distributions
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
distributions, distribution_qc = build_promoter_distributions(elements, coordinates, members)
save_table(elements, snakemake.output.elements)
save_table(summary, snakemake.output.summary)
save_table(per_gene, snakemake.output.per_gene)
save_table(distributions, snakemake.output.distributions)
save_table(distribution_qc, snakemake.output.distribution_qc)


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
