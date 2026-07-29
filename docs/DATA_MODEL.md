# Office AI Alpha 数据模型基线

- 数据库：MySQL 8.0
- 表数量：Post-Alpha 当前 25 张；`post-alpha-contract.v1` 规划 additive 增至 31 张
- 状态：Alpha 以 21 张封版；Post-Alpha `20260727_0015` 新增 `workflow_tasks`，
  P5-003 `20260729_0016` 新增三张 Chat 表并扩展 `provider_calls`；P5-004
  `20260729_0017` 新增三张 Deck 表；P5-005 `20260729_0018` 扩展模板 catalog，
  当前 28 张业务表

## 全局约定

- 应用生成 UUIDv7，MySQL 存储为 `BINARY(16)`。
- 时间统一为 UTC `DATETIME(6)`；金额、次数和积分使用整数。
- 核心关系使用外键，任务请求、能力和历史快照可以使用 JSON。
- 用户可见资源使用软删除；实际文件异步清理，活动存储立即删除，备份残留最长 30 天。
- 历史修订、输出版本、`credit_ledger` 和 `audit_logs` 不原地覆盖。
- 文件二进制、system/完整 Provider Prompt、Provider 原始响应和明文 Secret 不进入
  数据库。用户明确要求保存的 Chat 正文只进入 owner-scoped `chat_messages`；用户确认
  的媒体 Prompt 只进入 owner-scoped `media_jobs`。两者都不得复制到日志、audit、
  `provider_calls`、queue 或其他快照。

## P5-001 Post-Alpha 数据合同（`post-alpha-contract.v1`）

P5-001 冻结下列 additive Schema；P5-003 已实现前三张 Chat 表，P5-004 migration
`20260729_0017` 已实现三张 Deck 表。`chat_tool_invocations` 与两张 media 表仍按后续
批准任务建立。既有表不删除、不改写历史 migration。

### 计划新增 9 张表

23. `chat_threads`
   - owner user、title、default model ID、`chat/ppt` mode、status、last activity、
     retention expiry、soft-delete/purge request/content-purged 时间及 created/updated。
   - title 是用户内容；列表只按 owner 和未删除范围查询。模型只是后续 run 默认，
     不回写历史 snapshot。

24. `chat_messages`
   - thread、单调 sequence、`user/assistant` role、Markdown content、status、
     parent message、superseded message、branch root、可空 run、provenance summary、
     created/updated/finalized time。
   - 状态为 `pending`、`streaming`、`succeeded`、`cancelled_partial`、`failed` 或
     `provider_uncertain`。active assistant 行可 checkpoint 累计 partial；终态后不可变。
     编辑后重发/重新生成追加 sibling，不覆盖旧行。

25. `chat_runs`
   - owner、thread、user message、assistant message、client idempotency key、状态、
     last SSE sequence、provider/credential/model/capability/pricing snapshot、
     Thinking flag、Provider request ID、token/latency/finish reason、cancel request、
     error code/脱敏原因及生命周期时间。
   - 状态为 `queued`、`streaming`、`succeeded`、`failed`、`cancelled_partial`、
     `provider_uncertain`。不保存 system Prompt、隐藏 reasoning 或 Provider response。

26. `chat_tool_invocations`
   - owner、run、message、tool code/version、strict arguments JSON、arguments checksum、
     status、confirmation required/confirmed user/time、result resource type/ID、
     stable error code 和时间。
   - 只允许后端 registry 中的白名单工具。Provider 原始 tool call 不直接执行；Schema、
     owner、capability、额度和用户确认通过后才保存可执行 canonical arguments。
     arguments 只允许稳定 message/draft/slide/asset ID 和 bounded enum/数字选项，禁止
     复制 Chat/Deck/media 正文。

27. `deck_drafts`
   - owner、thread、source assistant message、stable group ID、latest revision、
     lifecycle status、created/updated/deleted time。
   - 只保存稳定 identity 和指针，不保存可变内容副本；删除 Chat 时按保留策略断开或清理
     未进入 generation 的内容。

28. `deck_draft_revisions`
   - draft、revision、strict `deck-brief.v1` JSON、content checksum、source mode、
     Skill/model/template snapshot、provenance summary、Preflight snapshot、
     high-risk confirmation metadata、status、confirmed/generation task/time。
   - 状态为 `draft`、`editing`、`confirmed`、`preflight`、`needs_resolution`、`ready`、
     `generation_queued`。每次保存插入下一 revision；confirmed 内容不原地覆盖。

29. `deck_draft_inputs`
   - revision、input kind、source asset/message/media ID、source version/checksum、
     Evidence/terminology snapshot 和 provenance kind。
   - 资料/混合模式只接受 owner 的 `ready/valid` 资产；灵感内容固定为
     `agnes_inference`，不能升级为 `source_fact`。

30. `media_jobs`（P5-006/P5-007 已实现 image/video）
   - owner、draft revision、slide stable ID、workflow task、kind `image/video`、
     mode、idempotency key、prompt hash、模型/capability/pricing snapshot、状态、
     Provider opaque ID、真实 progress、请求/实际尺寸与时长、cancel/error/时间。
   - 状态为 `queued`、`submitted`、`running`、`succeeded`、`failed`、
     `provider_uncertain`、`cancelled`。只有用户在 UI 查看/确认的媒体 Prompt 保存于
     owner-scoped job content 字段；system instructions、Provider request wrapper 和
     response 不落库。日志、Outbox 和 `provider_calls` 只保存 hash/metadata。

31. `media_job_inputs`（P5-006 已实现 owner-scoped image input）
   - job、input kind、owner-scoped asset ID/version/hash、slide ID、顺序和用途。
   - 本地图片只允许经安全解码后构造受控 Data URI；不保存 public URL。视频首期
     text-only，此表为未来经批准的 image/keyframe capability 保留严格关系。

### 现有表 additive 关系

- `provider_calls` 已增加可空 `chat_run_id`、`media_job_id` 和各 scope 的 attempt
  唯一约束；仍只保存脱敏 metadata，不保存正文、Prompt 或 response。
- `file_assets` 已增加可空 `generated_media_job_id`、`media_role`、媒体尺寸/metadata
  与不可变 `asset_version`，用既有
  owner-scoped immutable storage 承载 image、video、poster；同 job/role/version 唯一。
- `workflow_tasks` 已增加 `resource_kind/resource_id`，使首页和任务页投影 Deck/media/
  generation 的同一权威状态；Redis 不承担该关系。
- `generation_task_inputs` 以稳定 source kind/ID/version/checksum 引用 confirmed Deck
  revision、选中 media asset、Skill 和 template snapshot；video 成功时同时冻结
  `media_image` poster 与 `media_video_attachment`，Renderer 只接收 poster 的 strict
  image Plan，MP4 继续走独立 owner-scoped 下载。
- `ai_models.capabilities` 必须显式描述 `chat_stream`、`thinking`、`tool_calling`、
  `image_generation`、`video_generation` 和 `video_embedding`；缺失视为 `false`。

### Post-Alpha 唯一约束

| 表 | 唯一键 | 目的 |
|---|---|---|
| `chat_threads` | `(user_id, thread_id)` | owner-scoped identity，便于复合外键 |
| `chat_messages` | `(thread_id, sequence)` | 会话内稳定顺序 |
| `chat_runs` | `(user_id, idempotency_key)` | 重放发送只创建一个 run |
| `chat_runs` | `(assistant_message_id)` | 一个 assistant branch 只属于一个 run |
| `chat_tool_invocations` | `(run_id, tool_call_id)` | 重复 tool frame 不重复执行 |
| `deck_drafts` | `(user_id, draft_group_id)` | owner-scoped stable identity 唯一 |
| `deck_drafts` | `(user_id, idempotency_key)` | 相同创建键只对应一个 payload fingerprint |
| `deck_drafts` | `(user_id, source_message_id)` | 一个成功 assistant message 只对应一个稳定 Draft |
| `deck_draft_revisions` | `(draft_id, revision)` | 不可变 revision |
| `deck_draft_inputs` | `(revision_id, input_kind, source_asset_id, source_message_id)` | revision 内冻结来源不重复 |
| `media_jobs` | `(user_id, idempotency_key)` | 重放媒体创建不重复提交/扣费 |
| `media_jobs` | `(provider_id, provider_job_id)` | 上游 opaque ID 不重复关联 |
| `media_job_inputs` | `(media_job_id, input_kind, source_asset_id, sequence)` | 输入顺序与角色稳定 |
| `file_assets` | `(generated_media_job_id, media_role, version)` | job 输出/海报不可变 |

`NULL` Provider ID 不参与 completed identity；只有提交成功后写入并复验唯一约束。
幂等 replay 必须同时校验 payload fingerprint，key 相同而 fingerprint 不同返回冲突。

### 事务与 checkpoint

- Chat start：锁定 owner/thread 和 admission budget，在同一事务追加 user message、
  assistant placeholder、`queued` run 与脱敏 Provider call intent；commit 后才调用
  Provider。失败前没有无主 partial。
- Chat stream：累计正文按 bounded byte/time checkpoint 更新 active assistant row，
  同事务提高 `chat_runs.last_event_sequence`；终态锁定 run，只允许一次状态转换。
  SSE 重连从累计正文生成 `message.snapshot`，不需要在 MySQL 保存每个 token frame。
- Cancel/disconnect：锁定 active run 写 `cancel_requested_at`；上游确认后终态为
  `cancelled_partial`，结果不确定则为 `provider_uncertain`，禁止自动生成 sibling。
- Tool：严格参数和 confirmation 在一个事务落库；任务/媒体创建继续使用目标资源自己的
  幂等事务。tool invocation 只保存关联结果，不成为第二套业务事实。
- Draft create/save：创建 `deck_drafts + revision 1 + inputs` 或追加 revision 时锁定
  latest revision；checksum/idempotency replay 返回原 revision。confirm/Preflight
  snapshot 同事务提交，编辑 confirmed Draft 必须追加 revision。
- Media create：同事务创建 `media_jobs + inputs + workflow projection + reserve/outbox`；
  Provider submit 后 checkpoint opaque ID 再轮询。未知结果进入 `provider_uncertain` 并
  保留 reserve；成功 bytes 经类型/容量/解码/hash 后才创建 immutable `file_assets`。
- Deck generation：锁定 latest confirmed/ready revision，复验 input/media/template/
  Skill/model/pricing 后复用既有 generation task、ledger 和 Outbox 事务；重复 submit
  返回同一 task。

P5-004 的 `deck_draft_revisions` 还保存 bridge Brief ID 与 generation task ID，使
Preflight、credits、Renderer、QA 和 task history 继续使用既有 MySQL 事实。相同内容的
重放由 service checksum/idempotency contract 收口，不依赖 nullable JSON 字段的数据库
唯一约束。

### 保留、导出与删除

- active thread 以 `last_activity_at + 365 天` 计算默认 expiry；到期进入 soft delete。
- soft delete 隐藏 thread/message/draft，30 天 grace 内可恢复；到期后进入 purge。
- 用户显式“彻底删除”后 24 小时内清除 active Chat 正文、未进入 generation 的 Draft
  content 和未引用临时导出；`chat_threads` 保留不可逆 tombstone/时间用于幂等。
- 备份中的已清除正文最多再残留 30 天，不能承诺即时擦除不受应用直接控制的备份。
- 已生成资产、`generation_tasks`、`credit_ledger`、必要 `audit_logs` 继续按原保留策略；
  purge 断开 source message/body 关联，不伪造账务或历史输出删除。
- JSON export 由请求时读取 owner-scoped 表生成，不包含 Secret、system Prompt、隐藏
  reasoning、Provider response 或其他用户数据；过期临时 export 必须清理。

## Alpha 表清单

1. `users`
   - 手机国家码、手机号、角色、状态、Argon2id password hash、积分余额缓存、强制改密标记、邀请码来源。
   - 不拆 `user_profiles`；Alpha 不加入微信字段。

2. `user_sessions`
   - 用户、Refresh Token hash、设备信息、IP、过期时间、撤销时间和撤销原因。

3. `invite_codes`
   - 邀请码 hash、可识别前缀、最大/已用次数、有效期、状态、注册赠送积分、创建管理员。
   - 消费、创建用户和赠送积分在同一事务中完成。

4. `projects`
   - 用户、名称、默认项目标记、归档和软删除状态；无显式项目的上传自动创建默认项目。

5. `file_assets`
   - 用户、项目、清理后的原文件名、分类、MIME、字节数、SHA-256、storage provider/key、处理状态、上传幂等键、父版本、生成任务、manifest key、删除状态。
   - T2-001 additive metadata：结构化解析结果 key、parser 名称/版本、告警代码 JSON、稳定错误码、脱敏错误、处理开始/完成 UTC 时间；进入 `parsing` 时先持久化 deterministic intended output key，确保 output write 后 hard crash 仍有精确 recovery 定位；文件内容仍不进入 MySQL。
   - T2-002 additive metadata：Manifest 状态/SHA-256/Schema 版本、证据引擎版本、warning/blocker 数量、生成时间，以及有上限的 OCR retry count/next retry time。Manifest key 在文件写入前持久化；MySQL 不保存证据正文、OCR 原文、BBox 或本地路径。

6. `templates`
   - 类型、来源/预览资产、分类、样式关键字、完整设计配置、版本、状态、排序、使用次数
     与 catalog checksum。
   - P5-005 发布三套 `owner_user_id IS NULL / source=system_original / status=published`
     PPTX row；`design_config` 保存来源/license、配色、字体、布局、场景、兼容 Skill、
     本地 preview 与 Renderer token，checksum 覆盖完整 canonical payload。
   - 字段兼容未来用户模板，但当前 API 只发布上述三套系统原创模板；用户模板上传仍不在
     范围内。

7. `term_libraries`
   - 每个不可变 version 一行：版本行 ID、跨版本稳定 `library_id`、用户、可选项目、前一版本、名称、说明、状态、版本和创建时间。
   - `(library_id, version)` 唯一；mutation 锁定当前版本后创建下一版本，删除创建 `deleted` tombstone，不覆盖历史版本。

8. `term_items`
   - 每个库 version 保存完整条目 snapshot：版本行 ID、跨版本稳定 `item_id`、术语库版本行、标准术语、JSON 别名、canonical unit、定义、口径说明、优先级和创建时间。
   - `(term_library_version_id, item_id)` 与 `(term_library_version_id, canonical_term)` 唯一；条目更新/删除通过下一库版本表达。

9. `briefs`
   - 修订行 ID、跨 revision 稳定 `brief_group_id`、revision、用户、项目、选择模型、来源快照、17 字段内容 JSON、内容 checksum、可空 Preflight snapshot、可空锁定预计积分、状态、确认/创建时间。
   - `(brief_group_id, revision)` 唯一；T2-004 创建 revision 1 的 `draft`，T2-005 修改时锁定最新 Revision 并追加下一行，不 UPDATE 历史内容、来源或确认快照。

10. `skills`
    - 每版本一行：code、SemVer、kind、展示信息、output kind、input/output JSON Schema、workflow、能力要求、状态、checksum 和发布时间。
    - `kind` 仅 `user_workflow` 或 `internal_step`。
    - T2-004 migration 自包含固化 `ppt.sales-business-review.v1@1.0.0` 与 `excel.sales-analysis-dashboard.v1@1.0.0`；runtime 同时核对 row 全部合同字段与 checksum，数据库内容漂移时 fail closed。

11. `generation_tasks`
    - 用户、项目、Brief、模型、idempotency key、组合 group、父任务、状态、进度、Skill/模型快照、预计/结算积分、错误类别、超时和时间戳。
    - `(user_id, idempotency_key)` 唯一；任务冻结确认时的 Brief/Input/Skill/Model/费用合同，状态与 timeout/checkpoint 是 Redis 丢失后的恢复事实。

12. `generation_task_steps`
    - 任务、阶段、尝试次数、状态、checkpoint、开始/结束、错误分类、脱敏错误。
    - `(task_id, step_code)` 唯一；checkpoint 区分尚未进入外部 Provider 的 safe retry 与结果未知的 in-flight Provider call。

13. `generation_task_inputs`
    - 任务与资产、模板、术语库的关系及版本快照。
    - `(task_id, input_kind, source_id, source_version)` 唯一；只保存稳定 ID/version/checksum/合同 snapshot，不保存文件正文或 storage key。

14. `provider_calls`
    - 保存可空 Brief group/revision、可空 generation task/step、attempt、Provider、模型、Credential ID、Provider Request ID、状态、token usage、耗时、可空费用、错误分类、脱敏标记和时间。
    - Brief 生成使用 `(brief_group_id, attempt)`；task execution 使用 `(task_step_id, attempt)`，两种 scope 互不冲突。成功 Brief 保存后，初次 schema-invalid 与 repair call 均关联最终 revision。
    - 不保存明文 API Key、Prompt、响应正文、完整用户文件、本地路径或 storage key。

15. `outbox_events`
    - 事件类型、aggregate ID、payload、状态、重试次数、下一投递时间；保证 DB commit 后可恢复投递。
    - `(event_type, idempotency_key)` 唯一；published-before-marked 允许 at-least-once 重投，Worker 依靠数据库 task/step 状态去重。

16. `credit_ledger`
    - 用户、任务、流水类型、整数数量、余额快照、关联流水、idempotency key、说明、时间。
    - 只追加；它是账务真相，`users.credit_balance` 只是同事务缓存。reserve 为负数，release 为正数，finalize 以零金额 marker 固化成功结算。

17. `ai_providers`
    - 厂家、显示名称、protocol、base URL、状态、默认 timeout、非敏感 JSON 配置、创建/更新时间。

18. `ai_models`
    - Provider、Credential、model code、展示名称、能力、context、输出上限、用户可见、推荐状态、积分倍率、允许 Skills、状态和时间戳。

19. `provider_credentials`
    - 每行只存一个 API Key：唯一 ID、Provider、名称、Fernet encrypted key、SHA-256 fingerprint、状态、RPM、TPM、最大并发、最近测试结果/时间、轮换来源、创建管理员和时间戳。

20. `system_settings`
    - 非敏感平台配置、文件限制、feature flag 和默认值；API Key 禁止进入此表。

21. `audit_logs`
    - actor、action、target type/id、IP、User-Agent、原因、结果、脱敏 JSON context、Trace ID 和时间；只追加。
    - T4-002 固化 IP `/24` 或 `/64` 摘要、单行 bounded User-Agent、context 白名单与
      失败结果；不保存密码、Token、Key、storage key、签名 URL 或磁盘路径。

22. `workflow_tasks`
    - 用户、项目、Brief group、关联 generation task、同用户幂等键、标题、结构化请求
      snapshot、输出类型、stage/status/progress、系统备注、稳定失败码、安全失败原因、
      投递序号和生命周期时间。
    - `request_snapshot` 只保存重放 Brief 所需的 ID、Skill、目标和受众，不保存文件正文、
      Evidence、Prompt、Provider 原始响应、Credential、路径或 storage key。
    - Brief 成功后关联稳定 group；确认后按该 group 唯一关联 `generation_tasks`，列表和
      详情投影 generation task 的权威状态、进度、积分与失败结果。

## 关键唯一约束

| 表 | 唯一键 | 目的 |
|---|---|---|
| `users` | `(phone_country_code, phone_number)` | 防止重复账号 |
| `projects` | `(active_default_owner_id)` generated key | 每个用户最多一个未删除的默认项目 |
| `skills` | `(skill_code, version)` | Skill 版本不可歧义 |
| `briefs` | `(brief_group_id, revision)` | Brief 历史修订不可歧义 |
| `provider_calls` | `(brief_group_id, attempt)` | 同一 Brief 生成 attempt 唯一 |
| `provider_calls` | `(task_step_id, attempt)` | 同一任务步骤 Provider attempt 唯一 |
| `generation_tasks` | `(user_id, idempotency_key)` | 重复提交只创建一个任务 |
| `workflow_tasks` | `(user_id, idempotency_key)` | 点击生成的幂等重放返回同一工作流 |
| `workflow_tasks` | `(brief_group_id)` | 一个 Brief 修订组只属于一个工作流 |
| `workflow_tasks` | `(generation_task_id)` | 一个文件生成任务只投影到一个工作流 |
| `generation_task_steps` | `(task_id, step_code)` | 每个任务阶段 checkpoint 唯一 |
| `outbox_events` | `(event_type, idempotency_key)` | 同一业务事件只创建一条 Outbox |
| `credit_ledger` | `(user_id, idempotency_key, entry_type)` | 防止重复预留/结算/释放 |
| `file_assets` | `(storage_provider, storage_key)` | 存储定位唯一 |
| `file_assets` | `(user_id, idempotency_key)` | 同一用户上传重放只创建一个资产 |
| `term_libraries` | `(library_id, version)` | 稳定库 ID 下每个不可变版本唯一 |
| `term_items` | `(term_library_version_id, item_id)` | 每个库 snapshot 内条目稳定 ID 唯一 |
| `term_items` | `(term_library_version_id, canonical_term)` | 单一 snapshot 内标准术语不重复 |
| `ai_models` | `(provider_id, model_code, credential_id)` | 模型与独立 Credential 绑定唯一 |
| `provider_credentials` | `(provider_id, key_fingerprint)` | 防止同 Provider 重复 Key |

## 关系与事务边界

- 注册事务：校验并锁定 `invite_codes`，创建 `users`，写入 `credit_ledger`，同步余额缓存。
- T1-005 上传边界：先提交带不可变 quarantine key、`uploaded` 状态和幂等键的 `file_assets` checkpoint，再流式写文件；signature/project cleanup 成功时删除 checkpoint，cleanup 失败保留 `deleting`，最终 metadata commit 异常或 cancellation 时保留 `uploaded` 与文件定位，避免无数据库记录的 orphan file。写库幂等冲突发生在文件 I/O 前。`outbox_events` 尚未建立，T3-001 接入 Outbox 后再把后续处理投递纳入数据库事务边界。
- T2-002 证据边界：解析结果落盘后先在同一资产行提交 deterministic Manifest key 和 `building`，再生成/校验/原子写入 Manifest；最终条件更新一次性写入 `processing_status=ready`、`manifest_status=valid` 和摘要 metadata。暂时性 OCR 失败先精确清理本轮解析/Manifest 输出，再以 exponential backoff 回到 `quarantined`；第 3 次失败稳定拒绝，不产生伪造证据或无限重试。用户删除资产时必须按记录的 exact keys 幂等清理原文件、解析结果与 Manifest，任一清理失败都保留 `deleting`，不得伪装成 `deleted`。
- T2-003 术语边界：owner-scoped mutation 以 locking read 获取最新 active 库版本，同一事务插入下一库版本与完整条目 snapshot；历史 Brief/任务只引用稳定 `library_id + version`，回滚规则只选择旧版本，不改写 Manifest、Brief 或历史 snapshot。
- T2-004 Brief 边界：先 owner-scope 校验项目、`ready/valid` 资产、Manifest integrity、显式术语库 version、Skill row 全合同、发布模型/Provider/Credential；只把 bounded evidence 与选定术语规则作为 untrusted user context 发送给唯一选定 Agnes。每次调用先写脱敏 `provider_calls`，合法响应再以新 `brief_group_id + revision=1` 保存不可变 Brief 并回链 calls；Schema/evidence/snapshot 失败只修复一次，仍失败不创建 Brief 或积分记录。timeout 只写 `provider_uncertain` call，不自动重试或切换 Provider。
- T2-005 Preflight 边界：GET 可 owner-scoped 读取历史 Revision；PATCH 同时锁定目标行和 group 最新行，只有目标仍为最新且 `expected_revision` 匹配时才追加新 Revision。Preflight/confirm 锁定当前行并复验最新 Revision、资产版本/Manifest、Evidence blocker、Skill/template/model/Provider/Credential；状态和不可变 snapshot 在同一事务提交。费用变化或新增 blocker 先持久化最新 Preflight snapshot，再返回稳定 409；确认只把 Brief 置为 generation-ready `queued` 并锁定 multiplier/子输出费用/总预计积分，不创建任务、ledger 或 Outbox。
- T3-001 生成事务：锁定 owner 的最新 confirmed Brief、Model/Credential/Provider 与用户余额，复验 identity/capability/pricing/子输出总和，在同一事务创建 task、steps、inputs、负数 reserve ledger 与首个 Outbox；同一 user/idempotency key 重放返回既有结果，余额不足或 Outbox 写入失败整体回滚。
- T3-001 执行/恢复边界：MySQL task/step checkpoint 为权威，Redis 只承载可丢失 queue/limit。published-before-marked 允许重复投递但数据库 claim 去重；safe stale step 复位后重新入队，已进入 Provider 且结果未知的 checkpoint 转 `provider_uncertain`。
- T3-001 结算事务：全成功写幂等 finalize marker；全失败/可取消任务写 release；partial success 按成功子输出费用结算并 release 余量。所有流水只追加，`provider_uncertain` 保留 reserve。
- Post-Alpha workflow 创建边界：同一事务写 `workflow_tasks` 与 `brief.requested.v1`
  Outbox；Redis queue 不承载唯一任务状态。专用 worker 以数据库 claim 去重，成功回链
  Brief group，确定失败持久化稳定码与脱敏原因，Provider in-flight stale 收口为
  `provider_uncertain` 且不自动重试。
- T3-002 PPT 输出边界：`render:pptx` step 先以稳定 idempotency key 创建 `parsing` 资产 checkpoint，Renderer 结果先写 step checkpoint，再以 `users/{user_id}/outputs/{asset_id}/presentation.pptx` 原子持久化并最终置 `ready`。`generated_task_id` 关联生成任务；同 Plan replay 返回同一资产，不覆盖已完成文件，不同 Plan、模板 snapshot 漂移、文件 hash/size 漂移全部 fail closed。
- T3-003 PPT 质量边界：原始 `presentation.pptx` 保持不可变；质量报告、PDF、逐页 PNG 与可选 repaired PPTX 使用同一 asset 下固定 `quality/` key。`file_assets` 保存 quality status、report schema/engine/hash/key、preview keys、validated artifact hash/size/key、repair count 与 checked time；只有报告与全部 artifact integrity 一致时完成 checkpoint 或 replay。最多一次修复，修复文件不覆盖原输出。
- T3-004 Excel 输出边界：原始 `analysis.xlsx` 使用
  `users/{user_id}/outputs/{asset_id}/analysis.xlsx` 固定 key 原子保存且不可覆盖；
  Plan SHA-256、Schema/Renderer/template version 进入输出 trace 和 XLSX custom
  properties。LibreOffice 只读取该原件并在 shared-work 写独立 validation copy 与
  `workbook-validation-report.v1`；完成/replay 同时复验原件、copy、report 和
  formula/cache diff。
- T3-005 Excel QA/组合边界：不新增表或 migration；复用 `file_assets` 的通用 quality
  metadata 保存 `workbook-quality-report.v1`、validated artifact 和 status，复用
  `generation_task_steps.checkpoint` 保存 output asset/version、quality/download 状态与
  estimated credits。`generation_tasks` 聚合两个 step，`credit_ledger` 仅追加幂等
  finalize/release；Redis 不承载唯一输出或结算状态。
- Credential 操作：只通过 `credential_id` 关联；Reveal、测试和轮换写 `audit_logs`，任何日志不得含明文 Key。
- 管理员用户/积分操作：重新认证后，状态、密码/Session、ledger 与成功 audit 在同一
  数据库事务提交；目标不存在、余额不足等失败 audit 使用独立提交，不能随失败事务回滚。
- 管理员资产操作：权限判断、业务结果和 audit 写入必须具备可追溯的一致性边界；只按
  数据库 owner/asset exact keys 操作。删除成功 audit 记录活动文件清理状态与最长
  `backup_retention_days=30` 策略，不伪造不受应用控制的备份删除。

## 状态字段

- 资产：`uploaded`、`quarantined`、`scanning`、`parsing`、`ready`、`rejected`、`deleting`、`deleted`。
- 生成任务：`draft`、`preflight`、`needs_resolution`、`queued`、`running`、`succeeded`、`partial_success`、`provider_uncertain`、`failed`、`cancelled`。
- 工作流任务：stage 为 `brief_queued`、`brief_generating`、`awaiting_confirmation`、
  `generation_queued`、`generation_running` 或终态；status 为 `queued`、`running`、
  `awaiting_confirmation`、`succeeded`、`partial_success`、`provider_uncertain`、
  `failed`、`cancelled`。
- 质量：`passed`、`passed_with_warnings`、`blocked`。
- 积分流水：`registration_grant`、`admin_grant`、`generation_reserve`、`generation_finalize`、`generation_release`、`refund`。

## Migration gate

- `T1-002` 已创建 `20260722_0001` 初始空 migration 与基础连接；应用启动不自动建表。
- `T1-003` 已创建 `20260722_0002`，建立 `users`、`user_sessions`、`invite_codes`、`credit_ledger`；UUID 为 `BINARY(16)`，时间为 MySQL `DATETIME(6)`。
- `T1-003` runtime 补验新增 `20260722_0003`，为上述 4 张表及全部 41 个字段写入非空中文 COMMENT；2026-07-22 已在本机 MySQL 8.0.43 空库真实升级并通过 `information_schema` 与 `alembic check` 核对。
- `T1-004` 新增 `20260722_0004`，建立 `ai_providers`、`provider_credentials`、`ai_models`、`audit_logs`；2026-07-22 已在本机 MySQL 从 `0003` 真实升级，4/4 table comments、52/52 column comments、两项关键唯一约束通过 `information_schema` 与事务内 rollback probe 核对，`alembic check` 无 drift。
- `T1-005` 新增 `20260722_0005`，建立 `projects`、`file_assets`，包含
  owner/project/parent 外键、active default generated key、storage location 与 user
  idempotency 唯一约束及中文注释。T4-004 首次从 utf8mb4 MySQL 空库完整升级时发现
  `(storage_provider VARCHAR(32), storage_key VARCHAR(768))` 可能超过 InnoDB 3072-byte
  key 上限；两个只承载服务端 ASCII locator 的列已收紧为 `ascii_bin`，模型与 migration
  同步。`0011` 改变 `provider_calls.brief_group_id` nullable 时同时显式保留既有中文
  COMMENT，避免 MySQL `ALTER COLUMN` 产生 model drift。第二个隔离 utf8mb4 MySQL
  database 已从零升级到 `20260723_0013 (head)`，`alembic check` 为
  `No new upgrade operations detected`；旧失败 database 未删除，保留现场证据。
- `T2-001` 新增 `20260723_0006`，只向 `file_assets` additive 增加 8 个安全处理 metadata 字段；SQLite 空库完整升级、MySQL dialect offline SQL、中文 COMMENT 与唯一 Head `20260723_0006` 已验证。当前会话未读取本地 `.env`，未把 offline 结果冒充真实 MySQL runtime upgrade。
- `T2-002` 新增 `20260723_0007`，只向 `file_assets` additive 增加 9 个 Evidence Manifest 与 OCR retry metadata 字段；真实 MySQL runtime 结果以本任务执行记录为准。
- `T2-003` 新增 `20260723_0008`，建立不可变 `term_libraries` 与 `term_items` snapshot 表、owner/project/previous-version 外键、3 项版本唯一约束和中文 COMMENT。SQLite 空库完整升级与单一 Head、MySQL dialect offline DDL 已验证；本任务未读取 `.env`，未运行真实 MySQL `0008` upgrade。
- `T2-004` 新增 `20260723_0009`，建立 `skills`、`briefs`、`provider_calls` 并以 migration 内冻结 payload 固化两个 Alpha Skill；SQLite 空库完整升级、单一 Head 与 MySQL dialect offline DDL 已验证，真实 Agnes Contract 未 opt-in。
- `T2-005` 新增 `20260723_0010`，只向 `briefs` additive 增加可空 `preflight_snapshot JSON` 与 `estimated_credits INTEGER`；SQLite 空库完整升级测试、唯一 Head `20260723_0010` 与 MySQL dialect offline DDL 已通过。本任务未读取 `.env`，未运行真实 MySQL `0010` upgrade。
- `T3-003` 新增 `20260723_0013`，只向 `file_assets` additive 增加 11 个 PPT quality metadata 字段与 status index；SQLite 空库完整升级、历史 migration 连续性、单一 Head 与 MySQL dialect offline DDL 已验证。本任务未读取 `.env`，未运行真实 MySQL `0013` upgrade。
- `T3-001` 新增 `20260723_0011`，建立 `generation_tasks`、`generation_task_steps`、`generation_task_inputs`、`outbox_events`，向 `credit_ledger` 增加 task 外键，并向 `provider_calls` additive 增加 task/step scope 与唯一约束。SQLite 空库完整升级、唯一 Head、MySQL dialect offline upgrade/downgrade 已通过；未读取 `.env`，未运行真实 MySQL/Redis runtime。
- `T3-002` 新增 `20260723_0012`，只为既有 `file_assets.generated_task_id` 增加命名外键 `fk_file_assets_generated_task`。SQLite 空库完整升级、唯一 Head、历史 migration chain 和 MySQL dialect offline upgrade/downgrade 已通过；未读取 `.env`，未运行真实 MySQL runtime。
- 注册使用 `SELECT ... FOR UPDATE` 锁定邀请码，并在同一事务中增加次数、创建用户、写 `registration_grant` 和同步 `users.credit_balance`；任一写入失败整体回滚。
- 后续每个模型任务通过 additive migration 演进；禁止删除或改写历史 migration。
- Alpha 封版基线从空数据库完整升级并验证 21 张表、唯一约束和外键。
- `T4-005` 新增 additive `20260727_0014`，补齐 `templates` 与 `system_settings`。
  独立 utf8mb4 MySQL 验证库从 base 完整升级至唯一 Head；实测 21 张业务表、40 个外键、
  22 个唯一约束，`alembic check` 无 drift。验证库保留为现场证据。
- Post-Alpha 新增 additive `20260727_0015`，建立 `workflow_tasks`、owner/project/
  generation 外键和三项幂等/关联唯一约束。真实 MySQL 已从 `0014` 升级至唯一
  `20260727_0015`，当前作为 P5-003 migration 的直接前序。
- `P5-003` 新增 additive `20260729_0016`，建立 owner-scoped `chat_threads`、
  `chat_messages`、`chat_runs`，并向 `provider_calls` 增加 redacted Chat run scope 与
  `(chat_run_id, attempt)` 唯一约束。真实 MySQL 从 `0015` 升级至唯一
  `20260729_0016`，真实 run 验证先 INSERT run、再绑定
  assistant 外键，2.5/2.0 ProviderCall 均为 redacted terminal metadata。
- `P5-004` 新增 additive `20260729_0017`，建立 `deck_drafts`、
  `deck_draft_revisions` 与 `deck_draft_inputs`，当前共 28 张业务表。
- `P5-005` 新增 additive `20260729_0018`，为 `templates` 增加 nullable checksum 并
  发布三套完整原创 PPTX catalog row；真实 MySQL 已从 `0017` 升级到唯一
  `20260729_0018 (head)`。新 Deck revision 和 generation task 冻结
  code/version/checksum；旧 snapshot 缺 checksum 保持兼容，错误 checksum fail closed。
