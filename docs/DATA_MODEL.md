# Office AI Alpha 数据模型基线

- 数据库：MySQL 8.0
- 表数量：固定 21 张
- 状态：逻辑契约；`T3-001` migration `20260723_0011` 已 additive 建立任务、步骤、输入与 Outbox，并补齐账务/Provider call 关系，当前共实现 19/21 张表

## 全局约定

- 应用生成 UUIDv7，MySQL 存储为 `BINARY(16)`。
- 时间统一为 UTC `DATETIME(6)`；金额、次数和积分使用整数。
- 核心关系使用外键，任务请求、能力和历史快照可以使用 JSON。
- 用户可见资源使用软删除；实际文件异步清理，活动存储立即删除，备份残留最长 30 天。
- 历史修订、输出版本、`credit_ledger` 和 `audit_logs` 不原地覆盖。
- 文件二进制、完整 Prompt、明文 Secret 和完整用户内容不进入数据库。

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
   - 类型、来源/预览资产、分类、样式关键字、设计配置、版本、状态、排序、使用次数。
   - 字段兼容未来用户模板，但 Alpha 只发布系统模板。

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
- T2-002 证据边界：解析结果落盘后先在同一资产行提交 deterministic Manifest key 和 `building`，再生成/校验/原子写入 Manifest；最终条件更新一次性写入 `ready` 和摘要 metadata。暂时性 OCR 失败先精确清理本轮解析/Manifest 输出，再以 exponential backoff 回到 `quarantined`；第 3 次失败稳定拒绝，不产生伪造证据或无限重试。用户删除资产时必须按记录的 exact keys 幂等清理原文件、解析结果与 Manifest，任一清理失败都保留 `deleting`，不得伪装成 `deleted`。
- T2-003 术语边界：owner-scoped mutation 以 locking read 获取最新 active 库版本，同一事务插入下一库版本与完整条目 snapshot；历史 Brief/任务只引用稳定 `library_id + version`，回滚规则只选择旧版本，不改写 Manifest、Brief 或历史 snapshot。
- T2-004 Brief 边界：先 owner-scope 校验项目、ready 资产、Manifest integrity、显式术语库 version、Skill row 全合同、发布模型/Provider/Credential；只把 bounded evidence 与选定术语规则作为 untrusted user context 发送给唯一选定 Agnes。每次调用先写脱敏 `provider_calls`，合法响应再以新 `brief_group_id + revision=1` 保存不可变 Brief 并回链 calls；Schema/evidence/snapshot 失败只修复一次，仍失败不创建 Brief 或积分记录。timeout 只写 `provider_uncertain` call，不自动重试或切换 Provider。
- T2-005 Preflight 边界：GET 可 owner-scoped 读取历史 Revision；PATCH 同时锁定目标行和 group 最新行，只有目标仍为最新且 `expected_revision` 匹配时才追加新 Revision。Preflight/confirm 锁定当前行并复验最新 Revision、资产版本/Manifest、Evidence blocker、Skill/template/model/Provider/Credential；状态和不可变 snapshot 在同一事务提交。费用变化或新增 blocker 先持久化最新 Preflight snapshot，再返回稳定 409；确认只把 Brief 置为 generation-ready `queued` 并锁定 multiplier/子输出费用/总预计积分，不创建任务、ledger 或 Outbox。
- T3-001 生成事务：锁定 owner 的最新 confirmed Brief、Model/Credential/Provider 与用户余额，复验 identity/capability/pricing/子输出总和，在同一事务创建 task、steps、inputs、负数 reserve ledger 与首个 Outbox；同一 user/idempotency key 重放返回既有结果，余额不足或 Outbox 写入失败整体回滚。
- T3-001 执行/恢复边界：MySQL task/step checkpoint 为权威，Redis 只承载可丢失 queue/limit。published-before-marked 允许重复投递但数据库 claim 去重；safe stale step 复位后重新入队，已进入 Provider 且结果未知的 checkpoint 转 `provider_uncertain`。
- T3-001 结算事务：全成功写幂等 finalize marker；全失败/可取消任务写 release；partial success 按成功子输出费用结算并 release 余量。所有流水只追加，`provider_uncertain` 保留 reserve。
- Credential 操作：只通过 `credential_id` 关联；Reveal、测试和轮换写 `audit_logs`，任何日志不得含明文 Key。
- 管理员资产操作：权限判断、业务结果和 audit 写入必须具备可追溯的一致性边界。

## 状态字段

- 资产：`uploaded`、`quarantined`、`scanning`、`parsing`、`ready`、`rejected`、`deleting`、`deleted`。
- 任务：`draft`、`preflight`、`needs_resolution`、`queued`、`running`、`succeeded`、`partial_success`、`provider_uncertain`、`failed`、`cancelled`。
- 质量：`passed`、`passed_with_warnings`、`blocked`。
- 积分流水：`registration_grant`、`admin_grant`、`generation_reserve`、`generation_finalize`、`generation_release`、`refund`。

## Migration gate

- `T1-002` 已创建 `20260722_0001` 初始空 migration 与基础连接；应用启动不自动建表。
- `T1-003` 已创建 `20260722_0002`，建立 `users`、`user_sessions`、`invite_codes`、`credit_ledger`；UUID 为 `BINARY(16)`，时间为 MySQL `DATETIME(6)`。
- `T1-003` runtime 补验新增 `20260722_0003`，为上述 4 张表及全部 41 个字段写入非空中文 COMMENT；2026-07-22 已在本机 MySQL 8.0.43 空库真实升级并通过 `information_schema` 与 `alembic check` 核对。
- `T1-004` 新增 `20260722_0004`，建立 `ai_providers`、`provider_credentials`、`ai_models`、`audit_logs`；2026-07-22 已在本机 MySQL 从 `0003` 真实升级，4/4 table comments、52/52 column comments、两项关键唯一约束通过 `information_schema` 与事务内 rollback probe 核对，`alembic check` 无 drift。
- `T1-005` 新增 `20260722_0005`，建立 `projects`、`file_assets`，包含 owner/project/parent 外键、active default generated key、storage location 与 user idempotency 唯一约束及中文注释；SQLite 空库完整升级、MySQL dialect offline SQL 和单一 Head `20260722_0005` 已验证。当前会话未获授权读取本地 `.env`，因此未把 offline 结果冒充真实 MySQL runtime upgrade。
- `T2-001` 新增 `20260723_0006`，只向 `file_assets` additive 增加 8 个安全处理 metadata 字段；SQLite 空库完整升级、MySQL dialect offline SQL、中文 COMMENT 与唯一 Head `20260723_0006` 已验证。当前会话未读取本地 `.env`，未把 offline 结果冒充真实 MySQL runtime upgrade。
- `T2-002` 新增 `20260723_0007`，只向 `file_assets` additive 增加 9 个 Evidence Manifest 与 OCR retry metadata 字段；真实 MySQL runtime 结果以本任务执行记录为准。
- `T2-003` 新增 `20260723_0008`，建立不可变 `term_libraries` 与 `term_items` snapshot 表、owner/project/previous-version 外键、3 项版本唯一约束和中文 COMMENT。SQLite 空库完整升级与单一 Head、MySQL dialect offline DDL 已验证；本任务未读取 `.env`，未运行真实 MySQL `0008` upgrade。
- `T2-004` 新增 `20260723_0009`，建立 `skills`、`briefs`、`provider_calls` 并以 migration 内冻结 payload 固化两个 Alpha Skill；SQLite 空库完整升级、单一 Head 与 MySQL dialect offline DDL 已验证，真实 Agnes Contract 未 opt-in。
- `T2-005` 新增 `20260723_0010`，只向 `briefs` additive 增加可空 `preflight_snapshot JSON` 与 `estimated_credits INTEGER`；SQLite 空库完整升级测试、唯一 Head `20260723_0010` 与 MySQL dialect offline DDL 已通过。本任务未读取 `.env`，未运行真实 MySQL `0010` upgrade。
- `T3-001` 新增 `20260723_0011`，建立 `generation_tasks`、`generation_task_steps`、`generation_task_inputs`、`outbox_events`，向 `credit_ledger` 增加 task 外键，并向 `provider_calls` additive 增加 task/step scope 与唯一约束。SQLite 空库完整升级、唯一 Head、MySQL dialect offline upgrade/downgrade 已通过；未读取 `.env`，未运行真实 MySQL/Redis runtime。
- 注册使用 `SELECT ... FOR UPDATE` 锁定邀请码，并在同一事务中增加次数、创建用户、写 `registration_grant` 和同步 `users.credit_balance`；任一写入失败整体回滚。
- 后续每个模型任务通过 additive migration 演进；禁止删除或改写历史 migration。
- Alpha 封版必须从空数据库完整升级，并验证 21 张表、唯一约束和外键。
