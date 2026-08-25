from __future__ import annotations

import hashlib
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from panfamflow.workflow.scripts.promoter_distribution_utils import (
    build_promoter_distributions,
    build_promoter_hog_distributions,
)

SCRIPT_DIR = Path(__file__).parents[1] / "src" / "panfamflow" / "workflow" / "scripts"
TOY_DIR = Path(__file__).parents[1] / "examples" / "toy"


def test_family_tree_annotations_reconcile_exactly_with_accepted_members(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from phylogeny_figure_utils import build_tip_annotations, render_family_tree
    finally:
        sys.path.pop(0)

    tree = tmp_path / "family.treefile"
    tree.write_text("((SpA__Gene1:0.1,SpB__Gene1:0.2)95:0.1,SpC__Gene1:0.3);\n")
    members = tmp_path / "family_members.tsv"
    members.write_text(
        "stable_id\tspecies_id\tgene_id\tgroup\tsubfamily\n"
        "SpA__Gene1\tSpA\tGene1\tIndica\tS1\n"
        "SpB__Gene1\tSpB\tGene1\tJaponica\tS1\n"
        "SpC__Gene1\tSpC\tGene1\tWild\tS2\n",
        encoding="utf-8",
    )
    annotations = build_tip_annotations(tree, members)
    assert annotations["stable_id"].tolist() == [
        "SpA__Gene1",
        "SpB__Gene1",
        "SpC__Gene1",
    ]
    assert annotations["tree_tip_status"].eq("MATCHED_ACCEPTED_MEMBER").all()
    render_family_tree(
        tree,
        annotations,
        tmp_path / "family_tree",
        png_dpi=72,
    )
    assert (tmp_path / "family_tree.pdf").stat().st_size > 0
    assert (tmp_path / "family_tree.png").stat().st_size > 0


def test_family_tree_renderer_accepts_iqtree_composite_internal_support(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from phylogeny_figure_utils import render_family_tree
    finally:
        sys.path.pop(0)

    tree = tmp_path / "family.treefile"
    tree.write_text("((A:0.1,B:0.2)0/59:0.1,C:0.3);\n", encoding="utf-8")
    annotations = pd.DataFrame(
        {
            "stable_id": ["A", "B", "C"],
            "species_id": ["SpA", "SpB", "SpC"],
        }
    )
    render_family_tree(tree, annotations, tmp_path / "supported_tree", png_dpi=72)
    assert (tmp_path / "supported_tree.pdf").stat().st_size > 0
    assert (tmp_path / "supported_tree.png").stat().st_size > 0


def test_explicit_comparative_panel_keeps_external_sequences_out_of_pan_denominator(
    tmp_path: Path,
) -> None:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from comparative_phylogeny_utils import build_comparative_panel
    finally:
        sys.path.pop(0)

    external_fasta = tmp_path / "external.fa"
    external_fasta.write_text(">ExtGene1\nACDEFGHIK\n", encoding="utf-8")
    members = pd.DataFrame(
        {
            "stable_id": ["SpA__Gene1", "SpB__Gene1"],
            "species_id": ["SpA", "SpB"],
            "gene_id": ["Gene1", "Gene1"],
            "group": ["Indica", "Japonica"],
            "subfamily": ["S1", "S1"],
        }
    )
    proteins = {"SpA__Gene1": "ACDEFGHIK", "SpB__Gene1": "ACDEYGHIK"}
    registry = pd.DataFrame(
        [
            {"source_type": "INTERNAL", "stable_id": "SpA__Gene1"},
            {
                "source_type": "EXTERNAL",
                "stable_id": "Ext__Gene1",
                "species_id": "Ext",
                "sequence_path": str(external_fasta),
                "sequence_id": "ExtGene1",
                "accession": "TEST0001",
                "version": "1",
                "source_url": "https://example.org/TEST0001.1",
                "expected_sha256": hashlib.sha256(external_fasta.read_bytes()).hexdigest(),
                "outgroup": True,
            },
        ]
    )
    sequences, selection, provenance = build_comparative_panel(
        members,
        proteins,
        registry,
        strategy="explicit",
        seed=20260807,
        registry_root=tmp_path,
    )
    assert list(sequences) == ["SpA__Gene1", "Ext__Gene1"]
    assert selection["include_in_pan_denominator"].eq(False).all()
    assert provenance.loc[0, "observed_sha256"] == registry.loc[1, "expected_sha256"]


def test_comparative_phylogeny_script_materializes_fig03_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import workflow_utils
    finally:
        sys.path.pop(0)

    external_fasta = tmp_path / "external.fa"
    external_fasta.write_text(">ExtGene1\nACDEFGHIK\n", encoding="utf-8")
    members = tmp_path / "family_members.tsv"
    members.write_text(
        "stable_id\tspecies_id\tgene_id\tgroup\tsubfamily\n"
        "SpA__Gene1\tSpA\tGene1\tIndica\tS1\n"
        "SpB__Gene1\tSpB\tGene1\tJaponica\tS1\n"
        "SpC__Gene1\tSpC\tGene1\tWild\tS2\n",
        encoding="utf-8",
    )
    proteins = tmp_path / "family_proteins.fa"
    proteins.write_text(
        ">SpA__Gene1\nACDEFGHIK\n>SpB__Gene1\nACDEYGHIK\n>SpC__Gene1\nACDEFGHLK\n",
        encoding="utf-8",
    )
    registry = tmp_path / "external_species.tsv"
    registry.write_text(
        "source_type\tstable_id\tspecies_id\tsequence_path\tsequence_id\taccession\t"
        "version\tsource_url\texpected_sha256\toutgroup\n"
        "INTERNAL\tSpA__Gene1\tSpA\t\t\t\t\t\t\tfalse\n"
        "INTERNAL\tSpB__Gene1\tSpB\t\t\t\t\t\t\tfalse\n"
        "INTERNAL\tSpC__Gene1\tSpC\t\t\t\t\t\t\tfalse\n"
        f"EXTERNAL\tExt__Gene1\tExt\t{external_fasta}\tExtGene1\tTEST0001\t1\t"
        f"https://example.org/TEST0001.1\t{hashlib.sha256(external_fasta.read_bytes()).hexdigest()}\ttrue\n",
        encoding="utf-8",
    )

    def fake_run_command(
        command: list[str], *, stdout_path: str | Path | None = None, **_: object
    ) -> None:
        if command[0] == "mafft":
            Path(str(stdout_path)).write_text(Path(command[-1]).read_text(encoding="utf-8"))
        elif command[0] == "clipkit":
            output = Path(command[command.index("-o") + 1])
            output.write_text(Path(command[1]).read_text(encoding="utf-8"))
        elif command[0] == "iqtree3":
            prefix = Path(command[command.index("--prefix") + 1])
            prefix.with_suffix(".treefile").write_text(
                "(((SpA__Gene1:0.1,SpB__Gene1:0.1)95:0.1,SpC__Gene1:0.2)90:0.1,Ext__Gene1:0.4);\n",
                encoding="utf-8",
            )
            prefix.with_suffix(".iqtree").write_text("mock report\n", encoding="utf-8")
        else:
            raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(workflow_utils, "run_command", fake_run_command)
    monkeypatch.setattr(
        workflow_utils,
        "executable_version",
        lambda *_args, **_kwargs: ("iqtree3", "IQ-TREE 3.1.3"),
    )
    result_dir = tmp_path / "results"
    output = SimpleNamespace(
        selection=str(result_dir / "comparative_panel_selection.tsv"),
        provenance=str(result_dir / "external_sequence_provenance.tsv"),
        fasta=str(result_dir / "comparative_panel.fa"),
        alignment=str(result_dir / "comparative.aligned.fa"),
        trimmed=str(result_dir / "comparative.trimmed.fa"),
        tree=str(result_dir / "comparative.treefile"),
        report=str(result_dir / "comparative.iqtree"),
        tip_annotations=str(result_dir / "comparative_tree_tip_annotations.tsv"),
        figure_pdf=str(result_dir / "Fig03_representative_external_tree.pdf"),
        figure_png=str(result_dir / "Fig03_representative_external_tree.png"),
    )
    fake = SimpleNamespace(
        scriptdir=str(SCRIPT_DIR),
        input=SimpleNamespace(proteins=str(proteins), members=str(members), registry=str(registry)),
        output=output,
        params=SimpleNamespace(
            selection_strategy="explicit",
            min_sequences=4,
            mafft_mode="auto",
            trim_mode="smart-gap",
            model="MFP",
            ultrafast_bootstrap=1000,
            sh_alrt=1000,
            seed=20260807,
            work_dir=str(tmp_path / "work"),
            png_dpi=120,
        ),
        threads=2,
        log=SimpleNamespace(
            mafft=str(tmp_path / "mafft.log"),
            clipkit_stdout=str(tmp_path / "clipkit.out"),
            clipkit_stderr=str(tmp_path / "clipkit.err"),
            iqtree_stdout=str(tmp_path / "iqtree.out"),
            iqtree_stderr=str(tmp_path / "iqtree.err"),
        ),
    )
    runpy.run_path(
        str(SCRIPT_DIR / "run_comparative_phylogeny.py"), init_globals={"snakemake": fake}
    )
    annotations = pd.read_csv(output.tip_annotations, sep="\t")
    assert annotations["tree_tip_status"].eq("MATCHED_COMPARATIVE_PANEL").all()
    assert annotations.loc[annotations["source_type"].eq("EXTERNAL"), "outgroup"].all()
    assert Path(output.figure_pdf).stat().st_size > 0
    assert Path(output.figure_png).stat().st_size > 0


def test_sequence_logo_outputs_are_auditable(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        from sequence_logo_utils import build_sequence_logo
    finally:
        sys.path.pop(0)

    records = {
        "SpA__Gene1": "ACDEFGHIK",
        "SpB__Gene1": "ACDEYGHIK",
        "SpC__Gene1": "ACDEFGHIK",
    }
    outputs = {
        "aligned_fasta": str(tmp_path / "domains.aligned.fa"),
        "table_tsv": str(tmp_path / "logo.tsv"),
        "segments_tsv": str(tmp_path / "family_domain_segments.tsv"),
        "status_tsv": str(tmp_path / "status.tsv"),
        "workbook_xlsx": str(tmp_path / "logo.xlsx"),
        "plot_pdf": str(tmp_path / "logo.pdf"),
        "plot_png": str(tmp_path / "logo.png"),
    }
    build_sequence_logo(
        records,  # type: ignore[arg-type]
        prealigned=True,
        source="TEST_PREALIGNED",
        png_dpi=120,
        **outputs,
    )
    status = pd.read_csv(outputs["status_tsv"], sep="\t")
    values = pd.read_csv(outputs["table_tsv"], sep="\t")
    segments = pd.read_csv(outputs["segments_tsv"], sep="\t")
    assert status.loc[0, "status"] == "PASS"
    assert status.loc[0, "sequence_count"] == 3
    assert values["alignment_position"].max() == 9
    assert values.groupby("alignment_position")["letter_height_bits"].sum().gt(0).all()
    assert segments["stable_id"].tolist() == sorted(records)
    assert set(segments["alignment_source"]) == {"TEST_PREALIGNED"}
    assert segments["aligned_length"].eq(9).all()
    assert Path(outputs["plot_pdf"]).stat().st_size > 0
    assert Path(outputs["plot_png"]).stat().st_size > 0


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


def test_normalize_rule_uses_backend_specific_conda_environment() -> None:
    rule = (SCRIPT_DIR.parent / "rules" / "normalize.smk").read_text(encoding="utf-8")
    portable_environment = (SCRIPT_DIR.parent / "envs" / "normalize_portable.yaml").read_text(
        encoding="utf-8"
    )
    assert 'if CANONICAL_BACKEND == "agat"' in rule
    assert '"../envs/normalize_portable.yaml"' in rule
    assert "agat" not in portable_environment.lower()
    assert "gffread" in portable_environment.lower()


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
        class_summary=str(tmp_path / "class_summary.tsv"),
        hog_gene_counts=str(tmp_path / "hog_gene_counts.tsv"),
        species_class_summary=str(tmp_path / "species_class_summary.tsv"),
        subfamily_class_summary=str(tmp_path / "subfamily_class_summary.tsv"),
        xlsx=str(tmp_path / "pan_family.xlsx"),
        class_plot_pdf=str(tmp_path / "classes.pdf"),
        class_plot_png=str(tmp_path / "classes.png"),
        dual_denominator_plot_pdf=str(tmp_path / "dual.pdf"),
        dual_denominator_plot_png=str(tmp_path / "dual.png"),
        species_class_plot_pdf=str(tmp_path / "species_classes.pdf"),
        species_class_plot_png=str(tmp_path / "species_classes.png"),
        subfamily_class_plot_pdf=str(tmp_path / "subfamily_classes.pdf"),
        subfamily_class_plot_png=str(tmp_path / "subfamily_classes.png"),
        rarefaction_plot_pdf=str(tmp_path / "rarefaction.pdf"),
        rarefaction_plot_png=str(tmp_path / "rarefaction.png"),
        fig10_pdf=str(tmp_path / "Fig10.pdf"),
        fig10_png=str(tmp_path / "Fig10.png"),
        fig11_pdf=str(tmp_path / "Fig11.pdf"),
        fig11_png=str(tmp_path / "Fig11.png"),
        fig12_pdf=str(tmp_path / "Fig12.pdf"),
        fig12_png=str(tmp_path / "Fig12.png"),
        fig13_pdf=str(tmp_path / "Fig13.pdf"),
        fig13_png=str(tmp_path / "Fig13.png"),
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
        class_summary=str(tmp_path / "class_summary.tsv"),
        hog_gene_counts=str(tmp_path / "hog_gene_counts.tsv"),
        species_class_summary=str(tmp_path / "species_class_summary.tsv"),
        subfamily_class_summary=str(tmp_path / "subfamily_class_summary.tsv"),
        xlsx=str(tmp_path / "pan_family.xlsx"),
        class_plot_pdf=str(tmp_path / "classes.pdf"),
        class_plot_png=str(tmp_path / "classes.png"),
        dual_denominator_plot_pdf=str(tmp_path / "dual.pdf"),
        dual_denominator_plot_png=str(tmp_path / "dual.png"),
        species_class_plot_pdf=str(tmp_path / "species_classes.pdf"),
        species_class_plot_png=str(tmp_path / "species_classes.png"),
        subfamily_class_plot_pdf=str(tmp_path / "subfamily_classes.pdf"),
        subfamily_class_plot_png=str(tmp_path / "subfamily_classes.png"),
        rarefaction_plot_pdf=str(tmp_path / "rarefaction.pdf"),
        rarefaction_plot_png=str(tmp_path / "rarefaction.png"),
        fig10_pdf=str(tmp_path / "Fig10.pdf"),
        fig10_png=str(tmp_path / "Fig10.png"),
        fig11_pdf=str(tmp_path / "Fig11.pdf"),
        fig11_png=str(tmp_path / "Fig11.png"),
        fig12_pdf=str(tmp_path / "Fig12.pdf"),
        fig12_png=str(tmp_path / "Fig12.png"),
        fig13_pdf=str(tmp_path / "Fig13.pdf"),
        fig13_png=str(tmp_path / "Fig13.png"),
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
        scaled=str(tmp_path / "expression_scaled.tsv"),
        sample_metadata_audit=str(tmp_path / "sample_metadata_audit.tsv"),
        gene_condition=str(tmp_path / "expression_gene_condition.tsv"),
        stratified_summary=str(tmp_path / "expression_stratified_summary.tsv"),
        stratified_xlsx=str(tmp_path / "expression_stratified_summary.xlsx"),
        pan_class_table=str(tmp_path / "expression_by_pan_class.tsv"),
        pan_tissue_table=str(tmp_path / "expression_by_pan_class_tissue.tsv"),
        group_subfamily_table=str(tmp_path / "expression_by_group_subfamily.tsv"),
        overall_pdf=str(tmp_path / "expression_overall.pdf"),
        overall_png=str(tmp_path / "expression_overall.png"),
        pan_class_pdf=str(tmp_path / "expression_pan_class.pdf"),
        pan_class_png=str(tmp_path / "expression_pan_class.png"),
        pan_tissue_pdf=str(tmp_path / "expression_pan_tissue.pdf"),
        pan_tissue_png=str(tmp_path / "expression_pan_tissue.png"),
        group_subfamily_pdf=str(tmp_path / "expression_group_subfamily.pdf"),
        group_subfamily_png=str(tmp_path / "expression_group_subfamily.png"),
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
            sample_metadata=None,
            pan_membership=None,
            pan_classification=None,
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
        scaled=str(tmp_path / "expression_scaled.tsv"),
        sample_metadata_audit=str(tmp_path / "sample_metadata_audit.tsv"),
        gene_condition=str(tmp_path / "expression_gene_condition.tsv"),
        stratified_summary=str(tmp_path / "expression_stratified_summary.tsv"),
        stratified_xlsx=str(tmp_path / "expression_stratified_summary.xlsx"),
        pan_class_table=str(tmp_path / "expression_by_pan_class.tsv"),
        pan_tissue_table=str(tmp_path / "expression_by_pan_class_tissue.tsv"),
        group_subfamily_table=str(tmp_path / "expression_by_group_subfamily.tsv"),
        overall_pdf=str(tmp_path / "expression_overall.pdf"),
        overall_png=str(tmp_path / "expression_overall.png"),
        pan_class_pdf=str(tmp_path / "expression_pan_class.pdf"),
        pan_class_png=str(tmp_path / "expression_pan_class.png"),
        pan_tissue_pdf=str(tmp_path / "expression_pan_tissue.pdf"),
        pan_tissue_png=str(tmp_path / "expression_pan_tissue.png"),
        group_subfamily_pdf=str(tmp_path / "expression_group_subfamily.pdf"),
        group_subfamily_png=str(tmp_path / "expression_group_subfamily.png"),
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
            sample_metadata=None,
            pan_membership=None,
            pan_classification=None,
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


def test_imported_expression_respects_sample_species_metadata(tmp_path: Path) -> None:
    members = tmp_path / "family_members.tsv"
    members.write_text(
        "stable_id\tspecies_id\tgene_id\tgroup\tsubfamily\n"
        "SpA__Gene1\tSpA\tGene1\tG1\tS1\n"
        "SpB__Gene1\tSpB\tGene1\tG2\tS1\n",
        encoding="utf-8",
    )
    matrix = tmp_path / "expression.tsv"
    matrix.write_text(
        "stable_id\tSpA_CK\tSpB_CK\nSpA__Gene1\t2.5\t\nSpB__Gene1\t\t3.5\n",
        encoding="utf-8",
    )
    metadata = tmp_path / "sample_metadata.tsv"
    metadata.write_text(
        "sample_id\tspecies_id\tcondition\ttissue\tstress_type\treplicate\n"
        "SpA_CK\tSpA\tControl\tRoot\tControl\t1\n"
        "SpB_CK\tSpB\tControl\tLeaf\tControl\t1\n",
        encoding="utf-8",
    )
    output = SimpleNamespace(
        matrix=str(tmp_path / "expression_matrix.tsv"),
        long=str(tmp_path / "expression_long.tsv"),
        summary=str(tmp_path / "expression_summary.tsv"),
        xlsx=str(tmp_path / "expression.xlsx"),
        plot_pdf=str(tmp_path / "expression.pdf"),
        plot_png=str(tmp_path / "expression.png"),
        scaled=str(tmp_path / "expression_scaled.tsv"),
        sample_metadata_audit=str(tmp_path / "sample_metadata_audit.tsv"),
        gene_condition=str(tmp_path / "expression_gene_condition.tsv"),
        stratified_summary=str(tmp_path / "expression_stratified_summary.tsv"),
        stratified_xlsx=str(tmp_path / "expression_stratified_summary.xlsx"),
        pan_class_table=str(tmp_path / "expression_by_pan_class.tsv"),
        pan_tissue_table=str(tmp_path / "expression_by_pan_class_tissue.tsv"),
        group_subfamily_table=str(tmp_path / "expression_by_group_subfamily.tsv"),
        overall_pdf=str(tmp_path / "expression_overall.pdf"),
        overall_png=str(tmp_path / "expression_overall.png"),
        pan_class_pdf=str(tmp_path / "expression_pan_class.pdf"),
        pan_class_png=str(tmp_path / "expression_pan_class.png"),
        pan_tissue_pdf=str(tmp_path / "expression_pan_tissue.pdf"),
        pan_tissue_png=str(tmp_path / "expression_pan_tissue.png"),
        group_subfamily_pdf=str(tmp_path / "expression_group_subfamily.pdf"),
        group_subfamily_png=str(tmp_path / "expression_group_subfamily.png"),
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
            sample_metadata=str(metadata),
            pan_membership=None,
            pan_classification=None,
        ),
    )

    runpy.run_path(str(SCRIPT_DIR / "import_expression.py"), init_globals={"snakemake": fake})

    wide = pd.read_csv(output.matrix, sep="\t").set_index("stable_id")
    assert set(wide["expression_data_status"]) == {"AVAILABLE"}
    long = pd.read_csv(output.long, sep="\t").set_index(["stable_id", "sample_id"])
    assert long.loc[("SpA__Gene1", "SpA_CK"), "measurement_status"] == "OBSERVED"
    assert long.loc[("SpA__Gene1", "SpB_CK"), "measurement_status"] == "NOT_APPLICABLE"
    assert long.loc[("SpB__Gene1", "SpA_CK"), "measurement_status"] == "NOT_APPLICABLE"
    assert long.loc[("SpB__Gene1", "SpB_CK"), "measurement_status"] == "OBSERVED"
    assert pd.isna(long.loc[("SpA__Gene1", "SpB_CK"), "detected"])
    metadata_audit = pd.read_csv(output.sample_metadata_audit, sep="\t")
    assert set(metadata_audit["metadata_status"]) == {"PASS"}


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
        "distributions",
        "distribution_qc",
        "xlsx",
        "class_plot_pdf",
        "class_plot_png",
        "top_plot_pdf",
        "top_plot_png",
        "species_subfamily_plot_pdf",
        "species_subfamily_plot_png",
        "subfamily_plot_pdf",
        "subfamily_plot_png",
        "species_plot_pdf",
        "species_plot_png",
        "group_plot_pdf",
        "group_plot_png",
    ):
        assert f"snakemake.output.{key}" in script
        assert f"{key}=" in rule
    assert "separator=SEPARATOR" in rule
    assert "promoter_elements_per_gene.tsv" in rule


def test_gene_structure_and_duplication_rules_declare_statistical_outputs() -> None:
    gene_rule = (SCRIPT_DIR.parent / "rules" / "gene_structure.smk").read_text(encoding="utf-8")
    gene_script = (SCRIPT_DIR / "extract_gene_structure.py").read_text(encoding="utf-8")
    duplication_rule = (SCRIPT_DIR.parent / "rules" / "duplication.smk").read_text(encoding="utf-8")
    duplication_script = (SCRIPT_DIR / "run_duplication.py").read_text(encoding="utf-8")

    for key in (
        "global_tests",
        "pairwise_tests",
        "statistics_qc",
        "comparison_plot_pdf",
        "comparison_plot_png",
        "subfamily_source",
        "group_source",
        "fig07_pdf",
        "fig07_png",
        "fig08_pdf",
        "fig08_png",
    ):
        assert f"{key}=" in gene_rule
        assert f"snakemake.output.{key}" in gene_script
    for key in (
        "structure_global_tests",
        "structure_pairwise_tests",
        "structure_statistics_qc",
        "structure_plot_pdf",
        "structure_plot_png",
    ):
        assert f"{key}=" in duplication_rule
        assert f"snakemake.output.{key}" in duplication_script
    assert 'gene_structure=MODULE_TARGETS["gene_structure"]' in duplication_rule


def test_template_stratified_outputs_are_declared_by_rules_and_scripts() -> None:
    rules_dir = SCRIPT_DIR.parent / "rules"
    contracts = {
        "family": (
            "family_distribution.tsv",
            "family_distribution.pdf",
        ),
        "pan_family": (
            "pan_family_class_summary.tsv",
            "pan_family_species_class_summary.tsv",
            "pan_family_subfamily_class_summary.tsv",
            "pan_family_class_dual_denominator.pdf",
        ),
        "duplication": (
            "duplication_stratified_summary.tsv",
            "duplication_stratified_distributions.pdf",
        ),
        "kaks": (
            "kaks_stratified_summary.tsv",
            "kaks_stratified_distributions.pdf",
        ),
        "promoter": ("promoter_group_subfamily_zscore_heatmap.pdf",),
    }
    script_names = {
        "family": "combine_family_evidence.py",
        "pan_family": "parse_pan_family.py",
        "duplication": "run_duplication.py",
        "kaks": "run_kaks.py",
        "promoter": "parse_promoter_elements.py",
    }
    for module, expected_paths in contracts.items():
        rule = (rules_dir / f"{module}.smk").read_text(encoding="utf-8")
        script = (SCRIPT_DIR / script_names[module]).read_text(encoding="utf-8")
        for expected_path in expected_paths:
            assert expected_path in rule
        assert "stratified_summary_utils" in script or module == "promoter"
    assert "GROUP_SUBFAMILY" in (SCRIPT_DIR / "parse_promoter_elements.py").read_text(
        encoding="utf-8"
    )


def test_pan_family_rule_declares_fig10_to_fig13_canonical_contracts() -> None:
    rule = (SCRIPT_DIR.parent / "rules" / "pan_family.smk").read_text(encoding="utf-8")
    script = (SCRIPT_DIR / "parse_pan_family.py").read_text(encoding="utf-8")
    for key in (
        "hog_gene_counts",
        "fig10_pdf",
        "fig10_png",
        "fig11_pdf",
        "fig11_png",
        "fig12_pdf",
        "fig12_png",
        "fig13_pdf",
        "fig13_png",
    ):
        assert f"{key}=" in rule
        assert f"snakemake.output.{key}" in script


def test_complete_chromosome_rule_declares_fig15_annotation_contract() -> None:
    snakefile = (SCRIPT_DIR.parent / "Snakefile").read_text(encoding="utf-8")
    rule = (SCRIPT_DIR.parent / "rules" / "chromosome.smk").read_text(encoding="utf-8")
    script = (SCRIPT_DIR / "plot_chromosome_panclass.py").read_text(encoding="utf-8")
    assert "COMPLETE_CHROMOSOME_TARGETS" in snakefile
    for expected in (
        "chromosome_distribution_annotated.tsv",
        "Fig15_chromosome_panclass_subfamily.pdf",
        "Fig15_chromosome_panclass_subfamily.png",
    ):
        assert expected in rule
    assert "ANNOTATION_OCCUPANCY_NOT_VALIDATED_GENE_LOSS" in script


def test_promoter_rule_declares_fig23_to_fig28_source_contracts() -> None:
    rule = (SCRIPT_DIR.parent / "rules" / "promoter.smk").read_text(encoding="utf-8")
    script = (SCRIPT_DIR / "parse_promoter_elements.py").read_text(encoding="utf-8")
    for key in (
        "major_class_source",
        "subclass_source",
        "subfamily_heatmap_source",
        "group_subfamily_heatmap_source",
        "species_heatmap_source",
        "representative_gene_source",
        "fig23_pdf",
        "fig24_pdf",
        "fig25_pdf",
        "fig26_pdf",
        "fig27_pdf",
        "fig28_pdf",
    ):
        assert f"{key}=" in rule
        assert f"snakemake.output.{key}" in script
    assert "DISPLAY_FILTER_NOT_IMPORTANCE_RANKING" in script


def test_duplication_rule_declares_fig16_and_fig18_to_fig20_contracts() -> None:
    rule = (SCRIPT_DIR.parent / "rules" / "duplication.smk").read_text(encoding="utf-8")
    script = (SCRIPT_DIR / "run_duplication.py").read_text(encoding="utf-8")
    for key in (
        "overall_summary",
        "fig16_pdf",
        "fig16_png",
        "fig18_pdf",
        "fig18_png",
        "fig19_pdf",
        "fig19_png",
        "fig20_pdf",
        "fig20_png",
    ):
        assert f"{key}=" in rule
        assert f"snakemake.output.{key}" in script
    assert "DESCRIPTIVE_ASSOCIATION_NOT_CAUSAL" in script


def test_kaks_rule_declares_fig04_to_fig06_and_fig14_cluster_contracts() -> None:
    rule = (SCRIPT_DIR.parent / "rules" / "kaks.smk").read_text(encoding="utf-8")
    script = (SCRIPT_DIR / "run_kaks.py").read_text(encoding="utf-8")
    for key in (
        "subfamily_source",
        "group_source",
        "subfamily_group_source",
        "pan_class_source",
        "inference_tests",
        "fig04_pdf",
        "fig05_pdf",
        "fig06_pdf",
        "fig14_pdf",
    ):
        assert f"{key}=" in rule
        assert f"snakemake.output.{key}" in script
    assert "PAIR_CLUSTER_MEDIAN" in script


def test_promoter_distributions_complete_zero_grid_and_auditable_denominators() -> None:
    coordinates = pd.DataFrame(
        {
            "stable_id": ["A1", "A2", "A3", "B1", "B2"],
            "species_id": ["SpA", "SpA", "SpA", "SpB", "SpB"],
            "gene_id": ["A1", "A2", "A3", "B1", "B2"],
            "promoter_length": [1000, 1000, 1000, 1000, 1000],
            "promoter_qc": ["PASS"] * 5,
        }
    )
    members = pd.DataFrame(
        {
            "stable_id": ["A1", "A2", "A3", "B1", "B2"],
            "species_id": ["SpA", "SpA", "SpA", "SpB", "SpB"],
            "gene_id": ["A1", "A2", "A3", "B1", "B2"],
            "subfamily": ["S1", "S2", pd.NA, "S1", "S2"],
            "group": ["G1", "G1", pd.NA, "G2", "G2"],
        }
    )
    elements = pd.DataFrame(
        {
            "stable_id": [
                "A1",
                "A1",
                "A2",
                "A3",
                "B1",
                "B2",
                "B2",
                "A1",
                "A2",
                "A3",
                "B1",
                "B2",
            ],
            "element": [
                "E1",
                "E1",
                "E2",
                "E1",
                "E1",
                "E2",
                "E2",
                "E3",
                "E3",
                "E3",
                "E3",
                "E3",
            ],
        }
    )

    distributions, qc = build_promoter_distributions(elements, coordinates, members)

    assert set(distributions["aggregation_level"]) == {
        "SPECIES_SUBFAMILY",
        "SUBFAMILY",
        "SPECIES",
        "GROUP",
        "GROUP_SUBFAMILY",
    }
    cell = distributions.loc[
        (distributions["aggregation_level"] == "SPECIES_SUBFAMILY")
        & (distributions["species_id"] == "SpA")
        & (distributions["subfamily"] == "S1")
        & (distributions["element"] == "E2")
    ].iloc[0]
    assert cell["motif_hit_count"] == 0
    assert cell["genes_with_hit"] == 0
    assert cell["n_genes"] == 1
    assert cell["total_promoter_bp"] == 1000
    assert cell["hits_per_gene"] == 0.0
    assert cell["hits_per_kb"] == 0.0

    species_a_e1 = distributions.loc[
        (distributions["aggregation_level"] == "SPECIES")
        & (distributions["species_id"] == "SpA")
        & (distributions["element"] == "E1")
    ].iloc[0]
    assert species_a_e1["motif_hit_count"] == 3
    assert species_a_e1["n_genes"] == 3
    assert species_a_e1["hits_per_kb"] == 1.0

    qc_by_level = qc.set_index("aggregation_level")
    assert qc_by_level.loc["SPECIES", "excluded_genes_missing_annotation"] == 0
    assert qc_by_level.loc["SUBFAMILY", "excluded_genes_missing_annotation"] == 1
    assert qc_by_level.loc["GROUP", "excluded_genes_missing_annotation"] == 1
    assert qc_by_level.loc["SPECIES_SUBFAMILY", "excluded_genes_missing_annotation"] == 1
    assert qc_by_level.loc["GROUP_SUBFAMILY", "excluded_genes_missing_annotation"] == 1

    interaction = distributions.loc[
        (distributions["aggregation_level"] == "GROUP_SUBFAMILY")
        & (distributions["group"] == "G1")
        & (distributions["subfamily"] == "S1")
        & (distributions["element"] == "E2")
    ].iloc[0]
    assert interaction["motif_hit_count"] == 0
    assert interaction["n_genes"] == 1


def test_promoter_distribution_zscores_freeze_axis_and_edge_states() -> None:
    coordinates = pd.DataFrame(
        {
            "stable_id": ["A1", "B1"],
            "species_id": ["SpA", "SpB"],
            "gene_id": ["A1", "B1"],
            "promoter_length": [1000, 2000],
            "promoter_qc": ["PASS", "PASS"],
        }
    )
    members = pd.DataFrame(
        {
            "stable_id": ["A1", "B1"],
            "species_id": ["SpA", "SpB"],
            "gene_id": ["A1", "B1"],
            "subfamily": ["S1", "S1"],
            "group": ["Only", "Only"],
        }
    )
    elements = pd.DataFrame(
        {
            "stable_id": ["A1", "A1", "B1", "A1", "B1"],
            "element": ["E1", "E1", "E1", "E2", "E2"],
        }
    )

    distributions, _ = build_promoter_distributions(elements, coordinates, members)
    species_e1 = distributions.loc[
        (distributions["aggregation_level"] == "SPECIES") & (distributions["element"] == "E1")
    ].set_index("species_id")
    assert species_e1.loc["SpA", "zscore_motif_hit_count"] == pytest.approx(1.0)
    assert species_e1.loc["SpB", "zscore_motif_hit_count"] == pytest.approx(-1.0)
    assert set(species_e1["raw_zscore_status"]) == {"PASS"}
    assert species_e1.loc["SpA", "zscore_hits_per_kb"] == pytest.approx(1.0)
    assert species_e1.loc["SpB", "zscore_hits_per_kb"] == pytest.approx(-1.0)
    assert set(species_e1["rate_zscore_status"]) == {"PASS"}
    assert set(species_e1["zscore_axis"]) == {"PER_ELEMENT_ACROSS_CELLS"}
    assert set(species_e1["zscore_ddof"]) == {0}

    species_e2 = distributions.loc[
        (distributions["aggregation_level"] == "SPECIES") & (distributions["element"] == "E2")
    ]
    assert set(species_e2["raw_zscore_status"]) == {"ZERO_VARIANCE"}
    assert set(species_e2["zscore_motif_hit_count"]) == {0.0}
    assert set(species_e2["rate_zscore_status"]) == {"PASS"}

    one_group = distributions.loc[
        (distributions["aggregation_level"] == "GROUP") & (distributions["element"] == "E1")
    ]
    assert set(one_group["raw_zscore_status"]) == {"INSUFFICIENT_CELLS"}
    assert one_group["zscore_motif_hit_count"].isna().all()


def test_promoter_hog_distribution_has_complete_denominators_and_unassigned_state() -> None:
    elements = pd.DataFrame(
        {
            "stable_id": ["A1", "A1", "B1", "C1"],
            "element": ["E1", "E2", "E1", "E2"],
        }
    )
    coordinates = pd.DataFrame(
        {
            "stable_id": ["A1", "B1", "C1"],
            "promoter_length": [1000, 2000, 1000],
        }
    )
    membership = pd.DataFrame(
        {
            "stable_id": ["A1", "B1"],
            "HOG_ID": ["HOG1", "HOG1"],
            "pan_family_class": ["Core", "Core"],
        }
    )

    summary, qc = build_promoter_hog_distributions(elements, coordinates, membership)

    assert set(summary["HOG_ID"]) == {"HOG1", "Unassigned"}
    hog1_e2 = summary.loc[summary["HOG_ID"].eq("HOG1") & summary["element"].eq("E2")].iloc[0]
    assert hog1_e2["motif_hit_count"] == 1
    assert hog1_e2["n_genes"] == 2
    assert hog1_e2["total_promoter_bp"] == 3000
    assert hog1_e2["hits_per_kb"] == pytest.approx(1 / 3)
    assert qc.loc[0, "unassigned_genes"] == 1
    assert qc.loc[0, "qc_status"] == "PASS_WITH_UNASSIGNED_HOG"


def test_promoter_rule_declares_and_joins_pan_family_classification() -> None:
    rule = (SCRIPT_DIR.parent / "rules" / "promoter.smk").read_text(encoding="utf-8")
    script = (SCRIPT_DIR / "parse_promoter_elements.py").read_text(encoding="utf-8")

    assert "pan_classification=" in rule
    assert "snakemake.input.pan_classification" in script
    assert "attach_pan_family_class" in script
