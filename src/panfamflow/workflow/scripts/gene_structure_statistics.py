"""Auditable non-parametric comparisons for target-family structure metrics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Return Benjamini-Hochberg adjusted p-values in input order."""

    if not p_values:
        return []
    indexed = sorted(enumerate(float(value) for value in p_values), key=lambda item: item[1])
    adjusted = [math.nan] * len(indexed)
    running = 1.0
    total = len(indexed)
    for reverse_rank, (original_index, p_value) in enumerate(reversed(indexed), start=1):
        rank = total - reverse_rank + 1
        running = min(running, p_value * total / rank)
        adjusted[original_index] = min(1.0, running)
    return adjusted


def describe_panel_inference(values: Sequence[Sequence[float]], *, min_group_units: int = 2) -> str:
    """Return a concise warning that keeps descriptive plots inferentially honest."""

    arrays = [np.asarray(group_values, dtype=float) for group_values in values]
    arrays = [group_values[np.isfinite(group_values)] for group_values in arrays]
    notes: list[str] = []
    if not arrays or any(group_values.size < min_group_units for group_values in arrays):
        notes.append(f"Inference withheld: <{min_group_units} species units in at least one group")
    combined = np.concatenate(arrays) if arrays else np.asarray([], dtype=float)
    if combined.size and np.ptp(combined) == 0:
        notes.append("No between-unit variation")
    elif arrays and min(group_values.size for group_values in arrays) < 5:
        notes.append("Low species replication: <5 units in at least one group")
    return "\n".join(notes)


def _clean_group_values(table: pd.DataFrame, group_field: str) -> pd.DataFrame:
    required = {"stable_id", "species_id", group_field}
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError(f"Missing columns for {group_field} comparison: {', '.join(missing)}")
    clean = table.copy()
    if "structure_qc" in clean.columns:
        clean = clean.loc[clean["structure_qc"].astype(str) == "PASS"].copy()
    clean = clean.loc[clean[group_field].notna() & clean["species_id"].notna()].copy()
    clean[group_field] = clean[group_field].astype(str).str.strip()
    clean["species_id"] = clean["species_id"].astype(str).str.strip()
    clean = clean.loc[(clean[group_field] != "") & (clean["species_id"] != "")].copy()
    assignments = clean.groupby("stable_id", observed=True).agg(
        species_assignments=("species_id", "nunique"),
        group_assignments=(group_field, "nunique"),
        row_count=("stable_id", "size"),
    )
    conflicting = assignments.loc[
        (assignments["species_assignments"] > 1) | (assignments["group_assignments"] > 1)
    ]
    if not conflicting.empty:
        raise ValueError(
            f"Found conflicting {group_field} assignments for stable IDs: "
            + ", ".join(conflicting.index.astype(str).tolist()[:10])
        )
    duplicated = assignments.loc[assignments["row_count"] > 1]
    if not duplicated.empty:
        raise ValueError(
            "Gene-structure metrics must contain one row per stable_id; duplicates: "
            + ", ".join(duplicated.index.astype(str).tolist()[:10])
        )
    return clean


def compare_grouped_metrics(
    table: pd.DataFrame,
    *,
    group_field: str,
    metrics: Sequence[str],
    min_group_units: int = 2,
    alpha: float = 0.05,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compare grouped structure metrics using species medians as inference units.

    Gene-level rows remain available for descriptive medians and counts, but
    inferential tests operate on one median per ``species_id x group`` cell.
    This prevents multiple target-family genes from one species being silently
    treated as independent biological replicates.
    """

    if min_group_units < 2:
        raise ValueError("min_group_units must be at least 2")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    clean = _clean_group_values(table, group_field)
    global_rows: list[dict[str, object]] = []
    pairwise_rows: list[dict[str, object]] = []
    qc_rows: list[dict[str, object]] = []
    scope = group_field.upper()

    for metric in metrics:
        if metric not in clean.columns:
            raise ValueError(f"Unknown gene-structure metric: {metric}")
        metric_rows = clean.copy()
        metric_rows[metric] = pd.to_numeric(metric_rows[metric], errors="coerce")
        metric_rows = metric_rows.loc[metric_rows[metric].notna()].copy()
        units = (
            metric_rows.groupby(["species_id", group_field], as_index=False, observed=True)
            .agg(unit_value=(metric, "median"), n_genes=("stable_id", "nunique"))
            .sort_values([group_field, "species_id"])
            .reset_index(drop=True)
        )
        groups = sorted(units[group_field].astype(str).unique())
        unit_values = {
            group: units.loc[units[group_field].astype(str) == group, "unit_value"].to_numpy(
                dtype=float
            )
            for group in groups
        }
        eligible = {
            group: values for group, values in unit_values.items() if len(values) >= min_group_units
        }
        all_eligible_values = [value for values in eligible.values() for value in values]
        h_statistic = math.nan
        global_p = math.nan
        if len(eligible) < 2:
            global_status = "INSUFFICIENT_GROUP_UNITS"
            inference_warning = "INSUFFICIENT_SPECIES_REPLICATION"
        elif np.ptp(np.asarray(all_eligible_values, dtype=float)) == 0:
            h_statistic = 0.0
            global_p = 1.0
            global_status = "ZERO_VARIANCE"
            inference_warning = "NO_BETWEEN_UNIT_VARIATION"
        else:
            result = kruskal(*eligible.values(), nan_policy="omit")
            h_statistic = float(result.statistic)
            global_p = float(result.pvalue)
            global_status = "PASS"
            inference_warning = (
                "LOW_SPECIES_REPLICATION"
                if min(len(values) for values in eligible.values()) < 5
                else "NONE"
            )
        global_rows.append(
            {
                "comparison_scope": scope,
                "group_field": group_field,
                "metric": metric,
                "analysis_unit": "SPECIES_MEDIAN",
                "test_name": "Kruskal-Wallis",
                "n_groups_observed": len(groups),
                "n_groups_eligible": len(eligible),
                "n_genes": int(metric_rows["stable_id"].nunique()),
                "n_species": int(metric_rows["species_id"].nunique()),
                "n_species_group_units": int(units.shape[0]),
                "min_group_units": min_group_units,
                "h_statistic": h_statistic,
                "p_value": global_p,
                "alpha": alpha,
                "test_status": global_status,
                "inference_warning": inference_warning,
            }
        )

        metric_pair_indexes: list[int] = []
        metric_pair_pvalues: list[float] = []
        for group_1, group_2 in combinations(groups, 2):
            values_1 = unit_values[group_1]
            values_2 = unit_values[group_2]
            genes_1 = metric_rows.loc[metric_rows[group_field].astype(str) == group_1]
            genes_2 = metric_rows.loc[metric_rows[group_field].astype(str) == group_2]
            effect = math.nan
            u_statistic = math.nan
            pair_p = math.nan
            if values_1.size and values_2.size:
                descriptive_u = mannwhitneyu(
                    values_1, values_2, alternative="two-sided", method="auto"
                )
                u_statistic = float(descriptive_u.statistic)
                effect = float(2 * u_statistic / (values_1.size * values_2.size) - 1)
            if values_1.size < min_group_units or values_2.size < min_group_units:
                pair_status = "INSUFFICIENT_GROUP_UNITS"
                pair_warning = "INSUFFICIENT_SPECIES_REPLICATION"
            elif global_status != "PASS" or not math.isfinite(global_p) or global_p >= alpha:
                pair_status = "SKIPPED_GLOBAL_NOT_SIGNIFICANT"
                pair_warning = inference_warning
            else:
                pair_p = float(descriptive_u.pvalue)
                pair_status = "PASS"
                pair_warning = inference_warning
            pairwise_rows.append(
                {
                    "comparison_scope": scope,
                    "group_field": group_field,
                    "metric": metric,
                    "analysis_unit": "SPECIES_MEDIAN",
                    "group_1": group_1,
                    "group_2": group_2,
                    "n_genes_1": int(genes_1["stable_id"].nunique()),
                    "n_genes_2": int(genes_2["stable_id"].nunique()),
                    "n_species_1": int(values_1.size),
                    "n_species_2": int(values_2.size),
                    "median_gene_1": float(genes_1[metric].median()),
                    "median_gene_2": float(genes_2[metric].median()),
                    "median_species_unit_1": float(np.median(values_1)),
                    "median_species_unit_2": float(np.median(values_2)),
                    "median_species_unit_difference": float(
                        np.median(values_1) - np.median(values_2)
                    ),
                    "rank_biserial_effect": effect,
                    "test_name": "Mann-Whitney U",
                    "u_statistic": u_statistic,
                    "global_p_value": global_p,
                    "p_value": pair_p,
                    "p_adjusted_bh": math.nan,
                    "alpha": alpha,
                    "test_status": pair_status,
                    "inference_warning": pair_warning,
                }
            )
            if math.isfinite(pair_p):
                metric_pair_indexes.append(len(pairwise_rows) - 1)
                metric_pair_pvalues.append(pair_p)
        for row_index, adjusted in zip(
            metric_pair_indexes, benjamini_hochberg(metric_pair_pvalues), strict=True
        ):
            pairwise_rows[row_index]["p_adjusted_bh"] = adjusted

        qc_rows.append(
            {
                "comparison_scope": scope,
                "group_field": group_field,
                "metric": metric,
                "input_gene_rows": int(table.shape[0]),
                "eligible_gene_rows": int(metric_rows.shape[0]),
                "excluded_gene_rows": int(table.shape[0] - metric_rows.shape[0]),
                "observed_groups": len(groups),
                "eligible_groups": len(eligible),
                "eligible_species_group_units": int(units.shape[0]),
                "min_group_units": min_group_units,
                "inference_unit": "SPECIES_MEDIAN",
                "qc_status": global_status,
                "inference_warning": inference_warning,
                "low_power_warning": bool(
                    eligible and min(len(values) for values in eligible.values()) < 5
                ),
            }
        )

    return pd.DataFrame(global_rows), pd.DataFrame(pairwise_rows), pd.DataFrame(qc_rows)


def plot_grouped_metrics(
    table: pd.DataFrame,
    *,
    group_fields: Sequence[str],
    metrics: Sequence[str],
    pdf_path: str | Path,
    png_path: str | Path,
    png_dpi: int,
    seed: int,
    min_group_units: int = 2,
) -> None:
    """Plot species-median structure values with deterministic jitter."""

    panels = [(group_field, metric) for group_field in group_fields for metric in metrics]
    n_panels = max(1, len(panels))
    n_columns = min(3, n_panels)
    n_rows = math.ceil(n_panels / n_columns)
    figure, axes = plt.subplots(
        n_rows,
        n_columns,
        figsize=(5.2 * n_columns, 4.1 * n_rows),
        squeeze=False,
        facecolor="white",
    )
    flat_axes = axes.ravel()
    rng = np.random.default_rng(seed)
    palette = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]

    for axis, (group_field, metric) in zip(flat_axes, panels, strict=False):
        clean = _clean_group_values(table, group_field)
        clean[metric] = pd.to_numeric(clean[metric], errors="coerce")
        clean = clean.loc[clean[metric].notna()].copy()
        units = (
            clean.groupby(["species_id", group_field], as_index=False, observed=True)[metric]
            .median()
            .sort_values([group_field, "species_id"])
        )
        groups = sorted(units[group_field].astype(str).unique())
        values = [
            units.loc[units[group_field].astype(str) == group, metric].to_numpy(dtype=float)
            for group in groups
        ]
        if not groups:
            axis.text(0.5, 0.5, "No eligible species-group units", ha="center", va="center")
            axis.set_axis_off()
            continue
        box = axis.boxplot(values, tick_labels=groups, patch_artist=True, showfliers=False)
        for index, patch in enumerate(box["boxes"]):
            patch.set_facecolor(palette[index % len(palette)])
            patch.set_alpha(0.35)
        for position, group_values in enumerate(values, start=1):
            jitter = rng.uniform(-0.08, 0.08, size=len(group_values))
            axis.scatter(
                np.full(len(group_values), position) + jitter,
                group_values,
                s=28,
                color=palette[(position - 1) % len(palette)],
                edgecolor="white",
                linewidth=0.5,
                zorder=3,
            )
        inference_note = describe_panel_inference(values, min_group_units=min_group_units)
        if inference_note:
            axis.text(
                0.02,
                0.98,
                inference_note,
                transform=axis.transAxes,
                ha="left",
                va="top",
                fontsize=8,
                color="#8B1A1A",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 2},
            )
        axis.set_title(f"{group_field}: {metric}")
        axis.set_xlabel(f"{group_field} (points are species medians)")
        axis.set_ylabel(metric)
        axis.tick_params(axis="x", rotation=30)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(False)

    for axis in flat_axes[len(panels) :]:
        axis.set_axis_off()
    figure.suptitle("Target-family gene-structure comparisons", fontsize=14)
    figure.tight_layout(rect=(0, 0, 1, 0.98))
    figure.savefig(pdf_path, bbox_inches="tight")
    figure.savefig(png_path, dpi=png_dpi, bbox_inches="tight")
    plt.close(figure)
