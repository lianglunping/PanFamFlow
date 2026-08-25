from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from panfamflow.workflow.scripts.traceability_provenance_utils import build_id_chain_audit


def _write_tsv(path: Path, rows: list[dict[str, str]]) -> Path:
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)
    return path


def test_id_chain_audit_fails_closed_on_orphaned_hog_member(tmp_path: Path) -> None:
    mapping = _write_tsv(
        tmp_path / "mapping.tsv",
        [
            {
                "species_id": "SpA",
                "gene_id": "Gene1",
                "transcript_id": "Tx1",
                "stable_id": "SpA__Gene1",
            }
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
                "gene_id": "Gene2",
                "stable_id": "SpA__Gene2",
            }
        ],
    )

    with pytest.raises(ValueError, match="SELECTED_HOG_MEMBERSHIP"):
        build_id_chain_audit([mapping], family, membership, separator="__")


def test_id_chain_audit_reports_all_three_identifier_stages(tmp_path: Path) -> None:
    mapping = _write_tsv(
        tmp_path / "mapping.tsv",
        [
            {
                "species_id": "SpA",
                "gene_id": "Gene1",
                "transcript_id": "Tx1",
                "stable_id": "SpA__Gene1",
            }
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

    assert audit["stage"].tolist() == [
        "CANONICAL_TRANSCRIPT",
        "TARGET_FAMILY_MEMBER",
        "SELECTED_HOG_MEMBERSHIP",
    ]
    assert audit["status"].tolist() == ["PASS", "PASS", "PASS"]
    assert set(audit["evidence_boundary"]) == {"IDENTIFIER_CONTINUITY_NOT_BIOLOGICAL_GENE_LOSS"}
