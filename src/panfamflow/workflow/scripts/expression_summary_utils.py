"""Descriptive expression summaries with explicit sample and comparison boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from workflow_utils import read_delimited_table, save_table, save_workbook


def scale_expression_matrix(
    matrix: pd.DataFrame,
    sample_columns: list[str],
    transform: str,
) -> pd.DataFrame:
    """Return the exact numeric matrix used by Fig33 with row metadata attached."""

    values = matrix[sample_columns].astype(float).to_numpy()
    transformed = np.log2(values + 1.0)
    if transform == "log2_tpm1_zscore":
        valid = np.isfinite(transformed)
        counts = valid.sum(axis=1, keepdims=True)
        means = np.divide(
            np.nansum(transformed, axis=1, keepdims=True),
            counts,
            out=np.zeros((transformed.shape[0], 1), dtype=float),
            where=counts > 0,
        )
        centered = transformed - means
        variance = np.divide(
            np.nansum(centered**2, axis=1, keepdims=True),
            counts,
            out=np.zeros((transformed.shape[0], 1), dtype=float),
            where=counts > 0,
        )
        standard_deviations = np.sqrt(variance)
        standard_deviations[(standard_deviations == 0) | ~np.isfinite(standard_deviations)] = 1.0
        transformed = centered / standard_deviations
        transformed[~valid] = np.nan
    elif transform != "log2_tpm1":
        raise ValueError(f"Unsupported expression heatmap transform: {transform}")
    metadata_columns = [
        column
        for column in ("stable_id", "species_id", "gene_id", "group", "subfamily")
        if column in matrix.columns
    ]
    scaled = matrix[metadata_columns].copy()
    scaled[sample_columns] = transformed
    scaled["transform"] = transform
    return scaled


def save_expression_heatmap(
    scaled: pd.DataFrame,
    sample_columns: list[str],
    *,
    table_tsv: str,
    plot_pdf: str,
    plot_png: str,
    png_dpi: int,
) -> None:
    """Persist the Fig33 source table and render the matching heatmap."""

    save_table(scaled, table_tsv)
    values = scaled[sample_columns].to_numpy(dtype=float)
    fig_height = max(4.8, min(18.0, 0.18 * max(1, scaled.shape[0])))
    fig, axis = plt.subplots(figsize=(max(7.0, 0.35 * len(sample_columns)), fig_height))
    cmap = plt.get_cmap("viridis").with_extremes(bad="#d9d9d9")
    image = axis.imshow(
        np.ma.masked_invalid(values),
        aspect="auto",
        interpolation="nearest",
        cmap=cmap,
    )
    axis.set_xticks(range(len(sample_columns)), sample_columns, rotation=45, ha="right")
    if scaled.shape[0] <= 80 and "stable_id" in scaled:
        axis.set_yticks(range(scaled.shape[0]), scaled["stable_id"].astype(str), fontsize=6)
    else:
        axis.set_yticks([])
    axis.set_xlabel("Sample")
    axis.set_ylabel("Family gene")
    axis.set_title("Target-family expression heatmap")
    axis.grid(False)
    for spine in axis.spines.values():
        spine.set_visible(False)
    transform = str(scaled["transform"].iloc[0]) if not scaled.empty else "scaled expression"
    fig.colorbar(image, ax=axis, label=transform)
    fig.tight_layout()
    fig.savefig(plot_pdf, facecolor="white")
    fig.savefig(plot_png, dpi=png_dpi, facecolor="white")
    plt.close(fig)


def validate_sample_metadata(
    sample_columns: list[str], metadata_path: str | Path | None
) -> pd.DataFrame:
    """Return one audited metadata row per matrix column."""

    if metadata_path is None or not str(metadata_path).strip():
        return pd.DataFrame(
            {
                "sample_id": sample_columns,
                "sample_species_id": pd.NA,
                "condition": pd.NA,
                "tissue": pd.NA,
                "stress_type": "Other",
                "timepoint": pd.NA,
                "replicate": pd.NA,
                "batch": pd.NA,
                "metadata_status": "NOT_CONFIGURED",
            }
        )
    metadata = read_delimited_table(metadata_path)
    required = {"sample_id", "species_id", "condition", "replicate"}
    missing = sorted(required.difference(metadata.columns))
    if missing:
        raise ValueError(f"Sample metadata lacks required columns: {', '.join(missing)}")
    if metadata["sample_id"].astype(str).duplicated().any():
        raise ValueError("Sample metadata contains duplicate sample_id values.")
    matrix_samples = set(sample_columns)
    metadata_samples = set(metadata["sample_id"].astype(str))
    if matrix_samples != metadata_samples:
        raise ValueError(
            "Sample metadata and expression columns differ: "
            f"missing metadata={sorted(matrix_samples - metadata_samples)[:10]}, "
            f"extra metadata={sorted(metadata_samples - matrix_samples)[:10]}"
        )
    metadata = metadata.copy()
    metadata["sample_id"] = metadata["sample_id"].astype(str)
    metadata["sample_species_id"] = metadata["species_id"].astype(str)
    metadata["metadata_status"] = "PASS"
    for column, default in (
        ("tissue", pd.NA),
        ("stress_type", "Other"),
        ("timepoint", pd.NA),
        ("batch", pd.NA),
    ):
        if column not in metadata:
            metadata[column] = default
    return metadata[
        [
            "sample_id",
            "sample_species_id",
            "condition",
            "tissue",
            "stress_type",
            "timepoint",
            "replicate",
            "batch",
            "metadata_status",
        ]
    ].sort_values("sample_id")


def attach_pan_classes(
    long: pd.DataFrame,
    membership_path: str | Path | None,
    classification_path: str | Path | None,
) -> pd.DataFrame:
    """Attach HOG and pan class without inventing a fallback classification."""

    result = long.copy()
    if not membership_path or not classification_path:
        result["HOG_ID"] = pd.NA
        result["pan_family_class"] = pd.NA
        result["pan_class_status"] = "NOT_AVAILABLE"
        return result
    membership = pd.read_csv(membership_path, sep="\t", usecols=["stable_id", "HOG_ID"])
    classification = pd.read_csv(
        classification_path, sep="\t", usecols=["HOG_ID", "pan_family_class"]
    )
    if membership["stable_id"].duplicated().any():
        raise ValueError("Family HOG membership contains duplicate stable_id values.")
    membership = membership.merge(classification, on="HOG_ID", how="left", validate="many_to_one")
    result = result.merge(membership, on="stable_id", how="left", validate="many_to_one")
    result["pan_class_status"] = np.where(
        result["pan_family_class"].notna(), "AVAILABLE", "UNASSIGNED_HOG"
    )
    return result


def build_descriptive_summaries(long: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarize raw descriptive expression; no inferential statistics are implied."""

    observed = long.loc[
        long["measurement_status"].isin(["OBSERVED", "MEASURED", "ASSAYED_ZERO"])
        & long["expression_value"].notna()
    ].copy()
    observed["expression_value"] = pd.to_numeric(observed["expression_value"], errors="raise")
    gene_tissue_keys = [
        key
        for key in [
            "stable_id",
            "species_id",
            "gene_id",
            "group",
            "subfamily",
            "HOG_ID",
            "pan_family_class",
            "tissue",
            "condition",
            "stress_type",
        ]
        if key in observed.columns
    ]
    gene_condition = (
        observed.groupby(gene_tissue_keys, dropna=False, as_index=False)
        .agg(
            n_replicates=("expression_value", "size"),
            median_expression=("expression_value", "median"),
            mean_expression=("expression_value", "mean"),
            sd_expression=("expression_value", "std"),
        )
        .sort_values(gene_tissue_keys)
    )
    levels: list[tuple[str, list[str]]] = [
        ("OVERALL", []),
        ("SPECIES", ["species_id"]),
        ("SUBFAMILY", ["subfamily"]),
        ("GROUP", ["group"]),
        ("PAN_CLASS", ["pan_family_class"]),
        ("TISSUE", ["tissue"]),
        ("PAN_CLASS_TISSUE", ["pan_family_class", "tissue"]),
        ("GROUP_SUBFAMILY", ["group", "subfamily"]),
    ]
    rows: list[dict[str, Any]] = []
    for level, keys in levels:
        if any(key not in observed.columns for key in keys):
            continue
        grouped = [((), observed)] if not keys else observed.groupby(keys, dropna=False)
        for values, frame in grouped:
            if not isinstance(values, tuple):
                values = (values,)
            row: dict[str, Any] = {
                "aggregation_level": level,
                "n_observations": int(frame.shape[0]),
                "n_genes": int(frame["stable_id"].nunique()),
                "n_samples": int(frame["sample_id"].nunique()),
                "median_expression": frame["expression_value"].median(),
                "q1_expression": frame["expression_value"].quantile(0.25),
                "q3_expression": frame["expression_value"].quantile(0.75),
                "mean_expression": frame["expression_value"].mean(),
                "descriptive_status": "DESCRIPTIVE_ONLY",
            }
            row.update(dict(zip(keys, values, strict=True)))
            rows.append(row)
    return gene_condition, pd.DataFrame(rows)


def _save_distribution_plot(
    observed: pd.DataFrame,
    category: str | None,
    title: str,
    pdf: str,
    png: str,
    dpi: int,
) -> None:
    fig, axis = plt.subplots(
        figsize=(max(7.2, 0.75 * observed.get(category, pd.Series()).nunique()), 5.0)
    )
    if observed.empty or (category and category not in observed):
        axis.text(0.5, 0.5, "Required strata are not available", ha="center", va="center")
        axis.set_axis_off()
    else:
        plot = observed.copy()
        plot["log2_expression_plus_1"] = np.log2(plot["expression_value"].astype(float) + 1.0)
        if category is None:
            groups = [("All", plot["log2_expression_plus_1"].dropna().to_numpy())]
        else:
            groups = [
                (str(label), frame["log2_expression_plus_1"].dropna().to_numpy())
                for label, frame in plot.groupby(category, dropna=False, sort=True)
            ]
        groups = [(label, values) for label, values in groups if len(values)]
        if groups:
            axis.boxplot(
                [values for _, values in groups], tick_labels=[label for label, _ in groups]
            )
            axis.tick_params(axis="x", rotation=35)
            axis.set_ylabel("log2(expression + 1)")
            axis.set_title(title)
            axis.grid(False)
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)
        else:
            axis.text(0.5, 0.5, "No observed expression values", ha="center", va="center")
            axis.set_axis_off()
    fig.tight_layout()
    fig.savefig(pdf, facecolor="white")
    fig.savefig(png, dpi=dpi, facecolor="white")
    plt.close(fig)


def _save_heatmap(
    observed: pd.DataFrame,
    rows: str,
    columns: str,
    title: str,
    pdf: str,
    png: str,
    dpi: int,
) -> None:
    available = not observed.empty and rows in observed and columns in observed
    matrix = (
        observed.pivot_table(
            index=rows, columns=columns, values="expression_value", aggfunc="median", dropna=False
        )
        if available
        else pd.DataFrame()
    )
    fig, axis = plt.subplots(
        figsize=(max(7.2, 0.7 * max(1, matrix.shape[1])), max(4.8, 0.55 * max(1, matrix.shape[0])))
    )
    if matrix.empty:
        axis.text(0.5, 0.5, "Required strata are not available", ha="center", va="center")
        axis.set_axis_off()
    else:
        values = np.log2(matrix.to_numpy(dtype=float) + 1.0)
        image = axis.imshow(values, aspect="auto", cmap="viridis")
        axis.set_xticks(range(matrix.shape[1]), matrix.columns.astype(str), rotation=35, ha="right")
        axis.set_yticks(range(matrix.shape[0]), matrix.index.astype(str))
        axis.set_xlabel(columns)
        axis.set_ylabel(rows)
        axis.set_title(title)
        fig.colorbar(image, ax=axis, label="median log2(expression + 1)")
        for spine in axis.spines.values():
            spine.set_visible(False)
    fig.tight_layout()
    fig.savefig(pdf, facecolor="white")
    fig.savefig(png, dpi=dpi, facecolor="white")
    plt.close(fig)


def save_descriptive_expression_outputs(
    long: pd.DataFrame,
    gene_condition: pd.DataFrame,
    summary: pd.DataFrame,
    sample_metadata: pd.DataFrame,
    outputs: Any,
    png_dpi: int,
) -> None:
    save_table(sample_metadata, outputs.sample_metadata_audit)
    save_table(gene_condition, outputs.gene_condition)
    save_table(summary, outputs.stratified_summary)
    for level, destination in (
        ("PAN_CLASS", outputs.pan_class_table),
        ("PAN_CLASS_TISSUE", outputs.pan_tissue_table),
        ("GROUP_SUBFAMILY", outputs.group_subfamily_table),
    ):
        source = summary.loc[summary["aggregation_level"].eq(level)].copy()
        save_table(source, destination)
    save_workbook(
        {
            "sample_metadata": sample_metadata,
            "gene_condition": gene_condition,
            "stratified_summary": summary,
        },
        outputs.stratified_xlsx,
    )
    observed = long.loc[
        long["measurement_status"].isin(["OBSERVED", "MEASURED", "ASSAYED_ZERO"])
        & long["expression_value"].notna()
    ]
    _save_distribution_plot(
        observed,
        "species_id",
        "Target-family expression distribution by species/accession",
        outputs.overall_pdf,
        outputs.overall_png,
        png_dpi,
    )
    _save_distribution_plot(
        observed,
        "pan_family_class",
        "Target-family expression by pan-family class",
        outputs.pan_class_pdf,
        outputs.pan_class_png,
        png_dpi,
    )
    _save_heatmap(
        observed,
        "pan_family_class",
        "tissue",
        "Pan-family class by tissue (descriptive median)",
        outputs.pan_tissue_pdf,
        outputs.pan_tissue_png,
        png_dpi,
    )
    _save_heatmap(
        observed,
        "group",
        "subfamily",
        "Group by subfamily expression (descriptive median)",
        outputs.group_subfamily_pdf,
        outputs.group_subfamily_png,
        png_dpi,
    )
