#!/usr/bin/env python3
"""Validate and parse the complete synthetic workflow DAG on the HPC engine."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from panfamflow.config import load_config, validate_input_paths
from panfamflow.modules import resolve_modules
from panfamflow.runner import build_snakemake_command

PRECONTAINER_MODULES = (
    "qc",
    "normalize",
    "family",
    "phylogeny",
    "gene_structure",
    "orthology",
    "pan_family",
    "chromosome",
    "duplication",
    "kaks",
    "promoter",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("precontainer", "complete"), default="complete")
    parser.add_argument("--list-conda-envs", action="store_true")
    arguments = parser.parse_args()
    config_path = Path("examples/toy_complete/config.yaml").resolve()
    config = load_config(config_path)
    requested = PRECONTAINER_MODULES if arguments.phase == "precontainer" else config.run.modules
    modules = resolve_modules(requested, config)
    errors = [
        issue
        for issue in validate_input_paths(config, config_path, modules)
        if issue.severity == "ERROR"
    ]
    if errors:
        raise RuntimeError("; ".join(f"{issue.field}: {issue.message}" for issue in errors))
    command, stack = build_snakemake_command(
        config,
        config_path,
        modules,
        cores=2,
        dry_run=not arguments.list_conda_envs,
    )
    if arguments.list_conda_envs:
        command.insert(command.index("--"), "--list-conda-envs")
    with stack:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
