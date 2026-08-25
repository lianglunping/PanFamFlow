"""Validation contracts for manually exported external evidence services."""

from __future__ import annotations

import re
from collections.abc import Sequence

import pandas as pd

PROVENANCE_COLUMNS = ("evidence_source", "source_version", "accessed_date", "source_url")
RESULT_COLUMN_ALTERNATIVES: dict[str, tuple[str, ...]] = {
    "domain_validation": ("domain", "domain_accession", "cdd_accession", "status"),
    "localization": ("localization", "prediction", "compartment"),
    "plantcare": ("element", "motif_id", "cis_element"),
}
EXPECTED_SOURCE_TOKENS: dict[str, tuple[str, ...]] = {
    "domain_validation": ("CDD", "NCBI"),
    "localization": ("WOLF", "PSORT"),
    "plantcare": ("PLANTCARE",),
}


def validate_external_evidence_table(
    table: pd.DataFrame,
    *,
    evidence_kind: str,
    strict: bool,
    id_alternatives: Sequence[str] = ("stable_id", "protein_id", "sequence_id"),
) -> pd.DataFrame:
    """Validate result identity and, in strict mode, provenance completeness."""

    if evidence_kind not in RESULT_COLUMN_ALTERNATIVES:
        raise ValueError(f"Unknown external evidence kind: {evidence_kind}")
    if table.empty:
        raise ValueError(f"{evidence_kind} external evidence table is empty.")
    id_columns = [column for column in id_alternatives if column in table.columns]
    if not id_columns and not {"species_id", "gene_id"}.issubset(table.columns):
        raise ValueError(
            f"{evidence_kind} external evidence must contain stable_id or species_id + gene_id."
        )
    result_columns = RESULT_COLUMN_ALTERNATIVES[evidence_kind]
    if not any(column in table.columns for column in result_columns):
        raise ValueError(
            f"{evidence_kind} external evidence must contain one result column from: "
            + ", ".join(result_columns)
        )
    if not strict:
        return table

    missing = [column for column in PROVENANCE_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(
            f"{evidence_kind} strict external evidence is missing provenance columns: "
            + ", ".join(missing)
        )
    for column in PROVENANCE_COLUMNS:
        values = table[column].astype("string").str.strip()
        if values.isna().any() or values.eq("").any():
            raise ValueError(f"{evidence_kind} strict external evidence has blank {column} values.")
    if not table["accessed_date"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError(f"{evidence_kind} accessed_date must use YYYY-MM-DD.")
    if not table["source_url"].astype(str).str.match(r"^https?://", flags=re.I).all():
        raise ValueError(f"{evidence_kind} source_url must be an HTTP(S) URL.")
    source_text = " ".join(table["evidence_source"].astype(str).unique()).upper()
    if not any(token in source_text for token in EXPECTED_SOURCE_TOKENS[evidence_kind]):
        raise ValueError(
            f"{evidence_kind} evidence_source does not identify the expected external service."
        )
    return table
