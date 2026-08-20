# PanFamFlow 分析覆盖审计

本文件从第三方用户视角回答一个直接问题：来源工作流与模板列出的 51 项分析中，PanFamFlow 当前到底实现了什么。判定依据是仓库中的 Snakemake 规则、脚本、规范输出和测试，而不是功能名称相似、计划中的能力或真实 HSP 数据结果。

机器可读明细见 [`ANALYSIS_COVERAGE.tsv`](ANALYSIS_COVERAGE.tsv)。当前审计结果为：

| 状态 | 数量 | 含义 |
|---|---:|---|
| `IMPLEMENTED` | 11 | 存在可执行路径、明确的规范输出，并能直接回答该条目的核心问题。 |
| `CONDITIONALLY_AVAILABLE` | 29 | 已有基础数据，但仍需元数据连接、分母定义、统计检验、标准化或额外绘图；不能表述为自动完成。 |
| `EXTERNAL_IMPORT` | 2 | PanFamFlow 只接收外部结果用于整合或展示，不负责生成其统计证据。 |
| `NOT_SUPPORTED` | 9 | 当前没有足以支撑该条目结论的执行路径或规范输出。 |

## 审计边界

- PanFamFlow 分析的是目标基因家族在多个组装和注释中的成员、HOG 占有、结构、复制、Ka/Ks、启动子和表达，不构建水稻全基因组图泛基因组。
- `clade`、OrthoFinder `OG`、指定节点的 `HOG` 与目标家族 pan-locus 是不同层级，不能互换；`AUTO_ORTHOGROUP_FALLBACK` 结果不得表述为已固定节点的 HOG。
- annotation 中未发现基因不等于已验证的 gene loss；需要组装完整性、注释一致性、同源搜索和共线性证据。
- 单个成对 `Ka/Ks > 1` 不等于已经证明正选择；需要配对 QC、饱和过滤、统计模型和多重检验控制。
- 不同物种的 TPM 不具有天然可比性；跨物种热图只能用于经过明确同源映射与标准化设计的模式探索。
- 表达缺失语义按路线区分：FASTQ/StringTie 可依据样本物种标记跨物种 `NOT_APPLICABLE`；导入矩阵只保留用户输入的 NA 为 `MISSING_IN_INPUT`，在没有 sample species metadata 时不会猜测物种适用性。两者均不计入检测比例分母。
- 稀疏曲线和 Core/Soft-core/Shell/Cloud 分类只针对目标家族同源群，且依赖样本集合、阈值、HOG/OG 分组层级与随机种子。

## 如何使用覆盖表

1. 先按 `source_id` 在教程中定位相应条目。
2. 查看 `state`，不要把 `CONDITIONALLY_AVAILABLE` 或 `EXTERNAL_IMPORT` 写成“流程已自动完成”。
3. 用 `evidence` 与 `output` 找到可核验产物。
4. 在结果解读和论文表述前逐条检查 `limitation`。
5. 若研究问题要求 `NOT_SUPPORTED` 的能力，应建立独立、可验收的扩展任务，而不是从现有图表外推结论。

该审计不重算 HSP 数据，也不评价某一次真实项目运行是否生物学正确；真实数据验收仍需检查输入版本、配置、日志、软件版本、随机种子、输出校验和与科学 QC。
