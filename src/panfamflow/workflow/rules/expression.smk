EXPRESSION_MODE = config["expression"].get("mode", "imported_matrix")
EXPRESSION_MATRIX = config["inputs"].get("expression_matrix") or join_path(
    WORK, "11_expression", "UNCONFIGURED_EXPRESSION_MATRIX.tsv"
)
EXPRESSION_OUTPUTS = {
    "matrix": MODULE_TARGETS["expression"],
    "long": join_path(RESULTS, "11_expression", "expression_long.tsv"),
    "summary": join_path(RESULTS, "11_expression", "expression_summary.tsv"),
    "xlsx": join_path(RESULTS, "11_expression", "expression.xlsx"),
    "plot_pdf": join_path(RESULTS, "11_expression", "Fig33_all_family_expression_heatmap.pdf"),
    "plot_png": join_path(RESULTS, "11_expression", "Fig33_all_family_expression_heatmap.png"),
    "scaled": join_path(RESULTS, "11_expression", "expression_scaled.tsv"),
    "sample_metadata_audit": join_path(RESULTS, "11_expression", "sample_metadata_audit.tsv"),
    "gene_condition": join_path(RESULTS, "11_expression", "expression_gene_condition.tsv"),
    "stratified_summary": join_path(RESULTS, "11_expression", "expression_stratified_summary.tsv"),
    "stratified_xlsx": join_path(RESULTS, "11_expression", "expression_stratified_summary.xlsx"),
    "pan_class_table": join_path(RESULTS, "11_expression", "expression_by_pan_class.tsv"),
    "pan_tissue_table": join_path(RESULTS, "11_expression", "expression_by_pan_class_tissue.tsv"),
    "group_subfamily_table": join_path(RESULTS, "11_expression", "expression_by_group_subfamily.tsv"),
    "overall_pdf": join_path(RESULTS, "11_expression", "Fig29_all_family_expression_distribution.pdf"),
    "overall_png": join_path(RESULTS, "11_expression", "Fig29_all_family_expression_distribution.png"),
    "pan_class_pdf": join_path(RESULTS, "11_expression", "Fig30_expression_by_pan_class.pdf"),
    "pan_class_png": join_path(RESULTS, "11_expression", "Fig30_expression_by_pan_class.png"),
    "pan_tissue_pdf": join_path(RESULTS, "11_expression", "Fig31_expression_by_pan_class_tissue.pdf"),
    "pan_tissue_png": join_path(RESULTS, "11_expression", "Fig31_expression_by_pan_class_tissue.png"),
    "group_subfamily_pdf": join_path(RESULTS, "11_expression", "Fig32_expression_by_group_subfamily.pdf"),
    "group_subfamily_png": join_path(RESULTS, "11_expression", "Fig32_expression_by_group_subfamily.png"),
}

EXPRESSION_SAMPLE_METADATA = config["inputs"].get("sample_metadata")
EXPRESSION_PAN_MEMBERSHIP = (
    join_path(RESULTS, "06_pan_family", "family_hog_membership.tsv")
    if "pan_family" in SELECTED_MODULES
    else None
)
EXPRESSION_PAN_CLASSIFICATION = (
    MODULE_TARGETS["pan_family"] if "pan_family" in SELECTED_MODULES else None
)
EXPRESSION_CONTEXT_INPUTS = [
    path
    for path in (
        EXPRESSION_SAMPLE_METADATA,
        EXPRESSION_PAN_MEMBERSHIP,
        EXPRESSION_PAN_CLASSIFICATION,
    )
    if path
]

if EXPRESSION_MODE == "imported_matrix":
    rule expression_import:
        input:
            members=MODULE_TARGETS["family"],
            matrix=EXPRESSION_MATRIX,
            context=EXPRESSION_CONTEXT_INPUTS,
        output:
            matrix=EXPRESSION_OUTPUTS["matrix"],
            long=EXPRESSION_OUTPUTS["long"],
            summary=EXPRESSION_OUTPUTS["summary"],
            xlsx=EXPRESSION_OUTPUTS["xlsx"],
            plot_pdf=EXPRESSION_OUTPUTS["plot_pdf"],
            plot_png=EXPRESSION_OUTPUTS["plot_png"],
            scaled=EXPRESSION_OUTPUTS["scaled"],
            sample_metadata_audit=EXPRESSION_OUTPUTS["sample_metadata_audit"],
            gene_condition=EXPRESSION_OUTPUTS["gene_condition"],
            stratified_summary=EXPRESSION_OUTPUTS["stratified_summary"],
            stratified_xlsx=EXPRESSION_OUTPUTS["stratified_xlsx"],
            pan_class_table=EXPRESSION_OUTPUTS["pan_class_table"],
            pan_tissue_table=EXPRESSION_OUTPUTS["pan_tissue_table"],
            group_subfamily_table=EXPRESSION_OUTPUTS["group_subfamily_table"],
            overall_pdf=EXPRESSION_OUTPUTS["overall_pdf"],
            overall_png=EXPRESSION_OUTPUTS["overall_png"],
            pan_class_pdf=EXPRESSION_OUTPUTS["pan_class_pdf"],
            pan_class_png=EXPRESSION_OUTPUTS["pan_class_png"],
            pan_tissue_pdf=EXPRESSION_OUTPUTS["pan_tissue_pdf"],
            pan_tissue_png=EXPRESSION_OUTPUTS["pan_tissue_png"],
            group_subfamily_pdf=EXPRESSION_OUTPUTS["group_subfamily_pdf"],
            group_subfamily_png=EXPRESSION_OUTPUTS["group_subfamily_png"],
        params:
            separator=SEPARATOR,
            min_tpm_detected=config["expression"].get("min_tpm_detected", 1.0),
            heatmap_transform=config["expression"].get("heatmap_transform", "log2_tpm1_zscore"),
            png_dpi=PNG_DPI,
            sample_metadata=EXPRESSION_SAMPLE_METADATA,
            pan_membership=EXPRESSION_PAN_MEMBERSHIP,
            pan_classification=EXPRESSION_PAN_CLASSIFICATION,
        conda:
            "../envs/expression.yaml"
        script:
            "../scripts/import_expression.py"
else:
    rule fastp_reads:
        input:
            r1=lambda wildcards: sample_field(wildcards, "r1"),
            r2=lambda wildcards: SAMPLE_BY_ID[wildcards.sample].get("r2") or sample_field(wildcards, "r1"),
        output:
            r1=join_path(WORK, "11_expression", "fastp", "{sample}.R1.clean.fastq.gz"),
            r2=join_path(WORK, "11_expression", "fastp", "{sample}.R2.clean.fastq.gz"),
            json=join_path(RESULTS, "11_expression", "fastp", "{sample}.json"),
            html=join_path(RESULTS, "11_expression", "fastp", "{sample}.html"),
        params:
            paired=lambda wildcards: bool(SAMPLE_BY_ID[wildcards.sample].get("r2")),
            extra_args=config["expression"].get("fastp_extra_args", []),
        threads:
            min(8, int(RUN.get("cores", 16)))
        log:
            stdout=join_path(LOGS, "11_expression", "fastp", "{sample}.stdout.log"),
            stderr=join_path(LOGS, "11_expression", "fastp", "{sample}.stderr.log"),
        conda:
            "../envs/expression.yaml"
        script:
            "../scripts/run_fastp.py"

    rule hisat2_index:
        input:
            genome=lambda wildcards: species_field(wildcards, "genome")
        output:
            done=join_path(WORK, "11_expression", "hisat2_index", "{species}", "index.done")
        params:
            prefix=lambda wildcards: join_path(WORK, "11_expression", "hisat2_index", wildcards.species, "genome")
        threads:
            min(16, int(RUN.get("cores", 16)))
        log:
            join_path(LOGS, "11_expression", "hisat2_index", "{species}.log")
        conda:
            "../envs/expression.yaml"
        shell:
            "mkdir -p $(dirname {params.prefix}) $(dirname {log}); "
            "rm -f {params.prefix}*.ht2 {params.prefix}*.ht2l; "
            "hisat2-build -p {threads} {input.genome} {params.prefix} > {log} 2>&1; touch {output.done}"

    rule align_rnaseq:
        input:
            index=lambda wildcards: join_path(
                WORK,
                "11_expression",
                "hisat2_index",
                SAMPLE_BY_ID[wildcards.sample]["species_id"],
                "index.done",
            ),
            r1=rules.fastp_reads.output.r1,
            r2=rules.fastp_reads.output.r2,
        output:
            bam=join_path(WORK, "11_expression", "alignment", "{sample}.sorted.bam"),
            bai=join_path(WORK, "11_expression", "alignment", "{sample}.sorted.bam.bai"),
        params:
            index_prefix=lambda wildcards: join_path(
                WORK,
                "11_expression",
                "hisat2_index",
                SAMPLE_BY_ID[wildcards.sample]["species_id"],
                "genome",
            ),
            paired=lambda wildcards: bool(SAMPLE_BY_ID[wildcards.sample].get("r2")),
            extra_args=config["expression"].get("hisat2_extra_args", []),
        threads:
            min(16, int(RUN.get("cores", 16)))
        log:
            hisat2=join_path(LOGS, "11_expression", "hisat2", "{sample}.log"),
            samtools=join_path(LOGS, "11_expression", "samtools", "{sample}.log"),
        conda:
            "../envs/expression.yaml"
        script:
            "../scripts/run_hisat2.py"

    rule stringtie_quantify:
        input:
            bam=rules.align_rnaseq.output.bam,
            gff3=lambda wildcards: join_path(
                RESULTS,
                "01_normalized",
                f"{SAMPLE_BY_ID[wildcards.sample]['species_id']}.canonical.gff3",
            ),
        output:
            gtf=join_path(WORK, "11_expression", "stringtie", "{sample}.gtf"),
            abundance=join_path(WORK, "11_expression", "stringtie", "{sample}.abundance.tsv"),
        params:
            strandedness=lambda wildcards: SAMPLE_BY_ID[wildcards.sample].get("strandedness", "unstranded"),
            extra_args=config["expression"].get("stringtie_extra_args", []),
        threads:
            min(8, int(RUN.get("cores", 16)))
        log:
            stdout=join_path(LOGS, "11_expression", "stringtie", "{sample}.stdout.log"),
            stderr=join_path(LOGS, "11_expression", "stringtie", "{sample}.stderr.log"),
        conda:
            "../envs/expression.yaml"
        script:
            "../scripts/run_stringtie.py"

    rule expression_combine_stringtie:
        input:
            members=MODULE_TARGETS["family"],
            maps=NORMALIZED_MAPS,
            abundance=expand(join_path(WORK, "11_expression", "stringtie", "{sample}.abundance.tsv"), sample=SAMPLES),
            context=EXPRESSION_CONTEXT_INPUTS,
        output:
            matrix=EXPRESSION_OUTPUTS["matrix"],
            long=EXPRESSION_OUTPUTS["long"],
            summary=EXPRESSION_OUTPUTS["summary"],
            xlsx=EXPRESSION_OUTPUTS["xlsx"],
            plot_pdf=EXPRESSION_OUTPUTS["plot_pdf"],
            plot_png=EXPRESSION_OUTPUTS["plot_png"],
            scaled=EXPRESSION_OUTPUTS["scaled"],
            sample_metadata_audit=EXPRESSION_OUTPUTS["sample_metadata_audit"],
            gene_condition=EXPRESSION_OUTPUTS["gene_condition"],
            stratified_summary=EXPRESSION_OUTPUTS["stratified_summary"],
            stratified_xlsx=EXPRESSION_OUTPUTS["stratified_xlsx"],
            pan_class_table=EXPRESSION_OUTPUTS["pan_class_table"],
            pan_tissue_table=EXPRESSION_OUTPUTS["pan_tissue_table"],
            group_subfamily_table=EXPRESSION_OUTPUTS["group_subfamily_table"],
            overall_pdf=EXPRESSION_OUTPUTS["overall_pdf"],
            overall_png=EXPRESSION_OUTPUTS["overall_png"],
            pan_class_pdf=EXPRESSION_OUTPUTS["pan_class_pdf"],
            pan_class_png=EXPRESSION_OUTPUTS["pan_class_png"],
            pan_tissue_pdf=EXPRESSION_OUTPUTS["pan_tissue_pdf"],
            pan_tissue_png=EXPRESSION_OUTPUTS["pan_tissue_png"],
            group_subfamily_pdf=EXPRESSION_OUTPUTS["group_subfamily_pdf"],
            group_subfamily_png=EXPRESSION_OUTPUTS["group_subfamily_png"],
        params:
            sample_ids=SAMPLES,
            sample_species_ids=[SAMPLE_BY_ID[sample]["species_id"] for sample in SAMPLES],
            min_tpm_detected=config["expression"].get("min_tpm_detected", 1.0),
            heatmap_transform=config["expression"].get("heatmap_transform", "log2_tpm1_zscore"),
            png_dpi=PNG_DPI,
            sample_metadata=EXPRESSION_SAMPLE_METADATA,
            pan_membership=EXPRESSION_PAN_MEMBERSHIP,
            pan_classification=EXPRESSION_PAN_CLASSIFICATION,
        conda:
            "../envs/expression.yaml"
        script:
            "../scripts/combine_stringtie.py"


if DE_CONFIG.get("enabled", False):
    DE_SOURCE = DE_CONFIG.get("source", "featurecounts")
    # expression_de_container is the immutable R 4.6.1 / DESeq2 1.52.0 runtime.
    EXPRESSION_DE_CONTAINER = DE_CONFIG["container_image"]

    if DE_SOURCE == "featurecounts":
        rule featurecounts_raw_counts:
            input:
                bams=expand(
                    join_path(WORK, "11_expression", "alignment", "{sample}.sorted.bam"),
                    sample=SAMPLES,
                ),
                maps=NORMALIZED_MAPS,
                gff3=NORMALIZED_GFFS,
            output:
                counts=join_path(WORK, "11_expression", "de", "featurecounts_raw_counts.tsv"),
                counts_xlsx=join_path(
                    WORK, "11_expression", "de", "featurecounts_raw_counts.xlsx"
                ),
                provenance=join_path(
                    RESULTS, "11_expression", "featurecounts_provenance.tsv"
                ),
                provenance_xlsx=join_path(
                    RESULTS, "11_expression", "featurecounts_provenance.xlsx"
                ),
            params:
                sample_ids=SAMPLES,
                sample_records=list(SAMPLE_BY_ID.values()),
                species_ids=SPECIES,
                feature_type=DE_CONFIG.get("feature_type", "exon"),
                feature_attribute=DE_CONFIG.get("feature_attribute", "Parent"),
                work_dir=join_path(WORK, "11_expression", "de", "featurecounts"),
            threads:
                min(16, int(RUN.get("cores", 16)))
            conda:
                "../envs/expression_de.yaml"
            script:
                "../scripts/run_featurecounts.py"

        DE_RAW_COUNTS = rules.featurecounts_raw_counts.output.counts
    else:
        DE_RAW_COUNTS = str(DE_CONFIG["counts_table"])


    rule audit_differential_expression_inputs:
        input:
            counts=DE_RAW_COUNTS,
            design=str(DE_CONFIG["design_table"]),
            contrasts=str(DE_CONFIG["contrasts_table"]),
        output:
            counts=join_path(RESULTS, "11_expression", "raw_counts.tsv"),
            counts_xlsx=join_path(RESULTS, "11_expression", "raw_counts.xlsx"),
            design=join_path(RESULTS, "11_expression", "de_design_audit.tsv"),
            design_xlsx=join_path(RESULTS, "11_expression", "de_design_audit.xlsx"),
            contrasts=join_path(RESULTS, "11_expression", "de_contrast_audit.tsv"),
            contrasts_xlsx=join_path(
                RESULTS, "11_expression", "de_contrast_audit.xlsx"
            ),
            datasets=join_path(RESULTS, "11_expression", "expression_dataset_audit.tsv"),
            datasets_xlsx=join_path(
                RESULTS, "11_expression", "expression_dataset_audit.xlsx"
            ),
            sample_qc=join_path(RESULTS, "11_expression", "expression_sample_qc.tsv"),
            sample_qc_xlsx=join_path(
                RESULTS, "11_expression", "expression_sample_qc.xlsx"
            ),
        params:
            min_replicates=DE_CONFIG.get("min_replicates", 2),
        conda:
            "../envs/expression.yaml"
        script:
            "../scripts/audit_expression_datasets.py"


    rule run_deseq2:
        input:
            counts=rules.audit_differential_expression_inputs.output.counts,
            design=rules.audit_differential_expression_inputs.output.design,
            contrasts=rules.audit_differential_expression_inputs.output.contrasts,
        output:
            results=join_path(WORK, "11_expression", "de", "deseq2_all_results.tsv"),
            vst=join_path(WORK, "11_expression", "de", "expression_vst_long.tsv"),
            pca=join_path(WORK, "11_expression", "de", "deseq2_sample_pca.tsv"),
            fit_qc=join_path(WORK, "11_expression", "de", "deseq2_fit_qc.tsv"),
            session=join_path(RESULTS, "11_expression", "deseq2_session_info.txt"),
        params:
            alpha=DE_CONFIG.get("alpha", 0.05),
            min_total_count=DE_CONFIG.get("min_total_count", 10),
        container:
            EXPRESSION_DE_CONTAINER
        script:
            "../scripts/run_deseq2.R"


    rule integrate_differential_expression:
        input:
            results=rules.run_deseq2.output.results,
            vst=rules.run_deseq2.output.vst,
            pca=rules.run_deseq2.output.pca,
            fit_qc=rules.run_deseq2.output.fit_qc,
            session=rules.run_deseq2.output.session,
            design=rules.audit_differential_expression_inputs.output.design,
            contrasts=rules.audit_differential_expression_inputs.output.contrasts,
            members=MODULE_TARGETS["family"],
        output:
            results=join_path(
                RESULTS, "11_expression", "deseq2_contrast_results.tsv"
            ),
            results_xlsx=join_path(
                RESULTS, "11_expression", "deseq2_contrast_results.xlsx"
            ),
            vst=join_path(RESULTS, "11_expression", "expression_vst.tsv"),
            vst_xlsx=join_path(RESULTS, "11_expression", "expression_vst.xlsx"),
            stress_matrix=join_path(
                RESULTS, "11_expression", "stress_expression_matrix.tsv"
            ),
            stress_matrix_xlsx=join_path(
                RESULTS, "11_expression", "stress_expression_matrix.xlsx"
            ),
            deg_membership=join_path(RESULTS, "11_expression", "deg_membership.tsv"),
            deg_membership_xlsx=join_path(
                RESULTS, "11_expression", "deg_membership.xlsx"
            ),
            evidence=join_path(
                RESULTS, "11_expression", "stress_evidence_integration.tsv"
            ),
            evidence_xlsx=join_path(
                RESULTS, "11_expression", "stress_evidence_integration.xlsx"
            ),
            pca=join_path(RESULTS, "11_expression", "deseq2_sample_pca.tsv"),
            pca_xlsx=join_path(RESULTS, "11_expression", "deseq2_sample_pca.xlsx"),
            fit_qc=join_path(RESULTS, "11_expression", "deseq2_fit_qc.tsv"),
            fit_qc_xlsx=join_path(RESULTS, "11_expression", "deseq2_fit_qc.xlsx"),
            qc=join_path(RESULTS, "11_expression", "expression_qc_summary.tsv"),
            qc_xlsx=join_path(RESULTS, "11_expression", "expression_qc_summary.xlsx"),
            fig34_pdf=join_path(
                RESULTS,
                "11_expression",
                "Fig34_stress_expression_and_comparison.pdf",
            ),
            fig34_png=join_path(
                RESULTS,
                "11_expression",
                "Fig34_stress_expression_and_comparison.png",
            ),
        params:
            alpha=DE_CONFIG.get("alpha", 0.05),
            lfc_threshold=DE_CONFIG.get("lfc_threshold", 1.0),
            png_dpi=PNG_DPI,
        conda:
            "../envs/expression.yaml"
        script:
            "../scripts/integrate_expression_evidence.py"
