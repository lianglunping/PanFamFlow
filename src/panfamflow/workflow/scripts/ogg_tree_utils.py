"""Build auditable OGG species-tree and presence/absence clustering objects."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from Bio import Phylo
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist, squareform


def find_orthofinder_species_tree(result_dir: str | Path) -> Path:
    """Return the unique rooted OrthoFinder species-tree path, failing closed."""

    root = Path(result_dir)
    preferred = root / "Species_Tree" / "SpeciesTree_rooted.txt"
    if preferred.is_file():
        return preferred
    candidates = sorted(root.rglob("SpeciesTree_rooted.txt"))
    if not candidates:
        raise FileNotFoundError(
            f"No OrthoFinder Species_Tree/SpeciesTree_rooted.txt was found under {root}"
        )
    if len(candidates) > 1:
        raise RuntimeError(
            "Multiple OrthoFinder rooted species trees were found; the result directory "
            f"is ambiguous: {', '.join(str(path) for path in candidates)}"
        )
    return candidates[0]


def validate_species_tree_tips(tree_path: str | Path, species_ids: list[str]) -> list[str]:
    """Require exact closure between configured species and terminal tree labels."""

    if len(species_ids) != len(set(species_ids)):
        raise ValueError("Configured species IDs are not unique.")
    tree = Phylo.read(str(tree_path), "newick")
    observed = sorted(str(tip.name or "").strip() for tip in tree.get_terminals())
    expected = sorted(species_ids)
    if not all(observed):
        raise ValueError("The OrthoFinder species tree contains an unnamed terminal tip.")
    if observed != expected:
        missing = sorted(set(expected).difference(observed))
        unexpected = sorted(set(observed).difference(expected))
        raise ValueError(
            "OrthoFinder species-tree tips do not close against configured species; "
            f"missing={missing}, unexpected={unexpected}"
        )
    return observed


def build_presence_absence_distances(
    presence: pd.DataFrame,
    species_ids: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Return pairwise Jaccard evidence, linkage rows and the linkage matrix."""

    required = {"HOG_ID", *species_ids}
    missing = sorted(required.difference(presence.columns))
    if missing:
        raise ValueError("Presence/absence matrix is missing columns: " + ", ".join(missing))
    if len(species_ids) < 2:
        raise ValueError("OGG presence/absence clustering requires at least two species.")
    if presence["HOG_ID"].astype(str).duplicated().any():
        raise ValueError("Presence/absence matrix contains duplicate HOG_ID values.")

    matrix = presence.set_index("HOG_ID")[species_ids].apply(pd.to_numeric, errors="raise")
    values = matrix.to_numpy(dtype=float).T
    if not np.isin(values, [0.0, 1.0]).all():
        raise ValueError("OGG presence/absence values must be binary 0/1.")
    condensed = pdist(values, metric="jaccard")
    if not np.isfinite(condensed).all():
        raise ValueError("Jaccard distances are undefined for the supplied OGG matrix.")
    distance_matrix = squareform(condensed)

    distance_rows: list[dict[str, Any]] = []
    for left_index, left_species in enumerate(species_ids):
        left = values[left_index].astype(bool)
        for right_index in range(left_index + 1, len(species_ids)):
            right_species = species_ids[right_index]
            right = values[right_index].astype(bool)
            distance_rows.append(
                {
                    "species_a": left_species,
                    "species_b": right_species,
                    "n_ogg": int(values.shape[1]),
                    "intersection_ogg": int(np.logical_and(left, right).sum()),
                    "union_ogg": int(np.logical_or(left, right).sum()),
                    "jaccard_distance": float(distance_matrix[left_index, right_index]),
                    "distance_method": "JACCARD_BINARY_OGG_PRESENCE_ABSENCE",
                }
            )

    linkage_matrix = linkage(condensed, method="average")
    linkage_rows = pd.DataFrame(
        linkage_matrix,
        columns=["left_cluster", "right_cluster", "distance", "cluster_size"],
    )
    linkage_rows.insert(0, "step", np.arange(1, len(linkage_rows) + 1))
    linkage_rows["linkage_method"] = "AVERAGE"
    linkage_rows["object_type"] = "NON_PHYLOGENETIC_CLUSTERING"
    return pd.DataFrame(distance_rows), linkage_rows, linkage_matrix


def write_ogg_tree_objects(
    *,
    result_dir: str | Path,
    presence: pd.DataFrame,
    species_ids: list[str],
    outputs: dict[str, str | Path],
    png_dpi: int,
) -> dict[str, pd.DataFrame]:
    """Write both tree-like objects and their machine-readable truth contract."""

    species_tree_source = find_orthofinder_species_tree(result_dir)
    observed_tips = validate_species_tree_tips(species_tree_source, species_ids)
    source_bytes = species_tree_source.read_bytes()
    Path(outputs["species_tree_newick"]).write_bytes(source_bytes)

    tree = Phylo.read(str(species_tree_source), "newick")
    figure, axis = plt.subplots(figsize=(8.0, max(4.8, 0.42 * len(species_ids) + 1.8)))
    Phylo.draw(tree, axes=axis, do_show=False, show_confidence=True)
    axis.set_title("OrthoFinder species phylogeny")
    axis.set_xlabel("Branch length")
    figure.tight_layout()
    figure.savefig(outputs["species_tree_pdf"], facecolor="white")
    figure.savefig(outputs["species_tree_png"], dpi=png_dpi, facecolor="white")
    plt.close(figure)

    distances, linkage_rows, linkage_matrix = build_presence_absence_distances(
        presence,
        species_ids,
    )
    figure, axis = plt.subplots(figsize=(8.0, max(4.8, 0.42 * len(species_ids) + 1.8)))
    dendrogram(linkage_matrix, labels=species_ids, orientation="right", ax=axis)
    axis.set_title("OGG presence/absence clustering dendrogram (not a phylogenetic tree)")
    axis.set_xlabel("Jaccard distance")
    axis.set_ylabel("Species")
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(False)
    figure.tight_layout()
    figure.savefig(outputs["clustering_pdf"], facecolor="white")
    figure.savefig(outputs["clustering_png"], dpi=png_dpi, facecolor="white")
    plt.close(figure)

    provenance = pd.DataFrame(
        [
            {
                "object_id": "ORTHOFINDER_SPECIES_PHYLOGENY",
                "object_type": "PHYLOGENETIC_TREE",
                "source_path": str(species_tree_source.relative_to(Path(result_dir))),
                "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "configured_tip_count": len(species_ids),
                "observed_tip_count": len(observed_tips),
                "tip_closure_status": "PASS",
                "method": "ORTHOFINDER_ROOTED_SPECIES_TREE",
                "interpretation_boundary": "PHYLOGENETIC_TREE_NOT_OGG_CLUSTERING",
            },
            {
                "object_id": "OGG_PRESENCE_ABSENCE_CLUSTERING",
                "object_type": "NON_PHYLOGENETIC_CLUSTERING",
                "source_path": "family_presence_absence.tsv",
                "source_sha256": "RECORDED_IN_RESULT_MANIFEST",
                "configured_tip_count": len(species_ids),
                "observed_tip_count": len(species_ids),
                "tip_closure_status": "PASS",
                "method": "JACCARD_BINARY_PLUS_AVERAGE_LINKAGE",
                "interpretation_boundary": "NOT_A_PHYLOGENETIC_TREE",
            },
        ]
    )
    contract = pd.DataFrame(
        [
            {
                "object_id": "ORTHOFINDER_SPECIES_PHYLOGENY",
                "display_name": "OrthoFinder species phylogeny",
                "is_phylogenetic": True,
                "answers": "SPECIES_RELATIONSHIP_UNDER_ORTHOFINDER_MODEL",
                "must_not_be_called": "OGG_PRESENCE_ABSENCE_CLUSTERING",
            },
            {
                "object_id": "OGG_PRESENCE_ABSENCE_CLUSTERING",
                "display_name": "OGG presence/absence clustering dendrogram",
                "is_phylogenetic": False,
                "answers": "SIMILARITY_OF_TARGET_FAMILY_OGG_CONTENT",
                "must_not_be_called": "SPECIES_TREE_OR_PHYLOGENY",
            },
        ]
    )

    distances.to_csv(outputs["distances"], sep="\t", index=False)
    linkage_rows.to_csv(outputs["linkage"], sep="\t", index=False)
    provenance.to_csv(outputs["provenance"], sep="\t", index=False)
    contract.to_csv(outputs["contract"], sep="\t", index=False)
    return {
        "distances": distances,
        "linkage": linkage_rows,
        "provenance": provenance,
        "contract": contract,
    }
