# Office AI Internal Alpha 封版报告

- 日期：`2026-07-27`
- 任务：`T4-005 安全检查与 Alpha 封版`
- 基线：`c3d6b927423f042713a54301fbe39508d416f396`
- 候选结论：`ACCEPT_WITH_DECLARED_BOUNDARIES`

## 封版结论

Office AI 已满足总计划第 23 节的本地 Internal Alpha 完成定义。Docker 冷启动、MySQL
空库 migration、真实 Agnes Contract、脱敏黄金回归、Microsoft Office/WPS 证据复核、
自动化与 dependency/security 检查均有本次执行证据。任务只关闭 T4-005，没有加入生产
部署、支付、团队协作、用户模板或其他明确非范围功能。

最终结论为“带声明边界接受”：黄金 corpus 仍只有 `1/10 pilot`；ClamAV 使用固定镜像
内置 signature database，本次在线 FreshClam 更新受上游 CDN 限制未成功；本地 Compose
为支持任务卡中的容器测试命令包含 test/dev tooling，但服务仍保持 non-root、read-only
rootfs 与 private network 边界。

## 可重复验证

除下述明确标记的外部/人工证据外，以下命令均在当前候选执行，退出码 `0`：

| Gate | 命令/结果 |
|---|---|
| Backend full | `docker compose run --rm backend pytest -q`；`575 passed, 6 skipped in 40.13s` |
| Backend integration | `docker compose run --rm backend pytest tests/integration -q`；`5 passed` |
| Frontend test | `docker compose run --rm frontend npm run test`；22 files、`59 passed` |
| Frontend build | `docker compose run --rm frontend npm run build`；TypeScript/Vite production build 通过 |
| PPT Renderer test | `docker compose run --rm ppt-renderer npm test`；5 files、`22 passed`，含 20 次 pilot presentation generation |
| PPT Renderer build | `docker compose run --rm ppt-renderer npm run build`；read-only runtime 通过 `/tmp` output |
| Golden regression | Backend：20 次 XLSX generation + 20 次 PPTX reference；Node：20 次 PPTX generation；均 `passed` |
| Backend quality | `pip check`、`pip-audit`、Ruff check/format 均通过 |
| Node security | Frontend 与 PPT Renderer `npm audit --audit-level=high` 均为 `0 vulnerabilities` |
| Source size | 248 个 Python/TypeScript/Vue/MJS source files 检查，超过 500 行为 `0` |

Backend 默认 broad 中的 6 个 skip 是显式 opt-in 的 T4-004 live failure drill 与真实 Agnes
用例；真实 Agnes 已在本任务以独立一次性 runtime 执行，不能把默认 skip 解读为未验证。

## Docker 冷启动与 Readiness

- 先执行 `docker compose down --remove-orphans`，未删除 volumes；再执行
  `docker compose up -d --build --wait --wait-timeout 300`，退出码 `0`。
- 9/9 服务为 running + healthy：Frontend、Backend、Worker、PPT Renderer、MySQL
  `8.4.5`、Redis `7.4.5`、ClamAV `1.4.5`、PaddleOCR、LibreOffice。
- `GET /health/ready` 返回 `ready`，MySQL/Redis 均为 `up`。
- 实际合成 PNG 调用 `/v1/ocr`，返回 `paddleocr-response.v1`，识别
  `OFFICE AI 12345`；缺失内容 SHA-256 时先返回 422，补齐 integrity header 后通过。
- EICAR 通过 ClamAV INSTREAM 实际检测，结果为 `Eicar-Test-Signature FOUND`。

为消除不可解析 registry tag，ClamAV 固定为 `1.4.5`；Paddle 镜像使用当前可解析
`paddlepaddle/paddle:3.3.1` 作为可复现基础，再固定安装 runtime
`paddlepaddle==3.1.1` 与 PaddleOCR `3.7.0`。实际 OCR inference 是最终判定，不以
healthcheck 代替。

## MySQL 空库迁移

- 创建独立 utf8mb4 验证库 `office_ai_t4_005_20260727031231`，未删除现场证据。
- 从 `base -> head` 完整执行至 `20260727_0014 (head)`，退出码 `0`。
- `alembic current` 返回唯一 Head；`alembic check` 返回
  `No new upgrade operations detected`。
- `information_schema` 实测：21 张业务表、22 张总表（含 `alembic_version`）、
  40 个 foreign keys、22 个 unique constraints。
- 原冻结契约缺失的 `templates` 与 `system_settings` 由 additive `0014` migration
  补齐；模板 source/code/version 与 system setting key 唯一约束均存在。

## Agnes 与黄金回归

- 真实 Agnes Contract 使用根 `.env` 的最小必要变量，通过一次性 Fernet Master Key、
  一次性 SQLite 和加密 `provider_credentials` 注入；测试后临时库与进程变量清理。
- 真实 Agnes Contract：`4 passed in 2.37s`；未输出、记录或持久化 API Key、Prompt、
  response body 或用户文件。
- Golden regression 固定为 `sales-pilot-v1` / `1/10 pilot`。Backend 报告为
  `spreadsheet_generation_runs=20`、`presentation_reference_runs=20`、无 finding；
  PPT Renderer suite 实际完成 20 次 presentation generation。
- Backend integration `5 passed` 覆盖组合 PPTX/XLSX workflow；重复运行、组合状态、
  partial success、幂等结算与恢复边界继续由稳定 suites 约束。

## Microsoft Office 与 WPS

- T4-004 已在 Microsoft PowerPoint/Excel `16.0.20131.20154` 和 WPS Office
  `12.1.0.26899` 实际打开同一 ignored 工作副本，逐页/逐 Sheet 检查无 repair prompt，
  关键指标、公式结果、图表、字体与布局正常。
- 本次复核仍可定位相同版本的 Microsoft Office 与 WPS Office executables。
- 当前 tracked PPTX SHA-256 为
  `c8359cc339ac8467c8430e6e2cb02da529397446769d531a42ab6c03d82a9d77`；
  XLSX SHA-256 为
  `0b9fcb65552b13bfa72a40323658a5763c86c314cc42734fcac95822ec2d414d`。
  两者与 T4-004 人工打开前后 hash 完全一致，因此既有人工兼容证据未漂移。

## Git 与敏感信息 Gate

- `.env` 由 `*.env` ignore 规则命中；nested env allowlist negation 为 `0`。
- tracked files 与全历史路径检查均未发现 `.env`/`.ene`、`.playwright-cli/`、
  `design-system/`、`output/`、`golden-data/private/`。
- 当前候选 added lines 未发现 private key、AWS key、OpenAI-style key、Bearer token
  或 credential assignment；全历史强特征的两个启发式命中已人工分类为任务文件名片段
  与 `agnes-adapter-test-key` fixture，不是真实 Secret。
- exact-path staging 共包含 37 个本任务文件；staged path、added-line 与本次新增历史
  复检均通过。全程未使用 `git add .`，未暂存 `.env`、Secret、用户文件或未脱敏材料。

## Alpha 完成定义

对照总计划第 23 节：

1. Alpha 必须交付项已由 T1-001 至 T4-005 顺序关闭。
2. 明确不交付项未被加入当前范围。
3. 自动化测试和 `1/10 pilot` 黄金回归已通过。
4. Microsoft Office 与 WPS Office 人工验收已完成且本次 hash/version 复核未漂移。
5. 真实 Agnes API Contract Test 已通过。
6. Git tracked files、37 个 staged paths 与新增历史敏感信息 Gate 已通过。
7. `docs/PLAN.md`、`docs/PROGRESS.md`、任务卡、实现、测试与 Git 状态同步。
8. 当前无未解释 blocker 或重复扣费路径。

## 已声明边界

- `1/10 pilot` 只能证明单一授权脱敏 case 的确定性、结构与指标回归，不能证明原计划 10 组 corpus 的多样性；
  不得把 20 次重复运行解释为 20 组独立材料。
- ClamAV `1.4.5` 固定镜像内置 signature database 可实际检测 EICAR；本次 FreshClam
  访问上游 CDN 返回 403/cooldown，因此不声称在线 signature refresh 已验证。上线前须接入
  可审计的更新镜像或受控 signature mirror。
- Compose 的只读 test-evidence mounts 仅包含 tracked 配置、docs 与脱敏 golden
  inputs/expected/manifests；不挂载根 `.env`、`golden-data/private`、Secret、用户文件
  或未脱敏材料。
- Compose Renderer 使用 build target 以执行任务卡的 Vitest/build 命令；默认 production
  runtime stage 已另行构建，并在 non-root/read-only 容器中成功 import，仅含 production
  dependencies。
- 本报告是 Windows 本地 Internal Alpha Gate，不是公网生产部署、外部安全认证、
  SLA 或 10 组业务 corpus 质量认证。
