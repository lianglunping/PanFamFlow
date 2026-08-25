# PanFamFlow 中文教程整合审计（2026-08-20）

## 结论

GPT-5.6 Pro v2 提供的原 51 项、八章、四维教学结构被采用；PDF 逐图审计发现的 7 项目录遗漏已补入，形成 58 项权威清单。其旧实现状态和 runtime blocker 叙述没有直接照搬；当前 `docs/ANALYSIS_COVERAGE.tsv`、本地源码和隔离 toy 实跑是最终判定依据。

当前权威状态为 53 `IMPLEMENTED`、5 `CONDITIONALLY_AVAILABLE`。58 项均有教学入口、执行或条件门禁、规范输出和结论边界；工程实现仍不等于任意真实材料已经完成生物学验证。

## 主要校正

1. OrthoFinder result pointer 已统一为 `orthofinder_result_dir.txt`，旧 blocker 已消失。
2. promoter 的 `input.gff3s`、separator、outputs 与 report 路径已统一并完成 toy 实跑。
3. `hog_node:auto` 优先公开 HOG；无公开 HOG 表时仅可回退公开 OG，并输出 `ORTHOGROUP`、`AUTO_ORTHOGROUP_FALLBACK`、`ORTHOFINDER_ORTHOGROUP`。显式 N* 缺失时 fail closed。
4. clean toy 已完成 61/61 步骤、Fig01–Fig34、346 条结果 manifest、相同配置 no-op 和三类隔离局部恢复；全部图件均有 PDF 和 600 dpi PNG。
5. 启动子多维分布现已冻结分母、零值网格、每 kb 命中率与逐元件总体 z-score；物种层输出为直接实现，依赖亚家族或群体元数据的输出保持条件可用。
6. 其余 5 项保持有条件可用：核心结构域 Logo（4.4）、全基因组共线性/Circos（8.6）以及 Global、非生物胁迫和生物胁迫差异表达（11.3–11.5）。它们已有规范路径，但只有在对应开关、原始输入、重复、设计、参考和 provenance 门禁通过后才能声明本次分析完成。

## 科学边界

- toy 的两物种 OG fallback 不等于正式 N* HOG。
- annotation absence 不等于 validated gene loss。
- pairwise Ka/Ks，尤其 toy 中极低 Ks 对应的高比值，不是正选择证明。
- precomputed duplication、motif 和 expression fixture 只验证工程路径。
- motif hit 不等于 TF binding；TPM 热图不等于 raw-count 差异表达。

## 可追溯文件

- `docs/ANALYSIS_COVERAGE.tsv`：当前权威能力状态。
- `docs/TUTORIAL_CONTENT_MATRIX.tsv`：58 项完整教学合同。
- `docs/TUTORIAL_TOY_EVIDENCE_SCHEMA.tsv`：逐产物真实证据状态。
- `docs/VALIDATION.md`：本地全模块运行和质量门记录。
