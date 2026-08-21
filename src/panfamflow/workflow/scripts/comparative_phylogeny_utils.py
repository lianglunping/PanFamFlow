"""Build an auditable target/external comparative phylogeny panel."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import pandas as pd
from workflow_utils import read_fasta, sha256_file


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def build_comparative_panel(
    members: pd.DataFrame,
    proteins: dict[str, str],
    registry: pd.DataFrame,
    *,
    strategy: str,
    seed: int,
    registry_root: str | Path,
) -> tuple[OrderedDict[str, str], pd.DataFrame, pd.DataFrame]:
    """Select internal representatives and checksum external sequence records."""

    required = {"source_type", "stable_id"}
    missing = sorted(required.difference(registry.columns))
    if missing:
        raise ValueError(f"Comparative panel registry lacks columns: {', '.join(missing)}")
    if registry["stable_id"].astype(str).duplicated().any():
        raise ValueError("Comparative panel registry contains duplicate stable_id values.")
    registry = registry.copy()
    registry["source_type"] = registry["source_type"].astype(str).str.upper()
    invalid_types = sorted(set(registry["source_type"]).difference({"INTERNAL", "EXTERNAL"}))
    if invalid_types:
        raise ValueError(f"Unsupported comparative source_type values: {invalid_types}")
    member_ids = set(members["stable_id"].astype(str))
    internal_registry = registry.loc[registry["source_type"].eq("INTERNAL")].copy()
    if strategy == "explicit":
        if internal_registry.empty:
            raise ValueError("Explicit comparative selection requires INTERNAL registry rows.")
        selected_internal = internal_registry["stable_id"].astype(str).tolist()
    elif strategy == "stratified_seeded":
        strata = [column for column in ("species_id", "group", "subfamily") if column in members]
        if not strata:
            strata = ["species_id"]
        selected_internal = (
            members.sort_values("stable_id")
            .groupby(strata, dropna=False, group_keys=False)
            .sample(n=1, random_state=seed)["stable_id"]
            .astype(str)
            .sort_values()
            .tolist()
        )
    else:
        raise ValueError(f"Unsupported comparative selection strategy: {strategy}")
    unknown_internal = sorted(set(selected_internal).difference(member_ids))
    if unknown_internal:
        raise ValueError(
            "Comparative INTERNAL rows are not accepted family members: "
            + ", ".join(unknown_internal[:10])
        )
    missing_proteins = sorted(set(selected_internal).difference(proteins))
    if missing_proteins:
        raise ValueError(
            "Comparative INTERNAL rows lack accepted protein sequences: "
            + ", ".join(missing_proteins[:10])
        )

    sequences: OrderedDict[str, str] = OrderedDict(
        (stable_id, proteins[stable_id]) for stable_id in selected_internal
    )
    selection_rows: list[dict[str, object]] = []
    member_lookup = members.set_index("stable_id", drop=False).to_dict(orient="index")
    for stable_id in selected_internal:
        record = member_lookup[stable_id]
        selection_rows.append(
            {
                "panel_id": "comparative_panel_1",
                "stable_id": stable_id,
                "species_id": record.get("species_id"),
                "source_type": "INTERNAL",
                "selection_policy": strategy,
                "selection_reason": "EXPLICIT_REGISTRY"
                if strategy == "explicit"
                else "SEEDED_STRATUM_REPRESENTATIVE",
                "seed": seed,
                "outgroup": False,
                "include_in_pan_denominator": False,
            }
        )

    root = Path(registry_root)
    provenance_rows: list[dict[str, object]] = []
    external = registry.loc[registry["source_type"].eq("EXTERNAL")]
    if external.empty or not external.get("outgroup", pd.Series(dtype=object)).map(_truthy).any():
        raise ValueError("Comparative panel requires at least one explicit EXTERNAL outgroup.")
    provenance_required = {
        "sequence_path",
        "sequence_id",
        "accession",
        "version",
        "source_url",
        "expected_sha256",
    }
    missing_external_columns = sorted(provenance_required.difference(external.columns))
    if missing_external_columns:
        raise ValueError(
            "Comparative EXTERNAL registry lacks provenance columns: "
            + ", ".join(missing_external_columns)
        )
    for row in external.to_dict(orient="records"):
        stable_id = str(row["stable_id"])
        sequence_path = Path(str(row["sequence_path"]))
        if not sequence_path.is_absolute():
            sequence_path = root / sequence_path
        if not sequence_path.is_file():
            raise FileNotFoundError(f"External comparative FASTA not found: {sequence_path}")
        observed_sha256 = sha256_file(sequence_path)
        expected_sha256 = str(row["expected_sha256"])
        if observed_sha256 != expected_sha256:
            raise ValueError(f"External comparative FASTA SHA256 mismatch: {sequence_path}")
        external_sequences = read_fasta(sequence_path)
        sequence_id = str(row["sequence_id"])
        if sequence_id not in external_sequences:
            raise ValueError(f"External FASTA lacks sequence_id {sequence_id!r}: {sequence_path}")
        if stable_id in sequences:
            raise ValueError(f"Duplicate comparative stable_id: {stable_id}")
        sequences[stable_id] = external_sequences[sequence_id]
        selection_rows.append(
            {
                "panel_id": "comparative_panel_1",
                "stable_id": stable_id,
                "species_id": row.get("species_id"),
                "source_type": "EXTERNAL",
                "selection_policy": "explicit_external_registry",
                "selection_reason": "VERSIONED_EXTERNAL_SEQUENCE",
                "seed": seed,
                "outgroup": _truthy(row.get("outgroup")),
                "include_in_pan_denominator": False,
            }
        )
        provenance_rows.append(
            {
                "stable_id": stable_id,
                "species_id": row.get("species_id"),
                "sequence_id": sequence_id,
                "accession": row.get("accession"),
                "version": row.get("version"),
                "source_url": row.get("source_url"),
                "sequence_path": str(sequence_path),
                "expected_sha256": expected_sha256,
                "observed_sha256": observed_sha256,
                "provenance_status": "PASS",
            }
        )
    return sequences, pd.DataFrame(selection_rows), pd.DataFrame(provenance_rows)
