from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from panfamflow.config import load_config

PILOT = Path(__file__).parents[1] / "examples" / "rice_3group_pilot"


def test_rice_three_group_pilot_config_loads_without_raw_data() -> None:
    config = load_config(PILOT / "config.yaml")
    assert config.run.modules == ["qc"]
    assert [item.id for item in config.inputs.species] == [
        "GJ_GP523",
        "Wild_GP543",
        "XI_534M",
    ]
    assert [item.group for item in config.inputs.species] == ["GJ", "Wild", "XI"]
    assert config.family.name == "PILOT_TARGET_UNRESOLVED"


def test_rice_three_group_pilot_commits_metadata_not_genomes() -> None:
    repository_root = PILOT.parents[1]
    tracked = subprocess.run(
        ["git", "ls-files", "examples/rice_3group_pilot/data"],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert all(path == "examples/rice_3group_pilot/data/.gitignore" for path in tracked)
    with (PILOT / "source_manifest.tsv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 12
    assert {row["group"] for row in rows} == {"GJ", "Wild", "XI"}
    assert all(len(row["sha256"]) == 64 for row in rows)
    assert all("drive.google.com" not in row["source"] for row in rows)


def test_gp523_namespace_difference_is_explicitly_audited() -> None:
    with (PILOT / "audit" / "id_compatibility.tsv").open(encoding="utf-8", newline="") as handle:
        rows = {row["species_id"]: row for row in csv.DictReader(handle, delimiter="\t")}
    assert rows["GJ_GP523"]["mapping_mode"] == "GWH_HEADER_METADATA"
    assert rows["GJ_GP523"]["status"] == "REVIEW"
    assert rows["Wild_GP543"]["status"] == "PASS"
    assert rows["XI_534M"]["status"] == "PASS"


def test_real_pilot_audit_outputs_are_complete() -> None:
    with (PILOT / "audit" / "panfamflow_input_audit.tsv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 12
    assert {row["status"] for row in rows} == {"PASS"}

    with (PILOT / "audit" / "gzip_staging.tsv").open(encoding="utf-8", newline="") as handle:
        staged = list(csv.DictReader(handle, delimiter="\t"))
    assert len(staged) == 3
    assert {row["mtime_reused"] for row in staged} == {"True"}
    assert all(len(row["uncompressed_sha256"]) == 64 for row in staged)
