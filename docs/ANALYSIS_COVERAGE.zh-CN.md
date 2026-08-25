# PanFamFlow 分析覆盖审计

本文件从第三方用户视角回答一个直接问题：来源工作流文字清单及 PDF 逐图核对得到的 58 项分析中，PanFamFlow 当前到底实现了什么。原文字清单的 51 项曾漏列 7 个 PDF 独立主题，现已全部纳入权威目录。判定依据是仓库中的 Snakemake 规则、脚本、规范输出和测试，而不是功能名称相似、计划中的能力或真实 HSP 数据结果。

机器可读明细见 [`ANALYSIS_COVERAGE.tsv`](ANALYSIS_COVERAGE.tsv)。当前审计结果为：

| 状态 | 数量 | 含义 |
|---|---:|---|
| `IMPLEMENTED` | 52 | 存在直接可达的规则/脚本、规范源表与结果合同；输入不足时必须产生明确 QC 状态，而不是伪造结果。 |
| `CONDITIONALLY_AVAILABLE` | 6 | 执行路径已经实现，但默认关闭或需要额外、可审计的结构域对齐、HOG、全基因组共线性或 raw-count 实验设计输入。 |

6 项条件实现为：4.4 核心结构域 Logo、6.1 OGG/HOG 树上下文、8.6 全基因组共线性，以及 11.3–11.5 raw-count 差异表达/胁迫整合。`CONDITIONALLY_AVAILABLE` 表示“代码路径存在但运行门禁未必满足”，不是“尚未开发”。

## 审计边界

- PanFamFlow 分析的是目标基因家族在多个组装和注释中的成员、HOG 占有、结构、复制、Ka/Ks、启动子和表达，不构建水稻全基因组图泛基因组。
- `clade`、OrthoFinder `OG`、指定节点的 `HOG` 与目标家族 pan-locus 是不同层级，不能互换；`AUTO_ORTHOGROUP_FALLBACK` 结果不得表述为已固定节点的 HOG。
- annotation 中未发现基因不等于已验证的 gene loss；需要组装完整性、注释一致性、同源搜索和共线性证据。
- 单个成对 `Ka/Ks > 1` 不等于已经证明正选择；需要配对 QC、饱和过滤、统计模型和多重检验控制。
- 不同物种的 TPM 不具有天然可比性；跨物种热图只能用于经过明确同源映射与标准化设计的模式探索。
- 正式差异表达只接收 raw integer counts，在固定 DESeq2 环境中按 dataset 独立建模；TPM/FPKM 在配置验证阶段即被阻断。没有合格重复、design 或 contrast 时，不生成伪造的 DEG 结论。
- 共线性只接受通过审计的全基因组有序多锚点块；单个相似命中、染色体定位或 duplication pair 不能替代 synteny block。
- 表达缺失语义按路线区分：FASTQ/StringTie 可依据样本物种标记跨物种 `NOT_APPLICABLE`；导入矩阵只保留用户输入的 NA 为 `MISSING_IN_INPUT`，在没有 sample species metadata 时不会猜测物种适用性。两者均不计入检测比例分母。
- 稀疏曲线和 Core/Soft-core/Shell/Cloud 分类只针对目标家族同源群，且依赖样本集合、阈值、HOG/OG 分组层级与随机种子。
- 启动子标准化固定为“对每个元件跨聚合单元的每 kb 命中率计算总体 z-score（`ddof=0`）”；颜色只表示相对模式，不是显著富集、调控因果或物种/群体历史证据。
- 基因结构组间推断固定使用每个 `species_id × group` 单元的中位数，避免把同一物种的多个家族基因伪装成独立生物学重复。每组少于 2 个物种单元时，流程保留描述图和 QC，但明确暂停 P 值推断。

## 如何使用覆盖表

1. 先按 `source_id` 在教程中定位相应条目。
2. 查看 `state`；`CONDITIONALLY_AVAILABLE` 必须同时核对配置开关、输入审计和运行状态，不能写成无条件自动完成。
3. 用 `evidence` 与 `output` 找到可核验产物。
4. 在结果解读和论文表述前逐条检查 `limitation`。
5. 即使状态为 `IMPLEMENTED`，也要区分代码路径、工程运行证据和真实生物学验证；三者不能互相替代。

该审计不重算 HSP 数据，也不评价某一次真实项目运行是否生物学正确；真实数据验收仍需检查输入版本、配置、日志、软件版本、随机种子、输出校验和与科学 QC。
