# Office AI Alpha API 基线

- 前缀：`/api/v1`
- 数据格式：JSON；文件上传与下载除外
- 身份：短期 Session Access Token + 可撤销 Refresh Token
- 状态：`T1-003` 已实现 Auth 与 Admin Invite；其余接口按后续任务实现

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
| POST | `/assets/uploads` | 上传到 quarantine，校验数量与体积后异步处理 |
| GET | `/assets` | 当前用户资产列表 |
| GET | `/assets/{asset_id}` | 资产元数据与处理状态 |
| GET | `/assets/{asset_id}/preview` | 鉴权预览，不暴露 storage key |
| GET | `/assets/{asset_id}/download` | 鉴权下载 |
| DELETE | `/assets/{asset_id}` | `deleting -> deleted`，活动存储立即清理 |

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
| PATCH | `/admin/providers/{provider_id}` | 修改非 Secret 配置和状态 |
| POST | `/admin/credentials` | 每条记录写入一个加密 API Key |
| POST | `/admin/credentials/{credential_id}/test` | 测试认证和能力，结果脱敏 |
| POST | `/admin/credentials/{credential_id}/reveal` | 重新认证后临时 reveal，禁止缓存并审计 |
| POST | `/admin/models` | 创建 Provider 模型 |
| PATCH | `/admin/models/{model_id}` | 能力、可见性、倍率和状态 |
| GET | `/admin/tasks` | 查看持久任务和异常状态 |
| POST | `/admin/tasks/{task_id}/retry` | 对可安全重试任务执行受审计重试 |
| GET | `/admin/assets/{asset_id}/preview` | 重新认证并记录原因后预览任意资产 |
| GET | `/admin/assets/{asset_id}/download` | 重新认证并记录原因后下载任意资产 |
| DELETE | `/admin/assets/{asset_id}` | 重新认证并记录原因后删除任意资产 |
| POST | `/admin/credits/adjustments` | 只追加管理员积分调整流水 |
| GET | `/admin/audit-logs` | 只读查询 audit log，无编辑或删除接口 |

`T1-003` 已实现 `/admin/invite-codes` 的创建与查询：创建响应只返回一次完整 code 且禁止缓存，列表只返回 prefix、次数、有效期、状态和赠送积分。管理员密码 reset 的 service-level 撤销与 `must_change_password` 行为已实现；需要重新认证、reason 和 `audit_logs` 的 HTTP 闭环仍由 `T4-002` 交付，不在 T1-003 暴露不完整的敏感端点。

## 后续 contract gate

- `T1-003` 已实现并测试 Auth/Invite；`T1-004` 实现 Admin Provider/Credential/Model。
- `T1-005` 实现 Projects/Assets；`T2-003` 实现术语；`T2-004`/`T2-005` 实现 Brief/Preflight。
- `T3-001` 实现 Generation/Credits；`T4-002` 完成管理端资产和 audit 闭环。
- 任何端点增删或 envelope/state 变化必须先更新本文件和 `docs/PROGRESS.md`。
