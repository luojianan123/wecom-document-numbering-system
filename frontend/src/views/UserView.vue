<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showToast } from "vant";
import {
  ApiError,
  claimCode,
  generateMissingCode,
  listProjectCodes,
  listProjects,
  searchCodes
} from "../api";
import AppHeader from "../components/AppHeader.vue";
import type { FileCode, Project } from "../types";

const projects = ref<Project[]>([]);
const selectedProjectId = ref<number | null>(null);
const projectQuery = ref("");
const projectOptionsVisible = ref(false);
const fileName = ref("");
const searchedFileName = ref("");
const results = ref<FileCode[]>([]);
const resultMode = ref<"idle" | "search" | "all">("idle");
const loading = ref(false);
const loadingAll = ref(false);
const generating = ref(false);

const selectedProject = computed(() =>
  projects.value.find((item) => item.id === selectedProjectId.value)
);

const filteredProjects = computed(() => {
  const query = projectQuery.value.trim().toLocaleLowerCase();
  if (!query) return projects.value;
  return projects.value.filter(
    (project) =>
      project.project_code.toLocaleLowerCase().includes(query) ||
      project.project_name.toLocaleLowerCase().includes(query)
  );
});

const normalizedSearchedFileName = computed(() =>
  normalizeFileNameForComparison(searchedFileName.value)
);

const hasExactSearchMatch = computed(
  () =>
    resultMode.value === "search" &&
    normalizedSearchedFileName.value.length > 0 &&
    results.value.some(
      (item) =>
        normalizeFileNameForComparison(item.standard_name) ===
        normalizedSearchedFileName.value
    )
);

const showGenerateAlternative = computed(
  () =>
    resultMode.value === "search" &&
    results.value.length > 0 &&
    !hasExactSearchMatch.value
);

onMounted(async () => {
  try {
    projects.value = await listProjects();
  } catch (error) {
    showError(error);
  }
});

function showError(error: unknown): void {
  showToast(error instanceof ApiError ? error.message : "操作失败，请稍后重试");
}

function resetResults(): void {
  results.value = [];
  resultMode.value = "idle";
  searchedFileName.value = "";
}

function normalizeFileNameForComparison(value: string): string {
  const leaf = value.replaceAll("\\", "/").split("/").pop() ?? "";
  const normalized = leaf.normalize("NFKC").trim();
  const suffixMatch = normalized.match(/(\.[^./\\]{1,8})$/);
  const withoutSuffix = suffixMatch
    ? normalized.slice(0, -suffixMatch[1].length)
    : normalized;
  return withoutSuffix.replace(/\s+/g, "").toLocaleLowerCase();
}

function onProjectQueryChange(value: string): void {
  if (value.trim() && selectedProjectId.value !== null) {
    selectedProjectId.value = null;
    resetResults();
  }
  projectOptionsVisible.value = true;
}

function onFileNameChange(): void {
  if (resultMode.value === "search") {
    resetResults();
  }
}

function onProjectPickerFocusOut(event: FocusEvent): void {
  const picker = event.currentTarget as HTMLElement;
  const nextTarget = event.relatedTarget;
  if (!(nextTarget instanceof Node) || !picker.contains(nextTarget)) {
    projectOptionsVisible.value = false;
  }
}

function selectProject(project: Project): void {
  if (selectedProjectId.value !== project.id) {
    resetResults();
  }
  selectedProjectId.value = project.id;
  projectQuery.value = "";
  projectOptionsVisible.value = false;
}

function clearSelectedProject(): void {
  selectedProjectId.value = null;
  projectQuery.value = "";
  projectOptionsVisible.value = false;
  resetResults();
}

async function search(): Promise<void> {
  if (!selectedProjectId.value || !fileName.value.trim()) {
    showToast("请选择项目并输入文件名称");
    return;
  }
  loading.value = true;
  resultMode.value = "idle";
  try {
    const query = fileName.value.trim();
    searchedFileName.value = query;
    results.value = await searchCodes(selectedProjectId.value, query);
    resultMode.value = "search";
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function showAll(): Promise<void> {
  if (!selectedProjectId.value) {
    showToast("请先选择项目");
    return;
  }
  loadingAll.value = true;
  resultMode.value = "idle";
  try {
    results.value = await listProjectCodes(selectedProjectId.value);
    resultMode.value = "all";
  } catch (error) {
    showError(error);
  } finally {
    loadingAll.value = false;
  }
}

async function copyAndClaim(item: FileCode): Promise<void> {
  try {
    await claimCode(item.id);
    await navigator.clipboard.writeText(item.final_code);
    showToast("编码已领取并复制");
  } catch (error) {
    showError(error);
  }
}

async function generate(): Promise<void> {
  const requestedFileName =
    searchedFileName.value.trim() || fileName.value.trim();
  if (!selectedProjectId.value || !requestedFileName) return;
  generating.value = true;
  try {
    const item = await generateMissingCode(
      selectedProjectId.value,
      requestedFileName
    );
    results.value = [item];
    searchedFileName.value = requestedFileName;
    resultMode.value = "search";
    showToast("编码已生成");
  } catch (error) {
    showError(error);
  } finally {
    generating.value = false;
  }
}
</script>

<template>
  <main class="app-page">
    <div class="page-wrap">
      <AppHeader eyebrow="用户界面" title="编码领取" />

      <section class="hero-strip">
        <div>
          <span class="step-label">01</span>
          <h2>找到文件，领取正确编码</h2>
          <p>选择项目并输入文件名称。查询不到时，可直接提交名称补充编码。</p>
        </div>
        <div class="hero-rule">AB-CD-EF-G-H</div>
      </section>

      <section class="panel search-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">文件查询</p>
            <h2>输入文件名称</h2>
          </div>
        </div>

        <label class="field-label" for="project">项目</label>
        <div
          v-if="!selectedProject"
          class="project-picker"
          @focusout="onProjectPickerFocusOut"
        >
          <van-field
            id="project"
            v-model="projectQuery"
            class="project-picker-input"
            placeholder="输入项目号或项目名称搜索"
            clearable
            autocomplete="off"
            @focus="projectOptionsVisible = true"
            @update:model-value="onProjectQueryChange"
          />
          <div
            v-if="projectOptionsVisible"
            class="project-picker-results"
          >
            <button
              v-for="project in filteredProjects"
              :key="project.id"
              type="button"
              :class="[
                'project-option',
                { selected: project.id === selectedProjectId }
              ]"
              @click="selectProject(project)"
            >
              <strong>{{ project.project_code }}</strong>
              <span>{{ project.project_name }}</span>
            </button>
            <div v-if="!filteredProjects.length" class="project-picker-empty">
              未找到匹配项目
            </div>
          </div>
        </div>

        <div v-if="selectedProject" class="selected-project">
          <div>
            <strong>{{ selectedProject.project_code }}</strong>
            <span>{{ selectedProject.project_name }}</span>
          </div>
          <div class="selected-project-actions">
            <van-button
              plain
              color="#176443"
              :loading="loadingAll"
              loading-text="加载中…"
              @click="showAll"
            >
              显示全部
            </van-button>
            <button
              type="button"
              class="clear-project-button"
              title="重新选择项目"
              aria-label="清除当前项目并重新选择"
              @click="clearSelectedProject"
            >
              ×
            </button>
          </div>
        </div>

        <van-cell-group inset>
          <van-field
            v-model="fileName"
            label="文件名称"
            placeholder="例如：控制模块技术要求"
            clearable
            @update:model-value="onFileNameChange"
            @keyup.enter="search"
          />
        </van-cell-group>
        <van-button
          block
          color="#17324d"
          size="large"
          :loading="loading"
          loading-text="查询中…"
          @click="search"
        >
          查询编码
        </van-button>
      </section>

      <section v-if="results.length" class="results-section" aria-live="polite">
        <div class="section-heading">
          <div>
            <p class="eyebrow">查询结果</p>
            <h2>
              {{ resultMode === "all" ? "全部文件名和编号" : "可领取编码" }}
            </h2>
          </div>
          <van-tag color="#e8f3ee" text-color="#176443">
            {{ results.length }} 条
          </van-tag>
        </div>
        <div v-if="showGenerateAlternative" class="similar-match-notice">
          当前结果为库中的相近文件。可以直接领取已有编号；若都不是所需文件，请生成
          “{{ searchedFileName }}”的新编码。
        </div>
        <article v-for="item in results" :key="item.id" class="code-card">
          <div class="code-meta">
            <span>{{ item.standard_name }}</span>
            <small>{{ item.source === "admin_batch" ? "项目初始化" : "缺失补码" }}</small>
          </div>
          <code>{{ item.final_code }}</code>
          <div class="segment-row">
            <span>级别 {{ item.segment_c }}</span>
            <span>功能 {{ item.segment_d }}</span>
            <span>简号 {{ item.segment_f }}</span>
            <span>版本 {{ item.segment_h }}</span>
          </div>
          <div class="code-actions">
            <van-button
              block
              plain
              color="#17324d"
              @click="copyAndClaim(item)"
            >
              领取并复制
            </van-button>
            <van-button
              v-if="showGenerateAlternative"
              block
              color="#b4532a"
              :loading="generating"
              loading-text="正在生成…"
              @click="generate"
            >
              需要生成新编码
            </van-button>
          </div>
        </article>
      </section>

      <section
        v-else-if="resultMode === 'search'"
        class="panel missing-panel"
        aria-live="polite"
      >
        <span class="step-label warm">02</span>
        <h2>未找到对应编码</h2>
        <p>系统将修正当前文件名称，查重后按固定规则生成编码。</p>
        <div class="submitted-name">{{ searchedFileName }}</div>
        <van-button
          block
          color="#b4532a"
          size="large"
          :loading="generating"
          loading-text="AI 正在处理…"
          @click="generate"
        >
          AI 修正文件名并发码
        </van-button>
      </section>

      <van-empty
        v-else-if="resultMode === 'all'"
        image="search"
        description="该项目暂无可用文件和编号"
      />

      <van-empty
        v-else-if="!loading && !loadingAll"
        image="search"
        description="输入文件名称后开始查询"
      />
    </div>
  </main>
</template>
