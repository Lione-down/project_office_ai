# Office AI Agnes 对话与 PPT 创作中心 Post-Alpha 执行计划

- 状态：`ACTIVE`
- 批准来源：`docs/prd/2026-07-29-office-ai-agnes-chat-ppt-studio-prd.md`（`v1.0 / APPROVED`）
- 任务索引：`.hermes/plans/office-ai-agnes-chat-ppt-studio-tasks/README.md`
- 当前 Gate：`P5-004 DONE -> P5-005 READY`
- 执行方式：单一 dependency-ready 任务、单一 commit、push 后新会话交接

## 1. 目标

在不替换 Office AI Alpha 文件驱动流程的前提下，交付 owner-scoped Agnes 流式多轮对话、
可版本化 Deck Draft、系统模板浏览与冻结、按页图片/视频资产、现有 PPTX
Renderer/QA/任务/积分闭环，以及首页最近任务真实投影。

最终交付必须同时证明：

- `agnes-2.5-flash` 与 `agnes-2.0-flash` 均由用户明确选择，不静默切换。
- 对话、Draft、媒体、任务和资产保持 owner scope、幂等、不可变 revision 和安全日志边界。
- 灵感创作、资料驱动和混合来源不会把 `agnes_inference` 升级为 `source_fact`。
- 图片可进入 PPTX；视频只有通过 Microsoft PowerPoint 与 WPS 兼容 Gate 后才可声明内嵌，
  否则交付海报帧与独立视频资产。
- 旧 Structured Brief、PPTX/XLSX、Golden、Office/WPS、安全和下载流程不回退。

## 2. 阶段顺序裁决

批准 PRD 第 18 节是交付建议，第 20 节同时要求开发前先建立 Post-Alpha 任务索引，并把
获批合同同步到 `docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、
`docs/SECURITY.md`、`docs/ENVIRONMENT.md`。为避免在合同未冻结时先写 UI，正式执行顺序为：

| PRD 第 18 节建议 | 正式任务 | 裁决 |
|---|---|---|
| 原 P5-001：首页最近任务 | `P5-002` | 保留全部范围，但等待合同任务完成 |
| 原 P5-002：PRD、技术计划、数据/API/安全设计 | `P5-000` + `P5-001` | P5-000 建计划；P5-001 冻结正式合同 |
| 原 P5-003～P5-008 | `P5-003`～`P5-008` | 编号和相对顺序保持不变 |

`P5-000` 只建立计划，不修改正式 API/Data/Security/Environment 合同。`P5-001` 已冻结
`post-alpha-contract.v1` 并同步五份正式文档；`P5-002` 已交付 owner-scoped 首页最近
任务、权威 progress、失败/retry 和受控轮询。P5-003 已交付双模型真实 SSE、历史、
取消/重连、分支和安全 Markdown；P5-004 已完成 Deck Gate，`P5-005` 是下一唯一
`READY`。

## 3. 不可回退边界

- 保留现有首页、新建任务、文件、模板、任务详情、管理员入口和全部 Alpha API。
- 保留 `agnes-2.0-flash` 作为旧文件流程默认；新对话推荐 2.5 不能改变旧默认值。
- SSE 只由 FastAPI 连接 Agnes 并转发，API Key 不进入浏览器、正文、日志、队列或导出。
- MySQL 是会话、Draft、媒体、任务和结算事实来源；Redis 只承担可恢复队列、锁和限流。
- 聊天正文仅可进入 owner-scoped 正文表；`provider_calls`、audit、日志不复制正文、
  Prompt 或 Provider 原始响应。
- Agnes 工具仅限服务端白名单与 strict Schema；创建任务、图片或视频均需用户在 UI 确认。
- Deck Draft 以 `deck-brief.v1` 严格 Schema、不可变 revision/checksum 和 confirmed
  snapshot 进入现有 Preflight/Generation；自由 Markdown 不直接进入 Renderer。
- 资料驱动仍使用冻结资产、Evidence ID、术语、单位、冲突与 fail-closed 规则。
- 模板、Skill、图片、视频分别保存版本化 snapshot，不以一个概念替代另一个。
- 媒体资产使用受控存储、真实尺寸/类型/容量/解码检查；本地资产不通过公共 tunnel 暴露。
- 可下载 PPTX 继续通过 Renderer、LibreOffice、质量报告和不可变 validated artifact Gate。

## 4. 依赖链

```text
P5-000 计划基线
   -> P5-001 技术/API/Data/Security/Environment 合同
   -> P5-002 首页最近任务
   -> P5-003 双模型会话与 SSE
   -> P5-004 Deck Draft、Skill 与 Preflight
   -> P5-005 模板目录与版本快照
   -> P5-006 Agnes 图片资产与 PPT 集成
   -> P5-007 Agnes 视频资产与兼容 Gate
   -> P5-008 端到端、安全、Office/WPS 与发布 Gate
```

任何任务失败、证据不足或合同未同步时保持当前任务 `READY/DOING/BLOCKED`，不得提前激活
下一个任务。

## 5. 任务与 Gate

| ID | Gate | 核心交付 |
|---|---|---|
| `P5-000` | Plan Gate | 本计划、索引、任务卡、进度和唯一 `READY` |
| `P5-001` | Contract Gate | 技术决策、API、数据、状态机、安全、环境、保留/删除和能力合同 |
| `P5-002` | Recent Tasks Gate | 首页真实最近 3–5 条任务、权威进度、空态/失败/轮询 |
| `P5-003` | Chat Gate | 双模型、会话 CRUD/历史、SSE、停止、分支、Markdown 安全 |
| `P5-004` | Deck Gate | `deck-brief.v1`、逐页编辑、revision、Skill、Preflight、现有生成任务 |
| `P5-005` | Template Gate | 原创系统模板目录、缩略图、详情、兼容性和冻结 snapshot |
| `P5-006` | Image Gate | Visual Director、按页图片任务、不可变资产、PPTX 使用和 Golden |
| `P5-007` | Video Gate | 显式按页视频任务、真实轮询、独立资产、嵌入兼容 Gate |
| `P5-008` | Release Gate | 全链路、真实双模型、Golden、安全、PowerPoint/WPS 和发布结论 |

## 6. 验证与证据分层

每个实现任务必须先观察 RED，再做最小 GREEN，并依次记录：

1. **Focused**：当前模块的 contract、状态机、owner scope、幂等与错误路径。
2. **Broad**：Backend full pytest/Ruff、Frontend full test/build，涉及 Renderer 时执行其
   test/build 与相关 Golden。
3. **Security**：Markdown XSS、危险 URL、超长输入、跨用户访问、正文/Secret 日志泄漏、
   公共 URL、重复计费和静默模型切换。
4. **Runtime**：Compose config/health、真实 MySQL migration、Redis 恢复和队列状态；
   Mock/offline 不能替代真实 runtime。
5. **Provider**：只有显式 opt-in 的真实 Agnes 2.5/2.0、Image/Video Contract Test 才能
   证明 Provider 兼容；不记录 Prompt、response body、用户文件或 Secret。
6. **Office/WPS**：OOXML、Renderer、LibreOffice 和截图属于机器证据；只有 Microsoft
   PowerPoint/WPS 实际打开、无修复提示及所需播放/交互检查才是对应桌面兼容证据。

`P5-002` 等不涉及 Provider 或 Office 文件的任务必须明确写“本任务不产生该类证据”，
不得用无关旧证据填充。

## 7. P5-001 已冻结的决策（DONE）

P5-001 已在任何业务代码前完成并同步正式专题文档：

- 会话、消息、soft delete、导出与彻底删除/备份残留的保留合同。
- 首期文件上下文接入点、冻结条件、Evidence provenance 与上下文预算。
- Thinking capability/default、双模型 capability 和禁止静默降级规则。
- 文本/媒体额度、限流、并发、幂等、取消、`provider_uncertain` 与积分 snapshot。
- `chat_threads`、`chat_messages`、chat run、Deck Draft/revision、媒体任务和关联表设计。
- SSE event/envelope、重连/取消/partial、错误码、`Cache-Control` 和 owner scope。
- 首批原创模板数量/分类、版权/来源字段和兼容 Skill。
- 视频首期默认独立附件；只有 P5-007 兼容 Gate 通过才可启用内嵌 capability。
- 公共 Web 搜索保持关闭；未来启用必须另立合同和来源验证任务。
- 高风险主题提示、显式确认、审计与企业策略的首期最小合同。

若待确认项尚无批准结论，P5-001 必须选择最小、可逆、fail-closed 默认并记录 tradeoff；
会改变产品范围或外部数据处理的决策仍须作为 blocker，不得默默猜测。

## 8. 单任务交付协议

- 每个会话先创建该任务目标，再按 `AGENTS.md -> docs/PROGRESS.md -> Alpha index ->
  本索引/READY task -> docs/PLAN.md/专题合同 -> git status` 读取实时状态。
- 同一会话只完成一个 dependency-ready 任务，不提前编辑下一任务的代码。
- 每个任务更新自己的卡、索引、`docs/PROGRESS.md` 和必要合同。
- 先 focused，后 broad/security/runtime；未运行的验证写为未验证。
- 只精确暂存任务拥有路径，不使用 `git add .`，保留 `.playwright-cli/`、
  `design-system/` 和旧 `docs/ui-mockups/` 未跟踪文件。
- 单一 `type(scope): subject` commit，push 后确认 `HEAD == origin/main`。
- 完成后新建项目会话，仅激活下一个唯一 `READY` 任务。

## 9. 完成定义

只有 `P5-008` 的功能、安全、真实 Provider、Golden、Office/WPS、Git 和发布 Gate 全部
通过，且所有 P5 任务/文档/实现/测试/远端状态一致时，整个 PRD 才能标记完成并交由用户
整体验收。计划或机器验证不替代用户对最终交互和视觉成品的验收。
