from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "prepare_public_tissue_tpm.py"
SPEC = importlib.util.spec_from_file_location("prepare_public_tissue_tpm", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _matrix() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Input1_A1_1": [250_000.0, 750_000.0],
            "Input1_A2_1": [400_000.0, 600_000.0],
            "IP1_A1_1": [100_000.0, 900_000.0],
            "IP1_A2_1": [300_000.0, 700_000.0],
        },
        index=pd.Index(["Os01g1", "Os01g2"], name="stable_id"),
    )


def _samples() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset_id": "GSE229334",
                "sample_id": "GSM1",
                "matrix_column": "Input1_A1_1",
                "tissue_code": "A1",
                "tissue": "root tip",
                "biological_replicate": 1,
                "library_role": "RNA_SEQ_INPUT",
                "include": "TRUE",
            },
            {
                "dataset_id": "GSE229334",
                "sample_id": "GSM2",
                "matrix_column": "Input1_A2_1",
                "tissue_code": "A2",
                "tissue": "whole root",
                "biological_replicate": 1,
                "library_role": "RNA_SEQ_INPUT",
                "include": "TRUE",
            },
        ]
    )


def test_prepare_tissue_tpm_excludes_ip_and_preserves_author_tpm() -> None:
    result = MODULE.prepare_tissue_tpm(_matrix(), _samples())

    assert result["matrix"].columns.tolist() == [
        "stable_id",
        "Input1_A1_1",
        "Input1_A2_1",
    ]
    assert result["matrix"].iloc[0].to_dict() == {
        "stable_id": "Os01g1",
        "Input1_A1_1": 250_000.0,
        "Input1_A2_1": 400_000.0,
    }
    assert result["tissue_medians"].iloc[0].to_dict() == {
        "stable_id": "Os01g1",
        "root tip": 250_000.0,
        "whole root": 400_000.0,
    }
    assert result["audit"].set_index("field")["value"].to_dict() == {
        "status": "PASS",
        "gene_count": "2",
        "included_input_samples": "2",
        "excluded_ip_samples": "2",
        "tissue_count": "2",
        "value_unit": "AUTHOR_TPM_UNCHANGED",
        "inference_policy": "DESCRIPTIVE_ONLY_NO_DE",
    }


def test_prepare_tissue_tpm_rejects_ip_in_the_included_manifest() -> None:
    samples = _samples()
    samples.loc[0, "matrix_column"] = "IP1_A1_1"

    with pytest.raises(ValueError, match="exactly the Input columns"):
        MODULE.prepare_tissue_tpm(_matrix(), samples)
