# P5-004 Deck Draft、逐页编辑、Skill 与 Preflight

- 状态：`BLOCKED`
- Depends on：`P5-003`
- 来源：PRD FR-201～FR-208、来源模式、Deck Draft 状态机
- 建议 commit：`feat(deck): add versioned draft and generation handoff`

## 目标

把任一成功 assistant 消息转换为严格、可编辑、可确认的 `deck-brief.v1`，保存不可变
revision，并复用现有 Preflight、任务、积分、Renderer 与 QA 创建 PPTX。

## 交付范围

- `deck-brief.v1` Schema、Deck Draft/revision/checksum/status 与 additive migration。
- 从成功 assistant 消息创建 Draft；收集主题、受众、页数、语言、风格和来源模式。
- 逐页增删、复制、排序、编辑、讲者备注、视觉建议和单页重新整理。
- 显式 Skill 选择与建议；新增并固化 `ppt.knowledge-education.v1`，保留销售汇报 Skill。
- 灵感、资料、混合 provenance；资料必须 owner-scoped、ready/valid、版本冻结。
- confirm -> Deck Preflight -> resolution/ready -> 现有 generation task/credits/QA。
- 同一权威 generation 状态投影到会话、首页最近任务和任务页。

## RED 与实施顺序

1. Schema/provenance/revision/checksum/owner/state transition tests 先 RED。
2. Outline Director strict generation/一次 repair/失败不建 Draft contract 先 RED。
3. Preflight/Evidence/Skill/template/model/credit snapshot 与 generation handoff 先 RED。
4. Deck editor UI/reorder/save/confirm/stale revision/error tests 先 RED。
5. focused GREEN 后运行旧 Brief/Preflight/Generation/PPT suites 和真实浏览器流程。

## 验收标准

- assistant 成功消息可创建 Draft；partial/failed 消息不得冒充成功来源。
- 每次保存新 revision/checksum，confirmed revision 不原地覆盖；编辑后重跑 Preflight。
- `agnes_inference`、用户输入和 source Evidence 可区分；未知单位/冲突继续阻断。
- Skill 由用户确认；系统建议不静默替代用户选择。
- 同一幂等键只创建一个 generation task/reserve；状态来自现有 MySQL state machine。
- 旧 Structured Brief PPTX/XLSX 生成与下载行为不变。

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/decks tests/skills tests/preflight tests/generation -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check app tests alembic
.venv\Scripts\ruff.exe format --check app tests alembic
cd ..
cd frontend
npm run test -- deck
npm run test
npm run build
cd ..
docker compose config --quiet
git diff --check
```

## 证据边界

- Focused：Schema/revision/provenance/state/owner/preflight/idempotency/credit。
- Broad：旧 Brief/Preflight/Generation/Renderer regression + full suites。
- Security：跨用户 Draft/source message/Evidence、Prompt injection、stale revision、
  high-risk confirm、正文日志隔离。
- Provider：Mock 不替代真实 Outline Director；真实 Agnes 只用获授权或完全合成输入，
  结果必须过 strict Schema，不记录正文。
- Office/WPS：可用脱敏合成 Draft 生成 PPTX 做机器/LibreOffice回归；此任务不把该证据
  冒充最终 P5-008 PowerPoint/WPS Gate。

## 非目标与回滚

- 不建设 WYSIWYG PPT 编辑器、不实现图片/视频 Provider 任务。
- 不允许任意 Skill、自由 Markdown 或 chat 正文直接进入 Renderer。
- 回滚 feature 路由和 additive contract，不覆盖历史 Draft/revision/task。
