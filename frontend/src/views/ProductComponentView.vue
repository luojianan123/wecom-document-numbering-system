<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { showConfirmDialog, showToast } from "vant";
import {
  ApiError, claimComponentNode, deleteComponentNodes, exportComponentProject,
  generateComponentTree, getComponentProject, renumberComponentProject,
  updateComponentNode
} from "../api";
import AppHeader from "../components/AppHeader.vue";
import type { ComponentDraftNode, ComponentKind, ComponentNode, ComponentProject } from "../types";

type WorkNode = {
  key: string; parentKey: string | null; kind: ComponentKind; name: string;
  stage: "C" | "M" | "Z" | "G"; depth: number; saved: boolean; node?: ComponentNode;
  draft?: ComponentDraftNode;
};

const projectCode = ref("");
const project = ref<ComponentProject | null>(null);
const searched = ref(false);
const loading = ref(false);
const saving = ref(false);
const drafts = ref<ComponentDraftNode[]>([]);
const selectedKey = ref<string | null>(null);
const editingSaved = ref(false);
const needsRenumber = ref(false);
const editName = ref("");
const editCode = ref("");
let draftCounter = 0;

const labels: Record<ComponentKind, string> = {
  machine: "整机", component: "部组件", structure: "结构", hardware: "硬件",
  software: "软件/逻辑", other: "其他", part: "零件"
};
const kindOrder: Record<ComponentKind, number> = {
  machine: 0, component: 1, structure: 2, hardware: 3, software: 4, other: 5, part: 6
};
const stageOptions = [
  { value: "C", label: "初样件/电性件" },
  { value: "M", label: "模样件" },
  { value: "Z", label: "正样件" },
  { value: "G", label: "其他" }
] as const;
function savedKey(id: number): string { return `saved-${id}`; }
function draftKey(id: string): string { return `draft-${id}`; }
function errorMessage(error: unknown): void {
  showToast(error instanceof ApiError ? error.message : "操作失败，请稍后重试");
}
function stageLabel(stage: "C" | "M" | "Z" | "G"): string {
  return stageOptions.find((option) => option.value === stage)?.label ?? stage;
}

const allNodes = computed<WorkNode[]>(() => {
  const flat: Array<Omit<WorkNode, "depth">> = [];
  for (const node of project.value?.nodes ?? []) {
    flat.push({ key: savedKey(node.id), parentKey: node.parent_id ? savedKey(node.parent_id) : null,
      kind: node.kind, name: node.name, stage: node.stage, saved: true, node });
  }
  for (const draft of drafts.value) {
    flat.push({ key: draftKey(draft.client_id),
      parentKey: draft.parent_id ? savedKey(draft.parent_id) : draft.parent_client_id ? draftKey(draft.parent_client_id) : null,
      kind: draft.kind, name: draft.name, stage: draft.stage, saved: false, draft });
  }
  const children = new Map<string | null, Array<Omit<WorkNode, "depth">>>();
  for (const node of flat) children.set(node.parentKey, [...(children.get(node.parentKey) ?? []), node]);
  const result: WorkNode[] = [];
  function append(parentKey: string | null, depth: number): void {
    const group = children.get(parentKey) ?? [];
    group.sort((a, b) => kindOrder[a.kind] - kindOrder[b.kind]);
    for (const node of group) { result.push({ ...node, depth }); append(node.key, depth + 1); }
  }
  append(null, 0);
  return result;
});
const selected = computed(() => allNodes.value.find((node) => node.key === selectedKey.value) ?? null);
const childKinds = computed<ComponentKind[]>(() => {
  if (!selected.value) return [];
  if (selected.value.kind === "machine") return ["component"];
  if (selected.value.kind === "component") return ["structure", "hardware", "software", "other"];
  if (["structure", "hardware"].includes(selected.value.kind)) return ["part"];
  return [];
});
const completedDrafts = computed(() => drafts.value.filter((draft) => draft.name.trim()).length);
const emptyDrafts = computed(() => drafts.value.length - completedDrafts.value);

function makeDraft(kind: ComponentKind, parent: WorkNode | null): ComponentDraftNode {
  draftCounter += 1;
  return { client_id: `${Date.now()}-${draftCounter}`, parent_id: parent?.node?.id ?? null,
    parent_client_id: parent?.draft?.client_id ?? null, kind, name: "", stage: "G" };
}
async function addDraft(kind: ComponentKind, parent: WorkNode | null = selected.value): Promise<void> {
  if (kind === "software") { showToast(`${labels[kind]}编号规则尚未配置`); return; }
  const draft = makeDraft(kind, parent); drafts.value.push(draft);
  selectedKey.value = draftKey(draft.client_id); editingSaved.value = false;
  await nextTick();
  document.querySelector<HTMLInputElement>(".component-editor-name input")?.focus();
}
async function searchProject(): Promise<void> {
  const code = projectCode.value.trim();
  if (!/^\d{4}$/.test(code)) { showToast("请输入4位项目号"); return; }
  loading.value = true; searched.value = true; project.value = null; drafts.value = []; selectedKey.value = null; needsRenumber.value = false;
  try {
    project.value = await getComponentProject(code);
    const first = project.value.nodes.find((node) => node.kind === "machine");
    selectedKey.value = first ? savedKey(first.id) : null;
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) errorMessage(error);
    else await addDraft("machine", null);
  } finally { loading.value = false; }
}
function selectNode(node: WorkNode): void { selectedKey.value = node.key; editingSaved.value = false; }
function removeDraft(root: ComponentDraftNode): void {
  const ids = new Set([root.client_id]); let changed = true;
  while (changed) { changed = false; for (const draft of drafts.value) {
    if (draft.parent_client_id && ids.has(draft.parent_client_id) && !ids.has(draft.client_id)) {
      ids.add(draft.client_id); changed = true;
    }
  } }
  drafts.value = drafts.value.filter((draft) => !ids.has(draft.client_id));
  selectedKey.value = allNodes.value[0]?.key ?? null;
}
async function generateAll(): Promise<void> {
  if (!drafts.value.length && !needsRenumber.value) { showToast("当前没有待生成的内容"); return; }
  if (emptyDrafts.value) { showToast("请先填写所有草稿名称"); return; }
  saving.value = true;
  try {
    if (drafts.value.length) {
      project.value = await generateComponentTree(projectCode.value.trim(), drafts.value);
    }
    if (needsRenumber.value && project.value) {
      project.value = await renumberComponentProject(project.value.id);
    }
    if (!project.value) return;
    drafts.value = []; selectedKey.value = project.value.nodes.length ? savedKey(project.value.nodes.at(-1)!.id) : null;
    needsRenumber.value = false;
    showToast("全部编号已重新生成");
  } catch (error) { errorMessage(error); } finally { saving.value = false; }
}
function beginSavedEdit(node: ComponentNode): void {
  editName.value = node.name; editCode.value = node.code; editingSaved.value = true;
}
async function saveSavedEdit(node: ComponentNode): Promise<void> {
  if (!project.value || !editName.value.trim() || !editCode.value.trim()) return;
  saving.value = true;
  try {
    const updated = await updateComponentNode(project.value.id, node.id, editName.value.trim(), editCode.value.trim());
    project.value.nodes[project.value.nodes.findIndex((item) => item.id === node.id)] = updated;
    editingSaved.value = false; showToast("修改已保存");
  } catch (error) { errorMessage(error); } finally { saving.value = false; }
}
async function removeSaved(node: ComponentNode): Promise<void> {
  if (!project.value) return;
  try { await showConfirmDialog({ title: "删除产品组成", message: "该项的全部下级和领取记录也会删除。删除后请点击“统一生成全部编号”刷新受影响的编号。确定继续吗？", confirmButtonText: "删除" }); }
  catch { return; }
  saving.value = true;
  try {
    await deleteComponentNodes(project.value.id, [node.id]);
    project.value = await getComponentProject(project.value.project_code);
    selectedKey.value = allNodes.value[0]?.key ?? null;
    needsRenumber.value = project.value.nodes.length > 0;
    showToast(needsRenumber.value ? "已删除，请点击统一生成全部编号" : "已删除");
  } catch (error) { errorMessage(error); } finally { saving.value = false; }
}
function removeTreeNode(node: WorkNode): void {
  if (node.draft) removeDraft(node.draft);
  else if (node.node) void removeSaved(node.node);
}
async function claim(node: ComponentNode): Promise<void> {
  try { const record = await claimComponentNode(node.id); node.claims.unshift(record);
    await navigator.clipboard.writeText(node.code); showToast("编号已领取并复制"); }
  catch (error) { errorMessage(error); }
}
async function exportExcel(): Promise<void> {
  if (!project.value) return;
  try {
    const blob = await exportComponentProject(project.value.id);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `GH${project.value.project_code}-产品组件编码.xlsx`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) { errorMessage(error); }
}
function resetSearch(): void { searched.value = false; project.value = null; drafts.value = []; selectedKey.value = null; needsRenumber.value = false; }
</script>

<template>
  <main class="app-page"><div class="page-wrap wide component-code-page">
    <AppHeader eyebrow="产品组件编码" title="产品组件层级编制" />
    <section v-if="!searched" class="panel component-project-search">
      <div class="section-heading"><div><p class="eyebrow">开始编制</p><h2>输入4位项目号</h2></div></div>
      <div class="component-search-row"><van-field v-model="projectCode" placeholder="例如：2468" maxlength="4" />
        <van-button color="#17324d" :loading="loading" @click="searchProject">进入项目</van-button></div>
    </section>
    <template v-else>
      <section class="component-workbar">
        <div><button type="button" class="component-back-button" title="更换项目" @click="resetSearch">‹</button>
          <strong>{{ projectCode }}</strong><span>{{ project ? "已有编码" : "新项目" }}</span></div>
        <div class="component-workbar-actions">
          <button type="button" :disabled="!project?.nodes.length" @click="exportExcel">导出 Excel 表</button>
          <button type="button" @click="addDraft('machine', null)">增加整机</button>
        </div>
      </section>
      <section class="component-workspace">
        <aside class="component-tree-pane">
          <header><div><p class="eyebrow">层级树</p><h2>产品组成</h2></div><span>{{ allNodes.length }} 项</span></header>
          <div class="component-tree-scroll">
            <div v-for="node in allNodes" :key="node.key"
              :class="['component-tree-row', { active: selectedKey === node.key, draft: !node.saved }]"
              :style="{ '--tree-depth': node.depth }">
              <button type="button" class="component-tree-node" @click="selectNode(node)">
                <span class="component-tree-branch"></span><span class="component-kind-mark">{{ labels[node.kind].slice(0, 1) }}</span>
                <span class="component-tree-copy"><strong>{{ node.name || `未命名${labels[node.kind]}` }}</strong>
                  <small>{{ labels[node.kind] }} · {{ node.saved ? node.node?.code : "待生成" }}</small></span>
              </button>
              <button type="button" class="component-tree-delete" :aria-label="`删除${node.name || labels[node.kind]}`"
                title="删除" :disabled="saving" @click="removeTreeNode(node)">删除</button>
            </div>
          </div>
        </aside>
        <section class="component-editor-pane">
          <template v-if="selected">
            <header><div><p class="eyebrow">当前节点</p><h2>{{ labels[selected.kind] }}</h2></div>
              <span :class="['component-node-state', { draft: !selected.saved }]">{{ selected.saved ? "已生成" : "草稿" }}</span></header>
            <div v-if="selected.draft" class="component-editor-form">
              <label>名称</label><van-field v-model="selected.draft.name" class="component-editor-name" :placeholder="`请输入${labels[selected.kind]}名称`" maxlength="256" />
              <label>研制阶段</label><van-radio-group v-model="selected.draft.stage" direction="horizontal">
                <label v-for="option in stageOptions" :key="option.value" class="component-stage-check">
                  <input v-model="selected.draft.stage" type="radio" name="component-stage" :value="option.value" />
                  <span>{{ option.label }}（{{ option.value }}）</span>
                </label>
              </van-radio-group>
            </div>
            <div v-else-if="selected.node" class="component-saved-detail">
              <template v-if="editingSaved">
                <label>名称</label><van-field v-model="editName" /><label>编号</label><van-field v-model="editCode" />
                <div><van-button size="small" color="#176443" :loading="saving" @click="saveSavedEdit(selected.node)">保存</van-button>
                  <van-button size="small" plain @click="editingSaved = false">取消</van-button></div>
              </template>
              <template v-else>
                <strong>{{ selected.node.name }}</strong><code>{{ selected.node.code }}</code>
                <p>{{ stageLabel(selected.node.stage) }}（{{ selected.node.stage }}） · {{ selected.node.claims.length ? `已领取${selected.node.claims.length}次` : "未领取" }}</p>
                <div><van-button size="small" color="#17324d" @click="claim(selected.node)">领取</van-button>
                  <van-button size="small" plain @click="beginSavedEdit(selected.node)">修改</van-button>
                  <van-button size="small" plain type="danger" @click="removeSaved(selected.node)">删除</van-button></div>
              </template>
            </div>
            <div v-if="childKinds.length" class="component-next-level">
              <div><p class="eyebrow">继续询问</p><h3>“{{ selected.name || `未命名${labels[selected.kind]}` }}”下面有什么？</h3></div>
              <div class="component-kind-actions"><button v-for="kind in childKinds" :key="kind" type="button"
                :disabled="kind === 'software'" @click="addDraft(kind)">
                <span>＋</span><strong>{{ labels[kind] }}</strong><small>{{ kind === 'software' ? "为保证与项目文件编号规则一致，请转到文件编号处对软件/逻辑的代码进行编号" : "增加一个" }}</small></button></div>
            </div>
            <div v-else class="component-leaf-note">该节点是当前规则下的末级，无需继续填写。</div>
          </template>
          <div v-else class="component-empty-editor"><strong>先增加一台整机</strong><p>完整填写所有层级后，再统一生成编码。</p></div>
        </section>
      </section>
      <footer class="component-generate-bar">
        <div><strong v-if="needsRenumber">删除已完成，编号待重新生成</strong><strong v-else>{{ completedDrafts }} / {{ drafts.length }} 项已填写</strong><span v-if="emptyDrafts">请先填写剩余 {{ emptyDrafts }} 项的名称</span>
          <span v-else-if="needsRenumber">点击右侧按钮刷新全部产品组成编号</span>
          <span v-else-if="drafts.length">层级填写完成后可统一生成</span><span v-else>当前没有草稿</span></div>
        <van-button color="#176443" :disabled="(!drafts.length && !needsRenumber) || !!emptyDrafts" :loading="saving" @click="generateAll">统一生成全部编号</van-button>
      </footer>
    </template>
  </div></main>
</template>
