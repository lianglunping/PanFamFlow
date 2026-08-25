# PanFamFlow 与 PDF/MD 双基准的模板等价性审计

审计日期：2026-08-26。该审计以以下两份需求来源和当前 14 门机器验收记录交叉核对；不修改、不重算真实 HSP 数据：

- `03-泛基因家族分析-模板.pdf`（29 页，约 34 组结果图）
- `comparative_genomics_gene_family_workflow_20260807.md`（方法、QC、输出和验收合同）

机器可读的逐图核对见 [`TEMPLATE_FIGURE_EQUIVALENCE.tsv`](TEMPLATE_FIGURE_EQUIVALENCE.tsv)。

## 结论

当前 PanFamFlow 已为 PDF/MD 要求建立完整的代码与产物合同，并已完成 clean toy、原生工具链、公共数据 provenance、无工作复跑、局部恢复和 14/14 工程验收。权威 58 项能力矩阵回答“执行路径和规范输出是否存在”，逐图矩阵回答“Fig01–Fig34 是否有源表及 PDF/PNG 合同”；这些工程证据仍不能替代任意新目标家族的输入质量与生物学验收。

因此，当前 revision 在**工程交付层面**与 PDF 模板和 MD 完整交付清单闭合；在**真实研究结论层面**仍不是对任意目标家族的生物学等价性证明。可选路径只有在项目输入满足各自门禁并实际运行后，才能写成本次研究已完成。

逐图审计的当前分布为：

| 模板等价状态 | 数量 | 含义 |
|---|---:|---|
| `MATCHED_CORE` | 28 | 默认完整交付路径已登记规范源表、专用图、科学边界和失败状态。 |
| `CONDITIONAL_MATCH` | 5 | 专用路径已实现但默认关闭，需要显式提供比较物种、核心域对齐、全基因组共线性或 raw-count DE 输入。 |

因此，更准确的表达是：**58 个主题均有可执行/条件可执行路径；Fig01–Fig34 共用 33 条审计记录（Fig21–22 合并），其中 28 条走默认完整交付路径、5 条走默认关闭的可选路径。B10 clean toy、昆鹏原生工具链、无工作复跑、局部恢复和 14/14 工程验收均已完成；真实项目仍须按自己的输入与科学问题重新通过适用门禁。**

## 三类证据的优先级

1. PDF 定义“希望交付什么图和结果形态”。
2. MD 定义“怎样以更严谨、可复现的方法完成，以及哪些 PDF 口径不能照搬”。
3. 当前源码、规则、测试和隔离实跑定义“PanFamFlow 今天真正做到了什么”。

三者冲突时不能为了视觉复刻牺牲科学正确性。例如 PDF 把系统树 clade 直接称为 OGG；MD 已明确要求区分 clade、普通 OrthoFinder OG、物种树节点上的 HOG 和 presence/absence 聚类。PanFamFlow 应保留这种纠正，而不是复刻错误术语。

## 原 51 项矩阵曾漏掉、现已纳入的模板交付

以下内容在 PDF 中是明确图件，曾没有在原 51 项标题中成为独立条目；现在已经分别登记为 4.4、9.7–9.9、10.15、11.6–11.7：

- 群体 Ka、Ks、Ka/Ks 比较（PDF Fig05）；
- 亚家族×群体 Ka、Ks、Ka/Ks 交互比较（Fig06）；
- 核心结构域氨基酸 sequence logo（Fig09）；
- 核心/软核心/非必需基因 Ka、Ks、Ka/Ks 比较（Fig14）；
- 群体×亚家族启动子元件矩阵（Fig26）；
- 泛基因类型分组织表达比较（Fig31）；
- 群体×亚家族表达比较（Fig32）。

这解释了旧页面为什么即使展示 51 张卡片，仍会让熟悉 PDF 的读者觉得“差得很远”。当前 58 项目录已经消除主题遗漏，并把新增能力绑定到规范源表、图件和 QC；但可选路径仍必须用合规输入实际运行，不能把登记或单元测试误写成真实水稻结论。

## 当前工程实现范围

### 家族、树与结构

- Fig01–Fig03 已分别绑定家族树、成员注释和可选的代表材料/外部物种面板；外部物种默认不进入 pan-family 分母。
- Fig09 的核心结构域 Logo 已成为默认关闭的可选子路径，输出域片段、位点表、QC、工作簿和 PDF/PNG；Logo 仍不能证明功能位点或选择压力。
- Fig07–Fig08 以物种单元中位数进行基因结构汇总，并输出整体/两两非参数检验、效应量、BH-FDR 和不足样本状态。

### HOG、泛基因家族与染色体

- Fig10–Fig13 区分 HOG 数和基因数两个分母，保留指定节点 HOG 与普通 OG 回退状态、未分配成员和稀疏曲线。
- Fig15 把 pan class/subfamily 叠加到逐物种染色体坐标；不同物种不会被错误放在同一物理坐标轴。
- 能力仍只针对目标基因家族同源群，不构建全基因组图泛基因组，也不把 annotation absence 写成 validated gene loss。

### 复制、共线性与 Ka/Ks

- Fig16、Fig18–Fig20 生成唯一复制类型、pair registry、species/subfamily/pan-class 数量和比例，并显式保留冲突/未分配分母。
- Fig17、Fig21–Fig22 的可选共线性路径支持 JCVI 或预计算块；只有保持顺序的多锚点块可进入图，相似命中和 duplication pair 均不能冒充共线性。
- Fig04–Fig06、Fig14 生成 subfamily、group、subfamily×group、pan-class 分层源表和图；推断以注册 cluster 中位数为独立单位，并报告效应量与 BH-FDR，raw pair 数不作为生物学重复数。

### 启动子与表达

- Fig23–Fig28 绑定 major class、subclass、subfamily、group×subfamily、species 和代表基因源表；raw、每基因、每 kb、z-score、n 与 QC 均可追溯。
- 10.12 现已补充 `HOG × element` 的零值完整表、TSV/XLSX、每 kb 图和未分配 HOG 状态；motif hit 仍不是富集或真实 TF 结合证据。
- Fig29–Fig33 分别输出整体表达、pan class、pan class×tissue、group×subfamily 和全家族热图，并区分 `MISSING_IN_INPUT` 与 `NOT_APPLICABLE`。
- Fig34 是默认关闭的正式差异表达路径：只接收 raw integer counts，逐 dataset 在固定 DESeq2 容器中建模，输出 design/contrast、效应量、BH-FDR、DEG membership、跨胁迫证据和 session；TPM/FPKM 被禁止用于正式 DE。

## 教程当前合同

页面为 58 项各保留“基础概念、为什么做、输入、运行方法、规范输出、表图阅读、正常/异常、能说/不能说”四层教学卡片，并同时连接：

1. `ANALYSIS_COVERAGE.tsv` 的代码能力状态；
2. `TEMPLATE_FIGURE_EQUIVALENCE.tsv` 的 PDF 逐图匹配状态；
3. `FIGURE_CONTRACT.tsv` 的图件源表、开关和科学边界；
4. `REQUIREMENT_TRACEABILITY.tsv` 的 Fig01–Fig34 与 MD01–MD27 追踪关系。

术语采用中文主名称，英文、缩写和 PanFamFlow 内部状态只作为补充；每个可选路径都必须显示运行门禁，不能把“有代码”写成“已产生真实水稻结论”。

## 已完成的工程验收

- clean `toy_complete` 已覆盖默认和全部可选路径，生成 Fig01–Fig34、同源 TSV/XLSX、PDF/600 dpi PNG、版本、session、provenance 和 manifests；
- 相同配置无工作复跑已通过；三类隔离子产物恢复仅重建各自依赖闭包；
- 昆鹏原生 DupGen_finder 与原生 JCVI 已经由 `jsub` 计算节点执行并保留命令、版本、anchor 和调度回执；
- 96/96 FASTQ 共 88,296,890,982 字节通过逐文件 MD5 与 canonical verifier；24 个公共 RNA-seq 生物学样本完成 HISAT2、featureCounts 和固定 R 4.6.1 / DESeq2 1.52.0 重计算，形成 2 个数据集、6 个 contrast；
- 权威验收账本的 14 项门禁均为 `PASS`，包括结果语义、输入不可变性、教程真值合同、仓库质量、Pages 部署和公开 URL。

## 当前验收口径

当前可描述为“PDF/MD 的分析主题、执行路径、产物合同和工程验收已经无目录遗漏，14/14 门通过”；仍不可描述为“所有分析均已在任意真实水稻目标家族上完成生物学验证”。工程交付完成不提升功能、选择、适应性、调控因果或育种价值的结论强度。
