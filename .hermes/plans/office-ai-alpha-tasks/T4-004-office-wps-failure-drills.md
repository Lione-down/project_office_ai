# T4-004 Office/WPS 与故障演练

- 状态：`BLOCKED`
- Depends on：`T4-003`
- 外部前置：本机可用 Microsoft Office、WPS 和真实 Agnes 测试配置
- 来源：总计划第 3、10、16–18、22 节与 Day 19
- 建议 commit：`test(alpha): record compatibility and recovery drills`

## 目标

用真实桌面 Office/WPS 和受控故障演练证明输出兼容性、Provider 错误语义、队列恢复、幂等与积分恢复符合 Alpha 合同。

## 交付范围

- 全部黄金 `passed` 输出的 Microsoft Office/WPS 人工打开记录。
- Agnes `401`、`429`、`5xx`、超时、非法 Schema 的受控演练记录。
- Redis 重启、Worker 重启、MySQL Outbox 恢复、重复提交、取消、部分成功和积分恢复演练。
- `docs/PROGRESS.md` 中记录环境、步骤、预期、实际、证据路径和未通过项。

## 实施步骤

1. 在 Microsoft Office 和 WPS 分别打开全部通过自动门禁的黄金 PPTX/XLSX，记录修复提示、布局、公式和图表结果。
2. 使用可控 Mock/测试响应演练错误；真实 Agnes 只做批准范围内的必要 Contract 调用，不制造破坏性流量。
3. 在有持久任务时重启 Redis/Worker，验证 MySQL checkpoint 与 Outbox 恢复且不重复扣费。
4. 重放相同 Idempotency-Key，演练取消、一成一败和 `provider_uncertain` 人工处置。
5. 所有失败保持未完成状态并进入 `pitfalls.md`/`docs/PROGRESS.md`，不得降级 Gate 掩盖。

## 验收标准

- 所有标记 `passed` 的黄金文件在 Microsoft Office 与 WPS 中均无修复提示。
- Agnes 错误分类和重试次数符合合同；超时不确定不会自动重复计费。
- Redis/Worker 重启后任务恢复，重复提交不产生重复任务/预留/结算。
- 演练记录足以由另一人复现，并明确软件版本与证据文件。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/integration -q
docker compose run --rm backend pytest backend/tests/providers/agnes_contract -q
docker compose run --rm backend python -m app.utils.golden_regression
```

人工检查：逐个打开黄金 PPTX/XLSX，核对修复提示、页/Sheet 数、关键数字、公式值、图表、字体和布局，并在 `docs/PROGRESS.md` 留证。

## 非范围与回滚

- 不在没有 Microsoft Office/WPS 或真实 Agnes 证据时声明兼容通过。
- 演练不得删除持久卷或生产数据；恢复失败时停止封版，保留任务、流水和日志证据。
