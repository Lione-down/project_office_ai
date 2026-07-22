# Office AI Alpha 数据模型基线

- 数据库：MySQL 8.0
- 表数量：固定 21 张
- 状态：逻辑契约；`T1-005` migration `20260722_0005` 已 additive 建立 `projects`、`file_assets` 及中文注释，当前共实现 10/21 张表

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

6. `templates`
   - 类型、来源/预览资产、分类、样式关键字、设计配置、版本、状态、排序、使用次数。
   - 字段兼容未来用户模板，但 Alpha 只发布系统模板。

7. `term_libraries`
   - 用户、名称、说明、状态、版本。

8. `term_items`
   - 术语库、标准术语、别名、单位、定义、口径说明、优先级。

9. `briefs`
   - `brief_group_id`、revision、来源快照、内容 JSON、状态、确认时间；每个 revision 不可变。

10. `skills`
    - 每版本一行：code、SemVer、kind、展示信息、input/output schema、workflow、能力要求、状态、checksum。
    - `kind` 仅 `user_workflow` 或 `internal_step`。

11. `generation_tasks`
    - 用户、项目、Brief、模型、idempotency key、组合 group、父任务、状态、进度、Skill/模型快照、预计/结算积分、错误类别、超时和时间戳。

12. `generation_task_steps`
    - 任务、阶段、尝试次数、状态、checkpoint、开始/结束、错误分类、脱敏错误。

13. `generation_task_inputs`
    - 任务与资产、模板、术语库的关系及版本快照。

14. `provider_calls`
    - 任务、步骤、Provider、模型、Credential ID、Provider Request ID、状态、token usage、耗时、费用和错误分类。
    - 不保存明文 API Key 或完整用户文件内容。

15. `outbox_events`
    - 事件类型、aggregate ID、payload、状态、重试次数、下一投递时间；保证 DB commit 后可恢复投递。

16. `credit_ledger`
    - 用户、任务、流水类型、整数数量、余额快照、关联流水、idempotency key、说明、时间。
    - 只追加；它是账务真相，`users.credit_balance` 只是缓存。

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
| `generation_tasks` | `(user_id, idempotency_key)` | 重复提交只创建一个任务 |
| `credit_ledger` | `(user_id, idempotency_key, entry_type)` | 防止重复预留/结算/释放 |
| `file_assets` | `(storage_provider, storage_key)` | 存储定位唯一 |
| `file_assets` | `(user_id, idempotency_key)` | 同一用户上传重放只创建一个资产 |
| `ai_models` | `(provider_id, model_code, credential_id)` | 模型与独立 Credential 绑定唯一 |
| `provider_credentials` | `(provider_id, key_fingerprint)` | 防止同 Provider 重复 Key |

## 关系与事务边界

- 注册事务：校验并锁定 `invite_codes`，创建 `users`，写入 `credit_ledger`，同步余额缓存。
- T1-005 上传边界：先提交带不可变 quarantine key、`uploaded` 状态和幂等键的 `file_assets` checkpoint，再流式写文件；signature/project cleanup 成功时删除 checkpoint，cleanup 失败保留 `deleting`，最终 metadata commit 异常或 cancellation 时保留 `uploaded` 与文件定位，避免无数据库记录的 orphan file。写库幂等冲突发生在文件 I/O 前。`outbox_events` 尚未建立，T3-001 接入 Outbox 后再把后续处理投递纳入数据库事务边界。
- 生成事务：创建 `generation_tasks`、inputs、reserve ledger 与 Outbox；同一 idempotency key 重放返回既有结果。
- 结算事务：按子输出结果写 finalize/release，不允许同一输出重复结算。
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
- 注册使用 `SELECT ... FOR UPDATE` 锁定邀请码，并在同一事务中增加次数、创建用户、写 `registration_grant` 和同步 `users.credit_balance`；任一写入失败整体回滚。
- 后续每个模型任务通过 additive migration 演进；禁止删除或改写历史 migration。
- Alpha 封版必须从空数据库完整升级，并验证 21 张表、唯一约束和外键。
