# Office AI Alpha API 基线

- 前缀：`/api/v1`
- 数据格式：JSON；文件上传与下载除外
- 身份：短期 Session Access Token + 可撤销 Refresh Token
- 状态：已完成 T1、T2、`T3-001`–`T3-005`、`T4-001`–`T4-002`；管理员最高权限、统一重新认证与 audit HTTP 闭环已实现

## 共同行为

- 写接口接受 `Idempotency-Key`；生成和积分相关接口必须在数据库唯一约束下幂等。
- 错误响应包含稳定 `error_code`、用户可读中文 `message` 和 `trace_id`，不返回 stack trace 或敏感上下文。
- Alpha 列表接口使用稳定排序的 `page`、`page_size`；后续若改游标需作为显式 contract 变更。
- 所有资源接口按 user ownership 或 admin role 鉴权；客户端不能传入或获得任意磁盘路径。
- Credential reveal、密码重置、用户状态变更、积分调整、管理员资产预览/下载/删除需要重新认证和操作原因。
- 管理端敏感操作无论成功或失败都写 audit log；Secret 响应禁止缓存。
- 状态冲突使用明确错误码，不把 `provider_uncertain`、`partial_success` 或质量阻断折叠为通用 500。

建议错误 envelope：

```json
{
  "error": {
    "error_code": "stable_machine_code",
    "message": "可读中文信息",
    "trace_id": "uuid"
  }
}
```

## Post-Alpha Chat、Deck 与 Media 合同（`post-alpha-contract.v1`）

本节是 P5-001 冻结的 additive API。所有路径均位于 `/api/v1`；P5-001 只定义合同，
不表示端点已经实现。所有响应先验证 Session 和 owner scope；跨用户 ID 与不存在 ID
使用相同 not-found 语义。除 SSE 外，所有本节响应均设置
`Cache-Control: private, no-store`；写请求必须使用 8–128 字符 `Idempotency-Key`，
同 owner/key/payload 重放返回原结果，不同 payload 返回 `409 idempotency_conflict`。

### Chat Thread、消息与删除

| Method | Path | 合同 |
|---|---|---|
| POST | `/chat/threads` | 新建 owner-scoped 会话；默认模型必须来自当前已发布 Chat capability，2.5 仅为推荐值 |
| GET | `/chat/threads` | 按 `updated_at,id` 倒序游标分页；默认排除 soft-deleted |
| GET | `/chat/threads/{thread_id}` | 返回会话与选定 branch 的消息；不返回 system Prompt、隐藏 reasoning 或 Provider response |
| PATCH | `/chat/threads/{thread_id}` | 重命名、切换后续 run 默认模型或 mode；不修改历史 run snapshot |
| DELETE | `/chat/threads/{thread_id}` | soft delete；30 天内可恢复，重复删除幂等 |
| POST | `/chat/threads/{thread_id}/restore` | grace period 内恢复；已 purge 返回 `chat_thread_purged` |
| GET | `/chat/threads/{thread_id}/export` | owner-scoped UTF-8 JSON 导出正文、branch、provenance 和时间；不含 Secret/Prompt/response/hidden reasoning |
| POST | `/chat/threads/{thread_id}/purge` | 当前密码、会话标题确认和 reason 后创建彻底删除；活动正文 24 小时内清除 |

Thread create/patch 只接受已发布 `model_id`，服务端冻结真实
provider/credential/model code/capability snapshot。新 Chat 推荐 `agnes-2.5-flash`；
`agnes-2.0-flash` 必须保留为用户显式选项，旧文件流程默认不变。模型不可用时返回
`chat_model_unavailable`，禁止静默切换。Thinking 使用请求中的 `thinking_enabled`，
默认 `false`；模型 snapshot 没有 capability 时返回 `chat_thinking_unsupported`。

编辑后重发与重新生成均通过 stream request 表达：

- 普通发送提供 `content` 和可空 `parent_message_id`。
- 编辑后重发提供 `supersedes_message_id` 与新正文，创建新的 user message branch。
- 重新生成提供 `regenerate_from_message_id`，创建新的 assistant sibling/run。
- 三者互斥；历史 message/run 永不 UPDATE 覆盖。消息正文最大 32768 字符。
- 首期 `context_asset_ids` 必须省略或为空；非空稳定返回
  `chat_file_context_not_enabled`。文件只在转 Deck Draft 时选择。

### Chat SSE

| Method | Path | 合同 |
|---|---|---|
| POST | `/chat/threads/{thread_id}/messages:stream` | 同事务保存 user message、assistant placeholder 和 `queued` run 后建立 SSE |
| GET | `/chat/runs/{run_id}/stream` | 用 `Last-Event-ID` 重连同 owner run；只恢复当前 run |
| POST | `/chat/runs/{run_id}/cancel` | 幂等请求停止；不因取消再次调用或切换模型 |

SSE Header 固定为 `Content-Type: text/event-stream; charset=utf-8`、
`Cache-Control: private, no-store`、`X-Accel-Buffering: no`。语义事件 envelope 为
`chat-sse.v1`：

```json
{
  "schema_version": "chat-sse.v1",
  "run_id": "uuid",
  "thread_id": "uuid",
  "sequence": 3,
  "occurred_at": "UTC timestamp",
  "trace_id": "uuid",
  "payload": {}
}
```

每个语义 frame 同时设置 `id: <run_id>:<sequence>` 和下列 `event`；同一 run 的
`sequence` 从 1 严格递增：

1. 恰好一个 `run.started`。
2. 零到多个 `message.delta`；delta 是不可信 Markdown 文本，不含隐藏 reasoning。
3. 重连时可返回一个 `message.snapshot`，内容为已持久化的累计 partial；不承诺逐 token
   replay，客户端用 snapshot 替换当前 partial 后按 sequence 去重。
4. 工具仅可产生 `tool.proposed` 或 `tool.confirmation_required`；未收到独立用户确认前
   不执行任务创建、图片或视频。
5. 恰好一个终态：`run.completed`、`run.cancelled_partial`、`run.failed` 或
   `run.provider_uncertain`。

`heartbeat` 每 15 秒可发送且没有 `id/sequence`，不参与 replay。服务端先 checkpoint
assistant partial 再提高 sequence。网络可能重复最后 frame，客户端必须按 run/sequence
去重；MySQL 终态只提交一次。`Last-Event-ID` 不是当前 run、早于可用 checkpoint 或格式
非法时返回 `409 chat_stream_resume_invalid`，不会重放其他 run。

浏览器断开不是成功或已取消证明。FastAPI 必须请求上游取消并收口：上游确认停止时保存
现有正文为 `cancelled_partial`；请求已发送但无法确定结果时保存
`provider_uncertain`，禁止自动重试或扣费重放。终态 run 重连只返回
`message.snapshot`（如有）和持久终态。

P5-003 已实现上述 Chat thread CRUD/search、双模型 stream、reconnect/cancel 与
branch/regenerate 合同。真实 MySQL/SSE 证明 2.5/2.0 均由同一用户显式选择并分别
`succeeded`；同 idempotency key 不重复调用，Provider 失败不 fallback。Restore、
export、purge 与 Chat tool invocation 仍按后续任务边界保持未实现，不能因已有 CRUD
端点而声明可用。

### Deck Draft

| Method | Path | 合同 |
|---|---|---|
| POST | `/chat/messages/{message_id}/deck-drafts` | 从成功 assistant message 创建 `deck-brief.v1` revision 1；可选 `asset_ids` 仅在此处接入 |
| GET | `/deck-drafts/{draft_id}` | 返回 stable draft identity、最新或显式 revision、Preflight 和媒体摘要 |
| PATCH | `/deck-drafts/{draft_id}` | 要求 `expected_revision`，创建不可变新 revision/checksum |
| POST | `/deck-drafts/{draft_id}/confirm` | 确认最新 revision；确认快照不能原地覆盖 |
| POST | `/deck-drafts/{draft_id}/preflight` | 复验 revision、来源、Evidence、Skill、模板、模型、媒体和费用 |
| POST | `/deck-drafts/{draft_id}/media/images` | 对显式 slide ID 创建图片任务；需要用户确认和幂等键 |
| POST | `/deck-drafts/{draft_id}/media/videos` | 对显式 slide ID 创建视频任务；默认只允许文生视频和独立附件 |
| POST | `/deck-drafts/{draft_id}/generations` | 仅对最新 confirmed/ready revision 创建既有 PPTX generation task |

创建 Draft 前必须收集主题、受众、语言、页数、语气、来源模式和显式 Skill；最多 40 页。
`asset_ids` 最多 20 个、总量 200 MB，且必须是当前 owner、版本冻结、`ready/valid`。
灵感、资料和混合模式分别保留 `agnes_inference`、Evidence 和两者分离的 provenance。
Schema 或引用非法只允许一次 bounded repair；仍失败返回 `deck_schema_invalid` 或
`deck_evidence_invalid`，不创建 Draft。PATCH 只能更新用户可编辑内容、排序、显式 Skill/
template/media 选择，不能改写 source snapshot。`expected_revision` 过期返回
`deck_revision_stale`。

Preflight 的 `blocking/incompatible` 必须归零，且高风险主题已提交
`high_risk_confirmation_required`，才能进入 `ready`。Generation endpoint 复用现有
generation task、Outbox、积分、Renderer、QA 和下载合同；返回同一权威 task ID，
不创建第二套文件生成状态机。

P5-004 已实现六条 Deck endpoint，P5-006/P5-007 已实现 image/video media endpoint。
所有响应均为
`private, no-store`；create/generation 要求 `Idempotency-Key`，PATCH 要求
`expected_revision`，confirm 要求当前 revision。成功 confirm 会建立受控 bridge Brief，
Preflight 与 generation 始终调用既有服务；Chat assistant message 的 additive projection
只返回 `deck_draft_id/deck_status/generation_task_id/generation_status`。图片 endpoint
返回 owner-scoped 权威 job/asset 摘要；video endpoint 仅对显式确认的 text-to-video
请求可用，embedding/public URL 路径继续 fail closed。

### Media Job

| Method | Path | 合同 |
|---|---|---|
| GET | `/media/jobs/{job_id}` | owner-scoped 状态、真实 progress、实际尺寸/时长和输出资产摘要 |
| POST | `/media/jobs/{job_id}/cancel` | 幂等取消；已提交且结果不确定时收口 `provider_uncertain` |

媒体创建返回 `202` 和 `media_job_id/workflow_task_id`。一个幂等键只对应一个
draft revision + slide + kind + prompt hash + model/pricing snapshot；重新生成必须使用
新键并创建新 job/asset，永不覆盖旧结果。图片 adapter 只接受文本或受控 Data URI，
请求 2K/16:9 只是意图，最终宽高以 Provider bytes 解码结果为权威。public URL 输入默认
关闭。

视频首期仅允许用户明确选择的页面创建文生视频任务。保存上游 opaque Provider ID，
由服务端轮询真实 `queued/in_progress/completed/failed` 并映射为本地状态；前端不得用
timer 伪造 progress。图生视频/关键帧因 public URL 安全传输尚未批准返回
`media_public_url_input_disabled`。`OFFICE_AI_VIDEO_EMBED_ENABLED=false` 时成功视频只
产生独立 MP4 和海报帧；请求内嵌返回 `video_embedding_not_enabled`。轮询只对同一
opaque Provider ID 执行；可重试上游错误最多产生两次延迟 poll，连续失败进入
`provider_uncertain`，不会再次 create 或重复 reserve。

### 稳定错误与 HTTP

| HTTP | error_code | 边界 |
|---:|---|---|
| 400 | `chat_request_invalid`, `deck_schema_invalid`, `media_request_invalid` | strict Schema/长度/枚举错误，不重试 |
| 401 | `session_invalid` | 不调用 Provider |
| 404 | `chat_thread_not_found`, `chat_run_not_found`, `chat_message_not_found`, `deck_draft_not_found`, `media_job_not_found` | 不泄露跨用户存在性 |
| 409 | `idempotency_conflict`, `chat_stream_resume_invalid`, `chat_run_not_active`, `deck_revision_stale`, `deck_preflight_blocked` | 状态或 snapshot 冲突 |
| 409 | `high_risk_confirmation_required`, `chat_file_context_not_enabled`, `video_embedding_not_enabled`, `media_public_url_input_disabled` | fail-closed feature Gate |
| 422 | `chat_model_unavailable`, `chat_thinking_unsupported`, `deck_evidence_invalid`, `media_capability_unavailable` | 发布 capability 不满足 |
| 429 | `chat_rate_limit_exceeded`, `chat_concurrency_exceeded`, `media_concurrency_exceeded` | 返回安全 `Retry-After` |
| 502/503 | `provider_failed` | 确定性上游失败，不静默切换模型 |
| 504 | `provider_uncertain` | 请求已提交但结果未知，不自动重试 |

产品默认 Chat admission 为每用户同时 1 个 run、20 次/小时、100 次/日；服务端还必须取
Provider/Credential RPM、TPM、最大并发和发布模型额度的最小值。当前 Provider 标价为零
不能被前端解释为永久免费；每个 run/media/generation 都冻结实际发布价格/积分 snapshot。

## Platform Health

Health endpoint 是不带 `/api/v1` 前缀的运行时探针，不承载业务数据：

| Method | Path | 说明 |
|---|---|---|
| GET | `/health/live` | 进程存活、应用可处理请求；响应和 Header 均携带 Trace ID |
| GET | `/health/ready` | MySQL 与 Redis 均可用时返回 `200 ready`；否则返回脱敏的 `503 service_not_ready` |

探针不得返回连接串、用户名、密码、内部异常或 stack trace。

## Auth

以下路径均位于 `/api/v1`。注册要求 `+86` 中国大陆手机号、长度 12–128 的密码、有效邀请码及明确接受协议。注册、登录、刷新与改密响应统一 `Cache-Control: no-store`；Access Token 使用 `Authorization: Bearer`，Refresh Token 每次使用后轮换。

| Method | Path | 说明 |
|---|---|---|
| POST | `/auth/register` | 邀请码与未注册 `+86` 手机号注册；同事务消费邀请码并赠送积分 |
| POST | `/auth/login` | 手机号密码登录，受 Redis 限速 |
| POST | `/auth/refresh` | 轮换 Refresh Token，数据库仅存 Hash |
| POST | `/auth/logout` | 撤销当前 Session |
| GET | `/auth/me` | 当前用户、角色、状态与强制改密标记 |
| POST | `/auth/change-password` | 修改密码并按策略撤销旧 Session |

Auth 稳定错误码包括 `phone_already_registered`、`invite_invalid`、`invite_expired`、`invite_exhausted`、`invalid_credentials`、`refresh_token_invalid`、`session_invalid`、`rate_limit_exceeded` 与 `auth_not_configured`。响应不得回显密码、邀请码或 Token。

## Projects 与 Assets

| Method | Path | 说明 |
|---|---|---|
| GET | `/projects` | 当前用户项目列表 |
| POST | `/projects` | 创建项目；直接生成时可自动创建 |
| PATCH | `/projects/{project_id}` | 改名或归档 |
| DELETE | `/projects/{project_id}` | 软删除并安排文件清理 |
| POST | `/assets/uploads` | 单文件 multipart 流式上传到 quarantine；必须提供 `Idempotency-Key` |
| GET | `/assets` | 当前用户资产列表 |
| GET | `/assets/{asset_id}` | 资产元数据与处理状态 |
| GET | `/assets/{asset_id}/preview` | 鉴权预览，不暴露 storage key |
| GET | `/assets/{asset_id}/download` | 鉴权下载 |
| DELETE | `/assets/{asset_id}` | `deleting -> deleted`，活动存储立即清理 |

Post-Alpha Workflow 仅在材料已进入 `rejected/invalid` 时显示行级删除按钮，并复用既有
owner-scoped `DELETE /assets/{asset_id}`。客户端按文件名确认，只有收到成功响应后才移除
当前行；取消或失败时保留原记录。Excel 深度解析的默认输入上限为 100 Sheet，100 Sheet
可接受，第 101 Sheet 以 `excel_sheet_limit_exceeded` fail closed；其他解析门禁不变。
Evidence source expansion 默认最多 11,563 项，在空值过滤和 Pydantic Evidence object
构建前执行；第 11,564 项继续返回 `evidence_item_limit_exceeded`。该值来自用户批准的
唯一 private 黄金 XLSX 只读结构校准，不改变 Manifest byte 上限或语义 blocker。

T1-005 上传支持 XLSX、XLSM、CSV、DOCX、PDF、PNG、JPG、JPEG、WEBP、TXT、MD 的扩展名/MIME 初检；PDF、Office ZIP 与图片同时检查最小 magic header。单文件默认上限 50 MB，图片默认上限 20 MB；同一用户重放相同 `Idempotency-Key` 时，`quarantined` 及后续已持久化状态返回既有资产且不重复读取或写入文件，`uploaded`/`deleting` 则在读取 body 前稳定返回 `409 asset_upload_in_progress`。单次 API 只接受一个 `file` 和至多一个 `project_id`，额外文件或未知 multipart 字段以 `upload_form_invalid` 拒绝；必须提供唯一、合法且与实际 bytes 一致的 `Content-Length`，不能使用 `Transfer-Encoding`。upload ASGI middleware 在读取 body 前验证 Bearer Session 和 replay policy；新请求先写入 middleware 自己的 1 MiB memory-threshold 受控 preflight spool，以 `max_file_bytes + 64 KiB` 验证完整 body 后才 replay 给 Starlette multipart parser。拒绝路径不会创建 parser file spool，临时 preflight spool 始终在 `finally` 关闭。20 文件/200 MB 是后续 generation input selection 与 T2-001 安全解析 gate，不以一次 multipart batch 实现。

资产响应不返回 `storage_key`、`parsed_storage_key`、`manifest_key`、Manifest SHA-256、磁盘路径或证据内容。T2-001 在原响应上增加可空 `parser_name`/`parser_version`、`processing_warnings`、`processing_error_code` 与脱敏 `processing_error_message`；T2-002 只增加安全的 `manifest_status`、`manifest_schema_version`、`evidence_engine_version`、`evidence_warning_count` 与 `evidence_blocker_count`。可供 Brief/Preflight 使用的唯一组合为 `processing_status=ready` 与 `manifest_status=valid`；它必须同时满足安全解析、版本化 Manifest Schema 校验、原子落盘和数据库条件更新。`manifest_status=retryable_error` 的资产仍为 `quarantined`，不得供 Brief 使用。preview/download 先做 owner scope 鉴权，响应包含 `Cache-Control: private, no-store` 与 `X-Content-Type-Options: nosniff`，preview 额外使用 `Content-Security-Policy: sandbox`。已完成的同 owner/idempotency replay 在 preflight spool 与 `request.form()` 前返回，HTTP body receive、multipart parser/spool 与 service upload 均不进入；incomplete replay 在相同位置返回 409，同样不消费 body。数据库 unique race fallback 使用同一 policy，不会把并发 `uploaded`/`deleting` checkpoint 当成 201 成功；signature/stream 失败且 cleanup 成功删除 checkpoint 后，later retry 可重新上传。新上传先提交 `uploaded` checkpoint，再写入文件并最终更新为 `quarantined`；若最终事务异常或 cancellation，文件仍由该 checkpoint 定位，cleanup 失败则保留 `deleting` 供恢复。cleanup/reconciliation failure 不替换 `file_signature_invalid`、`file_too_large`、unexpected stream error 或 cancellation 主因；direct/generic/cancellation 路径均写脱敏 `asset_recovery_failed` 日志与 checkpoint 状态。项目 PATCH 不接受显式 `null`；项目删除仅允许空项目。资产删除先检查活动父版本引用；`scanning/parsing` 期间返回 `409 asset_processing_in_progress`，防止 active worker 在删除完成后重新写出派生文件；其余状态只有原文件、解析结果和 Evidence Manifest 均清理成功后才标记 `deleted`，任一物理删除失败保留 `deleting` 并明确返回失败。T2-001/T2-002 可持久化处理错误码以完整 contract 表为准；上传/资产稳定错误码继续包括 `project_not_found`、`project_not_empty`、`project_update_invalid`、`project_id_invalid`、`file_required`、`upload_form_invalid`、`asset_not_found`、`asset_in_use`、`asset_processing_in_progress`、`asset_delete_failed`、`asset_upload_in_progress`、`upload_body_invalid`、`upload_body_too_large`、`quarantine_cleanup_failed`、`file_type_unsupported`、`file_mime_mismatch`、`file_signature_invalid`、`file_too_large` 与 `idempotency_key_invalid`。

### T2-001/T2-002 可持久化处理错误码

| processing_error_code |
|---|
| `archive_bomb_detected` |
| `archive_member_invalid` |
| `evidence_item_limit_exceeded` |
| `evidence_manifest_invalid` |
| `evidence_manifest_key_invalid` |
| `evidence_manifest_state_conflict` |
| `evidence_manifest_too_large` |
| `evidence_manifest_write_failed` |
| `evidence_source_invalid` |
| `excel_cell_limit_exceeded` |
| `excel_sheet_limit_exceeded` |
| `file_corrupt` |
| `file_encoding_unsupported` |
| `file_encrypted` |
| `file_integrity_mismatch` |
| `file_mime_mismatch` |
| `file_parse_failed` |
| `file_too_large` |
| `file_type_unsupported` |
| `file_unavailable` |
| `image_corrupt` |
| `image_decoded_too_large` |
| `image_too_large` |
| `malware_scan_failed` |
| `malware_scan_unavailable` |
| `ocr_input_unavailable` |
| `ocr_item_limit_exceeded` |
| `ocr_request_rejected` |
| `ocr_response_invalid` |
| `ocr_response_too_large` |
| `ocr_retry_exhausted` |
| `ocr_unavailable` |
| `office_xml_member_too_large` |
| `parsed_output_too_large` |
| `parsed_output_write_failed` |
| `parser_process_failed` |
| `parser_structure_limit_exceeded` |
| `parser_timeout` |
| `pdf_page_limit_exceeded` |
| `processing_cancelled` |
| `processing_failed` |
| `processing_lease_expired` |
| `processing_state_conflict` |
| `storage_provider_unsupported` |
| `unsafe_xml_detected` |
| `virus_detected` |

## Skills、Models、Templates 与术语

| Method | Path | 说明 |
|---|---|---|
| GET | `/skills` | 已发布且用户可见的 Skill |
| GET | `/skills/{skill_code}` | 指定 Skill 当前可用版本与能力要求 |
| GET | `/models` | 管理员发布且满足所选 Skill 能力的模型 |
| GET | `/templates` | 已发布原创 PPTX 模板摘要；可用 `category` 精确过滤 |
| GET | `/templates/{template_code}` | 指定 `version` 的认证模板详情 |
| GET | `/term-libraries` | 当前用户各术语库的最新 active snapshot |
| POST | `/term-libraries` | 创建个人或 owner-scoped 项目术语库 |
| GET | `/term-libraries/{library_id}` | 当前 snapshot；`version` 查询显式历史版本 |
| PATCH | `/term-libraries/{library_id}` | 新建库 metadata 版本，不原地覆盖 |
| DELETE | `/term-libraries/{library_id}` | 新建 deleted tombstone，历史版本仍可显式读取 |
| GET | `/term-libraries/{library_id}/items` | 当前或显式 version 的条目 snapshot |
| POST | `/term-libraries/{library_id}/items` | 增加标准术语、别名、单位与口径并新建库版本 |
| PATCH | `/term-libraries/{library_id}/items/{item_id}` | 更新条目并新建完整库版本 |
| DELETE | `/term-libraries/{library_id}/items/{item_id}` | 从新版本移除条目，不改写历史 snapshot |

T2-003 的 `library_id` 与 `item_id` 是跨版本稳定 ID；每次库或条目 mutation 都生成递增的不可变 version 行及完整条目 snapshot。默认读取最新 active 版本，只有显式 `version>=1` 才能读取历史版本；当前 tombstone、跨用户 ID 和不存在资源统一返回 `404 term_library_not_found`，条目缺失返回 `404 term_item_not_found`。项目库的 `project_id` 必须属于当前用户且未删除，不能引用其他用户项目。

P5-005 的 template list/detail 均要求有效 Session 并返回 `private, no-store`。服务只投影
三套 `owner_user_id IS NULL / source=system_original / status=published / pptx` row；
DB row 与 runtime catalog 的 code/version/checksum、metadata、布局或 Skill 任一漂移时
返回 `409 template_contract_invalid`，不降级为静态列表。preview 仅允许
`/template-previews/<certified-code>/(cover|representative).svg`，不返回 storage key、
本地路径或远程 URL。

Deck `PATCH /deck-drafts/{draft_id}` 新增可选 `template_code`：必须与当前 Skill 兼容并
要求 `expected_revision`，成功只追加新 revision；响应中的 `template_snapshot` 固定
code/version/checksum。Generation task snapshot 继承该冻结值；Renderer 成功响应回传
实际 registry checksum，Python adapter 不一致即拒绝。历史 snapshot 缺 checksum 时仍
按冻结 code/version 兼容重放，不接受错误 checksum。

术语条目支持标准术语、最多 100 个 NFKC 去重别名、canonical unit code、定义、指标口径和 `-1000..1000` 优先级。项目规则只覆盖同一用户同一项目的全局匹配；同层级、同优先级映射到不同标准术语时返回 `term_ambiguous` unresolved。`terminology-normalization.v1` 确定性处理绝对日期、数字、百分比、CNY/USD、万/亿倍率和销售数量单位；缺少年份、未知单位、显式单位冲突或多来源标准化值不一致不会被猜测或静默合并。派生 `NormalizedEvidenceItem` 保留 source fact 的 asset/version/location/raw/provenance，并附加规则版本与术语库 version snapshot；它不改写已落盘的 `evidence-manifest.v1`。

T2-004 已实现 `/skills`、`/skills/{skill_code}` 与 `/briefs/generate`。Skills API 要求有效 Session，只返回 migration 固化且 row 全合同/checksum 与 runtime registry 一致的两个 published `1.0.0` Skill。Brief generate request 只接受 `project_id`、1–20 个 `asset_ids`、显式 `term_library_versions`、1–2 个固定 `skill_codes`、一个 published `model_id`、goal/audience 与 must include/exclude；不接受客户端 evidence 正文、本地路径、Provider Key 或任意 Skill。响应为不可变 revision 1 `draft`，包含严格 17 字段 Structured Brief、group/revision ID 与内容 checksum，并返回 `Cache-Control: private, no-store`。

T2-004 生成前校验 owner project/assets、`ready` Manifest key/SHA/asset version、术语库 owner/project/version、Skill 全合同、模型能力及 Provider/Credential 状态。Provider 只收到 bounded evidence 与选定术语规则，所有文档内容作为 untrusted user data；`brief-evidence-context.v2` 将重复的 asset identity/version 提升到 asset table，按 location kind/Sheet/Evidence type 分组，并使用确定性短引用承载全部 Evidence。模型只允许引用本次 Context 中的短引用；应用在 strict Schema/snapshot/evidence 校验前映射回原始不可变 Evidence ID，未知引用以 `brief_evidence_invalid` fail closed。模型返回必须保持 goal/audience/asset/term/Skill/model/include/exclude/output-kind authoritative snapshot，`file/calculation` fact 和 `agnes_inference` 均必须有 evidence。JSON/Schema/snapshot/evidence 失败只修复一次；第二次失败返回对应 `brief_schema_invalid`、`brief_snapshot_mismatch` 或 `brief_evidence_invalid`，不保存 Brief。压缩后完整 message 仍超出 `min(model.context_window, 256K)` 时在调用前返回 `context_budget_exceeded`；不抽样或截断必需 Evidence。timeout 返回 `provider_uncertain` 且不自动重试，`401/403` 暂停所选 Credential，不静默切换 Provider。

Post-Alpha Schema guidance 修复后，generation request 显式携带完整、紧凑的
`StructuredBrief` JSON Schema，而不只传顶层字段名。第一次 validation 失败时，repair
只接收最多 24 条、每条最多 160 字符的安全 `field.path:error_type` hints；JSON、
snapshot 与 Evidence 错误使用稳定类别，不携带输入值。Provider response、Prompt 和
validation input 仍不落库/日志，用户 API 错误 envelope 仍只返回稳定 code 与安全中文
message；严格校验和最多一次 repair 的 contract 不变。

## Brief 与 Generation

| Method | Path | 说明 |
|---|---|---|
| POST | `/workflow-tasks` | 幂等创建异步工作流任务并立即返回 `202` |
| GET | `/workflow-tasks` | 当前用户最近最多 100 条工作流任务 |
| GET | `/workflow-tasks/{task_id}` | 当前用户工作流进度、备注、失败原因与关联资源 |
| POST | `/briefs/generate` | 兼容用同步 Brief 生成；用户工作流不再调用 |
| PATCH | `/briefs/{brief_id}` | 新建不可变 revision，不原地覆盖历史版本 |
| POST | `/briefs/{brief_id}/confirm` | 用户确认当前 revision |
| POST | `/generations/preflight` | 返回冲突、阻断项和不可提高的预计积分 |
| POST | `/generations` | 幂等创建组合任务并预留积分 |
| GET | `/generations/{task_id}` | 持久任务、步骤、子输出与质量状态 |
| POST | `/generations/{task_id}/cancel` | 按状态机取消并释放可释放预留 |
| POST | `/generations/{task_id}/retry` | 仅对允许重试的确定失败执行；不重复扣费 |
| GET | `/generations/{task_id}/outputs` | 当前用户可下载的不可变输出版本 |

生成状态为：`draft`、`preflight`、`needs_resolution`、`queued`、`running`、`succeeded`、`partial_success`、`provider_uncertain`、`failed`、`cancelled`。

Post-Alpha 用户入口使用 `POST /workflow-tasks`。请求复用 Structured Brief 的严格
选择 contract，并要求 8–128 字符 `Idempotency-Key`；服务只在短事务内校验 Session 与
owner project，写入 workflow task 和专用 Outbox，首次返回 `202`，同用户幂等重放返回
`200` 与原任务。List/detail 均 owner-scoped、按创建时间倒序并使用
`Cache-Control: private, no-store`。

工作流快照返回 task/project/Brief/generation ID、标题、输出类型、stage、status、
0–100 progress、note、稳定 `failure_code`、安全 `failure_reason`、预计/结算积分和时间。
Brief worker 成功后进入 `awaiting_confirmation`；失败持久化原因，例如
`brief_schema_invalid / Structured Brief Schema 无效`。关联 generation task 后，
status/progress/credits/failure 以 `generation_tasks` 为权威投影。跨用户或不存在 ID
统一返回 `workflow_task_not_found`；服务未配置返回 `workflow_not_configured`。

T2-005 已实现 owner-scoped `GET /briefs/{brief_id}`、`PATCH /briefs/{brief_id}`、`POST /briefs/{brief_id}/confirm` 与 `POST /generations/preflight`。GET 可读取 owner 的历史 Revision；PATCH 只允许基于最新 Revision 追加用户可编辑字段、系统模板版本和匹配当前 Preflight blocker 的显式 resolution，不允许客户端替换来源、术语、Skill、模型或 Evidence 引用。Preflight 每次复验资产版本/Manifest、当前 Structured Brief 实际引用的 Evidence blocker、Brief unresolved item、Skill 全合同、系统模板以及当前 Agnes Provider/Credential/模型能力，返回 `auto_merge`、`needs_confirmation`、`blocking`、`incompatible` 四类结果。

Post-Alpha 单位 resolution 将 Manifest 的 `numeric_unit_unknown` 与运行时
`unit_unknown` 归一为一个 `unit_unknown` finding，并按 Evidence ID 去重。finding 只返回
Sheet/单元格、页码、段落或行列等安全定位，不返回文件正文；未被本次 Brief 引用的
Evidence 不阻断本次输出。`assign_unit` 只接受受支持的 canonical unit，必须匹配当前
blocking finding，成功后追加新 Revision 并固化到 `source_snapshot` 与 generation Brief
input snapshot。原始 Manifest 和 Evidence 保持不可变，非法 unit、伪造 ID 或过期
Revision 均 fail closed。

Alpha 每个输出按 `ceil(800 × model.credit_multiplier)` 独立计算，PPTX/XLSX 组合再求和；model multiplier、各子输出费用和模板版本进入不可变 Preflight snapshot。普通模式需要 confirm 接受当前预计积分，一键模式必须在同一请求提交匹配的预计积分。重复确认同一 Revision 与同一费用返回已锁定 snapshot；`brief_revision_stale`、`preflight_blocked`、`estimated_credits_changed`、Skill/template/model incompatibility 均不能进入 `queued`。

T3-001 已实现 `POST /generations`、task GET/cancel/retry 和 Credits 查询。Create 只接受 owner 的最新已确认 Brief，并在同一事务冻结 Brief/input/template/Skill/model 与预计积分 snapshot，创建任务/步骤、预留流水和首个 Outbox；同 user/idempotency key 返回既有任务。执行前再次验证 Model/Provider/Credential identity、能力、费用和子输出总和，配置漂移 fail closed。Task/credits 响应使用 `Cache-Control: private, no-store`；稳定错误码包括 `brief_not_confirmed`、`brief_revision_stale`、`generation_preflight_stale`、`insufficient_credits`、`task_not_found`、`task_retry_not_allowed` 与 `idempotency_key_invalid`。

T3-001 Worker 以数据库 task/step checkpoint 为权威。重复 queue delivery 只有一个 claim；确定性暂时失败有限重试，安全 stale checkpoint 可恢复，已开始 Provider 调用但结果未知时进入 `provider_uncertain` 并保留 reserve。Python consumer 只定义版本化 queue contract 和注入式 executor；真正 PPT/XLSX renderer 由后续任务交付。

T3-002 已实现内部 `POST /v1/render` PPT Renderer contract，不作为浏览器或公网 API 暴露。请求为 `ppt-renderer.request.v1`，只携带 UUID request ID 和经双端验证的 `presentation-plan.v1`；响应为 `ppt-renderer.response.v1`，只返回受控相对 output key、文件/Plan SHA-256、byte size、页数和固定模板/Renderer 版本。Python 适配层再次验证全部字段和共享 volume 中的文件内容，再以不可变 `file_assets` 版本关联 generation task；客户端不能提供输出路径或覆盖既有完成资产。

T3-003 已实现内部 `POST /v1/presentation/convert` LibreOffice sidecar contract，仅接受 UUID identity、source variant、SHA-256 与 byte size，不接受客户端路径。返回的 PDF/逐页 PNG key、hash、size、页码和尺寸会被 Backend 重新验证并固化到 `presentation-quality-report.v1`。生成 PPTX 只有 `passed`/`passed_with_warnings` 且 validated artifact 完整性复验通过时可下载；未检查返回 `asset_quality_pending`，阻断返回 `asset_quality_blocked`，artifact 漂移返回 `asset_quality_integrity_failed`。

T3-004 已实现 strict `workbook-plan.v1`，只接受两套系统 Excel 模板、typed
data/summary Sheet、结构化同比/环比/排名/汇总/chart/format/validation/print contract；
不接受自由公式、外部连接、客户端输出路径、Pivot、Power Query、DAX 或 VBA。Renderer
结果固定返回原件 SHA-256/size、Plan SHA-256、Schema/Renderer/template version、
Sheet 数和实际生成 cell 数。

T3-004 同时在既有 private LibreOffice sidecar 增加内部
`POST /v1/spreadsheet/recalculate`。请求 `libreoffice-spreadsheet-request.v1` 只包含
request/user/asset UUID、原件 SHA-256/size 与 Plan/Renderer/template version；sidecar
从固定 owner/asset key 读取原件，在 shared-work 写独立 validation copy 和
`workbook-validation-report.v1`。响应 `libreoffice-spreadsheet-response.v1` 只返回固定
相对 key、hash/size、LibreOffice version 与 formula/difference 数；Backend 再复验实际
artifact、完整 trace 和 report，不信任 sidecar JSON，也不把该 internal endpoint 暴露给
Browser。

T3-005 为 XLSX 固化 `workbook-quality-report.v1`：报告关联原始 asset/hash、
Workbook Plan、Renderer/template、LibreOffice validation copy/report，扫描实际公式错误
类型并精确比较原始数据、确定性公式 cache、summary 与 chart category/value range；未解决
的 Sheet/字段/单位冲突一律阻断。报告和 finding 不保存公式正文、storage key、本地路径或
用户材料。`passed`/`passed_with_warnings` 只有在 validated artifact hash/size 重验通过后
可下载，`blocked` 返回稳定质量状态且不暴露下载 key。

组合任务的 PPTX/XLSX step 分别保存 output asset、asset version、quality status、
download boundary 和 estimated credits。`GET /generations/{task_id}/outputs` 逐项复验
owner、generated task、file category、asset version 与质量 artifact；两成聚合为
`succeeded`，一成一败为 `partial_success`，只 finalize 成功额度并 release 失败额度。
checkpoint/ledger 唯一约束保证重复 quality 或 settlement event 不会重复改变余额。

## Credits

| Method | Path | 说明 |
|---|---|---|
| GET | `/credits/balance` | 事务内维护的余额缓存 |
| GET | `/credits/ledger` | 当前用户只追加的积分流水 |

`credit_ledger` 只追加，`users.credit_balance` 仅为同事务维护的余额缓存。创建任务写负数 `generation_reserve`；全部成功写幂等 finalize marker，全部失败或可取消任务写正数 release，部分成功 finalize 成功子输出并 release 未使用部分；重复消息或 retry 不能重复结算。`provider_uncertain` 保留预留直到后续受审计决策。

## Admin

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/users` | 用户查询与状态查看 |
| POST | `/admin/users/{user_id}/reset-password` | 重新认证、记录原因、强制用户改密 |
| POST | `/admin/users/{user_id}/status` | 重新认证、记录原因后启停用户并撤销受影响 Session |
| POST | `/admin/invite-codes` | 创建邀请码与赠送规则 |
| GET | `/admin/invite-codes` | 查询邀请码状态和使用情况 |
| POST | `/admin/providers` | 创建 Provider 配置 |
| GET | `/admin/providers` | 管理员查询 Provider 配置，不含 Secret |
| PATCH | `/admin/providers/{provider_id}` | 修改非 Secret 配置和状态 |
| POST | `/admin/credentials` | 每条记录写入一个加密 API Key |
| GET | `/admin/credentials` | 管理员查询固定掩码、限流、状态和最近测试结果；不解密 Key |
| PATCH | `/admin/credentials/{credential_id}` | 只修改名称、状态、RPM/TPM/最大并发；轮换 Key 必须新建记录 |
| POST | `/admin/credentials/{credential_id}/test` | 测试认证和能力，结果脱敏 |
| POST | `/admin/credentials/{credential_id}/reveal` | 重新认证后临时 reveal，禁止缓存并审计 |
| POST | `/admin/models` | 创建 Provider 模型 |
| GET | `/admin/models` | 管理员查询全部模型配置 |
| PATCH | `/admin/models/{model_id}` | 能力、可见性、倍率和状态 |
| GET | `/admin/tasks` | 查看持久任务和异常状态 |
| POST | `/admin/tasks/{task_id}/retry` | 对可安全重试任务执行受审计重试 |
| GET | `/admin/assets` | 查询全部用户资产的安全摘要，不返回 storage key 或路径 |
| POST | `/admin/assets/{asset_id}/preview` | JSON body 重新认证并记录原因后预览任意资产 |
| POST | `/admin/assets/{asset_id}/download` | JSON body 重新认证并记录原因后下载任意资产 |
| DELETE | `/admin/assets/{asset_id}` | 重新认证并记录原因后删除任意资产 |
| POST | `/admin/credits/adjustments` | 只追加管理员积分调整流水 |
| GET | `/admin/audit-logs` | 只读查询 audit log，无编辑或删除接口 |

`T1-003` 已实现 `/admin/invite-codes` 的创建与查询：创建响应只返回一次完整 code 且禁止缓存，列表只返回 prefix、次数、有效期、状态和赠送积分。管理员密码 reset 的 service-level 撤销与 `must_change_password` 行为已实现；需要重新认证、reason 和 `audit_logs` 的 HTTP 闭环仍由 `T4-002` 交付，不在 T1-003 暴露不完整的敏感端点。

`T1-004` 已实现 Provider/Credential/Model Registry。Agnes 配置在写入前验证 HTTPS、保守
`256K` Context、正 timeout，以及可选的布尔 capability
`native_response_format`（默认 `false`）；只有上游明确支持时才发送 native
`response_format`。该 capability 只改变传输字段，Structured Brief 仍由应用层 strict
Schema、一次 repair 和 Evidence 引用校验约束。Credential 创建响应只返回掩码并使用
`Cache-Control: no-store`。Reveal 要求管理员 Session、当前密码和 reason，成功/失败均审计，
响应禁止缓存。Credential test 要求 reason、受 Redis 限速，`401/403` 会暂停 Credential，
timeout 返回不确定状态而不自动重试。用户 `/models` 只返回 Provider、Credential、Model
都为 active 且 `user_visible=true` 的记录。

`T1-005` 已实现用户 Projects/Assets HTTP contract，并为后续管理员全局资产读取保留独立
admin role + reason + audit service 边界；该历史阶段没有暴露缺少重新认证的半成品端点。

`T4-002` 已完成上述用户、资产、积分与 audit HTTP 闭环。敏感 JSON body 统一使用
`current_password + reason`；原因缺失和重新认证失败进入 audit 后才返回稳定错误。
preview/download 使用 `POST`，避免密码和原因进入 URL/query；响应为
`private, no-store`。资产只接受 UUID，服务端从 `file_assets` 解析 owner 和既有
deterministic key。积分调整要求 `Idempotency-Key`，重放返回同一 ledger，不重复改变余额。
Audit 查询只读且返回脱敏 IP/User-Agent 摘要与白名单 context；没有编辑或删除端点。

## 后续 contract gate

- `T1-003` 已实现并测试 Auth/Invite；`T1-004` 已实现 Admin Provider/Credential/Model；`T1-005` 已实现 Projects/Assets。
- `T2-001` 已实现病毒扫描、深度类型/容量检查与安全解析；`T2-003` 已实现术语库、不可变 snapshot、确定性标准化与来源冲突项；`T2-004`/`T2-005` 已实现 Brief/Preflight。
- `T3-001` 已实现 Generation/Credits/Outbox 持久编排；`T3-002` 已交付真实 PPT Renderer 与不可变输出适配层；`T3-003` 已交付 PPT QA、一次确定性修复和下载门禁；`T3-004` 已交付确定性 Excel Renderer、两套模板、不可变原件和 LibreOffice validation-copy contract；`T3-005` 已完成 Excel QA、双输出状态、下载完整性与部分成功结算，`T4-002` 完成管理端资产和 audit 闭环。
- 任何端点增删或 envelope/state 变化必须先更新本文件和 `docs/PROGRESS.md`。
