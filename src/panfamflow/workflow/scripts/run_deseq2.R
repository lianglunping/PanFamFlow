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
contrast_defaults <- list(
  design_formula = "",
  factor = "condition",
  contrast_type = "simple",
  context_factor = "",
  context_numerator = "",
  context_denominator = ""
)
for (column in names(contrast_defaults)) {
  if (!(column %in% colnames(contrasts))) {
    contrasts[[column]] <- contrast_defaults[[column]]
  }
  contrasts[[column]][is.na(contrasts[[column]])] <- contrast_defaults[[column]]
}
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

low_dispersion_error <- "all gene-wise dispersion estimates are within 2 orders"

fit_deseq2 <- function(dds) {
  dispersion_fit_method <- "standard"
  fallback_reason <- ""
  fitted <- tryCatch(
    DESeq(dds, quiet = TRUE),
    error = function(error) {
      error_message <- conditionMessage(error)
      if (!grepl(low_dispersion_error, error_message, fixed = TRUE)) {
        stop(error)
      }
      dispersion_fit_method <<- "gene_wise_estimates_fallback"
      fallback_reason <<- gsub("[[:space:]]+", " ", trimws(error_message))
      fallback <- estimateSizeFactors(dds)
      fallback <- estimateDispersionsGeneEst(fallback, quiet = TRUE)
      dispersions(fallback) <- mcols(fallback)$dispGeneEst
      nbinomWaldTest(fallback, quiet = TRUE)
    }
  )
  if (dispersion_fit_method == "standard") {
    fit_type <- attr(dispersionFunction(fitted), "fitType")
    dispersion_fit_method <- paste0("standard_", fit_type)
  }
  list(
    dds = fitted,
    dispersion_fit_method = dispersion_fit_method,
    fallback_reason = fallback_reason
  )
}

transform_counts <- function(dds, dispersion_fit_method) {
  if (dispersion_fit_method != "gene_wise_estimates_fallback") {
    transformed <- varianceStabilizingTransformation(dds, blind = FALSE)
    return(list(
      transformed = transformed,
      transform_method = paste0(
        "vst_", attr(dispersionFunction(dds), "fitType")
      )
    ))
  }

  gene_wise_dispersions <- mcols(dds)$dispGeneEst
  usable <- is.finite(gene_wise_dispersions) & gene_wise_dispersions > 0
  if (!any(usable)) {
    stop("No finite positive gene-wise dispersions are available for VST fallback.")
  }
  mean_dispersion <- mean(gene_wise_dispersions[usable], trim = 0.001)
  dispersion_function <- function(means) rep(mean_dispersion, length(means))
  attr(dispersion_function, "fitType") <- "mean"
  attr(dispersion_function, "mean") <- mean_dispersion
  transform_dds <- dds
  suppressMessages(dispersionFunction(transform_dds) <- dispersion_function)
  list(
    transformed = varianceStabilizingTransformation(transform_dds, blind = FALSE),
    transform_method = "vst_mean_of_gene_wise_dispersions_fallback"
  )
}

model_cell <- function(dataset_design, design_formula, assignments, model_columns) {
  cell <- dataset_design[1, , drop = FALSE]
  for (variable in all.vars(design_formula)) {
    if (is.factor(dataset_design[[variable]])) {
      cell[[variable]] <- factor(
        as.character(dataset_design[[variable]][1]),
        levels = levels(dataset_design[[variable]])
      )
    }
  }
  for (variable in names(assignments)) {
    cell[[variable]] <- factor(
      assignments[[variable]],
      levels = levels(dataset_design[[variable]])
    )
  }
  cell_matrix <- model.matrix(design_formula, data = cell)
  vector <- rep(0, length(model_columns))
  names(vector) <- model_columns
  vector[colnames(cell_matrix)] <- cell_matrix[1, ]
  vector
}

factorial_contrast <- function(dataset_design, design_formula, contrast_row, model_columns) {
  factor_name <- as.character(contrast_row$factor)
  context_name <- as.character(contrast_row$context_factor)
  numerator <- as.character(contrast_row$numerator)
  denominator <- as.character(contrast_row$denominator)
  context_numerator <- as.character(contrast_row$context_numerator)
  numerator_assignments <- list()
  numerator_assignments[[factor_name]] <- numerator
  numerator_assignments[[context_name]] <- context_numerator
  denominator_assignments <- numerator_assignments
  denominator_assignments[[factor_name]] <- denominator
  contrast_vector <-
    model_cell(dataset_design, design_formula, numerator_assignments, model_columns) -
    model_cell(dataset_design, design_formula, denominator_assignments, model_columns)
  if (as.character(contrast_row$contrast_type) == "interaction") {
    context_denominator <- as.character(contrast_row$context_denominator)
    reference_numerator <- numerator_assignments
    reference_numerator[[context_name]] <- context_denominator
    reference_denominator <- denominator_assignments
    reference_denominator[[context_name]] <- context_denominator
    contrast_vector <- contrast_vector - (
      model_cell(dataset_design, design_formula, reference_numerator, model_columns) -
      model_cell(dataset_design, design_formula, reference_denominator, model_columns)
    )
  }
  contrast_vector
}

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
  dataset_contrasts <- contrasts[contrasts$dataset_id == dataset_id, , drop = FALSE]
  explicit_formulas <- unique(trimws(dataset_contrasts$design_formula))
  explicit_formulas <- explicit_formulas[nzchar(explicit_formulas)]
  if (length(explicit_formulas) > 1L) {
    stop(paste("Multiple design formulas declared for dataset", dataset_id))
  }
  if (length(explicit_formulas) == 1L) {
    design_formula <- as.formula(explicit_formulas[[1]])
  } else {
    dataset_design$condition <- factor(dataset_design$condition)
    dataset_design$batch <- factor(dataset_design$batch)
    design_formula <- if (nlevels(dataset_design$batch) > 1L) ~ batch + condition else ~ condition
  }
  for (variable in all.vars(design_formula)) {
    if (!(variable %in% colnames(dataset_design))) {
      stop(paste("Design formula references missing variable", variable, "for", dataset_id))
    }
    dataset_design[[variable]] <- factor(dataset_design[[variable]])
  }
  model_matrix <- model.matrix(design_formula, data = dataset_design)
  if (qr(model_matrix)$rank != ncol(model_matrix)) {
    stop(paste("Design matrix is rank deficient for dataset", dataset_id))
  }
  dds <- DESeqDataSetFromMatrix(
    countData = dataset_counts,
    colData = dataset_design,
    design = design_formula
  )
  fit <- fit_deseq2(dds)
  dds <- fit$dds
  transformation <- transform_counts(dds, fit$dispersion_fit_method)
  transformed <- transformation$transformed
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

  for (row_index in seq_len(nrow(dataset_contrasts))) {
    contrast_row <- dataset_contrasts[row_index, ]
    if (contrast_row$contrast_type == "simple") {
      result <- results(
        dds,
        contrast = c(contrast_row$factor, contrast_row$numerator, contrast_row$denominator),
        alpha = as.numeric(snakemake@params[["alpha"]])
      )
    } else {
      contrast_vector <- factorial_contrast(
        dataset_design,
        design_formula,
        contrast_row,
        colnames(model_matrix)
      )
      result <- results(dds, contrast = contrast_vector, alpha = as.numeric(snakemake@params[["alpha"]]))
    }
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
    dispersion_fit_method = fit$dispersion_fit_method,
    transform_method = transformation$transform_method,
    fallback_reason = fit$fallback_reason,
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
