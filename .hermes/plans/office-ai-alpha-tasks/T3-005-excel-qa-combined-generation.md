# T3-005 Excel QA 与组合任务

- 状态：`DONE`
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

## 可执行成功标准（TDD Contract）

- `backend/tests/quality/spreadsheet/` 先以 RED 覆盖：
  `#REF!/#VALUE!/#DIV/0!/#NAME?`、LibreOffice 无法打开、formula/cache
  确定性复算漂移、chart category/value range 越界，以及未解决的
  Sheet/字段类型/单位冲突；每个 blocker 使用稳定 code，报告不得保存公式正文、
  storage key、本地路径或用户材料。
- `workbook-quality-report.v1` 必须关联不可变原始 XLSX、Workbook Plan、
  Renderer/template、LibreOffice validation copy 与完整性摘要；`passed` 和
  `passed_with_warnings` 允许下载，`blocked` 禁止下载。下载前必须重新校验
  validated artifact 的 hash 与 byte size。
- `backend/tests/generation/combined/` 先以 RED 覆盖两个子输出独立保存
  output asset、quality status、download boundary 与 estimated credits；
  两成任务 `succeeded`，一成一败为 `partial_success`，只 finalize 成功额度并
  release 失败额度。
- 重放相同质量结果或 settlement 事件不得重复写
  `generation_finalize`/`generation_release`，不得重复改变余额；恢复只依赖
  MySQL task/step/file asset/ledger checkpoint，不依赖 Redis 中唯一状态。
- `backend/tests/integration/` 覆盖从已确认 combined Brief 创建同一
  `combination_group_id` 的 PPTX/XLSX 步骤，到任务/outputs API 返回各自质量结果和
  owner-scoped 下载资产；不得调用真实 Agnes，不读取 `.env` 或用户文件。
- focused verification 使用任务卡四条命令的本机等价命令执行；Docker、真实
  MySQL/Redis/LibreOffice、Microsoft Office/WPS 只在实际可用并实际运行后记录通过。

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

## 完成证据

- RED/GREEN 已覆盖公式错误、原始数值与公式 cache 确定性复算、精确 chart range、
  Sheet/字段/单位冲突、validated artifact 下载完整性，以及组合任务一成一败和幂等结算。
- Excel output service 使用 generation-owned `file_assets` 与稳定 checkpoint 保存
  `analysis.xlsx`；质量服务保存 strict `workbook-quality-report.v1`、LibreOffice 原始
  validation report 和独立 validation copy，重放时复验全部 hash/size。
- `GET /generations/{task_id}/outputs` 返回两个子输出各自的质量、下载边界、资产版本和
  estimated credits；只有 owner、task、category、version、quality artifact 全部一致时
  才暴露可下载输出。
- task-card focused：spreadsheet QA `22 passed`、combined `9 passed`、integration
  `5 passed`、PPT Renderer `20 passed`；补充聚焦集合 `33 passed`。Backend 全量
  `545 passed, 2 skipped`，两项 skip 仅为未
  opt-in 的真实 Agnes Contract。Frontend `12 passed`、PPT Renderer `20 passed`；
  Ruff、build、pip/npm audit、Alembic single head 均通过。
- 当前 PATH 无 Docker 和 `soffice`；未取得真实 MySQL/Redis、LibreOffice Calc、
  Microsoft Office/WPS 或真实 Agnes 新证据，不把 fake/Mock contract 提升为真实 runtime
  通过。
