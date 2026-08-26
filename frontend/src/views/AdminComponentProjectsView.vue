<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showToast } from "vant";
import {
  ApiError,
  getComponentProject,
  listAdminComponentProjects
} from "../api";
import AppHeader from "../components/AppHeader.vue";
import type {
  ComponentKind,
  ComponentNode,
  ComponentProject,
  ComponentProjectSummary
} from "../types";

const projects = ref<ComponentProjectSummary[]>([]);
const projectQuery = ref("");
const selectedProject = ref<ComponentProject | null>(null);
const loading = ref(true);
const detailLoading = ref(false);
const labels: Record<ComponentKind, string> = {
  machine: "整机", component: "部组件", structure: "结构", hardware: "硬件",
  software: "软件/逻辑", other: "其他", part: "零件"
};

const filteredProjects = computed(() => {
  const query = projectQuery.value.trim();
  if (!query) return projects.value;
  return projects.value.filter((project) => project.project_code.includes(query));
});

function normalizeProjectQuery(value: string): void {
  projectQuery.value = value.replace(/\D/g, "").slice(0, 4);
}

const detailNodes = computed(() => {
  if (!selectedProject.value) return [];
  const children = new Map<number | null, ComponentNode[]>();
  for (const node of selectedProject.value.nodes) {
    children.set(node.parent_id, [...(children.get(node.parent_id) ?? []), node]);
  }
  const result: Array<ComponentNode & { depth: number }> = [];
  function append(parentId: number | null, depth: number): void {
    const nodes = [...(children.get(parentId) ?? [])].sort(
      (a, b) => a.sequence - b.sequence || a.id - b.id
    );
    for (const node of nodes) {
      result.push({ ...node, depth });
      append(node.id, depth + 1);
    }
  }
  append(null, 0);
  return result;
});

function showError(error: unknown): void {
  showToast(error instanceof ApiError ? error.message : "项目列表加载失败，请稍后重试");
}

async function loadProjects(): Promise<void> {
  loading.value = true;
  try {
    projects.value = await listAdminComponentProjects();
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function openProject(summary: ComponentProjectSummary): Promise<void> {
  detailLoading.value = true;
  try {
    selectedProject.value = await getComponentProject(summary.project_code);
  } catch (error) {
    showError(error);
  } finally {
    detailLoading.value = false;
  }
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

onMounted(loadProjects);
</script>

<template>
  <main class="app-page">
    <div class="page-wrap wide admin-component-page">
      <AppHeader eyebrow="管理员界面 · 产品组成编号" title="产品组成编号项目" />

      <template v-if="!selectedProject">
        <section class="panel admin-component-intro">
          <div class="section-heading">
            <div>
              <p class="eyebrow">项目总览</p>
              <h2>已创建的产品组成编号项目</h2>
            </div>
            <span>{{ projects.length }} 个项目</span>
          </div>
          <p>点击任意项目，查看完整的产品组成结构、编号、创建人和领取记录。</p>
          <div class="admin-project-search">
            <van-field
              :model-value="projectQuery"
              inputmode="numeric"
              maxlength="4"
              clearable
              placeholder="输入项目号检索，例如：1283"
              @update:model-value="normalizeProjectQuery"
            />
            <span v-if="projectQuery">找到 {{ filteredProjects.length }} 个项目</span>
          </div>
        </section>

        <section v-if="loading" class="panel admin-component-empty">正在加载项目列表……</section>
        <section v-else-if="!projects.length" class="panel admin-component-empty">
          <strong>目前还没有产品组成编号项目</strong>
          <p>用户或管理员创建项目后，会显示在这里。</p>
        </section>
        <section v-else-if="!filteredProjects.length" class="panel admin-component-empty">
          <strong>没有找到项目号“{{ projectQuery }}”</strong>
          <p>请检查项目号，或清空检索条件查看全部项目。</p>
          <button type="button" class="text-button" @click="projectQuery = ''">清空检索</button>
        </section>
        <section v-else class="admin-project-grid">
          <button
            v-for="project in filteredProjects"
            :key="project.id"
            type="button"
            class="panel admin-project-card"
            @click="openProject(project)"
          >
            <div class="admin-project-card-top">
              <span class="admin-project-code">{{ project.project_code }}</span>
              <span class="admin-project-status">{{ project.status === "active" ? "正常" : project.status }}</span>
            </div>
            <strong>产品组成编号项目</strong>
            <div class="admin-project-meta">
              <span>创建人：{{ project.created_by_name }}</span>
              <span>创建时间：{{ formatDate(project.created_at) }}</span>
            </div>
            <div class="admin-project-stats">
              <span><b>{{ project.machine_count }}</b> 台整机</span>
              <span><b>{{ project.node_count }}</b> 项组成</span>
              <span><b>{{ project.claim_count }}</b> 次领取</span>
            </div>
            <small>查看产品组成详情 →</small>
          </button>
        </section>
      </template>

      <template v-else>
        <section class="admin-detail-toolbar">
          <button type="button" class="component-back-button" @click="selectedProject = null">‹</button>
          <div><strong>{{ selectedProject.project_code }}</strong><span>产品组成编号详情</span></div>
          <span class="admin-detail-created">项目创建人：{{ selectedProject.created_by_name }}</span>
        </section>
        <section v-if="detailLoading" class="panel admin-component-empty">正在加载项目详情……</section>
        <section v-else class="panel admin-component-detail">
          <div class="section-heading">
            <div><p class="eyebrow">结构及编号</p><h2>产品组成明细</h2></div>
            <span>{{ selectedProject.nodes.length }} 项</span>
          </div>
          <div class="admin-node-list">
            <article v-for="node in detailNodes" :key="node.id" class="admin-node-row">
              <div class="admin-node-name" :style="{ '--node-depth': node.depth }">
                <span class="component-kind-mark">{{ labels[node.kind].slice(0, 1) }}</span>
                <div><strong>{{ node.name }}</strong><small>{{ labels[node.kind] }}</small></div>
              </div>
              <code>{{ node.code }}</code>
              <div class="admin-node-owner"><span>创建人：{{ node.created_by_name }}</span><span>{{ node.stage === "Z" ? "正样件" : "其他" }}</span></div>
              <div class="admin-node-claims">
                <span v-if="!node.claims.length" class="admin-unclaimed">未领取</span>
                <span v-for="claim in node.claims" :key="claim.id">{{ claim.claimant_name }}（{{ formatDate(claim.claimed_at) }}）</span>
              </div>
            </article>
          </div>
        </section>
      </template>
    </div>
  </main>
</template>
