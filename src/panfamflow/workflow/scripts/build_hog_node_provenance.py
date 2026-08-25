import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from traceability_provenance_utils import build_hog_node_provenance
from workflow_utils import save_table

provenance = build_hog_node_provenance(
    snakemake.input.classification,
    snakemake.input.result_dir,
)
save_table(provenance, snakemake.output.tsv, snakemake.output.xlsx)
