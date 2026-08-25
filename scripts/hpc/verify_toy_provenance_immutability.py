#!/usr/bin/env python3
"""Validate immutable clean-toy inputs and provenance bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("toy_project_root", type=Path)
    parser.add_argument("receipt", type=Path)
    arguments = parser.parse_args()

    root = arguments.toy_project_root.resolve()
    results = root / "results"
    input_audit_path = results / "00_qc/input_audit.tsv"
    input_manifest_path = results / "00_qc/input_manifest.json"
    provenance_path = results / "report/provenance.json"
    figure_contract_path = Path("docs/FIGURE_CONTRACT.tsv")
    traceability_contract_path = Path("docs/REQUIREMENT_TRACEABILITY.tsv")
    config_path = root / "config.yaml"

    input_audit = pd.read_csv(input_audit_path, sep="\t", dtype=str).fillna("")
    if len(input_audit) != 11 or set(input_audit["status"]) != {"PASS"}:
        raise SystemExit("Input audit must contain exactly 11 PASS rows.")
    if input_audit["path"].duplicated().any():
        raise SystemExit("Input audit contains duplicate paths.")
    for row in input_audit.to_dict(orient="records"):
        path = Path(row["path"])
        if not path.is_file():
            raise SystemExit(f"Frozen input is missing: {path}")
        if path.stat().st_size != int(row["size_bytes"]):
            raise SystemExit(f"Frozen input size changed: {path}")
        if sha256(path) != row["sha256"]:
            raise SystemExit(f"Frozen input SHA256 changed: {path}")

    manifest = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    expected_modules = [
        "qc",
        "normalize",
        "family",
        "phylogeny",
        "gene_structure",
        "orthology",
        "pan_family",
        "chromosome",
        "duplication",
        "kaks",
        "promoter",
        "expression",
        "report",
    ]
    fixed_digest = (
        "docker://ghcr.io/lianglunping/panfamflow-expression-de@"
        "sha256:57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29"
    )
    if manifest["audit_records"] != 11 or manifest["failed_records"] != 0:
        raise SystemExit("Input manifest audit counts are not closed.")
    if provenance["input_manifest_sha256"] != sha256(input_manifest_path):
        raise SystemExit("Provenance does not bind the current input manifest.")
    if provenance["figure_contract_sha256"] != sha256(figure_contract_path):
        raise SystemExit("Provenance does not bind the frozen figure contract.")
    if provenance["traceability_contract_sha256"] != sha256(traceability_contract_path):
        raise SystemExit("Provenance does not bind the frozen traceability contract.")
    if provenance["seed"] != 20260821 or provenance["selected_modules"] != expected_modules:
        raise SystemExit("Seed or selected module order changed.")
    if provenance["scientific_boundary"] != "ENGINEERING_COMPLETION_IS_NOT_BIOLOGICAL_VALIDATION":
        raise SystemExit("Scientific boundary changed.")
    if provenance["configuration"]["differential_expression"]["container_image"] != fixed_digest:
        raise SystemExit("Fixed differential-expression image digest changed.")

    arguments.receipt.write_text(
        "field\tvalue\n"
        "status\tPASS\n"
        f"compute_host\t{Path('/etc/hostname').read_text().strip()}\n"
        f"input_audit_rows\t{len(input_audit)}\n"
        f"input_audit_sha256\t{sha256(input_audit_path)}\n"
        f"input_manifest_sha256\t{sha256(input_manifest_path)}\n"
        f"config_sha256\t{sha256(config_path)}\n"
        f"figure_contract_sha256\t{sha256(figure_contract_path)}\n"
        f"traceability_contract_sha256\t{sha256(traceability_contract_path)}\n"
        f"provenance_sha256\t{sha256(provenance_path)}\n"
        "seed\t20260821\n"
        f"selected_modules\t{len(expected_modules)}\n"
        "scientific_boundary\tENGINEERING_COMPLETION_IS_NOT_BIOLOGICAL_VALIDATION\n"
        "input_hash_mismatches\t0\n"
        "fixed_ghcr_digest\tsha256:57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
