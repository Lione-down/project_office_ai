import type { AdminSection } from "./types";

export interface AdminDisplayRow {
  id: string;
  values: Array<string | number>;
}

export const adminConfigurations = {
  users: {
    title: "用户管理",
    description: "查询用户、状态与强制改密标记",
    group: "用户与邀请码",
    columns: ["用户", "角色", "状态", "积分余额", "强制改密", "操作"],
    reserved: false,
  },
  invites: {
    title: "邀请码管理",
    description: "查看创建范围、使用情况和注册赠送积分",
    group: "用户与邀请码",
    columns: ["邀请码前缀", "状态", "已用/上限", "注册赠送积分", "有效期"],
    reserved: false,
  },
  providers: {
    title: "Provider 管理",
    description: "配置模型服务边界与连接状态",
    group: "服务配置",
    columns: ["Provider", "Adapter", "Base URL", "状态", "默认超时"],
    reserved: false,
  },
  credentials: {
    title: "Credential 管理",
    description: "每条记录只保存一个加密 API Key",
    group: "服务配置",
    columns: ["名称", "API Key", "状态", "RPM/TPM", "最大并发", "最近测试", "操作"],
    reserved: false,
  },
  models: {
    title: "Model 管理",
    description: "发布用户可选模型并绑定能力与积分倍率",
    group: "服务配置",
    columns: ["显示名称", "模型代码", "Context", "用户可见", "积分倍率", "状态"],
    reserved: false,
  },
  tasks: {
    title: "任务管理",
    description: "查看持久任务、子输出与异常状态",
    group: "任务与资产",
    columns: ["任务", "用户", "输出", "状态", "当前阶段", "积分"],
    reserved: true,
  },
  assets: {
    title: "资产管理",
    description: "查看全部用户资产并执行受审计操作",
    group: "任务与资产",
    columns: ["文件", "用户", "项目", "类型/大小", "处理状态", "SHA-256", "操作"],
    reserved: false,
  },
  credits: {
    title: "积分管理",
    description: "查询余额并执行只追加人工调整",
    group: "积分",
    columns: ["用户", "状态", "当前余额", "操作"],
    reserved: false,
  },
  "audit-logs": {
    title: "审计日志",
    description: "查询敏感操作、结果与脱敏上下文",
    group: "审计日志",
    columns: ["时间", "操作者", "动作", "目标", "网络摘要", "原因", "结果", "Trace ID"],
    reserved: false,
  },
} satisfies Record<
  AdminSection,
  {
    title: string;
    description: string;
    group: string;
    columns: string[];
    reserved: boolean;
  }
>;

function formatDate(value: unknown) {
  if (typeof value !== "string") return "—";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(
    new Date(value),
  );
}

export function mapAdminRows(
  section: AdminSection,
  items: Array<Record<string, unknown>>,
): AdminDisplayRow[] {
  if (section === "invites") {
    return items.map((item) => ({
      id: String(item.invite_id),
      values: [
        `${item.code_prefix}••••`,
        String(item.status),
        `${item.used_count}/${item.max_uses}`,
        Number(item.registration_credit).toLocaleString("zh-CN"),
        formatDate(item.expires_at),
      ],
    }));
  }
  if (section === "providers") {
    return items.map((item) => ({
      id: String(item.provider_id),
      values: [
        String(item.display_name),
        String(item.protocol),
        String(item.base_url),
        String(item.status),
        `${item.default_timeout_seconds} 秒`,
      ],
    }));
  }
  if (section === "credentials") {
    return items.map((item) => ({
      id: String(item.credential_id),
      values: [
        String(item.name),
        String(item.masked_key),
        String(item.status),
        `${item.rpm_limit}/${item.tpm_limit}`,
        Number(item.max_concurrency),
        String(item.last_test_status ?? "未测试"),
      ],
    }));
  }
  if (section === "models") {
    return items.map((item) => ({
      id: String(item.model_id),
      values: [
        String(item.display_name),
        String(item.model_code),
        Number(item.context_window).toLocaleString("zh-CN"),
        item.user_visible ? "是" : "否",
        `${item.credit_multiplier}×`,
        String(item.status),
      ],
    }));
  }
  if (section === "users" || section === "credits") {
    return items.map((item) => ({
      id: String(item.user_id),
      values:
        section === "users"
          ? [
              String(item.masked_phone),
              String(item.role),
              String(item.status),
              Number(item.credit_balance).toLocaleString("zh-CN"),
              item.must_change_password ? "是" : "否",
            ]
          : [
              String(item.masked_phone),
              String(item.status),
              Number(item.credit_balance).toLocaleString("zh-CN"),
            ],
    }));
  }
  if (section === "assets") {
    return items.map((item) => ({
      id: String(item.asset_id),
      values: [
        String(item.original_filename),
        String(item.owner_user_id),
        String(item.project_id),
        `${item.file_category} / ${Number(item.byte_size).toLocaleString("zh-CN")} B`,
        String(item.processing_status),
        String(item.sha256).slice(0, 12),
      ],
    }));
  }
  if (section === "audit-logs") {
    return items.map((item) => ({
      id: String(item.audit_id),
      values: [
        formatDate(item.created_at),
        String(item.actor_user_id ?? "系统"),
        String(item.action),
        `${item.target_type}:${item.target_id ?? "—"}`,
        `${item.ip_address ?? "—"} / ${item.user_agent ?? "—"}`,
        String(item.reason),
        String(item.result),
        String(item.trace_id),
      ],
    }));
  }
  return [];
}
