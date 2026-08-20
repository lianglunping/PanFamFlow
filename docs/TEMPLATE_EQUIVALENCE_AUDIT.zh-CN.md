# PanFamFlow 与 PDF/MD 双基准的模板等价性审计

审计日期：2026-08-21。该审计只读取以下两份来源，不修改、不重算真实 HSP 数据：

- `03-泛基因家族分析-模板.pdf`（29 页，约 34 组结果图）
- `comparative_genomics_gene_family_workflow_20260807.md`（方法、QC、输出和验收合同）

机器可读的逐图核对见 [`TEMPLATE_FIGURE_EQUIVALENCE.tsv`](TEMPLATE_FIGURE_EQUIVALENCE.tsv)。

## 结论

当前 PanFamFlow **不与 PDF 模板或 MD 完整交付清单等价**。权威 58 项能力矩阵回答的是“某个主题是否已有代码、基础表或外部导入路径”，不是“模板中的每张图、每个统计和每份表是否已经原样完成”。中文教程为 58 项建立卡片，其中也包括明确标记为未支持的条目；目录完整不能替代执行与科学验收。

逐图审计的当前分布为：

| 模板等价状态 | 数量 | 含义 |
|---|---:|---|
| `MATCHED_CORE` | 11 | 核心计算、规范表与核心图已存在，但仍需真实数据与图注验收。 |
| `PARTIAL` | 15 | 有基础表、描述性分层或相邻图，但缺模板要求的正式统计、依赖性控制、专用图或完整交付合同。 |
| `NOT_IMPLEMENTED` | 6 | 当前没有足以生成该图的规范执行路径；其中 Fig21–22 合并为一条审计记录。 |
| `EXTERNAL_REQUIRED` | 1 | 可展示外部表达矩阵，但正式胁迫差异表达证据必须由合规 raw-count 分析提供。 |

因此，不能用“58 项均有教学覆盖”暗示完整模板。更准确的表达是：**58 个主题均有入口说明；Fig01–Fig34 共用 33 条审计记录（Fig21–22 合并），其中 11 条达到核心计算匹配、15 条部分可达、7 条尚无本地完整证据（6 条未实现、1 条依赖外部正式分析）。**

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

这解释了旧页面为什么即使展示 51 张卡片，仍会让熟悉 PDF 的读者觉得“差得很远”。当前 58 项目录已消除这一层遗漏，但新增卡片中仍有 4 项 `NOT_SUPPORTED`、2 项 `CONDITIONALLY_AVAILABLE`，不能把登记完成误写成实现完成。

## 主要 pipeline 缺口

### 家族与系统发育

- 已有 HMM/BLAST/domain evidence、成员表、家族基因树，以及 `species × subfamily` 数量/物种内比例矩阵和双面板热图。
- 缺核心结构域裁剪、氨基酸比对和 sequence logo 路径。
- 多物种代表材料+外部参考物种树没有独立的选择与交付合同。

### 基因结构

- 本批次已补物种中位数整体/两两非参数检验、BH-FDR、效应量、QC 和 PDF/PNG。
- MD 要求的结构指标还包括 transcript、总/均值/中位 exon、UTR 等；当前配置默认统计的六项不能冒充全部指标。
- 模板式 violin+box+jitter、n、median/IQR 和 effect size 的整合图尚未完全实现。

### HOG/泛基因家族

- 已有目标家族 HOG/OG membership、presence/absence、四分类、稀疏曲线、gene/HOG 双分母图，以及逐物种和亚家族的 count/proportion 图。
- 缺 OGG/HOG 质量的完整独立指标与 PASS/WARN/FAIL 合同。
- 这些新增图属于目标家族范围；不能借双分母输出扩大为全基因组 OGG 分析。
- 现有能力只针对目标家族同源群，不是全基因组图泛基因组。

### 染色体、复制与共线性

- 已有独立物种染色体定位、复制 mode/pair、全样本聚合图，以及 species/subfamily/pan-class × duplication-mode 的数量与比例矩阵和图。
- 缺染色体图上的 pan class/subfamily 叠加。
- 复制分层输出目前是描述性统计；没有自动执行物种分层的关联检验。
- 缺全基因组 anchors/blocks，因此 PDF 的染色体内 Circos 和物种间共线性均未实现；`duplication_pairs.tsv` 不能替代共线块。

### Ka/Ks

- 已有受约束 orthology/duplication pair、codon-aware 计算、缓存、QC，以及亚家族、群体、pan class、复制 mode 的两端归属、Mixed/Unassigned 语义和描述性分层表图。
- 仍缺亚家族×群体交互、WGD-vs-SSD 正式组间推断、pair 依赖性控制和多重校正。
- 不能用一张总体分布图声称已覆盖 PDF Fig04–06、Fig14 和 MD Fig09.1–09.6。

### 启动子

- 已有坐标、motif 命中、五个聚合层级、零值网格、分母、每 kb rate、z-score、QC 和多组热图；新增 group×subfamily 交互层。
- 缺 raw-count/per-gene 与 z-score 热图并排交付；MD 明确要求不能只交 z-score 图。
- 仍缺 `HOG × element` 和代表材料逐基因 Top-N 的规范矩阵/图。
- 四大类当前是柱状图，不是 PDF 的饼图；图型差异必须公开说明。

### 表达

- 已有 imported matrix 或 fastp→HISAT2→StringTie TPM 描述性路线和整体热图。
- MD 的正式差异表达路线要求 raw integer counts、sample metadata、STAR/featureCounts 或等价计数、DESeq2、PCA、batch/replicate QC、contrast 和 BH-FDR；当前尚未实现。
- 缺 pan class 整体/分组织、群体×亚家族表达专用比较以及 DEG UpSet。
- PDF 第 23–26 页的胁迫热图带 PanType 行注释并按处理/组织展示；当前通用表达热图不能自动替代这种设计。

## 教程缺口

当前页面的主要问题不是完全没有文字，而是大量卡片仍停留在“概念和基础表可连接”层面，缺少与真实规范输出绑定的教学闭环：

1. 没有按 PDF Fig01–Fig34 展示“模板希望看到什么”。
2. 没有为每张规范图提供最小示例、轴/颜色/分母解释和异常结果对照。
3. 部分卡片只指出基础表路径，却没有告诉小白如何从表中的具体列读到图上的结论。
4. `CONDITIONALLY_AVAILABLE` 容易被误读为“基本完成”；页面必须同时显示模板等价状态。
5. 原 51 项没有单列的七类交付现已加入教程；其中未实现项仍须保留显眼的进入条件和结论红线。

## 后续修复顺序

### P0：冻结双轴审计

- 保留 `ANALYSIS_COVERAGE.tsv` 作为代码能力状态。
- 新增本审计作为模板图件等价状态。
- 页面同时展示“代码可达性”和“模板交付等价性”，禁止把二者合并成单一高覆盖率数字。

### P1：补齐高复用数据层

- family distribution matrices；
- gene/HOG 双分母 pan-class summaries；
- duplication 三类分层矩阵；
- Ka/Ks 的 group/subfamily/pan-class/mode 归属与统计；
- promoter 的 group×subfamily 与 HOG 层矩阵；
- expression 的 raw-count/contrast 外部结果合同。

### P2：补齐规范图与表

- 每个 MD 图名都对应 PDF+高分辨率 PNG；
- 每个结构化结果同时 TSV+XLSX；
- raw、rate、标准化、样本量和 QC 不拆散；
- 图件不能只有颜色而没有可重算的源表。

### P3：重写中文教程

- 以“为什么做 → 输入是什么 → pipeline 如何做 → 输出在哪 → 先看什么 → 正常/异常 → 能说/不能说”为固定结构；
- 每张图绑定 toy 结果、列级阅读和失败示例；
- 首屏明确当前不等价结论，不再把 58 张卡片数量当完成度。

## 当前验收口径

当前可以描述为“58 项主题无目录遗漏，且高复用数据层已有一批可复现实跑输出”；仍不能描述为“已经完整实现 PDF/MD 的全部分析”。剩余独立工具链和正式统计以逐图矩阵中的 `PARTIAL`、`NOT_IMPLEMENTED`、`EXTERNAL_REQUIRED` 为准。
