# PanFamFlow GitHub Pages 根因报告

审计日期：2026-08-18（Asia/Shanghai）  
审计基线：`main@06903f39dfab8ee1e454fe35eb7b48032a5781a3`

## 结论

首次 Pages 部署失败的直接根因是：仓库尚未启用 GitHub Pages，而 `actions/configure-pages@v5` 在 `enablement: true` 下尝试使用 workflow `GITHUB_TOKEN` 创建 Pages site；该 token 不具备仓库级 Pages enablement 所需的管理权限，GitHub 返回 `Resource not accessible by integration`。

此外，设置页保留了未正确配置的自定义域名 `llp98.work`，GitHub 明示 HTTPS 不可用。这不是首次 workflow 在 Configure Pages 步骤失败的直接原因，但会使验收指定的默认项目 URL `https://lianglunping.github.io/PanFamFlow/` 发生错误重定向或证书路径异常，必须作为独立配置债务处理。

## 原始失败信息

- Workflow：`Deploy PanFamFlow tutorial`
- Workflow run：`31958304609`
- Run URL：<https://github.com/lianglunping/PanFamFlow/actions/runs/31958304609>
- Job：`deploy`
- Job ID：`95192287726`
- Head SHA：`06903f39dfab8ee1e454fe35eb7b48032a5781a3`
- 失败步骤：`Configure Pages`
- 后续 `Upload static site` 与 `Deploy` 步骤：均为 `skipped`

日志中的关键事实：

1. workflow token 权限为 `Contents: read`、`Pages: write`；
2. `Get Pages site` 返回 `Not Found`；
3. 随后 `Create Pages site` 返回 `Resource not accessible by integration`；
4. 失败发生在 artifact 构建和部署之前。

## 根因

`pages.yml` 将 `enablement: true` 交给默认 `GITHUB_TOKEN`。GitHub 官方 `configure-pages` action 对该参数的说明是：尝试启用 Pages 需要高于默认 workflow token 的权限；GitHub App 上下文需要 `administration:write` 与 `pages:write`。本次 token 只有 `pages:write`，因此无法创建 Pages site。

仓库设置的实测状态与日志一致：

- GitHub Pages：disabled；
- Source：`Deploy from a branch`；
- Branch：`None`；
- 自定义域名：`llp98.work`；
- HTTPS：因域名配置错误而 unavailable。

## 已排除的替代原因

| 候选原因 | 证据与判断 |
|---|---|
| 上传仓库根目录 `.` 导致本次失败 | 排除为直接根因：上传步骤在 Configure Pages 失败后被跳过。但它会扩大公开面，仍需修复。 |
| `deploy-pages` OIDC 权限缺失 | 排除为本次直接根因：workflow 已声明 `pages: write` 与 `id-token: write`，且 Deploy 步骤尚未运行。 |
| checkout 失败或 SHA 不一致 | 排除：checkout 成功并记录精确 SHA `06903f39…`。 |
| environment 人工 approval 阻塞 | 排除为首次失败原因：失败在 Configure Pages，尚未进入 deployment；修复后仍需独立检查 environment rules。 |
| CNAME 文件污染 | 代码搜索未发现仓库中的 `CNAME`。设置层残留自定义域名仍需移除。 |
| Pages artifact 大小、符号链接或 tar 结构错误 | 首次运行没有生成/上传 artifact，无法成为该次失败原因；修复后由独立 `_site/` 构建与 manifest 检查覆盖。 |

## 最小修复方案

1. 由仓库管理员在 Settings → Pages 将 source 设为 `GitHub Actions`；不再让 workflow 自行 enable Pages。
2. 从 `configure-pages` 移除 `enablement: true`。
3. 以 `site/` 为受控静态源，构建 `_site/`；只复制首页、教程和必需静态资源，并加入 `.nojekyll`。
4. `upload-pages-artifact` 只上传 `_site/`，不上传仓库根目录。
5. 对 `/PanFamFlow/` 基路径、站内链接、HTTP 混合内容和禁止发布目录执行 fail-closed 检查。
6. 移除失效的 `llp98.work` 自定义域名，使正式入口回到 GitHub 默认项目站点。
7. 在修复分支、PR head 和合并后的 main head 分别记录 exact-SHA CI、Pages run、deployment 与 HTTP 验收证据。

## 风险

- 自定义域名移除是可逆设置变更，但会停止 GitHub 对 `llp98.work` 的重定向；本项目验收明确要求默认 `github.io/PanFamFlow/`，因此这是预期行为。
- Pages deployment 只能证明工程发布成功，不能改变 HSP 科学结果或 benchmark 的 `BLOCKED` 状态。
- 外部 Google Drive 链接可能受共享权限、账号登录或 Google 风控影响；必须用第三方会话逐项复验。

## 验收证据

以下项目仅在获得真实结果后填写，不预先声明成功：

- 修复 PR：待创建
- PR head SHA：待生成
- CI run：待运行
- Pages run：待运行
- github-pages deployment：待运行
- 公共首页 HTTP 200：待验证
- `/PanFamFlow/tutorial/` HTTP 200：待验证
- 合并后 main exact-head 复验：待完成
