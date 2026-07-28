# Office AI Post-Alpha 生成 Plan 边界修复

- 状态：`DONE`
- 日期：`2026-07-28`
- 目标任务：`019fa767-93ea-7b56-a5cd-0a3f9a06bb8e`

## Root cause

- `PresentationGenerationPipeline` 把已验证的 `PresentationPlan` 实例传给只接受
  `dict` 的 `PresentationOutputService.render()`；异常发生在 output checkpoint 前，
  被 worker 泛化为 `worker_execution_failed` 并重试三次。
- Workbook compiler 把同一内容的全部 Evidence ID 拼入一个 cell；目标 Brief 单条内容
  引用 21 个 ID，超过 strict Workbook cell 的 500 字符门禁。

## 范围

1. generation pipeline 在 output service 边界传递确定性 JSON payload，同时保留 typed
   Plan 给后续 QA。
2. Workbook Evidence ID 按 500 字符 cell budget 确定性分组；完整保留顺序和引用，
   不提高 contract 上限。
3. 增加失败于旧实现的 pipeline payload 与 21-Evidence workbook regression tests。
4. 重建 generation worker，并验证 focused/broad、真实 queue/runtime 与 Browser 状态。

## 非范围

- 不修改 HTTP API、数据库 Schema、Frontend、Provider、Evidence/Preflight contract。
- 不手工改写或重放失败任务，不自动创建会扣费的新任务。
- 不截断、抽样、压缩或伪造 Evidence ID，不放宽 500 字符 cell 门禁。

## 成功标准

- RED：PPT pipeline output payload 不是 `dict`；21-Evidence workbook 编译失败。
- GREEN：两个回归均通过，所有 Evidence ID 可从分组 cell 无损还原。
- Runtime：generation worker healthy，focused/broad tests 通过；旧失败任务保持审计事实。
- Git：只暂存本任务 5 个 owned 文件，一个 conventional commit 推送到 `origin/main`。

## 交付结果

- RED 为 `2 failed`：PPT output payload 类型错误；21-Evidence workbook 在旧 500 字符
  拼接检查处失败。GREEN runtime file 为 `7 passed`。
- Generation/Outbox/Renderer/QA/Workflow 相关回归 `182 passed`；Backend full
  `610 passed, 7 skipped`；Ruff `381 files` clean。
- 真实冻结 Brief 无数据库写入 probe：PPTX 为 5 页、21 Evidence 的 strict payload；
  XLSX 为 1 Sheet、12 rows、21 Evidence，最长引用 cell 468 字符，真实 renderer
  生成 8,092-byte 临时文件后清理。
- Worker、Backend、PPT Renderer、LibreOffice healthy，generation queue 深度 `0`。
  旧失败任务未重放；需由用户手工创建新任务完成积分受控的最终文件生成。
