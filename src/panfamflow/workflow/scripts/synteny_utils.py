"""Auditable whole-genome synteny anchor and block contracts."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import numpy as np
import pandas as pd

ANCHOR_COLUMNS = (
    "pair_id",
    "block_id",
    "anchor_id",
    "species_1",
    "species_2",
    "stable_id_1",
    "stable_id_2",
    "orientation",
    "score",
    "evidence_type",
)
MAP_COLUMNS = (
    "stable_id",
    "species_id",
    "chromosome",
    "gene_start",
    "gene_end",
)


def parse_jcvi_anchor_lines(
    lines: Iterable[str],
    *,
    pair_id: str,
    species_1: str,
    species_2: str,
) -> pd.DataFrame:
    """Convert a JCVI ``*.anchors`` stream into the canonical anchor contract."""

    rows: list[dict[str, object]] = []
    block_index = 0
    anchor_index = 0
    block_has_rows = False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("###"):
            if block_index == 0 or block_has_rows:
                block_index += 1
            block_has_rows = False
            continue
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 2:
            fields = line.split()
        if len(fields) < 2:
            raise ValueError(f"Malformed JCVI anchor row: {line!r}")
        if block_index == 0:
            block_index = 1
        anchor_index += 1
        block_has_rows = True
        score: float | object = pd.NA
        if len(fields) >= 3:
            score = pd.to_numeric(pd.Series([fields[2]]), errors="coerce").iloc[0]
        rows.append(
            {
                "pair_id": pair_id,
                "block_id": f"{pair_id}.block_{block_index:06d}",
                "anchor_id": f"{pair_id}.anchor_{anchor_index:08d}",
                "species_1": species_1,
                "species_2": species_2,
                "stable_id_1": fields[0],
                "stable_id_2": fields[1],
                "orientation": "PENDING_COORDINATE_AUDIT",
                "score": score,
                "evidence_type": "SYNTENY_ANCHOR",
            }
        )
    if not rows:
        raise ValueError(f"JCVI produced no anchors for pair_id {pair_id!r}.")
    return pd.DataFrame(rows, columns=list(ANCHOR_COLUMNS))


def assign_block_orientations(
    anchors: pd.DataFrame,
    map_1: pd.DataFrame,
    map_2: pd.DataFrame,
    species_1: str,
    species_2: str,
) -> pd.DataFrame:
    """Infer each block direction from audited genomic coordinates."""

    _require_columns(anchors, ANCHOR_COLUMNS, "synteny anchor table")
    left = _prepare_map(map_1, species_1, "1")
    right = _prepare_map(map_2, species_2, "2")
    working = anchors.copy()
    located = working.merge(left, on="stable_id_1", how="left", validate="many_to_one")
    located = located.merge(right, on="stable_id_2", how="left", validate="many_to_one")
    if located[["gene_start_1", "gene_start_2"]].isna().any(axis=None):
        raise ValueError("JCVI anchors contain identifiers without audited coordinates.")
    for block_id, group in located.groupby("block_id", sort=True):
        ordered = group.sort_values(["gene_start_1", "stable_id_1"])
        positions = ordered["gene_start_2"].to_numpy(dtype=float)
        orientation = "+" if positions[-1] >= positions[0] else "-"
        working.loc[working["block_id"].astype(str).eq(str(block_id)), "orientation"] = orientation
    return working


def _require_columns(table: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = sorted(set(columns).difference(table.columns))
    if missing:
        raise ValueError(f"{label} lacks required columns: {', '.join(missing)}")


def _prepare_map(table: pd.DataFrame, species_id: str, suffix: str) -> pd.DataFrame:
    _require_columns(table, MAP_COLUMNS, f"{species_id} gene map")
    working = table[list(MAP_COLUMNS)].copy()
    working = working.loc[working["species_id"].astype(str).eq(species_id)].copy()
    if working["stable_id"].astype(str).duplicated().any():
        raise ValueError(f"{species_id} gene map contains duplicate stable_id rows.")
    for column in ("gene_start", "gene_end"):
        working[column] = pd.to_numeric(working[column], errors="coerce")
    if working[["chromosome", "gene_start", "gene_end"]].isna().any(axis=None):
        raise ValueError(f"{species_id} gene map contains missing coordinates.")
    if (working["gene_start"] > working["gene_end"]).any():
        raise ValueError(f"{species_id} gene map contains reversed coordinates.")
    return working.rename(
        columns={column: f"{column}_{suffix}" for column in MAP_COLUMNS if column != "stable_id"}
    ).rename(columns={"stable_id": f"stable_id_{suffix}"})


def audit_synteny_anchors(
    raw_anchors: pd.DataFrame,
    map_1: pd.DataFrame,
    map_2: pd.DataFrame,
    *,
    pair_id: str,
    species_1: str,
    species_2: str,
    min_anchors_per_block: int,
    backend: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate ordered multi-anchor blocks and return anchor, block and pair tables."""

    if min_anchors_per_block < 3:
        raise ValueError("min_anchors_per_block must be at least 3")
    _require_columns(raw_anchors, ANCHOR_COLUMNS, "synteny anchor table")
    anchors = raw_anchors[list(ANCHOR_COLUMNS)].copy()
    anchors = anchors.loc[anchors["pair_id"].astype(str).eq(pair_id)].copy()
    if anchors.empty:
        raise ValueError(f"No anchors were supplied for pair_id {pair_id!r}.")
    if anchors["anchor_id"].astype(str).duplicated().any():
        raise ValueError(f"Synteny pair {pair_id} contains duplicate anchor_id rows.")
    if not anchors["species_1"].astype(str).eq(species_1).all():
        raise ValueError(f"Synteny pair {pair_id} has inconsistent species_1 values.")
    if not anchors["species_2"].astype(str).eq(species_2).all():
        raise ValueError(f"Synteny pair {pair_id} has inconsistent species_2 values.")
    evidence = set(anchors["evidence_type"].astype(str))
    if evidence != {"SYNTENY_ANCHOR"}:
        raise ValueError(
            "Only evidence_type=SYNTENY_ANCHOR may enter synteny blocks; "
            f"observed {sorted(evidence)}."
        )
    if not anchors["orientation"].astype(str).isin({"+", "-"}).all():
        raise ValueError("Synteny anchor orientation must be '+' or '-'.")

    left = _prepare_map(map_1, species_1, "1")
    right = _prepare_map(map_2, species_2, "2")
    anchors = anchors.merge(left, on="stable_id_1", how="left", validate="many_to_one")
    anchors = anchors.merge(right, on="stable_id_2", how="left", validate="many_to_one")
    coordinate_columns = [
        "chromosome_1",
        "gene_start_1",
        "gene_end_1",
        "chromosome_2",
        "gene_start_2",
        "gene_end_2",
    ]
    if anchors[coordinate_columns].isna().any(axis=None):
        missing_ids = anchors.loc[
            anchors[coordinate_columns].isna().any(axis=1), ["stable_id_1", "stable_id_2"]
        ]
        raise ValueError(
            "Synteny anchors contain stable IDs without audited coordinates: "
            + ", ".join("/".join(row) for row in missing_ids.astype(str).to_numpy()[:10])
        )
    anchors["score"] = pd.to_numeric(anchors["score"], errors="coerce")
    anchors["anchor_qc"] = "PENDING_BLOCK_AUDIT"
    block_rows: list[dict[str, object]] = []
    for block_id, group in anchors.groupby("block_id", sort=True):
        orientations = set(group["orientation"].astype(str))
        chromosome_pairs = group[["chromosome_1", "chromosome_2"]].drop_duplicates()
        ordered = group.sort_values(["gene_start_1", "stable_id_1"])
        second_positions = ordered["gene_start_2"].to_numpy(dtype=float)
        orientation = next(iter(orientations)) if len(orientations) == 1 else "MIXED"
        if orientation == "+":
            collinear_order = bool(np.all(np.diff(second_positions) >= 0))
        elif orientation == "-":
            collinear_order = bool(np.all(np.diff(second_positions) <= 0))
        else:
            collinear_order = False
        anchor_count = int(group["anchor_id"].nunique())
        if chromosome_pairs.shape[0] != 1:
            block_qc = "MIXED_CHROMOSOME_PAIR"
            anchor_qc = "BLOCK_MIXED_CHROMOSOME_PAIR"
        elif not collinear_order:
            block_qc = "NON_COLLINEAR_ORDER"
            anchor_qc = "BLOCK_NON_COLLINEAR_ORDER"
        elif anchor_count < min_anchors_per_block:
            block_qc = "BELOW_MIN_ANCHORS"
            anchor_qc = "BLOCK_BELOW_MIN_ANCHORS"
        else:
            block_qc = "PASS"
            anchor_qc = "PASS_ORDERED_BLOCK"
        anchors.loc[group.index, "anchor_qc"] = anchor_qc
        block_rows.append(
            {
                "pair_id": pair_id,
                "block_id": str(block_id),
                "species_1": species_1,
                "species_2": species_2,
                "chromosome_1": str(group["chromosome_1"].iloc[0]),
                "start_1": int(group["gene_start_1"].min()),
                "end_1": int(group["gene_end_1"].max()),
                "chromosome_2": str(group["chromosome_2"].iloc[0]),
                "start_2": int(group["gene_start_2"].min()),
                "end_2": int(group["gene_end_2"].max()),
                "anchor_count": anchor_count,
                "orientation": orientation,
                "minimum_anchors_required": min_anchors_per_block,
                "backend": backend,
                "block_qc": block_qc,
                "evidence_basis": "ORDERED_MULTI_ANCHOR_BLOCK",
            }
        )
    blocks = pd.DataFrame(block_rows)
    passing = blocks.loc[blocks["block_qc"].eq("PASS")]
    passing_anchor_ids = set(
        anchors.loc[anchors["anchor_qc"].eq("PASS_ORDERED_BLOCK"), "anchor_id"].astype(str)
    )
    total_genes_1 = int(left["stable_id_1"].nunique())
    total_genes_2 = int(right["stable_id_2"].nunique())
    summary = pd.DataFrame(
        [
            {
                "pair_id": pair_id,
                "species_1": species_1,
                "species_2": species_2,
                "backend": backend,
                "genome_gene_total_1": total_genes_1,
                "genome_gene_total_2": total_genes_2,
                "anchor_count_total": int(anchors["anchor_id"].nunique()),
                "anchor_count_pass": len(passing_anchor_ids),
                "block_count_total": int(blocks["block_id"].nunique()),
                "block_count_pass": int(passing["block_id"].nunique()),
                "anchored_gene_fraction_1": (
                    anchors.loc[
                        anchors["anchor_qc"].eq("PASS_ORDERED_BLOCK"), "stable_id_1"
                    ].nunique()
                    / total_genes_1
                    if total_genes_1
                    else pd.NA
                ),
                "anchored_gene_fraction_2": (
                    anchors.loc[
                        anchors["anchor_qc"].eq("PASS_ORDERED_BLOCK"), "stable_id_2"
                    ].nunique()
                    / total_genes_2
                    if total_genes_2
                    else pd.NA
                ),
                "minimum_anchors_per_block": min_anchors_per_block,
                "synteny_evidence_basis": "ORDERED_MULTI_ANCHOR_BLOCKS",
                "pair_status": "PASS" if not passing.empty else "BLOCKED_QC",
                "interpretation_flag": "SIMILARITY_HITS_ARE_NOT_SYNTENY_LINKS",
            }
        ]
    )
    return anchors, blocks, summary


def select_renderable_synteny(
    anchors: pd.DataFrame,
    blocks: pd.DataFrame,
    pair_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return only pair/block/anchor evidence that passed every synteny QC layer."""

    passing_pairs = pair_summary.loc[pair_summary["pair_status"].astype(str).eq("PASS")].copy()
    pair_ids = set(passing_pairs["pair_id"].astype(str))
    passing_blocks = blocks.loc[
        blocks["pair_id"].astype(str).isin(pair_ids) & blocks["block_qc"].astype(str).eq("PASS")
    ].copy()
    block_keys = set(
        zip(
            passing_blocks["pair_id"].astype(str),
            passing_blocks["block_id"].astype(str),
            strict=True,
        )
    )
    anchor_keys = list(
        zip(anchors["pair_id"].astype(str), anchors["block_id"].astype(str), strict=True)
    )
    passing_anchors = anchors.loc[
        pd.Series([key in block_keys for key in anchor_keys], index=anchors.index)
        & anchors["anchor_qc"].astype(str).eq("PASS_ORDERED_BLOCK")
    ].copy()
    return passing_anchors, passing_blocks, passing_pairs
