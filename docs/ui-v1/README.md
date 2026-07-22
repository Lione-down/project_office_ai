# Office AI Alpha UI V1 基线

- 状态：`APPROVED-V1`
- 确认日期：`2026-07-22`
- 适用范围：Office AI Alpha 用户端与后台管理系统
- 计划入口：[Alpha 总计划](../../.hermes/plans/2026-07-22_000414-office-ai-alpha.md)
- 实施任务：[T4-001 用户流程与管理后台功能壳](../../.hermes/plans/office-ai-alpha-tasks/T4-001-frontend-user-admin-flows.md)、[T4-002 管理员最高权限与审计](../../.hermes/plans/office-ai-alpha-tasks/T4-002-admin-asset-audit.md)

本目录保存已经确认的第一版 UI 图，作为 Alpha 前端开发的视觉层级、页面结构、配色和交互密度基线。UI 图不新增产品功能；功能、安全、状态和权限要求仍以 Alpha 总计划及对应任务文档为准。

## 用户端 UI 图

| 页面 | UI 图 | 开发要点 |
|---|---|---|
| 工作台 / 新建任务 | [01-home.png](user/01-home.png) | 以单一主任务入口为中心，首屏只保留一个填充型主操作 |
| 生成前确认 | [02-confirm-generation.png](user/02-confirm-generation.png) | 清晰展示材料、Skill、模型、模板和预计积分，确认后再提交 |
| 任务结果 | [03-task-results.png](user/03-task-results.png) | 同屏呈现 PPTX、XLSX 子输出状态、质量结果与下载动作 |

## 后台管理 UI 图

| 页面 | UI 图 | 开发要点 |
|---|---|---|
| 管理员登录 | [00-admin-login.png](admin/00-admin-login.png) | 独立、克制的登录入口与错误反馈 |
| 概览 | [01-overview.png](admin/01-overview.png) | 关键运行状态优先，避免堆叠无行动价值的指标 |
| 用户 | [02-users.png](admin/02-users.png) | 搜索、筛选、状态和敏感操作入口 |
| 邀请码 | [03-invites.png](admin/03-invites.png) | 创建、状态、使用情况和失效管理 |
| Provider | [04-providers.png](admin/04-providers.png) | Provider 可用状态和配置入口 |
| Credential 重新认证 | [05-credentials-reauth.png](admin/05-credentials-reauth.png) | Credential 默认掩码；Reveal 前重新认证并填写原因 |
| 模型 | [06-models.png](admin/06-models.png) | 发布状态、Provider 归属和用户可见性 |
| 任务 | [07-tasks.png](admin/07-tasks.png) | 任务状态、子输出、异常与重试信息 |
| 资产 | [08-assets.png](admin/08-assets.png) | 管理员预览、下载、删除及审计提示 |
| 积分 | [09-credits.png](admin/09-credits.png) | 余额、流水和人工调整；调整必须说明原因 |
| 审计日志 | [10-audit-logs.png](admin/10-audit-logs.png) | 操作者、动作、目标、原因、结果和时间可追溯 |

## 统一视觉与交互约束

- 采用暖瓷白背景、墨色文字和钢蓝色主操作，保持高级、安静、可信赖的工具感。
- 禁止紫色、紫蓝渐变、霓虹光晕和刻意的“AI 感”装饰；不使用无功能价值的大面积渐变。
- 用户端每个页面原则上只保留一个填充型主操作；次要动作使用描边、文字或菜单承载。
- 后台主导航统一为：`概览 / 用户与邀请码 / 服务配置 / 任务与资产 / 积分 / 审计日志`。个别概念图中的缩写只用于构图，开发时使用这里的完整名称。
- 复用项目既有 token、组件和 Vue 目录约定，不另建第二套设计系统。
- 所有页面必须补齐 `loading / empty / error / disabled / no-permission`；生成流程还需覆盖 `partial success / provider uncertain`。
- Credential Reveal、密码重置、用户状态变更、积分调整和资产删除统一使用重新认证对话框，并要求填写操作原因；失败尝试同样进入审计。
- Credential、Token、API Key 和签名 URL 默认掩码，不在页面、日志或错误信息中输出明文。
- UI V1 要求常用桌面宽度下完成主流程；最终像素级打磨、复杂动效和完整多端响应式属于 V1 之后的体验升级。

## 实施优先级

发生描述差异时，按以下顺序处理：

1. Alpha 总计划中的功能边界、安全约束与完成定义。
2. `T4-001`、`T4-002` 的任务验收标准。
3. [用户端方向说明](../ui-mockups/2026-07-22-office-ai-alpha-ui-direction-v3.md)与[后台 UI 说明](../ui-mockups/2026-07-22-office-ai-admin-ui-spec.md)。
4. 本目录 UI 图的视觉层级、布局比例和组件密度。

UI 图是实现基线，不是代码完成证据。开发完成后仍需通过组件测试、Production Build、权限/状态检查以及真实构建产物的逐页人工视觉验收。
