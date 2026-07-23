# T2-005 Brief 确认与 Preflight

- 状态：`DONE`
- Depends on：`T2-004`
- 来源：总计划第 7、9、10、12 节与 Day 10
- 建议 commit：`feat(preflight): add brief confirmation and conflict gates`

## 目标

让用户查看、修改并确认 Brief，在积分预留前解决所有单位、来源、Skill 和模型能力阻断项，并锁定预计积分。

## 交付范围

- Brief 查看、修改为新 Revision、确认 API 与基础前端页面。
- Preflight Service：单位、数据口径、来源、Skill、模板和模型能力冲突规则。
- 已知两 Skill 组合的输出计划和预计积分计算。
- 状态 `draft → preflight → needs_resolution/queued` 的门禁，不在本任务执行生成 Worker。

## 实施步骤

1. 先写不可变 Revision、未解决阻断、模型不兼容、重复确认、预计积分和一键模式测试。
2. 修改 Brief 时创建新 Revision，保留来源资产、术语、Skill、模型和模板版本快照。
3. 将冲突分为自动合并、需要确认、阻断冲突、不兼容，并提供中文可操作信息。
4. 只有无阻断项且用户确认预计积分后才能排队；确认后预计积分不得提高。
5. 更新 API、状态机与进度文档。

## 本任务可执行 Contract

- `GET /api/v1/briefs/{brief_id}` 可读取 owner-scoped 历史 Revision；`PATCH` 只允许基于当前最新 Revision 修改用户可编辑字段并追加下一 Revision，来源资产、术语、Skill、模型和 Evidence 引用不能由客户端替换。
- 修改可覆盖 goal、audience、must include/exclude、输出标题、可见引用策略、系统模板版本和显式冲突 resolution；旧 Revision 的 content、checksum、source snapshot、Preflight snapshot 和确认信息不被改写。
- `POST /api/v1/generations/preflight` 重新校验 Evidence blocker、Brief unresolved item、Skill 合同、系统模板合同和当前模型能力，返回 `auto_merge / needs_confirmation / blocking / incompatible` 四类中文可操作结果。
- Alpha 系统模板在本任务固化为 versioned Preflight contract：3 个 PPT 与 2 个 Excel template code；模板文件、renderer 和 QA 仍由 T3 交付。
- 每个 Alpha 输出基础预计积分为 `800`，乘所选模型 `credit_multiplier` 后按单个输出向上取整；PPTX/XLSX 组合分别计算并求和，模型 multiplier 与各子输出费用进入不可变 Preflight snapshot。
- 普通 Preflight 无阻断时进入 `preflight`，仍需 `POST /api/v1/briefs/{brief_id}/confirm` 接受当前预计积分；一键模式只在无阻断且同时提交相同预计积分时直接确认。
- 本任务中的 `queued` 是已确认 Brief 的 generation-ready handoff 状态；不创建 `generation_tasks`、不写 `credit_ledger`、不发 Outbox、不执行 Worker。以上事务边界留给 T3-001。
- 重复确认相同 Revision 与相同预计积分返回既有确认结果；确认后的 snapshot 不重算也不得提高。过期 Revision、预计积分变化、任何 blocker 或 capability/template incompatibility 都不能进入 `queued`。

## 验收标准

- 存在单位未知、数字低置信、来源冲突或能力不匹配时不能进入生成。
- 用户修改产生新 Revision，旧 Revision 不被覆盖。
- 两个 Skill 共用材料、术语库和一个模型，分别计划一个 PPTX 与一个 XLSX。
- Week 2 Gate 可独立演示：上传材料到获得、修改并确认带证据 Brief。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/preflight -q
docker compose run --rm backend pytest backend/tests/briefs -q
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
```

## 非范围与回滚

- 不生成 Office 文件，不实现任意三 Skill 组合或局部重生成。
- 回滚只停用新 Preflight 规则；已确认 Brief 和预计积分快照保持可审计。
