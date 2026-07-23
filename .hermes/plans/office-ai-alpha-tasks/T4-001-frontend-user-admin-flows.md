# T4-001 用户流程与管理后台功能壳

- 状态：`DONE`
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

## 2026-07-23 实施合同

### 路由与页面

- 公共认证：`/login`、`/register`、`/admin/login`。
- 用户主流程：`/`、`/workflow/new`、`/briefs/:briefId/confirm`、
  `/generations/:taskId`、`/tasks`、`/files`、`/templates`、`/term-libraries`、
  `/credits`、`/password/change`。
- 管理后台：`/admin`、`/admin/users`、`/admin/invites`、`/admin/providers`、
  `/admin/credentials`、`/admin/models`、`/admin/tasks`、`/admin/assets`、
  `/admin/credits`、`/admin/audit-logs`。
- 3 张用户端与 11 张管理端 UI V1 图均有独立可访问 route；管理后台使用完整六项主导航，
  二级资源通过 tab/route 呈现。

### API 与权限边界

- 直接接入已交付的 Auth、Projects/Assets、Skills/Models、Brief/Preflight、
  Generation/Outputs、Credits、Invite、Provider/Credential/Model API。
- 普通用户访问 admin route 时返回 no-permission 页面；匿名用户回到对应登录入口；
  `must_change_password=true` 时只能进入修改密码或退出，不能绕过强制改密。
- T4-002 才交付的管理员用户、任务、资产、积分和 audit HTTP 闭环在本任务只提供
  loading/empty/error/disabled/no-permission 页面壳与明确边界提示，不新增或模拟敏感 API。
- Credential 永远默认掩码；T4-001 不实现 Reveal、密码重置、用户状态变更、积分调整或
  管理员资产删除的敏感操作闭环。

### RED contract 与成功标准

- Router contract 覆盖全部 public/user/admin route、角色 metadata、404 和强制改密。
- Auth contract 覆盖注册、登录、Session bootstrap、角色跳转、中文错误和强制改密。
- 用户关键流程 contract 覆盖单一填充型主操作、已批准选择项、阻断提示、生成任务
  `loading/empty/error/disabled/partial_success/provider_uncertain` 与双输出下载 gate。
- Admin contract 覆盖完整六项导航、二级 tab、掩码 Credential、稳定列表状态和
  T4-002 敏感边界。
- 通过 frontend focused tests、production build、backend integration tests、
  dependency/security checks，以及真实 production build 的桌面和窄屏逐页浏览器验证。

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

## 实施结果（2026-07-23）

- 交付 25 个显式 public/user/admin route、Session refresh bootstrap、注册/登录/强制改密、
  用户完整选择与 Brief/Preflight/Generation/双输出下载流程，以及 11 个管理后台 UI V1
  route。普通用户稳定拒绝 admin route；Credential 仅掩码，不提供 Reveal。
- 已交付 API 的页面接入真实 frontend API module；T4-002 才交付的用户、任务、资产、积分
  与 audit 管理闭环只呈现明确 disabled/empty shell，没有伪造数据或敏感成功路径。
- RED contract 覆盖 router、auth/session、用户 Happy Path、生成状态、下载 gate、管理导航
  和 Credential 掩码；最终 frontend 为 `22 files / 58 tests passed`，Production Build
  `94 modules transformed`。
- 实际 headed Chrome 在 Production Build 上完成注册、登录、reload 后 refresh bootstrap、
  强制改密、普通用户 admin 拒绝、用户选择、Brief/Preflight、Generation、PPTX/XLSX 下载
  和 11 个管理 route 检查；桌面与 `375px` 窄屏无页面级横向溢出，最终 clean console 为
  `0 errors / 0 warnings`。浏览器后端为受控 Mock API，只证明前端视觉、交互和 contract。
- Broad verification：backend integration `5 passed`，backend full
  `545 passed, 2 skipped`，Ruff check/format 通过；PPT Renderer
  `4 files / 20 tests passed` 且 build 通过；两个 npm workspace audit 均为
  `0 vulnerabilities`。
- 任务卡三条 Docker 命令已实际尝试，但本机 `docker` 不可用并在启动前
  `CommandNotFoundException`。本任务没有 Docker、真实 MySQL/Redis/Agnes/LibreOffice、
  Microsoft Office/WPS 新证据；真实 Agnes 仍因未 opt-in 只有 Mock Contract 通过。
- 当前主会话完成顺序 deep review，修复 Session bootstrap、服务端 logout、术语库选择、
  Generation 创建、active navigation、注册部分失败清理、非 JSON 错误脱敏、环境标签、
  accessibility 和窄屏布局问题；最终没有剩余 blocking security/logic finding。
- T4-002 功能未提前实现；T4-001 commit/push 完成后，T4-002 是下一唯一 `READY` 任务。
