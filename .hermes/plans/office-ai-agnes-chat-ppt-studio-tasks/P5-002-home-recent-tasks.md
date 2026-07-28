# P5-002 首页最近任务真实展示

- 状态：`DONE`
- Depends on：`P5-001`
- 来源：PRD FR-601～FR-605、US-07
- 建议 commit：`feat(home): show authoritative recent tasks`

## 目标

用现有 owner-scoped workflow task API 替换首页静态占位，显示最近 3–5 条真实任务及权威
状态/进度，并保持完整任务页和旧流程不变。

## 交付范围

- 首页最近任务 loading、empty、success、failure/retry 四种状态。
- 按创建时间倒序显示标题、输出类型、状态、进度、更新时间和详情入口。
- 存在非终态任务时使用受控间隔刷新；离页、unmount 或全部终态时停止。
- 复用 workspace/workflow task API、类型和状态映射，不创建第二套任务事实。
- Desktop/mobile 与 App Shell scroll root 回归。

## RED 与实施顺序

1. Frontend component contract 先锁定真实列表、排序/截取、状态、失败和轮询清理。
2. 观察旧静态首页 RED，再最小实现 API 消费和 UI。
3. focused 后执行 Frontend full/build、现有任务 API regression 与真实浏览器只读验证。

## 验收标准

- 当前用户最近 3–5 条按创建时间倒序，点击进入现有 task detail。
- 非终态显示服务端 progress，无前端假进度；轮询不泄漏、不在离页后继续。
- 空列表、API 失败和 retry 可区分；旧任务页行为不变。
- 375px 与 Desktop 无横向 overflow，键盘焦点和状态文本可访问。

## 验证

```powershell
cd frontend
npm run test -- home
npm run test
npm run build
cd ..
cd backend
.venv\Scripts\python.exe -m pytest tests/workflow_tasks -q
cd ..
git diff --check
```

## 证据边界

- Focused：Home component/API/interval cleanup。
- Broad：Frontend full/build、workflow task API suite。
- Security：owner scope 由 API 回归；UI 不显示内部 ID、路径或 unsafe failure detail。
- Runtime/browser：使用已有登录状态只读验证真实任务；不创建、不重试、不扣积分。
- Provider/Office/WPS：本任务不调用 Provider、不生成 Office 文件，不产生对应证据。

## 非目标与回滚

- 不实现对话、Draft、模板详情或媒体任务。
- 不改变 workflow task API、数据库 Schema、任务状态机或积分。
- 回滚恢复首页为最后稳定实现，不删除任何持久任务。

## 完成记录（2026-07-29）

### RED -> GREEN 与实现

- RED：新增 Home component contract 后，旧静态首页为 `5 failed, 2 passed`；失败均因
  不存在真实 workflow list、loading/empty/failure、retry 或轮询行为，原有三个输出选择
  和继续动作保持通过。
- GREEN：首页调用既有 `workspaceApi.listWorkflowTasks`，按 `created_at` 倒序显示最近
  `5` 条；标题、输出类型、状态、`progress`、`updated_at` 和详情链接均来自既有
  `WorkflowTask`。
- workspace 级 presentation helper 统一 terminal status、状态文案和输出类型映射；
  Home、完整任务列表与任务详情复用同一映射，没有新增 API、任务状态机或持久状态。
- 只有成功列表中存在非终态任务时才在前一次请求完成后安排单次 `3000ms` 刷新；全部
  终态、失败、离页或 unmount 时清理 timer，迟到响应通过 request generation 失效。
- API 失败只显示固定安全中文和显式“重新加载”；首页不显示 `failure_code`、内部路径或
  Provider detail，也不自动触发 retry。

### 验证与浏览器证据

- Focused Home：`7 passed`；受共享映射影响的 Home/Resource/Task Detail 相关回归为
  `5 files / 20 passed`。
- Frontend full：`23 files / 78 passed`；production build 为
  `106 modules transformed`。
- Backend workflow task owner/API regression：`13 passed`。
- 真实已登录 Chrome 只读验证当前用户最近 `5` 条任务，状态含已完成/失败，权威进度为
  `100%`；首条详情链接成功进入既有 `/tasks/{task_id}`，没有创建、重试任务或扣积分。
- Desktop `2048x1146`：document `2048/2048`、User Shell `2033/2033`，最近任务为
  两列 `568px + 568px`；Mobile `375x812`：document `375/375`、User Shell
  `360/360`，最近任务为单列 `328px`，5 个详情链接均可键盘聚焦。Console
  warning/error 为 `0`。
- 浏览器只读验证临时使用当前源码 Vite 与既有 Backend；结束后恢复原 Frontend 容器，
  Frontend `8888=200`、Backend ready `9999=200`。

### Changed files 与证据边界

- Frontend：
  `frontend/src/modules/workspace/workflow-task-presentation.ts`、
  `frontend/src/views/user/home.vue`、`home-recent-tasks.css`、`home.test.ts`、
  `frontend/src/views/user/resource.vue`、`frontend/src/views/task/detail.vue`。
- Records：本任务卡、P5-003 卡、任务索引、Post-Alpha 总计划、`docs/PLAN.md` 和
  `docs/PROGRESS.md`。
- 未修改 workflow task API、数据库 Schema、任务/积分事实、Provider、Renderer、
  `.env`、用户文件或用户已有 `.playwright-cli/`、`design-system/`、旧
  `docs/ui-mockups/`。
- 本任务不调用 Provider、不生成 Office 文件，不产生 Agnes、Microsoft Office、WPS 或
  Renderer 新证据；上述测试和浏览器记录不替代这些后续 Gate。
