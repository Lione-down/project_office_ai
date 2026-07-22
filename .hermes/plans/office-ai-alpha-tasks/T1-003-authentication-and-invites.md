# T1-003 用户、Session 与邀请码

- 状态：`DONE`
- Depends on：`T1-002`
- 来源：总计划第 2、3、6、7、12、13 节与 Day 3
- 建议 commit：`feat(auth): add invite based phone authentication`

## 目标

交付 `+86` 手机号、邀请码、密码与可撤销 Session 驱动的认证闭环，并保证注册赠送积分的事务一致性。

## 交付范围

- `users`、`user_sessions`、`invite_codes`、注册赠送所需 `credit_ledger` 最小模型与迁移。
- 注册、登录、刷新、退出、当前用户、修改密码 API。
- Argon2id 密码 Hash、Refresh Token Hash、登录/注册/邀请码限速和强制改密标记。
- 管理员 Bootstrap 命令仅从环境变量读取初始信息，不接受源码默认密码。

## 实施步骤

1. 先写手机号唯一、邀请码无效/过期/耗尽、密码 Hash、限速和事务回滚测试。
2. 在单一事务中消费邀请码、创建用户、写入注册赠送流水并更新余额缓存。
3. 实现 Access/Refresh Session 生命周期、撤销和密码修改后的 Session 策略。
4. 实现管理员 Bootstrap 幂等行为与敏感日志脱敏。
5. 更新 API、数据模型、环境和安全文档。

## 验收标准

- 有效邀请码和未注册手机号可注册；重复手机号与无效邀请码稳定失败。
- 任一步骤失败时邀请码次数、用户、流水和余额全部回滚。
- Refresh Token 仅以 Hash 保存；密码和 Token 不出现在日志或响应缓存中。
- 登录失败限速生效，管理员重置后的用户被标记必须修改密码。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/auth -q
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend pytest -q
```

## 非范围与回滚

- 不实现短信验证码、手机号自助找回、微信、Workspace 或团队体系。
- 回滚 API 与迁移时保留向下兼容；已产生的积分流水不得原地修改，只能用反向流水更正。

## 2026-07-22 本机 Runtime 补验

- 用户明确授权本次执行只在进程内读取项目 `.env`，使用其中 MySQL 连接信息创建目标 database 并执行 migration；禁止回显、记录或提交 Secret。
- 保持 T1-004 不变。本补验只处理 `OFFICE_AI_DB_*` 本地变量兼容、认证 4 张表的中文 table/column comments、MySQL 空库升级和 Redis authenticated runtime verification。
- 不修改已推送的 `20260722_0001`、`20260722_0002`；schema comment 通过新的 additive migration 交付。
- 成功标准：目标 database 存在且 Alembic current=head；4 张认证表和全部字段均有非空中文 COMMENT；Redis authenticated `PING` 通过；应用 `/health/ready` 在真实 MySQL/Redis 下返回 `200`。
- 若本机旧 Redis 的非 UTF-8 `INFO` 文本与新版 redis-py 不兼容，只以 authenticated `PING` 作为可用性 gate，不把 INFO 解码失败误报为 Redis 不可用。

### 补验结果

- Windows `MySQL80` 与 `Redis` services 均为 Automatic/Running；MySQL 8.0.43 认证成功，Redis authenticated `PING=True`。
- `.env` 指定的目标 database 已按 `utf8mb4 / utf8mb4_0900_ai_ci` 创建并升级至 `20260722_0003`。
- `information_schema` 验证 4 张认证表、4 个 table comments、41 个 column comments 全部存在；`alembic check` 无 schema drift。
- 临时注入 Redis认证 URL 后，真实应用 `/health/ready` 返回 `200`，MySQL/Redis 均为 `up`。
