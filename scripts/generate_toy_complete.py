#!/usr/bin/env python3
"""Generate the deterministic, input-only PanFamFlow complete-profile fixture."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
OUTPUT = REPOSITORY / "examples" / "toy_complete"
SPECIES = ("SpA", "SpB", "SpC", "SpD")
GROUPS = {"SpA": "Group_1", "SpB": "Group_1", "SpC": "Group_2", "SpD": "Group_2"}
SPECIES_NAMES = {
    "SpA": "Synthetic_species_A",
    "SpB": "Synthetic_species_B",
    "SpC": "Synthetic_species_C",
    "SpD": "Synthetic_species_D",
}
AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
CODONS = {
    "A": "GCT",
    "C": "TGT",
    "D": "GAT",
    "E": "GAA",
    "F": "TTT",
    "G": "GGT",
    "H": "CAT",
    "I": "ATT",
    "K": "AAA",
    "L": "CTG",
    "M": "ATG",
    "N": "AAT",
    "P": "CCT",
    "Q": "CAA",
    "R": "CGT",
    "S": "TCT",
    "T": "ACT",
    "V": "GTT",
    "W": "TGG",
    "Y": "TAT",
}


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    lines = ["\t".join(columns)]
    for row in rows:
        lines.append("\t".join(str(row.get(column, "")) for column in columns))
    write_text(path, "\n".join(lines) + "\n")


def wrap_fasta(identifier: str, sequence: str) -> str:
    wrapped = "\n".join(sequence[index : index + 60] for index in range(0, len(sequence), 60))
    return f">{identifier}\n{wrapped}\n"


def protein_sequence(species_index: int, gene_index: int) -> str:
    # Each gene family gets an independent high-complexity ancestor, while the
    # four species carry only a few deterministic substitutions.  This avoids
    # low-complexity masking in DIAMOND and gives OrthoFinder real homologous
    # groups without making different genes artificial near-duplicates.
    generator = random.Random(20260821 + gene_index)
    variable = list(generator.choices(AMINO_ACIDS, k=98))
    for offset in range(2):
        mutation_position = (11 + species_index * 17 + offset * 29) % len(variable)
        current = variable[mutation_position]
        replacement_index = (
            AMINO_ACIDS.index(current) + gene_index + species_index + offset + 1
        ) % len(AMINO_ACIDS)
        variable[mutation_position] = AMINO_ACIDS[replacement_index]
    return "M" + "".join(variable)


def coding_sequence(protein: str) -> str:
    return "".join(CODONS[amino_acid] for amino_acid in protein) + "TAA"


def generate_genomes() -> dict[str, dict[str, str]]:
    proteins: dict[str, dict[str, str]] = {}
    for species_index, species in enumerate(SPECIES):
        genome = list("A" * 24000)
        gff = ["##gff-version 3"]
        proteins[species] = {}
        for gene_index in range(1, 7):
            gene_id = f"Gene{gene_index:02d}"
            transcript_id = f"{gene_id}.1"
            start = 1500 + (gene_index - 1) * 3500
            exon_1_end = start + 149
            exon_2_start = start + 250
            end = start + 399
            protein = protein_sequence(species_index, gene_index)
            cds = coding_sequence(protein)
            assert len(cds) == 300
            genome[start - 1 : exon_1_end] = cds[:150]
            genome[exon_2_start - 1 : end] = cds[150:]
            proteins[species][gene_id] = protein
            attributes = f"ID={gene_id};Name={gene_id}"
            gff.extend(
                [
                    f"Chr1\tPanFamFlow\tgene\t{start}\t{end}\t.\t+\t.\t{attributes}",
                    f"Chr1\tPanFamFlow\tmRNA\t{start}\t{end}\t.\t+\t.\tID={transcript_id};Parent={gene_id}",
                    f"Chr1\tPanFamFlow\texon\t{start}\t{exon_1_end}\t.\t+\t.\tID={transcript_id}.exon1;Parent={transcript_id}",
                    f"Chr1\tPanFamFlow\tCDS\t{start}\t{exon_1_end}\t.\t+\t0\tID={transcript_id}.cds1;Parent={transcript_id}",
                    f"Chr1\tPanFamFlow\texon\t{exon_2_start}\t{end}\t.\t+\t.\tID={transcript_id}.exon2;Parent={transcript_id}",
                    f"Chr1\tPanFamFlow\tCDS\t{exon_2_start}\t{end}\t.\t+\t0\tID={transcript_id}.cds2;Parent={transcript_id}",
                ]
            )
        data_dir = OUTPUT / "data" / species
        write_text(data_dir / "genome.fa", wrap_fasta("Chr1", "".join(genome)))
        write_text(data_dir / "annotation.gff3", "\n".join(gff) + "\n")
    return proteins


def generate_family_references(proteins: dict[str, dict[str, str]]) -> None:
    member_rows: list[dict[str, object]] = []
    subfamily_rows: list[dict[str, object]] = []
    duplication_rows: list[dict[str, object]] = []
    promoter_rows: list[dict[str, object]] = []
    domain_fasta: list[str] = []
    modes = ("WGD", "Tandem", "Proximal", "Transposed", "Dispersed", "Singleton")
    elements = (
        ("ABRE", "Stress_response", "Abscisic_acid_response"),
        ("MBS", "Stress_response", "Drought_response"),
        ("W-box", "Stress_response", "Pathogen_response"),
        ("G-box", "Light_response", "Light_response"),
        ("CAT-box", "Growth_development", "Meristem_expression"),
    )
    for species in SPECIES:
        for gene_index in range(1, 7):
            gene_id = f"Gene{gene_index:02d}"
            stable_id = f"{species}__{gene_id}"
            subfamily = f"SF{((gene_index - 1) // 2) + 1}"
            member_rows.append(
                {
                    "stable_id": stable_id,
                    "species_id": species,
                    "gene_id": gene_id,
                    "fixture_scope": "TOY_ENGINEERING_ONLY",
                }
            )
            subfamily_rows.append({"stable_id": stable_id, "subfamily": subfamily})
            partner_index = gene_index + 1 if gene_index % 2 else gene_index - 1
            duplication_rows.append(
                {
                    "stable_id": stable_id,
                    "duplication_mode": modes[gene_index - 1],
                    "partner_stable_id": (
                        f"{species}__Gene{partner_index:02d}" if gene_index < 6 else ""
                    ),
                }
            )
            for offset in range(1 + (gene_index % 3)):
                element, major_class, subclass = elements[(gene_index + offset - 1) % len(elements)]
                promoter_rows.append(
                    {
                        "stable_id": stable_id,
                        "element": element,
                        "major_class": major_class,
                        "subclass": subclass,
                        "source": "SYNTHETIC_PLANTCARE_LIKE_FIXTURE",
                    }
                )
            domain_fasta.append(wrap_fasta(stable_id, proteins[species][gene_id][20:70]))
    write_tsv(
        OUTPUT / "references" / "family_members.tsv",
        ["stable_id", "species_id", "gene_id", "fixture_scope"],
        member_rows,
    )
    write_tsv(
        OUTPUT / "references" / "subfamily_assignments.tsv",
        ["stable_id", "subfamily"],
        subfamily_rows,
    )
    write_tsv(
        OUTPUT / "references" / "duplication.tsv",
        ["stable_id", "duplication_mode", "partner_stable_id"],
        duplication_rows,
    )
    write_tsv(
        OUTPUT / "references" / "promoter.tsv",
        ["stable_id", "element", "major_class", "subclass", "source"],
        promoter_rows,
    )
    write_text(OUTPUT / "references" / "family_domain_alignment.fa", "".join(domain_fasta))


def generate_comparative_registry(proteins: dict[str, dict[str, str]]) -> None:
    external_id = "ExtGene01"
    external_protein = list(proteins["SpA"]["Gene01"])
    external_protein[11] = "Y" if external_protein[11] != "Y" else "F"
    external_fasta = OUTPUT / "references" / "external_outgroup.fa"
    write_text(external_fasta, wrap_fasta(external_id, "".join(external_protein)))
    digest = hashlib.sha256(external_fasta.read_bytes()).hexdigest()
    columns = [
        "source_type",
        "stable_id",
        "species_id",
        "sequence_path",
        "sequence_id",
        "accession",
        "version",
        "source_url",
        "expected_sha256",
        "outgroup",
    ]
    rows: list[dict[str, object]] = [
        {"source_type": "INTERNAL", "stable_id": f"{species}__Gene01", "species_id": species}
        for species in SPECIES
    ]
    rows.append(
        {
            "source_type": "EXTERNAL",
            "stable_id": "Ext__Gene01",
            "species_id": "Ext",
            "sequence_path": "external_outgroup.fa",
            "sequence_id": external_id,
            "accession": "TOYEXT0001",
            "version": "1",
            "source_url": "https://example.org/panfamflow/toy/TOYEXT0001.1",
            "expected_sha256": digest,
            "outgroup": "true",
        }
    )
    write_tsv(OUTPUT / "references" / "external_species.tsv", columns, rows)


def generate_synteny() -> None:
    pair_rows = [
        {
            "pair_id": "SpA_self",
            "species_1": "SpA",
            "species_2": "SpA",
            "layout_order": 1,
            "include_overview": "true",
        },
        {
            "pair_id": "SpA_vs_SpB",
            "species_1": "SpA",
            "species_2": "SpB",
            "layout_order": 2,
            "include_overview": "true",
        },
    ]
    write_tsv(
        OUTPUT / "references" / "synteny_pairs.tsv",
        ["pair_id", "species_1", "species_2", "layout_order", "include_overview"],
        pair_rows,
    )
    anchor_rows: list[dict[str, object]] = []
    for pair_id, species_1, species_2 in (
        ("SpA_self", "SpA", "SpA"),
        ("SpA_vs_SpB", "SpA", "SpB"),
    ):
        for gene_index in range(1, 7):
            anchor_rows.append(
                {
                    "pair_id": pair_id,
                    "block_id": f"{pair_id}_block01",
                    "anchor_id": f"{pair_id}_anchor{gene_index:02d}",
                    "species_1": species_1,
                    "species_2": species_2,
                    "stable_id_1": f"{species_1}__Gene{gene_index:02d}",
                    "stable_id_2": f"{species_2}__Gene{gene_index:02d}",
                    "orientation": "+",
                    "score": f"{1000 - gene_index:.1f}",
                    "evidence_type": "SYNTENY_ANCHOR",
                }
            )
    write_tsv(
        OUTPUT / "references" / "synteny_anchors.tsv",
        [
            "pair_id",
            "block_id",
            "anchor_id",
            "species_1",
            "species_2",
            "stable_id_1",
            "stable_id_2",
            "orientation",
            "score",
            "evidence_type",
        ],
        anchor_rows,
    )


def expression_value(species: str, gene_index: int, condition: str, replicate: int) -> float:
    baseline = 5.0 + gene_index * 2.0 + replicate * 0.25
    if species == "SpA" and condition == "Salt":
        if gene_index in {1, 2}:
            return baseline * 5.0
        if gene_index == 3:
            return baseline * 0.20
    if species == "SpB" and condition == "Infected":
        if gene_index in {1, 2}:
            return baseline * 4.0
        if gene_index == 3:
            return baseline * 0.25
    return baseline


def generate_expression() -> None:
    samples = [
        ("A_Control_R1", "DS_ABIOTIC", "SpA", "Control", 1, "Abiotic"),
        ("A_Control_R2", "DS_ABIOTIC", "SpA", "Control", 2, "Abiotic"),
        ("A_Salt_R1", "DS_ABIOTIC", "SpA", "Salt", 1, "Abiotic"),
        ("A_Salt_R2", "DS_ABIOTIC", "SpA", "Salt", 2, "Abiotic"),
        ("B_Mock_R1", "DS_BIOTIC", "SpB", "Mock", 1, "Biotic"),
        ("B_Mock_R2", "DS_BIOTIC", "SpB", "Mock", 2, "Biotic"),
        ("B_Infected_R1", "DS_BIOTIC", "SpB", "Infected", 1, "Biotic"),
        ("B_Infected_R2", "DS_BIOTIC", "SpB", "Infected", 2, "Biotic"),
    ]
    expression_rows: list[dict[str, object]] = []
    count_rows: list[dict[str, object]] = []
    for species in SPECIES:
        for gene_index in range(1, 7):
            stable_id = f"{species}__Gene{gene_index:02d}"
            expression_row: dict[str, object] = {"stable_id": stable_id}
            count_row: dict[str, object] = {"stable_id": stable_id}
            for sample_id, _, sample_species, condition, replicate, _ in samples:
                if sample_species == species:
                    value = expression_value(species, gene_index, condition, replicate)
                    expression_row[sample_id] = f"{value:.3f}"
                    count_row[sample_id] = round(value * 20)
                else:
                    expression_row[sample_id] = ""
                    count_row[sample_id] = 0
            expression_rows.append(expression_row)
            count_rows.append(count_row)
    sample_ids = [sample[0] for sample in samples]
    write_tsv(
        OUTPUT / "references" / "expression.tsv",
        ["stable_id", *sample_ids],
        expression_rows,
    )
    write_tsv(
        OUTPUT / "references" / "raw_counts.tsv",
        ["stable_id", *sample_ids],
        count_rows,
    )
    metadata_rows: list[dict[str, object]] = []
    design_rows: list[dict[str, object]] = []
    for sample_id, dataset_id, species, condition, replicate, stress_category in samples:
        tissue = "Seedling"
        metadata_rows.append(
            {
                "sample_id": sample_id,
                "species_id": species,
                "condition": condition,
                "tissue": tissue,
                "stress_type": stress_category,
                "timepoint": "24h",
                "replicate": replicate,
                "batch": "B1",
            }
        )
        design_rows.append(
            {
                "dataset_id": dataset_id,
                "sample_id": sample_id,
                "species_id": species,
                "condition": condition,
                "biological_replicate": replicate,
                "batch": "B1",
                "stress_category": stress_category,
                "evidence_grade": "TOY_ENGINEERING_ONLY",
                "accession": f"TOY_{dataset_id}",
                "reference_version": "synthetic_v1",
                "file_verification_status": "GENERATED_FIXTURE_VERIFIED",
            }
        )
    write_tsv(
        OUTPUT / "references" / "sample_metadata.tsv",
        [
            "sample_id",
            "species_id",
            "condition",
            "tissue",
            "stress_type",
            "timepoint",
            "replicate",
            "batch",
        ],
        metadata_rows,
    )
    write_tsv(
        OUTPUT / "references" / "de_design.tsv",
        [
            "dataset_id",
            "sample_id",
            "species_id",
            "condition",
            "biological_replicate",
            "batch",
            "stress_category",
            "evidence_grade",
            "accession",
            "reference_version",
            "file_verification_status",
        ],
        design_rows,
    )
    write_tsv(
        OUTPUT / "references" / "de_contrasts.tsv",
        ["contrast_id", "dataset_id", "numerator", "denominator", "stress_category", "is_primary"],
        [
            {
                "contrast_id": "Salt_vs_Control",
                "dataset_id": "DS_ABIOTIC",
                "numerator": "Salt",
                "denominator": "Control",
                "stress_category": "Abiotic",
                "is_primary": "true",
            },
            {
                "contrast_id": "Infected_vs_Mock",
                "dataset_id": "DS_BIOTIC",
                "numerator": "Infected",
                "denominator": "Mock",
                "stress_category": "Biotic",
                "is_primary": "true",
            },
        ],
    )


def generate_config() -> None:
    species_blocks: list[str] = []
    for index, species in enumerate(SPECIES):
        outgroup = SPECIES[(index + 1) % len(SPECIES)]
        species_blocks.append(
            f"""    - id: {species}
      name: {SPECIES_NAMES[species]}
      genome: data/{species}/genome.fa
      gff3: data/{species}/annotation.gff3
      protein: null
      cds: null
      group: {GROUPS[species]}
      subfamily: Synthetic_clade
      representative: {"true" if species == "SpA" else "false"}
      outgroup: {outgroup}
      busco_lineage: embryophyta_odb12"""
        )
    config = f"""schema_version: "1.1"
project:
  analysis_scope: target_pan_gene_family
  name: toy_complete_gene_family
  root: .
  seed: 20260821
  results_dir: results
  work_dir: work
  logs_dir: logs
run:
  modules: [qc, normalize, family, phylogeny, gene_structure, orthology, pan_family, chromosome, duplication, kaks, promoter, expression, report]
  cores: 8
  jobs: 8
  engine_runner: current
  engine_env: null
  use_conda: true
  resume_mode: smart
  keep_going: true
  rerun_incomplete: true
  latency_wait: 120
  retries: 1
  rerun_triggers: [mtime, input, params, code, software-env]
  printshellcmds: true
  show_failed_logs: true
  profile: null
  extra_snakemake_args: []
inputs:
  species:
{chr(10).join(species_blocks)}
  rnaseq_samples: []
  expression_matrix: references/expression.tsv
  sample_metadata: references/sample_metadata.tsv
qc:
  calculate_sha256: true
  busco:
    enabled: false
    mode: genome
    threads: 2
    offline: false
    download_path: null
    extra_args: []
canonical_transcript:
  method: longest_cds
  backend: portable_gff3
  sequence_source: gffread
  stable_id_separator: "__"
family:
  name: TOY_COMPLETE
  combine_evidence: union
  calculate_protein_properties: true
  hmm:
    enabled: false
    hmm: null
    evalue: 1.0e-5
    domain_evalue: 1.0e-3
    cut_ga: false
  blast:
    enabled: false
    reference_proteins: null
    evalue: 1.0e-5
    min_identity: 30.0
    min_query_coverage: 50.0
    max_target_seqs: 100
  subfamily_assignments: references/subfamily_assignments.tsv
  domain_validation_table: null
  domain_alignment: references/family_domain_alignment.fa
  subcellular_localization_table: null
  precomputed_members: references/family_members.tsv
phylogeny:
  mafft_mode: auto
  trim_mode: smart-gap
  model: MFP
  ultrafast_bootstrap: 1000
  sh_alrt: 1000
  min_sequences: 4
orthofinder:
  hog_node: auto
  search_threads: 8
  analysis_threads: 2
  extra_args: []
pan_family:
  core_min: 0.99
  soft_core_min: 0.75
  shell_min: 0.25
  rarefaction_iterations: 100
  max_exact_combinations: 1000
gene_structure:
  metrics: [gene_length, protein_length, cds_length, exon_count, intron_count, total_intron_length]
  inference_unit: species_median
  min_group_units: 2
  alpha: 0.05
chromosome:
  representative_only: false
  density_window_bp: 5000
duplication:
  backend: precomputed
  targets: null
  precomputed_table: references/duplication.tsv
  dupgen_executable: DupGen_finder-unique.pl
  diamond_evalue: 1.0e-10
  max_target_seqs: 5
  proximal_max_gene_distance: 10
  extra_args: []
kaks:
  pair_source: both
  reference_species: SpA
  method: MA
  max_pairs_per_group: 4
  saturation_ks: 2.0
  workers: 4
promoter:
  backend: precomputed_plantcare
  upstream_bp: 1000
  downstream_bp: 0
  motif_database: null
  category_map: null
  precomputed_table: references/promoter.tsv
  fimo_threshold: 1.0e-4
  top_n_elements: 10
expression:
  mode: imported_matrix
  min_tpm_detected: 1.0
  heatmap_transform: log2_tpm1_zscore
  fastp_extra_args: []
  hisat2_extra_args: []
  stringtie_extra_args: []
deliverables:
  profile: pdf_md_complete
comparative_panel:
  enabled: true
  external_species_table: references/external_species.tsv
  selection_strategy: explicit
  include_in_pan_denominator: false
domain_logo:
  enabled: true
  source: precomputed_alignment
  precomputed_alignment: references/family_domain_alignment.fa
  min_domain_coverage: 0.50
  min_column_occupancy: 0.50
synteny:
  enabled: true
  backend: precomputed
  species_pairs_table: references/synteny_pairs.tsv
  precomputed_blocks: references/synteny_anchors.tsv
  representative_species: SpA
  min_anchors_per_block: 5
  cscore: 0.95
  tandem_nmax: 10
differential_expression:
  enabled: true
  source: precomputed_counts
  input_scale: raw_counts
  counts_table: references/raw_counts.tsv
  design_table: references/de_design.tsv
  contrasts_table: references/de_contrasts.tsv
  min_replicates: 2
  alpha: 0.05
  lfc_threshold: 1.0
  min_total_count: 10
  feature_type: exon
  feature_attribute: Parent
  container_image: docker://panfamflow/expression-de@sha256:6f85d371ca4db01fcad2ab615bfad9d792a6ea5a0223f62b16acf277e0526a9d
plot:
  pdf: true
  png: true
  png_dpi: 600
  language: English
report:
  title: PanFamFlow complete synthetic engineering fixture
  include_existing_results: true
"""
    write_text(OUTPUT / "config.yaml", config)


def generate_readme() -> None:
    write_text(
        OUTPUT / "README.md",
        """# PanFamFlow complete synthetic fixture

This directory contains deterministic synthetic inputs only. It exercises every
PanFamFlow module and every optional complete-profile path, but it is not
biological evidence and must not be used for biological interpretation.

- Scope: `TOY_ENGINEERING_ONLY`
- Seed: `20260821`
- Expected runtime host: Kunpeng HPC with the frozen PanFamFlow engine
- Expected outputs: generated under `results/`, `work/`, and `logs/` at run time

Regenerate the fixture from the repository root with:

```bash
uv run python scripts/generate_toy_complete.py
```
""",
    )


def main() -> None:
    forbidden = [OUTPUT / name for name in ("results", "work", "logs", ".snakemake", ".panfamflow")]
    existing = [path for path in forbidden if path.exists()]
    if existing:
        raise RuntimeError(
            "Refusing to regenerate over run-state directories: " + ", ".join(map(str, existing))
        )
    proteins = generate_genomes()
    generate_family_references(proteins)
    generate_comparative_registry(proteins)
    generate_synteny()
    generate_expression()
    generate_config()
    generate_readme()


if __name__ == "__main__":
    main()
