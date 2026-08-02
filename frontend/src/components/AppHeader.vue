<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { authState, logout } from "../auth";

defineProps<{
  eyebrow: string;
  title: string;
}>();

const router = useRouter();
const roleLabel = computed(() =>
  authState.me?.user.role === "admin" ? "管理员" : "用户"
);
const canChooseView = computed(() => authState.me?.user.role === "admin");

async function chooseView(): Promise<void> {
  await router.push("/choose-view");
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
