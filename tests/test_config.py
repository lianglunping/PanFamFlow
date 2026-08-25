from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml
from pydantic import ValidationError

from panfamflow.config import WorkflowConfig, load_config, validate_input_paths
from panfamflow.modules import resolve_modules

TOY_CONFIG = Path(__file__).parents[1] / "examples" / "toy" / "config.yaml"


def test_toy_config_loads() -> None:
    config = load_config(TOY_CONFIG)
    assert config.project.name == "toy_gene_family"
    assert [species.id for species in config.inputs.species] == ["SpA", "SpB"]
    assert config.canonical_transcript.backend == "portable_gff3"


def test_toy_family_meets_configured_phylogeny_minimum() -> None:
    config = load_config(TOY_CONFIG)
    members = pd.read_csv(TOY_CONFIG.parent / "references" / "family_members.tsv", sep="\t")
    assert members["stable_id"].nunique() >= config.phylogeny.min_sequences


def test_every_toy_canonical_protein_is_not_nucleotide_like() -> None:
    from Bio.Seq import Seq

    from panfamflow.workflow.scripts.workflow_utils import iter_gff, read_fasta

    nucleotide_codes = set("ACGTUNRYKMSWBDHV")
    for species in ("SpA", "SpB"):
        data_dir = TOY_CONFIG.parent / "data" / species
        genome = read_fasta(data_dir / "genome.fa")
        cds_by_parent: dict[str, list[tuple[int, int, str]]] = {}
        for feature in iter_gff(data_dir / "annotation.gff3"):
            if str(feature["feature"]).lower() != "cds":
                continue
            parent = str(feature["attributes"]["Parent"])
            cds_by_parent.setdefault(parent, []).append(
                (int(feature["start"]), int(feature["end"]), str(feature["seqid"]))
            )
        for segments in cds_by_parent.values():
            coding = "".join(
                genome[seqid][start - 1 : end] for start, end, seqid in sorted(segments)
            )
            protein = str(Seq(coding).translate()).rstrip("*")
            assert protein
            assert len(set(protein)) >= 10
            assert set(protein).difference(nucleotide_codes)


def test_toy_contains_cross_species_homolog_pairs() -> None:
    from Bio.Seq import Seq

    from panfamflow.workflow.scripts.workflow_utils import iter_gff, read_fasta

    proteins: dict[str, str] = {}
    for species in ("SpA", "SpB"):
        data_dir = TOY_CONFIG.parent / "data" / species
        genome = read_fasta(data_dir / "genome.fa")
        cds_by_parent: dict[str, list[tuple[int, int, str]]] = {}
        for feature in iter_gff(data_dir / "annotation.gff3"):
            if str(feature["feature"]).lower() != "cds":
                continue
            parent = str(feature["attributes"]["Parent"])
            cds_by_parent.setdefault(parent, []).append(
                (int(feature["start"]), int(feature["end"]), str(feature["seqid"]))
            )
        for transcript_id, segments in cds_by_parent.items():
            coding = "".join(
                genome[seqid][start - 1 : end] for start, end, seqid in sorted(segments)
            )
            proteins[f"{species}:{transcript_id}"] = str(Seq(coding).translate()).rstrip("*")

    for transcript_a, transcript_b in (("GeneA1.1", "GeneB1.1"), ("GeneA2.1", "GeneB2.1")):
        protein_a = proteins[f"SpA:{transcript_a}"]
        protein_b = proteins[f"SpB:{transcript_b}"]
        assert len(protein_a) >= 50
        assert len(protein_a) == len(protein_b)
        identity = sum(a == b for a, b in zip(protein_a, protein_b, strict=True)) / len(protein_a)
        assert identity >= 0.95


def test_module_dependency_expansion() -> None:
    config = load_config(TOY_CONFIG)
    assert resolve_modules(["phylogeny"], config) == (
        "qc",
        "normalize",
        "family",
        "phylogeny",
    )


def test_duplication_expands_gene_structure_statistics_dependency() -> None:
    config = load_config(TOY_CONFIG)
    resolved = resolve_modules(["duplication"], config)
    assert "gene_structure" in resolved
    assert resolved[-1] == "duplication"


def test_gene_structure_statistics_settings_are_strict_and_reproducible() -> None:
    config = load_config(TOY_CONFIG)
    assert config.gene_structure.metrics == [
        "gene_length",
        "protein_length",
        "cds_length",
        "exon_count",
        "intron_count",
        "total_intron_length",
    ]
    assert config.gene_structure.inference_unit == "species_median"
    assert config.gene_structure.min_group_units == 2
    assert config.gene_structure.alpha == 0.05


def test_kaks_dynamic_dependency_expansion() -> None:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    raw["kaks"]["pair_source"] = "both"
    config = WorkflowConfig.model_validate(raw)
    resolved = resolve_modules(["kaks"], config)
    assert "pan_family" in resolved
    assert "duplication" in resolved
    assert resolved[-1] == "kaks"


def test_complete_chromosome_overlay_expands_pan_family_dependency() -> None:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    raw["schema_version"] = "1.1"
    raw["deliverables"] = {"profile": "pdf_md_complete"}
    config = WorkflowConfig.model_validate(raw)

    resolved = resolve_modules(["chromosome"], config)

    assert "pan_family" in resolved
    assert resolved[-1] == "chromosome"


def test_complete_promoter_hog_summary_expands_pan_family_dependency() -> None:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    raw["schema_version"] = "1.1"
    raw["deliverables"] = {"profile": "pdf_md_complete"}
    config = WorkflowConfig.model_validate(raw)

    resolved = resolve_modules(["promoter"], config)

    assert "pan_family" in resolved
    assert resolved[-1] == "promoter"


def test_qc_path_validation_passes() -> None:
    config = load_config(TOY_CONFIG)
    issues = validate_input_paths(config, TOY_CONFIG, ["qc"])
    assert not [issue for issue in issues if issue.severity == "ERROR"]


def test_duplicate_species_id_is_rejected() -> None:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    raw["inputs"]["species"][1]["id"] = "SpA"
    try:
        WorkflowConfig.model_validate(raw)
    except ValidationError as error:
        assert "Duplicate species IDs" in str(error)
    else:
        raise AssertionError("Duplicate species IDs were accepted")


def test_analysis_and_execution_fingerprints_are_separated() -> None:
    from panfamflow.config import analysis_config_hash, execution_config_hash

    config = load_config(TOY_CONFIG)
    more_cores = config.model_copy(
        update={"run": config.run.model_copy(update={"cores": config.run.cores + 4})}
    )
    assert analysis_config_hash(more_cores) == analysis_config_hash(config)
    assert execution_config_hash(more_cores) != execution_config_hash(config)

    changed_family = config.model_copy(
        update={
            "family": config.family.model_copy(
                update={
                    "hmm": config.family.hmm.model_copy(
                        update={"evalue": config.family.hmm.evalue / 10}
                    )
                }
            )
        }
    )
    assert analysis_config_hash(changed_family) != analysis_config_hash(config)


def test_legacy_pangenome_name_migrates_to_pan_family() -> None:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    raw["pangenome"] = {**raw.pop("pan_family"), "scope": "target_family"}
    raw["run"]["modules"] = ["pangenome"]
    config = WorkflowConfig.model_validate(raw)
    assert config.pan_family.core_min == 0.99
    assert resolve_modules(config.run.modules, config)[-1] == "pan_family"


def test_whole_genome_scope_is_rejected() -> None:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    raw["pangenome"] = {**raw.pop("pan_family"), "scope": "whole_genome"}
    try:
        WorkflowConfig.model_validate(raw)
    except ValidationError as error:
        assert "does not support whole-genome pangenome analysis" in str(error)
    else:
        raise AssertionError("whole_genome scope was accepted")


def test_analysis_scope_is_hard_guard() -> None:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    assert raw["project"]["analysis_scope"] == "target_pan_gene_family"
    raw["project"]["analysis_scope"] = "graph_pangenome"
    try:
        WorkflowConfig.model_validate(raw)
    except ValidationError as error:
        assert "analysis_scope" in str(error)
    else:
        raise AssertionError("Non-family analysis scope was accepted")
