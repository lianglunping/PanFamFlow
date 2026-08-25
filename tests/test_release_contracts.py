from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from panfamflow.config import DifferentialExpressionSettings, WorkflowConfig
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


def test_hpc_sif_promotion_requires_offline_digest_and_two_dataset_smoke() -> None:
    job = (ROOT / "scripts" / "hpc" / "build_verified_expression_sif.jh").read_text(
        encoding="utf-8"
    )
    smoke = (ROOT / "scripts" / "hpc" / "expression_sif_smoke.Snakefile").read_text(
        encoding="utf-8"
    )
    digest = "57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29"
    assert "#JSUB -q normal" in job
    assert "module load singularity" in job
    assert '"oci-archive://$archive"' in job
    assert "sha256sum --check --strict" in job
    assert "R_version=4.6.1" in job
    assert "DESeq2_version=1.52.0" in job
    assert "as.character(getRversion())" in job
    assert "verified-container-build-resume7-attempt2" in job
    assert "DS_ABIOTIC" in job and "DS_BIOTIC" in job
    assert "attempt2.resume7.verified.oci.tar" in job
    assert "canonical_cache.resume7" in job
    assert f"@sha256:{digest}" in smoke
    assert "run_deseq2.R" in smoke


def test_hpc_oci_reassembly_is_ordered_and_fail_closed() -> None:
    job = (ROOT / "scripts" / "hpc" / "reassemble_verified_oci.jh").read_text(encoding="utf-8")
    assert "#JSUB -q normal" in job
    assert "expected_chunks=27" in job
    assert "expected_bytes=1792461824" in job
    assert "9b0d65a671d0c29f20cda14d9642449a0debc342a4d40856db8c23fb964448fc" in job
    assert "sha256sum --check --strict" in job
    assert 'test ! -e "$archive"' in job
    assert 'cat "$chunk_file" >>"$archive_partial"' in job
    assert 'mv "$archive_partial" "$archive"' in job


def test_hpc_rule_environment_preparation_is_offline_and_scheduler_bound() -> None:
    job = (ROOT / "scripts" / "hpc" / "prepare_locked_rule_envs.jh").read_text(encoding="utf-8")
    installer = (ROOT / "scripts" / "hpc" / "install_locked_rule_envs.py").read_text(
        encoding="utf-8"
    )
    assert "#JSUB -q normal" in job
    assert "expected_packages=729" in job
    assert "sha256sum --check --strict" in job
    assert "install_locked_rule_envs.py" in job
    assert '"--offline"' in installer


def test_public_reference_job_is_scheduler_bound_and_immutable() -> None:
    job = (ROOT / "scripts" / "hpc" / "prepare_public_expression_reference.jh").read_text(
        encoding="utf-8"
    )
    assert "#JSUB -q normal" in job
    assert "hisat2-build" in job
    assert "prepare_public_expression_inputs.py saf" in job
    assert "abe7b2ecd9eb545f106886063c79a7b39a764e4394a36688da4621c3a00158b2" in job
    assert "6082ad6d23fe860001fab6e8954929be8172d1f6d0f5f6eb54e8982841bb4502" in job
    assert "curl" not in job and "wget" not in job


def test_public_expression_environment_is_explicit_locked_and_offline() -> None:
    job = (ROOT / "scripts" / "hpc" / "prepare_public_expression_env.jh").read_text(
        encoding="utf-8"
    )
    assert "#JSUB -q normal" in job
    assert "expression_de.explicit.txt" in job
    assert "--offline" in job
    assert "fastp" in job and "hisat2" in job and "featureCounts" in job
    assert "awk 'NF {print; exit}'" in job
    assert "curl" not in job and "wget" not in job


def test_public_de_subworkflow_uses_audited_counts_and_fixed_digest() -> None:
    snakefile = (ROOT / "scripts" / "hpc" / "public_expression_de.Snakefile").read_text(
        encoding="utf-8"
    )
    digest = "57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29"
    assert "audit_expression_datasets.py" in snakefile
    assert "conda:" not in snakefile
    assert "run_deseq2.R" in snakefile
    assert "min_replicates=3" in snakefile
    assert f"@sha256:{digest}" in snakefile
    assert "deseq2_fit_qc.tsv" in snakefile
    assert "deseq2_session_info.txt" in snakefile


def test_public_factorial_smoke_runs_on_scheduler_with_fixed_seed() -> None:
    job = (ROOT / "scripts" / "hpc" / "run_public_factorial_smoke.jh").read_text(encoding="utf-8")
    assert "#JSUB -q normal" in job
    assert "module load singularity" in job
    assert 'expression_env="$JH_SUB_CWD/work/public-expression-resume7/expression-de-env"' in job
    assert 'PYTHONPATH="$expression_env/lib/python3.12/site-packages' in job
    assert "--software-deployment-method apptainer" in job
    assert "--seed 20260823" in job
    assert "public_expression_de.Snakefile" in job
    assert "design_rank" in job and "design_columns" in job
    assert r"contrast_count\t6" in job


def test_complete_toy_job_preserves_locked_conda_hashes_and_uses_verified_sif() -> None:
    job = (ROOT / "scripts" / "hpc" / "run_toy_complete.jh").read_text(encoding="utf-8")
    activation = (ROOT / "scripts" / "hpc" / "conda_compat" / "bin" / "activate").read_text(
        encoding="utf-8"
    )
    assert "--conda-prefix" not in job
    assert '--conda-base-path "$JH_SUB_CWD/scripts/hpc/conda_compat"' in job
    assert '--apptainer-prefix "$JH_SUB_CWD/.snakemake/singularity"' in job
    assert 'ln -s "$JH_SUB_CWD/.snakemake/conda" "$toy_cache_root/conda"' not in job
    assert "dry_run_toy_complete.py --list-conda-envs" in job
    assert "install_locked_rule_envs.py" in job
    assert '"$mamba_root"' in job
    assert 'find "$toy_cache_root/conda"' in job
    assert 'run_token="${JH_JOB_ID:-${LSB_JOBID:-${JOB_ID:-$$}}}"' in job
    assert "toy-complete-environments.${JH_JOB_ID}" not in job
    assert 'toy_project_root="$JH_SUB_CWD/examples/toy_complete"' in job
    assert '  "$toy_project_root" \\' in job
    assert 'export PATH="${target_prefix}/bin:${PATH}"' in activation
    assert '"${target_prefix}/etc/conda/activate.d/"*.sh' in activation
    assert 'export PATH="$JH_SUB_CWD/scripts/hpc/conda_compat/bin:$engine/bin:$PATH"' in job
    launcher = (ROOT / "scripts" / "hpc" / "conda_compat" / "bin" / "snakemake").read_text(
        encoding="utf-8"
    )
    assert "Conda.instances.clear()" in launcher
    assert "Conda(prefix_path=compatibility_base)" in launcher


def test_no_work_toy_job_requires_unchanged_manifest_and_explicit_no_work_receipt() -> None:
    job = (ROOT / "scripts" / "hpc" / "rerun_toy_complete_no_work.jh").read_text(encoding="utf-8")
    assert "#JSUB -q normal" in job
    assert '--conda-base-path "$JH_SUB_CWD/scripts/hpc/conda_compat"' in job
    assert '--apptainer-prefix "$JH_SUB_CWD/.snakemake/singularity"' in job
    assert "Nothing to be done" in job
    assert "before_manifest_sha256" in job and "after_manifest_sha256" in job
    assert r"NO_WORK_RERUN\tPASS" in job


def test_isolated_recovery_job_checks_three_registered_dependency_closures() -> None:
    job = (ROOT / "scripts" / "hpc" / "verify_toy_isolated_recovery.jh").read_text(encoding="utf-8")
    assert "#JSUB -q normal" in job
    for case_id, target in (
        ("promoter_summary", "promoter_element_distributions.tsv"),
        ("promoter_single_png", "Fig26_promoter_by_group_subfamily.png"),
        ("expression_vst", "expression_vst.tsv"),
    ):
        assert case_id in job
        assert target in job
    assert "parse_promoter_elements,formal_table_xlsx_companion,integrated_report" in job
    assert "integrate_differential_expression,integrated_report" in job
    assert "run_deseq2" in job
    assert "scan_promoters_fimo" in job
    assert "observed_rules" in job
    assert "ISOLATED_RECOVERY" in job


def test_isolated_recovery_job_always_restores_failed_target_with_checksum() -> None:
    job = (ROOT / "scripts" / "hpc" / "verify_toy_isolated_recovery.jh").read_text(encoding="utf-8")

    assert "trap restore_failed_target EXIT" in job
    assert 'backup_sha256=$(sha256sum "$current_backup"' in job
    assert 'restored_sha256=$(sha256sum "$current_target"' in job
    assert 'test "$restored_sha256" = "$backup_sha256"' in job
    assert "trap - EXIT" in job


def test_isolated_recovery_requests_each_missing_child_as_an_explicit_target() -> None:
    job = (ROOT / "scripts" / "hpc" / "verify_toy_isolated_recovery.jh").read_text(encoding="utf-8")
    runner = (ROOT / "scripts" / "hpc" / "run_toy_complete.py").read_text(encoding="utf-8")

    assert '--target "$target_relative"' in job
    assert 'parser.add_argument("--target", action="append", default=[])' in runner
    assert "command.extend(arguments.target)" in runner


def test_public_requantification_jobs_are_scheduler_bound_and_fail_closed() -> None:
    alignment = (ROOT / "scripts" / "hpc" / "run_public_expression_alignment.jh").read_text(
        encoding="utf-8"
    )
    de_job = (ROOT / "scripts" / "hpc" / "run_public_expression_de.jh").read_text(encoding="utf-8")
    assert "#JSUB -q normal" in alignment and "#JSUB -q normal" in de_job
    assert "module load singularity" in de_job
    assert "fastq_verified_receipt.tsv" in alignment
    assert "reference_index_receipt.tsv" in alignment
    assert "run_public_expression_alignment.py" in alignment
    assert "featureCounts" in de_job
    assert "prepare_public_expression_inputs.py counts" in de_job
    assert "public_expression_de.Snakefile" in de_job
    assert 'PYTHONPATH="$expression_env/lib/python3.12/site-packages' in de_job
    assert "--software-deployment-method apptainer" in de_job
    assert "GSE101734" in de_job and "GSE81906" in de_job
    assert "awk 'NF {print; exit}'" in de_job


def test_public_de_validation_repairs_only_provenance_and_preserves_old_receipt() -> None:
    verifier = (ROOT / "scripts" / "hpc" / "verify_public_expression_de_outputs.jh").read_text(
        encoding="utf-8"
    )

    assert "#JSUB -q normal" in verifier
    assert "Program:featureCounts" in verifier
    assert 'test "$featurecounts_version" = "v2.1.1"' in verifier
    assert "pre-repair.$original_session_sha.tsv" in verifier
    assert 'cp -p "$session" "$original_backup"' in verifier
    assert "corrected_session.partial" in verifier
    assert "source_job_id\\t198370" in verifier
    assert 'bin/featureCounts"' not in verifier
    assert "samtools" not in verifier
    assert "snakemake" not in verifier
    assert "Rscript" not in verifier


def test_native_jcvi_acceptance_job_is_isolated_scheduler_bound_and_audited() -> None:
    job = (ROOT / "scripts" / "hpc" / "run_toy_native_jcvi.jh").read_text(encoding="utf-8")

    assert "#JSUB -q normal" in job
    assert "module load anaconda3" in job
    assert "toy-native-jcvi" in job
    assert 'config["synteny"]["backend"] = "jcvi"' in job
    assert 'config["synteny"]["precomputed_blocks"] = None' in job
    assert "SpA_vs_SpB/provenance.json" in job
    assert "JCVI_version=1.6.6" in job
    assert "DIAMOND_version=2.2.5" in job
    assert 'test "$pair_status" = "PASS"' in job
    assert "from panfamflow.config import load_config" in job
    assert "python -m panfamflow validate" not in job
    assert r"NATIVE_JCVI\tPASS" in job


def test_ci_deprecated_repository_check_cannot_match_its_own_literal() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    check = re.search(
        r"! grep -R (?P<options>[^\n]*?)"
        r"'https://github\.com/lianglunping/Wild-rice-Pangenome-Project'"
        r"\s*\\\n\s*(?P<paths>[^\n]+)",
        workflow,
    )
    assert check is not None
    assert "--exclude=ci.yml" in check.group("options").split()
    assert ".github" in check.group("paths").split()


def test_default_expression_runtime_uses_public_immutable_ghcr_digest() -> None:
    expected = (
        "docker://ghcr.io/lianglunping/panfamflow-expression-de@"
        "sha256:57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29"
    )
    assert DifferentialExpressionSettings().container_image == expected
    template = (ROOT / "src" / "panfamflow" / "templates" / "config.yaml").read_text(
        encoding="utf-8"
    )
    toy = (ROOT / "examples" / "toy_complete" / "config.yaml").read_text(encoding="utf-8")
    assert expected in template
    assert expected in toy


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


def test_traceability_validation_uses_frozen_table_contract_and_reuses_outputs() -> None:
    job = (ROOT / "scripts" / "hpc" / "verify_toy_traceability_provenance.jh").read_text(
        encoding="utf-8"
    )

    assert 'figure_contract_path = Path("docs/FIGURE_CONTRACT.tsv")' in job
    assert 'figure_contract["source_table"].nunique()' in job
    assert "len(table_manifest) != expected_table_pairs" in job
    assert "len(table_manifest) < 34" not in job
    assert "preexisting_artifact_count" in job
    assert 'test ! -e "$toy_project_root/$target"' not in job


def test_provenance_immutability_job_binds_inputs_contracts_seed_and_digest() -> None:
    job = (ROOT / "scripts" / "hpc" / "verify_toy_provenance_immutability.jh").read_text(
        encoding="utf-8"
    )

    assert "len(input_audit) != 11" in job
    assert 'provenance["input_manifest_sha256"]' in job
    assert 'provenance["figure_contract_sha256"]' in job
    assert 'provenance["traceability_contract_sha256"]' in job
    assert 'provenance["seed"] != 20260821' in job
    assert 'provenance["selected_modules"] != expected_modules' in job
    assert "ENGINEERING_COMPLETION_IS_NOT_BIOLOGICAL_VALIDATION" in job
    assert "sha256:57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29" in job


def test_public_hpc_scripts_do_not_expose_personal_filesystem_paths() -> None:
    scripts = sorted((ROOT / "scripts" / "hpc").glob("*.jh"))
    assert scripts
    for script in scripts:
        source = script.read_text(encoding="utf-8")
        assert "/public/home/" not in source, script
        assert "/Users/" not in source, script


def test_formal_contract_paths_rebase_to_configured_results_root() -> None:
    snakefile = (ROOT / "src" / "panfamflow" / "workflow" / "Snakefile").read_text(encoding="utf-8")

    assert "def configured_result_path(path):" in snakefile
    assert "configured_result_path(row['stem'])" in snakefile
    assert snakefile.count('configured_result_path(row["source_table"])') == 2


def test_report_dag_tracks_formal_figures_sources_and_recovery_audit_children() -> None:
    snakefile = (ROOT / "src" / "panfamflow" / "workflow" / "Snakefile").read_text(encoding="utf-8")
    report_rule = (ROOT / "src" / "panfamflow" / "workflow" / "rules" / "report.smk").read_text(
        encoding="utf-8"
    )
    assert "FORMAL_FIGURE_TARGETS" in snakefile
    assert "FORMAL_SOURCE_TABLE_TARGETS" in snakefile
    assert "RECOVERY_AUDIT_TARGETS" in snakefile
    assert "promoter_element_distributions.tsv" in snakefile
    assert "expression_vst.tsv" in snakefile
    for target_group in (
        "FORMAL_FIGURE_TARGETS",
        "FORMAL_SOURCE_TABLE_TARGETS",
        "RECOVERY_AUDIT_TARGETS",
    ):
        assert target_group in report_rule
