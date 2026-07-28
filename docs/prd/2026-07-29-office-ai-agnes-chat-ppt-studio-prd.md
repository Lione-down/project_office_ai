# Office AI Agnes 对话与 PPT 创作中心 PRD

| 文档字段 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 文档状态 | APPROVED |
| 更新日期 | 2026-07-29 |
| 产品阶段 | Post-Alpha 增量迭代 |
| 目标端 | Office AI Web 用户端 |
| 核心 Provider | Agnes AI |

## 1. 产品摘要

Office AI 将新增独立的“AI 创作中心”页面，为用户提供类似主流大模型产品的多轮文本对话体验，并把“内容整理—大纲编辑—模板选择—图片/视频生成—PPTX 交付”整合在同一条可追踪工作流中。

该能力是对现有产品的增量扩展，不替换或删除现有首页、文件上传、Evidence Manifest、Structured Brief、PPTX/XLSX 组合任务、模板、积分、任务历史、Renderer、质量门禁、Office/WPS 验证及下载能力。

### 1.1 一句话价值

用户可以从一句自然语言需求开始，通过 Agnes 流式对话完善内容，并将任意一条合适的回复转换为可编辑、可选模板、可生成视觉素材且最终可下载的 PPTX。

### 1.2 已确认的产品原则

1. 新功能与原有功能并存，旧流程保持可用且行为不变。
2. 新页面支持 `agnes-2.5-flash` 与 `agnes-2.0-flash`；2.5 是新对话推荐模型，2.0 继续作为兼容选项和旧流程默认模型。
3. 模型切换必须由用户明确选择；Provider 不得静默降级、静默切换或在失败后自动改用另一模型。
4. Agnes 可作为对话模型，也可作为仅能调用 Office AI 白名单工具的受控智能体；不得成为任意远程执行入口。
5. 聊天正文允许用户持续编辑；进入 PPT 生成前必须形成版本化、可确认的 Deck Brief 与 PresentationPlan。
6. 模板决定视觉表达，Skill 决定内容组织，Agnes 图片/视频属于任务资产；三者不可混为一个概念。

## 2. 背景与问题

### 2.1 当前能力

Office AI Alpha 已具备文件驱动的 PPTX/XLSX 生成闭环：

- 用户上传合法材料并经过隔离扫描、解析和 Evidence Manifest 构建。
- Agnes 根据 Evidence 生成严格 Structured Brief。
- 用户解决冲突并确认 Brief。
- 系统冻结 Skill、模型、模板和输入快照，异步生成文件。
- PPTX/XLSX 经过确定性 Renderer、LibreOffice QA、质量门禁和任务结算后下载。

### 2.2 当前不足

- 用户必须从文件和结构化表单开始，无法像使用通用大模型一样先对话、发散和整理知识。
- 首页“最近任务”当前只有静态占位文案，没有展示已有持久任务。
- 模板页只有文字卡片，缺少真实缩略图、分类、详情、版本及“一键使用”。
- 没有面向 PPT 的对话内快捷动作，也没有逐页大纲编辑和视觉素材编排。
- Agnes 图像与视频能力尚未成为 Office AI PPT 工作流中的正式任务步骤。
- 现有 `agnes-2.0-flash` 需要保留，但新版本 `agnes-2.5-flash` 尚未作为独立文本模型进入新对话体验。

## 3. 目标与成功标准

### 3.1 产品目标

1. 提供可持续使用的 Agnes 流式多轮对话页面。
2. 让用户从聊天结果一键进入可编辑 PPT 大纲，而不是复制粘贴到外部工具。
3. 允许用户选择经过认证的模板，并按页面选择是否生成图片或视频。
4. 复用现有任务、积分、资产、Renderer、QA 和下载闭环。
5. 在不降低 Evidence、安全和质量门禁的前提下，支持“灵感创作”和“资料驱动”两种来源模式。
6. 让首页能够展示最近任务及其真实进度。

### 3.2 建议北极星指标

- 首次对话到形成 PPT 大纲的转化率。
- 大纲确认到 PPTX 生成成功率。
- 成功 PPTX 的质量门禁通过率。
- 用户对 AI 大纲的平均编辑次数与确认率。
- 图片生成后被保留进入最终 PPT 的比例。
- 对话流首字节时间、完整响应成功率和主动停止成功率。
- 旧文件驱动流程的回归通过率必须维持 100%。

### 3.3 首期验收目标

- `agnes-2.5-flash` 和 `agnes-2.0-flash` 均可被用户明确选择并完成真实流式对话。
- 新建、继续、重命名、删除会话可用，刷新页面后历史仍存在。
- 任一成功的 assistant 消息可转换为 Deck Draft。
- Deck Draft 可编辑、保存版本、选择模板、预检并创建现有持久生成任务。
- 图片生成可进入受控资产并被 PPT Renderer 使用。
- 视频生成可形成独立可追踪资产；是否嵌入 PPTX 由兼容性 Gate 决定。
- 首页展示当前用户最近 3–5 条任务；任务页仍展示完整列表。
- 原有 Alpha focused/broad/security/golden/Office/WPS 验证不得回退。

## 4. 非目标

首期不包含：

- 替换或删除现有文件驱动 PPTX/XLSX 工作流。
- 浏览器内完整所见即所得 PPT 编辑器。
- 任意 PPTX 母版无损导入、第三方模板照搬或私人模板上传。
- 自动复制 DeepSeek 或其他第三方产品的品牌、布局细节和交互资产。
- 默认开启公共 Web 搜索、自动引用任意网页或宣称模型内容已经事实核验。
- 任意 Provider 自动路由、失败后自动切换模型或自动重复产生可能计费的媒体。
- 把本地受保护文件暴露为公共 URL。
- 让 Agnes 直接执行任意后端 API、数据库操作、文件操作或管理操作。
- 在没有 Office/WPS 兼容证据前承诺视频一定以内嵌方式进入 PPTX。

## 5. 用户与核心场景

### 5.1 目标用户

- 知识整理用户：从主题或问题开始，希望快速得到结构化长文和 PPT。
- 教育培训用户：需要课程、科普、医学教育或内部培训演示。
- 业务汇报用户：希望先在对话中打磨叙事，再选择现有经营汇报模板。
- 已有资料用户：希望把现有文件作为对话上下文，并继续使用可追溯 Evidence 模式。

### 5.2 核心用户故事

#### US-01：自由对话

作为用户，我希望选择 Agnes 2.5 Flash 或 2.0 Flash，输入问题后立即看到流式回复，并能停止、复制、重新生成或继续追问。

#### US-02：从聊天生成 PPT 大纲

作为用户，我希望对一条 AI 回复点击“整理为 PPT 大纲”，设置受众、页数和风格，得到逐页可编辑内容。

#### US-03：选择模板

作为用户，我希望查看模板缩略图、分类、代表页和适用场景，并把选定模板应用到当前 Deck Draft。

#### US-04：生成配图

作为用户，我希望系统判断哪些页面需要视觉素材，展示图片 Prompt，并允许我按页生成、重生成、替换或取消。

#### US-05：生成视频

作为用户，我希望只对指定页面生成视频，查看任务状态和结果，并在兼容性允许时将其加入 PPT；不允许系统默认为所有页面生成视频。

#### US-06：使用已有资料

作为用户，我希望选择已上传且 `ready/valid` 的文件作为对话或 PPT 上下文，并在最终文件中保留 Evidence 引用。

#### US-07：查看最近任务

作为用户，我希望在首页直接看到最近任务、状态、进度和输出类型，并可进入任务详情。

## 6. 信息架构与页面结构

### 6.1 顶部导航

在现有导航中新增“AI 创作”，保留：

- 首页
- AI 创作（新增）
- 任务
- 文件
- 模板

管理员入口及原有用户流程不变。

### 6.2 AI 创作页面

#### 左侧会话栏

- “开启新对话”主操作。
- 搜索当前用户会话标题。
- 按“今天 / 7 天内 / 30 天内 / 更早”分组。
- 会话标题、当前模型、更新时间。
- 重命名、删除。
- 收起侧栏。

#### 主对话区

- 顶部显示会话标题和当前模型。
- 用户消息与 assistant 消息。
- assistant 消息按 Markdown 安全渲染。
- 流式生成指示、停止按钮、失败状态和重试入口。
- 消息操作：复制、编辑后重发、重新生成。
- PPT 操作：整理为 PPT 大纲、加入当前 Deck Draft。
- 对高风险或无来源内容显示“AI 生成，尚未核验”提示。

#### 底部输入区

- 自适应多行输入框。
- 普通对话 / PPT 创作模式切换。
- 模型选择：Agnes 2.5 Flash、Agnes 2.0 Flash。
- Thinking 开关仅在模型能力允许时显示。
- 选择已有文件或上传新文件；上传必须复用现有安全资产流程。
- 发送、停止生成。
- 当前免费、积分或额度文案从已发布模型配置读取，不在前端硬编码。

#### PPT 大纲编辑区

首期采用右侧抽屉或独立步骤页，不建设完整 WYSIWYG 编辑器：

- Deck 标题、副标题、受众、语言、页数、语气。
- 逐页卡片：页面类型、标题、正文要点、讲者备注、视觉建议。
- 增加、删除、复制、排序页面。
- 单页重新整理。
- 选择模板。
- 图片和视频素材状态。
- 保存草稿、确认大纲、运行 Preflight、开始生成。

## 7. 来源模式

### 7.1 灵感创作模式

- 允许不上传文件，从用户输入和 Agnes 回复形成 Deck Draft。
- AI 产生的事实、数字、医学或其他专业内容保持 `agnes_inference` provenance。
- 用户确认表示接受其作为创作输入，不表示系统已完成事实核验。
- 最终 PPT 应提供可配置的“AI 生成内容”提示；高风险主题需在生成前再次确认。

### 7.2 资料驱动模式

- 只能引用当前用户拥有、版本冻结且 `processing_status=ready`、`manifest_status=valid` 的资产。
- 继续使用 Evidence ID、定位、术语、冲突、单位和引用规则。
- 未知单位、来源冲突、低置信数字等继续 fail closed。
- 聊天内容不得覆盖或伪装为 source fact。

### 7.3 混合模式

- 用户输入、AI 推断和文件 Evidence 必须分别保留 provenance。
- 可追溯事实与未核验推断在 UI 和最终 notes 中可区分。
- 从聊天到 Deck Brief 的编译不得删除来源类型或把推断升级为事实。

## 8. 模型策略

### 8.1 模型目录

| 模型 | 新对话可选 | 推荐状态 | 兼容用途 |
|---|---:|---:|---|
| `agnes-2.5-flash` | 是 | 新页面推荐 | 流式对话、PPT 内容整理、受控工具调用 |
| `agnes-2.0-flash` | 是 | 兼容 | 旧工作流默认、用户手动选择、回归比较 |
| `agnes-image-2.1-flash` | 媒体步骤 | 图片推荐 | 文生图、图生图、模板视觉素材 |
| `agnes-video-v2.0` | 媒体步骤 | 视频推荐 | 文生视频、图生视频、关键帧任务 |

### 8.2 模型选择规则

- 新建对话默认选择已发布且健康的 2.5 Flash。
- 旧文件驱动流程的默认 2.0 Flash 不因本功能自动变化。
- 用户选择的模型随会话保存，发送前可更改。
- 2.5 不可用时显示明确错误和模型状态；只有用户主动选择后才能改用 2.0。
- 每次 run 冻结 provider、credential、model code、capability 和价格/积分 snapshot。
- UI 只能展示管理员已发布且具备所需 capability 的模型。

### 8.3 官方合同基线

- 2.5 与 2.0 共用 OpenAI 风格 `POST /v1/chat/completions`。
- 流式请求使用 `stream: true`。
- 2.5 支持多轮对话、工具调用和 Thinking。
- 官方当前显示 2.5 输入/输出 Token 为 `$0`；可用性、限流和价格以账户权限为准。
- 前端只显示服务端发布的当前状态，不使用“永久免费”等不可验证承诺。

官方参考：

- https://agnes-ai.com/zh-Hans/docs/agnes-25-flash
- https://agnes-ai.com/zh-Hans/docs/agnes-20-flash
- https://agnes-ai.com/zh-Hans/docs/agnes-image-21-flash
- https://agnes-ai.com/zh-Hans/docs/agnes-video-v20

## 9. 功能需求

### 9.1 增量兼容

| ID | 需求 | 优先级 |
|---|---|---:|
| FR-001 | 新功能不得删除、替换或改变现有文件驱动流程的可观察行为。 | P0 |
| FR-002 | `agnes-2.0-flash` 必须保留并继续支持既有任务。 | P0 |
| FR-003 | 新对话、Deck Draft 和媒体任务必须与现有任务列表和 owner scope 集成。 | P0 |
| FR-004 | 旧回归、Golden、Office/WPS 和安全 Gate 必须持续通过。 | P0 |

### 9.2 会话与流式输出

| ID | 需求 | 优先级 |
|---|---|---:|
| FR-101 | 用户可创建、列出、打开、重命名和删除自己的会话。 | P0 |
| FR-102 | 会话消息持久化，刷新或重新登录后可继续。 | P0 |
| FR-103 | FastAPI 从 Agnes 接收流并以 SSE 转发给 Vue；API Key 不进入浏览器。 | P0 |
| FR-104 | 流式响应支持开始、增量 token、完成、停止、失败和 provider uncertain 事件。 | P0 |
| FR-105 | 用户停止生成后，已接收文本可保留为 `cancelled_partial`，但不得冒充完整成功回复。 | P0 |
| FR-106 | 消息支持复制、编辑后重发、重新生成；重新生成产生新分支或版本，不覆盖历史。 | P1 |
| FR-107 | UI 使用安全 Markdown 渲染，禁止未清理 HTML、脚本和危险链接协议。 | P0 |

### 9.3 PPT 创作

| ID | 需求 | 优先级 |
|---|---|---:|
| FR-201 | assistant 消息可触发“整理为 PPT 大纲”。 | P0 |
| FR-202 | 转换前收集或确认主题、受众、页数、语言、风格和来源模式。 | P0 |
| FR-203 | 大纲输出必须通过 `deck-brief.v1` 严格 Schema，不直接使用自由 Markdown 渲染 PPT。 | P0 |
| FR-204 | 用户可增删、复制、排序和编辑页面卡片。 | P0 |
| FR-205 | 每次保存产生不可变 revision 和 checksum；生成冻结确认版本。 | P0 |
| FR-206 | 用户可从现有 Skill 中选择兼容 Skill；系统可建议但不得静默替用户决定。 | P0 |
| FR-207 | 用户确认后进入现有 Preflight、任务、积分、Renderer 和 QA 链路。 | P0 |
| FR-208 | 生成后在会话、首页最近任务和任务页显示同一权威任务状态。 | P0 |

### 9.4 模板

| ID | 需求 | 优先级 |
|---|---|---:|
| FR-301 | 模板目录展示封面缩略图、代表页拼图、名称、分类、风格和适用场景。 | P0 |
| FR-302 | 模板详情展示配色、字体、布局清单、兼容 Skill、版本和版权/来源说明。 | P0 |
| FR-303 | 使用模板时冻结 template code、version 和 checksum。 | P0 |
| FR-304 | 首期只提供原创、授权明确的系统模板，不复制第三方案例。 | P0 |
| FR-305 | 用户可在大纲确认前切换模板并查看静态预览。 | P1 |

### 9.5 图片

| ID | 需求 | 优先级 |
|---|---|---:|
| FR-401 | Visual Director 为每页输出 `none/diagram/chart/illustration/photo` 建议及结构化 Prompt。 | P0 |
| FR-402 | 用户可按页选择生成、跳过、替换或重新生成图片。 | P0 |
| FR-403 | 全屏 PPT 素材默认建议 2K、16:9；最终使用 Provider 返回的权威尺寸。 | P1 |
| FR-404 | 图生图优先使用 Provider 支持的 Data URI，不通过公网 tunnel 暴露本地资产。 | P0 |
| FR-405 | 图片作为 owner-scoped 不可变资产保存，记录模型、Prompt hash、尺寸、版本和任务关联。 | P0 |
| FR-406 | Renderer 对图片执行格式、容量、尺寸、裁切、安全和版面检查。 | P0 |

### 9.6 视频

| ID | 需求 | 优先级 |
|---|---|---:|
| FR-501 | 用户只能对明确选择的页面创建视频任务。 | P0 |
| FR-502 | 视频任务使用异步状态和 Provider ID 轮询，不使用前端假进度。 | P0 |
| FR-503 | 文生视频可首期开放；需要公共图片 URL 的图生视频在安全传输方案批准前保持关闭。 | P0 |
| FR-504 | 视频结果作为独立资产提供预览和下载。 | P0 |
| FR-505 | PPTX 内嵌视频必须通过容器、编码、包关系及 Office/WPS Gate；未通过时使用海报帧和独立视频交付，不伪报已内嵌。 | P0 |

### 9.7 最近任务

| ID | 需求 | 优先级 |
|---|---|---:|
| FR-601 | 首页调用现有 owner-scoped workflow task 列表，而不是显示静态占位。 | P0 |
| FR-602 | 默认显示最近 3–5 条，按创建时间倒序。 | P0 |
| FR-603 | 每条显示标题、输出类型、状态、进度、更新时间和详情入口。 | P0 |
| FR-604 | 存在非终态任务时按受控间隔刷新；离开页面时停止轮询。 | P1 |
| FR-605 | 空态、加载失败和重试状态必须可区分。 | P0 |

## 10. 受控智能体与内置 Skill

### 10.1 用户可见 Skill

首批新增建议：

- `ppt.knowledge-education.v1`：知识科普、课程、医学教育和培训型演示。
- 保留 `ppt.sales-business-review.v1`：销售经营与管理汇报。
- 后续可增加 `ppt.business-proposal.v1`、`ppt.marketing-story.v1`，不在首期同时实现。

### 10.2 内部步骤

- `ppt.outline-director.v1`：自由文本到 Deck Brief。
- `ppt.visual-director.v1`：逐页视觉需求和 Prompt。
- `ppt.agnes-image-assets.v1`：图片任务与资产。
- `ppt.agnes-video-assets.v1`：视频任务与资产。
- `ppt.template-compose.v1`：内容到模板布局映射。
- `ppt.quality-accessibility.v2`：溢出、对比度、裁切、来源、可访问性和兼容性。

### 10.3 白名单工具

Agnes 可建议或调用以下受控工具，但涉及任务创建或媒体生成时必须由用户在 UI 中确认：

- `build_ppt_outline`
- `open_deck_editor`
- `suggest_ppt_template`
- `plan_slide_visuals`
- `generate_slide_image`
- `generate_slide_video`
- `run_deck_preflight`
- `submit_ppt_generation`

工具参数必须经过服务端 Schema、owner scope、capability、额度和状态校验。不存在通用 `execute` 工具。

## 11. 状态机

### 11.1 Chat Run

```text
queued -> streaming -> succeeded
                   -> failed
                   -> cancelled_partial
                   -> provider_uncertain
```

### 11.2 Deck Draft

```text
draft -> editing -> confirmed -> preflight
preflight -> needs_resolution | ready
ready -> generation_queued -> existing generation state machine
```

每次编辑创建新 revision；`confirmed` 之后继续编辑时必须创建新 revision 并重新 Preflight。

### 11.3 Media Job

```text
queued -> submitted -> running -> succeeded
                              -> failed
                              -> provider_uncertain
                              -> cancelled
```

## 12. 数据与持久化建议

### 12.1 新增核心实体

#### `chat_threads`

- owner user ID
- title
- default model ID
- mode：`chat` / `ppt`
- status、created_at、updated_at、deleted_at

#### `chat_messages`

- thread ID、sequence、role
- content、content format
- status、parent/branch message ID
- model/provider snapshot
- provenance summary
- created_at、updated_at

#### `deck_drafts`

- owner、thread、source message
- group ID、revision、status
- strict `deck-brief.v1`
- template snapshot、Skill snapshot、checksum
- created_at、confirmed_at

### 12.2 复用实体

- `provider_calls`：继续只保存 request ID、token、latency、状态和错误分类等脱敏元数据，不复制完整 Prompt 或 Provider 原始响应。
- `workflow_tasks`：投影 Brief、媒体准备和文件生成的权威进度。
- `generation_tasks`、steps、inputs、outbox、credit ledger：继续承担文件生成、幂等和结算。
- `file_assets`：承载生成图片、视频、PPTX 和质量报告。
- `templates`、`skills`、`ai_models`：保持版本和能力合同。

### 12.3 数据边界

- 聊天正文因属于用户明确要求保存的产品内容，可进入 owner-scoped `chat_messages`。
- 日志、audit 和 `provider_calls` 不得复制聊天正文。
- 删除会话采用 owner-scoped 软删除；关联已生成文件和账务历史按既有保留策略处理。
- 需要在开发计划中确定聊天保留期限、导出和彻底删除策略。

## 13. API 草案

| Method | Endpoint | 用途 |
|---|---|---|
| POST | `/api/v1/chat/threads` | 新建会话 |
| GET | `/api/v1/chat/threads` | 当前用户会话列表 |
| GET | `/api/v1/chat/threads/{thread_id}` | 会话及消息 |
| PATCH | `/api/v1/chat/threads/{thread_id}` | 重命名或更新默认模型 |
| DELETE | `/api/v1/chat/threads/{thread_id}` | 删除会话 |
| POST | `/api/v1/chat/threads/{thread_id}/messages:stream` | 发送消息并建立 SSE 流 |
| POST | `/api/v1/chat/runs/{run_id}/cancel` | 停止当前生成 |
| POST | `/api/v1/chat/messages/{message_id}/deck-drafts` | 从消息创建 Deck Draft |
| GET | `/api/v1/deck-drafts/{draft_id}` | 读取 Draft |
| PATCH | `/api/v1/deck-drafts/{draft_id}` | 创建新 revision |
| POST | `/api/v1/deck-drafts/{draft_id}/confirm` | 确认 revision |
| POST | `/api/v1/deck-drafts/{draft_id}/preflight` | 运行门禁 |
| POST | `/api/v1/deck-drafts/{draft_id}/media/images` | 创建图片任务 |
| POST | `/api/v1/deck-drafts/{draft_id}/media/videos` | 创建视频任务 |
| POST | `/api/v1/deck-drafts/{draft_id}/generations` | 进入现有 PPTX 生成 |

所有写请求应有 owner scope、幂等和 `Cache-Control: private, no-store`；错误返回稳定 code 和安全中文说明。

## 14. 安全、隐私与内容治理

1. Agnes API Key 仅由后端使用，不进入前端、聊天正文、日志或导出文件。
2. 会话、消息、Draft、媒体和输出均按 owner scope 鉴权。
3. SSE 断开不等于 Provider 已取消；服务端必须执行取消或状态收口。
4. 用户内容视为不可信输入，不得进入不可覆盖的 system instructions。
5. Markdown 必须清理 HTML、脚本、事件属性和危险 URL。
6. 2.5 和 2.0 的工具调用只接受后端注册白名单及严格 JSON Schema。
7. 医疗、法律、金融等高风险内容默认显示未核验提示，生成前要求用户确认。
8. 本地图片不通过公共 tunnel 暴露；Provider 只接受公共 URL 的能力保持关闭，直到受控短时访问方案被批准。
9. 媒体资产需进行类型、容量、解码、内容策略及哈希检查。
10. 模型返回文本、图片和视频不得被宣称为事实、版权无风险或必然适用于商业用途。

## 15. 异常处理

| 场景 | 产品行为 |
|---|---|
| 401/403 | 标记 Credential 不可用，停止请求，不切换模型 |
| 400 合同错误 | 返回稳定错误，禁止自动重试 |
| 429/5xx | 按 Retry-After 和配置分类；只进行明确、有限重试 |
| timeout/连接断开 | 进入 `provider_uncertain` 或安全失败，不重复提交 |
| 用户停止 | 中止本地流并请求 Provider/服务端取消，保留部分文本状态 |
| Schema 不合法 | 允许一次受约束 repair；仍失败则不创建 Draft |
| 图片/视频结果不可达 | 任务失败或 uncertain，不生成虚假资产 |
| PPT QA blocked | 禁止下载并按现有规则决定是否允许一次修复 |

## 16. 可观测性

需要记录但不得包含正文：

- thread、run、draft、workflow 和 generation 的关联 ID。
- 模型、Provider、Credential 指纹和 capability snapshot。
- 首字节时间、总耗时、token 数、finish reason。
- SSE 客户端断开、服务端取消及最终状态。
- Deck Draft Schema/Preflight 失败 code。
- 图片/视频任务创建、Provider ID、状态和安全错误分类。
- 从会话到 Draft、从 Draft 到生成、从生成到下载的漏斗指标。

## 17. 验收标准

### 17.1 功能验收

- [ ] 导航新增“AI 创作”，原页面与路由继续可用。
- [ ] 新对话默认显示已发布的 Agnes 2.5 Flash，用户可切换到 2.0 Flash。
- [ ] 两种模型均可真实流式输出，支持停止和错误恢复。
- [ ] 会话刷新后仍可继续，用户之间完全隔离。
- [ ] assistant 消息可创建并编辑 Deck Draft。
- [ ] Draft 保存为新 revision，确认后不可被原地覆盖。
- [ ] 模板预览、选择和冻结版本可用。
- [ ] 图片按页生成并进入受控资产。
- [ ] 视频只按用户选择生成，任务状态来自服务端。
- [ ] PPT 生成复用现有持久任务、质量门禁和下载流程。
- [ ] 首页最近任务展示真实数据。

### 17.2 安全验收

- [ ] 前端 bundle、Network 响应和日志不包含 Agnes API Key。
- [ ] 无跨用户会话、Draft、任务或资产访问。
- [ ] 没有公共 tunnel 暴露本地文件。
- [ ] Provider 失败不会静默切换模型或重复创建任务。
- [ ] `provider_calls`、日志和 audit 不保存完整聊天正文或原始 Provider 响应。
- [ ] Markdown XSS、危险 URL、超长输入和流中断测试通过。

### 17.3 质量与兼容验收

- [ ] 旧 Alpha focused/broad/security 测试全部通过。
- [ ] 新增 chat SSE、状态机、幂等、取消和 owner scope 测试。
- [ ] 新增 Deck Brief、模板、图片和视频合同测试。
- [ ] 真实 Agnes 2.5/2.0 Contract Test 分别记录，Mock 不能替代真实结果。
- [ ] 图片参与 PPT 的黄金回归通过。
- [ ] 视频嵌入仅在 Microsoft PowerPoint 和 WPS 均无修复提示且能播放后标记支持。
- [ ] 可下载 PPTX 继续满足溢出、裁切、引用、质量报告和不可变资产要求。

## 18. 分阶段交付建议

| 阶段 | 交付 | 依赖 |
|---|---|---|
| P5-001 | 首页最近任务真实展示 | 现有 workflow task API |
| P5-002 | 新 PRD、技术计划、数据/API/安全设计 | P5-001 |
| P5-003 | 双模型文本对话、SSE、会话历史 | P5-002 |
| P5-004 | Deck Draft、逐页编辑、Skill 与 Preflight | P5-003 |
| P5-005 | 模板目录、缩略图和版本快照 | P5-004 |
| P5-006 | Agnes 图片生成与 PPT 视觉集成 | P5-005 |
| P5-007 | Agnes 视频资产与兼容性 Gate | P5-006 |
| P5-008 | 端到端 Golden、Office/WPS、安全和发布 Gate | P5-007 |

每次只激活一个 dependency-ready 任务；每个任务独立执行 RED、focused、broad/security、文档同步、精确暂存、单一 commit 和 push。

## 19. 待确认事项

以下内容不阻塞 PRD 评审，但必须在对应实现任务前决策：

1. 会话正文默认保留期限，以及用户“彻底删除”的范围。
2. 首期是否允许选择已有文件作为聊天上下文，或仅在转 Deck Draft 时选择。
3. 2.5 Thinking 默认关闭还是按“深度整理”模式开启。
4. 免费模型的产品限流、每日额度和滥用保护规则。
5. 首批原创 PPT 模板的具体数量和主题分类。
6. 视频首期只作为独立附件，还是在通过兼容性 Gate 后开放内嵌。
7. 是否在后续版本增加公共 Web 搜索和可验证引用。
8. 高风险主题的提示强度、确认文案和企业管理员策略。

## 20. 发布边界

本 PRD 仅定义 Post-Alpha 新功能，不激活代码任务，也不改变当前 `INTERNAL ALPHA COMPLETE` 状态。开发前须建立 Post-Alpha 任务索引与唯一 `READY` 任务，并将获批合同同步至 `docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/SECURITY.md`、`docs/ENVIRONMENT.md`。
