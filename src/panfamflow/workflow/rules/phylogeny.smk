rule family_phylogeny:
    input:
        proteins=join_path(RESULTS, "02_family", "family_proteins.fa"),
        members=MODULE_TARGETS["family"],
    output:
        alignment=ensure(join_path(RESULTS, "03_phylogeny", "family.aligned.fa"), non_empty=True),
        trimmed=ensure(join_path(RESULTS, "03_phylogeny", "family.trimmed.fa"), non_empty=True),
        tree=ensure(MODULE_TARGETS["phylogeny"], non_empty=True),
        report=ensure(join_path(RESULTS, "03_phylogeny", "family.iqtree"), non_empty=True),
        tip_annotations=join_path(RESULTS, "03_phylogeny", "family_tree_tip_annotations.tsv"),
        figure_pdf=join_path(RESULTS, "03_phylogeny", "Fig01_all_family_tree.pdf"),
        figure_png=join_path(RESULTS, "03_phylogeny", "Fig01_all_family_tree.png"),
    params:
        min_sequences=int(config.get("phylogeny", {}).get("min_sequences", 4)),
        mafft_mode=config.get("phylogeny", {}).get("mafft_mode", "auto"),
        trim_mode=config.get("phylogeny", {}).get("trim_mode", "smart-gap"),
        model=config.get("phylogeny", {}).get("model", "MFP"),
        ultrafast_bootstrap=int(config.get("phylogeny", {}).get("ultrafast_bootstrap", 1000)),
        sh_alrt=int(config.get("phylogeny", {}).get("sh_alrt", 1000)),
        seed=SEED,
        work_dir=join_path(WORK, "03_phylogeny"),
        png_dpi=PNG_DPI,
    threads:
        min(int(RUN.get("cores", 16)), 32)
    resources:
        mem_mb=32000,
        runtime=1440,
    log:
        mafft=join_path(LOGS, "phylogeny", "mafft.stderr.log"),
        clipkit_stdout=join_path(LOGS, "phylogeny", "clipkit.stdout.log"),
        clipkit_stderr=join_path(LOGS, "phylogeny", "clipkit.stderr.log"),
        iqtree_stdout=join_path(LOGS, "phylogeny", "iqtree.stdout.log"),
        iqtree_stderr=join_path(LOGS, "phylogeny", "iqtree.stderr.log"),
    conda:
        "../envs/phylogeny.yaml"
    retries:
        int(RUN.get("retries", 1))
    script:
        "../scripts/run_phylogeny.py"


if COMPARATIVE_PANEL.get("enabled", False):
    rule comparative_family_phylogeny:
        input:
            proteins=join_path(RESULTS, "02_family", "family_proteins.fa"),
            members=MODULE_TARGETS["family"],
            registry=str(COMPARATIVE_PANEL["external_species_table"]),
        output:
            selection=join_path(RESULTS, "03_phylogeny", "comparative_panel_selection.tsv"),
            provenance=join_path(RESULTS, "03_phylogeny", "external_sequence_provenance.tsv"),
            fasta=join_path(RESULTS, "03_phylogeny", "comparative_panel.fa"),
            alignment=join_path(RESULTS, "03_phylogeny", "comparative.aligned.fa"),
            trimmed=join_path(RESULTS, "03_phylogeny", "comparative.trimmed.fa"),
            tree=join_path(RESULTS, "03_phylogeny", "comparative.treefile"),
            report=join_path(RESULTS, "03_phylogeny", "comparative.iqtree"),
            tip_annotations=join_path(
                RESULTS, "03_phylogeny", "comparative_tree_tip_annotations.tsv"
            ),
            figure_pdf=join_path(
                RESULTS, "03_phylogeny", "Fig03_representative_external_tree.pdf"
            ),
            figure_png=join_path(
                RESULTS, "03_phylogeny", "Fig03_representative_external_tree.png"
            ),
        params:
            selection_strategy=COMPARATIVE_PANEL.get("selection_strategy", "explicit"),
            min_sequences=int(config.get("phylogeny", {}).get("min_sequences", 4)),
            mafft_mode=config.get("phylogeny", {}).get("mafft_mode", "auto"),
            trim_mode=config.get("phylogeny", {}).get("trim_mode", "smart-gap"),
            model=config.get("phylogeny", {}).get("model", "MFP"),
            ultrafast_bootstrap=int(
                config.get("phylogeny", {}).get("ultrafast_bootstrap", 1000)
            ),
            sh_alrt=int(config.get("phylogeny", {}).get("sh_alrt", 1000)),
            seed=SEED,
            work_dir=join_path(WORK, "03_phylogeny", "comparative"),
            png_dpi=PNG_DPI,
        threads:
            min(int(RUN.get("cores", 16)), 32)
        resources:
            mem_mb=32000,
            runtime=1440,
        log:
            mafft=join_path(LOGS, "phylogeny", "comparative.mafft.stderr.log"),
            clipkit_stdout=join_path(LOGS, "phylogeny", "comparative.clipkit.stdout.log"),
            clipkit_stderr=join_path(LOGS, "phylogeny", "comparative.clipkit.stderr.log"),
            iqtree_stdout=join_path(LOGS, "phylogeny", "comparative.iqtree.stdout.log"),
            iqtree_stderr=join_path(LOGS, "phylogeny", "comparative.iqtree.stderr.log"),
        conda:
            "../envs/phylogeny.yaml"
        retries:
            int(RUN.get("retries", 1))
        script:
            "../scripts/run_comparative_phylogeny.py"
