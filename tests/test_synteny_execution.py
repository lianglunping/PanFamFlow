from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).parents[1]
SCRIPT_DIR = ROOT / "src" / "panfamflow" / "workflow" / "scripts"


def _write_inputs(tmp_path: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for species in ("SpA", "SpB"):
        stable_ids = [f"{species}__G{index}" for index in range(1, 7)]
        mapping = pd.DataFrame(
            {
                "stable_id": stable_ids,
                "species_id": [species] * 6,
                "chromosome": ["Chr1"] * 6,
                "gene_start": [100, 250, 400, 550, 700, 850],
                "gene_end": [149, 299, 449, 599, 749, 899],
                "strand": ["+"] * 6,
            }
        )
        paths[f"map_{species}"] = tmp_path / f"{species}.map.tsv"
        mapping.to_csv(paths[f"map_{species}"], sep="\t", index=False)
        paths[f"proteins_{species}"] = tmp_path / f"{species}.proteins.fa"
        paths[f"proteins_{species}"].write_text(
            "".join(f">{stable_id}\n{'M' * 20}\n" for stable_id in stable_ids),
            encoding="utf-8",
        )
        paths[f"genome_{species}"] = tmp_path / f"{species}.genome.fa"
        paths[f"genome_{species}"].write_text(f">Chr1\n{'A' * 1200}\n", encoding="utf-8")
    return paths


def _precomputed_anchors(path: Path) -> None:
    rows = []
    for pair_id, species_1, species_2, second_indices, orientation in (
        ("SpA_self", "SpA", "SpA", [5, 4, 3, 2, 1], "-"),
        ("SpA_vs_SpB", "SpA", "SpB", [1, 2, 3, 4, 5], "+"),
    ):
        for index, second_index in enumerate(second_indices, start=1):
            rows.append(
                {
                    "pair_id": pair_id,
                    "block_id": f"{pair_id}.block_1",
                    "anchor_id": f"{pair_id}.anchor_{index}",
                    "species_1": species_1,
                    "species_2": species_2,
                    "stable_id_1": f"{species_1}__G{index}",
                    "stable_id_2": f"{species_2}__G{second_index}",
                    "orientation": orientation,
                    "score": 100 - index,
                    "evidence_type": "SYNTENY_ANCHOR",
                }
            )
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)


def _run_pair(
    tmp_path: Path,
    paths: dict[str, Path],
    anchors: Path,
    pair_id: str,
    species_1: str,
    species_2: str,
) -> SimpleNamespace:
    output_dir = tmp_path / "pairs" / pair_id
    output = SimpleNamespace(
        anchors=output_dir / "anchors.tsv",
        blocks=output_dir / "blocks.tsv",
        summary=output_dir / "summary.tsv",
        provenance=output_dir / "provenance.json",
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(
            map_1=paths[f"map_{species_1}"],
            map_2=paths[f"map_{species_2}"],
            proteins_1=paths[f"proteins_{species_1}"],
            proteins_2=paths[f"proteins_{species_2}"],
            precomputed=anchors,
        ),
        output=output,
        params=SimpleNamespace(
            pair_id=pair_id,
            species_1=species_1,
            species_2=species_2,
            backend="precomputed",
            min_anchors_per_block=5,
            cscore=0.95,
            tandem_nmax=10,
            work_dir=tmp_path / "work" / pair_id,
        ),
        threads=1,
        log=SimpleNamespace(stdout=tmp_path / "stdout.log", stderr=tmp_path / "stderr.log"),
    )
    runpy.run_path(str(SCRIPT_DIR / "run_synteny.py"), init_globals={"snakemake": fake})
    return output


def test_precomputed_pair_audit_and_three_synteny_figures_execute(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path)
    precomputed = tmp_path / "synteny_anchors.tsv"
    _precomputed_anchors(precomputed)
    self_output = _run_pair(tmp_path, paths, precomputed, "SpA_self", "SpA", "SpA")
    inter_output = _run_pair(tmp_path, paths, precomputed, "SpA_vs_SpB", "SpA", "SpB")

    members = tmp_path / "family_members.tsv"
    pd.DataFrame({"stable_id": ["SpA__G1", "SpA__G2", "SpB__G1", "SpB__G2"]}).to_csv(
        members, sep="\t", index=False
    )
    modes = tmp_path / "duplication_mode.tsv"
    pd.DataFrame(
        {
            "stable_id": ["SpA__G1", "SpA__G2", "SpB__G1", "SpB__G2"],
            "duplication_mode": ["WGD", "Tandem", "WGD", "Singleton"],
        }
    ).to_csv(modes, sep="\t", index=False)

    results = tmp_path / "results"
    names = (
        "anchors",
        "anchors_xlsx",
        "blocks",
        "blocks_xlsx",
        "anchors_intra",
        "anchors_intra_xlsx",
        "blocks_intra",
        "blocks_intra_xlsx",
        "family_links",
        "family_links_xlsx",
        "anchors_inter",
        "anchors_inter_xlsx",
        "blocks_inter",
        "blocks_inter_xlsx",
        "pair_summary",
        "pair_summary_xlsx",
        "layout",
        "layout_xlsx",
        "fig17_pdf",
        "fig17_png",
        "fig21_pdf",
        "fig21_png",
        "fig22_pdf",
        "fig22_png",
    )
    output = SimpleNamespace(
        **{
            name: results
            / (
                f"{name}.xlsx"
                if name.endswith("xlsx")
                else f"{name}.png"
                if name.endswith("png")
                else f"{name}.pdf"
                if name.endswith("pdf")
                else f"{name}.tsv"
            )
            for name in names
        }
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(
            anchors=[self_output.anchors, inter_output.anchors],
            blocks=[self_output.blocks, inter_output.blocks],
            summaries=[self_output.summary, inter_output.summary],
            provenances=[self_output.provenance, inter_output.provenance],
            members=members,
            duplication_modes=modes,
            maps=[paths["map_SpA"], paths["map_SpB"]],
            genomes=[paths["genome_SpA"], paths["genome_SpB"]],
        ),
        output=output,
        params=SimpleNamespace(
            pair_records={
                "SpA_self": {
                    "species_1": "SpA",
                    "species_2": "SpA",
                    "layout_order": 1,
                    "include_overview": False,
                },
                "SpA_vs_SpB": {
                    "species_1": "SpA",
                    "species_2": "SpB",
                    "layout_order": 2,
                    "include_overview": True,
                },
            },
            species_ids=["SpA", "SpB"],
            representative_species="SpA",
            png_dpi=72,
        ),
    )
    runpy.run_path(str(SCRIPT_DIR / "render_synteny_figures.py"), init_globals={"snakemake": fake})

    assert all(
        Path(path).is_file() and Path(path).stat().st_size > 0 for path in vars(output).values()
    )
    assert pd.read_csv(output.pair_summary, sep="\t")["pair_status"].eq("PASS").all()
    assert pd.read_csv(output.family_links, sep="\t")["anchor_qc"].eq("PASS_ORDERED_BLOCK").all()
