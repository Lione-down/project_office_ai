# T2-001 文件扫描与解析沙箱

- 状态：`BLOCKED`
- Depends on：`T1-005`
- 来源：总计划第 7、8、13 节与 Day 6
- 建议 commit：`feat(parser): add sandboxed office file ingestion`

## 目标

把 Quarantine 资产通过病毒、类型、容量和安全解析门禁转换为可供证据提取的结构化内容，任何不安全输入都在积分预留前拒绝。

## 交付范围

- `backend/app/services/file-safety/`、`backend/app/workers/asset-processing/` 与恶意/边界测试样本。
- ClamAV 扫描；DOCX、PDF、XLSX、CSV、TXT、MD 安全解析。
- PNG、JPG、JPEG、WEBP 进入待 OCR 流程；XLSM 只提取安全数据且不执行宏。
- XLS、输入 PPTX、加密、密码保护、损坏、MIME 伪装、Zip Bomb 和超限文件明确拒绝。
- 资产状态按 `uploaded → quarantined → scanning → parsing → ready/rejected` 持久化。

## 实施步骤

1. 先建立病毒、伪装 MIME、Zip Bomb、加密文件、损坏文件和所有容量上限测试。
2. 接入 ClamAV；扫描失败、超时与服务不可用采用 fail-closed。
3. 在无公网、无 Provider 密钥、输入只读、输出限额的 Worker 中解析允许格式。
4. 禁止宏、外部连接、嵌入对象和文档 URL 执行；文档内容只作为不可信数据。
5. 记录解析器版本、告警和脱敏错误，更新安全与环境文档。

## 验收标准

- 允许格式可到达 `ready`；不允许或不安全格式稳定进入 `rejected`，且不会创建积分预留。
- ClamAV/解析器不可用时不放行资产。
- 解析容器无 Provider 密钥、无公网访问，用户输入不能改变 System Prompt 或执行本地/远程动作。
- 单文件 50 MB、任务 20 文件/200 MB、PDF 200 页、Excel 30 Sheet/30 万非空单元格边界有测试。

## 验证

```powershell
docker compose up -d clamav
docker compose run --rm backend pytest backend/tests/file_safety -q
docker compose run --rm backend pytest backend/tests/parsing -q
docker compose run --rm backend pytest -q
```

## 非范围与回滚

- 不生成最终 Evidence Manifest，不调用 Agnes，不处理 XLS 或 PPTX 输入。
- 回滚 Worker 时保留原始 Quarantine 资产和持久状态；不得把未完成扫描的资产标记为 `ready`。
