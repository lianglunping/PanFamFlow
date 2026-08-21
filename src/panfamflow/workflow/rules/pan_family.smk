rule pan_family_classification:
    input:
        result_dir=join_path(RESULTS, "05_orthology", "orthofinder_result_dir.txt"),
        members=join_path(RESULTS, "02_family", "family_members.tsv"),
    output:
        classification=ensure(MODULE_TARGETS["pan_family"], non_empty=True),
        membership=ensure(
            join_path(RESULTS, "06_pan_family", "family_hog_membership.tsv"),
            non_empty=True,
        ),
        presence=ensure(
            join_path(RESULTS, "06_pan_family", "family_presence_absence.tsv"),
            non_empty=True,
        ),
        unassigned_members=ensure(
            join_path(RESULTS, "06_pan_family", "unassigned_family_members.tsv"),
            non_empty=True,
        ),
        rarefaction=ensure(
            join_path(RESULTS, "06_pan_family", "pan_family_rarefaction_iterations.tsv"),
            non_empty=True,
        ),
        rarefaction_summary=ensure(
            join_path(RESULTS, "06_pan_family", "pan_family_rarefaction_summary.tsv"),
            non_empty=True,
        ),
        class_summary=ensure(
            join_path(RESULTS, "06_pan_family", "pan_family_class_summary.tsv"),
            non_empty=True,
        ),
        hog_gene_counts=ensure(
            join_path(RESULTS, "06_pan_family", "pan_family_hog_gene_counts.tsv"),
            non_empty=True,
        ),
        species_class_summary=ensure(
            join_path(RESULTS, "06_pan_family", "pan_family_species_class_summary.tsv"),
            non_empty=True,
        ),
        subfamily_class_summary=ensure(
            join_path(RESULTS, "06_pan_family", "pan_family_subfamily_class_summary.tsv"),
            non_empty=True,
        ),
        xlsx=ensure(
            join_path(RESULTS, "06_pan_family", "pan_family_results.xlsx"),
            non_empty=True,
        ),
        class_plot_pdf=join_path(
            RESULTS, "06_pan_family", "pan_family_classification.pdf"
        ),
        class_plot_png=join_path(
            RESULTS, "06_pan_family", "pan_family_classification.png"
        ),
        dual_denominator_plot_pdf=join_path(
            RESULTS, "06_pan_family", "pan_family_class_dual_denominator.pdf"
        ),
        dual_denominator_plot_png=join_path(
            RESULTS, "06_pan_family", "pan_family_class_dual_denominator.png"
        ),
        species_class_plot_pdf=join_path(
            RESULTS, "06_pan_family", "pan_family_species_class_distribution.pdf"
        ),
        species_class_plot_png=join_path(
            RESULTS, "06_pan_family", "pan_family_species_class_distribution.png"
        ),
        subfamily_class_plot_pdf=join_path(
            RESULTS, "06_pan_family", "pan_family_subfamily_class_distribution.pdf"
        ),
        subfamily_class_plot_png=join_path(
            RESULTS, "06_pan_family", "pan_family_subfamily_class_distribution.png"
        ),
        rarefaction_plot_pdf=join_path(
            RESULTS, "06_pan_family", "pan_family_rarefaction.pdf"
        ),
        rarefaction_plot_png=join_path(
            RESULTS, "06_pan_family", "pan_family_rarefaction.png"
        ),
        fig10_pdf=join_path(
            RESULTS, "06_pan_family", "Fig10_pan_class_dual_denominator.pdf"
        ),
        fig10_png=join_path(
            RESULTS, "06_pan_family", "Fig10_pan_class_dual_denominator.png"
        ),
        fig11_pdf=join_path(RESULTS, "06_pan_family", "Fig11_hog_class_gene_count.pdf"),
        fig11_png=join_path(RESULTS, "06_pan_family", "Fig11_hog_class_gene_count.png"),
        fig12_pdf=join_path(RESULTS, "06_pan_family", "Fig12_species_pan_class_counts.pdf"),
        fig12_png=join_path(RESULTS, "06_pan_family", "Fig12_species_pan_class_counts.png"),
        fig13_pdf=join_path(
            RESULTS, "06_pan_family", "Fig13_species_pan_class_fractions.pdf"
        ),
        fig13_png=join_path(
            RESULTS, "06_pan_family", "Fig13_species_pan_class_fractions.png"
        ),
    params:
        hog_node=config.get("orthofinder", {}).get("hog_node", "auto"),
        species_ids=SPECIES,
        separator=SEPARATOR,
        core_min=float(config.get("pan_family", {}).get("core_min", 0.99)),
        soft_core_min=float(config.get("pan_family", {}).get("soft_core_min", 0.90)),
        shell_min=float(config.get("pan_family", {}).get("shell_min", 0.10)),
        rarefaction_iterations=int(
            config.get("pan_family", {}).get("rarefaction_iterations", 1000)
        ),
        max_exact_combinations=int(
            config.get("pan_family", {}).get("max_exact_combinations", 5000)
        ),
        seed=SEED,
        png_dpi=PNG_DPI,
    conda:
        "../envs/analysis.yaml"
    retries:
        int(RUN.get("retries", 1))
    script:
        "../scripts/parse_pan_family.py"
