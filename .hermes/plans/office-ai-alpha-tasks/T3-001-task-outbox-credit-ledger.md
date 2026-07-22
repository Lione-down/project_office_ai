# T3-001 任务、Outbox 与积分事务

- 状态：`BLOCKED`
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
