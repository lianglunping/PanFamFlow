#!/usr/bin/env python3
"""Resume and verify public rice FASTQ downloads from a frozen ENA manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DownloadResult:
    dataset_id: str
    sample_id: str
    run_id: str
    file_role: str
    path: Path
    bytes: int
    md5: str
    status: str


def file_md5(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def target_path(output_root: Path, row: dict[str, str]) -> Path:
    filename = row["url"].rsplit("/", 1)[-1]
    return output_root / row["dataset_id"] / row["sample_id"] / row["run_id"] / filename


def verify_file(path: Path, *, expected_bytes: int, expected_md5: str) -> None:
    observed_bytes = path.stat().st_size
    if observed_bytes != expected_bytes:
        raise ValueError(f"Byte-size mismatch for {path}: {observed_bytes} != {expected_bytes}.")
    observed_md5 = file_md5(path)
    if observed_md5 != expected_md5:
        raise ValueError(f"MD5 mismatch for {path}: {observed_md5} != {expected_md5}.")


def download_one(
    row: dict[str, str], output_root: Path, *, allow_download: bool = True
) -> DownloadResult:
    final_path = target_path(output_root, row)
    expected_bytes = int(row["bytes"])
    expected_md5 = row["md5"]
    if final_path.exists():
        verify_file(final_path, expected_bytes=expected_bytes, expected_md5=expected_md5)
        status = "VERIFIED_EXISTING"
    else:
        if not allow_download:
            raise FileNotFoundError(f"Verify-only input is missing: {final_path}.")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = final_path.with_suffix(final_path.suffix + ".part")
        subprocess.run(
            [
                "curl",
                "--continue-at",
                "-",
                "--fail",
                "--location",
                "--retry",
                "8",
                "--retry-all-errors",
                "--retry-delay",
                "5",
                "--output",
                str(partial_path),
                row["url"],
            ],
            check=True,
        )
        verify_file(partial_path, expected_bytes=expected_bytes, expected_md5=expected_md5)
        os.replace(partial_path, final_path)
        status = "DOWNLOADED_AND_VERIFIED"
    return DownloadResult(
        dataset_id=row["dataset_id"],
        sample_id=row["sample_id"],
        run_id=row["run_id"],
        file_role=row["file_role"],
        path=final_path,
        bytes=expected_bytes,
        md5=expected_md5,
        status=status,
    )


def write_receipt(results: list[DownloadResult], receipt_path: Path) -> None:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    completed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    fields = (
        "dataset_id",
        "sample_id",
        "run_id",
        "file_role",
        "path",
        "bytes",
        "md5",
        "status",
        "verified_at_utc",
    )
    with receipt_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for result in sorted(
            results,
            key=lambda item: (item.dataset_id, item.sample_id, item.run_id, item.file_role),
        ):
            writer.writerow(
                {
                    **{
                        field: getattr(result, field)
                        for field in fields
                        if field not in {"verified_at_utc"}
                    },
                    "path": str(result.path),
                    "verified_at_utc": completed_at,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 5))
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Fail if any file is absent; never fall back to an external download.",
    )
    arguments = parser.parse_args()
    with arguments.manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError("Download manifest is empty.")
    results: list[DownloadResult] = []
    with ThreadPoolExecutor(max_workers=arguments.workers) as executor:
        futures = {
            executor.submit(
                download_one,
                row,
                arguments.output_root.resolve(),
                allow_download=not arguments.verify_only,
            ): row
            for row in rows
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"{len(results)}/{len(rows)}\t{result.status}\t{result.path}",
                flush=True,
            )
    write_receipt(results, arguments.receipt.resolve())


if __name__ == "__main__":
    main()
