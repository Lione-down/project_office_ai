# Office AI Alpha 执行基线

- 状态：`APPROVED`
- 范围基线：`.hermes/plans/2026-07-22_000414-office-ai-alpha.md`
- 任务索引：`.hermes/plans/office-ai-alpha-tasks/README.md`
- UI 基线：`docs/ui-v1/README.md`（`APPROVED-V1`）
- 执行方式：20 个顺序任务，每次只完成一个 dependency-ready 任务

本文是实施期的精简执行真源，不替代总计划中的详细论证。若描述冲突，以总计划的功能、安全和完成定义为最高优先级，以任务文档限定当前 commit 边界。

## 目标

在四周 Alpha 范围内交付可在 Windows 本地运行的 Office AI：用户从合法销售材料生成经过证据约束和质量门禁的 PPTX、XLSX，系统使用真实 Agnes API，并具备用户、管理员、资产、任务、积分与审计闭环。

## 锁定交付范围

- `+86` 手机号、邀请码注册、密码登录、Session/Refresh Token、管理员重置密码。
- 按 UI V1 实现用户端和管理端 Alpha 功能壳；UI V1 只约束视觉层级、结构、配色和交互密度。
- 本地资产上传、隔离、ClamAV 扫描、解析、PaddleOCR、预览、下载和删除。
- 输入支持 XLSX、CSV、DOCX、PDF、PNG、JPG、JPEG、WEBP、TXT、MD；XLSM 只读安全数据且不执行宏。
- Agnes 2.0 Flash Provider Adapter，管理员可配置 Provider、独立 Credential 和发布模型；不静默切换 Provider。
- 两个用户可见 Skill：销售经营汇报（PPTX）与销售数据分析和经营看板（XLSX），可共享材料组合执行。
- 结构化 Brief、版本、证据引用、冲突处理、用户确认、预计积分和异步生成。
- 3 套系统 PPT 模板、2 套系统 Excel 模板、确定性 renderer、LibreOffice 兼容验证和质量门禁。
- MySQL 持久任务、Outbox、Redis 队列、checkpoint、幂等、有限重试、积分预留/结算/释放。
- 管理员可查看、预览、下载和删除全部用户资产；所有敏感操作必须重新认证并写入 audit log。

## 明确非范围

- UI V1 之后的品牌升级、高保真动效、像素级终稿和完整多端响应式。
- 在线 PPT/Excel 编辑器、团队/Workspace/组织协作、微信、小程序、支付、会员和生产部署。
- 用户私人模板上传、任意 PPTX 母版无损复刻、PPTX 输入和任意历史 Excel 无损往返。
- VBA、宏执行、Power Query、Power Pivot、DAX、ActiveX、外部连接和第三方插件。
- Alpha 两个 Skill 之外的业务 Skill、任意 Skill 组合和多 Provider 正式质量认证。
- 绕过加密/保护、将本地图片暴露到公网或把文档内容当作 System Prompt。

## 架构与权威边界

```text
Browser -> Vue -> FastAPI -> MySQL
                    |       -> local protected files
                    |       -> Outbox -> Redis
                    |                    -> Python worker
                    |                    -> PPT renderer
                    -> Agnes Provider Adapter -> Agnes API

Python worker -> ClamAV / PaddleOCR / LibreOffice / Excel renderer
PPT renderer  -> LibreOffice QA
```

- MySQL 是用户、资产、配置、任务和账务的事实来源；Redis 可丢失并可从 MySQL Outbox 恢复。
- Provider credential 由 FastAPI 管理并加密保存；解析 worker 只在 internal network，通过受控内部边界请求需要的工作，不挂载 credential、不直接访问公网。
- 文件二进制不进入 MySQL，存放于 `backend/files/`；预览和下载只能通过授权 API。
- renderer 只接收 Schema 验证后的 `PresentationPlan` 或 `WorkbookPlan`，不直接渲染模型自由文本。

## 核心状态机

资产：

```text
uploaded -> quarantined -> scanning -> parsing -> ready
任一处理阶段失败 -> rejected
用户删除 -> deleting -> deleted
```

任务：

```text
draft -> preflight -> needs_resolution -> queued -> running
running -> succeeded | partial_success | provider_uncertain | failed | cancelled
```

积分流水：

```text
registration_grant | admin_grant
generation_reserve -> generation_finalize | generation_release -> refund
```

- `provider_uncertain` 保留预留，未经确认不得重试扣费。
- `partial_success` 只结算成功的 PPTX/XLSX 子输出。
- `credit_ledger` 只追加并作为账务真相；`users.credit_balance` 只是事务内缓存。

## 证据、质量与安全门禁

- 证据类型限定为 `source_fact`、`calculated_fact`、`ai_inference`，每项保留资产版本和 Sheet/单元格、页码、段落或 OCR BBox 定位。
- 数字 OCR 置信度低于 `0.90` 阻断相关计算；叙述低于 `0.75` 告警；单位未知或来源冲突必须解决。
- 个人术语库按 `library_id + version` 保存不可变 snapshot；`terminology-normalization.v1` 只执行显式数字、单位、币种和绝对日期规则，项目规则覆盖同用户全局规则，歧义、未知单位和来源冲突形成 unresolved item。
- 标准化只生成保留 source fact raw/provenance 的派生 Evidence，不改写已落盘 Manifest；历史 Brief/任务固定引用术语库版本。
- Agnes Structured Brief 必须通过 Pydantic/JSON Schema；只允许一次约束修复，仍失败则失败且不扣费。
- PPT QA 使用版本化报告关联原输出、Renderer/template/Plan、LibreOffice PDF/逐页 PNG 与 validated artifact；`passed` 和 `passed_with_warnings` 可下载，`blocked` 最多自动修复一次，仍失败则禁止下载且不扣费。
- 密码使用 Argon2id，Refresh Token 只保存 Hash，API Key 使用应用层加密，Master Key 只存在环境变量。
- 日志不得包含密码、Key、签名 URL、完整文件、完整 Prompt 或未清理的用户输入。

## 数据与 API

- Alpha 固定 21 张表，详细字段与约束见 `docs/DATA_MODEL.md`。
- HTTP API 统一以 `/api/v1` 开头，详细端点和共同行为见 `docs/API.md`。
- 环境变量和安全录入方式见 `docs/ENVIRONMENT.md`，安全边界见 `docs/SECURITY.md`。

## 四周 Gate

| Gate | 对应任务 | 可验证结果 |
|---|---|---|
| Week 1 | `T1-001`–`T1-005` | 可注册登录、配置 Provider/模型并管理本地资产 |
| Week 2 | `T2-001`–`T2-005` | 材料形成带证据的 Structured Brief，可修改、解决冲突并确认 |
| Week 3 | `T3-001`–`T3-005` | 同一材料异步生成 PPTX 与 XLSX，通过基础 QA 并下载 |
| Week 4 | `T4-001`–`T4-005` | 冷启动、真实 Agnes、黄金回归、Office/WPS 人工验收和敏感信息检查完成 |

## Alpha 完成定义

- 必须交付项全部完成，明确非范围没有被加入。
- 自动测试、10 组脱敏黄金材料的 PPT/Excel 回归全部通过。
- 所有 `passed` 文件经 Microsoft Office 与 WPS 人工打开且无修复提示。
- 真实 Agnes Contract Test 和 Git 敏感信息检查通过。
- `docs/PLAN.md`、`docs/PROGRESS.md`、实现、测试、Git 与推送状态一致。
- 没有未解释的阻断错误、证据伪造路径或重复扣费路径。
