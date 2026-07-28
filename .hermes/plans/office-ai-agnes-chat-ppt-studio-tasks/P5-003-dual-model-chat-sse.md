# P5-003 双模型会话、SSE 与历史

- 状态：`BLOCKED`
- Depends on：`P5-002`
- 来源：PRD FR-101～FR-107、模型策略、Chat Run 状态机
- 建议 commit：`feat(chat): add dual model streaming conversations`

## 目标

交付 owner-scoped、可持久继续的 Agnes 2.5/2.0 多轮对话，使用 FastAPI SSE 转发真实
Provider 流，并安全支持停止、partial、失败、重新生成和消息分支。

## 交付范围

- Additive migration、models/services/API：thread、message、run 与合同冻结的关联字段。
- 新建/列表/打开/重命名/软删除会话及搜索/时间分组。
- 用户明确选择已发布且具备 chat capability 的 2.5/2.0；会话保存默认模型。
- FastAPI -> Agnes `stream:true` -> SSE；事件含 start/delta/complete/cancelled_partial/
  failed/provider_uncertain，服务端权威终态。
- 停止、断线收口、幂等、防并发重复 run、有限重试和 Provider metadata 脱敏。
- Vue AI 创作导航、会话栏、消息区、输入区、安全 Markdown、copy/edit-resend/regenerate。
- 白名单工具框架只建立 capability/Schema 拒绝边界；媒体或生成工具仍不执行。

## RED 与实施顺序

1. Migration/model/state-machine/owner/API/SSE parser/cancel tests 先 RED。
2. Provider adapter Mock stream contract、双模型选择和禁止自动 fallback 先 RED。
3. Frontend store/API/SSE reducer/Markdown XSS/branch/UI tests 先 RED。
4. Backend GREEN -> Frontend GREEN -> 真实 MySQL migration -> Compose/browser ->
   opt-in 真实 Agnes 2.5/2.0。

## 验收标准

- 两模型均可由用户明确选择；2.5 失败不会自动切换 2.0，旧文件流程 2.0 默认不变。
- 刷新/重新登录后会话和消息可继续，跨用户 ID 不泄露存在性。
- stop 后 partial 标记准确；客户端断开有服务端收口，不把 partial 当 complete。
- branch/regenerate 新增消息/run，不覆盖历史；同幂等键不重复调用或扣费。
- Markdown 禁止原始 HTML、script、事件属性、危险 URL；高风险内容显示未核验提示。
- bundle、Network 非正文 metadata、日志、provider_calls 不含 Key/Prompt/response body。

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/chat tests/providers -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check app tests alembic
.venv\Scripts\ruff.exe format --check app tests alembic
cd ..
cd frontend
npm run test -- chat
npm run test
npm run build
cd ..
docker compose config --quiet
git diff --check
```

## 证据边界

- Focused：migration/state/SSE/cancel/owner/idempotency/Markdown/branch。
- Broad：Backend full/Ruff、Frontend full/build、Compose。
- Security：XSS、URL、超长输入、tool injection、跨用户、disconnect、日志/正文泄漏。
- Provider：Mock 只证明应用合同；2.5 与 2.0 分别执行显式 opt-in 的真实 stream/stop
  Contract，记录状态/latency/token 等脱敏 metadata，不打印正文。
- Office/WPS：本任务不生成 PPTX，不产生桌面兼容证据。

## 非目标与回滚

- 不创建 Deck Draft、图片、视频或文件生成任务。
- 不启用公共 Web 搜索或任意 execute 工具。
- 回滚 additive API/UI feature 和 migration head 的安全 downgrade；不删除已存在用户数据。
