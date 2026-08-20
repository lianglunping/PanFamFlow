from __future__ import annotations

import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

SCRIPT_DIR = Path(__file__).parents[1] / "src" / "panfamflow" / "workflow" / "scripts"
TOY_DIR = Path(__file__).parents[1] / "examples" / "toy"


def test_input_audit_script(tmp_path: Path) -> None:
    output = SimpleNamespace(
        tsv=str(tmp_path / "input_audit.tsv"),
        xlsx=str(tmp_path / "input_audit.xlsx"),
        manifest=str(tmp_path / "manifest.json"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        params=SimpleNamespace(
            records=[
                {
                    "species_id": "SpA",
                    "role": "genome",
                    "path": str(TOY_DIR / "data" / "SpA" / "genome.fa"),
                },
                {
                    "species_id": "SpA",
                    "role": "gff3",
                    "path": str(TOY_DIR / "data" / "SpA" / "annotation.gff3"),
                },
            ],
            calculate_sha256=True,
        ),
        config={"project": {"name": "toy"}, "panfamflow_selected_modules": "qc"},
        output=output,
    )
    runpy.run_path(str(SCRIPT_DIR / "input_audit.py"), init_globals={"snakemake": fake})
    table = pd.read_csv(output.tsv, sep="\t")
    assert table.shape[0] == 2
    assert set(table["status"]) == {"PASS"}
    assert table.loc[table["role"] == "genome", "record_count"].iloc[0] == 2


def test_normalize_canonical_replaces_stale_intermediates_atomically(
    tmp_path: Path, monkeypatch: object
) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "canonical.raw.gff3").write_text("stale\n", encoding="utf-8")
    genome = tmp_path / "genome.fa"
    genome.write_text(">chr1\n" + "ATG" * 30 + "\n", encoding="utf-8")
    gff = tmp_path / "annotation.gff3"
    gff.write_text(
        "##gff-version 3\n"
        "chr1\ttoy\tgene\t1\t90\t.\t+\t.\tID=Gene1\n"
        "chr1\ttoy\tmRNA\t1\t90\t.\t+\t.\tID=Gene1.1;Parent=Gene1\n"
        "chr1\ttoy\texon\t1\t90\t.\t+\t.\tParent=Gene1.1\n"
        "chr1\ttoy\tCDS\t1\t90\t.\t+\t0\tParent=Gene1.1\n",
        encoding="utf-8",
    )

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[0] == "agat_sp_keep_longest_isoform.pl":
            target = Path(command[command.index("--output") + 1])
            if target.exists():
                return subprocess.CompletedProcess(command, 2)
            target.write_text(gff.read_text(encoding="utf-8"), encoding="utf-8")
        elif command[0] == "gffread":
            Path(command[command.index("-w") + 1]).write_text(
                ">Gene1.1\n" + "ATG" * 30 + "\n", encoding="utf-8"
            )
            Path(command[command.index("-x") + 1]).write_text(
                ">Gene1.1\n" + "ATG" * 30 + "\n", encoding="utf-8"
            )
            Path(command[command.index("-y") + 1]).write_text(
                ">Gene1.1\n" + "M" * 30 + "\n", encoding="utf-8"
            )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)  # type: ignore[attr-defined]
    output = SimpleNamespace(
        gff3=str(tmp_path / "results" / "canonical.gff3"),
        proteins=str(tmp_path / "results" / "proteins.fa"),
        cds=str(tmp_path / "results" / "cds.fa"),
        transcripts=str(tmp_path / "results" / "transcripts.fa"),
        mapping=str(tmp_path / "results" / "mapping.tsv"),
        mapping_xlsx=str(tmp_path / "results" / "mapping.xlsx"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(gff3=str(gff), genome=str(genome)),
        output=output,
        params=SimpleNamespace(
            species="SpA",
            species_name="Species A",
            backend="agat",
            separator="__",
            work_dir=str(work_dir),
            group="Group1",
            subfamily="CladeA",
        ),
        log=SimpleNamespace(
            agat_stdout=str(tmp_path / "logs" / "agat.stdout.log"),
            agat_stderr=str(tmp_path / "logs" / "agat.stderr.log"),
            gffread_stdout=str(tmp_path / "logs" / "gffread.stdout.log"),
            gffread_stderr=str(tmp_path / "logs" / "gffread.stderr.log"),
        ),
    )

    runpy.run_path(str(SCRIPT_DIR / "normalize_canonical.py"), init_globals={"snakemake": fake})

    mapping = pd.read_csv(output.mapping, sep="\t")
    assert mapping.loc[0, "stable_id"] == "SpA__Gene1"
    assert not genome.with_suffix(".fa.fai").exists()


def test_normalize_canonical_portable_backend_does_not_call_agat(
    tmp_path: Path, monkeypatch: object
) -> None:
    work_dir = tmp_path / "work"
    genome = tmp_path / "genome.fa"
    genome.write_text(">chr1\n" + "ATG" * 30 + "\n", encoding="utf-8")
    gff = tmp_path / "annotation.gff3"
    gff.write_text(
        "##gff-version 3\n"
        "chr1\ttoy\tgene\t1\t90\t.\t+\t.\tID=Gene1\n"
        "chr1\ttoy\tmRNA\t1\t90\t.\t+\t.\tID=Gene1.1;Parent=Gene1\n"
        "chr1\ttoy\texon\t1\t90\t.\t+\t.\tParent=Gene1.1\n"
        "chr1\ttoy\tCDS\t1\t90\t.\t+\t0\tParent=Gene1.1\n",
        encoding="utf-8",
    )

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert command[0] == "gffread"
        Path(command[command.index("-w") + 1]).write_text(
            ">Gene1.1\n" + "ATG" * 30 + "\n", encoding="utf-8"
        )
        Path(command[command.index("-x") + 1]).write_text(
            ">Gene1.1\n" + "ATG" * 30 + "\n", encoding="utf-8"
        )
        Path(command[command.index("-y") + 1]).write_text(
            ">Gene1.1\n" + "M" * 30 + "\n", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)  # type: ignore[attr-defined]
    output = SimpleNamespace(
        gff3=str(tmp_path / "results" / "canonical.gff3"),
        proteins=str(tmp_path / "results" / "proteins.fa"),
        cds=str(tmp_path / "results" / "cds.fa"),
        transcripts=str(tmp_path / "results" / "transcripts.fa"),
        mapping=str(tmp_path / "results" / "mapping.tsv"),
        mapping_xlsx=str(tmp_path / "results" / "mapping.xlsx"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(gff3=str(gff), genome=str(genome)),
        output=output,
        params=SimpleNamespace(
            species="SpA",
            species_name="Species A",
            backend="portable_gff3",
            separator="__",
            work_dir=str(work_dir),
            group="Group1",
            subfamily="CladeA",
        ),
        log=SimpleNamespace(
            agat_stdout=str(tmp_path / "logs" / "canonical_selector.stdout.log"),
            agat_stderr=str(tmp_path / "logs" / "canonical_selector.stderr.log"),
            gffread_stdout=str(tmp_path / "logs" / "gffread.stdout.log"),
            gffread_stderr=str(tmp_path / "logs" / "gffread.stderr.log"),
        ),
    )

    runpy.run_path(str(SCRIPT_DIR / "normalize_canonical.py"), init_globals={"snakemake": fake})

    assert "Gene1.1" in Path(output.gff3).read_text(encoding="utf-8")
    assert "portable_gff3" in Path(fake.log.agat_stdout).read_text(encoding="utf-8")


def test_promoter_rule_passes_stable_id_separator() -> None:
    rule = (
        Path(__file__).parents[1] / "src" / "panfamflow" / "workflow" / "rules" / "promoter.smk"
    ).read_text(encoding="utf-8")
    extract_block = rule.split("rule extract_family_promoters:", 1)[1].split(
        "if PROMOTER_BACKEND", 1
    )[0]
    assert "separator=SEPARATOR" in extract_block
    assert "gff3s=NORMALIZED_GFFS" in extract_block


def test_orthofinder_resolves_work_directory_before_changing_cwd() -> None:
    script = (SCRIPT_DIR / "run_orthofinder.py").read_text(encoding="utf-8")
    assert "work_dir = Path(snakemake.params.work_dir).resolve()" in script


def test_orthofinder_does_not_precreate_custom_output_directory() -> None:
    script = (SCRIPT_DIR / "run_orthofinder.py").read_text(encoding="utf-8")
    assert "result_dir.rmdir()" in script
    assert "result_dir.parent.mkdir(parents=True, exist_ok=True)" in script
    assert "result_dir.mkdir(parents=True, exist_ok=True)" not in script


def test_pan_family_parser(tmp_path: Path) -> None:
    result_dir = tmp_path / "orthofinder"
    hog_dir = result_dir / "Phylogenetic_Hierarchical_Orthogroups"
    hog_dir.mkdir(parents=True)
    (hog_dir / "N0.tsv").write_text(
        "HOG\tOG\tGene Tree Parent Clade\tSpA\tSpB\n"
        "N0.HOG0000001\tOG0000001\tN0\tSpA__GeneA1\tSpB__GeneB1\n"
        "N0.HOG0000002\tOG0000002\tN0\tSpA__Other\t\n",
        encoding="utf-8",
    )
    marker = tmp_path / "result_dir.txt"
    marker.write_text(str(result_dir), encoding="utf-8")
    members = tmp_path / "family_members.tsv"
    members.write_text(
        "species_id\tgene_id\tstable_id\nSpA\tGeneA1\tSpA__GeneA1\nSpB\tGeneB1\tSpB__GeneB1\n",
        encoding="utf-8",
    )
    output = SimpleNamespace(
        classification=str(tmp_path / "classification.tsv"),
        membership=str(tmp_path / "membership.tsv"),
        presence=str(tmp_path / "presence.tsv"),
        unassigned_members=str(tmp_path / "unassigned.tsv"),
        rarefaction=str(tmp_path / "rarefaction.tsv"),
        rarefaction_summary=str(tmp_path / "rarefaction_summary.tsv"),
        xlsx=str(tmp_path / "pan_family.xlsx"),
        class_plot_pdf=str(tmp_path / "classes.pdf"),
        class_plot_png=str(tmp_path / "classes.png"),
        rarefaction_plot_pdf=str(tmp_path / "rarefaction.pdf"),
        rarefaction_plot_png=str(tmp_path / "rarefaction.png"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(result_dir=str(marker), members=str(members)),
        output=output,
        params=SimpleNamespace(
            species_ids=["SpA", "SpB"],
            separator="__",
            hog_node="N0",
            core_min=0.99,
            soft_core_min=0.90,
            shell_min=0.10,
            rarefaction_iterations=10,
            max_exact_combinations=100,
            seed=20260807,
            png_dpi=120,
        ),
    )
    runpy.run_path(str(SCRIPT_DIR / "parse_pan_family.py"), init_globals={"snakemake": fake})
    classification = pd.read_csv(output.classification, sep="\t")
    assert classification.shape[0] == 1
    assert classification.loc[0, "pan_family_class"] == "Core"
    assert classification.loc[0, "analysis_scope"] == "TARGET_GENE_FAMILY_ONLY"
    assert classification.loc[0, "HOG_ID"] == "N0.HOG0000001"
    unassigned = pd.read_csv(output.unassigned_members, sep="\t")
    assert unassigned.empty
    assert Path(output.class_plot_pdf).is_file()


def test_pan_family_parser_falls_back_to_public_orthogroups_in_auto_mode(
    tmp_path: Path,
) -> None:
    result_dir = tmp_path / "orthofinder"
    (result_dir / "Phylogenetic_Hierarchical_Orthogroups").mkdir(parents=True)
    orthogroup_dir = result_dir / "Orthogroups"
    orthogroup_dir.mkdir()
    (orthogroup_dir / "Orthogroups.tsv").write_text(
        "Orthogroup\tSpA\tSpB\nOG0000000\tSpA__GeneA1\tSpB__GeneB1\n",
        encoding="utf-8",
    )
    marker = tmp_path / "result_dir.txt"
    marker.write_text(str(result_dir), encoding="utf-8")
    members = tmp_path / "family_members.tsv"
    members.write_text(
        "species_id\tgene_id\tstable_id\nSpA\tGeneA1\tSpA__GeneA1\nSpB\tGeneB1\tSpB__GeneB1\n",
        encoding="utf-8",
    )
    output = SimpleNamespace(
        classification=str(tmp_path / "classification.tsv"),
        membership=str(tmp_path / "membership.tsv"),
        presence=str(tmp_path / "presence.tsv"),
        unassigned_members=str(tmp_path / "unassigned.tsv"),
        rarefaction=str(tmp_path / "rarefaction.tsv"),
        rarefaction_summary=str(tmp_path / "rarefaction_summary.tsv"),
        xlsx=str(tmp_path / "pan_family.xlsx"),
        class_plot_pdf=str(tmp_path / "classes.pdf"),
        class_plot_png=str(tmp_path / "classes.png"),
        rarefaction_plot_pdf=str(tmp_path / "rarefaction.pdf"),
        rarefaction_plot_png=str(tmp_path / "rarefaction.png"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(result_dir=str(marker), members=str(members)),
        output=output,
        params=SimpleNamespace(
            species_ids=["SpA", "SpB"],
            separator="__",
            hog_node="auto",
            core_min=0.99,
            soft_core_min=0.90,
            shell_min=0.10,
            rarefaction_iterations=10,
            max_exact_combinations=100,
            seed=20260807,
            png_dpi=120,
        ),
    )

    runpy.run_path(str(SCRIPT_DIR / "parse_pan_family.py"), init_globals={"snakemake": fake})

    classification = pd.read_csv(output.classification, sep="\t")
    assert classification.loc[0, "HOG_ID"] == "OG0000000"
    assert classification.loc[0, "orthology_group_type"] == "ORTHOGROUP"
    assert classification.loc[0, "analysis_unit"] == "ORTHOFINDER_ORTHOGROUP"
    assert classification.loc[0, "hog_node_status"] == "AUTO_ORTHOGROUP_FALLBACK"
    assert classification.loc[0, "orthology_source_file"] == "Orthogroups/Orthogroups.tsv"


def test_stringtie_combiner_uses_species_scoped_gene_ids(tmp_path: Path) -> None:
    members = tmp_path / "family_members.tsv"
    members.write_text(
        "stable_id\tspecies_id\tgene_id\tsubfamily\n"
        "SpA__Gene1\tSpA\tGene1\tA\n"
        "SpA__Gene2\tSpA\tGene2\tA\n"
        "SpB__Gene1\tSpB\tGene1\tB\n",
        encoding="utf-8",
    )
    map_a = tmp_path / "SpA.map.tsv"
    map_b = tmp_path / "SpB.map.tsv"
    map_a.write_text(
        "species_id\tgene_id\tstable_id\nSpA\tGene1\tSpA__Gene1\nSpA\tGene2\tSpA__Gene2\n",
        encoding="utf-8",
    )
    map_b.write_text(
        "species_id\tgene_id\tstable_id\nSpB\tGene1\tSpB__Gene1\n",
        encoding="utf-8",
    )
    abundance_a = tmp_path / "sample_a.tsv"
    abundance_b = tmp_path / "sample_b.tsv"
    abundance_a.write_text("Gene ID\tTPM\nGene1\t3.5\n", encoding="utf-8")
    abundance_b.write_text("Gene ID\tTPM\nGene1\t8.0\n", encoding="utf-8")
    output = SimpleNamespace(
        matrix=str(tmp_path / "expression_matrix.tsv"),
        long=str(tmp_path / "expression_long.tsv"),
        summary=str(tmp_path / "expression_summary.tsv"),
        xlsx=str(tmp_path / "expression.xlsx"),
        plot_pdf=str(tmp_path / "expression.pdf"),
        plot_png=str(tmp_path / "expression.png"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(
            members=str(members),
            maps=[str(map_a), str(map_b)],
            abundance=[str(abundance_a), str(abundance_b)],
        ),
        output=output,
        params=SimpleNamespace(
            sample_ids=["SampleA", "SampleB"],
            sample_species_ids=["SpA", "SpB"],
            min_tpm_detected=1.0,
            heatmap_transform="log2_tpm1_zscore",
            png_dpi=120,
        ),
    )
    runpy.run_path(str(SCRIPT_DIR / "combine_stringtie.py"), init_globals={"snakemake": fake})
    matrix = pd.read_csv(output.matrix, sep="\t").set_index("stable_id")
    assert matrix.loc["SpA__Gene1", "SampleA"] == 3.5
    assert pd.isna(matrix.loc["SpA__Gene1", "SampleB"])
    assert matrix.loc["SpA__Gene2", "SampleA"] == 0.0
    assert pd.isna(matrix.loc["SpA__Gene2", "SampleB"])
    assert pd.isna(matrix.loc["SpB__Gene1", "SampleA"])
    assert matrix.loc["SpB__Gene1", "SampleB"] == 8.0

    long = pd.read_csv(output.long, sep="\t")
    status = long.set_index(["stable_id", "sample_id"])["measurement_status"]
    assert status.loc[("SpA__Gene1", "SampleA")] == "MEASURED"
    assert status.loc[("SpA__Gene2", "SampleA")] == "ASSAYED_ZERO"
    assert status.loc[("SpA__Gene1", "SampleB")] == "NOT_APPLICABLE"
    detected = long.set_index(["stable_id", "sample_id"])["detected"]
    assert pd.isna(detected.loc[("SpA__Gene1", "SampleB")])

    summary = pd.read_csv(output.summary, sep="\t").set_index("stable_id")
    assert summary.loc["SpA__Gene2", "samples_available"] == 1
    assert summary.loc["SpA__Gene2", "expression_detected_samples"] == 0
    assert summary.loc["SpA__Gene2", "expression_detected_fraction"] == 0.0
    assert summary.loc["SpA__Gene2", "measured_samples"] == 0
    assert summary.loc["SpA__Gene2", "assayed_zero_samples"] == 1


def test_imported_expression_excludes_missing_cells_from_detection_denominator(
    tmp_path: Path,
) -> None:
    members = tmp_path / "family_members.tsv"
    members.write_text(
        "stable_id\tspecies_id\tgene_id\tsubfamily\n"
        "SpA__Gene1\tSpA\tGene1\tA\n"
        "SpA__Gene2\tSpA\tGene2\tA\n",
        encoding="utf-8",
    )
    matrix = tmp_path / "expression.tsv"
    matrix.write_text(
        "stable_id\tSample1\tSample2\nSpA__Gene1\t2.5\t\nSpA__Gene2\t\t\n",
        encoding="utf-8",
    )
    output = SimpleNamespace(
        matrix=str(tmp_path / "expression_matrix.tsv"),
        long=str(tmp_path / "expression_long.tsv"),
        summary=str(tmp_path / "expression_summary.tsv"),
        xlsx=str(tmp_path / "expression.xlsx"),
        plot_pdf=str(tmp_path / "expression.pdf"),
        plot_png=str(tmp_path / "expression.png"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(members=str(members), matrix=str(matrix)),
        output=output,
        params=SimpleNamespace(
            separator="__",
            min_tpm_detected=1.0,
            heatmap_transform="log2_tpm1_zscore",
            png_dpi=120,
        ),
    )

    runpy.run_path(str(SCRIPT_DIR / "import_expression.py"), init_globals={"snakemake": fake})

    wide = pd.read_csv(output.matrix, sep="\t").set_index("stable_id")
    assert wide.loc["SpA__Gene1", "expression_data_status"] == "PARTIAL_MISSING"
    assert wide.loc["SpA__Gene2", "expression_data_status"] == "MISSING"

    long = pd.read_csv(output.long, sep="\t").set_index(["stable_id", "sample_id"])
    assert long.loc[("SpA__Gene1", "Sample1"), "measurement_status"] == "OBSERVED"
    assert long.loc[("SpA__Gene1", "Sample2"), "measurement_status"] == "MISSING_IN_INPUT"
    assert pd.isna(long.loc[("SpA__Gene1", "Sample2"), "detected"])

    summary = pd.read_csv(output.summary, sep="\t").set_index("stable_id")
    assert summary.loc["SpA__Gene1", "samples_available"] == 1
    assert summary.loc["SpA__Gene1", "expression_detected_samples"] == 1
    assert summary.loc["SpA__Gene1", "expression_detected_fraction"] == 1.0
    assert summary.loc["SpA__Gene2", "samples_available"] == 0
    assert summary.loc["SpA__Gene2", "expression_detected_samples"] == 0
    assert pd.isna(summary.loc["SpA__Gene2", "expression_detected_fraction"])


def test_orthofinder_preserves_prefixed_stable_ids() -> None:
    source = (SCRIPT_DIR / "run_orthofinder.py").read_text(encoding="utf-8")
    assert '"-X"' in source


def test_orthofinder_marker_contract_matches_pan_family_consumer() -> None:
    orthology = (SCRIPT_DIR.parent / "rules" / "orthology.smk").read_text(encoding="utf-8")
    pan_family = (SCRIPT_DIR.parent / "rules" / "pan_family.smk").read_text(encoding="utf-8")
    marker = "orthofinder_result_dir.txt"
    assert marker in orthology
    assert marker in pan_family
    assert "orthofinder.result_dir.txt" not in pan_family


def test_promoter_rule_declares_all_script_outputs_and_separator() -> None:
    rule = (SCRIPT_DIR.parent / "rules" / "promoter.smk").read_text(encoding="utf-8")
    script = (SCRIPT_DIR / "parse_promoter_elements.py").read_text(encoding="utf-8")
    for key in (
        "elements",
        "summary",
        "per_gene",
        "xlsx",
        "class_plot_pdf",
        "class_plot_png",
        "top_plot_pdf",
        "top_plot_png",
    ):
        assert f"snakemake.output.{key}" in script
        assert f"{key}=" in rule
    assert "separator=SEPARATOR" in rule
    assert "promoter_elements_per_gene.tsv" in rule
