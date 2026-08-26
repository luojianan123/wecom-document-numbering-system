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
  special_numbering: boolean;
  created_at: string;
}

export interface ProjectNumberRequest {
  id: number;
  project_code: string;
  requested_by_id: number;
  requester_name: string;
  requester_user_id: string;
  status: "pending" | "processed";
  created_at: string;
  processed_at: string | null;
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

export interface ClaimRecord {
  id: number;
  claimant_name: string;
  claimed_at: string;
}

export interface BatchItem {
  id: number | null;
  file_code_id: number | null;
  original_name: string;
  success: boolean;
  standard_name: string | null;
  final_code: string | null;
  error: string | null;
  claims: ClaimRecord[];
}

export interface SimilarName {
  standard_name: string;
  score: number;
}

export interface NameReview {
  id: number;
  project_id: number;
  project: Project;
  requested_by_id: number;
  original_name: string;
  proposed_standard_name: string | null;
  issue_summary: string;
  similar_names: SimilarName[];
  status: "pending" | "approved" | "rejected";
  reviewed_name: string | null;
  file_code_id: number | null;
  file_code: FileCode | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface GenerateCodeResult {
  status: "generated" | "existing" | "pending_review";
  message: string;
  file_code: FileCode | null;
  review: NameReview | null;
}

export interface ProjectInitResult {
  project: Project;
  items: BatchItem[];
  success_count: number;
  failure_count: number;
}


export interface ComponentClaim {
  id: number;
  claimant_name: string;
  claimed_at: string;
}

export type ComponentKind =
  | "machine"
  | "component"
  | "structure"
  | "hardware"
  | "software"
  | "other"
  | "part";

export interface ComponentNode {
  id: number;
  component_project_id: number;
  parent_id: number | null;
  kind: ComponentKind;
  name: string;
  code: string;
  stage: "G" | "Z";
  sequence: number;
  created_by_name: string;
  claims: ComponentClaim[];
}

export interface ComponentProject {
  id: number;
  project_code: string;
  status: string;
  created_at: string;
  created_by_name: string;
  nodes: ComponentNode[];
}

export interface ComponentProjectSummary {
  id: number;
  project_code: string;
  status: string;
  created_at: string;
  created_by_name: string;
  machine_count: number;
  node_count: number;
  claim_count: number;
}

export interface ComponentDraftNode {
  client_id: string;
  parent_id: number | null;
  parent_client_id: string | null;
  kind: ComponentKind;
  name: string;
  is_prototype: boolean;
}
