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
- T4-002 的敏感 HTTP body 使用当前管理员密码完成逐次 Argon2id re-auth；preview/download
  使用 POST JSON，禁止把密码或原因放入 query。前端取消不发请求，提交期间禁用重复触发。
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
- Excel 最多 100 Sheet/30 万非空单元格；加密、密码保护、损坏文件在积分预留前拒绝。
- 解析 worker 和 PaddleOCR 只连 internal network，不挂载 Provider credential；输入只读，解析/Manifest 输出使用独立限额 volume。
- XLSM 只提取安全数据且不执行宏；拒绝 XLS；不跟随文档 URL或外部连接。
- 文档文本始终是 untrusted data，不拼入 System Prompt，不改变工具权限。
- 活动文件按不可变 `user_id/asset_id` 存储，不使用手机号或原始文件名作为路径。
- T1-005 Local Storage 只接受结构化 UUID key，解析后必须仍位于受控 root；客户端不能提交磁盘路径或 `storage_key`。
- 上传按 1 MiB chunk 写入并增量计算 SHA-256；signature probe 只读 12-byte header，不把完整文件加载到内存。文件名经过 NFKC、basename、长度与 Unicode control category 清理。
- upload 专用 ASGI middleware 在读取 body 前先验证 Bearer Session 和 owner/idempotency replay policy，再要求唯一合法且与实际 bytes 一致的 `Content-Length`、拒绝 `Transfer-Encoding`。新请求先进入 1 MiB memory-threshold 的受控 preflight spool，完整限额验证后才 replay 给 Starlette parser；低报/超限拒绝路径不会创建 parser spool，preflight spool 在 `finally` 关闭。未认证、completed replay 或 incomplete replay conflict 均零 body receive。
- 相同用户的 `Idempotency-Key` 由数据库唯一约束兜底；`quarantined` 及后续已持久化状态在 middleware preflight spool 与 endpoint `request.form()` 前返回既有资产，`uploaded`/`deleting` 在相同位置稳定返回 `409 asset_upload_in_progress`。数据库 unique race fallback 使用相同分类，测试证明两条路径的 body receive、multipart parser/spool 与 service upload 均为零；signature/stream cleanup 成功删除 checkpoint 后 later retry 可重新成功。新请求只允许一个 `file` 与至多一个 `project_id`，拒绝额外文件/未知字段。preview/download 只返回 owner-scoped FileResponse 和安全 Header，不返回存储定位。
- 默认项目通过 generated owner key 保证每个用户最多一个活动默认项目；上传在文件 I/O 前提交 owner-scoped `uploaded` checkpoint，最终状态事务再次锁定并重验项目。signature/project cleanup 成功后移除 checkpoint，cleanup 失败保留 `deleting`；最终 transaction failure/cancellation 保留 `uploaded` 定位已写文件，归档/删除不能与上传交错放行，也不产生无数据库记录的 orphan file。cleanup/reconciliation failure 只作为安全 exception note/marker 与脱敏 `asset_recovery_failed` 日志记录，不覆盖 signature、size、stream 或 cancellation 主因。
- 资产物理删除错误不得忽略；只有原始文件、结构化解析结果与 Evidence Manifest 三类具体资产输出均清理成功或本就不存在时才进入 `deleted`。`scanning/parsing` 期间拒绝删除并返回 `409 asset_processing_in_progress`，避免 worker 在删除完成后重新写出派生 orphan；处理完成或 stale lease 收口后可重试。清理中断保留 `deleting` 和 deterministic keys，重试时对已删除输出保持幂等。首次 checkpoint commit 发生在文件 I/O 前，失败时没有 quarantine 文件；finalization metadata commit 异常保留 `uploaded` checkpoint 与已写文件供恢复，不做破坏 durable tracking 的删除。signature/stream 等写入失败才清理本次 quarantine 目录与 checkpoint；partial write 的清理失败显式记录并保留 `deleting`，不能被二次 cleanup 覆盖或静默留下 orphan file。
- T1-005 只做扩展名/MIME/minimal signature 初检；ClamAV、Zip Bomb、加密/损坏 Office、页数/Sheet/单元格与 20 文件/200 MB 组合门禁属于 T2-001，未扫描资产保持 `quarantined`，不得标记 `ready`。
- T2-001 在 ClamAV 前重新计算 quarantine 文件 byte size 与 SHA-256，防止上传后到扫描前的磁盘替换；ClamAV 使用 `INSTREAM`，感染、协议错误、timeout 或连接失败全部 fail closed。Worker service 的 batch contract 在任何 claim/scan 前一次性校验最多 20 文件和 200 MB 总量。
- Office 深度门禁只遍历 ZIP metadata/受限 XML，不展开到磁盘；拒绝路径穿越 member、加密 flag、OLE encrypted package、损坏 archive、伪装 OOXML content type、DTD/entity、member 数量/总解压量/压缩率、单 XML member 或 parser 总结构项超限。DOCX 只读取段落文本，XLSX/XLSM 只读取 cell data；公式、VBA、external relationship、embedded object 和文档 URL 均不执行或抓取。
- PDF 使用 `pypdf` 严格读取并拒绝加密/密码保护与超过 200 页，同时保留页码和 text-matrix 推导的 BBox；Excel 拒绝超过 100 Sheet/30 万非空单元格并保留原始 cell reference。CSV/TXT/MD 只接受 UTF-8；PNG/JPEG/WEBP 必须通过 bounded streaming 结构检查、decoded-size gate 与 Pillow full decode 后才形成 `pending_ocr` 中间记录。
- Parser 只在可终止子进程中运行并受 wall-clock timeout 约束；worker 每轮 polling 先把超出 stale lease 的 `scanning/parsing` 资产稳定拒绝为 `processing_lease_expired`，避免 crash、OOM、SIGTERM 或暂时 DB outage 后永久滞留。
- worker 以原子条件更新 claim 单个 `quarantined` 资产，持久化 `scanning -> parsing/evidence -> ready/rejected`；进入 `parsing` 时先提交 deterministic parsed key，Evidence 文件写前再提交 deterministic Manifest key 和 `building`。只有版本化 Pydantic/JSON Schema 校验、原子文件写入与最终 DB 条件更新全部成功才进入 `ready`；hard crash/stale reconciliation 保留精确 recovery keys 并把 Manifest 标为 `invalid`。
- OCR client 只向 `http://paddleocr:8080/v1/ocr` 发送已完成安全解码的原始图片 bytes、MIME 和 SHA-256；timeout、network、429/502/503/504、响应大小/项数超限、非法 JSON/Schema、非有限 confidence/coordinates 全部 fail closed。暂时性不可用先清理本轮输出并按 30/60 秒 backoff 重试，最多 3 次；其他错误或重试耗尽稳定拒绝，不生成空白或猜测证据。
- Evidence Manifest 只允许三类显式 provenance：本任务生成 `source_fact`，`calculated_fact` 必须带 calculation expression，`ai_inference` 必须带 model identity；T2-002 不生成后两类。每条 source fact 关联资产 UUID、`sha256:` 资产版本、parser/OCR engine 版本和 Excel cell、PDF page/BBox、Word paragraph、CSV cell、text line 或 image OCR BBox。Post-Alpha 默认最多预算 11563 个过滤前 source item，在空值过滤和 Pydantic Evidence object expansion 前执行，避免小值/高结构输入放大 worker memory；第 11564 项稳定拒绝。该精确值只校准数量，不放宽 Manifest byte、语义 blocker 或任何 provenance 规则。
- 叙述 OCR confidence `<0.75` 只告警；数字 `<0.90` 或单位未知设置 calculation blocker。未知单位保持 `null`，不得默认零、币种或任意单位；来源冲突裁决和术语标准化仍属于 T2-003。
- Preflight 只把 Structured Brief 实际引用的 Evidence blocker 带入本次输出门禁，不能让
  未使用的整份 Manifest 问题造成无界 UI/response 放大；Manifest 与 Evidence 的同义
  blocker 必须 canonicalize 后按 Evidence ID 去重。该范围收敛不等于忽略问题，任何被引用
  的单位未知仍阻断确认。
- `assign_unit` resolution 必须来自受支持的 canonical unit 白名单并精确匹配当前
  owner-scoped Preflight finding。服务只在新 Brief Revision 的 `source_snapshot` 和
  generation input snapshot 中保存裁决，不改写原始 Manifest/Evidence；页面只返回来源
  位置，不返回非必要 raw value，也不得根据业务语境猜测单位。
- 术语库 API 和 service 始终按 access Session 的 `user_id` 查询；跨用户 library/item/project ID 与不存在资源使用相同 not-found 语义，不能通过版本查询或项目覆盖枚举其他用户 snapshot。
- 术语库 mutation 只追加不可变 version 与完整条目 snapshot，删除只追加 tombstone；历史任务固定引用 `library_id + version`，回滚规则不得改写已生成 Manifest、Brief 或任务输入。
- 标准化使用固定 `terminology-normalization.v1`，不调用模型或公网；只识别显式绝对日期、数字、百分比、币种、万/亿倍率和受支持销售单位。缺少年份、未知单位、显式 unit/currency 冲突全部保留 raw 并阻断，不从上下文猜测。
- 项目规则只覆盖同一用户同一项目的全局匹配；同层级同优先级别名歧义与同一事实多来源值不一致形成 unresolved item。来源冲突必须由用户指定权威 evidence ID，系统不得按顺序、最大值或最新文件静默裁决。
- `NormalizedEvidenceItem` 继承 source fact 的 asset/version/location/raw/parser/OCR provenance，只附加 normalized value、规则版本与术语库 version 引用；不能把标准化结果伪装为 `ai_inference`，也不改写 `evidence-manifest.v1`。
- Asset API 只返回 parser/Manifest Schema/engine 版本、warning/blocker 数量、稳定错误码与脱敏错误；不返回原始/解析/Manifest storage key、Manifest SHA-256、绝对路径、OCR 原文、BBox 或证据内容。

## Provider 与 Prompt 安全

- 发送给 Agnes 的内容来自经过限制与版本化的 evidence/context，不发送本地路径或不必要的原文件。
- 本地图片不通过公网 tunnel 暴露；Alpha 使用 OCR 文本和元数据。
- Structured Brief 通过 Pydantic/JSON Schema，schema 修复只允许一次。
- 模型推断必须标记 `ai_inference`，不能冒充 `source_fact`。
- `400` 不重试，`401/403` 暂停 Credential，`429/5xx` 有限重试，timeout 不确定进入 `provider_uncertain`。
- Agnes 配置写入前验证 HTTPS、默认 `agnes-2.0-flash`、保守 `256K` Context 与 120 秒 timeout；Alpha 不认证其他 Provider，不静默切换。
- native `response_format` 只有在 Provider 配置的布尔 capability
  `native_response_format=true` 时发送；默认省略不代表降低 Structured Brief 约束，响应
  仍必须通过应用层 strict Schema、Evidence 引用和一次 repair。非布尔 capability fail
  closed，禁止根据一次 400 静默永久改变全局 Provider 行为。
- T2-004 只从 owner-scoped、`ready` 且 key/SHA/asset version 完整性复验通过的 Manifest 构建 Context；Manifest read 上限为配置容量加 1 byte，不对被篡改的大文件执行无界读取。Evidence 和术语内容只进入 user message，固定 system contract 明确其为 untrusted data。
- Context 同时受 evidence budget 和完整 message+max-output budget 约束；不足时在调用前 fail closed，不截断必需 evidence。`brief-evidence-context.v2` 只消除重复编码：asset identity/version 进入一次性 table，Evidence 按 location kind/Sheet/type 分组并使用确定性短引用；不抽样、不改写原值或 provenance。Agnes 只允许返回本次短引用，应用在校验和落库前严格映射回原始不可变 Evidence ID，未知引用 fail closed。选定术语库必须使用显式 owner/project `library_id + version`，只发送该 snapshot 的标准术语、别名、unit、口径与优先级。
- Structured Brief 完整 JSON Schema 是静态应用 contract，不含用户数据或 Secret，可随
  generation/repair prompt 发送。repair validation hints 只由 Pydantic 固定字段路径、
  数组索引和错误类型构造；未知字段名归一为 `unknown_field`，最多 24 条、每条 160
  字符。禁止把 validation input、字段值、原始 response 或 exception context 放入 hints、
  日志、数据库或用户响应。
- Agnes 输出必须精确保持 user goal/audience/include/exclude、asset/term/Skill/model snapshot 与 Skill 对应 output kind；`file/calculation` fact 和 `agnes_inference` 必须引用本次 Context 已知 evidence ID。非法结构或伪造引用只允许一次 repair，仍失败不创建 Brief 或积分。
- `provider_calls` 只保存 ID、attempt、Request ID、Token、耗时、状态、错误分类和 `is_redacted=true`，禁止持久化 Key、Prompt、响应正文、文件内容、本地路径或 storage key。Brief API 响应使用 `private, no-store`。
- T2-005 Brief GET/PATCH/Preflight/confirm 全部先认证并按 `briefs.user_id` owner scope 查询；跨用户 ID 与不存在资源统一为 not-found。PATCH 只追加新 Revision，不能由客户端替换来源资产、术语、Skill、模型或 Evidence snapshot；过期 Revision 与已确认 Revision fail closed。
- Preflight 必须重新验证资产版本和 Manifest integrity、Evidence blocker、Brief unresolved item、Skill row 全合同、系统模板 allowlist、模型 snapshot identity、Agnes Provider、active Credential、allowed Skills 和 structured-output 能力。显式 resolution 的 code/action/evidence IDs 必须匹配当前 unresolved item，不能用任意 payload 静默移除 blocker。
- confirm 只在无 blocking/incompatible finding 且用户接受当前预计积分时提交；model multiplier、模板和各子输出费用进入不可变 snapshot。费用变化或新增 blocker 的最新 snapshot 先提交再返回 409；已确认快照不重算、不提高。本阶段不读取 Secret、不调用 Provider、不扣积分，也不创建 task/ledger/Outbox。

## 任务与账务

- 点击生成先建立 owner-scoped `workflow_tasks + outbox_events` 数据库事实，再由专用
  workflow worker 调用 Agnes。任务 snapshot 只保存结构化 ID/选择项、进度、稳定失败码
  和可安全展示原因，不保存 Prompt、Provider response、文件正文、Evidence、Credential、
  storage key 或本地路径。
- `workflow-worker` 是唯一新增的 Provider-capable worker：只读 Evidence volume、无
  Host port、non-root/read-only rootfs，连接受控 edge/private network。解析 `worker`
  继续没有 Master Key 且不能访问公网，不能因复用 backend image 扩大其权限。
- Brief queue 重复投递由 MySQL claim 去重；确定失败可保留原因，Provider 已 in-flight
  后 stale 必须转 `provider_uncertain`，不能自动重复外部调用。List/detail 只允许 owner，
  响应 `private, no-store`；跨用户 ID 不泄露存在性。
- T3-001 生成创建只接受 owner 的最新 confirmed Brief；同事务锁定用户余额与 Model/Credential/Provider，复验 Skill/model identity、capability、pricing 和子输出费用总和，再写不可变 inputs、task/steps、负数 reserve 与首个 Outbox。数据库唯一键保证幂等，任一写入失败整体回滚。
- 每用户最多 2 个 running task；Credential 最大并发使用数据库 active checkpoint，RPM/TPM 使用单个 Redis Lua 原子窗口预算。Redis 限流丢失不能改变 task/ledger 事实，恢复后只影响新的 admission。
- Redis queue 丢失后从 MySQL Outbox 和 checkpoint 恢复，不能依据孤立 queue message 扣费。重复投递由数据库 claim 去重；safe stale step 可重试，已经进入 Provider 且结果未知的 checkpoint 必须转 `provider_uncertain`。
- 失败或可取消任务释放 reserve；partial success 只 finalize 成功子输出并 release 余量；质量自动修复不额外收费。`provider_uncertain` 保留 reserve，不自动重试或重复结算，需要后续受审计决策。
- `credit_ledger` 与 `audit_logs` 只追加，不提供修改/删除业务接口。
- Generation、Credits、Outbox/queue payload 和日志不得包含 Credential Secret、Prompt、文件正文、storage key 或本地路径；用户 task/credits 响应使用 `private, no-store`。
- T4-004 真实恢复演练只使用隔离 UUID、合成用户、假 Credential 和真实 MySQL/Redis，
  不访问 Provider 或用户文件。Redis outage 必须保留 pending Outbox/reserve；恢复后新 worker
  只执行一次，duplicate delivery 不重复执行或结算；`provider_uncertain` 继续保留 reserve。

## PPT Renderer 与生成输出

- Renderer 只接受严格版本化 `PresentationPlan`；未知字段/版本、自由文本根对象、非有限或超精度数值、未知 Evidence/data/image 引用、路径型图片和客户端输出路径全部 fail closed。
- Python 与 Node 使用同一 canonical Plan hash；Python 再验证 response schema、request ID、模板/Renderer 版本、页数、Plan/file SHA-256、byte size 和唯一受控相对 key。HTTP request/response 均有上限，错误不回显 Plan、图片、路径或 stack。
- 同 request 的并发执行在 Renderer 内串行；sidecar replay 验证 Plan 和实际文件 hash/size，缺失或损坏的 derived output 可安全重建，不同 Plan 使用同一 request ID 时拒绝。
- Renderer 容器 non-root、read-only rootfs、private network、无 Host port、无 Secret/Redis/Provider credential；Backend 只读挂载 renderer work volume。最终资产使用 owner-scoped fixed key 和 stable asset ID 原子写入，不覆盖完成输出，ready replay 必须复验磁盘 integrity。

## PPT 质量门禁

- `presentation-quality-report.v1` 为 strict schema；finding 只保存稳定 code、severity、rule version、repairable 与可选页码，不保存正文、文件名、storage key、绝对路径或用户材料。
- OOXML 检查限制 ZIP entry 数量、单项/总解压大小、压缩比和 XML 大小，拒绝 path traversal、加密 entry、DTD/entity、坏 relationship、缺图、坏 chart range 与未知 Evidence 引用。
- LibreOffice sidecar 只接受固定 asset identity/hash/size/source variant；源文件与输出均使用服务端派生 key。request replay 必须同时复验 manifest、PDF 与逐页 PNG 的实际 hash/size，不能只信 sidecar JSON。
- 自动修复只允许一次且仅处理确定性 geometry/autofit 规则；repaired PPTX 使用新 key，原始输出永不覆盖。报告、preview 或 validated artifact 任一漂移均 fail closed，`blocked` 禁止下载并触发既有 release 结算。

## Excel Renderer 与验证副本

- `workbook-plan.v1` strict schema 禁止未知字段、自由公式、路径、外部连接、宏、Pivot、
  Power Query 和客户端输出位置；最多 20 Sheet、200,000 个实际生成 cell，Sheet/column/
  chart range、Excel anchor 与 inline validation 长度在写文件前校验。
- Renderer 只生成英文 `SUM/AVERAGE/COUNT/IFERROR/RANK` 和英文逗号；`RANK` 使用
  Microsoft Office 可直接计算的兼容语法，避免未加 `_xlfn.` 的 `RANK.EQ` 产生 `#NAME?`；每个公式同时
  写确定性 cache。普通文本使用显式 string writer，关闭 strings-to-formulas/URLs，
  防止 CSV/Excel formula injection 和自动外链。
- 原始 XLSX 使用 owner/asset 派生 key 原子保存且不可覆盖；Plan SHA-256、
  Schema/Renderer/template version 同时写入输出 trace 与 custom properties。同 Plan
  字节确定性、ZIP 完整性、无 externalLinks/VBA 和原件 hash 不变均有回归。
- LibreOffice sidecar request 只接受 UUID/hash/size/version，不接受路径、正文、Secret
  或任意 command。sidecar 以固定 key 只读原件，用独立 profile 重算 validation copy；
  Backend 复验 response 上限、固定 shared-work key、hash/size、完整 trace 和
  `workbook-validation-report.v1`，完成 replay 不单独信任 report JSON。
- validation report 不保存公式正文，只记录 Sheet/cell、formula-changed 和 cache 前后值；
  原件/copy/report 任一缺失、损坏、漂移，坏 XLSX 或 request ID/input fingerprint 冲突
  均 fail closed。
- `workbook-quality-report.v1` 只保存稳定 finding code、severity 和受限定位，不保存公式
  正文、storage key、本地路径或用户材料。公式错误类型、原始值/公式 cache/summary
  确定性复算、精确 chart range 与未解决 Sheet/字段/单位冲突均 fail closed。
- LibreOffice 原始 validation report、validation copy、最终 validated XLSX 和 quality
  report 使用独立固定 key 与 bounded streaming hash；重放和下载前复验 owner/task/
  category/version/hash/size，阻断输出不暴露 validated key。两个子输出独立结算，重复
  event 只能命中既有 checkpoint/ledger marker。

## 日志与审计

- 禁止记录密码、Key、Token、签名 URL、完整文件、完整 Prompt、明文手机号、完整 IP、Fingerprint 或 Trace 上下文中的 Secret。
- 文件名和用户输入需限制长度、清理控制字符；错误详情使用分类与脱敏摘要。
- 管理资产预览/下载/删除、Credential Reveal/测试、密码重置、用户状态、任务重试、积分调整全部审计。
- Audit 至少包含 actor、action、target、reason、result、IP/User-Agent 摘要、trace ID 和 UTC 时间。
- IP 只保留 IPv4 `/24` 或 IPv6 `/64`，User-Agent 只保留首行 bounded 摘要；audit context
  只接受固定安全字段。空原因、错误密码、目标不存在、业务冲突和文件操作失败均记录
  `failed`，但普通用户权限拒绝不伪造 admin actor。
- 管理员资产 API 只接受资产 UUID，服务端解析 owner 与 deterministic key；不存在和已删除
  资产统一返回安全错误，不返回绝对路径、storage key、签名 URL 或文件正文。活动文件
  删除后 audit 明确记录 30 天备份残留策略，而不是把软删除冒充备份已经物理擦除。

## Web 与容器

- CORS 仅允许 `OFFICE_AI_FRONTEND_ORIGIN`；生产配置不得使用 `*`。
- 错误响应不暴露 stack trace、SQL、绝对路径、内部 host 或 Secret。
- 容器默认 non-root，文件卷使用最小写权限；数据库和内部工具不映射 Host 端口。
- 唯一 root 例外是一次性 `storage-init`：无网络、无 environment/Secret、read-only
  rootfs、`no-new-privileges`，只将四个应用 named volume 根目录设为
  `10001:10001 / 0750` 后退出。所有读取或写入业务数据的长期服务仍为 non-root，且必须
  等待 initializer 成功。
- `worker`、ClamAV、PaddleOCR、LibreOffice、MySQL、Redis 和 renderer 使用 internal network；只有 FastAPI 具备受控 external egress。
- 镜像版本需锁定，新增 dependency 在任务内运行 vulnerability/license 检查。
- T4-005 将 ClamAV 固定为可解析的 `1.4.5`，以 UID/GID `100:101` 直接运行
  `clamd --foreground`，root filesystem read-only，只有 signature volume 和三个
  tmpfs 可写；EICAR INSTREAM 检测通过。固定 signature 可支撑本地 Alpha，但不替代
  可审计的在线更新或定期重建镜像。
- 为执行任务卡中的无附加参数容器 tests，Backend/PPT Renderer 只读挂载 tracked
  Compose、source contract、docs 与脱敏 golden inputs/expected/manifests；禁止挂载
  仓库根、`.env`、`golden-data/private` 或用户文件。默认 Renderer production stage
  仍只安装 production dependencies，并已在 non-root/read-only 容器单独验证。

## Git 与交付 Gate

- `.env`、`backend/files/`、output、日志、缓存、数据库目录、私有 golden data 必须被忽略。
- 使用精确路径暂存；推送前检查 `.gitignore`、暂存区、diff 和新增二进制来源。
- 获授权且脱敏的 golden sample 才能进入 Git；不确定授权时留在 `golden-data/private/`。
- T4-003 的唯一 pilot 原件虽已由用户确认使用权，仍必须在副本中移除人员/客户/终端名称、
  电话、地址、private author metadata、private 路径和非目录嵌入 payload；生成物 author
  只允许脱敏系统值 `Office AI`，递归扫描通过前不得暂存。
  `1/10 pilot` 必须进入 Manifest/报告，禁止切片或复制同一材料制造 corpus 数量。
- Alpha 完成前运行全历史新增敏感信息检查，并记录 Microsoft Office/WPS 与真实 Agnes 人工/contract 证据。

## Incident 最小响应

1. 停用受影响 Credential/Session，阻止新任务。
2. 保留只读 audit 和 task evidence，避免破坏调查链。
3. 轮换 Secret，识别受影响资产与调用。
4. 修复并增加回归测试，将不含 Secret 的原因和预防措施记录到 `pitfalls.md`。
