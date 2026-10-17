"""Regression tests for ERF-inspired, non-destructive intake diagnostics."""

from __future__ import annotations

import pytest

from panfamflow.workflow.scripts.hmm_domain_utils import hmm_model_span
from panfamflow.workflow.scripts.seqid_compatibility import assess_seqid_compatibility


def test_seqid_compatibility_exact_match_with_spare_fasta_contigs() -> None:
    result = assess_seqid_compatibility(
        {"Chr01": 100, "Chr02": 250, "unannotated": 30},
        {"Chr01": 100, "Chr02": 201},
    )
    assert result["seqid_compatibility_status"] == "PASS"
    assert result["gff_matched_seqid_count"] == 2
    assert result["gff_missing_seqid_count"] == 0
    assert result["gff_coordinate_overrun_count"] == 0


def test_seqid_mismatch_not_silently_repaired_by_similar_names() -> None:
    result = assess_seqid_compatibility(
        {"GWHFAJR00000001.1": 500},
        {"Chr01": 490},
    )
    assert result["seqid_compatibility_status"] == "SEQID_MISMATCH"
    assert result["gff_missing_seqid_examples"] == "Chr01"
    assert result["gff_matched_seqid_count"] == 0


def test_partial_match_and_coordinate_overrun_are_both_reported() -> None:
    result = assess_seqid_compatibility(
        {"Chr01": 100, "Chr02": 50},
        {"Chr01": 101, "Chr02": 50, "Chr03": 150},
    )
    assert result["seqid_compatibility_status"] == "SEQID_MISMATCH_AND_COORDINATE_OVERRUN"
    assert result["gff_missing_seqid_examples"] == "Chr03"
    assert result["gff_coordinate_overrun_examples"] == "Chr01:101>100"


def test_empty_gff_fails_closed() -> None:
    assert assess_seqid_compatibility({"Chr01": 100}, {})[
        "seqid_compatibility_status"
    ] == "EMPTY_GFF_FEATURES"


def test_seqid_examples_are_bounded_and_deterministic() -> None:
    result = assess_seqid_compatibility(
        {"Chr01": 30},
        {"x4": 10, "x3": 10, "x2": 10, "x1": 10},
        max_examples=2,
    )
    assert result["gff_missing_seqid_count"] == 4
    assert result["gff_missing_seqid_examples"] == "x1;x2"
    with pytest.raises(ValueError, match="max_examples"):
        assess_seqid_compatibility({}, {}, max_examples=0)


def test_hmm_model_coverage_uses_inclusive_model_coordinates() -> None:
    fields = ["placeholder"] * 22
    fields[5], fields[15], fields[16] = "60", "1", "60"
    result = hmm_model_span(fields)
    assert result == {
        "hmm_model_length": 60,
        "hmm_model_from": 1,
        "hmm_model_to": 60,
        "hmm_model_coverage": 1.0,
    }
    fields[15], fields[16] = "11", "40"
    assert hmm_model_span(fields)["hmm_model_coverage"] == pytest.approx(0.5)


@pytest.mark.parametrize("span", [(0, 50, 40), (50, 0, 10), (50, 3, 52), (50, 20, 19)])
def test_hmm_invalid_model_span_fails_closed(span: tuple[int, int, int]) -> None:
    fields = ["placeholder"] * 22
    fields[5], fields[15], fields[16] = map(str, span)
    with pytest.raises(ValueError, match="Invalid HMM"):
        hmm_model_span(fields)


def test_hmm_model_hit_is_not_a_member_adjudication() -> None:
    fields = ["placeholder"] * 22
    fields[5], fields[15], fields[16] = "80", "4", "34"
    result = hmm_model_span(fields)
    assert result["hmm_model_coverage"] == pytest.approx(31 / 80)
    assert "decision" not in result


def test_input_audit_fails_early_with_mismatched_gff_seqids(tmp_path):
    import hashlib
    import json
    import runpy
    from pathlib import Path
    from types import SimpleNamespace

    import pandas as pd

    scripts = Path(__file__).parents[1] / "src" / "panfamflow" / "workflow" / "scripts"
    genome = tmp_path / "genome.fa"
    gff = tmp_path / "annotation.gff3"
    genome.write_text(">GWHFAJR00000001.1 OriSeqID=Chr01\n" + "A" * 80 + "\n")
    gff.write_text(
        "##gff-version 3\n"
        "Chr01\tx\tgene\t1\t70\t.\t+\t.\tID=gene1\n"
        "Chr01\tx\tmRNA\t1\t70\t.\t+\t.\tID=rna1;Parent=gene1\n"
        "Chr01\tx\tCDS\t1\t60\t.\t+\t0\tID=cds1;Parent=rna1\n"
    )
    genome_sha = hashlib.sha256(genome.read_bytes()).hexdigest()
    gff_sha = hashlib.sha256(gff.read_bytes()).hexdigest()
    input_rows = [
        {"species_id": "SpA", "role": "genome", "path": str(genome)},
        {"species_id": "SpA", "role": "gff3", "path": str(gff)},
    ]
    snakemake = SimpleNamespace(
        scriptdir=str(scripts),
        params=SimpleNamespace(records=input_rows, calculate_sha256=True),
        config={"project": {"name": "test"}},
        output=SimpleNamespace(
            tsv=str(tmp_path / "input_audit.tsv"),
            xlsx=str(tmp_path / "input_audit.xlsx"),
            manifest=str(tmp_path / "input_manifest.json"),
        ),
    )
    with pytest.raises(RuntimeError, match="failed record"):
        runpy.run_path(str(scripts / "input_audit.py"), init_globals={"snakemake": snakemake})
    table = pd.read_csv(snakemake.output.tsv, sep="\t")
    gff_result = table.loc[table["role"].eq("gff3")].iloc[0]
    assert gff_result["status"] == "FAIL"
    assert gff_result["seqid_compatibility_status"] == "SEQID_MISMATCH"
    assert gff_result["gff_missing_seqid_examples"] == "Chr01"
    assert "no automatic remapping" in gff_result["notes"]
    assert json.loads(Path(snakemake.output.manifest).read_text())["failed_records"] == 1
    assert hashlib.sha256(genome.read_bytes()).hexdigest() == genome_sha
    assert hashlib.sha256(gff.read_bytes()).hexdigest() == gff_sha


def test_family_hmm_search_wires_additive_span_diagnostics() -> None:
    from pathlib import Path

    script = (
        Path(__file__).parents[1]
        / "src/panfamflow/workflow/scripts/combine_family_evidence.py"
    ).read_text(encoding="utf-8")
    assert "from hmm_domain_utils import hmm_model_span" in script
    assert "**hmm_model_span(fields)" in script
    assert '"evidence_hmm": stable_id in hmm_ids' in script
