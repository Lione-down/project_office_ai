# Office AI Post-Alpha 黄金 XLSX Evidence 限制校准

## 背景

- 用户明确授权只读使用 `golden-data/private/` 中唯一 XLSX 作为当前最高输入规模标准。
- 不提交、不复制、不输出 private workbook 的正文、文件名、路径、hash、作者或其他
  metadata；Git 继续忽略整个 private 目录。
- 只记录限制决策所需的结构计数。Artifact Tool 与生产 parser/Evidence builder 的只读
  测量结果为：31 Sheet、10,465 个非空单元格、11,563 个过滤前 source item、
  10,465 个最终 Evidence item、Manifest 约 7.48 MB。现有拒绝来自 10,000 source
  expansion 上限，而非 Sheet、单元格、Manifest byte、file byte、Archive 或 parser
  structural budget。

## 目标与成功标准

1. 将默认 `OFFICE_AI_MAX_EVIDENCE_ITEMS` 精确调整为 11,563，允许该黄金 XLSX 的过滤前
   source expansion 数量。
2. 第 11,564 个 source item 继续以 `evidence_item_limit_exceeded` fail closed。
3. 同步 Settings、Evidence builder default、Compose worker、测试和现行专题文档。
4. 不调整 10 MB Manifest byte、100 Sheet、300,000 非空单元格、Archive、parser
   structural、timeout、memory、ClamAV、owner scope 或 immutable Evidence 规则。
5. 不自动重试、删除或改写现有 rejected asset；用户可在新 worker 生效后删除旧记录并
   重新上传。

## RED contract

- Settings 默认必须为 11,563。
- Compose worker 必须使用
  `${OFFICE_AI_MAX_EVIDENCE_ITEMS:-11563}`。
- 默认 Evidence builder 必须接受 11,563 个来源，并在第 11,564 个来源到达、且构建
  Pydantic Evidence object 前稳定拒绝。
- Workflow 对 `evidence_item_limit_exceeded` 显示“超过 11,563 项”的可操作提示，不暴露
  private workbook 信息。

## 验证顺序

1. RED：focused Settings/Compose、Evidence builder 与 Workflow tests。
2. GREEN：Backend focused、Frontend focused。
3. Broad：Backend full、Frontend full/build、Ruff。
4. Security：dependency audit、Git ignore/secret/staged-path checks。
5. Runtime：重建并只重启 worker/frontend，确认 worker 实际变量为 10,465；不重建
   MySQL/Redis，不读取或改变用户资产。
6. 真实 Chrome：确认当前拒绝提示与删除操作可见；不点击删除，不自动重新处理用户文件。

## 交付边界

- 本任务只校准 Evidence item 数量阈值和对应用户提示。
- private XLSX 只作本地只读测量，不进入测试 fixture、文档正文、Git、日志或输出目录。
- 黄金样本仍只有 `1/10 pilot`，本次不能扩张为多样本覆盖或新的兼容性证明。
