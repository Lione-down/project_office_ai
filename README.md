# Project Office AI

面向销售及通用办公场景的 AI Office 文件生成项目。首个内部 Alpha 目标是在本地完成真实材料到 PPTX 与 XLSX 的双输出闭环。

## 当前状态

项目处于规划完成、尚未开始编码的阶段。批准后的实施计划位于：

`.hermes/plans/2026-07-22_000414-office-ai-alpha.md`

## 核心技术方向

- Vue 3 + TypeScript
- FastAPI + MySQL 8.0 + Redis
- Agnes Provider Adapter
- PptxGenJS
- XlsxWriter + openpyxl
- LibreOffice Headless
- ClamAV + PaddleOCR
- Docker Compose

## 敏感信息规则

- 不提交 `.env`、`.env.*`、API Key、Token、密码、证书或私钥。
- 不提交 `backend/files/` 中的用户文件、OCR 结果、预览和生成文件。
- 不提交数据库数据目录、日志、缓存或临时文件。
- 真实配置只通过本地环境变量或未来的 Secret 管理服务提供。
- 提交模板和黄金测试文件前，必须确认版权许可并完成数据脱敏。

## Git 提交前检查

```powershell
git check-ignore -v .env
git status --short
git diff --cached --name-only
```

只有确认暂存区不包含敏感信息后才能推送到 GitHub。
