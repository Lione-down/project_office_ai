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
| GET | `/templates` | Alpha 系统认证模板 |
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

术语条目支持标准术语、最多 100 个 NFKC 去重别名、canonical unit code、定义、指标口径和 `-1000..1000` 优先级。项目规则只覆盖同一用户同一项目的全局匹配；同层级、同优先级映射到不同标准术语时返回 `term_ambiguous` unresolved。`terminology-normalization.v1` 确定性处理绝对日期、数字、百分比、CNY/USD、万/亿倍率和销售数量单位；缺少年份、未知单位、显式单位冲突或多来源标准化值不一致不会被猜测或静默合并。派生 `NormalizedEvidenceItem` 保留 source fact 的 asset/version/location/raw/provenance，并附加规则版本与术语库 version snapshot；它不改写已落盘的 `evidence-manifest.v1`。

T2-004 已实现 `/skills`、`/skills/{skill_code}` 与 `/briefs/generate`。Skills API 要求有效 Session，只返回 migration 固化且 row 全合同/checksum 与 runtime registry 一致的两个 published `1.0.0` Skill。Brief generate request 只接受 `project_id`、1–20 个 `asset_ids`、显式 `term_library_versions`、1–2 个固定 `skill_codes`、一个 published `model_id`、goal/audience 与 must include/exclude；不接受客户端 evidence 正文、本地路径、Provider Key 或任意 Skill。响应为不可变 revision 1 `draft`，包含严格 17 字段 Structured Brief、group/revision ID 与内容 checksum，并返回 `Cache-Control: private, no-store`。

T2-004 生成前校验 owner project/assets、`ready` Manifest key/SHA/asset version、术语库 owner/project/version、Skill 全合同、模型能力及 Provider/Credential 状态。Provider 只收到 bounded evidence 与选定术语规则，所有文档内容作为 untrusted user data；模型返回必须保持 goal/audience/asset/term/Skill/model/include/exclude/output-kind authoritative snapshot，引用已知 evidence，`file/calculation` fact 和 `agnes_inference` 均必须有 evidence。JSON/Schema/snapshot/evidence 失败只修复一次；第二次失败返回对应 `brief_schema_invalid`、`brief_snapshot_mismatch` 或 `brief_evidence_invalid`，不保存 Brief。Context 不足在调用前返回 `context_budget_exceeded`；timeout 返回 `provider_uncertain` 且不自动重试，`401/403` 暂停所选 Credential，不静默切换 Provider。

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

T2-005 已实现 owner-scoped `GET /briefs/{brief_id}`、`PATCH /briefs/{brief_id}`、`POST /briefs/{brief_id}/confirm` 与 `POST /generations/preflight`。GET 可读取 owner 的历史 Revision；PATCH 只允许基于最新 Revision 追加用户可编辑字段、系统模板版本和匹配当前 unresolved item 的显式 resolution，不允许客户端替换来源、术语、Skill、模型或 Evidence 引用。Preflight 每次复验资产版本/Manifest、Evidence blocker、Brief unresolved item、Skill 全合同、系统模板以及当前 Agnes Provider/Credential/模型能力，返回 `auto_merge`、`needs_confirmation`、`blocking`、`incompatible` 四类结果。

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
