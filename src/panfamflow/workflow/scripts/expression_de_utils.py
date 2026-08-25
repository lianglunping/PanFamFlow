"""Fail-closed contracts for raw-count differential expression."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DESIGN_COLUMNS = (
    "dataset_id",
    "sample_id",
    "species_id",
    "condition",
    "biological_replicate",
    "batch",
    "stress_category",
    "evidence_grade",
    "accession",
    "reference_version",
    "file_verification_status",
)
CONTRAST_COLUMNS = (
    "contrast_id",
    "dataset_id",
    "numerator",
    "denominator",
    "stress_category",
    "is_primary",
)
FACTORIAL_CONTRAST_DEFAULTS = {
    "design_formula": "",
    "factor": "condition",
    "contrast_type": "simple",
    "context_factor": "",
    "context_numerator": "",
    "context_denominator": "",
    "minimum_replicates": "",
}
RESULT_COLUMNS = (
    "dataset_id",
    "contrast_id",
    "stable_id",
    "baseMean",
    "log2FoldChange",
    "lfcSE",
    "stat",
    "pvalue",
    "padj",
)


@dataclass(frozen=True)
class DeInputAudit:
    counts: pd.DataFrame
    design: pd.DataFrame
    contrasts: pd.DataFrame
    dataset_audit: pd.DataFrame
    contrast_audit: pd.DataFrame
    sample_qc: pd.DataFrame


def _require_columns(table: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    missing = sorted(set(columns).difference(table.columns))
    if missing:
        raise ValueError(f"{label} lacks required columns: {', '.join(missing)}")


def _design_terms(formula: str) -> tuple[tuple[str, ...], ...]:
    normalized = formula.strip()
    if not normalized.startswith("~"):
        raise ValueError(f"DE design formula must start with ~: {formula}")
    terms: list[tuple[str, ...]] = []
    for raw_term in normalized[1:].split("+"):
        factors = tuple(part.strip() for part in raw_term.strip().split(":"))
        if not factors or any(not factor.isidentifier() for factor in factors):
            raise ValueError(f"Unsupported DE design term: {raw_term.strip()}")
        terms.append(factors)
    if not terms:
        raise ValueError("DE design formula has no terms.")
    return tuple(terms)


def _factor_columns(design: pd.DataFrame, factor: str) -> list[np.ndarray]:
    if factor not in design.columns:
        raise ValueError(f"DE design formula references missing factor {factor}.")
    values = design[factor].astype(str)
    levels = sorted(values.unique())
    return [values.eq(level).astype(float).to_numpy() for level in levels[1:]]


def _full_rank_design(design: pd.DataFrame, formula: str) -> tuple[int, int, str]:
    columns = [np.ones(len(design), dtype=float)]
    for term in _design_terms(formula):
        term_columns: list[np.ndarray] = [np.ones(len(design), dtype=float)]
        for factor in term:
            factor_columns = _factor_columns(design, factor)
            if not factor_columns:
                term_columns = []
                break
            term_columns = [left * right for left in term_columns for right in factor_columns]
        columns.extend(term_columns)
    matrix = np.column_stack(columns)
    rank = int(np.linalg.matrix_rank(matrix))
    expected = int(matrix.shape[1])
    return rank, expected, "FULL_RANK" if rank == expected else "RANK_DEFICIENT"


def audit_de_inputs(
    counts: pd.DataFrame,
    design: pd.DataFrame,
    contrasts: pd.DataFrame,
    *,
    min_replicates: int,
) -> DeInputAudit:
    """Validate raw counts, design estimability and registered contrasts."""

    if min_replicates < 2:
        raise ValueError("Formal DE requires at least two biological replicates per condition.")
    _require_columns(counts, ("stable_id",), "raw count table")
    _require_columns(design, DESIGN_COLUMNS, "DE design table")
    _require_columns(contrasts, CONTRAST_COLUMNS, "DE contrasts table")
    if counts["stable_id"].astype(str).duplicated().any():
        raise ValueError("Raw count table contains duplicate stable_id rows.")
    if design["sample_id"].astype(str).duplicated().any():
        raise ValueError("DE design table contains duplicate sample_id rows.")
    if contrasts["contrast_id"].astype(str).duplicated().any():
        raise ValueError("DE contrasts table contains duplicate contrast_id rows.")
    if design[list(DESIGN_COLUMNS)].isna().any(axis=None):
        raise ValueError("DE design table contains missing required metadata.")
    if contrasts[list(CONTRAST_COLUMNS[:-1])].isna().any(axis=None):
        raise ValueError("DE contrasts table contains missing required metadata.")

    sample_columns = [column for column in counts.columns if column != "stable_id"]
    sample_ids = design["sample_id"].astype(str).tolist()
    if set(sample_columns) != set(sample_ids):
        missing = sorted(set(sample_ids).difference(sample_columns))
        extra = sorted(set(sample_columns).difference(sample_ids))
        raise ValueError(f"Raw count/design sample mismatch; missing={missing}, extra={extra}.")
    numeric = counts[sample_columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any(axis=None) or (numeric < 0).any(axis=None):
        raise ValueError("DESeq2 input must contain non-negative integer raw counts.")
    if not np.equal(numeric.to_numpy(), np.floor(numeric.to_numpy())).all():
        raise ValueError("DESeq2 input must contain integer raw counts, not TPM/FPKM.")
    normalized_counts = pd.concat(
        [counts[["stable_id"]].astype(str), numeric.astype("int64")], axis=1
    )

    design_working = design.copy()
    design_working["sample_id"] = design_working["sample_id"].astype(str)
    design_working["dataset_id"] = design_working["dataset_id"].astype(str)
    contrast_working = contrasts.copy()
    for column, default in FACTORIAL_CONTRAST_DEFAULTS.items():
        if column not in contrast_working.columns:
            contrast_working[column] = default
        contrast_working[column] = contrast_working[column].fillna(default)

    contrast_rows: list[dict[str, object]] = []
    dataset_rows: list[dict[str, object]] = []
    sample_rows: list[dict[str, object]] = []
    for dataset_id, dataset_design in design_working.groupby("dataset_id", sort=True):
        if dataset_design["species_id"].astype(str).nunique() != 1:
            raise ValueError(f"Dataset {dataset_id} mixes species in one DESeq2 fit.")
        if dataset_design["stress_category"].astype(str).nunique() != 1:
            raise ValueError(f"Dataset {dataset_id} mixes stress categories in one DESeq2 fit.")
        dataset_contrasts = contrast_working.loc[
            contrast_working["dataset_id"].astype(str).eq(str(dataset_id))
        ].copy()
        if dataset_contrasts.empty:
            raise ValueError(f"Dataset {dataset_id} has no registered contrast.")
        explicit_formulas = {
            str(value).strip()
            for value in dataset_contrasts["design_formula"]
            if str(value).strip()
        }
        if len(explicit_formulas) > 1:
            raise ValueError(f"Dataset {dataset_id} declares multiple DE design formulas.")
        if explicit_formulas:
            design_formula = explicit_formulas.pop()
        elif dataset_design["batch"].astype(str).nunique() > 1:
            design_formula = "~ batch + condition"
        else:
            design_formula = "~ condition"
        rank, expected_rank, rank_status = _full_rank_design(dataset_design, design_formula)
        if rank_status != "FULL_RANK":
            raise ValueError(
                f"Dataset {dataset_id} design matrix is rank deficient ({rank}/{expected_rank})."
            )

        for row in dataset_contrasts.to_dict(orient="records"):
            factor = str(row["factor"])
            numerator = str(row["numerator"])
            denominator = str(row["denominator"])
            if factor not in dataset_design.columns:
                raise ValueError(
                    f"Contrast {row['contrast_id']} references missing factor {factor}."
                )
            factor_levels = set(dataset_design[factor].astype(str))
            if numerator == denominator or {numerator, denominator}.difference(factor_levels):
                raise ValueError(
                    f"Contrast {row['contrast_id']} is not estimable from dataset {dataset_id}."
                )
            contrast_type = str(row["contrast_type"])
            context_factor = str(row["context_factor"])
            context_numerator = str(row["context_numerator"])
            context_denominator = str(row["context_denominator"])
            required_replicates = max(
                min_replicates,
                int(row["minimum_replicates"]) if str(row["minimum_replicates"]) else 0,
            )
            if contrast_type == "simple":
                numerator_n = int(dataset_design[factor].astype(str).eq(numerator).sum())
                denominator_n = int(dataset_design[factor].astype(str).eq(denominator).sum())
                component_counts = (numerator_n, denominator_n)
            elif contrast_type in {"simple_effect", "interaction"}:
                if not context_factor or context_factor not in dataset_design.columns:
                    raise ValueError(
                        f"Contrast {row['contrast_id']} requires a valid context factor."
                    )
                context_levels = set(dataset_design[context_factor].astype(str))
                requested_contexts = [context_numerator]
                if contrast_type == "interaction":
                    requested_contexts.append(context_denominator)
                for context_level in requested_contexts:
                    if context_level not in context_levels:
                        raise ValueError(
                            f"Contrast {row['contrast_id']} references context level "
                            f"{context_level} absent from dataset {dataset_id}."
                        )
                cell_counts = {
                    (context_level, factor_level): int(
                        (
                            dataset_design[context_factor].astype(str).eq(context_level)
                            & dataset_design[factor].astype(str).eq(factor_level)
                        ).sum()
                    )
                    for context_level in requested_contexts
                    for factor_level in (numerator, denominator)
                }
                numerator_n = cell_counts[(context_numerator, numerator)]
                denominator_n = cell_counts[(context_numerator, denominator)]
                component_counts = tuple(cell_counts.values())
            else:
                raise ValueError(
                    f"Contrast {row['contrast_id']} has unsupported contrast_type {contrast_type}."
                )
            if min(component_counts) < required_replicates:
                raise ValueError(
                    f"Contrast {row['contrast_id']} has fewer than {required_replicates} "
                    "biological replicates in a compared cell."
                )
            contrast_rows.append(
                {
                    **row,
                    "numerator_replicates": numerator_n,
                    "denominator_replicates": denominator_n,
                    "design_rank": rank,
                    "design_columns": expected_rank,
                    "design_rank_status": rank_status,
                    "contrast_status": "PASS",
                    "evidence_grade": str(dataset_design["evidence_grade"].iloc[0]),
                }
            )
        dataset_rows.append(
            {
                "dataset_id": dataset_id,
                "species_id": str(dataset_design["species_id"].iloc[0]),
                "stress_category": str(dataset_design["stress_category"].iloc[0]),
                "accession": str(dataset_design["accession"].iloc[0]),
                "reference_version": str(dataset_design["reference_version"].iloc[0]),
                "evidence_grade": str(dataset_design["evidence_grade"].iloc[0]),
                "file_verification_status": str(dataset_design["file_verification_status"].iloc[0]),
                "sample_count": len(dataset_design),
                "condition_count": int(dataset_design["condition"].nunique()),
                "design_formula": design_formula,
                "design_rank": rank,
                "design_columns": expected_rank,
                "dataset_status": "PASS",
                "fit_scope": "ONE_DATASET_ONE_SPECIES",
            }
        )
        for row in dataset_design.to_dict(orient="records"):
            sample_id = str(row["sample_id"])
            library_size = int(normalized_counts[sample_id].sum())
            sample_rows.append(
                {
                    **row,
                    "library_size": library_size,
                    "zero_gene_fraction": float(normalized_counts[sample_id].eq(0).mean()),
                    "count_input_status": "PASS_INTEGER_RAW_COUNTS",
                    "include_in_de": True,
                    "exclusion_reason": pd.NA,
                }
            )
    unknown_datasets = sorted(
        set(contrast_working["dataset_id"].astype(str)).difference(
            design_working["dataset_id"].astype(str)
        )
    )
    if unknown_datasets:
        raise ValueError(f"Contrasts reference unknown datasets: {unknown_datasets}.")
    return DeInputAudit(
        counts=normalized_counts,
        design=design_working.sort_values(["dataset_id", "sample_id"]),
        contrasts=contrast_working,
        dataset_audit=pd.DataFrame(dataset_rows),
        contrast_audit=pd.DataFrame(contrast_rows),
        sample_qc=pd.DataFrame(sample_rows),
    )


def integrate_de_results(
    results: pd.DataFrame,
    contrast_audit: pd.DataFrame,
    *,
    alpha: float,
    lfc_threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add explicit DEG states and cross-dataset direction-consistency metadata."""

    _require_columns(results, RESULT_COLUMNS, "DESeq2 result table")
    required_contrast = (
        "contrast_id",
        "dataset_id",
        "stress_category",
        "evidence_grade",
        "contrast_status",
    )
    _require_columns(contrast_audit, required_contrast, "contrast audit table")
    working = results[list(RESULT_COLUMNS)].copy()
    if working.duplicated(["contrast_id", "stable_id"]).any():
        raise ValueError("DESeq2 results contain duplicate contrast_id/stable_id rows.")
    for column in ("baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"):
        working[column] = pd.to_numeric(working[column], errors="coerce")
    if working["padj"].dropna().lt(0).any() or working["padj"].dropna().gt(1).any():
        raise ValueError("DESeq2 adjusted P values must be within [0, 1].")
    metadata = contrast_audit[list(required_contrast)].drop_duplicates("contrast_id")
    working = working.merge(
        metadata,
        on=["contrast_id", "dataset_id"],
        how="left",
        validate="many_to_one",
    )
    if working["contrast_status"].isna().any():
        raise ValueError("DESeq2 result references an unregistered contrast.")
    significant = working["padj"].le(alpha) & working["log2FoldChange"].abs().ge(lfc_threshold)
    working["deg_status"] = "NOT_DE"
    working.loc[working["padj"].isna(), "deg_status"] = "UNTESTED_LOW_INFORMATION"
    working.loc[significant & working["log2FoldChange"].gt(0), "deg_status"] = "UP"
    working.loc[significant & working["log2FoldChange"].lt(0), "deg_status"] = "DOWN"
    working["alpha"] = alpha
    working["absolute_log2fc_threshold"] = lfc_threshold
    working["multiple_testing_method"] = "BENJAMINI_HOCHBERG_BY_DESEQ2"

    consistency = (
        working.loc[working["deg_status"].isin(["UP", "DOWN"])]
        .groupby(["stable_id", "stress_category"])["deg_status"]
        .agg(lambda values: "CONSISTENT" if len(set(values)) == 1 else "CONFLICTING")
        .rename("direction_consistency")
        .reset_index()
    )
    integration = working.merge(
        consistency,
        on=["stable_id", "stress_category"],
        how="left",
    )
    integration["effect_direction"] = integration["deg_status"].where(
        integration["deg_status"].isin(["UP", "DOWN"]), "NO_FORMAL_DE"
    )
    dataset_counts = integration.groupby(["stable_id", "stress_category"])["dataset_id"].transform(
        "nunique"
    )
    integration["integration_status"] = np.where(
        dataset_counts > 1,
        "CROSS_DATASET_EFFECT_EVIDENCE",
        "SINGLE_DATASET_EVIDENCE",
    )
    integration["direction_consistency"] = integration["direction_consistency"].fillna(
        "NOT_APPLICABLE"
    )
    integration["interpretation_flag"] = "DATASETS_FIT_SEPARATELY_NO_RAW_COUNT_POOLING"
    membership = working[
        [
            "stable_id",
            "dataset_id",
            "contrast_id",
            "stress_category",
            "deg_status",
            "log2FoldChange",
            "padj",
            "alpha",
            "absolute_log2fc_threshold",
        ]
    ].copy()
    return integration, membership
