# T3-002 PPT Renderer 与系统模板

- 状态：`BLOCKED`
- Depends on：`T3-001`
- 来源：总计划第 6、11 节与 Day 12
- 建议 commit：`feat(ppt): add deterministic sales presentation renderer`

## 目标

用独立 Node.js/TypeScript Worker 和 PptxGenJS，从经过验证的 `PresentationPlan` 确定性生成可打开的销售汇报 PPTX。

## 交付范围

- `ppt-renderer/src/`、测试、构建入口和 Worker Contract。
- `PresentationPlan` JSON Schema；只接受结构化数据，不直接接收 Agnes 自由文本。
- 3 套 16:9 系统认证模板，使用 Slide Master、Placeholder、主题色和固定布局。
- 标题、正文、图片、表格、基础图表、页码、来源说明、演讲者备注和输出元数据。

## 实施步骤

1. 先写 Schema、确定性输出、标题/正文/图片/表格/图表/来源/备注 Renderer Contract Tests。
2. 定义跨 Python/Node 边界的版本化 JSON 输入输出和错误结构。
3. 实现三套模板及 3–30 页边界；所有事实引用可追踪到 evidence ID。
4. 生成固定样本，使用 LibreOffice Headless 打开并转出验证副本。
5. 把输出作为不可变 `file_assets` 版本关联任务，不覆盖旧输出。

## 验收标准

- 同一 `PresentationPlan`、模板版本和 Renderer 版本产生结构等价的 PPTX。
- 固定样本能被 LibreOffice 无修复打开，包含预期页数、元素和元数据。
- Renderer 拒绝自由文本、未知 Schema 版本和不存在的图表数据引用。
- 三套模板均有 Contract Test，且不依赖用户上传 PPTX。

## 验证

```powershell
docker compose run --rm ppt-renderer npm test
docker compose run --rm ppt-renderer npm run build
docker compose run --rm backend pytest backend/tests/renderers/presentation -q
```

## 非范围与回滚

- 不支持用户模板、动画、SmartArt、嵌入对象、任意母版复刻或 PPTX 输入。
- 回滚通过切换到上一不可变模板/Renderer 版本；已生成输出不覆盖、不修改。
