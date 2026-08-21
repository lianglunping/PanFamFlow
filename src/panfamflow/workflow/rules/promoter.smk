PROMOTER_BACKEND = config.get("promoter", {}).get("backend", "fimo")
PROMOTER_MOTIF_DATABASE = config.get("promoter", {}).get("motif_database")
PROMOTER_CATEGORY_MAP = config.get("promoter", {}).get("category_map")
PROMOTER_PRECOMPUTED = config.get("promoter", {}).get("precomputed_table")


rule extract_family_promoters:
    input:
        members=MODULE_TARGETS["family"],
        maps=NORMALIZED_MAPS,
        gff3s=NORMALIZED_GFFS,
        genomes=[record["genome"] for record in SPECIES_RECORDS],
    output:
        fasta=ensure(join_path(RESULTS, "10_promoter", "family_promoters.fa"), non_empty=True),
        coordinates=ensure(join_path(RESULTS, "10_promoter", "promoter_coordinates.tsv"), non_empty=True),
        coordinates_xlsx=ensure(join_path(RESULTS, "10_promoter", "promoter_coordinates.xlsx"), non_empty=True),
    params:
        species_ids=SPECIES,
        genome_paths=[record["genome"] for record in SPECIES_RECORDS],
        separator=SEPARATOR,
        upstream_bp=int(config.get("promoter", {}).get("upstream_bp", 2000)),
        downstream_bp=int(config.get("promoter", {}).get("downstream_bp", 0)),
    conda:
        "../envs/promoter.yaml"
    retries:
        int(RUN.get("retries", 1))
    script:
        "../scripts/extract_promoters.py"


if PROMOTER_BACKEND == "fimo":
    rule scan_promoters_fimo:
        input:
            promoters=rules.extract_family_promoters.output.fasta,
            motifs=PROMOTER_MOTIF_DATABASE,
        output:
            tsv=ensure(join_path(WORK, "10_promoter", "fimo.tsv"), non_empty=True),
        params:
            threshold=float(config.get("promoter", {}).get("fimo_threshold", 1.0e-4)),
            outdir=join_path(WORK, "10_promoter", "fimo_run"),
        log:
            join_path(LOGS, "promoter", "fimo.log")
        conda:
            "../envs/promoter.yaml"
        retries:
            int(RUN.get("retries", 1))
        shell:
            r"""
            set -euo pipefail
            mkdir -p "$(dirname {output.tsv})" "$(dirname {log})"
            tmpdir="{params.outdir}.partial.$$"
            rm -rf "$tmpdir"
            fimo --thresh {params.threshold} --oc "$tmpdir" {input.motifs} {input.promoters} > {log} 2>&1
            test -s "$tmpdir/fimo.tsv"
            mv "$tmpdir/fimo.tsv" "{output.tsv}.partial.$$"
            rm -rf "$tmpdir"
            mv "{output.tsv}.partial.$$" {output.tsv}
            """
else:
    rule scan_promoters_fimo:
        output:
            tsv=join_path(WORK, "10_promoter", "fimo.tsv"),
        shell:
            "mkdir -p $(dirname {output.tsv}); : > {output.tsv}"


PROMOTER_OPTIONAL_INPUTS = [path for path in (PROMOTER_CATEGORY_MAP, PROMOTER_PRECOMPUTED) if path]


rule parse_promoter_elements:
    input:
        coordinates=rules.extract_family_promoters.output.coordinates,
        members=MODULE_TARGETS["family"],
        hog_membership=join_path(
            RESULTS, "06_pan_family", "family_hog_membership.tsv"
        ) if COMPLETE_PROFILE else [],
        pan_classification=MODULE_TARGETS["pan_family"] if COMPLETE_PROFILE else [],
        fimo=rules.scan_promoters_fimo.output.tsv,
        optional=PROMOTER_OPTIONAL_INPUTS,
    output:
        elements=ensure(MODULE_TARGETS["promoter"], non_empty=True),
        summary=ensure(join_path(RESULTS, "10_promoter", "promoter_element_summary.tsv"), non_empty=True),
        per_gene=ensure(join_path(RESULTS, "10_promoter", "promoter_elements_per_gene.tsv"), non_empty=True),
        distributions=ensure(join_path(RESULTS, "10_promoter", "promoter_element_distributions.tsv"), non_empty=True),
        distribution_qc=ensure(join_path(RESULTS, "10_promoter", "promoter_distribution_qc.tsv"), non_empty=True),
        major_class_source=join_path(
            RESULTS, "10_promoter", "promoter_major_class_summary.tsv"
        ),
        subclass_source=join_path(RESULTS, "10_promoter", "promoter_subclass_summary.tsv"),
        subfamily_heatmap_source=join_path(
            RESULTS, "10_promoter", "promoter_heatmap_subfamily.tsv"
        ),
        group_subfamily_heatmap_source=join_path(
            RESULTS, "10_promoter", "promoter_heatmap_group_subfamily.tsv"
        ),
        species_heatmap_source=join_path(
            RESULTS, "10_promoter", "promoter_heatmap_species.tsv"
        ),
        representative_gene_source=join_path(
            RESULTS, "10_promoter", "representative_gene_element_matrix.tsv"
        ),
        hog_summary=join_path(RESULTS, "10_promoter", "promoter_by_hog.tsv"),
        hog_summary_xlsx=join_path(RESULTS, "10_promoter", "promoter_by_hog.xlsx"),
        hog_qc=join_path(RESULTS, "10_promoter", "promoter_by_hog_qc.tsv"),
        hog_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_by_hog.pdf"),
        hog_plot_png=join_path(RESULTS, "10_promoter", "promoter_by_hog.png"),
        xlsx=ensure(join_path(RESULTS, "10_promoter", "promoter_elements.xlsx"), non_empty=True),
        class_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_element_class_counts.pdf"),
        class_plot_png=join_path(RESULTS, "10_promoter", "promoter_element_class_counts.png"),
        top_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_top_elements.pdf"),
        top_plot_png=join_path(RESULTS, "10_promoter", "promoter_top_elements.png"),
        species_subfamily_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_species_subfamily_zscore_heatmap.pdf"),
        species_subfamily_plot_png=join_path(RESULTS, "10_promoter", "promoter_species_subfamily_zscore_heatmap.png"),
        subfamily_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_subfamily_zscore_heatmap.pdf"),
        subfamily_plot_png=join_path(RESULTS, "10_promoter", "promoter_subfamily_zscore_heatmap.png"),
        species_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_species_zscore_heatmap.pdf"),
        species_plot_png=join_path(RESULTS, "10_promoter", "promoter_species_zscore_heatmap.png"),
        group_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_group_zscore_heatmap.pdf"),
        group_plot_png=join_path(RESULTS, "10_promoter", "promoter_group_zscore_heatmap.png"),
        group_subfamily_plot_pdf=join_path(RESULTS, "10_promoter", "promoter_group_subfamily_zscore_heatmap.pdf"),
        group_subfamily_plot_png=join_path(RESULTS, "10_promoter", "promoter_group_subfamily_zscore_heatmap.png"),
        fig23_pdf=join_path(
            RESULTS, "10_promoter", "Fig23_promoter_four_major_classes.pdf"
        ),
        fig23_png=join_path(
            RESULTS, "10_promoter", "Fig23_promoter_four_major_classes.png"
        ),
        fig24_pdf=join_path(RESULTS, "10_promoter", "Fig24_promoter_subclasses.pdf"),
        fig24_png=join_path(RESULTS, "10_promoter", "Fig24_promoter_subclasses.png"),
        fig25_pdf=join_path(RESULTS, "10_promoter", "Fig25_promoter_by_subfamily.pdf"),
        fig25_png=join_path(RESULTS, "10_promoter", "Fig25_promoter_by_subfamily.png"),
        fig26_pdf=join_path(
            RESULTS, "10_promoter", "Fig26_promoter_by_group_subfamily.pdf"
        ),
        fig26_png=join_path(
            RESULTS, "10_promoter", "Fig26_promoter_by_group_subfamily.png"
        ),
        fig27_pdf=join_path(RESULTS, "10_promoter", "Fig27_promoter_by_species.pdf"),
        fig27_png=join_path(RESULTS, "10_promoter", "Fig27_promoter_by_species.png"),
        fig28_pdf=join_path(
            RESULTS, "10_promoter", "Fig28_representative_gene_top_elements.pdf"
        ),
        fig28_png=join_path(
            RESULTS, "10_promoter", "Fig28_representative_gene_top_elements.png"
        ),
    params:
        backend=PROMOTER_BACKEND,
        category_map=PROMOTER_CATEGORY_MAP,
        precomputed_table=PROMOTER_PRECOMPUTED,
        separator=SEPARATOR,
        top_n_elements=int(config.get("promoter", {}).get("top_n_elements", 20)),
        png_dpi=PNG_DPI,
        complete_profile=COMPLETE_PROFILE,
    conda:
        "../envs/promoter.yaml"
    retries:
        int(RUN.get("retries", 1))
    script:
        "../scripts/parse_promoter_elements.py"
