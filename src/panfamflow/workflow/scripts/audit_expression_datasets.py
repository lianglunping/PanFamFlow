import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

from expression_de_utils import audit_de_inputs
from workflow_utils import read_delimited_table, save_table

counts = read_delimited_table(snakemake.input.counts)
design = read_delimited_table(snakemake.input.design, dtype=str)
contrasts = read_delimited_table(snakemake.input.contrasts)
audited = audit_de_inputs(
    counts,
    design,
    contrasts,
    min_replicates=int(snakemake.params.min_replicates),
)

save_table(audited.counts, snakemake.output.counts, snakemake.output.counts_xlsx)
save_table(audited.design, snakemake.output.design, snakemake.output.design_xlsx)
save_table(
    audited.contrast_audit,
    snakemake.output.contrasts,
    snakemake.output.contrasts_xlsx,
)
save_table(
    audited.dataset_audit,
    snakemake.output.datasets,
    snakemake.output.datasets_xlsx,
)
save_table(audited.sample_qc, snakemake.output.sample_qc, snakemake.output.sample_qc_xlsx)
