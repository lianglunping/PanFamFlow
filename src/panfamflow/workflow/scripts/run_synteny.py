import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import importlib.metadata
import shutil
from pathlib import Path

import pandas as pd
from synteny_utils import (
    assign_block_orientations,
    audit_synteny_anchors,
    parse_jcvi_anchor_lines,
)
from workflow_utils import (
    read_delimited_table,
    read_fasta,
    run_command,
    save_table,
    sha256_file,
    write_fasta,
    write_json,
)


def write_jcvi_bed(table: pd.DataFrame, species_id: str, path: Path) -> None:
    required = {"stable_id", "species_id", "chromosome", "gene_start", "gene_end"}
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError(f"{species_id} gene map lacks JCVI BED fields: {', '.join(missing)}")
    subset = table.loc[table["species_id"].astype(str).eq(species_id)].copy()
    if subset.empty:
        raise ValueError(f"No normalized coordinates were found for {species_id}.")
    subset["gene_start"] = pd.to_numeric(subset["gene_start"], errors="raise").astype(int)
    subset["gene_end"] = pd.to_numeric(subset["gene_end"], errors="raise").astype(int)
    subset["bed_start_0based"] = subset["gene_start"] - 1
    subset["strand"] = subset.get("strand", "+").fillna("+").astype(str)
    bed = subset[["chromosome", "bed_start_0based", "gene_end", "stable_id", "strand"]].copy()
    bed.insert(4, "score", 0)
    bed = bed.sort_values(["chromosome", "bed_start_0based", "stable_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    bed.to_csv(path, sep="\t", index=False, header=False)


pair_id = str(snakemake.params.pair_id)
species_1 = str(snakemake.params.species_1)
species_2 = str(snakemake.params.species_2)
backend = str(snakemake.params.backend)
minimum = int(snakemake.params.min_anchors_per_block)
map_1 = pd.read_csv(snakemake.input.map_1, sep="\t")
map_2 = pd.read_csv(snakemake.input.map_2, sep="\t")
work_dir = Path(str(snakemake.params.work_dir))
work_dir.mkdir(parents=True, exist_ok=True)

command: list[str] | None = None
source_anchor_path: Path
if backend == "precomputed":
    source_anchor_path = Path(str(snakemake.input.precomputed))
    raw_anchors = read_delimited_table(source_anchor_path)
elif backend == "jcvi":
    for executable in ("diamond",):
        if shutil.which(executable) is None:
            raise FileNotFoundError(f"Required synteny executable is unavailable: {executable}")
    inputs = {
        species_1: (map_1, Path(str(snakemake.input.proteins_1))),
        species_2: (map_2, Path(str(snakemake.input.proteins_2))),
    }
    for species_id, (mapping, proteins) in inputs.items():
        write_jcvi_bed(mapping, species_id, work_dir / f"{species_id}.bed")
        write_fasta(read_fasta(proteins), work_dir / f"{species_id}.pep")
    command = [
        sys.executable,
        "-m",
        "jcvi.compara.catalog",
        "ortholog",
        species_1,
        species_2,
        "--dbtype=prot",
        "--align_soft=diamond_blastp",
        f"--cscore={float(snakemake.params.cscore)}",
        f"--tandem_Nmax={int(snakemake.params.tandem_nmax)}",
        f"--min_size={minimum}",
        "--no_strip_names",
        "--no_dotplot",
        f"--cpus={int(snakemake.threads)}",
    ]
    run_command(
        command,
        cwd=work_dir,
        stdout_path=snakemake.log.stdout,
        stderr_path=snakemake.log.stderr,
    )
    candidates = sorted(
        work_dir.glob(f"{species_1}.{species_2}*.anchors"),
        key=lambda path: ("lifted" not in path.name, path.name),
    )
    if not candidates:
        raise RuntimeError(f"JCVI did not produce an anchor file for synteny pair {pair_id}.")
    source_anchor_path = candidates[0]
    with source_anchor_path.open(encoding="utf-8") as handle:
        raw_anchors = parse_jcvi_anchor_lines(
            handle,
            pair_id=pair_id,
            species_1=species_1,
            species_2=species_2,
        )
    raw_anchors = assign_block_orientations(raw_anchors, map_1, map_2, species_1, species_2)
else:
    raise ValueError(
        f"Unsupported executable synteny backend {backend!r}; use jcvi or precomputed."
    )

anchors, blocks, summary = audit_synteny_anchors(
    raw_anchors,
    map_1,
    map_2,
    pair_id=pair_id,
    species_1=species_1,
    species_2=species_2,
    min_anchors_per_block=minimum,
    backend=backend,
)
save_table(anchors, snakemake.output.anchors)
save_table(blocks, snakemake.output.blocks)
save_table(summary, snakemake.output.summary)

package_versions: dict[str, str] = {}
for package in ("jcvi", "pandas", "numpy", "biopython"):
    try:
        package_versions[package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        package_versions[package] = "NOT_INSTALLED"
write_json(
    {
        "pair_id": pair_id,
        "species_1": species_1,
        "species_2": species_2,
        "backend": backend,
        "command": command,
        "parameters": {
            "min_anchors_per_block": minimum,
            "cscore": float(snakemake.params.cscore),
            "tandem_nmax": int(snakemake.params.tandem_nmax),
            "threads": int(snakemake.threads),
        },
        "coordinate_conventions": {
            "normalized_map": "1-based closed",
            "jcvi_bed": "0-based half-open",
            "canonical_synteny_outputs": "1-based closed",
        },
        "evidence_boundary": "ORDERED_MULTI_ANCHOR_BLOCKS_ONLY",
        "similarity_hits_are_synteny_links": False,
        "source_anchor_file": str(source_anchor_path.resolve()),
        "input_sha256": {
            "map_1": sha256_file(snakemake.input.map_1),
            "map_2": sha256_file(snakemake.input.map_2),
            "proteins_1": sha256_file(snakemake.input.proteins_1),
            "proteins_2": sha256_file(snakemake.input.proteins_2),
            "source_anchors": sha256_file(source_anchor_path),
        },
        "package_versions": package_versions,
        "pair_status": str(summary.loc[0, "pair_status"]),
    },
    snakemake.output.provenance,
)
