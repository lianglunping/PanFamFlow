# 公开水稻表达示例：证据分级与运行边界

这个目录冻结“组织表达—非生物胁迫—生物胁迫”三个公开示例的数据集选择。它不是 HSP 分析，也不包含用户的原始数据或冻结结果。

## 为什么分成两条路线

- `GSE229334` 仅使用官方提供的 TPM 表做同一数据集内的组织表达描述。TPM 可用于热图和组织偏好展示，但不能送入 DESeq2，也不能与其他物种的绝对 TPM 直接比较。
- `GSE101734` 和 `GSE81906` 使用 SRA 原始读段重新定量，生成整数 count，再按各自的 2×2 设计做差异分析。两个研究独立建模，不能把 count 或 TPM 直接拼接后统一检验。

### 为什么不直接使用 NCBI 的表达量矩阵

我们检查了两个 GEO 条目的系列矩阵、补充文件清单和补充归档内容，而不是默认“公开转录组一定要从 FASTQ 开始”：

- [`GSE101734`](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE101734) 提供 12 个样本级文本表，核心定量列是作者流程产生的 `FPKM`；
- [`GSE81906`](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE81906) 提供 12 个 Cufflinks transcript GTF，表达量同样记录为 `FPKM`；
- 两个 GEO series matrix 都只含样本元数据，没有可直接进入计数模型的基因表达行；
- NCBI 的[标准化 RNA-seq count 服务说明](https://www.ncbi.nlm.nih.gov/geo/info/rnaseqcounts.html)目前将 NCBI 生成的 count 覆盖范围限定为人和小鼠，不能据此为这两个水稻研究取得统一生成的原始整数 count。

因此，这些作者提交的 FPKM 文件可用于复核样本身份、表达趋势和原文描述，但不能替代 `featureCounts` 原始整数 count 进入 DESeq2。若未来发现同一研究的官方或作者提交 raw-count 矩阵，只有在基因 ID、参考版本、样本—GSM—SRR 映射、技术 run 合并方式、整数性和文件校验全部通过后，才可跳过 FASTQ 重定量；该决定必须写入 provenance，不能仅凭文件名判断。

## 冻结的输入与来源

- 数据集级来源与判定：`datasets.tsv`
- 组织 TPM 文件的 URL、大小、MD5、SHA256 与用途边界：`processed_files.tsv`
- 组织 TPM 的 42 个 Input 样本、组织和生物学重复：`tissue_samples.tsv`
- 样本、GSM 与 SRR 映射：`selected_samples.tsv`
- 可直接送入运行审计的样本设计：`de_design.tsv`
- 预注册设计与比较：`contrasts.tsv`
- 重定量参考版本、官方 URL、文件大小与双重校验：`reference_files.tsv`

样本映射来自 NCBI SRA RunInfo；正式运行还必须保存当次返回的完整 CSV、URL、检索时间、`RunHash`、文件大小与下载校验值。`GSE81906` 的一个 GSM 对应两个 SRA run，它们是同一样本的技术 run，必须先按样本合并再计数，不能当作独立生物学重复。

## 组织 TPM 路线怎样运行

`GSE229334_Os.RNAseq.TPM.csv.gz` 同时含 42 个常规 RNA-seq Input 文库和 42 个 m6A-IP 文库。组织表达图只纳入 `tissue_samples.tsv` 登记的 Input 文库：14 个组织，每个组织 3 个生物学重复；IP 文库不会混入常规表达矩阵。适配器保留作者提交的 TPM 原值，不重新归一化，以每个组织 3 个重复的中位数生成描述性汇总，并把每张表同时写为 TSV 和 XLSX：

```bash
python scripts/prepare_public_tissue_tpm.py \
  /verified/cache/GSE229334_Os.RNAseq.TPM.csv.gz \
  examples/public_rice_expression/tissue_samples.tsv \
  /local/results/GSE229334
```

运行前必须先把下载文件核对为 `processed_files.tsv` 中记录的 19,232,726 bytes、MD5 `f4d1fb593d25b4cf59d4485e539af418` 和 SHA256 `84681cd23c29a979e094752a4445d47928d63e0c15d1d55ec9dad38a602fc65f`。适配器还会检查 stable ID 唯一、数值非负且有限、Input 列完全覆盖，以及每列 TPM 总和为 1,000,000。输出 provenance 明确标记 `AUTHOR_TPM_UNCHANGED` 和 `DESCRIPTIVE_ONLY_NO_DE`。这些检查只能证明文件身份和工程处理正确，不能把 TPM 组织差异解释为显著差异或调控因果。

## 参考基因组与 ID 口径

三个研究的原作者使用的参考并不完全一致：`GSE101734` 明确写明 MSU7，`GSE229334` 的处理记录写明 `Oryza_sativa.IRGSP-1.0.55`，`GSE81906` 写明 RGAP7/IRGSP-1.0。重新定量时必须为每个正式运行冻结一个基因组 FASTA、GFF/GTF、release、下载 URL 和 SHA256，并让 count、目标家族 stable ID 与注释版本一致。若无法无歧义映射，相关基因必须进入 `UNRESOLVED_ID`，不得静默丢弃或凭名称猜测。

## 可以与不能得到的结论

完成 QC、重复一致性、PCA、样本相关性、批次/离群检查及 BH-FDR 后，可以描述“某个已注册比较中，目标家族基因的表达变化方向和统计证据”。不能仅凭表达变化证明调控、抗性机制或因果关系；跨研究只整合方向、显著性和 HOG/稳定 ID 证据，不直接比较绝对 TPM。

当前状态：数据集、样本合同和 Ensembl Plants release 63 的 IRGSP-1.0 参考选择已冻结；组织 TPM 适配器已在上述固定 SHA256 的文件上通过 37,960 个基因、42 个 Input、42 个排除 IP、14 个组织和 TSV/XLSX 行列一致性检查。本次验证运行的 96/96 个 FASTQ 对象也已在来源缓存中同时通过字节数与 MD5 核验，来源回执 SHA256 为 `310958e6b3af22689fdf2f35a18390586e1705765b10e60839c95915cf8cea30`。前者只支持组织 TPM 的描述性工程验证，后者只证明公开读段来源缓存完整；二者都不代表重定量、差异表达或生物学解释已经通过。只有昆鹏计算节点产出 count、QC、DESeq2 session、manifest 与验收报告后，raw-count 路线才能标记为 `VERIFIED`；其他用户的副本仍须对自己的下载重新核验，不能沿用本次回执状态。
