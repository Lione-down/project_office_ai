# T1-005 项目与资产上传

- 状态：`READY`
- Depends on：`T1-004`
- 来源：总计划第 2–8、12、13 节与 Day 5
- 建议 commit：`feat(asset): add isolated local asset management`

## 目标

交付用户隔离的项目与本地资产管理链路，使合法文件进入 Quarantine，所有预览和下载均通过鉴权 API。

## 交付范围

- `projects`、`file_assets` 模型、迁移、用户 API 与管理员读取边界。
- Local Storage Adapter，路径固定为 `backend/files/users/{user_id}/.../{asset_id}/`，数据库只保存 `storage_provider` 和 `storage_key`。
- 流式或分段上传、SHA-256、文件名清理、扩展名/MIME 初检和 Quarantine 状态。
- 资产列表、详情、预览、下载、软删除与删除前引用检查；直接生成时可创建默认项目。

## 实施步骤

1. 先写跨用户访问、管理员读取、路径穿越、重复文件、大小边界和删除引用测试。
2. 实现不可变 `user_id`/`asset_id` 路径构造，不接受客户端磁盘路径。
3. 上传到 `quarantine/`，计算 Hash 并记录状态，不在本任务执行病毒扫描和完整解析。
4. 实现所有权校验、管理员访问入口和下载响应安全头。
5. 更新 API、数据模型、环境和安全文档。

## 验收标准

- 普通用户无法读取、预览、下载或删除其他用户资产。
- 路径穿越和伪造 `storage_key` 被拒绝；文件二进制不进入 MySQL。
- 上传后资产处于可追踪的 Quarantine 状态，重复提交行为明确且幂等。
- 管理员读取走独立受审计边界，为 `T4-002` 的完整审计实现保留接口。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/assets -q
docker compose run --rm backend pytest backend/tests/security -q
docker compose run --rm backend pytest -q
```

## 非范围与回滚

- 不做 OCR、Office 深度解析、用户模板上传或 OSS。
- 回滚数据库记录时不得递归删除整个 `backend/files/`；仅按已解析并校验的具体资产路径清理，物理删除需遵循用户确认和备份策略。
