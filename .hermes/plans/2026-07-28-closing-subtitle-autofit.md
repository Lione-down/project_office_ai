# Post-Alpha 结束页长目标文本质量阻断修复

- 状态：`DONE`
- 日期：`2026-07-28`
- 关联任务：`019fa920-a43f-71f5-8617-1d1bc3d90cb5`
- 范围：仅修复 PPT 结束页长 subtitle 因未启用 autofit 而触发
  `presentation_quality_blocked` 的回归。

## 根因

管理汇报 composer 将完整 `brief.goal` 写入结束页 subtitle；renderer 使用固定
`10.73 x 0.65` 英寸、18pt 文本框，却没有启用 shrink/autofit。质量检查按实际 OOXML
几何计算安全容量：本次文本长度为 69，容量为 67，因此第 27 页 shape 3 被
`presentation-body-fit.v1` 阻断。重试保持同一输入和布局，所以产生新的 blocked 资产，
不会自行恢复。

## 实现与验收

1. RED：新增 renderer 回归测试，生成带长结束页 subtitle 的真实 PPTX，并断言该
   subtitle 所在 shape 包含 OOXML `a:normAutofit`。
2. GREEN：为 slide subtitle 启用 PptxGenJS `fit: "shrink"`，保留完整用户目标，不做
   字符截断。
3. Focused：运行 PPT renderer 测试与 build；运行 presentation quality focused tests。
4. Broad：运行 Backend、Frontend、Renderer 全量测试/构建及 Ruff、安全检查。
5. Runtime：重建 renderer/generation worker，重试真实任务，要求 PPTX quality 为
   `passed` 或 `passed_with_warnings`、`download_allowed=true`、LibreOffice 页数完整。
6. 记录：更新 `docs/PROGRESS.md` 与 `pitfalls.md`，精确暂存、单 commit、push。

## 完成证据

- RED：长结束页 subtitle 的真实 PPTX OOXML 不含 `a:normAutofit`，focused test 按预期
  失败。
- GREEN：subtitle 使用 `fit: "shrink"`；Renderer `23 passed`、Backend presentation
  focused `84 passed`。
- 真实任务 `019fa920-a43f-71f5-8617-1d1bc3d90cb5` 第二次 retry 后为
  `succeeded/100%`，新资产 `019fa929-c646-75d2-8132-4175625ecef9` 的 quality
  `passed`、`findings=0`、LibreOffice `27/27`、结算 800。
- 第 27 页 PNG 实际检查：完整目标换行为两行，无截断、重叠或越界。
- Broad：Backend `626 passed, 7 skipped`；Frontend `73 passed` 与 build；Ruff
  `383 files`；Renderer `23 passed` 与 build；Compose 服务健康。

## 不变边界

- 不修改 Brief、Evidence Manifest、用户文件、单位确认、积分和数据库 Schema。
- 不降低正文密度质量规则，不把 overflow blocker 改成 warning。
- blocked 历史资产保持不可变；重试创建新资产。
