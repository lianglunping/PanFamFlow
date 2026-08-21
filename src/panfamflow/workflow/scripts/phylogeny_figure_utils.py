"""Auditable family-gene-tree annotation and rendering utilities."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from artifact_contract import save_figure_pair
from Bio import Phylo


def build_tip_annotations(tree_path: str | Path, members_path: str | Path) -> pd.DataFrame:
    """Require a one-to-one match between Newick tips and accepted family members."""

    tree = Phylo.read(str(tree_path), "newick")
    tips = [str(tip.name or "") for tip in tree.get_terminals()]
    if not all(tips) or len(tips) != len(set(tips)):
        raise ValueError("Family tree contains blank or duplicate tip identifiers.")
    members = pd.read_csv(members_path, sep="\t")
    if "stable_id" not in members:
        raise ValueError("Accepted family member table lacks stable_id.")
    if members["stable_id"].astype(str).duplicated().any():
        raise ValueError("Accepted family member table contains duplicate stable_id values.")
    accepted = set(members["stable_id"].astype(str))
    tree_ids = set(tips)
    if accepted != tree_ids:
        raise ValueError(
            "Family tree tips do not reconcile with accepted members: "
            f"missing tips={sorted(accepted - tree_ids)[:10]}, "
            f"extra tips={sorted(tree_ids - accepted)[:10]}"
        )
    columns = [
        column
        for column in (
            "stable_id",
            "species_id",
            "gene_id",
            "group",
            "subfamily",
            "family_membership_status",
        )
        if column in members
    ]
    annotations = members[columns].copy()
    tip_order = {stable_id: index for index, stable_id in enumerate(tips)}
    annotations["tree_tip_order"] = annotations["stable_id"].astype(str).map(tip_order)
    annotations["tree_tip_status"] = "MATCHED_ACCEPTED_MEMBER"
    annotations["tree_scope"] = "TARGET_FAMILY_GENE_TREE_NOT_SPECIES_TREE"
    return annotations.sort_values("tree_tip_order").reset_index(drop=True)


def render_family_tree(
    tree_path: str | Path,
    annotations: pd.DataFrame,
    output_stem: str | Path,
    *,
    png_dpi: int,
    title: str = "Target-family gene tree (not a species tree)",
    outgroup_ids: list[str] | None = None,
) -> None:
    """Render the accepted-member tree with support labels and explicit scope."""

    tree = Phylo.read(str(tree_path), "newick")
    if outgroup_ids:
        outgroups = [tree.find_any(name=stable_id) for stable_id in outgroup_ids]
        if any(clade is None for clade in outgroups):
            raise ValueError("One or more declared outgroups are absent from the tree.")
        tree.root_with_outgroup(*outgroups)
    label_lookup = annotations.set_index("stable_id", drop=False).to_dict(orient="index")

    def label(clade: object) -> str | None:
        name = str(getattr(clade, "name", "") or "")
        if not name or name not in label_lookup:
            return None
        record = label_lookup[name]
        suffix = " | ".join(
            str(record[column])
            for column in ("species_id", "subfamily", "group")
            if column in record and pd.notna(record[column])
        )
        return f"{name} | {suffix}" if suffix else name

    def branch_label(clade: object) -> str | None:
        confidence = getattr(clade, "confidence", None)
        if confidence is not None:
            return f"{float(confidence):g}"
        is_terminal = getattr(clade, "is_terminal", None)
        if callable(is_terminal) and not is_terminal():
            support = str(getattr(clade, "name", "") or "").strip()
            return support or None
        return None

    height = max(5.0, min(28.0, 0.28 * len(annotations) + 2.0))
    figure, axis = plt.subplots(figsize=(12.0, height))
    Phylo.draw(
        tree,
        axes=axis,
        do_show=False,
        label_func=label,
        branch_labels=branch_label,
    )
    axis.set_title(title)
    axis.set_xlabel("Substitutions per site")
    axis.grid(False)
    figure.tight_layout()
    save_figure_pair(figure, output_stem, png_dpi=png_dpi)
    plt.close(figure)
