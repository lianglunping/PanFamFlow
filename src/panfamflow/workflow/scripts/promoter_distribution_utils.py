"""Auditable promoter-element aggregation and standardization helpers."""

import math
from collections.abc import Sequence

import pandas as pd

AGGREGATION_DIMENSIONS = {
    "SPECIES_SUBFAMILY": ("species_id", "subfamily"),
    "SUBFAMILY": ("subfamily",),
    "SPECIES": ("species_id",),
    "GROUP": ("group",),
    "GROUP_SUBFAMILY": ("group", "subfamily"),
}

DISTRIBUTION_COLUMNS = [
    "aggregation_level",
    "cell_id",
    "species_id",
    "subfamily",
    "group",
    "element",
    "motif_hit_count",
    "genes_with_hit",
    "n_genes",
    "total_promoter_bp",
    "hits_per_gene",
    "hits_per_kb",
    "zscore_motif_hit_count",
    "raw_zscore_status",
    "zscore_hits_per_kb",
    "rate_zscore_status",
    "zscore_axis",
    "zscore_ddof",
]

QC_COLUMNS = [
    "aggregation_level",
    "required_annotations",
    "total_genes",
    "eligible_genes",
    "excluded_genes_missing_annotation",
    "n_cells",
    "n_elements",
    "complete_grid_rows",
    "cells_zero_promoter_bp",
    "zscore_axis",
    "zscore_ddof",
    "qc_status",
]

MISSING_LABELS = {"", "NA", "N/A", "NONE", "NULL", "NAN", "<NA>"}

HOG_DISTRIBUTION_COLUMNS = [
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


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def _normalize_labels(values: pd.Series) -> pd.Series:
    normalized = values.astype("string").str.strip()
    return normalized.mask(normalized.str.upper().isin(MISSING_LABELS), pd.NA)


def _cell_id(frame: pd.DataFrame, dimensions: Sequence[str]) -> pd.Series:
    return frame.apply(
        lambda row: "|".join(f"{dimension}={row[dimension]}" for dimension in dimensions),
        axis=1,
    )


def attach_pan_family_class(
    membership: pd.DataFrame,
    classification: pd.DataFrame,
) -> pd.DataFrame:
    """Attach the authoritative HOG-level pan class to each gene membership row."""

    _require_columns(membership, ("stable_id", "HOG_ID"), "target-family HOG membership")
    _require_columns(classification, ("HOG_ID", "pan_family_class"), "pan classification")
    if classification["HOG_ID"].astype(str).duplicated().any():
        raise ValueError("Pan classification contains duplicate HOG_ID values.")
    clean_membership = membership.drop(columns=["pan_family_class"], errors="ignore").copy()
    clean_classification = classification[["HOG_ID", "pan_family_class"]].copy()
    enriched = clean_membership.merge(
        clean_classification,
        on="HOG_ID",
        how="left",
        validate="many_to_one",
    )
    assigned = _normalize_labels(enriched["HOG_ID"]).notna()
    missing = assigned & _normalize_labels(enriched["pan_family_class"]).isna()
    if missing.any():
        examples = sorted(enriched.loc[missing, "HOG_ID"].astype(str).unique())[:10]
        raise ValueError(
            "HOG membership does not reconcile with pan classification; "
            f"unclassified HOG_ID examples: {examples}"
        )
    return enriched


def _zscore_with_status(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    zscores = pd.Series(pd.NA, index=values.index, dtype="Float64")
    statuses = pd.Series("MISSING_DENOMINATOR", index=values.index, dtype="string")
    finite = numeric.map(math.isfinite)
    finite_values = numeric.loc[finite]
    if len(finite_values) < 2:
        statuses.loc[finite] = "INSUFFICIENT_CELLS"
        return zscores, statuses
    standard_deviation = float(finite_values.std(ddof=0))
    if math.isclose(standard_deviation, 0.0, abs_tol=1.0e-12):
        zscores.loc[finite] = 0.0
        statuses.loc[finite] = "ZERO_VARIANCE"
        return zscores, statuses
    zscores.loc[finite] = (finite_values - float(finite_values.mean())) / standard_deviation
    statuses.loc[finite] = "PASS"
    return zscores, statuses


def build_promoter_hog_distributions(
    elements: pd.DataFrame,
    coordinates: pd.DataFrame,
    membership: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate motif hits by audited target-family HOG with explicit denominators."""

    _require_columns(elements, ("stable_id", "element"), "promoter elements")
    _require_columns(coordinates, ("stable_id", "promoter_length"), "promoter coordinates")
    _require_columns(
        membership,
        ("stable_id", "HOG_ID", "pan_family_class"),
        "target-family HOG membership",
    )
    if coordinates["stable_id"].astype(str).duplicated().any():
        raise ValueError("Promoter coordinates contain duplicate stable_id values.")
    if membership["stable_id"].astype(str).duplicated().any():
        raise ValueError("Target-family HOG membership contains duplicate stable_id values.")

    genes = coordinates[["stable_id", "promoter_length"]].copy()
    genes["stable_id"] = genes["stable_id"].astype(str)
    genes["promoter_length"] = pd.to_numeric(genes["promoter_length"], errors="coerce")
    if genes["promoter_length"].isna().any() or (genes["promoter_length"] < 0).any():
        raise ValueError("Promoter coordinates contain invalid promoter_length values.")
    annotations = membership[["stable_id", "HOG_ID", "pan_family_class"]].copy()
    annotations["stable_id"] = annotations["stable_id"].astype(str)
    genes = genes.merge(annotations, on="stable_id", how="left", validate="one_to_one")
    genes["HOG_ID"] = _normalize_labels(genes["HOG_ID"]).fillna("Unassigned")
    genes["pan_family_class"] = _normalize_labels(genes["pan_family_class"]).fillna("Unassigned")

    element_names = sorted(elements["element"].dropna().astype(str).unique())
    groups = (
        genes.groupby(["HOG_ID", "pan_family_class"], dropna=False, as_index=False)
        .agg(n_genes=("stable_id", "nunique"), total_promoter_bp=("promoter_length", "sum"))
        .sort_values(["HOG_ID", "pan_family_class"], kind="stable")
    )
    if not element_names:
        summary = pd.DataFrame(columns=HOG_DISTRIBUTION_COLUMNS)
    else:
        counts = (
            elements[["stable_id", "element"]]
            .assign(stable_id=lambda frame: frame["stable_id"].astype(str))
            .merge(
                genes[["stable_id", "HOG_ID", "pan_family_class"]],
                on="stable_id",
                how="inner",
                validate="many_to_one",
            )
            .groupby(["HOG_ID", "pan_family_class", "element"], as_index=False)
            .agg(
                motif_hit_count=("stable_id", "size"),
                genes_with_hit=("stable_id", "nunique"),
            )
        )
        summary = (
            groups.assign(_cross=1)
            .merge(pd.DataFrame({"element": element_names, "_cross": 1}), on="_cross")
            .drop(columns="_cross")
            .merge(
                counts,
                on=["HOG_ID", "pan_family_class", "element"],
                how="left",
                validate="one_to_one",
            )
        )
        summary[["motif_hit_count", "genes_with_hit"]] = (
            summary[["motif_hit_count", "genes_with_hit"]].fillna(0).astype(int)
        )
        summary["hits_per_gene"] = summary["motif_hit_count"] / summary["n_genes"]
        summary["hits_per_kb"] = summary["motif_hit_count"].div(
            summary["total_promoter_bp"].replace(0, pd.NA) / 1000.0
        )
        summary = summary[HOG_DISTRIBUTION_COLUMNS].sort_values(
            ["HOG_ID", "element"], kind="stable"
        )

    unassigned_genes = int(genes["HOG_ID"].eq("Unassigned").sum())
    qc_status = "PASS_WITH_UNASSIGNED_HOG" if unassigned_genes else "PASS"
    qc = pd.DataFrame(
        [
            {
                "total_promoter_genes": int(genes["stable_id"].nunique()),
                "assigned_hog_genes": int(genes["stable_id"].nunique()) - unassigned_genes,
                "unassigned_genes": unassigned_genes,
                "n_hogs_including_unassigned": int(genes["HOG_ID"].nunique()),
                "n_elements": len(element_names),
                "qc_status": qc_status,
                "scientific_boundary": (
                    "HOG-level motif-hit composition is descriptive and is not enrichment, "
                    "TF binding or causal regulation evidence."
                ),
            }
        ]
    )
    return summary.reset_index(drop=True), qc


def _gene_metadata(coordinates: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        coordinates,
        ("stable_id", "species_id", "gene_id", "promoter_length"),
        "promoter coordinates",
    )
    _require_columns(members, ("stable_id",), "family members")
    if coordinates["stable_id"].astype(str).duplicated().any():
        raise ValueError("Promoter coordinates contain duplicate stable_id values.")
    if members["stable_id"].astype(str).duplicated().any():
        raise ValueError("Family members contain duplicate stable_id values.")

    metadata_columns = [
        column for column in ("stable_id", "subfamily", "group") if column in members.columns
    ]
    metadata = coordinates.copy()
    metadata["stable_id"] = metadata["stable_id"].astype(str)
    metadata = metadata.merge(
        members[metadata_columns].assign(stable_id=lambda frame: frame["stable_id"].astype(str)),
        on="stable_id",
        how="left",
        validate="one_to_one",
    )
    for column in ("species_id", "subfamily", "group"):
        if column not in metadata.columns:
            metadata[column] = pd.NA
        metadata[column] = _normalize_labels(metadata[column])
    metadata["promoter_length"] = pd.to_numeric(metadata["promoter_length"], errors="coerce")
    if metadata["promoter_length"].isna().any():
        raise ValueError("Promoter coordinates contain non-numeric promoter_length values.")
    if (metadata["promoter_length"] < 0).any():
        raise ValueError("Promoter coordinates contain negative promoter_length values.")
    return metadata


def _aggregate_level(
    elements: pd.DataFrame,
    metadata: pd.DataFrame,
    aggregation_level: str,
    dimensions: Sequence[str],
) -> tuple[pd.DataFrame, dict[str, object]]:
    missing_annotation = metadata[list(dimensions)].isna().any(axis=1)
    eligible = metadata.loc[~missing_annotation].copy()
    element_names = sorted(elements["element"].dropna().astype(str).unique())

    if eligible.empty:
        qc = {
            "aggregation_level": aggregation_level,
            "required_annotations": ",".join(dimensions),
            "total_genes": int(metadata["stable_id"].nunique()),
            "eligible_genes": 0,
            "excluded_genes_missing_annotation": int(metadata["stable_id"].nunique()),
            "n_cells": 0,
            "n_elements": len(element_names),
            "complete_grid_rows": 0,
            "cells_zero_promoter_bp": 0,
            "zscore_axis": "PER_ELEMENT_ACROSS_CELLS",
            "zscore_ddof": 0,
            "qc_status": "NO_ELIGIBLE_GENES",
        }
        return pd.DataFrame(columns=DISTRIBUTION_COLUMNS), qc

    cells = (
        eligible.groupby(list(dimensions), dropna=False)
        .agg(
            n_genes=("stable_id", "nunique"),
            total_promoter_bp=("promoter_length", "sum"),
        )
        .reset_index()
    )
    cells["cell_id"] = _cell_id(cells, dimensions)
    zero_promoter_cells = int((cells["total_promoter_bp"] <= 0).sum())

    if not element_names:
        qc = {
            "aggregation_level": aggregation_level,
            "required_annotations": ",".join(dimensions),
            "total_genes": int(metadata["stable_id"].nunique()),
            "eligible_genes": int(eligible["stable_id"].nunique()),
            "excluded_genes_missing_annotation": int(
                metadata.loc[missing_annotation, "stable_id"].nunique()
            ),
            "n_cells": len(cells),
            "n_elements": 0,
            "complete_grid_rows": 0,
            "cells_zero_promoter_bp": zero_promoter_cells,
            "zscore_axis": "PER_ELEMENT_ACROSS_CELLS",
            "zscore_ddof": 0,
            "qc_status": "NO_ELEMENTS",
        }
        return pd.DataFrame(columns=DISTRIBUTION_COLUMNS), qc

    hits = elements[["stable_id", "element"]].copy()
    hits["stable_id"] = hits["stable_id"].astype(str)
    hits["element"] = hits["element"].astype(str)
    hits = hits.merge(
        eligible[["stable_id", *dimensions]],
        on="stable_id",
        how="inner",
        validate="many_to_one",
    )
    counts = (
        hits.groupby([*dimensions, "element"], dropna=False)
        .agg(
            motif_hit_count=("stable_id", "size"),
            genes_with_hit=("stable_id", "nunique"),
        )
        .reset_index()
    )
    complete = cells.assign(_cross=1).merge(
        pd.DataFrame({"element": element_names, "_cross": 1}), on="_cross"
    )
    complete = complete.drop(columns="_cross").merge(
        counts,
        on=[*dimensions, "element"],
        how="left",
        validate="one_to_one",
    )
    complete[["motif_hit_count", "genes_with_hit"]] = (
        complete[["motif_hit_count", "genes_with_hit"]].fillna(0).astype(int)
    )
    complete["hits_per_gene"] = complete["motif_hit_count"] / complete["n_genes"]
    complete["hits_per_kb"] = complete["motif_hit_count"].div(
        complete["total_promoter_bp"].replace(0, pd.NA) / 1000.0
    )
    complete["aggregation_level"] = aggregation_level
    for dimension in ("species_id", "subfamily", "group"):
        if dimension not in complete.columns:
            complete[dimension] = "NOT_APPLICABLE"
    complete["zscore_motif_hit_count"] = pd.NA
    complete["raw_zscore_status"] = pd.NA
    complete["zscore_hits_per_kb"] = pd.NA
    complete["rate_zscore_status"] = pd.NA
    for _, index in complete.groupby("element", sort=False).groups.items():
        raw_zscores, raw_statuses = _zscore_with_status(complete.loc[index, "motif_hit_count"])
        rate_zscores, rate_statuses = _zscore_with_status(complete.loc[index, "hits_per_kb"])
        complete.loc[index, "zscore_motif_hit_count"] = raw_zscores
        complete.loc[index, "raw_zscore_status"] = raw_statuses
        complete.loc[index, "zscore_hits_per_kb"] = rate_zscores
        complete.loc[index, "rate_zscore_status"] = rate_statuses
    complete["zscore_motif_hit_count"] = complete["zscore_motif_hit_count"].astype("Float64")
    complete["zscore_hits_per_kb"] = complete["zscore_hits_per_kb"].astype("Float64")
    complete["zscore_axis"] = "PER_ELEMENT_ACROSS_CELLS"
    complete["zscore_ddof"] = 0
    complete = complete[DISTRIBUTION_COLUMNS].sort_values(["cell_id", "element"], kind="stable")

    qc_status = "PASS"
    if zero_promoter_cells:
        qc_status = "ZERO_PROMOTER_LENGTH"
    qc = {
        "aggregation_level": aggregation_level,
        "required_annotations": ",".join(dimensions),
        "total_genes": int(metadata["stable_id"].nunique()),
        "eligible_genes": int(eligible["stable_id"].nunique()),
        "excluded_genes_missing_annotation": int(
            metadata.loc[missing_annotation, "stable_id"].nunique()
        ),
        "n_cells": len(cells),
        "n_elements": len(element_names),
        "complete_grid_rows": len(complete),
        "cells_zero_promoter_bp": zero_promoter_cells,
        "zscore_axis": "PER_ELEMENT_ACROSS_CELLS",
        "zscore_ddof": 0,
        "qc_status": qc_status,
    }
    return complete, qc


def build_promoter_distributions(
    elements: pd.DataFrame,
    coordinates: pd.DataFrame,
    members: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build zero-complete promoter summaries with explicit denominators and z-scores."""

    _require_columns(elements, ("stable_id", "element"), "promoter elements")
    metadata = _gene_metadata(coordinates, members)
    normalized_elements = elements[["stable_id", "element"]].copy()
    normalized_elements["stable_id"] = normalized_elements["stable_id"].astype(str)
    normalized_elements["element"] = _normalize_labels(normalized_elements["element"])
    normalized_elements = normalized_elements.dropna(subset=["element"])
    unknown = sorted(set(normalized_elements["stable_id"]).difference(metadata["stable_id"]))
    if unknown:
        raise ValueError(
            "Promoter elements contain stable IDs absent from promoter coordinates: "
            + ", ".join(unknown[:10])
        )

    distributions: list[pd.DataFrame] = []
    qc_rows: list[dict[str, object]] = []
    for aggregation_level, dimensions in AGGREGATION_DIMENSIONS.items():
        distribution, qc = _aggregate_level(
            normalized_elements,
            metadata,
            aggregation_level,
            dimensions,
        )
        distributions.append(distribution)
        qc_rows.append(qc)
    combined = pd.concat(distributions, ignore_index=True)
    if combined.empty:
        combined = pd.DataFrame(columns=DISTRIBUTION_COLUMNS)
    return combined, pd.DataFrame(qc_rows, columns=QC_COLUMNS)
