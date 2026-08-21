<script setup lang="ts">
import { useRouter } from "vue-router";
import AppHeader from "../components/AppHeader.vue";

const router = useRouter();
</script>

<template>
  <main class="app-page">
    <div class="page-wrap view-choice-wrap">
      <AppHeader eyebrow="用户界面" title="选择编码类型" />

      <section class="panel view-choice-panel">
        <div class="section-heading view-choice-heading">
          <div>
            <p class="eyebrow">进入系统</p>
            <h2>请选择需要办理的编码业务</h2>
          </div>
        </div>

        <div class="view-choice-grid">
          <button
            type="button"
            class="view-choice-card product-code-choice"
            @click="router.push('/user/components')"
          >
            <span class="view-choice-index">01</span>
            <strong>产品组件编码</strong>
            <p>产品、板卡、软件及其他组件编码。</p>
            <small>进入产品组件编码 →</small>
          </button>

          <button
            type="button"
            class="view-choice-card file-code-choice"
            @click="router.push('/user/files')"
          >
            <span class="view-choice-index">02</span>
            <strong>文件编码</strong>
            <p>查询文件编号、申请新编号，并领取和复制编号。</p>
            <small>进入文件编码 →</small>
          </button>
        </div>
      </section>
    </div>
  </main>
</template>
