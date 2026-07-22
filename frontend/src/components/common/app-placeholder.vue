<script setup lang="ts">
defineProps<{ title: string }>();
</script>

<template>
  <section aria-live="polite">
    <h1>{{ title }}</h1>
    <p>应用基础设施已就绪，业务功能将在后续任务中实现。</p>
  </section>
</template>
