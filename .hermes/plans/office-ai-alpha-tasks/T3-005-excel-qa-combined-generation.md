# T3-005 Excel QA 与组合任务

- 状态：`BLOCKED`
- Depends on：`T3-004`
- 来源：总计划第 3、7、9、11、16 节与 Day 15
- 建议 commit：`feat(generation): complete combined ppt and excel workflow`

## 目标

完成 Excel 阻断质量门禁，并将 PPTX/XLSX 两个子输出接入同一组合任务，实现独立质量结果和部分成功结算。

## 交付范围

- `backend/app/services/quality/spreadsheet/` 和组合任务集成测试。
- 文件打开、公式错误、确定性复算、图表范围、Sheet/字段/单位冲突检查。
- 两个子任务/输出的状态聚合、质量报告、下载边界和积分分摊。
- 单输出失败时 `partial_success`，只结算成功输出，失败部分释放预留。

## 实施步骤

1. 先写 `#REF!/#VALUE!/#DIV/0!/#NAME?`、范围错误、单位冲突、复算不一致和一成一败测试。
2. 实现公式错误扫描、关键销售指标确定性复算和 LibreOffice 结果对比。
3. 按 PPTX/XLSX 子输出分别保存状态、质量结果、资产版本和结算额度。
4. 实现组合状态聚合与幂等结算，重放事件不得重复 finalize/release。
5. 完成从已确认 Brief 到双输出下载的 Week 3 端到端测试。

## 验收标准

- 阻断错误禁止 XLSX 下载并触发失败释放；告警可下载且可见。
- 两个输出成功时任务 `succeeded`；一个成功时 `partial_success` 且只扣成功部分。
- 同一材料、一个模型、两个 Skill 分别生成一个 PPTX 和一个 XLSX。
- Week 3 Gate 的端到端测试不依赖 Redis 中的唯一状态，重启后可恢复。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/quality/spreadsheet -q
docker compose run --rm backend pytest backend/tests/generation/combined -q
docker compose run --rm backend pytest backend/tests/integration -q
docker compose run --rm ppt-renderer npm test
```

## 非范围与回滚

- 不做 PPT 按页重生成、Excel 依赖感知局部重生成或复杂历史工作簿无损往返。
- 回滚组合聚合逻辑时保留两个子输出和账务流水；积分修正只追加反向流水。
