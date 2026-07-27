# Post-Alpha Preflight 引用范围与单位解决

## 背景与根因

- 当前真实 Brief 只引用 17 条 Evidence，其中 9 条存在单位未知。
- Preflight 旧实现扫描整份 Evidence Manifest，将 5,193 条未被本次 Brief 使用的单位问题
  也作为阻断项。
- 同一个 Evidence 又分别以 `numeric_unit_unknown` 和 `unit_unknown` 进入结果，最终显示
  10,386 条重复阻断。
- 页面只展示阻断文本，没有单位输入；后端显式 `assign_unit` resolution 仅允许匹配
  `StructuredBrief.unresolved_items`，无法解决 Manifest/Evidence blocker。

## 目标

1. Preflight 只校验当前 Structured Brief 实际引用的 Evidence。
2. Manifest 与 Evidence 的同义单位问题统一为 `unit_unknown`，同一 Evidence 只计一次。
3. 单位阻断显示 Sheet/单元格等来源位置，用户可显式选择单位并保存为新 Revision。
4. Resolution 只允许匹配当前 Preflight blocker，写入不可变 `source_snapshot`，并进入
   generation task input snapshot；不得改写原始 Evidence 或猜测单位。

## 实施范围

### Backend

- 从 `facts`、`inferences`、`output_plan`、`must_include`、`must_exclude` 与
  `unresolved_items` 收集本次 Brief 引用的 Evidence ID。
- Manifest/Evidence findings 仅保留引用集合内的条目；将
  `numeric_unit_unknown -> unit_unknown`、
  `ocr_numeric_low_confidence -> numeric_low_confidence`。
- 单位冲突消息加入安全、可追踪的位置标签，不返回文件正文或非必要原始值。
- `PATCH /briefs/{brief_id}` 的 resolution 校验改为匹配当前 Preflight snapshot；
  `assign_unit` 仅接受受支持的 canonical unit。
- generation task 的 Brief input snapshot 固化已确认 resolutions。

### Frontend

- 单位阻断逐条显示来源位置与 canonical unit 选择框。
- 未完成全部单位选择时不得保存 resolution，也不得确认生成。
- 保存目标、受众和单位 resolution 时创建新 Revision，重新执行 Preflight。
- 非单位 blocker 继续按现有安全中文消息显示。

## 不在范围

- 不修改或重新解析用户文件，不改写既有 Evidence Manifest。
- 不根据数值、列名或业务语境自动猜测单位。
- 不降低 OCR、来源、口径、Skill、模板、模型能力或积分门禁。
- 不修改历史 Brief、历史任务、Provider Prompt 或 Agnes response。

## RED / GREEN 验收

1. 一个被引用和一个未引用的单位未知 Evidence：Preflight 只返回一个
   `unit_unknown` blocker。
2. 同一 Evidence 同时来自 Manifest blocker 与 Evidence warning：结果仍只有一条。
3. 单位 blocker 包含可追踪位置；合法 `assign_unit` 创建新 Revision 并清除对应阻断。
4. 非当前 blocker、非法 unit 或伪造 Evidence ID fail closed。
5. Frontend 展示单位选择，未选不提交；选择后 PATCH 携带显式 resolution 并刷新到新
   Revision。
6. generation task Brief input snapshot 包含已确认 resolution，原始 Evidence 不变。

## 验证命令

```powershell
docker compose run --rm backend pytest backend/tests/preflight -q
docker compose run --rm backend pytest backend/tests/generation -q
docker compose run --rm frontend npm run test -- --run src/views/brief/confirm.test.ts
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm backend ruff check backend/app backend/tests
docker compose run --rm backend ruff format --check backend/app backend/tests
```

## Runtime 与交付

- 重建 Backend、workflow worker 与 Frontend 后，用当前 Brief 只读复核阻断数从 10,386
  降为实际引用问题数。
- 用真实浏览器验证位置提示、单位选择、Revision 保存、Preflight 刷新和确认门禁。
- 更新 `docs/PLAN.md`、`docs/API.md`、`docs/PROGRESS.md`、`docs/SECURITY.md` 与
  `pitfalls.md`；精确暂存，一个 `fix(preflight): ...` commit 并 push。
