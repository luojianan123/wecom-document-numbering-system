<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showConfirmDialog, showToast } from "vant";
import {
  addAdminManualProjectCode,
  addAdminProjectCode,
  ApiError,
  approveAdminNameReview,
  batchDeleteAdminProjectFiles,
  confirmProject,
  deleteAdminBatchItem,
  deleteAdminProject,
  deleteAdminProjectCode,
  exportAdminProjectCodes,
  getAdminProject,
  importProjectCodes,
  initializeProject,
  listAdminNameReviews,
  listProjects,
  manuallyNumberProjectBatchItem,
  rejectAdminNameReview,
  retryProjectCode,
  setProjectSpecialNumbering
} from "../api";
import AppHeader from "../components/AppHeader.vue";
import type {
  BatchItem,
  NameReview,
  Project,
  ProjectInitResult
} from "../types";

const projectName = ref("");
const projectCode = ref("");
const projectSpecialNumbering = ref(false);
const selectedFile = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const result = ref<ProjectInitResult | null>(null);
const projects = ref<Project[]>([]);
const projectNumberQuery = ref("");
const loading = ref(false);
const confirming = ref(false);
const retryingIndex = ref<number | null>(null);
const manualNames = ref<Record<number, string>>({});
const manualCodes = ref<Record<number, string>>({});
const savingManualIndex = ref<number | null>(null);
const openingProjectId = ref<number | null>(null);
const newFileName = ref("");
const addingCode = ref(false);
const importFileInput = ref<HTMLInputElement | null>(null);
const importingCodes = ref(false);
const manualCodeVisible = ref(false);
const manualFinalCode = ref("");
const addingManualCode = ref(false);
const deletingProject = ref(false);
const deletingFileCodeId = ref<number | null>(null);
const deletingBatchItemId = ref<number | null>(null);
const selectedItemKeys = ref<string[]>([]);
const deletingSelected = ref(false);
const exportingCodes = ref(false);
const nameReviews = ref<NameReview[]>([]);
const reviewNames = ref<Record<number, string>>({});
const reviewCodes = ref<Record<number, string>>({});
const loadingReviews = ref(false);
const processingReviewId = ref<number | null>(null);
const updatingSpecialNumbering = ref(false);

const filteredProjects = computed(() => {
  const query = projectNumberQuery.value.trim();
  if (!query) return projects.value;
  return projects.value.filter((project) =>
    project.project_code.includes(query)
  );
});

const pendingCount = computed(
  () =>
    result.value?.items.filter(
      (item) => item.success && item.file_code_id === null
    ).length ?? 0
);

const storedCount = computed(
  () =>
    result.value?.items.filter((item) => item.file_code_id !== null).length ?? 0
);

const duplicateCount = computed(
  () =>
    result.value?.items.filter(
      (item) => !item.success && item.error?.startsWith("已重复：")
    ).length ?? 0
);

const selectableKeys = computed(() =>
  (result.value?.items ?? [])
    .map(selectionKey)
    .filter((key): key is string => key !== null)
);

const allItemsSelected = computed(
  () =>
    selectableKeys.value.length > 0 &&
    selectableKeys.value.every((key) => selectedItemKeys.value.includes(key))
);

const selectionIndeterminate = computed(
  () =>
    selectedItemKeys.value.length > 0 &&
    !allItemsSelected.value
);

const canExport = computed(
  () =>
    result.value?.project.status === "active" &&
    storedCount.value > 0 &&
    pendingCount.value === 0 &&
    result.value.failure_count === 0
);

onMounted(async () => {
  await Promise.all([loadProjects(), loadNameReviews()]);
});

async function loadProjects(): Promise<void> {
  try {
    projects.value = await listProjects(true);
  } catch (error) {
    showError(error);
  }
}

async function loadNameReviews(): Promise<void> {
  loadingReviews.value = true;
  try {
    nameReviews.value = await listAdminNameReviews();
    reviewNames.value = Object.fromEntries(
      nameReviews.value.map((review) => [
        review.id,
        review.proposed_standard_name ?? review.original_name
      ])
    );
    reviewCodes.value = Object.fromEntries(
      nameReviews.value.map((review) => [
        review.id,
        review.file_code?.final_code ?? ""
      ])
    );
  } catch (error) {
    showError(error);
  } finally {
    loadingReviews.value = false;
  }
}

async function approveReview(review: NameReview): Promise<void> {
  const fileName = reviewNames.value[review.id]?.trim();
  if (!fileName) {
    showToast("请输入审核后的正确文件名称");
    return;
  }
  const finalCode = reviewCodes.value[review.id]?.trim();
  if (review.project.special_numbering && !finalCode) {
    showToast("特殊编号项目必须填写完整编号");
    return;
  }
  processingReviewId.value = review.id;
  try {
    await approveAdminNameReview(review.id, fileName, finalCode);
    await loadNameReviews();
    showToast("审核通过，正确文件名称已生成编号并提交给用户");
  } catch (error) {
    showError(error);
  } finally {
    processingReviewId.value = null;
  }
}

async function rejectReview(review: NameReview): Promise<void> {
  processingReviewId.value = review.id;
  try {
    await rejectAdminNameReview(review.id, "文件名称不符合项目文件命名要求");
    await loadNameReviews();
    showToast("已驳回该名称申请");
  } catch (error) {
    showError(error);
  } finally {
    processingReviewId.value = null;
  }
}

function showError(error: unknown): void {
  showToast(error instanceof ApiError ? error.message : "操作失败，请稍后重试");
}

function formatClaimTime(value: string): string {
  const hasTimeZone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
  const date = new Date(hasTimeZone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

function showResult(value: ProjectInitResult): void {
  result.value = value;
  selectedItemKeys.value = [];
  manualNames.value = Object.fromEntries(
    value.items.map((item, index) => [
      index,
      item.standard_name ?? item.original_name
    ])
  );
  manualCodes.value = Object.fromEntries(
    value.items.map((item, index) => [index, item.final_code ?? ""])
  );
}

function selectionKey(item: BatchItem): string | null {
  if (item.file_code_id !== null) return `file:${item.file_code_id}`;
  if (item.id !== null) return `batch:${item.id}`;
  return null;
}

function setItemSelected(item: BatchItem, checked: boolean): void {
  const key = selectionKey(item);
  if (!key) return;
  if (checked) {
    if (!selectedItemKeys.value.includes(key)) {
      selectedItemKeys.value = [...selectedItemKeys.value, key];
    }
    return;
  }
  selectedItemKeys.value = selectedItemKeys.value.filter(
    (selected) => selected !== key
  );
}

function isItemSelected(item: BatchItem): boolean {
  const key = selectionKey(item);
  return key !== null && selectedItemKeys.value.includes(key);
}

function setAllSelected(checked: boolean): void {
  selectedItemKeys.value = checked ? [...selectableKeys.value] : [];
}

function chooseFile(): void {
  fileInput.value?.click();
}

function onFileChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] ?? null;
}

async function initialize(): Promise<void> {
  if (!projectName.value.trim()) {
    showToast("请输入项目名称");
    return;
  }
  if (!/^\d{4}$/.test(projectCode.value)) {
    showToast("项目号必须为4位数字");
    return;
  }
  if (!selectedFile.value) {
    showToast("请选择 XLSX 或 CSV 清单");
    return;
  }
  loading.value = true;
  try {
    const initialized = await initializeProject(
      projectName.value.trim(),
      projectCode.value,
      projectSpecialNumbering.value,
      selectedFile.value
    );
    showResult(initialized);
    projectSpecialNumbering.value = false;
    await loadProjects();
    showToast("批量生成完成");
  } catch (error) {
    showError(error);
  } finally {
    loading.value = false;
  }
}

async function updateSpecialNumbering(value: boolean): Promise<void> {
  if (!result.value) return;
  updatingSpecialNumbering.value = true;
  try {
    const project = await setProjectSpecialNumbering(
      result.value.project.id,
      value
    );
    result.value.project = project;
    projects.value = projects.value.map((item) =>
      item.id === project.id ? project : item
    );
    showToast(value ? "已标记为特殊编号项目" : "已取消特殊编号标识");
  } catch (error) {
    showError(error);
  } finally {
    updatingSpecialNumbering.value = false;
  }
}

async function toggleSpecialNumbering(): Promise<void> {
  if (!result.value) return;
  const nextValue = !result.value.project.special_numbering;
  try {
    await showConfirmDialog({
      title: nextValue
        ? "标记为特殊编号项目"
        : "取消特殊编号项目",
      message: nextValue
        ? "标记后，用户申请新编号将转交管理员人工编号；管理员直接新增文件仍按正常规则生成编号。"
        : "取消后，用户申请新编号将恢复自动执行编号规则。",
      confirmButtonText: nextValue ? "确认标记" : "确认取消"
    });
  } catch {
    return;
  }
  await updateSpecialNumbering(nextValue);
}

async function openProject(project: Project): Promise<void> {
  openingProjectId.value = project.id;
  try {
    showResult(await getAdminProject(project.id));
    newFileName.value = "";
    manualFinalCode.value = "";
    manualCodeVisible.value = false;
  } catch (error) {
    showError(error);
  } finally {
    openingProjectId.value = null;
  }
}

async function reloadCurrentProject(): Promise<void> {
  if (!result.value) return;
  showResult(await getAdminProject(result.value.project.id));
}

async function addCode(): Promise<void> {
  if (!result.value) return;
  const fileName = newFileName.value.trim();
  if (!fileName) {
    showToast("请输入文件名称");
    return;
  }
  addingCode.value = true;
  try {
    const item = await addAdminProjectCode(result.value.project.id, fileName);
    newFileName.value = "";
    await reloadCurrentProject();
    showToast(
      item.error?.startsWith("已重复：")
        ? "该文件已重复"
        : item.success
          ? "已生成待确认预览，确认后写入编码库"
          : item.error ?? "文件编号生成失败"
    );
  } catch (error) {
    showError(error);
    manualCodeVisible.value = true;
  } finally {
    addingCode.value = false;
  }
}

function chooseImportFile(): void {
  importFileInput.value?.click();
}

async function importCodes(event: Event): Promise<void> {
  if (!result.value) return;
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  target.value = "";
  if (!file) return;

  importingCodes.value = true;
  try {
    showResult(await importProjectCodes(result.value.project.id, file));
    const messageParts = [
      pendingCount.value ? `待确认 ${pendingCount.value} 条` : "",
      duplicateCount.value ? `已重复 ${duplicateCount.value} 条` : ""
    ].filter(Boolean);
    showToast(messageParts.join("，") || "表格处理完成");
  } catch (error) {
    showError(error);
  } finally {
    importingCodes.value = false;
  }
}

async function addManualCode(): Promise<void> {
  if (!result.value) return;
  const fileName = newFileName.value.trim();
  const finalCode = manualFinalCode.value.trim();
  if (!fileName) {
    showToast("请输入文件名称");
    return;
  }
  if (!finalCode) {
    showToast("请输入完整编号");
    return;
  }

  addingManualCode.value = true;
  try {
    await addAdminManualProjectCode(
      result.value.project.id,
      fileName,
      finalCode
    );
    newFileName.value = "";
    manualFinalCode.value = "";
    manualCodeVisible.value = false;
    await reloadCurrentProject();
    showToast("手工编号已加入待确认列表");
  } catch (error) {
    showError(error);
  } finally {
    addingManualCode.value = false;
  }
}

async function removeItem(item: BatchItem): Promise<void> {
  if (
    !result.value ||
    (item.file_code_id === null && item.id === null)
  ) {
    return;
  }
  const isStored = item.file_code_id !== null;
  try {
    await showConfirmDialog({
      title: isStored ? "删除文件及编码" : "移除待确认文件",
      message: isStored
        ? `确定删除“${item.standard_name}”及编码 ${item.final_code} 吗？`
        : `确定从待确认列表移除“${item.standard_name ?? item.original_name}”吗？`,
      confirmButtonText: "删除"
    });
  } catch {
    return;
  }

  if (isStored) {
    deletingFileCodeId.value = item.file_code_id;
  } else {
    deletingBatchItemId.value = item.id;
  }
  try {
    if (item.file_code_id !== null) {
      await deleteAdminProjectCode(
        result.value.project.id,
        item.file_code_id
      );
    } else if (item.id !== null) {
      await deleteAdminBatchItem(result.value.project.id, item.id);
    }
    await reloadCurrentProject();
    showToast(isStored ? "文件及编码已删除" : "待确认文件已移除");
  } catch (error) {
    showError(error);
  } finally {
    deletingFileCodeId.value = null;
    deletingBatchItemId.value = null;
  }
}

async function removeSelectedItems(): Promise<void> {
  if (!result.value || !selectedItemKeys.value.length) {
    showToast("请先选择需要删除的文件");
    return;
  }
  const selectedItems = result.value.items.filter((item) => {
    const key = selectionKey(item);
    return key !== null && selectedItemKeys.value.includes(key);
  });
  const storedItems = selectedItems.filter(
    (item) => item.file_code_id !== null
  );
  try {
    await showConfirmDialog({
      title: `批量删除 ${selectedItems.length} 个文件`,
      message: storedItems.length
        ? `其中 ${storedItems.length} 个文件已入库，相关编码及领取记录也会删除。确定继续吗？`
        : "所选待确认、失败或重复记录将被删除，确定继续吗？",
      confirmButtonText: "批量删除"
    });
  } catch {
    return;
  }

  const fileCodeIds = selectedItems
    .map((item) => item.file_code_id)
    .filter((id): id is number => id !== null);
  const batchItemIds = selectedItems
    .filter((item) => item.file_code_id === null)
    .map((item) => item.id)
    .filter((id): id is number => id !== null);

  deletingSelected.value = true;
  try {
    await batchDeleteAdminProjectFiles(
      result.value.project.id,
      fileCodeIds,
      batchItemIds
    );
    selectedItemKeys.value = [];
    await reloadCurrentProject();
    showToast(`已删除 ${selectedItems.length} 个文件`);
  } catch (error) {
    showError(error);
  } finally {
    deletingSelected.value = false;
  }
}

async function removeProject(): Promise<void> {
  if (!result.value) return;
  const project = result.value.project;
  try {
    await showConfirmDialog({
      title: "删除整个项目",
      message:
        `确定删除 ${project.project_code} · ${project.project_name} 吗？` +
        "项目下全部文件、编码及领取记录将同时删除；若正在生成，也会立即终止。",
      confirmButtonText: "删除项目"
    });
  } catch {
    return;
  }

  deletingProject.value = true;
  try {
    await deleteAdminProject(project.id);
    result.value = null;
    newFileName.value = "";
    manualFinalCode.value = "";
    manualCodeVisible.value = false;
    manualNames.value = {};
    manualCodes.value = {};
    await loadProjects();
    showToast("项目及其全部文件和编码已删除");
  } catch (error) {
    showError(error);
  } finally {
    deletingProject.value = false;
  }
}

async function exportCodes(): Promise<void> {
  if (!result.value || !canExport.value) {
    showToast("请先处理全部待确认、失败或已重复文件");
    return;
  }
  exportingCodes.value = true;
  try {
    const blob = await exportAdminProjectCodes(result.value.project.id);
    const safeProjectName = result.value.project.project_name.replace(
      /[\\/:*?"<>|]/g,
      "_"
    );
    const filename =
      `${result.value.project.project_code}-` +
      `${safeProjectName}-文件编码.xlsx`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showToast("文件编码表已导出");
  } catch (error) {
    showError(error);
  } finally {
    exportingCodes.value = false;
  }
}

async function retryItem(index: number): Promise<void> {
  if (!result.value) return;
  const item = result.value.items[index];
  if (item.id === null) {
    showToast("该记录不是可修正的批量失败项");
    return;
  }
  const fileName = manualNames.value[index]?.trim();
  if (!fileName) {
    showToast("请输入修正后的文件名称");
    return;
  }
  retryingIndex.value = index;
  try {
    const previous = item;
    const updated = await retryProjectCode(
      result.value.project.id,
      item.id,
      fileName
    );
    result.value.items[index] = updated;
    if (!previous.success && updated.success) {
      result.value.success_count += 1;
      result.value.failure_count -= 1;
      showToast("修正成功，已重新生成编码");
    } else if (updated.success) {
      showToast("编码已重新生成");
    } else {
      showToast(updated.error ?? "修正后仍无法生成编码");
    }
  } catch (error) {
    showError(error);
  } finally {
    retryingIndex.value = null;
  }
}

function isDuplicate(item: BatchItem): boolean {
  return !item.success && Boolean(item.error?.startsWith("已重复："));
}

async function saveManualItem(index: number): Promise<void> {
  if (!result.value) return;
  const item = result.value.items[index];
  if (
    item.id === null ||
    item.file_code_id !== null ||
    !["draft", "active"].includes(result.value.project.status)
  ) {
    showToast("该记录不能修改");
    return;
  }
  const fileName = manualNames.value[index]?.trim();
  const finalCode = manualCodes.value[index]?.trim();
  if (!fileName) {
    showToast("请输入修正后文件名");
    return;
  }
  if (!finalCode) {
    showToast("请输入生成编码");
    return;
  }

  const wasSuccessful = item.success;
  savingManualIndex.value = index;
  try {
    const updated = await manuallyNumberProjectBatchItem(
      result.value.project.id,
      item.id,
      fileName,
      finalCode
    );
    result.value.items[index] = updated;
    manualNames.value[index] = updated.standard_name ?? fileName;
    manualCodes.value[index] = updated.final_code ?? finalCode;
    if (!wasSuccessful) {
      result.value.success_count += 1;
      result.value.failure_count -= 1;
    }
    showToast(
      wasSuccessful
        ? "修正后文件名和编码已保存"
        : "人工编号已加入待确认列表"
    );
  } catch (error) {
    showError(error);
  } finally {
    savingManualIndex.value = null;
  }
}

async function confirm(): Promise<void> {
  if (!result.value) return;
  confirming.value = true;
  try {
    const project = await confirmProject(result.value.project.id);
    result.value.project = project;
    await reloadCurrentProject();
    await loadProjects();
    showToast("成功项已写入编码库并可领取");
  } catch (error) {
    showError(error);
  } finally {
    confirming.value = false;
  }
}
</script>

<template>
  <main class="app-page admin-page">
    <div class="page-wrap wide">
      <AppHeader eyebrow="管理员界面" title="项目初始化" />

      <section class="hero-strip admin-hero">
        <div>
          <span class="step-label">01</span>
          <h2>上传一份清单，批量建立项目编码</h2>
          <p>清单只需“文件名称”列，文件名称前不要填写项目号。</p>
        </div>
        <div class="hero-rule">XLSX / CSV</div>
      </section>

      <section class="panel name-review-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">用户名称申请</p>
            <h2>待审核名称</h2>
          </div>
          <van-button
            plain
            size="small"
            color="#17324d"
            :loading="loadingReviews"
            @click="loadNameReviews"
          >
            刷新
          </van-button>
        </div>
        <div v-if="nameReviews.length" class="name-review-list">
          <article
            v-for="review in nameReviews"
            :key="review.id"
            :class="[
              'name-review-item',
              { 'special-review-item': review.project.special_numbering }
            ]"
          >
            <div class="name-review-copy">
              <strong>
                {{ review.project.project_code }} · {{ review.original_name }}
              </strong>
              <van-tag
                v-if="review.project.special_numbering"
                color="#fff1e8"
                text-color="#a14922"
              >
                特殊编号
              </van-tag>
              <span>{{ review.issue_summary }}</span>
              <small v-if="review.similar_names.length">
                相似名称：{{ review.similar_names.map((item) => item.standard_name).join("、") }}
              </small>
            </div>
            <van-field
              v-model="reviewNames[review.id]"
              label="正确名称"
              placeholder="管理员修改后的正确文件名称"
              maxlength="512"
              clearable
            />
            <van-field
              v-if="review.project.special_numbering"
              v-model="reviewCodes[review.id]"
              label="完整编号"
              placeholder="管理员填写完整编号"
              maxlength="64"
              clearable
            />
            <div class="name-review-actions">
              <van-button
                plain
                type="danger"
                :loading="processingReviewId === review.id"
                @click="rejectReview(review)"
              >
                驳回
              </van-button>
              <van-button
                color="#176443"
                :loading="processingReviewId === review.id"
                @click="approveReview(review)"
              >
                {{
                  review.project.special_numbering
                    ? "人工编号并提交"
                    : "通过并生成编号"
                }}
              </van-button>
            </div>
          </article>
        </div>
        <van-empty
          v-else
          image="search"
          description="暂无待审核文件名称"
        />
      </section>

      <div class="admin-grid">
        <section class="panel init-form">
          <div class="section-heading">
            <div>
              <p class="eyebrow">项目信息</p>
              <h2>新项目初始化</h2>
            </div>
          </div>
          <van-cell-group inset>
            <van-field
              v-model="projectName"
              label="项目名称"
              placeholder="输入新项目名称"
              maxlength="128"
            />
            <van-field
              v-model="projectCode"
              label="项目号"
              placeholder="4位项目号，单独填写"
              maxlength="4"
              inputmode="numeric"
            />
          </van-cell-group>

          <label
            :class="[
              'special-numbering-choice',
              { selected: projectSpecialNumbering }
            ]"
          >
            <van-checkbox
              v-model="projectSpecialNumbering"
              shape="square"
              checked-color="#b4532a"
            />
            <span>
              <strong>标记为特殊编号项目</strong>
              <small>
                用户申请新编号时转管理员人工编号，管理员初始化仍按正常规则运行。
              </small>
            </span>
          </label>

          <div class="upload-box" role="button" tabindex="0" @click="chooseFile">
            <input
              ref="fileInput"
              class="visually-hidden"
              type="file"
              accept=".xlsx,.csv"
              @change="onFileChange"
            />
            <div class="upload-icon">↑</div>
            <strong>{{ selectedFile?.name ?? "选择文件名称清单" }}</strong>
            <span>支持 XLSX 或 CSV，第一行必须包含“文件名称”</span>
          </div>
          <van-button
            block
            color="#17324d"
            size="large"
            :loading="loading"
            loading-text="正在批量生成…"
            @click="initialize"
          >
            批量生成编码
          </van-button>
        </section>

        <aside class="panel project-list">
          <div class="section-heading">
            <div>
              <p class="eyebrow">项目状态</p>
              <h2>已有项目</h2>
            </div>
          </div>
          <van-field
            v-model="projectNumberQuery"
            class="project-search"
            placeholder="输入项目号模糊搜索"
            inputmode="numeric"
            maxlength="4"
            clearable
          />
          <div class="project-list-scroll">
            <div v-if="filteredProjects.length" class="project-stack">
              <button
                v-for="project in filteredProjects"
                :key="project.id"
                type="button"
                :class="[
                  'project-row',
                  { selected: result?.project.id === project.id }
                ]"
                :disabled="openingProjectId === project.id"
                @click="openProject(project)"
              >
                <div>
                  <strong>
                    {{ project.project_code }}
                    <van-tag
                      v-if="project.special_numbering"
                      color="#fff1e8"
                      text-color="#a14922"
                    >
                      特殊
                    </van-tag>
                  </strong>
                  <span>{{ project.project_name }}</span>
                </div>
                <div class="project-row-action">
                  <van-tag
                    :color="
                      project.status === 'active'
                        ? '#e8f3ee'
                        : project.status === 'failed'
                          ? '#fff0ed'
                        : project.status === 'initializing'
                          ? '#edf2f7'
                          : '#fff1e8'
                    "
                    :text-color="
                      project.status === 'active'
                        ? '#176443'
                        : project.status === 'failed'
                          ? '#a13c2f'
                        : project.status === 'initializing'
                          ? '#526579'
                          : '#a14922'
                    "
                  >
                    {{
                      project.status === "active"
                        ? "已启用"
                        : project.status === "failed"
                          ? "初始化失败"
                        : project.status === "initializing"
                          ? "生成中"
                          : "待确认"
                    }}
                  </van-tag>
                  <small>
                    {{ openingProjectId === project.id ? "加载中" : "查看" }}
                  </small>
                </div>
              </button>
            </div>
            <van-empty
              v-else
              image="search"
              :description="projects.length ? '未找到匹配项目' : '暂无项目'"
            />
          </div>
        </aside>
      </div>

      <section v-if="result" class="results-section batch-results" aria-live="polite">
        <div class="section-heading">
          <div>
            <p class="eyebrow">项目文件及编码</p>
            <h2>{{ result.project.project_code }} · {{ result.project.project_name }}</h2>
          </div>
          <div class="project-heading-actions">
            <div class="summary-tags">
              <van-tag
                v-if="result.project.special_numbering"
                color="#fff1e8"
                text-color="#a14922"
              >
                特殊编号项目
              </van-tag>
              <van-tag color="#e8f3ee" text-color="#176443">
                已入库 {{ storedCount }}
              </van-tag>
              <van-tag
                v-if="pendingCount"
                color="#fff1e8"
                text-color="#a14922"
              >
                待确认 {{ pendingCount }}
              </van-tag>
              <van-tag
                v-if="duplicateCount"
                color="#fff4dc"
                text-color="#8a5a14"
              >
                已重复 {{ duplicateCount }}
              </van-tag>
              <van-tag
                v-if="result.failure_count - duplicateCount"
                color="#fff0ed"
                text-color="#a13c2f"
              >
                失败 {{ result.failure_count - duplicateCount }}
              </van-tag>
            </div>
            <van-button
              :plain="!result.project.special_numbering"
              :color="
                result.project.special_numbering ? '#b4532a' : '#7b4a2f'
              "
              size="small"
              :loading="updatingSpecialNumbering"
              @click="toggleSpecialNumbering"
            >
              {{
                result.project.special_numbering
                  ? "取消特殊编号项目"
                  : "标记为特殊编号项目"
              }}
            </van-button>
            <van-button
              plain
              color="#176443"
              size="small"
              :disabled="!canExport"
              :loading="exportingCodes"
              @click="exportCodes"
            >
              导出 Excel
            </van-button>
            <van-button
              plain
              type="danger"
              size="small"
              :loading="deletingProject"
              @click="removeProject"
            >
              删除项目
            </van-button>
          </div>
        </div>

        <div class="admin-add-code">
          <div>
            <strong>新增文件并生成编码</strong>
            <span>
              使用与用户补码相同的 AI 修正及编码规则；待确认项目仅生成预览。
            </span>
            <van-button
              plain
              size="small"
              color="#7b4a2f"
              @click="manualCodeVisible = !manualCodeVisible"
            >
              {{ manualCodeVisible ? "收起手工补码" : "AI 无法匹配？手工补码" }}
            </van-button>
          </div>
          <div class="admin-add-code-form">
            <van-field
              v-model="newFileName"
              placeholder="输入文件名称，不含项目号"
              maxlength="512"
              clearable
              @keyup.enter="addCode"
            />
            <van-button
              color="#17324d"
              :disabled="!['draft', 'active'].includes(result.project.status)"
              :loading="addingCode"
              loading-text="AI 处理中…"
              @click="addCode"
            >
              按规则生成编码
            </van-button>
            <input
              ref="importFileInput"
              class="visually-hidden"
              type="file"
              accept=".xlsx,.csv"
              @change="importCodes"
            />
            <van-button
              plain
              color="#176443"
              :disabled="!['draft', 'active'].includes(result.project.status)"
              :loading="importingCodes"
              loading-text="正在导入…"
              @click="chooseImportFile"
            >
              上传表格批量新增
            </van-button>
          </div>
          <div v-if="manualCodeVisible" class="manual-code-form">
            <div>
              <strong>手工填写完整编号</strong>
              <span>
                系统仍会校验项目号、固定段、级别、阶段版本、特殊前缀及全局唯一性。
              </span>
            </div>
            <van-field
              v-model="manualFinalCode"
              label="完整编号"
              placeholder="例如 P-GH1234-3KZ-010JY-1.00"
              maxlength="64"
              clearable
              @keyup.enter="addManualCode"
            />
            <van-button
              color="#7b4a2f"
              :disabled="!['draft', 'active'].includes(result.project.status)"
              :loading="addingManualCode"
              loading-text="正在校验…"
              @click="addManualCode"
            >
              手工补码
            </van-button>
          </div>
        </div>

        <div class="batch-selection-bar">
          <van-checkbox
            :model-value="allItemsSelected"
            :indeterminate="selectionIndeterminate"
            shape="square"
            @update:model-value="setAllSelected"
          >
            全选
          </van-checkbox>
          <span>已选择 {{ selectedItemKeys.length }} 项</span>
          <van-button
            size="small"
            plain
            type="danger"
            :disabled="!selectedItemKeys.length"
            :loading="deletingSelected"
            @click="removeSelectedItems"
          >
            批量删除
          </van-button>
        </div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th class="selection-column">
                  <van-checkbox
                    :model-value="allItemsSelected"
                    :indeterminate="selectionIndeterminate"
                    shape="square"
                    aria-label="全选文件"
                    @update:model-value="setAllSelected"
                  />
                </th>
                <th>原文件名</th>
                <th>修正后文件名</th>
                <th>生成编码</th>
                <th>状态</th>
                <th>领取记录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, index) in result.items"
                :key="item.file_code_id ?? item.id ?? `${index}-${item.original_name}`"
              >
                <td class="selection-column">
                  <van-checkbox
                    :model-value="isItemSelected(item)"
                    shape="square"
                    aria-label="选择文件"
                    @update:model-value="
                      (checked: boolean) => setItemSelected(item, checked)
                    "
                  />
                </td>
                <td>{{ item.original_name }}</td>
                <td>
                  <van-field
                    v-if="
                      ['draft', 'active'].includes(result.project.status) &&
                      item.id !== null &&
                      item.file_code_id === null
                    "
                    v-model="manualNames[index]"
                    class="inline-correction"
                    placeholder="修正后文件名"
                    maxlength="512"
                    clearable
                  />
                  <span v-else>{{ item.standard_name ?? item.original_name }}</span>
                </td>
                <td>
                  <div
                    v-if="
                      ['draft', 'active'].includes(result.project.status) &&
                      item.id !== null &&
                      item.file_code_id === null
                    "
                    class="inline-code-editor"
                  >
                    <van-field
                      v-model="manualCodes[index]"
                      class="inline-code-field"
                      placeholder="输入完整编号"
                      maxlength="64"
                      clearable
                    />
                    <small v-if="!item.success && item.error">
                      {{ item.error }}
                    </small>
                  </div>
                  <code v-else>{{ item.final_code ?? item.error }}</code>
                </td>
                <td>
                  <span
                    :class="[
                      'status-dot',
                      item.success ? 'ok' : isDuplicate(item) ? 'duplicate' : 'error'
                    ]"
                  >
                    {{
                      item.success
                        ? (item.file_code_id === null ? "待确认" : "已入库")
                        : isDuplicate(item)
                          ? "已重复"
                          : "失败"
                    }}
                  </span>
                </td>
                <td class="claim-history-cell">
                  <div v-if="item.claims.length" class="claim-history">
                    <span v-for="claim in item.claims" :key="claim.id">
                      <strong>{{ claim.claimant_name }}</strong>
                      <small>{{ formatClaimTime(claim.claimed_at) }}</small>
                    </span>
                  </div>
                  <span v-else class="claim-history-empty">尚未领取</span>
                </td>
                <td class="row-actions">
                  <van-button
                    v-if="
                      !item.success &&
                      ['draft', 'active'].includes(result.project.status)
                    "
                    class="retry-button"
                    size="small"
                    plain
                    color="#b4532a"
                    :loading="retryingIndex === index"
                    @click="retryItem(index)"
                  >
                    修正并重试
                  </van-button>
                  <van-button
                    v-if="
                      item.id !== null &&
                      item.file_code_id === null &&
                      ['draft', 'active'].includes(result.project.status)
                    "
                    class="manual-row-button"
                    size="small"
                    plain
                    color="#17324d"
                    :loading="savingManualIndex === index"
                    @click="saveManualItem(index)"
                  >
                    {{ item.success ? "保存修改" : "人工生成编号" }}
                  </van-button>
                  <van-button
                    v-if="
                      item.file_code_id !== null ||
                      (item.id !== null &&
                        ['draft', 'active'].includes(result.project.status))
                    "
                    class="delete-code-button"
                    size="small"
                    plain
                    type="danger"
                    :loading="
                      (item.file_code_id !== null &&
                        deletingFileCodeId === item.file_code_id) ||
                      (item.file_code_id === null &&
                        item.id !== null &&
                        deletingBatchItemId === item.id)
                    "
                    @click="removeItem(item)"
                  >
                    删除
                  </van-button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <van-notice-bar
          v-if="result.failure_count - duplicateCount"
          color="#8a3b24"
          background="#fff5ef"
          text="失败项不会启用，请根据失败原因修正文件名称后重新处理。"
        />
        <van-notice-bar
          v-if="pendingCount"
          color="#176443"
          background="#eef7f2"
          text="当前成功项仅为待确认预览，尚未写入正式编码库。"
        />
        <van-button
          block
          color="#176443"
          size="large"
          :disabled="
            !['draft', 'active'].includes(result.project.status) || !pendingCount
          "
          :loading="confirming"
          @click="confirm"
        >
          {{
            result.project.status === "failed"
                ? "初始化失败，请删除后重建"
              : result.project.status === "initializing"
                ? "批量生成中"
                : "确认待确认项并写入编码库"
          }}
        </van-button>
      </section>

    </div>
  </main>
</template>
