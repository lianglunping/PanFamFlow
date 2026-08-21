from __future__ import annotations

import pandas as pd
import pytest

from panfamflow.workflow.scripts.kaks_statistics import build_cluster_source


def test_kaks_cluster_source_collapses_dependent_pairs_before_inference() -> None:
    pairs = pd.DataFrame(
        {
            "pair_id": ["p1", "p2", "p3", "p4"],
            "group_id": ["HOG1", "HOG1", "HOG2", "HOG3"],
            "subfamily_stratum": ["A", "A", "A", "B"],
            "Ka_Ks": [0.2, 0.4, 0.8, 1.2],
            "qc_status": ["PASS"] * 4,
        }
    )

    source = build_cluster_source(
        pairs,
        scope="SUBFAMILY",
        stratum_columns=["subfamily_stratum"],
    )

    assert source.shape[0] == 3
    hog1 = source.loc[source["cluster_id"].eq("HOG1")].iloc[0]
    assert hog1["cluster_median_ka_ks"] == pytest.approx(0.3)
    assert hog1["n_pairs"] == 2
    assert source["analysis_unit"].eq("PAIR_CLUSTER_MEDIAN").all()
    assert source["interpretation_flag"].eq("PAIRWISE_KAKS_NOT_PROOF_OF_POSITIVE_SELECTION").all()
