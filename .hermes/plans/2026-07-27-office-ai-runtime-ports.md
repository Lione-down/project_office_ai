# Office AI 默认运行端口迁移计划

- 日期：`2026-07-27`
- 类型：Internal Alpha 封版后的单一运维配置变更
- 状态：`DONE`
- 用户要求：Frontend 默认 Host port 固定为 `8888`，Backend 默认 Host port 固定为
  `9999`，并使用这两个端口重启项目。

## 范围

1. 将 Compose 的 Frontend/Backend 默认 Host port 从 `5173/8000` 改为
   `8888/9999`。
2. 将 Frontend 默认 API base URL 改为 `http://localhost:9999/api/v1`。
3. 将 Backend 默认允许的 Frontend origin 改为 `http://localhost:8888`。
4. 保留容器内部端口 `5173/8000`，不修改 private-network service contract。
5. 同步 contract test、README、环境文档与进度记录。
6. 使用默认配置重建 Frontend/Backend，并验证页面、readiness、MySQL/Redis 和 API
   docs。

## 不在范围

- 不修改 API、Schema、业务逻辑、用户数据、Credential 或根 `.env`。
- 不停止或修改占用旧端口的 `project_revid` 进程。
- 不改变 MySQL、Redis、Renderer、OCR、LibreOffice 或 ClamAV 的网络暴露边界。

## RED / GREEN Contract

- RED：先要求 Compose 默认值包含 Frontend `8888`、Backend `9999`、API base
  `http://localhost:9999/api/v1` 和 origin `http://localhost:8888`；旧配置应使测试按
  预期失败。
- GREEN：只修改 Compose 默认值与对应文档，使 focused contract 通过。
- Regression：运行 Compose contract tests、release contract、`docker compose config`
  和 `git diff --check`。

## Runtime 验收

1. `docker compose up -d --force-recreate --wait --wait-timeout 180 backend frontend`
   使用仓库默认值成功。
2. `http://127.0.0.1:8888` 返回 HTTP 200。
3. `http://127.0.0.1:9999/health/ready` 返回 `ready`，MySQL/Redis 均为 `up`。
4. `http://127.0.0.1:9999/docs` 返回 HTTP 200。
5. `docker compose ps` 显示 `8888->5173` 和 `9999->8000`，全部 9 个服务 healthy。

## Git 与保护边界

- 只精确暂存本变更拥有的计划、Compose、测试与文档路径。
- 不暂存 `.env`、`.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/`、
  ignored `output/`、Secret 或用户文件。
- focused、runtime、security 与 staged checks 通过后形成一个 conventional commit
  并推送 `origin/main`。

## 完成证据

- RED：旧默认端口使 focused contract 按预期失败。
- GREEN：Compose contract `3 passed`；与 release contract 合计 `9 passed`。
- Runtime：Frontend `8888`、Backend `9999` 重建成功，9/9 services healthy；
  Frontend、readiness、API docs 与 CORS 均通过。
- Git：以本计划声明的 exact paths 完成 security/staged checks、单一 commit 与 push
  后闭环。
