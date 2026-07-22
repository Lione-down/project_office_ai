# T2-003 术语库与证据标准化

- 状态：`BLOCKED`
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
