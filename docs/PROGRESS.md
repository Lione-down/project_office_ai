# Office AI Alpha 进度记录

- 最后更新：`2026-07-23`
- 最近完成：`T2-002 OCR 与 Evidence Manifest`
- 下一任务：`T2-003 术语库与证据标准化`
- 当前状态：`T2-003 READY`
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
| T1-004 | DONE | T1-003 | `feat(provider): add encrypted multi provider model registry`；验证证据见下文 |
| T1-005 | DONE | T1-004 | `feat(asset): add isolated local asset management`；验证证据见下文 |
| T2-001 | DONE | T1-005 | `feat(parser): add sandboxed office file ingestion`；验证证据见下文 |
| T2-002 | DONE | T2-001 | `feat(evidence): add traceable ocr and evidence manifests`；验证证据见下文 |
| T2-003 | READY | T2-002 | 术语库与证据标准化 |
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

### Runtime 本地配置闭环

- 用户后续明确授权编辑本项目 `.env`；先按无认证默认 URL 验证得到 `503`、`mysql=up`、`redis=down`，与 Redis CLI 的 `NOAUTH` 一致。
- 用户提供的候选 Redis Secret 经仅进程内 authenticated `PING` 验证成功；随后只在 ignored `.env` 中配置默认 `127.0.0.1:6379` 的认证 URL，未改动 Windows Redis service config。
- 重新加载 `.env` 后，真实 `GET /health/ready` 返回 `200 ready`，dependencies 为 `mysql=up`、`redis=up`；Secret 未写入 tracked files、暂存区、日志或本文档。

### Changed files 与交接

- Backend：`backend/app/settings/config.py`、认证 4 个 model files、`backend/alembic/versions/20260722_0003_auth_schema_comments.py`、相关 auth tests。
- Records：T1-003 task、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- `.env` 已在用户明确授权下写入本机 Redis URL，保持 ignored 且未暂存；`design-system/` 和旧版 `docs/ui-mockups/` 继续保留为用户未跟踪文件。
- T1-004 仍是唯一 `READY` 任务；新会话必须从 `AGENTS.md`、本文件、任务索引、T1-004 任务卡和专题文档重新读取事实，不得仅依赖聊天交接。

## T1-004 执行记录

### 范围

- 建立 `ai_providers`、`provider_credentials`、`ai_models`、`audit_logs` ORM 与 additive migration `20260722_0004`；当前实现 8/21 张 Alpha 表。
- 实现管理员 Provider/Credential/Model 创建、列表和白名单 PATCH，Credential health test、重新认证 Reveal、成功/失败审计，以及用户 active/visible 模型列表。
- API Key 使用随机化 Fernet 应用层密文，只持久化密文和 SHA-256 fingerprint；同 Provider fingerprint 唯一，Model 明确绑定 Provider 与 Credential ID。
- 实现 Agnes Adapter 七项固定合同：`validate_configuration`、`test_authentication`、`test_structured_output`、`test_image_url`、`create_chat_completion`、`classify_error`、`extract_usage`。
- 固定 Agnes 默认 Base URL、`agnes-2.0-flash`、保守 `256K` Context 和 120 秒 timeout；本地/私网图片 URL 在请求前拒绝，未实现 T1-005 资产能力。

### Changed files

- Models/Migration：`backend/app/models/{ai_providers,provider_credentials,ai_models,audit_logs}.py`、`backend/alembic/versions/20260722_0004_provider_model_registry.py`、model registry。
- Provider/Services：`backend/app/providers/agnes.py`、`backend/app/services/provider_{security,contracts,admin}.py`、Settings/Application/Error wiring。
- API/Schemas：`backend/app/api/v1/providers.py`、router、`backend/app/schemas/providers.py`。
- Tests/Dependency：`backend/tests/providers/**`、`backend/tests/admin/**`、auth migration chain test、`backend/pyproject.toml`；`httpx` 进入 production dependencies，`cryptography` 固定为已修复的 `>=48.0.1,<49`。
- Records：T1-004/T1-005 task cards、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env` 或真实 Provider Key。

### TDD 与 focused verification

- RED：依次确认 Master Key/cipher、四个 ORM、migration、Credential 密文/重复拦截、Reveal 双向审计、Registry/Model 绑定、Agnes 七项合同、Credential health、Admin HTTP contract、安全列表/PATCH 和 Agnes 配置写入验证在实现前按预期失败。
- REFACTOR：将 Provider DTO/summary/factory 拆到 `provider_contracts.py`，service 498 行；Provider 测试按 health/registry 边界拆分，全部 Python 文件不超过 500 行。
- `backend/.venv/Scripts/python.exe -m pytest tests/providers -q`：`33 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/admin -q`：`2 passed`。
- Mock Contract Test 覆盖 Agnes chat payload、structured output、usage、公开图片 URL gate 与 `400/401/403/429/5xx/timeout` 分类；没有使用或读取真实 Agnes Key，不声称真实 Agnes 兼容已验证。

### Broad、quality 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`84 passed`。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；全套 pytest 曾暴露 auth/providers 同名 test module collection 冲突，增加 package marker 后闭环。
- `alembic heads`：`20260722_0004 (head)`；SQLite 空库 upgrade、MySQL dialect offline 中文 COMMENT 与两项关键唯一约束测试通过。
- `pip check` 通过；首次 `pip-audit` 发现 `cryptography 45.0.7` 已知漏洞，提升到 `48.0.1` 后复跑为 `0 known vulnerabilities`，只按预期跳过本地非 PyPI package。

### 真实 MySQL/Redis Runtime

- 通过用户授权的本机 ignored `.env` 仅向子进程注入 MySQL/Redis 配置，真实 MySQL 从 `20260722_0003` 升级到 `20260722_0004`；`alembic current` 为 Head，`alembic check` 为 `No new upgrade operations detected`。
- `information_schema` 验证 4/4 新表 table comments、52/52 column comments 非空，两项关键唯一约束存在。
- 真实 MySQL transaction probe 使用子进程临时 Master Key 写入 Provider/Credential/Model/Audit 后整体 rollback；验证密文不含 probe plaintext、同 Provider fingerprint 重复写入被唯一约束拒绝、Model 绑定正确，未留下 probe 数据。
- 使用临时进程 Master/Session key 装配真实应用，`GET /health/ready` 返回 `200 ready`，dependencies 为 `mysql=up`、`redis=up`，Provider service 配置成功并通过 lifespan 正常关闭。
- Docker CLI 仍不在 PATH，`docker compose version` 为 command not found；任务卡三个 Compose 入口未运行，不标记容器验证通过。direct Windows focused/broad 与真实 MySQL/Redis 证据不冒充 Docker runtime。

### 安全与决策

- Master Key 缺失/空值/无效时 Provider service fail closed；Master Key 无源码默认值，不落库。常规 Credential 列表固定掩码且不 decrypt，metadata PATCH 不能替换 Key/Fingerprint；轮换以新 Credential ID 和 `rotation_source` 完成。
- Provider 非敏感 JSON config 递归拒绝 `api_key`、Token、密码、Secret、Master Key、Authorization 和 Credential 字段；Credential schema/service 双层拒绝空白 Key，防止绕过专用密文边界。
- Reveal 要求管理员 Session、当前密码和 reason，响应 `Cache-Control: no-store`，成功/失败均只记录脱敏 audit context；Credential test 受 Redis 限速并审计，`401/403` 暂停 Credential，timeout 返回不确定且不自动重试。
- `400` 不重试，`429/5xx` 标记有限重试类别；用户模型查询同时过滤 Provider、Credential、Model active 与 `user_visible`，不静默切换 Provider。

### 完成结论

- T1-004 严格范围内的实现、TDD、focused/broad、真实 MySQL/Redis runtime、dependency/security gate 和文档记录已完成；单一逻辑 commit 推送后闭环。
- T1-005 是下一唯一 `READY` 任务；本会话没有实现 Project、Asset、上传、文件存储或任何 T1-005 代码。

## T1-005 执行记录

### 范围

- 建立 `projects`、`file_assets` ORM 与 additive migration `20260722_0005`；当前实现 10/21 张 Alpha 表。
- 实现用户 Project 创建、列表、改名/归档、空项目软删除，以及无显式项目上传时自动创建默认项目。
- 实现 Local Storage Adapter：固定 `users/{user_id}/quarantine/{asset_id}/original.{ext}`，按 1 MiB chunk 写入、增量 SHA-256、大小 gate 和具体资产目录清理。
- 实现单文件 multipart 上传、扩展名/MIME/minimal signature 初检、Quarantine、幂等重放、资产列表/详情/preview/download/删除与父版本引用检查。
- 实现 owner-scoped 用户 HTTP API 与管理员 service-level role + reason + audit 读取边界；未提前暴露 T4-002 的管理员资产 HTTP/re-auth/delete 闭环，未做 ClamAV、深度 Office/PDF 解析、OCR、OSS 或 Outbox。

### Changed files

- Models/Migration：`backend/app/models/{projects,file_assets}.py`、model registry、`backend/alembic/versions/20260722_0005_projects_and_file_assets.py`。
- Storage/Services：`backend/app/storage/local.py`、`backend/app/services/{asset_contracts,asset_management,asset_uploads}.py`、Settings/Application/Error wiring。
- API/Schemas：`backend/app/api/v1/assets.py`、router、`backend/app/schemas/assets.py`。
- Tests/Dependency：`backend/tests/assets/**`、`backend/tests/security/**`、provider migration chain test、`backend/pyproject.toml`；新增 `python-multipart>=0.0.20,<1`。
- Runtime/Records：`docker-compose.yml`、task README、T1-005/T2-001 task cards、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret 或用户文件。

### TDD 与 focused verification

- RED：模型/migration、Local Storage、service ownership/idempotency/audit/delete、HTTP/settings、12-byte signature probe、Unicode control filename 和 Compose limit contracts 均先观察到目标能力缺失或错误行为后再实现。
- `backend/.venv/Scripts/python.exe -m pytest tests/assets -q`：`56 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/security -q`：`10 passed`；覆盖不可变 UUID key、路径穿越/伪造 key、大小溢出清理、partial/cancellation cleanup、cleanup failure cause、只删除具体资产目录和物理删除失败显式上报。
- 跨用户 get/open 返回同一 `asset_not_found` 404；管理员独立读取写入不含 `storage_key` 的 `asset.admin_read` audit。
- 独立 pre-commit review 首轮发现物理删除静默失败、PATCH null、project state race、默认项目并发和非 IntegrityError orphan file 五项阻断；新增 10 个定向测试先 `10 failed`，最小修复后 `10 passed`，随后 focused/broad 全绿。
- 第二轮独立 review 发现 multipart parser 前缺少 request body bound、partial write 仍有 silent cleanup 两项阻断；最终 auto-fix cycle 的 10 个定向测试先 RED，修复后 `10 passed`，新增 pre-parser ASGI gate 与显式 `quarantine_cleanup_failed`。
- 最终 review 的三项 blocker 由 8 个新回归测试复现为 `8 failed`：未认证上传先进入 multipart parser、`CancelledError` 留下 22-byte partial、写文件前无 durable checkpoint、cleanup 覆盖 signature 主因及 finalization failure 无追踪记录。修复后同组 `8 passed`。
- 独立 re-review 继续发现已完成 idempotency replay 仍进入 multipart parser/spool，以及 cleanup failure 在 HTTP 主异常位置遮蔽 signature/cancellation。新增 5 个定向断言先得到 `3 failed, 1 passed`（随后修正两个误改/缺 header 的 test maintenance 问题），改为 endpoint pre-form replay lookup、original-error-first marker/note、`deleting` checkpoint 与脱敏 recovery log 后 `5 passed`；最终 assets/security 合并 `53 passed`。
- 第二次 re-review 发现多 chunk 低报长度会在 parser 已滚盘后用 disconnect 中止并留下未关闭 spool，且 generic/direct/cancellation recovery log 覆盖不全；额外 multipart 文件也未拒绝。新增 5 个用例先 `5 failed`，改为 middleware 受控 preflight spool、middleware completed replay、统一 recovery logger 和严格单文件 form 后同组 `5 passed`，含 replay 回归共 `6 passed`；最终 assets/security 合并 `58 passed`。
- 第二次 auto-fix 后的最终 re-review probe 确认上述 parser spool、completed replay、direct/generic/cancellation logging 与严格 form blocker 均闭环，但发现 `_finalize_checkpoint` 在 commit 主异常/`CancelledError` 后的 `session.rollback()` 若再抛异常，会覆盖主因且没有 `recovery_failure` marker、安全 note 或 recovery log；fault probe 得到最终 `OSError` 而非原 `CancelledError`。该项阻止 commit。
- 新 goal continuation 重新启用 strict TDD/review workflow；独立 fix agent 对 finalization commit `RuntimeError`/`CancelledError` + rollback `OSError` 组合新增参数化 fault test，先得到 `2 failed`，再将 rollback failure 转为 primary 上的 `recovery_failure=True` 与仅含 `OSError` 类型的安全 note，原样重抛 primary 后 `2 passed`。主 agent 复跑同组、assets/security 与 broad 均通过。
- Fresh reviewer 发现并发相同 key 会把首请求尚未完成的 `uploaded` checkpoint 当作 201 replay，且 unique `IntegrityError` fallback 同样误判。独立 fix agent 新增 service 并发 signature/stream failure + later retry、真实 middleware `uploaded`/`deleting` 零 receive/零 upload 409、unique race 三组参数化用例，先得到 service `4 failed`、HTTP `2 failed`；统一 replay policy 后分别 `4 passed`、`2 passed`，完整 assets 为 `56 passed`。
- 修复后独立 re-review 重新读取 39 个 staged 文件并复跑 incomplete replay、fault recovery、assets/security/broad 与 quality gates，确认普通 lookup、middleware、unique race fallback 和文档一致性全部闭环，结论为 `PASS`，无新增 security/logic blocker。

### Broad、quality、migration 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`150 passed`。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；全部 Python 文件不超过 500 行。
- `alembic heads`：`20260722_0005 (head)`；SQLite 空库完整 upgrade、active default/storage location/user idempotency 三个唯一约束、中文 COMMENT 和 MySQL dialect offline `upgrade head --sql` 通过。
- `pip check` 通过；`pip-audit` 为 `0 known vulnerabilities`，仅按预期跳过本地非 PyPI package；12 个 direct production dependency license metadata 无缺失。

### Runtime 缺口与证据边界

- 任务卡三条命令已逐条实际执行：assets、security、broad Docker pytest 都因 PowerShell `docker` command not found 在容器创建前 exit `1`；不标记容器 runtime 通过。
- Direct Windows focused/broad、SQLite migration、MySQL offline DDL 和 `tmp_path` 受控文件 I/O 通过；这些证据不冒充 Docker volume/non-root 或真实 MySQL `0005` runtime upgrade。
- 当前会话遵守项目规则，未读取 ignored `.env`；因此没有使用已有数据库 Secret 运行真实 MySQL migration。Docker 或经用户明确授权的 Secret 注入环境可用后，应补跑 Compose 原始命令与真实 `alembic upgrade head/check`。

### 安全与决策

- 客户端不能提交或获得磁盘路径/`storage_key`；结构化 key 必须解析为指定 owner/asset UUID 且仍位于受控 root。
- 文件名使用 NFKC、basename、255 字符和 Unicode control category 清理；binary signature 只读取 12-byte header，不把最大 50 MB 文件整体加载内存。
- 用户/幂等键唯一约束与 application lookup 共同保证已完成 replay 在 `request.form()` 前返回；`uploaded`/`deleting` incomplete replay 则稳定返回 `409 asset_upload_in_progress`，两者都保持零 body receive/parser/spool/service upload。普通 lookup 与 unique race fallback 共用 replay policy；signature/stream cleanup 成功删除 checkpoint 后，同 key later retry 可重新成功。storage location 另有唯一约束，文件二进制不进入 MySQL。
- preview/download 使用 `private, no-store`、`nosniff`，preview 额外 `CSP sandbox`；资产保持 `quarantined`，T2-001 完成 ClamAV/深度类型/容量/解析前不得进入 `ready`。
- upload gate 在 body receive 前验证 Bearer Session 与 replay policy；新请求进入 middleware 自有 1 MiB threshold preflight spool，只有声明/实际长度一致且不超过 `max_file_bytes + 64 KiB` 才 replay 给 parser。拒绝路径不创建 parser spool，preflight spool 始终关闭；未认证/completed replay/incomplete conflict 均不消费 body。
- 项目删除当前只允许空项目；资产删除按 `deleting -> deleted` 并检查活动父版本引用。未来 `generation_task_inputs` 建立后必须把历史生成引用加入同一 delete gate。
- 每个用户的活动默认项目通过 generated owner key 唯一约束；上传在文件 I/O 前提交 `uploaded` checkpoint，最终事务锁定并重验 project 后更新 `quarantined`。finalization 异常/cancellation 保留 checkpoint 与具体 storage key，文件始终可恢复追踪。物理删除失败保留 `deleting` 并返回 `asset_delete_failed`，不静默标记成功。
- stream/open/write 失败后的 partial quarantine cleanup 不使用 `ignore_errors`；目录已不存在保持幂等，其他清理失败保留原始 signature/size/stream/cancellation 主因，并以安全 note/marker、`deleting` checkpoint 和脱敏 `asset_recovery_failed` 日志记录恢复失败。人工/适配器直接抛出的 `quarantine_cleanup_failed` 仍稳定翻译，service 不做会覆盖它的二次删除。

### 完成结论

- 最终 review 与两次 re-review 的 parser/replay/storage blocker 已完成 TDD remediation：pre-auth/completed replay 都发生在 receive 前；受控 preflight spool 在 parser 前完整验证并关闭；文件 I/O 前持久化 `uploaded` checkpoint；Local Storage cleanup 保留原始错误、可恢复状态与 direct/generic/cancellation 脱敏日志。
- 当前 direct Windows evidence：assets `56 passed`、security `10 passed`、broad `150 passed`；Ruff check/format、Alembic single head/offline SQL、`pip check`、`pip-audit`、`git diff --check` 均通过。Docker 仍为 command not found，不冒充容器 runtime evidence；未读取 ignored `.env`，未运行真实 MySQL `0005` upgrade。
- T1-005 已通过独立 pre-commit re-review、focused/broad/quality/migration/dependency 与敏感信息门禁；状态与依赖链已收口为 `DONE`，T2-001 是唯一 `READY` 任务。新会话必须按“新会话必读”顺序重新读取文件记录后再实现 T2-001。

## T2-001 执行记录

### 范围

- 建立 Quarantine 资产的完整性复核、ClamAV `INSTREAM` fail-closed 扫描、安全类型/容量门禁、隔离 parser 与结构化输出存储；未新增用户 HTTP API、Evidence Manifest、OCR、Agnes、Redis Outbox 或积分路径。
- 支持 DOCX、PDF、XLSX、CSV、TXT、MD 的版本化结构化结果；XLSM 只读取安全数据并标记宏未执行；PNG/JPG/JPEG/WEBP 通过完整性和解码预算后只生成 `pending_ocr`。
- 拒绝 XLS/PPTX、伪装 MIME、病毒、加密/密码保护、损坏、Zip Bomb、危险 OOXML、DTD/entity、超限文件/PDF/Excel/Archive/结构、不可解码或膨胀图片。
- 持久化 `quarantined -> scanning -> parsing -> ready/rejected`、parser metadata、warnings、稳定错误码和 deterministic parsed-output recovery key；20 文件/200 MiB batch contract 在 claim/scan 前 fail-fast。

### Changed files

- Model/Migration/Schema：`backend/app/models/file_assets.py`、`backend/alembic/versions/20260723_0006_file_processing_metadata.py`、`backend/app/schemas/assets.py`、`backend/app/services/asset_contracts.py`。
- File safety：`backend/app/services/file_safety/` 下 ClamAV client、limits/contracts、深度 validation、安全 parsers、可终止 parser runtime 与 parsed output store。
- Worker/Runtime：`backend/app/workers/asset_processing/`、`backend/app/settings/config.py`、`docker-compose.yml`；worker 使用只读输入 volume、独立限额输出 volume、只读 root、tmpfs、non-root、resource limits 和 internal network，且不挂载 Provider/Master Key。
- Tests/Dependencies：`backend/tests/file_safety/`、`backend/tests/parsing/`、相关 asset/provider migration tests、`backend/pyproject.toml`；新增 `pypdf>=6.14.2,<7` 与 `Pillow>=12.3,<13`。
- Records：T2-001 task card/index、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏黄金材料。

### TDD 与 focused verification

- 首轮按 contracts、ClamAV、各格式真实最小样本、worker state machine、output recovery 和 Compose/settings contract 分组先观察 RED，再最小实现转 GREEN。
- 首次独立 review 发现 delimiter-only CSV/Office 结构预算与 parser timeout、stale processing、截断图片、batch gate 未接入四类 blocker；修复前定向回归为 `13 failed, 36 passed`，随后图片强化 `2 failed`、Windows spawn entrypoint `1 failed`、DOM 前预算/真实 decode/lease 配置 `4 failed`，均完成 GREEN。
- 第二次独立 review 发现 output 落盘后、DB 完成前 hard crash 会留下无 recovery key 的 orphan，以及 API error-code contract 不完整；新增两项定向测试先 `2 failed`，写前 durable deterministic key checkpoint、unknown-code fail-closed registry 和文档 contract 后 `2 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/file_safety -q`：`27 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/parsing -q`：`60 passed`；focused 合并为 `87 passed`。
- 最终独立 pre-commit re-review 复核 crash recovery、stale key、稳定错误码和 staged diff，结论 `PASS`、无 findings。

### Broad、quality、migration 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`238 passed`。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；全部 Python 文件不超过 500 行。
- `alembic heads`：`20260723_0006 (head)`；processing migration 定向测试 `3 passed`，MySQL dialect offline `upgrade head --sql` 生成通过。
- Compose/settings 静态 contract tests 通过：worker 无 Provider/Master Key、输入只读、输出独立且限额、无 external network；这些静态证据不冒充容器 runtime。
- `pip check` 通过；`pip-audit` 为 `0 known vulnerabilities`，仅按预期跳过本地非 PyPI package；14 个 direct production dependency license metadata 无缺失。
- `git diff --cached --check`、staged added-line secret/dangerous-call scan、binary scan 和禁止路径检查均通过；未发现 Secret signature、危险动态执行、新增二进制或用户 UI 资料。

### Runtime 缺口、风险与决策

- 任务卡四条 Docker 命令已逐条实际执行：`docker compose up -d clamav`、file-safety、parsing、backend broad 均因 PowerShell `docker` command not found 在容器创建前 exit `1`；不标记 ClamAV/Compose/non-root/volume runtime 通过。
- Direct Windows focused/broad、SQLite migration contract、MySQL offline DDL 与 `tmp_path` 受控文件 I/O 通过；未读取 ignored `.env`，因此未运行真实 MySQL `0006` upgrade。
- Parser 在 spawned child process 中受 wall-clock timeout，Office XML 在 DOM 前受 member/总结构预算，图片受 bounded structural validation、decoded-size gate 与 Pillow full decode；感染、服务异常、timeout、parser crash 和未知错误码全部 fail closed。
- `scanning/parsing` 超过至少 300 秒且覆盖 scan/parser timeout 与 I/O 余量的 lease 后稳定拒绝；本任务选择安全拒绝而不是自动重试。极慢 I/O 超过 lease 仍会 rejected，未来若引入多 worker 长任务恢复，应增加 owner/heartbeat lease，不在 T2-001 提前实现 T3 orchestration。
- Output write 前先持久化 deterministic recovery key；hard crash 后 stale reconciliation 保留精确 key，不形成不可追踪 orphan。自动物理删除留给后续受审计 recovery，避免与并发恢复误删。

### 完成结论

- T2-001 严格范围内的实现、TDD、两轮独立 review remediation、focused/broad/quality/migration/dependency 与敏感信息门禁已完成；Docker 和真实 MySQL runtime 缺口已如实记录。
- T2-001 以单一逻辑 commit 推送后收口为 `DONE`；T2-002 是下一唯一 `READY` 任务，本会话未实现任何 OCR 或 Evidence Manifest 代码。

## T2-002 执行记录

### 范围

- 建立 internal PaddleOCR HTTP service/client，将图片 OCR 与 T2-001 解析结果统一转换为版本化 `evidence-manifest.v1`；本任务只生成 `source_fact`，不生成 Agnes 推断、`calculated_fact` 或 `ai_inference`。
- 证据位置覆盖 Excel cell、PDF page/BBox、Word paragraph、CSV cell、text line 与 image OCR BBox；每条证据绑定资产 UUID、`sha256:` 版本、原始/标准化值、单位/币种、置信度及 parser/OCR engine 版本。
- 叙述 OCR `<0.75` 产生 warning；数字 OCR `<0.90` 或数字单位未知产生 calculation blocker；冲突币种/单位不做猜测。
- Manifest 写入前持久化 deterministic intended key 与 `building`，严格 Pydantic/JSON Schema 校验后原子落盘，再条件更新为 `valid/ready`；暂时性 OCR 错误按 30/60 秒 backoff 最多 3 次，清理失败或非法 Manifest 均 fail closed。
- 未实现 T2-003 术语库、来源冲突裁决、T2-004 Agnes/Structured Brief、用户证据读取 API 或后续任务能力。

### Changed files

- OCR：`backend/app/services/ocr/`、`backend/ocr-service/Dockerfile`、Compose `paddleocr` service 与 worker OCR 配置。
- Evidence：`backend/app/services/evidence/`、`backend/scripts/export-evidence-schema.py`、`backend/tests/evidence/`。
- State/Model：`backend/app/workers/asset_processing/`、`backend/app/models/file_assets.py`、`backend/alembic/versions/20260723_0007_evidence_manifest_metadata.py`、asset safe-response contracts。
- Parser fidelity：Excel 原 cell、PDF combined transform BBox、Word 原 paragraph index、`backend/app/services/file_safety/pdf_geometry.py` 及对应 tests。
- Deletion lifecycle：owner-scoped 删除同时覆盖原文件、parsed output 与 Manifest；active `scanning/parsing` writer 返回 `409 asset_processing_in_progress`，派生清理失败保留可重试 `deleting`。
- Runtime/Records：`backend/app/settings/config.py`、`backend/app/core/application.py`、`docker-compose.yml`、任务卡/索引、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏黄金材料。

### TDD、review 与 focused verification

- RED：OCR/evidence tests 首次 collection 因目标 modules 不存在而失败；随后按 client/server、Manifest schema/location/confidence/store、worker retry/recovery、migration 与 Compose contract 分组转 GREEN。
- 深度 pre-commit review 发现并修复：Manifest source expansion 内存放大、冲突币种误归一、Word 空段落位置漂移、PDF matrix 未组合、OCR health 早于模型 readiness、历史 migration test 固定最新 head、资产删除遗漏派生输出，以及 active worker/delete race。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/ocr -q`：`10 passed`。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/evidence -q`：`11 passed`。
- OCR/evidence/parsing/assets 邻接回归在删除生命周期修复前为 `142 passed`；最终 broad 覆盖全部新增 fault-injection 与 race tests。

### Broad、quality、migration 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest backend/tests -q`：最终 `265 passed`。
- `ruff check backend/app backend/tests backend/alembic` 与 `ruff format --check backend/app backend/tests backend/alembic` 均通过；项目 Python 文件不超过 500 行。
- `alembic heads`：`20260723_0007 (head)`；Evidence migration SQLite 空库 upgrade 定向 `2 passed`；MySQL dialect offline `upgrade head --sql` 退出码 `0` 并生成 Evidence fields/`DATETIME(6)`。
- `pip check` 通过；Backend `pip-audit` 为 `0 known vulnerabilities`，仅按预期跳过本地非 PyPI package。独立 pinned requirements 对 `paddleocr==3.7.0` 与 `paddlepaddle==3.1.1` 的 audit 均为 `0 known vulnerabilities`。
- JSON Schema export 与 checked-in schema byte-for-byte 一致；Compose/settings contract 证明 OCR 仅在 internal network、non-root/read-only/resource-limited，worker 输入只读、parsed/evidence 输出独立且 bounded，backend 仅为鉴权删除挂载派生 volume。

### Runtime 缺口与证据边界

- 任务卡四条 Docker 命令均已实际尝试；`docker` 与 `docker-compose` 均为 `NOT_FOUND`，在容器创建前失败，因此不标记 PaddleOCR build/model warmup/首图 inference、private network、non-root volume 或 Compose broad runtime 通过。
- Direct Windows focused/broad、SQLite migration、MySQL offline DDL 与 `tmp_path` 原子文件 I/O 通过；未读取 ignored `.env`，未使用本机 Secret，因此没有运行真实 MySQL `0007` upgrade。这些替代证据不冒充 Docker 或真实 MySQL runtime。
- PaddleOCR image 固定 PaddlePaddle `3.1.1`、PaddleOCR `3.7.0` 与 PP-OCRv5 mobile det/rec；模型在 build 阶段预热到 non-root cache，runtime readiness 先构造 engine，再开放 HTTP。Docker 可用后必须补跑任务卡命令和真实首图 inference。

### 安全与决策

- OCR client 只调用 `http://paddleocr:8080`，请求/响应/item 均有预算；网络、timeout、HTTP、JSON/schema、response/item 超限返回稳定错误且不生成证据。
- Manifest 每资产最多 10000 条 evidence，并在 Pydantic object expansion 前执行预算；存储 key 只允许 exact owner/asset UUID path，MySQL 不保存内容、物理路径或用户可见 hash。
- worker 在 Manifest 文件写前提交 intended key；成功条件是 parser、Schema、atomic write 与最终 DB conditional update 全部通过。cleanup 失败保留 exact recovery key；stale processing 标记 `invalid/rejected`。
- 用户删除只按数据库 exact keys 清理原文件、解析结果与 Manifest，不扫描 broad root；`scanning/parsing` 期间拒绝删除，消除 worker 在 `deleted` 后重新写出 orphan 的 race。任一物理清理失败都保留 `deleting`，fault-injection 证明后续重试可完成。
- 历史 migration tests 只验证自身 revision 位于唯一连续链路；只有 T2-002 当前 migration test 固定 `0007` head，避免正常后续 additive migration 制造伪回归。

### 完成结论

- T2-002 严格范围内的实现、TDD、深度 security/architecture/adversarial review remediation、focused/broad/quality/migration/dependency 与文档同步已完成；Docker 与真实 MySQL runtime 缺口已如实记录。
- T2-002 以单一逻辑 commit 推送后收口为 `DONE`；T2-003 是下一唯一 `READY` 任务，新会话必须重新按“新会话必读”顺序读取 live Git 与文档，不得依赖聊天摘要。
