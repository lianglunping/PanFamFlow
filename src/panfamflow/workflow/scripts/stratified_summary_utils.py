"""Deterministic, auditable summaries reused by target-family modules."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from typing import Any

import pandas as pd

PAN_CLASS_ORDER = ["Core", "Soft-core", "Shell", "Cloud"]
MISSING_LABELS = {"", "NA", "N/A", "NONE", "NULL", "NAN", "<NA>"}


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")


def _assert_unique(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    if frame.duplicated(list(columns)).any():
        raise ValueError(f"{label} contains duplicate keys: {', '.join(columns)}")


def _labels(values: pd.Series, missing_label: str = "Unassigned") -> pd.Series:
    normalized = values.astype("string").str.strip()
    return normalized.mask(normalized.str.upper().isin(MISSING_LABELS), missing_label).fillna(
        missing_label
    )


def _cross_grid(dimensions: dict[str, Sequence[str]]) -> pd.DataFrame:
    columns = list(dimensions)
    rows = itertools.product(*(dimensions[column] for column in columns))
    return pd.DataFrame(rows, columns=columns)


def _safe_fraction(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return pd.to_numeric(numerator, errors="coerce").div(
        pd.to_numeric(denominator, errors="coerce").replace(0, pd.NA)
    )


def numeric_pivot(
    frame: pd.DataFrame,
    *,
    index: str,
    columns: str,
    values: str,
    column_order: Sequence[str] | None = None,
    fill_value: float | None = None,
) -> pd.DataFrame:
    """Pivot a table into a float matrix safe for matplotlib across pandas versions."""

    matrix = frame.pivot(index=index, columns=columns, values=values)
    if column_order is not None:
        matrix = matrix.reindex(columns=list(column_order))
    matrix = matrix.apply(pd.to_numeric, errors="coerce")
    if fill_value is not None:
        matrix = matrix.fillna(fill_value)
    return matrix.astype(float)


def nonzero_composition(
    frame: pd.DataFrame,
    *,
    label_column: str,
    count_column: str = "count",
) -> tuple[list[str], list[int]]:
    """Return only positive composition slices so zero labels cannot overlap."""

    _require_columns(frame, (label_column, count_column), "composition table")
    counts = pd.to_numeric(frame[count_column], errors="raise").astype(int)
    positive = frame.loc[counts > 0]
    return positive[label_column].astype(str).tolist(), counts.loc[counts > 0].tolist()


def build_family_distribution(
    members: pd.DataFrame,
    *,
    species_ids: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Build a zero-complete species-by-subfamily gene-count grid."""

    _require_columns(members, ("stable_id", "species_id", "subfamily"), "family members")
    _assert_unique(members, ("stable_id",), "family members")
    working = members[["stable_id", "species_id", "subfamily"]].copy()
    working["species_id"] = _labels(working["species_id"])
    working["subfamily"] = _labels(working["subfamily"])
    species = list(dict.fromkeys(str(item) for item in species_ids or []))
    observed_species = sorted(working["species_id"].unique())
    species.extend(item for item in observed_species if item not in species)
    subfamilies = sorted(working["subfamily"].unique())
    grid = _cross_grid({"species_id": species, "subfamily": subfamilies})
    counts = (
        working.groupby(["species_id", "subfamily"], as_index=False)["stable_id"]
        .nunique()
        .rename(columns={"stable_id": "gene_count"})
    )
    result = grid.merge(counts, on=["species_id", "subfamily"], how="left", validate="one_to_one")
    result["gene_count"] = result["gene_count"].fillna(0).astype(int)
    result["species_gene_total"] = result.groupby("species_id")["gene_count"].transform("sum")
    result["within_species_fraction"] = _safe_fraction(
        result["gene_count"], result["species_gene_total"]
    )
    result["counting_unit"] = "GENE"
    result["absence_interpretation"] = "ANNOTATION_COUNT_NOT_VALIDATED_GENE_LOSS"
    return result.sort_values(["species_id", "subfamily"], kind="stable").reset_index(drop=True)


def _membership_with_metadata(
    membership: pd.DataFrame,
    classification: pd.DataFrame,
    members: pd.DataFrame,
) -> pd.DataFrame:
    _require_columns(membership, ("HOG_ID", "stable_id", "species_id"), "HOG membership")
    _require_columns(classification, ("HOG_ID", "pan_family_class"), "pan classification")
    _require_columns(
        members,
        ("stable_id", "species_id"),
        "family members",
    )
    _assert_unique(membership, ("stable_id",), "HOG membership")
    _assert_unique(classification, ("HOG_ID",), "pan classification")
    _assert_unique(members, ("stable_id",), "family members")
    metadata = members.copy()
    for column in ("subfamily", "group"):
        if column not in metadata.columns:
            metadata[column] = pd.NA
    metadata = metadata[["stable_id", "species_id", "subfamily", "group"]]
    metadata = metadata.rename(columns={"species_id": "member_species_id"})
    joined = membership[["HOG_ID", "stable_id", "species_id"]].merge(
        metadata,
        on="stable_id",
        how="left",
        validate="one_to_one",
    )
    mismatch = joined.loc[
        joined["member_species_id"].notna()
        & (joined["species_id"].astype(str) != joined["member_species_id"].astype(str))
    ]
    if not mismatch.empty:
        raise ValueError("HOG membership species_id conflicts with family member metadata.")
    joined = joined.merge(
        classification[["HOG_ID", "pan_family_class"]],
        on="HOG_ID",
        how="left",
        validate="many_to_one",
    )
    for column in ("species_id", "subfamily", "group", "pan_family_class"):
        joined[column] = _labels(joined[column])
    return joined.drop(columns="member_species_id")


def build_pan_family_summaries(
    classification: pd.DataFrame,
    membership: pd.DataFrame,
    members: pd.DataFrame,
    *,
    species_ids: Sequence[str],
) -> dict[str, pd.DataFrame]:
    """Summarize pan classes without mixing gene and HOG denominators."""

    joined = _membership_with_metadata(membership, classification, members)
    classes = PAN_CLASS_ORDER.copy()

    class_rows: list[dict[str, Any]] = []
    for counting_unit, frame, key in (
        ("HOG", classification, "HOG_ID"),
        ("GENE", joined, "stable_id"),
    ):
        counts = frame.groupby("pan_family_class")[key].nunique().reindex(classes, fill_value=0)
        denominator = int(counts.sum())
        for pan_class, count in counts.items():
            class_rows.append(
                {
                    "counting_unit": counting_unit,
                    "pan_family_class": pan_class,
                    "count": int(count),
                    "denominator": denominator,
                    "fraction": count / denominator if denominator else pd.NA,
                }
            )
    class_summary = pd.DataFrame(class_rows)

    species = list(dict.fromkeys(str(item) for item in species_ids))
    species_grid = _cross_grid({"species_id": species, "pan_family_class": classes})
    species_counts = joined.groupby(["species_id", "pan_family_class"], as_index=False).agg(
        gene_count=("stable_id", "nunique"), hog_count=("HOG_ID", "nunique")
    )
    species_summary = species_grid.merge(
        species_counts,
        on=["species_id", "pan_family_class"],
        how="left",
        validate="one_to_one",
    )
    species_summary[["gene_count", "hog_count"]] = (
        species_summary[["gene_count", "hog_count"]].fillna(0).astype(int)
    )
    species_summary["species_gene_total"] = species_summary.groupby("species_id")[
        "gene_count"
    ].transform("sum")
    species_summary["species_hog_total"] = species_summary.groupby("species_id")[
        "hog_count"
    ].transform("sum")
    species_summary["gene_fraction"] = _safe_fraction(
        species_summary["gene_count"], species_summary["species_gene_total"]
    )
    species_summary["hog_fraction"] = _safe_fraction(
        species_summary["hog_count"], species_summary["species_hog_total"]
    )

    subfamilies = sorted(joined["subfamily"].unique())
    subfamily_grid = _cross_grid({"subfamily": subfamilies, "pan_family_class": classes})
    subfamily_counts = joined.groupby(["subfamily", "pan_family_class"], as_index=False).agg(
        gene_count=("stable_id", "nunique"), hog_count=("HOG_ID", "nunique")
    )
    subfamily_summary = subfamily_grid.merge(
        subfamily_counts,
        on=["subfamily", "pan_family_class"],
        how="left",
        validate="one_to_one",
    )
    subfamily_summary[["gene_count", "hog_count"]] = (
        subfamily_summary[["gene_count", "hog_count"]].fillna(0).astype(int)
    )
    subfamily_summary["subfamily_gene_total"] = subfamily_summary.groupby("subfamily")[
        "gene_count"
    ].transform("sum")
    subfamily_summary["subfamily_hog_total"] = subfamily_summary.groupby("subfamily")[
        "hog_count"
    ].transform("sum")
    subfamily_summary["gene_fraction"] = _safe_fraction(
        subfamily_summary["gene_count"], subfamily_summary["subfamily_gene_total"]
    )
    subfamily_summary["hog_fraction"] = _safe_fraction(
        subfamily_summary["hog_count"], subfamily_summary["subfamily_hog_total"]
    )
    return {
        "class_summary": class_summary,
        "species_class_summary": species_summary,
        "subfamily_class_summary": subfamily_summary,
    }


def build_duplication_summaries(
    modes: pd.DataFrame,
    members: pd.DataFrame,
    membership: pd.DataFrame,
    classification: pd.DataFrame,
) -> pd.DataFrame:
    """Build zero-complete duplication-mode summaries for three strata."""

    _require_columns(modes, ("stable_id", "species_id", "duplication_mode"), "duplication modes")
    _assert_unique(modes, ("stable_id",), "duplication modes")
    annotations = _membership_with_metadata(membership, classification, members)
    working = modes[["stable_id", "species_id", "duplication_mode"]].merge(
        annotations[["stable_id", "subfamily", "pan_family_class"]],
        on="stable_id",
        how="left",
        validate="one_to_one",
    )
    for column in ("species_id", "subfamily", "pan_family_class", "duplication_mode"):
        working[column] = _labels(working[column])
    duplication_modes = sorted(working["duplication_mode"].unique())
    results: list[pd.DataFrame] = []
    for name, column in (
        ("SPECIES", "species_id"),
        ("SUBFAMILY", "subfamily"),
        ("PAN_CLASS", "pan_family_class"),
    ):
        strata = sorted(working[column].unique())
        grid = _cross_grid({"stratum": strata, "duplication_mode": duplication_modes})
        counts = (
            working.rename(columns={column: "stratum"})
            .groupby(["stratum", "duplication_mode"], as_index=False)["stable_id"]
            .nunique()
            .rename(columns={"stable_id": "gene_count"})
        )
        summary = grid.merge(
            counts,
            on=["stratum", "duplication_mode"],
            how="left",
            validate="one_to_one",
        )
        summary["gene_count"] = summary["gene_count"].fillna(0).astype(int)
        summary["stratum_gene_total"] = summary.groupby("stratum")["gene_count"].transform("sum")
        summary["within_stratum_fraction"] = _safe_fraction(
            summary["gene_count"], summary["stratum_gene_total"]
        )
        summary.insert(0, "stratification", name)
        results.append(summary)
    return pd.concat(results, ignore_index=True)


def _pair_stratum(left: object, right: object) -> str:
    left_label = _labels(pd.Series([left])).iloc[0]
    right_label = _labels(pd.Series([right])).iloc[0]
    if left_label == "Unassigned" or right_label == "Unassigned":
        return "Unassigned"
    return str(left_label) if left_label == right_label else "Mixed"


def annotate_kaks_pairs(
    pairs: pd.DataFrame,
    members: pd.DataFrame,
    membership: pd.DataFrame,
    classification: pd.DataFrame,
    modes: pd.DataFrame,
) -> pd.DataFrame:
    """Attach symmetric strata to Ka/Ks pairs without forcing conflicts."""

    _require_columns(pairs, ("stable_id_1", "stable_id_2"), "Ka/Ks pairs")
    _assert_unique(members, ("stable_id",), "family members")
    annotations = _membership_with_metadata(membership, classification, members)
    _require_columns(modes, ("stable_id", "duplication_mode"), "duplication modes")
    _assert_unique(modes, ("stable_id",), "duplication modes")
    metadata = annotations[["stable_id", "subfamily", "group", "pan_family_class"]].merge(
        modes[["stable_id", "duplication_mode"]],
        on="stable_id",
        how="left",
        validate="one_to_one",
    )
    result = pairs.copy()
    for suffix, key in (("1", "stable_id_1"), ("2", "stable_id_2")):
        renamed = metadata.rename(
            columns={
                column: f"{column}_{suffix}" for column in metadata.columns if column != "stable_id"
            }
        )
        result = result.merge(
            renamed,
            left_on=key,
            right_on="stable_id",
            how="left",
            validate="many_to_one",
        ).drop(columns="stable_id")
    for source, target in (
        ("subfamily", "subfamily_stratum"),
        ("group", "group_stratum"),
        ("pan_family_class", "pan_class_stratum"),
        ("duplication_mode", "duplication_mode_stratum"),
    ):
        result[target] = [
            _pair_stratum(left, right)
            for left, right in zip(result[f"{source}_1"], result[f"{source}_2"], strict=True)
        ]
    return result


def summarize_kaks_strata(pairs: pd.DataFrame) -> pd.DataFrame:
    """Return descriptive Ka/Ks summaries for every declared pair stratum."""

    rows: list[dict[str, Any]] = []
    for name, column in (
        ("SUBFAMILY", "subfamily_stratum"),
        ("GROUP", "group_stratum"),
        ("PAN_CLASS", "pan_class_stratum"),
        ("DUPLICATION_MODE", "duplication_mode_stratum"),
    ):
        _require_columns(pairs, (column,), "annotated Ka/Ks pairs")
        for stratum, group in pairs.groupby(column, dropna=False, sort=True):
            for metric in ("Ka", "Ks", "Ka_Ks"):
                values = pd.to_numeric(group[metric], errors="coerce").dropna()
                rows.append(
                    {
                        "stratification": name,
                        "stratum": str(stratum),
                        "metric": metric,
                        "n_pairs": len(values),
                        "median": values.median() if len(values) else pd.NA,
                        "q1": values.quantile(0.25) if len(values) else pd.NA,
                        "q3": values.quantile(0.75) if len(values) else pd.NA,
                        "minimum": values.min() if len(values) else pd.NA,
                        "maximum": values.max() if len(values) else pd.NA,
                        "inference_status": "DESCRIPTIVE_ONLY_NONINDEPENDENT_PAIRS",
                    }
                )
    return pd.DataFrame(rows)
