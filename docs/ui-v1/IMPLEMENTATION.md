# Office AI Alpha UI V1 实施映射

- 状态：`T4-001 DONE`
- 视觉权威：`docs/ui-v1/README.md` 与本目录 14 张 `APPROVED-V1` UI 图
- 工程范围：Vue 3 + TypeScript；沿用现有 scoped CSS 与全局 token，不引入第二套设计系统

## 视觉主题与氛围

Office AI 使用暖瓷白底、墨色正文、钢蓝主操作和低饱和状态色，形成安静、精确、可信赖的
生产力工具界面。用户端以单一任务推进为中心，管理端以异常、状态和可追溯操作为中心，
不使用紫色、渐变、霓虹、玻璃拟态或装饰性 AI 元素。

参考产品只用于验证成熟交互模式，不覆盖 UI V1：Notion 的工作区信息克制、Linear 的
状态密度与筛选秩序、Stripe 的敏感信息掩码和审计式操作说明。

## Token 映射

| 角色 | Token | 值 |
|---|---|---|
| 画布 | `--oa-canvas` | `#f7f8f6` |
| 一级表面 | `--oa-surface` | `#ffffff` |
| 次级表面 | `--oa-surface-muted` | `#f1f3f2` |
| 主文字 | `--oa-ink` | `#0f172a` |
| 次文字 | `--oa-muted` | `#64748b` |
| 分隔线 | `--oa-line` | `#dde2e6` |
| 主操作 | `--oa-accent` | `#075985` |
| 主操作 hover | `--oa-accent-strong` | `#064a70` |
| 成功 | `--oa-success` | `#087f5b` |
| 警告 | `--oa-warning` | `#b85c00` |
| 危险 | `--oa-danger` | `#b91c1c` |

Spacing 只使用 `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64px` 阶梯。Radius 使用
`6 / 10 / 14px / pill` 四级；按钮统一 `10px`，输入统一 `8px`，主要表面统一 `14px`。
表面层级以背景明度步进、hairline 和低强度 shadow 表达。

## Typography

- 字体栈：`-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC",
  "Microsoft YaHei", sans-serif`，不依赖公网字体。
- 中文正文 `line-height: 1.7`；数字和表格列使用 `tabular-nums`。
- 32px 以上英文 display 可使用 `-0.022em`，中文不使用负字距。
- 标题和短说明使用 balance，正文使用 pretty wrapping。

## 组件和状态

- `AppShell` 根据 route 呈现用户 top navigation、管理 sidebar 或认证空壳。
- `AppButton`、`AppField`、`AppStatus`、`AppStatePanel` 统一 primary/secondary、
  focus、disabled、loading 和状态语义。
- 用户端页面原则上只有一个填充型主操作；管理端每页最多一个 header primary action。
- 列表使用稳定标题、最小筛选、hairline rows 和详情区域；数字右对齐、文字左对齐。
- 所有敏感值默认掩码；错误只显示稳定中文消息和可选 Trace ID，不显示 Secret 或路径。

## Layout

- 用户端 top navigation 固定四项：`首页 / 任务 / 文件 / 模板`。
- 管理端 sidebar 固定六项：`概览 / 用户与邀请码 / 服务配置 / 任务与资产 / 积分 /
  审计日志`。
- 用户主内容最大宽度 `1180px`；管理内容使用 sidebar 后的弹性工作区。
- Drawer 只用于非破坏性详情；敏感确认和 destructive flow 留给 T4-002。

## Responsive 与 accessibility

- 验证宽度：`1440 / 1280 / 1024 / 768 / 375 / 320px`。
- `<= 760px` 时用户导航允许水平滚动但页面本身不得横向溢出；管理 sidebar 折叠为顶部
  navigation，宽表使用受控 table scroller。
- interactive target 最小 `40 × 40px`；首个可聚焦元素为 skip link。
- 使用语义化 `button/a/nav/main/table`、明确 label、`aria-current`、live region 和
  visible focus；尊重 `prefers-reduced-motion`。

## 禁止项

- 不新增紫色、紫蓝渐变、glow、glass blur、装饰卡片墙或无功能 hero。
- 不使用 emoji 代替图标，不使用 `transition: all`，不动画 width/height/spacing。
- 不让客户端获得 storage key、路径、明文 Credential、Token、签名 URL 或敏感日志上下文。
- 不为 T4-002 尚未交付的敏感 API 伪造成功路径。

## 实际验证（2026-07-23）

- 用户端 3 张与管理端 11 张 UI V1 图均映射到独立可访问 route；headed Chrome 逐页验证
  Production Build，并检查 `1440px` 桌面和 `375px` 窄屏关键流程。
- 用户端完成注册、登录、reload 后 Session rotation、强制改密、项目/资产/Skill/模型/
  术语库选择、Brief/Preflight、Generation 与 PPTX/XLSX 下载；普通用户访问 admin
  稳定进入 no-permission。
- 管理端完整验证概览、用户、邀请码、Provider、Credential、模型、任务、资产、积分与
  audit route；Credential 显示掩码且无 Reveal 入口，T4-002 边界页面不伪造数据。
- 页面级 `scrollWidth === clientWidth`，窄屏 navigation/table 使用局部 scroller；
  最终 clean browser console 为 `0 errors / 0 warnings`。
- 浏览器使用受控 Mock API 验证前端视觉、交互和 API contract，不代表真实
  MySQL/Redis/Agnes/LibreOffice 或 Office/WPS runtime 通过。
