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

## `duplication_mode.tsv`

- `species_id`, `gene_id`, `stable_id`
- `duplication_mode`, `partner_stable_ids`
- `outgroup`, `backend`

## `kaks_pairs.tsv`

- `stable_id_1`, `stable_id_2`
- `pair_type`, `group_id`, `pair_id`
- `Ka`, `Ks`, `Ka_Ks`, `method`
- `qc_status`, `qc_message`, `resumed_from_cache`

## `promoter_elements.tsv`

- `stable_id`, `element`, `major_class`, `subclass`
- FIMO coordinate/score/p/q-value fields when available
- `species_id`, `gene_id`, `promoter_length`, `promoter_qc`

配套输出：

- `promoter_element_summary.tsv`：按 stable gene、major class 和 element 汇总命中数；
- `promoter_elements_per_gene.tsv`：按 stable gene 与 major class 汇总，供整合报告使用；
- `promoter_element_class_counts.pdf/.png`：主类别计数图；
- `promoter_top_elements.pdf/.png`：配置 Top-N 的元件计数图。

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
