<script setup lang="ts">
import { useRouter } from "vue-router";
import AppHeader from "../components/AppHeader.vue";

const router = useRouter();
</script>

<template>
  <main class="app-page">
    <div class="page-wrap view-choice-wrap">
      <AppHeader eyebrow="管理员身份已验证" title="选择编号系统" />

      <section class="panel view-choice-panel">
        <div class="section-heading view-choice-heading">
          <div>
            <p class="eyebrow">进入系统</p>
            <h2>请选择需要办理的编号业务</h2>
          </div>
          <span>管理员可随时切换</span>
        </div>

        <div class="view-choice-grid">
          <button
            type="button"
            class="view-choice-card product-code-choice"
            @click="router.push('/admin/components')"
          >
            <span class="view-choice-index">01</span>
            <strong>产品组成编号</strong>
            <p>查看整机、部组件、结构、硬件、其他及零件的产品组成编号。</p>
            <small>进入产品组成编号 →</small>
          </button>

          <button
            type="button"
            class="view-choice-card file-code-choice"
            @click="router.push('/admin')"
          >
            <span class="view-choice-index">02</span>
            <strong>文件编号</strong>
            <p>审核文件编号申请、维护项目，并查看文件编号领取记录。</p>
            <small>进入文件编号系统 →</small>
          </button>
        </div>
      </section>
    </div>
  </main>
</template>
