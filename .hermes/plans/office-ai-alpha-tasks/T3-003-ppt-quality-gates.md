# T3-003 PPT QA

- 状态：`BLOCKED`
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
