# Office AI Alpha 进度记录

- 最后更新：`2026-07-22`
- 最近完成：`T1-002 FastAPI、Vue 与数据库骨架`
- 下一任务：`T1-003 用户、Session 与邀请码`
- 当前状态：`T1-003 READY`
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
| T1-002 | DONE | T1-001 | `chore(core): bootstrap frontend backend and database`；Docker runtime 缺口见下文 |
| T1-003 | READY | T1-002 | 用户、Session 与邀请码 |
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
- T1-001 交接时，T1-002 是唯一 `READY` 任务；该历史交接要求已由下方 T1-002 执行记录闭环。

## T1-002 执行记录

### 范围

- 按批准结构建立 FastAPI、SQLAlchemy 2、Pydantic 2、Redis 与 Alembic skeleton；没有创建任何用户、Provider、资产或任务业务表。
- 提供 `/health/live`、`/health/ready`、Trace ID、结构化 JSON request log、稳定错误 envelope、CORS 和脱敏 dependency status。
- 建立 Vue 3、TypeScript、Vite、Router、Pinia、API client、权限 metadata/guard 与非业务 placeholder shell。
- 将 Backend/Frontend Dockerfile 和 Compose placeholder command 替换为真实应用/test/build entry；保持其余服务边界不变。

### Changed files

- Backend：`backend/pyproject.toml`、`backend/Dockerfile`、`backend/.dockerignore`、`backend/app/**`、`backend/tests/**`。
- Migration：`backend/alembic.ini`、`backend/alembic/**`；初始 Head 为 `20260722_0001`，只建立 Alembic version baseline。
- Frontend：`frontend/package.json`、`frontend/package-lock.json`、`frontend/Dockerfile`、`frontend/.dockerignore`、`frontend/index.html`、`frontend/tsconfig*.json`、`frontend/vite.config.ts`、`frontend/src/**`、`frontend/tests/**`。
- Runtime/记录：`docker-compose.yml`、`README.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/PROGRESS.md`、`pitfalls.md`、T1-002/T1-003 任务状态。
- 未触碰：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`。

### TDD 与 focused verification

- RED：Backend tests 因 `app` 不存在而 collection 失败；Frontend 4 个 suite 因 request/guard/routes/bootstrap 尚不存在而失败；MySQL driver contract 在 `asyncmy -> aiomysql` 切换前按预期失败。
- Backend：`backend/.venv/Scripts/python.exe -m pytest -q`，`8 passed`，无 warning。
- Backend quality：`ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过。
- Frontend：`npm run test`，4 个 test files、`7 passed`；`npm run build` 通过，44 modules transformed，TypeScript 无错误。
- 本机 Uvicorn HTTP smoke：`/health/live` 返回 `200 live`；MySQL/Redis 均不可用时 `/health/ready` 返回脱敏 `503 service_not_ready`，日志含 Trace ID。
- Alembic：`alembic heads` 为 `20260722_0001 (head)`；MySQL dialect `upgrade head --sql` 通过；SQLite in-memory 空库 `upgrade head` 退出码 `0`。SQLite 只验证 migration 机制，不代表 MySQL runtime。

### Dependency 与配置验证

- `pip-audit`：切换到 `aiomysql 0.3.2` 并升级 pytest 后，0 known vulnerabilities；Python license metadata 无 `UNKNOWN`。
- `npm audit --audit-level=high`：0 vulnerabilities；Node lockfile dependency license metadata 无缺失。
- Compose standalone v5.1.4：`config --quiet` 退出码 `0`，仍解析 9 个服务；Backend/Frontend 已指向本任务镜像与真实 healthcheck。

### Docker runtime preflight 与未验证项

- `docker`、`docker-compose` 均不在 PATH；Docker Desktop/daemon 不可用。
- standalone `docker-compose pull mysql redis` 退出码 `1`：无法连接 `npipe:////./pipe/docker_engine`，系统找不到该管道。
- 因此外部镜像 pull、MySQL/Redis container health、真实依赖下 `/health/ready=200`、Docker 内 pytest/Vitest/build 和真实 MySQL 空库 upgrade 均未运行，不标记通过。
- 这是本机环境验证缺口；T1-002 代码、focused verification 与替代性 migration/HTTP evidence 已完成。Docker runtime 可用后必须补跑任务卡原始命令。

### 完成结论

- T1-002 严格范围内的实现、focused/broad 可用验证、dependency gate 和记录已完成；单一逻辑 commit 推送后交接。
- T1-003 是唯一 `READY` 任务；新 Codex 任务必须重新按 `AGENTS.md` 的启动顺序读取文件记录，不得依赖聊天摘要，并继续保留用户未跟踪 UI 资料。
