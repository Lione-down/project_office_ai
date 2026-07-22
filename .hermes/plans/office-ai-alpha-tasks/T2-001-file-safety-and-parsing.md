# T2-001 文件扫描与解析沙箱

- 状态：`DONE`
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

## 本次执行设计

1. 先用纯 contract 测试锁定单文件、任务组合、PDF、Excel、Archive 与输出容量边界，以及支持/拒绝格式矩阵。
2. 再用 ClamAV protocol 测试锁定 `clean/infected/error/timeout/unavailable` 五类结果；只有 `clean` 可以进入解析。
3. 分格式用真实最小样本驱动 parser：UTF-8 CSV/TXT/MD、DOCX、PDF、XLSX/XLSM；图片仅生成待 OCR 结构化记录，不在本任务执行 OCR。
4. 用 worker service 测试锁定 `quarantined -> scanning -> parsing -> ready/rejected`、并发 claim、结构化输出持久化、parser metadata/warning/error 脱敏与失败不触碰积分表。
5. 解析输入从只读根目录读取，结构化输出写入独立受控根目录并受 byte quota；Compose worker 不挂载 Provider/Master Key，且只连接 internal network。
6. 不新增用户 HTTP API，不创建 Evidence Manifest，不接入 Redis/Outbox/Agnes；T3-001 前以可直接调用的 asset-processing worker contract 作为处理入口。

## 本次成功标准

- 所有新增行为都先观察到预期 RED，再以最小实现转 GREEN；focused suites 为 `backend/tests/file_safety` 与 `backend/tests/parsing`。
- DOCX/PDF/XLSX/CSV/TXT/MD 可产生版本化、限额内的结构化中间结果；PNG/JPG/JPEG/WEBP 只产生 `pending_ocr` 记录；XLSM 不保留或执行 VBA。
- XLS/PPTX、病毒、伪装类型、加密/密码保护、损坏、Zip Bomb、超限页/Sheet/单元格/文件/任务稳定拒绝，ClamAV/Parser 异常 fail closed。
- 资产状态与 parser metadata、warnings、脱敏错误持久化；只有完成扫描和解析的资产进入 `ready`，失败资产进入 `rejected`，且无任何 `generation_reserve` 写入路径。
- focused verification、backend broad suite、Ruff、migration/offline SQL、Compose contract、dependency/vulnerability/license 与敏感信息检查全部有实际结果；Docker 不可用时记录原始缺口，不冒充 runtime 通过。

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
