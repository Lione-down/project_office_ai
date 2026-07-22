# T4-005 安全检查与 Alpha 封版

- 状态：`BLOCKED`
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
