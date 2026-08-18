# PanFamFlow GitHub Pages 根因报告

审计日期：2026-08-18—2026-08-19（Asia/Shanghai）  
审计基线：`main@06903f39dfab8ee1e454fe35eb7b48032a5781a3`

## 结论

首次 Pages 部署失败的直接根因是：仓库尚未启用 GitHub Pages，而 `actions/configure-pages@v5` 在 `enablement: true` 下尝试使用 workflow `GITHUB_TOKEN` 创建 Pages site；该 token 不具备仓库级 Pages enablement 所需的管理权限，GitHub 返回 `Resource not accessible by integration`。

此外，账号的用户站点仓库 `lianglunping/lianglunping.github.io` 在默认分支 `hexo` 中发布了 `CNAME=llp98.work`。GitHub Pages 将这个账号级自定义域名继承到项目站点，因此 `https://lianglunping.github.io/PanFamFlow/` 会重定向到 `http://llp98.work/PanFamFlow/`，而 PanFamFlow 的 Pages 设置页显示 HTTPS 不可用。这不是首次 workflow 在 Configure Pages 步骤失败的直接原因，而是另一个独立的账号级配置问题；修复它会影响该账号下的用户站点及其他项目站点，不能当作 PanFamFlow 仓库内的普通文件修复。

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

修复前仓库设置的实测状态与日志一致：

- GitHub Pages：disabled；
- Source：`Deploy from a branch`；
- Branch：`None`；
- 项目仓库自定义域名输入框：空；
- Pages 对外地址：继承为 `http://llp98.work/PanFamFlow/`；
- HTTPS：因继承域名未正确配置而 unavailable。

账号级域名来源经 GitHub API 只读核验：

- 仓库：`lianglunping/lianglunping.github.io`；
- 默认分支：`hexo`；
- `CNAME` blob SHA：`e64938fc93c2ee58f0105e2f28ac0e47a7da4f33`；
- `CNAME` 内容：`llp98.work`。

## 已排除的替代原因

| 候选原因 | 证据与判断 |
|---|---|
| 上传仓库根目录 `.` 导致本次失败 | 排除为直接根因：上传步骤在 Configure Pages 失败后被跳过。但它会扩大公开面，仍需修复。 |
| `deploy-pages` OIDC 权限缺失 | 排除为本次直接根因：workflow 已声明 `pages: write` 与 `id-token: write`，且 Deploy 步骤尚未运行。 |
| checkout 失败或 SHA 不一致 | 排除：checkout 成功并记录精确 SHA `06903f39…`。 |
| environment 人工 approval 阻塞 | 排除为首次失败原因：失败在 Configure Pages，尚未进入 deployment。后续实测发现 `github-pages` environment 只允许 `main`，因此修复分支首次部署另行失败；临时加入精确修复分支后，同一 run 重试成功。 |
| PanFamFlow 仓库内 `CNAME` 污染 | 排除：代码搜索未发现 PanFamFlow 仓库中的 `CNAME`，项目设置页输入框也为空。重定向来自用户站点仓库的账号级 `CNAME`。 |
| Pages artifact 大小、符号链接或 tar 结构错误 | 首次运行没有生成/上传 artifact，无法成为该次失败原因；修复后由独立 `_site/` 构建与 manifest 检查覆盖。 |

## 最小修复方案

1. 由仓库管理员在 Settings → Pages 将 source 设为 `GitHub Actions`；不再让 workflow 自行 enable Pages。
2. 从 `configure-pages` 移除 `enablement: true`。
3. 以 `site/` 为受控静态源，构建 `_site/`；只复制首页、教程和必需静态资源，并加入 `.nojekyll`。
4. `upload-pages-artifact` 只上传 `_site/`，不上传仓库根目录。
5. 对 `/PanFamFlow/` 基路径、站内链接、HTTP 混合内容和禁止发布目录执行 fail-closed 检查。
6. 经用户明确授权后，通过独立 PR 移除 `lianglunping/lianglunping.github.io` 的 `CNAME=llp98.work`；该跨仓库变更不混入 PanFamFlow PR。
7. 在修复分支、PR head 和合并后的 main head 分别记录 exact-SHA CI、Pages run、deployment 与 HTTP 验收证据。

## 修复分支实测

- 修复分支：`fix/github-pages-deployment-v0.1.3`
- 首个修复提交：`42cbb302b828882e4492bf374c430fdbb76668a7`
- PR：<https://github.com/lianglunping/PanFamFlow/pull/1>
- exact-head CI：<https://github.com/lianglunping/PanFamFlow/actions/runs/32155974837>，结论 `success`
- 分支 Pages：<https://github.com/lianglunping/PanFamFlow/actions/runs/32157464159>
  - attempt 1：构建和 artifact 成功，部署因 `github-pages` environment 仅允许 `main` 而失败；
  - 临时增加精确分支规则后重试：`build` job `95780876729` 成功，`deploy` job `95780876385` 成功。

这些结果证明仓库内 workflow、受控 `_site/` artifact 和 Pages deployment 链路已经可运行；它们不能证明账号级自定义域名已经修复，也不能替代合并后 `main` exact-head 的最终复验。临时修复分支规则必须在合并验证完成后移除。

## 账号级域名修复实测

- 用户授权：2026-08-19（Asia/Shanghai）明确授权处理账号级 Pages 自定义域名；
- 用户站点 PR：<https://github.com/lianglunping/lianglunping.github.io/pull/1>；
- 删除 `CNAME` 的精确提交：`95ae2d3a7c071f148d840c30595c4b73637bd2ca`；
- 合并后的 `hexo` head：`04a188c948a3a80cc6d8a9bf4c3b6ae8d74f1303`；
- 用户站点 Pages run：<https://github.com/lianglunping/lianglunping.github.io/actions/runs/32167770598>；
- 合并后 `hexo:CNAME`：GitHub Contents API 返回 `404 Not Found`；
- 设置页：正式地址恢复为 `https://lianglunping.github.io/`，自定义域名输入框为空，HTTPS redirect 已启用。

PanFamFlow 当前 PR head 的 CI 已通过；为绕过 GitHub 手动触发控件的加载错误，使用默认分支上的一次性、精确分支 Pages 验证 workflow 生成 PR-head 部署证据。该 workflow 与临时分支触发器必须在最终清理 PR 中一并移除。

## 风险

- 账号级自定义域名变更已获得明确授权并通过独立 PR 执行；原 `CNAME` 可由 blob `e64938fc93c2ee58f0105e2f28ac0e47a7da4f33` 或父提交 `49a9dfe131436344ce003b3145e2e4195fa46a08` 恢复。
- Pages deployment 只能证明工程发布成功，不能改变 HSP 科学结果或 benchmark 的 `BLOCKED` 状态。
- 外部 Google Drive 链接可能受共享权限、账号登录或 Google 风控影响；必须用第三方会话逐项复验。

## 验收证据

以下项目仅在获得真实结果后填写，不预先声明成功：

- 修复 PR：<https://github.com/lianglunping/PanFamFlow/pull/1>（draft，待最终验证）
- 当前已验证 PR head SHA：`9f76cb1ec6fd7a7bbc00f1cdc6868acce5d15fce`（本报告更新提交后需对新 head 重跑）
- CI run：<https://github.com/lianglunping/PanFamFlow/actions/runs/32168187657>（成功；本报告更新提交后需对新 head 重跑）
- Pages run：<https://github.com/lianglunping/PanFamFlow/actions/runs/32157464159>（重试成功；本报告更新后需对新 head 重跑）
- github-pages deployment：分支级部署链路已成功；账号级域名已移除；当前 PR exact-head 和最终 main exact-head 仍需复验
- 公共首页 HTTP 200：待验证
- `/PanFamFlow/tutorial/` HTTP 200：待验证
- 合并后 main exact-head 复验：待完成
