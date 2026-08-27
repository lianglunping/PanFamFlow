# PanFamFlow 教程仓库集成与浏览器 QA

## 集成基线

- Pro 教程内容基线：`eebe5af5f58de3b932bc54a2b1b540579053889b`。
- `main` 发布基线为 PR #11 合并提交 `19199a79cd99427d19712c81cc92888231a30287`；Pro 内容基线只记录来源，不冒充当前发布 revision。
- Pro ZIP SHA256：`a33d9f9e78e4830e6e291c5db11d934d94c30db1e515a12dd99a9f8444d1f7a4`；manifest 逐文件哈希和大小均通过。

## 本地验收结果

2026-08-27 的 Pages 触发与运行时加固分支本地验收结果：

- Ruff lint 与格式检查通过；
- mypy strict 检查通过；
- `278 passed`；
- wheel 与 sdist 构建通过；
- Pages 构建和内部链接检查通过；
- 10 个教程矩阵/审计附件全部进入 Pages 白名单和部署触发范围，并通过内部链接与敏感路径检查；
- PR #11 部署教程内容 SHA256 为 `2f0837e1c8282af151ddd20662e1b6d9c234f14a7f354a32c60f5bbc629bd35d`；
- 58 项状态与权威能力矩阵逐行一致，当前为 53 `IMPLEMENTED`、5 `CONDITIONALLY_AVAILABLE`；
- 无已停用自定义域名、旧 result-pointer 文件名或 toy 待回填占位。

## 浏览器验收状态

交付包原始页面曾通过其自带的 Chromium 桌面/移动测试；本地适配后的最终 `file://` 页面被 Codex 应用浏览器 URL 安全策略拒绝自动控制，因此没有把当前页面的可视化截图、真实 viewport 宽度或 console 记录标为通过。当前替代证据是 HTML parser、自包含资源、ARIA/响应式保护、交互脚本回归测试以及 Pages 链接审计。

PR #11 的 exact-head CI、合并后 `main` CI 和 Pages 部署均已通过；本次加固仍须以新 PR 的 exact-head CI、合并后部署及公开 URL 的 HTTP 200/内容标记作为最终门禁。自动化证据仍不替代真实桌面/手机的人工可用性抽查，也不把工程通过提升为生物学验证。
