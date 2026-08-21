rule gene_structure_metrics:
    input:
        members=MODULE_TARGETS["family"],
        gff3s=NORMALIZED_GFFS,
        maps=NORMALIZED_MAPS,
    output:
        metrics=MODULE_TARGETS["gene_structure"],
        summary=join_path(RESULTS, "04_gene_structure", "gene_structure_summary.tsv"),
        global_tests=join_path(RESULTS, "04_gene_structure", "gene_structure_global_tests.tsv"),
        pairwise_tests=join_path(RESULTS, "04_gene_structure", "gene_structure_pairwise_tests.tsv"),
        statistics_qc=join_path(RESULTS, "04_gene_structure", "gene_structure_statistics_qc.tsv"),
        subfamily_source=join_path(
            RESULTS, "04_gene_structure", "gene_structure_by_subfamily.tsv"
        ),
        group_source=join_path(RESULTS, "04_gene_structure", "gene_structure_by_group.tsv"),
        xlsx=join_path(RESULTS, "04_gene_structure", "gene_structure.xlsx"),
        comparison_plot_pdf=join_path(RESULTS, "04_gene_structure", "gene_structure_group_comparisons.pdf"),
        comparison_plot_png=join_path(RESULTS, "04_gene_structure", "gene_structure_group_comparisons.png"),
        fig07_pdf=join_path(
            RESULTS, "04_gene_structure", "Fig07_gene_structure_by_subfamily.pdf"
        ),
        fig07_png=join_path(
            RESULTS, "04_gene_structure", "Fig07_gene_structure_by_subfamily.png"
        ),
        fig08_pdf=join_path(RESULTS, "04_gene_structure", "Fig08_gene_structure_by_group.pdf"),
        fig08_png=join_path(RESULTS, "04_gene_structure", "Fig08_gene_structure_by_group.png"),
    params:
        metrics=config.get("gene_structure", {}).get("metrics", [
            "gene_length",
            "protein_length",
            "cds_length",
            "exon_count",
            "intron_count",
            "total_intron_length",
        ]),
        min_group_units=config.get("gene_structure", {}).get("min_group_units", 2),
        alpha=config.get("gene_structure", {}).get("alpha", 0.05),
        seed=SEED,
        png_dpi=PNG_DPI,
    conda:
        "../envs/analysis.yaml"
    script:
        "../scripts/extract_gene_structure.py"
