# Office AI 空项目首份材料上传修复

- 日期：`2026-07-27`
- 类型：Post-Alpha runtime bug fix
- 基线：`f754736281c7dd46453d5917c2e98c22c2e2bb4d`
- 范围：仅修复新账号或空库账号在“新建生成任务”页无法上传首份材料的问题。

## 根因

后端上传契约允许省略 `project_id`，并会为当前用户幂等创建唯一“默认项目”；前端却要求
`projectId` 非空才启用文件输入，同时总是向 multipart 写入 `project_id`。当
`GET /projects` 返回空数组时，项目选择与首份上传互相等待，形成不可恢复的首用死锁。

## 成功标准

1. 项目为空时，项目选择框显示“上传首份材料后自动创建默认项目”的明确占位信息。
2. 项目为空时，“上传一份材料”仍可打开文件选择器。
3. 首份上传不写入空 `project_id`；后端按既有契约创建默认项目。
4. 上传完成并重新加载后，默认项目出现在选择框中。
5. 已有项目时仍显式上传到当前项目，Brief 提交流程不变。

## RED / GREEN

1. 先在 `frontend/src/modules/workspace/api.test.ts` 固定无项目上传时不发送
   `project_id` 的 contract。
2. 先在 `frontend/src/views/user/workflow-new.test.ts` 固定空项目时文件输入可用、
   占位提示可见、上传调用使用未指定项目。
3. 运行 focused tests，确认新增断言因当前强制项目逻辑而失败。
4. 最小修改 `frontend/src/modules/workspace/api.ts` 和
   `frontend/src/views/user/workflow-new.vue`，再运行 focused、frontend broad 和 build。
5. 重建 Frontend，并在真实浏览器空项目状态验证项目占位、文件选择器和无 Console 错误。

## 边界

- 不修改后端上传、项目或数据库 contract。
- 不自动在页面加载时执行写操作。
- 不上传用户文件；浏览器验证只打开文件选择器。
- 不触碰 `.env`、`.playwright-cli/`、`design-system/`、旧 `docs/ui-mockups/` 或
  ignored `output/`。
