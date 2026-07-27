# Post-Alpha Preflight 单位操作闭环与滚动修复

## 背景与根因

- 单位下拉框只更新确认页的临时 state，不会自动写入 Brief Revision。
- 唯一保存入口位于左侧 Brief 编辑卡片，单位选择位于右侧长阻断列表；两者在长页面中无法
  同时看见，用户完成全部选择后仍会看到 disabled 的生成按钮。
- 右侧单位列表没有受限高度或独立滚动区域，9 个以上表单项会把确认动作推到视口之外。
- disabled 主按钮没有解释还需要“保存单位并重新校验”，造成“全部选好仍无法生成”的
  错误反馈。

## 目标

1. 单位列表提供清晰、可键盘、滚轮和触控滚动的受限区域。
2. 单位选择旁显示完成计数，并提供同一上下文内的保存与重新校验动作。
3. 全部单位选择保存为新 Revision 后自动刷新 Preflight；无 blocker 时生成按钮解锁。
4. 未满足门禁时，主按钮文案准确说明当前缺少的步骤。

## 实施范围

### Frontend

- 为单位列表增加稳定的滚动容器、可见滚动条和移动端高度上限。
- 在单位 blocker 区加入 `已选 x/y`、保存按钮和 Revision/重新校验说明。
- 保存按钮只在目标、受众和全部单位已填写时启用，复用既有 immutable Revision PATCH。
- 根据缺失单位、待保存单位、其他 blocker 和 clean Preflight 显示对应主按钮文案。

## 不在范围

- 不自动猜测单位，不自动替用户保存或确认生成。
- 不修改 Backend API、数据库 Schema、Evidence Manifest、Preflight 判定或积分门禁。
- 不读取、修改、上传或删除用户文件，不改写历史 Revision 或任务。
- 不重构无关页面、路由或全局设计系统。

## RED / GREEN 验收

1. 有多个单位 blocker 时，页面显示 `0/n`，单位保存按钮 disabled。
2. 单位列表具有可识别的独立滚动区域。
3. 全部选择后显示 `n/n`，右侧保存按钮 enabled，主按钮提示先保存并重新校验。
4. 点击右侧保存调用既有 Revision PATCH；刷新到 clean Preflight 后生成按钮 enabled。
5. 无单位 blocker 时，目标编辑和正常生成流程保持现有行为。

## 验证命令

```powershell
docker compose run --rm frontend npm run test -- --run src/views/brief/confirm.test.ts
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run build
docker compose run --rm frontend npm audit --audit-level=high
```

## Runtime 与交付

- 仅重建并强制替换 Frontend，保持 Backend、workflow worker、MySQL、Redis 与用户数据不变。
- 真实 Browser 验证 desktop 与 375px：单位列表可滚动、保存动作可达、门禁文案准确、
  Console 无 warning/error；不替用户保存 Revision 或确认生成。
- 更新 `docs/PLAN.md`、`docs/PROGRESS.md` 与 `pitfalls.md`，精确暂存，一个
  `fix(preflight): ...` commit 并 push。
