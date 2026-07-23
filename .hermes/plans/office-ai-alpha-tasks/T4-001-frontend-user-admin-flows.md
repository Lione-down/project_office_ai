# T4-001 用户流程与管理后台功能壳

- 状态：`READY`
- Depends on：`T3-005`
- 来源：总计划第 2、12 节与 Day 16
- 建议 commit：`feat(frontend): expose alpha user and admin workflows`

## 目标

用现有 Vue 设计约定交付清晰可用的 Alpha 用户端和管理端完整流程，并以 `docs/ui-v1/README.md` 及其 14 张已确认 UI 图作为第一版视觉与交互基线。

## 交付范围

- 用户端：注册、登录、强制改密、项目/资产、术语库、Skill/模型/模板选择、Brief、Preflight、生成进度、质量结果、下载、积分。
- 管理端：用户、邀请码、Provider、Credential、Model、任务、资产、积分调整和审计日志基础页面。
- 路由权限、加载/空/错误/无权限状态、稳定 API 错误信息和关键组件测试。
- 页面结构、视觉层级、配色和交互密度对齐 UI V1；用户端参考 `docs/ui-v1/user/**`，后台参考 `docs/ui-v1/admin/**`。
- 后台主导航使用“概览 / 用户与邀请码 / 服务配置 / 任务与资产 / 积分 / 审计日志”的完整名称。
- 样式遵循项目既有 token、命名和组件约定；不新建第二套设计系统。

## 实施步骤

1. 先盘点现有组件、样式、路由和模块边界，对照 UI V1 建立页面清单、共用组件清单与视觉 token 映射，再写关键流程与权限组件测试。
2. 按 `views/<domain>/components` 和 `modules/<domain>` 组织页面、业务 API、类型与单域状态。
3. 按 `docs/ui-v1/user/01-home.png`、`02-confirm-generation.png`、`03-task-results.png` 实现用户 Happy Path 和所有阻断/错误反馈，生成状态使用持久任务 API。
4. 按 `docs/ui-v1/admin/**` 实现管理员登录、概览、用户、邀请码、Provider、Credential、模型、任务、资产、积分和审计页面；Credential 默认掩码。
5. 补齐 loading、empty、error、disabled、no-permission、partial success 和 provider uncertain 状态，不使用紫色、紫蓝渐变或无功能价值的 AI 装饰。
6. 使用真实 Production Build 逐页截屏，与 14 张 UI V1 图进行人工视觉与交互核对，并把差异和结论更新到进度文档。

## 验收标准

- 用户可独立完成从注册到双输出下载的 Alpha 流程，阻断项有明确中文提示。
- 普通用户无法进入或调用管理功能；强制改密用户不能绕过修改步骤。
- 页面覆盖 loading、empty、error、disabled、partial success 和 provider uncertain 状态。
- 3 张用户端和 11 张后台管理 UI 图均有对应可访问路由；主信息层级、主操作位置、色彩和组件密度与 UI V1 一致。
- 用户端每页原则上只有一个填充型主操作；后台导航、筛选、表格和敏感操作入口在页面间保持一致。
- 未引入紫色、紫蓝渐变、霓虹光晕或第二套设计 token；常用桌面宽度下无横向溢出和主操作遮挡。
- Frontend 测试与 Production Build 通过，无 TypeScript 错误。

## 验证

```powershell
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm backend pytest backend/tests/integration -q
```

## 非范围与回滚

- 不做 UI V1 之后的品牌升级、高保真动效、像素级终稿、完整多端响应式打磨或在线 Office 编辑器。
- 回滚单个路由/页面模块，不改变后端状态或删除已生成资产。
