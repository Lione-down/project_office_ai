# Project Office AI

面向销售及通用办公场景的 AI Office 文件生成项目。首个内部 Alpha 目标是在本地完成真实材料到 PPTX 与 XLSX 的双输出闭环。

## 当前状态

项目按 20 个 dependency-ordered 任务实施。当前进度和下一任务以 `docs/PROGRESS.md` 为准；批准后的总计划位于：

`.hermes/plans/2026-07-22_000414-office-ai-alpha.md`

新会话开始前依次读取：

1. `AGENTS.md`
2. `docs/PROGRESS.md`
3. `.hermes/plans/office-ai-alpha-tasks/README.md`
4. 唯一 `READY` 任务文档

每完成一个任务，必须更新进度记录、运行任务验证、产生一个逻辑 commit 并推送，再由新 Codex 任务继续下一项。

## 核心技术方向

- Vue 3 + TypeScript
- FastAPI + MySQL 8.0 + Redis
- Agnes Provider Adapter
- PptxGenJS
- XlsxWriter + openpyxl
- LibreOffice Headless
- ClamAV + PaddleOCR
- Docker Compose

## T1-003 认证入口

认证服务要求通过 runtime Secret 配置 `OFFICE_AI_SESSION_SECRET`。初始管理员只允许通过未跟踪的 runtime environment 提供 `OFFICE_AI_BOOTSTRAP_ADMIN_PHONE` 与 `OFFICE_AI_BOOTSTRAP_ADMIN_PASSWORD`，迁移后执行：

```powershell
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m app.commands.bootstrap_admin
```

Bootstrap 不含默认手机号或密码，重复执行不会修改已有管理员密码。管理员登录后通过 `POST /api/v1/admin/invite-codes` 创建邀请码；创建响应仅一次返回完整 code。

## 本地验证入口

项目默认 Host ports 固定为 Frontend `8888`、Backend `9999`；容器内部仍使用
`5173/8000`。启动完整项目：

```powershell
docker compose up -d --wait
```

- Frontend：`http://localhost:8888`
- Backend readiness：`http://localhost:9999/health/ready`
- API docs：`http://localhost:9999/docs`

Docker runtime 可用时：

```powershell
docker compose up -d mysql redis
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend pytest tests/auth -q
```

Docker 不可用时，只能运行不替代 MySQL/Redis runtime 的 focused verification：

```powershell
backend\.venv\Scripts\python.exe -m pytest -q
backend\.venv\Scripts\python.exe -m pytest backend/tests/auth -q
Set-Location frontend
npm run test
npm run build
```

## 敏感信息规则

- 不提交 `.env`、`.env.*`、API Key、Token、密码、证书或私钥。
- 不提交 `backend/files/` 中的用户文件、OCR 结果、预览和生成文件。
- 不提交数据库数据目录、日志、缓存或临时文件。
- 真实配置只通过本地环境变量或未来的 Secret 管理服务提供。
- 提交模板和黄金测试文件前，必须确认版权许可并完成数据脱敏。

## Git 提交前检查

```powershell
git check-ignore -v .env
git status --short
git diff --cached --name-only
```

只有确认暂存区不包含敏感信息后才能推送到 GitHub。

## 基线文档

- `docs/PLAN.md`：Alpha scope、架构、状态机、Gate 与完成定义
- `docs/API.md`：`/api/v1` 用户端和管理端 contract
- `docs/DATA_MODEL.md`：21 张 Alpha 表与事务边界
- `docs/ENVIRONMENT.md`：环境变量名称与安全录入方式
- `docs/SECURITY.md`：身份、文件、Provider、账务、日志和容器边界
- `docs/ui-v1/README.md`：已批准 UI V1 视觉与交互基线
