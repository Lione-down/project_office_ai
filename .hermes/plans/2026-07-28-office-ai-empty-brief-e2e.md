# Office AI 空 Structured Brief 端到端修复

## 目标

- 使用管理员已上传并完成 Evidence Manifest 的 `第一季度数据.xlsx`，从浏览器走完
  Structured Brief、Preflight、确认、PPTX/XLSX 生成、质量检查与下载，不重复上传。
- 修复真实任务 `019fa780-8b72-74b2-a258-59b52e522e17` 暴露的
  `generation_brief_content_required`，避免合法结构但没有可生成内容的 Brief 进入后续流程。

## 根因与边界

- `StructuredBrief.facts` 当前允许空数组；`validate_brief_response` 因而会接受 Provider
  repair 返回的空 `facts/inferences/must_include`，Preflight 也没有内容门禁，错误直到
  generation compiler 才暴露。
- 上传材料生成的 Brief 必须至少包含一条带 Evidence 的 file/calculation fact。该约束进入
  Pydantic/JSON Schema，使首轮生成与唯一一次 repair 都受同一合同约束。
- 不增加 Provider repair 次数，不截断 Evidence，不自动猜测单位，不修改既有失败任务，
  不降低 Preflight、质量或下载门禁。

## TDD 与验证

1. RED：新增合同回归，证明空 `facts` 当前会被接受。
2. GREEN：将 `StructuredBrief.facts` 设为 `min_length=1`，并验证生成 prompt 中的完整
   JSON Schema 包含 `minItems=1`。
3. Focused：运行 Brief contract、validation、prompting、service 测试。
4. Broad：运行 backend 全量测试、ruff、前端测试/build 与 Git/Secret 检查。
5. Runtime：用授权 XLSX 创建全新真实工作流，完成显式 blocker resolution、确认和
   PPTX/XLSX 生成；验证任务/步骤、积分、质量、下载权限、文件 hash/大小及浏览器成功页。

## 完成标准

- 新任务的 Brief 至少有一条 Evidence-backed fact。
- PPTX 与 XLSX 步骤均为成功，任务不再出现 `generation_brief_content_required`。
- 两个产物通过质量门禁且可下载到 `D:\works\codexWorks\download`。
- 验证证据写入 `docs/PROGRESS.md`，本任务仅提交并推送一个逻辑 commit。

## 2026-07-28 阻塞记录

- 原失败 generation task `019fa780-8b72-74b2-a258-59b52e522e17` 的 Brief
  `facts/inferences/must_include` 均为 0；两项 renderer 因
  `generation_brief_content_required` 失败。
- RED/GREEN 已证明并实现 `facts.minItems=1`；Brief focused 为 `39 passed`。
- 真实 workflow `019fa789-5c97-7783-9e1b-fa8aefd89ce4` 在空内容门禁后于 Brief 阶段
  fail closed；首轮/repair completion 均打满 8,192 tokens。
- 进一步把 Provider-authored facts/inferences/unresolved items 限制为 `12/6/12`，
  每项 Evidence 引用限制为 32；真实 workflow
  `019fa78f-eaac-7f14-af47-c6c56dc699fa` 仍两次打满 8,192 tokens。
- 再加入“仅生成代表性摘要、禁止枚举全部 Evidence/blocker”的 Schema 语义说明；真实
  workflow `019fa795-9fcf-71a8-8875-0c9c8f7b2fb7` 仍两次打满 8,192 tokens 并以
  `brief_schema_invalid` 失败。
- 三个诊断假设均已验证但未走通目标。按重复回归门禁停止继续叠加补丁；当前 checkout
  保持 dirty，未暂存、未 commit、未 push。下一步需要批准扩大为：
  1. 只持久化/记录脱敏后的最终 validation `loc:type` 分类，以分辨 JSON 截断、数组超限
     或 snapshot/evidence mismatch；或
  2. 把单次 10,465 Evidence 的 Brief 生成改为确定性分阶段聚合，再由 Agnes 生成最终
     strict Structured Brief。
- Chrome 扩展未启用本地 file URL 访问，重复上传被扩展拒绝；真实任务复用了页面中已完成
  安全解析、Manifest valid 且与授权文件同名同大小的既有资产。未产生 generation 积分
  结算，页面余额保持 10,000。

## 2026-07-28 脱敏诊断与截断修复

- 用户确认不再上传材料，继续复用管理员已上传的 `第一季度数据.xlsx`；若 Preflight 要求
  确认单位，全部显式选择 `数量`。
- 新增脱敏 validation 诊断，只记录 Brief group、attempt、`finish_reason`、token 数和
  bounded `loc:type` hints，不记录 Prompt、Provider response 或文件内容。真实任务
  `019fa7ab-e2e0-7f99-be3a-a77ece77242b` 的首轮明确为
  `finish_reason=length / completion_tokens=8192 / hints=json:invalid`，证明失败是完整
  JSON 返回前被截断，而不是数组上限或 Evidence allowlist 校验。
- Prompt 新增显式总输出预算和代表性摘要规则；Brief 合同收紧为最多 `8` facts、`4`
  inferences、`4` semantic unresolved items，每项正文最多 `512` 字符、Evidence refs
  最多 `8`。`numeric_unit_unknown/unit_unknown` 不复制进 Brief unresolved items，
  继续由 Preflight 根据实际引用 Evidence fail closed。
- 若首轮 `finish_reason=length`，唯一 repair 不再回送 8,192-token 的截断响应，而是在
  同一完整 Evidence Context 上从头生成受预算约束的 JSON；非截断 Schema 错误仍保留
  原有一次修复行为。
- Brief focused：`41 passed`；backend broad：`614 passed, 7 skipped`；Ruff
  check/format 全部通过。Frontend：`23` files / `72 passed`，production build 通过。
- 为加载镜像内 `/app/app` 的新代码，已重建 backend、workflow-worker 和
  generation-worker。重建后原 Chrome Session 失效，runtime bootstrap 登录变量为空；
  未重置密码、未绕过鉴权。待用户在 Chrome 手动重新登录后，继续创建真实任务、单位全部
  选 `数量`、确认生成、质量检查与下载验证。

## 2026-07-28 真实流程闭环

- 用户重新登录后，真实 combined workflow
  `019fa7bd-aa3f-76c1-8cfa-0b9569b03559` 的 Brief 首轮成功；Preflight 的 16 个单位
  blocker 全部显式选择 `数量（个/件）`。generation task
  `019fa7bf-7ea8-7ab3-aacd-d00759fe3942` 中 XLSX 一次通过质量门禁并结算 800，PPTX
  暴露独立 renderer 合同错误，因此任务为 `partial_success`。
- 第一处 PPT 根因是 Python compiler 原样传递重复 `evidence_ids`，而 TypeScript renderer
  JSON Schema 要求每个元素的引用 `uniqueItems=true`。RED 回归证明重复引用存在；compiler
  以稳定顺序去重后，focused generation runtime `8 passed`，renderer 从 HTTP 422 变为
  HTTP 200。
- PPT-only workflow `019fa7c5-40e0-71e1-982e-494cf2897538` 的 36 个单位同样全部选择
  `数量（个/件）`。generation task `019fa7c6-dcbc-762b-834e-2d84a68761cf` 已成功
  renderer 并持久化 107,783-byte PPTX，但在 LibreOffice 调用前失败，结算 0 且预留的
  800 已完整释放。
- 第二处 PPT 根因是 pipeline 给 `PresentationQualityService` 传入 Pydantic
  `PresentationPlan`，而质量服务入口严格接收 renderer payload `dict`。RED 测试稳定复现；
  pipeline 改为让 renderer 与 quality 复用同一个 `_output_payload` 后，generation runtime
  `8 passed`、presentation quality `52 passed`。
- 修复镜像重建后，新 PPT-only workflow
  `019fa7cc-7d45-73ae-bf35-04f3e9070dab` 首轮生成 Brief 成功；22 个单位全部显式选择
  `数量（个/件）`。generation task `019fa7cf-041d-73ce-ac3d-eb146ffe568a` 一次生成
  成功，PPTX 质量状态 `passed`、`download_allowed=true`，结算 800。
- 最终 XLSX/PPTX 分别下载到 `D:\works\codexWorks\download`。下载副本 SHA-256 与数据库
  质量门禁摘要完全一致：XLSX
  `dc1777ccd095c973059e4e14d8f7839b5a8a141df8cc43fd83a3d8d75b20ec81`
  （9,878 bytes、1 个工作表），PPTX
  `44c5737705ec9856f29cb947d3298fa12df7a64b124e7f6d5d9fb36284b3b01d`
  （105,823 bytes、4 页）。两份 OOXML ZIP 关键结构均存在。
- 三次真实 Brief Provider call 均首轮成功并标记 `is_redacted=1`；失败 PPT-only 任务未
  结算且已释放预留，最终成功输出合计实际结算 1,600。
