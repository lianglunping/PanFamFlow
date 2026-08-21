import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from pathlib import Path

import pandas as pd
from Bio import Phylo
from comparative_phylogeny_utils import build_comparative_panel
from phylogeny_figure_utils import render_family_tree
from workflow_utils import (
    copy_atomic,
    executable_version,
    read_fasta,
    run_command,
    save_table,
    write_fasta,
    write_text_atomic,
)


def mafft_command(mode: str) -> list[str]:
    if mode == "linsi":
        return ["mafft", "--localpair", "--maxiterate", "1000"]
    if mode == "ginsi":
        return ["mafft", "--globalpair", "--maxiterate", "1000"]
    if mode == "einsi":
        return ["mafft", "--genafpair", "--maxiterate", "1000"]
    return ["mafft", "--auto"]


members = pd.read_csv(snakemake.input.members, sep="\t", dtype=str)
registry_path = Path(snakemake.input.registry)
registry = pd.read_csv(registry_path, sep="\t", dtype=str, keep_default_na=False)
sequences, selection, provenance = build_comparative_panel(
    members,
    read_fasta(snakemake.input.proteins),
    registry,
    strategy=str(snakemake.params.selection_strategy),
    seed=int(snakemake.params.seed),
    registry_root=registry_path.parent,
)
minimum = int(snakemake.params.min_sequences)
if len(sequences) < minimum:
    raise RuntimeError(
        f"Comparative phylogeny requires at least {minimum} sequences; observed {len(sequences)}."
    )

save_table(selection, snakemake.output.selection)
save_table(provenance, snakemake.output.provenance)
write_fasta(sequences, snakemake.output.fasta)

command = mafft_command(str(snakemake.params.mafft_mode))
command.extend(["--thread", str(snakemake.threads), str(snakemake.output.fasta)])
run_command(command, stdout_path=snakemake.output.alignment, stderr_path=snakemake.log.mafft)
run_command(
    [
        "clipkit",
        str(snakemake.output.alignment),
        "-m",
        str(snakemake.params.trim_mode),
        "-o",
        str(snakemake.output.trimmed),
    ],
    stdout_path=snakemake.log.clipkit_stdout,
    stderr_path=snakemake.log.clipkit_stderr,
)

work_dir = Path(snakemake.params.work_dir)
work_dir.mkdir(parents=True, exist_ok=True)
prefix = work_dir / "comparative"
iqtree_executable, version = executable_version(["iqtree3", "iqtree2", "iqtree"], ["--version"])
iqtree_command = [
    iqtree_executable,
    "-s",
    str(snakemake.output.trimmed),
    "-m",
    str(snakemake.params.model),
    "-T",
    str(snakemake.threads),
    "--seed",
    str(snakemake.params.seed),
    "--prefix",
    str(prefix),
]
bootstrap = int(snakemake.params.ultrafast_bootstrap)
sh_alrt = int(snakemake.params.sh_alrt)
if bootstrap:
    iqtree_command.extend(["-B", str(bootstrap)])
if sh_alrt:
    iqtree_command.extend(["--alrt", str(sh_alrt)])
run_command(
    iqtree_command,
    stdout_path=snakemake.log.iqtree_stdout,
    stderr_path=snakemake.log.iqtree_stderr,
)
tree_source = Path(f"{prefix}.treefile")
if not tree_source.is_file():
    raise FileNotFoundError(f"IQ-TREE did not produce {tree_source}; executable was {version}")
copy_atomic(tree_source, snakemake.output.tree)
report_source = Path(f"{prefix}.iqtree")
if report_source.is_file():
    copy_atomic(report_source, snakemake.output.report)
else:
    write_text_atomic(
        f"IQ-TREE executable: {iqtree_executable}\nVersion: {version}\n",
        snakemake.output.report,
    )

tree = Phylo.read(str(snakemake.output.tree), "newick")
tips = [str(tip.name or "") for tip in tree.get_terminals()]
selected = selection.set_index("stable_id", drop=False)
if not all(tips) or set(tips) != set(selected.index) or len(tips) != len(selected):
    raise ValueError("Comparative tree tips do not reconcile one-to-one with panel selection.")
tip_order = {stable_id: index for index, stable_id in enumerate(tips)}
tip_annotations = selection.copy()
tip_annotations["tree_tip_order"] = tip_annotations["stable_id"].map(tip_order)
tip_annotations["tree_tip_status"] = "MATCHED_COMPARATIVE_PANEL"
tip_annotations["tree_scope"] = "TARGET_FAMILY_WITH_EXTERNAL_CONTEXT_NOT_SPECIES_TREE"
tip_annotations = tip_annotations.sort_values("tree_tip_order").reset_index(drop=True)
save_table(tip_annotations, snakemake.output.tip_annotations)
outgroup_ids = tip_annotations.loc[tip_annotations["outgroup"].astype(bool), "stable_id"].tolist()
render_family_tree(
    snakemake.output.tree,
    tip_annotations,
    str(Path(snakemake.output.figure_pdf).with_suffix("")),
    png_dpi=int(snakemake.params.png_dpi),
    title="Representative target-family tree with external context (not a species tree)",
    outgroup_ids=outgroup_ids,
)
