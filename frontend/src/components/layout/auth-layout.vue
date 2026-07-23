<script setup lang="ts">
import AppLogo from "@/components/common/app-logo.vue";

withDefaults(
  defineProps<{
    admin?: boolean;
  }>(),
  { admin: false },
);
</script>

<template>
  <div class="auth-layout">
    <header class="auth-layout__header">
      <AppLogo :admin="admin" />
      <RouterLink :to="admin ? '/login' : '/admin/login'">
        {{ admin ? "返回用户端" : "管理员登录" }}
      </RouterLink>
    </header>
    <main id="main-content" class="auth-layout__main">
      <slot />
    </main>
    <footer>仅限授权访问 · 敏感操作均会记录</footer>
  </div>
</template>

<style scoped>
.auth-layout {
  display: grid;
  min-height: 100vh;
  grid-template-rows: auto 1fr auto;
  padding: 24px clamp(20px, 4vw, 56px);
  background: var(--oa-canvas);
}

.auth-layout__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.auth-layout__header > a:last-child {
  min-height: 40px;
  align-content: center;
  font-weight: 650;
  text-decoration: none;
}

.auth-layout__main {
  display: grid;
  width: 100%;
  place-items: center;
  padding: 48px 0;
}

footer {
  color: var(--oa-muted);
  font-size: 13px;
  text-align: center;
}

@media (max-width: 560px) {
  .auth-layout {
    padding: 16px;
  }

  .auth-layout__header :deep(.app-logo > span:last-child) {
    display: none;
  }

  .auth-layout__main {
    padding: 32px 0;
  }
}
</style>
