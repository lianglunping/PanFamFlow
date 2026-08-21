from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from panfamflow.config import WorkflowConfig, analysis_config_hash, execution_config_hash
from panfamflow.modules import resolve_modules, targets_for_modules

TOY_CONFIG = Path(__file__).parents[1] / "examples" / "toy" / "config.yaml"


def _toy_raw() -> dict[str, object]:
    raw = yaml.safe_load(TOY_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def test_schema_10_normalization_fingerprints_and_targets_are_unchanged() -> None:
    config = WorkflowConfig.model_validate(_toy_raw())

    assert config.schema_version == "1.0"
    assert analysis_config_hash(config) == (
        "cfcf21e3972ae430ff0cae0f9445f76c916a6ed4e0e50bca7e39bd97e16ffb10"
    )
    assert execution_config_hash(config) == (
        "8ce056819c63442ccfd4da1b55eb849de0abca3afa8aca6d742f202845de6da0"
    )
    modules = resolve_modules(config.run.modules, config)
    assert modules == ("qc",)
    assert targets_for_modules(modules, str(config.project.results_dir)) == (
        "results/00_qc/qc.done",
    )


def test_schema_11_optional_complete_profile_defaults_heavy_paths_off() -> None:
    raw = _toy_raw()
    raw["schema_version"] = "1.1"
    raw["deliverables"] = {"profile": "pdf_md_complete"}

    config = WorkflowConfig.model_validate(raw)

    assert config.schema_version == "1.1"
    assert config.deliverables.profile == "pdf_md_complete"
    assert config.synteny.enabled is False
    assert config.differential_expression.enabled is False
    assert config.comparative_panel.enabled is False
    assert config.comparative_panel.include_in_pan_denominator is False
    assert config.domain_logo.enabled is False


def test_formal_de_rejects_tpm_or_fpkm_input_scale() -> None:
    for scale in ("tpm", "fpkm"):
        raw = _toy_raw()
        raw["schema_version"] = "1.1"
        raw["differential_expression"] = {
            "enabled": True,
            "input_scale": scale,
            "counts_table": "references/expression.tsv",
            "design_table": "references/sample_metadata.tsv",
            "contrasts_table": "references/contrasts.tsv",
        }

        try:
            WorkflowConfig.model_validate(raw)
        except ValidationError as error:
            assert "raw integer counts" in str(error)
        else:
            raise AssertionError(f"Formal DE accepted {scale!r} input")


def test_external_comparative_species_cannot_enter_pan_denominator() -> None:
    raw = _toy_raw()
    raw["schema_version"] = "1.1"
    raw["comparative_panel"] = {
        "enabled": True,
        "external_species_table": "references/external_species.tsv",
        "include_in_pan_denominator": True,
    }

    try:
        WorkflowConfig.model_validate(raw)
    except ValidationError as error:
        assert "include_in_pan_denominator" in str(error)
    else:
        raise AssertionError("External comparative species entered the pan-family denominator")


def test_enabled_comparative_panel_requires_a_versioned_registry() -> None:
    raw = _toy_raw()
    raw["schema_version"] = "1.1"
    raw["comparative_panel"] = {"enabled": True}

    with pytest.raises(ValidationError, match="external_species_table"):
        WorkflowConfig.model_validate(raw)


def test_enabled_synteny_requires_explicit_pairs_and_representative() -> None:
    raw = _toy_raw()
    raw["schema_version"] = "1.1"
    raw["synteny"] = {"enabled": True, "backend": "jcvi"}

    with pytest.raises(ValidationError, match="species_pairs_table"):
        WorkflowConfig.model_validate(raw)


def test_precomputed_synteny_requires_auditable_anchor_blocks() -> None:
    raw = _toy_raw()
    raw["schema_version"] = "1.1"
    raw["synteny"] = {
        "enabled": True,
        "backend": "precomputed",
        "species_pairs_table": "references/synteny_pairs.tsv",
        "representative_species": "SpA",
    }

    with pytest.raises(ValidationError, match="precomputed_blocks"):
        WorkflowConfig.model_validate(raw)
