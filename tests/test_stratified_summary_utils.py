from __future__ import annotations

import pandas as pd
import pytest

from panfamflow.workflow.scripts.stratified_summary_utils import (
    annotate_kaks_pairs,
    build_duplication_summaries,
    build_family_distribution,
    build_pan_family_summaries,
    nonzero_composition,
    numeric_pivot,
    summarize_kaks_strata,
)


def test_nonzero_composition_omits_zero_count_labels() -> None:
    table = pd.DataFrame(
        {
            "pan_family_class": ["Core", "Soft-core", "Shell", "Cloud"],
            "count": [0, 0, 2, 0],
        }
    )

    labels, values = nonzero_composition(table, label_column="pan_family_class")

    assert labels == ["Shell"]
    assert values == [2]


def test_numeric_pivot_converts_nullable_object_values_for_plotting() -> None:
    table = pd.DataFrame(
        {
            "species_id": ["SpA", "SpA", "SpB", "SpB"],
            "pan_class": ["Core", "Shell", "Core", "Shell"],
            "fraction": pd.Series([1.0, pd.NA, 0.5, 0.5], dtype="object"),
        }
    )

    matrix = numeric_pivot(
        table,
        index="species_id",
        columns="pan_class",
        values="fraction",
        column_order=["Core", "Shell"],
        fill_value=0.0,
    )

    assert all(pd.api.types.is_float_dtype(dtype) for dtype in matrix.dtypes)
    assert matrix.loc["SpA", "Shell"] == 0.0


@pytest.fixture
def members() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stable_id": ["A1", "A2", "B1", "B2"],
            "species_id": ["SpA", "SpA", "SpB", "SpB"],
            "gene_id": ["A1", "A2", "B1", "B2"],
            "subfamily": ["S1", "S2", "S1", "S2"],
            "group": ["Cultivated", "Cultivated", "Wild", "Wild"],
        }
    )


@pytest.fixture
def membership() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "HOG_ID": ["H1", "H2", "H1", "H3"],
            "stable_id": ["A1", "A2", "B1", "B2"],
            "species_id": ["SpA", "SpA", "SpB", "SpB"],
        }
    )


@pytest.fixture
def classification() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "HOG_ID": ["H1", "H2", "H3"],
            "pan_family_class": ["Core", "Shell", "Shell"],
        }
    )


def test_family_distribution_is_zero_complete_and_closes_species_denominators(
    members: pd.DataFrame,
) -> None:
    distribution = build_family_distribution(members, species_ids=["SpA", "SpB"])

    assert len(distribution) == 4
    missing_cell = distribution.loc[
        (distribution["species_id"] == "SpA") & (distribution["subfamily"] == "S1")
    ].iloc[0]
    assert missing_cell["gene_count"] == 1
    assert missing_cell["within_species_fraction"] == pytest.approx(0.5)
    assert not distribution.duplicated(["species_id", "subfamily"]).any()
    assert distribution.groupby("species_id")["gene_count"].sum().to_dict() == {
        "SpA": 2,
        "SpB": 2,
    }
    assert distribution.groupby("species_id")["within_species_fraction"].sum().to_dict() == {
        "SpA": pytest.approx(1.0),
        "SpB": pytest.approx(1.0),
    }


def test_pan_family_summaries_keep_gene_and_hog_denominators_separate(
    members: pd.DataFrame,
    membership: pd.DataFrame,
    classification: pd.DataFrame,
) -> None:
    summaries = build_pan_family_summaries(
        classification,
        membership,
        members,
        species_ids=["SpA", "SpB"],
    )

    overall = summaries["class_summary"].set_index(["counting_unit", "pan_family_class"])
    assert overall.loc[("HOG", "Core"), "count"] == 1
    assert overall.loc[("HOG", "Shell"), "count"] == 2
    assert overall.loc[("GENE", "Core"), "count"] == 2
    assert overall.loc[("GENE", "Shell"), "count"] == 2
    assert overall.loc[("HOG", "Core"), "fraction"] == pytest.approx(1 / 3)
    assert overall.loc[("GENE", "Core"), "fraction"] == pytest.approx(0.5)

    species = summaries["species_class_summary"]
    assert not species.duplicated(["species_id", "pan_family_class"]).any()
    assert set(species["pan_family_class"]) == {"Core", "Soft-core", "Shell", "Cloud"}
    assert species.groupby("species_id")["gene_count"].sum().to_dict() == {
        "SpA": 2,
        "SpB": 2,
    }
    assert species.groupby("species_id")["gene_fraction"].sum().to_dict() == {
        "SpA": pytest.approx(1.0),
        "SpB": pytest.approx(1.0),
    }

    subfamily = summaries["subfamily_class_summary"]
    assert not subfamily.duplicated(["subfamily", "pan_family_class"]).any()
    assert len(subfamily) == 8


def test_duplication_summaries_report_species_subfamily_and_pan_class(
    members: pd.DataFrame,
    membership: pd.DataFrame,
    classification: pd.DataFrame,
) -> None:
    modes = pd.DataFrame(
        {
            "stable_id": ["A1", "A2", "B1", "B2"],
            "species_id": ["SpA", "SpA", "SpB", "SpB"],
            "duplication_mode": ["WGD", "Tandem", "WGD", "Unclassified"],
        }
    )

    summary = build_duplication_summaries(modes, members, membership, classification)

    assert set(summary["stratification"]) == {"SPECIES", "SUBFAMILY", "PAN_CLASS"}
    assert not summary.duplicated(["stratification", "stratum", "duplication_mode"]).any()
    species = summary.loc[summary["stratification"] == "SPECIES"]
    assert species.groupby("stratum")["gene_count"].sum().to_dict() == {
        "SpA": 2,
        "SpB": 2,
    }
    assert species.groupby("stratum")["within_stratum_fraction"].sum().to_dict() == {
        "SpA": pytest.approx(1.0),
        "SpB": pytest.approx(1.0),
    }


def test_kaks_annotation_marks_conflicts_instead_of_forcing_a_group(
    members: pd.DataFrame,
    membership: pd.DataFrame,
    classification: pd.DataFrame,
) -> None:
    modes = pd.DataFrame(
        {
            "stable_id": ["A1", "A2", "B1", "B2"],
            "duplication_mode": ["WGD", "Tandem", "WGD", "Unclassified"],
        }
    )
    pairs = pd.DataFrame(
        {
            "pair_id": ["p1", "p2"],
            "stable_id_1": ["A1", "A1"],
            "stable_id_2": ["B1", "B2"],
            "Ka": [0.1, 0.2],
            "Ks": [0.5, 0.4],
            "Ka_Ks": [0.2, 0.5],
            "qc_status": ["PASS", "PASS"],
        }
    )

    annotated = annotate_kaks_pairs(pairs, members, membership, classification, modes)

    same = annotated.set_index("pair_id").loc["p1"]
    assert same["subfamily_stratum"] == "S1"
    assert same["group_stratum"] == "Mixed"
    assert same["pan_class_stratum"] == "Core"
    assert same["duplication_mode_stratum"] == "WGD"
    mixed = annotated.set_index("pair_id").loc["p2"]
    assert mixed["subfamily_stratum"] == "Mixed"
    assert mixed["pan_class_stratum"] == "Mixed"
    assert mixed["duplication_mode_stratum"] == "Mixed"

    summary = summarize_kaks_strata(annotated)
    assert set(summary["metric"]) == {"Ka", "Ks", "Ka_Ks"}
    assert set(summary["stratification"]) == {
        "SUBFAMILY",
        "GROUP",
        "PAN_CLASS",
        "DUPLICATION_MODE",
    }
    assert {"n_pairs", "median", "q1", "q3", "minimum", "maximum"}.issubset(summary.columns)
