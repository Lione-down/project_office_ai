# T1-004 Provider、Credential 与模型后台

- 状态：`BLOCKED`
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
