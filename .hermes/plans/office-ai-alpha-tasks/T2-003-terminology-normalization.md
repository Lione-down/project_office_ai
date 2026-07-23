# T2-003 术语库与证据标准化

- 状态：`DONE`
- Depends on：`T2-002`
- 来源：总计划第 6、8、9、12 节与 Day 8
- 建议 commit：`feat(terms): add reusable terminology normalization`

## 目标

提供用户隔离的个人术语库，并用明确规则标准化单位、数字和日期，检测而不掩盖来源冲突。

## 交付范围

- `term_libraries`、`term_items` 模型、迁移、CRUD API 和权限测试。
- 标准术语、别名、单位、定义、口径说明、优先级与库版本。
- 数字、百分比、币种、日期和销售常用单位标准化。
- 同一事实多来源不一致时生成冲突项，要求用户指定权威来源。

## 实施步骤

1. 先写跨用户隔离、别名解析、单位换算、项目覆盖、版本快照和来源冲突测试。
2. 实现术语库与条目 CRUD，删除/更新不破坏历史任务快照。
3. 实现确定性标准化，不用模型猜测缺失单位或口径。
4. 将标准化值和规则版本写回派生证据，保留原始值。
5. 更新 API 与数据模型文档。

## 可执行成功标准

- `term_libraries` 以稳定 library ID 加不可变 version 行保存快照；库或条目变更只创建下一版本，历史版本可按显式 version 读取且不被更新或删除改写。
- `term_items` 仅属于一个具体库版本；标准术语、去重别名、单位、定义、口径、优先级均受长度和类型校验，不能引用其他用户或已删除库。
- `/api/v1/term-libraries` 与 items 子资源提供 owner-scoped create/list/get/update/delete；响应不暴露其他用户快照，显式不存在、跨用户和已删除当前版本均使用稳定错误码。
- 项目术语只覆盖同一用户同一项目下的全局术语；同层级、同优先级别名映射到不同标准术语时返回 unresolved，不静默挑选。
- `terminology-normalization.v1` 对数字、百分比、CNY/USD、销售数量单位和绝对日期产生确定性结果；未知单位、缺少年份或口径不明保留原始值并返回 unresolved。
- 派生 Evidence 保留 `raw_value`、来源定位和 provenance，只补充标准化值、单位/币种、规则版本与术语库快照引用；来源事实不被改写为模型推断。
- 同一事实的多个来源经相同规则标准化后仍不一致时生成 `source_conflict`，列出候选 evidence ID/值并要求用户指定权威来源，不自动合并。
- focused terminology/evidence、完整 backend、Ruff、Alembic 单 Head/空库升级、dependency/security 与敏感路径检查均有真实执行结果；Docker 或真实 MySQL 不可用时如实记录，不用替代证据冒充 runtime 通过。

## 本任务 owned paths

- `backend/app/api/v1/term_libraries.py`
- `backend/app/models/term_libraries.py`、`backend/app/models/term_items.py`
- `backend/app/schemas/terminology.py`
- `backend/app/services/terminology/**`
- `backend/alembic/versions/20260723_0008_terminology_snapshots.py`
- `backend/tests/terminology/**` 与本任务必要的 evidence contract 测试
- 本任务必要的 router/application/model/error wiring、`docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`、任务卡与索引状态

不拥有 `design-system/`、旧 `docs/ui-mockups/`、ignored `output/`，也不实现 T2-004 的 Skill、Agnes、Brief 或 Preflight。

## 验收标准

- 用户不能读取或引用他人术语库。
- 同一输入和规则版本产生相同标准化结果；原始值始终可追踪。
- 单位未知、口径不一致或来源冲突形成可显示的 unresolved item，而非静默合并。
- 历史 Brief/任务引用不可变术语版本。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/terminology -q
docker compose run --rm backend pytest backend/tests/evidence -q
docker compose run --rm backend pytest -q
```

## 非范围与回滚

- 不提供团队词库、行业公共词包或自动联网查询。
- 回滚新规则版本，不改写已生成 Manifest 和历史 Brief 快照。

## 执行记录

- TDD 按纯标准化规则、snapshot service/migration、HTTP CRUD、派生 Evidence 四轮先 RED 后 GREEN；额外回归捕获并修复整数尾零与“万”倍率丢失。
- 主会话 staged review 发现并按 TDD 修复：同 canonical term 的最高优先级候选存在 unit/口径差异时曾被稳定但错误地择一；术语 unit 补齐后曾残留 T2-002 的 `numeric_unit_unknown` blocker。4 个定向测试先 RED 后 GREEN，OCR 独立 blocker 继续保留。
- Focused：`backend/tests/terminology` 为 `29 passed`；既有 `backend/tests/evidence` 为 `11 passed`；合并为 `40 passed`。
- Broad：`backend/.venv/Scripts/python.exe -m pytest backend/tests -q` 为 `294 passed`。
- Quality：Ruff check/format 全量通过，174 个 Python 文件已格式化且全部不超过 500 行；`git diff --check` 通过。
- Migration：`20260723_0008` 是唯一 Head，SQLite 空库完整升级与两项表/关键唯一约束测试通过；主会话逐项比对两表 model/migration 的 column、foreign key、unique constraint 与 index name 全部一致；MySQL dialect offline SQL 退出码 `0` 并生成两张表、命名外键/唯一约束及中文 COMMENT。
- Dependency/Security：`pip check` 通过，`pip-audit` 为 0 known vulnerabilities（仅跳过本地非 PyPI package），14 个 direct production dependency license metadata 无缺失；added-line Secret/危险调用、新增二进制和禁止路径扫描通过。
- Final review：当前主会话按 migration/model、API/Service、Normalizer/Evidence、tests、security/scope 与状态文档顺序复核最终 cached diff；修复后的结论为 `security_concerns=0`、`logic_errors=0`，无剩余 blocking finding。
- Runtime 缺口：当前 PATH 无 `docker`，任务卡 3 条 Compose 命令未进入容器；未读取 `.env`，未运行真实 MySQL `0008` upgrade。单进程临时 SQLite `upgrade head` 成功，随后 `alembic check` 因仓库既有 SQLite `BINARY(16)` introspection 被识别为 `NUMERIC(16)`，对全部历史及新增 UUID 列统一报告 type drift；不标记该 check 通过，也不把 SQLite/offline 证据冒充 Docker/真实 MySQL runtime。
- 范围：未实现 T2-004 Skill、Agnes、Structured Brief 或 Preflight；保留且未暂存 `design-system/`、旧 `docs/ui-mockups/` 与 ignored `output/`。
