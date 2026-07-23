# T3-002 PPT Renderer 与系统模板

- 状态：`DONE`
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

### 本任务可执行成功标准

- `presentation-plan.v1` 使用严格 JSON Schema，固定 `schema_version`、`renderer_version`、3–30 页、系统模板 code/version、Evidence ID、图片和表格/图表数据引用；未知字段、非有限数值、自由文本根对象、缺失引用和路径型图片输入全部 fail closed。
- Node Worker 使用版本化 request/response/error envelope，只在受控 `WORK_ROOT` 内生成文件，不接受客户端输出路径；错误响应不回显 Plan、图片数据、文件路径或 stack trace。
- 3 套 `16:9` 模板分别定义 Slide Master、Placeholder、主题色、常用中文字体 fallback、标题/内容/章节/结束页固定布局，并覆盖标题、正文、图片、表格、柱/线/饼图、页码、来源、备注和 OOXML metadata。
- 固定脱敏 synthetic sample 在两次独立渲染后获得结构等价 OOXML；三套模板均能生成真实 `.pptx`，页数、notes、charts、media、masters、metadata 和 Evidence ID 可由 ZIP/XML contract 检查。
- Python 适配层验证 Node response、SHA-256、byte size 和受控相对路径，将输出以 `generated_task_id`、稳定幂等键和不可变版本写入 `file_assets`；retry/replay 返回同一完成资产，不覆盖已完成输出，finalization 失败保留可恢复 checkpoint。
- 实际尝试任务卡的 Compose 命令和 LibreOffice Headless 打开/转换；本机缺失 Docker/LibreOffice 时只记录原始环境结论，并以本地 Node/Python contract 证据替代，不标记 container/Office runtime 通过。

## 验证

```powershell
docker compose run --rm ppt-renderer npm test
docker compose run --rm ppt-renderer npm run build
docker compose run --rm backend pytest backend/tests/renderers/presentation -q
```

## 非范围与回滚

- 不支持用户模板、动画、SmartArt、嵌入对象、任意母版复刻或 PPTX 输入。
- 不实现 T3-003 的 overflow、字体替换、图片裁切、坏链、质量状态或自动修复；本任务只验证生成文件的结构合同与可打开性。
- 回滚通过切换到上一不可变模板/Renderer 版本；已生成输出不覆盖、不修改。

## 完成证据

- Node contract/build：`20 passed`；真实 PptxGenJS sample 为 4 页，包含 Slide Master、Placeholder、页码、notes、native table、bar/line/pie chart、media、Evidence/source 与 OOXML metadata；同 Plan 两次渲染结构等价。
- Python renderer/output contract：`27 passed`；跨进程 Node server + Python client smoke 生成 3 页、85,987-byte PPTX，并验证 response、Plan SHA-256、文件 SHA-256、byte size 与受控相对路径。
- 不可变输出使用 task/step checkpoint、稳定 asset ID 和 `file_assets.generated_task_id`；并发 replay、损坏 derived output repair、finalization recovery、ready file integrity 和不同 Plan conflict 均有回归。
- Docker 与 LibreOffice 在本机不可用，任务卡 Compose 命令和 Headless 打开/转换未进入对应 runtime，不标记通过；真实 Agnes 未 opt-in，Office/WPS 仍由后续 Gate 验收。
