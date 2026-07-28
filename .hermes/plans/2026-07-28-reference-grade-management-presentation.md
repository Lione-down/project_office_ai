# 参考级经营管理汇报 PPT 修复计划

## 状态

- 状态：`DONE`
- 日期：2026-07-28
- 范围：Post-Alpha PPT 生成质量修复
- 验收样本：
  - 输入：管理员已上传的 `第一季度数据.xlsx`
  - 私有只读视觉参考：`golden-data/private/广州B区2026年上半年总结与下一步措施.pptx`

## 问题与根因

当前生产链路只把 `StructuredBrief` 的少量事实、推断和必含项编译成固定文本框，
没有加载已冻结资产对应的 Evidence Manifest，也没有生成 table/chart data source。
PPT renderer 又把完整 Evidence ID 拼接到可见正文中，而现有质量门禁只检查对象边界、
空白页和标题长度，没有阻断正文过密、溢出或重叠风险。

这会稳定地产生以下失败结果：

- 输出只有约 4 页，缺少经营汇报所需的目录、专题分析和行动计划结构；
- 工作表中的业务明细没有转化为表格或图表；
- 完整 Evidence ID 暴露在页面正文，挤占可读空间；
- 文本框几何边界合法，但正文实际溢出并互相覆盖，质量检查仍可能通过。

## 目标

在不复制私有品牌、Logo、图片或母版素材的前提下，使系统生成的 PPT 达到参考稿的
经营管理汇报结构和可读性：

1. 使用明确的封面、目录、经营摘要、专题分析、问题与措施、结束页结构；
2. 从冻结资产的 Evidence Manifest 恢复 Excel 工作表的行列关系，将适合的内容编译为
   table，必要时辅以简洁图表，不再把全部内容堆成正文；
3. 页面只展示面向读者的业务内容和简短来源说明，完整 Evidence ID 仅保留在 speaker
   notes 或内部追踪数据中；
4. 对正文密度、文本框容量和可见 Evidence 泄漏增加自动质量门禁；
5. 使用同一份 `第一季度数据.xlsx` 重新走完整流程，并通过 Microsoft PowerPoint
   原生打开与逐页导出检查。

## 非目标

- 不复制或提交私有参考 PPT 的内容、品牌、Logo、图片、母版或嵌入对象；
- 不承诺对任意企业私有模板做像素级复刻；
- 本任务不改造 XLSX 输出；经营看板 XLSX 质量作为后续独立任务；
- 不从缺少 Evidence 的内容猜测数值、单位、口径或因果关系；
- 不修改已确认 Brief、不可变 Evidence 或历史生成文件。

## 可验证成功标准

### 结构与内容

- 生产计划不再固定为纯文本：至少包含目录、摘要、数据表格、问题/措施和结束页；
- 对具有 Excel 单元格定位的 Evidence，计划生成至少一个 table data source；
- 每页只承载一个清晰主题，标题与正文使用稳定层级；
- 无业务内容的占位页不得进入最终文件。

### Evidence 与安全

- PPT 可见 slide text 中不得出现 `e-` 加 64 位十六进制的完整 Evidence ID；
- 计划顶层和元素仍保留完整 Evidence 关联；
- renderer 将完整 Evidence 追踪写入 speaker notes，不写入可见正文；
- 私有参考文件和输入材料不进入 Git、测试 fixture、日志或文档正文。

### 布局质量

- renderer 对正文启用确定性的 shrink/fit 行为；
- 质量门禁阻断可见 Evidence ID；
- 质量门禁阻断超过文本框安全容量的正文；
- 当前 4 页文字重叠成品作为失败回归样本，不得再被判为可下载。

### Runtime 验收

- 使用管理员已上传的 `第一季度数据.xlsx` 创建新生成任务；
- Brief 如要求确认单位，按用户指示统一选择“数量”；
- PPT 任务完成且允许下载；
- Microsoft PowerPoint 原生打开成功；
- 原生导出的逐页 PNG 中没有文字重叠、截断或完整 Evidence ID；
- 输出结构与 28 页参考稿同类：具备管理汇报叙事和表格化表达，但不复制私有视觉资产。

## TDD 实施顺序

1. RED：compiler 测试证明纯 Brief 文本计划缺少管理汇报结构和 table data source；
2. RED：renderer 测试证明完整 Evidence ID 当前出现在可见 slide XML；
3. RED：presentation QA 测试证明正文过密和可见 Evidence ID 必须被阻断；
4. GREEN：为 PPT pipeline 注入只读 Evidence Manifest loader，并校验冻结资产版本；
5. GREEN：新增确定性的经营汇报 plan composer，生成目录、摘要、表格专题和措施页；
6. GREEN：将完整 Evidence ID 写入 speaker notes，并为正文启用 shrink/fit；
7. GREEN：补齐正文密度与 Evidence 泄漏质量规则；
8. focused tests 通过后，重建相关服务并执行真实生成；
9. 使用 PowerPoint 原生导出做视觉检查，再执行 backend、renderer、security 和 Git
   broad checks；
10. 更新 `docs/PROGRESS.md`，精确暂存、单一 commit 并推送。

## 回滚与边界

- 新 composer 或质量门禁失败时，任务必须 fail closed，不回退到可下载的文字堆叠稿；
- 历史输出保持不可变，新结果使用新的 generation task 和 asset；
- 任何无法从 Evidence Manifest 确认的数据都保持缺失或明确标记，不做补写；
- 自动化截图仅作为机器视觉证据，最终 Human 风格接受仍由用户确认。
