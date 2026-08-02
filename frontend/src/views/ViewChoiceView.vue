<script setup lang="ts">
import { useRouter } from "vue-router";
import AppHeader from "../components/AppHeader.vue";

const router = useRouter();
</script>

<template>
  <main class="app-page">
    <div class="page-wrap view-choice-wrap">
      <AppHeader eyebrow="管理员身份已验证" title="选择工作视图" />

      <section class="panel view-choice-panel">
        <div class="section-heading view-choice-heading">
          <div>
            <p class="eyebrow">进入系统</p>
            <h2>这次要处理哪类工作？</h2>
          </div>
          <span>管理员可随时切换</span>
        </div>

        <div class="view-choice-grid">
          <button
            type="button"
            class="view-choice-card user-choice"
            @click="router.push('/user')"
          >
            <span class="view-choice-index">01</span>
            <strong>用户视图</strong>
            <p>查询文件编号、申请新编号，并领取和复制编号。</p>
            <small>进入编码领取 →</small>
          </button>

          <button
            type="button"
            class="view-choice-card admin-choice"
            @click="router.push('/admin')"
          >
            <span class="view-choice-index">02</span>
            <strong>管理员视图</strong>
            <p>审核编号申请、维护项目，并查看编号领取记录。</p>
            <small>进入管理后台 →</small>
          </button>
        </div>
      </section>
    </div>
  </main>
</template>
