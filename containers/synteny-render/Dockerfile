FROM bioconductor/bioconductor_docker:RELEASE_3_23@sha256:81bf4c3e9f1b08b0ada0a45ef16ef51d03dc91b0b06cda4b408d667cb8c2c645

LABEL org.opencontainers.image.title="PanFamFlow circlize runtime" \
      org.opencontainers.image.description="Immutable R 4.6 renderer for audited whole-genome synteny blocks"

RUN Rscript -e 'install.packages(c("GlobalOptions", "shape", "colorspace"), repos="https://cloud.r-project.org")' \
    && Rscript -e 'install.packages("https://cloud.r-project.org/src/contrib/circlize_0.4.18.tar.gz", repos=NULL, type="source")' \
    && Rscript -e 'stopifnot(as.character(packageVersion("circlize")) == "0.4.18")'

CMD ["R"]
