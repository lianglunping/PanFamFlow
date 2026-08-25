from __future__ import annotations

import pandas as pd
import pytest

from panfamflow.workflow.scripts.synteny_utils import (
    assign_block_orientations,
    audit_synteny_anchors,
    parse_jcvi_anchor_lines,
    select_renderable_synteny,
)


def _maps() -> tuple[pd.DataFrame, pd.DataFrame]:
    left = pd.DataFrame(
        {
            "stable_id": [f"SpA__G{i}" for i in range(1, 7)],
            "species_id": ["SpA"] * 6,
            "chromosome": ["Chr1"] * 6,
            "gene_start": [100, 200, 300, 400, 500, 600],
            "gene_end": [150, 250, 350, 450, 550, 650],
        }
    )
    right = pd.DataFrame(
        {
            "stable_id": [f"SpB__G{i}" for i in range(1, 7)],
            "species_id": ["SpB"] * 6,
            "chromosome": ["Chr3"] * 6,
            "gene_start": [1000, 1100, 1200, 1300, 1400, 1500],
            "gene_end": [1050, 1150, 1250, 1350, 1450, 1550],
        }
    )
    return left, right


def _anchors() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pair_id": ["A_vs_B"] * 5,
            "block_id": ["block_1"] * 5,
            "anchor_id": [f"anchor_{i}" for i in range(1, 6)],
            "species_1": ["SpA"] * 5,
            "species_2": ["SpB"] * 5,
            "stable_id_1": [f"SpA__G{i}" for i in range(1, 6)],
            "stable_id_2": [f"SpB__G{i}" for i in range(1, 6)],
            "orientation": ["+"] * 5,
            "score": [100, 95, 90, 85, 80],
            "evidence_type": ["SYNTENY_ANCHOR"] * 5,
        }
    )


def test_audited_blocks_require_ordered_whole_genome_anchors() -> None:
    left, right = _maps()
    anchors, blocks, summary = audit_synteny_anchors(
        _anchors(),
        left,
        right,
        pair_id="A_vs_B",
        species_1="SpA",
        species_2="SpB",
        min_anchors_per_block=5,
        backend="precomputed",
    )

    assert anchors["anchor_qc"].eq("PASS_ORDERED_BLOCK").all()
    assert blocks.loc[0, "anchor_count"] == 5
    assert blocks.loc[0, "block_qc"] == "PASS"
    assert summary.loc[0, "pair_status"] == "PASS"
    assert summary.loc[0, "synteny_evidence_basis"] == "ORDERED_MULTI_ANCHOR_BLOCKS"


def test_similarity_hits_cannot_be_imported_as_synteny_anchors() -> None:
    left, right = _maps()
    anchors = _anchors()
    anchors["evidence_type"] = "SIMILARITY_HIT"

    with pytest.raises(ValueError, match="SYNTENY_ANCHOR"):
        audit_synteny_anchors(
            anchors,
            left,
            right,
            pair_id="A_vs_B",
            species_1="SpA",
            species_2="SpB",
            min_anchors_per_block=5,
            backend="precomputed",
        )


def test_short_blocks_fail_pair_level_qc_without_becoming_links() -> None:
    left, right = _maps()
    anchors = _anchors().iloc[:4].copy()

    audited, blocks, summary = audit_synteny_anchors(
        anchors,
        left,
        right,
        pair_id="A_vs_B",
        species_1="SpA",
        species_2="SpB",
        min_anchors_per_block=5,
        backend="precomputed",
    )

    assert audited["anchor_qc"].eq("BLOCK_BELOW_MIN_ANCHORS").all()
    assert blocks.loc[0, "block_qc"] == "BELOW_MIN_ANCHORS"
    assert summary.loc[0, "pair_status"] == "BLOCKED_QC"

    render_anchors, render_blocks, render_pairs = select_renderable_synteny(
        audited, blocks, summary
    )
    assert render_anchors.empty
    assert render_blocks.empty
    assert render_pairs.empty


def test_jcvi_anchor_blocks_are_parsed_and_oriented_from_audited_coordinates() -> None:
    left, right = _maps()
    raw = parse_jcvi_anchor_lines(
        [
            "###\n",
            "SpA__G1\tSpB__G5\t100\n",
            "SpA__G2\tSpB__G4\t95\n",
            "SpA__G3\tSpB__G3\t90\n",
            "###\n",
            "SpA__G4\tSpB__G4\t85\n",
            "SpA__G5\tSpB__G5\t80\n",
        ],
        pair_id="A_vs_B",
        species_1="SpA",
        species_2="SpB",
    )
    oriented = assign_block_orientations(raw, left, right, "SpA", "SpB")

    assert raw["block_id"].tolist() == [
        "A_vs_B.block_000001",
        "A_vs_B.block_000001",
        "A_vs_B.block_000001",
        "A_vs_B.block_000002",
        "A_vs_B.block_000002",
    ]
    assert oriented.groupby("block_id")["orientation"].first().tolist() == ["-", "+"]
    assert oriented["evidence_type"].eq("SYNTENY_ANCHOR").all()


def test_synteny_rules_declare_independent_pair_and_canonical_figure_contracts() -> None:
    from pathlib import Path

    root = Path(__file__).parents[1] / "src" / "panfamflow" / "workflow"
    snakefile = (root / "Snakefile").read_text(encoding="utf-8")
    rule = (root / "rules" / "duplication.smk").read_text(encoding="utf-8")
    pair_script = (root / "scripts" / "run_synteny.py").read_text(encoding="utf-8")
    render_script = (root / "scripts" / "render_synteny_figures.py").read_text(encoding="utf-8")
    assert "SYNTENY_PAIR_IDS" in snakefile
    assert "rule synteny_pair:" in rule
    for expected in (
        "synteny_anchors_intra.tsv",
        "synteny_blocks_intra.tsv",
        "family_duplication_links.tsv",
        "synteny_anchors_inter.tsv",
        "synteny_blocks_inter.tsv",
        "synteny_pair_summary.tsv",
        "synteny_layout_provenance.tsv",
        "Fig17_representative_intragenome_circos.pdf",
        "Fig21_inter_species_pairwise_synteny.pdf",
        "Fig22_inter_species_synteny_overview.pdf",
    ):
        assert expected in rule
    assert "diamond_blastp" in pair_script
    assert "PASS_ORDERED_BLOCK" in render_script
    assert "SIMILARITY_HITS_ARE_NOT_SYNTENY_LINKS" in render_script
