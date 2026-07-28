# P5-002 首页最近任务真实展示

- 状态：`BLOCKED`
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
