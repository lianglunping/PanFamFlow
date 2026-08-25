import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from traceability_provenance_utils import build_id_chain_audit
from workflow_utils import save_table

audit = build_id_chain_audit(
    list(snakemake.input.maps),
    snakemake.input.family,
    snakemake.input.membership,
    separator=str(snakemake.params.separator),
)
save_table(audit, snakemake.output.tsv, snakemake.output.xlsx)
