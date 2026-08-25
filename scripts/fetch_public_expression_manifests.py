#!/usr/bin/env python3
"""Freeze ENA FASTQ URLs, MD5 values and sizes for selected public rice RNA-seq."""

from __future__ import annotations

import csv
import io
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

DATASETS = {
    "GSE101734": "SRP113286",
    "GSE81906": "SRP075722",
}
FIELDS = (
    "run_accession",
    "secondary_sample_accession",
    "sample_accession",
    "experiment_accession",
    "library_layout",
    "fastq_ftp",
    "fastq_md5",
    "fastq_bytes",
)


def selected_run_map(samples_path: Path) -> dict[str, tuple[str, str]]:
    selected: dict[str, tuple[str, str]] = {}
    with samples_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            for run_id in row["run_ids"].split(";"):
                if run_id in selected:
                    raise ValueError(f"Run {run_id} occurs in more than one selected sample.")
                selected[run_id] = (row["dataset_id"], row["sample_id"])
    return selected


def ena_url(study_accession: str) -> str:
    query = urllib.parse.urlencode(
        {
            "accession": study_accession,
            "result": "read_run",
            "fields": ",".join(FIELDS),
            "format": "tsv",
        }
    )
    return f"https://www.ebi.ac.uk/ena/portal/api/filereport?{query}"


def fetch_ena_rows(study_accession: str) -> tuple[str, list[dict[str, str]]]:
    url = ena_url(study_accession)
    with urllib.request.urlopen(url, timeout=120) as response:
        text = response.read().decode("utf-8")
    return url, list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def file_role(url: str) -> str:
    filename = url.rsplit("/", 1)[-1]
    if filename.endswith("_1.fastq.gz"):
        return "paired_1"
    if filename.endswith("_2.fastq.gz"):
        return "paired_2"
    return "orphan_unpaired"


def build_manifest_rows(
    selected: dict[str, tuple[str, str]], fetched_at_utc: str
) -> list[dict[str, str]]:
    manifest: list[dict[str, str]] = []
    observed_runs: set[str] = set()
    for dataset_id, study_accession in DATASETS.items():
        source_url, ena_rows = fetch_ena_rows(study_accession)
        for ena_row in ena_rows:
            run_id = ena_row["run_accession"]
            if run_id not in selected:
                continue
            selected_dataset, sample_id = selected[run_id]
            if selected_dataset != dataset_id:
                raise ValueError(
                    f"Run {run_id} was selected for {selected_dataset}, not {dataset_id}."
                )
            observed_runs.add(run_id)
            urls = ena_row["fastq_ftp"].split(";")
            md5_values = ena_row["fastq_md5"].split(";")
            byte_values = ena_row["fastq_bytes"].split(";")
            if not (len(urls) == len(md5_values) == len(byte_values)):
                raise ValueError(f"ENA file columns have unequal lengths for {run_id}.")
            for url, md5_value, byte_value in zip(urls, md5_values, byte_values, strict=True):
                https_url = url if url.startswith("https://") else f"https://{url}"
                manifest.append(
                    {
                        "dataset_id": dataset_id,
                        "study_accession": study_accession,
                        "sample_id": sample_id,
                        "run_id": run_id,
                        "file_role": file_role(https_url),
                        "url": https_url,
                        "md5": md5_value,
                        "bytes": byte_value,
                        "library_layout": ena_row["library_layout"],
                        "ena_secondary_sample": ena_row["secondary_sample_accession"],
                        "biosample_accession": ena_row["sample_accession"],
                        "experiment_accession": ena_row["experiment_accession"],
                        "source_url": source_url,
                        "fetched_at_utc": fetched_at_utc,
                        "download_status": "CANDIDATE",
                    }
                )
    missing_runs = sorted(set(selected) - observed_runs)
    if missing_runs:
        raise ValueError(f"Selected runs absent from ENA: {', '.join(missing_runs)}")
    roles: dict[str, set[str]] = defaultdict(set)
    for row in manifest:
        roles[row["run_id"]].add(row["file_role"])
    invalid = sorted(
        run_id
        for run_id, run_roles in roles.items()
        if not {"paired_1", "paired_2"}.issubset(run_roles)
    )
    if invalid:
        raise ValueError(f"Paired files missing for: {', '.join(invalid)}")
    return sorted(manifest, key=lambda row: (row["dataset_id"], row["run_id"], row["file_role"]))


def write_manifest(rows: list[dict[str, str]], output_path: Path) -> None:
    if not rows:
        raise ValueError("Refusing to write an empty manifest.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    root = Path(__file__).parents[1]
    public_dir = root / "examples" / "public_rice_expression"
    selected = selected_run_map(public_dir / "selected_samples.tsv")
    fetched_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    rows = build_manifest_rows(selected, fetched_at)
    write_manifest(rows, public_dir / "raw_files.tsv")
    print(f"Wrote {len(rows)} files for {len(selected)} selected runs.")


if __name__ == "__main__":
    main()
