# P5-007 Agnes 视频资产与兼容性 Gate

- 状态：`BLOCKED`
- Depends on：`P5-006`
- 来源：PRD FR-501～FR-505、Video 2.0 模型策略
- 建议 commit：`feat(media): add gated agnes video assets`

## 目标

为用户明确选择的页面创建 Agnes Video 异步任务，保存独立可追踪资产；视频内嵌只有在
Microsoft PowerPoint 与 WPS 真实兼容 Gate 通过时才开放，否则使用海报帧加独立视频交付。

## 交付范围

- 文生视频首期 contract；图生视频若需要公共 URL，capability 保持关闭。
- queued/submitted/running/succeeded/failed/provider_uncertain/cancelled 状态与真实
  Provider ID 轮询、Retry-After、timeout、cancel。
- 每页显式创建、预览、下载、重新生成和不可变 asset/ledger。
- 视频 MIME/container/codec/容量/hash/可达性/内容策略，海报帧与 owner storage。
- 条件式 PPTX media relationship/encoding/package contract 与 feature flag。
- PowerPoint/WPS 无修复、可播放、重开后可播放的兼容矩阵；失败时固定独立附件 fallback。

## RED 与实施顺序

1. Provider submit/poll/cancel/uncertain/idempotency tests 先 RED。
2. 非用户选择页面、自动全页、public URL 和静默 retry 必须 RED 拒绝。
3. Asset validation/poster/fallback/UI tests 先 RED。
4. Renderer package/media relationship tests 先 RED；默认 embedding capability 为 false。
5. 真实 Agnes Video Contract 成功后，分别用 PowerPoint/WPS 执行嵌入 Gate；未双通过不
   启用 capability。

## 验收标准

- 只为明确选择页面创建一次任务；进度来自 Provider/服务端，不使用前端假进度。
- timeout/断线/结果未知进入 `provider_uncertain`，不重复提交或重复扣费。
- 视频结果即使不能内嵌，也作为 owner-scoped 独立资产可预览/下载。
- 需要公共图片 URL 的路径默认拒绝；本地资产不公开。
- 只有 PowerPoint 与 WPS 对目标 container/codec 均无修复提示且实际播放，才标记
  `ppt_video_embedding=true`；否则 PPT 使用海报帧并明确独立附件。

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/media/videos tests/providers tests/generation -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check app tests alembic
.venv\Scripts\ruff.exe format --check app tests alembic
cd ..
cd frontend
npm run test -- video
npm run test
npm run build
cd ..
cd ppt-renderer
npm test
npm run build
cd ..
docker compose config --quiet
git diff --check
```

## 证据边界

- Focused：submit/poll/cancel/state/idempotency/asset/fallback/package。
- Broad：Backend/Frontend/Renderer full、Compose、相关 Golden。
- Security：public URL disabled、owner scope、MIME/container/codec/capacity、Prompt/response
  redaction、重复计费和自动媒体生成拒绝。
- Provider：Mock 不证明 Agnes Video；真实 opt-in Contract 使用合成文本/图片并记录脱敏
  Provider ID/status，不记录 Prompt/response body。
- Office/WPS：LibreOffice/OOXML 不能证明播放；必须分别在 PowerPoint/WPS 实际打开、播放、
  保存/重开。任一失败即保持 embedding false。

## 非目标与回滚

- 不默认全页生成视频，不启用未批准公共 URL 图生视频。
- 不因单一 Office 应用成功就声明跨应用内嵌兼容。
- 回滚关闭 embedding/video capability，保留历史 asset/task/ledger 和海报帧 fallback。
