# T2-004 Skills 与 Agnes Structured Brief

- 状态：`READY`
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
