# PanFamFlow Decision Log

### DEC-20260821-001: Pro 长任务按同项目多会话交接

- **Task**: task-validate-panfamflow-template
- **Session**: 2026-08-21T03:37:07+08:00 / resume4
- **Fingerprint**: 2cef9182427a366ecb119ebf737cf0c7e132aa6a
- **Decision**: 同一个 ChatGPT Pro 会话最多承载 2 次实质请求；需要第三次修订或进入新阶段时，在同一 ChatGPT 项目中创建新会话，并以轻量 `handoff.md` 加精确请求包恢复。
- **Trigger**: 原“提出全覆盖设计”会话较长；内部浏览器、已登录 Chrome 和专用配置均在消息读取或控制阶段出现超时，用户指出会话长度可能是重要因素。
- **Alternatives**: 继续在旧会话重试；完全重新描述项目；不使用 Pro；同项目新会话加结构化交接。
- **Rationale**: 新会话降低页面和上下文负担；结构化交接保留可复现状态；原始请求包及 SHA256 继续作为协议边界；同项目保留必要项目语境。
- **Trade-offs**: 新 Pro 会话不会自动拥有旧会话全文，因此交接必须明确区分已确认事实、未验证推断和下一步请求；Codex 仍需独立合并并审查 attempt 2 与新会话响应。
- **Impact**: `HANDOVER.md`、`.codex/cross-model-runs/20260820T172243Z-panfamflow-template-complete-expression/handoff.md`、`.codex/cross-model-runs/20260820T172243Z-panfamflow-template-complete-expression/session_strategy_20260821.md`、同运行目录的 outbound 新会话包和运行状态文件。
- **Details**: -> `.codex/cross-model-runs/20260820T172243Z-panfamflow-template-complete-expression/session_strategy_20260821.md`
