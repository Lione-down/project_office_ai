<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import AuthCard from "@/components/common/auth-card.vue";
import AuthLayout from "@/components/layout/auth-layout.vue";
import { authApi } from "@/modules/auth/api";
import { useSessionStore } from "@/store/session";

const phonePattern = /^1[3-9]\d{9}$/;
const router = useRouter();
const session = useSessionStore();
const phoneNumber = ref("");
const inviteCode = ref("");
const password = ref("");
const acceptedTerms = ref(false);
const errorMessage = ref("");
const isSubmitting = ref(false);

function validate() {
  if (!phonePattern.test(phoneNumber.value.trim())) {
    return "请输入有效的中国大陆手机号";
  }
  if (inviteCode.value.trim().length < 4) {
    return "请输入有效邀请码";
  }
  if (password.value.length < 12) {
    return "密码至少需要 12 个字符";
  }
  if (!acceptedTerms.value) {
    return "请阅读并接受服务条款与隐私政策";
  }
  return "";
}

async function submit() {
  errorMessage.value = validate();
  if (errorMessage.value) return;
  isSubmitting.value = true;
  try {
    const tokens = await authApi.register(
      phoneNumber.value.trim(),
      password.value,
      inviteCode.value.trim(),
    );
    session.setTokens(tokens);
    session.applyCurrentUser(await authApi.me(tokens.access_token));
    await router.push({ name: "home" });
  } catch (error) {
    session.clearSession();
    errorMessage.value =
      error instanceof ApiError || error instanceof Error
        ? error.message
        : "无法完成注册，请稍后重试";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <AuthLayout>
    <AuthCard
      eyebrow="邀请注册"
      title="创建 Office AI 账号"
      description="使用有效邀请码注册，文件与生成结果只对你本人可见"
    >
      <form data-testid="register-submit" novalidate @submit.prevent="submit">
        <label class="oa-field">
          <span>手机号</span>
          <input
            v-model="phoneNumber"
            class="oa-input"
            data-testid="phone-number"
            inputmode="numeric"
            autocomplete="tel"
            placeholder="11 位手机号"
          />
        </label>
        <label class="oa-field">
          <span>邀请码</span>
          <input
            v-model="inviteCode"
            class="oa-input"
            data-testid="invite-code"
            autocomplete="off"
          />
        </label>
        <label class="oa-field">
          <span>密码</span>
          <input
            v-model="password"
            class="oa-input"
            data-testid="password"
            type="password"
            autocomplete="new-password"
            placeholder="至少 12 个字符"
          />
        </label>
        <label class="terms-row">
          <input
            v-model="acceptedTerms"
            data-testid="accepted-terms"
            type="checkbox"
          />
          <span>我已阅读并接受服务条款与隐私政策</span>
        </label>
        <p v-if="errorMessage" class="oa-error" role="alert">
          {{ errorMessage }}
        </p>
        <button
          class="oa-button oa-button--primary auth-card__submit"
          type="submit"
          :disabled="isSubmitting"
        >
          {{ isSubmitting ? "创建中…" : "创建账号" }}
        </button>
        <p class="auth-card__footer">
          已有账号？
          <RouterLink to="/login">返回登录</RouterLink>
        </p>
      </form>
    </AuthCard>
  </AuthLayout>
</template>

<style scoped>
.terms-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--oa-muted);
  font-size: 14px;
  line-height: 1.6;
}

.terms-row input {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--oa-accent);
}
</style>
