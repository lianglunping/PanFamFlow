#!/usr/bin/env python3
"""Generate deterministic engineering counts for the public 2x2 DE contract."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate_counts(
    design: pd.DataFrame, *, seed: int = 20260823, gene_count: int = 48
) -> pd.DataFrame:
    required = {"dataset_id", "sample_id", "genotype", "condition"}
    missing = sorted(required.difference(design.columns))
    if missing:
        raise ValueError(f"Factorial smoke design lacks columns: {missing}.")
    if len(design) != 24 or design["sample_id"].astype(str).duplicated().any():
        raise ValueError("Factorial smoke requires 24 unique biological samples.")
    if gene_count < 24:
        raise ValueError("Factorial smoke requires at least 24 genes.")

    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for gene_index in range(gene_count):
        row: dict[str, object] = {"stable_id": f"SMOKE_GENE_{gene_index + 1:03d}"}
        baseline = 40.0 + 3.0 * gene_index
        for sample in design.to_dict(orient="records"):
            dataset = str(sample["dataset_id"])
            genotype = str(sample["genotype"])
            condition = str(sample["condition"])
            mean = baseline * (1.15 if dataset == "GSE81906" else 1.0)
            if genotype in {"9L136", "PB1_Pi9"} and gene_index % 3 == 0:
                mean *= 1.25
            treated = condition in {"Salt", "Magnaporthe_oryzae"}
            if treated and gene_index < gene_count // 3:
                mean *= 2.0
            elif treated and gene_index < 2 * gene_count // 3:
                mean *= 0.55
            if treated and genotype in {"9L136", "PB1_Pi9"} and gene_index % 4 == 0:
                mean *= 1.8
            dispersion_size = 20.0
            probability = dispersion_size / (dispersion_size + mean)
            row[str(sample["sample_id"])] = int(rng.negative_binomial(dispersion_size, probability))
        rows.append(row)
    return pd.DataFrame(rows, columns=["stable_id", *design["sample_id"].astype(str)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("design", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--gene-count", type=int, default=48)
    arguments = parser.parse_args()
    design = pd.read_csv(arguments.design, sep="\t", dtype=str)
    counts = generate_counts(design, seed=arguments.seed, gene_count=arguments.gene_count)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    counts.to_csv(arguments.output, sep="\t", index=False)


if __name__ == "__main__":
    main()
