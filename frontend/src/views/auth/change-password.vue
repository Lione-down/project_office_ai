<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import AuthCard from "@/components/common/auth-card.vue";
import AuthLayout from "@/components/layout/auth-layout.vue";
import { authApi } from "@/modules/auth/api";
import { useSessionStore } from "@/store/session";

const router = useRouter();
const session = useSessionStore();
const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const errorMessage = ref("");
const isSubmitting = ref(false);

async function submit() {
  if (newPassword.value.length < 12) {
    errorMessage.value = "新密码至少需要 12 个字符";
    return;
  }
  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = "两次输入的新密码不一致";
    return;
  }
  if (!session.accessToken) {
    errorMessage.value = "登录状态已失效，请重新登录";
    return;
  }
  errorMessage.value = "";
  isSubmitting.value = true;
  try {
    const tokens = await authApi.changePassword(
      currentPassword.value,
      newPassword.value,
      session.accessToken,
    );
    session.setTokens(tokens);
    const user = await authApi.me(tokens.access_token);
    session.applyCurrentUser(user);
    await router.push({ name: user.role === "admin" ? "admin-overview" : "home" });
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError || error instanceof Error
        ? error.message
        : "无法修改密码，请稍后重试";
  } finally {
    isSubmitting.value = false;
  }
}

async function logout() {
  const accessToken = session.accessToken;
  const loginRoute = session.role === "admin" ? "admin-login" : "login";
  if (accessToken) {
    try {
      await authApi.logout(accessToken);
    } catch {
      // The browser must still discard credentials when revoke is unavailable.
    }
  }
  session.clearSession();
  await router.push({ name: loginRoute });
}
</script>

<template>
  <AuthLayout>
    <AuthCard
      eyebrow="账号安全"
      title="先设置新密码"
      description="管理员重置密码后必须完成此步骤，不能跳过"
    >
      <form data-testid="change-password-submit" @submit.prevent="submit">
        <input
          class="credential-username"
          type="text"
          autocomplete="username"
          :value="session.phoneNumber ?? ''"
          tabindex="-1"
          aria-hidden="true"
          readonly
        />
        <label class="oa-field">
          <span>当前密码</span>
          <input
            v-model="currentPassword"
            class="oa-input"
            data-testid="current-password"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <label class="oa-field">
          <span>新密码</span>
          <input
            v-model="newPassword"
            class="oa-input"
            data-testid="new-password"
            type="password"
            autocomplete="new-password"
            required
          />
        </label>
        <label class="oa-field">
          <span>再次输入新密码</span>
          <input
            v-model="confirmPassword"
            class="oa-input"
            data-testid="confirm-password"
            type="password"
            autocomplete="new-password"
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
          {{ isSubmitting ? "保存中…" : "保存新密码" }}
        </button>
        <button
          class="logout-button"
          data-testid="logout-forced-password"
          type="button"
          :disabled="isSubmitting"
          @click="logout"
        >
          退出登录
        </button>
      </form>
    </AuthCard>
  </AuthLayout>
</template>

<style scoped>
.logout-button {
  display: block;
  min-height: 40px;
  margin: 16px auto 0;
  border: 0;
  padding: 0 12px;
  color: var(--oa-muted);
  background: transparent;
  font-weight: 650;
}

.credential-username {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
</style>
