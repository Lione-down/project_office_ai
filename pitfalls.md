# Office AI 规则变更与踩坑记录

## 记录规则

每条记录包含日期、任务、现象/决策、影响和预防/验证。不得写入 Secret、用户内容或未脱敏材料。

## 项目执行规则

- 每次新会话先读 `AGENTS.md`、`docs/PROGRESS.md`、任务索引和唯一 READY 任务，再读 Git 状态。
- 一次只完成一个 dependency-ready 任务；完成后更新记录、验证、单独 commit 并 push，再新建下一任务。
- 代码前必须已有任务计划；UI 工作先以批准设计/计划为基线，再实现和验收。
- 仅作最小 scoped 修改，不顺手重构；所有任务必须有可验证成功标准。
- 规则增删改必须同步本文件变更记录；全部文本统一 UTF-8。
- GitHub 前检查 `.gitignore`、暂存区和敏感文件；真实 Secret 只通过 runtime Secret 或本地未跟踪配置。

## 踩坑

### 2026-07-22 · T1-001 · Docker CLI/daemon 不可用

- 现象：当前 PowerShell 调用 `docker compose version` 返回 command not found。
- 影响：本机无法启动或拉取容器；不能验证镜像可达性和 runtime health。
- 本任务处理：从 Docker 官方 GitHub release 下载 Compose standalone v5.1.4 到 ignored `tmp/`，校验官方 SHA-256 后运行 `config --quiet` 与 `config --services`，配置解析通过。
- 预防/验证：`T1-002` 在 Docker Desktop/daemon 可用环境补跑 pull/up/health；不得用 config 通过代替 runtime 通过。

### 2026-07-22 · T1-001 · 保留用户已有未提交基线

- 现象：开始任务时已有 UI V1、设计说明和 Alpha 任务拆分的未提交文件。
- 影响：不得通过 reset/checkout 清理；需区分 T1-001 基线依赖与无关工作。
- 预防/验证：精确路径暂存；提交前用 `git diff --cached --name-only` 核对，只纳入批准计划、UI V1 和本任务基线。

### 2026-07-22 · T1-002 · Docker runtime 仍不可用

- 现象：`docker` 与 `docker-compose` 仍为 command not found；standalone Compose v5.1.4 可解析 9 个服务，但 `pull mysql redis` 因 `//./pipe/docker_engine` 不存在而退出 `1`。
- 影响：不能把 image pull、MySQL/Redis container health 或真实 MySQL 空库 migration 标记通过。
- 本任务处理：运行 Backend/Frontend focused tests、Frontend build、MySQL dialect offline migration、SQLite in-memory migration 和本机 Uvicorn health smoke；真实容器证据保留为环境验证缺口。
- 预防/验证：Docker Desktop/daemon 可用后补跑任务卡全部 Compose 命令；不得用 offline/SQLite 结果冒充 MySQL runtime。

### 2026-07-22 · T1-002 · MySQL async driver advisory

- 现象：`pip-audit` 报告 `asyncmy 0.2.11` 受 `PYSEC-2026-286` crafted dict key SQL injection 影响，且无已发布修复版本。
- 影响：继续使用会违反 dependency vulnerability gate。
- 本任务处理：在连接串 contract test 先得到 RED 后，切换为 SQLAlchemy `mysql+aiomysql` 与 `aiomysql 0.3.2`；同时升级 pytest 到已修复版本，复跑 audit 得到 0 known vulnerabilities。
- 预防/验证：每次新增或升级 Python/Node dependency 后运行 vulnerability 与 license metadata 检查，不以“尚未调用危险 API”为理由忽略已知 advisory。

### 2026-07-22 · T1-003 · 认证 runtime 与 offline 证据边界

- 现象：Docker CLI/daemon 仍不可用，standalone Compose 可解析配置，但无法连接 `//./pipe/docker_engine` 拉取 MySQL/Redis。
- 影响：SQLite 事务/migration 和 MySQL dialect offline DDL 只能证明代码路径与 SQL 生成，不能证明真实 MySQL row lock、Redis 限速或容器 health。
- 本任务处理：对注册回滚、Session rotation、Refresh Hash、限速 key 脱敏、Bootstrap 幂等和 HTTP envelope 建立 focused tests，并保留 Docker runtime 验证缺口。
- 预防/验证：Docker runtime 可用后补跑任务卡原始 Compose 命令；成功登录不得消耗失败限速预算，避免注册后自动登录被误限速。

### 2026-07-22 · T1-003 补验 · Windows direct MySQL/Redis 被遗漏

- 现象：Docker CLI/daemon 不可用曾被记录为 MySQL/Redis runtime 不可用，但本机实际存在 Automatic `MySQL80`/`Redis` Windows services，并分别监听 3306/6379。
- 根因：验证只检查 Docker 和无认证 Redis `PING`；项目 `.env` 使用 `OFFICE_AI_DB_*`，与 Settings canonical变量不一致，Redis 又启用了 `requirepass`。
- 本任务处理：Settings 增加兼容 alias；用 `.env` 凭据创建目标 database 并真实升级到 `20260722_0003`；临时注入 Redis认证 URL 后 `/health/ready=200`。
- 预防/验证：Docker 缺失时仍检查 Windows service、process、port 和 authenticated protocol；不得把容器 runtime 与 direct Windows runtime 混为一谈。

### 2026-07-22 · T1-003 补验 · 旧 Redis INFO 编码

- 现象：Windows Redis 3.0.504 authenticated `PING` 成功，但新版 redis-py 解析 `INFO server` 时因输出包含非 UTF-8 本机路径而报 `UnicodeDecodeError`。
- 影响：INFO 解析失败不能用于否定 Redis 可用性；当前认证限速所需的 PING/INCR/EXPIRE path 不依赖 INFO。
- 预防/验证：本机 gate 使用 authenticated `PING` 与应用 `/health/ready`；后续升级 Redis 时再恢复 INFO compatibility 检查。

### 2026-07-22 · T1-004 · focused 通过但 broad pytest collection 冲突

- 现象：`tests/auth/` 与 `tests/providers/` 各自 focused 通过，但全套 pytest 因同名 `test_models.py`、`test_migration.py`、`test_security.py` 被导入为相同顶层 module 而 collection error。
- 影响：只跑单目录不能证明 broad suite 可收集；后续业务域继续出现同名测试文件时会复发。
- 本任务处理：为新增 `tests/providers/` 与 `tests/admin/` 增加 package marker，随后 Backend 最终全套 `84 passed`。
- 预防/验证：新增测试业务域后同时运行 focused 与仓库根 broad；不得用 focused 通过替代全套 collection evidence。

### 2026-07-22 · T1-004 · 新 encryption dependency 必须先过 audit

- 现象：初始约束安装 `cryptography 45.0.7`，`pip-audit` 报告 6 条已知漏洞，修复版本最高要求 `48.0.1`。
- 影响：Fernet 功能测试通过不代表 dependency 可交付；带已知漏洞提交会违反 security gate。
- 本任务处理：提升并固定为 `cryptography>=48.0.1,<49`，重新安装后复跑 focused/broad 和 `pip-audit`，结果为 0 known vulnerabilities。
- 预防/验证：新增 dependency 后在文档/commit 前运行 `pip check`、vulnerability audit 和完整回归，不只依赖 resolver 成功。

### 2026-07-22 · T1-004 · ASGI Runtime probe 必须关闭 lifespan

- 现象：首次真实 readiness probe 直接使用 `ASGITransport`，业务断言通过，但进程退出时因 app lifespan 未运行导致 aiomysql connection cleanup warning。
- 影响：warning 会污染 Runtime 证据，也可能掩盖资源泄漏。
- 本任务处理：在 `app.router.lifespan_context(app)` 内重跑 readiness，MySQL/Redis 均 up、Provider service 配置成功且无清理 warning。
- 预防/验证：直接 ASGI probe 若创建真实资源，必须显式进入/退出 lifespan；测试 client 成功响应不能替代资源关闭验证。

### 2026-07-22 · T1-005 · 文件初检不得整文件读入内存

- 现象：初版 signature probe 使用 `Path.read_bytes()[:12]`，虽然只保留 12 bytes，实际仍先分配并读取整个最大 50 MB 文件。
- 影响：并发上传会放大内存占用，破坏“流式上传”的资源边界。
- 本任务处理：先用 monkeypatch 禁止 `read_bytes()` 得到 RED，再改为 `open("rb").read(12)`；上传正文按 1 MiB chunk 写入并增量计算 SHA-256。
- 预防/验证：任何 header/magic 检查都必须限制实际读取长度，不能在切片语法后隐藏整文件读取。

### 2026-07-22 · T1-005 · Alembic Head 测试不能永久写死上一任务

- 现象：新增 additive `20260722_0005` 后，T1-004 的 provider migration test 仍断言唯一 Head 为 `0004`，导致 full suite 唯一失败。
- 影响：每个正常后续 migration 都会制造伪回归，或诱使开发者跳过 broad suite。
- 本任务处理：改为断言唯一 Head 是当前 `0005`，且 `0005.down_revision == 0004`，同时保留 provider migration 位于单链中的证明。
- 预防/验证：历史任务测试应验证自己的 revision 存在和链路连续；当前 Head 只由最新 migration task 断言。

### 2026-07-22 · T1-005 · 文件删除与数据库状态不能伪一致

- 现象：初版 `shutil.rmtree(..., ignore_errors=True)` 会吞掉权限/锁定错误，service 随后仍把资产标成 `deleted`；非唯一冲突的 metadata commit 失败也不会清理已写 quarantine 文件。
- 影响：用户收到删除成功但敏感文件仍在磁盘，或磁盘出现没有 `file_assets` 记录的 orphan file。
- 本任务处理：缺失目录保持幂等，其他物理删除错误返回 `asset_delete_failed` 并保留 `deleting`；首次 checkpoint commit 在文件 I/O 前失败时无需文件清理，finalization metadata commit 异常则保留 `uploaded` checkpoint 与已写文件供恢复，只有 signature/stream 等失败才清理本次 asset UUID 目录与 checkpoint。
- 预防/验证：文件系统/数据库跨资源流程必须用 fault-injection 测试覆盖每个失败点，并区分“安全删除失败产物”和“保留 durable checkpoint 以追踪已写文件”，不能用 `ignore_errors` 伪造一致性。

### 2026-07-22 · T1-005 · 默认项目与上传需要数据库并发约束

- 现象：默认项目最初是 unlocked read-then-insert，且上传在写文件前读取 project、写库时不重验；并发请求可创建多个默认项目或向刚归档/删除的项目写入资产。
- 影响：幂等上传仍可能留下 orphan default project，project 状态与资产归属不一致。
- 本任务处理：新增 `active_default_owner_id` generated key 唯一约束；默认项目冲突 rollback 后回读 winner；资产 insert 前在同一事务中 `FOR UPDATE` 锁定并重验 project。
- 预防/验证：业务唯一性必须由数据库约束兜底；跨 I/O 的授权/状态快照在最终持久化事务内重新确认。

### 2026-07-22 · T1-005 · Service 文件上限不能替代 multipart 解析前上限

- 现象：初版只在 `UploadFile` 传入 service 后按 chunk 限制 50 MB，但 Starlette 已在此前把 multipart file spool 到临时存储；任意大或 chunked body 可先耗尽 `/tmp`/Host storage。
- 影响：业务测试显示 `file_too_large` 仍不能证明 request parser 具备 DoS 边界。
- 本任务处理：新增 upload 专用纯 ASGI gate；缺失/非法 `Content-Length`、任何 `Transfer-Encoding`、声明或实际 bytes 超过 `max_file_bytes + 64 KiB` 均在 service 调用前返回稳定 413。
- 预防/验证：上传限制必须分别验证 transport/parser gate 和业务 file gate；测试需证明拒绝时 receive/body 与 service 都未被消费。

### 2026-07-23 · T1-005 · 文件落盘前必须建立可恢复 checkpoint

- 现象：原流程先写 quarantine 文件、再插入 `file_assets`；metadata commit、signature cleanup 或 `CancelledError` 可在两个资源之间中断，留下无数据库定位的文件，cleanup exception 还可能遮蔽原始错误。
- 影响：orphan file 无法由状态机发现或安全重试，未认证 multipart 请求也可能在鉴权前反复占用 spool/disk I/O。
- 本任务处理：upload middleware 在 body receive/parser 前验证 Session；service 在文件 I/O 前提交 `uploaded` checkpoint，成功后更新 `quarantined`，cleanup 失败保留 `deleting`；Local Storage 显式捕获 cancellation，所有 reconciliation failure 只作为 exception note，不覆盖主因。
- 预防/验证：跨数据库与文件系统操作必须先有 durable owner/key/status；测试同时断言 pre-auth receive count 为 0、stream cancellation 无 partial、cleanup failure 可追踪、finalization failure 仍有 `uploaded` 记录。

### 2026-07-23 · T1-005 · parser 中途 disconnect 不能替代完整 body preflight

- 现象：streaming ASGI gate 在实际 bytes 超限时向下游返回 `http.disconnect`；若 parser 已处理首个 chunk 并把 UploadFile 滚盘，Starlette 异常路径可能留下未关闭的 spool handle。
- 影响：低报 `Content-Length` 的重复请求可积累临时文件与句柄，虽然单请求有大小上限，仍形成资源耗尽面。
- 本任务处理：认证和 completed replay 后，middleware 先把新请求写入自有 1 MiB threshold `SpooledTemporaryFile`，完整校验实际/声明长度和上限后才 replay 给 parser；所有出口 `finally close`。
- 预防/验证：body gate 测试必须使用至少两个 ASGI message，让第一段足以触发 parser roll、第二段才越界，并断言拒绝时 parser spool 根本未创建；不要只用单 message 超限测试代替。

### 2026-07-23 · T1-005 · incomplete checkpoint 不能伪装成幂等成功

- 现象：并发请求可在首请求已提交 `uploaded` checkpoint、但尚未通过 signature/stream gate 时命中相同 `Idempotency-Key`；初版 lookup 会直接把该 incomplete row 当作 201 replay。若首请求随后失败并清理 checkpoint，客户端已收到的“成功资产”会消失。
- 影响：幂等响应不稳定，调用方可能把尚未形成合法 quarantine 的资产当成可用输入；数据库 unique race fallback 也存在同一误判。
- 本任务处理：统一 replay policy 将 `uploaded`/`deleting` 映射为 `409 asset_upload_in_progress`，completed/后续已持久化状态才返回既有资产；普通 lookup 与 `IntegrityError` fallback 共用该 policy，且 middleware 在 body receive 前返回冲突。
- 预防/验证：并发测试必须让首请求停在 durable checkpoint 后，证明第二请求为零 body read 的 409；还要覆盖首请求 signature/stream 失败 cleanup 后，同 key later retry 能重新成功。

### 2026-07-23 · T2-001 · OOXML 不能只相信 ZIP magic 或扩展名

- 现象：DOCX/XLSX/XLSM 都以 `PK` 开头，伪装的 PPTX、加密 OLE package、DTD/entity、异常压缩率和 path traversal member 可绕过 T1-005 的 12-byte 初检。
- 影响：只按扩展名或 magic 放行会让 parser 面对错误容器、XML entity expansion 或 archive resource exhaustion。
- 本任务处理：在 ClamAV/解析前核对 OOXML Content Types，拒绝 OLE encrypted package、ZIP encryption、损坏 archive、非法 member、DTD/entity，并限制 member 数量、总解压量和单 member 压缩率。
- 预防/验证：Office parser 必须先通过 archive metadata gate；禁止 `extractall`，所有 XML 解析入口统一拒绝 DTD/entity，新增格式时先补伪装与压缩炸弹 RED。

### 2026-07-23 · T2-001 · 解析输出也需要 durable recovery 边界

- 现象：结构化 JSON 已原子写入独立 volume 后，数据库 finalization 仍可能失败；若随后的精确文件清理也失败，单纯把资产标成 rejected 会留下无定位输出。
- 影响：即使原始 quarantine 有 checkpoint，解析结果仍会形成不可追踪 orphan，且重复处理无法安全判断清理范围。
- 本任务处理：输出固定到 owner/asset UUID key 并限制 10 MB；进入 `parsing` 时在文件写入前先持久化 deterministic intended key，因此 output write 后 hard crash 仍可由 stale reconciliation 精确定位。finalization 与 cleanup 同时失败时，rejected 记录保留 `parsed_storage_key` 与 `parsed_output_cleanup_failed` 告警，原始错误仍为主因。
- 预防/验证：所有数据库与文件系统双写路径都要 fault-injection 覆盖“output write 后 hard crash”和“主写失败 + cleanup 失败”；只允许记录精确恢复 key，禁止递归清理 broad root 或用 ignore-errors 伪造成功。

### 2026-07-23 · T2-001 · 内容 byte quota 不能替代结构预算与可终止 timeout

- 现象：delimiter-only CSV 的字段内容为零字节，XLSX 可先装载大量未引用 shared strings，单个 Office XML member 也可在总 Archive 250 MB 限额内先触发巨大 DOM；普通 thread timeout 无法终止仍在运行的 parser。
- 影响：攻击输入可绕过输出容量门禁，占满 768 MB worker 或长期消耗 CPU；worker crash 后若没有 stale lease reconciliation，资产会永久停在 `scanning/parsing`。
- 本任务处理：所有 parser 共用总结构项预算，Office XML member 在读取和 DOM 前单独限额；parser 在可 terminate/kill 的子进程中运行，polling 先把过期处理租约 fail closed 到 `rejected`。
- 预防/验证：资源门禁测试必须包含“零内容但高结构”“未引用结构”“单 member 超限”和 timeout 后子进程不能继续写 marker；状态机需覆盖 crash/DB 恢复后的 stale lease 收口。

### 2026-07-23 · T2-001 · 图片 magic bytes 不是完整性证明

- 现象：只有 PNG/JPEG/WEBP 头部 magic 的截断文件，以及 CRC、deflate、RIFF size 或 frame header 损坏的文件，都会通过简单 signature gate。
- 影响：损坏图片可被误标为 `pending_ocr/ready`，把不可信 decoder 风险和不稳定失败推迟到 OCR 阶段。
- 本任务处理：在进入 `pending_ocr` 前以 bounded streaming 校验 PNG chunk/CRC/zlib/IHDR、JPEG marker/segment/frame/scan/EOI 和 WEBP RIFF/chunk/frame header，再通过 decoded-size gate 与 Pillow full decode；解码运行在受 timeout 的 parser 子进程中。
- 预防/验证：每种图片格式都保留真实最小结构样本和截断/损坏 adversarial fixture；新增格式不得只补 magic bytes。

### 2026-07-23 · T2-002 · PaddleOCR 模型不能留到隔离 runtime 下载

- 现象：PaddleOCR 3.x 的 pipeline 会把 official model 放入用户 HOME 下的 PaddleX cache；只在 Dockerfile 设置旧版 `PADDLE_OCR_BASE_DIR` 或只安装 Python package，non-root/read-only/internal-network runtime 仍可能找不到模型并尝试联网。
- 影响：静态 import/health 可通过，但第一张图片才因权限或网络失败；internal network 设计会把该缺陷稳定暴露为 OCR unavailable。
- 本任务处理：固定 PaddlePaddle `3.1.1`、PaddleOCR `3.7.0` 与 PP-OCRv5 mobile det/rec；build 阶段在 `/opt/paddle-home` 初始化下载，设置 HOME/PaddleX/PaddleOCR cache 并改为 non-root 可读，runtime 禁用 model source connectivity check 且只连 private network。
- 预防/验证：OCR image 必须同时验证 pinned dependency、build-time model warmup、non-root cache path、read-only root、无 external network 和真实首图 inference；仅 `import paddle` 不能作为 OCR readiness 证据。

### 2026-07-23 · T2-002 · Manifest 写入也需要 durable intended key

- 现象：解析 JSON 已有 deterministic recovery key，但若 Evidence Manifest 先落盘、再写 MySQL key，hard crash 会形成第二类不可追踪 orphan；反过来只写 DB 状态也可能把非法/半写 Manifest 当成 ready。
- 影响：Brief 可能读取不存在或无 Schema 保证的证据，cleanup 无法精确定位，重试还可能覆盖审计链。
- 本任务处理：解析完成后先把 deterministic Manifest key 与 `building` 提交到资产行，再进行严格 Schema 构建和原子 replace；最终条件更新一次性写 `valid`、摘要、engine/warning/blocker metadata 与 `ready`。cleanup 失败保留精确 key，stale lease 标为 `invalid`。
- 预防/验证：所有新文件型 checkpoint 都要覆盖“intended key commit”“atomic write”“final DB commit”“主失败 + cleanup 失败”“hard crash + stale reconciliation”五个点；没有有效 Manifest 的资产绝不能进入 Brief-ready 状态。

### 2026-07-23 · T2-002 · 用户删除必须覆盖全部派生输出

- 现象：原有资产删除路径只清理 quarantine 原文件；T2-001 的解析 JSON 与 T2-002 的 Evidence Manifest 位于独立 volume，即使数据库已标记 `deleted` 仍会留下敏感 orphan。
- 影响：用户看到删除成功，但结构化内容与可追溯事实仍保留在磁盘，违反删除语义并扩大隐私暴露窗口。
- 本任务处理：backend 仅为 owner-scoped 删除挂载 parsed/evidence volume；`scanning/parsing` 期间返回 `409 asset_processing_in_progress`，防止 worker 在删除后重新落盘。其余状态先持久化 `deleting`，再按数据库 exact keys 幂等清理原文件、解析结果和 Manifest，全部成功后才标记 `deleted`。任一派生清理失败返回 `asset_delete_failed` 并保留 checkpoint，重试可继续清理。
- 预防/验证：每增加一种资产派生存储，都必须把删除生命周期、active writer race 与 fault-injection 测试作为同一任务的验收项；禁止只软删数据库行或递归扫描 broad root。

### 2026-07-23 · T2-003 · 术语库更新不能破坏历史任务口径

- 现象：若 `term_libraries` 只保留一行并原地 PATCH，条目更新、删除或项目覆盖变化会让历史 Brief/任务引用到新的别名、单位和指标口径。
- 影响：同一历史输入在重放时产生不同标准化结果，证据链无法说明当时使用的规则，回滚还会改写已交付结果。
- 本任务处理：`library_id`/`item_id` 作为跨版本稳定 ID，每次库或条目 mutation 在事务内新增库 version 与完整条目 snapshot；删除只新增 tombstone，显式 version 仍可 owner-scoped 读取。
- 预防/验证：所有历史任务只引用 `library_id + version`；规则回滚选择旧 snapshot，不 UPDATE/DELETE 历史 version，也不重写 Manifest 或 Brief。

### 2026-07-23 · T2-003 · “万/亿”倍率不能和基础单位混为一体

- 现象：初版把未知后缀统一当成 `unit_unknown`，`1.2万` 虽被保留却丢失 10000 倍率；若随后用术语 unit 补成 CNY，会错误得到 `1.2 CNY`。
- 影响：销售金额和数量可产生数量级错误，且结果看似已标准化，不一定触发后续冲突。
- 本任务处理：把万/亿建模为确定 scale-only 规则，先得到 `12000 + unknown base unit`；只有显式币种符号或版本化术语 unit 才补齐基础单位，否则保持 unresolved。
- 预防/验证：标准化测试分别覆盖“倍率+显式单位”“倍率+术语 hint”“倍率但无基础单位”；Decimal canonical formatting 不能用盲目 `rstrip('0')`，避免把整数 `2500` 变成 `25`。

### 2026-07-23 · T2-004 · 历史 migration 不能 import 可演进 runtime catalog

- 现象：初版 `20260723_0009` 直接 import `ALPHA_SKILLS` 生成 seed；未来增加或修改 runtime Skill 时，历史 migration 的 seed/checksum 会漂移，甚至因固定两个 ID 与新数组长度不一致而无法从零升级。
- 影响：相同 revision 在不同代码版本生成不同数据库内容，破坏 migration 可重放性和 Skill 不可变承诺。
- 本任务处理：migration 内自包含冻结两个 `1.0.0` seed、Schema、workflow、能力与 checksum 算法；测试禁止 migration import `app.*`，并从空库核对 seed checksum 与 runtime v1 合同。
- 预防/验证：版本化 seed 必须冻结在 migration 或不可变 data artifact；禁止历史 migration import 会继续演进的 service/catalog/model 代码。

### 2026-07-23 · T2-004 · checksum 字段不能替代内容重算与 authoritative snapshot

- 现象：只比较数据库 `checksum` 字段无法发现 Schema/workflow 已被改写但 checksum 未同步；只校验 Brief 的 17 个字段也无法阻止模型改写用户 goal、输出类型或 must include/exclude。
- 影响：系统可能把漂移 Skill 或静默改变用户意图的 Brief 当作合法结果，checksum 和 evidence 引用形成虚假可信感。
- 本任务处理：runtime 逐字段核对 Skill row 与冻结定义；Brief validation 同时锁定 goal/audience/asset/term/Skill/model/include/exclude/output kind，file/calculation facts 与 Agnes inference 必须引用本次已知 evidence。
- 预防/验证：所有“版本 + checksum”合同都要测试“内容变、checksum 不变”；模型结构化输出除 Schema 外还必须验证 authoritative input snapshot 与跨字段语义。

### 2026-07-23 · T2-005 · immutable Revision 页面不能继续使用旧资源 ID

- 现象：PATCH 成功返回新的 `brief_id`，初版页面却继续用路由中的旧 Revision ID执行 Preflight/confirm。
- 影响：保存编辑后必然命中 `brief_revision_stale`，用户无法完成 Week 2 确认流程；只测 PATCH request 会漏掉该跨请求状态错误。
- 本任务处理：页面把已加载 Brief 的 ID 作为后续操作权威值，仅首次加载回退到路由参数；组件测试断言保存后最后一次 Preflight 使用新 Revision ID。
- 预防/验证：所有 append-only resource UI 都要覆盖 create-next-version 后的下一次 read/action target，不能只断言 mutation payload 或页面 revision 文案。

### 2026-07-23 · T2-005 · 需要返回 409 的状态变化不能在事务内直接抛出

- 现象：确认时发现新 blocker 或预计积分变化，若在 `session.begin()` 内写状态后立即抛业务异常，context manager 会回滚最新 Preflight snapshot。
- 影响：客户端收到 409，但后续 GET 看不到导致冲突的最新 blocker/费用，形成不可解释的重试循环；费用快照若遗漏 model multiplier 也无法审计计算依据。
- 本任务处理：事务内保存最新状态、model multiplier、模板、子输出费用与总费用，把 409 延迟到事务成功退出后抛出；确认成功后始终读取既有锁定 snapshot，不重算。
- 预防/验证：所有“持久化诊断状态后返回失败”的路径都要 fault-test commit/rollback 边界；费用锁必须同时保存公式输入和各子输出结果，不能只保存总数。

### 2026-07-23 · T3-001 · 任务、预留与 Outbox 必须只有一个事务事实

- 现象：如果先创建任务、再单独预留积分或发布 Redis 消息，任一步骤失败都会留下无余额保障的任务、孤立扣费或数据库不可恢复的 queue 状态。
- 影响：重放相同请求可能重复扣费，Redis 丢失后也无法判断任务是否真实提交。
- 本任务处理：同一事务锁定 owner/latest confirmed Brief、余额和运行配置，写 task、不可变 inputs、reserve ledger 与首个 Outbox；数据库唯一键处理 idempotency race，Outbox failure fault test 证明整体回滚。
- 预防/验证：queue 只传递工作提示，MySQL task/step/ledger/outbox 才是事实；所有跨事务重放都必须由持久唯一键和 checkpoint 去重。

### 2026-07-23 · T3-001 · stale checkpoint 必须区分安全重试和外部结果未知

- 现象：统一把 stale running step 重置为 pending，会把已经发到 Provider 但尚未持久化响应的调用当成安全重试；反过来完全不恢复又会永久卡住尚未进入外部调用的步骤。
- 影响：前者可能重复 Provider 副作用和扣费，后者导致 Redis/进程故障后任务无法恢复。
- 本任务处理：safe stale checkpoint 先复位为 pending 再创建恢复 Outbox；已经进入 Provider 的 stale checkpoint 收口为 `provider_uncertain` 并保留 reserve。
- 预防/验证：每个外部边界前后必须持久化可判定 checkpoint；没有确定证据时选择 uncertain，不把未知执行伪装成确定失败。

### 2026-07-23 · T3-001 · 共享 ProviderCall 与 retry key 必须按业务 scope 限宽

- 现象：沿用 `(brief_group_id, attempt)` 会让不同 generation task 的相同步骤 attempt 发生唯一键冲突；把 128 字符客户端 Idempotency-Key 原样拼接 retry 后缀还会超过 ledger 列宽。
- 影响：正常并行任务或允许重试的失败任务可能被数据库约束意外拒绝，甚至让账务重试无法落盘。
- 本任务处理：Brief call 保留原唯一键，task call 使用可空 task/step 外键与 `(task_step_id, attempt)`；retry billing key 改为固定 task UUID 和 retry 序号。
- 预防/验证：共享审计表的唯一键必须明确互斥 scope；派生 idempotency key 必须从固定长度内部 ID 生成，并覆盖最大合法客户端输入。

### 2026-07-23 · T3-002 · 跨语言 Plan hash 必须固定数值 canonicalization

- 现象：Python `json.dumps` 与 JavaScript `JSON.stringify` 对整数/浮点数表示不同；几何值 `1` 在一端可能成为 `1.0`，导致同一合法 Plan 的 hash 不一致。
- 影响：真实 Renderer 已生成文件，但 Python 会把 response 当作篡改而拒绝；无限精度或 scientific notation 还会让不同 runtime 的重放语义漂移。
- 本任务处理：双端只接受有限、绝对值受限且最多 6 位小数的 Plan 数值，并使用 key 排序、UTF-8 字符和固定小数裁剪的共享 canonical JSON 算法；真实跨进程 smoke 验证 hash 相同。
- 预防/验证：所有跨语言幂等/hash contract 必须用共享 fixture 和真实进程边界验证，不能只在各自语言内 self-hash。

### 2026-07-23 · T3-002 · Renderer replay 不能只信 sidecar

- 现象：只要 `result.json` 和输出路径存在就返回旧结果，会把部分写入、损坏文件或并发 sidecar race 当作成功；Python 虽能发现 hash 不符，同 request 重试仍会永远取到坏文件。
- 影响：task checkpoint 无法自恢复，重复 delivery 可能持续失败或产生两个互相覆盖的 derived output。
- 本任务处理：单进程内按 `work root + request ID` 串行执行；replay 同时核对 Plan、版本、页数、模板、文件 hash/size，缺失/损坏的 derived PPTX 重新生成并刷新 sidecar，不同 Plan 冲突 fail closed。
- 预防/验证：所有文件型 external worker replay 都要覆盖并发同请求、sidecar 存在但文件缺失/损坏、不同输入复用 ID，以及最终持久化失败后的恢复。

### 2026-07-23 · T3-003 · 质量报告重放必须复验全部 artifact

- 现象：只复验 `report.json` 和 validated PPTX，会漏掉已缺失或被篡改的 PDF/PNG；数据库仍可能把不可用预览标成完成。
- 影响：用户看到的预览与实际下载文件失去关联，历史质量证据不再可信。
- 本任务处理：完成、恢复与重放均按报告逐项复验 PDF/PNG hash/size；report、preview 或 validated artifact 任一漂移都 fail closed。
- 预防/验证：文件型质量 checkpoint 必须把“报告合同”和“实际 artifact 完整性”作为同一完成条件，并覆盖落库前恢复、落库后重放和篡改回归。

### 2026-07-23 · T3-003 · 固定 request work dir 需要 durable completion marker

- 现象：LibreOffice 已成功转换但调用方在落库前崩溃时，同 request 重试会遇到已存在目录；盲删重跑又会丢失已完成结果并引入并发覆盖。
- 影响：可安全重放的确定性 QA 被误判为永久失败，或重复执行昂贵转换。
- 本任务处理：sidecar 原子写入 strict `result.json`，重试先复验 user/asset/source variant/hash/size 的完整 request fingerprint、固定 key 以及 PDF/PNG 实际 hash/size；不一致时 fail closed。
- 预防/验证：external file worker 的 completion marker 必须最后写、原子写且不可单独信任，manifest 与实际 artifact 始终双向校验。

### 2026-07-23 · T3-004 · 宿主代码不能假设 backend 容器拥有 LibreOffice

- 现象：初版 Excel validator 直接在 Backend 进程执行 `soffice`；但 Compose 只在独立
  `libreoffice` sidecar 安装 Office runtime，且既有镜像只有 Impress、没有 Calc。
- 影响：Python/fake runner tests 可通过，但真实 Docker backend 必然
  `libreoffice_unavailable`，即使 sidecar 健康也无法重算 XLSX。
- 本任务处理：在既有 private sidecar 增加 strict spreadsheet recalculation HTTP
  contract，镜像补装 `libreoffice-calc`；sidecar 从固定 owner/asset key 读取原件并写
  shared-work，Backend client 再复验固定 key/hash/trace/report。
- 预防/验证：凡外部 binary 只存在专用容器，host service 必须通过最小 internal contract
  调用；focused test 同时断言镜像 package、Compose command、sidecar route 和 Backend
  artifact verification，不能用本机 PATH 或进程内 fake 代替容器边界。

### 2026-07-23 · T3-004 · 公式 cache 与 validation artifact 都不能只看一层

- 现象：openpyxl 以 formula 视图读取不到 cache，以 `data_only=True` 又看不到 formula；
  直接用 openpyxl 重存测试副本还会清空全部公式 cache。另一方面，只读取已有 validation
  report 会漏掉 copy/report 篡改或半完成目录。
- 影响：测试可能把库行为误报成 12 个公式差异；任务重放也可能把损坏副本当成已完成，
  破坏原件不可变和重算证据。
- 本任务处理：formula/cache 使用两个只读 workbook 视图按 Sheet/cell 合并；测试只改
  validation ZIP 的单个 formula XML，保留其他 cache。完成 replay 重新复验原件、
  validation copy、report、trace 和重算 diff，不单独信任 marker。
- 预防/验证：Office formula 合同必须分别验证 formula、cache 与实际文件 hash；测试工具
  对 OOXML 的副作用要先确认，文件型 completion marker 始终与 artifact 双向复核。

### 2026-07-23 · T3-005 · 质量报告通过不等于输出可以下载

- 现象：只信 step checkpoint 中的 `download_allowed=true`，会在资产被跨任务替换、
  category/version 漂移或 validated file 被篡改后继续返回下载入口；质量尚 pending 的
  generation output 又不能被同一完整性函数误判为永久损坏。
- 影响：前者越过 owner/task/quality 边界暴露错误文件，后者让正常的 renderer→QA 两阶段
  流程在质量执行前失败。
- 本任务处理：outputs API 先复验 owner、generated task、file category、asset version；
  pending 只允许返回不可下载状态，quality 完成后再要求 report/validated key/hash/size
  全部一致。实际下载仍复用同一 artifact integrity gate。
- 预防/验证：文件输出的“已生成”“已质检”“可下载”必须是三个显式阶段；任何可下载
  snapshot 都要从数据库事实和实际 artifact 重新推导，不能只信布尔 checkpoint。

### 2026-07-23 · T3-005 · 组合结算必须携带每个子输出的完整事实

- 现象：执行结果只有 success/failure 时，worker 无法可靠保存 output asset、版本、质量和
  下载边界；若一个成功结果遗漏 metadata 仍写入默认 false，还会覆盖质量服务已完成的
  checkpoint。
- 影响：任务状态可能正确但 outputs API 无法解释哪个版本成功，或重放时错误释放/重复
  finalize 积分。
- 本任务处理：`StepExecutionResult` 对成功/失败与 output metadata 建立互斥校验；worker
  只写显式提供的字段，PPT/Excel quality outcome 都返回完整 asset/version/quality/
  download snapshot。结算只读取持久 step 状态和 estimated credits，以 ledger 唯一键
  幂等 finalize/release。
- 预防/验证：组合任务的 executor contract 必须一次返回可审计的子输出事实；聚合层不能
  根据默认值猜测质量或下载状态，并要覆盖一成一败、重复 delivery 和 checkpoint replay。

### 2026-07-23 · T3-005 · LibreOffice 原始报告也是质量证据

- 现象：只把 validation report 内容折叠进最终 quality report，而不保存 sidecar 原始
  report，会让 `report_sha256` 指向临时文件；固定 `.tmp` 名称在 crash 后还会阻断恢复，
  且把质量报告 1 MiB 上限误用于 sidecar 允许的 10 MiB report 会拒绝合法结果。
- 影响：重放无法证明当时的重算证据，残留 temp 造成永久失败，边界上合法 artifact 在
  本地测试未覆盖时被生产误拒。
- 本任务处理：使用 UUID temp + hard-link 的不可覆盖写入，分别持久化
  `libreoffice-report.json`、validation copy 与最终 report；重放逐项 hash/size，质量报告
  与 sidecar report 使用各自 1 MiB/10 MiB 上限。
- 预防/验证：派生报告的摘要必须指向 durable artifact；每种 artifact 独立声明容量上限，
  并测试 crash residue、并发完成、篡改和合法上界，而不是复用一个模糊常量。

### 2026-07-23 · T4-001 · 前端重载不能把内存 Access Token 当作持久 Session

- 现象：若只在登录成功时设置内存 Access Token，页面重载会丢失身份；若直接把 Access
  Token 持久化，又扩大 token 被脚本读取的暴露面。注册后部分 bootstrap 失败还可能留下
  半认证状态。
- 影响：用户刷新 Brief 或 Generation 页面会被误送回登录，或客户端保留不完整身份；
  强制改密和 role guard 也可能在启动瞬间被绕过。
- 本任务处理：应用启动只从 `sessionStorage` 取 Refresh Token，先调用 rotation，再用新
  Access Token 请求 `/auth/me`；Access Token 始终只在内存，任一步失败都 fail closed
  清空状态。logout 先请求服务端 revoke，再清理客户端状态。
- 预防/验证：所有 Session UI 必须测试 reload bootstrap、refresh rotation、部分失败清理、
  强制改密和 server logout；不能用 localStorage 持久化 Access Token 作为简化方案。

### 2026-07-23 · T4-001 · 管理后台功能壳不能伪造尚未交付的管理 API

- 现象：UI V1 已包含用户、任务、资产、积分和 audit 页面，但对应敏感 HTTP 闭环属于
  T4-002；用静态成功数据或前端假操作补齐截图会让页面看似可用。
- 影响：验收会把 visual shell 误认为权限、重新认证、审计和资产操作已经实现，后续接入
  时还可能保留不安全入口。
- 本任务处理：只接入已经交付的 invite、Provider、Credential、model 等 API；其余页面
  显式显示 disabled/empty boundary，Credential 始终掩码且没有 Reveal。环境标识从
  `VITE_APP_ENV_LABEL` 读取，未配置时显示本地环境，不硬编码生产状态。
- 预防/验证：UI 计划早于 API 时，逐页标注 authoritative endpoint 和 dependency task；
  没有后端 contract 的操作只能是明确 disabled shell，不能 mock 成产品成功路径。

### 2026-07-24 · T4-002 · 失败审计不能跟随失败事务一起回滚

- 现象：在用户不存在或积分不足的事务中先插入 `audit_logs` 再抛异常，transaction context
  会把业务修改和失败 audit 一起回滚；HTTP 仍返回失败，但调查链为空。
- 影响：敏感失败尝试不可追溯，管理员最高权限边界只在成功路径成立。
- 本任务处理：成功 audit 与用户/Session/ledger 在同一事务提交；业务失败先安全退出失败
  事务，再用独立只追加事务写 `failed` audit，写入失败时 fail closed。资产文件失败沿用
  exact-key 操作后的独立审计，并且 context 只保留白名单状态。
- 预防/验证：任何“失败也审计”的 contract 必须测试异常返回后重新开 Session 查询记录，
  不能只在抛异常前断言 `session.add()` 被调用。

### 2026-07-24 · T4-002 · 重新认证原因不能进入 URL 或被 schema 提前吞掉

- 现象：GET preview/download 无法安全携带当前密码和原因；若 Pydantic 在 service 前拒绝
  空原因，service 也无法记录 `reason_required` 失败审计。
- 影响：密码/原因可能进入 URL、代理日志或浏览历史，原因缺失尝试又绕过 audit。
- 本任务处理：管理员 preview/download 改为 POST JSON；reason schema 只做长度上限，
  非空与 trim 在已识别管理员 actor 的 service 内校验并记录失败。所有 audit IP/User-Agent
  统一压缩为网络/首行摘要。
- 预防/验证：敏感 re-auth 字段只放 body；需要审计的业务校验不能在建立 actor/trace 前被
  transport schema 截断。

### 2026-07-26 · T4-003 · 单一样本不能复制成黄金数据多样性

- 现象：原计划要求 10 组脱敏材料，但用户最终只能提供一份 XLSX 来源和一份 PPTX 参考
  输出；把 Sheet、月份或重复运行拆成 10 组会让数量满足而证据失真。
- 影响：重复运行可以证明确定性，却不能证明不同客户、模板、行业和异常输入的覆盖；若
  把 `1/10 pilot` 写成完整 corpus 通过，会直接污染 Alpha release 判断。
- 本任务处理：用户明确批准缩减为一个 `sales-pilot-v1` case；任务卡、总计划、进度和
  Manifest 固定记录 `1/10 pilot`，仍运行 20 次 PPT/20 次 Excel，但将覆盖局限与外部
  runtime 证据分开。
- 预防/验证：黄金样本数量必须按独立来源 case 计数；重复运行、切片和副本只能作为同一
  case 的 determinism evidence，不得提升 corpus count。

### 2026-07-26 · T4-003 · 导入后改 cell 不等于 package 已脱敏

- 现象：对导入 workbook 改写可见 cells 后，OOXML 仍可能保留未引用 shared strings、
  drawings 或旧 package payload；按 raw XML 连续文本扫描又会把相邻业务数字误报为电话。
- 影响：只看 worksheet UI 会漏掉 private token，直接 raw regex 又会制造假阳性，二者都
  不能作为提交安全证据。
- 本任务处理：用 artifact-tool 新建 workbook，只复制脱敏 values/formulas/必要格式，
  shared formulas 按 OOXML 结构展开；PII 扫描按 cell/XML text-node 语义执行，并用 ignored
  private replacement map 做一次不输出原值的精确残留检查。
- 预防/验证：真实 Office 脱敏副本必须 fresh regenerate，再组合 exact-token 与 semantic
  PII/package scan；禁止只依赖 visible cells 或整段 XML regex。

### 2026-07-26 · T4-003 · OOXML 自动门禁不能替代实际 Office 视觉与计算

- 现象：结构检查和 cached values 均通过时，Microsoft Excel 仍显示 `RANK.EQ` 为 `#NAME?`
  且固定 print area 裁掉两个 chart categories；PowerPoint closing layout 也出现正文重叠。
- 影响：自动报告会把实际不可用/不可读文件错误标成 `passed`。
- 本任务处理：实际用 PowerPoint/Excel 16.0 打开并导出；以 RED contract 改用兼容 `RANK`、
  显式 axis font 与 anchor-aware print area，并调整 PPT closing/source plan 后重复视觉验证。
- 预防/验证：Office artifact 必须按 `自动结构/缓存 -> 实际应用重新计算 -> 导出视觉检查`
  三层收口；实际应用发现的缺陷回写 renderer tests，不能只记为人工备注。

### 2026-07-26 · T4-004 前置 · 基础文本 200 不等于 Structured Output Contract 通过

- 现象：真实 Agnes Key、endpoint 与 text model 的最小请求在不带 `response_format`
  时返回 HTTP `200`，但项目 live Contract 增加
  `response_format={"type":"json_object"}` 后返回 `upstream_error/400`；上游明确说明
  当前 grammar backend 不支持 grammar-based JSON generation。
- 影响：把“鉴权/基础文本可用”记录成“Structured Brief 真实兼容通过”，会掩盖生产请求
  必然失败，并让 Mock Contract 的能力声明污染 Alpha release gate。
- 本次处理：只用一次性加密 Credential 和临时数据库执行真实 Contract；分别记录
  prompt-only 基础访问与 strict structured-output 结果，不修改业务 adapter，也不把
  `2 failed, 2 passed` 降级为通过。
- 预防/验证：真实 Provider gate 必须逐项验证 endpoint/auth、请求字段、structured
  output、响应 envelope 与 usage；任何 fallback 都必须先有 RED contract、严格 schema
  validation、单次 repair 和不重复计费边界，不能仅删除失败字段后宣称兼容。

### 2026-07-27 · T4-004 · Provider 请求能力必须显式声明

- 现象：Mock Agnes 接受 `response_format`，真实 Agnes grammar backend 却返回 HTTP 400；
  adapter 无条件发送该字段会让基础可用的模型在 Structured Brief 路径必然失败。
- 影响：Mock 合同会制造虚假的生产兼容性；反过来直接删除字段又可能在未来支持 native
  structured output 时丢失能力，并被误解为降低应用层 Schema。
- 本任务处理：增加默认 `false` 的严格布尔 capability `native_response_format`；只有显式
  支持才发送 native 字段，应用层 strict Schema、一次 repair、Evidence 引用和错误分类不变。
- 预防/验证：Provider-specific optional field 必须由显式 capability 驱动，并同时覆盖
  unsupported、supported、错误类型与真实 opt-in Contract，不能从单次响应静默学习全局配置。

### 2026-07-27 · T4-004 · Offline migration SQL 不能替代 utf8mb4 空库升级

- 现象：历史 `file_assets` storage locator 在 SQLite/offline MySQL DDL 下通过，但真实
  utf8mb4 MySQL 从零升级时，32+768 字符的联合唯一键超过 InnoDB 3072-byte 上限。
- 影响：所有后续 migration 和 runtime test 都无法启动；若只在已有库增补新 migration，
  新部署仍会先死在旧 revision。
- 本任务处理：storage locator 本来就只允许服务端 ASCII key，因此模型与 `0005` 同步使用
  `ascii_bin`；同时发现 `0011` nullable ALTER 会丢失列 COMMENT，upgrade/downgrade 均显式
  传入 `existing_comment`。第二个隔离空库从零升级至唯一 head，`alembic check` 无 drift；
  旧失败库不删除。
- 预防/验证：长索引必须按真实 charset 的字节上限设计；Alpha 封版前至少在 utf8mb4
  MySQL 空库跑完整 migration chain，不能只看 SQLite 或 dialect compile。

### 2026-07-27 · T4-005 · 冻结表数必须由空库实测而不是文档推断

- 现象：历史 migration chain 到 `0013` 可正常升级且无 drift，但实际只有 19 张业务表；
  冻结的 21 表契约中的 `templates` 与 `system_settings` 从未进入 migration。
- 影响：只检查唯一 Head 或 `alembic check` 会把完整性缺口误判为封版通过。
- 本任务处理：先以 exact table-set RED contract 固定 21 张业务表，再用 additive `0014`
  补齐两表；真实 utf8mb4 空库实测 21 表、40 外键、22 unique constraints。
- 预防/验证：封版 migration Gate 必须同时核对 revision、业务表 exact set、关键约束和
  drift；schema 文档中的固定数量必须成为可执行 contract。

### 2026-07-27 · T4-005 · 镜像 health 不能替代首次真实推理

- 现象：可解析的 Paddle `3.3.1` image 能通过 healthcheck，但首次 OCR inference 因
  oneDNN/PIR runtime incompatibility 返回 503；原固定 `3.1.1` image tag 又不可解析。
- 影响：冷启动显示 healthy，真实图片任务仍会在首次请求失败。
- 本任务处理：使用可解析 `3.3.1` base，固定安装经项目验证的 PaddlePaddle `3.1.1`；
  最终不仅检查 health，还发送带 SHA-256 integrity header 的合成 PNG 并核对识别文本。
- 预防/验证：ML sidecar Gate 必须覆盖 model preload、首个真实 inference、response
  schema 和输入 integrity；不能把 HTTP health 当作引擎兼容证据。

### 2026-07-27 · T4-005 · 官方容器 init 可能与 non-root/read-only 合同冲突

- 现象：ClamAV 官方 `/init` 会对 `/run`、lock 与配置执行 root-only chown/sed；强制
  non-root/read-only 后无法启动。FreshClam 又受到上游 CDN 403/cooldown。
- 影响：为了启动而放宽 root/rootfs 会破坏安全基线；忽略 signature 更新则会夸大病毒
  检测能力。
- 本任务处理：固定可解析 `1.4.5`，以 non-root direct `clamd`、signature volume 与
  最小 tmpfs 运行；EICAR INSTREAM 通过。在线更新失败作为明确 release boundary 保留。
- 预防/验证：安全 sidecar 应分别验证 daemon privilege、signature provenance/update
  和真实检测；固定内置 signature 只能支撑本地 Alpha，不能冒充持续更新。

### 2026-07-27 · T4-005 · read-only runtime 的测试与 build 也需要写路径合同

- 现象：Vite/Vitest 默认 config bundler 写 `node_modules/.vite-temp`，TypeScript build
  写 `/app/dist`；在 read-only rootfs 中任务卡命令分别失败。Renderer production stage
  也不含 Vitest，精确命令最初退出 127。
- 影响：应用 runtime healthy 不代表 release verification 可重复；为测试临时关闭
  read-only 又会隐藏真实权限问题。
- 本任务处理：Vite/Vitest 使用 runner config loader；Renderer build 输出写 `/tmp`
  tmpfs。Compose 使用含测试工具的 build target，默认 production stage 仍只含 production
  dependencies并单独在 non-root/read-only 容器验证。
- 预防/验证：容器化 release command 必须在与服务一致的 user/rootfs/network 边界下跑；
  build cache、test config 与产物目录都需显式可写位置。

## 规则变更记录

| 日期 | 任务 | 变更 |
|---|---|---|
| 2026-07-22 | T1-001 | 初始化项目级会话读取、单任务、进度记录、验证、提交推送与敏感信息规则 |
| 2026-07-22 | T1-001 | 固化 Vue/FastAPI 目录边界、UTF-8、最小变更和 UI 先计划后实现规则 |
| 2026-07-23 | 全局安全规则 | 环境示例文件同样禁止进入 Git；补齐 `.env`、`*.env.*` 与 `.ene` 误拼变体的 ignore 和提交检查 |
| 2026-07-26 | T4-003 | 用户批准将 10 组黄金材料前置缩减为唯一 `1/10 pilot`，保留覆盖限制和严格脱敏/证据边界 |
| 2026-07-26 | 项目 Secret 授权 | 用户长期授权按最小必要原则读取仓库根 `.env` 用于项目 runtime、真实 Agnes Contract 与配置验证；任何值仍禁止回显、复制、记录或进入 Git，其他环境文件继续禁读 |
