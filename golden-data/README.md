# Golden regression corpus

`sales-pilot-v1` 是用户于 2026-07-26 授权的单组本地 pilot。它由一份 XLSX
来源和一份 PPTX 私有参考组成；原件保留在 ignored `golden-data/private/`，不进入 Git，
也不会被修改。

仓库只跟踪重新生成的脱敏材料：

- `inputs/`：30-Sheet 脱敏输入，移除人员、客户、终端、电话、地址、private metadata、
  空白 worksheet、drawing 与旧 package payload，修复两个已知坏公式，并把一张 merged
  汇总表规范化为可机器复算的脱敏指标表。
- `expected/`：项目 renderer 生成的 4 页 PPTX 与 2-Sheet XLSX 基线。
- `manifests/`：授权范围、`1/10 pilot` 覆盖边界、指标口径、允许偏差、evidence IDs、
  版本与 SHA-256。

20 次 PPT 与 20 次 Excel 重复验证证明本 case 的确定性和结构合同，不证明 10 组数据覆盖，
也不升级为 Microsoft Office、WPS、LibreOffice 或真实 Agnes runtime 通过。
