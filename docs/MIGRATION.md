# Standalone repository migration

## Decision

PanFamFlow is maintained as an independent repository: `lianglunping/PanFamFlow`.

## Rationale

The former incubation location, `Wild-rice-Pangenome-Project`, is a separate project whose name and directory structure concern wild-rice pangenome work. Keeping PanFamFlow there could mislead users into treating a target pan-gene-family workflow as a pangenome-assembly component.

## Repository contract

- Source code lives at the repository root.
- `README.md` is the English entry point.
- `README.zh-CN.md` is the Simplified Chinese entry point.
- `docs/index.html` is the self-contained Chinese beginner tutorial and is linked from both README files.
- Both READMEs state that PanFamFlow does not assemble pangenomes or build graph pangenomes.
- CI runs from `.github/workflows/ci.yml`.
- Package, citation, clone, issue, and badge URLs refer only to `lianglunping/PanFamFlow`.
- Historical branches in the former repository are not canonical distribution channels.

## Scientific continuity

Migration changes repository identity and documentation, not the scientific scope. PanFamFlow remains a target-family workflow built around family discovery, phylogeny, HOG occupancy, Core/Soft-core/Shell/Cloud classification, gene structure, duplication, Ka/Ks, promoters, expression, and integrated reporting.
