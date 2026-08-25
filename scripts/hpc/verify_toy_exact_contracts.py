#!/usr/bin/env python3
"""Validate exact OGG, promoter-denominator, and formal-figure toy contracts."""

from __future__ import annotations

import argparse
import hashlib
import math
import re
from pathlib import Path

import pandas as pd

from panfamflow.workflow.scripts.validate_deliverable_contract import (
    _validate_pdf,
    _validate_png,
)

FOUR_MAJOR_CLASSES = {
    "Growth_development",
    "Hormone_response",
    "Light_response",
    "Stress_response",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("toy_project_root", type=Path)
    parser.add_argument("receipt", type=Path)
    arguments = parser.parse_args()

    root = arguments.toy_project_root.resolve()
    results = root / "results"
    report = results / "report"
    pan = results / "06_pan_family"
    promoter = results / "10_promoter"

    figure_manifest_path = report / "figure_manifest.tsv"
    figure_manifest = pd.read_csv(figure_manifest_path, sep="\t", dtype=str)
    if len(figure_manifest) != 34 or set(figure_manifest["status"]) != {"GENERATED"}:
        raise SystemExit("Figure contract is not 34/34 GENERATED.")
    for row in figure_manifest.to_dict(orient="records"):
        pdf = root / row["pdf_path"]
        png = root / row["png_path"]
        source = root / row["source_table"]
        _validate_pdf(pdf)
        _validate_png(png, minimum_dpi=600)
        if not source.is_file() or source.stat().st_size == 0:
            raise SystemExit(f"Missing figure source table: {source}")
        if sha256(pdf) != row["pdf_sha256"] or sha256(png) != row["png_sha256"]:
            raise SystemExit(f"Figure manifest hash mismatch: {row['figure_id']}")

    presence = pd.read_csv(pan / "family_presence_absence.tsv", sep="\t")
    species = list(presence.columns[1:])
    if not species or presence["HOG_ID"].duplicated().any():
        raise SystemExit("OGG presence matrix lacks species or has duplicate HOG_ID values.")
    values = presence[species]
    if not values.isin([0, 1]).all().all():
        raise SystemExit("OGG presence matrix is not binary.")

    distances = pd.read_csv(pan / "ogg_presence_absence_distances.tsv", sep="\t")
    expected_pairs = len(species) * (len(species) - 1) // 2
    if len(distances) != expected_pairs:
        raise SystemExit("OGG distance table does not contain one row per species pair.")
    if set(distances["distance_method"]) != {"JACCARD_BINARY_OGG_PRESENCE_ABSENCE"}:
        raise SystemExit("OGG distance method changed.")
    numeric_distances = pd.to_numeric(distances["jaccard_distance"], errors="coerce")
    if numeric_distances.isna().any() or not numeric_distances.between(0, 1).all():
        raise SystemExit("OGG Jaccard distances are non-finite or outside [0, 1].")

    linkage = pd.read_csv(pan / "ogg_presence_absence_linkage.tsv", sep="\t")
    if len(linkage) != len(species) - 1:
        raise SystemExit("OGG linkage table does not contain n_species - 1 merges.")
    if set(linkage["linkage_method"]) != {"AVERAGE"} or set(linkage["object_type"]) != {
        "NON_PHYLOGENETIC_CLUSTERING"
    }:
        raise SystemExit("OGG clustering method or object type changed.")

    contract = pd.read_csv(pan / "ogg_tree_contract.tsv", sep="\t", dtype=str)
    if set(contract["object_id"]) != {
        "ORTHOFINDER_SPECIES_PHYLOGENY",
        "OGG_PRESENCE_ABSENCE_CLUSTERING",
    }:
        raise SystemExit("OGG tree contract does not contain the two distinct objects.")
    phylogenetic = contract.set_index("object_id")["is_phylogenetic"].str.lower().to_dict()
    if phylogenetic != {
        "ORTHOFINDER_SPECIES_PHYLOGENY": "true",
        "OGG_PRESENCE_ABSENCE_CLUSTERING": "false",
    }:
        raise SystemExit("Species-tree and OGG-clustering roles are not explicit.")

    provenance = pd.read_csv(pan / "ogg_tree_provenance.tsv", sep="\t", dtype=str)
    if len(provenance) != 2 or set(provenance["tip_closure_status"]) != {"PASS"}:
        raise SystemExit("OGG object provenance does not close both tip sets.")
    newick = (pan / "orthofinder_species_tree.nwk").read_text(encoding="utf-8").strip()
    tips = set(re.findall(r"(?<=[(,])([^():,;]+)(?=:)", newick))
    if tips != set(species):
        raise SystemExit(f"Species-tree tips differ from the OGG matrix: {tips} vs {set(species)}")

    elements = pd.read_csv(promoter / "promoter_elements.tsv", sep="\t")
    coordinates = pd.read_csv(promoter / "promoter_coordinates.tsv", sep="\t")
    major = pd.read_csv(promoter / "promoter_major_class_summary.tsv", sep="\t")
    subclass = pd.read_csv(promoter / "promoter_subclass_summary.tsv", sep="\t")
    if set(major["major_class"]) != FOUR_MAJOR_CLASSES or len(major) != 4:
        raise SystemExit("Promoter major-class summary is not the frozen four-class contract.")
    if int(major["motif_hit_count"].sum()) != len(elements):
        raise SystemExit("Promoter major-class motif-hit denominator does not close.")
    if int(subclass["motif_hit_count"].sum()) != len(elements):
        raise SystemExit("Promoter subclass motif-hit denominator does not close.")
    if not math.isclose(float(major["motif_hit_fraction"].sum()), 1.0, abs_tol=1e-10):
        raise SystemExit("Promoter motif-hit fractions do not sum to one.")
    gene_denominator = int(coordinates["stable_id"].astype(str).nunique())
    promoter_bp_denominator = float(pd.to_numeric(coordinates["promoter_length"]).sum())
    for label, table in (("major", major), ("subclass", subclass)):
        if set(pd.to_numeric(table["gene_denominator"])) != {gene_denominator}:
            raise SystemExit(f"Promoter {label} gene denominator changed.")
        if set(pd.to_numeric(table["total_promoter_bp"])) != {promoter_bp_denominator}:
            raise SystemExit(f"Promoter {label} bp denominator changed.")
        if not table["genes_with_hit"].eq(table["n_genes"]).all():
            raise SystemExit(f"Promoter {label} genes_with_hit and n_genes differ.")
        expected_rate = pd.to_numeric(table["motif_hit_count"]) / (promoter_bp_denominator / 1000.0)
        observed_rate = pd.to_numeric(table["hits_per_kb"])
        if not all(
            math.isclose(a, b, abs_tol=1e-12)
            for a, b in zip(expected_rate, observed_rate, strict=True)
        ):
            raise SystemExit(f"Promoter {label} hits_per_kb denominator changed.")

    arguments.receipt.write_text(
        "field\tvalue\n"
        "status\tPASS\n"
        f"compute_host\t{Path('/etc/hostname').read_text().strip()}\n"
        f"figure_pairs_600_dpi\t{len(figure_manifest)}\n"
        f"figure_manifest_sha256\t{sha256(figure_manifest_path)}\n"
        f"ogg_species\t{len(species)}\n"
        f"ogg_groups\t{len(presence)}\n"
        f"ogg_distance_pairs\t{len(distances)}\n"
        "ogg_objects\t2\n"
        "promoter_major_classes\t4\n"
        f"promoter_motif_hits\t{len(elements)}\n"
        f"promoter_gene_denominator\t{gene_denominator}\n"
        f"promoter_bp_denominator\t{promoter_bp_denominator:g}\n"
        f"promoter_major_summary_sha256\t{sha256(promoter / 'promoter_major_class_summary.tsv')}\n"
        f"promoter_subclass_summary_sha256\t{sha256(promoter / 'promoter_subclass_summary.tsv')}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
