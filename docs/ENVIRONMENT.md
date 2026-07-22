# Office AI Alpha 环境基线

本文只记录变量名称、用途和安全录入方式。禁止把真实值写入本文件、`.env.example`、测试 fixture、日志或聊天。

## 支持环境

- Host：Windows 开发机
- Runtime：Docker Compose；Node.js 和 Python 可用于本地 focused tests
- Data：MySQL 8.0、Redis
- Office 工具：LibreOffice Headless；Week 4 人工验收需要 Microsoft Office 与 WPS
- 外部 Provider：Agnes API，通过管理员创建的加密 Credential 使用

## 环境变量

| 变量 | 用途 | 敏感 | 必需时点 | 安全录入方式 |
|---|---|---:|---|---|
| `OFFICE_AI_ENV` | `local/test` 运行环境 | 否 | T1-002 | Compose/CI 普通变量 |
| `OFFICE_AI_LOG_LEVEL` | 日志级别 | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_FRONTEND_ORIGIN` | 唯一允许的前端 Origin | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_API_BASE_URL` | Compose 提供的前端 API 基址，映射为容器内 `VITE_API_BASE_URL` | 否 | T1-002 | Build/runtime 普通变量 |
| `OFFICE_AI_MYSQL_DATABASE` | MySQL database 名 | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_MYSQL_USER` | MySQL app user | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_MYSQL_PASSWORD` | MySQL app password | 是 | T1-002 | 本地未跟踪环境或 Secret store |
| `OFFICE_AI_MYSQL_ROOT_PASSWORD` | MySQL root password | 是 | T1-002 | 本地未跟踪环境或 Secret store |
| `OFFICE_AI_DATABASE_HOST` | MySQL internal hostname，Compose 默认 `mysql` | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_DATABASE_PORT` | MySQL internal port，默认 `3306` | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_DATABASE_URL` | SQLAlchemy 连接串 | 是 | T1-002 | 运行时组合或本地 Secret，不打印 |
| `OFFICE_AI_REDIS_URL` | Redis internal URL | 视部署 | T1-002 | Compose internal network；生产用 Secret |
| `OFFICE_AI_MASTER_KEY` | Provider credential 应用层加密主密钥 | 是 | T1-004 | OS secret/CI secret；禁止落库和提交 |
| `OFFICE_AI_SESSION_SECRET` | Session 签名/派生 Secret | 是 | T1-003 | OS secret/CI secret；定期轮换 |
| `OFFICE_AI_ACCESS_TOKEN_TTL_SECONDS` | Access Token TTL | 否 | T1-003 | Compose 普通变量 |
| `OFFICE_AI_REFRESH_TOKEN_TTL_SECONDS` | Refresh Token TTL | 否 | T1-003 | Compose 普通变量 |
| `OFFICE_AI_BOOTSTRAP_ADMIN_PHONE` | 初始管理员 `+86` 手机号 | 是 | T1-003 Bootstrap | 仅本地未跟踪环境或 Secret store；无默认值 |
| `OFFICE_AI_BOOTSTRAP_ADMIN_PASSWORD` | 初始管理员密码 | 是 | T1-003 Bootstrap | 仅本地未跟踪环境或 Secret store；无默认值 |
| `OFFICE_AI_FILES_ROOT` | 受控文件根目录 | 否 | T1-005 | Compose path；默认 `/app/files` |
| `OFFICE_AI_MAX_FILE_BYTES` | 单文件上限，默认 50 MB | 否 | T1-005 | `system_settings`/普通变量 |
| `OFFICE_AI_MAX_TASK_BYTES` | 单任务总上限，默认 200 MB | 否 | T1-005 | `system_settings`/普通变量 |
| `OFFICE_AI_CLAMAV_HOST` | ClamAV internal hostname | 否 | T2-001 | Compose DNS 名 |
| `OFFICE_AI_CLAMAV_PORT` | ClamAV port | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_PADDLEOCR_URL` | OCR internal service URL | 否 | T2-002 | Compose internal URL |
| `OFFICE_AI_LIBREOFFICE_URL` | LibreOffice internal service URL | 否 | T3-002 | Compose internal URL |
| `OFFICE_AI_PPT_RENDERER_URL` | PPT renderer internal URL | 否 | T3-002 | Compose internal URL |
| `OFFICE_AI_PROVIDER_TIMEOUT_SECONDS` | Provider 请求 timeout，默认 120 | 否 | T2-004 | Admin config/普通变量 |
| `OFFICE_AI_TASK_TIMEOUT_SECONDS` | 完整任务 timeout，默认 2700 | 否 | T3-001 | Admin config/普通变量 |

### 本机兼容变量

- Settings 同时接受现有本地 `.env` 的 `OFFICE_AI_DB_HOST`、`OFFICE_AI_DB_PORT`、`OFFICE_AI_DB_NAME`、`OFFICE_AI_DB_USER`、`OFFICE_AI_DB_PASSWORD`，分别对应上表的 canonical MySQL变量。
- Canonical变量优先；兼容 alias 只用于保留现有本机配置，不写入 Compose，也不改变部署契约。
- 应用不会自动读取 `.env`。本机命令需使用 `python -m dotenv -f <path> run -- <command>` 或由 OS/IDE 注入；禁止用会回显变量值的命令检查配置。
- 本机 Windows Redis service 启用了密码认证。`OFFICE_AI_REDIS_URL` 必须通过本地未跟踪配置或临时进程环境注入；不得把 service config 中的密码复制到文档或 Git。

## Agnes Credential

- Agnes API Key 不使用固定仓库变量名写入 Compose，也不进入 `system_settings`。
- 管理员通过 `POST /api/v1/admin/credentials` 录入一个 Key；后端使用 `OFFICE_AI_MASTER_KEY` 加密后写入 `provider_credentials`。
- 测试、Reveal、轮换和停用均通过 `credential_id`，不在 worker command、queue payload 或日志中传明文 Key。
- `OFFICE_AI_MASTER_KEY` 缺失时，Credential 创建/Reveal/Provider 调用必须 fail closed。

## Auth 与管理员 Bootstrap

- `OFFICE_AI_SESSION_SECRET` 缺失时 Auth/Invite 路由 fail closed 并返回 `auth_not_configured`；应用不提供源码默认签名 Secret。
- Access Token 默认 900 秒，Refresh Token 默认 2592000 秒；Refresh Token 轮换后旧值立即失效。
- 初始管理员手机号和密码必须同时由 runtime environment 提供。执行 `python -m app.commands.bootstrap_admin` 创建；重复执行只报告已存在，不修改密码，也不记录手机号或密码。
- Bootstrap 完成后应从当前进程环境移除这两个变量；真实值不得写入 Compose 文件、`.env.example`、测试 fixture、日志或聊天。

## 本地文件与卷

| 路径/卷 | 内容 | Git |
|---|---|---|
| `backend/files/` / `app-files` | quarantine、原文件、extracted、preview、output | 必须忽略 |
| `mysql-data` | MySQL 数据 | 必须忽略 |
| `redis-data` | 可丢失 Redis 状态 | 必须忽略 |
| `shared-work` | renderer/QA 临时交换 | 必须忽略或仅 Docker volume |
| `golden-data/private/` | 获授权且脱敏前的本地材料 | 必须忽略 |

## 安全录入与验证

1. 仅在本机未跟踪配置、OS environment 或 CI Secret 中设置敏感值。
2. 不执行会回显 Secret 的诊断命令；应用日志只记录变量是否配置，不记录内容。
3. 提交前运行：

```powershell
git check-ignore -v .env
git status --short
git diff --cached --name-only
```

4. 如果 `.env` 或任何 Secret 文件出现在 Git 状态/暂存区，立即停止提交并处理，不把路径内容复制到聊天。
