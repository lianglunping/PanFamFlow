import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import pandas as pd
from workflow_utils import save_workbook

table = pd.read_csv(snakemake.input[0], sep="\t")
save_workbook({"data": table}, snakemake.output[0])
