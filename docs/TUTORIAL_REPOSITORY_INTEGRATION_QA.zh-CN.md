# PanFamFlow 教程仓库集成与浏览器 QA

## 集成基线

- Pro 教程内容基线：`eebe5af5f58de3b932bc54a2b1b540579053889b`。
- 当前工作树包含未提交的 pipeline 修复与教程整合；页面不会把基线 SHA 冒充当前已发布 revision。
- Pro ZIP SHA256：`a33d9f9e78e4830e6e291c5db11d934d94c30db1e515a12dd99a9f8444d1f7a4`；manifest 逐文件哈希和大小均通过。

## 本地验收结果

2026-08-20 的最终工作树验收结果：

- Ruff lint 与格式检查通过；
- mypy strict 检查通过；
- `90 passed`；
- wheel 与 sdist 构建通过；
- Pages 构建和内部链接检查通过；
- 6 个教程矩阵/审计附件与源文件逐字节一致；
- 教程 HTML 为 378,700 bytes，构建后 SHA256 为 `459ea2852f2e9cb8883c54b28625f766f3ba97b4bfa3628917e4be04fbb2831a`；
- 58 项状态与权威能力矩阵逐行一致，章节汇总为 21 `IMPLEMENTED`、29 `CONDITIONALLY_AVAILABLE`、2 `EXTERNAL_IMPORT`、6 `NOT_SUPPORTED`；
- 无已停用自定义域名、旧 result-pointer 文件名或 toy 待回填占位。

## 浏览器验收状态

交付包原始页面曾通过其自带的 Chromium 桌面/移动测试；本地适配后的最终 `file://` 页面被 Codex 应用浏览器 URL 安全策略拒绝自动控制，因此没有把当前页面的可视化截图、真实 viewport 宽度或 console 记录标为通过。当前替代证据是 HTML parser、自包含资源、ARIA/响应式保护、交互脚本回归测试以及 Pages 链接审计。

远程 GitHub Pages 尚未部署；本地通过不能替代最终 revision 上的 GitHub Actions、远程 Pages 与人工桌面/手机验收。
