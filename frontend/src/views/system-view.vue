<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import AppPlaceholder from "@/components/common/app-placeholder.vue";

const route = useRoute();
const title = computed(() => {
  const labels: Record<string, string> = {
    login: "登录入口",
    home: "Office AI",
    admin: "管理入口",
  };
  return labels[String(route.name)] ?? "Office AI";
});
</script>

<template>
  <AppPlaceholder :title="title" />
</template>
