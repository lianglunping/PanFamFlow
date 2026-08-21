from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "download_public_expression_files.py"
SPEC = importlib.util.spec_from_file_location("download_public_expression_files", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_target_path_keeps_dataset_sample_and_run_boundaries(tmp_path: Path) -> None:
    row = {
        "dataset_id": "GSE1",
        "sample_id": "GSM2",
        "run_id": "SRR3",
        "url": "https://example.invalid/SRR3_1.fastq.gz",
    }

    assert MODULE.target_path(tmp_path, row) == (
        tmp_path / "GSE1" / "GSM2" / "SRR3" / "SRR3_1.fastq.gz"
    )


def test_verify_file_checks_size_and_ena_md5(tmp_path: Path) -> None:
    path = tmp_path / "read.fastq.gz"
    path.write_bytes(b"synthetic-fastq")
    expected_md5 = hashlib.md5(path.read_bytes()).hexdigest()

    MODULE.verify_file(path, expected_bytes=15, expected_md5=expected_md5)
    with pytest.raises(ValueError, match="Byte-size mismatch"):
        MODULE.verify_file(path, expected_bytes=14, expected_md5=expected_md5)
    with pytest.raises(ValueError, match="MD5 mismatch"):
        MODULE.verify_file(path, expected_bytes=15, expected_md5="0" * 32)
