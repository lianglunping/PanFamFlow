import sys
from pathlib import Path as _ScriptPath

sys.path.insert(0, str(_ScriptPath(snakemake.scriptdir)))

import html
import importlib.metadata
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from validate_deliverable_contract import evaluate_figure_contract
from workflow_utils import (
    project_relative_path,
    save_table,
    sha256_file,
    write_json,
    write_text_atomic,
)

results_dir = Path(snakemake.params.results_dir)
project_root = Path(str(snakemake.params.project_root)).resolve()
results_dir.mkdir(parents=True, exist_ok=True)
family_path = results_dir / "02_family" / "family_members.tsv"
if family_path.is_file():
    master = pd.read_csv(family_path, sep="\t")
else:
    master = pd.DataFrame(columns=["stable_id", "species_id", "gene_id"])


def merge_one(path: Path, columns: list[str] | None = None, suffix: str = "") -> None:
    global master
    if not path.is_file() or master.empty:
        return
    table = pd.read_csv(path, sep="\t")
    if "stable_id" not in table.columns:
        return
    if columns is not None:
        table = table[[column for column in columns if column in table.columns]]
    table = table.drop_duplicates("stable_id")
    overlapping = set(master.columns).intersection(table.columns).difference({"stable_id"})
    if overlapping:
        table = table.rename(columns={column: f"{column}{suffix}" for column in overlapping})
    master = master.merge(table, on="stable_id", how="left", validate="one_to_one")


merge_one(results_dir / "04_gene_structure" / "gene_structure_metrics.tsv", suffix="_structure")
merge_one(results_dir / "07_chromosome" / "chromosome_distribution.tsv", suffix="_chromosome")
merge_one(results_dir / "08_duplication" / "duplication_mode.tsv", suffix="_duplication")

membership_path = results_dir / "06_pan_family" / "family_hog_membership.tsv"
classification_path = results_dir / "06_pan_family" / "pan_family_classification.tsv"
if membership_path.is_file() and classification_path.is_file() and not master.empty:
    membership = pd.read_csv(membership_path, sep="\t")
    classification = pd.read_csv(classification_path, sep="\t")
    membership = membership.merge(classification, on="HOG_ID", how="left", validate="many_to_one")
    membership = membership.drop_duplicates("stable_id")
    master = master.merge(membership, on="stable_id", how="left", suffixes=("", "_pan_family"))

promoter_path = results_dir / "10_promoter" / "promoter_elements_per_gene.tsv"
if promoter_path.is_file() and not master.empty:
    promoter = pd.read_csv(promoter_path, sep="\t")
    promoter_total = (
        promoter.groupby("stable_id", as_index=False)
        .agg(
            cis_element_total=("element_count", "sum"),
            cis_element_major_classes=(
                "major_class",
                lambda values: ";".join(sorted(set(values.dropna().astype(str)))),
            ),
        )
        .drop_duplicates("stable_id")
    )
    master = master.merge(promoter_total, on="stable_id", how="left", validate="one_to_one")

merge_one(results_dir / "11_expression" / "expression_summary.tsv", suffix="_expression")

kaks_path = results_dir / "09_kaks" / "kaks_pairs.tsv"
if kaks_path.is_file() and not master.empty:
    kaks = pd.read_csv(kaks_path, sep="\t")
    required = {"stable_id_1", "stable_id_2", "Ka", "Ks", "Ka_Ks"}
    if required.issubset(kaks.columns):
        first = kaks[["stable_id_1", "Ka", "Ks", "Ka_Ks"]].rename(
            columns={"stable_id_1": "stable_id"}
        )
        second = kaks[["stable_id_2", "Ka", "Ks", "Ka_Ks"]].rename(
            columns={"stable_id_2": "stable_id"}
        )
        per_gene_kaks = (
            pd.concat([first, second], ignore_index=True)
            .groupby("stable_id", as_index=False)
            .agg(
                kaks_pair_count=("Ka_Ks", "count"),
                median_Ka=("Ka", "median"),
                median_Ks=("Ks", "median"),
                median_Ka_Ks=("Ka_Ks", "median"),
            )
        )
        master = master.merge(per_gene_kaks, on="stable_id", how="left", validate="one_to_one")

de_path = results_dir / "11_expression" / "deseq2_contrast_results.tsv"
if de_path.is_file() and not master.empty:
    de = pd.read_csv(de_path, sep="\t")
    de_summary = (
        de.assign(
            formal_de=de["deg_status"].astype(str).isin(["UP", "DOWN"]),
            formal_up=de["deg_status"].astype(str).eq("UP"),
            formal_down=de["deg_status"].astype(str).eq("DOWN"),
        )
        .groupby("stable_id", as_index=False)
        .agg(
            formal_de_contrast_count=("formal_de", "sum"),
            formal_up_contrast_count=("formal_up", "sum"),
            formal_down_contrast_count=("formal_down", "sum"),
            minimum_de_padj=("padj", "min"),
            maximum_absolute_de_log2fc=("log2FoldChange", lambda values: values.abs().max()),
        )
    )
    master = master.merge(de_summary, on="stable_id", how="left", validate="one_to_one")

save_table(master, snakemake.output.master_tsv, snakemake.output.master_xlsx)

package_rows = []
for distribution in (
    "panfamflow",
    "pandas",
    "numpy",
    "pydantic",
    "pyyaml",
    "openpyxl",
    "matplotlib",
):
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        version = "not-installed-in-report-environment"
    package_rows.append(
        {
            "software": distribution,
            "version": version,
            "source": "Python package metadata",
            "environment": "report",
        }
    )
software = pd.DataFrame(package_rows)
save_table(
    software,
    snakemake.output.software_versions,
    snakemake.output.software_versions_xlsx,
)

enabled_features: set[str] = set()
if snakemake.config.get("deliverables", {}).get("profile") == "pdf_md_complete":
    enabled_features.add("pdf_md_complete")
for section, activation in (
    ("comparative_panel", "comparative_panel.enabled"),
    ("domain_logo", "domain_logo.enabled"),
    ("synteny", "synteny.enabled"),
    ("differential_expression", "differential_expression.enabled"),
):
    if snakemake.config.get(section, {}).get("enabled", False):
        enabled_features.add(activation)

figure_contract = pd.read_csv(snakemake.params.figure_contract, sep="\t", dtype=str)
figure_rows = [
    evaluate_figure_contract(
        row,
        project_root=project_root,
        enabled_features=enabled_features,
    )
    for row in figure_contract.to_dict(orient="records")
]
figure_manifest = pd.DataFrame(figure_rows)
save_table(
    figure_manifest,
    snakemake.output.figure_manifest,
    snakemake.output.figure_manifest_xlsx,
)

table_rows: list[dict[str, Any]] = []
generated_sources = figure_manifest.loc[
    figure_manifest["status"].eq("GENERATED"), "source_table"
].drop_duplicates()
for relative_tsv in generated_sources:
    tsv = project_root / str(relative_tsv)
    xlsx = tsv.with_suffix(".xlsx")
    if not tsv.is_file() or not xlsx.is_file():
        raise RuntimeError(f"Formal table pair is incomplete: {tsv} / {xlsx}")
    tsv_table = pd.read_csv(tsv, sep="\t")
    xlsx_table = pd.read_excel(xlsx)
    if tsv_table.columns.tolist() != xlsx_table.columns.tolist():
        raise RuntimeError(f"Formal table columns differ between TSV and XLSX: {tsv}")
    if len(tsv_table) != len(xlsx_table):
        raise RuntimeError(f"Formal table row counts differ between TSV and XLSX: {tsv}")
    table_rows.append(
        {
            "table_id": tsv.stem,
            "tsv_path": str(tsv.relative_to(project_root)),
            "xlsx_path": str(xlsx.relative_to(project_root)),
            "rows": len(tsv_table),
            "columns": len(tsv_table.columns),
            "column_names": ";".join(tsv_table.columns.astype(str)),
            "tsv_sha256": sha256_file(tsv),
            "xlsx_sha256": sha256_file(xlsx),
            "status": "GENERATED",
            "parity_status": "PASS_ROWS_AND_COLUMNS",
        }
    )
table_manifest = pd.DataFrame(table_rows)
save_table(
    table_manifest,
    snakemake.output.table_manifest,
    snakemake.output.table_manifest_xlsx,
)

traceability = pd.read_csv(snakemake.params.requirement_traceability, sep="\t", dtype=str)
figure_status = figure_manifest.set_index("figure_id")["status"]
traceability["runtime_status"] = traceability.apply(
    lambda row: (
        str(figure_status.get(row["requirement_id"], "MISSING_FIGURE_REQUIREMENT"))
        if row["requirement_type"] == "PDF_FIGURE"
        else (
            "ARTIFACT_PRESENT_PENDING_B10"
            if (project_root / row["artifact"]).is_file()
            else "PENDING_B10_GATE"
        )
    ),
    axis=1,
)
save_table(
    traceability,
    snakemake.output.traceability,
    snakemake.output.traceability_xlsx,
)

session_text = (
    "\n".join(
        [
            f"Python={platform.python_version()}",
            f"platform={platform.platform()}",
            f"implementation={platform.python_implementation()}",
            f"selected_modules={snakemake.params.selected_modules}",
            f"enabled_features={','.join(sorted(enabled_features))}",
        ]
    )
    + "\n"
)
write_text_atomic(session_text, snakemake.output.session)

generated_at = datetime.now(UTC).isoformat()
run_info = {
    "project": snakemake.config.get("project", {}),
    "selected_modules": str(snakemake.params.selected_modules).split(","),
    "enabled_features": sorted(enabled_features),
    "generated_at_utc": generated_at,
    "config_path": snakemake.config.get("panfamflow_config_path"),
    "master_rows": int(master.shape[0]),
    "figure_status_counts": figure_manifest["status"].value_counts().to_dict(),
    "formal_table_count": len(table_manifest),
}
write_json(run_info, snakemake.output.run_info)

input_manifest = results_dir / "00_qc" / "input_manifest.json"
provenance = {
    "generated_at_utc": generated_at,
    "analysis_scope": snakemake.config.get("project", {}).get("analysis_scope"),
    "seed": snakemake.config.get("project", {}).get("seed"),
    "selected_modules": run_info["selected_modules"],
    "enabled_features": run_info["enabled_features"],
    "configuration": snakemake.config,
    "input_manifest_path": str(project_relative_path(input_manifest, project_root))
    if input_manifest.is_file()
    else None,
    "input_manifest_sha256": sha256_file(input_manifest) if input_manifest.is_file() else None,
    "figure_contract_sha256": sha256_file(snakemake.params.figure_contract),
    "traceability_contract_sha256": sha256_file(snakemake.params.requirement_traceability),
    "scientific_boundary": "ENGINEERING_COMPLETION_IS_NOT_BIOLOGICAL_VALIDATION",
}
write_json(provenance, snakemake.output.provenance)

excluded_manifest_paths = {
    Path(snakemake.output.index),
    Path(snakemake.output.manifest),
    Path(snakemake.output.manifest_xlsx),
}
manifest_rows: list[dict[str, Any]] = []
for path in sorted(results_dir.rglob("*")):
    if not path.is_file() or path in excluded_manifest_paths:
        continue
    manifest_rows.append(
        {
            "relative_path": str(path.relative_to(results_dir)),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "suffix": path.suffix.lower(),
        }
    )
manifest = pd.DataFrame(manifest_rows)
save_table(manifest, snakemake.output.manifest, snakemake.output.manifest_xlsx)

report_title = snakemake.params.title or snakemake.config.get("project", {}).get(
    "name", "PanFamFlow pan-gene-family report"
)
cards = [
    ("Family genes", str(master.shape[0])),
    ("Result files", str(manifest.shape[0])),
    ("Generated formal figures", str(figure_manifest["status"].eq("GENERATED").sum())),
    ("Selected modules", html.escape(str(snakemake.params.selected_modules))),
]
card_html = "".join(
    f'<div class="card"><div class="value">{value}</div><div>{label}</div></div>'
    for label, value in cards
)
plot_html = "".join(
    f'<figure><img src="../{html.escape(row["png_path"])}" '
    f'alt="{html.escape(row["figure_id"])}"><figcaption>{html.escape(row["figure_id"])} — '
    f"{html.escape(row['scientific_boundary'])}</figcaption></figure>"
    for row in figure_manifest.loc[figure_manifest["status"].eq("GENERATED")].to_dict(
        orient="records"
    )
)
table_html = "".join(
    f'<li><a href="../{html.escape(row["tsv_path"])}">{html.escape(row["table_id"])} TSV</a> · '
    f'<a href="../{html.escape(row["xlsx_path"])}">XLSX</a></li>'
    for row in table_manifest.to_dict(orient="records")
)
write_text_atomic(
    f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(str(report_title))}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 1200px; color: #222; line-height: 1.5; }}
h1, h2 {{ border-bottom: 1px solid #ddd; padding-bottom: .35rem; }}
.cards {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
.card {{ border: 1px solid #ddd; padding: 1rem; min-width: 180px; border-radius: 4px; }}
.value {{ font-size: 1.6rem; font-weight: bold; }}
.gallery {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1rem; }}
figure {{ margin: 0; border: 1px solid #ddd; padding: .7rem; }}
img {{ max-width: 100%; height: auto; }}
code {{ background: #f4f4f4; padding: .1rem .25rem; }}
</style>
</head>
<body>
<h1>{html.escape(str(report_title))}</h1>
<p>Generated by PanFamFlow for a target pan-gene-family analysis at {html.escape(generated_at)}. Engineering completion does not replace project-specific biological validation.</p>
<div class="cards">{card_html}</div>
<h2>Integrated master table</h2>
<p><a href="../{html.escape(str(Path(snakemake.output.master_tsv).relative_to(results_dir)))}">TSV</a> · <a href="../{html.escape(str(Path(snakemake.output.master_xlsx).relative_to(results_dir)))}">XLSX</a></p>
<h2>Formal figures</h2>
<div class="gallery">{plot_html or "<p>No generated formal figures are available for the selected profile.</p>"}</div>
<h2>Formal source tables</h2>
<ul>{table_html or "<li>No generated formal source tables are available.</li>"}</ul>
<h2>Audit bundle</h2>
<p><a href="figure_manifest.tsv">Figure manifest</a> · <a href="table_manifest.tsv">Table manifest</a> · <a href="requirement_traceability.tsv">Requirement traceability</a> · <a href="result_manifest.tsv">SHA256 result manifest</a> · <a href="software_versions.tsv">Software versions</a> · <a href="provenance.json">Provenance</a> · <a href="session_info.txt">Session</a></p>
</body>
</html>
""",
    snakemake.output.index,
)
