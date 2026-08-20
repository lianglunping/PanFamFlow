import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from workflow_utils import resolve_column, save_table, save_workbook

members = pd.read_csv(snakemake.input.members, sep="\t")
family_ids = set(members["stable_id"].astype(str))
map_frames = [pd.read_csv(path, sep="\t") for path in snakemake.input.maps]
mapping = pd.concat(map_frames, ignore_index=True)
sample_ids = [str(item) for item in snakemake.params.sample_ids]
sample_species_ids = [str(item) for item in snakemake.params.sample_species_ids]
if not (len(sample_ids) == len(sample_species_ids) == len(snakemake.input.abundance)):
    raise ValueError(
        "StringTie abundance files, sample IDs and sample species IDs have different lengths"
    )
if len(sample_ids) != len(set(sample_ids)):
    raise ValueError("StringTie sample IDs must be unique")

stable_lookup_by_species: dict[str, dict[str, str]] = {}
for species_id, species_mapping in mapping.groupby("species_id", sort=False):
    gene_ids = species_mapping["gene_id"].astype(str)
    duplicated = sorted(gene_ids[gene_ids.duplicated(keep=False)].unique())
    if duplicated:
        raise ValueError(
            f"Canonical mapping for {species_id} contains duplicate gene IDs: "
            + ", ".join(duplicated[:10])
        )
    stable_lookup_by_species[str(species_id)] = dict(
        zip(gene_ids, species_mapping["stable_id"].astype(str), strict=True)
    )

observed_by_sample: dict[str, set[str]] = {}
values_by_sample: dict[str, pd.Series] = {}
for sample_id, species_id, path in zip(
    sample_ids, sample_species_ids, snakemake.input.abundance, strict=True
):
    if species_id not in stable_lookup_by_species:
        raise ValueError(f"No canonical ID mapping was found for sample species {species_id!r}")
    table = pd.read_csv(path, sep="\t")
    gene_column = resolve_column(table, ["Gene ID", "gene_id", "gene"])
    tpm_column = resolve_column(table, ["TPM", "tpm"])
    table["stable_id"] = table[gene_column].astype(str).map(stable_lookup_by_species[species_id])
    table = table.dropna(subset=["stable_id"])
    table[tpm_column] = pd.to_numeric(table[tpm_column], errors="raise")
    if (
        table[tpm_column].isna().any()
        or (~np.isfinite(table[tpm_column].to_numpy(dtype=float))).any()
        or (table[tpm_column] < 0).any()
    ):
        raise ValueError(f"StringTie TPM values must be finite and non-negative: {path}")
    values = table.groupby("stable_id")[tpm_column].sum().astype(float)
    values = values.loc[values.index.astype(str).isin(family_ids)]
    values.name = sample_id
    values_by_sample[sample_id] = values
    observed_by_sample[sample_id] = set(values.index.astype(str))

wide = members[["stable_id", "species_id", "gene_id", "subfamily"]].copy()
wide["stable_id"] = wide["stable_id"].astype(str)
wide["species_id"] = wide["species_id"].astype(str)
if wide["stable_id"].duplicated().any():
    raise ValueError("Family members contain duplicate stable IDs")
for sample_id, sample_species_id in zip(sample_ids, sample_species_ids, strict=True):
    applicable = wide["species_id"].eq(sample_species_id)
    wide[sample_id] = np.nan
    mapped = wide.loc[applicable, "stable_id"].map(values_by_sample[sample_id])
    wide.loc[applicable, sample_id] = mapped.fillna(0.0).astype(float)

long = wide.melt(
    id_vars=["stable_id", "species_id", "gene_id", "subfamily"],
    value_vars=sample_ids,
    var_name="sample_id",
    value_name="expression_value",
)
sample_species_lookup = dict(zip(sample_ids, sample_species_ids, strict=True))
long["sample_species_id"] = long["sample_id"].map(sample_species_lookup)
applicable = long["species_id"].astype(str).eq(long["sample_species_id"].astype(str))
measured = pd.Series(
    [
        stable_id in observed_by_sample[sample_id]
        for stable_id, sample_id in zip(long["stable_id"], long["sample_id"], strict=True)
    ],
    index=long.index,
)
long["measurement_status"] = np.select(
    [~applicable, measured],
    ["NOT_APPLICABLE", "MEASURED"],
    default="ASSAYED_ZERO",
)
long["detected"] = pd.Series(pd.NA, index=long.index, dtype="boolean")
long.loc[applicable, "detected"] = (
    long.loc[applicable, "expression_value"] >= float(snakemake.params.min_tpm_detected)
).astype(bool)
long["measured_sample"] = long["measurement_status"].eq("MEASURED")
long["assayed_zero_sample"] = long["measurement_status"].eq("ASSAYED_ZERO")

summary = long.groupby(["stable_id", "species_id", "gene_id"], as_index=False).agg(
    samples_available=("expression_value", "count"),
    expression_detected_samples=("detected", "sum"),
    expression_detected_fraction=("detected", "mean"),
    measured_samples=("measured_sample", "sum"),
    assayed_zero_samples=("assayed_zero_sample", "sum"),
    median_expression=("expression_value", "median"),
    max_expression=("expression_value", "max"),
)
summary["expression_detected_samples"] = summary["expression_detected_samples"].astype("Int64")
long_output = long.drop(columns=["measured_sample", "assayed_zero_sample"])
save_table(wide, snakemake.output.matrix)
save_table(long_output, snakemake.output.long)
save_table(summary, snakemake.output.summary)
save_workbook({"matrix": wide, "long": long_output, "summary": summary}, snakemake.output.xlsx)

values = wide[sample_ids].to_numpy(dtype=float)
transformed = np.log2(values + 1.0)
if str(snakemake.params.heatmap_transform) == "log2_tpm1_zscore":
    valid = np.isfinite(transformed)
    counts = valid.sum(axis=1, keepdims=True)
    means = np.divide(
        np.nansum(transformed, axis=1, keepdims=True),
        counts,
        out=np.zeros((transformed.shape[0], 1), dtype=float),
        where=counts > 0,
    )
    centered = transformed - means
    variance = np.divide(
        np.nansum(centered**2, axis=1, keepdims=True),
        counts,
        out=np.zeros((transformed.shape[0], 1), dtype=float),
        where=counts > 0,
    )
    sd = np.sqrt(variance)
    sd[(sd == 0) | ~np.isfinite(sd)] = 1.0
    transformed = centered / sd
    transformed[~valid] = np.nan
fig_height = max(4.8, min(18.0, 0.18 * max(1, wide.shape[0])))
fig, axis = plt.subplots(figsize=(max(7.0, 0.35 * len(sample_ids)), fig_height))
cmap = plt.get_cmap("viridis").with_extremes(bad="#d9d9d9")
image = axis.imshow(
    np.ma.masked_invalid(transformed),
    aspect="auto",
    interpolation="nearest",
    cmap=cmap,
)
axis.set_xticks(range(len(sample_ids)), sample_ids, rotation=45, ha="right")
if wide.shape[0] <= 80:
    axis.set_yticks(range(wide.shape[0]), wide["stable_id"].astype(str), fontsize=6)
else:
    axis.set_yticks([])
fig.colorbar(image, ax=axis, label=str(snakemake.params.heatmap_transform))
fig.tight_layout()
fig.savefig(snakemake.output.plot_pdf)
fig.savefig(snakemake.output.plot_png, dpi=int(snakemake.params.png_dpi))
plt.close(fig)
