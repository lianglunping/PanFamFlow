#!/usr/bin/env python3
"""Audit and prepare the frozen GSE229334 Input TPM tissue atlas."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_SAMPLE_COLUMNS = {
    "dataset_id",
    "sample_id",
    "matrix_column",
    "tissue_code",
    "tissue",
    "biological_replicate",
    "library_role",
    "include",
}


def _sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _write_table_pair(table: pd.DataFrame, tsv: Path, xlsx: Path) -> None:
    tsv.parent.mkdir(parents=True, exist_ok=True)
    temporary_tsv = tsv.with_suffix(tsv.suffix + ".tmp")
    temporary_xlsx = xlsx.with_name(f"{xlsx.stem}.tmp{xlsx.suffix}")
    table.to_csv(temporary_tsv, sep="\t", index=False)
    table.to_excel(temporary_xlsx, index=False)
    os.replace(temporary_tsv, tsv)
    os.replace(temporary_xlsx, xlsx)


def prepare_tissue_tpm(matrix: pd.DataFrame, samples: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Preserve author TPM, exclude m6A-IP columns and build descriptive summaries."""

    missing = sorted(REQUIRED_SAMPLE_COLUMNS.difference(samples.columns))
    if missing:
        raise ValueError(f"Tissue sample manifest lacks required columns: {missing}.")
    if matrix.index.duplicated().any():
        raise ValueError("TPM matrix contains duplicate stable IDs.")
    if samples["matrix_column"].duplicated().any() or samples["sample_id"].duplicated().any():
        raise ValueError("Tissue sample manifest contains duplicate sample or matrix columns.")

    included = samples.loc[samples["include"].astype(str).str.upper().eq("TRUE")].copy()
    if included.empty or not included["library_role"].eq("RNA_SEQ_INPUT").all():
        raise ValueError("Included tissue samples must all be RNA_SEQ_INPUT libraries.")
    input_columns = [str(column) for column in matrix.columns if str(column).startswith("Input")]
    ip_columns = [str(column) for column in matrix.columns if str(column).startswith("IP")]
    unknown_columns = sorted(set(map(str, matrix.columns)).difference(input_columns + ip_columns))
    if unknown_columns:
        raise ValueError(
            f"TPM matrix contains unsupported library columns: {unknown_columns[:10]}."
        )
    if set(included["matrix_column"].astype(str)) != set(input_columns):
        raise ValueError("Included sample manifest must contain exactly the Input columns.")

    ordered_columns = included["matrix_column"].astype(str).tolist()
    numeric = matrix.loc[:, ordered_columns].apply(pd.to_numeric, errors="coerce")
    values = numeric.to_numpy(dtype=float)
    if np.isnan(values).any() or np.isinf(values).any() or (values < 0).any():
        raise ValueError("TPM matrix contains missing, infinite or negative values.")
    column_sums = numeric.sum(axis=0)
    if not np.allclose(column_sums.to_numpy(dtype=float), 1_000_000.0, rtol=0, atol=1e-3):
        raise ValueError("Author TPM columns do not close to 1,000,000.")

    stable_ids = matrix.index.astype(str)
    selected = numeric.copy()
    selected.insert(0, "stable_id", stable_ids)

    qc = included[
        [
            "dataset_id",
            "sample_id",
            "matrix_column",
            "tissue_code",
            "tissue",
            "biological_replicate",
            "library_role",
        ]
    ].copy()
    qc["gene_count"] = len(numeric)
    qc["detected_gene_count"] = [int(numeric[column].gt(0).sum()) for column in ordered_columns]
    qc["tpm_sum"] = [float(column_sums[column]) for column in ordered_columns]
    qc["status"] = "PASS_AUTHOR_TPM"

    tissue_medians = pd.DataFrame({"stable_id": stable_ids})
    for tissue in dict.fromkeys(included["tissue"].astype(str)):
        columns = included.loc[included["tissue"].astype(str).eq(tissue), "matrix_column"].tolist()
        tissue_medians[tissue] = numeric[columns].median(axis=1).to_numpy()

    audit = pd.DataFrame(
        [
            ("status", "PASS"),
            ("gene_count", str(len(numeric))),
            ("included_input_samples", str(len(input_columns))),
            ("excluded_ip_samples", str(len(ip_columns))),
            ("tissue_count", str(included["tissue"].nunique())),
            ("value_unit", "AUTHOR_TPM_UNCHANGED"),
            ("inference_policy", "DESCRIPTIVE_ONLY_NO_DE"),
        ],
        columns=["field", "value"],
    )
    return {
        "matrix": selected,
        "sample_qc": qc,
        "tissue_medians": tissue_medians,
        "audit": audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix", type=Path)
    parser.add_argument("sample_manifest", type=Path)
    parser.add_argument("output_root", type=Path)
    arguments = parser.parse_args()

    matrix = pd.read_csv(arguments.matrix, index_col=0)
    samples = pd.read_csv(arguments.sample_manifest, sep="\t", dtype=str, keep_default_na=False)
    result = prepare_tissue_tpm(matrix, samples)
    if matrix.shape != (37_960, 84):
        raise ValueError(f"Frozen GSE229334 matrix shape changed: {matrix.shape}.")
    included = samples["include"].str.upper().eq("TRUE")
    if (
        int(included.sum()) != 42
        or samples.loc[included, "tissue"].nunique() != 14
        or not samples.loc[included].groupby("tissue").size().eq(3).all()
    ):
        raise ValueError("Frozen GSE229334 manifest must contain 14 tissues x 3 Input replicates.")

    outputs = {
        "matrix": "GSE229334_input_tpm",
        "sample_qc": "GSE229334_input_sample_qc",
        "tissue_medians": "GSE229334_tissue_median_tpm",
        "audit": "GSE229334_tpm_audit",
    }
    for key, stem in outputs.items():
        _write_table_pair(
            result[key],
            arguments.output_root / f"{stem}.tsv",
            arguments.output_root / f"{stem}.xlsx",
        )

    provenance = {
        "status": "PASS",
        "dataset_id": "GSE229334",
        "source_matrix": str(arguments.matrix.resolve()),
        "source_matrix_sha256": _sha256(arguments.matrix),
        "sample_manifest": str(arguments.sample_manifest.resolve()),
        "sample_manifest_sha256": _sha256(arguments.sample_manifest),
        "gene_count": 37_960,
        "input_sample_count": 42,
        "excluded_ip_sample_count": 42,
        "tissue_count": 14,
        "biological_replicates_per_tissue": 3,
        "value_unit": "AUTHOR_TPM_UNCHANGED",
        "transformation": "NONE",
        "inference_policy": "DESCRIPTIVE_ONLY_NO_DE",
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    provenance_path = arguments.output_root / "GSE229334_tpm_provenance.json"
    temporary = provenance_path.with_suffix(provenance_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, provenance_path)
    print(
        "PUBLIC_TISSUE_TPM PASS "
        "genes=37960 input_samples=42 excluded_ip=42 tissues=14 policy=DESCRIPTIVE_ONLY_NO_DE"
    )


if __name__ == "__main__":
    main()
