# CDD、WoLF PSORT 与 PlantCARE 外部结果导入合同

PanFamFlow 不会伪装成 NCBI CDD、WoLF PSORT 或 PlantCARE 的本地替代品。这三类网页或数据库结果必须由用户在对应服务中完成分析后，以可审计表格导入。流程负责稳定 ID 映射、字段与来源检查、结果合并和边界声明，不负责替代外部服务的算法。

## 1. 为什么必须保存来源字段

只有结果列而没有服务名称、版本、访问日期和 URL 的复制粘贴表，无法证明结果来自哪次查询，也无法在数据库更新后复核。正式项目建议在 `family.external_import_validation` 或 `promoter.external_import_validation` 中使用 `strict`：

```yaml
family:
  external_import_validation: strict
  domain_validation_table: references/cdd.tsv
  subcellular_localization_table: references/wolf_psort.tsv
promoter:
  backend: precomputed_plantcare
  external_import_validation: strict
  precomputed_table: references/plantcare.tsv
```

`legacy` 只用于兼容早期表格；它不会补造缺失来源，也不应作为新的正式分析默认值。

## 2. 三类表的最小字段

三类表都优先使用 `stable_id`。CDD 与 WoLF PSORT 也可用 `species_id + gene_id`；PlantCARE 也可用 `sequence_id`，但必须能唯一映射到已提取的目标家族启动子。

| 证据类型 | 结果字段（至少一项） | strict 模式共同来源字段 |
|---|---|---|
| NCBI CDD | `domain`、`domain_accession`、`cdd_accession` 或 `status` | `evidence_source`、`source_version`、`accessed_date`、`source_url` |
| WoLF PSORT | `localization`、`prediction` 或 `compartment` | 同上 |
| PlantCARE | `element`、`motif_id` 或 `cis_element` | 同上 |

`accessed_date` 必须使用 `YYYY-MM-DD`；`source_url` 必须是 HTTP(S) 地址；`evidence_source` 必须能够识别相应服务。模板位于：

- `examples/external_import_templates/cdd.tsv`
- `examples/external_import_templates/wolf_psort.tsv`
- `examples/external_import_templates/plantcare.tsv`

## 3. 导入后怎么读

- CDD 结果用于补充结构域验证证据；它不能单独证明基因的体内功能。
- WoLF PSORT 是亚细胞定位预测；它不能替代荧光定位、分级实验或其他实验验证。
- PlantCARE 元件是序列命中或数据库注释；motif hit 不是 TF 真实结合，更不是调控因果或显著富集。
- 所有外部结果必须先检查 ID 闭合、重复记录、空值、来源版本和访问日期，再与 `family_members.tsv` 或 `promoter_coordinates.tsv` 连接。

模板行只是字段示例，不是水稻研究结果；正式数据不得把示例行混入分析。
