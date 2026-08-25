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
        overall_summary=join_path(
            RESULTS, "08_duplication", "duplication_mode_overall.tsv"
        ),
        xlsx=join_path(RESULTS, "08_duplication", "duplication.xlsx"),
        plot_pdf=join_path(RESULTS, "08_duplication", "duplication_mode_counts.pdf"),
        plot_png=join_path(RESULTS, "08_duplication", "duplication_mode_counts.png"),
        structure_plot_pdf=join_path(RESULTS, "08_duplication", "duplication_structure_comparisons.pdf"),
        structure_plot_png=join_path(RESULTS, "08_duplication", "duplication_structure_comparisons.png"),
        stratified_plot_pdf=join_path(RESULTS, "08_duplication", "duplication_stratified_distributions.pdf"),
        stratified_plot_png=join_path(RESULTS, "08_duplication", "duplication_stratified_distributions.png"),
        fig16_pdf=join_path(RESULTS, "08_duplication", "Fig16_duplication_overall.pdf"),
        fig16_png=join_path(RESULTS, "08_duplication", "Fig16_duplication_overall.png"),
        fig18_pdf=join_path(RESULTS, "08_duplication", "Fig18_duplication_by_species.pdf"),
        fig18_png=join_path(RESULTS, "08_duplication", "Fig18_duplication_by_species.png"),
        fig19_pdf=join_path(RESULTS, "08_duplication", "Fig19_duplication_by_subfamily.pdf"),
        fig19_png=join_path(RESULTS, "08_duplication", "Fig19_duplication_by_subfamily.png"),
        fig20_pdf=join_path(RESULTS, "08_duplication", "Fig20_duplication_by_pan_class.pdf"),
        fig20_png=join_path(RESULTS, "08_duplication", "Fig20_duplication_by_pan_class.png"),
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


if SYNTENY_CONFIG.get("enabled", False):

    def synteny_pair_record(wildcards):
        return SYNTENY_PAIR_RECORDS[wildcards.pair_id]


    rule synteny_pair:
        input:
            map_1=lambda wildcards: join_path(
                RESULTS,
                "01_normalized",
                f"{synteny_pair_record(wildcards)['species_1']}.gene_transcript_map.tsv",
            ),
            map_2=lambda wildcards: join_path(
                RESULTS,
                "01_normalized",
                f"{synteny_pair_record(wildcards)['species_2']}.gene_transcript_map.tsv",
            ),
            proteins_1=lambda wildcards: join_path(
                RESULTS,
                "01_normalized",
                f"{synteny_pair_record(wildcards)['species_1']}.proteins.fa",
            ),
            proteins_2=lambda wildcards: join_path(
                RESULTS,
                "01_normalized",
                f"{synteny_pair_record(wildcards)['species_2']}.proteins.fa",
            ),
            precomputed=lambda wildcards: (
                str(SYNTENY_CONFIG["precomputed_blocks"])
                if SYNTENY_CONFIG.get("backend") == "precomputed"
                else []
            ),
        output:
            anchors=join_path(
                RESULTS, "08_duplication", "synteny_pairs", "{pair_id}", "anchors.tsv"
            ),
            blocks=join_path(
                RESULTS, "08_duplication", "synteny_pairs", "{pair_id}", "blocks.tsv"
            ),
            summary=join_path(
                RESULTS, "08_duplication", "synteny_pairs", "{pair_id}", "summary.tsv"
            ),
            provenance=join_path(
                RESULTS, "08_duplication", "synteny_pairs", "{pair_id}", "provenance.json"
            ),
        params:
            pair_id=lambda wildcards: wildcards.pair_id,
            species_1=lambda wildcards: synteny_pair_record(wildcards)["species_1"],
            species_2=lambda wildcards: synteny_pair_record(wildcards)["species_2"],
            backend=SYNTENY_CONFIG.get("backend", "jcvi"),
            min_anchors_per_block=SYNTENY_CONFIG.get("min_anchors_per_block", 5),
            cscore=SYNTENY_CONFIG.get("cscore", 0.95),
            tandem_nmax=SYNTENY_CONFIG.get("tandem_nmax", 10),
            work_dir=lambda wildcards: join_path(
                WORK, "08_duplication", "synteny_pairs", wildcards.pair_id
            ),
        threads:
            min(32, int(RUN.get("cores", 16)))
        log:
            stdout=join_path(LOGS, "08_duplication", "synteny", "{pair_id}.stdout.log"),
            stderr=join_path(LOGS, "08_duplication", "synteny", "{pair_id}.stderr.log"),
        conda:
            "../envs/synteny.yaml"
        script:
            "../scripts/run_synteny.py"


    rule render_synteny_figures:
        input:
            anchors=expand(
                join_path(
                    RESULTS, "08_duplication", "synteny_pairs", "{pair_id}", "anchors.tsv"
                ),
                pair_id=SYNTENY_PAIR_IDS,
            ),
            blocks=expand(
                join_path(
                    RESULTS, "08_duplication", "synteny_pairs", "{pair_id}", "blocks.tsv"
                ),
                pair_id=SYNTENY_PAIR_IDS,
            ),
            summaries=expand(
                join_path(
                    RESULTS, "08_duplication", "synteny_pairs", "{pair_id}", "summary.tsv"
                ),
                pair_id=SYNTENY_PAIR_IDS,
            ),
            provenances=expand(
                join_path(
                    RESULTS,
                    "08_duplication",
                    "synteny_pairs",
                    "{pair_id}",
                    "provenance.json",
                ),
                pair_id=SYNTENY_PAIR_IDS,
            ),
            members=MODULE_TARGETS["family"],
            duplication_modes=MODULE_TARGETS["duplication"],
            maps=NORMALIZED_MAPS,
            genomes=[record["genome"] for record in SPECIES_RECORDS],
        output:
            anchors=join_path(RESULTS, "08_duplication", "synteny_anchors.tsv"),
            anchors_xlsx=join_path(RESULTS, "08_duplication", "synteny_anchors.xlsx"),
            blocks=join_path(RESULTS, "08_duplication", "synteny_blocks.tsv"),
            blocks_xlsx=join_path(RESULTS, "08_duplication", "synteny_blocks.xlsx"),
            anchors_intra=join_path(RESULTS, "08_duplication", "synteny_anchors_intra.tsv"),
            anchors_intra_xlsx=join_path(
                RESULTS, "08_duplication", "synteny_anchors_intra.xlsx"
            ),
            blocks_intra=join_path(RESULTS, "08_duplication", "synteny_blocks_intra.tsv"),
            blocks_intra_xlsx=join_path(
                RESULTS, "08_duplication", "synteny_blocks_intra.xlsx"
            ),
            family_links=join_path(
                RESULTS, "08_duplication", "family_duplication_links.tsv"
            ),
            family_links_xlsx=join_path(
                RESULTS, "08_duplication", "family_duplication_links.xlsx"
            ),
            anchors_inter=join_path(RESULTS, "08_duplication", "synteny_anchors_inter.tsv"),
            anchors_inter_xlsx=join_path(
                RESULTS, "08_duplication", "synteny_anchors_inter.xlsx"
            ),
            blocks_inter=join_path(RESULTS, "08_duplication", "synteny_blocks_inter.tsv"),
            blocks_inter_xlsx=join_path(
                RESULTS, "08_duplication", "synteny_blocks_inter.xlsx"
            ),
            pair_summary=join_path(
                RESULTS, "08_duplication", "synteny_pair_summary.tsv"
            ),
            pair_summary_xlsx=join_path(
                RESULTS, "08_duplication", "synteny_pair_summary.xlsx"
            ),
            layout=join_path(
                RESULTS, "08_duplication", "synteny_layout_provenance.tsv"
            ),
            layout_xlsx=join_path(
                RESULTS, "08_duplication", "synteny_layout_provenance.xlsx"
            ),
            fig17_pdf=join_path(
                RESULTS, "08_duplication", "Fig17_representative_intragenome_circos.pdf"
            ),
            fig17_png=join_path(
                RESULTS, "08_duplication", "Fig17_representative_intragenome_circos.png"
            ),
            fig21_pdf=join_path(
                RESULTS, "08_duplication", "Fig21_inter_species_pairwise_synteny.pdf"
            ),
            fig21_png=join_path(
                RESULTS, "08_duplication", "Fig21_inter_species_pairwise_synteny.png"
            ),
            fig22_pdf=join_path(
                RESULTS, "08_duplication", "Fig22_inter_species_synteny_overview.pdf"
            ),
            fig22_png=join_path(
                RESULTS, "08_duplication", "Fig22_inter_species_synteny_overview.png"
            ),
        params:
            pair_records=SYNTENY_PAIR_RECORDS,
            species_ids=SPECIES,
            representative_species=SYNTENY_CONFIG.get("representative_species"),
            png_dpi=PNG_DPI,
        conda:
            "../envs/synteny.yaml"
        script:
            "../scripts/render_synteny_figures.py"
