# Office AI Alpha 安全基线

## 安全目标

- 不跨用户访问资产，不以磁盘路径代替授权。
- 不把 Secret、完整用户内容或第三方签名 URL泄露到 Git、日志、队列或错误响应。
- 不执行不可信 Office 内容、宏、外部连接、嵌入对象或文档 URL。
- 任务、积分和 Provider 不确定状态可恢复且不会重复扣费。
- 管理员最高权限可追溯、需重新认证、不能绕过 audit。

## 身份与授权

- 密码使用 Argon2id；禁止明文或可逆保存。
- Refresh Token 仅保存 hash，支持撤销和轮换；密码重置后强制改密并撤销相关 Session。
- Access Token 必须同时通过签名/过期校验，并关联数据库中未过期、未撤销的 Session；退出、改密与管理员 reset 均使相关 Session 失效。
- 注册密码长度为 12–128；管理员 Bootstrap 不提供默认凭据，且只读取 runtime environment。
- 用户只能访问自己的项目、资产、Brief、任务、输出和积分流水。
- 管理员敏感操作要求近期重新认证与非空原因；失败尝试同样写 audit log。
- 登录、注册、邀请码、密码重置和 Credential 测试使用 Redis 限速，并保留 CAPTCHA gate。
- 登录失败才消耗失败限速预算；注册与邀请码校验分别按脱敏 key 限速，Redis key 不包含明文手机号、IP 或邀请码。

## Secret 管理

- API Key 每个数据库记录只保存一个随机化 Fernet 密文和 SHA-256 不可逆 fingerprint；同 Provider fingerprint 唯一。
- 应用层 Master Key 只来自 runtime Secret，不写数据库、不进入镜像、不提交。
- Credential 默认掩码；Reveal 响应 `Cache-Control: no-store`，仅短暂返回并记录 actor、reason、result。
- Credential 常规列表使用固定掩码且不调用 decrypt；名称、状态和限流 PATCH 不允许替换 encrypted key 或 fingerprint，轮换通过新 ID 完成。
- Provider Key 不进入 queue payload、worker environment、trace、exception 或 audit context。
- 缺少 Master Key、解密失败或 credential 状态异常时 fail closed，不静默切换 Provider。

## 文件隔离与解析沙箱

```text
upload -> quarantine -> MIME/extension -> size/archive limits
       -> ClamAV -> isolated parser -> Evidence Manifest -> ready
```

- 上传最多 20 个文件；单文件 50 MB、单任务 200 MB、图片 20 MB、PDF 200 页。
- Excel 最多 30 Sheet/30 万非空单元格；加密、密码保护、损坏文件在积分预留前拒绝。
- 解析 worker 只连 internal network，不挂载 Provider credential；输入只读，输出限额。
- XLSM 只提取安全数据且不执行宏；拒绝 XLS；不跟随文档 URL或外部连接。
- 文档文本始终是 untrusted data，不拼入 System Prompt，不改变工具权限。
- 活动文件按不可变 `user_id/asset_id` 存储，不使用手机号或原始文件名作为路径。
- T1-005 Local Storage 只接受结构化 UUID key，解析后必须仍位于受控 root；客户端不能提交磁盘路径或 `storage_key`。
- 上传按 1 MiB chunk 写入并增量计算 SHA-256；signature probe 只读 12-byte header，不把完整文件加载到内存。文件名经过 NFKC、basename、长度与 Unicode control category 清理。
- upload 专用 ASGI middleware 在读取 body 前先验证 Bearer Session 和 owner/idempotency replay policy，再要求唯一合法且与实际 bytes 一致的 `Content-Length`、拒绝 `Transfer-Encoding`。新请求先进入 1 MiB memory-threshold 的受控 preflight spool，完整限额验证后才 replay 给 Starlette parser；低报/超限拒绝路径不会创建 parser spool，preflight spool 在 `finally` 关闭。未认证、completed replay 或 incomplete replay conflict 均零 body receive。
- 相同用户的 `Idempotency-Key` 由数据库唯一约束兜底；`quarantined` 及后续已持久化状态在 middleware preflight spool 与 endpoint `request.form()` 前返回既有资产，`uploaded`/`deleting` 在相同位置稳定返回 `409 asset_upload_in_progress`。数据库 unique race fallback 使用相同分类，测试证明两条路径的 body receive、multipart parser/spool 与 service upload 均为零；signature/stream cleanup 成功删除 checkpoint 后 later retry 可重新成功。新请求只允许一个 `file` 与至多一个 `project_id`，拒绝额外文件/未知字段。preview/download 只返回 owner-scoped FileResponse 和安全 Header，不返回存储定位。
- 默认项目通过 generated owner key 保证每个用户最多一个活动默认项目；上传在文件 I/O 前提交 owner-scoped `uploaded` checkpoint，最终状态事务再次锁定并重验项目。signature/project cleanup 成功后移除 checkpoint，cleanup 失败保留 `deleting`；最终 transaction failure/cancellation 保留 `uploaded` 定位已写文件，归档/删除不能与上传交错放行，也不产生无数据库记录的 orphan file。cleanup/reconciliation failure 只作为安全 exception note/marker 与脱敏 `asset_recovery_failed` 日志记录，不覆盖 signature、size、stream 或 cancellation 主因。
- 资产物理删除错误不得忽略；只有具体资产目录清理成功或本就不存在时才进入 `deleted`。首次 checkpoint commit 发生在文件 I/O 前，失败时没有 quarantine 文件；finalization metadata commit 异常保留 `uploaded` checkpoint 与已写文件供恢复，不做破坏 durable tracking 的删除。signature/stream 等写入失败才清理本次 quarantine 目录与 checkpoint；partial write 的清理失败显式记录并保留 `deleting`，不能被二次 cleanup 覆盖或静默留下 orphan file。
- T1-005 只做扩展名/MIME/minimal signature 初检；ClamAV、Zip Bomb、加密/损坏 Office、页数/Sheet/单元格与 20 文件/200 MB 组合门禁属于 T2-001，未扫描资产保持 `quarantined`，不得标记 `ready`。
- T2-001 在 ClamAV 前重新计算 quarantine 文件 byte size 与 SHA-256，防止上传后到扫描前的磁盘替换；ClamAV 使用 `INSTREAM`，感染、协议错误、timeout 或连接失败全部 fail closed。Worker service 的 batch contract 在任何 claim/scan 前一次性校验最多 20 文件和 200 MB 总量。
- Office 深度门禁只遍历 ZIP metadata/受限 XML，不展开到磁盘；拒绝路径穿越 member、加密 flag、OLE encrypted package、损坏 archive、伪装 OOXML content type、DTD/entity、member 数量/总解压量/压缩率、单 XML member 或 parser 总结构项超限。DOCX 只读取段落文本，XLSX/XLSM 只读取 cell data；公式、VBA、external relationship、embedded object 和文档 URL 均不执行或抓取。
- PDF 使用 `pypdf` 严格读取并拒绝加密/密码保护与超过 200 页；Excel 拒绝超过 30 Sheet/30 万非空单元格。CSV/TXT/MD 只接受 UTF-8；PNG/JPEG/WEBP 必须通过 bounded streaming 结构检查、decoded-size gate 与 Pillow full decode 后才形成 `pending_ocr` 中间记录，OCR 留给 T2-002。
- Parser 只在可终止子进程中运行并受 wall-clock timeout 约束；worker 每轮 polling 先把超出 stale lease 的 `scanning/parsing` 资产稳定拒绝为 `processing_lease_expired`，避免 crash、OOM、SIGTERM 或暂时 DB outage 后永久滞留。
- worker 以原子条件更新 claim 单个 `quarantined` 资产，持久化 `scanning -> parsing -> ready/rejected`；进入 `parsing` 时先提交 deterministic intended output key，再写结构化输出。parser 名称/版本、告警代码和脱敏错误写入 MySQL；若 output write 后 hard crash，stale reconciliation 仍保留精确 recovery key；若 DB finalization 与输出清理同时失败，rejected 记录保留该 key 和 `parsed_output_cleanup_failed` 告警，不留下不可追踪 orphan。
- Asset API 只返回 parser 名称/版本、告警代码、稳定错误码与脱敏错误；不返回原始/解析 storage key、绝对路径或文档内容。

## Provider 与 Prompt 安全

- 发送给 Agnes 的内容来自经过限制与版本化的 evidence/context，不发送本地路径或不必要的原文件。
- 本地图片不通过公网 tunnel 暴露；Alpha 使用 OCR 文本和元数据。
- Structured Brief 通过 Pydantic/JSON Schema，schema 修复只允许一次。
- 模型推断必须标记 `ai_inference`，不能冒充 `source_fact`。
- `400` 不重试，`401/403` 暂停 Credential，`429/5xx` 有限重试，timeout 不确定进入 `provider_uncertain`。
- Agnes 配置写入前验证 HTTPS、默认 `agnes-2.0-flash`、保守 `256K` Context 与 120 秒 timeout；Alpha 不认证其他 Provider，不静默切换。

## 任务与账务

- 生成创建、积分 reserve 和 Outbox 在同一事务边界内；数据库唯一键保证幂等。
- Redis 丢失后从 MySQL Outbox 和 checkpoint 恢复，不能依据 queue 孤立消息扣费。
- 失败任务释放 reserve；partial success 只 finalize 成功子输出；质量自动修复不额外收费。
- `provider_uncertain` 不自动重试或重复结算，需要受审计决策。
- `credit_ledger` 与 `audit_logs` 只追加，不提供修改/删除业务接口。

## 日志与审计

- 禁止记录密码、Key、Token、签名 URL、完整文件、完整 Prompt、明文手机号、完整 IP、Fingerprint 或 Trace 上下文中的 Secret。
- 文件名和用户输入需限制长度、清理控制字符；错误详情使用分类与脱敏摘要。
- 管理资产预览/下载/删除、Credential Reveal/测试、密码重置、用户状态、任务重试、积分调整全部审计。
- Audit 至少包含 actor、action、target、reason、result、IP/User-Agent 摘要、trace ID 和 UTC 时间。

## Web 与容器

- CORS 仅允许 `OFFICE_AI_FRONTEND_ORIGIN`；生产配置不得使用 `*`。
- 错误响应不暴露 stack trace、SQL、绝对路径、内部 host 或 Secret。
- 容器默认 non-root，文件卷使用最小写权限；数据库和内部工具不映射 Host 端口。
- `worker`、ClamAV、PaddleOCR、LibreOffice、MySQL、Redis 和 renderer 使用 internal network；只有 FastAPI 具备受控 external egress。
- 镜像版本需锁定，新增 dependency 在任务内运行 vulnerability/license 检查。

## Git 与交付 Gate

- `.env`、`backend/files/`、output、日志、缓存、数据库目录、私有 golden data 必须被忽略。
- 使用精确路径暂存；推送前检查 `.gitignore`、暂存区、diff 和新增二进制来源。
- 获授权且脱敏的 golden sample 才能进入 Git；不确定授权时留在 `golden-data/private/`。
- Alpha 完成前运行全历史新增敏感信息检查，并记录 Microsoft Office/WPS 与真实 Agnes 人工/contract 证据。

## Incident 最小响应

1. 停用受影响 Credential/Session，阻止新任务。
2. 保留只读 audit 和 task evidence，避免破坏调查链。
3. 轮换 Secret，识别受影响资产与调用。
4. 修复并增加回归测试，将不含 Secret 的原因和预防措施记录到 `pitfalls.md`。
