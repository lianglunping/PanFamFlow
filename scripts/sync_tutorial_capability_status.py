#!/usr/bin/env python3
"""Synchronize audited PanFamFlow capability states across TSV and tutorial HTML."""

# Chinese tutorial content intentionally uses full-width punctuation.
# ruff: noqa: RUF001

from __future__ import annotations

import csv
import html
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_PATH = ROOT / "docs" / "ANALYSIS_COVERAGE.tsv"
MATRIX_PATH = ROOT / "docs" / "TUTORIAL_CONTENT_MATRIX.tsv"
FIGURE_EQUIVALENCE_PATH = ROOT / "docs" / "TEMPLATE_FIGURE_EQUIVALENCE.tsv"
FIGURE_CONTRACT_PATH = ROOT / "docs" / "FIGURE_CONTRACT.tsv"
HTML_PATH = ROOT / "docs" / "index.html"

CONDITIONAL_IDS = {"4.4", "8.6", "11.3", "11.4", "11.5"}
OPTIONAL_FIGURES = {"Fig03", "Fig09", "Fig17", "Fig21-22", "Fig34"}
STATE_LABELS = {
    "IMPLEMENTED": ("implemented", "已实现"),
    "CONDITIONALLY_AVAILABLE": ("conditional", "有条件可用"),
    "EXTERNAL_IMPORT": ("external", "需外部分析结果"),
    "NOT_SUPPORTED": ("not-supported", "当前未支持"),
}

COVERAGE_OVERRIDES = {
    "6.1": {
        "evidence": "pan_family 同时输出 OrthoFinder rooted species tree 与基于目标家族 OGG 0/1 矩阵的 Jaccard-average-linkage 聚类，并用合同表禁止混称",
        "output": "results/06_pan_family/orthofinder_species_tree.pdf；results/06_pan_family/ogg_presence_absence_clustering.pdf；results/06_pan_family/ogg_tree_contract.tsv",
        "limitation": "物种树是系统发育对象；OGG 有无聚类只是目标家族组成相似性，不是系统树、单个 HOG 基因树或分化时间证据",
    },
    "4.4": {
        "evidence": "domain_logo 可选子路径读取经过审计的核心结构域对齐，输出逐位点残基频率、信息量、域片段和 Logo QC",
        "output": "results/03_phylogeny/Fig09_core_domain_logo.pdf；results/03_phylogeny/family_domain_segments.tsv",
        "limitation": "仅在 domain_logo.enabled=true 且结构域边界与对齐输入通过 QC 时运行；Logo 不能证明功能位点或选择压力",
    },
    "8.6": {
        "evidence": "synteny 可选子路径按 species pair 独立审计 JCVI 或预计算的有序多锚点块，并生成染色体内、物种间和总览图",
        "output": "results/08_duplication/synteny_anchors.tsv；results/08_duplication/Fig17_representative_intragenome_circos.pdf；results/08_duplication/Fig21_inter_species_pairwise_synteny.pdf；results/08_duplication/Fig22_inter_species_synteny_overview.pdf",
        "limitation": "仅在 synteny.enabled=true 且全基因组坐标、蛋白与成块证据通过审计时运行；相似命中或 duplication pair 不能替代共线块",
    },
    "9.8": {
        "evidence": "kaks 同时生成 subfamily×group 二维配对层、cluster 中位数独立单位、整体/两两检验、效应量、BH-FDR 和 Fig06",
        "output": "results/09_kaks/kaks_by_subfamily_group.tsv；results/09_kaks/kaks_cluster_inference_tests.tsv；results/09_kaks/Fig06_kaks_by_subfamily_group.pdf",
        "limitation": "同一基因参与的 raw pair 不独立；正式推断使用注册 cluster 单位，物种与系统发育混杂仍需在研究设计中控制",
    },
    "10.1": {
        "evidence": "promoter 规则从同一逐命中源表按审计后的 major_class 汇总，输出带 motif-hit、基因覆盖和启动子长度分母的四大类圆环图与源表",
        "output": "results/10_promoter/promoter_major_class_summary.tsv；results/10_promoter/Fig23_promoter_four_major_classes.pdf",
        "limitation": "圆环比例的分母是 motif hit；genes_with_hit/gene_denominator 与 hits_per_kb 是另两种描述量，三者不可混称为调控强度或富集",
    },
    "10.2": {
        "evidence": "promoter_major_class_summary.tsv 同时报告 motif_hit_count、genes_with_hit、gene_denominator、gene_prevalence、promoter_bp_denominator 和 hits_per_kb",
        "output": "results/10_promoter/promoter_major_class_summary.tsv；results/10_promoter/Fig23_promoter_four_major_classes.pdf",
        "limitation": "必须冻结 motif 数据库/PlantCARE 来源、阈值、去重规则和 category_map；主类别命中多不等于相应通路被激活",
    },
    "10.3": {
        "evidence": "promoter_subclass_summary.tsv 对 subclass 输出命中负担、命中基因数、完整基因分母、基因覆盖率、启动子 bp 分母与每 kb 频率，并生成 Fig24",
        "output": "results/10_promoter/promoter_subclass_summary.tsv；results/10_promoter/Fig24_promoter_subclasses.pdf",
        "limitation": "subclass 名称和闭合性依赖版本化 category_map；描述性频率不自动构成富集、真实 TF 结合或因果调控证据",
    },
    "10.12": {
        "evidence": "pdf_md_complete 路径把 promoter hit 与目标家族 HOG membership 一对一连接，输出完整零值网格、基因数、启动子长度分母、每基因与每 kb 命中率及 QC",
        "output": "results/10_promoter/promoter_by_hog.tsv；results/10_promoter/promoter_by_hog.xlsx；results/10_promoter/promoter_by_hog.pdf",
        "limitation": "HOG 层 motif 命中率是描述性证据，不等于富集、真实 TF 结合或因果调控；Unassigned 基因必须保留",
    },
    "10.13": {
        "evidence": "promoter 规则按冻结的代表物种与 subfamily 分组确定性选择代表基因，输出选择原因、完整 gene×element 源表和 Fig28",
        "output": "results/10_promoter/representative_gene_element_matrix.tsv；results/10_promoter/Fig28_representative_gene_top_elements.pdf",
        "limitation": "代表基因由预注册规则选择，只用于展示；Top-N 是显示过滤，不代表元件或基因的生物学重要性排序",
    },
    "11.1": {
        "evidence": "expression 规则按 stable_id 连接 pan-family class，并输出物种内可比的分层表、规范图和适用性状态",
        "output": "results/11_expression/expression_by_pan_class.tsv；results/11_expression/Fig30_expression_by_pan_class.pdf",
        "limitation": "跨物种绝对 TPM 不直接比较；应先看物种内标准化、样本数、组织/条件和 NOT_APPLICABLE 状态",
    },
    "11.3": {
        "evidence": "differential_expression 可选子路径审计 raw integer counts、design 和 contrasts，在固定 DESeq2 容器中逐数据集建模并输出 DEG membership 与跨条件整合",
        "output": "results/11_expression/deseq2_fit_qc.tsv；results/11_expression/deseq2_contrast_results.tsv；results/11_expression/deg_membership.tsv；results/11_expression/Fig34_stress_expression_and_comparison.pdf",
        "limitation": "仅在 differential_expression.enabled=true 且 raw counts、重复、design/contrast 通过审计时运行；TPM/FPKM 被禁止用于正式 DE",
    },
    "11.4": {
        "evidence": "正式 DE 子路径按 abiotic dataset 独立执行 raw-count DESeq2，保留 design_id、contrast_id、log2FoldChange、padj、方向和质量状态",
        "output": "results/11_expression/deseq2_contrast_results.tsv；results/11_expression/stress_evidence_integration.tsv；results/11_expression/Fig34_stress_expression_and_comparison.pdf",
        "limitation": "必须提供有生物学重复且可核验 provenance 的非生物胁迫 raw counts；跨研究只整合效应方向和证据，不直接混合 TPM",
    },
    "11.5": {
        "evidence": "正式 DE 子路径按 biotic dataset 独立执行 raw-count DESeq2，保留 design_id、contrast_id、log2FoldChange、padj、方向和质量状态",
        "output": "results/11_expression/deseq2_contrast_results.tsv；results/11_expression/stress_evidence_integration.tsv；results/11_expression/Fig34_stress_expression_and_comparison.pdf",
        "limitation": "必须提供有生物学重复且可核验 provenance 的生物胁迫 raw counts；感染时间、组织和批次差异限制跨研究解释",
    },
    "11.6": {
        "evidence": "expression 规则读取 sample metadata 的 tissue，按 stable_id→HOG_ID→pan class 连接并输出组织分层表、规范图和缺失适用性状态",
        "output": "results/11_expression/expression_by_pan_class_tissue.tsv；results/11_expression/Fig31_expression_by_pan_class_tissue.pdf",
        "limitation": "只在可比组织和物种内表达尺度下解释；描述图不替代带重复、批次与物种效应的正式模型",
    },
    "11.7": {
        "evidence": "expression 规则按样本 group 与成员 subfamily 构造 group×subfamily 表和 Fig32，同时保留样本数、缺失和适用性状态",
        "output": "results/11_expression/expression_by_group_subfamily.tsv；results/11_expression/Fig32_expression_by_group_subfamily.pdf",
        "limitation": "该输出用于可审计的描述性比较；若要推断交互效应，仍需足够独立重复、批次控制和预注册统计模型",
    },
}

MATRIX_OVERRIDES = {
    "6.1": {
        "required_inputs": "OrthoFinder Species_Tree/SpeciesTree_rooted.txt；目标家族 family_presence_absence.tsv；与两者精确闭合的冻结 species_id 列表。",
        "pipeline_entry": "模块 pan_family；读取 OrthoFinder rooted species tree，并对目标家族 OGG 0/1 矩阵计算 Jaccard 距离与 average linkage。",
        "canonical_outputs": "results/06_pan_family/orthofinder_species_tree.nwk；results/06_pan_family/orthofinder_species_tree.pdf；results/06_pan_family/ogg_presence_absence_clustering.pdf；results/06_pan_family/ogg_presence_absence_distances.tsv；results/06_pan_family/ogg_presence_absence_linkage.tsv；results/06_pan_family/ogg_tree_provenance.tsv；results/06_pan_family/ogg_tree_contract.tsv",
        "how_to_read": "先读 ogg_tree_contract.tsv 确认对象：物种树回答物种关系；聚类图只回答目标家族 OGG 组成相似性。随后核对物种树叶标签闭合、Jaccard 距离和聚类分支，绝不把两图互换命名。",
        "qc_checks": "species tree 叶标签必须与配置物种精确闭合；OGG 矩阵只能为 0/1；HOG_ID 唯一；距离有限；两类对象均有来源哈希、方法和解释边界。",
        "supported_claims": "可分别展示 OrthoFinder 模型下的物种关系，以及冻结目标家族 OGG 组成的描述性相似聚类。",
        "unsupported_claims": "不能把 Jaccard 聚类称为系统发育树，也不能把 species tree 当成单个 HOG gene tree；不能由任一图直接推断功能、分化时间或因果。",
        "analysis_unit": "对象一：species-tree tip；对象二：species×target-family OGG presence vector",
        "join_keys": "species tree tip = configured species_id；presence matrix species columns = configured species_id",
        "runtime_gate": "OrthoFinder rooted species tree 必须唯一存在且叶标签精确闭合；presence 矩阵必须二元、HOG_ID 唯一、Jaccard 距离可计算。",
        "extension_requirements": "正式研究需冻结 OrthoFinder 版本、HOG node、物种集合、树来源哈希和 presence 矩阵清单；单个 HOG 基因树应另建独立产物。",
    },
    "4.4": {
        "pipeline_entry": "模块 phylogeny；设置 domain_logo.enabled=true 并提供经过审计的 domain_alignment。",
        "canonical_outputs": "results/03_phylogeny/Fig09_core_domain_logo.pdf；results/03_phylogeny/Fig09_core_domain_logo.png；results/03_phylogeny/family_domain_segments.tsv；results/03_phylogeny/domain_logo.xlsx",
        "runtime_gate": "仅在 domain_logo.enabled=true 且边界、序列 ID、对齐长度和缺口 QC 通过时运行。",
        "extension_requirements": "真实数据需冻结结构域数据库版本、边界来源、序列筛选和高缺口列规则。",
    },
    "8.6": {
        "pipeline_entry": "模块 duplication；设置 synteny.enabled=true，选择 jcvi 或 precomputed backend 并登记 species pairs。",
        "canonical_outputs": "results/08_duplication/synteny_anchors.tsv；results/08_duplication/synteny_blocks_intra.tsv；results/08_duplication/synteny_blocks_inter.tsv；results/08_duplication/Fig17_representative_intragenome_circos.pdf；results/08_duplication/Fig21_inter_species_pairwise_synteny.pdf；results/08_duplication/Fig22_inter_species_synteny_overview.pdf",
        "runtime_gate": "仅接受保持基因顺序且达到最小锚点数的块；每个 species pair 独立失败或通过。",
        "extension_requirements": "真实全基因组运行需冻结组装/注释版本、JCVI 参数、染色体布局和 anchor/block provenance。",
    },
    "9.8": {
        "pipeline_entry": "模块 kaks；二维 subfamily×group 汇总与 cluster-level inference 随规范 Ka/Ks 路径生成。",
        "canonical_outputs": "results/09_kaks/kaks_by_subfamily_group.tsv；results/09_kaks/kaks_cluster_inference_tests.tsv；results/09_kaks/Fig06_kaks_by_subfamily_group.pdf",
        "runtime_gate": "至少需要可计算 pair、完整二维归属和每个比较组足够的独立 cluster 单位；不足时保留 QC 而不伪造 P 值。",
        "extension_requirements": "正式研究可追加物种/系统发育混合模型，但不得把 raw pair 数当独立重复数。",
    },
    "10.1": {
        "required_inputs": "promoter_elements 明细；经人工审查的 element→major_class category_map；完整目标家族 promoter 坐标分母。PlantCARE 外部表须先通过来源与字段合同。",
        "pipeline_entry": "模块 promoter；从同一逐命中表生成四大类汇总和 Fig23 圆环图，图注同时给出 motif-hit 与基因覆盖分母。",
        "canonical_outputs": "results/10_promoter/promoter_major_class_summary.tsv；results/10_promoter/Fig23_promoter_four_major_classes.pdf；results/10_promoter/Fig23_promoter_four_major_classes.png",
        "how_to_read": "先核对 Unclassified 与完整基因/启动子长度分母；圆环扇区读 motif-hit 组成，标签中的 genes_with_hit/gene_denominator 读基因覆盖，hits_per_kb 读长度标准化负担，三者分开解释。",
        "qc_checks": "major_class 分类唯一且闭合；motif-hit 总数守恒；gene_denominator 等于冻结目标家族 promoter 数；promoter_bp_denominator 可追溯；PDF/600 dpi PNG 均存在。",
        "supported_claims": "可描述指定数据库、阈值和分类映射下四大类 motif 命中组成、基因覆盖和每 kb 命中率。",
        "unsupported_claims": "不能由圆环比例推断信号通路激活、TF 真实结合、表达效应、富集或因果调控。",
        "analysis_unit": "motif hit；并列报告 gene/promoter 与 promoter bp 分母",
        "join_keys": "element→category_map.major_class；stable_id→promoter coordinate denominator",
        "runtime_gate": "category_map、stable_id、类别闭合、命中总数守恒和两个分母均通过审计；否则关闭失败。",
        "extension_requirements": "正式数据需冻结 FIMO motif database 或 PlantCARE 导出版本、来源 URL、访问日期、阈值、去重规则和 category_map。",
    },
    "10.2": {
        "required_inputs": "promoter_elements 的 stable_id、major_class 与完整 promoter coordinate denominator。",
        "pipeline_entry": "模块 promoter；从 major_class×gene 零值完整网格汇总命中负担、基因覆盖率和每 kb 频率。",
        "canonical_outputs": "results/10_promoter/promoter_major_class_summary.tsv；results/10_promoter/promoter_elements_per_gene.tsv；results/10_promoter/Fig23_promoter_four_major_classes.pdf",
        "how_to_read": "同时看 motif_hit_count、genes_with_hit/gene_denominator 和 hits_per_kb；若三者方向不一致，应优先排查少数高重复 promoter 或长度差异。",
        "qc_checks": "stable_id 唯一连接；零命中基因保留在分母；Unclassified 不被静默删除；数据库、阈值与去重规则有 provenance。",
        "runtime_gate": "所有目标 promoter 都进入分母，外部命中 stable_id 不得越界；缺失或重复键时关闭失败。",
        "extension_requirements": "如需组间推断，另行预注册独立单位、背景集合、效应量和多重检验；本结果仅为描述性。",
    },
    "10.3": {
        "required_inputs": "promoter_elements 的 element/subclass/stable_id；版本化 category_map；完整 promoter coordinate denominator。",
        "pipeline_entry": "模块 promoter；按 subclass 汇总 motif hit、命中基因覆盖和每 kb 频率，并生成 Fig24 的负担与覆盖双面板。",
        "canonical_outputs": "results/10_promoter/promoter_subclass_summary.tsv；results/10_promoter/Fig24_promoter_subclasses.pdf；results/10_promoter/Fig24_promoter_subclasses.png",
        "how_to_read": "先比较命中负担，再看命中基因覆盖；命中集中在少数基因时不能用总 hit 数概括整个家族。",
        "qc_checks": "subclass 缺失进入 Unclassified；gene_denominator 与 promoter_bp_denominator 完整；命中数与逐命中表守恒。",
        "runtime_gate": "category_map 与逐命中表键可闭合，零命中分母被保留，统计量均为有限值。",
        "extension_requirements": "正式解释需冻结数据库版本，并避免把 motif 名称直接翻译成已验证生物功能。",
    },
    "10.12": {
        "pipeline_entry": "模块 promoter；pdf_md_complete 路径自动依赖 pan_family 并生成 HOG 层汇总。",
        "canonical_outputs": "results/10_promoter/promoter_by_hog.tsv；results/10_promoter/promoter_by_hog.xlsx；results/10_promoter/promoter_by_hog.pdf；results/10_promoter/promoter_by_hog_qc.tsv",
        "runtime_gate": "HOG membership 与 promoter stable_id 必须一对一；未分配成员进入 Unassigned 而不是被删除。",
        "extension_requirements": "如需富集检验，须另行预注册背景集合、独立单位和多重校正；本表不自动声称富集。",
    },
    "10.13": {
        "pipeline_entry": "模块 promoter；按代表物种和 subfamily 使用确定性规则选择代表基因，并随 Fig28 源表输出 selection_reason。",
        "canonical_outputs": "results/10_promoter/representative_gene_element_matrix.tsv；results/10_promoter/Fig28_representative_gene_top_elements.pdf；results/10_promoter/Fig28_representative_gene_top_elements.png",
        "runtime_gate": "代表物种、subfamily 和 stable_id 必须可解析；并列时按 stable_id 确定，不能人工挑选漂亮结果。",
        "extension_requirements": "正式数据需在报告中说明代表物种选择理由，并同时提供全体基因源表。",
    },
    "11.3": {
        "pipeline_entry": "模块 expression；设置 differential_expression.enabled=true，提供 raw integer counts、sample metadata、design 和 contrast 注册表。",
        "required_inputs": "逐数据集原始整数计数、sample metadata、design formula 和 contrast 注册表；流程生成 log2FoldChange、P 值、padj（BH-FDR）、方向和方法字段。若导入外部 DE 表，必须另行证明其满足同等输入和质量合同。",
        "canonical_outputs": "results/11_expression/deseq2_fit_qc.tsv；results/11_expression/deseq2_contrast_results.tsv；results/11_expression/deg_membership.tsv；results/11_expression/stress_evidence_integration.tsv；results/11_expression/Fig34_stress_expression_and_comparison.pdf",
        "supported_claims": "各数据集门禁通过后，可报告预先注册比较的效应量、BH-FDR、差异方向和跨比较成员关系；工程示例不等于真实水稻数据的生物学结论。",
        "runtime_gate": "每个 dataset 独立建模；输入必须是 raw integer counts；design matrix、重复和 contrast 均通过审计。",
        "extension_requirements": "真实数据需冻结 accession、GSM-SRR 映射、参考版本、计数文件哈希和 DESeq2 session。",
    },
    "11.4": {
        "pipeline_entry": "模块 expression 的 differential_expression 可选子路径；abiotic dataset 按各自 design 独立建模。",
        "canonical_outputs": "results/11_expression/deseq2_contrast_results.tsv；results/11_expression/stress_evidence_integration.tsv；results/11_expression/Fig34_stress_expression_and_comparison.pdf",
        "runtime_gate": "仅接受具有 biological replicate、control/treatment、design_id 和 contrast_id 的 raw-count 数据集。",
        "supported_claims": "门禁通过后，可支持特定非生物胁迫比较的效应量、BH-FDR、方向和跨研究 HOG 证据整合。",
        "extension_requirements": "登记公共 accession、run mapping、组织/时间、参考版本、URL、MD5/SHA256 和文件大小后才能升级为 ready。",
    },
    "11.5": {
        "pipeline_entry": "模块 expression 的 differential_expression 可选子路径；biotic dataset 按各自 design 独立建模。",
        "canonical_outputs": "results/11_expression/deseq2_contrast_results.tsv；results/11_expression/stress_evidence_integration.tsv；results/11_expression/Fig34_stress_expression_and_comparison.pdf",
        "runtime_gate": "仅接受具有 biological replicate、control/treatment、design_id 和 contrast_id 的 raw-count 数据集。",
        "supported_claims": "门禁通过后，可支持特定生物胁迫比较的效应量、BH-FDR、方向和跨研究 HOG 证据整合。",
        "extension_requirements": "登记病原、感染时间、组织、公共 accession、run mapping、参考版本和文件身份后才能升级为 ready。",
    },
    "11.6": {
        "pipeline_entry": "模块 expression；sample metadata 提供 tissue 后，描述性组织×pan-class 输出随主表达路径生成。",
        "canonical_outputs": "results/11_expression/expression_by_pan_class_tissue.tsv；results/11_expression/Fig31_expression_by_pan_class_tissue.pdf",
        "runtime_gate": "需要 tissue、species_id 和 pan-class 连接；不可比较的跨物种样本标为 NOT_APPLICABLE。",
        "extension_requirements": "若进行推断，需预注册组织对应、独立重复、批次和物种效应模型。",
    },
    "11.7": {
        "pipeline_entry": "模块 expression；sample metadata 的 group 与 family subfamily 元数据生成二维描述表和 Fig32。",
        "canonical_outputs": "results/11_expression/expression_by_group_subfamily.tsv；results/11_expression/Fig32_expression_by_group_subfamily.pdf",
        "runtime_gate": "需要非缺失 group/subfamily 和可比表达单位；空单元保留状态，不以零值填补缺失。",
        "extension_requirements": "若进行交互推断，需足够独立重复、批次控制和预注册模型。",
    },
}

CARD_REPLACEMENTS = {
    "6.1": {
        "正交组相关树形展示（对象需先定义）": "物种系统树与正交组有无聚类（两类对象分开）",
        "物种系统树与 OGG 有无聚类（两类对象分开）": "物种系统树与正交组有无聚类（两类对象分开）",
        "这一条首先要说明想画的是物种关系、某个正交组的基因树，还是有无矩阵的聚类树。三种图回答的问题不同，名称不能混用。": "流程会生成两类明确分开的对象：OrthoFinder 物种系统树，以及目标家族 OGG 有无矩阵的相似性聚类；后者不是系统发育树。",
        "PanFamFlow 能提供基础数据，但该条目的连接、分母、统计或专用图还要按下方合同补齐。完成这些步骤前，只能作有限的描述。": "PanFamFlow 在 pan_family 模块中复制并绘制 OrthoFinder rooted species tree，同时从目标家族 OGG 0/1 矩阵计算 Jaccard 距离和 average-linkage 聚类，并输出来源、距离、linkage 与命名边界合同。",
        "当前只能教学性解释不同树的含义。": "可分别解释冻结物种集合的系统关系和目标家族 OGG 组成相似性；两者均有直接源表与 provenance。",
        "本地最小示例已验证可连接的基础产物，但本条目尚无专用 canonical 结果：orthology 模块保留 OrthoFinder 结果目录和 HOG 节点。基础产物：": "clean toy 会直接验证两类 canonical 产物、叶标签闭合和非系统发育命名合同。规范产物：",
        "物种树、HOG 聚类树与目标家族基因树概念不同，且未输出原资料中名称含 OGG 的同款图": "物种树是系统发育对象；OGG 有无聚类只是目标家族组成相似性，不是系统树、单个 HOG 基因树或分化时间证据",
    },
    "4.4": {
        "当前没有核心结构域裁剪、氨基酸对齐和 sequence logo 规则": "流程读取经审计的核心结构域对齐，计算逐位点残基频率、信息量、覆盖与缺口状态，并生成可追溯 Logo",
        "当前未支持；必须先建立可审计的结构域裁剪与对齐合同。": "设置 domain_logo.enabled=true；结构域边界、stable_id、对齐长度和缺口 QC 必须通过。",
        "后续需实现 HMMER domain coordinate 裁剪、片段 QC、MAFFT/ClipKIT 参数、序列加权 Logo 及 PDF/PNG/位点映射表。": "真实数据需冻结结构域数据库版本、边界来源、序列筛选、MAFFT 参数与高缺口列规则。",
    },
    "8.6": {
        "当前未实现 MCScanX/JCVI 共线块或 Circos 轨道": "流程按物种对运行或导入经审计的 JCVI 有序多锚点块，并生成染色体内、物种间与总览图",
        "当前没有可到达的完整规则和规范输出。页面只说明所缺的执行路径，不能把相邻模块的表或图改名后当作本项结果。": "流程先逐对核验坐标、全基因组相似关系和有序多锚点块，再把目标家族锚点叠加到 Fig17、Fig21 和 Fig22；任何一对失败都保留独立状态。",
        "当前仅能说明需要何种外部证据。": "可以描述通过审计的全基因组共线块及其中目标家族锚点的位置关系。",
        "不能声称已经完成共线性/Circos，不能从定位图或 duplication pair 推断共线块。": "不能把单个相似命中、染色体定位或 duplication pair 写成共线块，也不能把工程示例当成真实物种结论。",
        "无。": "synteny.enabled=true；每个物种对必须具备可追溯的坐标、蛋白和 block/anchor 证据。",
        "本地 toy 未生成该分析，与当前能力矩阵的 CONDITIONALLY_AVAILABLE 一致；不得用邻近基础表冒充。边界：仅在 synteny.enabled=true 且全基因组坐标、蛋白与成块证据通过审计时运行；相似命中或 duplication pair 不能替代共线块": "examples/toy_complete 使用预计算但经过严格审计的有序多锚点块，验证 Fig17、Fig21 和 Fig22 的产物合同；原生 JCVI 后端仍需在冻结 JCVI/DIAMOND 环境中单独保存命令、版本和 anchor provenance。",
    },
    "10.2": {
        "results/10_promoter/promoter_major_class_summary.tsv；results/10_promoter/promoter_major_class_summary.tsv；": "results/10_promoter/promoter_major_class_summary.tsv；",
        "results/10_promoter/Fig23_promoter_four_major_classes.pdf；results/10_promoter/Fig23_promoter_four_major_classes.pdf": "results/10_promoter/Fig23_promoter_four_major_classes.pdf",
    },
    "9.8": {
        "当前仅分别生成 subfamily 和 group 的配对分层，没有交互层级的推断合同": "流程生成 subfamily×group 二维配对层，并以注册 cluster 的中位数作为独立单位执行受限推断",
        "当前未支持；现有描述性单因素输出不能替代交互模型。": "需要完整二维归属和足够的独立 cluster 单位；不足时只输出描述结果与 QC。",
        "当前只分别生成 subfamily_stratum 与 group_stratum，没有二维交互统计规则。": "流程同时生成二维分层源表、cluster-level 整体/两两检验、效应量、BH-FDR 和 Fig06。",
    },
    "11.3": {
        "当前没有 DESeq2/edgeR、contrast、DEG 判定、外部 DE schema validator 或 UpSet/Venn rule。": "可选 formal-DE 路径审计 raw counts、design 和 contrasts，在固定 DESeq2 容器中逐数据集建模并整合 DEG membership。",
        "当前流程没有原始计数模型和跨比较成员矩阵，尚不支持。": "流程用 raw integer counts 和注册 contrast 产生效应量、BH-FDR 与跨条件成员矩阵；TPM 热图不能替代这一路径。",
        "当前没有可到达的完整规则和规范输出。页面只说明所缺的执行路径，不能把相邻模块的表或图改名后当作本项结果。": "启用可选差异表达路径后，流程先检查整数计数、样本对应、重复、设计矩阵秩和比较方向，再在固定 DESeq2 容器中逐数据集独立建模；失败数据集关闭失败，不能用 TPM 或空表顶替。",
        "当前教程只能说明合规 DEG overlap 所需的输入和 QC，不能报告分析结果。": "各数据集门禁通过后，可报告预先注册比较中的效应量、BH-FDR、差异方向和跨比较成员关系。",
        "本地 toy 未生成该分析，与当前能力矩阵的 CONDITIONALLY_AVAILABLE 一致；不得用邻近基础表冒充。边界：仅在 differential_expression.enabled=true 且 raw counts、重复、design/contrast 通过审计时运行；TPM/FPKM 被禁止用于正式 DE": "examples/toy_complete 已登记 DS_ABIOTIC 和 DS_BIOTIC 两个专门构造的数据集；它们以原始整数计数、独立重复和注册 design/contrast 进入固定 DESeq2 路径，并生成拟合质量、效应量、BH-FDR、成员矩阵、整合表和 Fig34。",
    },
    "11.4": {
        "外部按 dataset/species 独立建模；PanFamFlow 仅可导入结果后按 HOG/方向整合。": "PanFamFlow 按 abiotic dataset/species 独立运行 raw-count DESeq2，再按 HOG、contrast 和效应方向整合。",
        "这一条需要先在外部按实验设计完成统计，再把包含效应量、显著性和质量信息的结果导入。PanFamFlow 不会把 TPM 热图冒充差异分析。": "该可选路径先审计重复、design 与 raw counts，再在固定 DESeq2 环境中计算效应量和 BH-FDR；流程仍不会把 TPM 热图冒充差异分析。",
        "仅外部结果导入。": "differential_expression.enabled=true，且 raw counts、重复、design 与 contrast 审计通过。",
        "toy 示例未提供满足 raw counts、重复、design/contrast、效应量与 FDR 要求的外部结果；因此本条目保持 CONDITIONALLY_AVAILABLE。": "examples/toy_complete 的 DS_ABIOTIC 使用专门构造的原始整数计数、独立重复和注册 design/contrast 验证固定 DESeq2 工程路径；真实研究仍需另行冻结公共数据来源和文件身份。",
    },
    "11.5": {
        "外部按 dataset/species 建模，导入后整合；当前无规则。": "PanFamFlow 按 biotic dataset/species 独立运行 raw-count DESeq2，再按 HOG、contrast 和效应方向整合。",
        "这一条需要先在外部按实验设计完成统计，再把包含效应量、显著性和质量信息的结果导入。PanFamFlow 不会把 TPM 热图冒充差异分析。": "该可选路径先审计重复、design 与 raw counts，再在固定 DESeq2 环境中计算效应量和 BH-FDR；流程仍不会把 TPM 热图冒充差异分析。",
        "仅外部结果导入。": "differential_expression.enabled=true，且 raw counts、重复、design 与 contrast 审计通过。",
        "toy 示例未提供满足 raw counts、重复、design/contrast、效应量与 FDR 要求的外部结果；因此本条目保持 CONDITIONALLY_AVAILABLE。": "examples/toy_complete 的 DS_BIOTIC 使用专门构造的原始整数计数、独立重复和注册 design/contrast 验证固定 DESeq2 工程路径；真实研究仍需另行冻结病原、感染时间和文件身份。",
    },
    "11.6": {
        "当前表达模块没有 tissue 元数据合同与 pan-class 联合统计规则": "表达模块读取 tissue 元数据并连接 HOG/pan-class，输出物种内可比的组织分层源表、Fig31 与适用性状态",
        "当前未支持；缺少 tissue 元数据与统计合同。": "需要 sample metadata 中的 tissue/species_id 与可追溯 pan-class；不可比单元标为 NOT_APPLICABLE。",
        "当前表达模块没有 tissue 元数据合同、物种内标准化或 pan-class 联合规则。": "流程在物种内表达尺度上汇总 tissue×pan-class，保留样本数、缺失状态、源表和 Fig31。",
    },
    "11.7": {
        "当前表达模块没有 group×subfamily 交互矩阵或可审计统计模型": "表达模块生成 group×subfamily 描述矩阵、样本数、缺失适用性状态和 Fig32；推断模型仍需独立重复",
        "当前未支持；整体表达矩阵不能替代二维交互模型。": "需要可比表达单位与完整 group/subfamily；描述图不能冒充二维交互显著性检验。",
        "当前表达模块没有 group×subfamily 交互矩阵、物种内标准化或可审计模型。": "流程生成 group×subfamily 源表和 Fig32，并把描述输出与需要额外重复的推断问题明确分开。",
    },
    "10.13": {
        "过滤 representative species 后绘制 gene×element heatmap/stack；当前无规则。": "流程按代表物种与 subfamily 采用确定性规则选择代表基因，并生成带 selection_reason 的 gene×element 源表和 Fig28。",
        "基础 promoter 表可按 representative species 过滤；专用 heatmap/stack 仍需后处理。": "代表物种、subfamily 与 stable_id 通过审计后直接生成规范源表和 PDF/PNG。",
        "增加 representative selection provenance 和 full table。": "正式数据需说明代表物种选择理由，并同时保留全体基因源表；Top-N 只是展示过滤。",
    },
}


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or []), list(reader)


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def machine_summary(rows: list[dict[str, str]]) -> str:
    counts = Counter(row["state"] for row in rows)
    order = ("IMPLEMENTED", "CONDITIONALLY_AVAILABLE", "EXTERNAL_IMPORT", "NOT_SUPPORTED")
    return "；".join(f"{state}={counts[state]}" for state in order if counts[state])


def human_summary(rows: list[dict[str, str]]) -> str:
    counts = Counter(row["state"] for row in rows)
    labels = {
        "IMPLEMENTED": "已实现",
        "CONDITIONALLY_AVAILABLE": "有条件可用",
        "EXTERNAL_IMPORT": "需外部分析结果",
        "NOT_SUPPORTED": "当前未支持",
    }
    order = ("IMPLEMENTED", "CONDITIONALLY_AVAILABLE", "EXTERNAL_IMPORT", "NOT_SUPPORTED")
    return "；".join(f"{labels[state]} {counts[state]} 项" for state in order if counts[state])


def replace_text(fragment: str, old: str, new: str) -> str:
    if not old or old == new:
        return fragment
    for source, target in ((old, new), (html.escape(old), html.escape(new))):
        fragment = fragment.replace(source, target)
    return fragment


def main() -> None:
    coverage_fields, old_coverage = read_tsv(COVERAGE_PATH)
    coverage: list[dict[str, str]] = []
    for old in old_coverage:
        row = dict(old)
        row["state"] = (
            "CONDITIONALLY_AVAILABLE" if row["source_id"] in CONDITIONAL_IDS else "IMPLEMENTED"
        )
        row.update(COVERAGE_OVERRIDES.get(row["source_id"], {}))
        coverage.append(row)
    if Counter(row["state"] for row in coverage) != Counter(
        {"IMPLEMENTED": 53, "CONDITIONALLY_AVAILABLE": 5}
    ):
        raise RuntimeError("Unexpected capability-state distribution.")
    write_tsv(COVERAGE_PATH, coverage_fields, coverage)

    matrix_fields, old_matrix = read_tsv(MATRIX_PATH)
    coverage_by_id = {row["source_id"]: row for row in coverage}
    matrix: list[dict[str, str]] = []
    for old in old_matrix:
        row = dict(old)
        audited = coverage_by_id[row["source_id"]]
        row.update(
            title=audited["source_title"],
            state=audited["state"],
            evidence_basis=audited["evidence"],
            limitation=audited["limitation"],
            canonical_outputs=audited["output"],
        )
        row.update(MATRIX_OVERRIDES.get(row["source_id"], {}))
        matrix.append(row)
    write_tsv(MATRIX_PATH, matrix_fields, matrix)

    contract_fields, contract = read_tsv(FIGURE_CONTRACT_PATH)
    del contract_fields
    contract_by_id = {row["figure_id"]: row for row in contract}
    equivalence_fields, equivalence = read_tsv(FIGURE_EQUIVALENCE_PATH)
    for row in equivalence:
        figure = row["template_figure"]
        row["equivalence_status"] = (
            "CONDITIONAL_MATCH" if figure in OPTIONAL_FIGURES else "MATCHED_CORE"
        )
        source_ids = ["Fig21", "Fig22"] if figure == "Fig21-22" else [figure]
        row["current_evidence"] = "；".join(
            contract_by_id[source_id]["source_table"] for source_id in source_ids
        )
        if figure in OPTIONAL_FIGURES:
            row["material_gap"] = (
                "规范执行路径、源表与 PDF/PNG 合同已实现但默认关闭；仍需合规输入和 B10 "
                "原生运行验收，工程测试不能替代生物学验证"
            )
        else:
            row["material_gap"] = (
                "规范执行路径、源表与 PDF/PNG 合同已实现；仍需真实数据和 B10 原生运行验收，"
                "工程完成不能写成生物学结论"
            )
    write_tsv(FIGURE_EQUIVALENCE_PATH, equivalence_fields, equivalence)

    page = HTML_PATH.read_text(encoding="utf-8")
    old_matrix_by_id = {row["source_id"]: row for row in old_matrix}
    new_matrix_by_id = {row["source_id"]: row for row in matrix}
    old_coverage_by_id = {row["source_id"]: row for row in old_coverage}
    for source_id, new_row in new_matrix_by_id.items():
        anchor = new_row["anchor"]
        pattern = re.compile(
            rf'(<article class="analysis-card" id="{re.escape(anchor)}".*?</article>)',
            re.DOTALL,
        )
        match = pattern.search(page)
        if match is None:
            raise RuntimeError(f"Tutorial card not found: {anchor}")
        fragment = match.group(1)
        old_row = old_matrix_by_id[source_id]
        old_state = old_row["state"]
        new_state = new_row["state"]
        old_class, old_label = STATE_LABELS[old_state]
        new_class, new_label = STATE_LABELS[new_state]
        fragment = fragment.replace(f'data-state="{old_state}"', f'data-state="{new_state}"')
        fragment = fragment.replace(
            f'class="state-badge {old_class}"', f'class="state-badge {new_class}"'
        )
        fragment = fragment.replace(
            f'data-state-label="{old_state}"', f'data-state-label="{new_state}"'
        )
        fragment = fragment.replace(old_state.lower(), new_state.lower())
        fragment = fragment.replace(old_state, new_state)
        fragment = fragment.replace(old_label, new_label)
        for field in (
            "title",
            "pipeline_entry",
            "canonical_outputs",
            "runtime_gate",
            "evidence_basis",
            "extension_requirements",
            "limitation",
        ):
            fragment = replace_text(fragment, old_row.get(field, ""), new_row.get(field, ""))
        old_audit = old_coverage_by_id[source_id]
        new_audit = coverage_by_id[source_id]
        # The matrix canonical_outputs field is derived from the coverage output and may
        # then be expanded by MATRIX_OVERRIDES. Replacing the shorter coverage output a
        # second time can therefore duplicate an output prefix on repeated synchronization.
        for field in ("source_title", "evidence", "limitation"):
            fragment = replace_text(fragment, old_audit.get(field, ""), new_audit.get(field, ""))
        for old_text, new_text in CARD_REPLACEMENTS.get(source_id, {}).items():
            fragment = replace_text(fragment, old_text, new_text)
        if new_state == "IMPLEMENTED":
            fragment = replace_text(
                fragment,
                "本地最小示例已验证可连接的基础产物，但本条目尚无专用 canonical 结果：",
                "clean toy 已验证本条目的规范执行路径与可追溯结果：",
            )
        search_blob = " ".join(
            str(new_row.get(field, ""))
            for field in (
                "source_id",
                "chapter",
                "title",
                "state",
                "biological_question",
                "required_inputs",
                "pipeline_entry",
                "canonical_outputs",
                "how_to_read",
                "qc_checks",
                "supported_claims",
                "unsupported_claims",
                "limitation",
                "runtime_gate",
                "evidence_basis",
                "extension_requirements",
            )
        )
        search_blob = html.escape(re.sub(r"\s+", " ", search_blob).strip().lower(), quote=True)
        fragment = re.sub(
            r'data-search="[^"]*"',
            f'data-search="{search_blob}"',
            fragment,
            count=1,
        )
        page = page[: match.start()] + fragment + page[match.end() :]

    old_by_chapter: dict[str, list[dict[str, str]]] = {}
    new_by_chapter: dict[str, list[dict[str, str]]] = {}
    for row in old_coverage:
        old_by_chapter.setdefault(row["source_id"].split(".", 1)[0], []).append(row)
    for row in coverage:
        new_by_chapter.setdefault(row["source_id"].split(".", 1)[0], []).append(row)
    for chapter in map(str, range(4, 12)):
        page = page.replace(
            machine_summary(old_by_chapter[chapter]), machine_summary(new_by_chapter[chapter])
        )
        page = page.replace(
            human_summary(old_by_chapter[chapter]), human_summary(new_by_chapter[chapter])
        )

    page = re.sub(
        r'(<div class="state-card implemented".*?<p><strong>)\d+( 项</strong>)',
        rf"\g<1>{Counter(row['state'] for row in coverage)['IMPLEMENTED']}\g<2>",
        page,
        count=1,
        flags=re.DOTALL,
    )
    page = re.sub(
        r'(<div class="state-card conditional".*?<p><strong>)\d+( 项</strong>)',
        rf"\g<1>{Counter(row['state'] for row in coverage)['CONDITIONALLY_AVAILABLE']}\g<2>",
        page,
        count=1,
        flags=re.DOTALL,
    )
    page = re.sub(
        r'(<div class="state-card external".*?<p><strong>)\d+( 项</strong>)',
        r"\g<1>0\g<2>",
        page,
        count=1,
        flags=re.DOTALL,
    )
    page = re.sub(
        r'(<div class="state-card unsupported".*?<p><strong>)\d+( 项</strong>)',
        r"\g<1>0\g<2>",
        page,
        count=1,
        flags=re.DOTALL,
    )
    page = page.replace(
        "PDF 的 Fig01–Fig34 有 11 条审计记录达到核心计算匹配、15 条部分可达、6 条未实现、1 条需要外部正式表达分析。原 51 项遗漏的 7 类图件现已全部纳入 58 项清单，但“已登记”仍不等于“已实现”。",
        "PDF 的 Fig01–Fig34 共有 33 条逐图审计记录（Fig21–22 合并），其中 28 条具备默认规范路径，5 条具备默认关闭的可选规范路径。全部仍需 B10 原生工具链和真实数据验收；工程实现不等于生物学验证。",
    )
    page = page.replace(
        "当前仍缺少全基因组共线块与 Circos 执行路径。",
        "可选 synteny 子路径已实现 JCVI/预计算有序多锚点块审计、目标家族叠加及 Fig17/Fig21/Fig22；默认关闭并要求合规全基因组输入。",
    )
    page = page.replace(
        "DESeq2、UpSet、tissue×pan-class 和 group×subfamily 表达统计未实现。",
        "tissue×pan-class 与 group×subfamily 描述路径已实现；默认关闭的 raw-count DESeq2 路径输出 contrast、DEG membership、效应量、BH-FDR 与 Fig34。",
    )
    page = page.replace(
        "HOG 层连接和显著性检验尚未实现。",
        "HOG 层零值完整表、每 kb 命中率、QC 与专用图已实现；这些描述输出不等于显著富集。",
    )
    page = page.replace(
        "当前物种共线性条目需要外部全基因组分析，不能用单个复制对替代。",
        "可选共线性路径审计全基因组有序多锚点块；单个相似命中或复制对不能替代。",
    )
    page = page.replace(
        "当前差异表达跨条件汇总未实现，不能由表达热图替代。",
        "可选 raw-count DESeq2 路径生成跨条件 DEG 成员矩阵；表达热图仍不能替代正式 DE。",
    )
    page = page.replace(
        "PanFamFlow 只接收带设计和统计证据的外部差异结果。",
        "PanFamFlow 可在 raw counts、重复、design 与 contrast 审计通过后逐数据集运行正式 DE。",
    )
    page = page.replace(
        "表示已有基础数据，但还缺连接、分母、统计或专用展示。",
        "表示规范执行路径已存在，但默认关闭或仍需额外、可审计的输入和运行门禁。",
    )
    page = page.replace(
        "这是教程能力矩阵的 PanFamFlow 内部机器值，不能写成已经完整实现。",
        "这是教程能力矩阵的 PanFamFlow 内部机器值；只有运行门禁通过后才能写成本次分析已完成。",
    )
    HTML_PATH.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
