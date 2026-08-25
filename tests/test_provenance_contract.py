from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_report_provenance_binds_inputs_contracts_seed_modules_and_boundary() -> None:
    source = (ROOT / "src/panfamflow/workflow/scripts/build_report.py").read_text(encoding="utf-8")

    for required_field in (
        '"input_manifest_path"',
        '"input_manifest_sha256"',
        '"figure_contract_sha256"',
        '"traceability_contract_sha256"',
        '"seed"',
        '"selected_modules"',
        '"scientific_boundary"',
    ):
        assert required_field in source
    assert "ENGINEERING_COMPLETION_IS_NOT_BIOLOGICAL_VALIDATION" in source
    assert "write_json(provenance, snakemake.output.provenance)" in source


def test_compute_node_provenance_validator_is_fail_closed_and_digest_pinned() -> None:
    validator = (ROOT / "scripts/hpc/verify_toy_provenance_immutability.jh").read_text(
        encoding="utf-8"
    )

    assert 'provenance["seed"] != 20260821' in validator
    assert 'provenance["selected_modules"] != expected_modules' in validator
    assert (
        'provenance["scientific_boundary"] != "ENGINEERING_COMPLETION_IS_NOT_BIOLOGICAL_VALIDATION"'
        in validator
    )
    assert 'provenance["input_manifest_sha256"]' in validator
    assert 'provenance["figure_contract_sha256"]' in validator
    assert 'provenance["traceability_contract_sha256"]' in validator
    assert "sha256:57252522c5af7ebfe6fcec649896065316771c8679cc36c2a3094b9e755eeb29" in validator
