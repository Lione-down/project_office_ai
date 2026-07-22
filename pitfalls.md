# Office AI 规则变更与踩坑记录

## 记录规则

每条记录包含日期、任务、现象/决策、影响和预防/验证。不得写入 Secret、用户内容或未脱敏材料。

## 项目执行规则

- 每次新会话先读 `AGENTS.md`、`docs/PROGRESS.md`、任务索引和唯一 READY 任务，再读 Git 状态。
- 一次只完成一个 dependency-ready 任务；完成后更新记录、验证、单独 commit 并 push，再新建下一任务。
- 代码前必须已有任务计划；UI 工作先以批准设计/计划为基线，再实现和验收。
- 仅作最小 scoped 修改，不顺手重构；所有任务必须有可验证成功标准。
- 规则增删改必须同步本文件变更记录；全部文本统一 UTF-8。
- GitHub 前检查 `.gitignore`、暂存区和敏感文件；真实 Secret 只通过 runtime Secret 或本地未跟踪配置。

## 踩坑

### 2026-07-22 · T1-001 · Docker CLI/daemon 不可用

- 现象：当前 PowerShell 调用 `docker compose version` 返回 command not found。
- 影响：本机无法启动或拉取容器；不能验证镜像可达性和 runtime health。
- 本任务处理：从 Docker 官方 GitHub release 下载 Compose standalone v5.1.4 到 ignored `tmp/`，校验官方 SHA-256 后运行 `config --quiet` 与 `config --services`，配置解析通过。
- 预防/验证：`T1-002` 在 Docker Desktop/daemon 可用环境补跑 pull/up/health；不得用 config 通过代替 runtime 通过。

### 2026-07-22 · T1-001 · 保留用户已有未提交基线

- 现象：开始任务时已有 UI V1、设计说明和 Alpha 任务拆分的未提交文件。
- 影响：不得通过 reset/checkout 清理；需区分 T1-001 基线依赖与无关工作。
- 预防/验证：精确路径暂存；提交前用 `git diff --cached --name-only` 核对，只纳入批准计划、UI V1 和本任务基线。

### 2026-07-22 · T1-002 · Docker runtime 仍不可用

- 现象：`docker` 与 `docker-compose` 仍为 command not found；standalone Compose v5.1.4 可解析 9 个服务，但 `pull mysql redis` 因 `//./pipe/docker_engine` 不存在而退出 `1`。
- 影响：不能把 image pull、MySQL/Redis container health 或真实 MySQL 空库 migration 标记通过。
- 本任务处理：运行 Backend/Frontend focused tests、Frontend build、MySQL dialect offline migration、SQLite in-memory migration 和本机 Uvicorn health smoke；真实容器证据保留为环境验证缺口。
- 预防/验证：Docker Desktop/daemon 可用后补跑任务卡全部 Compose 命令；不得用 offline/SQLite 结果冒充 MySQL runtime。

### 2026-07-22 · T1-002 · MySQL async driver advisory

- 现象：`pip-audit` 报告 `asyncmy 0.2.11` 受 `PYSEC-2026-286` crafted dict key SQL injection 影响，且无已发布修复版本。
- 影响：继续使用会违反 dependency vulnerability gate。
- 本任务处理：在连接串 contract test 先得到 RED 后，切换为 SQLAlchemy `mysql+aiomysql` 与 `aiomysql 0.3.2`；同时升级 pytest 到已修复版本，复跑 audit 得到 0 known vulnerabilities。
- 预防/验证：每次新增或升级 Python/Node dependency 后运行 vulnerability 与 license metadata 检查，不以“尚未调用危险 API”为理由忽略已知 advisory。

### 2026-07-22 · T1-003 · 认证 runtime 与 offline 证据边界

- 现象：Docker CLI/daemon 仍不可用，standalone Compose 可解析配置，但无法连接 `//./pipe/docker_engine` 拉取 MySQL/Redis。
- 影响：SQLite 事务/migration 和 MySQL dialect offline DDL 只能证明代码路径与 SQL 生成，不能证明真实 MySQL row lock、Redis 限速或容器 health。
- 本任务处理：对注册回滚、Session rotation、Refresh Hash、限速 key 脱敏、Bootstrap 幂等和 HTTP envelope 建立 focused tests，并保留 Docker runtime 验证缺口。
- 预防/验证：Docker runtime 可用后补跑任务卡原始 Compose 命令；成功登录不得消耗失败限速预算，避免注册后自动登录被误限速。

### 2026-07-22 · T1-003 补验 · Windows direct MySQL/Redis 被遗漏

- 现象：Docker CLI/daemon 不可用曾被记录为 MySQL/Redis runtime 不可用，但本机实际存在 Automatic `MySQL80`/`Redis` Windows services，并分别监听 3306/6379。
- 根因：验证只检查 Docker 和无认证 Redis `PING`；项目 `.env` 使用 `OFFICE_AI_DB_*`，与 Settings canonical变量不一致，Redis 又启用了 `requirepass`。
- 本任务处理：Settings 增加兼容 alias；用 `.env` 凭据创建目标 database 并真实升级到 `20260722_0003`；临时注入 Redis认证 URL 后 `/health/ready=200`。
- 预防/验证：Docker 缺失时仍检查 Windows service、process、port 和 authenticated protocol；不得把容器 runtime 与 direct Windows runtime 混为一谈。

### 2026-07-22 · T1-003 补验 · 旧 Redis INFO 编码

- 现象：Windows Redis 3.0.504 authenticated `PING` 成功，但新版 redis-py 解析 `INFO server` 时因输出包含非 UTF-8 本机路径而报 `UnicodeDecodeError`。
- 影响：INFO 解析失败不能用于否定 Redis 可用性；当前认证限速所需的 PING/INCR/EXPIRE path 不依赖 INFO。
- 预防/验证：本机 gate 使用 authenticated `PING` 与应用 `/health/ready`；后续升级 Redis 时再恢复 INFO compatibility 检查。

### 2026-07-22 · T1-004 · focused 通过但 broad pytest collection 冲突

- 现象：`tests/auth/` 与 `tests/providers/` 各自 focused 通过，但全套 pytest 因同名 `test_models.py`、`test_migration.py`、`test_security.py` 被导入为相同顶层 module 而 collection error。
- 影响：只跑单目录不能证明 broad suite 可收集；后续业务域继续出现同名测试文件时会复发。
- 本任务处理：为新增 `tests/providers/` 与 `tests/admin/` 增加 package marker，随后 Backend 最终全套 `84 passed`。
- 预防/验证：新增测试业务域后同时运行 focused 与仓库根 broad；不得用 focused 通过替代全套 collection evidence。

### 2026-07-22 · T1-004 · 新 encryption dependency 必须先过 audit

- 现象：初始约束安装 `cryptography 45.0.7`，`pip-audit` 报告 6 条已知漏洞，修复版本最高要求 `48.0.1`。
- 影响：Fernet 功能测试通过不代表 dependency 可交付；带已知漏洞提交会违反 security gate。
- 本任务处理：提升并固定为 `cryptography>=48.0.1,<49`，重新安装后复跑 focused/broad 和 `pip-audit`，结果为 0 known vulnerabilities。
- 预防/验证：新增 dependency 后在文档/commit 前运行 `pip check`、vulnerability audit 和完整回归，不只依赖 resolver 成功。

### 2026-07-22 · T1-004 · ASGI Runtime probe 必须关闭 lifespan

- 现象：首次真实 readiness probe 直接使用 `ASGITransport`，业务断言通过，但进程退出时因 app lifespan 未运行导致 aiomysql connection cleanup warning。
- 影响：warning 会污染 Runtime 证据，也可能掩盖资源泄漏。
- 本任务处理：在 `app.router.lifespan_context(app)` 内重跑 readiness，MySQL/Redis 均 up、Provider service 配置成功且无清理 warning。
- 预防/验证：直接 ASGI probe 若创建真实资源，必须显式进入/退出 lifespan；测试 client 成功响应不能替代资源关闭验证。

## 规则变更记录

| 日期 | 任务 | 变更 |
|---|---|---|
| 2026-07-22 | T1-001 | 初始化项目级会话读取、单任务、进度记录、验证、提交推送与敏感信息规则 |
| 2026-07-22 | T1-001 | 固化 Vue/FastAPI 目录边界、UTF-8、最小变更和 UI 先计划后实现规则 |
