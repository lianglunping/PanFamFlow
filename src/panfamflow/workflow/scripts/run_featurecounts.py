import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from pathlib import Path

import pandas as pd
from workflow_utils import run_command, save_table

sample_records = {str(row["id"]): row for row in snakemake.params.sample_records}
sample_ids = [str(value) for value in snakemake.params.sample_ids]
species_ids = [str(value) for value in snakemake.params.species_ids]
map_paths = dict(zip(species_ids, snakemake.input.maps, strict=True))
gff_paths = dict(zip(species_ids, snakemake.input.gff3, strict=True))
bam_paths = dict(zip(sample_ids, snakemake.input.bams, strict=True))
stable_by_transcript: dict[str, dict[str, str]] = {}
for species_id, path in map_paths.items():
    mapping = pd.read_csv(path, sep="\t", dtype=str)
    if mapping["transcript_id"].duplicated().any():
        raise ValueError(f"{species_id} normalized map has duplicate transcript_id rows.")
    stable_by_transcript[species_id] = dict(
        zip(mapping["transcript_id"], mapping["stable_id"], strict=True)
    )

work_dir = Path(str(snakemake.params.work_dir))
work_dir.mkdir(parents=True, exist_ok=True)
series: list[pd.Series] = []
provenance_rows: list[dict[str, object]] = []
strand_codes = {"unstranded": 0, "forward": 1, "reverse": 2}
for sample_id in sample_ids:
    record = sample_records[sample_id]
    species_id = str(record["species_id"])
    output_path = work_dir / f"{sample_id}.featureCounts.tsv"
    command = [
        "featureCounts",
        "-T",
        str(int(snakemake.threads)),
        "-a",
        str(gff_paths[species_id]),
        "-o",
        str(output_path),
        "-t",
        str(snakemake.params.feature_type),
        "-g",
        str(snakemake.params.feature_attribute),
        "-s",
        str(strand_codes[str(record.get("strandedness", "unstranded"))]),
    ]
    if record.get("r2"):
        command.extend(["-p", "--countReadPairs"])
    command.append(str(bam_paths[sample_id]))
    run_command(
        command,
        stdout_path=work_dir / f"{sample_id}.stdout.log",
        stderr_path=work_dir / f"{sample_id}.stderr.log",
    )
    raw = pd.read_csv(output_path, sep="\t", comment="#")
    count_column = raw.columns[-1]
    raw["stable_id"] = raw["Geneid"].astype(str).map(stable_by_transcript[species_id])
    if raw["stable_id"].isna().any():
        missing = raw.loc[raw["stable_id"].isna(), "Geneid"].astype(str).head(10).tolist()
        raise ValueError(
            f"featureCounts identifiers are absent from the normalized map for {sample_id}: {missing}"
        )
    counts = pd.to_numeric(raw[count_column], errors="raise").astype("int64")
    sample_series = counts.groupby(raw["stable_id"].astype(str)).sum().rename(sample_id)
    series.append(sample_series)
    provenance_rows.append(
        {
            "sample_id": sample_id,
            "species_id": species_id,
            "paired_end": bool(record.get("r2")),
            "strandedness": str(record.get("strandedness", "unstranded")),
            "feature_type": str(snakemake.params.feature_type),
            "feature_attribute": str(snakemake.params.feature_attribute),
            "bam": str(Path(bam_paths[sample_id]).resolve()),
            "annotation": str(Path(gff_paths[species_id]).resolve()),
            "count_status": "PASS_INTEGER_RAW_COUNTS",
        }
    )
matrix = pd.concat(series, axis=1).fillna(0).astype("int64").reset_index()
matrix = matrix.rename(columns={matrix.columns[0]: "stable_id"})
save_table(matrix, snakemake.output.counts, snakemake.output.counts_xlsx)
save_table(
    pd.DataFrame(provenance_rows),
    snakemake.output.provenance,
    snakemake.output.provenance_xlsx,
)
