<script setup lang="ts">
defineProps<{
  eyebrow: string;
  title: string;
  description: string;
}>();
</script>

<template>
  <section class="auth-card" lang="zh-CN">
    <header>
      <p>{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
      <span>{{ description }}</span>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.auth-card {
  width: min(100%, 500px);
  border: 1px solid var(--oa-line);
  border-radius: 14px;
  padding: clamp(24px, 4vw, 36px);
  background: var(--oa-surface);
  box-shadow:
    0 1px 3px rgb(15 23 42 / 10%),
    0 24px 60px rgb(15 23 42 / 7%);
}

header {
  margin-bottom: 28px;
  text-align: center;
}

header p {
  margin: 0 0 8px;
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
  letter-spacing: 0.04em;
}

h1 {
  margin: 0;
  font-size: clamp(26px, 4vw, 34px);
  line-height: 1.25;
  text-wrap: balance;
}

header span {
  display: block;
  margin-top: 10px;
  color: var(--oa-muted);
  line-height: 1.7;
  text-wrap: pretty;
}

:deep(form) {
  display: grid;
  gap: 18px;
}

:deep(.auth-card__submit) {
  width: 100%;
  margin-top: 4px;
}

:deep(.auth-card__footer) {
  margin: 4px 0 0;
  color: var(--oa-muted);
  font-size: 14px;
  line-height: 1.7;
  text-align: center;
}
</style>
