# Office AI 异步工作流任务与失败记录

- 日期：2026-07-27
- 类型：Post-Alpha 单任务修复
- 基线：`59595796707fbe8603e7266f2816446030325fe9`
- 用户目标：点击生成后立即创建可追踪任务；Brief 与文件生成在后台继续；任务页实时展示进度、备注和失败原因。

## 现状与根因

- `POST /briefs/generate` 在浏览器请求内同步构建完整 Context、调用 Agnes、执行一次
  repair 并校验 Schema，成功后才写入 `briefs`。
- 真实 Runtime 已观察到请求分别等待约 110 秒后返回 `502`、约 88 秒后返回 `422`；
  后者为两次 Provider 响应均未通过严格 Structured Brief Schema。
- 当前 `/tasks` 是静态占位页，前端测试还明确要求“不虚构任务历史”；后端只有
  `GET /generations/{task_id}`，没有 owner-scoped 工作流任务列表。
- `generation_tasks` 只在用户复核并确认 Brief 后创建，不能代表前置的 Brief 整理阶段。
  因此同步请求进行中、失败或等待确认时都没有统一任务记录。

## 设计决策

### 1. Canonical 工作流任务

新增 `workflow_tasks`，一条记录覆盖同一次用户工作流的全部阶段：

1. `brief_queued`
2. `brief_generating`
3. `awaiting_confirmation`
4. `generation_queued` / `generation_running`
5. `succeeded` / `partial_success` / `failed` / `provider_uncertain` /
   `cancelled`

记录 owner、project、Brief group、关联 generation task、幂等键、目标标题、输出类型、
当前阶段、状态、进度、系统备注、稳定失败码、可安全展示的失败原因和时间戳。

- `request_snapshot` 只保存重放 Brief 所需的结构化 ID、Skill、目标和受众；
  不保存文件内容、Evidence、Prompt、Provider 原始响应或 Credential。
- `brief_group_id` 关联整个不可变 Revision 组，用户修订 Brief 后仍属于同一工作流。
- 现有 `generation_tasks` 继续作为积分、Outbox、步骤和输出执行事实来源，不复制其状态机。

### 2. 异步创建与执行

- 新增 `POST /workflow-tasks`，要求 `Idempotency-Key`，在短事务内校验 Session 与
  owner project，创建 `workflow_tasks + outbox_events`，立即以 `202` 返回任务快照。
- 现有同步 `POST /briefs/generate` 仅保留为兼容 contract，不再由用户工作流调用；
  API 文档标记为 legacy，后续在独立版本化任务中移除，避免本次混入破坏性 API 变更。
- 新增独立 `workflow-worker` 容器。它可以访问 Agnes、只读 Evidence、MySQL 与 Redis；
  原解析 `worker` 继续不挂载 Credential、不访问 Provider，保持安全隔离。
- Outbox publisher 按 event type 分流到 Brief 与文件生成队列，避免不同 consumer
  误取消息。
- Brief worker claim 后调用既有严格 Brief service；成功写 Brief 并将工作流置为
  `awaiting_confirmation`，失败则持久化稳定错误码和脱敏原因。
- Worker 崩溃且 Provider 结果未知时置为 `provider_uncertain`，不自动重复外部调用。
  队列投递前失败仍由 Transactional Outbox 重试。

### 3. 与现有文件生成关联

- 用户从工作流详情进入 Brief 确认页，现有 Preflight 与人工确认 Gate 保持不变。
- `POST /generations` 创建现有 durable generation task 时，按同一 Brief group 关联
  `workflow_tasks.generation_task_id`。
- 工作流列表/详情在有关联 generation task 后，以其持久状态、进度、积分和失败结果为
  authoritative projection；不维护第二套文件生成状态。

### 4. API 与 UI

- `GET /workflow-tasks`：owner-scoped，按创建时间倒序返回最多 100 条。
- `GET /workflow-tasks/{task_id}`：owner-scoped 工作流详情。
- `/tasks` 使用真实 API，显示任务、输出、状态、进度、备注/失败原因、积分，并轮询
  非终态任务。
- 新增 `/tasks/{task_id}` 工作流详情：
  - Brief 处理中展示 durable progress；
  - `awaiting_confirmation` 提供“查看并确认 Brief”；
  - 文件生成阶段提供现有 generation detail 入口；
  - 失败展示 `failure_code + failure_reason`，包括真实
    `brief_schema_invalid / Structured Brief Schema 无效`。
- 新建工作流提交成功后立即导航到工作流详情，不再等待 Agnes。

## TDD 验收

### RED

1. Migration/model：`workflow_tasks`、owner/idempotency unique、关联字段和失败字段存在。
2. Backend：
   - enqueue 立即返回 queued task 并产生专用 Outbox；
   - owner-scoped list/detail；
   - worker success 进入 waiting confirmation；
   - `brief_schema_invalid` 被持久化为 failed 与安全失败原因；
   - 重复消息不重复调用 Provider；
   - generation create 关联同一 Brief group。
3. Frontend：
   - submit 使用 Idempotency-Key 并导航到 workflow task；
   - 任务页读取真实列表并展示进度、备注、失败原因；
   - 详情轮询非终态，失败不消失，Brief ready 可进入确认页。

### GREEN 与 broad verification

1. Backend focused pytest：workflow task API/service/worker/migration/outbox/generation link。
2. Frontend focused Vitest：workspace API、workflow new、task list/detail、routes。
3. Backend full pytest、Ruff check/format；Frontend full Vitest、build。
4. Alembic empty SQLite、MySQL offline SQL、真实 MySQL upgrade/check。
5. Docker build/recreate backend/frontend/workflow-worker；health 与真实浏览器验证：
   创建立即返回、列表立即出现、失败原因持久、刷新后仍可见。
6. `pip check`、`pip-audit`、`npm audit`、`git diff --check` 与敏感信息检查。

## 文档与交付

- 同步 `docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、
  `docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md` 与 `pitfalls.md`。
- 只精确暂存本任务文件，创建一个 `feat(workflow): add durable async task tracking`
  commit 并 push `origin/main`。

## 明确不变

- 不降低 Structured Brief Schema、Evidence、Preflight、质量或下载 Gate。
- 不把 Provider 原始响应写入任务备注或返回给用户。
- 不自动重试 `provider_uncertain`，不重复扣费。
- 不修改或暂存 private workbook、Manifest、`.env`、`.playwright-cli/`、
  `design-system/`、旧 `docs/ui-mockups/` 或 ignored `output/`。
- 本任务不顺带解决 Agnes 为什么两次生成均违反 Schema；该 Provider 内容质量问题由
  新任务持久记录，后续可用脱敏失败分类单独分析。

## 完成记录

- Backend focused：`71 passed`；full：`597 passed, 6 skipped`；Ruff 全量
  check/format 通过。
- Frontend full：23 files / `70 passed`；production build：
  `101 modules transformed`。
- 真实 MySQL migration：`20260727_0015 (head)`；`alembic check` 无 drift。
- Docker：Backend image 顺序重建成功，Backend/Frontend/workflow-worker 重建后
  10 个长期服务 healthy；`9999/health/ready=ready`，`8888=200`。
- Backend image 内 workflow tests `12 passed`；`pip check`、`pip-audit` 与
  `npm audit --audit-level=high` 通过，未发现已知 dependency vulnerability。
- Browser：无登录 Session 的真实 Chrome 按 contract 重定向登录页；为避免无必要
  Provider 调用，没有代替用户登录或创建含用户材料的新任务。登录态交互由 focused
  component contract 覆盖，修复前没有 canonical task 的失败不做伪造回填。
