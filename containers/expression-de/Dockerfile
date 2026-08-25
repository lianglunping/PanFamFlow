FROM bioconductor/bioconductor_docker:RELEASE_3_23@sha256:81bf4c3e9f1b08b0ada0a45ef16ef51d03dc91b0b06cda4b408d667cb8c2c645

LABEL org.opencontainers.image.title="PanFamFlow DESeq2 runtime" \
      org.opencontainers.image.description="Immutable R 4.6 / Bioconductor 3.23 runtime for raw-count differential expression" \
      org.opencontainers.image.source="https://github.com/lianglunping/PanFamFlow"

RUN Rscript -e 'BiocManager::install("DESeq2", version="3.23", ask=FALSE, update=FALSE)' \
    && Rscript -e 'stopifnot(as.character(packageVersion("DESeq2")) == "1.52.0")'

CMD ["R"]
