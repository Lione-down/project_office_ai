# T4-003 黄金数据回归

- 状态：`DONE`
- Depends on：`T4-002`
- 外部前置：用户已于 `2026-07-26` 确认 1 组本地销售材料拥有使用权，并授权在不修改
  原件的前提下生成脱敏副本；原件保持在 ignored `golden-data/private/`
- 来源：总计划第 3、16、18、21、22 节与 Day 18
- 建议 commit：`test(golden): validate office generation corpus`

## 用户批准的 Pilot 范围变更

- 用户明确说明没有更多材料，批准以一份 XLSX 来源和一份 PPTX 参考输出组成唯一
  `sales-pilot-v1` case，替代原计划 10 组 corpus 的本任务执行前置。
- 本任务必须持续标记为 `1/10 pilot`：20 次 PPT 与 20 次 Excel 重复运行只验证该 case
  的确定性、结构、指标和引用合同，不证明跨行业、跨模板或多样销售材料质量。
- 原始 XLSX 当前包含人员/客户/联系电话/地址信息、31 个 Sheet 和两个公式错误；原始
  PPTX 含作者 metadata 与 embedded objects。只有结构化脱敏、移除空白 Sheet、明确公式
  修复口径、递归检查嵌入对象并通过 Secret/PII 扫描后的副本可以进入 Git。
- 期望指标由脱敏来源确定性复算并固化到 Manifest，标记为
  `system_derived_from_authorized_source`，不冒充用户单独签署的业务口径。

## 目标

用真实或脱敏销售材料建立可重复的黄金回归，验证数字、公式、页数、Sheet、图表和证据引用，而不是只证明文件能生成。

## 交付范围

- `golden-data/inputs/`、`golden-data/expected/`、`golden-data/manifests/` 与数据许可/脱敏清单。
- `backend/tests/golden/`、`ppt-renderer/tests/golden/` 和稳定 `app.utils.golden_regression` 入口。
- 1 组授权且脱敏的 pilot 输入，明确关键事实、期望指标、允许偏差、期望页/Sheet 范围
  和引用要求；Manifest 明确原计划覆盖为 `1/10`。
- 同一 case 至少 20 次 PPT 与 20 次 Excel 重复生成/验证及结构化回归报告；报告区分
  `generated`、`reference_validated` 与因外部 runtime 缺失未执行的证据。

## 实施步骤

1. 以 tests-first contract 固化授权、脱敏、package 安全、Manifest checksum、指标、重复
   运行和报告脱敏边界；先观察缺少 golden regression package/corpus 的 RED。
2. 不修改 private 原件；使用结构化 XLSX/PPTX 工具生成 deterministic aliases，移除作者
   metadata、电话/客户/地址、空白 Sheet 和外部关系，并递归验证嵌入对象。
3. 修复副本中的已知公式错误时保留 cell、原 formula hash、修复规则和确定性期望值，
   Manifest/报告不保存原公式正文或 PII。
4. 固化脱敏输入/参考输出版本、期望指标、允许偏差、页/Sheet/图表/引用要求和 SHA-256，
   避免样本漂移。
5. 运行 20 次 PPT/20 次 Excel，比较关键数字、公式、页数、Sheet、图表范围和 evidence ID；
   Excel 比较 deterministic bytes，PPT baseline 用 SHA-256 固定且重复生成比较包含 media 的
   OOXML structural digest（仅排除会变化的 core timestamp metadata）。
6. 将失败归类为解析、口径、内容、视觉、Provider、runtime 或流程问题；阻断问题必须修复
   并记入 `pitfalls.md`。
7. 保存不含用户材料的结构化报告和运行环境/版本信息，不保存 Agnes Key、完整 Prompt、
   private 路径或原始业务正文。

## 验收标准

- `sales-pilot-v1` 有用户许可确认、机器可验证的脱敏证明、期望值和 `1/10 pilot` 声明；
  不复制/切片同一材料冒充 10 组真实质量证据。
- 40 次重复运行全部产出可审计结果；所有 `passed` 输出无阻断级差异，并明确每次属于
  真实生成、参考验证或受控 fallback。
- Excel 合计、同比、环比、排名和公式缓存与确定性复算一致。
- PPT 无空白页、越界、缺图、标题截断或不可追踪结论。
- tracked corpus 无手机号、座机、身份证、邮箱、人员/客户/终端名称、地址、private author
  metadata、宏、外部 relationship、Secret、private 路径或非目录嵌入 payload；生成物
  metadata 只允许脱敏系统值 `Office AI`。
- 缺少 Docker、真实 Agnes、LibreOffice、Microsoft Office 或 WPS 时只记录真实缺口；
  不把 OOXML/Mock/受控生成证据升级为外部 runtime 通过。

## 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.utils.golden_regression `
  ..\golden-data\manifests\sales-pilot-v1.json --repo-root ..
.\.venv\Scripts\python.exe -m pytest tests/golden -q
cd ..\ppt-renderer
npm test -- tests/golden

docker compose run --rm backend python -m app.utils.golden_regression
docker compose run --rm backend pytest backend/tests/golden -q
docker compose run --rm ppt-renderer npm test
```

## 非范围与回滚

- 不把未脱敏真实文件、客户隐私或无许可材料提交到仓库。
- 样本更新必须新建版本并说明原因；失败报告不可删除来制造通过结果。
- 本任务完成只解除 T4-004 的代码依赖；1/10 覆盖限制必须继续进入
  `docs/PROGRESS.md` 和最终 Alpha release note。

## 完成证据

- `sales-pilot-v1` 的授权、脱敏、5 个 tracked artifact checksums、6 个期望指标、
  4 个 evidence IDs、页/Sheet/chart requirements 已进入 strict Manifest。
- Backend golden `9 passed`；CLI 记录 Excel generation `20`、PPT reference validation
  `20`，Node golden 另完成 PPT generation `20` 的 structural digest 验证。
- Microsoft PowerPoint 16.0 实际导出 4/4 slides；Microsoft Excel 16.0 实际打开 2
  Sheets、1 chart、17 formulas，最终 `0` formula error。视觉迭代修复 closing overlap、
  重复 evidence footer、`RANK.EQ` 的 `#NAME?` 和 chart print-area 裁切。
- corpus 精确扫描为 private token/手机号/座机/邮箱/unsafe embedded payload/unsafe author
  全部 `0`。原件保持 ignored 且未修改。
- Backend full `561 passed, 2 skipped`；Frontend `59 passed`、PPT Renderer `22 passed`；
  build、Ruff、pip/npm audit 通过。Docker、WPS、LibreOffice 和真实 Agnes 仍未验证。
