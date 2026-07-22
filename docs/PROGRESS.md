# Office AI Alpha 进度记录

- 最后更新：`2026-07-22`
- 最近完成：`T1-001 工程与文档基线`
- 下一任务：`T1-002 FastAPI、Vue 与数据库骨架`
- 当前状态：`T1-002 READY`
- 当前分支：`main`
- 远端：`origin/main`

## 新会话必读

每次会话必须按顺序读取：

1. `AGENTS.md`
2. 本文件
3. `.hermes/plans/office-ai-alpha-tasks/README.md`
4. 表格中第一个 `READY` 任务的任务文档
5. `docs/PLAN.md` 及该任务涉及的专题文档
6. `git status --short --branch`

不得只依赖上一会话的聊天摘要。只有前置任务为 `DONE` 的任务才能改为 `READY`。

## 任务状态

| ID | 状态 | Depends on | Commit/证据 |
|---|---|---|---|
| T1-001 | DONE | 无 | `chore(project): establish office ai alpha baseline`；验证证据见下文 |
| T1-002 | READY | T1-001 | FastAPI、Vue 与数据库骨架；必须先补 Docker runtime preflight |
| T1-003 | BLOCKED | T1-002 | 用户、Session 与邀请码 |
| T1-004 | BLOCKED | T1-003 | Provider、Credential 与模型后台 |
| T1-005 | BLOCKED | T1-004 | 项目与资产上传；Week 1 Gate |
| T2-001 | BLOCKED | T1-005 | 文件扫描与解析沙箱 |
| T2-002 | BLOCKED | T2-001 | OCR 与 Evidence Manifest |
| T2-003 | BLOCKED | T2-002 | 术语库与证据标准化 |
| T2-004 | BLOCKED | T2-003 | Skills 与 Agnes Structured Brief |
| T2-005 | BLOCKED | T2-004 | Brief 确认与 Preflight；Week 2 Gate |
| T3-001 | BLOCKED | T2-005 | 任务、Outbox 与积分事务 |
| T3-002 | BLOCKED | T3-001 | PPT Renderer 与系统模板 |
| T3-003 | BLOCKED | T3-002 | PPT QA |
| T3-004 | BLOCKED | T3-003 | Excel Renderer 与系统模板 |
| T3-005 | BLOCKED | T3-004 | Excel QA 与组合任务；Week 3 Gate |
| T4-001 | BLOCKED | T3-005 | 用户流程与管理后台功能壳 |
| T4-002 | BLOCKED | T4-001 | 管理员最高权限与审计 |
| T4-003 | BLOCKED | T4-002 | 黄金数据回归 |
| T4-004 | BLOCKED | T4-003 | Office/WPS 与故障演练 |
| T4-005 | BLOCKED | T4-004 | 安全检查与 Alpha 封版；Week 4 Gate |

## T1-001 执行记录

### 范围

- 建立项目级执行规则和 Alpha scope、API、21 张表、环境、安全与进度文档。
- 建立 9 服务 Docker Compose 拓扑和 healthcheck/dependency 边界。
- 保留并纳入已批准的 UI V1 和 20 个 dependency-ordered 任务文档。
- 不启动容器、不实现业务模型/API/UI、不读取本地 `.env`。

### Changed files

- 工程基线：`AGENTS.md`、`README.md`、`docker-compose.yml`、`pitfalls.md`。
- 执行文档：`docs/PLAN.md`、`docs/PROGRESS.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`。
- 批准基线：`.hermes/plans/2026-07-22_000414-office-ai-alpha.md`、`.hermes/plans/office-ai-alpha-tasks/`、`docs/ui-v1/`。
- UI V1 直接引用规格：`docs/ui-mockups/2026-07-22-office-ai-alpha-ui-direction-v3.md`、`docs/ui-mockups/2026-07-22-office-ai-admin-ui-spec.md`。
- 未纳入本任务：`design-system/`、旧版 `docs/ui-mockups/` 进度/方向稿和 ignored `output/`。

### 验证证据

- 官方 Docker Compose standalone v5.1.4：官方 SHA-256 校验通过；`docker-compose -f docker-compose.yml config --quiet` 退出码 `0`。
- `docker-compose -f docker-compose.yml config --services`：通过，解析 `frontend/backend/worker/ppt-renderer/mysql/redis/clamav/paddleocr/libreoffice` 共 9 个服务。
- PyYAML 静态断言：通过；YAML 可解析，9/9 healthcheck、9/9 non-root，`worker` 仅在 internal `private` network 且无 Provider/Master Key 环境变量。
- UTF-8、21 张表连续编号、20 个任务 ID、20 个任务索引链接：通过。
- `git check-ignore -v .env backend/files/example.txt output/example.png golden-data/private/example.xlsx`：通过。
- Secret pattern scan：通过；未发现常见 API token、AWS access key 或 private key header。
- `git diff --check`：通过。
- `git fetch origin` 后 `HEAD...origin/main` 为 `0 0`，提交前没有远端分叉。

### 阻塞与风险

- 本机没有 Docker daemon/Desktop，官方 standalone 只能验证 Compose config；未拉取镜像、未验证镜像可达性或容器 runtime health。该项阻塞后续容器启动验证，`T1-002` 必须在可用 Docker 环境补验，T1-001 未伪造 runtime 通过。
- 真实 Agnes Key、10 组获授权且脱敏的销售材料、Microsoft Office/WPS 分别是后续任务的外部前置条件；不得写入仓库或聊天。

### 完成结论

- T1-001 交付、focused verification、文档记录和单一逻辑 commit 已完成；最终 commit 推送到 `origin/main` 后由当前会话创建 T1-002 新任务。
- T1-002 是唯一 `READY` 任务。新会话必须先读取本文件与任务卡，先确认 Docker Desktop/daemon 可用并验证镜像 pull/runtime health，再建立应用骨架。
