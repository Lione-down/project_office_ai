# P5-001 技术、API、Data、Security 与 Environment 合同

- 状态：`DONE`
- Depends on：`P5-000`
- 来源：PRD 第 7–16、19、20 节
- 建议 commit：`docs(chat): define agnes studio contracts`

## 目标

在任何业务代码或 migration 前，把批准 PRD 转换为无歧义、可测试、fail-closed 的技术、
API、数据、状态机、安全、环境与交付合同，并解决或显式阻断第 19 节待确认事项。

## 交付范围

- 更新 `docs/PLAN.md`：Post-Alpha 架构、状态机、能力/来源模式、阶段 Gate 和完成定义。
- 更新 `docs/API.md`：会话 CRUD、SSE event、cancel、message branch、Deck Draft、
  media、generation 入口、owner scope、幂等、错误码、缓存和限流合同。
- 更新 `docs/DATA_MODEL.md`：chat thread/message/run、Deck Draft/revision、media job
  及现有 task/file/provider 关系、唯一约束、事务与 additive migration 计划。
- 更新 `docs/SECURITY.md`：正文保留/删除、Markdown、Prompt/tool injection、白名单工具、
  高风险内容、跨用户、SSE 断连、媒体传输/解码和日志脱敏。
- 更新 `docs/ENVIRONMENT.md`：非 Secret 配置名称、SSE/输入/保留/并发/媒体 limits、
  真实 Contract opt-in；不新增或提交环境文件。
- 明确双模型 capability、Thinking、文件上下文、配额、模板、视频内嵌、Web 搜索和高风险
  主题的首期决策；无法安全决定的事项保持 blocker。

## RED 与实施顺序

1. 先增加文档 contract validator，要求五份专题文档均覆盖实体、endpoint、状态、错误、
   owner scope、删除/保留、能力和证据边界；观察旧文档失败。
2. 冻结命名、状态和事务关系，再写 API/Data/Security/Environment，避免跨文档漂移。
3. 逐项关闭 PRD 第 19 节；范围扩张项保持关闭或另立后续任务。
4. 让 validator GREEN，再运行文档链接、UTF-8、diff 和敏感路径检查。

## 验收标准

- 五份正式专题文档对实体、状态、endpoint、错误码和 capability 无冲突。
- SSE 明确事件顺序、断线、取消、partial、重连/重放边界和 `provider_uncertain` 收口。
- 明确聊天正文可持久化但不得复制到日志/audit/provider_calls；软删除、彻底删除和备份残留
  有可执行合同。
- 明确 2.5/2.0 用户选择、旧 2.0 默认不变、Thinking capability 和禁止静默切换。
- 明确灵感/资料/混合 provenance、Evidence 约束和 Deck Draft revision/checksum。
- 明确媒体幂等、真实 Provider ID/尺寸、积分、取消、不确定状态和视频内嵌默认关闭。
- 不包含业务代码、migration 或对真实 Provider/Office 兼容性的虚假通过声明。

## 验证

```powershell
python scripts/validate-post-alpha-contracts.py
git diff --check
git check-ignore -v .env
git status --short
git diff --cached --name-only
```

## 证据边界

- Focused：专题合同 validator、链接、状态/envelope/API/Data 对齐。
- Broad：现有计划/进度/PRD 引用一致；本任务不要求产品 suites。
- Security：敏感文件名、正文/Prompt/response 禁止持久化位置和 public URL 默认关闭。
- Provider：只固定 contract/opt-in，不能声明 2.5/2.0/Image/Video 真实兼容。
- Office/WPS：只固定未来 Gate，不生成或打开文件。

## 非目标与回滚

- 不实现最近任务、Chat UI/SSE、数据库 migration、Deck、模板或媒体。
- 不更改批准 PRD；若合同发现范围冲突，在进度中记录并请求产品裁决。
- 回滚仅恢复本任务修改的正式文档和 validator，不触碰 Alpha 实现。

## 完成记录

- 新增 `scripts/validate-post-alpha-contracts.py`；旧文档首次 RED 为 97 个缺失合同项，
  覆盖五份文档、endpoint、状态机和 PRD 第 19 节决策。
- `docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/SECURITY.md`、
  `docs/ENVIRONMENT.md` 已统一冻结 `post-alpha-contract.v1`。
- 八项决策采用最小 fail-closed 默认：365/30/24/30 天保留删除合同、文件
  `deck_only`、Thinking 默认关闭、Chat 额度、3 套既有原创模板、视频内嵌关闭、
  Web 搜索关闭、高风险显式确认。
- Focused validator GREEN：5 份正式文档、14 个 endpoint、3 个状态机、8 项决策。
- Broad 文档检查：18 个 UTF-8 文件、11 个本地链接、0 个坏链接；validator Ruff
  check/format、syntax 和 `git diff --check` 通过。
- Security 检查：新增 diff/validator 高置信 Secret 命中 0、tracked environment-like
  文件 0、`.env` 命中 `.gitignore`、业务代码/migration diff 0。
- 本任务未读取 `.env`，未调用真实 Agnes，未生成/打开 Office 文件；Provider 与
  Microsoft Office/WPS 只固定后续 Gate，不声明兼容已通过。
- P5-002 已激活为唯一 `READY`；本会话未实现 P5-002。
