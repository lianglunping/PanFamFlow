## 项目范围硬约束

```yaml
project:
  analysis_scope: target_pan_gene_family
```

该字段只接受 `target_pan_gene_family`。它用于阻止配置在不显式报错的情况下漂移到基因组组装、图泛基因组构建或全基因组 HOG 分类。

# `config.yaml` 说明

## 1. 设计原则

`config.yaml` 是唯一需要用户日常编辑的文件。配置通过 Pydantic 严格校验：字段拼写错误、未知模块、重复物种 ID、错误 outgroup、非法阈值顺序和模块所需输入缺失都会在运行前报告。

初始化项目后，编辑器可读取 `.panfamflow/config.schema.json` 完成补全和类型检查。

## 2. 顶层字段

| 字段 | 含义 |
|---|---|
| `schema_version` | 接受 `1.0` 和 `1.1`；旧配置不会被自动改写 |
| `project` | 项目名、根目录、随机种子和输出路径 |
| `run` | 模块、资源、engine、profile 和 Snakemake 参数 |
| `inputs` | 物种、RNA-seq 样本、表达矩阵与样本元数据 |
| `qc` | SHA256 与 BUSCO |
| `canonical_transcript` | canonical transcript 规则、后端与稳定 ID 分隔符 |
| `family` | HMM/BLAST/预计算证据与外部注释导入 |
| `phylogeny` | MAFFT/ClipKIT/IQ-TREE 参数 |
| `orthofinder` | HOG node 和线程 |
| `pan_family` | 目标家族 HOG 的四分类阈值与 rarefaction |
| `chromosome` | representative 筛选与 density window |
| `gene_structure` | 结构比较指标、物种中位数推断单位、最小物种单元数和显著性阈值 |
| `duplication` | DupGen_finder 或预计算 backend |
| `kaks` | pair source、reference species、方法和饱和阈值 |
| `promoter` | promoter 长度、FIMO/PlantCARE backend |
| `expression` | imported matrix 或 FASTQ/StringTie 路线 |
| `deliverables` | `legacy` 或 PDF/MD 完整交付 profile |
| `comparative_panel` | 外部比较物种面板；默认关闭且不得进入 pan-family 分母 |
| `domain_logo` | 核心结构域氨基酸 Logo；默认关闭 |
| `synteny` | 全基因组共线性/Circos 子路径；默认关闭 |
| `differential_expression` | raw-count 正式差异表达子路径；默认关闭 |
| `plot` | PDF/PNG 与 DPI |
| `report` | 报告标题和已有结果整合 |

## 3. 路径解析

除绝对路径外，所有路径均相对于 `project.root`。`project.root` 本身相对于配置文件所在目录解析。

```yaml
project:
  root: .
```

意味着 `data/Os/genome.fa` 对应 `config.yaml` 所在项目目录下的 `data/Os/genome.fa`。

## 4. 模块选择

```yaml
run:
  modules: [family, phylogeny, gene_structure]
```

CLI 会自动解析为 `qc → normalize → family → phylogeny/gene_structure`。

### 4.1 Schema 1.1 的安全默认值

Schema 1.1 只增加可选配置壳，不改变 12 个用户可见分析模块或旧 target 路径。以下高成本或证据敏感路径缺省均为 `false`：

```yaml
schema_version: "1.1"
deliverables:
  profile: legacy
comparative_panel:
  enabled: false
  include_in_pan_denominator: false
domain_logo:
  enabled: false
synteny:
  enabled: false
differential_expression:
  enabled: false
  input_scale: raw_counts
```

`deliverables.profile: pdf_md_complete` 表示请求完整的图、表、QC、manifest 和教程合同，但不会自动打开共线性或差异表达，也不会在输入不足时生成空白图。正式差异表达只接受非负整数 raw counts；TPM/FPKM 只能用于描述性表达图。完整字段、默认值和触发条件见 `docs/schemas/config_fields.tsv`。

临时覆盖：

```bash
uv run panfamflow run -c config.yaml -m promoter
```

## 5. 物种记录

```yaml
inputs:
  species:
    - id: Os
      name: Oryza_sativa
      genome: data/Os/genome.fa
      gff3: data/Os/annotation.gff3
      protein: null
      cds: null
      group: Cultivated
      subfamily: Oryza
      representative: true
      outgroup: Og
      busco_lineage: poales_odb12
```

约束：

- `id` 必须全局唯一，不能包含保留分隔符 `__`。
- `outgroup` 必须引用已配置物种，且不能指向自身。
- DupGen_finder target 必须有 outgroup。
- BUSCO 启用时每个物种必须配置 lineage。

### 5.1 Canonical transcript 后端

```yaml
canonical_transcript:
  method: longest_cds
  backend: agat
  sequence_source: gffread
  stable_id_separator: "__"
```

- `agat`（默认）：使用 `agat_sp_keep_longest_isoform.pl`，适合真实项目中来源复杂的 GFF3/GTF。实测 AGAT 1.7.0 在 macOS 会因读取 Linux `/proc` 失败而退出，因此该组合应在 Linux 容器或 Linux 计算节点运行。
- `portable_gff3`：跨平台的严格 GFF3 后端，仅接受明确的 `gene → transcript → CDS/exon`、`ID/Parent` 层级。它按 CDS 总长度选择转录本，同长时按 transcript ID 字典序选择；多父节点、重复 ID、未知父节点、CDS 重叠和内嵌 FASTA 会直接报错。

`portable_gff3` 不承担 AGAT 的注释清洗与纠错职责。真实注释若不能通过其严格校验，应修正输入或改用 Linux/AGAT，不能通过放宽校验强行继续。toy 示例为保证 macOS/Linux 都能复现，显式使用该后端。

## 6. 家族证据

```yaml
family:
  name: GPAT
  combine_evidence: intersection
  hmm:
    enabled: true
    hmm: references/PF01553.hmm
    evalue: 1.0e-5
    domain_evalue: 1.0e-3
  blast:
    enabled: true
    reference_proteins: references/known_GPAT.pep.fa
    evalue: 1.0e-5
    min_identity: 30
    min_query_coverage: 50
```

- `union`：HMM 或 BLAST 任一通过。
- `intersection`：两类证据均通过。
- `hmm_only`：只使用 HMM。
- `blast_only`：只使用 BLAST。
- `precomputed_members` 非空时直接以外部成员表为准，仍校验 stable ID。

外部表应优先包含 `stable_id`；也可包含 `species_id + gene_id`。

## 7. 泛基因家族占有率阈值

```yaml
pan_family:
  core_min: 0.99
  soft_core_min: 0.90
  shell_min: 0.10
```

只对包含 `family_members.tsv` 目标家族成员的 HOG 分类：

- `fraction >= core_min`：Core
- `soft_core_min <= fraction < core_min`：Soft-core
- `shell_min <= fraction < soft_core_min`：Shell
- `< shell_min`：Cloud

阈值必须满足 `core_min >= soft_core_min >= shell_min`。PanFamFlow 不接受 `whole_genome` scope；旧 `pangenome` 字段只在 `scope: target_family` 时自动迁移。

## 8. 基因结构组间统计

```yaml
gene_structure:
  metrics: [gene_length, protein_length, cds_length, exon_count, intron_count, total_intron_length]
  inference_unit: species_median
  min_group_units: 2
  alpha: 0.05
```

流程先在每个 `species_id × subfamily/group/duplication_mode` 单元内取中位数，再把这些物种单元用于整体和两两非参数检验。`min_group_units` 不能小于 2；任一比较组未达到阈值时，描述表和图仍会生成，但 P 值保持缺失并写入 `INSUFFICIENT_SPECIES_REPLICATION`。`alpha` 同时控制是否启动事后两两检验；多重校正在每个比较范围与指标内采用 BH-FDR。

这套默认值用于阻止把同一物种的多个家族基因当作独立生物学重复。正式多物种研究仍应根据物种关系、群体构成和预注册假设评估层级模型或系统发育校正。

## 9. expression 两种输入

### 导入矩阵

```yaml
inputs:
  expression_matrix: references/expression.tsv
expression:
  mode: imported_matrix
```

行 ID 优先使用 `stable_id`。若只使用 gene ID，必须在全体 family genes 中唯一，否则拒绝自动映射。

### FASTQ/StringTie

```yaml
inputs:
  rnaseq_samples:
    - id: Os_control_R1
      species_id: Os
      condition: Control
      tissue: Leaf
      replicate: 1
      strandedness: unstranded
      r1: data/rnaseq/Os_control_R1.fastq.gz
      r2: null
expression:
  mode: fastq_stringtie
```

v0.1 生成 TPM，不自动执行统计推断型差异表达。

## 10. 配置校验

```bash
uv run panfamflow validate -c config.yaml
uv run panfamflow validate -c config.yaml -m promoter
uv run panfamflow schema -o config.schema.json
```

错误导致退出码 2；warning 不阻止执行，但必须在正式分析记录中处理。

## 断点续跑相关字段（v0.1.1）

```yaml
run:
  resume_mode: smart
  keep_going: true
  rerun_incomplete: true
  latency_wait: 120
  retries: 1
  rerun_triggers: [mtime, input, params, code, software-env]
  printshellcmds: true
  show_failed_logs: true
```

- `resume_mode`：`smart`、`mtime_only` 或 `off`。推荐 `smart`。
- `keep_going`：某个 job 失败后，继续执行与它无依赖关系的 job；最终流程仍返回失败状态。
- `rerun_incomplete`：重跑被 Snakemake 标记为 incomplete 的 job。
- `latency_wait`：网络文件系统上等待输出可见的秒数。
- `retries`：单个 job 的额外自动重试次数。格式错误和配置错误不会因重试而自行修复，因此不宜设置过大。
- `rerun_triggers`：决定输出何时因输入、参数、代码、环境或 mtime 变化而失效。
- `printshellcmds`：记录实际命令。
- `show_failed_logs`：失败时显示规则日志。

查看状态：

```bash
uv run panfamflow status -c config.yaml
```

修复问题后恢复：

```bash
uv run panfamflow resume -c config.yaml
```

完整语义见 [RESUME.md](RESUME.md)。

## gzip 输入

`genome`、`gff3`、`protein` 和 `cds` 可以使用 `.gz`。Python 审计脚本直接流式读取 gzip；需要调用 AGAT、gffread 或 BUSCO 的规则会先在 `work/` 中原子解压，并在失败重试时复用完整的 staged 文件。原始压缩文件不会被覆盖。

真实示例见 `examples/rice_3group_pilot/`。
