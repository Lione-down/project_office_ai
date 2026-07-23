<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { ApiError } from "@/api/request";
import { adminApi } from "@/modules/admin/api";
import type { AdminSection } from "@/modules/admin/types";
import { useSessionStore } from "@/store/session";

const props = defineProps<{ section: AdminSection }>();
const session = useSessionStore();
const rows = ref<Array<Record<string, unknown>>>([]);
const isLoading = ref(false);
const errorMessage = ref("");

const configurations = {
  users: {
    title: "用户管理",
    description: "查询用户、状态与强制改密标记",
    group: "用户与邀请码",
    columns: ["用户", "状态", "积分余额", "项目/资产", "最近登录"],
    reserved: true,
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
    columns: ["名称", "API Key", "状态", "RPM/TPM", "最大并发", "最近测试"],
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
    columns: ["文件", "用户", "项目", "类型/大小", "处理状态", "SHA-256"],
    reserved: true,
  },
  credits: {
    title: "积分管理",
    description: "查询余额、预留、结算、释放和赠送流水",
    group: "积分",
    columns: ["时间", "用户", "类型", "关联对象", "变动", "变动后"],
    reserved: true,
  },
  "audit-logs": {
    title: "审计日志",
    description: "查询敏感操作、结果与脱敏上下文",
    group: "审计日志",
    columns: ["时间", "操作者", "动作", "目标", "原因", "结果", "Trace ID"],
    reserved: true,
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

const config = computed(() => configurations[props.section]);
const tabs = computed(() => {
  if (config.value.group === "用户与邀请码") {
    return [
      { label: "用户", href: "/admin/users", section: "users" },
      { label: "邀请码", href: "/admin/invites", section: "invites" },
    ];
  }
  if (config.value.group === "服务配置") {
    return [
      { label: "Provider", href: "/admin/providers", section: "providers" },
      { label: "Credential", href: "/admin/credentials", section: "credentials" },
      { label: "Model", href: "/admin/models", section: "models" },
    ];
  }
  if (config.value.group === "任务与资产") {
    return [
      { label: "任务", href: "/admin/tasks", section: "tasks" },
      { label: "资产", href: "/admin/assets", section: "assets" },
    ];
  }
  return [];
});

function requireToken() {
  if (!session.accessToken) throw new Error("管理员 Session 已失效");
  return session.accessToken;
}

function formatDate(value: unknown) {
  if (typeof value !== "string") return "—";
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(
    new Date(value),
  );
}

function mapRows(section: AdminSection, items: Array<Record<string, unknown>>) {
  if (section === "invites") {
    return items.map((item) => ({
      code: `${item.code_prefix}••••`,
      status: item.status,
      usage: `${item.used_count}/${item.max_uses}`,
      credit: Number(item.registration_credit).toLocaleString("zh-CN"),
      expires: formatDate(item.expires_at),
    }));
  }
  if (section === "providers") {
    return items.map((item) => ({
      name: item.display_name,
      adapter: item.protocol,
      url: item.base_url,
      status: item.status,
      timeout: `${item.default_timeout_seconds} 秒`,
    }));
  }
  if (section === "credentials") {
    return items.map((item) => ({
      name: item.name,
      key: item.masked_key,
      status: item.status,
      limits: `${item.rpm_limit}/${item.tpm_limit}`,
      concurrency: item.max_concurrency,
      test: item.last_test_status ?? "未测试",
    }));
  }
  if (section === "models") {
    return items.map((item) => ({
      name: item.display_name,
      code: item.model_code,
      context: Number(item.context_window).toLocaleString("zh-CN"),
      visible: item.user_visible ? "是" : "否",
      multiplier: `${item.credit_multiplier}×`,
      status: item.status,
    }));
  }
  return [];
}

async function load() {
  rows.value = [];
  errorMessage.value = "";
  if (config.value.reserved) return;
  isLoading.value = true;
  try {
    const token = requireToken();
    let items: unknown[] = [];
    if (props.section === "invites") items = await adminApi.listInvites(token);
    if (props.section === "providers") items = await adminApi.listProviders(token);
    if (props.section === "credentials") items = await adminApi.listCredentials(token);
    if (props.section === "models") items = await adminApi.listModels(token);
    rows.value = mapRows(props.section, items as Array<Record<string, unknown>>);
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError || error instanceof Error
        ? error.message
        : "无法加载管理数据";
  } finally {
    isLoading.value = false;
  }
}

watch(() => props.section, load);
onMounted(load);
</script>

<template>
  <section class="admin-resource" lang="zh-CN">
    <header>
      <div>
        <p>{{ config.group }}</p>
        <h1>{{ config.title }}</h1>
        <span>{{ config.description }}</span>
      </div>
      <button
        v-if="!config.reserved"
        class="oa-button oa-button--primary"
        type="button"
        disabled
        title="T4-001 先交付稳定读取与状态壳"
      >
        新增记录
      </button>
    </header>

    <nav v-if="tabs.length" class="resource-tabs" :aria-label="`${config.group}二级导航`">
      <a
        v-for="tab in tabs"
        :key="tab.section"
        :href="tab.href"
        :aria-current="tab.section === section ? 'page' : undefined"
      >
        {{ tab.label }}
      </a>
    </nav>

    <aside v-if="section === 'credentials'" class="boundary-note">
      Credential 默认掩码。Reveal 与重新认证闭环将在 T4-002 接入。
    </aside>
    <aside v-if="config.reserved" class="boundary-note boundary-note--reserved">
      <strong>当前页面仅提供功能壳</strong>
      <span>
        对应管理员 HTTP API、重新认证、操作原因和审计闭环由 T4-002 交付；
        当前不显示 mock 数据，也不开放敏感操作。
      </span>
    </aside>

    <div class="toolbar">
      <label>
        <span class="visually-hidden">搜索</span>
        <input class="oa-input" type="search" placeholder="搜索当前列表" disabled />
      </label>
      <button class="oa-button oa-button--secondary" type="button" disabled>筛选</button>
    </div>

    <div class="table-panel">
      <div v-if="isLoading" class="state-copy" aria-live="polite">正在加载{{ config.title }}…</div>
      <div v-else-if="errorMessage" class="state-copy state-copy--error">
        <p>{{ errorMessage }}</p>
        <button class="oa-button oa-button--secondary" type="button" @click="load">重新加载</button>
      </div>
      <div v-else class="table-scroll">
        <table>
          <thead>
            <tr>
              <th v-for="column in config.columns" :key="column" scope="col">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rows" :key="index">
              <td v-for="value in Object.values(row)" :key="String(value)">
                {{ value }}
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!rows.length" class="empty-copy">
          {{ config.reserved ? "等待 T4-002 接入真实管理数据。" : "当前没有记录。" }}
        </p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.admin-resource {
  display: grid;
  gap: 18px;
}

header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

header p {
  margin: 0 0 6px;
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}

h1 {
  margin: 0;
  font-size: 30px;
}

header span {
  display: block;
  margin-top: 8px;
  color: var(--oa-muted);
}

.resource-tabs {
  display: flex;
  min-height: 48px;
  align-items: stretch;
  gap: 30px;
  border-bottom: 1px solid var(--oa-line);
}

.resource-tabs a {
  position: relative;
  display: grid;
  place-items: center;
  color: #475569;
  font-weight: 650;
  text-decoration: none;
}

.resource-tabs a[aria-current="page"] {
  color: #0759bd;
}

.resource-tabs a[aria-current="page"]::after {
  position: absolute;
  right: 0;
  bottom: -1px;
  left: 0;
  height: 3px;
  background: #0b6ed0;
  content: "";
}

.boundary-note {
  border: 1px solid #b8d6ed;
  border-radius: 8px;
  padding: 13px 16px;
  color: #075985;
  background: #f3f8fc;
  line-height: 1.65;
}

.boundary-note--reserved {
  display: grid;
  color: #8a4b08;
  background: #fff8ed;
  border-color: #f2cf9a;
  gap: 4px;
}

.toolbar {
  display: flex;
  gap: 12px;
}

.toolbar label {
  width: min(100%, 340px);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}

.table-panel {
  min-height: 460px;
  overflow: hidden;
  border: 1px solid var(--oa-line);
  border-radius: 12px;
  background: #fff;
}

.table-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  white-space: nowrap;
}

th,
td {
  min-width: 130px;
  padding: 16px;
  border-bottom: 1px solid var(--oa-line);
  text-align: left;
}

th {
  color: #475569;
  background: #fbfcfc;
  font-size: 13px;
  font-weight: 750;
}

td {
  font-variant-numeric: tabular-nums;
}

.empty-copy,
.state-copy {
  margin: 0;
  padding: 42px 20px;
  color: var(--oa-muted);
  line-height: 1.7;
  text-align: center;
}

.state-copy--error {
  color: var(--oa-danger);
}

@media (max-width: 640px) {
  header {
    flex-direction: column;
  }

  .toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
