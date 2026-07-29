# Office AI Agnes 对话与 PPT 创作中心任务索引

> 批准 PRD：[`../../../docs/prd/2026-07-29-office-ai-agnes-chat-ppt-studio-prd.md`](../../../docs/prd/2026-07-29-office-ai-agnes-chat-ppt-studio-prd.md)
> 执行计划：[`../2026-07-29-office-ai-agnes-chat-ppt-studio-post-alpha.md`](../2026-07-29-office-ai-agnes-chat-ppt-studio-post-alpha.md)

## 执行规则

- 同一时间只有一个 `READY`，并且它的全部 dependency 必须为 `DONE`。
- 每个任务在独立会话先创建目标，只完成该任务，完成验证、精确暂存、单一 commit 和 push
  后再创建下一会话。
- 每个实现任务必须执行 RED -> GREEN -> focused -> broad/security；涉及 Provider、
  MySQL/Redis、Renderer、Office/WPS 时分别记录真实证据，Mock/offline 不得替代。
- 不提交 `.env` 或其他环境文件、Secret、Prompt、Provider response、用户文件、私有材料
  或未脱敏输出；根 `.env` 仅按授权最小注入临时进程且不得回显。
- 用户已有 `.playwright-cli/`、`design-system/` 和旧 `docs/ui-mockups/` 保持未修改、
  未暂存。
- 未经用户明确要求，不使用 subagent 或并行代理。

## 顺序裁决

PRD 第 18 节原建议把首页最近任务放在设计合同之前；第 20 节又要求开发前同步正式合同。
正式顺序将合同 Gate 提前为 `P5-001`，将最近任务完整后移为 `P5-002`。其余任务保持
`P5-003`～`P5-008`。

## 任务状态

| ID | 任务 | Depends on | 状态 | Gate |
|---|---|---|---|---|
| `P5-000` | Post-Alpha 执行计划基线 | Alpha Complete | `DONE` | Plan |
| `P5-001` | 技术、API、Data、Security 与 Environment 合同 | `P5-000` | `DONE` | Contract |
| `P5-002` | 首页最近任务真实展示 | `P5-001` | `DONE` | Recent Tasks |
| `P5-003` | 双模型会话、SSE 与历史 | `P5-002` | `DONE` | Chat |
| `P5-004` | Deck Draft、逐页编辑、Skill 与 Preflight | `P5-003` | `DONE` | Deck |
| `P5-005` | 模板目录、缩略图与版本快照 | `P5-004` | `DONE` | Template |
| `P5-006` | Agnes 图片资产与 PPT 视觉集成 | `P5-005` | `DONE` | Image |
| `P5-007` | Agnes 视频资产与兼容性 Gate | `P5-006` | `READY` | Video |
| `P5-008` | 端到端 Golden、安全、Office/WPS 与发布 Gate | `P5-007` | `BLOCKED` | Release |

## 任务文档

- [P5-000 Post-Alpha 执行计划基线](P5-000-post-alpha-plan-baseline.md)
- [P5-001 技术、API、Data、Security 与 Environment 合同](P5-001-contract-baseline.md)
- [P5-002 首页最近任务真实展示](P5-002-home-recent-tasks.md)
- [P5-003 双模型会话、SSE 与历史](P5-003-dual-model-chat-sse.md)
- [P5-004 Deck Draft、逐页编辑、Skill 与 Preflight](P5-004-deck-draft-preflight.md)
- [P5-005 模板目录、缩略图与版本快照](P5-005-template-catalog.md)
- [P5-006 Agnes 图片资产与 PPT 视觉集成](P5-006-image-assets-ppt.md)
- [P5-007 Agnes 视频资产与兼容性 Gate](P5-007-video-assets-compatibility.md)
- [P5-008 端到端 Golden、安全、Office/WPS 与发布 Gate](P5-008-release-gate.md)

## PRD 覆盖

- 旧流程/双模型/会话/SSE：P5-001、P5-003、P5-008。
- Deck Draft/Skill/Preflight/现有任务：P5-001、P5-004、P5-008。
- 模板：P5-001、P5-005、P5-008。
- 图片：P5-001、P5-006、P5-008。
- 视频：P5-001、P5-007、P5-008。
- 首页最近任务：P5-002、P5-008。
- Evidence、owner scope、Secret、内容治理、质量和兼容性：所有实现任务持续回归，
  P5-008 汇总发布结论。
