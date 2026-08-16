# 水稻 HSP 六材料真实输入试运行

本目录定义一个不提交原始基因组/蛋白组的真实数据试运行，用于验证 PanFamFlow 对热激蛋白（HSP）目标泛基因家族的成员发现与审计能力。

## 生物学范围

HSP 不是一个单一同源家族。本试运行将以下六类作为相互独立的分析单元：

- HSP20/sHSP：PF00011；
- HSP40/DnaJ：PF00226；
- HSP60/chaperonin：PF00118；
- HSP70：PF00012；
- HSP90：PF00183；
- HSP100/ClpB-like：PF10431，并要求 PF00004 与 PF07724 支持双 AAA 架构。

禁止把六类蛋白合并构建一棵“HSP 总树”，也禁止跨六类直接计算 Ka/Ks。

## 材料面板

样本信息来自用户提供的 `sample_info.csv`，仅提交本试运行所需的六条最小化记录：

| 生物学分组 | 材料 | 分类 |
|---|---|---|
| `Oryza_sativa_indica` | 534M、Gla4 | *Oryza sativa* indica group |
| `Oryza_sativa_japonica` | GP523、GP680 | *Oryza sativa* japonica group |
| `Oryza_longistaminata` | OL2296 | 独立野生稻物种 |
| `Oryza_meridionalis` | OM1952 | 独立野生稻物种 |

Drive 中的 `Wild` 是存储目录名，不直接等同于物种或分析群体。此前用于工程 QC 的 GP543/GP635 在样本表中标注为 `intermediate`，因此不再作为野生稻物种代表。

## 输入与隐私

- 原始蛋白组由一次性 CI 作业从用户授权的 Drive 文件夹中按文件名解析和下载；
- Git 仓库不提交原始蛋白组、基因组、GFF3、CDS、Drive 文件 URL 或文件 ID；
- `source_receipt.tsv` 只保存来源文件 SHA256、选择口径和所选材料；
- `sample_metadata.tsv` 保存可审计的六材料元数据。

## 输出解释

候选分为：

- `HIGH_CONFIDENCE`：主 Pfam HMM、MSU 参考蛋白 BLAST 和家族结构规则均通过；
- `HMM_ONLY_REVIEW`：主 HMM 通过，但无 BLAST 支持；
- `ARCHITECTURE_REVIEW`：主 HMM 存在，但长度、motif 或域顺序需人工复核；
- `ARCHITECTURE_REJECT`：与定义冲突；
- `BLAST_ONLY_REJECT`：仅有 BLAST、缺失主 Pfam domain。

这些结果仍是工程/生物信息学候选，不替代人工审阅、实验验证和正式 HOG/pan-family 推断。
