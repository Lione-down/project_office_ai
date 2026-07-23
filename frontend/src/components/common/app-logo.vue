<script setup lang="ts">
withDefaults(
  defineProps<{
    admin?: boolean;
  }>(),
  { admin: false },
);
</script>

<template>
  <RouterLink class="app-logo" :to="admin ? '/admin' : '/'" aria-label="Office AI 首页">
    <span class="app-logo__mark" aria-hidden="true">OA</span>
    <span>
      <strong>Office AI</strong>
      <small v-if="admin">管理台</small>
    </span>
  </RouterLink>
</template>

<style scoped>
.app-logo {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  gap: 12px;
  color: var(--oa-ink);
  text-decoration: none;
}

.app-logo__mark {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 8px;
  color: #fff;
  background: var(--oa-ink);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.app-logo strong,
.app-logo small {
  display: block;
}

.app-logo strong {
  font-size: 20px;
  letter-spacing: -0.012em;
}

.app-logo small {
  margin-top: 1px;
  color: var(--oa-muted);
  font-size: 12px;
}
</style>
