# P5-000 Post-Alpha 执行计划基线

- 状态：`DONE`
- Depends on：Office AI Internal Alpha Complete、批准 PRD `v1.0`
- 来源：PRD 第 18、20 节与项目单任务交付规则
- 建议 commit：`docs(plan): establish agnes chat ppt studio delivery baseline`

## 目标

把批准 PRD 转换为正式、dependency-ordered、可逐会话交付的 Post-Alpha 执行计划，并让
`P5-001` 成为唯一 `READY` 任务；本任务不实现业务代码或提前冻结正式接口。

## 交付范围

- 新增 Post-Alpha 总执行计划、任务索引和 `P5-000`～`P5-008` 任务卡。
- 裁决 PRD 第 18 节与第 20 节顺序冲突：先合同，后最近任务和业务代码。
- 每张任务卡定义目标、范围、验收、RED/focused/broad/security、真实
  Provider/Office/WPS 证据边界、非目标、依赖与建议 commit。
- 更新 `docs/PLAN.md` 的计划入口和 `docs/PROGRESS.md` 的状态/唯一下一任务。

## 验收标准

- 任务 ID 连续、索引链接有效、依赖形成单链，只有 `P5-001` 为 `READY`。
- 计划覆盖旧功能、双模型、SSE、Deck Draft、模板、图片、视频、最近任务、
  Evidence/安全/质量边界。
- `P5-001` 明确承担正式技术/API/Data/Security/Environment 合同，不在 P5-000
  伪造合同已批准。
- 无业务代码、migration、正式 API/Data/Security/Environment 合同变更。
- 用户未跟踪 UI 文件保持未修改、未暂存。

## 验证

```powershell
$taskRoot = '.hermes/plans/office-ai-agnes-chat-ppt-studio-tasks'
# 只读断言：P5-000～P5-008 连续、索引链接有效、仅 P5-001 READY、章节和 UTF-8 完整
git diff --check
git check-ignore -v .env
git status --short
git diff --cached --name-only
```

若仓库没有专用 validator，本任务使用只读脚本断言文件数、链接、状态、dependency、
必需章节、UTF-8 和禁用占位词；不为一次验证新增产品代码。

## 证据边界

- RED：计划一致性断言在文件创建前应因缺少索引/任务卡失败。
- Focused：计划结构、链接、唯一 READY、PRD 覆盖、UTF-8。
- Broad：`git diff --check` 与项目文档一致性；本任务不需要产品 test suite。
- Security：ignore/staged 路径与敏感文件名检查；不读取环境文件内容。
- Provider/Office/WPS：本任务不调用 Provider、不生成 Office 文件，因此不产生对应证据。

## 非范围与回滚

- 不实现首页、会话、SSE、Deck Draft、模板、媒体或 Renderer。
- 不新增表、API、环境变量或正式安全合同；这些是 P5-001 的唯一交付。
- 回滚只恢复本任务拥有的计划/进度链接，不触碰用户未跟踪文件或现有产品实现。
