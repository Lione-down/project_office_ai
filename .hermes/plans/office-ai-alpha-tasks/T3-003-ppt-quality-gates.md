# T3-003 PPT QA

- 状态：`DONE`
- Depends on：`T3-002`
- 来源：总计划第 3、11、16 节与 Day 13
- 建议 commit：`test(ppt): enforce presentation quality gates`

## 目标

为 PPTX 建立可自动阻断的兼容性、完整性和布局质量门禁，并允许一次确定性自动修复。

## 交付范围

- `backend/app/services/quality/presentation/`、黄金样本与质量结果 Schema。
- OOXML 完整性、LibreOffice 打开、空白页、页缺失、对象越界、图片缺失、标题截断、图表引用和证据引用检查。
- LibreOffice 转 PDF、PDF 转图片的预览链路。
- `passed`、`passed_with_warnings`、`blocked` 三种质量结果和一次自动修复。

## 实施步骤

1. 先建立损坏 OOXML、空白页、越界、缺图、长标题和不存在图表范围的失败样本。
2. 实现 OOXML/关系检查与 LibreOffice 无交互打开/转换。
3. 实现布局几何和内容完整性规则；告警与阻断原因使用稳定代码。
4. 对可确定修复的问题只修复一次，并对修复输出重新执行全部门禁。
5. 生成预览资产并关联原输出、质量报告和 Renderer 版本。

## 验收标准

- `passed`/`passed_with_warnings` 可下载；`blocked` 禁止下载、任务失败且不扣费。
- 自动修复最多一次，修复失败不会循环或覆盖原输出。
- 所有阻断样本被正确拒绝，正常样本被正确放行。
- 质量报告包含页码、规则、严重级别和可追踪证据，不泄露敏感内容。

## 本次可执行成功标准

- Owned implementation 限于 `backend/app/services/quality/presentation/`、对应
  `backend/tests/quality/presentation/` synthetic fixtures、质量运行所需的
  settings/dependency/Compose 边界，以及与当前 task/asset/download 状态衔接的最小改动。
- `presentation-quality-report.v1` 严格拒绝未知字段，报告固定关联原始输出
  asset/hash、Renderer/template/Plan 版本、质量引擎版本、LibreOffice 结果、预览摘要、
  修复次数和脱敏 finding；finding 不保存原始正文、物理路径或 storage key。
- synthetic fixtures 覆盖：损坏 OOXML、空白页、页缺失、对象越界、缺图、长标题、
  坏图表引用和 Evidence 引用失败；正常样本必须放行。
- LibreOffice sidecar 只接受内部、结构化且受控的 asset identity，在无交互模式打开并转
  PDF；PDF 预览逐页转 PNG。未实际执行 LibreOffice/Office/WPS 时不得以 ZIP/XML
  structure test 代替兼容性通过。
- 只允许一次确定性修复；修复输出使用新的受控文件，不覆盖原 PPTX，随后重新执行全部
  OOXML、LibreOffice、布局、内容和 Evidence 门禁。
- `passed`/`passed_with_warnings` 才允许下载；`blocked` 返回稳定 permanent failure，
  由既有任务结算释放预留且不扣费。质量报告、PDF/PNG 预览与原输出及 Renderer 版本可追踪。
- focused 后运行 Backend broad、PPT Renderer、Frontend、migration/Compose 静态、
  dependency/security 和 Git exact-path gate；Docker、真实 MySQL/Redis/Agnes、
  LibreOffice、Microsoft Office/WPS 的未运行项按实际证据记录。

## 验证

```powershell
docker compose up -d libreoffice
docker compose run --rm backend pytest backend/tests/quality/presentation -q
docker compose run --rm ppt-renderer npm test
docker compose run --rm backend pytest backend/tests/integration -q
```

## 非范围与回滚

- 不承诺任意字体环境像素级一致或完整视觉 AI 审核。
- 回滚质量规则版本时保留历史报告；不得把旧 `blocked` 输出直接改为通过，必须重新验证。

## 完成记录

- 已按 TDD 建立 8 类 deterministic synthetic failure sample、严格
  `presentation-quality-report.v1`、OOXML/layout/Evidence 检查、一次确定性修复、
  LibreOffice/PDFium sidecar、不可变 report/preview/repaired artifact 与下载门禁。
- Focused `52 passed`；Backend broad `477 passed, 2 skipped`；PPT Renderer
  `20 passed`，Frontend `12 passed`，两端 build/audit 与 Python quality gate 通过。
- 当前主机没有 Docker 与 `soffice`，未执行真实 LibreOffice、Microsoft Office/WPS、
  真实 MySQL/Redis 或真实 Agnes；ZIP/XML 和 PDFium contract 未冒充这些 runtime 通过。
