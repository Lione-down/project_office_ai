# T4-003 黄金数据回归

- 状态：`BLOCKED`
- Depends on：`T4-002`
- 外部前置：10 组拥有使用权且已脱敏的销售输入和明确期望指标
- 来源：总计划第 3、16、18、21、22 节与 Day 18
- 建议 commit：`test(golden): validate office generation corpus`

## 目标

用真实或脱敏销售材料建立可重复的黄金回归，验证数字、公式、页数、Sheet、图表和证据引用，而不是只证明文件能生成。

## 交付范围

- `golden-data/inputs/`、`golden-data/expected/`、`golden-data/manifests/` 与数据许可/脱敏清单。
- `backend/tests/golden/`、`ppt-renderer/tests/golden/` 和稳定 `app.utils.golden_regression` 入口。
- 10 组输入，每组明确关键事实、期望指标、允许偏差、期望页/Sheet 范围和引用要求。
- 至少 20 次 PPT 与 20 次 Excel 自动生成及结构化回归报告。

## 实施步骤

1. 在纳入 Git 前逐组确认版权许可、隐私脱敏和不含密钥；敏感原始数据只放 `golden-data/private/` 且保持忽略。
2. 固化输入版本、期望指标和 Manifest 校验值，避免样本漂移。
3. 运行 20 次 PPT/20 次 Excel，比较关键数字、公式、页数、Sheet、图表范围和 evidence ID。
4. 将失败归类为解析、口径、内容、视觉、Provider 或流程问题；阻断问题必须修复并记入 `pitfalls.md`。
5. 保存结构化报告和运行环境/版本信息，不保存 Agnes Key 或完整 Prompt。

## 验收标准

- 10 组数据均有明确许可、脱敏证明和期望值，不用合成样本冒充真实质量证据。
- 40 次生成全部产出可审计结果；所有 `passed` 输出无阻断级差异。
- Excel 合计、同比、环比、排名和公式缓存与确定性复算一致。
- PPT 无空白页、越界、缺图、标题截断或不可追踪结论。

## 验证

```powershell
docker compose run --rm backend python -m app.utils.golden_regression
docker compose run --rm backend pytest backend/tests/golden -q
docker compose run --rm ppt-renderer npm test
```

## 非范围与回滚

- 不把未脱敏真实文件、客户隐私或无许可材料提交到仓库。
- 样本更新必须新建版本并说明原因；失败报告不可删除来制造通过结果。
