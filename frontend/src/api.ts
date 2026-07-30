import type {
  BatchItem,
  FileCode,
  Me,
  Project,
  ProjectInitResult,
  Role
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
  }
}

let csrfToken = "";

export function setCsrfToken(value: string): void {
  csrfToken = value;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include"
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // 保留通用错误信息。
    }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function getMe(): Promise<Me> {
  const me = await request<Me>("/api/me");
  setCsrfToken(me.csrf_token);
  return me;
}

export async function startQrLogin(): Promise<{
  mode: "mock" | "live";
  authorization_url: string | null;
}> {
  return request("/api/auth/wecom/qr/start");
}

export async function devLogin(role: Role): Promise<Me> {
  const me = await request<Me>("/api/auth/dev-login", {
    method: "POST",
    body: JSON.stringify({
      user_id: role === "admin" ? "admin-001" : "user-001",
      name: role === "admin" ? "配置管理员" : "项目成员",
      role
    })
  });
  setCsrfToken(me.csrf_token);
  return me;
}

export async function logout(): Promise<void> {
  await request<void>("/api/auth/logout", { method: "POST" });
  setCsrfToken("");
}

export function listProjects(admin = false): Promise<Project[]> {
  return request<Project[]>(admin ? "/api/admin/projects" : "/api/projects");
}

export function listProjectCodes(projectId: number): Promise<FileCode[]> {
  return request<FileCode[]>(`/api/projects/${projectId}/codes`);
}

export function getAdminProject(projectId: number): Promise<ProjectInitResult> {
  return request<ProjectInitResult>(`/api/admin/projects/${projectId}`);
}

export async function exportAdminProjectCodes(
  projectId: number
): Promise<Blob> {
  const response = await fetch(`/api/admin/projects/${projectId}/export`, {
    credentials: "include"
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // 保留通用错误信息。
    }
    throw new ApiError(response.status, message);
  }
  return response.blob();
}

export async function initializeProject(
  projectName: string,
  projectCode: string,
  file: File
): Promise<ProjectInitResult> {
  const form = new FormData();
  form.append("project_name", projectName);
  form.append("project_code", projectCode);
  form.append("file", file);
  return request<ProjectInitResult>("/api/admin/projects/init", {
    method: "POST",
    body: form
  });
}

export async function importProjectCodes(
  projectId: number,
  file: File
): Promise<ProjectInitResult> {
  const form = new FormData();
  form.append("file", file);
  return request<ProjectInitResult>(
    `/api/admin/projects/${projectId}/codes/import`,
    {
      method: "POST",
      body: form
    }
  );
}

export function confirmProject(projectId: number): Promise<Project> {
  return request<Project>(`/api/admin/projects/${projectId}/confirm`, {
    method: "POST"
  });
}

export function retryProjectCode(
  projectId: number,
  batchItemId: number,
  fileName: string
): Promise<ProjectInitResult["items"][number]> {
  return request(
    `/api/admin/projects/${projectId}/batch-items/${batchItemId}/retry`,
    {
    method: "POST",
    body: JSON.stringify({ file_name: fileName })
    }
  );
}

export function manuallyNumberProjectBatchItem(
  projectId: number,
  batchItemId: number,
  fileName: string,
  finalCode: string
): Promise<ProjectInitResult["items"][number]> {
  return request(
    `/api/admin/projects/${projectId}/batch-items/${batchItemId}/manual`,
    {
      method: "POST",
      body: JSON.stringify({
        file_name: fileName,
        final_code: finalCode
      })
    }
  );
}

export function addAdminProjectCode(
  projectId: number,
  fileName: string
): Promise<BatchItem> {
  return request<BatchItem>(`/api/admin/projects/${projectId}/codes`, {
    method: "POST",
    body: JSON.stringify({ file_name: fileName })
  });
}

export function addAdminManualProjectCode(
  projectId: number,
  fileName: string,
  finalCode: string
): Promise<BatchItem> {
  return request<BatchItem>(
    `/api/admin/projects/${projectId}/codes/manual`,
    {
      method: "POST",
      body: JSON.stringify({
        file_name: fileName,
        final_code: finalCode
      })
    }
  );
}

export function deleteAdminProjectCode(
  projectId: number,
  fileCodeId: number
): Promise<void> {
  return request<void>(
    `/api/admin/projects/${projectId}/codes/${fileCodeId}`,
    { method: "DELETE" }
  );
}

export function deleteAdminProject(projectId: number): Promise<void> {
  return request<void>(`/api/admin/projects/${projectId}`, {
    method: "DELETE"
  });
}

export function batchDeleteAdminProjectFiles(
  projectId: number,
  fileCodeIds: number[],
  batchItemIds: number[]
): Promise<void> {
  return request<void>(
    `/api/admin/projects/${projectId}/files/batch-delete`,
    {
      method: "POST",
      body: JSON.stringify({
        file_code_ids: fileCodeIds,
        batch_item_ids: batchItemIds
      })
    }
  );
}

export function deleteAdminBatchItem(
  projectId: number,
  batchItemId: number
): Promise<void> {
  return request<void>(
    `/api/admin/projects/${projectId}/batch-items/${batchItemId}`,
    { method: "DELETE" }
  );
}

export function searchCodes(projectId: number, name: string): Promise<FileCode[]> {
  const params = new URLSearchParams({
    project_id: String(projectId),
    name
  });
  return request<FileCode[]>(`/api/codes/search?${params}`);
}

export function claimCode(fileCodeId: number): Promise<{ file_code: FileCode }> {
  return request(`/api/codes/${fileCodeId}/claim`, { method: "POST" });
}

export function generateMissingCode(projectId: number, fileName: string): Promise<FileCode> {
  return request<FileCode>("/api/codes/generate", {
    method: "POST",
    body: JSON.stringify({
      project_id: projectId,
      file_name: fileName
    })
  });
}
