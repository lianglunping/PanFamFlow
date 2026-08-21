suppressPackageStartupMessages(library(DESeq2))

counts_path <- snakemake@input[["counts"]]
design_path <- snakemake@input[["design"]]
contrasts_path <- snakemake@input[["contrasts"]]
results_path <- snakemake@output[["results"]]
vst_path <- snakemake@output[["vst"]]
pca_path <- snakemake@output[["pca"]]
fit_qc_path <- snakemake@output[["fit_qc"]]
session_path <- snakemake@output[["session"]]

for (path in c(results_path, vst_path, pca_path, fit_qc_path, session_path)) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
}

counts_table <- read.delim(counts_path, check.names = FALSE, stringsAsFactors = FALSE)
design <- read.delim(design_path, check.names = FALSE, stringsAsFactors = FALSE)
contrasts <- read.delim(contrasts_path, check.names = FALSE, stringsAsFactors = FALSE)
stopifnot(!anyDuplicated(counts_table$stable_id))
rownames(counts_table) <- counts_table$stable_id
counts_table$stable_id <- NULL

all_results <- list()
all_vst <- list()
all_pca <- list()
all_fit_qc <- list()
result_index <- 0L
vst_index <- 0L
pca_index <- 0L
fit_index <- 0L

for (dataset_id in sort(unique(design$dataset_id))) {
  dataset_design <- droplevels(design[design$dataset_id == dataset_id, , drop = FALSE])
  sample_ids <- dataset_design$sample_id
  dataset_counts <- as.matrix(counts_table[, sample_ids, drop = FALSE])
  storage.mode(dataset_counts) <- "integer"
  row_filter <- rowSums(dataset_counts) >= as.integer(snakemake@params[["min_total_count"]])
  dataset_counts <- dataset_counts[row_filter, , drop = FALSE]
  if (nrow(dataset_counts) == 0L) {
    stop(paste("No genes pass min_total_count for dataset", dataset_id))
  }
  rownames(dataset_design) <- sample_ids
  dataset_design$condition <- factor(dataset_design$condition)
  dataset_design$batch <- factor(dataset_design$batch)
  design_formula <- if (nlevels(dataset_design$batch) > 1L) ~ batch + condition else ~ condition
  model_matrix <- model.matrix(design_formula, data = dataset_design)
  if (qr(model_matrix)$rank != ncol(model_matrix)) {
    stop(paste("Design matrix is rank deficient for dataset", dataset_id))
  }
  dds <- DESeqDataSetFromMatrix(
    countData = dataset_counts,
    colData = dataset_design,
    design = design_formula
  )
  dds <- DESeq(dds, quiet = TRUE)
  transformed <- varianceStabilizingTransformation(dds, blind = FALSE)
  assay_table <- assay(transformed)
  vst_long <- as.data.frame(as.table(assay_table), stringsAsFactors = FALSE)
  colnames(vst_long) <- c("stable_id", "sample_id", "vst_value")
  vst_long$dataset_id <- dataset_id
  vst_index <- vst_index + 1L
  all_vst[[vst_index]] <- vst_long[, c("dataset_id", "stable_id", "sample_id", "vst_value")]

  pca_fit <- prcomp(t(assay_table), center = TRUE, scale. = FALSE)
  variance_fraction <- (pca_fit$sdev ^ 2) / sum(pca_fit$sdev ^ 2)
  pca_table <- data.frame(
    dataset_id = dataset_id,
    sample_id = rownames(pca_fit$x),
    PC1 = pca_fit$x[, 1],
    PC2 = if (ncol(pca_fit$x) >= 2L) pca_fit$x[, 2] else 0,
    PC1_variance_fraction = variance_fraction[1],
    PC2_variance_fraction = if (length(variance_fraction) >= 2L) variance_fraction[2] else 0,
    stringsAsFactors = FALSE
  )
  pca_index <- pca_index + 1L
  all_pca[[pca_index]] <- pca_table

  dataset_contrasts <- contrasts[contrasts$dataset_id == dataset_id, , drop = FALSE]
  for (row_index in seq_len(nrow(dataset_contrasts))) {
    contrast_row <- dataset_contrasts[row_index, ]
    result <- results(
      dds,
      contrast = c("condition", contrast_row$numerator, contrast_row$denominator),
      alpha = as.numeric(snakemake@params[["alpha"]])
    )
    result_table <- as.data.frame(result)
    result_table$stable_id <- rownames(result_table)
    result_table$dataset_id <- dataset_id
    result_table$contrast_id <- contrast_row$contrast_id
    result_index <- result_index + 1L
    all_results[[result_index]] <- result_table[, c(
      "dataset_id", "contrast_id", "stable_id", "baseMean", "log2FoldChange",
      "lfcSE", "stat", "pvalue", "padj"
    )]
  }
  fit_index <- fit_index + 1L
  all_fit_qc[[fit_index]] <- data.frame(
    dataset_id = dataset_id,
    input_gene_count = nrow(counts_table),
    fitted_gene_count = nrow(dataset_counts),
    sample_count = length(sample_ids),
    design_formula = paste(deparse(design_formula), collapse = ""),
    design_rank = qr(model_matrix)$rank,
    design_columns = ncol(model_matrix),
    fit_status = "PASS",
    independent_dataset_fit = TRUE,
    stringsAsFactors = FALSE
  )
}

write.table(do.call(rbind, all_results), results_path, sep = "\t", quote = FALSE, row.names = FALSE)
write.table(do.call(rbind, all_vst), vst_path, sep = "\t", quote = FALSE, row.names = FALSE)
write.table(do.call(rbind, all_pca), pca_path, sep = "\t", quote = FALSE, row.names = FALSE)
write.table(do.call(rbind, all_fit_qc), fit_qc_path, sep = "\t", quote = FALSE, row.names = FALSE)
session_lines <- capture.output(sessionInfo())
writeLines(c(
  paste0("DESeq2_version=", as.character(packageVersion("DESeq2"))),
  paste0("R_version=", getRversion()),
  "fit_scope=ONE_DATASET_ONE_MODEL",
  session_lines
), session_path)
