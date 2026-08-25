from __future__ import annotations

from pathlib import Path

import pandas as pd

from panfamflow.workflow.scripts.traceability_provenance_utils import (
    build_canonical_transcript_provenance,
    build_hog_node_provenance,
    build_id_chain_audit,
)


def _write_tsv(path: Path, rows: list[dict[str, object]]) -> Path:
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)
    return path


def test_traceability_provenance_closes_the_identifier_chain(tmp_path: Path) -> None:
    mapping = _write_tsv(
        tmp_path / "SpA.map.tsv",
        [
            {
                "species_id": "SpA",
                "gene_id": "Gene1",
                "transcript_id": "Tx1",
                "stable_id": "SpA__Gene1",
            },
            {
                "species_id": "SpA",
                "gene_id": "Gene2",
                "transcript_id": "Tx2",
                "stable_id": "SpA__Gene2",
            },
        ],
    )
    family = _write_tsv(
        tmp_path / "family.tsv",
        [{"species_id": "SpA", "gene_id": "Gene1", "stable_id": "SpA__Gene1"}],
    )
    membership = _write_tsv(
        tmp_path / "membership.tsv",
        [
            {
                "HOG_ID": "HOG1",
                "species_id": "SpA",
                "gene_id": "Gene1",
                "stable_id": "SpA__Gene1",
            }
        ],
    )

    audit = build_id_chain_audit([mapping], family, membership, separator="__")
    canonical = build_canonical_transcript_provenance(
        [mapping], backend="portable_gff3", method="longest_cds", separator="__"
    )

    assert audit["status"].tolist() == ["PASS", "PASS", "PASS"]
    assert canonical.loc[0, "status"] == "PASS"
    assert canonical.loc[0, "gene_count"] == 2


def test_hog_node_provenance_hashes_the_selected_source(tmp_path: Path) -> None:
    result_dir = tmp_path / "orthofinder"
    source = result_dir / "Phylogenetic_Hierarchical_Orthogroups" / "N0.tsv"
    source.parent.mkdir(parents=True)
    source.write_text("HOG\tSpA\nHOG1\tSpA__Gene1\n", encoding="utf-8")
    pointer = tmp_path / "result_dir.txt"
    pointer.write_text(str(result_dir), encoding="utf-8")
    classification = _write_tsv(
        tmp_path / "classification.tsv",
        [
            {
                "HOG_ID": "HOG1",
                "hog_node": "N0",
                "hog_node_status": "AUTO_DISCOVERY",
                "orthology_group_type": "HOG",
                "orthology_source_file": "Phylogenetic_Hierarchical_Orthogroups/N0.tsv",
                "analysis_scope": "TARGET_GENE_FAMILY_ONLY",
                "analysis_unit": "ORTHOFINDER_HOG",
                "presence_basis": "ANNOTATION_AND_HOG_MEMBERSHIP",
                "absence_validation_status": "NOT_GENOME_RESCUED",
                "interpretation_flag": "ANNOTATION_OCCUPANCY_NOT_VALIDATED_GENE_LOSS",
            }
        ],
    )

    provenance = build_hog_node_provenance(classification, pointer)

    assert provenance.loc[0, "status"] == "PASS"
    assert provenance.loc[0, "selected_group_count"] == 1
    assert len(provenance.loc[0, "source_sha256"]) == 64
