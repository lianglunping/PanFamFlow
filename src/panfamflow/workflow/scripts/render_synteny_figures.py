import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import math
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from synteny_utils import select_renderable_synteny
from workflow_utils import fasta_lengths, save_table

PASS_ANCHOR_STATUS = "PASS_ORDERED_BLOCK"
INTERPRETATION_FLAG = "SIMILARITY_HITS_ARE_NOT_SYNTENY_LINKS"


def natural_key(value: str) -> tuple[int, str]:
    digits = "".join(character for character in value if character.isdigit())
    return (int(digits) if digits else 10**9, value)


def genome_coordinate_system(
    mapping: pd.DataFrame, sequence_lengths: dict[str, int]
) -> tuple[dict[str, tuple[float, float]], float]:
    chromosomes = sorted(mapping["chromosome"].dropna().astype(str).unique(), key=natural_key)
    if not chromosomes:
        raise ValueError("A synteny genome has no chromosome coordinates.")
    annotated_maximum = (
        mapping.assign(gene_end=pd.to_numeric(mapping["gene_end"], errors="coerce"))
        .groupby(mapping["chromosome"].astype(str))["gene_end"]
        .max()
        .to_dict()
    )
    lengths: dict[str, float] = {}
    for chromosome in chromosomes:
        length = sequence_lengths.get(chromosome, annotated_maximum.get(chromosome))
        if length is None or not np.isfinite(float(length)) or float(length) <= 0:
            raise ValueError(f"No positive sequence length is available for {chromosome}.")
        lengths[chromosome] = float(length)
    gap = max(sum(lengths.values()) * 0.005, 1.0)
    offsets: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for chromosome in chromosomes:
        offsets[chromosome] = (cursor, lengths[chromosome])
        cursor += lengths[chromosome] + gap
    return offsets, cursor - gap


def linear_position(
    chromosome: str, coordinate: float, offsets: dict[str, tuple[float, float]], total: float
) -> float:
    if chromosome not in offsets:
        raise ValueError(f"Chromosome {chromosome!r} is absent from the audited genome layout.")
    offset, length = offsets[chromosome]
    bounded = min(max(float(coordinate), 0.0), length)
    return (offset + bounded) / total


def add_chord(
    axis: plt.Axes,
    angle_1: float,
    angle_2: float,
    *,
    color: str,
    linewidth: float,
    alpha: float,
    radius: float = 0.93,
) -> None:
    start = np.array([math.cos(angle_1), math.sin(angle_1)]) * radius
    end = np.array([math.cos(angle_2), math.sin(angle_2)]) * radius
    path = MplPath(
        [start, np.array([0.0, 0.0]), end],
        [MplPath.MOVETO, MplPath.CURVE3, MplPath.CURVE3],
    )
    axis.add_patch(
        PathPatch(
            path,
            facecolor="none",
            edgecolor=color,
            linewidth=linewidth,
            alpha=alpha,
            zorder=1 if color == "#C9CDD1" else 3,
        )
    )


def save_figure(figure: plt.Figure, pdf: str, png: str, dpi: int) -> None:
    figure.savefig(pdf, facecolor="white", bbox_inches="tight")
    figure.savefig(png, dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(figure)


anchors = pd.concat(
    [pd.read_csv(path, sep="\t") for path in snakemake.input.anchors], ignore_index=True
)
blocks = pd.concat(
    [pd.read_csv(path, sep="\t") for path in snakemake.input.blocks], ignore_index=True
)
pair_summary = pd.concat(
    [pd.read_csv(path, sep="\t") for path in snakemake.input.summaries], ignore_index=True
)
render_anchors, render_blocks, render_pairs = select_renderable_synteny(
    anchors, blocks, pair_summary
)
if render_pairs.empty:
    raise RuntimeError(
        "No species pair passed ordered multi-anchor synteny QC; figures are blocked."
    )

species_ids = [str(value) for value in snakemake.params.species_ids]
maps = {
    species: pd.read_csv(path, sep="\t")
    for species, path in zip(species_ids, snakemake.input.maps, strict=True)
}
genome_sizes = {
    species: dict(fasta_lengths(path))
    for species, path in zip(species_ids, snakemake.input.genomes, strict=True)
}
coordinate_systems = {
    species: genome_coordinate_system(maps[species], genome_sizes[species])
    for species in species_ids
}

members = pd.read_csv(snakemake.input.members, sep="\t")
family_ids = set(members["stable_id"].astype(str))
duplication_modes = pd.read_csv(snakemake.input.duplication_modes, sep="\t")
if duplication_modes["stable_id"].astype(str).duplicated().any():
    raise ValueError("Duplication mode table contains duplicate stable_id assignments.")
mode_by_id = duplication_modes.set_index(duplication_modes["stable_id"].astype(str))[
    "duplication_mode"
].astype(str)

family_links = render_anchors.loc[
    render_anchors["stable_id_1"].astype(str).isin(family_ids)
    | render_anchors["stable_id_2"].astype(str).isin(family_ids)
].copy()
family_links["is_family_gene_1"] = family_links["stable_id_1"].astype(str).isin(family_ids)
family_links["is_family_gene_2"] = family_links["stable_id_2"].astype(str).isin(family_ids)
family_links["duplication_mode_1"] = (
    family_links["stable_id_1"].astype(str).map(mode_by_id).fillna("Not_target_family")
)
family_links["duplication_mode_2"] = (
    family_links["stable_id_2"].astype(str).map(mode_by_id).fillna("Not_target_family")
)
family_links["highlight_class"] = np.where(
    family_links[["duplication_mode_1", "duplication_mode_2"]].eq("WGD").any(axis=1),
    "TARGET_FAMILY_WGD_ANCHOR",
    "TARGET_FAMILY_SYNTENIC_ANCHOR",
)
family_links["interpretation_flag"] = INTERPRETATION_FLAG

intra_mask_anchors = (
    render_anchors["species_1"].astype(str).eq(render_anchors["species_2"].astype(str))
)
intra_mask_blocks = (
    render_blocks["species_1"].astype(str).eq(render_blocks["species_2"].astype(str))
)
anchors_intra = render_anchors.loc[intra_mask_anchors].copy()
anchors_inter = render_anchors.loc[~intra_mask_anchors].copy()
blocks_intra = render_blocks.loc[intra_mask_blocks].copy()
blocks_inter = render_blocks.loc[~intra_mask_blocks].copy()

pair_records: dict[str, dict[str, Any]] = {
    str(key): dict(value) for key, value in dict(snakemake.params.pair_records).items()
}
layout_rows = []
status_by_pair = pair_summary.set_index(pair_summary["pair_id"].astype(str))["pair_status"]
for pair_id, record in pair_records.items():
    layout_rows.append(
        {
            "pair_id": pair_id,
            "species_1": record["species_1"],
            "species_2": record["species_2"],
            "layout_order": int(record["layout_order"]),
            "include_overview": bool(record["include_overview"]),
            "pair_status": str(status_by_pair.get(pair_id, "NOT_EVALUATED")),
            "renderer": "MATPLOTLIB_DETERMINISTIC_EQUIVALENT",
            "coordinate_convention": "1-based closed input; genome-length normalized rendering",
            "evidence_boundary": "ORDERED_MULTI_ANCHOR_BLOCKS_ONLY",
            "interpretation_flag": INTERPRETATION_FLAG,
        }
    )
layout = pd.DataFrame(layout_rows).sort_values(["layout_order", "pair_id"])

table_outputs = (
    (anchors, snakemake.output.anchors, snakemake.output.anchors_xlsx),
    (blocks, snakemake.output.blocks, snakemake.output.blocks_xlsx),
    (anchors_intra, snakemake.output.anchors_intra, snakemake.output.anchors_intra_xlsx),
    (blocks_intra, snakemake.output.blocks_intra, snakemake.output.blocks_intra_xlsx),
    (family_links, snakemake.output.family_links, snakemake.output.family_links_xlsx),
    (anchors_inter, snakemake.output.anchors_inter, snakemake.output.anchors_inter_xlsx),
    (blocks_inter, snakemake.output.blocks_inter, snakemake.output.blocks_inter_xlsx),
    (pair_summary, snakemake.output.pair_summary, snakemake.output.pair_summary_xlsx),
    (layout, snakemake.output.layout, snakemake.output.layout_xlsx),
)
for table, tsv, xlsx in table_outputs:
    save_table(table, tsv, xlsx)

# Fig17: whole-genome blocks are the background; target-family WGD anchors are highlights.
representative = str(snakemake.params.representative_species)
representative_blocks = blocks_intra.loc[
    blocks_intra["species_1"].astype(str).eq(representative)
].copy()
if representative_blocks.empty:
    raise RuntimeError("Fig17 requires one passing intragenome pair for representative_species.")
rep_offsets, rep_total = coordinate_systems[representative]
figure, axis = plt.subplots(figsize=(9.2, 9.2), facecolor="white")
for chromosome, (offset, length) in rep_offsets.items():
    start = 2 * math.pi * (offset / rep_total)
    end = 2 * math.pi * ((offset + length) / rep_total)
    angles = np.linspace(start, end, 100)
    axis.plot(np.cos(angles), np.sin(angles), linewidth=8, solid_capstyle="butt", color="#4C78A8")
    middle = (start + end) / 2
    axis.text(
        1.08 * math.cos(middle),
        1.08 * math.sin(middle),
        chromosome,
        ha="center",
        va="center",
        fontsize=8,
    )
for row in representative_blocks.to_dict(orient="records"):
    angle_1 = (
        2
        * math.pi
        * linear_position(
            str(row["chromosome_1"]),
            (float(row["start_1"]) + float(row["end_1"])) / 2,
            rep_offsets,
            rep_total,
        )
    )
    angle_2 = (
        2
        * math.pi
        * linear_position(
            str(row["chromosome_2"]),
            (float(row["start_2"]) + float(row["end_2"])) / 2,
            rep_offsets,
            rep_total,
        )
    )
    add_chord(axis, angle_1, angle_2, color="#C9CDD1", linewidth=0.7, alpha=0.35)
representative_family = family_links.loc[
    family_links["species_1"].astype(str).eq(representative)
    & family_links["species_2"].astype(str).eq(representative)
].copy()
wgd_links = representative_family.loc[
    representative_family["highlight_class"].eq("TARGET_FAMILY_WGD_ANCHOR")
]
for row in wgd_links.to_dict(orient="records"):
    angle_1 = (
        2
        * math.pi
        * linear_position(
            str(row["chromosome_1"]), float(row["gene_start_1"]), rep_offsets, rep_total
        )
    )
    angle_2 = (
        2
        * math.pi
        * linear_position(
            str(row["chromosome_2"]), float(row["gene_start_2"]), rep_offsets, rep_total
        )
    )
    add_chord(axis, angle_1, angle_2, color="#D55E00", linewidth=1.8, alpha=0.85)
tandem_ids = set(
    duplication_modes.loc[
        duplication_modes["stable_id"].astype(str).isin(family_ids)
        & duplication_modes["duplication_mode"].astype(str).eq("Tandem"),
        "stable_id",
    ].astype(str)
)
rep_map = maps[representative].loc[maps[representative]["stable_id"].astype(str).isin(tandem_ids)]
for row in rep_map.to_dict(orient="records"):
    angle = (
        2
        * math.pi
        * linear_position(str(row["chromosome"]), float(row["gene_start"]), rep_offsets, rep_total)
    )
    axis.scatter(
        [1.01 * math.cos(angle)],
        [1.01 * math.sin(angle)],
        marker="D",
        s=24,
        color="#E69F00",
        zorder=5,
    )
axis.text(
    -1.15,
    -1.22,
    f"Whole-genome blocks: {len(representative_blocks)} | target-family WGD anchors: {len(wgd_links)} | tandem genes: {len(rep_map)}",
    fontsize=9,
)
axis.set_title(f"Representative intragenome synteny — {representative}", fontweight="bold")
axis.set_aspect("equal")
axis.set_xlim(-1.28, 1.28)
axis.set_ylim(-1.28, 1.28)
axis.axis("off")
save_figure(
    figure, snakemake.output.fig17_pdf, snakemake.output.fig17_png, int(snakemake.params.png_dpi)
)

# Fig21: each species pair is an independent panel and uses passing whole-genome blocks.
passing_inter_pairs = layout.loc[
    layout["pair_status"].eq("PASS")
    & layout["species_1"].astype(str).ne(layout["species_2"].astype(str))
].copy()
if passing_inter_pairs.empty:
    raise RuntimeError("Fig21 requires at least one passing inter-species synteny pair.")
n_panels = len(passing_inter_pairs)
figure, axes = plt.subplots(
    n_panels, 1, figsize=(12, max(4.2, 3.5 * n_panels)), squeeze=False, facecolor="white"
)
for axis, pair in zip(axes.ravel(), passing_inter_pairs.to_dict(orient="records"), strict=True):
    pair_id = str(pair["pair_id"])
    species_1 = str(pair["species_1"])
    species_2 = str(pair["species_2"])
    offsets_1, total_1 = coordinate_systems[species_1]
    offsets_2, total_2 = coordinate_systems[species_2]
    axis.plot([0, 1], [1, 1], color="#4C78A8", linewidth=5)
    axis.plot([0, 1], [0, 0], color="#009E73", linewidth=5)
    pair_blocks = blocks_inter.loc[blocks_inter["pair_id"].astype(str).eq(pair_id)]
    for row in pair_blocks.to_dict(orient="records"):
        x_1 = linear_position(
            str(row["chromosome_1"]),
            (float(row["start_1"]) + float(row["end_1"])) / 2,
            offsets_1,
            total_1,
        )
        x_2 = linear_position(
            str(row["chromosome_2"]),
            (float(row["start_2"]) + float(row["end_2"])) / 2,
            offsets_2,
            total_2,
        )
        axis.plot([x_1, x_2], [0.95, 0.05], color="#C9CDD1", linewidth=0.7, alpha=0.45)
    pair_family = family_links.loc[family_links["pair_id"].astype(str).eq(pair_id)]
    for row in pair_family.to_dict(orient="records"):
        x_1 = linear_position(
            str(row["chromosome_1"]), float(row["gene_start_1"]), offsets_1, total_1
        )
        x_2 = linear_position(
            str(row["chromosome_2"]), float(row["gene_start_2"]), offsets_2, total_2
        )
        axis.plot([x_1, x_2], [0.95, 0.05], color="#D55E00", linewidth=1.2, alpha=0.85)
    axis.text(-0.02, 1, species_1, ha="right", va="center", fontweight="bold")
    axis.text(-0.02, 0, species_2, ha="right", va="center", fontweight="bold")
    axis.set_title(
        f"{pair_id}: {len(pair_blocks)} blocks; {len(pair_family)} target-family anchors",
        loc="left",
        fontsize=10,
    )
    axis.set_xlim(-0.08, 1.02)
    axis.set_ylim(-0.25, 1.25)
    axis.axis("off")
figure.suptitle("Pairwise inter-species whole-genome synteny", fontweight="bold")
figure.tight_layout()
save_figure(
    figure, snakemake.output.fig21_pdf, snakemake.output.fig21_png, int(snakemake.params.png_dpi)
)

# Fig22: only PASS pairs explicitly included in the overview enter the fixed layout.
overview_pairs = passing_inter_pairs.loc[passing_inter_pairs["include_overview"]].sort_values(
    "layout_order"
)
if overview_pairs.empty:
    raise RuntimeError("Fig22 has no PASS pair with include_overview=true.")
ordered_species: list[str] = []
for row in overview_pairs.to_dict(orient="records"):
    for species in (str(row["species_1"]), str(row["species_2"])):
        if species not in ordered_species:
            ordered_species.append(species)
y_by_species = {
    species: len(ordered_species) - index - 1 for index, species in enumerate(ordered_species)
}
figure, axis = plt.subplots(figsize=(13, max(5.5, 1.2 * len(ordered_species))), facecolor="white")
for species, y_value in y_by_species.items():
    axis.plot([0, 1], [y_value, y_value], linewidth=5, color="#4C78A8")
    axis.text(-0.02, y_value, species, ha="right", va="center", fontweight="bold")
for pair in overview_pairs.to_dict(orient="records"):
    pair_id = str(pair["pair_id"])
    species_1 = str(pair["species_1"])
    species_2 = str(pair["species_2"])
    offsets_1, total_1 = coordinate_systems[species_1]
    offsets_2, total_2 = coordinate_systems[species_2]
    for row in blocks_inter.loc[blocks_inter["pair_id"].astype(str).eq(pair_id)].to_dict(
        orient="records"
    ):
        x_1 = linear_position(
            str(row["chromosome_1"]),
            (float(row["start_1"]) + float(row["end_1"])) / 2,
            offsets_1,
            total_1,
        )
        x_2 = linear_position(
            str(row["chromosome_2"]),
            (float(row["start_2"]) + float(row["end_2"])) / 2,
            offsets_2,
            total_2,
        )
        axis.plot(
            [x_1, x_2],
            [y_by_species[species_1], y_by_species[species_2]],
            color="#C9CDD1",
            linewidth=0.55,
            alpha=0.35,
        )
    for row in family_links.loc[family_links["pair_id"].astype(str).eq(pair_id)].to_dict(
        orient="records"
    ):
        x_1 = linear_position(
            str(row["chromosome_1"]), float(row["gene_start_1"]), offsets_1, total_1
        )
        x_2 = linear_position(
            str(row["chromosome_2"]), float(row["gene_start_2"]), offsets_2, total_2
        )
        axis.plot(
            [x_1, x_2],
            [y_by_species[species_1], y_by_species[species_2]],
            color="#D55E00",
            linewidth=1.1,
            alpha=0.85,
        )
axis.set_xlim(-0.1, 1.02)
axis.set_ylim(-0.5, len(ordered_species) - 0.5)
axis.set_title("Multi-species synteny overview — PASS pairs only", fontweight="bold")
axis.text(0, -0.42, "Grey: whole-genome blocks; orange: target-family syntenic anchors", fontsize=9)
axis.axis("off")
save_figure(
    figure, snakemake.output.fig22_pdf, snakemake.output.fig22_png, int(snakemake.params.png_dpi)
)
