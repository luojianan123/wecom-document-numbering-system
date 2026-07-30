export type Role = "user" | "admin";

export interface User {
  id: number;
  wecom_user_id: string;
  name: string;
  role: Role;
}

export interface Me {
  authenticated: boolean;
  user: User;
  csrf_token: string;
  auth_mode: "mock" | "live";
}

export interface Project {
  id: number;
  project_code: string;
  project_name: string;
  status: string;
  created_at: string;
}

export interface FileCode {
  id: number;
  project_id: number;
  original_name: string;
  standard_name: string;
  segment_a: string;
  segment_b: string;
  segment_c: string;
  segment_d: string;
  segment_e: string;
  segment_f: string;
  segment_g: string;
  segment_h: string;
  final_code: string;
  source: string;
  enabled: boolean;
}

export interface BatchItem {
  id: number | null;
  file_code_id: number | null;
  original_name: string;
  success: boolean;
  standard_name: string | null;
  final_code: string | null;
  error: string | null;
}

export interface ProjectInitResult {
  project: Project;
  items: BatchItem[];
  success_count: number;
  failure_count: number;
}
