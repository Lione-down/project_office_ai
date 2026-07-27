# Office AI Structured Brief Context 压缩修复

- 日期：2026-07-27
- 类型：Post-Alpha 单任务修复
- 基线：`eaf9e446c14d03fffa2bc96be808a41ad1e6ae07`
- 用户目标：已通过安全解析的 private 黄金 XLSX 可以继续生成 Structured Brief，不再因冗余 Context 编码失败。

## 根因

- 当前 `build_evidence_context` 为每条 Evidence 重复序列化完整 asset UUID、asset version 和 location JSON，并直接暴露 66 字符原始 Evidence ID。
- 当前真实上传材料包含 10,465 条 Evidence；旧编码约为 4.26 MB / 1,418,854 估算 token，而发布模型在保留 8,192 output token 和 2,048 fixed reserve 后只有 251,904 token 可用。
- 这是 Context 表示层放大，不是 Excel、Manifest 或模型登记值错误。不得通过虚增模型 Context、截断 Evidence 或删除语义 blocker 绕过。

## 设计

1. 新增版本化 `brief-evidence-context.v2`：
   - asset identity/version 只在 asset table 中出现一次；
   - 按 asset、location kind、Sheet 和 Evidence type 分组；
   - 每条 Evidence 使用确定性短引用 `r<base36>`；
   - 保留原始值、标准化值、单位、币种、位置和 calculated provenance。
2. Agnes 输出中的短引用只允许从本次 Context 映射表解析；未知引用继续以 `brief_evidence_invalid` fail closed。
3. Schema、snapshot 和 Evidence 校验前把短引用严格映射回原始 Evidence ID；数据库和后续 Preflight/Renderer 只看到原始 ID。
4. Context 仍按 `min(model.context_window, 256K) - max_output_tokens - fixed_prompt_reserve` 计算；压缩后仍超限则保持 `context_budget_exceeded`。
5. 不改变 Manifest、解析、owner scope、Provider、Credential、模型能力或 Preflight blocker contract；5,193 个 `numeric_unit_unknown` 继续保留。

## RED / GREEN

- RED：
  - 10,465 条黄金规模 synthetic Excel Evidence 在 256K Context 下必须可完整编码；
  - Context 不得在 item 行重复原始 Evidence ID、asset UUID/version；
  - Agnes 短引用必须映射回原始 Evidence ID；
  - 未知短引用必须在落库前 fail closed。
- GREEN：
  - `backend/tests/briefs/test_context.py`
  - `backend/tests/briefs/test_validation.py`
  - `backend/tests/briefs/test_service.py`

## 验证与交付

1. 用真实 runtime 中已上传的 ready/valid 黄金材料只读测量 v2 Context，确认 10,465 条全部保留且完整 message 小于模型预算。
2. 运行 backend Brief focused、全量 pytest、Ruff、依赖与安全检查。
3. 重建并重启 backend，确认 9999 readiness、8888 前端和真实 Agnes synthetic
   Contract；private 材料只验证完整 Prompt 预算，由用户在保留页面亲自触发发送。
4. 更新 `docs/PLAN.md`、`docs/API.md`、`docs/SECURITY.md`、`docs/PROGRESS.md` 与 `pitfalls.md`。
5. 精确暂存本任务文件，检查 forbidden/env/Secret/user-file 边界，创建单一 conventional commit 并 push `origin/main`。

## 明确不变

- 不提交或复制 private workbook、Manifest、Prompt、Provider response 或 Secret。
- 不把 `1/10 pilot` 扩张为 10 组覆盖。
- 不自动解决单位未知、来源冲突或其他 Preflight blocker。
- 不触碰 `.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/` 或 ignored `output/`。
