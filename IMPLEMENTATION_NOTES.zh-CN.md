# PanFamFlow GPT-5.6 Pro 教程整合说明

本地整合采用“Pro 丰富教程结构 + 当前源码/能力矩阵校正 + 真实 toy 证据回填”。没有修改来源 MD/PDF，没有重算 HSP，没有覆盖原始数据，也没有提交、推送或部署。

建议验证：

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
uv run python scripts/build_pages_site.py --output /tmp/panfamflow-pages
```

页面发布前还必须在最终 revision 上复核 GitHub Actions 和 Pages；当前只完成本地工作树验收。

## 2026-08-20 中文可读性分层

本轮接收并逐字节核验了 GPT-5.6 Pro 的有界交付包，仅整合 `docs/index.html`、`docs/TUTORIAL_TERMINOLOGY.tsv` 和新增语言回归测试。Pro 交付的 4 个 manifest 文件均通过 SHA256 与字节数核对，完整仓库上下文中的教程测试在隔离副本通过。

本地复核又修正了两类容易误导初学者的遗留词：

- 原资料中的 `OGG` 不再作为页面主标题；教程明确要求根据 `orthology_group_type` 判定实际对象是 HOG 或 OG，不能把 OGG 当作第三种规范数据类型。
- `toy`、`fixture` 不再作为醒目教学标签；默认文字改为“专门构造的极小测试数据”，并继续声明它只验证流程与文件合同，不替代真实水稻材料和生物学验收。

本轮没有改变任何分析条目的能力状态，没有修改 pipeline、配置、schema、原始数据或依赖，也没有提交、推送或部署。
