from __future__ import annotations

from pathlib import Path

import pandas as pd

from panfamflow.config import load_config, validate_input_paths
from panfamflow.modules import module_names, resolve_modules
from panfamflow.workflow.scripts.expression_de_utils import audit_de_inputs
from panfamflow.workflow.scripts.synteny_utils import ANCHOR_COLUMNS

TOY_COMPLETE = Path(__file__).parents[1] / "examples" / "toy_complete"
CONFIG = TOY_COMPLETE / "config.yaml"


def fasta_sequences(path: Path) -> dict[str, str]:
    sequences: dict[str, str] = {}
    identifier: str | None = None
    chunks: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(">"):
            if identifier is not None:
                sequences[identifier] = "".join(chunks)
            identifier = line[1:].split()[0]
            chunks = []
        else:
            chunks.append(line.strip())
    if identifier is not None:
        sequences[identifier] = "".join(chunks)
    return sequences


def sequence_identity(left: str, right: str) -> float:
    assert len(left) == len(right)
    return sum(a == b for a, b in zip(left, right, strict=True)) / len(left)


def test_toy_complete_enables_the_full_pdf_md_profile() -> None:
    config = load_config(CONFIG)

    assert config.schema_version == "1.1"
    assert config.project.analysis_scope == "target_pan_gene_family"
    assert config.project.seed == 20260821
    assert config.deliverables.profile == "pdf_md_complete"
    assert config.run.engine_runner == "current"
    assert config.run.engine_env is None
    assert resolve_modules(config.run.modules, config) == module_names()
    assert config.comparative_panel.enabled is True
    assert config.comparative_panel.include_in_pan_denominator is False
    assert config.domain_logo.enabled is True
    assert config.synteny.enabled is True
    assert config.synteny.backend == "precomputed"
    assert config.differential_expression.enabled is True
    assert config.differential_expression.input_scale == "raw_counts"
    assert config.plot.pdf is True
    assert config.plot.png is True
    assert config.plot.png_dpi == 600

    issues = validate_input_paths(config, CONFIG)
    assert [issue for issue in issues if issue.severity == "ERROR"] == []


def test_toy_complete_has_four_species_and_sufficient_family_members() -> None:
    config = load_config(CONFIG)
    members = pd.read_csv(TOY_COMPLETE / "references" / "family_members.tsv", sep="\t")

    assert len(config.inputs.species) == 4
    assert set(members["species_id"]) == {species.id for species in config.inputs.species}
    assert members["stable_id"].is_unique
    assert members.groupby("species_id")["stable_id"].nunique().min() >= 6
    assert members["stable_id"].str.contains("__", regex=False).all()


def test_toy_complete_proteins_are_homologous_without_cross_gene_low_complexity() -> None:
    proteins = fasta_sequences(TOY_COMPLETE / "references" / "family_domain_alignment.fa")
    for gene_index in range(1, 7):
        gene = f"Gene{gene_index:02d}"
        assert sequence_identity(proteins[f"SpA__{gene}"], proteins[f"SpD__{gene}"]) > 0.9
    assert sequence_identity(proteins["SpA__Gene01"], proteins["SpA__Gene02"]) < 0.4
    assert all(
        len({sequence[index : index + 2] for index in range(len(sequence) - 1)}) > 35
        for sequence in proteins.values()
    )


def test_toy_complete_precomputed_synteny_is_ordered_multi_anchor_evidence() -> None:
    anchors = pd.read_csv(TOY_COMPLETE / "references" / "synteny_anchors.tsv", sep="\t")

    assert tuple(anchors.columns) == ANCHOR_COLUMNS
    assert anchors["anchor_id"].is_unique
    assert set(anchors["evidence_type"]) == {"SYNTENY_ANCHOR"}
    assert set(anchors["orientation"]) <= {"+", "-"}
    assert anchors.groupby(["pair_id", "block_id"])["anchor_id"].nunique().min() >= 5


def test_toy_complete_raw_counts_cover_abiotic_and_biotic_designs() -> None:
    counts = pd.read_csv(TOY_COMPLETE / "references" / "raw_counts.tsv", sep="\t")
    design = pd.read_csv(TOY_COMPLETE / "references" / "de_design.tsv", sep="\t")
    contrasts = pd.read_csv(TOY_COMPLETE / "references" / "de_contrasts.tsv", sep="\t")

    audited = audit_de_inputs(counts, design, contrasts, min_replicates=2)
    assert set(audited.dataset_audit["stress_category"]) == {"Abiotic", "Biotic"}
    assert audited.dataset_audit["dataset_status"].eq("PASS").all()
    assert audited.contrast_audit["contrast_status"].eq("PASS").all()
    assert audited.contrast_audit["numerator_replicates"].min() >= 2
    assert audited.contrast_audit["denominator_replicates"].min() >= 2


def test_toy_complete_is_a_clean_input_fixture() -> None:
    forbidden = ["results", "work", "logs", ".snakemake", ".panfamflow"]
    assert [name for name in forbidden if (TOY_COMPLETE / name).exists()] == []
