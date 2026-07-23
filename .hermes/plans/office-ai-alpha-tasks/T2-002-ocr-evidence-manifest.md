# T2-002 OCR 与 Evidence Manifest

- 状态：`DONE`
- Depends on：`T2-001`
- 来源：总计划第 8 节与 Day 7
- 建议 commit：`feat(evidence): add traceable ocr and evidence manifests`

## 目标

将解析结果和图片 OCR 转换为可追踪、可验证、带置信度与位置的 Evidence Manifest，为 Brief 和质量审计提供事实基础。

## 交付范围

- `backend/app/services/ocr/`、`backend/app/services/evidence/`、Manifest JSON Schema 和测试。
- PaddleOCR 集成，以及 Excel 单元格、PDF 页码/BBox、Word 段落、图片 OCR BBox 定位。
- 每条证据包含 `evidence_id`、类型、资产版本、location、原始/标准化值、单位/币种、OCR 置信度、解析器版本。
- Manifest 写入资产 `extracted/`，MySQL 只保存 Key、状态、摘要、引擎版本和告警数。

## 实施步骤

1. 先写叙述/数字置信度、位置映射、单位未知、来源类型和引擎版本测试。
2. 接入 PaddleOCR，保持输入隔离和资源限额。
3. 统一产出 `source_fact`、`calculated_fact`、`ai_inference` 三类证据结构，但本任务不产生 AI 推断。
4. 对叙述置信度 `<0.75` 生成告警；对数字置信度 `<0.90` 标记为阻断相关计算。
5. 实现 Manifest Schema 校验、不可变资产版本关联和可审计错误。

## 验收标准

- 任一来源事实可追踪到资产版本和明确位置。
- 低置信叙述只告警，低置信数字阻断计算；单位未知不会被默认为零或任意单位。
- Manifest Schema 不合法时资产不会进入可供 Brief 使用的状态。
- OCR 服务不可用时可重试但不得生成伪造证据。

## 可执行成功标准

- OCR client 只调用 internal PaddleOCR HTTP endpoint，使用 timeout、响应大小和识别项数量预算；连接、timeout、HTTP、非法 JSON/Schema 与超限响应均返回稳定可重试错误，不产生证据。
- `source_fact` 可从 Excel 单元格、PDF 页码/BBox、Word 段落、文本行和图片 OCR BBox 生成；每条证据关联不可变 `asset_id`、`asset_version`、原始/标准化值、单位/币种、OCR 置信度以及 parser/OCR engine 名称与版本。
- 叙述 OCR `<0.75` 生成 warning；数字 OCR `<0.90` 或数字单位未知时设置 calculation blocker，不把未知单位推断为零或任意单位。
- Manifest 通过版本化 JSON Schema 和 Pydantic 校验后才原子写入 `users/{user_id}/assets/{asset_id}/extracted/evidence-manifest.json`；MySQL 只保存 deterministic key、摘要、engine version、warning/blocker 数量和完成时间。
- 处理状态在 manifest 写前持久化 deterministic key；OCR 暂时不可用时资产回到可重试状态并记录稳定错误，非法 Manifest 或持久化失败时 fail closed，不进入 Brief-ready 状态。
- focused `backend/tests/ocr` 与 `backend/tests/evidence`、Backend broad、Ruff、Alembic、dependency/security/diff 检查通过；Docker 或真实 MySQL 不可用时记录原始缺口，不冒充 runtime evidence。

## 验证

```powershell
docker compose up -d paddleocr
docker compose run --rm backend pytest tests/ocr -q
docker compose run --rm backend pytest tests/evidence -q
docker compose run --rm backend pytest -q
```

## 非范围与回滚

- 不做术语标准化、来源冲突裁决或 Agnes 推断。
- 回滚只使新 Manifest 版本失效，不覆盖或删除原始资产与旧 Manifest。
