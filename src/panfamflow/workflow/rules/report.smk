rule audit_id_chain:
    input:
        maps=NORMALIZED_MAPS,
        family=rules.combine_family_evidence.output.members,
        membership=rules.pan_family_classification.output.membership,
    output:
        tsv=ensure(join_path(RESULTS, "00_qc", "id_mapping_audit.tsv"), non_empty=True),
        xlsx=ensure(join_path(RESULTS, "00_qc", "id_mapping_audit.xlsx"), non_empty=True),
    params:
        separator=SEPARATOR,
    conda:
        "../envs/report.yaml"
    script:
        "../scripts/audit_id_chain.py"


rule canonical_transcript_provenance:
    input:
        maps=NORMALIZED_MAPS,
    output:
        tsv=ensure(
            join_path(RESULTS, "01_normalized", "canonical_transcript_provenance.tsv"),
            non_empty=True,
        ),
        xlsx=ensure(
            join_path(RESULTS, "01_normalized", "canonical_transcript_provenance.xlsx"),
            non_empty=True,
        ),
    params:
        backend=CANONICAL_BACKEND,
        method=config.get("canonical_transcript", {}).get("method", "longest_cds"),
        separator=SEPARATOR,
    conda:
        "../envs/report.yaml"
    script:
        "../scripts/build_canonical_transcript_provenance.py"


rule hog_node_provenance:
    input:
        classification=rules.pan_family_classification.output.classification,
        result_dir=rules.orthofinder.output.result_dir,
    output:
        tsv=ensure(join_path(RESULTS, "06_pan_family", "hog_node_provenance.tsv"), non_empty=True),
        xlsx=ensure(
            join_path(RESULTS, "06_pan_family", "hog_node_provenance.xlsx"),
            non_empty=True,
        ),
    conda:
        "../envs/report.yaml"
    script:
        "../scripts/build_hog_node_provenance.py"


TRACEABILITY_PROVENANCE_TARGETS = (
    [
        rules.audit_id_chain.output.tsv,
        rules.audit_id_chain.output.xlsx,
        rules.canonical_transcript_provenance.output.tsv,
        rules.canonical_transcript_provenance.output.xlsx,
        rules.hog_node_provenance.output.tsv,
        rules.hog_node_provenance.output.xlsx,
    ]
    if COMPLETE_PROFILE and {"normalize", "family", "orthology", "pan_family"}.issubset(SELECTED_MODULES)
    else []
)


REPORT_DEPENDENCIES = (
    [MODULE_TARGETS[module] for module in SELECTED_MODULES if module != "report"]
    + COMPARATIVE_PHYLOGENY_TARGETS
    + COMPLETE_CHROMOSOME_TARGETS
    + SYNTENY_TARGETS
    + DE_TARGETS
    + FORMAL_FIGURE_TARGETS
    + FORMAL_SOURCE_TABLE_TARGETS
    + FORMAL_TABLE_COMPANION_TARGETS
    + RECOVERY_AUDIT_TARGETS
    + TRACEABILITY_PROVENANCE_TARGETS
)


if FORMAL_TABLE_COMPANION_STEMS:
    wildcard_constraints:
        formal_table="|".join(re.escape(value) for value in FORMAL_TABLE_COMPANION_STEMS)


    rule formal_table_xlsx_companion:
        input:
            lambda wildcards: join_path(RESULTS, f"{wildcards.formal_table}.tsv")
        output:
            join_path(RESULTS, "{formal_table}.xlsx")
        conda:
            "../envs/report.yaml"
        script:
            "../scripts/tsv_to_xlsx.py"


rule integrated_report:
    input:
        REPORT_DEPENDENCIES
    output:
        index=MODULE_TARGETS["report"],
        master_tsv=join_path(RESULTS, "12_integrated", "master_gene_table.tsv"),
        master_xlsx=join_path(RESULTS, "12_integrated", "master_gene_table.xlsx"),
        manifest=join_path(RESULTS, "report", "result_manifest.tsv"),
        manifest_xlsx=join_path(RESULTS, "report", "result_manifest.xlsx"),
        figure_manifest=join_path(RESULTS, "report", "figure_manifest.tsv"),
        figure_manifest_xlsx=join_path(RESULTS, "report", "figure_manifest.xlsx"),
        table_manifest=join_path(RESULTS, "report", "table_manifest.tsv"),
        table_manifest_xlsx=join_path(RESULTS, "report", "table_manifest.xlsx"),
        traceability=join_path(RESULTS, "report", "requirement_traceability.tsv"),
        traceability_xlsx=join_path(RESULTS, "report", "requirement_traceability.xlsx"),
        software_versions=join_path(RESULTS, "report", "software_versions.tsv"),
        software_versions_xlsx=join_path(RESULTS, "report", "software_versions.xlsx"),
        run_info=join_path(RESULTS, "report", "run_info.json"),
        provenance=join_path(RESULTS, "report", "provenance.json"),
        session=join_path(RESULTS, "report", "session_info.txt"),
    params:
        results_dir=RESULTS,
        project_root=".",
        figure_contract=str(FIGURE_CONTRACT_PATH),
        requirement_traceability=str(
            Path(workflow.basedir).parents[2] / "docs" / "REQUIREMENT_TRACEABILITY.tsv"
        ),
        selected_modules=",".join(SELECTED_MODULES),
        title=config.get("report", {}).get("title"),
    conda:
        "../envs/report.yaml"
    script:
        "../scripts/build_report.py"
