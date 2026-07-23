# T3-004 Excel Renderer 与系统模板

- 状态：`DONE`
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

## 实施合同

- `workbook-plan.v1` 使用 strict Pydantic contract 导出版本化 JSON Schema；根对象固定
  `excel-renderer.v1`、`zh-CN`、系统模板引用、文档 metadata、Evidence ID 和有序 Sheet。
- Sheet 只允许 `data` 与 `summary` 两类。数据 Sheet 由 typed raw columns、确定性计算列和
  rows 组成；汇总 Sheet 由 `SUM`/`AVERAGE`/`COUNT` 指标和基础 `column`/`line`/`pie`
  图表组成。Sheet 名、列 key、跨 Sheet/列引用、图表 range 必须在渲染前闭合校验。
- 计算列只允许 `yoy`、`mom` 与 `rank`。Renderer 仅生成英文 `IFERROR`、`RANK.EQ`、
  `SUM`、`AVERAGE`、`COUNT` 函数和英文逗号参数分隔符；不接受 Plan 自由公式、外部链接、
  宏、Pivot、Power Query 或客户端输出路径。
- 每个公式由 Renderer 根据结构化引用同时计算显式 cache；原始文本关闭
  `strings_to_formulas`/`strings_to_urls`，避免把用户文本解释为公式或链接。
- 计划最多 20 个 Sheet、200,000 个实际生成 cell；精确边界允许，超限在创建 XLSX 前以
  稳定 contract error 拒绝。
- 两套模板固定为 `excel.analysis-dashboard.v1@1.0.0` 与
  `excel.operating-review.v1@1.0.0`，只改变认证样式，不改变数据、公式或来源语义。
- 原始 XLSX 以 owner/asset 派生的固定 key 原子保存且不可覆盖；trace 固定记录原件
  SHA-256/size、Plan SHA-256、Schema/Renderer/template version。
- LibreOffice 只处理独立 validation copy。重算前后分别用 openpyxl
  `data_only=False/True` 有界读取公式与 cache，写出
  `workbook-validation-report.v1`；报告记录公式/cache 差异，且重验原始 XLSX hash 未变化。
- LibreOffice、Microsoft Office/WPS 或 Docker 不可用时只记录真实缺口；Python contract
  与真实 XLSX ZIP/openpyxl 证据不能冒充这些 runtime/人工兼容通过。

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

## 完成记录

- strict `workbook-plan.v1`、两套模板、数据/汇总/同比/环比/排名、基础图表、条件格式、
  data validation、冻结窗格、打印设置、公式白名单、显式 cache 和精确容量边界已实现。
- 真实 XlsxWriter XLSX 由 openpyxl 分别按 formula/cache 视图复验；同 Plan 两次输出 bytes
  一致，原始 formula-like 文本未被解释为公式或 URL，ZIP 不含 external link/VBA。
- 原始 XLSX 使用 owner/asset 固定 key 不可覆盖；Plan SHA-256、Schema/Renderer/template
  version 同时写入结果 trace、XLSX custom properties 和 validation report。
- private LibreOffice sidecar 新增 strict spreadsheet recalculation contract；只接收
  UUID/hash/version，从固定资产 key 读取原件，并复验 validation copy/report key、hash、
  formula/cache 差异和完成重放。镜像已包含 `libreoffice-calc`。
- focused 为 `36 passed`；integration 为 `4 passed`；backend broad 为
  `513 passed, 2 skipped`，两项 skip 仅为未 opt-in 的真实 Agnes Contract。
- 当前主会话 deep review 修复 validation inline 长度/anchor 边界、目的文件覆盖 race、
  validation artifact replay/tamper、坏 XLSX 稳定错误，以及 Backend 无 `soffice` 的错误
  进程边界；最终无剩余 blocking finding。
- 当前 PATH 无 `docker`/`docker-compose`/`soffice`，已逐条实际尝试任务卡三条 Docker
  命令且均在创建容器前 `CommandNotFoundException`；常见 LibreOffice 安装路径也不存在。
  因此未把 fake sidecar、真实 XLSX 或 openpyxl contract 冒充 LibreOffice runtime、
  Microsoft Office/WPS 兼容通过。
