<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { authState, logout } from "../auth";

defineProps<{
  eyebrow: string;
  title: string;
}>();

const router = useRouter();
const route = useRoute();
const roleLabel = computed(() =>
  authState.me?.user.role === "admin" ? "管理员" : "用户"
);
const canChooseView = computed(() => authState.me?.user.role === "admin");
const canChooseCodeType = computed(
  () => authState.me?.user.role === "user" && route.path !== "/user"
);

async function chooseView(): Promise<void> {
  await router.push("/choose-view");
}

async function chooseCodeType(): Promise<void> {
  await router.push("/user");
}

async function handleLogout(): Promise<void> {
  await logout();
  await router.replace("/login");
}
</script>

<template>
  <header class="app-header">
    <div>
      <p class="eyebrow">{{ eyebrow }}</p>
      <h1>{{ title }}</h1>
    </div>
    <div class="account">
      <div class="account-copy">
        <span>{{ authState.me?.user.name }}</span>
        <small>{{ roleLabel }}</small>
      </div>
      <button
        v-if="canChooseCodeType"
        class="text-button"
        type="button"
        @click="chooseCodeType"
      >
        编码类型
      </button>
      <button
        v-if="canChooseView"
        class="text-button"
        type="button"
        @click="chooseView"
      >
        切换视图
      </button>
      <button class="text-button" type="button" @click="handleLogout">退出</button>
    </div>
  </header>
</template>
