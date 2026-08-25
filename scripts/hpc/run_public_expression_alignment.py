#!/usr/bin/env python3
"""Run resumable fastp and HISAT2 alignment for frozen public rice samples."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

import pandas as pd


def _run_logged(command: list[str], stdout: Path, stderr: Path) -> None:
    stdout.parent.mkdir(parents=True, exist_ok=True)
    with (
        stdout.open("w", encoding="utf-8") as stdout_handle,
        stderr.open("w", encoding="utf-8") as stderr_handle,
    ):
        subprocess.run(command, check=True, stdout=stdout_handle, stderr=stderr_handle)


def _write_progress(rows: list[dict[str, object]], path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    pd.DataFrame(rows).to_csv(temporary, sep="\t", index=False)
    os.replace(temporary, path)


def _gzip_partial_path(output: Path) -> Path:
    """Return a same-directory atomic temporary path that fastp will gzip."""

    if output.suffix != ".gz":
        raise ValueError(f"Expected a .gz fastp output path: {output}.")
    return output.with_name(f"{output.stem}.partial{output.suffix}")


def _require_gzip_file(path: Path) -> None:
    """Reject empty, missing or mislabeled fastp outputs before promotion/reuse."""

    if not path.is_file() or path.stat().st_size <= 2:
        raise RuntimeError(f"fastp gzip output is missing or empty: {path}.")
    with path.open("rb") as handle:
        if handle.read(2) != b"\x1f\x8b":
            raise RuntimeError(f"fastp output lacks gzip magic bytes: {path}.")


def _fastp_pair(
    *,
    fastp: Path,
    dataset_id: str,
    sample_id: str,
    input_r1: Path,
    input_r2: Path,
    output_root: Path,
) -> tuple[Path, Path]:
    run_id = input_r1.parent.name
    if input_r2.parent.name != run_id:
        raise ValueError(f"Technical mate paths do not share one run directory: {run_id}.")
    run_root = output_root / "trimmed" / dataset_id / sample_id / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    output_r1 = run_root / f"{run_id}_1.trimmed.fastq.gz"
    output_r2 = run_root / f"{run_id}_2.trimmed.fastq.gz"
    json_path = run_root / f"{run_id}.fastp.json"
    html_path = run_root / f"{run_id}.fastp.html"
    done = run_root / "FASTP_DONE"
    if done.is_file():
        for output in (output_r1, output_r2):
            _require_gzip_file(output)
        return output_r1, output_r2

    partial_r1 = _gzip_partial_path(output_r1)
    partial_r2 = _gzip_partial_path(output_r2)
    for partial in (partial_r1, partial_r2):
        partial.unlink(missing_ok=True)
    _run_logged(
        [
            str(fastp),
            "--thread",
            "4",
            "--in1",
            str(input_r1),
            "--in2",
            str(input_r2),
            "--out1",
            str(partial_r1),
            "--out2",
            str(partial_r2),
            "--json",
            str(json_path),
            "--html",
            str(html_path),
        ],
        run_root / "fastp.stdout.log",
        run_root / "fastp.stderr.log",
    )
    if not all(path.is_file() and path.stat().st_size > 0 for path in (partial_r1, partial_r2)):
        raise RuntimeError(f"fastp did not produce both paired outputs for {run_id}.")
    for partial in (partial_r1, partial_r2):
        _require_gzip_file(partial)
    os.replace(partial_r1, output_r1)
    os.replace(partial_r2, output_r2)
    done.write_text("PASS\n", encoding="utf-8")
    return output_r1, output_r2


def _align_sample(
    *,
    hisat2: Path,
    samtools: Path,
    index_prefix: Path,
    dataset_id: str,
    sample_id: str,
    mate1_paths: list[Path],
    mate2_paths: list[Path],
    output_root: Path,
    threads: int,
) -> tuple[Path, Path, Path]:
    bam_root = output_root / "alignment" / dataset_id
    log_root = output_root / "alignment-logs" / dataset_id / sample_id
    bam_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    bam = bam_root / f"{sample_id}.sorted.bam"
    bai = bam.with_suffix(bam.suffix + ".bai")
    summary = log_root / "hisat2.summary.txt"
    done = log_root / "ALIGNMENT_DONE"
    if done.is_file():
        if not bam.is_file() or not bai.is_file() or not summary.is_file():
            raise RuntimeError(f"ALIGNMENT_DONE exists but outputs are incomplete for {sample_id}.")
        subprocess.run([str(samtools), "quickcheck", "-v", str(bam)], check=True)
        return bam, bai, summary

    bam_partial = bam.with_suffix(bam.suffix + ".partial")
    bai_partial = bai.with_suffix(bai.suffix + ".partial")
    summary_partial = summary.with_suffix(summary.suffix + ".partial")
    for partial in (bam_partial, bai_partial, summary_partial):
        partial.unlink(missing_ok=True)
    align_threads = max(1, threads - 4)
    hisat2_command = [
        str(hisat2),
        "-p",
        str(align_threads),
        "--dta",
        "--no-unal",
        "--summary-file",
        str(summary_partial),
        "-x",
        str(index_prefix),
        "-1",
        ",".join(map(str, mate1_paths)),
        "-2",
        ",".join(map(str, mate2_paths)),
    ]
    with (
        (log_root / "hisat2.stderr.log").open("w", encoding="utf-8") as hisat2_stderr,
        (log_root / "samtools_sort.stderr.log").open("w", encoding="utf-8") as sort_stderr,
    ):
        align_process = subprocess.Popen(
            hisat2_command,
            stdout=subprocess.PIPE,
            stderr=hisat2_stderr,
        )
        assert align_process.stdout is not None
        sort_process = subprocess.Popen(
            [
                str(samtools),
                "sort",
                "-@",
                str(min(4, threads)),
                "-o",
                str(bam_partial),
                "-",
            ],
            stdin=align_process.stdout,
            stderr=sort_stderr,
        )
        align_process.stdout.close()
        sort_return_code = sort_process.wait()
        align_return_code = align_process.wait()
    if align_return_code != 0 or sort_return_code != 0:
        raise RuntimeError(
            f"HISAT2/samtools failed for {sample_id}: "
            f"hisat2={align_return_code}, samtools={sort_return_code}."
        )
    subprocess.run([str(samtools), "quickcheck", "-v", str(bam_partial)], check=True)
    subprocess.run(
        [str(samtools), "index", "-@", str(min(4, threads)), str(bam_partial), str(bai_partial)],
        check=True,
    )
    os.replace(bam_partial, bam)
    os.replace(bai_partial, bai)
    os.replace(summary_partial, summary)
    done.write_text("PASS\n", encoding="utf-8")
    return bam, bai, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_sheet", type=Path)
    parser.add_argument("environment", type=Path)
    parser.add_argument("index_prefix", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--threads", type=int, default=16)
    arguments = parser.parse_args()
    if arguments.threads < 5:
        raise ValueError("Alignment requires at least five allocated threads.")
    tools = {name: arguments.environment / "bin" / name for name in ("fastp", "hisat2", "samtools")}
    for name, path in tools.items():
        if not path.is_file() or not os.access(path, os.X_OK):
            raise FileNotFoundError(f"Locked environment lacks executable {name}: {path}.")
    sheet = pd.read_csv(arguments.sample_sheet, sep="\t", dtype=str, keep_default_na=False)
    required = {"dataset_id", "sample_id", "mate1_csv", "mate2_csv", "technical_run_count"}
    missing = sorted(required.difference(sheet.columns))
    if missing:
        raise ValueError(f"Sample sheet lacks required columns: {missing}.")
    if len(sheet) != 24 or sheet["sample_id"].duplicated().any():
        raise ValueError("Frozen public alignment requires 24 unique biological samples.")
    arguments.output_root.mkdir(parents=True, exist_ok=True)
    progress_path = arguments.output_root / "alignment_progress.tsv"
    receipt_path = arguments.output_root / "alignment_receipt.tsv"
    receipt_rows: list[dict[str, object]] = []
    for row in sheet.sort_values(["dataset_id", "sample_id"]).to_dict(orient="records"):
        dataset_id = str(row["dataset_id"])
        sample_id = str(row["sample_id"])
        source_r1 = [Path(value) for value in str(row["mate1_csv"]).split(",")]
        source_r2 = [Path(value) for value in str(row["mate2_csv"]).split(",")]
        if len(source_r1) != len(source_r2) or len(source_r1) != int(row["technical_run_count"]):
            raise ValueError(f"Technical-run count mismatch for {sample_id}.")
        trimmed_pairs = [
            _fastp_pair(
                fastp=tools["fastp"],
                dataset_id=dataset_id,
                sample_id=sample_id,
                input_r1=mate1,
                input_r2=mate2,
                output_root=arguments.output_root,
            )
            for mate1, mate2 in zip(source_r1, source_r2, strict=True)
        ]
        bam, bai, summary = _align_sample(
            hisat2=tools["hisat2"],
            samtools=tools["samtools"],
            index_prefix=arguments.index_prefix,
            dataset_id=dataset_id,
            sample_id=sample_id,
            mate1_paths=[pair[0] for pair in trimmed_pairs],
            mate2_paths=[pair[1] for pair in trimmed_pairs],
            output_root=arguments.output_root,
            threads=arguments.threads,
        )
        receipt_rows.append(
            {
                "dataset_id": dataset_id,
                "sample_id": sample_id,
                "technical_run_count": len(trimmed_pairs),
                "ignored_orphan_count": int(row.get("ignored_orphan_count", 0)),
                "bam": str(bam.resolve()),
                "bam_bytes": bam.stat().st_size,
                "bai": str(bai.resolve()),
                "hisat2_summary": str(summary.resolve()),
                "preprocessing": "FASTP_PER_TECHNICAL_RUN",
                "technical_run_policy": "MERGED_WITHIN_BIOLOGICAL_SAMPLE",
                "alignment_status": "PASS",
            }
        )
        _write_progress(receipt_rows, progress_path)
    _write_progress(receipt_rows, receipt_path)
    print(f"PUBLIC_ALIGNMENT PASS samples={len(receipt_rows)} receipt={receipt_path}")


if __name__ == "__main__":
    main()
