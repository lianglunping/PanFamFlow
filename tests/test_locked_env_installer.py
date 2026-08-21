from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "hpc" / "install_locked_rule_envs.py"
SPEC = importlib.util.spec_from_file_location("install_locked_rule_envs", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_parse_environment_listing_ignores_preamble() -> None:
    text = """Building DAG of jobs...
environment\tcontainer\tlocation
/repo/envs/qc.yaml\t\t.snakemake/conda/abc_
/repo/envs/family.yaml\t\t.snakemake/conda/def_
"""

    environments = MODULE.parse_environment_listing(text)

    assert [environment.name for environment in environments] == ["qc", "family"]
    assert environments[0].location == Path(".snakemake/conda/abc_")


def test_verify_lock_fails_closed_on_checksum_mismatch(tmp_path: Path) -> None:
    lock = tmp_path / "qc.explicit.txt"
    lock.write_text("@EXPLICIT\nhttps://example.invalid/pkg.conda\n", encoding="utf-8")
    checksums = tmp_path / "SHA256SUMS"
    checksums.write_text(f"{'0' * 64}  env-locks/linux-64/{lock.name}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Lock checksum mismatch"):
        MODULE.verify_lock(lock, checksums)


def test_existing_locked_environment_receives_snakemake_done_marker(
    tmp_path: Path,
) -> None:
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    lock = lock_dir / "qc.explicit.txt"
    lock.write_text("@EXPLICIT\n", encoding="utf-8")
    checksum = hashlib.sha256(lock.read_bytes()).hexdigest()
    (lock_dir / "SHA256SUMS").write_text(
        f"{checksum}  env-locks/linux-64/{lock.name}\n", encoding="utf-8"
    )
    location = Path(".snakemake/conda/qc_hash_")
    history = tmp_path / location / "conda-meta" / "history"
    history.parent.mkdir(parents=True)
    history.write_text("created by test\n", encoding="utf-8")

    status = MODULE.install_environment(
        MODULE.LockedEnvironment(Path("/repo/envs/qc.yaml"), location),
        project_root=tmp_path,
        lock_dir=lock_dir,
        checksum_file=lock_dir / "SHA256SUMS",
        micromamba=tmp_path / "unused-micromamba",
        mamba_root_prefix=tmp_path / "mamba-root",
    )

    assert status.startswith("SKIP\tqc\t")
    assert (tmp_path / location).with_suffix(".env_setup_done").is_file()
