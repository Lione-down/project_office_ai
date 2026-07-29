# Office AI 进度记录

- 最后更新：`2026-07-29`
- 最近完成：`P5-004 Deck Draft、逐页编辑、Skill 与 Preflight`
- 下一任务：`P5-005 模板目录、缩略图与版本快照`（唯一 `READY`）
- 当前状态：`POST-ALPHA DECK GATE COMPLETE`；Alpha 仍为
  `INTERNAL ALPHA COMPLETE / ACCEPT_WITH_DECLARED_BOUNDARIES`
- 当前分支：`main`
- 远端：`origin/main`

## P5-004 Deck Draft、逐页编辑、Skill 与 Preflight（DONE）

### RED -> GREEN 与实现

- RED 先锁定 strict `deck-brief.v1`、一次 bounded repair、owner/source/asset 边界、
  revision/checksum/state、Skill、Preflight、generation 幂等与 Deck editor；GREEN
  新增 `deck_drafts`、`deck_draft_revisions`、`deck_draft_inputs` 和 additive migration。
- 成功 assistant message 才能创建稳定 Draft；灵感、资料和混合 provenance 分离，
  source asset 必须 owner-scoped、`ready/valid`、版本冻结且不超过 20 个/200 MiB。
  Outline Director 只允许一次 repair，仍不满足 Schema 时返回稳定错误且不创建 Draft。
- 固化 `ppt.knowledge-education.v1`，保留销售汇报 Skill；用户显式选择优先，不可用
  model/Skill 组合 fail closed。每次编辑追加不可变 revision，stale revision 拒绝覆盖。
- confirm/preflight 复用既有 Brief、WorkflowTask、Outbox、积分、Renderer、QA 和下载
  状态机；同一 generation idempotency key 只创建一个 task/reserve。Chat message 只投影
  MySQL 权威 Draft/revision/generation 状态，不建立第二套任务事实。
- Vue 新增 Chat “整理为 PPT 大纲”入口、独立创建页与 Deck Studio；支持逐页增删、
  复制、排序、标题/要点/讲者备注/视觉建议编辑、保存、confirm、Preflight 和生成交接。

### 验证与真实证据

- Focused：Backend `tests/decks tests/skills tests/preflight tests/generation`
  `99 passed`；Frontend Deck `4 passed`。
- Broad：Backend full `662 passed, 11 skipped`；Ruff check 通过、format
  `420 files already formatted`；Frontend full `93 passed`、production build 通过；
  `docker compose config --quiet` 通过。
- Runtime：重建 backend/frontend/generation-worker 后均 healthy；ready probe 的
  MySQL/Redis 均为 ready；显式 Alembic upgrade 后为 `20260729_0017 (head)`。
- Chrome 真实用户态：成功 Agnes assistant message 显示 Deck 入口；真实 Outline
  调用在一次 repair 后仍不满足 strict Schema，UI 返回 `Deck Brief Schema 无效`，
  未创建 Draft，证明 fail-closed 边界。没有把该失败宣称为 Provider 成功。
- Provider-free browser proof 使用脱敏 synthetic Draft 验证 3 页加载、排序
  `MOVE_TARGET`、复制为 4 页和保存至 `Revision 2`；验证后删除 1 个 Draft、2 个
  Revision 和 2 个 Input，MySQL 无残留。未提交 generation，因此未创建 synthetic
  task、文件或积分变动。
- 本任务没有取得真实 PPTX、LibreOffice、Microsoft PowerPoint 或 WPS 新证据；
  generation/Renderer/QA 交接由自动化 integration contract 证明，最终兼容性仍属于
  P5-008 Human/desktop Gate。

### Changed files 与交接

- Backend：Deck migration/models/contracts/repository/service/handoff/API/settings、
  knowledge/education Skill、Preflight/Generation/Renderer/Chat projection 及 tests。
- Frontend：Deck types/API/create/editor/routes/tests，以及 Chat Deck action。
- Runtime/records：Compose Deck limits、P5-004/P5-005 状态、正式 API/Data/Security/
  Environment/Plan、`pitfalls.md` 与本文件。
- 未触碰/暂存 `.env`、`.playwright-cli/`、`design-system/` 或旧
  `docs/ui-mockups/`；未实现 P5-005 模板目录、图片或视频。P5-005 是下一唯一 `READY`。

## P5-003 双模型会话、SSE 与历史（DONE）

### RED -> GREEN 与实现

- RED 先锁定 additive migration/model/state、owner CRUD、幂等、显式模型选择、
  Provider Mock stream、SSE parser/reconnect/cancel、Markdown XSS、branch 与 Chat UI。
  初始 Backend 因缺 `ProviderStreamChunk` 失败，Frontend 因缺 Chat modules/route/view
  失败；真实 MySQL 首轮再暴露 assistant `run_id` 更新早于 `chat_runs` INSERT。
- GREEN 建立 `chat_threads`、`chat_messages`、`chat_runs` 与 `provider_calls.chat_run_id`，
  持久化 provider/credential/model/capability/pricing snapshot、partial checkpoint、
  monotonic sequence 和服务端权威终态。SQL 顺序回归锁定先 INSERT run、再绑定 assistant
  外键，修复 SQLite Mock 未暴露的 MySQL 约束差异。
- FastAPI 提供 owner-scoped thread CRUD/search、stream/reconnect/cancel；同
  owner/idempotency key/payload 只调用一次 Provider，失败不 fallback。Agnes adapter
  使用官方 `/v1/chat/completions` + `stream:true`，Thinking 只在 capability + per-run
  opt-in 时发送；工具、文件与 Web 均 fail closed。
- Vue 新增 AI 创作导航、会话/时间分组、双模型选择、Chat/PPT mode、Thinking gate、
  stop/copy/edit-resend/regenerate、安全 Markdown 和高风险未核验提示。新 Chat 代码显式
  推荐 2.5，既有全局 2.0 recommended 状态保持不变。

### 验证与真实证据

- Focused：Backend Chat `18 passed, 4 skipped`；Chat + Provider suites
  `56 passed, 7 skipped`；Frontend Chat `4 files / 10 passed`，route/shell
  `2 files / 9 passed`。
- Broad：Backend full `644 passed, 11 skipped`；Ruff `402 files already formatted`；
  Frontend full `27 files / 88 passed`；production build `190 modules transformed`；
  `docker compose config --quiet` 通过。
- Security：DOMPurify + raw HTML disabled，危险 URL/event/script/image 拒绝；owner、
  32768 字输入、tool/file injection、disconnect/reconnect、cancel 和 no-fallback 回归
  通过。`npm audit --audit-level=high` 为 0 vulnerabilities；`pip check` 无 broken
  requirement；`pip-audit` 除本地非 PyPI package 外无已知漏洞。
- Runtime：真实 MySQL 从 `20260727_0015` 升级至 `20260729_0016 (head)`，当前
  25 张业务表；backend/frontend 均 healthy。runtime 只发布公开 model/capability
  metadata：2.0 保留旧文件默认并补 `chat_stream`，2.5 作为 Chat 推荐显式发布；未读取
  Credential 密文。
- Provider：opt-in 测试用显式 credential + 两个 model ID，2.5/2.0 完整 stream
  latency 为 `7262/1234ms`，均为 `277 prompt + 7 completion tokens`；两模型
  close-after-delta 也通过，合计 `4 passed`。仅输出脱敏 metadata，不打印 Prompt/
  response body/Key。
- Chrome 真实用户态：2.5 与 2.0 两条 run 均 `succeeded`，latency 为
  `6857/6724ms`、token 为 `331/359`，刷新后 2 条历史仍存在；UI stop 收口为
  `cancelled_partial`。所有 ProviderCall `is_redacted=true`，日志高置信正文/Secret
  pattern 命中 0，Console error 0。
- Desktop `1280x800` 与 Mobile `375x812` 均无 document horizontal overflow；
  会话栏、composer、双模型和 capability-gated Thinking 可用。Office/WPS 不适用：
  本任务未生成 PPTX、XLSX 或媒体文件。

### Changed files 与交接

- Backend：Chat migration、thread/message/run models、ProviderCall link、schemas、
  service/runtime/persistence/request modules、Agnes stream adapter、API/router/settings
  与 Chat contracts/tests。
- Frontend：Chat types/API/SSE/store/safe Markdown、Studio view/style/tests、AI 创作
  route/navigation，以及 `markdown-it`/`dompurify` 依赖。
- Contracts/records：P5-003/P5-004 状态、Post-Alpha 计划、`docs/PLAN.md`、API/Data/
  Security/Environment、`pitfalls.md` 与本文件。
- 未触碰/暂存 `.env`、`.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/`；
  未实现 Deck Draft、模板、图片、视频或文件生成。P5-004 是下一唯一 `READY`。

## P5-002 首页最近任务真实展示（DONE）

### RED -> GREEN 与实现

- RED：Home component contract 在旧静态首页上为 `5 failed, 2 passed`，锁定
  owner-scoped 真实 workflow list、initial loading/empty、倒序截取 5 条、权威状态/
  progress、失败/retry、非终态轮询与 unmount 清理。
- GREEN：首页复用既有 `workspaceApi.listWorkflowTasks`、`WorkflowTask` 和
  `workflow-task-detail` route；按 `created_at` 倒序显示最近 `5` 条，不改完整任务页
  的最多 100 条合同。
- 新 workspace presentation helper 让首页、任务列表和详情复用同一 terminal status、
  状态文案与输出类型映射。progress/time/title/output 均直接来自 API，不使用前端假进度
  或第二套持久状态。
- 成功列表存在非终态任务时，在前一请求完成后安排单次 `3000ms` refresh；全部终态、
  API 失败、离页或 unmount 时停止。失败态显示固定安全文案和显式 retry，不暴露
  `failure_code`、内部路径或 Provider detail。

### 验证与真实浏览器

- Focused Home 最终 `7 passed`；受共享映射影响的 Home/Resource/Task Detail 相关回归
  `5 files / 20 passed`。
- Frontend full 为 `23 files / 78 passed`；production build 为
  `106 modules transformed`。Backend `tests/workflow_tasks` 为 `13 passed`。
- 真实已登录 Chrome 只读显示当前用户最近 `5` 条真实任务，包含已完成/失败和服务端
  `100%` progress；首条 link 成功进入既有 task detail。未创建、重试任务或扣积分。
- Desktop `2048x1146`：document `2048/2048`、User Shell `2033/2033`，最近任务双列；
  Mobile `375x812`：document `375/375`、User Shell `360/360`，最近任务单列 `328px`；
  5 个详情链接均可键盘聚焦，Console warning/error 为 `0`。
- QA 临时以不含 Secret 的 API base 启动当前源码 Vite；结束后原 Frontend 容器已恢复，
  Frontend `8888=200`、Backend ready `9999=200`。

### Changed files 与边界

- Frontend：workspace workflow task presentation helper、Home 实现/contract，以及任务
  列表/详情对 shared mapping 的复用。
- Records：P5-002/P5-003 卡、索引、Post-Alpha 总计划、`docs/PLAN.md` 和本文件。
- 未修改 API、数据库 Schema、任务/积分事实、Provider/Renderer 或环境配置；未读取
  `.env`，未触碰/暂存 `.playwright-cli/`、`design-system/` 或旧
  `docs/ui-mockups/`。
- 本任务不调用 Provider、不生成 Office 文件，因此不产生 Agnes、Microsoft Office、
  WPS 或 Renderer 新证据。

## P5-001 技术、API、Data、Security 与 Environment 合同（DONE）

### 合同与第 19 节决策

- 在任何业务代码或 migration 前，把批准 PRD 冻结为 `post-alpha-contract.v1`，同步
  Post-Alpha 架构、Chat/Deck/Media 状态机、14 个 endpoint、SSE reconnect/cancel/
  partial/uncertain、owner scope、幂等、错误和缓存合同。
- 数据计划从当前 22 张表以 9 张 additive 表增至 31 张：thread/message/run/tool、
  Draft/revision/input、media job/input；P5-001 没有创建实际 migration。
- 正文保留合同为 active 365 天、soft-delete grace 30 天、显式 purge 24 小时内清除
  active 正文、备份最长再残留 30 天；账务/audit/既有生成资产不伪装删除。
- 首期文件上下文固定 `deck_only`，Thinking 默认关闭且 per-run/capability gated；Chat
  admission 为每用户 1 个 active run、20 次/小时、100 次/日，单消息 32768 字符、
  输出 8192 token。
- 首批冻结既有 `ppt.executive-blue.v1`、`ppt.operating-review.v1`、
  `ppt.data-story.v1` 三套系统模板；P5-005 再补齐分类、缩略图、来源/版权和兼容 Skill。
- `OFFICE_AI_CHAT_WEB_SEARCH_ENABLED=false`、
  `OFFICE_AI_MEDIA_PUBLIC_URL_INPUT_ENABLED=false`、
  `OFFICE_AI_VIDEO_EMBED_ENABLED=false` 是首期唯一支持值。视频默认独立 MP4 + poster；
  内嵌必须等待 P5-007 双 Microsoft PowerPoint/WPS Gate。
- 医疗、法律、金融等高风险内容持续显示未核验提示，并在 Deck/media/generation 前要求
  `high_risk_confirmation_required`。确认不等于事实、专业建议或版权已验证。

### RED -> GREEN 与验证

- RED：先新增 `scripts/validate-post-alpha-contracts.py`，旧五份正式文档按预期失败
  `97` 项，锁定 endpoint、状态、保留/删除、capability、环境变量和证据边界。
- GREEN：同一 validator 通过，覆盖 `5` 份正式文档、`14` 个 endpoint、`3` 个状态机、
  `8` 项待确认决策。
- Broad：18 个相关 Markdown 均为严格 UTF-8，11 个本地链接全部有效；validator Ruff
  check/format 与 syntax 通过，`git diff --check` 通过。
- Security：新增 diff/validator 高置信 Secret pattern 命中 0；Git tracked
  environment-like 文件 0；`.env` 命中 `.gitignore`；业务代码和 migration diff 为 0。
- 2026-07-29 只读核对 Agnes 官方 2.5/2.0/Image/Video 文档以冻结未来 adapter 入口；
  没有读取 `.env`、调用 Provider、发送 Prompt 或生成媒体。官方文档核对不等于真实
  Agnes Contract Test。
- 本任务不运行产品 test suite、Docker/MySQL/Redis、Renderer 或 Office/WPS；它们与
  真实 Agnes 2.5/2.0/Image/Video 均保留为后续对应 Gate，未伪报通过。

### Changed files 与交接

- 正式合同：`docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、
  `docs/SECURITY.md`、`docs/ENVIRONMENT.md`。
- 可执行合同：`scripts/validate-post-alpha-contracts.py`。
- 计划与记录：Post-Alpha 总计划、P5-001/P5-002 任务卡、任务索引和本文件。
- 未修改业务代码、migration、Compose、PRD、`.env`、用户文件或未跟踪
  `.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/`。
- P5-001 完成后，P5-002 是唯一 `READY`；新 Codex task 只能实现首页最近任务，不得在
  本会话提前实现。

## P5-000 Post-Alpha 执行计划基线（DONE）

### 范围与顺序裁决

- 将 `v1.0 / APPROVED` 的 Agnes 对话与 PPT 创作中心 PRD 转换为正式总执行计划、
  任务索引和 `P5-000`～`P5-008` 任务卡；本任务没有实现业务代码。
- PRD 第 18 节原建议先做首页最近任务、再做设计；第 20 节要求开发前同步正式合同。
  正式依赖链因此将合同设计设为 `P5-001`，首页最近任务完整后移为 `P5-002`；
  `P5-003`～`P5-008` 保持原相对顺序。
- `P5-001` 是唯一 `READY`；其余任务按单链 `BLOCKED`。正式 API/Data/Security/
  Environment 合同仍由 P5-001 交付，P5-000 没有提前修改。

### Changed files

- 总计划：
  `.hermes/plans/2026-07-29-office-ai-agnes-chat-ppt-studio-post-alpha.md`。
- 索引与任务卡：
  `.hermes/plans/office-ai-agnes-chat-ppt-studio-tasks/README.md`、
  `P5-000`～`P5-008`。
- 计划入口与进度：`docs/PLAN.md`、`docs/PROGRESS.md`。
- 用户已有 `.playwright-cli/`、`design-system/` 和旧 `docs/ui-mockups/` 保持未修改、
  未暂存。

### 验证与证据边界

- 计划 focused validator 通过：任务卡 `9/9`、索引链接 `9/9`、ID 连续，唯一
  `READY` 为 P5-001；每张后续卡均包含依赖、建议 commit、目标、范围、RED、
  验收、验证、证据边界和非目标。
- 13 个候选 Markdown 严格 UTF-8、本地链接 `11/11` 有效；11 个新增计划文件均不超过
  500 行。高置信 Secret pattern scan 为 0。
- `git diff --check` 通过；`.env` 命中 `.gitignore`，Git 未跟踪环境类文件；
  `docs/API.md`、`docs/DATA_MODEL.md`、`docs/SECURITY.md`、`docs/ENVIRONMENT.md`
  无 diff。
- 本任务不调用 Provider、不运行产品 runtime、不生成 Office 文件，因此不产生真实
  Agnes、Docker、Microsoft Office 或 WPS 新证据。

### 下一任务

- `P5-001` 只冻结 Post-Alpha 技术、API、Data、Security、Environment 和第 19 节决策；
  不得在同一会话提前实现 P5-002。

## Post-Alpha 结束页长目标文本质量阻断修复（COMPLETE）

### 根因与实现

- generation task `019fa920-a43f-71f5-8617-1d1bc3d90cb5` 的原生成与用户手工 retry
  都成功产出 27 页 PPTX，但两份 quality report 均只在第 27 页 shape 3 命中
  `body_text_overflow_risk`：结束页 subtitle 长度为 69，固定文本框安全容量为 67，且
  OOXML 不含 `a:normAutofit`。质量 precheck 因此在 LibreOffice 前永久阻断；重复 retry
  保持相同输入和布局，必然重复失败。
- Renderer 为所有 slide subtitle 启用 PptxGenJS `fit: "shrink"`，保留完整
  `brief.goal`，不截断用户目标，也不降低 `presentation-body-fit.v1` 质量规则。真实 OOXML
  回归直接定位目标 subtitle shape 并要求包含 `a:normAutofit`。
- 脱敏 presentation golden 按新增 OOXML 标记安全再生成，大小从 159,755 更新为
  159,771 bytes；输入、Evidence、Private 文件和 workbook golden 不变。

### 真实流程、质量与视觉证据

- 修复并重建 `ppt-renderer` 后，在用户已登录的 Chrome 对原任务执行第二次 retry。
  task 最终为 `succeeded/100%`、PPTX step `succeeded`、结算 800；第三个不可变资产
  `019fa929-c646-75d2-8132-4175625ecef9` 为 `quality=passed`、
  `download_allowed=true`、`findings=0`、`repair_attempt_count=0`。
- LibreOffice `25.2.3.2` 成功验证 27/27 页。第 27 页实际 PNG 复核确认 69 字目标完整
  换行为两行，无截断、重叠或越界；浏览器显示“任务已完成 / 全部文件已通过检查”。
- 验证文件：
  `D:\works\codexWorks\download\019fa920-结束页自适应修复验证.pptx`，
  2,653,204 bytes，SHA-256
  `27890b6446024343d1b85f9410605cf92933f27501b0d69fe6507007c2a6f836`。

### RED→GREEN 与 Broad

- RED：`applies shrink autofit to a long closing subtitle` 在旧代码上因缺少
  `<a:normAutofit>` 按预期失败；GREEN 后通过。
- Focused：PPT Renderer `23 passed` 与 build；Backend presentation quality/renderer
  `84 passed`。
- Broad：Backend `626 passed, 7 skipped`；Ruff check/format `383 files`；Frontend
  `23 files / 73 passed` 与 production build；`docker compose config --quiet` 及全部
  runtime health 通过。
- Changed files：PPT renderer 与真实 OOXML 回归、脱敏 golden PPT/manifest、修复计划、
  本进度记录和 `pitfalls.md`。用户已有 `.playwright-cli/`、`design-system/` 和旧版
  `docs/ui-mockups/` 保持未修改、未暂存。

## Post-Alpha 参考级经营管理汇报 PPT 修复（COMPLETE）

### 根因与实现

- 原生成结果只有 4 页：compiler 只把少量 Brief 文本放入固定正文框，未加载冻结来源的
  Evidence Manifest，也没有恢复 Excel 行列或构造 table data source；Renderer 又把完整
  Evidence ID 写进可见正文，既挤占版面又造成重叠。
- 新增确定性的管理汇报 composer：复验来源 owner/project/version/status/hash，从
  ExcelCellLocation 恢复 Sheet、行、列与数据分页，生成封面、目录、经营摘要、22 页业务
  表、问题与下一步措施、结束页，共 27 页。无表头 Sheet 使用安全通用列名，不丢首条数据；
  浮点展示最多保留 4 位小数，单页标题不再带多余“（1）”。
- `ppt.operating-review.v1` 使用红/金/暖白管理汇报视觉；正文使用 shrink/autofit，table
  使用动态字号和交替行底色。可见 slide 不显示完整 Evidence ID，完整引用进入 speaker
  notes；质量门禁新增可见 Evidence 泄漏和高密度正文检查，并排除页码、日期、页脚等
  placeholder 的正文误判。
- `generation-worker` 只读挂载 Evidence volume。任务级 retry 使用 retry 序号创建新的
  不可变输出资产，不覆盖 blocked 历史资产；失败 partial checkpoint 不再冒充完整输出。
  前端失败任务提供确定性的“重试生成”入口。Preflight 仅让系统确有 resolution UI 的
  blocker 阻断，Provider 自定义但无法操作的 code 保留为确认 warning。

### 真实浏览器、质量与 Office 证据

- 未重新上传，复用管理员已上传的 `第一季度数据.xlsx`。workflow
  `019fa7ff-18d8-7dfb-b4be-964baf3aa46a` 的 Brief 首轮成功；26 个单位确认全部按用户指示
  选择 `数量（个/件）`，confirmed revision 为
  `019fa801-0899-7727-949d-1fe4cd6f94e4`。
- 最终 generation task `019fa828-8f7a-706d-9b88-64a433b7be76`：
  `progress=100`、PPTX `succeeded`、quality `passed`、`download_allowed=true`、
  `findings=0`、结算 800；最终 asset 为
  `019fa828-93e2-7103-a2be-adadf5179674`。浏览器显示“任务已完成 / 全部文件已通过检查”。
- 私有只读参考为 28 页、8 个 table、9 个 picture、4 个 group、16 个 OLE；最终输出为
  27 页、22 个原生 table、0 个外部图片/嵌入对象。该结果复用管理叙事、红白层级和
  表格化表达，不复制私有品牌、Logo、图片、母版或嵌入对象。
- Microsoft PowerPoint 原生打开并导出 27/27 页 PNG；逐页 contact sheet 与重点页抽查
  未见文字重叠、截断或浮点尾差。OOXML 检查确认 27 个 slide、27 个 notes、可见完整
  Evidence ID 为 0、notes 中 1,199 个唯一 Evidence 引用。

### 下载、验证与 Changed files

- 最终文件：
  `D:\works\codexWorks\download\第一季度数据-参考级销售经营复盘-最终版.pptx`，
  2,652,931 bytes，SHA-256
  `8191b1f449b69c4b134bcd2061753a972e292d97d79db5b03048409d1540d09f`。
- RED→GREEN 覆盖 management composer、浮点展示、无表头 Sheet、可见 Evidence、
  正文密度、页码 placeholder、retry 新资产、partial checkpoint 和前端 retry。
- Broad：Backend `626 passed, 7 skipped`；Ruff check/format `383 files`；Frontend
  `23 files / 73 passed` 与 production build；PPT renderer `5 files / 22 passed`
  与 build；Backend golden `5 passed`；Python/Frontend/Renderer dependency audit
  均为 0 known vulnerabilities；`docker compose config --quiet` 通过。
- 核心代码：`backend/app/services/management_presentation.py`、generation/preflight/
  presentation quality/runtime/output services、generation worker、PPT renderer 与
  generation detail UI；同步更新 Compose、脱敏黄金 PPT/manifest、计划、安全、环境和
  pitfalls 记录。
- 私有参考、管理员上传文件、`.playwright-cli/`、`design-system/` 和用户已有旧版
  `docs/ui-mockups/` 均未修改、未暂存。自动化和原生导出是机器验收证据；最终视觉偏好
  仍由用户查看成品后确认。

## Post-Alpha 空 Brief 与 PPT 真实端到端修复（COMPLETE）

### 根因与实现

- 原失败 generation task `019fa780-8b72-74b2-a258-59b52e522e17` 的 Brief
  `facts/inferences/must_include` 均为空；`StructuredBrief` 已改为至少包含一条
  Evidence-backed fact，generation runtime 对 legacy 空 Brief 仍返回稳定
  `generation_brief_content_required`。
- 真实诊断 workflow `019fa7ab-e2e0-7f99-be3a-a77ece77242b` 确认 Agnes 首轮在完整
  JSON 结束前达到 `completion_tokens=8192 / finish_reason=length`。Prompt 和合同现限制
  为代表性摘要：最多 8 facts、4 inferences、4 semantic unresolved items，每项 512 字符、
  8 个 Evidence refs；截断 repair 从完整 Evidence Context 重新生成，不回送截断正文。
  安全日志只记录 attempt、finish reason、token 数和 bounded `loc:type`，不记录 Prompt、
  Provider response 或材料内容。
- PPT renderer 422 的根因是 compiler 允许重复 `evidence_ids`，但 renderer Schema 要求
  `uniqueItems=true`；compiler 现按首次出现顺序去重。后续 renderer 已返回 HTTP 200。
- PPT 在 renderer/持久化成功后仍失败的根因是 pipeline 把 Pydantic
  `PresentationPlan` 交给只接收 renderer payload `dict` 的 quality service；pipeline 现让
  renderer 与 quality 复用同一 `_output_payload`。

### 真实浏览器与 runtime 证据

- 未重复上传，复用管理员已上传且 Manifest valid 的 `第一季度数据.xlsx`。combined
  workflow `019fa7bd-aa3f-76c1-8cfa-0b9569b03559` 的 Brief 首轮成功，16 个单位 blocker
  全部显式选择 `数量（个/件）`。generation task
  `019fa7bf-7ea8-7ab3-aacd-d00759fe3942` 的 XLSX 一次通过；PPTX 在修复前失败，任务为
  `partial_success`，只结算成功 XLSX 的 800。
- 第一处 PPT 修复后，PPT-only workflow
  `019fa7c5-40e0-71e1-982e-494cf2897538` 的 Brief 首轮成功，36 个单位全部选择
  `数量（个/件）`。generation task `019fa7c6-dcbc-762b-834e-2d84a68761cf` 暴露第二处
  quality 输入边界错误；结算 0，预留 800 已完整释放。
- 两处 PPT 修复后，PPT-only workflow
  `019fa7cc-7d45-73ae-bf35-04f3e9070dab` 的 Brief 首轮成功，22 个单位全部选择
  `数量（个/件）`。generation task `019fa7cf-041d-73ce-ac3d-eb146ffe568a` 一次成功：
  `progress=100`、PPTX step `succeeded/attempt=1`、quality `passed`、
  `download_allowed=true`、结算 800。浏览器显示“任务已完成 / 全部文件已通过检查”。
- 三个真实 Brief Provider call 均为 `attempt=1/status=succeeded/is_redacted=1`。最终两个
  成功输出合计结算 1,600；失败任务没有结算，积分流水 reserve/release 成对闭合。

### 下载与文件验证

- `D:\works\codexWorks\download\第一季度数据-销售数据分析.xlsx`：9,878 bytes，1 个工作表，
  OOXML 关键结构完整，SHA-256
  `dc1777ccd095c973059e4e14d8f7839b5a8a141df8cc43fd83a3d8d75b20ec81`，与质量门禁记录一致。
- `D:\works\codexWorks\download\第一季度数据-销售经营汇报.pptx`：105,823 bytes，4 页，
  OOXML 关键结构完整，SHA-256
  `44c5737705ec9856f29cb947d3298fa12df7a64b124e7f6d5d9fb36284b3b01d`，与质量门禁记录一致。

### 验证与 Changed files

- TDD：Brief focused `41 passed`；generation runtime `8 passed`；presentation quality
  `52 passed`。PPT 两个回归均先 RED 后 GREEN。
- Broad：backend 最终从 `backend/` 运行为 `615 passed, 7 skipped`；Frontend `23`
  files / `72 passed`，production build 通过；Ruff check/format 为 `380 files`
  全部通过。一次从仓库根目录误运行 pytest 因未加载 `backend/pyproject.toml` 的 async
  配置产生级联失败，不作为产品回归或通过证据。
- 代码：`backend/app/services/briefs/{contracts,prompting,service}.py`、
  `backend/app/services/generation_runtime.py`。
- 测试：`backend/tests/briefs/{test_contracts,test_prompting,test_service}.py`、
  `backend/tests/generation/test_runtime.py`。
- 记录：`.hermes/plans/2026-07-28-office-ai-empty-brief-e2e.md`、本文件。
- 用户未跟踪的 `.playwright-cli/`、`design-system/`、旧版 `docs/ui-mockups/` 与 ignored
  `output/` 未修改、未暂存。

## 新会话必读

每次会话必须按顺序读取：

1. `AGENTS.md`
2. 本文件
3. `.hermes/plans/office-ai-alpha-tasks/README.md`
4. `docs/prd/2026-07-29-office-ai-agnes-chat-ppt-studio-prd.md`
5. `.hermes/plans/office-ai-agnes-chat-ppt-studio-tasks/README.md`
6. 表格中唯一 `READY` 任务的任务文档
7. `docs/PLAN.md` 及该任务涉及的专题文档
8. `git status --short --branch`

不得只依赖上一会话的聊天摘要。只有前置任务为 `DONE` 的任务才能改为 `READY`。

## 任务状态

| ID | 状态 | Depends on | Commit/证据 |
|---|---|---|---|
| T1-001 | DONE | 无 | `chore(project): establish office ai alpha baseline`；验证证据见下文 |
| T1-002 | DONE | T1-001 | `chore(core): bootstrap frontend backend and database`；Docker runtime 缺口见下文 |
| T1-003 | DONE | T1-002 | `feat(auth): add invite based phone authentication`；Docker runtime 缺口见下文 |
| T1-004 | DONE | T1-003 | `feat(provider): add encrypted multi provider model registry`；验证证据见下文 |
| T1-005 | DONE | T1-004 | `feat(asset): add isolated local asset management`；验证证据见下文 |
| T2-001 | DONE | T1-005 | `feat(parser): add sandboxed office file ingestion`；验证证据见下文 |
| T2-002 | DONE | T2-001 | `feat(evidence): add traceable ocr and evidence manifests`；验证证据见下文 |
| T2-003 | DONE | T2-002 | `feat(terms): add reusable terminology normalization`；验证证据见下文 |
| T2-004 | DONE | T2-003 | `feat(brief): generate evidence grounded structured briefs`；Mock Contract 通过，真实 Agnes 缺口见下文 |
| T2-005 | DONE | T2-004 | `feat(preflight): add brief confirmation and conflict gates`；验证证据见下文 |
| T3-001 | DONE | T2-005 | `feat(task): add durable generation orchestration`；验证证据见下文 |
| T3-002 | DONE | T3-001 | `feat(ppt): add deterministic sales presentation renderer`；验证证据见下文 |
| T3-003 | DONE | T3-002 | `test(ppt): enforce presentation quality gates`；验证证据见下文 |
| T3-004 | DONE | T3-003 | `feat(excel): add deterministic sales analysis workbook renderer`；验证证据见下文 |
| T3-005 | DONE | T3-004 | `feat(generation): complete combined ppt and excel workflow`；Week 3 Gate |
| T4-001 | DONE | T3-005 | `feat(frontend): expose alpha user and admin workflows`；UI V1 与浏览器证据见下文 |
| T4-002 | DONE | T4-001 | `feat(admin): add audited global asset access`；权限、审计与浏览器证据见下文 |
| T4-003 | DONE | T4-002 | `test(golden): validate office generation corpus`；1/10 pilot 与实际 Office 证据见下文 |
| T4-004 | DONE | T4-003 | `test(alpha): record compatibility and recovery drills`；真实 Agnes、Docker/恢复演练与 Office/WPS 证据见下文 |
| T4-005 | DONE | T4-004 | `chore(release): prepare internal office ai alpha`；Week 4 / Alpha Gate |
| P5-000 | DONE | Alpha Complete | `docs(plan): establish agnes chat ppt studio delivery baseline` |
| P5-001 | DONE | P5-000 | `docs(chat): define agnes studio contracts` |
| P5-002 | DONE | P5-001 | `feat(home): show authoritative recent tasks` |
| P5-003 | DONE | P5-002 | 双模型会话、SSE、历史、取消/重连和安全 Markdown |
| P5-004 | DONE | P5-003 | Deck Draft、逐页编辑、Skill、Preflight 与 generation handoff |
| P5-005 | READY | P5-004 | 唯一下一任务：模板目录、缩略图与版本快照 |
| P5-006 | BLOCKED | P5-005 | Agnes 图片资产与 PPT 视觉集成 |
| P5-007 | BLOCKED | P5-006 | Agnes 视频资产与兼容性 Gate |
| P5-008 | BLOCKED | P5-007 | 端到端 Golden、安全、Office/WPS 与发布 Gate |

## T1-001 执行记录

### 范围

- 建立项目级执行规则和 Alpha scope、API、21 张表、环境、安全与进度文档。
- 建立 9 服务 Docker Compose 拓扑和 healthcheck/dependency 边界。
- 保留并纳入已批准的 UI V1 和 20 个 dependency-ordered 任务文档。
- 不启动容器、不实现业务模型/API/UI、不读取本地 `.env`。

### Changed files

- 工程基线：`AGENTS.md`、`README.md`、`docker-compose.yml`、`pitfalls.md`。
- 执行文档：`docs/PLAN.md`、`docs/PROGRESS.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`。
- 批准基线：`.hermes/plans/2026-07-22_000414-office-ai-alpha.md`、`.hermes/plans/office-ai-alpha-tasks/`、`docs/ui-v1/`。
- UI V1 直接引用规格：`docs/ui-mockups/2026-07-22-office-ai-alpha-ui-direction-v3.md`、`docs/ui-mockups/2026-07-22-office-ai-admin-ui-spec.md`。
- 未纳入本任务：`design-system/`、旧版 `docs/ui-mockups/` 进度/方向稿和 ignored `output/`。

### 验证证据

- 官方 Docker Compose standalone v5.1.4：官方 SHA-256 校验通过；`docker-compose -f docker-compose.yml config --quiet` 退出码 `0`。
- `docker-compose -f docker-compose.yml config --services`：通过，解析 `frontend/backend/worker/ppt-renderer/mysql/redis/clamav/paddleocr/libreoffice` 共 9 个服务。
- PyYAML 静态断言：通过；YAML 可解析，9/9 healthcheck、9/9 non-root，`worker` 仅在 internal `private` network 且无 Provider/Master Key 环境变量。
- UTF-8、21 张表连续编号、20 个任务 ID、20 个任务索引链接：通过。
- `git check-ignore -v .env backend/files/example.txt output/example.png golden-data/private/example.xlsx`：通过。
- Secret pattern scan：通过；未发现常见 API token、AWS access key 或 private key header。
- `git diff --check`：通过。
- `git fetch origin` 后 `HEAD...origin/main` 为 `0 0`，提交前没有远端分叉。

### 阻塞与风险

- 本机没有 Docker daemon/Desktop，官方 standalone 只能验证 Compose config；未拉取镜像、未验证镜像可达性或容器 runtime health。该项阻塞后续容器启动验证，`T1-002` 必须在可用 Docker 环境补验，T1-001 未伪造 runtime 通过。
- 真实 Agnes Key、10 组获授权且脱敏的销售材料、Microsoft Office/WPS 分别是后续任务的外部前置条件；不得写入仓库或聊天。

### 完成结论

- T1-001 交付、focused verification、文档记录和单一逻辑 commit 已完成；最终 commit 推送到 `origin/main` 后由当前会话创建 T1-002 新任务。
- T1-001 交接时，T1-002 是唯一 `READY` 任务；该历史交接要求已由下方 T1-002 执行记录闭环。

## T1-002 执行记录

### 范围

- 按批准结构建立 FastAPI、SQLAlchemy 2、Pydantic 2、Redis 与 Alembic skeleton；没有创建任何用户、Provider、资产或任务业务表。
- 提供 `/health/live`、`/health/ready`、Trace ID、结构化 JSON request log、稳定错误 envelope、CORS 和脱敏 dependency status。
- 建立 Vue 3、TypeScript、Vite、Router、Pinia、API client、权限 metadata/guard 与非业务 placeholder shell。
- 将 Backend/Frontend Dockerfile 和 Compose placeholder command 替换为真实应用/test/build entry；保持其余服务边界不变。

### Changed files

- Backend：`backend/pyproject.toml`、`backend/Dockerfile`、`backend/.dockerignore`、`backend/app/**`、`backend/tests/**`。
- Migration：`backend/alembic.ini`、`backend/alembic/**`；初始 Head 为 `20260722_0001`，只建立 Alembic version baseline。
- Frontend：`frontend/package.json`、`frontend/package-lock.json`、`frontend/Dockerfile`、`frontend/.dockerignore`、`frontend/index.html`、`frontend/tsconfig*.json`、`frontend/vite.config.ts`、`frontend/src/**`、`frontend/tests/**`。
- Runtime/记录：`docker-compose.yml`、`README.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/PROGRESS.md`、`pitfalls.md`、T1-002/T1-003 任务状态。
- 未触碰：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`。

### TDD 与 focused verification

- RED：Backend tests 因 `app` 不存在而 collection 失败；Frontend 4 个 suite 因 request/guard/routes/bootstrap 尚不存在而失败；MySQL driver contract 在 `asyncmy -> aiomysql` 切换前按预期失败。
- Backend：`backend/.venv/Scripts/python.exe -m pytest -q`，`8 passed`，无 warning。
- Backend quality：`ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过。
- Frontend：`npm run test`，4 个 test files、`7 passed`；`npm run build` 通过，44 modules transformed，TypeScript 无错误。
- 本机 Uvicorn HTTP smoke：`/health/live` 返回 `200 live`；MySQL/Redis 均不可用时 `/health/ready` 返回脱敏 `503 service_not_ready`，日志含 Trace ID。
- Alembic：`alembic heads` 为 `20260722_0001 (head)`；MySQL dialect `upgrade head --sql` 通过；SQLite in-memory 空库 `upgrade head` 退出码 `0`。SQLite 只验证 migration 机制，不代表 MySQL runtime。

### Dependency 与配置验证

- `pip-audit`：切换到 `aiomysql 0.3.2` 并升级 pytest 后，0 known vulnerabilities；Python license metadata 无 `UNKNOWN`。
- `npm audit --audit-level=high`：0 vulnerabilities；Node lockfile dependency license metadata 无缺失。
- Compose standalone v5.1.4：`config --quiet` 退出码 `0`，仍解析 9 个服务；Backend/Frontend 已指向本任务镜像与真实 healthcheck。

### Docker runtime preflight 与未验证项

- `docker`、`docker-compose` 均不在 PATH；Docker Desktop/daemon 不可用。
- standalone `docker-compose pull mysql redis` 退出码 `1`：无法连接 `npipe:////./pipe/docker_engine`，系统找不到该管道。
- 因此外部镜像 pull、MySQL/Redis container health、真实依赖下 `/health/ready=200`、Docker 内 pytest/Vitest/build 和真实 MySQL 空库 upgrade 均未运行，不标记通过。
- 这是本机环境验证缺口；T1-002 代码、focused verification 与替代性 migration/HTTP evidence 已完成。Docker runtime 可用后必须补跑任务卡原始命令。

### 完成结论

- T1-002 严格范围内的实现、focused/broad 可用验证、dependency gate 和记录已完成；单一逻辑 commit 推送后交接。
- T1-003 是唯一 `READY` 任务；新 Codex 任务必须重新按 `AGENTS.md` 的启动顺序读取文件记录，不得依赖聊天摘要，并继续保留用户未跟踪 UI 资料。

## T1-003 执行记录

### 范围

- 建立 `users`、`user_sessions`、`invite_codes`、`credit_ledger` 模型与 additive migration `20260722_0002`；UUID 使用 `BINARY(16)`，MySQL 时间编译为 `DATETIME(6)`。
- 实现 `+86` 邀请码注册、登录、Refresh rotation、退出、当前用户、修改密码、管理员 reset service policy，以及管理员邀请码创建/脱敏查询 API。
- 密码使用 Argon2id；Access Token 使用 HS256 且关联数据库 Session；Refresh Token、邀请码分别只保存 SHA-256 hash、peppered HMAC hash。
- 注册在单一事务中锁定并消费邀请码、创建用户、追加 `registration_grant`、同步余额；流水写入失败时四项整体回滚。
- 实现 Redis 失败限速、注册/邀请码限速、runtime-only 幂等管理员 Bootstrap；未实现短信、找回、微信、Workspace、T1-004 Provider 能力或 T4-002 audit HTTP 闭环。

### Changed files

- Models/Migration：`backend/app/models/{base,users,user_sessions,invite_codes,credit_ledger}.py`、`backend/alembic/versions/20260722_0002_auth_and_invites.py`、`backend/alembic/env.py`。
- Services/Runtime：`backend/app/services/auth_*.py`、`backend/app/services/rate_limit.py`、`backend/app/core/{application,database,errors,redis}.py`、`backend/app/settings/config.py`、`backend/app/commands/bootstrap_admin.py`。
- API/Schemas：`backend/app/api/v1/{auth,invite_codes}.py`、`backend/app/api/router.py`、`backend/app/schemas/{auth,invites}.py`。
- Tests/Dependencies：`backend/tests/auth/**`、`backend/pyproject.toml`；新增 `argon2-cffi` 与 `PyJWT`。
- Runtime/Docs：`docker-compose.yml`、`README.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md` 与 T1-003/T1-004 状态。
- 未触碰：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`。

### TDD 与 focused verification

- RED：依次确认 auth security/settings、4 个模型与注册事务、Session/rate limit、migration/Bootstrap/HTTP、邀请码管理、失败限速预算、UTC 时间归一化、MySQL `DATETIME(6)` 和空 Secret fail-closed 在实现前按预期失败。
- GREEN：`backend/.venv/Scripts/python.exe -m pytest backend/tests/auth -q`，`36 passed`。
- 注册 rollback test 通过 SQLAlchemy `before_insert` 触发真实流水写入异常，验证 user/ledger 均为 0、invite `used_count` 保持 0。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；无超过 500 行的 Python 文件。

### Broad verification 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`44 passed`。
- Alembic：`heads` 为 `20260722_0002 (head)`；SQLite 临时空库 `upgrade head` 由 test 通过；MySQL dialect `upgrade head --sql` exit `0`，包含 `BINARY(16)`、`DATETIME(6)` 与两条命名外键。
- Compose standalone v5.1.4：`config --quiet` exit `0`。
- `pip-audit`：0 known vulnerabilities；仅按预期跳过本地非 PyPI package `office-ai-backend`。9 个 direct production dependency license metadata 均存在。
- 全套测试曾发现 Alembic `fileConfig` 禁用应用 logger 的全局状态污染；改为 `disable_existing_loggers=False` 后既有 request log regression 通过。

### Docker runtime preflight 与未验证项

- `docker`、`docker-compose` 均不在 PATH，Docker Desktop/daemon 不可用；standalone `pull mysql redis` exit `1`，缺少 `npipe:////./pipe/docker_engine`。
- 任务卡三个命令均已用 standalone Compose 实际尝试：Auth pytest、`alembic upgrade head`、Backend broad pytest 分别 exit `1`，都在容器创建前因缺少 engine pipe 失败。
- 因此真实 MySQL row lock/空库 migration、Redis rate limit/Session runtime、容器内 36/44 tests 与 health 均未验证；SQLite/offline 结果不代表这些 runtime 通过。Docker 可用后必须原样补跑任务卡命令。

### 安全与决策

- Session Secret、Bootstrap 手机号/密码均无源码默认值；Compose 空字符串归一化为未配置，Session Secret 少于 32 字符、Bootstrap 密码少于 12 字符会拒绝。
- token 响应与一次性邀请码响应使用 `Cache-Control: no-store`；错误 envelope 和 request log 不记录 body，不回显密码、邀请码或 Token；限速 Redis key 只含 SHA-256 摘要。
- 管理员 reset 已实现密码 Hash、强制改密和 Session 撤销的 service behavior；为避免绕过 re-auth、reason 和 audit，`/admin/users/{id}/reset-password` HTTP 端点留给 `T4-002`，未暴露半成品敏感接口。

### 完成结论

- T1-003 严格范围内实现、focused/broad 可用验证、dependency gate、环境缺口与文档记录已完成；单一逻辑 commit 推送后交接。
- T1-004 是唯一 `READY` 任务；新会话必须重新按 `AGENTS.md` 启动顺序核对 current Git/runtime 状态，不得提前进入 T1-005。

## T1-003 本机 Runtime 补验

### 授权与范围

- 用户明确授权本次执行在进程内读取项目 `.env`，使用其中 MySQL 连接信息创建目标 database 和表结构；所有 Secret 均未回显、写入文档或提交。
- 本补验没有进入 T1-004，只修正 T1-003 的 direct Windows runtime、现有 `.env` 变量兼容和认证 schema 中文 COMMENT。
- 未修改历史 migrations `20260722_0001`/`20260722_0002`，新增 additive `20260722_0003_auth_schema_comments.py`。

### Runtime 调查与根因

- Windows services：`MySQL80`、`Redis` 均为 `Running / Automatic`；3306/6379 均监听并可连接。
- MySQL：8.0.43，`.env` 凭据认证成功且目标 database 原先不存在。
- Redis：Windows Redis 3.0.504，启用 `requirepass`；无认证返回 `NOAUTH`，从 service config 临时注入认证后 `PING=True`。
- 先前 runtime 缺口的根因是只检查 Docker；同时 `.env` 使用 `OFFICE_AI_DB_*`，Settings 只接受 canonical MySQL变量，且 `.env` 没有 Redis URL。

### 实现与数据库结果

- Settings 使用 `AliasChoices` 兼容 `OFFICE_AI_DB_HOST/PORT/NAME/USER/PASSWORD`，canonical变量仍优先；应用仍不自动读取 `.env`。
- 4 个 ORM tables 和全部 columns 增加中文 comment；ORM unique constraints/indexes/FKs 与历史 `20260722_0002` 精确对齐。
- 使用授权连接创建目标 database，字符集 `utf8mb4`、collation `utf8mb4_0900_ai_ci`；真实 Alembic upgrade 从 base 运行到 `20260722_0003`。
- `information_schema`：4/4 table comments、41/41 column comments 非空；`alembic current=20260722_0003`，`alembic check` 为 `No new upgrade operations detected`。

### 验证

- TDD RED：DB alias、ORM中文 comments、Alembic 0003/offline COMMENT、constraint/index/FK 对齐测试均在实现前按预期失败。
- Focused：`backend/.venv/Scripts/python.exe -m pytest backend/tests/auth -q`，`41 passed`。
- Broad：Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`，`49 passed`。
- Quality：`ruff check app tests alembic`、`ruff format --check app tests alembic` 均通过。
- Live readiness：使用 `.env` MySQL配置并临时注入 Redis认证 URL，`GET /health/ready` 返回 `200 ready`，dependencies 为 `mysql=up`、`redis=up`。
- Redis `INFO server` 因旧 Windows build 输出含非 UTF-8 本机路径而与新版 redis-py 解码不兼容；不影响 authenticated PING 和 readiness，本项不伪装为 INFO 通过。

### Runtime 本地配置闭环

- 用户后续明确授权编辑本项目 `.env`；先按无认证默认 URL 验证得到 `503`、`mysql=up`、`redis=down`，与 Redis CLI 的 `NOAUTH` 一致。
- 用户提供的候选 Redis Secret 经仅进程内 authenticated `PING` 验证成功；随后只在 ignored `.env` 中配置默认 `127.0.0.1:6379` 的认证 URL，未改动 Windows Redis service config。
- 重新加载 `.env` 后，真实 `GET /health/ready` 返回 `200 ready`，dependencies 为 `mysql=up`、`redis=up`；Secret 未写入 tracked files、暂存区、日志或本文档。

### Changed files 与交接

- Backend：`backend/app/settings/config.py`、认证 4 个 model files、`backend/alembic/versions/20260722_0003_auth_schema_comments.py`、相关 auth tests。
- Records：T1-003 task、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- `.env` 已在用户明确授权下写入本机 Redis URL，保持 ignored 且未暂存；`design-system/` 和旧版 `docs/ui-mockups/` 继续保留为用户未跟踪文件。
- T1-004 仍是唯一 `READY` 任务；新会话必须从 `AGENTS.md`、本文件、任务索引、T1-004 任务卡和专题文档重新读取事实，不得仅依赖聊天交接。

## T1-004 执行记录

### 范围

- 建立 `ai_providers`、`provider_credentials`、`ai_models`、`audit_logs` ORM 与 additive migration `20260722_0004`；当前实现 8/21 张 Alpha 表。
- 实现管理员 Provider/Credential/Model 创建、列表和白名单 PATCH，Credential health test、重新认证 Reveal、成功/失败审计，以及用户 active/visible 模型列表。
- API Key 使用随机化 Fernet 应用层密文，只持久化密文和 SHA-256 fingerprint；同 Provider fingerprint 唯一，Model 明确绑定 Provider 与 Credential ID。
- 实现 Agnes Adapter 七项固定合同：`validate_configuration`、`test_authentication`、`test_structured_output`、`test_image_url`、`create_chat_completion`、`classify_error`、`extract_usage`。
- 固定 Agnes 默认 Base URL、`agnes-2.0-flash`、保守 `256K` Context 和 120 秒 timeout；本地/私网图片 URL 在请求前拒绝，未实现 T1-005 资产能力。

### Changed files

- Models/Migration：`backend/app/models/{ai_providers,provider_credentials,ai_models,audit_logs}.py`、`backend/alembic/versions/20260722_0004_provider_model_registry.py`、model registry。
- Provider/Services：`backend/app/providers/agnes.py`、`backend/app/services/provider_{security,contracts,admin}.py`、Settings/Application/Error wiring。
- API/Schemas：`backend/app/api/v1/providers.py`、router、`backend/app/schemas/providers.py`。
- Tests/Dependency：`backend/tests/providers/**`、`backend/tests/admin/**`、auth migration chain test、`backend/pyproject.toml`；`httpx` 进入 production dependencies，`cryptography` 固定为已修复的 `>=48.0.1,<49`。
- Records：T1-004/T1-005 task cards、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env` 或真实 Provider Key。

### TDD 与 focused verification

- RED：依次确认 Master Key/cipher、四个 ORM、migration、Credential 密文/重复拦截、Reveal 双向审计、Registry/Model 绑定、Agnes 七项合同、Credential health、Admin HTTP contract、安全列表/PATCH 和 Agnes 配置写入验证在实现前按预期失败。
- REFACTOR：将 Provider DTO/summary/factory 拆到 `provider_contracts.py`，service 498 行；Provider 测试按 health/registry 边界拆分，全部 Python 文件不超过 500 行。
- `backend/.venv/Scripts/python.exe -m pytest tests/providers -q`：`33 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/admin -q`：`2 passed`。
- Mock Contract Test 覆盖 Agnes chat payload、structured output、usage、公开图片 URL gate 与 `400/401/403/429/5xx/timeout` 分类；没有使用或读取真实 Agnes Key，不声称真实 Agnes 兼容已验证。

### Broad、quality 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`84 passed`。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；全套 pytest 曾暴露 auth/providers 同名 test module collection 冲突，增加 package marker 后闭环。
- `alembic heads`：`20260722_0004 (head)`；SQLite 空库 upgrade、MySQL dialect offline 中文 COMMENT 与两项关键唯一约束测试通过。
- `pip check` 通过；首次 `pip-audit` 发现 `cryptography 45.0.7` 已知漏洞，提升到 `48.0.1` 后复跑为 `0 known vulnerabilities`，只按预期跳过本地非 PyPI package。

### 真实 MySQL/Redis Runtime

- 通过用户授权的本机 ignored `.env` 仅向子进程注入 MySQL/Redis 配置，真实 MySQL 从 `20260722_0003` 升级到 `20260722_0004`；`alembic current` 为 Head，`alembic check` 为 `No new upgrade operations detected`。
- `information_schema` 验证 4/4 新表 table comments、52/52 column comments 非空，两项关键唯一约束存在。
- 真实 MySQL transaction probe 使用子进程临时 Master Key 写入 Provider/Credential/Model/Audit 后整体 rollback；验证密文不含 probe plaintext、同 Provider fingerprint 重复写入被唯一约束拒绝、Model 绑定正确，未留下 probe 数据。
- 使用临时进程 Master/Session key 装配真实应用，`GET /health/ready` 返回 `200 ready`，dependencies 为 `mysql=up`、`redis=up`，Provider service 配置成功并通过 lifespan 正常关闭。
- Docker CLI 仍不在 PATH，`docker compose version` 为 command not found；任务卡三个 Compose 入口未运行，不标记容器验证通过。direct Windows focused/broad 与真实 MySQL/Redis 证据不冒充 Docker runtime。

### 安全与决策

- Master Key 缺失/空值/无效时 Provider service fail closed；Master Key 无源码默认值，不落库。常规 Credential 列表固定掩码且不 decrypt，metadata PATCH 不能替换 Key/Fingerprint；轮换以新 Credential ID 和 `rotation_source` 完成。
- Provider 非敏感 JSON config 递归拒绝 `api_key`、Token、密码、Secret、Master Key、Authorization 和 Credential 字段；Credential schema/service 双层拒绝空白 Key，防止绕过专用密文边界。
- Reveal 要求管理员 Session、当前密码和 reason，响应 `Cache-Control: no-store`，成功/失败均只记录脱敏 audit context；Credential test 受 Redis 限速并审计，`401/403` 暂停 Credential，timeout 返回不确定且不自动重试。
- `400` 不重试，`429/5xx` 标记有限重试类别；用户模型查询同时过滤 Provider、Credential、Model active 与 `user_visible`，不静默切换 Provider。

### 完成结论

- T1-004 严格范围内的实现、TDD、focused/broad、真实 MySQL/Redis runtime、dependency/security gate 和文档记录已完成；单一逻辑 commit 推送后闭环。
- T1-005 是下一唯一 `READY` 任务；本会话没有实现 Project、Asset、上传、文件存储或任何 T1-005 代码。

## T1-005 执行记录

### 范围

- 建立 `projects`、`file_assets` ORM 与 additive migration `20260722_0005`；当前实现 10/21 张 Alpha 表。
- 实现用户 Project 创建、列表、改名/归档、空项目软删除，以及无显式项目上传时自动创建默认项目。
- 实现 Local Storage Adapter：固定 `users/{user_id}/quarantine/{asset_id}/original.{ext}`，按 1 MiB chunk 写入、增量 SHA-256、大小 gate 和具体资产目录清理。
- 实现单文件 multipart 上传、扩展名/MIME/minimal signature 初检、Quarantine、幂等重放、资产列表/详情/preview/download/删除与父版本引用检查。
- 实现 owner-scoped 用户 HTTP API 与管理员 service-level role + reason + audit 读取边界；未提前暴露 T4-002 的管理员资产 HTTP/re-auth/delete 闭环，未做 ClamAV、深度 Office/PDF 解析、OCR、OSS 或 Outbox。

### Changed files

- Models/Migration：`backend/app/models/{projects,file_assets}.py`、model registry、`backend/alembic/versions/20260722_0005_projects_and_file_assets.py`。
- Storage/Services：`backend/app/storage/local.py`、`backend/app/services/{asset_contracts,asset_management,asset_uploads}.py`、Settings/Application/Error wiring。
- API/Schemas：`backend/app/api/v1/assets.py`、router、`backend/app/schemas/assets.py`。
- Tests/Dependency：`backend/tests/assets/**`、`backend/tests/security/**`、provider migration chain test、`backend/pyproject.toml`；新增 `python-multipart>=0.0.20,<1`。
- Runtime/Records：`docker-compose.yml`、task README、T1-005/T2-001 task cards、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret 或用户文件。

### TDD 与 focused verification

- RED：模型/migration、Local Storage、service ownership/idempotency/audit/delete、HTTP/settings、12-byte signature probe、Unicode control filename 和 Compose limit contracts 均先观察到目标能力缺失或错误行为后再实现。
- `backend/.venv/Scripts/python.exe -m pytest tests/assets -q`：`56 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/security -q`：`10 passed`；覆盖不可变 UUID key、路径穿越/伪造 key、大小溢出清理、partial/cancellation cleanup、cleanup failure cause、只删除具体资产目录和物理删除失败显式上报。
- 跨用户 get/open 返回同一 `asset_not_found` 404；管理员独立读取写入不含 `storage_key` 的 `asset.admin_read` audit。
- 独立 pre-commit review 首轮发现物理删除静默失败、PATCH null、project state race、默认项目并发和非 IntegrityError orphan file 五项阻断；新增 10 个定向测试先 `10 failed`，最小修复后 `10 passed`，随后 focused/broad 全绿。
- 第二轮独立 review 发现 multipart parser 前缺少 request body bound、partial write 仍有 silent cleanup 两项阻断；最终 auto-fix cycle 的 10 个定向测试先 RED，修复后 `10 passed`，新增 pre-parser ASGI gate 与显式 `quarantine_cleanup_failed`。
- 最终 review 的三项 blocker 由 8 个新回归测试复现为 `8 failed`：未认证上传先进入 multipart parser、`CancelledError` 留下 22-byte partial、写文件前无 durable checkpoint、cleanup 覆盖 signature 主因及 finalization failure 无追踪记录。修复后同组 `8 passed`。
- 独立 re-review 继续发现已完成 idempotency replay 仍进入 multipart parser/spool，以及 cleanup failure 在 HTTP 主异常位置遮蔽 signature/cancellation。新增 5 个定向断言先得到 `3 failed, 1 passed`（随后修正两个误改/缺 header 的 test maintenance 问题），改为 endpoint pre-form replay lookup、original-error-first marker/note、`deleting` checkpoint 与脱敏 recovery log 后 `5 passed`；最终 assets/security 合并 `53 passed`。
- 第二次 re-review 发现多 chunk 低报长度会在 parser 已滚盘后用 disconnect 中止并留下未关闭 spool，且 generic/direct/cancellation recovery log 覆盖不全；额外 multipart 文件也未拒绝。新增 5 个用例先 `5 failed`，改为 middleware 受控 preflight spool、middleware completed replay、统一 recovery logger 和严格单文件 form 后同组 `5 passed`，含 replay 回归共 `6 passed`；最终 assets/security 合并 `58 passed`。
- 第二次 auto-fix 后的最终 re-review probe 确认上述 parser spool、completed replay、direct/generic/cancellation logging 与严格 form blocker 均闭环，但发现 `_finalize_checkpoint` 在 commit 主异常/`CancelledError` 后的 `session.rollback()` 若再抛异常，会覆盖主因且没有 `recovery_failure` marker、安全 note 或 recovery log；fault probe 得到最终 `OSError` 而非原 `CancelledError`。该项阻止 commit。
- 新 goal continuation 重新启用 strict TDD/review workflow；独立 fix agent 对 finalization commit `RuntimeError`/`CancelledError` + rollback `OSError` 组合新增参数化 fault test，先得到 `2 failed`，再将 rollback failure 转为 primary 上的 `recovery_failure=True` 与仅含 `OSError` 类型的安全 note，原样重抛 primary 后 `2 passed`。主 agent 复跑同组、assets/security 与 broad 均通过。
- Fresh reviewer 发现并发相同 key 会把首请求尚未完成的 `uploaded` checkpoint 当作 201 replay，且 unique `IntegrityError` fallback 同样误判。独立 fix agent 新增 service 并发 signature/stream failure + later retry、真实 middleware `uploaded`/`deleting` 零 receive/零 upload 409、unique race 三组参数化用例，先得到 service `4 failed`、HTTP `2 failed`；统一 replay policy 后分别 `4 passed`、`2 passed`，完整 assets 为 `56 passed`。
- 修复后独立 re-review 重新读取 39 个 staged 文件并复跑 incomplete replay、fault recovery、assets/security/broad 与 quality gates，确认普通 lookup、middleware、unique race fallback 和文档一致性全部闭环，结论为 `PASS`，无新增 security/logic blocker。

### Broad、quality、migration 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`150 passed`。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；全部 Python 文件不超过 500 行。
- `alembic heads`：`20260722_0005 (head)`；SQLite 空库完整 upgrade、active default/storage location/user idempotency 三个唯一约束、中文 COMMENT 和 MySQL dialect offline `upgrade head --sql` 通过。
- `pip check` 通过；`pip-audit` 为 `0 known vulnerabilities`，仅按预期跳过本地非 PyPI package；12 个 direct production dependency license metadata 无缺失。

### Runtime 缺口与证据边界

- 任务卡三条命令已逐条实际执行：assets、security、broad Docker pytest 都因 PowerShell `docker` command not found 在容器创建前 exit `1`；不标记容器 runtime 通过。
- Direct Windows focused/broad、SQLite migration、MySQL offline DDL 和 `tmp_path` 受控文件 I/O 通过；这些证据不冒充 Docker volume/non-root 或真实 MySQL `0005` runtime upgrade。
- 当前会话遵守项目规则，未读取 ignored `.env`；因此没有使用已有数据库 Secret 运行真实 MySQL migration。Docker 或经用户明确授权的 Secret 注入环境可用后，应补跑 Compose 原始命令与真实 `alembic upgrade head/check`。

### 安全与决策

- 客户端不能提交或获得磁盘路径/`storage_key`；结构化 key 必须解析为指定 owner/asset UUID 且仍位于受控 root。
- 文件名使用 NFKC、basename、255 字符和 Unicode control category 清理；binary signature 只读取 12-byte header，不把最大 50 MB 文件整体加载内存。
- 用户/幂等键唯一约束与 application lookup 共同保证已完成 replay 在 `request.form()` 前返回；`uploaded`/`deleting` incomplete replay 则稳定返回 `409 asset_upload_in_progress`，两者都保持零 body receive/parser/spool/service upload。普通 lookup 与 unique race fallback 共用 replay policy；signature/stream cleanup 成功删除 checkpoint 后，同 key later retry 可重新成功。storage location 另有唯一约束，文件二进制不进入 MySQL。
- preview/download 使用 `private, no-store`、`nosniff`，preview 额外 `CSP sandbox`；资产保持 `quarantined`，T2-001 完成 ClamAV/深度类型/容量/解析前不得进入 `ready`。
- upload gate 在 body receive 前验证 Bearer Session 与 replay policy；新请求进入 middleware 自有 1 MiB threshold preflight spool，只有声明/实际长度一致且不超过 `max_file_bytes + 64 KiB` 才 replay 给 parser。拒绝路径不创建 parser spool，preflight spool 始终关闭；未认证/completed replay/incomplete conflict 均不消费 body。
- 项目删除当前只允许空项目；资产删除按 `deleting -> deleted` 并检查活动父版本引用。未来 `generation_task_inputs` 建立后必须把历史生成引用加入同一 delete gate。
- 每个用户的活动默认项目通过 generated owner key 唯一约束；上传在文件 I/O 前提交 `uploaded` checkpoint，最终事务锁定并重验 project 后更新 `quarantined`。finalization 异常/cancellation 保留 checkpoint 与具体 storage key，文件始终可恢复追踪。物理删除失败保留 `deleting` 并返回 `asset_delete_failed`，不静默标记成功。
- stream/open/write 失败后的 partial quarantine cleanup 不使用 `ignore_errors`；目录已不存在保持幂等，其他清理失败保留原始 signature/size/stream/cancellation 主因，并以安全 note/marker、`deleting` checkpoint 和脱敏 `asset_recovery_failed` 日志记录恢复失败。人工/适配器直接抛出的 `quarantine_cleanup_failed` 仍稳定翻译，service 不做会覆盖它的二次删除。

### 完成结论

- 最终 review 与两次 re-review 的 parser/replay/storage blocker 已完成 TDD remediation：pre-auth/completed replay 都发生在 receive 前；受控 preflight spool 在 parser 前完整验证并关闭；文件 I/O 前持久化 `uploaded` checkpoint；Local Storage cleanup 保留原始错误、可恢复状态与 direct/generic/cancellation 脱敏日志。
- 当前 direct Windows evidence：assets `56 passed`、security `10 passed`、broad `150 passed`；Ruff check/format、Alembic single head/offline SQL、`pip check`、`pip-audit`、`git diff --check` 均通过。Docker 仍为 command not found，不冒充容器 runtime evidence；未读取 ignored `.env`，未运行真实 MySQL `0005` upgrade。
- T1-005 已通过独立 pre-commit re-review、focused/broad/quality/migration/dependency 与敏感信息门禁；状态与依赖链已收口为 `DONE`，T2-001 是唯一 `READY` 任务。新会话必须按“新会话必读”顺序重新读取文件记录后再实现 T2-001。

## T2-001 执行记录

### 范围

- 建立 Quarantine 资产的完整性复核、ClamAV `INSTREAM` fail-closed 扫描、安全类型/容量门禁、隔离 parser 与结构化输出存储；未新增用户 HTTP API、Evidence Manifest、OCR、Agnes、Redis Outbox 或积分路径。
- 支持 DOCX、PDF、XLSX、CSV、TXT、MD 的版本化结构化结果；XLSM 只读取安全数据并标记宏未执行；PNG/JPG/JPEG/WEBP 通过完整性和解码预算后只生成 `pending_ocr`。
- 拒绝 XLS/PPTX、伪装 MIME、病毒、加密/密码保护、损坏、Zip Bomb、危险 OOXML、DTD/entity、超限文件/PDF/Excel/Archive/结构、不可解码或膨胀图片。
- 持久化 `quarantined -> scanning -> parsing -> ready/rejected`、parser metadata、warnings、稳定错误码和 deterministic parsed-output recovery key；20 文件/200 MiB batch contract 在 claim/scan 前 fail-fast。

### Changed files

- Model/Migration/Schema：`backend/app/models/file_assets.py`、`backend/alembic/versions/20260723_0006_file_processing_metadata.py`、`backend/app/schemas/assets.py`、`backend/app/services/asset_contracts.py`。
- File safety：`backend/app/services/file_safety/` 下 ClamAV client、limits/contracts、深度 validation、安全 parsers、可终止 parser runtime 与 parsed output store。
- Worker/Runtime：`backend/app/workers/asset_processing/`、`backend/app/settings/config.py`、`docker-compose.yml`；worker 使用只读输入 volume、独立限额输出 volume、只读 root、tmpfs、non-root、resource limits 和 internal network，且不挂载 Provider/Master Key。
- Tests/Dependencies：`backend/tests/file_safety/`、`backend/tests/parsing/`、相关 asset/provider migration tests、`backend/pyproject.toml`；新增 `pypdf>=6.14.2,<7` 与 `Pillow>=12.3,<13`。
- Records：T2-001 task card/index、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏黄金材料。

### TDD 与 focused verification

- 首轮按 contracts、ClamAV、各格式真实最小样本、worker state machine、output recovery 和 Compose/settings contract 分组先观察 RED，再最小实现转 GREEN。
- 首次独立 review 发现 delimiter-only CSV/Office 结构预算与 parser timeout、stale processing、截断图片、batch gate 未接入四类 blocker；修复前定向回归为 `13 failed, 36 passed`，随后图片强化 `2 failed`、Windows spawn entrypoint `1 failed`、DOM 前预算/真实 decode/lease 配置 `4 failed`，均完成 GREEN。
- 第二次独立 review 发现 output 落盘后、DB 完成前 hard crash 会留下无 recovery key 的 orphan，以及 API error-code contract 不完整；新增两项定向测试先 `2 failed`，写前 durable deterministic key checkpoint、unknown-code fail-closed registry 和文档 contract 后 `2 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/file_safety -q`：`27 passed`。
- `backend/.venv/Scripts/python.exe -m pytest tests/parsing -q`：`60 passed`；focused 合并为 `87 passed`。
- 最终独立 pre-commit re-review 复核 crash recovery、stale key、稳定错误码和 staged diff，结论 `PASS`、无 findings。

### Broad、quality、migration 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest -q`：`238 passed`。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 均通过；全部 Python 文件不超过 500 行。
- `alembic heads`：`20260723_0006 (head)`；processing migration 定向测试 `3 passed`，MySQL dialect offline `upgrade head --sql` 生成通过。
- Compose/settings 静态 contract tests 通过：worker 无 Provider/Master Key、输入只读、输出独立且限额、无 external network；这些静态证据不冒充容器 runtime。
- `pip check` 通过；`pip-audit` 为 `0 known vulnerabilities`，仅按预期跳过本地非 PyPI package；14 个 direct production dependency license metadata 无缺失。
- `git diff --cached --check`、staged added-line secret/dangerous-call scan、binary scan 和禁止路径检查均通过；未发现 Secret signature、危险动态执行、新增二进制或用户 UI 资料。

### Runtime 缺口、风险与决策

- 任务卡四条 Docker 命令已逐条实际执行：`docker compose up -d clamav`、file-safety、parsing、backend broad 均因 PowerShell `docker` command not found 在容器创建前 exit `1`；不标记 ClamAV/Compose/non-root/volume runtime 通过。
- Direct Windows focused/broad、SQLite migration contract、MySQL offline DDL 与 `tmp_path` 受控文件 I/O 通过；未读取 ignored `.env`，因此未运行真实 MySQL `0006` upgrade。
- Parser 在 spawned child process 中受 wall-clock timeout，Office XML 在 DOM 前受 member/总结构预算，图片受 bounded structural validation、decoded-size gate 与 Pillow full decode；感染、服务异常、timeout、parser crash 和未知错误码全部 fail closed。
- `scanning/parsing` 超过至少 300 秒且覆盖 scan/parser timeout 与 I/O 余量的 lease 后稳定拒绝；本任务选择安全拒绝而不是自动重试。极慢 I/O 超过 lease 仍会 rejected，未来若引入多 worker 长任务恢复，应增加 owner/heartbeat lease，不在 T2-001 提前实现 T3 orchestration。
- Output write 前先持久化 deterministic recovery key；hard crash 后 stale reconciliation 保留精确 key，不形成不可追踪 orphan。自动物理删除留给后续受审计 recovery，避免与并发恢复误删。

### 完成结论

- T2-001 严格范围内的实现、TDD、两轮独立 review remediation、focused/broad/quality/migration/dependency 与敏感信息门禁已完成；Docker 和真实 MySQL runtime 缺口已如实记录。
- T2-001 以单一逻辑 commit 推送后收口为 `DONE`；T2-002 是下一唯一 `READY` 任务，本会话未实现任何 OCR 或 Evidence Manifest 代码。

## T2-002 执行记录

### 范围

- 建立 internal PaddleOCR HTTP service/client，将图片 OCR 与 T2-001 解析结果统一转换为版本化 `evidence-manifest.v1`；本任务只生成 `source_fact`，不生成 Agnes 推断、`calculated_fact` 或 `ai_inference`。
- 证据位置覆盖 Excel cell、PDF page/BBox、Word paragraph、CSV cell、text line 与 image OCR BBox；每条证据绑定资产 UUID、`sha256:` 版本、原始/标准化值、单位/币种、置信度及 parser/OCR engine 版本。
- 叙述 OCR `<0.75` 产生 warning；数字 OCR `<0.90` 或数字单位未知产生 calculation blocker；冲突币种/单位不做猜测。
- Manifest 写入前持久化 deterministic intended key 与 `building`，严格 Pydantic/JSON Schema 校验后原子落盘，再条件更新为 `valid/ready`；暂时性 OCR 错误按 30/60 秒 backoff 最多 3 次，清理失败或非法 Manifest 均 fail closed。
- 未实现 T2-003 术语库、来源冲突裁决、T2-004 Agnes/Structured Brief、用户证据读取 API 或后续任务能力。

### Changed files

- OCR：`backend/app/services/ocr/`、`backend/ocr-service/Dockerfile`、Compose `paddleocr` service 与 worker OCR 配置。
- Evidence：`backend/app/services/evidence/`、`backend/scripts/export-evidence-schema.py`、`backend/tests/evidence/`。
- State/Model：`backend/app/workers/asset_processing/`、`backend/app/models/file_assets.py`、`backend/alembic/versions/20260723_0007_evidence_manifest_metadata.py`、asset safe-response contracts。
- Parser fidelity：Excel 原 cell、PDF combined transform BBox、Word 原 paragraph index、`backend/app/services/file_safety/pdf_geometry.py` 及对应 tests。
- Deletion lifecycle：owner-scoped 删除同时覆盖原文件、parsed output 与 Manifest；active `scanning/parsing` writer 返回 `409 asset_processing_in_progress`，派生清理失败保留可重试 `deleting`。
- Runtime/Records：`backend/app/settings/config.py`、`backend/app/core/application.py`、`docker-compose.yml`、任务卡/索引、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏黄金材料。

### TDD、review 与 focused verification

- RED：OCR/evidence tests 首次 collection 因目标 modules 不存在而失败；随后按 client/server、Manifest schema/location/confidence/store、worker retry/recovery、migration 与 Compose contract 分组转 GREEN。
- 深度 pre-commit review 发现并修复：Manifest source expansion 内存放大、冲突币种误归一、Word 空段落位置漂移、PDF matrix 未组合、OCR health 早于模型 readiness、历史 migration test 固定最新 head、资产删除遗漏派生输出，以及 active worker/delete race。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/ocr -q`：`10 passed`。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/evidence -q`：`11 passed`。
- OCR/evidence/parsing/assets 邻接回归在删除生命周期修复前为 `142 passed`；最终 broad 覆盖全部新增 fault-injection 与 race tests。

### Broad、quality、migration 与 dependency gate

- Backend 根目录 `.venv/Scripts/python.exe -m pytest backend/tests -q`：最终 `265 passed`。
- `ruff check backend/app backend/tests backend/alembic` 与 `ruff format --check backend/app backend/tests backend/alembic` 均通过；项目 Python 文件不超过 500 行。
- `alembic heads`：`20260723_0007 (head)`；Evidence migration SQLite 空库 upgrade 定向 `2 passed`；MySQL dialect offline `upgrade head --sql` 退出码 `0` 并生成 Evidence fields/`DATETIME(6)`。
- `pip check` 通过；Backend `pip-audit` 为 `0 known vulnerabilities`，仅按预期跳过本地非 PyPI package。独立 pinned requirements 对 `paddleocr==3.7.0` 与 `paddlepaddle==3.1.1` 的 audit 均为 `0 known vulnerabilities`。
- JSON Schema export 与 checked-in schema byte-for-byte 一致；Compose/settings contract 证明 OCR 仅在 internal network、non-root/read-only/resource-limited，worker 输入只读、parsed/evidence 输出独立且 bounded，backend 仅为鉴权删除挂载派生 volume。

### Runtime 缺口与证据边界

- 任务卡四条 Docker 命令均已实际尝试；`docker` 与 `docker-compose` 均为 `NOT_FOUND`，在容器创建前失败，因此不标记 PaddleOCR build/model warmup/首图 inference、private network、non-root volume 或 Compose broad runtime 通过。
- Direct Windows focused/broad、SQLite migration、MySQL offline DDL 与 `tmp_path` 原子文件 I/O 通过；未读取 ignored `.env`，未使用本机 Secret，因此没有运行真实 MySQL `0007` upgrade。这些替代证据不冒充 Docker 或真实 MySQL runtime。
- PaddleOCR image 固定 PaddlePaddle `3.1.1`、PaddleOCR `3.7.0` 与 PP-OCRv5 mobile det/rec；模型在 build 阶段预热到 non-root cache，runtime readiness 先构造 engine，再开放 HTTP。Docker 可用后必须补跑任务卡命令和真实首图 inference。

### 安全与决策

- OCR client 只调用 `http://paddleocr:8080`，请求/响应/item 均有预算；网络、timeout、HTTP、JSON/schema、response/item 超限返回稳定错误且不生成证据。
- Manifest 每资产最多 10000 条 evidence，并在 Pydantic object expansion 前执行预算；存储 key 只允许 exact owner/asset UUID path，MySQL 不保存内容、物理路径或用户可见 hash。
- worker 在 Manifest 文件写前提交 intended key；成功条件是 parser、Schema、atomic write 与最终 DB conditional update 全部通过。cleanup 失败保留 exact recovery key；stale processing 标记 `invalid/rejected`。
- 用户删除只按数据库 exact keys 清理原文件、解析结果与 Manifest，不扫描 broad root；`scanning/parsing` 期间拒绝删除，消除 worker 在 `deleted` 后重新写出 orphan 的 race。任一物理清理失败都保留 `deleting`，fault-injection 证明后续重试可完成。
- 历史 migration tests 只验证自身 revision 位于唯一连续链路；只有 T2-002 当前 migration test 固定 `0007` head，避免正常后续 additive migration 制造伪回归。

### 完成结论

- T2-002 严格范围内的实现、TDD、深度 security/architecture/adversarial review remediation、focused/broad/quality/migration/dependency 与文档同步已完成；Docker 与真实 MySQL runtime 缺口已如实记录。
- T2-002 以单一逻辑 commit 推送后收口为 `DONE`；T2-003 是下一唯一 `READY` 任务，新会话必须重新按“新会话必读”顺序读取 live Git 与文档，不得依赖聊天摘要。

## T2-003 执行记录

### 范围

- 建立 owner-scoped 个人术语库与项目覆盖；`library_id`、`item_id` 跨版本稳定，每次库/条目 mutation 写入新的不可变库 version 和完整条目 snapshot。
- `/api/v1/term-libraries` 与 items 子资源提供 create/list/get/update/delete；默认只返回当前用户最新 active snapshot，显式 `version` 可读取历史版本，删除只追加 tombstone。
- `terminology-normalization.v1` 确定性处理数字、百分比、CNY/USD、万/亿倍率、销售数量单位与绝对日期；缺少年份、未知单位、显式 unit/currency 冲突或同优先级别名歧义返回 unresolved。
- 项目规则只覆盖同一用户同一项目的全局匹配；同一事实多来源标准化值不一致生成 `source_conflict` 并要求权威 evidence ID，不按顺序或数值静默裁决。
- `NormalizedEvidenceItem` 保留 source fact 的 asset/version/location/raw/parser/OCR provenance，只附加 canonical term、normalized value、规则版本和术语库 snapshot 引用；不改写 `evidence-manifest.v1`。
- 未实现 T2-004 Skill、Agnes、Structured Brief、Brief persistence 或 Preflight。

### Changed files

- Model/Migration：`backend/app/models/term_libraries.py`、`term_items.py`、model exports 与 `20260723_0008_terminology_snapshots.py`。
- Service/Contracts：`backend/app/services/terminology/` 的 immutable snapshot service、contracts、normalizer、validation 与稳定 operation error。
- API/Wiring：`backend/app/api/v1/term_libraries.py`、`backend/app/schemas/terminology.py`、router/application/error handler wiring。
- Tests：`backend/tests/terminology/` 的 normalization、Evidence、service、API、migration/权限覆盖；历史 Evidence migration test 改为验证 `0007 -> 0008` 连续链，不再错误固定旧 Head。
- Records：T2-003/T2-004 task cards、task index、`docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧版 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏黄金材料。

### TDD 与 focused verification

- RED 1：纯规则测试因 `app.services.terminology` 不存在而 collection fail；最小实现后发现整数 `2500` 被错误去掉尾零，修复 Decimal canonical formatting 后转 GREEN。
- RED 2：service/migration 测试因 `term_items`/`term_libraries` 不存在而 collection fail；实现 owner scope、project ownership、不可变 snapshot 与 `0008` 后转 GREEN。
- RED 3：API 测试因 `create_app` 缺少 terminology wiring 而 `TypeError`；补 schema/router/error/application 后转 GREEN。
- RED 4：派生 Evidence 测试因 `normalize_evidence_item` 不存在而 collection fail；实现保留 provenance 的派生 contract、unit hint 与显式冲突阻断后转 GREEN。
- 自审新增“`1.2万` + CNY 术语 unit”回归，先观察 `1.2 != 12000` 的预期失败，再把万/亿拆为已知倍率与待解析基础单位后转 GREEN。
- 主会话 staged review 新增 4 个定向 RED：同 canonical term 但 unit/口径不一致的最高优先级候选不得择一；术语 unit 成功补齐后必须移除 `numeric_unit_unknown`，但保留独立 `ocr_numeric_low_confidence` blocker。最小修复后均转 GREEN。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/terminology -q`：`29 passed`。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/evidence -q`：`11 passed`；合并 focused 为 `40 passed`。

### Broad、quality、migration 与 dependency gate

- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q`：`294 passed`。
- `ruff check backend/app backend/tests backend/alembic` 与 `ruff format --check backend/app backend/tests backend/alembic` 均通过；174 个 Python 文件全部不超过 500 行。
- `20260723_0008` 为唯一 Head；terminology migration 定向测试覆盖 SQLite 空库完整 upgrade、两张表与关键 snapshot 唯一约束。主会话逐项比对两表 model/migration 的 column、foreign key、unique constraint 与 index name 全部一致。MySQL dialect offline `upgrade head --sql` 退出码 `0`，生成两张表、命名外键/唯一约束及中文 COMMENT；PowerShell 显示片段发生 console transcoding，不是 migration 源文件编码丢失。
- `pip check` 通过；Backend `pip-audit --local` 为 `0 known vulnerabilities`，仅按预期跳过本地非 PyPI package；14 个 direct production dependency license metadata 无缺失。
- `git diff --check`、unstaged/staged added-line Secret/危险调用、binary 与禁止路径检查均纳入本任务 gate；最终 staged 结论见提交前记录。
- 当前主会话按 migration/model、API/Service、Normalizer/Evidence、tests、security/scope 与状态文档顺序复核最终 cached diff；两项 blocker 完成 TDD remediation 后，最终 verdict 为 `security_concerns=0`、`logic_errors=0`，无剩余 blocking finding。

### Runtime 缺口与证据边界

- 当前 PATH 无 `docker`，任务卡 3 条 `docker compose run` 命令未进入容器，不标记 Compose/backend container runtime 通过。
- 未读取 ignored `.env`、未使用本机 Secret，因此未运行真实 MySQL `0008` upgrade。Direct Windows focused/broad、SQLite 空库 migration 与 MySQL offline DDL 不冒充真实 MySQL row lock/constraint runtime。
- 单进程临时 SQLite `upgrade head` 成功；紧接运行的 `alembic check` 因仓库既有 SQLite `BINARY(16)` introspection 被识别为 `NUMERIC(16)`，对全部历史及新增 UUID 列统一报告 type drift，因此不标记通过。定向 migration tests 与 MySQL offline DDL 证明 T2-003 表/约束契约，但不等同于真实 MySQL `alembic check`。

### 安全与决策

- 所有 library/version/item/project 读取先绑定 authenticated `user_id`；跨用户与不存在资源使用一致 not-found，不通过 version query 泄露 snapshot。
- mutation 对最新 active 版本使用 locking read，并在同一事务写下一版本与完整 items；历史版本不更新，删除只追加 tombstone。
- 标准化不调用模型、不访问公网、不猜缺失年份或单位；显式来源单位优先于术语 hint，冲突保留 raw 并阻断。
- 来源冲突只输出 evidence ID/标准化候选并要求用户权威选择；派生 Evidence 保留 source provenance 且继续标记 `source_fact`。

### 完成结论

- T2-003 严格范围内的实现、四轮 TDD、focused/broad/quality/migration/dependency/security 与文档同步已完成；Docker、真实 MySQL 和 SQLite type-introspection 导致的 `alembic check` 非通过结论已如实记录。
- T2-003 以单一逻辑 commit 推送后收口为 `DONE`；T2-004 是下一唯一 `READY` 任务，本会话未实现任何 Skill、Agnes 或 Structured Brief 代码。

## T2-004 执行记录

### 范围

- 固化 `ppt.sales-business-review.v1` 与 `excel.sales-analysis-dashboard.v1` 两个不可变 Alpha Skill，保存完整 input/output Schema、workflow、能力要求与 checksum，并限制为已知单选或组合。
- 建立 `skills`、`briefs`、`provider_calls` 模型与 `20260723_0009` migration；Brief 每次生成只写一个不可变 `draft` revision，Provider call 只保存脱敏 metadata。
- 新增鉴权 Skills catalog/detail 与 Brief generate API；服务只读取 owner-scoped ready asset、Evidence Manifest、术语 snapshot、已发布模型和 active Credential。
- 实现保守 Context/message budget、严格 17 字段 Structured Brief、evidence/source validation、最多一次 repair、timeout uncertain、401/403 Credential pause 与禁止 Provider fallback。
- 未实现 T2-005 的 Brief PATCH、确认、Preflight、积分预留、生成任务或前端页面。

### Changed files

- Model/Migration：`backend/app/models/{skills,briefs,provider_calls}.py`、model exports 与 `backend/alembic/versions/20260723_0009_skills_and_structured_briefs.py`。
- Skill/Brief contracts 与服务：`backend/app/skills/catalog.py`、`backend/app/services/skills.py`、`backend/app/services/briefs/`、`backend/app/schemas/briefs.py`。
- API/Wiring：`backend/app/api/v1/briefs.py`、router/application/error wiring；Evidence Manifest store 增加 bounded read。
- Tests：`backend/tests/skills/`、`backend/tests/briefs/`、`backend/tests/providers/agnes_contract/`，以及历史 terminology migration head 断言随连续 revision 更新。
- Records：T2-004/T2-005 task cards、task index、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未触碰/未暂存：用户未跟踪 `design-system/`、旧 `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏黄金材料。

### TDD、focused 与 review

- RED 从缺失 Skill/Brief modules、models、migration、API wiring 与 Agnes Contract 开始；按 catalog/model、strict schema/context、service/API、provider failure 与 contract 分组转 GREEN。
- Focused 最终：`backend/tests/skills` 为 `17 passed`；`backend/tests/briefs` 为 `28 passed`；`backend/tests/providers/agnes_contract` 为 `2 passed, 2 skipped`。
- 两项 Agnes skip 明确要求显式 real-contract opt-in，缺失时不读取 `.env` 或 Credential；Mock 覆盖最小文本/销售材料、响应 envelope 与 usage/request ID contract。
- 主会话顺序 review 修复：数据库 Skill 内容可绕过 checksum 漂移、goal/audience/must constraints 未纳入权威快照、migration 导入 runtime catalog、Brief route cache/auth 顺序、术语规则未进入 Provider context、无 evidence 的 file/calculation/Agnes inference、独立 cipher wiring、Manifest 无界读取。
- Broad 首轮另发现 MySQL offline DDL 无法编译 `BINARY(16)` seed UUID，先复现 4 个 migration regression，再改为 dialect-safe literal insert；相关 8 个 migration tests 转 GREEN。最终 review verdict 无 blocking security/logic finding。

### Broad、quality、migration 与 dependency gate

- Backend `.venv/Scripts/python.exe -m pytest tests -q --tb=no`：`341 passed, 2 skipped`，仅跳过未 opt-in 的真实 Agnes Contract。
- `ruff format --check app tests alembic`：209 files already formatted；`ruff check app tests alembic`：All checks passed；全部 Python 文件不超过 500 行。
- `alembic heads`：`20260723_0009 (head)`；SQLite 空库 upgrade 与 exact Skill seed checksum tests 通过；MySQL dialect `upgrade head --sql` 退出码 `0`。
- `pip check`：No broken requirements；`pip-audit --local`：0 known vulnerabilities，仅按预期跳过本地非 PyPI package；14 个 direct production dependency license metadata 无缺失。
- `git diff --check` 与 owned source Secret/危险调用扫描通过；`.env` 由 `.gitignore` 的 `*.env` 规则忽略。精确暂存后的 path/binary/added-line Secret/危险调用 gate 全部通过，staged paths 无禁止目录。

### Runtime 缺口与证据边界

- 当前 PATH 无 `docker`，任务卡 3 条 `docker compose run` 命令无法进入容器；Direct Windows focused/broad 不冒充 Compose runtime。
- 未读取 ignored `.env` 或本机 Secret，未运行真实 MySQL `0009` upgrade；SQLite 空库 migration 与 MySQL offline DDL 不冒充真实 MySQL constraint/runtime 证据。
- 未提供真实 Agnes opt-in、runtime Database/Master Key 与已配置 Credential，因此真实 Contract 为 `skipped`。T2-004 只标记 Mock Contract 和本地实现通过，不声称真实 Agnes 兼容性通过；最终外部集成结论仍由后续真实环境 Gate 承担。

### 安全与决策

- API 先认证再查询 Skill/Brief service；项目、资产、术语 snapshot、Evidence 与模型均绑定当前 owner，跨用户资源不进入 Provider context。
- Provider 请求只含预算内 evidence/metadata/术语规则，不公开本地文件；`provider_calls` 不保存 Key、Prompt、响应正文、用户内容、storage key 或物理路径。
- 初次结构/evidence validation 失败仅允许一次约束 repair；第二次失败不保存 Brief。timeout 标记 `provider_uncertain` 且不自动重试，401/403 暂停当前 Credential，均不静默切换 Provider。
- migration seed 自包含，不导入 runtime application code；runtime 启动同时校验数据库 Skill checksum 与完整内容，防止 checksum 未变但行内容漂移。

### 完成结论

- T2-004 严格范围内的实现、TDD、focused/broad/quality/migration/dependency/security 与文档同步已完成；Docker、真实 MySQL 和真实 Agnes Contract 缺口已如实记录。
- T2-004 以单一逻辑 commit 推送后收口为 `DONE`；T2-005 是下一唯一 `READY` 任务，新会话必须重新读取 live 文档、Git 与 origin 状态后再实现。

## T2-005 执行记录

### 范围

- 新增 owner-scoped Brief GET、append-only PATCH、普通确认和一键 Preflight；过期或已确认 Revision 不可修改，重复确认同一 Revision/费用返回既有锁定结果。
- Preflight 复验资产版本与 Manifest、Evidence blocker、Brief unresolved item、两个 Alpha Skill 合同、5 个系统模板、Agnes Provider/Credential 和模型 snapshot/capability。
- 冲突稳定分为 `auto_merge`、`needs_confirmation`、`blocking`、`incompatible`；resolution 必须匹配当前 unresolved code/action/evidence IDs。
- 每个输出按 `ceil(800 × model.credit_multiplier)` 计算；multiplier、模板版本、子输出费用和总费用进入不可变 Preflight snapshot。
- 新增基础确认页，可查看/编辑 goal 与 audience、显示输出/模板/积分和可操作冲突，并在 blocker 存在时禁用唯一 primary CTA。
- `queued` 仅表示 generation-ready Brief；本任务不创建 `generation_tasks`、不写 `credit_ledger` 或 Outbox、不调用 Worker、不执行 Office renderer。

### Changed files

- Contract/Service：`backend/app/services/preflight/` 的 catalog、contracts、evaluator 与 workflow service；`backend/app/services/briefs/` 补系统模板 snapshot 和 workflow wiring。
- Model/Migration：`backend/app/models/briefs.py` 与 `backend/alembic/versions/20260723_0010_brief_preflight_snapshot.py`，只 additive 增加两个可空字段。
- API/Wiring：`backend/app/api/v1/briefs.py`、router、schemas、application。
- Backend tests：`backend/tests/preflight/`，既有 Brief/Skill/Terminology migration/model contract 随连续 Head 更新。
- Frontend：authenticated API client、in-memory Session token、Brief module/types、确认路由与 `frontend/src/views/brief/confirm.vue`，及相应 Vitest。
- Records：T2-005/T3-001 task status、task index、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/SECURITY.md`、本文件与 `pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧 `docs/ui-mockups/` 和 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏材料。

### TDD、focused 与主会话 review

- RED 从缺失 Preflight package、migration/model 字段、service/API、frontend client/route/view 和默认模板 snapshot 开始，按 contract、persistence、service、API 与 UI 分组转 GREEN。
- 主会话顺序 deep review 新增并修复 resolution action/evidence matching、模型完整 identity、`auto_merge`/`needs_confirmation` 展示，以及“写诊断状态后立即抛 409 导致事务回滚”。
- 最终 traceability review 又发现两项 hard stop：保存新 Revision 后页面仍向旧 ID 发 Preflight，以及 snapshot 未显式记录 task card 要求的 model multiplier。两项均先得到定向 RED，再最小修复转 GREEN。
- Focused backend：`.venv/Scripts/python.exe -m pytest tests/preflight tests/briefs -q` 为 `57 passed`。
- Frontend：`npm run test` 为 `6 files / 12 tests passed`；`npm run build` 通过。
- Playwright 以脱敏本地 mock 验证 1280×900 与 375×812 页面；最终移动端 `scrollWidth=clientWidth=375`，模板显示中文标签且无横向溢出。截图留在 ignored `output/`，不纳入 Git。

### Broad、quality、migration 与 dependency gate

- Backend `.venv/Scripts/python.exe -m pytest tests -q --tb=no`：`370 passed, 2 skipped`；只跳过未 opt-in 的两项真实 Agnes Contract，未读取 `.env` 或 Credential。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 通过；221 个 Python 文件全部不超过 500 行。
- `alembic heads` 为单一 `20260723_0010 (head)`；SQLite 空库 upgrade/migration tests 通过；MySQL dialect offline `upgrade head --sql` 退出码 `0`，生成 536 行并包含 `briefs` 两列 ALTER。
- `pip check` 通过；`pip-audit --local` 为 0 known vulnerabilities，仅按预期跳过本地非 PyPI package；14 个 direct production dependency license metadata 无缺失。
- `npm audit --audit-level=high` 为 0 vulnerabilities；Node lockfile 236 个 package license metadata 无缺失。
- 主会话按 auth/owner boundary、append-only revision、transaction/locking、model/template/evidence compatibility、费用锁、API/UI、migration 和 adversarial abuse 顺序复核；修复 2 个 hard stop 后，无剩余 blocking security/logic finding。

### Runtime 缺口与证据边界

- 任务卡四条 Compose 命令已逐条实际尝试；当前 PATH 无 `docker`，全部在容器创建前 command not found，不标记 Compose/backend/frontend container runtime 通过。
- 未读取 ignored `.env` 或本机 Secret，因此未运行真实 MySQL `0010` upgrade/row-lock probe；SQLite migration 与 MySQL offline DDL 不冒充真实 MySQL runtime。
- 真实 Agnes Contract 仍未获 explicit opt-in，保持 `2 skipped`；T2-004 的 Mock Contract 证据未被提升为真实 Agnes 通过。
- 本任务没有生成 Office 文件；Microsoft Office/WPS 接受与真实 renderer 证据仍属于 T3/T4 外部 Gate。

### 安全与决策

- 所有 Brief 操作先认证并按 `user_id` owner scope；来源资产还绑定 project、未删除、ready 状态、asset version、Manifest key/SHA。
- PATCH 只接受明确用户字段、系统模板和匹配当前 unresolved item 的 resolution；来源、术语、Skill、模型与 Evidence 引用沿用权威 snapshot。
- Preflight 不解密 Credential、不访问 Provider 或公网；只核对数据库中 active Agnes Provider/Credential/model capability，不把 Secret 放入 response、snapshot 或日志。
- 费用变化或新增 blocker 先提交最新 snapshot 再返回 409；确认快照保持 multiplier/模板/子输出与总费用，重复确认不重算。
- Frontend access token 只保存在 Pinia memory state，不写 localStorage、URL 或日志；Brief API 使用 Bearer 并返回 `private, no-store`。

### 完成结论

- T2-005 严格范围内的实现、TDD、focused/broad/quality/migration/dependency/security、实机 UI 和状态文档同步已完成；Docker、真实 MySQL、真实 Agnes 与 Office/WPS runtime 缺口已如实记录。
- T2-005 以单一逻辑 commit 推送后收口为 `DONE`；T3-001 是下一唯一 `READY` 任务，本会话未创建 generation task、积分流水或 Outbox。

## T3-001 执行记录

### 范围

- Additive 建立 `generation_tasks`、`generation_task_steps`、`generation_task_inputs` 与 `outbox_events`，补齐 `credit_ledger` 的 task 外键和 `provider_calls` 的 task/step attempt 关联。
- `POST /generations` 在同一数据库事务锁定 owner、最新已确认 Brief、Model/Credential/Provider 和余额，冻结输入/模板/Skill/model snapshot，写入 task、steps、reserve ledger 与首个 Outbox；同 user/idempotency key 重放既有任务。
- 实现 owner-scoped task 查询、取消、受限重试和 Credits balance/ledger；状态机覆盖 queued/running/succeeded/partial_success/provider_uncertain/failed/cancelled。
- 实现 MySQL checkpoint 权威的 Worker 编排、Outbox at-least-once Dispatcher、Redis 丢失恢复、safe stale step 恢复、每用户并发和 Credential RPM/TPM/最大并发限制。
- Python consumer 只接受注入的 step executor；本任务不渲染或伪造 PPTX/XLSX，不提前实现 T3-002。

### Changed files

- Models/Migration：`backend/app/models/{generation_tasks,generation_task_steps,generation_task_inputs,outbox_events,credit_ledger,provider_calls}.py`、model exports 与 `backend/alembic/versions/20260723_0011_generation_outbox_credits.py`。
- Service/Worker：`backend/app/services/{generation,generation_contracts,generation_snapshots,credit_transactions,generation_worker,credential_limits,outbox,outbox_events}.py` 与 `backend/app/workers/generation/`。
- API/Wiring：`backend/app/api/v1/generations.py`、`backend/app/schemas/generation.py`、router、application lifespan、Redis Lua helper、settings/error contract 与 Compose timeout mapping。
- Tests：`backend/tests/{generation,credits,outbox,integration}/`，以及历史 migration/model contract 对连续 `0011` Head 和 ProviderCall additive 字段的更新。
- Records：T3-001/T3-002 task status、task index、`docs/API.md`、`docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、本文件与 `pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧 `docs/ui-mockups/`、`.playwright-cli/` 和 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏材料。

### TDD、focused 与主会话 review

- RED 首先因 generation service 不存在而 collection fail；随后按 model/migration、事务幂等、credits、状态机、Worker、Outbox、并发/限流、API/lifespan 分组转 GREEN。
- Focused：`.venv/Scripts/python.exe -m pytest tests/generation tests/credits tests/outbox tests/integration -q` 为 `27 passed`。
- 主会话顺序 deep review 修复 8 项 hard stop：Skill version 未冻结、safe stale step 未复位、service 幂等键校验绕过、满长 retry billing key 超列宽、ProviderCall 跨任务唯一键冲突、过期任务仍执行、confirm 后模型/费用漂移，以及子输出费用与锁定总额不一致。
- 修复项均增加或扩展定向回归；最终按 auth/owner、transaction/idempotency、ledger、state machine、checkpoint/recovery、provider uncertainty、limits、migration/API 顺序复核，无剩余 blocking security/logic finding。

### Broad、quality、migration 与 dependency gate

- Backend `.venv/Scripts/python.exe -m pytest tests -q --tb=no`：`397 passed, 2 skipped`；两项 skip 仅为未 opt-in 的真实 Agnes Contract。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 通过；252 个 Python 文件全部不超过 500 行。
- `alembic heads` 为单一 `20260723_0011 (head)`；SQLite 空库完整 upgrade 通过；MySQL dialect offline upgrade 捕获 674 行并包含四张新表、外键、ProviderCall task/step unique 和 nullable Brief group，`0011 -> 0010` offline downgrade 生成通过。
- `pip check` 通过；`pip-audit --local` 为 0 known vulnerabilities，仅按预期跳过本地非 PyPI package；14 个 direct production dependency license metadata 无缺失。
- Frontend `npm audit --audit-level=high` 为 0 vulnerabilities，251 个 package license metadata 无缺失；`npm run test` 为 `6 files / 12 tests passed`，`npm run build` 通过。
- 候选变更敏感模式扫描为 0 命中；最终 Git exact-path staging 前后继续执行 ignore、diff、staged-name 与状态门禁。

### Runtime 缺口与证据边界

- 任务卡四条 `docker compose run --rm backend pytest ...` 命令已逐条实际尝试；当前 PATH 无 `docker`，全部在容器创建前 `CommandNotFoundException`，不标记 Compose/backend container runtime 通过。
- 未读取 ignored `.env` 或本机 Secret，因此未运行真实 MySQL `0011` transaction/row-lock 或真实 Redis queue/Lua/recovery runtime；SQLite migration、MySQL offline DDL 与测试 double 不冒充这些 runtime 证据。
- 真实 Agnes Contract 仍未获 explicit opt-in，保持 `2 skipped`；T2-004 的 Mock Contract 不提升为真实 Agnes 通过。
- 本任务没有生成 Office 文件；Microsoft Office/WPS 接受、LibreOffice 和真实 renderer 证据仍属于 T3-002 及后续 Gate。

### 安全与决策

- Task create/read/cancel/retry 和 Credits 查询均先认证并 owner scope；响应使用 `private, no-store`，queue/outbox payload 不含 Credential Secret、文件正文、Prompt、storage key 或本地路径。
- 任务、不可变输入/能力快照、reserve ledger 和 Outbox 同事务提交；余额不足或 Outbox 写入失败整体回滚。账务真相保持 append-only，余额缓存只在同一事务同步。
- 全成功 finalize 全额；全失败/可取消任务 release；部分成功 finalize 成功子输出费用并 release 余量。`provider_uncertain` 保留 reserve，不自动重试或重复结算。
- 重复 queue message 依赖数据库 claim/checkpoint 去重；安全 stale step 可恢复，已进入 Provider 且结果未知的 checkpoint 转 `provider_uncertain`，不能伪装为安全重放。
- confirm 后仍复验 model/provider/credential identity、pricing/capability 与子输出费用总和，防止锁定费用或能力 snapshot 被漂移配置绕过。

### 完成结论

- T3-001 严格范围内的实现、TDD、focused/broad/quality/migration/dependency/security、主会话顺序 deep review 与状态文档同步已完成；Docker、真实 MySQL/Redis、真实 Agnes 和 Office/WPS runtime 缺口已如实记录。
- T3-001 以单一逻辑 commit 推送后收口为 `DONE`；T3-002 是下一唯一 `READY` 任务，新会话必须重新读取 live 文档、Git 与 origin 状态后再实现。

## T3-002 执行记录

### 范围

- 新增独立 Node.js/TypeScript `ppt-renderer`，只接受严格 `presentation-plan.v1`，使用 PptxGenJS 4.0.1 生成真实 16:9 PPTX；不接受自由文本、客户端路径或 PPTX 输入。
- 固化 `ppt.executive-blue.v1`、`ppt.operating-review.v1`、`ppt.data-story.v1` 三套 `1.0.0` 系统模板，覆盖 Slide Master、Placeholder、主题色、固定布局、页码和中文字体。
- 支持标题、正文、内联 PNG/JPEG、native table、bar/line/pie chart、Evidence/source、speaker notes 与 OOXML metadata；Plan 限制 3–30 页，所有事实型元素引用已知 Evidence ID。
- 建立版本化 renderer HTTP/worker envelope、受控 work root、请求/响应容量限制、同 request 并发去重、sidecar replay 与损坏 derived output repair。
- Python 适配层校验 response、Plan/file SHA-256、byte size、模板/Renderer 版本和受控相对路径；输出以稳定 asset ID、任务外键和不可变 key 持久化到 `file_assets`，不覆盖旧输出。
- 未实现 T3-003 的 overflow、字体替换、图片裁切、坏链、质量状态、LibreOffice 自动修复或视觉 QA。

### Changed files

- Renderer：`ppt-renderer/{src,tests,scripts}`、package/TypeScript/Vitest 配置、multi-stage Dockerfile 与 lockfile。
- Backend：`backend/app/services/renderers/presentation/`、`file_assets` task 外键、LocalStorage 精确 generated-output key、Renderer settings。
- Migration/Runtime：`20260723_0012_file_asset_generation_output.py`、历史 migration head tests、`docker-compose.yml` 的私有 non-root/read-only renderer 与 backend read-only handoff。
- Records：T3-002/T3-003 task cards、task index、`docs/{API,DATA_MODEL,ENVIRONMENT,SECURITY,PROGRESS}.md` 与 `pitfalls.md`。
- 未触碰/未暂存：用户未跟踪的 `design-system/`、旧 `docs/ui-mockups/`、`.playwright-cli/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件或未脱敏材料。

### TDD、focused 与真实输出证据

- RED：Node tests 先因 `contracts/renderer/worker-contract` 缺失而失败；Python tests 先因 `app.services.renderers` 缺失而 collection fail，随后按 schema、真实 OOXML、worker、HTTP client、output store/service 与 migration 分组转 GREEN。
- Node：`npm test` 为 `4 files / 20 passed`；`npm run build` 通过。固定 synthetic sample 为 4 页、189,830 bytes，ZIP/XML contract 确认 4 notes、3 charts、1 master、至少 4 layouts、Placeholder、页码、native table、media、Evidence/source 和 metadata；两次渲染结构等价。
- Python：`.venv/Scripts/python.exe -m pytest tests/renderers/presentation -q` 为 `27 passed`；presentation + storage + migration focused 合并为 `49 passed`。
- 编译后 Node server 与 Python client 的真实跨进程 smoke 通过：3 页、85,987 bytes；Python 复验 Node canonical Plan SHA-256、PPTX SHA-256、byte size 和受控 output key。
- 三套模板均生成真实 PPTX；同 request 并发 replay、损坏 work output repair、finalization failure recovery、ready output integrity、不同 Plan conflict 和冻结模板冲突均有回归。

### Broad、quality、migration 与 dependency gate

- Backend 全量候选运行唯一失败为既有 parser timing test：`424 passed, 2 skipped, 1 failed`，全量顺序 elapsed `0.385s > 0.3s`；该 exact test 单独运行 `1 passed`，精确排除后余集 `424 passed, 2 skipped, 1 deselected`。两项 skip 仅为未 opt-in 的真实 Agnes Contract。
- `ruff format --check app tests` 为 254 files formatted；`ruff check app tests` 通过。owned Python/TypeScript source 均不超过 500 行，package lockfile 不计 source gate。
- Frontend `6 files / 12 passed`、build 通过；`ppt-renderer` 与 frontend `npm audit` 均为 0 vulnerabilities。Backend `pip check` 通过，`pip-audit` 为 0 known vulnerabilities，仅跳过本地非 PyPI package。
- `alembic heads` 为唯一 `20260723_0012 (head)`；SQLite 空库完整 upgrade、历史连续 migration 和 named FK contract 通过；MySQL dialect offline upgrade/downgrade 通过。未读取 `.env`，未运行真实 MySQL migration。
- Compose 静态解析保持 9 服务；renderer 使用 pinned image build、non-root、read-only rootfs、private network、容量/CPU/PID 限制，无 Host port、Redis、Provider credential 或公网依赖；backend 只读挂载 renderer work volume。

### 主会话 deep review 与安全结论

- review 修复跨 Python/Node number canonicalization、Python 未校验 Plan hash、HTTP response 无界读取/不安全 base URL、ready replay 未复验磁盘、计划模板未绑定冻结 task snapshot、外部调用前 checkpoint 缺失，以及 Node 并发/损坏 replay 不可恢复。
- storage review 发现 generated-output allowlist 在长度检查前索引 malformed key；修正为 shape-first fail closed，并增加短 key/伪造文件名回归。
- 最终逐项复核 schema/reference、OOXML、worker concurrency/replay、HTTP boundary、task/template/asset integrity、migration/model、Compose isolation、测试与范围；无剩余 blocking security/logic finding。

### Runtime 缺口与完成结论

- 任务卡 3 条 `docker compose run` 命令已逐条实际尝试；当前 PATH 无 `docker`，均在容器创建前 `CommandNotFoundException`，不标记 Compose/container runtime 通过。
- 本机 PATH 与 Program Files 未发现 LibreOffice `soffice.exe`，固定样本未完成 Headless 打开/转换；结构合同与真实 PptxGenJS 输出不能替代 LibreOffice、Microsoft Office 或 WPS 接受。
- 未读取 ignored `.env` 或本机 Secret；未运行真实 MySQL/Redis、真实 Agnes 或用户材料。真实 Agnes 仍因未 explicit opt-in 保持 2 skipped，T2-004 Mock 证据未被提升。
- T3-002 的实现、TDD、focused/broad/security、主会话顺序 deep review 与状态同步已完成；以单一逻辑 commit 推送后收口。T3-003 是下一唯一 `READY` 任务，本会话未实现任何 PPT QA。

## T3-003 执行记录

### 范围

- 新增严格 `presentation-quality-report.v1`，固定关联原始 asset/hash、Renderer/template/Plan、质量引擎、LibreOffice、PDF/逐页 PNG、validated output 与最多一次 repair；finding 不含正文、路径或 storage key。
- 以 bounded ZIP/XML 检查损坏 OOXML、空白/缺页、对象越界、缺图、长标题、坏 chart workbook range 与 Evidence 引用；仅 geometry/autofit blocker 可确定性修复一次，原 PPTX 不覆盖。
- 新增 internal LibreOffice sidecar：固定 asset identity/source variant、无交互打开/转 PDF、PDFium 逐页转 PNG、原子 completion manifest 与实际 artifact replay 校验。
- 质量报告、preview、可选 repaired PPTX 使用同 asset 的固定 `quality/` key；DB checkpoint 和下载路径都复验实际 hash/size。`blocked` 返回 permanent failure，既有结算释放全部 reserve。
- 未实现 T3-004 Excel Renderer，不读取或修改用户材料、Secret、`.env`、黄金数据、旧 UI 草稿或 design-system。

### Changed files

- Quality：`backend/app/services/quality/presentation/` 与 `backend/tests/quality/presentation/`。
- Model/Migration：`file_assets` quality metadata、`20260723_0013_presentation_quality_metadata.py` 及历史 migration head contract。
- Asset/API：validated PPTX download gate、safe quality summary 字段与 LocalStorage repaired key allowlist。
- Runtime：LibreOffice sidecar Dockerfile、Compose private/non-root/read-only boundary、settings 和 `pypdfium2` dependency。
- Records：T3-003/T3-004 task cards、task index、`docs/{PLAN,API,DATA_MODEL,ENVIRONMENT,SECURITY,PROGRESS}.md` 与 `pitfalls.md`。
- 保留且未暂存：`.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/` 与 ignored `output/`。

### TDD、focused 与主会话 deep review

- RED 从缺失 quality package/strict schema 开始，依次建立损坏 OOXML、空白页、页缺失、越界、缺图、长标题、坏图表引用和 Evidence 引用 synthetic samples，再实现 contract、inspector、repair、sidecar、artifact store、service、migration、download 与 billing integration。
- Focused `.venv/Scripts/python.exe -m pytest tests/quality/presentation -q`：`52 passed`；assets/generation/integration/storage-security/quality 合并：`138 passed`；migration focused：`17 passed`。
- 主会话按 Schema/脱敏、OOXML bomb/path/XML 边界、repair 单次与原文件不可变、sidecar request/path/replay、artifact recovery/integrity、DB race/checkpoint、download/owner 与 billing 顺序 review。
- Review 修复 4 项 hard stop：DB finalize race 构造无效 Plan、重放未复验 PDF/PNG、成功转换后同 request 无法 retry，以及 completion marker 未绑定完整输入 fingerprint；均先增加失败回归再转 GREEN。最终所有 owned Python source 不超过 500 行，无剩余 blocking security/logic finding。

### Broad、quality、migration 与 dependency gate

- Backend `.venv/Scripts/python.exe -m pytest tests -q --tb=no`：`477 passed, 2 skipped`；两项 skip 仅为未 opt-in 的真实 Agnes Contract。
- `ruff check app tests alembic` 与 `ruff format --check app tests alembic` 通过；`pip check` 通过。
- PPT Renderer：`4 files / 20 tests passed`、build 通过、`npm audit --audit-level=high` 为 0 vulnerabilities。
- Frontend：`6 files / 12 tests passed`、build 通过、`npm audit --audit-level=high` 为 0 vulnerabilities。
- `alembic heads` 为唯一 `20260723_0013 (head)`；SQLite 空库 upgrade 通过；MySQL dialect offline upgrade 为 694 行并含 quality columns，`0013 -> 0012` downgrade 为 28 行并含 drop；未运行真实 MySQL。
- `pip check` 通过；`pip-audit --local` 为 0 known vulnerabilities，仅跳过本地非 PyPI package；15 个 direct production dependency license metadata 无缺失。Compose 静态 quality/settings contract、Git sensitive/exact-path gate 通过。

### Runtime 缺口与证据边界

- 任务卡四条 Docker 命令已逐条实际尝试；当前 PATH 无 `docker`，全部在创建容器前 `CommandNotFoundException`，不标记 Compose、Backend、Renderer 或 LibreOffice container runtime 通过。
- PATH 与 `C:\Program Files` 未发现 `soffice.exe`；没有真实执行 LibreOffice 打开/转 PDF。synthetic OOXML、sidecar contract 与 PDFium preview test 不冒充 LibreOffice、Microsoft Office 或 WPS 接受。
- 未读取 ignored `.env` 或本机 Secret；未运行真实 MySQL `0013`、真实 Redis、真实 Agnes 或用户材料。真实 Agnes 仍保持 `2 skipped`，T2-004 Mock 证据未提升。

### 安全与完成结论

- 质量 sidecar 不接收路径、正文、Credential 或 Provider data；容器没有 Host port/external network/Secret，原始 asset volume 只读。报告 finding 与错误只返回稳定脱敏 code。
- OOXML/XML/ZIP、HTTP body/response、PDF/PNG、页数和 geometry 均有上限；未知字段、path escape、hash/size/页数/版本漂移和 artifact tamper 全部 fail closed。
- 原 PPTX 与历史质量报告不可变；修复最多一次。只有 `passed`/`passed_with_warnings` 且 validated artifact 完整性通过时可下载；blocked 任务失败并由既有 ledger 释放 reserve。
- T3-003 的实现、TDD、focused/broad/security、主会话顺序 deep review 与状态同步已完成；以单一逻辑 commit 推送后收口。T3-004 是下一唯一 `READY` 任务，新会话必须重新读取 live 文档、Git 与 origin 状态后再实现。

## T3-004 执行记录

### 范围

- 新增 strict `workbook-plan.v1` 与 canonical Plan SHA-256；只接受
  `excel-renderer.v1`、`zh-CN`、两套系统模板、typed data/summary Sheet 和结构化
  calculation/chart/format/validation/print contract。
- XlsxWriter 从新工作簿生成数据表、汇总、同比/环比、排名、column/line/pie 基础图表、
  条件格式、data validation、冻结窗格和打印设置；公式仅由 Renderer 生成英文
  `SUM/AVERAGE/COUNT/IFERROR/RANK.EQ` 与英文逗号，并写显式确定性 cache。
- 原始文本关闭 formula/URL 自动解释；WorkbookPlan 最多 20 Sheet、200,000 个实际生成
  cell，Sheet/column/chart 引用和 Excel anchor/inline validation 上限在创建文件前闭合验证。
- 两套认证模板为 `excel.analysis-dashboard.v1@1.0.0` 和
  `excel.operating-review.v1@1.0.0`；样式变化不改变数据、公式和 trace 语义。
- 原始 XLSX 使用 owner/asset 固定 key 原子保存且不可覆盖；输出结果与 XLSX custom
  properties 固定关联 original SHA-256/size、Plan SHA-256、Schema/Renderer/template。
- LibreOffice private sidecar 新增 strict `/v1/spreadsheet/recalculate`；只接受
  request/user/asset UUID、原件 hash/size 和 Plan/Renderer/template version，从固定
  `users/{user_id}/outputs/{asset_id}/analysis.xlsx` 只读原件，在 shared-work 生成独立
  validation copy 与 `workbook-validation-report.v1`。Backend client 复验固定 key、
  hash/size、formula/cache 差异和完成重放；镜像新增 `libreoffice-calc`。
- 未实现 T3-005 的公式错误/黄金指标质量 gate、组合任务聚合、下载状态或积分结算。

### Changed files

- Renderer：`backend/app/services/renderers/excel/`。
- Tests：`backend/tests/renderers/spreadsheet/`。
- Runtime/dependency：`backend/pyproject.toml`、`backend/libreoffice-service/Dockerfile`、
  `backend/app/services/quality/presentation/server.py`。
- Records：T3-004/T3-005 task cards、task index、`docs/{PLAN,API,DATA_MODEL,ENVIRONMENT,SECURITY,PROGRESS}.md`
  与 `pitfalls.md`。
- 保留且未暂存：用户未跟踪的 `.playwright-cli/`、`design-system/`、旧
  `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件
  或未脱敏材料。

### TDD、focused 与真实 XLSX 证据

- RED 1：spreadsheet tests 因 `app.services.renderers.excel` 不存在 collection fail；
  Schema/引用/容量 contract 最小实现后转 GREEN。
- RED 2：真实 XLSX tests 先因 openpyxl/XlsxWriter 与 Renderer/output store 缺失失败；
  安装并声明 `openpyxl 3.1.5`、`XlsxWriter 3.2.9` 后，实现两套模板和不可变存储转
  GREEN。
- RED 3：LibreOffice validation-copy tests 因 module 缺失失败；实现 formula/cache
  双视图 diff、原件 hash 双检、完成 replay/tamper 和稳定错误后转 GREEN。
- RED 4：deep review 发现 Backend 容器无 `soffice` 且 sidecar 镜像无 Calc；sidecar/client
  contract 与镜像 tests 先 RED，再接入现有 private LibreOffice service 转 GREEN。
- `.venv/Scripts/python.exe -m pytest backend/tests/renderers/spreadsheet -q`：
  `36 passed`。
- 固定 synthetic sample 实际生成 2 Sheet、38 个 cell、12 个公式；openpyxl
  `data_only=False/True` 分别确认英文公式和 cache，图表 range、conditional format、
  validation、freeze/print contract 均通过；同 Plan 两次 XLSX bytes/SHA-256 一致。
- 输出 ZIP 无损、无 externalLinks/VBA；`=UNTRUSTED()` 原始文本保持 string。原始 XLSX、
  validation copy 与 report 使用独立 path，fake sidecar 只证明 contract，不冒充真实
  LibreOffice。

### Broad、dependency 与安全验证

- `.venv/Scripts/python.exe -m pytest backend/tests/integration -q`：`4 passed`。
- `.venv/Scripts/python.exe -m pytest backend/tests -q --tb=no`：
  `513 passed, 2 skipped`；两项 skip 仅为未显式 opt-in 的真实 Agnes Contract，T2-004
  仍只保持 Mock 证据。
- `ruff check backend/app backend/tests backend/alembic` 与
  `ruff format --check backend/app backend/tests backend/alembic`：通过，309 个文件格式
  已一致；本任务 owned Python source 均不超过 500 行。
- Backend `pip check`：通过；`pip-audit --local`：0 known vulnerabilities，仅按预期跳过
  本地非 PyPI package。新增 direct dependency license：openpyxl `MIT`、XlsxWriter
  `BSD-2-Clause`。
- Frontend：6 files / 12 tests passed、build 通过、npm audit 0 vulnerabilities。
- PPT Renderer：4 files / 20 tests passed、build 通过、npm audit 0 vulnerabilities。
- strict Schema 禁止自由公式、未知字段、客户端路径、外部连接和 unsupported template；
  原始文本不自动转公式/URL。sidecar request/response body 有上限，固定 key/hash/size/
  trace 漂移、坏 XLSX、报告/validation copy 篡改与 request ID 冲突全部 fail closed。

### 主会话 deep review 与 runtime 缺口

- 当前主会话按 Schema/容量、公式/cache、真实 OOXML、两套模板、chart/format/validation/
  print、目的文件覆盖、output store、LibreOffice copy/report/replay、sidecar HTTP/key、
  dependency/container 和 T3-005 scope 顺序复核。
- Review 修复 Excel inline validation 255 字符和 XFD/1048576 anchor 边界、sheet-limit
  稳定错误、Renderer destination TOCTOU 覆盖、全文件内存 hash、LibreOffice profile
  隔离、报告/副本 replay/tamper、坏 XLSX exception 泄漏，以及错误的 backend-local
  `soffice` 进程边界；最终无剩余 blocking security/logic finding。
- PATH 当前无 `docker`、`docker-compose`、`soffice`；常见 64/32-bit LibreOffice
  `soffice.exe` 路径均不存在。任务卡三条 Docker 命令和 `soffice --version` 已实际尝试，
  均在容器/进程启动前 `CommandNotFoundException`。
- 因此没有 Docker build/runtime、真实 LibreOffice 打开/重算、Microsoft Office/WPS
  接受、真实 MySQL/Redis 或真实 Agnes 新证据；Python sidecar fake、真实 XLSX 和
  openpyxl contract 不能替代这些 runtime/人工证据。
- T3-004 代码、TDD、focused/broad/security、当前主会话顺序 deep review 与状态同步已
  完成；单一逻辑 commit 推送并确认远端 0/0 后收口。T3-005 是下一唯一 `READY` 任务，
  新 Codex 会话必须重新读取 live 文档、Git 与 origin 状态后再执行。

## T3-005 执行记录

### 范围

- 新增 strict `workbook-quality-report.v1`，检查实际 formula error、原始值与公式 cache
  确定性复算、summary、精确 chart category/value range，以及未解决的 Sheet/字段/单位
  冲突；finding 不保存公式正文、storage key、本地路径或用户材料。
- 新增 generation-owned Excel output service：从冻结 Workbook Plan 生成不可变
  `analysis.xlsx`，先写 step checkpoint，再保存 owner/task scoped `file_assets`，同 Plan
  安全重放，不同 Plan 或 artifact 漂移 fail closed。
- Excel QA 调用既有 private LibreOffice sidecar，持久化原始 validation report、独立
  validation copy、质量报告和 validated XLSX；完成/replay/download 均复验实际
  hash/size。
- PPTX/XLSX 子步骤分别保存 output asset/version、quality/download 状态与 estimated
  credits；组合 worker 将两成聚合为 `succeeded`，一成一败聚合为 `partial_success`，
  只 finalize 成功额度并 release 失败额度，重放不重复写 ledger。
- 新增 owner-scoped outputs API contract 与 output-kind executor router；本任务未实现
  T4-001 UI、管理员功能壳或任何后续任务。

### Changed files

- Excel QA：`backend/app/services/quality/spreadsheet/`。
- Generation/输出：`backend/app/services/generation_combined.py`、
  `generation_outputs.py`、`generation.py`、`generation_worker.py`、
  `generation_contracts.py`、API/schema 与 asset download gate。
- Excel output：`backend/app/services/renderers/excel/service.py` 及 package export。
- Tests：`backend/tests/quality/spreadsheet/`、`backend/tests/generation/combined/`、
  `backend/tests/integration/test_combined_generation_week3.py` 与 PPT 结算回归。
- Records：T3-005/T4-001 task cards、task index、
  `docs/{PLAN,API,DATA_MODEL,ENVIRONMENT,SECURITY,PROGRESS}.md` 与 `pitfalls.md`。
- 保留且未暂存：用户未跟踪的 `.playwright-cli/`、`design-system/`、旧
  `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件
  或未脱敏材料。

### TDD、focused 与组合证据

- RED 1：spreadsheet quality tests 因 package 缺失 collection fail；formula error、
  formula/cache、raw value、summary、chart range、Sheet/字段/单位 conflict contract
  分批实现后转 GREEN。
- RED 2：combined tests 先暴露 `StepExecutionResult` 缺少质量/output metadata、互斥状态
  可同时成立，以及一成一败结算/重放合同缺失；补齐 step checkpoint、聚合与幂等 ledger
  后转 GREEN。
- RED 3：integration/outputs tests 先因 endpoint 与真实 asset integrity gate 缺失失败；
  新增 owner/task/category/version/quality artifact 校验后转 GREEN。
- RED 4：deep review 为错误 chart field、plain-text `#REF!` 误报、原始数值漂移、
  LibreOffice report 未持久化、固定 temp crash、pending output integrity、PPT checkpoint
  clobber、retry checkpoint 丢失、Excel generation asset 和 output-kind router 分别补
  RED，再最小修复。
- Focused：
  `.venv/Scripts/python.exe -m pytest tests/quality/spreadsheet tests/generation/combined tests/integration/test_combined_generation_week3.py tests/quality/presentation/test_billing_integration.py -q`
  为 `33 passed`。
- 任务卡目录逐项：spreadsheet QA `22 passed`、combined `9 passed`、integration
  `5 passed`；PPT Renderer `4 files / 20 tests passed`。
- Week 3 integration 覆盖 confirmed combined Brief 创建同一 task 的 PPTX/XLSX steps、
  独立质量/下载结果、全部成功和一成一败，以及重复 settlement 不改变余额；不调用真实
  Agnes，不读取 `.env` 或用户材料。

### Broad、quality、security 与 runtime

- Backend `.venv/Scripts/python.exe -m pytest -q`：`545 passed, 2 skipped`；两项 skip
  仅为未显式 opt-in 的真实 Agnes Contract，T2-004 仍只保持 Mock 证据。
- `ruff check app tests` 与 `ruff format --check app tests`：通过，313 个文件格式一致；
  本任务主要 Python source 均不超过 500 行。
- Backend `pip check` 通过；`pip-audit` 0 known vulnerabilities，仅按预期跳过本地非
  PyPI package；Alembic 保持单一 `20260723_0013 (head)`，本任务无 migration。
- Frontend：6 files / 12 tests passed、build 通过、npm audit 0 vulnerabilities。
- PPT Renderer：4 files / 20 tests passed、build 通过、npm audit 0 vulnerabilities。
- 当前主会话按 formula/value/cache、chart/冲突、artifact replay、owner/download、
  worker checkpoint、组合 settlement、PPT regression、文件体积和 T4-001 scope 顺序
  deep review；修复上述缺陷后无剩余 blocking security/logic finding。
- 任务卡四条 Docker 命令与 `soffice --version` 已实际尝试；PATH 无 Docker/`soffice`，
  均在容器或进程启动前 `CommandNotFoundException`。没有 Docker、真实 LibreOffice
  Calc、MySQL/Redis、Microsoft Office/WPS 或真实 Agnes 新证据，不把 fake/Mock contract
  冒充 runtime 通过。

### 完成结论

- T3-005 严格范围内实现、TDD、focused/broad/security、主会话顺序 deep review 与状态
  文档同步已完成；单一逻辑 commit 推送并确认远端 0/0 后收口。
- T4-001 是下一唯一 `READY` 任务；新 Codex 任务必须重新读取 live `AGENTS.md`、
  `docs/PROGRESS.md`、任务索引/任务卡、PLAN/专题文档和 Git/origin 状态，不得依赖聊天
  摘要，也不得提前实现 T4-002。

## T4-001 执行记录

### 范围

- 建立 25 个显式 public/user/admin route，以及 anonymous、user、admin、
  `must_change_password`、no-permission 和 404 权限边界。
- Access Token 只保存在内存；Refresh Token 只保存在 `sessionStorage`。应用启动先 rotation
  再读取 `/auth/me`，失败时 fail closed 清空状态；logout 同时调用服务端 revoke。
- 用户端接入现有 project/asset、Skill/model、term library、Brief/Preflight、
  Generation/output/download 和 credit API，完成从注册到双输出下载的 Alpha 流程。
- 管理端接入现有 invite、Provider、Credential、model 与概览数据；T4-002 才交付的用户、
  任务、资产、积分和 audit 管理 HTTP 闭环只呈现 truthful disabled/empty shell。
- UI 沿用批准的暖瓷白、墨色、钢蓝 token 与既有 Vue 分层；没有紫色、渐变、glow、
  第二套设计系统、Credential Reveal 或提前实现的敏感操作。

### Changed files

- Frontend shell/auth：`frontend/src/{router,store,layouts,components/common,modules/auth}/`、
  `frontend/src/views/auth/` 与入口/全局样式。
- 用户流程：`frontend/src/modules/{workflow,projects,assets,skills,terms,generations,credits}/`
  和 `frontend/src/views/user/`。
- 管理后台：`frontend/src/modules/admin/` 和 `frontend/src/views/admin/`。
- Records：T4-001/T4-002 task cards、task index、`docs/PROGRESS.md`、
  `docs/ui-v1/IMPLEMENTATION.md` 与 `pitfalls.md`。
- 保留且未暂存：用户未跟踪的 `.playwright-cli/`、`design-system/`、旧
  `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件
  或未脱敏材料。

### TDD、focused 与实际浏览器证据

- RED contract 先覆盖全部 route/metadata、Session bootstrap/rotation、登录/注册/强制改密、
  用户选择和阻断、Brief/Preflight、Generation/双输出 download gate、管理六项导航、
  Credential 掩码及 T4-002 disabled boundary，再按最小页面/API/store 实现转 GREEN。
- Frontend 最终 `22 files / 58 tests passed`；Production Build
  `94 modules transformed`，无 TypeScript 错误。
- 实际 headed Chrome 在 Production Build 上逐步完成：登录、reload 后 refresh bootstrap、
  首页选择、workflow、Brief/Preflight、确认后创建 Generation、成功结果、PPTX/XLSX
  下载、注册、强制改密、logout escape 与普通用户 admin 拒绝。
- 实际访问并检查 11 个管理 UI V1 route；Credential 精确显示
  `sk-••••••••9F3A` 且 Reveal button 为 `0`。桌面核心与最终 clean session console 均为
  `0 errors / 0 warnings`。
- `1440px` 桌面和 `375px` 窄屏关键截图人工核对；页面无横向溢出，移动端 admin
  navigation/table 仅在自己的受控 scroller 内滚动。浏览器使用受控 Mock API，因此只
  证明前端视觉、交互和 contract，不冒充真实后端 runtime。

### Broad、security、deep review 与 runtime 缺口

- Backend focused integration：`5 passed`；backend full：
  `545 passed, 2 skipped in 49.20s`。两项 skip 仅为未显式 opt-in 的真实 Agnes
  Contract，T2-004 仍只有 Mock 通过。
- Ruff check 通过，Ruff format check 为 `313 files already formatted`。
- Frontend 与 PPT Renderer `npm audit --audit-level=high` 均为
  `0 vulnerabilities`；PPT Renderer `4 files / 20 tests passed` 且 build 通过。
- 当前主会话顺序 deep review 修复 Session bootstrap、server logout、term library
  version 选择、Brief 确认后 Generation 创建、管理导航 active group、注册部分成功残留、
  非 JSON 5xx 脱敏、硬编码环境标签、改密 accessibility 和窄屏 metadata 碰撞；最终无
  剩余 blocking security/logic finding。
- 任务卡三条 Docker 命令已实际尝试，但 PATH 无 `docker`，均在服务启动前
  `CommandNotFoundException`。本任务没有 Docker、真实 MySQL/Redis/Agnes/LibreOffice、
  Microsoft Office/WPS 新证据；历史直接 runtime 结果不作为本任务新证据。

### 完成结论

- T4-001 严格范围内的计划、RED/GREEN、实现、focused/broad/security、实际浏览器视觉与
  交互、主会话顺序 deep review 和状态文档同步已完成；单一逻辑 commit 推送并确认远端
  `0 0` 后收口。
- T4-002 是下一唯一 `READY` 任务；新 Codex 任务必须重新读取 live 项目文档与 Git/origin
  状态，不得依赖聊天摘要，也不得提前实现 T4-003。

## T4-002 执行记录

### 范围

- 新增管理员用户查询、密码重置、状态变更、全局资产查询/preview/download/delete、
  积分调整与只读 audit HTTP 闭环；普通用户稳定 `403 admin_required`。
- 敏感操作逐次校验当前管理员密码与非空原因；Credential Reveal/Test、用户、积分和资产
  成功/失败均只追加脱敏 audit。preview/download 使用 POST JSON，不让密码/原因进入 URL。
- 管理员资产只接受 UUID，服务端从 `file_assets` 解析 owner 与 deterministic exact keys；
  复用引用、处理中状态、质量和派生文件删除 gate。删除 audit 记录活动文件状态与最长
  30 天备份残留策略，不伪造不受应用控制的备份已擦除。
- 五个 UI V1 敏感页面接入真实 frontend API；统一对话框覆盖动作/目标/后果、当前密码、
  原因、临时密码/积分金额、取消、提交防重复、结果反馈和 audit 跳转。

### Changed files

- Backend：admin/audit contracts、service、schema、API/router/application/error wiring，
  资产管理员动作与 Credential audit 脱敏。
- Frontend：统一敏感操作对话框、admin API/types/presentation、用户/Credential/资产/积分/
  audit 页面与 request JSON delete/POST download。
- Tests：`backend/tests/admin/`、`backend/tests/audit/` 与 Frontend admin contract。
- Records：T4-002 task card、task index、`docs/{API,DATA_MODEL,SECURITY,ENVIRONMENT,
  PROGRESS}.md`、`docs/ui-v1/IMPLEMENTATION.md` 与 `pitfalls.md`。
- 保留且未暂存：用户未跟踪 `.playwright-cli/`、`design-system/`、旧
  `docs/ui-mockups/` 与 ignored `output/`；未读取、打印或提交 `.env`、Secret、用户文件
  或未脱敏材料。

### TDD、focused 与浏览器证据

- RED：Backend 因缺少 `admin_operations`/`audit` 模块 collection 失败；Frontend 管理页
  4 个 contract 中 3 个因真实列表、Reveal 与统一对话框缺失按预期失败。
- GREEN focused：`tests/admin + tests/audit + tests/security + asset service` 最终
  `34 passed`；Frontend 管理/API/request `3 files / 12 tests passed`；Production Build
  `98 modules transformed`。
- Headed Chrome 在真实 Production Build 上使用受控 Mock API 验证资产、Credential、
  用户和 audit 页面；取消对话框敏感请求数为 0，Reveal 确认请求数为 1，默认值保持掩码。
- `1440px` 资产页与 `375px` audit 页页面级 overflow 均为 0；宽表只在受控 scroller
  内滚动；重新认证对话框与 UI V1 信息层级、暖瓷白/墨色/钢蓝及危险语义一致。
  最终 browser console 为 `0 errors / 0 warnings`。

### Broad、security、deep review 与 runtime

- Backend full：`552 passed, 2 skipped in 49.09s`；两项 skip 仅为未显式 opt-in 的真实
  Agnes Contract，T2-004 仍只有 Mock 通过。
- Frontend：`22 files / 59 tests passed`，Production Build 通过；PPT Renderer：
  `4 files / 20 tests passed` 且 build 通过。
- Ruff check 通过，Ruff format check 为 `323 files already formatted`；`pip check`
  通过；`pip-audit` 0 known vulnerabilities，仅跳过本地非 PyPI package；Frontend 与
  PPT Renderer `npm audit` 均为 0 vulnerabilities；Alembic 保持
  `20260723_0013 (head)`，本任务无 migration。
- 当前主会话顺序 deep review 修复：失败 audit 随业务异常回滚、Credential 保存完整
  IP/User-Agent、reason schema 在 actor/trace 前拦截失败、preview/download 敏感 GET
  URL，以及 Python/Vue 主文件超过 500 行。修复后无剩余 blocking security/logic finding。
- 任务卡 4 条 Docker 命令均实际尝试，PATH 无 `docker`，全部在容器启动前
  `CommandNotFoundException`。没有 Docker、真实 MySQL/Redis/Agnes/LibreOffice、
  Microsoft Office/WPS 新证据；受控 Mock/SQLite/offline 结果不冒充真实 runtime。

### 完成与下一任务

- T4-002 范围、RED/GREEN、实现、focused/broad/security、浏览器视觉与交互、主会话
  deep review 和状态文档同步完成；单一 commit 推送并确认远端 `0 0` 后收口。
- T4-003 依赖代码已满足，但任务卡要求的 10 组拥有使用权且已脱敏销售输入与明确期望
  指标尚未在本会话验证，因此保持 `BLOCKED`，没有伪造为唯一 `READY`，也不读取本地
  private golden data。外部前置确认后再创建新 Codex 任务并按启动顺序执行。

## T4-003 启动记录

### 用户批准与范围

- `2026-07-26` 用户确认 private 目录中的一份 XLSX 与一份 PPTX 均拥有使用权，并授权在
  不修改原件的前提下生成脱敏副本；同时明确没有更多数据，要求以该组进入 T4-003。
- 两个文件作为同一 `sales-pilot-v1` case：XLSX 为来源，PPTX 为参考输出，不拆分或复制
  冒充多组 corpus。任务与最终报告必须固定标记 `1/10 pilot`。
- 启动只读准入发现：XLSX 31 个 Sheet，其中 1 个空白；存在人员/客户/联系电话/地址信息
  和两个公式错误；PPTX 28 页，带作者 metadata 与 embedded objects。private 原件继续
  ignored，只有通过递归脱敏和安全扫描的副本才允许进入 Git。
- 20 次 PPT/20 次 Excel 重复运行用于验证同一 case 的确定性、结构、指标和引用，不证明
  10 组材料的业务多样性。真实 Agnes、LibreOffice、Microsoft Office/WPS 证据仍按实际
  runtime 单独报告。

### 交付与 TDD

- 新增 `golden-data/{inputs,expected,manifests}/`：tracked input 为 30 个安全命名
  worksheet，expected 为 4 页 PPTX 与 2-Sheet XLSX；Manifest 固定授权、`1/10 pilot`、
  5 个 artifact checksums、6 个指标、4 个 evidence IDs 与页/Sheet/chart requirements。
- 脱敏采用 fresh package regeneration：1677 个 cells 改写为 deterministic aliases，
  移除 1 个公式残留空白 worksheet、private metadata/drawings/旧 package payload，
  修复 2 个坏公式，并把 1 张 merged 汇总表规范化为机器可复算指标表。private 原件未修改。
- RED：Backend 因缺少 `app.services.golden` collection 失败；PPT golden 因缺少 Manifest
  失败。Microsoft Excel 实际打开后另观察到 rank `#NAME?` 与 chart print-area 裁切，
  对应 formula/axis/print-area tests 均先失败再实现。
- GREEN：strict Manifest/path/hash/security contracts、指标复算、Excel 20 次 deterministic
  generation、PPT 20 次 reference validation、Node 20 次 generation structural digest
  与脱敏 CLI 报告全部完成。PPT raw SHA 只固定 baseline；重复生成仅排除会变化的 core
  timestamp，其余 OOXML 与 media 全部进入 structural digest。

### Focused、broad、security 与实际 Office

- Focused：Backend golden `9 passed`；PPT golden `2 passed`；CLI 返回
  `spreadsheet_generation_runs=20`、`presentation_reference_runs=20`，并明确 PPT
  generation 由 Node suite 证明，不伪造 Backend 生成次数。
- Backend full：`561 passed, 2 skipped in 49.07s`；两项 skip 仍为真实 Agnes 未显式
  opt-in，T2-004 只有 Mock 通过。Ruff check/format、`pip check`、`pip-audit` 通过，
  Python 已知漏洞为 0，仅跳过本地非 PyPI package。
- Frontend：`22 files / 59 tests passed`、Production Build 通过；新 advisory 使
  dev-only `js-beautify 1.15.4` 链产生 6 个 high，精确 override 到 `2.0.3` 后测试/build
  不回归且 `npm audit` 为 0。PPT Renderer：`5 files / 22 tests passed`、build、audit 通过。
- 17 个 Python direct production dependencies、Frontend lockfile 203 个 package entries
  与 PPT Renderer 102 个 package entries 均无缺失 license metadata。
- corpus 递归语义扫描：private token、手机号/座机/邮箱、宏、external relationship、
  非目录 embedded payload、unsafe author 均为 `0`；input 30 Sheets/1042 formulas，
  expected workbook 2 Sheets/17 formulas。
- Microsoft PowerPoint 16.0 只读打开 expected PPTX 并实际导出 4/4 PNG；最终 4 页无
  空白、越界、标题截断、closing overlap 或重复 source footer。
- Microsoft Excel 16.0 只读打开 expected XLSX、`CalculateFullRebuild` 并实际导出 PDF：
  2 Sheets、1 chart、17 formulas、0 formula error；7 个 chart categories、标题和 print
  area 完整。`RANK.EQ` 改为兼容 `RANK`，避免缺少 `_xlfn.` 时的 `#NAME?`。

### Deep review、边界与下一任务

- 当前主会话按文件顺序 review；因用户禁止 subagent，没有启动独立 reviewer。修复
  Manifest requirements 未独立执行、generic worksheet 名编码漂移、Office formula 与
  chart visual gaps；最终无剩余 blocking security/logic finding。
- `docker` 实测为 `docker_command_not_found`，无法运行 Compose/MySQL/Redis/Worker/
  LibreOffice 故障演练；WPS/LibreOffice 未安装，真实 Agnes 未 opt-in。Microsoft Office
  单 runtime 证据不冒充 WPS、LibreOffice、容器或 Agnes 通过。
- T4-003 完成只解除 T4-004 代码依赖。T4-004 外部前置仍不满足并保持 `BLOCKED`，
  当前没有唯一 `READY` 任务，因此不创建下一 Codex 任务。

## T4-004 环境前置准备记录

### 用户决策与安全边界

- `2026-07-26` 用户要求将 Docker 安装到 `D:\works\tool\Docker` 并配置系统环境变量，
  长期授权 Agent 按最小必要原则读取仓库根 `.env` 用于本项目 runtime、真实 Agnes
  Contract 与配置验证；任何值仍不得回显、复制到 tracked 文件、暂存、提交或推送。
- 用户明确本机不安装 WPS，并自行负责 Microsoft Office 激活。T4-004 任务卡仍把
  Microsoft Office/WPS 双 runtime 作为硬性验收，因此该决定作为已知未通过边界保留，
  不把 Microsoft Office 单 runtime 证据提升为 Office/WPS 兼容通过。

### Docker Desktop 安装证据

- 主机为 Windows 11 x64，31.2 GB RAM；CPU SLAT 与 BIOS/UEFI virtualization 均启用，
  `LanmanServer` 为 `Running/Automatic`。
- 从 Docker 官方 Windows x86_64 下载入口取得 Docker Desktop Installer
  `4.83.0 (234302)`；Authenticode 状态为 `Valid`，签名者为 Docker Inc.，文件
  SHA-256 为
  `D812D89DA0CDA66C97CDF9DECB60DEBF17D71C358900DB33C48EB9EE9604F40C`。
- 官方 all-users installer 使用 WSL2 backend、禁用 Windows containers，将应用安装到
  `D:\works\tool\Docker`，WSL data root 配置为 `D:\works\tool\DockerData`。安装日志
  明确记录 `Installation succeeded`，并将 `D:\works\tool\Docker\resources\bin`
  写入 machine `PATH`。
- 当前 CLI 可执行：Docker Client `29.6.2`、Docker Compose `v5.3.1`、Docker Desktop
  CLI plugin `v0.4.2`。安装器刚启用 `VirtualMachinePlatform` 与
  `Microsoft-Windows-Subsystem-Linux`，Windows 明确要求 restart；重启前
  `com.docker.service` 为 stopped，`docker version` 只能返回 Client，daemon pipe
  不存在。因此本记录不声称 daemon、镜像 pull、Compose services、MySQL/Redis、
  LibreOffice 或故障演练已通过。

### 真实 Agnes 预检证据

- `.env` 在 `.gitignore` 命中 `*.env` 且未被 Git 跟踪；只检查必要变量是否存在并通过
  临时进程注入，未输出、记录或提交任何值。真实 Key 仅加密写入一次性 SQLite
  `provider_credentials`，测试后临时数据库和进程变量均清除。
- 使用 `.env` 中的真实 Agnes Key 与 text model，对
  `https://apihub.agnes-ai.com/v1/chat/completions` 发出最小文本请求：不带
  `response_format` 时 HTTP `200`，响应含 `choices` 与 `usage`，证明 endpoint、Key
  与基础文本模型可用。
- `backend/tests/providers/agnes_contract` 显式 opt-in 后为 `2 failed, 2 passed`：
  两个 Mock Contract 通过；最小文本与 synthetic sales 两个真实 Contract 均为 HTTP
  `400`。受控最小 probe 确认，只要增加
  `response_format={"type":"json_object"}` 即返回 `upstream_error/400`，上游明确说明
  当前 grammar backend 不支持 grammar-based JSON generation。
- 结论：真实 Agnes 基础文本访问已验证，但项目依赖的 Structured Output Contract 未
  通过；这不是缺 Key，也不得用 prompt-only JSON `200` 冒充 strict structured-output
  兼容。T4-004 在 Windows restart 后仍需 Docker 故障演练，并需对 Provider contract
  作出有测试和安全边界的处理；本次环境准备未修改业务 adapter。

### 重启后 runtime 复验与任务激活（2026-07-27）

- 从 Microsoft WSL `2.7.11` 官方 release 下载 x64 MSI；文件大小 `258990080`、SHA-256
  `A611DDACEE689D2FB1FB5319E58AF7F3998864D86CDCE632EADD8E61614A0F9D` 与 release
  metadata 一致，Authenticode 为 `Valid`，签名者为 Microsoft Corporation。安装后
  `wsl --version` 为 `2.7.11.0`，kernel 为 `6.18.33.2`。
- Docker Desktop `4.83.0` 状态为 `running`；`docker version` 返回 Client/Server
  `29.6.2`，WSL2 的 `docker-desktop` distribution 为 running，`docker run --rm
  hello-world` 通过。Compose 为 `v5.3.1`，项目 `docker compose config --quiet`
  exit `0`；data root 实际创建在 `D:\works\tool\DockerData`。
- WPS Office `12.1.0.26899` 的 `wps.exe`、`et.exe`、`wpp.exe` 已定位；Microsoft
  PowerPoint/Excel 为 `16.0.20131.20154`。版本与 executable discovery 只证明 runtime
  可用，真正的黄金文件无修复提示、视觉和交互仍须在 T4-004 内逐项验证。
- T4-003 已 `DONE`，上述外部 runtime gate 均满足，因此 T4-004 激活为唯一 `READY`
  任务。真实 Agnes `response_format` 400 保留为任务内 RED；先写 capability Contract，
  再做最小 compatibility 实现，并继续保持严格 Schema、一次 repair、错误分类和
  credential/prompt/response 不落日志边界。

### T4-004 执行计划

1. RED/GREEN：固定并实现 Agnes native structured-output capability fallback，先跑离线
   focused，再显式 opt-in 真实 Contract。
2. 在真实 Compose MySQL/Redis/Worker 中完成 Provider 错误、restart/recovery、
   idempotency、取消、部分成功、`provider_uncertain` 与积分恢复演练。
3. 对 tracked 黄金输出制作 ignored 工作副本，分别在 Microsoft Office 与 WPS 中实际
   打开并核对修复提示、结构、指标、公式、图表、字体与布局；原文件 hash 必须不变。
4. 完成任务卡 Docker 命令、broad/quality/security、当前主会话 sequential deep review，
   同步任务卡、索引、专题文档、`pitfalls.md` 与本记录；只精确暂存 T4-004 文件并形成
   一个 `test(alpha): ...` commit 后 push。

### T4-004 当前执行记录（2026-07-27）

#### RED/GREEN 与实现

- Agnes RED 固定真实上游不支持 native `response_format` 时的传输合同；GREEN 增加严格
  布尔 `native_response_format` capability，默认省略该字段，只有显式 `true` 才发送。
  Structured Brief 仍由应用层 strict Schema、Evidence 引用、一次 repair 和既有错误分类
  约束；没有改为宽松 JSON 或静默切换 Provider。
- 黄金 XLSX 在 Windows/Linux 生成的 OOXML entry 内容一致，但 XML newline 与 ZIP
  `create_system/external_attr` 元数据不同，导致 raw hash 跨 OS 漂移。新增 structural digest
  只忽略这两类非语义差异；tracked 期望 artifact 仍先按 Manifest 的 raw SHA-256/size
  fail closed 校验，实际 XML/relationship/entry name 或内容变化仍会失败。
- backend 镜像原先隐式依赖测试环境中的 `defusedxml`；已补为 production dependency，
  并用 security regression 固定。
- 真实 utf8mb4 MySQL 从空库首次暴露 `0005` storage locator 联合唯一键超过 InnoDB
  3072-byte 上限。由于 provider/key 均为服务端 ASCII locator，模型与 migration 同步使用
  `ascii_bin`；第一次成功升级后 `alembic check` 又暴露 `0011` 改 nullable 时丢失既有
  COMMENT，已在 upgrade/downgrade 显式保留并加回归。第二个隔离 utf8mb4 database 从
  revision 0 升级到 `20260723_0013 (head)`，`alembic check` 无 drift；旧失败 database
  均未删除。

#### 真实 Provider 与恢复演练

- 本地未跟踪 Credential 只通过一次性加密 SQLite/runtime 注入，未打印、复制或持久化
  Key、Prompt、response body；真实 Agnes Contract：`4 passed in 3.86s`。离线 Provider
  focused：`23 passed`；Provider/Brief/Outbox/Generation/Credits 容器 focused：
  `53 passed in 5.60s`。
- 隔离 failure-drill run ID `86d22c8a-bd5c-4254-96d7-9ad990a8325f`，四阶段各
  `1 passed`：创建 task/outbox/reserve 并验证 Idempotency-Key；真实停止 Redis 时 Outbox
  保持 pending、retry_count 增加且 reserve 不丢；Redis 恢复与新 worker 后只消费一次，
  duplicate delivery 不重复执行/结算；取消释放、部分成功 finalize/release、
  `provider_uncertain` 保留 reserve，safe/unsafe stale checkpoint 分别 requeue/uncertain。
- 故障测试默认 skip，只有显式 `OFFICE_AI_RUN_T4_FAILURE_DRILL=1` 和唯一 UUID 才运行；
  使用合成 identity、假 Credential，不访问用户文件或真实 Provider。

#### Docker、Office/WPS 与黄金回归

- Docker Desktop `4.83.0`、Linux Engine `29.6.2`、Compose `v5.3.1` 运行正常；
  MySQL `8.4.5`、Redis `7.4.5`、PPT Renderer、LibreOffice 均 healthy。重建 backend
  image 后：integration `5 passed`；Agnes 容器 Contract `2 passed, 2 skipped`
  （真实 live 默认不 opt-in）；黄金回归报告为 XLSX generation `20`、PPTX reference
  `20`、status `passed`；`soffice --version` 为 `25.2.3.2`。
- WPS Office `12.1.0.26899` 实际打开 ignored 工作副本：PPTX 共 4 页，逐页核对标题、
  指标表、业务员对比和结论页；XLSX 共 2 Sheet，经营数据表、完成率/同比、排名、经营
  看板和出货对比图均可见，无 repair prompt 或公式错误。弹出的“设为默认办公软件并开启
  防篡改保护”提示只按 `Escape` 关闭，没有启用系统级设置。
- 用户完成激活后，Microsoft PowerPoint/Excel `16.0.20131.20154` 实际打开同一 ignored
  副本。PowerPoint 放映模式逐页检查 4 页，Excel 切换检查“经营数据”和“经营看板”
  2 Sheet；中文、字体、表格、关键数字、公式结果、百分比格式、柱状图和布局均正常，
  无 repair、Protected View、登录或激活提示。OfficePLUS 模板推广层未授权，Excel
  “隐私设置已应用”只读通知未交互。
- 关闭 WPS/Excel 后复验：PPTX tracked expected 与工作副本 SHA-256 均为
  `c8359cc339ac8467c8430e6e2cb02da529397446769d531a42ab6c03d82a9d77`；XLSX 均为
  `0b9fcb65552b13bfa72a40323658a5763c86c314cc42734fcac95822ec2d414d`。真实桌面应用
  未改写验证文件。

#### 当前验证

- Backend broad：`567 passed, 6 skipped`；6 个 skip 均为默认关闭的真实 Agnes/failure
  opt-in。Ruff check/format check、`pip check`、`pip-audit` 通过且无已知漏洞。
- Frontend：`22` test files、`59 passed`，production build 通过，`npm audit --omit=dev`
  为 `0 vulnerabilities`。
- PPT Renderer：`5` test files、`22 passed`，build 通过，
  `npm audit --omit=dev` 为 `0 vulnerabilities`。
- T4-004 focused、Docker、broad、quality/security、真实桌面兼容和恢复演练 Gate 均
  已通过；任务卡/索引同步为 `DONE`，T4-005 仅激活为唯一 `READY`，未提前实现。

#### 当前 changed files

- Provider/Golden/Data：`backend/app/providers/agnes.py`、
  `backend/app/services/golden/runner.py`、`backend/app/models/file_assets.py`、
  `backend/alembic/versions/20260722_0005_projects_and_file_assets.py`、
  `backend/alembic/versions/20260723_0011_generation_outbox_credits.py`、
  `backend/pyproject.toml`。
- Tests：`backend/tests/providers/`、`backend/tests/golden/`、
  `backend/tests/assets/test_models.py`、`backend/tests/generation/test_models_migration.py`、
  `backend/tests/failure_drills/`。
- Records：T4-004 task card/index、T4-005 READY 状态、`docs/API.md`、`docs/DATA_MODEL.md`、
  `docs/ENVIRONMENT.md`、`docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。

## T4-005 执行记录

### 范围与 RED contract

- 严格只完成安全检查与 Alpha 封版；没有实现生产部署、支付、团队协作、用户模板或后续
  功能。启动时从 live repo 重新读取规则/状态/任务/专题文档，HEAD 与 `origin/main`
  均为 `c3d6b927423f042713a54301fbe39508d416f396`，ahead/behind `0/0`。
- Release report contract 在 `docs/ALPHA_RELEASE.md` 不存在时为 `3 failed`；21 表
  Alpha schema contract 在缺 `templates/system_settings` 时为 `3 failed`。最终两组
  focused 分别为 `3 passed` 和 `3 passed`。

### Runtime、migration 与外部证据

- 最终执行 `docker compose down --remove-orphans`（不删除 volumes）与
  `docker compose up -d --build --wait --wait-timeout 300`：9/9 services healthy；
  `/health/ready` 为 ready，MySQL/Redis 为 up。实际 PaddleOCR inference 识别
  `OFFICE AI 12345`，EICAR INSTREAM 被 ClamAV 检测。
- registry 中不存在原 ClamAV `1.4.2` 与 Paddle base `3.1.1` tag。Compose 固定
  ClamAV `1.4.5`；OCR 使用可解析的 Paddle `3.3.1` base，再固定安装经真实 inference
  验证的 PaddlePaddle `3.1.1` 与 PaddleOCR `3.7.0`。
- 独立 utf8mb4 MySQL validation database 从 base 升至 `20260727_0014 (head)`，
  `alembic check` 无 drift；实测 21 张业务表、40 个外键、22 个唯一约束。验证库未删除。
- 真实 Agnes 使用一次性加密 Credential/SQLite 与临时进程变量，`4 passed in 2.37s`；
  Key、Prompt、response body 未打印或持久化。Backend golden 为 20 次 XLSX generation
  + 20 次 PPTX reference；Node suite 为 20 次 PPTX generation，均 passed。
- Microsoft Office `16.0.20131.20154` 与 WPS `12.1.0.26899` 仍可定位；当前 tracked
  golden PPTX/XLSX hash 与 T4-004 人工打开前后记录完全一致。

### Focused、broad、security 与 deep review

- Backend full：`575 passed, 6 skipped in 40.13s`；6 个 skip 只包含默认关闭的 live
  Agnes/failure drill，本任务真实 Agnes 已独立通过。Integration：`5 passed`。
- Frontend：22 test files / `59 passed`，build 通过；PPT Renderer：5 test files /
  `22 passed`，build 通过。Renderer 默认 production stage 另行构建，并在
  non-root/read-only 容器成功 import。
- Backend `pip check`、`pip-audit`、Ruff check/format，Frontend/Renderer full
  `npm audit --audit-level=high` 均通过；248 个 source files 无超过 500 行文件。
- 当前主会话逐文件 deep review；没有使用 subagent。修复 21 表冻结契约缺口、容器
  test package/path portability、Vite read-only config loader、Renderer read-only build
  output 与 Node engine patch；最终无剩余 blocking logic/security finding。
- Git 预检：`.env` ignore 命中，nested negation 为 0，tracked/history forbidden path
  为 0，candidate added-line finding 为 0；全历史两个强特征启发式命中均为 task 文件名
  片段或明确 synthetic fixture。exact-path staging 共 37 个本任务文件；staged path、
  added-line、binary 与 `git diff --cached --check` Gate 均通过，用户已有未跟踪路径未进入
  staging。

### Changed files 与结论

- Schema：`backend/app/models/templates.py`、`system_settings.py`、model exports、
  `20260727_0014_alpha_schema_completion.py` 与 migration/schema regressions。
- Runtime：`docker-compose.yml`、OCR/Frontend/PPT Renderer Dockerfiles、Frontend/
  Renderer scripts/package contracts。
- Tests：Backend test package marker、release contracts、Compose/runtime portability
  regressions及历史 Head/表数断言同步。
- Records：T4-005 task card/index、`docs/ALPHA_RELEASE.md`、`docs/PLAN.md`、
  `docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、
  `docs/PROGRESS.md` 与 `pitfalls.md`。
- 结论：`ACCEPT_WITH_DECLARED_BOUNDARIES`。Internal Alpha 已封版且无下一
  dependency-ready task；`1/10 pilot`、ClamAV online signature refresh 和生产部署
  边界不被提升为已验证。

## Post-Alpha 默认运行端口迁移

### 范围与 TDD

- 用户明确要求本项目以后固定使用 Frontend `8888`、Backend `9999`，并立即以这两个
  端口重启；本变更不新增 Alpha 功能或 dependency-ready task。
- 先新增 Compose default-port contract；旧配置按预期以 Frontend 默认 `5173` 失败。
  最小修改四个默认值后 focused test 转为 `1 passed`，完整 Compose contract 为
  `3 passed`。
- Host mapping 改为 `8888->5173`、`9999->8000`；Frontend API base 改为
  `http://localhost:9999/api/v1`，Backend CORS origin 改为
  `http://localhost:8888`。容器内部端口、API 和 private-network contract 不变。

### Runtime 与验证

- 无临时环境覆盖的 `docker compose config` 实际解析为 `8888/9999` 以及一致的 API
  base/CORS origin。
- `docker compose up -d --force-recreate --wait --wait-timeout 180 backend frontend`
  成功；9/9 services healthy。
- `http://localhost:8888` 返回 200；`http://localhost:9999/health/ready` 返回
  `ready`，MySQL/Redis 均为 `up`；API docs 返回 200。
- 从 `http://localhost:8888` 到登录 API 的 CORS preflight 返回 200，allow-origin
  精确为 `http://localhost:8888`；先前临时 `5174/8001` 已无监听。
- Focused + release contract：`9 passed`；`docker compose config --quiet`
  和 `git diff --check` 通过。
- Exact-path staging 共 8 个本任务文件；unexpected/missing/forbidden path、binary、
  tracked forbidden path、Secret signature 和 env allowlist negation 均为 0，
  staged security Gate 通过。

### Changed files 与边界

- Plan/config/test：`.hermes/plans/2026-07-27-office-ai-runtime-ports.md`、
  `docker-compose.yml`、`backend/tests/assets/test_compose_contract.py`。
- Records：`README.md`、`docs/PLAN.md`、`docs/ENVIRONMENT.md`、
  `docs/PROGRESS.md`、`pitfalls.md`。
- 未修改或读取根 `.env`；未触碰/未暂存 `.playwright-cli/`、`design-system/`、
  旧 `docs/ui-mockups/`、ignored `output/`、Secret 或用户文件。
- 结论：默认端口迁移完成，Internal Alpha 状态和既有声明边界不变，下一
  dependency-ready task 仍为无。

## Post-Alpha 空项目首份材料上传修复

### 根因与 TDD

- 真实浏览器与 API 数据流确认：空库管理员的 `GET /projects` 返回空数组，Skill、模型、
  Backend readiness 与 Console 均正常；前端却因 `projectId` 为空禁用文件输入。
- 后端既有 contract 支持上传时省略 `project_id` 并幂等创建唯一默认项目；前端强制
  `project_id` 造成项目选择与首份上传互相等待。
- RED：workspace multipart、空项目提示/文件输入、首份上传调用共 `3 failed`；最小修复后
  focused 为 2 files / `8 passed`。

### 实现与验证

- `workspaceApi.uploadAsset` 接受未指定项目，并只在存在项目时写 multipart
  `project_id`；已有项目流程不变。
- 空项目选择框显示“上传首份材料后自动创建默认项目”，文件输入只在实际上传期间禁用；
  上传完成后重新加载既有 workspace options。
- Frontend full：22 files / `62 passed`；`vue-tsc -b` 与 Vite build 通过。
- Backend 既有默认项目 contract：
  `test_upload_creates_default_project_and_quarantined_asset` 为 `1 passed`。
- 重建 Frontend 后 `http://localhost:8888` 返回 200，Backend `/health/ready` 为
  `ready`。真实 Chrome 空项目页面显示占位 option，上传按钮 enabled，点击成功触发单文件
  chooser，未选择或上传任何文件，Console 无 warning/error。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-empty-project-upload-fix.md`。
- Frontend：`frontend/src/modules/workspace/{api.ts,api.test.ts}`、
  `frontend/src/views/user/{workflow-new.vue,workflow-new.test.ts}`。
- Records：`docs/PLAN.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未修改后端、数据库或 API contract；未上传用户文件，未触碰 `.env`、
  `.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/` 或 ignored `output/`。
- 结论：空项目首用死锁已修复；Internal Alpha 状态和既有声明边界不变，下一
  dependency-ready task 仍为无。

## Post-Alpha 应用卷权限上传修复

### 根因、RED 与实现

- 真实 Chrome 上传请求已到达 `POST /api/v1/assets/uploads`；Backend traceback 明确为
  non-root UID/GID `10001:10001` 创建 `/app/files/users` 时触发
  `PermissionError`，因此浏览器只显示 `Failed to fetch`。
- `app-files`、`parsed-files`、`evidence-files` 与 `shared-work` 四个 Compose named
  volume 冷创建后均为 `root:root / 0755`。镜像内目录 ownership 会被 volume mount
  覆盖；已有 healthcheck 未执行首次写入，未发现该缺口。
- RED contract 先因缺少 `storage-init` 以 `KeyError` 失败；新增一次性、无网络、无
  environment/Secret、read-only rootfs initializer 后转为 `1 passed`。四个长期 writer
  均继续使用 `10001:10001`，并等待 `service_completed_successfully`。
- initializer 只对四个应用卷根目录执行 ownership/mode 初始化，不删除或扫描文件；
  MySQL/Redis/ClamAV volume、上传 API、Schema、storage key 与业务服务均未修改。

### Runtime 与验证

- 四个临时 fresh Docker volume 实测初始化后均为 `10001:10001 / 0750`，non-root
  写入四个 probe 目录成功；临时 volumes 在同一验证流程中全部删除，没有创建新数据库。
- `docker compose up -d --build --wait --wait-timeout 240` 成功：
  `storage-init` exit `0`，其余 9 个长期服务全部 healthy；Host Frontend `8888` 与
  Backend `9999/health/ready` 均返回 200。Backend/Worker/Renderer 中四个挂载点实际
  ownership/mode 全部为 `10001:10001 / 0750`。
- 真实 runtime 合成 TXT probe 调用同一 `AssetUploadService`，使用现有 admin owner，
  经过真实 MySQL、`app-files`、Worker、ClamAV、parsed/evidence volume，状态为
  `quarantined -> ready -> deleted`。当前 active asset 为 0，四个应用卷文件数为 0；
  数据库仅保留 1 条符合既有删除 contract 的 soft-deleted tombstone。
- Chrome 刷新后显示“默认项目”和 enabled“上传一份材料”，无 `Failed to fetch`、
  console warning/error。自动化安全策略不允许将 Agent 创建的合成文件注入 Chrome；
  runtime probe 因而绕过登录层，但没有绕过本次失败的上传/存储/处理层。管理员既有密码
  未被重置或绕过。

### 回归、文件与边界

- Focused Compose/volume：`14 passed`；Backend full：
  `577 passed, 6 skipped`，skip 仅为未 opt-in 的既有真实 Agnes/故障演练。
- Ruff check、Ruff format `341 files already formatted`、`pip check` 与
  `pip-audit` 通过；`pip-audit` 为 0 known vulnerabilities，仅跳过本地非 PyPI package。
  Frontend full：22 files / `62 passed`；production build `98 modules transformed`，
  `npm audit --audit-level=high` 为 0 vulnerabilities。
- Plan/test/runtime：`.hermes/plans/2026-07-27-office-ai-volume-permission-upload-fix.md`、
  `backend/tests/assets/test_compose_contract.py`、`docker-compose.yml`。
- Records：`docs/PLAN.md`、`docs/PROGRESS.md`、`docs/ENVIRONMENT.md`、
  `docs/SECURITY.md`、`pitfalls.md`。
- 仅最小读取根 `.env` 中两个 bootstrap admin 变量是否存在，结果均为未配置；没有输出、
  复制、暂存或提交任何值。未读取/上传用户文件，未触碰受保护的 `.playwright-cli/`、
  `design-system/` 与旧 `docs/ui-mockups/`；临时 ignored synthetic 文件已删除。
- 结论：应用 volume 首次写入缺口已修复；Internal Alpha 与 `1/10 pilot` 等既有声明
  边界不变，下一 dependency-ready task 仍为无。

## Post-Alpha 材料处理反馈与 Evidence 状态修复

### 根因与 RED contract

- 真实 Browser/API/Worker/MySQL 证据确认上传接口已返回 `201`，当前 4 条 active 资产均已
  落库，但因 `excel_sheet_limit_exceeded` 被安全拒绝；前端只渲染 ready 材料，造成“上传
  成功后消失”，且立即 reload 后没有继续轮询。
- 同链路发现 Worker 与 T2-002 测试的成功组合为
  `processing_status=ready / manifest_status=valid`，而 Workflow、Brief 和 Preflight
  仍要求旧的 `ready/ready`，会把后续合规材料误判为不可用。
- RED：Workflow focused 为 `4 failed, 3 passed`；Brief/Preflight 使用真实 Worker
  fixture 后为 `13 failed, 7 passed`。测试固定拒绝原因展示、处理中自动刷新、
  `ready/valid` 可选择以及无效材料继续 fail closed。

### 实现与验证

- Workflow 显示 selected project 的全部 active 材料；拒绝材料显示脱敏原因，
  `excel_sheet_limit_exceeded` 明确提示精简至不超过 30 张工作表后重新上传；非 ready
  材料不提供选择框且不能启用生成。
- 处理中材料每 `1.5s` 背景刷新，离开页面或进入终态后停止；刷新不切走表单，处理成功后
  按既有 defaults flow 自动选择首条 `ready/valid` 材料。
- Brief input loader 与 Preflight evaluator 统一接受 Worker 权威的 `ready/valid` 组合；
  Manifest key/SHA、owner/project/version、invalid/retryable/rejected 等既有门禁不变。
- Focused：Workflow `7 passed`，Brief/Preflight `57 passed`。Broad：Frontend
  22 files / `64 passed`，production build `98 modules transformed`；Backend
  `577 passed, 6 skipped`，6 个 skip 仍为默认关闭的 live Agnes/failure drills；Ruff
  changed-file check 通过。
- 只重新构建并 `--no-deps --force-recreate` Backend/Frontend；MySQL/Redis 与用户资产
  未重建或清理。实际映射为 `8888->5173`、`9999->8000`，两服务均 healthy。
- 真实 Chrome 显示 4 条拒绝资产及统一安全原因，项目选择框存在，继续按钮 disabled，
  Console 无 warning/error；未读取资产内容、未上传或删除用户文件。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-asset-processing-feedback-fix.md`。
- Backend：`backend/app/services/{briefs/inputs.py,preflight/evaluator.py}` 与对应
  `tests/{briefs,preflight}/conftest.py`。
- Frontend：`frontend/src/views/user/{workflow-new.vue,workflow-new.test.ts}`。
- Records：`docs/PLAN.md`、`docs/API.md`、`docs/DATA_MODEL.md`、
  `docs/PROGRESS.md`、`pitfalls.md`。
- 30-Sheet 安全上限、数据库 Schema、API shape、owner scope、4 条拒绝记录和用户文件
  保持不变；未读取 `.env`，未触碰受保护的 `.playwright-cli/`、`design-system/`、
  旧 `docs/ui-mockups/` 或 ignored `output/`。
- 结论：上传状态现在可见且可恢复，合规材料可沿 `ready/valid` 进入 Brief/Preflight；
  当前 4 条超限材料仍需精简后重新上传。Internal Alpha 及既有声明边界不变，无下一
  dependency-ready task。

## Post-Alpha Excel 100-Sheet 上限与拒绝材料删除

### 计划、RED 与实现

- 用户批准将 Excel 输入上限从 30 Sheet 调整为 100 Sheet，并要求未通过材料可在行右侧
  主动删除；本次按唯一 Post-Alpha 任务执行，不启动下一 Alpha 任务。
- RED contract 固定三处运行时默认值一致、100 Sheet 接受且第 101 Sheet 稳定拒绝，以及
  前端只对 `rejected/invalid` 显示删除操作。Frontend 首次为 `5 failed, 8 passed`，
  Backend 首次为 `6 failed, 12 passed`。
- Settings、`ProcessingLimits` 与 Compose worker 默认值统一为 100；30 万非空单元格、
  20 文件/200 MB、Archive、内存、timeout、ClamAV 与 owner scope 等门禁保持不变。
- Workflow 复用既有 owner-scoped `DELETE /assets/{asset_id}`；`×` 采用可访问名称，
  按文件名确认后调用一次删除。只有成功响应才移除对应行，取消或失败时保留材料并在行内
  显示安全错误；处理中或 ready 材料不显示该操作，且没有自动删除。

### 验证与 Runtime 证据

- Focused GREEN：Frontend `13 passed`；Backend `18 passed`。
- Broad：Frontend 22 files / `67 passed`，production build
  `98 modules transformed`；Backend `577 passed, 6 skipped`，skip 仍仅为默认关闭的
  live Agnes/failure drills；Ruff changed-file check 通过。
- Security/dependency：Frontend `npm audit --audit-level=high` 为 0 vulnerabilities；
  Backend `pip check` 无 broken requirements，`pip-audit` 为 0 known vulnerabilities，
  仅跳过本地非 PyPI package `office-ai-backend`。
- `docker compose build worker frontend` 成功；只用 `--no-deps --force-recreate`
  重启 worker/frontend，未重建 Backend、MySQL、Redis 或用户数据。worker 实际读取
  `OFFICE_AI_MAX_EXCEL_SHEETS=100`，Frontend `8888`、Backend `9999` 与依赖均 healthy，
  `/health/ready` 和前端首页均返回 200。
- 真实 Chrome 2048 px desktop 页面显示 4 条拒绝材料、4 个右侧 `×`、4 条
  “超过 100 个”提示，继续按钮 disabled；Console 无 warning/error，仅有重启期间 Vite
  连接日志。没有点击删除、读取材料内容或改变现有 4 条用户记录。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-excel-limit-rejected-asset-delete.md`。
- Backend/Runtime：`backend/app/settings/config.py`、
  `backend/app/services/file_safety/contracts.py`、`docker-compose.yml` 与对应 parsing/
  file-safety tests。
- Frontend：`frontend/src/modules/workspace/{api.ts,api.test.ts}`、
  `frontend/src/views/user/{workflow-new.vue,workflow-new.test.ts}`。
- Records：`docs/PLAN.md`、`docs/API.md`、`docs/ENVIRONMENT.md`、
  `docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 历史 T2-001 任务卡保留当时的 30-Sheet Alpha contract；本节、当前计划和现行专题文档
  记录用户批准的 Post-Alpha 100-Sheet 覆盖。数据库 Schema、API shape、现有 4 条资产、
  `1/10 pilot` 与 Alpha 封版证据边界不变。
- 未读取 `.env`、Secret 或用户文件；未触碰/未暂存 `.playwright-cli/`、
  `design-system/`、旧 `docs/ui-mockups/` 或 ignored `output/`。下一
  dependency-ready task 仍为无。

## Post-Alpha private 黄金 XLSX Evidence 限制校准

### 授权、测量与 RED

- 用户明确授权只读使用 `golden-data/private/` 中唯一 XLSX 作为当前最高输入规模标准；
  private 文件继续被 `.gitignore` 覆盖，未复制、修改、输出或暂存其正文、文件名、hash
  与 metadata。
- Artifact Tool 结构测量为 31 Sheet、10,465 个非空单元格；生产 parser/Evidence
  builder 进一步确认过滤前 source expansion 为 11,563 项，过滤后最终 Evidence 为
  10,465 条，Manifest 约 7.48 MB。
- 初始按最终 Evidence 数 10,465 设限时，生产同链路仍以
  `evidence_item_limit_exceeded` 拒绝，证明预算发生在空值过滤前；纠正后的 RED 为
  Backend `3 failed, 8 passed`、Frontend `1 failed, 10 passed`。
- 最终 contract 精确接受 11,563 个 source item，第 11,564 项稳定拒绝。Settings、
  Evidence builder default、Compose worker 与用户提示统一为 11,563。

### 验证与 Runtime

- Focused GREEN：Backend `11 passed`；Frontend `11 passed`。黄金 XLSX 使用生产
  parser 与默认 builder 只读复验成功，仍生成 10,465 条 Evidence 与约 7.48 MB
  Manifest。
- Broad：Backend `579 passed, 6 skipped`，skip 仅为未 opt-in 的 live Agnes/failure
  drills；Frontend 22 files / `68 passed`，production build `98 modules transformed`；
  Ruff changed-file check 通过。
- Security/dependency：Frontend `npm audit --audit-level=high` 为 0 vulnerabilities；
  Backend `pip check` 无 broken requirements，`pip-audit` 为 0 known vulnerabilities，
  仅跳过本地非 PyPI package `office-ai-backend`。
- `docker compose build worker frontend` 成功；只用 `--no-deps --force-recreate`
  重启 worker/frontend，未重建 Backend、MySQL、Redis 或用户数据。worker 实际读取
  `OFFICE_AI_MAX_EVIDENCE_ITEMS=11563`；Frontend `8888`、Backend `9999` 与依赖均
  healthy，前端首页和 `/health/ready` 返回 200。
- 真实 Chrome 当前账号已无 active asset，因此没有伪造 rejected row 或重新上传 private
  文件；页面上传按钮 enabled、继续按钮 disabled，Console 无 warning/error，仅有重启
  期间 Vite 连接日志。11,563 提示由 focused UI contract 覆盖。

### 安全边界与 Changed files

- 黄金 Manifest 的 5,193 个 `numeric_unit_unknown` blocker 保持原样；数量限制通过不等于
  语义冲突被解决，Preflight 仍要求术语/单位明确，禁止静默猜测。
- 10 MB Manifest、100 Sheet、30 万非空单元格、Archive、parser structural、timeout、
  memory、ClamAV、owner scope、immutable Evidence、API shape 与数据库 Schema 均不变。
- Plan：`.hermes/plans/2026-07-27-office-ai-golden-evidence-limit-calibration.md`。
- Backend/Runtime：`backend/app/services/evidence/builder.py`、
  `backend/app/settings/config.py`、`docker-compose.yml` 与对应 evidence/OCR tests。
- Frontend：`frontend/src/views/user/{workflow-new.vue,workflow-new.test.ts}`。
- Records：`docs/PLAN.md`、`docs/API.md`、`docs/ENVIRONMENT.md`、
  `docs/SECURITY.md`、`docs/PROGRESS.md`、`pitfalls.md`。
- 未读取 `.env` 或 Secret，未修改/暂存 private workbook、`.playwright-cli/`、
  `design-system/`、旧 `docs/ui-mockups/` 或 ignored `output/`。黄金覆盖仍为
  `1/10 pilot`，下一 dependency-ready task 仍为无。

## Post-Alpha Structured Brief Context 压缩修复

### 根因、RED 与实现

- 当前 MySQL 中唯一 active 材料为 `ready/valid`，包含 10,465 条 Evidence、5,193 个
  blocker；发布模型为真实登记的 `262144` Context 与 `8192` max output。
- 旧 `build_evidence_context` 为每条 Evidence 重复完整 asset UUID、asset version 和
  location JSON，并直接携带 66 字符 Evidence ID；同一材料形成 4,256,561 bytes /
  1,418,854 估算 token，超过扣除 output/fixed reserve 后的 251,904 token。
- RED 新增黄金规模 10,465 条 synthetic Evidence、短引用映射、未知引用拒绝和 service
  落库 contract；首次 local collection 以缺少
  `resolve_brief_evidence_references` 的 `ImportError` 失败。
- GREEN 新增 `brief-evidence-context.v2`：asset identity/version 只出现一次，Evidence
  按 asset、location kind、Sheet 和 type 分组，使用确定性 `r<base36>` 短引用。
  Agnes 响应只允许本次短引用；应用在 strict Schema/snapshot/evidence 校验前映射回
  原始 Evidence ID，未知引用及未暴露 raw ID 均 fail closed。
- 没有抽样、截断、改写 raw/normalized value 或虚增模型能力；calculated provenance、
  owner scope、Manifest integrity、一次 repair 与 Provider error policy 保持不变。

### Focused、真实 Runtime 与 Agnes

- Backend Brief focused 最终为 `33 passed`；Ruff focused check/format 均通过。
- 用当前 `ready/valid` 材料和生产 Evidence Manifest store 只读复核：
  `10,465/10,465` Evidence 与引用全部保留，v2 Context 为 `521,684` bytes /
  `173,895` 估算 token，剩余 evidence budget 为 `78,009` token。
- 使用 combined Skill、当前模型快照和同一材料构造完整 production messages，
  `enforce_message_budget` 通过：Prompt `597,421` bytes / `199,141` 估算 token，
  加 `8,192` output 后总计 `207,333 < 262,144`。
- 真实 Agnes Contract 使用 runtime 中已加密 Credential 显式 opt-in，结果为
  `4 passed`（最终镜像复验 `10.28s`）；没有打印或持久化 Key、Prompt、response body
  或用户材料。
- 重建并重启 Backend 后，Host `9999/health/ready` 返回 `ready`，MySQL/Redis 均为
  `up`；真实 Chrome 页面保留已选黄金材料、两个 Skill 和模型，继续按钮 enabled。
- 未代替用户点击继续按钮，避免在未获得当下明确确认时把包含个人信息的完整材料再次
  发送给外部 Provider；用户可在保留的页面亲自触发真实材料生成。

### Broad、Security 与边界

- Backend full 最终为 `584 passed, 6 skipped`；6 个 skip 仍仅为默认关闭的
  4 个 failure drill 与 2 个 live Agnes case，live Agnes 已在独立 opt-in run 通过。
- 一次在带 runtime Secret 的 Compose service environment 中运行全量 suite 时，
  2 个“Secret 未提供时应为 None”的配置隔离测试按预期失败，其他为
  `581 passed, 6 skipped`；改用无 Secret 的本地 test runtime 后全量通过，不将该环境
  污染误报为产品回归。
- Ruff 全量 check 通过，format 最终无差异；`pip check` 无 broken requirements，
  `pip-audit` 为 0 known vulnerabilities，仅跳过 editable local package。
- Plan：`.hermes/plans/2026-07-27-office-ai-brief-context-compaction.md`。
- Backend：`backend/app/services/briefs/{context.py,prompting.py,service.py,validation.py}`
  与对应 `backend/tests/briefs/` contract。
- Records：`docs/PLAN.md`、`docs/API.md`、`docs/SECURITY.md`、
  `docs/PROGRESS.md` 与 `pitfalls.md`；数据库 Schema、环境配置和前端 API shape 不变。
- 未读取 `.env` 或 Secret，未修改/暂存 private workbook、`.playwright-cli/`、
  `design-system/`、旧 `docs/ui-mockups/` 或 ignored `output/`；5,193 个
  `numeric_unit_unknown` blocker、`1/10 pilot` 边界和“无下一 dependency-ready task”
  均保持不变。

## Post-Alpha durable 异步工作流任务与失败记录

### 根因与实现

- 用户点击继续后，旧前端同步等待 `POST /briefs/generate`；真实 Runtime 分别观察到约
  110 秒 `502` 与约 88 秒 `422`。后一次经过 Agnes 初次和 repair 两次 `200`，最终因
  strict Schema 返回 `brief_schema_invalid`。Brief 成功前数据库没有任务，`/tasks`
  又是静态占位，因此处理中和失败均无记录。
- 新增 `workflow_tasks` 与 migration `20260727_0015`。`POST /workflow-tasks` 在短事务
  内写 task + Outbox 并立即返回；独立 workflow worker 后台整理 Brief，成功进入
  `awaiting_confirmation`，失败保留 stable code、安全原因和备注。
- Frontend 新建任务后立即进入 `/tasks/{task_id}`；任务列表/详情调用真实 API 并轮询
  非终态，显示输出、状态、0–100 进度、备注、失败原因和积分。确认 Brief 后按 group
  自动关联现有 generation task，并投影其权威状态。

### 验证与 Runtime 证据

- RED 依次覆盖缺少 model/migration、service/API、worker、Compose contract、
  generation link，以及前端 API/list/detail/route；GREEN focused Backend
  `71 passed`。
- Broad：Backend `597 passed, 6 skipped`，6 个 skip 仍仅为默认关闭的 4 个 live
  failure drill 与 2 个 live Agnes case；Ruff 全量 check/format 通过。Frontend
  23 files / `70 passed`，production build `101 modules transformed`。
- 真实 MySQL 从 `20260727_0014` 升级到唯一 `20260727_0015 (head)`；
  `alembic current` 与 `alembic check` 均通过。Backend image 顺序重建成功，
  Backend/Frontend/workflow-worker 无依赖强制重建后 10 个长期服务 healthy；
  Host `9999/health/ready=ready`，Frontend `8888=200`。
- Backend image 内 workflow tests `12 passed`。Backend `pip check` 无 broken
  requirements，`pip-audit` 为 0 known vulnerabilities（仅跳过本地非 PyPI package）；
  Frontend `npm audit --audit-level=high` 为 0 vulnerabilities。
- 真实浏览器在没有登录 Session 的新标签访问 `/tasks`，按鉴权 contract 重定向登录页；
  未读取凭证、未代替登录，也未为 QA 再触发 Agnes。已登录任务列表、详情轮询、失败保留
  由组件 contract 覆盖；下一次用户提交会创建新 canonical task，修复前的同步失败不会
  伪造或回填为历史记录。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-async-workflow-tasks.md`。
- Backend：workflow model/migration/API/services/worker、Outbox 分流、Brief identity
  执行入口、generation group 关联与对应 tests。
- Frontend：workspace workflow API/type、新建任务异步提交、真实任务列表与详情、
  route 和对应 tests。
- Runtime/Records：`docker-compose.yml`、`docs/PLAN.md`、`docs/API.md`、
  `docs/DATA_MODEL.md`、`docs/ENVIRONMENT.md`、`docs/SECURITY.md`、
  `docs/PROGRESS.md` 与 `pitfalls.md`。
- 同步 `/briefs/generate` 只作为兼容 API 保留；Structured Brief/Evidence/Preflight/
  积分/质量 Gate 均未降低。不保存 Provider 原始响应或 Prompt，不自动重试
  `provider_uncertain`，不回填修复前没有 canonical task 的历史同步失败。

## Post-Alpha Structured Brief Schema guidance 修复

### Runtime 根因

- 最新 workflow task `019fa32b-9a5b-78a6-80a7-8c398a4dc579` 正确持久化
  `failed / brief_failed / brief_schema_invalid`；其 Agnes attempt 1/2 都成功返回，
  分别约 47 秒与 90 秒。数据库最近 3 组、共 6 次成功 Provider response 全部在应用层
  strict Schema 校验失败，证明问题位于 Provider response -> validation 边界。
- `generation_messages` 只传 17 个顶层字段名，没有传 nested required、Literal、长度、
  `extra=forbid` 与 validator contract；generic repair 也没有告诉模型失败字段和类型。
  `temperature=0` 下模型无法可靠推导或定位修复目标。

### TDD 与实现

- RED focused 为 `4 failed, 17 passed`：分别缺少完整 Schema、repair hints 参数、
  `BriefValidationError.repair_hints` 与 service 透传。
- GREEN 在 generation payload 加入紧凑的完整 Pydantic JSON Schema；Pydantic error
  只提取已知字段路径、数组索引和固定 type，未知字段归一为 `unknown_field`。hints
  限制为最多 24 条、每条 160 字符，仅用于同一次 repair conversation。
- Provider response、Prompt、字段值与 validation input 仍不持久化/记录；strict
  Pydantic、snapshot、Evidence allowlist、一次 repair、`provider_uncertain` 与
  native `response_format=false` 均保持不变。

### 验证与 Runtime

- Brief focused `37 passed`；Backend full 最终 `600 passed, 7 skipped`，7 个 skip
  为默认关闭的 4 个 failure drill 与 3 个 real Agnes case；Ruff 377 files clean。
- 显式 opt-in 的新增 real Agnes Contract 使用完全合成销售 Evidence，执行生产
  `Schema guidance -> generation -> optional repair -> strict validation`，结果
  `1 passed in 5.64s`。未读取用户文件，未输出 Key、Prompt 或 response。
- `pip check` 无 broken requirements，`pip-audit` 无已知漏洞。Backend image 重建成功；
  Backend/workflow-worker 重建后均 healthy，Host `/health/ready=ready`。
- 旧失败 workflow task 保留为审计事实且不自动重放；新 Schema guidance 对新建任务
  生效。真实用户大材料的最终验收需要用户重新新建任务，不能用合成 Contract 冒充。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-brief-schema-repair.md`。
- Backend：`briefs/{prompting.py,validation.py,service.py}` 与 Brief/real Agnes tests。
- Records：`docs/PLAN.md`、`docs/API.md`、`docs/SECURITY.md`、
  `docs/PROGRESS.md` 与 `pitfalls.md`。
- 不修改数据库 Schema、API shape、Frontend、Environment、用户文件或旧任务状态；
  不触碰/暂存 `.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/` 或
  ignored `output/`。

## Post-Alpha Preflight 引用范围与单位解决

### Runtime 根因与修复

- 当前真实 Brief 有 4 个 facts、2 个 inferences、2 个 outputs、0 个
  `unresolved_items`；17 次 Evidence 引用去重后为 12 个唯一 ID，其中 9 个单位未知。
- 旧 Preflight 对整份 10,465 Evidence Manifest 扫描，5,193 个
  `numeric_unit_unknown` 又被 Evidence warning 以 `unit_unknown` 重复加入，最终形成
  `5,193 + 5,193 + 1 auto_merge = 10,387` 个 conflicts，页面显示 10,386 个阻断项。
- 新实现只检查当前 Brief 实际引用的 Evidence，并将
  `numeric_unit_unknown -> unit_unknown`、
  `ocr_numeric_low_confidence -> numeric_low_confidence` 后按
  `code + level + evidence_ids` 去重。当前 Runtime 结果为 9 个单位阻断和 1 个非阻断
  `skill_inputs_shared`。
- 单位阻断消息提供 Sheet/单元格等安全定位；用户从受支持的 canonical unit 下拉框显式
  选择，`PATCH` 只接受匹配当前 Preflight blocker 的 resolution，并追加新 Revision。
  Resolution 固化到 `source_snapshot` 和 generation Brief input snapshot；原始 Manifest、
  Evidence 和历史 Revision 均不改写。

### TDD、Broad 与真实 Browser

- RED：Backend Preflight 3 个失败，分别锁定非法 unit 未拒绝、未引用 Evidence 被阻断与
  Manifest/Evidence 重复计数，以及 resolution 无法匹配 Evidence blocker；Generation
  1 个失败锁定 input snapshot 未携带 resolution；Frontend 1 个失败锁定缺少单位选择。
- GREEN focused：Preflight `25 passed`、Generation `7 passed`、相关模块合计
  `50 passed`；Frontend Brief `4 passed`。Frontend full 为 23 files / `71 passed`，
  最终 production build `104 modules transformed`。
- Backend full 为 `602 passed, 7 skipped`；skip 仍仅为默认关闭的 4 个 live failure
  drill 与 3 个 real Agnes case。Ruff 360 files check/format 通过。
- Backend `pip check` 无 broken requirements，`pip-audit` 无已知漏洞，仅跳过本地非
  PyPI package；Frontend `npm audit --audit-level=high` 为 0 vulnerabilities。
- 重建 Backend/Frontend 并只强制替换应用容器，MySQL/Redis 与用户数据未重建；
  Backend/Frontend healthy，Host `/health/ready=ready` 与 Frontend 返回 200。
- 生产服务直接只读评估当前 Brief：12 个唯一引用、9 个 `unit_unknown`、1 个
  `skill_inputs_shared`。真实 Chrome 刷新同一已登录页面后显示 9 个带来源位置的单位
  下拉框，确认按钮 disabled，Console 无 warning/error；未选择单位、未提交 Revision。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-preflight-referenced-unit-resolution.md`。
- Backend：Preflight contract/evaluator/service、generation input snapshot 与对应 tests。
- Frontend：Brief types、确认页、action styles 与 component test。
- Records：`docs/PLAN.md`、`docs/API.md`、`docs/SECURITY.md`、
  `docs/PROGRESS.md` 与 `pitfalls.md`；数据库 Schema、Environment、Provider 与用户文件
  不变。
- 未打开、输出或修改用户文件正文，未自动猜测单位，未替用户提交页面；未触碰/暂存
  `.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/` 或 ignored `output/`。

## Post-Alpha Preflight 单位操作闭环与滚动修复

### 根因与实现

- 单位下拉只更新页面临时 state，唯一保存入口位于左侧 Brief 编辑卡片；右侧长 blocker
  列表与左侧保存动作无法同时看见。完成 9/9 选择后，服务端 Preflight 尚未刷新，因此
  生成按钮保持 disabled，但旧页面没有解释下一步。
- 单位列表改为有可见滚动条、键盘 focus 和 responsive 高度上限的独立区域；滚到列表
  边界后仍可继续滚动页面。阻断区底部显示 `已选 x/y`，全部完成后启用“保存 n 个单位并
  重新校验”。
- 保存继续复用既有 immutable Revision PATCH；成功后刷新 Preflight。单位未选完、
  已选但未保存、存在其他 blocker 与 clean 状态分别显示准确的主按钮文案。

### TDD、Broad 与 Runtime

- 首次 Compose focused 命令误用了旧 Frontend image，未计入证据；重建 image 后真实 RED
  为 `1 failed, 3 passed`，锁定缺少滚动区和右侧保存动作。GREEN focused 为 `4 passed`。
- Frontend full 为 23 files / `71 passed`；production build 为
  `104 modules transformed`；`npm audit --audit-level=high` 为 0 vulnerabilities。
- 只重建并强制替换 Frontend；Backend、workflow worker、MySQL、Redis 与用户数据未重建。
  Frontend/Backend/workflow worker/MySQL/Redis 均 healthy，Frontend Host 返回 200。
- 真实 Chrome 只读确认当前用户已通过旧入口形成 Revision 2 并创建 generation task；
  未再次保存或确认。2048px 为双栏且无横向 overflow，375px 为 343px 单栏且无横向
  overflow，Console 无 warning/error；验收后恢复到用户原 generation 详情页。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-preflight-unit-action-scroll.md`。
- Frontend：Brief 确认页、单位列表、action styles 与 component test。
- Records：`docs/PLAN.md`、`docs/PROGRESS.md` 与 `pitfalls.md`。
- Backend/API/数据库 Schema/Evidence/Preflight/积分均不变；未打开或修改用户文件，未
  自动猜测、保存单位或创建任务；未触碰/暂存 `.playwright-cli/`、`design-system/`、
  旧 `docs/ui-mockups/` 或 ignored `output/`。

## Post-Alpha User App Shell 滚动根修复

### Runtime 根因

- 新建任务页实测内容高度 1627px、视口 1090px，理论可滚动 537px；
  `html/body/main` 的 overflow 均正常，也没有页面级 `wheel/touchmove/keydown`
  listener，但真实滚轮与 `PageDown` 后 root `scrollTop` 始终为 0。
- 同一 Chrome 的独立长页面可以滚动，排除鼠标、Chrome 和全局扩展故障。Office AI
  User Shell 仅用 `min-height: 100vh`，依赖浏览器隐式 root scrolling，导致手势没有
  进入 scroll tree；程序化 `scrollTo` 可用但不能代表真实交互。
- 运行时只为 `.user-shell` 建立 `height: 100dvh; min-height: 0; overflow-y: auto`
  后，滚轮立即令 shell `scrollTop` 从 0 变为 280，证明共享 App Shell 是根因。

### TDD、实现与验证

- RED：App Shell focused 为 `1 failed, 6 passed`，锁定缺少明确 user scroll root；
  GREEN 为 `7 passed`。
- 实现仅标记 User Shell scroll root 并增加三条滚动 CSS；没有修改单个业务页面、添加
  wheel listener、调用 `preventDefault` 或模拟滚动。
- Frontend full 为 23 files / `72 passed`；production build 为
  `104 modules transformed`；`npm audit --audit-level=high` 为 0 vulnerabilities。
- 只重建并强制替换 Frontend；Frontend/Backend/workflow worker/MySQL/Redis 均 healthy，
  Frontend Host 返回 200。
- 真实 Chrome Desktop 滚轮从 `0 -> 360 -> 537.6` 并显示底部主按钮；375x812 滚到
  `352.8/353`，横向 overflow 为 0。Console 无 warning/error；临时诊断样式已移除，
  浏览器恢复到用户原任务详情页。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-27-office-ai-user-shell-scroll-root.md`。
- Frontend：`components/layout/app-shell.vue` 与对应 component test。
- Records：`docs/PLAN.md`、`docs/PROGRESS.md` 与 `pitfalls.md`。
- Admin/Public Shell、业务页面、API、数据库 Schema、任务、用户文件和历史记录均不变；
  未触碰/暂存 `.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/` 或 ignored
  `output/`。

## Post-Alpha 文件生成 Worker Runtime 修复

### Runtime 根因与修复

- 用户 generation task `019fa43d-c6a8-7461-acea-9985dc8e6145` 在 MySQL 中保持
  `queued / 0%`，对应 `generation.queued` Outbox 已发布且 Redis generation queue
  存在消息；Compose 却没有 production generation consumer。仓库已有
  `GenerationQueueConsumer`、worker 状态机、Renderer 与 QA service，但没有 runner
  注入真实 step executor，形成只有 producer、没有 consumer 的运行时断链。
- 新增独立 `generation-worker`，消费既有 `office_ai:generation:queue`，将冻结的
  confirmed Structured Brief 确定性编译为 strict `PresentationPlan` /
  `WorkbookPlan`，复用现有 PPT/Excel Renderer、LibreOffice QA、output checkpoint
  与积分结算。worker 不调用 Provider、不读取源文件，也不猜测缺失数字或单位。
- 任务 claim 后持久化 `10%`；多输出任务每完成一个 step 按已完成比例推进，最终由既有
  settle 状态机写入 `100%`。进度来源仍是 MySQL durable state，不使用前端假动画。
- 合法但没有任何 facts/inferences/must-include 的 Brief 会在 renderer 前返回
  `generation_brief_content_required` 的 permanent failure；非法 Brief 返回
  `generation_brief_invalid`，避免无效重试和空白文件。

### TDD、Broad 与 Runtime

- RED 依次锁定缺少 runtime module、pipeline、Compose service、stage progress 和空
  Brief permanent failure；GREEN focused runtime 为 `6 passed`，generation/outbox/
  quality/workflow 相关回归为 `118 passed`。
- Backend full 为 `609 passed, 7 skipped`；7 个 skip 仍仅为默认关闭的 4 个 live
  failure drill 与 3 个 real Agnes case。Ruff `381 files` check/format 通过。
- Frontend full 为 23 files / `72 passed`；production build 为
  `104 modules transformed`。本任务没有修改前端代码。
- Compose config 通过；Backend image 重建后 `generation-worker`、Backend、MySQL、
  Redis、PPT Renderer 与 LibreOffice 均 healthy。worker 容器 focused 为 `6 passed`，
  `pip check` 无 broken requirements，generation queue 深度为 `0`，
  Host `/health/ready=ready`，Frontend 返回 `200`。
- 真实 Chrome 只读刷新旧任务后显示 `任务未完成 / 100% / task_timeout`、文件不可下载、
  已结算 `0`，用户积分从预留后的 `7,600` 恢复为 `10,000`，Console 无 warning/error。
  旧任务在 worker 启动前已超过 timeout，且其冻结 Brief 没有可生成 Evidence，因此没有
  手工改写状态、重放任务或自动创建会再次扣费的新任务。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-28-office-ai-generation-worker-runtime.md`。
- Backend：`services/generation_runtime.py`、generation worker runner/entrypoint、阶段进度
  持久化与对应 tests。
- Runtime/Records：`docker-compose.yml`、`docs/PLAN.md`、`docs/ENVIRONMENT.md`、
  `docs/SECURITY.md`、`docs/PROGRESS.md` 与 `pitfalls.md`。
- 不修改 HTTP API、数据库 Schema、Frontend、Provider Contract、用户文件或旧任务审计
  事实；未触碰/暂存 `.playwright-cli/`、`design-system/`、旧
  `docs/ui-mockups/` 或 ignored `output/`。

## Post-Alpha 生成 Plan 边界修复

### Runtime 根因与修复

- 新任务 `019fa767-93ea-7b56-a5cd-0a3f9a06bb8e` 已被 generation worker 消费，
  不再是 queue 卡死。其 Brief 有 10 个内容项、21 个唯一 Evidence，单条内容最多引用
  21 个 Evidence；PPTX 三次 `worker_execution_failed` 且没有 renderer checkpoint，
  XLSX 首次以 `workbook_evidence_reference_limit_exceeded` 永久失败。
- `PresentationGenerationPipeline` 原先把 typed `PresentationPlan` 直接传给只接受
  `dict` 的 `PresentationOutputService`，因此在 checkpoint 前触发 contract error，
  再被 worker 泛化为 retryable failure。现在仅 Presentation pipeline 在 output 边界
  输出确定性 JSON payload，typed Plan 仍传给 QA；Spreadsheet 保持原 typed contract。
- Workbook compiler 原先把同一内容的全部 Evidence ID 拼入单个 cell。现在按实际字符数
  在 500 字符 budget 内确定性分组，必要时重复内容行，完整保留 Evidence 顺序与引用；
  不截断、不抽样，也不提高 Workbook cell 上限。

### TDD、Broad 与 Runtime

- RED 为 `2 failed`：PPT output payload 不是 `dict`；21-Evidence workbook 在旧拼接检查
  处失败。GREEN focused 两项通过，runtime file 为 `7 passed`。
- Generation/Outbox/Presentation/Spreadsheet/QA/Workflow 相关回归为 `182 passed`。
  Backend full 为 `610 passed, 7 skipped`；7 个 skip 仍仅为默认关闭的 4 个 live
  failure drill 与 3 个 real Agnes case。Ruff `381 files` check/format 通过。
- Backend image 重建后 generation worker、Backend、PPT Renderer 与 LibreOffice 均
  healthy；worker 容器 focused `7 passed`，`pip check` 无 broken requirements，
  generation queue 深度为 `0`。
- 对失败任务的冻结 Brief 执行无数据库写入 probe：PPTX payload 通过 strict contract，
  共 5 页、21 Evidence；XLSX 为 1 Sheet、12 rows、21 Evidence，最长 Evidence cell
  为 468 字符，真实 Excel renderer 生成 8,092-byte 临时文件后立即清理。
- 旧失败任务、step 和积分流水保持审计事实，未自动重放或创建新收费任务。用户需手工
  再生成一次，才能完成真实 task checkpoint、LibreOffice QA 与下载验收。

### Changed files 与边界

- Plan：`.hermes/plans/2026-07-28-office-ai-generation-plan-boundaries.md`。
- Backend：`services/generation_runtime.py` 与 `tests/generation/test_runtime.py`。
- Records：`docs/PROGRESS.md`、`pitfalls.md`。
- 不修改 API、数据库 Schema、Frontend、Provider、Evidence/Preflight/Workbook
  contract、用户文件或旧任务事实；未触碰/暂存 `.playwright-cli/`、`design-system/`、
  旧 `docs/ui-mockups/` 或 ignored `output/`。
- 诊断中一次 `docker compose config` 过滤命令意外展开当前 Session Secret 到工具输出；
  未复制、记录、暂存或提交该值。为使该输出失效，仍需用户授权后轮换 Session Secret，
  该操作会终止现有登录，因此本任务未擅自执行。
