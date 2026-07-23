# T2-005 Brief 确认与 Preflight

- 状态：`READY`
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
