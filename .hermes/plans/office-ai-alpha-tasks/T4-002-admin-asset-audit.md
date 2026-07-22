# T4-002 管理员最高权限与审计

- 状态：`BLOCKED`
- Depends on：`T4-001`
- 来源：总计划第 2、3、6、12、13 节与 Day 17
- 建议 commit：`feat(admin): add audited global asset access`

## 目标

完成管理员查看、预览、下载和删除全体用户资产的最高权限边界，同时确保每次敏感操作可重新认证、说明原因并形成不可篡改审计记录。

后台交互以 `docs/ui-v1/admin/02-users.png`、`05-credentials-reauth.png`、`08-assets.png`、`09-credits.png` 和 `10-audit-logs.png` 为视觉基线。

## 交付范围

- 管理 Asset API、Audit Middleware/Service、权限与审计测试。
- 管理员预览、下载、删除；用户状态、密码重置、积分调整和 Credential Reveal 的统一敏感操作审计。
- 统一的重新认证对话框、原因输入、危险动作确认、成功/失败反馈和审计记录跳转入口。
- 审计字段包含操作者、动作、目标、IP、User-Agent、原因、结果和脱敏上下文。
- 文件引用检查、活动文件删除与 30 天备份残留策略的可审计状态。

## 实施步骤

1. 先写管理员允许、普通用户拒绝、重新认证过期、原因缺失、取消操作、重复提交和成功/失败审计测试。
2. 在授权完成后按资产 ID 解析存储路径，不接受管理员提供任意磁盘路径。
3. 对预览、下载、删除和其他敏感管理操作统一写审计；失败尝试也记录结果。
4. 复用统一敏感操作组件：先展示动作和目标，再要求重新认证与原因；危险操作使用明确中文后果说明，提交期间禁用重复触发。
5. 日志和审计上下文脱敏，不记录完整文件内容、密码、Token、API Key 或签名 URL。
6. 对照 UI V1 的用户、Credential、资产、积分和审计页面完成真实构建产物人工检查，并更新 API、安全、数据模型和协议要求文档。

## 验收标准

- 管理员四类资产操作均有可查询审计记录；普通用户相同请求稳定拒绝。
- Reveal、密码重置、积分调整和资产删除都要求重新认证和原因。
- 用户状态变更同样要求重新认证和原因；重新认证失败、原因缺失、取消和服务端失败均有清晰反馈，且不会提前执行操作。
- 路径穿越、已删除资产和不存在资产不会泄露磁盘信息。
- 管理员权限是显式产品边界，前端和协议说明一致。
- Credential 默认掩码；5 个敏感管理页面与 UI V1 的信息层级、对话框结构和危险操作表达一致。

## 验证

```powershell
docker compose run --rm backend pytest backend/tests/admin -q
docker compose run --rm backend pytest backend/tests/audit -q
docker compose run --rm backend pytest backend/tests/security -q
docker compose run --rm frontend npm run test
```

## 非范围与回滚

- 不新增组织、细粒度团队角色或协作权限。
- 审计记录只追加；回滚功能不能删除审计历史，资产删除恢复遵循备份策略而非数据库字段反转假装恢复。
