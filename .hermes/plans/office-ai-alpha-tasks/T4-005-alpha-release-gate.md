# T4-005 安全检查与 Alpha 封版

- 状态：`DONE`
- Depends on：`T4-004`
- 来源：总计划第 3、15–19、22、23 节与 Day 20
- 建议 commit：`chore(release): prepare internal office ai alpha`

## 目标

以可重复的自动化、冷启动、零库迁移、真实 Contract、人工兼容和敏感信息证据关闭 Alpha；任何未通过项保持阻塞，不能通过改文档伪装完成。

## 交付范围

- Backend、Frontend、PPT Renderer、集成与黄金回归完整报告。
- Docker Compose Windows 冷启动和 `/health/ready` 证据。
- 新 MySQL 数据库从 Alembic 零升级到 Head 的证据。
- Git 工作树、暂存区和本次新增历史的敏感信息检查。
- `docs/PLAN.md`、`docs/PROGRESS.md`、`pitfalls.md` 与总计划第 23 节完成定义逐项一致。

## 实施步骤

1. 从干净运行态执行所有稳定验证命令，记录退出码和报告位置。
2. 验证 Compose 冷启动、依赖健康、空库迁移和端到端双输出。
3. 检查 `.gitignore`、`git status`、暂存区、提交候选 diff 和新增历史，不输出或读取真实 Secret 内容。
4. 对照 Alpha 必须交付、明确不交付、质量、安全、账务、真实 Agnes 和 Office/WPS 证据逐条关闭。
5. 更新计划与进度；未完成项保留为阻塞，不移动到“完成”。

## 本次执行计划与 RED contract（2026-07-27）

1. 先新增 `backend/tests/release/test_alpha_release_contract.py`，要求最终报告
   `docs/ALPHA_RELEASE.md` 必须显式记录：稳定测试命令与退出码、Compose 冷启动和
   `/health/ready`、独立 utf8mb4 MySQL 空库 `base -> head` 与 `alembic check`、真实 Agnes
   Contract、黄金回归、Microsoft Office/WPS 复核、Git tracked/staged/history 敏感信息
   检查、总计划第 23 节逐项结论，以及 `1/10 pilot` 不等于 10 组 corpus 的边界。
2. 在报告尚不存在时运行该 focused test，必须观察到 RED；不得预写伪造的通过结果使测试
   直接为 GREEN。
3. 按“Docker 冷启动与零库 -> focused/stable suites -> 真实 Agnes/黄金/Office 证据 ->
   broad/quality/security -> 当前主会话 sequential deep review”的顺序执行。外部值只从根
   `.env` 最小必要注入临时进程，不打印、复制、暂存或写入报告。
4. 只有实际证据全部满足后才编写 `docs/ALPHA_RELEASE.md`，再将 focused contract 转为
   GREEN；任一 hard gate 失败则报告为阻塞，T4-005 保持 `READY`。
5. 最后同步本任务卡、任务索引、`docs/PLAN.md`、`docs/PROGRESS.md` 与 `pitfalls.md`，
   完成 exact-path staging、候选 diff/history Secret gate、单一 conventional commit 和
   `origin/main` push。

## 验收标准

- 全部命令退出码为 0；Frontend Build 无 TypeScript 错误，Alembic 空库升级成功。
- 黄金回归无阻断差异，真实 Agnes Contract、Office/WPS 验收均有当前证据。
- 同一幂等键、失败释放、部分成功、Provider 不确定和恢复路径全部通过。
- Git 不跟踪 `.env`、Key、Token、证书、私钥、用户文件或私有黄金材料。
- `docs/PLAN.md` 与 `docs/PROGRESS.md` 状态一致且无未解释阻断。

## 验证

```powershell
docker compose config
docker compose run --rm backend pytest -q
docker compose run --rm backend pytest backend/tests/integration -q
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm ppt-renderer npm test
docker compose run --rm ppt-renderer npm run build
docker compose run --rm backend python -m app.utils.golden_regression
git check-ignore -v .env
git status --short
git diff --cached --name-only
git diff --check
```

## 非范围与回滚

- 不加入延期功能、生产部署、OSS、支付、微信、用户模板或最终高保真 UI。
- 封版失败时不做破坏性 reset；保留最后通过的不可变 Skill、模板和输出版本，使用反向积分流水和任务恢复机制处理外部状态。

## 当前执行证据（2026-07-27）

- RED/GREEN：release report contract 初始 `3 failed`；Alpha 21 表 schema contract
  初始 `3 failed`。最终分别为 `3 passed` 与 `3 passed`。
- Docker：不删除 volumes 的冷启动/rebuild 后 9/9 services healthy，
  `/health/ready` 为 ready；实际 OCR inference 与 EICAR INSTREAM 均通过。
- MySQL：独立 utf8mb4 空库从 base 升至 `20260727_0014 (head)`；
  21 张业务表、40 个外键、22 个唯一约束，`alembic check` 无 drift。
- Runtime：真实 Agnes Contract `4 passed`；Backend Golden regression 为 20 次
  XLSX generation + 20 次 PPTX reference，PPT Renderer suite 为 20 次 PPTX generation。
  Microsoft Office/WPS executable 版本与 T4-004 相同，tracked golden hashes 未漂移。
- Stable suites：Backend full `575 passed, 6 skipped`，integration `5 passed`；
  Frontend `59 passed` + build；PPT Renderer `22 passed` + build。Ruff、pip check/audit、
  两个 npm full audit、source-size 与 Git tracked/diff/history Gate 均通过。
- 封版结论：`ACCEPT_WITH_DECLARED_BOUNDARIES`。`1/10 pilot` 不扩张为 10 组覆盖；
  ClamAV online signature refresh 与生产部署不在通过结论内。详见
  `docs/ALPHA_RELEASE.md`。
