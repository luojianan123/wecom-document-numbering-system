<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { showToast } from "vant";
import {
  ApiError,
  claimCode,
  generateMissingCode,
  listMyNameReviews,
  listProjectCodes,
  listProjects,
  searchCodes
} from "../api";
import AppHeader from "../components/AppHeader.vue";
import type { FileCode, NameReview, Project } from "../types";

const projects = ref<Project[]>([]);
const selectedProjectId = ref<number | null>(null);
const projectQuery = ref("");
const projectOptionsVisible = ref(false);
const projectPicker = ref<HTMLElement | null>(null);
const productName = ref("");
const stageName = ref("");
const fileType = ref("");
const searchedFileName = ref("");
const results = ref<FileCode[]>([]);
const resultMode = ref<"idle" | "search" | "all">("idle");
const loading = ref(false);
const loadingAll = ref(false);
const generating = ref(false);
const reviews = ref<NameReview[]>([]);
const loadingReviews = ref(false);

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

const mergedFileName = computed(() =>
  [productName.value, stageName.value, fileType.value]
    .map((value) => value.trim())
    .filter(Boolean)
    .join("")
);

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
  document.addEventListener("pointerdown", onDocumentPointerDown);
  try {
    [projects.value, reviews.value] = await Promise.all([
      listProjects(),
      listMyNameReviews()
    ]);
  } catch (error) {
    showError(error);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocumentPointerDown);
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

function onFileSegmentChange(): void {
  if (resultMode.value === "search") {
    resetResults();
  }
}

function onProjectPickerFocusOut(event: FocusEvent): void {
  const picker = event.currentTarget as HTMLElement;
  const nextTarget = event.relatedTarget;
  if (nextTarget instanceof Node && !picker.contains(nextTarget)) {
    projectOptionsVisible.value = false;
  }
}

function onDocumentPointerDown(event: PointerEvent): void {
  const target = event.target;
  if (
    projectOptionsVisible.value &&
    target instanceof Node &&
    projectPicker.value &&
    !projectPicker.value.contains(target)
  ) {
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
  if (!selectedProjectId.value) {
    showToast("请选择项目");
    return;
  }
  if (!productName.value.trim()) {
    showToast("请输入产品/部组件");
    return;
  }
  if (!fileType.value.trim()) {
    showToast("请输入文件类型");
    return;
  }
  loading.value = true;
  resultMode.value = "idle";
  try {
    const query = mergedFileName.value;
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
    searchedFileName.value.trim() || mergedFileName.value;
  if (!selectedProjectId.value || !requestedFileName) return;
  generating.value = true;
  try {
    const outcome = await generateMissingCode(
      selectedProjectId.value,
      requestedFileName
    );
    searchedFileName.value = requestedFileName;
    if (outcome.file_code) {
      results.value = [outcome.file_code];
      resultMode.value = "search";
    } else {
      results.value = [];
      resultMode.value = "idle";
      await refreshReviews();
    }
    showToast(outcome.message);
  } catch (error) {
    showError(error);
  } finally {
    generating.value = false;
  }
}

async function refreshReviews(): Promise<void> {
  loadingReviews.value = true;
  try {
    reviews.value = await listMyNameReviews();
  } catch (error) {
    showError(error);
  } finally {
    loadingReviews.value = false;
  }
}

async function copyApprovedReview(review: NameReview): Promise<void> {
  if (!review.file_code) return;
  await copyAndClaim(review.file_code);
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
          <p>选择项目并输入文件名称。名称正常时直接生成编号，检测到明显问题时提交管理员审核。</p>
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
          ref="projectPicker"
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
            <van-tag
              v-if="selectedProject.special_numbering"
              color="#fff1e8"
              text-color="#a14922"
            >
              特殊编号项目
            </van-tag>
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
        <van-notice-bar
          v-if="selectedProject?.special_numbering"
          class="special-project-notice"
          color="#8a5a14"
          background="#fff8e8"
          text="该项目有其他编号要求。已有编号可正常领取；申请新编号时，请等待管理员人工编号。"
        />

        <div class="file-segment-form">
          <label class="file-segment-field">
            <span>
              产品/部组件
              <small>（如主控板、智能控制设备）</small>
            </span>
            <van-field
              v-model="productName"
              placeholder="请输入产品或部组件"
              maxlength="256"
              clearable
              @update:model-value="onFileSegmentChange"
              @keyup.enter="search"
            />
          </label>
          <label class="file-segment-field">
            <span>
              阶段
              <small>（如鉴定件、正样件，可不填）</small>
            </span>
            <van-field
              v-model="stageName"
              placeholder="请输入阶段"
              maxlength="64"
              clearable
              @update:model-value="onFileSegmentChange"
              @keyup.enter="search"
            />
          </label>
          <label class="file-segment-field">
            <span>
              文件类型
              <small>（如开发计划、方案设计报告）</small>
            </span>
            <van-field
              v-model="fileType"
              placeholder="请输入文件类型"
              maxlength="256"
              clearable
              @update:model-value="onFileSegmentChange"
              @keyup.enter="search"
            />
          </label>
        </div>
        <div v-if="mergedFileName" class="merged-file-name">
          <span>合并后文件名称</span>
          <strong>{{ mergedFileName }}</strong>
        </div>
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
          当前结果为库中的相近文件。可以直接领取已有编号；若都不是所需文件，请提交
          “{{ searchedFileName }}”进行名称检测。
        </div>
        <article v-for="item in results" :key="item.id" class="code-card">
          <div class="code-meta">
            <span>{{ item.standard_name }}</span>
            <small>{{ item.source === "admin_batch" ? "项目初始化" : "缺失补码" }}</small>
          </div>
          <code>{{ item.final_code }}</code>
          <div class="segment-row">
            <span v-if="item.segment_c">级别 {{ item.segment_c }}</span>
            <span v-if="item.segment_d">功能 {{ item.segment_d }}</span>
            <span v-if="item.segment_f">简号 {{ item.segment_f }}</span>
            <span v-if="item.segment_h">版本 {{ item.segment_h }}</span>
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
              {{
                selectedProject?.special_numbering
                  ? "提交管理员人工编号"
                  : "检测并生成新编号"
              }}
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
        <p v-if="selectedProject?.special_numbering">
          该项目有其他编号要求，提交后请等待管理员人工编号。
        </p>
        <p v-else>系统会校验内容并标准化查重；名称正常时直接生成，明显异常或相似名称会提交管理员审核。</p>
        <div class="submitted-name">{{ searchedFileName }}</div>
        <van-button
          block
          color="#b4532a"
          size="large"
          :loading="generating"
          loading-text="正在检测…"
          @click="generate"
        >
          {{
            selectedProject?.special_numbering
              ? "提交管理员人工编号"
              : "检测名称并生成编号"
          }}
        </van-button>
      </section>

      <section v-if="reviews.length" class="panel review-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">名称审核</p>
            <h2>我的申请</h2>
          </div>
          <van-button
            plain
            size="small"
            color="#17324d"
            :loading="loadingReviews"
            @click="refreshReviews"
          >
            刷新
          </van-button>
        </div>
        <article v-for="review in reviews" :key="review.id" class="review-row">
          <div>
            <strong>{{ review.reviewed_name ?? review.proposed_standard_name ?? review.original_name }}</strong>
            <span>{{ review.issue_summary }}</span>
            <small v-if="review.similar_names.length">
              相似名称：{{ review.similar_names.map((item) => item.standard_name).join("、") }}
            </small>
          </div>
          <van-tag
            :color="
              review.status === 'approved'
                ? '#e8f3ee'
                : review.status === 'rejected'
                  ? '#fff0ed'
                  : '#fff1e8'
            "
            :text-color="
              review.status === 'approved'
                ? '#176443'
                : review.status === 'rejected'
                  ? '#a13c2f'
                  : '#a14922'
            "
          >
            {{
              review.status === "approved"
                ? "审核通过"
                : review.status === "rejected"
                  ? "已驳回"
                  : "待管理员审核"
            }}
          </van-tag>
          <code v-if="review.file_code">{{ review.file_code.final_code }}</code>
          <van-button
            v-if="review.file_code"
            plain
            color="#176443"
            @click="copyApprovedReview(review)"
          >
            领取并复制
          </van-button>
        </article>
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
