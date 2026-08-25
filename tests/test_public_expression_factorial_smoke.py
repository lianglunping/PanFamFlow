from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "hpc" / "generate_public_factorial_smoke_counts.py"
SPEC = importlib.util.spec_from_file_location("generate_public_factorial_smoke_counts", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_factorial_smoke_counts_are_integer_deterministic_and_complete() -> None:
    design = pd.read_csv(
        ROOT / "examples" / "public_rice_expression" / "de_design.tsv",
        sep="\t",
        dtype=str,
    )

    first = MODULE.generate_counts(design, seed=20260823, gene_count=48)
    second = MODULE.generate_counts(design, seed=20260823, gene_count=48)

    assert first.equals(second)
    assert first.shape == (48, 25)
    assert first.columns.tolist() == ["stable_id", *design["sample_id"].tolist()]
    numeric = first.drop(columns="stable_id").to_numpy()
    assert np.issubdtype(numeric.dtype, np.integer)
    assert (numeric >= 0).all()
    assert first["stable_id"].is_unique
