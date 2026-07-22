# T1-001 工程与文档基线

- 状态：`DONE`
- Depends on：无
- 来源：总计划第 2–5、13–19 节与 Day 1
- 建议 commit：`chore(project): establish office ai alpha baseline`

## 目标

建立可执行、可审计且不泄露敏感信息的项目基线，使后续代码任务共享同一架构、数据、安全、环境和进度口径。

## 交付范围

- 创建 `AGENTS.md`、`docs/PLAN.md`、`docs/PROGRESS.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`pitfalls.md`、`docker-compose.yml`。
- 审阅并按需更新已有 `README.md` 与 `.gitignore`，不得覆盖其中已经正确的敏感信息规则。
- Compose 明确定义 `frontend`、`backend`、`worker`、`ppt-renderer`、`mysql`、`redis`、`clamav`、`paddleocr`、`libreoffice` 九个服务及健康检查/依赖关系。
- `docs/PLAN.md` 保留总计划已锁定范围；`docs/PROGRESS.md` 初始化任务状态、验证证据、阻塞和下一步字段。

## 实施步骤

1. 将总计划的目标、范围、架构、状态机、质量门禁和完成定义同步到项目文档，不扩充 Alpha 范围。
2. 在 `docs/ENVIRONMENT.md` 列出变量名称、用途、是否敏感和安全录入方式；不创建、读取或提交真实密钥。
3. 在 `docs/SECURITY.md` 固化文件隔离、密钥、审计、日志脱敏和管理员权限边界。
4. 建立 Compose 配置和持久卷边界，容器默认非 Root；解析 Worker 不挂载 Provider 密钥且无公网访问。
5. 在 `pitfalls.md` 建立规则变更与踩坑记录格式，并记录本任务确认的项目执行规则。

## 验收标准

- 文档之间对 Alpha 范围、21 张表、九个服务和四周 Gate 的描述无冲突。
- `.env`、`backend/files/`、输出、日志、缓存、数据库目录和私有黄金数据均被忽略。
- `docker compose config` 退出码为 0，且九个服务均出现在解析结果中。
- `git status --short` 不显示 `.env`，暂存区不含任何敏感文件。

## 验证

```powershell
docker compose config
git check-ignore -v .env
git status --short
git diff --check
```

## 非范围与回滚

- 不启动容器、不创建业务模型、不实现 API 或 UI。
- 若 Compose 依赖暂不能拉取，配置解析仍必须通过；把镜像可达性作为明确阻塞记录，不能伪造完成。
- 回滚只删除本任务新增的基线文件或恢复本任务对已有文档的精确修改，不触碰本地 `.env`。

## 完成记录

- 完成日期：`2026-07-22`
- 交付：项目执行规则、Alpha scope、API、21 张表、环境、安全、进度、踩坑与 9 服务 Compose 基线。
- 验证：官方 Docker Compose standalone `config --quiet` 退出码 0，9 个服务解析通过；UTF-8、任务链接、ignore、Secret pattern 和 `git diff --check` 通过。
- 环境边界：本机无 Docker daemon，未验证镜像 pull 与 runtime health；该验证由 `T1-002` 在 Docker 可用环境补齐。
- Commit：`chore(project): establish office ai alpha baseline`。
