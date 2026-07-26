# T4-004 Office/WPS 与故障演练

- 状态：`DONE`
- Depends on：`T4-003`
- 外部前置：本机可用 Microsoft Office、WPS 和真实 Agnes 测试配置
- 来源：总计划第 3、10、16–18、22 节与 Day 19
- 建议 commit：`test(alpha): record compatibility and recovery drills`

## 当前外部前置状态（2026-07-27）

- Microsoft PowerPoint/Excel `16.0.20131.20154` 已激活，并已实际打开同一组黄金
  PPTX/XLSX 验证副本。
- WPS Office `12.1.0.26899` 已安装并定位到 `D:\工具\WPS Office`。
- WSL `2.7.11.0`、kernel `6.18.33.2` 与 Docker Desktop `4.83.0` 已实际启动；
  `docker version` 返回 Linux Engine `29.6.2`，Compose `v5.3.1`，`hello-world` 与项目
  `docker compose config --quiet` 均通过。WSL data root 位于
  `D:\works\tool\DockerData`。
- Agnes Structured Output compatibility 已先以 RED Contract 固定，再通过显式
  `native_response_format` capability 最小修复；使用本地未跟踪 Credential 的真实
  Contract 为 `4 passed`。
- 本任务代码、外部 runtime、桌面兼容与恢复演练 Gate 均完成；下一唯一
  dependency-ready 任务为 `T4-005`。

## 目标

用真实桌面 Office/WPS 和受控故障演练证明输出兼容性、Provider 错误语义、队列恢复、幂等与积分恢复符合 Alpha 合同。

## 交付范围

- 全部黄金 `passed` 输出的 Microsoft Office/WPS 人工打开记录。
- Agnes `401`、`429`、`5xx`、超时、非法 Schema 的受控演练记录。
- Redis 重启、Worker 重启、MySQL Outbox 恢复、重复提交、取消、部分成功和积分恢复演练。
- `docs/PROGRESS.md` 中记录环境、步骤、预期、实际、证据路径和未通过项。

## 实施步骤

1. RED：用离线单元 Contract 固定 Agnes 不支持 native `response_format` 时的显式 capability
   行为，并保持严格应用层 Schema、一次 repair 和错误分类边界。
2. GREEN：只做最小 Provider compatibility 实现；先跑 focused Contract，再显式 opt-in
   重跑真实 Agnes，且不打印 Key、prompt 或 response body。
3. 启动真实 MySQL/Redis/Worker runtime；使用隔离测试记录演练 Agnes `401`、`429`、
   `5xx`、超时、非法 Schema，以及 Redis/Worker restart、Outbox recovery、重复提交、
   取消、部分成功、`provider_uncertain` 与积分恢复。
4. 在 Microsoft Office 和 WPS 分别打开所有 `passed` 黄金 PPTX/XLSX 副本，记录修复
   提示、页/Sheet 数、公式、关键数字、图表、字体和布局；验证前后确认 tracked 黄金
   文件 checksum 不变。
5. 依次执行 focused、任务卡 Docker 命令、broad、quality/security 与当前主会话
   sequential deep review；所有失败保持未完成状态并记录，不降级 Gate。

## 验收标准

- 所有标记 `passed` 的黄金文件在 Microsoft Office 与 WPS 中均无修复提示。
- Agnes 错误分类和重试次数符合合同；超时不确定不会自动重复计费。
- Redis/Worker 重启后任务恢复，重复提交不产生重复任务/预留/结算。
- 演练记录足以由另一人复现，并明确软件版本与证据文件。

## 验证

```powershell
docker compose run --rm backend python -m pytest tests/integration -q
docker compose run --rm backend python -m pytest tests/providers/agnes_contract -q
$repo = (Get-Location).Path
docker compose run --rm `
  --volume "${repo}\golden-data\inputs:/workspace/golden-data/inputs:ro" `
  --volume "${repo}\golden-data\expected:/workspace/golden-data/expected:ro" `
  --volume "${repo}\golden-data\manifests:/workspace/golden-data/manifests:ro" `
  backend python -m app.utils.golden_regression `
  /workspace/golden-data/manifests/sales-pilot-v1.json --repo-root /workspace
```

## 当前执行证据（2026-07-27）

- Agnes：默认不发送上游未声明支持的 native `response_format`，但仍由应用层执行 strict
  Structured Brief Schema、一次 repair 与稳定错误分类；离线 focused 为 `23 passed`，
  使用本地未跟踪 Credential 的真实 Contract 为 `4 passed`。
- Docker：重建 backend 镜像后，integration 为 `5 passed`，Agnes 容器 Contract 为
  `2 passed, 2 skipped`（live 默认未 opt-in），黄金回归为 20 次 XLSX generation 与
  20 次 PPTX reference `passed`；LibreOffice 为 `25.2.3.2`。第二个隔离 utf8mb4 MySQL
  database 从 revision 0 完整升级到 head，`alembic check` 无 drift。
- 故障演练：隔离 run `86d22c8a-bd5c-4254-96d7-9ad990a8325f` 的 4 个阶段均通过，
  覆盖真实 MySQL/Redis、Redis stop/start、Outbox pending/recovery、新 worker、重复投递、
  取消、部分成功、`provider_uncertain`、stale recovery 与 ledger 幂等。
- WPS：`12.1.0.26899` 已实际打开 4 页 PPTX 与 2 Sheet XLSX；逐页/逐 Sheet 检查无
  repair prompt，表格、关键指标和图表可见。
- Microsoft Office：PowerPoint/Excel `16.0.20131.20154` 已实际打开同一验证副本。
  PowerPoint 放映模式逐页检查 4 页；Excel 切换检查“经营数据”和“经营看板”2 Sheet，
  中文、表格、关键数字、公式结果、百分比格式和图表均正常，无 repair、Protected View、
  登录或激活提示。OfficePLUS 模板推广层未授权，只通过放映模式完成 PPTX 检查；Excel
  “隐私设置已应用”只读通知未交互。
- 双应用验证后，PPTX 工作副本与 tracked expected SHA-256 均为
  `c8359cc339ac8467c8430e6e2cb02da529397446769d531a42ab6c03d82a9d77`，XLSX 均为
  `0b9fcb65552b13bfa72a40323658a5763c86c314cc42734fcac95822ec2d414d`；应用未改写文件。

人工检查：逐个打开黄金 PPTX/XLSX，核对修复提示、页/Sheet 数、关键数字、公式值、图表、字体和布局，并在 `docs/PROGRESS.md` 留证。

## 非范围与回滚

- 不在没有 Microsoft Office/WPS 或真实 Agnes 证据时声明兼容通过。
- 演练不得删除持久卷或生产数据；恢复失败时停止封版，保留任务、流水和日志证据。
