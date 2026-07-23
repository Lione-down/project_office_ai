<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import AuthCard from "@/components/common/auth-card.vue";
import AuthLayout from "@/components/layout/auth-layout.vue";
import { authApi } from "@/modules/auth/api";
import { useSessionStore } from "@/store/session";

const props = withDefaults(
  defineProps<{
    mode?: "user" | "admin";
  }>(),
  { mode: "user" },
);

const router = useRouter();
const session = useSessionStore();
const phoneNumber = ref("");
const password = ref("");
const errorMessage = ref("");
const isSubmitting = ref(false);
const isAdmin = computed(() => props.mode === "admin");

function readableError(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return "无法登录，请稍后重试";
}

async function submit() {
  errorMessage.value = "";
  isSubmitting.value = true;
  try {
    const tokens = await authApi.login(phoneNumber.value.trim(), password.value);
    session.setTokens(tokens);
    const user = await authApi.me(tokens.access_token);
    if (isAdmin.value && user.role !== "admin") {
      session.clearSession();
      errorMessage.value = "此账号没有管理员权限";
      return;
    }
    session.applyCurrentUser(user);
    if (user.must_change_password) {
      await router.push({ name: "password-change" });
    } else {
      await router.push({ name: isAdmin.value ? "admin-overview" : "home" });
    }
  } catch (error) {
    session.clearSession();
    errorMessage.value = readableError(error);
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <AuthLayout :admin="isAdmin">
    <AuthCard
      :eyebrow="isAdmin ? 'Office AI 管理台' : 'Office AI'"
      :title="isAdmin ? '管理员登录' : '登录'"
      :description="
        isAdmin ? '使用已授权的管理员账号进入' : '继续处理你的材料与生成任务'
      "
    >
      <form data-testid="login-submit" @submit.prevent="submit">
        <label class="oa-field">
          <span>手机号</span>
          <div class="phone-field">
            <span aria-hidden="true">+86</span>
            <input
              v-model="phoneNumber"
              class="oa-input"
              data-testid="phone-number"
              inputmode="numeric"
              autocomplete="tel"
              placeholder="请输入手机号"
              required
            />
          </div>
        </label>
        <label class="oa-field">
          <span>密码</span>
          <input
            v-model="password"
            class="oa-input"
            data-testid="password"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <p v-if="errorMessage" class="oa-error" role="alert">
          {{ errorMessage }}
        </p>
        <button
          class="oa-button oa-button--primary auth-card__submit"
          type="submit"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? "登录中…" : "登录" }}
        </button>
        <p v-if="!isAdmin" class="auth-card__footer">
          还没有账号？
          <RouterLink to="/register">使用邀请码注册</RouterLink>
        </p>
        <p v-else class="auth-card__footer">登录失败次数过多时将暂时限制访问</p>
      </form>
    </AuthCard>
  </AuthLayout>
</template>

<style scoped>
.phone-field {
  display: grid;
  grid-template-columns: 60px 1fr;
}

.phone-field > span {
  display: grid;
  min-height: 46px;
  place-items: center;
  border: 1px solid #cbd5e1;
  border-right: 0;
  border-radius: 8px 0 0 8px;
  background: var(--oa-surface-muted);
  font-weight: 650;
}

.phone-field .oa-input {
  border-radius: 0 8px 8px 0;
}
</style>
