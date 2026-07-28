# Office AI 执行基线

- 状态：`INTERNAL ALPHA COMPLETE`（`ACCEPT_WITH_DECLARED_BOUNDARIES`）
- 范围基线：`.hermes/plans/2026-07-22_000414-office-ai-alpha.md`
- 任务索引：`.hermes/plans/office-ai-alpha-tasks/README.md`
- UI 基线：`docs/ui-v1/README.md`（`APPROVED-V1`）
- 执行方式：20 个顺序任务，每次只完成一个 dependency-ready 任务

## Post-Alpha Agnes 对话与 PPT 创作中心

- 批准 PRD：`docs/prd/2026-07-29-office-ai-agnes-chat-ppt-studio-prd.md`
  （`v1.0 / APPROVED`）
- 正式执行计划：
  `.hermes/plans/2026-07-29-office-ai-agnes-chat-ppt-studio-post-alpha.md`
- 任务索引：`.hermes/plans/office-ai-agnes-chat-ppt-studio-tasks/README.md`
- 当前 Gate：`P5-002 DONE -> P5-003 READY`
- 计划裁决：PRD 第 20 节要求开发前同步正式合同，因此 `P5-001` 先完成
  技术/API/Data/Security/Environment 合同；首页最近任务完整后移为 `P5-002`，
  `P5-003`～`P5-008` 保持批准 PRD 的相对顺序。
- 合同边界：P5-000 只建立计划与任务卡；P5-001 已将
  `post-alpha-contract.v1` 同步到本文件及 `docs/API.md`、`docs/DATA_MODEL.md`、
  `docs/SECURITY.md`、`docs/ENVIRONMENT.md`。P5-002 只能实现最近任务，不得提前实现
  Chat、Deck、模板或媒体。

### P5-001 Contract Gate（`post-alpha-contract.v1`）

P5-001 在业务代码和 migration 之前冻结下列合同。它是 Post-Alpha 的 additive 设计，
不改变 Alpha 旧流程；P5-002～P5-008 必须逐项实现并验证，不能把本节文档验证当作
Provider、runtime、Microsoft Office 或 WPS 通过证据。

#### 架构与权威边界

```text
Vue -> FastAPI -> MySQL chat/deck/media facts
          |       -> Outbox -> Redis -> bounded workers
          |       -> owner-scoped protected files
          -> Agnes text/image/video adapters
          -> existing Preflight -> generation task -> Renderer/QA
```

- FastAPI 是 Agnes 的唯一调用方和 SSE 边界，Browser 永远不接触 API Key。
- MySQL 保存会话、消息、run、Deck revision、媒体任务、幂等和结算事实；Redis 只保存
  可恢复 queue、锁、限流和瞬时 fan-out，Redis 丢失不能改变最终状态。
- Chat 正文只进入 owner-scoped `chat_messages`；日志、audit、queue、
  `provider_calls` 不复制正文、Prompt 或 Provider response。
- 自由 Markdown 不进入 Renderer。assistant 消息先编译为 strict `deck-brief.v1`，
  用户编辑形成不可变 revision/checksum，确认后才进入既有 Preflight/Generation。
- 图片和视频是独立 owner-scoped 不可变资产。视频默认独立交付；只有 P5-007 同时通过
  Microsoft PowerPoint 与 WPS 播放/无修复 Gate 才允许开启内嵌 capability。

#### 状态机与版本边界

Chat Run：

```text
queued -> streaming -> succeeded
                   -> failed
                   -> cancelled_partial
                   -> provider_uncertain
```

Deck Draft：

```text
draft -> editing -> confirmed -> preflight
preflight -> needs_resolution | ready
ready -> generation_queued -> existing generation state machine
```

Media Job：

```text
queued -> submitted -> running -> succeeded
                              -> failed
                              -> provider_uncertain
                              -> cancelled
```

- SSE 使用 `chat-sse.v1`。语义 event 具有单 run 单调 sequence；断线重连返回持久化
  `message.snapshot` 后继续，绝不把未确认 delta 冒充成功消息。
- cancel、重连、重新生成、Deck 保存、媒体创建和 generation submit 均使用数据库
  幂等边界。Provider 已提交但结果不确定时只能收口为 `provider_uncertain`。
- 编辑后重发和重新生成创建 message branch；旧 message/run 不原地覆盖。
- 已确认 Deck revision 继续编辑时创建新 revision，并必须重新 Preflight。

#### 来源与 capability

- 首期 Chat 本身只允许灵感创作；文件上下文固定为 `deck_only`，只在 assistant 消息
  转 Deck Draft 时选择现有 owner-scoped、版本冻结且 `ready/valid` 的资产。P5-003
  不向 Agnes Chat 发送文件、Evidence 或图片。
- Deck 支持灵感、资料和混合模式。`source_fact`、`calculated_fact` 与
  `agnes_inference` 分开保存；聊天内容不能升级为 `source_fact`，资料模式继续执行
  Evidence、术语、单位、冲突和低置信 fail-closed Gate。
- `agnes-2.5-flash` 是新会话推荐模型，`agnes-2.0-flash` 是用户可选兼容模型且仍为旧
  文件流程默认。发送前冻结 provider/credential/model/capability/pricing snapshot；
  任何失败都不得静默切换模型。
- Thinking 默认关闭；只有已发布模型 snapshot 明确声明 capability 且用户对当前 run
  显式开启时才发送。UI 不按 model code 猜 capability。
- 2026-07-29 仅核对 Agnes 官方文档合同：两种文本模型使用
  `POST /v1/chat/completions` 和 `stream: true`；图片使用
  `POST /v1/images/generations`；视频使用异步 `POST /v1/videos` 和结果查询。
  这不是本项目真实 Contract Test 通过证据。未来 adapter 必须以实际 response 中的
  token、尺寸、时长、Provider ID 和状态为权威。
- 图片图生图只允许受控 Data URI；本地资产禁止 public URL/tunnel。视频图生视频和
  keyframes 因官方合同要求公共图片 URL，首期保持关闭；文生视频也必须在 P5-007
  真实 Contract 后才能发布。

官方合同来源：

- [Agnes 2.5 Flash](https://agnes-ai.com/zh-Hans/docs/agnes-25-flash)
- [Agnes 2.0 Flash](https://agnes-ai.com/zh-Hans/docs/agnes-20-flash)
- [Agnes Image 2.1 Flash](https://agnes-ai.com/zh-Hans/docs/agnes-image-21-flash)
- [Agnes Video V2.0](https://agnes-ai.com/zh-Hans/docs/agnes-video-v20)

#### PRD 第 19 节首期决策

| 待确认项 | `post-alpha-contract.v1` 决策 | Tradeoff / Gate |
|---|---|---|
| 正文保留与彻底删除 | 活跃会话最后活动后默认保留 365 天；软删除可恢复 30 天；显式彻底删除在 24 小时内清除活动正文，备份残留最多 30 天 | 账务、审计和已生成资产按原策略保留，只断开正文关联；导出仅为 owner-scoped JSON |
| 文件上下文 | `deck_only`；Chat 首期不带文件 | 降低 Prompt injection/预算风险；P5-004 才接入冻结 Evidence |
| Thinking | 默认关闭、per-run 显式开启、capability gated | 不硬编码 2.5/2.0 能力，不保存隐藏 reasoning |
| 免费模型额度 | 每用户同时 1 个 Chat run、20 次/小时、100 次/日；输入 32768 字符、输出上限 8192 token | Provider 当前价格不等于永久免费；媒体和文件生成继续使用发布价格/积分 snapshot |
| 首批模板 | 冻结现有 3 套原创系统模板 `ppt.executive-blue.v1`、`ppt.operating-review.v1`、`ppt.data-story.v1` | P5-005 补齐分类、缩略图、来源/版权与兼容 Skill；缺 metadata 不发布 |
| 视频交付 | `OFFICE_AI_VIDEO_EMBED_ENABLED=false`，独立 MP4 + 海报帧 | P5-007 双 Office/WPS Gate 后才可显式开启 |
| 公共 Web 搜索 | `OFFICE_AI_CHAT_WEB_SEARCH_ENABLED=false` | 无搜索工具、无网页事实核验声明；未来另立来源/引用/隐私合同 |
| 高风险主题 | 医疗/法律/金融使用持续未核验提示；生成前要求 `high_risk_confirmation_required` 显式确认 | 首期固定标准策略，无企业管理员放宽；更严格策略可后续 additive |

以上八项均已选择最小、可逆、fail-closed 默认，没有遗留会阻塞 P5-002 的产品裁决。
会扩大外部数据处理范围的 public URL、Web 搜索、视频内嵌和 Chat 文件上下文仍由
feature/capability Gate 关闭，不能通过普通配置默默开启。

#### Post-Alpha 交付 Gate

| Gate | 任务 | 必须新增的证据 |
|---|---|---|
| Contract | P5-001 | 五份正式合同、RED/GREEN validator、八项决策 |
| Recent Tasks | P5-002 | owner-scoped 最近任务、真实进度、空态/失败/轮询 |
| Chat | P5-003 | 双模型真实 SSE、历史、branch/cancel/reconnect、Markdown 安全 |
| Deck | P5-004 | `deck-brief.v1`、revision/checksum、Skill、Evidence 与 Preflight |
| Template | P5-005 | 3 套模板 metadata/缩略图/版本/来源与兼容性 |
| Image | P5-006 | 真实图片 Contract、受控资产、PPTX Golden |
| Video | P5-007 | 异步 Provider ID、独立资产；内嵌默认关闭及 Office/WPS Gate |
| Release | P5-008 | 全链路、broad/security、真实 Provider、Golden、Office/WPS |

P5-001 的完成定义仅为合同一致、validator GREEN、文档/Git/远端对齐。P5-002 已完成
首页真实最近任务 Gate，P5-003 是下一唯一 `READY`；整个 PRD 只有 P5-008 通过且用户
整体验收后才能宣称完成。

本文是实施期的精简执行真源，不替代总计划中的详细论证。若描述冲突，以总计划的功能、安全和完成定义为最高优先级，以任务文档限定当前 commit 边界。

## 目标

在四周 Alpha 范围内交付可在 Windows 本地运行的 Office AI：用户从合法销售材料生成经过证据约束和质量门禁的 PPTX、XLSX，系统使用真实 Agnes API，并具备用户、管理员、资产、任务、积分与审计闭环。

## 锁定交付范围

- `+86` 手机号、邀请码注册、密码登录、Session/Refresh Token、管理员重置密码。
- 按 UI V1 实现用户端和管理端 Alpha 功能壳；UI V1 只约束视觉层级、结构、配色和交互密度。
- 本地资产上传、隔离、ClamAV 扫描、解析、PaddleOCR、预览、下载和删除。
- 输入支持 XLSX、CSV、DOCX、PDF、PNG、JPG、JPEG、WEBP、TXT、MD；XLSM 只读安全数据且不执行宏。
- Agnes 2.0 Flash Provider Adapter，管理员可配置 Provider、独立 Credential 和发布模型；不静默切换 Provider。
- 两个用户可见 Skill：销售经营汇报（PPTX）与销售数据分析和经营看板（XLSX），可共享材料组合执行。
- 销售经营汇报从已冻结资产的 Evidence Manifest 恢复 Excel 行列关系，生成封面、目录、
  经营摘要、分页业务表、问题与措施、结束页等管理汇报结构；完整 Evidence ID 进入
  speaker notes 和内部追踪，不占用可见正文。私有参考稿仅用于只读结构与可读性验收，
  不复制其品牌、Logo、图片、母版或嵌入对象。
- 结构化 Brief、版本、证据引用、冲突处理、用户确认、预计积分和异步生成。
- 3 套系统 PPT 模板、2 套系统 Excel 模板、确定性 renderer、LibreOffice 兼容验证和质量门禁。
- T4-003 由用户于 `2026-07-26` 批准以唯一一组授权 XLSX 来源 + PPTX 参考输出完成
  `1/10 pilot` 黄金回归；该变更降低 corpus 多样性证明，不降低脱敏、确定性、结构、
  指标、引用、审计报告或敏感信息门禁。
- MySQL 持久任务、Outbox、Redis 队列、checkpoint、幂等、有限重试、积分预留/结算/释放。
- 管理员可查看、预览、下载和删除全部用户资产；所有敏感操作必须重新认证并写入 audit log。

## 明确非范围

- UI V1 之后的品牌升级、高保真动效、像素级终稿和完整多端响应式。
- 在线 PPT/Excel 编辑器、团队/Workspace/组织协作、微信、小程序、支付、会员和生产部署。
- 用户私人模板上传、任意 PPTX 母版无损复刻、PPTX 输入和任意历史 Excel 无损往返。
- 对私有参考稿做像素级、品牌级或内容级复刻；本期只交付同类管理叙事和表格化表达。
- VBA、宏执行、Power Query、Power Pivot、DAX、ActiveX、外部连接和第三方插件。
- Alpha 两个 Skill 之外的业务 Skill、任意 Skill 组合和多 Provider 正式质量认证。
- 绕过加密/保护、将本地图片暴露到公网或把文档内容当作 System Prompt。

## 架构与权威边界

```text
Browser -> Vue -> FastAPI -> MySQL
                    |       -> local protected files
                    |       -> Outbox -> Redis
                    |                    -> Python worker
                    |                    -> PPT renderer
                    -> Agnes Provider Adapter -> Agnes API

Python worker -> ClamAV / PaddleOCR / LibreOffice / Excel renderer
PPT renderer  -> LibreOffice QA
```

- MySQL 是用户、资产、配置、任务和账务的事实来源；Redis 可丢失并可从 MySQL Outbox 恢复。
- Provider credential 由 FastAPI 管理并加密保存；解析 worker 只在 internal network，通过受控内部边界请求需要的工作，不挂载 credential、不直接访问公网。
- 文件二进制不进入 MySQL，存放于 `backend/files/`；预览和下载只能通过授权 API。
- renderer 只接收 Schema 验证后的 `PresentationPlan` 或 `WorkbookPlan`，不直接渲染模型自由文本。

## 核心状态机

资产：

```text
uploaded -> quarantined -> scanning -> parsing -> ready
任一处理阶段失败 -> rejected
用户删除 -> deleting -> deleted
```

任务：

```text
draft -> preflight -> needs_resolution -> queued -> running
running -> succeeded | partial_success | provider_uncertain | failed | cancelled
```

积分流水：

```text
registration_grant | admin_grant
generation_reserve -> generation_finalize | generation_release -> refund
```

- `provider_uncertain` 保留预留，未经确认不得重试扣费。
- `partial_success` 只结算成功的 PPTX/XLSX 子输出。
- `credit_ledger` 只追加并作为账务真相；`users.credit_balance` 只是事务内缓存。

## 证据、质量与安全门禁

- 证据类型限定为 `source_fact`、`calculated_fact`、`ai_inference`，每项保留资产版本和 Sheet/单元格、页码、段落或 OCR BBox 定位。
- 数字 OCR 置信度低于 `0.90` 阻断相关计算；叙述低于 `0.75` 告警；单位未知或来源冲突必须解决。
- 个人术语库按 `library_id + version` 保存不可变 snapshot；`terminology-normalization.v1` 只执行显式数字、单位、币种和绝对日期规则，项目规则覆盖同用户全局规则，歧义、未知单位和来源冲突形成 unresolved item。
- 标准化只生成保留 source fact raw/provenance 的派生 Evidence，不改写已落盘 Manifest；历史 Brief/任务固定引用术语库版本。
- Agnes Structured Brief 必须通过 Pydantic/JSON Schema；只允许一次约束修复，仍失败则失败且不扣费。
- PPT QA 使用版本化报告关联原输出、Renderer/template/Plan、LibreOffice PDF/逐页 PNG 与 validated artifact；`passed` 和 `passed_with_warnings` 可下载，`blocked` 最多自动修复一次，仍失败则禁止下载且不扣费。
- Excel Renderer 使用 strict `workbook-plan.v1`、两套认证模板和英文公式白名单生成确定性
  XLSX；原始输出不可覆盖，validation copy 通过 private LibreOffice sidecar 独立重算，
  `workbook-validation-report.v1` 关联原件、Plan、Renderer、template 与 formula/cache
  差异。`workbook-quality-report.v1` 进一步校验公式错误、确定性复算、chart range 与
  Sheet/字段/单位冲突；PPTX/XLSX 独立质量结果汇总为组合状态，并按成功输出幂等结算。
- 密码使用 Argon2id，Refresh Token 只保存 Hash，API Key 使用应用层加密，Master Key 只存在环境变量。
- 日志不得包含密码、Key、签名 URL、完整文件、完整 Prompt 或未清理的用户输入。

## 数据与 API

- Alpha 固定 21 张表，详细字段与约束见 `docs/DATA_MODEL.md`。
- HTTP API 统一以 `/api/v1` 开头，详细端点和共同行为见 `docs/API.md`。
- 环境变量和安全录入方式见 `docs/ENVIRONMENT.md`，安全边界见 `docs/SECURITY.md`。

## 四周 Gate

| Gate | 对应任务 | 可验证结果 |
|---|---|---|
| Week 1 | `T1-001`–`T1-005` | 可注册登录、配置 Provider/模型并管理本地资产 |
| Week 2 | `T2-001`–`T2-005` | 材料形成带证据的 Structured Brief，可修改、解决冲突并确认 |
| Week 3 | `T3-001`–`T3-005` | 同一材料异步生成 PPTX 与 XLSX，通过基础 QA 并下载 |
| Week 4 | `T4-001`–`T4-005` | 冷启动、真实 Agnes、1/10 pilot 黄金回归、Office/WPS 人工验收和敏感信息检查完成；未验证项显式保留 |

## Alpha 完成定义

- 必须交付项全部完成，明确非范围没有被加入。
- 自动测试、用户批准的 1 组脱敏 pilot 材料的 PPT/Excel 重复回归全部通过，并在 release
  note 中明确不具备原计划 10 组 corpus 的多样性证据。
- 所有 `passed` 文件经 Microsoft Office 与 WPS 人工打开且无修复提示。
- 真实 Agnes Contract Test 和 Git 敏感信息检查通过。
- `docs/PLAN.md`、`docs/PROGRESS.md`、实现、测试、Git 与推送状态一致。
- 没有未解释的阻断错误、证据伪造路径或重复扣费路径。

## Alpha 封版

- `2026-07-27`，T4-005 完成 Windows 本地 Internal Alpha Gate；封版报告见
  `docs/ALPHA_RELEASE.md`。
- 真实 Docker 冷启动为 9/9 healthy，MySQL 空库从 base 升至唯一
  `20260727_0014 (head)` 并完成 21 张业务表；真实 Agnes、黄金回归、Office/WPS
  证据复核与 Git/security Gate 均通过。
- 封版不改变 `1/10 pilot` 边界；它不能证明原计划 10 组 corpus 的多样性。ClamAV
  在线 signature refresh 与生产部署同样保留为已声明边界，不冒充完成。
- `2026-07-27` post-Alpha 运维配置将本地默认 Host ports 固定为 Frontend `8888`、
  Backend `9999`；容器内部 `5173/8000`、API contract 和 Alpha scope 不变。

## Post-Alpha 运行时修复

- `2026-07-27` 修复空项目账号无法上传首份材料的前端死锁：页面在项目列表为空时显示
  明确占位提示并允许选择文件；multipart 省略 `project_id`，继续复用后端既有的幂等默认
  项目创建 contract。
- 已有项目上传、owner scope、文件安全处理、Evidence Manifest、Brief 与生成 contract
  均不变；页面加载不新增写操作，也不扩展 Alpha scope。
- `2026-07-27` 修复 Compose named volume 冷创建后的所有权缺口：一次性
  `storage-init` 在无网络、无 Secret、read-only rootfs 下将 `app-files`、
  `parsed-files`、`evidence-files` 与 `shared-work` 根目录初始化为
  `10001:10001 / 0750`；Backend、Worker、PPT Renderer 与 LibreOffice 仅在初始化成功
  后以既有 non-root 用户启动。
- 该修复不改变上传 API、数据库 Schema、文件 key、解析/Evidence/Renderer contract
  或 Alpha scope；root 只存在于一次性 volume ownership 初始化阶段。
- `2026-07-27` 修复材料处理反馈与 Evidence 状态消费错配：工作流显示 selected project
  的全部 active 材料，对处理中状态每 `1.5s` 自动刷新，并对拒绝状态展示脱敏、可操作原因；
  只有 Worker 的权威成功组合 `processing_status=ready` +
  `manifest_status=valid` 可被选择。
- Brief 与 Preflight 同步采用 `ready/valid`，不再把 Worker 已验证的 `valid` Manifest
  误判为未就绪；`excel_sheet_limit_exceeded` 等安全拒绝仍 fail closed。
- 2026-07-27 经用户批准，Post-Alpha Excel 输入上限从 30 Sheet 调整为 100 Sheet；
  第 100 张仍可处理，第 101 张稳定拒绝。其他文件/任务/单元格/Archive/解析资源门禁、
  owner scope、数据库 Schema、用户文件和 Alpha scope 均不变。
- Workflow 仅对 `rejected/invalid` 材料显示右侧删除操作，复用 owner-scoped
  `DELETE /assets/{asset_id}`；用户按文件名确认且服务端返回成功后才移除当前行，
  取消或失败时保留材料，不自动清理任何用户资产。
- 2026-07-27 经用户批准，`golden-data/private/` 中唯一 XLSX 暂作为最高输入规模标准。
  只读测量确认 Evidence builder 在过滤空值前预算 11,563 个 source item，最终生成
  10,465 条 Evidence，Manifest 约 7.48 MB；因此默认 Evidence source expansion 上限
  精确调整为 11,563，第 11,564 项继续 fail closed。
- 该校准不修改 10 MB Manifest、100 Sheet、30 万非空单元格、Archive、parser
  structural、timeout、memory、ClamAV、owner scope、immutable Evidence 或单位未知
  blocker；private workbook 不进入 Git、fixture、日志或文档正文。
- `2026-07-27` 修复 Structured Brief Context 表示层放大：旧实现为每条 Evidence
  重复完整 asset identity/version 和 location JSON，导致 10,465 条黄金 Evidence
  被估算为 1,418,854 token。`brief-evidence-context.v2` 改为按 asset、location kind、
  Sheet 和 Evidence type 分组，并为每条证据分配确定性短引用。
- Agnes 只接收本次 Context 中的短引用；应用在 strict Schema/snapshot/evidence 校验前
  将其映射回原始不可变 Evidence ID，未知引用继续 fail closed。全部 Evidence 均保留，
  不抽样、不截断、不虚增 256K 模型能力，也不改变 5,193 个单位未知 blocker。
- `2026-07-27` 将用户“点击生成”改为 durable asynchronous workflow：前端先调用
  `POST /workflow-tasks`，同一事务立即写入 `workflow_tasks + outbox_events` 并返回
  `202`，随后独立 `workflow-worker` 在后台整理 Brief。用户无需等待 Agnes 完成即可在
  `/tasks` 查看持久进度、系统备注和失败原因。
- `workflow_tasks` 覆盖 `brief_queued -> brief_generating -> awaiting_confirmation`
  及确认后的 generation 阶段；生成任务创建后只投影既有 `generation_tasks` 的权威
  状态、进度和积分，不复制第二套文件生成状态机。`brief_schema_invalid` 等稳定错误码
  与安全中文原因会保留，刷新后仍可追踪。
- 现有同步 `POST /briefs/generate` 仅保留兼容，不再由用户工作流页面调用。Structured
  Brief Schema、Evidence、Preflight、积分和质量门禁均不降低；任务记录不保存 Prompt、
  Provider 原始响应、Credential、文件正文或 storage key。
- `2026-07-27` 修复真实 Agnes 连续返回 `brief_schema_invalid` 的 contract 传递缺口：
  generation prompt 除 17 个顶层字段外，现同时携带
  `StructuredBrief.model_json_schema()` 的完整 nested required/Literal/length/
  `additionalProperties=false` 约束；一次 repair 接收仅含字段路径和错误类型的 bounded
  hints，不再要求模型在没有错误定位的情况下盲修。
- 应用仍以原 strict Pydantic、authoritative snapshot 和 Evidence allowlist 判定结果；
  validation hints 不含字段值，不进入数据库、日志或用户错误响应。真实 Agnes 合成销售
  Evidence Contract 已通过，native `response_format` 仍保持关闭。
- `2026-07-27` 修复 Preflight 全量扫描 Manifest 与同义 blocker 重复计数：Preflight
  现在只检查 Structured Brief 的 facts、inferences、output、must include/exclude 和
  unresolved item 实际引用的 Evidence；`numeric_unit_unknown` 统一为
  `unit_unknown`，同一 Evidence 只形成一个阻断。
- 单位未知继续 fail closed，但页面会显示 Sheet/单元格等安全定位，并要求用户从受支持的
  canonical unit 中显式选择。选择结果保存到新的不可变 Brief Revision、
  `source_snapshot.resolutions` 和 generation input snapshot；不修改 Manifest、不猜测
  单位，也不放宽 OCR、来源、口径、模型或积分门禁。
- `2026-07-27` 补齐单位解决的前端操作闭环：单位列表使用有明确滚动条的受限高度区域，
  阻断区内显示 `已选 x/y` 和“保存单位并重新校验”。全部选择保存为新 Revision 并刷新
  Preflight 后，生成按钮才自动解锁；未满足门禁时按钮文案直接说明缺少选择、保存或其他
  blocker。
- 该交互修复复用既有 Revision PATCH，不自动保存、不自动确认生成，也不修改 API、
  数据库 Schema、Evidence、Preflight 判定、积分或历史记录。
- `2026-07-27` 修复所有 User App Shell 页面无法接受滚轮手势的问题：User Shell 现在
  使用 `height: 100dvh; min-height: 0; overflow-y: auto`，成为明确的纵向 scroll root。
  新建任务、Brief、任务详情、文件和模板页面共享该滚动责任，不再依赖浏览器隐式 root
  scrolling。
- 该修复不添加全局 wheel listener 或 JS 模拟滚动，不调用 `preventDefault`，也不修改
  Admin/Public Shell、页面表单、API、数据库或业务状态。
- `2026-07-28` 修复 generation queue 只有 producer、没有 production consumer
  导致任务长期 `queued / 0%` 的运行时断链：Compose 新增独立
  `generation-worker`，通过 `python -m app.workers.generation` 消费既有 queue。
- worker 从 confirmed Structured Brief 与冻结 template snapshot 确定性编译 strict
  PPTX/XLSX Plan，复用既有 Renderer、LibreOffice QA、checkpoint 与 credit
  settlement；不调用 Provider、不读源文件、不猜测数字或单位。
- claim、step completion 与 settle 均将进度写入 MySQL；空或非法 Brief 在 renderer
  前永久失败并释放 reserve。HTTP API、数据库 Schema、Frontend、Evidence、
  Preflight 与质量 Gate 均不降低。
