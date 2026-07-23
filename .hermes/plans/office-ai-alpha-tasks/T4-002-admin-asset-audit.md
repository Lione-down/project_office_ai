# T4-002 管理员最高权限与审计

- 状态：`DONE`
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

## 2026-07-24 实施合同

### 统一敏感操作协议

- 所有敏感写操作使用 `current_password + reason`；原因去除首尾空白后长度为
  `1..500`。密码只参与 Argon2id 校验，不进入 audit、日志、响应或幂等上下文。
- Credential Reveal 沿用既有 `POST .../reveal`；密码重置、用户状态变更、积分调整和
  资产删除使用 JSON body。资产 preview/download 改用 `POST`，避免把密码或原因放入
  URL/query，响应统一 `private, no-store`。
- 写操作要求 `Idempotency-Key`；相同管理员、动作、目标和 key 的已完成重放返回既有
  安全结果，不重复修改状态、积分或删除文件。前端提交期间禁用确认按钮。
- 前端统一对话框先展示动作、目标与后果，再收集当前密码和原因；关闭/取消不发送请求。
  服务端失败保留对话框输入并显示稳定中文错误，成功后提供“查看审计记录”入口。

### 权限、资产与审计边界

- 新增管理员用户查询、密码重置、状态变更、全局资产查询/preview/download/delete、
  积分调整与只读 audit 查询；普通用户统一 `403 admin_required`。
- 管理员只能提交资源 UUID，服务端从 `file_assets` 解析 owner 与既有 deterministic key；
  不接受路径、storage key、签名 URL或文件正文。不存在/已删除资产统一
  `asset_not_found`，错误与 audit context 不含磁盘信息。
- 管理员删除复用 owner 删除的引用、处理中状态和三类 exact-key 清理规则；audit context
  只记录 owner、处理状态、活动文件清理结果与 `backup_retention_days=30`，不宣称已删除
  不受应用控制的备份副本。
- audit 仅追加，字段固定为 actor、action、target、脱敏 IP/User-Agent 摘要、reason、
  result、脱敏 context、trace ID、UTC 时间。失败的重新认证、原因缺失、资源不存在和
  业务失败同样审计；普通用户权限拒绝不创建伪造 admin actor 记录。

### RED contract 与成功标准

- Backend RED 覆盖：管理员允许、普通用户拒绝、原因缺失、重新认证失败、资产四类操作、
  路径/删除状态不泄露、引用/处理中删除、用户 reset/status、积分只追加、Credential
  Reveal、失败审计、audit 查询和幂等重放。
- Frontend RED 覆盖：五个敏感管理页面真实加载、Credential 默认掩码、统一重新认证
  对话框、危险后果说明、取消零请求、提交中防重复、成功/失败反馈与审计跳转。
- GREEN 后依次执行 admin/audit/security focused suites、Backend/Frontend broad suites、
  Ruff/Build/audit 检查、真实 Production Build headed Chrome 的 `1440px` 与 `375px`
  视觉/交互验证，以及当前主会话顺序 deep review。

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

## 实施结果（2026-07-24）

- 交付显式 admin 用户/资产/积分/audit API、逐次当前密码 re-auth、原因校验、失败审计、
  Credential Reveal/Test 网络上下文脱敏，以及 exact-key 资产 preview/download/delete。
- 成功用户/Session/ledger 与 audit 同事务提交；业务失败退出失败事务后独立追加
  `failed` audit，避免调查链随异常回滚。积分 `Idempotency-Key` 重放不重复改变余额。
- 五个 UI V1 敏感页面接入真实 frontend API；统一对话框覆盖动作、目标、后果、当前密码、
  原因、临时密码/积分金额、提交禁用、取消零请求、成功/失败反馈与 audit 跳转。
- RED 后 focused 最终为 admin/audit/security/assets `34 passed`，Frontend 管理/API/request
  `12 passed`；broad 为 Backend `552 passed, 2 skipped`、Frontend `22 files / 59 tests`
  与 Production Build 98 modules、PPT Renderer `4 files / 20 tests` 与 build。
- Ruff check/format、pip check、pip-audit、两个 npm audit 与 Alembic single head 通过；
  新增主文件均不超过 500 行。真实 Agnes 仍因未 opt-in 只有 Mock Contract 通过。
- Headed Chrome 在 Production Build 上验证资产、Credential、用户和 audit：取消敏感请求
  为 0、Reveal 确认为 1，桌面/375px overflow 均为 0，console 0 errors / 0 warnings。
  浏览器使用受控 Mock API，不冒充真实 Backend/MySQL/Redis runtime。
- 4 条 Docker 验证命令均实际尝试，但 PATH 无 `docker`，在容器启动前
  `CommandNotFoundException`；无真实 MySQL/Redis/Agnes/LibreOffice/Office/WPS 新证据。
- 当前主会话顺序 deep review 修复失败 audit 回滚、Credential 网络上下文、schema 提前
  吞掉原因缺失、敏感 GET URL 与文件体积问题；最终无剩余 blocking security/logic finding。
