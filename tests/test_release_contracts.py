from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from panfamflow.config import WorkflowConfig
from panfamflow.workflow.scripts.artifact_contract import DeliverableStatus

ROOT = Path(__file__).parents[1]


def test_only_direct_snakemake_scripts_avoid_future_annotations() -> None:
    """Snakemake injects a preamble before direct ``script:`` files.

    Helper modules are imported normally and may safely use ``__future__``.
    Keep this gate scoped to files that Snakemake executes directly so that
    ordinary typed helper modules are not rejected by CI.
    """

    rules = ROOT / "src" / "panfamflow" / "workflow" / "rules"
    direct_script_names: set[str] = set()
    pattern = re.compile(r'script:\s*\n\s*"\.\./scripts/([^"\n]+)"')
    for rule_file in rules.glob("*.smk"):
        direct_script_names.update(pattern.findall(rule_file.read_text(encoding="utf-8")))

    assert direct_script_names
    for script_name in sorted(direct_script_names):
        script = ROOT / "src" / "panfamflow" / "workflow" / "scripts" / script_name
        assert script.is_file(), script_name
        assert "from __future__ import annotations" not in script.read_text(encoding="utf-8")


def test_exported_config_schema_matches_runtime_model() -> None:
    exported = json.loads((ROOT / "schemas" / "panfamflow-config.schema.json").read_text())
    assert exported == WorkflowConfig.model_json_schema()


def test_implementation_order_lists_every_approved_batch_once() -> None:
    table = pd.read_csv(ROOT / "docs" / "IMPLEMENTATION_ORDER.tsv", sep="\t", dtype=str)
    expected = [
        "B0",
        "B1",
        "B2",
        "B3",
        "B4A",
        "B4B",
        "B4C",
        "B4D",
        "B5",
        "B6",
        "B7",
        "B8",
        "B9",
        "B10",
    ]
    assert table["batch_id"].tolist() == expected
    assert table["batch_id"].is_unique
    assert table["depends_on"].notna().all()
    assert set(table["status"]).issubset({"PENDING", "IN_PROGRESS", "PASS", "BLOCKED"})


def test_dependency_freeze_covers_required_tools_without_floating_heads() -> None:
    table = pd.read_csv(ROOT / "docs" / "DEPENDENCY_FREEZE.tsv", sep="\t", dtype=str).fillna("")
    required = {
        "snakemake",
        "python",
        "r-base",
        "deseq2",
        "subread",
        "fastp",
        "hisat2",
        "mafft",
        "clipkit",
        "iqtree",
        "hmmer",
        "diamond",
        "orthofinder",
        "dupgen_finder",
        "pal2nal",
        "kakscalculator2",
        "meme",
        "jcvi",
        "circlize",
        "pandas",
        "openpyxl",
        "matplotlib",
        "scipy",
        "biopython",
    }
    assert required.issubset(set(table["dependency_id"]))
    assert (
        not table["requested_version"].str.lower().isin({"latest", "main", "master", "head"}).any()
    )
    assert (table["verification_command"].str.len() > 0).all()
    assert (table["runtime_boundary"].str.len() > 0).all()


def test_heavy_optional_paths_have_separate_linux_runtime_environments() -> None:
    environments = ROOT / "src" / "panfamflow" / "workflow" / "envs"
    synteny = (environments / "synteny.yaml").read_text(encoding="utf-8")
    expression_de = (environments / "expression_de.yaml").read_text(encoding="utf-8")

    assert "jcvi=1.6.6" in synteny
    assert "diamond" in synteny
    assert "r-base" not in synteny
    assert "subread=2.1.1" in expression_de
    assert "featurecounts" not in synteny.lower()
    assert "deseq2" not in expression_de.lower()


def test_phylogeny_environment_pins_independently_verified_native_tools() -> None:
    environment = (ROOT / "src" / "panfamflow" / "workflow" / "envs" / "phylogeny.yaml").read_text(
        encoding="utf-8"
    )
    assert "mafft>=7.5,<8" in environment
    assert "clipkit=2.13.2" in environment
    assert "iqtree=3.1.3" in environment
    assert "matplotlib-base>=3.9,<4" in environment


def test_statistical_rule_environments_contain_runtime_statistics_dependency() -> None:
    environment_root = ROOT / "src" / "panfamflow" / "workflow" / "envs"
    for environment_name in ("analysis.yaml", "duplication.yaml", "kaks.yaml"):
        environment = (environment_root / environment_name).read_text(encoding="utf-8")
        assert "scipy>=1.15,<1.18" in environment


def test_dupgen_installer_uses_a_full_immutable_source_commit() -> None:
    installer = (ROOT / "scripts" / "install_dupgen.sh").read_text(encoding="utf-8")
    assert "54b950216efe7700f84395d03565cf75cd745e14" in installer
    assert "checkout --detach" in installer
    assert "rev-parse HEAD" in installer


def test_r_runtime_recipes_pin_base_digest_and_package_versions() -> None:
    for relative, package, version in (
        ("containers/expression-de/Dockerfile", "DESeq2", "1.52.0"),
        ("containers/synteny-render/Dockerfile", "circlize", "0.4.18"),
    ):
        recipe = (ROOT / relative).read_text(encoding="utf-8")
        assert "FROM bioconductor/bioconductor_docker:RELEASE_3_23@sha256:" in recipe
        assert package in recipe
        assert version in recipe
        assert ":latest" not in recipe


def test_expression_container_publication_uses_scoped_registry_permissions() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish-expression-container.yml").read_text(
        encoding="utf-8"
    )
    assert "packages: write" in workflow
    assert "contents: read" in workflow
    assert "ghcr.io/lianglunping/panfamflow-expression-de" in workflow
    assert "platforms: linux/amd64" in workflow
    assert "provenance: false" in workflow
    assert "password: ${{ secrets.GITHUB_TOKEN }}" in workflow


def test_linux_explicit_locks_cover_every_environment_with_sha256_urls() -> None:
    environments = {
        path.stem for path in (ROOT / "src" / "panfamflow" / "workflow" / "envs").glob("*.yaml")
    }
    locks = ROOT / "env-locks" / "linux-64"
    locked = {path.name.removesuffix(".explicit.txt") for path in locks.glob("*.explicit.txt")}
    assert locked == environments | {"engine"}
    for lock in locks.glob("*.explicit.txt"):
        lines = lock.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "@EXPLICIT"
        assert len(lines) > 1
        assert all(
            line.startswith("https://")
            and ("/linux-64/" in line or "/noarch/" in line)
            and len(line.rsplit("#", 1)[-1]) == 64
            for line in lines[1:]
        )


def test_engine_environment_and_verification_cover_the_cli_runtime() -> None:
    environment = (ROOT / "environment.yaml").read_text(encoding="utf-8")
    for dependency in ("openpyxl", "pandas", "pydantic", "pyyaml", "rich", "typer"):
        assert dependency in environment

    verification = (ROOT / "scripts" / "hpc" / "verify_linux_lock.jh").read_text(encoding="utf-8")
    assert 'PYTHONPATH="$JH_SUB_CWD/src"' in verification
    assert 'python" -m panfamflow --help' in verification


def test_derived_r_image_lock_records_verified_amd64_content_ids() -> None:
    locks = pd.read_csv(ROOT / "containers" / "IMAGE_LOCKS.tsv", sep="\t", dtype=str)
    assert set(locks["runtime_id"]) == {"expression_de_container", "synteny_render_container"}
    assert set(locks["platform"]) == {"linux/amd64"}
    assert set(locks["verification_status"]) == {"PASS"}
    assert locks["base_image_digest"].str.match(r"^sha256:[0-9a-f]{64}$").all()
    assert locks["derived_image_id"].str.match(r"^sha256:[0-9a-f]{64}$").all()
    assert locks["recipe_sha256"].str.match(r"^[0-9a-f]{64}$").all()


def test_machine_readable_config_field_table_records_safe_defaults() -> None:
    table = pd.read_csv(ROOT / "docs" / "schemas" / "config_fields.tsv", sep="\t", dtype=str)
    defaults = dict(zip(table["field"], table["default"], strict=True))
    assert defaults["deliverables.profile"] == "legacy"
    assert defaults["synteny.enabled"] == "false"
    assert defaults["differential_expression.enabled"] == "false"
    assert defaults["comparative_panel.include_in_pan_denominator"] == "false"


def test_figure_contract_has_exactly_fig01_through_fig34() -> None:
    table = pd.read_csv(ROOT / "docs" / "FIGURE_CONTRACT.tsv", sep="\t", dtype=str)
    assert table["figure_id"].tolist() == [f"Fig{index:02d}" for index in range(1, 35)]
    assert table["figure_id"].is_unique
    assert table["stem"].is_unique
    assert table["source_table"].str.len().gt(0).all()
    assert table["tutorial_anchor"].str.match(r"^fig\d{2}$").all()


def test_logo_and_expression_rules_declare_canonical_figure_contract_outputs() -> None:
    rules = ROOT / "src" / "panfamflow" / "workflow" / "rules"
    family_rule = (rules / "family.smk").read_text(encoding="utf-8")
    expression_rule = (rules / "expression.smk").read_text(encoding="utf-8")

    for expected in (
        "family_domain_segments.tsv",
        "Fig09_core_domain_logo.pdf",
        "Fig09_core_domain_logo.png",
    ):
        assert expected in family_rule
    for expected in (
        "expression_by_pan_class.tsv",
        "expression_by_pan_class_tissue.tsv",
        "expression_by_group_subfamily.tsv",
        "expression_scaled.tsv",
        "Fig29_all_family_expression_distribution.pdf",
        "Fig30_expression_by_pan_class.pdf",
        "Fig31_expression_by_pan_class_tissue.pdf",
        "Fig32_expression_by_group_subfamily.pdf",
        "Fig33_all_family_expression_heatmap.pdf",
    ):
        assert expected in expression_rule


def test_family_and_phylogeny_rules_declare_fig01_fig02_source_contracts() -> None:
    rules = ROOT / "src" / "panfamflow" / "workflow" / "rules"
    family_rule = (rules / "family.smk").read_text(encoding="utf-8")
    phylogeny_rule = (rules / "phylogeny.smk").read_text(encoding="utf-8")
    for expected in (
        "family_copy_number_by_species_subfamily.tsv",
        "Fig02_subfamily_copy_number.pdf",
        "Fig02_subfamily_copy_number.png",
    ):
        assert expected in family_rule
    for expected in (
        "family_tree_tip_annotations.tsv",
        "Fig01_all_family_tree.pdf",
        "Fig01_all_family_tree.png",
    ):
        assert expected in phylogeny_rule


def test_comparative_phylogeny_declares_fig03_and_provenance_contracts() -> None:
    root = ROOT / "src" / "panfamflow" / "workflow"
    snakefile = (root / "Snakefile").read_text(encoding="utf-8")
    phylogeny_rule = (root / "rules" / "phylogeny.smk").read_text(encoding="utf-8")
    for expected in (
        "comparative_panel_selection.tsv",
        "external_sequence_provenance.tsv",
        "comparative_tree_tip_annotations.tsv",
        "Fig03_representative_external_tree.pdf",
        "Fig03_representative_external_tree.png",
    ):
        assert expected in phylogeny_rule
    assert "COMPARATIVE_PHYLOGENY_TARGETS" in snakefile


def test_qc_enum_contract_matches_runtime_enum() -> None:
    table = pd.read_csv(ROOT / "docs" / "schemas" / "qc_enums.tsv", sep="\t", dtype=str)
    deliverable_rows = table.loc[table["enum_name"] == "DeliverableStatus", "value"]
    assert set(deliverable_rows) == {status.value for status in DeliverableStatus}


def test_requirement_traceability_has_exactly_34_figures_and_27_markdown_gates() -> None:
    table = pd.read_csv(ROOT / "docs" / "REQUIREMENT_TRACEABILITY.tsv", sep="\t", dtype=str)
    expected = [f"Fig{index:02d}" for index in range(1, 35)] + [
        f"MD{index:02d}" for index in range(1, 28)
    ]
    assert table["requirement_id"].tolist() == expected
    assert table["requirement_id"].is_unique
    assert len(table) == 61
    assert set(table.loc[table["requirement_id"].str.startswith("Fig"), "requirement_type"]) == {
        "PDF_FIGURE"
    }
    assert set(table.loc[table["requirement_id"].str.startswith("MD"), "requirement_type"]) == {
        "MARKDOWN_ACCEPTANCE"
    }
    for column in ("implementation", "test", "tutorial_anchor", "artifact", "status_basis"):
        assert table[column].fillna("").str.len().gt(0).all(), column


def test_output_schema_and_report_rule_declare_complete_manifest_bundle() -> None:
    schema = pd.read_csv(ROOT / "docs" / "schemas" / "output_tables.tsv", sep="\t", dtype=str)
    required_tables = {
        "promoter_by_hog",
        "synteny_anchors",
        "synteny_blocks",
        "deseq2_contrast_results",
        "figure_manifest",
        "table_manifest",
        "requirement_traceability",
        "result_manifest",
    }
    assert required_tables.issubset(set(schema["table_id"]))
    assert schema["table_id"].is_unique
    report_rule = (ROOT / "src" / "panfamflow" / "workflow" / "rules" / "report.smk").read_text(
        encoding="utf-8"
    )
    for artifact in (
        "result_manifest.tsv",
        "result_manifest.xlsx",
        "figure_manifest.tsv",
        "figure_manifest.xlsx",
        "table_manifest.tsv",
        "table_manifest.xlsx",
        "requirement_traceability.tsv",
        "requirement_traceability.xlsx",
        "software_versions.tsv",
        "software_versions.xlsx",
        "provenance.json",
        "session_info.txt",
    ):
        assert artifact in report_rule


def test_formal_table_companions_are_explicit_dag_targets() -> None:
    snakefile = (ROOT / "src" / "panfamflow" / "workflow" / "Snakefile").read_text(encoding="utf-8")
    report_rule = (ROOT / "src" / "panfamflow" / "workflow" / "rules" / "report.smk").read_text(
        encoding="utf-8"
    )
    assert "FORMAL_TABLE_COMPANION_TARGETS" in snakefile
    assert "FORMAL_TABLE_COMPANION_STEMS" in snakefile
    assert "rule formal_table_xlsx_companion:" in report_rule
    assert "tsv_to_xlsx.py" in report_rule
