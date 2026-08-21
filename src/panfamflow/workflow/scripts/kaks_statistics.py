"""Dependency-aware summaries for pairwise target-family Ka/Ks estimates."""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu


def _bh(p_values: Sequence[float]) -> list[float]:
    order = np.argsort(np.asarray(p_values, dtype=float))
    adjusted = np.full(len(order), np.nan)
    running = 1.0
    total = len(order)
    for rank_index in range(total - 1, -1, -1):
        original = int(order[rank_index])
        rank = rank_index + 1
        running = min(running, float(p_values[original]) * total / rank)
        adjusted[original] = min(1.0, running)
    return adjusted.tolist()


def build_cluster_source(
    pairs: pd.DataFrame,
    *,
    scope: str,
    stratum_columns: Sequence[str],
) -> pd.DataFrame:
    """Collapse dependent sequence pairs to one median per registered pair cluster."""

    required = {"pair_id", "group_id", "Ka_Ks", "qc_status", *stratum_columns}
    missing = sorted(required.difference(pairs.columns))
    if missing:
        raise ValueError(f"Ka/Ks pairs lack columns: {', '.join(missing)}")
    working = pairs.copy()
    working["Ka_Ks"] = pd.to_numeric(working["Ka_Ks"], errors="coerce")
    working["inference_eligible_pair"] = (
        working["qc_status"].astype(str).eq("PASS") & working["Ka_Ks"].notna()
    )
    working = working.loc[working["inference_eligible_pair"]].copy()
    working["cluster_id"] = working["group_id"].astype(str)
    working["stratum_label"] = working[list(stratum_columns)].astype(str).agg(" | ".join, axis=1)
    cluster_strata = working.groupby("cluster_id")["stratum_label"].nunique()
    rows = (
        working.groupby(["cluster_id", "stratum_label"], as_index=False)
        .agg(
            cluster_median_ka_ks=("Ka_Ks", "median"),
            n_pairs=("pair_id", "nunique"),
            minimum_ka_ks=("Ka_Ks", "min"),
            maximum_ka_ks=("Ka_Ks", "max"),
        )
        .sort_values(["stratum_label", "cluster_id"])
        .reset_index(drop=True)
    )
    rows.insert(0, "scope", scope)
    rows["analysis_unit"] = "PAIR_CLUSTER_MEDIAN"
    rows["cluster_stratum_count"] = rows["cluster_id"].map(cluster_strata).astype(int)
    rows["inference_eligible"] = rows["cluster_stratum_count"].eq(1)
    rows["inference_exclusion_reason"] = rows["inference_eligible"].map(
        {True: "NONE", False: "CLUSTER_SPANS_MULTIPLE_STRATA"}
    )
    rows["interpretation_flag"] = "PAIRWISE_KAKS_NOT_PROOF_OF_POSITIVE_SELECTION"
    return rows


def cluster_inference_tests(
    source: pd.DataFrame,
    *,
    min_units: int = 2,
    alpha: float = 0.05,
) -> pd.DataFrame:
    """Run global and guarded pairwise tests on independent cluster medians."""

    eligible = source.loc[source["inference_eligible"].astype(bool)].copy()
    groups = {
        str(label): group["cluster_median_ka_ks"].to_numpy(dtype=float)
        for label, group in eligible.groupby("stratum_label", sort=True)
    }
    scope = str(source["scope"].iloc[0]) if not source.empty else "UNKNOWN"
    qualified = {label: values for label, values in groups.items() if len(values) >= min_units}
    rows: list[dict[str, object]] = []
    if len(qualified) < 2:
        global_p = math.nan
        global_status = "INSUFFICIENT_CLUSTER_UNITS"
        statistic = math.nan
    elif np.ptp(np.concatenate(list(qualified.values()))) == 0:
        global_p = 1.0
        global_status = "ZERO_VARIANCE"
        statistic = 0.0
    else:
        result = kruskal(*qualified.values())
        global_p = float(result.pvalue)
        statistic = float(result.statistic)
        global_status = "PASS"
    rows.append(
        {
            "scope": scope,
            "test_level": "GLOBAL",
            "test_name": "Kruskal-Wallis",
            "analysis_unit": "PAIR_CLUSTER_MEDIAN",
            "stratum_1": pd.NA,
            "stratum_2": pd.NA,
            "n_1": sum(len(values) for values in qualified.values()),
            "n_2": pd.NA,
            "median_1": pd.NA,
            "median_2": pd.NA,
            "effect_size_rank_biserial": pd.NA,
            "statistic": statistic,
            "p_value": global_p,
            "p_adjusted_bh": global_p,
            "test_status": global_status,
            "interpretation_flag": "PAIRWISE_KAKS_NOT_PROOF_OF_POSITIVE_SELECTION",
        }
    )
    pair_indexes: list[int] = []
    pair_pvalues: list[float] = []
    for label_1, label_2 in combinations(sorted(groups), 2):
        values_1 = groups[label_1]
        values_2 = groups[label_2]
        effect = math.nan
        statistic = math.nan
        p_value = math.nan
        if len(values_1) and len(values_2):
            result = mannwhitneyu(values_1, values_2, alternative="two-sided", method="auto")
            statistic = float(result.statistic)
            effect = float(2 * statistic / (len(values_1) * len(values_2)) - 1)
        if len(values_1) < min_units or len(values_2) < min_units:
            status = "INSUFFICIENT_CLUSTER_UNITS"
        elif global_status != "PASS" or global_p >= alpha:
            status = "SKIPPED_GLOBAL_NOT_SIGNIFICANT"
        else:
            p_value = float(result.pvalue)
            status = "PASS"
        rows.append(
            {
                "scope": scope,
                "test_level": "PAIRWISE",
                "test_name": "Mann-Whitney U",
                "analysis_unit": "PAIR_CLUSTER_MEDIAN",
                "stratum_1": label_1,
                "stratum_2": label_2,
                "n_1": len(values_1),
                "n_2": len(values_2),
                "median_1": float(np.median(values_1)) if len(values_1) else pd.NA,
                "median_2": float(np.median(values_2)) if len(values_2) else pd.NA,
                "effect_size_rank_biserial": effect,
                "statistic": statistic,
                "p_value": p_value,
                "p_adjusted_bh": math.nan,
                "test_status": status,
                "interpretation_flag": "PAIRWISE_KAKS_NOT_PROOF_OF_POSITIVE_SELECTION",
            }
        )
        if math.isfinite(p_value):
            pair_indexes.append(len(rows) - 1)
            pair_pvalues.append(p_value)
    for index, adjusted in zip(pair_indexes, _bh(pair_pvalues), strict=True):
        rows[index]["p_adjusted_bh"] = adjusted
    return pd.DataFrame(rows)
