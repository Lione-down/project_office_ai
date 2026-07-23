# T2-004 Skills 与 Agnes Structured Brief

- 状态：`DONE`（Mock Contract 通过；真实 Agnes Contract 未验证）
- Depends on：`T2-003`
- 外部前置：真实 Agnes API Key 以未跟踪方式提供，用于最终 Contract Test
- 来源：总计划第 9、10 节与 Day 9
- 建议 commit：`feat(brief): generate evidence grounded structured briefs`

## 目标

固化两个 Alpha Skill，并通过 Agnes 生成经过 Schema 校验、证据可追踪、不可变修订的 Structured Brief。

## 交付范围

- `skills`、`briefs`、必要的 `provider_calls` 模型与迁移。
- `ppt.sales-business-review.v1` 与 `excel.sales-analysis-dashboard.v1` 的版本、输入/输出 Schema、能力要求和固定组合规则。
- Structured Brief 顶层字段严格包含总计划第 9.3 节定义的 17 个字段。
- 证据选择、Context 预算、Pydantic/JSON Schema 校验、一次约束修复和 Brief Revision 保存。
- Mock Contract Test 与使用真实 Agnes 的最小文本/销售材料 Contract Test。

## 实施步骤

1. 先写合法结构、非法结构、一次修复失败、证据伪造、Context 超限和 Provider 错误分类测试。
2. 固化两个 Skill 版本；Alpha 只支持两者单选或已知组合。
3. 只向 Agnes 提供所需证据文本/元数据；本地图片不通过公网隧道暴露。
4. 验证每个内容项来源为 `user`、`file`、`calculation`、`agnes_inference` 或 `system_default`。
5. 真实 Agnes 调用写入 Provider Request ID、Token、耗时和脱敏状态，不记录 Key 或完整文件内容。

## 本次执行规格

- `skills` 以 `(skill_code, version)` 唯一且不可变，migration 固化两个 `v1` Skill；runtime registry 校验数据库 checksum、JSON Schema、能力要求及 Alpha 固定单选/组合规则。
- `briefs` 每行是一个不可变 revision，以 `(brief_group_id, revision)` 唯一；T2-004 只创建首个 `draft` revision，不实现 PATCH、确认或 Preflight。
- `provider_calls` 为每次 Agnes attempt 保存 Provider/Model/Credential、Brief group、可空 Brief revision、Request ID、Token、耗时、状态、错误分类和 `is_redacted=true`；不保存 Key、Prompt、响应正文、本地路径或文件内容。
- `POST /api/v1/briefs/generate` 只接收 owner-scoped project、ready asset ID、术语库 version、两个固定 Skill、已发布模型和用户约束；服务从受控 Evidence Manifest 读取证据，不接受客户端伪造 evidence 正文。
- Structured Brief 使用 `extra=forbid` 的 Pydantic/JSON Schema，顶层严格为总计划 9.3 的 17 个字段；来源枚举固定，`inferences` 只能使用 `agnes_inference`，全部 evidence ID 必须属于本次 owner-scoped context。
- Context 预算按 `min(model.context_window, 256K) - max_output_tokens - fixed_prompt_reserve` 保守计算；预算不足在 Provider 调用前 fail closed，不截断必需 evidence。
- 初次 JSON/Schema/evidence validation 失败只允许一次约束修复；第二次失败不保存 Brief，也不触碰积分。Provider timeout 记录为 `provider_uncertain` 且不自动重试，`401/403` 暂停当前 Credential，不切换 Provider。
- `GET /api/v1/skills` 与 `GET /api/v1/skills/{skill_code}` 只返回已发布用户 Skill，并要求有效 Session。
- 真实 Agnes Contract Test 仅在显式 opt-in、runtime Database/Master Key 与已配置 Credential 均可用时运行；缺少任一前置时只报告 skip/Mock 通过，不读取 `.env`、不回显 Secret。

## 可验证成功标准

- RED：合法结构、严格 17 字段、非法/二次非法 repair、伪造 evidence、Context 超限、timeout/401、固定组合、不可变 revision、migration/API 与 Agnes Mock Contract 在实现前因缺失模块或行为失败。
- GREEN focused：`backend/tests/skills`、`backend/tests/briefs`、`backend/tests/providers/agnes_contract` 全部通过；真实 Contract 未 opt-in 时明确 skip。
- Broad：Backend 全量 pytest、Ruff check/format、单一 Alembic head、SQLite 空库 upgrade、MySQL offline DDL、`pip check`、`pip-audit` 和 direct dependency license gate。
- Security/review：确认 owner scope、无 Provider 静默切换、无 Prompt/响应/Key 持久化、无 Secret/用户文件/二进制/禁止路径进入 diff 或 staged paths。
- 状态收口：本任务卡与索引改为 `DONE`，`T2-005` 改为唯一 `READY`，`docs/PROGRESS.md` 记录真实命令、结果、缺口和 changed files。

## 验收标准

- 合法响应生成不可变 Brief Revision；Schema 失败仅修复一次，再失败则不扣费。
- Agnes 推断明确标记 `ai_inference`，不能伪装为来源事实；引用的 evidence ID 必须存在。
- 不发生 Provider 静默切换；超时结果不确定进入 `provider_uncertain` 语义。
- 真实 Key 缺失时任务保持阻塞或只标记 Mock 通过，不得声称真实 Contract Test 通过。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/skills -q
docker compose run --rm backend pytest backend/tests/briefs -q
docker compose run --rm backend pytest backend/tests/providers/agnes_contract -q
```

## 非范围与回滚

- 不发布其余六个业务 Skill，不实现任意 Skill 冲突矩阵或 Agnes 原生本地图片理解。
- Skill 与 Brief 版本不可变；回滚通过停用新版本和恢复上一已发布版本，不覆盖历史记录。

## 执行结果

- Focused：Skills `17 passed`；Briefs `28 passed`；Agnes Contract `2 passed, 2 skipped`。两项 skip 均因未显式 opt-in 真实 Agnes，未读取 `.env` 或 Credential。
- Broad：Backend `341 passed, 2 skipped`；Ruff check/format、`20260723_0009` single head、SQLite 空库 upgrade、MySQL offline DDL、`pip check`、`pip-audit` 与 14 个 direct production dependency license gate 均通过。
- Review：修复 Skill row 内容漂移、Brief 权威快照漂移、migration runtime import、鉴权顺序、术语规则遗漏、无证据事实、Credential cipher wiring、Manifest 无界读取，以及 MySQL offline seed UUID 编译失败；最终无 blocking finding。
- Runtime 缺口：当前 PATH 无 Docker，未运行 Compose container 或真实 MySQL migration；未提供真实 Agnes opt-in/credential，故仅标记 Mock Contract 通过，不声称真实 Agnes 兼容性通过。
- Scope/security：未读取 `.env`、Secret、用户文件或未脱敏材料；用户未跟踪 `design-system/`、旧 `docs/ui-mockups/` 与 ignored `output/` 保持未暂存。
