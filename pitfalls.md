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

## 规则变更记录

| 日期 | 任务 | 变更 |
|---|---|---|
| 2026-07-22 | T1-001 | 初始化项目级会话读取、单任务、进度记录、验证、提交推送与敏感信息规则 |
| 2026-07-22 | T1-001 | 固化 Vue/FastAPI 目录边界、UTF-8、最小变更和 UI 先计划后实现规则 |
