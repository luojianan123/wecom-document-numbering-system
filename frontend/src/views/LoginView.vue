<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { showToast } from "vant";
import ucasLogo from "../assets/ucas-logo-white.png";
import { loginForDevelopment } from "../auth";
import { ApiError, startQrLogin } from "../api";
import type { Role } from "../types";

const router = useRouter();
const route = useRoute();
const loading = ref(false);
const authMode = ref<"mock" | "live">("live");
const authorizationUrl = ref<string | null>(null);

onMounted(async () => {
  if (typeof route.query.auth_error === "string") {
    showToast(route.query.auth_error);
  }
  try {
    const result = await startQrLogin("/choose-view");
    authMode.value = result.mode;
    authorizationUrl.value = result.authorization_url;
  } catch {
    authMode.value = "live";
  }
});

async function scanLogin(): Promise<void> {
  loading.value = true;
  try {
    if (authorizationUrl.value) {
      window.location.assign(authorizationUrl.value);
      return;
    }
    const result = await startQrLogin("/choose-view");
    authMode.value = result.mode;
    authorizationUrl.value = result.authorization_url;
    if (authorizationUrl.value) {
      window.location.assign(authorizationUrl.value);
      return;
    }
    showToast("本地开发模式请使用下方测试身份");
  } catch (error) {
    showToast(error instanceof ApiError ? error.message : "暂时无法发起扫码登录");
  } finally {
    loading.value = false;
  }
}

async function mockLogin(role: Role): Promise<void> {
  loading.value = true;
  try {
    const me = await loginForDevelopment(role);
    await router.replace(me.user.role === "admin" ? "/choose-view" : "/user");
  } catch (error) {
    showToast(error instanceof ApiError ? error.message : "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-brand">
      <div class="brand-mark">
        <img :src="ucasLogo" alt="国科环宇 UCAS" />
      </div>
      <h1 class="brand-title">项目编号系统</h1>
      <p class="brand-statement">统一文件与产品组件编码，实现全对象规范编号。</p>
      <div class="format-sample">
        <span>编号示例</span>
        <strong>GH1234-3KZ-010JY-1.00</strong>
      </div>
    </section>

    <section class="login-panel" aria-labelledby="login-title">
      <van-tag color="#e8f3ee" text-color="#176443">第一阶段 · Web 入口</van-tag>
      <h2 id="login-title">使用企业微信登录</h2>
      <p>请使用本企业的企业微信扫描二维码完成身份认证。</p>
      <van-button
        block
        color="#17324d"
        size="large"
        :loading="loading"
        loading-text="正在打开…"
        @click="scanLogin"
      >
        企业微信扫码登录
      </van-button>

      <div v-if="authMode === 'mock'" class="dev-login">
        <div class="divider"><span>本地开发身份</span></div>
        <div class="dev-actions">
          <van-button plain color="#17324d" @click="mockLogin('user')">用户界面</van-button>
          <van-button plain color="#17324d" @click="mockLogin('admin')">管理员界面</van-button>
        </div>
      </div>
      <p class="login-note">仅应用可见范围内的企业成员可以进入系统。</p>
    </section>
  </main>
</template>
