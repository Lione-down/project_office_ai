<script setup lang="ts">
import type { PreflightConflict } from "@/modules/briefs/types";


defineProps<{
  conflicts: PreflightConflict[];
}>();

const resolutionValues = defineModel<Record<string, string>>({ required: true });
const unitOptions = [
  { value: "CNY", label: "人民币（元）" },
  { value: "CNY_10K", label: "人民币（万元）" },
  { value: "CNY_100M", label: "人民币（亿元）" },
  { value: "USD", label: "美元" },
  { value: "PERCENT", label: "百分比（%）" },
  { value: "RATIO", label: "比率（0–1）" },
  { value: "COUNT_PERSON", label: "人数（人）" },
  { value: "COUNT_ITEM", label: "数量（个/件）" },
  { value: "COUNT_SET", label: "套数（套）" },
  { value: "COUNT_UNIT", label: "台数（台）" },
] as const;

function conflictKey(conflict: PreflightConflict) {
  return `${conflict.code}:${conflict.evidence_ids.join(",")}`;
}
</script>

<template>
  <div class="unit-resolution-list" aria-label="单位确认">
    <label
      v-for="(conflict, index) in conflicts"
      :key="conflictKey(conflict)"
      class="unit-resolution-item"
    >
      <span>{{ conflict.message }}</span>
      <select
        v-model="resolutionValues[conflictKey(conflict)]"
        :data-testid="`unit-resolution-${index}`"
      >
        <option value="">请选择单位</option>
        <option
          v-for="option in unitOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </option>
      </select>
    </label>
  </div>
</template>

<style scoped>
.unit-resolution-list {
  display: grid;
  margin-top: 14px;
  gap: 12px;
}

.unit-resolution-item {
  display: grid;
  margin: 0;
  gap: 7px;
  font-weight: 650;
}

.unit-resolution-item select {
  width: 100%;
  min-height: 42px;
  border: 1px solid oklch(0.78 0.04 70);
  border-radius: 8px;
  padding: 0 10px;
  color: var(--ink);
  background: var(--surface);
  font: inherit;
}
</style>
