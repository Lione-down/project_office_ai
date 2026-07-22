# T1-003 用户、Session 与邀请码

- 状态：`READY`
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
