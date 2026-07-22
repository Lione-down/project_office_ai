# T1-002 FastAPI、Vue 与数据库骨架

- 状态：`DONE`
- Depends on：`T1-001`
- 来源：总计划第 5、6、12 节与 Day 2
- 建议 commit：`chore(core): bootstrap frontend backend and database`

## 目标

建立遵循现有规范的 FastAPI、Vue 3 和 Alembic 骨架，并打通 MySQL、Redis、统一错误和最小前后端健康链路。

## 交付范围

- `backend/app/` 按 `api/v1`、`controllers`、`core`、`models`、`schemas`、`settings`、`utils` 等边界组织。
- `frontend/src/` 按 `api`、`assets`、`components`、`composables`、`modules`、`router`、`store`、`types`、`utils`、`views` 组织。
- 初始化 `backend/alembic/`，接入 SQLAlchemy 2、Pydantic 2、MySQL 8 和 Redis。
- 提供 `GET /health/live` 与 `GET /health/ready`、结构化日志、Trace ID 和稳定错误响应壳。
- 建立 Vue Router、Pinia 根 Store、请求封装和权限守卫壳。

## 实施步骤

1. 先建立后端健康检查、异常响应和配置加载测试，以及前端启动/路由最小测试。
2. 实现应用工厂、数据库/Redis 生命周期和 readiness 依赖检查。
3. 初始化 Alembic，验证空库升级到当前 Head。
4. 实现前端 API client、路由、Store 和用户/管理员权限元数据，不实现业务页面。
5. 固化 Backend、Frontend 的 test/build 稳定入口并更新环境文档。

## 验收标准

- MySQL 与 Redis 正常时 `/health/ready` 返回 Ready；任一关键依赖不可用时返回非 Ready 且不泄露凭证。
- Backend/Frontend 最小测试通过，Frontend Production Build 无 TypeScript 错误。
- Alembic 可从空库升级到 Head；日志包含 Trace ID 且不包含配置密钥。

## 验证

```powershell
docker compose up -d mysql redis
docker compose run --rm backend pytest -q
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm backend alembic upgrade head
```

## 非范围与回滚

- 不创建用户、Provider、资产或任务业务表。
- 回滚应用骨架和初始无业务数据迁移；不得删除本地数据库卷，除非用户另行确认。
