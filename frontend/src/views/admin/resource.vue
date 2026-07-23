<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { ApiError } from "@/api/request";
import SensitiveOperationDialog from "@/components/common/sensitive-operation-dialog.vue";
import { adminApi } from "@/modules/admin/api";
import {
  adminConfigurations,
  mapAdminRows,
  type AdminDisplayRow,
} from "@/modules/admin/presentation";
import type { AdminSection } from "@/modules/admin/types";
import { useSessionStore } from "@/store/session";

const props = defineProps<{ section: AdminSection }>();
const session = useSessionStore();
interface PendingAction {
  kind:
    | "credential-reveal"
    | "user-status"
    | "user-password"
    | "asset-preview"
    | "asset-download"
    | "asset-delete"
    | "credit-adjust";
  id: string;
  title: string;
  target: string;
  consequence: string;
  danger?: boolean;
  status?: string;
}

const rows = ref<AdminDisplayRow[]>([]);
const rawItems = ref<Array<Record<string, unknown>>>([]);
const isLoading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");
const pendingAction = ref<PendingAction | null>(null);
const isSubmitting = ref(false);
const actionError = ref("");
const revealedValue = ref("");

const config = computed(() => adminConfigurations[props.section]);
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

async function load() {
  rows.value = [];
  rawItems.value = [];
  errorMessage.value = "";
  successMessage.value = "";
  revealedValue.value = "";
  if (config.value.reserved) return;
  isLoading.value = true;
  try {
    const token = requireToken();
    let items: unknown[] = [];
    if (props.section === "invites") items = await adminApi.listInvites(token);
    if (props.section === "providers") items = await adminApi.listProviders(token);
    if (props.section === "credentials") items = await adminApi.listCredentials(token);
    if (props.section === "models") items = await adminApi.listModels(token);
    if (props.section === "users" || props.section === "credits") {
      items = await adminApi.listUsers(token);
    }
    if (props.section === "assets") items = await adminApi.listAssets(token);
    if (props.section === "audit-logs") items = await adminApi.listAuditLogs(token);
    rawItems.value = items as Array<Record<string, unknown>>;
    rows.value = mapAdminRows(props.section, rawItems.value);
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError || error instanceof Error
        ? error.message
        : "无法加载管理数据";
  } finally {
    isLoading.value = false;
  }
}

function itemFor(row: AdminDisplayRow) {
  return rawItems.value.find((item) =>
    Object.values(item).some((value) => String(value) === row.id),
  );
}

function openAction(kind: PendingAction["kind"], row: AdminDisplayRow) {
  const item = itemFor(row);
  const target = String(
    item?.original_filename ?? item?.masked_phone ?? item?.name ?? row.id,
  );
  const definitions: Record<PendingAction["kind"], Omit<PendingAction, "kind" | "id" | "target">> = {
    "credential-reveal": {
      title: "Reveal Credential",
      consequence: "明文仅在本次响应中短暂显示，页面关闭后不再保留。",
    },
    "user-status": {
      title: item?.status === "active" ? "停用用户" : "启用用户",
      consequence:
        item?.status === "active"
          ? "停用后该用户现有 Session 将立即撤销。"
          : "启用后用户可以重新登录。",
      danger: item?.status === "active",
      status: item?.status === "active" ? "suspended" : "active",
    },
    "user-password": {
      title: "重置用户密码",
      consequence: "用户现有 Session 将撤销，下次登录必须修改临时密码。",
      danger: true,
    },
    "asset-preview": {
      title: "预览用户资产",
      consequence: "本次跨用户读取将写入不可变审计记录。",
    },
    "asset-download": {
      title: "下载用户资产",
      consequence: "下载只通过鉴权响应，不暴露 storage key 或磁盘路径。",
    },
    "asset-delete": {
      title: "删除用户资产",
      consequence: "活动文件将立即清理；受控备份残留策略最长 30 天。",
      danger: true,
    },
    "credit-adjust": {
      title: "调整用户积分",
      consequence: "调整会写入只追加积分流水，不能覆盖历史记录。",
    },
  };
  pendingAction.value = { kind, id: row.id, target, ...definitions[kind] };
  actionError.value = "";
  revealedValue.value = "";
}

async function submitAction(payload: {
  current_password: string;
  reason: string;
  new_password?: string;
  amount?: number;
}) {
  if (!pendingAction.value || isSubmitting.value) return;
  isSubmitting.value = true;
  actionError.value = "";
  const action = pendingAction.value;
  try {
    const token = requireToken();
    const sensitive = {
      current_password: payload.current_password,
      reason: payload.reason,
    };
    if (action.kind === "credential-reveal") {
      const response = await adminApi.revealCredential(action.id, sensitive, token);
      revealedValue.value = response.api_key;
      pendingAction.value = null;
    }
    if (action.kind === "user-status") {
      await adminApi.changeUserStatus(action.id, action.status ?? "active", sensitive, token);
    }
    if (action.kind === "user-password") {
      await adminApi.resetPassword(
        action.id,
        { ...sensitive, new_password: payload.new_password ?? "" },
        token,
      );
    }
    if (action.kind === "credit-adjust") {
      await adminApi.adjustCredits(action.id, payload.amount ?? 0, sensitive, token);
    }
    if (action.kind === "asset-preview" || action.kind === "asset-download") {
      const mode = action.kind === "asset-preview" ? "preview" : "download";
      const blob = await adminApi.openAsset(action.id, mode, sensitive, token);
      const url = URL.createObjectURL(blob);
      window.open(url, mode === "preview" ? "_blank" : "_self", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    }
    if (action.kind === "asset-delete") {
      await adminApi.deleteAsset(action.id, sensitive, token);
    }
    successMessage.value = `${action.title}已完成。`;
    if (action.kind !== "credential-reveal") {
      pendingAction.value = null;
      await load();
      successMessage.value = `${action.title}已完成。`;
    }
  } catch (error) {
    actionError.value =
      error instanceof ApiError || error instanceof Error ? error.message : "敏感操作失败";
  } finally {
    isSubmitting.value = false;
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
      Credential 默认掩码；Reveal 必须重新认证、填写原因并进入审计。
    </aside>
    <aside v-if="successMessage" class="boundary-note" role="status">
      {{ successMessage }}
      <a href="/admin/audit-logs">查看审计记录</a>
    </aside>
    <aside v-if="revealedValue" class="boundary-note" role="status">
      <strong>仅显示一次：</strong>
      <code>{{ revealedValue }}</code>
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
              <td v-for="value in row.values" :key="String(value)">
                {{ value }}
              </td>
              <td v-if="section === 'credentials'">
                <button
                  class="table-action"
                  type="button"
                  data-testid="credential-reveal"
                  @click="openAction('credential-reveal', row)"
                >
                  Reveal
                </button>
              </td>
              <td v-if="section === 'users'" class="action-group">
                <button
                  class="table-action"
                  type="button"
                  data-testid="user-status-action"
                  @click="openAction('user-status', row)"
                >
                  {{ itemFor(row)?.status === "active" ? "停用" : "启用" }}
                </button>
                <button class="table-action" type="button" @click="openAction('user-password', row)">
                  重置密码
                </button>
              </td>
              <td v-if="section === 'assets'" class="action-group">
                <button class="table-action" type="button" @click="openAction('asset-preview', row)">预览</button>
                <button class="table-action" type="button" @click="openAction('asset-download', row)">下载</button>
                <button class="table-action table-action--danger" type="button" @click="openAction('asset-delete', row)">删除</button>
              </td>
              <td v-if="section === 'credits'">
                <button class="table-action" type="button" @click="openAction('credit-adjust', row)">
                  调整积分
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!rows.length" class="empty-copy">
          {{ config.reserved ? "等待 T4-002 接入真实管理数据。" : "当前没有记录。" }}
        </p>
      </div>
    </div>

    <SensitiveOperationDialog
      v-if="pendingAction"
      :title="pendingAction.title"
      :target="pendingAction.target"
      :consequence="pendingAction.consequence"
      :danger="pendingAction.danger"
      :submitting="isSubmitting"
      :error="actionError"
      :require-new-password="pendingAction.kind === 'user-password'"
      :require-amount="pendingAction.kind === 'credit-adjust'"
      @cancel="pendingAction = null"
      @confirm="submitAction"
    />
  </section>
</template>

<style scoped src="./resource.css"></style>
