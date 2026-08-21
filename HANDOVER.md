---
schema_version: 1
project: PanFamFlow
project_root: .
last_updated: 2026-08-21T08:40:00+08:00
focus_task: template-complete-expression
status: EXECUTE_ACTIVE
---

# PanFamFlow 工作交接

本文件只保存继续工程任务所需的轻量状态，不替代原始数据、运行日志、结果清单或 Git 历史。

## 当前目标

在不重新分析用户 HSP 数据的前提下，使 PanFamFlow 对照冻结的 PDF/Markdown 模板完整实现并可验证：34 张正式图、配套源表、原生工具链、全基因组共线性、原始计数差异表达、报告、中文新手教程、可重复运行和公开 GitHub Pages。

## 已完成并有证据的事项

- Pro DESIGN attempt 2/3 已完成审查；批准方案 SHA256 为 `5a433ac54d909cc2ac5054efcd9484c7d6b389b721a25e90b4d12d76c36722c6`。
- Fig01–Fig34、MD01–MD27、输出表、配置字段和依赖版本均有机器可读合同。
- 旧 `1.0` 配置保持兼容；新 `1.1` 完整配置可解析和规划。
- 原生工具链 clean-toy 在 sxyH3 完成 21/21：规范化、OrthoFinder、IQ-TREE、复制分类、Ka/Ks 和启动子分析均通过。
- 全基因组共线性同时支持 `jcvi` 和审计过的 `precomputed` 输入；TPM 只做描述，正式差异表达只接受整数 raw counts、注册设计和对比。
- 依赖使用 linux-64 显式锁；DESeq2 运行时使用固定版本的 amd64 容器。
- 本地精确工作树已通过 Ruff、Mypy 和 204 项 Pytest；Pages 构建和内部链接检查通过。
- `llp98.work`、用户本地绝对路径和外部运行时网页资源已从公开入口与站点资产中移除。

## 已确认的科学边界

- 外部比较物种不进入 pan-family 分母；gene tree 不等同于 species tree。
- 基因结构以物种层汇总值作为独立单位；Ka/Ks 以 pair-cluster 汇总值作为推断单位。
- annotation absence 不是 validated gene loss；pairwise Ka/Ks 不是正选择证明。
- motif hit 不是调控因果；TPM 不用于差异表达检验；测试通过不等于生物学验证。

## 正在运行

- sxyH3：从空结果目录执行完整 12 模块、58 步 toy 闭包。
- sxyH3：按冻结 ENA 清单续传公开水稻 abiotic/biotic RNA-seq FASTQ；每个文件须通过字节数和 MD5 后才能写入下载回执。
- GitHub：首次功能分支推送后，由 Actions 使用仓库范围 `GITHUB_TOKEN` 构建 GHCR 表达容器并产生摘要回执。

## 尚需完成

1. 完整 clean-toy、34 图/源表语义校验、相同配置二次 no-work、局部子闭包恢复。
2. 用原生 JCVI 后端完成独立共线性运行证据。
3. 完成公共 RNA-seq 下载回执、参考版本登记、raw-count 定量和两组正式 DE 对比；组织表达 TPM 保持描述性证据。
4. 将公开 GHCR 摘要回填配置，验证从公共 URI 拉取容器。
5. 在最终 revision 重跑格式、静态检查、类型检查、测试、构建、Pages 和 14 门汇总。
6. 推送、PR、合并、Pages 部署，并从第三方 URL 验证项目首页和中文教程。

## 失败关闭规则

- 缺输入、MD5 不符、样本映射不唯一、参考版本不明、重复数不足、TPM 被送入 DE、HOG/基因无法协调或原生工具失败时必须停止该证据链。
- 不得用 toy 测试替代真实生物学结论；公共数据只有在来源、设计、参考、文件身份和结果清单全部协调后才能从 `CANDIDATE` 升为 `READY`。
- 后续如确需 Pro，应在同一 ChatGPT 项目中新建会话；每个会话最多提交 1–2 个实质请求，并只读取本文件和必要合同，不加载旧会话全文。

## 继续任务所需索引

- `docs/IMPLEMENTATION_ORDER.tsv`
- `docs/FIGURE_CONTRACT.tsv`
- `docs/REQUIREMENT_TRACEABILITY.tsv`
- `docs/DEPENDENCY_FREEZE.tsv`
- `docs/TEMPLATE_EQUIVALENCE_AUDIT.zh-CN.md`
- `decisions/DECISION_LOG.md`
- `examples/toy_complete/config.yaml`
- `examples/public_rice_expression/README.zh-CN.md`
