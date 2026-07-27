# Office AI Structured Brief Schema repair 修复

- 日期：2026-07-27
- 类型：Post-Alpha 单任务修复
- 基线：`9ad39a6`
- 用户目标：修复 Agnes 成功响应后仍连续出现
  `brief_schema_invalid / Structured Brief Schema 无效`。

## Runtime 证据与根因

- 最新 durable workflow task `019fa32b-9a5b-78a6-80a7-8c398a4dc579` 已按预期记录
  `failed / brief_failed / 100% / brief_schema_invalid`，证明异步任务与失败留痕有效。
- 该任务的 Agnes attempt 1/2 均成功返回，分别耗时约 47 秒与 90 秒；应用层均记录
  `schema_invalid`。数据库中最近 3 组、共 6 次成功 Provider 响应全部得到同一结论，
  问题可稳定复现于 Provider response -> strict validation 边界。
- 当前 `generation_messages` 只传递 17 个顶层字段名，没有传递
  `StructuredBrief` 的嵌套对象、required、Literal、长度、`extra=forbid` 与 validator
  约束。模型无法仅凭字段名推导完整 contract。
- 当前 repair 只给出通用“Schema/snapshot/evidence validation failed”，没有提供具体
  错误路径与类型；在 `temperature=0` 下无法知道应该修复哪一层。
- Provider 原始 response、Prompt、材料正文与 Credential 按安全设计均未落库，因此本次
  根因依据 runtime 状态、token/latency metadata 与代码数据流确认，不读取或回显正文。

## 修复设计

1. 初次 generation user payload 增加紧凑的
   `StructuredBrief.model_json_schema()`，明确完整 nested contract。
2. `BriefValidationError` 增加只供同一次 repair 使用的 `repair_hints`：
   - Pydantic 只保留 `loc + type`；
   - JSON decode 只标记 `json_invalid`；
   - Snapshot 只标记不匹配的字段名；
   - Evidence 只标记 unknown reference，不携带 evidence/raw value。
3. repair request 携带上述 hints 和完整 Schema；原始无效 JSON 只回传给同一个 Agnes
   conversation，不写入数据库、日志或用户错误响应。
4. strict Pydantic、authoritative snapshot、Evidence allowlist、一次 repair、timeout/
   `provider_uncertain`、Provider capability 和审计边界全部保持不变。

## TDD 验收

### RED

- generation prompt 包含完整 Schema，且嵌套 `required`/`additionalProperties=false`
  可验证。
- invalid nested payload 产生稳定、脱敏、无字段值的 `loc:type` hints。
- repair prompt 包含 hints，并且 service 把第一次 validation hints 传给第二次调用。
- hints 有数量/长度上限，不能成为 Prompt、日志或错误响应的数据泄露通道。

### GREEN 与验证

1. Backend Brief focused pytest 与 Ruff。
2. Backend full pytest。
3. 使用 Mock payload 验证一次 repair 成功、二次无效仍 fail closed。
4. 重建/recreate Backend 与 workflow-worker，验证 health。
5. 在不打印 Prompt/response/material/Secret 的前提下，用用户下一次真实提交验证
   `awaiting_confirmation` 或记录新的稳定失败分类。
6. `pip check`、`pip-audit`、`git diff --check`、敏感文件与精确暂存检查。

## 文档与交付

- 同步 `docs/PLAN.md`、`docs/API.md`、`docs/SECURITY.md`、`docs/PROGRESS.md` 与
  `pitfalls.md`。
- 一个逻辑 commit：`fix(brief): provide schema-aware repair guidance`，验证后 push
  `origin/main`。

## 明确不变

- 不降低或自动补写 Structured Brief Schema。
- 不持久化 Provider 原始 response、Prompt、validation input 或材料正文。
- 不启用已知不兼容的 Agnes native `response_format`。
- 不自动重试已失败 workflow task；新请求使用新 task，旧失败记录保留。
- 不修改/暂存 `.env`、private workbook、`.playwright-cli/`、`design-system/`、旧
  `docs/ui-mockups/` 或 ignored `output/`。

## 完成记录

- RED：`4 failed, 17 passed`；GREEN Brief focused：`37 passed`。
- Backend full：`600 passed, 7 skipped`；Ruff 377 files clean。
- 新增 real Agnes synthetic Structured Brief Contract 显式 opt-in：
  `1 passed in 5.64s`；未读取用户材料，未输出 Prompt/response/Credential。
- `pip check` 与 `pip-audit` 通过，无已知漏洞。
- Backend image 重建，Backend/workflow-worker 均 healthy，
  `9999/health/ready=ready`。
- 用户旧失败 task 保留且不自动重放；生产修复只对下一次新任务生效。
