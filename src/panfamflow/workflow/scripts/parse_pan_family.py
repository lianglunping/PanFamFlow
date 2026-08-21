import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import itertools
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from stratified_summary_utils import (
    PAN_CLASS_ORDER,
    build_pan_family_summaries,
    nonzero_composition,
    numeric_pivot,
)
from workflow_utils import resolve_column, save_table, save_workbook, split_multi_value

# PanFamFlow analyses target-family members in a multi-genome context.  This
# script does not construct a whole-genome pangenome and never classifies HOGs
# that contain no configured target-family member.
result_dir = Path(Path(snakemake.input.result_dir).read_text(encoding="utf-8").strip())
hog_dir = result_dir / "Phylogenetic_Hierarchical_Orthogroups"
if not hog_dir.is_dir():
    candidates = list(result_dir.rglob("Phylogenetic_Hierarchical_Orthogroups"))
    if candidates:
        hog_dir = candidates[0]

requested_node = str(snakemake.params.hog_node)
if requested_node.lower() == "auto":
    candidate = hog_dir / "N0.tsv"
    if not candidate.is_file():
        files = sorted(hog_dir.glob("N*.tsv"), key=lambda path: int(path.stem[1:]))
        if files:
            candidate = files[0]
    if candidate.is_file():
        node_status = "AUTO_DISCOVERY"
        group_type = "HOG"
        analysis_unit = "ORTHOFINDER_HOG"
    else:
        candidate = result_dir / "Orthogroups" / "Orthogroups.tsv"
        if not candidate.is_file():
            raise FileNotFoundError(
                "No public N*.tsv HOG table or Orthogroups/Orthogroups.tsv was found "
                f"under {result_dir}"
            )
        node_status = "AUTO_ORTHOGROUP_FALLBACK"
        group_type = "ORTHOGROUP"
        analysis_unit = "ORTHOFINDER_ORTHOGROUP"
else:
    node_name = requested_node if requested_node.endswith(".tsv") else f"{requested_node}.tsv"
    candidate = hog_dir / node_name
    if not candidate.is_file():
        raise FileNotFoundError(f"Configured HOG node table does not exist: {candidate}")
    node_status = "CONFIGURED"
    group_type = "HOG"
    analysis_unit = "ORTHOFINDER_HOG"

hog = pd.read_csv(candidate, sep="\t", dtype=str).fillna("")
species_ids = [str(item) for item in snakemake.params.species_ids]
if len(species_ids) != len(set(species_ids)):
    raise ValueError("Configured species IDs are not unique.")
missing_species = [species for species in species_ids if species not in hog.columns]
if missing_species:
    raise ValueError(
        "Configured species are missing from the selected HOG table: " + ", ".join(missing_species)
    )
hog_column = resolve_column(hog, ["hog", "hog_id", "orthogroup", hog.columns[0]])

family_members = pd.read_csv(snakemake.input.members, sep="\t", dtype=str).fillna("")
required_member_columns = {"stable_id", "species_id", "gene_id"}
missing_columns = sorted(required_member_columns.difference(family_members.columns))
if missing_columns:
    raise ValueError(
        "family_members.tsv is missing required columns: " + ", ".join(missing_columns)
    )
if family_members.empty:
    raise RuntimeError("No target-family members were supplied to pan_family classification.")
if family_members["stable_id"].duplicated().any():
    duplicates = sorted(
        family_members.loc[family_members["stable_id"].duplicated(keep=False), "stable_id"].unique()
    )
    raise ValueError("Duplicate target-family stable IDs: " + ", ".join(duplicates[:20]))

family_ids = set(family_members["stable_id"].astype(str))
separator = str(snakemake.params.separator)

classification_rows: list[dict[str, Any]] = []
membership_rows: list[dict[str, Any]] = []
presence_records: list[dict[str, Any]] = []
assigned_family_ids: set[str] = set()

for row in hog.to_dict(orient="records"):
    hog_id = str(row[hog_column])
    per_species: dict[str, list[str]] = {}
    for species in species_ids:
        raw_genes = split_multi_value(row.get(species, ""))
        genes = sorted({gene for gene in raw_genes if gene in family_ids})
        for stable_id in genes:
            if separator in stable_id:
                stable_species = stable_id.split(separator, 1)[0]
                if stable_species != species:
                    raise ValueError(
                        f"Stable ID {stable_id!r} is listed under species {species!r} in {candidate}, "
                        f"but its prefix is {stable_species!r}."
                    )
        per_species[species] = genes

    if not any(per_species.values()):
        continue

    assigned_family_ids.update(gene for genes in per_species.values() for gene in genes)
    occupancy = sum(bool(genes) for genes in per_species.values())
    fraction = occupancy / len(species_ids)
    if fraction >= float(snakemake.params.core_min):
        pan_class = "Core"
    elif fraction >= float(snakemake.params.soft_core_min):
        pan_class = "Soft-core"
    elif fraction >= float(snakemake.params.shell_min):
        pan_class = "Shell"
    else:
        pan_class = "Cloud"

    family_gene_count = sum(len(genes) for genes in per_species.values())
    classification_rows.append(
        {
            "HOG_ID": hog_id,
            "hog_node": candidate.stem,
            "hog_node_status": node_status,
            "orthology_group_type": group_type,
            "orthology_source_file": str(candidate.relative_to(result_dir)),
            "analysis_scope": "TARGET_GENE_FAMILY_ONLY",
            "analysis_unit": analysis_unit,
            "presence_basis": f"ANNOTATION_AND_{group_type}_MEMBERSHIP",
            "absence_validation_status": "NOT_GENOME_RESCUED",
            "interpretation_flag": "ANNOTATION_OCCUPANCY_NOT_VALIDATED_GENE_LOSS",
            "species_occupancy": occupancy,
            "species_fraction": fraction,
            "family_gene_count": family_gene_count,
            "mean_copy_number_present_species": family_gene_count / occupancy if occupancy else 0.0,
            "max_copy_number": max((len(genes) for genes in per_species.values()), default=0),
            "single_copy_species_fraction": sum(len(genes) == 1 for genes in per_species.values())
            / len(species_ids),
            "pan_family_class": pan_class,
            "is_private": occupancy == 1,
        }
    )

    presence_record: dict[str, Any] = {"HOG_ID": hog_id}
    for species, genes in per_species.items():
        presence_record[species] = int(bool(genes))
        for stable_id in genes:
            if separator in stable_id:
                stable_species, gene_id = stable_id.split(separator, 1)
            else:
                stable_species, gene_id = species, stable_id
            membership_rows.append(
                {
                    "HOG_ID": hog_id,
                    "orthology_group_type": group_type,
                    "species_id": stable_species,
                    "gene_id": gene_id,
                    "stable_id": stable_id,
                    "copy_number_in_species": len(genes),
                }
            )
    presence_records.append(presence_record)

classification = pd.DataFrame(classification_rows)
membership = pd.DataFrame(membership_rows)
presence = pd.DataFrame(presence_records)
if classification.empty:
    raise RuntimeError(
        "No target-family HOG remained after intersecting the selected HOG node with "
        "family_members.tsv. Check stable IDs and orthofinder.hog_node."
    )
classification = classification.sort_values("HOG_ID").reset_index(drop=True)
membership = membership.sort_values(["HOG_ID", "species_id", "stable_id"]).reset_index(drop=True)
presence = presence.sort_values("HOG_ID").reset_index(drop=True)

unassigned = family_members.loc[~family_members["stable_id"].isin(assigned_family_ids)].copy()
unassigned["reason"] = "NOT_FOUND_IN_SELECTED_HOG_NODE"
unassigned["selected_hog_node"] = candidate.stem
unassigned["hog_node_status"] = node_status
unassigned["orthology_group_type"] = group_type
unassigned["orthology_source_file"] = str(candidate.relative_to(result_dir))
save_table(unassigned, snakemake.output.unassigned_members)

matrix = presence.set_index("HOG_ID")[species_ids].astype(bool)
rng = np.random.default_rng(int(snakemake.params.seed))


def random_unique_subsets(items: list[str], size: int, count: int) -> Iterable[tuple[str, ...]]:
    """Yield up to ``count`` unique subsets without materializing all combinations."""

    target = min(count, math.comb(len(items), size))
    observed: set[tuple[str, ...]] = set()
    while len(observed) < target:
        subset = tuple(sorted(rng.choice(items, size=size, replace=False).tolist()))
        observed.add(subset)
    return sorted(observed)


rarefaction_rows: list[dict[str, Any]] = []
for n_species in range(1, len(species_ids) + 1):
    combination_count = math.comb(len(species_ids), n_species)
    if combination_count <= int(snakemake.params.max_exact_combinations):
        subsets: Iterable[tuple[str, ...]] = itertools.combinations(species_ids, n_species)
        sampling = "exact"
    else:
        subsets = random_unique_subsets(
            species_ids,
            n_species,
            int(snakemake.params.rarefaction_iterations),
        )
        sampling = "random_unique"
    for iteration, subset in enumerate(subsets, start=1):
        subset_matrix = matrix.loc[:, list(subset)]
        rarefaction_rows.append(
            {
                "n_species": n_species,
                "iteration": iteration,
                "sampling": sampling,
                "subset": ",".join(subset),
                "pan_family_hog_count": int(subset_matrix.any(axis=1).sum()),
                "core_family_hog_count": int(subset_matrix.all(axis=1).sum()),
            }
        )

rarefaction = pd.DataFrame(rarefaction_rows)
summary = rarefaction.groupby("n_species", as_index=False).agg(
    pan_mean=("pan_family_hog_count", "mean"),
    pan_median=("pan_family_hog_count", "median"),
    pan_q025=("pan_family_hog_count", lambda values: values.quantile(0.025)),
    pan_q975=("pan_family_hog_count", lambda values: values.quantile(0.975)),
    core_mean=("core_family_hog_count", "mean"),
    core_median=("core_family_hog_count", "median"),
    core_q025=("core_family_hog_count", lambda values: values.quantile(0.025)),
    core_q975=("core_family_hog_count", lambda values: values.quantile(0.975)),
)
pan_summaries = build_pan_family_summaries(
    classification,
    membership,
    family_members,
    species_ids=species_ids,
)
class_summary = pan_summaries["class_summary"]
species_class_summary = pan_summaries["species_class_summary"]
subfamily_class_summary = pan_summaries["subfamily_class_summary"]
hog_gene_counts = classification[
    [
        "HOG_ID",
        "pan_family_class",
        "family_gene_count",
        "species_occupancy",
        "species_fraction",
        "mean_copy_number_present_species",
        "max_copy_number",
        "single_copy_species_fraction",
        "hog_node",
        "hog_node_status",
        "orthology_group_type",
        "absence_validation_status",
        "interpretation_flag",
    ]
].copy()

save_table(classification, snakemake.output.classification)
save_table(membership, snakemake.output.membership)
save_table(presence, snakemake.output.presence)
save_table(rarefaction, snakemake.output.rarefaction)
save_table(summary, snakemake.output.rarefaction_summary)
save_table(class_summary, snakemake.output.class_summary)
save_table(hog_gene_counts, snakemake.output.hog_gene_counts)
save_table(species_class_summary, snakemake.output.species_class_summary)
save_table(subfamily_class_summary, snakemake.output.subfamily_class_summary)
save_workbook(
    {
        "pan_family_classification": classification,
        "family_hog_membership": membership,
        "family_presence_absence": presence,
        "unassigned_members": unassigned,
        "rarefaction_iterations": rarefaction,
        "rarefaction_summary": summary,
        "class_summary": class_summary,
        "hog_gene_counts": hog_gene_counts,
        "species_class_summary": species_class_summary,
        "subfamily_class_summary": subfamily_class_summary,
    },
    snakemake.output.xlsx,
)

class_order = PAN_CLASS_ORDER
class_counts = classification["pan_family_class"].value_counts().reindex(class_order, fill_value=0)
colors = {"Core": "#D55E00", "Soft-core": "#E69F00", "Shell": "#009E73", "Cloud": "#56B4E9"}
fig, axis = plt.subplots(figsize=(6.4, 4.8))
axis.bar(
    class_counts.index, class_counts.values, color=[colors[item] for item in class_counts.index]
)
axis.set_xlabel("Pan-family class")
axis.set_ylabel("Number of target-family orthology groups")
axis.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(snakemake.output.class_plot_pdf)
fig.savefig(snakemake.output.class_plot_png, dpi=int(snakemake.params.png_dpi))
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.8))
for axis, counting_unit in zip(axes, ("HOG", "GENE"), strict=True):
    subset = (
        class_summary.loc[class_summary["counting_unit"] == counting_unit]
        .set_index("pan_family_class")
        .reindex(class_order)
    )
    labels, values = nonzero_composition(
        subset.reset_index(),
        label_column="pan_family_class",
    )
    if not values:
        axis.text(0.5, 0.5, "No assigned units", ha="center", va="center")
        axis.set_axis_off()
    else:
        denominator = sum(values)
        axis.pie(
            values,
            labels=[
                f"{label}\n{value} ({value / denominator:.1%})"
                for label, value in zip(labels, values, strict=True)
            ],
            colors=[colors[label] for label in labels],
            startangle=90,
            wedgeprops={"width": 0.45, "edgecolor": "white"},
        )
    axis.set_title(f"{counting_unit} denominator")
fig.suptitle("Target-family pan-class composition")
fig.tight_layout()
fig.savefig(snakemake.output.dual_denominator_plot_pdf, facecolor="white")
fig.savefig(
    snakemake.output.dual_denominator_plot_png,
    dpi=int(snakemake.params.png_dpi),
    facecolor="white",
)
fig.savefig(snakemake.output.fig10_pdf, facecolor="white")
fig.savefig(
    snakemake.output.fig10_png,
    dpi=int(snakemake.params.png_dpi),
    facecolor="white",
)
plt.close(fig)

fig, axis = plt.subplots(figsize=(8.2, max(4.8, 0.20 * len(hog_gene_counts) + 2.0)))
ordered_hogs = hog_gene_counts.sort_values(
    ["pan_family_class", "family_gene_count", "HOG_ID"],
    key=lambda series: (
        series.map({label: index for index, label in enumerate(class_order)})
        if series.name == "pan_family_class"
        else series
    ),
).reset_index(drop=True)
axis.scatter(
    ordered_hogs["family_gene_count"],
    np.arange(len(ordered_hogs)),
    c=ordered_hogs["pan_family_class"].map(colors),
    s=38,
    alpha=0.9,
)
axis.set_yticks(np.arange(len(ordered_hogs)), ordered_hogs["HOG_ID"], fontsize=7)
axis.set_xlabel("Target-family gene count per orthology group")
axis.set_ylabel("Orthology group")
axis.set_title("Gene counts of target-family orthology groups by pan class")
axis.spines[["top", "right"]].set_visible(False)
axis.grid(False)
fig.tight_layout()
fig.savefig(snakemake.output.fig11_pdf, facecolor="white")
fig.savefig(snakemake.output.fig11_png, dpi=int(snakemake.params.png_dpi), facecolor="white")
plt.close(fig)


def save_species_pan_class_measure(
    value_column: str, ylabel: str, pdf_path: str, png_path: str
) -> None:
    matrix = numeric_pivot(
        species_class_summary,
        index="species_id",
        columns="pan_family_class",
        values=value_column,
        column_order=class_order,
        fill_value=0.0,
    )
    fig, axis = plt.subplots(figsize=(max(8.0, 0.42 * len(matrix) + 4.5), 5.2))
    matrix.plot(
        kind="bar",
        stacked=True,
        color=[colors[label] for label in class_order],
        ax=axis,
    )
    axis.set_xlabel("Species or accession")
    axis.set_ylabel(ylabel)
    if value_column.endswith("fraction"):
        axis.set_ylim(0, 1)
    axis.tick_params(axis="x", rotation=45)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(False)
    axis.legend(frameon=False, title="Pan class", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(pdf_path, facecolor="white")
    fig.savefig(png_path, dpi=int(snakemake.params.png_dpi), facecolor="white")
    plt.close(fig)


save_species_pan_class_measure(
    "gene_count",
    "Number of target-family genes",
    snakemake.output.fig12_pdf,
    snakemake.output.fig12_png,
)
save_species_pan_class_measure(
    "gene_fraction",
    "Within-species fraction of target-family genes",
    snakemake.output.fig13_pdf,
    snakemake.output.fig13_png,
)


def save_class_distribution(
    table: pd.DataFrame,
    index_column: str,
    title: str,
    pdf_path: str,
    png_path: str,
) -> None:
    count_matrix = numeric_pivot(
        table,
        index=index_column,
        columns="pan_family_class",
        values="gene_count",
        column_order=class_order,
        fill_value=0.0,
    )
    fraction_matrix = numeric_pivot(
        table,
        index=index_column,
        columns="pan_family_class",
        values="gene_fraction",
        column_order=class_order,
        fill_value=0.0,
    ).reindex(index=count_matrix.index)
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(max(10.0, 0.45 * len(count_matrix) + 6.5), 5.2),
    )
    count_matrix.plot(
        kind="bar",
        stacked=True,
        color=[colors[label] for label in class_order],
        ax=axes[0],
        legend=False,
    )
    fraction_matrix.plot(
        kind="bar",
        stacked=True,
        color=[colors[label] for label in class_order],
        ax=axes[1],
    )
    axes[0].set_ylabel("Number of target-family genes")
    axes[1].set_ylabel("Within-stratum gene fraction")
    axes[1].set_ylim(0, 1)
    for axis in axes:
        axis.set_xlabel(index_column.replace("_", " ").title())
        axis.tick_params(axis="x", rotation=45)
        axis.spines[["top", "right"]].set_visible(False)
    axes[1].legend(frameon=False, title="Pan class", bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(pdf_path, facecolor="white")
    fig.savefig(png_path, dpi=int(snakemake.params.png_dpi), facecolor="white")
    plt.close(fig)


save_class_distribution(
    species_class_summary,
    "species_id",
    "Pan-class distribution by species or accession",
    snakemake.output.species_class_plot_pdf,
    snakemake.output.species_class_plot_png,
)
save_class_distribution(
    subfamily_class_summary,
    "subfamily",
    "Pan-class distribution by subfamily",
    snakemake.output.subfamily_class_plot_pdf,
    snakemake.output.subfamily_class_plot_png,
)

fig, axis = plt.subplots(figsize=(6.4, 4.8))
axis.plot(summary["n_species"], summary["pan_mean"], marker="o", label="Pan-family groups")
axis.fill_between(summary["n_species"], summary["pan_q025"], summary["pan_q975"], alpha=0.2)
axis.plot(summary["n_species"], summary["core_mean"], marker="o", label="Core family groups")
axis.fill_between(summary["n_species"], summary["core_q025"], summary["core_q975"], alpha=0.2)
axis.set_xlabel("Number of species or accessions")
axis.set_ylabel("Number of target-family orthology groups")
axis.legend(frameon=False)
axis.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(snakemake.output.rarefaction_plot_pdf)
fig.savefig(snakemake.output.rarefaction_plot_png, dpi=int(snakemake.params.png_dpi))
plt.close(fig)
