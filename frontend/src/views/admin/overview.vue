<script setup lang="ts">
import { onMounted, ref } from "vue";

import { ApiError } from "@/api/request";
import { adminApi } from "@/modules/admin/api";
import type { AdminOverview } from "@/modules/admin/types";
import { useSessionStore } from "@/store/session";
import { getAppEnvironmentLabel } from "@/utils/runtime-config";

const session = useSessionStore();
const environmentLabel = getAppEnvironmentLabel();
const overview = ref<AdminOverview | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");

function requireToken() {
  if (!session.accessToken) throw new Error("管理员 Session 已失效");
  return session.accessToken;
}

async function load() {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    overview.value = await adminApi.getOverview(requireToken());
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError || error instanceof Error
        ? error.message
        : "无法加载管理概览";
  } finally {
    isLoading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="admin-page" lang="zh-CN">
    <header class="page-heading">
      <div>
        <p>管理后台</p>
        <h1>概览</h1>
        <span>查看已交付的账号入口与模型服务配置状态。</span>
      </div>
      <span class="scope-chip">当前环境 · {{ environmentLabel }}</span>
    </header>

    <aside class="security-note">
      <strong>敏感操作需要重新认证</strong>
      <span>Credential Reveal、密码重置、状态变更、积分调整和资产删除都必须填写原因并记录审计。</span>
    </aside>

    <div v-if="isLoading" class="state-panel" aria-live="polite">正在读取服务配置…</div>
    <div v-else-if="errorMessage" class="state-panel state-panel--error">
      <p>{{ errorMessage }}</p>
      <button class="oa-button oa-button--secondary" type="button" @click="load">重新加载</button>
    </div>
    <div v-else-if="overview" class="metric-grid">
      <article>
        <span>已配置 Provider</span>
        <strong>{{ overview.providerCount }}</strong>
        <RouterLink to="/admin/providers">查看服务配置</RouterLink>
      </article>
      <article>
        <span>Credential 记录</span>
        <strong>{{ overview.credentialCount }}</strong>
        <RouterLink to="/admin/credentials">查看掩码记录</RouterLink>
      </article>
      <article>
        <span>已登记 Model</span>
        <strong>{{ overview.modelCount }}</strong>
        <RouterLink to="/admin/models">查看模型路由</RouterLink>
      </article>
      <article>
        <span>邀请码记录</span>
        <strong>{{ overview.inviteCount }}</strong>
        <RouterLink to="/admin/invites">查看邀请码</RouterLink>
      </article>
    </div>

    <section class="boundary-panel">
      <div>
        <p>今天需要处理</p>
        <h2>T4-001 仅交付安全功能壳</h2>
      </div>
      <p>
        用户、任务、全局资产、积分调整和审计日志的敏感 HTTP 闭环由 T4-002 接入。
        当前页面不会以 mock 数据冒充真实运行状态。
      </p>
    </section>
  </section>
</template>

<style scoped>
.admin-page {
  display: grid;
  gap: 22px;
}

.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.page-heading p,
.boundary-panel p {
  margin: 0 0 6px;
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}

h1 {
  margin: 0;
  font-size: 32px;
}

.page-heading div > span {
  display: block;
  margin-top: 8px;
  color: var(--oa-muted);
}

.scope-chip {
  border: 1px solid var(--oa-line);
  border-radius: 8px;
  padding: 9px 12px;
  background: #fff;
  color: #475569;
}

.security-note {
  display: flex;
  align-items: center;
  gap: 14px;
  border: 1px solid var(--oa-line);
  border-radius: 10px;
  padding: 16px 18px;
  background: #fff;
}

.security-note span {
  color: var(--oa-muted);
  line-height: 1.6;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid var(--oa-line);
  border-radius: 12px;
  background: #fff;
}

.metric-grid article {
  display: grid;
  min-height: 180px;
  padding: 24px;
  align-content: center;
  gap: 10px;
}

.metric-grid article + article {
  border-left: 1px solid var(--oa-line);
}

.metric-grid span {
  color: var(--oa-muted);
}

.metric-grid strong {
  font-size: 38px;
  font-variant-numeric: tabular-nums;
}

.metric-grid a {
  font-size: 14px;
  font-weight: 650;
  text-decoration: none;
}

.boundary-panel,
.state-panel {
  border: 1px solid var(--oa-line);
  border-radius: 12px;
  padding: 24px;
  background: #fff;
}

.boundary-panel {
  display: grid;
  grid-template-columns: minmax(220px, 0.75fr) 1.25fr;
  gap: 28px;
}

.boundary-panel h2 {
  margin: 0;
}

.boundary-panel > p {
  margin: 0;
  color: var(--oa-muted);
  font-size: 15px;
  font-weight: 400;
  line-height: 1.75;
}

.state-panel--error {
  color: var(--oa-danger);
}

@media (max-width: 980px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .metric-grid article + article {
    border-left: 0;
  }

  .metric-grid article:nth-child(even) {
    border-left: 1px solid var(--oa-line);
  }

  .metric-grid article:nth-child(n + 3) {
    border-top: 1px solid var(--oa-line);
  }
}

@media (max-width: 600px) {
  .page-heading,
  .security-note {
    align-items: flex-start;
    flex-direction: column;
  }

  .metric-grid,
  .boundary-panel {
    grid-template-columns: 1fr;
  }

  .metric-grid article {
    min-height: 138px;
  }

  .metric-grid article:nth-child(even) {
    border-left: 0;
  }

  .metric-grid article + article {
    border-top: 1px solid var(--oa-line);
  }
}
</style>
