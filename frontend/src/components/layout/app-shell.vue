<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import AppLogo from "@/components/common/app-logo.vue";
import { authApi } from "@/modules/auth/api";
import { useSessionStore } from "@/store/session";
import { getAppEnvironmentLabel } from "@/utils/runtime-config";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const environmentLabel = getAppEnvironmentLabel();
const shell = computed(() => route.meta.shell ?? "public");

const userLinks = [
  { label: "首页", to: "/" },
  { label: "任务", to: "/tasks" },
  { label: "文件", to: "/files" },
  { label: "模板", to: "/templates" },
];
const adminLinks = [
  { label: "概览", to: "/admin", activePaths: ["/admin"] },
  {
    label: "用户与邀请码",
    to: "/admin/users",
    activePaths: ["/admin/users", "/admin/invites"],
  },
  {
    label: "服务配置",
    to: "/admin/providers",
    activePaths: ["/admin/providers", "/admin/credentials", "/admin/models"],
  },
  {
    label: "任务与资产",
    to: "/admin/tasks",
    activePaths: ["/admin/tasks", "/admin/assets"],
  },
  { label: "积分", to: "/admin/credits", activePaths: ["/admin/credits"] },
  {
    label: "审计日志",
    to: "/admin/audit-logs",
    activePaths: ["/admin/audit-logs"],
  },
];

function isAdminLinkActive(paths: string[]) {
  return paths.some(
    (path) =>
      route.path === path ||
      (path !== "/admin" && route.path.startsWith(`${path}/`)),
  );
}

async function logout() {
  const loginRoute = session.role === "admin" ? "admin-login" : "login";
  const accessToken = session.accessToken;
  if (accessToken) {
    try {
      await authApi.logout(accessToken);
    } catch {
      // Local credentials are still cleared when the server is unavailable.
    }
  }
  session.clearSession();
  await router.push({ name: loginRoute });
}
</script>

<template>
  <a class="skip-link" href="#main-content">跳到主要内容</a>

  <div v-if="shell === 'user'" class="user-shell" data-testid="app-root">
    <header class="user-shell__header">
      <AppLogo />
      <nav aria-label="用户主导航">
        <RouterLink
          v-for="item in userLinks"
          :key="item.to"
          :to="item.to"
          :aria-current="route.path === item.to ? 'page' : undefined"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="user-shell__account">
        <RouterLink class="credit-link oa-tabular" to="/credits">
          积分 {{ session.creditBalance.toLocaleString("zh-CN") }}
        </RouterLink>
        <button type="button" aria-label="退出登录" @click="logout">
          {{ session.phoneNumber?.slice(-1) ?? "我" }}
        </button>
      </div>
    </header>
    <main id="main-content" class="user-shell__main">
      <slot />
    </main>
  </div>

  <div v-else-if="shell === 'admin'" class="admin-shell" data-testid="app-root">
    <aside>
      <AppLogo admin />
      <nav aria-label="管理后台主导航">
        <RouterLink
          v-for="item in adminLinks"
          :key="item.to"
          :to="item.to"
          :class="{ active: isAdminLinkActive(item.activePaths) }"
          :aria-current="isAdminLinkActive(item.activePaths) ? 'page' : undefined"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
      <RouterLink class="admin-shell__settings" to="/admin">系统设置</RouterLink>
    </aside>
    <div class="admin-shell__workspace">
      <header>
        <span>{{ environmentLabel }}</span>
        <button type="button" @click="logout">
          {{ session.phoneNumber ? `管理员 ${session.phoneNumber.slice(-4)}` : "管理员" }}
        </button>
      </header>
      <main id="main-content">
        <slot />
      </main>
    </div>
  </div>

  <main v-else id="main-content" data-testid="app-root">
    <slot />
  </main>
</template>

<style scoped>
.user-shell,
.admin-shell {
  min-height: 100vh;
  background: var(--oa-canvas);
}

.user-shell__header {
  display: grid;
  min-height: 82px;
  padding: 0 clamp(20px, 4vw, 48px);
  border-bottom: 1px solid var(--oa-line);
  background: rgb(255 255 255 / 92%);
  grid-template-columns: minmax(190px, 1fr) auto minmax(190px, 1fr);
  align-items: center;
  gap: 24px;
}

.user-shell nav {
  display: flex;
  height: 100%;
  align-items: stretch;
  gap: clamp(18px, 3vw, 44px);
}

.user-shell nav a {
  position: relative;
  display: grid;
  min-width: 48px;
  place-items: center;
  color: #475569;
  font-weight: 650;
  text-decoration: none;
}

.user-shell nav a[aria-current="page"] {
  color: var(--oa-ink);
}

.user-shell nav a[aria-current="page"]::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: var(--oa-accent);
  content: "";
}

.user-shell__account {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 18px;
}

.credit-link {
  min-height: 40px;
  align-content: center;
  color: #475569;
  text-decoration: none;
}

.user-shell__account button {
  width: 42px;
  height: 42px;
  border: 0;
  border-radius: 50%;
  color: var(--oa-ink);
  background: #e8ebee;
  font-weight: 750;
}

.user-shell__main {
  width: min(100%, 1280px);
  margin: 0 auto;
}

.admin-shell {
  display: grid;
  grid-template-columns: 228px minmax(0, 1fr);
}

.admin-shell > aside {
  position: sticky;
  top: 0;
  display: grid;
  height: 100vh;
  padding: 28px 18px 24px;
  border-right: 1px solid var(--oa-line);
  background: #fff;
  grid-template-rows: auto 1fr auto;
  gap: 38px;
}

.admin-shell nav {
  display: grid;
  align-content: start;
  gap: 8px;
}

.admin-shell nav a,
.admin-shell__settings {
  display: flex;
  min-height: 48px;
  align-items: center;
  border-radius: 8px;
  padding: 0 14px;
  color: var(--oa-ink);
  font-weight: 650;
  text-decoration: none;
}

.admin-shell nav a.active {
  color: #0759bd;
  background: #eef5fc;
  box-shadow: inset 3px 0 #0b6ed0;
}

.admin-shell__settings {
  border-top: 1px solid var(--oa-line);
  border-radius: 0;
  padding-top: 18px;
}

.admin-shell__workspace {
  min-width: 0;
}

.admin-shell__workspace > header {
  display: flex;
  min-height: 72px;
  justify-content: flex-end;
  align-items: center;
  gap: 20px;
  padding: 0 32px;
  border-bottom: 1px solid var(--oa-line);
  background: rgb(255 255 255 / 88%);
}

.admin-shell__workspace > header span {
  color: #475569;
}

.admin-shell__workspace > header button {
  min-height: 40px;
  border: 0;
  border-radius: 8px;
  padding: 0 12px;
  color: var(--oa-ink);
  background: transparent;
  font-weight: 650;
}

.admin-shell__workspace main {
  min-width: 0;
  padding: 32px;
}

@media (max-width: 900px) {
  .user-shell__header {
    grid-template-columns: auto 1fr auto;
  }

  .user-shell__header :deep(.app-logo > span:last-child),
  .credit-link {
    display: none;
  }

  .admin-shell {
    grid-template-columns: 1fr;
  }

  .admin-shell > aside {
    position: static;
    display: grid;
    height: auto;
    padding: 14px 18px;
    border-right: 0;
    border-bottom: 1px solid var(--oa-line);
    grid-template-columns: auto minmax(0, 1fr);
    gap: 18px;
  }

  .admin-shell > aside :deep(.app-logo > span:last-child),
  .admin-shell__settings {
    display: none;
  }

  .admin-shell nav {
    display: flex;
    overflow-x: auto;
    gap: 4px;
  }

  .admin-shell nav a {
    flex: 0 0 auto;
    min-height: 44px;
    white-space: nowrap;
  }

  .admin-shell nav a.active {
    box-shadow: inset 0 -3px #0b6ed0;
  }
}

@media (max-width: 620px) {
  .user-shell__header {
    padding: 10px 14px 0;
    grid-template-columns: auto auto;
    gap: 12px;
  }

  .user-shell nav {
    grid-row: 2;
    grid-column: 1 / -1;
    overflow-x: auto;
    gap: 24px;
  }

  .user-shell nav a {
    min-height: 48px;
  }

  .user-shell__account {
    justify-self: end;
  }

  .admin-shell__workspace > header {
    min-height: 60px;
    padding: 0 16px;
  }

  .admin-shell__workspace main {
    padding: 20px 16px 32px;
  }
}
</style>
