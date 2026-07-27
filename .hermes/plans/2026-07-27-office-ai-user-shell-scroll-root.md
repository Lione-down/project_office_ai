# Post-Alpha User App Shell 滚动根修复

## 背景与 Runtime 根因

- 新建任务页和 Brief 确认页内容高度均超过视口，但真实鼠标滚轮与 `PageDown` 不改变
  `document.scrollingElement.scrollTop`。
- 页面布局高度正确：新建任务页内容 1627px、视口 1090px，理论可滚动 537px；
  `html/body/main` 的 `overflow-y` 均为 `visible`，且没有页面级
  `wheel/touchmove/keydown` listener。
- 同一 Chrome 的独立长页面可以正常滚动，排除鼠标、Chrome 和全局扩展故障。
- Office AI User App Shell 只设置 `min-height: 100vh`，依赖浏览器隐式 root scrolling。
  运行时仅为 `.user-shell` 增加 `height: 100dvh; min-height: 0; overflow-y: auto` 后，
  同一滚轮手势令 shell `scrollTop` 从 0 变为 280，根因得到验证。

## 目标

1. User App Shell 成为唯一、明确的纵向 scroll root。
2. 新建任务、Brief、任务详情、文件和模板等用户端页面共享同一滚动行为。
3. Header 与内容继续在同一自然文档流中滚动，不改页面结构、表单 state 或路由。
4. Desktop、375px 和键盘滚动均可到达页面底部，无横向 overflow。

## 设计方向

- **Visual thesis**：保持现有暖白画布、钢蓝强调和低层级阴影，不做视觉重设计。
- **Content plan**：App Shell 负责方向与滚动，页面继续负责内容高度和业务动作。
- **Interaction thesis**：滚轮、触控和键盘都作用于同一个明确 scroll root；不增加动画。
- 参考 Linear、Notion、Slack 的工作区结构：viewport-height shell 明确承担滚动，而不是
  依赖浏览器隐式 root scrolling。

## 实施范围

- 在 User App Shell 标记并建立 viewport-height vertical scroll root。
- 增加 App Shell component contract，防止以后退回隐式 root scrolling。
- 不修改单个业务页面的高度或 overflow，不在每个页面分别打补丁。

## 不在范围

- 不修改 Admin/Public Shell、页面视觉、导航、API、数据库、任务或用户文件。
- 不添加全局 wheel listener，不调用 `preventDefault`，不使用 JS 模拟滚动。
- 不修改 Brief、Evidence、Preflight、积分或生成状态。

## RED / GREEN 验收

1. User Shell 暴露唯一、可测试的 scroll root contract。
2. CSS 明确使用 `height: 100dvh; min-height: 0; overflow-y: auto`。
3. 真实新建任务页滚轮后 scroll root `scrollTop > 0`，并可到达底部主按钮。
4. 2048px 与 375px 无横向 overflow，Console 无 warning/error。
5. Frontend focused、full tests、production build 与 audit 通过。

## 验证命令

```powershell
docker compose run --rm frontend npm run test -- --run src/components/layout/app-shell.test.ts
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm frontend npm audit --audit-level=high
```

## Runtime 与交付

- 只重建并强制替换 Frontend；Backend、Worker、MySQL、Redis 和用户数据不变。
- 更新 `docs/PLAN.md`、`docs/PROGRESS.md` 与 `pitfalls.md`。
- 精确暂存，一个 `fix(ui): ...` commit 并 push。
