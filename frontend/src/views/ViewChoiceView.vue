<script setup lang="ts">
import { useRouter } from "vue-router";
import AppHeader from "../components/AppHeader.vue";

const router = useRouter();
</script>

<template>
  <main class="app-page">
    <div class="page-wrap view-choice-wrap">
      <AppHeader eyebrow="管理员身份已验证" title="选择进入的界面" />

      <section class="panel view-choice-panel">
        <div class="section-heading view-choice-heading">
          <div>
            <p class="eyebrow">进入系统</p>
            <h2>请选择以“用户”或“管理员”身份进入</h2>
          </div>
          <span>可随时切换</span>
        </div>

        <div class="view-choice-grid">
          <button
            type="button"
            class="view-choice-card product-code-choice"
            @click="router.push('/user')"
          >
            <span class="view-choice-index">用户</span>
            <strong>用户界面</strong>
            <p>以普通用户身份使用：查询与领取文件编号、申请新编号，以及编制产品组件编号。</p>
            <small>进入用户界面 →</small>
          </button>

          <button
            type="button"
            class="view-choice-card file-code-choice"
            @click="router.push('/admin')"
          >
            <span class="view-choice-index">管理</span>
            <strong>管理员 · 文件编号</strong>
            <p>审核文件编号申请、维护项目、批量生成编号，并查看文件编号领取记录。</p>
            <small>进入管理员 · 文件编号 →</small>
          </button>

          <button
            type="button"
            class="view-choice-card admin-choice"
            @click="router.push('/admin/components')"
          >
            <span class="view-choice-index">管理</span>
            <strong>管理员 · 产品组成编号</strong>
            <p>查看并维护整机、部组件、结构、硬件、其他及零件的产品组成编号。</p>
            <small>进入管理员 · 产品组成编号 →</small>
          </button>
        </div>
      </section>
    </div>
  </main>
</template>
