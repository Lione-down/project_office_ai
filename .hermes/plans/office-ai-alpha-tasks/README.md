# Office AI Alpha 任务索引

> 范围基线：[`../2026-07-22_000414-office-ai-alpha.md`](../2026-07-22_000414-office-ai-alpha.md)。本目录只拆分执行单元，不修改基线中的产品边界、技术选型或完成定义。

## 执行规则

- 同一时间只启动一个 dependency-ready 任务；默认从 `T1-001` 开始，按编号推进。
- `READY` 表示前置条件已满足；`BLOCKED` 表示必须等待 `Depends on` 中的任务通过验收。
- 每个任务完成后先运行该任务的 focused verification，再运行任务要求的 broad verification。
- 每个任务结束时同步更新 `docs/PROGRESS.md`；范围或接口变化同步更新 `docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md` 或 `docs/SECURITY.md`。
- 每个任务只产生一个逻辑 commit，格式使用 `type(scope): subject`；只暂存本任务拥有的路径。
- 不提交或推送任何环境配置文件，包括 `.env`、`.env.*`、`*.env`、`*.env.*`、`*.env.example` 及 `.ene` 误拼变体；即使只含示例值也不得进入 Git。API Key、Token、证书、私钥、用户文件和未脱敏黄金材料同样禁止提交。
- 未经用户明确要求，不使用 subagent 或并行代理。

## 推荐方向

直接沿用总计划的 `4 Week × 5 Day` 边界，拆成 20 个顺序任务。这样不重新设计已批准范围，每个任务都有明确交付、验证和 commit 边界，每周结束形成一个可独立保留的可用 Gate。

最小替代方案是只建立 4 个周级任务，但每个任务会同时横跨多个服务和十余个文件域，不利于逐项验证、回滚和进度同步，因此不采用。

## UI V1 实施基线

- `docs/ui-v1/README.md` 及其 14 张用户端、后台管理 UI 图已确认为 `APPROVED-V1`，是 Alpha 前端开发的视觉与交互基线。
- `T4-001` 负责按 UI V1 落地用户流程、后台页面壳、路由、共用状态与基础组件。
- `T4-002` 负责按 UI V1 落地 Credential Reveal、密码重置、用户状态变更、积分调整、资产删除和审计日志等敏感操作闭环。
- UI V1 不新增任务、不改变依赖关系或初始状态，也不扩大 Alpha 功能范围；`T1-001` 仍是唯一初始 `READY` 任务。
- 开发时如 UI 图与功能、安全或权限要求冲突，以总计划和任务验收标准为准，并在 `docs/PROGRESS.md` 记录差异及处理结果。

## 任务顺序

| ID | 任务 | Depends on | 初始状态 | 阶段 Gate |
|---|---|---|---|---|
| `T1-001` | 工程与文档基线 | 无 | `READY` | |
| `T1-002` | FastAPI、Vue 与数据库骨架 | `T1-001` | `BLOCKED` | |
| `T1-003` | 用户、Session 与邀请码 | `T1-002` | `BLOCKED` | |
| `T1-004` | Provider、Credential 与模型后台 | `T1-003` | `BLOCKED` | |
| `T1-005` | 项目与资产上传 | `T1-004` | `DONE` | Week 1 |
| `T2-001` | 文件扫描与解析沙箱 | `T1-005` | `DONE` | |
| `T2-002` | OCR 与 Evidence Manifest | `T2-001` | `DONE` | |
| `T2-003` | 术语库与证据标准化 | `T2-002` | `DONE` | |
| `T2-004` | Skills 与 Agnes Structured Brief | `T2-003` | `DONE` | |
| `T2-005` | Brief 确认与 Preflight | `T2-004` | `DONE` | Week 2 |
| `T3-001` | 任务、Outbox 与积分事务 | `T2-005` | `DONE` | |
| `T3-002` | PPT Renderer 与系统模板 | `T3-001` | `DONE` | |
| `T3-003` | PPT QA | `T3-002` | `DONE` | |
| `T3-004` | Excel Renderer 与系统模板 | `T3-003` | `DONE` | |
| `T3-005` | Excel QA 与组合任务 | `T3-004` | `DONE` | Week 3 |
| `T4-001` | 用户流程与管理后台功能壳 | `T3-005` | `DONE` | |
| `T4-002` | 管理员最高权限与审计 | `T4-001` | `DONE` | |
| `T4-003` | 黄金数据回归 | `T4-002` | `DONE` | |
| `T4-004` | Office/WPS 与故障演练 | `T4-003` | `BLOCKED` | |
| `T4-005` | 安全检查与 Alpha 封版 | `T4-004` | `BLOCKED` | Week 4 / Alpha |

## 阶段 Gate

- Week 1：用户可注册登录和管理资产；管理员可配置 Agnes Credential 与模型。
- Week 2：用户可从材料得到带证据的 Structured Brief，并完成修改、冲突处理和确认。
- Week 3：同一份材料可异步生成 PPTX 与 XLSX，通过基础质量门禁并下载。
- Week 4：Windows 本地冷启动、真实 Agnes、黄金回归、Microsoft Office/WPS 人工验收和敏感信息检查全部完成。

## 外部前置条件

- `T2-004` 前：通过本地未跟踪配置或管理后台提供真实 Agnes API Key；不得写入计划、聊天记录或 Git。
- `T4-003` 前：原计划要求 10 组材料；用户于 `2026-07-26` 明确确认没有更多材料，批准将
  1 组拥有使用权的 XLSX/PPTX 配对材料生成脱敏副本并作为 `1/10 pilot` 执行。
- `T4-004` 前：本机可用 Microsoft Office 与 WPS、真实 Agnes 测试配置及 Docker
  故障演练 runtime。当前 Microsoft Office 16.0 已验证；Docker Desktop 已安装但
  Windows/WSL2 待重启；真实 Agnes 基础文本请求为 200，但 Structured Output Contract
  因上游 grammar backend 返回 400；用户明确不安装 WPS。任务继续 `BLOCKED`。

## 最脆弱假设

本拆分原假设真实 Agnes Key 和 10 组脱敏销售样本能在 Week 2 前到位，且 Week 4 可使用
Microsoft Office 与 WPS。实际仅有 1 组用户授权材料，因此 T4-003 只能证明该 pilot 的
确定性和回归机制，不能把 Agnes 真实兼容、10 组内容多样性或 Office/WPS 可交付性标记
为通过。

## 任务文档

- [T1-001 工程与文档基线](T1-001-engineering-documentation-baseline.md)
- [T1-002 FastAPI、Vue 与数据库骨架](T1-002-application-foundation.md)
- [T1-003 用户、Session 与邀请码](T1-003-authentication-and-invites.md)
- [T1-004 Provider、Credential 与模型后台](T1-004-provider-model-registry.md)
- [T1-005 项目与资产上传](T1-005-project-and-asset-upload.md)
- [T2-001 文件扫描与解析沙箱](T2-001-file-safety-and-parsing.md)
- [T2-002 OCR 与 Evidence Manifest](T2-002-ocr-evidence-manifest.md)
- [T2-003 术语库与证据标准化](T2-003-terminology-normalization.md)
- [T2-004 Skills 与 Agnes Structured Brief](T2-004-skills-and-structured-brief.md)
- [T2-005 Brief 确认与 Preflight](T2-005-brief-confirmation-preflight.md)
- [T3-001 任务、Outbox 与积分事务](T3-001-task-outbox-credit-ledger.md)
- [T3-002 PPT Renderer 与系统模板](T3-002-ppt-renderer-templates.md)
- [T3-003 PPT QA](T3-003-ppt-quality-gates.md)
- [T3-004 Excel Renderer 与系统模板](T3-004-excel-renderer-templates.md)
- [T3-005 Excel QA 与组合任务](T3-005-excel-qa-combined-generation.md)
- [T4-001 用户流程与管理后台功能壳](T4-001-frontend-user-admin-flows.md)
- [T4-002 管理员最高权限与审计](T4-002-admin-asset-audit.md)
- [T4-003 黄金数据回归](T4-003-golden-regression.md)
- [T4-004 Office/WPS 与故障演练](T4-004-office-wps-failure-drills.md)
- [T4-005 安全检查与 Alpha 封版](T4-005-alpha-release-gate.md)
