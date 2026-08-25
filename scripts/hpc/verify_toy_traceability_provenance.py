#!/usr/bin/env python3
"""Validate clean-toy traceability, manifests, and canonical provenance tables."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("toy_project_root", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("preexisting_artifact_count", type=int)
    arguments = parser.parse_args()

    root = arguments.toy_project_root.resolve()
    results = root / "results"
    contract = Path("docs/REQUIREMENT_TRACEABILITY.tsv")
    figure_contract_path = Path("docs/FIGURE_CONTRACT.tsv")
    traceability = pd.read_csv(results / "report/requirement_traceability.tsv", sep="\t", dtype=str)
    result_manifest = pd.read_csv(results / "report/result_manifest.tsv", sep="\t", dtype=str)
    figure_manifest = pd.read_csv(results / "report/figure_manifest.tsv", sep="\t", dtype=str)
    table_manifest = pd.read_csv(results / "report/table_manifest.tsv", sep="\t", dtype=str)
    frozen = pd.read_csv(contract, sep="\t", dtype=str)
    figure_contract = pd.read_csv(figure_contract_path, sep="\t", dtype=str)
    expected_table_pairs = figure_contract["source_table"].nunique()

    if len(traceability) != 61 or len(frozen) != 61:
        raise SystemExit("Traceability contract must contain exactly 61 rows.")
    if set(traceability["requirement_id"]) != set(frozen["requirement_id"]):
        raise SystemExit("Runtime and frozen traceability IDs differ.")
    missing = [artifact for artifact in frozen["artifact"] if not (root / artifact).is_file()]
    if missing:
        raise SystemExit("Missing frozen traceability artifacts: " + ", ".join(missing))
    if len(figure_manifest) != 34 or set(figure_manifest["status"]) != {"GENERATED"}:
        raise SystemExit("Figure manifest is not 34/34 GENERATED.")
    if len(table_manifest) != expected_table_pairs or set(table_manifest["status"]) != {
        "GENERATED"
    }:
        raise SystemExit("Table manifest does not contain all generated pairs.")
    if set(table_manifest["parity_status"]) != {"PASS_ROWS_AND_COLUMNS"}:
        raise SystemExit("TSV/XLSX parity failed.")

    required_paths = {
        "00_qc/id_mapping_audit.tsv",
        "01_normalized/canonical_transcript_provenance.tsv",
        "06_pan_family/hog_node_provenance.tsv",
    }
    if not required_paths.issubset(set(result_manifest["relative_path"])):
        raise SystemExit("Result manifest omits a repaired provenance artifact.")
    for relative in required_paths:
        table = pd.read_csv(results / relative, sep="\t", dtype=str)
        if table.empty or set(table["status"]) != {"PASS"}:
            raise SystemExit(f"Provenance artifact is not PASS: {relative}")

    arguments.receipt.write_text(
        "field\tvalue\n"
        "status\tPASS\n"
        f"compute_host\t{Path('/etc/hostname').read_text().strip()}\n"
        f"traceability_rows\t{len(traceability)}\n"
        f"traceability_sha256\t{hashlib.sha256((results / 'report/requirement_traceability.tsv').read_bytes()).hexdigest()}\n"
        f"result_manifest_rows\t{len(result_manifest)}\n"
        f"result_manifest_sha256\t{hashlib.sha256((results / 'report/result_manifest.tsv').read_bytes()).hexdigest()}\n"
        f"figure_manifest_rows\t{len(figure_manifest)}\n"
        f"table_manifest_rows\t{len(table_manifest)}\n"
        f"expected_table_pairs\t{expected_table_pairs}\n"
        f"preexisting_artifact_count\t{arguments.preexisting_artifact_count}\n"
        "missing_registered_artifacts\t0\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
