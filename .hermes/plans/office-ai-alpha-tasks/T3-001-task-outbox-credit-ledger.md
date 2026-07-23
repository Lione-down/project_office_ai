# T3-001 任务、Outbox 与积分事务

- 状态：`DONE`
- Depends on：`T2-005`
- 来源：总计划第 4、6、7、10、12 节与 Day 11
- 建议 commit：`feat(task): add durable generation orchestration`

## 目标

建立以 MySQL 为事实来源、Redis 可丢失的持久生成编排，并保证幂等提交、积分预留/结算/释放和故障恢复一致。

## 交付范围

- `generation_tasks`、`generation_task_steps`、`generation_task_inputs`、`outbox_events`、完整 `credit_ledger` 与相关迁移。
- MySQL Outbox 到 Redis 的 Dispatcher、Python Worker 消费、阶段 checkpoint 和僵尸任务恢复。
- 每用户最多 2 个运行任务、Credential RPM/TPM/最大并发限制。
- `draft/preflight/queued/running/succeeded/partial_success/provider_uncertain/failed/cancelled` 状态转换。

## 实施步骤

1. 先写重复幂等键、预留、成功结算、失败释放、取消、部分成功和重复 Outbox 投递测试。
2. 同一事务创建任务、输入快照、积分预留和 Outbox 事件；唯一约束阻止重复任务/扣费。
3. Worker 每阶段落 MySQL checkpoint，Redis 重启后可从 Outbox 和持久状态恢复。
4. 实现有限重试和错误分类；Provider 超时结果未知时进入 `provider_uncertain` 并保留预留。
5. 实现取消与僵尸任务恢复，所有流水只追加，不原地更新历史。

## 验收标准

- 同一用户和 Idempotency-Key 只创建一个任务和一笔对应预留。
- Redis 数据清空后可从 MySQL 恢复待投递/运行任务，不重复结算。
- 失败释放积分；`provider_uncertain` 不自动重试或重复扣费。
- 并发限制和 Credential 限流有确定性测试。

## 本次执行合同

- `POST /api/v1/generations` 只接受已确认且 owner-scoped 的最新 Brief，并在一个数据库事务内创建任务、不可变输入/模型/Skill 快照、`generation_reserve` 和首个 Outbox 事件；重放返回既有任务。
- `GET /api/v1/generations/{task_id}`、取消、受限重试和 Credits 查询保持 owner scope、稳定错误码与 `private, no-store`；T3-001 不暴露 Admin retry/audit 半成品。
- Worker 以任务/步骤持久 checkpoint 为权威；重复 queue message 只能有一个 claim，确定失败有限重试，timeout 结果未知进入 `provider_uncertain` 并保留 reserve。
- 终态结算按成功子输出聚合：全部成功 finalize，全部失败或可取消任务 release，部分成功 finalize 成功费用并 release 未使用费用；ledger 只追加且每个结算动作幂等。
- Outbox Dispatcher 允许“已发布但未标记”的 at-least-once 重投；Redis 丢失后 reconciler 从 MySQL 任务状态创建新的可审计恢复事件，Worker 依靠数据库状态去重。
- 每用户最多 2 个 `running` 任务；Credential RPM/TPM 使用 Redis 原子窗口预算，最大并发由 MySQL active checkpoint 约束。Redis 限流丢失不能改变任务或账务事实。
- 新增 migration 必须保持单一 Head、SQLite 空库升级和 MySQL dialect offline DDL 可验证；Docker、真实 MySQL/Redis runtime 只按实际可用证据报告。
- Owned paths 限于 `backend/app/{api,core,models,schemas,services,settings,workers}`、`backend/alembic/versions`、`backend/tests/{generation,credits,outbox,integration}`、必要 Compose/专题文档、任务卡、索引、`docs/PROGRESS.md` 与 `pitfalls.md`；不实现 T3-002 renderer。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/generation -q
docker compose run --rm backend pytest backend/tests/credits -q
docker compose run --rm backend pytest backend/tests/outbox -q
docker compose run --rm backend pytest backend/tests/integration -q
```

## 非范围与回滚

- 不渲染 PPTX/XLSX；Worker 用可控测试步骤验证编排。
- 回滚状态机代码不能删除任务/流水；积分更正使用反向流水，Outbox 事件保持可审计。

## 执行记录

- Migration `20260723_0011` additive 建立 `generation_tasks`、`generation_task_steps`、`generation_task_inputs`、`outbox_events`，补齐 ledger task FK 与 ProviderCall task/step scope；业务表达到 19/21。
- Generation 创建在单一事务内锁定 owner/latest confirmed Brief、Model/Credential/Provider 与用户余额，冻结 Brief/asset/term/template/Skill/model 快照，写 reserve 和首个 Outbox；数据库唯一键与 service/API 双层 Idempotency-Key 校验保证重放。
- Worker/queue contract 覆盖每用户 2 个 running task、Credential 行锁与 Redis 原子 RPM/TPM 预算、checkpoint、有限重试、取消、完整/部分结算、失败释放、`provider_uncertain` 保留预留、重复消息去重和 timeout。
- Outbox Dispatcher 由 backend lifespan 启动，采用 at-least-once 投递；Redis 丢失或 safe stale checkpoint 可由 MySQL 恢复，已开始但结果未知的 Provider checkpoint 收口为 `provider_uncertain`。Python queue consumer 接受注入的受控 step executor；T3-002 前不渲染或伪造 Office 输出。
- TDD RED 从缺失 generation service/model/migration/worker/outbox/limits/API 开始；focused 最终 `27 passed`，backend broad `397 passed, 2 skipped`，两项 skip 仅为未 opt-in 的真实 Agnes Contract。
- Ruff check/format、单文件 ≤500 行、单一 Alembic Head、SQLite 空库 upgrade、MySQL dialect offline upgrade/downgrade、`pip check`、`pip-audit`、Python/Node license metadata、`npm audit`、frontend test/build 与敏感模式扫描通过。
- 四条任务卡 Docker Compose 验证均已逐条实际尝试，但当前 PATH 无 `docker`，在容器创建前 `CommandNotFoundException`；未读取 ignored `.env`，因此真实 MySQL/Redis transaction/queue runtime 未冒充通过。真实 Agnes 仍只有 Mock Contract；Office/WPS 与 renderer 属于后续 Gate。
- 主会话顺序 deep review 修复 Skill version 未冻结、safe stale step 未复位、service 幂等校验绕过、满长 retry billing key 超列宽、ProviderCall 跨任务唯一键冲突、任务 timeout 未释放、确认后模型/费用漂移和子输出费用总和不一致。
