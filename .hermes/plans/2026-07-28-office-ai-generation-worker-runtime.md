# Office AI Post-Alpha 文件生成 Worker Runtime 修复

- 状态：`DONE`
- 日期：`2026-07-28`
- 用户症状：已确认 Brief 创建文件生成任务后，详情页长期显示 `queued / 0%`，
  输出不可下载且质量检查未开始。

## Root cause

- Backend lifespan 已将 `generation.queued` Outbox 发布到
  `office_ai:generation:queue`。
- MySQL 中目标 generation task、step 和积分 reserve 均已持久化，Redis 中存在对应
  queue message。
- 仓库有 `GenerationQueueConsumer`、`GenerationWorkerService`、PPTX/XLSX Renderer
  与 QA service，但 Compose 没有 generation worker service，也没有 production runner
  注入真实 step executor。因此队列只有 producer，没有 consumer。

## 范围

1. 新增独立、non-root、read-only rootfs 的 generation worker runtime，消费既有
   `office_ai:generation:queue`。
2. 从 confirmed Structured Brief 和冻结 template snapshot 确定性编译 strict
   `PresentationPlan` / `WorkbookPlan`；不调用 Provider，不猜测缺失数字或单位。
3. 复用既有 PPT Renderer、Excel Renderer、LibreOffice QA、output checkpoint、
   credit settlement 和 duplicate-delivery contract。
4. 为 runner、Plan compiler、Compose isolation 和 queue consumption 增加 RED→GREEN
   regression tests。
5. 重建并启动 generation worker，观察现有积压任务按既有幂等状态机收口。

## 非范围

- 不修改 HTTP API、数据库 Schema、前端进度映射、Brief/Evidence/Preflight contract。
- 不读取或修改用户源文件，不把 Prompt、Provider response、Credential、文件正文、
  storage key 或本地路径写入 queue/log。
- 不手工改写任务进度、步骤状态、积分流水或删除 Redis queue message。
- 不重新触发 Agnes，不自动重试 `provider_uncertain`。

## 可验证成功标准

- RED：Compose contract 明确失败，因为缺少 `generation-worker`；runtime test 明确失败，
  因为 production executor/runner 不存在。
- GREEN：focused worker/runtime tests、generation/outbox/combined/quality tests 全部通过；
  Backend broad、Ruff、Compose config 和 security checks 通过。
- Runtime：generation worker healthy；目标任务从 `queued / 0%` 离开，Redis generation
  queue 收敛；成功输出必须通过既有 QA 后才可下载，失败则保存稳定 error category 并
  释放对应 reserve。
- Git：只暂存本任务拥有文件，敏感信息检查通过，一个 conventional commit 推送到
  `origin/main`。

## 交付结果

- TDD：focused runtime `6 passed`；Backend full `609 passed, 7 skipped`；Frontend
  full `72 passed` 且 production build 通过；Ruff `381 files` clean。
- Runtime：`generation-worker`、Backend、MySQL、Redis、PPT Renderer、LibreOffice
  healthy；generation queue 深度 `0`，worker 容器 `pip check` 无 broken
  requirements。
- 目标旧任务在 worker 启动前已超过 timeout，按既有状态机保存
  `task_timeout / 100%` 并完整释放 reserve；其 Brief 无可生成 Evidence，因此未手工
  重放或自动创建收费任务。
