# P5-005 模板目录、缩略图与版本快照

- 状态：`BLOCKED`
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
