# 水稻三组真实数据工程测试

本目录用于验证 PanFamFlow 对用户提供的 **GJ（粳稻组）/ XI（籼稻组）/ Wild（野生稻组）** 已组装基因组数据的输入审计、gzip 兼容、断点续跑和局部恢复。

## 重要边界

- 这是 **3 个基因组/材料的工程 smoke test**，不是论文级生物学 benchmark。
- 文件夹名支持 `GJ / XI / Wild` 分组，但仅凭文件名不能确认正式物种学名、assembly accession 和 annotation version。
- 目标基因家族尚未冻结，因此当前只允许执行 `qc`。不要把占位家族用于真实家族结论。
- 5–10 个高质量基因组、目标家族 HMM/参考蛋白、人工正负例和正式 HOG 节点仍是完整生物学验收的要求。

## 选取的三个基因组

| 分组 | 材料/前缀 | 输入 |
|---|---|---|
| GJ | GP523 | genome、GFF3、protein、CDS |
| Wild | GP543 | genome、GFF3、protein、CDS |
| XI | 534M | genome、GFF3、protein、CDS |

原始数据不进入 Git 仓库。`source_manifest.tsv` 只记录文件名、大小和 SHA256；Drive URL 与文件 ID不在公开仓库中提交。

## 数据摆放

```text
data/
├── GJ_GP523/
│   ├── GP523.fa.gz
│   ├── GP523.gff3.gz
│   ├── GP523_pep.fa.gz
│   └── GP523_cds.fa.gz
├── Wild_GP543/
│   ├── GP543.fa.gz
│   ├── GP543.gff3.gz
│   ├── GP543_pep.fa.gz
│   └── GP543_cds.fa.gz
└── XI_534M/
    ├── 534M.fa.gz
    ├── 534M.gff3.gz
    ├── 534M_pep.fa.gz
    └── 534M_cds.fa.gz
```

## 执行输入审计

```bash
uv run panfamflow validate -c examples/rice_3group_pilot/config.yaml -m qc
uv run panfamflow run -c examples/rice_3group_pilot/config.yaml -m qc
```

第二次执行相同命令时，完整且仍有效的结果应自动跳过：

```bash
uv run panfamflow resume -c examples/rice_3group_pilot/config.yaml -m qc
```

## 已发现的真实数据兼容性问题

`GP543` 和 `534M` 的 protein/CDS/GFF transcript 主 ID 可以直接对应。`GP523` 使用三套 GWH accession 主键：

```text
protein: GWHP*
CDS/mRNA: GWHT*
gene: GWHG*
GFF ID: evm.model* / evm.TU*
```

映射信息存在于 FASTA header 的 `mRNA= / Protein= / Gene= / OriID=` 以及 GFF 的 `Accession / Parent_Accession` 字段中。因此不能用“主 ID 字符串必须完全相等”的简单规则判断 GP523 数据不一致。

输入审计结果见：

```text
audit/pilot_summary.tsv
audit/id_compatibility.tsv
source_manifest.tsv
```
