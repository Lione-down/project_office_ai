# Office AI 项目执行规范

本文件适用于仓库根目录及全部子目录。开始任何实现前，必须先读取本文件和项目记录，不得仅依赖聊天上下文。

## 会话启动顺序

1. 读取 `docs/PROGRESS.md`，确认当前完成项、验证证据、阻塞和唯一下一任务。
2. 读取 `.hermes/plans/office-ai-alpha-tasks/README.md` 和下一任务文档。
3. 读取 `docs/PLAN.md`；涉及接口、数据、安全或环境时，再读取对应专题文档。
4. 执行 `git status --short --branch`，保留并识别用户已有改动。
5. 只有当前置任务为 `DONE` 且目标任务为 `READY` 时才开始实现。

## 单任务工作流

- 同一会话只完成一个 dependency-ready 任务，不提前实现后续任务。
- 修改代码前，以任务文档中的目标、范围、验收和验证命令作为成功标准。
- 先做 focused verification，再做任务要求的 broad verification；未实际运行的检查不得标记通过。
- 每次任务结束前更新 `docs/PROGRESS.md`，记录 changed files、验证命令与结果、阻塞、决策和下一任务。
- 范围或接口发生批准内变化时，同步更新 `docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md` 或 `docs/SECURITY.md`。
- 每个任务只产生一个逻辑 commit，并在验证和敏感信息检查通过后推送。

## 工程边界

- 前端使用 Vue 3 + TypeScript，并遵循 `views/`、`modules/`、`components/`、`composables/`、`api/`、`types/`、`utils/` 的既有职责。
- FastAPI 按 `api/v1`、`controllers`、`core`、`models`、`schemas`、`settings`、`utils` 分层，不跨层混放业务逻辑。
- MySQL 是持久化事实来源；Redis 仅用于队列、锁、限流和进度，不承载唯一业务状态。
- 文件二进制只存放于受控存储，不能作为静态目录公开；下载和预览必须通过鉴权 API。
- 保持 UTF-8 编码，文件名使用小写 kebab-case；只在确实降低复杂度时增加抽象。

## 安全与 Git

- 用户已长期授权 Agent 在本项目工作时按最小必要原则读取仓库根目录 `.env`，仅用于项目 runtime、真实 Agnes Contract 和配置验证；不得打印、回显、记录、复制到其他文件、暂存、提交或推送其中任何值。除此唯一例外外，仍禁止读取 `.env.*`、`*.env`、`*.env.*`、`*.env.example` 以及误拼的 `.ene`、`.ene.*`、`*.ene`、`*.ene.*`；所有环境配置文件即使只包含示例值也不得进入 Git。API Key、Token、密码、证书、私钥、用户文件和未脱敏黄金材料同样禁止进入 Git。
- Provider credential 只通过管理后台或本地未跟踪配置录入；解析 worker 不得挂载 credential，且不得访问公网。
- 提交前至少运行 `git check-ignore -v .env`、`git diff --check`、`git diff --cached --name-only` 和 `git status --short`。
- 使用精确路径暂存本任务拥有的文件，不使用 `git add .`，不混入用户无关改动。
- commit 使用 `type(scope): subject`；不可逆操作必须先获得用户确认。

## 记录与踩坑

- 规则变更和重复风险同步写入 `pitfalls.md` 的变更记录。
- 遇到环境缺失或外部依赖不可用时，在 `docs/PROGRESS.md` 记录命令、原始结论和影响，不伪造通过。
- 任务只有在交付、验证、记录、commit 和 push 全部完成后，才能标记 `DONE` 并交接下一任务。
