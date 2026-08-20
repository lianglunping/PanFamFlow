DUPLICATION_BACKEND = config["duplication"].get("backend", "dupgen_finder_unique")
DUPLICATION_TARGETS = config["duplication"].get("targets") or [
    record["id"] for record in SPECIES_RECORDS if record.get("outgroup")
]
DUPLICATION_OPTIONAL = [config["duplication"].get("precomputed_table")] if config["duplication"].get("precomputed_table") else []


rule duplication_classification:
    input:
        members=MODULE_TARGETS["family"],
        gene_structure=MODULE_TARGETS["gene_structure"],
        pan_membership=join_path(RESULTS, "06_pan_family", "family_hog_membership.tsv"),
        pan_classification=MODULE_TARGETS["pan_family"],
        maps=NORMALIZED_MAPS,
        proteins=NORMALIZED_PROTEINS,
        optional=DUPLICATION_OPTIONAL,
    output:
        modes=MODULE_TARGETS["duplication"],
        pairs=join_path(RESULTS, "08_duplication", "duplication_pairs.tsv"),
        structure_global_tests=join_path(RESULTS, "08_duplication", "duplication_structure_global_tests.tsv"),
        structure_pairwise_tests=join_path(RESULTS, "08_duplication", "duplication_structure_pairwise_tests.tsv"),
        structure_statistics_qc=join_path(RESULTS, "08_duplication", "duplication_structure_statistics_qc.tsv"),
        stratified_summary=join_path(RESULTS, "08_duplication", "duplication_stratified_summary.tsv"),
        xlsx=join_path(RESULTS, "08_duplication", "duplication.xlsx"),
        plot_pdf=join_path(RESULTS, "08_duplication", "duplication_mode_counts.pdf"),
        plot_png=join_path(RESULTS, "08_duplication", "duplication_mode_counts.png"),
        structure_plot_pdf=join_path(RESULTS, "08_duplication", "duplication_structure_comparisons.pdf"),
        structure_plot_png=join_path(RESULTS, "08_duplication", "duplication_structure_comparisons.png"),
        stratified_plot_pdf=join_path(RESULTS, "08_duplication", "duplication_stratified_distributions.pdf"),
        stratified_plot_png=join_path(RESULTS, "08_duplication", "duplication_stratified_distributions.png"),
    params:
        backend=DUPLICATION_BACKEND,
        targets=DUPLICATION_TARGETS,
        species_ids=SPECIES,
        species_records=SPECIES_RECORDS,
        separator=SEPARATOR,
        precomputed_table=config["duplication"].get("precomputed_table"),
        dupgen_executable=config["duplication"].get("dupgen_executable", "DupGen_finder-unique.pl"),
        diamond_evalue=config["duplication"].get("diamond_evalue", 1e-10),
        max_target_seqs=config["duplication"].get("max_target_seqs", 5),
        proximal_max_gene_distance=config["duplication"].get("proximal_max_gene_distance", 10),
        extra_args=config["duplication"].get("extra_args", []),
        work_dir=join_path(WORK, "08_duplication"),
        png_dpi=PNG_DPI,
        statistics_metrics=config.get("gene_structure", {}).get("metrics", [
            "gene_length",
            "protein_length",
            "cds_length",
            "exon_count",
            "intron_count",
            "total_intron_length",
        ]),
        statistics_min_group_units=config.get("gene_structure", {}).get("min_group_units", 2),
        statistics_alpha=config.get("gene_structure", {}).get("alpha", 0.05),
        seed=SEED,
    threads:
        min(32, int(RUN.get("cores", 16)))
    conda:
        "../envs/duplication.yaml"
    script:
        "../scripts/run_duplication.py"
