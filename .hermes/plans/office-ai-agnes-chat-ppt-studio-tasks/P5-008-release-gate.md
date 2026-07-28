# P5-008 端到端 Golden、安全、Office/WPS 与发布 Gate

- 状态：`BLOCKED`
- Depends on：`P5-007`
- 来源：PRD 第 3、17、20 节
- 建议 commit：`chore(release): complete agnes chat ppt studio gate`

## 目标

以可重复自动化、真实双模型/媒体 Contract、完整 Golden、安全、恢复、PowerPoint/WPS
和浏览器证据关闭整个 PRD；任何 hard gate 未通过时保持阻塞，不用文档或 Mock 冒充完成。

## 交付范围

- PRD FR/验收追踪矩阵与 Post-Alpha release report。
- 从新对话 -> SSE -> Deck Draft -> Template -> 可选 Image/Video -> Preflight ->
  generation -> QA -> 下载的真实端到端。
- 灵感、资料、混合来源和旧文件驱动流程回归。
- 双模型、取消/断线、SSE、幂等、provider uncertain、Redis/MySQL 恢复和积分闭环。
- 图片 PPT Golden；视频 embedding/fallback 兼容矩阵。
- Security、dependency、Secret、Git history/staged、owner isolation 和内容治理 Gate。
- Desktop/mobile 浏览器与最终 PowerPoint/WPS 人工验收交接。

## RED 与实施顺序

1. Release contract test 先要求报告逐项覆盖 PRD、真实证据和声明边界；报告缺失时观察 RED。
2. 从干净 runtime 执行 migration/health/focused/full/security/Golden/recovery。
3. 分别执行真实 Agnes 2.5、2.0、Image、Video opt-in Contract，不输出正文或 Secret。
4. 对可下载 PPTX 在 PowerPoint/WPS 实际打开；视频内嵌按 P5-007 Gate 播放/重开。
5. 完成真实浏览器功能/响应式/键盘/console/network 检查，并保留用户最终视觉验收边界。
6. 全部 hard gate 通过后写 release report，让 contract test GREEN。

## 验收标准

- PRD 第 17 节功能、安全、质量/兼容项逐条有当前证据或明确阻塞。
- 两个文本模型真实 stream/stop；Image/Video 真实 contract 与 capability 声明一致。
- 旧 Alpha focused/broad/security/golden 全部通过且可观察行为不回退。
- 新/旧流程任务、积分、不可变资产、owner scope、日志脱敏和恢复路径通过。
- 图片 PPTX 在 PowerPoint/WPS 无修复且视觉合格；视频仅按双应用 Gate 声明内嵌。
- Git 不跟踪或暂存 `.env`、Secret、Prompt、Provider response、用户文件或私有材料。
- `docs/PLAN.md`、`docs/PROGRESS.md`、任务卡、实现、测试、commit/push 状态一致。

## 验证

```powershell
docker compose config --quiet
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm ppt-renderer npm test
docker compose run --rm ppt-renderer npm run build
docker compose run --rm backend python -m app.utils.golden_regression
git check-ignore -v .env
git diff --check
git diff --cached --name-only
git status --short
```

真实 Provider、failure drill 和 Office/WPS 命令使用 P5-001/P5-007 冻结的显式 opt-in，
不得把 Secret 参数写入任务卡、日志或报告。

## 证据边界

- Focused/Broad：所有新模块和 Alpha stable suites。
- Security：跨用户、XSS、危险 URL、Prompt/tool injection、public file exposure、
  staged/history Secret、重复计费。
- Runtime：真实 Compose/MySQL/Redis/worker/Renderer/LibreOffice；离线合同不替代。
- Provider：2.5、2.0、Image、Video 分项真实证据；Mock 只列为测试层。
- Office/WPS：PowerPoint/WPS 实际交互证据与机器证据分列；最终视觉偏好由用户整体验收。

## 非目标与回滚

- 不在发布 Gate 顺手增加 Web 搜索、用户模板、WYSIWYG、团队协作或生产部署。
- 任一 Gate 失败保持 P5-008 未完成并保留现场，不做 destructive reset。
- 回滚使用 feature flag、不可变版本和补偿流水；不删除审计、任务、资产或账务事实。
