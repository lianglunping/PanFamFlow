import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from traceability_provenance_utils import build_canonical_transcript_provenance
from workflow_utils import save_table

provenance = build_canonical_transcript_provenance(
    list(snakemake.input.maps),
    backend=str(snakemake.params.backend),
    method=str(snakemake.params.method),
    separator=str(snakemake.params.separator),
)
save_table(provenance, snakemake.output.tsv, snakemake.output.xlsx)
