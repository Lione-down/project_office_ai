# P5-005 模板目录、缩略图与版本快照

- 状态：`DONE`
- Depends on：`P5-004`
- 来源：PRD FR-301～FR-305、模板/Skill 分离原则
- 建议 commit：`feat(template): add certified deck catalog`

## 目标

把现有文字模板页升级为原创、授权明确、可预览且与 Skill 兼容的系统模板目录，并在
Deck Draft/Generation 中冻结 template code/version/checksum。

## 交付范围

- 合同规定数量/分类的首批原创系统模板及 version/checksum/source metadata。
- 封面缩略图、代表页拼图、详情、配色、字体、布局清单、适用场景和兼容 Skill。
- Template list/detail API 或现有 API additive projection，owner/public published 边界。
- Deck Draft 选择/切换/静态预览和 generation snapshot。
- Renderer template registry/layout mapping 与 Golden fixtures。

## RED 与实施顺序

1. Template metadata/checksum/Skill compatibility/migration or seed contract 先 RED。
2. API list/detail/filter/version tests 与 frontend catalog/detail/select tests 先 RED。
3. Renderer 逐模板 strict plan/preview/Golden tests 先 RED。
4. GREEN 后运行全 Renderer、Frontend、Backend template/preflight/generation suites。

## 验收标准

- 目录展示真实缩略图/代表页，不使用第三方截图或品牌资产。
- 详情与 runtime registry 的 code/version/checksum/布局/Skill 一致，漂移 fail closed。
- 切换模板只创建新 Draft revision；已确认/生成任务的 snapshot 不漂移。
- 每个认证模板的代表性 Plan 通过 Renderer、质量检查和视觉抽查。
- 旧三套系统 PPT 模板及历史任务仍可按冻结版本重放。

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/templates tests/preflight tests/generation -q
cd ..
cd frontend
npm run test -- template
npm run test
npm run build
cd ..
cd ppt-renderer
npm test
npm run build
cd ..
git diff --check
```

## 证据边界

- Focused：metadata/version/checksum/compatibility/API/UI/Renderer layout。
- Broad：Backend relevant/full、Frontend full/build、Renderer full/build/Golden。
- Security：素材版权/来源字段、无外链、无 private path/metadata、owner/发布状态。
- Provider：本任务不需 Agnes Provider 调用。
- Office/WPS：LibreOffice/PDF/PNG/OOXML 是机器证据；认证模板的最终 PowerPoint/WPS
  全量兼容在 P5-008 关闭，本任务不得提前宣称。

## 非目标与回滚

- 不支持用户私人模板上传、任意 PPTX 母版导入或第三方模板复刻。
- 不生成图片/视频。
- 回滚停用新增模板版本，不覆盖历史模板或已生成任务 snapshot。

## 完成记录（2026-07-29）

- Additive migration `20260729_0018` 为既有 `templates` 增加 checksum，并发布三套
  `system_original` PPTX catalog row；DB row、Python catalog、Deck/generation snapshot
  与 Node Renderer registry 以 code/version/checksum/layout 严格对齐，漂移返回稳定错误。
- 新增 authenticated、`private, no-store` 的 template list/detail API；前端目录和
  Deck Studio 只使用本地 SVG 封面/代表页，展示来源、license、配色、字体、布局、
  use case 与 compatible Skill，外链、Data URI 和 private path 均 fail closed。
- 模板切换要求当前 Draft revision，且只追加新 revision；confirm/generation 冻结
  template snapshot。历史 generation snapshot 缺 checksum 时仍按已冻结 code/version
  重放，新 Renderer sidecar 缺 checksum 时安全重渲染。
- RED 覆盖 catalog/migration/API/UI/Deck/generation/Renderer checksum；最终 focused
  Backend `171 passed`，Backend full `668 passed, 11 skipped`，Frontend full
  `97 passed` + build，Renderer `23 passed` + build，Ruff/依赖审计/Compose config 通过。
- 真实 MySQL 已升级至 `20260729_0018 (head)`；backend、frontend、generation-worker、
  ppt-renderer 均 healthy。三套代表 Plan 均通过 live Renderer 和 LibreOffice
  25.2.3.2 PDF/逐页 PNG，Chrome 登录态目录/详情无 console warning/error。
- 本任务未调用 Agnes Provider；LibreOffice/PNG/OOXML 和浏览器属于机器证据，未提前
  宣称 Microsoft PowerPoint/WPS 或 Human acceptance，最终兼容性仍由 P5-008 关闭。
