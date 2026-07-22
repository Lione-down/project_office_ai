# Office AI Alpha 进度记录

- 最后更新：`2026-07-22`
- 最近完成：`T1-003 用户、Session 与邀请码`
- 下一任务：`T1-004 Provider、Credential 与模型后台`
- 当前状态：`T1-004 READY`
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
| T1-003 | DONE | T1-002 | `feat(auth): add invite based phone authentication`；Docker runtime 缺口见下文 |
| T1-004 | READY | T1-003 | Provider、Credential 与模型后台 |
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

## T1-003 执行记录

### 范围

- 建立 `users`、`user_sessions`、`invite_codes`、`credit_ledger` 模型与 additive migration `20260722_0002`；UUID 使用 `BINARY(16)`，MySQL 时间编译为 `DATETIME(6)`。
- 实现 `+86` 邀请码注册、登录、Refresh rotation、退出、当前用户、修改密码、管理员 reset service policy，以及管理员邀请码创建/脱敏查询 API。
- 密码使用 Argon2id；Access Token 使用 HS256 且关联数据库 Session；Refresh Token、邀请码分别只保存 SHA-256 hash、peppered HMAC hash。
- 注册在单一事务中锁定并消费邀请码、创建用户、追加 `registration_grant`、同步余额；流水写入失败时四项整体回滚。
- 实现 Redis 失败限速、注册/邀请码限速、runtime-only 幂等管理员 Bootstrap；未实现短信、找回、微信、Workspace、T1-004 Provider 能力或 T4-002 audit HTTP 闭环。

### Changed files

- Models/Migration：`backend/app/models/{base,users,user_sessions,invite_codes,credit_ledger}.py`、`backend/alembic/versions/20260722_0002_auth_and_invites.py`、`backend/alembic/env.py`。
- Services/Runtime：`backend/app/services/auth_*.py`、`backend/app/services/rate_limit.py`、`backend/app/core/{application,database,errors,redis}.py`、`backend/app/settings/config.py`、`backend/app/commands/bootstrap_admin.py`。
- API/Schemas：`backend/app/api/v1/{auth,invite_codes}.py`、`backend/app/api/router.py`、`backend/app/schemas/{auth,invites}.py`。
- Tests/Dependencies：`backend/tests/auth/**`、`backend/pyproject.toml`；新增 `argon2-cffi` 与 `PyJWT`。
- Runtime/Docs：`docker-compose.yml`、`README.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md` 与 T1-003/T1-004 状态。
- 未触碰：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`。

### TDD 与 focused verification

- RED：依次确认 auth security/settings、4 个模型与注册事务、Session/rate limit、migration/Bootstrap/HTTP、邀请码管理、失败限速预算、UTC 时间归一化、MySQL `DATETIME(6)` 和空 Secret fail-closed 在实现前按预期失败。
- GREEN：`backend/.venv/Scripts/python.exe -m pytest backend/tests/auth -q`，`36 passed`。
- 注册 rollback test 通过 SQLAlchemy `before_insert` 触发真实流水写入异常，验证 user/ledger 均为 0、invite `used_count` 保持 0。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；无超过 500 行的 Python 文件。

### Broad verification 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`44 passed`。
- Alembic：`heads` 为 `20260722_0002 (head)`；SQLite 临时空库 `upgrade head` 由 test 通过；MySQL dialect `upgrade head --sql` exit `0`，包含 `BINARY(16)`、`DATETIME(6)` 与两条命名外键。
- Compose standalone v5.1.4：`config --quiet` exit `0`。
- `pip-audit`：0 known vulnerabilities；仅按预期跳过本地非 PyPI package `office-ai-backend`。9 个 direct production dependency license metadata 均存在。
- 全套测试曾发现 Alembic `fileConfig` 禁用应用 logger 的全局状态污染；改为 `disable_existing_loggers=False` 后既有 request log regression 通过。

### Docker runtime preflight 与未验证项

- `docker`、`docker-compose` 均不在 PATH，Docker Desktop/daemon 不可用；standalone `pull mysql redis` exit `1`，缺少 `npipe:////./pipe/docker_engine`。
- 任务卡三个命令均已用 standalone Compose 实际尝试：Auth pytest、`alembic upgrade head`、Backend broad pytest 分别 exit `1`，都在容器创建前因缺少 engine pipe 失败。
- 因此真实 MySQL row lock/空库 migration、Redis rate limit/Session runtime、容器内 36/44 tests 与 health 均未验证；SQLite/offline 结果不代表这些 runtime 通过。Docker 可用后必须原样补跑任务卡命令。

### 安全与决策

- Session Secret、Bootstrap 手机号/密码均无源码默认值；Compose 空字符串归一化为未配置，Session Secret 少于 32 字符、Bootstrap 密码少于 12 字符会拒绝。
- token 响应与一次性邀请码响应使用 `Cache-Control: no-store`；错误 envelope 和 request log 不记录 body，不回显密码、邀请码或 Token；限速 Redis key 只含 SHA-256 摘要。
- 管理员 reset 已实现密码 Hash、强制改密和 Session 撤销的 service behavior；为避免绕过 re-auth、reason 和 audit，`/admin/users/{id}/reset-password` HTTP 端点留给 `T4-002`，未暴露半成品敏感接口。

### 完成结论

- T1-003 严格范围内实现、focused/broad 可用验证、dependency gate、环境缺口与文档记录已完成；单一逻辑 commit 推送后交接。
- T1-004 是唯一 `READY` 任务；新会话必须重新按 `AGENTS.md` 启动顺序核对 current Git/runtime 状态，不得提前进入 T1-005。

## T1-003 本机 Runtime 补验

### 授权与范围

- 用户明确授权本次执行在进程内读取项目 `.env`，使用其中 MySQL 连接信息创建目标 database 和表结构；所有 Secret 均未回显、写入文档或提交。
- 本补验没有进入 T1-004，只修正 T1-003 的 direct Windows runtime、现有 `.env` 变量兼容和认证 schema 中文 COMMENT。
- 未修改历史 migrations `20260722_0001`/`20260722_0002`，新增 additive `20260722_0003_auth_schema_comments.py`。

### Runtime 调查与根因

- Windows services：`MySQL80`、`Redis` 均为 `Running / Automatic`；3306/6379 均监听并可连接。
- MySQL：8.0.43，`.env` 凭据认证成功且目标 database 原先不存在。
- Redis：Windows Redis 3.0.504，启用 `requirepass`；无认证返回 `NOAUTH`，从 service config 临时注入认证后 `PING=True`。
- 先前 runtime 缺口的根因是只检查 Docker；同时 `.env` 使用 `OFFICE_AI_DB_*`，Settings 只接受 canonical MySQL变量，且 `.env` 没有 Redis URL。

### 实现与数据库结果

- Settings 使用 `AliasChoices` 兼容 `OFFICE_AI_DB_HOST/PORT/NAME/USER/PASSWORD`，canonical变量仍优先；应用仍不自动读取 `.env`。
- 4 个 ORM tables 和全部 columns 增加中文 comment；ORM unique constraints/indexes/FKs 与历史 `20260722_0002` 精确对齐。
- 使用授权连接创建目标 database，字符集 `utf8mb4`、collation `utf8mb4_0900_ai_ci`；真实 Alembic upgrade 从 base 运行到 `20260722_0003`。
- `information_schema`：4/4 table comments、41/41 column comments 非空；`alembic current=20260722_0003`，`alembic check` 为 `No new upgrade operations detected`。

### 验证

- TDD RED：DB alias、ORM中文 comments、Alembic 0003/offline COMMENT、constraint/index/FK 对齐测试均在实现前按预期失败。
- Focused：`backend/.venv/Scripts/python.exe -m pytest backend/tests/auth -q`，`41 passed`。
- Broad：Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`，`49 passed`。
- Quality：`ruff check app tests alembic`、`ruff format --check app tests alembic` 均通过。
- Live readiness：使用 `.env` MySQL配置并临时注入 Redis认证 URL，`GET /health/ready` 返回 `200 ready`，dependencies 为 `mysql=up`、`redis=up`。
- Redis `INFO server` 因旧 Windows build 输出含非 UTF-8 本机路径而与新版 redis-py 解码不兼容；不影响 authenticated PING 和 readiness，本项不伪装为 INFO 通过。

### Changed files 与交接

- Backend：`backend/app/settings/config.py`、认证 4 个 model files、`backend/alembic/versions/20260722_0003_auth_schema_comments.py`、相关 auth tests。
- Records：T1-003 task、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- `.env` 未修改、未暂存；`design-system/` 和旧版 `docs/ui-mockups/` 继续保留为用户未跟踪文件。
- T1-004 仍是唯一 `READY` 任务；后续本机启动必须以本地 Secret 提供 `OFFICE_AI_REDIS_URL`。
