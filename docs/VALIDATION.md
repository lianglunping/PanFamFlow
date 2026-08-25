# 验证记录

## 声明规则

只有独立仓库根目录中的完整源码可直接浏览，并且同一提交通过自动化检查后，才可标记为软件工程层面的已发布。临时 staging、压缩分片或外部归档不算源码发布。

## v0.1.1-alpha 软件工程验证

验证日期：2026-08-09

已在 GitHub Actions 的 Ubuntu 24.04 / Python 3.12 环境中完成：

```text
uv 0.12.3 lock and locked sync
Ruff lint and formatting
mypy strict checking
27 pytest tests
wheel and source-distribution build
PanFamFlow CLI version/list/validate/plan
Snakemake 9.25.1 toy DAG dry-run
actual toy QC first execution
second identical execution with unchanged hashes and mtimes
deletion of qc.done followed by downstream-only reconstruction
three terminal provenance records with COMPLETED / exit code 0
```

关键兼容性修复包括：

- 在 Snakemake 多值 `--rerun-triggers` 与工作流目标之间加入 `--` 终止符，避免目标被解析为触发器；
- 移除 `workflow/scripts/*.py` 中不兼容 Snakemake `script:` 包装器的 `from __future__ import annotations`；
- 将工作流脚本测试所需的 Biopython 与 Matplotlib 纳入锁定的开发依赖；
- 保留原子输出、运行指纹和最终 `COMPLETED`/`FAILED` provenance 状态。

首次执行、自动跳过和局部恢复已经由 GitHub Actions run `31304925922` 实际验证；该运行还生成了非空的 verified-source artifact。长期 CI 会在每次相关提交和 PR 更新时重复执行同类门禁。

清理后的精确提交 `60edf5504f0f2e7a80508ae5f84662deef6f5e37` 已由长期 CI push run `31305053638` 验证成功。

## v0.1.2 benchmark-gate 开发验证

在不修改 v0.1.1 基线的独立工作目录中，已使用 Python 3.13.5 执行：

```text
python -m compileall -q src tests
PYTHONPATH=src pytest -q
```

结果：

```text
34 passed
```

新增回归覆盖：

- benchmark 初始化拒绝覆盖非空目录；
- 完整双基因组 fixture 达到 `READY`；
- 缺失 genome/GFF3/protein/CDS 时保持 `BLOCKED`；
- 输入内容发生 SHA256 漂移时保持 `BLOCKED`；
- reference-aligned sample 不能替代 assembled genome；
- 中文 HTML、JSON、TSV、XLSX 和 SHA256 receipt 均非空；
- 规划期 `--allow-blocked` 不改变报告中的阻断状态。
- `docs/index.html` 可由标准库 HTML parser 解析，ID 唯一，不依赖外部 JavaScript/CSS，并包含中文小白教程、配置生成器、断点续跑和解释边界。

Ruff、mypy、wheel/sdist 和 benchmark CLI smoke test 由新分支长期 CI 在精确提交上复核。

## v0.1.2-alpha 本地全模块实跑（2026-08-19）

在 macOS arm64 主机上，以 Snakemake 9.25.1、OrthoFinder 3.1.5 和规则级 Conda 环境对扩展 toy 数据执行了完整模块闭包：

```text
qc, normalize, family, phylogeny, gene_structure, orthology,
pan_family, chromosome, duplication, kaks, promoter, expression, report
```

该次运行不是 dry-run。规范化后的 4 个目标家族成员形成 2 个跨物种 Orthogroup；OrthoFinder 3 在双物种 toy 场景没有发布 `N*.tsv` HOG 表，因此 `pan_family` 按设计采用公开 `Orthogroups/Orthogroups.tsv`，并在结果中写明：

```text
orthology_group_type = ORTHOGROUP
hog_node_status = AUTO_ORTHOGROUP_FALLBACK
analysis_unit = ORTHOFINDER_ORTHOGROUP
```

实跑产物级验收结果：

- 6 条输入审计记录全部 `PASS`；
- 4 个 family member 均唯一，全部且仅一次进入 2 个 Core Orthogroup，无 unassigned member；
- chromosome、duplication、promoter、expression 和 master table 均覆盖 4 个成员；
- 2 个 Ka/Ks pair 均通过脚本 QC；数值仅为工程 fixture，不作生物学解释；
- report 记录全部 13 个模块，80 条 manifest 文件的 SHA256 全部与磁盘内容一致；
- 紧接着的同命令复跑返回 `Nothing to be done`，完整状态表全部为 `ok / no update`；
- 在隔离副本中删除一个规范化蛋白输出后，dry-run 正确计划重建缺失文件及其完成标记。

同一工作树最终质量门为：Ruff lint 通过、Ruff format 通过、mypy strict 通过、`71 passed`、wheel/sdist 构建通过、Pages 最小站点构建和内部链接检查通过。来源 MD 与 29 页 PDF 模板中的 51 个分析条目均进入 `ANALYSIS_COVERAGE.tsv` 和中文教程；该次基线状态分布为 11 `IMPLEMENTED`、29 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、9 `NOT_SUPPORTED`。后续启动子多维分布批次的当前状态见下节与权威覆盖表。

## 启动子多维分布与标准化本地验证（2026-08-20）

在隔离的扩展 toy 副本中运行 `qc,normalize,family,promoter` 模块闭包，使用 4 个稳定基因、2 个物种、2 个亚家族、2 个群体和 4 种启动子元件。流程生成四个聚合层级的零值完整网格、显式分母、每基因/每 kb 命中率、逐元件总体 z-score（`ddof=0`）、QC 表、工作簿和四组 PDF/PNG 热图。

隔离运行的工程证据包括：四个聚合层级 QC 均为 `PASS`；40 行完整分布网格；缺失分母、单单元和零方差使用独立状态而不伪造信号；相同代码重跑只重建受代码指纹影响的规则，最终相同输入下的规范输出保持确定性。该示例只验证计算与文件合同，不支持启动子元件显著富集、调控因果、适应性或群体历史结论。

该启动子批次完成时的 51 项能力状态为 13 `IMPLEMENTED`、31 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、5 `NOT_SUPPORTED`；后续基因结构统计批次的最新口径见下一节与权威覆盖表。

## 基因结构分组统计本地验证（2026-08-20）

在 `temp_tests/gene-structure-statistics-20260820/` 隔离 toy 副本中运行 `qc,normalize,family,gene_structure,duplication` 依赖闭包。实际 Snakemake 9.25.1 运行完成 11/11 个步骤；代码变更后的定向复跑只重建 `gene_structure_metrics` 与 `duplication_classification` 两个受影响规则。

新增路径以 `species_id × group` 中位数作为推断单位，执行 Kruskal-Wallis、总体显著后才执行的两侧 Mann-Whitney U、每个比较范围与指标内的 BH-FDR，并输出秩二列效应量。隔离结果包含 gene_structure 的 12 行整体检验与 12 行两两比较，以及 duplication 的 6 行整体检验与 6 行两两比较；所有统计表均写明 `analysis_unit=SPECIES_MEDIAN`。toy 的 group 和 duplication mode 每组只有 1 个物种单元，因此 P 值按设计保持缺失并标记 `INSUFFICIENT_SPECIES_REPLICATION`；subfamily 指标在物种单元间无变异，整体检验标记 `ZERO_VARIANCE`。这些状态只验证边界处理，不构成组间无差异的生物学结论。

PDF/PNG 图件经人工复核：白底、无网格、物种中位数点可见，并在面板内明确显示推断暂停、低重复或无物种单元变异。对应单元、配置、规则/脚本合约和图件测试均已加入回归套件。

更新后的 51 项能力状态为 13 `IMPLEMENTED`、34 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、2 `NOT_SUPPORTED`。其中 5.3、5.6 和 8.5 仍是有条件可用，而不是无条件已实现；正式结论需要完整分组、每组足够物种单元，并评估系统发育与组成混杂。

## PDF/MD 模板等价性审计（2026-08-20）

对 29 页 `03-泛基因家族分析-模板.pdf` 与 `comparative_genomics_gene_family_workflow_20260807.md` 进行了只读逐图核对。PDF 的 Fig01–Fig34 归并为 33 条可审计记录（Fig21–22 共用一条），结果为 3 条 `MATCHED_CORE`、20 条 `PARTIAL`、9 条 `NOT_IMPLEMENTED` 和 1 条 `EXTERNAL_REQUIRED`。原 51 项能力目录还漏掉 7 类独立模板交付：群体 Ka/Ks、亚家族×群体 Ka/Ks、核心结构域 sequence logo、pan class Ka/Ks、群体×亚家族启动子、分组织 pan class 表达、群体×亚家族表达。

### 2026-08-21：模板完整性第二批

原 51 项目录遗漏的 7 类独立主题已全部加入权威矩阵与教程，形成 58 项连续清单。新增 family species×subfamily、pan-family gene/HOG 双分母与 species/subfamily 分层、duplication species/subfamily/pan-class 分层、Ka/Ks subfamily/group/pan-class/mode 描述性分层，以及 promoter group×subfamily 输出。隔离最小示例真实执行后产生 21 个 PDF，新增表的唯一键、分母闭合、Mixed/Unassigned 语义和 promoter 二维网格均通过检查；同命令复跑为 `Nothing to be done`。当前能力状态为 21 `IMPLEMENTED`、29 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、6 `NOT_SUPPORTED`；模板逐图状态为 11 `MATCHED_CORE`、15 `PARTIAL`、6 `NOT_IMPLEMENTED`、1 `EXTERNAL_REQUIRED`。该运行只验证工程与语义合同，不重算或替代 HSP 科学结果。

该审计证明“主题存在教程入口”不等于“模板图件、统计和交付合同已经实现”。逐图证据和修复优先级分别记录在 `TEMPLATE_FIGURE_EQUIVALENCE.tsv` 与 `TEMPLATE_EQUIVALENCE_AUDIT.zh-CN.md`，并已纳入 Pages 发布资产和回归测试。

本批次最终工程质量门为：Ruff lint 通过、84 个文件格式检查通过、mypy 对 8 个源码文件检查通过、`114 passed`、wheel/sdist 构建通过、Pages 离线站点构建和内部链接检查通过。该结果只验证当前软件合同与审计材料的一致性，不改变模板尚未完整实现的结论。

上述证据证明 toy 工程闭环和能力边界可审计，不替代真实水稻材料的生物学验收。正式多物种分析仍应固定目标 `N*` HOG node；不能把 toy 的 OG fallback、极短序列 Ka/Ks 或预计算 fixture 当作论文结果。

## 研究范围验证

标准配置固定为：

```yaml
project:
  analysis_scope: target_pan_gene_family

pan_family:
  # target-family HOG occupancy and classification
```

标准模块为 `pan_family`，不提供 `whole_genome` 分析范围。OrthoFinder 可在完整 canonical proteome 背景中推断 HOG，但最终占有率、Core/Soft-core/Shell/Cloud 分类和下游整合仅投影到已鉴定的目标家族成员。

## 独立仓库迁移验证

独立仓库必须同时满足：

```text
README.md               English entry
README.zh-CN.md         Simplified Chinese entry
docs/index.html         Chinese interactive beginner tutorial
.github/workflows/ci.yml
pyproject.toml           standalone Repository/Issues URLs
CITATION.cff             standalone repository-code URL
```

CI 还应阻断任何重新引入旧仓库克隆命令、旧仓库元数据或嵌套工作目录假设的提交。

## 尚未完成的生物学验收

软件工程验证不等于生物学结论已经得到验证。以下仍未完成：

- 5–10 个高质量水稻基因组及一个人工核验目标家族的端到端 benchmark；
- apparent absence 的 TBLASTN/miniprot、共线性区域和 assembly-gap 救援；
- OrthoFinder HOG node 的真实材料人工核验；
- DupGen 外群与复制类型稳定性评估；
- 大规模 Ka/Ks 分块、饱和过滤及统计独立性评估；
- 多材料 RNA-seq reference bias、批次和生物学重复验收；
- 来源模板全部图件的逐图复现。

因此当前独立仓库版本标记为 `v0.1.2-alpha`；在真实水稻目标家族 benchmark 完成前，不应被表述为生产级生物学结果流程。

## Three-group rice input smoke test

A user-provided GJ/XI/Wild Drive panel was sampled as GP523, GP543 and 534M. All twelve compressed genome/GFF3/protein/CDS files passed the actual PanFamFlow input-audit logic; genome sizes were 374,988,626–398,659,260 bp and annotations contained 39,081–39,511 genes. All three real genome archives also passed atomic decompression and immediate cache-reuse testing. GP523 requires GWH header/Accession namespace mapping, while GP543 and 534M use directly matching primary IDs. The committed `examples/rice_3group_pilot/` contains only metadata, checksums and audit evidence, not raw genomes or Drive file IDs.

This validates input feasibility for a three-genome engineering smoke test, not biological validation of any target family.

## 当前发布验收快照（2026-08-25）

PR #10 将 PDF/MD 差距闭合批次合并到 `main` 提交 `0179069f24f9fc212f4d9fe147ed2fada7acf2be`。权威 58 项能力矩阵当前为 53 `IMPLEMENTED`、5 `CONDITIONALLY_AVAILABLE`；条件项是核心结构域 Logo、全基因组共线性/Circos 和三类正式差异表达整合，均要求额外合规输入与运行门禁。

当前工程验收证据包括：`268 passed`；clean toy 61/61 步骤；Fig01–Fig34 的 PDF 与 600 dpi PNG；346 条结果 manifest；相同配置 no-op；三类隔离局部恢复；原生 DupGen_finder 与 JCVI 计算回执；24 个公共 RNA-seq 生物学样本、2 个数据集和 6 个 DESeq2 comparison 的既有固定证据；PR CI、main CI、Pages 部署和两个公开 URL 均通过。

该快照证明代码、运行合同、图表、教程与发布面闭合，不改变以下科学边界：toy、工程 benchmark 和公共数据复算均不自动证明任一新目标家族的功能、选择、适应性、调控因果或育种价值。
