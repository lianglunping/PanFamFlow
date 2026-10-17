"""Read-only FASTA/GFF3 seqid and coordinate compatibility checks.

This is an intake guard, not an automatic name-remapping or annotation
repair tool. Any remapping must use an explicitly reviewed derived GFF3.
"""

from __future__ import annotations

from collections.abc import Mapping


def assess_seqid_compatibility(
    genome_lengths: Mapping[str, int],
    gff_max_ends: Mapping[str, int],
    *,
    max_examples: int = 5,
) -> dict[str, object]:
    """Compare GFF feature seqids and maximum ends to FASTA primary IDs.

    ``gff_max_ends`` must include every parsed GFF feature rather than only
    explicit ``gene`` rows. Coordinates are GFF3 1-based closed ends; FASTA
    lengths are base counts. Values above the FASTA length are incompatible.
    No contig alias is guessed from numeric suffixes or similar spelling.
    """
    if max_examples < 1:
        raise ValueError("max_examples must be positive")

    genome_ids = set(genome_lengths)
    gff_ids = set(gff_max_ends)
    matched = sorted(gff_ids & genome_ids)
    missing = sorted(gff_ids - genome_ids)
    overrun = sorted(seqid for seqid in matched if gff_max_ends[seqid] > genome_lengths[seqid])

    if not gff_ids:
        status = "EMPTY_GFF_FEATURES"
    elif missing and overrun:
        status = "SEQID_MISMATCH_AND_COORDINATE_OVERRUN"
    elif missing:
        status = "SEQID_MISMATCH"
    elif overrun:
        status = "COORDINATE_OVERRUN"
    else:
        status = "PASS"

    return {
        "seqid_compatibility_status": status,
        "genome_seqid_count": len(genome_ids),
        "gff_matched_seqid_count": len(matched),
        "gff_missing_seqid_count": len(missing),
        "gff_missing_seqid_examples": ";".join(missing[:max_examples]),
        "gff_coordinate_overrun_count": len(overrun),
        "gff_coordinate_overrun_examples": ";".join(
            f"{seqid}:{gff_max_ends[seqid]}>{genome_lengths[seqid]}"
            for seqid in overrun[:max_examples]
        ),
    }
