# Office AI Alpha 后台管理系统 UI 规格

## 目标

补齐可直接指导 Vue 前端开发的后台管理页面体系。范围严格来自 Alpha 总计划及 `T1-004`、`T4-001`、`T4-002`，不引入组织、团队、多角色权限或在线 Office 编辑器。

## 信息架构

后台主导航固定为六组：

1. 概览
2. 用户与邀请码
3. 服务配置
4. 任务与资产
5. 积分
6. 审计日志

二级导航：

- 用户与邀请码：`用户` / `邀请码`
- 服务配置：`Provider` / `Credential` / `Model`
- 任务与资产：`任务` / `资产`

## UI 图清单

| 编号 | 路由/状态 | 主要开发内容 |
|---|---|---|
| 00 | 管理员登录 | 手机号、密码、限速反馈、登录态和无权限提示 |
| 01 | 概览 | 今日任务、成功率、待处理事项、服务状态、最近审计 |
| 02 | 用户管理 | 搜索、状态过滤、用户表格、详情 Drawer、禁用/启用、重置密码 |
| 03 | 邀请码管理 | 创建邀请码、有效期、次数、赠送积分、状态和使用记录 |
| 04 | Provider | Provider CRUD、Base URL、启用状态、配置校验和健康测试 |
| 05 | Credential | 掩码、Fingerprint、RPM/TPM/并发、测试结果、Reveal 重新认证 |
| 06 | Model | Provider/Credential 绑定、能力、Context、输出上限、用户可见、推荐、积分倍率、Skill |
| 07 | 任务管理 | 状态过滤、`partial_success`、`provider_uncertain`、积分预留和任务详情 Drawer |
| 08 | 资产管理 | 全用户资产搜索、扫描/解析状态、预览/下载/删除和审计边界 |
| 09 | 积分管理 | 用户余额、流水、预留/结算/释放、管理员调整 Drawer |
| 10 | 审计日志 | 操作者、动作、目标、IP、User-Agent、原因、结果和脱敏上下文 |

## 通用页面结构

- 220px 左侧导航，顶部为页面标题、环境、通知和管理员身份。
- 内容区使用暖瓷白背景，主表面使用白色，钢蓝作为唯一 Primary Action。
- 页面 Header 最多一个实心按钮；表格行操作使用文字、更多菜单或描边按钮。
- 表格顶部只保留任务必需的搜索与 2–4 个过滤器。
- 详情优先使用右侧 Drawer，避免离开列表后丢失查询状态。
- 分页使用 `page/page_size`，默认保留搜索、过滤、排序与页码状态。

## 敏感操作模式

以下操作必须使用统一 `AdminReauthDialog`：

- Credential Reveal
- 用户密码重置
- 用户状态变更
- 管理员积分调整
- 资产删除

Dialog 包含：操作摘要、管理员密码、操作原因、风险说明、取消和确认。原因必填；确认成功后显示反馈并写入审计。Credential 默认显示 `sk-••••9K2A`，Reveal 结果不可缓存，关闭后恢复遮罩。

## 状态覆盖

- 列表：loading / empty / error / permission denied / normal。
- 操作：idle / submitting / success / validation error / re-auth expired / conflict。
- 任务：queued / running / succeeded / partial success / provider uncertain / failed / cancelled。
- 资产：quarantine / scanning / parsing / ready / rejected / deleted。
- Credential：active / degraded / disabled / auth failed / rotation due。

## Vue 开发映射

```text
src/views/admin/
├── Login.vue
├── Overview.vue
├── users/
├── invites/
├── providers/
├── credentials/
├── models/
├── tasks/
├── assets/
├── credits/
├── audit/
└── components/
    ├── AdminShell.vue
    ├── AdminDataTable.vue
    ├── AdminDetailDrawer.vue
    ├── AdminReauthDialog.vue
    ├── AdminStatusBadge.vue
    └── AdminEmptyState.vue
```

业务 API、类型与单域状态放入 `src/modules/admin/<domain>/`，不把具体业务接口放入全局 `api/`。

## 开发验收标准

- 普通用户无法进入后台路由或调用管理接口。
- 所有列表具备 loading、empty、error、权限不足和分页状态。
- 所有敏感操作要求重新认证和原因，成功与失败均有明确反馈。
- Credential 默认遮罩，任何普通响应、日志和 UI 截图不包含明文 Key。
- 资产预览、下载和删除均通过资产 ID 与管理员权限，不接受磁盘路径。
- 页面无紫色、无渐变、无发光 AI 图形；同一页面最多一个实心 Primary Action。
