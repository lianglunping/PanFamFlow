# Independent-style audit and corrective actions

This document records issues that a third-party reviewer would identify, including problems not visible from the analysis template screenshots.

## Release and repository integrity

### Finding A1 — the workflow was hosted inside an unrelated pangenome project

Hosting PanFamFlow inside `Wild-rice-Pangenome-Project` made a target pan-gene-family workflow appear to be a pangenome-assembly component. Repository identity, scope, issues, releases, and CI were therefore ambiguous.

Corrective action:

- publish the complete source tree at the root of the standalone `lianglunping/PanFamFlow` repository;
- keep `README.md` in English and `README.zh-CN.md` in Simplified Chinese, with reciprocal language links;
- provide `docs/index.html` as a self-contained Chinese beginner tutorial linked from both README files;
- update package metadata, citation metadata, clone commands, issue links, and CI badges to the standalone repository;
- keep one root-level long-lived CI workflow and no staging or one-time publication payloads.

Acceptance:

```text
GET /contents/README.md?ref=<commit> -> 200
GET /contents/README.zh-CN.md?ref=<commit> -> 200
GET /contents/docs/index.html?ref=<commit> -> 200
GET /contents/pyproject.toml?ref=<commit> -> 200
GET /contents/src/panfamflow/cli.py?ref=<commit> -> 200
GET /contents/.github/workflows/ci.yml?ref=<commit> -> 200
```

### Finding A2 — repository-root CI must test the standalone layout

The CI workflow must run from the repository root rather than assume a nested `PanFamFlow/` working directory.

Corrective action: install `/.github/workflows/ci.yml`, test both README languages and target-family scope, and run all Python/Snakemake gates from the repository root.

## Scientific scope and terminology

### Finding B1 — project wording drifted toward general pangenome analysis

The original project objective is target pan-gene-family analysis, not pangenome assembly or whole-genome HOG classification.

Corrective action:

- title and package description changed to target pan-gene-family analysis;
- canonical module renamed from `pangenome` to `pan_family`;
- `whole_genome` scope removed and rejected;
- output directory renamed to `06_pan_family/`;
- all HOG rows are intersected with target-family stable IDs.

### Finding B2 — OGG, HOG, clade and pan-locus were at risk of conflation

A family-tree clade is not automatically an orthogroup; a HOG is not automatically a material-level syntenic pan-locus.

Corrective action:

- canonical output uses `HOG_ID`, not `OGG_ID`;
- family `subfamily` remains a separate field;
- docs state that pan-locus inference is not implemented in v0.1.1;
- no gene-loss conclusion is generated automatically.

### Finding B3 — family genes absent from the selected HOG node could disappear silently

A stable-ID mismatch or inappropriate HOG node could cause target-family members to be omitted without an explicit audit table.

Corrective action: write `06_pan_family/unassigned_family_members.tsv` with a reason and selected node.

### Finding B4 — annotation absence was too easy to overinterpret

Binary HOG occupancy is influenced by assembly and annotation quality.

Corrective action: each classification row now records that occupancy is annotation/HOG based and not genome-rescued. The report cannot label zeroes as confirmed gene losses.

## Workflow engineering

### Finding C1 — retry/resume claims must be tested against actual outputs

Command-construction unit tests alone do not prove skip/resume behavior.

Required CI gates:

1. unit tests and type/lint checks;
2. Snakemake lint and dry-run;
3. a real toy `qc` execution;
4. a second identical execution with unchanged output hashes/mtimes;
5. deletion of one downstream marker followed by local reconstruction only.

### Finding C2 — list-valued Snakemake inputs were handled as scalar paths in Ka/Ks

Named list inputs can be list-like, so `Path(snakemake.input.membership)` is not universally safe.

Corrective action: normalize scalar/list input values before creating `Path` objects.

### Finding C3 — cached Ka/Ks results did not report cache reuse

Corrective action: set `resumed_from_cache = true` when a validated pair cache is returned.

### Finding C4 — provenance records only described launch intent

Corrective action: run records now start as `RUNNING` and are atomically finalized with `COMPLETED`/`FAILED`, exit code and finish time. A failed launcher invocation is recorded as exit code 127. Per-rule failure summaries remain a future enhancement.

## Biological limitations still open

The following are not represented as completed features:

- genome-level rescue of apparent absent family genes;
- syntenic pan-locus construction for intraspecific accessions;
- real-data acceptance of the implemented optional raw-count DESeq2 path (the engineering path and fail-closed gates exist; public biological validation is still pending);
- codeml/HyPhy positive-selection models;
- systematic matched-background motif enrichment;
- full-scale OrthoFinder/IQ-TREE/KaKs interruption tests on real rice data.

These remain explicit roadmap items rather than implied capabilities.
