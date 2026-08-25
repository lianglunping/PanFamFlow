from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def _load_tables(paths: list[str | Path]) -> pd.DataFrame:
    tables = [pd.read_csv(path, sep="\t", dtype=str).fillna("") for path in paths]
    if not tables:
        raise ValueError("At least one table is required.")
    return pd.concat(tables, ignore_index=True)


def _require_columns(table: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns.difference(table.columns))
    if missing:
        raise ValueError(f"{label} is missing columns: {', '.join(missing)}")


def _prefix_mismatch_count(table: pd.DataFrame, separator: str) -> int:
    expected = table["stable_id"].str.split(separator, n=1).str[0]
    return int((expected != table["species_id"]).sum())


def build_id_chain_audit(
    mapping_paths: list[str | Path],
    family_members_path: str | Path,
    hog_membership_path: str | Path,
    *,
    separator: str,
) -> pd.DataFrame:
    normalized = _load_tables(mapping_paths)
    family = pd.read_csv(family_members_path, sep="\t", dtype=str).fillna("")
    membership = pd.read_csv(hog_membership_path, sep="\t", dtype=str).fillna("")
    required = {"stable_id", "species_id", "gene_id"}
    _require_columns(normalized, required | {"transcript_id"}, "canonical mappings")
    _require_columns(family, required, "family_members.tsv")
    _require_columns(membership, required | {"HOG_ID"}, "family_hog_membership.tsv")

    stages = (
        ("CANONICAL_TRANSCRIPT", normalized, None),
        ("TARGET_FAMILY_MEMBER", family, set(normalized["stable_id"])),
        ("SELECTED_HOG_MEMBERSHIP", membership, set(family["stable_id"])),
    )
    rows: list[dict[str, object]] = []
    for stage, table, parent_ids in stages:
        duplicates = int(table["stable_id"].duplicated().sum())
        missing_parent = (
            0 if parent_ids is None else int((~table["stable_id"].isin(parent_ids)).sum())
        )
        prefix_mismatches = _prefix_mismatch_count(table, separator)
        status = "PASS" if duplicates == missing_parent == prefix_mismatches == 0 else "FAIL"
        rows.append(
            {
                "stage": stage,
                "row_count": len(table),
                "unique_stable_id_count": table["stable_id"].nunique(),
                "duplicate_stable_id_count": duplicates,
                "missing_from_parent_count": missing_parent,
                "species_prefix_mismatch_count": prefix_mismatches,
                "status": status,
                "evidence_boundary": "IDENTIFIER_CONTINUITY_NOT_BIOLOGICAL_GENE_LOSS",
            }
        )
    audit = pd.DataFrame(rows)
    if (audit["status"] != "PASS").any():
        failed = ", ".join(audit.loc[audit["status"] != "PASS", "stage"])
        raise ValueError(f"Identifier-chain audit failed: {failed}")
    return audit


def build_canonical_transcript_provenance(
    mapping_paths: list[str | Path],
    *,
    backend: str,
    method: str,
    separator: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path_value in mapping_paths:
        path = Path(path_value)
        table = pd.read_csv(path, sep="\t", dtype=str).fillna("")
        required = {"species_id", "gene_id", "transcript_id", "stable_id"}
        _require_columns(table, required, path.name)
        species_values = sorted(set(table["species_id"]))
        if len(species_values) != 1:
            raise ValueError(f"{path.name} must contain exactly one species_id.")
        duplicate_stable = int(table["stable_id"].duplicated().sum())
        duplicate_gene = int(table["gene_id"].duplicated().sum())
        prefix_mismatches = _prefix_mismatch_count(table, separator)
        status = "PASS" if duplicate_stable == duplicate_gene == prefix_mismatches == 0 else "FAIL"
        rows.append(
            {
                "species_id": species_values[0],
                "backend": backend,
                "selection_method": method,
                "mapping_path": str(path),
                "gene_count": table["gene_id"].nunique(),
                "transcript_count": table["transcript_id"].nunique(),
                "stable_id_count": table["stable_id"].nunique(),
                "duplicate_gene_count": duplicate_gene,
                "duplicate_stable_id_count": duplicate_stable,
                "species_prefix_mismatch_count": prefix_mismatches,
                "status": status,
                "evidence_boundary": "ONE_CANONICAL_TRANSCRIPT_PER_ANNOTATED_GENE",
            }
        )
    provenance = pd.DataFrame(rows).sort_values("species_id").reset_index(drop=True)
    if (provenance["status"] != "PASS").any():
        failed = ", ".join(provenance.loc[provenance["status"] != "PASS", "species_id"])
        raise ValueError(f"Canonical-transcript provenance failed: {failed}")
    return provenance


def build_hog_node_provenance(
    classification_path: str | Path,
    result_dir_pointer: str | Path,
) -> pd.DataFrame:
    classification = pd.read_csv(classification_path, sep="\t", dtype=str).fillna("")
    required = {
        "HOG_ID",
        "hog_node",
        "hog_node_status",
        "orthology_group_type",
        "orthology_source_file",
        "analysis_scope",
        "analysis_unit",
        "presence_basis",
        "absence_validation_status",
        "interpretation_flag",
    }
    _require_columns(classification, required, "pan_family_classification.tsv")
    fields = sorted(required.difference({"HOG_ID"}))
    unique_values = {field: sorted(set(classification[field])) for field in fields}
    nonconstant = [field for field, values in unique_values.items() if len(values) != 1]
    if nonconstant:
        raise ValueError("HOG provenance fields are not constant: " + ", ".join(nonconstant))

    result_dir = Path(Path(result_dir_pointer).read_text(encoding="utf-8").strip())
    source_relative = unique_values["orthology_source_file"][0]
    source_path = result_dir / source_relative
    if not source_path.is_file():
        raise FileNotFoundError(f"Selected HOG source does not exist: {source_path}")
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    row = {field: unique_values[field][0] for field in fields}
    row.update(
        {
            "selected_group_count": classification["HOG_ID"].nunique(),
            "source_path": str(source_path),
            "source_size_bytes": source_path.stat().st_size,
            "source_sha256": source_sha,
            "status": "PASS",
        }
    )
    return pd.DataFrame([row])
