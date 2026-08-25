from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "hpc" / "prepare_public_expression_inputs.py"
SPEC = importlib.util.spec_from_file_location("prepare_public_expression_inputs", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

ALIGNMENT_MODULE_PATH = ROOT / "scripts" / "hpc" / "run_public_expression_alignment.py"
ALIGNMENT_SPEC = importlib.util.spec_from_file_location(
    "run_public_expression_alignment", ALIGNMENT_MODULE_PATH
)
assert ALIGNMENT_SPEC and ALIGNMENT_SPEC.loader
ALIGNMENT_MODULE = importlib.util.module_from_spec(ALIGNMENT_SPEC)
sys.modules[ALIGNMENT_SPEC.name] = ALIGNMENT_MODULE
ALIGNMENT_SPEC.loader.exec_module(ALIGNMENT_MODULE)


def test_build_sample_sheet_merges_technical_runs_without_using_orphans() -> None:
    selected = pd.DataFrame(
        [
            {
                "dataset_id": "GSE1",
                "sample_id": "GSM1",
                "run_ids": "SRR1;SRR2",
                "genotype": "G1",
                "condition": "Mock",
                "replicate": "1",
            }
        ]
    )
    receipt = pd.DataFrame(
        [
            {
                "dataset_id": "GSE1",
                "sample_id": "GSM1",
                "run_id": run,
                "file_role": role,
                "path": f"/raw/{run}/{run}{suffix}.fastq.gz",
                "status": "KUNPENG_CACHE_VERIFIED",
            }
            for run in ("SRR1", "SRR2")
            for role, suffix in (
                ("orphan_unpaired", ""),
                ("paired_1", "_1"),
                ("paired_2", "_2"),
            )
        ]
    )

    sheet = MODULE.build_sample_sheet(selected, receipt)

    assert sheet.loc[0, "mate1_csv"] == "/raw/SRR1/SRR1_1.fastq.gz,/raw/SRR2/SRR2_1.fastq.gz"
    assert sheet.loc[0, "mate2_csv"] == "/raw/SRR1/SRR1_2.fastq.gz,/raw/SRR2/SRR2_2.fastq.gz"
    assert sheet.loc[0, "technical_run_count"] == 2
    assert sheet.loc[0, "ignored_orphan_count"] == 2


def test_build_sample_sheet_rejects_a_missing_registered_mate() -> None:
    selected = pd.DataFrame([{"dataset_id": "GSE1", "sample_id": "GSM1", "run_ids": "SRR1"}])
    receipt = pd.DataFrame(
        [
            {
                "dataset_id": "GSE1",
                "sample_id": "GSM1",
                "run_id": "SRR1",
                "file_role": "paired_1",
                "path": "/raw/SRR1_1.fastq.gz",
                "status": "KUNPENG_CACHE_VERIFIED",
            }
        ]
    )

    with pytest.raises(ValueError, match="exactly one paired_1 and paired_2"):
        MODULE.build_sample_sheet(selected, receipt)


def test_gff3_to_gene_saf_maps_transcripts_and_deduplicates_exons(tmp_path: Path) -> None:
    gff = tmp_path / "annotation.gff3"
    gff.write_text(
        "##gff-version 3\n"
        "1\tsrc\tmRNA\t1\t100\t.\t+\t.\tID=transcript:Tx1;Parent=gene:Gene1\n"
        "1\tsrc\tmRNA\t1\t100\t.\t+\t.\tID=transcript:Tx2;Parent=gene:Gene1\n"
        "1\tsrc\tncRNA\t120\t160\t.\t-\t.\tID=transcript:Tx3;Parent=gene:Gene2\n"
        "1\tsrc\texon\t1\t20\t.\t+\t.\tParent=transcript:Tx1,transcript:Tx2\n"
        "1\tsrc\texon\t1\t20\t.\t+\t.\tParent=transcript:Tx1\n"
        "1\tsrc\texon\t50\t80\t.\t+\t.\tParent=transcript:Tx2\n"
        "1\tsrc\texon\t120\t160\t.\t-\t.\tParent=transcript:Tx3\n",
        encoding="utf-8",
    )
    output = tmp_path / "genes.saf"

    audit = MODULE.gff3_to_gene_saf(gff, output)
    saf = pd.read_csv(output, sep="\t", dtype=str)

    assert saf.to_dict(orient="records") == [
        {"GeneID": "Gene1", "Chr": "1", "Start": "1", "End": "20", "Strand": "+"},
        {"GeneID": "Gene1", "Chr": "1", "Start": "50", "End": "80", "Strand": "+"},
        {"GeneID": "Gene2", "Chr": "1", "Start": "120", "End": "160", "Strand": "-"},
    ]
    assert audit == {"transcripts": 3, "genes": 2, "unique_exons": 3}


def test_featurecounts_table_to_raw_counts_uses_declared_bam_order(tmp_path: Path) -> None:
    featurecounts = tmp_path / "counts.tsv"
    featurecounts.write_text(
        "# Program:featureCounts\n"
        "Geneid\tChr\tStart\tEnd\tStrand\tLength\t/a/GSM1.bam\t/a/GSM2.bam\n"
        "Gene1\t1\t1\t20\t+\t20\t5\t7\n",
        encoding="utf-8",
    )
    output = tmp_path / "raw_counts.tsv"

    MODULE.featurecounts_to_raw_counts(
        featurecounts,
        ["GSM1", "GSM2"],
        ["/a/GSM1.bam", "/a/GSM2.bam"],
        output,
    )

    assert pd.read_csv(output, sep="\t").to_dict(orient="records") == [
        {"stable_id": "Gene1", "GSM1": 5, "GSM2": 7}
    ]


def test_fastp_atomic_partial_path_preserves_gzip_suffix(tmp_path: Path) -> None:
    output = tmp_path / "SRR1_1.trimmed.fastq.gz"

    partial = ALIGNMENT_MODULE._gzip_partial_path(output)

    assert partial.parent == output.parent
    assert partial != output
    assert partial.name.endswith(".partial.gz")


def test_fastp_atomic_promotion_rejects_plain_text_with_gzip_name(tmp_path: Path) -> None:
    partial = tmp_path / "SRR1_1.trimmed.fastq.partial.gz"
    partial.write_text("@read1\nACGT\n+\nIIII\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="gzip magic"):
        ALIGNMENT_MODULE._require_gzip_file(partial)
