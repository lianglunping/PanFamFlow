import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from collections import Counter
from pathlib import Path

import pandas as pd
from seqid_compatibility import assess_seqid_compatibility
from workflow_utils import fasta_lengths, iter_gff, save_table, sha256_file, write_json

records = list(snakemake.params.records)
calculate_sha256 = bool(snakemake.params.calculate_sha256)
rows: list[dict[str, object]] = []
genome_lengths_by_species: dict[str, dict[str, int]] = {}
gff_max_ends_by_species: dict[str, dict[str, int]] = {}

for record in records:
    path = Path(record["path"])
    row: dict[str, object] = {
        "species_id": record.get("species_id", ""),
        "role": record["role"],
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path) if calculate_sha256 else "NOT_CALCULATED",
        "record_count": pd.NA,
        "total_length": pd.NA,
        "min_length": pd.NA,
        "max_length": pd.NA,
        "mean_length": pd.NA,
        "gff_seqid_count": pd.NA,
        "gff_gene_count": pd.NA,
        "gff_transcript_count": pd.NA,
        "gff_cds_count": pd.NA,
        "seqid_compatibility_status": pd.NA,
        "genome_seqid_count": pd.NA,
        "gff_matched_seqid_count": pd.NA,
        "gff_missing_seqid_count": pd.NA,
        "gff_missing_seqid_examples": pd.NA,
        "gff_coordinate_overrun_count": pd.NA,
        "gff_coordinate_overrun_examples": pd.NA,
        "status": "PASS",
        "notes": "",
    }
    role = str(record["role"])
    species_id = str(record.get("species_id", ""))
    try:
        if role in {"genome", "protein", "cds", "reference_proteins"}:
            fasta_index = fasta_lengths(path)
            if role == "genome":
                genome_lengths_by_species[species_id] = dict(fasta_index)
            lengths = list(fasta_index.values())
            total_length = sum(lengths)
            row.update(
                {
                    "record_count": len(lengths),
                    "total_length": total_length,
                    "min_length": min(lengths) if lengths else 0,
                    "max_length": max(lengths) if lengths else 0,
                    "mean_length": total_length / len(lengths) if lengths else 0.0,
                }
            )
            if not lengths:
                row["status"] = "FAIL"
                row["notes"] = "No FASTA records"
        elif role == "gff3":
            counts: Counter[str] = Counter()
            seqids: set[str] = set()
            max_ends: dict[str, int] = {}
            for feature in iter_gff(path):
                counts[str(feature["feature"]).lower()] += 1
                seqid = str(feature["seqid"])
                seqids.add(seqid)
                max_ends[seqid] = max(max_ends.get(seqid, 0), int(feature["end"]))
            gff_max_ends_by_species[species_id] = max_ends
            transcript_count = sum(
                counts[name] for name in ("mrna", "transcript", "ncrna", "trna", "rrna")
            )
            row.update(
                {
                    "record_count": sum(counts.values()),
                    "gff_seqid_count": len(seqids),
                    "gff_gene_count": counts["gene"],
                    "gff_transcript_count": transcript_count,
                    "gff_cds_count": counts["cds"],
                }
            )
            if counts["gene"] == 0:
                row["status"] = "WARN"
                row["notes"] = "No explicit gene features; downstream mapping may need review"
    except Exception as error:  # input audit records failures instead of hiding them
        row["status"] = "FAIL"
        row["notes"] = f"{type(error).__name__}: {error}"
    rows.append(row)

# Fail before AGAT/gffread instead of silently extracting no/partial genes.
# This compares each GFF3 only to its own assembled genome and never guesses
# contig aliases, rewrites the annotation, or changes scientific input files.
for row in rows:
    if row["role"] != "gff3" or row["status"] == "FAIL":
        continue
    species_id = str(row["species_id"])
    if species_id not in genome_lengths_by_species:
        row["status"] = "FAIL"
        row["notes"] = "No successfully parsed genome FASTA is registered for this GFF3"
        continue
    diagnostic = assess_seqid_compatibility(
        genome_lengths_by_species[species_id],
        gff_max_ends_by_species.get(species_id, {}),
    )
    row.update(diagnostic)
    if diagnostic["seqid_compatibility_status"] != "PASS":
        row["status"] = "FAIL"
        details = [
            str(diagnostic["seqid_compatibility_status"]),
            "Check genome FASTA primary IDs against GFF3 seqids; no automatic remapping",
        ]
        for key in ("gff_missing_seqid_examples", "gff_coordinate_overrun_examples"):
            if diagnostic[key]:
                details.append(f"{key}={diagnostic[key]}")
        if row["notes"]:
            details.insert(0, str(row["notes"]))
        row["notes"] = "; ".join(details)

table = pd.DataFrame(rows)
save_table(table, snakemake.output.tsv, snakemake.output.xlsx)
manifest = {
    "project": snakemake.config.get("project", {}),
    "config_path": snakemake.config.get("panfamflow_config_path"),
    "selected_modules": snakemake.config.get("panfamflow_selected_modules"),
    "audit_records": len(rows),
    "failed_records": int((table["status"] == "FAIL").sum()),
}
write_json(manifest, snakemake.output.manifest)
if manifest["failed_records"]:
    raise RuntimeError(
        f"Input audit detected {manifest['failed_records']} failed record(s); inspect {snakemake.output.tsv}."
    )
