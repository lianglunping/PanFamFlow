#!/usr/bin/env python3
"""Install Snakemake rule environments from audited explicit Linux locks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LockedEnvironment:
    environment_file: Path
    location: Path

    @property
    def name(self) -> str:
        return self.environment_file.stem


def parse_environment_listing(text: str) -> tuple[LockedEnvironment, ...]:
    lines = [line for line in text.splitlines() if line.strip()]
    try:
        header_index = lines.index("environment\tcontainer\tlocation")
    except ValueError as error:
        raise ValueError("Snakemake environment listing has no TSV header.") from error
    rows = csv.DictReader(lines[header_index:], delimiter="\t")
    environments = tuple(
        LockedEnvironment(
            environment_file=Path(row["environment"]),
            location=Path(row["location"]),
        )
        for row in rows
        if row.get("environment", "").endswith((".yaml", ".yml"))
    )
    if not environments:
        raise ValueError("Snakemake environment listing contains no YAML environments.")
    return environments


def expected_sha256(checksum_file: Path, lock_file: Path) -> str:
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        checksum, _, recorded_path = line.partition("  ")
        if Path(recorded_path).name == lock_file.name:
            return checksum
    raise ValueError(f"No SHA256 receipt for {lock_file.name}.")


def verify_lock(lock_file: Path, checksum_file: Path) -> None:
    observed = hashlib.sha256(lock_file.read_bytes()).hexdigest()
    expected = expected_sha256(checksum_file, lock_file)
    if observed != expected:
        raise ValueError(f"Lock checksum mismatch for {lock_file.name}: {observed} != {expected}.")


def install_environment(
    environment: LockedEnvironment,
    *,
    project_root: Path,
    lock_dir: Path,
    checksum_file: Path,
    micromamba: Path,
    mamba_root_prefix: Path,
) -> str:
    lock_file = lock_dir / f"{environment.name}.explicit.txt"
    if not lock_file.is_file():
        raise FileNotFoundError(f"Missing explicit lock: {lock_file}")
    verify_lock(lock_file, checksum_file)
    target = environment.location
    if not target.is_absolute():
        target = project_root / target
    history = target / "conda-meta" / "history"
    setup_done = target.with_suffix(".env_setup_done")
    if history.is_file():
        setup_done.touch(exist_ok=True)
        return f"SKIP\t{environment.name}\t{target}"
    if target.exists():
        raise FileExistsError(f"Refusing to reuse incomplete environment directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    runtime_environment = os.environ.copy()
    runtime_environment["MAMBA_ROOT_PREFIX"] = str(mamba_root_prefix)
    subprocess.run(
        [
            str(micromamba),
            "create",
            "--yes",
            "--offline",
            "--prefix",
            str(target),
            "--file",
            str(lock_file),
        ],
        check=True,
        env=runtime_environment,
    )
    if not history.is_file():
        raise RuntimeError(f"Micromamba did not finalize environment: {target}")
    setup_done.touch(exist_ok=True)
    return f"CREATE\t{environment.name}\t{target}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("listing", type=Path)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("lock_dir", type=Path)
    parser.add_argument("micromamba", type=Path)
    parser.add_argument("mamba_root_prefix", type=Path)
    arguments = parser.parse_args()
    listing = parse_environment_listing(arguments.listing.read_text(encoding="utf-8"))
    checksum_file = arguments.lock_dir / "SHA256SUMS"
    for environment in listing:
        print(
            install_environment(
                environment,
                project_root=arguments.project_root.resolve(),
                lock_dir=arguments.lock_dir.resolve(),
                checksum_file=checksum_file.resolve(),
                micromamba=arguments.micromamba.resolve(),
                mamba_root_prefix=arguments.mamba_root_prefix.resolve(),
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
