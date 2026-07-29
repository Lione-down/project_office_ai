# Office AI Alpha 环境基线

本文只记录变量名称、用途和安全录入方式。禁止把真实值写入本文件、`.env.example`、测试 fixture、日志或聊天。

## 支持环境

- Host：Windows 开发机
- Runtime：Docker Compose；Node.js 和 Python 可用于本地 focused tests
- Data：MySQL 8.0、Redis
- Office 工具：LibreOffice Headless（Impress + Calc）；Week 4 人工验收需要 Microsoft Office 与 WPS
- 外部 Provider：Agnes API，通过管理员创建的加密 Credential 使用

## 环境变量

| 变量 | 用途 | 敏感 | 必需时点 | 安全录入方式 |
|---|---|---:|---|---|
| `OFFICE_AI_ENV` | `local/test` 运行环境 | 否 | T1-002 | Compose/CI 普通变量 |
| `OFFICE_AI_LOG_LEVEL` | 日志级别 | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_FRONTEND_PORT` | Frontend Host port，默认 `8888`；容器内仍为 `5173` | 否 | Runtime | Compose 普通变量 |
| `OFFICE_AI_BACKEND_PORT` | Backend Host port，默认 `9999`；容器内仍为 `8000` | 否 | Runtime | Compose 普通变量 |
| `OFFICE_AI_FRONTEND_ORIGIN` | 唯一允许的前端 Origin，默认 `http://localhost:8888` | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_API_BASE_URL` | Compose 提供的前端 API 基址，默认 `http://localhost:9999/api/v1`，映射为容器内 `VITE_API_BASE_URL` | 否 | T1-002 | Build/runtime 普通变量 |
| `OFFICE_AI_MYSQL_DATABASE` | MySQL database 名 | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_MYSQL_USER` | MySQL app user | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_MYSQL_PASSWORD` | MySQL app password | 是 | T1-002 | 本地未跟踪环境或 Secret store |
| `OFFICE_AI_MYSQL_ROOT_PASSWORD` | MySQL root password | 是 | T1-002 | 本地未跟踪环境或 Secret store |
| `OFFICE_AI_DATABASE_HOST` | MySQL internal hostname，Compose 默认 `mysql` | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_DATABASE_PORT` | MySQL internal port，默认 `3306` | 否 | T1-002 | Compose 普通变量 |
| `OFFICE_AI_DATABASE_URL` | SQLAlchemy 连接串 | 是 | T1-002 | 运行时组合或本地 Secret，不打印 |
| `OFFICE_AI_REDIS_URL` | Redis internal URL | 视部署 | T1-002 | Compose internal network；生产用 Secret |
| `OFFICE_AI_MASTER_KEY` | Provider credential Fernet 应用层加密主密钥 | 是 | T1-004 | URL-safe Base64 编码的 32-byte Key；仅 OS secret/CI secret，禁止落库和提交 |
| `OFFICE_AI_SESSION_SECRET` | Session 签名/派生 Secret | 是 | T1-003 | OS secret/CI secret；定期轮换 |
| `OFFICE_AI_ACCESS_TOKEN_TTL_SECONDS` | Access Token TTL | 否 | T1-003 | Compose 普通变量 |
| `OFFICE_AI_REFRESH_TOKEN_TTL_SECONDS` | Refresh Token TTL | 否 | T1-003 | Compose 普通变量 |
| `OFFICE_AI_BOOTSTRAP_ADMIN_PHONE` | 初始管理员 `+86` 手机号 | 是 | T1-003 Bootstrap | 仅本地未跟踪环境或 Secret store；无默认值 |
| `OFFICE_AI_BOOTSTRAP_ADMIN_PASSWORD` | 初始管理员密码 | 是 | T1-003 Bootstrap | 仅本地未跟踪环境或 Secret store；无默认值 |
| `OFFICE_AI_FILES_ROOT` | 受控文件根目录 | 否 | T1-005 | Compose path；默认 `/app/files` |
| `OFFICE_AI_MAX_FILE_BYTES` | 单文件上限，默认 50 MB | 否 | T1-005 | `system_settings`/普通变量 |
| `OFFICE_AI_MAX_IMAGE_BYTES` | 图片上限，默认 20 MB | 否 | T1-005 | `system_settings`/普通变量 |
| `OFFICE_AI_MAX_IMAGE_DECODED_BYTES` | 图片 full decode 内存估算上限，默认 128 MB | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_TASK_FILES` | 单处理批次文件数上限，默认 20 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_TASK_BYTES` | 单任务总上限，默认 200 MB | 否 | T1-005 | `system_settings`/普通变量 |
| `OFFICE_AI_PARSED_ROOT` | 结构化解析结果根目录，默认 `/app/parsed` | 否 | T2-001 | 独立受控 volume/path |
| `OFFICE_AI_MAX_PARSED_OUTPUT_BYTES` | 单资产结构化解析输出上限，默认 10 MB | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_PDF_PAGES` | PDF 页数上限，默认 200 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_EXCEL_SHEETS` | Excel Sheet 上限，Post-Alpha 默认 100 | 否 | T2-001 / Post-Alpha | Compose 普通变量 |
| `OFFICE_AI_MAX_EXCEL_NON_EMPTY_CELLS` | Excel 非空单元格上限，默认 300000 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_ARCHIVE_ENTRIES` | Office Archive member 上限，默认 10000 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_ARCHIVE_UNCOMPRESSED_BYTES` | Office Archive 解压后总量上限，默认 250 MB | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_ARCHIVE_COMPRESSION_RATIO` | 单 member 最大压缩率，默认 100 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_OFFICE_XML_MEMBER_BYTES` | 单个 Office XML member 上限，默认 16 MB | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_MAX_PARSER_STRUCTURAL_ITEMS` | 单资产 parser 总结构项预算，默认 1500000 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_PARSER_TIMEOUT_SECONDS` | 隔离 parser timeout，默认 30 秒 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_PROCESSING_LEASE_SECONDS` | scanning/parsing/evidence stale lease，默认且最少 300 秒，并覆盖 scan/parser/OCR timeout 与 I/O 余量 | 否 | T2-001/T2-002 | Compose 普通变量 |
| `OFFICE_AI_CLAMAV_HOST` | ClamAV internal hostname | 否 | T2-001 | Compose DNS 名 |
| `OFFICE_AI_CLAMAV_PORT` | ClamAV port | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_CLAMAV_TIMEOUT_SECONDS` | ClamAV 单文件 timeout，默认 30 秒 | 否 | T2-001 | Compose 普通变量 |
| `OFFICE_AI_PADDLEOCR_URL` | OCR internal service URL | 否 | T2-002 | Compose internal URL |
| `OFFICE_AI_OCR_TIMEOUT_SECONDS` | 单图片 internal OCR timeout，默认 60 秒 | 否 | T2-002 | Compose 普通变量 |
| `OFFICE_AI_MAX_OCR_RESPONSE_BYTES` | 单图片 OCR JSON 响应上限，默认 10 MB | 否 | T2-002 | Compose 普通变量 |
| `OFFICE_AI_MAX_OCR_ITEMS` | 单图片 OCR 识别项上限，默认 5000 | 否 | T2-002 | Compose 普通变量 |
| `OFFICE_AI_EVIDENCE_ROOT` | Evidence Manifest 根目录，默认 `/app/evidence` | 否 | T2-002 | 独立受控 volume/path |
| `OFFICE_AI_MAX_EVIDENCE_MANIFEST_BYTES` | 单资产 Manifest 上限，默认 10 MB | 否 | T2-002 | Compose 普通变量 |
| `OFFICE_AI_MAX_EVIDENCE_ITEMS` | 单资产过滤前 Evidence source item 上限，Post-Alpha 黄金校准默认 11563，在对象构建前执行 | 否 | T2-002 / Post-Alpha | Compose 普通变量 |
| `OFFICE_AI_OCR_RETRY_LIMIT` | 暂时性 OCR 失败最大总尝试次数，默认 3 | 否 | T2-002 | Compose 普通变量 |
| `OFFICE_AI_OCR_RETRY_BACKOFF_SECONDS` | OCR exponential backoff 基数，默认 30 秒 | 否 | T2-002 | Compose 普通变量 |
| `OFFICE_AI_LIBREOFFICE_URL` | LibreOffice quality sidecar internal URL | 否 | T3-003 | Compose internal URL |
| `OFFICE_AI_LIBREOFFICE_TIMEOUT_SECONDS` | LibreOffice 打开、转 PDF timeout，默认 120 秒 | 否 | T3-003 | Compose 普通变量，范围 `(0, 600]` |
| `OFFICE_AI_PPT_RENDERER_URL` | PPT renderer internal URL | 否 | T3-002 | Compose internal URL |
| `OFFICE_AI_RENDERED_ROOT` | Backend 只读访问 Renderer work volume 的根目录，默认 `/app/rendered` | 否 | T3-002 | Compose path；不得映射为静态目录 |
| `OFFICE_AI_PPT_RENDERER_TIMEOUT_SECONDS` | PPT Renderer HTTP timeout，默认 120 秒 | 否 | T3-002 | Compose 普通变量 |
| `OFFICE_AI_MAX_PRESENTATION_REQUEST_BYTES` | PresentationPlan/Renderer request 上限，默认 32 MB；容纳单张 20 MB 图片的 bounded base64 | 否 | P5-006 | Compose 普通变量 |
| `OFFICE_AI_PROVIDER_TIMEOUT_SECONDS` | Provider 请求 timeout，默认 120 | 否 | T2-004 | Admin config/普通变量 |
| `OFFICE_AI_RUN_REAL_AGNES_CONTRACT` | 显式启用真实 Agnes Contract Test；仅精确值 `1` 启用 | 否 | T2-004 手工联调 | 临时进程环境；默认不设置 |
| `OFFICE_AI_AGNES_CONTRACT_CREDENTIAL_ID` | 真实 Contract Test 选择已加密 Agnes Credential 的 UUID，不是 API Key | 否 | T2-004 手工联调 | 临时进程环境；只与显式 opt-in 同时使用 |
| `OFFICE_AI_RUN_T4_FAILURE_DRILL` | 显式启用 T4-004 真实 MySQL/Redis 故障演练；仅精确值 `1` 启用 | 否 | T4-004 手工联调 | 临时进程环境；默认不设置 |
| `OFFICE_AI_T4_FAILURE_DRILL_RUN_ID` | 隔离一次故障演练数据的 UUID | 否 | T4-004 手工联调 | 临时进程环境；不得复用生产 identity |
| `OFFICE_AI_TASK_TIMEOUT_SECONDS` | 完整任务 timeout，默认 2700 | 否 | T3-001 | Admin config/普通变量 |

## P5-001 Post-Alpha 配置合同（`post-alpha-contract.v1`）

下表冻结非 Secret 名称与 fail-closed 默认值。P5-003 已把 Chat 变量接入
Settings/Compose；P5-004 已接入两项 Deck 上限。媒体变量仍只有在对应代码、测试和
文档同步时才接入。

| 变量 | 默认值 | 用途与边界 |
|---|---:|---|
| `OFFICE_AI_CHAT_MAX_INPUT_CHARS` | `32768` | 单条 user message Unicode 字符上限，Provider 前拒绝 |
| `OFFICE_AI_CHAT_MAX_OUTPUT_TOKENS` | `8192` | 单个 run 请求上限；仍不得超过发布 model snapshot |
| `OFFICE_AI_CHAT_STREAM_TIMEOUT_SECONDS` | `180` | 首期完整 SSE run deadline；timeout 依 in-flight 状态收口 |
| `OFFICE_AI_CHAT_HEARTBEAT_SECONDS` | `15` | 无正文、无 sequence 的 SSE heartbeat 间隔 |
| `OFFICE_AI_CHAT_MAX_ACTIVE_RUNS_PER_USER` | `1` | 同用户 active run 上限，MySQL admission 为事实 |
| `OFFICE_AI_CHAT_RUNS_PER_HOUR` | `20` | 用户级 rolling-hour admission |
| `OFFICE_AI_CHAT_RUNS_PER_DAY` | `100` | 用户级 UTC daily admission |
| `OFFICE_AI_CHAT_THREAD_RETENTION_DAYS` | `365` | 最后活动后的 active 正文默认保留 |
| `OFFICE_AI_CHAT_SOFT_DELETE_GRACE_DAYS` | `30` | soft delete 可恢复期 |
| `OFFICE_AI_CHAT_BACKUP_RETENTION_DAYS` | `30` | active purge 后备份最长残留，不能宣传即时擦除 |
| `OFFICE_AI_CHAT_PURGE_SLA_HOURS` | `24` | 显式彻底删除清除 active 正文的最长时间 |
| `OFFICE_AI_CHAT_EXPORT_MAX_BYTES` | `10485760` | owner-scoped JSON 导出上限；不建立公共 URL |
| `OFFICE_AI_CHAT_FILE_CONTEXT_MODE` | `deck_only` | P5-003 Chat 禁止附件；P5-004 转 Draft 才接入冻结资产 |
| `OFFICE_AI_CHAT_THINKING_DEFAULT_ENABLED` | `false` | per-run opt-in 且 model capability 为 true 才能发送 |
| `OFFICE_AI_CHAT_WEB_SEARCH_ENABLED` | `false` | 首期无 Web search/fetch 工具；设置 true 必须 fail startup |
| `OFFICE_AI_DECK_MAX_SLIDES` | `40` | `deck-brief.v1` 最大页数 |
| `OFFICE_AI_DECK_MAX_CONTEXT_ASSETS` | `20` | 复用 owner-scoped `ready/valid` 资产；总量仍为 200 MB |
| `OFFICE_AI_MEDIA_MAX_ACTIVE_JOBS_PER_USER` | `2` | image/video 合计 active job admission |
| `OFFICE_AI_IMAGE_MAX_PROMPT_CHARS` | `4000` | 图片 Prompt 上限；日志只记 hash/length |
| `OFFICE_AI_IMAGE_PROVIDER_TIMEOUT_SECONDS` | `360` | 图片单请求 deadline；未知结果不得自动重试 |
| `OFFICE_AI_VIDEO_MAX_PROMPT_CHARS` | `2000` | 视频 Prompt 上限 |
| `OFFICE_AI_VIDEO_POLL_INTERVAL_SECONDS` | `5` | 服务端最小轮询间隔，支持 Provider Retry-After |
| `OFFICE_AI_VIDEO_JOB_TIMEOUT_SECONDS` | `1800` | 视频任务 deadline；超时按 Provider ID 可查询性收口 |
| `OFFICE_AI_VIDEO_MAX_BYTES` | `104857600` | 下载后 MP4 最大字节数；stream 中持续强制 |
| `OFFICE_AI_VIDEO_MAX_DURATION_SECONDS` | `20` | ffprobe/full-decode 接受的最大视频时长 |
| `OFFICE_AI_VIDEO_OUTPUT_HOST_ALLOWLIST` | `platform-outputs.agnes-ai.space` | 结果 HTTPS hostname 精确 allowlist；不允许 suffix 匹配 |
| `OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED` | `false` | 禁止本地 public URL/tunnel；首期视频仅 text-to-video |
| `OFFICE_AI_VIDEO_EMBED_ENABLED` | `false` | P5-007 双 Office/WPS Gate 前禁止 PPTX 内嵌 |

P5-004 runtime 已从 Settings/Compose 注入
`OFFICE_AI_DECK_MAX_SLIDES=40` 与 `OFFICE_AI_DECK_MAX_CONTEXT_ASSETS=20`；
服务端同时维持 200 MiB 总量、owner、状态和冻结版本 Gate。当前 Compose 启动不会替代
显式 Alembic upgrade；P5-005 不新增环境变量，真实 runtime 已升级到
`20260729_0018 (head)`，并以当前 source 重建 backend、frontend、generation-worker
与 ppt-renderer；所有受影响服务 healthy。

P5-007 不新增 migration；workflow-worker 使用包含 `ffmpeg/ffprobe` 的 Backend image
执行视频完整解码与 poster 提取。`OFFICE_AI_VIDEO_EMBED_ENABLED=true` 仍会 fail
startup；P5-008 取得 PowerPoint/WPS 双应用实际播放证据前不允许改变。

上述安全开关不是普通 feature toggle：
`OFFICE_AI_CHAT_WEB_SEARCH_ENABLED=false`、
`OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED=false` 和
`OFFICE_AI_VIDEO_EMBED_ENABLED=false` 是首期唯一支持值。实现若收到 `true` 必须
fail startup，直到后续批准合同、migration/代码和对应安全/兼容 Gate 同时交付。

### 真实 Provider Contract opt-in

| 变量 | 用途 | 安全边界 |
|---|---|---|
| `OFFICE_AI_RUN_REAL_AGNES_CHAT_CONTRACT` | 精确值 `1` 才运行真实 2.5/2.0 SSE/Thinking/cancel Contract | 默认不设置；Mock 不能替代 |
| `OFFICE_AI_AGNES_CHAT_CONTRACT_CREDENTIAL_ID` | 管理后台已加密 Credential UUID | 非 API Key；仅与 opt-in 同时使用 |
| `OFFICE_AI_AGNES_CHAT_CONTRACT_MODEL_IDS` | 两个已发布 text model UUID，顺序不代表 fallback | 测试必须逐个显式选择并分别报告 |
| `OFFICE_AI_RUN_REAL_AGNES_IMAGE_CONTRACT` | 精确值 `1` 才运行 image text/Data URI/尺寸 Contract | 默认不设置；不发送用户文件 |
| `OFFICE_AI_AGNES_IMAGE_CONTRACT_CREDENTIAL_ID` | 已加密 image Credential UUID | 不接受明文 Key 变量 |
| `OFFICE_AI_AGNES_IMAGE_CONTRACT_MODEL_ID` | 已发布 `agnes-image-2.1-flash` model UUID | response bytes/尺寸为权威 |
| `OFFICE_AI_RUN_REAL_AGNES_VIDEO_CONTRACT` | 精确值 `1` 才运行 text-to-video create/poll Contract | 默认不设置；首期不测 public URL 输入 |
| `OFFICE_AI_AGNES_VIDEO_CONTRACT_CREDENTIAL_ID` | 已加密 video Credential UUID | 不接受明文 Key 变量 |
| `OFFICE_AI_AGNES_VIDEO_CONTRACT_MODEL_ID` | 已发布 `agnes-video-v2.0` model UUID | Provider ID 视为 opaque |

真实 Contract 只能用完全合成、无用户内容的输入；不得打印 Key、Prompt、response body、
Provider URL query、Data URI 或生成内容。测试只记录 model/credential opaque ID、
request ID、状态、token/latency、实际尺寸/时长和 stable failure category。
P5-003 只在显式 opt-in 进程中使用加密 Credential UUID 和两个发布 model ID，合成
2.5/2.0 stream/close 合同共 `4 passed`；未把 selector 写入 Compose，也未打印 Key、
Prompt 或 response body。默认 test suite 仍跳过真实 Provider。

### Post-Alpha runtime 拓扑

- P5-003 Chat 由 FastAPI 使用现有受控 edge egress 调用唯一选定 text model，并把
  `chat-sse.v1` 转发给 Browser；API Key 不进入 Frontend、Redis 或 queue。
- P5-004 Deck 编译可由独立 worker 执行，但只有受控 Provider-capable process 能解密
  Credential；解析 worker/generation-worker 权限不扩大。
- P5-006/P5-007 媒体 worker 需要 edge + private、MySQL/Redis 和 owner-scoped media
  storage；不得挂载用户源文件 broad root，不映射 Host port，non-root/read-only rootfs。
- image Data URI 只在受限进程内从已验证 asset bytes 临时构造；不得落入环境变量、命令
  参数、日志、数据库或 queue。Provider URL output 由安全 downloader 拉取后立即转存。
- 视频轮询使用已持久化 opaque Provider ID；Redis 丢失后从 MySQL job/outbox 恢复。
  前端 progress 只能来自持久 job/provider response，不能使用 timer 假进度。

本项目固定使用 Frontend Host port `8888` 与 Backend Host port `9999`。这只改变
Windows Host 映射、Frontend 默认 API base 与 Backend CORS origin；容器内部
`5173/8000` 及 private-network service URL 不变。需要临时覆盖时可使用上表普通变量，
但仓库默认值仍以 `8888/9999` 为准。

T3-001 已在 backend Compose environment 显式映射 `OFFICE_AI_TASK_TIMEOUT_SECONDS`。
FastAPI lifespan 启动 MySQL Outbox Dispatcher 和 stale-task reconciler；Redis queue
可丢失，任务、步骤和账务事实仍以 MySQL 为准。Python generation consumer 只接收
不含 Secret/文件正文/storage key 的任务 ID 与事件合同。Post-Alpha
`generation-worker` 已注入真实 PPTX/XLSX step executor。

T3-002 的 `ppt-renderer` 使用独立 pinned Node image，只在 private network 暴露 internal HTTP，root filesystem read-only，以 non-root 用户写入 `shared-work`。Backend 将同一 volume 只读挂载到 `OFFICE_AI_RENDERED_ROOT`，验证 contract/hash/size 后再复制到受控资产存储；Renderer 不接收 Secret、Provider credential、用户路径或 Host port。

T3-003 将 LibreOffice 改为项目自有 internal sidecar：non-root、read-only rootfs、private network、无 Host port/Secret/Provider credential；只读挂载原始 asset volume，只写 `shared-work`，以 `--headless` 打开并转 PDF，再用 PDFium 生成逐页 PNG。Backend 复验 sidecar schema、固定 key、hash/size 与页数后复制到 asset `quality/` 目录。当前本机未安装 Docker/`soffice`，该描述是静态合同而非本机 runtime 通过证据。

T3-004 在同一 sidecar 镜像安装 `libreoffice-calc` 并增加
`/v1/spreadsheet/recalculate`。sidecar 只读固定
`users/{user_id}/outputs/{asset_id}/analysis.xlsx`，使用每 request 独立
`UserInstallation` profile 和 headless/no-restore 参数，在 `shared-work` 写 validation
copy 与 report；Backend 通过只读 `/app/rendered` 挂载复验 artifact。当前本机 PATH 无
Docker/`soffice`，因此只有 Python/fake-sidecar contract 证据，没有真实 Calc runtime
通过证据。

T3-005 不新增环境变量或网络服务；Excel QA 继续复用上述 private sidecar、受控 asset
root 和 MySQL checkpoint/ledger。当前任务已再次实际尝试任务卡 Docker 命令与
`soffice --version`，均在进程启动前 `CommandNotFoundException`；因此没有新增 Docker、
真实 LibreOffice Calc、MySQL/Redis、Microsoft Office/WPS 或真实 Agnes runtime 证据。

T4-002 不新增环境变量、网络服务或 Secret 文件。管理员重新认证复用既有
`OFFICE_AI_SESSION_SECRET`/Argon2id 身份边界，资产操作复用既有受控 volumes；
Credential Reveal 仍要求 `OFFICE_AI_MASTER_KEY`。本地浏览器验证只使用受控 Mock API，
不代表 Docker、MySQL/Redis、Agnes、LibreOffice 或 Office/WPS runtime 通过。

T4-003 不新增 Secret 或外部网络依赖。private 原件只从 ignored
`golden-data/private/` 本地读取；tracked 脱敏副本和 Manifest 不得保存 private 路径、
private author metadata、用户/客户身份或电话。当前 Microsoft PowerPoint/Excel 16.0
已实际打开并导出黄金输出；PATH 无 Docker，LibreOffice/WPS 未安装，真实 Agnes 未
opt-in。这些缺口不得由 Python/Node/OOXML 或 Microsoft Office 单 runtime 证据替代。

T4-004 已在 Windows restart 后实际验证 WSL `2.7.11.0`/kernel `6.18.33.2`、
Docker Desktop `4.83.0`、Linux Client/Engine `29.6.2` 与 Compose `v5.3.1`；
`hello-world`、项目 Compose config、backend image rebuild、MySQL `8.4.5`、Redis
`7.4.5`、PPT Renderer 与 LibreOffice `25.2.3.2` sidecar 均有真实 runtime 证据。
Docker 程序位于 `D:\works\tool\Docker`，WSL data root 位于
`D:\works\tool\DockerData`。WPS Office `12.1.0.26899` 与已激活的 Microsoft Office
`16.0.20131.20154` 均已实际打开同一组黄金 PPTX/XLSX 验证副本；PowerPoint 4 页、
Excel 2 Sheet、关键指标、公式结果和图表均通过视觉/交互检查，且双应用验证后的副本
SHA-256 与 tracked expected 一致。

T4-004 故障演练默认 skip，只有同时提供 opt-in 与唯一 run UUID 才允许连接真实
MySQL/Redis。演练使用隔离 database、合成 identity 和非真实 Credential，不读取用户文件
或发送 Provider 请求；Redis stop/start 期间 MySQL task/outbox/ledger 为事实来源，结束后
不自动删除持久记录，以保留可审计证据。

### 本机兼容变量

- Settings 同时接受现有本地 `.env` 的 `OFFICE_AI_DB_HOST`、`OFFICE_AI_DB_PORT`、`OFFICE_AI_DB_NAME`、`OFFICE_AI_DB_USER`、`OFFICE_AI_DB_PASSWORD`，分别对应上表的 canonical MySQL变量。
- Canonical变量优先；兼容 alias 只用于保留现有本机配置，不写入 Compose，也不改变部署契约。
- 应用不会自动读取 `.env`。本机命令需使用 `python -m dotenv -f <path> run -- <command>` 或由 OS/IDE 注入；禁止用会回显变量值的命令检查配置。
- 用户已长期授权 Agent 按最小必要原则读取仓库根 `.env` 并向本项目临时进程注入所需
  值；该授权不改变应用的显式注入合同，也不允许打印、记录、复制、暂存或提交任何值，
  且不适用于其他环境文件。
- 本机 Windows Redis service 启用了密码认证。`OFFICE_AI_REDIS_URL` 必须通过本地未跟踪配置或临时进程环境注入；不得把 service config 中的密码复制到文档或 Git。

## Agnes Credential

- Agnes API Key 不使用固定仓库变量名写入 Compose，也不进入 `system_settings`。
- 管理员通过 `POST /api/v1/admin/credentials` 录入一个 Key；后端使用 `OFFICE_AI_MASTER_KEY` 加密后写入 `provider_credentials`。
- Master Key 必须使用密码学安全随机源生成并符合 Fernet key 格式；不得使用人类密码、源码默认值或 Provider Key 直接充当 Master Key。
- 测试、Reveal、轮换和停用均通过 `credential_id`，不在 worker command、queue payload 或日志中传明文 Key。
- `OFFICE_AI_MASTER_KEY` 缺失时，Credential 创建/Reveal/Provider 调用必须 fail closed。
- T2-004 真实 Contract Test 默认 skip；只有 `OFFICE_AI_RUN_REAL_AGNES_CONTRACT=1` 时才使用 runtime Database URL、Master Key 和 `OFFICE_AI_AGNES_CONTRACT_CREDENTIAL_ID` 读取已加密 Credential。测试不读取 `.env`、不接受单独的明文 Key 变量、不回显 Key；缺少任一 runtime 前置时不得声称真实 Agnes 通过。
- `2026-07-26` 真实预检证明 endpoint、Key 与 text model 在不带
  `response_format` 的最小请求上返回 HTTP `200`；两个 live Contract 携带 native
  `response_format` 时因上游 grammar backend 返回 HTTP `400`。
- `2026-07-27` 以 RED/GREEN 固定 capability contract：Agnes
  `native_response_format` 默认 `false`，只在配置显式 `true` 时发送该字段；应用层仍执行
  strict Schema、一次 repair 和 Evidence 校验。使用一次性加密 Credential 的真实 Contract
  为 `4 passed`，没有打印或持久化 Key、Prompt、response body 或用户文件。
- Master Key 轮换不覆盖旧 Credential；新 Key 以新的 Credential ID 和 `rotation_source` 录入，旧记录停用并保留审计链。跨 Master Key 重新加密工具不在 T1-004 范围。

## Auth 与管理员 Bootstrap

- `OFFICE_AI_SESSION_SECRET` 缺失时 Auth/Invite 路由 fail closed 并返回 `auth_not_configured`；应用不提供源码默认签名 Secret。
- Access Token 默认 900 秒，Refresh Token 默认 2592000 秒；Refresh Token 轮换后旧值立即失效。
- 初始管理员手机号和密码必须同时由 runtime environment 提供。执行 `python -m app.commands.bootstrap_admin` 创建；重复执行只报告已存在，不修改密码，也不记录手机号或密码。
- Bootstrap 完成后应从当前进程环境移除这两个变量；真实值不得写入 Compose 文件、`.env.example`、测试 fixture、日志或聊天。

## 本地文件与卷

- Compose backend 固定挂载 `app-files:/app/files`，并显式映射 50 MB 单文件、20 MB 图片和 200 MB 单任务默认值。
- Compose 使用一次性 `storage-init` 初始化 `app-files`、`parsed-files`、
  `evidence-files` 与 `shared-work` 根目录。该 service 以 root 仅执行
  `chown 10001:10001` 与 `chmod 0750`，`network_mode: none`、无 environment/Secret、
  root filesystem read-only，成功退出后 Backend、Worker、PPT Renderer 与 LibreOffice
  才会启动；长期服务仍全部以 `10001:10001` 运行。`docker compose ps --all` 中
  `storage-init` 显示 `exited (0)` 是预期完成态，不是服务故障。
- ASGI upload body gate 自动使用 `OFFICE_AI_MAX_FILE_BYTES + 64 KiB`；64 KiB 只用于单文件 multipart header、清理后文件名、UUID field、boundary/framing，不是额外文件容量。新请求 body 先进入 middleware 自己的 `SpooledTemporaryFile`（1 MiB memory threshold），完整验证后才 replay 给 multipart parser；该 preflight spool 与 parser/file spool 都不写入公开目录，并在请求结束或拒绝时关闭。
- Local Storage key 固定为 `users/{user_id}/quarantine/{asset_id}/original.{ext}`；原始文件名、手机号和客户端路径不参与磁盘定位。
- T1-005 API 每次只流式接收一个文件；T2-001 worker service 的 batch contract 在 claim/scan 前一次性校验最多 20 个文件和 200 MB 总量，当前不新增用户 batch HTTP API。
- T2-001 worker 将 `app-files` 只读挂载到 `/app/files`，将独立 `parsed-files` 可写挂载到 `/app/parsed`；结构化结果固定为 `users/{user_id}/parsed/{asset_id}/content.json`，单结果默认不超过 10 MB。
- T2-002 worker 将独立 `evidence-files` 可写挂载到 `/app/evidence`；Manifest key 固定为 `users/{user_id}/assets/{asset_id}/extracted/evidence-manifest.json`，单结果默认不超过 10 MB。`app-files` 仍只读，Evidence 输出不能改写原始 quarantine。
- 解析 worker 使用 backend 镜像与真实 polling entrypoint，只连接 internal `private` network，不挂载 Master/Provider Key；root filesystem 只读，`/tmp` 使用 tmpfs，并限制为 `768m` memory、`1.0` CPU 和 `128` PIDs。Office XML member、parser 总结构项、OCR response 和两类结构化输出分别有独立预算；parser 在可终止子进程中执行并受 timeout 约束。
- Post-Alpha 新增 `workflow-worker`，使用 backend 镜像和
  `python -m app.workers.workflow` entrypoint，消费
  `office_ai:workflow:queue`。它需要 MySQL、Redis、只读 `parsed-files`/
  `evidence-files` 及 Agnes credential 解密能力，因此连接 `edge + private` 并挂载
  `OFFICE_AI_MASTER_KEY`；不映射 Host port，root filesystem read-only，以
  `10001:10001` 运行。原解析 `worker` 继续只连 private、无 Master/Provider credential。
- Backend Outbox publisher 按 event type 分流：`brief.*` 只进入 workflow queue，
  `generation.*` 只进入 `office_ai:generation:queue`，不同 consumer 不混取。真实 Compose
  已构建并启动 `workflow-worker` 与 `generation-worker`，当前 11 个长期服务 healthy。
- Post-Alpha 新增 `generation-worker`，使用 backend 镜像和
  `python -m app.workers.generation` entrypoint。它只连接 private network，不映射
  Host port，不挂载 Master/Provider credential、parsed volume 或用户源文件；
  root filesystem read-only，以 `10001:10001` 运行。为从已确认的冻结来源构造
  reference-grade PPT Plan，它只读挂载 `evidence-files` 到 `/app/evidence`，并复验
  owner、project、asset version、Manifest status 与 SHA-256；不能写回或改造 Evidence。
  它可写 owner-scoped
  `app-files` 输出，只读共享 Renderer work volume，并通过 internal PPT Renderer 与
  LibreOffice sidecar 完成生成和 QA。
- generation runner 只从 MySQL 读取 confirmed Structured Brief 与 task 的冻结 model/
  skill/template snapshot；任务 ID queue message 不携带正文。claim 后写入 10%，每完成
  一个输出 step 按比例持久化进度，settle 写入 100%。空/非法 Brief 在调用 Renderer 前
  permanent failure，不进入重试风暴。
- PaddleOCR 使用独立 `office-ai-paddleocr:local` image。为避免不可解析的旧 image tag，
  以可解析的 `paddlepaddle/paddle:3.3.1` 为基础，再固定安装经真实 inference 验证的
  PaddlePaddle `3.1.1` 与 PaddleOCR `3.7.0`；构建阶段固定下载
  `PP-OCRv5_mobile_det/rec` 到 non-root 可读的 `/opt/paddle-home`。runtime 只连
  internal `private` network、无 Host port、无 Provider credential、root filesystem
  只读，使用 `/tmp` tmpfs，并限制为 `2g` memory、`2.0` CPU 和 `128` PIDs。
- T4-005 最终 Compose 冷启动实际构建并启动 9/9 healthy services；合成图片 OCR 返回
  `paddleocr-response.v1` 并识别 `OFFICE AI 12345`。ClamAV 固定 `1.4.5`，绕过需要
  root 的官方 init wrapper，以 non-root direct `clamd`、read-only rootfs 和 tmpfs
  运行；固定镜像 signature database 实际检测 EICAR。FreshClam 上游 CDN
  403/cooldown 使在线更新未验证，生产前必须接入受控更新来源。

| 路径/卷 | 内容 | Git |
|---|---|---|
| `backend/files/` / `app-files` | quarantine、原文件、extracted、preview、output | 必须忽略 |
| `parsed-files` | T2-001 结构化中间结果；不含 Evidence Manifest | Docker volume，不进入 Git |
| `evidence-files` | T2-002 版本化 Evidence Manifest | Docker volume，不进入 Git |

`backend` 只为鉴权后的资产删除流程以读写方式挂载 `parsed-files` 与 `evidence-files`；常规解析和 Manifest 写入仍由隔离 worker 负责。删除流程只使用数据库中已持久化的 owner/asset deterministic key，不扫描 broad root。
| `mysql-data` | MySQL 数据 | 必须忽略 |
| `redis-data` | 可丢失 Redis 状态 | 必须忽略 |
| `shared-work` | renderer/QA 临时交换 | 必须忽略或仅 Docker volume |
| `golden-data/private/` | 获授权且脱敏前的本地材料 | 必须忽略 |

## 安全录入与验证

1. 仅在本机未跟踪配置、OS environment 或 CI Secret 中设置敏感值。
2. 不执行会回显 Secret 的诊断命令；应用日志只记录变量是否配置，不记录内容。
3. 提交前运行：

```powershell
git check-ignore -v .env
git status --short
git diff --cached --name-only
```

4. 如果 `.env` 或任何 Secret 文件出现在 Git 状态/暂存区，立即停止提交并处理，不把路径内容复制到聊天。
