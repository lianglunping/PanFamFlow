# Rice three-group pilot audit

The committed audit contains no raw genome sequence and no Google Drive file IDs.

Observed from the selected input files:

- all twelve gzip files were readable to EOF and passed the actual PanFamFlow `input_audit.py` logic;
- genome sizes were approximately 375–399 Mb;
- each annotation had 39,081–39,511 gene/transcript records and no malformed nine-column GFF rows;
- GP543 and 534M had direct protein/CDS/GFF transcript identifier compatibility;
- all three real compressed genomes were atomically staged to plain FASTA, and an immediate second call reused the completed stage without changing its mtime;
- GP523 requires the documented GWH header/`Accession` mapping and has 358 more GFF transcripts than supplied protein/CDS records;
- the exact taxonomic names, formal assembly accessions, and annotation versions were not present in the provided folder metadata and remain unresolved.

This is sufficient for a three-genome engineering input/QC smoke test. It is not sufficient for a publication-level target-family biological benchmark until a target family and metadata are frozen.

Machine-readable evidence is stored in `panfamflow_input_audit.tsv` and `gzip_staging.tsv`. Timing values are environment-specific and are retained only as execution evidence, not as performance benchmarks.
