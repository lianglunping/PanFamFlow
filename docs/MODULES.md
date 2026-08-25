# 模块说明

## `qc`

输入：配置中与所选模块相关的 genome、GFF3、reference protein、HMM、motif、expression/FASTQ 等。

输出：

- `input_audit.tsv/.xlsx`
- `run_manifest.json`
- 可选 `busco_summary.tsv/.xlsx`

失败条件：文件不存在、为空、FASTA 无记录、GFF3 无法解析、BUSCO 运行失败。

## `normalize`

方法：默认使用 AGAT `agat_sp_keep_longest_isoform.pl` 选择最长 CDS 转录本，再由 gffread 提取序列。严格、结构清晰的 GFF3 也可显式选择 `portable_gff3` 后端；该后端遇到层级歧义会终止，不替代 AGAT 的注释清洗能力。

输出：每物种 canonical GFF3、protein、CDS、transcript 和 `gene_transcript_map.tsv/.xlsx`。

关键 QC：stable ID 唯一、每个 gene 只保留一个 canonical transcript、CDS 长度模 3。

## `family`

方法：HMMER `hmmsearch`、BLASTP 或预计算成员表。HMM/BLAST 候选先分别筛选，再按配置合并。

输出：

- `family_members.tsv/.xlsx`
- `family_candidates_rejected.tsv`
- `family_proteins.fa`
- `family_cds.fa`
- `family_domains.fa`
- `family_distribution.tsv/.xlsx`
- `family_distribution.pdf/.png`

可导入 subfamily、CDD/domain validation 和 WoLF PSORT subcellular localization 表。新正式项目应把 `external_import_validation` 设为 `strict`，并提供来源、版本、访问日期和 URL；字段模板与解释边界见 [`EXTERNAL_EVIDENCE_IMPORTS.zh-CN.md`](EXTERNAL_EVIDENCE_IMPORTS.zh-CN.md)。大规模项目只加载候选 family 的序列和 mapping 子集，避免把全体 proteome/CDS 同时载入内存。

## `phylogeny`

方法：MAFFT → ClipKIT → IQ-TREE。最少序列数由 `phylogeny.min_sequences` 控制。

输出：alignment、trimmed alignment、`.treefile` 和 IQ-TREE report。

## `gene_structure`

从 canonical GFF3 提取 gene length、exon count、CDS count/length、intron count/length 和 UTR 指标。

对配置的结构指标，模块按 `species_id × subfamily` 和 `species_id × group` 计算物种中位数，以 Kruskal-Wallis 作整体检验；只有整体检验显著时才执行两侧 Mann-Whitney U，并在每个比较范围与指标内做 BH-FDR。输出同时保留基因数、物种单元数、中位数差、秩二列效应量和推断警告。若每组物种单元不足，P 值被明确暂停而不是用基因条目数补足重复。

输出包括逐基因指标、描述汇总、整体/两两统计表、统计 QC、XLSX，以及带物种中位数散点和推断警告的 PDF/PNG 图。

## `orthology`

方法：OrthoFinder 3。输入 canonical proteomes；调用 `-X` 保留 PanFamFlow stable ID。

输出：完整 OrthoFinder 工作目录位置和 completion JSON。正式发布结果应保存 `SpeciesTree_rooted_node_labels.txt` 并固定目标 HOG node。

## `pan_family`

优先读取所选 OrthoFinder `Phylogenetic_Hierarchical_Orthogroups/N*.tsv`，并与 `family_members.tsv` 取交集。`hog_node: auto` 下若没有公开 HOG 表（OrthoFinder 3 的双物种小数据集可出现此情况），则读取保留稳定 ID 的公开 `Orthogroups/Orthogroups.tsv`；结果明确标记 `orthology_group_type=ORTHOGROUP` 和 `AUTO_ORTHOGROUP_FALLBACK`。显式配置 `N*` 时不自动降级。流程只处理目标家族同源群；不提供 whole-genome 模式，也不构建泛基因组。

输出：

- `pan_family_classification.tsv`
- `family_hog_membership.tsv`
- `family_presence_absence.tsv`
- `unassigned_family_members.tsv`
- rarefaction 原始迭代、汇总和图件
- HOG/基因双分母 pan-class 表图
- species/subfamily × pan-class 的 gene/HOG 数量与比例表图
- OrthoFinder rooted species tree 的 Newick、PDF/PNG 和来源哈希
- 目标家族 OGG 0/1 矩阵的 Jaccard 距离、average-linkage 聚类 PDF/PNG 和非系统发育命名合同

分类表为向后兼容保留 `HOG_ID` 列名，同时用 `orthology_group_type`、`orthology_source_file`、`analysis_unit` 区分 HOG 与普通 Orthogroup，并记录 `pan_family_class`、`presence_basis` 和 `absence_validation_status`。矩阵中的 0 表示注释/同源群层面未检出，不自动代表已验证的基因丢失。旧预发布模块名 `pangenome` 仅作为兼容别名。

## `chromosome`

读取 family 成员坐标和各物种 genome chromosome 长度。输出每个 gene 的位置、相对位置、coordinate QC，以及每物种/染色体计数与 density。

不同物种保持独立 panel，不直接拼接物理坐标。

## `duplication`

### `dupgen_finder_unique`

对配置 target/outgroup 组合生成 DupGen_finder 输入，使用 DIAMOND 生成相似性文件，再解析 WGD/Tandem/Proximal/Transposed/Dispersed/Singleton。

DupGen_finder 本体通过 `scripts/install_dupgen.sh` 非覆盖安装，并应记录源 commit。

### `precomputed`

导入包含 stable ID、duplication mode 和可选 partner 的表。若 partner 可解析，会同时生成 `duplication_pairs.tsv`，供 Ka/Ks 使用。

无论使用哪个 backend，模块都会按 `stable_id` 一对一连接 `gene_structure_metrics.tsv`，并对 `species_id × duplication_mode` 中位数执行与 `gene_structure` 相同的整体/两两统计、BH-FDR、效应量和推断 QC。该输出描述“复制类型与结构指标的关联”，不能证明复制机制导致了结构变化。

模块还连接 family 的 `subfamily` 与 pan_family 的分类，输出 species、subfamily、pan-family class 三层 `duplication_mode` 数量/比例长表和 PDF/PNG。该部分为描述性汇总；pan-family 层当前按基因计数，不可误称为 HOG 分母或因果检验。

## `kaks`

pair source：

- `orthology`：目标 HOG 内 reference species 与其他物种的严格单拷贝 pair。
- `duplication`：duplication partner pair。
- `both`：合并并去重。

方法：protein MAFFT → PAL2NAL codon alignment → KaKs_Calculator。

输出包含失败信息和 QC flags；任何单 pair 失败不会静默删除。每个 pair 还连接两端 subfamily、group、pan-class 和 duplication-mode，并分别归为同名层、`Mixed` 或 `Unassigned`。规范分层表图只汇总 n、四分位数和范围，并明确标记 pair 非独立；当前不提供组间显著性检验或系统发育校正。

## `promoter`

先根据 strand 提取 promoter：默认 upstream 2000 bp、downstream 0 bp；记录 chromosome 边界截断和邻近 gene overlap。

backend：

- `fimo`：扫描 versioned MEME motif database。
- `precomputed_plantcare`：导入 PlantCARE/其他来源表；`strict` 模式要求服务、版本、访问日期和 URL。

所有 ID 必须可映射到提取的 family promoter。

规范输出包括逐命中 `promoter_elements.tsv`、逐元件汇总 `promoter_element_summary.tsv`、逐基因主类别汇总 `promoter_elements_per_gene.tsv`、主类别/子类别源表、多维分布长表 `promoter_element_distributions.tsv`、分布 QC 表、工作簿、Fig23 四大类圆环图、Fig24 子类别命中数与基因检出率双面板、Top-N 元件图，以及物种×亚家族、亚家族、物种、群体、群体×亚家族五组标准化热图。

主类别和子类别源表同时保留 motif 命中数、命中比例、有命中的基因数、全部启动子基因分母、基因检出率、启动子总长度和每 kb 命中率。多维分布表为每个聚合单元和每种元件补齐真零组合，同时保留 `n_genes`、`total_promoter_bp`、`hits_per_gene` 和 `hits_per_kb`。标准化固定为对每个元件跨聚合单元的 `hits_per_kb` 计算总体 z-score（`ddof=0`），并用 `PASS`、`ZERO_VARIANCE`、`INSUFFICIENT_CELLS` 或 `MISSING_DENOMINATOR` 记录可解释性。亚家族和群体输出依赖相应元数据；HOG 层级由 `pdf_md_complete` 路径生成独立源表和 QC，逐项状态见 `ANALYSIS_COVERAGE.tsv`。

## `expression`

### `imported_matrix`

导入 wide matrix，筛选 family genes，输出 wide/long/summary 和模式热图。输入中的空单元保留为 NA，在 long 表标记为 `MISSING_IN_INPUT`，不计入 detected fraction 分母；每个基因的 `expression_data_status` 为 `AVAILABLE`、`PARTIAL_MISSING` 或 `MISSING`。该路线没有 sample species metadata，因此不会把 NA 自动解释为跨物种不适用。

### `fastq_stringtie`

fastp → HISAT2 → sorted BAM → StringTie `-e -A` → family TPM matrix。gene ID 映射按 sample 的 species scope 处理，允许不同物种存在相同原始 gene ID。同物种 abundance table 未报告的目标基因记为 `ASSAYED_ZERO`（0.0），跨物种不适用单元记为 `NOT_APPLICABLE`（NA），只有 StringTie 明确报告的单元记为 `MEASURED`。该解释以前提“abundance table 完整且上游成功”为条件。

上述两条基础表达路线只提供表达模式与汇总。另有默认关闭的 `differential_expression` 子路径：它只接收 raw integer counts，先审计生物学重复、design rank 和预注册 contrast，再在固定 DESeq2 容器中逐数据集建模，输出效应量、BH-FDR、DEG membership、PCA、拟合 QC 与 Fig34。TPM/FPKM 会在正式差异分析入口被拒绝；缺少合格重复、design 或 contrast 时保持失败关闭。

## `report`

整合 family、gene structure、pan_family、chromosome、duplication、Ka/Ks、promoter 和 expression 指标，输出 master table、结果 SHA256 manifest、Python package versions、run info 和静态 HTML gallery。

## Ka/Ks 环境说明

Bioconda 包名为 `kakscalculator2=2.0.1`，安装后提供 `KaKs_Calculator` 命令。流程不会使用不存在的 `kaks_calculator` 包名。
