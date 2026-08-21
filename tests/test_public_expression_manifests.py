from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
PUBLIC = ROOT / "examples" / "public_rice_expression"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_frozen_raw_manifest_covers_selected_runs_and_checksums() -> None:
    selected_rows = read_tsv(PUBLIC / "selected_samples.tsv")
    selected_runs = {run_id for row in selected_rows for run_id in row["run_ids"].split(";")}
    files = read_tsv(PUBLIC / "raw_files.tsv")
    assert {row["run_id"] for row in files} == selected_runs
    assert all(row["url"].startswith("https://ftp.sra.ebi.ac.uk/") for row in files)
    assert all(re.fullmatch(r"[0-9a-f]{32}", row["md5"]) for row in files)
    assert all(int(row["bytes"]) > 0 for row in files)
    assert all(row["download_status"] == "CANDIDATE" for row in files)

    roles: dict[str, set[str]] = defaultdict(set)
    for row in files:
        roles[row["run_id"]].add(row["file_role"])
    assert all({"paired_1", "paired_2"}.issubset(run_roles) for run_roles in roles.values())


def test_processed_tpm_manifest_is_descriptive_and_immutable() -> None:
    rows = read_tsv(PUBLIC / "processed_files.tsv")
    assert len(rows) == 1
    row = rows[0]
    assert row["dataset_id"] == "GSE229334"
    assert row["analysis_role"] == "DESCRIPTIVE_TPM_ONLY"
    assert re.fullmatch(r"[0-9a-f]{32}", row["md5"])
    assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
    assert int(row["bytes"]) == 19_232_726
