# Office AI Alpha API 基线

- 前缀：`/api/v1`
- 数据格式：JSON；文件上传与下载除外
- 身份：短期 Session Access Token + 可撤销 Refresh Token
- 状态：`T1-005` 已实现 Auth、Admin Invite、Provider/Credential/Model Registry、Projects 与 Assets；其余接口按后续任务实现

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

T1-005 上传支持 XLSX、XLSM、CSV、DOCX、PDF、PNG、JPG、JPEG、WEBP、TXT、MD 的扩展名/MIME 初检；PDF、Office ZIP 与图片同时检查最小 magic header。单文件默认上限 50 MB，图片默认上限 20 MB；同一用户重放相同 `Idempotency-Key` 时，`quarantined` 及后续已持久化状态返回既有资产且不重复读取或写入文件，`uploaded`/`deleting` 则在读取 body 前稳定返回 `409 asset_upload_in_progress`。单次 API 只接受一个 `file` 和至多一个 `project_id`，额外文件或未知 multipart 字段以 `upload_form_invalid` 拒绝；必须提供唯一、合法且与实际 bytes 一致的 `Content-Length`，不能使用 `Transfer-Encoding`。upload ASGI middleware 在读取 body 前验证 Bearer Session 和 replay policy；新请求先写入 middleware 自己的 1 MiB memory-threshold 受控 preflight spool，以 `max_file_bytes + 64 KiB` 验证完整 body 后才 replay 给 Starlette multipart parser。拒绝路径不会创建 parser file spool，临时 preflight spool 始终在 `finally` 关闭。20 文件/200 MB 是后续 generation input selection 与 T2-001 安全解析 gate，不以一次 multipart batch 实现。

资产响应不返回 `storage_key`、`parsed_storage_key` 或磁盘路径。T2-001 在原响应上增加可空 `parser_name`/`parser_version`、`processing_warnings`、`processing_error_code` 与脱敏 `processing_error_message`；不返回结构化内容本体。preview/download 先做 owner scope 鉴权，响应包含 `Cache-Control: private, no-store` 与 `X-Content-Type-Options: nosniff`，preview 额外使用 `Content-Security-Policy: sandbox`。已完成的同 owner/idempotency replay 在 preflight spool 与 `request.form()` 前返回，HTTP body receive、multipart parser/spool 与 service upload 均不进入；incomplete replay 在相同位置返回 409，同样不消费 body。数据库 unique race fallback 使用同一 policy，不会把并发 `uploaded`/`deleting` checkpoint 当成 201 成功；signature/stream 失败且 cleanup 成功删除 checkpoint 后，later retry 可重新上传。新上传先提交 `uploaded` checkpoint，再写入文件并最终更新为 `quarantined`；若最终事务异常或 cancellation，文件仍由该 checkpoint 定位，cleanup 失败则保留 `deleting` 供恢复。cleanup/reconciliation failure 不替换 `file_signature_invalid`、`file_too_large`、unexpected stream error 或 cancellation 主因；direct/generic/cancellation 路径均写脱敏 `asset_recovery_failed` 日志与 checkpoint 状态。项目 PATCH 不接受显式 `null`；项目删除仅允许空项目。资产删除先检查活动父版本引用；物理删除失败保留 `deleting` 状态并明确返回失败，不伪报 `deleted`。T2-001 可持久化处理错误码以完整 contract 表为准；上传/资产稳定错误码继续包括 `project_not_found`、`project_not_empty`、`project_update_invalid`、`project_id_invalid`、`file_required`、`upload_form_invalid`、`asset_not_found`、`asset_in_use`、`asset_delete_failed`、`asset_upload_in_progress`、`upload_body_invalid`、`upload_body_too_large`、`quarantine_cleanup_failed`、`file_type_unsupported`、`file_mime_mismatch`、`file_signature_invalid`、`file_too_large` 与 `idempotency_key_invalid`。

### T2-001 可持久化处理错误码

| processing_error_code |
|---|
| `archive_bomb_detected` |
| `archive_member_invalid` |
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
| GET | `/templates` | Alpha 系统认证模板 |
| GET | `/term-libraries` | 当前用户术语库 |
| POST | `/term-libraries` | 创建术语库 |
| POST | `/term-libraries/{library_id}/items` | 增加标准术语、别名、单位与口径 |

## Brief 与 Generation

| Method | Path | 说明 |
|---|---|---|
| POST | `/briefs/generate` | 从版本化材料生成 evidence-grounded Structured Brief |
| PATCH | `/briefs/{brief_id}` | 新建不可变 revision，不原地覆盖历史版本 |
| POST | `/briefs/{brief_id}/confirm` | 用户确认当前 revision |
| POST | `/generations/preflight` | 返回冲突、阻断项和不可提高的预计积分 |
| POST | `/generations` | 幂等创建组合任务并预留积分 |
| GET | `/generations/{task_id}` | 持久任务、步骤、子输出与质量状态 |
| POST | `/generations/{task_id}/cancel` | 按状态机取消并释放可释放预留 |
| POST | `/generations/{task_id}/retry` | 仅对允许重试的确定失败执行；不重复扣费 |
| GET | `/generations/{task_id}/outputs` | 当前用户可下载的不可变输出版本 |

生成状态为：`draft`、`preflight`、`needs_resolution`、`queued`、`running`、`succeeded`、`partial_success`、`provider_uncertain`、`failed`、`cancelled`。

## Credits

| Method | Path | 说明 |
|---|---|---|
| GET | `/credits/balance` | 事务内维护的余额缓存 |
| GET | `/credits/ledger` | 当前用户只追加的积分流水 |

失败任务不结算；组合任务只结算成功子输出；`provider_uncertain` 保留预留直到人工决策。

## Admin

| Method | Path | 说明 |
|---|---|---|
| GET | `/admin/users` | 用户查询与状态查看 |
| POST | `/admin/users/{user_id}/reset-password` | 重新认证、记录原因、强制用户改密 |
| POST | `/admin/users/{user_id}/status` | 启停用户，写 audit log |
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
| GET | `/admin/assets/{asset_id}/preview` | 重新认证并记录原因后预览任意资产 |
| GET | `/admin/assets/{asset_id}/download` | 重新认证并记录原因后下载任意资产 |
| DELETE | `/admin/assets/{asset_id}` | 重新认证并记录原因后删除任意资产 |
| POST | `/admin/credits/adjustments` | 只追加管理员积分调整流水 |
| GET | `/admin/audit-logs` | 只读查询 audit log，无编辑或删除接口 |

`T1-003` 已实现 `/admin/invite-codes` 的创建与查询：创建响应只返回一次完整 code 且禁止缓存，列表只返回 prefix、次数、有效期、状态和赠送积分。管理员密码 reset 的 service-level 撤销与 `must_change_password` 行为已实现；需要重新认证、reason 和 `audit_logs` 的 HTTP 闭环仍由 `T4-002` 交付，不在 T1-003 暴露不完整的敏感端点。

`T1-004` 已实现 Provider/Credential/Model Registry。Agnes 配置在写入前验证 HTTPS、保守 `256K` Context 和正 timeout；Credential 创建响应只返回掩码并使用 `Cache-Control: no-store`。Reveal 要求管理员 Session、当前密码和 reason，成功/失败均审计，响应禁止缓存。Credential test 要求 reason、受 Redis 限速，`401/403` 会暂停 Credential，timeout 返回不确定状态而不自动重试。用户 `/models` 只返回 Provider、Credential、Model 都为 active 且 `user_visible=true` 的记录。

`T1-005` 已实现用户 Projects/Assets HTTP contract。管理员全局资产读取当前只在 service-level 提供独立 admin role + reason + audit 边界并覆盖成功/失败审计；不暴露缺少近期重新认证的半成品 Admin HTTP 端点，完整 preview/download/delete re-auth 闭环仍由 `T4-002` 交付。

## 后续 contract gate

- `T1-003` 已实现并测试 Auth/Invite；`T1-004` 已实现 Admin Provider/Credential/Model；`T1-005` 已实现 Projects/Assets。
- `T2-001` 实现病毒扫描、深度类型/容量检查与安全解析；`T2-003` 实现术语；`T2-004`/`T2-005` 实现 Brief/Preflight。
- `T3-001` 实现 Generation/Credits；`T4-002` 完成管理端资产和 audit 闭环。
- 任何端点增删或 envelope/state 变化必须先更新本文件和 `docs/PROGRESS.md`。
