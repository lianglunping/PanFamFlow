import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import numpy as np
import pandas as pd
from expression_summary_utils import (
    attach_pan_classes,
    build_descriptive_summaries,
    save_descriptive_expression_outputs,
    save_expression_heatmap,
    scale_expression_matrix,
    validate_sample_metadata,
)
from workflow_utils import read_delimited_table, resolve_column, save_table, save_workbook

members = pd.read_csv(snakemake.input.members, sep="\t")
source = read_delimited_table(snakemake.input.matrix)
separator = str(snakemake.params.separator)

stable_column = resolve_column(source, ["stable_id", "protein_id"], required=False)
if stable_column is None:
    species_column = resolve_column(source, ["species_id", "species"], required=False)
    gene_column = resolve_column(source, ["gene_id", "gene"], required=False)
    if species_column and gene_column:
        source["stable_id"] = [
            f"{species}{separator}{gene}"
            for species, gene in zip(
                source[species_column].astype(str), source[gene_column].astype(str), strict=True
            )
        ]
    else:
        first_column = source.columns[0]
        raw_ids = source[first_column].astype(str)
        gene_to_stable = members.groupby("gene_id")["stable_id"].agg(list).to_dict()
        ambiguous = [gene for gene in raw_ids if len(gene_to_stable.get(gene, [])) != 1]
        if ambiguous:
            raise ValueError(
                "Expression row IDs are not stable IDs and are not uniquely mappable gene IDs. "
                f"Examples: {ambiguous[:10]}"
            )
        source["stable_id"] = [gene_to_stable[gene][0] for gene in raw_ids]
else:
    source = source.rename(columns={stable_column: "stable_id"})

metadata_columns = {
    "stable_id",
    "species_id",
    "species",
    "gene_id",
    "gene",
    "transcript_id",
    "protein_id",
}
sample_columns = [
    column for column in source.columns if str(column).lower() not in metadata_columns
]
if not sample_columns:
    raise ValueError("Expression matrix contains no sample columns.")
for column in sample_columns:
    source[column] = pd.to_numeric(source[column], errors="raise")
observed_values = source[sample_columns].to_numpy(dtype=float)
invalid_values = np.isinf(observed_values) | (observed_values < 0)
if invalid_values.any():
    raise ValueError("Imported expression values must be finite and non-negative when present")
if source["stable_id"].duplicated().any():
    duplicates = source.loc[source["stable_id"].duplicated(), "stable_id"].astype(str).tolist()
    raise ValueError(f"Expression matrix has duplicate stable IDs: {duplicates[:10]}")

family_ids = set(members["stable_id"].astype(str))
matrix = source.loc[
    source["stable_id"].astype(str).isin(family_ids), ["stable_id", *sample_columns]
]
member_columns = [
    column
    for column in ["stable_id", "species_id", "gene_id", "group", "subfamily"]
    if column in members.columns
]
matrix = members[member_columns].merge(matrix, on="stable_id", how="left", validate="one_to_one")
sample_metadata = validate_sample_metadata(
    sample_columns, getattr(snakemake.params, "sample_metadata", None)
)
metadata_is_configured = sample_metadata["metadata_status"].eq("PASS").all()
if metadata_is_configured:
    sample_species = sample_metadata.set_index("sample_id")["sample_species_id"].to_dict()
    for _, row in matrix.iterrows():
        species_id = str(row["species_id"])
        for sample_id in sample_columns:
            value = row[sample_id]
            if str(sample_species[sample_id]) != species_id and pd.notna(value):
                raise ValueError(
                    f"Expression value was supplied for non-applicable species/sample cell: "
                    f"{row['stable_id']}, {sample_id}. Use an empty value, not zero."
                )
    status_values: list[str] = []
    for _, row in matrix.iterrows():
        applicable = [
            sample_id
            for sample_id in sample_columns
            if str(sample_species[sample_id]) == str(row["species_id"])
        ]
        available = int(row[applicable].notna().sum()) if applicable else 0
        status_values.append(
            "NOT_APPLICABLE"
            if not applicable
            else "MISSING"
            if available == 0
            else "PARTIAL_MISSING"
            if available < len(applicable)
            else "AVAILABLE"
        )
    matrix["expression_data_status"] = status_values
else:
    available_counts = matrix[sample_columns].notna().sum(axis=1)
    matrix["expression_data_status"] = np.select(
        [available_counts.eq(0), available_counts.lt(len(sample_columns))],
        ["MISSING", "PARTIAL_MISSING"],
        default="AVAILABLE",
    )
long = matrix.melt(
    id_vars=[*member_columns, "expression_data_status"],
    value_vars=sample_columns,
    var_name="sample_id",
    value_name="expression_value",
)
long = long.merge(sample_metadata, on="sample_id", how="left", validate="many_to_one")
applicable = long["sample_species_id"].isna() | long["species_id"].astype(str).eq(
    long["sample_species_id"].astype(str)
)
observed = long["expression_value"].notna() & applicable
long["measurement_status"] = np.select(
    [~applicable, observed], ["NOT_APPLICABLE", "OBSERVED"], default="MISSING_IN_INPUT"
)
long["detected"] = pd.Series(pd.NA, index=long.index, dtype="boolean")
long.loc[observed, "detected"] = (
    long.loc[observed, "expression_value"] >= float(snakemake.params.min_tpm_detected)
).astype(bool)
summary = long.groupby(["stable_id", "species_id", "gene_id"], as_index=False).agg(
    samples_available=("expression_value", "count"),
    expression_detected_samples=("detected", "sum"),
    expression_detected_fraction=("detected", "mean"),
    median_expression=("expression_value", "median"),
    max_expression=("expression_value", "max"),
)
summary["expression_detected_samples"] = summary["expression_detected_samples"].astype("Int64")
long = attach_pan_classes(
    long,
    getattr(snakemake.params, "pan_membership", None),
    getattr(snakemake.params, "pan_classification", None),
)
gene_condition, stratified_summary = build_descriptive_summaries(long)
save_table(matrix, snakemake.output.matrix)
save_table(long, snakemake.output.long)
save_table(summary, snakemake.output.summary)
save_workbook({"matrix": matrix, "long": long, "summary": summary}, snakemake.output.xlsx)
save_descriptive_expression_outputs(
    long,
    gene_condition,
    stratified_summary,
    sample_metadata,
    snakemake.output,
    int(snakemake.params.png_dpi),
)

scaled = scale_expression_matrix(
    matrix,
    sample_columns,
    str(snakemake.params.heatmap_transform),
)
save_expression_heatmap(
    scaled,
    sample_columns,
    table_tsv=snakemake.output.scaled,
    plot_pdf=snakemake.output.plot_pdf,
    plot_png=snakemake.output.plot_png,
    png_dpi=int(snakemake.params.png_dpi),
)
