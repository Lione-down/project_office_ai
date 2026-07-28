# P5-006 Agnes 图片资产与 PPT 视觉集成

- 状态：`BLOCKED`
- Depends on：`P5-005`
- 来源：PRD FR-401～FR-406、Image 2.1 模型策略
- 建议 commit：`feat(media): add agnes image assets to decks`

## 目标

让 Visual Director 为逐页生成结构化视觉建议，并由用户显式按页创建 Agnes 图片任务；
通过安全检查的不可变图片资产可由 PPT Renderer 使用。

## 交付范围

- `ppt.visual-director.v1` 输出 `none/diagram/chart/illustration/photo` 与 bounded Prompt。
- 按页 generate/skip/replace/regenerate；每次收费外部调用均显式确认和幂等。
- Image job 状态、Provider ID、model/capability/pricing snapshot、Prompt hash、真实尺寸、
  asset version 和关联关系。
- 文生图与合同允许的 Data URI 图生图；不使用公共 tunnel/未批准 public URL。
- 格式、容量、完整解码、尺寸、hash、内容策略和 owner storage gate。
- PresentationPlan image ref、裁切/版面/alt text 和图片参与 PPTX Golden。

## RED 与实施顺序

1. Image provider request/response、capability、job state/idempotency/uncertain tests 先 RED。
2. Asset validation/storage/owner/Prompt redaction tests 先 RED。
3. Visual Director/Deck UI/explicit confirmation tests 先 RED。
4. Renderer image reference/crop/overflow/Golden tests 先 RED。
5. Mock GREEN 后执行显式 opt-in 真实 Agnes Image Contract 和 PPTX runtime。

## 验收标准

- 仅用户选择页面创建任务；retry/regenerate 产生新 job/asset，不覆盖历史。
- Provider 返回尺寸为权威；建议 2K/16:9 不伪造结果尺寸。
- `provider_uncertain` 不自动重复提交或扣费；非法/不可达结果不创建 ready asset。
- Prompt 正文不进入日志/provider_calls；只保存必要产品内容位置和 hash/metadata。
- Renderer 只接受 owner-scoped ready image version，裁切/尺寸/容量/缺失均 fail closed。
- 图片 Golden PPTX 通过质量报告与不可变 artifact integrity。

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests/media/images tests/providers tests/generation tests/quality -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\ruff.exe check app tests alembic
.venv\Scripts\ruff.exe format --check app tests alembic
cd ..
cd frontend
npm run test -- image
npm run test
npm run build
cd ..
cd ppt-renderer
npm test
npm run build
cd ..
docker compose config --quiet
git diff --check
```

## 证据边界

- Focused：provider contract/job/asset/idempotency/owner/renderer refs。
- Broad：Backend/Frontend/Renderer full、Golden、Compose。
- Security：Data URI limits、full decode、MIME magic、public URL disabled、Prompt/log redaction、
  cross-owner asset ref、重复计费。
- Provider：Mock 不证明 Agnes Image；显式 opt-in 真实 Contract 只用合成 Prompt/asset，
  记录脱敏 metadata 和实际尺寸。
- Office/WPS：图片 PPTX 的 LibreOffice/OOXML/截图是机器证据；PowerPoint/WPS 实际打开
  和视觉结果必须记录，最终全量结论仍由 P5-008 汇总。

## 非目标与回滚

- 不默认给所有页面生成图片，不启用任意公网 tunnel。
- 不实现视频或承诺版权/商业适用性。
- 回滚停用 image feature/capability；保留不可变历史 job/asset/ledger。
