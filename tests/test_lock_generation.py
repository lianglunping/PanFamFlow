from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "micromamba_json_to_lock.py"
SPEC = importlib.util.spec_from_file_location("micromamba_json_to_lock", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_micromamba_json_conversion_writes_explicit_lock_and_receipt(tmp_path: Path) -> None:
    payload = {
        "actions": {
            "LINK": [
                {
                    "name": "python",
                    "version": "3.12.13",
                    "build_string": "h123_0",
                    "fn": "python-3.12.13-h123_0.conda",
                    "channel": "https://conda.anaconda.org/conda-forge/linux-64",
                    "sha256": "a" * 64,
                }
            ]
        }
    }
    lock = tmp_path / "environment.explicit.txt"
    receipt = tmp_path / "environment.packages.tsv"
    MODULE.write_lock(payload, lock, receipt)

    assert lock.read_text(encoding="utf-8").splitlines() == [
        "@EXPLICIT",
        "https://conda.anaconda.org/conda-forge/linux-64/python-3.12.13-h123_0.conda#" + "a" * 64,
    ]
    assert receipt.read_text(encoding="utf-8").splitlines()[1].startswith("python\t3.12.13\th123_0")


def test_linux_lock_job_solves_engine_and_rule_environments() -> None:
    job = (ROOT / "scripts" / "hpc" / "build_linux_locks.jh").read_text(encoding="utf-8")

    assert '"environment.yaml"' in job
    assert '"engine"' in job
    assert "src/panfamflow/workflow/envs/*.yaml" in job
