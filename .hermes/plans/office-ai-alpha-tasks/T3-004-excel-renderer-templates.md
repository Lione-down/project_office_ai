# T3-004 Excel Renderer 与系统模板

- 状态：`BLOCKED`
- Depends on：`T3-003`
- 来源：总计划第 6、11 节与 Day 14
- 建议 commit：`feat(excel): add deterministic sales analysis workbook renderer`

## 目标

使用 XlsxWriter 从版本化 `WorkbookPlan` 确定性生成销售分析工作簿，并通过 LibreOffice 验证副本完成公式重算。

## 交付范围

- `backend/app/services/renderers/excel/`、`WorkbookPlan` JSON Schema、测试与 2 套系统认证模板。
- 数据表、汇总、同比/环比、排名、基础图表、条件格式、数据验证、冻结窗格和打印设置。
- 英文函数名/参数分隔符、允许公式白名单和确定性缓存值。
- LibreOffice 对验证副本重新计算；原始输出保持不可变。

## 实施步骤

1. 先写 Schema、表格、汇总、同比/环比、排名、图表范围、条件格式和缓存值测试。
2. 实现两个模板和最多 20 Sheet/20 万生成单元格边界。
3. 用 XlsxWriter 创建新工作簿；openpyxl 只用于安全读取/必要修改，不承担公式计算。
4. 生成验证副本并用 LibreOffice 重算和打开，记录公式与缓存值差异。
5. 以不可变资产版本保存输出、模板版本和 Renderer 版本。

## 验收标准

- 固定 `WorkbookPlan` 的关键数字、公式、Sheet、图表范围和格式可重复。
- LibreOffice 可无修复打开验证副本；原始输出不会因验证被覆盖。
- 公式只来自白名单，写入英文函数名和分隔符，并带确定性缓存值。
- 两套模板均有 Contract Test。

## 验证

```powershell
docker compose up -d libreoffice
docker compose run --rm backend pytest backend/tests/renderers/spreadsheet -q
docker compose run --rm backend pytest backend/tests/integration -q
```

## 非范围与回滚

- 不创建 Pivot Table/Chart、Power Query、DAX、VBA、外部连接或用户模板。
- 回滚到上一 Renderer/模板版本，保留已生成工作簿和验证副本。
