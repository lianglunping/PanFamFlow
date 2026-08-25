#!/usr/bin/env python3
"""Prepare fail-closed public RNA-seq inputs for Kunpeng compute jobs."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
from typing import TextIO

import numpy as np
import pandas as pd


def _require_columns(table: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = sorted(columns.difference(table.columns))
    if missing:
        raise ValueError(f"{label} lacks required columns: {', '.join(missing)}")


def build_sample_sheet(selected: pd.DataFrame, receipt: pd.DataFrame) -> pd.DataFrame:
    """Resolve one or more technical runs to one biological-sample row."""

    _require_columns(selected, {"dataset_id", "sample_id", "run_ids"}, "selected samples")
    _require_columns(
        receipt,
        {"dataset_id", "sample_id", "run_id", "file_role", "path", "status"},
        "FASTQ receipt",
    )
    if selected.duplicated(["dataset_id", "sample_id"]).any():
        raise ValueError("Selected samples contain duplicate dataset/sample rows.")
    if receipt.duplicated(["dataset_id", "sample_id", "run_id", "file_role"]).any():
        raise ValueError("FASTQ receipt contains duplicate dataset/sample/run/role rows.")
    if not receipt["status"].astype(str).str.contains("VERIFIED", regex=False).all():
        raise ValueError("Every FASTQ receipt row must have a verified status.")

    rows: list[dict[str, object]] = []
    for selected_row in selected.to_dict(orient="records"):
        dataset_id = str(selected_row["dataset_id"])
        sample_id = str(selected_row["sample_id"])
        expected_runs = [value for value in str(selected_row["run_ids"]).split(";") if value]
        if not expected_runs or len(expected_runs) != len(set(expected_runs)):
            raise ValueError(f"Sample {sample_id} has empty or duplicate run IDs.")
        sample_receipt = receipt.loc[
            receipt["dataset_id"].astype(str).eq(dataset_id)
            & receipt["sample_id"].astype(str).eq(sample_id)
        ].copy()
        observed_runs = set(sample_receipt["run_id"].astype(str))
        if observed_runs != set(expected_runs):
            raise ValueError(
                f"Sample {sample_id} run mismatch: expected={expected_runs}, "
                f"observed={sorted(observed_runs)}."
            )
        mate_paths: dict[str, list[str]] = {"paired_1": [], "paired_2": []}
        ignored_orphans = 0
        for run_id in expected_runs:
            run_rows = sample_receipt.loc[sample_receipt["run_id"].astype(str).eq(run_id)]
            for role in ("paired_1", "paired_2"):
                role_rows = run_rows.loc[run_rows["file_role"].astype(str).eq(role)]
                if len(role_rows) != 1:
                    raise ValueError(
                        f"Run {run_id} must have exactly one paired_1 and paired_2 file."
                    )
                mate_paths[role].append(str(role_rows.iloc[0]["path"]))
            unexpected = set(run_rows["file_role"].astype(str)).difference(
                {"paired_1", "paired_2", "orphan_unpaired"}
            )
            if unexpected:
                raise ValueError(f"Run {run_id} has unsupported FASTQ roles: {sorted(unexpected)}.")
            ignored_orphans += int(run_rows["file_role"].astype(str).eq("orphan_unpaired").sum())
        rows.append(
            {
                **selected_row,
                "mate1_csv": ",".join(mate_paths["paired_1"]),
                "mate2_csv": ",".join(mate_paths["paired_2"]),
                "technical_run_count": len(expected_runs),
                "ignored_orphan_count": ignored_orphans,
                "technical_run_policy": "MERGED_WITHIN_BIOLOGICAL_SAMPLE",
            }
        )
    return pd.DataFrame(rows)


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def _attributes(raw: str) -> dict[str, str]:
    return {
        key: value
        for field in raw.rstrip(";\n").split(";")
        if "=" in field
        for key, value in [field.split("=", 1)]
    }


def _strip_id_prefix(value: str) -> str:
    return value.split(":", 1)[1] if ":" in value else value


def gff3_to_gene_saf(gff3: Path, output: Path) -> dict[str, int]:
    """Convert transcript-parented GFF3 exons to a de-duplicated gene-level SAF."""

    transcript_to_gene: dict[str, str] = {}
    exon_records: list[tuple[str, str, str, str, tuple[str, ...]]] = []
    with _open_text(gff3) as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"Malformed GFF3 row with {len(fields)} columns.")
            seqid, _source, feature, start, end, _score, strand, _phase, raw_attrs = fields
            attrs = _attributes(raw_attrs)
            if "ID" in attrs and attrs["ID"].startswith("transcript:") and "Parent" in attrs:
                transcript_to_gene[_strip_id_prefix(attrs["ID"])] = _strip_id_prefix(
                    attrs["Parent"].split(",", 1)[0]
                )
            elif feature == "exon":
                if "Parent" not in attrs:
                    raise ValueError("Exon row lacks Parent in GFF3.")
                parents = tuple(_strip_id_prefix(value) for value in attrs["Parent"].split(","))
                exon_records.append((seqid, start, end, strand, parents))

    saf_rows: set[tuple[str, str, int, int, str]] = set()
    for seqid, start, end, strand, parents in exon_records:
        missing = sorted(set(parents).difference(transcript_to_gene))
        if missing:
            raise ValueError(f"Exon parents are absent from transcript rows: {missing[:10]}.")
        genes = {transcript_to_gene[parent] for parent in parents}
        if len(genes) != 1:
            raise ValueError(f"One exon maps to multiple genes: {sorted(genes)}.")
        saf_rows.add((genes.pop(), seqid, int(start), int(end), strand))
    if not saf_rows:
        raise ValueError("No gene-level exon interval was produced from GFF3.")
    saf = pd.DataFrame(
        sorted(saf_rows, key=lambda row: (row[1], row[2], row[3], row[0])),
        columns=["GeneID", "Chr", "Start", "End", "Strand"],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    saf.to_csv(output, sep="\t", index=False)
    return {
        "transcripts": len(transcript_to_gene),
        "genes": int(saf["GeneID"].nunique()),
        "unique_exons": len(saf),
    }


def featurecounts_to_raw_counts(
    featurecounts: Path,
    sample_ids: list[str],
    bam_paths: list[str],
    output: Path,
) -> None:
    """Normalize featureCounts columns into the registered DESeq2 count contract."""

    if len(sample_ids) != len(bam_paths) or len(sample_ids) != len(set(sample_ids)):
        raise ValueError("Sample IDs and BAM paths must be unique and one-to-one.")
    table = pd.read_csv(featurecounts, sep="\t", comment="#")
    _require_columns(table, {"Geneid", *bam_paths}, "featureCounts table")
    if table["Geneid"].astype(str).duplicated().any():
        raise ValueError("featureCounts output contains duplicate Geneid rows.")
    numeric = table[bam_paths].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any(axis=None) or (numeric < 0).any(axis=None):
        raise ValueError("featureCounts output contains missing or negative counts.")
    if not np.equal(numeric.to_numpy(), np.floor(numeric.to_numpy())).all():
        raise ValueError("featureCounts output contains non-integer counts.")
    normalized = numeric.astype("int64")
    normalized.columns = sample_ids
    normalized.insert(
        0,
        "stable_id",
        table["Geneid"].astype(str).map(_strip_id_prefix),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output, sep="\t", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample_parser = subparsers.add_parser("sample-sheet")
    sample_parser.add_argument("selected", type=Path)
    sample_parser.add_argument("receipt", type=Path)
    sample_parser.add_argument("output", type=Path)

    saf_parser = subparsers.add_parser("saf")
    saf_parser.add_argument("gff3", type=Path)
    saf_parser.add_argument("output", type=Path)

    counts_parser = subparsers.add_parser("counts")
    counts_parser.add_argument("featurecounts", type=Path)
    counts_parser.add_argument("sample_ids")
    counts_parser.add_argument("bam_paths")
    counts_parser.add_argument("output", type=Path)

    arguments = parser.parse_args()
    if arguments.command == "sample-sheet":
        selected = pd.read_csv(arguments.selected, sep="\t", dtype=str)
        receipt = pd.read_csv(arguments.receipt, sep="\t", dtype=str)
        sheet = build_sample_sheet(selected, receipt)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        sheet.to_csv(arguments.output, sep="\t", index=False)
    elif arguments.command == "saf":
        audit = gff3_to_gene_saf(arguments.gff3, arguments.output)
        print("\t".join(f"{key}={value}" for key, value in audit.items()))
    else:
        featurecounts_to_raw_counts(
            arguments.featurecounts,
            arguments.sample_ids.split(","),
            arguments.bam_paths.split(","),
            arguments.output,
        )


if __name__ == "__main__":
    main()
