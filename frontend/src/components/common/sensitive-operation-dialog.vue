<script setup lang="ts">
import { computed, ref } from "vue";

const props = withDefaults(
  defineProps<{
    title: string;
    target: string;
    consequence: string;
    danger?: boolean;
    submitting?: boolean;
    error?: string;
    requireNewPassword?: boolean;
    requireAmount?: boolean;
  }>(),
  {
    danger: false,
    submitting: false,
    error: "",
    requireNewPassword: false,
    requireAmount: false,
  },
);

const emit = defineEmits<{
  cancel: [];
  confirm: [
    payload: {
      current_password: string;
      reason: string;
      new_password?: string;
      amount?: number;
    },
  ];
}>();

const currentPassword = ref("");
const reason = ref("");
const newPassword = ref("");
const amount = ref<number | null>(null);
const isValid = computed(
  () =>
    currentPassword.value.length > 0 &&
    reason.value.trim().length > 0 &&
    (!props.requireNewPassword || newPassword.value.length >= 12) &&
    (!props.requireAmount || (amount.value !== null && amount.value !== 0)),
);

function confirm() {
  if (!isValid.value || props.submitting) return;
  emit("confirm", {
    current_password: currentPassword.value,
    reason: reason.value.trim(),
    ...(props.requireNewPassword ? { new_password: newPassword.value } : {}),
    ...(props.requireAmount ? { amount: amount.value ?? 0 } : {}),
  });
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="!submitting && emit('cancel')">
    <section
      class="sensitive-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sensitive-dialog-title"
    >
      <header>
        <p>敏感操作 · 重新认证</p>
        <h2 id="sensitive-dialog-title">{{ title }}</h2>
        <span>目标：{{ target }}</span>
      </header>
      <div :class="['consequence', { 'consequence--danger': danger }]">
        {{ consequence }}
      </div>
      <label v-if="requireNewPassword">
        <span>临时密码</span>
        <input v-model="newPassword" class="oa-input" type="password" autocomplete="new-password" />
      </label>
      <label v-if="requireAmount">
        <span>调整积分（正数增加，负数扣减）</span>
        <input v-model.number="amount" class="oa-input" type="number" />
      </label>
      <label>
        <span>当前管理员密码</span>
        <input
          v-model="currentPassword"
          class="oa-input"
          type="password"
          autocomplete="current-password"
        />
      </label>
      <label>
        <span>操作原因</span>
        <textarea v-model="reason" class="oa-input" maxlength="500" rows="3" />
      </label>
      <p v-if="error" class="dialog-error" role="alert">{{ error }}</p>
      <footer>
        <button
          class="oa-button oa-button--secondary"
          type="button"
          data-testid="sensitive-cancel"
          :disabled="submitting"
          @click="emit('cancel')"
        >
          取消
        </button>
        <button
          :class="['oa-button', danger ? 'oa-button--danger' : 'oa-button--primary']"
          type="button"
          data-testid="sensitive-confirm"
          :disabled="!isValid || submitting"
          @click="confirm"
        >
          {{ submitting ? "正在提交…" : "确认并记录审计" }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  z-index: 30;
  display: grid;
  padding: 24px;
  background: rgb(15 23 42 / 48%);
  inset: 0;
  place-items: center;
}

.sensitive-dialog {
  display: grid;
  width: min(100%, 540px);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  border-radius: 14px;
  padding: 24px;
  background: var(--oa-surface);
  box-shadow: 0 24px 60px rgb(15 23 42 / 18%);
  gap: 16px;
}

header p,
header h2,
header span {
  margin: 0;
}

header p {
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}

header h2 {
  margin-top: 6px;
  font-size: 24px;
}

header span,
label span {
  color: var(--oa-muted);
}

header span {
  display: block;
  margin-top: 8px;
}

label {
  display: grid;
  gap: 7px;
}

.consequence {
  border: 1px solid #b8d6ed;
  border-radius: 8px;
  padding: 12px 14px;
  color: #075985;
  background: #f3f8fc;
  line-height: 1.65;
}

.consequence--danger {
  color: var(--oa-danger);
  background: #fff5f5;
  border-color: #fecaca;
}

.dialog-error {
  margin: 0;
  color: var(--oa-danger);
}

footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.oa-button--danger {
  color: #fff;
  background: var(--oa-danger);
}
</style>
