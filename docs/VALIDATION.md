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

同一工作树最终质量门为：Ruff lint 通过、Ruff format 通过、mypy strict 通过、`71 passed`、wheel/sdist 构建通过、Pages 最小站点构建和内部链接检查通过。来源 MD 与 29 页 PDF 模板中的 51 个分析条目均进入 `ANALYSIS_COVERAGE.tsv` 和中文教程；状态分布为 11 `IMPLEMENTED`、29 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、9 `NOT_SUPPORTED`。

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
