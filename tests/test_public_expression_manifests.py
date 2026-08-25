from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
PUBLIC = ROOT / "examples" / "public_rice_expression"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_frozen_raw_manifest_covers_selected_runs_and_checksums() -> None:
    selected_rows = read_tsv(PUBLIC / "selected_samples.tsv")
    selected_runs = {run_id for row in selected_rows for run_id in row["run_ids"].split(";")}
    files = read_tsv(PUBLIC / "raw_files.tsv")
    assert {row["run_id"] for row in files} == selected_runs
    assert all(row["url"].startswith("https://ftp.sra.ebi.ac.uk/") for row in files)
    assert all(re.fullmatch(r"[0-9a-f]{32}", row["md5"]) for row in files)
    assert all(int(row["bytes"]) > 0 for row in files)
    assert all(row["download_status"] == "CANDIDATE" for row in files)

    roles: dict[str, set[str]] = defaultdict(set)
    for row in files:
        roles[row["run_id"]].add(row["file_role"])
    assert all({"paired_1", "paired_2"}.issubset(run_roles) for run_roles in roles.values())


def test_processed_tpm_manifest_is_descriptive_and_immutable() -> None:
    rows = read_tsv(PUBLIC / "processed_files.tsv")
    assert len(rows) == 1
    row = rows[0]
    assert row["dataset_id"] == "GSE229334"
    assert row["analysis_role"] == "DESCRIPTIVE_TPM_ONLY"
    assert re.fullmatch(r"[0-9a-f]{32}", row["md5"])
    assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
    assert int(row["bytes"]) == 19_232_726


def test_tissue_tpm_manifest_selects_only_input_biological_replicates() -> None:
    rows = read_tsv(PUBLIC / "tissue_samples.tsv")

    assert len(rows) == 42
    assert len({row["sample_id"] for row in rows}) == 42
    assert len({row["matrix_column"] for row in rows}) == 42
    assert {row["dataset_id"] for row in rows} == {"GSE229334"}
    assert {row["library_role"] for row in rows} == {"RNA_SEQ_INPUT"}
    assert {row["include"] for row in rows} == {"TRUE"}
    assert {row["reference_version"] for row in rows} == {"Oryza_sativa.IRGSP-1.0.55"}
    assert all(row["matrix_column"].startswith("Input") for row in rows)
    assert all(
        row["official_url"].startswith("https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSM")
        for row in rows
    )

    tissue_replicates: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        tissue_replicates[row["tissue"]].add(row["biological_replicate"])
    assert len(tissue_replicates) == 14
    assert all(replicates == {"1", "2", "3"} for replicates in tissue_replicates.values())


def test_public_expression_readme_records_processed_matrix_decision_boundary() -> None:
    readme = (PUBLIC / "README.zh-CN.md").read_text(encoding="utf-8")
    assert "GSE101734" in readme and "GSE81906" in readme
    assert "FPKM" in readme
    assert "不能替代 `featureCounts` 原始整数 count 进入 DESeq2" in readme
    assert "目前将 NCBI 生成的 count 覆盖范围限定为人和小鼠" in readme


def test_requantification_reference_manifest_freezes_release_and_file_identity() -> None:
    rows = read_tsv(PUBLIC / "reference_files.tsv")
    assert {row["file_role"] for row in rows} == {"genome_fasta", "annotation_gff3"}
    assert {row["assembly"] for row in rows} == {"IRGSP-1.0"}
    assert {row["ensembl_plants_release"] for row in rows} == {"63"}
    assert all(row["url"].startswith("https://ftp.ensemblgenomes.ebi.ac.uk/") for row in rows)
    assert all(re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) for row in rows)
    assert all(int(row["bytes"]) > 0 for row in rows)
    assert all(row["source_checksum_status"] == "PASS" for row in rows)


def test_public_factorial_contrasts_have_explicit_context_estimands() -> None:
    contrasts = read_tsv(PUBLIC / "contrasts.tsv")
    required = {
        "design_formula",
        "factor",
        "numerator",
        "denominator",
        "contrast_type",
        "context_factor",
        "context_numerator",
        "context_denominator",
        "stress_category",
        "is_primary",
    }
    assert contrasts
    assert required.issubset(contrasts[0])
    assert {row["contrast_type"] for row in contrasts} == {
        "simple_effect",
        "interaction",
    }
    assert all(row["context_factor"] == "genotype" for row in contrasts)
    interactions = [row for row in contrasts if row["contrast_type"] == "interaction"]
    assert all(row["context_denominator"] for row in interactions)


def test_public_de_design_is_executable_and_preserves_factorial_metadata() -> None:
    selected = read_tsv(PUBLIC / "selected_samples.tsv")
    design = read_tsv(PUBLIC / "de_design.tsv")

    assert len(design) == len(selected) == 24
    assert {row["sample_id"] for row in design} == {row["sample_id"] for row in selected}
    assert {row["dataset_id"] for row in design} == {"GSE101734", "GSE81906"}
    assert {row["species_id"] for row in design} == {"Os_IRGSP1_release63"}
    assert {row["genotype"] for row in design} == {
        "9311",
        "9L136",
        "PB1",
        "PB1_Pi9",
    }
    assert all(row["biological_replicate"] in {"1", "2", "3"} for row in design)
    assert all(row["batch"] == "NOT_DECLARED" for row in design)
    assert all(row["evidence_grade"] == "PUBLIC_RAW_READS_REQUANTIFIED" for row in design)
    assert all(row["reference_version"] == "IRGSP-1.0_EnsemblPlants_release63" for row in design)
    assert all(row["file_verification_status"] == "MD5_AND_BYTES_VERIFIED" for row in design)
