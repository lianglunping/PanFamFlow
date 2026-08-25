"""Build an auditable amino-acid sequence logo from validated domain sequences."""

from __future__ import annotations

import math
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch
from matplotlib.textpath import TextPath
from matplotlib.transforms import Affine2D
from workflow_utils import iter_fasta_records, save_table, save_workbook, write_fasta

AMINO_ACIDS = tuple("ACDEFGHIKLMNPQRSTVWY")
AA_COLORS = {
    **dict.fromkeys("AVILMFWY", "#0072B2"),
    **dict.fromkeys("STNQ", "#009E73"),
    **dict.fromkeys("KRH", "#D55E00"),
    **dict.fromkeys("DE", "#CC79A7"),
    **dict.fromkeys("CGP", "#E69F00"),
}


def _read_alignment(path: str | Path) -> OrderedDict[str, str]:
    records = OrderedDict(iter_fasta_records(path))
    lengths = {len(sequence) for sequence in records.values()}
    if len(lengths) > 1:
        raise ValueError("Aligned domain FASTA contains unequal sequence lengths.")
    invalid = sorted(
        {
            residue
            for sequence in records.values()
            for residue in sequence.upper()
            if residue not in set(AMINO_ACIDS) | {"-", "X", "?", "."}
        }
    )
    if invalid:
        raise ValueError(f"Domain alignment contains unsupported residues: {invalid}")
    return OrderedDict((key, value.upper().replace(".", "-")) for key, value in records.items())


def _align_with_mafft(records: OrderedDict[str, str]) -> OrderedDict[str, str]:
    if len(records) < 2:
        return records
    with tempfile.TemporaryDirectory(prefix="panfamflow-domain-logo-") as temporary:
        input_path = Path(temporary) / "domains.fa"
        output_path = Path(temporary) / "domains.aligned.fa"
        write_fasta(records, input_path)
        completed = subprocess.run(
            ["mafft", "--auto", "--quiet", str(input_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"MAFFT domain alignment failed: {completed.stderr[-2000:]}")
        output_path.write_text(completed.stdout, encoding="utf-8")
        return _read_alignment(output_path)


def _frequency_table(alignment: OrderedDict[str, str]) -> pd.DataFrame:
    columns = [
        "alignment_position",
        "amino_acid",
        "count",
        "frequency",
        "coverage_fraction",
        "information_bits",
        "letter_height_bits",
    ]
    if not alignment:
        return pd.DataFrame(columns=columns)
    sequences = list(alignment.values())
    rows: list[dict[str, float | int | str]] = []
    for index in range(len(sequences[0])):
        residues = [sequence[index] for sequence in sequences]
        counts = {aa: residues.count(aa) for aa in AMINO_ACIDS}
        observed = sum(counts.values())
        coverage = observed / len(sequences)
        entropy = -sum(
            (count / observed) * math.log2(count / observed)
            for count in counts.values()
            if count and observed
        )
        information = max(0.0, math.log2(len(AMINO_ACIDS)) - entropy) * coverage
        for amino_acid, count in counts.items():
            if not count:
                continue
            frequency = count / observed
            rows.append(
                {
                    "alignment_position": index + 1,
                    "amino_acid": amino_acid,
                    "count": count,
                    "frequency": frequency,
                    "coverage_fraction": coverage,
                    "information_bits": information,
                    "letter_height_bits": frequency * information,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def _plot_logo(table: pd.DataFrame, sequence_count: int, pdf: str, png: str, dpi: int) -> None:
    position_count = int(table["alignment_position"].max()) if not table.empty else 1
    figure_width = max(8.0, min(30.0, 0.28 * position_count))
    fig, axis = plt.subplots(figsize=(figure_width, 4.8))
    if table.empty:
        axis.text(
            0.5,
            0.55,
            "No validated core-domain alignment was available",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
        axis.text(
            0.5,
            0.42,
            "Status: NOT_AVAILABLE (this is not a biological absence)",
            ha="center",
            va="center",
            fontsize=9,
            transform=axis.transAxes,
        )
        axis.set_axis_off()
    else:
        font = FontProperties(family="DejaVu Sans", weight="bold")
        for position, group in table.groupby("alignment_position", sort=True):
            bottom = 0.0
            for row in group.sort_values("letter_height_bits").itertuples(index=False):
                height = float(row.letter_height_bits)
                if height <= 0:
                    continue
                glyph = TextPath((0, 0), str(row.amino_acid), size=1, prop=font)
                bounds = glyph.get_extents()
                if bounds.width == 0 or bounds.height == 0:
                    continue
                transform = (
                    Affine2D()
                    .scale(0.86 / bounds.width, height / bounds.height)
                    .translate(float(position) - 0.43, bottom)
                    + axis.transData
                )
                axis.add_patch(
                    PathPatch(
                        glyph,
                        transform=transform,
                        color=AA_COLORS.get(str(row.amino_acid), "#666666"),
                        linewidth=0,
                    )
                )
                bottom += height
        axis.set_xlim(0.4, position_count + 0.6)
        axis.set_ylim(0, math.log2(len(AMINO_ACIDS)) * 1.04)
        axis.set_xlabel("Aligned core-domain position")
        axis.set_ylabel("Information (bits; coverage weighted)")
        axis.set_title(f"Target-family core-domain amino-acid logo (n={sequence_count})")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.grid(False)
    fig.tight_layout()
    fig.savefig(pdf, facecolor="white")
    fig.savefig(png, dpi=dpi, facecolor="white")
    plt.close(fig)


def build_sequence_logo(
    records: OrderedDict[str, str],
    *,
    prealigned: bool,
    source: str,
    aligned_fasta: str,
    table_tsv: str,
    segments_tsv: str,
    status_tsv: str,
    workbook_xlsx: str,
    plot_pdf: str,
    plot_png: str,
    png_dpi: int,
) -> None:
    """Align domain sequences, calculate information content and emit all formal outputs."""

    alignment = records if prealigned else _align_with_mafft(records)
    if alignment:
        lengths = {len(sequence) for sequence in alignment.values()}
        if len(lengths) != 1:
            raise ValueError("Domain alignment must have one common aligned length.")
    write_fasta(alignment, aligned_fasta)
    table = _frequency_table(alignment)
    segments = pd.DataFrame(
        [
            {
                "stable_id": stable_id,
                "aligned_sequence": sequence,
                "aligned_length": len(sequence),
                "ungapped_length": len(sequence.replace("-", "")),
                "alignment_source": source,
                "prealigned_input": prealigned,
            }
            for stable_id, sequence in sorted(alignment.items())
        ],
        columns=[
            "stable_id",
            "aligned_sequence",
            "aligned_length",
            "ungapped_length",
            "alignment_source",
            "prealigned_input",
        ],
    )
    status = pd.DataFrame(
        [
            {
                "status": "PASS" if len(alignment) >= 2 else "NOT_AVAILABLE",
                "sequence_count": len(alignment),
                "alignment_length": len(next(iter(alignment.values()))) if alignment else 0,
                "alignment_source": source,
                "prealigned_input": prealigned,
                "interpretation_limit": (
                    "Logo describes conservation in the validated aligned sequences only; "
                    "it does not establish biochemical function."
                    if len(alignment) >= 2
                    else "At least two validated domain sequences are required for a logo."
                ),
            }
        ]
    )
    save_table(table, table_tsv)
    save_table(segments, segments_tsv)
    save_table(status, status_tsv)
    save_workbook(
        {"domain_segments": segments, "logo_values": table, "status": status},
        workbook_xlsx,
    )
    _plot_logo(table, len(alignment), plot_pdf, plot_png, png_dpi)
