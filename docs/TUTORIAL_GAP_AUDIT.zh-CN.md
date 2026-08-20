# PanFamFlow 中文教程整合审计（2026-08-20）

## 结论

GPT-5.6 Pro v2 提供的 51 项、八章、四维教学结构被采用；其旧实现状态和 runtime blocker 叙述没有直接照搬。当前 `docs/ANALYSIS_COVERAGE.tsv`、本地源码和 2026-08-19 全模块 toy 实跑是最终判定依据。

状态为 11 `IMPLEMENTED`、29 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、9 `NOT_SUPPORTED`。这表示 51 项均有教学覆盖，不表示 51 项均已由 pipeline 原生实现。

## 主要校正

1. OrthoFinder result pointer 已统一为 `orthofinder_result_dir.txt`，旧 blocker 已消失。
2. promoter 的 `input.gff3s`、separator、outputs 与 report 路径已统一并完成 toy 实跑。
3. `hog_node:auto` 优先公开 HOG；无公开 HOG 表时仅可回退公开 OG，并输出 `ORTHOGROUP`、`AUTO_ORTHOGROUP_FALLBACK`、`ORTHOFINDER_ORTHOGROUP`。显式 N* 缺失时 fail closed。
4. toy 已跑通 13 模块、二次 no-op、缺失子输出定向重建及 80 个 manifest 哈希核对；未生成的 DAG SVG、外部 DE 和专用失败归档保持未捕获状态。
5. 模板中的两两统计、scale 标准化、共线性 Circos、Global DEG overlap 等未实现项保持 `NOT_SUPPORTED`；可由基础表连接但没有专用结果的条目保持条件可用。

## 科学边界

- toy 的两物种 OG fallback 不等于正式 N* HOG。
- annotation absence 不等于 validated gene loss。
- pairwise Ka/Ks，尤其 toy 中极低 Ks 对应的高比值，不是正选择证明。
- precomputed duplication、motif 和 expression fixture 只验证工程路径。
- motif hit 不等于 TF binding；TPM 热图不等于 raw-count 差异表达。

## 可追溯文件

- `docs/ANALYSIS_COVERAGE.tsv`：当前权威能力状态。
- `docs/TUTORIAL_CONTENT_MATRIX.tsv`：51 项完整教学合同。
- `docs/TUTORIAL_TOY_EVIDENCE_SCHEMA.tsv`：逐产物真实证据状态。
- `docs/VALIDATION.md`：本地全模块运行和质量门记录。
