# 关键输出表结构

## `family_members.tsv`

核心列：

- `species_id`, `gene_id`, `transcript_id`, `stable_id`
- `family_name`, `subfamily`
- `chromosome`, `gene_start`, `gene_end`, `strand`
- `evidence_hmm`, `evidence_blast`, `evidence_precomputed`
- HMM/BLAST best-hit fields
- `molecular_weight_da`, `theoretical_pi`, `protein_property_qc`
- optional domain/localization prefixed columns
- `decision`, `rejection_reason`

配套 `family_distribution.tsv` 以 `species_id × subfamily` 为零值完整单元，保存 `gene_count`、物种总成员数与 `species_fraction`；`family_distribution.pdf/.png` 将绝对数量和物种内比例并列。矩阵中的 0 只表示当前成员表未检出，不是已验证基因丢失。

## `06_pan_family/pan_family_classification.tsv`

- `HOG_ID`, `hog_node`, `hog_node_status`（列名为向后兼容保留；值可为 HOG 或 OG）
- `orthology_group_type=HOG|ORTHOGROUP`, `orthology_source_file`
- `analysis_scope=TARGET_GENE_FAMILY_ONLY`
- `analysis_unit=ORTHOFINDER_HOG|ORTHOFINDER_ORTHOGROUP`
- `presence_basis=ANNOTATION_AND_HOG_MEMBERSHIP|ANNOTATION_AND_ORTHOGROUP_MEMBERSHIP`
- `absence_validation_status=NOT_GENOME_RESCUED`
- `interpretation_flag`
- `species_occupancy`, `species_fraction`, `family_gene_count`
- copy-number metrics
- `pan_family_class`, `is_private`

## `06_pan_family/family_hog_membership.tsv`

- `HOG_ID`, `orthology_group_type`, `species_id`, `gene_id`, `stable_id`
- `copy_number_in_species`

## `06_pan_family/unassigned_family_members.tsv`

目标家族成员未出现在所选 HOG node 时保留原 family columns，并增加：

- `reason=NOT_FOUND_IN_SELECTED_HOG_NODE`
- `selected_hog_node`
- `hog_node_status`
- `orthology_group_type`, `orthology_source_file`

当 `orthofinder.hog_node: auto` 且 OrthoFinder 未生成公开 `N*.tsv`（例如双物种小数据集）时，流程使用公开的 `Orthogroups/Orthogroups.tsv`，并写入 `AUTO_ORTHOGROUP_FALLBACK`。显式指定 `N*` 时不降级，缺表即报错。OG 与指定物种树节点上的 HOG 是不同分析层级，解释时必须查看上述类型与来源列。

配套分层输出：

- `pan_family_class_summary.tsv`：每个 `pan_family_class` 的 `hog_count`、`gene_count` 及两套独立分母比例；
- `pan_family_species_class_summary.tsv`：`species_id × pan_family_class` 的零值完整 gene/HOG 数量与比例；
- `pan_family_subfamily_class_summary.tsv`：`subfamily × pan_family_class` 的零值完整 gene/HOG 数量与比例；
- 相应 `*_dual_denominator.pdf/.png` 和 `*_class_distribution.pdf/.png` 图件。

## `04_gene_structure/gene_structure_global_tests.tsv`

- `comparison_scope`, `group_field`, `metric`
- `analysis_unit=SPECIES_MEDIAN`, `test_name=Kruskal-Wallis`
- `n_genes`, `n_species`, `n_species_group_units`, `min_group_units`
- `h_statistic`, `p_value`, `test_status`, `inference_warning`

配套 `gene_structure_pairwise_tests.tsv` 使用 Mann-Whitney U，记录每组基因数与物种单元数、基因/物种中位数、中位数差、`rank_biserial_effect`、原始 P 值和 `p_adjusted_bh`。只有总体检验通过且显著时才执行两两推断；否则 `test_status` 解释跳过原因。`gene_structure_statistics_qc.tsv`、XLSX 和 PDF/PNG 图保留同一状态语义。

## `duplication_mode.tsv`

- `species_id`, `gene_id`, `stable_id`
- `duplication_mode`, `partner_stable_ids`
- `outgroup`, `backend`

配套 `duplication_structure_global_tests.tsv`、`duplication_structure_pairwise_tests.tsv` 和 `duplication_structure_statistics_qc.tsv` 沿用上述结构统计字段，但 `group_field=duplication_mode`。`duplication_structure_comparisons.pdf/.png` 以物种中位数作点，并直接标注重复不足、低重复或物种单元无变异。

`duplication_stratified_summary.tsv` 以 `stratification`、`stratum`、`duplication_mode` 为主键，保存 species、subfamily 和 pan-family class 三个层级的 `gene_count` 与层内 `gene_fraction`。`duplication_stratified_distributions.pdf/.png` 是描述性数量/比例图，不执行因果或正式组间推断。

## `kaks_pairs.tsv`

- `stable_id_1`, `stable_id_2`
- `pair_type`, `group_id`, `pair_id`
- 两端 species/subfamily/group/pan-class/duplication-mode 元数据
- `subfamily_stratum`, `group_stratum`, `pan_class_stratum`, `duplication_mode_stratum`；两端不一致时为 `Mixed`，缺失时为 `Unassigned`
- `Ka`, `Ks`, `Ka_Ks`, `method`
- `qc_status`, `qc_message`, `resumed_from_cache`

`kaks_stratified_summary.tsv` 按上述四类 stratum 汇总 Ka、Ks、Ka/Ks 的 `n`、中位数、四分位数和范围；`kaks_stratified_distributions.pdf/.png` 明确标记 `DESCRIPTIVE_ONLY_NONINDEPENDENT_PAIRS`。这些 pair 可能共享基因，不能直接当作独立生物学重复。

## `promoter_elements.tsv`

- `stable_id`, `element`, `major_class`, `subclass`
- FIMO coordinate/score/p/q-value fields when available
- `species_id`, `gene_id`, `promoter_length`, `promoter_qc`

配套输出：

- `promoter_element_summary.tsv`：按 stable gene、major class 和 element 汇总命中数；
- `promoter_elements_per_gene.tsv`：按 stable gene 与 major class 汇总，供整合报告使用；
- `promoter_element_distributions.tsv`：按 `SPECIES_SUBFAMILY`、`SUBFAMILY`、`SPECIES`、`GROUP` 和 `GROUP_SUBFAMILY` 五个层级输出零值完整网格、`motif_hit_count`、`genes_with_hit`、`n_genes`、`total_promoter_bp`、`hits_per_gene`、`hits_per_kb`、两个 z-score 及其状态；
- `promoter_distribution_qc.tsv`：逐聚合层级记录所需注释、可用/排除基因数、单元与元件数、完整网格行数、零长度单元、标准化轴和 QC 状态；
- `promoter_element_class_counts.pdf/.png`：主类别计数图；
- `promoter_top_elements.pdf/.png`：配置 Top-N 的元件计数图；
- `promoter_species_subfamily_zscore_heatmap.pdf/.png`、`promoter_subfamily_zscore_heatmap.pdf/.png`、`promoter_species_zscore_heatmap.pdf/.png`、`promoter_group_zscore_heatmap.pdf/.png`、`promoter_group_subfamily_zscore_heatmap.pdf/.png`：对每个元件跨相应单元的 `hits_per_kb` 计算总体 z-score（`ddof=0`）后绘制；灰色表示分母缺失，颜色不代表显著富集。

## `expression_matrix.tsv`

前置 metadata 列为 `stable_id`, `species_id`, `gene_id`, `subfamily`，后续为 sample columns。导入矩阵路线另含 `expression_data_status`：`AVAILABLE`、`PARTIAL_MISSING` 或 `MISSING`。

FASTQ/StringTie 路线中，同物种样本未报告的目标基因写为 `0.0`；基因与样本属于不同物种时写为 `NA`，不得把 NA 当作未表达。

导入矩阵路线保留输入中的 NA，但由于没有 sample species metadata，不会自行判断该 NA 是否为跨物种不适用。

## `expression_long.tsv`

- `stable_id`, `species_id`, `gene_id`, `subfamily`
- `sample_id`, `expression_value`；FASTQ/StringTie 路线另含 `sample_species_id`
- `measurement_status`：FASTQ/StringTie 路线为 `MEASURED`、`ASSAYED_ZERO`、`NOT_APPLICABLE`；导入矩阵路线为 `OBSERVED`、`MISSING_IN_INPUT`
- `detected`：对 `NOT_APPLICABLE` 或 `MISSING_IN_INPUT` 为 NA

## `expression_summary.tsv`

- `samples_available`：统计有数值且适用的样本；
- `expression_detected_samples`, `expression_detected_fraction`：排除 `NOT_APPLICABLE` 和 `MISSING_IN_INPUT`；
- `measured_samples`, `assayed_zero_samples`：仅 FASTQ/StringTie 路线提供；
- `median_expression`, `max_expression`：忽略 NA。

## `master_gene_table.tsv`

以 `stable_id` 为一行，整合 family 证据、gene structure、target-family HOG/pan-family class、chromosome、duplication、per-gene Ka/Ks summary、promoter summary 和 expression summary。

表结构可能在 minor release 增列，但 `stable_id` 语义保持稳定；破坏性改名需要 schema 版本更新。
