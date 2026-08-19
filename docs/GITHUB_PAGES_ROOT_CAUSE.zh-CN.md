# PanFamFlow GitHub Pages 根因与修复报告

审计日期：2026-08-18—2026-08-19（Asia/Shanghai）

首次失败基线：`main@06903f39dfab8ee1e454fe35eb7b48032a5781a3`

修复后基线：`main@d60c22db5a27b07f08f626482f22afa085ff2bef`

## 结论

首次 Pages 部署失败的直接根因是：仓库当时尚未启用 GitHub Pages，而 `actions/configure-pages@v5` 在 `enablement: true` 下尝试使用 workflow `GITHUB_TOKEN` 创建 Pages site。该 token 不具备仓库级 Pages enablement 所需的管理权限，GitHub 返回 `Resource not accessible by integration`。

仓库发布链路随后改为：管理员预先启用 GitHub Pages，workflow 只负责构建受控 `_site/` artifact 并部署。该链路已经在合并后的 `main` 精确提交上通过 CI 与 Pages 验证。

2026-08-19 的后续可用性检查又发现，仓库根目录 `index.html` 把项目根地址立即指回自身，会形成自刷新循环。尽管当前 Pages workflow 从 `site/` 构建首页，这个遗留入口仍可能被旧发布配置或浏览器缓存命中。修复要求同时覆盖仓库根入口、发布首页和 README 的外部链接。

## 原始失败证据

- Workflow：`Deploy PanFamFlow tutorial`
- Workflow run：<https://github.com/lianglunping/PanFamFlow/actions/runs/31958304609>
- Job ID：`95192287726`
- Head SHA：`06903f39dfab8ee1e454fe35eb7b48032a5781a3`
- 失败步骤：`Configure Pages`
- 后续 artifact 上传与部署步骤：均为 `skipped`

日志中的关键事实：

1. workflow token 权限为 `Contents: read`、`Pages: write`；
2. `Get Pages site` 返回 `Not Found`；
3. 随后 `Create Pages site` 返回 `Resource not accessible by integration`；
4. 失败发生在 artifact 构建和部署之前。

## 已排除的替代原因

| 候选原因 | 证据与判断 |
|---|---|
| 上传仓库根目录导致首次失败 | 排除为直接根因：上传步骤在 Configure Pages 失败后被跳过；但扩大公开面的风险仍需修复。 |
| `deploy-pages` OIDC 权限缺失 | 排除：workflow 已声明 `pages: write` 与 `id-token: write`，且首次失败时 Deploy 尚未运行。 |
| checkout 失败或 SHA 不一致 | 排除：checkout 成功并记录精确 SHA。 |
| environment 人工 approval 阻塞首次运行 | 排除：首次失败发生在 Configure Pages。 |
| artifact 大小、符号链接或 tar 结构错误 | 排除为首次失败原因；修复后由独立 `_site/` 构建与 manifest 检查覆盖。 |

## 已实施修复

1. Pages source 固定为 `GitHub Actions`，workflow 不再自行 enable Pages。
2. 以 `site/` 为受控静态源构建 `_site/`，只发布首页、教程和必需静态资源。
3. `upload-pages-artifact` 只上传 `_site/`，不上传仓库根目录。
4. 对 `/PanFamFlow/` 基路径、站内链接、HTTP 混合内容和禁止发布目录执行 fail-closed 检查。
5. 构建脚本拒绝输出目录与输入目录重叠，避免误删源文件。
6. 根入口移除自动跳转；发布首页改为无外部样式依赖的自包含 HTML。
7. README 的项目网站链接显式指向发布的 `index.html`，并带版本化查询参数以避开旧入口缓存。
8. CI 加入入口回归测试：禁止自跳转、校验 README 外链并验证首页与教程入口；发布前另执行仓库全文遗留信息审计。

## 已完成的精确版本验证

- 合并后 CI：<https://github.com/lianglunping/PanFamFlow/actions/runs/32176372262>，结论 `success`
- 合并后 Pages：<https://github.com/lianglunping/PanFamFlow/actions/runs/32176218751>，结论 `success`
- 对应 `main` SHA：`d60c22db5a27b07f08f626482f22afa085ff2bef`
- 中文教程：`https://lianglunping.github.io/PanFamFlow/tutorial/`

上述证据证明修复前的构建、artifact 与部署链路已经可运行。2026-08-19 的入口修复仍须在新的 PR head 和合并后的新 `main` head 上重新执行相同门禁，并从 README 实际点击项目网站链接完成最终验收。

## 风险与边界

- Pages deployment 成功只证明工程发布成功，不改变 HSP 科学结果或 benchmark 的 `BLOCKED` 状态。
- 外部 Google Drive 链接可能受共享权限、账号登录或平台风控影响，需在独立会话逐项验证。
- GitHub Pages 与浏览器缓存存在传播延迟；最终验收必须记录合并后的精确 SHA、CI run、Pages run 和实际页面标题。

## 本轮验收合同

- README 中“Project site / 项目网站”链接可直接打开；
- 项目首页标题为 `PanFamFlow｜目标泛基因家族分析流程`；
- 中文教程仍可打开且交互内容不回退；
- 根入口与发布首页均不存在自动跳转到自身；
- 仓库全文不再包含已停用域名及其配置说明；
- 新 PR head 与合并后 `main` exact-head 的 CI、Pages 均成功。
