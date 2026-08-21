#!/usr/bin/env python3
"""Execute the complete synthetic workflow with auditable run provenance."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path

from panfamflow.config import load_config, validate_input_paths
from panfamflow.modules import resolve_modules
from panfamflow.runner import (
    build_snakemake_command,
    execute,
    finalize_run_provenance,
    write_run_provenance,
)

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("precontainer", "complete"), default="complete")
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
        cores=8,
    )
    provenance = write_run_provenance(
        config,
        config_path,
        modules,
        command,
        mode=f"hpc_{platform.node()}_{arguments.phase}",
    )
    try:
        with stack:
            return_code = execute(command)
    except OSError as error:
        finalize_run_provenance(
            provenance,
            127,
            error=f"{type(error).__name__}: {error}",
        )
        raise
    finalize_run_provenance(provenance, return_code)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
