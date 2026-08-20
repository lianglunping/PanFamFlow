# PanFamFlow 中文教程整合审计（2026-08-20）

## 结论

GPT-5.6 Pro v2 提供的原 51 项、八章、四维教学结构被采用；PDF 逐图审计发现的 7 项目录遗漏已补入，形成 58 项权威清单。其旧实现状态和 runtime blocker 叙述没有直接照搬；当前 `docs/ANALYSIS_COVERAGE.tsv`、本地源码和隔离 toy 实跑是最终判定依据。

状态为 21 `IMPLEMENTED`、29 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、6 `NOT_SUPPORTED`。这表示 58 项均有教学入口，不表示 58 项均已由 pipeline 原生实现。

## 主要校正

1. OrthoFinder result pointer 已统一为 `orthofinder_result_dir.txt`，旧 blocker 已消失。
2. promoter 的 `input.gff3s`、separator、outputs 与 report 路径已统一并完成 toy 实跑。
3. `hog_node:auto` 优先公开 HOG；无公开 HOG 表时仅可回退公开 OG，并输出 `ORTHOGROUP`、`AUTO_ORTHOGROUP_FALLBACK`、`ORTHOFINDER_ORTHOGROUP`。显式 N* 缺失时 fail closed。
4. toy 已跑通 13 模块、二次 no-op、缺失子输出定向重建及 80 个 manifest 哈希核对；未生成的 DAG SVG、外部 DE 和专用失败归档保持未捕获状态。
5. 启动子多维分布现已冻结分母、零值网格、每 kb 命中率与逐元件总体 z-score；物种层输出为直接实现，依赖亚家族或群体元数据的输出保持条件可用。
6. 亚家族、群体和复制类型的基因结构比较现在具有统一的物种中位数推断路径、整体检验、条件性两两检验、BH-FDR、效应量和 QC；由于仍依赖完整分组与足够物种重复，5.3、5.6、8.5 判为 `CONDITIONALLY_AVAILABLE`。当前仅共线性 Circos（8.6）与 Global DEG overlap（11.3）保持 `NOT_SUPPORTED`。

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
