# T1-004 Provider、Credential 与模型后台

- 状态：`DONE`
- Depends on：`T1-003`
- 来源：总计划第 3、6、10、12、13 节与 Day 4
- 建议 commit：`feat(provider): add encrypted multi provider model registry`

## 目标

建立多 Provider 数据边界、单 Key 单记录的 Credential 管理和 Agnes Adapter 最小真实合同，同时只对 Alpha 认证 Agnes。

## 交付范围

- `ai_providers`、`provider_credentials`、`ai_models`、`audit_logs` 模型与迁移。
- Provider/Credential/Model 管理 API，包含测试、掩码显示、重新认证 Reveal 和审计。
- 应用层 Key 加密、Fingerprint 去重、每 Credential 的 RPM/TPM/最大并发配置。
- Adapter 固定实现 `validate_configuration`、`test_authentication`、`test_structured_output`、`test_image_url`、`create_chat_completion`、`classify_error`、`extract_usage`。
- Agnes 默认 Base URL `https://apihub.agnes-ai.com/v1`、模型 `agnes-2.0-flash`、保守 Context `256K`、单次超时 120 秒。

## 实施步骤

1. 先写一 Key 一 ID、密文存储、Fingerprint 唯一、Model 绑定 Credential、Reveal 审计测试。
2. 实现 Master Key 环境变量加载和密钥轮换来源字段；明文仅在必要调用边界短暂存在。
3. 实现管理员 CRUD、Credential 健康测试、模型可见性和 Skill 能力字段。
4. 实现 Agnes 最小文本合同与错误分类：`400` 不重试、`401/403` 停用、`429/5xx` 有限重试、超时转不确定状态。
5. 更新 API、数据模型、环境和安全文档。

## 验收标准

- 数据库、日志和常规管理响应均不包含明文 Key。
- Reveal 要求重新认证、禁止缓存并生成审计日志。
- 同一 Fingerprint 不能在同 Provider 重复录入；模型明确绑定 Credential ID。
- 没有真实 Key 时 Mock Contract Test 通过，但不得声称真实 Agnes 已验证。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/providers -q
docker compose run --rm backend pytest backend/tests/admin -q
docker compose run --rm backend pytest -q
```

## 非范围与回滚

- 不认证 Agnes 之外 Provider，不做静默 Provider 切换，不公开本地图片 URL。
- 回滚时停用新增配置而非覆盖历史 Credential；禁止在回滚输出中打印解密值。

## 2026-07-22 执行计划

1. RED：先覆盖 Master Key fail-closed、单 Key 单记录、应用层密文、同 Provider Fingerprint 唯一、Model 绑定 Credential、Reveal 重新认证与成功/失败审计。
2. RED：覆盖管理员 Provider/Credential/Model API、掩码/禁止缓存、Credential 健康测试和用户可见模型过滤，确保常规响应与日志不含明文 Key。
3. RED：覆盖 Agnes Adapter 七项固定合同、默认 Base URL/模型/256K Context/120 秒 timeout，以及 `400`、`401/403`、`429/5xx`、timeout 分类和 usage 提取。
4. GREEN：以 additive migration 建立 `ai_providers`、`provider_credentials`、`ai_models`、`audit_logs`，实现最小 service/API/adapter，不进入 T1-005。
5. VERIFY：依次运行 providers focused、admin focused、Backend broad、ruff、migration/offline SQL、真实 MySQL upgrade/check 与真实 MySQL/Redis readiness；无真实 Agnes Key 时只记录 Mock Contract Test。
6. CLOSE：同步 API、DATA_MODEL、ENVIRONMENT、SECURITY、PROGRESS 和 pitfalls；完成敏感信息检查、精确路径暂存、单一 commit 和 `origin/main` 推送后，仅交接 T1-005 为下一唯一 READY。

### 成功标准

- 四张表、唯一约束、外键、中文 table/column comments 与 ORM/migration 一致，真实 MySQL 从 `20260722_0003` additive 升级到新 Head。
- Master Key 缺失或无效时创建、Reveal 与 Provider 调用 fail closed；Key 只以密文和不可逆 Fingerprint 持久化。
- Reveal 必须同时满足管理员 Session、当前密码重新认证和非空 reason，响应 `Cache-Control: no-store`，成功与失败均产生不含 Key/Fingerprint 的 audit。
- Agnes Mock Contract Test 覆盖固定 adapter 方法和错误分类；没有真实 Agnes Key 时不声称真实兼容通过。

### 执行结果

- RED→GREEN→REFACTOR 完成；Providers `33 passed`、Admin `2 passed`、Backend broad `84 passed`，Ruff check/format 全通过。
- Alembic 单 Head 为 `20260722_0004`；真实 MySQL 从 `0003` 升级并通过 `alembic check`、4/4 table comments、52/52 column comments、唯一约束和 rollback runtime probe。
- 真实 `/health/ready=200`，MySQL/Redis 均 up；Docker CLI 不可用，Compose 入口未伪造通过。
- Agnes 七项合同与错误分类只完成 Mock Contract Test；没有读取真实 Agnes Key，不声称真实 Agnes 兼容通过。
- T1-005 仅交接为下一唯一 `READY`，未实现 Project/Asset/upload 范围。
